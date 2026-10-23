import sqlite3
import uuid
from dataclasses import replace
from datetime import timedelta

import pytest

from app.network_metadata_projection.models import ProjectionConflict, RegistryEvaluation, ProjectionUnavailable, ProjectionValidationError
from app.network_metadata_projection.read_service import DeviceNetworkMetadataReadService
from app.network_metadata_projection.schema import TABLES
from .support import stack, source_record, SITE, MAC, OTHER_MAC, GENERATION, T0


@pytest.fixture
def state(tmp_path):
    value = stack(tmp_path)
    try:
        yield value
    finally:
        value.repo.close()


def edges(state):
    return [dict(row) for row in state.repo.connection.execute("SELECT * FROM device_network_metadata_edges ORDER BY device_endpoint_role DESC")]


@pytest.mark.parametrize("src,dst,count", [("resolved", "resolved", 2), ("resolved", "unattributed", 1),
    ("unattributed", "resolved", 1), ("ambiguous", "unattributed", 0), ("unavailable", "resolved", 1)])
def test_zero_one_two_edges_and_terminal_peer(state, src, dst, count):
    state.attribution.states = {"10.73.0.7": src, "10.73.0.8": dst}
    state.service.poll()
    assert len(edges(state)) == count
    assert state.repo.checkpoint(GENERATION)["last_record_start_byte_offset"] == 0
    assert all(call[2] == state.source.records[0].event_at for call in state.attribution.calls)


def test_same_mac_two_roles_replay_and_immutability(state):
    state.attribution.macs["10.73.0.8"] = MAC
    prepared = state.service.prepare(state.source.records[0])
    state.repo.commit_dispositions([prepared], state.service._evaluations([prepared]), state.service.run_id)
    before = edges(state)
    assert len(before) == 2 and len({row["edge_id"] for row in before}) == 2
    state.clock.advance(seconds=5)
    state.repo.commit_dispositions([state.service.prepare(state.source.records[0])], {}, state.service.run_id)
    assert edges(state) == before
    assert state.registry.calls == [MAC]
    for statement in ("UPDATE device_network_metadata_edges SET client_mac='bad'", "DELETE FROM device_network_metadata_edges"):
        with pytest.raises(sqlite3.Error):
            state.repo.connection.execute(statement)
    changed = state.service.prepare(replace(state.source.records[0], src_port=1))
    with pytest.raises(ProjectionConflict, match="edge_semantic_conflict"):
        state.repo.commit_dispositions([changed], {}, state.service.run_id)
    assert edges(state) == before


@pytest.mark.parametrize("initial,first_retry,second_retry", [
    (("resolved", "unavailable"), None, None),
    (("unattributed", "unavailable"), None, None),
    (("unavailable", "unavailable"), "src", "dst"),
])
def test_r1_partial_retry_preserves_old_counterpart_snapshot(state, initial, first_retry, second_retry):
    state.attribution.states = dict(zip(("10.73.0.7", "10.73.0.8"), initial))
    state.service.poll()
    old = edges(state)
    pending = state.repo.connection.execute("SELECT * FROM projection_pending_attribution").fetchone()
    assert pending["src_snapshot_state"] == initial[0] and pending["dst_snapshot_state"] == initial[1]
    columns = {row[1] for row in state.repo.connection.execute("PRAGMA table_info(projection_pending_attribution)")}
    assert not {"src_ip", "dst_ip", "client_mac", "device_id", "src_port", "dst_port"} & columns
    state.clock.advance(seconds=30)
    state.attribution.calls.clear()
    if first_retry:
        state.attribution.states["10.73.0.7"] = "resolved"
        state.service.retry()
        first = edges(state)
        assert first[0]["peer_attribution_state"] == "unavailable"
        state.clock.advance(seconds=30)
        state.attribution.calls.clear()
        old = first
    state.attribution.states["10.73.0.8"] = "resolved"
    # Opposite authority changes must NOT be queried again by partial retry.
    state.attribution.states["10.73.0.7"] = "ambiguous"
    state.service.retry()
    assert [call[1] for call in state.attribution.calls] == ["10.73.0.8"]
    final = edges(state)
    assert all(row in final for row in old)
    dst = next(row for row in final if row["device_endpoint_role"] == "dst")
    expected = "resolved" if first_retry or initial[0] == "resolved" else "unattributed"
    assert dst["peer_attribution_state"] == expected
    assert state.repo.connection.execute("SELECT count(*) FROM projection_pending_attribution").fetchone()[0] == 0


def test_both_pending_resolve_in_one_retry_have_mutual_refs(state):
    state.attribution.states = {"10.73.0.7": "unavailable", "10.73.0.8": "unavailable"}
    state.service.poll()
    state.attribution.states.clear()
    state.clock.advance(seconds=30)
    state.service.retry()
    left, right = edges(state)
    assert left["peer_attribution_binding_id"] == right["attribution_binding_id"]
    assert right["peer_attribution_binding_id"] == left["attribution_binding_id"]


def test_pending_terminal_and_expired_dependency(state):
    state.attribution.states = {"10.73.0.7": "unavailable", "10.73.0.8": "unavailable"}
    state.service.poll()
    state.clock.advance(seconds=30)
    state.attribution.states = {"10.73.0.7": "unattributed", "10.73.0.8": "unavailable"}
    state.service.retry()
    state.source.records = [replace(state.source.records[0], sensitive_endpoint_presence_state="expired", src_ip=None, dst_ip=None)]
    state.clock.advance(seconds=30)
    state.service.retry()
    assert edges(state) == []
    assert not state.repo.pending()


def test_late_registry_binding_exact_site_join_monotonic_and_conflict(state):
    state.service.poll()
    old = edges(state)
    reader = DeviceNetworkMetadataReadService(state.config.db_path)
    start, end = "2026-10-09T12:00:00.000000Z", "2026-10-09T13:00:00.000000Z"
    assert reader.list_edges_by_mac(SITE, MAC, start, end)["items"][0]["device_id"] is None
    device_id = str(uuid.uuid4())
    state.registry.values[MAC] = RegistryEvaluation("authoritative", device_id)
    state.service.reconcile()
    item = reader.list_edges_by_device(SITE, device_id, start, end)["items"][0]
    assert item["device_id"] == device_id and item["identity_binding_state"] == "authoritative"
    state.registry.values[MAC] = RegistryEvaluation("registry_unavailable", reason="registry_unavailable")
    state.service.reconcile()
    assert state.repo.binding(SITE, MAC)["device_id"] == device_id
    assert edges(state) == old
    assert reader.list_edges_by_device("f" * 24, device_id, start, end)["items"] == []
    state.registry.values[MAC] = RegistryEvaluation("authoritative", str(uuid.uuid4()))
    with pytest.raises(ProjectionConflict, match="registry_identity_conflict"):
        state.service.reconcile()
    assert edges(state) == old


@pytest.mark.parametrize("offset,state_name", [(0, "unattributed"), (50, "unavailable")])
def test_first_checkpoint_zero_or_nonzero_atomic_zero_edge_disposition(tmp_path, offset, state_name):
    value = stack(tmp_path, [source_record(offset)])
    try:
        assert value.repo.checkpoint(GENERATION) is None
        value.attribution.states = {"10.73.0.7": state_name, "10.73.0.8": state_name}
        value.service.poll()
        assert value.repo.checkpoint(GENERATION)["last_record_start_byte_offset"] == offset
        assert edges(value) == []
    finally:
        value.repo.close()


@pytest.mark.parametrize("point,committed", [("before_commit", False), ("after_commit", True)])
def test_crash_checkpoint_atomicity(state, point, committed):
    class Crash(BaseException):
        pass
    def crash(stage):
        if stage == point:
            raise Crash()
    state.repo.crash_point = crash
    with pytest.raises(Crash):
        state.service.poll()
    assert (state.repo.checkpoint(GENERATION) is not None) == committed
    assert bool(edges(state)) == committed
    state.repo.crash_point = lambda _: None
    state.service.poll()
    assert len(edges(state)) == 2


@pytest.mark.parametrize("kind", ["invalid", "unadmitted_scope", "source_identity"])
def test_conflict_no_checkpoint_and_upstream_unmodified(state, kind):
    if kind == "invalid":
        state.attribution.states["10.73.0.7"] = "invalid"
    elif kind == "unadmitted_scope":
        state.source.records = [replace(state.source.records[0], capture_scope_binding_digest="f" * 64)]
    else:
        state.source.records = [replace(state.source.records[0], source_event_identity="bad")]
    state.service.poll()
    assert state.repo.live_state == "blocked_conflict"
    assert state.repo.checkpoint(GENERATION) is None
    assert edges(state) == []


def test_ipv6_endpoint_absence_scope_direction_and_reader_validation(state):
    state.source.records = [replace(state.source.records[0], dst_ip="2001:db8::1")]
    state.service.poll()
    assert len(state.attribution.calls) == 1
    assert edges(state)[0]["peer_attribution_state"] == "unsupported_address_family"
    assert edges(state)[0]["direction"] == "unknown"
    reader = DeviceNetworkMetadataReadService(state.config.db_path)
    observation = state.source.records[0].observation_id
    assert len(reader.list_edges_by_observation(SITE, observation)) == 1
    assert reader.list_edges_by_observation("f" * 24, observation) == ()
    for limits in (0, 501, True):
        with pytest.raises(ProjectionValidationError):
            reader.list_edges_by_mac(SITE, MAC, "2026-10-09T00:00:00.000000Z", "2026-10-10T00:00:00.000000Z", limit=limits)
    with pytest.raises(ProjectionValidationError):
        reader.list_edges_by_mac(SITE, MAC, "2026-10-01T00:00:00.000000Z", "2026-10-16T00:00:00.000000Z")


def test_retention_uses_event_and_ingested_not_projection_or_binding(state):
    state.service.poll()
    state.clock.advance(days=1)
    # source_ingested_at is already strictly older than 24h (clock began +30s).
    state.service.reconcile()
    state.service.retain()
    assert edges(state) == []
    # Reconciliation just evaluated these current bindings; expiry is not reset.
    assert state.repo.connection.execute("SELECT count(*) FROM projection_site_mac_bindings").fetchone()[0] == 2
    assert state.repo.connection.execute("SELECT count(*) FROM projection_registry_identities").fetchone()[0] == 0


@pytest.mark.parametrize('age', [86399, 86400, 86401])
@pytest.mark.parametrize('field', ['event_at', 'ingested_at'])
@pytest.mark.parametrize('role', ['src', 'dst'])
def test_24h_source_admission_checks_both_original_times_and_roles(state, age, field, role):
    from app.network_metadata.validation import ni_format_utc
    from types import SimpleNamespace
    state.attribution.get_authority_horizon = lambda site: SimpleNamespace(state='available',
        first_usable_at='2026-01-01T00:00:00.000Z', retained_from='2026-01-01T00:00:00.000Z')
    original = state.attribution.resolve_ipv4
    def resolve(*args):
        value = original(*args)
        return replace(value, valid_from='2026-01-01T00:00:00.000Z', valid_until='2026-12-01T00:00:00.000Z') if value.state == 'resolved' else value
    state.attribution.resolve_ipv4 = resolve
    value = replace(state.source.records[0], **{field:ni_format_utc(state.clock()-timedelta(seconds=age))})
    state.source.records = [value]
    state.attribution.states['10.73.0.8' if role == 'src' else '10.73.0.7'] = 'unattributed'
    state.service.poll()
    assert len(edges(state)) == int(age <= 86400)
    assert state.repo.checkpoint(GENERATION)['last_record_start_byte_offset'] == 0
    if age > 86400:assert state.attribution.calls == []


def test_pending_expiry_updates_runtime_count_within_last_allowed_batch(state):
    from app.network_metadata_projection.retention import ProjectionRetention
    state.attribution.states = {'10.73.0.7':'unavailable', '10.73.0.8':'unavailable'}
    state.service.poll()
    assert state.repo.connection.execute('SELECT pending_attribution_count FROM projection_runtime_state').fetchone()[0] == 1
    state.clock.advance(days=2)
    state.repo.config = replace(state.config, retention_max_batches_per_pass=1)
    result = ProjectionRetention(state.repo, state.source).run()
    assert result['projection_pending_attribution'] == 1
    assert not state.repo.pending()
    assert state.repo.connection.execute('SELECT pending_attribution_count FROM projection_runtime_state').fetchone()[0] == 0
    assert edges(state) == []
    assert state.repo.checkpoint(GENERATION) is not None


def test_authoritative_identity_and_change_index_survive_event_gc(state):
    from app.network_metadata_projection.service_extension import install_service_recognition_extension
    install_service_recognition_extension(state.repo)
    state.registry.values[MAC] = RegistryEvaluation('authoritative', str(uuid.uuid4()))
    state.service.poll()
    before = tuple(tuple(r) for r in state.repo.connection.execute('SELECT * FROM projection_registry_binding_change_index'))
    identity = dict(state.repo.binding(SITE, MAC))
    state.clock.advance(days=3)
    state.service.retain()
    assert edges(state) == []
    assert dict(state.repo.binding(SITE, MAC)) == identity
    assert state.repo.connection.execute('SELECT 1 FROM projection_registry_identities WHERE device_id=?',(identity['device_id'],)).fetchone()
    assert before == tuple(tuple(r) for r in state.repo.connection.execute('SELECT * FROM projection_registry_binding_change_index'))
    assert state.repo.checkpoint(GENERATION) is not None
    assert state.repo.connection.execute('PRAGMA foreign_key_check').fetchall() == []


def test_exact_schema_missing_join_fail_closed_and_source_failure(state):
    assert {row[0] for row in state.repo.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")} == set(TABLES)
    state.source.fail = True
    state.service.poll()
    assert state.repo.live_state == "source_unavailable" and state.repo.checkpoint(GENERATION) is None
    state.source.fail = False
    state.service.poll()
    state.repo.connection.execute("DELETE FROM projection_site_mac_bindings")
    with pytest.raises(ProjectionUnavailable):
        DeviceNetworkMetadataReadService(state.config.db_path).list_edges_by_observation(SITE, state.source.records[0].observation_id)
