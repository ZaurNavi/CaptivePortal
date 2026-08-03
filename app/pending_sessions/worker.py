from __future__ import annotations

import threading

from .cleaner import PendingClientSessionCleaner


class PendingSessionWorker:
    """Single-process fixed-delay worker."""

    def __init__(self, cleaner: PendingClientSessionCleaner) -> None:
        self.cleaner = cleaner
        self.config = cleaner.config
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()

    def start(self) -> bool:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            if self.cleaner.shutdown_event.is_set():
                return False
            self._thread = threading.Thread(
                target=self._run,
                name="pending_session_cleaner_worker",
                daemon=True,
            )
            self._thread.start()
            self.cleaner.telemetry.safe_emit_system(
                "pending_session_cleaner_started",
            )
            return True

    def run_once(self):
        return self.cleaner.run_once()

    def stop(self, timeout_seconds: float) -> bool:
        self.cleaner.begin_stopping()
        with self._lock:
            thread = self._thread
        if thread is not None:
            thread.join(max(0.0, float(timeout_seconds)))
            stopped = not thread.is_alive()
        else:
            stopped = True
        self.cleaner.close()
        self.cleaner.telemetry.safe_emit_system(
            "pending_session_cleaner_stopped",
            stopped=stopped,
        )
        return stopped

    def _run(self) -> None:
        if self.cleaner.shutdown_event.wait(
            self.config.initial_delay_seconds
        ):
            return
        while not self.cleaner.shutdown_event.is_set():
            self.cleaner.run_once()
            if self.cleaner.shutdown_event.wait(
                self.config.scan_interval_seconds
            ):
                return
