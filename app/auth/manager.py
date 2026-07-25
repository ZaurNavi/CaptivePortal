import re
import threading
import time
from typing import Optional, Tuple

from .session import AuthSession, AuthStatus


SESSION_TTL_SECONDS = 60.0
SESSION_RETRY_COOLDOWN_SECONDS = 5.0
FINISHED_SESSION_RETENTION_SECONDS = 300.0


class AuthSessionManager:
    def __init__(self):
        # Активная или последняя сессия по ключу site_id + MAC.
        self._sessions_by_key: dict[str, AuthSession] = {}

        # Быстрый поиск сессии для status endpoint и worker.
        self._sessions_by_id: dict[str, AuthSession] = {}

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

    @classmethod
    def get_session_key(cls, site_id: str, client_mac: str) -> str:
        if not isinstance(site_id, str) or not site_id.strip():
            raise ValueError("site_id is required")

        normalized_mac = cls.normalize_mac(client_mac)
        return f"{site_id.strip()}:{normalized_mac}"

    def create_or_get(
        self,
        site_id: str,
        client_mac: str,
        client_ip: Optional[str] = None,
        ap_mac: Optional[str] = None,
        ssid: Optional[str] = None,
        redirect_url: Optional[str] = None,
        radio_id: Optional[str] = None,
    ) -> Tuple[AuthSession, bool]:
        """
        Возвращает (session, created).

        Правила:
        - активная сессия переиспользуется;
        - для активной сессии второй worker не создаётся;
        - завершённая сессия удерживается в течение cooldown;
        - после cooldown создаётся новая сессия;
        - старые завершённые сессии периодически очищаются.
        """
        normalized_mac = self.normalize_mac(client_mac)
        session_key = self.get_session_key(site_id, normalized_mac)

        with self._lock:
            self._cleanup_locked()

            existing = self._sessions_by_key.get(session_key)

            if existing is not None:
                if existing.is_active():
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

            now = time.monotonic()

            session = AuthSession(
                site_id=site_id.strip(),
                client_mac=normalized_mac,
                client_ip=client_ip or None,
                ap_mac=self._normalize_optional_mac(ap_mac),
                ssid=ssid or None,
                redirect_url=redirect_url or None,
                radio_id=radio_id or None,
                status=AuthStatus.WAITING,
                progress=0,
                _created_monotonic=now,
                _last_activity_monotonic=now,
            )

            self._sessions_by_key[session_key] = session
            self._sessions_by_id[session.session_id] = session

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

    def claim_worker(self, session_or_id) -> bool:
        """
        Атомарно закрепляет worker за сессией.

        Возвращает False, если worker уже был запущен или сессия завершена.
        """
        with self._lock:
            session = self._resolve_session_locked(session_or_id)

            if session is None:
                return False

            if session._worker_started:
                return False

            if session.is_finished():
                return False

            session._worker_started = True
            session._worker_finished = False
            session.update_activity()
            return True

    def mark_worker_started(self, session_or_id) -> bool:
        """Совместимый alias для существующего web-слоя."""
        return self.claim_worker(session_or_id)

    def mark_worker_finished(self, session_or_id) -> None:
        with self._lock:
            session = self._resolve_session_locked(session_or_id)

            if session is None:
                return

            session._worker_finished = True
            session.update_activity()

    def update_status(
        self,
        session_or_id,
        new_status: AuthStatus,
        error: Optional[str] = None,
        progress: Optional[int] = None,
    ) -> bool:
        with self._lock:
            session = self._resolve_session_locked(session_or_id)

            if session is None:
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
    ) -> bool:
        with self._lock:
            session = self._resolve_session_locked(session_or_id)

            if session is None:
                return False

            session.attempt = max(0, int(attempt))
            session.update_activity()
            return True

    def begin_attempt(
        self,
        session_or_id,
        attempt: int,
        progress: Optional[int] = None,
    ) -> bool:
        with self._lock:
            session = self._resolve_session_locked(session_or_id)

            if session is None:
                return False

            session.attempt = max(0, int(attempt))
            session.status = AuthStatus.AUTHORIZING
            session.last_error = None

            if progress is not None:
                session.progress = self._clamp_progress(progress)

            session.update_activity()
            return True

    def set_auth_status(
        self,
        session_or_id,
        auth_status: Optional[int],
    ) -> bool:
        with self._lock:
            session = self._resolve_session_locked(session_or_id)

            if session is None:
                return False

            session.auth_status = auth_status
            session.update_activity()
            return True

    def set_progress(
        self,
        session_or_id,
        progress: int,
    ) -> bool:
        with self._lock:
            session = self._resolve_session_locked(session_or_id)

            if session is None:
                return False

            session.progress = self._clamp_progress(progress)
            session.update_activity()
            return True

    def fail(
        self,
        session_or_id,
        error: str,
    ) -> bool:
        return self.update_status(
            session_or_id,
            AuthStatus.FAILED,
            error=error,
            progress=100,
        )

    def is_expired(self, session_or_id) -> bool:
        with self._lock:
            session = self._resolve_session_locked(session_or_id)

            if session is None:
                return True

            return (
                time.monotonic() - session._created_monotonic
                >= SESSION_TTL_SECONDS
            )

    def expire_if_needed(self, session_or_id) -> bool:
        """
        Помечает сессию EXPIRED, если TTL истёк до recovery RESETTING.
        """
        with self._lock:
            session = self._resolve_session_locked(session_or_id)

            if session is None:
                return True

            expired = (
                time.monotonic() - session._created_monotonic
                >= SESSION_TTL_SECONDS
            )

            if not expired:
                return False

            # Если recovery уже начался, даём завершить /unauth.
            if session.status == AuthStatus.RESETTING:
                return False

            if not session.is_finished():
                session.status = AuthStatus.EXPIRED
                session.last_error = "Authorization session expired."
                session.progress = 100
                session.update_activity()

            return True

    def cleanup(self) -> int:
        """Удаляет старые завершённые сессии."""
        with self._lock:
            return self._cleanup_locked()

    def _cleanup_locked(self) -> int:
        now = time.monotonic()
        expired_sessions: list[AuthSession] = []

        for session in self._sessions_by_id.values():
            if not session.is_finished():
                continue

            finished_age = now - session._last_activity_monotonic

            if finished_age >= FINISHED_SESSION_RETENTION_SECONDS:
                expired_sessions.append(session)

        for session in expired_sessions:
            self._remove_session_locked(session)

        return len(expired_sessions)

    def _remove_session_locked(self, session: AuthSession) -> None:
        session_key = self.get_session_key(
            session.site_id,
            session.client_mac,
        )

        current = self._sessions_by_key.get(session_key)

        if current is session:
            self._sessions_by_key.pop(session_key, None)

        self._sessions_by_id.pop(session.session_id, None)

    def _resolve_session_locked(
        self,
        session_or_id,
    ) -> Optional[AuthSession]:
        if isinstance(session_or_id, AuthSession):
            return session_or_id

        if isinstance(session_or_id, str):
            return self._sessions_by_id.get(session_or_id)

        return None

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
