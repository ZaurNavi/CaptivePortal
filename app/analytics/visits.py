"""Site-scoped Visit Analytics over persisted, read-only source facts."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import AnalyticsConfig
from .formulas import (
    configured_threshold_ratio, coverage, distribution_from_values,
    join_coverage, numeric_distribution, observation_coverage,
    pearson_from_sums,
)
from .models import (
    AnalyticsProvenance, AnalyticsQuality, AnalyticsResult,
    DeviceCountSummary, NewToSiteDeviceSummary, RepeatDeviceSummary,
    ReturnIntervalSummary, VisitAnalyticsBundle, VisitAuthorizationSummary,
    VisitClosureSummary, VisitContextDistribution,
    VisitContextDistributionItem, VisitContextSummary,
    VisitContextTransition, VisitCountSummary, VisitDurationSummary,
    VisitObservationCoverageSummary, VisitSourceEventQuality,
    VisitTimeBucket, VisitTimeSeries, VisitTrafficSummary,
    VisitWirelessSummary, SignalApCorrelation, SignalDistribution,
)
from .source_gateway import (
    AnalyticsPerformanceBudgetExceeded, AnalyticsQueryDeadlineExceeded,
    AnalyticsSourceGateway, AnalyticsSourceUnavailable, QueryDeadline,
    SOURCE_SCHEMA_VERSIONS,
)
from .telemetry import AnalyticsTelemetry
from .validation import (
    AnalyticsQueryValidationError, format_utc, parse_utc, require_site,
)


UTC = timezone.utc
QUALITY_MODE = "strict_complete"
_METRIC_VERSION = "visit-analytics.v1"
_START_COHORT = "visit_start_cohort:[from_utc,to_utc)"


class VisitAnalyticsService:
    """Compose Visit metrics without polling, identifiers lists, or writes."""

    def __init__(
        self,
        config: AnalyticsConfig,
        gateway: AnalyticsSourceGateway,
        *,
        telemetry: AnalyticsTelemetry | None = None,
        clock: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        self.config = config
        self.gateway = gateway
        self.telemetry = telemetry or AnalyticsTelemetry()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._monotonic = monotonic

    def get_visit_counts(self, site_id: str, from_utc: str, to_utc: str):
        site, start, end, _, _ = self._query(site_id, from_utc, to_utc)
        return self._execute(
            site, start, end, "visit.counts.v1", ("visits",),
            lambda deadline, _evaluation: self.gateway.visit_cohort_summary(
                site_id=site, from_utc=start, to_utc=end, deadline=deadline),
            lambda raw: (
                VisitCountSummary(
                    int(raw["total_visit_count"]),
                    int(raw["open_visit_count"]),
                    int(raw["closed_visit_count"]),
                ),
                "ok", None,
                self._meta(raw, sample=int(raw["total_visit_count"])),
            ),
            {"population_semantics": _START_COHORT},
        )

    def get_visit_time_series(
        self, site_id: str, from_utc: str, to_utc: str,
        granularity: str, *, display_timezone: str = "UTC",
    ):
        site, start, end, start_dt, end_dt = self._query(
            site_id, from_utc, to_utc)
        if granularity not in {"hour", "day", "week"}:
            raise AnalyticsQueryValidationError("granularity is invalid")
        if granularity == "hour" and end_dt-start_dt > timedelta(days=7):
            raise AnalyticsQueryValidationError(
                "hour Visit series window exceeds 7 days")
        try:
            zone = ZoneInfo(display_timezone)
        except (ZoneInfoNotFoundError, ValueError, TypeError) as exc:
            raise AnalyticsQueryValidationError(
                "display_timezone must be a valid IANA timezone") from exc
        return self._execute(
            site, start, end, "visit.time_series.v1", ("visits",),
            lambda deadline, _evaluation: self.gateway.visit_start_timestamps(
                site_id=site, from_utc=start, to_utc=end, deadline=deadline),
            lambda raw: self._time_series_value(
                raw, start_dt, end_dt, granularity, zone,
                display_timezone),
            {"population_semantics": _START_COHORT,
             "granularity": granularity,
             "display_timezone": display_timezone},
        )

    def get_device_counts(self, site_id: str, from_utc: str, to_utc: str):
        return self._device_result(site_id, from_utc, to_utc, "counts")

    def get_repeat_devices(self, site_id: str, from_utc: str, to_utc: str):
        return self._device_result(site_id, from_utc, to_utc, "repeat")

    def _device_result(
        self, site_id: str, from_utc: str, to_utc: str, mode: str,
    ):
        site, start, end, _, _ = self._query(site_id, from_utc, to_utc)
        metric = "visit.devices.v1" if mode == "counts" else "visit.repeat.v1"

        def build(raw: Mapping[str, Any]):
            unique = int(raw["unique_linked_devices"])
            if mode == "counts":
                value = DeviceCountSummary(
                    unique, int(raw["linked_visit_count"]),
                    int(raw["unlinked_visit_count"]))
                status, reason = "ok", None
            else:
                repeats = int(raw["repeat_device_count"])
                value = RepeatDeviceSummary(
                    unique, repeats, None if not unique else repeats/unique)
                status = "ok" if unique else "insufficient_data"
                reason = None if unique else "zero_denominator"
            return value, status, reason, self._meta(
                raw, examined=int(raw["rows_examined"]),
                accepted=int(raw["linked_visit_count"]),
                rejected=int(raw["unlinked_visit_count"]), sample=unique,
                missing=int(raw["unlinked_visit_count"]))

        return self._execute(
            site, start, end, metric, ("visits",),
            lambda deadline, _evaluation: self.gateway.visit_device_summary(
                site_id=site, from_utc=start, to_utc=end, deadline=deadline),
            build, {"population_semantics": _START_COHORT})

    def get_new_to_site_devices(
        self, site_id: str, from_utc: str, to_utc: str,
    ):
        site, start, end, _, _ = self._query(site_id, from_utc, to_utc)

        def build(raw: Mapping[str, Any]):
            linked = int(raw["unique_linked_devices_in_window"])
            unlinked = int(raw["unlinked_visit_count"])
            value = NewToSiteDeviceSummary(
                linked, int(raw["new_to_site_device_count"]),
                int(raw["known_before_window_device_count"]), unlinked)
            return value, "ok", None, self._meta(
                raw, examined=int(raw["rows_examined"]),
                accepted=linked, rejected=unlinked, sample=linked,
                missing=unlinked)

        return self._execute(
            site, start, end, "visit.new_to_site.v1", ("visits",),
            lambda deadline, _evaluation:
                self.gateway.visit_new_to_site_summary(
                    site_id=site, from_utc=start, to_utc=end,
                    deadline=deadline),
            build, {"population_semantics": _START_COHORT,
                    "identity_basis": "same_site_device_id_visit_history"})

    def get_duration_distribution(
        self, site_id: str, from_utc: str, to_utc: str,
    ):
        site, start, end, _, _ = self._query(site_id, from_utc, to_utc)
        return self._execute_distribution(
            site, start, end, "visit.duration.v1",
            lambda deadline: self.gateway.visit_duration_distribution(
                site_id=site, from_utc=start, to_utc=end, deadline=deadline),
            lambda raw, dist: VisitDurationSummary(
                dist, int(raw["excluded_open_count"]),
                int(raw["excluded_missing_duration_count"])),
            min_samples=1)

    def get_authorization_distribution(
        self, site_id: str, from_utc: str, to_utc: str,
    ):
        site, start, end, _, _ = self._query(site_id, from_utc, to_utc)
        return self._execute_distribution(
            site, start, end, "visit.authorizations.v1",
            lambda deadline: self.gateway.visit_authorization_distribution(
                site_id=site, from_utc=start, to_utc=end, deadline=deadline),
            lambda raw, dist: VisitAuthorizationSummary(
                dist, int(raw["exactly_one"]), int(raw["multiple"]),
                int(raw["zero"])), min_samples=1)

    def get_closure_distribution(
        self, site_id: str, from_utc: str, to_utc: str,
    ):
        site, start, end, _, _ = self._query(site_id, from_utc, to_utc)

        def build(raw: Mapping[str, Any]):
            difference = numeric_distribution(
                raw["duration_difference"], min_samples=1)
            count = int(raw["closed_visit_count"])
            value = VisitClosureSummary(
                count, raw["close_reasons"], raw["close_time_sources"],
                difference)
            status = "ok" if count else "insufficient_data"
            return value, status, None if count else "insufficient_samples", \
                self._meta(raw["duration_difference"], sample=count)

        return self._execute(
            site, start, end, "visit.closure.v1", ("visits",),
            lambda deadline, _evaluation: self.gateway.visit_closure_summary(
                site_id=site, from_utc=start, to_utc=end, deadline=deadline),
            build, {"population_semantics": _START_COHORT,
                    "duration_sources_separate": True})

    def get_source_event_quality(
        self, site_id: str, from_utc: str, to_utc: str,
    ):
        site, start, end, _, _ = self._query(site_id, from_utc, to_utc)

        def build(payload: Mapping[str, Any]):
            raw = payload["quality"]
            by_result = {name: int(raw["by_processing_result"].get(name, 0))
                         for name in ("closed", "unmatched", "invalid",
                                      "pending_match")}
            total = sum(by_result.values())
            value = VisitSourceEventQuality(by_result, raw["by_reason"])
            return value, "ok", None, {
                "rows_examined": total, "rows_accepted": total,
                "rows_rejected": 0, "sample_size": total,
                "missing_count": 0,
                "watermarks": {"visits": payload["watermark"]}}

        return self._execute(
            site, start, end, "visit.source_event_quality.v1", ("visits",),
            lambda deadline, _evaluation: {
                "quality": self.gateway.source_event_quality(
                    site_id=site, from_utc=start, to_utc=end,
                    deadline=deadline),
                "watermark": self.gateway.source_event_watermark(
                    site_id=site, from_utc=start, to_utc=end,
                    deadline=deadline)},
            build, {"site_null_events_excluded": True,
                    "time_basis": "processed_at"})

    def get_context_distributions(
        self, site_id: str, from_utc: str, to_utc: str,
    ):
        site, start, end, _, _ = self._query(site_id, from_utc, to_utc)
        dimensions = (
            "start_ssid", "final_ssid", "start_ap_mac", "final_ap_mac",
            "touched_ssid", "touched_ap_mac")

        def load(deadline: QueryDeadline, _evaluation: str):
            return {name: self.gateway.visit_context_distribution(
                site_id=site, from_utc=start, to_utc=end, dimension=name,
                deadline=deadline) for name in dimensions}

        def item(name: str, raw: Mapping[str, Any]):
            rows = raw["rows"]
            nulls = sum(int(row["visit_count"]) for row in rows
                        if row["context"] is None)
            return VisitContextDistribution(
                name, tuple(VisitContextDistributionItem(
                    row["context"], int(row["visit_count"]))
                    for row in rows if row["context"] is not None),
                nulls, name.startswith("touched_"))

        def build(raw: Mapping[str, Mapping[str, Any]]):
            value = VisitContextSummary(*(item(name, raw[name])
                                          for name in dimensions))
            examined = int(raw["start_ssid"]["rows_examined"])
            watermark = raw["start_ssid"]["watermark"]
            return value, "ok", None, {
                "rows_examined": examined, "rows_accepted": examined,
                "rows_rejected": 0, "sample_size": examined,
                "missing_count": 0, "watermarks": {"visits": watermark}}

        return self._execute(
            site, start, end, "visit.contexts.v1", ("visits",), load,
            build, {"population_semantics": _START_COHORT,
                    "touched_grouping_is_non_exclusive": True})

    def get_context_transition(
        self, site_id: str, from_utc: str, to_utc: str,
    ):
        site, start, end, _, _ = self._query(site_id, from_utc, to_utc)

        def build(raw: Mapping[str, Any]):
            values = (
                VisitContextTransition(
                    "ssid", int(raw["ssid_comparable"]),
                    int(raw["ssid_changed"]), int(raw["ssid_unchanged"]),
                    int(raw["ssid_missing"]),
                    "context transition; not automatically a fault"),
                VisitContextTransition(
                    "ap_mac", int(raw["ap_comparable"]),
                    int(raw["ap_changed"]), int(raw["ap_unchanged"]),
                    int(raw["ap_missing"]),
                    "AP change may represent roaming; not a fault label"),
            )
            n = int(raw["rows_examined"])
            return values, "ok", None, self._meta(raw, examined=n,
                                                   accepted=n, sample=n)

        return self._execute(
            site, start, end, "visit.context_transition.v1", ("visits",),
            lambda deadline, _evaluation:
                self.gateway.visit_context_transitions(
                    site_id=site, from_utc=start, to_utc=end,
                    deadline=deadline),
            build, {"population_semantics": _START_COHORT})

    def get_observation_coverage_summary(
        self, site_id: str, from_utc: str, to_utc: str,
    ):
        site, start, end, _, _ = self._query(site_id, from_utc, to_utc)

        def load(deadline: QueryDeadline, evaluation: str):
            windows = self.gateway.visit_windows(
                site_id=site, from_utc=start, to_utc=end,
                evaluation_at_utc=evaluation, deadline=deadline)
            raw = self.gateway.visit_observation_coverage_batch(
                site_id=site, windows=windows,
                gap_threshold_seconds=self.config.quality_gap_threshold_seconds,
                deadline=deadline)
            return {"windows": windows, "coverage": raw}

        def build(raw: Mapping[str, Any]):
            by_id = {str(row["visit_id"]): row
                     for row in raw["coverage"]["rows"]}
            values = []
            for window in raw["windows"]:
                row = by_id.get(str(window["visit_id"]), {})
                values.append(self._coverage_value(window, row))
            zero = sum(value.sample_count == 0 for value in values)
            summary = VisitObservationCoverageSummary(
                len(values), zero, len(values)-zero,
                distribution_from_values(
                    (value.sample_count for value in values), min_samples=1),
                distribution_from_values(
                    (value.observed_span_ratio for value in values),
                    min_samples=1),
                distribution_from_values(
                    (value.max_inter_sample_gap_seconds for value in values),
                    min_samples=1),
            )
            coverage_raw = raw["coverage"]
            return summary, "ok", None, {
                "rows_examined": int(coverage_raw["rows_examined"]),
                "rows_accepted": int(coverage_raw["rows_accepted"]),
                "rows_rejected": 0, "sample_size": len(values),
                "missing_count": zero,
                "watermarks": {"visits": max(
                    (str(w["started_at"]) for w in raw["windows"]),
                    default=None),
                    "observations": coverage_raw["watermark"]}}

        return self._execute(
            site, start, end, "visit.observation_coverage.v1",
            ("visits", "observations"), load, build,
            {"population_semantics": _START_COHORT,
             "composition": "bounded_set_based"})

    def get_visit_wireless_summary(
        self, site_id: str, visit_id: str,
    ) -> AnalyticsResult[VisitWirelessSummary]:
        site = require_site(site_id)
        if not isinstance(visit_id, str) or not visit_id.strip():
            raise AnalyticsQueryValidationError("visit_id must be non-empty")
        started = self._monotonic()
        evaluation = self._now()
        deadline = self._deadline()
        try:
            self._require_enabled()
            if not self.config.wireless_enabled:
                raise AnalyticsSourceUnavailable(
                    "Wireless Analytics is disabled")
            visit = self.gateway.visit_by_id(
                site_id=site, visit_id=visit_id, deadline=deadline)
            if visit is None:
                raise AnalyticsSourceUnavailable("Visit is unavailable")
            start = str(visit["started_at"])
            end = str(visit["closed_at"] or evaluation)
            if parse_utc(end, "visit end") <= parse_utc(start, "visit start"):
                end = format_utc(
                    parse_utc(start, "visit start") + timedelta(milliseconds=1))
            if parse_utc(end, "visit end")-parse_utc(
                start, "visit start") > timedelta(
                    days=self.config.wireless_max_window_days):
                raise AnalyticsPerformanceBudgetExceeded(
                    "Visit wireless window exceeds configured maximum")
            coverage_raw = self.gateway.observation_coverage(
                site_id=site, client_mac=str(visit["client_mac"]),
                from_utc=start, to_utc=end,
                gap_threshold_seconds=self.config.quality_gap_threshold_seconds,
                deadline=deadline)
            coverage_value = self._coverage_value(
                {"started_at": start, "evaluation_end": end,
                 "closed_at": visit["closed_at"]}, coverage_raw)
            client_mac = str(visit["client_mac"])
            signals = {metric: self._visit_signal_result(
                site, start, end, evaluation, metric, client_mac, deadline)
                for metric in ("rssi", "snr")}
            correlations = {
                f"{signal}:{target}": self._visit_correlation_result(
                    site, start, end, evaluation, signal, target,
                    client_mac, deadline)
                for signal in ("rssi", "snr")
                for target in ("busy_util", "cpu_util")
            }
        except (AnalyticsSourceUnavailable, AnalyticsQueryDeadlineExceeded,
                AnalyticsPerformanceBudgetExceeded) as exc:
            reason = self._failure_reason(exc)
            return self._result(
                status="unavailable", reason=reason, value=None, site=site,
                start=evaluation, end=evaluation, evaluation=evaluation,
                started=started, metric="visit.wireless.v1",
                sources=("visits", "observations"), watermarks={},
                filters={"visit_detail": True})
        value = VisitWirelessSummary(
            visit_id, coverage_value, signals, correlations)
        samples = coverage_value.sample_count
        return self._result(
            status="ok" if samples else "insufficient_data",
            reason=None if samples else "insufficient_samples", value=value,
            site=site, start=start, end=end, evaluation=evaluation,
            started=started, metric="visit.wireless.v1",
            sources=("visits", "observations"),
            watermarks={"visits": start,
                        "observations": coverage_raw["last_observed_at"]},
            examined=samples, accepted=samples, sample=samples,
            filters={"visit_detail": True, "population_semantics":
                     "single_persisted_visit_interval"})

    def get_visit_traffic_summary(
        self, site_id: str, from_utc: str, to_utc: str,
    ):
        site, start, end, _, _ = self._query(site_id, from_utc, to_utc)

        def load(deadline: QueryDeadline, evaluation: str):
            windows = self.gateway.visit_windows(
                site_id=site, from_utc=start, to_utc=end,
                evaluation_at_utc=evaluation, deadline=deadline)
            observed = self.gateway.visit_observed_traffic_batch(
                site_id=site, windows=windows,
                max_gap_seconds=self.config.counter_max_gap_seconds,
                deadline=deadline)
            return {"windows": windows, "observed": observed}

        def build(raw: Mapping[str, Any]):
            windows = raw["windows"]
            observed = raw["observed"]
            rows = observed["rows"]
            reported_total = self._sum_present(
                windows, "reported_traffic_total_bytes")
            reported_up = self._sum_present(
                windows, "reported_traffic_up_bytes")
            reported_down = self._sum_present(
                windows, "reported_traffic_down_bytes")
            observed_down = self._sum_present(rows, "down_delta")
            observed_up = self._sum_present(rows, "up_delta")
            observed_total = None if observed_down is None or observed_up is None \
                else observed_down + observed_up
            valid_visits = sum(int(row["valid_interval_count"]) > 0
                               for row in rows)
            difference = None
            ratio = None
            if observed_total is not None and reported_total is not None:
                difference = observed_total-reported_total
                if reported_total > 0:
                    ratio = difference/reported_total
            value = VisitTrafficSummary(
                reported_total, reported_up, reported_down,
                sum(w["reported_traffic_total_bytes"] is None for w in windows),
                sum(w["reported_traffic_up_bytes"] is None for w in windows),
                sum(w["reported_traffic_down_bytes"] is None for w in windows),
                observed_down, observed_up, coverage(valid_visits, len(windows)),
                difference, ratio)
            return value, "ok", None, {
                "rows_examined": int(observed["rows_examined"]),
                "rows_accepted": int(observed["rows_accepted"]),
                "rows_rejected": int(observed["rows_rejected"]),
                "sample_size": len(windows),
                "missing_count": len(windows)-valid_visits,
                "watermarks": {"visits": max(
                    (str(w["started_at"]) for w in windows), default=None),
                    "observations": observed["watermark"]}}

        return self._execute(
            site, start, end, "visit.traffic.v1",
            ("visits", "observations"), load, build,
            {"population_semantics": _START_COHORT,
             "reported_and_observed_sources_separate": True})

    def get_return_intervals(
        self, site_id: str, from_utc: str, to_utc: str,
    ):
        site, start, end, _, _ = self._query(site_id, from_utc, to_utc)
        return self._execute_distribution(
            site, start, end, "visit.return_intervals.v1",
            lambda deadline: self.gateway.visit_return_intervals(
                site_id=site, from_utc=start, to_utc=end, deadline=deadline),
            lambda _raw, dist: ReturnIntervalSummary(dist),
            min_samples=self.config.visit_min_cohort_size)

    def get_visit_analytics_bundle(
        self, site_id: str, from_utc: str, to_utc: str,
    ) -> VisitAnalyticsBundle:
        return VisitAnalyticsBundle(
            counts=self.get_visit_counts(site_id, from_utc, to_utc),
            devices=self.get_device_counts(site_id, from_utc, to_utc),
            repeat_devices=self.get_repeat_devices(site_id, from_utc, to_utc),
            new_to_site_devices=self.get_new_to_site_devices(
                site_id, from_utc, to_utc),
            duration=self.get_duration_distribution(site_id, from_utc, to_utc),
            authorizations=self.get_authorization_distribution(
                site_id, from_utc, to_utc),
            closure=self.get_closure_distribution(site_id, from_utc, to_utc),
            source_event_quality=self.get_source_event_quality(
                site_id, from_utc, to_utc),
            contexts=self.get_context_distributions(site_id, from_utc, to_utc),
            context_transitions=self.get_context_transition(
                site_id, from_utc, to_utc),
            observation_coverage=self.get_observation_coverage_summary(
                site_id, from_utc, to_utc),
            traffic=self.get_visit_traffic_summary(site_id, from_utc, to_utc),
            return_intervals=self.get_return_intervals(
                site_id, from_utc, to_utc),
        )

    def _execute_distribution(
        self, site: str, start: str, end: str, metric: str,
        loader: Callable[[QueryDeadline], Mapping[str, Any]],
        factory: Callable[[Mapping[str, Any], Any], Any], *, min_samples: int,
    ):
        def build(raw: Mapping[str, Any]):
            dist = numeric_distribution(raw, min_samples=min_samples)
            status = "ok" if dist.sample_count >= min_samples \
                else "insufficient_data"
            return factory(raw, dist), status, (
                None if status == "ok" else "insufficient_samples"), \
                self._meta(raw, sample=dist.sample_count,
                           missing=dist.missing_count)
        return self._execute(
            site, start, end, metric, ("visits",),
            lambda deadline, _evaluation: loader(deadline), build,
            {"population_semantics": _START_COHORT})

    def _visit_signal_result(
        self, site: str, start: str, end: str, evaluation: str,
        metric: str, client_mac: str, deadline: QueryDeadline,
    ) -> AnalyticsResult[Any]:
        started = self._monotonic()
        configured = (self.config.rssi_threshold_dbm if metric == "rssi"
                      else self.config.snr_threshold_db)
        raw = self.gateway.wireless_scalar_distribution(
            site_id=site, source="client", metric=metric,
            from_utc=start, to_utc=end, quality_mode=QUALITY_MODE,
            filters={"client_mac": client_mac}, threshold=configured,
            deadline=deadline)
        distribution = numeric_distribution(
            raw, min_samples=self.config.wireless_min_samples)
        value = SignalDistribution(
            metric, distribution,
            configured_threshold_ratio(
                threshold=configured, sample_count=distribution.sample_count,
                below_count=raw.get("below_threshold_count")))
        sufficient = distribution.sample_count >= self.config.wireless_min_samples
        return self._result(
            status="ok" if sufficient else "insufficient_data",
            reason=None if sufficient else "insufficient_samples",
            value=value, site=site, start=start, end=end,
            evaluation=evaluation, started=started,
            metric=f"visit.wireless.signal.{metric}.v1",
            sources=("observations",),
            watermarks={"observations": raw.get("watermark")},
            examined=int(raw.get("rows_examined") or 0),
            accepted=int(raw.get("rows_accepted") or 0),
            rejected=int(raw.get("rows_rejected") or 0),
            sample=distribution.sample_count,
            missing=distribution.missing_count,
            filters={"single_visit_client_filter": True})

    def _visit_correlation_result(
        self, site: str, start: str, end: str, evaluation: str,
        signal: str, target: str, client_mac: str, deadline: QueryDeadline,
    ) -> AnalyticsResult[Any]:
        started = self._monotonic()
        raw = self.gateway.signal_ap_correlation(
            site_id=site, signal_metric=signal, ap_metric=target,
            from_utc=start, to_utc=end, quality_mode=QUALITY_MODE,
            max_lag_seconds=self.config.ap_join_max_lag_seconds,
            deadline=deadline, client_mac=client_mac)
        count = int(raw["sample_count"])
        coefficient = pearson_from_sums(
            sample_count=count, sum_x=float(raw["sum_x"]),
            sum_y=float(raw["sum_y"]), sum_xx=float(raw["sum_xx"]),
            sum_yy=float(raw["sum_yy"]), sum_xy=float(raw["sum_xy"]),
            min_samples=self.config.wireless_min_samples)
        value = SignalApCorrelation(
            signal, target, count, coefficient, join_coverage(raw))
        sufficient = coefficient is not None
        clients = int(raw["client_sample_count"])
        return self._result(
            status="ok" if sufficient else "insufficient_data",
            reason=None if sufficient else "insufficient_samples_or_variance",
            value=value, site=site, start=start, end=end,
            evaluation=evaluation, started=started,
            metric="visit.wireless.correlation.v1",
            sources=("observations",),
            watermarks={"observations": raw.get("watermark")},
            examined=clients, accepted=count, rejected=max(clients-count, 0),
            sample=count, missing=max(clients-count, 0),
            filters={"signal_metric": signal, "ap_metric": target,
                     "single_visit_client_filter": True,
                     "join_max_lag_seconds":
                         self.config.ap_join_max_lag_seconds})

    def _execute(
        self, site: str, start: str, end: str, metric: str,
        sources: tuple[str, ...],
        loader: Callable[[QueryDeadline, str], Mapping[str, Any]],
        builder: Callable[[Mapping[str, Any]], tuple[Any, str, str | None,
                                                      Mapping[str, Any]]],
        filters: Mapping[str, Any],
    ):
        started = self._monotonic()
        evaluation = self._now()
        try:
            self._require_enabled()
            raw = loader(self._deadline(), evaluation)
            value, status, reason, meta = builder(raw)
        except (AnalyticsSourceUnavailable, AnalyticsQueryDeadlineExceeded,
                AnalyticsPerformanceBudgetExceeded) as exc:
            return self._result(
                status="unavailable", reason=self._failure_reason(exc),
                value=None, site=site, start=start, end=end,
                evaluation=evaluation, started=started, metric=metric,
                sources=sources, watermarks={}, filters=filters)
        return self._result(
            status=status, reason=reason, value=value, site=site,
            start=start, end=end, evaluation=evaluation, started=started,
            metric=metric, sources=sources,
            watermarks=meta.get("watermarks", {}),
            examined=int(meta.get("rows_examined", 0)),
            accepted=int(meta.get("rows_accepted", 0)),
            rejected=int(meta.get("rows_rejected", 0)),
            sample=int(meta.get("sample_size", 0)),
            missing=int(meta.get("missing_count", 0)), filters=filters)

    def _result(
        self, *, status: str, reason: str | None, value: Any, site: str,
        start: str, end: str, evaluation: str, started: float, metric: str,
        sources: tuple[str, ...], watermarks: Mapping[str, str | None],
        filters: Mapping[str, Any], examined: int = 0, accepted: int = 0,
        rejected: int = 0, sample: int = 0, missing: int = 0,
    ) -> AnalyticsResult[Any]:
        duration = max(0.0, (self._monotonic()-started)*1000)
        normalized_watermarks = {source: watermarks.get(source)
                                 for source in sources}
        result = AnalyticsResult(
            status=status, value=value,
            quality=AnalyticsQuality(
                quality_mode=QUALITY_MODE, reason=reason,
                accepted_rows=accepted, rejected_rows=rejected,
                missing_count=missing),
            provenance=AnalyticsProvenance(
                site_id=site, from_utc=start, to_utc=end,
                evaluation_at_utc=evaluation, computed_at_utc=self._now(),
                quality_mode=QUALITY_MODE, source_names=sources,
                source_schema_versions={source: SOURCE_SCHEMA_VERSIONS[source]
                                        for source in sources},
                source_watermarks=normalized_watermarks,
                source_rows_examined=examined,
                source_rows_accepted=accepted,
                source_rows_rejected=rejected, sample_size=sample,
                missing_count=missing, partial_cycle_count=0,
                failed_cycle_count=0, abandoned_cycle_count=0,
                filters=filters, metric_version=metric,
                query_duration_ms=duration))
        event = {
            "unavailable": "analytics.visit_query_unavailable",
            "insufficient_data": "analytics.visit_insufficient_data",
        }.get(status, "analytics.visit_query_completed")
        self.telemetry.emit(
            event, metric=metric, site_id=site,
            duration_ms=round(duration, 3), sample_size=sample,
            accepted_rows=accepted, rejected_rows=rejected,
            status=status, reason=reason, quality_mode=QUALITY_MODE)
        return result

    def _query(
        self, site_id: str, from_utc: str, to_utc: str,
    ) -> tuple[str, str, str, datetime, datetime]:
        site = require_site(site_id)
        start_dt = parse_utc(from_utc, "from_utc")
        end_dt = parse_utc(to_utc, "to_utc")
        if start_dt >= end_dt:
            raise AnalyticsQueryValidationError(
                "from_utc must be before to_utc")
        if end_dt-start_dt > timedelta(days=self.config.visit_max_window_days):
            raise AnalyticsQueryValidationError(
                "Visit query window exceeds configured maximum")
        return site, from_utc, to_utc, start_dt, end_dt

    def _require_enabled(self) -> None:
        if not self.config.enabled:
            raise AnalyticsSourceUnavailable("Analytics is disabled")
        if not self.config.visit_enabled:
            raise AnalyticsSourceUnavailable("Visit Analytics is disabled")

    def _deadline(self) -> QueryDeadline:
        return QueryDeadline.after(
            self.config.max_query_duration_seconds,
            monotonic=self._monotonic)

    def _now(self) -> str:
        value = self._clock()
        if not isinstance(value, datetime):
            raise RuntimeError("Analytics clock must return datetime")
        return format_utc(value)

    @staticmethod
    def _failure_reason(exc: Exception) -> str:
        if isinstance(exc, AnalyticsQueryDeadlineExceeded):
            return "query_deadline"
        if isinstance(exc, AnalyticsPerformanceBudgetExceeded):
            return "performance_budget_exceeded"
        if "disabled" in str(exc).lower():
            return "disabled"
        return "source_unavailable"

    @staticmethod
    def _meta(
        raw: Mapping[str, Any], *, examined: int | None = None,
        accepted: int | None = None, rejected: int | None = None,
        sample: int | None = None, missing: int | None = None,
    ) -> Mapping[str, Any]:
        return {
            "rows_examined": int(raw.get("rows_examined", 0)
                                 if examined is None else examined),
            "rows_accepted": int(raw.get("rows_accepted", 0)
                                 if accepted is None else accepted),
            "rows_rejected": int(raw.get("rows_rejected", 0)
                                 if rejected is None else rejected),
            "sample_size": int(raw.get("sample_count", 0)
                               if sample is None else sample),
            "missing_count": int(raw.get("missing_count", 0)
                                  if missing is None else missing),
            "watermarks": {"visits": raw.get("watermark")},
        }

    def _coverage_value(
        self, window: Mapping[str, Any], raw: Mapping[str, Any],
    ):
        started = parse_utc(str(window["started_at"]), "started_at")
        ended = parse_utc(str(window["evaluation_end"]), "evaluation_end")
        closed = window.get("closed_at") is not None
        duration = int((ended-started).total_seconds()) if ended > started \
            else None
        return observation_coverage(
            started_at=started, ended_at=ended,
            sample_count=int(raw.get("sample_count") or 0),
            first_observed_at=(None if raw.get("first_observed_at") is None
                               else parse_utc(str(raw["first_observed_at"]),
                                              "first_observed_at")),
            last_observed_at=(None if raw.get("last_observed_at") is None
                              else parse_utc(str(raw["last_observed_at"]),
                                             "last_observed_at")),
            max_gap_seconds=(None if raw.get("max_gap_seconds") is None
                             else float(raw["max_gap_seconds"])),
            gap_count_over_threshold=int(
                raw.get("gap_count_over_threshold") or 0),
            gap_threshold_seconds=self.config.quality_gap_threshold_seconds,
            visit_duration_seconds=duration, provisional=not closed)

    def _time_series_value(
        self, raw: Mapping[str, Any], start: datetime, end: datetime,
        granularity: str, zone: ZoneInfo, display_timezone: str,
    ):
        counts: dict[str, int] = {}
        for row in raw["rows"]:
            instant = parse_utc(str(row["started_at"]), "started_at")
            key = self._bucket_start(instant, granularity, zone)
            key_text = key.isoformat(timespec="milliseconds")
            counts[key_text] = counts.get(key_text, 0)+1
        items = []
        if granularity == "hour":
            current_utc = self._bucket_start(
                start, "hour", zone
            ).astimezone(UTC)
            while current_utc < end:
                following_utc = current_utc+timedelta(hours=1)
                current = current_utc.astimezone(zone)
                following = following_utc.astimezone(zone)
                key_text = current.isoformat(timespec="milliseconds")
                items.append(VisitTimeBucket(
                    key_text, following.isoformat(timespec="milliseconds"),
                    counts.get(key_text, 0)))
                current_utc = following_utc
            value = VisitTimeSeries(
                granularity, display_timezone, _START_COHORT, tuple(items))
            sample = sum(item.count for item in items)
            return value, "ok", None, {
                "rows_examined": sample, "rows_accepted": sample,
                "rows_rejected": 0, "sample_size": sample,
                "missing_count": 0,
                "watermarks": {"visits": raw["watermark"]}}
        current = self._bucket_start(start, granularity, zone)
        end_local = end.astimezone(zone)
        while current < end_local:
            following = self._next_bucket(current, granularity)
            key_text = current.isoformat(timespec="milliseconds")
            items.append(VisitTimeBucket(
                key_text,
                following.isoformat(timespec="milliseconds"),
                counts.get(key_text, 0)))
            current = following
        value = VisitTimeSeries(
            granularity, display_timezone, _START_COHORT, tuple(items))
        sample = sum(item.count for item in items)
        return value, "ok", None, {
            "rows_examined": sample, "rows_accepted": sample,
            "rows_rejected": 0, "sample_size": sample,
            "missing_count": 0,
            "watermarks": {"visits": raw["watermark"]}}

    @staticmethod
    def _bucket_start(value: datetime, granularity: str, zone: ZoneInfo):
        local = value.astimezone(zone)
        if granularity == "hour":
            return local.replace(minute=0, second=0, microsecond=0)
        if granularity == "day":
            return local.replace(hour=0, minute=0, second=0, microsecond=0)
        day = local.replace(hour=0, minute=0, second=0, microsecond=0)
        return day-timedelta(days=day.weekday())

    @staticmethod
    def _next_bucket(value: datetime, granularity: str):
        if granularity == "hour":
            return value+timedelta(hours=1)
        if granularity == "day":
            return value+timedelta(days=1)
        return value+timedelta(days=7)

    @staticmethod
    def _sum_present(rows: Any, field: str) -> int | None:
        values = [int(row[field]) for row in rows if row.get(field) is not None]
        return sum(values) if values else None
