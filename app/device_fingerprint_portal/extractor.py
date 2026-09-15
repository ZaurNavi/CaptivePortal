"""Pure bounded User-Agent and low-entropy Client-Hints normalization."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from app.device_fingerprint.validation import format_utc

from .models import PortalEvidenceCandidate

_SUBTYPES = frozenset({"omada_external_portal", "capport_login"})
_LIMITS = {
    "User-Agent": 1024,
    "sec-ch-ua": 1024,
    "sec-ch-ua-platform": 128,
    "sec-ch-ua-mobile": 16,
}
_PLATFORM_CH = re.compile(r'[ \t]*"([0-9A-Za-z ._-]{1,64})"[ \t]*')
_PLATFORM_MAP = {
    "android": "android", "ios": "ios", "windows": "windows",
    "macos": "macos", "chrome os": "chromeos", "linux": "linux",
}
_BRAND_ITEM = re.compile(
    r'[ \t]*"([^"\\,;\r\n]{1,64})"[ \t]*;[ \t]*v[ \t]*=[ \t]*"([0-9A-Za-z._-]{1,32})"[ \t]*'
)
_BRAND_MAP = {
    "android webview": "android_webview",
    "chromium": "chromium", "google chrome": "chromium",
    "microsoft edge": "chromium", "opera": "chromium", "firefox": "firefox",
}
_ANDROID_VERSION = re.compile(r"Android ([1-9][0-9]?)(?:\.[0-9]{1,3}){0,3}", re.IGNORECASE)
_IOS_VERSION = re.compile(
    r"(?<![0-9A-Za-z])(?:CPU iPhone OS|CPU OS) ([1-9][0-9]?)(?:_[0-9]{1,3}){0,3}(?![0-9A-Za-z_.])",
    re.IGNORECASE,
)
_LOCALE = re.compile(r"[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8}){1,2}")
_MODEL_BUILD = re.compile(
    r"(?P<model>[0-9A-Za-z][0-9A-Za-z ._()+\-]{0,63}) +Build/[A-Za-z0-9._-]{1,64}",
    re.IGNORECASE,
)
_MAC_LIKE = re.compile(r"(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}")
_UUID_LIKE = re.compile(r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}")


def extract_portal_evidence_candidate(
    headers: Mapping[str, Any], *, source_subtype: str, observed_at: datetime | str
) -> PortalEvidenceCandidate | None:
    if source_subtype not in _SUBTYPES:
        raise ValueError("Unsupported portal evidence subtype")
    raw = {name: _bounded_header(headers, name, limit) for name, limit in _LIMITS.items()}
    ua = raw["User-Agent"]
    ch_ua = raw["sec-ch-ua"]
    ch_platform = raw["sec-ch-ua-platform"]
    ch_mobile = raw["sec-ch-ua-mobile"]

    ua_platform = _ua_platform(ua)
    parsed_platform = _ch_platform(ch_platform)
    platform = parsed_platform or ua_platform
    platform_source = "sec_ch_ua_platform" if parsed_platform else ("user_agent" if ua_platform else None)

    parsed_mobile = _ch_mobile(ch_mobile)
    ua_mobile = _ua_mobile(ua)
    mobile = parsed_mobile if parsed_mobile is not None else ua_mobile
    mobile_source = "sec_ch_ua_mobile" if parsed_mobile is not None else ("user_agent" if ua_mobile is not None else None)

    ch_runtime = _ch_runtime(ch_ua)
    ua_runtime = _ua_runtime(ua)
    runtime, runtime_source = _reconcile_runtime(ch_runtime, ua_runtime)
    context = _ua_context(ua)
    model, android_majors = _android_details(ua) if platform == "android" else (None, set())
    if platform == "android":
        os_major = next(iter(android_majors)) if len(android_majors) == 1 else None
    elif platform == "ios":
        majors = {int(match.group(1)) for match in _IOS_VERSION.finditer(ua or "")}
        os_major = next(iter(majors)) if len(majors) == 1 else None
    else:
        os_major = None

    payload = {
        "platform_family": platform,
        "mobile_boolean": mobile,
        "browser_runtime_family": runtime,
        "webview_or_captive_context": context,
        "model_family": model,
        "os_major": os_major,
        "platform_source": platform_source,
        "mobile_source": mobile_source,
        "runtime_source": runtime_source,
        "context_source": "user_agent" if context else None,
        "model_source": "user_agent" if model else None,
        "os_major_source": "user_agent" if os_major is not None else None,
        "ua_present": ua is not None,
        "sec_ch_ua_present": ch_ua is not None,
        "sec_ch_ua_platform_present": ch_platform is not None,
        "sec_ch_ua_mobile_present": ch_mobile is not None,
    }
    values = (platform, mobile, runtime, context, model, os_major)
    if all(value is None for value in values):
        return None
    quality = "valid" if platform is not None and runtime is not None and (mobile is not None or context is not None) else "partial"
    timestamp = format_utc(observed_at) if isinstance(observed_at, datetime) else observed_at
    return PortalEvidenceCandidate(source_subtype, timestamp, payload, quality)


def _bounded_header(headers: Mapping[str, Any], name: str, limit: int) -> str | None:
    value = headers.get(name)
    if not isinstance(value, str) or not value or len(value) > limit:
        return None
    if name == "User-Agent" and any(character in value for character in ("\r", "\n", "\x00")):
        return None
    return value


def _ch_platform(value: str | None) -> str | None:
    if value is None:
        return None
    match = _PLATFORM_CH.fullmatch(value)
    return _PLATFORM_MAP.get(match.group(1).lower()) if match else None


def _ch_mobile(value: str | None) -> bool | None:
    if value is None or re.fullmatch(r"[ \t]*\?[01][ \t]*", value) is None:
        return None
    return "?1" in value


def _ch_runtime(value: str | None) -> str | None:
    if value is None:
        return None
    position = 0
    families: set[str] = set()
    count = 0
    while position < len(value):
        match = _BRAND_ITEM.match(value, position)
        if match is None:
            return None
        count += 1
        if count > 16:
            return None
        brand = match.group(1)
        if any(ord(character) < 0x20 or ord(character) > 0x7E for character in brand):
            return None
        family = _BRAND_MAP.get(brand.lower())
        if family:
            families.add(family)
        position = match.end()
        if position == len(value):
            break
        comma = re.match(r'[ \t]*,[ \t]*', value[position:])
        if comma is None:
            return None
        position += comma.end()
        if position == len(value):
            return None
    if "android_webview" in families:
        return "android_webview"
    return next(iter(families)) if len(families) == 1 else None


def _token(value: str | None, literal: str) -> bool:
    if value is None:
        return False
    return re.search(rf"(?<![0-9A-Za-z]){re.escape(literal)}(?![0-9A-Za-z])", value, re.IGNORECASE) is not None


def _ua_platform(ua: str | None) -> str | None:
    for family, literals in (
        ("android", ("Android",)), ("ios", ("iPhone", "iPad", "iPod")),
        ("chromeos", ("CrOS",)), ("windows", ("Windows NT",)),
        ("macos", ("Macintosh", "Mac OS X")), ("linux", ("X11", "Linux")),
    ):
        if any(_token(ua, item) for item in literals):
            return family
    return None


def _ua_mobile(ua: str | None) -> bool | None:
    if _token(ua, "iPhone") or _token(ua, "iPod"):
        return True
    if _token(ua, "Android") and _token(ua, "Mobile"):
        return True
    return None


def _ua_runtime(ua: str | None) -> str | None:
    if ua is None:
        return None
    if _ua_context(ua) == "android_webview":
        return "android_webview"
    if re.search(r"(?<![0-9A-Za-z])Firefox/", ua, re.IGNORECASE):
        return "firefox"
    chromium = re.search(r"(?<![0-9A-Za-z])(?:CriOS|Chrome|Chromium|Edg|OPR)/", ua, re.IGNORECASE)
    if chromium:
        return "chromium"
    if re.search(r"(?<![0-9A-Za-z])Version/", ua, re.IGNORECASE) and re.search(r"(?<![0-9A-Za-z])Safari/", ua, re.IGNORECASE):
        return "safari_webkit"
    return None


def _reconcile_runtime(ch: str | None, ua: str | None) -> tuple[str | None, str | None]:
    if ch == "android_webview" or ua == "android_webview":
        source = "combined" if ch == ua else ("sec_ch_ua" if ch == "android_webview" else "user_agent")
        return "android_webview", source
    if ch is not None and ua is not None:
        return (ch, "combined") if ch == ua else (None, None)
    return (ch, "sec_ch_ua") if ch is not None else ((ua, "user_agent") if ua is not None else (None, None))


def _ua_context(ua: str | None) -> str | None:
    if ua is None:
        return None
    if re.search(r";[ \t]*wv[ \t]*\)", ua, re.IGNORECASE):
        return "android_webview"
    android = re.search(r"(?<![0-9A-Za-z])Android(?![0-9A-Za-z])", ua, re.IGNORECASE)
    if android:
        remainder = ua[android.end():]
        first = re.search(r"Version/4\.0", remainder, re.IGNORECASE)
        second = re.search(r"(?:Chrome|Chromium)/", remainder[first.end():], re.IGNORECASE) if first else None
        third = re.search(r"Mobile Safari/", remainder[first.end() + second.end():], re.IGNORECASE) if first and second else None
        if first and second and third:
            return "android_webview"
    if any(_token(ua, item) for item in ("CaptiveNetworkSupport", "CaptivePortalLogin", "CaptivePortal")):
        return "captive_helper"
    return None


def _android_details(ua: str | None) -> tuple[str | None, set[int]]:
    if ua is None:
        return None, set()
    models: set[str] = set()
    majors: set[int] = set()
    for comment in _non_nested_comments(ua):
        if len(comment) > 256:
            continue
        fields = comment.split(";", 7)
        fields = [field.strip(" \t") for field in fields]
        for index, field in enumerate(fields):
            version = _ANDROID_VERSION.fullmatch(field)
            if version is None:
                continue
            majors.add(int(version.group(1)))
            target = index + 1
            if target < len(fields) and _LOCALE.fullmatch(fields[target]):
                target += 1
            if target >= len(fields):
                continue
            model_match = _MODEL_BUILD.fullmatch(fields[target])
            if model_match is None:
                continue
            model = re.sub(r"[ \t]+", " ", model_match.group("model").strip(" \t"))
            if not model or len(model) > 64 or _MAC_LIKE.fullmatch(model) or _UUID_LIKE.fullmatch(model):
                continue
            models.add(model)
    return (next(iter(models)) if len(models) == 1 else None), majors


def _non_nested_comments(ua: str) -> list[str]:
    comments: list[str] = []
    depth = 0
    start = 0
    nested = False
    for index, character in enumerate(ua):
        if character == "(":
            if depth == 0:
                start = index + 1
                nested = False
            else:
                nested = True
            depth += 1
        elif character == ")" and depth:
            depth -= 1
            if depth == 0 and not nested:
                comments.append(ua[start:index])
                if len(comments) == 4:
                    break
    return comments
