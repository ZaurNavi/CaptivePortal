"""Immutable NI-02A facts, finite intervals and read results."""

from dataclasses import dataclass


class NetworkAttributionError(RuntimeError):
    """Safe error categories only; never retain a raw frame."""


class NetworkAttributionValidationError(NetworkAttributionError):
    pass


class NetworkAttributionStorageUnavailable(NetworkAttributionError):
    pass


class NetworkAttributionConflict(NetworkAttributionError):
    pass


@dataclass(frozen=True, slots=True)
class NetworkAttributionConfig:
    enabled: bool = False
    db_path: str = "/opt/CaptivePortal/data/network_attribution.sqlite3"
    max_db_bytes: int = 536870912


@dataclass(frozen=True, slots=True)
class NetworkAddressBindingFactV1:
    fact_id: str
    schema_version: int
    site_id: str
    capture_source_id: str
    event_at: str
    ingested_at: str
    message_type: str
    client_mac: str
    ipv4: str
    xid: int
    server_ipv4: str | None
    option54_ipv4: str | None
    lease_seconds: int | None
    authority_class: str


@dataclass(frozen=True, slots=True)
class IPv4BindingIntervalV1:
    binding_id: str
    site_id: str
    capture_source_id: str
    client_mac: str
    ipv4: str
    valid_from: str
    valid_until: str
    last_confirmed_at: str
    lease_expires_at: str
    start_fact_id: str
    last_fact_id: str
    end_reason: str | None


@dataclass(frozen=True, slots=True)
class SourceCoverageIntervalV1:
    coverage_id: str
    coverage_from: str
    coverage_until: str | None
    site_id: str
    capture_source_id: str
    state: str
    reason_code: str | None
    verified_through: str


@dataclass(frozen=True, slots=True)
class NetworkMetadataAttributionResultV1:
    state: str
    reason: str | None = None
    site_id: str | None = None
    client_mac: str | None = None
    ipv4: str | None = None
    event_at: str | None = None
    binding_id: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    attribution_source: str | None = None


@dataclass(frozen=True, slots=True)
class NetworkAttributionHorizonV1:
    state: str
    site_id: str
    first_usable_at: str | None = None
    retained_from: str | None = None
    reason: str | None = None
