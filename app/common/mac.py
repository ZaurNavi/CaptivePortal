"""One strict MAC parser with explicit output formats."""

from __future__ import annotations

import re
from typing import Any


_MAC_HEX_PATTERN = re.compile(r"[0-9A-F]{12}")


def parse_mac(value: Any) -> str:
    """Return the immutable twelve-hex-digit representation."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("MAC address is required")
    clean = re.sub(r"[:.\-\s]", "", value).upper()
    if _MAC_HEX_PATTERN.fullmatch(clean) is None:
        raise ValueError("Invalid MAC address")
    return clean


def _format_mac(value: Any, separator: str) -> str:
    clean = parse_mac(value)
    return separator.join(
        clean[index:index + 2]
        for index in range(0, len(clean), 2)
    )


def format_mac_colon(value: Any) -> str:
    """Return ``AA:BB:CC:DD:EE:FF``."""
    return _format_mac(value, ":")


def format_mac_hyphen(value: Any) -> str:
    """Return ``AA-BB-CC-DD-EE-FF``."""
    return _format_mac(value, "-")
