"""Immutable contracts for Visit Lifecycle schema version 2."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.common.mac import format_mac_colon


SCHEMA_VERSION = 2
MAX_SQLITE_INTEGER = 9_223_372_036_854_775_807


class VisitLifecycleConfigError(ValueError):
    """Visit Lifecycle configuration is invalid or unsafe."""


class VisitValidationError(ValueError):
    """A write-side Visit Lifecycle contract is invalid."""


class VisitQueryValidationError(ValueError):
    """A read-side Visit Lifecycle query is invalid."""


class VisitSchemaError(RuntimeError):
    """The Visit database schema cannot be used safely."""


class VisitStorageCategory(Enum):
    BUSY = "busy"
    FULL = "full"
    IO_ERROR = "io_error"
    CORRUPT = "corrupt"
    CONSTRAINT = "constraint"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class VisitWriterContention:
    """Safe immutable snapshot of process-local writer contention."""

    holder_operation: str | None = None
    holder_age_ms: int | None = None
    foreground_queue_depth: int = 0
    background_queue_depth: int = 0
    waiter_operation: str | None = None
    waiter_wait_ms: int | None = None


class VisitStorageError(RuntimeError):
    def __init__(
        self,
        category: VisitStorageCategory,
        message: str = "Visit storage operation failed",
        *,
        operation: str | None = None,
        lock_wait_ms: int | None = None,
        contention_layer: str | None = None,
        contention: VisitWriterContention | None = None,
    ):
        super().__init__(message)
        self.category = category
        self.operation = operation
        self.lock_wait_ms = lock_wait_ms
        self.contention_layer = contention_layer
        self.contention = contention


@dataclass(frozen=True)
class VisitLifecycleConfig:
    enabled: bool
    db_path: str
    webhook_source: str
    scan_interval_seconds: float
    reconcile_interval_seconds: float
    max_line_bytes: int
    reader_max_lines_per_scan: int
    reader_max_bytes_per_scan: int
    reader_max_duration_seconds: float
    reconcile_batch_size: int
    pending_offline_batch_size: int
    offline_match_grace_seconds: float
    start_writer_slot_wait_ms: int
    reader_writer_slot_wait_ms: int
    reconciliation_writer_slot_wait_ms: int
    sqlite_busy_timeout_ms: int
    start_max_attempts: int
    start_total_budget_ms: int
    shutdown_timeout_seconds: float
    max_offline_clock_skew_seconds: float
    max_reported_duration_drift_seconds: float


@dataclass(frozen=True)
class VisitStartRequest:
    auth_session_id: str
    site_id: str
    client_mac: str
    authorized_at: datetime
    auth_run_number: int
    authorization_attempt: int | None
    final_reason: str
    client_ip: str | None
    portal_ssid: str | None
    portal_ap_mac: str | None
    portal_radio_id: int | str | None


@dataclass(frozen=True)
class NormalizedVisitStart:
    auth_session_id: str
    site_id: str
    client_mac: str
    authorized_at: str
    auth_run_number: int
    authorization_attempt: int | None
    final_reason: str
    client_ip: str | None
    portal_ssid: str | None
    portal_ap_mac: str | None
    portal_radio_id: int | None


@dataclass(frozen=True)
class VisitStartOutcome:
    status: str
    visit_id: str | None = None
    created: bool = False
    authorization_attached: bool = False
    storage_category: str | None = None


@dataclass(frozen=True)
class VisitRecord:
    visit_id: str
    site_id: str
    client_mac: str
    device_id: str | None
    initial_snapshot_id: str | None
    start_auth_session_id: str
    start_auth_run_number: int
    start_final_reason: str
    link_reconcile_attempted_at: str | None
    link_reconcile_next_at: str | None
    link_reconcile_attempt_count: int
    started_at: str
    closed_at: str | None
    status: str
    close_reason: str | None
    close_time_source: str | None
    start_ip: str | None
    start_ssid: str | None
    start_ap_mac: str | None
    final_ip: str | None
    final_ssid: str | None
    final_ap_mac: str | None
    reported_connected_seconds: int | None
    reported_traffic_total_bytes: int | None
    reported_traffic_up_bytes: int | None
    reported_traffic_down_bytes: int | None
    duration_seconds: int | None
    offline_event_id: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class VisitSourceEventRecord:
    event_id: str
    event_type: str
    site_id: str | None
    client_mac: str | None
    controller_event_at: str | None
    received_at: str | None
    client_ip: str | None
    ssid: str | None
    ap_mac: str | None
    reported_connected_seconds: int | None
    reported_traffic_total_bytes: int | None
    processing_result: str
    visit_id: str | None
    reason: str | None
    first_processed_at: str
    processed_at: str
    pending_until: str | None


@dataclass(frozen=True)
class OfflineEvidence:
    event_id: str | None
    site_id: str | None
    client_mac: str | None
    controller_event_at: str | None
    received_at: str | None
    client_ip: str | None
    ssid: str | None
    ap_mac: str | None
    reported_connected_seconds: int | None
    reported_traffic_total_bytes: int | None
    invalid_reason: str | None = None


@dataclass(frozen=True)
class ReaderCheckpoint:
    checkpoint_offset: int
    checkpoint_length: int
    checkpoint_sha256: str


@dataclass(frozen=True)
class ReaderProgress:
    source_identity: str
    source_path: str
    source_offset: int
    last_observed_size: int
    checkpoint: ReaderCheckpoint
    retired_completed: bool = False
    source_offset_start: int | None = None


@dataclass(frozen=True)
class VisitReaderState:
    source_identity: str
    source_path: str
    source_offset: int
    last_observed_size: int | None
    checkpoint_offset: int | None
    checkpoint_length: int | None
    checkpoint_sha256: str | None
    retired_completed: bool
    missing_warning_emitted: bool
    updated_at: str


@dataclass(frozen=True)
class OfflineProcessingOutcome:
    processing_result: str
    event_id: str | None = None
    visit_id: str | None = None
    reason: str | None = None
    duplicate: bool = False
    duration_drift_seconds: float | None = None
    duration_drift_threshold_seconds: float | None = None
    duration_drift_exceeded: bool = False
    close_time_source: str | None = None


@dataclass(frozen=True)
class VisitPage:
    items: tuple[Any, ...]
    next_cursor: str | None


@dataclass(frozen=True)
class VisitObservationWindow:
    site_id: str
    client_mac: str
    from_utc: str
    to_utc: str | None


@dataclass(frozen=True)
class ReconcileCandidate:
    visit_id: str
    site_id: str
    client_mac: str
    start_auth_session_id: str
    device_id: str | None
    initial_snapshot_id: str | None


def normalize_start_request(request: VisitStartRequest) -> NormalizedVisitStart:
    if not isinstance(request, VisitStartRequest):
        raise VisitValidationError("request must be VisitStartRequest")
    return NormalizedVisitStart(
        auth_session_id=require_canonical_uuid(
            request.auth_session_id,
            "auth_session_id",
        ),
        site_id=require_text(request.site_id, "site_id"),
        client_mac=require_mac(request.client_mac, "client_mac"),
        authorized_at=normalize_utc(request.authorized_at, "authorized_at"),
        auth_run_number=require_positive_int(
            request.auth_run_number,
            "auth_run_number",
        ),
        authorization_attempt=require_nonnegative_int_or_none(
            request.authorization_attempt,
            "authorization_attempt",
        ),
        final_reason=require_text(request.final_reason, "final_reason"),
        client_ip=optional_text(request.client_ip, "client_ip"),
        portal_ssid=optional_text(request.portal_ssid, "portal_ssid"),
        portal_ap_mac=optional_mac(
            request.portal_ap_mac,
            "portal_ap_mac",
        ),
        portal_radio_id=optional_nonnegative_int(
            request.portal_radio_id,
            "portal_radio_id",
        ),
    )


def utc_now() -> str:
    return format_utc(datetime.now(timezone.utc))


def normalize_utc(value: datetime | str, name: str) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise VisitValidationError(f"{name} must be timezone-aware")
        return format_utc(value)
    if not isinstance(value, str):
        raise VisitValidationError(f"{name} must be a UTC timestamp")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError as exc:
        raise VisitValidationError(
            f"{name} must use YYYY-MM-DDTHH:MM:SS.mmmZ"
        ) from exc
    normalized = format_utc(parsed.replace(tzinfo=timezone.utc))
    if value != normalized:
        raise VisitValidationError(
            f"{name} must use fixed-width millisecond UTC"
        )
    return normalized


def format_utc(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def require_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VisitValidationError(f"{name} must be a non-empty string")
    return value.strip()


def require_canonical_uuid(value: Any, name: str) -> str:
    text = require_text(value, name)
    try:
        canonical = str(uuid.UUID(text))
    except (ValueError, AttributeError) as exc:
        raise VisitValidationError(f"{name} must be a UUID") from exc
    if text != canonical:
        raise VisitValidationError(
            f"{name} must be canonical lowercase UUID"
        )
    return canonical


def optional_text(value: Any, name: str) -> str | None:
    if value is None:
        return None
    return require_text(value, name)


def require_mac(value: Any, name: str) -> str:
    try:
        return format_mac_colon(require_text(value, name))
    except (TypeError, ValueError) as exc:
        raise VisitValidationError(f"{name} must be a valid MAC") from exc


def optional_mac(value: Any, name: str) -> str | None:
    if value is None:
        return None
    return require_mac(value, name)


def require_positive_int(value: Any, name: str) -> int:
    if type(value) is not int or value <= 0 or value > MAX_SQLITE_INTEGER:
        raise VisitValidationError(f"{name} must be a positive integer")
    return value


def require_nonnegative_int_or_none(value: Any, name: str) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 0 or value > MAX_SQLITE_INTEGER:
        raise VisitValidationError(
            f"{name} must be a non-negative integer or null"
        )
    return value


def optional_nonnegative_int(value: Any, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    return require_nonnegative_int_or_none(value, name)
