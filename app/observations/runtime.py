"""Fail-open runtime composition for Observation Foundation workers."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from .ap_worker import APObservationWorker
from .cleanup import ObservationCleanup, ObservationCleanupWorker
from .client_worker import ClientObservationWorker
from .config import observation_config_from_settings
from .models import ObservationConfig, ObservationConfigError
from .repository import ObservationRepository
from .telemetry import ObservationTelemetry


class DisabledObservationFoundation:
    state = "disabled"
    config: ObservationConfig | None = None

    def start(self) -> bool:
        return False

    def stop(self, timeout_seconds: float | None = None) -> bool:
        return True


class UnavailableObservationFoundation:
    state = "unavailable"

    def __init__(self, *, config: ObservationConfig | None = None):
        self.config = config

    def start(self) -> bool:
        return False

    def stop(self, timeout_seconds: float | None = None) -> bool:
        return True


class ObservationFoundationRuntime:
    def __init__(
        self,
        *,
        config: ObservationConfig,
        provider: Any,
        telemetry: ObservationTelemetry,
        logger: logging.Logger,
    ):
        self.config = config
        self.provider = provider
        self.telemetry = telemetry
        self.repository = ObservationRepository(config)
        self.client_worker = ClientObservationWorker(
            provider=provider,
            repository=self.repository,
            config=config,
            logger=logger,
        )
        self.ap_worker = APObservationWorker(
            provider=provider,
            repository=self.repository,
            config=config,
            telemetry=telemetry,
        )
        self.cleanup_worker = ObservationCleanupWorker(
            ObservationCleanup(self.repository, config),
            config,
            telemetry=telemetry,
        )
        self._state = "disabled"
        self._lock = threading.RLock()

    @property
    def state(self) -> str:
        with self._lock:
            current = self._state
        if current == "active" and (
            self.client_worker.degraded
            or self.ap_worker.degraded
            or self.cleanup_worker.last_error is not None
        ):
            return "degraded"
        return current

    def start(self) -> bool:
        with self._lock:
            if self._state in {"starting", "active", "degraded", "stopping", "unavailable"}:
                return False
            self._state = "starting"
        try:
            initialized = self.repository.initialize()
            self.repository.validate_runtime_health()
            started = []
            if self.config.client_enabled:
                started.append(self.client_worker.start())
            if self.config.ap_enabled:
                started.append(self.ap_worker.start())
            started.append(self.cleanup_worker.start())
            if not all(started):
                raise RuntimeError("Observation worker did not start")
        except Exception:
            with self._lock:
                self._state = "unavailable"
            self.telemetry.emit(
                "observation.runtime_unavailable",
                "error",
                failure_category="initialization_error",
            )
            self._stop_started_workers()
            return False
        with self._lock:
            self._state = "active"
        self.telemetry.emit(
            "observation.runtime_started",
            abandoned_cycles=initialized.abandoned_cycles,
            client_enabled=self.config.client_enabled,
            ap_enabled=self.config.ap_enabled,
            site_count=len(self.config.site_ids),
        )
        return True

    def stop(self, timeout_seconds: float | None = None) -> bool:
        with self._lock:
            if self._state == "disabled":
                return True
            self._state = "stopping"
        timeout = self.config.shutdown_timeout_seconds if timeout_seconds is None else max(0.0, float(timeout_seconds))
        deadline = time.monotonic() + timeout
        success = True
        for worker in (self.ap_worker, self.client_worker, self.cleanup_worker):
            remaining = max(0.0, deadline - time.monotonic())
            try:
                success = bool(worker.stop(remaining)) and success
            except Exception:
                success = False
        if success:
            with self._lock:
                self._state = "disabled"
            self.telemetry.emit("observation.runtime_stopped")
            return True
        return False

    def _stop_started_workers(self) -> None:
        for worker in (self.ap_worker, self.client_worker, self.cleanup_worker):
            try:
                worker.stop(0.0)
            except Exception:
                pass


def create_observation_foundation(
    settings: dict[str, Any],
    provider: Any,
    telemetry: Any,
    *,
    logger: logging.Logger | None = None,
):
    """Always return a fail-open lifecycle object without starting threads."""
    actual_logger = logger or logging.getLogger("observation_foundation")
    adapter = ObservationTelemetry(telemetry, actual_logger)
    try:
        config = observation_config_from_settings(settings)
    except (ObservationConfigError, TypeError, ValueError, OverflowError):
        adapter.emit(
            "observation.runtime_unavailable",
            "error",
            failure_category="configuration_error",
        )
        return UnavailableObservationFoundation()
    if not config.enabled:
        return DisabledObservationFoundation()
    try:
        return ObservationFoundationRuntime(
            config=config,
            provider=provider,
            telemetry=adapter,
            logger=actual_logger,
        )
    except Exception:
        adapter.emit(
            "observation.runtime_unavailable",
            "error",
            failure_category="construction_error",
        )
        return UnavailableObservationFoundation(config=config)
