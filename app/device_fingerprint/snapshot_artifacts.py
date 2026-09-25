"""Closed R14 T-01 snapshot content and successful-build audit artifacts."""

from __future__ import annotations

import uuid
from typing import Any

from .artifact_content import ArtifactContent, ArtifactRef, canonical_set, make_artifact_content
from .binding_contracts import resolve_authoritative_binding
from .foundation_admission_artifacts import make_origin_runtime_admission
from .models import DeviceFingerprintValidationError
from .runtime_profile_artifacts import make_foundation_runtime_profile
from .validation import (
    parse_utc, validate_mac, validate_quality, validate_site_id,
    validate_source_kind, validate_health_status, validate_uuid,
)

_CONTENT_FIELDS = frozenset({
    "snapshot_contract_version", "site_id", "observed_mac", "window_start_utc",
    "window_end_utc", "database_generation_id", "max_committed_ingest_sequence",
    "evidence_source_binding_timeline", "binding_clock_policy",
    "evidence_schema_registry_contract", "origin_runtime_admission",
    "classification_foundation_valid_from_utc", "binding_epoch_descriptors",
    "evidence_descriptors", "source_health_descriptors",
})
_ORIGIN_FIELDS = frozenset({
    "artifact_id", "content_sha256", "tcp_state", "tcp_reason_code",
    "ttl_capture_placement_proof",
})
_BINDING_FIELDS = frozenset({
    "binding_epoch_id", "site_id", "origin_group", "source_kind",
    "capture_source_id", "producer_id", "source_health_emitter_contract",
    "effective_from_utc", "effective_to_utc",
})
_EVIDENCE_FIELDS = frozenset({
    "evidence_id", "ingest_sequence", "producer_id", "source_kind", "source_subtype",
    "capture_source_id", "extractor_name", "extractor_version", "feature_schema_version",
    "rule_version", "site_id", "observed_at", "ingested_at", "observed_mac",
    "privacy_class", "quality_state", "payload_sha256", "binding_epoch_id",
})
_HEALTH_FIELDS = frozenset({
    "source_health_id", "ingest_sequence", "producer_id", "source_kind",
    "capture_source_id", "status", "reason_code", "observed_at", "ingested_at",
    "content_sha256", "binding_epoch_id",
})
_RECORD_FIELDS = frozenset({
    "evidence_snapshot_content", "foundation_runtime_profile", "snapshot_captured_at_utc",
    "snapshot_content_policy", "snapshot_execution_policy", "verified_evidence_row_count",
    "verified_payload_bytes", "materialized_evidence_row_count", "materialized_payload_bytes",
    "total_semantic_input_bytes", "scope_anomaly_count", "scope_anomaly_reason_counts",
    "build_outcome",
})
_SOURCE_ORIGIN = {
    "dhcp": "dhcp", "portal_headers": "portal", "tcp_syn": "tcp",
    "tls_client": "tls", "quic_client": "quic",
}
_ORIGINS = frozenset(_SOURCE_ORIGIN.values())
_MAX_I64 = 2**63 - 1


def _fail(message: str) -> None:
    raise DeviceFingerprintValidationError(message)


def _shape(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        _fail(f"Invalid {label} shape")
    return value


def _text(value: Any, label: str, *, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        _fail(f"Invalid {label}")
    return value


def _number(value: Any, label: str, *, minimum: int = 0, maximum: int = _MAX_I64) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        _fail(f"Invalid {label}")
    return value


def _uuid4(value: Any) -> str:
    validate_uuid(value)
    if uuid.UUID(value).version != 4:
        _fail("Invalid UUIDv4")
    return value


def _digest(value: Any) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        _fail("Invalid SHA256")
    return value


def _ref(value: Any, target: str, *, nullable: bool = False) -> dict[str, str] | None:
    if nullable and value is None:
        return None
    reference = ArtifactRef.from_dict(value)
    if not reference.artifact_id.startswith(f"{target}:v1:sha256:"):
        _fail(f"Invalid {target} reference")
    return reference.as_dict()


def _exact_ref(value: Any, content: ArtifactContent, target: str) -> None:
    reference = ArtifactRef.from_dict(_ref(value, target))
    reference.resolve(content, target)


def _binding_descriptor(value: Any) -> dict[str, Any]:
    row = _shape(value, _BINDING_FIELDS, "binding descriptor")
    _text(row["binding_epoch_id"], "binding epoch ID")
    validate_site_id(row["site_id"])
    if row["origin_group"] not in _ORIGINS:
        _fail("Invalid binding origin")
    validate_source_kind(row["source_kind"])
    if _SOURCE_ORIGIN.get(row["source_kind"]) != row["origin_group"]:
        _fail("Binding source/origin mismatch")
    _text(row["capture_source_id"], "capture source")
    _text(row["producer_id"], "producer")
    _ref(row["source_health_emitter_contract"], "SourceHealthEmitterContract")
    start = parse_utc(row["effective_from_utc"])
    end = row["effective_to_utc"]
    if end is not None and parse_utc(end) <= start:
        _fail("Invalid binding interval")
    return row


def _evidence_descriptor(value: Any, bindings: dict[str, dict[str, Any]],
                         site_id: str, observed_mac: str) -> dict[str, Any]:
    row = _shape(value, _EVIDENCE_FIELDS, "evidence descriptor")
    _uuid4(row["evidence_id"])
    _number(row["ingest_sequence"], "evidence ingest sequence", minimum=1)
    for field in ("producer_id", "capture_source_id", "extractor_name", "extractor_version"):
        _text(row[field], field)
    validate_source_kind(row["source_kind"])
    _text(row["source_subtype"], "source subtype", nullable=True)
    _number(row["feature_schema_version"], "schema version", minimum=1, maximum=2**31 - 1)
    _text(row["rule_version"], "rule version", nullable=True)
    validate_site_id(row["site_id"])
    parse_utc(row["observed_at"])
    parse_utc(row["ingested_at"])
    if validate_mac(row["observed_mac"]) != row["observed_mac"]:
        _fail("Noncanonical evidence MAC")
    if row["privacy_class"] != "P1" or validate_quality(row["quality_state"]) != row["quality_state"]:
        _fail("Invalid evidence privacy/quality")
    _digest(row["payload_sha256"])
    _text(row["binding_epoch_id"], "evidence binding epoch ID")
    epoch = bindings.get(row["binding_epoch_id"])
    if (epoch is None or row["site_id"] != site_id or row["observed_mac"] != observed_mac
            or any(row[field] != epoch[field] for field in (
                "site_id", "source_kind", "capture_source_id", "producer_id"))):
        _fail("Evidence descriptor binding mismatch")
    return row


def _health_descriptor(value: Any, bindings: dict[str, dict[str, Any]],
                       site_id: str) -> dict[str, Any]:
    row = _shape(value, _HEALTH_FIELDS, "health descriptor")
    _uuid4(row["source_health_id"])
    _number(row["ingest_sequence"], "health ingest sequence", minimum=1)
    for field in ("producer_id", "capture_source_id"):
        _text(row[field], field)
    validate_source_kind(row["source_kind"])
    validate_health_status(row["status"])
    _text(row["reason_code"], "health reason", nullable=True)
    parse_utc(row["observed_at"])
    parse_utc(row["ingested_at"])
    _digest(row["content_sha256"])
    _text(row["binding_epoch_id"], "health binding epoch ID")
    epoch = bindings.get(row["binding_epoch_id"])
    if (epoch is None or epoch["site_id"] != site_id
            or any(row[field] != epoch[field] for field in (
                "source_kind", "capture_source_id", "producer_id"))):
        _fail("Health descriptor binding mismatch")
    return row


def make_evidence_snapshot_content(
    payload: dict[str, Any], *, foundation_runtime_profile: ArtifactContent,
    binding_timeline: ArtifactContent, binding_clock_policy: ArtifactContent,
    schema_registry_contract: ArtifactContent, origin_runtime_admission: ArtifactContent,
) -> ArtifactContent:
    """Validate exact pinned semantic dependencies and canonical snapshot membership."""
    value = _shape(payload, _CONTENT_FIELDS, "EvidenceSnapshotContent")
    profile = make_foundation_runtime_profile(foundation_runtime_profile.semantic_payload)
    if profile != foundation_runtime_profile:
        _fail("Noncanonical FoundationRuntimeProfile")
    profile_payload = profile.semantic_payload
    _number(value["snapshot_contract_version"], "snapshot version", minimum=1, maximum=2**31 - 1)
    if value["snapshot_contract_version"] != profile_payload["snapshot_contract_version"]:
        _fail("Snapshot/profile version mismatch")
    validate_site_id(value["site_id"])
    if validate_mac(value["observed_mac"]) != value["observed_mac"]:
        _fail("Noncanonical snapshot MAC")
    start, end = parse_utc(value["window_start_utc"]), parse_utc(value["window_end_utc"])
    if start >= end or start < parse_utc(value["classification_foundation_valid_from_utc"]):
        _fail("Invalid snapshot window")
    _uuid4(value["database_generation_id"])
    _number(value["max_committed_ingest_sequence"], "snapshot watermark")
    if value["classification_foundation_valid_from_utc"] != profile_payload[
            "classification_foundation_valid_from_utc"]:
        _fail("Snapshot valid-from/profile mismatch")
    for field, content, kind in (
        ("evidence_source_binding_timeline", binding_timeline, "EvidenceSourceBindingTimeline"),
        ("binding_clock_policy", binding_clock_policy, "BindingClockPolicy"),
        ("evidence_schema_registry_contract", schema_registry_contract, "EvidenceSchemaRegistryContract"),
    ):
        _exact_ref(value[field], content, kind)
        if value[field] != profile_payload[field]:
            _fail("Snapshot/profile dependency mismatch")
    origin = _shape(value["origin_runtime_admission"], _ORIGIN_FIELDS, "origin descriptor")
    if make_origin_runtime_admission(origin_runtime_admission.semantic_payload) != origin_runtime_admission:
        _fail("Invalid OriginRuntimeAdmission")
    _exact_ref({key: origin[key] for key in ("artifact_id", "content_sha256")},
               origin_runtime_admission, "OriginRuntimeAdmission")
    origin_payload = origin_runtime_admission.semantic_payload
    if (origin["tcp_state"] != origin_payload["tcp_state"]
            or origin["tcp_reason_code"] != origin_payload["tcp_reason_code"]
            or origin["ttl_capture_placement_proof"] != origin_payload["ttl_capture_placement_proof"]
            or {key: origin[key] for key in ("artifact_id", "content_sha256")} !=
            profile_payload["origin_runtime_admission"]
            or origin["ttl_capture_placement_proof"] != profile_payload["ttl_capture_placement_proof"]):
        _fail("Origin/profile dependency mismatch")
    _ref(origin["ttl_capture_placement_proof"], "TTLCapturePlacementProof", nullable=True)
    raw_bindings = value["binding_epoch_descriptors"]
    if not isinstance(raw_bindings, list):
        _fail("Invalid binding descriptors")
    bindings = [_binding_descriptor(item) for item in raw_bindings]
    if len({item["binding_epoch_id"] for item in bindings}) != len(bindings):
        _fail("Duplicate binding epoch ID")
    timeline_by_id = {item["binding_epoch_id"]: item for item in
                      binding_timeline.semantic_payload["binding_epochs"]}
    if any(timeline_by_id.get(item["binding_epoch_id"]) != item for item in bindings):
        _fail("Binding descriptor/timeline mismatch")
    required = {
        epoch["binding_epoch_id"] for epoch in timeline_by_id.values()
        if epoch["site_id"] == value["site_id"]
        and parse_utc(epoch["effective_from_utc"]) < end
        and (epoch["effective_to_utc"] is None
             or start < parse_utc(epoch["effective_to_utc"]))
    }
    if {item["binding_epoch_id"] for item in bindings} != required or not required:
        _fail("Incomplete snapshot binding descriptors")
    bindings = canonical_set(bindings, lambda item: (
        item["effective_from_utc"], item["origin_group"], item["source_kind"],
        item["capture_source_id"], item["producer_id"], item["binding_epoch_id"],
    ))
    by_id = {item["binding_epoch_id"]: item for item in bindings}
    raw_evidence, raw_health = value["evidence_descriptors"], value["source_health_descriptors"]
    if not isinstance(raw_evidence, list) or not isinstance(raw_health, list):
        _fail("Invalid snapshot descriptor sequences")
    evidence = [_evidence_descriptor(item, by_id, value["site_id"], value["observed_mac"])
                for item in raw_evidence]
    health = [_health_descriptor(item, by_id, value["site_id"]) for item in raw_health]
    if (len({item["evidence_id"] for item in evidence}) != len(evidence)
            or len({item["source_health_id"] for item in health}) != len(health)):
        _fail("Duplicate snapshot descriptor ID")
    for row in evidence:
        if row["ingest_sequence"] > value["max_committed_ingest_sequence"] or not (
                start <= parse_utc(row["observed_at"]) < end):
            _fail("Evidence descriptor outside window/watermark")
    for row in health:
        if (row["ingest_sequence"] > value["max_committed_ingest_sequence"]
                or parse_utc(row["observed_at"]) >= end):
            _fail("Health descriptor outside watermark/end")
    for row in (*evidence, *health):
        origin_group = by_id[row["binding_epoch_id"]]["origin_group"]
        authority = resolve_authoritative_binding(
            binding_timeline, binding_clock_policy, value["site_id"],
            origin_group, row["source_kind"], row["observed_at"])
        epoch = authority["binding_epoch"]
        if (authority["status"] != "AUTHORIZED" or epoch is None
                or epoch["binding_epoch_id"] != row["binding_epoch_id"]
                or row["producer_id"] != epoch["producer_id"]
                or row["capture_source_id"] != epoch["capture_source_id"]):
            _fail("Snapshot descriptor lacks exact binding authority")
    evidence.sort(key=lambda row: (
        by_id[row["binding_epoch_id"]]["origin_group"], row["source_kind"],
        row["capture_source_id"], row["producer_id"], row["observed_at"],
        row["ingest_sequence"], row["evidence_id"],
    ))
    health.sort(key=lambda row: (
        by_id[row["binding_epoch_id"]]["origin_group"], row["source_kind"],
        row["capture_source_id"], row["producer_id"], row["observed_at"],
        row["ingest_sequence"], row["source_health_id"],
    ))
    return make_artifact_content("EvidenceSnapshotContent", {
        **value, "binding_epoch_descriptors": bindings,
        "evidence_descriptors": evidence, "source_health_descriptors": health,
    })


def make_snapshot_record(
    payload: dict[str, Any], *, evidence_snapshot_content: ArtifactContent,
    foundation_runtime_profile: ArtifactContent, snapshot_content_policy: ArtifactContent,
    snapshot_execution_policy: ArtifactContent,
) -> ArtifactContent:
    """Validate exact profile/policy duplication before durable success identity."""
    value = _shape(payload, _RECORD_FIELDS, "SnapshotRecord")
    profile = make_foundation_runtime_profile(foundation_runtime_profile.semantic_payload)
    if profile != foundation_runtime_profile:
        _fail("Noncanonical FoundationRuntimeProfile")
    _exact_ref(value["evidence_snapshot_content"], evidence_snapshot_content, "EvidenceSnapshotContent")
    _exact_ref(value["foundation_runtime_profile"], profile, "FoundationRuntimeProfile")
    for field, content, kind in (
        ("snapshot_content_policy", snapshot_content_policy, "SnapshotContentPolicy"),
        ("snapshot_execution_policy", snapshot_execution_policy, "SnapshotExecutionPolicy"),
    ):
        _exact_ref(value[field], content, kind)
        if value[field] != profile.semantic_payload[field]:
            _fail("SnapshotRecord/profile policy mismatch")
    captured_at = parse_utc(value["snapshot_captured_at_utc"])
    snapshot_payload = evidence_snapshot_content.semantic_payload
    if captured_at < parse_utc(snapshot_payload["window_end_utc"]):
        _fail("SnapshotRecord capture precedes completed window")
    for field in (
        "evidence_source_binding_timeline", "binding_clock_policy",
        "evidence_schema_registry_contract", "classification_foundation_valid_from_utc",
    ):
        if snapshot_payload[field] != profile.semantic_payload[field]:
            _fail("SnapshotRecord/profile semantic dependency mismatch")
    origin_descriptor = snapshot_payload["origin_runtime_admission"]
    if ({key: origin_descriptor[key] for key in ("artifact_id", "content_sha256")}
            != profile.semantic_payload["origin_runtime_admission"]
            or origin_descriptor["ttl_capture_placement_proof"] !=
            profile.semantic_payload["ttl_capture_placement_proof"]):
        _fail("SnapshotRecord/profile origin mismatch")
    if value["build_outcome"] != "success":
        _fail("Invalid SnapshotRecord outcome")
    for field in (
        "verified_evidence_row_count", "verified_payload_bytes", "materialized_evidence_row_count",
        "materialized_payload_bytes", "total_semantic_input_bytes", "scope_anomaly_count",
    ):
        _number(value[field], field)
    if (value["verified_evidence_row_count"] != len(
            evidence_snapshot_content.semantic_payload["evidence_descriptors"])
            or value["materialized_evidence_row_count"] > value["verified_evidence_row_count"]
            or value["materialized_payload_bytes"] > value["verified_payload_bytes"]):
        _fail("Inconsistent SnapshotRecord evidence counts")
    reasons = value["scope_anomaly_reason_counts"]
    if not isinstance(reasons, list):
        _fail("Invalid scope anomaly reasons")
    for row in reasons:
        _shape(row, frozenset({"reason_code", "count"}), "scope anomaly reason")
        _text(row["reason_code"], "scope anomaly reason code")
        _number(row["count"], "scope anomaly count", minimum=1)
    if len({row["reason_code"] for row in reasons}) != len(reasons):
        _fail("Duplicate scope anomaly reason")
    if sum(row["count"] for row in reasons) != value["scope_anomaly_count"]:
        _fail("Scope anomaly count mismatch")
    return make_artifact_content("SnapshotRecord", {
        **value, "scope_anomaly_reason_counts": canonical_set(reasons, lambda row: row["reason_code"]),
    })
