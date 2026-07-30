import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from app.auth_telemetry import get_auth_telemetry
from app.auth_telemetry import events
from app.models import Result
from app.visitor_registry.snapshot_collector import (
    DISABLED_VISITOR_SNAPSHOT_COLLECTOR,
)
from app.visitor_registry.snapshot_models import (
    AuthorizedClientAuthContext,
    AuthorizedClientSnapshotRequest,
)
from app.visitor_registry.protocols import VisitorSnapshotSubmitter
from .manager import AuthSessionManager
from .session import AuthSession, AuthStatus


MIN_INITIAL_DELAY_SECONDS = 5.0
AUTH_FALLBACK_DELAY_SECONDS = 13.0
CLIENT_READY_POLL_SECONDS = 3.0
MAX_AUTH_ATTEMPTS = 3
VERIFY_DELAY_SECONDS = 3.0
SLEEP_CHECK_INTERVAL_SECONDS = 0.25

logger = logging.getLogger("captiveportal.auth")

ATTEMPT_PROGRESS = {
    1: {"authorizing": 50, "verifying": 65, "verified": 72},
    2: {"authorizing": 72, "verifying": 80, "verified": 86},
    3: {"authorizing": 86, "verifying": 92, "verified": 92},
}


@dataclass
class _RunMetrics:
    started: float
    worker_id: str
    readiness_checks: int = 0
    auth_attempts: int = 0
    ready_after_ms: Optional[float] = None
    last_active: Optional[bool] = None
    last_auth_status: Optional[int] = None
    last_omada_error_code: Optional[Any] = None
    last_failure_reason: Optional[str] = None
    last_failure_retryable: bool = False
    final_reason: str = "INTERNAL_ERROR"


@dataclass
class _WorkerRun:
    session_id: str
    run_number: int
    run_token: str
    stale_reported: bool = False


class _StaleRun(RuntimeError):
    pass


def _session_fields(session: AuthSession) -> dict[str, Any]:
    return {
        "site_id": session.site_id,
        "client_mac": session.client_mac,
        "client_ip": session.client_ip,
        "state": session.status.value,
        "run_number": session.current_run_number,
        "auth_attempt": session.attempt,
    }


def log_auth_event(
    event: str,
    session: AuthSession,
    level: int | str = logging.INFO,
    **fields: Any,
) -> bool:
    """Compatibility adapter: all auth events use the dedicated journal."""
    level_name = (
        logging.getLevelName(level).lower()
        if isinstance(level, int)
        else str(level).lower()
    )
    payload = _session_fields(session)
    payload.update(fields)
    return get_auth_telemetry().safe_emit(
        event,
        session.session_id,
        level_name,
        **payload,
    )


class AuthWorker:
    def __init__(
        self,
        provider: Any,
        session_manager: AuthSessionManager,
        snapshot_collector: Optional[
            VisitorSnapshotSubmitter
        ] = None,
    ):
        self._provider = provider
        self._session_manager = session_manager
        self._snapshot_collector = (
            snapshot_collector
            if snapshot_collector is not None
            else DISABLED_VISITOR_SNAPSHOT_COLLECTOR
        )

    def process(
        self,
        session_id: str,
        run_number: Optional[int] = None,
        run_token: Optional[str] = None,
    ) -> None:
        session = self._session_manager.get(session_id)
        if session is None:
            return

        run_number = (
            session.current_run_number
            if run_number is None
            else run_number
        )
        run_token = (
            session.current_run_token
            if run_token is None
            else run_token
        )
        if run_token is None:
            return
        run = _WorkerRun(
            session_id=session_id,
            run_number=run_number,
            run_token=run_token,
        )
        if not self._session_manager.current_run_matches(
            session_id,
            run.run_number,
            run.run_token,
        ):
            try:
                self._raise_stale(session, run, "worker_start")
            except _StaleRun:
                return

        metrics = _RunMetrics(
            started=time.monotonic(),
            worker_id=threading.current_thread().name,
        )
        try:
            self._require_update(
                self._session_manager.set_worker_id(
                    session,
                    metrics.worker_id,
                    run_number=run.run_number,
                    run_token=run.run_token,
                ),
                session,
                run,
                "worker_id",
            )
        except _StaleRun:
            return
        log_auth_event(
            events.WORKER_STARTED,
            session,
            run_number=run.run_number,
            auth_attempt=0,
            worker_id=metrics.worker_id,
            initial_delay_ms=self._milliseconds(
                MIN_INITIAL_DELAY_SECONDS
            ),
            readiness_interval_ms=self._milliseconds(
                CLIENT_READY_POLL_SECONDS
            ),
            fallback_after_ms=self._milliseconds(
                AUTH_FALLBACK_DELAY_SECONDS
            ),
            max_auth_attempts=MAX_AUTH_ATTEMPTS,
            verification_delay_ms=self._milliseconds(
                VERIFY_DELAY_SECONDS
            ),
        )
        if run.run_number >= 2:
            run_state = self._session_manager.run_snapshot(
                session,
                run.run_number,
            ) or {}
            previous_run = (
                session.runs[-2]
                if len(session.runs) >= 2
                else None
            )
            get_auth_telemetry().safe_emit(
                events.RETRY_STARTED,
                session.session_id,
                "info",
                site_id=session.site_id,
                client_ip=session.client_ip,
                client_mac=session.client_mac,
                run_number=run.run_number,
                auth_attempt=0,
                retry_request_id=run_state.get(
                    "retry_request_id"
                ),
                previous_final_state=(
                    previous_run.final_state
                    if previous_run is not None
                    else None
                ),
                previous_final_reason=(
                    previous_run.final_reason
                    if previous_run is not None
                    else None
                ),
            )

        try:
            self._require_update(
                self._session_manager.update_status(
                    session,
                    AuthStatus.WAITING,
                    error="",
                    progress=0,
                    run_number=run.run_number,
                    run_token=run.run_token,
                ),
                session,
                run,
                "waiting",
            )

            sleep_completed = self._sleep_with_ttl_check(
                session_id=session.session_id,
                seconds=MIN_INITIAL_DELAY_SECONDS,
                start_progress=0,
                end_progress=10,
                run=run,
            )
            if not sleep_completed:
                self._ensure_current(session, run, "initial_delay")
                metrics.final_reason = "SESSION_EXPIRED"
                self._expire_session(session, run)
                return

            log_auth_event(
                events.INITIAL_DELAY_COMPLETED,
                session,
                level="debug",
                run_number=run.run_number,
                auth_attempt=0,
                initial_delay_ms=self._milliseconds(
                    MIN_INITIAL_DELAY_SECONDS
                ),
                elapsed_ms=self._elapsed_ms(metrics.started),
            )

            ready_state, ready_result = self._wait_for_client_ready(
                session,
                metrics,
                run,
            )
            if ready_state == "expired":
                metrics.final_reason = "SESSION_EXPIRED"
                self._expire_session(session, run)
                return
            if ready_state == "authorized":
                if ready_result is None:
                    raise RuntimeError(
                        "Authorized client result is missing."
                    )
                metrics.final_reason = "ALREADY_AUTHORIZED"
                self._mark_authorized(
                    session,
                    ready_result,
                    run,
                    final_reason=metrics.final_reason,
                )
                return
            if ready_state == "not_found":
                metrics.final_reason = "CLIENT_NOT_FOUND"
                self._finish_failed(
                    session,
                    run,
                    final_reason="CLIENT_NOT_FOUND",
                    retryable=True,
                    error="Client was not found in Omada.",
                )
                return
            if ready_state not in {"ready", "fallback"}:
                raise RuntimeError(
                    f"Unexpected client readiness state: {ready_state}"
                )

            for attempt in range(1, MAX_AUTH_ATTEMPTS + 1):
                if self._session_manager.expire_if_needed(
                    session,
                    run_number=run.run_number,
                    run_token=run.run_token,
                ):
                    self._ensure_current(session, run, "attempt_expiry")
                    metrics.final_reason = "SESSION_EXPIRED"
                    return

                metrics.auth_attempts = attempt
                progress = ATTEMPT_PROGRESS[attempt]
                self._require_update(
                    self._session_manager.begin_attempt(
                        session,
                        attempt,
                        progress=progress["authorizing"],
                        run_number=run.run_number,
                        run_token=run.run_token,
                    ),
                    session,
                    run,
                    "authorizing",
                )
                self._require_update(
                    self._session_manager
                    .mark_authorization_may_have_changed(
                        session,
                        run_number=run.run_number,
                        run_token=run.run_token,
                    ),
                    session,
                    run,
                    "authorization_flag",
                )
                log_auth_event(
                    events.AUTHORIZATION_REQUEST,
                    session,
                    run_number=run.run_number,
                    auth_attempt=attempt,
                    elapsed_ms=self._elapsed_ms(metrics.started),
                )

                auth_result, auth_ms, auth_exception = (
                    self._authorize_client(session)
                )
                self._ensure_current(
                    session,
                    run,
                    "authorization_response",
                )
                failure_reason, failure_retryable = (
                    self._classify_failure(
                        auth_result,
                        auth_exception,
                    )
                )
                if failure_reason is not None:
                    metrics.last_failure_reason = failure_reason
                    metrics.last_failure_retryable = failure_retryable
                self._emit_authorization_response(
                    session,
                    auth_result,
                    attempt,
                    auth_ms,
                    auth_exception,
                    metrics,
                )

                self._require_update(
                    self._session_manager.update_status(
                        session,
                        AuthStatus.VERIFYING,
                        progress=progress["verifying"],
                        run_number=run.run_number,
                        run_token=run.run_token,
                    ),
                    session,
                    run,
                    "verifying",
                )
                log_auth_event(
                    events.VERIFICATION_STARTED,
                    session,
                    level="debug",
                    run_number=run.run_number,
                    auth_attempt=attempt,
                    verification_delay_ms=self._milliseconds(
                        VERIFY_DELAY_SECONDS
                    ),
                    verification_phase="attempt",
                )

                sleep_completed = self._sleep_with_ttl_check(
                    session_id=session.session_id,
                    seconds=VERIFY_DELAY_SECONDS,
                    start_progress=progress["verifying"],
                    end_progress=progress["verified"],
                    run=run,
                )
                if not sleep_completed:
                    self._ensure_current(session, run, "verification_delay")
                    metrics.final_reason = "SESSION_EXPIRED"
                    self._expire_session(session, run)
                    return

                verify_result, response_ms, exception_type = (
                    self._get_client(
                        session,
                        operation="verify",
                        operation_number=attempt,
                        run=run,
                    )
                )
                self._ensure_current(
                    session,
                    run,
                    "verification_result",
                )
                auth_status = self._extract_auth_status(verify_result)
                active = self._extract_active(verify_result)
                self._capture_last(metrics, verify_result)
                verify_reason, verify_retryable = self._classify_failure(
                    verify_result,
                    exception_type,
                )
                if verify_reason is not None:
                    metrics.last_failure_reason = verify_reason
                    metrics.last_failure_retryable = verify_retryable
                self._require_update(
                    self._session_manager.set_auth_status(
                        session,
                        auth_status,
                        run_number=run.run_number,
                        run_token=run.run_token,
                    ),
                    session,
                    run,
                    "verification_auth_status",
                )
                verified = auth_status == 2
                self._emit_verification_result(
                    session=session,
                    result=verify_result,
                    attempt=attempt,
                    phase="attempt",
                    verified=verified,
                    response_time_ms=response_ms,
                    exception_type=exception_type,
                    metrics=metrics,
                )
                if verified:
                    metrics.final_reason = "AUTHORIZED_AFTER_ATTEMPT"
                    self._mark_authorized(
                        session,
                        verify_result,
                        run,
                        final_reason=metrics.final_reason,
                    )
                    return

                if attempt < MAX_AUTH_ATTEMPTS:
                    log_auth_event(
                        events.RETRY_SCHEDULED,
                        session,
                        level="warning",
                        run_number=run.run_number,
                        completed_attempt=attempt,
                        next_attempt=attempt + 1,
                        reason=(
                            verify_result.error
                            or "VERIFY_NOT_AUTHORIZED"
                        ),
                        elapsed_ms=self._elapsed_ms(metrics.started),
                    )

            if self._session_manager.expire_if_needed(
                session,
                run_number=run.run_number,
                run_token=run.run_token,
            ):
                self._ensure_current(session, run, "final_expiry")
                metrics.final_reason = "SESSION_EXPIRED"
                return

            self._require_update(
                self._session_manager.update_status(
                    session,
                    AuthStatus.VERIFYING,
                    progress=95,
                    run_number=run.run_number,
                    run_token=run.run_token,
                ),
                session,
                run,
                "final_verifying",
            )
            log_auth_event(
                events.VERIFICATION_STARTED,
                session,
                level="debug",
                run_number=run.run_number,
                auth_attempt=metrics.auth_attempts,
                verification_delay_ms=0,
                verification_phase="final",
            )
            final_result, final_ms, final_exception = self._get_client(
                session,
                operation="final_verify",
                operation_number=metrics.auth_attempts,
                run=run,
            )
            self._ensure_current(session, run, "final_verification_result")
            final_auth_status = self._extract_auth_status(final_result)
            self._capture_last(metrics, final_result)
            final_failure_reason, final_failure_retryable = (
                self._classify_failure(
                    final_result,
                    final_exception,
                )
            )
            if final_failure_reason is not None:
                metrics.last_failure_reason = final_failure_reason
                metrics.last_failure_retryable = (
                    final_failure_retryable
                )
            self._require_update(
                self._session_manager.set_auth_status(
                    session,
                    final_auth_status,
                    run_number=run.run_number,
                    run_token=run.run_token,
                ),
                session,
                run,
                "final_auth_status",
            )
            final_verified = final_auth_status == 2
            self._emit_verification_result(
                session=session,
                result=final_result,
                attempt=metrics.auth_attempts,
                phase="final",
                verified=final_verified,
                response_time_ms=final_ms,
                exception_type=final_exception,
                metrics=metrics,
            )
            if final_verified:
                metrics.final_reason = "AUTHORIZED_FINAL_VERIFY"
                self._mark_authorized(
                    session,
                    final_result,
                    run,
                    final_reason=metrics.final_reason,
                )
                return

            success_reason = (
                metrics.last_failure_reason
                or "AUTH_EXHAUSTED_RESET_SUCCEEDED"
            )
            success_retryable = (
                metrics.last_failure_retryable
                if metrics.last_failure_reason is not None
                else True
            )
            if (
                success_reason == "AUTHORIZATION_REJECTED"
                and final_result.success
                and metrics.last_active is False
                and final_auth_status != 2
            ):
                self._finish_failed(
                    session,
                    run,
                    final_reason=success_reason,
                    retryable=True,
                    error=(
                        "Authorization was rejected and the client "
                        "remains inactive. A retry is available."
                    ),
                )
                metrics.final_reason = success_reason
                return
            metrics.final_reason = self._cleanup_and_finish(
                session,
                run,
                success_reason=success_reason,
                success_retryable=success_retryable,
            )

        except _StaleRun:
            return
        except Exception as exc:
            try:
                self._ensure_current(session, run, "worker_exception")
            except _StaleRun:
                return
            self._session_manager.fail(
                session,
                error=str(exc),
                final_reason="WORKER_EXCEPTION",
                retryable=False,
                run_number=run.run_number,
                run_token=run.run_token,
            )
            metrics.final_reason = "WORKER_EXCEPTION"
            logger.exception(
                "Authorization worker failed session_id=%s run_number=%s",
                session.session_id,
                run.run_number,
            )
            log_auth_event(
                events.WORKER_EXCEPTION,
                session,
                level="error",
                run_number=run.run_number,
                auth_attempt=metrics.auth_attempts,
                exception_type=type(exc).__name__,
                error=str(exc),
                elapsed_ms=self._elapsed_ms(metrics.started),
                worker_id=metrics.worker_id,
            )
        finally:
            self._session_manager.mark_worker_finished(
                session,
                run_number=run.run_number,
                run_token=run.run_token,
            )
            self._emit_finished(session, metrics, run)

    def _cleanup_and_finish(
        self,
        session: AuthSession,
        run: _WorkerRun,
        *,
        success_reason: str,
        success_retryable: bool,
    ) -> str:
        self._require_update(
            self._session_manager.update_status(
                session,
                AuthStatus.RESETTING,
                progress=95,
                run_number=run.run_number,
                run_token=run.run_token,
            ),
            session,
            run,
            "resetting",
        )
        reset_started = time.monotonic()
        try:
            reset_result: Result = self._provider.unauthorize(
                site_id=session.site_id,
                client_mac=session.client_mac,
            )
            reset_exception = None
        except Exception as exc:
            reset_exception = type(exc).__name__
            reset_result = Result.fail(
                error="UNAUTH_PROVIDER_EXCEPTION",
                message=str(exc),
                data={"http_status": 0, "error_code": 0},
            )
            self._emit_omada_unavailable(
                session,
                operation="unauthorize",
                result=reset_result,
                response_time_ms=self._elapsed_ms(reset_started),
                exception_type=reset_exception,
            )

        self._ensure_current(session, run, "unauthorize_result")
        if self._is_token_error(reset_result):
            self._emit_token_error(
                session,
                "unauthorize",
                reset_result,
            )

        if reset_result.success:
            self._finish_failed(
                session,
                run,
                final_reason=success_reason,
                retryable=success_retryable,
                error=(
                    "Authorization did not complete. "
                    "A retry is available."
                ),
            )
            return success_reason

        self._finish_failed(
            session,
            run,
            final_reason="RESET_REQUEST_FAILED",
            retryable=False,
            error=(
                reset_result.message
                or "Unable to reset Portal session."
            ),
        )
        return "RESET_REQUEST_FAILED"

    def _wait_for_client_ready(
        self,
        session: AuthSession,
        metrics: _RunMetrics,
        run: _WorkerRun,
    ) -> tuple[str, Optional[Result]]:
        adaptive_wait_seconds = max(
            0.0,
            AUTH_FALLBACK_DELAY_SECONDS - MIN_INITIAL_DELAY_SECONDS,
        )
        started = time.monotonic()
        deadline = started + adaptive_wait_seconds
        last_result: Optional[Result] = None

        while True:
            if self._session_manager.expire_if_needed(
                session,
                run_number=run.run_number,
                run_token=run.run_token,
            ):
                self._ensure_current(session, run, "readiness_expiry")
                return "expired", last_result

            metrics.readiness_checks += 1
            result, response_ms, exception_type = self._get_client(
                session,
                operation="readiness",
                operation_number=metrics.readiness_checks,
                run=run,
            )
            self._ensure_current(session, run, "client_readiness")
            last_result = result
            auth_status = self._extract_auth_status(result)
            active = self._extract_active(result)
            client_found = self._client_found(result)
            self._capture_last(metrics, result)
            failure_reason, failure_retryable = self._classify_failure(
                result,
                exception_type,
            )
            if failure_reason is not None:
                metrics.last_failure_reason = failure_reason
                metrics.last_failure_retryable = failure_retryable
            self._require_update(
                self._session_manager.set_auth_status(
                    session,
                    auth_status,
                    run_number=run.run_number,
                    run_token=run.run_token,
                ),
                session,
                run,
                "readiness_auth_status",
            )

            total_waited = (
                MIN_INITIAL_DELAY_SECONDS
                + time.monotonic()
                - started
            )
            log_auth_event(
                events.CLIENT_CHECK,
                session,
                level="debug",
                run_number=run.run_number,
                auth_attempt=0,
                readiness_check=metrics.readiness_checks,
                elapsed_ms=self._elapsed_ms(metrics.started),
                client_found=client_found,
                active=active,
                auth_status=auth_status,
                omada_http_status=self._result_value(
                    result,
                    "http_status",
                ),
                omada_error_code=self._result_value(
                    result,
                    "error_code",
                ),
                response_time_ms=response_ms,
            )

            if result.success and active is True:
                self._require_update(
                    self._session_manager.set_progress(
                        session.session_id,
                        50,
                        run_number=run.run_number,
                        run_token=run.run_token,
                    ),
                    session,
                    run,
                    "client_ready_progress",
                )
                metrics.ready_after_ms = round(total_waited * 1000, 2)
                get_auth_telemetry().safe_emit(
                    events.CLIENT_READY,
                    session.session_id,
                    "info",
                    **_session_fields(session),
                    readiness_checks=metrics.readiness_checks,
                    ready_after_ms=metrics.ready_after_ms,
                    active=active,
                    auth_status=auth_status,
                )
            if auth_status == 2:
                return "authorized", result
            if result.success and active is True:
                return "ready", result

            now = time.monotonic()
            if now >= deadline:
                if client_found is False:
                    return "not_found", result
                self._require_update(
                    self._session_manager.set_progress(
                        session.session_id,
                        50,
                        run_number=run.run_number,
                        run_token=run.run_token,
                    ),
                    session,
                    run,
                    "fallback_progress",
                )
                log_auth_event(
                    events.FALLBACK_TRIGGERED,
                    session,
                    level="warning",
                    run_number=run.run_number,
                    auth_attempt=0,
                    readiness_checks=metrics.readiness_checks,
                    elapsed_ms=self._elapsed_ms(metrics.started),
                    fallback_after_ms=self._milliseconds(
                        AUTH_FALLBACK_DELAY_SECONDS
                    ),
                    last_active=active,
                    last_auth_status=auth_status,
                    last_omada_error_code=self._result_value(
                        result,
                        "error_code",
                    ),
                )
                return "fallback", result

            if adaptive_wait_seconds > 0:
                ratio = min(
                    1.0,
                    max(0.0, (time.monotonic() - started)
                        / adaptive_wait_seconds),
                )
                self._require_update(
                    self._session_manager.set_progress(
                        session.session_id,
                        round(10 + (40 * ratio)),
                        run_number=run.run_number,
                        run_token=run.run_token,
                    ),
                    session,
                    run,
                    "readiness_progress",
                )

            if not self._sleep_with_ttl_check(
                session_id=session.session_id,
                seconds=min(
                    CLIENT_READY_POLL_SECONDS,
                    max(0.0, deadline - now),
                ),
                run=run,
            ):
                self._ensure_current(session, run, "readiness_sleep")
                return "expired", last_result

    def _authorize_client(
        self,
        session: AuthSession,
    ) -> tuple[Result, float, Optional[str]]:
        started = time.monotonic()
        if not session.client_mac:
            return (
                Result.fail(
                    error="CLIENT_NOT_FOUND",
                    message="Client MAC is not available.",
                    data={"http_status": 0, "error_code": 0},
                ),
                self._elapsed_ms(started),
                None,
            )
        try:
            result: Result = self._provider.authorize(
                site_id=session.site_id,
                client_mac=session.client_mac,
            )
            return result, self._elapsed_ms(started), None
        except Exception as exc:
            result = Result.fail(
                error="AUTH_PROVIDER_EXCEPTION",
                message=str(exc),
                data={"http_status": 0, "error_code": 0},
            )
            elapsed = self._elapsed_ms(started)
            return result, elapsed, type(exc).__name__

    def _get_client(
        self,
        session: AuthSession,
        operation: str,
        operation_number: int,
        run: _WorkerRun,
    ) -> tuple[Result, float, Optional[str]]:
        started = time.monotonic()
        try:
            if not session.client_mac:
                if (
                    not session.client_ip
                    or not hasattr(self._provider, "get_client_by_ip")
                ):
                    return (
                        Result.fail(
                            error="CLIENT_NOT_FOUND",
                            message="Client MAC is not available.",
                            data={
                                "http_status": 0,
                                "error_code": 0,
                                "authStatus": None,
                                "active": None,
                            },
                        ),
                        self._elapsed_ms(started),
                        None,
                    )
                lookup: Result = self._provider.get_client_by_ip(
                    site_id=session.site_id,
                    client_ip=session.client_ip,
                )
                resolved_mac = (
                    lookup.data.get("client_mac")
                    if lookup.success
                    else None
                )
                if not resolved_mac:
                    if lookup.success:
                        lookup = Result.fail(
                            error="CLIENT_NOT_FOUND",
                            message="Client was not found by IP.",
                            data={
                                **lookup.data,
                                "authStatus": None,
                                "active": None,
                            },
                        )
                    return (
                        lookup,
                        self._elapsed_ms(started),
                        None,
                    )
                self._require_update(
                    self._session_manager.set_client_mac(
                        session,
                        resolved_mac,
                        run_number=run.run_number,
                        run_token=run.run_token,
                    ),
                    session,
                    run,
                    "client_identity",
                )

            result: Result = self._provider.get_client(
                site_id=session.site_id,
                client_mac=session.client_mac,
            )
            elapsed = self._elapsed_ms(started)
            if self._is_token_error(result):
                self._emit_token_error(session, operation, result)
            elif not result.success and self._is_unavailable(result):
                self._emit_omada_unavailable(
                    session,
                    operation=operation,
                    result=result,
                    response_time_ms=elapsed,
                    operation_number=operation_number,
                )
            return result, elapsed, None
        except Exception as exc:
            result = Result.fail(
                error="GET_CLIENT_EXCEPTION",
                message=str(exc),
                data={
                    "http_status": 0,
                    "error_code": 0,
                    "authStatus": None,
                    "active": None,
                },
            )
            elapsed = self._elapsed_ms(started)
            self._emit_omada_unavailable(
                session,
                operation=operation,
                result=result,
                response_time_ms=elapsed,
                exception_type=type(exc).__name__,
                operation_number=operation_number,
            )
            return result, elapsed, type(exc).__name__

    def _emit_authorization_response(
        self,
        session: AuthSession,
        result: Result,
        attempt: int,
        response_time_ms: float,
        exception_type: Optional[str],
        metrics: _RunMetrics,
    ) -> None:
        if self._is_token_error(result):
            self._emit_token_error(session, "authorize", result)
        elif not result.success and (
            exception_type or self._is_unavailable(result)
        ):
            self._emit_omada_unavailable(
                session,
                operation="authorize",
                result=result,
                response_time_ms=response_time_ms,
                exception_type=exception_type,
                operation_number=attempt,
            )

        level = "info"
        if exception_type or self._is_unavailable(result):
            level = "error"
        elif not result.success:
            level = "warning"
        log_auth_event(
            events.AUTHORIZATION_RESPONSE,
            session,
            level=level,
            auth_attempt=attempt,
            request_success=result.success,
            omada_http_status=self._result_value(
                result,
                "http_status",
            ),
            omada_error_code=self._result_value(
                result,
                "error_code",
            ),
            omada_message=result.message,
            response_time_ms=response_time_ms,
            elapsed_ms=self._elapsed_ms(metrics.started),
        )

    def _emit_verification_result(
        self,
        *,
        session: AuthSession,
        result: Result,
        attempt: int,
        phase: str,
        verified: bool,
        response_time_ms: float,
        exception_type: Optional[str],
        metrics: _RunMetrics,
    ) -> None:
        level = "info" if verified else "warning"
        if exception_type or self._is_unavailable(result):
            level = "error"
        log_auth_event(
            events.VERIFICATION_RESULT,
            session,
            level=level,
            auth_attempt=attempt,
            verification_phase=phase,
            auth_status=self._extract_auth_status(result),
            active=self._extract_active(result),
            verified=verified,
            omada_http_status=self._result_value(
                result,
                "http_status",
            ),
            omada_error_code=self._result_value(
                result,
                "error_code",
            ),
            response_time_ms=response_time_ms,
            elapsed_ms=self._elapsed_ms(metrics.started),
        )

    def _emit_omada_unavailable(
        self,
        session: AuthSession,
        *,
        operation: str,
        result: Result,
        response_time_ms: float,
        exception_type: Optional[str] = None,
        operation_number: Optional[int] = None,
    ) -> None:
        counter_fields: dict[str, Any] = {}
        if operation == "readiness":
            counter_fields["readiness_check"] = operation_number
        elif operation in {
            "authorize",
            "verify",
            "final_verify",
        }:
            counter_fields["auth_attempt"] = operation_number

        log_auth_event(
            events.OMADA_UNAVAILABLE,
            session,
            level="error",
            operation=operation,
            exception_type=exception_type,
            error=result.message or result.error,
            response_time_ms=response_time_ms,
            **counter_fields,
        )

    def _emit_token_error(
        self,
        session: AuthSession,
        operation: str,
        result: Result,
    ) -> None:
        log_auth_event(
            events.TOKEN_ERROR,
            session,
            level="error",
            operation=operation,
            omada_http_status=self._result_value(
                result,
                "http_status",
            ),
            omada_error_code=self._result_value(
                result,
                "error_code",
            ),
            error=result.message or result.error,
        )

    def _emit_finished(
        self,
        session: AuthSession,
        metrics: _RunMetrics,
        run: _WorkerRun,
    ) -> None:
        run_state = self._session_manager.run_snapshot(
            session,
            run.run_number,
        )
        if run_state is None or run_state["finished_at"] is None:
            return

        duration_ms = self._elapsed_ms(metrics.started)
        final_state = (
            run_state["final_state"]
            or session.status.value
        )
        final_reason = (
            run_state["final_reason"]
            or metrics.final_reason
        )
        retryable = bool(run_state["retryable"])
        fields = {
            **_session_fields(session),
            "state": final_state,
            "run_number": run.run_number,
            "auth_attempt": metrics.auth_attempts,
            "retry_request_id": run_state["retry_request_id"],
            "final_state": final_state,
            "final_reason": final_reason,
            "retryable": retryable,
            "duration_ms": duration_ms,
            "readiness_checks": metrics.readiness_checks,
            "auth_attempts": metrics.auth_attempts,
            "ready_after_ms": metrics.ready_after_ms,
            "last_active": metrics.last_active,
            "last_auth_status": metrics.last_auth_status,
            "last_omada_error_code": (
                metrics.last_omada_error_code
            ),
        }
        if final_state == AuthStatus.AUTHORIZED.value:
            level = "info"
        elif retryable or final_state == AuthStatus.EXPIRED.value:
            level = "warning"
        else:
            level = "error"

        telemetry = get_auth_telemetry()
        telemetry.safe_emit(
            events.RUN_FINISHED,
            session.session_id,
            level,
            **fields,
        )
        if run.run_number >= 2:
            retry_event = (
                events.RETRY_SUCCEEDED
                if final_state == AuthStatus.AUTHORIZED.value
                else events.RETRY_FAILED
            )
            telemetry.safe_emit(
                retry_event,
                session.session_id,
                level,
                **fields,
            )

        if (
            self._session_manager.current_run_identity_matches(
                session,
                run.run_number,
                run.run_token,
            )
            and (
                final_state in {
                    AuthStatus.AUTHORIZED.value,
                    AuthStatus.EXPIRED.value,
                }
                or (
                    final_state == AuthStatus.FAILED.value
                    and not retryable
                )
            )
        ):
            telemetry.safe_emit_once(
                events.SESSION_FINISHED,
                session.session_id,
                level,
                **fields,
            )

        log_auth_event(
            events.WORKER_COMPLETED,
            session,
            run_number=run.run_number,
            auth_attempt=metrics.auth_attempts,
            worker_id=metrics.worker_id,
            final_state=final_state,
            final_reason=final_reason,
            retryable=retryable,
            duration_ms=duration_ms,
        )

    def _sleep_with_ttl_check(
        self,
        session_id: str,
        seconds: float,
        start_progress: Optional[int] = None,
        end_progress: Optional[int] = None,
        run: Optional[_WorkerRun] = None,
    ) -> bool:
        started = time.monotonic()
        deadline = started + seconds
        while True:
            if (
                run is not None
                and not self._session_manager.current_run_matches(
                    session_id,
                    run.run_number,
                    run.run_token,
                )
            ):
                return False
            now = time.monotonic()
            if now >= deadline:
                if end_progress is not None:
                    kwargs = {}
                    if run is not None:
                        kwargs = {
                            "run_number": run.run_number,
                            "run_token": run.run_token,
                        }
                    if not self._session_manager.set_progress(
                        session_id,
                        end_progress,
                        **kwargs,
                    ):
                        return False
                return True
            if self._session_manager.is_expired(session_id):
                return False
            if (
                start_progress is not None
                and end_progress is not None
                and seconds > 0
            ):
                ratio = min(1.0, max(0.0, (now - started) / seconds))
                kwargs = {}
                if run is not None:
                    kwargs = {
                        "run_number": run.run_number,
                        "run_token": run.run_token,
                    }
                if not self._session_manager.set_progress(
                    session_id,
                    round(
                        start_progress
                        + (end_progress - start_progress) * ratio
                    ),
                    **kwargs,
                ):
                    return False
            time.sleep(
                min(
                    SLEEP_CHECK_INTERVAL_SECONDS,
                    max(0.0, deadline - now),
                )
            )

    def _expire_session(
        self,
        session: AuthSession,
        run: _WorkerRun,
    ) -> None:
        self._require_update(
            self._session_manager.finish_run(
                session,
                run_number=run.run_number,
                run_token=run.run_token,
                final_state=AuthStatus.EXPIRED,
                final_reason="SESSION_EXPIRED",
                retryable=False,
                error="Authorization session expired.",
                progress=100,
            ),
            session,
            run,
            "expired",
        )

    def _finish_failed(
        self,
        session: AuthSession,
        run: _WorkerRun,
        *,
        final_reason: str,
        retryable: bool,
        error: str,
    ) -> None:
        self._require_update(
            self._session_manager.finish_run(
                session,
                run_number=run.run_number,
                run_token=run.run_token,
                final_state=AuthStatus.FAILED,
                final_reason=final_reason,
                retryable=retryable,
                error=error,
                progress=100,
            ),
            session,
            run,
            "failed",
        )

    def _mark_authorized(
        self,
        session: AuthSession,
        result: Result,
        run: _WorkerRun,
        *,
        final_reason: str,
    ) -> None:
        self._require_update(
            self._session_manager.set_auth_status(
                session,
                self._extract_auth_status(result),
                run_number=run.run_number,
                run_token=run.run_token,
            ),
            session,
            run,
            "authorized_auth_status",
        )
        self._require_update(
            self._session_manager.finish_run(
                session,
                run_number=run.run_number,
                run_token=run.run_token,
                final_state=AuthStatus.AUTHORIZED,
                final_reason=final_reason,
                retryable=False,
                error="",
                progress=100,
            ),
            session,
            run,
            "authorized",
        )
        self._submit_authorized_snapshot(session, run)

    def _submit_authorized_snapshot(
        self,
        session: AuthSession,
        run: _WorkerRun,
    ) -> None:
        try:
            run_state = self._session_manager.run_snapshot(
                session,
                run.run_number,
            )
            if (
                run_state is None
                or run_state.get("final_state")
                != AuthStatus.AUTHORIZED.value
            ):
                return
            finished_at = run_state.get("finished_at")
            if not isinstance(finished_at, str):
                raise ValueError(
                    "completed AuthRun has no finished_at"
                )
            request = AuthorizedClientSnapshotRequest(
                auth_session_id=session.session_id,
                site_id=session.site_id,
                requested_mac=session.client_mac or "",
                authorized_at=datetime.fromisoformat(finished_at),
                auth_context=AuthorizedClientAuthContext(
                    client_ip=session.client_ip,
                    portal_ssid=session.ssid,
                    portal_ap_mac=session.ap_mac,
                    portal_radio_id=session.radio_id,
                    auth_run_number=run_state["run_number"],
                    authorization_attempt=run_state[
                        "auth_attempt_count"
                    ],
                    auth_final_reason=(
                        run_state.get("final_reason") or ""
                    ),
                    retry_request_id=run_state.get(
                        "retry_request_id"
                    ),
                ),
            )
            self._snapshot_collector.submit(request)
        except Exception:
            logger.exception("visitor_snapshot_submission_failed")

    def _ensure_current(
        self,
        session: AuthSession,
        run: _WorkerRun,
        operation: str,
    ) -> None:
        if self._session_manager.current_run_matches(
            session,
            run.run_number,
            run.run_token,
        ):
            return
        self._raise_stale(session, run, operation)

    def _require_update(
        self,
        updated: bool,
        session: AuthSession,
        run: _WorkerRun,
        operation: str,
    ) -> None:
        if updated:
            return
        self._raise_stale(session, run, operation)

    def _raise_stale(
        self,
        session: AuthSession,
        run: _WorkerRun,
        operation: str,
    ) -> None:
        if not run.stale_reported:
            run.stale_reported = True
            run_state = self._session_manager.run_snapshot(
                session,
                run.run_number,
            ) or {}
            get_auth_telemetry().safe_emit(
                events.WORKER_RESULT_IGNORED,
                session.session_id,
                "warning",
                site_id=session.site_id,
                client_ip=session.client_ip,
                client_mac=session.client_mac,
                run_number=run.run_number,
                auth_attempt=run_state.get(
                    "auth_attempt_count",
                    0,
                ),
                current_run_number=session.current_run_number,
                reason="STALE_RUN_TOKEN",
                ignored_operation=operation,
            )
        raise _StaleRun("Worker run token is stale.")

    @staticmethod
    def _classify_failure(
        result: Optional[Result],
        exception_type: Optional[str] = None,
    ) -> tuple[Optional[str], bool]:
        if result is None or result.success:
            return None, False

        error = str(result.error or "").upper()
        message = str(result.message or "").lower()
        raw_http_status = AuthWorker._result_value(
            result,
            "http_status",
        )
        try:
            http_status = int(raw_http_status or 0)
        except (TypeError, ValueError):
            http_status = 0

        normalized_exception = str(exception_type or "").strip()
        if normalized_exception in {
            "Timeout",
            "TimeoutError",
            "ConnectTimeout",
            "ReadTimeout",
        }:
            return "OMADA_REQUEST_TIMEOUT", True
        if normalized_exception in {
            "ConnectionError",
            "ConnectionRefusedError",
            "ConnectionResetError",
            "ConnectError",
            "NewConnectionError",
            "ProxyError",
            "SSLError",
        }:
            return "OMADA_CONNECTION_ERROR", True
        if normalized_exception in {
            "RequestException",
            "ChunkedEncodingError",
        }:
            return "OMADA_UNAVAILABLE", True

        if error == "AUTH_PROVIDER_EXCEPTION":
            return "AUTH_PROVIDER_EXCEPTION", False
        if exception_type or error in {
            "GET_CLIENT_EXCEPTION",
            "UNAUTH_PROVIDER_EXCEPTION",
            "UNEXPECTED_ERROR",
        }:
            return "WORKER_EXCEPTION", False
        if error == "TOKEN_FAILED" or http_status == 401:
            return "AUTH_TOKEN_ERROR", False
        if http_status == 403:
            return "OMADA_HTTP_403", False
        if http_status >= 500:
            return "OMADA_HTTP_5XX", True
        if error in {
            "OMADA_UNAVAILABLE",
            "OMADA_CONNECTION_ERROR",
            "OMADA_REQUEST_TIMEOUT",
            "OMADA_HTTP_5XX",
            "AUTHORIZATION_TIMEOUT",
        }:
            return error, True
        if error in {
            "AUTH_TOKEN_ERROR",
            "INVALID_CREDENTIALS",
            "OMADA_HTTP_401",
            "OMADA_HTTP_403",
            "AUTHORIZATION_REJECTED",
            "AUTHORIZATION_REJECTED_FINAL",
            "CONFIGURATION_ERROR",
            "INVALID_SESSION",
            "CLIENT_BLOCKED",
        }:
            return error, False
        if error in {"CLIENT_NOT_FOUND", "NOT_FOUND"}:
            return "CLIENT_NOT_FOUND", True
        if error == "CLIENT_NOT_READY":
            return "CLIENT_NOT_READY", True
        if error == "HTTP_ERROR":
            if "timeout" in message or "timed out" in message:
                return "OMADA_REQUEST_TIMEOUT", True
            return "OMADA_CONNECTION_ERROR", True
        if error == "AUTH_FAILED":
            return "AUTHORIZATION_REJECTED", False
        return "CONFIGURATION_ERROR", False

    @staticmethod
    def _capture_last(
        metrics: _RunMetrics,
        result: Optional[Result],
    ) -> None:
        metrics.last_active = AuthWorker._extract_active(result)
        metrics.last_auth_status = AuthWorker._extract_auth_status(result)
        metrics.last_omada_error_code = AuthWorker._result_value(
            result,
            "error_code",
        )

    @staticmethod
    def _client_found(result: Result) -> Optional[bool]:
        if result.success:
            return True

        error = str(result.error or "").upper()
        http_status = AuthWorker._result_value(
            result,
            "http_status",
        )
        error_code = AuthWorker._result_value(
            result,
            "error_code",
        )
        message = str(result.message or "").lower()

        if (
            error in {"CLIENT_NOT_FOUND", "NOT_FOUND"}
            or http_status == 404
            or error_code == -41011
            or "client not found" in message
            or "client does not exist" in message
        ):
            return False

        return None

    @staticmethod
    def _extract_auth_status(
        result: Optional[Result],
    ) -> Optional[int]:
        value = AuthWorker._result_value(result, "authStatus")
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_active(
        result: Optional[Result],
    ) -> Optional[bool]:
        value = AuthWorker._result_value(result, "active")
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes"}:
                return True
            if normalized in {"false", "0", "no"}:
                return False
        return None

    @staticmethod
    def _result_value(
        result: Optional[Result],
        key: str,
    ) -> Optional[Any]:
        if result is None or not result.data:
            return None
        return result.data.get(key)

    @staticmethod
    def _is_token_error(result: Result) -> bool:
        return str(result.error or "").upper() == "TOKEN_FAILED"

    @staticmethod
    def _is_unavailable(result: Result) -> bool:
        return str(result.error or "").upper() in {
            "HTTP_ERROR",
            "OMADA_UNAVAILABLE",
            "OMADA_CONNECTION_ERROR",
            "OMADA_REQUEST_TIMEOUT",
            "OMADA_HTTP_5XX",
            "UNEXPECTED_ERROR",
            "AUTH_PROVIDER_EXCEPTION",
            "GET_CLIENT_EXCEPTION",
            "UNAUTH_PROVIDER_EXCEPTION",
        }

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return round((time.monotonic() - started) * 1000, 2)

    @staticmethod
    def _milliseconds(seconds: float) -> int:
        return int(round(seconds * 1000))
