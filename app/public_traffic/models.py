"""Value objects and configuration for the public traffic counter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


INT64_MAX = 9_223_372_036_854_775_807


class PublicTrafficConfigError(ValueError):
    """The traffic component configuration is invalid."""


class BackfillIncompleteError(RuntimeError):
    """Administrative reset is forbidden before initial backfill."""


class AggregateOverflowError(RuntimeError):
    """Stored aggregate cannot be represented as SQLite INTEGER."""


@dataclass(frozen=True)
class PublicTrafficConfig:
    enabled: bool
    ssid: str
    db_path: str
    source_log_path: str
    timezone_name: str
    scan_interval_seconds: int
    frontend_refresh_seconds: int

    @classmethod
    def from_settings(
        cls,
        settings: dict[str, Any],
    ) -> "PublicTrafficConfig":
        enabled = _strict_bool(
            settings.get("public_traffic_counter_enabled", False),
            "PUBLIC_TRAFFIC_COUNTER_ENABLED",
        )
        ssid = _strict_string(
            settings.get("public_traffic_ssid", ""),
            "PUBLIC_TRAFFIC_SSID",
            required=enabled,
        )
        db_path = _strict_string(
            settings.get("public_traffic_db_path", ""),
            "PUBLIC_TRAFFIC_DB_PATH",
            required=enabled,
        )
        source_log_path = _strict_string(
            settings.get("omada_webhook_normalized_log_file", ""),
            "OMADA_WEBHOOK_NORMALIZED_LOG_FILE",
            required=enabled,
        )
        timezone_name = _strict_string(
            settings.get("portal_counter_timezone", ""),
            "PORTAL_COUNTER_TIMEZONE",
            required=enabled,
        )
        scan_interval = _positive_int(
            settings.get("public_traffic_scan_interval_seconds", 10),
            "PUBLIC_TRAFFIC_SCAN_INTERVAL_SECONDS",
        )
        frontend_refresh = _positive_int(
            settings.get(
                "public_traffic_frontend_refresh_seconds",
                60,
            ),
            "PUBLIC_TRAFFIC_FRONTEND_REFRESH_SECONDS",
        )
        return cls(
            enabled=enabled,
            ssid=ssid,
            db_path=db_path,
            source_log_path=source_log_path,
            timezone_name=timezone_name,
            scan_interval_seconds=scan_interval,
            frontend_refresh_seconds=frontend_refresh,
        )


@dataclass(frozen=True)
class ReaderState:
    source_identity: str
    source_path: str
    source_offset: int
    source_checkpoint: str | None
    last_observed_size: int | None
    retired_completed: bool
    missing_warning_emitted: bool


@dataclass(frozen=True)
class TrafficEvent:
    normalized_event_id: str
    ssid: str | None
    local_date: str | None
    traffic_bytes: int | None
    skip_reason: str | None

    @property
    def valid(self) -> bool:
        return self.skip_reason is None


@dataclass(frozen=True)
class ClassifiedRecord:
    target: bool
    event: TrafficEvent | None = None
    warning_code: str | None = None
    timestamp_fallback: bool = False


@dataclass(frozen=True)
class ProcessOutcome:
    duplicate: bool
    counted: bool
    skip_reason: str | None


@dataclass(frozen=True)
class TrafficSnapshot:
    available: bool
    ssid: str
    today_bytes: int = 0
    total_bytes: int = 0
    completed_sessions_today: int = 0
    completed_sessions_total: int = 0
    updated_at: str | None = None


@dataclass(frozen=True)
class ResetSummary:
    reset_id: str
    scope: str
    ssid: str | None
    reset_at: str
    previous_today_bytes: int | None
    previous_total_bytes: int | None
    previous_sessions_today: int | None
    previous_sessions_total: int | None
    affected_ssids: int | None


def _strict_bool(value: Any, name: str) -> bool:
    if type(value) is bool:
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    raise PublicTrafficConfigError(f"{name} must be true or false")


def _strict_string(
    value: Any,
    name: str,
    *,
    required: bool,
) -> str:
    if not isinstance(value, str):
        if required:
            raise PublicTrafficConfigError(
                f"{name} must be a non-empty string"
            )
        return ""
    result = value.strip()
    if required and not result:
        raise PublicTrafficConfigError(
            f"{name} must be a non-empty string"
        )
    return result


def _positive_int(value: Any, name: str) -> int:
    if type(value) is int:
        parsed = value
    elif isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
    else:
        raise PublicTrafficConfigError(
            f"{name} must be a positive integer"
        )
    if parsed <= 0 or parsed > INT64_MAX:
        raise PublicTrafficConfigError(
            f"{name} must be a positive integer"
        )
    return parsed
