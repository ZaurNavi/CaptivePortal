from types import SimpleNamespace
import sqlite3

import pytest

from app.auth.manager import AuthSessionManager
from app.auth.worker import AuthWorker, _WorkerRun
from app.auth.session import AuthStatus
from app.models import Result
from app.device_fingerprint_integration.submitter import DurableFingerprintIntegrationSubmitter
from .test_repository_identity import repository, SITE, MAC


@pytest.mark.parametrize("failure", [None, "busy", "unavailable", "unexpected"])
def test_authorized_authrun_hook_order_and_fail_open(tmp_path, failure):
    repo = repository(tmp_path)
    manager = AuthSessionManager()
    session, _ = manager.create_or_get(SITE, MAC, "192.168.8.2")
    manager.claim_worker(session, 1, session.current_run_token)
    calls = []
    class Snapshot:
        def submit(self, request):
            calls.append("registry")
    class Visit:
        def submit_authorized(self, request):
            calls.append("visit")
    class Submission:
        def submit_authorized(self, request):
            assert session.status == AuthStatus.AUTHORIZED
            assert manager.run_snapshot(session, 1)["final_state"] == AuthStatus.AUTHORIZED.value
            calls.append("integration")
            if failure == "busy":
                raise sqlite3.OperationalError("database is locked")
            if failure is not None:
                raise RuntimeError("synthetic unavailable")
            return DurableFingerprintIntegrationSubmitter(repo).submit_authorized(request)
    worker = AuthWorker(None, manager, snapshot_collector=Snapshot(), visit_start_submitter=Visit(),
                        fingerprint_integration_submitter=Submission())
    run = _WorkerRun(session.session_id, 1, session.current_run_token)
    worker._mark_authorized(session, Result.ok(data={"authStatus": 2}), run, final_reason="AUTHORIZED")
    assert session.status == AuthStatus.AUTHORIZED
    assert calls == ["registry", "visit", "integration"]
    with repo.connection(readonly=True) as conn:
        assert conn.execute("SELECT count(*) FROM integration_jobs").fetchone()[0] == (1 if failure is None else 0)


def test_default_worker_noop_preserves_authorization_and_existing_submissions():
    manager = AuthSessionManager()
    session, _ = manager.create_or_get("legacy-site", MAC, "192.168.8.2")
    manager.claim_worker(session, 1, session.current_run_token)
    worker = AuthWorker(None, manager)
    worker._mark_authorized(session, Result.ok(), _WorkerRun(session.session_id, 1, session.current_run_token),
                            final_reason="AUTHORIZED")
    assert session.status == AuthStatus.AUTHORIZED
