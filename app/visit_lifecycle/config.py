"""Strict fail-open configuration parsing for Visit Lifecycle v1."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from .models import (
    MAX_SQLITE_INTEGER,
    VisitLifecycleConfig,
    VisitLifecycleConfigError,
)


DEFAULT_DB_PATH = "/opt/CaptivePortal/data/visits.sqlite3"
DEFAULT_WEBHOOK_SOURCE = (
    "/opt/CaptivePortal/logs/omada_webhook_normalized.log"
)


def visit_config_from_settings(
    settings: dict[str, Any],
) -> VisitLifecycleConfig:
    enabled = _strict_bool(
        settings.get("visit_lifecycle_enabled", False),
        "VISIT_LIFECYCLE_ENABLED",
    )
    if not enabled:
        return VisitLifecycleConfig(
            enabled=False,
            db_path=str(settings.get("visit_lifecycle_db_path", DEFAULT_DB_PATH)),
            webhook_source=str(settings.get(
                "visit_lifecycle_webhook_source",
                DEFAULT_WEBHOOK_SOURCE,
            )),
            scan_interval_seconds=5.0,
            reconcile_interval_seconds=30.0,
            max_line_bytes=1_048_576,
            reader_max_lines_per_scan=5_000,
            reader_max_bytes_per_scan=16_777_216,
            reader_max_duration_seconds=20.0,
            reconcile_batch_size=500,
            pending_offline_batch_size=500,
            offline_match_grace_seconds=30.0,
            start_busy_timeout_ms=250,
            shutdown_timeout_seconds=20.0,
            max_offline_clock_skew_seconds=120.0,
            max_reported_duration_drift_seconds=300.0,
        )
    return VisitLifecycleConfig(
        enabled=True,
        db_path=_absolute_path(
            settings.get("visit_lifecycle_db_path", DEFAULT_DB_PATH),
            "VISIT_LIFECYCLE_DB_PATH",
        ),
        webhook_source=_absolute_path(
            settings.get(
                "visit_lifecycle_webhook_source",
                DEFAULT_WEBHOOK_SOURCE,
            ),
            "VISIT_LIFECYCLE_WEBHOOK_SOURCE",
        ),
        scan_interval_seconds=_positive_number(
            settings.get("visit_lifecycle_scan_interval_seconds", 5),
            "VISIT_LIFECYCLE_SCAN_INTERVAL_SECONDS",
        ),
        reconcile_interval_seconds=_positive_number(
            settings.get("visit_lifecycle_reconcile_interval_seconds", 30),
            "VISIT_LIFECYCLE_RECONCILE_INTERVAL_SECONDS",
        ),
        max_line_bytes=_positive_int(
            settings.get("visit_lifecycle_max_line_bytes", 1_048_576),
            "VISIT_LIFECYCLE_MAX_LINE_BYTES",
        ),
        reader_max_lines_per_scan=_positive_int(
            settings.get(
                "visit_lifecycle_reader_max_lines_per_scan",
                5_000,
            ),
            "VISIT_LIFECYCLE_READER_MAX_LINES_PER_SCAN",
        ),
        reader_max_bytes_per_scan=_positive_int(
            settings.get(
                "visit_lifecycle_reader_max_bytes_per_scan",
                16_777_216,
            ),
            "VISIT_LIFECYCLE_READER_MAX_BYTES_PER_SCAN",
        ),
        reader_max_duration_seconds=_positive_number(
            settings.get(
                "visit_lifecycle_reader_max_duration_seconds",
                20,
            ),
            "VISIT_LIFECYCLE_READER_MAX_DURATION_SECONDS",
        ),
        reconcile_batch_size=_positive_int(
            settings.get("visit_lifecycle_reconcile_batch_size", 500),
            "VISIT_LIFECYCLE_RECONCILE_BATCH_SIZE",
        ),
        pending_offline_batch_size=_positive_int(
            settings.get(
                "visit_lifecycle_pending_offline_batch_size",
                500,
            ),
            "VISIT_LIFECYCLE_PENDING_OFFLINE_BATCH_SIZE",
        ),
        offline_match_grace_seconds=_positive_number(
            settings.get(
                "visit_lifecycle_offline_match_grace_seconds",
                30,
            ),
            "VISIT_LIFECYCLE_OFFLINE_MATCH_GRACE_SECONDS",
        ),
        start_busy_timeout_ms=_positive_int(
            settings.get("visit_lifecycle_start_busy_timeout_ms", 250),
            "VISIT_LIFECYCLE_START_BUSY_TIMEOUT_MS",
            maximum=60_000,
        ),
        shutdown_timeout_seconds=_positive_number(
            settings.get("visit_lifecycle_shutdown_timeout_seconds", 20),
            "VISIT_LIFECYCLE_SHUTDOWN_TIMEOUT_SECONDS",
        ),
        max_offline_clock_skew_seconds=_positive_number(
            settings.get(
                "visit_lifecycle_max_offline_clock_skew_seconds",
                120,
            ),
            "VISIT_LIFECYCLE_MAX_OFFLINE_CLOCK_SKEW_SECONDS",
        ),
        max_reported_duration_drift_seconds=_positive_number(
            settings.get(
                "visit_lifecycle_max_reported_duration_drift_seconds",
                300,
            ),
            "VISIT_LIFECYCLE_MAX_REPORTED_DURATION_DRIFT_SECONDS",
        ),
    )


def _strict_bool(value: Any, name: str) -> bool:
    if type(value) is bool:
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    raise VisitLifecycleConfigError(f"{name} must be true or false")


def _absolute_path(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VisitLifecycleConfigError(f"{name} must be an absolute path")
    text = value.strip()
    if not Path(text).is_absolute() and not PurePosixPath(text).is_absolute():
        raise VisitLifecycleConfigError(f"{name} must be an absolute path")
    return text


def _positive_int(
    value: Any,
    name: str,
    *,
    maximum: int = MAX_SQLITE_INTEGER,
) -> int:
    if type(value) is int:
        parsed = value
    elif isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
    else:
        raise VisitLifecycleConfigError(f"{name} must be positive")
    if parsed <= 0 or parsed > maximum:
        raise VisitLifecycleConfigError(f"{name} must be positive")
    return parsed


def _positive_number(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise VisitLifecycleConfigError(f"{name} must be positive")
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise VisitLifecycleConfigError(f"{name} must be positive") from exc
    if not 0 < parsed < float("inf"):
        raise VisitLifecycleConfigError(f"{name} must be positive")
    return parsed
