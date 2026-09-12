"""Strict public serialization for the Device list Current State overlay."""

from __future__ import annotations

import math
import re
import uuid
from datetime import datetime
from typing import Any, Mapping

from app.common.device_type import normalize_device_type_key
from app.current_state.models import CurrentSnapshotMeta
from app.current_state.normalizer import canonical_scope


_SITE = re.compile(r"[0-9a-f]{24}")
_MAC = re.compile(r"[0-9A-F]{2}(?::[0-9A-F]{2}){5}")
_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z")
_OVERLAY_KEYS = {
    "overlay_mode", "ordering_applied", "source_execution_status",
    "evaluated_at_utc", "scope", "snapshot",
}
_SNAPSHOT_KEYS = {
    "observed_at", "capture_finished_at", "age_seconds", "freshness_status",
    "freshness_reason", "complete",
}
_SOURCE_ITEM_KEYS = {
    "device_id", "canonical_mac", "hostname", "device_type",
    "site_first_seen_at", "site_last_seen_at", "site_snapshot_count",
    "site_visit_count", "last_site_ip", "last_site_ssid",
    "last_site_ap_mac", "current_presence",
}
_PUBLIC_ITEM_KEYS = _SOURCE_ITEM_KEYS | {"device_type_key"}
_FRESHNESS_REASONS = {
    "within_freshness_window", "older_than_freshness_window",
    "older_than_unavailable_threshold", "no_complete_snapshot",
    "clock_anomaly", "invalid_timestamp", "invalid_source_scope",
}


class DeviceListContextSerializationError(ValueError):
    pass


def serialize_device_list_context_overlay(
    *,
    site_id: str,
    overlay_mode: str,
    source_execution_status: str,
    evaluated_at_utc: str,
    scope,
    snapshot: CurrentSnapshotMeta | None,
) -> dict:
    """Construct sanitized chain metadata before list composition."""

    site = _site(site_id)
    evaluated = _timestamp(evaluated_at_utc)
    safe_scope = _scope(scope, site, optional=source_execution_status == "unavailable")
    if overlay_mode not in {"trusted", "unknown"}:
        raise DeviceListContextSerializationError("overlay mode is invalid")
    if source_execution_status not in {"available", "unavailable"}:
        raise DeviceListContextSerializationError("source status is invalid")
    if source_execution_status == "unavailable":
        if overlay_mode != "unknown" or snapshot is not None:
            raise DeviceListContextSerializationError("unavailable overlay is contradictory")
        snapshot_dto = None
    else:
        if not isinstance(snapshot, CurrentSnapshotMeta) or safe_scope is None:
            raise DeviceListContextSerializationError("overlay snapshot is invalid")
        if (
            snapshot.site_id != site
            or snapshot.kind != "client"
            or _timestamp(snapshot.evaluated_at) != evaluated
        ):
            raise DeviceListContextSerializationError("overlay snapshot is inconsistent")
        if (
            snapshot.source_scope is not None
            and dict(snapshot.source_scope) != safe_scope
            and snapshot.freshness_reason != "invalid_source_scope"
        ):
            raise DeviceListContextSerializationError("overlay scope is inconsistent")
        snapshot_dto = _snapshot(snapshot)
        trusted = (
            snapshot_dto["freshness_status"] == "fresh"
            and snapshot_dto["freshness_reason"] == "within_freshness_window"
            and snapshot_dto["complete"] is True
        )
        if (overlay_mode == "trusted") != trusted:
            raise DeviceListContextSerializationError("overlay evidence is contradictory")
    return {
        "overlay_mode": overlay_mode,
        "ordering_applied": overlay_mode == "trusted",
        "source_execution_status": source_execution_status,
        "evaluated_at_utc": evaluated,
        "scope": safe_scope,
        "snapshot": snapshot_dto,
    }


def serialize_device_list_context(*, site_id: str, items, overlay) -> dict:
    """Validate the exact Feature-ON Device list result shape."""

    site = _site(site_id)
    safe_overlay = _public_overlay(overlay, site)
    try:
        values = tuple(items)
    except TypeError as exc:
        raise DeviceListContextSerializationError("items are invalid") from exc
    serialized = [_item(item) for item in values]
    expected_presence = (
        {"online", "offline"}
        if safe_overlay["overlay_mode"] == "trusted"
        else {"unknown"}
    )
    if any(item["current_presence"] not in expected_presence for item in serialized):
        raise DeviceListContextSerializationError("item presence contradicts overlay")
    return {"items": serialized, "current_state_overlay": safe_overlay}


def _public_overlay(value: Any, site_id: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _OVERLAY_KEYS:
        raise DeviceListContextSerializationError("overlay is invalid")
    mode = value.get("overlay_mode")
    status = value.get("source_execution_status")
    if mode not in {"trusted", "unknown"} or status not in {"available", "unavailable"}:
        raise DeviceListContextSerializationError("overlay is invalid")
    if type(value.get("ordering_applied")) is not bool or value["ordering_applied"] != (mode == "trusted"):
        raise DeviceListContextSerializationError("overlay ordering is invalid")
    evaluated = _timestamp(value.get("evaluated_at_utc"))
    scope = _scope(value.get("scope"), site_id, optional=status == "unavailable")
    snapshot = value.get("snapshot")
    if status == "unavailable":
        if mode != "unknown" or snapshot is not None:
            raise DeviceListContextSerializationError("overlay is contradictory")
    else:
        if scope is None or not isinstance(snapshot, Mapping) or set(snapshot) != _SNAPSHOT_KEYS:
            raise DeviceListContextSerializationError("overlay is contradictory")
        snapshot = _snapshot_dict(snapshot)
        trusted = (
            snapshot["freshness_status"] == "fresh"
            and snapshot["freshness_reason"] == "within_freshness_window"
            and snapshot["complete"] is True
        )
        if (mode == "trusted") != trusted:
            raise DeviceListContextSerializationError("overlay is contradictory")
    return {
        "overlay_mode": mode,
        "ordering_applied": value["ordering_applied"],
        "source_execution_status": status,
        "evaluated_at_utc": evaluated,
        "scope": scope,
        "snapshot": None if snapshot is None else dict(snapshot),
    }


def _snapshot(value: CurrentSnapshotMeta) -> dict[str, Any]:
    freshness = value.freshness_status
    reason = value.freshness_reason
    sanitize = freshness == "unavailable" and reason in {
        "invalid_timestamp", "invalid_source_scope",
    }
    try:
        observed = _timestamp(value.observed_at, optional=True)
        finished = _timestamp(value.capture_finished_at, optional=True)
        if observed is not None and finished is not None:
            if _parsed(finished) < _parsed(observed):
                raise DeviceListContextSerializationError("snapshot interval is invalid")
    except DeviceListContextSerializationError:
        if not sanitize:
            raise
        observed = finished = None
    age = value.age_seconds
    if sanitize:
        observed = finished = None
        age = None
    result = {
        "observed_at": observed,
        "capture_finished_at": finished,
        "age_seconds": age,
        "freshness_status": freshness,
        "freshness_reason": reason,
        "complete": value.complete,
    }
    return _snapshot_dict(result)


def _snapshot_dict(value: Mapping[str, Any]) -> dict[str, Any]:
    if set(value) != _SNAPSHOT_KEYS:
        raise DeviceListContextSerializationError("snapshot is invalid")
    freshness = value.get("freshness_status")
    reason = value.get("freshness_reason")
    complete = value.get("complete")
    age = value.get("age_seconds")
    if (
        freshness not in {"fresh", "stale", "unavailable"}
        or reason not in _FRESHNESS_REASONS
        or type(complete) is not bool
        or (
            age is not None
            and (type(age) not in {int, float} or not math.isfinite(age) or age < 0)
        )
    ):
        raise DeviceListContextSerializationError("snapshot is invalid")
    observed = _timestamp(value.get("observed_at"), optional=True)
    finished = _timestamp(value.get("capture_finished_at"), optional=True)
    if (observed is None) != (finished is None):
        raise DeviceListContextSerializationError("snapshot is invalid")
    if observed is not None and _parsed(finished) < _parsed(observed):
        raise DeviceListContextSerializationError("snapshot is invalid")
    valid_pair = (
        (freshness == "fresh" and reason == "within_freshness_window")
        or (freshness == "stale" and reason == "older_than_freshness_window")
        or (
            freshness == "unavailable"
            and reason in _FRESHNESS_REASONS - {"within_freshness_window", "older_than_freshness_window"}
        )
    )
    if not valid_pair or (freshness == "fresh" and complete is not True):
        raise DeviceListContextSerializationError("snapshot is invalid")
    if complete is False and (observed is not None or age is not None):
        raise DeviceListContextSerializationError("snapshot is invalid")
    if complete is True and reason not in {"invalid_timestamp", "invalid_source_scope"}:
        if observed is None or age is None:
            raise DeviceListContextSerializationError("snapshot is invalid")
    if reason in {"invalid_timestamp", "invalid_source_scope"} and (
        observed is not None or finished is not None or age is not None
    ):
        raise DeviceListContextSerializationError("snapshot is invalid")
    return dict(value)


def _item(value: Any) -> dict[str, Any]:
    if hasattr(value, "__dataclass_fields__"):
        source = {
            name: getattr(value, name)
            for name in _SOURCE_ITEM_KEYS
        }
    elif isinstance(value, Mapping):
        source = dict(value)
    else:
        raise DeviceListContextSerializationError("item is invalid")
    if set(source) != _SOURCE_ITEM_KEYS:
        raise DeviceListContextSerializationError("item fields are invalid")
    try:
        if str(uuid.UUID(source["device_id"])) != source["device_id"]:
            raise ValueError
    except (AttributeError, TypeError, ValueError) as exc:
        raise DeviceListContextSerializationError("device identity is invalid") from exc
    if not isinstance(source["canonical_mac"], str) or _MAC.fullmatch(source["canonical_mac"]) is None:
        raise DeviceListContextSerializationError("device MAC is invalid")
    for name in ("hostname", "device_type", "last_site_ip", "last_site_ssid"):
        if source[name] is not None and not isinstance(source[name], str):
            raise DeviceListContextSerializationError(f"{name} is invalid")
    _timestamp(source["site_first_seen_at"])
    _timestamp(source["site_last_seen_at"])
    for name in ("site_snapshot_count", "site_visit_count"):
        if type(source[name]) is not int or source[name] < 0:
            raise DeviceListContextSerializationError(f"{name} is invalid")
    ap_mac = source["last_site_ap_mac"]
    if ap_mac is not None and (not isinstance(ap_mac, str) or _MAC.fullmatch(ap_mac) is None):
        raise DeviceListContextSerializationError("last Site AP MAC is invalid")
    if source["current_presence"] not in {"online", "offline", "unknown"}:
        raise DeviceListContextSerializationError("current presence is invalid")
    result = dict(source)
    result["device_type_key"] = normalize_device_type_key(
        source["device_type"]
    )
    if set(result) != _PUBLIC_ITEM_KEYS:
        raise DeviceListContextSerializationError("public item fields are invalid")
    return result


def _scope(value: Any, site_id: str, *, optional: bool) -> dict[str, Any] | None:
    if value is None and optional:
        return None
    if not isinstance(value, Mapping) or set(value) != {"scope_type", "site_id", "ssids"}:
        raise DeviceListContextSerializationError("scope is invalid")
    ssids = value.get("ssids")
    if (
        value.get("scope_type") != "client_ssid_allowlist"
        or value.get("site_id") != site_id
        or not isinstance(ssids, (list, tuple))
        or not ssids
        or any(not isinstance(item, str) or not item for item in ssids)
        or list(ssids) != sorted(set(ssids))
    ):
        raise DeviceListContextSerializationError("scope is invalid")
    canonical_json, _hash = canonical_scope("client", site_id, tuple(ssids))
    import json
    canonical = json.loads(canonical_json)
    if dict(value) != canonical:
        raise DeviceListContextSerializationError("scope is invalid")
    return canonical


def _site(value: Any) -> str:
    if not isinstance(value, str) or _SITE.fullmatch(value) is None:
        raise DeviceListContextSerializationError("Site identity is invalid")
    return value


def _timestamp(value: Any, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        raise DeviceListContextSerializationError("timestamp is invalid")
    parsed = _parsed(value)
    if parsed.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z" != value:
        raise DeviceListContextSerializationError("timestamp is invalid")
    return value


def _parsed(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError as exc:
        raise DeviceListContextSerializationError("timestamp is invalid") from exc
