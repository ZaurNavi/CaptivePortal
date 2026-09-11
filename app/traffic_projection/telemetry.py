"""Strict safe-field telemetry for projection operations."""

from __future__ import annotations

import logging
import json
import math
from typing import Any, Mapping


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
    "reconcile_sweep_from_utc", "reconcile_sweep_source_head_utc",
    "reconcile_cursor_started_at", "reconcile_cursor_cycle_id",
    "source_count", "projection_count", "count_delta",
    "artifact_sha", "artifact_tree", "service_name", "process_started_at",
})

_RUNTIME_FIELDS = frozenset({
    "artifact_sha", "artifact_tree", "service_name", "process_started_at",
})
_HANDLER_MARKER = "_captivportal_traffic_projection_owned"


def configure_traffic_projection_logger() -> logging.Logger:
    logger = logging.getLogger("captivportal.traffic_projection")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for handler in tuple(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(message)s"))
    setattr(handler, _HANDLER_MARKER, True)
    logger.addHandler(handler)
    return logger


class TrafficProjectionTelemetry:
    def __init__(
        self,
        logger: logging.Logger,
        *,
        runtime_fields: Mapping[str, Any] | None = None,
    ):
        self._logger = logger
        self._runtime_fields = {
            key: normalized
            for key, value in dict(runtime_fields or {}).items()
            if key in _RUNTIME_FIELDS
            and (normalized := _safe_value(value)) is not _OMIT
        }

    def emit(self, event: str, **fields: Any) -> None:
        try:
            payload: dict[str, Any] = {"event": str(event)[:256]}
            for key, value in fields.items():
                normalized = _safe_value(value)
                if key in SAFE_FIELDS and normalized is not _OMIT:
                    payload[key] = normalized
            payload.update(self._runtime_fields)
            line = json.dumps(
                payload,
                ensure_ascii=True,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            self._logger.info("%s", line)
        except Exception:
            return


_OMIT = object()


def _safe_value(value: Any) -> Any:
    if value is None or type(value) in {bool, int}:
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else _OMIT
    if isinstance(value, str):
        return value[:256]
    return _OMIT
