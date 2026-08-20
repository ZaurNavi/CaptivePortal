"""Bounded, Site-scoped wireless analytics over persisted observations."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from .config import AnalyticsConfig
from .formulas import (
    configured_threshold_ratio,
    interpolate_r7,
    join_coverage,
    numeric_distribution,
    pearson_from_sums,
)
from .models import (
    AnalyticsProvenance,
    AnalyticsQuality,
    AnalyticsResult,
    ClientContextDistribution,
    ClientContextDistributionItem,
    ConcurrentClientDistribution,
    ControllerCounterMetric,
    CounterQualitySummary,
    RadioUtilizationItem,
    RadioUtilizationSummary,
    ResourceDistribution,
    SignalApCorrelation,
    SignalDistribution,
    ThroughputDistribution,
    WirelessEvidenceBundle,
)
from .source_gateway import (
    AnalyticsPerformanceBudgetExceeded,
    AnalyticsQueryDeadlineExceeded,
    AnalyticsSourceGateway,
    AnalyticsSourceUnavailable,
    QueryDeadline,
    SOURCE_SCHEMA_VERSIONS,
)
from .telemetry import AnalyticsTelemetry
from .validation import (
    AnalyticsQueryValidationError,
    format_utc,
    parse_utc,
    query_range,
    require_site,
)


QUALITY_MODE_STRICT = "strict_complete"
QUALITY_MODE_DIAGNOSTIC = "diagnostic_including_partial"
_WIRELESS_METRIC_VERSION = "wireless.v1"
_UTC = timezone.utc


class WirelessAnalyticsService:
    """Evidence-only query service; it never polls or mutates a source."""

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
        self._clock = clock or (lambda: datetime.now(_UTC))
        self._monotonic = monotonic

    def get_signal_distribution(
        self,
        site_id: str,
        from_utc: str,
        to_utc: str,
        metric: str,
        *,
        client_mac: str | None = None,
        ap_mac: str | None = None,
        ssid: str | None = None,
        band: str | None = None,
        channel: int | None = None,
        threshold: float | None = None,
        quality_mode: str = QUALITY_MODE_STRICT,
    ) -> AnalyticsResult[SignalDistribution]:
        if metric not in {"rssi", "snr"}:
            raise AnalyticsQueryValidationError("metric must be rssi or snr")
        filters = {
            "client_mac": client_mac,
            "ap_mac": ap_mac,
            "ssid": ssid,
            "band": band,
            "channel": channel,
        }
        site, start, end, mode = self._query(
            site_id, from_utc, to_utc, quality_mode
        )
        started = self._monotonic()
        evaluation = self._now()
        configured = threshold
        if configured is None:
            configured = (
                self.config.rssi_threshold_dbm
                if metric == "rssi" else self.config.snr_threshold_db
            )
        if configured is not None:
            configured = self._finite(configured, "threshold")
        try:
            self._require_enabled()
            raw = self.gateway.wireless_scalar_distribution(
                site_id=site, source="client", metric=metric,
                from_utc=start, to_utc=end, quality_mode=mode,
                filters=filters, threshold=configured,
                deadline=self._deadline(),
            )
        except (AnalyticsSourceUnavailable, AnalyticsQueryDeadlineExceeded,
                AnalyticsPerformanceBudgetExceeded) as exc:
            return self._failure(
                exc, site, start, end, evaluation, started, mode,
                f"wireless.signal.{metric}.v1", filters,
            )
        distribution = numeric_distribution(
            raw, min_samples=self.config.wireless_min_samples
        )
        value = SignalDistribution(
            metric=metric,
            distribution=distribution,
            threshold=configured_threshold_ratio(
                threshold=configured,
                sample_count=distribution.sample_count,
                below_count=raw.get("below_threshold_count"),
            ),
        )
        status, reason = self._distribution_status(
            distribution.sample_count, mode
        )
        return self._result(
            status=status, reason=reason, value=value, site=site,
            start=start, end=end, evaluation=evaluation, started=started,
            mode=mode, metric=f"wireless.signal.{metric}.v1", raw=raw,
            filters={**filters, "threshold": configured},
        )

    def get_client_distribution(
        self,
        site_id: str,
        from_utc: str,
        to_utc: str,
        dimension: str,
        *,
        quality_mode: str = QUALITY_MODE_STRICT,
    ) -> AnalyticsResult[ClientContextDistribution]:
        if dimension not in {"ap_mac", "ssid", "band", "channel"}:
            raise AnalyticsQueryValidationError("unsupported dimension")
        site, start, end, mode = self._query(
            site_id, from_utc, to_utc, quality_mode
        )
        started = self._monotonic()
        evaluation = self._now()
        try:
            self._require_enabled()
            raw = self.gateway.client_context_distribution(
                site_id=site, dimension=dimension, from_utc=start,
                to_utc=end, quality_mode=mode, deadline=self._deadline(),
            )
        except (AnalyticsSourceUnavailable, AnalyticsQueryDeadlineExceeded,
                AnalyticsPerformanceBudgetExceeded) as exc:
            return self._failure(
                exc, site, start, end, evaluation, started, mode,
                f"wireless.client_context.{dimension}.v1",
                {"dimension": dimension},
            )
        value = ClientContextDistribution(
            dimension=dimension,
            items=tuple(
                ClientContextDistributionItem(
                    context=row["context"],
                    observation_count=int(row["observation_count"]),
                    distinct_client_count=int(row["distinct_client_count"]),
                )
                for row in raw["items"]
            ),
            missing_context_count=int(raw["missing_context_count"]),
        )
        status = "insufficient_data" if not value.items else self._mode_status(mode)
        reason = "no_samples" if not value.items else None
        return self._result(
            status=status, reason=reason, value=value, site=site,
            start=start, end=end, evaluation=evaluation, started=started,
            mode=mode,
            metric=f"wireless.client_context.{dimension}.v1", raw=raw,
            filters={"dimension": dimension},
        )

    def get_concurrent_client_distribution(
        self,
        site_id: str,
        from_utc: str,
        to_utc: str,
        *,
        group_by: str | None = None,
        quality_mode: str = QUALITY_MODE_STRICT,
    ) -> AnalyticsResult[tuple[ConcurrentClientDistribution, ...]]:
        if group_by not in {None, "ap_mac", "ssid", "band"}:
            raise AnalyticsQueryValidationError("unsupported group_by")
        site, start, end, mode = self._query(
            site_id, from_utc, to_utc, quality_mode
        )
        started = self._monotonic()
        evaluation = self._now()
        try:
            self._require_enabled()
            raw = self.gateway.concurrent_client_distribution(
                site_id=site, from_utc=start, to_utc=end,
                quality_mode=mode, group_by=group_by,
                deadline=self._deadline(),
            )
        except (AnalyticsSourceUnavailable, AnalyticsQueryDeadlineExceeded,
                AnalyticsPerformanceBudgetExceeded) as exc:
            return self._failure(
                exc, site, start, end, evaluation, started, mode,
                "wireless.concurrent_clients.v1", {"group_by": group_by},
            )
        values = tuple(
            ConcurrentClientDistribution(
                group_dimension=group_by,
                context=(
                    None if row["context"] is None else str(row["context"])
                ),
                cycle_sample_count=int(row["cycle_sample_count"]),
                minimum=self._sufficient_value(row, "minimum"),
                mean=self._sufficient_value(row, "mean"),
                p50=self._sufficient_percentile(row, "p50", 0.50),
                p95=self._sufficient_percentile(row, "p95", 0.95),
                maximum=self._sufficient_value(row, "maximum"),
            )
            for row in raw["items"]
        )
        samples = int(raw["rows_accepted"])
        status, reason = self._distribution_status(samples, mode)
        if not values:
            status, reason = "insufficient_data", "no_groups"
        raw = {
            **raw,
            "sample_count": samples,
            "missing_count": 0,
        }
        return self._result(
            status=status, reason=reason, value=values, site=site,
            start=start, end=end, evaluation=evaluation, started=started,
            mode=mode, metric="wireless.concurrent_clients.v1", raw=raw,
            filters={"group_by": group_by},
        )

    def get_ap_resource_distribution(
        self,
        site_id: str,
        from_utc: str,
        to_utc: str,
        metric: str,
        *,
        ap_mac: str | None = None,
        quality_mode: str = QUALITY_MODE_STRICT,
    ) -> AnalyticsResult[ResourceDistribution]:
        if metric not in {"cpu_util", "mem_util"}:
            raise AnalyticsQueryValidationError("unsupported AP metric")
        return self._resource_distribution(
            site_id, from_utc, to_utc, source="ap", metric=metric,
            ap_mac=ap_mac, band=None, quality_mode=quality_mode,
        )

    def get_radio_utilization(
        self,
        site_id: str,
        from_utc: str,
        to_utc: str,
        metric: str,
        *,
        ap_mac: str | None = None,
        band: str | None = None,
        quality_mode: str = QUALITY_MODE_STRICT,
    ) -> AnalyticsResult[RadioUtilizationSummary]:
        if metric not in {
            "tx_util", "rx_util", "interference_util", "busy_util"
        }:
            raise AnalyticsQueryValidationError("unsupported radio metric")
        site, start, end, mode = self._query(
            site_id, from_utc, to_utc, quality_mode
        )
        started = self._monotonic()
        evaluation = self._now()
        filters = {"ap_mac": ap_mac, "band": band}
        try:
            self._require_enabled()
            raw = self.gateway.radio_utilization_distributions(
                site_id=site, metric=metric, from_utc=start, to_utc=end,
                quality_mode=mode, ap_mac=ap_mac, band=band,
                deadline=self._deadline(),
            )
        except (AnalyticsSourceUnavailable, AnalyticsQueryDeadlineExceeded,
                AnalyticsPerformanceBudgetExceeded) as exc:
            return self._failure(
                exc, site, start, end, evaluation, started, mode,
                f"wireless.radio.{metric}.v1", filters,
            )
        items = tuple(
            RadioUtilizationItem(
                ap_mac=str(row["ap_mac"]),
                band=str(row["band"]),
                distribution=numeric_distribution(
                    row, min_samples=self.config.wireless_min_samples
                ),
            )
            for row in raw["items"]
        )
        sufficient = sum(
            item.distribution.sample_count >= self.config.wireless_min_samples
            for item in items
        )
        if not items or sufficient == 0:
            status, reason = "insufficient_data", "insufficient_samples"
        elif sufficient < len(items):
            status, reason = "partial", "insufficient_group_samples"
        else:
            status, reason = self._mode_status(mode), None
        value = RadioUtilizationSummary(
            metric=metric,
            items=items,
            distinct_ap_count=int(raw["distinct_ap_count"]),
        )
        raw = {
            **raw,
            "sample_count": sum(
                item.distribution.sample_count for item in items
            ),
            "missing_count": sum(
                item.distribution.missing_count for item in items
            ),
        }
        return self._result(
            status=status, reason=reason, value=value, site=site,
            start=start, end=end, evaluation=evaluation, started=started,
            mode=mode, metric=f"wireless.radio.{metric}.v1", raw=raw,
            filters=filters,
        )

    def get_throughput_distribution(
        self,
        site_id: str,
        from_utc: str,
        to_utc: str,
        metric: str,
        *,
        client_mac: str | None = None,
        ap_mac: str | None = None,
        band: str | None = None,
        quality_mode: str = QUALITY_MODE_STRICT,
    ) -> AnalyticsResult[ThroughputDistribution]:
        site, start, end, mode = self._query(
            site_id, from_utc, to_utc, quality_mode
        )
        started = self._monotonic()
        evaluation = self._now()
        filters = {
            "client_mac": client_mac, "ap_mac": ap_mac, "band": band,
        }
        try:
            self._require_enabled()
            if metric.startswith("client_"):
                if ap_mac is not None or band is not None:
                    raise AnalyticsQueryValidationError(
                        "AP filters do not apply to client counter rates"
                    )
                raw = self.gateway.client_counter_rate_distribution(
                    site_id=site, metric=metric, from_utc=start, to_utc=end,
                    quality_mode=mode,
                    max_gap_seconds=self.config.counter_max_gap_seconds,
                    client_mac=client_mac, deadline=self._deadline(),
                )
            else:
                if client_mac is not None:
                    raise AnalyticsQueryValidationError(
                        "client filter does not apply to AP rates"
                    )
                raw = self.gateway.stored_rate_distribution(
                    site_id=site, metric=metric, from_utc=start, to_utc=end,
                    quality_mode=mode, ap_mac=ap_mac, band=band,
                    deadline=self._deadline(),
                )
        except AnalyticsQueryValidationError:
            raise
        except (AnalyticsSourceUnavailable, AnalyticsQueryDeadlineExceeded,
                AnalyticsPerformanceBudgetExceeded, ValueError) as exc:
            if isinstance(exc, ValueError) and not isinstance(
                exc, (AnalyticsSourceUnavailable,
                      AnalyticsQueryDeadlineExceeded,
                      AnalyticsPerformanceBudgetExceeded),
            ):
                raise AnalyticsQueryValidationError(str(exc)) from exc
            return self._failure(
                exc, site, start, end, evaluation, started, mode,
                f"wireless.throughput.{metric}.v1", filters,
            )
        distribution = numeric_distribution(
            raw, min_samples=self.config.wireless_min_samples
        )
        value = ThroughputDistribution(
            metric=metric,
            valid_rate_sample_count=int(raw["valid_rate_sample_count"]),
            excluded_rate_sample_count=int(raw["excluded_rate_sample_count"]),
            reason_counts=raw["reason_counts"],
            distribution=distribution,
        )
        status, reason = self._distribution_status(
            distribution.sample_count, mode
        )
        return self._result(
            status=status, reason=reason, value=value, site=site,
            start=start, end=end, evaluation=evaluation, started=started,
            mode=mode, metric=f"wireless.throughput.{metric}.v1", raw=raw,
            filters={
                **filters,
                "counter_max_gap_seconds": self.config.counter_max_gap_seconds,
            },
        )

    def get_counter_quality(
        self,
        site_id: str,
        from_utc: str,
        to_utc: str,
        *,
        ap_mac: str | None = None,
        band: str | None = None,
        quality_mode: str = QUALITY_MODE_STRICT,
    ) -> AnalyticsResult[CounterQualitySummary]:
        site, start, end, mode = self._query(
            site_id, from_utc, to_utc, quality_mode
        )
        started = self._monotonic()
        evaluation = self._now()
        filters = {"ap_mac": ap_mac, "band": band}
        try:
            self._require_enabled()
            raw = self.gateway.radio_counter_quality(
                site_id=site, from_utc=start, to_utc=end,
                quality_mode=mode,
                max_gap_seconds=self.config.counter_max_gap_seconds,
                ap_mac=ap_mac, band=band, deadline=self._deadline(),
            )
        except (AnalyticsSourceUnavailable, AnalyticsQueryDeadlineExceeded,
                AnalyticsPerformanceBudgetExceeded) as exc:
            return self._failure(
                exc, site, start, end, evaluation, started, mode,
                "wireless.counter_quality.v1", filters,
            )
        metrics = {}
        for name, item in raw["metrics"].items():
            event_delta = int(item["total_delta"])
            ratio_event_delta = int(item["ratio_event_delta"])
            packet_delta = int(item["packet_delta"])
            metrics[name] = ControllerCounterMetric(
                metric=name,
                valid_interval_count=int(item["valid_count"]),
                reset_interval_count=int(item["reset_count"]),
                gap_interval_count=int(item["gap_count"]),
                missing_interval_count=int(item["missing_count"]),
                total_delta=event_delta,
                ratio_event_delta=ratio_event_delta,
                packet_delta=packet_delta,
                controller_events_per_1000_packets=(
                    None if packet_delta <= 0
                    else 1000.0 * ratio_event_delta / packet_delta
                ),
            )
        value = CounterQualitySummary(ap_mac, band, metrics)
        samples = int(raw["rows_accepted"])
        status = "insufficient_data" if samples < 2 else self._mode_status(mode)
        reason = "insufficient_samples" if samples < 2 else None
        raw = {
            **raw, "sample_count": samples, "missing_count": 0,
            "partial_cycle_count": int(raw.get("partial_cycle_count") or 0),
        }
        return self._result(
            status=status, reason=reason, value=value, site=site,
            start=start, end=end, evaluation=evaluation, started=started,
            mode=mode, metric="wireless.counter_quality.v1", raw=raw,
            filters={
                **filters,
                "counter_max_gap_seconds": self.config.counter_max_gap_seconds,
            },
        )

    def get_signal_ap_correlation(
        self,
        site_id: str,
        from_utc: str,
        to_utc: str,
        signal_metric: str,
        ap_metric: str,
        *,
        quality_mode: str = QUALITY_MODE_STRICT,
    ) -> AnalyticsResult[SignalApCorrelation]:
        site, start, end, mode = self._query(
            site_id, from_utc, to_utc, quality_mode
        )
        started = self._monotonic()
        evaluation = self._now()
        filters = {"signal_metric": signal_metric, "ap_metric": ap_metric}
        try:
            self._require_enabled()
            raw = self.gateway.signal_ap_correlation(
                site_id=site, signal_metric=signal_metric,
                ap_metric=ap_metric, from_utc=start, to_utc=end,
                quality_mode=mode,
                max_lag_seconds=self.config.ap_join_max_lag_seconds,
                deadline=self._deadline(),
            )
        except ValueError as exc:
            raise AnalyticsQueryValidationError(str(exc)) from exc
        except (AnalyticsSourceUnavailable, AnalyticsQueryDeadlineExceeded,
                AnalyticsPerformanceBudgetExceeded) as exc:
            return self._failure(
                exc, site, start, end, evaluation, started, mode,
                "wireless.correlation.v1", filters,
            )
        sample_count = int(raw["sample_count"])
        coefficient = pearson_from_sums(
            sample_count=sample_count,
            sum_x=float(raw["sum_x"]), sum_y=float(raw["sum_y"]),
            sum_xx=float(raw["sum_xx"]), sum_yy=float(raw["sum_yy"]),
            sum_xy=float(raw["sum_xy"]),
            min_samples=self.config.wireless_min_samples,
        )
        coverage = join_coverage(raw)
        value = SignalApCorrelation(
            signal_metric, ap_metric, sample_count, coefficient, coverage
        )
        status = (
            self._mode_status(mode) if coefficient is not None
            else "insufficient_data"
        )
        reason = None if coefficient is not None else "insufficient_samples_or_variance"
        if coverage.client_sample_count and coverage.match_ratio is not None:
            if coverage.match_ratio < 0.5:
                self.telemetry.emit(
                    "analytics.wireless_join_coverage_low",
                    metric="wireless.correlation.v1", site_id=site,
                    duration_ms=0, sample_size=sample_count,
                    status=status, reason="join_coverage_low",
                    quality_mode=mode,
                )
        raw = {
            **raw,
            "rows_examined": int(raw["client_sample_count"]),
            "rows_accepted": sample_count,
            "rows_rejected": (
                int(raw["client_sample_count"]) - sample_count
            ),
            "missing_count": (
                int(raw["client_sample_count"]) - sample_count
            ),
            "partial_cycle_count": 0,
        }
        return self._result(
            status=status, reason=reason, value=value, site=site,
            start=start, end=end, evaluation=evaluation, started=started,
            mode=mode, metric="wireless.correlation.v1", raw=raw,
            filters={
                **filters,
                "join_max_lag_seconds": self.config.ap_join_max_lag_seconds,
            },
        )

    def get_wireless_evidence_bundle(
        self,
        site_id: str,
        from_utc: str,
        to_utc: str,
        *,
        quality_mode: str = QUALITY_MODE_STRICT,
    ) -> WirelessEvidenceBundle:
        return WirelessEvidenceBundle(
            signal={metric: self.get_signal_distribution(
                site_id, from_utc, to_utc, metric,
                quality_mode=quality_mode,
            ) for metric in ("rssi", "snr")},
            client_context={dimension: self.get_client_distribution(
                site_id, from_utc, to_utc, dimension,
                quality_mode=quality_mode,
            ) for dimension in ("ap_mac", "ssid", "band", "channel")},
            concurrent_clients=self.get_concurrent_client_distribution(
                site_id, from_utc, to_utc, quality_mode=quality_mode
            ),
            ap_resources={metric: self.get_ap_resource_distribution(
                site_id, from_utc, to_utc, metric,
                quality_mode=quality_mode,
            ) for metric in ("cpu_util", "mem_util")},
            radio_utilization={metric: self.get_radio_utilization(
                site_id, from_utc, to_utc, metric,
                quality_mode=quality_mode,
            ) for metric in (
                "tx_util", "rx_util", "interference_util", "busy_util"
            )},
            throughput={metric: self.get_throughput_distribution(
                site_id, from_utc, to_utc, metric,
                quality_mode=quality_mode,
            ) for metric in (
                "client_download_mbps", "client_upload_mbps",
                "wired_download_mbps", "wired_upload_mbps",
                "lan_rx_mbps", "lan_tx_mbps",
                "radio_rx_mbps", "radio_tx_mbps",
            )},
            counter_quality=self.get_counter_quality(
                site_id, from_utc, to_utc, quality_mode=quality_mode
            ),
            correlations={
                f"{signal}_{target}": self.get_signal_ap_correlation(
                    site_id, from_utc, to_utc, signal, target,
                    quality_mode=quality_mode,
                )
                for signal in ("rssi", "snr")
                for target in ("busy_util", "cpu_util")
            },
        )

    def _resource_distribution(
        self,
        site_id: str,
        from_utc: str,
        to_utc: str,
        *,
        source: str,
        metric: str,
        ap_mac: str | None,
        band: str | None,
        quality_mode: str,
    ) -> AnalyticsResult[ResourceDistribution]:
        site, start, end, mode = self._query(
            site_id, from_utc, to_utc, quality_mode
        )
        started = self._monotonic()
        evaluation = self._now()
        filters = {"ap_mac": ap_mac, "band": band}
        try:
            self._require_enabled()
            raw = self.gateway.wireless_scalar_distribution(
                site_id=site, source=source, metric=metric,
                from_utc=start, to_utc=end, quality_mode=mode,
                filters=filters, threshold=None, deadline=self._deadline(),
            )
        except (AnalyticsSourceUnavailable, AnalyticsQueryDeadlineExceeded,
                AnalyticsPerformanceBudgetExceeded) as exc:
            return self._failure(
                exc, site, start, end, evaluation, started, mode,
                f"wireless.{source}.{metric}.v1", filters,
            )
        distribution = numeric_distribution(
            raw, min_samples=self.config.wireless_min_samples
        )
        value = ResourceDistribution(
            metric=metric, distribution=distribution,
            distinct_ap_count=(
                int(raw["distinct_ap_count"]) if source == "radio" else None
            ),
            band=band if source == "radio" else None,
        )
        status, reason = self._distribution_status(
            distribution.sample_count, mode
        )
        return self._result(
            status=status, reason=reason, value=value, site=site,
            start=start, end=end, evaluation=evaluation, started=started,
            mode=mode, metric=f"wireless.{source}.{metric}.v1", raw=raw,
            filters=filters,
        )

    def _query(
        self,
        site_id: str,
        from_utc: str,
        to_utc: str,
        quality_mode: str,
    ) -> tuple[str, str, str, str]:
        site = require_site(site_id)
        start, end, start_dt, end_dt = query_range(
            self.config, from_utc, to_utc
        )
        if (end_dt - start_dt).total_seconds() > (
            self.config.wireless_max_window_days * 86_400
        ):
            raise AnalyticsQueryValidationError(
                "wireless query window exceeds configured maximum"
            )
        if quality_mode not in {QUALITY_MODE_STRICT, QUALITY_MODE_DIAGNOSTIC}:
            raise AnalyticsQueryValidationError("quality_mode is invalid")
        return site, start, end, quality_mode

    def _deadline(self) -> QueryDeadline:
        return QueryDeadline.after(
            self.config.max_query_duration_seconds,
            monotonic=self._monotonic,
        )

    def _require_enabled(self) -> None:
        if not self.config.enabled:
            raise AnalyticsSourceUnavailable("Analytics is disabled")
        if not self.config.wireless_enabled:
            raise AnalyticsSourceUnavailable("Wireless Analytics is disabled")

    def _now(self) -> str:
        value = self._clock()
        if not isinstance(value, datetime):
            raise RuntimeError("Analytics clock must return datetime")
        return format_utc(value)

    def _result(
        self,
        *,
        status: str,
        reason: str | None,
        value: Any,
        site: str,
        start: str,
        end: str,
        evaluation: str,
        started: float,
        mode: str,
        metric: str,
        raw: Mapping[str, Any],
        filters: Mapping[str, Any],
    ) -> AnalyticsResult[Any]:
        duration = max(0.0, (self._monotonic() - started) * 1000)
        result = AnalyticsResult(
            status=status,
            value=value,
            quality=AnalyticsQuality(
                quality_mode=mode,
                reason=reason,
                accepted_rows=int(raw.get("rows_accepted") or 0),
                rejected_rows=int(raw.get("rows_rejected") or 0),
                missing_count=int(raw.get("missing_count") or 0),
                partial_cycle_count=int(
                    raw.get("partial_cycle_count") or 0
                ),
                failed_cycle_count=int(
                    raw.get("failed_cycle_count") or 0
                ),
                abandoned_cycle_count=int(
                    raw.get("abandoned_cycle_count") or 0
                ),
            ),
            provenance=AnalyticsProvenance(
                site_id=site, from_utc=start, to_utc=end,
                evaluation_at_utc=evaluation,
                computed_at_utc=self._now(), quality_mode=mode,
                source_names=("observations",),
                source_schema_versions={
                    "observations": SOURCE_SCHEMA_VERSIONS["observations"]
                },
                source_watermarks={"observations": raw.get("watermark")},
                source_rows_examined=int(raw.get("rows_examined") or 0),
                source_rows_accepted=int(raw.get("rows_accepted") or 0),
                source_rows_rejected=int(raw.get("rows_rejected") or 0),
                sample_size=int(raw.get("sample_count") or 0),
                missing_count=int(raw.get("missing_count") or 0),
                partial_cycle_count=int(
                    raw.get("partial_cycle_count") or 0
                ),
                failed_cycle_count=int(
                    raw.get("failed_cycle_count") or 0
                ),
                abandoned_cycle_count=int(
                    raw.get("abandoned_cycle_count") or 0
                ),
                filters=filters, metric_version=metric,
                query_duration_ms=duration,
            ),
        )
        event = {
            "unavailable": "analytics.wireless_query_unavailable",
            "insufficient_data": "analytics.wireless_insufficient_data",
        }.get(status, "analytics.wireless_query_completed")
        self.telemetry.emit(
            event, metric=metric, site_id=site,
            duration_ms=round(duration, 3),
            sample_size=result.provenance.sample_size,
            status=status, reason=reason, quality_mode=mode,
        )
        return result

    def _failure(
        self,
        exc: Exception,
        site: str,
        start: str,
        end: str,
        evaluation: str,
        started: float,
        mode: str,
        metric: str,
        filters: Mapping[str, Any],
    ) -> AnalyticsResult[Any]:
        if isinstance(exc, AnalyticsQueryDeadlineExceeded):
            reason = "query_deadline"
        elif isinstance(exc, AnalyticsPerformanceBudgetExceeded):
            reason = "performance_budget_exceeded"
        elif "disabled" in str(exc).lower():
            reason = "disabled"
        else:
            reason = "source_unavailable"
        return self._result(
            status="unavailable", reason=reason, value=None, site=site,
            start=start, end=end, evaluation=evaluation, started=started,
            mode=mode, metric=metric,
            raw={"rows_examined": 0, "rows_accepted": 0,
                 "rows_rejected": 0, "sample_count": 0,
                 "missing_count": 0, "partial_cycle_count": 0,
                 "watermark": None},
            filters=filters,
        )

    def _distribution_status(
        self, sample_count: int, mode: str
    ) -> tuple[str, str | None]:
        if sample_count < self.config.wireless_min_samples:
            return "insufficient_data", "insufficient_samples"
        return self._mode_status(mode), None

    @staticmethod
    def _mode_status(mode: str) -> str:
        return "partial" if mode == QUALITY_MODE_DIAGNOSTIC else "ok"

    def _sufficient_value(
        self, row: Mapping[str, Any], name: str
    ) -> float | None:
        if int(row["cycle_sample_count"]) < self.config.wireless_min_samples:
            return None
        return None if row[name] is None else float(row[name])

    def _sufficient_percentile(
        self,
        row: Mapping[str, Any],
        prefix: str,
        probability: float,
    ) -> float | None:
        count = int(row["cycle_sample_count"])
        if count < self.config.wireless_min_samples:
            return None
        return interpolate_r7(
            count, probability,
            row[f"{prefix}_lower"], row[f"{prefix}_upper"],
        )

    @staticmethod
    def _finite(value: Any, name: str) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError) as exc:
            raise AnalyticsQueryValidationError(
                f"{name} must be finite"
            ) from exc
        if parsed != parsed or parsed in {float("inf"), float("-inf")}:
            raise AnalyticsQueryValidationError(f"{name} must be finite")
        return parsed
