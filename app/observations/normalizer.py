"""Strict, allowlist-only client observation normalization."""

from __future__ import annotations

import ipaddress
import json
from dataclasses import dataclass
from typing import Any, Mapping

from app.common.mac import format_mac_colon


@dataclass(frozen=True, slots=True)
class ClientEligibility:
    client_mac: str | None
    eligible: bool
    reason: str
    unknown_auth_status: bool = False


_TEXT_FIELDS: dict[str, tuple[str, ...]] = {
    "controller_client_id": ("id", "clientId", "controller_client_id"),
    "name": ("name",),
    "hostname": ("hostName", "hostname"),
    "system_name": ("systemName", "system_name"),
    "device_type": ("deviceType", "device_type"),
    "connect_device_type": (
        "connectDevType", "connectDeviceType", "connect_device_type",
    ),
    "ssid": ("ssid",),
    "ap_name": ("apName", "ap_name"),
}

_ENUM_FIELDS: dict[str, tuple[str, ...]] = {
    "connect_type": ("connectType", "connect_type"),
    "wifi_mode": ("wifiMode", "wifi_mode"),
}

_INTEGER_FIELDS: dict[str, tuple[str, ...]] = {
    "signal_level": ("signalLevel", "signal_level"),
    "signal_rank": ("signalRank", "signal_rank"),
    "radio_id": ("radioId", "radio_id"),
    "channel": ("channel",),
    "rx_rate": ("rxRate", "rx_rate"),
    "tx_rate": ("txRate", "tx_rate"),
    "rssi": ("rssi",),
    "snr": ("snr",),
    "vid": ("vid",),
    "uptime": ("uptime",),
    "last_seen_ms": ("lastSeen", "lastSeenMs", "last_seen_ms"),
    "auth_status": ("authStatus", "auth_status"),
    "activity": ("activity",),
    "traffic_down": ("trafficDown", "traffic_down"),
    "traffic_up": ("trafficUp", "traffic_up"),
    "down_packet": ("downPacket", "down_packet"),
    "up_packet": ("upPacket", "up_packet"),
}

_NONNEGATIVE_FIELDS = frozenset({
    "channel", "rx_rate", "tx_rate", "vid", "uptime", "last_seen_ms",
    "activity", "traffic_down", "traffic_up", "down_packet", "up_packet",
})

_BOOLEAN_FIELDS: dict[str, tuple[str, ...]] = {
    "wireless": ("wireless",),
    "power_save": ("powerSave", "power_save"),
    "blocked": ("blocked",),
    "guest": ("guest",),
    "active": ("active",),
    "manager": ("manager",),
}


def _first(raw: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in raw:
            return raw[key]
    return None


def canonical_client_mac(raw: Any) -> str | None:
    if not isinstance(raw, Mapping):
        return None
    value = _first(raw, ("mac", "clientMac", "client_mac"))
    try:
        return format_mac_colon(value)
    except (TypeError, ValueError):
        return None


def classify_client(
    raw: Any,
    ssid_allowlist: tuple[str, ...] = (),
) -> ClientEligibility:
    if not isinstance(raw, Mapping):
        return ClientEligibility(None, False, "malformed_row")
    client_mac = canonical_client_mac(raw)
    if client_mac is None:
        return ClientEligibility(None, False, "invalid_mac")
    auth_status = _first(raw, ("authStatus", "auth_status"))
    unknown = type(auth_status) is not int or auth_status not in {1, 2}
    wireless = _first(raw, ("wireless",))
    if type(wireless) is not bool or wireless is not True:
        return ClientEligibility(
            client_mac, False, "not_wireless", unknown,
        )
    active = _first(raw, ("active",))
    if type(active) is not bool or active is not True:
        return ClientEligibility(client_mac, False, "not_active", unknown)
    if type(auth_status) is not int or auth_status != 2:
        return ClientEligibility(
            client_mac,
            False,
            "unknown_auth_status" if unknown else "not_authorized",
            unknown,
        )
    if ssid_allowlist:
        ssid = _first(raw, ("ssid",))
        if not isinstance(ssid, str) or ssid not in ssid_allowlist:
            return ClientEligibility(client_mac, False, "ssid_filtered")
    return ClientEligibility(client_mac, True, "eligible")


def normalize_client_observation(
    raw: Any,
    *,
    cycle_id: str,
    site_id: str,
    observed_at: str,
    source_inventory_complete: bool,
) -> dict[str, Any] | None:
    """Return only schema-v1 allowlisted facts; raw rows are never retained."""
    if not isinstance(raw, Mapping):
        return None
    client_mac = canonical_client_mac(raw)
    if client_mac is None:
        return None
    row: dict[str, Any] = {
        "cycle_id": cycle_id,
        "observed_at": observed_at,
        "site_id": site_id,
        "client_mac": client_mac,
        "source_inventory_complete": source_inventory_complete,
    }
    for target, keys in _TEXT_FIELDS.items():
        value = _first(raw, keys)
        if isinstance(value, str) and value.strip():
            row[target] = value.strip()
    for target, keys in _ENUM_FIELDS.items():
        value = _first(raw, keys)
        if isinstance(value, str) and value.strip():
            row[target] = value.strip()
        elif type(value) is int:
            # Unknown enum codes are kept raw, never assigned invented labels.
            row[target] = value
    for target, keys in _INTEGER_FIELDS.items():
        value = _first(raw, keys)
        if type(value) is int and (
            target not in _NONNEGATIVE_FIELDS or value >= 0
        ):
            row[target] = value
    for target, keys in _BOOLEAN_FIELDS.items():
        value = _first(raw, keys)
        if type(value) is bool:
            row[target] = value

    ip_value = _first(raw, ("ip", "clientIp", "client_ip"))
    if isinstance(ip_value, str):
        try:
            row["ip"] = str(ipaddress.ip_address(ip_value.strip()))
        except ValueError:
            pass
    ipv6_json = _normalize_ipv6_list(
        _first(raw, ("ipv6List", "ipv6_list", "ipv6_list_json"))
    )
    if ipv6_json is not None:
        row["ipv6_list_json"] = ipv6_json
    ap_mac = _first(raw, ("apMac", "ap_mac"))
    if ap_mac is not None:
        try:
            row["ap_mac"] = format_mac_colon(ap_mac)
        except (TypeError, ValueError):
            pass
    radio_id = row.get("radio_id")
    if radio_id == 0:
        row["band"] = "2.4GHz"
    elif radio_id == 1:
        row["band"] = "5GHz"
    return row


def _normalize_ipv6_list(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, list):
        return None
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            return None
        try:
            address = ipaddress.ip_address(item.strip())
        except ValueError:
            return None
        if address.version != 6:
            return None
        normalized.append(str(address))
    return json.dumps(
        normalized,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )
