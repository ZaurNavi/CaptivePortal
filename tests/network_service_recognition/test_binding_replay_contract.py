"""G2 B1 consumer atomics; real SQLite, minimal disposable queue/checkpoint fixture."""
from contextlib import contextmanager
from types import SimpleNamespace
import sqlite3

import pytest

from app.network_service_recognition.binding_replay import (
    enqueue_binding_changes, read_targeted_replay_page, BindingReplayConflict)

GENERATION = "10000000-0000-4000-8000-000000000010"
DEVICE = "10000000-0000-4000-8000-000000000001"
SITE, MAC = "6a64f17630da7c70d232187a", "02:AA:BB:CC:DD:01"
AT = "2026-10-13T12:00:00.000000Z"


class QueueFixture:
    """Only B1's two SQL contracts; full store/startup validation belongs to G3."""
    def __init__(self):
        self.connection = sqlite3.connect(":memory:", isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.crash_point = lambda _: None
        self.connection.execute(
            "CREATE TABLE service_materialization_checkpoints("
            "generation_id TEXT PRIMARY KEY,last_binding_change_seq INTEGER NOT NULL,updated_at_utc TEXT NOT NULL)")
        self.connection.execute(
            "CREATE TABLE service_binding_replay_jobs(job_id TEXT PRIMARY KEY,generation_id TEXT NOT NULL,"
            "binding_change_seq INTEGER NOT NULL,site_id TEXT NOT NULL,client_mac TEXT NOT NULL,device_id TEXT NOT NULL,"
            "from_utc TEXT NOT NULL,to_utc TEXT NOT NULL,cursor_event_at TEXT,cursor_edge_id TEXT,state TEXT NOT NULL,"
            "UNIQUE(generation_id,binding_change_seq))")
        self.connection.execute("INSERT INTO service_materialization_checkpoints VALUES(?,0,?)", (GENERATION, AT))
    @contextmanager
    def transaction(self):
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.crash_point("before_commit")
            self.connection.execute("COMMIT")
            self.crash_point("after_commit")
        except BaseException:
            if self.connection.in_transaction:
                self.connection.execute("ROLLBACK")
            raise


@pytest.fixture
def queue():
    value = QueueFixture()
    try:
        yield value
    finally:
        value.connection.close()


def change(sequence=1, **kwargs):
    return SimpleNamespace(change_seq=sequence, site_id=SITE, client_mac=MAC, device_id=DEVICE, **kwargs)


@pytest.mark.parametrize("point,committed", [
    ("binding_job_enqueued", False), ("before_commit", False), ("after_commit", True),
])
def test_R1_QA05_QA06_enqueue_and_cursor_crash_atomicity(queue, point, committed):
    class Crash(BaseException):
        pass
    def crash(stage):
        if stage == point:
            raise Crash()
    queue.crash_point = crash
    with pytest.raises(Crash):
        enqueue_binding_changes(queue, GENERATION, 0, (change(),), AT)
    assert queue.connection.execute("SELECT count(*) FROM service_binding_replay_jobs").fetchone()[0] == int(committed)
    cursor = queue.connection.execute("SELECT last_binding_change_seq FROM service_materialization_checkpoints").fetchone()[0]
    assert cursor == int(committed)
    queue.crash_point = lambda _: None
    if not committed:
        assert enqueue_binding_changes(queue, GENERATION, 0, (change(),), AT)
    else:
        # A restarted consumer reads after the durable cursor; no duplicate page.
        assert enqueue_binding_changes(queue, GENERATION, cursor, (), AT) is False
    assert queue.connection.execute("SELECT count(*) FROM service_binding_replay_jobs").fetchone()[0] == 1


def test_R1_QA07_exact_mac_replay_never_queries_another_device(queue):
    enqueue_binding_changes(queue, GENERATION, 0, (change(),), AT)
    job = queue.connection.execute("SELECT * FROM service_binding_replay_jobs").fetchone()
    calls = []
    class Reader:
        def read_candidate_page(self, site, first, last, **kwargs):
            calls.append((site, kwargs["client_mac"], kwargs["limit"]))
            assert site == SITE and kwargs["client_mac"] == MAC and kwargs["limit"] == 128
            return ()
    assert read_targeted_replay_page(Reader(), job, deadline=object()) == ()
    assert calls == [(SITE, MAC, 128)]
    assert all(mac != "02:AA:BB:CC:DD:02" for _, mac, _ in calls)


def test_deterministic_job_identity_and_cursor_cas(queue):
    enqueue_binding_changes(queue, GENERATION, 0, (change(),), AT)
    before = tuple(queue.connection.iterdump())
    with pytest.raises(BindingReplayConflict):
        enqueue_binding_changes(queue, GENERATION, 0, (change(),), AT)
    assert tuple(queue.connection.iterdump()) == before
    assert enqueue_binding_changes(queue, GENERATION, 1, (change(2),), AT)
    assert queue.connection.execute("SELECT count(*) FROM service_binding_replay_jobs").fetchone()[0] == 2


@pytest.mark.parametrize("rows", [(change(2), change(1)), (change(), change()), tuple(change(i + 1) for i in range(129))])
def test_invalid_page_cannot_advance_checkpoint(queue, rows):
    with pytest.raises(BindingReplayConflict):
        enqueue_binding_changes(queue, GENERATION, 0, rows, AT)
    assert queue.connection.execute("SELECT last_binding_change_seq FROM service_materialization_checkpoints").fetchone()[0] == 0
