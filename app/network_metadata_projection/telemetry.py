"""Closed, privacy-safe structured events; never serialize exception objects."""
import json
import logging
from .models import CONFLICTS
from app.network_metadata.success_telemetry import SuccessCounters

EVENTS = frozenset({"projection_conflict", "projection_unavailable", "source_unavailable", "expired_unresolved",
                   "projection_started", "projection_stopped", "batch_committed", "registry_reconciled", "retention_completed",
                   "attribution_retry_counters"})
RETRY_COUNTER_FIELDS = frozenset({
    "attribution_retry_attempted_roles", "attribution_retry_resolved_roles",
    "attribution_retry_terminal_roles", "attribution_retry_still_unavailable_roles",
    "attribution_retry_expired_unresolved", "pending_attribution_count",
    "pending_oldest_age_seconds", "attribution_authority_unavailable_count",
})
MAX_COUNTER = 2**63 - 1
_LEGACY_FIELDS = frozenset({"observation_id", "edge_id", "source_generation_id", "site_id", "reason_code", "count"})
FIELDS = _LEGACY_FIELDS | RETRY_COUNTER_FIELDS


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
        allowed = RETRY_COUNTER_FIELDS if event == "attribution_retry_counters" else _LEGACY_FIELDS
        if event not in EVENTS or not set(values) <= allowed:
            raise ValueError("invalid_projection_telemetry")
        if event == "attribution_retry_counters":
            if not values or any(type(value) is not int or not 0 <= value <= MAX_COUNTER for value in values.values()):
                raise ValueError("invalid_projection_telemetry")
            self.logger.info(json.dumps(dict(event=event, **values), sort_keys=True, separators=(",", ":")))
            return
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
