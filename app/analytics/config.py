"""Validated configuration for the read-only Analytics foundation."""

from __future__ import annotations

import math
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
    wireless_enabled: bool = True
    wireless_min_samples: int = 20
    wireless_max_window_days: int = 7
    counter_max_gap_seconds: float = 180.0
    ap_join_max_lag_seconds: float = 120.0
    rssi_threshold_dbm: float | None = None
    snr_threshold_db: float | None = None
    visit_enabled: bool = True
    visit_min_cohort_size: int = 20
    visit_max_window_days: int = 90


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
    wireless_window_days = _positive_int(
        settings.get("analytics_wireless_max_window_days", 7),
        "ANALYTICS_WIRELESS_MAX_WINDOW_DAYS",
    )
    if wireless_window_days > window_days:
        raise AnalyticsConfigError(
            "ANALYTICS_WIRELESS_MAX_WINDOW_DAYS must not exceed "
            "ANALYTICS_MAX_QUERY_WINDOW_DAYS"
        )
    wireless_min_samples = _positive_int(
        settings.get("analytics_wireless_min_samples", 20),
        "ANALYTICS_WIRELESS_MIN_SAMPLES",
    )
    if wireless_min_samples < 2:
        raise AnalyticsConfigError(
            "ANALYTICS_WIRELESS_MIN_SAMPLES must be at least 2"
        )
    visit_min_cohort_size = _positive_int(
        settings.get("analytics_visit_min_cohort_size", 20),
        "ANALYTICS_VISIT_MIN_COHORT_SIZE",
    )
    if visit_min_cohort_size < 2:
        raise AnalyticsConfigError(
            "ANALYTICS_VISIT_MIN_COHORT_SIZE must be at least 2"
        )
    visit_max_window_days = _positive_int(
        settings.get("analytics_visit_max_window_days", 90),
        "ANALYTICS_VISIT_MAX_WINDOW_DAYS",
    )
    if visit_max_window_days > 90:
        raise AnalyticsConfigError(
            "ANALYTICS_VISIT_MAX_WINDOW_DAYS must not exceed 90"
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
        wireless_enabled=_exact_bool(
            settings.get("analytics_wireless_enabled", "true"),
            "ANALYTICS_WIRELESS_ENABLED",
        ),
        wireless_min_samples=wireless_min_samples,
        wireless_max_window_days=wireless_window_days,
        counter_max_gap_seconds=_positive_float(
            settings.get("analytics_counter_max_gap_seconds", 180),
            "ANALYTICS_COUNTER_MAX_GAP_SECONDS",
        ),
        ap_join_max_lag_seconds=_positive_float(
            settings.get("analytics_ap_join_max_lag_seconds", 120),
            "ANALYTICS_AP_JOIN_MAX_LAG_SECONDS",
        ),
        rssi_threshold_dbm=_optional_finite_float(
            settings.get("analytics_rssi_threshold_dbm"),
            "ANALYTICS_RSSI_THRESHOLD_DBM",
        ),
        snr_threshold_db=_optional_finite_float(
            settings.get("analytics_snr_threshold_db"),
            "ANALYTICS_SNR_THRESHOLD_DB",
        ),
        visit_enabled=_exact_bool(
            settings.get("analytics_visit_enabled", "true"),
            "ANALYTICS_VISIT_ENABLED",
        ),
        visit_min_cohort_size=visit_min_cohort_size,
        visit_max_window_days=visit_max_window_days,
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


def _optional_finite_float(value: Any, name: str) -> float | None:
    if value is None or value == "":
        return None
    if type(value) is bool:
        raise AnalyticsConfigError(f"{name} must be a finite number")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise AnalyticsConfigError(
            f"{name} must be a finite number"
        ) from exc
    if not math.isfinite(parsed):
        raise AnalyticsConfigError(f"{name} must be a finite number")
    return parsed
