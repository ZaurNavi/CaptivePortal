"""Narrow structural dependencies for Visitor Snapshot."""

from __future__ import annotations

from typing import Any, Protocol

from app.models import Result

from .snapshot_models import (
    AuthorizedClientSnapshotRequest,
    SnapshotSubmitOutcome,
)


class ClientSnapshotProvider(Protocol):
    def get_client_snapshot(
        self,
        site_id: str,
        client_mac: str,
        timeout_seconds: float,
    ) -> Result:
        ...


class VisitorSnapshotSubmitter(Protocol):
    def submit(
        self,
        request: AuthorizedClientSnapshotRequest,
    ) -> SnapshotSubmitOutcome:
        ...


class SystemTelemetry(Protocol):
    def safe_emit_system(
        self,
        event: str,
        level: str = "info",
        **fields: Any,
    ) -> bool:
        ...


class SnapshotDataWriter(Protocol):
    available: bool

    def initialize(self) -> bool:
        ...

    def write(self, record: dict[str, Any]) -> None:
        ...

    def close(self) -> None:
        ...
