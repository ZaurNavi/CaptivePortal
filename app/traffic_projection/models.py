"""Contracts for the derived Historical Traffic projection."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Mapping


SCHEMA_VERSION = 1
SOURCE_SCHEMA_VERSION = 1
PROJECTION_VERSION = "historical_traffic_projection.v1"
SEMANTIC_CONTRACT_SHA256 = hashlib.sha256(
    b"historical_traffic_projection.semantic.v1"
).hexdigest()
SUPPORTED_SEMANTIC_CONTRACTS = frozenset({SEMANTIC_CONTRACT_SHA256})
SOURCE = "observations"
RETENTION_DAYS = 14
MAX_PRODUCT_RANGE_DAYS = 7
SOURCE_HEAD_SCAN_INTERVAL_SECONDS = 15
FULL_RECONCILE_TARGET_INTERVAL_SECONDS = 300
HEALTHY_FULL_RECONCILE_MAX_AGE_SECONDS = 600
CATCHING_UP_FULL_RECONCILE_MAX_AGE_SECONDS = 900
HEALTHY_HEAD_LAG_MAX_SECONDS = 90
CATCHING_UP_HEAD_LAG_MAX_SECONDS = 300
INCREMENTAL_PROGRESS_MAX_AGE_SECONDS = 60
PASSIVE_CHECKPOINT_INTERVAL_SECONDS = 60
MAX_BULK_CYCLES_PER_TRANSACTION = 100
MAX_BULK_TRANSACTION_SECONDS = 1.0
MAX_CLEANUP_CHUNKS_PER_INVOCATION = 100
BUSY_TIMEOUT_MS = 500
WAL_AUTOCHECKPOINT_PAGES = 1000
JOURNAL_SIZE_LIMIT_BYTES = 67_108_864

VERSION_STATUSES = frozenset({"building", "ready", "active", "retired", "failed"})
HEALTH_STATUSES = frozenset({
    "healthy", "catching_up", "stale", "unavailable", "rebuilding", "diverged",
})
RATE_REASONS = frozenset({
    "ok", "no_baseline", "counter_reset", "gap_too_large",
    "invalid_elapsed", "source_unavailable",
})
_PROJECTION_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


def validate_projection_version(value: object) -> str:
    if not isinstance(value, str) or _PROJECTION_VERSION.fullmatch(value) is None:
        raise TrafficProjectionConfigError("projection version is invalid")
    return value


class TrafficProjectionError(RuntimeError):
    """Base class for sanitized projection failures."""


class TrafficProjectionConfigError(ValueError):
    """Projection configuration is invalid."""


class TrafficProjectionStorageUnavailable(TrafficProjectionError):
    """Projection storage cannot be used within bounded constraints."""


class TrafficProjectionStorageCorrupt(TrafficProjectionError):
    """Projection storage does not satisfy schema or integrity contracts."""


class TrafficProjectionVersionUnavailable(TrafficProjectionError):
    """No compatible active projection version can serve the request."""


class TrafficProjectionDiverged(TrafficProjectionError):
    """Projection facts conflict with authoritative source evidence."""


class TrafficProjectionWriterUnavailable(TrafficProjectionError):
    """The exclusive projection writer owner could not be established."""


class TrafficProjectionSourceUnavailable(TrafficProjectionError):
    """The authoritative Observation source cannot be read safely."""


class TrafficProjectionValidationError(ValueError):
    """An operation argument violates the projection contract."""


@dataclass(frozen=True, slots=True)
class TrafficProjectionConfig:
    enabled: bool
    db_path: str
    writer_lock_path: str
    source_db_path: str
    site_ids: tuple[str, ...]
    source_head_scan_interval_seconds: int = SOURCE_HEAD_SCAN_INTERVAL_SECONDS
    full_reconcile_target_interval_seconds: int = FULL_RECONCILE_TARGET_INTERVAL_SECONDS
    retention_days: int = RETENTION_DAYS
    shutdown_timeout_seconds: float = 20.0


@dataclass(frozen=True, slots=True)
class ProjectionHealth:
    status: str
    projection_version: str | None
    projection_revision: int | None
    source_head_utc: str | None
    projection_head_utc: str | None
    head_lag_seconds: float | None
    last_incremental_progress_at: str | None
    reconcile_sweep_started_at: str | None
    last_full_reconcile_completed_at: str | None
    last_full_reconcile_source_head_utc: str | None
    last_deep_audit_at: str | None
    backlog_cycle_count: int | None
    build_state: str | None

    def safe_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "projection_version": self.projection_version,
            "projection_revision": self.projection_revision,
            "source_head_utc": self.source_head_utc,
            "projection_head_utc": self.projection_head_utc,
            "head_lag_seconds": self.head_lag_seconds,
            "last_incremental_progress_at": self.last_incremental_progress_at,
            "reconcile_sweep_started_at": self.reconcile_sweep_started_at,
            "last_full_reconcile_completed_at": self.last_full_reconcile_completed_at,
            "last_full_reconcile_source_head_utc": self.last_full_reconcile_source_head_utc,
            "last_deep_audit_at": self.last_deep_audit_at,
            "backlog_cycle_count": self.backlog_cycle_count,
            "build_state": self.build_state,
        }


@dataclass(frozen=True, slots=True)
class ProjectedCycle:
    cycle: Mapping[str, Any]
    ap_rows: tuple[Mapping[str, Any], ...]
    source_revision_marker: str
    source_semantic_fingerprint: str | None
    integrity_ok: bool
    metric_facts_present: bool
    integrity_counts: Mapping[str, int]
    family_facts: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ProjectionRunResult:
    site_id: str
    cycles_examined: int
    cycles_projected: int
    cycles_replayed: int
    cycles_corrected: int
    cycles_invalidated: int
    deep_audit_checked: int
    sweep_completed: bool


@dataclass(frozen=True, slots=True)
class ProjectedRangeSelection:
    """One coherent request-relative selection shared by all five products."""

    projection_version: str
    projection_revision: int
    site_id: str
    from_utc: str
    to_utc: str
    bucket_seconds: int
    rows: tuple[Mapping[str, Any], ...]
    statistics: Mapping[str, Any] | None
    peak_samples: tuple[Mapping[str, Any], ...] | None
    ap_population: Mapping[str, int] | None
    ap_rows: tuple[Mapping[str, Any], ...] | None
    meta: Mapping[str, Any]
    attempts: Mapping[str, Any]

    def gateway_payload(self) -> Mapping[str, Any]:
        return {
            "meta": dict(self.meta),
            "buckets": tuple(dict(row) for row in self.rows),
            "attempts": dict(self.attempts),
            "period_statistics": (
                None if self.statistics is None else dict(self.statistics)
            ),
            "peak_samples": (
                None if self.peak_samples is None
                else tuple(dict(row) for row in self.peak_samples)
            ),
            "ap_population": (
                None if self.ap_population is None else dict(self.ap_population)
            ),
            "ap_rows": (
                None if self.ap_rows is None
                else tuple(dict(row) for row in self.ap_rows)
            ),
        }
