"""Immutable contracts for Current Network State Foundation schema v1."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping


UTC = timezone.utc
SCHEMA_VERSION = 1
MAX_SQLITE_INTEGER = 9_223_372_036_854_775_807
SITE_ID_PATTERN = re.compile(r"[0-9a-f]{24}")
SCOPE_HASH_PATTERN = re.compile(r"[0-9a-f]{64}")
UTC_TIMESTAMP_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z"
)


class CurrentStateConfigError(ValueError):
    """Enabled Current State configuration is invalid."""


class CurrentStateValidationError(ValueError):
    """A model, storage, or query argument violates the v1 contract."""


class CurrentStateSchemaError(RuntimeError):
    """The existing on-disk database is not the exact schema-v1 contract."""


class CurrentStateStorageError(RuntimeError):
    """A sanitized Current State SQLite operation failed."""


@dataclass(frozen=True, slots=True, repr=False)
class CurrentStateConfig:
    enabled: bool
    db_path: str
    site_ids: tuple[str, ...]
    client_ssids: tuple[str, ...]
    client_initial_delay_seconds: float
    client_interval_seconds: float
    ap_initial_delay_seconds: float
    ap_interval_seconds: float
    request_timeout_seconds: float
    client_page_size: int
    client_max_pages: int
    client_max_rows: int
    ap_page_size: int
    ap_max_pages: int
    ap_max_rows: int
    client_fresh_max_age_seconds: int
    client_stale_max_age_seconds: int
    ap_fresh_max_age_seconds: int
    ap_stale_max_age_seconds: int
    history_retention_hours: int
    history_max_client_rows: int
    cleanup_initial_delay_seconds: float
    cleanup_interval_seconds: float
    cleanup_max_cycles_per_run: int
    cleanup_max_rows_per_transaction: int
    cleanup_max_duration_seconds: float
    sqlite_busy_timeout_ms: int
    shutdown_timeout_seconds: float
    other_sqlite_paths: tuple[str, ...] = ()

    def __repr__(self) -> str:
        return (
            "CurrentStateConfig("
            f"enabled={self.enabled!r}, db_path={self.db_path!r}, "
            f"site_count={len(self.site_ids)}, "
            f"ssid_count={len(self.client_ssids)}, "
            f"client_interval_seconds={self.client_interval_seconds!r}, "
            f"ap_interval_seconds={self.ap_interval_seconds!r})"
        )


@dataclass(frozen=True, slots=True)
class CurrentStateCycle:
    cycle_id: str
    kind: str
    site_id: str
    capture_started_at: str
    capture_finished_at: str
    complete: bool
    result: str
    source_scope_version: int
    source_scope_json: str
    source_scope_hash: str
    source_rows_reported: int | None
    items_seen: int
    items_stored: int
    items_skipped: int
    unidentified_count: int
    duplicate_identity_count: int
    unknown_status_count: int
    error_count: int
    data_quality_warning_count: int
    page_count: int
    failure_category: str | None
    duration_ms: int
    created_at: str


@dataclass(frozen=True, slots=True)
class CurrentClientState:
    cycle_id: str
    site_id: str
    observed_at: str
    client_mac: str
    name: str | None
    hostname: str | None
    device_type: str | None
    ip: str | None
    ssid: str
    ap_name: str | None
    ap_mac: str | None
    radio_id: int | None
    band: str | None
    channel: int | None
    rssi: int | None
    snr: int | None
    controller_uptime: int | None
    auth_status_code: int | None
    auth_classification: str
    controller_traffic_down: int | None
    controller_traffic_up: int | None
    controller_traffic_total: int | None
    active: bool
    wireless: bool


@dataclass(frozen=True, slots=True)
class CurrentApState:
    cycle_id: str
    site_id: str
    observed_at: str
    ap_mac: str
    name: str | None
    ip: str | None
    model: str | None
    firmware_version: str | None
    status_code: int | None
    status_classification: str
    last_seen_ms: int | None
    controller_uptime: int | None
    uptime_raw: str | None


@dataclass(frozen=True, slots=True)
class CurrentSnapshotMeta:
    cycle_id: str | None
    site_id: str
    kind: str
    evaluated_at: str
    observed_at: str | None
    capture_finished_at: str | None
    age_seconds: float | None
    freshness_status: str
    freshness_reason: str
    complete: bool
    source_scope_version: int | None
    source_scope_hash: str | None
    source_scope: Mapping[str, Any] | None
    latest_attempt_result: str | None
    latest_attempt_at: str | None
    latest_partial_cycle_id: str | None

    def __post_init__(self) -> None:
        if self.source_scope is not None:
            object.__setattr__(
                self,
                "source_scope",
                MappingProxyType(dict(self.source_scope)),
            )


@dataclass(frozen=True, slots=True)
class CurrentApBucket:
    ap_mac: str
    client_count: int


@dataclass(frozen=True, slots=True)
class CurrentClientSummary:
    snapshot: CurrentSnapshotMeta
    online_count: int | None
    authorized_count: int | None
    pending_count: int | None
    other_count: int | None
    unknown_count: int | None
    other_unknown_count: int | None
    ap_unknown_count: int | None
    devices_by_ap: tuple[CurrentApBucket, ...]


@dataclass(frozen=True, slots=True)
class CurrentApSummary:
    snapshot: CurrentSnapshotMeta
    ap_total: int | None
    online_count: int | None
    offline_count: int | None
    other_count: int | None
    unknown_count: int | None


@dataclass(frozen=True, slots=True)
class CurrentClientPage:
    snapshot: CurrentSnapshotMeta
    items: tuple[CurrentClientState, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class CurrentApPage:
    snapshot: CurrentSnapshotMeta
    items: tuple[CurrentApState, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class CurrentHistoryQuality:
    site_id: str
    from_utc: str
    to_utc: str
    source_scope_version: int
    source_scope_hash: str
    complete_cycle_count: int
    partial_cycle_count: int
    failed_cycle_count: int
    first_snapshot_at: str | None
    last_snapshot_at: str | None
    max_gap_seconds: float | None
    scope_changed: bool
    retention_pressure: bool
    coverage_status: str


@dataclass(frozen=True, slots=True)
class CleanupResult:
    deleted_cycles: int
    deleted_client_rows: int
    deleted_ap_rows: int
    duration_exhausted: bool
    interrupted: bool
    retention_pressure: bool


def format_utc(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise CurrentStateValidationError("UTC datetime must be timezone-aware")
    normalized = value.astimezone(UTC)
    return normalized.strftime("%Y-%m-%dT%H:%M:%S") + (
        f".{normalized.microsecond // 1000:03d}Z"
    )


def utc_now() -> str:
    return format_utc(datetime.now(UTC))


def parse_utc(value: Any, name: str = "timestamp") -> datetime:
    if not isinstance(value, str) or UTC_TIMESTAMP_PATTERN.fullmatch(value) is None:
        raise CurrentStateValidationError(
            f"{name} must use YYYY-MM-DDTHH:MM:SS.mmmZ"
        )
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError as exc:
        raise CurrentStateValidationError(f"{name} is invalid") from exc
    return parsed.replace(tzinfo=UTC)


def require_site_id(value: Any) -> str:
    if not isinstance(value, str) or SITE_ID_PATTERN.fullmatch(value) is None:
        raise CurrentStateValidationError("site_id is invalid")
    return value


def require_cycle_id(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 128:
        raise CurrentStateValidationError("cycle_id is invalid")
    return value


def require_nonnegative(value: Any, name: str, *, nullable: bool = False) -> int | None:
    if value is None and nullable:
        return None
    if type(value) is not int or not 0 <= value <= MAX_SQLITE_INTEGER:
        raise CurrentStateValidationError(f"{name} must be a non-negative INT64")
    return value
