"""Fixed-delay Current State client inventory collector."""

from __future__ import annotations

import threading
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable

from .models import CurrentStateConfig, CurrentStateCycle, utc_now
from .normalizer import canonical_client_mac, canonical_scope, current_client_relevant, normalize_current_client
from .repository import CurrentStateRepository
from .telemetry import CurrentStateTelemetry
from .worker_common import poll_inventory


@dataclass(frozen=True, slots=True)
class ClientCycleOutcome:
    site_id: str
    cycle_id: str
    result: str
    complete: bool
    items_seen: int
    items_stored: int
    page_count: int
    failure_category: str | None


class CurrentClientWorker:
    def __init__(
        self,
        *,
        provider: Any,
        repository: CurrentStateRepository,
        config: CurrentStateConfig,
        telemetry: CurrentStateTelemetry,
        now_factory: Callable[[], str] = utc_now,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        self.provider = provider
        self.repository = repository
        self.config = config
        self.telemetry = telemetry
        self._now = now_factory
        self._monotonic = monotonic
        self.stop_event = threading.Event()
        self._cycle_lock = threading.Lock()
        self._thread_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.degraded = False
        self.last_error: Exception | None = None

    @property
    def state(self) -> str:
        if self.running:
            return "degraded" if self.degraded else "active"
        return "stopped"

    @property
    def running(self) -> bool:
        with self._thread_lock:
            return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        with self._thread_lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self.stop_event.clear()
            self._thread = threading.Thread(target=self._run, name="current-state-clients", daemon=True)
            self._thread.start()
            return True

    def stop(self, timeout: float) -> bool:
        self.stop_event.set()
        with self._thread_lock:
            thread = self._thread
        if thread is None:
            return True
        thread.join(max(0.0, timeout))
        stopped = not thread.is_alive()
        if stopped:
            with self._thread_lock:
                if self._thread is thread:
                    self._thread = None
        return stopped

    def run_once(self) -> tuple[ClientCycleOutcome, ...]:
        if not self._cycle_lock.acquire(blocking=False):
            return ()
        try:
            outcomes = tuple(self._run_site(site_id) for site_id in self.config.site_ids if not self.stop_event.is_set())
            self.degraded = any(item.result != "success" for item in outcomes)
            if not self.degraded:
                self.last_error = None
            return outcomes
        finally:
            self._cycle_lock.release()

    def _run(self) -> None:
        if self.stop_event.wait(self.config.client_initial_delay_seconds):
            return
        while not self.stop_event.is_set():
            try:
                self.run_once()
            except Exception as exc:
                self.last_error = exc
                self.degraded = True
                self.telemetry.emit("current_state.client_cycle_failed", "error", failure_category="worker_error")
            if self.stop_event.wait(self.config.client_interval_seconds):
                return

    def _run_site(self, site_id: str) -> ClientCycleOutcome:
        started_at = self._now()
        started_mono = self._monotonic()
        cycle_id = str(uuid.uuid4())
        inventory = poll_inventory(
            provider=self.provider,
            method_name="list_observation_clients",
            result_key="clients",
            site_id=site_id,
            page_size=self.config.client_page_size,
            max_pages=self.config.client_max_pages,
            max_rows=self.config.client_max_rows,
            timeout_seconds=self.config.request_timeout_seconds,
            stop_event=self.stop_event,
        )
        relevant = [row for row in inventory.rows if current_client_relevant(row, self.config.client_ssids)]
        identities = Counter(mac for row in relevant if (mac := canonical_client_mac(row)) is not None)
        duplicate_macs = {mac for mac, count in identities.items() if count > 1}
        unidentified = sum(1 for row in relevant if canonical_client_mac(row) is None)
        normalized = []
        warnings = inventory.warning_count + unidentified + len(duplicate_macs)
        unknown = 0
        for raw in relevant:
            mac = canonical_client_mac(raw)
            if mac is None or mac in duplicate_macs:
                continue
            item = normalize_current_client(
                raw, cycle_id=cycle_id, site_id=site_id, observed_at=started_at,
                ssids=self.config.client_ssids,
            )
            if item is not None:
                normalized.append(item.values)
                warnings += item.warning_count
                unknown += int(item.unknown_status)
        complete = inventory.complete and not duplicate_macs and unidentified == 0
        if inventory.result == "shutdown":
            result = "shutdown"
        elif complete:
            result = "success"
        elif inventory.rows or relevant:
            result = "partial"
        else:
            result = inventory.result
        failure = inventory.failure_category
        if not complete and failure is None:
            failure = "malformed_response"
        finished_at = self._now()
        duration_ms = max(0, int((self._monotonic() - started_mono) * 1000))
        scope_json, scope_hash = canonical_scope("client", site_id, self.config.client_ssids)
        cycle = CurrentStateCycle(
            cycle_id=cycle_id, kind="client", site_id=site_id,
            capture_started_at=started_at, capture_finished_at=finished_at,
            complete=complete, result=result, source_scope_version=1,
            source_scope_json=scope_json, source_scope_hash=scope_hash,
            source_rows_reported=inventory.total_rows,
            items_seen=len(inventory.rows), items_stored=len(normalized),
            items_skipped=len(inventory.rows) - len(normalized),
            unidentified_count=unidentified,
            duplicate_identity_count=len(duplicate_macs),
            unknown_status_count=unknown,
            error_count=inventory.error_count,
            data_quality_warning_count=warnings,
            page_count=inventory.page_count, failure_category=failure,
            duration_ms=duration_ms, created_at=finished_at,
        )
        try:
            self.repository.publish_cycle(cycle, client_rows=normalized)
        except Exception as exc:
            self.last_error = exc
            self.degraded = True
            self.telemetry.emit("current_state.storage_error", "error", site_id=site_id, cycle_id=cycle_id, kind="client", failure_category="storage_error")
            return ClientCycleOutcome(site_id, cycle_id, "failed", False, len(inventory.rows), 0, inventory.page_count, "storage_error")
        event = {
            "success": "current_state.client_cycle_completed",
            "partial": "current_state.client_cycle_partial",
        }.get(result, "current_state.client_cycle_failed")
        self.telemetry.emit(
            event, "info" if result == "success" else "warning",
            site_id=site_id, cycle_id=cycle_id, kind="client", duration_ms=duration_ms,
            complete=complete, items_seen=len(inventory.rows), items_stored=len(normalized),
            items_skipped=len(inventory.rows) - len(normalized), page_count=inventory.page_count,
            error_count=inventory.error_count, warning_count=warnings,
            duplicate_count=len(duplicate_macs), unknown_status_count=unknown,
            failure_category=failure,
        )
        return ClientCycleOutcome(site_id, cycle_id, result, complete, len(inventory.rows), len(normalized), inventory.page_count, failure)
