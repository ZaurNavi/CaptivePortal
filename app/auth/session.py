import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional


DEFAULT_SESSION_TTL_SECONDS = 60.0


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


@dataclass
class AuthRun:
    run_number: int
    run_token: str = field(default_factory=lambda: str(uuid.uuid4()))
    retry_request_id: Optional[str] = None
    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    finished_at: Optional[datetime] = None
    final_state: Optional[str] = None
    final_reason: Optional[str] = None
    retryable: bool = False
    auth_attempt_count: int = 0
    worker_id: Optional[str] = None
    authorization_may_have_changed: bool = False
    worker_started: bool = False
    worker_finished: bool = False

    @property
    def active(self) -> bool:
        return self.finished_at is None

    def public_dict(self) -> dict:
        return {
            "run_number": self.run_number,
            "retry_request_id": self.retry_request_id,
            "started_at": self.started_at.isoformat(),
            "finished_at": (
                self.finished_at.isoformat()
                if self.finished_at is not None
                else None
            ),
            "final_state": self.final_state,
            "final_reason": self.final_reason,
            "retryable": self.retryable,
            "auth_attempt_count": self.auth_attempt_count,
            "worker_id": self.worker_id,
            "authorization_may_have_changed": (
                self.authorization_may_have_changed
            ),
        }


@dataclass
class AuthSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    site_id: str = ""
    client_mac: Optional[str] = None
    client_ip: Optional[str] = None

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    expires_at: datetime = field(
        default_factory=lambda: (
            datetime.now(timezone.utc)
            + timedelta(seconds=DEFAULT_SESSION_TTL_SECONDS)
        )
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    status: AuthStatus = AuthStatus.WAITING
    attempt: int = 0
    retryable: bool = False
    current_run_number: int = 0
    current_run_token: Optional[str] = None
    final_reason: Optional[str] = None
    runs: list[AuthRun] = field(default_factory=list)
    retry_request_runs: dict[str, int] = field(default_factory=dict)

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

    # Внутренние поля управления. Сохранены для совместимости с текущим
    # web-слоем; источником истины для worker является текущий AuthRun.
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
        if self.status in {
            AuthStatus.AUTHORIZED,
            AuthStatus.EXPIRED,
        }:
            return True
        return self.status == AuthStatus.FAILED and not self.retryable

    @property
    def terminal(self) -> bool:
        return self.is_finished()

    @property
    def authorized(self) -> bool:
        return self.status == AuthStatus.AUTHORIZED

    def current_run(self) -> Optional[AuthRun]:
        if self.current_run_number <= 0:
            return None
        for run in reversed(self.runs):
            if run.run_number == self.current_run_number:
                return run
        return None

    def update_activity(self) -> None:
        self.updated_at = datetime.now(timezone.utc)
        self._last_activity_monotonic = time.monotonic()

    def age_seconds(self) -> float:
        return time.monotonic() - self._created_monotonic

    def to_dict(self) -> dict:
        expires_at = self.expires_at.astimezone(timezone.utc).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z")
        progress = max(0, min(100, int(self.progress)))
        result = {
            # Canonical retry contract.
            "session_id": self.session_id,
            "state": self.status.value,
            "retryable": bool(self.retryable),
            "current_run_number": self.current_run_number,
            "final_reason": self.final_reason,
            "expires_at": expires_at,
            # Backward-compatible fields consumed by the current portal.
            "sessionId": self.session_id,
            "status": self.status.value,
            "attempt": self.attempt,
            "progress": progress,
            "authorized": self.authorized,
            "terminal": self.terminal,
            "authStatus": self.auth_status,
        }

        if self.last_error:
            result["message"] = self.last_error

        return result
