"""Closed routine telemetry; rejected values are never rendered."""
import json
import logging
import re
from .models import FAULT_CATEGORIES

EVENTS = frozenset({"service_started", "service_stopped", "source_absent", "source_generation_opened",
    "source_generation_closed", "batch_committed", "duplicate_noop", "ingest_fault_aggregate_updated",
    "health_transition", "health_heartbeat", "retention_completed", "capacity_stop", "storage_unavailable"})
REASONS = FAULT_CATEGORIES | frozenset({"source_absent", "source_unavailable", "host_boot_id_unavailable",
    "host_reboot_source_lost", "source_replaced_while_reader_down", "continuity_anchor_mismatch",
    "capture_scope_binding_changed", "source_rotated_live", "capture_health_read_unavailable",
    "capture_interface_unavailable", "raw_parser_unavailable", "suricata_unavailable", "eve_datagram_truncated"})
FIELDS = frozenset({"event", "source_generation_id", "ingest_run_id", "observation_id", "record_start_byte_offset",
    "record_end_byte_offset", "family", "reason_code", "count", "capture_health", "metadata_output_health",
    "metadata_ingest_health", "sqlite_footprint_bytes", "max_db_bytes", "artifact_sha", "artifact_tree",
    "service_name", "process_started_at", "normalizer_version"})


class NetworkMetadataTelemetry:
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger("captivportal.network_metadata")
        self.logger.propagate = False

    def emit(self, event, **fields):
        if event not in EVENTS:
            return
        safe = {"event": event}
        for key, value in fields.items():
            if key not in FIELDS or value is None:
                continue
            if key == "reason_code":
                if type(value) is str and value in REASONS:
                    safe[key] = value
            elif key == "family":
                if type(value) is str and value in {"dns", "tls", "quic"}:
                    safe[key] = value
            elif key.endswith("health"):
                if type(value) is str and value in {"usable", "partial", "stale", "unavailable", "unknown"}:
                    safe[key] = value
            elif key.endswith("_id"):
                if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", value):
                    safe[key] = value
            elif key in {"artifact_sha", "artifact_tree"}:
                if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value):
                    safe[key] = value
            elif key == "service_name":
                if value == "network-metadata.service":
                    safe[key] = value
            elif key == "normalizer_version":
                if value == "network-metadata-normalizer-v1":
                    safe[key] = value
            elif key == "process_started_at":
                if isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3,6}Z", value):
                    safe[key] = value
            elif type(value) is int and value >= 0:
                safe[key] = value
        self.logger.info(json.dumps(safe, sort_keys=True, separators=(",", ":")))


def configure_logger():
    logger = logging.getLogger("captivportal.network_metadata")
    logger.propagate = False
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    return NetworkMetadataTelemetry(logger)
