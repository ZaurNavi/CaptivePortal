"""Fail-open, local-file authorization telemetry service."""

import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler
from typing import Any, Optional

from .formatter import JsonLineFormatter
from .schemas import build_record


LOGGER_NAME = "captive_portal.auth_telemetry"
_HANDLER_MARKER = "_captive_portal_auth_telemetry"
_CONFIG_LOCK = threading.RLock()
_SYSTEM_LOGGER = logging.getLogger("captivportal")


class _TelemetryRotatingFileHandler(RotatingFileHandler):
    def _open(self):
        stream = super()._open()
        if os.name == "posix":
            try:
                os.chmod(self.baseFilename, 0o640)
            except OSError:
                pass
        return stream

    def handleError(self, record: logging.LogRecord) -> None:
        """Propagate handler failures to the fail-open service boundary."""
        error = sys.exc_info()[1]
        if error is not None:
            raise error
        raise OSError("Unknown auth telemetry handler failure")


class AuthorizationTelemetry:
    def __init__(
        self,
        *,
        enabled: bool,
        log_path: str,
        level: str = "INFO",
        schema_version: int = 1,
        rotation_max_bytes: int = 52_428_800,
        rotation_backup_count: int = 10,
    ):
        self.enabled = bool(enabled)
        self.schema_version = int(schema_version)
        self._logger = logging.getLogger(LOGGER_NAME)
        self._logger.propagate = False
        self._emit_lock = threading.RLock()
        self._once: set[tuple[str, str]] = set()
        self._reported_failures: set[str] = set()
        self.available = False

        numeric_level = getattr(
            logging,
            str(level).upper(),
            logging.INFO,
        )
        self._logger.setLevel(numeric_level)

        with _CONFIG_LOCK:
            existing = [
                handler
                for handler in self._logger.handlers
                if getattr(handler, _HANDLER_MARKER, False)
            ]
            for handler in existing:
                self._logger.removeHandler(handler)
                try:
                    handler.close()
                except Exception:
                    pass

            if not self.enabled:
                return

            try:
                handler = _TelemetryRotatingFileHandler(
                    filename=log_path,
                    maxBytes=max(0, int(rotation_max_bytes)),
                    backupCount=max(0, int(rotation_backup_count)),
                    encoding="utf-8",
                )
                setattr(handler, _HANDLER_MARKER, True)
                handler.setLevel(numeric_level)
                handler.setFormatter(JsonLineFormatter())
                self._logger.addHandler(handler)
                self.available = True
            except Exception as exc:
                self.available = False
                self._report_failure_once("initialization", exc)

    @classmethod
    def from_settings(cls, settings: dict[str, Any]):
        return cls(
            enabled=settings.get("auth_telemetry_enabled", False),
            log_path=settings.get("auth_telemetry_log_path", ""),
            level=settings.get("auth_telemetry_level", "INFO"),
            schema_version=settings.get(
                "auth_telemetry_schema_version",
                1,
            ),
            rotation_max_bytes=(
                settings.get(
                    "auth_telemetry_rotation_max_bytes",
                    52_428_800,
                )
            ),
            rotation_backup_count=(
                settings.get(
                    "auth_telemetry_rotation_backup_count",
                    10,
                )
            ),
        )

    @property
    def logger(self) -> logging.Logger:
        return self._logger

    def safe_emit(
        self,
        event: str,
        session_id: str,
        level: str = "info",
        **fields: Any,
    ) -> bool:
        if not self.enabled or not self.available:
            return False
        try:
            numeric_level = getattr(
                logging,
                str(level).upper(),
                logging.INFO,
            )
            if not self._logger.isEnabledFor(numeric_level):
                return False
            record = build_record(
                event=event,
                session_id=session_id,
                level=logging.getLevelName(numeric_level).lower(),
                schema_version=self.schema_version,
                fields=fields,
            )
            with self._emit_lock:
                self._logger.log(numeric_level, record)
            return True
        except Exception as exc:
            self._report_failure_once("write", exc)
            return False

    def safe_emit_once(
        self,
        event: str,
        session_id: str,
        level: str = "info",
        **fields: Any,
    ) -> bool:
        key = (event, session_id)
        with self._emit_lock:
            if key in self._once:
                return False
            emitted = self.safe_emit(
                event,
                session_id,
                level,
                **fields,
            )
            if emitted:
                self._once.add(key)
            return emitted

    def _report_failure_once(
        self,
        stage: str,
        error: Exception,
    ) -> None:
        with self._emit_lock:
            if stage in self._reported_failures:
                return
            self._reported_failures.add(stage)
        try:
            _SYSTEM_LOGGER.error(
                "auth_telemetry.%s_failed error_type=%s error=%s",
                stage,
                type(error).__name__,
                error,
            )
        except Exception:
            pass


_service: Optional[AuthorizationTelemetry] = None
_SERVICE_LOCK = threading.RLock()


def configure_auth_telemetry(
    settings: dict[str, Any],
) -> AuthorizationTelemetry:
    global _service
    with _SERVICE_LOCK:
        _service = AuthorizationTelemetry.from_settings(settings)
        return _service


def get_auth_telemetry() -> AuthorizationTelemetry:
    global _service
    with _SERVICE_LOCK:
        if _service is None:
            _service = AuthorizationTelemetry(
                enabled=False,
                log_path="",
            )
        return _service
