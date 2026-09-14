"""Independent fail-open sensor lifecycle and workers."""

from __future__ import annotations

import subprocess
import threading
import time
from typing import Any

from .capture import InterfacePreflight, RawCapture
from .dedup import ExactFrameDeduplicator
from .eve import EveReceiver
from .health import SourceHealthTracker
from .models import SensorConfig
from .normalizer import NetworkNormalizer
from .producer import EvidenceProducer
from .spool import SensorSpool
from .telemetry import SensorTelemetry, resource_snapshot

SURICATA_STATS_INTERVAL_SECONDS = 10.0
SURICATA_HEARTBEAT_TIMEOUT_SECONDS = 30.0


class SensorRuntime:
    def __init__(self, config: SensorConfig, *, telemetry: SensorTelemetry,
                 monotonic=time.monotonic, now=None, preflight=None, capture=None,
                 eve=None, spool=None, producer=None) -> None:
        self.config = config
        self.telemetry = telemetry
        self.monotonic = monotonic
        self.stop_event = threading.Event()
        self.state = "initializing"
        self.reason: str | None = None
        self.preflight = preflight or InterfacePreflight(config.interface)
        self.capture = capture or RawCapture(config.interface)
        self.eve = eve or EveReceiver(config.eve_socket_path, max_datagram_bytes=config.eve_max_datagram_bytes)
        self.spool = spool or SensorSpool(
            config.spool_path, total_budget_bytes=config.spool_total_budget_bytes,
            main_db_max_bytes=config.spool_main_db_max_bytes,
            max_events=config.spool_max_events,
            write_headroom_bytes=config.spool_write_headroom_bytes, now=now,
        )
        self.producer = producer or EvidenceProducer(config, self.spool)
        self.normalizer = NetworkNormalizer(config, monotonic=monotonic)
        self.health = SourceHealthTracker(config, monotonic=monotonic, now=now)
        self.dedup = ExactFrameDeduplicator(
            config.capture_source_id, max_entries=config.raw_dedup_max_entries,
            horizon_ms=config.raw_dedup_horizon_ms,
        )
        self.threads: list[threading.Thread] = []
        self._suricata_ready = False
        self._suricata_last_heartbeat: float | None = None
        self._local_health = {
            "dhcp": ("unavailable", "raw_parser_unavailable"),
            "tcp_syn": ("unavailable", "raw_parser_unavailable"),
            "tls_client": ("unavailable", "suricata_unavailable"),
            "quic_client": ("unavailable", "suricata_unavailable"),
        }
        self._delivery_available = True
        self._delivery_permanent_fault = False

    def initialize_transport(self) -> None:
        self.spool.initialize()

    def preflight_or_report(self) -> bool:
        try:
            self.preflight.validate()
        except Exception:
            self.state, self.reason = "unavailable", "capture_interface_unavailable"
            self.spool.enqueue(self.health.all("unavailable", "capture_interface_unavailable"))
            self.telemetry.emit("fingerprint_sensor_unavailable", runtime_state=self.state, reason=self.reason)
            return False
        return True

    def start(self) -> None:
        self.eve.open()
        self.capture.open()
        self._set_local(("dhcp", "tcp_syn"), "available", None)
        self._set_local(("tls_client", "quic_client"), "unavailable", "suricata_unavailable")
        self.state, self.reason = "degraded", "suricata_unavailable"
        self.threads = [
            threading.Thread(target=self._raw_loop, name="fingerprint-raw", daemon=False),
            threading.Thread(target=self._eve_loop, name="fingerprint-eve", daemon=False),
            threading.Thread(target=self._delivery_loop, name="fingerprint-delivery", daemon=False),
            threading.Thread(target=self._telemetry_loop, name="fingerprint-telemetry", daemon=False),
        ]
        for thread in self.threads:
            thread.start()
        self.telemetry.emit("fingerprint_sensor_started", runtime_state=self.state, reason=self.reason)

    def _raw_loop(self) -> None:
        try:
            while not self.stop_event.is_set():
                received = self.capture.receive()
                if received is None:
                    continue
                frame, received_ns, observed_at = received
                if self.dedup.is_duplicate(frame, received_ns):
                    continue
                self.spool.enqueue(self.normalizer.raw(frame, observed_at))
        except Exception:
            if not self.stop_event.is_set():
                self.state, self.reason = "degraded", "raw_parser_unavailable"
                self._set_local(("dhcp", "tcp_syn"), "unavailable", "raw_parser_unavailable")

    def _eve_loop(self) -> None:
        last_truncated = 0
        try:
            while not self.stop_event.is_set():
                value = self.eve.receive()
                self._check_suricata_heartbeat()
                if self.eve.truncated != last_truncated:
                    last_truncated = self.eve.truncated
                    self.state, self.reason = "degraded", "eve_datagram_truncated"
                    self._set_local(("tls_client", "quic_client"), "unavailable", "eve_datagram_truncated")
                    continue
                if value is None:
                    continue
                if value.get("event_type") == "stats" and self._valid_stats(value):
                    self._suricata_heartbeat()
                    self._emit_stats(value)
                    continue
                events = self.normalizer.eve(value)
                self.spool.enqueue(events)
                for event in events:
                    if self._suricata_ready and event.source_kind in {"tls_client", "quic_client"}:
                        self._set_local((event.source_kind,), "available", None)
        except Exception:
            if not self.stop_event.is_set():
                self.state, self.reason = "degraded", "suricata_unavailable"
                self._set_local(("tls_client", "quic_client"), "unavailable", "suricata_unavailable")

    def _delivery_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                result = self.producer.deliver_once()
            except Exception:
                result = None
            if result is None or result.status == "retry":
                self._delivery_available = False
                self.spool.enqueue(self.health.all("unavailable", "ingest_delivery_unavailable"))
                delay = result.delay_seconds if result is not None else 1.0
                self.telemetry.emit("fingerprint_delivery_retry", delivery_retry=1)
            elif result.status == "permanent":
                self._delivery_available = False
                self._delivery_permanent_fault = True
                self.state, self.reason = "degraded", "delivery_permanent_reject"
                self.telemetry.emit("fingerprint_delivery_rejected", delivery_permanent_reject=1)
                return
            else:
                if result.status == "delivered":
                    if not self._delivery_available:
                        self._delivery_available = True
                        self._publish_local_health()
                    self.telemetry.emit("fingerprint_delivery_completed", delivery_success=result.delivered)
                delay = 1.0
            self.stop_event.wait(delay)

    def _telemetry_loop(self) -> None:
        while not self.stop_event.wait(60.0):
            if self._delivery_available:
                self._publish_local_health()
            self._refresh_state()
            self._emit_metrics()

    def _set_local(self, kinds: tuple[str, ...], status: str, reason: str | None) -> None:
        events = []
        for kind in kinds:
            self._local_health[kind] = (status, reason)
            if self._delivery_available:
                event = self.health.transition(kind, status, reason)
                if event is not None:
                    events.append(event)
        self.spool.enqueue(events)
        self._refresh_state()

    def _publish_local_health(self) -> None:
        events = []
        for kind, (status, reason) in self._local_health.items():
            event = self.health.transition(kind, status, reason)
            if event is not None:
                events.append(event)
        self.spool.enqueue(events)
        self._refresh_state()

    def _emit_stats(self, value: dict[str, Any]) -> None:
        capture = value["stats"]["capture"]
        self.telemetry.emit(
            "fingerprint_suricata_stats",
            suricata_version="8.0.6",
            capture_kernel_packets=capture.get("kernel_packets"),
            capture_kernel_drops=capture.get("kernel_drops"),
            capture_kernel_ifdrops=capture.get("kernel_ifdrops"),
        )

    def _suricata_heartbeat(self) -> None:
        self._suricata_last_heartbeat = self.monotonic()
        self._suricata_ready = True
        self._set_local(("tls_client", "quic_client"), "available", None)

    def _check_suricata_heartbeat(self) -> None:
        if (
            self._suricata_ready
            and self._suricata_last_heartbeat is not None
            and self.monotonic() - self._suricata_last_heartbeat > SURICATA_HEARTBEAT_TIMEOUT_SECONDS
        ):
            self._suricata_ready = False
            self._set_local(("tls_client", "quic_client"), "unavailable", "suricata_unavailable")

    def _emit_metrics(self) -> None:
        metrics = self.spool.metrics()
        counters = dict(self.normalizer.counters)
        counters["eve_datagram_truncated"] = getattr(self.eve, "truncated", 0)
        counters["eve_json_invalid"] = getattr(self.eve, "invalid", 0) + counters.get("eve_json_invalid", 0)
        self.telemetry.emit(
            "fingerprint_sensor_metrics", runtime_state=self.state,
            raw_packet_count=self.dedup.raw_packet_count,
            duplicate_packet_count=self.dedup.duplicate_packet_count,
            deduplicated_packet_count=self.dedup.deduplicated_packet_count,
            raw_dedup_ratio=self.dedup.ratio,
            spool_rows=metrics["rows"], spool_bytes=metrics["spool_bytes"],
            oldest_spool_age=metrics["oldest_spool_age"],
            stale_spool_event_dropped=self.spool.stale_dropped,
            **counters, **resource_snapshot(),
        )

    @staticmethod
    def _valid_stats(value: dict[str, Any]) -> bool:
        stats = value.get("stats")
        if not isinstance(stats, dict):
            return False
        capture = stats.get("capture")
        return isinstance(capture, dict) and all(type(capture.get(key)) in {int, float} for key in ("kernel_packets", "kernel_drops"))

    def _refresh_state(self) -> None:
        if self._delivery_permanent_fault or getattr(self.producer, "permanent_fault", False):
            self.state, self.reason = "degraded", "delivery_permanent_reject"
        elif all(status == "available" for status, _reason in self._local_health.values()) and self._delivery_available and not self.spool.capacity_blocked:
            self.state, self.reason = "ready", None
        elif self.state != "unavailable":
            self.state = "degraded"
            if self.spool.capacity_blocked:
                self.reason = "spool_capacity"

    def shutdown(self) -> bool:
        self.state, self.reason = "stopping", "stopping"
        self.stop_event.set()
        self.capture.close()
        self.eve.close()
        deadline = self.monotonic() + 20.0
        for thread in self.threads:
            thread.join(max(0.0, deadline - self.monotonic()))
        clean = all(not thread.is_alive() for thread in self.threads)
        self.spool.close()
        self.telemetry.emit("fingerprint_sensor_stopped", runtime_state="stopping")
        return clean
