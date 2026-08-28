"""Strict product-safe serialization boundary for Home AP-24H."""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from typing import Any

from app.analytics.home_ap_24h import (
    BUCKET_COUNT,
    BUCKET_SECONDS,
    CONTRACT_VERSION,
    MAX_PAGE_SIZE,
    WINDOW_SECONDS,
)
from app.analytics.validation import format_utc, parse_utc
from app.common.mac import format_mac_colon


class HomeAp24SerializationError(ValueError):
    pass


_STATUS = frozenset({"operational", "degraded", "unavailable", "unknown"})
_COVERAGE = frozenset({"complete", "partial", "insufficient_data"})
_FRESHNESS = frozenset({"fresh", "stale", "unavailable"})
_BLOCK_REASONS = frozenset({
    None, "no_historical_evidence", "source_partially_unavailable",
    "source_evidence_degraded",
})
_CURRENT_REASONS = frozenset({
    "fresh_online_evidence", "controller_reported_offline",
    "controller_status_other", "controller_status_unknown",
    "not_in_complete_inventory", "current_state_source_gap",
    "no_current_state_evidence", "source_unavailable",
})
_HISTORY_REASONS = frozenset({
    "operational_history", "mixed_operational_unavailable",
    "controller_reported_offline", "history_evidence_incomplete",
    "unknown_state_evidence", "no_historical_evidence",
    "current_state_source_gap", "source_unavailable",
})
_OBSERVATION_REASONS = frozenset({
    None, "ap_local_evidence_degraded", "observation_source_gap",
    "no_observation_evidence", "source_unavailable",
})
_BUCKET_STATE_REASONS = frozenset({
    "before_first_evidence", "current_state_source_gap",
    "not_in_complete_inventory", "fresh_online_evidence",
    "controller_reported_offline", "controller_status_other",
    "controller_status_unknown", "mixed_state_within_bucket",
    "operational_evidence", "source_unavailable",
})
_OBSERVATION_BUCKET_REASONS = frozenset({
    "overview_unobserved", "wired_uplink_unobserved",
    "lan_traffic_unobserved", "radios_unobserved",
    "rate_quality_degraded", "observation_source_gap", "source_unavailable",
})


def serialize_home_ap_24h(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("contract_version") != CONTRACT_VERSION:
        raise HomeAp24SerializationError("AP-24H result is invalid")
    if value.get("block_status") not in _STATUS or value.get("block_reason") not in _BLOCK_REASONS:
        raise HomeAp24SerializationError("AP-24H block status is invalid")
    window = value.get("window")
    items = value.get("items")
    summary = value.get("summary")
    sources = value.get("sources")
    page = value.get("page")
    if not all(isinstance(item, dict) for item in (window, summary, sources, page)) or not isinstance(items, list):
        raise HomeAp24SerializationError("AP-24H result shape is invalid")
    if window.get("kind") != "rolling_24h" or window.get("bucket_seconds") != 900 or window.get("bucket_count") != BUCKET_COUNT:
        raise HomeAp24SerializationError("AP-24H window is invalid")
    evaluated = _timestamp(window.get("evaluated_at_utc"))
    start = _timestamp(window.get("from_utc"))
    end = _timestamp(window.get("to_utc"))
    if evaluated != end or end - start != timedelta(seconds=WINDOW_SECONDS):
        raise HomeAp24SerializationError("AP-24H window is invalid")
    if set(sources) != {"current_state", "observations"}:
        raise HomeAp24SerializationError("AP-24H source set is invalid")
    for source in sources.values():
        if not isinstance(source, dict) or source.get("status") not in _STATUS:
            raise HomeAp24SerializationError("AP-24H source is invalid")
        version = source.get("schema_version")
        if version not in {None, 1} or (version is None) != (source["status"] == "unavailable"):
            raise HomeAp24SerializationError("AP-24H source is invalid")
        for field in ("complete_cycle_count", "partial_cycle_count", "failed_cycle_count"):
            _count(source.get(field))
        _optional_count(source.get("max_gap_seconds"))
        _optional_timestamp(source.get("first_evidence_at"))
        _optional_timestamp(source.get("last_evidence_at"))
        reasons = source.get("reason_codes", [])
        if not isinstance(reasons, list) or len(reasons) != len(set(reasons)) or any(
            reason != "observation_cycle_capacity_exceeded" for reason in reasons
        ):
            raise HomeAp24SerializationError("AP-24H source is invalid")
    _summary(summary)
    if type(page.get("limit")) is not int or not 1 <= page["limit"] <= MAX_PAGE_SIZE:
        raise HomeAp24SerializationError("AP-24H page is invalid")
    if type(page.get("has_more")) is not bool or len(items) > page["limit"]:
        raise HomeAp24SerializationError("AP-24H page is invalid")
    for item in items:
        _item(item, start, end)
    if "coverage_ratio" in repr(value) or "uptime_percent" in repr(value):
        raise HomeAp24SerializationError("AP-24H forbidden metric")
    result = deepcopy(value)
    result["page"].pop("has_more", None)
    return result


def _item(item: object, window_start, window_end) -> None:
    if not isinstance(item, dict):
        raise HomeAp24SerializationError("AP identity is invalid")
    try:
        canonical_mac = format_mac_colon(item.get("ap_mac"))
    except (TypeError, ValueError) as exc:
        raise HomeAp24SerializationError("AP identity is invalid") from exc
    if canonical_mac != item.get("ap_mac"):
        raise HomeAp24SerializationError("AP identity is invalid")
    if item.get("identity_source") not in {None, "current_state", "observations"}:
        raise HomeAp24SerializationError("AP identity is invalid")
    if any(value is not None and not isinstance(value, str) for value in (item.get("name"), item.get("model"))):
        raise HomeAp24SerializationError("AP identity is invalid")
    current = item.get("current")
    history = item.get("history")
    observation = item.get("observation_quality")
    if not isinstance(current, dict) or current.get("status") not in _STATUS:
        raise HomeAp24SerializationError("AP current axis is invalid")
    if current.get("reason_code") not in _CURRENT_REASONS or current.get("freshness_status") not in _FRESHNESS:
        raise HomeAp24SerializationError("AP current axis is invalid")
    _optional_timestamp(current.get("observed_at"))
    if not isinstance(history, dict) or history.get("status") not in _STATUS:
        raise HomeAp24SerializationError("AP history axis is invalid")
    if history.get("reason_code") not in _HISTORY_REASONS or history.get("coverage_status") not in _COVERAGE:
        raise HomeAp24SerializationError("AP history axis is invalid")
    for field in (
        "authoritative_sample_count", "operational_seconds", "unavailable_seconds",
        "unknown_evidence_seconds", "short_history_seconds",
    ):
        _count(history.get(field))
    _optional_count(history.get("max_gap_seconds"))
    for field in ("history_eligible_from", "first_evidence_at", "last_evidence_at"):
        _optional_timestamp(history.get(field))
    if sum(history[field] for field in (
        "operational_seconds", "unavailable_seconds", "unknown_evidence_seconds",
        "short_history_seconds",
    )) > WINDOW_SECONDS:
        raise HomeAp24SerializationError("AP history duration is invalid")
    if history.get("current_vs_24h") not in {
        "consistent_with_24h_online_evidence", "current_less_certain_than_24h",
        "history_insufficient", "historical_state_mixed_or_unknown",
    }:
        raise HomeAp24SerializationError("AP history comparison is invalid")
    if not isinstance(observation, dict) or observation.get("status") not in _STATUS:
        raise HomeAp24SerializationError("AP Observation axis is invalid")
    if observation.get("reason_code") not in _OBSERVATION_REASONS:
        raise HomeAp24SerializationError("AP Observation axis is invalid")
    for field in ("complete_sample_count", "diagnostic_partial_sample_count"):
        _count(observation.get(field))
    section_counts = observation.get("section_problem_counts")
    if not isinstance(section_counts, dict) or set(section_counts) != {
        "overview", "wired_uplink", "lan_traffic", "radios"
    }:
        raise HomeAp24SerializationError("AP Observation axis is invalid")
    for value in section_counts.values():
        _count(value)
    timeline = item.get("timeline")
    if not isinstance(timeline, list) or len(timeline) != BUCKET_COUNT:
        raise HomeAp24SerializationError("AP timeline is invalid")
    expected_start = window_start
    for bucket in timeline:
        if not isinstance(bucket, dict) or bucket.get("ap_state") not in _STATUS or bucket.get("observation_quality") not in _STATUS:
            raise HomeAp24SerializationError("AP timeline bucket is invalid")
        bucket_start = _timestamp(bucket.get("from_utc"))
        bucket_end = _timestamp(bucket.get("to_utc"))
        if bucket_start != expected_start or bucket_end - bucket_start != timedelta(seconds=BUCKET_SECONDS):
            raise HomeAp24SerializationError("AP timeline boundary is invalid")
        expected_start = bucket_end
        if bucket.get("ap_state_reason") not in _BUCKET_STATE_REASONS:
            raise HomeAp24SerializationError("AP timeline state reason is invalid")
        reasons = bucket.get("observation_reason_codes")
        if not isinstance(reasons, list) or len(reasons) != len(set(reasons)) or any(
            reason not in _OBSERVATION_BUCKET_REASONS for reason in reasons
        ):
            raise HomeAp24SerializationError("AP timeline Observation reason is invalid")
        for field in (
            "operational_seconds", "unavailable_seconds", "unknown_evidence_seconds",
            "short_history_seconds", "authoritative_state_sample_count",
            "complete_observation_sample_count", "diagnostic_partial_observation_sample_count",
        ):
            if type(bucket.get(field)) is not int or bucket[field] < 0:
                raise HomeAp24SerializationError("AP timeline count is invalid")
        if sum(bucket[field] for field in (
            "operational_seconds", "unavailable_seconds", "unknown_evidence_seconds",
            "short_history_seconds",
        )) != BUCKET_SECONDS:
            raise HomeAp24SerializationError("AP timeline duration is invalid")
    if expected_start != window_end:
        raise HomeAp24SerializationError("AP timeline boundary is invalid")


def _summary(value: dict[str, Any]) -> None:
    expected = {
        "ap_count_in_window", "current", "history", "observation_quality",
        "short_history_ap_count", "status_gap_ap_count",
        "observation_problem_ap_count",
    }
    if set(value) != expected:
        raise HomeAp24SerializationError("AP-24H summary is invalid")
    population = _count(value["ap_count_in_window"])
    for axis_name in ("current", "history", "observation_quality"):
        axis = value[axis_name]
        if not isinstance(axis, dict) or set(axis) != _STATUS:
            raise HomeAp24SerializationError("AP-24H summary is invalid")
        counts = [_count(axis[status]) for status in _STATUS]
        if sum(counts) != population:
            raise HomeAp24SerializationError("AP-24H summary is invalid")
    for field in (
        "short_history_ap_count", "status_gap_ap_count", "observation_problem_ap_count"
    ):
        if _count(value[field]) > population:
            raise HomeAp24SerializationError("AP-24H summary is invalid")


def _count(value: object) -> int:
    if type(value) is not int or value < 0:
        raise HomeAp24SerializationError("AP-24H count is invalid")
    return value


def _optional_count(value: object) -> int | None:
    if value is None:
        return None
    return _count(value)


def _timestamp(value: object):
    if not isinstance(value, str):
        raise HomeAp24SerializationError("AP-24H timestamp is invalid")
    try:
        parsed = parse_utc(value, "timestamp")
    except Exception as exc:
        raise HomeAp24SerializationError("AP-24H timestamp is invalid") from exc
    if format_utc(parsed) != value:
        raise HomeAp24SerializationError("AP-24H timestamp is not canonical")
    return parsed


def _optional_timestamp(value: object):
    return None if value is None else _timestamp(value)
