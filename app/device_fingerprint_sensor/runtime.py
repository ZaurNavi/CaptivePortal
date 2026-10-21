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
from .telemetry import SensorTelemetry, SensorRoutineAggregate, resource_snapshot

SURICATA_STATS_INTERVAL_SECONDS = 10.0
SURICATA_HEARTBEAT_TIMEOUT_SECONDS = 30.0


class SensorRuntime:
    def __init__(self, config: SensorConfig, *, telemetry: SensorTelemetry,
                 monotonic=time.monotonic, now=None, preflight=None, capture=None,
                 eve=None, spool=None, producer=None, attribution_config=None,
                 attribution_recorder=None) -> None:
        self.config = config
        self.telemetry = telemetry
        self.monotonic = monotonic
        self.stop_event = threading.Event()
        self.state = "initializing"
        self.reason: str | None = None
        self.preflight = preflight or InterfacePreflight(config.interface)
        self.capture = capture if capture is not None else RawCapture(config.interface, config.guest_cidrs)
        self.eve = eve or EveReceiver(config.eve_socket_path, max_datagram_bytes=config.eve_max_datagram_bytes)
        self.spool = spool or SensorSpool(
            config.spool_path, total_budget_bytes=config.spool_total_budget_bytes,
            main_db_max_bytes=config.spool_main_db_max_bytes,
            max_events=config.spool_max_events,
            write_headroom_bytes=config.spool_write_headroom_bytes, now=now,
            io_stale_purge_gate_enabled=config.io_stale_purge_gate_enabled,
        )
        if isinstance(self.spool, SensorSpool) or config.io_stale_purge_gate_enabled:
            self.spool.io_stale_purge_gate_enabled = config.io_stale_purge_gate_enabled
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
        self._attribution = None
        # No I/O at composition; absent/unprovisioned channel stays fail-closed.
        self._operations_metadata = None
        try:
            from .operations_metadata import SensorMetadataPublisher
            self._operations_metadata = SensorMetadataPublisher({
                "sensor_spool": config.spool_path,
                "network_attribution": attribution_config.db_path if attribution_config is not None and attribution_config.enabled else None,
            }, health_provider=self._operations_health)
        except Exception:
            pass  # Optional metadata composition cannot prevent Sensor startup.
        self._capture_preflight_passed = False
        self._routine_aggregate = None
        if config.io_telemetry_aggregation_enabled:
            try:
                self._routine_aggregate = SensorRoutineAggregate(monotonic=monotonic)
            except Exception:
                self._io_fallback_notice("telemetry_aggregation")
        self._ingress = None
        if config.io_ingress_coalesce_enabled:
            try:
                from .ingress_coalescer import IngressCoalescer
                self._ingress = IngressCoalescer(self.spool, monotonic=monotonic, on_fault=self._ingress_fault)
            except Exception:
                self._io_fallback_notice("ingress_coalescer")
        if attribution_config is not None and attribution_config.enabled:
            from app.network_attribution.dhcp_authority import DhcpAuthorityRecorder
            options = {"clock": now} if now is not None else {}
            self._attribution = attribution_recorder or DhcpAuthorityRecorder(
                attribution_config, config, telemetry=telemetry, **options,
            )

    def _attribution_call(self, method, *args) -> None:
        if self._attribution is None:
            return
        try:
            getattr(self._attribution, method)(*args)
        except Exception:
            # Even failure reporting must never escape into Fingerprint lifecycle.
            try:
                self._attribution.fault("attribution_recorder_unavailable")
            except Exception:
                pass

    def initialize_transport(self) -> None:
        self.spool.initialize()
        if self._ingress is not None:
            self._ingress.start()

    def _submit(self, events) -> int:
        if self._ingress is None:
            return self.spool.enqueue(events)
        return self._ingress.submit(events)

    def _submit_health(self, events) -> int:
        if self._ingress is None:
            return self.spool.enqueue(events)
        if not events:
            return 0  # Health dedup generated no transition/heartbeat to order.
        return self._ingress.barrier(events)

    def _ingress_fault(self, category: str) -> None:
        if category == "spool_write":
            self._delivery_available = False
            self.state, self.reason = "degraded", "spool_capacity" if self.spool.capacity_blocked else "ingest_delivery_unavailable"
        self._io_fallback_notice(category)
        if category == "spool_write":
            if not self.stop_event.is_set():
                try:
                    self._submit_health(self.health.all("unavailable", "ingest_delivery_unavailable"))
                except Exception:
                    pass  # No successful source-health claim from failed storage.

    def _io_fallback_notice(self, category: str) -> None:
        try:
            self.telemetry.emit("fingerprint_sensor_io_fallback", error_category=category)
        except Exception:
            pass

    def _flush_ingress_fault_exit(self) -> None:
        if self._ingress is not None:
            try:
                self._ingress.barrier()
            except Exception:
                self._io_fallback_notice("ingress_flush")

    def preflight_or_report(self) -> bool:
        try:
            self.preflight.validate()
        except Exception:
            self._attribution_call("fault", "capture_interface_unavailable")
            self.state, self.reason = "unavailable", "capture_interface_unavailable"
            self._submit_health(self.health.all("unavailable", "capture_interface_unavailable"))
            self.telemetry.emit("fingerprint_sensor_unavailable", runtime_state=self.state, reason=self.reason)
            return False
        self._capture_preflight_passed = True
        return True

    def start(self) -> None:
        self.eve.open()
        try:
            self.capture.open()
        except Exception:
            self._attribution_call("fault", "raw_capture_unavailable")
            raise
        if self._capture_preflight_passed:
            self._attribution_call("start")
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
                    self._attribution_call("poll")
                    continue
                frame, received_ns, observed_at = received
                if self._ingress is not None and self.stop_event.is_set():
                    break
                if self.dedup.is_duplicate(frame, received_ns):
                    continue
                self._submit(self.normalizer.raw(frame, observed_at))
                self._attribution_call("record_frame", frame, observed_at)
        except Exception:
            self._flush_ingress_fault_exit()
            self._attribution_call("fault", "raw_capture_unavailable")
            if not self.stop_event.is_set():
                self.state, self.reason = "degraded", "raw_parser_unavailable"
                self._set_local(("dhcp", "tcp_syn"), "unavailable", "raw_parser_unavailable")

    def _eve_loop(self) -> None:
        last_truncated = 0
        try:
            while not self.stop_event.is_set():
                value = self.eve.receive()
                if self._ingress is not None and self.stop_event.is_set():
                    break
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
                self._submit(events)
                for event in events:
                    if self._suricata_ready and event.source_kind in {"tls_client", "quic_client"}:
                        self._set_local((event.source_kind,), "available", None)
        except Exception:
            self._flush_ingress_fault_exit()
            if not self.stop_event.is_set():
                self.state, self.reason = "degraded", "suricata_unavailable"
                self._set_local(("tls_client", "quic_client"), "unavailable", "suricata_unavailable")

    def _delivery_loop(self) -> None:
        if self._ingress is None:
            return self._delivery_loop_inner()
        try:
            self._delivery_loop_inner()
        except Exception:
            self._flush_ingress_fault_exit()
            self._delivery_available = False
            self.state, self.reason = "degraded", "ingest_delivery_unavailable"
            self.telemetry.emit("fingerprint_delivery_retry", delivery_retry=1)
            if not self.stop_event.is_set():
                try:
                    self._submit_health(self.health.all("unavailable", "ingest_delivery_unavailable"))
                except Exception:
                    pass

    def _delivery_loop_inner(self) -> None:
        while not self.stop_event.is_set():
            try:
                result = self.producer.deliver_once()
            except Exception:
                result = None
            if result is None or result.status == "retry":
                self._delivery_available = False
                if self._ingress is None or not self.stop_event.is_set():
                    self._submit_health(self.health.all("unavailable", "ingest_delivery_unavailable"))
                delay = result.delay_seconds if result is not None else 1.0
                self.telemetry.emit("fingerprint_delivery_retry", delivery_retry=1)
            elif result.status == "permanent":
                self._flush_ingress_fault_exit()
                self._delivery_available = False
                self._delivery_permanent_fault = True
                self.state, self.reason = "degraded", "delivery_permanent_reject"
                self.telemetry.emit("fingerprint_delivery_rejected", delivery_permanent_reject=1)
                return
            else:
                if result.status == "delivered":
                    if not self._delivery_available and (self._ingress is None or not self.stop_event.is_set()):
                        self._delivery_available = True
                        self._publish_local_health()
                    if self._routine_aggregate is not None:
                        try:
                            self._routine_aggregate.delivery(result.delivered)
                        except Exception:
                            self._routine_aggregate = None
                            self._io_fallback_notice("telemetry_aggregation")
                            self.telemetry.emit("fingerprint_delivery_completed", delivery_success=result.delivered)
                    else:
                        self.telemetry.emit("fingerprint_delivery_completed", delivery_success=result.delivered)
                delay = 1.0
            self.stop_event.wait(delay)

    def _telemetry_loop(self) -> None:
        while not self.stop_event.wait(60.0):
            if self._delivery_available:
                self._publish_local_health()
            self._refresh_state()
            self._emit_metrics()
            if not self.stop_event.is_set():
                try:
                    self._operations_metadata.publish(self.stop_event)
                except Exception:
                    pass  # Optional metadata never changes capture/spool health.

    def _operations_health(self):
        """Already-refreshed lifecycle only; never a health-triggered DB read."""
        from app.operations_health import sensor_health
        heartbeat = self._suricata_last_heartbeat
        return sensor_health(self.state, dict(
            preflight=self._capture_preflight_passed is True,
            raw_capture=all(self._local_health.get(kind, (None,))[0] == "available" for kind in ("dhcp", "tcp_syn")),
            suricata=(self._suricata_ready is True and heartbeat is not None
                      and 0 <= self.monotonic() - heartbeat <= SURICATA_HEARTBEAT_TIMEOUT_SECONDS
                      and all(self._local_health.get(kind, (None,))[0] == "available" for kind in ("tls_client", "quic_client"))),
            delivery=self._delivery_available is True and not self._delivery_permanent_fault
                     and not getattr(self.producer, "permanent_fault", False),
            spool=not self.spool.capacity_blocked and not self.stop_event.is_set()))

    def _set_local(self, kinds: tuple[str, ...], status: str, reason: str | None) -> None:
        events = []
        for kind in kinds:
            self._local_health[kind] = (status, reason)
            if self._delivery_available:
                event = self.health.transition(kind, status, reason)
                if event is not None:
                    events.append(event)
        self._submit_health(events)
        self._refresh_state()

    def _publish_local_health(self) -> None:
        events = []
        for kind, (status, reason) in self._local_health.items():
            event = self.health.transition(kind, status, reason)
            if event is not None:
                events.append(event)
        self._submit_health(events)
        self._refresh_state()

    def _emit_stats(self, value: dict[str, Any]) -> None:
        capture = value["stats"]["capture"]
        if self._routine_aggregate is not None:
            try:
                self._routine_aggregate.stats(capture)
                return
            except Exception:
                self._routine_aggregate = None
                self._io_fallback_notice("telemetry_aggregation")
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

    def _take_routine_aggregate(self, *, final: bool = False) -> dict[str, Any]:
        if self._routine_aggregate is None:
            return {}
        try:
            return self._routine_aggregate.snapshot_reset(final=final)
        except Exception:
            self._routine_aggregate = None
            self._io_fallback_notice("telemetry_aggregation")
            return {}

    def _emit_final_routine(self) -> None:
        fields = self._take_routine_aggregate(final=True)
        if fields:
            self.telemetry.emit("fingerprint_sensor_metrics", runtime_state=self.state, **fields)

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
            **self._take_routine_aggregate(),
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
        if self._ingress is not None:
            return self._shutdown_coalesced()
        self.state, self.reason = "stopping", "stopping"
        self.stop_event.set()
        self._attribution_call("fault", "sensor_shutdown")
        self.capture.close()
        self.eve.close()
        deadline = self.monotonic() + 20.0
        for thread in self.threads:
            thread.join(max(0.0, deadline - self.monotonic()))
        clean = all(not thread.is_alive() for thread in self.threads)
        self._attribution_call("shutdown")
        self.spool.close()
        self._emit_final_routine()
        self.telemetry.emit("fingerprint_sensor_stopped", runtime_state="stopping")
        return clean

    def _shutdown_coalesced(self) -> bool:
        deadline = self.monotonic() + 20.0
        self.state, self.reason = "stopping", "stopping"
        self.stop_event.set()
        self._attribution_call("fault", "sensor_shutdown")
        closed_sources = True
        for source in (self.capture, self.eve):
            try:
                source.close()
            except Exception:
                closed_sources = False
        source_threads = [thread for thread in self.threads if thread.name in {"fingerprint-raw", "fingerprint-eve"}]
        for thread in source_threads:
            thread.join(max(0.0, deadline - self.monotonic()))
        sources_done = all(not thread.is_alive() for thread in source_threads)
        try:
            flushed = self._ingress.shutdown(deadline=deadline)
        except Exception:
            flushed = False
            self._io_fallback_notice("ingress_shutdown")
        for thread in self.threads:
            if thread not in source_threads:
                thread.join(max(0.0, deadline - self.monotonic()))
        workers_done = all(not thread.is_alive() for thread in self.threads)
        clean = closed_sources and sources_done and workers_done and flushed and self.monotonic() <= deadline
        # Never close SQLite underneath a still-running writer/producer.
        if workers_done and self._ingress.timer_stopped:
            self._attribution_call("shutdown")
            try:
                self.spool.close()
            except Exception:
                clean = False
        self._emit_final_routine()
        clean = clean and self.monotonic() <= deadline
        if clean:
            self.telemetry.emit("fingerprint_sensor_stopped", runtime_state="stopping")
        else:
            self.telemetry.emit("fingerprint_sensor_stopped", runtime_state="stopping", status="unclean")
        return clean and self.monotonic() <= deadline
