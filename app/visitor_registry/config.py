"""Strict, fail-open configuration for Visitor Snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


DEFAULT_LOG_FILE = "/opt/CaptivePortal/logs/visitor_snapshots.log"
DEFAULT_MAX_WORKERS = 2
DEFAULT_MAX_PENDING = 100
DEFAULT_MAX_JOB_AGE_SECONDS = 30.0
DEFAULT_REQUEST_TIMEOUT_SECONDS = 5.0
DEFAULT_RETRY_DELAYS_SECONDS = (2.0, 5.0)
DEFAULT_ROTATION_MAX_BYTES = 52_428_800
DEFAULT_ROTATION_BACKUP_COUNT = 20
DEFAULT_SHUTDOWN_TIMEOUT_SECONDS = 90.0


class VisitorSnapshotConfigError(ValueError):
    """The Visitor Snapshot component configuration is invalid."""


@dataclass(frozen=True)
class VisitorSnapshotConfig:
    enabled: bool
    log_file: str = DEFAULT_LOG_FILE
    max_workers: int = DEFAULT_MAX_WORKERS
    max_pending: int = DEFAULT_MAX_PENDING
    max_job_age_seconds: float = DEFAULT_MAX_JOB_AGE_SECONDS
    request_timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS
    retry_delays_seconds: tuple[float, float] = (
        DEFAULT_RETRY_DELAYS_SECONDS
    )
    rotation_max_bytes: int = DEFAULT_ROTATION_MAX_BYTES
    rotation_backup_count: int = DEFAULT_ROTATION_BACKUP_COUNT
    shutdown_timeout_seconds: float = DEFAULT_SHUTDOWN_TIMEOUT_SECONDS

    @classmethod
    def from_settings(
        cls,
        settings: dict[str, Any],
    ) -> "VisitorSnapshotConfig":
        enabled = _strict_bool(
            settings.get("visitor_snapshot_enabled", False),
            "VISITOR_SNAPSHOT_ENABLED",
        )
        if not enabled:
            return cls(enabled=False)

        return cls(
            enabled=True,
            log_file=_nonempty_string(
                settings.get(
                    "visitor_snapshot_log_file",
                    DEFAULT_LOG_FILE,
                ),
                "VISITOR_SNAPSHOT_LOG_FILE",
            ),
            max_workers=_integer(
                settings.get(
                    "visitor_snapshot_max_workers",
                    DEFAULT_MAX_WORKERS,
                ),
                "VISITOR_SNAPSHOT_MAX_WORKERS",
                minimum=1,
            ),
            max_pending=_integer(
                settings.get(
                    "visitor_snapshot_max_pending",
                    DEFAULT_MAX_PENDING,
                ),
                "VISITOR_SNAPSHOT_MAX_PENDING",
                minimum=0,
            ),
            max_job_age_seconds=_positive_number(
                settings.get(
                    "visitor_snapshot_max_job_age_seconds",
                    DEFAULT_MAX_JOB_AGE_SECONDS,
                ),
                "VISITOR_SNAPSHOT_MAX_JOB_AGE_SECONDS",
            ),
            request_timeout_seconds=_positive_number(
                settings.get(
                    "visitor_snapshot_request_timeout_seconds",
                    DEFAULT_REQUEST_TIMEOUT_SECONDS,
                ),
                "VISITOR_SNAPSHOT_REQUEST_TIMEOUT_SECONDS",
            ),
            retry_delays_seconds=_retry_delays(
                settings.get(
                    "visitor_snapshot_retry_delays_seconds",
                    "2,5",
                )
            ),
            rotation_max_bytes=_integer(
                settings.get(
                    "visitor_snapshot_rotation_max_bytes",
                    DEFAULT_ROTATION_MAX_BYTES,
                ),
                "VISITOR_SNAPSHOT_ROTATION_MAX_BYTES",
                minimum=1,
            ),
            rotation_backup_count=_integer(
                settings.get(
                    "visitor_snapshot_rotation_backup_count",
                    DEFAULT_ROTATION_BACKUP_COUNT,
                ),
                "VISITOR_SNAPSHOT_ROTATION_BACKUP_COUNT",
                minimum=1,
            ),
            shutdown_timeout_seconds=_positive_number(
                settings.get(
                    "visitor_snapshot_shutdown_timeout_seconds",
                    DEFAULT_SHUTDOWN_TIMEOUT_SECONDS,
                ),
                "VISITOR_SNAPSHOT_SHUTDOWN_TIMEOUT_SECONDS",
            ),
        )

    @property
    def total_capacity(self) -> int:
        return self.max_workers + self.max_pending


def _strict_bool(value: Any, name: str) -> bool:
    if type(value) is bool:
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    raise VisitorSnapshotConfigError(
        f"{name} must be true or false"
    )


def _nonempty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VisitorSnapshotConfigError(
            f"{name} must be a non-empty string"
        )
    return value.strip()


def _integer(
    value: Any,
    name: str,
    *,
    minimum: int,
) -> int:
    if type(value) is int:
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = int(value.strip())
        except ValueError as exc:
            raise VisitorSnapshotConfigError(
                f"{name} must be an integer >= {minimum}"
            ) from exc
    else:
        raise VisitorSnapshotConfigError(
            f"{name} must be an integer >= {minimum}"
        )
    if parsed < minimum:
        raise VisitorSnapshotConfigError(
            f"{name} must be an integer >= {minimum}"
        )
    return parsed


def _positive_number(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise VisitorSnapshotConfigError(
            f"{name} must be a number > 0"
        )
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise VisitorSnapshotConfigError(
            f"{name} must be a number > 0"
        ) from exc
    if parsed <= 0 or parsed == float("inf") or parsed != parsed:
        raise VisitorSnapshotConfigError(
            f"{name} must be a finite number > 0"
        )
    return parsed


def _retry_delays(value: Any) -> tuple[float, float]:
    if isinstance(value, str):
        items = value.split(",")
    elif isinstance(value, (tuple, list)):
        items = list(value)
    else:
        raise VisitorSnapshotConfigError(
            "VISITOR_SNAPSHOT_RETRY_DELAYS_SECONDS must contain "
            "exactly two numbers"
        )
    if len(items) != 2:
        raise VisitorSnapshotConfigError(
            "VISITOR_SNAPSHOT_RETRY_DELAYS_SECONDS must contain "
            "exactly two numbers"
        )
    parsed: list[float] = []
    for item in items:
        if isinstance(item, bool):
            raise VisitorSnapshotConfigError(
                "VISITOR_SNAPSHOT_RETRY_DELAYS_SECONDS values must "
                "be finite numbers >= 0"
            )
        try:
            number = float(item)
        except (TypeError, ValueError) as exc:
            raise VisitorSnapshotConfigError(
                "VISITOR_SNAPSHOT_RETRY_DELAYS_SECONDS values must "
                "be finite numbers >= 0"
            ) from exc
        if number < 0 or number == float("inf") or number != number:
            raise VisitorSnapshotConfigError(
                "VISITOR_SNAPSHOT_RETRY_DELAYS_SECONDS values must "
                "be finite numbers >= 0"
            )
        parsed.append(number)
    return parsed[0], parsed[1]
