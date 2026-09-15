"""Strict normalized portal-header evidence schema for Task-03."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .models import DeviceFingerprintValidationError

PORTAL_HEADER_KEYS = frozenset({
    "platform_family", "mobile_boolean", "browser_runtime_family",
    "webview_or_captive_context", "model_family", "os_major",
    "platform_source", "mobile_source", "runtime_source", "context_source",
    "model_source", "os_major_source", "ua_present", "sec_ch_ua_present",
    "sec_ch_ua_platform_present", "sec_ch_ua_mobile_present",
})

_PLATFORMS = frozenset({"android", "ios", "windows", "macos", "chromeos", "linux"})
_RUNTIMES = frozenset({"android_webview", "chromium", "firefox", "safari_webkit"})
_CONTEXTS = frozenset({"android_webview", "captive_helper"})
_PLATFORM_SOURCES = frozenset({"sec_ch_ua_platform", "user_agent"})
_MOBILE_SOURCES = frozenset({"sec_ch_ua_mobile", "user_agent"})
_RUNTIME_SOURCES = frozenset({"sec_ch_ua", "user_agent", "combined"})
_MODEL = re.compile(r"[0-9A-Za-z][0-9A-Za-z ._()+-]{0,63}")
_MAC_LIKE = re.compile(r"(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}")
_UUID_LIKE = re.compile(r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}")


def validate_portal_headers_v1(value: Mapping[str, Any]) -> Mapping[str, Any]:
    """Validate the exact P1-only ``portal_headers/1`` payload."""
    if set(value) != PORTAL_HEADER_KEYS:
        _fail()
    _nullable_enum(value["platform_family"], _PLATFORMS)
    _nullable_boolean(value["mobile_boolean"])
    _nullable_enum(value["browser_runtime_family"], _RUNTIMES)
    _nullable_enum(value["webview_or_captive_context"], _CONTEXTS)
    model = value["model_family"]
    if model is not None and (
        not isinstance(model, str)
        or _MODEL.fullmatch(model) is None
        or _MAC_LIKE.fullmatch(model) is not None
        or _UUID_LIKE.fullmatch(model) is not None
        or any(ord(character) < 0x20 or ord(character) > 0x7E for character in model)
    ):
        _fail()
    major = value["os_major"]
    if major is not None and (type(major) is not int or not 1 <= major <= 99):
        _fail()
    _nullable_enum(value["platform_source"], _PLATFORM_SOURCES)
    _nullable_enum(value["mobile_source"], _MOBILE_SOURCES)
    _nullable_enum(value["runtime_source"], _RUNTIME_SOURCES)
    for key in ("context_source", "model_source", "os_major_source"):
        _nullable_enum(value[key], frozenset({"user_agent"}))
    for key in (
        "ua_present", "sec_ch_ua_present", "sec_ch_ua_platform_present",
        "sec_ch_ua_mobile_present",
    ):
        if type(value[key]) is not bool:
            _fail()
    for field, source in (
        ("platform_family", "platform_source"),
        ("mobile_boolean", "mobile_source"),
        ("browser_runtime_family", "runtime_source"),
        ("webview_or_captive_context", "context_source"),
        ("model_family", "model_source"),
        ("os_major", "os_major_source"),
    ):
        if (value[field] is None) != (value[source] is None):
            _fail()
    if all(value[key] is None for key in (
        "platform_family", "mobile_boolean", "browser_runtime_family",
        "webview_or_captive_context", "model_family", "os_major",
    )):
        _fail()
    if value["platform_source"] == "sec_ch_ua_platform" and not value["sec_ch_ua_platform_present"]:
        _fail()
    if value["mobile_source"] == "sec_ch_ua_mobile" and not value["sec_ch_ua_mobile_present"]:
        _fail()
    if value["runtime_source"] in {"sec_ch_ua", "combined"} and not value["sec_ch_ua_present"]:
        _fail()
    if value["runtime_source"] == "combined" and not value["ua_present"]:
        _fail()
    if any(value[key] == "user_agent" for key in (
        "platform_source", "mobile_source", "runtime_source", "context_source",
        "model_source", "os_major_source",
    )) and not value["ua_present"]:
        _fail()
    return dict(value)


def _nullable_enum(value: Any, allowed: frozenset[str]) -> None:
    if value is not None and (not isinstance(value, str) or value not in allowed):
        _fail()


def _nullable_boolean(value: Any) -> None:
    if value is not None and type(value) is not bool:
        _fail()


def _fail() -> None:
    raise DeviceFingerprintValidationError("Invalid portal header evidence")
