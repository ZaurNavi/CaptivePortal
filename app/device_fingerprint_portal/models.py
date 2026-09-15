"""Immutable Task-03 portal producer models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class PortalEvidenceError(RuntimeError):
    pass


class PortalEvidenceConfigError(PortalEvidenceError):
    pass


@dataclass(frozen=True, slots=True)
class PortalEvidenceConfig:
    enabled: bool
    producer_id: str
    capture_source_id: str
    site_id: str
    guest_cidrs: tuple[Any, ...]
    allowed_ssids: tuple[str, ...]
    evidence_base_url: str
    ca_cert_path: str
    credential_path: str
    queue_max_events: int
    batch_size: int
    queue_max_age_seconds: int
    coalesce_seconds: int
    coalesce_max_entries: int
    connect_timeout_seconds: float
    read_timeout_seconds: float
    transient_cooldown_seconds: int
    reject_cooldown_seconds: int


@dataclass(frozen=True, slots=True)
class PortalEvidenceCandidate:
    source_subtype: str
    observed_at: str
    payload: dict[str, Any]
    quality_state: str


CoalescerKey = tuple[str, str, str, str]


@dataclass(frozen=True, slots=True)
class QueuedPortalEvidence:
    event: dict[str, Any]
    coalescer_key: CoalescerKey
    enqueued_monotonic: float


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    status: str
    cooldown_seconds: int
    http_status: int | None = None
