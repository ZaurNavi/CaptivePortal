"""Closed NI-02B constants and safe errors; no import-time composition."""
from dataclasses import dataclass

ALGORITHM = "dti-ni-02b-projection-v1"
PROJECTION_TRANSACTION_HEADROOM_BYTES = 16777216
ATTRIBUTION_STATES = frozenset({"resolved", "ambiguous", "unattributed", "unavailable",
    "outside_historical_horizon", "invalid", "unsupported_address_family", "endpoint_absent"})
BINDING_STATES = frozenset({"authoritative", "not_yet_registry_resolved", "registry_unavailable"})
RUNTIME_STATES = frozenset({"initializing", "usable", "degraded", "source_unavailable", "attribution_unavailable",
    "registry_degraded", "capacity_waiting_reader", "capacity_halted", "blocked_conflict", "stopping"})
CONFLICTS = frozenset({"source_observation_identity_conflict", "resolved_endpoint_outside_capture_scope",
    "attribution_query_contract_invalid", "edge_semantic_conflict", "registry_identity_conflict", "checkpoint_source_conflict"})


class ProjectionError(RuntimeError):
    def __init__(self, reason="projection_store_unavailable"):
        self.reason = reason
        super().__init__(reason)


class ProjectionUnavailable(ProjectionError):
    pass


class ProjectionValidationError(ProjectionError):
    def __init__(self):
        super().__init__("invalid_projection_request")


class ProjectionConflict(ProjectionError):
    def __init__(self, reason):
        if reason not in CONFLICTS:
            raise ProjectionValidationError()
        super().__init__(reason)


class ProjectionCapacity(ProjectionUnavailable):
    pass


@dataclass(frozen=True, slots=True)
class ProjectionConfig:
    enabled: bool = False
    db_path: str = "/opt/CaptivePortal/data/network_metadata_projection.sqlite3"
    max_db_bytes: int = 17179869184
    batch_max_observations: int = 256
    poll_interval_seconds: int = 1
    attribution_retry_interval_seconds: int = 30
    attribution_retry_batch_size: int = 500
    registry_reconcile_interval_seconds: int = 60
    registry_reconcile_batch_size: int = 500
    retention_interval_seconds: int = 3600
    retention_batch_size: int = 5000
    retention_max_batches_per_pass: int = 20
    shutdown_timeout_seconds: int = 20
    source_db_path: str = "/opt/CaptivePortal/data/network_metadata.sqlite3"
    registry_db_path: str = "/opt/CaptivePortal/data/visitor_registry.sqlite3"


@dataclass(frozen=True, slots=True, repr=False)
class RegistryEvaluation:
    state: str
    device_id: str | None = None
    record_updated_at: str | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class NetworkMetadataProjectionResultV1:
    observation_id: str
    src_attribution_state: str
    dst_attribution_state: str
    emitted_edge_count: int
    projection_state: str
    safe_reason: str | None = None


@dataclass(frozen=True, slots=True, repr=False)
class DeviceNetworkMetadataEdgeV1:
    edge_id: str
    schema_version: int
    site_id: str
    device_id: str | None
    client_mac: str
    identity_binding_state: str
    identity_binding_evaluated_at: str
    device_id_bound_at: str | None
    event_at: str
    projected_at: str
    device_endpoint: dict
    peer_endpoint: dict
    device_endpoint_role: str
    peer_scope: str
    direction: str
    source_observation_ref: str
    source_event_identity: str
    source_event_family: str
    source_generation_id: str
    capture_source_id: str
    network_scope_id: str
    network_scope_state: str
    capture_scope_binding_digest: str
    attribution_state: str
    attribution_source: str
    attribution_binding_id: str
    attribution_valid_from: str
    attribution_valid_until: str
    peer_attribution_state: str
    peer_attribution_binding_id: str | None
    projection_contract_version: int
    projection_algorithm_version: str
    projection_run_id: str


@dataclass(slots=True, repr=False)
class PreparedDisposition:
    source: object
    edges: list
    pending: dict | None
    result: NetworkMetadataProjectionResultV1

    def __iter__(self):
        yield self.source
        yield self.edges
        yield self.pending
