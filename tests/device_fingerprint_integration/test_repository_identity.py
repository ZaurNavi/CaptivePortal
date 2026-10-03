from dataclasses import replace
from types import SimpleNamespace
import sqlite3
import uuid
import json
import logging

import pytest

from app.device_fingerprint_integration.models import (
    AuthorizedFingerprintRequest, IntegrationError, IdentityResolution, plus,
)
from app.device_fingerprint_integration.repository import IntegrationRepository
from app.device_fingerprint_integration.config import integration_config_from_settings
from app.device_fingerprint_integration.runtime import create_fingerprint_integration_submitter, create_worker
from app.device_fingerprint_integration.submitter import DISABLED_FINGERPRINT_INTEGRATION_SUBMITTER, emit
from app.device_fingerprint_integration.identity_resolver import ExactIdentityResolver
from app.device_fingerprint_integration.worker import IntegrationWorker, consumer_lock
from app.device_fingerprint_integration.read_service import FingerprintIntegrationReadService
from tests.device_fingerprint import SITE
from tests.device_fingerprint_task04_t01.test_snapshot_service import MAC

A = "2026-09-15T12:00:00.000Z"
SESSION, DEVICE, SNAPSHOT, VISIT = (str(uuid.uuid4()) for _ in range(4))


def request(**changes):
    return replace(AuthorizedFingerprintRequest(SESSION, 1, SITE, MAC, A), **changes)


def repository(tmp_path):
    repo = IntegrationRepository(tmp_path / "integration.sqlite")
    repo.initialize()
    return repo


def job(repo, **changes):
    identity, _ = repo.enqueue(request(**changes), A)
    return repo.get(identity)


def visit(**changes):
    return SimpleNamespace(**{**dict(site_id=SITE, client_mac=MAC, start_auth_session_id=SESSION,
        start_auth_run_number=1, device_id=DEVICE, visit_id=VISIT), **changes})


def resolver(snapshot=None, opened=None, history=()):
    class Registry:
        def get_snapshot_by_auth_session(self, session, *, site_id, client_mac):
            assert (session, site_id, client_mac) == (SESSION, SITE, MAC)
            return snapshot

        def get_device_by_mac(self, *_args):
            raise AssertionError("Bare MAC lookup forbidden")

    class Visits:
        def get_open_visit(self, site, mac):
            assert (site, mac) == (SITE, MAC)
            return opened

        def list_visits(self, site, start, end, **kwargs):
            assert (site, start, end) == (SITE, plus(A, -3600), plus(A, 3600))
            assert kwargs == dict(client_mac=MAC, limit=100)
            return SimpleNamespace(items=history)

    return ExactIdentityResolver(Registry(), Visits())


def snapshot(**changes):
    return {**dict(site_id=SITE, auth_session_id=SESSION, requested_mac=MAC,
                   device_id=DEVICE, snapshot_id=SNAPSHOT), **changes}


def test_disabled_and_invalid_config_never_initialize_or_break_portal(tmp_path):
    assert integration_config_from_settings({"device_fingerprint_integration_db_path": None}).enabled is False
    assert create_fingerprint_integration_submitter({}) is DISABLED_FINGERPRINT_INTEGRATION_SUBMITTER
    assert create_fingerprint_integration_submitter({"device_fingerprint_integration_enabled": "bad"}) is DISABLED_FINGERPRINT_INTEGRATION_SUBMITTER
    assert not list(tmp_path.iterdir())


def test_config_paths_distinct_and_real_settings_path(tmp_path):
    paths = {"device_fingerprint_integration_enabled": True,
             "device_fingerprint_integration_db_path": str(tmp_path / "integration.sqlite"),
             "device_fingerprint_evidence_db_path": str(tmp_path / "evidence.sqlite"),
             "device_fingerprint_classification_db_path": str(tmp_path / "class.sqlite"),
             "device_fingerprint_control_plane_db_path": str(tmp_path / "control.sqlite")}
    submitter = create_fingerprint_integration_submitter(paths)
    assert submitter is not DISABLED_FINGERPRINT_INTEGRATION_SUBMITTER
    assert submitter.repository.path.exists()
    with pytest.raises(ValueError):
        integration_config_from_settings({**paths, "device_fingerprint_classification_db_path": paths["device_fingerprint_integration_db_path"]})


def test_durable_idempotency_new_run_and_fixed_timing(tmp_path):
    repo = repository(tmp_path)
    first = job(repo)
    assert repo.enqueue(request(), plus(A, 10)) == (first.integration_id, False)
    assert repo.get(first.integration_id) == first
    second = job(repo, auth_run_number=2)
    assert second.integration_id != first.integration_id
    assert second.planned_classification_id != first.planned_classification_id
    assert uuid.UUID(first.planned_classification_id).version == 4
    assert first.due_at_utc == plus(A, 150)
    assert repo.claim(plus(A, 149)) is None


@pytest.mark.parametrize("change", [dict(site_id="b" * 24), dict(observed_mac="02:11:22:33:44:55"),
                                   dict(authorized_at_utc=plus(A, 1))])
def test_duplicate_immutable_identity_conflict(tmp_path, change):
    repo = repository(tmp_path)
    original = job(repo)
    with pytest.raises(IntegrationError, match="integration_identity_conflict"):
        repo.enqueue(request(**change), A)
    assert repo.get(original.integration_id) == original


def test_lease_claim_no_steal_expiry_reclaim_and_token_cas(tmp_path):
    repo = repository(tmp_path)
    job(repo)
    first, _ = repo.claim(plus(A, 150))
    assert first.attempt_count == 1
    assert repo.claim(plus(A, 449)) is None
    second, _ = repo.claim(plus(A, 450))
    assert second.attempt_count == 2 and second.lease_token != first.lease_token
    assert not repo.finish(first, plus(A, 451), state="NO_RESULT_FINAL")
    assert repo.finish(second, plus(A, 451), state="NO_RESULT_FINAL")


def test_busy_is_bounded_and_never_widens_concurrency(tmp_path):
    repo = repository(tmp_path)
    with sqlite3.connect(repo.path, isolation_level=None) as blocker:
        blocker.execute("BEGIN IMMEDIATE")
        with pytest.raises(IntegrationError, match="retryable_sqlite_busy"):
            repo.enqueue(request(), A)
        blocker.rollback()
    assert repo.enqueue(request(), A)[1]


def test_single_consumer_even_if_db_lease_expired(tmp_path):
    repo = repository(tmp_path)
    pending = job(repo)
    with consumer_lock(repo.path) as acquired:
        assert acquired
        worker = IntegrationWorker(repo, None, None, clock=lambda: plus(A, 1000))
        assert worker.run_once() is False
    assert repo.get(pending.integration_id).attempt_count == 0


@pytest.mark.parametrize("changed", [dict(site_id="b" * 24), dict(requested_mac="02:11:22:33:44:55"),
                                    dict(auth_session_id=str(uuid.uuid4()))])
def test_registry_exact_tuple_mismatch_is_never_resolved(tmp_path, changed):
    assert resolver(snapshot(**changed)).resolve(job(repository(tmp_path))).state == "CONFLICT"


def test_exact_registry_and_visit_open_or_history(tmp_path):
    candidate = job(repository(tmp_path))
    device = resolver(snapshot()).resolve(candidate)
    assert (device.state, device.device_id, device.snapshot_id) == ("DEVICE_RESOLVED", DEVICE, SNAPSHOT)
    for opened, history in ((visit(), ()), (visit(start_auth_run_number=9), (visit(),))):
        resolved = resolver(snapshot(), opened, history).resolve(candidate)
        assert (resolved.state, resolved.visit_id) == ("DEVICE_AND_VISIT_RESOLVED", VISIT)


@pytest.mark.parametrize("changes", [dict(start_auth_run_number=2), dict(site_id="b" * 24),
    dict(client_mac="02:11:22:33:44:55"), dict(start_auth_session_id=str(uuid.uuid4()))])
def test_nonmatching_visit_is_not_linked(tmp_path, changes):
    resolved = resolver(snapshot(), visit(**changes)).resolve(job(repository(tmp_path)))
    assert resolved.state == "DEVICE_RESOLVED" and resolved.visit_id is None


def test_conflicting_exact_device_ids_never_choose_a_winner(tmp_path):
    candidate = job(repository(tmp_path))
    assert resolver(snapshot(), visit(device_id=str(uuid.uuid4()))).resolve(candidate).state == "CONFLICT"
    candidate = replace(candidate, device_id=str(uuid.uuid4()), registry_snapshot_id=SNAPSHOT, identity_state="DEVICE_RESOLVED")
    assert resolver(snapshot()).resolve(candidate).state == "CONFLICT"


def test_unresolved_is_valid_and_identity_retries_stop_at_hour(tmp_path):
    repo = repository(tmp_path)
    pending = job(repo)
    worker = IntegrationWorker(repo, None, resolver(), clock=lambda: A)
    assert worker.run_once()
    assert repo.get(pending.integration_id).identity_state == "UNRESOLVED"
    assert repo.identity_due(plus(A, 29)) is None
    assert repo.identity_due(plus(A, 30)) is not None
    repo.save_identity(pending, IdentityResolution(reason="identity_proof_unavailable"), plus(A, 3600))
    assert repo.identity_due(plus(A, 3630)) is None


def test_relation_only_schema_and_read_refuses_unresolved_conflict(tmp_path):
    repo = repository(tmp_path)
    pending = job(repo)
    reader = FingerprintIntegrationReadService(repo, None)
    assert reader.get_current_for_device(SITE, DEVICE) is None
    assert reader.get_for_auth_run("b" * 24, SESSION, 1) is None
    assert reader.get_for_auth_run(SITE, SESSION, 1) is None
    with repo.connection(readonly=True) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(integration_jobs)")}
        assert not columns & {"payload_json", "platform", "device_class", "manufacturer", "model", "raw_evidence"}
    repo.save_identity(pending, IdentityResolution("CONFLICT", "identity_device_conflict"), A)
    assert reader.get_current_for_device(SITE, DEVICE) is None


def test_worker_composition_does_not_mutate_other_domain_databases(tmp_path):
    paths = {}
    for key in ("evidence", "classification", "control_plane"):
        path = tmp_path / (key + ".sqlite")
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE untouched(value)")
        paths[f"device_fingerprint_{key}_db_path"] = str(path)
    original = {path: path.read_bytes() for path in tmp_path.glob("*.sqlite")}
    worker = create_worker({**paths, "device_fingerprint_integration_enabled": True,
        "device_fingerprint_integration_db_path": str(tmp_path / "integration.sqlite"),
        "visitor_registry_db_path": str(tmp_path / "registry.sqlite"),
        "visit_lifecycle_db_path": str(tmp_path / "visits.sqlite"), "portal_counter_timezone": "UTC"})
    worker.stop()
    assert all(path.read_bytes() == data for path, data in original.items())
    assert not (tmp_path / "registry.sqlite").exists() and not (tmp_path / "visits.sqlite").exists()


@pytest.mark.parametrize("reason", ["snapshot_timeout", "snapshot_memory_pressure", "persistence_unavailable",
                                   "integration_unavailable", "binding_unavailable"])
def test_bounded_retry_schedule_and_shutdown_restart(tmp_path, reason):
    repo = repository(tmp_path)
    original = job(repo)
    class Executor:
        def execute(self, *_args, **_kwargs):
            raise IntegrationError(reason)
    now = plus(A, 150)
    worker = IntegrationWorker(repo, Executor(), resolver(), clock=lambda: now)
    for attempt, delay in enumerate((30, 120, 300, 600, None), 1):
        worker.run_once()
        stored = repo.get(original.integration_id)
        assert stored.attempt_count == attempt
        assert stored.last_reason_code == reason
        if reason == "binding_unavailable" or delay is None:
            assert stored.classification_state == "NO_RESULT_FINAL"
            break
        assert stored.classification_state == "PENDING" and stored.next_attempt_at_utc == plus(now, delay)
        assert repo.claim(plus(now, delay - 1)) is None
        worker.stop()
        now = plus(now, delay)
        worker = IntegrationWorker(IntegrationRepository(repo.path), Executor(), resolver(), clock=lambda: now)


@pytest.mark.parametrize("mac", ["02:11:22:33:44:55", "AA:BB:CC:DD:EE:FF"])
def test_randomized_mac_and_same_mac_cross_site_have_no_identity_shortcut(tmp_path, mac):
    repo = repository(tmp_path)
    a = job(repo, observed_mac=mac)
    b = job(repo, auth_session_id=str(uuid.uuid4()), site_id="b" * 24, observed_mac=mac)
    assert a.observed_mac == b.observed_mac
    assert a.site_id != b.site_id
    assert a.integration_id != b.integration_id
    reader = FingerprintIntegrationReadService(repo, None)
    assert reader.get_current_for_device(a.site_id, DEVICE) is None
    assert reader.get_current_for_device(b.site_id, DEVICE) is None


def test_expired_last_attempt_is_recovery_only_not_a_sixth_classification(tmp_path):
    repo = repository(tmp_path)
    original = job(repo)
    with repo.connection() as conn:
        conn.execute("UPDATE integration_jobs SET classification_state='LEASED', attempt_count=5, lease_token=?, lease_until_utc=?",
                     (str(uuid.uuid4()), plus(A, 150)))
    leased, recovery_only = repo.claim(plus(A, 150))
    assert recovery_only and leased.attempt_count == 5
    assert repo.finish(leased, plus(A, 151), state="NO_RESULT_FINAL", reason="snapshot_timeout")
    assert repo.claim(plus(A, 10000)) is None


def test_expired_lease_token_cannot_finalize_even_without_reclaim(tmp_path):
    repo = repository(tmp_path)
    original = job(repo)
    leased, _ = repo.claim(plus(A, 150))
    assert not repo.finish(leased, plus(A, 450), state="NO_RESULT_FINAL")
    assert repo.get(original.integration_id).classification_state == "LEASED"


def test_conflict_preserves_previously_proven_immutable_anchors(tmp_path):
    candidate = replace(job(repository(tmp_path)), identity_state="DEVICE_AND_VISIT_RESOLVED",
                        registry_snapshot_id=SNAPSHOT, device_id=DEVICE, visit_id=VISIT)
    for exact in (resolver(snapshot(site_id="b" * 24)),
                  resolver(snapshot(), visit(device_id=str(uuid.uuid4()))),
                  resolver(snapshot(), None, (visit(), visit(visit_id=str(uuid.uuid4()))))):
        conflict = exact.resolve(candidate)
        assert conflict.state == "CONFLICT"
        assert (conflict.snapshot_id, conflict.device_id, conflict.visit_id) == (SNAPSHOT, DEVICE, VISIT)


def test_structured_telemetry_excludes_unapproved_payload_fields(caplog):
    with caplog.at_level(logging.INFO, logger="captivportal.fingerprint.integration"):
        emit("fingerprint.integration_worker_health", reason_code="ready", raw_evidence="secret")
    payload = json.loads(caplog.records[-1].getMessage())
    assert payload == {"event": "fingerprint.integration_worker_health", "reason_code": "ready"}


def test_expired_failure_cas_does_not_claim_terminal_success_in_telemetry(tmp_path, caplog):
    repo = repository(tmp_path)
    original = job(repo)
    now = plus(A, 150)
    class Executor:
        def execute(self, *_args, **_kwargs):
            nonlocal now
            now = plus(A, 450)
            raise IntegrationError("binding_unavailable")
    with caplog.at_level(logging.INFO, logger="captivportal.fingerprint.integration"):
        IntegrationWorker(repo, Executor(), resolver(), clock=lambda: now).run_once()
    assert repo.get(original.integration_id).classification_state == "LEASED"
    events = [json.loads(record.getMessage())["event"] for record in caplog.records]
    assert "fingerprint.integration_classification_no_result" not in events
    assert any(json.loads(record.getMessage()).get("reason_code") == "lease_lost" for record in caplog.records)


def test_worker_telemetry_inherits_existing_application_logger_configuration():
    from app.logger import logger as application_logger
    from app.device_fingerprint_integration.submitter import logger as integration_logger
    assert integration_logger.parent is application_logger
    assert integration_logger.getEffectiveLevel() == application_logger.getEffectiveLevel()
    assert integration_logger.propagate and application_logger.handlers
