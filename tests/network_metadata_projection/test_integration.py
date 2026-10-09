"""Real upstream read boundaries and frozen projection maintenance matrix."""
import logging
import sqlite3
import uuid
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path

import pytest

from app.network_attribution.validation import make_fact
from app.network_metadata_projection.models import RegistryEvaluation, ProjectionConflict, ProjectionUnavailable
from app.network_metadata_projection.read_service import DeviceNetworkMetadataReadService
from app.network_metadata_projection.registry_adapter import RegistryAdapter
from app.network_metadata_projection.telemetry import ProjectionTelemetry
from app.network_metadata_projection.validation import timestamp
from tests.network_attribution.test_authority import store as authority_store, fact, SOURCE, ts
from tests.visitor_registry.test_device_registry import make_stack, append_event, fixture_event, event_for
from .support import stack, source_record, SITE, MAC, OTHER_MAC, GENERATION, T0


def test_real_ms_authority_exact_original_microsecond_event(authority_store, tmp_path):
    authority, reader, _ = authority_store
    values = asdict(fact(0, lease=1))
    values.pop("fact_id")
    values.pop("schema_version")
    values.update(ipv4="10.73.0.7", event_at="2026-10-09T12:00:00.123Z",
                  ingested_at="2026-10-09T12:00:00.123Z")
    admitted = authority.record(make_fact(**values))
    authority.confirm_capture(SITE, SOURCE, ts(2))
    value = stack(tmp_path, [source_record(dst_ip=None, dst_port=None)])
    try:
        calls = []
        original = reader.resolve_ipv4
        def resolve(site, address, event):
            calls.append((site, address, event))
            return original(site, address, event)
        reader.resolve_ipv4 = resolve
        value.service.attribution = reader
        before = authority.connection.total_changes
        result = value.service.poll()[0]
        edge = value.repo.existing_edges(value.source.records[0].observation_id)["src"]
        assert calls == [(SITE, "10.73.0.7", "2026-10-09T12:00:00.123456Z")]
        assert edge["event_at"] == calls[0][2] and len(edge["event_at"]) == 27
        assert edge["attribution_binding_id"] == admitted.binding_id
        assert edge["attribution_valid_from"] == "2026-10-09T12:00:00.123Z"
        assert result.projection_state == "complete" and result.emitted_edge_count == 1
        assert authority.connection.total_changes == before
    finally:
        value.repo.close()


def test_real_reassignment_uses_event_time_not_delivery(authority_store, tmp_path):
    authority, reader, _ = authority_store
    for milliseconds, mac in ((0, MAC), (1000, OTHER_MAC)):
        values = asdict(fact(0))
        values.pop("fact_id")
        values.pop("schema_version")
        values.update(ipv4="10.73.0.7", client_mac=mac, event_at=ts(milliseconds / 1000), ingested_at=ts(3))
        authority.record(make_fact(**values))
    authority.confirm_capture(SITE, SOURCE, ts(4))
    records = [source_record(0, event_at="2026-10-09T12:00:00.999999Z", dst_ip=None, dst_port=None),
               source_record(1, event_at="2026-10-09T12:00:01.000000Z", dst_ip=None, dst_port=None)]
    value = stack(tmp_path, records)
    try:
        value.service.attribution = reader
        value.service.poll()
        before = value.repo.existing_edges(records[0].observation_id)["src"]
        after = value.repo.existing_edges(records[1].observation_id)["src"]
        assert before["client_mac"] == MAC and after["client_mac"] == OTHER_MAC
        assert before["attribution_binding_id"] != after["attribution_binding_id"]
        assert before["attribution_valid_until"] == after["attribution_valid_from"] == ts(1)
    finally:
        value.repo.close()


def test_real_registry_adapter_exact_authority_no_initialization_or_write(tmp_path):
    config, _, repository, reader, _ = make_stack(tmp_path)
    adapter = RegistryAdapter(config.db_path)
    assert adapter.evaluate("02:11:22:33:44:55").state == "not_yet_registry_resolved"
    append_event(config.source_log_path, fixture_event())
    assert reader.scan().complete
    expected = repository.get_device_by_mac("02:11:22:33:44:55")
    before = Path(config.db_path).read_bytes()
    result = adapter.evaluate(expected["mac"])
    assert result == RegistryEvaluation("authoritative", expected["device_id"], expected["updated_at"])
    assert adapter.reader.get_status()["available"]
    assert Path(config.db_path).read_bytes() == before
    assert repository.get_device_by_mac(expected["mac"]) == expected
    with sqlite3.connect(config.db_path) as connection:
        connection.execute("PRAGMA user_version=2")
    assert adapter.evaluate(expected["mac"]).state == "registry_unavailable"
    absent = tmp_path / "absent.sqlite3"
    assert RegistryAdapter(str(absent)).evaluate(MAC).state == "registry_unavailable"
    assert not absent.exists()


def test_two_sites_same_mac_same_device_and_cross_mac_conflict(tmp_path):
    records = [source_record(dst_ip=None, dst_port=None),
               source_record(1, site_id="f" * 24, dst_ip=None, dst_port=None)]
    value = stack(tmp_path, records)
    try:
        device_id = str(uuid.uuid4())
        value.registry.values[MAC] = RegistryEvaluation("authoritative", device_id)
        value.service.poll()
        assert value.repo.connection.execute("SELECT count(*) FROM projection_registry_identities").fetchone()[0] == 1
        assert value.repo.connection.execute("SELECT count(*) FROM projection_site_mac_bindings").fetchone()[0] == 2
        read = DeviceNetworkMetadataReadService(value.config.db_path)
        for record in records:
            items = read.list_edges_by_device(record.site_id, device_id, timestamp(T0), timestamp(T0 + timedelta(hours=1)))["items"]
            assert len(items) == 1 and items[0]["site_id"] == record.site_id
        value.source.records.append(source_record(2, src_ip="10.73.0.8", dst_ip=None, dst_port=None))
        value.registry.values[OTHER_MAC] = RegistryEvaluation("authoritative", device_id)
        value.service.poll()
        assert value.repo.live_reason == "registry_identity_conflict"
        assert value.repo.checkpoint(GENERATION)["last_record_start_byte_offset"] == 1
    finally:
        value.repo.close()


@pytest.mark.parametrize("unresolved,authoritative,expected_u,expected_a", [
    (450, 150, 400, 100), (50, 500, 50, 450), (500, 50, 450, 50), (0, 501, 0, 500), (501, 0, 500, 0)])
def test_reconcile_two_lanes_deterministic_spillover(tmp_path, unresolved, authoritative, expected_u, expected_a):
    value = stack(tmp_path)
    try:
        now = timestamp(value.clock())
        with value.repo.transaction():
            for number in range(unresolved + authoritative):
                mac = f"00:10:20:30:{number // 256:02X}:{number % 256:02X}"
                resolved = number >= unresolved
                evaluation = RegistryEvaluation("authoritative", str(uuid.uuid4())) if resolved else RegistryEvaluation(
                    "registry_unavailable" if number % 2 else "not_yet_registry_resolved",
                    reason="registry_unavailable" if number % 2 else None)
                value.repo._registry_binding(SITE, mac, evaluation, value.service.run_id, now, edge_at=now)
        selected = value.repo.reconcile_selection()
        assert len(selected) == expected_u + expected_a <= 500
        keys = [(row["site_id"], row["client_mac"]) for row in selected]
        assert len(set(keys)) == len(keys)
        assert sum(row["binding_state"] == "authoritative" for row in selected) == expected_a
        unresolved_rows = selected[:expected_u]
        assert list(unresolved_rows) == sorted(unresolved_rows, key=lambda row: (
            row["binding_state"] != "not_yet_registry_resolved", row["last_evaluated_at"], row["site_id"], row["client_mac"]))
        assert keys == [(row["site_id"], row["client_mac"]) for row in value.repo.reconcile_selection()]
        evaluations = {key: RegistryEvaluation("authoritative", str(uuid.uuid4())) if row["binding_state"] != "authoritative"
            else RegistryEvaluation("authoritative", row["device_id"]) for key, row in zip(keys, selected)}
        value.repo.reconcile(selected, evaluations, value.service.run_id)
        assert all(value.repo.binding(*key)["binding_state"] == "authoritative" for key in keys)
        # The already-preselected pass visits each identity exactly once.
        assert len(keys) == len(evaluations)
    finally:
        value.repo.close()


def test_read_keyset_exact_contract_readonly_no_upstream(tmp_path):
    value = stack(tmp_path, [source_record(index, dst_ip=None, dst_port=None) for index in range(4)])
    try:
        value.service.poll()
        def forbidden(*args, **kwargs):
            pytest.fail("query-time upstream access")
        value.attribution.resolve_ipv4 = value.registry.evaluate = value.registry.evaluate_many = value.source.get_projection_source_record = forbidden
        read = DeviceNetworkMetadataReadService(value.config.db_path)
        before = value.repo.connection.total_changes
        cursor, ids = None, []
        while True:
            page = read.list_edges_by_mac(SITE, MAC, timestamp(T0), timestamp(T0 + timedelta(hours=1)), limit=1, cursor=cursor)
            ids.extend(item["edge_id"] for item in page["items"])
            assert set(page["items"][0]["device_endpoint"]) == {"ip", "port", "transport_protocol"}
            assert "record_start_byte_offset" not in page["items"][0]
            cursor = page["next_cursor"]
            if cursor is None:
                break
        assert len(ids) == len(set(ids)) == 4 and ids == sorted(ids)
        with read._snapshot() as connection:
            assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
            with pytest.raises(sqlite3.OperationalError):
                connection.execute("DELETE FROM projection_source_checkpoints")
        assert value.repo.connection.total_changes == before
    finally:
        value.repo.close()


@pytest.mark.parametrize("point,committed", [("before_commit", False), ("after_commit", True)])
def test_retry_crash_atomicity(tmp_path, point, committed):
    value = stack(tmp_path)
    class Crash(BaseException):
        pass
    try:
        value.attribution.states = {"10.73.0.7": "resolved", "10.73.0.8": "unavailable"}
        value.service.poll()
        old = value.repo.existing_edges(value.source.records[0].observation_id)["src"]
        checkpoint = dict(value.repo.checkpoint(GENERATION))
        value.clock.advance(seconds=30)
        value.attribution.states.clear()
        def crash(stage):
            if stage == point:
                raise Crash()
        value.repo.crash_point = crash
        with pytest.raises(Crash):
            value.service.retry()
        current = value.repo.existing_edges(value.source.records[0].observation_id)
        assert ("dst" in current) == committed and current["src"] == old
        assert dict(value.repo.checkpoint(GENERATION)) == checkpoint
        value.repo.crash_point = lambda _: None
        value.service.retry()
        assert len(value.repo.existing_edges(value.source.records[0].observation_id)) == 2
    finally:
        value.repo.close()


@pytest.mark.parametrize("age_field", ["event_at", "ingested_at"])
def test_exact_sensitive_cutoff_not_extended_by_projection_binding(tmp_path, age_field):
    value = stack(tmp_path)
    try:
        boundary = value.clock() - timedelta(days=14)
        record = source_record(**{age_field: timestamp(boundary)})
        value.source.records = [record]
        # A read-only horizon earlier than this fixture permits exact-boundary projection.
        value.attribution.get_authority_horizon = lambda site: type("H", (), {
            "state": "available", "first_usable_at": "2026-01-01T00:00:00.000Z", "retained_from": "2026-01-01T00:00:00.000Z"})()
        if age_field == "event_at":
            original = value.attribution.resolve_ipv4
            value.attribution.resolve_ipv4 = lambda site, address, event: replace(original(site, address, event),
                valid_from="2026-01-01T00:00:00.000Z", valid_until="2026-12-01T00:00:00.000Z")
        value.service.poll()
        assert len(value.repo.existing_edges(record.observation_id)) == 2
        value.service.retain()
        assert len(value.repo.existing_edges(record.observation_id)) == 2
        value.clock.advance(microseconds=1)
        value.registry.values[MAC] = RegistryEvaluation("authoritative", str(uuid.uuid4()))
        value.service.reconcile()
        value.service.retain()
        assert value.repo.existing_edges(record.observation_id) == {}
    finally:
        value.repo.close()


@pytest.mark.parametrize("source_state,expected", [("not_observed", "terminal_no_edge"), ("expired", "terminal_no_edge")])
def test_ineligible_source_no_attribution_or_private_reconstruction(tmp_path, source_state, expected):
    value = stack(tmp_path, [source_record(sensitive_endpoint_presence_state=source_state, src_ip=None, dst_ip=None)])
    try:
        assert value.service.poll()[0].projection_state == expected
        assert value.attribution.calls == []
        assert not value.repo.existing_edges(value.source.records[0].observation_id)
    finally:
        value.repo.close()


def test_failure_diagnostics_survive_maintenance_and_no_sensitive_logs(tmp_path, caplog):
    value = stack(tmp_path)
    try:
        value.service.telemetry = ProjectionTelemetry(logging.getLogger("ni02b-test"))
        value.source.fail = True
        with caplog.at_level(logging.INFO):
            value.service.tick()
        assert value.repo.live_state == "source_unavailable"
        assert "source-private-sentinel" not in caplog.text
        for secret in (MAC, "10.73.0.7", "10.73.0.8"):
            assert secret not in caplog.text
        with pytest.raises(ValueError):
            value.service.telemetry.emit("batch_committed", src_ip="10.73.0.7")
        for table in ("device_network_metadata_edges", "projection_pending_attribution"):
            fields = {row[1] for row in value.repo.connection.execute("PRAGMA table_info(" + table + ")")}
            assert not {"dns", "sni", "raw_json", "raw_dhcp_frame"} & fields
        value.source.fail = False
        value.attribution.get_authority_horizon = lambda _: type("H", (), {"state": "unavailable"})()
        value.service.poll()
        assert value.repo.live_state == "attribution_unavailable" and value.repo.pending() == []  # not due yet
        value.registry.values[MAC] = RegistryEvaluation("registry_unavailable", reason="registry_unavailable")
        value.service.reconcile()
        assert value.repo.live_state == "attribution_unavailable"
    finally:
        value.repo.close()


@pytest.mark.parametrize("role", ["src", "dst"])
def test_private_outside_scope_peer_is_external_not_automatically_local(tmp_path, role):
    changes = {("dst" if role == "src" else "src") + "_ip": "192.168.50.2"}
    value = stack(tmp_path, [source_record(**changes)])
    try:
        value.attribution.states["192.168.50.2"] = "unattributed"
        value.service.poll()
        edge = value.repo.existing_edges(value.source.records[0].observation_id)[role]
        assert edge["peer_scope"] == "external"
        assert edge["direction"] == ("outbound" if role == "src" else "inbound")
    finally:
        value.repo.close()


def test_pending_terminal_result_preserves_previously_created_edge(tmp_path):
    value = stack(tmp_path)
    try:
        value.attribution.states["10.73.0.8"] = "unavailable"
        assert value.service.poll()[0].projection_state == "partial_pending"
        old = value.repo.existing_edges(value.source.records[0].observation_id)
        value.clock.advance(seconds=30)
        value.attribution.states["10.73.0.8"] = "ambiguous"
        result = value.service.retry()[0]
        assert result.projection_state == "complete" and result.emitted_edge_count == 1
        assert value.repo.existing_edges(value.source.records[0].observation_id) == old
        assert not value.repo.pending()
    finally:
        value.repo.close()


def test_registry_outage_does_not_block_first_edges_or_checkpoint(tmp_path):
    value = stack(tmp_path)
    try:
        value.registry.values = {mac: RegistryEvaluation("registry_unavailable", reason="registry_unavailable") for mac in (MAC, OTHER_MAC)}
        value.service.poll()
        assert len(value.repo.existing_edges(value.source.records[0].observation_id)) == 2
        assert value.repo.checkpoint(GENERATION)["last_record_start_byte_offset"] == 0
        assert value.repo.live_state == "registry_degraded"
        value.registry.values[MAC] = RegistryEvaluation("authoritative", str(uuid.uuid4()))
        value.service.reconcile()
        assert value.repo.binding(SITE, MAC)["binding_state"] == "authoritative"
    finally:
        value.repo.close()


def test_before_authority_horizon_no_fabrication(tmp_path):
    value = stack(tmp_path)
    try:
        value.attribution.get_authority_horizon = lambda site: type("H", (), {
            "state": "available", "first_usable_at": ts(1), "retained_from": ts(1)})()
        result = value.service.poll()[0]
        assert result.src_attribution_state == result.dst_attribution_state == "outside_historical_horizon"
        assert result.projection_state == "terminal_no_edge"
        assert value.attribution.calls == []
        assert value.repo.checkpoint(GENERATION)["last_record_start_byte_offset"] == 0
    finally:
        value.repo.close()


def test_stop_during_preparation_has_no_partial_transaction(tmp_path):
    value = stack(tmp_path, [source_record(index) for index in range(3)])
    try:
        original = value.attribution.resolve_ipv4
        def stop(site, address, event):
            value.service.stop()
            return original(site, address, event)
        value.attribution.resolve_ipv4 = stop
        assert value.service.poll() == ()
        assert value.repo.checkpoint(GENERATION) is None
        assert value.repo.connection.execute("SELECT count(*) FROM device_network_metadata_edges").fetchone()[0] == 0
        assert value.service.poll() is None
    finally:
        value.repo.close()


def test_projection_db_failure_does_not_call_upstream_writers(tmp_path):
    value = stack(tmp_path)
    try:
        before = list(value.source.records)
        value.repo.connection.execute("PRAGMA query_only=ON")
        with pytest.raises(ProjectionUnavailable):
            value.service.poll()
        assert value.repo.checkpoint(GENERATION) is None
        assert value.source.records == before
        assert not value.repo.existing_edges(before[0].observation_id)
    finally:
        value.repo.close()


def test_checkpoint_conflict_no_later_record_advance(tmp_path):
    value = stack(tmp_path)
    try:
        value.service.poll()
        value.source.records.append(source_record(1))
        value.repo.connection.execute("UPDATE projection_source_checkpoints SET last_observation_id=?", (str(uuid.uuid4()),))
        value.source.records = value.source.records[1:]
        value.service.poll()
        assert value.repo.live_reason == "checkpoint_source_conflict"
        assert value.repo.checkpoint(GENERATION)["last_record_start_byte_offset"] == 0
        assert value.repo.existing_edges(value.source.records[0].observation_id) == {}
    finally:
        value.repo.close()


def test_reopen_durable_projection_checkpoint_and_no_replay_refresh(tmp_path):
    from app.network_metadata_projection.repository import ProjectionRepository
    value = stack(tmp_path)
    try:
        value.service.poll()
        original = value.repo.existing_edges(value.source.records[0].observation_id)
        checkpoint = dict(value.repo.checkpoint(GENERATION))
        value.repo.close()
        value.repo = ProjectionRepository(value.config, clock=value.clock).initialize()
        value.service.repository = value.repo
        value.clock.advance(seconds=30)
        value.service.poll()
        assert dict(value.repo.checkpoint(GENERATION)) == checkpoint
        assert value.repo.existing_edges(value.source.records[0].observation_id) == original
        value.source.records.append(source_record(1))
        value.service.poll()
        assert value.repo.checkpoint(GENERATION)["last_record_start_byte_offset"] == 1
        assert value.repo.existing_edges(value.source.records[0].observation_id) == original
    finally:
        value.repo.close()


def test_binding_event_30d_run_and_invisible_checkpoint_90d_gc(tmp_path):
    value = stack(tmp_path)
    try:
        value.service.poll()
        run_id = value.service.run_id
        value.clock.advance(days=30)
        value.service.retain()
        assert value.repo.connection.execute("SELECT count(*) FROM projection_registry_binding_events").fetchone()[0] == 2
        value.clock.advance(microseconds=1)
        value.service.retain()
        assert value.repo.connection.execute("SELECT count(*) FROM projection_registry_binding_events").fetchone()[0] == 0
        value.clock.advance(days=60)
        value.service.retain()
        assert value.repo.checkpoint(GENERATION) is not None  # still-visible source generation
        assert value.repo.connection.execute("SELECT 1 FROM projection_runs WHERE projection_run_id=?", (run_id,)).fetchone() is not None
        # The live worker still references its run. A later startup releases it.
        value.service.run_id = value.repo.create_run(type("I", (), {"artifact_sha": "a" * 40, "artifact_tree": "b" * 40})())
        value.service.retain()
        assert value.repo.connection.execute("SELECT 1 FROM projection_runs WHERE projection_run_id=?", (run_id,)).fetchone() is None
        value.source.records = []
        value.service.retain()
        assert value.repo.checkpoint(GENERATION) is None
    finally:
        value.repo.close()
