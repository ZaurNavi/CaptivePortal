"""Secret-safe configuration for the Device list Current State overlay."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping


_SECRET_PATTERN = re.compile(r"[0-9a-f]{64}")


class DeviceListContextConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True, repr=False)
class DeviceListContextConfig:
    enabled: bool
    cursor_secret: bytes

    def __repr__(self) -> str:
        return (
            "DeviceListContextConfig("
            f"enabled={self.enabled!r}, cursor_secret='[REDACTED]')"
        )


def device_list_context_config_from_settings(
    settings: Mapping[str, Any],
    *,
    admin_config,
) -> DeviceListContextConfig:
    """Parse the dedicated cursor key only when the feature is enabled."""

    if admin_config.device_list_context_enabled is False:
        return DeviceListContextConfig(enabled=False, cursor_secret=b"")
    value = settings.get("web_admin_device_list_context_cursor_secret", "")
    if not isinstance(value, str) or _SECRET_PATTERN.fullmatch(value) is None:
        raise DeviceListContextConfigError(
            "WEB_ADMIN_DEVICE_LIST_CONTEXT_CURSOR_SECRET is invalid"
        )
    secret = bytes.fromhex(value)
    if len(secret) != 32:
        raise DeviceListContextConfigError(
            "WEB_ADMIN_DEVICE_LIST_CONTEXT_CURSOR_SECRET is invalid"
        )
    return DeviceListContextConfig(enabled=True, cursor_secret=secret)
