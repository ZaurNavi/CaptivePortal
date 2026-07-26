import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Optional

from app.auth_telemetry import get_auth_telemetry
from app.auth_telemetry import events
from app.models import Result
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
    final_reason: str = "INTERNAL_ERROR"


def _session_fields(session: AuthSession) -> dict[str, Any]:
    return {
        "site_id": session.site_id,
        "client_mac": session.client_mac,
        "client_ip": session.client_ip,
        "state": session.status.value,
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
    ):
        self._provider = provider
        self._session_manager = session_manager

    def process(self, session_id: str) -> None:
        session = self._session_manager.get(session_id)
        if session is None:
            return

        metrics = _RunMetrics(
            started=time.monotonic(),
            worker_id=threading.current_thread().name,
        )
        log_auth_event(
            events.WORKER_STARTED,
            session,
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

        try:
            self._session_manager.update_status(
                session,
                AuthStatus.WAITING,
                error="",
                progress=0,
            )

            sleep_completed = self._sleep_with_ttl_check(
                session_id=session.session_id,
                seconds=MIN_INITIAL_DELAY_SECONDS,
                start_progress=0,
                end_progress=10,
            )
            if not sleep_completed:
                metrics.final_reason = "SESSION_EXPIRED"
                self._expire_session(session)
                return

            log_auth_event(
                events.INITIAL_DELAY_COMPLETED,
                session,
                level="debug",
                initial_delay_ms=self._milliseconds(
                    MIN_INITIAL_DELAY_SECONDS
                ),
                elapsed_ms=self._elapsed_ms(metrics.started),
            )

            ready_state, ready_result = self._wait_for_client_ready(
                session,
                metrics,
            )
            if ready_state == "expired":
                metrics.final_reason = "SESSION_EXPIRED"
                self._expire_session(session)
                return
            if ready_state == "authorized":
                if ready_result is None:
                    raise RuntimeError(
                        "Authorized client result is missing."
                    )
                metrics.final_reason = "ALREADY_AUTHORIZED"
                self._mark_authorized(session, ready_result)
                return
            if ready_state not in {"ready", "fallback"}:
                raise RuntimeError(
                    f"Unexpected client readiness state: {ready_state}"
                )

            for attempt in range(1, MAX_AUTH_ATTEMPTS + 1):
                if self._session_manager.expire_if_needed(session):
                    metrics.final_reason = "SESSION_EXPIRED"
                    return

                metrics.auth_attempts = attempt
                progress = ATTEMPT_PROGRESS[attempt]
                self._session_manager.begin_attempt(
                    session,
                    attempt,
                    progress=progress["authorizing"],
                )
                log_auth_event(
                    events.AUTHORIZATION_REQUEST,
                    session,
                    auth_attempt=attempt,
                    elapsed_ms=self._elapsed_ms(metrics.started),
                )

                auth_result, auth_ms, auth_exception = (
                    self._authorize_client(session)
                )
                self._emit_authorization_response(
                    session,
                    auth_result,
                    attempt,
                    auth_ms,
                    auth_exception,
                    metrics,
                )

                self._session_manager.update_status(
                    session,
                    AuthStatus.VERIFYING,
                    progress=progress["verifying"],
                )
                log_auth_event(
                    events.VERIFICATION_STARTED,
                    session,
                    level="debug",
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
                )
                if not sleep_completed:
                    metrics.final_reason = "SESSION_EXPIRED"
                    self._expire_session(session)
                    return

                verify_result, response_ms, exception_type = (
                    self._get_client(
                        session,
                        operation="verify",
                        operation_number=attempt,
                    )
                )
                auth_status = self._extract_auth_status(verify_result)
                active = self._extract_active(verify_result)
                self._capture_last(metrics, verify_result)
                self._session_manager.set_auth_status(
                    session,
                    auth_status,
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
                    self._mark_authorized(session, verify_result)
                    return

                if attempt < MAX_AUTH_ATTEMPTS:
                    log_auth_event(
                        events.RETRY_SCHEDULED,
                        session,
                        level="warning",
                        completed_attempt=attempt,
                        next_attempt=attempt + 1,
                        reason=(
                            verify_result.error
                            or "VERIFY_NOT_AUTHORIZED"
                        ),
                        elapsed_ms=self._elapsed_ms(metrics.started),
                    )

            if self._session_manager.expire_if_needed(session):
                metrics.final_reason = "SESSION_EXPIRED"
                return

            self._session_manager.update_status(
                session,
                AuthStatus.VERIFYING,
                progress=95,
            )
            log_auth_event(
                events.VERIFICATION_STARTED,
                session,
                level="debug",
                auth_attempt=metrics.auth_attempts,
                verification_delay_ms=0,
                verification_phase="final",
            )
            final_result, final_ms, final_exception = self._get_client(
                session,
                operation="final_verify",
                operation_number=metrics.auth_attempts,
            )
            final_auth_status = self._extract_auth_status(final_result)
            self._capture_last(metrics, final_result)
            self._session_manager.set_auth_status(
                session,
                final_auth_status,
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
                self._mark_authorized(session, final_result)
                return

            self._session_manager.update_status(
                session,
                AuthStatus.RESETTING,
                progress=95,
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

            if self._is_token_error(reset_result):
                self._emit_token_error(
                    session,
                    "unauthorize",
                    reset_result,
                )

            if reset_result.success:
                self._session_manager.update_status(
                    session,
                    AuthStatus.RESET,
                    error="Portal session reset. Reconnect to Wi-Fi.",
                    progress=100,
                )
                metrics.final_reason = (
                    "AUTH_EXHAUSTED_RESET_SUCCEEDED"
                )
            else:
                self._session_manager.update_status(
                    session,
                    AuthStatus.FAILED,
                    error=(
                        reset_result.message
                        or "Unable to reset Portal session."
                    ),
                    progress=100,
                )
                metrics.final_reason = "RESET_REQUEST_FAILED"

        except Exception as exc:
            self._session_manager.fail(session, error=str(exc))
            metrics.final_reason = "WORKER_EXCEPTION"
            logger.exception(
                "Authorization worker failed session_id=%s",
                session.session_id,
            )
            log_auth_event(
                events.WORKER_EXCEPTION,
                session,
                level="error",
                exception_type=type(exc).__name__,
                error=str(exc),
                elapsed_ms=self._elapsed_ms(metrics.started),
                worker_id=metrics.worker_id,
            )
        finally:
            self._session_manager.mark_worker_finished(session)
            self._emit_finished(session, metrics)

    def _wait_for_client_ready(
        self,
        session: AuthSession,
        metrics: _RunMetrics,
    ) -> tuple[str, Optional[Result]]:
        adaptive_wait_seconds = max(
            0.0,
            AUTH_FALLBACK_DELAY_SECONDS - MIN_INITIAL_DELAY_SECONDS,
        )
        started = time.monotonic()
        deadline = started + adaptive_wait_seconds
        last_result: Optional[Result] = None

        while True:
            if self._session_manager.expire_if_needed(session):
                return "expired", last_result

            metrics.readiness_checks += 1
            result, response_ms, exception_type = self._get_client(
                session,
                operation="readiness",
                operation_number=metrics.readiness_checks,
            )
            last_result = result
            auth_status = self._extract_auth_status(result)
            active = self._extract_active(result)
            self._capture_last(metrics, result)
            self._session_manager.set_auth_status(session, auth_status)

            total_waited = (
                MIN_INITIAL_DELAY_SECONDS
                + time.monotonic()
                - started
            )
            log_auth_event(
                events.CLIENT_CHECK,
                session,
                level="debug",
                readiness_check=metrics.readiness_checks,
                elapsed_ms=self._elapsed_ms(metrics.started),
                client_found=self._client_found(result),
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
                self._session_manager.set_progress(
                    session.session_id,
                    50,
                )
                metrics.ready_after_ms = round(total_waited * 1000, 2)
                get_auth_telemetry().safe_emit_once(
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
                self._session_manager.set_progress(
                    session.session_id,
                    50,
                )
                log_auth_event(
                    events.FALLBACK_TRIGGERED,
                    session,
                    level="warning",
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
                self._session_manager.set_progress(
                    session.session_id,
                    round(10 + (40 * ratio)),
                )

            if not self._sleep_with_ttl_check(
                session_id=session.session_id,
                seconds=min(
                    CLIENT_READY_POLL_SECONDS,
                    max(0.0, deadline - now),
                ),
            ):
                return "expired", last_result

    def _authorize_client(
        self,
        session: AuthSession,
    ) -> tuple[Result, float, Optional[str]]:
        started = time.monotonic()
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
    ) -> tuple[Result, float, Optional[str]]:
        started = time.monotonic()
        try:
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
    ) -> None:
        duration_ms = self._elapsed_ms(metrics.started)
        fields = {
            **_session_fields(session),
            "final_state": session.status.value,
            "final_reason": metrics.final_reason,
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
        if session.status == AuthStatus.AUTHORIZED:
            level = "info"
        elif session.status in {
            AuthStatus.RESET,
            AuthStatus.EXPIRED,
        }:
            level = "warning"
        else:
            level = "error"
        get_auth_telemetry().safe_emit_once(
            events.SESSION_FINISHED,
            session.session_id,
            level,
            **fields,
        )
        log_auth_event(
            events.WORKER_COMPLETED,
            session,
            worker_id=metrics.worker_id,
            final_state=session.status.value,
            final_reason=metrics.final_reason,
            duration_ms=duration_ms,
        )

    def _sleep_with_ttl_check(
        self,
        session_id: str,
        seconds: float,
        start_progress: Optional[int] = None,
        end_progress: Optional[int] = None,
    ) -> bool:
        started = time.monotonic()
        deadline = started + seconds
        while True:
            now = time.monotonic()
            if now >= deadline:
                if end_progress is not None:
                    self._session_manager.set_progress(
                        session_id,
                        end_progress,
                    )
                return True
            if self._session_manager.is_expired(session_id):
                return False
            if (
                start_progress is not None
                and end_progress is not None
                and seconds > 0
            ):
                ratio = min(1.0, max(0.0, (now - started) / seconds))
                self._session_manager.set_progress(
                    session_id,
                    round(
                        start_progress
                        + (end_progress - start_progress) * ratio
                    ),
                )
            time.sleep(
                min(
                    SLEEP_CHECK_INTERVAL_SECONDS,
                    max(0.0, deadline - now),
                )
            )

    def _expire_session(self, session: AuthSession) -> None:
        self._session_manager.update_status(
            session,
            AuthStatus.EXPIRED,
            error="Authorization session expired.",
            progress=100,
        )

    def _mark_authorized(
        self,
        session: AuthSession,
        result: Result,
    ) -> None:
        self._session_manager.set_auth_status(
            session,
            self._extract_auth_status(result),
        )
        self._session_manager.update_status(
            session,
            AuthStatus.AUTHORIZED,
            error="",
            progress=100,
        )

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
        message = str(result.message or "").lower()

        if (
            error in {"CLIENT_NOT_FOUND", "NOT_FOUND"}
            or http_status == 404
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
