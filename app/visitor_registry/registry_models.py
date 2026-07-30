"""Value objects for Visitor Device Registry schema version 1."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


REGISTRY_SCHEMA_VERSION = 1
CHECKPOINT_WINDOW_BYTES = 2048
MAX_SQLITE_INTEGER = 9_223_372_036_854_775_807

SKIP_REASONS = frozenset({
    "missing_required_field",
    "invalid_field_type",
    "invalid_field_range",
    "invalid_field_format",
    "invalid_field_value",
    "client_mac_mismatch",
    "snapshot_id_mismatch",
    "unsupported_schema_version",
})


class RegistryConfigError(ValueError):
    """The enabled Registry configuration is unsafe or invalid."""


class RegistrySchemaError(RuntimeError):
    """The existing SQLite schema cannot be used safely."""


class RegistryUnavailableError(RuntimeError):
    """The Registry cannot continue without operator intervention."""


class DecisionKind(Enum):
    ADVANCE = "advance"
    STORE = "store"
    SKIP = "skip"


class ApplyOutcome(Enum):
    ADVANCED = "advanced"
    STORED = "stored"
    SKIPPED = "skipped"
    DUPLICATE = "duplicate"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class RegistryConfig:
    enabled: bool
    db_path: str
    source_log_path: str
    source_backup_count: int
    timezone_name: str
    scan_interval_seconds: float
    shutdown_timeout_seconds: float
    max_line_bytes: int


@dataclass(frozen=True)
class ReaderState:
    source_identity: str
    source_path: str
    source_offset: int
    last_observed_size: int | None
    source_checkpoint: str | None
    retired_completed: bool
    missing_warning_emitted: bool


@dataclass(frozen=True)
class SourceLineRecord:
    source_identity: str
    source_path: str
    source_offset_start: int
    source_offset_end: int
    last_observed_size: int
    source_checkpoint: str
    processing_now: str


@dataclass(frozen=True)
class RegistrySnapshot:
    snapshot_id: str
    device_id: str
    mac: str
    event_sha256: str
    schema_version: int
    auth_session_id: str
    site_id: str
    requested_mac: str
    authorized_at: str
    captured_at: str
    attempts: int | None
    queue_delay_ms: int | None
    request_duration_ms: int | None
    snapshot_lag_ms: int | None
    auth_final_reason: str
    auth_run_number: int
    authorization_attempt: int
    retry_request_id: str | None
    portal_client_ip: str | None
    portal_ssid: str | None
    portal_ap_mac: str | None
    portal_radio_id: str | None
    controller_client_id: str | None
    name: str | None
    hostname: str | None
    system_name: str | None
    device_type: str | None
    ip: str | None
    ssid: str | None
    ap_name: str | None
    ap_mac: str | None
    radio_id: int | None
    channel: int | None
    rssi: int | None
    snr: int | None
    traffic_down: int | None
    traffic_up: int | None
    uptime: int | None
    controller_last_seen_ms: int | None
    active: bool | None
    auth_status: int | None
    auth_context_json: str
    client_json: str
    raw_controller_snapshot_json: str


@dataclass(frozen=True)
class RegistryEventDecision:
    kind: DecisionKind
    snapshot_id: str | None = None
    event_sha256: str | None = None
    skip_reason: str | None = None
    snapshot: RegistrySnapshot | None = None
    warning_reason: str | None = None


@dataclass(frozen=True)
class ApplyResult:
    outcome: ApplyOutcome
    snapshot_id: str | None = None
    device_id: str | None = None
    skip_reason: str | None = None
    device_created: bool | None = None


@dataclass(frozen=True)
class ScanResult:
    complete: bool
    pending_partial_line: bool = False
    reason: str | None = None
    processed_line_count: int = 0


@dataclass(frozen=True)
class RegistryStatus:
    configured_enabled: bool
    database_exists: bool
    database_ready: bool
    schema_version: int | None
    registry_state: str
    state_reason: str | None
    initial_backfill_completed: bool
    initial_backfill_completed_at: str | None
    last_successful_scan_at: str | None
    last_snapshot_stored_at: str | None
    reader_states: tuple[dict[str, Any], ...]
