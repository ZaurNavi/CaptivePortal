"""IPv4 outbound SYN fingerprint parser."""

from __future__ import annotations

import ipaddress
import struct
from typing import Any


def parse_tcp_syn_frame(frame: bytes, guest_cidrs: tuple[Any, ...]) -> tuple[str, str, dict[str, Any]] | None:
    if len(frame) < 34:
        return None
    source_mac = ":".join(f"{part:02x}" for part in frame[6:12])
    offset = 14
    ether_type = struct.unpack_from("!H", frame, 12)[0]
    while ether_type in {0x8100, 0x88A8}:
        if len(frame) < offset + 4:
            return None
        ether_type = struct.unpack_from("!H", frame, offset + 2)[0]
        offset += 4
    if ether_type != 0x0800 or len(frame) < offset + 20 or frame[offset] >> 4 != 4:
        return None
    ihl = (frame[offset] & 0x0F) * 4
    total = struct.unpack_from("!H", frame, offset + 2)[0]
    fragment = struct.unpack_from("!H", frame, offset + 6)[0]
    if ihl < 20 or total < ihl + 20 or len(frame) < offset + total or frame[offset + 9] != 6 or fragment & 0x3FFF:
        return None
    source = ipaddress.ip_address(frame[offset + 12:offset + 16])
    if not any(source in network for network in guest_cidrs):
        return None
    tcp = offset + ihl
    data_offset = (frame[tcp + 12] >> 4) * 4
    flags = frame[tcp + 13]
    if data_offset < 20 or tcp + data_offset > offset + total or flags & 0x12 != 0x02:
        return None
    options = frame[tcp + 20:tcp + data_offset]
    return source_mac, str(source), {
        "ip_version": 4,
        "observed_ttl": frame[offset + 8],
        "ip_option_length_bytes": ihl - 20,
        "ip_id_zero": struct.unpack_from("!H", frame, offset + 4)[0] == 0,
        "ip_df": bool(fragment & 0x4000),
        "ip_reserved_flag": bool(fragment & 0x8000),
        "ip_ecn_bits": frame[offset + 1] & 0x03,
        "tcp_header_length_bytes": data_offset,
        "tcp_window": struct.unpack_from("!H", frame, tcp + 14)[0],
        "tcp_sequence_zero": struct.unpack_from("!I", frame, tcp + 4)[0] == 0,
        "tcp_ack_number_nonzero": struct.unpack_from("!I", frame, tcp + 8)[0] != 0,
        "tcp_urg_pointer_nonzero": struct.unpack_from("!H", frame, tcp + 18)[0] != 0,
        "tcp_fin": bool(flags & 0x01),
        "tcp_rst": bool(flags & 0x04),
        "tcp_push": bool(flags & 0x08),
        "tcp_urg": bool(flags & 0x20),
        "tcp_ece": bool(flags & 0x40),
        "tcp_cwr": bool(flags & 0x80),
        "tcp_payload_present": total > ihl + data_offset,
        "tcp_option_records": _options(options),
    }


def _options(raw: bytes) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    offset = 0
    while offset < len(raw):
        kind = raw[offset]
        offset += 1
        if kind == 0:
            padding = raw[offset:]
            records.append({
                "record_type": "eol", "kind": 0, "declared_length": None,
                "available_value_length": 0, "structure_state": "well_formed",
                "eol_padding_length": len(padding),
                "eol_padding_nonzero": any(padding),
                "eol_padding_nonzero_before_final_byte": any(padding[:-1]),
            })
            break
        if kind == 1:
            records.append({
                "record_type": "nop", "kind": 1, "declared_length": None,
                "available_value_length": 0, "structure_state": "well_formed",
            })
            continue
        record_type = {
            2: "mss", 3: "window_scale", 4: "sack_permitted", 8: "timestamp",
        }.get(kind, "unknown")
        length = raw[offset] if offset < len(raw) else None
        if length is not None:
            offset += 1
        available = min(length - 2, len(raw) - offset) if length is not None and length >= 2 else 0
        value = raw[offset:offset + available]
        offset += available
        expected_length = {2: 4, 3: 3, 4: 2, 8: 10}.get(kind)
        complete = length is not None and length >= 2 and available == length - 2
        record: dict[str, Any] = {
            "record_type": record_type, "kind": kind,
            "declared_length": length, "available_value_length": available,
            "structure_state": (
                "well_formed" if complete and (expected_length is None or length == expected_length)
                else "malformed_but_observable"
            ),
        }
        if kind == 2:
            record["mss"] = int.from_bytes(value[:2], "big") if available >= 2 else None
        elif kind == 3:
            record["window_scale_raw"] = value[0] if available >= 1 else None
        elif kind == 8:
            record["timestamp_value_zero"] = value[:4] == b"\0" * 4 if available >= 4 else None
            record["timestamp_echo_nonzero"] = value[4:8] != b"\0" * 4 if available >= 8 else None
        records.append(record)
        if not complete:
            break
    return records
