from __future__ import annotations

from app.auth.health import (
    AuthorizationHealthTracker,
    OUTCOME_BLOCKING_FAILURE,
    OUTCOME_VERIFIED_SUCCESS,
    authorization_health_tracker_from_settings,
)
from app.auth.manager import AuthSessionManager
from app.auth.worker import AuthWorker, _WorkerRun
from app.models import Result


SITE = "0123456789abcdef01234567"


def _session():
    manager = AuthSessionManager()
    session, created = manager.create_or_get(
        SITE, "02-11-22-33-44-55", client_ip="192.0.2.1"
    )
    assert created
    run = _WorkerRun(session.session_id, 1, session.current_run_token)
    return manager, session, run


def test_verified_authorization_records_only_product_safe_evidence():
    manager, session, run = _session()
    tracker = AuthorizationHealthTracker((SITE,))
    worker = AuthWorker(object(), manager, authorization_health_tracker=tracker)
    worker._mark_authorized(
        session,
        Result.ok(data={"authStatus": 2}),
        run,
        final_reason="AUTHORIZED_AFTER_ATTEMPT",
    )
    evidence = tracker.snapshot(SITE)
    assert evidence.outcome == OUTCOME_VERIFIED_SUCCESS
    assert evidence.observed_at == evidence.last_success_at
    assert not any(
        hasattr(evidence, name)
        for name in ("client_mac", "client_ip", "ssid", "session_id", "token")
    )


def test_client_failure_is_ignored_but_blocking_system_failure_is_recorded():
    manager, session, run = _session()
    tracker = AuthorizationHealthTracker((SITE,))
    worker = AuthWorker(object(), manager, authorization_health_tracker=tracker)
    worker._finish_failed(
        session,
        run,
        final_reason="CLIENT_NOT_FOUND",
        retryable=True,
        error="not found",
    )
    assert tracker.snapshot(SITE).outcome is None

    manager, session, run = _session()
    worker = AuthWorker(object(), manager, authorization_health_tracker=tracker)
    worker._finish_failed(
        session,
        run,
        final_reason="AUTH_TOKEN_ERROR",
        retryable=False,
        error="unavailable",
    )
    assert tracker.snapshot(SITE).outcome == OUTCOME_BLOCKING_FAILURE


def test_tracker_failure_never_changes_authorization_result():
    class Broken:
        def record(self, *_args):
            raise RuntimeError("health unavailable")

    manager, session, run = _session()
    worker = AuthWorker(object(), manager, authorization_health_tracker=Broken())
    worker._mark_authorized(
        session,
        Result.ok(data={"authStatus": 2}),
        run,
        final_reason="AUTHORIZED_AFTER_ATTEMPT",
    )
    assert manager.snapshot(session)["status"] == "AUTHORIZED"


def test_tracker_factory_accepts_only_canonical_configured_site_ids():
    tracker = authorization_health_tracker_from_settings(
        {"web_admin_allowed_site_ids": SITE}
    )
    assert tracker.site_count == 1
    for value in (
        SITE.upper(),
        "g" * 24,
        "a" * 23,
        f"{SITE}, {SITE}",
    ):
        disabled = authorization_health_tracker_from_settings(
            {"web_admin_allowed_site_ids": value}
        )
        assert disabled.site_count == 0
