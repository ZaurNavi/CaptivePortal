"""Secret-safe operational telemetry for Visitor Snapshot."""

from __future__ import annotations

import logging
import re
import threading
from collections.abc import Callable
from typing import Any

from app.auth_telemetry import get_auth_telemetry
from app.logger import logger as application_logger


COMPONENT = "visitor_snapshot"
CRITICAL_FALLBACK_EVENTS = frozenset({
    "visitor_snapshot_collector_unavailable",
    "visitor_snapshot_write_failed",
    "visitor_snapshot_invalid_configuration",
    "visitor_snapshot_start_failed",
    "visitor_snapshot_stop_failed",
})
_SAFE_FALLBACK_FIELDS = frozenset({
    "error_category",
    "exception_type",
    "outcome",
    "stage",
})


class VisitorSnapshotTelemetry:
    def __init__(
        self,
        telemetry_provider: Callable[[], Any] = get_auth_telemetry,
        logger: logging.Logger = application_logger,
    ):
        self._telemetry_provider = telemetry_provider
        self._logger = logger
        self._lock = threading.RLock()
        self._fallback_emitted: set[str] = set()

    def emit(
        self,
        event: str,
        level: str = "info",
        **fields: Any,
    ) -> bool:
        emitted = False
        try:
            telemetry = self._telemetry_provider()
            emitted = bool(
                telemetry.safe_emit_system(
                    event,
                    level,
                    component=COMPONENT,
                    **fields,
                )
            )
        except Exception:
            emitted = False
        if not emitted and event in CRITICAL_FALLBACK_EVENTS:
            self._fallback_once(event, level, fields)
        return emitted

    def _fallback_once(
        self,
        event: str,
        level: str,
        fields: dict[str, Any],
    ) -> None:
        with self._lock:
            if event in self._fallback_emitted:
                return
            self._fallback_emitted.add(event)
        safe_fields = []
        for key in sorted(_SAFE_FALLBACK_FIELDS):
            value = fields.get(key)
            if value is None:
                continue
            safe_fields.append(
                f"{key}={_safe_scalar(value)}"
            )
        suffix = " " + " ".join(safe_fields) if safe_fields else ""
        numeric_level = getattr(
            logging,
            str(level).upper(),
            logging.ERROR,
        )
        try:
            self._logger.log(
                numeric_level,
                "%s component=%s%s",
                event,
                COMPONENT,
                suffix,
            )
        except Exception:
            pass


def _safe_scalar(value: Any) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", str(value))
    text = re.sub(r"\s+", "_", text).strip("_")
    return text[:128] or "unknown"
