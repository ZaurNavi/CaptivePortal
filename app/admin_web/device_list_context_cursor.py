"""Authenticated immutable pagination context for the Device list overlay."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import math
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Mapping

from app.current_state.normalizer import canonical_scope

from .cursors import filter_fingerprint


_VERSION = 1
_KIND = "devices_context"
_ORDERING_CONTRACT_VERSION = 1
_SITE = re.compile(r"[0-9a-f]{24}")
_HASH = re.compile(r"[0-9a-f]{64}")
_TOKEN_SEGMENT = re.compile(r"[A-Za-z0-9_-]+")
_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z")
_FIELDS = {
    "version", "kind", "site_id", "filter_fingerprint",
    "ordering_contract_version", "overlay_mode", "evaluated_at_utc",
    "source_execution_status", "scope", "snapshot", "current_cycle_id",
    "source_scope_hash", "last_online_rank", "last_site_last_seen_at",
    "last_device_id",
}
_SNAPSHOT_FIELDS = {
    "observed_at", "capture_finished_at", "age_seconds", "freshness_status",
    "freshness_reason", "complete",
}
_FRESHNESS_REASONS = {
    "within_freshness_window", "older_than_freshness_window",
    "older_than_unavailable_threshold", "no_complete_snapshot",
    "clock_anomaly", "invalid_timestamp", "invalid_source_scope",
}


class DeviceListContextCursorError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DeviceListContextCursor:
    version: int
    kind: str
    site_id: str
    filter_fingerprint: str
    ordering_contract_version: int
    overlay_mode: str
    evaluated_at_utc: str
    source_execution_status: str
    scope: dict | None
    snapshot: dict | None
    current_cycle_id: str | None
    source_scope_hash: str | None
    last_online_rank: int
    last_site_last_seen_at: str
    last_device_id: str


class DeviceListContextCursorCodec:
    def __init__(self, *, secret_key: bytes, maximum_length: int):
        if not isinstance(secret_key, bytes) or len(secret_key) != 32:
            raise DeviceListContextCursorError("cursor secret is invalid")
        if type(maximum_length) is not int or maximum_length <= 0:
            raise DeviceListContextCursorError("cursor maximum is invalid")
        self._secret_key = secret_key
        self._maximum_length = maximum_length

    def encode(self, value: DeviceListContextCursor) -> str:
        payload = _validated_payload(value)
        raw = _canonical(payload)
        signature = hmac.new(self._secret_key, raw, hashlib.sha256).digest()
        token = f"{_b64(raw)}.{_b64(signature)}"
        if len(token) > self._maximum_length:
            raise DeviceListContextCursorError("cursor is too long")
        return token

    def decode(self, value, *, site_id, filters) -> DeviceListContextCursor | None:
        if value is None:
            return None
        if (
            not isinstance(value, str)
            or not value
            or len(value) > self._maximum_length
            or value.count(".") != 1
        ):
            raise DeviceListContextCursorError("cursor is malformed")
        payload_segment, signature_segment = value.split(".")
        if not payload_segment or not signature_segment:
            raise DeviceListContextCursorError("cursor is malformed")
        raw = _strict_b64(payload_segment)
        signature = _strict_b64(signature_segment)
        if len(signature) != hashlib.sha256().digest_size:
            raise DeviceListContextCursorError("cursor is malformed")
        expected = hmac.new(self._secret_key, raw, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise DeviceListContextCursorError("cursor signature is invalid")
        try:
            payload = json.loads(raw.decode("ascii"))
        except (UnicodeError, ValueError, json.JSONDecodeError) as exc:
            raise DeviceListContextCursorError("cursor is malformed") from exc
        if not isinstance(payload, dict) or set(payload) != _FIELDS:
            raise DeviceListContextCursorError("cursor is malformed")
        try:
            cursor = DeviceListContextCursor(**payload)
        except TypeError as exc:
            raise DeviceListContextCursorError("cursor is malformed") from exc
        canonical = _validated_payload(cursor)
        if (
            cursor.version != _VERSION
            or cursor.kind != _KIND
            or cursor.site_id != site_id
            or cursor.filter_fingerprint != filter_fingerprint(filters)
            or cursor.ordering_contract_version != _ORDERING_CONTRACT_VERSION
        ):
            raise DeviceListContextCursorError("cursor context is invalid")
        if _canonical(canonical) != raw:
            raise DeviceListContextCursorError("cursor is not canonical")
        if f"{_b64(raw)}.{_b64(signature)}" != value:
            raise DeviceListContextCursorError("cursor is not canonical")
        return cursor


def _validated_payload(value: DeviceListContextCursor) -> dict[str, Any]:
    if not isinstance(value, DeviceListContextCursor):
        raise DeviceListContextCursorError("cursor value is invalid")
    payload = asdict(value)
    if set(payload) != _FIELDS:
        raise DeviceListContextCursorError("cursor fields are invalid")
    if type(value.version) is not int or type(value.ordering_contract_version) is not int:
        raise DeviceListContextCursorError("cursor version is invalid")
    if (
        value.version != _VERSION
        or value.kind != _KIND
        or value.ordering_contract_version != _ORDERING_CONTRACT_VERSION
    ):
        raise DeviceListContextCursorError("cursor contract is invalid")
    if not isinstance(value.site_id, str) or _SITE.fullmatch(value.site_id) is None:
        raise DeviceListContextCursorError("cursor Site is invalid")
    if (
        not isinstance(value.filter_fingerprint, str)
        or _HASH.fullmatch(value.filter_fingerprint) is None
    ):
        raise DeviceListContextCursorError("cursor filter is invalid")
    _timestamp(value.evaluated_at_utc)
    _timestamp(value.last_site_last_seen_at)
    try:
        if str(uuid.UUID(value.last_device_id)) != value.last_device_id:
            raise ValueError
    except (AttributeError, TypeError, ValueError) as exc:
        raise DeviceListContextCursorError("cursor device identity is invalid") from exc
    if value.overlay_mode not in {"trusted", "unknown"}:
        raise DeviceListContextCursorError("cursor overlay mode is invalid")
    if value.source_execution_status not in {"available", "unavailable"}:
        raise DeviceListContextCursorError("cursor source status is invalid")
    if type(value.last_online_rank) is not int or value.last_online_rank not in {0, 1}:
        raise DeviceListContextCursorError("cursor online rank is invalid")
    scope, scope_hash = _scope(value.scope, value.site_id)
    snapshot = _snapshot(value.snapshot)
    cycle = value.current_cycle_id
    source_hash = value.source_scope_hash
    if value.overlay_mode == "trusted":
        if (
            value.source_execution_status != "available"
            or scope is None
            or snapshot is None
            or snapshot["freshness_status"] != "fresh"
            or snapshot["freshness_reason"] != "within_freshness_window"
            or snapshot["complete"] is not True
            or not isinstance(cycle, str)
            or not cycle
            or len(cycle) > 128
            or not isinstance(source_hash, str)
            or _HASH.fullmatch(source_hash) is None
            or source_hash != scope_hash
        ):
            raise DeviceListContextCursorError("trusted cursor is contradictory")
    elif value.source_execution_status == "available":
        if (
            scope is None
            or snapshot is None
            or snapshot["freshness_status"] == "fresh"
            or cycle is not None
            or source_hash is not None
            or value.last_online_rank != 1
        ):
            raise DeviceListContextCursorError("unknown cursor is contradictory")
    elif (
        snapshot is not None
        or cycle is not None
        or source_hash is not None
        or value.last_online_rank != 1
    ):
        raise DeviceListContextCursorError("unavailable cursor is contradictory")
    payload["scope"] = scope
    payload["snapshot"] = snapshot
    return payload


def _scope(value: Any, site_id: str) -> tuple[dict[str, Any] | None, str | None]:
    if value is None:
        return None, None
    if not isinstance(value, Mapping) or set(value) != {"scope_type", "site_id", "ssids"}:
        raise DeviceListContextCursorError("cursor scope is invalid")
    ssids = value.get("ssids")
    if (
        value.get("scope_type") != "client_ssid_allowlist"
        or value.get("site_id") != site_id
        or not isinstance(ssids, list)
        or not ssids
        or any(not isinstance(item, str) or not item for item in ssids)
        or ssids != sorted(set(ssids))
    ):
        raise DeviceListContextCursorError("cursor scope is invalid")
    scope_json, scope_hash = canonical_scope("client", site_id, tuple(ssids))
    canonical = json.loads(scope_json)
    if dict(value) != canonical:
        raise DeviceListContextCursorError("cursor scope is not canonical")
    return canonical, scope_hash


def _snapshot(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) != _SNAPSHOT_FIELDS:
        raise DeviceListContextCursorError("cursor snapshot is invalid")
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
        raise DeviceListContextCursorError("cursor snapshot is invalid")
    observed = value.get("observed_at")
    finished = value.get("capture_finished_at")
    if observed is not None:
        _timestamp(observed)
    if finished is not None:
        _timestamp(finished)
    if (observed is None) != (finished is None):
        raise DeviceListContextCursorError("cursor snapshot is invalid")
    if observed is not None and datetime.strptime(finished, "%Y-%m-%dT%H:%M:%S.%fZ") < datetime.strptime(observed, "%Y-%m-%dT%H:%M:%S.%fZ"):
        raise DeviceListContextCursorError("cursor snapshot is invalid")
    valid_pair = (
        (freshness == "fresh" and reason == "within_freshness_window")
        or (freshness == "stale" and reason == "older_than_freshness_window")
        or (
            freshness == "unavailable"
            and reason in _FRESHNESS_REASONS - {"within_freshness_window", "older_than_freshness_window"}
        )
    )
    if not valid_pair or (freshness == "fresh" and complete is not True):
        raise DeviceListContextCursorError("cursor snapshot is invalid")
    if complete is False and (observed is not None or age is not None):
        raise DeviceListContextCursorError("cursor snapshot is invalid")
    if complete is True and reason not in {"invalid_timestamp", "invalid_source_scope"}:
        if observed is None or age is None:
            raise DeviceListContextCursorError("cursor snapshot is invalid")
    if reason in {"invalid_timestamp", "invalid_source_scope"} and (
        observed is not None or finished is not None or age is not None
    ):
        raise DeviceListContextCursorError("cursor snapshot is invalid")
    return dict(value)


def _timestamp(value: Any) -> str:
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        raise DeviceListContextCursorError("cursor timestamp is invalid")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError as exc:
        raise DeviceListContextCursorError("cursor timestamp is invalid") from exc
    canonical = parsed.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    if canonical != value:
        raise DeviceListContextCursorError("cursor timestamp is invalid")
    return value


def _canonical(payload: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(
            dict(payload), ensure_ascii=True, allow_nan=False,
            separators=(",", ":"), sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise DeviceListContextCursorError("cursor is not serializable") from exc


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _strict_b64(value: str) -> bytes:
    if _TOKEN_SEGMENT.fullmatch(value) is None:
        raise DeviceListContextCursorError("cursor is malformed")
    try:
        return base64.b64decode(
            value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
        )
    except (binascii.Error, ValueError, TypeError) as exc:
        raise DeviceListContextCursorError("cursor is malformed") from exc
