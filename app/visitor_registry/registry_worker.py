"""Lifecycle-owned fail-open worker for Visitor Device Registry."""

from __future__ import annotations

import sqlite3
import threading
import time
from typing import Any

from .registry_config import registry_config_from_settings
from .registry_models import (
    RegistryConfigError,
    RegistrySchemaError,
)
from .registry_reader import VisitorRegistryReader
from .registry_repository import VisitorRegistryRepository
from .registry_service import VisitorRegistryService
from .registry_telemetry import VisitorRegistryTelemetry


_SQLITE_BUSY = 5
_SQLITE_LOCKED = 6
_SQLITE_READONLY = 8
_SQLITE_IOERR = 10
_SQLITE_CORRUPT = 11
_SQLITE_FULL = 13
_SQLITE_CANTOPEN = 14
_SQLITE_NOTADB = 26

_SQLITE_LOCKED_CODES = frozenset({_SQLITE_BUSY, _SQLITE_LOCKED})
_SQLITE_UNAVAILABLE_CODES = frozenset({
    _SQLITE_CORRUPT,
    _SQLITE_NOTADB,
    _SQLITE_READONLY,
    _SQLITE_CANTOPEN,
})
_SQLITE_CORRUPTION_CODES = frozenset({
    _SQLITE_CORRUPT,
    _SQLITE_NOTADB,
})
_SQLITE_MESSAGE_CATEGORIES = (
    ("database is locked", "locked"),
    ("database table is locked", "locked"),
    ("database disk image is malformed", "unavailable"),
    ("file is not a database", "unavailable"),
    ("attempt to write a readonly database", "unavailable"),
    ("unable to open database file", "unavailable"),
    ("disk i/o error", "io_error"),
)
_SQLITE_CORRUPTION_MESSAGES = (
    "database disk image is malformed",
    "file is not a database",
)


class DisabledVisitorRegistry:
    enabled = False
    available = False
    running = False

    def start(self) -> bool:
        return False

    def run_once(self) -> None:
        return None

    def stop(
        self,
        timeout: float | None = None,
        *,
        final_scan: bool = True,
    ) -> None:
        return None


class UnavailableVisitorRegistry(DisabledVisitorRegistry):
    enabled = True


DISABLED_VISITOR_REGISTRY = DisabledVisitorRegistry()


class VisitorRegistryWorker:
    enabled = True

    def __init__(
        self,
        *,
        repository: VisitorRegistryRepository,
        service: VisitorRegistryService,
        reader: VisitorRegistryReader,
        telemetry: VisitorRegistryTelemetry,
    ):
        self.repository = repository
        self.service = service
        self.reader = reader
        self.telemetry = telemetry
        self.config = repository.config
        self.available = True
        self._stop_event = threading.Event()
        self._scan_lock = threading.Lock()
        self._stop_lock = threading.Lock()
        self._state_lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._backfill_started = False
        self._full_audit_completed = False
        self._shutdown_timeout_emitted = False
        self._stopped_emitted = False
        self._stop_completed = False

    @property
    def running(self) -> bool:
        with self._state_lock:
            return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        with self._state_lock:
            if not self.available:
                return False
            if self._thread is not None and self._thread.is_alive():
                return False
            self._stop_event.clear()
            self._full_audit_completed = False
            self._shutdown_timeout_emitted = False
            self._stopped_emitted = False
            self._stop_completed = False
            try:
                self._change_state(
                    "initializing",
                    "full_audit_pending",
                )
            except Exception as exc:
                self._handle_error(exc)
                return False
            self._thread = threading.Thread(
                target=self._run,
                name="visitor_registry_worker",
                daemon=True,
            )
            self._thread.start()
        self.telemetry.emit(
            "visitor_registry_started",
            "info",
            scan_interval_seconds=self.config.scan_interval_seconds,
        )
        return True

    def run_once(self) -> None:
        with self._scan_lock:
            self._run_once_locked(
                should_stop=self._stop_event.is_set,
            )

    def _run_once_locked(self, *, should_stop) -> None:
        if not self.available:
            return
        try:
            if not self._full_audit_completed:
                if not self._change_state_if_running(
                    "initializing",
                    "full_audit_pending",
                    should_stop,
                ):
                    return
                if should_stop():
                    return
                self.repository.run_full_audit()
                self._full_audit_completed = True
                if should_stop():
                    return
                self.telemetry.emit(
                    "visitor_registry_integrity_audit_completed",
                    "info",
                )
            if should_stop():
                return
            backfill = not self.repository.initial_backfill_completed()
            if should_stop():
                return
            if backfill:
                if not self._backfill_started:
                    self._backfill_started = True
                    self.telemetry.emit(
                        "visitor_registry_backfill_started",
                        "info",
                    )
                if should_stop():
                    return
                if not self._change_state_if_running(
                    "backfilling",
                    None,
                    should_stop,
                ):
                    return
            if should_stop():
                return
            result = self.reader.scan(should_stop=should_stop)
            if result.reason == "shutdown" or should_stop():
                return
            if result.complete:
                now = self.service.now_iso()
                if backfill:
                    if should_stop():
                        return
                    self.repository.mark_backfill_completed(now)
                    if should_stop():
                        return
                    self.telemetry.emit(
                        "visitor_registry_backfill_completed",
                        "info",
                    )
                if should_stop():
                    return
                self.repository.mark_successful_scan(now)
                if should_stop():
                    return
                previous = self._current_state()
                if should_stop():
                    return
                if not self._change_state_if_running(
                    "ready",
                    None,
                    should_stop,
                ):
                    return
                if previous == "degraded":
                    self.telemetry.clear_rate_limits()
                    self.telemetry.emit(
                        "visitor_registry_recovered",
                        "info",
                    )
            else:
                if should_stop():
                    return
                if not self._change_state_if_running(
                    "degraded",
                    result.reason or "scan_incomplete",
                    should_stop,
                ):
                    return
                self.telemetry.emit_once(
                    "visitor_registry_scan_incomplete",
                    key=result.reason or "scan_incomplete",
                    reason=result.reason or "scan_incomplete",
                )
        except Exception as exc:
            with self._state_lock:
                if should_stop():
                    return
                self._handle_error(exc)

    def stop(
        self,
        timeout: float | None = None,
        *,
        final_scan: bool = True,
    ) -> None:
        with self._stop_lock:
            if self._stop_completed:
                return
            completed = self._stop_once(
                timeout,
                final_scan=final_scan,
            )
            if completed:
                self._stop_completed = True

    def _stop_once(
        self,
        timeout: float | None,
        *,
        final_scan: bool,
    ) -> bool:
        bounded = (
            self.config.shutdown_timeout_seconds
            if timeout is None
            else max(0.0, float(timeout))
        )
        deadline = time.monotonic() + bounded
        with self._state_lock:
            self._stop_event.set()
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(max(0.0, deadline - time.monotonic()))

        thread_alive = bool(thread is not None and thread.is_alive())
        final_scan_attempted = not final_scan or not self.available
        if final_scan and self.available and not thread_alive:
            remaining = max(0.0, deadline - time.monotonic())
            acquired = self._scan_lock.acquire(timeout=remaining)
            if acquired:
                try:
                    final_scan_attempted = True
                    self._run_once_locked(
                        should_stop=lambda: time.monotonic() >= deadline,
                    )
                finally:
                    self._scan_lock.release()

        deadline_exceeded = time.monotonic() > deadline
        timed_out = (
            thread_alive
            or not final_scan_attempted
            or deadline_exceeded
        )
        if timed_out:
            self._emit_shutdown_timeout_once(bounded)
        if self.available:
            try:
                with self._state_lock:
                    self._change_state("stopping", None)
            except Exception:
                pass
        with self._state_lock:
            if self._thread is thread and (
                thread is None or not thread.is_alive()
            ):
                self._thread = None
            thread_stopped = (
                self._thread is None
                or not self._thread.is_alive()
            )
        completed = thread_stopped and final_scan_attempted
        if completed:
            self._emit_stopped_once()
        return completed

    def _run(self) -> None:
        while not self._stop_event.is_set() and self.available:
            self.run_once()
            if self._stop_event.wait(
                self.config.scan_interval_seconds
            ):
                break

    def _change_state(
        self,
        state: str,
        reason: str | None,
    ) -> None:
        changed = self.repository.set_state(
            state,
            reason,
            self.service.now_iso(),
        )
        if changed:
            self.telemetry.emit(
                "visitor_registry_state_changed",
                "info" if state in {"ready", "stopping"} else "warning",
                registry_state=state,
                state_reason=reason,
            )

    def _change_state_if_running(
        self,
        state: str,
        reason: str | None,
        should_stop,
    ) -> bool:
        with self._state_lock:
            if should_stop():
                return False
            self._change_state(state, reason)
            return True

    def _current_state(self) -> str | None:
        try:
            return self.repository.get_status(True).registry_state
        except Exception:
            return None

    def _handle_error(self, exc: Exception) -> None:
        category = _sqlite_category(exc)
        if category == "io_error":
            try:
                self.repository.validate_runtime_health()
            except Exception:
                category = "unavailable"
            else:
                category = "degraded"
        if (
            isinstance(
                exc,
                (
                    RegistryConfigError,
                    RegistrySchemaError,
                    PermissionError,
                ),
            )
            or category == "unavailable"
        ):
            self.available = False
            self._stop_event.set()
            try:
                self._change_state(
                    "unavailable",
                    type(exc).__name__,
                )
            except Exception:
                pass
            if isinstance(exc, RegistrySchemaError):
                diagnostic_event = "visitor_registry_schema_invalid"
            elif _is_sqlite_corruption(exc):
                diagnostic_event = "visitor_registry_corrupt_database"
            else:
                diagnostic_event = "visitor_registry_database_error"
            self.telemetry.emit_once(
                diagnostic_event,
                "critical",
                key=type(exc).__name__,
                exception_type=type(exc).__name__,
            )
            self.telemetry.emit(
                "visitor_registry_unavailable",
                "critical",
                exception_type=type(exc).__name__,
            )
            return

        try:
            self._change_state("degraded", type(exc).__name__)
        except Exception:
            pass
        event = (
            "visitor_registry_database_locked"
            if category == "locked"
            else "visitor_registry_database_error"
        )
        self.telemetry.emit_once(
            event,
            "warning",
            key=type(exc).__name__,
            exception_type=type(exc).__name__,
        )

    def _emit_shutdown_timeout_once(self, timeout: float) -> None:
        with self._state_lock:
            if self._shutdown_timeout_emitted:
                return
            self._shutdown_timeout_emitted = True
        self.telemetry.emit(
            "visitor_registry_shutdown_timeout",
            "error",
            timeout_seconds=timeout,
        )

    def _emit_stopped_once(self) -> None:
        with self._state_lock:
            if self._stopped_emitted:
                return
            self._stopped_emitted = True
        self.telemetry.emit("visitor_registry_stopped", "info")


def create_visitor_registry(
    settings: dict[str, Any],
    *,
    telemetry: VisitorRegistryTelemetry | None = None,
):
    """Create and validate Registry without ever failing the portal."""
    operational = telemetry or VisitorRegistryTelemetry()
    try:
        config = registry_config_from_settings(settings)
    except RegistryConfigError as exc:
        operational.emit(
            "visitor_registry_unavailable",
            "critical",
            stage="configuration",
            exception_type=type(exc).__name__,
        )
        return UnavailableVisitorRegistry()
    if not config.enabled:
        return DISABLED_VISITOR_REGISTRY

    service = VisitorRegistryService(config.timezone_name)
    repository = VisitorRegistryRepository(config)
    try:
        migrated = repository.initialize(service.now_iso())
    except Exception as exc:
        if isinstance(exc, RegistrySchemaError):
            diagnostic_event = "visitor_registry_schema_invalid"
        elif _is_sqlite_corruption(exc):
            diagnostic_event = "visitor_registry_corrupt_database"
        else:
            diagnostic_event = "visitor_registry_database_error"
        operational.emit(
            diagnostic_event,
            "critical",
            stage="initialization",
            exception_type=type(exc).__name__,
        )
        operational.emit(
            "visitor_registry_unavailable",
            "critical",
            stage="initialization",
            exception_type=type(exc).__name__,
        )
        return UnavailableVisitorRegistry()
    if migrated:
        operational.emit(
            "visitor_registry_migration_completed",
            "info",
            schema_version=1,
        )
    reader = VisitorRegistryReader(
        config=config,
        repository=repository,
        service=service,
        telemetry=operational,
    )
    return VisitorRegistryWorker(
        repository=repository,
        service=service,
        reader=reader,
        telemetry=operational,
    )


def _sqlite_category(exc: Exception) -> str:
    if not isinstance(exc, sqlite3.Error):
        return "degraded"
    primary = _sqlite_primary_code(exc)
    if primary is not None:
        if primary in _SQLITE_LOCKED_CODES:
            return "locked"
        if primary in _SQLITE_UNAVAILABLE_CODES:
            return "unavailable"
        if primary == _SQLITE_IOERR:
            return "io_error"
        if primary == _SQLITE_FULL:
            return "degraded"
        return "degraded"
    return _sqlite_message_category(exc) or "degraded"


def _sqlite_primary_code(exc: Exception) -> int | None:
    if not isinstance(exc, sqlite3.Error):
        return None
    code = getattr(exc, "sqlite_errorcode", None)
    return (code & 0xFF) if isinstance(code, int) else None


def _sqlite_message_category(exc: Exception) -> str | None:
    if not isinstance(exc, sqlite3.Error):
        return None
    message = str(exc).strip().lower()
    for fragment, category in _SQLITE_MESSAGE_CATEGORIES:
        if fragment in message:
            return category
    return None


def _is_sqlite_corruption(exc: Exception) -> bool:
    primary = _sqlite_primary_code(exc)
    if primary is not None:
        return primary in _SQLITE_CORRUPTION_CODES
    if not isinstance(exc, sqlite3.Error):
        return False
    message = str(exc).strip().lower()
    return any(
        fragment in message
        for fragment in _SQLITE_CORRUPTION_MESSAGES
    )
