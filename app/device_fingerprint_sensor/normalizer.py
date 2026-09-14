"""Normalize raw and EVE observations into the frozen Task-01 envelope."""

from __future__ import annotations

import ipaddress
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from app.device_fingerprint.network_schemas import (
    validate_dhcp_v1,
    validate_quic_v1,
    validate_tls_v1,
)
from app.device_fingerprint.validation import format_utc

from .dhcp import DhcpPacket, parse_dhcp_frame
from .models import NormalizedEvent, SensorConfig
from .scope import DhcpScopeResolver
from .tcp_syn import parse_tcp_syn_frame

UTC = timezone.utc
_GREASE = frozenset(range(0x0A0A, 0xFAFA + 1, 0x1010))


class NetworkNormalizer:
    def __init__(self, config: SensorConfig, *, monotonic: Callable[[], float]) -> None:
        self.config = config
        self.scope = DhcpScopeResolver(
            config.guest_cidrs, config.dhcp_server_authority,
            config.dhcp_option54_authority, monotonic=monotonic,
        )
        self.counters: dict[str, int] = {}

    def raw(self, frame: bytes, observed_at: str) -> list[NormalizedEvent]:
        dhcp = parse_dhcp_frame(frame)
        if dhcp is not None:
            self._count("dhcp_candidate_count")
            return self._dhcp(dhcp, observed_at)
        syn = parse_tcp_syn_frame(frame, self.config.guest_cidrs)
        if syn is None:
            return []
        mac, ip, payload = syn
        self._count("tcp_syn_event_count")
        return [self._evidence("tcp_syn", "ipv4", "packet-tcp-syn", "1.0.0", observed_at, mac, ip, "valid", payload)]

    def eve(self, value: Any) -> list[NormalizedEvent]:
        if not isinstance(value, dict):
            self._count("eve_json_invalid")
            return []
        kind = value.get("event_type")
        if kind == "tls":
            self._count("tls_eve_count")
            event = self._tls(value)
            if event:
                self._count("tls_normalized_count")
            return [event] if event else []
        if kind == "quic":
            self._count("quic_eve_count")
            event = self._quic(value)
            if event:
                self._count("quic_normalized_count")
            return [event] if event else []
        return []

    def _dhcp(self, packet: DhcpPacket, observed_at: str) -> list[NormalizedEvent]:
        if not packet.is_client:
            if packet.message_type not in {"offer", "ack"} or packet.option54 is None:
                return []
            released = self.scope.server_reply(
                packet.client_mac, packet.xid, yiaddr=packet.yiaddr,
                server_source=packet.source_ip, option54=packet.option54,
                lease_seconds=packet.lease_seconds, is_ack=packet.message_type == "ack",
            )
            result = [self._from_pending(item) for item in released]
            if result:
                self._count("dhcp_scoped_count", len(result))
            return result
        actual = packet.source_ip if self._guest(packet.source_ip) else packet.ciaddr if self._guest(packet.ciaddr) else None
        direct = actual is not None
        if packet.message_type == "decline":
            binding_ip = packet.requested_ip or actual
            direct = bool(
                binding_ip
                and self._guest(binding_ip)
                and (
                    self.scope.lease_proves(packet.client_mac, binding_ip)
                    or self.scope.transaction_proves(packet.client_mac, packet.xid, binding_ip)
                )
            )
            if not direct:
                return []
        elif packet.message_type == "release" and not direct:
            direct = bool(
                packet.requested_ip
                and self._guest(packet.requested_ip)
                and self.scope.lease_proves(packet.client_mac, packet.requested_ip)
            )
            if not direct:
                return []
        if packet.payload is None:
            return []
        try:
            payload = dict(validate_dhcp_v1(packet.payload))
        except Exception:
            return []
        pending = {
            "observed_at": observed_at,
            "mac": packet.observed_mac,
            "ip": actual,
            "subtype": packet.message_type,
            "payload": payload,
        }
        released = self.scope.client(packet.client_mac, packet.xid, pending, directly_scoped=direct)
        result = [self._from_pending(item) for item in released]
        if result:
            self._count("dhcp_scoped_count", len(result))
        return result

    def _from_pending(self, item: dict[str, Any]) -> NormalizedEvent:
        return self._evidence(
            "dhcp", item["subtype"], "packet-dhcp", "1.0.0",
            item["observed_at"], item["mac"], item["ip"], "valid", item["payload"],
        )

    def _tls(self, event: dict[str, Any]) -> NormalizedEvent | None:
        common = self._eve_common(event)
        tls = event.get("tls")
        if common is None or not isinstance(tls, dict):
            return None
        split = _split_ja4(tls.get("ja4"), "t")
        if split is None:
            return None
        alpns = tls.get("client_alpns")
        if alpns == []:
            alpns = None
        handshake = tls.get("client_handshake")
        extensions = handshake.get("exts") if isinstance(handshake, dict) else None
        flags = _extension_flags(extensions)
        a, b, c = split
        payload = {
            "ja4": tls["ja4"], "ja4_a": a, "ja4_b": b, "ja4_c": c,
            "tls_version_family": {"13": "tls1_3", "12": "tls1_2"}.get(a[1:3], "other"),
            "client_alpns": alpns,
            "ech_extension_present": flags[0], "grease_extension_present": flags[1],
        }
        try:
            payload = dict(validate_tls_v1(payload))
        except Exception:
            return None
        return self._evidence("tls_client", "client_hello", "suricata-tls-ja4", "8.0.6", *common, "valid" if extensions is not None else "partial", payload)

    def _quic(self, event: dict[str, Any]) -> NormalizedEvent | None:
        common = self._eve_common(event)
        quic = event.get("quic")
        if common is None or not isinstance(quic, dict):
            return None
        split = _split_ja4(quic.get("ja4"), "q")
        raw_version = quic.get("version")
        if split is None or not isinstance(raw_version, str) or not __import__("re").fullmatch(r"[0-9a-f]{1,8}", raw_version):
            self._count("quic_version_invalid")
            return None
        extensions = quic.get("extensions")
        types = None
        if isinstance(extensions, list):
            types = []
            for item in extensions:
                if not isinstance(item, dict) or type(item.get("type")) is not int:
                    return None
                types.append(item["type"])
        flags = _extension_flags(types)
        a, b, c = split
        payload = {
            "ja4": quic["ja4"], "ja4_a": a, "ja4_b": b, "ja4_c": c,
            "quic_version": "0x" + f"{int(raw_version, 16):08x}",
            "ech_extension_present": flags[0], "grease_extension_present": flags[1],
        }
        try:
            payload = dict(validate_quic_v1(payload))
        except Exception:
            return None
        return self._evidence("quic_client", "client_hello", "suricata-quic-ja4", "8.0.6", *common, "valid" if types is not None else "partial", payload)

    def _eve_common(self, event: dict[str, Any]) -> tuple[str, str, str] | None:
        try:
            timestamp = _eve_timestamp(event.get("timestamp"))
            ip = str(ipaddress.ip_address(event.get("src_ip")))
            ether = event.get("ether")
            mac = ether.get("src_mac") if isinstance(ether, dict) else None
            if not isinstance(mac, str) or not self._guest(ip):
                return None
            normalized = __import__("app.common.mac", fromlist=["format_mac_colon"]).format_mac_colon(
                __import__("app.common.mac", fromlist=["parse_mac"]).parse_mac(mac)
            )
            return timestamp, normalized, ip
        except (TypeError, ValueError):
            self._count("missing_l2_identity")
            return None

    def _evidence(self, kind: str, subtype: str, extractor: str, version: str,
                  observed_at: str, mac: str, ip: str | None, quality: str,
                  payload: dict[str, Any]) -> NormalizedEvent:
        identity = str(uuid.uuid4())
        return NormalizedEvent("evidence", identity, kind, observed_at, {
            "source_event_id": identity, "source_kind": kind, "source_subtype": subtype,
            "extractor_name": extractor, "extractor_version": version,
            "feature_schema_version": 1, "rule_version": None,
            "site_id": self.config.site_id, "capture_source_id": self.config.capture_source_id,
            "observed_at": observed_at, "observed_mac": mac, "observed_ip": ip,
            "quality_state": quality, "payload": payload,
        })

    def _guest(self, value: str) -> bool:
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            return False
        return any(address in network for network in self.config.guest_cidrs)

    def _count(self, name: str, amount: int = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + amount


def _split_ja4(value: Any, family: str) -> tuple[str, str, str] | None:
    if not isinstance(value, str):
        return None
    parts = value.split("_")
    if len(parts) != 3 or not parts[0].startswith(family):
        return None
    return parts[0], parts[1], parts[2]


def _extension_flags(values: Any) -> tuple[bool | None, bool | None]:
    if not isinstance(values, list) or any(type(item) is not int for item in values):
        return None, None
    return 65037 in values, any(item in _GREASE for item in values)


def _eve_timestamp(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError
    return format_utc(parsed.astimezone(UTC))
