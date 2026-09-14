"""Exact bounded DHCPv4 parser for BPF-admitted Ethernet frames."""

from __future__ import annotations

import ipaddress
import struct
from dataclasses import dataclass
from typing import Any

_TYPES = {1: "discover", 3: "request", 4: "decline", 7: "release", 8: "inform"}
_SERVER_TYPES = {2: "offer", 5: "ack", 6: "nak"}


@dataclass(frozen=True, slots=True)
class DhcpPacket:
    client_mac: str
    observed_mac: str | None
    xid: int
    source_ip: str
    ciaddr: str
    yiaddr: str
    message_type: str
    option54: str | None
    requested_ip: str | None
    lease_seconds: int | None
    payload: dict[str, Any] | None

    @property
    def is_client(self) -> bool:
        return self.message_type in set(_TYPES.values())


def parse_dhcp_frame(frame: bytes) -> DhcpPacket | None:
    network = _ipv4_udp(frame)
    if network is None:
        return None
    source_ip, source_port, destination_port, data = network
    if {source_port, destination_port}.isdisjoint({67, 68}) or len(data) < 240:
        return None
    op, _htype, hlen = data[0], data[1], data[2]
    if hlen != 6 or op not in {1, 2}:
        return None
    xid = struct.unpack_from("!I", data, 4)[0]
    ciaddr = str(ipaddress.ip_address(data[12:16]))
    yiaddr = str(ipaddress.ip_address(data[16:20]))
    mac_bytes = data[28:34]
    mac = ":".join(f"{part:02x}" for part in mac_bytes)
    ethernet_source = ":".join(f"{part:02x}" for part in frame[6:12])
    if data[236:240] != b"\x63\x82\x53\x63":
        return None
    options, order = _options(data[240:])
    if options is None or 53 not in options or len(options[53][0]) != 1:
        return None
    number = options[53][0][0]
    message_type = _TYPES.get(number) or _SERVER_TYPES.get(number)
    if message_type is None:
        return None
    if not all(
        _single_option_length(options, code, length)
        for code, length in ((50, 4), (51, 4), (54, 4))
    ):
        return None
    option54 = _ipv4_option(options, 54)
    lease = _uint_option(options, 51, 4)
    if message_type in _SERVER_TYPES.values():
        return DhcpPacket(mac, None, xid, source_ip, ciaddr, yiaddr, message_type, option54, _ipv4_option(options, 50), lease, None)
    if ethernet_source != mac:
        return None
    prl = list(options.get(55, [b""])[0])
    vendor_raw = options.get(60, [None])[0]
    vendor = None
    if vendor_raw is not None:
        try:
            vendor = vendor_raw.decode("ascii")
        except UnicodeDecodeError:
            return None
        if not 1 <= len(vendor) <= 128 or any(ord(char) < 0x20 or ord(char) > 0x7E for char in vendor):
            return None
    client_id = options.get(61, [None])[0]
    client_kind = "absent"
    if client_id is not None:
        client_kind = "mac" if len(client_id) == 7 and client_id[0] == 1 and client_id[1:] == mac_bytes else "opaque"
    if not _single_option_length(options, 57, 2):
        return None
    if 80 in options and not _single_option_length(options, 80, 0):
        return None
    if 108 in options and not _single_option_length(options, 108, 4):
        return None
    maximum = _uint_option(options, 57, 2)
    if maximum is not None and not 576 <= maximum <= 65535:
        return None
    if len(prl) > 64 or len(order) > 64:
        return None
    payload = {
        "message_type": message_type,
        "parameter_request_list": prl,
        "option_order": order,
        "vendor_class": vendor,
        "client_identifier_kind": client_kind,
        "maximum_message_size": maximum,
        "rapid_commit_requested": 80 in options,
        "capport_requested": 114 in options,
        "ipv6_only_preferred_requested": 108 in options,
        "hostname_present": 12 in options,
    }
    return DhcpPacket(mac, ethernet_source, xid, source_ip, ciaddr, yiaddr, message_type, option54, _ipv4_option(options, 50), lease, payload)


def _options(raw: bytes) -> tuple[dict[int, list[bytes]] | None, list[int]]:
    result: dict[int, list[bytes]] = {}
    order: list[int] = []
    offset = 0
    while offset < len(raw):
        code = raw[offset]
        offset += 1
        if code == 255:
            return result, order
        if code == 0:
            continue
        if offset >= len(raw):
            return None, []
        length = raw[offset]
        offset += 1
        if offset + length > len(raw):
            return None, []
        value = raw[offset:offset + length]
        offset += length
        order.append(code)
        result.setdefault(code, []).append(value)
    return None, []


def _ipv4_udp(frame: bytes) -> tuple[str, int, int, bytes] | None:
    offset = 14
    if len(frame) < offset:
        return None
    ether_type = struct.unpack_from("!H", frame, 12)[0]
    while ether_type in {0x8100, 0x88A8}:
        if len(frame) < offset + 4:
            return None
        ether_type = struct.unpack_from("!H", frame, offset + 2)[0]
        offset += 4
    if ether_type != 0x0800 or len(frame) < offset + 20:
        return None
    ihl = (frame[offset] & 0x0F) * 4
    if frame[offset] >> 4 != 4 or ihl < 20 or len(frame) < offset + ihl + 8 or frame[offset + 9] != 17:
        return None
    total = struct.unpack_from("!H", frame, offset + 2)[0]
    if total < ihl + 8 or len(frame) < offset + total:
        return None
    source = str(ipaddress.ip_address(frame[offset + 12:offset + 16]))
    udp = offset + ihl
    source_port, destination_port, length = struct.unpack_from("!HHH", frame, udp)
    if length < 8 or udp + length > offset + total:
        return None
    return source, source_port, destination_port, frame[udp + 8:udp + length]


def _ipv4_option(options: dict[int, list[bytes]], code: int) -> str | None:
    value = options.get(code, [None])[0]
    return str(ipaddress.ip_address(value)) if value is not None and len(value) == 4 else None


def _uint_option(options: dict[int, list[bytes]], code: int, length: int) -> int | None:
    value = options.get(code, [None])[0]
    return int.from_bytes(value, "big") if value is not None and len(value) == length else None


def _single_option_length(options: dict[int, list[bytes]], code: int, length: int) -> bool:
    values = options.get(code)
    return values is None or (len(values) == 1 and len(values[0]) == length)
