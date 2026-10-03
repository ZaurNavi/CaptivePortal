"""Default-disabled configuration; no disabled-module validation cascade."""

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class IntegrationConfig:
    enabled: bool = False
    db_path: str = "/opt/CaptivePortal/data/device_fingerprint_integration.sqlite3"
    evidence_db_path: str = "/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3"
    classification_db_path: str = "/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3"
    control_plane_db_path: str = "/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3"


def integration_config_from_settings(settings):
    enabled = settings.get("device_fingerprint_integration_enabled", False)
    if isinstance(enabled, str) and enabled.lower() in {"true", "false"}:
        enabled = enabled.lower() == "true"
    if type(enabled) is not bool:
        raise ValueError("Invalid DEVICE_FINGERPRINT_INTEGRATION_ENABLED")
    if not enabled:
        return IntegrationConfig()
    defaults = IntegrationConfig()
    paths = {}
    for field in ("db_path", "evidence_db_path", "classification_db_path", "control_plane_db_path"):
        key = "device_fingerprint_integration_db_path" if field == "db_path" else f"device_fingerprint_{field}"
        value = settings.get(key, getattr(defaults, field))
        if not isinstance(value, str) or not value or not Path(value).is_absolute():
            raise ValueError(f"Invalid {key}")
        paths[field] = str(Path(value).resolve())
    # Dedicated files, including symlink/hardlink aliases; never mutate other domains.
    others = list(paths.values())[1:] + [str(Path(settings[key]).resolve()) for key in (
        "visitor_registry_db_path", "visit_lifecycle_db_path", "current_state_db_path",
    ) if settings.get(key)]
    for other in others:
        if paths["db_path"] == other or (Path(paths["db_path"]).exists() and Path(other).exists()
                                         and os.path.samefile(paths["db_path"], other)):
            raise ValueError("Integration database must be a dedicated file")
    if len(set(paths.values())) != 4:
        raise ValueError("Fingerprint database paths must be distinct")
    return IntegrationConfig(enabled=True, **paths)
