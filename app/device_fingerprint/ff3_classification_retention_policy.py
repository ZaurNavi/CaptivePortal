"""F-F3 initial retention-policy gate; Owner acceptance is external evidence."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from .artifact_content import ArtifactContent, ArtifactRef, canonical_artifact_json
from .classification_retention_policy import (
    build_initial_classification_retention_policy_v1,
    make_classification_retention_policy,
)
from .foundation_gate_artifacts import make_gate_result_manifest
from .models import DeviceFingerprintValidationError

_INITIAL_SHA256 = "029c3534e076db6f7293c78e8a86c425b10c786d58713e77a077a19dfdda3e72"
_INITIAL_ID = f"ClassificationRetentionPolicy:v1:sha256:{_INITIAL_SHA256}"
_PRIVACY_ANALYSIS_LABEL = "classification_retention_privacy_storage_analysis"
_OWNER_REGISTRATION_LABEL = "classification_retention_owner_decision_registration"


@dataclass(frozen=True, slots=True)
class FF3GateExecution:
    classification_retention_policy_artifact_id: str
    classification_retention_policy_content_sha256: str
    build_1_artifact_id: str | None
    build_2_artifact_id: str | None
    double_build_bytes_equal: bool
    gate_result_manifest: ArtifactContent
    failure_reasons: tuple[str, ...]


def _retained_evidence_check(
    evidence: list[dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]]]:
    """Enforce F-F3 proof multiplicity; delegate row schema to GateResultManifest."""
    if not isinstance(evidence, list):
        raise DeviceFingerprintValidationError("Invalid retained evidence refs")
    if not evidence:
        return ["retained_evidence_required"], evidence
    for row in evidence:
        if not isinstance(row, dict) or not isinstance(row.get("evidence_label"), str):
            raise DeviceFingerprintValidationError("Invalid retained evidence ref")
    analysis = [row for row in evidence if row["evidence_label"] == _PRIVACY_ANALYSIS_LABEL]
    registration = [row for row in evidence if row["evidence_label"] == _OWNER_REGISTRATION_LABEL]
    reasons = []
    if len(analysis) != 1:
        reasons.append("classification_retention_privacy_storage_analysis_required")
    if len(registration) != 1:
        reasons.append("classification_retention_owner_decision_registration_required")
    # The multiplicity failure remains explicit even if identical mandatory refs
    # cannot both be represented in the generic manifest's canonical SET.
    manifest_rows = []
    seen = set()
    for row in evidence:
        if row["evidence_label"] in {_PRIVACY_ANALYSIS_LABEL, _OWNER_REGISTRATION_LABEL}:
            identity = canonical_artifact_json(row)
            if identity in seen:
                continue
            seen.add(identity)
        manifest_rows.append(row)
    return reasons, manifest_rows


def run_ff3_classification_retention_policy_gate(
    candidate: ArtifactContent, *, candidate_repository_commit_sha: str,
    candidate_repository_tree_sha: str, environment_identity: str,
    retained_evidence_refs: list[dict[str, Any]], decision_record_refs: list[str],
) -> FF3GateExecution:
    """Apply the fixed initial identity and Owner-evidence boundary without bypass."""
    if (not isinstance(candidate, ArtifactContent)
            or candidate.artifact_type != "ClassificationRetentionPolicy"):
        raise DeviceFingerprintValidationError("Invalid F-F3 candidate")
    reasons: list[str] = []
    build_1: ArtifactContent | None = None
    build_2: ArtifactContent | None = None
    bytes_equal = False
    try:
        build_1 = make_classification_retention_policy(candidate.semantic_payload)
        build_2 = make_classification_retention_policy(candidate.semantic_payload)
        bytes_equal = (build_1.semantic_payload_json == build_2.semantic_payload_json
                       and build_1.content_sha256 == build_2.content_sha256
                       and build_1.artifact_id == build_2.artifact_id)
        if not bytes_equal or build_1.artifact_id != candidate.artifact_id:
            reasons.append("classification_retention_policy_invalid")
    except DeviceFingerprintValidationError:
        reasons.append("classification_retention_policy_invalid")
    if candidate.artifact_id != _INITIAL_ID or candidate.content_sha256 != _INITIAL_SHA256:
        reasons.append("initial_classification_retention_policy_identity_mismatch")
    evidence_reasons, manifest_evidence = _retained_evidence_check(retained_evidence_refs)
    reasons.extend(evidence_reasons)
    if not isinstance(decision_record_refs, list) or any(
            not isinstance(ref, str) for ref in decision_record_refs):
        raise DeviceFingerprintValidationError("Invalid decision refs")
    unique_decisions = sorted(set(decision_record_refs))
    if not unique_decisions:
        reasons.append("classification_retention_owner_decision_required")
    reasons = sorted(set(reasons))
    status = "FAIL" if reasons else "PASS"
    manifest = make_gate_result_manifest({
        "gate_id": "F-F3", "gate_contract_version": "R14-F-F3-v1", "status": status,
        "candidate_repository_commit_sha": candidate_repository_commit_sha,
        "candidate_repository_tree_sha": candidate_repository_tree_sha,
        "input_artifact_refs": [],
        "output_artifact_refs": [ArtifactRef(candidate.artifact_id,
                                             candidate.content_sha256).as_dict()] if status == "PASS" else [],
        "retained_evidence_refs": manifest_evidence,
        "proof_execution_identity": {
            "execution_id": str(uuid.uuid4()), "executor_kind": "TECHLEAD_GATE_TOOL",
            "repository_commit_sha": candidate_repository_commit_sha,
            "repository_tree_sha": candidate_repository_tree_sha,
            "procedure_or_test_suite_id": "F-F3-classification-retention-policy-v1",
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
    return FF3GateExecution(
        candidate.artifact_id, candidate.content_sha256,
        build_1.artifact_id if build_1 else None,
        build_2.artifact_id if build_2 else None,
        bytes_equal, manifest, tuple(reasons),
    )
