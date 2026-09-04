"""Strict independent configuration for Traffic Projection v1."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .models import TrafficProjectionConfig, TrafficProjectionConfigError


DEFAULT_DB_PATH = "/opt/CaptivePortal/data/traffic_projection.sqlite3"
DEFAULT_LOCK_PATH = "/opt/CaptivePortal/data/traffic_projection.writer.lock"
DEFAULT_SOURCE_DB_PATH = "/opt/CaptivePortal/data/observations.sqlite3"


def traffic_projection_config_from_settings(
    settings: Mapping[str, Any],
) -> TrafficProjectionConfig:
    enabled = _bool(
        settings.get("traffic_projection_enabled", "false"),
        "TRAFFIC_PROJECTION_ENABLED",
    )
    read_enabled = _bool(
        settings.get("web_admin_traffic_projection_read_enabled", "false"),
        "WEB_ADMIN_TRAFFIC_PROJECTION_READ_ENABLED",
    )
    if not enabled and not read_enabled:
        db_value = settings.get("traffic_projection_db_path", DEFAULT_DB_PATH)
        lock_value = settings.get(
            "traffic_projection_writer_lock_path", DEFAULT_LOCK_PATH
        )
        source_value = settings.get("observation_db_path", DEFAULT_SOURCE_DB_PATH)
        return TrafficProjectionConfig(
            enabled=False,
            db_path=db_value if isinstance(db_value, str) else DEFAULT_DB_PATH,
            writer_lock_path=(
                lock_value if isinstance(lock_value, str) else DEFAULT_LOCK_PATH
            ),
            source_db_path=(
                source_value if isinstance(source_value, str) else DEFAULT_SOURCE_DB_PATH
            ),
            site_ids=(),
        )
    db_path = str(settings.get("traffic_projection_db_path", DEFAULT_DB_PATH))
    lock_path = str(
        settings.get("traffic_projection_writer_lock_path", DEFAULT_LOCK_PATH)
    )
    source_path = str(
        settings.get("observation_db_path", DEFAULT_SOURCE_DB_PATH)
    )
    raw_sites = settings.get("observation_site_ids", "")
    sites = _csv(raw_sites)
    db_path = _absolute(db_path, "TRAFFIC_PROJECTION_DB_PATH")
    lock_path = _absolute(lock_path, "TRAFFIC_PROJECTION_WRITER_LOCK_PATH")
    source_path = _absolute(source_path, "OBSERVATION_DB_PATH")
    resolved = {
        Path(db_path).resolve(strict=False),
        Path(lock_path).resolve(strict=False),
        Path(source_path).resolve(strict=False),
    }
    if len(resolved) != 3:
        raise TrafficProjectionConfigError(
            "Projection, lock and Observation paths must be distinct"
        )
    return TrafficProjectionConfig(
        enabled=enabled,
        db_path=db_path,
        writer_lock_path=lock_path,
        source_db_path=source_path,
        site_ids=sites,
    )


def projection_read_enabled(settings: Mapping[str, Any]) -> bool:
    return _bool(
        settings.get("web_admin_traffic_projection_read_enabled", "false"),
        "WEB_ADMIN_TRAFFIC_PROJECTION_READ_ENABLED",
    )


def _bool(value: Any, name: str) -> bool:
    if type(value) is bool:
        return value
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    raise TrafficProjectionConfigError(f"{name} must be true or false")


def _absolute(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TrafficProjectionConfigError(f"{name} must be an absolute path")
    path = Path(value.strip())
    if not path.is_absolute():
        raise TrafficProjectionConfigError(f"{name} must be an absolute path")
    return str(path)


def _csv(value: Any) -> tuple[str, ...]:
    sites = _optional_csv(value)
    if not sites:
        raise TrafficProjectionConfigError(
            "OBSERVATION_SITE_IDS is required when Traffic Projection is enabled"
        )
    return sites


def _optional_csv(value: Any) -> tuple[str, ...]:
    if not isinstance(value, str):
        raise TrafficProjectionConfigError("OBSERVATION_SITE_IDS must be CSV")
    if not value.strip():
        return ()
    parts = value.split(",")
    if any(not part.strip() for part in parts):
        raise TrafficProjectionConfigError("OBSERVATION_SITE_IDS contains an empty value")
    return tuple(dict.fromkeys(part.strip() for part in parts))
