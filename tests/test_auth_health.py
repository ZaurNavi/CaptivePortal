from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from app.auth.health import (
    AuthorizationHealthTracker,
    OUTCOME_BLOCKING_FAILURE,
    OUTCOME_RETRYABLE_FAILURE,
    OUTCOME_VERIFIED_SUCCESS,
    authorization_health_tracker_from_settings,
)
from app.auth.manager import AuthSessionManager
from app.auth.worker import AuthWorker, _WorkerRun
from app.models import Result


SITE = "0123456789abcdef01234567"
NOW = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)


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


def test_older_success_updates_last_success_without_replacing_newer_failure():
    tracker = AuthorizationHealthTracker((SITE,))
    tracker.record(SITE, OUTCOME_BLOCKING_FAILURE, NOW)
    assert tracker.record(
        SITE, OUTCOME_VERIFIED_SUCCESS, NOW - timedelta(seconds=1)
    )
    snapshot = tracker.snapshot(SITE)
    assert snapshot.outcome == OUTCOME_BLOCKING_FAILURE
    assert snapshot.observed_at == NOW
    assert snapshot.last_success_at == NOW - timedelta(seconds=1)


@pytest.mark.parametrize(
    "other_outcome",
    [OUTCOME_BLOCKING_FAILURE, OUTCOME_RETRYABLE_FAILURE],
)
def test_equal_timestamp_precedence_keeps_failure_and_records_success(
    other_outcome,
):
    tracker = AuthorizationHealthTracker((SITE,))
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(
            pool.map(
                lambda outcome: tracker.record(SITE, outcome, NOW),
                (OUTCOME_VERIFIED_SUCCESS, other_outcome),
            )
        )
    snapshot = tracker.snapshot(SITE)
    assert snapshot.outcome == other_outcome
    assert snapshot.observed_at == NOW
    assert snapshot.last_success_at == NOW


def test_newer_verified_success_recovers_latest_health_outcome():
    tracker = AuthorizationHealthTracker((SITE,))
    tracker.record(SITE, OUTCOME_BLOCKING_FAILURE, NOW)
    tracker.record(SITE, OUTCOME_VERIFIED_SUCCESS, NOW + timedelta(seconds=1))
    snapshot = tracker.snapshot(SITE)
    assert snapshot.outcome == OUTCOME_VERIFIED_SUCCESS
    assert snapshot.observed_at == NOW + timedelta(seconds=1)
    assert snapshot.last_success_at == NOW + timedelta(seconds=1)


@pytest.mark.parametrize(
    "reason",
    [
        "AUTH_TOKEN_ERROR",
        "INVALID_CREDENTIALS",
        "OMADA_HTTP_401",
        "OMADA_HTTP_403",
        "CONFIGURATION_ERROR",
        "AUTH_PROVIDER_EXCEPTION",
        "WORKER_EXCEPTION",
        "RESET_REQUEST_FAILED",
    ],
)
def test_required_blocking_failure_reasons_map_to_health(reason):
    assert AuthWorker._health_failure_outcome(reason) == OUTCOME_BLOCKING_FAILURE


def test_token_failure_is_canonicalized_to_blocking_health_reason():
    reason, retryable = AuthWorker._classify_failure(
        Result.fail("TOKEN_FAILED")
    )
    assert (reason, retryable) == ("AUTH_TOKEN_ERROR", False)
    assert AuthWorker._health_failure_outcome(reason) == OUTCOME_BLOCKING_FAILURE


@pytest.mark.parametrize(
    "reason",
    [
        "OMADA_REQUEST_TIMEOUT",
        "OMADA_CONNECTION_ERROR",
        "OMADA_UNAVAILABLE",
        "OMADA_HTTP_5XX",
        "AUTHORIZATION_TIMEOUT",
    ],
)
def test_retryable_failure_reasons_remain_retryable(reason):
    assert AuthWorker._health_failure_outcome(reason) == OUTCOME_RETRYABLE_FAILURE


@pytest.mark.parametrize(
    "reason",
    [
        "CLIENT_NOT_FOUND",
        "CLIENT_NOT_READY",
        "CLIENT_BLOCKED",
        "AUTHORIZATION_REJECTED",
        "AUTHORIZATION_REJECTED_FINAL",
    ],
)
def test_client_and_authorization_rejections_are_not_system_health(reason):
    assert AuthWorker._health_failure_outcome(reason) is None
