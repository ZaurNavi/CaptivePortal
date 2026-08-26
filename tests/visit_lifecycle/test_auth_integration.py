from __future__ import annotations

from app.auth.manager import AuthSessionManager
from app.auth.session import AuthStatus
from app.auth.worker import AuthWorker, _WorkerRun
from app.models import Result


class CapturingSink:
    def __init__(self, raises=False):
        self.requests = []
        self.raises = raises

    def submit_authorized(self, request):
        if self.raises:
            raise OSError("visit database unavailable")
        self.requests.append(request)


class CapturingSnapshotCollector:
    def __init__(self):
        self.requests = []

    def submit(self, request):
        self.requests.append(request)


def _session_and_run():
    manager = AuthSessionManager()
    session, created = manager.create_or_get(
        "site-a",
        "02-11-22-33-44-55",
        client_ip="192.0.2.10",
        ap_mac="02-AA-BB-CC-DD-EE",
        ssid="Zefer_Parki",
        radio_id="0",
    )
    assert created
    session.runs[0].auth_attempt_count = 2
    run = _WorkerRun(
        session_id=session.session_id,
        run_number=1,
        run_token=session.current_run_token,
    )
    return manager, session, run


def test_authorized_submits_independent_snapshot_and_visit_evidence():
    manager, session, run = _session_and_run()
    snapshots = CapturingSnapshotCollector()
    visits = CapturingSink()
    worker = AuthWorker(object(), manager, snapshots, visits)
    worker._mark_authorized(
        session,
        Result.ok(data={"authStatus": 2}),
        run,
        final_reason="AUTHORIZED_AFTER_ATTEMPT",
    )
    assert len(snapshots.requests) == 1
    assert len(visits.requests) == 1
    request = visits.requests[0]
    assert request.auth_session_id == session.session_id
    assert request.site_id == "site-a"
    assert request.client_mac == "02-11-22-33-44-55"
    assert request.auth_run_number == 1
    assert request.authorization_attempt == 2
    assert request.final_reason == "AUTHORIZED_AFTER_ATTEMPT"
    assert request.portal_ssid == "Zefer_Parki"
    assert request.portal_radio_id == "0"
    assert manager.snapshot(session)["status"] == AuthStatus.AUTHORIZED.value


def test_visit_sink_failure_is_fail_open_and_snapshot_semantics_are_unchanged():
    manager, session, run = _session_and_run()
    snapshots = CapturingSnapshotCollector()
    worker = AuthWorker(object(), manager, snapshots, CapturingSink(raises=True))
    worker._mark_authorized(
        session,
        Result.ok(data={"authStatus": 2}),
        run,
        final_reason="AUTHORIZED_FINAL_VERIFY",
    )
    assert len(snapshots.requests) == 1
    state = manager.snapshot(session)
    assert state["status"] == AuthStatus.AUTHORIZED.value
    assert state["final_reason"] == "AUTHORIZED_FINAL_VERIFY"
