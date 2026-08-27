"""Fail-open configuration for the Home System Health feature."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .config import AdminWebConfig


class HomeHealthConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class HomeHealthConfig:
    enabled: bool
    refresh_seconds: int
    request_timeout_seconds: int
    auth_evidence_max_age_seconds: int


def home_health_config_from_settings(
    settings: Mapping[str, Any], *, admin_config: AdminWebConfig
) -> HomeHealthConfig:
    enabled = _bool(
        settings.get("web_admin_home_health_enabled", "false"),
        "WEB_ADMIN_HOME_HEALTH_ENABLED",
    )
    if not enabled:
        return HomeHealthConfig(False, 60, 20, 86400)
    refresh = _integer(
        settings.get("web_admin_home_health_refresh_seconds", "60"),
        "WEB_ADMIN_HOME_HEALTH_REFRESH_SECONDS",
        60,
        300,
    )
    request_timeout = _integer(
        settings.get("web_admin_home_health_request_timeout_seconds", "20"),
        "WEB_ADMIN_HOME_HEALTH_REQUEST_TIMEOUT_SECONDS",
        5,
        60,
    )
    evidence_age = _integer(
        settings.get(
            "web_admin_home_health_auth_evidence_max_age_seconds", "86400"
        ),
        "WEB_ADMIN_HOME_HEALTH_AUTH_EVIDENCE_MAX_AGE_SECONDS",
        300,
        604800,
    )
    if not admin_config.enabled:
        raise HomeHealthConfigError("Home Health requires Admin Web")
    if request_timeout <= admin_config.max_query_duration_seconds:
        raise HomeHealthConfigError(
            "Home Health request timeout must exceed Admin query deadline"
        )
    return HomeHealthConfig(True, refresh, request_timeout, evidence_age)


def _bool(value: Any, name: str) -> bool:
    if type(value) is bool:
        return value
    if value == "true":
        return True
    if value == "false":
        return False
    raise HomeHealthConfigError(f"{name} must be exactly true or false")


def _integer(value: Any, name: str, minimum: int, maximum: int) -> int:
    if type(value) is int:
        result = value
    elif isinstance(value, str) and value.isascii() and value.isdigit():
        result = int(value)
    else:
        raise HomeHealthConfigError(f"{name} must be an integer")
    if not minimum <= result <= maximum:
        raise HomeHealthConfigError(
            f"{name} must be between {minimum} and {maximum}"
        )
    return result
