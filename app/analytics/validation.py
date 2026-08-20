"""Strict validation and canonical cursors for Analytics v1."""

from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from .config import AnalyticsConfig


UTC = timezone.utc
_UTC_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z"
)
_CURSOR_VERSION = 1
_MAX_CURSOR_LENGTH = 512


class AnalyticsQueryValidationError(ValueError):
    """A read query violates the Analytics v1 contract."""


def require_site(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AnalyticsQueryValidationError("site_id must be non-empty")
    return value.strip()


def parse_utc(value: Any, name: str) -> datetime:
    if not isinstance(value, str) or _UTC_PATTERN.fullmatch(value) is None:
        raise AnalyticsQueryValidationError(
            f"{name} must use YYYY-MM-DDTHH:MM:SS.mmmZ"
        )
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError as exc:
        raise AnalyticsQueryValidationError(
            f"{name} must be a valid UTC timestamp"
        ) from exc
    return parsed.replace(tzinfo=UTC)


def format_utc(value: datetime) -> str:
    return (
        value.astimezone(UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def query_range(
    config: AnalyticsConfig,
    from_utc: Any,
    to_utc: Any,
) -> tuple[str, str, datetime, datetime]:
    start = parse_utc(from_utc, "from_utc")
    end = parse_utc(to_utc, "to_utc")
    if start >= end:
        raise AnalyticsQueryValidationError(
            "from_utc must be before to_utc"
        )
    if end - start > timedelta(days=config.max_query_window_days):
        raise AnalyticsQueryValidationError("query window exceeds hard limit")
    return str(from_utc), str(to_utc), start, end


def query_limit(
    config: AnalyticsConfig,
    value: Any | None,
) -> int:
    selected = config.default_limit if value is None else value
    if type(selected) is not int or not 1 <= selected <= config.max_limit:
        raise AnalyticsQueryValidationError(
            f"limit must be between 1 and {config.max_limit}"
        )
    return selected


def encode_cursor(timestamp: str, identifier: str) -> str:
    raw = json.dumps(
        {"v": _CURSOR_VERSION, "t": timestamp, "i": identifier},
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(value: Any | None) -> tuple[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value or len(value) > _MAX_CURSOR_LENGTH:
        raise AnalyticsQueryValidationError("cursor is malformed")
    try:
        padding = "=" * (-len(value) % 4)
        raw = base64.b64decode(
            value + padding, altchars=b"-_", validate=True
        )
        payload = json.loads(raw.decode("ascii"))
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise AnalyticsQueryValidationError("cursor is malformed") from exc
    if (
        not isinstance(payload, dict)
        or set(payload) != {"v", "t", "i"}
        or payload["v"] != _CURSOR_VERSION
        or not isinstance(payload["i"], str)
        or not payload["i"]
    ):
        raise AnalyticsQueryValidationError("cursor is malformed")
    timestamp = str(payload["t"])
    parse_utc(timestamp, "cursor timestamp")
    return timestamp, payload["i"]
