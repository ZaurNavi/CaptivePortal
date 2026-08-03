from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple, Optional
import os
import re
import math


def parse_bool(value: object, *, name: str) -> bool:
    if type(value) is bool:
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    raise ValueError(f"{name} must be boolean")


def parse_int_strict(value: object, *, name: str) -> int:
    if type(value) is int and not isinstance(value, bool):
        return int(value)
    if isinstance(value, str) and value != "" and re.fullmatch(r"\d+", value.strip()):
        return int(value.strip())
    raise ValueError(f"{name} must be integer (int type or decimal string)")


def parse_float_strict(value: object, *, name: str) -> float:
    if type(value) in (int, float) and not isinstance(value, bool):
        f = float(value)
        if math.isfinite(f):
            return f
        raise ValueError(f"{name} must be finite")
    if isinstance(value, str) and value.strip() != "":
        try:
            f = float(value.strip())
        except Exception:
            raise ValueError(f"{name} must be numeric") from None
        if math.isfinite(f):
            return f
        raise ValueError(f"{name} must be finite")
    raise ValueError(f"{name} must be finite float or numeric string")


def parse_float_list_strict(raw: object, *, name: str) -> Tuple[float, ...]:
    if not isinstance(raw, str):
        raise ValueError(f"{name} must be CSV string")
    parts = raw.split(",")
    if any(p == "" for p in parts):
        raise ValueError(f"{name} contains empty elements")
    items = []
    for p in parts:
        try:
            f = float(p)
        except Exception:
            raise ValueError(f"{name} contains non-numeric element")
        if not math.isfinite(f) or f < 0:
            raise ValueError(f"{name} contains invalid value")
        items.append(f)
    return tuple(items)


def parse_ssid_list_strict(raw: object, *, name: str) -> Tuple[str, ...]:
    if not isinstance(raw, str):
        raise ValueError(f"{name} must be CSV string")
    parts = [p.strip() for p in raw.split(",")]
    if any(p == "" for p in parts):
        raise ValueError(f"{name} contains empty SSID value")
    return tuple(parts)


@dataclass(frozen=True)
class PendingSessionCleanerConfig:
    enabled: bool
    site_id: Optional[str]
    ssids: Tuple[str, ...]
    initial_delay_seconds: float
    scan_interval_seconds: float
    max_scan_duration_seconds: float
    min_uptime_seconds: int
    portal_grace_seconds: float
    uptime_regression_tolerance_seconds: float
    request_timeout_seconds: float
    get_retry_delays_seconds: Tuple[float, ...]
    verify_delays_seconds: Tuple[float, ...]
    page_size: int
    max_pages: int
    max_clients: int
    max_actions_per_scan: int
    action_cooldown_seconds: float
    max_actions_per_mac_per_hour: int
    log_file: str
    rotation_max_bytes: int
    rotation_backup_count: int
    shutdown_timeout_seconds: float

    @classmethod
    def from_settings(cls, settings: dict) -> "PendingSessionCleanerConfig":
        # Strict: parse and validate enabled flag
        raw_enabled = settings.get("pending_session_cleaner_enabled", "false")
        enabled = parse_bool(raw_enabled, name="pending_session_cleaner_enabled")

        # If disabled -> return safe defaults without reading other cleaner parameters
        if not enabled:
            return cls(
                enabled=False,
                site_id=None,
                ssids=tuple(),
                initial_delay_seconds=10.0,
                scan_interval_seconds=60.0,
                max_scan_duration_seconds=50.0,
                min_uptime_seconds=120,
                portal_grace_seconds=45.0,
                uptime_regression_tolerance_seconds=5.0,
                request_timeout_seconds=5.0,
                get_retry_delays_seconds=(1.0, 3.0),
                verify_delays_seconds=(1.0, 4.0),
                page_size=500,
                max_pages=20,
                max_clients=10000,
                max_actions_per_scan=1,
                action_cooldown_seconds=180.0,
                max_actions_per_mac_per_hour=3,
                log_file="/opt/CaptivePortal/logs/pending_session_cleaner.log",
                rotation_max_bytes=52428800,
                rotation_backup_count=20,
                shutdown_timeout_seconds=20.0,
            )

        # enabled == True -> strict validation
        site_id = settings.get("capport_site_id")
        if not isinstance(site_id, str) or not site_id.strip():
            raise ValueError("pending_session_cleaner enabled but capport_site_id is missing")

        ssids_raw = settings.get("pending_session_cleaner_ssids")
        ssids = parse_ssid_list_strict(ssids_raw, name="pending_session_cleaner_ssids")

        initial_delay_seconds = parse_float_strict(settings.get("pending_session_cleaner_initial_delay_seconds"), name="pending_session_cleaner_initial_delay_seconds")
        scan_interval_seconds = parse_float_strict(settings.get("pending_session_cleaner_scan_interval_seconds"), name="pending_session_cleaner_scan_interval_seconds")
        max_scan_duration_seconds = parse_float_strict(settings.get("pending_session_cleaner_max_scan_duration_seconds"), name="pending_session_cleaner_max_scan_duration_seconds")
        min_uptime_seconds = parse_int_strict(settings.get("pending_session_cleaner_min_uptime_seconds"), name="pending_session_cleaner_min_uptime_seconds")
        portal_grace_seconds = parse_float_strict(settings.get("pending_session_cleaner_portal_grace_seconds"), name="pending_session_cleaner_portal_grace_seconds")
        uptime_regression_tolerance_seconds = parse_float_strict(settings.get("pending_session_cleaner_uptime_regression_tolerance_seconds"), name="pending_session_cleaner_uptime_regression_tolerance_seconds")
        request_timeout_seconds = parse_float_strict(settings.get("pending_session_cleaner_request_timeout_seconds"), name="pending_session_cleaner_request_timeout_seconds")

        get_retry_delays = parse_float_list_strict(settings.get("pending_session_cleaner_get_retry_delays_seconds"), name="pending_session_cleaner_get_retry_delays_seconds")
        verify_delays = parse_float_list_strict(settings.get("pending_session_cleaner_verify_delays_seconds"), name="pending_session_cleaner_verify_delays_seconds")

        page_size = parse_int_strict(settings.get("pending_session_cleaner_page_size"), name="pending_session_cleaner_page_size")
        max_pages = parse_int_strict(settings.get("pending_session_cleaner_max_pages"), name="pending_session_cleaner_max_pages")
        max_clients = parse_int_strict(settings.get("pending_session_cleaner_max_clients"), name="pending_session_cleaner_max_clients")
        max_actions_per_scan = parse_int_strict(settings.get("pending_session_cleaner_max_actions_per_scan"), name="pending_session_cleaner_max_actions_per_scan")
        action_cooldown_seconds = parse_float_strict(settings.get("pending_session_cleaner_action_cooldown_seconds"), name="pending_session_cleaner_action_cooldown_seconds")
        max_actions_per_mac_per_hour = parse_int_strict(settings.get("pending_session_cleaner_max_actions_per_mac_per_hour"), name="pending_session_cleaner_max_actions_per_mac_per_hour")

        log_file = settings.get("pending_session_cleaner_log_file")
        if not isinstance(log_file, str) or not os.path.isabs(log_file):
            raise ValueError("pending_session_cleaner_log_file must be absolute path")

        rotation_max_bytes = parse_int_strict(settings.get("pending_session_cleaner_rotation_max_bytes"), name="pending_session_cleaner_rotation_max_bytes")
        rotation_backup_count = parse_int_strict(settings.get("pending_session_cleaner_rotation_backup_count"), name="pending_session_cleaner_rotation_backup_count")
        shutdown_timeout_seconds = parse_float_strict(settings.get("pending_session_cleaner_shutdown_timeout_seconds"), name="pending_session_cleaner_shutdown_timeout_seconds")

        # Additional non-negative checks requested
        if initial_delay_seconds < 0:
            raise ValueError("initial_delay_seconds must be >= 0")
        if portal_grace_seconds < 0:
            raise ValueError("portal_grace_seconds must be >= 0")
        if uptime_regression_tolerance_seconds < 0:
            raise ValueError("uptime_regression_tolerance_seconds must be >= 0")
        if action_cooldown_seconds < 0:
            raise ValueError("action_cooldown_seconds must be >= 0")

        # Value constraints
        if scan_interval_seconds <= 0:
            raise ValueError("scan_interval_seconds must be > 0")
        if max_scan_duration_seconds <= 0:
            raise ValueError("max_scan_duration_seconds must be > 0")
        if min_uptime_seconds <= 0:
            raise ValueError("min_uptime_seconds must be > 0")
        if request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be > 0")
        if len(get_retry_delays) != 2:
            raise ValueError("get_retry_delays_seconds must contain exactly two values")
        if len(verify_delays) != 2:
            raise ValueError("verify_delays_seconds must contain exactly two values")
        if page_size <= 0 or max_pages <= 0 or max_clients <= 0 or max_actions_per_scan <= 0 or max_actions_per_mac_per_hour <= 0:
            raise ValueError("page_size, max_pages, max_clients, max_actions_per_scan and max_actions_per_mac_per_hour must be > 0")
        if rotation_max_bytes <= 0 or rotation_backup_count <= 0:
            raise ValueError("rotation values must be > 0")
        if shutdown_timeout_seconds <= 0:
            raise ValueError("shutdown_timeout_seconds must be > 0")

        return cls(
            enabled=True,
            site_id=site_id.strip(),
            ssids=ssids,
            initial_delay_seconds=initial_delay_seconds,
            scan_interval_seconds=scan_interval_seconds,
            max_scan_duration_seconds=max_scan_duration_seconds,
            min_uptime_seconds=min_uptime_seconds,
            portal_grace_seconds=portal_grace_seconds,
            uptime_regression_tolerance_seconds=uptime_regression_tolerance_seconds,
            request_timeout_seconds=request_timeout_seconds,
            get_retry_delays_seconds=get_retry_delays,
            verify_delays_seconds=verify_delays,
            page_size=page_size,
            max_pages=max_pages,
            max_clients=max_clients,
            max_actions_per_scan=max_actions_per_scan,
            action_cooldown_seconds=action_cooldown_seconds,
            max_actions_per_mac_per_hour=max_actions_per_mac_per_hour,
            log_file=log_file,
            rotation_max_bytes=rotation_max_bytes,
            rotation_backup_count=rotation_backup_count,
            shutdown_timeout_seconds=shutdown_timeout_seconds,
        )
