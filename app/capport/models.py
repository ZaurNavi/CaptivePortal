"""Typed contracts used by the CAPPORT module."""

import ipaddress
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit


@dataclass(frozen=True)
class CapportClient:
    site_id: str
    client_ip: str
    client_mac: str
    auth_status: int | None
    active: bool | None


@dataclass(frozen=True)
class CapportState:
    allowed: bool
    captive: bool
    client_found: bool
    client_ip: str
    client: CapportClient | None
    reason: str
    cache_hit: bool
    lookup_failed: bool
    response_time_ms: float


@dataclass(frozen=True)
class CapportConfig:
    site_id: str
    public_base_url: str
    api_path: str
    login_path: str
    allowed_networks: tuple[
        ipaddress.IPv4Network | ipaddress.IPv6Network,
        ...,
    ]
    cache_ttl_seconds: float
    failure_cache_ttl_seconds: float

    @property
    def login_url(self) -> str:
        return f"{self.public_base_url}{self.login_path}"

    @classmethod
    def from_settings(cls, settings: dict[str, Any]) -> "CapportConfig":
        site_id = str(settings.get("capport_site_id", "")).strip()
        base_url = str(
            settings.get("capport_public_base_url", "")
        ).rstrip("/")
        api_path = str(settings.get("capport_api_path", ""))
        login_path = str(settings.get("capport_login_path", ""))
        raw_networks = settings.get(
            "capport_allowed_client_networks",
            (),
        )
        try:
            ttl = float(
                settings.get(
                    "capport_client_cache_ttl_seconds",
                    0,
                )
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "CAPPORT cache TTL must be a number"
            ) from exc
        try:
            failure_ttl = float(
                settings.get(
                    "capport_failure_cache_ttl_seconds",
                    0,
                )
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "CAPPORT failure cache TTL must be a number"
            ) from exc

        if not site_id:
            raise ValueError("CAPPORT_SITE_ID must not be empty")

        parsed_url = urlsplit(base_url)
        if (
            parsed_url.scheme.lower() != "https"
            or not parsed_url.netloc
        ):
            raise ValueError(
                "CAPPORT_PUBLIC_BASE_URL must use https://"
            )
        if not api_path.startswith("/"):
            raise ValueError("CAPPORT_API_PATH must start with /")
        if not login_path.startswith("/"):
            raise ValueError("CAPPORT_LOGIN_PATH must start with /")
        if ttl <= 0:
            raise ValueError(
                "CAPPORT_CLIENT_CACHE_TTL_SECONDS must be positive"
            )
        if failure_ttl <= 0:
            raise ValueError(
                "CAPPORT_FAILURE_CACHE_TTL_SECONDS must be positive"
            )
        if settings.get("host") != "127.0.0.1":
            raise ValueError(
                "CAPPORT requires HOST == 127.0.0.1"
            )

        if isinstance(raw_networks, str):
            raw_networks = (raw_networks,)
        try:
            networks = tuple(
                ipaddress.ip_network(str(value), strict=False)
                for value in raw_networks
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Invalid CAPPORT allowed client network"
            ) from exc
        if not networks:
            raise ValueError(
                "CAPPORT_ALLOWED_CLIENT_NETWORKS must not be empty"
            )

        return cls(
            site_id=site_id,
            public_base_url=base_url,
            api_path=api_path,
            login_path=login_path,
            allowed_networks=networks,
            cache_ttl_seconds=ttl,
            failure_cache_ttl_seconds=failure_ttl,
        )
