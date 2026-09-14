"""Sensor-only immutable models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class SensorError(RuntimeError):
    pass


class SensorConfigError(SensorError):
    pass


class SensorPreflightError(SensorError):
    pass


class SensorSpoolError(SensorError):
    pass


@dataclass(frozen=True, slots=True)
class SensorConfig:
    enabled: bool
    interface: str
    producer_id: str
    capture_source_id: str
    site_id: str
    guest_cidrs: tuple[Any, ...]
    dhcp_server_authority: str
    dhcp_option54_authority: str
    evidence_base_url: str
    ca_cert_path: str
    credential_path: str | None
    spool_path: str
    spool_total_budget_bytes: int
    spool_main_db_max_bytes: int
    spool_write_headroom_bytes: int
    spool_max_events: int
    delivery_batch_size: int
    http_timeout_seconds: float
    raw_dedup_max_entries: int
    raw_dedup_horizon_ms: float
    core_ready_host: str
    core_ready_port: int
    core_ready_connect_timeout_seconds: float
    core_ready_poll_interval_seconds: float
    core_ready_max_wait_seconds: float
    eve_max_datagram_bytes: int
    eve_socket_path: str
    eve_socket_wait_seconds: int


@dataclass(frozen=True, slots=True)
class NormalizedEvent:
    endpoint: str
    event_id: str
    source_kind: str
    observed_at: str
    document: dict[str, Any]
