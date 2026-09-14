"""Strict normalized network-evidence payload schemas for Task-02."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .models import DeviceFingerprintValidationError

_JA4_A = re.compile(r"[tq](?:13|12|11|10|s3|s2|00)[di][0-9]{4}[0-9A-Za-z]{2}")
_JA4_HASH = re.compile(r"[0-9a-f]{12}")
_PRINTABLE_ASCII = re.compile(r"[\x21-\x7e]{1,255}")

_DHCP_KEYS = frozenset({
    "message_type", "parameter_request_list", "option_order", "vendor_class",
    "client_identifier_kind", "maximum_message_size", "rapid_commit_requested",
    "capport_requested", "ipv6_only_preferred_requested", "hostname_present",
})
_TCP_KEYS = frozenset({
    "ip_version", "observed_ttl", "tcp_window", "mss", "window_scale",
    "sack_permitted", "timestamps_present", "tcp_option_order",
})
_TLS_KEYS = frozenset({
    "ja4", "ja4_a", "ja4_b", "ja4_c", "tls_version_family",
    "client_alpns", "ech_extension_present", "grease_extension_present",
})
_QUIC_KEYS = frozenset({
    "ja4", "ja4_a", "ja4_b", "ja4_c", "quic_version",
    "ech_extension_present", "grease_extension_present",
})


def validate_dhcp_v1(value: Mapping[str, Any]) -> Mapping[str, Any]:
    _keys(value, _DHCP_KEYS)
    if value["message_type"] not in {"discover", "request", "inform", "decline", "release"}:
        _fail()
    prl = _integer_list(value["parameter_request_list"], 64)
    order = _integer_list(value["option_order"], 64)
    vendor = value["vendor_class"]
    if vendor is not None and (
        not isinstance(vendor, str)
        or not 1 <= len(vendor) <= 128
        or any(ord(character) < 0x20 or ord(character) > 0x7E for character in vendor)
    ):
        _fail()
    if value["client_identifier_kind"] not in {"absent", "mac", "opaque"}:
        _fail()
    maximum = value["maximum_message_size"]
    if maximum is not None and not _integer(maximum, 576, 65535):
        _fail()
    for key in (
        "rapid_commit_requested", "capport_requested",
        "ipv6_only_preferred_requested", "hostname_present",
    ):
        if type(value[key]) is not bool:
            _fail()
    return {
        **value,
        "parameter_request_list": prl,
        "option_order": order,
    }


def validate_tcp_syn_v1(value: Mapping[str, Any]) -> Mapping[str, Any]:
    _keys(value, _TCP_KEYS)
    if value["ip_version"] != 4 or type(value["ip_version"]) is not int:
        _fail()
    if not _integer(value["observed_ttl"], 0, 255):
        _fail()
    if not _integer(value["tcp_window"], 0, 65535):
        _fail()
    if value["mss"] is not None and not _integer(value["mss"], 0, 65535):
        _fail()
    if value["window_scale"] is not None and not _integer(value["window_scale"], 0, 14):
        _fail()
    if type(value["sack_permitted"]) is not bool or type(value["timestamps_present"]) is not bool:
        _fail()
    return {**value, "tcp_option_order": _integer_list(value["tcp_option_order"], 32)}


def validate_tls_v1(value: Mapping[str, Any]) -> Mapping[str, Any]:
    _keys(value, _TLS_KEYS)
    _ja4(value, "t")
    if value["tls_version_family"] not in {"tls1_3", "tls1_2", "other"}:
        _fail()
    expected = {"13": "tls1_3", "12": "tls1_2"}.get(value["ja4_a"][1:3], "other")
    if value["tls_version_family"] != expected:
        _fail()
    alpns = value["client_alpns"]
    if alpns is not None:
        if not isinstance(alpns, list) or not 1 <= len(alpns) <= 16:
            _fail()
        if any(not isinstance(item, str) or _PRINTABLE_ASCII.fullmatch(item) is None for item in alpns):
            _fail()
        alpns = list(alpns)
    _nullable_bools(value)
    return {**value, "client_alpns": alpns}


def validate_quic_v1(value: Mapping[str, Any]) -> Mapping[str, Any]:
    _keys(value, _QUIC_KEYS)
    _ja4(value, "q")
    version = value["quic_version"]
    if not isinstance(version, str) or re.fullmatch(r"0x[0-9a-f]{8}", version) is None:
        _fail()
    _nullable_bools(value)
    return dict(value)


def _keys(value: Mapping[str, Any], expected: frozenset[str]) -> None:
    if not isinstance(value, Mapping) or set(value) != expected:
        _fail()


def _ja4(value: Mapping[str, Any], family: str) -> None:
    a, b, c, full = value["ja4_a"], value["ja4_b"], value["ja4_c"], value["ja4"]
    if (
        not isinstance(a, str) or _JA4_A.fullmatch(a) is None or not a.startswith(family)
        or not isinstance(b, str) or _JA4_HASH.fullmatch(b) is None
        or not isinstance(c, str) or _JA4_HASH.fullmatch(c) is None
        or not isinstance(full, str) or full != f"{a}_{b}_{c}"
    ):
        _fail()


def _nullable_bools(value: Mapping[str, Any]) -> None:
    for key in ("ech_extension_present", "grease_extension_present"):
        if value[key] is not None and type(value[key]) is not bool:
            _fail()


def _integer(value: Any, minimum: int, maximum: int) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _integer_list(value: Any, maximum_length: int) -> list[int]:
    if not isinstance(value, list) or len(value) > maximum_length:
        _fail()
    if any(not _integer(item, 0, 255) for item in value):
        _fail()
    return list(value)


def _fail() -> None:
    raise DeviceFingerprintValidationError("Invalid network evidence payload")
