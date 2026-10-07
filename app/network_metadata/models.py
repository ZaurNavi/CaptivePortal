"""Immutable NI-01 contracts, constants and safe task-local errors."""
from dataclasses import dataclass, field
from enum import Enum

SCHEMA_VERSION = 1
SOURCE_TYPE = "suricata"
SOURCE_CONTRACT_VERSION = "suricata-eve-v1"
LOGICAL_SOURCE_ID = "suricata-dti-ni-v1"
NORMALIZER_VERSION = "network-metadata-normalizer-v1"
NI01_OBSERVATION_NAMESPACE_UUID = "ce2387da-5bc4-5c4e-9e6a-6de970889764"
MAX_DB_BYTES = 8589934592
MIN_DB_BYTES = 67108864
MAX_RECORD_BYTES = 1048576
MIN_RECORD_BYTES = 4096
MAX_BATCH_RECORDS = 256
MAX_BATCH_BYTES = 1048576
SOURCE_READ_CHUNK_BYTES = 65536
CONTINUITY_ANCHOR_MAX_BYTES = 4096
BUSY_TIMEOUT_MS = 500
WAL_AUTOCHECKPOINT_PAGES = 1000
JOURNAL_SIZE_LIMIT_BYTES = 67108864
TRANSACTION_HEADROOM_MIN_BYTES = 16777216
HEALTH_HEARTBEAT_SECONDS = 60
FAULT_AGGREGATION_WINDOW_SECONDS = 300
CAPTURE_HEALTH_FRESHNESS_SECONDS = 600
RETENTION_PARENT_BATCH_ROWS = 5000
RETENTION_MAX_BATCHES_PER_PASS = 20
SENSITIVE_RETENTION_DAYS = 14
CORE_RETENTION_DAYS = 30
HEALTH_RETENTION_DAYS = 45
FAULT_RETENTION_DAYS = 45
LINEAGE_RETENTION_DAYS = 90
INT64_MAX = 9223372036854775807
UINT64_MAX = 18446744073709551615
FAULT_CATEGORIES = frozenset({
    "invalid_utf8", "invalid_json", "duplicate_json_member", "non_object_json",
    "schema_invalid", "record_too_large", "partial_final_record", "unexpected_family",
    "pre_binding_event", "outside_intended_scope", "unsupported_address_family_for_scope",
    "retention_expired_event",
    "source_record_identity_conflict", "normalizer_determinism_conflict",
    "replay_identity_evidence_expired", "source_continuity_mismatch", "observed_truncation",
    "storage_unavailable", "storage_capacity_headroom_exhausted",
})
CONFLICT_CATEGORIES = frozenset({"source_record_identity_conflict",
    "normalizer_determinism_conflict", "replay_identity_evidence_expired"})


class NetworkMetadataError(Exception):
    def __init__(self):
        super().__init__("Network metadata operation unavailable")


class NetworkMetadataConfigError(NetworkMetadataError):
    pass


class NetworkMetadataValidationError(NetworkMetadataError):
    def __init__(self, category="schema_invalid"):
        self.category = category if category in FAULT_CATEGORIES else "schema_invalid"
        super().__init__()


class NetworkMetadataStorageUnavailable(NetworkMetadataError):
    pass


class NetworkMetadataStorageCorrupt(NetworkMetadataStorageUnavailable):
    pass


class NetworkMetadataStorageLimit(NetworkMetadataStorageUnavailable):
    pass


class NetworkMetadataWriterUnavailable(NetworkMetadataError):
    pass


class NetworkMetadataConflict(NetworkMetadataError):
    def __init__(self, category):
        self.category = category if category in CONFLICT_CATEGORIES else "source_record_identity_conflict"
        super().__init__()


class Presence(str, Enum):
    OBSERVED_RETAINED = "observed_retained"
    NOT_OBSERVED = "not_observed"
    EXPIRED = "expired"


class Health(str, Enum):
    USABLE = "usable"
    PARTIAL = "partial"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CaptureScopeBindingV1:
    schema_version: int
    capture_source_id: str
    site_id: str
    network_scope_id: str
    ipv4_cidrs: tuple[str, ...]
    valid_from_utc: str
    binding_digest: str


@dataclass(frozen=True, slots=True)
class NetworkMetadataConfig:
    enabled: bool = False
    source_path: str | None = None
    db_path: str | None = None
    capture_scope_binding: CaptureScopeBindingV1 | None = None
    max_db_bytes: int = MAX_DB_BYTES
    max_record_bytes: int = MAX_RECORD_BYTES
    batch_max_records: int = MAX_BATCH_RECORDS
    batch_max_bytes: int = MAX_BATCH_BYTES
    poll_interval_seconds: int = 1
    configuration_digest: str | None = None

    @property
    def writer_lock_path(self):
        return self.db_path + ".writer.lock" if self.db_path is not None else None


@dataclass(frozen=True, slots=True)
class SourceRecordIdentityV1:
    source_generation_id: str
    record_start_byte_offset: int


@dataclass(frozen=True, slots=True)
class SourceGenerationV1:
    source_generation_id: str
    logical_source_id: str
    host_boot_id: str
    st_dev: int
    st_ino: int
    generation_start_offset: int
    committed_byte_offset: int
    end_offset: int | None
    capture_scope_binding_schema_version: int
    capture_scope_binding_digest: str
    binding_valid_from_utc: str
    opened_at_utc: str
    closed_at_utc: str | None
    close_reason: str | None
    coverage_gap_possible: bool
    processing_state: str = "runnable"
    blocked_reason_code: str | None = None
    blocked_at_utc: str | None = None
    blocked_record_start_byte_offset: int | None = None

    def __post_init__(self):
        from .validation import integer, ni_timestamp, canonical_uuid, digest
        canonical_uuid(self.source_generation_id, 4)
        canonical_uuid(self.host_boot_id)
        integer(self.st_dev)
        integer(self.st_ino)
        integer(self.capture_scope_binding_schema_version, 1, 1)
        digest(self.capture_scope_binding_digest)
        ni_timestamp(self.binding_valid_from_utc, canonical=True)
        ni_timestamp(self.opened_at_utc, canonical=True)
        closure = (self.closed_at_utc, self.end_offset, self.close_reason)
        if any(value is not None for value in closure):
            if any(value is None for value in closure):
                raise NetworkMetadataValidationError()
            ni_timestamp(self.closed_at_utc, canonical=True)
            integer(self.end_offset, self.generation_start_offset)
        integer(self.generation_start_offset)
        integer(self.committed_byte_offset, self.generation_start_offset)
        metadata = (self.blocked_reason_code, self.blocked_at_utc,
                    self.blocked_record_start_byte_offset)
        if self.processing_state == "runnable":
            if any(value is not None for value in metadata):
                raise NetworkMetadataValidationError()
        elif self.processing_state == "blocked":
            if (any(value is None for value in metadata)
                    or self.blocked_reason_code not in CONFLICT_CATEGORIES
                    or any(value is not None for value in
                           (self.closed_at_utc, self.end_offset, self.close_reason))):
                raise NetworkMetadataValidationError()
            integer(self.blocked_record_start_byte_offset, self.generation_start_offset)
            ni_timestamp(self.blocked_at_utc, canonical=True)
            if self.blocked_record_start_byte_offset != self.committed_byte_offset:
                raise NetworkMetadataValidationError()
        else:
            raise NetworkMetadataValidationError()


@dataclass(frozen=True, slots=True)
class SourceCheckpointV1:
    logical_source_id: str
    source_generation_id: str
    committed_byte_offset: int
    continuity_anchor_start_offset: int
    continuity_anchor_length: int
    continuity_anchor_sha256: str | None
    updated_at_utc: str


@dataclass(frozen=True, slots=True)
class IngestRunV1:
    ingest_run_id: str
    started_at_utc: str
    repository_head: str
    repository_tree: str
    normalizer_version: str
    configuration_digest: str


@dataclass(frozen=True, slots=True)
class NetworkMetadataEnvelopeV1:
    observation_id: str
    schema_version: int
    source_type: str
    source_contract_version: str
    source_event_family: str
    source_event_identity: str
    source_generation_id: str
    record_start_byte_offset: int
    capture_source_id: str
    capture_scope_binding_schema_version: int
    capture_scope_binding_digest: str
    network_scope_id: str
    network_scope_state: str
    site_id: str
    event_at: str
    ingested_at: str
    flow_id_decimal: str | None
    transaction_id_decimal: str | None
    source_health_ref: str
    ingest_run_id: str
    normalizer_version: str
    sensitive_endpoint_presence_state: str


@dataclass(frozen=True, slots=True, repr=False)
class NetworkMetadataSensitiveEndpointV1:
    observation_id: str
    src_ip: str | None
    dst_ip: str | None
    src_port: int | None
    dst_port: int | None
    transport_protocol: str | None


@dataclass(frozen=True, slots=True, repr=False)
class DnsQueryV1:
    ordinal: int
    query_name: str
    query_type: str


@dataclass(frozen=True, slots=True, repr=False)
class DnsAnswerV1:
    ordinal: int
    answer_type: str
    answer_value: str


@dataclass(frozen=True, slots=True, repr=False)
class DnsObservationV1:
    dns_version: int
    dns_event_kind: str
    dns_tx_id: int
    dns_wire_id: int | None
    rcode: str | None
    query_names_presence_state: str
    answer_values_presence_state: str
    query_count_observed: int
    answer_count_observed: int
    queries_truncated: bool
    answers_truncated: bool
    queries: tuple[DnsQueryV1, ...]
    answers: tuple[DnsAnswerV1, ...]


@dataclass(frozen=True, slots=True, repr=False)
class TlsObservationV1:
    tls_version: str | None
    sni: str | None
    sni_presence_state: str
    client_alpns: tuple[str, ...]
    server_alpns: tuple[str, ...]
    client_alpns_truncated: bool
    server_alpns_truncated: bool


@dataclass(frozen=True, slots=True, repr=False)
class QuicObservationV1:
    quic_version: str | None
    sni: str | None
    sni_presence_state: str


@dataclass(frozen=True, slots=True)
class NetworkMetadataSourceHealthV1:
    health_id: str
    evaluated_at: str
    capture_source_id: str
    source_generation_id: str | None
    capture_health: str
    metadata_output_health: str
    metadata_ingest_health: str
    last_output_event_at: str | None
    last_ingested_event_at: str | None
    committed_byte_offset: int | None
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True, repr=False)
class NormalizedEvent:
    observation_id: str
    source_event_identity: str
    family: str
    event_at: str
    flow_id: int | None
    transaction_id: int | None
    binding: CaptureScopeBindingV1
    endpoint: NetworkMetadataSensitiveEndpointV1
    payload: DnsObservationV1 | TlsObservationV1 | QuicObservationV1
    source_record_sha256: str
    semantic_payload_sha256: str


@dataclass(frozen=True, slots=True, repr=False)
class RecordOutcome:
    start: int
    end: int
    byte_length: int
    category: str
    normalized: NormalizedEvent | None = None
    output_event_at: str | None = None
    source_record_sha256: str | None = None
