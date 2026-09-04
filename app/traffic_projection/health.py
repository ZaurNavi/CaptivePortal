"""Pure projection-health classification with frozen precedence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from .models import (
    CATCHING_UP_FULL_RECONCILE_MAX_AGE_SECONDS,
    CATCHING_UP_HEAD_LAG_MAX_SECONDS,
    HEALTHY_FULL_RECONCILE_MAX_AGE_SECONDS,
    HEALTHY_HEAD_LAG_MAX_SECONDS,
    INCREMENTAL_PROGRESS_MAX_AGE_SECONDS,
    PROJECTION_VERSION,
    ProjectionHealth,
)


UTC = timezone.utc


def classify_projection_health(
    state: Mapping[str, Any] | None,
    *,
    now_utc: str,
    storage_available: bool = True,
    version_available: bool = True,
    source_available: bool = True,
    build_state: str | None = None,
) -> ProjectionHealth:
    """Apply exact diverged→unavailable→rebuilding→healthy→catching→stale order."""
    row = dict(state or {})
    stored = row.get("status")
    source_head = row.get("source_head_utc")
    projection_head = row.get("projection_head_utc")
    lag = _head_lag(source_head, projection_head)
    reconcile_age = _age(now_utc, row.get("last_full_reconcile_completed_at"))
    progress_age = _age(now_utc, row.get("last_incremental_progress_at"))
    if stored == "diverged":
        status = "diverged"
    elif not storage_available or state is None:
        status = "unavailable"
    elif build_state in {"building", "ready"} or stored == "rebuilding":
        status = "rebuilding"
    elif not version_available:
        status = "unavailable"
    elif (
        source_available and lag is not None and lag <= HEALTHY_HEAD_LAG_MAX_SECONDS
        and reconcile_age is not None
        and reconcile_age <= HEALTHY_FULL_RECONCILE_MAX_AGE_SECONDS
    ):
        status = "healthy"
    elif (
        source_available and lag is not None and lag <= CATCHING_UP_HEAD_LAG_MAX_SECONDS
        and progress_age is not None and progress_age <= INCREMENTAL_PROGRESS_MAX_AGE_SECONDS
        and (
            reconcile_age is not None
            and reconcile_age <= CATCHING_UP_FULL_RECONCILE_MAX_AGE_SECONDS
        )
    ):
        status = "catching_up"
    else:
        status = "stale"
    return ProjectionHealth(
        status=status,
        projection_version=row.get("projection_version", PROJECTION_VERSION) if state else None,
        projection_revision=row.get("projection_revision"),
        source_head_utc=source_head,
        projection_head_utc=projection_head,
        head_lag_seconds=lag,
        last_incremental_progress_at=row.get("last_incremental_progress_at"),
        reconcile_sweep_started_at=row.get("reconcile_sweep_started_at"),
        last_full_reconcile_completed_at=row.get("last_full_reconcile_completed_at"),
        last_full_reconcile_source_head_utc=row.get("last_full_reconcile_source_head_utc"),
        last_deep_audit_at=row.get("last_deep_audit_at"),
        backlog_cycle_count=row.get("backlog_cycle_count"),
        build_state=build_state,
    )


def _parse(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(UTC) if parsed.tzinfo is not None else None
    except ValueError:
        return None


def _age(now: Any, then: Any) -> float | None:
    current, previous = _parse(now), _parse(then)
    if current is None or previous is None:
        return None
    return max((current - previous).total_seconds(), 0.0)


def _head_lag(source: Any, projection: Any) -> float | None:
    source_at, projection_at = _parse(source), _parse(projection)
    if source_at is None or projection_at is None:
        return None
    return max((source_at - projection_at).total_seconds(), 0.0)
