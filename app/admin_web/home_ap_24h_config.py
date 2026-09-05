"""Fail-closed enabled configuration for the independent AP-24H panel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class HomeAp24ConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class HomeAp24Config:
    enabled: bool
    refresh_seconds: int
    request_timeout_seconds: int
    page_size: int = 20


def home_ap_24h_config_from_settings(settings: Mapping[str, Any], *, admin_config) -> HomeAp24Config:
    enabled = _bool(settings.get("web_admin_home_ap_24h_enabled", "false"))
    if not enabled:
        return HomeAp24Config(False, 120, 30)
    refresh = _integer(settings.get("web_admin_home_ap_24h_refresh_seconds", "120"), 60, 600)
    timeout = _integer(settings.get("web_admin_home_ap_24h_request_timeout_seconds", "30"), 5, 60)
    if not admin_config.enabled:
        raise HomeAp24ConfigError("AP-24H requires Admin Web")
    if timeout <= admin_config.max_query_duration_seconds:
        raise HomeAp24ConfigError("AP-24H timeout must exceed the Admin query deadline")
    return HomeAp24Config(True, refresh, timeout)


def _bool(value: object) -> bool:
    if value in (True, "true"):
        return True
    if value in (False, "false"):
        return False
    raise HomeAp24ConfigError("AP-24H enabled must be exactly true or false")


def _integer(value: object, minimum: int, maximum: int) -> int:
    try:
        selected = int(value)
    except (TypeError, ValueError) as exc:
        raise HomeAp24ConfigError("AP-24H setting must be an integer") from exc
    if isinstance(value, bool) or not minimum <= selected <= maximum:
        raise HomeAp24ConfigError("AP-24H setting is outside bounds")
    return selected
