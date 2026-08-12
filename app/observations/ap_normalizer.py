"""Strict allowlist-only AP observation and configuration normalization."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Mapping

from app.common.mac import format_mac_colon


MAX_CONFIG_DEPTH = 8
MAX_CONFIG_LIST_ITEMS = 1000
MAX_CONFIG_STRING_BYTES = 4096
MAX_CONFIG_SNAPSHOT_BYTES = 1024 * 1024
MAX_SQLITE_INTEGER = 9_223_372_036_854_775_807

_CHANNEL = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*MHz\s*$", re.I)


@dataclass(frozen=True, slots=True)
class CanonicalConfig:
    config_json: str
    sha256: str


def canonical_ap_mac(raw: Any) -> str | None:
    if not isinstance(raw, Mapping) or raw.get("type") != "ap":
        return None
    try:
        return format_mac_colon(raw.get("mac"))
    except (TypeError, ValueError):
        return None


def normalize_ap_overview(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, Mapping):
        return None
    result: dict[str, Any] = {}
    _put_text(result, "name", raw.get("name"))
    _put_text(result, "ip", raw.get("ip"))
    _put_text(result, "model", raw.get("showModel", raw.get("model")))
    _put_text(result, "firmware_version", raw.get("firmwareVersion"))
    wlan_id = _integer_or_numeric_string(raw.get("wlanId"), nonnegative=True)
    if wlan_id is not None:
        result["wlan_id"] = wlan_id
    _put_number(result, "cpu_util", raw.get("cpuUtil"))
    _put_number(result, "mem_util", raw.get("memUtil"))
    _put_int(result, "uptime_seconds", raw.get("uptimeLong"))
    return result


def normalize_ap_wired(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, Mapping) or not isinstance(raw.get("wiredUplink"), Mapping):
        return None
    source = raw["wiredUplink"]
    result: dict[str, Any] = {}
    rate = _number_or_numeric_string(source.get("rate"), nonnegative=True)
    if rate is not None:
        result["wired_rate_raw"] = rate
    duplex = _strict_int(source.get("duplex"), nonnegative=False)
    if duplex is not None:
        result["wired_duplex_code"] = duplex
    for target, key in (
        ("wired_up_bytes", "upBytes"),
        ("wired_down_bytes", "downBytes"),
        ("wired_up_packets", "upPackets"),
        ("wired_down_packets", "downPackets"),
    ):
        _put_int(result, target, source.get(key))
    _put_number(result, "wired_activity_raw", source.get("activity"))
    return result


def normalize_ap_lan(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, Mapping) or not isinstance(raw.get("lanTraffic"), Mapping):
        return None
    source = raw["lanTraffic"]
    result: dict[str, Any] = {}
    for target, key in (
        ("lan_rx_bytes", "rx"), ("lan_tx_bytes", "tx"),
        ("lan_rx_packets", "rxPkts"), ("lan_tx_packets", "txPkts"),
        ("lan_rx_drop_packets", "rxDropPkts"),
        ("lan_tx_drop_packets", "txDropPkts"),
        ("lan_rx_error_packets", "rxErrPkts"),
        ("lan_tx_error_packets", "txErrPkts"),
    ):
        _put_int(result, target, source.get(key))
    return result


def normalize_ap_radios(raw: Any) -> tuple[dict[str, Any], ...] | None:
    if not isinstance(raw, Mapping):
        return None
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for suffix, band in (("2g", "2g"), ("5g", "5g")):
        traffic = raw.get(f"radioTraffic{suffix}")
        properties = raw.get(f"wp{suffix}")
        if traffic is None and properties is None:
            continue
        if not isinstance(traffic, Mapping) or not isinstance(properties, Mapping):
            return None
        if band in seen:
            return None
        seen.add(band)
        row: dict[str, Any] = {"band": band, "radio_id": None}
        actual_raw = _text(properties.get("actualChannel"))
        if actual_raw is not None:
            row["actual_channel_raw"] = actual_raw
            matched = _CHANNEL.fullmatch(actual_raw)
            if matched is not None:
                row["actual_channel"] = int(matched.group(1))
                row["frequency_mhz"] = int(matched.group(2))
        _put_text(row, "channel_width", properties.get("bandWidth"))
        _put_number(row, "max_tx_rate", properties.get("maxTxRate"))
        _put_number(row, "tx_power", properties.get("txPower"))
        _put_text(row, "wireless_mode", properties.get("rdMode"))
        for target, key in (
            ("tx_util", "txUtil"), ("rx_util", "rxUtil"),
            ("interference_util", "interUtil"), ("busy_util", "busyUtil"),
        ):
            _put_number(row, target, properties.get(key))
        for target, key in (
            ("rx_bytes", "rx"), ("tx_bytes", "tx"),
            ("rx_packets", "rxPkts"), ("tx_packets", "txPkts"),
            ("rx_drop_packets", "rxDropPkts"),
            ("tx_drop_packets", "txDropPkts"),
            ("rx_error_packets", "rxErrPkts"),
            ("tx_error_packets", "txErrPkts"),
            ("rx_retry_packets", "rxRetryPkts"),
            ("tx_retry_packets", "txRetryPkts"),
        ):
            _put_int(row, target, traffic.get(key))
        rows.append(row)
    return tuple(rows)


def build_ap_config(sections: Mapping[str, Any]) -> CanonicalConfig | None:
    if not isinstance(sections, Mapping):
        return None
    normalizers = (
        ("general", "general_config", _normalize_general),
        ("ip", "ip_setting", _normalize_ip),
        ("radio", "radio_config", _normalize_radio_config),
        ("ofdma", "ofdma", _normalize_ofdma),
        ("available_channels", "available_channels", _normalize_channels),
        ("overrides", "safe_overrides", _normalize_overrides),
        ("rf_scan", "rf_scan_state", _normalize_rf_scan),
    )
    normalized: dict[str, Any] = {"schema_version": 1}
    for output_name, input_name, normalizer in normalizers:
        if input_name not in sections or not _within_limits(sections[input_name]):
            return None
        value = normalizer(sections[input_name])
        if value is _INVALID:
            return None
        normalized[output_name] = value
    try:
        encoded = json.dumps(
            normalized,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        payload = encoded.encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError):
        return None
    if len(payload) > MAX_CONFIG_SNAPSHOT_BYTES:
        return None
    return CanonicalConfig(
        config_json=encoded,
        sha256=hashlib.sha256(payload).hexdigest(),
    )


_INVALID = object()


def _normalize_general(raw: Any) -> Any:
    if not isinstance(raw, Mapping):
        return _INVALID
    result: dict[str, Any] = {}
    name = _text(raw.get("name"))
    led = _strict_int(raw.get("ledSetting"), nonnegative=False)
    if "name" in raw and name is None:
        return _INVALID
    if "ledSetting" in raw and led is None:
        return _INVALID
    tags = raw.get("tagIds")
    location = raw.get("location")
    if name is not None:
        result["name"] = name
    if led is not None:
        result["led_setting_code"] = led
    if not isinstance(tags, list) or not all(type(x) in {str, int} for x in tags):
        return _INVALID
    result["tag_ids"] = list(tags)
    if not isinstance(location, Mapping):
        return _INVALID
    result["location"] = {}
    return result


def _normalize_ip(raw: Any) -> Any:
    if not isinstance(raw, Mapping):
        return _INVALID
    dhcp = raw.get("dhcpIpSetting")
    static = raw.get("staticIpSetting")
    if not isinstance(dhcp, Mapping) or not isinstance(static, Mapping):
        return _INVALID
    mode = _text(raw.get("mode"))
    if mode is None:
        return _INVALID
    normalized_dhcp = _allow_typed_scalars(dhcp, {
        "fallback": ("fallback", bool),
        "fallbackIp": ("fallback_ip", str),
        "fallbackMask": ("fallback_mask", str),
        "fallbackGate": ("fallback_gateway", str),
        "useFixedAddr": ("use_fixed_address", bool),
    })
    normalized_static = _allow_typed_scalars(static, {
        "configIp": ("ip", str),
        "configMask": ("mask", str),
        "configGate": ("gateway", str),
        "preferredDNS": ("preferred_dns", str),
        "alternateDNS": ("alternate_dns", str),
    })
    if normalized_dhcp is _INVALID or normalized_static is _INVALID:
        return _INVALID
    return {"mode": mode, "dhcp": normalized_dhcp, "static": normalized_static}


def _normalize_radio_config(raw: Any) -> Any:
    if not isinstance(raw, Mapping):
        return _INVALID
    result: dict[str, Any] = {}
    for source_name, band in (("radioSetting2g", "2g"), ("radioSetting5g", "5g")):
        source = raw.get(source_name)
        if not isinstance(source, Mapping):
            return _INVALID
        item = _allow_typed_scalars(source, {
            "radioEnable": ("enabled", bool),
            "channelWidth": ("channel_width", str),
            "channel": ("channel", str),
            "txPower": ("tx_power", int),
            "txPowerLevel": ("tx_power_level", int),
            "wirelessMode": ("wireless_mode", int),
            "channelLimitEnable": ("channel_limit_enabled", bool),
        })
        if item is _INVALID:
            return _INVALID
        if "channelRange" in source:
            values = source["channelRange"]
            if not isinstance(values, list) or not all(_strict_int(v) is not None for v in values):
                return _INVALID
            item["channel_range"] = list(values)
        result[band] = item
    return result


def _normalize_ofdma(raw: Any) -> Any:
    if not isinstance(raw, Mapping):
        return _INVALID
    allowed = {
        "ofdmaEnable2g": "enabled_2g", "ofdmaEnable5g": "enabled_5g",
        "supportOfdma2g": "supported_2g", "supportOfdma5g": "supported_5g",
        "supportOfdma5g2": "supported_5g2", "supportOfdma6g": "supported_6g",
    }
    result = _allow_typed_scalars(
        raw,
        {key: (target, bool) for key, target in allowed.items()},
    )
    if result is _INVALID:
        return _INVALID
    if any(not isinstance(value, bool) for value in result.values()):
        return _INVALID
    return result


def _normalize_channels(raw: Any) -> Any:
    if not isinstance(raw, list):
        return _INVALID
    result = []
    for band in raw:
        if not isinstance(band, Mapping) or _strict_int(band.get("radioId")) is None:
            return _INVALID
        details = band.get("apChannelDetailList")
        if not isinstance(details, list):
            return _INVALID
        normalized_details = []
        for detail in details:
            if not isinstance(detail, Mapping):
                return _INVALID
            channel = _strict_int(detail.get("channel"))
            frequency = _strict_int(detail.get("freq"))
            widths = detail.get("availableChannelWidthList")
            if channel is None or frequency is None or not isinstance(widths, list) or not all(_strict_int(x) is not None for x in widths):
                return _INVALID
            normalized_details.append({
                "channel": channel,
                "frequency_mhz": frequency,
                "available_channel_widths": list(widths),
            })
        result.append({"radio_id": band["radioId"], "channels": normalized_details})
    return result


def _normalize_overrides(raw: Any) -> Any:
    if not isinstance(raw, Mapping) or not isinstance(raw.get("ssidOverrides"), list):
        return _INVALID
    result = []
    for item in raw["ssidOverrides"]:
        if not isinstance(item, Mapping) or "ssidPassword" in item:
            return _INVALID
        normalized = _allow_typed_scalars(item, {
            "ssidId": ("ssid_id", str),
            "ssidEntryId": ("ssid_entry_id", int),
            "ssidName": ("ssid_name", str),
            "security": ("security_code", int),
            "vlanEnable": ("vlan_enabled", bool),
            "vlanId": ("vlan_id", int),
            "ssidEnable": ("ssid_enabled", bool),
        })
        if normalized is _INVALID:
            return _INVALID
        band = item.get("band")
        if not isinstance(band, list) or not all(_strict_int(x) is not None for x in band):
            return _INVALID
        normalized["band"] = list(band)
        result.append(normalized)
    return result


def _normalize_rf_scan(raw: Any) -> Any:
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        return _INVALID
    result: dict[str, Any] = {}
    for key in ("time", "status", "status2g", "status5g", "status5g2", "status6g"):
        if key in raw:
            value = _strict_int(raw[key], nonnegative=False)
            if value is None:
                return _INVALID
            result[key] = value
    return result


def _allow_typed_scalars(
    raw: Mapping[str, Any],
    allowed: Mapping[str, tuple[str, type]],
) -> dict[str, Any] | object:
    result: dict[str, Any] = {}
    for source, (target, expected_type) in allowed.items():
        if source not in raw:
            continue
        value = raw[source]
        if type(value) is not expected_type:
            return _INVALID
        result[target] = value
    return result


def _within_limits(value: Any) -> bool:
    stack = [(value, 0)]
    seen: set[int] = set()
    while stack:
        current, depth = stack.pop()
        if depth > MAX_CONFIG_DEPTH:
            return False
        if isinstance(current, (dict, list)):
            identity = id(current)
            if identity in seen:
                return False
            seen.add(identity)
        if isinstance(current, Mapping):
            if len(current) > MAX_CONFIG_LIST_ITEMS:
                return False
            for key, child in current.items():
                if not isinstance(key, str) or len(key.encode("utf-8")) > MAX_CONFIG_STRING_BYTES:
                    return False
                stack.append((child, depth + 1))
        elif isinstance(current, list):
            if len(current) > MAX_CONFIG_LIST_ITEMS:
                return False
            stack.extend((child, depth + 1) for child in current)
        elif isinstance(current, str):
            if len(current.encode("utf-8")) > MAX_CONFIG_STRING_BYTES:
                return False
        elif current is not None and type(current) not in {bool, int, float}:
            return False
        elif type(current) is float and not math.isfinite(current):
            return False
    return True


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _strict_int(value: Any, *, nonnegative: bool = True) -> int | None:
    if type(value) is not int or (nonnegative and value < 0):
        return None
    return value


def _integer_or_numeric_string(value: Any, *, nonnegative: bool) -> int | None:
    if type(value) is int:
        parsed = value
    elif isinstance(value, str) and value.strip():
        text = value.strip()
        if not text.isascii() or not text.isdecimal():
            return None
        significant = text.lstrip("0") or "0"
        if len(significant) > 19:
            return None
        try:
            parsed = int(significant)
        except (ValueError, OverflowError):
            return None
    else:
        return None
    if parsed > MAX_SQLITE_INTEGER:
        return None
    if nonnegative and parsed < 0:
        return None
    return parsed


def _number_or_numeric_string(value: Any, *, nonnegative: bool) -> int | float | None:
    if type(value) in {int, float}:
        parsed = float(value)
    elif isinstance(value, str) and value.strip():
        try:
            parsed = float(value.strip())
        except (ValueError, OverflowError):
            return None
    else:
        return None
    if not math.isfinite(parsed) or (nonnegative and parsed < 0):
        return None
    return int(parsed) if parsed.is_integer() else parsed


def _put_text(target: dict[str, Any], name: str, value: Any) -> None:
    parsed = _text(value)
    if parsed is not None:
        target[name] = parsed


def _put_int(target: dict[str, Any], name: str, value: Any) -> None:
    parsed = _strict_int(value)
    if parsed is not None:
        target[name] = parsed


def _put_number(target: dict[str, Any], name: str, value: Any) -> None:
    if type(value) in {int, float} and math.isfinite(float(value)):
        target[name] = float(value)
