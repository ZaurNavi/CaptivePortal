from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple, Mapping
from datetime import datetime


@dataclass(frozen=True)
class PendingClientObservation:
    mac: str
    wireless: bool
    active: bool
    auth_status: int
    uptime: int
    ssid: str
    blocked: bool
    client_ip: Optional[str]
    ap_mac: Optional[str]
    radio_id: Optional[int]
    channel: Optional[int]
    rssi: Optional[int]
    snr: Optional[int]


@dataclass(frozen=True)
class PendingClientCandidate:
    observation: PendingClientObservation
    list_uptime: int


@dataclass(frozen=True)
class ClassificationResult:
    clients_rows_received: int
    clients_valid: int
    clients_invalid: int
    duplicate_mac_count: int
    wireless_active_count: int
    wired_or_non_wireless_count: int
    authorized_active_count: int
    unauthorized_active_count: int
    unknown_auth_status_count: int
    below_threshold_count: int
    ssid_not_allowed_count: int
    blocked_count: int
    initial_candidate_count: int
    auth_status_counts: Mapping[str, int]
    candidates: Tuple[PendingClientCandidate, ...]


@dataclass(frozen=True)
class PaginationResult:
    clients: Tuple[dict, ...]
    inventory_complete: bool
    scan_result: str  # success | partial | failed
    pages_fetched: int
    controller_total_rows: Optional[int]
    failure_reason: Optional[str]


@dataclass(frozen=True)
class ProtectionDecision:
    protected: bool
    reason: Optional[str] = None
    observed_at: Optional[datetime] = None


@dataclass
class PendingScanSummary:
    scan_id: str
    started_at: str
    finished_at: str
    duration_ms: int
    site_id: str
    scan_result: str
    inventory_complete: bool = True

    pages_fetched: int = 0
    controller_total_rows: Optional[int] = None

    clients_rows_received: int = 0
    clients_valid: int = 0
    clients_invalid: int = 0
    duplicate_mac_count: int = 0

    wireless_active_count: int = 0
    wired_or_non_wireless_count: int = 0
    authorized_active_count: int = 0
    unauthorized_active_count: int = 0
    unknown_auth_status_count: int = 0

    below_threshold_count: int = 0
    ssid_not_allowed_count: int = 0
    blocked_count: int = 0
    initial_candidate_count: int = 0

    local_protected_count: int = 0
    preflight_rejected_count: int = 0
    final_eligible_count: int = 0

    reconnect_attempted_count: int = 0
    reconnect_confirmed_count: int = 0
    reconnect_unconfirmed_count: int = 0
    action_error_count: int = 0
    rate_limited_count: int = 0
    action_limit_count: int = 0

    auth_status_counts: dict[str, int] = field(default_factory=dict)
