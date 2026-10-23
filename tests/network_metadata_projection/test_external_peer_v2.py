"""Owner T01–T11 / V2 regression fixtures: entirely disposable, no live reset."""
from tests.network_metadata import requires_posix_io
import hashlib
import json
import shutil
import sqlite3
import subprocess
import time
import uuid
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.analytics.source_gateway import QueryDeadline
from app.network_metadata.config import make_capture_scope_binding
from app.network_metadata.projection_source import NetworkMetadataProjectionSourceReadService
from app.network_metadata.models import NetworkMetadataStorageUnavailable
from app.network_metadata_projection.config import ScopeAdmission, projection_config_from_env
from app.network_metadata_projection.models import ProjectionConfig, ProjectionConflict, ProjectionUnavailable, ALGORITHM, EndpointDisposition, RegistryEvaluation
from app.network_metadata_projection.repository import ProjectionRepository
from app.network_metadata_projection.schema import validate_schema, signature
from app.network_metadata_projection.service import NetworkMetadataProjectionService
from app.network_metadata_projection.service_extension import install_service_recognition_extension
from app.network_metadata_projection.service_delivery_read_service import ServiceRecognitionDeliveryReadService
from app.network_metadata_projection.read_service import DeviceNetworkMetadataReadService
from app.network_metadata_projection.validation import timestamp
from app.network_metadata_projection.telemetry import ProjectionTelemetry
from scripts.ni02b_v2_offline_bootstrap import prepare, verify, inspect_paths, BootstrapHold
from tests.network_metadata import store, record, source_event, outcome, BOOT
from .support import stack, source_record, scope_admission, SITE, MAC, IDENTITY, GENERATION, Clock, Attribution, Registry

BASE = "f324c1e157b71802acda14a797c0e0f6747b6276"


@pytest.mark.parametrize("role,address", [(role, address) for role in ("src", "dst")
    for address in ("203.0.113.93", "192.168.50.2", "172.16.1.1")])
def test_T01_T02_V2_01_02_external_terminal_no_dhcp_or_phantom_edge(tmp_path, role, address):
    other = "dst" if role == "src" else "src"
    value = stack(tmp_path, [source_record(**{other + "_ip": address})])
    try:
        install_service_recognition_extension(value.repo)
        result, = value.service.poll()
        edge, = value.repo.existing_edges(result.observation_id).values()
        assert result.emitted_edge_count == 1 and result.projection_state == "complete"
        assert getattr(result, other + "_attribution_state") == "not_applicable_outside_guest_scope"
        assert [call[1] for call in value.attribution.calls] == [getattr(value.source.records[0], role + "_ip")]
        assert edge["device_endpoint_role"] == role and edge["site_id"] == SITE
        assert edge["event_at"] == value.source.records[0].event_at
        assert edge["peer_scope"] == "external" and edge["direction"] == ("outbound" if role == "src" else "inbound")
        assert edge["peer_attribution_binding_id"] is None
        assert edge["projection_contract_version"] == 2 and edge["schema_version"] == 1
        assert edge["projection_algorithm_version"] == ALGORITHM
        assert not value.repo.connection.execute("SELECT 1 FROM projection_pending_attribution").fetchone()
        assert value.repo.connection.execute("SELECT count(*) FROM projection_service_recognition_feed").fetchone()[0] == (role == "src")
    finally:
        value.repo.close()


@pytest.mark.parametrize("states,count,pending", [(("resolved", "resolved"), 2, 0),
    (("resolved", "unattributed"), 1, 0), (("ambiguous", "unattributed"), 0, 0),
    (("resolved", "unavailable"), 1, 1), (("unavailable", "unavailable"), 0, 1)])
def test_T03_V2_03_guest_both_exact_temporal_calls(tmp_path, states, count, pending):
    value = stack(tmp_path)
    try:
        value.attribution.states = dict(zip(("10.73.0.7", "10.73.0.8"), states))
        result, = value.service.poll()
        assert result.emitted_edge_count == count
        assert [call[1] for call in value.attribution.calls] == ["10.73.0.7", "10.73.0.8"]
        assert all(call[0] == SITE and call[2] == value.source.records[0].event_at for call in value.attribution.calls)
        assert value.repo.connection.execute("SELECT count(*) FROM projection_pending_attribution").fetchone()[0] == pending
    finally:
        value.repo.close()


def test_T05_T08_V2_04_guest_gap_only_guest_retry_and_honest_unavailable(tmp_path):
    value = stack(tmp_path, [source_record(dst_ip="203.0.113.93")])
    try:
        value.attribution.states["10.73.0.7"] = "unavailable"
        result, = value.service.poll()
        pending, = value.repo.connection.execute("SELECT * FROM projection_pending_attribution")
        assert pending["pending_src"] == 1 and pending["pending_dst"] == 0
        assert pending["dst_snapshot_state"] == "not_applicable_outside_guest_scope"
        assert result.emitted_edge_count == 0 and value.repo.live_state == "attribution_unavailable"
        assert DeviceNetworkMetadataReadService(value.config.db_path).get_status()["runtime_state"] == "attribution_unavailable"
        for _ in range(3):
            value.clock.advance(seconds=30)
            value.service.retry()
        assert all(call[1] == "10.73.0.7" for call in value.attribution.calls)
        value.attribution.states.clear()
        value.clock.advance(seconds=30)
        value.service.retry()
        edge = value.repo.existing_edges(result.observation_id)["src"]
        value.clock.advance(seconds=30)
        value.service.retry()
        assert value.repo.existing_edges(result.observation_id)["src"] == edge
        assert value.repo.connection.execute("SELECT count(*) FROM projection_pending_attribution").fetchone()[0] == 0
    finally:
        value.repo.close()


@pytest.mark.parametrize("changes", [dict(site_id="f" * 24), dict(capture_source_id="wrong"),
    dict(network_scope_id="wrong"), dict(capture_scope_binding_digest="f" * 64),
    dict(binding_valid_from_utc="2026-10-09T13:00:00.000000Z"),
    dict(capture_scope_ipv4_cidrs=("10.74.0.0/16",)), dict(network_scope_state="unknown"),
    dict(event_at="2025-12-31T23:59:59.999999Z")])
def test_T04_V2_05_scope_conflict_blocks_entire_batch(tmp_path, changes):
    value = stack(tmp_path)
    try:
        value.source.records.append(replace(source_record(1), **changes))
        value.service.poll()
        assert value.repo.live_reason == "scope_admission_untrusted"
        assert value.repo.checkpoint(GENERATION) is None
        for table in ("device_network_metadata_edges", "projection_pending_attribution"):
            assert not value.repo.connection.execute(f"SELECT 1 FROM {table}").fetchone()
    finally:
        value.repo.close()


@pytest.mark.parametrize("mutation", ["missing", "post_nat", "duplicate", "overlap", "wrong_digest", "bool", "extra", "wildcard"])
def test_V2_05_06_closed_manifest_not_guessed(mutation):
    value = json.loads(scope_admission())
    if mutation == "missing":
        value["scopes"] = []
    elif mutation == "post_nat":
        value["placement_kind"] = "post_nat"
    elif mutation == "duplicate":
        value["scopes"] *= 2
    elif mutation in {"overlap", "wildcard"}:
        value["scopes"][0]["ipv4_cidrs"] = ["10.73.0.0/16", "10.73.0.0/24"] if mutation == "overlap" else ["0.0.0.0/0"]
    elif mutation == "wrong_digest":
        value["scopes"][0]["capture_scope_binding_digest"] = "f" * 64
    elif mutation == "bool":
        value["schema_version"] = True
    else:
        value["allow_any"] = True
    with pytest.raises(ProjectionConflict, match="scope_admission_untrusted"):
        ScopeAdmission(json.dumps(value))


def test_V2_admission_deterministic_strict_json_and_restart_pin(tmp_path):
    value = stack(tmp_path)
    try:
        canonical = ScopeAdmission(scope_admission())
        assert ScopeAdmission(canonical.canonical).digest == canonical.digest
        for encoded in ('{"schema_version":1,"schema_version":1}', '{"schema_version":NaN}'):
            with pytest.raises(ProjectionConflict):
                ScopeAdmission(encoded)
        value.repo.close()
        changed = scope_admission([source_record(site_id="f" * 24)])
        with pytest.raises(ProjectionUnavailable):
            ProjectionRepository(replace(value.config, scope_admission_json=changed)).initialize()
        value.repo = ProjectionRepository(value.config, clock=value.clock).initialize()
        assert value.repo.connection.execute("SELECT admission_digest FROM projection_scope_admission").fetchone()[0] == canonical.digest
        with pytest.raises(sqlite3.Error):
            value.repo.connection.execute("UPDATE projection_scope_admission SET admission_digest=?", ("f" * 64,))
    finally:
        value.repo.close()


@pytest.mark.parametrize("peer,state", [(None, "endpoint_absent"), ("2001:db8::1", "unsupported_address_family")])
def test_T04_V2_06_ipv6_absence_distinct_no_lookup(tmp_path, peer, state):
    value = stack(tmp_path, [source_record(dst_ip=peer, dst_port=None)])
    try:
        result, = value.service.poll()
        assert result.dst_attribution_state == state and len(value.attribution.calls) == 1
        assert value.repo.existing_edges(result.observation_id)["src"]["peer_scope"] == "unknown"
        assert not isinstance(EndpointDisposition(state), type(value.attribution.resolve_ipv4(SITE, "10.73.0.7", source_record().event_at)))
    finally:
        value.repo.close()


def admitted_source(source):
    binding = source.config.capture_scope_binding
    return json.dumps(dict(schema_version=1, placement_kind="verified_pre_nat_guest_ipv4", scopes=[dict(
        site_id=binding.site_id, capture_source_id=binding.capture_source_id, network_scope_id=binding.network_scope_id,
        capture_scope_binding_digest=binding.binding_digest, ipv4_cidrs=list(binding.ipv4_cidrs),
        binding_valid_from_utc=binding.valid_from_utc)]))


def seed_source(source, *, data=None, start=0, generation=None):
    item = outcome(source.config.capture_scope_binding, data=data, start=start,
                   generation=generation or source.generation.source_generation_id)
    source.repo.ingest_batch([item], source.run, source.health, source.anchor)
    return item


@requires_posix_io
def test_V2_08_consistent_read_only_tail_not_raw_length_and_empty_generation(tmp_path):
    with store(tmp_path) as source:
        reader = NetworkMetadataProjectionSourceReadService(source.config.db_path)
        admission = ScopeAdmission(admitted_source(source))
        empty, = reader.read_reset_snapshot(admission=admission)
        assert empty["last_retained_record_start_byte_offset"] is empty["last_retained_observation_id"] is None
        seed_source(source)
        before = source.repo.connection.total_changes
        floor, = reader.read_reset_snapshot(admission=admission)
        assert floor["last_retained_record_start_byte_offset"] == 0
        assert floor["last_retained_observation_id"] == reader.read_projection_batch(source.generation.source_generation_id, None, 1)[0].observation_id
        assert source.repo.connection.total_changes == before
        assert floor["last_retained_record_start_byte_offset"] != Path(source.config.source_path).stat().st_size


def staged(source, tmp_path, suffix="stage"):
    keep = [source.config.db_path, str(tmp_path / "protected-attribution.sqlite3"), str(tmp_path / "protected-registry.sqlite3")]
    for path in keep[1:]:
        Path(path).write_bytes(b"synthetic protected sentinel")
    manifest = prepare(staging_dir=str(tmp_path / suffix), source_path=source.config.db_path,
        projection_target=str(tmp_path / "target-projection.sqlite3"),
        materialization_target=str(tmp_path / "target-ni04.sqlite3"), keep_paths=keep,
        admission_json=admitted_source(source), writers_stopped=True, readers_drained=True)
    return manifest, keep


@requires_posix_io
def test_T06_T07_V2_08_09_reset_append_restart_no_pre_reset_replay(tmp_path):
    data = record(source_event(dest_ip="203.0.113.93"))
    with store(tmp_path, source=(data+b"\n")*3) as source:
        seed_source(source, data=data)
        manifest, keep = staged(source, tmp_path)
        floor = json.loads(Path(tmp_path / "stage" / "prepared-pair.json").read_text())
        assert floor == manifest
        seed_source(source, data=data, start=len(data)+1)
        clock = Clock()
        clock.value = source.clock() + timedelta(minutes=1)  # Post-reset input is within the native 24h horizon.
        config = ProjectionConfig(enabled=True, db_path=manifest["projection"]["path"],
            source_db_path=source.config.db_path, scope_admission_json=admitted_source(source))
        repo = ProjectionRepository(config, clock=clock).initialize()
        try:
            assert not repo.connection.execute("SELECT 1 FROM projection_source_checkpoints").fetchone()
            authority = Attribution()
            authority.get_authority_horizon = lambda site: SimpleNamespace(state="available",
                first_usable_at="2026-01-01T00:00:00.000Z", retained_from="2026-01-01T00:00:00.000Z")
            original = authority.resolve_ipv4
            authority.resolve_ipv4 = lambda *args: replace(original(*args), valid_from="2026-01-01T00:00:00.000Z")
            service = NetworkMetadataProjectionService(config, repo,
                NetworkMetadataProjectionSourceReadService(source.config.db_path), authority, Registry(), IDENTITY)
            service.run_id = repo.create_run(IDENTITY)
            result, = service.poll()
            assert result.emitted_edge_count == 1
            assert repo.checkpoint(source.generation.source_generation_id)["last_record_start_byte_offset"] == len(data)+1
            assert repo.reset_floor(source.generation.source_generation_id)["last_retained_record_start_byte_offset"] == 0
            before = tuple(repo.connection.iterdump())
            service.poll()
            assert repo.connection.execute("SELECT count(*) FROM device_network_metadata_edges").fetchone()[0] == 1
            assert repo.connection.execute("SELECT count(*) FROM projection_service_recognition_feed").fetchone()[0] == 1
            assert before != ()
        finally:
            repo.close()
        with pytest.raises(BootstrapHold):
            verify(manifest_path=str(tmp_path / "stage" / "prepared-pair.json"), admission_json=admitted_source(source))
        assert all(Path(path).read_bytes() == b"synthetic protected sentinel" for path in keep[1:])


def test_V2_10_reset_install_crash_whole_boundary_rollback(tmp_path):
    value = stack(tmp_path)
    try:
        # Fresh-store requirement is real: a run is already present.
        with pytest.raises(ProjectionUnavailable):
            value.repo.install_reset_floors((), reset_epoch_id=str(uuid.uuid4()), reset_at_utc=timestamp(value.clock()))
        assert value.repo.connection.execute("SELECT count(*) FROM projection_source_reset_epoch").fetchone()[0] == 0
    finally:
        value.repo.close()
    config = replace(value.config, db_path=str(tmp_path / "fresh.sqlite3"))
    repo = ProjectionRepository(config).initialize()
    class Crash(BaseException):
        pass
    try:
        repo.crash_point = lambda point: (_ for _ in ()).throw(Crash()) if point == "before_commit" else None
        with pytest.raises(Crash):
            repo.install_reset_floors((), reset_epoch_id=str(uuid.uuid4()), reset_at_utc=timestamp(value.clock()))
        assert repo.connection.execute("SELECT count(*) FROM projection_source_reset_epoch").fetchone()[0] == 0
        assert not repo.connection.execute("SELECT 1 FROM projection_source_checkpoints").fetchone()
    finally:
        repo.close()


def test_V2_07_11_frozen_old_schema_rejects_terminal_and_new_core(tmp_path):
    root = Path(__file__).resolve().parents[2]
    models = subprocess.check_output(["git", "show", BASE+":app/network_metadata_projection/models.py"], cwd=root).decode()
    schema = subprocess.check_output(["git", "show", BASE+":app/network_metadata_projection/schema.py"], cwd=root).decode()
    namespace = {"__name__": "frozen_v1", "__package__": "app.network_metadata_projection"}
    exec(compile(models, "frozen_v1_models.py", "exec"), namespace)
    schema = schema.replace("from .models import ALGORITHM, ATTRIBUTION_STATES, RUNTIME_STATES, ProjectionUnavailable", "")
    exec(compile(schema, "frozen_v1_schema.py", "exec"), namespace)
    old = sqlite3.connect(tmp_path / "v1.sqlite3")
    old.execute("PRAGMA journal_mode=WAL")
    old.execute("PRAGMA foreign_keys=ON")
    namespace["create_schema"](old, "2026-10-09T12:00:00.000000Z")
    old.commit()
    before = tuple(old.iterdump())
    with pytest.raises(ProjectionUnavailable):
        validate_schema(old)
    assert tuple(old.iterdump()) == before
    assert "not_applicable_outside_guest_scope" not in namespace["STATES"]
    old.close()
    value = stack(tmp_path)
    try:
        with pytest.raises(namespace["ProjectionUnavailable"]):
            namespace["validate_schema"](value.repo.connection)
        item = value.service.prepare(source_record(dst_ip="203.0.113.93"))
        invalid = dict(item.edges[0], peer_attribution_state="invented")
        with pytest.raises(ProjectionUnavailable):
            value.repo.commit_dispositions([(item.source, [invalid], None)], value.service._evaluations([item]), value.service.run_id)
        assert not value.repo.existing_edges(item.source.observation_id)
    finally:
        value.repo.close()


def test_T06_T07_V2_12_inert_pair_verify_rejects_partial_or_changed_db(tmp_path):
    with store(tmp_path) as source:
        manifest, keep = staged(source, tmp_path)
        report = verify(manifest_path=str(tmp_path / "stage" / "prepared-pair.json"), admission_json=admitted_source(source))
        assert report["state"] == "PREPARED" and not report["activation_authorized"]
        with pytest.raises(BootstrapHold):
            prepare(staging_dir=str(tmp_path / "other"), source_path=source.config.db_path,
                projection_target=manifest["projection_target"], materialization_target=manifest["materialization_target"],
                keep_paths=keep, admission_json=admitted_source(source), writers_stopped=True, readers_drained=False)
        assert not (tmp_path / "other").exists()
        # Disposable simulation only: one switched DB never constitutes a pair.
        shutil.copyfile(manifest["projection"]["path"], manifest["projection_target"])
        interrupted = dict(manifest, state="REPLACED_NOT_STARTED",
            projection=dict(manifest["projection"], path=manifest["projection_target"]))
        path = tmp_path / "interrupted.json"
        path.write_text(json.dumps(interrupted))
        with pytest.raises(BootstrapHold):
            verify(manifest_path=str(path), admission_json=admitted_source(source))
        assert all(Path(p).read_bytes() == b"synthetic protected sentinel" for p in keep[1:])


def test_V2_12_path_alias_symlink_hardlink_protected_hold(tmp_path):
    keep = tmp_path / "keep.sqlite3"
    keep.write_bytes(b"protected")
    for target in (keep, tmp_path / "link.sqlite3", tmp_path / "hard.sqlite3"):
        if target.name == "link.sqlite3":
            target.symlink_to(keep)
        elif target.name == "hard.sqlite3":
            target.hardlink_to(keep)
        with pytest.raises(BootstrapHold):
            inspect_paths(projection_target=str(target), materialization_target=str(tmp_path / "ni04.sqlite3"), keep_paths=[str(keep)])
    assert keep.read_bytes() == b"protected"


def test_T11_V2_14_closed_counter_and_no_raw_endpoint_logs(tmp_path, caplog):
    value = stack(tmp_path, [source_record(dst_ip="203.0.113.93")])
    try:
        value.service.telemetry = ProjectionTelemetry()
        with caplog.at_level("INFO"):
            value.service.poll()
        assert all(token not in caplog.text for token in ("10.73.0.7", "203.0.113.93", MAC))
        with pytest.raises(ValueError):
            value.service.telemetry.emit("attribution_retry_counters", peer_ip="203.0.113.93")
    finally:
        value.repo.close()


@requires_posix_io
def test_V2_08_single_snapshot_concurrent_append_preserves_new_tail(tmp_path, monkeypatch):
    data = record()
    with store(tmp_path, source=(data+b"\n")*2) as source:
        seed_source(source, data=data)
        reader = NetworkMetadataProjectionSourceReadService(source.config.db_path)
        original = reader._binding
        appended = []
        def binding(connection, generation):
            value = original(connection, generation)
            if not appended:
                appended.append(True)
                seed_source(source, data=data, start=len(data)+1)
            return value
        monkeypatch.setattr(reader, "_binding", binding)
        floor, = reader.read_reset_snapshot(admission=ScopeAdmission(admitted_source(source)))
        assert appended == [True] and floor["last_retained_record_start_byte_offset"] == 0
        fresh, = reader.read_projection_batch(source.generation.source_generation_id, 0, 256)
        assert fresh.record_start_byte_offset == len(data)+1


@pytest.mark.parametrize("point,committed", [("before_commit", False), ("after_commit", True)])
@requires_posix_io
def test_V2_09_10_post_floor_crash_and_real_restart(tmp_path, point, committed):
    data = record(source_event(dest_ip="203.0.113.93"))
    with store(tmp_path, source=(data+b"\n")*2) as source:
        seed_source(source, data=data)
        manifest, _ = staged(source, tmp_path)
        seed_source(source, data=data, start=len(data)+1)
        config = ProjectionConfig(enabled=True, db_path=manifest["projection"]["path"], scope_admission_json=admitted_source(source))
        clock, authority = Clock(), Attribution()
        authority.get_authority_horizon = lambda site: SimpleNamespace(state="available",
            first_usable_at="2026-01-01T00:00:00.000Z", retained_from="2026-01-01T00:00:00.000Z")
        resolve = authority.resolve_ipv4
        authority.resolve_ipv4 = lambda *args: replace(resolve(*args), valid_from="2026-01-01T00:00:00.000Z")
        repo = ProjectionRepository(config, clock=clock).initialize()
        service = NetworkMetadataProjectionService(config, repo,
            NetworkMetadataProjectionSourceReadService(source.config.db_path), authority, Registry(), IDENTITY)
        service.run_id = repo.create_run(IDENTITY)
        floor = dict(repo.reset_floor(source.generation.source_generation_id))
        class Crash(BaseException):
            pass
        repo.crash_point = lambda stage: (_ for _ in ()).throw(Crash()) if stage == point else None
        try:
            with pytest.raises(Crash):
                service.poll()
            assert (repo.checkpoint(source.generation.source_generation_id) is not None) == committed
            assert dict(repo.reset_floor(source.generation.source_generation_id)) == floor
        finally:
            repo.close()
        repo = ProjectionRepository(config, clock=clock).initialize()
        try:
            service.repository = repo
            service.run_id = repo.create_run(IDENTITY)
            service.poll()
            assert repo.connection.execute("SELECT count(*) FROM device_network_metadata_edges").fetchone()[0] == 1
            assert repo.connection.execute("SELECT count(*) FROM projection_service_recognition_feed").fetchone()[0] == 1
            assert dict(repo.reset_floor(source.generation.source_generation_id)) == floor
            assert repo.checkpoint(source.generation.source_generation_id)["last_record_start_byte_offset"] == len(data)+1
        finally:
            repo.close()


@requires_posix_io
def test_V2_09_empty_and_new_generation_natural_beginning_retention(tmp_path):
    from app.network_metadata.retention import RetentionPolicy
    data = record()
    with store(tmp_path, source=data+b"\n") as source:
        manifest, _ = staged(source, tmp_path)  # Existing generation with no rows.
        config = ProjectionConfig(enabled=True, db_path=manifest["projection"]["path"], scope_admission_json=admitted_source(source))
        repo = ProjectionRepository(config).initialize()
        try:
            service = NetworkMetadataProjectionService(config, repo,
                NetworkMetadataProjectionSourceReadService(source.config.db_path), Attribution(), Registry(), IDENTITY)
            generation = service.source.get_source_progress(source.generation.source_generation_id)
            assert service._read_after(generation) is None
            seed_source(source, data=data)
            assert service.source.read_projection_batch(generation.source_generation_id, service._read_after(generation), 256)[0].record_start_byte_offset == 0
            source.clock.advance(days=31)
            RetentionPolicy(source.repo).run()
            assert not service.source.read_projection_batch(generation.source_generation_id, None, 256)
            assert service._read_after(service.source.get_source_progress(generation.source_generation_id)) is None
            new, _ = source.repo.transition_generation(binding=source.config.capture_scope_binding,
                boot_id=BOOT, physical=(1, 2), close_reason="rotation")
            assert repo.reset_floor(new.source_generation_id) is None
            assert service._read_after(service.source.get_source_progress(new.source_generation_id)) is None
            with pytest.raises(sqlite3.Error):
                repo.connection.execute("DELETE FROM projection_source_reset_floors")
        finally:
            repo.close()


def test_V2_unadmitted_empty_generation_is_blocked_not_false_complete(tmp_path):
    with store(tmp_path) as source:
        config = ProjectionConfig(enabled=True, db_path=str(tmp_path / "projection.sqlite3"), scope_admission_json=scope_admission())
        repo = ProjectionRepository(config).initialize()
        try:
            service = NetworkMetadataProjectionService(config, repo,
                NetworkMetadataProjectionSourceReadService(source.config.db_path), Attribution(), Registry(), IDENTITY)
            service.run_id = repo.create_run(IDENTITY)
            assert service.poll() == ()
            assert repo.live_state == "blocked_conflict" and repo.live_reason == "scope_admission_untrusted"
            assert not repo.connection.execute("SELECT 1 FROM projection_source_checkpoints").fetchone()
            assert repo.connection.execute("SELECT last_source_poll_at FROM projection_runtime_state").fetchone()[0] is None
        finally:
            repo.close()


def test_T08_T10_V2_15_bounded_local_load_reports_not_hdd_acceptance(tmp_path, record_property, monkeypatch):
    import socket
    attempts = []
    def no_network(*args, **kwargs):
        attempts.append(True)
        raise AssertionError("online lookup forbidden")
    monkeypatch.setattr(socket, "socket", no_network)
    records = [source_record(index, dst_ip="203.0.113.93") for index in range(1024)]
    value = stack(tmp_path, records)
    samples = []
    try:
        install_service_recognition_extension(value.repo)
        for _ in range(4):
            started = time.perf_counter()
            results = value.service.poll()
            samples.append((time.perf_counter()-started)*1000)
            assert len(results) == 256
        assert not attempts and len(value.attribution.calls) == 1024
        assert all(call[1] == "10.73.0.7" for call in value.attribution.calls)
        assert value.repo.connection.execute("SELECT count(*) FROM projection_pending_attribution").fetchone()[0] == 0
        assert value.repo.connection.execute("SELECT count(*) FROM projection_service_recognition_feed").fetchone()[0] == 1024
        ordered = sorted(samples)
        record_property("local_load", json.dumps(dict(samples_ms=samples, p95_ms=ordered[-1], p99_ms=ordered[-1],
            footprint_bytes=value.repo.footprint(), scope="disposable laptop WSL; not physical HDD or production acceptance",
            performance_pass_claimed=False)))
    finally:
        value.repo.close()


@pytest.mark.parametrize("point,committed", [("reset_core_created", False), ("reset_floors_installed", False),
                                            ("before_commit", False), ("after_commit", True)])
def test_V2_08_core_and_floors_one_atomic_initialization(tmp_path, point, committed):
    class Crash(BaseException):
        pass
    config = ProjectionConfig(enabled=True, db_path=str(tmp_path / "new.sqlite3"), scope_admission_json=scope_admission())
    repo = ProjectionRepository(config, reset_bootstrap=dict(floors=(), reset_epoch_id=str(uuid.uuid4()),
        reset_at_utc="2026-10-14T00:00:00.000000Z"),
        crash_point=lambda stage: (_ for _ in ()).throw(Crash()) if stage == point else None)
    with pytest.raises(Crash):
        repo.initialize()
    assert repo.connection is repo._writer_fd is None
    with sqlite3.connect(config.db_path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert bool(tables) == committed
        if committed:
            assert connection.execute("SELECT floor_count FROM projection_source_reset_epoch").fetchone()[0] == 0
            assert not connection.execute("SELECT 1 FROM projection_source_checkpoints").fetchone()


def test_V2_manifest_external_hash_and_corruption_fail_closed(tmp_path):
    with store(tmp_path) as source:
        manifest, keep = staged(source, tmp_path)
        path = tmp_path / "stage" / "prepared-pair.json"
        frozen = hashlib.sha256(path.read_bytes()).hexdigest()
        assert verify(manifest_path=str(path), admission_json=admitted_source(source), expected_manifest_sha256=frozen)["state"] == "PREPARED"
        path.write_text(json.dumps(dict(manifest, state="VERIFIED")))
        with pytest.raises(BootstrapHold):
            verify(manifest_path=str(path), admission_json=admitted_source(source), expected_manifest_sha256=frozen)


@requires_posix_io
def test_T09_V2_13_fresh_pair_publishes_only_post_floor_ni03_ni04(tmp_path):
    from tests.network_service_recognition.support import AT, bundle
    from tests.network_service_recognition.test_summary import EVENT
    from tests.network_service_recognition.test_protected_readers import DEVICE
    from app.network_metadata.validation import ni_timestamp
    from app.network_service_recognition.materialization_repository import ServiceMaterializationRepository
    from app.network_service_recognition.worker import ServiceMaterializationWorker
    from app.network_service_recognition.source_adapter import WorkerSourceReadService
    from app.network_service_recognition.materialized_read_service import MaterializedDeviceServiceReadService
    from app.network_service_recognition.serialization import serialize_device_service_intelligence
    from app.network_protocol_intelligence.read_service import DeviceProtocolIntelligenceReadService
    event = source_event("tls", timestamp=EVENT, dest_ip="203.0.113.93", proto="TCP")
    event["tls"]["sni"] = "www.youtube.com"
    data = record(event)
    with store(tmp_path, source=(data+b"\n")*2) as source:
        source.clock.value = ni_timestamp(AT, canonical=True)
        seed_source(source, data=data)
        old_ref = source.repo.connection.execute("SELECT observation_id FROM network_metadata_observations").fetchone()[0]
        manifest, _ = staged(source, tmp_path)
        clock = lambda: ni_timestamp(AT, canonical=True)
        config = ProjectionConfig(enabled=True, db_path=manifest["projection"]["path"], scope_admission_json=admitted_source(source))
        repo = ProjectionRepository(config, clock=clock).initialize()
        target = ServiceMaterializationRepository(manifest["materialization"]["path"], clock=clock).initialize()
        authority, registry = Attribution(), Registry()
        registry.values[MAC] = RegistryEvaluation("authoritative", DEVICE)
        resolve = authority.resolve_ipv4
        authority.resolve_ipv4 = lambda *args: replace(resolve(*args), valid_from="2026-10-11T00:00:00.000Z", valid_until="2026-10-13T00:00:00.000Z")
        source_reader = NetworkMetadataProjectionSourceReadService(source.config.db_path)
        service = NetworkMetadataProjectionService(config, repo, source_reader, authority, registry, IDENTITY)
        service.run_id = repo.create_run(IDENTITY)
        b = bundle()
        worker = ServiceMaterializationWorker(target, ServiceRecognitionDeliveryReadService(repo.config.db_path),
            WorkerSourceReadService(source.config.db_path), b, clock=clock)
        try:
            service.poll()
            worker.cycle()
            assert not repo.existing_edges(old_ref)
            assert not target.connection.execute("SELECT 1 FROM service_recognition_observations").fetchone()
            seed_source(source, data=data, start=len(data)+1)
            service.poll()
            worker.cycle()
            assert not repo.existing_edges(old_ref)
            assert repo.connection.execute("SELECT count(*) FROM device_network_metadata_edges").fetchone()[0] == 1
            assert target.connection.execute("SELECT count(*) FROM service_recognition_observations").fetchone()[0] == 1
            site = source.config.capture_scope_binding.site_id
            protocol = DeviceProtocolIntelligenceReadService(DeviceNetworkMetadataReadService(repo.config.db_path)).get_device_protocol_summary(
                site, DEVICE, MAC, evaluated_at_utc=AT, deadline=QueryDeadline.after(5))
            assert protocol.schema_version == 1 and protocol.last_protocol_observation.protocol_id == "tls"
            ni04 = MaterializedDeviceServiceReadService(target.db_path, b)
            value = ni04.get_device_service_summary(site, DEVICE, MAC, evaluated_at_utc=AT, deadline=QueryDeadline.after(5))
            assert value.schema_version == 3 and value.recent_services[0].service_id == "service.youtube"
            public = json.dumps(serialize_device_service_intelligence(value, b))
            assert all(token not in public for token in (MAC, "203.0.113.93", "10.73.0.7", "www.youtube.com", old_ref))
        finally:
            target.close()
            repo.close()


def test_bootstrap_default_inspect_no_sqlite_or_writes(tmp_path, monkeypatch, capsys):
    from scripts.ni02b_v2_offline_bootstrap import main
    keep = tmp_path / "keep.sqlite3"
    keep.write_bytes(b"protected")
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    def forbidden(*args, **kwargs):
        pytest.fail("inspect must not open SQLite or create sidecars")
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    assert main(["--projection-target", str(tmp_path / "projection.sqlite3"),
        "--materialization-target", str(tmp_path / "ni04.sqlite3"), "--keep-path", str(keep)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["destructive_action"] is output["schema_admitted"] is False
    assert output["scope_admission"] == "not_supplied"
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before


def test_bootstrap_verify_exact_operator_inventory(tmp_path):
    with store(tmp_path) as source:
        manifest, keep = staged(source, tmp_path)
        path = tmp_path / "stage" / "prepared-pair.json"
        other = inspect_paths(projection_target=str(tmp_path / "different.sqlite3"),
            materialization_target=manifest["materialization_target"], keep_paths=keep)
        with pytest.raises(BootstrapHold):
            verify(manifest_path=str(path), admission_json=admitted_source(source), expected_inventory=other)


def test_synthetic_scope_fixture_canonical_identity_and_disabled_boundary(tmp_path):
    path = Path(__file__).parent / "fixtures" / "external_peer_scope_synthetic.json"
    fixture = ScopeAdmission(path.read_text())
    assert fixture.canonical == ScopeAdmission(scope_admission()).canonical
    assert projection_config_from_env({"NETWORK_METADATA_PROJECTION_ENABLED": "false",
        "NETWORK_METADATA_PROJECTION_SCOPE_ADMISSION_JSON": "not-json"}) == ProjectionConfig()
    with pytest.raises(ProjectionConflict, match="scope_admission_untrusted"):
        projection_config_from_env({"NETWORK_METADATA_PROJECTION_ENABLED": "true",
            "NETWORK_METADATA_PROJECTION_DB_PATH": str(tmp_path / "projection.sqlite3"),
            "NETWORK_METADATA_DB_PATH": str(tmp_path / "metadata.sqlite3"),
            "VISITOR_REGISTRY_DB_PATH": str(tmp_path / "registry.sqlite3")})
    assert list(tmp_path.iterdir()) == []


def test_runtime_start_requires_discard_epoch_no_implicit_replay(tmp_path):
    config = ProjectionConfig(enabled=True, db_path=str(tmp_path / "unprepared.sqlite3"), scope_admission_json=scope_admission())
    repo = ProjectionRepository(config)
    dependency = SimpleNamespace()  # Must not read any source/authority.
    service = NetworkMetadataProjectionService(config, repo, dependency, dependency, dependency, IDENTITY)
    try:
        with pytest.raises(ProjectionUnavailable, match="reset_bootstrap_required"):
            service.startup()
        for table in ("projection_runs", "projection_source_checkpoints", "projection_pending_attribution", "device_network_metadata_edges"):
            assert not repo.connection.execute(f"SELECT 1 FROM {table}").fetchone()
    finally:
        repo.close()
    ready = replace(config, db_path=str(tmp_path / "prepared.sqlite3"))
    repo = ProjectionRepository(ready, reset_bootstrap=dict(floors=(), reset_epoch_id=str(uuid.uuid4()),
        reset_at_utc="2026-10-14T00:00:00.000000Z"))
    service = NetworkMetadataProjectionService(ready, repo, dependency, dependency, dependency, IDENTITY)
    try:
        assert service.startup() is True
        assert repo.connection.execute("SELECT count(*) FROM projection_runs").fetchone()[0] == 1
        assert not repo.connection.execute("SELECT 1 FROM projection_source_checkpoints").fetchone()
    finally:
        repo.close()


def test_T06_V2_12_complete_disposable_pair_discards_derived_only(tmp_path):
    with store(tmp_path) as source:
        manifest, keep = staged(source, tmp_path)
        protected = {p: Path(p).read_bytes() for p in keep}
        targets = [manifest["projection_target"], manifest["materialization_target"]]
        for target in targets:
            with sqlite3.connect(target) as connection:
                connection.execute("CREATE TABLE old_derived_history(value TEXT)")
                connection.execute("INSERT INTO old_derived_history VALUES('disposable derived history')")
        paired = dict(manifest, state="REPLACED_NOT_STARTED")
        for member, target in zip(("projection", "materialization"), targets):
            # Simulation under tmp_path only; no executable reset capability in
            # the shipped helper and no production paths or services are used.
            shutil.copyfile(manifest[member]["path"], target)
            paired[member] = dict(manifest[member], path=target)
        path = tmp_path / "replaced-pair.json"
        path.write_text(json.dumps(paired))
        frozen = hashlib.sha256(path.read_bytes()).hexdigest()
        report = verify(manifest_path=str(path), admission_json=admitted_source(source),
                        expected_manifest_sha256=frozen)
        assert report["state"] == "VERIFIED" and report["activation_authorized"] is False
        for target in targets:
            with sqlite3.connect(Path(target).as_uri()+"?mode=ro", uri=True) as connection:
                assert not connection.execute("SELECT 1 FROM sqlite_master WHERE name='old_derived_history'").fetchone()
        assert {p: Path(p).read_bytes() for p in keep} == protected
