from __future__ import annotations

import copy

import pytest

from app.auth.manager import AuthSessionManager
from app.auth.worker import AuthWorker, _WorkerRun
from app.models import Result
from app.visitor_registry.snapshot_collector import (
    DisabledVisitorSnapshotCollector,
)
from app.visitor_registry.snapshot_models import SnapshotSubmitOutcome


class CapturingCollector:
    def __init__(self, raises=False):
        self.requests = []
        self.raises = raises

    def submit(self, request):
        if self.raises:
            raise OSError("collector unavailable")
        self.requests.append(request)
        return SnapshotSubmitOutcome.ACCEPTED


class Controller:
    pass


def session_and_run():
    manager = AuthSessionManager()
    session, created = manager.create_or_get(
        "site-id",
        "02-11-22-33-44-55",
        client_ip="192.0.2.27",
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


@pytest.mark.parametrize(
    "reason",
    [
        "ALREADY_AUTHORIZED",
        "AUTHORIZED_AFTER_ATTEMPT",
        "AUTHORIZED_FINAL_VERIFY",
        "FUTURE_SUCCESS_REASON",
    ],
)
def test_every_authorized_final_reason_submits_once(reason):
    manager, session, run = session_and_run()
    collector = CapturingCollector()
    worker = AuthWorker(Controller(), manager, collector)
    worker._mark_authorized(
        session,
        Result.ok(data={"authStatus": 2}),
        run,
        final_reason=reason,
    )
    assert len(collector.requests) == 1
    actual = collector.requests[0]
    completed = manager.run_snapshot(session, 1)
    assert actual.auth_session_id == session.session_id
    assert actual.site_id == "site-id"
    assert actual.requested_mac == "02-11-22-33-44-55"
    assert actual.authorized_at.isoformat() == completed["finished_at"]
    assert actual.auth_context.auth_run_number == 1
    assert actual.auth_context.authorization_attempt == 2
    assert actual.auth_context.auth_final_reason == reason
    assert actual.auth_context.retry_request_id is None
    assert actual.auth_context.client_ip == "192.0.2.27"
    assert actual.auth_context.portal_ssid == "Zefer_Parki"
    assert actual.auth_context.portal_ap_mac == (
        "02-AA-BB-CC-DD-EE"
    )
    assert actual.auth_context.portal_radio_id == "0"


def test_snapshot_request_does_not_reference_mutable_session_or_run():
    manager, session, run = session_and_run()
    collector = CapturingCollector()
    worker = AuthWorker(Controller(), manager, collector)
    worker._mark_authorized(
        session,
        Result.ok(data={"authStatus": 2}),
        run,
        final_reason="AUTHORIZED",
    )
    actual = collector.requests[0]
    before = copy.deepcopy(actual)
    session.client_ip = "192.0.2.99"
    session.ssid = "Other"
    session.runs[0].auth_attempt_count = 99
    assert actual == before


def test_collector_exception_cannot_change_authorization(caplog):
    manager, session, run = session_and_run()
    worker = AuthWorker(
        Controller(),
        manager,
        CapturingCollector(raises=True),
    )
    worker._mark_authorized(
        session,
        Result.ok(data={"authStatus": 2}),
        run,
        final_reason="AUTHORIZED",
    )
    snapshot = manager.run_snapshot(session, 1)
    assert snapshot["final_state"] == "AUTHORIZED"
    assert snapshot["retryable"] is False
    assert "visitor_snapshot_submission_failed" in caplog.text


def test_stale_finish_cannot_submit():
    manager, session, run = session_and_run()
    collector = CapturingCollector()
    worker = AuthWorker(Controller(), manager, collector)
    stale = _WorkerRun(
        session_id=run.session_id,
        run_number=run.run_number,
        run_token="stale-token",
    )
    with pytest.raises(RuntimeError):
        worker._mark_authorized(
            session,
            Result.ok(data={"authStatus": 2}),
            stale,
            final_reason="AUTHORIZED",
        )
    assert collector.requests == []


def test_failed_and_expired_runs_do_not_submit():
    manager, session, run = session_and_run()
    collector = CapturingCollector()
    worker = AuthWorker(Controller(), manager, collector)
    worker._finish_failed(
        session,
        run,
        final_reason="FAILED",
        retryable=False,
        error="failed",
    )
    assert collector.requests == []

    manager2, session2, run2 = session_and_run()
    collector2 = CapturingCollector()
    worker2 = AuthWorker(Controller(), manager2, collector2)
    worker2._expire_session(session2, run2)
    assert collector2.requests == []


def app_settings():
    return {
        "portal_counter_enabled": False,
        "portal_counter_db_path": "unused.db",
        "portal_counter_timezone": "Asia/Baku",
        "portal_counter_api_enabled": False,
        "public_traffic_counter_enabled": False,
        "public_traffic_ssid": "Zefer_Parki",
        "public_traffic_db_path": "unused-traffic.db",
        "public_traffic_scan_interval_seconds": 10,
        "public_traffic_frontend_refresh_seconds": 60,
        "auth_telemetry_enabled": False,
        "auth_telemetry_log_path": "unused.log",
        "auth_telemetry_level": "INFO",
        "auth_telemetry_schema_version": 1,
        "auth_telemetry_rotation_max_bytes": 1000,
        "auth_telemetry_rotation_backup_count": 1,
        "omada_webhook_enabled": False,
        "omada_webhook_allowed_ips": "",
        "omada_webhook_auth_mode": "ip_only",
        "omada_webhook_shared_secret": "",
        "omada_webhook_header_token": "",
        "omada_webhook_max_body_bytes": 1000,
        "omada_webhook_log_file": "raw.log",
        "omada_webhook_normalized_log_file": "normalized.log",
        "capport_enabled": False,
    }


def test_create_app_uses_injected_provider_and_collector(monkeypatch):
    import app.web.web as web

    controller = Controller()
    collector = CapturingCollector()
    monkeypatch.setattr(web, "get_settings", app_settings)
    monkeypatch.setattr(
        web,
        "create_controller",
        lambda: (_ for _ in ()).throw(
            AssertionError("second provider created")
        ),
    )
    app = web.create_app(
        portal_counter_service=None,
        public_traffic_service=None,
        controller=controller,
        visitor_snapshot_collector=collector,
    )
    assert app.extensions["visitor_snapshot_collector"] is collector
    handler = app.extensions["portal_entry_handler"]
    assert handler._auth_worker._provider is controller
    assert handler._auth_worker._snapshot_collector is collector


def test_create_app_without_collector_uses_disabled(monkeypatch):
    import app.web.web as web

    monkeypatch.setattr(web, "get_settings", app_settings)
    app = web.create_app(
        portal_counter_service=None,
        public_traffic_service=None,
        controller=Controller(),
    )
    assert isinstance(
        app.extensions["visitor_snapshot_collector"],
        DisabledVisitorSnapshotCollector,
    )
