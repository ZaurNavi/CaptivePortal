"""Sanitized sensor operational telemetry."""

from __future__ import annotations

import json
import logging
import math
import threading
from pathlib import Path
from typing import Any, Mapping

SAFE_FIELDS = frozenset({
    "runtime_state", "reason", "source_kind", "status", "error_category",
    "raw_packet_count", "duplicate_packet_count", "deduplicated_packet_count",
    "raw_dedup_ratio", "dhcp_candidate_count", "dhcp_scoped_count",
    "tcp_syn_event_count", "tls_eve_count", "tls_normalized_count",
    "quic_eve_count", "quic_normalized_count", "eve_datagram_truncated",
    "eve_json_invalid", "quic_version_invalid", "missing_l2_identity", "spool_rows", "spool_bytes",
    "oldest_spool_age", "delivery_success", "delivery_retry",
    "delivery_success_batches",
    "delivery_permanent_reject", "stale_spool_event_dropped", "artifact_sha",
    "artifact_tree", "service_name", "process_started_at", "suricata_version",
    "capture_kernel_packets", "capture_kernel_drops", "capture_kernel_ifdrops",
    "sensor_cpu_usec", "sensor_memory_current", "suricata_cpu_usec",
    "suricata_memory_current", "suricata_process_active",
})
_MAX_ROUTINE_COUNTER = 9223372036854775807


class SensorRoutineAggregate:
    """Non-authoritative minute counters, atomically consumed by metrics/shutdown."""
    def __init__(self, *, monotonic) -> None:
        self._monotonic = monotonic
        self._lock = threading.Lock()
        self._window_started = monotonic()
        self._delivered = self._batches = 0
        self._stats: dict[str, int | float] = {}

    def delivery(self, delivered: int) -> None:
        if type(delivered) is not int or not 0 <= delivered <= _MAX_ROUTINE_COUNTER:
            raise ValueError("invalid delivery counter")
        with self._lock:
            self._delivered = min(_MAX_ROUTINE_COUNTER, self._delivered + delivered)
            self._batches = min(_MAX_ROUTINE_COUNTER, self._batches + 1)

    def stats(self, capture: Mapping[str, Any]) -> None:
        fields = {}
        for key in ("kernel_packets", "kernel_drops", "kernel_ifdrops"):
            if key == "kernel_ifdrops" and key not in capture:
                continue
            value = capture.get(key)
            if (type(value) not in {int, float} or not 0 <= value <= _MAX_ROUTINE_COUNTER
                    or not math.isfinite(value)):
                return  # Invalid stats cannot replace the last real valid sample.
            fields["capture_" + key] = value
        with self._lock:
            self._stats = fields

    def snapshot_reset(self, *, final: bool = False) -> dict[str, Any]:
        with self._lock:
            current = self._monotonic()
            if not final and current - self._window_started < 60:
                return {}
            result: dict[str, Any] = dict(self._stats)
            if self._batches:
                result.update(delivery_success=self._delivered, delivery_success_batches=self._batches)
            if self._stats:
                result["suricata_version"] = "8.0.6"
            self._delivered = self._batches = 0
            self._stats = {}
            self._window_started = current
            return result


class SensorTelemetry:
    def __init__(self, logger: logging.Logger, *, runtime_fields: Mapping[str, Any] | None = None) -> None:
        self.logger = logger
        self.runtime_fields = {key: value for key, value in dict(runtime_fields or {}).items() if key in SAFE_FIELDS}

    def emit(self, event: str, **fields: Any) -> None:
        try:
            payload = {"event": str(event)[:128]}
            for key, value in {**fields, **self.runtime_fields}.items():
                if key == "delivery_success_batches" and (
                        type(value) is not int or not 0 <= value <= _MAX_ROUTINE_COUNTER):
                    continue
                if key in SAFE_FIELDS and _safe(value):
                    payload[key] = value
            self.logger.info(json.dumps(payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")))
        except Exception:
            return


def configure_sensor_logger() -> logging.Logger:
    logger = logging.getLogger("captivportal.device_fingerprint_sensor")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    return logger


def _safe(value: Any) -> bool:
    return value is None or type(value) in {bool, int} or (isinstance(value, float) and math.isfinite(value)) or (isinstance(value, str) and len(value) <= 256)


def resource_snapshot(root: Path = Path("/sys/fs/cgroup/system.slice")) -> dict[str, int | bool]:
    result: dict[str, int | bool] = {}
    for prefix, service in (("sensor", "fingerprint-sensor.service"), ("suricata", "fingerprint-suricata.service")):
        directory = root / service
        if prefix == "suricata":
            result["suricata_process_active"] = directory.exists()
        try:
            memory = int((directory / "memory.current").read_text(encoding="ascii").strip())
            cpu = {
                line.split()[0]: int(line.split()[1])
                for line in (directory / "cpu.stat").read_text(encoding="ascii").splitlines()
                if len(line.split()) == 2
            }
        except (OSError, ValueError):
            continue
        result[f"{prefix}_memory_current"] = memory
        result[f"{prefix}_cpu_usec"] = cpu.get("usage_usec", 0)
    return result
