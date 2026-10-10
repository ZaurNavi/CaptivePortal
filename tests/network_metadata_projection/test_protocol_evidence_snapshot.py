import sqlite3
import threading
from contextlib import contextmanager
from datetime import timedelta

import pytest

from app.analytics.source_gateway import QueryDeadline, AnalyticsQueryDeadlineExceeded
from app.network_metadata.validation import ni_format_utc
from app.network_metadata_projection.models import RegistryEvaluation, ProjectionUnavailable, ProjectionValidationError
from app.network_metadata_projection.read_service import DeviceNetworkMetadataReadService
from app.network_protocol_intelligence import DeviceProtocolIntelligenceReadService
from .support import stack, source_record, SITE, MAC, T0

DEVICE = "10000000-0000-4000-8000-000000000001"


@pytest.fixture
def state(tmp_path):
    value = stack(tmp_path)
    value.registry.values[MAC] = RegistryEvaluation("authoritative", DEVICE)
    value.service.poll()
    try:
        yield value
    finally:
        value.repo.close()


def read(state, *, reader=None, device=DEVICE, at=None):
    at = at or T0 + timedelta(minutes=1)
    return (reader or DeviceNetworkMetadataReadService(state.config.db_path)).read_protocol_evidence_snapshot(
        SITE, device, MAC, ni_format_utc(at - timedelta(days=1)), ni_format_utc(at),
        max_rows=20000, deadline=QueryDeadline.after(5))


def test_read_only_single_snapshot_narrow_sql_and_late_binding(state, monkeypatch):
    reader = DeviceNetworkMetadataReadService(state.config.db_path)
    original = reader._snapshot
    statements = []
    @contextmanager
    def traced(**kwargs):
        with original(**kwargs) as c:
            c.set_trace_callback(statements.append)
            yield c
    monkeypatch.setattr(reader, "_snapshot", traced)
    value = read(state, reader=reader)
    assert value["binding_state"] == "authoritative" and value["bound_device_id"] == DEVICE
    assert len(value["facts"]) == 1
    assert set(value["facts"][0]) == {"edge_id", "event_at", "source_event_family"}
    assert any("idx_projection_mac_event" in sql for sql in statements)
    assert not any(sql.startswith(("UPDATE", "INSERT", "DELETE", "PRAGMA wal_checkpoint")) for sql in statements)


@pytest.mark.parametrize("binding", ["not_yet_registry_resolved", "registry_unavailable", None])
def test_pending_identity_never_scans_edges(state, monkeypatch, binding):
    # Separate disposable state with pending binding; no production mutation.
    c = state.repo.connection
    if binding is None:
        c.execute("DELETE FROM projection_site_mac_bindings WHERE site_id=? AND client_mac=?", (SITE, MAC))
    else:
        c.execute("UPDATE projection_site_mac_bindings SET binding_state=?,device_id=NULL,authoritative_bound_at=NULL WHERE site_id=? AND client_mac=?", (binding, SITE, MAC))
    reader = DeviceNetworkMetadataReadService(state.config.db_path)
    original = reader._snapshot
    statements = []
    @contextmanager
    def traced(**kwargs):
        with original(**kwargs) as connection:
            connection.set_trace_callback(statements.append)
            yield connection
    monkeypatch.setattr(reader, "_snapshot", traced)
    value = read(state, reader=reader)
    assert value["facts"] == ()
    assert not any("FROM device_network_metadata_edges" in sql for sql in statements)
    # Writer-owned next authoritative binding reveals retained facts unchanged.
    if binding is not None:
        c.execute("UPDATE projection_site_mac_bindings SET binding_state='authoritative',device_id=?,authoritative_bound_at=? WHERE site_id=? AND client_mac=?",
                  (DEVICE, ni_format_utc(T0), SITE, MAC))
        assert len(read(state)["facts"]) == 1


def test_wrong_device_and_future_rows_rejected(state):
    with pytest.raises(ProjectionUnavailable):
        read(state, device="20000000-0000-4000-8000-000000000002")
    with pytest.raises(ProjectionUnavailable):
        read(state, at=T0)  # retained event is strictly after the evaluation instant
    with pytest.raises(ProjectionUnavailable):
        read(state, at=T0 + timedelta(microseconds=123456))


def test_exact_row_bound_with_disposable_facts(state):
    c = state.repo.connection
    original = dict(c.execute("SELECT * FROM device_network_metadata_edges WHERE client_mac=?", (MAC,)).fetchone())
    sql = "INSERT INTO device_network_metadata_edges (" + ",".join(original) + ") VALUES(" + ",".join("?" for _ in original) + ")"
    with state.repo.transaction():
        for number in range(1, 20000):
            row = {**original, "edge_id": f"{number:064x}", "source_observation_ref": f"synthetic-{number}"}
            c.execute(sql, tuple(row.values()))
    assert len(read(state)["facts"]) == 20000
    row = {**original, "edge_id": "f" * 64, "source_observation_ref": "synthetic-overflow"}
    c.execute(sql, tuple(row.values()))
    with pytest.raises(ProjectionUnavailable):
        read(state)


def test_deadline_progress_cancels_snapshot_and_disabled_never_opens(state, monkeypatch):
    with pytest.raises(AnalyticsQueryDeadlineExceeded):
        DeviceNetworkMetadataReadService(state.config.db_path).read_protocol_evidence_snapshot(
            SITE, DEVICE, MAC, ni_format_utc(T0 - timedelta(days=1)), ni_format_utc(T0),
            max_rows=20000, deadline=QueryDeadline.after(-1))
    original = sqlite3.connect
    def reject(*args, **kwargs):
        raise AssertionError("disabled must not open DB")
    monkeypatch.setattr(sqlite3, "connect", reject)
    with pytest.raises(ProjectionUnavailable):
        read(state, reader=DeviceNetworkMetadataReadService(state.config.db_path, enabled=False))
    monkeypatch.setattr(sqlite3, "connect", original)
    class Clock:
        def __init__(self): self.n = 0
        def __call__(self):
            self.n += 1
            return 0 if self.n < 5 else 6
    with pytest.raises(AnalyticsQueryDeadlineExceeded):
        with DeviceNetworkMetadataReadService(state.config.db_path)._snapshot(deadline=QueryDeadline(5, Clock())) as c:
            c.execute("WITH RECURSIVE numbers(n) AS (VALUES(0) UNION ALL SELECT n+1 FROM numbers WHERE n<1000000) SELECT sum(n) FROM numbers").fetchone()
    assert len(read(state)["facts"]) == 1


def test_runtime_binding_and_facts_share_snapshot_with_two_wal_readers(state, monkeypatch):
    """Writer uses normal repository transactions/poll while two real reads hold WAL snapshots."""
    barrier = threading.Barrier(3)
    release = threading.Event()
    reader = DeviceNetworkMetadataReadService(state.config.db_path)
    original = reader._snapshot
    @contextmanager
    def pinned(**kwargs):
        with original(**kwargs) as c:
            c.execute("SELECT runtime_state FROM projection_runtime_state").fetchone()
            barrier.wait(timeout=4)
            assert release.wait(4)
            yield c
    monkeypatch.setattr(reader, "_snapshot", pinned)
    results, failures = [], []
    def worker():
        try:
            results.append(DeviceProtocolIntelligenceReadService(reader).get_device_protocol_summary(
                SITE, DEVICE, MAC, evaluated_at_utc=ni_format_utc(T0 + timedelta(minutes=1)), deadline=QueryDeadline.after(5)))
        except Exception as exc:
            failures.append(type(exc).__name__)
    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads: thread.start()
    try:
        barrier.wait(timeout=4)
        state.source.records.append(source_record(1, event_at=ni_format_utc(T0 + timedelta(seconds=2))))
        state.service.poll()
        with state.repo.transaction():
            state.repo.connection.execute("UPDATE projection_runtime_state SET runtime_state='attribution_unavailable'")
        assert state.repo.live_state not in {"blocked_conflict", "capacity_halted"}
    finally:
        release.set()
        for thread in threads: thread.join(5)
    assert failures == [] and len(results) == 2
    assert all(value.last_protocol_observation.observed_at == state.source.records[0].event_at
               and value.coverage.attribution_state == "usable" for value in results)
    monkeypatch.setattr(reader, "_snapshot", original)
    after = read(state, reader=reader)
    assert len(after["facts"]) == 2 and after["runtime_state"] == "attribution_unavailable"


@pytest.mark.parametrize("kind", ["absent", "schema", "busy"])
def test_store_failure_is_unavailable(tmp_path, kind):
    path = tmp_path / "untrusted.sqlite3"
    connection = None
    if kind != "absent":
        connection = sqlite3.connect(path)
        connection.execute("CREATE TABLE invalid(value)")
        connection.commit()
        if kind == "busy":
            connection.execute("BEGIN EXCLUSIVE")
    reader = DeviceNetworkMetadataReadService(str(path))
    try:
        with pytest.raises(ProjectionUnavailable):
            reader.read_protocol_evidence_snapshot(SITE, DEVICE, MAC, ni_format_utc(T0 - timedelta(days=1)),
                ni_format_utc(T0), max_rows=20000, deadline=QueryDeadline.after(5))
    finally:
        if connection: connection.close()


def test_unknown_retained_protocol_fails_semantic_integrity(state):
    c = state.repo.connection
    row = dict(c.execute("SELECT * FROM device_network_metadata_edges WHERE client_mac=?", (MAC,)).fetchone())
    c.execute("PRAGMA ignore_check_constraints=ON")
    row.update(edge_id="e" * 64, source_observation_ref="synthetic-corrupt", source_event_family="tcp")
    c.execute("INSERT INTO device_network_metadata_edges (" + ",".join(row) + ") VALUES(" + ",".join("?" for _ in row) + ")", tuple(row.values()))
    with pytest.raises(Exception) as error:
        DeviceProtocolIntelligenceReadService(DeviceNetworkMetadataReadService(state.config.db_path)).get_device_protocol_summary(
            SITE, DEVICE, MAC, evaluated_at_utc=ni_format_utc(T0 + timedelta(minutes=1)), deadline=QueryDeadline.after(5))
    from app.network_protocol_intelligence.models import ProtocolUnavailable
    assert type(error.value) is ProtocolUnavailable


@pytest.mark.parametrize("max_rows", [0, 500, 20001, True])
def test_exact_internal_row_ceiling_only(state, max_rows):
    with pytest.raises(ProjectionValidationError):
        DeviceNetworkMetadataReadService(state.config.db_path).read_protocol_evidence_snapshot(SITE, DEVICE, MAC,
            ni_format_utc(T0 - timedelta(days=1)), ni_format_utc(T0), max_rows=max_rows, deadline=QueryDeadline.after(5))
