"""Frozen Task-01 models and sanitized error taxonomy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class DeviceFingerprintError(RuntimeError):
    """Base class for the isolated fingerprint service."""


class DeviceFingerprintConfigError(DeviceFingerprintError):
    pass


class DeviceFingerprintValidationError(DeviceFingerprintError):
    pass


class DeviceFingerprintUnsupportedSchema(DeviceFingerprintValidationError):
    pass


class DeviceFingerprintConflict(DeviceFingerprintError):
    pass


class DeviceFingerprintStorageUnavailable(DeviceFingerprintError):
    pass


class DeviceFingerprintStorageCorrupt(DeviceFingerprintError):
    pass


class DeviceFingerprintStorageLimit(DeviceFingerprintError):
    pass


class DeviceFingerprintWriterUnavailable(DeviceFingerprintError):
    pass


@dataclass(frozen=True, slots=True)
class DeviceFingerprintProducer:
    producer_id: str
    bearer_token: str
    capture_source_id: str
    site_id: str
    allowed_guest_cidrs: tuple[Any, ...]
    allowed_source_kinds: tuple[str, ...]

    def __repr__(self) -> str:
        return (
            "DeviceFingerprintProducer("
            f"producer_id={self.producer_id!r}, bearer_token='<redacted>', "
            f"capture_source_id={self.capture_source_id!r}, "
            f"site_id={self.site_id!r}, "
            f"allowed_guest_cidrs={self.allowed_guest_cidrs!r}, "
            f"allowed_source_kinds={self.allowed_source_kinds!r})"
        )


@dataclass(frozen=True, slots=True)
class DeviceFingerprintConfig:
    enabled: bool
    db_path: str
    writer_lock_path: str
    bind_address: str
    port: int
    tls_cert_path: str
    tls_key_path: str
    allowed_networks: tuple[Any, ...]
    producers: tuple[DeviceFingerprintProducer, ...]
    retention_days: int
    max_future_skew_seconds: int
    max_delayed_event_age_seconds: int
    max_db_bytes: int
    max_http_request_bytes: int
    max_events_per_batch: int
    max_payload_bytes: int
    max_concurrent_ingest_requests: int

    def __repr__(self) -> str:
        return (
            "DeviceFingerprintConfig("
            f"enabled={self.enabled!r}, db_path={self.db_path!r}, "
            f"writer_lock_path={self.writer_lock_path!r}, "
            f"bind_address={self.bind_address!r}, port={self.port!r}, "
            f"tls_cert_path={self.tls_cert_path!r}, tls_key_path={self.tls_key_path!r}, "
            f"allowed_networks={self.allowed_networks!r}, producers={self.producers!r}, "
            f"retention_days={self.retention_days!r}, "
            f"max_future_skew_seconds={self.max_future_skew_seconds!r}, "
            f"max_delayed_event_age_seconds={self.max_delayed_event_age_seconds!r}, "
            f"max_db_bytes={self.max_db_bytes!r}, "
            f"max_http_request_bytes={self.max_http_request_bytes!r}, "
            f"max_events_per_batch={self.max_events_per_batch!r}, "
            f"max_payload_bytes={self.max_payload_bytes!r}, "
            f"max_concurrent_ingest_requests={self.max_concurrent_ingest_requests!r})"
        )


@dataclass(frozen=True, slots=True)
class BatchResult:
    received: int
    inserted: int
    duplicate_noop: int


@dataclass(frozen=True, slots=True)
class ValidatedEvidence:
    producer_id: str
    source_event_id: str
    source_kind: str
    source_subtype: str | None
    extractor_name: str
    extractor_version: str
    feature_schema_version: int
    rule_version: str | None
    site_id: str
    capture_source_id: str
    observed_at: str
    observed_mac: str
    observed_ip: str | None
    privacy_class: str
    quality_state: str
    payload_json: str
    payload_sha256: str

    def immutable_fields(self) -> Mapping[str, Any]:
        return {name: getattr(self, name) for name in self.__slots__}


@dataclass(frozen=True, slots=True)
class ValidatedSourceHealth:
    producer_id: str
    source_health_event_id: str
    site_id: str
    capture_source_id: str
    source_kind: str
    status: str
    reason_code: str | None
    observed_at: str
    content_sha256: str

    def immutable_fields(self) -> Mapping[str, Any]:
        return {name: getattr(self, name) for name in self.__slots__}
