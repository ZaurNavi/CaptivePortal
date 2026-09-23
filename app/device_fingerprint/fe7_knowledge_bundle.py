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

_INITIAL_TIME = "2026-09-22T22:30:34.464Z"
_INITIAL_IDS = {
    "classification_taxonomy": "ClassificationTaxonomy:v1:sha256:399e2a337e7ebecb1bd7a9b21dff5e744c13be36313bc39f16832bc7a57a4d10",
    "alias_mapping": "AliasMapping:v1:sha256:f1cdd7c9510c2a33bad99bd1ae15eaccd20fcb828a52e02533b9917fdfc2e228",
    "k3_portal_rule_set": "K3PortalRuleSet:v1:sha256:5e47945da04c60baf8dc1d1a7777a4e2efa2dfa0e80bf7639a97ba51d6fdb28f",
    "k3_provenance": "KnowledgeProvenanceManifest:v1:sha256:99029f81d6ca8c2afc6d48640ac4c1f47f01c78baa2836d68dcec5d0adc28b92",
}
_INITIAL_EXTERNAL = {
    "k1": ("4f64a405fb1debbd2e066478a7190b821424e0691399068421fdaf168da09b14",
           "2026-09-19T21:00:50.036Z", 903, "fresh"),
    "k2b": ("791444ebf9a97a492b7a94020f721d016584918c437a450ccaa5525a55c95ad0",
            "2026-09-22T22:16:00.456Z", 43, "stale"),
    "k4": ("eb81bb97240fb7754659c33c13a9139583f7f505e38bc6618f9eef51b3878ae5",
           "2026-09-22T20:43:37.766Z", 54012, "fresh"),
}


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


def _initial_anchor_reasons(
    candidate: KnowledgeBundleCandidate, evaluation_time: str,
    per_source: tuple[dict[str, Any], ...],
) -> list[str]:
    reasons = []
    if evaluation_time != _INITIAL_TIME:
        reasons.append("initial_f_e5_trusted_time_mismatch")
    for name, expected_id in _INITIAL_IDS.items():
        content = getattr(candidate, name)
        if content is None or content.artifact_id != expected_id:
            reasons.append(f"initial_{name}_identity_mismatch")
    for slot, (digest, retrieved, count, state) in _INITIAL_EXTERNAL.items():
        provenance = getattr(candidate, f"{slot}_provenance")
        record_set = getattr(candidate, f"{slot}_record_set")
        if provenance is None or record_set is None:
            reasons.append(f"initial_{slot}_dependency_missing")
            continue
        source = provenance.semantic_payload
        records = record_set.semantic_payload.get("records")
        if (source.get("source_artifact_sha256") != digest
                or source.get("retrieved_at_utc") != retrieved
                or not isinstance(records, list) or len(records) != count):
            reasons.append(f"initial_{slot}_source_or_count_mismatch")
        report = next((row for row in per_source if row["slot"] == slot), None)
        if (report is None or report["freshness_state"] != state
                or not report["claim_eligible"]
                or (slot == "k2b" and report["claim_strength_cap"] != "supporting")):
            reasons.append(f"initial_{slot}_freshness_mismatch")
    rule_set = candidate.k3_portal_rule_set
    k3 = rule_set.semantic_payload if rule_set is not None else {}
    rules, vectors = k3.get("rules"), k3.get("test_vectors")
    if (not isinstance(rules, list) or not isinstance(vectors, list)
            or (len(rules), len(vectors)) != (13, 21)):
        reasons.append("initial_k3_concrete_count_mismatch")
    return reasons


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
    reasons.extend(_initial_anchor_reasons(candidate, foundation_knowledge_evaluation_at_utc,
                                           per_source))
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
