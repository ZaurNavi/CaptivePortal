"""Closed R14 GateProofArtifact V1 builder."""

from __future__ import annotations

from typing import Any

from .artifact_content import ArtifactContent, make_artifact_content
from .foundation_gate_artifacts import make_gate_result_manifest
from .models import DeviceFingerprintValidationError

PROOF_KINDS = frozenset({
    "SNAPSHOT_CONCURRENCY", "SNAPSHOT_PERFORMANCE", "RUNTIME_PROFILE_ATOMICITY",
    "SNAPSHOT_MATERIALIZATION_EXECUTION", "SOURCE_EVALUABILITY_EXECUTION",
    "ORIGIN_ASSESSMENT_EXECUTION", "FUSION_EXECUTION", "REQUEST_ASSEMBLY_DETERMINISM",
    "CLASSIFICATION_AUDIT_PERSISTENCE", "OFFLINE_FAILURE_ISOLATION",
    "TASK04_PRODUCT_VALIDATION", "ARTIFACT_GRAPH_ACYCLICITY",
    "CLASSIFICATION_PROFILE_COMPATIBILITY",
})
_FIELDS = frozenset({
    "proof_kind", "source_gate_id", "candidate_repository_commit_sha",
    "candidate_repository_tree_sha", "input_artifact_refs", "procedure_or_test_suite_id",
    "proof_execution_identity", "canonical_result_summary", "retained_evidence_refs",
})


def make_gate_proof_artifact(payload: dict[str, Any]) -> ArtifactContent:
    """Validate V1 proof shape, reusing generic gate ref/evidence/proof rules."""
    if not isinstance(payload, dict) or set(payload) != _FIELDS:
        raise DeviceFingerprintValidationError("Invalid GateProofArtifact shape")
    if not isinstance(payload["proof_kind"], str) or payload["proof_kind"] not in PROOF_KINDS:
        raise DeviceFingerprintValidationError("Invalid proof kind")
    if any(not isinstance(payload[field], str) or not payload[field] for field in (
            "source_gate_id", "procedure_or_test_suite_id", "canonical_result_summary")):
        raise DeviceFingerprintValidationError("Invalid proof text")
    # The shared validator owns exact ProofExecutionIdentity, refs, retained
    # evidence, Git SHA, and canonical SET semantics. No duplicate schema fork.
    generic = make_gate_result_manifest({
        "gate_id": payload["source_gate_id"],
        "gate_contract_version": "R14-GateProofArtifact-v1",
        "status": "PASS",
        "candidate_repository_commit_sha": payload["candidate_repository_commit_sha"],
        "candidate_repository_tree_sha": payload["candidate_repository_tree_sha"],
        "input_artifact_refs": payload["input_artifact_refs"],
        "output_artifact_refs": [],
        "retained_evidence_refs": payload["retained_evidence_refs"],
        "proof_execution_identity": payload["proof_execution_identity"],
        "trusted_time_inputs": {
            "foundation_knowledge_evaluation_at_utc": None,
            "foundation_admission_evaluation_at_utc": None,
            "knowledge_evaluation_at_utc": None,
        },
        "decision_record_refs": [],
    }).semantic_payload
    return make_artifact_content("GateProofArtifact", {
        **payload,
        "input_artifact_refs": generic["input_artifact_refs"],
        "retained_evidence_refs": generic["retained_evidence_refs"],
        "proof_execution_identity": generic["proof_execution_identity"],
    })
