"""Fail-open operational telemetry for Visit Lifecycle."""

from __future__ import annotations

import logging
from typing import Any

from app.auth_telemetry import get_auth_telemetry


class VisitTelemetry:
    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def emit(self, event: str, level: str = "info", **fields: Any) -> bool:
        safe_fields = {
            key: value
            for key, value in fields.items()
            if _safe_field(key, value)
        }
        try:
            telemetry = get_auth_telemetry()
            method = getattr(telemetry, "safe_emit_system", None)
            if callable(method) and method(
                event,
                level=level,
                component="visit_lifecycle",
                **safe_fields,
            ):
                return True
        except Exception:
            pass
        try:
            numeric = getattr(logging, str(level).upper(), logging.INFO)
            details = " ".join(
                f"{key}={value}" for key, value in sorted(safe_fields.items())
            )
            self._logger.log(
                numeric,
                "%s%s",
                event,
                f" {details}" if details else "",
            )
            return True
        except Exception:
            return False


def _safe_field(key: str, value: Any) -> bool:
    lowered = key.lower()
    if any(token in lowered for token in (
        "token", "secret", "password", "cookie", "authorization", "raw",
    )):
        return False
    return value is None or type(value) in {str, int, float, bool}
