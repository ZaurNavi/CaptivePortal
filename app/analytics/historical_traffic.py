"""Bounded Site-scoped history derived from persisted AP rate facts."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from .models import (
    HistoricalSiteTraffic,
    HistoricalTrafficBucket,
    HistoricalTrafficCoverage,
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
_AUTO_BUCKET_SECONDS = (300, 900, 3600, 21600, 86400, 604800, 2592000)
_QUALITY_REASONS = (
    "no_baseline", "counter_reset", "gap_too_large",
    "invalid_elapsed", "source_unavailable",
)
_BUCKET_REASONS = ("ok", *_QUALITY_REASONS)


class HistoricalTrafficValidationError(ValueError):
    """Caller input violates the Historical Traffic read contract."""


class HistoricalTrafficSourceUnavailable(RuntimeError):
    """Persisted facts cannot safely satisfy Historical Traffic."""


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
    ) -> HistoricalSiteTraffic:
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
        return HistoricalSiteTraffic(
            status=(
                "insufficient_data" if coverage_status == "none" else
                "ok" if coverage_status == "complete" else "partial"
            ),
            range=traffic_range,
            buckets=tuple(buckets),
            coverage=coverage,
            quality=quality,
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
