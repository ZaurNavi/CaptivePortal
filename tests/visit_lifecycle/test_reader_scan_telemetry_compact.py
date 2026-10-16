"""QIO-01D: deterministic reporting only; real disposable Visit storage."""
from dataclasses import replace
import json
from pathlib import Path
import time
from types import SimpleNamespace
import uuid

import pytest

from app.visit_lifecycle import VisitRepository, VisitLifecycleService
from app.visit_lifecycle.models import VisitStorageError, VisitStorageCategory, VisitWriterContention
from app.visit_lifecycle import webhook_reader as module
from app.visit_lifecycle.webhook_reader import VisitLifecycleWebhookReader
from .conftest import make_request
from .test_webhook_reader import CapturingTelemetry, _append, _offline, _state


NOW = "2026-08-13T10:06:00.000Z"
EVENT = "visit.reader_scan_completed"


class Clock:
    def __init__(self):
        # The repository has its own real monotonic deadlines. Keep injected
        # scan deadlines valid without monkeypatching its clock or coordinator.
        self.base = time.monotonic() + 1000
        self.value = 0.0
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.base + self.value


def reports(rig):
    return [fields for event, _level, fields in rig.telemetry.events if event == EVENT]


def scan(rig, at):
    rig.clock.value = at
    return rig.reader.scan_once()


@pytest.fixture
def rig(visit_config, visit_repository, visit_service):
    config = replace(visit_config, reader_scan_telemetry_compact_enabled=True)
    clock, telemetry, health = Clock(), CapturingTelemetry(), []
    reader = VisitLifecycleWebhookReader(config=config, repository=visit_repository,
        service=visit_service, telemetry=telemetry, monotonic=clock,
        now_factory=lambda: NOW, health_callback=health.append)
    return SimpleNamespace(config=config, repository=visit_repository, service=visit_service,
        reader=reader, clock=clock, telemetry=telemetry, health=health)


def assert_report(report, reason, suppressed=0):
    assert set(report) == {"processed_line_count", "scan_complete", "duration_ms",
        "reader_report_schema_version", "report_reason", "suppressed_empty_scans", "scans_represented"}
    assert report["reader_report_schema_version"] == 2
    assert report["report_reason"] == reason
    assert type(report["suppressed_empty_scans"]) is int
    assert report["suppressed_empty_scans"] == suppressed
    assert report["scans_represented"] == suppressed + 1
    assert all(type(value) in {str, int, bool} for value in report.values())


@pytest.mark.parametrize("first", ["initial", "activity", "progress", "source_change", "incomplete"])
def test_first_scan_priority_clarification(rig, monkeypatch, first):
    if first == "activity":
        _append(rig.config.webhook_source, {"event": "unrelated"})
    elif first in {"source_change", "progress"}:
        Path(rig.config.webhook_source).write_bytes(b"")
    elif first == "incomplete":
        Path(rig.config.webhook_source).write_bytes(b'{"event":"partial"}')
    if first == "progress":
        def committed(**kwargs):
            kwargs["on_committed_progress"](1)
            return 1
        monkeypatch.setattr(rig.service, "retry_pending", committed)
    assert scan(rig, 0) is (first != "incomplete")
    assert len(reports(rig)) == 1
    assert_report(reports(rig)[0], first)


def test_activity_wins_simultaneous_progress_and_source_transition(rig, monkeypatch):
    _append(rig.config.webhook_source, {"event": "unrelated"})
    def committed(**kwargs):
        kwargs["on_committed_progress"](1)
        return 1
    monkeypatch.setattr(rig.service, "retry_pending", committed)
    assert scan(rig, 0)
    assert_report(reports(rig)[0], "activity")


def test_off_preserves_each_scan_exact_legacy_fields_including_incomplete(rig):
    rig.reader.config = replace(rig.config, reader_scan_telemetry_compact_enabled=False)
    for at in (0, 5, 59.999, 60, 61):
        assert scan(rig, at)
    Path(rig.config.webhook_source).write_bytes(b"partial")
    assert scan(rig, 65) is False
    assert len(reports(rig)) == 6
    for index, report in enumerate(reports(rig)):
        assert report == {"processed_line_count": 0, "scan_complete": index < 5, "duration_ms": 0}
    assert rig.health == [True] * 6


def test_monotonic_boundary_and_current_not_aggregate_fields(rig):
    for at in (0, 5, 59.999):
        assert scan(rig, at)
    assert len(reports(rig)) == 1
    assert scan(rig, 60)
    assert_report(reports(rig)[-1], "heartbeat", 2)
    assert reports(rig)[-1]["processed_line_count"] == 0
    assert reports(rig)[-1]["scan_complete"] is True
    assert reports(rig)[-1]["duration_ms"] == 0
    assert scan(rig, 61)
    assert len(reports(rig)) == 2 and rig.health == [True] * 5


def test_repeated_five_second_cadence(rig):
    for at in range(0, 121, 5):
        assert scan(rig, at)
    assert len(reports(rig)) == 3
    assert_report(reports(rig)[0], "initial")
    for report in reports(rig)[1:]:
        assert_report(report, "heartbeat", 11)
    assert sum(report["scans_represented"] for report in reports(rig)) == 25
    assert len(rig.health) == 25


def test_activity_always_immediate_then_idle_transition(rig):
    assert scan(rig, 0)
    assert scan(rig, 1)
    for at in (2, 3):
        _append(rig.config.webhook_source, {"event": "unrelated"})
        assert scan(rig, at)
        assert reports(rig)[-1]["processed_line_count"] == 1
        assert_report(reports(rig)[-1], "activity", 1 if at == 2 else 0)
    assert scan(rig, 4)
    assert_report(reports(rig)[-1], "idle_transition")
    assert scan(rig, 5)
    assert len(reports(rig)) == 4


@pytest.mark.parametrize("duration", [15, 20])
def test_long_scan_uses_completion_time_and_never_heartbeats_incomplete(rig, monkeypatch, duration):
    assert scan(rig, 0)
    assert scan(rig, 5)
    original = rig.reader._reconcile_missing
    def delayed(*args):
        original(*args)
        rig.clock.value += duration
    monkeypatch.setattr(rig.reader, "_reconcile_missing", delayed)
    assert scan(rig, 45) is (duration < 20)
    report = reports(rig)[-1]
    assert_report(report, "heartbeat" if duration < 20 else "incomplete", 1)
    assert report["duration_ms"] == duration * 1000
    monkeypatch.setattr(rig.reader, "_reconcile_missing", original)
    if duration == 20:
        assert scan(rig, 66)
        assert_report(reports(rig)[-1], "recovery")


def test_incomplete_every_time_then_complete_recovery(rig, monkeypatch):
    assert scan(rig, 0)
    original = rig.service.retry_pending
    def slow(**_kwargs):
        rig.clock.value += 20
        return 0
    monkeypatch.setattr(rig.service, "retry_pending", slow)
    assert scan(rig, 1) is False
    assert scan(rig, 22) is False
    assert [r["report_reason"] for r in reports(rig)] == ["initial", "incomplete", "incomplete"]
    monkeypatch.setattr(rig.service, "retry_pending", original)
    assert scan(rig, 43)
    assert_report(reports(rig)[-1], "recovery")


@pytest.mark.parametrize("failure", ["error", "deferred"])
def test_failure_or_deferral_then_recovery_excludes_failed_scans(rig, monkeypatch, failure):
    assert scan(rig, 0)
    assert scan(rig, 1)
    original = rig.repository.get_reader_states
    error = RuntimeError("disposable failure") if failure == "error" else VisitStorageError(
        VisitStorageCategory.BUSY, operation="reader_line", lock_wait_ms=250,
        contention_layer="coordinator", contention=VisitWriterContention(holder_operation="start"))
    def fail():
        raise error
    monkeypatch.setattr(rig.repository, "get_reader_states", fail)
    assert scan(rig, 2) is False
    assert scan(rig, 33) is False
    other = [event for event in rig.telemetry.events if event[0] != EVENT]
    assert len([event for event in other if event[0] == "visit.reader_scan_failed"]) == (2 if failure == "error" else 1)
    if failure == "deferred":
        assert len([event for event in other if event[0] == "visit.reader_scan_deferred"]) == 2
        assert other[-1][2]["reason"] == "writer_starvation"
    monkeypatch.setattr(rig.repository, "get_reader_states", original)
    assert scan(rig, 34)
    assert_report(reports(rig)[-1], "recovery", 1)
    assert rig.health == ([True, True, False, False, True] if failure == "error" else [True, True, False, True])


@pytest.mark.parametrize("signal", ["activity", "progress", "source_change"])
def test_meaningful_signal_wins_recovery_priority(rig, monkeypatch, signal):
    original = rig.repository.get_reader_states
    def fail():
        raise RuntimeError("disposable failure")
    monkeypatch.setattr(rig.repository, "get_reader_states", fail)
    assert scan(rig, 0) is False
    monkeypatch.setattr(rig.repository, "get_reader_states", original)
    if signal == "activity":
        _append(rig.config.webhook_source, {"event": "unrelated"})
    elif signal == "source_change":
        Path(rig.config.webhook_source).write_bytes(b"")
    else:
        def committed(**kwargs):
            kwargs["on_committed_progress"](1)
            return 1
        monkeypatch.setattr(rig.service, "retry_pending", committed)
    assert scan(rig, 1)
    assert_report(reports(rig)[-1], signal)


def test_zero_retry_callback_is_not_committed_progress(rig, monkeypatch):
    assert scan(rig, 0)
    def no_progress(**kwargs):
        kwargs["on_committed_progress"](0)
        return 0
    monkeypatch.setattr(rig.service, "retry_pending", no_progress)
    assert scan(rig, 1)
    assert len(reports(rig)) == 1
    assert rig.reader._last_durable_progress_at is None


def test_partial_committed_retry_then_error_is_never_a_completed_scan(rig, monkeypatch):
    assert scan(rig, 0)
    assert scan(rig, 1)
    original = rig.service.retry_pending
    def partial(**kwargs):
        kwargs["on_committed_progress"](1)
        raise RuntimeError("failure after committed chunk")
    monkeypatch.setattr(rig.service, "retry_pending", partial)
    assert scan(rig, 2) is False
    assert len(reports(rig)) == 1
    monkeypatch.setattr(rig.service, "retry_pending", original)
    assert scan(rig, 3)
    assert_report(reports(rig)[-1], "recovery", 1)
    assert rig.reader._last_durable_progress_at == rig.clock.base + 2


@pytest.mark.parametrize("change", ["missing", "reappeared", "retired_reused", "retired_deleted", "path", "truncated", "checkpoint"])
def test_source_transitions_with_zero_lines_are_immediate(rig, monkeypatch, change):
    path = Path(rig.config.webhook_source)
    monkeypatch.setattr(module, "_source_identity", lambda _stat: "fixed:source")
    seed = Path(str(path) + ".1") if change in {"retired_reused", "retired_deleted"} else path
    if change == "truncated":
        _append(seed, {"event": "unrelated"})
    else:
        seed.write_bytes(b"")
    assert scan(rig, 0)
    assert scan(rig, 1)
    if change == "missing":
        path.unlink()
    elif change == "reappeared":
        path.unlink()
        assert scan(rig, 2)
        path.write_bytes(b"")
    elif change in {"retired_reused", "retired_deleted"}:
        seed.unlink()
        if change == "retired_reused":
            path.write_bytes(b"")
    elif change == "path":
        path.rename(str(path) + ".1")
    elif change == "truncated":
        path.write_bytes(b"")
    else:
        monkeypatch.setattr(module, "_checkpoint_matches", lambda _state, _checkpoint: False)
    count = len(reports(rig))
    assert scan(rig, 3)
    assert len(reports(rig)) == count + 1
    assert reports(rig)[-1]["processed_line_count"] == 0
    assert reports(rig)[-1]["report_reason"] == "source_change"
    source_events = [event for event in rig.telemetry.events if event[0] in {
        "visit.reader_source_missing", "visit.reader_source_restarted"}]
    if change in {"missing", "reappeared", "retired_reused", "truncated", "checkpoint"}:
        assert source_events and all(event[1] == "warning" for event in source_events)


@pytest.mark.parametrize("line", ['{invalid}\n', '{"value":NaN}\n', '[]\n', 'x' * 600 + '\n'])
def test_invalid_journal_zero_outcomes_never_suppressed(rig, line):
    rig.reader.config = replace(rig.config, max_line_bytes=512)
    assert scan(rig, 0)
    assert scan(rig, 1)
    _append(rig.config.webhook_source, line)
    assert scan(rig, 2)
    assert_report(reports(rig)[-1], "activity", 1)
    assert reports(rig)[-1]["processed_line_count"] == 1
    warnings = [item for item in rig.telemetry.events if item[0] == "visit.offline_invalid"]
    assert len(warnings) == 1 and warnings[0][1] == "warning"
    with rig.repository._connect(readonly=True) as db:
        assert db.execute("SELECT COUNT(*) FROM visit_source_events").fetchone()[0] == 0
    assert _state(rig.repository).source_offset == len(line.encode())


def test_nonregular_input_is_conservatively_reported(rig):
    Path(rig.config.webhook_source).mkdir()
    assert scan(rig, 0)
    assert scan(rig, 1)
    assert [report["report_reason"] for report in reports(rig)] == ["source_change"] * 2


@pytest.mark.parametrize("failure", ["false", "raise"])
def test_completed_emitter_unavailable_resets_on_attempt_without_health_change(rig, failure):
    def unavailable(event, level="info", **fields):
        rig.telemetry.events.append((event, level, fields))
        if failure == "raise":
            raise RuntimeError("unavailable telemetry")
        return False
    rig.telemetry.emit = unavailable
    assert scan(rig, 0)
    assert scan(rig, 5)
    assert scan(rig, 60)
    assert_report(reports(rig)[-1], "heartbeat", 1)
    assert rig.health == [True] * 3
    assert not [event for event in rig.telemetry.events if event[0] == "visit.reader_scan_failed"]


def test_clock_regression_emits_and_reanchors(rig):
    assert scan(rig, 0)
    assert scan(rig, 5)
    assert scan(rig, -1)
    assert_report(reports(rig)[-1], "heartbeat", 1)
    assert scan(rig, 0)
    assert scan(rig, 59)
    assert_report(reports(rig)[-1], "heartbeat", 1)


def test_clock_regression_after_suppressed_scan_not_just_after_report(rig):
    assert scan(rig, 0)
    assert scan(rig, 55)
    assert scan(rig, 10)
    assert_report(reports(rig)[-1], "heartbeat", 1)


@pytest.mark.parametrize("invalid_previous", [float("nan"), float("inf"), float("-inf")])
def test_invalid_heartbeat_delta_is_fail_safe(rig, invalid_previous):
    assert scan(rig, 0)
    rig.reader._last_completed_report_at = invalid_previous
    assert scan(rig, 1)
    assert_report(reports(rig)[-1], "heartbeat")
    assert scan(rig, 2)
    assert len(reports(rig)) == 2


def test_stop_does_not_flush_or_fabricate_heartbeat_and_restart_resets(rig, monkeypatch):
    class Thread:
        def __init__(self, **kwargs):
            assert kwargs["name"] == "visit_webhook_reader"
            self.alive = False
        def start(self):
            self.alive = True
        def is_alive(self):
            return self.alive
        def join(self, _timeout):
            self.alive = False
    monkeypatch.setattr(module.threading, "Thread", Thread)
    assert rig.reader.start()
    assert not rig.reader.start()
    assert scan(rig, 0)
    assert scan(rig, 5)
    before = list(rig.telemetry.events)
    assert rig.reader.stop(1)
    rig.clock.value = 100
    assert rig.telemetry.events == before
    assert rig.reader.start()
    assert scan(rig, 101)
    assert_report(reports(rig)[-1], "initial")
    assert rig.reader.stop(1)


def test_stopping_cancelled_storage_cannot_create_success(rig, monkeypatch):
    assert scan(rig, 0)
    rig.reader._stop_event.set()
    def cancelled():
        raise VisitStorageError(VisitStorageCategory.UNAVAILABLE)
    monkeypatch.setattr(rig.repository, "get_reader_states", cancelled)
    assert scan(rig, 100) is False
    assert len(reports(rig)) == 1
    assert rig.health == [True]


def test_real_committed_pending_retry_reports_progress_with_zero_lines(rig, monkeypatch):
    rig.reader._now = lambda: "2026-08-13T10:00:01.000Z"
    _append(rig.config.webhook_source, _offline("pending:compact", reported_connected_seconds=300))
    assert scan(rig, 0)
    Path(rig.config.webhook_source).unlink()
    assert scan(rig, 1)  # Account for the missing-source transition first.
    monkeypatch.setattr("app.visit_lifecycle.service.utc_now", lambda: "2026-08-13T10:00:02.000Z")
    opened = rig.service.submit_authorized(make_request())
    rig.reader._now = lambda: "2026-08-13T10:00:03.000Z"
    assert scan(rig, 2)
    assert_report(reports(rig)[-1], "progress")
    assert reports(rig)[-1]["processed_line_count"] == 0
    assert rig.repository.get_visit("site-a", opened.visit_id).status == "closed"


def test_off_on_identical_sql_workflow_rows_checkpoints_and_callbacks(visit_config, tmp_path, monkeypatch):
    monkeypatch.setattr(module, "_source_identity", lambda _stat: "fixed:source")
    monkeypatch.setattr("app.visit_lifecycle.repository.uuid.uuid4", lambda: uuid.UUID(int=42))
    monkeypatch.setattr("app.visit_lifecycle.service.utc_now", lambda: NOW)
    results = []
    for enabled in (False, True):
        root = tmp_path / str(enabled)
        root.mkdir()
        config = replace(visit_config, db_path=str(root / "visits.sqlite3"),
            webhook_source=str(root / "journal.log"), reader_scan_telemetry_compact_enabled=enabled)
        repository = VisitRepository(config)
        assert repository.initialize()
        telemetry, clock, health, sql, order = CapturingTelemetry(), Clock(), [], [], []
        service = VisitLifecycleService(repository, telemetry)
        original_connect = repository._connect
        def connect(*args, **kwargs):
            connection = original_connect(*args, **kwargs)
            connection.set_trace_callback(lambda statement: sql.append(statement.replace(str(root), "ROOT")))
            return connection
        repository._connect = connect
        reader = VisitLifecycleWebhookReader(config=config, repository=repository, service=service,
            telemetry=telemetry, monotonic=clock, now_factory=lambda: NOW, health_callback=health.append)
        for owner, name in ((reader, "_discover_sources"), (reader, "_process_source"),
                            (reader, "_reconcile_missing"), (service, "retry_pending")):
            original = getattr(owner, name)
            def observed(*args, _name=name, _original=original, **kwargs):
                order.append(_name)
                if _name == "retry_pending":
                    callback = kwargs["on_committed_progress"]
                    def committed(count):
                        order.append(("committed_progress", count))
                        callback(count)
                    kwargs["on_committed_progress"] = committed
                return _original(*args, **kwargs)
            setattr(owner, name, observed)
        _append(config.webhook_source, _offline("event:equivalence", reported_connected_seconds=300))
        returns = []
        for at in (0, 5, 10, 60, 70):
            clock.value = at
            returns.append(reader.scan_once())
            if at == 0:
                # The first scan persists pending evidence; the next scan has
                # zero new lines and a real committed retry callback.
                service.submit_authorized(make_request(auth_session_id=str(uuid.UUID(int=24))))
        # Compare complete durable state and the exact SQL stream, not just row counts.
        with original_connect(readonly=True) as db:
            tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            rows = {name: [tuple(value.replace(str(root), "ROOT") if isinstance(value, str) else value
                                for value in row) for row in db.execute('SELECT * FROM "' + name + '"')]
                    for name in tables}
        other_events = [event for event in telemetry.events if event[0] != EVENT]
        results.append((returns, health, order, sql, rows, other_events, clock.calls))
    assert results[0] == results[1]
    assert results[0][0] == [True] * 5
    assert results[0][1] == [True] * 5
    assert ("committed_progress", 1) in results[0][2]
