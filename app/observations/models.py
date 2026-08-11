"""Immutable contracts for Observation Storage Foundation v1."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Generic, Mapping, TypeVar

from app.common.mac import format_mac_colon


SCHEMA_VERSION = 1
DEFAULT_QUERY_LIMIT = 500
MAX_QUERY_LIMIT = 2000

_UTC_TIMESTAMP = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z"
)


class ObservationConfigError(ValueError):
    """Enabled Observation Foundation configuration is invalid."""


class ObservationValidationError(ValueError):
    """A storage or query argument violates the v1 contract."""


class ObservationSchemaError(RuntimeError):
    """The on-disk schema is incompatible or incomplete."""


class StorageFailureCategory(str, Enum):
    """Stable operational categories for SQLite failures."""

    BUSY = "busy"
    FULL = "full"
    IO_ERROR = "io_error"
    CORRUPT = "corrupt"
    UNAVAILABLE = "unavailable"
    CONSTRAINT = "constraint"
    DEGRADED = "degraded"


class ObservationStorageError(RuntimeError):
    """A sanitized SQLite failure safe for operational handling."""

    def __init__(
        self,
        category: StorageFailureCategory,
        message: str = "Observation storage operation failed",
    ):
        super().__init__(message)
        self.category = category


@dataclass(frozen=True, slots=True)
class ObservationConfig:
    enabled: bool
    db_path: str
    dynamic_retention_days: int
    config_retention_days: int
    cleanup_initial_delay_seconds: float
    cleanup_interval_seconds: float
    cleanup_batch_size: int
    cleanup_max_duration_seconds: float
    shutdown_timeout_seconds: float
    client_enabled: bool = False
    site_ids: tuple[str, ...] = ()
    client_ssids: tuple[str, ...] = ()
    client_initial_delay_seconds: float = 15.0
    client_interval_seconds: float = 60.0
    request_timeout_seconds: float = 5.0
    client_page_size: int = 500
    client_max_pages: int = 20
    client_max_rows: int = 10_000


@dataclass(frozen=True, slots=True)
class InitializationResult:
    created: bool
    abandoned_cycles: int


@dataclass(frozen=True, slots=True)
class ObservationCycle:
    cycle_id: str
    kind: str
    site_id: str
    state: str
    started_at: str
    finished_at: str | None
    abandoned_at: str | None
    complete: bool | None
    result: str | None
    source_rows_reported: int | None
    items_seen: int
    items_stored: int
    items_skipped: int
    error_count: int
    data_quality_warning_count: int
    created_at: str
    updated_at: str


def _immutable_data(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(value))


@dataclass(frozen=True, slots=True)
class ClientObservation:
    row_id: int
    cycle_id: str
    observed_at: str
    site_id: str
    client_mac: str
    source_inventory_complete: bool
    ssid: str | None
    ap_mac: str | None
    radio_id: int | None
    data: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", _immutable_data(self.data))


@dataclass(frozen=True, slots=True)
class ApObservation:
    row_id: int
    cycle_id: str
    observed_at: str
    site_id: str
    ap_mac: str
    partial: bool
    data: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", _immutable_data(self.data))


@dataclass(frozen=True, slots=True)
class ApRadioObservation:
    row_id: int
    cycle_id: str
    ap_observation_row_id: int
    radio_observed_at: str
    site_id: str
    ap_mac: str
    band: str
    data: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", _immutable_data(self.data))


@dataclass(frozen=True, slots=True)
class ApConfigSnapshot:
    row_id: int
    cycle_id: str
    captured_at: str
    site_id: str
    ap_mac: str
    config_sha256: str
    schema_version: int
    config_json: str


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class ObservationPage(Generic[T]):
    items: tuple[T, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class CleanupResult:
    deleted_dynamic_cycles: int
    deleted_config_cycles: int
    batches: int
    interrupted: bool
    duration_exhausted: bool


def utc_now() -> str:
    """Return current UTC in the fixed-width persistence format."""
    return format_utc(datetime.now(UTC))


def format_utc(value: datetime) -> str:
    """Normalize a datetime to ``YYYY-MM-DDTHH:MM:SS.mmmZ``."""
    if not isinstance(value, datetime):
        raise ObservationValidationError("UTC datetime is required")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ObservationValidationError("UTC datetime must be timezone-aware")
    normalized = value.astimezone(UTC)
    milliseconds = normalized.microsecond // 1000
    return normalized.strftime("%Y-%m-%dT%H:%M:%S") + (
        f".{milliseconds:03d}Z"
    )


def parse_utc(value: Any, name: str = "timestamp") -> datetime:
    """Strictly parse the persisted timestamp contract."""
    if not isinstance(value, str) or _UTC_TIMESTAMP.fullmatch(value) is None:
        raise ObservationValidationError(
            f"{name} must use YYYY-MM-DDTHH:MM:SS.mmmZ"
        )
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError as exc:
        raise ObservationValidationError(
            f"{name} must be a valid UTC timestamp"
        ) from exc
    return parsed.replace(tzinfo=UTC)


def require_utc(value: Any, name: str = "timestamp") -> str:
    parse_utc(value, name)
    return value


def require_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ObservationValidationError(f"{name} must be non-empty")
    return value.strip()


def require_mac(value: Any, name: str) -> str:
    try:
        return format_mac_colon(value)
    except ValueError as exc:
        raise ObservationValidationError(
            f"{name} must be a valid MAC address"
        ) from exc


def require_limit(value: Any) -> int:
    if type(value) is not int or not 1 <= value <= MAX_QUERY_LIMIT:
        raise ObservationValidationError(
            f"limit must be between 1 and {MAX_QUERY_LIMIT}"
        )
    return value


def require_nonnegative_int_or_none(
    value: Any,
    name: str,
) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 0:
        raise ObservationValidationError(
            f"{name} must be a non-negative integer or null"
        )
    return value
