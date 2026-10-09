"""Independent default-OFF NI-02A configuration, not SensorConfig fields."""

import os
import re
from pathlib import Path

from .models import NetworkAttributionConfig, NetworkAttributionValidationError

MAX_DB_BYTES = 2147483648


def network_attribution_config_from_env(environ=None):
    env = os.environ if environ is None else environ
    enabled = env.get("NETWORK_ATTRIBUTION_ENABLED", "false")
    if not isinstance(enabled, str) or enabled not in {"true", "false"}:
        raise NetworkAttributionValidationError("invalid_attribution_config")
    if enabled == "false":
        return NetworkAttributionConfig()
    path = env.get("NETWORK_ATTRIBUTION_DB_PATH", NetworkAttributionConfig().db_path)
    budget = env.get("NETWORK_ATTRIBUTION_MAX_DB_BYTES", "536870912")
    if (not isinstance(path, str) or not path or "\0" in path
            or not (path.startswith("/") or Path(path).is_absolute())
            or not isinstance(budget, str) or re.fullmatch(r"[0-9]{1,10}", budget) is None
            or not 1 <= int(budget) <= MAX_DB_BYTES):
        raise NetworkAttributionValidationError("invalid_attribution_config")
    return NetworkAttributionConfig(True, path, int(budget))
