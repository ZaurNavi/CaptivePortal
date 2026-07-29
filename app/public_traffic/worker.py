"""Lifecycle-owned background loop for the public traffic reader."""

from __future__ import annotations

import logging
import threading

from .reader import PublicTrafficReader
from .repository import PublicTrafficRepository
from .service import PublicTrafficService


class PublicTrafficWorker:
    def __init__(
        self,
        *,
        reader: PublicTrafficReader,
        repository: PublicTrafficRepository,
        service: PublicTrafficService,
        logger: logging.Logger,
        scan_interval_seconds: int,
    ):
        self.reader = reader
        self.repository = repository
        self.service = service
        self.logger = logger
        self.scan_interval_seconds = scan_interval_seconds
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._startup_mode: str | None = None
        self._startup_started_logged = False
        self._startup_complete = False

    def start(self) -> bool:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="public_traffic_worker",
                daemon=True,
            )
            self._thread.start()
            return True

    def stop(self, timeout: float = 5.0) -> None:
        with self._lock:
            thread = self._thread
            self._stop_event.set()
        if thread is not None:
            thread.join(timeout=max(0.0, timeout))
        with self._lock:
            if self._thread is thread and (
                thread is None or not thread.is_alive()
            ):
                self._thread = None

    @property
    def running(self) -> bool:
        with self._lock:
            return (
                self._thread is not None
                and self._thread.is_alive()
            )

    def run_once(self) -> None:
        if self._startup_complete:
            self.reader.scan()
            return

        if self._startup_mode is None:
            self._startup_mode = (
                "backfill"
                if not self.repository.initial_backfill_completed()
                else "reconciliation"
            )
        event_prefix = f"public_traffic_{self._startup_mode}"
        if not self._startup_started_logged:
            self.logger.info("%s_started", event_prefix)
            self._startup_started_logged = True

        complete = self.reader.scan()
        if not complete:
            return
        if self._startup_mode == "backfill":
            self.repository.mark_initial_backfill_completed(
                self.service.now_iso()
            )
        self.logger.info("%s_completed", event_prefix)
        self._startup_complete = True

    def _run(self) -> None:
        self.logger.info("public_traffic_counter_started")
        try:
            while not self._stop_event.is_set():
                try:
                    self.run_once()
                except Exception:
                    self.logger.exception(
                        "public_traffic_reader_error"
                    )
                if self._stop_event.wait(
                    self.scan_interval_seconds
                ):
                    break
        finally:
            self.logger.info("public_traffic_counter_stopped")
