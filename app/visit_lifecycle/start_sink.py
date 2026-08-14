"""Fail-open synchronous Visit Start sink used by AuthWorker."""

from __future__ import annotations

import threading
import time
from typing import Protocol

from .models import (
    VisitStartOutcome,
    VisitStartRequest,
    VisitStorageError,
    VisitValidationError,
)
from .service import VisitLifecycleService
from .telemetry import VisitTelemetry


class VisitStartSubmitter(Protocol):
    def submit_authorized(
        self,
        request: VisitStartRequest,
    ) -> VisitStartOutcome:
        ...


class DisabledVisitStartSubmitter:
    def submit_authorized(
        self,
        request: VisitStartRequest,
    ) -> VisitStartOutcome:
        return VisitStartOutcome(status="disabled")

    def stop_accepting(self) -> None:
        return None

    def wait_for_idle(self, timeout: float) -> bool:
        return True


class UnavailableVisitStartSubmitter(DisabledVisitStartSubmitter):
    def submit_authorized(
        self,
        request: VisitStartRequest,
    ) -> VisitStartOutcome:
        return VisitStartOutcome(status="unavailable")


DISABLED_VISIT_START_SUBMITTER = DisabledVisitStartSubmitter()
UNAVAILABLE_VISIT_START_SUBMITTER = UnavailableVisitStartSubmitter()


class LocalVisitStartSubmitter:
    def __init__(
        self,
        service: VisitLifecycleService,
        telemetry: VisitTelemetry,
    ):
        self._service = service
        self._telemetry = telemetry
        self._condition = threading.Condition()
        self._accepting = True
        self._active_calls = 0

    def submit_authorized(
        self,
        request: VisitStartRequest,
    ) -> VisitStartOutcome:
        with self._condition:
            if not self._accepting:
                return VisitStartOutcome(status="shutting_down")
            self._active_calls += 1
        try:
            return self._service.submit_authorized(request)
        except VisitValidationError as exc:
            self._telemetry.emit(
                "visit.storage_error",
                "warning",
                stage="start_validation",
                error_type=type(exc).__name__,
            )
            return VisitStartOutcome(status="invalid")
        except VisitStorageError as exc:
            self._telemetry.emit(
                "visit.storage_error",
                "error",
                stage="start",
                storage_category=exc.category.value,
            )
            return VisitStartOutcome(
                status="unavailable",
                storage_category=exc.category.value,
            )
        except Exception as exc:
            self._telemetry.emit(
                "visit.storage_error",
                "error",
                stage="start_unexpected",
                error_type=type(exc).__name__,
            )
            return VisitStartOutcome(status="unavailable")
        finally:
            with self._condition:
                self._active_calls -= 1
                self._condition.notify_all()

    def stop_accepting(self) -> None:
        with self._condition:
            self._accepting = False

    def wait_for_idle(self, timeout: float) -> bool:
        deadline = time.monotonic() + max(0.0, float(timeout))
        with self._condition:
            while self._active_calls:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(remaining)
            return True
