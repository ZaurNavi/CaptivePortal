import ipaddress
import re
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional, Tuple

from .session import AuthRun, AuthSession, AuthStatus


SESSION_TTL_SECONDS = 60.0
SESSION_RETRY_COOLDOWN_SECONDS = 5.0
FINISHED_SESSION_RETENTION_SECONDS = 300.0


class RetryOutcome(Enum):
    CREATED = "created"
    DUPLICATE = "duplicate"
    ACTIVE = "active"
    EXPIRED = "expired"
    NOT_FOUND = "not_found"
    NOT_RETRYABLE = "not_retryable"


@dataclass(frozen=True)
class RetryPreparation:
    outcome: RetryOutcome
    session: Optional[AuthSession] = None
    run_number: Optional[int] = None
    run_token: Optional[str] = None
    request_run_number: Optional[int] = None


class AuthSessionManager:
    def __init__(self):
        # Активная или последняя сессия по site_id + MAC/IP.
        self._sessions_by_key: dict[str, AuthSession] = {}

        # Быстрый поиск сессии для status endpoint и worker.
        self._sessions_by_id: dict[str, AuthSession] = {}

        self._session_locks: dict[str, threading.RLock] = {}
        self._lock = threading.RLock()

    @staticmethod
    def normalize_mac(mac: str) -> str:
        """Нормализует MAC к формату AA-BB-CC-DD-EE-FF."""
        if not isinstance(mac, str) or not mac.strip():
            raise ValueError("MAC address is required")

        clean = re.sub(r"[:.\-\s]", "", mac).upper()

        if not re.fullmatch(r"[0-9A-F]{12}", clean):
            raise ValueError(f"Invalid MAC address format: {mac}")

        return "-".join(
            clean[index:index + 2]
            for index in range(0, 12, 2)
        )

    @staticmethod
    def normalize_ip(client_ip: str) -> str:
        if not isinstance(client_ip, str) or not client_ip.strip():
            raise ValueError("client_ip is required")
        return str(ipaddress.ip_address(client_ip.strip()))

    @classmethod
    def get_session_key(
        cls,
        site_id: str,
        client_mac: Optional[str],
        client_ip: Optional[str] = None,
    ) -> str:
        if not isinstance(site_id, str) or not site_id.strip():
            raise ValueError("site_id is required")

        if client_mac:
            identity = f"mac:{cls.normalize_mac(client_mac)}"
        elif client_ip:
            identity = f"ip:{cls.normalize_ip(client_ip)}"
        else:
            raise ValueError("client_mac or client_ip is required")
        return f"{site_id.strip()}:{identity}"

    def create_or_get(
        self,
        site_id: str,
        client_mac: Optional[str],
        client_ip: Optional[str] = None,
        ap_mac: Optional[str] = None,
        ssid: Optional[str] = None,
        redirect_url: Optional[str] = None,
        radio_id: Optional[str] = None,
    ) -> Tuple[AuthSession, bool]:
        """
        Возвращает (session, created).

        Первый run создаётся вместе с сессией и получает run_number=1.
        Retryable failure переиспользует ту же сессию до исходного TTL.
        """
        normalized_mac = (
            self.normalize_mac(client_mac)
            if client_mac
            else None
        )
        normalized_ip = (
            self.normalize_ip(client_ip)
            if client_ip
            else None
        )
        session_key = self.get_session_key(
            site_id,
            normalized_mac,
            normalized_ip,
        )

        with self._lock:
            self._cleanup_locked()

            existing = self._sessions_by_key.get(session_key)

            if (
                existing is not None
                and self._is_expired_locked(existing)
            ):
                self._expire_locked(existing)
                self._detach_session_keys_locked(existing)
                existing = None

            if existing is not None:
                if (
                    existing.is_active()
                    or (
                        existing.status == AuthStatus.FAILED
                        and existing.retryable
                    )
                ):
                    return existing, False

                if not existing._worker_finished:
                    return existing, False

                finished_age = (
                    time.monotonic()
                    - existing._last_activity_monotonic
                )

                if finished_age < SESSION_RETRY_COOLDOWN_SECONDS:
                    return existing, False

                self._remove_session_locked(existing)

            now_monotonic = time.monotonic()
            now = datetime.now(timezone.utc)
            session = AuthSession(
                site_id=site_id.strip(),
                client_mac=normalized_mac,
                client_ip=normalized_ip,
                created_at=now,
                expires_at=(
                    now + timedelta(seconds=SESSION_TTL_SECONDS)
                ),
                updated_at=now,
                ap_mac=self._normalize_optional_mac(ap_mac),
                ssid=ssid or None,
                redirect_url=redirect_url or None,
                radio_id=radio_id or None,
                status=AuthStatus.WAITING,
                progress=0,
                _created_monotonic=now_monotonic,
                _last_activity_monotonic=now_monotonic,
            )
            self._create_run_locked(
                session,
                run_number=1,
                retry_request_id=None,
            )

            self._sessions_by_key[session_key] = session
            if normalized_ip:
                self._sessions_by_key[
                    self.get_session_key(
                        session.site_id,
                        None,
                        normalized_ip,
                    )
                ] = session
            self._sessions_by_id[session.session_id] = session
            self._session_locks[session.session_id] = threading.RLock()

            return session, True

    def get(self, session_id: str) -> Optional[AuthSession]:
        with self._lock:
            return self._sessions_by_id.get(session_id)

    def get_by_client(
        self,
        site_id: str,
        client_mac: str,
    ) -> Optional[AuthSession]:
        session_key = self.get_session_key(site_id, client_mac)

        with self._lock:
            return self._sessions_by_key.get(session_key)

    def snapshot(self, session_or_id) -> Optional[dict]:
        """Возвращает публичное состояние AuthSession."""
        with self._lock:
            session = self._resolve_session_locked(session_or_id)

            if session is None:
                return None

            return session.to_dict()

    def run_snapshot(
        self,
        session_or_id,
        run_number: int,
    ) -> Optional[dict]:
        with self._lock:
            session = self._resolve_session_locked(session_or_id)
            if session is None:
                return None
            run = self._find_run_locked(session, run_number)
            return run.public_dict() if run is not None else None

    def prepare_retry(
        self,
        session_id: str,
        retry_request_id: str,
    ) -> RetryPreparation:
        with self._lock:
            session = self._sessions_by_id.get(session_id)
            session_lock = self._session_locks.get(session_id)
        if session is None or session_lock is None:
            return RetryPreparation(RetryOutcome.NOT_FOUND)

        with session_lock:
            with self._lock:
                session = self._sessions_by_id.get(session_id)
                if session is None:
                    return RetryPreparation(RetryOutcome.NOT_FOUND)

                if self._is_expired_locked(session):
                    self._expire_locked(session)
                    return RetryPreparation(
                        RetryOutcome.EXPIRED,
                        session=session,
                    )

                prior_run_number = session.retry_request_runs.get(
                    retry_request_id
                )
                if prior_run_number is not None:
                    return RetryPreparation(
                        RetryOutcome.DUPLICATE,
                        session=session,
                        run_number=session.current_run_number,
                        run_token=session.current_run_token,
                        request_run_number=prior_run_number,
                    )

                if session.is_active():
                    session.retry_request_runs[
                        retry_request_id
                    ] = session.current_run_number
                    return RetryPreparation(
                        RetryOutcome.ACTIVE,
                        session=session,
                        run_number=session.current_run_number,
                        run_token=session.current_run_token,
                    )

                if (
                    session.status != AuthStatus.FAILED
                    or not session.retryable
                ):
                    return RetryPreparation(
                        RetryOutcome.NOT_RETRYABLE,
                        session=session,
                    )

                run_number = session.current_run_number + 1
                run = self._create_run_locked(
                    session,
                    run_number=run_number,
                    retry_request_id=retry_request_id,
                )
                session.retry_request_runs[
                    retry_request_id
                ] = run_number

                return RetryPreparation(
                    RetryOutcome.CREATED,
                    session=session,
                    run_number=run_number,
                    run_token=run.run_token,
                    request_run_number=run_number,
                )

    def owns_session(
        self,
        session_or_id,
        client_ip: Optional[str],
    ) -> bool:
        with self._lock:
            session = self._resolve_session_locked(session_or_id)
            if session is None or not session.client_ip or not client_ip:
                return False
            try:
                return (
                    self.normalize_ip(session.client_ip)
                    == self.normalize_ip(client_ip)
                )
            except ValueError:
                return False

    def claim_worker(
        self,
        session_or_id,
        run_number: Optional[int] = None,
        run_token: Optional[str] = None,
    ) -> bool:
        """Атомарно закрепляет worker за конкретным run."""
        with self._lock:
            session = self._resolve_session_locked(session_or_id)

            if session is None:
                return False

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
            if not self._run_matches_locked(
                session,
                run_number,
                run_token,
            ):
                return False

            run = self._find_run_locked(session, run_number)
            if (
                run is None
                or run.worker_started
                or not run.active
                or not session.is_active()
            ):
                return False

            run.worker_started = True
            run.worker_finished = False
            session._worker_started = True
            session._worker_finished = False
            session.update_activity()
            return True

    def mark_worker_started(
        self,
        session_or_id,
        run_number: Optional[int] = None,
        run_token: Optional[str] = None,
    ) -> bool:
        return self.claim_worker(
            session_or_id,
            run_number,
            run_token,
        )

    def set_worker_id(
        self,
        session_or_id,
        worker_id: str,
        *,
        run_number: int,
        run_token: str,
    ) -> bool:
        with self._lock:
            session = self._resolve_session_locked(session_or_id)
            if (
                session is None
                or not self._run_matches_locked(
                    session,
                    run_number,
                    run_token,
                )
            ):
                return False
            run = self._find_run_locked(session, run_number)
            if run is None:
                return False
            run.worker_id = worker_id
            session.update_activity()
            return True

    def mark_worker_finished(
        self,
        session_or_id,
        *,
        run_number: Optional[int] = None,
        run_token: Optional[str] = None,
    ) -> bool:
        with self._lock:
            session = self._resolve_session_locked(session_or_id)

            if session is None:
                return False

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
            run = self._find_run_locked(session, run_number)
            if run is None or run.run_token != run_token:
                return False

            run.worker_finished = True
            if self._run_identity_matches_locked(
                session,
                run_number,
                run_token,
            ):
                session._worker_finished = True
                session.update_activity()
                return True
            return False

    def current_run_matches(
        self,
        session_or_id,
        run_number: int,
        run_token: str,
    ) -> bool:
        with self._lock:
            session = self._resolve_session_locked(session_or_id)
            return (
                session is not None
                and self._run_matches_locked(
                    session,
                    run_number,
                    run_token,
                )
            )

    def current_run_identity_matches(
        self,
        session_or_id,
        run_number: int,
        run_token: str,
    ) -> bool:
        """Return whether a run is current, including after it finished."""
        with self._lock:
            session = self._resolve_session_locked(session_or_id)
            return (
                session is not None
                and self._run_identity_matches_locked(
                    session,
                    run_number,
                    run_token,
                )
            )

    def update_status(
        self,
        session_or_id,
        new_status: AuthStatus,
        error: Optional[str] = None,
        progress: Optional[int] = None,
        *,
        run_number: Optional[int] = None,
        run_token: Optional[str] = None,
    ) -> bool:
        with self._lock:
            session = self._resolve_session_locked(session_or_id)

            if session is None or not self._guard_matches_locked(
                session,
                run_number,
                run_token,
            ):
                return False

            session.status = new_status

            if error is not None:
                session.last_error = error or None

            if progress is not None:
                session.progress = self._clamp_progress(progress)

            session.update_activity()
            return True

    def set_attempt(
        self,
        session_or_id,
        attempt: int,
        *,
        run_number: Optional[int] = None,
        run_token: Optional[str] = None,
    ) -> bool:
        with self._lock:
            session = self._resolve_session_locked(session_or_id)

            if session is None or not self._guard_matches_locked(
                session,
                run_number,
                run_token,
            ):
                return False

            normalized_attempt = max(0, int(attempt))
            session.attempt = normalized_attempt
            run = session.current_run()
            if run is not None:
                run.auth_attempt_count = max(
                    run.auth_attempt_count,
                    normalized_attempt,
                )
            session.update_activity()
            return True

    def begin_attempt(
        self,
        session_or_id,
        attempt: int,
        progress: Optional[int] = None,
        *,
        run_number: Optional[int] = None,
        run_token: Optional[str] = None,
    ) -> bool:
        with self._lock:
            session = self._resolve_session_locked(session_or_id)

            if session is None or not self._guard_matches_locked(
                session,
                run_number,
                run_token,
            ):
                return False

            normalized_attempt = max(0, int(attempt))
            session.attempt = normalized_attempt
            session.status = AuthStatus.AUTHORIZING
            session.last_error = None
            run = session.current_run()
            if run is not None:
                run.auth_attempt_count = max(
                    run.auth_attempt_count,
                    normalized_attempt,
                )

            if progress is not None:
                session.progress = self._clamp_progress(progress)

            session.update_activity()
            return True

    def set_auth_status(
        self,
        session_or_id,
        auth_status: Optional[int],
        *,
        run_number: Optional[int] = None,
        run_token: Optional[str] = None,
    ) -> bool:
        with self._lock:
            session = self._resolve_session_locked(session_or_id)

            if session is None or not self._guard_matches_locked(
                session,
                run_number,
                run_token,
            ):
                return False

            session.auth_status = auth_status
            session.update_activity()
            return True

    def set_progress(
        self,
        session_or_id,
        progress: int,
        *,
        run_number: Optional[int] = None,
        run_token: Optional[str] = None,
    ) -> bool:
        with self._lock:
            session = self._resolve_session_locked(session_or_id)

            if session is None or not self._guard_matches_locked(
                session,
                run_number,
                run_token,
            ):
                return False

            session.progress = self._clamp_progress(progress)
            session.update_activity()
            return True

    def set_client_mac(
        self,
        session_or_id,
        client_mac: str,
        *,
        run_number: int,
        run_token: str,
    ) -> bool:
        normalized_mac = self.normalize_mac(client_mac)
        with self._lock:
            session = self._resolve_session_locked(session_or_id)
            if (
                session is None
                or not self._run_matches_locked(
                    session,
                    run_number,
                    run_token,
                )
            ):
                return False

            old_key = self.get_session_key(
                session.site_id,
                session.client_mac,
                session.client_ip,
            )
            new_key = self.get_session_key(
                session.site_id,
                normalized_mac,
                session.client_ip,
            )
            # Keep the IP alias so a portal entry that still has no MAC
            # reuses this same session after identity resolution.
            self._sessions_by_key[old_key] = session
            self._sessions_by_key[new_key] = session
            session.client_mac = normalized_mac
            session.update_activity()
            return True

    def mark_authorization_may_have_changed(
        self,
        session_or_id,
        *,
        run_number: int,
        run_token: str,
    ) -> bool:
        with self._lock:
            session = self._resolve_session_locked(session_or_id)
            if (
                session is None
                or not self._run_matches_locked(
                    session,
                    run_number,
                    run_token,
                )
            ):
                return False
            run = self._find_run_locked(session, run_number)
            if run is None:
                return False
            run.authorization_may_have_changed = True
            session.update_activity()
            return True

    def finish_run(
        self,
        session_or_id,
        *,
        run_number: int,
        run_token: str,
        final_state: AuthStatus,
        final_reason: str,
        retryable: bool,
        error: Optional[str] = None,
        progress: int = 100,
    ) -> bool:
        with self._lock:
            session = self._resolve_session_locked(session_or_id)
            if (
                session is None
                or not self._run_matches_locked(
                    session,
                    run_number,
                    run_token,
                )
            ):
                return False
            run = self._find_run_locked(session, run_number)
            if run is None:
                return False

            now = datetime.now(timezone.utc)
            run.finished_at = now
            run.final_state = final_state.value
            run.final_reason = final_reason
            run.retryable = bool(retryable)
            session.status = final_state
            session.final_reason = final_reason
            session.retryable = bool(retryable)
            session.progress = self._clamp_progress(progress)
            if error is not None:
                session.last_error = error or None
            session.update_activity()
            return True

    def fail(
        self,
        session_or_id,
        error: str,
        *,
        final_reason: str = "WORKER_EXCEPTION",
        retryable: bool = False,
        run_number: Optional[int] = None,
        run_token: Optional[str] = None,
    ) -> bool:
        with self._lock:
            session = self._resolve_session_locked(session_or_id)
            if session is None:
                return False
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
            return False
        return self.finish_run(
            session_or_id,
            run_number=run_number,
            run_token=run_token,
            final_state=AuthStatus.FAILED,
            final_reason=final_reason,
            retryable=retryable,
            error=error,
        )

    def is_expired(self, session_or_id) -> bool:
        with self._lock:
            session = self._resolve_session_locked(session_or_id)

            if session is None:
                return True

            return self._is_expired_locked(session)

    def expire_if_needed(
        self,
        session_or_id,
        *,
        run_number: Optional[int] = None,
        run_token: Optional[str] = None,
    ) -> bool:
        with self._lock:
            session = self._resolve_session_locked(session_or_id)

            if session is None:
                return True

            if not self._is_expired_locked(session):
                return False

            if not self._guard_matches_locked(
                session,
                run_number,
                run_token,
            ):
                return True

            self._expire_locked(session)
            return True

    def cleanup(self) -> int:
        """Удаляет старые завершённые сессии."""
        with self._lock:
            return self._cleanup_locked()

    def _cleanup_locked(self) -> int:
        now = time.monotonic()
        expired_sessions: list[AuthSession] = []

        for session in self._sessions_by_id.values():
            if self._is_expired_locked(session):
                self._expire_locked(session)
            if not session.is_finished():
                continue

            finished_age = now - session._last_activity_monotonic

            if finished_age >= FINISHED_SESSION_RETENTION_SECONDS:
                expired_sessions.append(session)

        for session in expired_sessions:
            self._remove_session_locked(session)

        return len(expired_sessions)

    def _detach_session_keys_locked(
        self,
        session: AuthSession,
    ) -> None:
        for session_key, mapped in list(
            self._sessions_by_key.items()
        ):
            if mapped is session:
                self._sessions_by_key.pop(session_key, None)

    def _remove_session_locked(self, session: AuthSession) -> None:
        self._detach_session_keys_locked(session)
        self._sessions_by_id.pop(session.session_id, None)
        self._session_locks.pop(session.session_id, None)

    def _resolve_session_locked(
        self,
        session_or_id,
    ) -> Optional[AuthSession]:
        if isinstance(session_or_id, AuthSession):
            return self._sessions_by_id.get(session_or_id.session_id)

        if isinstance(session_or_id, str):
            return self._sessions_by_id.get(session_or_id)

        return None

    def _create_run_locked(
        self,
        session: AuthSession,
        *,
        run_number: int,
        retry_request_id: Optional[str],
    ) -> AuthRun:
        run = AuthRun(
            run_number=run_number,
            run_token=str(uuid.uuid4()),
            retry_request_id=retry_request_id,
        )
        session.runs.append(run)
        session.current_run_number = run_number
        session.current_run_token = run.run_token
        session.status = AuthStatus.WAITING
        session.retryable = False
        session.final_reason = None
        session.attempt = 0
        session.auth_status = None
        session.last_error = None
        session.progress = 0
        session._worker_started = False
        session._worker_finished = False
        session.update_activity()
        return run

    @staticmethod
    def _find_run_locked(
        session: AuthSession,
        run_number: int,
    ) -> Optional[AuthRun]:
        for run in reversed(session.runs):
            if run.run_number == run_number:
                return run
        return None

    @staticmethod
    def _run_identity_matches_locked(
        session: AuthSession,
        run_number: int,
        run_token: Optional[str],
    ) -> bool:
        return (
            run_token is not None
            and session.current_run_number == run_number
            and session.current_run_token == run_token
        )

    def _run_matches_locked(
        self,
        session: AuthSession,
        run_number: int,
        run_token: Optional[str],
    ) -> bool:
        if not self._run_identity_matches_locked(
            session,
            run_number,
            run_token,
        ):
            return False
        run = self._find_run_locked(session, run_number)
        return run is not None and run.finished_at is None

    def _guard_matches_locked(
        self,
        session: AuthSession,
        run_number: Optional[int],
        run_token: Optional[str],
    ) -> bool:
        if run_number is None and run_token is None:
            return True
        if run_number is None or run_token is None:
            return False
        return self._run_matches_locked(
            session,
            run_number,
            run_token,
        )

    @staticmethod
    def _is_expired_locked(session: AuthSession) -> bool:
        return (
            time.monotonic() - session._created_monotonic
            >= SESSION_TTL_SECONDS
        )

    def _expire_locked(self, session: AuthSession) -> None:
        if session.status == AuthStatus.EXPIRED:
            return
        run = session.current_run()
        now = datetime.now(timezone.utc)
        if run is not None and run.finished_at is None:
            run.finished_at = now
            run.final_state = AuthStatus.EXPIRED.value
            run.final_reason = "SESSION_EXPIRED"
            run.retryable = False
        session.status = AuthStatus.EXPIRED
        session.retryable = False
        session.final_reason = "SESSION_EXPIRED"
        session.last_error = "Authorization session expired."
        session.progress = 100
        session.update_activity()

    @classmethod
    def _normalize_optional_mac(
        cls,
        mac: Optional[str],
    ) -> Optional[str]:
        if not mac:
            return None

        try:
            return cls.normalize_mac(mac)
        except ValueError:
            # ap_mac не является обязательным параметром сессии.
            return mac

    @staticmethod
    def _clamp_progress(progress: int) -> int:
        return max(0, min(100, int(progress)))
