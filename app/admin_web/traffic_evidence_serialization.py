"""Strict, identifier-free projections for consolidated Traffic evidence."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Mapping

from .traffic_network_ranges import TrafficNetworkRange


class TrafficEvidenceSerializationError(ValueError):
    """The aggregate or an owning product projection is unsafe to expose."""


CONTRACT_VERSION = "admin.traffic.evidence.v1"
PRODUCT_IDS = (
    "current", "history", "statistics", "peak", "aps", "apshare",
    "online_guests", "completed_sessions",
)
FAILURE_CATEGORIES = frozenset({
    "source_unavailable", "query_deadline", "integrity_unavailable",
    "runtime_unavailable", "unexpected",
})
COMPLETED_REASONS = frozenset({
    "invalid_elapsed", "gap_too_large", "authorization_boundary",
    "ssid_transition", "ssid_unproven", "continuity_frozen",
    "connection_reset", "continuity_unproven", "counter_missing",
    "counter_reset", "start_edge_uncovered", "end_edge_uncovered",
    "no_usable_interval", "observation_source_unavailable",
    "attribution_window_exceeds_supported_max",
})
EVIDENCE_KEYS = {
    "current": (
        "freshness_status", "freshness_reason", "observed_at",
        "newest_observed_at", "age_seconds", "source_skew_seconds", "complete",
        "primary_source", "selected_source", "selection_reason", "coverage_status",
        "total_ap_count", "valid_rate_ap_count", "missing_rate_ap_count",
        "stale_ap_count", "unavailable_ap_count", "reset_ap_count",
        "gap_rejected_ap_count", "no_baseline_ap_count",
        "source_unavailable_ap_count", "invalid_elapsed_ap_count",
    ),
    "history": (
        "status", "metric_version", "source_kind", "source_watermark_utc",
        "source_age_seconds", "bucket_count", "complete_bucket_count",
        "partial_bucket_count", "missing_bucket_count", "canonical_cycle_count",
        "complete_site_sample_count", "excluded_site_sample_count",
        "gap_bucket_count", "source_transition_count", "partial_cycle_count",
        "failed_cycle_count", "shutdown_cycle_count", "abandoned_cycle_count",
        "running_cycle_count", "no_baseline_count", "counter_reset_count",
        "gap_too_large_count", "invalid_elapsed_count", "source_unavailable_count",
        "source_skew_excluded_sample_count", "integrity_failure_count",
    ),
    "statistics": (
        "status", "metric_version", "average_method", "peak_method",
        "candidate_interval_count", "accepted_interval_count",
        "accepted_interval_seconds", "interval_coverage_ratio",
        "excluded_gap_interval_count", "excluded_source_transition_interval_count",
        "invalid_period_interval_count", "accepted_peak_sample_count",
        "leading_unweighted_seconds", "trailing_unweighted_seconds",
    ),
    "peak": (
        "status", "metric_version", "peak_value_method", "peak_tie_break_method",
        "sample_timestamp_semantics", "download_event_available",
        "upload_event_available", "total_event_available",
        "busiest_bucket_status", "busiest_hour_status",
    ),
    "aps": (
        "status", "metric_version", "population_method", "population_count",
        "current_population_count", "historical_population_count",
        "supported_max_ap_count", "returned_ap_count", "population_complete",
        "complete_ap_count", "partial_ap_count", "insufficient_data_ap_count",
    ),
    "apshare": (
        "status", "metric_version", "share_method", "temporal_method",
        "presence_method", "absence_method", "population_method",
        "population_count", "historical_population_count",
        "current_population_status", "current_population_count",
        "supported_max_ap_count", "returned_ap_count", "population_complete",
        "candidate_interval_count", "accepted_interval_count",
        "accepted_interval_seconds", "interval_coverage_ratio",
        "excluded_gap_interval_count", "excluded_source_transition_interval_count",
        "invalid_period_interval_count", "download_denominator_status",
        "upload_denominator_status", "total_denominator_status",
    ),
    "online_guests": (
        "status", "metric_version", "population_method", "rate_method",
        "baseline_method", "continuity_method", "connection_boundary_observation",
        "source_health_status", "source_health_reason", "rate_evidence_status",
        "population_complete", "scoped_client_row_count", "known_authorized_count",
        "unknown_auth_count", "population_count", "rate_valid_count",
        "rate_partial_count", "rate_unavailable_count", "current_capture_started_at",
        "baseline_capture_started_at", "elapsed_seconds",
    ),
    "completed_sessions": (
        "status", "metric_version", "session_method", "attribution_method",
        "continuity_method", "visits_source_status", "observations_source_status",
        "complete_count", "partial_count", "insufficient_data_count",
        "unavailable_count", "reason_counts",
    ),
}


def scope_current(evaluated_at: str) -> dict[str, Any]:
    return {"kind": "current_snapshot", "evaluated_at_utc": evaluated_at}


def scope_online(evaluated_at: str) -> dict[str, Any]:
    return {
        "kind": "current_authorized_population",
        "evaluated_at_utc": evaluated_at,
    }


def scope_historical(value: TrafficNetworkRange) -> dict[str, Any]:
    return {
        "kind": "historical_range",
        "range_id": value.id,
        "from_utc": value.from_utc,
        "to_utc": value.to_utc,
        "evaluated_at_utc": value.evaluated_at_utc,
    }


def scope_completed(
    value: TrafficNetworkRange,
    *,
    limit: int,
    returned_count: int,
    has_more: bool,
) -> dict[str, Any]:
    return {
        "kind": "completion_first_page",
        "range_id": value.id,
        "from_utc": value.from_utc,
        "to_utc": value.to_utc,
        "evaluated_at_utc": value.evaluated_at_utc,
        "limit": limit,
        "returned_count": returned_count,
        "has_more": has_more,
    }


def project_current(value: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = _mapping(value.get("snapshot"), "Current snapshot")
    source = _mapping(value.get("source_selection"), "Current source")
    coverage = _mapping(value.get("coverage"), "Current coverage")
    result = {
        "freshness_status": snapshot.get("freshness_status"),
        "freshness_reason": snapshot.get("freshness_reason"),
        "observed_at": snapshot.get("observed_at"),
        "newest_observed_at": snapshot.get("newest_observed_at"),
        "age_seconds": snapshot.get("age_seconds"),
        "source_skew_seconds": snapshot.get("source_skew_seconds"),
        "complete": snapshot.get("complete"),
        "primary_source": source.get("primary_source"),
        "selected_source": source.get("selected_source"),
        "selection_reason": source.get("selection_reason"),
        "coverage_status": coverage.get("coverage_status"),
    }
    for name in (
        "total_ap_count", "valid_rate_ap_count", "missing_rate_ap_count",
        "stale_ap_count", "unavailable_ap_count", "reset_ap_count",
        "gap_rejected_ap_count", "no_baseline_ap_count",
        "source_unavailable_ap_count", "invalid_elapsed_ap_count",
    ):
        result[name] = coverage.get(name)
    return _validate_current(result)


def project_history(value: Mapping[str, Any]) -> dict[str, Any]:
    coverage = _mapping(value.get("coverage"), "History coverage")
    quality = _mapping(value.get("quality"), "History quality")
    result = {
        "status": value.get("status"),
        "metric_version": _mapping(value.get("range"), "History range").get(
            "metric_version"
        ),
        "source_kind": value["range"].get("source_kind"),
    }
    for name in (
        "source_watermark_utc", "source_age_seconds", "bucket_count",
        "complete_bucket_count", "partial_bucket_count", "missing_bucket_count",
        "canonical_cycle_count", "complete_site_sample_count",
        "excluded_site_sample_count", "gap_bucket_count",
        "source_transition_count",
    ):
        result[name] = coverage.get(name)
    for name in (
        "partial_cycle_count", "failed_cycle_count", "shutdown_cycle_count",
        "abandoned_cycle_count", "running_cycle_count", "no_baseline_count",
        "counter_reset_count", "gap_too_large_count", "invalid_elapsed_count",
        "source_unavailable_count", "source_skew_excluded_sample_count",
        "integrity_failure_count",
    ):
        result[name] = quality.get(name)
    return _validate_history(result)


def project_statistics(value: Mapping[str, Any]) -> dict[str, Any]:
    statistics = _mapping(value.get("period_statistics"), "Statistics")
    interval = _mapping(statistics.get("interval_evidence"), "Statistics evidence")
    result = {
        "status": statistics.get("status"),
        "metric_version": statistics.get("metric_version"),
        "average_method": statistics.get("average_method"),
        "peak_method": statistics.get("peak_method"),
    }
    for name in (
        "candidate_interval_count", "accepted_interval_count",
        "accepted_interval_seconds", "interval_coverage_ratio",
        "excluded_gap_interval_count", "excluded_source_transition_interval_count",
        "invalid_period_interval_count", "accepted_peak_sample_count",
        "leading_unweighted_seconds", "trailing_unweighted_seconds",
    ):
        result[name] = interval.get(name)
    return _validate_statistics(result)


def project_peak(value: Mapping[str, Any]) -> dict[str, Any]:
    peak = _mapping(value.get("peak_load"), "Peak")
    events = _mapping(peak.get("events"), "Peak events")
    result = {
        "status": peak.get("status"),
        "metric_version": peak.get("metric_version"),
        "peak_value_method": peak.get("peak_value_method"),
        "peak_tie_break_method": peak.get("peak_tie_break_method"),
        "sample_timestamp_semantics": peak.get("sample_timestamp_semantics"),
        "download_event_available": _event_available(events.get("download")),
        "upload_event_available": _event_available(events.get("upload")),
        "total_event_available": _event_available(events.get("total")),
        "busiest_bucket_status": _mapping(
            peak.get("busiest_bucket"), "Peak bucket"
        ).get("status"),
        "busiest_hour_status": _mapping(
            peak.get("busiest_hour"), "Peak hour"
        ).get("status"),
    }
    return _validate_peak(result)


def project_aps(value: Mapping[str, Any]) -> dict[str, Any]:
    aps = _mapping(value.get("ap_traffic"), "AP Traffic")
    population = _mapping(aps.get("population"), "AP population")
    items = _list(aps.get("items"), "AP items")
    counts = {"complete": 0, "partial": 0, "insufficient_data": 0}
    for item in items:
        status = _mapping(item, "AP item").get("status")
        if status not in counts:
            raise TrafficEvidenceSerializationError("AP item status is invalid")
        counts[status] += 1
    result = {
        "status": aps.get("status"),
        "metric_version": aps.get("metric_version"),
        "population_method": population.get("population_method"),
        "population_count": population.get("population_count"),
        "current_population_count": population.get("current_population_count"),
        "historical_population_count": population.get("historical_population_count"),
        "supported_max_ap_count": population.get("supported_max_ap_count"),
        "returned_ap_count": population.get("returned_ap_count"),
        "population_complete": population.get("population_complete"),
        "complete_ap_count": counts["complete"],
        "partial_ap_count": counts["partial"],
        "insufficient_data_ap_count": counts["insufficient_data"],
    }
    return _validate_aps(result)


def project_apshare(value: Mapping[str, Any]) -> dict[str, Any]:
    share = _mapping(value.get("ap_traffic_share"), "AP Share")
    population = _mapping(share.get("population"), "AP Share population")
    coverage = _mapping(share.get("coverage"), "AP Share coverage")
    denominators = _mapping(share.get("denominators"), "AP Share denominators")
    result = {
        "status": share.get("status"),
        "metric_version": share.get("metric_version"),
        "share_method": share.get("share_method"),
        "temporal_method": share.get("temporal_method"),
        "presence_method": share.get("presence_method"),
        "absence_method": share.get("absence_method"),
        "population_method": population.get("population_method"),
        "population_count": population.get("population_count"),
        "historical_population_count": population.get("historical_population_count"),
        "current_population_status": population.get("current_population_status"),
        "current_population_count": population.get("current_population_count"),
        "supported_max_ap_count": population.get("supported_max_ap_count"),
        "returned_ap_count": population.get("returned_ap_count"),
        "population_complete": population.get("population_complete"),
    }
    for name in (
        "candidate_interval_count", "accepted_interval_count",
        "accepted_interval_seconds", "interval_coverage_ratio",
        "excluded_gap_interval_count", "excluded_source_transition_interval_count",
        "invalid_period_interval_count",
    ):
        result[name] = coverage.get(name)
    for name in ("download", "upload", "total"):
        result[f"{name}_denominator_status"] = denominators.get(f"{name}_status")
    return _validate_apshare(result)


def project_online(value: Mapping[str, Any]) -> dict[str, Any]:
    names = (
        "status", "metric_version", "population_method", "rate_method",
        "baseline_method", "continuity_method", "connection_boundary_observation",
        "source_health_status", "source_health_reason", "rate_evidence_status",
        "population_complete", "scoped_client_row_count", "known_authorized_count",
        "unknown_auth_count", "population_count", "rate_valid_count",
        "rate_partial_count", "rate_unavailable_count",
        "current_capture_started_at", "baseline_capture_started_at", "elapsed_seconds",
    )
    return _validate_online({name: value.get(name) for name in names})


def project_completed(value: Mapping[str, Any]) -> dict[str, Any]:
    source = _mapping(value.get("source_health"), "Completed source")
    items = _list(value.get("items"), "Completed items")
    statuses = {"complete": 0, "partial": 0, "insufficient_data": 0, "unavailable": 0}
    reasons: dict[str, int] = {}
    for item in items:
        item = _mapping(item, "Completed item")
        status = item.get("traffic_evidence_status")
        if status not in statuses:
            raise TrafficEvidenceSerializationError("Completed status is invalid")
        statuses[status] += 1
        item_reasons = item.get("evidence_reason_codes")
        if not isinstance(item_reasons, list) or any(
            reason not in COMPLETED_REASONS for reason in item_reasons
        ):
            raise TrafficEvidenceSerializationError("Completed reason is invalid")
        for reason in item_reasons:
            reasons[reason] = reasons.get(reason, 0) + 1
    result = {
        "status": value.get("status"),
        "metric_version": value.get("metric_version"),
        "session_method": value.get("session_method"),
        "attribution_method": value.get("attribution_method"),
        "continuity_method": value.get("continuity_method"),
        "visits_source_status": source.get("visits"),
        "observations_source_status": source.get("observations"),
        "complete_count": statuses["complete"],
        "partial_count": statuses["partial"],
        "insufficient_data_count": statuses["insufficient_data"],
        "unavailable_count": statuses["unavailable"],
        "reason_counts": dict(sorted(reasons.items())),
    }
    return _validate_completed(result)


def serialize_traffic_evidence(
    value: Mapping[str, Any], *, resolved_range: TrafficNetworkRange,
) -> dict[str, Any]:
    value = _mapping(value, "Evidence result")
    if set(value) != {"contract_version", "evaluated_at_utc", "evidence_range", "products"}:
        raise TrafficEvidenceSerializationError("Evidence result keys are invalid")
    if value.get("contract_version") != CONTRACT_VERSION:
        raise TrafficEvidenceSerializationError("Evidence contract is invalid")
    if value.get("evaluated_at_utc") != resolved_range.evaluated_at_utc:
        raise TrafficEvidenceSerializationError("Evidence evaluation is invalid")
    expected_range = {
        "id": resolved_range.id,
        "from_utc": resolved_range.from_utc,
        "to_utc": resolved_range.to_utc,
    }
    if value.get("evidence_range") != expected_range:
        raise TrafficEvidenceSerializationError("Evidence range is invalid")
    products = _mapping(value.get("products"), "Evidence products")
    if tuple(products) != PRODUCT_IDS or set(products) != set(PRODUCT_IDS):
        raise TrafficEvidenceSerializationError("Evidence products are invalid")
    projected = {
        product_id: _validate_wrapper(product_id, products[product_id], resolved_range)
        for product_id in PRODUCT_IDS
    }
    return {
        "contract_version": CONTRACT_VERSION,
        "evaluated_at_utc": resolved_range.evaluated_at_utc,
        "evidence_range": expected_range,
        "products": projected,
    }


def _validate_wrapper(product_id, raw, resolved_range):
    value = _mapping(raw, "Evidence product")
    exact = {"product_id", "exposure_status", "delivery_status", "scope", "evidence", "failure_category"}
    if set(value) != exact or value.get("product_id") != product_id:
        raise TrafficEvidenceSerializationError("Evidence wrapper is invalid")
    exposure = value.get("exposure_status")
    delivery = value.get("delivery_status")
    failure = value.get("failure_category")
    if exposure not in {"enabled", "disabled"} or delivery not in {"available", "failed", "not_attempted"}:
        raise TrafficEvidenceSerializationError("Evidence delivery is invalid")
    if exposure == "disabled":
        valid = delivery == "not_attempted" and value.get("evidence") is None and failure is None
    elif delivery == "available":
        evidence = value.get("evidence")
        valid = isinstance(evidence, Mapping) and failure is None
    elif delivery == "failed":
        valid = value.get("evidence") is None and failure in FAILURE_CATEGORIES
    else:
        valid = False
    if not valid:
        raise TrafficEvidenceSerializationError("Evidence wrapper shape is invalid")
    _validate_scope(
        product_id,
        value.get("scope"),
        resolved_range,
        delivery_status=delivery,
    )
    if delivery == "available":
        evidence = value["evidence"]
        if set(evidence) != set(EVIDENCE_KEYS[product_id]):
            raise TrafficEvidenceSerializationError("Product evidence keys are invalid")
        validators = {
            "current": _validate_current,
            "history": _validate_history,
            "statistics": _validate_statistics,
            "peak": _validate_peak,
            "aps": _validate_aps,
            "apshare": _validate_apshare,
            "online_guests": _validate_online,
            "completed_sessions": _validate_completed,
        }
        validated = validators[product_id](dict(evidence))
        if product_id == "completed_sessions" and sum(
            validated[name] for name in (
                "complete_count", "partial_count", "insufficient_data_count",
                "unavailable_count",
            )
        ) != value["scope"]["returned_count"]:
            raise TrafficEvidenceSerializationError("Completed page count is invalid")
    return dict(value)


def _validate_scope(product_id, raw, value, *, delivery_status):
    if product_id == "completed_sessions":
        if delivery_status != "available":
            if raw is not None:
                raise TrafficEvidenceSerializationError("Evidence scope is invalid")
            return
        scope = _mapping(raw, "Completed scope")
        if set(scope) != {
            "kind", "range_id", "from_utc", "to_utc", "evaluated_at_utc",
            "limit", "returned_count", "has_more",
        }:
            raise TrafficEvidenceSerializationError("Evidence scope is invalid")
        expected = {
            "kind": "completion_first_page",
            "range_id": value.id,
            "from_utc": value.from_utc,
            "to_utc": value.to_utc,
            "evaluated_at_utc": value.evaluated_at_utc,
        }
        if (
            any(scope.get(key) != item for key, item in expected.items())
            or scope.get("limit") != 100
            or type(scope.get("has_more")) is not bool
        ):
            raise TrafficEvidenceSerializationError("Evidence scope is invalid")
        _count(scope.get("returned_count"))
        if (
            scope["returned_count"] > scope["limit"]
            or (scope["has_more"] and scope["returned_count"] == 0)
        ):
            raise TrafficEvidenceSerializationError("Evidence scope is invalid")
        return
    expected = (
        scope_current(value.evaluated_at_utc) if product_id == "current"
        else scope_online(value.evaluated_at_utc) if product_id == "online_guests"
        else scope_historical(value)
    )
    if raw != expected:
        raise TrafficEvidenceSerializationError("Evidence scope is invalid")


def _validate_current(value):
    if value["freshness_status"] not in {"fresh", "stale", "unavailable"} or value["freshness_reason"] not in {"within_freshness_window", "within_stale_window", "age_exceeded", "clock_anomaly", "no_complete_snapshot", "source_unavailable"} or value["coverage_status"] not in {"complete", "partial", "none"}:
        raise TrafficEvidenceSerializationError("Current status is invalid")
    if value["primary_source"] != "wired" or value["selected_source"] not in {"wired", "lan", None} or value["selection_reason"] not in {"no_complete_snapshot", "empty_population", "primary_full_coverage", "fallback_full_coverage", "fallback_higher_coverage", "primary_preferred_tie_or_higher"} or type(value["complete"]) is not bool:
        raise TrafficEvidenceSerializationError("Current source is invalid")
    _optional_utc(value["observed_at"]); _optional_utc(value["newest_observed_at"])
    _optional_number(value["age_seconds"]); _optional_number(value["source_skew_seconds"])
    for key in value.keys() - {"freshness_status", "freshness_reason", "observed_at", "newest_observed_at", "age_seconds", "source_skew_seconds", "complete", "primary_source", "selected_source", "selection_reason", "coverage_status"}:
        _count(value[key])
    return value


def _validate_history(value):
    if value["status"] not in {"ok", "partial", "insufficient_data"} or value["metric_version"] != "network_traffic_history.v1" or value["source_kind"] != "observation_ap_dynamic":
        raise TrafficEvidenceSerializationError("History contract is invalid")
    _optional_number(value["source_age_seconds"])
    _optional_utc(value["source_watermark_utc"])
    for key, item in value.items():
        if key.endswith("_count") or key == "bucket_count": _count(item)
    return value


def _validate_statistics(value):
    expected = ("network_traffic_period_statistics.v1", "right_endpoint_sample_hold_time_weighted.v1", "max_accepted_complete_site_sample.v1")
    if value["status"] not in {"ok", "partial", "insufficient_data"} or (value["metric_version"], value["average_method"], value["peak_method"]) != expected:
        raise TrafficEvidenceSerializationError("Statistics contract is invalid")
    for key, item in value.items():
        if key.endswith("_count"): _count(item)
        elif key.endswith("_seconds") or key == "interval_coverage_ratio": _number(item)
    return value


def _validate_peak(value):
    if value["status"] not in {"ok", "partial", "insufficient_data"} or value["metric_version"] != "network_traffic_peak_load.v1" or value["peak_value_method"] != "max_accepted_complete_site_sample.v1" or value["peak_tie_break_method"] != "earliest_peak_sample_at.v1" or value["sample_timestamp_semantics"] != "cycle_finished_at":
        raise TrafficEvidenceSerializationError("Peak contract is invalid")
    if any(type(value[name]) is not bool for name in ("download_event_available", "upload_event_available", "total_event_available")) or value["busiest_bucket_status"] not in {"ok", "insufficient_data"} or value["busiest_hour_status"] not in {"ok", "insufficient_data"}:
        raise TrafficEvidenceSerializationError("Peak evidence is invalid")
    return value


def _validate_aps(value):
    if value["status"] not in {"ok", "partial", "insufficient_data", "unsupported_population"} or value["metric_version"] != "network_traffic_by_ap.v1" or value["population_method"] != "current_union_historical_validated.v1" or value["supported_max_ap_count"] != 12 or type(value["population_complete"]) is not bool:
        raise TrafficEvidenceSerializationError("AP contract is invalid")
    for key, item in value.items():
        if key.endswith("_count"): _count(item)
    if value["complete_ap_count"] + value["partial_ap_count"] + value["insufficient_data_ap_count"] != value["returned_ap_count"]:
        raise TrafficEvidenceSerializationError("AP status counts are invalid")
    return value


def _validate_apshare(value):
    constants = {
        "metric_version": "network_traffic_ap_share.v1",
        "share_method": "accepted_site_interval_integrated_ap_contribution_ratio.v1",
        "temporal_method": "right_endpoint_sample_hold_time_weighted.v1",
        "presence_method": "accepted_selected_source_historical_presence_in_range.v1",
        "absence_method": "proven_population_member_absent_from_trusted_complete_site_sample_zero_contribution.v1",
        "population_method": "current_union_historical_validated.v1",
    }
    if value["status"] not in {"ok", "partial", "insufficient_data", "unsupported_population"} or any(value[key] != expected for key, expected in constants.items()) or value["supported_max_ap_count"] != 12:
        raise TrafficEvidenceSerializationError("AP Share contract is invalid")
    if value["current_population_status"] not in {"available", "unavailable"} or type(value["population_complete"]) is not bool:
        raise TrafficEvidenceSerializationError("AP Share population is invalid")
    for key, item in value.items():
        if key.endswith("_count") and key != "current_population_count": _count(item)
    if value["current_population_count"] is not None: _count(value["current_population_count"])
    for key in ("accepted_interval_seconds", "interval_coverage_ratio"): _number(value[key])
    if any(value[f"{name}_denominator_status"] not in {"positive", "zero_traffic", "insufficient_data"} for name in ("download", "upload", "total")):
        raise TrafficEvidenceSerializationError("AP Share denominator is invalid")
    return value


def _validate_online(value):
    constants = {
        "metric_version": "network_traffic_online_guest_current_rate.v1",
        "population_method": "fresh_complete_current_state_authorized_guest_scope.v1",
        "rate_method": "current_connection_counter_delta_interval_average.v1",
        "baseline_method": "nearest_previous_complete_same_site_scope_cycle.v1",
        "continuity_method": "omada_controller_connection_progress_v1",
        "connection_boundary_observation": "sampled_current_state_evidence_v1",
    }
    if value["status"] not in {"ok", "partial", "insufficient_data", "stale", "unavailable", "unsupported_population"} or any(value[key] != expected for key, expected in constants.items()):
        raise TrafficEvidenceSerializationError("Online contract is invalid")
    if value["source_health_status"] not in {"healthy", "degraded", "stale", "unavailable"} or value["source_health_reason"] not in {"within_freshness_window", "newer_degraded_attempt", "older_than_freshness_window", "older_than_unavailable_threshold", "clock_anomaly", "no_complete_snapshot"} or value["rate_evidence_status"] not in {"complete", "partial", "insufficient_data", "not_applicable"} or type(value["population_complete"]) is not bool:
        raise TrafficEvidenceSerializationError("Online evidence is invalid")
    for key in ("scoped_client_row_count", "known_authorized_count", "unknown_auth_count", "population_count", "rate_valid_count", "rate_partial_count", "rate_unavailable_count"):
        if value[key] is not None: _count(value[key])
    _optional_number(value["elapsed_seconds"])
    _optional_utc(value["current_capture_started_at"])
    _optional_utc(value["baseline_capture_started_at"])
    return value


def _validate_completed(value):
    constants = {
        "metric_version": "network_traffic_completed_guest_session_observed_bytes.v1",
        "session_method": "closed_visit_completion_cohort.v1",
        "attribution_method": "visit_window_observation_counter_interval_sum.v1",
        "continuity_method": "observation_uptime_progress.v1",
    }
    if value["status"] not in {"ok", "partial", "insufficient_data", "unavailable"} or any(value[key] != expected for key, expected in constants.items()):
        raise TrafficEvidenceSerializationError("Completed contract is invalid")
    if value["visits_source_status"] not in {"healthy", "unavailable"} or value["observations_source_status"] not in {"healthy", "unavailable", "not_required"}:
        raise TrafficEvidenceSerializationError("Completed source is invalid")
    for key in ("complete_count", "partial_count", "insufficient_data_count", "unavailable_count"): _count(value[key])
    reasons = _mapping(value["reason_counts"], "Completed reasons")
    if any(reason not in COMPLETED_REASONS for reason in reasons):
        raise TrafficEvidenceSerializationError("Completed reason is invalid")
    for item in reasons.values(): _count(item)
    return value


def _event_available(value):
    event = _mapping(value, "Peak event")
    available = event.get("value_mbps") is not None
    if available != (event.get("sample_at_utc") is not None):
        raise TrafficEvidenceSerializationError("Peak event is invalid")
    return available


def _mapping(value, name):
    if not isinstance(value, Mapping):
        raise TrafficEvidenceSerializationError(f"{name} is invalid")
    return value


def _list(value, name):
    if not isinstance(value, list):
        raise TrafficEvidenceSerializationError(f"{name} is invalid")
    return value


def _count(value):
    if type(value) is not int or value < 0:
        raise TrafficEvidenceSerializationError("Evidence count is invalid")
    return value


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise TrafficEvidenceSerializationError("Evidence number is invalid")
    return float(value)


def _optional_number(value):
    if value is not None: _number(value)
    return value


def _optional_utc(value):
    if value is None:
        return None
    if not isinstance(value, str) or not value.endswith("Z"):
        raise TrafficEvidenceSerializationError("Evidence timestamp is invalid")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError as exc:
        raise TrafficEvidenceSerializationError("Evidence timestamp is invalid") from exc
    return value
