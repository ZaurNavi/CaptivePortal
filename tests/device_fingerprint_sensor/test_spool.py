from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from app.device_fingerprint_sensor.models import NormalizedEvent, SensorSpoolError
from app.device_fingerprint_sensor.spool import SensorSpool

UTC = timezone.utc


class Clock:
    value = datetime(2026, 9, 14, tzinfo=UTC)
    def __call__(self): return self.value


def event(index, endpoint="evidence", observed=None):
    identity = f"00000000-0000-4000-8000-{index:012d}"
    return NormalizedEvent(endpoint, identity, "dhcp", observed or "2026-09-14T00:00:00.000Z", {"id": index})


def spool(tmp_path, clock, **changes):
    value = SensorSpool(str(tmp_path / "spool.sqlite3"), total_budget_bytes=changes.get("budget", 10_000_000), main_db_max_bytes=5_000_000, max_events=changes.get("max_events", 100), now=clock)
    value.initialize(); return value


def test_spool_is_delete_journal_bounded_and_endpoint_homogeneous(tmp_path):
    clock = Clock(); value = spool(tmp_path, clock)
    assert value.connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    assert value.connection.execute("PRAGMA user_version").fetchone()[0] == 1
    value.enqueue([event(1), event(2, "source_health")])
    endpoint, rows = value.batch(100)
    assert endpoint == "evidence" and len(rows) == 1
    value.acknowledge([rows[0][0]])
    assert value.batch(100)[0] == "source_health"


def test_stable_id_is_idempotent_and_stale_rows_are_dropped(tmp_path):
    clock = Clock(); value = spool(tmp_path, clock)
    value.enqueue([event(1), event(1)])
    assert value.metrics()["rows"] == 1
    value.enqueue([event(2, observed="2026-09-12T00:00:00.000Z")])
    assert value.metrics()["rows"] == 1
    assert value.stale_dropped == 1


def test_row_cap_evicts_oldest_evidence_not_health(tmp_path):
    clock = Clock(); value = spool(tmp_path, clock, max_events=2)
    value.enqueue([event(1, "source_health"), event(2)])
    value.enqueue([event(3)])
    assert value.metrics()["rows"] == 2
    documents = [row[1] for row in value.batch(100)[1]]
    assert documents[0]["id"] == 1


def test_transaction_is_limited_to_100(tmp_path):
    clock = Clock(); value = spool(tmp_path, clock, max_events=1000)
    with pytest.raises(SensorSpoolError):
        value.enqueue([event(index) for index in range(101)])


def test_physical_fingerprint_contains_no_raw_packet_material(tmp_path):
    clock = Clock(); value = spool(tmp_path, clock)
    value.enqueue([event(1)])
    raw = Path(value.path).read_bytes()
    assert b"raw_packet" not in raw and b"private.example" not in raw


def test_batch_purges_more_than_one_chunk_without_delivering_stale_rows(tmp_path):
    clock = Clock(); value = spool(tmp_path, clock, max_events=200)
    value.enqueue([event(index) for index in range(100)])
    value.enqueue([event(index) for index in range(100, 150)])
    clock.value += timedelta(days=2)
    value.capacity_blocked = True
    deletions = []
    original = value._purge_stale

    def measured_purge():
        deleted = original()
        deletions.append(deleted)
        return deleted

    value._purge_stale = measured_purge
    value.enqueue([event(999, observed="2026-09-16T00:00:00.000Z")])
    endpoint, rows = value.batch(100)
    assert endpoint == "evidence"
    assert [document["id"] for _sequence, document in rows] == [999]
    assert deletions == [100, 50]
    assert all(deleted <= 100 for deleted in deletions)
    assert value.stale_dropped == 150
    assert value.capacity_blocked is False


def _qio05_spool(tmp_path, *, gate, max_events=1000):
    value = SensorSpool(str(tmp_path / "qio05.sqlite3"), total_budget_bytes=10_000_000,
        main_db_max_bytes=5_000_000, max_events=max_events, now=Clock(),
        io_stale_purge_gate_enabled=gate)
    value.initialize()
    return value


def _qio05_rows(value):
    return value.connection.execute("SELECT * FROM sensor_spool ORDER BY sequence").fetchall()


@pytest.mark.parametrize("gate", [False, True])
@pytest.mark.parametrize("endpoint,count", [("evidence", n) for n in (0, 1, 2, 4, 8, 32, 100)] + [("source_health", 2), ("source_health", 4)])
def test_QIO05_T01_existing_list_transaction_and_durable_order(tmp_path, gate, endpoint, count):
    value = _qio05_spool(tmp_path, gate=gate)
    trace = []
    value.connection.set_trace_callback(trace.append)
    try:
        assert value.enqueue([event(i, endpoint) for i in range(count)]) == count
        assert sum(sql == "BEGIN IMMEDIATE" for sql in trace) == (1 if count >= 2 else 0)
        assert sum(sql == "COMMIT" for sql in trace) == (1 if count >= 2 else 0)
        assert value.connection.in_transaction is False
        assert value.connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        assert value.connection.execute("PRAGMA synchronous").fetchone()[0] == 2
        assert value.connection.execute("PRAGMA busy_timeout").fetchone()[0] == 500
        rows = _qio05_rows(value)
        assert [(r[0], r[1], r[2]) for r in rows] == [(i + 1, endpoint, event(i).event_id) for i in range(count)]
        value.close(); value.initialize()
        assert _qio05_rows(value) == rows
        with pytest.raises(SensorSpoolError, match="too large"):
            value.enqueue([event(i) for i in range(101)])
        assert _qio05_rows(value) == rows
    finally:
        value.close()


@pytest.mark.parametrize("gate", [False, True])
def test_QIO05_T02_mixed_duplicate_lists_and_autoincrement_semantics(tmp_path, gate):
    value = _qio05_spool(tmp_path, gate=gate)
    try:
        assert value.enqueue([event(1), event(2)]) == 2
        for index in range(4):
            assert value.enqueue([event(1), event(3 + 2 * index), event(2), event(4 + 2 * index)]) == 2
        rows = _qio05_rows(value)
        assert [(r[0], r[2]) for r in rows] == [(1, event(1).event_id), (2, event(2).event_id)] + [
            (2 * i - 2, event(i).event_id) for i in range(3, 11)]
        memo = value.next_possible_stale_at_utc
        assert value.enqueue([event(1), event(2), event(3), event(4)]) == 0
        assert _qio05_rows(value) == rows
        if gate:
            assert value.next_possible_stale_at_utc == memo
        # INSERT OR IGNORE still consumes AUTOINCREMENT candidates, as before.
        assert value.connection.execute("SELECT seq FROM sqlite_sequence WHERE name='sensor_spool'").fetchone()[0] == 22
        value.close(); value.initialize()
        assert _qio05_rows(value) == rows
    finally:
        value.close()


@pytest.mark.parametrize("gate", [False, True])
@pytest.mark.parametrize("failed_index", [2, 3])
@pytest.mark.parametrize("endpoint", ["evidence", "source_health"])
def test_QIO05_T03_real_sqlite_abort_has_zero_proposed_survivors(tmp_path, gate, failed_index, endpoint):
    from app.device_fingerprint_sensor import spool as module
    value = _qio05_spool(tmp_path, gate=gate)
    try:
        value.enqueue([event(90)])
        before = _qio05_rows(value)
        notes = []
        value._note_new_insert = notes.append
        value.connection.execute("CREATE TRIGGER qio05_abort BEFORE INSERT ON sensor_spool WHEN NEW.event_id='%s' BEGIN SELECT RAISE(ABORT,'qio05 injected'); END" % event(failed_index).event_id)
        with pytest.raises(SensorSpoolError, match="enqueue failed") as exc:
            value.enqueue([event(i, endpoint) for i in (1, 2, 3)])
        assert isinstance(exc.value.__cause__, sqlite3.IntegrityError)
        assert not value.connection.in_transaction and notes == []
        assert value.next_possible_stale_at_utc is module._UNKNOWN
        assert _qio05_rows(value) == before
        assert value.connection.execute("SELECT seq FROM sqlite_sequence WHERE name='sensor_spool'").fetchone()[0] == 1
        value.close(); value.initialize()
        assert _qio05_rows(value) == before
        value.connection.execute("DROP TRIGGER qio05_abort")
        assert value.enqueue([event(i, endpoint) for i in (1, 2, 3)]) == 3
    finally:
        value.close()


class _Qio05ConnectionProxy:
    """Test-only seam; all unmodified calls execute against real disposable SQLite."""
    def __init__(self, connection, *, execute=None, rollback=None):
        self.raw, self.on_execute, self.on_rollback = connection, execute, rollback
        self.was_closed = False
    def __getattr__(self, name): return getattr(self.raw, name)
    def __enter__(self): self.raw.__enter__(); return self
    def __exit__(self, *args): return self.raw.__exit__(*args)
    def execute(self, sql, *args):
        if self.on_execute is not None: self.on_execute(sql)
        return self.raw.execute(sql, *args)
    def rollback(self):
        if self.on_rollback is not None: self.on_rollback()
        return self.raw.rollback()
    def close(self): self.was_closed = True; return self.raw.close()


@pytest.mark.parametrize("gate", [False, True])
def test_QIO05_T04_begin_busy_is_real_and_leaves_no_transaction(tmp_path, gate):
    value = _qio05_spool(tmp_path, gate=gate)
    other = sqlite3.connect(str(value.path), isolation_level=None)
    def lock_at_begin(sql):
        if sql == "BEGIN IMMEDIATE":
            other.execute("BEGIN IMMEDIATE")
    value.connection = _Qio05ConnectionProxy(value.connection, execute=lock_at_begin)
    try:
        with pytest.raises(SensorSpoolError) as exc:
            value.enqueue([event(1), event(2)])
        assert isinstance(exc.value.__cause__, sqlite3.OperationalError)
        assert "locked" in str(exc.value.__cause__)
        assert not value.connection.in_transaction
        other.rollback()
        assert _qio05_rows(value) == []
        value.close(); value.initialize()
        assert _qio05_rows(value) == []
    finally:
        other.close(); value.close()


@pytest.mark.parametrize("gate", [False, True])
def test_QIO05_T04_real_sqlite_commit_denial_rolls_back(tmp_path, gate):
    value = _qio05_spool(tmp_path, gate=gate)
    denied = []
    trace = []
    value.connection.set_trace_callback(trace.append)
    def authorize(action, first, _second, _db, _source):
        if action == sqlite3.SQLITE_TRANSACTION and first == "COMMIT":
            denied.append(first)
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    value.connection.set_authorizer(authorize)
    try:
        with pytest.raises(SensorSpoolError) as exc:
            value.enqueue([event(1), event(2)])
        assert isinstance(exc.value.__cause__, sqlite3.DatabaseError)
        assert not value.connection.in_transaction
        assert denied == ["COMMIT"]
        assert sum(sql.startswith("INSERT OR IGNORE") for sql in trace) == 2
        value.connection.set_authorizer(lambda *_args: sqlite3.SQLITE_OK)
        assert _qio05_rows(value) == []
        value.close(); value.initialize()
        assert _qio05_rows(value) == []
    finally:
        value.close()


@pytest.mark.parametrize("gate", [False, True])
@pytest.mark.parametrize("rollback_fails", [False, True])
def test_QIO05_T04_simulated_ioerr_commit_and_rollback_discard(tmp_path, gate, rollback_fails):
    from app.device_fingerprint_sensor import spool as module
    value = _qio05_spool(tmp_path, gate=gate)
    before = _qio05_rows(value)
    def fail_commit(sql):
        if sql == "COMMIT": raise sqlite3.OperationalError("simulated SQLite IOERR at COMMIT")
    def fail_rollback():
        if rollback_fails: raise sqlite3.OperationalError("simulated rollback IOERR")
    connection = _Qio05ConnectionProxy(value.connection, execute=fail_commit, rollback=fail_rollback)
    value.connection = connection
    try:
        with pytest.raises(SensorSpoolError):
            value.enqueue([event(1), event(2)])
        assert value.next_possible_stale_at_utc is module._UNKNOWN
        if rollback_fails:
            assert value.connection is None and connection.was_closed
        else:
            assert value.connection is connection and not connection.in_transaction
        value.close(); value.initialize()
        assert _qio05_rows(value) == before
    finally:
        value.close()


@pytest.mark.parametrize("gate", [False, True])
def test_QIO05_T04_real_full_rolls_back_inserted_prefix(tmp_path, gate):
    value = _qio05_spool(tmp_path, gate=gate)
    try:
        page_count = value.connection.execute("PRAGMA page_count").fetchone()[0]
        value.connection.execute("PRAGMA max_page_count=%d" % (page_count + 3))
        values = [NormalizedEvent("evidence", event(i).event_id, "dhcp", event(i).observed_at, {"synthetic": "x" * 3000}) for i in range(4)]
        with pytest.raises(SensorSpoolError) as exc:
            value.enqueue(values)
        assert "full" in str(exc.value.__cause__).lower()
        assert not value.connection.in_transaction
        value.close(); value.initialize()
        assert _qio05_rows(value) == []
    finally:
        value.close()


@pytest.mark.parametrize("gate", [False, True])
def test_QIO05_T05_commit_visible_before_memo_and_success_return(tmp_path, gate):
    value = _qio05_spool(tmp_path, gate=gate)
    observed = []
    original = value._note_new_insert
    def note(stamp):
        assert not value.connection.in_transaction
        with sqlite3.connect(str(value.path)) as reader:
            assert reader.execute("SELECT COUNT(*) FROM sensor_spool").fetchone()[0] == 4
        observed.append(stamp)
        original(stamp)
    value._note_new_insert = note
    try:
        values = [event(i) for i in range(4)]
        assert value.enqueue(values) == 4
        assert len(observed) == (4 if gate else 0)
        rows = _qio05_rows(value)
        # Lost consumer response: reopen and replay the same source IDs.
        value.close(); value.initialize()
        assert value.enqueue(values) == 0
        assert _qio05_rows(value) == rows
    finally:
        value.close()


def test_QIO05_T05_process_exit_after_commit_before_consumer_response(tmp_path):
    path = tmp_path / "qio05.sqlite3"
    script = """
import os, sys
from tests.device_fingerprint_sensor.test_spool import _qio05_spool, event
value = _qio05_spool(__import__('pathlib').Path(sys.argv[1]), gate=True)
value.enqueue([event(1), event(2), event(3)])
os._exit(73)
"""
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path)], cwd=Path(__file__).resolve().parents[2], timeout=20)
    assert result.returncode == 73
    value = _qio05_spool(tmp_path, gate=True)
    try:
        rows = _qio05_rows(value)
        assert [r[2] for r in rows] == [event(i).event_id for i in (1, 2, 3)]
        assert value.enqueue([event(i) for i in (1, 2, 3)]) == 0
        assert _qio05_rows(value) == rows
        assert value.path == path
    finally:
        value.close()


@pytest.mark.parametrize("gate", [False, True])
@pytest.mark.parametrize("housekeeping", ["stale", "eviction"])
def test_QIO05_T07_housekeeping_is_not_rolled_back_with_failed_proposed_rows(tmp_path, gate, housekeeping):
    clock = Clock()
    value = _qio05_spool(tmp_path, gate=gate, max_events=4)
    value.now = clock
    try:
        value.enqueue([event(90), event(91)])
        if housekeeping == "stale":
            clock.value += timedelta(days=2)
        value.connection.execute("CREATE TRIGGER qio05_abort BEFORE INSERT ON sensor_spool WHEN NEW.event_id='%s' BEGIN SELECT RAISE(ABORT,'proposed insert fails'); END" % event(2).event_id)
        values = [event(i, observed=clock.value.isoformat(timespec="milliseconds").replace("+00:00", "Z")) for i in (1, 2, 3)]
        with pytest.raises(SensorSpoolError): value.enqueue(values)
        assert not value.connection.in_transaction
        rows = _qio05_rows(value)
        if housekeeping == "stale":
            assert rows == [] and value.stale_dropped == 2 and value.evicted == 0
        else:
            assert [r[2] for r in rows] == [event(91).event_id]
            assert value.evicted == 1 and value.stale_dropped == 0
        value.close(); value.initialize()
        assert _qio05_rows(value) == rows
    finally:
        value.close()


@pytest.mark.parametrize("gate", [False, True])
def test_QIO05_T08_single_calls_remain_immediate_without_atomic_group(tmp_path, gate, monkeypatch):
    value = _qio05_spool(tmp_path, gate=gate)
    def forbidden(*_args): pytest.fail("single call must not wait for/group another call")
    monkeypatch.setattr(value, "_insert_coalesced_rows", forbidden)
    try:
        for i in range(4):
            assert value.enqueue([event(i)]) == 1
            with sqlite3.connect(str(value.path)) as reader:
                assert reader.execute("SELECT COUNT(*) FROM sensor_spool").fetchone()[0] == i + 1
    finally:
        value.close()


@pytest.mark.parametrize("gate", [False, True])
def test_QIO05_existing_atomic_coalesced_constraints_and_rollback(tmp_path, gate):
    value = _qio05_spool(tmp_path, gate=gate)
    try:
        assert value.enqueue([event(i) for i in range(32)], atomic_coalesced=True) == 32
        before = _qio05_rows(value)
        for values in ([event(i) for i in range(33)], [event(100, "source_health")], [NormalizedEvent("evidence", event(100).event_id, "dhcp", event(1).observed_at, {"synthetic": "x" * 262144})]):
            with pytest.raises(SensorSpoolError): value.enqueue(values, atomic_coalesced=True)
            assert _qio05_rows(value) == before
        value.connection.execute("CREATE TRIGGER qio05_abort BEFORE INSERT ON sensor_spool WHEN NEW.event_id='%s' BEGIN SELECT RAISE(ABORT,'coalesced failure'); END" % event(101).event_id)
        with pytest.raises(SensorSpoolError): value.enqueue([event(100), event(101)], atomic_coalesced=True)
        assert not value.connection.in_transaction and _qio05_rows(value) == before
        value.close(); value.initialize()
        assert _qio05_rows(value) == before
    finally:
        value.close()


@pytest.mark.parametrize("gate", [False, True])
def test_QIO05_T01_stale_filter_preserves_existing_list_transaction_boundary(tmp_path, gate):
    value = _qio05_spool(tmp_path, gate=gate)
    try:
        trace = []
        value.connection.set_trace_callback(trace.append)
        assert value.enqueue([event(1, observed="2026-09-12T00:00:00.000Z"), event(2)]) == 1
        assert sum(sql == "BEGIN IMMEDIATE" for sql in trace) == 1
        assert value.stale_dropped == 1
        rows = _qio05_rows(value)
        trace.clear()
        assert value.enqueue([event(3, observed="2026-09-12T00:00:00.000Z"), event(4, observed="2026-09-12T00:00:00.000Z")]) == 0
        assert "BEGIN IMMEDIATE" not in trace and _qio05_rows(value) == rows
        assert value.stale_dropped == 3
    finally:
        value.close()


def test_QIO05_T01_ordinary_list_does_not_inherit_coalescer_size_cap(tmp_path):
    value = _qio05_spool(tmp_path, gate=True)
    try:
        values = [NormalizedEvent("source_health", event(i).event_id, "dhcp", event(i).observed_at, {"synthetic": "x" * 135000}) for i in (1, 2)]
        assert value.enqueue(values) == 2
        rows = _qio05_rows(value)
        value.close(); value.initialize()
        assert _qio05_rows(value) == rows
    finally:
        value.close()


@pytest.mark.parametrize("gate", [False, True])
@pytest.mark.parametrize("failure", [RuntimeError, KeyboardInterrupt])
def test_QIO05_T04_interruption_or_begin_failure_does_not_leave_transaction(tmp_path, gate, failure):
    value = _qio05_spool(tmp_path, gate=gate)
    inserts = []
    def interrupt(sql):
        if sql == "BEGIN IMMEDIATE" and failure is RuntimeError:
            raise failure("synthetic begin failure")
        if sql.startswith("INSERT OR IGNORE"):
            inserts.append(sql)
            if len(inserts) == 2: raise failure("synthetic interrupt")
    value.connection = _Qio05ConnectionProxy(value.connection, execute=interrupt)
    try:
        with pytest.raises(failure): value.enqueue([event(1), event(2), event(3)])
        assert not value.connection.in_transaction
        assert _qio05_rows(value) == []
        value.close(); value.initialize()
        assert _qio05_rows(value) == []
    finally:
        value.close()


@pytest.mark.parametrize("gate", [False, True])
def test_QIO05_T07_health_capacity_is_preserved_without_false_success(tmp_path, gate):
    value = _qio05_spool(tmp_path, gate=gate, max_events=2)
    try:
        assert value.enqueue([event(1, "source_health"), event(2, "source_health")]) == 2
        rows = _qio05_rows(value)
        assert value.enqueue([event(3), event(4)]) == 0
        assert value.capacity_blocked and value.evicted == 0 and value.stale_dropped == 0
        assert _qio05_rows(value) == rows and not value.connection.in_transaction
        value.close(); value.initialize()
        assert _qio05_rows(value) == rows
    finally:
        value.close()
