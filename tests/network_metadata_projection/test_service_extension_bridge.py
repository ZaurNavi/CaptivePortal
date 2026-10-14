"""G1 compatibility bridge: optional extension, exact core, unconditional upkeep."""
import sqlite3
import subprocess
from pathlib import Path
from dataclasses import replace

import pytest

from app.network_metadata_projection.repository import ProjectionRepository
from app.network_metadata_projection.models import RegistryEvaluation, ProjectionUnavailable
from app.network_metadata_projection.schema import validate_schema, signature, _expected_signatures
from app.network_metadata_projection.service_extension import TABLES, create_extension_objects
from app.network_metadata_projection.read_service import DeviceNetworkMetadataReadService
from app.network_metadata_projection.recognition_read_service import DeviceNetworkMetadataRecognitionReadService
from app.analytics.source_gateway import QueryDeadline
from .support import stack, source_record, SITE, MAC, OTHER_MAC
from .test_projection import edges

DEVICE = "10000000-0000-4000-8000-000000000001"
BASE = "b1442efc434716d35e21b9e3124c3b9cd2222fbe"


def install_fixture(state):
    """Disposable migrated fixture only; no production installer exists in G1."""
    with state.repo.transaction():
        create_extension_objects(state.repo.connection)
        state.repo.connection.execute(
            "INSERT INTO projection_registry_binding_change_index"
            "(site_id,client_mac,binding_state,device_id,evaluated_at_utc) "
            "SELECT site_id,client_mac,binding_state,device_id,last_evaluated_at "
            "FROM projection_site_mac_bindings WHERE binding_state='authoritative' ORDER BY site_id,client_mac")
        state.repo.connection.execute(
            "INSERT INTO projection_service_recognition_extension_meta VALUES(1,1,?)",
            ("2026-10-09T12:00:30.000000Z",))
        assert validate_schema(state.repo.connection) == "CORE_PLUS_EXTENSION_V1"
    state.repo.close()
    state.repo = ProjectionRepository(state.config, clock=state.clock).initialize()
    state.service.repository = state.repo


@pytest.fixture
def state(tmp_path):
    value = stack(tmp_path, [source_record(dst_ip="203.0.113.93")])
    value.attribution.states["203.0.113.93"] = "endpoint_absent"
    value.registry.values[MAC] = RegistryEvaluation("authoritative", DEVICE)
    try:
        yield value
    finally:
        value.repo.close()


def test_G1_R2_QA01_core_only_default_no_installer(state):
    assert validate_schema(state.repo.connection) == "CORE_ONLY"
    assert state.repo.service_recognition_extension_present is False
    state.service.poll()
    assert len(edges(state)) == 1
    assert not any(name in TABLES for _, name, _ in signature(state.repo.connection))
    assert state.repo.connection.execute("PRAGMA user_version").fetchone()[0] == 2


def test_G1_R2_QA02_R2_QA09_core_plus_extension_off_upkeep(state):
    install_fixture(state)
    assert state.repo.service_recognition_extension_present is True
    state.service.poll()
    rows = state.repo.connection.execute("SELECT * FROM projection_service_recognition_feed").fetchall()
    assert len(rows) == 1 and rows[0]["edge_id"] == edges(state)[0]["edge_id"]
    changes = state.repo.connection.execute("SELECT * FROM projection_registry_binding_change_index").fetchall()
    assert len(changes) == 1 and changes[0]["device_id"] == DEVICE
    assert validate_schema(state.repo.connection, integrity=True) == "CORE_PLUS_EXTENSION_V1"
    assert tuple(row for row in signature(state.repo.connection) if row[1] not in TABLES) == _expected_signatures()[0]


def test_G1_R2_QA03_old_baseline_is_not_rollback_floor(state):
    install_fixture(state)
    root = Path(__file__).resolve().parents[2]
    source = subprocess.check_output(["git", "show", BASE + ":app/network_metadata_projection/schema.py"], cwd=root)
    namespace = {"__package__": "app.network_metadata_projection", "__name__": "old_projection_schema"}
    exec(compile(source, "accepted_old_schema.py", "exec"), namespace)
    with pytest.raises(ProjectionUnavailable):
        namespace["validate_schema"](state.repo.connection)


@pytest.mark.parametrize("damage", [
    "CREATE TABLE alien(value TEXT)",
    "CREATE INDEX alien_index ON projection_pending_attribution(site_id)",
    "DROP INDEX idx_projection_mac_event",
    "DROP TRIGGER immutable_device_network_metadata_edges",
    "DELETE FROM projection_service_recognition_extension_meta",
    "PRAGMA user_version=1",
])
def test_G1_R2_QA06_QA07_QA08_closed_object_and_metadata_validation(state, damage):
    install_fixture(state)
    state.repo.connection.execute(damage)
    with pytest.raises(ProjectionUnavailable):
        validate_schema(state.repo.connection)


@pytest.mark.parametrize("name", list(TABLES))
def test_G1_partial_extension_never_repaired(state, name):
    state.repo.connection.execute(f"CREATE TABLE {name} ({TABLES[name]})")
    before = signature(state.repo.connection)
    with pytest.raises(ProjectionUnavailable):
        validate_schema(state.repo.connection)
    assert signature(state.repo.connection) == before


@pytest.mark.parametrize("point,committed", [("before_commit", False), ("after_commit", True)])
def test_G1_edge_feed_checkpoint_atomicity(state, point, committed):
    install_fixture(state)
    class Crash(BaseException):
        pass
    def crash(stage):
        if stage == point:
            raise Crash()
    state.repo.crash_point = crash
    with pytest.raises(Crash):
        state.service.poll()
    assert bool(edges(state)) == committed
    assert bool(state.repo.connection.execute("SELECT * FROM projection_service_recognition_feed").fetchall()) == committed
    assert bool(state.repo.connection.execute("SELECT * FROM projection_source_checkpoints").fetchall()) == committed
    state.repo.crash_point = lambda _: None
    state.service.poll()
    assert len(edges(state)) == 1
    assert state.repo.connection.execute("SELECT count(*) FROM projection_service_recognition_feed").fetchone()[0] == 1


def test_G1_idempotent_edge_replay_has_no_second_outbox(state):
    install_fixture(state)
    state.service.poll()
    original = edges(state)
    prepared = state.service.prepare(state.source.records[0])
    state.repo.commit_dispositions([prepared], {}, state.service.run_id)
    assert edges(state) == original
    assert state.repo.connection.execute("SELECT count(*) FROM projection_service_recognition_feed").fetchone()[0] == 1


def test_G1_legacy_projection_consumers_read_extension_without_semantic_change(state):
    install_fixture(state)
    state.service.poll()
    reader = DeviceNetworkMetadataReadService(state.config.db_path)
    first, last = "2026-10-08T13:00:00.000000Z", "2026-10-09T13:00:00.000000Z"
    snapshot = reader.read_protocol_evidence_snapshot(
        SITE, DEVICE, MAC, first, last, max_rows=20000, deadline=QueryDeadline.after(5))
    assert snapshot["binding_state"] == "authoritative" and len(snapshot["facts"]) == 1
    assert reader.list_edges_by_device(SITE, DEVICE, first, last)["items"][0]["device_id"] == DEVICE
    assert reader.get_status()["store_state"] == "available"
    recognition = DeviceNetworkMetadataRecognitionReadService(state.config.db_path).read_service_recognition_snapshot(
        SITE, DEVICE, MAC, first, last, max_rows=5000, deadline=QueryDeadline.after(5))
    assert recognition.schema_version == 2 and len(recognition.facts) == 1
    assert recognition.bound_device_id == DEVICE


def test_G1_R1_QA08_safe_reason_and_periodic_revalidation_do_not_allocate_sequence(state):
    install_fixture(state)
    state.service.poll()
    original = tuple(state.repo.connection.execute("SELECT * FROM projection_registry_binding_change_index").fetchone())
    state.clock.advance(seconds=30)
    state.service.reconcile()
    assert tuple(state.repo.connection.execute("SELECT * FROM projection_registry_binding_change_index").fetchone()) == original
    state.registry.values[MAC] = RegistryEvaluation("registry_unavailable", reason="registry_unavailable")
    state.service.reconcile()
    # Existing monotonic Core identity rule remains authoritative during outage.
    assert state.repo.binding(SITE, MAC)["binding_state"] == "authoritative"
    assert tuple(state.repo.connection.execute("SELECT * FROM projection_registry_binding_change_index").fetchone()) == original


def test_G1_retention_cascades_feed_and_binding_index(state):
    install_fixture(state)
    state.service.poll()
    state.clock.advance(days=14)
    state.service.retain()
    assert state.repo.connection.execute("SELECT count(*) FROM projection_service_recognition_feed").fetchone()[0] == 0
    assert state.repo.connection.execute("SELECT count(*) FROM projection_registry_binding_change_index").fetchone()[0] == 0


@pytest.mark.parametrize("changes", [
    {"src_ip": "203.0.113.93", "dst_ip": "10.73.0.7"},
    {"dst_ip": "10.73.0.8"},
    {"dst_ip": None, "dst_port": None},
])
def test_G1_ineligible_edges_never_enter_feed(state, changes):
    state.source.records = [replace(state.source.records[0], **changes)]
    install_fixture(state)
    state.service.poll()
    assert edges(state)
    assert state.repo.connection.execute("SELECT count(*) FROM projection_service_recognition_feed").fetchone()[0] == 0
