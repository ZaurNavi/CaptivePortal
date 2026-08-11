"""Configuration parsing for Observation Storage Foundation v1."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import ObservationConfig, ObservationConfigError


DEFAULT_DB_PATH = "/opt/CaptivePortal/data/observations.sqlite3"
MAX_CLEANUP_BATCH_SIZE = 100_000


def observation_config_from_settings(
    settings: dict[str, Any],
) -> ObservationConfig:
    """Build a strict, independently fail-open configuration object."""
    enabled = _strict_bool(
        settings.get("observation_foundation_enabled", False),
        "OBSERVATION_FOUNDATION_ENABLED",
    )
    if not enabled:
        return ObservationConfig(
            enabled=False,
            db_path=str(settings.get("observation_db_path", DEFAULT_DB_PATH)),
            dynamic_retention_days=180,
            config_retention_days=730,
            cleanup_initial_delay_seconds=900.0,
            cleanup_interval_seconds=86400.0,
            cleanup_batch_size=5000,
            cleanup_max_duration_seconds=30.0,
            shutdown_timeout_seconds=20.0,
        )

    db_path = _absolute_path(
        settings.get("observation_db_path", DEFAULT_DB_PATH),
        "OBSERVATION_DB_PATH",
    )
    return ObservationConfig(
        enabled=True,
        db_path=db_path,
        dynamic_retention_days=_positive_int(
            settings.get("observation_dynamic_retention_days", 180),
            "OBSERVATION_DYNAMIC_RETENTION_DAYS",
        ),
        config_retention_days=_positive_int(
            settings.get("observation_config_retention_days", 730),
            "OBSERVATION_CONFIG_RETENTION_DAYS",
        ),
        cleanup_initial_delay_seconds=_positive_number(
            settings.get(
                "observation_cleanup_initial_delay_seconds",
                900,
            ),
            "OBSERVATION_CLEANUP_INITIAL_DELAY_SECONDS",
        ),
        cleanup_interval_seconds=_positive_number(
            settings.get("observation_cleanup_interval_seconds", 86400),
            "OBSERVATION_CLEANUP_INTERVAL_SECONDS",
        ),
        cleanup_batch_size=_positive_int(
            settings.get("observation_cleanup_batch_size", 5000),
            "OBSERVATION_CLEANUP_BATCH_SIZE",
            maximum=MAX_CLEANUP_BATCH_SIZE,
        ),
        cleanup_max_duration_seconds=_positive_number(
            settings.get(
                "observation_cleanup_max_duration_seconds",
                30,
            ),
            "OBSERVATION_CLEANUP_MAX_DURATION_SECONDS",
        ),
        shutdown_timeout_seconds=_positive_number(
            settings.get("observation_shutdown_timeout_seconds", 20),
            "OBSERVATION_SHUTDOWN_TIMEOUT_SECONDS",
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
    raise ObservationConfigError(f"{name} must be true or false")


def _absolute_path(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ObservationConfigError(f"{name} must be an absolute path")
    path = Path(value.strip())
    if not path.is_absolute():
        raise ObservationConfigError(f"{name} must be an absolute path")
    return str(path)


def _positive_int(
    value: Any,
    name: str,
    *,
    maximum: int | None = None,
) -> int:
    if type(value) is int:
        parsed = value
    elif isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
    else:
        raise ObservationConfigError(f"{name} must be a positive integer")
    if parsed <= 0 or (maximum is not None and parsed > maximum):
        raise ObservationConfigError(f"{name} must be a positive integer")
    return parsed


def _positive_number(value: Any, name: str) -> float:
    if type(value) is bool:
        raise ObservationConfigError(f"{name} must be positive")
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ObservationConfigError(f"{name} must be positive") from exc
    if not 0 < parsed < float("inf"):
        raise ObservationConfigError(f"{name} must be positive")
    return parsed
