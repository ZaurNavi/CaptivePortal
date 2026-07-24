import json
import logging
import time
import traceback
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from app.models import Result
from .session import AuthSession, AuthStatus
from .manager import AuthSessionManager

MAX_AUTH_ATTEMPTS = 3
VERIFY_DELAY_SECONDS = 3.0

logger = logging.getLogger("captiveportal.auth")

class VerifyResult(Enum):
    AUTHORIZED = "AUTHORIZED"
    UNAUTHORIZED = "UNAUTHORIZED"
    VERIFY_ERROR = "VERIFY_ERROR"

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
    **extra_fields: Any
) -> None:
    log_data = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session.session_id,
        "site_id": session.site_id,
        "client_mac": session.client_mac,
        "client_ip": session.client_ip,
        "attempt": session.attempt,
        "status": session.status.value,
        "authStatus": auth_status,
        "http_status": http_status,
        "errorCode": error_code,
        "message": message,
        "elapsed_ms": elapsed_ms,
        "traceback": traceback_str,
        **extra_fields
    }
    log_data = {k: v for k, v in log_data.items() if v is not None}
    logger.log(level, json.dumps(log_data, ensure_ascii=False))


class AuthWorker:
    def __init__(self, provider: Any, session_manager: AuthSessionManager):
        self._provider = provider
        self._session_manager = session_manager

    def process(self, session_id: str) -> None:
        session = self._session_manager.get(session_id)
        if not session:
            return

        self._session_manager.mark_worker_started(session)
        log_auth_event("AUTH_SESSION_STARTED", session, level=logging.INFO)

        try:
            for attempt in range(1, MAX_AUTH_ATTEMPTS + 1):
                self._session_manager.begin_attempt(session, attempt)
                log_auth_event("AUTH_ATTEMPT_STARTED", session, attempt=attempt)

                started = time.monotonic()
                auth_result: Result = self._provider.authorize(site_id=session.site_id, client_mac=session.client_mac)
                elapsed_ms = round((time.monotonic() - started) * 1000, 2)
                
                if auth_result.success:
                    log_auth_event("AUTH_REQUEST_SUCCEEDED", session, attempt=attempt, http_status=auth_result.data.get("http_status"), error_code=auth_result.data.get("error_code"), elapsed_ms=elapsed_ms)
                else:
                    log_auth_event("AUTH_REQUEST_FAILED", session, attempt=attempt, http_status=auth_result.data.get("http_status"), error_code=auth_result.data.get("error_code"), message=auth_result.message, elapsed_ms=elapsed_ms, level=logging.WARNING)

                self._session_manager.update_status(session, AuthStatus.VERIFYING)
                time.sleep(VERIFY_DELAY_SECONDS)

                started = time.monotonic()
                verify_result: Result = self._provider.get_client(site_id=session.site_id, client_mac=session.client_mac)
                elapsed_ms = round((time.monotonic() - started) * 1000, 2)

                verify_status = self._verify_client_status(verify_result)
                
                if verify_status == VerifyResult.AUTHORIZED:
                    auth_status = verify_result.data.get("authStatus", 0) if verify_result.data else 0
                    self._session_manager.update_status(session, AuthStatus.AUTHORIZED)
                    log_auth_event("AUTHORIZED", session, attempt=attempt, auth_status=auth_status, http_status=verify_result.data.get("http_status"), error_code=verify_result.data.get("error_code"), elapsed_ms=elapsed_ms, level=logging.INFO)
                    return
                
                elif verify_status == VerifyResult.UNAUTHORIZED:
                    auth_status = verify_result.data.get("authStatus", 0) if verify_result.data else 0
                    confirmed = self._session_manager.increment_confirmed_failure(session)
                    log_auth_event("VERIFY_NOT_AUTHORIZED", session, attempt=attempt, auth_status=auth_status, http_status=verify_result.data.get("http_status"), error_code=verify_result.data.get("error_code"), elapsed_ms=elapsed_ms, confirmed_failures=confirmed, level=logging.WARNING)
                
                else:
                    self._session_manager.update_status(session, AuthStatus.FAILED, error="Verification failed due to technical error")
                    log_auth_event("VERIFY_ERROR", session, attempt=attempt, http_status=verify_result.data.get("http_status") if verify_result.data else 0, error_code=verify_result.data.get("error_code") if verify_result.data else 0, message=verify_result.message if verify_result else "Request failed", elapsed_ms=elapsed_ms, level=logging.ERROR)
                    log_auth_event("AUTH_FAILED", session, message="Verification failed due to technical error", level=logging.ERROR)
                    return

            confirmed_failures = self._session_manager.get_confirmed_failures(session)
            
            if confirmed_failures >= MAX_AUTH_ATTEMPTS:
                self._session_manager.update_status(session, AuthStatus.RESETTING)
                log_auth_event("RESET_STARTED", session, level=logging.INFO)

                started = time.monotonic()
                unauth_result: Result = self._provider.unauthorize(site_id=session.site_id, client_mac=session.client_mac)
                elapsed_ms = round((time.monotonic() - started) * 1000, 2)
                
                if unauth_result.success:
                    self._session_manager.update_status(session, AuthStatus.RESET)
                    log_auth_event("RESET_SUCCEEDED", session, http_status=unauth_result.data.get("http_status"), error_code=unauth_result.data.get("error_code"), elapsed_ms=elapsed_ms, level=logging.INFO)
                else:
                    self._session_manager.update_status(session, AuthStatus.FAILED, error=unauth_result.message)
                    log_auth_event("RESET_REQUEST_FAILED", session, http_status=unauth_result.data.get("http_status"), error_code=unauth_result.data.get("error_code"), message=unauth_result.message, elapsed_ms=elapsed_ms, level=logging.WARNING)
            else:
                self._session_manager.update_status(session, AuthStatus.FAILED, error="Insufficient confirmed failures for recovery")
                log_auth_event("RECOVERY_SKIPPED", session, confirmed_failures=confirmed_failures, level=logging.WARNING)

        except Exception as e:
            self._session_manager.update_status(session, AuthStatus.FAILED, error=str(e))
            log_auth_event("WORKER_EXCEPTION", session, message=str(e), traceback_str=traceback.format_exc(), level=logging.ERROR)
        
        finally:
            self._session_manager.mark_worker_finished(session)

    def _verify_client_status(self, result: Optional[Result]) -> VerifyResult:
        if not result or not result.success:
            return VerifyResult.VERIFY_ERROR
        
        auth_status = result.data.get("authStatus", 0) if result.data else 0
        
        if auth_status == 2:
            return VerifyResult.AUTHORIZED
        elif auth_status == 1:
            return VerifyResult.UNAUTHORIZED
        else:
            return VerifyResult.VERIFY_ERROR
