"""Strict normalization and defensive raw-result redaction."""

from __future__ import annotations

import copy
import ipaddress
import math
from typing import Any

from app.common.mac import format_mac_colon

from .snapshot_models import NormalizedClientSnapshot


_REDACTED = "[REDACTED]"
_SENSITIVE_KEYS = frozenset({
    "accesstoken",
    "access_token",
    "token",
    "authorization",
    "clientsecret",
    "client_secret",
    "cookie",
    "set-cookie",
    "password",
})

_STRING_FIELDS = {
    "id": "controller_client_id",
    "name": "name",
    "hostName": "hostname",
    "systemName": "system_name",
    "deviceType": "device_type",
    "connectDevType": "connect_device_type",
    "ssid": "ssid",
    "apName": "ap_name",
    "dot1xIdentity": "dot1x_identity",
}
_INTEGER_FIELDS = {
    "connectType": "connect_type",
    "signalLevel": "signal_level",
    "signalRank": "signal_rank",
    "wifiMode": "wifi_mode",
    "radioId": "radio_id",
    "channel": "channel",
    "rxRate": "rx_rate",
    "txRate": "tx_rate",
    "rssi": "rssi",
    "snr": "snr",
    "vid": "vid",
    "trafficDown": "traffic_down",
    "trafficUp": "traffic_up",
    "uptime": "uptime",
    "lastSeen": "last_seen",
    "authStatus": "auth_status",
    "downPacket": "down_packet",
    "upPacket": "up_packet",
}
_NUMBER_FIELDS = {
    "activity": "activity",
}
_BOOLEAN_FIELDS = {
    "connectedToWirelessRouter": "connected_to_wireless_router",
    "wireless": "wireless",
    "powerSave": "power_save",
    "blocked": "blocked",
    "guest": "guest",
    "active": "active",
    "manager": "manager",
}
_OBJECT_FIELDS = {
    "ipSetting": "ip_setting",
    "rateLimit": "rate_limit",
    "clientLockToApSetting": "client_lock_to_ap_setting",
}
_ARRAY_FIELDS = {
    "multiLink": "multi_link",
}


class SnapshotNormalizationError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        path: str | None = None,
        raw_serializable: bool = True,
    ):
        super().__init__(message)
        self.path = path
        self.raw_serializable = raw_serializable


def normalize_client_snapshot(
    raw_result: dict[str, Any],
) -> NormalizedClientSnapshot:
    if not isinstance(raw_result, dict):
        raise SnapshotNormalizationError(
            "Controller result must be an object",
            raw_serializable=False,
        )

    try:
        raw_copy = copy.deepcopy(raw_result)
    except Exception as exc:
        raise SnapshotNormalizationError(
            "Controller result could not be copied safely",
            raw_serializable=False,
        ) from exc
    strict_json_path = _strict_json_problem(raw_copy)
    if strict_json_path is not None:
        raise SnapshotNormalizationError(
            "Controller result is not strict JSON-compatible",
            path=strict_json_path,
            raw_serializable=False,
        )

    sanitized_raw, redacted_count = _sanitize_raw(raw_copy)

    try:
        client_mac = format_mac_colon(raw_result.get("mac"))
    except ValueError as exc:
        raise SnapshotNormalizationError(
            "Controller result has no valid client MAC",
            path="mac",
        ) from exc

    client: dict[str, Any] = {"mac": client_mac}
    for source, target in _STRING_FIELDS.items():
        client[target] = _strict_string(
            sanitized_raw.get(source)
        )
    for source, target in _INTEGER_FIELDS.items():
        client[target] = _strict_integer(
            sanitized_raw.get(source)
        )
    for source, target in _NUMBER_FIELDS.items():
        client[target] = _strict_number(
            sanitized_raw.get(source)
        )
    for source, target in _BOOLEAN_FIELDS.items():
        client[target] = _strict_boolean(
            sanitized_raw.get(source)
        )
    for source, target in _OBJECT_FIELDS.items():
        client[target] = _strict_object(
            sanitized_raw.get(source)
        )
    for source, target in _ARRAY_FIELDS.items():
        client[target] = _strict_array(
            sanitized_raw.get(source)
        )

    client["ip"] = _canonical_ip(sanitized_raw.get("ip"))
    client["ipv6_list"] = _ipv6_list(
        sanitized_raw.get("ipv6List")
    )
    try:
        client["ap_mac"] = (
            format_mac_colon(sanitized_raw["apMac"])
            if sanitized_raw.get("apMac") is not None
            else None
        )
    except ValueError:
        client["ap_mac"] = None

    return NormalizedClientSnapshot(
        client=client,
        raw_controller_snapshot=sanitized_raw,
        redacted_field_count=redacted_count,
    )


def safe_raw_snapshot(
    raw_result: Any,
) -> tuple[dict[str, Any], int]:
    """Return a strict, sanitized raw snapshot or raise."""
    if not isinstance(raw_result, dict):
        raise SnapshotNormalizationError(
            "Controller result must be an object",
            raw_serializable=False,
        )
    try:
        raw_copy = copy.deepcopy(raw_result)
    except Exception as exc:
        raise SnapshotNormalizationError(
            "Controller result could not be copied safely",
            raw_serializable=False,
        ) from exc
    problem_path = _strict_json_problem(raw_copy)
    if problem_path is not None:
        raise SnapshotNormalizationError(
            "Controller result is not strict JSON-compatible",
            path=problem_path,
            raw_serializable=False,
        )
    return _sanitize_raw(raw_copy)


def _strict_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _strict_integer(value: Any) -> int | None:
    return value if type(value) is int else None


def _strict_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _strict_boolean(value: Any) -> bool | None:
    return value if type(value) is bool else None


def _strict_object(value: Any) -> dict[str, Any] | None:
    return copy.deepcopy(value) if isinstance(value, dict) else None


def _strict_array(value: Any) -> list[Any] | None:
    return copy.deepcopy(value) if isinstance(value, list) else None


def _canonical_ip(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def _ipv6_list(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        try:
            address = ipaddress.ip_address(item.strip())
        except ValueError:
            continue
        if address.version == 6:
            result.append(str(address))
    return result


def _sanitize_raw(
    value: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    redacted = 0

    def visit(item: Any) -> Any:
        nonlocal redacted
        if isinstance(item, dict):
            result: dict[str, Any] = {}
            for key, child in item.items():
                if key.casefold() in _SENSITIVE_KEYS:
                    result[key] = _REDACTED
                    redacted += 1
                else:
                    result[key] = visit(child)
            return result
        if isinstance(item, list):
            return [visit(child) for child in item]
        return item

    return visit(value), redacted


def _strict_json_problem(
    value: Any,
    path: str = "$",
) -> str | None:
    if value is None or type(value) in {bool, int}:
        return None
    if isinstance(value, float):
        return None if math.isfinite(value) else path
    if isinstance(value, str):
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeEncodeError:
            return path
        return None
    if isinstance(value, list):
        for index, item in enumerate(value):
            problem = _strict_json_problem(
                item,
                f"{path}[{index}]",
            )
            if problem is not None:
                return problem
        return None
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                return f"{path}.<non-string-key>"
            try:
                key.encode("utf-8", errors="strict")
            except UnicodeEncodeError:
                return f"{path}.<invalid-key>"
            child_path = f"{path}.{key}" if path != "$" else key
            problem = _strict_json_problem(item, child_path)
            if problem is not None:
                return problem
        return None
    return path
