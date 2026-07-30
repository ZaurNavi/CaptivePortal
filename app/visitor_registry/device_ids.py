"""Stable Visitor Device Registry identifiers."""

from __future__ import annotations

import uuid

from app.common.mac import format_mac_colon


VISITOR_DEVICE_NAMESPACE = uuid.UUID(
    "afca1c95-15b2-446d-b10d-ab47f0090b76"
)


def build_device_id(mac: str) -> str:
    """Return the permanent schema-v1 UUIDv5 for a canonical device MAC."""
    canonical_mac = format_mac_colon(mac)
    return str(uuid.uuid5(VISITOR_DEVICE_NAMESPACE, canonical_mac))
