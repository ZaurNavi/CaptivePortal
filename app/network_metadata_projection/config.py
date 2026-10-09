"""Default-OFF independent configuration; upstream paths are read-only."""
import hashlib
import os
import re
from dataclasses import asdict, fields
from pathlib import Path
from app.network_metadata.canonical import ni01_canonical_json
from .models import ProjectionConfig, ProjectionValidationError

PREFIX = "NETWORK_METADATA_PROJECTION_"


def configuration_digest(config):
    return hashlib.sha256(ni01_canonical_json(asdict(config))).hexdigest()


def projection_config_from_env(environ=None):
    env = os.environ if environ is None else environ
    enabled = env.get(PREFIX + "ENABLED", "false")
    if enabled not in {"true", "false"}:
        raise ProjectionValidationError()
    if enabled == "false":
        return ProjectionConfig()
    defaults, values = ProjectionConfig(), {"enabled": True}
    for field in fields(defaults):
        name = field.name
        if name == "enabled":
            continue
        key = {"source_db_path": "NETWORK_METADATA_DB_PATH", "registry_db_path": "VISITOR_REGISTRY_DB_PATH"}.get(name, PREFIX + name.upper())
        default = getattr(defaults, name)
        value = env.get(key, str(default))
        if name.endswith("db_path"):
            if not isinstance(value, str) or not value or "\0" in value or not Path(value).is_absolute():
                raise ProjectionValidationError()
        else:
            if not isinstance(value, str) or re.fullmatch(r"[0-9]{1,11}", value) is None:
                raise ProjectionValidationError()
            value = int(value)
            if name == "max_db_bytes":
                if not 67108864 <= value <= 68719476736:
                    raise ProjectionValidationError()
            elif value != default:
                # V1 processing values are frozen, not operator-tunable limits.
                raise ProjectionValidationError()
        values[name] = value
    paths = [Path(values[name]).resolve() for name in ("db_path", "source_db_path", "registry_db_path")]
    if len(set(paths)) != len(paths):
        raise ProjectionValidationError()
    return ProjectionConfig(**values)
