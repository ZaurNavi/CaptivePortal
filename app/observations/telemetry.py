"""Fail-open operational telemetry adapter for Observation Foundation."""

from __future__ import annotations

import logging
from typing import Any


class ObservationTelemetry:
    def __init__(self, telemetry: Any, logger: logging.Logger):
        self._telemetry = telemetry
        self._logger = logger

    def emit(self, event: str, level: str = "info", **fields: Any) -> bool:
        safe_fields = {
            key: value
            for key, value in fields.items()
            if _safe_field(key, value)
        }
        try:
            if self._telemetry is not None:
                method = getattr(self._telemetry, "safe_emit_system", None)
                if callable(method):
                    emitted = bool(method(
                        event,
                        level=level,
                        component="observation_foundation",
                        **safe_fields,
                    ))
                    if emitted:
                        return True
        except Exception:
            pass
        try:
            numeric = getattr(logging, level.upper(), logging.INFO)
            details = " ".join(f"{key}={value}" for key, value in sorted(safe_fields.items()))
            self._logger.log(numeric, "%s%s", event, f" {details}" if details else "")
            return True
        except Exception:
            return False


def _safe_field(key: str, value: Any) -> bool:
    lowered = key.lower()
    if any(token in lowered for token in ("token", "secret", "password", "cookie", "authorization", "raw")):
        return False
    return value is None or type(value) in {str, int, float, bool}
