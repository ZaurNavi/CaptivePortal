"""Independent bounded DHCP authority parsing of an already received frame."""

import ipaddress
import struct
from datetime import datetime, timezone

from app.device_fingerprint.validation import format_utc

from .models import NetworkAttributionConflict, NetworkAttributionValidationError
from .repository import NetworkAttributionRepository
from .validation import canonical_mac, make_fact


def _packet(frame):
    if not isinstance(frame, bytes) or not 14 <= len(frame) <= 65535:
        return None
    offset, kind = 14, int.from_bytes(frame[12:14], "big")
    while kind in {0x8100, 0x88A8}:
        if len(frame) < offset + 4:
            return None
        kind = int.from_bytes(frame[offset + 2:offset + 4], "big")
        offset += 4
    if kind != 0x0800 or len(frame) < offset + 20:
        return None
    ihl = (frame[offset] & 15) * 4
    total = int.from_bytes(frame[offset + 2:offset + 4], "big")
    # No fragmented UDP is an admitted complete DHCP lifecycle observation.
    if (frame[offset] >> 4 != 4 or ihl < 20 or total < ihl + 8 + 240
            or len(frame) < offset + total or frame[offset + 9] != 17
            or int.from_bytes(frame[offset + 6:offset + 8], "big") & 0x3FFF):
        return None
    udp = offset + ihl
    src_port, dst_port, length = struct.unpack_from("!HHH", frame, udp)
    if length < 248 or udp + length > offset + total:
        return None
    data = frame[udp + 8:udp + length]
    if data[:3] not in {b"\x01\x01\x06", b"\x02\x01\x06"} or data[236:240] != b"\x63\x82\x53\x63":
        return None
    selected = {}
    cursor, ended = 240, False
    while cursor < len(data):
        code = data[cursor]
        cursor += 1
        if code == 255:
            ended = True
            break
        if code == 0:
            continue
        if cursor >= len(data):
            return None
        size = data[cursor]
        cursor += 1
        if cursor + size > len(data):
            return None
        if code in {50, 51, 53, 54}:
            if code in selected or size != (1 if code == 53 else 4):
                return None
            selected[code] = data[cursor:cursor + size]
        cursor += size
    message = {b"\x05": "ack", b"\x07": "release", b"\x04": "decline"}.get(selected.get(53))
    if not ended or message is None:
        return None
    if message == "ack":
        if data[0] != 2 or (src_port, dst_port) not in {(67, 68), (67, 67)}:
            return None
    elif data[0] != 1 or (src_port, dst_port) != (68, 67) or data[28:34] != frame[6:12]:
        return None
    return data, selected, message, str(ipaddress.IPv4Address(frame[offset + 12:offset + 16]))


def authority_fact_from_frame(frame, event_at, ingested_at, sensor_config):
    parsed = _packet(frame)
    if parsed is None:
        return None
    data, options, message, source_ip = parsed
    try:
        mac = canonical_mac(":".join(f"{part:02X}" for part in data[28:34]))
        if message == "ack":
            address = ipaddress.IPv4Address(data[16:20])
            server = source_ip
            option54 = str(ipaddress.IPv4Address(options[54])) if 54 in options else None
            lease = int.from_bytes(options[51], "big") if 51 in options else None
            if (server != sensor_config.dhcp_server_authority
                    or option54 != sensor_config.dhcp_option54_authority
                    or lease is None or not 1 <= lease <= 86400):
                return None
            authority = "trusted_dhcp_ack"
        else:
            # RELEASE declares ciaddr; DECLINE declares requested-address option 50.
            if message == "decline" and 50 not in options:
                return None
            address = ipaddress.IPv4Address(data[12:16] if message == "release" else options[50])
            server = option54 = lease = None
            authority = "validated_client_" + message
        if not any(address in network for network in sensor_config.guest_cidrs):
            return None
        return make_fact(site_id=sensor_config.site_id, capture_source_id=sensor_config.capture_source_id,
                         event_at=event_at, ingested_at=ingested_at, message_type=message, client_mac=mac,
                         ipv4=str(address), xid=int.from_bytes(data[4:8], "big"), server_ipv4=server,
                         option54_ipv4=option54, lease_seconds=lease, authority_class=authority)
    except (ValueError, NetworkAttributionValidationError):
        return None


class DhcpAuthorityRecorder:
    def __init__(self, config, sensor_config, *, telemetry, clock=lambda: datetime.now(timezone.utc), repository=None):
        self.config, self.sensor_config, self.telemetry, self.clock = config, sensor_config, telemetry, clock
        self.repository = repository or NetworkAttributionRepository(config, clock=clock)
        self.permanent_fault = False
        self._reported = False
        self._last_retention = None
        self._last_poll = None
        self._activated_at = None

    def start(self):
        """Called only after capture preflight PASS and raw capture open."""
        try:
            self.repository.initialize()
            self._activated_at = format_utc(self.clock())
            self.repository.capture_started(self.sensor_config.site_id, self.sensor_config.capture_source_id,
                                            self._activated_at)
        except Exception:
            self.fault("attribution_store_unavailable")

    def record_frame(self, frame, event_at):
        if self.permanent_fault:
            return
        try:
            now = self.clock()
            self.poll()
            if self.permanent_fault:
                return
            # Frames already queued before the first persisted usable coverage
            # are not an authoritative pre-activation backfill.
            if self._activated_at is None or event_at < self._activated_at:
                return
            fact = authority_fact_from_frame(frame, event_at, format_utc(now), self.sensor_config)
            if fact is not None:
                # An actual authority frame confirms this live capture even
                # between the bounded idle-poll watermark updates.
                self.repository.confirm_capture(self.sensor_config.site_id, self.sensor_config.capture_source_id,
                                                format_utc(self.clock()))
                self.repository.record(fact)
        except NetworkAttributionConflict:
            self.fault("authority_event_conflict")
        except Exception:
            self.fault("attribution_recorder_unavailable")

    def poll(self):
        if self.permanent_fault:
            return
        try:
            now = self.clock()
            if self._last_poll is None or (now - self._last_poll).total_seconds() >= 1:
                self.repository.confirm_capture(self.sensor_config.site_id, self.sensor_config.capture_source_id, format_utc(now))
                self._last_poll = now
            if self._last_retention is None or (now - self._last_retention).total_seconds() >= 60:
                self.repository.retain(at=format_utc(now))
                self.repository.maintain_wal()
                self._last_retention = now
        except Exception:
            self.fault("attribution_store_unavailable")

    def fault(self, reason):
        self.permanent_fault = True
        try:
            self.repository.coverage(self.sensor_config.site_id, self.sensor_config.capture_source_id,
                                     "unavailable", format_utc(self.clock()), reason)
        except Exception:
            pass
        if not self._reported:
            self._reported = True
            self.telemetry.emit("network_attribution_unavailable", status="unavailable", reason=reason)

    def shutdown(self):
        try:
            if self.repository.connection is not None:
                self.repository.coverage(self.sensor_config.site_id, self.sensor_config.capture_source_id,
                                         "unavailable", format_utc(self.clock()), "sensor_shutdown")
        finally:
            self.repository.close()
