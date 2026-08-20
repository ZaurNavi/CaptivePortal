"""Validated security and resource limits for the internal Analytics API."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from typing import Any, Mapping


_SITE_ID = re.compile(r"[0-9a-f]{24}")


class AnalyticsApiConfigError(ValueError):
    """Analytics API configuration is invalid and must fail closed."""


@dataclass(frozen=True, slots=True, repr=False)
class AnalyticsApiConfig:
    enabled: bool
    bearer_token: str
    allowed_networks: tuple[
        ipaddress.IPv4Network | ipaddress.IPv6Network, ...
    ]
    allowed_site_ids: frozenset[str]
    max_concurrent_requests: int
    max_response_bytes: int

    def __repr__(self) -> str:
        return (
            "AnalyticsApiConfig("
            f"enabled={self.enabled!r}, bearer_token='[REDACTED]', "
            f"allowed_network_count={len(self.allowed_networks)}, "
            f"allowed_site_count={len(self.allowed_site_ids)}, "
            f"max_concurrent_requests={self.max_concurrent_requests}, "
            f"max_response_bytes={self.max_response_bytes})"
        )


def analytics_api_config_from_settings(
    settings: Mapping[str, Any],
) -> AnalyticsApiConfig:
    enabled = _exact_bool(
        settings.get("analytics_api_enabled", "false"),
        "ANALYTICS_API_ENABLED",
    )
    token_value = settings.get("analytics_api_bearer_token", "")
    if not isinstance(token_value, str):
        raise AnalyticsApiConfigError(
            "ANALYTICS_API_BEARER_TOKEN must be a string"
        )
    token = token_value.strip()
    if enabled and len(token) < 32:
        raise AnalyticsApiConfigError(
            "ANALYTICS_API_BEARER_TOKEN must contain at least 32 characters"
        )
    networks = _networks(
        settings.get(
            "analytics_api_allowed_networks",
            "127.0.0.1/32,::1/128",
        )
    )
    sites = _sites(settings.get("analytics_api_allowed_site_ids", ""))
    if enabled and not sites:
        raise AnalyticsApiConfigError(
            "ANALYTICS_API_ALLOWED_SITE_IDS must not be empty"
        )
    concurrent = _bounded_int(
        settings.get("analytics_api_max_concurrent_requests", 2),
        "ANALYTICS_API_MAX_CONCURRENT_REQUESTS",
        minimum=1,
        maximum=8,
    )
    response_bytes = _bounded_int(
        settings.get("analytics_api_max_response_bytes", 1_048_576),
        "ANALYTICS_API_MAX_RESPONSE_BYTES",
        minimum=65_536,
        maximum=4_194_304,
    )
    return AnalyticsApiConfig(
        enabled=enabled,
        bearer_token=token,
        allowed_networks=networks,
        allowed_site_ids=sites,
        max_concurrent_requests=concurrent,
        max_response_bytes=response_bytes,
    )


def _exact_bool(value: Any, name: str) -> bool:
    if type(value) is bool:
        return value
    if value == "true":
        return True
    if value == "false":
        return False
    raise AnalyticsApiConfigError(f"{name} must be exactly true or false")


def _csv(value: Any, name: str) -> tuple[str, ...]:
    if isinstance(value, str):
        items = tuple(item.strip() for item in value.split(","))
    elif isinstance(value, (tuple, list)):
        items = tuple(
            item.strip() if isinstance(item, str) else "" for item in value
        )
    else:
        raise AnalyticsApiConfigError(f"{name} must be a comma-separated list")
    if not items or any(not item for item in items):
        raise AnalyticsApiConfigError(f"{name} must not contain empty values")
    if len(set(items)) != len(items):
        raise AnalyticsApiConfigError(f"{name} must not contain duplicates")
    return items


def _networks(
    value: Any,
) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    items = _csv(value, "ANALYTICS_API_ALLOWED_NETWORKS")
    parsed = []
    for item in items:
        if "/" not in item:
            raise AnalyticsApiConfigError(
                "ANALYTICS_API_ALLOWED_NETWORKS contains an invalid CIDR"
            )
        try:
            parsed.append(ipaddress.ip_network(item, strict=True))
        except ValueError as exc:
            raise AnalyticsApiConfigError(
                "ANALYTICS_API_ALLOWED_NETWORKS contains an invalid CIDR"
            ) from exc
    return tuple(parsed)


def _sites(value: Any) -> frozenset[str]:
    if value == "" or value == () or value == []:
        return frozenset()
    items = _csv(value, "ANALYTICS_API_ALLOWED_SITE_IDS")
    if any(_SITE_ID.fullmatch(item) is None for item in items):
        raise AnalyticsApiConfigError(
            "ANALYTICS_API_ALLOWED_SITE_IDS contains an invalid Site ID"
        )
    return frozenset(items)


def _bounded_int(
    value: Any,
    name: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    if type(value) is int:
        parsed = value
    elif isinstance(value, str) and value.isdigit():
        parsed = int(value)
    else:
        raise AnalyticsApiConfigError(f"{name} must be an integer")
    if not minimum <= parsed <= maximum:
        raise AnalyticsApiConfigError(
            f"{name} must be between {minimum} and {maximum}"
        )
    return parsed
