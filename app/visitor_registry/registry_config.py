"""Configuration validation for Visitor Device Registry."""

from __future__ import annotations

import os
import stat
from pathlib import Path, PurePosixPath
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .registry_models import (
    MAX_SQLITE_INTEGER,
    RegistryConfig,
    RegistryConfigError,
)


DEFAULT_DB_PATH = "/opt/CaptivePortal/data/visitor_registry.sqlite3"
ALLOWED_AUTO_CREATE_ROOT = Path("/opt/CaptivePortal/data")


def registry_config_from_settings(
    settings: dict[str, Any],
) -> RegistryConfig:
    """Build configuration while normalizing path failures as config errors."""
    try:
        return _registry_config_from_settings(settings)
    except RegistryConfigError:
        raise
    except (OSError, RuntimeError) as exc:
        raise RegistryConfigError(
            "Visitor Registry path validation failed"
        ) from exc


def _registry_config_from_settings(
    settings: dict[str, Any],
) -> RegistryConfig:
    """Build and validate runtime configuration."""
    enabled = _strict_bool(
        settings.get("visitor_registry_enabled", False),
        "VISITOR_REGISTRY_ENABLED",
    )
    if not enabled:
        return RegistryConfig(
            enabled=False,
            db_path=str(settings.get("visitor_registry_db_path", "")),
            source_log_path=str(
                settings.get("visitor_snapshot_log_file", "")
            ),
            source_backup_count=0,
            timezone_name=str(
                settings.get("portal_counter_timezone", "")
            ),
            scan_interval_seconds=0.0,
            shutdown_timeout_seconds=0.0,
            max_line_bytes=0,
        )

    db_path = _absolute_path(
        settings.get("visitor_registry_db_path", DEFAULT_DB_PATH),
        "VISITOR_REGISTRY_DB_PATH",
    )
    source_path = _absolute_path(
        settings.get("visitor_snapshot_log_file", ""),
        "VISITOR_SNAPSHOT_LOG_FILE",
    )
    backup_count = _nonnegative_int(
        settings.get("visitor_snapshot_rotation_backup_count", 20),
        "VISITOR_SNAPSHOT_ROTATION_BACKUP_COUNT",
    )
    timezone_name = _required_string(
        settings.get("portal_counter_timezone", ""),
        "PORTAL_COUNTER_TIMEZONE",
    )
    try:
        ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise RegistryConfigError(
            "PORTAL_COUNTER_TIMEZONE must name a valid timezone"
        ) from exc

    config = RegistryConfig(
        enabled=True,
        db_path=db_path,
        source_log_path=source_path,
        source_backup_count=backup_count,
        timezone_name=timezone_name,
        scan_interval_seconds=_positive_number(
            settings.get("visitor_registry_scan_interval_seconds", 5),
            "VISITOR_REGISTRY_SCAN_INTERVAL_SECONDS",
        ),
        shutdown_timeout_seconds=_positive_number(
            settings.get(
                "visitor_registry_shutdown_timeout_seconds",
                10,
            ),
            "VISITOR_REGISTRY_SHUTDOWN_TIMEOUT_SECONDS",
        ),
        max_line_bytes=_positive_int(
            settings.get("visitor_registry_max_line_bytes", 4_194_304),
            "VISITOR_REGISTRY_MAX_LINE_BYTES",
        ),
    )
    _validate_paths(config, settings)
    return config


def registry_timezone_from_settings(
    settings: dict[str, Any],
) -> str:
    """Return the CLI timezone independently from the runtime feature flag."""
    timezone_name = _required_string(
        settings.get("portal_counter_timezone", ""),
        "PORTAL_COUNTER_TIMEZONE",
    )
    try:
        ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise RegistryConfigError(
            "PORTAL_COUNTER_TIMEZONE must name a valid timezone"
        ) from exc
    return timezone_name


def ensure_registry_parent(config: RegistryConfig) -> None:
    """Create only the approved project data parent, never an arbitrary one."""
    database_path = Path(config.db_path)
    validate_registry_database_target(database_path)
    parent = database_path.parent
    if parent.exists():
        _validate_existing_parent(parent)
        return

    resolved_parent = parent.resolve(strict=False)
    allowed_root = ALLOWED_AUTO_CREATE_ROOT.resolve(strict=False)
    if not _is_within(resolved_parent, allowed_root):
        raise RegistryConfigError(
            "Missing Registry DB parent may only be created under "
            f"{ALLOWED_AUTO_CREATE_ROOT}"
        )
    missing: list[Path] = []
    current = parent
    while not current.exists():
        missing.append(current)
        current = current.parent
    try:
        parent.mkdir(parents=True, mode=0o750, exist_ok=True)
        if os.name == "posix":
            for created in reversed(missing):
                os.chmod(created, 0o750)
    except OSError as exc:
        raise RegistryConfigError(
            "Visitor Registry DB parent could not be created"
        ) from exc
    _validate_existing_parent(parent)


def validate_registry_database_target(database_path: Path) -> None:
    """Reject symlinks and nonregular existing SQLite targets."""
    registry_database_exists(database_path)


def registry_database_exists(database_path: Path) -> bool:
    """Distinguish an absent SQLite path from an unsafe existing target."""
    try:
        path_stat = os.lstat(database_path)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise RegistryConfigError(
            "VISITOR_REGISTRY_DB_PATH is not safely accessible"
        ) from exc
    if stat.S_ISLNK(path_stat.st_mode):
        raise RegistryConfigError(
            "VISITOR_REGISTRY_DB_PATH must not be a symlink"
        )
    if not stat.S_ISREG(path_stat.st_mode):
        raise RegistryConfigError(
            "Existing Visitor Registry DB must be a regular file"
        )
    return True


def _validate_existing_parent(parent: Path) -> None:
    """Require an existing DB parent to be private and writable."""
    try:
        resolved = parent.resolve(strict=True)
        if not resolved.is_dir():
            raise RegistryConfigError(
                "VISITOR_REGISTRY_DB_PATH parent must be a directory"
            )
        if not os.access(resolved, os.W_OK):
            raise RegistryConfigError(
                "VISITOR_REGISTRY_DB_PATH parent is not writable"
            )
        if os.name == "posix":
            mode = stat.S_IMODE(resolved.stat().st_mode)
            if mode & 0o007 or mode & 0o020:
                raise RegistryConfigError(
                    "VISITOR_REGISTRY_DB_PATH parent permissions "
                    "must not allow group write or any access by others"
                )
    except RegistryConfigError:
        raise
    except OSError as exc:
        raise RegistryConfigError(
            "VISITOR_REGISTRY_DB_PATH parent is not safely accessible"
        ) from exc


def _validate_paths(
    config: RegistryConfig,
    settings: dict[str, Any],
) -> None:
    db = Path(config.db_path).resolve(strict=False)
    collisions: list[tuple[str, Path]] = [
        ("VISITOR_SNAPSHOT_LOG_FILE", Path(config.source_log_path)),
    ]
    configured_keys = (
        ("PORTAL_COUNTER_DB_PATH", "portal_counter_db_path"),
        ("PUBLIC_TRAFFIC_DB_PATH", "public_traffic_db_path"),
        ("AUTH_TELEMETRY_LOG_PATH", "auth_telemetry_log_path"),
        ("OMADA_WEBHOOK_LOG_FILE", "omada_webhook_log_file"),
        (
            "OMADA_WEBHOOK_NORMALIZED_LOG_FILE",
            "omada_webhook_normalized_log_file",
        ),
    )
    for label, key in configured_keys:
        value = settings.get(key)
        if isinstance(value, str) and value.strip():
            collisions.append((label, Path(value.strip())))
    for index in range(1, config.source_backup_count + 1):
        collisions.append((
            f"VISITOR_SNAPSHOT_LOG_FILE.{index}",
            Path(f"{config.source_log_path}.{index}"),
        ))

    for label, other in collisions:
        other_resolved = other.resolve(strict=False)
        if db == other_resolved or _same_existing_file(db, other_resolved):
            raise RegistryConfigError(
                f"VISITOR_REGISTRY_DB_PATH conflicts with {label}"
            )

    project_root = Path(__file__).resolve().parents[2]
    public_roots = (
        project_root / "app" / "web" / "static",
        project_root / "app" / "web" / "templates",
    )
    for root in public_roots:
        if _is_within(db, root.resolve(strict=False)):
            raise RegistryConfigError(
                "VISITOR_REGISTRY_DB_PATH must not be in a public web tree"
            )


def _same_existing_file(first: Path, second: Path) -> bool:
    try:
        return first.exists() and second.exists() and os.path.samefile(
            first,
            second,
        )
    except OSError:
        return False


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _strict_bool(value: Any, name: str) -> bool:
    if type(value) is bool:
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    raise RegistryConfigError(f"{name} must be true or false")


def _required_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RegistryConfigError(f"{name} must be a non-empty string")
    return value.strip()


def _absolute_path(value: Any, name: str) -> str:
    text = _required_string(value, name)
    path = Path(text)
    if not path.is_absolute() and not PurePosixPath(text).is_absolute():
        raise RegistryConfigError(f"{name} must be an absolute path")
    return str(path)


def _positive_int(value: Any, name: str) -> int:
    if type(value) is int:
        parsed = value
    elif isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
    else:
        raise RegistryConfigError(f"{name} must be a positive integer")
    if parsed <= 0 or parsed > MAX_SQLITE_INTEGER:
        raise RegistryConfigError(f"{name} must be a positive integer")
    return parsed


def _nonnegative_int(value: Any, name: str) -> int:
    if type(value) is int:
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = int(value.strip())
        except ValueError as exc:
            raise RegistryConfigError(
                f"{name} must be a non-negative integer"
            ) from exc
    else:
        raise RegistryConfigError(
            f"{name} must be a non-negative integer"
        )
    if parsed < 0 or parsed > MAX_SQLITE_INTEGER:
        raise RegistryConfigError(
            f"{name} must be a non-negative integer"
        )
    return parsed


def _positive_number(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise RegistryConfigError(f"{name} must be positive")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise RegistryConfigError(f"{name} must be positive") from exc
    if parsed <= 0 or parsed != parsed or parsed == float("inf"):
        raise RegistryConfigError(f"{name} must be positive")
    return parsed
