"""Explicit, minimized serializers for Admin Home Traffic v1."""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any

from app.analytics.models import (
    CurrentApTrafficPage, CurrentSiteTraffic, CoverageAwareCurrentSiteTrafficV1,
    CoverageAwareCurrentApTrafficPageV1,
)
from collections.abc import Mapping
from app.analytics.validation import AnalyticsQueryValidationError, format_utc, parse_utc


class CurrentTrafficSerializationError(ValueError):
    """A source result cannot be exposed through the Admin API."""


_SOURCES = frozenset({"wired", "lan"})
_FRESHNESS = frozenset({"fresh", "stale", "unavailable"})
_FRESHNESS_REASONS = frozenset({
    "within_freshness_window", "within_stale_window", "age_exceeded",
    "clock_anomaly", "no_complete_snapshot", "source_unavailable",
})
_COVERAGE = frozenset({"complete", "partial", "none"})
_COVERAGE_REASONS = frozenset({
    "missing_direction", "missing_pair", "temporal_skew", "no_valid_rate",
    "empty_population",
})
_SELECTION_REASONS = frozenset({
    "no_complete_snapshot", "empty_population", "primary_full_coverage",
    "fallback_full_coverage", "fallback_higher_coverage",
    "primary_preferred_tie_or_higher",
})
_RATE_REASONS = frozenset({
    "ok", "no_baseline", "counter_reset", "gap_too_large",
    "invalid_elapsed", "source_unavailable",
})
_RATE_STATUS = frozenset({"valid", "partial", "unavailable"})
_LATEST_STATES = frozenset({"none", "running", "completed", "abandoned"})
_LATEST_RESULTS = frozenset({"success", "partial", "failed", "shutdown"})
_MAC_PATTERN = re.compile(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}")

_PARTIAL_REASONS = frozenset({
    "complete_installed_population", "complete_confirmed_online_population", "confirmed_offline_excluded",
    "online_measurement_missing", "other_status_measurement_missing", "unknown_status_measurement_missing",
    "status_evidence_stale", "status_evidence_unavailable", "population_mismatch", "no_valid_rate",
    "missing_direction", "no_baseline", "counter_reset", "gap_too_large", "source_unavailable",
    "invalid_elapsed", "temporal_skew", "source_cycle_partial", "source_cycle_failed",
    "source_integrity_unavailable", "status_measurement_conflict", "clock_anomaly", "age_exceeded",
})
_PARTIAL_SELECTION = frozenset({
    "no_complete_snapshot", "primary_full_observation_coverage", "fallback_full_observation_coverage",
    "primary_full_online_coverage", "fallback_full_online_coverage", "fallback_higher_measured_coverage",
    "primary_preferred_tie_or_higher",
})


def _plain(value):
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def _closed(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys.split()):
        raise CurrentTrafficSerializationError("partial current fields are invalid")


def serialize_partial_current_summary(value, site_id):
    try:
        return _serialize_partial_current_summary(value, site_id)
    except CurrentTrafficSerializationError:
        raise
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise CurrentTrafficSerializationError("partial current source is malformed") from exc


def _serialize_partial_current_summary(value, site_id):
    if not isinstance(value, CoverageAwareCurrentSiteTrafficV1) or value.site_id != site_id:
        raise CurrentTrafficSerializationError("partial current identity is invalid")
    if value.metric_version != "network_traffic_current_partial_coverage.v1":
        raise CurrentTrafficSerializationError("partial metric is invalid")
    if {"complete_installed": "installed", "complete_online_population": "confirmed_online",
        "partial_measured": "measured_only", "unavailable": "none"}.get(value.measurement_state) != value.population_scope:
        raise CurrentTrafficSerializationError("partial population state is invalid")
    _timestamp(value.evaluated_at_utc)
    snapshot, coverage, selection, status, traffic = map(_plain, (
        value.snapshot, value.coverage, value.source_selection, value.status_evidence, value.traffic,
    ))
    _closed(snapshot, "cycle_id started_at finished_at source_result source_complete latest_attempt_state latest_attempt_result latest_attempt_at using_previous_snapshot observed_at newest_observed_at age_seconds source_skew_seconds freshness_status freshness_reason")
    for key in ("started_at", "finished_at", "latest_attempt_at", "observed_at", "newest_observed_at"):
        _timestamp(snapshot[key], optional=True)
    if snapshot["cycle_id"] is not None and (not isinstance(snapshot["cycle_id"], str) or not 1 <= len(snapshot["cycle_id"]) <= 128):
        raise CurrentTrafficSerializationError("partial cycle identity is invalid")
    if snapshot["cycle_id"] is None:
        if any(snapshot[key] is not None for key in ("started_at", "finished_at", "source_result")) or snapshot["source_complete"]:
            raise CurrentTrafficSerializationError("missing partial cycle has facts")
    elif snapshot["started_at"] is None or snapshot["finished_at"] is None or snapshot["started_at"] > snapshot["finished_at"]:
        raise CurrentTrafficSerializationError("partial cycle interval is invalid")
    for key in ("age_seconds", "source_skew_seconds"):
        _number(snapshot[key], optional=True, nonnegative=True)
    if snapshot["freshness_status"] not in _FRESHNESS or snapshot["freshness_reason"] not in _FRESHNESS_REASONS:
        raise CurrentTrafficSerializationError("partial freshness is invalid")
    if type(snapshot["source_complete"]) is not bool or type(snapshot["using_previous_snapshot"]) is not bool:
        raise CurrentTrafficSerializationError("partial snapshot is invalid")
    if snapshot["source_result"] not in {None, "success", "partial"}:
        raise CurrentTrafficSerializationError("partial source result is invalid")
    _latest_attempt(snapshot["latest_attempt_state"], snapshot["latest_attempt_result"], snapshot["latest_attempt_at"])
    _closed(selection, "primary_source selected_source selection_reason source_mixing_allowed wired_pair_valid_ap_count lan_pair_valid_ap_count")
    if (selection["primary_source"] != "wired" or selection["selected_source"] not in _SOURCES | {None}
        or selection["selection_reason"] not in _PARTIAL_SELECTION or selection["source_mixing_allowed"] is not False):
        raise CurrentTrafficSerializationError("partial selection is invalid")
    _closed(coverage, "observation_ap_count installed_ap_count online_ap_count offline_ap_count other_ap_count unknown_ap_count measured_pair_ap_count measured_download_ap_count measured_upload_ap_count required_measurement_ap_count missing_required_ap_count offline_excluded_ap_count observation_only_ap_count inventory_only_ap_count population_match_state coverage_reasons")
    nullable = {"installed_ap_count", "online_ap_count", "offline_ap_count", "other_ap_count", "unknown_ap_count", "required_measurement_ap_count", "missing_required_ap_count"}
    for key, count in coverage.items():
        if key.endswith("_count") and not (key in nullable and count is None):
            _count(count)
    for key in ("wired_pair_valid_ap_count", "lan_pair_valid_ap_count"):
        if _count(selection[key]) > coverage["observation_ap_count"]:
            raise CurrentTrafficSerializationError("partial selection counts are invalid")
    for key in ("measured_pair_ap_count", "measured_download_ap_count", "measured_upload_ap_count", "offline_excluded_ap_count"):
        if coverage[key] > coverage["observation_ap_count"]:
            raise CurrentTrafficSerializationError("partial coverage exceeds population")
    if coverage["measured_pair_ap_count"] > min(coverage["measured_download_ap_count"], coverage["measured_upload_ap_count"]):
        raise CurrentTrafficSerializationError("partial directional counts are invalid")
    if coverage["installed_ap_count"] is not None:
        if any(coverage[key] is None for key in nullable) or sum(coverage[key] for key in ("online_ap_count", "offline_ap_count", "other_ap_count", "unknown_ap_count")) != coverage["installed_ap_count"]:
            raise CurrentTrafficSerializationError("partial installed counts are invalid")
        if (coverage["required_measurement_ap_count"] != coverage["installed_ap_count"] - coverage["offline_excluded_ap_count"]
            or coverage["missing_required_ap_count"] > coverage["required_measurement_ap_count"]):
            raise CurrentTrafficSerializationError("partial required counts are invalid")
    elif any(coverage[key] is not None for key in nullable):
        raise CurrentTrafficSerializationError("unproven inventory counts are invalid")
    if coverage["population_match_state"] not in {"matched", "observation_only", "inventory_only", "mismatch", "status_unavailable"}:
        raise CurrentTrafficSerializationError("partial population match is invalid")
    reasons = coverage["coverage_reasons"]
    if not isinstance(reasons, list) or reasons != sorted(set(reasons)) or any(reason not in _PARTIAL_REASONS for reason in reasons):
        raise CurrentTrafficSerializationError("partial coverage reasons are invalid")
    _closed(status, "state cycle_id capture_started_at capture_finished_at age_at_traffic_seconds source_scope_hash")
    if status["state"] not in {"aligned_fresh", "stale", "unavailable", "population_mismatch"}:
        raise CurrentTrafficSerializationError("partial status evidence is invalid")
    for key in ("capture_started_at", "capture_finished_at"):
        _timestamp(status[key], optional=True)
    _number(status["age_at_traffic_seconds"], optional=True, nonnegative=True)
    if status["source_scope_hash"] is not None and re.fullmatch(r"[0-9a-f]{64}", status["source_scope_hash"]) is None:
        raise CurrentTrafficSerializationError("partial status scope is invalid")
    if status["state"] in {"aligned_fresh", "population_mismatch"}:
        if any(status[key] is None for key in ("cycle_id", "capture_started_at", "capture_finished_at", "age_at_traffic_seconds", "source_scope_hash")) or status["capture_finished_at"] > snapshot["finished_at"]:
            raise CurrentTrafficSerializationError("future or missing status evidence")
    if status["cycle_id"] is not None and (not isinstance(status["cycle_id"], str) or not 1 <= len(status["cycle_id"]) <= 128):
        raise CurrentTrafficSerializationError("partial status identity is invalid")
    _closed(traffic, "download_mbps upload_mbps total_mbps unit")
    if traffic["unit"] != "Mbps":
        raise CurrentTrafficSerializationError("partial traffic unit is invalid")
    down, up, total = (_number(traffic[key], optional=True, nonnegative=True) for key in ("download_mbps", "upload_mbps", "total_mbps"))
    _total_consistent(down, up, total)
    if value.measurement_state == "unavailable" or snapshot["freshness_status"] == "unavailable":
        if any(number is not None for number in (down, up, total)):
            raise CurrentTrafficSerializationError("unavailable partial traffic has numbers")
    elif down is None and up is None:
        raise CurrentTrafficSerializationError("partial traffic has no measurements")
    if value.measurement_state == "complete_online_population":
        if (status["state"] != "aligned_fresh" or coverage["population_match_state"] != "matched"
            or coverage["other_ap_count"] or coverage["unknown_ap_count"]
            or coverage["measured_pair_ap_count"] != coverage["online_ap_count"]
            or coverage["measured_download_ap_count"] != coverage["online_ap_count"]
            or coverage["measured_upload_ap_count"] != coverage["online_ap_count"]
            or coverage["offline_excluded_ap_count"] != coverage["offline_ap_count"]
            or "status_measurement_conflict" in reasons):
            raise CurrentTrafficSerializationError("unproven complete-online population")
    if value.measurement_state == "complete_installed":
        if (coverage["measured_pair_ap_count"] != coverage["observation_ap_count"]
            or coverage["population_match_state"] == "mismatch"
            or not (status["state"] == "aligned_fresh" and coverage["population_match_state"] == "matched"
                    or snapshot["source_complete"] and snapshot["source_result"] == "success")):
            raise CurrentTrafficSerializationError("unproven installed population")
    return {"metric_version": value.metric_version, "site_id": value.site_id,
            "evaluated_at_utc": value.evaluated_at_utc, "measurement_state": value.measurement_state,
            "population_scope": value.population_scope, "snapshot": snapshot, "traffic": traffic,
            "source_selection": selection, "coverage": coverage, "status_evidence": status}


def serialize_partial_current_ap_page(value, site_id, *, cycle_id, limit):
    try:
        return _serialize_partial_current_ap_page(value, site_id, cycle_id=cycle_id, limit=limit)
    except CurrentTrafficSerializationError:
        raise
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise CurrentTrafficSerializationError("partial current AP source is malformed") from exc


def _serialize_partial_current_ap_page(value, site_id, *, cycle_id, limit):
    if not isinstance(value, CoverageAwareCurrentApTrafficPageV1) or value.metric_version != "network_traffic_current_ap_partial_coverage.v1":
        raise CurrentTrafficSerializationError("partial AP page is invalid")
    result = serialize_partial_current_summary(value.summary, site_id)
    if value.page.cycle_id != cycle_id or value.page.limit != limit or not 1 <= limit <= 250 or len(value.items) > limit or value.page.selected_source != result["source_selection"]["selected_source"]:
        raise CurrentTrafficSerializationError("partial AP page context is invalid")
    items = _plain(value.items)
    seen = set()
    for item in items:
        _closed(item, "ap_mac name selected_source download_mbps upload_mbps total_mbps download_reason upload_reason rate_status coverage_role status_classification observed_at")
        if not isinstance(item["ap_mac"], str) or _MAC_PATTERN.fullmatch(item["ap_mac"]) is None or item["ap_mac"] in seen:
            raise CurrentTrafficSerializationError("partial AP identity is invalid")
        seen.add(item["ap_mac"])
        if item["name"] is not None and not isinstance(item["name"], str):
            raise CurrentTrafficSerializationError("partial AP name is invalid")
        if item["selected_source"] != value.page.selected_source or item["rate_status"] not in _RATE_STATUS or item["coverage_role"] not in {"measured", "offline_excluded", "missing", "required_unknown", "population_conflict"} or item["status_classification"] not in {None, "online", "offline", "other", "unknown"}:
            raise CurrentTrafficSerializationError("partial AP role is invalid")
        for direction in ("download", "upload"):
            if item[f"{direction}_reason"] not in _RATE_REASONS:
                raise CurrentTrafficSerializationError("partial AP rate reason is invalid")
            number = _number(item[f"{direction}_mbps"], optional=True, nonnegative=True)
            if number is not None and item[f"{direction}_reason"] != "ok":
                raise CurrentTrafficSerializationError("partial AP rate shape is invalid")
        total = _number(item["total_mbps"], optional=True, nonnegative=True)
        _total_consistent(item["download_mbps"], item["upload_mbps"], total)
        expected_status = "valid" if item["download_mbps"] is not None and item["upload_mbps"] is not None else "partial" if item["download_mbps"] is not None or item["upload_mbps"] is not None else "unavailable"
        if item["rate_status"] != expected_status:
            raise CurrentTrafficSerializationError("partial AP rate status is inconsistent")
        _timestamp(item["observed_at"], optional=True)
        if item["coverage_role"] == "offline_excluded" and (item["status_classification"] != "offline" or item["download_reason"] != "source_unavailable" or item["upload_reason"] != "source_unavailable" or any(item[key] is not None for key in ("download_mbps", "upload_mbps", "total_mbps"))):
            raise CurrentTrafficSerializationError("Offline AP is not excluded")
    result["metric_version"] = value.metric_version
    result["items"] = items
    return result, {"limit": limit, "cycle_id": cycle_id, "selected_source": value.page.selected_source,
                    "next_cursor": value.page.next_cursor}


def serialize_current_traffic_summary(
    value: CurrentSiteTraffic,
    site_id: str,
) -> dict[str, Any]:
    snapshot = _snapshot(value.snapshot, site_id)
    policy = _policy(value.freshness_policy, include_skew=True)
    source = _source_selection(value.source_selection, snapshot)
    coverage = _coverage(value.coverage, snapshot)
    traffic = _traffic(value.traffic, snapshot, coverage)
    _freshness_consistent(value.freshness, snapshot)
    return {
        "snapshot": snapshot,
        "freshness_policy": policy,
        "traffic": traffic,
        "source_selection": source,
        "coverage": coverage,
    }


def serialize_current_ap_traffic_page(
    value: CurrentApTrafficPage,
    site_id: str,
    *,
    cycle_id: str,
    limit: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    snapshot = _snapshot(value.snapshot, site_id)
    policy = _policy(value.freshness_policy, include_skew=False)
    source = _source_selection(value.source_selection, snapshot, compact=True)
    selected = snapshot["selected_source"]
    if (
        snapshot["cycle_id"] != cycle_id
        or snapshot["complete"] is not True
        or snapshot["freshness_status"] == "unavailable"
        or selected not in _SOURCES
        or value.page.cycle_id != cycle_id
        or value.page.selected_source != selected
        or value.page.limit != limit
    ):
        raise CurrentTrafficSerializationError("AP page context is invalid")
    items = []
    seen_macs: set[str] = set()
    for item in value.items:
        if item.selected_source != selected:
            raise CurrentTrafficSerializationError("AP item source is invalid")
        if (
            not isinstance(item.ap_mac, str)
            or _MAC_PATTERN.fullmatch(item.ap_mac) is None
            or item.ap_mac in seen_macs
        ):
            raise CurrentTrafficSerializationError("AP identity is invalid")
        seen_macs.add(item.ap_mac)
        if item.name is not None and not isinstance(item.name, str):
            raise CurrentTrafficSerializationError("AP name is invalid")
        if item.download_reason not in _RATE_REASONS or item.upload_reason not in _RATE_REASONS:
            raise CurrentTrafficSerializationError("AP rate reason is invalid")
        if item.rate_status not in _RATE_STATUS:
            raise CurrentTrafficSerializationError("AP rate status is invalid")
        observed = _timestamp(item.observed_at, optional=True)
        age = _number(item.age_seconds, optional=True, nonnegative=True)
        download = _number(item.download_mbps, optional=True, nonnegative=True)
        upload = _number(item.upload_mbps, optional=True, nonnegative=True)
        total = _number(item.total_mbps, optional=True, nonnegative=True)
        _total_consistent(download, upload, total)
        items.append({
            "ap_mac": item.ap_mac,
            "name": item.name,
            "download_mbps": download,
            "upload_mbps": upload,
            "total_mbps": total,
            "download_reason": item.download_reason,
            "upload_reason": item.upload_reason,
            "rate_status": item.rate_status,
            "observed_at": observed,
            "age_seconds": age,
            "selected_source": selected,
        })
    cursor = value.page.next_cursor
    if cursor is not None and (not isinstance(cursor, str) or not cursor):
        raise CurrentTrafficSerializationError("AP page cursor is invalid")
    result = {
        "snapshot": _compact_page_snapshot(snapshot),
        "freshness_policy": policy,
        "source_selection": source,
        "items": items,
    }
    page = {
        "limit": value.page.limit,
        "next_cursor": cursor,
        "cycle_id": value.page.cycle_id,
        "selected_source": value.page.selected_source,
    }
    return result, page


def _snapshot(value: Any, site_id: str) -> dict[str, Any]:
    if value.source_kind != "observation_ap_dynamic" or value.site_id != site_id:
        raise CurrentTrafficSerializationError("snapshot identity is invalid")
    if type(value.complete) is not bool or type(value.empty_population) is not bool:
        raise CurrentTrafficSerializationError("snapshot flags are invalid")
    if type(value.using_previous_complete_snapshot) is not bool:
        raise CurrentTrafficSerializationError("snapshot previous flag is invalid")
    cycle_id = value.cycle_id
    if cycle_id is not None and (not isinstance(cycle_id, str) or not cycle_id):
        raise CurrentTrafficSerializationError("snapshot cycle is invalid")
    evaluated = _timestamp(value.evaluated_at)
    observed = _timestamp(value.observed_at, optional=True)
    newest = _timestamp(value.newest_observed_at, optional=True)
    latest_at = _timestamp(value.latest_attempt_at, optional=True)
    if observed is not None and newest is not None:
        if not (_instant(observed) <= _instant(newest) <= _instant(evaluated)):
            raise CurrentTrafficSerializationError("snapshot timestamps are invalid")
    elif observed is not None or newest is not None:
        raise CurrentTrafficSerializationError("snapshot timestamps are incomplete")
    age = _number(value.age_seconds, optional=True, nonnegative=True)
    skew = _number(value.source_skew_seconds, optional=True, nonnegative=True)
    if value.freshness_status not in _FRESHNESS or value.freshness_reason not in _FRESHNESS_REASONS:
        raise CurrentTrafficSerializationError("snapshot freshness is invalid")
    if value.primary_source != "wired" or value.selection_reason not in _SELECTION_REASONS:
        raise CurrentTrafficSerializationError("snapshot source selection is invalid")
    selected = value.selected_source
    if selected is not None and selected not in _SOURCES:
        raise CurrentTrafficSerializationError("snapshot selected source is invalid")
    _latest_attempt(value.latest_attempt_state, value.latest_attempt_result, latest_at)
    if cycle_id is None:
        if (
            value.complete is not False
            or selected is not None
            or value.selection_reason != "no_complete_snapshot"
            or value.empty_population
            or value.freshness_status != "unavailable"
            or value.freshness_reason != "no_complete_snapshot"
            or any(item is not None for item in (observed, newest, age, skew))
        ):
            raise CurrentTrafficSerializationError("no-snapshot state is invalid")
    elif value.complete is not True or selected not in _SOURCES:
        raise CurrentTrafficSerializationError("complete snapshot state is invalid")
    elif value.empty_population:
        if selected != "wired" or value.selection_reason != "empty_population":
            raise CurrentTrafficSerializationError("empty snapshot source selection is invalid")
    elif value.selection_reason == "empty_population":
        raise CurrentTrafficSerializationError("non-empty snapshot selection reason is invalid")
    return {
        "source_kind": value.source_kind,
        "cycle_id": cycle_id,
        "complete": value.complete,
        "evaluated_at": evaluated,
        "observed_at": observed,
        "newest_observed_at": newest,
        "age_seconds": age,
        "source_skew_seconds": skew,
        "freshness_status": value.freshness_status,
        "freshness_reason": value.freshness_reason,
        "latest_attempt_state": value.latest_attempt_state,
        "latest_attempt_result": value.latest_attempt_result,
        "latest_attempt_at": latest_at,
        "using_previous_complete_snapshot": value.using_previous_complete_snapshot,
        "selected_source": selected,
        "selection_reason": value.selection_reason,
        "empty_population": value.empty_population,
    }


def _compact_page_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        key: snapshot[key]
        for key in (
            "source_kind", "cycle_id", "evaluated_at", "observed_at",
            "newest_observed_at", "age_seconds", "freshness_status",
            "freshness_reason",
        )
    }


def _policy(value: Any, *, include_skew: bool) -> dict[str, Any]:
    fresh = _number(value.fresh_max_age_seconds, nonnegative=True)
    stale = _number(value.stale_max_age_seconds, nonnegative=True)
    skew = _number(value.max_ap_skew_seconds, nonnegative=True)
    if stale < fresh:
        raise CurrentTrafficSerializationError("freshness policy is invalid")
    result = {
        "fresh_max_age_seconds": fresh,
        "unavailable_after_seconds": stale,
    }
    if include_skew:
        result["max_ap_skew_seconds"] = skew
    return result


def _source_selection(value: Any, snapshot: dict[str, Any], *, compact: bool = False) -> dict[str, Any]:
    if (
        value.primary_source != "wired"
        or value.selected_source != snapshot["selected_source"]
        or value.selection_reason != snapshot["selection_reason"]
        or type(value.source_mixing_allowed) is not bool
        or value.source_mixing_allowed
    ):
        raise CurrentTrafficSerializationError("source selection is invalid")
    wired = _count(value.wired_pair_valid_ap_count)
    lan = _count(value.lan_pair_valid_ap_count)
    if snapshot["cycle_id"] is None and (wired != 0 or lan != 0):
        raise CurrentTrafficSerializationError("no-snapshot source counts are invalid")
    if snapshot["empty_population"] and (wired != 0 or lan != 0):
        raise CurrentTrafficSerializationError("empty source counts are invalid")
    result = {
        "selected_source": value.selected_source,
        "selection_reason": value.selection_reason,
        "source_mixing_allowed": value.source_mixing_allowed,
    }
    if not compact:
        result = {"primary_source": "wired", **result}
        result["wired_pair_valid_ap_count"] = wired
        result["lan_pair_valid_ap_count"] = lan
    return result


def _coverage(value: Any, snapshot: dict[str, Any]) -> dict[str, Any]:
    if value.status not in _COVERAGE or type(value.empty_population) is not bool:
        raise CurrentTrafficSerializationError("coverage status is invalid")
    if value.empty_population != snapshot["empty_population"]:
        raise CurrentTrafficSerializationError("coverage population is invalid")
    reasons = list(value.reasons)
    if len(set(reasons)) != len(reasons) or any(item not in _COVERAGE_REASONS for item in reasons):
        raise CurrentTrafficSerializationError("coverage reasons are invalid")
    fields = (
        "total_ap_count", "valid_rate_ap_count", "valid_download_ap_count",
        "valid_upload_ap_count", "missing_rate_ap_count", "stale_ap_count",
        "unavailable_ap_count", "reset_ap_count", "gap_rejected_ap_count",
        "no_baseline_ap_count", "source_unavailable_ap_count",
        "invalid_elapsed_ap_count",
    )
    counts = {name: _count(getattr(value, name)) for name in fields}
    total = counts["total_ap_count"]
    if any(counts[name] > total for name in fields if name != "total_ap_count"):
        raise CurrentTrafficSerializationError("coverage count exceeds population")
    if counts["missing_rate_ap_count"] != total - counts["valid_rate_ap_count"]:
        raise CurrentTrafficSerializationError("coverage count invariant failed")
    if snapshot["cycle_id"] is None and (value.status != "none" or total != 0):
        raise CurrentTrafficSerializationError("no-snapshot coverage is invalid")
    if snapshot["empty_population"] and (value.status != "complete" or total != 0):
        raise CurrentTrafficSerializationError("empty coverage is invalid")
    return {
        "coverage_status": value.status,
        "empty_population": value.empty_population,
        **counts,
        "coverage_reasons": reasons,
    }


def _traffic(value: Any, snapshot: dict[str, Any], coverage: dict[str, Any]) -> dict[str, Any]:
    download = _number(value.download_mbps, optional=True, nonnegative=True)
    upload = _number(value.upload_mbps, optional=True, nonnegative=True)
    total = _number(value.total_mbps, optional=True, nonnegative=True)
    _total_consistent(download, upload, total)
    if coverage["coverage_status"] == "none" or snapshot["freshness_status"] == "unavailable":
        if any(item is not None for item in (download, upload, total)):
            raise CurrentTrafficSerializationError("unavailable traffic contains values")
    if snapshot["empty_population"] and (download, upload, total) != (0.0, 0.0, 0.0):
        raise CurrentTrafficSerializationError("empty traffic must be exact zero")
    return {
        "download_mbps": download,
        "upload_mbps": upload,
        "total_mbps": total,
        "unit": "Mbps",
    }


def _freshness_consistent(value: Any, snapshot: dict[str, Any]) -> None:
    if (
        value.status != snapshot["freshness_status"]
        or value.reason != snapshot["freshness_reason"]
        or value.evaluated_at_utc != snapshot["evaluated_at"]
        or value.observed_at != snapshot["observed_at"]
        or value.newest_observed_at != snapshot["newest_observed_at"]
        or value.age_seconds != snapshot["age_seconds"]
    ):
        raise CurrentTrafficSerializationError("freshness projection is inconsistent")


def _latest_attempt(state: Any, result: Any, at: str | None) -> None:
    if state not in _LATEST_STATES or (result is not None and result not in _LATEST_RESULTS):
        raise CurrentTrafficSerializationError("latest attempt is invalid")
    valid = (
        (state == "none" and result is None and at is None)
        or (state == "running" and result is None and at is not None)
        or (state == "abandoned" and result is None and at is not None)
        or (state == "completed" and result in _LATEST_RESULTS and at is not None)
    )
    if not valid:
        raise CurrentTrafficSerializationError("latest attempt combination is invalid")


def _total_consistent(download: float | None, upload: float | None, total: float | None) -> None:
    if download is not None and upload is not None:
        if total is None or abs(total - (download + upload)) > 1e-6:
            raise CurrentTrafficSerializationError("traffic total is invalid")
    elif total is not None:
        raise CurrentTrafficSerializationError("partial traffic total is invalid")


def _count(value: Any) -> int:
    if type(value) is not int or value < 0:
        raise CurrentTrafficSerializationError("count is invalid")
    return value


def _number(value: Any, *, optional: bool = False, nonnegative: bool = False) -> float | None:
    if value is None and optional:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise CurrentTrafficSerializationError("number is invalid")
    result = float(value)
    if nonnegative and result < 0:
        raise CurrentTrafficSerializationError("number is negative")
    return result


def _timestamp(value: Any, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise CurrentTrafficSerializationError("timestamp is invalid")
    try:
        parsed = parse_utc(value, "timestamp")
    except AnalyticsQueryValidationError as exc:
        raise CurrentTrafficSerializationError("timestamp is invalid") from exc
    if format_utc(parsed) != value:
        raise CurrentTrafficSerializationError("timestamp is not canonical")
    return value


def _instant(value: str) -> datetime:
    try:
        return parse_utc(value, "timestamp")
    except AnalyticsQueryValidationError as exc:
        raise CurrentTrafficSerializationError("timestamp is invalid") from exc
