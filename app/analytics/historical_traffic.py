"""Bounded Site-scoped history derived from persisted AP rate facts."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from .models import (
    CurrentApTrafficItem,
    CurrentTrafficSnapshot,
    HistoricalSiteTraffic,
    HistoricalTrafficApCoverage,
    HistoricalTrafficApItem,
    HistoricalTrafficApNow,
    HistoricalTrafficApPopulation,
    HistoricalTrafficApSeries,
    HistoricalTrafficByAp,
    HistoricalTrafficBucket,
    HistoricalTrafficCoverage,
    HistoricalTrafficPeriodIntervalEvidence,
    HistoricalTrafficPeriodStatistics,
    HistoricalTrafficPeriodValues,
    HistoricalTrafficPeakEvent,
    HistoricalTrafficBusiestBucket,
    HistoricalTrafficBusiestHour,
    HistoricalTrafficPeakLoad,
    HistoricalTrafficQuality,
    HistoricalTrafficRange,
    HistoricalTrafficSourceSelection,
)
from .source_gateway import (
    AnalyticsQueryDeadlineExceeded,
    AnalyticsSourceGateway,
    AnalyticsSourceUnavailable,
    QueryDeadline,
)
from .validation import AnalyticsQueryValidationError, format_utc, parse_utc, require_site


UTC = timezone.utc
MAX_SITE_HISTORY_BUCKETS = 720
MAX_SITE_SAMPLE_SOURCE_SKEW_SECONDS = 60
MAX_TRAFFIC_BY_AP_SUPPORTED_APS = 12
_AUTO_BUCKET_SECONDS = (300, 900, 3600, 21600, 86400, 604800, 2592000)
_QUALITY_REASONS = (
    "no_baseline", "counter_reset", "gap_too_large",
    "invalid_elapsed", "source_unavailable",
)
_BUCKET_REASONS = ("ok", *_QUALITY_REASONS)
_MAC_PATTERN = re.compile(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}")


class HistoricalTrafficValidationError(ValueError):
    """Caller input violates the Historical Traffic read contract."""


class HistoricalTrafficSourceUnavailable(RuntimeError):
    """Persisted facts cannot safely satisfy Historical Traffic."""


@dataclass(frozen=True, slots=True)
class _HistoricalTrafficPeakValues:
    status: str
    peak: HistoricalTrafficPeriodValues
    interval_evidence: HistoricalTrafficPeriodIntervalEvidence


class HistoricalTrafficReadService:
    """Read canonical traffic buckets without polling or source writes."""

    def __init__(
        self,
        gateway: AnalyticsSourceGateway,
        *,
        quality_gap_threshold_seconds: float = 180.0,
        max_query_duration_seconds: float = 10.0,
        clock=lambda: datetime.now(UTC),
    ):
        if not _positive_finite(quality_gap_threshold_seconds):
            raise ValueError("quality gap threshold must be positive")
        if not _positive_finite(max_query_duration_seconds):
            raise ValueError("query duration must be positive")
        self._gateway = gateway
        self._gap_threshold = float(quality_gap_threshold_seconds)
        self._query_seconds = float(max_query_duration_seconds)
        self._clock = clock

    def get_site_history(
        self,
        site_id: str,
        *,
        from_utc: str,
        to_utc: str,
        evaluated_at_utc: str | None = None,
        bucket_seconds: int | None = None,
        deadline: QueryDeadline | None = None,
        include_period_statistics: bool = False,
        include_peak_load: bool = False,
        include_ap_traffic: bool = False,
        current_cycle_id: str | None = None,
    ) -> HistoricalSiteTraffic:
        if type(include_period_statistics) is not bool:
            raise HistoricalTrafficValidationError(
                "include_period_statistics must be a boolean"
            )
        if type(include_peak_load) is not bool:
            raise HistoricalTrafficValidationError(
                "include_peak_load must be a boolean"
            )
        if type(include_ap_traffic) is not bool:
            raise HistoricalTrafficValidationError(
                "include_ap_traffic must be a boolean"
            )
        if current_cycle_id is not None and (
            not isinstance(current_cycle_id, str) or not current_cycle_id
        ):
            raise HistoricalTrafficValidationError("current_cycle_id is invalid")
        try:
            site = require_site(site_id)
            start = parse_utc(from_utc, "from_utc")
            end = parse_utc(to_utc, "to_utc")
            evaluated = (
                self._clock().astimezone(UTC)
                if evaluated_at_utc is None
                else parse_utc(evaluated_at_utc, "evaluated_at_utc")
            )
        except AnalyticsQueryValidationError as exc:
            raise HistoricalTrafficValidationError(str(exc)) from exc
        if start >= end:
            raise HistoricalTrafficValidationError("from_utc must be before to_utc")
        if end > evaluated:
            raise HistoricalTrafficValidationError(
                "to_utc must not exceed evaluated_at_utc"
            )
        duration = (end - start).total_seconds()
        selected_bucket = _bucket_size(duration, bucket_seconds)
        bucket_count = math.ceil(duration / selected_bucket)
        if bucket_count > MAX_SITE_HISTORY_BUCKETS:
            raise HistoricalTrafficValidationError("bucket count exceeds 720")

        evaluated_text = format_utc(evaluated)
        query_deadline = deadline or QueryDeadline.after(self._query_seconds)
        try:
            data = self._gateway.historical_traffic_data(
                site_id=site,
                from_utc=format_utc(start),
                to_utc=format_utc(end),
                evaluated_at_utc=evaluated_text,
                bucket_seconds=selected_bucket,
                gap_threshold_seconds=self._gap_threshold,
                max_site_sample_source_skew_seconds=(
                    MAX_SITE_SAMPLE_SOURCE_SKEW_SECONDS
                ),
                deadline=query_deadline,
                include_period_statistics=include_period_statistics,
                include_peak_load=include_peak_load,
                include_ap_traffic=include_ap_traffic,
                current_cycle_id=current_cycle_id,
            )
        except AnalyticsQueryDeadlineExceeded:
            raise
        except AnalyticsSourceUnavailable as exc:
            raise HistoricalTrafficSourceUnavailable(
                "Historical traffic source is unavailable"
            ) from exc

        meta = dict(data.get("meta") or {})
        integrity_failures = _integer(meta.get("integrity_failure_count", 0))
        if integrity_failures:
            raise HistoricalTrafficSourceUnavailable(
                "Historical traffic source integrity is unavailable"
            )
        rows = {int(row["bucket_index"]): dict(row) for row in data["buckets"]}
        buckets: list[HistoricalTrafficBucket] = []
        prior_source: str | None = None
        for index in range(bucket_count):
            bucket_start = start + timedelta(seconds=index * selected_bucket)
            bucket_end = min(bucket_start + timedelta(seconds=selected_bucket), end)
            row = rows.get(index)
            bucket = self._bucket(row, bucket_start, bucket_end, prior_source)
            buckets.append(bucket)
            prior_source = bucket.selected_source

        available_from = _optional_utc(meta.get("available_from_utc"))
        available_through = _optional_utc(meta.get("available_through_utc"))
        watermark = _optional_utc(meta.get("source_watermark_utc"))
        source_age = None
        if watermark is not None:
            source_age = max(
                (evaluated - parse_utc(watermark, "source_watermark_utc")).total_seconds(),
                0.0,
            )
        usable = sum(item.complete_site_sample_count > 0 for item in buckets)
        complete = sum(item.status == "complete" for item in buckets)
        partial = sum(item.status == "partial" for item in buckets)
        missing = sum(item.status == "none" for item in buckets)
        coverage_status = (
            "none" if usable == 0 else
            "complete" if complete == bucket_count else "partial"
        )
        attempts = dict(data.get("attempts") or {})
        reason_totals = {
            reason: sum(item.rate_reason_counts[reason] for item in buckets)
            for reason in _QUALITY_REASONS
        }
        traffic_range = HistoricalTrafficRange(
            site_id=site,
            from_utc=format_utc(start),
            to_utc=format_utc(end),
            evaluated_at_utc=evaluated_text,
            bucket_seconds=selected_bucket,
            bucket_count=bucket_count,
            max_site_sample_source_skew_seconds=(
                MAX_SITE_SAMPLE_SOURCE_SKEW_SECONDS
            ),
        )
        coverage = HistoricalTrafficCoverage(
            status=coverage_status,
            available_from_utc=available_from,
            available_through_utc=available_through,
            source_watermark_utc=watermark,
            source_age_seconds=source_age,
            bucket_count=bucket_count,
            complete_bucket_count=complete,
            partial_bucket_count=partial,
            missing_bucket_count=missing,
            canonical_cycle_count=sum(item.canonical_cycle_count for item in buckets),
            complete_site_sample_count=sum(
                item.complete_site_sample_count for item in buckets
            ),
            excluded_site_sample_count=sum(
                item.excluded_site_sample_count for item in buckets
            ),
            gap_bucket_count=sum(item.gap_count_over_threshold > 0 for item in buckets),
            source_transition_count=sum(item.source_changed_from_previous for item in buckets),
        )
        quality = HistoricalTrafficQuality(
            partial_cycle_count=_integer(attempts.get("partial_cycle_count", 0)),
            failed_cycle_count=_integer(attempts.get("failed_cycle_count", 0)),
            shutdown_cycle_count=_integer(attempts.get("shutdown_cycle_count", 0)),
            abandoned_cycle_count=_integer(attempts.get("abandoned_cycle_count", 0)),
            running_cycle_count=_integer(attempts.get("running_cycle_count", 0)),
            no_baseline_count=reason_totals["no_baseline"],
            counter_reset_count=reason_totals["counter_reset"],
            gap_too_large_count=reason_totals["gap_too_large"],
            invalid_elapsed_count=reason_totals["invalid_elapsed"],
            source_unavailable_count=reason_totals["source_unavailable"],
            source_skew_excluded_sample_count=sum(
                item.selected_source_skew_excluded_sample_count for item in buckets
            ),
            integrity_failure_count=0,
        )
        result_status = (
            "insufficient_data" if coverage_status == "none" else
            "ok" if coverage_status == "complete" else "partial"
        )
        period_statistics = None
        peak_values = None
        if include_period_statistics or include_peak_load:
            peak_values = self._peak_values(
                data.get("period_statistics"),
                start=start,
                end=end,
                history_status=result_status,
            )
        if include_period_statistics:
            assert peak_values is not None
            period_statistics = self._period_statistics(
                data.get("period_statistics"),
                peak_values=peak_values,
            )
        peak_load = None
        if include_peak_load:
            assert peak_values is not None
            query_deadline.require_remaining()
            peak_load = self._peak_load(
                data.get("peak_samples"),
                buckets=tuple(buckets),
                peak_values=peak_values,
                start=start,
                end=end,
                history_status=result_status,
            )
            query_deadline.require_remaining()
        ap_traffic = None
        if include_ap_traffic:
            ap_traffic = self._ap_traffic(
                data.get("ap_population"),
                data.get("ap_rows"),
                buckets=tuple(buckets),
                history_status=result_status,
            )
            query_deadline.require_remaining()
        return HistoricalSiteTraffic(
            status=result_status,
            range=traffic_range,
            buckets=tuple(buckets),
            coverage=coverage,
            quality=quality,
            period_statistics=period_statistics,
            peak_load=peak_load,
            ap_traffic=ap_traffic,
        )

    def compose_current_ap_traffic(
        self,
        value: HistoricalSiteTraffic,
        *,
        current_snapshot: CurrentTrafficSnapshot | None,
        current_population_count: int,
        current_items: tuple[CurrentApTrafficItem, ...],
    ) -> HistoricalSiteTraffic:
        """Attach bounded Current-owner evidence without changing History facts."""
        ap_traffic = value.ap_traffic
        if ap_traffic is None:
            raise HistoricalTrafficValidationError("AP Traffic was not requested")
        if ap_traffic.population.current_population_count != current_population_count:
            raise HistoricalTrafficSourceUnavailable(
                "Current AP population identity is unavailable"
            )
        if ap_traffic.status == "unsupported_population":
            if ap_traffic.items:
                raise HistoricalTrafficSourceUnavailable(
                    "Unsupported AP population contains items"
                )
            return value
        current = {item.ap_mac: item for item in current_items}
        if len(current) != len(current_items) or len(current) != current_population_count:
            raise HistoricalTrafficSourceUnavailable(
                "Current AP population projection is unavailable"
            )
        projected: list[HistoricalTrafficApItem] = []
        any_numeric = False
        for item in ap_traffic.items:
            source = current.get(item.ap_mac)
            if source is None:
                now = _unavailable_now()
                display_name = item.display_name
                display_source = item.display_name_source
            else:
                now = HistoricalTrafficApNow(
                    status=source.rate_status,
                    download_mbps=source.download_mbps,
                    upload_mbps=source.upload_mbps,
                    total_mbps=source.total_mbps,
                    download_reason=source.download_reason,
                    upload_reason=source.upload_reason,
                    observed_at=source.observed_at,
                    age_seconds=source.age_seconds,
                    selected_source=source.selected_source,
                )
                if isinstance(source.name, str) and source.name.strip():
                    display_name = source.name.strip()
                    display_source = "current"
                else:
                    display_name = item.display_name
                    display_source = item.display_name_source
            historical_numeric = item.coverage.accepted_sample_count > 0
            current_numeric = now.download_mbps is not None or now.upload_mbps is not None
            any_numeric = any_numeric or historical_numeric or current_numeric
            complete = (
                item.coverage.status == "complete"
                and current_snapshot is not None
                and current_snapshot.freshness_status == "fresh"
                and now.status == "valid"
            )
            status = "complete" if complete else (
                "partial" if historical_numeric or current_numeric
                else "insufficient_data"
            )
            projected.append(replace(
                item,
                display_name=display_name,
                display_name_source=display_source,
                status=status,
                now=now,
            ))
        complete = (
            value.status == "ok"
            and ap_traffic.population.population_count > 0
            and current_snapshot is not None
            and current_snapshot.freshness_status == "fresh"
            and all(item.status == "complete" for item in projected)
        )
        status = "ok" if complete else (
            "partial" if any_numeric else "insufficient_data"
        )
        return replace(value, ap_traffic=replace(
            ap_traffic,
            status=status,
            current_snapshot=current_snapshot,
            items=tuple(projected),
        ))

    def _ap_traffic(
        self,
        raw_population: Any,
        raw_rows: Any,
        *,
        buckets: tuple[HistoricalTrafficBucket, ...],
        history_status: str,
    ) -> HistoricalTrafficByAp:
        if not isinstance(raw_population, Mapping) or not isinstance(
            raw_rows, (tuple, list)
        ):
            raise HistoricalTrafficSourceUnavailable(
                "Historical AP Traffic projection is unavailable"
            )
        population_count = _integer(raw_population.get("population_count"))
        current_count = _integer(raw_population.get("current_population_count"))
        historical_count = _integer(
            raw_population.get("historical_population_count")
        )
        if current_count > population_count or historical_count > population_count:
            raise HistoricalTrafficSourceUnavailable(
                "Historical AP population is invalid"
            )
        supported = population_count <= MAX_TRAFFIC_BY_AP_SUPPORTED_APS
        population = HistoricalTrafficApPopulation(
            population_count=population_count,
            current_population_count=current_count,
            historical_population_count=historical_count,
            supported_max_ap_count=MAX_TRAFFIC_BY_AP_SUPPORTED_APS,
            returned_ap_count=population_count if supported else 0,
            population_complete=supported,
        )
        if not supported:
            if raw_rows:
                raise HistoricalTrafficSourceUnavailable(
                    "Unsupported AP population was materialized"
                )
            return HistoricalTrafficByAp(
                status="unsupported_population",
                population=population,
                current_snapshot=None,
                items=(),
            )
        grouped: dict[str, list[Mapping[str, Any]]] = {}
        for raw in raw_rows:
            if not isinstance(raw, Mapping):
                raise HistoricalTrafficSourceUnavailable(
                    "Historical AP Traffic row is invalid"
                )
            mac = raw.get("ap_mac")
            if not isinstance(mac, str) or _MAC_PATTERN.fullmatch(mac) is None:
                raise HistoricalTrafficSourceUnavailable(
                    "Historical AP identity is invalid"
                )
            grouped.setdefault(mac, []).append(raw)
        if len(grouped) != population_count:
            raise HistoricalTrafficSourceUnavailable(
                "Historical AP population projection is incomplete"
            )
        items = tuple(
            self._ap_item(mac, grouped[mac], buckets, history_status)
            for mac in sorted(grouped)
        )
        any_numeric = any(item.coverage.accepted_sample_count > 0 for item in items)
        return HistoricalTrafficByAp(
            status="partial" if any_numeric else "insufficient_data",
            population=population,
            current_snapshot=None,
            items=items,
        )

    def _ap_item(
        self,
        mac: str,
        rows: list[Mapping[str, Any]],
        buckets: tuple[HistoricalTrafficBucket, ...],
        history_status: str,
    ) -> HistoricalTrafficApItem:
        first = rows[0]
        aggregate_fields = (
            "ap_current_name", "ap_historical_name",
            "ap_sample_opportunity_count", "ap_accepted_sample_count",
            "ap_site_accepted_interval_seconds", "ap_accepted_interval_seconds",
            "ap_weighted_download", "ap_weighted_upload", "ap_peak_download",
            "ap_peak_upload", "ap_peak_total", "ap_no_baseline_count",
            "ap_counter_reset_count", "ap_gap_too_large_count",
            "ap_invalid_elapsed_count", "ap_source_unavailable_count",
            "ap_missing_selected_source_sample_count",
            "ap_source_transition_excluded_interval_count",
        )
        if any(
            row.get(field) != first.get(field)
            for row in rows for field in aggregate_fields
        ):
            raise HistoricalTrafficSourceUnavailable(
                "Historical AP aggregate is inconsistent"
            )
        statuses = ["none"] * len(buckets)
        download: list[float | None] = [None] * len(buckets)
        upload: list[float | None] = [None] * len(buckets)
        seen: set[int] = set()
        for row in rows:
            raw_index = row.get("ap_bucket_index")
            if raw_index is None:
                continue
            index = _integer(raw_index)
            if index >= len(buckets) or index in seen:
                raise HistoricalTrafficSourceUnavailable(
                    "Historical AP bucket alignment is invalid"
                )
            seen.add(index)
            opportunity = _integer(row.get("ap_bucket_opportunity_count"))
            accepted = _integer(row.get("ap_bucket_accepted_count"))
            if accepted > opportunity:
                raise HistoricalTrafficSourceUnavailable(
                    "Historical AP bucket evidence is invalid"
                )
            if accepted:
                download[index] = _finite_nonnegative(row.get("ap_bucket_download"))
                upload[index] = _finite_nonnegative(row.get("ap_bucket_upload"))
                statuses[index] = "complete" if accepted == opportunity else "partial"
            elif row.get("ap_bucket_download") is not None or row.get("ap_bucket_upload") is not None:
                raise HistoricalTrafficSourceUnavailable(
                    "Historical AP missing bucket contains values"
                )
        complete_count = statuses.count("complete")
        partial_count = statuses.count("partial")
        missing_count = statuses.count("none")
        sample_opportunities = _integer(first.get("ap_sample_opportunity_count"))
        accepted_samples = _integer(first.get("ap_accepted_sample_count"))
        if accepted_samples > sample_opportunities:
            raise HistoricalTrafficSourceUnavailable(
                "Historical AP sample evidence is invalid"
            )
        site_seconds = _finite_nonnegative(
            first.get("ap_site_accepted_interval_seconds")
        )
        ap_seconds = _finite_nonnegative(first.get("ap_accepted_interval_seconds"))
        if ap_seconds > site_seconds:
            raise HistoricalTrafficSourceUnavailable(
                "Historical AP interval evidence is invalid"
            )
        if ap_seconds:
            weighted_download = _finite_nonnegative(first.get("ap_weighted_download"))
            weighted_upload = _finite_nonnegative(first.get("ap_weighted_upload"))
            average = HistoricalTrafficPeriodValues(
                weighted_download / ap_seconds,
                weighted_upload / ap_seconds,
                (weighted_download + weighted_upload) / ap_seconds,
            )
        else:
            if first.get("ap_weighted_download") is not None or first.get("ap_weighted_upload") is not None:
                raise HistoricalTrafficSourceUnavailable(
                    "Historical AP weighting is invalid"
                )
            average = HistoricalTrafficPeriodValues(None, None, None)
        if accepted_samples:
            peak = HistoricalTrafficPeriodValues(
                _finite_nonnegative(first.get("ap_peak_download")),
                _finite_nonnegative(first.get("ap_peak_upload")),
                _finite_nonnegative(first.get("ap_peak_total")),
            )
        else:
            if any(first.get(field) is not None for field in (
                "ap_peak_download", "ap_peak_upload", "ap_peak_total"
            )):
                raise HistoricalTrafficSourceUnavailable(
                    "Historical AP Peak is invalid"
                )
            peak = HistoricalTrafficPeriodValues(None, None, None)
        history_numeric = accepted_samples > 0
        coverage_status = (
            "insufficient_data" if not history_numeric else
            "complete" if history_status == "ok" and complete_count == len(buckets)
            and ap_seconds == site_seconds else "partial"
        )
        coverage = HistoricalTrafficApCoverage(
            status=coverage_status,
            bucket_count=len(buckets),
            complete_bucket_count=complete_count,
            partial_bucket_count=partial_count,
            missing_bucket_count=missing_count,
            sample_opportunity_count=sample_opportunities,
            accepted_sample_count=accepted_samples,
            site_accepted_interval_seconds=site_seconds,
            ap_accepted_interval_seconds=ap_seconds,
            ap_interval_coverage_ratio=(
                ap_seconds / site_seconds if site_seconds else None
            ),
            no_baseline_count=_integer(first.get("ap_no_baseline_count")),
            counter_reset_count=_integer(first.get("ap_counter_reset_count")),
            gap_too_large_count=_integer(first.get("ap_gap_too_large_count")),
            invalid_elapsed_count=_integer(first.get("ap_invalid_elapsed_count")),
            source_unavailable_count=_integer(
                first.get("ap_source_unavailable_count")
            ),
            missing_selected_source_sample_count=_integer(
                first.get("ap_missing_selected_source_sample_count")
            ),
            source_transition_excluded_interval_count=_integer(
                first.get("ap_source_transition_excluded_interval_count")
            ),
        )
        current_name = _display_name(first.get("ap_current_name"))
        historical_name = _display_name(first.get("ap_historical_name"))
        if current_name is not None:
            name, name_source = current_name, "current"
        elif historical_name is not None:
            name, name_source = historical_name, "historical"
        else:
            name, name_source = mac, "mac_fallback"
        return HistoricalTrafficApItem(
            ap_mac=mac,
            display_name=name,
            display_name_source=name_source,
            status=coverage_status,
            series=HistoricalTrafficApSeries(
                bucket_count=len(buckets),
                status=tuple(statuses),
                download_mbps=tuple(download),
                upload_mbps=tuple(upload),
            ),
            average=average,
            peak=peak,
            coverage=coverage,
            now=_unavailable_now(),
        )

    def _peak_load(
        self,
        raw_samples: Any,
        *,
        buckets: tuple[HistoricalTrafficBucket, ...],
        peak_values: _HistoricalTrafficPeakValues,
        start: datetime,
        end: datetime,
        history_status: str,
    ) -> HistoricalTrafficPeakLoad:
        if not isinstance(raw_samples, (tuple, list)):
            raise HistoricalTrafficSourceUnavailable(
                "Historical traffic Peak samples are unavailable"
            )
        samples = _peak_samples(
            raw_samples,
            start=start,
            end=end,
            gap_threshold=self._gap_threshold,
        )
        expected = peak_values.interval_evidence.accepted_peak_sample_count
        if len(samples) != expected:
            raise HistoricalTrafficSourceUnavailable(
                "Historical traffic Peak sample count is invalid"
            )
        events = {
            name: _peak_event(samples, name)
            for name in ("download", "upload", "total")
        }
        expected_peaks = peak_values.peak
        for name, expected_value in (
            ("download", expected_peaks.download_mbps),
            ("upload", expected_peaks.upload_mbps),
            ("total", expected_peaks.total_mbps),
        ):
            actual = events[name].value_mbps
            if actual is None or expected_value is None:
                if actual is not expected_value:
                    raise HistoricalTrafficSourceUnavailable(
                        "Historical traffic Peak value is invalid"
                    )
            elif not math.isclose(actual, expected_value, rel_tol=1e-9, abs_tol=1e-9):
                raise HistoricalTrafficSourceUnavailable(
                    "Historical traffic Peak value is invalid"
                )
        busiest_bucket = _busiest_bucket(buckets)
        busiest_hour = _busiest_hour(samples)
        if not samples:
            status = "insufficient_data"
            if (
                busiest_bucket.status != "insufficient_data"
                or busiest_hour.status != "insufficient_data"
            ):
                raise HistoricalTrafficSourceUnavailable(
                    "Historical traffic Peak insufficient state is invalid"
                )
        else:
            status = (
                "ok" if (
                    history_status == "ok"
                    and peak_values.status == "ok"
                    and busiest_bucket.status == "ok"
                    and busiest_hour.status == "ok"
                ) else "partial"
            )
        return HistoricalTrafficPeakLoad(
            status=status,
            events=events,
            busiest_bucket=busiest_bucket,
            busiest_hour=busiest_hour,
        )

    def _peak_values(
        self,
        raw: Any,
        *,
        start: datetime,
        end: datetime,
        history_status: str,
    ) -> _HistoricalTrafficPeakValues:
        if not isinstance(raw, Mapping):
            raise HistoricalTrafficSourceUnavailable(
                "Historical traffic Statistics aggregate is unavailable"
            )
        peak_count = _integer(raw.get("accepted_peak_sample_count"))
        candidate_count = _integer(raw.get("candidate_interval_count"))
        accepted_count = _integer(raw.get("accepted_interval_count"))
        gap_count = _integer(raw.get("excluded_gap_interval_count"))
        transition_count = _integer(
            raw.get("excluded_source_transition_interval_count")
        )
        invalid_count = _integer(raw.get("invalid_period_interval_count"))
        accepted_seconds = _finite_nonnegative(
            raw.get("accepted_interval_seconds")
        )
        if (
            candidate_count != max(peak_count - 1, 0)
            or candidate_count
            != accepted_count + gap_count + transition_count + invalid_count
        ):
            raise HistoricalTrafficSourceUnavailable(
                "Historical traffic Statistics interval evidence is invalid"
            )
        duration = (end - start).total_seconds()
        if accepted_seconds > duration:
            raise HistoricalTrafficSourceUnavailable(
                "Historical traffic Statistics interval duration is invalid"
            )
        first = _optional_utc(raw.get("first_sample_at"))
        last = _optional_utc(raw.get("last_sample_at"))
        if peak_count == 0:
            if first is not None or last is not None:
                raise HistoricalTrafficSourceUnavailable(
                    "Historical traffic Statistics sample boundary is invalid"
                )
            leading = trailing = duration
            peak = HistoricalTrafficPeriodValues(None, None, None)
        else:
            if first is None or last is None:
                raise HistoricalTrafficSourceUnavailable(
                    "Historical traffic Statistics sample boundary is invalid"
                )
            first_at = parse_utc(first, "first_sample_at")
            last_at = parse_utc(last, "last_sample_at")
            if first_at < start or last_at >= end or first_at > last_at:
                raise HistoricalTrafficSourceUnavailable(
                    "Historical traffic Statistics sample boundary is invalid"
                )
            leading = (first_at - start).total_seconds()
            trailing = (end - last_at).total_seconds()
            peak = HistoricalTrafficPeriodValues(
                _finite_nonnegative(raw.get("peak_download")),
                _finite_nonnegative(raw.get("peak_upload")),
                _finite_nonnegative(raw.get("peak_total")),
            )
        status = (
            "insufficient_data" if peak_count == 0 else
            "ok" if (
                history_status == "ok"
                and accepted_count > 0
                and gap_count == 0
                and transition_count == 0
                and invalid_count == 0
            ) else "partial"
        )
        return _HistoricalTrafficPeakValues(
            status=status,
            peak=peak,
            interval_evidence=HistoricalTrafficPeriodIntervalEvidence(
                range_seconds=duration,
                candidate_interval_count=candidate_count,
                accepted_interval_count=accepted_count,
                accepted_interval_seconds=accepted_seconds,
                interval_coverage_ratio=accepted_seconds / duration,
                excluded_gap_interval_count=gap_count,
                excluded_source_transition_interval_count=transition_count,
                invalid_period_interval_count=invalid_count,
                accepted_peak_sample_count=peak_count,
                leading_unweighted_seconds=leading,
                trailing_unweighted_seconds=trailing,
            ),
        )

    def _period_statistics(
        self,
        raw: Any,
        *,
        peak_values: _HistoricalTrafficPeakValues,
    ) -> HistoricalTrafficPeriodStatistics:
        if not isinstance(raw, Mapping):
            raise HistoricalTrafficSourceUnavailable(
                "Historical traffic Statistics aggregate is unavailable"
            )
        evidence = peak_values.interval_evidence
        if evidence.accepted_interval_count == 0:
            if evidence.accepted_interval_seconds != 0:
                raise HistoricalTrafficSourceUnavailable(
                    "Historical traffic Statistics weighting is invalid"
                )
            average = HistoricalTrafficPeriodValues(None, None, None)
        else:
            if evidence.accepted_interval_seconds <= 0:
                raise HistoricalTrafficSourceUnavailable(
                    "Historical traffic Statistics weighting is invalid"
                )
            weighted_download = _finite_nonnegative(raw.get("weighted_download"))
            weighted_upload = _finite_nonnegative(raw.get("weighted_upload"))
            average = HistoricalTrafficPeriodValues(
                weighted_download / evidence.accepted_interval_seconds,
                weighted_upload / evidence.accepted_interval_seconds,
                (weighted_download + weighted_upload)
                / evidence.accepted_interval_seconds,
            )
        return HistoricalTrafficPeriodStatistics(
            status=peak_values.status,
            average=average,
            peak=peak_values.peak,
            interval_evidence=evidence,
        )

    def _bucket(
        self,
        row: Mapping[str, Any] | None,
        start: datetime,
        end: datetime,
        prior_source: str | None,
    ) -> HistoricalTrafficBucket:
        if row is None:
            return _empty_bucket(start, end, self._gap_threshold)
        source = str(row["selected_source"])
        sample_count = _integer(row["complete_sample_count"])
        first = _optional_utc(row.get("first_sample"))
        last = _optional_utc(row.get("last_sample"))
        if sample_count:
            assert first is not None and last is not None
            leading = max((parse_utc(first, "first_sample") - start).total_seconds(), 0.0)
            trailing = max((end - parse_utc(last, "last_sample")).total_seconds(), 0.0)
            inter = max(float(row["max_inter_gap"]), 0.0)
            gap_count = _integer(row["inter_gap_count"])
            gap_count += int(leading > self._gap_threshold)
            gap_count += int(trailing > self._gap_threshold)
            status = "complete" if gap_count == 0 else "partial"
            download = _finite_nonnegative(row["download_mbps"])
            upload = _finite_nonnegative(row["upload_mbps"])
            total = download + upload
        else:
            leading = (end - start).total_seconds()
            trailing = leading
            inter = 0.0
            gap_count = int(leading > self._gap_threshold)
            status = "none"
            download = upload = total = None
        canonical = _integer(row["canonical_cycle_count"])
        wired_count = _integer(row["wired_complete_count"])
        lan_count = _integer(row["lan_complete_count"])
        wired_pairs = _integer(row["wired_pairs"])
        lan_pairs = _integer(row["lan_pairs"])
        selected_pairs = wired_pairs if source == "wired" else lan_pairs
        reasons = {
            reason: _integer(row[f"{reason}_count"])
            for reason in _BUCKET_REASONS
        }
        return HistoricalTrafficBucket(
            bucket_start_utc=format_utc(start),
            bucket_end_utc=format_utc(end),
            download_mbps=download,
            upload_mbps=upload,
            total_mbps=total,
            status=status,
            selected_source=source,
            selection_reason=str(row["selection_reason"]),
            source_changed_from_previous=(
                prior_source is not None and prior_source != source
            ),
            canonical_cycle_count=canonical,
            complete_site_sample_count=sample_count,
            excluded_site_sample_count=max(canonical - sample_count, 0),
            total_ap_opportunities=_integer(row["total_ap_opportunities"]),
            selected_pair_valid_ap_opportunities=selected_pairs,
            first_complete_sample_at=first,
            last_complete_sample_at=last,
            leading_gap_seconds=leading,
            trailing_gap_seconds=trailing,
            max_inter_sample_gap_seconds=inter,
            gap_count_over_threshold=gap_count,
            selected_source_skew_excluded_sample_count=_integer(
                row["skew_excluded_count"]
            ),
            rate_reason_counts=reasons,
            source_selection=HistoricalTrafficSourceSelection(
                primary_source="wired",
                selected_source=source,
                selection_reason=str(row["selection_reason"]),
                wired_complete_site_cycle_count=wired_count,
                lan_complete_site_cycle_count=lan_count,
                wired_pair_valid_ap_opportunities=wired_pairs,
                lan_pair_valid_ap_opportunities=lan_pairs,
            ),
        )


def _peak_samples(
    raw_samples: tuple[Any, ...] | list[Any],
    *,
    start: datetime,
    end: datetime,
    gap_threshold: float,
) -> tuple[dict[str, Any], ...]:
    result: list[dict[str, Any]] = []
    previous_at: datetime | None = None
    previous_source: str | None = None
    for raw in raw_samples:
        if not isinstance(raw, Mapping):
            raise HistoricalTrafficSourceUnavailable(
                "Historical traffic Peak sample is invalid"
            )
        sample_at_value = raw.get("finished_at")
        source = raw.get("selected_source")
        if not isinstance(sample_at_value, str) or source not in {"wired", "lan"}:
            raise HistoricalTrafficSourceUnavailable(
                "Historical traffic Peak sample is invalid"
            )
        try:
            sample_at = parse_utc(sample_at_value, "sample_at")
        except AnalyticsQueryValidationError as exc:
            raise HistoricalTrafficSourceUnavailable(
                "Historical traffic Peak sample is invalid"
            ) from exc
        sample_at_text = format_utc(sample_at)
        if sample_at_text != sample_at_value:
            raise HistoricalTrafficSourceUnavailable(
                "Historical traffic Peak sample is invalid"
            )
        if sample_at < start or sample_at >= end:
            raise HistoricalTrafficSourceUnavailable(
                "Historical traffic Peak sample boundary is invalid"
            )
        persisted_previous = raw.get("previous_at")
        expected_previous = None if previous_at is None else format_utc(previous_at)
        if persisted_previous != expected_previous:
            raise HistoricalTrafficSourceUnavailable(
                "Historical traffic Peak sequence is invalid"
            )
        if previous_at is None:
            expected_result = "first"
        else:
            elapsed = (sample_at - previous_at).total_seconds()
            expected_result = (
                "invalid" if elapsed <= 0 else
                "source_transition" if source != previous_source else
                "gap" if elapsed > gap_threshold else "accepted"
            )
        if raw.get("interval_result") != expected_result:
            raise HistoricalTrafficSourceUnavailable(
                "Historical traffic Peak interval is invalid"
            )
        download = _finite_nonnegative(raw.get("download"))
        upload = _finite_nonnegative(raw.get("upload"))
        result.append({
            "sample_at": sample_at,
            "sample_at_utc": sample_at_text,
            "selected_source": source,
            "download": download,
            "upload": upload,
            "total": download + upload,
            "previous_at": previous_at,
            "interval_result": expected_result,
        })
        previous_at = sample_at
        previous_source = source
    return tuple(result)


def _peak_event(
    samples: tuple[dict[str, Any], ...],
    metric: str,
) -> HistoricalTrafficPeakEvent:
    if not samples:
        return HistoricalTrafficPeakEvent(None, None, None, 0)
    value = max(float(sample[metric]) for sample in samples)
    matches = tuple(sample for sample in samples if sample[metric] == value)
    winner = matches[0]
    return HistoricalTrafficPeakEvent(
        value_mbps=value,
        sample_at_utc=str(winner["sample_at_utc"]),
        selected_source=str(winner["selected_source"]),
        occurrence_count=len(matches),
    )


def _busiest_bucket(
    buckets: tuple[HistoricalTrafficBucket, ...],
) -> HistoricalTrafficBusiestBucket:
    usable = tuple(
        bucket for bucket in buckets
        if bucket.status == "complete" and bucket.total_mbps is not None
    )
    if not usable:
        return HistoricalTrafficBusiestBucket(
            "insufficient_data", None, None, None, None, 0
        )
    value = max(float(bucket.total_mbps) for bucket in usable)
    matches = tuple(bucket for bucket in usable if bucket.total_mbps == value)
    winner = matches[0]
    return HistoricalTrafficBusiestBucket(
        status="ok",
        bucket_start_utc=winner.bucket_start_utc,
        bucket_end_utc=winner.bucket_end_utc,
        average_total_mbps=value,
        selected_source=winner.selected_source,
        occurrence_count=len(matches),
    )


def _busiest_hour(
    samples: tuple[dict[str, Any], ...],
) -> HistoricalTrafficBusiestHour:
    window_seconds = 3600.0
    chains: list[list[tuple[float, float, float, str]]] = []
    current: list[tuple[float, float, float, str]] = []
    for sample in samples:
        if sample["interval_result"] != "accepted":
            if current:
                chains.append(current)
                current = []
            continue
        previous = sample["previous_at"]
        assert isinstance(previous, datetime)
        interval = (
            previous.timestamp(),
            sample["sample_at"].timestamp(),
            float(sample["total"]),
            str(sample["selected_source"]),
        )
        if current and (
            current[-1][1] != interval[0]
            or current[-1][3] != interval[3]
        ):
            chains.append(current)
            current = []
        current.append(interval)
    if current:
        chains.append(current)

    winner: tuple[float, float, str] | None = None
    for chain in chains:
        chain_start = chain[0][0]
        chain_end = chain[-1][1]
        if chain_end - chain_start < window_seconds:
            continue
        prefixes = [0.0]
        for item in chain:
            prefixes.append(prefixes[-1] + (item[1] - item[0]) * item[2])
        latest_start = chain_end - window_seconds
        start_candidate_index = 0
        shifted_candidate_index = 0
        start_area_index = 0
        end_area_index = 0
        prior_candidate: float | None = None

        def area(at: float, index: int) -> tuple[float, int]:
            while index + 1 < len(chain) and at > chain[index][1]:
                index += 1
            if at < chain[index][0] or at > chain[index][1]:
                raise HistoricalTrafficSourceUnavailable(
                    "Historical traffic Peak rolling interval is invalid"
                )
            return (
                prefixes[index] + (at - chain[index][0]) * chain[index][2],
                index,
            )

        while True:
            start_candidate = (
                chain[start_candidate_index][0]
                if start_candidate_index < len(chain)
                and chain[start_candidate_index][0] <= latest_start
                else None
            )
            while (
                shifted_candidate_index < len(chain)
                and chain[shifted_candidate_index][1] - window_seconds
                < chain_start
            ):
                shifted_candidate_index += 1
            shifted_candidate = (
                chain[shifted_candidate_index][1] - window_seconds
                if shifted_candidate_index < len(chain)
                and chain[shifted_candidate_index][1] - window_seconds
                <= latest_start
                else None
            )
            if start_candidate is None and shifted_candidate is None:
                break
            candidate = (
                shifted_candidate
                if start_candidate is None else
                start_candidate
                if shifted_candidate is None else
                min(start_candidate, shifted_candidate)
            )
            if start_candidate == candidate:
                start_candidate_index += 1
            if shifted_candidate == candidate:
                shifted_candidate_index += 1
            if candidate == prior_candidate:
                continue
            prior_candidate = candidate
            start_area, start_area_index = area(candidate, start_area_index)
            end_area, end_area_index = area(
                candidate + window_seconds,
                end_area_index,
            )
            average = (end_area - start_area) / window_seconds
            possible = (average, candidate, chain[0][3])
            if winner is None or average > winner[0] or (
                average == winner[0] and candidate < winner[1]
            ):
                winner = possible
    if winner is None:
        return HistoricalTrafficBusiestHour(
            "insufficient_data", None, None, 3600, None, None, None
        )
    average, window_start, source = winner
    start_at = datetime.fromtimestamp(window_start, UTC)
    return HistoricalTrafficBusiestHour(
        status="ok",
        window_start_utc=format_utc(start_at),
        window_end_utc=format_utc(start_at + timedelta(seconds=3600)),
        duration_seconds=3600,
        average_total_mbps=average,
        accepted_interval_seconds=3600.0,
        selected_source=source,
    )


def _empty_bucket(
    start: datetime,
    end: datetime,
    gap_threshold: float,
) -> HistoricalTrafficBucket:
    duration = (end - start).total_seconds()
    selection = HistoricalTrafficSourceSelection(
        primary_source="wired",
        selected_source=None,
        selection_reason="no_canonical_samples",
        wired_complete_site_cycle_count=0,
        lan_complete_site_cycle_count=0,
        wired_pair_valid_ap_opportunities=0,
        lan_pair_valid_ap_opportunities=0,
    )
    return HistoricalTrafficBucket(
        bucket_start_utc=format_utc(start), bucket_end_utc=format_utc(end),
        download_mbps=None, upload_mbps=None, total_mbps=None, status="none",
        selected_source=None, selection_reason="no_canonical_samples",
        source_changed_from_previous=False, canonical_cycle_count=0,
        complete_site_sample_count=0, excluded_site_sample_count=0,
        total_ap_opportunities=0, selected_pair_valid_ap_opportunities=0,
        first_complete_sample_at=None, last_complete_sample_at=None,
        leading_gap_seconds=duration, trailing_gap_seconds=duration,
        max_inter_sample_gap_seconds=0.0,
        gap_count_over_threshold=1 if duration > gap_threshold else 0,
        selected_source_skew_excluded_sample_count=0,
        rate_reason_counts={reason: 0 for reason in _BUCKET_REASONS},
        source_selection=selection,
    )


def _bucket_size(duration_seconds: float, requested: int | None) -> int:
    if requested is not None:
        if type(requested) is not int or requested <= 0:
            raise HistoricalTrafficValidationError(
                "bucket_seconds must be a positive integer"
            )
        if math.ceil(duration_seconds / requested) > MAX_SITE_HISTORY_BUCKETS:
            raise HistoricalTrafficValidationError("bucket count exceeds 720")
        return requested
    for candidate in _AUTO_BUCKET_SECONDS:
        if math.ceil(duration_seconds / candidate) <= MAX_SITE_HISTORY_BUCKETS:
            return candidate
    required = math.ceil(duration_seconds / MAX_SITE_HISTORY_BUCKETS)
    return math.ceil(required / 86400) * 86400


def _optional_utc(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return format_utc(parse_utc(str(value), "source timestamp"))
    except AnalyticsQueryValidationError as exc:
        raise HistoricalTrafficSourceUnavailable(
            "Historical traffic source timestamp is invalid"
        ) from exc


def _display_name(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise HistoricalTrafficSourceUnavailable(
            "Historical AP display name is invalid"
        )
    result = value.strip()
    if not result:
        return None
    if len(result) > 256 or any(ord(character) < 32 for character in result):
        raise HistoricalTrafficSourceUnavailable(
            "Historical AP display name is invalid"
        )
    return result


def _unavailable_now() -> HistoricalTrafficApNow:
    return HistoricalTrafficApNow(
        status="unavailable",
        download_mbps=None,
        upload_mbps=None,
        total_mbps=None,
        download_reason="source_unavailable",
        upload_reason="source_unavailable",
        observed_at=None,
        age_seconds=None,
        selected_source=None,
    )


def _integer(value: Any) -> int:
    if type(value) is not int or value < 0:
        raise HistoricalTrafficSourceUnavailable(
            "Historical traffic aggregate is invalid"
        )
    return value


def _finite_nonnegative(value: Any) -> float:
    if type(value) not in {int, float} or not math.isfinite(float(value)) or value < 0:
        raise HistoricalTrafficSourceUnavailable(
            "Historical traffic aggregate is invalid"
        )
    return float(value)


def _positive_finite(value: Any) -> bool:
    return type(value) in {int, float} and math.isfinite(float(value)) and value > 0
