"""Fail-open synchronous Visit Start sink used by AuthWorker."""

from __future__ import annotations

import threading
import time
from typing import Protocol

from .models import (
    VisitStartOutcome,
    VisitStartRequest,
    VisitStorageCategory,
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
    _BACKOFF_SECONDS = (0.050, 0.100)

    def __init__(
        self,
        service: VisitLifecycleService,
        telemetry: VisitTelemetry,
        *,
        max_attempts: int = 3,
        total_budget_ms: int = 2_000,
        monotonic=time.monotonic,
    ):
        self._service = service
        self._telemetry = telemetry
        self._condition = threading.Condition()
        self._accepting = True
        self._active_calls = 0
        self._max_attempts = max(1, int(max_attempts))
        self._total_budget_ms = max(1, int(total_budget_ms))
        self._monotonic = monotonic
        self._stop_event = threading.Event()

    def submit_authorized(
        self,
        request: VisitStartRequest,
    ) -> VisitStartOutcome:
        with self._condition:
            if not self._accepting:
                return VisitStartOutcome(status="shutting_down")
            self._active_calls += 1
        started = self._monotonic()
        deadline = started + self._total_budget_ms / 1000
        attempt = 0
        blockers = _new_blocker_totals()
        try:
            while attempt < self._max_attempts:
                attempt += 1
                if self._stop_event.is_set():
                    return self._storage_failure(
                        VisitStorageError(VisitStorageCategory.UNAVAILABLE),
                        attempt=attempt,
                        started=started,
                        retry_exhausted=False,
                        blockers=blockers,
                    )
                try:
                    outcome = self._service.submit_authorized(
                        request,
                        deadline=deadline,
                        cancel_event=self._stop_event,
                    )
                except VisitStorageError as exc:
                    if exc.category is not VisitStorageCategory.BUSY:
                        return self._storage_failure(
                            exc,
                            attempt=attempt,
                            started=started,
                            retry_exhausted=False,
                            blockers=blockers,
                        )
                    _record_busy_attempt(blockers, exc)
                    remaining = deadline - self._monotonic()
                    exhausted = (
                        attempt >= self._max_attempts or remaining <= 0
                    )
                    if exhausted:
                        return self._storage_failure(
                            exc,
                            attempt=attempt,
                            started=started,
                            retry_exhausted=True,
                            blockers=blockers,
                        )
                    backoff = self._BACKOFF_SECONDS[
                        min(attempt - 1, len(self._BACKOFF_SECONDS) - 1)
                    ]
                    if backoff >= remaining:
                        return self._storage_failure(
                            exc,
                            attempt=attempt,
                            started=started,
                            retry_exhausted=True,
                            blockers=blockers,
                        )
                    if self._stop_event.wait(backoff):
                        return self._storage_failure(
                            VisitStorageError(
                                VisitStorageCategory.UNAVAILABLE
                            ),
                            attempt=attempt,
                            started=started,
                            retry_exhausted=False,
                            blockers=blockers,
                        )
                    continue
                if attempt > 1 and outcome.status == "duplicate":
                    self._telemetry.emit(
                        "visit.start_retry_recovered",
                        "info",
                        operation="start",
                        attempt=attempt,
                        max_attempts=self._max_attempts,
                        budget_ms=self._total_budget_ms,
                        wait_ms=self._elapsed_ms(started),
                        retry_exhausted=False,
                        **blockers,
                    )
                return outcome
            raise AssertionError("bounded Start retry loop did not return")
        except VisitValidationError as exc:
            self._telemetry.emit(
                "visit.storage_error",
                "warning",
                stage="start_validation",
                error_type=type(exc).__name__,
                operation="start",
                attempt=max(1, attempt),
                retry_exhausted=False,
                wait_ms=self._elapsed_ms(started),
            )
            return VisitStartOutcome(status="invalid")
        except Exception as exc:
            self._telemetry.emit(
                "visit.storage_error",
                "error",
                stage="start_unexpected",
                error_type=type(exc).__name__,
                operation="start",
                attempt=max(1, attempt),
                retry_exhausted=False,
                wait_ms=self._elapsed_ms(started),
            )
            return VisitStartOutcome(status="unavailable")
        finally:
            with self._condition:
                self._active_calls -= 1
                self._condition.notify_all()

    def stop_accepting(self) -> None:
        with self._condition:
            self._accepting = False
            self._stop_event.set()
            self._condition.notify_all()
        wake_waiters = getattr(self._service, "wake_write_waiters", None)
        if callable(wake_waiters):
            wake_waiters()

    def wait_for_idle(self, timeout: float) -> bool:
        deadline = time.monotonic() + max(0.0, float(timeout))
        with self._condition:
            while self._active_calls:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(remaining)
            return True

    def _storage_failure(
        self,
        error: VisitStorageError,
        *,
        attempt: int,
        started: float,
        retry_exhausted: bool,
        blockers: dict[str, int | str | None],
    ) -> VisitStartOutcome:
        snapshot = error.contention
        self._telemetry.emit(
            "visit.storage_error",
            "error",
            stage="start",
            storage_category=error.category.value,
            operation="start",
            attempt=attempt,
            max_attempts=self._max_attempts,
            budget_ms=self._total_budget_ms,
            retry_exhausted=retry_exhausted,
            wait_ms=self._elapsed_ms(started),
            lock_wait_ms=error.lock_wait_ms,
            contention_layer=error.contention_layer,
            holder_operation=(
                None if snapshot is None else snapshot.holder_operation
            ),
            holder_age_ms=(
                None if snapshot is None else snapshot.holder_age_ms
            ),
            foreground_queue_depth=(
                None
                if snapshot is None
                else snapshot.foreground_queue_depth
            ),
            background_queue_depth=(
                None
                if snapshot is None
                else snapshot.background_queue_depth
            ),
            waiter_operation=(
                None if snapshot is None else snapshot.waiter_operation
            ),
            waiter_wait_ms=(
                None if snapshot is None else snapshot.waiter_wait_ms
            ),
            **blockers,
        )
        return VisitStartOutcome(
            status="unavailable",
            storage_category=error.category.value,
        )

    def _elapsed_ms(self, started: float) -> int:
        return max(0, int(round((self._monotonic() - started) * 1000)))


def _new_blocker_totals() -> dict[str, int | str | None]:
    return {
        "coordinator_busy_attempt_count": 0,
        "sqlite_busy_attempt_count": 0,
        "background_blocked_attempt_count": 0,
        "background_blocked_wait_ms": 0,
        "foreground_blocked_attempt_count": 0,
        "foreground_blocked_wait_ms": 0,
        "max_background_holder_age_ms": 0,
        "last_holder_operation": None,
    }


def _record_busy_attempt(
    totals: dict[str, int | str | None],
    error: VisitStorageError,
) -> None:
    if error.contention_layer == "coordinator":
        totals["coordinator_busy_attempt_count"] = int(
            totals["coordinator_busy_attempt_count"]
        ) + 1
    elif error.contention_layer == "sqlite":
        totals["sqlite_busy_attempt_count"] = int(
            totals["sqlite_busy_attempt_count"]
        ) + 1
    snapshot = error.contention
    if snapshot is None:
        return
    holder = snapshot.holder_operation
    wait_ms = max(0, int(error.lock_wait_ms or 0))
    totals["last_holder_operation"] = holder
    background_holders = {
        "reader_line",
        "reader_checkpoint",
        "pending_retry",
        "reconciliation",
        "startup",
    }
    if holder in background_holders:
        totals["background_blocked_attempt_count"] = int(
            totals["background_blocked_attempt_count"]
        ) + 1
        totals["background_blocked_wait_ms"] = int(
            totals["background_blocked_wait_ms"]
        ) + wait_ms
        totals["max_background_holder_age_ms"] = max(
            int(totals["max_background_holder_age_ms"]),
            int(snapshot.holder_age_ms or 0),
        )
    elif holder == "start" or snapshot.foreground_queue_depth > 0:
        totals["foreground_blocked_attempt_count"] = int(
            totals["foreground_blocked_attempt_count"]
        ) + 1
        totals["foreground_blocked_wait_ms"] = int(
            totals["foreground_blocked_wait_ms"]
        ) + wait_ms
