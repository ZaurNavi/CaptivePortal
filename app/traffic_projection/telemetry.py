"""Strict safe-field telemetry for projection operations."""

from __future__ import annotations

import logging
from typing import Any


SAFE_FIELDS = frozenset({
    "projection_version", "site_id", "status", "build_state",
    "projection_revision", "source_head_utc", "projection_head_utc",
    "head_lag_seconds", "last_incremental_progress_at",
    "reconcile_sweep_started_at", "last_full_reconcile_completed_at",
    "last_full_reconcile_source_head_utc", "last_deep_audit_at",
    "backlog_cycle_count", "cycles_examined", "cycles_projected",
    "cycles_replayed", "cycles_corrected", "cycles_invalidated",
    "deep_audit_checked", "rebuild_progress", "duration_ms", "db_bytes",
    "wal_bytes", "error_category",
})


class TrafficProjectionTelemetry:
    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def emit(self, event: str, **fields: Any) -> None:
        safe = {key: value for key, value in fields.items() if key in SAFE_FIELDS}
        self._logger.info("%s", event, extra={"event": event, **safe})
