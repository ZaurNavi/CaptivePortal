"""F-F4 initial product-validation-policy gate; Owner acceptance is external."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from .artifact_content import ArtifactContent, ArtifactRef, canonical_artifact_json
from .foundation_gate_artifacts import make_gate_result_manifest
from .models import DeviceFingerprintValidationError
from .product_validation_policy import make_product_validation_policy

_INITIAL_SHA256 = "806779ca1844e55083a2c1c464cf8d94a9bdd0b2f97436d203b63fd03e81bea5"
_INITIAL_ID = f"ProductValidationPolicy:v1:sha256:{_INITIAL_SHA256}"
_REVIEW_LABEL = "product_validation_policy_review"
_REGISTRATION_LABEL = "product_validation_owner_decision_registration"


@dataclass(frozen=True, slots=True)
class FF4GateExecution:
    product_validation_policy_artifact_id: str
    product_validation_policy_content_sha256: str
    build_1_artifact_id: str | None
    build_2_artifact_id: str | None
    double_build_bytes_equal: bool
    gate_result_manifest: ArtifactContent
    failure_reasons: tuple[str, ...]


def _retained_evidence_check(
    evidence: list[dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]]]:
    """Check mandatory label multiplicity; generic manifest validates each row."""
    if not isinstance(evidence, list):
        raise DeviceFingerprintValidationError("Invalid retained evidence refs")
    if not evidence:
        return ["retained_evidence_required"], evidence
    for row in evidence:
        if not isinstance(row, dict) or not isinstance(row.get("evidence_label"), str):
            raise DeviceFingerprintValidationError("Invalid retained evidence ref")
    review = [row for row in evidence if row["evidence_label"] == _REVIEW_LABEL]
    registration = [row for row in evidence if row["evidence_label"] == _REGISTRATION_LABEL]
    reasons = []
    if len(review) != 1:
        reasons.append("product_validation_policy_review_required")
    if len(registration) != 1:
        reasons.append("product_validation_owner_decision_registration_required")
    # Identical duplicate mandatory rows are still a multiplicity failure.
    # De-duplicate them only for the generic manifest's canonical SET.
    manifest_rows = []
    seen = set()
    for row in evidence:
        if row["evidence_label"] in {_REVIEW_LABEL, _REGISTRATION_LABEL}:
            identity = canonical_artifact_json(row)
            if identity in seen:
                continue
            seen.add(identity)
        manifest_rows.append(row)
    return reasons, manifest_rows


def run_ff4_product_validation_policy_gate(
    candidate: ArtifactContent, *, candidate_repository_commit_sha: str,
    candidate_repository_tree_sha: str, environment_identity: str,
    retained_evidence_refs: list[dict[str, Any]], decision_record_refs: list[str],
) -> FF4GateExecution:
    """Evaluate only the fixed initial identity and required Owner evidence."""
    if (not isinstance(candidate, ArtifactContent)
            or candidate.artifact_type != "ProductValidationPolicy"):
        raise DeviceFingerprintValidationError("Invalid F-F4 candidate")
    reasons: list[str] = []
    build_1: ArtifactContent | None = None
    build_2: ArtifactContent | None = None
    bytes_equal = False
    try:
        build_1 = make_product_validation_policy(candidate.semantic_payload)
        build_2 = make_product_validation_policy(candidate.semantic_payload)
        bytes_equal = (build_1.semantic_payload_json == build_2.semantic_payload_json
                       and build_1.content_sha256 == build_2.content_sha256
                       and build_1.artifact_id == build_2.artifact_id)
        if not bytes_equal or build_1.artifact_id != candidate.artifact_id:
            reasons.append("product_validation_policy_invalid")
    except DeviceFingerprintValidationError:
        reasons.append("product_validation_policy_invalid")
    if candidate.artifact_id != _INITIAL_ID or candidate.content_sha256 != _INITIAL_SHA256:
        reasons.append("initial_product_validation_policy_identity_mismatch")
    evidence_reasons, manifest_evidence = _retained_evidence_check(retained_evidence_refs)
    reasons.extend(evidence_reasons)
    if not isinstance(decision_record_refs, list) or any(
            not isinstance(ref, str) for ref in decision_record_refs):
        raise DeviceFingerprintValidationError("Invalid decision refs")
    unique_decisions = sorted(set(decision_record_refs))
    if not unique_decisions:
        reasons.append("product_validation_owner_decision_required")
    reasons = sorted(set(reasons))
    status = "FAIL" if reasons else "PASS"
    manifest = make_gate_result_manifest({
        "gate_id": "F-F4", "gate_contract_version": "R14-F-F4-v1", "status": status,
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
            "procedure_or_test_suite_id": "F-F4-product-validation-policy-v1",
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
    return FF4GateExecution(
        candidate.artifact_id, candidate.content_sha256,
        build_1.artifact_id if build_1 else None,
        build_2.artifact_id if build_2 else None,
        bytes_equal, manifest, tuple(reasons),
    )
