"""G2 migration/feed/index: exact cursor authority, no upstream reinterpretation."""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
import runpy

import pytest

from app.analytics.source_gateway import QueryDeadline
from app.network_metadata.validation import ni_format_utc
from app.network_metadata_projection.models import ProjectionUnavailable, ProjectionValidationError, RegistryEvaluation
from app.device_fingerprint.validation import format_utc
from app.network_metadata_projection.repository import ProjectionRepository
from app.network_metadata_projection.schema import signature, validate_schema
from app.network_metadata_projection.service_extension import (
    TABLES, install_service_recognition_extension, maintain_authoritative_change)
from app.network_metadata_projection.service_delivery_read_service import ServiceRecognitionDeliveryReadService
from .support import stack, source_record, SITE, MAC, OTHER_MAC
from .test_service_extension_bridge import DEVICE
from .test_projection import edges


@pytest.fixture
def state(tmp_path):
    value = stack(tmp_path, [source_record(dst_ip="203.0.113.93")])
    value.attribution.states["203.0.113.93"] = "endpoint_absent"
    value.registry.values[MAC] = RegistryEvaluation("authoritative", DEVICE)
    try:
        yield value
    finally:
        value.repo.close()


def reader(state):
    return ServiceRecognitionDeliveryReadService(state.config.db_path)


def feed(state, after=0, **kwargs):
    return reader(state).read_service_recognition_feed(after, deadline=QueryDeadline.after(5), **kwargs)


def changes(state, after=0, **kwargs):
    return reader(state).read_authoritative_binding_changes(after, deadline=QueryDeadline.after(5), **kwargs)


def test_G2_R1_QA01_seed_with_empty_audit_history(state):
    state.service.poll()
    with state.repo.transaction(retention=True):
        state.repo.connection.execute("DELETE FROM projection_registry_binding_events")
    assert install_service_recognition_extension(state.repo) is True
    row, = changes(state)
    assert (row.site_id, row.client_mac, row.device_id) == (SITE, MAC, DEVICE)
    # Existing edges are supplied by backfill, not mislabeled as new live events.
    assert feed(state) == ()
    assert reader(state).recognition_feed_bounds(deadline=QueryDeadline.after(5)).max_feed_seq is None


@pytest.mark.parametrize("point", [
    *("extension_created_" + name for name in TABLES),
    "extension_seeded_bindings", "extension_inserted_metadata", "extension_validated", "before_commit",
])
def test_G2_R2_QA04_install_crash_before_commit_is_exact_core_only(state, point):
    state.service.poll()
    original = signature(state.repo.connection)
    class Crash(BaseException):
        pass
    def crash(stage):
        if stage == point:
            raise Crash()
    state.repo.crash_point = crash
    with pytest.raises(Crash):
        install_service_recognition_extension(state.repo)
    assert signature(state.repo.connection) == original
    assert validate_schema(state.repo.connection, integrity=True) == "CORE_ONLY"
    state.repo.crash_point = lambda _: None
    assert install_service_recognition_extension(state.repo) is True


def test_G2_R2_QA05_QA12_postcommit_crash_and_restart_idempotency(state):
    class Crash(BaseException):
        pass
    state.repo.crash_point = lambda stage: (_ for _ in ()).throw(Crash()) if stage == "after_commit" else None
    with pytest.raises(Crash):
        install_service_recognition_extension(state.repo)
    state.repo.close()
    state.repo = ProjectionRepository(state.config, clock=state.clock,
                                     install_service_recognition_extension=True).initialize()
    state.service.repository = state.repo
    assert validate_schema(state.repo.connection, integrity=True) == "CORE_PLUS_EXTENSION_V1"
    before = tuple(state.repo.connection.iterdump())
    assert install_service_recognition_extension(state.repo) is False
    assert tuple(state.repo.connection.iterdump()) == before


def test_G2_installer_requires_acquired_single_writer_lock(state):
    with pytest.raises(ProjectionUnavailable):
        install_service_recognition_extension(SimpleNamespace(connection=state.repo.connection, _writer_fd=None))
    other = ProjectionRepository(state.config, install_service_recognition_extension=True)
    with pytest.raises(ProjectionUnavailable):
        other.initialize()
    assert validate_schema(state.repo.connection) == "CORE_ONLY"


def test_G2_default_off_and_explicit_startup_install(state):
    state.repo.close()
    state.repo = ProjectionRepository(state.config, clock=state.clock,
                                     install_service_recognition_extension=True).initialize()
    assert state.repo.service_recognition_extension_present is True
    assert state.repo.connection.execute("PRAGMA user_version").fetchone()[0] == 2


def test_G2_feed_exact_provenance_readonly_and_monotonic(state):
    install_service_recognition_extension(state.repo)
    state.service.poll()
    before = tuple(state.repo.connection.iterdump())
    row, = feed(state)
    assert row.feed_seq == 1
    assert row.fact.edge_id == edges(state)[0]["edge_id"]
    assert row.identity.device_id == DEVICE and row.identity.registry_binding_change_seq == 1
    assert row.identity.site_id == SITE and row.identity.client_mac == MAC
    assert feed(state, 1) == ()
    assert reader(state).recognition_feed_bounds(deadline=QueryDeadline.after(5)).min_retained_feed_seq == 1
    assert tuple(state.repo.connection.iterdump()) == before
    assert "203.0." not in repr(row)


@pytest.mark.parametrize("limit", [0, 257, True, -1])
def test_G2_feed_bounds_reject_without_open(state, limit):
    with pytest.raises(ProjectionValidationError):
        feed(state, limit=limit)


@pytest.mark.parametrize("after", [-1, True, "1"])
def test_G2_cursor_type_reject_without_open(state, after):
    with pytest.raises(ProjectionValidationError):
        feed(state, after)


def test_G2_R1_QA02_QA03_audit_retention_id_reuse_does_not_change_cursor(state):
    install_service_recognition_extension(state.repo)
    state.service.poll()
    first, = changes(state)
    old_audit_id = state.repo.connection.execute("SELECT binding_event_id FROM projection_registry_binding_events").fetchone()[0]
    with state.repo.transaction(retention=True):
        state.repo.connection.execute("DELETE FROM projection_registry_binding_events")
    state.registry.values[MAC] = RegistryEvaluation("registry_unavailable", reason="registry_unavailable")
    state.service.reconcile()
    assert state.repo.connection.execute("SELECT binding_event_id FROM projection_registry_binding_events").fetchone()[0] == old_audit_id
    assert changes(state) == (first,)


def test_G2_R1_QA04_feed_sequence_and_current_change_survive_event_retention(state):
    install_service_recognition_extension(state.repo)
    state.service.poll()
    first_feed, = feed(state)
    first_change, = changes(state)
    state.clock.advance(days=14)
    state.service.retain()
    bounds = reader(state).recognition_feed_bounds(deadline=QueryDeadline.after(5))
    assert bounds.min_retained_feed_seq is None and bounds.max_feed_seq == first_feed.feed_seq
    state.source.records = [source_record(100, dst_ip="203.0.113.93",
        event_at=ni_format_utc(state.clock.value - timedelta(seconds=10)),
        ingested_at=ni_format_utc(state.clock.value - timedelta(seconds=10)))]
    original = state.attribution.resolve_ipv4
    def resolve(*args):
        value = original(*args)
        if value.state == "resolved":
            value = replace(value, valid_from=format_utc(state.clock.value - timedelta(minutes=1)),
                            valid_until=format_utc(state.clock.value + timedelta(minutes=1)))
        return value
    state.attribution.resolve_ipv4 = resolve
    state.service.poll()
    second_feed, = feed(state)
    second_change, = changes(state)
    assert second_feed.feed_seq > first_feed.feed_seq
    # Current authoritative identity is not historical binding-event garbage.
    assert second_change.change_seq == first_change.change_seq
    assert second_change.device_id == first_change.device_id


def test_G2_late_binding_allocates_one_targeted_change(state):
    state.registry.values.clear()
    install_service_recognition_extension(state.repo)
    state.service.poll()
    assert feed(state)[0].identity.device_id is None and changes(state) == ()
    state.registry.values[MAC] = RegistryEvaluation("authoritative", DEVICE)
    state.service.reconcile()
    change, = changes(state)
    assert (change.site_id, change.client_mac, change.device_id) == (SITE, MAC, DEVICE)
    assert feed(state)[0].identity.device_id == DEVICE
    state.clock.advance(seconds=30)
    state.service.reconcile()
    assert changes(state) == (change,)


def test_G2_obsolete_authoritative_index_fails_closed_and_cleanup_has_no_new_sequence(state):
    install_service_recognition_extension(state.repo)
    state.service.poll()
    first, = changes(state)
    old = dict(state.repo.binding(SITE, MAC))
    with state.repo.transaction():
        # Simulates an actual Core state transition; does not alter its existing
        # monotonic Registry outage algorithm.
        state.repo.connection.execute(
            "UPDATE projection_site_mac_bindings SET binding_state='not_yet_registry_resolved',"
            "device_id=NULL,authoritative_bound_at=NULL WHERE site_id=? AND client_mac=?", (SITE, MAC))
    with pytest.raises(ProjectionUnavailable):
        changes(state)
    with state.repo.transaction():
        maintain_authoritative_change(state.repo.connection, old, site=SITE, mac=MAC,
                                      state="not_yet_registry_resolved", device=None,
                                      evaluated_at="2026-10-09T12:01:00.000000Z")
    assert changes(state) == ()
    assert state.repo.connection.execute(
        "SELECT seq FROM sqlite_sequence WHERE name='projection_registry_binding_change_index'").fetchone()[0] == first.change_seq


@pytest.mark.parametrize("consumer_missing,budget,backup,backfill", [
    (True, 180, True, False), (False, 179, True, False),
    (False, 180, False, False), (False, 180, True, True),
])
def test_G2_R2_QA10_migration_preflight_refuses_incomplete_rollout(consumer_missing, budget, backup, backfill):
    validate = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/ni04_materialization_preflight.py"))["validate_preflight"]
    sha = "36e2b462a39533c32954215e40d9097167591237"
    evidence = dict(schema_version=1, accepted_compatibility_bridge_sha=sha,
        declared_consumers=["captive_portal_admin", "network_metadata_projection"],
        consumer_commit_shas={"captive_portal_admin": sha, "network_metadata_projection": sha},
        timeout_start_seconds=budget, backup_verified=backup, backfill_running=backfill)
    if consumer_missing:
        evidence["consumer_commit_shas"]["captive_portal_admin"] = "b1442efc434716d35e21b9e3124c3b9cd2222fbe"
    with pytest.raises(ValueError):
        validate(evidence)


def test_G2_R2_QA11_slow_install_fixture_within_declared_startup_budget(state):
    original = state.repo.crash_point
    points = []
    def slow(stage):
        if stage.startswith("extension_"):
            state.clock.advance(seconds=20)
            points.append(stage)
        original(stage)
    state.repo.crash_point = slow
    assert install_service_recognition_extension(state.repo)
    assert len(points) == 6 and 20 * len(points) < 180
    assert validate_schema(state.repo.connection, integrity=True) == "CORE_PLUS_EXTENSION_V1"


def test_G2_feed_query_uses_primary_key_search(state):
    install_service_recognition_extension(state.repo)
    state.service.poll()
    queries = []
    original = reader(state)
    snapshot = original._snapshot
    from contextlib import contextmanager
    @contextmanager
    def traced(**kwargs):
        with snapshot(**kwargs) as connection:
            connection.set_trace_callback(queries.append)
            yield connection
    original._snapshot = traced
    original.read_service_recognition_feed(0, deadline=QueryDeadline.after(5))
    query, = [q for q in queries if q.startswith("SELECT e.*,f.feed_seq")]
    plan = state.repo.connection.execute("EXPLAIN QUERY PLAN " + query).fetchall()
    details = " ".join(row[3] for row in plan)
    assert "SEARCH f USING INTEGER PRIMARY KEY" in details
    assert "SCAN e" not in details and "SCAN f" not in details


def test_G2_coverage_only_and_bounded_replay_share_exact_identity(state):
    install_service_recognition_extension(state.repo)
    state.attribution.states["203.0.113.93"] = "unavailable"
    state.service.poll()
    api = reader(state)
    first, last = "2026-10-08T13:00:00.000000Z", "2026-10-09T13:00:00.000000Z"
    before = tuple(state.repo.connection.iterdump())
    coverage = api.read_recognition_device_coverage(SITE, DEVICE, MAC, first, last, deadline=QueryDeadline.after(5))
    assert coverage.identity_binding_state == "authoritative"
    assert coverage.projection_safe_reason is None
    assert coverage.device_linked_pending_count == 0
    assert [call[1] for call in state.attribution.calls] == ["10.73.0.7"]
    assert not hasattr(coverage, "facts")
    page = api.read_candidate_page(SITE, first, last, client_mac=MAC, limit=1, deadline=QueryDeadline.after(5))
    assert len(page) == 1 and page[0].identity.device_id == DEVICE
    cursor = (page[0].fact.event_at, page[0].fact.edge_id)
    assert api.read_candidate_page(SITE, first, last, client_mac=MAC, cursor=cursor, deadline=QueryDeadline.after(5)) == ()
    assert api.read_candidate_sites(deadline=QueryDeadline.after(5)) == (SITE,)
    assert api.read_current_identity(SITE, MAC, deadline=QueryDeadline.after(5)).device_id == DEVICE
    assert tuple(state.repo.connection.iterdump()) == before
    with pytest.raises(ProjectionUnavailable):
        api.read_recognition_device_coverage(SITE, "10000000-0000-4000-8000-000000000002",
            MAC, first, last, deadline=QueryDeadline.after(5))
    assert api.read_candidate_page("f" * 24, first, last, deadline=QueryDeadline.after(5)) == ()


def test_G2_fail_closed_when_current_change_index_is_inconsistent(state):
    install_service_recognition_extension(state.repo)
    state.service.poll()
    state.repo.connection.execute("UPDATE projection_registry_binding_change_index SET device_id=?", (OTHER_MAC,))
    with pytest.raises(ProjectionUnavailable):
        feed(state)
    with pytest.raises(ProjectionUnavailable):
        changes(state)


def test_G2_preflight_complete_and_old_baseline_forbidden():
    validate = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/ni04_materialization_preflight.py"))["validate_preflight"]
    sha = "36e2b462a39533c32954215e40d9097167591237"
    value = dict(schema_version=1, accepted_compatibility_bridge_sha=sha,
        declared_consumers=["captive_portal_admin", "network_metadata_projection"],
        consumer_commit_shas={"captive_portal_admin": sha, "network_metadata_projection": sha},
        timeout_start_seconds=180, backup_verified=True, backfill_running=False)
    assert validate(value)
    with pytest.raises(ValueError):
        validate(dict(value, accepted_compatibility_bridge_sha="b1442efc434716d35e21b9e3124c3b9cd2222fbe"))
