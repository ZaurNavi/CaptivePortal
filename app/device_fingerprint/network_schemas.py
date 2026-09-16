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
_TCP_V2_KEYS = frozenset({
    "ip_version", "observed_ttl", "ip_option_length_bytes", "ip_id_zero",
    "ip_df", "ip_reserved_flag", "ip_ecn_bits", "tcp_header_length_bytes",
    "tcp_window", "tcp_sequence_zero", "tcp_ack_number_nonzero",
    "tcp_urg_pointer_nonzero", "tcp_fin", "tcp_rst", "tcp_push", "tcp_urg",
    "tcp_ece", "tcp_cwr", "tcp_payload_present", "tcp_option_records",
})
_TCP_V2_BOOLEAN_KEYS = frozenset({
    "ip_id_zero", "ip_df", "ip_reserved_flag", "tcp_sequence_zero",
    "tcp_ack_number_nonzero", "tcp_urg_pointer_nonzero", "tcp_fin",
    "tcp_rst", "tcp_push", "tcp_urg", "tcp_ece", "tcp_cwr",
    "tcp_payload_present",
})
_TCP_V2_OPTION_COMMON = frozenset({
    "record_type", "kind", "declared_length", "available_value_length",
    "structure_state",
})
_TCP_V2_OPTION_FIELDS = {
    "eol": frozenset({
        "eol_padding_length", "eol_padding_nonzero",
        "eol_padding_nonzero_before_final_byte",
    }),
    "nop": frozenset(),
    "mss": frozenset({"mss"}),
    "window_scale": frozenset({"window_scale_raw"}),
    "sack_permitted": frozenset(),
    "timestamp": frozenset({"timestamp_value_zero", "timestamp_echo_nonzero"}),
    "unknown": frozenset(),
}
_TCP_V2_OPTION_TYPES = {
    0: "eol", 1: "nop", 2: "mss", 3: "window_scale",
    4: "sack_permitted", 8: "timestamp",
}
_TCP_V2_KNOWN_LENGTHS = {2: 4, 3: 3, 4: 2, 8: 10}
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


def validate_tcp_syn_v2(value: Mapping[str, Any]) -> Mapping[str, Any]:
    _keys(value, _TCP_V2_KEYS)
    if type(value["ip_version"]) is not int or value["ip_version"] != 4:
        _fail()
    for name, maximum in (
        ("observed_ttl", 255), ("ip_option_length_bytes", 40),
        ("ip_ecn_bits", 3), ("tcp_window", 65535),
    ):
        if not _integer(value[name], 0, maximum):
            _fail()
    if value["ip_option_length_bytes"] % 4:
        _fail()
    header_length = value["tcp_header_length_bytes"]
    if not _integer(header_length, 20, 60) or header_length % 4:
        _fail()
    if any(type(value[name]) is not bool for name in _TCP_V2_BOOLEAN_KEYS):
        _fail()
    records = value["tcp_option_records"]
    if not isinstance(records, list) or len(records) > 40:
        _fail()
    option_length = header_length - 20
    offset = 0
    stopped = False
    normalized = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            _fail()
        kind = record.get("kind")
        if not _integer(kind, 0, 255):
            _fail()
        record_type = _TCP_V2_OPTION_TYPES.get(kind, "unknown")
        if record.get("record_type") != record_type:
            _fail()
        _keys(record, _TCP_V2_OPTION_COMMON | _TCP_V2_OPTION_FIELDS[record_type])
        if offset >= option_length:
            _fail()
        offset += 1  # physically observed option kind
        declared = record["declared_length"]
        available = record["available_value_length"]
        if not _integer(available, 0, 40):
            _fail()
        last = index == len(records) - 1
        if kind == 0:
            if (declared is not None or available != 0
                    or record["structure_state"] != "well_formed"
                    or not last
                    or type(record["eol_padding_nonzero"]) is not bool
                    or type(record["eol_padding_nonzero_before_final_byte"]) is not bool
                    or not _integer(record["eol_padding_length"], 0, 40)
                    or record["eol_padding_length"] != option_length - offset
                    or (record["eol_padding_length"] == 0 and record["eol_padding_nonzero"])
                    or (record["eol_padding_length"] <= 1
                        and record["eol_padding_nonzero_before_final_byte"])
                    or (record["eol_padding_nonzero_before_final_byte"]
                        and not record["eol_padding_nonzero"])):
                _fail()
            offset = option_length
            stopped = True
        elif kind == 1:
            if declared is not None or available != 0 or record["structure_state"] != "well_formed":
                _fail()
        else:
            if declared is None:
                if offset != option_length or available != 0 or not last:
                    _fail()
                expected_state = "malformed_but_observable"
                stopped = True
            else:
                if not _integer(declared, 0, 255) or offset >= option_length:
                    _fail()
                offset += 1  # physically observed length byte
                if declared < 2:
                    if available != 0 or not last:
                        _fail()
                    expected_state = "malformed_but_observable"
                    stopped = True
                else:
                    physically_available = min(declared - 2, option_length - offset)
                    if available != physically_available:
                        _fail()
                    offset += available
                    complete = available == declared - 2
                    expected_state = (
                        "well_formed" if complete and (
                            kind not in _TCP_V2_KNOWN_LENGTHS
                            or declared == _TCP_V2_KNOWN_LENGTHS[kind]
                        ) else "malformed_but_observable"
                    )
                    if not complete:
                        if not last:
                            _fail()
                        stopped = True
            if record["structure_state"] != expected_state:
                _fail()
            if kind == 2:
                if available >= 2:
                    if not _integer(record["mss"], 0, 65535):
                        _fail()
                elif record["mss"] is not None:
                    _fail()
            elif kind == 3:
                if available >= 1:
                    if not _integer(record["window_scale_raw"], 0, 255):
                        _fail()
                elif record["window_scale_raw"] is not None:
                    _fail()
            elif kind == 8:
                for name, present in (
                    ("timestamp_value_zero", available >= 4),
                    ("timestamp_echo_nonzero", available >= 8),
                ):
                    if (present and type(record[name]) is not bool) or (not present and record[name] is not None):
                        _fail()
        normalized.append(dict(record))
    if not stopped and offset != option_length:
        _fail()
    return {**value, "tcp_option_records": normalized}


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
