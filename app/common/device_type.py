"""Canonical read-time Device Type key normalization."""

from __future__ import annotations


DEVICE_TYPE_KEY_MAX_UTF8_BYTES = 128


def normalize_device_type_key(source_value: object) -> str | None:
    """Return the bounded lexical key derived from one raw Device Type value."""

    if source_value is None or not isinstance(source_value, str):
        return None
    trimmed = source_value.strip()
    if not trimmed or "\x00" in trimmed:
        return None
    try:
        source_bytes = trimmed.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        return None
    if len(source_bytes) > DEVICE_TYPE_KEY_MAX_UTF8_BYTES:
        return None
    canonical = trimmed.casefold()
    if not canonical or "\x00" in canonical:
        return None
    try:
        canonical_bytes = canonical.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        return None
    if len(canonical_bytes) > DEVICE_TYPE_KEY_MAX_UTF8_BYTES:
        return None
    return canonical
