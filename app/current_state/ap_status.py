"""Canonical AP status-code semantics shared by current-state consumers."""

from __future__ import annotations

from typing import Literal


ApStatusClassification = Literal["online", "offline", "other", "unknown"]


def classify_ap_status_code(raw_status: object) -> ApStatusClassification:
    """Classify a sanitized controller AP status without type coercion."""
    if type(raw_status) is not int:
        return "unknown"
    if raw_status == 1:
        return "online"
    if raw_status == 0:
        return "offline"
    return "other"
