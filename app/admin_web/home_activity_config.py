"""Fail-open, Site-scoped configuration for the Home Activity panel."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.analytics.validation import format_utc, parse_utc

from .config import AdminWebConfig, SITE_ID_PATTERN


class HomeActivityConfigError(ValueError):
    """Activity-only configuration is invalid; core Admin remains usable."""

    def __init__(self, message: str, *, reason: str = "configuration_error"):
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class HomeActivitySiteContext:
    site_id: str
    timezone: str
    visits_coverage_from_utc: str | None
    traffic_coverage_from_utc: str | None


@dataclass(frozen=True, slots=True)
class HomeActivityConfig:
    enabled: bool
    refresh_seconds: int
    request_timeout_seconds: int
    traffic_fresh_max_age_seconds: int
    traffic_stale_max_age_seconds: int
    sites: Mapping[str, HomeActivitySiteContext]
    guest_ssids: tuple[str, ...]

    def site(self, site_id: str) -> HomeActivitySiteContext | None:
        return self.sites.get(site_id)


def home_activity_config_from_settings(
    settings: Mapping[str, Any],
    *,
    admin_config: AdminWebConfig,
    current_state_config: Any | None,
    now_utc: datetime | None = None,
) -> HomeActivityConfig:
    """Parse Activity settings without creating a second guest-SSID source."""
    enabled = _bool(
        settings.get("web_admin_home_activity_enabled", "false"),
        "WEB_ADMIN_HOME_ACTIVITY_ENABLED",
    )
    # The feature flag is the rollback boundary.  Activity-only values are
    # deliberately not parsed while disabled, so stale/broken optional
    # configuration cannot degrade the rest of Admin Web.
    if not enabled:
        return HomeActivityConfig(False, 60, 30, 90, 180, {}, ())
    refresh = _integer(
        settings.get("web_admin_home_activity_refresh_seconds", "60"),
        "WEB_ADMIN_HOME_ACTIVITY_REFRESH_SECONDS",
        60,
        300,
    )
    request_timeout = _integer(
        settings.get("web_admin_home_activity_request_timeout_seconds", "30"),
        "WEB_ADMIN_HOME_ACTIVITY_REQUEST_TIMEOUT_SECONDS",
        5,
        60,
    )
    fresh = _integer(
        settings.get(
            "web_admin_home_activity_traffic_fresh_max_age_seconds", "90"
        ),
        "WEB_ADMIN_HOME_ACTIVITY_TRAFFIC_FRESH_MAX_AGE_SECONDS",
        1,
        3600,
    )
    stale = _integer(
        settings.get(
            "web_admin_home_activity_traffic_stale_max_age_seconds", "180"
        ),
        "WEB_ADMIN_HOME_ACTIVITY_TRAFFIC_STALE_MAX_AGE_SECONDS",
        2,
        7200,
    )
    if stale <= fresh:
        raise HomeActivityConfigError(
            "Activity Traffic stale age must exceed fresh age"
        )
    if request_timeout <= admin_config.max_query_duration_seconds:
        raise HomeActivityConfigError(
            "Activity request timeout must exceed the Admin query deadline"
        )

    if not admin_config.enabled or not admin_config.home_live_enabled:
        raise HomeActivityConfigError(
            "Home Activity requires Admin Web and Home Live"
        )
    if current_state_config is None or not bool(
        getattr(current_state_config, "enabled", False)
    ):
        raise HomeActivityConfigError(
            "Current State scope is unavailable", reason="scope_mismatch"
        )
    site_ids = tuple(getattr(current_state_config, "site_ids", ()))
    guest_ssids = tuple(getattr(current_state_config, "client_ssids", ()))
    if not site_ids or not guest_ssids:
        raise HomeActivityConfigError(
            "Current State canonical scope is empty", reason="scope_mismatch"
        )

    raw = settings.get("web_admin_home_activity_site_context_json", "{}")
    document = _json_object(raw)
    if not document:
        raise HomeActivityConfigError("Activity Site context must not be empty")
    evaluated = (now_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)
    contexts: dict[str, HomeActivitySiteContext] = {}
    for site_id, value in document.items():
        if SITE_ID_PATTERN.fullmatch(site_id) is None:
            raise HomeActivityConfigError("Activity Site ID is invalid")
        if site_id not in admin_config.allowed_site_ids or site_id not in site_ids:
            raise HomeActivityConfigError(
                "Activity Site scope mismatch", reason="scope_mismatch"
            )
        if not isinstance(value, dict) or set(value) != {
            "timezone",
            "visits_coverage_from_utc",
            "traffic_coverage_from_utc",
        }:
            raise HomeActivityConfigError("Activity Site context is invalid")
        zone_name = value["timezone"]
        if not isinstance(zone_name, str) or not zone_name or zone_name.strip() != zone_name:
            raise HomeActivityConfigError("Activity Site timezone is invalid")
        try:
            ZoneInfo(zone_name)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise HomeActivityConfigError(
                "Activity Site timezone is invalid"
            ) from exc
        visits_from = _coverage(value["visits_coverage_from_utc"], evaluated)
        traffic_from = _coverage(value["traffic_coverage_from_utc"], evaluated)
        contexts[site_id] = HomeActivitySiteContext(
            site_id, zone_name, visits_from, traffic_from
        )
    return HomeActivityConfig(
        True, refresh, request_timeout, fresh, stale, contexts, guest_ssids
    )


def _json_object(value: Any) -> dict[str, Any]:
    if not isinstance(value, str):
        raise HomeActivityConfigError("Activity Site context must be JSON text")

    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise HomeActivityConfigError(
                    "Activity Site context contains duplicate keys"
                )
            result[key] = item
        return result

    try:
        parsed = json.loads(value, object_pairs_hook=pairs)
    except (json.JSONDecodeError, TypeError) as exc:
        raise HomeActivityConfigError("Activity Site context is invalid") from exc
    if not isinstance(parsed, dict):
        raise HomeActivityConfigError("Activity Site context must be an object")
    return parsed


def _coverage(value: Any, now_utc: datetime) -> str | None:
    if value is None:
        return None
    try:
        parsed = parse_utc(value, "coverage_from_utc")
    except Exception as exc:
        raise HomeActivityConfigError("Activity coverage start is invalid") from exc
    if parsed > now_utc:
        raise HomeActivityConfigError("Activity coverage start is in the future")
    return format_utc(parsed)


def _bool(value: Any, name: str) -> bool:
    if type(value) is bool:
        return value
    if value == "true":
        return True
    if value == "false":
        return False
    raise HomeActivityConfigError(f"{name} must be exactly true or false")


def _integer(value: Any, name: str, minimum: int, maximum: int) -> int:
    if type(value) is int:
        result = value
    elif isinstance(value, str) and value.isascii() and value.isdigit():
        result = int(value)
    else:
        raise HomeActivityConfigError(f"{name} must be an integer")
    if not minimum <= result <= maximum:
        raise HomeActivityConfigError(
            f"{name} must be between {minimum} and {maximum}"
        )
    return result
