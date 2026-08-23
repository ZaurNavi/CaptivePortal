"""Strict configuration for Current Network State Foundation v1."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import CurrentStateConfig, CurrentStateConfigError, SITE_ID_PATTERN


DEFAULT_DB_PATH = "/opt/CaptivePortal/data/current_state.sqlite3"


def current_state_config_from_settings(settings: dict[str, Any]) -> CurrentStateConfig:
    enabled = _bool(settings.get("current_state_enabled", "false"), "CURRENT_STATE_ENABLED")
    if not enabled:
        configured_path = settings.get("current_state_db_path", DEFAULT_DB_PATH)
        return CurrentStateConfig(
            enabled=False,
            db_path=configured_path if isinstance(configured_path, str) else DEFAULT_DB_PATH,
            site_ids=(),
            client_ssids=(),
            other_sqlite_paths=_other_sqlite_paths(settings),
            **_values({}),
        )

    db_path = _text(settings.get("current_state_db_path", DEFAULT_DB_PATH), "CURRENT_STATE_DB_PATH")
    defaults = _values(settings)
    site_ids = _site_ids(settings.get("current_state_site_ids", ""))
    client_ssids = _ssid_json(settings.get("current_state_client_ssids_json", "[]"))
    if not site_ids:
        raise CurrentStateConfigError("CURRENT_STATE_SITE_IDS must not be empty")
    if not client_ssids:
        raise CurrentStateConfigError("CURRENT_STATE_CLIENT_SSIDS_JSON must not be empty")
    if not db_path:
        raise CurrentStateConfigError("CURRENT_STATE_DB_PATH must not be empty")
    return CurrentStateConfig(
        enabled=True,
        db_path=db_path,
        site_ids=site_ids,
        client_ssids=client_ssids,
        other_sqlite_paths=_other_sqlite_paths(settings),
        **defaults,
    )


def _values(settings: dict[str, Any]) -> dict[str, Any]:
    client_fresh = _integer(settings, "client_fresh_max_age_seconds", 60, 1, 3600)
    client_stale = _integer(settings, "client_stale_max_age_seconds", 180, 2, 7200)
    ap_fresh = _integer(settings, "ap_fresh_max_age_seconds", 90, 1, 3600)
    ap_stale = _integer(settings, "ap_stale_max_age_seconds", 300, 2, 7200)
    if client_stale <= client_fresh:
        raise CurrentStateConfigError("CURRENT_STATE_CLIENT_STALE_MAX_AGE_SECONDS must exceed fresh age")
    if ap_stale <= ap_fresh:
        raise CurrentStateConfigError("CURRENT_STATE_AP_STALE_MAX_AGE_SECONDS must exceed fresh age")
    return {
        "client_initial_delay_seconds": _number(settings, "client_initial_delay_seconds", 10, 0, 3600),
        "client_interval_seconds": _number(settings, "client_interval_seconds", 60, 10, 300),
        "ap_initial_delay_seconds": _number(settings, "ap_initial_delay_seconds", 15, 0, 3600),
        "ap_interval_seconds": _number(settings, "ap_interval_seconds", 60, 10, 600),
        "request_timeout_seconds": _number(settings, "request_timeout_seconds", 5, 1, 30),
        "client_page_size": _integer(settings, "client_page_size", 500, 1, 500),
        "client_max_pages": _integer(settings, "client_max_pages", 20, 1, 100),
        "client_max_rows": _integer(settings, "client_max_rows", 10_000, 1, 50_000),
        "ap_page_size": _integer(settings, "ap_page_size", 100, 1, 100),
        "ap_max_pages": _integer(settings, "ap_max_pages", 10, 1, 100),
        "ap_max_rows": _integer(settings, "ap_max_rows", 500, 1, 5000),
        "client_fresh_max_age_seconds": client_fresh,
        "client_stale_max_age_seconds": client_stale,
        "ap_fresh_max_age_seconds": ap_fresh,
        "ap_stale_max_age_seconds": ap_stale,
        "history_retention_hours": _integer(settings, "history_retention_hours", 48, 24, 168),
        "history_max_client_rows": _integer(settings, "history_max_client_rows", 5_000_000, 100_000, 20_000_000),
        "cleanup_initial_delay_seconds": _number(settings, "cleanup_initial_delay_seconds", 300, 0, 86400),
        "cleanup_interval_seconds": _number(settings, "cleanup_interval_seconds", 3600, 1, 86400),
        "cleanup_max_cycles_per_run": _integer(settings, "cleanup_max_cycles_per_run", 100, 1, 10_000),
        "cleanup_max_rows_per_transaction": _integer(settings, "cleanup_max_rows_per_transaction", 100_000, 1, 1_000_000),
        "cleanup_max_duration_seconds": _number(settings, "cleanup_max_duration_seconds", 30, 1, 300),
        "sqlite_busy_timeout_ms": _integer(settings, "sqlite_busy_timeout_ms", 500, 0, 5000),
        "shutdown_timeout_seconds": _number(settings, "shutdown_timeout_seconds", 20, 1, 120),
    }


def _other_sqlite_paths(settings: dict[str, Any]) -> tuple[str, ...]:
    keys = (
        "observation_db_path",
        "visit_lifecycle_db_path",
        "visitor_registry_db_path",
        "portal_counter_db_path",
        "public_traffic_db_path",
    )
    values: list[str] = []
    for key in keys:
        value = settings.get(key)
        if isinstance(value, str) and value:
            values.append(str(Path(value)))
    return tuple(dict.fromkeys(values))


def _bool(value: Any, name: str) -> bool:
    if type(value) is bool:
        return value
    if value == "true":
        return True
    if value == "false":
        return False
    raise CurrentStateConfigError(f"{name} must be exactly true or false")


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise CurrentStateConfigError(f"{name} must be a string")
    return value


def _site_ids(value: Any) -> tuple[str, ...]:
    if not isinstance(value, str):
        raise CurrentStateConfigError("CURRENT_STATE_SITE_IDS must be comma-separated")
    items = tuple(part.strip() for part in value.split(",") if part.strip())
    if not items or any(SITE_ID_PATTERN.fullmatch(item) is None for item in items):
        raise CurrentStateConfigError("CURRENT_STATE_SITE_IDS contains an invalid Site ID")
    if len(set(items)) != len(items):
        raise CurrentStateConfigError("CURRENT_STATE_SITE_IDS contains duplicates")
    return items


def _ssid_json(value: Any) -> tuple[str, ...]:
    if not isinstance(value, str):
        raise CurrentStateConfigError("CURRENT_STATE_CLIENT_SSIDS_JSON must be JSON text")
    try:
        parsed = json.loads(value, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (TypeError, ValueError, json.JSONDecodeError, RecursionError) as exc:
        raise CurrentStateConfigError("CURRENT_STATE_CLIENT_SSIDS_JSON is invalid") from exc
    if not isinstance(parsed, list) or not parsed or any(
        not isinstance(item, str)
        or item == ""
        or "\x00" in item
        or not _utf8_within(item, 32)
        for item in parsed
    ):
        raise CurrentStateConfigError("CURRENT_STATE_CLIENT_SSIDS_JSON must be a non-empty string array")
    if len(set(parsed)) != len(parsed):
        raise CurrentStateConfigError("CURRENT_STATE_CLIENT_SSIDS_JSON contains duplicates")
    return tuple(parsed)


def _utf8_within(value: str, maximum: int) -> bool:
    try:
        return len(value.encode("utf-8")) <= maximum
    except UnicodeEncodeError:
        return False


def _number(settings: dict[str, Any], suffix: str, default: float, minimum: float, maximum: float) -> float:
    value = settings.get("current_state_" + suffix, default)
    if type(value) not in {int, float}:
        if not isinstance(value, str):
            raise CurrentStateConfigError(f"CURRENT_STATE_{suffix.upper()} must be numeric")
        try:
            value = float(value)
        except ValueError as exc:
            raise CurrentStateConfigError(f"CURRENT_STATE_{suffix.upper()} must be numeric") from exc
    parsed = float(value)
    if parsed != parsed or not minimum <= parsed <= maximum:
        raise CurrentStateConfigError(f"CURRENT_STATE_{suffix.upper()} is outside bounds")
    return parsed


def _integer(settings: dict[str, Any], suffix: str, default: int, minimum: int, maximum: int) -> int:
    value = settings.get("current_state_" + suffix, default)
    if type(value) is int:
        parsed = value
    elif isinstance(value, str) and value.isdigit():
        parsed = int(value)
    else:
        raise CurrentStateConfigError(f"CURRENT_STATE_{suffix.upper()} must be an integer")
    if not minimum <= parsed <= maximum:
        raise CurrentStateConfigError(f"CURRENT_STATE_{suffix.upper()} is outside bounds")
    return parsed
