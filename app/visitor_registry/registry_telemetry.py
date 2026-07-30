"""Secret-safe operational telemetry for Visitor Device Registry."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

from app.auth_telemetry import get_auth_telemetry
from app.logger import logger as application_logger


class VisitorRegistryTelemetry:
    def __init__(
        self,
        telemetry_provider: Callable[[], Any] = get_auth_telemetry,
        logger: logging.Logger = application_logger,
    ):
        self._telemetry_provider = telemetry_provider
        self._logger = logger
        self._lock = threading.RLock()
        self._emitted_once: set[tuple[str, str]] = set()

    def emit(
        self,
        event: str,
        level: str = "info",
        **fields: Any,
    ) -> bool:
        safe_fields = {
            key: value
            for key, value in fields.items()
            if key not in {
                "raw_controller_snapshot",
                "auth_context",
                "client_json",
                "raw_controller_snapshot_json",
            }
        }
        try:
            telemetry = self._telemetry_provider()
            emitted = bool(
                telemetry.safe_emit_system(
                    event,
                    level,
                    component="visitor_registry",
                    **safe_fields,
                )
            )
        except Exception:
            emitted = False
        if not emitted and level in {"error", "critical"}:
            try:
                self._logger.log(
                    getattr(logging, level.upper(), logging.ERROR),
                    "%s component=visitor_registry",
                    event,
                )
            except Exception:
                pass
        return emitted

    def emit_once(
        self,
        event: str,
        level: str = "warning",
        *,
        key: str = "",
        **fields: Any,
    ) -> bool:
        marker = (event, key)
        with self._lock:
            if marker in self._emitted_once:
                return False
            self._emitted_once.add(marker)
        return self.emit(event, level, **fields)

    def clear_rate_limits(self) -> None:
        with self._lock:
            self._emitted_once.clear()
