"""Pure normalization of captured Omada webhook records."""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from decimal import (
    Decimal,
    InvalidOperation,
    ROUND_HALF_UP,
    localcontext,
)
from ipaddress import ip_address
from typing import Any, NamedTuple


SCHEMA_VERSION = 1
MODULE_NAME = "omada_webhook_normalizer"

MIN_CONTROLLER_TIMESTAMP_MS = 946_684_800_000
MAX_CONTROLLER_TIMESTAMP_MS = 4_102_444_800_000
MAX_DURATION_COMPONENT_DIGITS = 12
MAX_TRAFFIC_NUMBER_DIGITS = 24
MAX_OCCURRENCE_COUNT = 999_999

MAC_PATTERN = r"(?:[0-9A-Fa-f]{2}[-:]){5}[0-9A-Fa-f]{2}"
MAC_RE = re.compile(rf"^{MAC_PATTERN}$")
NAMED_MAC_RE = re.compile(
    rf"^(?:(?P<name>.*):)?(?P<mac>{MAC_PATTERN})$"
)
CLIENT_BLOCK_RE = re.compile(
    r"\[client:(?P<body>[^\]]*)\]",
    re.IGNORECASE,
)
AP_BLOCK_RE = re.compile(
    r"\[ap:(?P<body>[^\]]*)\]",
    re.IGNORECASE,
)
IP_RE = re.compile(
    r"\(\s*IP\s*:\s*(?P<ip>[^)]*)\)",
    re.IGNORECASE,
)
ONLINE_RE = re.compile(r"\bwent\s+online\b", re.IGNORECASE)
OFFLINE_RE = re.compile(r"\bwent\s+offline\b", re.IGNORECASE)
UNAUTHORIZED_RE = re.compile(
    r"\bwas\s+unauthorized\s+by\s+Main\s+Administrator\b",
    re.IGNORECASE,
)
FAILED_TO_CONNECT_RE = re.compile(
    r"\bfailed\s+to\s+connect\b",
    re.IGNORECASE,
)
ACCESS_POLICY_BLOCKED_RE = re.compile(
    r"\bbecause\s+the\s+user\s+was\s+blocked\s+by\s+"
    r"(?P<reason>"
    r"MAC\s+block\s*/\s*MAC\s+Filter\s*/\s*Lock\s+To\s+AP"
    r")\b",
    re.IGNORECASE | re.DOTALL,
)
WRONG_PASSWORD_RE = re.compile(
    r"\bbecause\s+the\s+"
    r"(?P<reason>password\s+was\s+wrong)\b",
    re.IGNORECASE | re.DOTALL,
)
ONLINE_SSID_RE = re.compile(
    r'\bwith\s+SSID\s+"(?P<ssid>[^"]*)"',
    re.IGNORECASE,
)
OFFLINE_SSID_RE = re.compile(
    r'\bfrom\s+SSID\s+"(?P<ssid>[^"]*)"',
    re.IGNORECASE,
)
CHANNEL_RE = re.compile(
    r"\bon\s+channel\s+(?P<channel>[^\s.]+)",
    re.IGNORECASE,
)
DURATION_SOURCE_RE = re.compile(
    r"\(\s*(?P<duration>[^,()]+?)\s+connected(?:\s*,|\s*\))",
    re.IGNORECASE,
)
TRAFFIC_SOURCE_RE = re.compile(
    r"\bconnected\s*,\s*(?P<traffic>[^)]+?)\s*\)",
    re.IGNORECASE,
)
DURATION_RE = re.compile(
    r"^(?:(?P<hours>\d+)h)?"
    r"(?:(?P<minutes>\d+)m)?"
    r"(?:(?P<seconds>\d+)s)?$",
    re.IGNORECASE,
)
TRAFFIC_RE = re.compile(
    r"^(?P<value>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>B|KB|MB|GB|TB)$",
    re.IGNORECASE,
)
ADMINISTRATOR_RE = re.compile(
    r"\bwas\s+unauthorized\s+by\s+Main\s+Administrator"
    r"\s+(?P<administrator>.+?)\s*\.\s*$",
    re.IGNORECASE | re.DOTALL,
)
OCCURRENCE_RE = re.compile(
    r"^(?:(?P<count>\S+)\s+)?"
    r"times?"
    r"(?:\s+in\s+the(?:\s+(?P<window>.*?))?)?$",
    re.IGNORECASE | re.DOTALL,
)
TECHNICAL_OCCURRENCE_TAIL_RE = re.compile(
    r"^(?:\S+\s+)?times?"
    r"(?:\s+in\s+the(?:\s+last\s+"
    r"(?:minute|hour|\d+\s+(?:minutes?|hours?)))?)?$",
    re.IGNORECASE | re.DOTALL,
)
LEGACY_ATTEMPTS_RECENTLY_RE = re.compile(
    r"^[+-]?\d+\s+attempts?\s+recently$",
    re.IGNORECASE | re.DOTALL,
)

TRAFFIC_MULTIPLIERS = {
    "B": 1,
    "KB": 1024,
    "MB": 1024**2,
    "GB": 1024**3,
    "TB": 1024**4,
}

EventParser = Callable[
    [str],
    tuple[dict[str, Any], list[str]],
]
EventMatcher = Callable[[str], bool]


class ConnectionFailureReason(NamedTuple):
    """One exact controller reason and its normalized meaning."""

    failure_reason: str
    pattern: re.Pattern[str]


class EventHandler(NamedTuple):
    """One deterministic text classifier and its parser."""

    event_name: str
    matcher: EventMatcher
    parser: EventParser

    def matches(self, raw_text: str) -> bool:
        return self.matcher(raw_text)


def _regex_matcher(pattern: re.Pattern[str]) -> EventMatcher:
    def matches(raw_text: str) -> bool:
        return pattern.search(raw_text) is not None

    return matches


CONNECTION_FAILURE_REASONS: tuple[
    ConnectionFailureReason,
    ...,
] = (
    ConnectionFailureReason(
        "ACCESS_POLICY_BLOCKED",
        ACCESS_POLICY_BLOCKED_RE,
    ),
    ConnectionFailureReason(
        "WRONG_PASSWORD",
        WRONG_PASSWORD_RE,
    ),
)


def normalize_webhook(raw_record: dict[str, Any]) -> list[dict[str, Any]]:
    """Return one normalized event for every item in ``text``."""
    if not isinstance(raw_record, dict):
        raise TypeError("raw_record must be a dictionary")

    payload = raw_record.get("parsed_payload")
    if not isinstance(payload, dict):
        return [
            _diagnostic_event(
                raw_record,
                reason="TEXT_MISSING",
                text_index=None,
                text_count=0,
                raw_text=None,
            )
        ]

    if "text" not in payload:
        return [
            _diagnostic_event(
                raw_record,
                reason="TEXT_MISSING",
                text_index=None,
                text_count=0,
                raw_text=None,
            )
        ]

    text_items = payload["text"]
    if not isinstance(text_items, list):
        return [
            _diagnostic_event(
                raw_record,
                reason="TEXT_INVALID_TYPE",
                text_index=None,
                text_count=0,
                raw_text=None,
            )
        ]

    if not text_items:
        return [
            _diagnostic_event(
                raw_record,
                reason="TEXT_EMPTY",
                text_index=None,
                text_count=0,
                raw_text=None,
            )
        ]

    normalized: list[dict[str, Any]] = []
    text_count = len(text_items)
    for text_index, item in enumerate(text_items):
        if not isinstance(item, str):
            normalized.append(
                _diagnostic_event(
                    raw_record,
                    reason="TEXT_ITEM_INVALID_TYPE",
                    text_index=text_index,
                    text_count=text_count,
                    raw_text=None,
                )
            )
            continue
        if not item.strip():
            normalized.append(
                _diagnostic_event(
                    raw_record,
                    reason="TEXT_ITEM_EMPTY",
                    text_index=text_index,
                    text_count=text_count,
                    raw_text=item,
                )
            )
            continue
        normalized.append(
            _normalize_text_item(
                raw_record,
                raw_text=item,
                text_index=text_index,
                text_count=text_count,
            )
        )
    return normalized


def _normalize_text_item(
    raw_record: dict[str, Any],
    *,
    raw_text: str,
    text_index: int,
    text_count: int,
) -> dict[str, Any]:
    handler = next(
        (
            candidate
            for candidate in EVENT_HANDLERS
            if candidate.matches(raw_text)
        ),
        None,
    )
    if handler is None:
        return _diagnostic_event(
            raw_record,
            reason="UNKNOWN_TEXT_FORMAT",
            text_index=text_index,
            text_count=text_count,
            raw_text=raw_text,
        )

    fields, warnings = handler.parser(raw_text)

    time_fields, time_warnings = _controller_time_fields(raw_record)
    warnings = _unique(warnings + time_warnings)
    parse_status = "partial" if warnings else "parsed"
    event = _common_event(
        raw_record,
        event_name=handler.event_name,
        text_index=text_index,
        text_count=text_count,
        raw_text=raw_text,
        parse_status=parse_status,
        parse_reason=None,
        parse_warnings=warnings,
        time_fields=time_fields,
    )
    event.update(fields)
    return event


def _parse_online(raw_text: str) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    fields = _empty_connection_fields()
    _apply_client(fields, warnings, raw_text)
    _apply_ip(fields, warnings, raw_text)
    _apply_ap(fields, warnings, raw_text)

    ssid_match = ONLINE_SSID_RE.search(raw_text)
    if ssid_match is None:
        warnings.append("SSID_MISSING")
    else:
        fields["ssid"] = ssid_match.group("ssid")

    _apply_channel(fields, warnings, raw_text)
    return fields, warnings


def _parse_offline(raw_text: str) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    fields = {
        **_empty_connection_fields(),
        **_empty_reported_fields(),
    }
    _apply_client(fields, warnings, raw_text)
    _apply_ip(fields, warnings, raw_text)
    _apply_ap(fields, warnings, raw_text)

    ssid_match = OFFLINE_SSID_RE.search(raw_text)
    if ssid_match is None:
        warnings.append("SSID_MISSING")
    else:
        fields["ssid"] = ssid_match.group("ssid")

    duration_match = DURATION_SOURCE_RE.search(raw_text)
    if duration_match is not None:
        duration_raw = duration_match.group("duration").strip()
        fields["reported_connected_raw"] = duration_raw
        duration_seconds = _parse_duration(duration_raw)
        if duration_seconds is None:
            warnings.append("DURATION_INVALID")
        else:
            fields["reported_connected_seconds"] = duration_seconds

    traffic_match = TRAFFIC_SOURCE_RE.search(raw_text)
    if traffic_match is not None:
        traffic_raw = traffic_match.group("traffic").strip()
        fields["reported_traffic_raw"] = traffic_raw
        traffic = _parse_traffic(traffic_raw)
        if traffic is None:
            warnings.append("TRAFFIC_INVALID")
        else:
            fields.update(traffic)
    return fields, warnings


def _parse_unauthorized(
    raw_text: str,
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    connection_fields = _empty_connection_fields()
    _apply_client(connection_fields, warnings, raw_text)
    administrator_match = ADMINISTRATOR_RE.search(raw_text)
    administrator = None
    if administrator_match is None:
        warnings.append("ADMINISTRATOR_MISSING")
    else:
        administrator = administrator_match.group(
            "administrator"
        ).strip() or None
        if administrator is None:
            warnings.append("ADMINISTRATOR_MISSING")
    return {
        "client_mac": connection_fields["client_mac"],
        "client_mac_raw": connection_fields["client_mac_raw"],
        "administrator": administrator,
        "action": "unauthorize",
        "action_source": "omada_controller",
    }, warnings


def _parse_connection_failed(
    raw_text: str,
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    fields = _empty_failed_connection_fields()
    _apply_client(fields, warnings, raw_text)
    _apply_ap(fields, warnings, raw_text)

    ssid_match = ONLINE_SSID_RE.search(raw_text)
    if ssid_match is None:
        warnings.append("SSID_MISSING")
    else:
        fields["ssid"] = ssid_match.group("ssid")

    _apply_channel(fields, warnings, raw_text)

    reason_definition, reason_match = (
        _match_connection_failure_reason(raw_text)
    )
    fields["failure_reason"] = reason_definition.failure_reason
    fields["failure_source"] = "omada_controller"
    fields["controller_reason_raw"] = reason_match.group(
        "reason"
    ).strip()
    _apply_occurrence(
        fields,
        warnings,
        raw_text[reason_match.end():],
    )
    return fields, warnings


def _match_connection_failure_reason(
    raw_text: str,
) -> tuple[ConnectionFailureReason, re.Match[str]]:
    failed_match = FAILED_TO_CONNECT_RE.search(raw_text)
    if failed_match is None:
        raise ValueError("not a failed-to-connect event")
    for definition in CONNECTION_FAILURE_REASONS:
        reason_match = definition.pattern.search(
            raw_text,
            failed_match.end(),
        )
        if reason_match is not None:
            return definition, reason_match
    raise ValueError("unknown connection failure reason")


def _matches_connection_failed(raw_text: str) -> bool:
    try:
        _, reason_match = _match_connection_failure_reason(raw_text)
    except ValueError:
        return False
    return _is_technical_occurrence_tail(
        raw_text[reason_match.end():],
    )


def _is_technical_occurrence_tail(raw_tail: str) -> bool:
    block = _occurrence_block(raw_tail)
    if block is None:
        return True
    return (
        TECHNICAL_OCCURRENCE_TAIL_RE.fullmatch(block) is not None
        or LEGACY_ATTEMPTS_RECENTLY_RE.fullmatch(block) is not None
    )


# Registry order is classification priority. Keep this tuple explicit:
# adding a future Omada event requires only its parser, matcher, and
# one local registry entry; the central dispatch remains unchanged.
EVENT_HANDLERS: tuple[EventHandler, ...] = (
    EventHandler(
        "omada.client_unauthorized",
        _regex_matcher(UNAUTHORIZED_RE),
        _parse_unauthorized,
    ),
    EventHandler(
        "omada.client_online",
        _regex_matcher(ONLINE_RE),
        _parse_online,
    ),
    EventHandler(
        "omada.client_offline",
        _regex_matcher(OFFLINE_RE),
        _parse_offline,
    ),
    EventHandler(
        "omada.client_connection_failed",
        _matches_connection_failed,
        _parse_connection_failed,
    ),
)


def _apply_client(
    fields: dict[str, Any],
    warnings: list[str],
    raw_text: str,
) -> None:
    match = CLIENT_BLOCK_RE.search(raw_text)
    if match is None:
        warnings.append("INVALID_CLIENT_MAC")
        return
    parsed = _parse_named_mac(match.group("body"), subject="client")
    fields.update(parsed)
    if parsed["client_mac"] is None:
        warnings.append("INVALID_CLIENT_MAC")


def _apply_ap(
    fields: dict[str, Any],
    warnings: list[str],
    raw_text: str,
) -> None:
    match = AP_BLOCK_RE.search(raw_text)
    if match is None:
        warnings.append("AP_MAC_MISSING")
        return
    parsed = _parse_named_mac(match.group("body"), subject="ap")
    fields.update(parsed)
    if parsed["ap_mac"] is None:
        warnings.append("INVALID_AP_MAC")


def _apply_ip(
    fields: dict[str, Any],
    warnings: list[str],
    raw_text: str,
) -> None:
    match = IP_RE.search(raw_text)
    if match is None:
        warnings.append("CLIENT_IP_MISSING")
        return
    candidate = match.group("ip").strip()
    try:
        fields["client_ip"] = str(ip_address(candidate))
    except ValueError:
        warnings.append("INVALID_CLIENT_IP")


def _apply_channel(
    fields: dict[str, Any],
    warnings: list[str],
    raw_text: str,
) -> None:
    match = CHANNEL_RE.search(raw_text)
    if match is None:
        warnings.append("CHANNEL_MISSING")
        return
    try:
        fields["channel"] = int(match.group("channel"))
    except (TypeError, ValueError):
        warnings.append("CHANNEL_INVALID")


def _apply_occurrence(
    fields: dict[str, Any],
    warnings: list[str],
    raw_tail: str,
) -> None:
    block = _occurrence_block(raw_tail)
    if block is None:
        warnings.extend([
            "OCCURRENCE_COUNT_MISSING",
            "OCCURRENCE_WINDOW_MISSING",
        ])
        return

    match = OCCURRENCE_RE.fullmatch(block)
    if match is not None:
        count_raw = match.group("count")
        window_raw = match.group("window")
    else:
        parts = block.split(maxsplit=1)
        count_raw = parts[0] if parts else None
        window_raw = parts[1] if len(parts) == 2 else None

    _apply_occurrence_count(
        fields,
        warnings,
        count_raw,
    )
    if window_raw is None or not window_raw.strip():
        warnings.append("OCCURRENCE_WINDOW_MISSING")
    elif re.fullmatch(
        r"last\s+minute",
        window_raw.strip(),
        re.IGNORECASE,
    ):
        fields["occurrence_window_seconds"] = 60
    else:
        warnings.append("OCCURRENCE_WINDOW_INVALID")


def _occurrence_block(raw_tail: str) -> str | None:
    candidate = raw_tail.strip()
    candidate = candidate.lstrip(".").strip()
    candidate = candidate.rstrip(".").strip()
    if not candidate:
        return None
    if candidate.startswith("(") and candidate.endswith(")"):
        candidate = candidate[1:-1].strip()
    return candidate or None


def _apply_occurrence_count(
    fields: dict[str, Any],
    warnings: list[str],
    raw_value: str | None,
) -> None:
    if raw_value is None or not raw_value.strip():
        warnings.append("OCCURRENCE_COUNT_MISSING")
        return
    candidate = raw_value.strip()
    if (
        len(candidate) > len(str(MAX_OCCURRENCE_COUNT))
        or re.fullmatch(r"[0-9]+", candidate) is None
    ):
        warnings.append("OCCURRENCE_COUNT_INVALID")
        return
    try:
        value = int(candidate)
    except (ValueError, OverflowError):
        warnings.append("OCCURRENCE_COUNT_INVALID")
        return
    if not 1 <= value <= MAX_OCCURRENCE_COUNT:
        warnings.append("OCCURRENCE_COUNT_INVALID")
        return
    fields["occurrence_count"] = value


def _parse_named_mac(
    raw_value: str,
    *,
    subject: str,
) -> dict[str, Any]:
    prefix = f"{subject}_"
    fields = {
        f"{prefix}name": None,
        f"{prefix}name_raw": None,
        f"{prefix}name_available": False,
        f"{prefix}name_fallback": None,
        f"{prefix}mac": None,
        f"{prefix}mac_raw": None,
    }
    candidate = raw_value.strip()
    match = NAMED_MAC_RE.fullmatch(candidate)
    if match is None:
        if ":" in candidate:
            name_raw, mac_raw = candidate.rsplit(":", 1)
            name_raw = name_raw.strip()
            fields[f"{prefix}name_raw"] = name_raw or None
            if name_raw:
                fields[f"{prefix}name"] = name_raw
                fields[f"{prefix}name_available"] = True
            fields[f"{prefix}mac_raw"] = mac_raw.strip() or None
        else:
            fields[f"{prefix}mac_raw"] = candidate or None
        return fields

    mac_raw = match.group("mac")
    mac = normalize_mac(mac_raw)
    fields[f"{prefix}mac_raw"] = mac_raw
    fields[f"{prefix}mac"] = mac
    name_raw = match.group("name")
    if name_raw is None:
        fields[f"{prefix}name_fallback"] = "mac_only"
        return fields

    name_raw = name_raw.strip()
    fields[f"{prefix}name_raw"] = name_raw
    if normalize_mac(name_raw) == mac:
        fields[f"{prefix}name_fallback"] = "mac"
        return fields

    fields[f"{prefix}name"] = name_raw
    fields[f"{prefix}name_available"] = True
    return fields


def normalize_mac(value: Any) -> str | None:
    """Return an upper-case colon-delimited MAC or ``None``."""
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if MAC_RE.fullmatch(candidate) is None:
        return None
    return candidate.replace("-", ":").upper()


def _parse_duration(value: str) -> int | None:
    match = DURATION_RE.fullmatch(value.strip())
    if match is None or not any(match.groupdict().values()):
        return None
    parsed: dict[str, int] = {}
    for component in ("hours", "minutes", "seconds"):
        raw_component = match.group(component)
        if raw_component is None:
            parsed[component] = 0
            continue
        significant = raw_component.lstrip("0") or "0"
        if len(significant) > MAX_DURATION_COMPONENT_DIGITS:
            return None
        try:
            parsed[component] = int(significant)
        except (ValueError, OverflowError):
            return None
    return (
        parsed["hours"] * 3600
        + parsed["minutes"] * 60
        + parsed["seconds"]
    )


def _parse_traffic(value: str) -> dict[str, Any] | None:
    match = TRAFFIC_RE.fullmatch(value.strip())
    if match is None:
        return None
    raw_number = match.group("value")
    if (
        sum(character.isdigit() for character in raw_number)
        > MAX_TRAFFIC_NUMBER_DIGITS
    ):
        return None
    try:
        with localcontext() as context:
            context.prec = max(
                50,
                MAX_TRAFFIC_NUMBER_DIGITS + 20,
            )
            decimal_value = Decimal(raw_number)
            unit = match.group("unit").upper()
            byte_value = (
                decimal_value * TRAFFIC_MULTIPLIERS[unit]
            ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            if decimal_value == decimal_value.to_integral_value():
                json_value: int | float = int(decimal_value)
            else:
                json_value = float(decimal_value)
                if not math.isfinite(json_value):
                    return None
            byte_estimate = int(byte_value)
    except (InvalidOperation, ValueError, OverflowError):
        return None
    return {
        "reported_traffic_value": json_value,
        "reported_traffic_unit": unit,
        "reported_traffic_bytes_estimate": byte_estimate,
    }


def _controller_time_fields(
    raw_record: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    received_at, received_datetime, received_error = (
        _canonical_received_at(raw_record)
    )
    payload = raw_record.get("parsed_payload")
    raw_timestamp = (
        payload.get("timestamp")
        if isinstance(payload, dict)
        else None
    )
    timestamp_ms, error = _parse_controller_timestamp(raw_timestamp)
    fields = {
        "timestamp": received_at,
        "received_at": received_at,
        "controller_timestamp": None,
        "controller_timestamp_ms": None,
        "delivery_latency_ms": None,
    }
    warnings: list[str] = []
    if received_error is not None:
        warnings.append(received_error)
    if error is not None:
        warnings.append(error)
        return fields, warnings

    assert timestamp_ms is not None
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    controller_datetime = epoch + timedelta(milliseconds=timestamp_ms)
    fields["controller_timestamp"] = (
        controller_datetime.isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
    fields["controller_timestamp_ms"] = timestamp_ms

    if received_datetime is not None:
        received_delta = received_datetime - epoch
        received_ms = (
            received_delta.days * 86_400_000
            + received_delta.seconds * 1000
            + received_delta.microseconds // 1000
        )
        latency = received_ms - timestamp_ms
        fields["delivery_latency_ms"] = latency
        if latency < -100:
            warnings.append("NEGATIVE_DELIVERY_LATENCY")
        elif latency > 10_000:
            warnings.append("HIGH_DELIVERY_LATENCY")
    return fields, warnings


def _parse_controller_timestamp(
    value: Any,
) -> tuple[int | None, str | None]:
    if isinstance(value, bool):
        return None, "CONTROLLER_TIMESTAMP_INVALID"
    if isinstance(value, int):
        timestamp_ms = value
    elif isinstance(value, str) and re.fullmatch(r"\d+", value):
        significant = value.lstrip("0") or "0"
        if len(significant) > len(
            str(MAX_CONTROLLER_TIMESTAMP_MS)
        ):
            return None, "CONTROLLER_TIMESTAMP_OUT_OF_RANGE"
        try:
            timestamp_ms = int(significant)
        except (ValueError, OverflowError):
            return None, "CONTROLLER_TIMESTAMP_INVALID"
    else:
        return None, "CONTROLLER_TIMESTAMP_INVALID"

    if not (
        MIN_CONTROLLER_TIMESTAMP_MS
        <= timestamp_ms
        <= MAX_CONTROLLER_TIMESTAMP_MS
    ):
        return None, "CONTROLLER_TIMESTAMP_OUT_OF_RANGE"
    return timestamp_ms, None


def _canonical_received_at(
    raw_record: dict[str, Any],
) -> tuple[str | None, datetime | None, str | None]:
    if "received_at" not in raw_record:
        return None, None, "RECEIVED_AT_MISSING"
    value = raw_record.get("received_at")
    if not isinstance(value, str) or not value:
        return None, None, "RECEIVED_AT_INVALID"
    candidate = value
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
        if parsed.tzinfo is None:
            return None, None, "RECEIVED_AT_INVALID"
        parsed = parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None, None, "RECEIVED_AT_INVALID"
    canonical = (
        parsed.isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
    return canonical, parsed, None


def _diagnostic_event(
    raw_record: dict[str, Any],
    *,
    reason: str,
    text_index: int | None,
    text_count: int,
    raw_text: str | None,
) -> dict[str, Any]:
    time_fields, time_warnings = _controller_time_fields(raw_record)
    event = _common_event(
        raw_record,
        event_name="omada.webhook_unclassified",
        text_index=text_index,
        text_count=text_count,
        raw_text=raw_text,
        parse_status="unclassified",
        parse_reason=reason,
        parse_warnings=time_warnings,
        time_fields=time_fields,
    )
    event.update(_empty_unclassified_fields())
    return event


def _common_event(
    raw_record: dict[str, Any],
    *,
    event_name: str,
    text_index: int | None,
    text_count: int,
    raw_text: str | None,
    parse_status: str,
    parse_reason: str | None,
    parse_warnings: list[str],
    time_fields: dict[str, Any],
) -> dict[str, Any]:
    payload = raw_record.get("parsed_payload")
    payload = payload if isinstance(payload, dict) else {}
    webhook_id = _optional_string(raw_record.get("webhook_id"))
    event_id_suffix = "none" if text_index is None else str(text_index)
    id_prefix = webhook_id or (
        f"missing-{_optional_string(raw_record.get('payload_sha256')) or 'id'}"
    )
    return {
        "timestamp": time_fields["timestamp"],
        "level": (
            "info" if parse_status == "parsed" else "warning"
        ),
        "service": "captive_portal",
        "module": MODULE_NAME,
        "event": event_name,
        "schema_version": SCHEMA_VERSION,
        "normalized_event_id": f"{id_prefix}:{event_id_suffix}",
        "webhook_id": webhook_id,
        "text_index": text_index,
        "text_count": text_count,
        "received_at": time_fields["received_at"],
        "controller_timestamp": time_fields[
            "controller_timestamp"
        ],
        "controller_timestamp_ms": time_fields[
            "controller_timestamp_ms"
        ],
        "delivery_latency_ms": time_fields[
            "delivery_latency_ms"
        ],
        "source_ip": _optional_string(raw_record.get("source_ip")),
        "site": _optional_string(payload.get("Site")),
        "controller_name": _optional_string(
            payload.get("Controller")
        ),
        "payload_sha256": _optional_string(
            raw_record.get("payload_sha256")
        ),
        "parse_status": parse_status,
        "parse_reason": parse_reason,
        "parse_warnings": list(parse_warnings),
        "raw_text": raw_text,
    }


def _empty_connection_fields() -> dict[str, Any]:
    return {
        "client_name": None,
        "client_name_raw": None,
        "client_name_available": False,
        "client_name_fallback": None,
        "client_mac": None,
        "client_mac_raw": None,
        "client_ip": None,
        "ssid": None,
        "ap_name": None,
        "ap_name_raw": None,
        "ap_name_available": False,
        "ap_name_fallback": None,
        "ap_mac": None,
        "ap_mac_raw": None,
        "channel": None,
    }


def _empty_reported_fields() -> dict[str, Any]:
    return {
        "reported_connected_raw": None,
        "reported_connected_seconds": None,
        "reported_traffic_raw": None,
        "reported_traffic_value": None,
        "reported_traffic_unit": None,
        "reported_traffic_bytes_estimate": None,
    }


def _empty_failed_connection_fields() -> dict[str, Any]:
    return {
        "client_name": None,
        "client_name_raw": None,
        "client_name_available": False,
        "client_name_fallback": None,
        "client_mac": None,
        "client_mac_raw": None,
        "ssid": None,
        "ap_name": None,
        "ap_name_raw": None,
        "ap_name_available": False,
        "ap_name_fallback": None,
        "ap_mac": None,
        "ap_mac_raw": None,
        "channel": None,
        "failure_reason": None,
        "failure_source": None,
        "controller_reason_raw": None,
        "occurrence_count": None,
        "occurrence_window_seconds": None,
    }


def _empty_unclassified_fields() -> dict[str, Any]:
    return {
        "source_line_number": None,
        "source_line_sha256": None,
        "exception_type": None,
    }


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
