"""Composition-owned lifecycle for Visit Storage/Start/Reconciliation."""

from __future__ import annotations

import logging
import threading
from typing import Any

from .config import visit_config_from_settings
from .models import VisitLifecycleConfigError
from .read_service import VisitLifecycleReadService
from .reconciliation import VisitLinkReconciler
from .repository import VisitRepository
from .service import VisitLifecycleService
from .start_sink import (
    DISABLED_VISIT_START_SUBMITTER,
    UNAVAILABLE_VISIT_START_SUBMITTER,
    LocalVisitStartSubmitter,
)
from .telemetry import VisitTelemetry


class DisabledVisitLifecycleRuntime:
    enabled = False
    available = False
    state = "disabled"
    start_submitter = DISABLED_VISIT_START_SUBMITTER
    read_service = None
    config = None

    def start_reconciliation(self, registry_read_service: Any) -> bool:
        return False

    def stop_scheduling(self) -> bool:
        return True

    def stop_accepting(self) -> None:
        return None

    def close(self) -> bool:
        return True


class UnavailableVisitLifecycleRuntime(DisabledVisitLifecycleRuntime):
    enabled = True
    state = "unavailable"
    start_submitter = UNAVAILABLE_VISIT_START_SUBMITTER


DISABLED_VISIT_LIFECYCLE_RUNTIME = DisabledVisitLifecycleRuntime()
UNAVAILABLE_VISIT_LIFECYCLE_RUNTIME = UnavailableVisitLifecycleRuntime()


class VisitLifecycleRuntime:
    enabled = True

    def __init__(
        self,
        *,
        config: Any,
        repository: VisitRepository,
        telemetry: VisitTelemetry,
    ):
        self.config = config
        self.repository = repository
        self.telemetry = telemetry
        self.service = VisitLifecycleService(repository, telemetry)
        self.start_submitter = LocalVisitStartSubmitter(
            self.service,
            telemetry,
        )
        self.read_service = VisitLifecycleReadService(repository)
        self.available = True
        self.state = "starting"
        self._state_lock = threading.RLock()
        self._reconciler: VisitLinkReconciler | None = None

    def start_reconciliation(self, registry_read_service: Any) -> bool:
        if registry_read_service is None:
            with self._state_lock:
                self.state = "degraded"
            self.telemetry.emit(
                "visit.runtime_unavailable",
                "warning",
                stage="registry_read_service",
            )
            return False
        with self._state_lock:
            if self._reconciler is not None and self._reconciler.running:
                return False
            reconciler = VisitLinkReconciler(
                config=self.config,
                repository=self.repository,
                registry_read_service=registry_read_service,
                telemetry=self.telemetry,
            )
            self._reconciler = reconciler
        started = reconciler.start()
        with self._state_lock:
            self.state = "active" if started else "degraded"
        if started:
            self.telemetry.emit(
                "visit.runtime_started",
                schema_version=1,
            )
        return started

    def stop_scheduling(self) -> bool:
        with self._state_lock:
            self.state = "stopping"
            reconciler = self._reconciler
        if reconciler is None:
            return True
        stopped = reconciler.stop(self.config.shutdown_timeout_seconds)
        if not stopped:
            self.telemetry.emit(
                "visit.runtime_unavailable",
                "error",
                stage="reconciliation_shutdown_timeout",
                timeout_seconds=self.config.shutdown_timeout_seconds,
            )
        return stopped

    def stop_accepting(self) -> None:
        self.start_submitter.stop_accepting()

    def close(self) -> bool:
        self.stop_accepting()
        idle = self.start_submitter.wait_for_idle(
            self.config.shutdown_timeout_seconds
        )
        with self._state_lock:
            self.state = "unavailable"
            self.available = False
        self.telemetry.emit(
            "visit.runtime_stopped",
            "info" if idle else "warning",
            idle=idle,
        )
        return idle


def create_visit_lifecycle(
    settings: dict[str, Any],
    *,
    logger: logging.Logger,
):
    telemetry = VisitTelemetry(logger)
    try:
        config = visit_config_from_settings(settings)
    except VisitLifecycleConfigError as exc:
        telemetry.emit(
            "visit.runtime_unavailable",
            "critical",
            stage="configuration",
            error_type=type(exc).__name__,
        )
        return UNAVAILABLE_VISIT_LIFECYCLE_RUNTIME
    if not config.enabled:
        return DISABLED_VISIT_LIFECYCLE_RUNTIME
    repository = VisitRepository(config)
    try:
        repository.initialize()
    except Exception as exc:
        telemetry.emit(
            "visit.runtime_unavailable",
            "critical",
            stage="storage_initialization",
            error_type=type(exc).__name__,
        )
        return UNAVAILABLE_VISIT_LIFECYCLE_RUNTIME
    return VisitLifecycleRuntime(
        config=config,
        repository=repository,
        telemetry=telemetry,
    )
