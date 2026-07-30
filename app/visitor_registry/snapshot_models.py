"""Immutable contracts for authorized-client snapshot collection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class SnapshotSubmitOutcome(Enum):
    ACCEPTED = "ACCEPTED"
    DUPLICATE_SUPPRESSED = "DUPLICATE_SUPPRESSED"
    QUEUE_REJECTED = "QUEUE_REJECTED"
    DISABLED = "DISABLED"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID_CONTEXT = "INVALID_CONTEXT"
    SHUTTING_DOWN = "SHUTTING_DOWN"


@dataclass(frozen=True)
class AuthorizedClientAuthContext:
    client_ip: str | None
    portal_ssid: str | None
    portal_ap_mac: str | None
    portal_radio_id: str | None
    auth_run_number: int
    authorization_attempt: int
    auth_final_reason: str
    retry_request_id: str | None


@dataclass(frozen=True)
class AuthorizedClientSnapshotRequest:
    auth_session_id: str
    site_id: str
    requested_mac: str
    authorized_at: datetime
    auth_context: AuthorizedClientAuthContext


@dataclass(frozen=True)
class NormalizedSnapshotJob:
    snapshot_id: str
    idempotency_key: str
    auth_session_id: str
    site_id: str
    requested_mac: str
    authorized_at: datetime
    auth_context: AuthorizedClientAuthContext
    submitted_monotonic: float


@dataclass(frozen=True)
class NormalizedClientSnapshot:
    client: dict[str, Any]
    raw_controller_snapshot: dict[str, Any]
    redacted_field_count: int


@dataclass(frozen=True)
class ProviderFailure:
    failure_category: str
    retryable: bool
    http_status: int | None
    error_code: int | str | None
    message: str
