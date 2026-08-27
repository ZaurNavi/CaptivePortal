"""Strict public serializer for Home System Health v1."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .home_health import (
    HomeHealthResult,
    STATUSES,
    _AGGREGATE_MESSAGES,
    _COMPONENTS,
    _MESSAGES,
    _aggregate,
)


class HomeHealthSerializationError(ValueError):
    pass


def serialize_home_health(value: HomeHealthResult) -> dict[str, Any]:
    if (
        value.health_version != 1
        or value.status not in STATUSES
        or value.message != _AGGREGATE_MESSAGES.get(value.status)
    ):
        raise HomeHealthSerializationError("Invalid Home Health result")
    if len(value.components) != 5:
        raise HomeHealthSerializationError("Invalid Home Health component set")
    for item, identity in zip(value.components, _COMPONENTS):
        component_id, label, criticality, scope_type = identity
        if (
            item.id != component_id
            or item.label != label
            or item.status not in STATUSES
            or item.reason_code not in _MESSAGES
            or item.message != _MESSAGES[item.reason_code]
            or item.criticality != criticality
            or item.scope_type != scope_type
            or item.site_id != (value.site_id if scope_type == "site" else None)
        ):
            raise HomeHealthSerializationError(
                "Invalid Home Health component"
            )
    if value.status != _aggregate(value.components):
        raise HomeHealthSerializationError("Invalid Home Health aggregate")
    return {
        "health_version": 1,
        "site_id": value.site_id,
        "evaluated_at": _timestamp(value.evaluated_at),
        "status": value.status,
        "message": value.message,
        "components": [
            {
                "id": item.id,
                "label": item.label,
                "status": item.status,
                "reason_code": item.reason_code,
                "message": item.message,
                "criticality": item.criticality,
                "scope": (
                    {"type": "site", "site_id": item.site_id}
                    if item.scope_type == "site"
                    else {"type": "global"}
                ),
                "evidence_at": _optional_timestamp(item.evidence_at),
                "last_success_at": _optional_timestamp(item.last_success_at),
            }
            for item in value.components
        ],
    }


def _optional_timestamp(value: datetime | None) -> str | None:
    return None if value is None else _timestamp(value)


def _timestamp(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise HomeHealthSerializationError("Health timestamp is invalid")
    return value.astimezone(timezone.utc).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")
