import json
import logging
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Optional

from app.models import Result
from .manager import AuthSessionManager
from .session import AuthSession, AuthStatus


INITIAL_AUTH_DELAY_SECONDS = 30.0
MAX_AUTH_ATTEMPTS = 3
VERIFY_DELAY_SECONDS = 3.0
SLEEP_CHECK_INTERVAL_SECONDS = 0.25


logger = logging.getLogger("captiveportal.auth")


ATTEMPT_PROGRESS = {
    1: {
        "authorizing": 50,
        "verifying": 65,
        "verified": 72,
    },
    2: {
        "authorizing": 72,
        "verifying": 80,
        "verified": 86,
    },
    3: {
        "authorizing": 86,
        "verifying": 92,
        "verified": 92,
    },
}


def log_auth_event(
    event: str,
    session: AuthSession,
    level: int = logging.INFO,
    auth_status: Optional[int] = None,
    http_status: Optional[int] = None,
    error_code: Optional[int] = None,
    message: str = "",
    elapsed_ms: Optional[float] = None,
    traceback_str: Optional[str] = None,
    **extra_fields: Any,
) -> None:
    """Записывает однострочное структурированное событие авторизации."""

    log_data = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session.session_id,
        "site_id": session.site_id,
        "client_mac": session.client_mac,
        "client_ip": session.client_ip,
        "attempt": session.attempt,
        "status": session.status.value,
        "progress": session.progress,
        "authStatus": (
            auth_status
            if auth_status is not None
            else session.auth_status
        ),
        "http_status": http_status,
        "errorCode": error_code,
        "message": message,
        "elapsed_ms": elapsed_ms,
        "traceback": traceback_str,
        **extra_fields,
    }

    log_data = {
        key: value
        for key, value in log_data.items()
        if value is not None and value != ""
    }

    logger.log(
        level,
        json.dumps(log_data, ensure_ascii=False),
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
        """
        Выполняет полный серверный цикл:

        WAITING
        → initial GET client
        → до трёх authorize/verify
        → final verify
        → unauthorize при полном провале.
        """

        session = self._session_manager.get(session_id)

        if session is None:
            logger.warning(
                json.dumps(
                    {
                        "event": "AUTH_SESSION_NOT_FOUND",
                        "timestamp": datetime.now(
                            timezone.utc
                        ).isoformat(),
                        "session_id": session_id,
                    },
                    ensure_ascii=False,
                )
            )
            return

        log_auth_event(
            "AUTH_WORKER_STARTED",
            session,
        )

        try:
            self._session_manager.update_status(
                session,
                AuthStatus.WAITING,
                error="",
                progress=0,
            )

            log_auth_event(
                "AUTH_INITIAL_DELAY_STARTED",
                session,
                delay_seconds=INITIAL_AUTH_DELAY_SECONDS,
            )

            sleep_completed = self._sleep_with_ttl_check(
                session_id=session.session_id,
                seconds=INITIAL_AUTH_DELAY_SECONDS,
                start_progress=0,
                end_progress=50,
            )

            if not sleep_completed:
                self._expire_session(session)
                return

            log_auth_event(
                "AUTH_INITIAL_DELAY_FINISHED",
                session,
            )

            if self._session_manager.expire_if_needed(
                session
            ):
                log_auth_event(
                    "AUTH_SESSION_EXPIRED",
                    session,
                    level=logging.WARNING,
                )
                return

            # До первой команды /auth проверяем,
            # не успел ли Omada уже авторизовать клиента.
            initial_result = self._get_client(
                session=session,
                event_prefix="INITIAL_VERIFY",
            )

            initial_auth_status = self._extract_auth_status(
                initial_result
            )

            self._session_manager.set_auth_status(
                session,
                initial_auth_status,
            )

            if initial_auth_status == 2:
                self._mark_authorized(
                    session=session,
                    event="ALREADY_AUTHORIZED",
                    result=initial_result,
                )
                return

            # Выполняем максимум три попытки.
            for attempt in range(
                1,
                MAX_AUTH_ATTEMPTS + 1,
            ):
                if self._session_manager.expire_if_needed(
                    session
                ):
                    log_auth_event(
                        "AUTH_SESSION_EXPIRED",
                        session,
                        level=logging.WARNING,
                    )
                    return

                progress = ATTEMPT_PROGRESS[attempt]

                self._session_manager.begin_attempt(
                    session,
                    attempt,
                    progress=progress["authorizing"],
                )

                log_auth_event(
                    "AUTH_ATTEMPT_STARTED",
                    session,
                    attempt=attempt,
                )

                auth_result = self._authorize_client(
                    session
                )

                if auth_result.success:
                    log_auth_event(
                        "AUTH_REQUEST_SUCCEEDED",
                        session,
                        http_status=self._result_value(
                            auth_result,
                            "http_status",
                        ),
                        error_code=self._result_value(
                            auth_result,
                            "error_code",
                        ),
                    )
                else:
                    # Даже при timeout или другой ошибке
                    # обязательно выполняем последующий GET.
                    log_auth_event(
                        "AUTH_REQUEST_FAILED",
                        session,
                        level=logging.WARNING,
                        http_status=self._result_value(
                            auth_result,
                            "http_status",
                        ),
                        error_code=self._result_value(
                            auth_result,
                            "error_code",
                        ),
                        message=auth_result.message,
                    )

                self._session_manager.update_status(
                    session,
                    AuthStatus.VERIFYING,
                    progress=progress["verifying"],
                )

                log_auth_event(
                    "AUTH_VERIFY_DELAY_STARTED",
                    session,
                    delay_seconds=VERIFY_DELAY_SECONDS,
                )

                sleep_completed = self._sleep_with_ttl_check(
                    session_id=session.session_id,
                    seconds=VERIFY_DELAY_SECONDS,
                    start_progress=progress["verifying"],
                    end_progress=progress["verified"],
                )

                if not sleep_completed:
                    self._expire_session(session)
                    return

                verify_result = self._get_client(
                    session=session,
                    event_prefix="VERIFY",
                )

                auth_status = self._extract_auth_status(
                    verify_result
                )

                self._session_manager.set_auth_status(
                    session,
                    auth_status,
                )

                if auth_status == 2:
                    self._mark_authorized(
                        session=session,
                        event="AUTHORIZED",
                        result=verify_result,
                    )
                    return

                if verify_result.success:
                    log_auth_event(
                        "VERIFY_NOT_AUTHORIZED",
                        session,
                        level=logging.WARNING,
                        auth_status=auth_status,
                        http_status=self._result_value(
                            verify_result,
                            "http_status",
                        ),
                        error_code=self._result_value(
                            verify_result,
                            "error_code",
                        ),
                    )
                else:
                    # Техническая ошибка проверки не отменяет
                    # оставшиеся попытки авторизации.
                    log_auth_event(
                        "VERIFY_ERROR",
                        session,
                        level=logging.ERROR,
                        http_status=self._result_value(
                            verify_result,
                            "http_status",
                        ),
                        error_code=self._result_value(
                            verify_result,
                            "error_code",
                        ),
                        message=verify_result.message,
                    )

            # После всех попыток выполняется обязательный
            # финальный защитный GET.
            if self._session_manager.expire_if_needed(
                session
            ):
                log_auth_event(
                    "AUTH_SESSION_EXPIRED",
                    session,
                    level=logging.WARNING,
                )
                return

            self._session_manager.update_status(
                session,
                AuthStatus.VERIFYING,
                progress=95,
            )

            log_auth_event(
                "FINAL_VERIFY_STARTED",
                session,
            )

            final_result = self._get_client(
                session=session,
                event_prefix="FINAL_VERIFY",
            )

            final_auth_status = self._extract_auth_status(
                final_result
            )

            self._session_manager.set_auth_status(
                session,
                final_auth_status,
            )

            if final_auth_status == 2:
                self._mark_authorized(
                    session=session,
                    event="AUTHORIZED_FINAL_VERIFY",
                    result=final_result,
                )
                return

            # Только после трёх попыток, трёх verify
            # и финальной проверки разрешён recovery.
            self._session_manager.update_status(
                session,
                AuthStatus.RESETTING,
                progress=95,
            )

            log_auth_event(
                "RESET_STARTED",
                session,
                level=logging.WARNING,
                final_auth_status=final_auth_status,
            )

            reset_started = time.monotonic()

            reset_result: Result = (
                self._provider.unauthorize(
                    site_id=session.site_id,
                    client_mac=session.client_mac,
                )
            )

            reset_elapsed_ms = round(
                (
                    time.monotonic()
                    - reset_started
                )
                * 1000,
                2,
            )

            if reset_result.success:
                self._session_manager.update_status(
                    session,
                    AuthStatus.RESET,
                    error=(
                        "Portal session reset. "
                        "Reconnect to Wi-Fi."
                    ),
                    progress=100,
                )

                log_auth_event(
                    "RESET_SUCCEEDED",
                    session,
                    level=logging.WARNING,
                    http_status=self._result_value(
                        reset_result,
                        "http_status",
                    ),
                    error_code=self._result_value(
                        reset_result,
                        "error_code",
                    ),
                    elapsed_ms=reset_elapsed_ms,
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

                log_auth_event(
                    "RESET_REQUEST_FAILED",
                    session,
                    level=logging.ERROR,
                    http_status=self._result_value(
                        reset_result,
                        "http_status",
                    ),
                    error_code=self._result_value(
                        reset_result,
                        "error_code",
                    ),
                    message=reset_result.message,
                    elapsed_ms=reset_elapsed_ms,
                )

        except Exception as exc:
            self._session_manager.fail(
                session,
                error=str(exc),
            )

            log_auth_event(
                "AUTH_WORKER_EXCEPTION",
                session,
                level=logging.ERROR,
                message=str(exc),
                traceback_str=traceback.format_exc(),
            )

        finally:
            self._session_manager.mark_worker_finished(
                session
            )

            log_auth_event(
                "AUTH_WORKER_FINISHED",
                session,
            )

    def _authorize_client(
        self,
        session: AuthSession,
    ) -> Result:
        started = time.monotonic()

        try:
            result: Result = self._provider.authorize(
                site_id=session.site_id,
                client_mac=session.client_mac,
            )
        except Exception as exc:
            elapsed_ms = round(
                (time.monotonic() - started) * 1000,
                2,
            )

            log_auth_event(
                "AUTH_PROVIDER_EXCEPTION",
                session,
                level=logging.ERROR,
                message=str(exc),
                elapsed_ms=elapsed_ms,
                traceback_str=traceback.format_exc(),
            )

            return Result.fail(
                error="AUTH_PROVIDER_EXCEPTION",
                message=str(exc),
                data={
                    "http_status": 0,
                    "error_code": 0,
                },
            )

        elapsed_ms = round(
            (time.monotonic() - started) * 1000,
            2,
        )

        log_auth_event(
            "AUTH_REQUEST_FINISHED",
            session,
            level=(
                logging.INFO
                if result.success
                else logging.WARNING
            ),
            http_status=self._result_value(
                result,
                "http_status",
            ),
            error_code=self._result_value(
                result,
                "error_code",
            ),
            message=(
                ""
                if result.success
                else result.message
            ),
            elapsed_ms=elapsed_ms,
        )

        return result

    def _get_client(
        self,
        session: AuthSession,
        event_prefix: str,
    ) -> Result:
        started = time.monotonic()

        try:
            result: Result = self._provider.get_client(
                site_id=session.site_id,
                client_mac=session.client_mac,
            )
        except Exception as exc:
            elapsed_ms = round(
                (time.monotonic() - started) * 1000,
                2,
            )

            log_auth_event(
                f"{event_prefix}_PROVIDER_EXCEPTION",
                session,
                level=logging.ERROR,
                message=str(exc),
                elapsed_ms=elapsed_ms,
                traceback_str=traceback.format_exc(),
            )

            return Result.fail(
                error="GET_CLIENT_EXCEPTION",
                message=str(exc),
                data={
                    "http_status": 0,
                    "error_code": 0,
                    "authStatus": 0,
                },
            )

        elapsed_ms = round(
            (time.monotonic() - started) * 1000,
            2,
        )

        log_auth_event(
            f"{event_prefix}_FINISHED",
            session,
            level=(
                logging.INFO
                if result.success
                else logging.WARNING
            ),
            auth_status=self._extract_auth_status(
                result
            ),
            http_status=self._result_value(
                result,
                "http_status",
            ),
            error_code=self._result_value(
                result,
                "error_code",
            ),
            message=(
                ""
                if result.success
                else result.message
            ),
            elapsed_ms=elapsed_ms,
        )

        return result

    def _sleep_with_ttl_check(
        self,
        session_id: str,
        seconds: float,
        start_progress: Optional[int] = None,
        end_progress: Optional[int] = None,
    ) -> bool:
        """
        Спит небольшими интервалами.

        Во время начального ожидания также плавно обновляет
        progress, но решение о результате остаётся за backend.
        """

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

            if self._session_manager.is_expired(
                session_id
            ):
                return False

            if (
                start_progress is not None
                and end_progress is not None
                and seconds > 0
            ):
                elapsed = now - started
                ratio = min(
                    1.0,
                    max(0.0, elapsed / seconds),
                )

                progress = round(
                    start_progress
                    + (
                        end_progress
                        - start_progress
                    )
                    * ratio
                )

                self._session_manager.set_progress(
                    session_id,
                    progress,
                )

            remaining = deadline - now

            time.sleep(
                min(
                    SLEEP_CHECK_INTERVAL_SECONDS,
                    max(0.0, remaining),
                )
            )

    def _expire_session(
        self,
        session: AuthSession,
    ) -> None:
        self._session_manager.update_status(
            session,
            AuthStatus.EXPIRED,
            error="Authorization session expired.",
            progress=100,
        )

        log_auth_event(
            "AUTH_SESSION_EXPIRED",
            session,
            level=logging.WARNING,
        )

    def _mark_authorized(
        self,
        session: AuthSession,
        event: str,
        result: Result,
    ) -> None:
        auth_status = self._extract_auth_status(
            result
        )

        self._session_manager.set_auth_status(
            session,
            auth_status,
        )

        self._session_manager.update_status(
            session,
            AuthStatus.AUTHORIZED,
            error="",
            progress=100,
        )

        log_auth_event(
            event,
            session,
            auth_status=auth_status,
            http_status=self._result_value(
                result,
                "http_status",
            ),
            error_code=self._result_value(
                result,
                "error_code",
            ),
        )

    @staticmethod
    def _extract_auth_status(
        result: Optional[Result],
    ) -> Optional[int]:
        if result is None:
            return None

        if not result.data:
            return None

        value = result.data.get("authStatus")

        if value is None:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _result_value(
        result: Optional[Result],
        key: str,
    ) -> Optional[Any]:
        if result is None or not result.data:
            return None

        return result.data.get(key)
