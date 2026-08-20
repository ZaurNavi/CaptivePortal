"""Explicit JSON serialization boundary for approved Analytics DTOs."""

from __future__ import annotations

import math
from dataclasses import fields, is_dataclass
from types import MappingProxyType
from typing import Any, Mapping


class AnalyticsSerializationError(TypeError):
    """A value is outside the approved aggregate DTO contract."""


def serialize_analytics_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise AnalyticsSerializationError("non-finite number")
        return value
    if is_dataclass(value) and type(value).__module__ == "app.analytics.models":
        return {
            item.name: serialize_analytics_value(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, (Mapping, MappingProxyType)):
        result = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise AnalyticsSerializationError("mapping key is not a string")
            result[key] = serialize_analytics_value(item)
        return result
    if isinstance(value, tuple):
        return [serialize_analytics_value(item) for item in value]
    if isinstance(value, frozenset):
        serialized = [serialize_analytics_value(item) for item in value]
        try:
            return sorted(serialized)
        except TypeError as exc:
            raise AnalyticsSerializationError(
                "frozenset items are not deterministically sortable"
            ) from exc
    raise AnalyticsSerializationError("unsupported Analytics value type")
