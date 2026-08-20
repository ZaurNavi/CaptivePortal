"""Bounded background integrity validation for Observation storage."""

from __future__ import annotations

import threading
import time
from typing import Callable

from .repository import ObservationRepository
from .telemetry import ObservationTelemetry


INTEGRITY_CHECK_MAX_DURATION_SECONDS = 900.0


class ObservationIntegrityWorker:
    """Run the expensive SQLite integrity scan outside portal readiness."""

    def __init__(
        self,
        repository: ObservationRepository,
        telemetry: ObservationTelemetry,
        *,
        max_duration_seconds: float = INTEGRITY_CHECK_MAX_DURATION_SECONDS,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        self._repository = repository
        self._telemetry = telemetry
        self._max_duration_seconds = max(0.001, float(max_duration_seconds))
        self._monotonic = monotonic
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.last_error: Exception | None = None
        self.completed = False
        self.timed_out = False

    @property
    def running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._stop_event.clear()
            self.last_error = None
            self.completed = False
            self.timed_out = False
            self._thread = threading.Thread(
                target=self._run,
                name="observation-integrity",
                daemon=True,
            )
            self._thread.start()
            return True

    def stop(self, timeout: float | None = None) -> bool:
        with self._lock:
            thread = self._thread
        if thread is None:
            return True
        self._stop_event.set()
        thread.join(None if timeout is None else max(0.0, float(timeout)))
        stopped = not thread.is_alive()
        if stopped:
            with self._lock:
                if self._thread is thread:
                    self._thread = None
        return stopped

    def _run(self) -> None:
        started = self._monotonic()
        deadline = started + self._max_duration_seconds
        self._telemetry.emit(
            "observation.integrity_check_started",
            max_duration_seconds=self._max_duration_seconds,
        )
        try:
            completed = self._repository.validate_runtime_health(
                should_interrupt=lambda: (
                    self._stop_event.is_set()
                    or self._monotonic() >= deadline
                )
            )
        except Exception as exc:
            self.last_error = exc
            self._telemetry.emit(
                "observation.integrity_check_failed",
                "error",
                failure_category="storage_error",
                duration_ms=round(
                    (self._monotonic() - started) * 1000,
                    3,
                ),
            )
            return

        duration_ms = round((self._monotonic() - started) * 1000, 3)
        if completed:
            self.completed = True
            self.last_error = None
            self._telemetry.emit(
                "observation.integrity_check_completed",
                duration_ms=duration_ms,
            )
            return
        if self._stop_event.is_set():
            self._telemetry.emit(
                "observation.integrity_check_interrupted",
                duration_ms=duration_ms,
            )
            return
        self.timed_out = True
        self._telemetry.emit(
            "observation.integrity_check_timed_out",
            "warning",
            duration_ms=duration_ms,
            max_duration_seconds=self._max_duration_seconds,
        )
