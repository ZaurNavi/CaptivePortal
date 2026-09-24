"""F-E7 deterministic bundle, dependency, freshness and formal gate proof."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, fields
from typing import Any

from .artifact_content import ArtifactContent, ArtifactRef, canonical_set
from .fe5_external_knowledge import evaluate_external_knowledge_freshness
from .foundation_gate_artifacts import make_gate_result_manifest
from .knowledge_bundle import (
    KnowledgeBundleCandidate, build_initial_knowledge_bundle_v1,
    make_knowledge_bundle, validate_knowledge_bundle_dependencies,
)
from .models import DeviceFingerprintValidationError
from .validation import parse_utc

@dataclass(frozen=True, slots=True)
class FE7GateExecution:
    knowledge_bundle_artifact_id: str | None
    knowledge_bundle_content_sha256: str | None
    build_1_artifact_id: str | None
    build_1_content_sha256: str | None
    build_2_artifact_id: str | None
    build_2_content_sha256: str | None
    dependency_validation_passed: bool
    per_source: tuple[dict[str, Any], ...]
    gate_result_manifest: ArtifactContent
    failure_reasons: tuple[str, ...]


def _candidate_refs(candidate: KnowledgeBundleCandidate) -> list[dict[str, str]]:
    refs = []
    for field in fields(candidate):
        content = getattr(candidate, field.name)
        if content is None:
            continue
        if not isinstance(content, ArtifactContent):
            raise DeviceFingerprintValidationError("Malformed F-E7 candidate dependency")
        refs.append(ArtifactRef(content.artifact_id, content.content_sha256).as_dict())
    return canonical_set(
        list({ref["artifact_id"]: ref for ref in refs}.values()),
        lambda ref: ref["artifact_id"],
    )


def run_fe7_knowledge_bundle_gate(
    candidate: KnowledgeBundleCandidate,
    *,
    foundation_knowledge_evaluation_at_utc: str,
    candidate_repository_commit_sha: str,
    candidate_repository_tree_sha: str,
    environment_identity: str,
    retained_evidence_refs: list[dict[str, Any]],
    decision_record_refs: list[str],
) -> FE7GateExecution:
    """Use the inherited F-E5 proof time; never observe the current clock."""
    if not isinstance(candidate, KnowledgeBundleCandidate):
        raise DeviceFingerprintValidationError("Invalid F-E7 gate input")
    parse_utc(foundation_knowledge_evaluation_at_utc)
    refs = _candidate_refs(candidate)
    reasons: list[str] = []
    if len(refs) != 16:
        reasons.append("candidate_dependency_refs_not_sixteen_distinct")
    bundle_a = None
    bundle_b = None
    dependencies_valid = False
    try:
        bundle_a = build_initial_knowledge_bundle_v1(candidate)
        bundle_b = build_initial_knowledge_bundle_v1(candidate)
        if not (
            bundle_a.artifact_id == bundle_b.artifact_id
            and bundle_a.content_sha256 == bundle_b.content_sha256
            and bundle_a.semantic_payload_json == bundle_b.semantic_payload_json
        ):
            reasons.append("double_build_identity_mismatch")
        permuted = bundle_a.semantic_payload
        for key in ("knowledge_provenance_manifests", "source_governance_records",
                    "knowledge_freshness_policies"):
            permuted[key] = list(reversed(permuted[key]))
        if make_knowledge_bundle(permuted).artifact_id != bundle_a.artifact_id:
            reasons.append("dependency_set_permutation_mismatch")
        validate_knowledge_bundle_dependencies(bundle_a, candidate)
        dependencies_valid = True
    except DeviceFingerprintValidationError:
        reasons.append("bundle_or_dependency_invalid")

    reports = []
    for slot in ("k1", "k2b", "k4"):
        provenance = getattr(candidate, f"{slot}_provenance")
        policy = getattr(candidate, f"{slot}_freshness_policy")
        if provenance is None or policy is None:
            reasons.append(f"{slot}_freshness_dependency_missing")
            continue
        try:
            result = evaluate_external_knowledge_freshness(
                provenance, policy,
                knowledge_evaluation_at_utc=foundation_knowledge_evaluation_at_utc,
            )
        except DeviceFingerprintValidationError:
            reasons.append(f"{slot}_freshness_invalid")
            continue
        report = {"slot": slot, **result}
        reports.append(report)
        if (result["age_ms"] < 0 or result["failure_code"] is not None
                or not result["claim_eligible"] or result["freshness_state"] == "expired"):
            reasons.append(f"{slot}_knowledge_not_usable")
    per_source = tuple(reports)
    if not retained_evidence_refs:
        reasons.append("retained_evidence_required")
    if not decision_record_refs:
        reasons.append("owner_decision_required")
    if bundle_a is None:
        reasons.append("knowledge_bundle_unavailable")
    status = "FAIL" if reasons else "PASS"
    manifest = make_gate_result_manifest({
        "gate_id": "F-E7", "gate_contract_version": "R14-F-E7-v1",
        "status": status,
        "candidate_repository_commit_sha": candidate_repository_commit_sha,
        "candidate_repository_tree_sha": candidate_repository_tree_sha,
        "input_artifact_refs": refs,
        "output_artifact_refs": [ArtifactRef(bundle_a.artifact_id, bundle_a.content_sha256).as_dict()]
            if status == "PASS" else [],
        "retained_evidence_refs": retained_evidence_refs,
        "proof_execution_identity": {
            "execution_id": str(uuid.uuid4()), "executor_kind": "TECHLEAD_GATE_TOOL",
            "repository_commit_sha": candidate_repository_commit_sha,
            "repository_tree_sha": candidate_repository_tree_sha,
            "procedure_or_test_suite_id": "F-E7-knowledge-bundle-v1",
            "environment_identity": environment_identity,
            "execution_artifact_sha256": None,
        },
        "trusted_time_inputs": {
            "foundation_knowledge_evaluation_at_utc": foundation_knowledge_evaluation_at_utc,
            "foundation_admission_evaluation_at_utc": None,
            "knowledge_evaluation_at_utc": None,
        },
        "decision_record_refs": decision_record_refs,
    })
    return FE7GateExecution(
        bundle_a.artifact_id if bundle_a is not None else None,
        bundle_a.content_sha256 if bundle_a is not None else None,
        bundle_a.artifact_id if bundle_a is not None else None,
        bundle_a.content_sha256 if bundle_a is not None else None,
        bundle_b.artifact_id if bundle_b is not None else None,
        bundle_b.content_sha256 if bundle_b is not None else None,
        dependencies_valid, per_source, manifest, tuple(reasons),
    )
