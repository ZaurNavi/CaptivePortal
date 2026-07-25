import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class AuthStatus(Enum):
    WAITING = "WAITING"
    AUTHORIZING = "AUTHORIZING"
    VERIFYING = "VERIFYING"
    AUTHORIZED = "AUTHORIZED"
    RESETTING = "RESETTING"
    RESET = "RESET"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


ACTIVE_STATUSES = {
    AuthStatus.WAITING,
    AuthStatus.AUTHORIZING,
    AuthStatus.VERIFYING,
    AuthStatus.RESETTING,
}

TERMINAL_STATUSES = {
    AuthStatus.AUTHORIZED,
    AuthStatus.RESET,
    AuthStatus.FAILED,
    AuthStatus.EXPIRED,
}


@dataclass
class AuthSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    site_id: str = ""
    client_mac: str = ""
    client_ip: Optional[str] = None

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    status: AuthStatus = AuthStatus.WAITING
    attempt: int = 0

    # Последний реальный authStatus, полученный от Omada.
    auth_status: Optional[int] = None

    # Текст последней ошибки.
    last_error: Optional[str] = None

    # Значение для отображения frontend.
    progress: int = 0

    # Дополнительные параметры Omada.
    ap_mac: Optional[str] = None
    ssid: Optional[str] = None
    redirect_url: Optional[str] = None
    radio_id: Optional[str] = None

    # Внутренние поля управления.
    _created_monotonic: float = field(
        default_factory=time.monotonic,
        repr=False,
    )
    _last_activity_monotonic: float = field(
        default_factory=time.monotonic,
        repr=False,
    )
    _worker_started: bool = field(
        default=False,
        repr=False,
    )
    _worker_finished: bool = field(
        default=False,
        repr=False,
    )

    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    def is_finished(self) -> bool:
        return self.status in TERMINAL_STATUSES

    @property
    def terminal(self) -> bool:
        return self.is_finished()

    @property
    def authorized(self) -> bool:
        return self.status == AuthStatus.AUTHORIZED

    def update_activity(self) -> None:
        self.updated_at = datetime.now(timezone.utc)
        self._last_activity_monotonic = time.monotonic()

    def age_seconds(self) -> float:
        return time.monotonic() - self._created_monotonic

    def to_dict(self) -> dict:
        result = {
            "sessionId": self.session_id,
            "status": self.status.value,
            "attempt": self.attempt,
            "progress": max(0, min(100, int(self.progress))),
            "authorized": self.authorized,
            "terminal": self.terminal,
            "authStatus": self.auth_status,
        }

        if self.last_error:
            result["message"] = self.last_error

        return result
