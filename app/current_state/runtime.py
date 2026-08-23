"""Fail-open composition and bounded lifecycle for Current State."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from .ap_worker import CurrentApWorker
from .cleanup import CurrentStateCleanup, CurrentStateCleanupWorker
from .client_worker import CurrentClientWorker
from .config import current_state_config_from_settings
from .models import CurrentStateConfig, CurrentStateConfigError
from .read_service import CurrentStateReadService
from .repository import CurrentStateRepository
from .telemetry import CurrentStateTelemetry


class DisabledCurrentStateRuntime:
    state = "disabled"
    config: CurrentStateConfig | None = None
    repository = None
    read_service = None
    client_state = "disabled"
    ap_state = "disabled"

    def start(self) -> bool:
        return False

    def stop(self, timeout_seconds: float | None = None) -> bool:
        return True


class UnavailableCurrentStateRuntime(DisabledCurrentStateRuntime):
    state = "unavailable"
    client_state = "unavailable"
    ap_state = "unavailable"

    def __init__(self, config: CurrentStateConfig | None = None):
        self.config = config


class CurrentStateRuntime:
    def __init__(self, *, config: CurrentStateConfig, provider: Any, telemetry: CurrentStateTelemetry):
        self.config = config
        self.provider = provider
        self.telemetry = telemetry
        self.repository = CurrentStateRepository(config)
        self.read_service = CurrentStateReadService(self.repository)
        self.client_worker = CurrentClientWorker(
            provider=provider, repository=self.repository, config=config, telemetry=telemetry,
        )
        self.ap_worker = CurrentApWorker(
            provider=provider, repository=self.repository, config=config, telemetry=telemetry,
        )
        self.cleanup_worker = CurrentStateCleanupWorker(
            CurrentStateCleanup(self.repository, config), config, telemetry,
        )
        self._state = "disabled"
        self._lock = threading.RLock()

    @property
    def state(self) -> str:
        with self._lock:
            state = self._state
        if state == "active" and (
            self.client_worker.degraded
            or self.ap_worker.degraded
            or self.cleanup_worker.last_error is not None
            or self.cleanup_worker.retention_pressure
        ):
            return "degraded"
        return state

    @property
    def client_state(self) -> str:
        return self.client_worker.state if self._state in {"active", "stopping"} else self._state

    @property
    def ap_state(self) -> str:
        return self.ap_worker.state if self._state in {"active", "stopping"} else self._state

    def start(self) -> bool:
        with self._lock:
            if self._state != "disabled":
                return False
            self._state = "starting"
        try:
            created = self.repository.initialize()
            if not self.client_worker.start() or not self.ap_worker.start() or not self.cleanup_worker.start():
                raise RuntimeError("Current State worker did not start")
        except Exception:
            with self._lock:
                self._state = "unavailable"
            self.telemetry.emit("current_state.storage_error", "error", failure_category="initialization_error")
            self._stop_workers(0.0)
            return False
        with self._lock:
            self._state = "active"
        self.telemetry.emit(
            "current_state.runtime_started",
            created=created,
            site_count=len(self.config.site_ids),
            client_interval_seconds=self.config.client_interval_seconds,
            ap_interval_seconds=self.config.ap_interval_seconds,
        )
        return True

    def stop(self, timeout_seconds: float | None = None) -> bool:
        with self._lock:
            if self._state == "disabled":
                return True
            self._state = "stopping"
        timeout = self.config.shutdown_timeout_seconds if timeout_seconds is None else max(0.0, float(timeout_seconds))
        for worker in (self.client_worker, self.ap_worker, self.cleanup_worker):
            worker.stop_event.set()
        success = self._stop_workers(timeout)
        if success:
            with self._lock:
                self._state = "disabled"
            self.telemetry.emit("current_state.runtime_stopped")
        return success

    def _stop_workers(self, timeout: float) -> bool:
        deadline = time.monotonic() + max(0.0, timeout)
        success = True
        for worker in (self.client_worker, self.ap_worker, self.cleanup_worker):
            try:
                success = bool(worker.stop(max(0.0, deadline - time.monotonic()))) and success
            except Exception:
                success = False
        return success


def create_current_state_runtime(settings: dict[str, Any], provider: Any, telemetry: Any, *, logger: logging.Logger | None = None):
    actual_logger = logger or logging.getLogger("current_state")
    adapter = CurrentStateTelemetry(telemetry, actual_logger)
    try:
        config = current_state_config_from_settings(settings)
    except (CurrentStateConfigError, TypeError, ValueError, OverflowError):
        adapter.emit("current_state.storage_error", "error", failure_category="configuration_error")
        return UnavailableCurrentStateRuntime()
    if not config.enabled:
        return DisabledCurrentStateRuntime()
    try:
        return CurrentStateRuntime(config=config, provider=provider, telemetry=adapter)
    except Exception:
        adapter.emit("current_state.storage_error", "error", failure_category="construction_error")
        return UnavailableCurrentStateRuntime(config)
