from __future__ import annotations

import threading
import time
import json
import os
from dataclasses import replace

from app.visit_lifecycle import VisitLifecycleService
from app.visit_lifecycle.repository import (
    WRITE_OPERATION_READER,
    WRITE_OPERATION_START,
    VisitRepository,
    _expected_v2_signature,
    _schema_signature,
)
from app.visit_lifecycle.reconciliation import VisitLinkReconciler
from app.visit_lifecycle.start_sink import LocalVisitStartSubmitter
from app.visit_lifecycle.webhook_reader import VisitLifecycleWebhookReader

from .conftest import make_request


class CapturingTelemetry:
    def __init__(self):
        self.events = []
        self._lock = threading.Lock()

    def emit(self, event, level="info", **fields):
        with self._lock:
            self.events.append((event, level, fields))
        return True


def _wait_until(predicate, timeout=1.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


def test_start_waits_past_old_threshold_and_succeeds_once(visit_config):
    config = replace(
        visit_config,
        start_writer_slot_wait_ms=750,
        start_total_budget_ms=2_000,
    )
    repository = VisitRepository(config)
    repository.initialize()
    telemetry = CapturingTelemetry()
    service = VisitLifecycleService(repository, telemetry)
    sink = LocalVisitStartSubmitter(
        service,
        telemetry,
        max_attempts=config.start_max_attempts,
        total_budget_ms=config.start_total_budget_ms,
    )
    holder_ready = threading.Event()
    release_holder = threading.Event()
    result = []

    def hold_background():
        with repository._bounded_write(WRITE_OPERATION_READER):  # noqa: SLF001
            holder_ready.set()
            release_holder.wait(2)

    holder = threading.Thread(target=hold_background)
    holder.start()
    assert holder_ready.wait(1)
    starter = threading.Thread(
        target=lambda: result.append(sink.submit_authorized(make_request()))
    )
    starter.start()
    assert _wait_until(
        lambda: repository._write_coordinator._waiting_counts()[0] == 1  # noqa: SLF001
    )
    time.sleep(0.275)
    release_holder.set()
    starter.join(2)
    holder.join(2)

    assert [item.status for item in result] == ["opened"]
    assert repository.authorization_count(result[0].visit_id) == 1
    assert not [item for item in telemetry.events if item[0] == "visit.storage_error"]


def test_waiting_start_precedes_second_background_writer(visit_repository):
    order = []
    holder_ready = threading.Event()
    release_holder = threading.Event()

    def first_background():
        with visit_repository._bounded_write(WRITE_OPERATION_READER):  # noqa: SLF001
            holder_ready.set()
            release_holder.wait(2)

    def foreground():
        with visit_repository._bounded_write(WRITE_OPERATION_START):  # noqa: SLF001
            order.append("start")

    def second_background():
        with visit_repository._bounded_write(WRITE_OPERATION_READER):  # noqa: SLF001
            order.append("background")

    holder = threading.Thread(target=first_background)
    holder.start()
    assert holder_ready.wait(1)
    start_thread = threading.Thread(target=foreground)
    start_thread.start()
    assert _wait_until(
        lambda: visit_repository._write_coordinator._waiting_counts() == (1, 0)  # noqa: SLF001
    )
    background_thread = threading.Thread(target=second_background)
    background_thread.start()
    assert _wait_until(
        lambda: visit_repository._write_coordinator._waiting_counts() == (1, 1)  # noqa: SLF001
    )
    release_holder.set()
    for thread in (holder, start_thread, background_thread):
        thread.join(2)
        assert not thread.is_alive()
    assert order == ["start", "background"]


def test_actual_writer_hold_exhausts_budget_once_and_remains_fail_open(
    visit_config,
):
    config = replace(
        visit_config,
        start_writer_slot_wait_ms=750,
        start_total_budget_ms=300,
    )
    repository = VisitRepository(config)
    repository.initialize()
    telemetry = CapturingTelemetry()
    service = VisitLifecycleService(repository, telemetry)
    sink = LocalVisitStartSubmitter(
        service,
        telemetry,
        max_attempts=config.start_max_attempts,
        total_budget_ms=config.start_total_budget_ms,
    )
    holder_ready = threading.Event()
    release_holder = threading.Event()

    def hold_background():
        with repository._bounded_write(WRITE_OPERATION_READER):  # noqa: SLF001
            holder_ready.set()
            release_holder.wait(2)

    holder = threading.Thread(target=hold_background)
    holder.start()
    assert holder_ready.wait(1)
    started = time.monotonic()
    outcome = sink.submit_authorized(make_request())
    elapsed = time.monotonic() - started
    release_holder.set()
    holder.join(1)

    assert outcome.status == "unavailable"
    assert outcome.storage_category == "busy"
    assert 0.25 <= elapsed < 0.75
    errors = [
        item for item in telemetry.events if item[0] == "visit.storage_error"
    ]
    assert len(errors) == 1
    assert errors[0][2]["operation"] == "start"
    assert errors[0][2]["retry_exhausted"] is True
    assert errors[0][2]["lock_wait_ms"] >= 250


def test_ambiguous_commit_retry_is_idempotent(visit_repository, monkeypatch):
    telemetry = CapturingTelemetry()
    service = VisitLifecycleService(visit_repository, telemetry)
    original = visit_repository.create_or_reuse_start
    calls = 0

    def ambiguous(*args, **kwargs):
        nonlocal calls
        calls += 1
        outcome = original(*args, **kwargs)
        if calls == 1:
            from app.visit_lifecycle import VisitStorageCategory, VisitStorageError

            raise VisitStorageError(VisitStorageCategory.BUSY)
        return outcome

    monkeypatch.setattr(visit_repository, "create_or_reuse_start", ambiguous)
    sink = LocalVisitStartSubmitter(service, telemetry, total_budget_ms=500)
    outcome = sink.submit_authorized(make_request())

    assert outcome.status == "duplicate"
    assert visit_repository.authorization_count(outcome.visit_id) == 1
    with visit_repository._connect(readonly=True) as connection:  # noqa: SLF001
        assert connection.execute("SELECT COUNT(*) FROM visits").fetchone()[0] == 1
    names = [item[0] for item in telemetry.events]
    assert names.count("visit.start_retry_recovered") == 1
    assert names.count("visit.opened") == 0
    assert names.count("visit.start_reused") == 0
    assert names.count("visit.authorization_attached") == 0
    assert names.count("visit.storage_error") == 0


def test_shutdown_interrupts_waiting_start_without_deadlock(visit_repository):
    telemetry = CapturingTelemetry()
    service = VisitLifecycleService(visit_repository, telemetry)
    sink = LocalVisitStartSubmitter(service, telemetry, total_budget_ms=2_000)
    holder_ready = threading.Event()
    release_holder = threading.Event()
    result = []

    def hold_background():
        with visit_repository._bounded_write(WRITE_OPERATION_READER):  # noqa: SLF001
            holder_ready.set()
            release_holder.wait(2)

    holder = threading.Thread(target=hold_background)
    holder.start()
    assert holder_ready.wait(1)
    starter = threading.Thread(
        target=lambda: result.append(sink.submit_authorized(make_request()))
    )
    starter.start()
    assert _wait_until(
        lambda: visit_repository._write_coordinator._waiting_counts()[0] == 1  # noqa: SLF001
    )
    sink.stop_accepting()
    starter.join(1)
    assert not starter.is_alive()
    assert result[0].status == "unavailable"
    assert visit_repository._write_coordinator._waiting_counts() == (0, 0)  # noqa: SLF001
    assert sink.wait_for_idle(0.1) is True
    assert sink.submit_authorized(make_request()).status == "shutting_down"
    release_holder.set()
    holder.join(1)


def test_concurrent_start_reader_reconciliation_series_preserves_invariants(
    visit_config,
):
    repository = VisitRepository(visit_config)
    repository.initialize()
    telemetry = CapturingTelemetry()
    service = VisitLifecycleService(repository, telemetry)
    sink = LocalVisitStartSubmitter(service, telemetry)
    requests = [make_request() for _ in range(8)]
    with open(
        visit_config.webhook_source,
        "w",
        encoding="utf-8",
        newline="",
    ) as output:
        for index in range(3):
            output.write(json.dumps({
                "event": "omada.client_online",
                "normalized_event_id": f"online:{index}",
            }) + "\n")

    reader = VisitLifecycleWebhookReader(
        config=visit_config,
        repository=repository,
        service=service,
        telemetry=telemetry,
    )

    class EmptyRegistry:
        def get_device_by_mac(self, _mac):
            return None

        def get_snapshot_by_auth_session(
            self,
            _session_id,
            *,
            site_id,
            client_mac,
        ):
            return None

    reconciler = VisitLinkReconciler(
        config=visit_config,
        repository=repository,
        registry_read_service=EmptyRegistry(),
        telemetry=telemetry,
    )
    outcomes = []
    start_threads = [
        threading.Thread(
            target=lambda request=request: outcomes.append(
                sink.submit_authorized(request)
            )
        )
        for request in requests
    ]
    background_threads = [
        threading.Thread(target=reader.scan_once),
        threading.Thread(target=reconciler.run_once),
    ]
    for thread in background_threads + start_threads:
        thread.start()
    for thread in background_threads + start_threads:
        thread.join(15)
        assert not thread.is_alive()

    for _attempt in range(3):
        if reader.scan_once():
            break
    else:
        raise AssertionError("reader did not reach the final checkpoint")
    assert len(outcomes) == len(requests)
    assert all(item.status in {"opened", "reused"} for item in outcomes)
    visit_ids = {item.visit_id for item in outcomes}
    assert len(visit_ids) == 1
    visit_id = next(iter(visit_ids))
    assert repository.authorization_count(visit_id) == len(requests)
    states = repository.get_reader_states()
    assert len(states) == 1
    assert next(iter(states.values())).source_offset == os.path.getsize(
        visit_config.webhook_source
    )
    with repository._connect(readonly=True) as connection:  # noqa: SLF001
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert _schema_signature(connection) == _expected_v2_signature()
