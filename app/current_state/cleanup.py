"""Bounded whole-cycle retention for Current State history."""

from __future__ import annotations

import threading
import time
from datetime import timedelta
from typing import Callable

from .models import CleanupResult, CurrentStateConfig, format_utc, parse_utc, utc_now
from .repository import CurrentStateRepository
from .telemetry import CurrentStateTelemetry


class CurrentStateCleanup:
    def __init__(self, repository: CurrentStateRepository, config: CurrentStateConfig):
        self.repository = repository
        self.config = config

    def run_once(
        self,
        *,
        now_utc: str | None = None,
        stop_event: threading.Event | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> CleanupResult:
        stop = stop_event or threading.Event()
        now = parse_utc(now_utc or utc_now(), "now_utc")
        cutoff = format_utc(now - timedelta(hours=self.config.history_retention_hours))
        deadline = monotonic() + self.config.cleanup_max_duration_seconds
        protected = self.repository.protected_cycle_ids()
        deleted_cycles = deleted_clients = deleted_aps = 0
        duration_exhausted = interrupted = False

        def can_continue() -> bool:
            nonlocal duration_exhausted, interrupted
            if stop.is_set():
                interrupted = True
                return False
            if monotonic() >= deadline:
                duration_exhausted = True
                return False
            return deleted_cycles < self.config.cleanup_max_cycles_per_run

        while can_continue():
            candidates = self.repository.cleanup_candidates(
                cutoff_utc=cutoff,
                protected=protected,
                limit=self.config.cleanup_max_cycles_per_run - deleted_cycles,
            )
            if not candidates:
                break
            selected = _bounded_batch(candidates, self.config.cleanup_max_rows_per_transaction)
            count, clients, aps = self.repository.delete_cycles(tuple(item[0] for item in selected))
            deleted_cycles += count
            deleted_clients += clients
            deleted_aps += aps
            if count == 0:
                break

        while self.repository.count_client_rows() > self.config.history_max_client_rows and can_continue():
            candidates = self.repository.oldest_client_candidates(
                protected=protected,
                limit=self.config.cleanup_max_cycles_per_run - deleted_cycles,
            )
            if not candidates:
                break
            selected = _bounded_batch(candidates, self.config.cleanup_max_rows_per_transaction)
            count, clients, aps = self.repository.delete_cycles(tuple(item[0] for item in selected))
            deleted_cycles += count
            deleted_clients += clients
            deleted_aps += aps
            if count == 0:
                break

        pressure = self.repository.count_client_rows() > self.config.history_max_client_rows
        return CleanupResult(
            deleted_cycles=deleted_cycles,
            deleted_client_rows=deleted_clients,
            deleted_ap_rows=deleted_aps,
            duration_exhausted=duration_exhausted,
            interrupted=interrupted,
            retention_pressure=pressure,
        )


def _bounded_batch(candidates: tuple[tuple[str, int, int], ...], row_budget: int) -> tuple[tuple[str, int, int], ...]:
    selected: list[tuple[str, int, int]] = []
    rows = 0
    for item in candidates:
        item_rows = item[1] + item[2]
        if not selected and item_rows > row_budget:
            # Whole-cycle exception required by the storage contract.
            return (item,)
        if selected and rows + item_rows > row_budget:
            break
        selected.append(item)
        rows += item_rows
    return tuple(selected)


class CurrentStateCleanupWorker:
    def __init__(self, cleanup: CurrentStateCleanup, config: CurrentStateConfig, telemetry: CurrentStateTelemetry):
        self.cleanup = cleanup
        self.config = config
        self.telemetry = telemetry
        self.stop_event = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.last_error: Exception | None = None
        self.retention_pressure = False

    @property
    def running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self.stop_event.clear()
            self._thread = threading.Thread(target=self._run, name="current-state-cleanup", daemon=True)
            self._thread.start()
            return True

    def stop(self, timeout: float) -> bool:
        self.stop_event.set()
        with self._lock:
            thread = self._thread
        if thread is None:
            return True
        thread.join(max(0.0, timeout))
        stopped = not thread.is_alive()
        if stopped:
            with self._lock:
                if self._thread is thread:
                    self._thread = None
        return stopped

    def run_once(self) -> CleanupResult:
        try:
            result = self.cleanup.run_once(stop_event=self.stop_event)
        except Exception as exc:
            self.last_error = exc
            self.telemetry.emit("current_state.cleanup_failed", "error", failure_category="storage_error")
            raise
        self.last_error = None
        self.retention_pressure = result.retention_pressure
        self.telemetry.emit(
            "current_state.cleanup_completed",
            deleted_cycles=result.deleted_cycles,
            deleted_client_rows=result.deleted_client_rows,
            deleted_ap_rows=result.deleted_ap_rows,
            duration_exhausted=result.duration_exhausted,
            interrupted=result.interrupted,
        )
        if result.retention_pressure:
            self.telemetry.emit("current_state.retention_pressure", "warning", remaining_client_rows=self.cleanup.repository.count_client_rows())
        return result

    def _run(self) -> None:
        if self.stop_event.wait(self.config.cleanup_initial_delay_seconds):
            return
        while not self.stop_event.is_set():
            try:
                self.run_once()
            except Exception:
                pass
            if self.stop_event.wait(self.config.cleanup_interval_seconds):
                return
