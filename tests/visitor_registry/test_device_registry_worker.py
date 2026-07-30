from __future__ import annotations

import sqlite3
import threading
import time

import pytest

from app.visitor_registry.registry_models import (
    RegistryConfig,
    RegistrySchemaError,
    ScanResult,
)
from app.visitor_registry.registry_worker import (
    DisabledVisitorRegistry,
    UnavailableVisitorRegistry,
    VisitorRegistryWorker,
    _sqlite_category,
    create_visitor_registry,
)


class CaptureTelemetry:
    def __init__(self):
        self.events = []
        self.cleared = 0

    def emit(self, event, level="info", **fields):
        self.events.append({
            "event": event,
            "level": level,
            **fields,
        })
        return True

    def emit_once(self, event, level="warning", **fields):
        return self.emit(event, level, **fields)

    def clear_rate_limits(self):
        self.cleared += 1


class FakeService:
    def __init__(self):
        self.index = 0

    def now_iso(self):
        self.index += 1
        return f"2026-07-30T11:00:{self.index:02d}.000Z"


class FakeRepository:
    def __init__(self, config, *, backfill=False):
        self.config = config
        self.backfill = backfill
        self.states = []
        self.backfill_completed_at = None
        self.successful_scan_at = None
        self.health_error = None
        self.full_audit_calls = 0

    def run_full_audit(self):
        self.full_audit_calls += 1

    def initial_backfill_completed(self):
        return self.backfill

    def mark_backfill_completed(self, now):
        self.backfill = True
        self.backfill_completed_at = now

    def mark_successful_scan(self, now):
        self.successful_scan_at = now

    def set_state(self, state, reason, now):
        previous = (
            self.states[-1][0:2] if self.states else (None, None)
        )
        changed = previous != (state, reason)
        if changed:
            self.states.append((state, reason, now))
        return changed

    def get_status(self, configured_enabled):
        class Status:
            registry_state = (
                self.states[-1][0] if self.states else "initializing"
            )

        return Status()

    def validate_runtime_health(self):
        if self.health_error is not None:
            raise self.health_error


class FakeReader:
    def __init__(self, results):
        self.results = list(results)
        self.calls = 0

    def scan(self, *, should_stop):
        self.calls += 1
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


def worker_config() -> RegistryConfig:
    return RegistryConfig(
        enabled=True,
        db_path="/private/visitor_registry.sqlite3",
        source_log_path="/private/visitor_snapshots.log",
        source_backup_count=20,
        timezone_name="Asia/Baku",
        scan_interval_seconds=0.01,
        shutdown_timeout_seconds=0.05,
        max_line_bytes=4_194_304,
    )


def make_worker(results, *, backfill=False):
    telemetry = CaptureTelemetry()
    repository = FakeRepository(worker_config(), backfill=backfill)
    reader = FakeReader(results)
    worker = VisitorRegistryWorker(
        repository=repository,
        service=FakeService(),
        reader=reader,
        telemetry=telemetry,
    )
    return worker, repository, reader, telemetry


def test_successful_initial_scan_completes_backfill_and_becomes_ready():
    worker, repository, reader, telemetry = make_worker([
        ScanResult(True),
    ])

    worker.run_once()

    assert reader.calls == 1
    assert repository.backfill
    assert repository.backfill_completed_at is not None
    assert repository.successful_scan_at is not None
    assert [state[0] for state in repository.states] == [
        "initializing",
        "backfilling",
        "ready",
    ]
    assert [event["event"] for event in telemetry.events] == [
        "visitor_registry_state_changed",
        "visitor_registry_integrity_audit_completed",
        "visitor_registry_backfill_started",
        "visitor_registry_state_changed",
        "visitor_registry_backfill_completed",
        "visitor_registry_state_changed",
    ]


def test_incomplete_scan_keeps_backfill_open_and_marks_degraded():
    worker, repository, _, telemetry = make_worker([
        ScanResult(False, reason="old_inode_missing"),
    ])

    worker.run_once()

    assert not repository.backfill
    assert repository.backfill_completed_at is None
    assert repository.states[-1][0:2] == (
        "degraded",
        "old_inode_missing",
    )
    assert any(
        item["event"] == "visitor_registry_scan_incomplete"
        for item in telemetry.events
    )


def test_schema_error_stops_worker_as_unavailable():
    worker, repository, _, telemetry = make_worker([
        RegistrySchemaError("future schema"),
    ])

    worker.run_once()

    assert not worker.available
    assert repository.states[-1][0] == "unavailable"
    assert telemetry.events[-1]["event"] == (
        "visitor_registry_unavailable"
    )


def test_failed_background_audit_prevents_journal_processing():
    worker, repository, reader, telemetry = make_worker([
        ScanResult(True),
    ])

    def fail_audit():
        raise RegistrySchemaError("count mismatch")

    repository.run_full_audit = fail_audit

    worker.run_once()

    assert reader.calls == 0
    assert not worker.available
    assert repository.states[-1][0] == "unavailable"
    assert telemetry.events[-1]["event"] == (
        "visitor_registry_unavailable"
    )


def test_io_error_is_unavailable_when_database_health_cannot_be_proved(
    monkeypatch,
):
    error = sqlite3.OperationalError("disk I/O error")
    worker, repository, _, telemetry = make_worker([error])
    repository.health_error = sqlite3.DatabaseError("not readable")
    monkeypatch.setattr(
        "app.visitor_registry.registry_worker._sqlite_category",
        lambda actual: "io_error",
    )

    worker.run_once()

    assert not worker.available
    assert repository.states[-1][0] == "unavailable"
    assert telemetry.events[-1]["level"] == "critical"


def test_recoverable_io_error_is_degraded_after_successful_health_check(
    monkeypatch,
):
    error = sqlite3.OperationalError("temporary disk write failure")
    worker, repository, _, _ = make_worker([error])
    monkeypatch.setattr(
        "app.visitor_registry.registry_worker._sqlite_category",
        lambda actual: "io_error",
    )

    worker.run_once()

    assert worker.available
    assert repository.states[-1][0] == "degraded"


def test_shutdown_timeout_is_bounded_and_emitted_once():
    worker, _, _, telemetry = make_worker([], backfill=True)
    release = threading.Event()

    def blocked():
        release.wait(1)

    thread = threading.Thread(target=blocked, daemon=True)
    thread.start()
    worker._thread = thread

    started = time.monotonic()
    worker.stop(0.01, final_scan=False)
    elapsed = time.monotonic() - started
    assert worker._stop_completed is False
    assert thread.is_alive()
    assert not any(
        item["event"] == "visitor_registry_stopped"
        for item in telemetry.events
    )

    release.set()
    thread.join(1)
    worker.stop(0.1, final_scan=False)

    assert elapsed < 0.2
    assert worker._stop_completed is True
    assert [
        item["event"] for item in telemetry.events
    ].count("visitor_registry_shutdown_timeout") == 1
    assert [
        item["event"] for item in telemetry.events
    ].count("visitor_registry_stopped") == 1


def test_shutdown_during_full_audit_cannot_overwrite_stopping_state():
    worker, repository, reader, _ = make_worker(
        [ScanResult(True)],
        backfill=True,
    )
    audit_started = threading.Event()
    release_audit = threading.Event()

    def blocking_audit():
        repository.full_audit_calls += 1
        audit_started.set()
        release_audit.wait(1)

    repository.run_full_audit = blocking_audit
    assert worker.start() is True
    assert audit_started.wait(0.2)

    worker.stop(0.01, final_scan=False)
    assert worker._stop_completed is False
    stopping_index = len(repository.states) - 1
    assert repository.states[stopping_index][0] == "stopping"

    release_audit.set()
    worker.stop(0.2, final_scan=False)

    assert worker._stop_completed is True
    assert reader.calls == 0
    assert all(
        state[0] not in {"ready", "degraded", "backfilling"}
        for state in repository.states[stopping_index + 1:]
    )


def test_reader_shutdown_result_is_not_reported_as_degraded():
    worker, repository, reader, telemetry = make_worker(
        [ScanResult(False, reason="shutdown")],
        backfill=True,
    )

    worker.run_once()

    assert reader.calls == 1
    assert all(state[0] != "degraded" for state in repository.states)
    assert not any(
        item["event"] == "visitor_registry_scan_incomplete"
        for item in telemetry.events
    )


def test_stop_with_final_scan_is_fully_idempotent():
    worker, repository, reader, telemetry = make_worker(
        [ScanResult(True)],
        backfill=True,
    )

    worker.stop(0.05, final_scan=True)
    worker.stop(0.05, final_scan=True)

    assert repository.full_audit_calls == 1
    assert reader.calls == 1
    assert [
        item["event"] for item in telemetry.events
    ].count("visitor_registry_stopped") == 1
    assert [
        state[0] for state in repository.states
    ].count("stopping") == 1


def test_long_full_audit_runs_in_worker_and_does_not_block_start():
    worker, repository, reader, _ = make_worker(
        [ScanResult(True)],
        backfill=True,
    )
    audit_started = threading.Event()
    release_audit = threading.Event()

    def blocking_audit():
        repository.full_audit_calls += 1
        audit_started.set()
        release_audit.wait(1)

    repository.run_full_audit = blocking_audit

    started = time.monotonic()
    assert worker.start() is True
    elapsed = time.monotonic() - started
    assert audit_started.wait(0.2)
    assert elapsed < 0.2
    assert reader.calls == 0

    release_audit.set()
    deadline = time.monotonic() + 1
    while reader.calls == 0 and time.monotonic() < deadline:
        time.sleep(0.005)
    worker.stop(0.2, final_scan=False)

    assert repository.full_audit_calls == 1
    assert reader.calls == 1


@pytest.mark.parametrize("previous_state", ["ready", "stopping"])
def test_start_exposes_initializing_until_full_audit_finishes(
    previous_state,
):
    worker, repository, reader, _ = make_worker(
        [ScanResult(True)],
        backfill=True,
    )
    repository.states.append((
        previous_state,
        None,
        "2026-07-30T10:59:59.000Z",
    ))
    audit_started = threading.Event()
    release_audit = threading.Event()

    def blocking_audit():
        repository.full_audit_calls += 1
        audit_started.set()
        release_audit.wait(1)

    repository.run_full_audit = blocking_audit

    assert worker.start() is True
    assert repository.states[-1][0:2] == (
        "initializing",
        "full_audit_pending",
    )
    assert audit_started.wait(0.2)
    assert reader.calls == 0

    release_audit.set()
    deadline = time.monotonic() + 1
    while reader.calls == 0 and time.monotonic() < deadline:
        time.sleep(0.005)
    worker.stop(0.2, final_scan=False)

    assert reader.calls == 1
    assert "ready" in [state[0] for state in repository.states]


def test_disabled_and_invalid_configuration_remain_fail_open():
    disabled = create_visitor_registry({
        "visitor_registry_enabled": "false",
    })
    invalid = create_visitor_registry({
        "visitor_registry_enabled": "true",
        "visitor_registry_db_path": "",
    })

    assert isinstance(disabled, DisabledVisitorRegistry)
    assert disabled.start() is False
    assert isinstance(invalid, UnavailableVisitorRegistry)
    assert invalid.start() is False


def _sqlite_error(code):
    error = sqlite3.OperationalError(f"sqlite code {code}")
    error.sqlite_errorcode = code
    return error


def test_sqlite_primary_error_classification():
    assert _sqlite_category(sqlite3.OperationalError("plain")) == (
        "degraded"
    )
    assert _sqlite_category(ValueError("not sqlite")) == "degraded"
    assert _sqlite_category(
        _sqlite_error(sqlite3.SQLITE_BUSY)
    ) == "locked"
    assert _sqlite_category(
        _sqlite_error(sqlite3.SQLITE_LOCKED)
    ) == "locked"
    assert _sqlite_category(
        _sqlite_error(sqlite3.SQLITE_FULL)
    ) == "degraded"
    assert _sqlite_category(
        _sqlite_error(sqlite3.SQLITE_IOERR)
    ) == "io_error"
    assert _sqlite_category(
        _sqlite_error(sqlite3.SQLITE_CORRUPT)
    ) == "unavailable"
    assert _sqlite_category(
        _sqlite_error(sqlite3.SQLITE_NOTADB)
    ) == "unavailable"
    assert _sqlite_category(
        _sqlite_error(sqlite3.SQLITE_READONLY)
    ) == "unavailable"
    assert _sqlite_category(
        _sqlite_error(sqlite3.SQLITE_CANTOPEN)
    ) == "unavailable"
