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
    parsed = _options(options)
    if parsed is None:
        return None
    order, mss, scale, sack, timestamps = parsed
    return source_mac, str(source), {
        "ip_version": 4,
        "observed_ttl": frame[offset + 8],
        "tcp_window": struct.unpack_from("!H", frame, tcp + 14)[0],
        "mss": mss,
        "window_scale": scale,
        "sack_permitted": sack,
        "timestamps_present": timestamps,
        "tcp_option_order": order,
    }


def _options(raw: bytes) -> tuple[list[int], int | None, int | None, bool, bool] | None:
    order: list[int] = []
    mss = scale = None
    sack = timestamps = False
    offset = 0
    while offset < len(raw):
        kind = raw[offset]
        offset += 1
        order.append(kind)
        if len(order) > 32:
            return None
        if kind == 0:
            if any(byte != 0 for byte in raw[offset:]):
                return None
            break
        if kind == 1:
            continue
        if offset >= len(raw):
            return None
        length = raw[offset]
        offset += 1
        if length < 2 or offset + length - 2 > len(raw):
            return None
        value = raw[offset:offset + length - 2]
        offset += length - 2
        if kind == 2:
            if length != 4:
                return None
            mss = int.from_bytes(value, "big")
        elif kind == 3:
            if length != 3 or value[0] > 14:
                return None
            scale = value[0]
        elif kind == 4:
            if length != 2:
                return None
            sack = True
        elif kind == 8:
            if length != 10:
                return None
            timestamps = True
    return order, mss, scale, sack, timestamps
