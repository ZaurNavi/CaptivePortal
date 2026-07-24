import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

class AuthStatus(Enum):
    PENDING = "PENDING"
    AUTHORIZING = "AUTHORIZING"
    VERIFYING = "VERIFYING"
    AUTHORIZED = "AUTHORIZED"
    RESETTING = "RESETTING"
    RESET = "RESET"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"  # Зарезервирован для будущих версий

@dataclass
class AuthSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    site_id: str = ""
    client_mac: str = ""
    client_ip: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    attempt: int = 0
    status: AuthStatus = AuthStatus.PENDING
    last_error: str = ""
    
    # Внутренние поля для управления состоянием
    _created_monotonic: float = field(default_factory=time.monotonic, repr=False)
    _last_activity_monotonic: float = field(default_factory=time.monotonic, repr=False)
    _worker_finished: bool = field(default=False, repr=False)
    _confirmed_failures: int = field(default=0, repr=False)

    def is_active(self) -> bool:
        return self.status in (
            AuthStatus.PENDING,
            AuthStatus.AUTHORIZING,
            AuthStatus.VERIFYING,
            AuthStatus.RESETTING
        )

    def is_finished(self) -> bool:
        return self.status in (
            AuthStatus.AUTHORIZED,
            AuthStatus.RESET,
            AuthStatus.FAILED,
            AuthStatus.EXPIRED
        )
    
    def update_activity(self) -> None:
        """Обновляет время последней активности"""
        self._last_activity_monotonic = time.monotonic()
