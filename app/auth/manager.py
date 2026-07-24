import re
import threading
import time
from typing import Tuple, Optional

from .session import AuthSession, AuthStatus

# Константы
FINISHED_SESSION_RETENTION_SECONDS = 300  # 5 минут хранения AUTHORIZED сессий

class AuthSessionManager:
    def __init__(self):
        self._sessions: dict[str, AuthSession] = {}
        self._lock = threading.RLock()

    @staticmethod
    def normalize_mac(mac: str) -> str:
        """Нормализует MAC-адрес к формату AA-BB-CC-DD-EE-FF"""
        clean = mac.replace(':', '').replace('-', '').replace('.', '').upper()
        
        if len(clean) != 12 or not re.match(r'^[0-9A-F]{12}$', clean):
            raise ValueError(f"Invalid MAC address format: {mac}")
        
        return '-'.join(clean[i:i+2] for i in range(0, 12, 2))

    def _get_session_key(self, site_id: str, client_mac: str) -> str:
        return f"{site_id}:{self.normalize_mac(client_mac)}"

    def create_or_get(self, site_id: str, client_mac: str, client_ip: str) -> Tuple[AuthSession, bool]:
        """
        Возвращает (AuthSession, is_new).
        
        Логика retention:
        - AUTHORIZED: блокирует повторный запуск на 5 минут
        - FAILED, RESET, EXPIRED: разрешают немедленный повторный запуск
        - Активная сессия или работающий worker: блокируют повторный запуск
        """
        norm_mac = self.normalize_mac(client_mac)
        session_key = self._get_session_key(site_id, norm_mac)

        with self._lock:
            now_mono = time.monotonic()
            
            if session_key in self._sessions:
                existing = self._sessions[session_key]
                
                # Если worker ещё работает или сессия активна - не создаём новую
                if not existing._worker_finished or existing.is_active():
                    return existing, False
                
                # Если сессия завершена
                if existing.is_finished():
                    # AUTHORIZED блокирует повторный запуск на 5 минут
                    if existing.status == AuthStatus.AUTHORIZED:
                        age = now_mono - existing._last_activity_monotonic
                        if age <= FINISHED_SESSION_RETENTION_SECONDS:
                            return existing, False
                    
                    # FAILED, RESET, EXPIRED разрешают немедленный повторный запуск
                    # Удаляем старую сессию и создаём новую
                    del self._sessions[session_key]

            # Создание новой сессии
            new_session = AuthSession(
                site_id=site_id,
                client_mac=norm_mac,
                client_ip=client_ip,
                _created_monotonic=now_mono,
                _last_activity_monotonic=now_mono
            )
            self._sessions[session_key] = new_session
            return new_session, True

    def get(self, session_id: str) -> Optional[AuthSession]:
        with self._lock:
            for session in self._sessions.values():
                if session.session_id == session_id:
                    return session
            return None

    def snapshot(self, session: AuthSession) -> dict:
        """Публичный снимок состояния сессии для Web-слоя"""
        with self._lock:
            return {
                "session_id": session.session_id,
                "status": session.status.value,
                "attempt": session.attempt,
                "last_error": session.last_error,
                "worker_finished": session._worker_finished,
                "confirmed_failures": session._confirmed_failures,
                "is_active": session.is_active(),
                "is_finished": session.is_finished(),
            }

    def mark_worker_started(self, session: AuthSession) -> None:
        with self._lock:
            session._worker_finished = False
            session.update_activity()

    def mark_worker_finished(self, session: AuthSession) -> None:
        with self._lock:
            session._worker_finished = True
            session.update_activity()

    def begin_attempt(self, session: AuthSession, attempt: int) -> None:
        with self._lock:
            session.attempt = attempt
            session.status = AuthStatus.AUTHORIZING
            session.last_error = ""
            session.update_activity()

    def update_status(self, session: AuthSession, new_status: AuthStatus, error: str = "") -> None:
        with self._lock:
            session.status = new_status
            session.last_error = error
            session.update_activity()

    def increment_confirmed_failure(self, session: AuthSession) -> int:
        with self._lock:
            session._confirmed_failures += 1
            session.update_activity()
            return session._confirmed_failures

    def get_confirmed_failures(self, session: AuthSession) -> int:
        with self._lock:
            return session._confirmed_failures
