"""Allowlist-only normalization for current client and AP inventories."""

from __future__ import annotations

import hashlib
import ipaddress
import json
from dataclasses import dataclass
from typing import Any, Mapping

from app.common.mac import format_mac_colon

from .ap_status import classify_ap_status_code
from .models import MAX_SQLITE_INTEGER


@dataclass(frozen=True, slots=True)
class NormalizedItem:
    values: dict[str, Any]
    warning_count: int
    unknown_status: bool


def canonical_scope(kind: str, site_id: str, ssids: tuple[str, ...]) -> tuple[str, str]:
    if kind == "client":
        payload = {
            "scope_type": "client_ssid_allowlist",
            "site_id": site_id,
            "ssids": sorted(set(ssids)),
        }
    elif kind == "ap":
        payload = {"scope_type": "site_ap_inventory", "site_id": site_id}
    else:
        raise ValueError("unsupported scope kind")
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
    return encoded, hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def current_client_relevant(raw: Any, ssids: tuple[str, ...]) -> bool:
    if not isinstance(raw, Mapping):
        return False
    return (
        raw.get("wireless") is True
        and raw.get("active") is True
        and isinstance(raw.get("ssid"), str)
        and raw.get("ssid") in ssids
    )


def canonical_client_mac(raw: Any) -> str | None:
    if not isinstance(raw, Mapping):
        return None
    return _mac(_first(raw, "mac", "clientMac", "client_mac"))


def normalize_current_client(raw: Any, *, cycle_id: str, site_id: str, observed_at: str, ssids: tuple[str, ...]) -> NormalizedItem | None:
    if not current_client_relevant(raw, ssids):
        return None
    mac = canonical_client_mac(raw)
    if mac is None:
        return None
    warning = 0
    values: dict[str, Any] = {
        "cycle_id": cycle_id,
        "cycle_kind": "client",
        "site_id": site_id,
        "observed_at": observed_at,
        "client_mac": mac,
        "active": True,
        "wireless": True,
        "ssid": raw["ssid"],
    }
    for target, aliases, maximum in (
        ("name", ("name",), 256),
        ("hostname", ("hostName", "hostname"), 253),
        ("device_type", ("deviceType", "device_type"), 128),
        ("ap_name", ("apName", "ap_name"), 256),
    ):
        value, warned = _bounded_text(_first(raw, *aliases), maximum)
        values[target] = value
        warning += warned
    ip_value, warned = _ip(_first(raw, "ip", "clientIp", "client_ip"))
    values["ip"] = ip_value
    warning += warned
    ap_value = _first(raw, "apMac", "ap_mac")
    values["ap_mac"] = _mac(ap_value)
    if ap_value is not None and values["ap_mac"] is None:
        warning += 1
    radio_id = _strict_int(_first(raw, "radioId", "radio_id"), nonnegative=True)
    values["radio_id"] = radio_id
    values["band"] = "2.4GHz" if radio_id == 0 else "5GHz" if radio_id == 1 else None
    for target, aliases, nonnegative in (
        ("channel", ("channel",), True),
        ("rssi", ("rssi",), False),
        ("snr", ("snr",), False),
        ("controller_uptime", ("uptime", "uptimeLong", "controller_uptime"), True),
    ):
        raw_value = _first(raw, *aliases)
        value = _strict_int(raw_value, nonnegative=nonnegative)
        values[target] = value
        if raw_value is not None and value is None:
            warning += 1
    auth_raw = _first(raw, "authStatus", "auth_status")
    auth_code = auth_raw if type(auth_raw) is int and -MAX_SQLITE_INTEGER <= auth_raw <= MAX_SQLITE_INTEGER else None
    values["auth_status_code"] = auth_code
    values["auth_classification"] = (
        "authorized" if auth_code == 2 else
        "pending" if auth_code == 1 else
        "other" if auth_code is not None else
        "unknown"
    )
    unknown = auth_code is None
    if auth_raw is not None and auth_code is None:
        warning += 1
    down_raw = _first(raw, "trafficDown", "traffic_down")
    up_raw = _first(raw, "trafficUp", "traffic_up")
    down = _strict_int(down_raw, nonnegative=True)
    up = _strict_int(up_raw, nonnegative=True)
    values["controller_traffic_down"] = down
    values["controller_traffic_up"] = up
    if down_raw is not None and down is None:
        warning += 1
    if up_raw is not None and up is None:
        warning += 1
    if down is not None and up is not None and down <= MAX_SQLITE_INTEGER - up:
        values["controller_traffic_total"] = down + up
    else:
        values["controller_traffic_total"] = None
        if down is not None and up is not None:
            warning += 1
    return NormalizedItem(values, warning, unknown)


def canonical_ap_mac(raw: Any) -> str | None:
    if not isinstance(raw, Mapping) or raw.get("type") != "ap":
        return None
    return _mac(_first(raw, "mac", "apMac", "ap_mac"))


def normalize_current_ap(raw: Any, *, cycle_id: str, site_id: str, observed_at: str) -> NormalizedItem | None:
    if not isinstance(raw, Mapping) or raw.get("type") != "ap":
        return None
    mac = canonical_ap_mac(raw)
    if mac is None:
        return None
    warning = 0
    values: dict[str, Any] = {
        "cycle_id": cycle_id,
        "cycle_kind": "ap",
        "site_id": site_id,
        "observed_at": observed_at,
        "ap_mac": mac,
    }
    for target, aliases, maximum in (
        ("name", ("name",), 256),
        ("model", ("showModel", "model"), 128),
        ("firmware_version", ("firmwareVersion", "firmware_version"), 256),
    ):
        value, warned = _bounded_text(_first(raw, *aliases), maximum)
        values[target] = value
        warning += warned
    ip_value, warned = _ip(_first(raw, "ip", "deviceIp", "ap_ip"))
    values["ip"] = ip_value
    warning += warned
    status_raw = _first(raw, "status", "statusCode", "status_code")
    status_code = _strict_int(status_raw, nonnegative=False)
    values["status_code"] = status_code
    values["status_classification"] = classify_ap_status_code(status_code)
    unknown = status_code is None
    if status_raw is not None and status_code is None:
        warning += 1
    for target, aliases in (
        ("last_seen_ms", ("lastSeen", "lastSeenMs", "last_seen_ms")),
        ("controller_uptime", ("uptimeLong", "uptime", "controller_uptime")),
    ):
        raw_value = _first(raw, *aliases)
        value = _strict_int(raw_value, nonnegative=True)
        values[target] = value
        if raw_value is not None and value is None:
            warning += 1
    uptime_value = _first(raw, "uptimeRaw", "uptime_raw")
    values["uptime_raw"], warned = _bounded_text(uptime_value, 128)
    warning += warned
    return NormalizedItem(values, warning, unknown)


def _first(raw: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in raw:
            return raw[name]
    return None


def _mac(value: Any) -> str | None:
    try:
        return format_mac_colon(value)
    except (TypeError, ValueError):
        return None


def _bounded_text(value: Any, maximum: int) -> tuple[str | None, int]:
    if value is None:
        return None, 0
    if not isinstance(value, str) or not value or "\x00" in value:
        return None, 1
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError:
        return None, 1
    return (value, 0) if size <= maximum else (None, 1)


def _ip(value: Any) -> tuple[str | None, int]:
    if value is None:
        return None, 0
    if not isinstance(value, str):
        return None, 1
    try:
        return str(ipaddress.ip_address(value.strip())), 0
    except ValueError:
        return None, 1


def _strict_int(value: Any, *, nonnegative: bool) -> int | None:
    if type(value) is not int or not -MAX_SQLITE_INTEGER <= value <= MAX_SQLITE_INTEGER:
        return None
    if nonnegative and value < 0:
        return None
    return value
