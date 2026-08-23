"""Secret-safe operational telemetry for Current State."""

from __future__ import annotations

import logging
from typing import Any


_ALLOWED_FIELDS = frozenset({
    "site_id",
    "cycle_id",
    "kind",
    "duration_ms",
    "complete",
    "items_seen",
    "items_stored",
    "items_skipped",
    "page_count",
    "error_count",
    "warning_count",
    "duplicate_count",
    "unknown_status_count",
    "failure_category",
    "deleted_cycles",
    "deleted_client_rows",
    "deleted_ap_rows",
    "duration_exhausted",
    "interrupted",
    "remaining_client_rows",
    "created",
    "site_count",
    "client_interval_seconds",
    "ap_interval_seconds",
})


class CurrentStateTelemetry:
    def __init__(self, telemetry: Any, logger: logging.Logger):
        self._telemetry = telemetry
        self._logger = logger

    def emit(self, event: str, level: str = "info", **fields: Any) -> bool:
        safe = {key: value for key, value in fields.items() if _safe(key, value)}
        try:
            method = getattr(self._telemetry, "safe_emit_system", None)
            if callable(method) and method(
                event,
                level=level,
                component="current_state",
                **safe,
            ):
                return True
        except Exception:
            pass
        try:
            details = " ".join(f"{key}={value}" for key, value in sorted(safe.items()))
            self._logger.log(
                getattr(logging, level.upper(), logging.INFO),
                "%s%s",
                event,
                f" {details}" if details else "",
            )
            return True
        except Exception:
            return False


def _safe(key: str, value: Any) -> bool:
    if key not in _ALLOWED_FIELDS:
        return False
    lowered = key.lower()
    if any(word in lowered for word in ("token", "secret", "password", "cookie", "authorization", "raw", "ssid")):
        return False
    return value is None or type(value) in {str, int, float, bool}
