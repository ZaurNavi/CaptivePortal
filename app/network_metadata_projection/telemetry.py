"""Closed, privacy-safe structured events; never serialize exception objects."""
import json
import logging
from .models import CONFLICTS
from app.network_metadata.success_telemetry import SuccessCounters

EVENTS = frozenset({"projection_conflict", "projection_unavailable", "source_unavailable", "expired_unresolved",
                   "projection_started", "projection_stopped", "batch_committed", "registry_reconciled", "retention_completed"})
FIELDS = frozenset({"observation_id", "edge_id", "source_generation_id", "site_id", "reason_code", "count"})


class ProjectionTelemetry:
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger("network_metadata_projection")
        self._success = None

    def enable_aggregation(self, *, monotonic):
        if self._success is None:
            self._success = SuccessCounters(self._publish_summary, monotonic=monotonic)

    def _publish_summary(self, summary):
        self.logger.info(json.dumps(summary, sort_keys=True, separators=(",", ":")))

    def observe_success(self, **counts):
        if self._success is not None:
            self._success.flush_due()
            self._success.observe(**counts)

    def flush_due(self):
        if self._success is not None:
            self._success.flush_due()

    def emit(self, event, **values):
        if event not in EVENTS or not set(values) <= FIELDS:
            raise ValueError("invalid_projection_telemetry")
        # Closed token grammar: never interpolate an upstream error/value.
        from app.network_metadata.validation import canonical_uuid, digest, integer
        from app.device_fingerprint.validation import validate_site_id, validate_machine_id
        for key, value in values.items():
            if key in {"observation_id", "source_generation_id"}:
                canonical_uuid(value)
            elif key == "edge_id":
                digest(value)
            elif key == "site_id":
                validate_site_id(value)
            elif key == "count":
                integer(value)
            else:
                validate_machine_id(value)
        if self._success is not None:
            self._success.flush_due()
            if event == "batch_committed":
                counts = dict(batch_count=1, suppressed_event_count=1)
                if "count" in values:
                    counts["record_count"] = values["count"]
                self._success.observe(**counts)
                return
        self.logger.info(json.dumps(dict(event=event, **values), sort_keys=True, separators=(",", ":")))
