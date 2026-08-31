"""Validated, secret-safe configuration for Admin Web v1."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from typing import Any, Mapping

SITE_ID_PATTERN = re.compile(r"[0-9a-f]{24}")
USERNAME_PATTERN = re.compile(r"[A-Za-z0-9._@-]{1,128}")
_SALT_PATTERN = re.compile(r"[A-Za-z0-9]{8,64}")
_LOWER_HEX_PATTERN = re.compile(r"[0-9a-f]+")
_PBKDF2_DIGEST_LENGTHS = {
    "sha256": 64,
    "sha384": 96,
    "sha512": 128,
}
_PBKDF2_MIN_ITERATIONS = 100_000
_PBKDF2_MAX_ITERATIONS = 2_000_000
_SCRYPT_MIN_N = 16_384
_SCRYPT_MAX_N = 65_536
_SCRYPT_MAX_R = 8
_SCRYPT_MAX_P = 2
_SCRYPT_MAX_WORK = 1_048_576
_SCRYPT_MAX_MEMORY_BYTES = 67_108_864


class AdminWebConfigError(ValueError):
    """Enabled Admin Web configuration is invalid and must fail closed."""


@dataclass(frozen=True, slots=True, repr=False)
class AdminWebConfig:
    enabled: bool
    username: str
    password_hash: str
    allowed_networks: tuple[
        ipaddress.IPv4Network | ipaddress.IPv6Network, ...
    ]
    allowed_site_ids: frozenset[str]
    default_site_id: str
    require_https: bool
    session_idle_seconds: int
    session_absolute_seconds: int
    login_window_seconds: int
    login_max_failures: int
    login_lock_seconds: int
    preauth_csrf_ttl_seconds: int
    max_preauth_states: int
    max_sessions: int
    max_login_trackers: int
    max_post_bytes: int
    max_query_string_bytes: int
    max_username_chars: int
    max_password_chars: int
    max_csrf_chars: int
    max_next_chars: int
    max_cursor_chars: int
    max_filter_chars: int
    max_concurrent_queries: int
    max_query_duration_seconds: int
    max_response_bytes: int
    device_page_size: int
    visit_page_size: int
    observation_page_size: int
    observation_max_window_hours: int
    home_live_enabled: bool
    home_live_refresh_seconds: int
    home_live_request_timeout_seconds: int
    current_state_page_size: int
    home_traffic_enabled: bool
    home_traffic_refresh_seconds: int
    home_traffic_request_timeout_seconds: int
    home_traffic_page_size: int
    home_traffic_fresh_max_age_seconds: int
    home_traffic_stale_max_age_seconds: int
    home_traffic_max_ap_skew_seconds: int
    traffic_enabled: bool
    traffic_history_enabled: bool
    traffic_statistics_enabled: bool
    traffic_peak_enabled: bool
    traffic_by_ap_enabled: bool
    traffic_refresh_seconds: int
    traffic_request_timeout_seconds: int

    def __repr__(self) -> str:
        return (
            "AdminWebConfig("
            f"enabled={self.enabled!r}, username='[REDACTED]', "
            "password_hash='[REDACTED]', "
            f"allowed_network_count={len(self.allowed_networks)}, "
            f"allowed_site_count={len(self.allowed_site_ids)}, "
            f"require_https={self.require_https!r}, "
            f"max_sessions={self.max_sessions})"
        )


def admin_web_config_from_settings(
    settings: Mapping[str, Any],
) -> AdminWebConfig:
    """Parse repository settings without normalizing security identities."""
    enabled = _exact_bool(
        settings.get("web_admin_enabled", "false"),
        "WEB_ADMIN_ENABLED",
    )
    require_https = _exact_bool(
        settings.get("web_admin_require_https", "true"),
        "WEB_ADMIN_REQUIRE_HTTPS",
    )
    home_live_enabled = _exact_bool(
        settings.get("web_admin_home_live_enabled", "false"),
        "WEB_ADMIN_HOME_LIVE_ENABLED",
    )
    home_traffic_enabled = _exact_bool(
        settings.get("web_admin_home_traffic_enabled", "false"),
        "WEB_ADMIN_HOME_TRAFFIC_ENABLED",
    )
    traffic_enabled = _exact_bool(
        settings.get("web_admin_traffic_enabled", "false"),
        "WEB_ADMIN_TRAFFIC_ENABLED",
    )
    traffic_history_enabled = _exact_bool(
        settings.get("web_admin_traffic_history_enabled", "false"),
        "WEB_ADMIN_TRAFFIC_HISTORY_ENABLED",
    )
    traffic_statistics_enabled = _exact_bool(
        settings.get("web_admin_traffic_statistics_enabled", "false"),
        "WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED",
    )
    traffic_peak_enabled = _exact_bool(
        settings.get("web_admin_traffic_peak_enabled", "false"),
        "WEB_ADMIN_TRAFFIC_PEAK_ENABLED",
    )
    traffic_by_ap_enabled = _exact_bool(
        settings.get("web_admin_traffic_by_ap_enabled", "false"),
        "WEB_ADMIN_TRAFFIC_BY_AP_ENABLED",
    )
    username = _string(settings.get("web_admin_username", ""), "WEB_ADMIN_USERNAME")
    password_hash = _string(
        settings.get("web_admin_password_hash", ""),
        "WEB_ADMIN_PASSWORD_HASH",
    )
    networks = _networks(
        settings.get(
            "web_admin_allowed_networks",
            "127.0.0.1/32,::1/128",
        )
    )
    sites = _sites(settings.get("web_admin_allowed_site_ids", ""))
    default_site = _string(
        settings.get("web_admin_default_site_id", ""),
        "WEB_ADMIN_DEFAULT_SITE_ID",
    )

    values = {
        "session_idle_seconds": _bounded_int(settings, "session_idle_seconds", 1800, 60, 86400),
        "session_absolute_seconds": _bounded_int(settings, "session_absolute_seconds", 28800, 60, 604800),
        "login_window_seconds": _bounded_int(settings, "login_window_seconds", 300, 60, 3600),
        "login_max_failures": _bounded_int(settings, "login_max_failures", 5, 1, 50),
        "login_lock_seconds": _bounded_int(settings, "login_lock_seconds", 900, 60, 86400),
        "preauth_csrf_ttl_seconds": _bounded_int(settings, "preauth_csrf_ttl_seconds", 300, 60, 1800),
        "max_preauth_states": _bounded_int(settings, "max_preauth_states", 256, 16, 4096),
        "max_sessions": _bounded_int(settings, "max_sessions", 128, 1, 1024),
        "max_login_trackers": _bounded_int(settings, "max_login_trackers", 512, 16, 8192),
        "max_post_bytes": _bounded_int(settings, "max_post_bytes", 16384, 1024, 65536),
        "max_query_string_bytes": _bounded_int(settings, "max_query_string_bytes", 8192, 256, 32768),
        "max_username_chars": _bounded_int(settings, "max_username_chars", 128, 1, 128),
        "max_password_chars": _bounded_int(settings, "max_password_chars", 1024, 1, 4096),
        "max_csrf_chars": _bounded_int(settings, "max_csrf_chars", 256, 32, 1024),
        "max_next_chars": _bounded_int(settings, "max_next_chars", 2048, 1, 4096),
        "max_cursor_chars": _bounded_int(settings, "max_cursor_chars", 4096, 16, 16384),
        "max_filter_chars": _bounded_int(settings, "max_filter_chars", 256, 1, 1024),
        "max_concurrent_queries": _bounded_int(settings, "max_concurrent_queries", 2, 1, 8),
        "max_query_duration_seconds": _bounded_int(settings, "max_query_duration_seconds", 10, 1, 30),
        "max_response_bytes": _bounded_int(settings, "max_response_bytes", 1048576, 65536, 4194304),
        "device_page_size": _bounded_int(settings, "device_page_size", 100, 1, 500),
        "visit_page_size": _bounded_int(settings, "visit_page_size", 100, 1, 500),
        "observation_page_size": _bounded_int(settings, "observation_page_size", 100, 1, 500),
        "observation_max_window_hours": _bounded_int(settings, "observation_max_window_hours", 24, 1, 168),
        "home_live_refresh_seconds": _bounded_int(settings, "home_live_refresh_seconds", 60, 60, 300),
        "home_live_request_timeout_seconds": _bounded_int(settings, "home_live_request_timeout_seconds", 20, 5, 60),
        "current_state_page_size": _bounded_int(settings, "current_state_page_size", 100, 1, 250),
        "home_traffic_refresh_seconds": _bounded_int(settings, "home_traffic_refresh_seconds", 60, 60, 300),
        "home_traffic_request_timeout_seconds": _bounded_int(settings, "home_traffic_request_timeout_seconds", 20, 5, 60),
        "home_traffic_page_size": _bounded_int(settings, "home_traffic_page_size", 100, 1, 250),
        "home_traffic_fresh_max_age_seconds": _bounded_int(settings, "home_traffic_fresh_max_age_seconds", 90, 30, 300),
        "home_traffic_stale_max_age_seconds": _bounded_int(settings, "home_traffic_stale_max_age_seconds", 180, 30, 600),
        "home_traffic_max_ap_skew_seconds": _bounded_int(settings, "home_traffic_max_ap_skew_seconds", 60, 10, 180),
        "traffic_refresh_seconds": _bounded_int(settings, "traffic_refresh_seconds", 60, 60, 300),
        "traffic_request_timeout_seconds": _bounded_int(settings, "traffic_request_timeout_seconds", 20, 5, 60),
    }
    if values["session_absolute_seconds"] < values["session_idle_seconds"]:
        raise AdminWebConfigError(
            "WEB_ADMIN_SESSION_ABSOLUTE_SECONDS must not be shorter than idle"
        )
    if values["home_live_request_timeout_seconds"] <= values["max_query_duration_seconds"]:
        raise AdminWebConfigError(
            "WEB_ADMIN_HOME_LIVE_REQUEST_TIMEOUT_SECONDS must exceed WEB_ADMIN_MAX_QUERY_DURATION_SECONDS"
        )
    if values["home_traffic_request_timeout_seconds"] <= values["max_query_duration_seconds"]:
        raise AdminWebConfigError(
            "WEB_ADMIN_HOME_TRAFFIC_REQUEST_TIMEOUT_SECONDS must exceed WEB_ADMIN_MAX_QUERY_DURATION_SECONDS"
        )
    if values["traffic_request_timeout_seconds"] <= values["max_query_duration_seconds"]:
        raise AdminWebConfigError(
            "WEB_ADMIN_TRAFFIC_REQUEST_TIMEOUT_SECONDS must exceed WEB_ADMIN_MAX_QUERY_DURATION_SECONDS"
        )
    if values["home_traffic_stale_max_age_seconds"] < values["home_traffic_fresh_max_age_seconds"]:
        raise AdminWebConfigError(
            "WEB_ADMIN_HOME_TRAFFIC_STALE_MAX_AGE_SECONDS must not be shorter than fresh"
        )
    if home_live_enabled and not enabled:
        raise AdminWebConfigError(
            "WEB_ADMIN_HOME_LIVE_ENABLED requires WEB_ADMIN_ENABLED=true"
        )
    if home_traffic_enabled and (not enabled or not home_live_enabled):
        raise AdminWebConfigError(
            "WEB_ADMIN_HOME_TRAFFIC_ENABLED requires WEB_ADMIN_ENABLED=true and WEB_ADMIN_HOME_LIVE_ENABLED=true"
        )
    if traffic_enabled and not enabled:
        raise AdminWebConfigError(
            "WEB_ADMIN_TRAFFIC_ENABLED requires WEB_ADMIN_ENABLED=true"
        )
    if traffic_history_enabled and (not enabled or not traffic_enabled):
        raise AdminWebConfigError(
            "WEB_ADMIN_TRAFFIC_HISTORY_ENABLED requires "
            "WEB_ADMIN_ENABLED=true and WEB_ADMIN_TRAFFIC_ENABLED=true"
        )
    if traffic_statistics_enabled and (
        not enabled or not traffic_enabled or not traffic_history_enabled
    ):
        raise AdminWebConfigError(
            "WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED requires "
            "WEB_ADMIN_ENABLED=true, WEB_ADMIN_TRAFFIC_ENABLED=true and "
            "WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true"
        )
    if traffic_peak_enabled and (
        not enabled
        or not traffic_enabled
        or not traffic_history_enabled
        or not traffic_statistics_enabled
    ):
        raise AdminWebConfigError(
            "WEB_ADMIN_TRAFFIC_PEAK_ENABLED requires WEB_ADMIN_ENABLED=true, "
            "WEB_ADMIN_TRAFFIC_ENABLED=true, "
            "WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true and "
            "WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=true"
        )
    if traffic_by_ap_enabled and (
        not enabled or not traffic_enabled or not traffic_history_enabled
    ):
        raise AdminWebConfigError(
            "WEB_ADMIN_TRAFFIC_BY_AP_ENABLED requires WEB_ADMIN_ENABLED=true, "
            "WEB_ADMIN_TRAFFIC_ENABLED=true and "
            "WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true"
        )

    if enabled:
        if USERNAME_PATTERN.fullmatch(username) is None:
            raise AdminWebConfigError("WEB_ADMIN_USERNAME is invalid")
        if len(username) > values["max_username_chars"]:
            raise AdminWebConfigError("WEB_ADMIN_USERNAME is too long")
        _validate_password_hash(password_hash)
        if not sites:
            raise AdminWebConfigError("WEB_ADMIN_ALLOWED_SITE_IDS must not be empty")
        if SITE_ID_PATTERN.fullmatch(default_site) is None:
            raise AdminWebConfigError("WEB_ADMIN_DEFAULT_SITE_ID is invalid")
        if default_site not in sites:
            raise AdminWebConfigError(
                "WEB_ADMIN_DEFAULT_SITE_ID must belong to the Site allowlist"
            )
    elif default_site and SITE_ID_PATTERN.fullmatch(default_site) is None:
        raise AdminWebConfigError("WEB_ADMIN_DEFAULT_SITE_ID is invalid")

    return AdminWebConfig(
        enabled=enabled,
        username=username,
        password_hash=password_hash,
        allowed_networks=networks,
        allowed_site_ids=sites,
        default_site_id=default_site,
        require_https=require_https,
        home_live_enabled=home_live_enabled,
        home_traffic_enabled=home_traffic_enabled,
        traffic_enabled=traffic_enabled,
        traffic_history_enabled=traffic_history_enabled,
        traffic_statistics_enabled=traffic_statistics_enabled,
        traffic_peak_enabled=traffic_peak_enabled,
        traffic_by_ap_enabled=traffic_by_ap_enabled,
        **values,
    )


def _validate_password_hash(value: str) -> None:
    if not value or value.strip() != value:
        raise AdminWebConfigError("WEB_ADMIN_PASSWORD_HASH is invalid")
    parts = value.split("$")
    if len(parts) != 3:
        raise AdminWebConfigError("WEB_ADMIN_PASSWORD_HASH is invalid")
    method, salt, digest = parts
    if _SALT_PATTERN.fullmatch(salt) is None:
        raise AdminWebConfigError("WEB_ADMIN_PASSWORD_HASH is invalid")
    if method.startswith("scrypt:"):
        _validate_scrypt_method(method, digest)
        return
    if method.startswith("pbkdf2:"):
        _validate_pbkdf2_method(method, digest)
        return
    raise AdminWebConfigError("WEB_ADMIN_PASSWORD_HASH is invalid")


def _validate_scrypt_method(method: str, digest: str) -> None:
    parts = method.split(":")
    if len(parts) != 4 or parts[0] != "scrypt":
        raise AdminWebConfigError("WEB_ADMIN_PASSWORD_HASH is invalid")
    n = _canonical_positive_int(parts[1])
    r = _canonical_positive_int(parts[2])
    p = _canonical_positive_int(parts[3])
    if (
        n < _SCRYPT_MIN_N
        or n > _SCRYPT_MAX_N
        or n & (n - 1) != 0
        or r > _SCRYPT_MAX_R
        or p > _SCRYPT_MAX_P
        or n * r * p > _SCRYPT_MAX_WORK
        or 128 * n * r > _SCRYPT_MAX_MEMORY_BYTES
    ):
        raise AdminWebConfigError("WEB_ADMIN_PASSWORD_HASH is invalid")
    _validate_digest(digest, expected_length=128)


def _validate_pbkdf2_method(method: str, digest: str) -> None:
    parts = method.split(":")
    if len(parts) != 3 or parts[0] != "pbkdf2":
        raise AdminWebConfigError("WEB_ADMIN_PASSWORD_HASH is invalid")
    algorithm = parts[1]
    expected_length = _PBKDF2_DIGEST_LENGTHS.get(algorithm)
    iterations = _canonical_positive_int(parts[2])
    if (
        expected_length is None
        or not _PBKDF2_MIN_ITERATIONS <= iterations <= _PBKDF2_MAX_ITERATIONS
    ):
        raise AdminWebConfigError("WEB_ADMIN_PASSWORD_HASH is invalid")
    _validate_digest(digest, expected_length=expected_length)


def _canonical_positive_int(value: str) -> int:
    if re.fullmatch(r"[1-9][0-9]{0,7}", value) is None:
        raise AdminWebConfigError("WEB_ADMIN_PASSWORD_HASH is invalid")
    return int(value)


def _validate_digest(value: str, *, expected_length: int) -> None:
    if (
        len(value) != expected_length
        or _LOWER_HEX_PATTERN.fullmatch(value) is None
    ):
        raise AdminWebConfigError("WEB_ADMIN_PASSWORD_HASH is invalid")


def _string(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise AdminWebConfigError(f"{name} must be a string")
    return value


def _exact_bool(value: Any, name: str) -> bool:
    if type(value) is bool:
        return value
    if value == "true":
        return True
    if value == "false":
        return False
    raise AdminWebConfigError(f"{name} must be exactly true or false")


def _csv(value: Any, name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if allow_empty and (value == "" or value == () or value == [] or value is None):
        return ()
    if isinstance(value, str):
        items = tuple(part.strip() for part in value.split(","))
    elif isinstance(value, (tuple, list)):
        items = tuple(part if isinstance(part, str) else "" for part in value)
    else:
        raise AdminWebConfigError(f"{name} must be a comma-separated list")
    if not items or any(not item for item in items):
        raise AdminWebConfigError(f"{name} must not contain empty values")
    if len(set(items)) != len(items):
        raise AdminWebConfigError(f"{name} must not contain duplicates")
    return items


def _networks(value: Any) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    items = _csv(value, "WEB_ADMIN_ALLOWED_NETWORKS")
    parsed = []
    for item in items:
        if "/" not in item:
            raise AdminWebConfigError(
                "WEB_ADMIN_ALLOWED_NETWORKS contains an invalid CIDR"
            )
        try:
            parsed.append(ipaddress.ip_network(item, strict=True))
        except ValueError as exc:
            raise AdminWebConfigError(
                "WEB_ADMIN_ALLOWED_NETWORKS contains an invalid CIDR"
            ) from exc
    if len(set(parsed)) != len(parsed):
        raise AdminWebConfigError(
            "WEB_ADMIN_ALLOWED_NETWORKS must not contain duplicates"
        )
    return tuple(parsed)


def _sites(value: Any) -> frozenset[str]:
    if value == "" or value == () or value == [] or value is None:
        return frozenset()
    if isinstance(value, str):
        items = tuple(value.split(","))
    elif isinstance(value, (tuple, list)):
        items = tuple(item if isinstance(item, str) else "" for item in value)
    else:
        raise AdminWebConfigError(
            "WEB_ADMIN_ALLOWED_SITE_IDS must be a comma-separated list"
        )
    if not items or any(not item for item in items):
        raise AdminWebConfigError(
            "WEB_ADMIN_ALLOWED_SITE_IDS must not contain empty values"
        )
    if len(set(items)) != len(items):
        raise AdminWebConfigError(
            "WEB_ADMIN_ALLOWED_SITE_IDS must not contain duplicates"
        )
    if any(SITE_ID_PATTERN.fullmatch(item) is None for item in items):
        raise AdminWebConfigError(
            "WEB_ADMIN_ALLOWED_SITE_IDS contains an invalid Site ID"
        )
    return frozenset(items)


def _bounded_int(
    settings: Mapping[str, Any],
    suffix: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    name = "WEB_ADMIN_" + suffix.upper()
    value = settings.get("web_admin_" + suffix, default)
    if type(value) is int:
        parsed = value
    elif isinstance(value, str) and value.isdigit():
        parsed = int(value)
    else:
        raise AdminWebConfigError(f"{name} must be an integer")
    if not minimum <= parsed <= maximum:
        raise AdminWebConfigError(
            f"{name} must be between {minimum} and {maximum}"
        )
    return parsed
