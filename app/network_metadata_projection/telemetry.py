"""Closed, privacy-safe structured events; never serialize exception objects."""
import json
import logging
from .models import CONFLICTS

EVENTS = frozenset({"projection_conflict", "projection_unavailable", "source_unavailable", "expired_unresolved",
                   "projection_started", "projection_stopped", "batch_committed", "registry_reconciled", "retention_completed"})
FIELDS = frozenset({"observation_id", "edge_id", "source_generation_id", "site_id", "reason_code", "count"})


class ProjectionTelemetry:
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger("network_metadata_projection")

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
        self.logger.info(json.dumps(dict(event=event, **values), sort_keys=True, separators=(",", ":")))
