"""Bounded starvation-free Registry link reconciliation."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any, Callable

from app.common.mac import format_mac_colon

from .models import VisitLifecycleConfig, VisitStorageError, utc_now
from .repository import VisitRepository
from .telemetry import VisitTelemetry


MAX_RECONCILIATION_PASS_SECONDS = 20.0


class VisitLinkReconciler:
    def __init__(
        self,
        *,
        config: VisitLifecycleConfig,
        repository: VisitRepository,
        registry_read_service: Any,
        telemetry: VisitTelemetry,
        monotonic: Callable[[], float] = time.monotonic,
        pass_max_duration_seconds: float | None = None,
    ):
        self.config = config
        self.repository = repository
        self.registry_read_service = registry_read_service
        self.telemetry = telemetry
        self._monotonic = monotonic
        configured_deadline = (
            min(
                MAX_RECONCILIATION_PASS_SECONDS,
                config.reconcile_interval_seconds,
            )
            if pass_max_duration_seconds is None
            else float(pass_max_duration_seconds)
        )
        if not isfinite(configured_deadline) or configured_deadline <= 0:
            raise ValueError("reconciliation pass deadline must be positive")
        self._pass_max_duration_seconds = configured_deadline
        self._stop_event = threading.Event()
        self._state_lock = threading.RLock()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        with self._state_lock:
            return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        with self._state_lock:
            if self.running:
                return False
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="visit_link_reconciliation",
                daemon=True,
            )
            self._thread.start()
            return True

    def stop(self, timeout: float) -> bool:
        with self._state_lock:
            thread = self._thread
            self._stop_event.set()
        self.repository.wake_write_waiters()
        if thread is None:
            return True
        thread.join(max(0.0, float(timeout)))
        stopped = not thread.is_alive()
        if stopped:
            with self._state_lock:
                if self._thread is thread:
                    self._thread = None
        return stopped

    def run_once(self) -> int:
        deadline = self._monotonic() + self._pass_max_duration_seconds
        now = utc_now()
        candidates = self.repository.list_due_reconciliation(
            now,
            self.config.reconcile_batch_size,
        )
        linked = 0
        retry_at = _after_seconds(
            now,
            self.config.reconcile_interval_seconds,
        )
        processed = 0
        deadline_emitted = False

        def deadline_reached() -> bool:
            nonlocal deadline_emitted
            if self._monotonic() < deadline:
                return False
            if not deadline_emitted:
                deadline_emitted = True
                self.telemetry.emit(
                    "visit.reconciliation_degraded",
                    "warning",
                    stage="pass_deadline",
                    max_duration_seconds=self._pass_max_duration_seconds,
                    processed_count=processed,
                    operation="reconciliation",
                    attempt=1,
                    retry_exhausted=False,
                    wait_ms=int(self._pass_max_duration_seconds * 1000),
                )
            return True

        for candidate in candidates:
            if self._stop_event.is_set() or deadline_reached():
                break
            try:
                device = self.registry_read_service.get_device_by_mac(
                    candidate.client_mac
                )
                if self._stop_event.is_set() or deadline_reached():
                    break
                snapshot = (
                    self.registry_read_service.get_snapshot_by_auth_session(
                        candidate.start_auth_session_id,
                        site_id=candidate.site_id,
                        client_mac=candidate.client_mac,
                    )
                )
                if self._stop_event.is_set() or deadline_reached():
                    break
            except Exception as exc:
                fields: dict[str, Any] = {
                    "error_type": type(exc).__name__,
                    "operation": "reconciliation",
                    "attempt": 1,
                    "retry_exhausted": False,
                    "wait_ms": 0,
                }
                if isinstance(exc, VisitStorageError):
                    fields["storage_category"] = exc.category.value
                    fields["lock_wait_ms"] = exc.lock_wait_ms
                    fields.update(_contention_fields(exc))
                self.telemetry.emit(
                    "visit.reconciliation_degraded",
                    "warning",
                    **fields,
                )
                break
            device_id = _safe_device_id(device)
            snapshot_id = _safe_snapshot_id(
                snapshot,
                site_id=candidate.site_id,
                client_mac=candidate.client_mac,
            )
            try:
                changed, _complete = (
                    self.repository.record_reconciliation_attempt(
                        candidate.visit_id,
                        device_id=device_id,
                        initial_snapshot_id=snapshot_id,
                        attempted_at=now,
                        retry_at=retry_at,
                        deadline=deadline,
                        cancel_event=self._stop_event,
                    )
                )
            except VisitStorageError as exc:
                self.telemetry.emit(
                    "visit.reconciliation_degraded",
                    "warning",
                    error_type=type(exc).__name__,
                    operation="reconciliation",
                    attempt=1,
                    retry_exhausted=False,
                    storage_category=exc.category.value,
                    lock_wait_ms=exc.lock_wait_ms,
                    wait_ms=exc.lock_wait_ms,
                    **_contention_fields(exc),
                )
                break
            processed += 1
            if changed:
                linked += 1
                self.telemetry.emit(
                    "visit.link_reconciled",
                    visit_id=candidate.visit_id,
                    site_id=candidate.site_id,
                    client_mac=candidate.client_mac,
                    device_linked=device_id is not None,
                    snapshot_linked=snapshot_id is not None,
                )
        return linked

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception as exc:
                self.telemetry.emit(
                    "visit.reconciliation_degraded",
                    "warning",
                    error_type=type(exc).__name__,
                    operation="reconciliation",
                    attempt=1,
                    retry_exhausted=False,
                    wait_ms=0,
                )
            self._stop_event.wait(self.config.reconcile_interval_seconds)


def _after_seconds(timestamp: str, seconds: float) -> str:
    parsed = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
    return (
        (parsed.replace(tzinfo=timezone.utc) + timedelta(seconds=seconds))
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _contention_fields(error: VisitStorageError) -> dict[str, Any]:
    snapshot = error.contention
    return {
        "contention_layer": error.contention_layer,
        "holder_operation": (
            None if snapshot is None else snapshot.holder_operation
        ),
        "holder_age_ms": (
            None if snapshot is None else snapshot.holder_age_ms
        ),
        "foreground_queue_depth": (
            None if snapshot is None else snapshot.foreground_queue_depth
        ),
        "background_queue_depth": (
            None if snapshot is None else snapshot.background_queue_depth
        ),
        "waiter_operation": (
            None if snapshot is None else snapshot.waiter_operation
        ),
        "waiter_wait_ms": (
            None if snapshot is None else snapshot.waiter_wait_ms
        ),
    }


def _safe_device_id(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    device_id = value.get("device_id")
    return device_id if isinstance(device_id, str) and device_id else None


def _safe_snapshot_id(
    value: Any,
    *,
    site_id: str,
    client_mac: str,
) -> str | None:
    if not isinstance(value, dict):
        return None
    snapshot_id = value.get("snapshot_id")
    if not isinstance(snapshot_id, str) or not snapshot_id:
        return None
    if value.get("site_id") != site_id:
        return None
    requested_mac = value.get("requested_mac")
    try:
        if format_mac_colon(requested_mac) != client_mac:
            return None
    except (TypeError, ValueError):
        return None
    return snapshot_id
