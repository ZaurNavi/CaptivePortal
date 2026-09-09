"""Strict Device Current Context composition and Admin serialization."""

from __future__ import annotations

import math
import re
import uuid
from datetime import datetime
from typing import Any, Mapping

from app.analytics.current_guest_traffic import CurrentGuestTrafficClientResult
from app.current_state.read_service import CurrentClientLookup


CONTRACT_VERSION = "admin.device.current.v1"
_SITE = re.compile(r"[0-9a-f]{24}")
_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z")
_MAC = re.compile(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}")
_FRESHNESS = frozenset({"fresh", "stale", "unavailable"})
_FRESHNESS_REASONS = frozenset({
    "within_freshness_window", "older_than_freshness_window",
    "older_than_unavailable_threshold", "no_complete_snapshot",
    "clock_anomaly", "invalid_timestamp", "invalid_source_scope",
})
_AUTH = frozenset({"authorized", "pending", "other", "unknown"})
_SOURCE_HEALTH = frozenset({"healthy", "degraded", "stale", "unavailable"})
_SOURCE_REASONS = frozenset({
    "within_freshness_window", "newer_degraded_attempt",
    "older_than_freshness_window", "older_than_unavailable_threshold",
    "clock_anomaly", "no_complete_snapshot",
})
_RATE_REASONS = frozenset({
    "valid", "no_baseline", "no_authorized_baseline", "ssid_transition",
    "invalid_elapsed", "baseline_gap_too_large",
    "connection_continuity_unproven", "source_frozen", "connection_reset",
    "counter_missing", "counter_reset",
})


class DeviceCurrentContextSerializationError(ValueError):
    """The composed entity result cannot be safely exposed."""


def serialize_device_current_context(
    *,
    site_id: str,
    device_id: str,
    evaluated_at_utc: str,
    scope: Mapping[str, Any],
    current: CurrentClientLookup,
    traffic: CurrentGuestTrafficClientResult | None,
    applicability: str,
    applicability_reason: str,
    traffic_failure_reason: str | None = None,
) -> dict[str, Any]:
    """Validate cross-source invariants and return the frozen safe DTO."""

    if not isinstance(site_id, str) or _SITE.fullmatch(site_id) is None:
        raise DeviceCurrentContextSerializationError("Site identity is invalid")
    try:
        if str(uuid.UUID(device_id)) != device_id:
            raise ValueError
    except (AttributeError, TypeError, ValueError) as exc:
        raise DeviceCurrentContextSerializationError("device identity is invalid") from exc
    evaluated = _timestamp(evaluated_at_utc)
    if not isinstance(current, CurrentClientLookup):
        raise DeviceCurrentContextSerializationError("Current State result is invalid")
    snapshot = current.snapshot
    if snapshot.site_id != site_id or snapshot.kind != "client":
        raise DeviceCurrentContextSerializationError("Current State Site is invalid")
    if _timestamp(snapshot.evaluated_at) != evaluated:
        raise DeviceCurrentContextSerializationError("evaluation anchor is inconsistent")
    safe_scope = _scope(scope, site_id)
    if (
        snapshot.source_scope is not None
        and dict(snapshot.source_scope) != safe_scope
        and snapshot.freshness_reason != "invalid_source_scope"
    ):
        raise DeviceCurrentContextSerializationError("Current State scope is invalid")

    snapshot_dto = _snapshot(snapshot)
    client = current.client
    if client is not None:
        if (
            snapshot.freshness_status != "fresh"
            or not snapshot.complete
            or snapshot.cycle_id is None
            or client.site_id != site_id
            or client.cycle_id != snapshot.cycle_id
            or client.observed_at != snapshot.observed_at
            or not client.active
            or not client.wireless
        ):
            raise DeviceCurrentContextSerializationError("current client is contradictory")
        presence = "online"
        presence_reason = "present_in_fresh_complete_scope"
        authorization = {
            "classification": _enum(client.auth_classification, _AUTH, "authorization"),
            "reason": "current_row",
        }
        client_dto = _client(client)
        if client.ssid not in safe_scope["ssids"]:
            raise DeviceCurrentContextSerializationError("client SSID is outside scope")
    elif snapshot.freshness_status == "fresh" and snapshot.complete:
        presence = "offline"
        presence_reason = "absent_from_fresh_complete_scope"
        authorization = {"classification": "unknown", "reason": "offline"}
        client_dto = None
    else:
        presence = "unknown"
        presence_reason = "current_state_unknown"
        authorization = {
            "classification": "unknown", "reason": "current_state_unknown"
        }
        client_dto = None

    traffic_dto = _traffic(
        traffic,
        site_id=site_id,
        client_mac=client.client_mac if client is not None else None,
        evaluated=evaluated,
        current_cycle_id=snapshot.cycle_id,
        current_scope_hash=snapshot.source_scope_hash,
        applicability=applicability,
        applicability_reason=applicability_reason,
        failure_reason=traffic_failure_reason,
    )
    expected_applicability = (
        ("applicable", "authorized_current_guest")
        if presence == "online" and authorization["classification"] == "authorized"
        else ("not_applicable", "not_authorized_current_guest")
        if presence == "online"
        else ("not_applicable", "offline")
        if presence == "offline"
        else ("unknown", "current_state_unknown")
    )
    if (applicability, applicability_reason) != expected_applicability:
        raise DeviceCurrentContextSerializationError("Traffic applicability is invalid")

    return {
        "contract_version": CONTRACT_VERSION,
        "site_id": site_id,
        "device_id": device_id,
        "evaluated_at_utc": evaluated,
        "scope": safe_scope,
        "current_state": {
            "presence_status": presence,
            "presence_reason": presence_reason,
            "snapshot": snapshot_dto,
            "authorization": authorization,
            "client": client_dto,
        },
        "current_guest_traffic": traffic_dto,
    }


def _snapshot(value) -> dict[str, Any]:
    freshness = _enum(value.freshness_status, _FRESHNESS, "freshness")
    reason = _enum(value.freshness_reason, _FRESHNESS_REASONS, "freshness reason")
    cycle = _identity(value.cycle_id, optional=True)
    if type(value.complete) is not bool:
        raise DeviceCurrentContextSerializationError("snapshot completeness is invalid")
    semantic_timestamp = (
        freshness == "unavailable"
        and reason in {"invalid_timestamp", "invalid_source_scope"}
    )
    observed, finished, timestamps_sanitized = _snapshot_timestamps(
        value.observed_at,
        value.capture_finished_at,
        sanitize=semantic_timestamp,
    )
    if reason == "invalid_timestamp":
        if value.age_seconds is not None:
            raise DeviceCurrentContextSerializationError(
                "invalid timestamp age is contradictory"
            )
        age = None
    elif timestamps_sanitized:
        age = None
    else:
        age = _number(value.age_seconds, optional=True, nonnegative=True)
    if value.complete:
        if cycle is None:
            raise DeviceCurrentContextSerializationError("snapshot evidence is incomplete")
        if not timestamps_sanitized and reason != "invalid_timestamp" and (
            observed is None or finished is None or age is None
        ):
            raise DeviceCurrentContextSerializationError("snapshot evidence is incomplete")
    elif cycle is not None or observed is not None or finished is not None or age is not None:
        raise DeviceCurrentContextSerializationError("empty snapshot is contradictory")
    if freshness == "fresh" and not value.complete:
        raise DeviceCurrentContextSerializationError("fresh snapshot is incomplete")
    valid_pair = (
        (freshness == "fresh" and reason == "within_freshness_window")
        or (freshness == "stale" and reason == "older_than_freshness_window")
        or (
            freshness == "unavailable"
            and reason in {
                "older_than_unavailable_threshold", "no_complete_snapshot",
                "clock_anomaly", "invalid_timestamp", "invalid_source_scope",
            }
        )
    )
    if not valid_pair:
        raise DeviceCurrentContextSerializationError("freshness pair is invalid")
    return {
        "cycle_id": cycle,
        "observed_at": observed,
        "capture_finished_at": finished,
        "age_seconds": age,
        "freshness_status": freshness,
        "freshness_reason": reason,
        "complete": value.complete,
    }


def _client(value) -> dict[str, Any]:
    if _MAC.fullmatch(value.client_mac) is None:
        raise DeviceCurrentContextSerializationError("client MAC is invalid")
    if type(value.active) is not bool or type(value.wireless) is not bool:
        raise DeviceCurrentContextSerializationError("client state flags are invalid")
    return {
        "client_mac": value.client_mac,
        "name": _text(value.name),
        "hostname": _text(value.hostname),
        "device_type": _text(value.device_type),
        "ip": _text(value.ip),
        "ssid": _text(value.ssid, required=True),
        "ap_name": _text(value.ap_name),
        "ap_mac": _mac(value.ap_mac),
        "radio_id": _integer(value.radio_id),
        "band": _text(value.band),
        "channel": _integer(value.channel),
        "rssi": _integer(value.rssi),
        "snr": _integer(value.snr),
        "controller_uptime": _integer(value.controller_uptime, nonnegative=True),
        "controller_traffic_down_bytes": _integer(
            value.controller_traffic_down, nonnegative=True
        ),
        "controller_traffic_up_bytes": _integer(
            value.controller_traffic_up, nonnegative=True
        ),
        "controller_traffic_total_bytes": _integer(
            value.controller_traffic_total, nonnegative=True
        ),
        "active": value.active,
        "wireless": value.wireless,
    }


def _traffic(
    value,
    *,
    site_id,
    client_mac,
    evaluated,
    current_cycle_id,
    current_scope_hash,
    applicability,
    applicability_reason,
    failure_reason,
) -> dict[str, Any]:
    if applicability not in {"applicable", "not_applicable", "unknown"}:
        raise DeviceCurrentContextSerializationError("Traffic applicability is invalid")
    if applicability_reason not in {
        "authorized_current_guest", "not_authorized_current_guest",
        "offline", "current_state_unknown",
    }:
        raise DeviceCurrentContextSerializationError("Traffic applicability reason is invalid")
    if failure_reason is not None and failure_reason not in {
        "source_unavailable", "integrity_unavailable", "query_deadline",
    }:
        raise DeviceCurrentContextSerializationError("Traffic failure reason is invalid")
    if applicability != "applicable":
        if value is not None or failure_reason is not None:
            raise DeviceCurrentContextSerializationError("non-applicable Traffic is contradictory")
        return {
            "applicability": applicability,
            "applicability_reason": applicability_reason,
            "source_health_status": None,
            "source_health_reason": None,
            "rate_evidence_status": "not_applicable",
            "current_cycle_id": current_cycle_id,
            "baseline_cycle_id": None,
            "elapsed_seconds": None,
            "item": None,
            "failure_reason": None,
        }
    if failure_reason is not None:
        if value is not None or current_cycle_id is None:
            raise DeviceCurrentContextSerializationError("failed Traffic evidence is invalid")
        return {
            "applicability": applicability,
            "applicability_reason": applicability_reason,
            "source_health_status": None,
            "source_health_reason": None,
            "rate_evidence_status": None,
            "current_cycle_id": current_cycle_id,
            "baseline_cycle_id": None,
            "elapsed_seconds": None,
            "item": None,
            "failure_reason": failure_reason,
        }
    if not isinstance(value, CurrentGuestTrafficClientResult):
        raise DeviceCurrentContextSerializationError("Traffic result is invalid")
    if (
        value.site_id != site_id
        or value.evaluated_at_utc != evaluated
        or value.current_cycle_id != current_cycle_id
        or value.item.client_mac != client_mac
        or value.source_scope_hash != current_scope_hash
    ):
        raise DeviceCurrentContextSerializationError("Traffic coherence is invalid")
    source_status = _enum(value.source_health_status, _SOURCE_HEALTH, "source health")
    source_reason = _enum(value.source_health_reason, _SOURCE_REASONS, "source reason")
    if source_status not in {"healthy", "degraded"}:
        raise DeviceCurrentContextSerializationError("exact Traffic source is not current")
    if (source_status, source_reason) not in {
        ("healthy", "within_freshness_window"),
        ("degraded", "newer_degraded_attempt"),
        ("stale", "older_than_freshness_window"),
        ("unavailable", "older_than_unavailable_threshold"),
        ("unavailable", "clock_anomaly"),
        ("unavailable", "no_complete_snapshot"),
    }:
        raise DeviceCurrentContextSerializationError("source health pair is invalid")
    item = _traffic_item(value.item)
    expected_evidence = {
        "valid": "complete", "partial": "partial",
        "unavailable": "insufficient_data",
    }[item["rate_status"]]
    if value.rate_evidence_status != expected_evidence:
        raise DeviceCurrentContextSerializationError("rate evidence is invalid")
    baseline = _identity(value.baseline_cycle_id, optional=True)
    elapsed = _number(value.elapsed_seconds, optional=True, positive=True)
    if (baseline is None) != (elapsed is None):
        raise DeviceCurrentContextSerializationError("baseline evidence is inconsistent")
    return {
        "applicability": applicability,
        "applicability_reason": applicability_reason,
        "source_health_status": source_status,
        "source_health_reason": source_reason,
        "rate_evidence_status": value.rate_evidence_status,
        "current_cycle_id": value.current_cycle_id,
        "baseline_cycle_id": baseline,
        "elapsed_seconds": elapsed,
        "item": item,
        "failure_reason": None,
    }


def _traffic_item(value) -> dict[str, Any]:
    down = _number(value.download_mbps, optional=True, nonnegative=True)
    up = _number(value.upload_mbps, optional=True, nonnegative=True)
    total = _number(value.total_mbps, optional=True, nonnegative=True)
    reasons = tuple(
        _enum(reason, _RATE_REASONS, "rate reason")
        for reason in (value.download_reason, value.upload_reason, value.total_reason)
    )
    numeric = tuple(item is not None for item in (down, up, total))
    if numeric[0] != (reasons[0] == "valid"):
        raise DeviceCurrentContextSerializationError("Download reason is invalid")
    if numeric[1] != (reasons[1] == "valid"):
        raise DeviceCurrentContextSerializationError("Upload reason is invalid")
    if numeric[2] != (reasons[2] == "valid"):
        raise DeviceCurrentContextSerializationError("Total reason is invalid")
    if total is not None and (
        down is None
        or up is None
        or not math.isclose(total, down + up, rel_tol=1e-12, abs_tol=1e-12)
    ):
        raise DeviceCurrentContextSerializationError("Traffic total is invalid")
    if value.rate_status == "valid":
        valid = numeric == (True, True, True) and reasons == ("valid",) * 3
    elif value.rate_status == "partial":
        valid = sum(numeric[:2]) == 1 and not numeric[2]
    elif value.rate_status == "unavailable":
        valid = not any(numeric)
    else:
        valid = False
    if not valid:
        raise DeviceCurrentContextSerializationError("Traffic item shape is invalid")
    if any(numeric) and (
        value.source_progress_status != "advanced"
        or value.connection_continuity_status != "proven"
        or value.continuity_basis != "uptime_progress"
    ):
        raise DeviceCurrentContextSerializationError("Traffic continuity is invalid")
    if value.source_progress_status not in {"advanced", "frozen", "unproven"}:
        raise DeviceCurrentContextSerializationError("Traffic progress is invalid")
    if value.connection_continuity_status not in {"proven", "unproven", "reset"}:
        raise DeviceCurrentContextSerializationError("Traffic continuity is invalid")
    if value.continuity_basis not in {"uptime_progress", "counters_only_diagnostic", "none"}:
        raise DeviceCurrentContextSerializationError("Traffic basis is invalid")
    return {
        "download_mbps": down,
        "upload_mbps": up,
        "total_mbps": total,
        "rate_status": value.rate_status,
        "source_progress_status": value.source_progress_status,
        "connection_continuity_status": value.connection_continuity_status,
        "continuity_basis": value.continuity_basis,
        "download_reason": reasons[0],
        "upload_reason": reasons[1],
        "total_reason": reasons[2],
    }


def _scope(value: Mapping[str, Any], site_id: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {"scope_type", "site_id", "ssids"}:
        raise DeviceCurrentContextSerializationError("scope is invalid")
    ssids = value.get("ssids")
    if (
        value.get("scope_type") != "client_ssid_allowlist"
        or value.get("site_id") != site_id
        or not isinstance(ssids, (list, tuple))
        or not ssids
        or any(not isinstance(item, str) or not item for item in ssids)
        or len(set(ssids)) != len(ssids)
    ):
        raise DeviceCurrentContextSerializationError("scope is invalid")
    return {"scope_type": "client_ssid_allowlist", "site_id": site_id, "ssids": list(ssids)}


def _enum(value: Any, allowed: frozenset[str], name: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise DeviceCurrentContextSerializationError(f"{name} is invalid")
    return value


def _timestamp(value: Any, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        raise DeviceCurrentContextSerializationError("timestamp is invalid")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError as exc:
        raise DeviceCurrentContextSerializationError("timestamp is invalid") from exc
    return value


def _snapshot_timestamps(
    observed_value: Any,
    finished_value: Any,
    *,
    sanitize: bool,
) -> tuple[str | None, str | None, bool]:
    try:
        observed = _timestamp(observed_value, optional=True)
        finished = _timestamp(finished_value, optional=True)
    except DeviceCurrentContextSerializationError:
        if sanitize:
            return None, None, True
        raise
    if observed is None or finished is None:
        if sanitize:
            return None, None, True
        return observed, finished, False
    observed_at = datetime.strptime(observed, "%Y-%m-%dT%H:%M:%S.%fZ")
    finished_at = datetime.strptime(finished, "%Y-%m-%dT%H:%M:%S.%fZ")
    if finished_at < observed_at:
        if sanitize:
            return None, None, True
        raise DeviceCurrentContextSerializationError("capture interval is invalid")
    return observed, finished, False


def _identity(value: Any, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value or len(value) > 128:
        raise DeviceCurrentContextSerializationError("cycle identity is invalid")
    return value


def _number(value: Any, *, optional: bool = False, nonnegative: bool = False, positive: bool = False) -> float | int | None:
    if value is None and optional:
        return None
    if type(value) not in {int, float} or not math.isfinite(value):
        raise DeviceCurrentContextSerializationError("number is invalid")
    if (nonnegative and value < 0) or (positive and value <= 0):
        raise DeviceCurrentContextSerializationError("number is invalid")
    return value


def _integer(value: Any, *, nonnegative: bool = False) -> int | None:
    if value is None:
        return None
    if type(value) is not int or (nonnegative and value < 0):
        raise DeviceCurrentContextSerializationError("integer is invalid")
    return value


def _text(value: Any, *, required: bool = False) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or (required and not value):
        raise DeviceCurrentContextSerializationError("text is invalid")
    return value


def _mac(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or _MAC.fullmatch(value) is None:
        raise DeviceCurrentContextSerializationError("MAC is invalid")
    return value
