"""Validated configuration for the read-only Analytics foundation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class AnalyticsConfigError(ValueError):
    """Analytics configuration violates the bounded v1 contract."""


@dataclass(frozen=True, slots=True)
class AnalyticsConfig:
    enabled: bool = False
    default_limit: int = 500
    max_limit: int = 2_000
    max_query_window_days: int = 31
    max_query_duration_seconds: float = 10.0
    quality_gap_threshold_seconds: float = 180.0


def analytics_config_from_settings(
    settings: Mapping[str, Any],
) -> AnalyticsConfig:
    enabled = _exact_bool(
        settings.get("analytics_foundation_enabled", "false"),
        "ANALYTICS_FOUNDATION_ENABLED",
    )
    default_limit = _positive_int(
        settings.get("analytics_default_limit", 500),
        "ANALYTICS_DEFAULT_LIMIT",
    )
    max_limit = _positive_int(
        settings.get("analytics_max_limit", 2_000),
        "ANALYTICS_MAX_LIMIT",
    )
    if default_limit > max_limit:
        raise AnalyticsConfigError(
            "ANALYTICS_DEFAULT_LIMIT must not exceed ANALYTICS_MAX_LIMIT"
        )
    if max_limit > 2_000:
        raise AnalyticsConfigError(
            "ANALYTICS_MAX_LIMIT must not exceed 2000"
        )
    window_days = _positive_int(
        settings.get("analytics_max_query_window_days", 31),
        "ANALYTICS_MAX_QUERY_WINDOW_DAYS",
    )
    if window_days > 31:
        raise AnalyticsConfigError(
            "ANALYTICS_MAX_QUERY_WINDOW_DAYS must not exceed 31"
        )
    return AnalyticsConfig(
        enabled=enabled,
        default_limit=default_limit,
        max_limit=max_limit,
        max_query_window_days=window_days,
        max_query_duration_seconds=_positive_float(
            settings.get("analytics_max_query_duration_seconds", 10),
            "ANALYTICS_MAX_QUERY_DURATION_SECONDS",
        ),
        quality_gap_threshold_seconds=_positive_float(
            settings.get("analytics_quality_gap_threshold_seconds", 180),
            "ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS",
        ),
    )


def _exact_bool(value: Any, name: str) -> bool:
    if type(value) is bool:
        return value
    if value == "true":
        return True
    if value == "false":
        return False
    raise AnalyticsConfigError(f"{name} must be exactly true or false")


def _positive_int(value: Any, name: str) -> int:
    if type(value) is int:
        parsed = value
    elif isinstance(value, str) and value.isdigit():
        parsed = int(value)
    else:
        raise AnalyticsConfigError(f"{name} must be a positive integer")
    if parsed <= 0:
        raise AnalyticsConfigError(f"{name} must be a positive integer")
    return parsed


def _positive_float(value: Any, name: str) -> float:
    if type(value) is bool:
        raise AnalyticsConfigError(f"{name} must be positive")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise AnalyticsConfigError(f"{name} must be positive") from exc
    if not 0 < parsed < float("inf"):
        raise AnalyticsConfigError(f"{name} must be positive")
    return parsed
