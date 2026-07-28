import json
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from app.auth.manager import (
    AuthSessionManager,
    RetryOutcome,
)
from app.auth.session import AuthStatus
from app.auth.worker import AuthWorker
from app.auth_telemetry import events
from app.auth_telemetry.service import AuthorizationTelemetry
from app.models import Result


CLIENT_IP = "192.168.1.25"
CLIENT_MAC = "AA-BB-CC-DD-EE-FF"
SITE_ID = "park"


class CapturingExecutor:
    def __init__(self, fail_after=None):
        self.submissions = []
        self.fail_after = fail_after

    def submit(self, function, session_id):
        if (
            self.fail_after is not None
            and len(self.submissions) >= self.fail_after
        ):
            raise RuntimeError("executor temporarily unavailable")
        self.submissions.append((function, session_id))
        return object()


class AuthorizedProvider:
    def get_client(self, **_kwargs):
        return Result.ok(data={
            "http_status": 200,
            "error_code": 0,
            "authStatus": 2,
            "active": True,
        })

    def authorize(self, **_kwargs):
        return Result.ok()

    def unauthorize(self, **_kwargs):
        return Result.ok()


class IpResolvingProvider(AuthorizedProvider):
    def get_client_by_ip(self, **_kwargs):
        return Result.ok(data={
            "found": True,
            "client_mac": CLIENT_MAC,
            "http_status": 200,
            "error_code": 0,
        })


class MissingClientProvider:
    def __init__(self):
        self.authorize_calls = 0
        self.unauthorize_calls = 0

    def get_client_by_ip(self, **_kwargs):
        return Result.ok(data={
            "found": False,
            "client_mac": None,
            "http_status": 200,
            "error_code": 0,
        })

    def authorize(self, **_kwargs):
        self.authorize_calls += 1
        return Result.ok()

    def unauthorize(self, **_kwargs):
        self.unauthorize_calls += 1
        return Result.ok()


class KnownMacMissingClientProvider(MissingClientProvider):
    def get_client(self, **_kwargs):
        return Result.fail(
            error="CLIENT_NOT_FOUND",
            message="Client does not exist.",
            data={
                "http_status": 404,
                "error_code": -41011,
                "authStatus": None,
                "active": None,
            },
        )


class BlockingVerificationProvider:
    def __init__(self):
        self.get_client_calls = 0
        self.verification_started = threading.Event()
        self.release_verification = threading.Event()

    def get_client(self, **_kwargs):
        self.get_client_calls += 1
        if self.get_client_calls == 2:
            self.verification_started.set()
            self.release_verification.wait(timeout=5)
            auth_status = 2
        else:
            auth_status = 0
        return Result.ok(data={
            "http_status": 200,
            "error_code": 0,
            "authStatus": auth_status,
            "active": True,
        })

    def authorize(self, **_kwargs):
        return Result.ok()

    def unauthorize(self, **_kwargs):
        return Result.ok()


class BlockingCleanupProvider:
    def __init__(self):
        self.cleanup_started = threading.Event()
        self.release_cleanup = threading.Event()
        self.authorize_calls = 0
        self.unauthorize_calls = 0

    def get_client(self, **_kwargs):
        return Result.ok(data={
            "http_status": 200,
            "error_code": 0,
            "authStatus": 0,
            "active": True,
        })

    def authorize(self, **_kwargs):
        self.authorize_calls += 1
        return Result.ok()

    def unauthorize(self, **_kwargs):
        self.unauthorize_calls += 1
        self.cleanup_started.set()
        self.release_cleanup.wait(timeout=5)
        return Result.ok()


class ExplicitRejectionInactiveProvider:
    def __init__(self):
        self.get_client_calls = 0
        self.authorize_calls = 0
        self.unauthorize_calls = 0

    def get_client(self, **_kwargs):
        self.get_client_calls += 1
        return Result.ok(data={
            "http_status": 200,
            "error_code": 0,
            "authStatus": 0,
            "active": False,
        })

    def authorize(self, **_kwargs):
        self.authorize_calls += 1
        return Result.fail(
            error="AUTH_FAILED",
            message="Failed to authorize this client.",
            data={
                "http_status": 200,
                "error_code": -1,
            },
        )

    def unauthorize(self, **_kwargs):
        self.unauthorize_calls += 1
        return Result.ok()


class CapturingTelemetry:
    def __init__(self):
        self.records = []

    def safe_emit(self, event, session_id, level, **fields):
        self.records.append({
            "event": event,
            "session_id": session_id,
            "level": level,
            **fields,
        })
        return True

    def safe_emit_once(self, event, session_id, level, **fields):
        return self.safe_emit(
            event,
            session_id,
            level,
            **fields,
        )


@contextmanager
def fast_worker():
    with (
        patch("app.auth.worker.MIN_INITIAL_DELAY_SECONDS", 0),
        patch("app.auth.worker.AUTH_FALLBACK_DELAY_SECONDS", 0),
        patch("app.auth.worker.CLIENT_READY_POLL_SECONDS", 0),
        patch("app.auth.worker.VERIFY_DELAY_SECONDS", 0),
    ):
        yield


def settings(temp_dir):
    return {
        "portal_counter_enabled": False,
        "portal_counter_db_path": str(
            Path(temp_dir) / "counter.db"
        ),
        "portal_counter_timezone": "Asia/Baku",
        "portal_counter_api_enabled": False,
        "auth_telemetry_enabled": False,
        "auth_telemetry_log_path": str(
            Path(temp_dir) / "auth.log"
        ),
        "auth_telemetry_level": "DEBUG",
        "auth_telemetry_schema_version": 1,
        "auth_telemetry_rotation_max_bytes": 1_000_000,
        "auth_telemetry_rotation_backup_count": 2,
        "capport_enabled": False,
    }


def create_client(executor=None, controller=None):
    import app.web.web as web_module

    temp_dir = tempfile.TemporaryDirectory()
    executor = executor or CapturingExecutor()
    web_module.auth_manager = AuthSessionManager()
    with (
        patch.object(
            web_module,
            "get_settings",
            return_value=settings(temp_dir.name),
        ),
        patch.object(
            web_module,
            "create_controller",
            return_value=controller or AuthorizedProvider(),
        ),
        patch.object(
            web_module,
            "auth_executor",
            executor,
        ),
    ):
        app = web_module.create_app(
            portal_counter_service=None
        )
    app.config["TESTING"] = True
    return (
        app.test_client(),
        web_module.auth_manager,
        executor,
        temp_dir,
    )


def open_session(client, manager):
    response = client.get(
        (
            f"/?site={SITE_ID}&clientMac={CLIENT_MAC}"
            f"&clientIp={CLIENT_IP}"
        ),
        environ_base={"REMOTE_ADDR": CLIENT_IP},
    )
    assert response.status_code == 200
    session = manager.get_by_client(SITE_ID, CLIENT_MAC)
    assert session is not None
    return session


def finish_retryable(manager, session, reason="CLIENT_NOT_FOUND"):
    assert manager.finish_run(
        session,
        run_number=session.current_run_number,
        run_token=session.current_run_token,
        final_state=AuthStatus.FAILED,
        final_reason=reason,
        retryable=True,
        error="temporary failure",
    )
    assert manager.mark_worker_finished(
        session,
        run_number=session.current_run_number,
        run_token=session.current_run_token,
    )


def post_retry(client, session_id, request_id=None, ip=CLIENT_IP):
    return client.post(
        f"/auth/session/{session_id}/retry",
        json={
            "retry_request_id": (
                request_id or str(uuid.uuid4())
            )
        },
        environ_base={"REMOTE_ADDR": ip},
    )


def test_explicit_rejection_with_inactive_client_can_retry_same_session():
    provider = ExplicitRejectionInactiveProvider()
    client, manager, executor, temp_dir = create_client(
        controller=provider
    )
    try:
        session = open_session(client, manager)
        worker, submitted_session_id = executor.submissions[0]

        with fast_worker():
            worker(submitted_session_id)

        assert provider.authorize_calls == 3
        assert provider.get_client_calls == 5
        assert provider.unauthorize_calls == 0
        assert session.status == AuthStatus.FAILED
        assert session.final_reason == "AUTHORIZATION_REJECTED"
        assert session.retryable is True

        status_response = client.get(
            f"/auth/session/{session.session_id}",
            environ_base={"REMOTE_ADDR": CLIENT_IP},
        )
        status_payload = status_response.get_json()

        assert status_response.status_code == 200
        assert status_payload["session_id"] == session.session_id
        assert status_payload["state"] == "FAILED"
        assert status_payload["final_reason"] == (
            "AUTHORIZATION_REJECTED"
        )
        assert status_payload["retryable"] is True

        retry_response = post_retry(client, session.session_id)
        retry_payload = retry_response.get_json()

        assert retry_response.status_code == 202
        assert retry_payload["session_id"] == session.session_id
        assert retry_payload["state"] == "WAITING"
        assert retry_payload["current_run_number"] == 2
        assert len(session.runs) == 2
        assert len(executor.submissions) == 2
    finally:
        temp_dir.cleanup()


def test_first_run_has_token_number_and_original_expiry():
    manager = AuthSessionManager()
    session, created = manager.create_or_get(
        SITE_ID,
        CLIENT_MAC,
        CLIENT_IP,
    )

    assert created is True
    assert session.current_run_number == 1
    assert uuid.UUID(session.current_run_token)
    assert len(session.runs) == 1
    assert session.runs[0].retry_request_id is None
    assert session.expires_at > session.created_at


def test_retry_reuses_session_preserves_history_and_resets_attempt():
    client, manager, executor, temp_dir = create_client()
    try:
        session = open_session(client, manager)
        original_session_id = session.session_id
        original_token = session.current_run_token
        original_expiry = session.expires_at
        manager.set_attempt(session, 3)
        finish_retryable(manager, session)
        request_id = str(uuid.uuid4())

        response = post_retry(
            client,
            session.session_id,
            request_id,
        )
        payload = response.get_json()

        assert response.status_code == 202
        assert payload["session_id"] == original_session_id
        assert payload["state"] == "WAITING"
        assert payload["retryable"] is False
        assert payload["current_run_number"] == 2
        assert session.current_run_token != original_token
        assert session.expires_at == original_expiry
        assert session.attempt == 0
        assert len(session.runs) == 2
        assert session.runs[0].final_reason == "CLIENT_NOT_FOUND"
        assert session.runs[0].auth_attempt_count == 3
        assert session.runs[1].retry_request_id == request_id
        assert len(executor.submissions) == 2
    finally:
        temp_dir.cleanup()


@pytest.mark.parametrize(
    "status",
    [
        AuthStatus.WAITING,
        AuthStatus.AUTHORIZING,
        AuthStatus.VERIFYING,
        AuthStatus.RESETTING,
    ],
)
def test_retry_during_active_run_is_idempotent(status):
    client, manager, executor, temp_dir = create_client()
    try:
        session = open_session(client, manager)
        manager.update_status(session, status)
        response = post_retry(client, session.session_id)

        assert response.status_code == 200
        assert response.get_json()["current_run_number"] == 1
        assert len(session.runs) == 1
        assert len(executor.submissions) == 1
    finally:
        temp_dir.cleanup()


def test_duplicate_request_id_is_idempotent_after_run_finishes():
    client, manager, executor, temp_dir = create_client()
    try:
        session = open_session(client, manager)
        finish_retryable(manager, session)
        request_id = str(uuid.uuid4())
        first = post_retry(client, session.session_id, request_id)
        assert first.status_code == 202

        finish_retryable(
            manager,
            session,
            reason="OMADA_REQUEST_TIMEOUT",
        )
        duplicate = post_retry(
            client,
            session.session_id,
            request_id,
        )
        payload = duplicate.get_json()

        assert duplicate.status_code == 200
        assert payload["duplicate"] is True
        assert payload["request_run_number"] == 2
        assert payload["current_run_number"] == 2
        assert len(session.runs) == 2
        assert len(executor.submissions) == 2
    finally:
        temp_dir.cleanup()


def test_request_id_seen_during_active_run_stays_idempotent():
    client, manager, executor, temp_dir = create_client()
    try:
        session = open_session(client, manager)
        request_id = str(uuid.uuid4())

        active = post_retry(
            client,
            session.session_id,
            request_id,
        )

        assert active.status_code == 200
        assert active.get_json()["duplicate"] is False
        assert session.retry_request_runs[request_id] == 1

        finish_retryable(manager, session)
        duplicate = post_retry(
            client,
            session.session_id,
            request_id,
        )

        assert duplicate.status_code == 200
        assert duplicate.get_json()["duplicate"] is True
        assert duplicate.get_json()["request_run_number"] == 1
        assert session.current_run_number == 1
        assert len(session.runs) == 1
        assert len(executor.submissions) == 1
    finally:
        temp_dir.cleanup()


def test_two_parallel_retries_create_one_run():
    manager = AuthSessionManager()
    session, _ = manager.create_or_get(
        SITE_ID,
        CLIENT_MAC,
        CLIENT_IP,
    )
    finish_retryable(manager, session)
    request_ids = [str(uuid.uuid4()), str(uuid.uuid4())]

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda request_id: manager.prepare_retry(
                session.session_id,
                request_id,
            ),
            request_ids,
        ))

    assert sorted(
        result.outcome.value for result in results
    ) == sorted([
        RetryOutcome.CREATED.value,
        RetryOutcome.ACTIVE.value,
    ])
    assert session.current_run_number == 2
    assert len(session.runs) == 2


def test_invalid_request_id_and_foreign_ip_do_not_change_state():
    client, manager, executor, temp_dir = create_client()
    try:
        session = open_session(client, manager)
        finish_retryable(manager, session)

        invalid = client.post(
            f"/auth/session/{session.session_id}/retry",
            json={"retry_request_id": "not-a-uuid"},
            environ_base={"REMOTE_ADDR": CLIENT_IP},
        )
        foreign = post_retry(
            client,
            session.session_id,
            ip="192.168.1.99",
        )

        assert invalid.status_code == 400
        assert foreign.status_code == 403
        assert session.current_run_number == 1
        assert len(session.runs) == 1
        assert len(executor.submissions) == 1
    finally:
        temp_dir.cleanup()


def test_expired_final_and_missing_sessions_are_rejected():
    client, manager, executor, temp_dir = create_client()
    try:
        session = open_session(client, manager)
        finish_retryable(manager, session)
        original_expiry = session.expires_at
        session._created_monotonic -= 61

        expired = post_retry(client, session.session_id)
        missing = post_retry(client, str(uuid.uuid4()))

        assert expired.status_code == 410
        assert expired.get_json()["state"] == "EXPIRED"
        assert session.expires_at == original_expiry
        assert missing.status_code == 404
        assert len(executor.submissions) == 1
    finally:
        temp_dir.cleanup()


def test_nonretryable_failure_returns_conflict():
    client, manager, executor, temp_dir = create_client()
    try:
        session = open_session(client, manager)
        assert manager.finish_run(
            session,
            run_number=1,
            run_token=session.current_run_token,
            final_state=AuthStatus.FAILED,
            final_reason="AUTH_TOKEN_ERROR",
            retryable=False,
            error="invalid credentials",
        )
        manager.mark_worker_finished(
            session,
            run_number=1,
            run_token=session.current_run_token,
        )

        response = post_retry(client, session.session_id)

        assert response.status_code == 409
        assert session.current_run_number == 1
        assert len(executor.submissions) == 1
    finally:
        temp_dir.cleanup()


def test_retry_worker_submit_failure_is_503_and_retryable():
    executor = CapturingExecutor(fail_after=1)
    client, manager, _executor, temp_dir = create_client(
        executor=executor
    )
    try:
        session = open_session(client, manager)
        finish_retryable(manager, session)

        response = post_retry(client, session.session_id)
        payload = response.get_json()

        assert response.status_code == 503
        assert payload["state"] == "FAILED"
        assert payload["retryable"] is True
        assert payload["final_reason"] == "WORKER_START_FAILED"
        assert session.runs[1].worker_finished is True
        assert len(executor.submissions) == 1
    finally:
        temp_dir.cleanup()


def test_stale_worker_is_ignored_and_emits_event():
    with tempfile.TemporaryDirectory() as temp_dir:
        log_path = Path(temp_dir) / "auth.log"
        telemetry = AuthorizationTelemetry(
            enabled=True,
            log_path=str(log_path),
            level="DEBUG",
        )
        import app.auth_telemetry.service as service_module
        service_module._service = telemetry
        try:
            manager = AuthSessionManager()
            session, _ = manager.create_or_get(
                SITE_ID,
                CLIENT_MAC,
                CLIENT_IP,
            )
            old_token = session.current_run_token
            finish_retryable(manager, session)
            preparation = manager.prepare_retry(
                session.session_id,
                str(uuid.uuid4()),
            )
            assert preparation.outcome == RetryOutcome.CREATED

            AuthWorker(
                AuthorizedProvider(),
                manager,
            ).process(
                session.session_id,
                1,
                old_token,
            )

            assert session.current_run_number == 2
            assert session.status == AuthStatus.WAITING
            records = [
                json.loads(line)
                for line in log_path.read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            ignored = [
                record for record in records
                if record["event"]
                == events.WORKER_RESULT_IGNORED
            ]
            assert len(ignored) == 1
            assert ignored[0]["reason"] == "STALE_RUN_TOKEN"
            assert ignored[0]["run_number"] == 1
        finally:
            AuthorizationTelemetry(enabled=False, log_path="")


def test_manual_retry_success_has_run_telemetry_without_run_token():
    with tempfile.TemporaryDirectory() as temp_dir:
        log_path = Path(temp_dir) / "auth.log"
        telemetry = AuthorizationTelemetry(
            enabled=True,
            log_path=str(log_path),
            level="DEBUG",
        )
        import app.auth_telemetry.service as service_module
        service_module._service = telemetry
        try:
            manager = AuthSessionManager()
            session, _ = manager.create_or_get(
                SITE_ID,
                CLIENT_MAC,
                CLIENT_IP,
            )
            finish_retryable(manager, session)
            request_id = str(uuid.uuid4())
            preparation = manager.prepare_retry(
                session.session_id,
                request_id,
            )
            assert manager.claim_worker(
                session,
                preparation.run_number,
                preparation.run_token,
            )
            with (
                patch(
                    "app.auth.worker.MIN_INITIAL_DELAY_SECONDS",
                    0,
                ),
                patch(
                    "app.auth.worker.AUTH_FALLBACK_DELAY_SECONDS",
                    0,
                ),
                patch(
                    "app.auth.worker.CLIENT_READY_POLL_SECONDS",
                    0,
                ),
                patch(
                    "app.auth.worker.VERIFY_DELAY_SECONDS",
                    0,
                ),
            ):
                AuthWorker(
                    AuthorizedProvider(),
                    manager,
                ).process(
                    session.session_id,
                    preparation.run_number,
                    preparation.run_token,
                )

            records = [
                json.loads(line)
                for line in log_path.read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            event_names = {
                record["event"] for record in records
            }
            assert events.RETRY_STARTED in event_names
            assert events.RETRY_SUCCEEDED in event_names
            assert events.RUN_FINISHED in event_names
            manual_run_events = [
                record for record in records
                if record["event"] in {
                    events.RETRY_STARTED,
                    events.RETRY_SUCCEEDED,
                    events.RUN_FINISHED,
                }
            ]
            assert all(
                record["run_number"] == 2
                for record in manual_run_events
            )
            assert all(
                "run_token" not in record
                for record in records
            )
            assert any(
                record.get("retry_request_id") == request_id
                for record in manual_run_events
            )
            assert session.status == AuthStatus.AUTHORIZED
        finally:
            AuthorizationTelemetry(enabled=False, log_path="")


def test_first_run_can_resolve_missing_mac_by_saved_ip():
    manager = AuthSessionManager()
    session, _ = manager.create_or_get(
        SITE_ID,
        None,
        CLIENT_IP,
    )
    assert manager.claim_worker(
        session,
        1,
        session.current_run_token,
    )
    with (
        patch("app.auth.worker.MIN_INITIAL_DELAY_SECONDS", 0),
        patch("app.auth.worker.AUTH_FALLBACK_DELAY_SECONDS", 0),
        patch("app.auth.worker.CLIENT_READY_POLL_SECONDS", 0),
        patch("app.auth.worker.VERIFY_DELAY_SECONDS", 0),
    ):
        AuthWorker(
            IpResolvingProvider(),
            manager,
        ).process(
            session.session_id,
            1,
            session.current_run_token,
        )

    assert session.client_mac == CLIENT_MAC
    assert session.status == AuthStatus.AUTHORIZED
    same_session, created = manager.create_or_get(
        SITE_ID,
        None,
        CLIENT_IP,
    )
    assert created is False
    assert same_session is session


def test_client_not_found_is_retryable_without_auth_or_cleanup():
    manager = AuthSessionManager()
    provider = MissingClientProvider()
    session, _ = manager.create_or_get(
        SITE_ID,
        None,
        CLIENT_IP,
    )
    assert manager.claim_worker(
        session,
        1,
        session.current_run_token,
    )
    with (
        patch("app.auth.worker.MIN_INITIAL_DELAY_SECONDS", 0),
        patch("app.auth.worker.AUTH_FALLBACK_DELAY_SECONDS", 0),
        patch("app.auth.worker.CLIENT_READY_POLL_SECONDS", 0),
        patch("app.auth.worker.VERIFY_DELAY_SECONDS", 0),
    ):
        AuthWorker(
            provider,
            manager,
        ).process(
            session.session_id,
            1,
            session.current_run_token,
        )

    assert session.status == AuthStatus.FAILED
    assert session.retryable is True
    assert session.final_reason == "CLIENT_NOT_FOUND"
    assert session.runs[0].authorization_may_have_changed is False
    assert provider.authorize_calls == 0
    assert provider.unauthorize_calls == 0


def test_known_mac_client_not_found_skips_auth_and_cleanup():
    manager = AuthSessionManager()
    provider = KnownMacMissingClientProvider()
    session, _ = manager.create_or_get(
        SITE_ID,
        CLIENT_MAC,
        CLIENT_IP,
    )
    assert manager.claim_worker(
        session,
        1,
        session.current_run_token,
    )

    with fast_worker():
        AuthWorker(provider, manager).process(
            session.session_id,
            1,
            session.current_run_token,
        )

    assert session.status == AuthStatus.FAILED
    assert session.retryable is True
    assert session.final_reason == "CLIENT_NOT_FOUND"
    assert session.runs[0].authorization_may_have_changed is False
    assert provider.authorize_calls == 0
    assert provider.unauthorize_calls == 0


def test_successful_cleanup_finishes_without_observable_reset():
    manager = AuthSessionManager()
    provider = BlockingCleanupProvider()
    session, _ = manager.create_or_get(
        SITE_ID,
        CLIENT_MAC,
        CLIENT_IP,
    )
    assert manager.claim_worker(
        session,
        1,
        session.current_run_token,
    )
    observed_updates = []
    original_update_status = manager.update_status

    def track_update(*args, **kwargs):
        if len(args) >= 2:
            observed_updates.append(args[1])
        else:
            observed_updates.append(kwargs["new_status"])
        return original_update_status(*args, **kwargs)

    manager.update_status = track_update
    worker_thread = threading.Thread(
        target=AuthWorker(provider, manager).process,
        args=(
            session.session_id,
            1,
            session.current_run_token,
        ),
    )

    with fast_worker():
        worker_thread.start()
        assert provider.cleanup_started.wait(timeout=5)
        assert manager.snapshot(session)["state"] == "RESETTING"
        provider.release_cleanup.set()
        worker_thread.join(timeout=5)

    assert not worker_thread.is_alive()
    assert AuthStatus.RESETTING in observed_updates
    assert AuthStatus.RESET not in observed_updates
    snapshot = manager.snapshot(session)
    assert snapshot["state"] == "FAILED"
    assert snapshot["retryable"] is True


def test_expiry_during_verification_ignores_late_worker_result():
    manager = AuthSessionManager()
    provider = BlockingVerificationProvider()
    telemetry = CapturingTelemetry()
    session, _ = manager.create_or_get(
        SITE_ID,
        CLIENT_MAC,
        CLIENT_IP,
    )
    assert manager.claim_worker(
        session,
        1,
        session.current_run_token,
    )
    worker_thread = threading.Thread(
        target=AuthWorker(provider, manager).process,
        args=(
            session.session_id,
            1,
            session.current_run_token,
        ),
    )

    with (
        fast_worker(),
        patch(
            "app.auth.worker.get_auth_telemetry",
            return_value=telemetry,
        ),
    ):
        worker_thread.start()
        assert provider.verification_started.wait(timeout=5)
        assert session.status == AuthStatus.VERIFYING
        session._created_monotonic -= 61
        assert manager.expire_if_needed(session) is True
        assert manager.current_run_matches(
            session,
            1,
            session.current_run_token,
        ) is False
        provider.release_verification.set()
        worker_thread.join(timeout=5)

    assert not worker_thread.is_alive()
    assert session.status == AuthStatus.EXPIRED
    assert session.final_reason == "SESSION_EXPIRED"
    assert any(
        record["event"] == events.WORKER_RESULT_IGNORED
        and record["reason"] == "STALE_RUN_TOKEN"
        for record in telemetry.records
    )


def test_expiry_during_resetting_ignores_late_cleanup_result():
    manager = AuthSessionManager()
    provider = BlockingCleanupProvider()
    telemetry = CapturingTelemetry()
    session, _ = manager.create_or_get(
        SITE_ID,
        CLIENT_MAC,
        CLIENT_IP,
    )
    assert manager.claim_worker(
        session,
        1,
        session.current_run_token,
    )
    worker_thread = threading.Thread(
        target=AuthWorker(provider, manager).process,
        args=(
            session.session_id,
            1,
            session.current_run_token,
        ),
    )

    with (
        fast_worker(),
        patch(
            "app.auth.worker.get_auth_telemetry",
            return_value=telemetry,
        ),
    ):
        worker_thread.start()
        assert provider.cleanup_started.wait(timeout=5)
        assert session.status == AuthStatus.RESETTING
        session._created_monotonic -= 61
        assert manager.expire_if_needed(session) is True
        provider.release_cleanup.set()
        worker_thread.join(timeout=5)

    assert not worker_thread.is_alive()
    assert session.status == AuthStatus.EXPIRED
    assert session.final_reason == "SESSION_EXPIRED"
    assert any(
        record["event"] == events.WORKER_RESULT_IGNORED
        and record["reason"] == "STALE_RUN_TOKEN"
        for record in telemetry.records
    )


@pytest.mark.parametrize(
    ("error", "http_status", "message", "expected"),
    [
        (
            "CLIENT_NOT_FOUND",
            404,
            "not found",
            ("CLIENT_NOT_FOUND", True),
        ),
        (
            "OMADA_UNAVAILABLE",
            0,
            "unavailable",
            ("OMADA_UNAVAILABLE", True),
        ),
        (
            "HTTP_ERROR",
            0,
            "request timed out",
            ("OMADA_REQUEST_TIMEOUT", True),
        ),
        (
            "HTTP_ERROR",
            0,
            "connection refused",
            ("OMADA_CONNECTION_ERROR", True),
        ),
        (
            "HTTP_ERROR",
            503,
            "service unavailable",
            ("OMADA_HTTP_5XX", True),
        ),
        (
            "TOKEN_FAILED",
            401,
            "invalid token",
            ("AUTH_TOKEN_ERROR", False),
        ),
        (
            "AUTH_FAILED",
            400,
            "rejected",
            ("AUTHORIZATION_REJECTED", False),
        ),
        (
            "SOMETHING_UNKNOWN",
            0,
            "unknown",
            ("CONFIGURATION_ERROR", False),
        ),
    ],
)
def test_failure_classification_is_fail_safe(
    error,
    http_status,
    message,
    expected,
):
    result = Result.fail(
        error=error,
        message=message,
        data={
            "http_status": http_status,
            "error_code": -1,
        },
    )

    assert AuthWorker._classify_failure(result) == expected


@pytest.mark.parametrize(
    ("exception_type", "expected"),
    [
        ("Timeout", ("OMADA_REQUEST_TIMEOUT", True)),
        ("ConnectTimeout", ("OMADA_REQUEST_TIMEOUT", True)),
        ("ReadTimeout", ("OMADA_REQUEST_TIMEOUT", True)),
        ("ConnectionError", ("OMADA_CONNECTION_ERROR", True)),
        ("RequestException", ("OMADA_UNAVAILABLE", True)),
        ("ValueError", ("WORKER_EXCEPTION", False)),
    ],
)
def test_network_exception_classification_is_retryable(
    exception_type,
    expected,
):
    result = Result.fail(
        error="GET_CLIENT_EXCEPTION",
        message="provider raised",
        data={"http_status": 0, "error_code": 0},
    )

    assert AuthWorker._classify_failure(
        result,
        exception_type,
    ) == expected
