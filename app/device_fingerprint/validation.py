"""Canonical envelope validation for passive fingerprint evidence."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

from app.common.mac import format_mac_colon, parse_mac

from .models import DeviceFingerprintValidationError

UTC = timezone.utc
_MACHINE = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
_SOURCE_KIND = re.compile(r"[a-z][a-z0-9_]{0,63}")
_VERSION = re.compile(r"[0-9A-Za-z][0-9A-Za-z._+-]{0,63}")
_SITE = re.compile(r"[0-9a-f]{24}")
_P2_KEYS = frozenset({"raw_packet", "packet_payload", "sni", "server_name", "dns_rrname", "fqdn_destination", "full_user_agent", "cookie", "authorization", "credential", "raw_headers"})


def validate_machine_id(value: Any) -> str:
    if not isinstance(value, str) or _MACHINE.fullmatch(value) is None:
        raise DeviceFingerprintValidationError("Invalid machine identifier")
    return value


def validate_source_kind(value: Any) -> str:
    if not isinstance(value, str) or _SOURCE_KIND.fullmatch(value) is None:
        raise DeviceFingerprintValidationError("Invalid source kind")
    return value


def validate_version(value: Any) -> str:
    if not isinstance(value, str) or _VERSION.fullmatch(value) is None:
        raise DeviceFingerprintValidationError("Invalid version")
    return value


def validate_site_id(value: Any) -> str:
    if not isinstance(value, str) or _SITE.fullmatch(value) is None:
        raise DeviceFingerprintValidationError("Invalid Site identifier")
    return value


def validate_uuid(value: Any) -> str:
    if not isinstance(value, str):
        raise DeviceFingerprintValidationError("Invalid UUID")
    try:
        parsed = str(uuid.UUID(value))
    except ValueError as exc:
        raise DeviceFingerprintValidationError("Invalid UUID") from exc
    if parsed != value:
        raise DeviceFingerprintValidationError("Invalid UUID")
    return value


def validate_mac(value: Any) -> str:
    try:
        return format_mac_colon(parse_mac(value))
    except ValueError as exc:
        raise DeviceFingerprintValidationError("Invalid MAC") from exc


def validate_ip(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise DeviceFingerprintValidationError("Invalid IP")
    try:
        parsed = str(ipaddress.ip_address(value))
    except ValueError as exc:
        raise DeviceFingerprintValidationError("Invalid IP") from exc
    return parsed


def parse_utc(value: Any) -> datetime:
    if not isinstance(value, str) or len(value) != 24:
        raise DeviceFingerprintValidationError("Invalid timestamp")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
    except ValueError as exc:
        raise DeviceFingerprintValidationError("Invalid timestamp") from exc
    if format_utc(parsed) != value:
        raise DeviceFingerprintValidationError("Invalid timestamp")
    return parsed


def format_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def validate_observed_at(value: Any, *, now: datetime, max_future_skew_seconds: int, max_delayed_event_age_seconds: int) -> str:
    parsed = parse_utc(value)
    current = now.astimezone(UTC)
    if (parsed - current).total_seconds() > max_future_skew_seconds:
        raise DeviceFingerprintValidationError("Timestamp is in the future")
    if (current - parsed).total_seconds() > max_delayed_event_age_seconds:
        raise DeviceFingerprintValidationError("Timestamp is too old")
    return value


def validate_nullable_machine_id(value: Any) -> str | None:
    return None if value is None else validate_machine_id(value)


def validate_reason_code(value: Any) -> str | None:
    return None if value is None else validate_machine_id(value)


def validate_quality(value: Any) -> str:
    if value not in {"valid", "partial", "degraded"}:
        raise DeviceFingerprintValidationError("Invalid quality state")
    return value


def validate_health_status(value: Any) -> str:
    if value not in {"available", "unavailable", "unsupported"}:
        raise DeviceFingerprintValidationError("Invalid source health status")
    return value


def validate_feature_schema_version(value: Any) -> int:
    if type(value) is not int or not 1 <= value <= 2_147_483_647:
        raise DeviceFingerprintValidationError("Invalid feature schema version")
    return value


def canonical_json(value: Mapping[str, Any]) -> str:
    _reject_forbidden(value)
    try:
        encoded = json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise DeviceFingerprintValidationError("Invalid canonical JSON") from exc
    return encoded


def canonical_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _reject_forbidden(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str) or key.lower() in _P2_KEYS:
                raise DeviceFingerprintValidationError("Forbidden payload field")
            _reject_forbidden(child)
    elif isinstance(value, list):
        for child in value:
            _reject_forbidden(child)
    elif isinstance(value, float) and not math.isfinite(value):
        raise DeviceFingerprintValidationError("Invalid numeric payload value")
