"""Bounded starvation-free Registry link reconciliation."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any, Callable

from app.common.mac import format_mac_colon

from .models import VisitLifecycleConfig, VisitStorageError, utc_now, format_utc, protocol_visit_guard
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
        protocol_reader=None,
        service_history_path=None,
        service_history_ttl_days=None,
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
        self.protocol_reader = protocol_reader
        self._protocol_after = None
        if (service_history_path is None)!=(service_history_ttl_days is None):raise ValueError('Incomplete Visit history activation policy')
        if service_history_ttl_days is not None and (type(service_history_ttl_days) is not int or not 1<=service_history_ttl_days<=365):raise ValueError('Invalid Visit history retention')
        self.service_history_path=service_history_path
        self.service_history_ttl_days=service_history_ttl_days

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
        # Same existing thread; source locks end before a short Visit batch.
        # A small reserved slice prevents Registry backlog starving this lane.
        if self.protocol_reader is not None:
            try:
                self.run_protocol_once(now=now, deadline=min(deadline, self._monotonic()+2))
            except Exception:
                self.telemetry.emit('visit.reconciliation_degraded', 'warning', stage='protocol_materialization')
        if self.service_history_path is not None:
            try:
                self.run_services_once(now=now,deadline=min(deadline,self._monotonic()+2))
            except Exception:
                self.telemetry.emit('visit.reconciliation_degraded','warning',stage='service_materialization')
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

    def run_services_once(self, *, now=None, deadline=None, crash_point=lambda _:None):
        if self.service_history_path is None:return 0
        from app.analytics.source_gateway import QueryDeadline
        from app.network_service_recognition.materialization_repository import read_visit_delivery_page
        now=now or utc_now();deadline=deadline if deadline is not None else self._monotonic()+2
        now=format_utc(datetime.strptime(now,'%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc))
        total=0
        # A finite drain, not one commit per edge or an unbounded backlog loop.
        # Every <=25-row batch releases source AND Visit locks and re-enters
        # the existing priority coordinator, allowing foreground Auth through.
        for _ in range(32):
            if self._stop_event.is_set() or self._monotonic()>=deadline:break
            cursor=self.repository.service_consumer_cursor()
            try:
                page=read_visit_delivery_page(self.service_history_path,cursor,deadline=QueryDeadline(deadline,self._monotonic))
            except Exception as exc:
                from app.network_service_recognition.materialization_repository import MaterializationConflict
                self.repository.service_delivery_unavailable(now=now,deadline=deadline,conflict=isinstance(exc,MaterializationConflict))
                raise
            changed=self.repository.consume_service_delivery(page,cursor,now=now,history_ttl_days=self.service_history_ttl_days,
                deadline=deadline,cancel_event=self._stop_event,crash_point=crash_point)
            total+=changed
            after=self.repository.service_consumer_cursor()
            if not changed and after['last_outbox_seq']==(cursor['last_outbox_seq'] if cursor else 0):break
        return total

    def run_protocol_once(self, *, now=None, deadline=None):
        """Eventually consistent NI03 materialization, not an Auth/GET hook."""
        from app.analytics.source_gateway import QueryDeadline
        from app.network_metadata.validation import ni_format_utc, ni_timestamp, digest
        now = now or utc_now()
        now = format_utc(datetime.strptime(now,'%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc))
        at = datetime.strptime(now, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
        deadline = deadline if deadline is not None else self._monotonic()+2
        if self.protocol_reader is None or self._stop_event.is_set():
            return 0
        limit = min(25, self.config.reconcile_batch_size)
        visits = self.repository.protocol_candidates(now, after=self._protocol_after, limit=limit, deadline=deadline)
        if not visits and self._protocol_after is not None:
            self._protocol_after = None
            visits = self.repository.protocol_candidates(now, limit=limit, deadline=deadline)
        updates = []
        for visit in visits:
            if self._stop_event.is_set() or self._monotonic() >= deadline:
                break
            self._protocol_after = visit.visit_id
            end = datetime.strptime(visit.closed_at or now, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
            start = datetime.strptime(visit.started_at, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
            if end <= start or end > at:
                continue
            old = self.repository.saved_protocol_summary(visit)
            value = dict(visit_id=visit.visit_id, summary_version=1, site_id=visit.site_id,
                client_mac=visit.client_mac, device_id=visit.device_id, visit_guard=protocol_visit_guard(visit),
                visit_started_at=visit.started_at, snapshot_id=visit.initial_snapshot_id, binding_confirmed_at=None,
                **{key:None for family in ('dns','tls','quic') for key in (family+'_at',family+'_edge')},
                summary_state='pending', source_coverage='unknown', attribution_coverage='unknown',
                partial_reason='identity_unconfirmed', evaluated_at=now, finalized_at=None)
            if visit.device_id is not None and visit.initial_snapshot_id is not None and self.repository.protocol_bounds_clear(visit, visit.closed_at or now):
                # Retained positive knowledge survives raw retention/outage,
                # but never a Device/auth-snapshot/start identity correction.
                if old and all(old[key] == value[key] for key in ('site_id','client_mac','device_id','snapshot_id','visit_started_at')):
                    value['binding_confirmed_at'] = old['binding_confirmed_at']
                    for family in ('dns','tls','quic'):
                        if old[family+'_at'] is not None and start <= ni_timestamp(old[family+'_at'], canonical=True) < end:
                            value[family+'_at'], value[family+'_edge'] = old[family+'_at'], old[family+'_edge']
                value.update(summary_state='unavailable', source_coverage='unavailable', partial_reason='source_unavailable')
                try:
                    # Returns a materialized tuple; its source connection has
                    # already closed before ANY Visit writer acquisition.
                    source = self.protocol_reader.read_visit_protocol_snapshot(visit.site_id, visit.device_id,
                        visit.client_mac, ni_format_utc(start), ni_format_utc(end), evaluated_at=ni_format_utc(at),
                        deadline=QueryDeadline(deadline, self._monotonic))
                    if source['binding_state'] == 'authoritative' and source['bound_device_id'] == visit.device_id:
                        if value['binding_confirmed_at'] not in (None, source['binding_confirmed_at']):
                            for family in ('dns','tls','quic'):value[family+'_at'] = value[family+'_edge'] = None
                        value['binding_confirmed_at'] = source['binding_confirmed_at']
                        if len(source['facts']) > 3:
                            raise ValueError('Invalid bounded source')
                        for fact in source['facts']:
                            family = fact['source_event_family']
                            if family not in ('dns','tls','quic') or not start <= ni_timestamp(fact['event_at'], canonical=True) < end:
                                raise ValueError('Invalid protocol fact')
                            digest(fact['edge_id'])
                            previous = value[family+'_at']
                            if previous is None or fact['event_at'] > previous or fact['event_at'] == previous and fact['edge_id'] < value[family+'_edge']:
                                value[family+'_at'], value[family+'_edge'] = fact['event_at'], fact['edge_id']
                        value.update(summary_state='active' if visit.status == 'open' else 'partial',
                            source_coverage='bounded_partial',
                            attribution_coverage='current_available' if source['runtime_state'] == 'usable' else 'limited',
                            partial_reason='bounded_source' if visit.status == 'open' else 'late_unresolved')
                    else:
                        value.update(summary_state='pending', partial_reason='identity_unconfirmed')
                except Exception:
                    # Prior confirmed in-Visit values are partial historical
                    # knowledge, not fresh source availability/completeness.
                    value.update(summary_state='partial' if any(value[f+'_at'] for f in ('dns','tls','quic')) else 'unavailable',
                        source_coverage='unavailable', attribution_coverage='unknown', partial_reason='source_unavailable')
                if not any(value[f+'_at'] for f in ('dns','tls','quic')) and value['source_coverage'] == 'bounded_partial':
                    value.update(summary_state='pending', partial_reason='no_confirmed_observation')
            if visit.closed_at is not None and (at-end).total_seconds() >= 900:
                value.update(summary_state='finalized', finalized_at=now, partial_reason='grace_elapsed_partial')
            updates.append((visit, value))
        if self._stop_event.is_set() or self._monotonic() >= deadline:
            return 0
        return self.repository.put_protocol_summaries(updates, deadline=deadline, cancel_event=self._stop_event)

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
