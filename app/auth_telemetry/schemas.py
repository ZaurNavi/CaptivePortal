"""Record normalization and secret-safe serialization helpers."""

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any


MAX_ERROR_LENGTH = 512
_DENIED_KEY_PARTS = (
    "token",
    "secret",
    "password",
    "authorization",
    "cookie",
    "credential",
    "environment",
    "traceback",
    "requestbody",
    "responsebody",
    "headers",
)


def utc_timestamp() -> str:
    now = datetime.now(timezone.utc)
    return now.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def normalize_mac(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    clean = re.sub(r"[:.\-\s]", "", value).upper()
    if not re.fullmatch(r"[0-9A-F]{12}", clean):
        return value
    return ":".join(clean[index:index + 2] for index in range(0, 12, 2))


def sanitize_text(value: Any, limit: int | None = None) -> str:
    text = str(value)
    text = re.sub(
        r"(?i)\b(access[_ -]?token|client[_ -]?secret|authorization|"
        r"cookie|password)\b\s*[:=]\s*[^\s,;]+",
        r"\1=[REDACTED]",
        text,
    )
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if limit is not None:
        text = text[:limit]
    return text


def _denied_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", key.lower())
    return any(part in normalized for part in _DENIED_KEY_PARTS)


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z")
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return sanitize_fields(value)
    return sanitize_text(value)


def sanitize_fields(fields: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for raw_key, raw_value in fields.items():
        key = str(raw_key)
        if _denied_key(key) or raw_value is None:
            continue
        if key in {"client_mac", "ap_mac"}:
            value = normalize_mac(raw_value)
        elif key in {"error", "omada_message"}:
            value = sanitize_text(raw_value, MAX_ERROR_LENGTH)
        else:
            value = _json_value(raw_value)
        if value != "":
            safe[key] = value
    return safe


def build_record(
    event: str,
    session_id: str,
    level: str,
    schema_version: int,
    fields: dict[str, Any],
) -> dict[str, Any]:
    record = sanitize_fields(fields)
    record.update({
        "timestamp": utc_timestamp(),
        "level": level.lower(),
        "service": "captive_portal",
        "module": "auth_telemetry",
        "event": sanitize_text(event),
        "schema_version": int(schema_version),
        "session_id": sanitize_text(session_id),
    })
    return record
