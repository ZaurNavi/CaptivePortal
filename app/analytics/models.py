"""Immutable public contracts for Analytics Read and Data Quality v1."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Generic, Mapping, TypeVar


ANALYTICS_STATUSES = frozenset({
    "ok", "partial", "insufficient_data", "unavailable",
})
QUALITY_MODES = frozenset({
    "strict_complete", "diagnostic_including_partial",
})


def freeze(value: Any) -> Any:
    """Recursively detach and freeze values exposed by Analytics."""
    if isinstance(value, Mapping):
        return MappingProxyType({
            str(key): freeze(item) for key, item in value.items()
        })
    if isinstance(value, (list, tuple)):
        return tuple(freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(freeze(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class AnalyticsQuality:
    quality_mode: str
    reason: str | None = None
    accepted_rows: int = 0
    rejected_rows: int = 0
    missing_count: int = 0
    partial_cycle_count: int = 0
    failed_cycle_count: int = 0
    abandoned_cycle_count: int = 0
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.quality_mode not in QUALITY_MODES:
            raise ValueError("unsupported Analytics quality mode")
        object.__setattr__(self, "warnings", tuple(self.warnings))


@dataclass(frozen=True, slots=True)
class AnalyticsProvenance:
    site_id: str
    from_utc: str
    to_utc: str
    evaluation_at_utc: str
    computed_at_utc: str
    quality_mode: str
    source_names: tuple[str, ...]
    source_schema_versions: Mapping[str, int]
    source_watermarks: Mapping[str, str | None]
    source_rows_examined: int
    source_rows_accepted: int
    source_rows_rejected: int
    sample_size: int
    missing_count: int
    partial_cycle_count: int
    failed_cycle_count: int
    abandoned_cycle_count: int
    filters: Mapping[str, Any]
    metric_version: str
    query_duration_ms: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_names", tuple(self.source_names))
        object.__setattr__(
            self, "source_schema_versions",
            freeze(self.source_schema_versions),
        )
        object.__setattr__(
            self, "source_watermarks", freeze(self.source_watermarks)
        )
        object.__setattr__(self, "filters", freeze(self.filters))


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class AnalyticsResult(Generic[T]):
    status: str
    value: T | None
    quality: AnalyticsQuality
    provenance: AnalyticsProvenance

    def __post_init__(self) -> None:
        if self.status not in ANALYTICS_STATUSES:
            raise ValueError("unsupported Analytics status")
        object.__setattr__(self, "value", freeze(self.value))


@dataclass(frozen=True, slots=True)
class CoverageMetric:
    numerator: int
    denominator: int
    ratio: float | None


@dataclass(frozen=True, slots=True)
class CycleQualitySummary:
    kind: str
    running: int
    completed: int
    abandoned: int
    completed_complete: int
    completed_incomplete: int
    success: int
    partial: int
    failed: int
    shutdown: int
    complete_ratio: float | None
    latest_accepted_at: str | None


@dataclass(frozen=True, slots=True)
class SourceFreshness:
    source_name: str
    status: str
    latest_timestamp: str | None
    freshness_seconds: float | None


@dataclass(frozen=True, slots=True)
class FieldCompleteness:
    source: str
    field: str
    row_count: int
    non_null_count: int
    missing_count: int
    coverage_ratio: float | None


@dataclass(frozen=True, slots=True)
class VisitObservationCoverage:
    sample_count: int
    interval_count: int
    first_observed_at: str | None
    last_observed_at: str | None
    edge_gap_start_seconds: float | None
    edge_gap_end_seconds: float | None
    max_inter_sample_gap_seconds: float | None
    gap_count_over_threshold: int
    gap_threshold_seconds: float
    observed_span_seconds: float | None
    observed_span_ratio: float | None
    provisional: bool


@dataclass(frozen=True, slots=True)
class SafeSnapshotSummary:
    snapshot_id: str
    device_id: str
    auth_session_id: str
    site_id: str
    requested_mac: str
    authorized_at: str
    captured_at: str
    device_type: str | None
    ssid: str | None
    ap_mac: str | None
    radio_id: int | None
    channel: int | None
    rssi: int | None
    snr: int | None
    traffic_down: int | None
    traffic_up: int | None


@dataclass(frozen=True, slots=True)
class RegistryDeviceSummary:
    device_id: str
    mac: str
    first_seen_at: str
    last_seen_at: str
    last_site_id: str
    last_ip: str | None
    last_ssid: str | None
    last_ap_name: str | None
    last_ap_mac: str | None
    last_rssi: int | None
    last_snr: int | None
    snapshot_count: int
    site_context_available: bool


@dataclass(frozen=True, slots=True)
class VisitQualityItem:
    visit_id: str
    site_id: str
    client_mac: str
    device_id: str | None
    initial_snapshot_id: str | None
    started_at: str
    closed_at: str | None
    status: str
    authorization_count: int | None
    snapshot_resolved: bool | None


@dataclass(frozen=True, slots=True)
class AnalyticsPage(Generic[T]):
    items: tuple[T, ...]
    next_cursor: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))


@dataclass(frozen=True, slots=True)
class AnalyticsVisitContext:
    visit: VisitQualityItem
    device: RegistryDeviceSummary | None
    snapshot: SafeSnapshotSummary | None
    observation_coverage: VisitObservationCoverage | None


@dataclass(frozen=True, slots=True)
class SourceQualitySummary:
    cycle_quality: Mapping[str, CycleQualitySummary]
    freshness: Mapping[str, SourceFreshness]
    field_completeness: Mapping[str, tuple[FieldCompleteness, ...]]
    device_link_coverage: CoverageMetric | None
    initial_snapshot_link_coverage: CoverageMetric | None
    resolved_snapshot_coverage: CoverageMetric | None
    authorization_attachment_coverage: CoverageMetric | None
    closed_visit_coverage: CoverageMetric | None
    open_visit_count: int | None
    source_event_quality: Mapping[str, Mapping[str, int]]
    unavailable_sources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "cycle_quality", freeze(self.cycle_quality))
        object.__setattr__(self, "freshness", freeze(self.freshness))
        object.__setattr__(
            self, "field_completeness", freeze(self.field_completeness)
        )
        object.__setattr__(
            self, "source_event_quality", freeze(self.source_event_quality)
        )
        object.__setattr__(
            self, "unavailable_sources", tuple(self.unavailable_sources)
        )


@dataclass(frozen=True, slots=True)
class NumericDistribution:
    sample_count: int
    missing_count: int
    minimum: float | None
    maximum: float | None
    mean: float | None
    p10: float | None
    p50: float | None
    p90: float | None
    p95: float | None


@dataclass(frozen=True, slots=True)
class ConfiguredThresholdRatio:
    threshold: float | None
    below_threshold_count: int | None
    below_configured_threshold_ratio: float | None


@dataclass(frozen=True, slots=True)
class SignalDistribution:
    metric: str
    distribution: NumericDistribution
    threshold: ConfiguredThresholdRatio


@dataclass(frozen=True, slots=True)
class ClientContextDistributionItem:
    context: str | int | None
    observation_count: int
    distinct_client_count: int


@dataclass(frozen=True, slots=True)
class ClientContextDistribution:
    dimension: str
    items: tuple[ClientContextDistributionItem, ...]
    missing_context_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))


@dataclass(frozen=True, slots=True)
class ConcurrentClientDistribution:
    group_dimension: str | None
    context: str | None
    cycle_sample_count: int
    minimum: float | None
    mean: float | None
    p50: float | None
    p95: float | None
    maximum: float | None


@dataclass(frozen=True, slots=True)
class ResourceDistribution:
    metric: str
    distribution: NumericDistribution
    distinct_ap_count: int | None = None
    band: str | None = None


@dataclass(frozen=True, slots=True)
class RadioUtilizationItem:
    ap_mac: str
    band: str
    distribution: NumericDistribution


@dataclass(frozen=True, slots=True)
class RadioUtilizationSummary:
    metric: str
    items: tuple[RadioUtilizationItem, ...]
    distinct_ap_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))


@dataclass(frozen=True, slots=True)
class ThroughputDistribution:
    metric: str
    valid_rate_sample_count: int
    excluded_rate_sample_count: int
    reason_counts: Mapping[str, int]
    distribution: NumericDistribution

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_counts", freeze(self.reason_counts))


@dataclass(frozen=True, slots=True)
class ControllerCounterMetric:
    metric: str
    valid_interval_count: int
    reset_interval_count: int
    gap_interval_count: int
    missing_interval_count: int
    total_delta: int
    ratio_event_delta: int
    packet_delta: int
    controller_events_per_1000_packets: float | None


@dataclass(frozen=True, slots=True)
class CounterQualitySummary:
    ap_mac: str | None
    band: str | None
    metrics: Mapping[str, ControllerCounterMetric]

    def __post_init__(self) -> None:
        object.__setattr__(self, "metrics", freeze(self.metrics))


@dataclass(frozen=True, slots=True)
class JoinCoverage:
    client_sample_count: int
    matched_count: int
    unmatched_count: int
    match_ratio: float | None
    lag_p50: float | None
    lag_p95: float | None
    lag_max: float | None


@dataclass(frozen=True, slots=True)
class SignalApCorrelation:
    signal_metric: str
    ap_metric: str
    sample_count: int
    coefficient: float | None
    coverage: JoinCoverage


@dataclass(frozen=True, slots=True)
class WirelessEvidenceBundle:
    signal: Mapping[str, AnalyticsResult[Any]]
    client_context: Mapping[str, AnalyticsResult[Any]]
    concurrent_clients: AnalyticsResult[Any]
    ap_resources: Mapping[str, AnalyticsResult[Any]]
    radio_utilization: Mapping[str, AnalyticsResult[Any]]
    throughput: Mapping[str, AnalyticsResult[Any]]
    counter_quality: AnalyticsResult[Any]
    correlations: Mapping[str, AnalyticsResult[Any]]

    def __post_init__(self) -> None:
        for field in (
            "signal", "client_context", "ap_resources",
            "radio_utilization", "throughput", "correlations",
        ):
            object.__setattr__(self, field, freeze(getattr(self, field)))


@dataclass(frozen=True, slots=True)
class VisitCountSummary:
    total_visit_count: int
    open_visit_count: int
    closed_visit_count: int
    population_semantics: str = "visit_start_cohort"


@dataclass(frozen=True, slots=True)
class VisitTimeBucket:
    bucket_start: str
    bucket_end: str
    count: int


@dataclass(frozen=True, slots=True)
class VisitTimeSeries:
    granularity: str
    display_timezone: str
    population_semantics: str
    items: tuple[VisitTimeBucket, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))


@dataclass(frozen=True, slots=True)
class DeviceCountSummary:
    unique_linked_devices: int
    linked_visit_count: int
    unlinked_visit_count: int


@dataclass(frozen=True, slots=True)
class RepeatDeviceSummary:
    unique_linked_devices: int
    repeat_device_count: int
    repeat_device_ratio: float | None


@dataclass(frozen=True, slots=True)
class NewToSiteDeviceSummary:
    unique_linked_devices_in_window: int
    new_to_site_device_count: int
    known_before_window_device_count: int
    unlinked_visit_count: int


@dataclass(frozen=True, slots=True)
class VisitDurationSummary:
    distribution: NumericDistribution
    excluded_open_count: int
    excluded_missing_duration_count: int


@dataclass(frozen=True, slots=True)
class VisitAuthorizationSummary:
    distribution: NumericDistribution
    visits_with_exactly_one_authorization: int
    visits_with_multiple_authorizations: int
    visits_with_zero_authorization: int


@dataclass(frozen=True, slots=True)
class VisitClosureSummary:
    closed_visit_count: int
    close_reasons: Mapping[str, int]
    close_time_sources: Mapping[str, int]
    duration_difference_seconds: NumericDistribution

    def __post_init__(self) -> None:
        object.__setattr__(self, "close_reasons", freeze(self.close_reasons))
        object.__setattr__(
            self, "close_time_sources", freeze(self.close_time_sources)
        )


@dataclass(frozen=True, slots=True)
class VisitSourceEventQuality:
    by_processing_result: Mapping[str, int]
    by_reason: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "by_processing_result", freeze(self.by_processing_result)
        )
        object.__setattr__(self, "by_reason", freeze(self.by_reason))


@dataclass(frozen=True, slots=True)
class VisitContextDistributionItem:
    context: str | None
    visit_count: int


@dataclass(frozen=True, slots=True)
class VisitContextDistribution:
    dimension: str
    items: tuple[VisitContextDistributionItem, ...]
    null_context_count: int
    grouping_is_non_exclusive: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))


@dataclass(frozen=True, slots=True)
class VisitContextSummary:
    start_ssid: VisitContextDistribution
    final_ssid: VisitContextDistribution
    start_ap_mac: VisitContextDistribution
    final_ap_mac: VisitContextDistribution
    touched_ssid: VisitContextDistribution
    touched_ap_mac: VisitContextDistribution


@dataclass(frozen=True, slots=True)
class VisitContextTransition:
    context: str
    comparable_count: int
    changed_count: int
    unchanged_count: int
    missing_side_count: int
    interpretation: str


@dataclass(frozen=True, slots=True)
class VisitObservationCoverageSummary:
    visit_count: int
    visits_with_zero_client_observations: int
    visits_with_one_or_more_client_observations: int
    sample_count_distribution: NumericDistribution
    observed_span_ratio_distribution: NumericDistribution
    max_gap_distribution: NumericDistribution


@dataclass(frozen=True, slots=True)
class VisitWirelessSummary:
    visit_id: str
    observation_coverage: VisitObservationCoverage
    signal: Mapping[str, AnalyticsResult[Any]]
    correlations: Mapping[str, AnalyticsResult[Any]]

    def __post_init__(self) -> None:
        object.__setattr__(self, "signal", freeze(self.signal))
        object.__setattr__(self, "correlations", freeze(self.correlations))


@dataclass(frozen=True, slots=True)
class VisitTrafficSummary:
    reported_total_bytes: int | None
    reported_up_bytes: int | None
    reported_down_bytes: int | None
    reported_missing_total_count: int
    reported_missing_up_count: int
    reported_missing_down_count: int
    observed_counter_delta_down_bytes: int | None
    observed_counter_delta_up_bytes: int | None
    observed_delta_coverage: CoverageMetric
    reconciliation_difference_bytes: int | None
    reconciliation_ratio: float | None


@dataclass(frozen=True, slots=True)
class ReturnIntervalSummary:
    distribution: NumericDistribution


@dataclass(frozen=True, slots=True)
class VisitAnalyticsBundle:
    counts: AnalyticsResult[Any]
    devices: AnalyticsResult[Any]
    repeat_devices: AnalyticsResult[Any]
    new_to_site_devices: AnalyticsResult[Any]
    duration: AnalyticsResult[Any]
    authorizations: AnalyticsResult[Any]
    closure: AnalyticsResult[Any]
    source_event_quality: AnalyticsResult[Any]
    contexts: AnalyticsResult[Any]
    context_transitions: AnalyticsResult[Any]
    observation_coverage: AnalyticsResult[Any]
    traffic: AnalyticsResult[Any]
    return_intervals: AnalyticsResult[Any]


@dataclass(frozen=True, slots=True)
class CurrentTrafficFreshnessPolicy:
    fresh_max_age_seconds: float
    stale_max_age_seconds: float
    max_ap_skew_seconds: float


@dataclass(frozen=True, slots=True)
class CurrentTrafficSnapshot:
    source_kind: str
    site_id: str
    cycle_id: str | None
    started_at: str | None
    finished_at: str | None
    complete: bool
    evaluated_at: str
    observed_at: str | None
    newest_observed_at: str | None
    age_seconds: float | None
    source_skew_seconds: float | None
    freshness_status: str
    freshness_reason: str
    primary_source: str
    selected_source: str | None
    selection_reason: str
    empty_population: bool
    latest_attempt_state: str
    latest_attempt_result: str | None
    latest_attempt_at: str | None
    using_previous_complete_snapshot: bool


@dataclass(frozen=True, slots=True)
class CurrentTrafficSourceSelection:
    primary_source: str
    selected_source: str | None
    selection_reason: str
    wired_pair_valid_ap_count: int
    lan_pair_valid_ap_count: int
    source_mixing_allowed: bool = False


@dataclass(frozen=True, slots=True)
class CurrentTrafficCoverage:
    status: str
    reasons: tuple[str, ...]
    empty_population: bool
    total_ap_count: int
    valid_rate_ap_count: int
    valid_download_ap_count: int
    valid_upload_ap_count: int
    missing_rate_ap_count: int
    stale_ap_count: int
    unavailable_ap_count: int
    reset_ap_count: int
    gap_rejected_ap_count: int
    no_baseline_ap_count: int
    source_unavailable_ap_count: int
    invalid_elapsed_ap_count: int
    observed_at: str | None
    newest_observed_at: str | None
    source_skew_seconds: float | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "reasons", tuple(self.reasons))


@dataclass(frozen=True, slots=True)
class CurrentTrafficFreshness:
    status: str
    reason: str
    evaluated_at_utc: str
    observed_at: str | None
    newest_observed_at: str | None
    age_seconds: float | None


@dataclass(frozen=True, slots=True)
class CurrentTrafficTotals:
    download_mbps: float | None
    upload_mbps: float | None
    total_mbps: float | None


@dataclass(frozen=True, slots=True)
class CurrentSiteTraffic:
    snapshot: CurrentTrafficSnapshot
    freshness_policy: CurrentTrafficFreshnessPolicy
    source_selection: CurrentTrafficSourceSelection
    coverage: CurrentTrafficCoverage
    freshness: CurrentTrafficFreshness
    traffic: CurrentTrafficTotals


@dataclass(frozen=True, slots=True)
class CurrentApTrafficItem:
    ap_mac: str
    name: str | None
    download_mbps: float | None
    upload_mbps: float | None
    total_mbps: float | None
    download_reason: str
    upload_reason: str
    rate_status: str
    observed_at: str | None
    age_seconds: float | None
    selected_source: str


@dataclass(frozen=True, slots=True)
class CurrentTrafficPageMetadata:
    limit: int
    next_cursor: str | None
    cycle_id: str
    selected_source: str


@dataclass(frozen=True, slots=True)
class CurrentApTrafficPage:
    snapshot: CurrentTrafficSnapshot
    freshness_policy: CurrentTrafficFreshnessPolicy
    source_selection: CurrentTrafficSourceSelection
    items: tuple[CurrentApTrafficItem, ...]
    page: CurrentTrafficPageMetadata

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))


@dataclass(frozen=True, slots=True)
class HistoricalTrafficRange:
    site_id: str
    from_utc: str
    to_utc: str
    evaluated_at_utc: str
    bucket_seconds: int
    bucket_count: int
    max_site_sample_source_skew_seconds: int
    bucket_alignment: str = "range_start_utc"
    max_site_history_buckets: int = 720
    unit: str = "Mbps"
    aggregation: str = "mean_of_complete_site_rate_samples"
    metric_version: str = "network_traffic_history.v1"
    source_kind: str = "observation_ap_dynamic"
    sample_timestamp_semantics: str = "cycle_finished_at"


@dataclass(frozen=True, slots=True)
class HistoricalTrafficSourceSelection:
    primary_source: str
    selected_source: str | None
    selection_reason: str
    wired_complete_site_cycle_count: int
    lan_complete_site_cycle_count: int
    wired_pair_valid_ap_opportunities: int
    lan_pair_valid_ap_opportunities: int
    source_mixing_allowed: bool = False


@dataclass(frozen=True, slots=True)
class HistoricalTrafficBucket:
    bucket_start_utc: str
    bucket_end_utc: str
    download_mbps: float | None
    upload_mbps: float | None
    total_mbps: float | None
    status: str
    selected_source: str | None
    selection_reason: str
    source_changed_from_previous: bool
    canonical_cycle_count: int
    complete_site_sample_count: int
    excluded_site_sample_count: int
    total_ap_opportunities: int
    selected_pair_valid_ap_opportunities: int
    first_complete_sample_at: str | None
    last_complete_sample_at: str | None
    leading_gap_seconds: float
    trailing_gap_seconds: float
    max_inter_sample_gap_seconds: float
    gap_count_over_threshold: int
    selected_source_skew_excluded_sample_count: int
    rate_reason_counts: Mapping[str, int]
    source_selection: HistoricalTrafficSourceSelection

    def __post_init__(self) -> None:
        object.__setattr__(self, "rate_reason_counts", freeze(self.rate_reason_counts))


@dataclass(frozen=True, slots=True)
class HistoricalTrafficCoverage:
    status: str
    available_from_utc: str | None
    available_through_utc: str | None
    source_watermark_utc: str | None
    source_age_seconds: float | None
    bucket_count: int
    complete_bucket_count: int
    partial_bucket_count: int
    missing_bucket_count: int
    canonical_cycle_count: int
    complete_site_sample_count: int
    excluded_site_sample_count: int
    gap_bucket_count: int
    source_transition_count: int


@dataclass(frozen=True, slots=True)
class HistoricalTrafficQuality:
    partial_cycle_count: int
    failed_cycle_count: int
    shutdown_cycle_count: int
    abandoned_cycle_count: int
    running_cycle_count: int
    no_baseline_count: int
    counter_reset_count: int
    gap_too_large_count: int
    invalid_elapsed_count: int
    source_unavailable_count: int
    source_skew_excluded_sample_count: int
    integrity_failure_count: int


@dataclass(frozen=True, slots=True)
class HistoricalTrafficPeriodValues:
    download_mbps: float | None
    upload_mbps: float | None
    total_mbps: float | None


@dataclass(frozen=True, slots=True)
class HistoricalTrafficPeriodIntervalEvidence:
    range_seconds: float
    candidate_interval_count: int
    accepted_interval_count: int
    accepted_interval_seconds: float
    interval_coverage_ratio: float
    excluded_gap_interval_count: int
    excluded_source_transition_interval_count: int
    invalid_period_interval_count: int
    accepted_peak_sample_count: int
    leading_unweighted_seconds: float
    trailing_unweighted_seconds: float


@dataclass(frozen=True, slots=True)
class HistoricalTrafficPeriodStatistics:
    status: str
    average: HistoricalTrafficPeriodValues
    peak: HistoricalTrafficPeriodValues
    interval_evidence: HistoricalTrafficPeriodIntervalEvidence
    metric_version: str = "network_traffic_period_statistics.v1"
    average_method: str = "right_endpoint_sample_hold_time_weighted.v1"
    peak_method: str = "max_accepted_complete_site_sample.v1"
    unit: str = "Mbps"


@dataclass(frozen=True, slots=True)
class HistoricalTrafficPeakEvent:
    value_mbps: float | None
    sample_at_utc: str | None
    selected_source: str | None
    occurrence_count: int


@dataclass(frozen=True, slots=True)
class HistoricalTrafficBusiestBucket:
    status: str
    bucket_start_utc: str | None
    bucket_end_utc: str | None
    average_total_mbps: float | None
    selected_source: str | None
    occurrence_count: int
    method: str = "max_complete_history_bucket_total_mean.v1"
    tie_break_method: str = "earliest_bucket_start.v1"


@dataclass(frozen=True, slots=True)
class HistoricalTrafficBusiestHour:
    status: str
    window_start_utc: str | None
    window_end_utc: str | None
    duration_seconds: int
    average_total_mbps: float | None
    accepted_interval_seconds: float | None
    selected_source: str | None
    method: str = "max_complete_rolling_3600s_average_total_sample_hold.v1"
    average_method: str = "right_endpoint_sample_hold_time_weighted.v1"
    tie_break_method: str = "earliest_window_start.v1"


@dataclass(frozen=True, slots=True)
class HistoricalTrafficPeakLoad:
    status: str
    events: Mapping[str, HistoricalTrafficPeakEvent]
    busiest_bucket: HistoricalTrafficBusiestBucket
    busiest_hour: HistoricalTrafficBusiestHour
    metric_version: str = "network_traffic_peak_load.v1"
    unit: str = "Mbps"
    peak_value_method: str = "max_accepted_complete_site_sample.v1"
    peak_tie_break_method: str = "earliest_peak_sample_at.v1"
    sample_timestamp_semantics: str = "cycle_finished_at"

    def __post_init__(self) -> None:
        object.__setattr__(self, "events", MappingProxyType(dict(self.events)))


@dataclass(frozen=True, slots=True)
class HistoricalSiteTraffic:
    status: str
    range: HistoricalTrafficRange
    buckets: tuple[HistoricalTrafficBucket, ...]
    coverage: HistoricalTrafficCoverage
    quality: HistoricalTrafficQuality
    period_statistics: HistoricalTrafficPeriodStatistics | None = None
    peak_load: HistoricalTrafficPeakLoad | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "buckets", tuple(self.buckets))


@dataclass(frozen=True, slots=True)
class HomeActivityCoverage:
    coverage_from_utc: str | None
    coverage_through_utc: str | None
    covered_from_utc: str | None
    covered_through_utc: str | None
    fully_covered: bool
    status: str
    quality_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "quality_reasons", tuple(self.quality_reasons))


@dataclass(frozen=True, slots=True)
class HomeActivityVisits:
    value: int | None
    status: str
    cohort: str
    source_kind: str
    verified_visit_count: int | None
    integrity_anomaly_count: int
    coverage: HomeActivityCoverage
    earliest_persisted_evidence_at: str | None
    latest_persisted_evidence_at: str | None


@dataclass(frozen=True, slots=True)
class HomeActivityTraffic:
    bytes: int | None
    status: str
    estimated: bool
    attribution: str
    source_kind: str
    eligible_terminal_event_count: int
    included_fingerprint_count: int
    unmatched_included_event_count: int
    pending_event_count: int
    invalid_event_count: int
    missing_traffic_count: int
    missing_controller_time_count: int
    semantic_duplicate_count: int
    other_excluded_event_count: int
    reader_watermark_at: str | None
    ingestion_freshness: str
    coverage: HomeActivityCoverage
    earliest_persisted_evidence_at: str | None
    latest_persisted_evidence_at: str | None


@dataclass(frozen=True, slots=True)
class HomeActivityResult:
    evaluated_at_utc: str
    timezone: str
    guest_ssids: tuple[str, ...]
    range: Mapping[str, Any]
    authorized_visits: HomeActivityVisits
    traffic: HomeActivityTraffic
    next_site_midnight_utc: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "guest_ssids", tuple(self.guest_ssids))
        object.__setattr__(self, "range", freeze(self.range))
