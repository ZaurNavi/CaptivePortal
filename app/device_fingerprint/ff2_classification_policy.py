"""F-F2 initial ClassificationPolicy admission proof; no classifier runtime."""

from __future__ import annotations

import uuid
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .artifact_content import ArtifactContent, ArtifactRef, canonical_artifact_json, canonical_set
from .classification_policy import (
    _PolicyCrossLayerContamination, _PolicyMatrixIncomplete, _PolicyMatrixMismatch,
    build_initial_classification_policy_v1, make_classification_policy,
    validate_classification_policy_dependencies,
)
from .foundation_gate_artifacts import make_gate_result_manifest
from .models import DeviceFingerprintValidationError

_INITIAL_IDS = {
    "classification_taxonomy": (
        "ClassificationTaxonomy:v1:sha256:"
        "399e2a337e7ebecb1bd7a9b21dff5e744c13be36313bc39f16832bc7a57a4d10"
    ),
    "alias_mapping": (
        "AliasMapping:v1:sha256:"
        "f1cdd7c9510c2a33bad99bd1ae15eaccd20fcb828a52e02533b9917fdfc2e228"
    ),
    "evidence_adapter_contract_set": (
        "EvidenceAdapterContractSet:v1:sha256:"
        "7cca6802ebc5839317643dcb584173b75d985477da687ab0d8fe5802b181f788"
    ),
}
_INITIAL_REASONS = {
    "classification_taxonomy": "initial_taxonomy_identity_mismatch",
    "alias_mapping": "initial_alias_identity_mismatch",
    "evidence_adapter_contract_set": "initial_adapter_identity_mismatch",
}
_CLASSIFICATION_POLICY_TEST_VECTOR_SHA256 = (
    "6ac3f1016072add2df4f954e7d50efe54e093887da8e6304e43b14d57537de07"
)
_CLASSIFICATION_POLICY_TEST_VECTOR_LABEL = (
    "classification_policy_test_vectors"
)
_CLASSIFICATION_POLICY_REVIEW_REPORT_LABEL = (
    "classification_policy_review_report"
)


@dataclass(frozen=True, slots=True)
class FF2GateExecution:
    classification_policy_artifact_id: str
    classification_policy_content_sha256: str
    build_1_artifact_id: str | None
    build_2_artifact_id: str | None
    double_build_bytes_equal: bool
    permutation_invariant: bool
    dependency_validation_passed: bool
    gate_result_manifest: ArtifactContent
    failure_reasons: tuple[str, ...]


def _ref(content: ArtifactContent) -> dict[str, str]:
    if not isinstance(content, ArtifactContent):
        raise DeviceFingerprintValidationError("Invalid F-F2 prerequisite")
    return ArtifactRef(content.artifact_id, content.content_sha256).as_dict()


def _permuted_candidate(candidate: ArtifactContent) -> ArtifactContent:
    payload = candidate.semantic_payload
    for name in (
        "same_origin_ambiguity_conflict_rules", "same_origin_conflict_strength_rules",
        "cross_origin_fusion_matrix", "recognized_out_of_scope_applicability",
    ):
        payload[name].reverse()
    return make_classification_policy(payload)


def _retained_evidence_check(
    evidence: list[dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]]]:
    """Check F-F2 proof labels; leave evidence schema validation to the manifest."""
    if not isinstance(evidence, list):
        raise DeviceFingerprintValidationError("Invalid retained evidence refs")
    if not evidence:
        return ["retained_evidence_required"], evidence
    for row in evidence:
        if not isinstance(row, dict) or not isinstance(row.get("evidence_label"), str):
            raise DeviceFingerprintValidationError("Invalid retained evidence ref")
    vectors = [row for row in evidence if row["evidence_label"] ==
               _CLASSIFICATION_POLICY_TEST_VECTOR_LABEL]
    reports = [row for row in evidence if row["evidence_label"] ==
               _CLASSIFICATION_POLICY_REVIEW_REPORT_LABEL]
    reasons = []
    if (len(vectors) != 1
            or vectors[0].get("file_sha256") != _CLASSIFICATION_POLICY_TEST_VECTOR_SHA256
            or vectors[0].get("media_type") != "application/json"):
        reasons.append("classification_policy_test_vectors_evidence_invalid")
    if len(reports) != 1:
        reasons.append("classification_policy_review_report_required")
    # Preserve a FAIL manifest for identical mandatory-proof duplicates; leave
    # unrelated rows untouched for the generic manifest's schema/SET validator.
    manifest_rows = []
    seen = set()
    for row in evidence:
        if row["evidence_label"] in {
                _CLASSIFICATION_POLICY_TEST_VECTOR_LABEL,
                _CLASSIFICATION_POLICY_REVIEW_REPORT_LABEL}:
            identity = canonical_artifact_json(row)
            if identity in seen:
                continue
            seen.add(identity)
        manifest_rows.append(row)
    return reasons, manifest_rows


def run_ff2_classification_policy_gate(
    candidate: ArtifactContent, *, classification_taxonomy: ArtifactContent,
    alias_mapping: ArtifactContent, evidence_adapter_contract_set: ArtifactContent,
    candidate_repository_commit_sha: str, candidate_repository_tree_sha: str,
    environment_identity: str, retained_evidence_refs: list[dict[str, Any]],
    decision_record_refs: list[str],
) -> FF2GateExecution:
    """Admit only the initial F-F2 policy; no public bypass or acceptance fabrication."""
    if not isinstance(candidate, ArtifactContent) or candidate.artifact_type != "ClassificationPolicy":
        raise DeviceFingerprintValidationError("Invalid F-F2 candidate")
    inputs = (classification_taxonomy, alias_mapping, evidence_adapter_contract_set)
    refs = canonical_set([_ref(content) for content in inputs], lambda ref: ref["artifact_id"])
    reasons: list[str] = []
    build_1: ArtifactContent | None = None
    build_2: ArtifactContent | None = None
    bytes_equal = False
    permutation_invariant = False
    dependencies_valid = False
    candidate_valid = False
    try:
        build_1 = make_classification_policy(candidate.semantic_payload)
        build_2 = make_classification_policy(deepcopy(candidate.semantic_payload))
        bytes_equal = (build_1.semantic_payload_json == build_2.semantic_payload_json
                       and build_1.content_sha256 == build_2.content_sha256
                       and build_1.artifact_id == build_2.artifact_id)
        permutation_invariant = _permuted_candidate(candidate).artifact_id == candidate.artifact_id
        candidate_valid = build_1.artifact_id == candidate.artifact_id
        if not bytes_equal or not permutation_invariant or not candidate_valid:
            reasons.append("classification_policy_invalid")
    except _PolicyMatrixIncomplete:
        reasons.append("classification_policy_matrix_incomplete")
    except _PolicyMatrixMismatch:
        reasons.append("classification_policy_matrix_mismatch")
    except _PolicyCrossLayerContamination:
        reasons.append("classification_policy_cross_layer_contamination")
    except DeviceFingerprintValidationError:
        reasons.append("classification_policy_invalid")
    if candidate_valid:
        try:
            validate_classification_policy_dependencies(
                candidate, classification_taxonomy=classification_taxonomy,
                alias_mapping=alias_mapping,
                evidence_adapter_contract_set=evidence_adapter_contract_set,
            )
            dependencies_valid = True
        except DeviceFingerprintValidationError:
            reasons.append("classification_policy_dependency_invalid")
    prerequisites = {
        "classification_taxonomy": classification_taxonomy,
        "alias_mapping": alias_mapping,
        "evidence_adapter_contract_set": evidence_adapter_contract_set,
    }
    for name, expected in _INITIAL_IDS.items():
        if prerequisites[name].artifact_id != expected:
            reasons.append(_INITIAL_REASONS[name])
    if candidate_valid:
        try:
            initial = build_initial_classification_policy_v1(*inputs)
            if candidate.artifact_id != initial.artifact_id:
                reasons.append("classification_policy_matrix_mismatch")
        except DeviceFingerprintValidationError:
            reasons.append("classification_policy_invalid")
    evidence_reasons, manifest_evidence = _retained_evidence_check(retained_evidence_refs)
    reasons.extend(evidence_reasons)
    if not isinstance(decision_record_refs, list) or any(
            not isinstance(ref, str) for ref in decision_record_refs):
        raise DeviceFingerprintValidationError("Invalid decision refs")
    unique_decisions = sorted(set(decision_record_refs))
    if len(unique_decisions) < 2:
        reasons.append("owner_techlead_decisions_required")
    reasons = sorted(set(reasons))
    status = "FAIL" if reasons else "PASS"
    manifest = make_gate_result_manifest({
        "gate_id": "F-F2", "gate_contract_version": "R14-F-F2-v1", "status": status,
        "candidate_repository_commit_sha": candidate_repository_commit_sha,
        "candidate_repository_tree_sha": candidate_repository_tree_sha,
        "input_artifact_refs": refs,
        "output_artifact_refs": [_ref(candidate)] if status == "PASS" else [],
        "retained_evidence_refs": manifest_evidence,
        "proof_execution_identity": {
            "execution_id": str(uuid.uuid4()), "executor_kind": "TECHLEAD_GATE_TOOL",
            "repository_commit_sha": candidate_repository_commit_sha,
            "repository_tree_sha": candidate_repository_tree_sha,
            "procedure_or_test_suite_id": "F-F2-classification-policy-v1",
            "environment_identity": environment_identity,
            "execution_artifact_sha256": None,
        },
        "trusted_time_inputs": {
            "foundation_knowledge_evaluation_at_utc": None,
            "foundation_admission_evaluation_at_utc": None,
            "knowledge_evaluation_at_utc": None,
        },
        "decision_record_refs": unique_decisions,
    })
    return FF2GateExecution(
        candidate.artifact_id, candidate.content_sha256,
        build_1.artifact_id if build_1 else None,
        build_2.artifact_id if build_2 else None,
        bytes_equal, permutation_invariant, dependencies_valid,
        manifest, tuple(reasons),
    )
