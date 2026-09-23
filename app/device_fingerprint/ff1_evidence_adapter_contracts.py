"""Deterministic initial F-F1 admission proof; no classifier or runtime activation."""

from __future__ import annotations

import uuid
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .artifact_content import ArtifactContent, ArtifactRef, canonical_set
from .evidence_adapter_contracts import (
    _AdapterRegistryCompatibilityError,
    build_initial_evidence_adapter_contract_set_v1,
    make_evidence_adapter_contract_set,
    validate_evidence_adapter_contract_set_dependencies,
)
from .foundation_gate_artifacts import make_gate_result_manifest
from .models import DeviceFingerprintValidationError

_INITIAL_IDS = {
    "evidence_schema_registry": "EvidenceSchemaRegistryContract:v1:sha256:090d763e99247ca3b10be34976069e4e7e708be0899e21a15c6e103a015f7814",
    "capability_disposition": "CapabilityDisposition:v1:sha256:53ae5181e5a1fc8aa371214ded51c2ca719aafc21ba27c745b3cfafe5a77ae50",
    "k2a_conformance_package": "K2AConformancePackage:v1:sha256:bbe6fa22ac50e568ee4580faac4ad09f7301bb38f6af2ab2075b8adc39262328",
    "k3_portal_rule_set": "K3PortalRuleSet:v1:sha256:5e47945da04c60baf8dc1d1a7777a4e2efa2dfa0e80bf7639a97ba51d6fdb28f",
}


@dataclass(frozen=True, slots=True)
class FF1GateExecution:
    adapter_contract_set_artifact_id: str | None
    adapter_contract_set_content_sha256: str | None
    build_1_artifact_id: str | None
    build_2_artifact_id: str | None
    double_build_bytes_equal: bool
    permutation_invariant: bool
    dependency_validation_passed: bool
    gate_result_manifest: ArtifactContent
    failure_reasons: tuple[str, ...]


def _ref(content: ArtifactContent) -> dict[str, str]:
    if not isinstance(content, ArtifactContent):
        raise DeviceFingerprintValidationError("Invalid F-F1 prerequisite")
    return ArtifactRef(content.artifact_id, content.content_sha256).as_dict()


def _initial_anchor_reasons(
    candidate: ArtifactContent, *, evidence_schema_registry: ArtifactContent,
    capability_disposition: ArtifactContent, k2a_conformance_package: ArtifactContent,
    k1_record_set: ArtifactContent, k3_portal_rule_set: ArtifactContent,
    k4_record_set: ArtifactContent,
) -> list[str]:
    dependencies = locals()
    reasons = []
    for name, expected in _INITIAL_IDS.items():
        if dependencies[name].artifact_id != expected:
            code = {
                "evidence_schema_registry": "initial_registry_identity_mismatch",
                "capability_disposition": "initial_capability_disposition_mismatch",
                "k2a_conformance_package": "initial_k2a_identity_mismatch",
                "k3_portal_rule_set": "initial_k3_identity_mismatch",
            }[name]
            reasons.append(code)
    disposition = capability_disposition.semantic_payload
    if disposition != {
        "capability_id": "portal_headers/2", "status": "ADMITTED", "reason_codes": [],
        "fallback_source_kind": None, "fallback_feature_schema_version": None,
    }:
        reasons.append("initial_capability_disposition_mismatch")
    k3 = k3_portal_rule_set.semantic_payload
    if (len(k3.get("rules", [])) != 13 or len(k3.get("test_vectors", [])) != 21
            or k3.get("admitted_feature_schema_versions") != [1, 2]
            or any(rule.get("base_claim_strength") == "strong" for rule in k3.get("rules", []))):
        reasons.append("initial_k3_identity_mismatch")
    k1 = k1_record_set.semantic_payload
    if (k1.get("knowledge_slot") != "K1"
            or any(record.get("record_type") != "K1_DHCP"
                   or any(outcome.get("base_claim_strength") == "strong"
                          for outcome in record.get("candidate_taxonomy_refs", []))
                   for record in k1.get("records", []))):
        reasons.append("initial_k1_contract_mismatch")
    k4 = k4_record_set.semantic_payload
    if (k4.get("knowledge_slot") != "K4"
            or any(record.get("record_type") != "K4_IEEE_ASSIGNMENT" for record in k4.get("records", []))):
        reasons.append("initial_k4_contract_mismatch")
    if candidate.artifact_id != build_initial_evidence_adapter_contract_set_v1(
            evidence_schema_registry).artifact_id:
        reasons.append("initial_matrix_mismatch")
    return reasons


def _permuted_candidate(candidate: ArtifactContent) -> ArtifactContent:
    payload = candidate.semantic_payload
    payload["adapter_entries"].reverse()
    for entry in payload["adapter_entries"]:
        if entry["adapter_kind"] != "TASK01_EVIDENCE":
            continue
        for name in ("supported_source_subtypes", "extractor_name_constraints",
                     "extractor_version_constraints", "rule_version_constraints"):
            entry[name].reverse()
        for fields in entry["required_fields_by_dimension"].values():
            fields.reverse()
    return make_evidence_adapter_contract_set(payload)


def run_ff1_evidence_adapter_contract_gate(
    candidate: ArtifactContent, *, evidence_schema_registry: ArtifactContent,
    capability_disposition: ArtifactContent, k2a_conformance_package: ArtifactContent,
    k1_record_set: ArtifactContent, k3_portal_rule_set: ArtifactContent,
    k4_record_set: ArtifactContent, candidate_repository_commit_sha: str,
    candidate_repository_tree_sha: str, environment_identity: str,
    retained_evidence_refs: list[dict[str, Any]],
) -> FF1GateExecution:
    """Always apply initial anchors; no caller-controlled admission bypass."""
    if not isinstance(candidate, ArtifactContent) or candidate.artifact_type != "EvidenceAdapterContractSet":
        raise DeviceFingerprintValidationError("Invalid F-F1 candidate")
    inputs = (
        evidence_schema_registry, capability_disposition, k2a_conformance_package,
        k1_record_set, k3_portal_rule_set, k4_record_set,
    )
    refs = canonical_set([_ref(content) for content in inputs], lambda ref: ref["artifact_id"])
    reasons: list[str] = []
    dependencies_valid = False
    build_1: ArtifactContent | None = None
    build_2: ArtifactContent | None = None
    bytes_equal = False
    permutation_invariant = False
    try:
        build_1 = make_evidence_adapter_contract_set(candidate.semantic_payload)
        build_2 = make_evidence_adapter_contract_set(deepcopy(candidate.semantic_payload))
        bytes_equal = (build_1.semantic_payload_json == build_2.semantic_payload_json
                       and build_1.content_sha256 == build_2.content_sha256
                       and build_1.artifact_id == build_2.artifact_id)
        if not bytes_equal:
            reasons.append("double_build_identity_mismatch")
        permutation_invariant = _permuted_candidate(candidate).artifact_id == candidate.artifact_id
        if not permutation_invariant:
            reasons.append("adapter_set_permutation_mismatch")
        validate_evidence_adapter_contract_set_dependencies(
            candidate, evidence_schema_registry=evidence_schema_registry,
            capability_disposition=capability_disposition,
            k2a_conformance_package=k2a_conformance_package,
            k1_record_set=k1_record_set, k3_portal_rule_set=k3_portal_rule_set,
            k4_record_set=k4_record_set,
        )
        dependencies_valid = True
    except _AdapterRegistryCompatibilityError:
        reasons.append("adapter_registry_incompatible")
    except DeviceFingerprintValidationError:
        reasons.append("adapter_dependency_invalid")
    try:
        reasons.extend(_initial_anchor_reasons(
            candidate, evidence_schema_registry=evidence_schema_registry,
            capability_disposition=capability_disposition,
            k2a_conformance_package=k2a_conformance_package,
            k1_record_set=k1_record_set, k3_portal_rule_set=k3_portal_rule_set,
            k4_record_set=k4_record_set,
        ))
    except DeviceFingerprintValidationError:
        reasons.append("initial_matrix_mismatch")
    if not retained_evidence_refs:
        reasons.append("retained_evidence_required")
    reasons = sorted(set(reasons))
    status = "FAIL" if reasons else "PASS"
    manifest = make_gate_result_manifest({
        "gate_id": "F-F1", "gate_contract_version": "R14-F-F1-v1",
        "status": status,
        "candidate_repository_commit_sha": candidate_repository_commit_sha,
        "candidate_repository_tree_sha": candidate_repository_tree_sha,
        "input_artifact_refs": refs,
        "output_artifact_refs": [_ref(candidate)] if status == "PASS" else [],
        "retained_evidence_refs": retained_evidence_refs,
        "proof_execution_identity": {
            "execution_id": str(uuid.uuid4()), "executor_kind": "TECHLEAD_GATE_TOOL",
            "repository_commit_sha": candidate_repository_commit_sha,
            "repository_tree_sha": candidate_repository_tree_sha,
            "procedure_or_test_suite_id": "F-F1-evidence-adapter-contract-set-v1",
            "environment_identity": environment_identity,
            "execution_artifact_sha256": None,
        },
        "trusted_time_inputs": {
            "foundation_knowledge_evaluation_at_utc": None,
            "foundation_admission_evaluation_at_utc": None,
            "knowledge_evaluation_at_utc": None,
        },
        "decision_record_refs": [],
    })
    return FF1GateExecution(
        candidate.artifact_id, candidate.content_sha256,
        build_1.artifact_id if build_1 else None,
        build_2.artifact_id if build_2 else None,
        bytes_equal, permutation_invariant, dependencies_valid, manifest,
        tuple(reasons),
    )
