"""Explicit minimized serializers for Admin Home Live v1."""

from __future__ import annotations

import math
from typing import Any, Mapping

from app.current_state import (
    CurrentApPage,
    CurrentApSummary,
    CurrentClientPage,
    CurrentClientSummary,
    CurrentSnapshotMeta,
    CurrentStateValidationError,
)


CLIENT_FRESHNESS_POLICY = {
    "fresh_max_age_seconds": 60,
    "unavailable_after_seconds": 180,
}
AP_FRESHNESS_POLICY = {
    "fresh_max_age_seconds": 90,
    "unavailable_after_seconds": 300,
}
_FRESHNESS = frozenset({"fresh", "stale", "unavailable"})
_AUTH = frozenset({"authorized", "pending", "other", "unknown"})


def serialize_client_summary(value: CurrentClientSummary, site_id: str) -> dict[str, Any]:
    snapshot = _snapshot(value.snapshot, site_id, "client")
    counts = {
        "online": value.online_count,
        "authorized": value.authorized_count,
        "pending": value.pending_count,
        "other": value.other_count,
        "unknown": value.unknown_count,
        "other_unknown": value.other_unknown_count,
        "ap_unknown": value.ap_unknown_count,
    }
    if snapshot["freshness_status"] == "unavailable":
        if any(item is not None for item in counts.values()) or value.devices_by_ap:
            raise CurrentStateValidationError("unavailable client summary contains values")
    else:
        _client_count_invariants(counts, value.devices_by_ap)
    buckets = []
    for item in value.devices_by_ap:
        if not isinstance(item.ap_mac, str) or not _nonnegative(item.client_count):
            raise CurrentStateValidationError("invalid client AP bucket")
        buckets.append({"ap_mac": item.ap_mac, "client_count": item.client_count})
    return {
        "snapshot": snapshot,
        "freshness_policy": dict(CLIENT_FRESHNESS_POLICY),
        "counts": counts,
        "devices_by_ap": buckets,
    }


def serialize_client_page(
    value: CurrentClientPage,
    site_id: str,
    *,
    limit: int,
    explicit_cycle_id: str | None,
    explicit_cursor: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    snapshot = _snapshot(value.snapshot, site_id, "client")
    cycle_id = snapshot["cycle_id"]
    if (explicit_cycle_id is not None and cycle_id != explicit_cycle_id) or (
        explicit_cursor is not None and cycle_id is None
    ) or ((explicit_cycle_id is not None or explicit_cursor is not None) and snapshot["freshness_status"] == "unavailable"):
        raise ValueError("explicit current client page is unavailable")
    scope = snapshot["source_scope"]
    allowed_ssids = set(scope["ssids"]) if scope is not None else set()
    items = []
    for item in value.items:
        if item.site_id != site_id or item.cycle_id != cycle_id or item.ssid not in allowed_ssids:
            raise CurrentStateValidationError("client item identity invariant failed")
        if item.auth_classification not in _AUTH:
            raise CurrentStateValidationError("client auth classification is invalid")
        items.append(
            {
                "client_mac": item.client_mac,
                "name": item.name,
                "hostname": item.hostname,
                "ip": item.ip,
                "ssid": item.ssid,
                "ap_name": item.ap_name,
                "ap_mac": item.ap_mac,
                "band": item.band,
                "rssi": item.rssi,
                "snr": item.snr,
                "controller_uptime": item.controller_uptime,
                "controller_traffic_down": item.controller_traffic_down,
                "controller_traffic_up": item.controller_traffic_up,
                "controller_traffic_total": item.controller_traffic_total,
                "auth_classification": item.auth_classification,
            }
        )
    result = {
        "snapshot": snapshot,
        "freshness_policy": dict(CLIENT_FRESHNESS_POLICY),
        "items": items,
    }
    page = {
        "limit": limit,
        "next_cursor": value.next_cursor,
        "cycle_id": cycle_id,
        "source_scope_hash": snapshot["source_scope_hash"],
    }
    return result, page


def serialize_ap_summary(value: CurrentApSummary, site_id: str) -> dict[str, Any]:
    snapshot = _snapshot(value.snapshot, site_id, "ap")
    other = None
    if value.other_count is not None and value.offline_count is not None:
        other = value.other_count + value.offline_count
    counts = {
        "total": value.ap_total,
        "online": value.online_count,
        "other": other,
        "unknown": value.unknown_count,
    }
    if snapshot["freshness_status"] == "unavailable":
        if any(item is not None for item in counts.values()):
            raise CurrentStateValidationError("unavailable AP summary contains values")
    elif not all(_nonnegative(item) for item in counts.values()) or counts["total"] != counts["online"] + counts["other"] + counts["unknown"]:
        raise CurrentStateValidationError("AP product count invariant failed")
    return {
        "snapshot": snapshot,
        "freshness_policy": dict(AP_FRESHNESS_POLICY),
        "counts": counts,
    }


def serialize_ap_page(
    value: CurrentApPage,
    site_id: str,
    *,
    limit: int,
    explicit_cycle_id: str | None,
    explicit_cursor: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    snapshot = _snapshot(value.snapshot, site_id, "ap")
    cycle_id = snapshot["cycle_id"]
    if (explicit_cycle_id is not None and cycle_id != explicit_cycle_id) or (
        explicit_cursor is not None and cycle_id is None
    ) or ((explicit_cycle_id is not None or explicit_cursor is not None) and snapshot["freshness_status"] == "unavailable"):
        raise ValueError("explicit current AP page is unavailable")
    items = []
    for item in value.items:
        if item.site_id != site_id or item.cycle_id != cycle_id:
            raise CurrentStateValidationError("AP item identity invariant failed")
        classification = (
            "Online" if item.status_classification == "online" else
            "Unknown" if item.status_classification == "unknown" else "Other"
        )
        items.append({
            "ap_mac": item.ap_mac,
            "name": item.name,
            "product_status_classification": classification,
        })
    result = {
        "snapshot": snapshot,
        "freshness_policy": dict(AP_FRESHNESS_POLICY),
        "items": items,
    }
    page = {
        "limit": limit,
        "next_cursor": value.next_cursor,
        "cycle_id": cycle_id,
        "source_scope_hash": snapshot["source_scope_hash"],
    }
    return result, page


def _snapshot(value: CurrentSnapshotMeta, site_id: str, kind: str) -> dict[str, Any]:
    if value.site_id != site_id or value.kind != kind or value.freshness_status not in _FRESHNESS:
        raise CurrentStateValidationError("snapshot identity invariant failed")
    if value.age_seconds is not None and (
        isinstance(value.age_seconds, bool)
        or not isinstance(value.age_seconds, (int, float))
        or not math.isfinite(value.age_seconds)
        or value.age_seconds < 0
    ):
        raise CurrentStateValidationError("snapshot age is invalid")
    return {
        "kind": value.kind,
        "cycle_id": value.cycle_id,
        "evaluated_at": value.evaluated_at,
        "observed_at": value.observed_at,
        "capture_finished_at": value.capture_finished_at,
        "age_seconds": value.age_seconds,
        "freshness_status": value.freshness_status,
        "freshness_reason": value.freshness_reason,
        "complete": value.complete,
        "source_scope_version": value.source_scope_version,
        "source_scope_hash": value.source_scope_hash,
        "source_scope": _scope(value.source_scope, site_id, kind),
        "latest_attempt_result": value.latest_attempt_result,
        "latest_attempt_at": value.latest_attempt_at,
        "latest_partial_cycle_id": value.latest_partial_cycle_id,
    }


def _scope(value: Mapping[str, Any] | None, site_id: str, kind: str) -> dict[str, Any] | None:
    if value is None:
        return None
    if value.get("site_id") != site_id:
        raise CurrentStateValidationError("source scope Site invariant failed")
    if kind == "client":
        ssids = value.get("ssids")
        if value.get("scope_type") != "client_ssid_allowlist" or not isinstance(ssids, (list, tuple)) or any(not isinstance(item, str) or not item for item in ssids):
            raise CurrentStateValidationError("client source scope is invalid")
        return {"scope_type": value["scope_type"], "site_id": site_id, "ssids": list(ssids)}
    if value.get("scope_type") != "site_ap_inventory":
        raise CurrentStateValidationError("AP source scope is invalid")
    return {"scope_type": "site_ap_inventory", "site_id": site_id}


def _client_count_invariants(counts: Mapping[str, Any], buckets: Any) -> None:
    if not all(_nonnegative(item) for item in counts.values()):
        raise CurrentStateValidationError("client count is invalid")
    if counts["online"] != counts["authorized"] + counts["pending"] + counts["other"] + counts["unknown"]:
        raise CurrentStateValidationError("client auth count invariant failed")
    if counts["other_unknown"] != counts["other"] + counts["unknown"]:
        raise CurrentStateValidationError("client other count invariant failed")
    if counts["online"] != counts["ap_unknown"] + sum(item.client_count for item in buckets):
        raise CurrentStateValidationError("client AP count invariant failed")


def _nonnegative(value: Any) -> bool:
    return type(value) is int and value >= 0
