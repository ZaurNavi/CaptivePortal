"""Exact R14 semantic-byte accounting dependencies for F-A4 measurement."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from app.device_fingerprint.artifact_content import (
    ArtifactContent,
    ArtifactRef,
    canonical_artifact_json,
    canonical_set,
    make_artifact_content,
)
from app.device_fingerprint.binding_contracts import (
    make_binding_clock_policy,
    make_evidence_source_binding_timeline,
    resolve_authoritative_binding,
)
from app.device_fingerprint.foundation_schema_artifacts import (
    build_foundation_schema_artifacts,
)
from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.source_health_emitter_contracts import (
    build_source_health_emitter_contracts,
)

ACCEPTED_BINDING_TIMELINE_ID = (
    "EvidenceSourceBindingTimeline:v1:sha256:"
    "820c5d43aca36b2284fe43cf4bbc4ce380300901c7adf9a0808353d28004a357"
)
ACCEPTED_BINDING_CLOCK_POLICY_ID = (
    "BindingClockPolicy:v1:sha256:"
    "4d825299e26819129ab5c357f12e7c5a54fa06999df02cf1cc87ccb1ae45ca66"
)
ACCEPTED_SCHEMA_REGISTRY_ID = (
    "EvidenceSchemaRegistryContract:v1:sha256:"
    "090d763e99247ca3b10be34976069e4e7e708be0899e21a15c6e103a015f7814"
)
ACCEPTED_TTL_PROOF_ID = (
    "TTLCapturePlacementProof:v1:sha256:"
    "c47c4235ddb2fd55c9851484f2fc242fe49a31e6b08d8ac44388368266989e1f"
)
ACCEPTED_CLASSIFICATION_FOUNDATION_VALID_FROM_UTC = "2026-09-18T10:43:29.014Z"

_SOURCE_ORIGINS = {
    "dhcp": "dhcp",
    "portal_headers": "portal",
    "tcp_syn": "tcp",
    "tls_client": "tls",
    "quic_client": "quic",
}
_BYTE_CATEGORIES = frozenset({
    "authorized_evidence_descriptor_bytes",
    "verified_payload_bytes",
    "materialized_payload_bytes",
    "authorized_health_descriptor_bytes",
    "binding_descriptor_bytes",
    "semantic_dependency_reference_bytes",
})


def _fail(message: str) -> None:
    raise DeviceFingerprintValidationError(message)


def _ref(content: ArtifactContent) -> dict[str, str]:
    return ArtifactRef(content.artifact_id, content.content_sha256).as_dict()


@dataclass(frozen=True, slots=True)
class SemanticAccountingDependencies:
    """Exact accepted dependencies required for COMPLETE F-A4 accounting."""

    binding_timeline: ArtifactContent
    binding_clock_policy: ArtifactContent
    schema_registry_contract: ArtifactContent
    ttl_capture_placement_proof: ArtifactRef


def build_semantic_accounting_dependencies(
    binding_timeline_payload: dict[str, Any],
    binding_clock_policy_payload: dict[str, Any],
) -> SemanticAccountingDependencies:
    """Rematerialize and validate the accepted F-B1/F-A5/F-C3 inputs."""
    timeline = make_evidence_source_binding_timeline(
        binding_timeline_payload, build_source_health_emitter_contracts(),
    )
    clock = make_binding_clock_policy(binding_clock_policy_payload)
    registry = build_foundation_schema_artifacts()["EvidenceSchemaRegistryContract"]
    dependencies = SemanticAccountingDependencies(
        timeline,
        clock,
        registry,
        ArtifactRef(
            ACCEPTED_TTL_PROOF_ID,
            ACCEPTED_TTL_PROOF_ID.rsplit(":", 1)[1],
        ),
    )
    validate_semantic_accounting_dependencies(dependencies)
    return dependencies


def load_semantic_accounting_dependencies(
    binding_timeline_path: str,
    binding_clock_policy_path: str,
) -> SemanticAccountingDependencies:
    """Load semantic payload JSON files without accepting artifact-ID assertions."""
    try:
        timeline = json.loads(Path(binding_timeline_path).read_text(encoding="utf-8"))
        clock = json.loads(Path(binding_clock_policy_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DeviceFingerprintValidationError("Invalid F-A4 dependency input") from exc
    if not isinstance(timeline, dict) or not isinstance(clock, dict):
        _fail("Invalid F-A4 dependency payload")
    return build_semantic_accounting_dependencies(timeline, clock)


def validate_semantic_accounting_dependencies(
    dependencies: SemanticAccountingDependencies,
) -> None:
    if not isinstance(dependencies, SemanticAccountingDependencies):
        _fail("Missing F-A4 semantic dependencies")
    expected = (
        (dependencies.binding_timeline, "EvidenceSourceBindingTimeline",
         ACCEPTED_BINDING_TIMELINE_ID),
        (dependencies.binding_clock_policy, "BindingClockPolicy",
         ACCEPTED_BINDING_CLOCK_POLICY_ID),
        (dependencies.schema_registry_contract, "EvidenceSchemaRegistryContract",
         ACCEPTED_SCHEMA_REGISTRY_ID),
    )
    for content, artifact_type, artifact_id in expected:
        if (not isinstance(content, ArtifactContent)
                or content.artifact_type != artifact_type
                or content.artifact_id != artifact_id
                or content.content_sha256 != artifact_id.rsplit(":", 1)[1]):
            _fail(f"Wrong accepted {artifact_type} identity")
    proof = dependencies.ttl_capture_placement_proof
    if (not isinstance(proof, ArtifactRef)
            or proof.artifact_id != ACCEPTED_TTL_PROOF_ID
            or proof.content_sha256 != ACCEPTED_TTL_PROOF_ID.rsplit(":", 1)[1]):
        _fail("Wrong accepted TTLCapturePlacementProof identity")


def resolve_row_binding(
    row: dict[str, Any],
    timeline: ArtifactContent,
    clock_policy: ArtifactContent,
) -> dict[str, Any]:
    """Resolve and verify one exact row authority without fallback."""
    source_kind = row.get("source_kind")
    origin_group = _SOURCE_ORIGINS.get(source_kind)
    if origin_group is None:
        _fail("No exact origin mapping for source kind")
    result = resolve_authoritative_binding(
        timeline,
        clock_policy,
        row.get("site_id"),
        origin_group,
        source_kind,
        row.get("observed_at"),
    )
    if result["status"] != "AUTHORIZED" or result["binding_epoch"] is None:
        _fail("Snapshot row has no unambiguous authoritative binding")
    epoch = result["binding_epoch"]
    if (row.get("producer_id") != epoch["producer_id"]
            or row.get("capture_source_id") != epoch["capture_source_id"]):
        _fail("Snapshot row does not match authoritative binding")
    return epoch


def authorized_descriptor(
    row: dict[str, Any],
    fields: Iterable[str],
    dependencies: SemanticAccountingDependencies,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return one exact R14 descriptor plus its authoritative binding epoch."""
    epoch = resolve_row_binding(
        row, dependencies.binding_timeline, dependencies.binding_clock_policy,
    )
    try:
        descriptor = {field: row[field] for field in fields}
    except KeyError as exc:
        raise DeviceFingerprintValidationError("Incomplete snapshot descriptor") from exc
    descriptor["binding_epoch_id"] = epoch["binding_epoch_id"]
    return descriptor, epoch


def ordered_binding_descriptors(epochs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate by epoch ID and apply the exact R14 binding ordering tuple."""
    by_id: dict[str, dict[str, Any]] = {}
    for epoch in epochs:
        epoch_id = epoch.get("binding_epoch_id") if isinstance(epoch, dict) else None
        if not isinstance(epoch_id, str) or not epoch_id:
            _fail("Invalid binding descriptor")
        previous = by_id.get(epoch_id)
        if previous is not None and canonical_artifact_json(previous) != canonical_artifact_json(epoch):
            _fail("Conflicting binding descriptor identity")
        by_id[epoch_id] = epoch
    return canonical_set(list(by_id.values()), lambda epoch: (
        epoch["effective_from_utc"],
        epoch["origin_group"],
        epoch["source_kind"],
        epoch["capture_source_id"],
        epoch["producer_id"],
        epoch["binding_epoch_id"],
    ))


def binding_descriptor_bytes(epochs: Iterable[dict[str, Any]]) -> tuple[int, int]:
    ordered = ordered_binding_descriptors(epochs)
    return sum(len(canonical_artifact_json(epoch)) for epoch in ordered), len(ordered)


def semantic_dependency_descriptor(
    dependencies: SemanticAccountingDependencies,
) -> dict[str, Any]:
    """Build the exact PRE-F-ADMIT snapshot dependency structures for sizing."""
    validate_semantic_accounting_dependencies(dependencies)
    proof_ref = dependencies.ttl_capture_placement_proof.as_dict()
    origin_payload = {
        "origin_runtime_admission_contract_version": 1,
        "tcp_state": "ENABLED",
        "tcp_reason_code": "TTL_PROOF_VALID",
        "ttl_capture_placement_proof": proof_ref,
    }
    origin = make_artifact_content("OriginRuntimeAdmission", origin_payload)
    return {
        "evidence_source_binding_timeline": _ref(dependencies.binding_timeline),
        "binding_clock_policy": _ref(dependencies.binding_clock_policy),
        "evidence_schema_registry_contract": _ref(dependencies.schema_registry_contract),
        "origin_runtime_admission": {
            "artifact_id": origin.artifact_id,
            "content_sha256": origin.content_sha256,
            "tcp_state": origin_payload["tcp_state"],
            "tcp_reason_code": origin_payload["tcp_reason_code"],
            "ttl_capture_placement_proof": proof_ref,
        },
        "classification_foundation_valid_from_utc": (
            ACCEPTED_CLASSIFICATION_FOUNDATION_VALID_FROM_UTC
        ),
    }


def semantic_dependency_reference_bytes(
    dependencies: SemanticAccountingDependencies,
) -> int:
    return len(canonical_artifact_json(semantic_dependency_descriptor(dependencies)))


def complete_semantic_byte_accounting(categories: dict[str, Any]) -> dict[str, Any]:
    """Complete the exact six-category formula, or fail closed."""
    if not isinstance(categories, dict) or set(categories) != _BYTE_CATEGORIES:
        _fail("Incomplete semantic byte accounting categories")
    if any(type(value) is not int or value < 0 for value in categories.values()):
        _fail("Invalid semantic byte accounting category")
    return {
        **categories,
        "total_semantic_input_bytes": sum(categories.values()),
        "descriptor_scope": "r14_snapshot_semantic_descriptors_complete",
        "final_binding_and_dependency_overhead_status": "COMPLETE",
    }
