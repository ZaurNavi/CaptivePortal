"""Safe-field-only operational telemetry."""

from __future__ import annotations

import json
import logging
import math
from typing import Any, Mapping

SAFE_FIELDS = frozenset({
    "request_id", "producer_id", "capture_source_id", "site_id", "source_kind",
    "http_status", "error_category", "received", "inserted", "duplicate_noop",
    "deleted_evidence", "deleted_source_health", "runtime_state", "reason",
    "schema_version", "duration_ms", "artifact_sha", "artifact_tree",
    "service_name", "process_started_at", "active_ingest_count",
})
_RUNTIME_FIELDS = frozenset({"artifact_sha", "artifact_tree", "service_name", "process_started_at"})


def configure_device_fingerprint_logger() -> logging.Logger:
    logger = logging.getLogger("captivportal.device_fingerprint")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for handler in tuple(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    return logger


class DeviceFingerprintTelemetry:
    def __init__(self, logger: logging.Logger, *, runtime_fields: Mapping[str, Any] | None = None) -> None:
        self._logger = logger
        self._runtime_fields = {
            key: normalized
            for key, value in dict(runtime_fields or {}).items()
            if key in _RUNTIME_FIELDS
            and (normalized := _safe_value(value)) is not _OMIT
        }

    def emit(self, event: str, **fields: Any) -> None:
        try:
            payload: dict[str, Any] = {"event": str(event)[:128]}
            for key, value in fields.items():
                normalized = _safe_value(value)
                if key in SAFE_FIELDS and normalized is not _OMIT:
                    payload[key] = normalized
            payload.update(self._runtime_fields)
            self._logger.info("%s", json.dumps(payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")))
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
