"""Bounded retention primitives without production lifecycle wiring."""

from __future__ import annotations

import threading
import time
from datetime import timedelta
from typing import Callable

from .models import CleanupResult, ObservationConfig, format_utc, parse_utc, utc_now
from .repository import ObservationRepository
from .telemetry import ObservationTelemetry


class ObservationCleanup:
    """Delete expired non-running cycles in bounded, cascade-safe batches."""

    def __init__(
        self,
        repository: ObservationRepository,
        config: ObservationConfig,
    ):
        self._repository = repository
        self._config = config

    def run_once(
        self,
        *,
        now_utc: str | None = None,
        shutdown_event: threading.Event | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> CleanupResult:
        stop = shutdown_event or threading.Event()
        now = parse_utc(now_utc or utc_now(), "now_utc")
        dynamic_cutoff = format_utc(
            now - timedelta(days=self._config.dynamic_retention_days)
        )
        config_cutoff = format_utc(
            now - timedelta(days=self._config.config_retention_days)
        )
        deadline = monotonic() + self._config.cleanup_max_duration_seconds
        totals = {"dynamic": 0, "config": 0}
        complete = {"dynamic": False, "config": False}
        batches = 0
        interrupted = False
        duration_exhausted = False

        while not all(complete.values()):
            made_progress = False
            for name, kinds, cutoff in (
                ("dynamic", ("client", "ap_dynamic"), dynamic_cutoff),
                ("config", ("ap_config",), config_cutoff),
            ):
                if complete[name]:
                    continue
                if stop.is_set():
                    interrupted = True
                    break
                if monotonic() >= deadline:
                    duration_exhausted = True
                    break
                deleted = self._repository.delete_expired_cycles(
                    kinds=kinds,
                    cutoff_utc=cutoff,
                    limit=self._config.cleanup_batch_size,
                )
                batches += 1
                totals[name] += deleted
                made_progress = made_progress or deleted > 0
                if deleted < self._config.cleanup_batch_size:
                    complete[name] = True
            if interrupted or duration_exhausted:
                break
            if not made_progress and not all(complete.values()):
                break

        if not interrupted and not duration_exhausted:
            self._repository.optimize()
        return CleanupResult(
            deleted_dynamic_cycles=totals["dynamic"],
            deleted_config_cycles=totals["config"],
            batches=batches,
            interrupted=interrupted,
            duration_exhausted=duration_exhausted,
        )


class ObservationCleanupWorker:
    """Optional fixed-delay worker primitive; TASK 01A does not compose it."""

    def __init__(
        self,
        cleanup: ObservationCleanup,
        config: ObservationConfig,
        *,
        now_factory: Callable[[], str] = utc_now,
        telemetry: ObservationTelemetry | None = None,
    ):
        self._cleanup = cleanup
        self._config = config
        self._now_factory = now_factory
        self._telemetry = telemetry
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.last_error: Exception | None = None

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
            self._thread = threading.Thread(
                target=self._run,
                name="observation-cleanup",
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
        thread.join(
            self._config.shutdown_timeout_seconds
            if timeout is None
            else max(0.0, float(timeout))
        )
        stopped = not thread.is_alive()
        if stopped:
            with self._lock:
                if self._thread is thread:
                    self._thread = None
        return stopped

    def run_once(self) -> CleanupResult:
        try:
            result = self._cleanup.run_once(
                now_utc=self._now_factory(),
                shutdown_event=self._stop_event,
            )
        except Exception as exc:
            self.last_error = exc
            if self._telemetry is not None:
                self._telemetry.emit(
                    "observation.cleanup_failed",
                    "error",
                    failure_category="storage_error",
                )
            raise
        self.last_error = None
        if self._telemetry is not None:
            event = (
                "observation.cleanup_partial"
                if result.interrupted or result.duration_exhausted
                else "observation.cleanup_completed"
            )
            self._telemetry.emit(
                event,
                "warning" if event.endswith("partial") else "info",
                deleted_dynamic_cycles=result.deleted_dynamic_cycles,
                deleted_config_cycles=result.deleted_config_cycles,
                batches=result.batches,
                interrupted=result.interrupted,
                duration_exhausted=result.duration_exhausted,
            )
        return result

    def _run(self) -> None:
        if self._stop_event.wait(
            self._config.cleanup_initial_delay_seconds
        ):
            return
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception as exc:  # Fail-open primitive boundary.
                self.last_error = exc
            if self._stop_event.wait(
                self._config.cleanup_interval_seconds
            ):
                return
