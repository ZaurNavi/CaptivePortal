"""Closed R14 initial Foundation admission ArtifactContent contracts."""

from __future__ import annotations

import re
from typing import Any

from .artifact_content import ArtifactContent, ArtifactRef, canonical_set, make_artifact_content
from .foundation_gate_artifacts import make_gate_result_manifest
from .models import DeviceFingerprintValidationError
from .validation import parse_utc

MANDATORY_PRE_ADMISSION_GATES = tuple(
    f"F-{family}{number}"
    for family, numbers in (
        ("A", range(1, 6)), ("B", range(0, 4)), ("C", range(1, 4)),
        ("D", range(1, 2)), ("E", range(1, 8)), ("F", range(1, 7)),
    )
    for number in numbers
)

_SHA256 = re.compile(r"[0-9a-f]{64}")
_GIT_SHA = re.compile(r"[0-9a-f]{40}")
_ORIGIN_FIELDS = frozenset({
    "origin_runtime_admission_contract_version", "tcp_state", "tcp_reason_code",
    "ttl_capture_placement_proof",
})
_MANIFEST_REFS = {
    "architecture_contract_reference": "ArchitectureContractReference",
    "evidence_schema_registry_contract": "EvidenceSchemaRegistryContract",
    "evidence_adapter_contract_set": "EvidenceAdapterContractSet",
    "knowledge_bundle": "KnowledgeBundle",
    "evidence_source_binding_timeline": "EvidenceSourceBindingTimeline",
    "binding_clock_policy": "BindingClockPolicy",
    "source_health_policy": "SourceHealthPolicy",
    "snapshot_content_policy": "SnapshotContentPolicy",
    "snapshot_execution_policy": "SnapshotExecutionPolicy",
    "classification_policy": "ClassificationPolicy",
    "classification_retention_policy": "ClassificationRetentionPolicy",
    "product_validation_policy": "ProductValidationPolicy",
    "k2a_conformance_package": "K2AConformancePackage",
    "ttl_capture_placement_proof": "TTLCapturePlacementProof",
    "origin_runtime_admission": "OriginRuntimeAdmission",
    "portal_headers_v2_capability_disposition": "CapabilityDisposition",
}
_MANIFEST_REF_SETS = {
    "pre_admission_gate_result_manifests": "GateResultManifest",
    "source_health_emitter_contracts": "SourceHealthEmitterContract",
    "knowledge_freshness_policies": "KnowledgeFreshnessPolicy",
    "source_governance_records": "SourceGovernanceRecord",
    "knowledge_provenance_manifests": "KnowledgeProvenanceManifest",
}
_MANIFEST_FIELDS = frozenset({
    "foundation_manifest_version", "architecture_document_sha256",
    "foundation_repository_commit_sha", "foundation_repository_tree_sha",
    "foundation_knowledge_evaluation_at_utc", "foundation_admission_evaluation_at_utc",
    "classification_foundation_valid_from_utc",
    "task01_database_schema_generation_contract_version",
    "task01_watermark_generation_contract_version",
    "mandatory_pre_admission_foundation_gate_ids",
    *_MANIFEST_REFS, *_MANIFEST_REF_SETS,
})
_ARCHITECTURE_FIELDS = frozenset({
    "architecture_contract_name", "architecture_revision", "architecture_status",
    "architecture_document_sha256",
})


def _fail(label: str) -> None:
    raise DeviceFingerprintValidationError(f"Invalid {label}")


def _version(value: Any, label: str) -> int:
    if type(value) is not int or not 1 <= value <= 2_147_483_647:
        _fail(label)
    return value


def _match(value: Any, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        _fail(label)
    return value


def _ref(value: Any, target: str) -> dict[str, str]:
    ref = ArtifactRef.from_dict(value)
    if not ref.artifact_id.startswith(f"{target}:v1:sha256:"):
        _fail(f"{target} reference")
    return ref.as_dict()


def _ref_set(value: Any, target: str) -> list[dict[str, str]]:
    if not isinstance(value, list):
        _fail(f"{target} reference SET")
    normalized = [_ref(item, target) for item in value]
    if len({item["artifact_id"] for item in normalized}) != len(normalized):
        _fail(f"duplicate {target} reference")
    return canonical_set(normalized, lambda item: item["artifact_id"])


def make_architecture_contract_reference(payload: dict[str, Any]) -> ArtifactContent:
    if not isinstance(payload, dict) or set(payload) != _ARCHITECTURE_FIELDS:
        _fail("ArchitectureContractReference shape")
    if (payload["architecture_contract_name"] != "DEVICE-FINGERPRINT-03A-R2 / TASK-04"
            or payload["architecture_revision"] != "R14"
            or payload["architecture_status"] != "FINAL"):
        _fail("ArchitectureContractReference authority")
    _match(payload["architecture_document_sha256"], _SHA256, "architecture document SHA256")
    return make_artifact_content("ArchitectureContractReference", payload)


def build_f_admit_input_refs(
    architecture: ArtifactContent, prerequisite_gates: list[ArtifactContent],
) -> list[dict[str, str]]:
    """Canonical exact input closure for the final F-ADMIT GateResultManifest."""
    if (not isinstance(architecture, ArtifactContent) or
            make_architecture_contract_reference(architecture.semantic_payload) != architecture):
        _fail("F-ADMIT architecture input")
    if not isinstance(prerequisite_gates, list):
        _fail("F-ADMIT prerequisite inputs")
    refs = [_ref(ArtifactRef(architecture.artifact_id, architecture.content_sha256).as_dict(),
                 "ArchitectureContractReference")]
    gate_ids = set()
    for gate in prerequisite_gates:
        if (not isinstance(gate, ArtifactContent) or gate.artifact_type != "GateResultManifest" or
                make_gate_result_manifest(gate.semantic_payload) != gate):
            _fail("F-ADMIT prerequisite GateResult")
        gate_payload = gate.semantic_payload
        if gate_payload["status"] != "PASS" or gate_payload["gate_id"] in gate_ids:
            _fail("F-ADMIT prerequisite gate status/identity")
        gate_ids.add(gate_payload["gate_id"])
        refs.append(ArtifactRef(gate.artifact_id, gate.content_sha256).as_dict())
        refs.extend(gate_payload["output_artifact_refs"])
    if gate_ids != set(MANDATORY_PRE_ADMISSION_GATES):
        _fail("F-ADMIT prerequisite gate inventory")
    by_id: dict[str, dict[str, str]] = {}
    for value in refs:
        ref = ArtifactRef.from_dict(value).as_dict()
        previous = by_id.get(ref["artifact_id"])
        if previous is not None and previous != ref:
            _fail("F-ADMIT input digest conflict")
        by_id[ref["artifact_id"]] = ref
    return canonical_set(list(by_id.values()), lambda value: value["artifact_id"])


def make_origin_runtime_admission(payload: dict[str, Any]) -> ArtifactContent:
    if not isinstance(payload, dict) or set(payload) != _ORIGIN_FIELDS:
        _fail("OriginRuntimeAdmission shape")
    if payload["origin_runtime_admission_contract_version"] != 1 or type(
            payload["origin_runtime_admission_contract_version"]) is not int:
        _fail("origin version")
    state, reason, proof = (payload[key] for key in (
        "tcp_state", "tcp_reason_code", "ttl_capture_placement_proof"))
    if state == "ENABLED":
        if reason != "TTL_PROOF_VALID" or proof is None:
            _fail("enabled origin proof")
        proof = _ref(proof, "TTLCapturePlacementProof")
    elif state == "DISABLED":
        if reason not in ("TTL_PROOF_INVALID", "PROFILE_POLICY_DISABLED") or proof is not None:
            _fail("disabled origin proof")
    else:
        _fail("origin TCP state")
    return make_artifact_content("OriginRuntimeAdmission", {
        **payload, "ttl_capture_placement_proof": proof,
    })


def make_foundation_admission_manifest(payload: dict[str, Any]) -> ArtifactContent:
    if not isinstance(payload, dict) or set(payload) != _MANIFEST_FIELDS:
        _fail("FoundationAdmissionManifest shape")
    if payload["foundation_manifest_version"] != 1 or type(payload["foundation_manifest_version"]) is not int:
        _fail("foundation manifest version")
    _match(payload["architecture_document_sha256"], _SHA256, "architecture document SHA256")
    for field in ("foundation_repository_commit_sha", "foundation_repository_tree_sha"):
        _match(payload[field], _GIT_SHA, field)
    for field in (
        "foundation_knowledge_evaluation_at_utc", "foundation_admission_evaluation_at_utc",
        "classification_foundation_valid_from_utc",
    ):
        parse_utc(payload[field])
    for field in (
        "task01_database_schema_generation_contract_version",
        "task01_watermark_generation_contract_version",
    ):
        _version(payload[field], field)
    ids = payload["mandatory_pre_admission_foundation_gate_ids"]
    if (not isinstance(ids, list) or not all(isinstance(item, str) for item in ids)
            or len(ids) != len(MANDATORY_PRE_ADMISSION_GATES)
            or set(ids) != set(MANDATORY_PRE_ADMISSION_GATES)):
        _fail("mandatory pre-admission gate inventory")
    normalized = dict(payload)
    normalized["mandatory_pre_admission_foundation_gate_ids"] = canonical_set(ids, lambda item: item)
    for field, target in _MANIFEST_REFS.items():
        normalized[field] = _ref(payload[field], target)
    for field, target in _MANIFEST_REF_SETS.items():
        normalized[field] = _ref_set(payload[field], target)
    if len(normalized["pre_admission_gate_result_manifests"]) != len(MANDATORY_PRE_ADMISSION_GATES):
        _fail("pre-admission GateResultManifest count")
    for field in (
        "source_health_emitter_contracts", "knowledge_freshness_policies",
        "source_governance_records", "knowledge_provenance_manifests",
    ):
        if not normalized[field]:
            _fail(f"empty {field}")
    return make_artifact_content("FoundationAdmissionManifest", normalized)


def validate_initial_foundation_manifest_lineage(
    manifest: ArtifactContent, origin: ArtifactContent, ttl_proof: ArtifactContent,
) -> bool:
    """Resolve the mandatory direct/transitive Origin ↔ TTL relationship."""
    if (not isinstance(manifest, ArtifactContent) or
            make_foundation_admission_manifest(manifest.semantic_payload).artifact_id != manifest.artifact_id or
            not isinstance(origin, ArtifactContent) or
            make_origin_runtime_admission(origin.semantic_payload).artifact_id != origin.artifact_id or
            not isinstance(ttl_proof, ArtifactContent) or
            ttl_proof.artifact_type != "TTLCapturePlacementProof"):
        _fail("initial Foundation lineage")
    fields = manifest.semantic_payload
    origin_ref = ArtifactRef(origin.artifact_id, origin.content_sha256).as_dict()
    ttl_ref = ArtifactRef(ttl_proof.artifact_id, ttl_proof.content_sha256).as_dict()
    if (fields["origin_runtime_admission"] != origin_ref or
            fields["ttl_capture_placement_proof"] != ttl_ref or
            origin.semantic_payload["tcp_state"] != "ENABLED" or
            origin.semantic_payload["tcp_reason_code"] != "TTL_PROOF_VALID" or
            origin.semantic_payload["ttl_capture_placement_proof"] != ttl_ref):
        _fail("initial Origin/TTL lineage")
    return True
