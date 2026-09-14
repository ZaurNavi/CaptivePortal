"""Sanitized sensor operational telemetry."""

from __future__ import annotations

import json
import logging
import math
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
    "delivery_permanent_reject", "stale_spool_event_dropped", "artifact_sha",
    "artifact_tree", "service_name", "process_started_at", "suricata_version",
    "capture_kernel_packets", "capture_kernel_drops", "capture_kernel_ifdrops",
    "sensor_cpu_usec", "sensor_memory_current", "suricata_cpu_usec",
    "suricata_memory_current", "suricata_process_active",
})


class SensorTelemetry:
    def __init__(self, logger: logging.Logger, *, runtime_fields: Mapping[str, Any] | None = None) -> None:
        self.logger = logger
        self.runtime_fields = {key: value for key, value in dict(runtime_fields or {}).items() if key in SAFE_FIELDS}

    def emit(self, event: str, **fields: Any) -> None:
        try:
            payload = {"event": str(event)[:128]}
            for key, value in {**fields, **self.runtime_fields}.items():
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
