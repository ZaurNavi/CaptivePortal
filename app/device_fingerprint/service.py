"""Validation, ingestion, retention, and bounded runtime lifecycle."""

from __future__ import annotations

import ipaddress
import json
import threading
import time
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from .config import (
    RETENTION_SCAN_INTERVAL_SECONDS, SHUTDOWN_TIMEOUT_SECONDS,
    SOURCE_HEALTH_RETENTION_DAYS,
)
from .models import (
    BatchResult,
    DeviceFingerprintConfig,
    DeviceFingerprintProducer,
    DeviceFingerprintStorageCorrupt,
    DeviceFingerprintStorageLimit,
    DeviceFingerprintStorageUnavailable,
    DeviceFingerprintValidationError,
    ValidatedEvidence,
    ValidatedSourceHealth,
)
from .repository import DeviceFingerprintRepository
from .schema import SCHEMA_VERSION
from .schema_registry import EvidenceSchemaRegistry
from .telemetry import DeviceFingerprintTelemetry
from .validation import (
    canonical_json, canonical_sha256, format_utc, validate_feature_schema_version,
    validate_health_status, validate_ip, validate_mac, validate_machine_id,
    validate_nullable_machine_id, validate_observed_at, validate_quality,
    validate_reason_code, validate_site_id, validate_source_kind, validate_uuid,
    validate_version,
)

UTC = timezone.utc
_EVIDENCE_KEYS = frozenset({
    "source_event_id", "source_kind", "source_subtype", "extractor_name",
    "extractor_version", "feature_schema_version", "rule_version", "site_id",
    "capture_source_id", "observed_at", "observed_mac", "observed_ip",
    "quality_state", "payload",
})
_HEALTH_KEYS = frozenset({
    "source_health_event_id", "site_id", "capture_source_id", "source_kind",
    "status", "reason_code", "observed_at",
})


class DeviceFingerprintService:
    def __init__(self, config: DeviceFingerprintConfig, repository: DeviceFingerprintRepository,
                 registry: EvidenceSchemaRegistry, *, now=None) -> None:
        self.config = config
        self.repository = repository
        self.registry = registry
        self._now = now or (lambda: datetime.now(UTC))

    def evidence_batch(self, producer: DeviceFingerprintProducer, payload: Any) -> BatchResult:
        root = self._root(payload, producer)
        now = self._now()
        events = root["events"]
        validated: list[ValidatedEvidence] = []
        identities: set[str] = set()
        for raw in events:
            if not isinstance(raw, dict) or set(raw) != _EVIDENCE_KEYS:
                raise DeviceFingerprintValidationError("Invalid evidence event")
            identity = validate_uuid(raw["source_event_id"])
            if identity in identities:
                raise DeviceFingerprintValidationError("Duplicate source event")
            identities.add(identity)
            kind = validate_source_kind(raw["source_kind"])
            site_id = validate_site_id(raw["site_id"])
            capture_source_id = validate_machine_id(raw["capture_source_id"])
            self._authorize_event(producer, site_id, capture_source_id, kind)
            observed_ip = validate_ip(raw["observed_ip"])
            if observed_ip is not None and not any(ipaddress.ip_address(observed_ip) in network for network in producer.allowed_guest_cidrs):
                raise DeviceFingerprintValidationError("Observed IP is outside guest scope")
            schema_version = validate_feature_schema_version(raw["feature_schema_version"])
            canonical_json(raw["payload"])
            approved = self.registry.validate(kind, schema_version, raw["payload"])
            payload_json = canonical_json(approved)
            if len(payload_json.encode("utf-8")) > self.config.max_payload_bytes:
                raise OverflowError("request_too_large")
            validated.append(ValidatedEvidence(
                producer_id=producer.producer_id,
                source_event_id=identity,
                source_kind=kind,
                source_subtype=validate_nullable_machine_id(raw["source_subtype"]),
                extractor_name=validate_machine_id(raw["extractor_name"]),
                extractor_version=validate_version(raw["extractor_version"]),
                feature_schema_version=schema_version,
                rule_version=None if raw["rule_version"] is None else validate_version(raw["rule_version"]),
                site_id=site_id,
                capture_source_id=capture_source_id,
                observed_at=validate_observed_at(raw["observed_at"], now=now, max_future_skew_seconds=self.config.max_future_skew_seconds, max_delayed_event_age_seconds=self.config.max_delayed_event_age_seconds),
                observed_mac=validate_mac(raw["observed_mac"]),
                observed_ip=observed_ip,
                privacy_class="P1",
                quality_state=validate_quality(raw["quality_state"]),
                payload_json=payload_json,
                payload_sha256=canonical_sha256(payload_json),
            ))
        return self.repository.ingest_evidence(validated, ingested_at=format_utc(now))

    def source_health_batch(self, producer: DeviceFingerprintProducer, payload: Any) -> BatchResult:
        root = self._root(payload, producer)
        now = self._now()
        validated: list[ValidatedSourceHealth] = []
        identities: set[str] = set()
        for raw in root["events"]:
            if not isinstance(raw, dict) or set(raw) != _HEALTH_KEYS:
                raise DeviceFingerprintValidationError("Invalid source health event")
            identity = validate_uuid(raw["source_health_event_id"])
            if identity in identities:
                raise DeviceFingerprintValidationError("Duplicate source health event")
            identities.add(identity)
            kind = validate_source_kind(raw["source_kind"])
            site_id = validate_site_id(raw["site_id"])
            capture_source_id = validate_machine_id(raw["capture_source_id"])
            self._authorize_event(producer, site_id, capture_source_id, kind)
            content = {
                "producer_id": producer.producer_id,
                "source_health_event_id": identity,
                "site_id": site_id,
                "capture_source_id": capture_source_id,
                "source_kind": kind,
                "status": validate_health_status(raw["status"]),
                "reason_code": validate_reason_code(raw["reason_code"]),
                "observed_at": validate_observed_at(raw["observed_at"], now=now, max_future_skew_seconds=self.config.max_future_skew_seconds, max_delayed_event_age_seconds=self.config.max_delayed_event_age_seconds),
            }
            content_json = canonical_json(content)
            validated.append(ValidatedSourceHealth(**content, content_sha256=canonical_sha256(content_json)))
        return self.repository.ingest_source_health(validated, ingested_at=format_utc(now))

    def _root(self, payload: Any, producer: DeviceFingerprintProducer) -> Mapping[str, Any]:
        if not isinstance(payload, dict) or set(payload) != {"producer_id", "events"}:
            raise DeviceFingerprintValidationError("Invalid batch")
        producer_id = validate_machine_id(payload["producer_id"])
        if producer_id != producer.producer_id:
            raise PermissionError("producer_forbidden")
        events = payload["events"]
        if not isinstance(events, list) or not events:
            raise DeviceFingerprintValidationError("Invalid batch")
        if len(events) > self.config.max_events_per_batch:
            raise OverflowError("request_too_large")
        return payload

    @staticmethod
    def _authorize_event(producer: DeviceFingerprintProducer, site_id: str,
                         capture_source_id: str, kind: str) -> None:
        if site_id != producer.site_id:
            raise PermissionError("site_forbidden")
        if capture_source_id != producer.capture_source_id:
            raise PermissionError("capture_source_forbidden")
        if kind not in producer.allowed_source_kinds:
            raise PermissionError("source_kind_forbidden")


class DeviceFingerprintRuntime:
    def __init__(self, config: DeviceFingerprintConfig, repository: DeviceFingerprintRepository,
                 registry: EvidenceSchemaRegistry | None, *, artifact_identity: Any,
                 telemetry: DeviceFingerprintTelemetry, monotonic=time.monotonic,
                 now=None) -> None:
        self.config = config
        self.repository = repository
        self.registry = registry
        self.artifact_identity = artifact_identity
        self.telemetry = telemetry
        self.service = (
            DeviceFingerprintService(config, repository, registry, now=now)
            if registry is not None else None
        )
        self._now = now
        self.condition = threading.Condition()
        self.state = "initializing"
        self.reason: str | None = None
        self.accepting_writes = False
        self.active_ingest_count = 0
        self.stop_event = threading.Event()
        self.maintenance_thread: threading.Thread | None = None
        self.last_successful_retention_at: str | None = None
        self._monotonic = monotonic
        self._finalized = False
        self._hard_containment = False

    def initialize(self) -> None:
        self.repository.initialize()

    def configure_registry(self, registry: EvidenceSchemaRegistry) -> None:
        if not registry.frozen or self.service is not None:
            raise RuntimeError("Fingerprint schema registry composition is invalid")
        self.registry = registry
        self.service = DeviceFingerprintService(
            self.config, self.repository, registry, now=self._now
        )

    def mark_ready(self) -> None:
        with self.condition:
            self.state, self.reason, self.accepting_writes = "ready", None, True
            self.condition.notify_all()

    def begin_ingest(self) -> bool:
        with self.condition:
            if not self.accepting_writes or self.state not in {"ready", "degraded"}:
                return False
            self.active_ingest_count += 1
            return True

    def finish_ingest(self) -> None:
        with self.condition:
            self.active_ingest_count -= 1
            self.condition.notify_all()

    def transition_stopping(self) -> None:
        with self.condition:
            self.state, self.reason, self.accepting_writes = "stopping", "stopping", False
            self.condition.notify_all()
        self.stop_event.set()

    def signal_stop(self, _signum=None, _frame=None) -> None:
        self.transition_stopping()
        raise SystemExit(0)

    def start_maintenance(self) -> None:
        if self.maintenance_thread is not None:
            raise RuntimeError("Fingerprint maintenance already started")
        self.maintenance_thread = threading.Thread(target=self._maintenance_loop, name="device-fingerprint-retention", daemon=False)
        self.maintenance_thread.start()

    def _maintenance_loop(self) -> None:
        while not self.stop_event.wait(RETENTION_SCAN_INTERVAL_SECONDS):
            self.run_maintenance_once()

    def run_maintenance_once(self) -> None:
        with self.condition:
            if self.reason in {"storage_unavailable", "storage_corrupt"}:
                return
        try:
            deleted = self.repository.cleanup(now=datetime.now(UTC), evidence_retention_days=self.config.retention_days)
            self.repository.validate_runtime_health()
            capacity = self.repository.capacity()
            with self.condition:
                if self.state != "stopping":
                    if self.reason == "storage_limit" and not (capacity["page_count"] < capacity["max_page_count"] or capacity["freelist_count"] > 0):
                        return
                    self.state, self.reason, self.accepting_writes = "ready", None, True
                    self.last_successful_retention_at = format_utc(datetime.now(UTC))
            self.telemetry.emit("device_fingerprint_retention_completed", deleted_evidence=deleted["device_fingerprint_evidence"], deleted_source_health=deleted["device_fingerprint_source_health_events"])
        except DeviceFingerprintStorageCorrupt:
            self._unavailable("storage_corrupt", "device_fingerprint_storage_unavailable")
        except DeviceFingerprintStorageLimit:
            self._unavailable("storage_limit", "device_fingerprint_storage_limit")
        except DeviceFingerprintStorageUnavailable:
            try:
                self.repository.validate_runtime_health()
            except Exception:
                self._unavailable("storage_unavailable", "device_fingerprint_storage_unavailable")
            else:
                with self.condition:
                    if self.state != "stopping":
                        self.state, self.reason, self.accepting_writes = "degraded", "retention_failed", True
                self.telemetry.emit("device_fingerprint_retention_failed", error_category="retention_failed")
        except Exception:
            try:
                self.repository.validate_runtime_health()
            except DeviceFingerprintStorageCorrupt:
                self._unavailable("storage_corrupt", "device_fingerprint_storage_unavailable")
            except Exception:
                self._unavailable("storage_unavailable", "device_fingerprint_storage_unavailable")
            else:
                with self.condition:
                    if self.state != "stopping":
                        self.state, self.reason, self.accepting_writes = "degraded", "retention_failed", True
                self.telemetry.emit("device_fingerprint_retention_failed", error_category="retention_failed")

    def note_storage_error(self, exc: Exception) -> None:
        if isinstance(exc, DeviceFingerprintStorageLimit):
            self._unavailable("storage_limit", "device_fingerprint_storage_limit")
        elif isinstance(exc, DeviceFingerprintStorageCorrupt):
            self._unavailable("storage_corrupt", "device_fingerprint_storage_unavailable")

    def _unavailable(self, reason: str, event: str) -> None:
        with self.condition:
            if self.state != "stopping":
                self.state, self.reason, self.accepting_writes = "unavailable", reason, False
                self.condition.notify_all()
        self.telemetry.emit(event, error_category=reason)

    def health_payload(self) -> Mapping[str, Any]:
        with self.condition:
            state, reason = self.state, self.reason
        return {
            "status": state,
            "reason": reason,
            "artifact_identity": self.artifact_identity.safe_fields(),
            "schema_version": SCHEMA_VERSION,
            "evidence_retention_days": self.config.retention_days,
            "source_health_retention_days": SOURCE_HEALTH_RETENTION_DAYS,
            "last_successful_retention_at": self.last_successful_retention_at,
        }

    def finalize(self, *, release_lock=None) -> bool:
        with self.condition:
            if self._finalized:
                return True
            if self._hard_containment:
                return False
            deadline = self._monotonic() + SHUTDOWN_TIMEOUT_SECONDS
            self.state, self.reason, self.accepting_writes = "stopping", "stopping", False
            self.condition.notify_all()
        self.stop_event.set()
        with self.condition:
            while self.active_ingest_count:
                remaining = deadline - self._monotonic()
                if remaining <= 0:
                    break
                self.condition.wait(remaining)
        thread = self.maintenance_thread
        if thread is not None and thread.is_alive():
            remaining = max(0.0, deadline - self._monotonic())
            thread.join(remaining)
        with self.condition:
            safe = self.active_ingest_count == 0 and (thread is None or not thread.is_alive())
        if not safe:
            self._hard_containment = True
            self.telemetry.emit("device_fingerprint_product_health", runtime_state="stopping", error_category="shutdown_timeout", active_ingest_count=self.active_ingest_count)
            return False
        self.repository.close()
        if release_lock is not None:
            release_lock()
        self._finalized = True
        self.telemetry.emit("device_fingerprint_service_stopped", runtime_state="stopping")
        return True
