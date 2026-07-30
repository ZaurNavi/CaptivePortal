"""Stable identifiers for Visitor Snapshot schema version 1."""

from __future__ import annotations

import uuid

from app.common.mac import format_mac_colon


VISITOR_SNAPSHOT_NAMESPACE = uuid.UUID(
    "f69e1190-9a09-55fc-81c5-63fab0ce2703"
)


def build_snapshot_id(
    auth_session_id: str,
    requested_mac: str,
) -> str:
    canonical_mac = format_mac_colon(requested_mac)
    return str(
        uuid.uuid5(
            VISITOR_SNAPSHOT_NAMESPACE,
            f"{auth_session_id}:{canonical_mac}",
        )
    )
