"""#293: fixed-size exact NI03 projection under high cardinality (synthetic)."""
import sqlite3
import threading
import uuid
import tracemalloc
from contextlib import contextmanager
from dataclasses import replace
from datetime import timedelta

import pytest

from app.analytics.source_gateway import QueryDeadline, AnalyticsQueryDeadlineExceeded
from app.network_metadata.validation import ni_format_utc
from app.network_metadata_projection.models import ProjectionUnavailable, RegistryEvaluation, ProjectionValidationError
from app.network_metadata_projection.read_service import DeviceNetworkMetadataReadService, PROTOCOL_LATEST_SQL
from app.network_protocol_intelligence.read_service import DeviceProtocolIntelligenceReadService
from app.network_protocol_intelligence.models import ProtocolUnavailable, public_summary
from .support import stack, source_record, SITE, MAC, T0

DEVICE = "10000000-0000-4000-8000-000000000001"
AT = T0 + timedelta(minutes=1)
FAMILIES = ("dns", "tls", "quic")


def seed(tmp_path, count, *, families=FAMILIES, site=SITE, mac=MAC, extension=False):
    """File-backed Core V2 with real service-produced template + disposable facts."""
    state = stack(tmp_path, [source_record(site_id=site, dst_ip="203.0.113.93")])
    state.repo.config = state.config = replace(state.config, max_db_bytes=1073741824)
    state.attribution.macs["10.73.0.7"] = mac
    state.attribution.states["203.0.113.93"] = "endpoint_absent"
    state.registry.values[mac] = RegistryEvaluation("authoritative", DEVICE)
    if extension:
        from app.network_metadata_projection.service_extension import install_service_recognition_extension
        install_service_recognition_extension(state.repo)
    state.service.poll()
    c = state.repo.connection
    template = dict(c.execute("SELECT * FROM device_network_metadata_edges").fetchone())
    with state.repo.transaction(retention=True):
        c.execute("DELETE FROM device_network_metadata_edges")
        sql = "INSERT INTO device_network_metadata_edges (" + ",".join(template) + ") VALUES(" + ",".join("?" for _ in template) + ")"
        def rows():
            for number in range(count):
                yield tuple({**template, "edge_id": f"{number:064x}",
                    "source_observation_ref": str(uuid.uuid5(uuid.NAMESPACE_URL, "issue293/" + str(number))),
                    "source_event_family": families[number % len(families)],
                    "event_at": ni_format_utc(AT - timedelta(seconds=1 + number % 100)),
                }.values())
        c.executemany(sql, rows())
        if extension:
            c.execute("INSERT INTO projection_service_recognition_feed(edge_id,committed_at_utc) "
                      "SELECT edge_id,projected_at FROM device_network_metadata_edges ORDER BY edge_id")
    return state


def latest(state, *, reader=None, site=SITE, device=DEVICE, mac=MAC, at=AT, deadline=None):
    return (reader or DeviceNetworkMetadataReadService(state.config.db_path)).read_protocol_latest_snapshot(
        site, device, mac, ni_format_utc(at - timedelta(days=1)), ni_format_utc(at),
        deadline=deadline or QueryDeadline.after(5))


def summary(state, **kwargs):
    return DeviceProtocolIntelligenceReadService(DeviceNetworkMetadataReadService(state.config.db_path)).get_device_protocol_summary(
        SITE, DEVICE, MAC, evaluated_at_utc=ni_format_utc(AT), deadline=QueryDeadline.after(5), **kwargs)


@pytest.mark.parametrize("count", [0, 1, 20000, 20001, 28976, 30000, 100001])
def test_volume_never_changes_exact_top1_summary(tmp_path, count):
    state = seed(tmp_path, count)
    try:
        value = latest(state)
        assert len(value["facts"]) == min(count, 3)
        c = state.repo.connection
        # Independent exhaustive test oracle, NEVER used by the production read.
        all_rows = c.execute("SELECT edge_id,event_at,source_event_family FROM device_network_metadata_edges "
            "ORDER BY event_at DESC,edge_id").fetchall()
        expected = {}
        for row in all_rows:
            expected.setdefault(row["source_event_family"], dict(row))
        assert value["facts"] == tuple(expected[f] for f in FAMILIES if f in expected)
        dto = public_summary(summary(state))
        assert dto["evidence_state"] == ("present" if count else "empty")
        assert dto["coverage"]["historical_window_completeness_claimed"] is False
        assert "client_mac" not in str(dto) and "edge_id" not in str(dto)
        if count:
            assert dto["last_protocol_observation"]["protocol_id"] == "dns"
        if count == 100001:
            tracemalloc.start()
            try:
                summary(state)
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
            assert peak < 1048576  # no 100k-row Python materialization
        if count > 20000:
            with pytest.raises(ProjectionUnavailable):
                DeviceNetworkMetadataReadService(state.config.db_path).read_protocol_evidence_snapshot(
                    SITE, DEVICE, MAC, ni_format_utc(AT - timedelta(days=1)), ni_format_utc(AT),
                    max_rows=20000, deadline=QueryDeadline.after(5))
    finally:
        state.repo.close()


@pytest.mark.parametrize("families", [("quic",), ("tls", "quic"), ("dns",) * 98 + ("tls", "quic")])
def test_skew_and_rare_families_use_covering_seek_no_sort(tmp_path, families):
    state = seed(tmp_path, 1001, families=families)
    try:
        assert {row["source_event_family"] for row in latest(state)["facts"]} == set(families)
        for family in FAMILIES:
            plan = [row[3] for row in state.repo.connection.execute("EXPLAIN QUERY PLAN " + PROTOCOL_LATEST_SQL,
                (SITE, MAC, family, ni_format_utc(AT - timedelta(days=1)), ni_format_utc(AT)))]
            assert any("SEARCH" in p and "idx_projection_mac_family_event_latest" in p for p in plan)
            assert not any("SCAN" in p or "TEMP B-TREE" in p for p in plan)
    finally:
        state.repo.close()


@pytest.mark.parametrize("age,recent,accepted", [(86400, False, True), (86400.000001, False, True),
    (3600, True, True), (3600.000001, False, True), (0.000001, True, True), (0, False, False), (-1, False, False)])
def test_exact_half_open_windows_and_future_guard(tmp_path, age, recent, accepted):
    state = seed(tmp_path, 1)
    try:
        c = state.repo.connection
        row = dict(c.execute("SELECT * FROM device_network_metadata_edges").fetchone())
        with state.repo.transaction(retention=True):
            c.execute("DELETE FROM device_network_metadata_edges")
            row["event_at"] = ni_format_utc(AT - timedelta(seconds=age))
            c.execute("INSERT INTO device_network_metadata_edges (" + ",".join(row) + ") VALUES(" + ",".join("?" for _ in row) + ")", tuple(row.values()))
        if not accepted:
            with pytest.raises(ProtocolUnavailable):
                summary(state)
        else:
            dto = summary(state)
            assert bool(dto.recent_protocols) is recent
            assert (dto.last_protocol_observation is not None) is (age <= 86400)
    finally:
        state.repo.close()


@pytest.mark.parametrize("binding", [None, "not_yet_registry_resolved", "registry_unavailable"])
def test_identity_gate_before_any_fact_query(tmp_path, monkeypatch, binding):
    state = seed(tmp_path, 5)
    try:
        c = state.repo.connection
        if binding is None:
            c.execute("DELETE FROM projection_site_mac_bindings")
        else:
            c.execute("UPDATE projection_site_mac_bindings SET binding_state=?,device_id=NULL,authoritative_bound_at=NULL", (binding,))
        reader = DeviceNetworkMetadataReadService(state.config.db_path)
        original = reader._snapshot
        sql = []
        @contextmanager
        def traced(**kwargs):
            with original(**kwargs) as connection:
                connection.set_trace_callback(sql.append)
                yield connection
        monkeypatch.setattr(reader, "_snapshot", traced)
        assert latest(state, reader=reader)["facts"] == ()
        assert not any("FROM device_network_metadata_edges" in query for query in sql)
    finally:
        state.repo.close()


def test_site_device_and_changed_binding_never_leak_facts(tmp_path):
    state = seed(tmp_path, 5)
    try:
        other = "20000000-0000-4000-8000-000000000002"
        with pytest.raises(ProjectionUnavailable):
            latest(state, device=other)
        assert latest(state, site="f" * 24)["facts"] == ()
        c = state.repo.connection
        # Legitimate alternate Site with same canonical MAC, pending identity.
        c.execute("INSERT INTO projection_site_mac_bindings SELECT ?,client_mac,'registry_unavailable',NULL,"
                  "first_edge_at,last_edge_at,last_evaluated_at,NULL,NULL FROM projection_site_mac_bindings", ("f" * 24,))
        assert latest(state, site="f" * 24)["facts"] == ()
        with state.repo.transaction():
            c.execute("UPDATE projection_site_mac_bindings SET binding_state='registry_unavailable',device_id=NULL,authoritative_bound_at=NULL WHERE site_id=?", (SITE,))
            c.execute("DELETE FROM projection_registry_identities")
            c.execute("INSERT INTO projection_registry_identities VALUES(?,?,1,?,?,NULL)",
                      (other, MAC, ni_format_utc(AT), ni_format_utc(AT)))
            c.execute("UPDATE projection_site_mac_bindings SET binding_state='authoritative',device_id=?,authoritative_bound_at=? WHERE site_id=?", (other, ni_format_utc(AT), SITE))
        with pytest.raises(ProjectionUnavailable):
            latest(state)
        assert len(latest(state, device=other)["facts"]) == 3
    finally:
        state.repo.close()


def test_same_snapshot_with_ingest_retention_runtime_and_binding_changes(tmp_path, monkeypatch):
    state = seed(tmp_path, 3)
    ready, release = threading.Event(), threading.Event()
    reader = DeviceNetworkMetadataReadService(state.config.db_path)
    original = reader._snapshot
    result, failures = [], []
    @contextmanager
    def pinned(**kwargs):
        with original(**kwargs) as c:
            c.execute("SELECT runtime_state FROM projection_runtime_state").fetchone()
            ready.set()
            assert release.wait(4)
            yield c
    monkeypatch.setattr(reader, "_snapshot", pinned)
    def run():
        try:
            result.append(latest(state, reader=reader))
        except Exception as error:
            failures.append(type(error).__name__)
    thread = threading.Thread(target=run)
    thread.start()
    try:
        assert ready.wait(4)
        state.source.records.append(source_record(1, dst_ip="203.0.113.93", event_at=ni_format_utc(T0 + timedelta(seconds=2))))
        state.service.poll()
        state.service.retain()
        with state.repo.transaction(retention=True):
            state.repo.connection.execute("DELETE FROM device_network_metadata_edges")
            state.repo.connection.execute("UPDATE projection_runtime_state SET runtime_state='source_unavailable'")
            state.repo.connection.execute("UPDATE projection_site_mac_bindings SET binding_state='registry_unavailable',device_id=NULL,authoritative_bound_at=NULL")
    finally:
        release.set()
        thread.join(5)
        state.repo.close()
    assert failures == [] and not thread.is_alive()
    assert len(result) == 1 and len(result[0]["facts"]) == 3
    assert result[0]["runtime_state"] == "usable" and result[0]["binding_state"] == "authoritative"


def test_new_reader_cannot_write_or_create_missing_store_and_obeys_deadline(tmp_path):
    missing = tmp_path / "absent.sqlite3"
    with pytest.raises(ProjectionUnavailable):
        DeviceNetworkMetadataReadService(str(missing)).read_protocol_latest_snapshot(
            SITE, DEVICE, MAC, ni_format_utc(AT - timedelta(days=1)), ni_format_utc(AT), deadline=QueryDeadline.after(5))
    assert not missing.exists()
    state = seed(tmp_path, 3)
    try:
        reader = DeviceNetworkMetadataReadService(state.config.db_path)
        with reader._snapshot(deadline=QueryDeadline.after(5)) as c:
            assert c.execute("PRAGMA query_only").fetchone()[0] == 1
            with pytest.raises(sqlite3.OperationalError):
                c.execute("DELETE FROM device_network_metadata_edges")
        with pytest.raises(AnalyticsQueryDeadlineExceeded):
            latest(state, deadline=QueryDeadline.after(-1))
        with pytest.raises(ProjectionValidationError):
            latest(state, mac=MAC.lower().replace(":", "-"))
    finally:
        state.repo.close()


@pytest.mark.parametrize("bad_family", ["aaa", "other", "tcp", "zzz"])
def test_closed_family_corruption_fails_without_valid_family_scan(tmp_path, bad_family):
    state = seed(tmp_path, 1)
    try:
        c = state.repo.connection
        row = dict(c.execute("SELECT * FROM device_network_metadata_edges").fetchone())
        row.update(edge_id="f" * 64, source_observation_ref="synthetic-invalid-family", source_event_family=bad_family)
        c.execute("PRAGMA ignore_check_constraints=ON")
        c.execute("INSERT INTO device_network_metadata_edges (" + ",".join(row) + ") VALUES(" + ",".join("?" for _ in row) + ")", tuple(row.values()))
        with pytest.raises(ProjectionUnavailable):
            latest(state)
    finally:
        state.repo.close()


def test_same_timestamp_family_priority_and_minimum_edge_tie(tmp_path):
    state = seed(tmp_path, 1)
    try:
        c = state.repo.connection
        row = dict(c.execute("SELECT * FROM device_network_metadata_edges").fetchone())
        sql = "INSERT INTO device_network_metadata_edges (" + ",".join(row) + ") VALUES(" + ",".join("?" for _ in row) + ")"
        with state.repo.transaction():
            for number, family in enumerate(("quic", "tls", "dns", "dns"), start=1):
                extra = {**row, "edge_id": f"{number:064x}", "source_observation_ref": f"synthetic-tie-{number}",
                         "source_event_family": family, "event_at": ni_format_utc(AT - timedelta(microseconds=1))}
                c.execute(sql, tuple(extra.values()))
        facts = latest(state)["facts"]
        assert [row["source_event_family"] for row in facts] == list(FAMILIES)
        assert facts[0]["edge_id"] == f"{3:064x}"
        value = summary(state)
        assert value.last_protocol_observation.protocol_id == "dns"
        assert [row.protocol_id for row in value.recent_protocols] == list(FAMILIES)
    finally:
        state.repo.close()


def test_selected_noncanonical_timestamp_and_missing_index_fail_closed(tmp_path):
    state = seed(tmp_path, 1)
    try:
        c = state.repo.connection
        row = dict(c.execute("SELECT * FROM device_network_metadata_edges").fetchone())
        row.update(edge_id="f" * 64, source_observation_ref="synthetic-bad-time", event_at="2026-10-09T12:00:59Z")
        c.execute("INSERT INTO device_network_metadata_edges (" + ",".join(row) + ") VALUES(" + ",".join("?" for _ in row) + ")", tuple(row.values()))
        with pytest.raises(ProtocolUnavailable):
            summary(state)
        c.execute("DROP INDEX idx_projection_mac_family_event_latest")
        with pytest.raises(ProtocolUnavailable):
            summary(state)
    finally:
        state.repo.close()
