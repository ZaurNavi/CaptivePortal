"""Source-family health transitions and bounded heartbeats."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Callable

from app.device_fingerprint.validation import format_utc

from .models import NormalizedEvent, SensorConfig

SOURCE_KINDS = ("dhcp", "tcp_syn", "tls_client", "quic_client")
HEARTBEAT_SECONDS = 300.0


class SourceHealthTracker:
    def __init__(self, config: SensorConfig, *, monotonic: Callable[[], float], now=None) -> None:
        self.config = config
        self.monotonic = monotonic
        self.now = now or (lambda: datetime.now(timezone.utc))
        self._states: dict[str, tuple[str, str | None, float]] = {}

    def transition(self, source_kind: str, status: str, reason: str | None) -> NormalizedEvent | None:
        if source_kind not in SOURCE_KINDS or status not in {"available", "unavailable", "unsupported"}:
            raise ValueError("source health transition is invalid")
        current = self.monotonic()
        previous = self._states.get(source_kind)
        if previous and previous[:2] == (status, reason) and current - previous[2] < HEARTBEAT_SECONDS:
            return None
        self._states[source_kind] = (status, reason, current)
        identity = str(uuid.uuid4())
        observed = format_utc(self.now())
        return NormalizedEvent("source_health", identity, source_kind, observed, {
            "source_health_event_id": identity,
            "site_id": self.config.site_id,
            "capture_source_id": self.config.capture_source_id,
            "source_kind": source_kind,
            "status": status,
            "reason_code": reason,
            "observed_at": observed,
        })

    def all(self, status: str, reason: str | None) -> list[NormalizedEvent]:
        return [event for kind in SOURCE_KINDS if (event := self.transition(kind, status, reason)) is not None]

    def raw(self, status: str, reason: str | None) -> list[NormalizedEvent]:
        return [event for kind in SOURCE_KINDS[:2] if (event := self.transition(kind, status, reason)) is not None]

    def suricata(self, status: str, reason: str | None) -> list[NormalizedEvent]:
        return [event for kind in SOURCE_KINDS[2:] if (event := self.transition(kind, status, reason)) is not None]

    @property
    def ready(self) -> bool:
        return all(self._states.get(kind, (None, None, 0))[0] == "available" for kind in SOURCE_KINDS)
