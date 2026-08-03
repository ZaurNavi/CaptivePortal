from __future__ import annotations

from typing import Protocol
from app.models.result import Result
from datetime import datetime
from .models import ProtectionDecision


class PendingClientSessionProvider(Protocol):
    def list_active_clients(
        self,
        *,
        site_id: str,
        page: int,
        page_size: int,
        timeout_seconds: float,
    ) -> Result:
        ...

    def get_pending_client_state(
        self,
        *,
        site_id: str,
        client_mac: str,
        timeout_seconds: float,
    ) -> Result:
        ...

    def reconnect_client(
        self,
        *,
        site_id: str,
        client_mac: str,
        timeout_seconds: float,
    ) -> Result:
        ...


class PendingSessionProtection(Protocol):
    def check(
        self,
        *,
        site_id: str,
        client_mac: str,
        now: datetime,
        grace_seconds: float,
    ) -> ProtectionDecision:
        ...
