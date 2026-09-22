"""R14 F-E5 external knowledge policies, provenance and admission gate."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .artifact_content import ArtifactContent, ArtifactRef
from .foundation_gate_artifacts import make_gate_result_manifest
from .k1_satori_import import SATORI_SOURCE_SHA256
from .k2a_conformance_artifacts import make_source_governance_record
from .k2b_p0f_import import verify_p0f_source_bytes
from .k4_ieee_import import compute_ieee_k4_source_bundle_sha256
from .knowledge_artifacts import (
    make_external_knowledge_provenance_manifest, make_knowledge_freshness_policy,
)
from .models import DeviceFingerprintValidationError
from .validation import format_utc, parse_utc

_FAMILIES = {
    "satori_dhcp": (
        "K1", "current",
        "direct admitted DHCP taxonomy mappings only; supporting authority; ambiguity preserved",
        31536000000, 63072000000,
    ),
    "p0f3_legacy_tcp": (
        "K2B", "legacy",
        "platform_family only; supporting authority; legacy source; other dimensions NO_CLAIM",
        0, 9223372036854775807,
    ),
    "ieee_ra_mac": (
        "K4", "current",
        "raw mac_assignment_org only; manufacturer_mapping remains null unless separately reviewed",
        172800000, 604800000,
    ),
}
_SOURCE_METADATA = {
    "satori_dhcp": "xnih/satori@c5dfcfbff31620e35248aa86da0c67f2ad4982f5:fingerprints/dhcp.xml",
    "p0f3_legacy_tcp": (
        "peace-maker/p0f3-database@7687e779c42c256c1f36b8c48da7e1f8fe24c2d4:"
        "p0f.fp;source_character=legacy"
    ),
}
_IMPORTERS = {
    "satori_dhcp": "captivportal.k1_satori_import",
    "p0f3_legacy_tcp": "captivportal.k2b_p0f_import",
    "ieee_ra_mac": "captivportal.k4_ieee_import",
}


def _fail(message: str) -> None:
    raise DeviceFingerprintValidationError(message)


def _rules() -> list[dict[str, Any]]:
    return [
        {"freshness_state": "fresh", "claim_eligible": True,
         "claim_strength_cap": "NO_ADDITIONAL_CAP", "required_explanation_code": None,
         "dimension_overrides": []},
        {"freshness_state": "stale", "claim_eligible": True,
         "claim_strength_cap": "supporting", "required_explanation_code": "knowledge_source_stale",
         "dimension_overrides": []},
        {"freshness_state": "expired", "claim_eligible": False,
         "claim_strength_cap": "NONE", "required_explanation_code": "knowledge_source_expired",
         "dimension_overrides": []},
    ]


def _policy(family: str) -> ArtifactContent:
    _slot, _character, _caveat, fresh, stale = _FAMILIES[family]
    return make_knowledge_freshness_policy({
        "knowledge_freshness_policy_version": 1,
        "source_family_id": family,
        "fresh_max_age_ms": fresh,
        "stale_max_age_ms": stale,
        "freshness_state_rules": _rules(),
    })


def build_satori_k1_freshness_policy() -> ArtifactContent:
    return _policy("satori_dhcp")


def build_p0f_k2b_freshness_policy() -> ArtifactContent:
    return _policy("p0f3_legacy_tcp")


def build_ieee_k4_freshness_policy() -> ArtifactContent:
    return _policy("ieee_ra_mac")


def _ref(content: ArtifactContent, expected_type: str) -> dict[str, str]:
    if not isinstance(content, ArtifactContent):
        _fail(f"Missing {expected_type} artifact")
    reference = ArtifactRef(content.artifact_id, content.content_sha256)
    reference.resolve(content, expected_type)
    return reference.as_dict()


def _external_provenance(
    family: str, source_sha256: str, *, retrieved_at_utc: str,
    governance: ArtifactContent, freshness_policy: ArtifactContent,
) -> ArtifactContent:
    governance_ref = _ref(governance, "SourceGovernanceRecord")
    freshness_ref = _ref(freshness_policy, "KnowledgeFreshnessPolicy")
    metadata = _SOURCE_METADATA.get(
        family, f"IEEE-RA-MA-L-MA-M-MA-S:bundle-sha256={source_sha256}",
    )
    return make_external_knowledge_provenance_manifest({
        "provenance_contract_version": 1,
        "provenance_kind": "external",
        "source_artifact_sha256": source_sha256,
        "source_governance_record": governance_ref,
        "retrieved_at_utc": retrieved_at_utc,
        "source_provider_version_metadata": metadata,
        "knowledge_freshness_policy": freshness_ref,
        "importer_identity": _IMPORTERS[family],
        "importer_version": "1",
    })


def build_satori_k1_external_provenance(
    source_bytes: bytes, *, retrieved_at_utc: str,
    governance: ArtifactContent, freshness_policy: ArtifactContent,
) -> ArtifactContent:
    if not isinstance(source_bytes, bytes) or hashlib.sha256(source_bytes).hexdigest() != SATORI_SOURCE_SHA256:
        _fail("Pinned Satori source SHA256 mismatch")
    return _external_provenance(
        "satori_dhcp", SATORI_SOURCE_SHA256, retrieved_at_utc=retrieved_at_utc,
        governance=governance, freshness_policy=freshness_policy,
    )


def build_p0f_k2b_external_provenance(
    source_bytes: bytes, *, retrieved_at_utc: str,
    governance: ArtifactContent, freshness_policy: ArtifactContent,
) -> ArtifactContent:
    digest = verify_p0f_source_bytes(source_bytes)
    return _external_provenance(
        "p0f3_legacy_tcp", digest, retrieved_at_utc=retrieved_at_utc,
        governance=governance, freshness_policy=freshness_policy,
    )


def build_ieee_k4_external_provenance(
    ma_l_bytes: bytes, ma_m_bytes: bytes, ma_s_bytes: bytes, *,
    retrieved_at_utc: str, governance: ArtifactContent,
    freshness_policy: ArtifactContent,
) -> ArtifactContent:
    digest = compute_ieee_k4_source_bundle_sha256(ma_l_bytes, ma_m_bytes, ma_s_bytes)
    return _external_provenance(
        "ieee_ra_mac", digest, retrieved_at_utc=retrieved_at_utc,
        governance=governance, freshness_policy=freshness_policy,
    )


@dataclass(frozen=True, slots=True)
class ExternalKnowledgeCandidate:
    knowledge_slot: str
    source_family_id: str
    source_character: str
    claim_caveat: str
    governance: ArtifactContent
    freshness_policy: ArtifactContent
    provenance: ArtifactContent


@dataclass(frozen=True, slots=True)
class FE5GateExecution:
    foundation_knowledge_evaluation_at_utc: str
    per_source: tuple[dict[str, Any], ...]
    gate_result_manifest: ArtifactContent
    failure_reasons: tuple[str, ...]


def _milliseconds(value: datetime) -> int:
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = value - epoch
    return delta.days * 86400000 + delta.seconds * 1000 + delta.microseconds // 1000


def evaluate_external_knowledge_freshness(
    provenance: ArtifactContent, freshness_policy: ArtifactContent, *,
    knowledge_evaluation_at_utc: str,
    dimension_name: str | None = None,
) -> dict[str, Any]:
    """Evaluate exact integer-ms age and generic dimension override semantics."""
    _ref(provenance, "KnowledgeProvenanceManifest")
    _ref(freshness_policy, "KnowledgeFreshnessPolicy")
    source = make_external_knowledge_provenance_manifest(provenance.semantic_payload)
    policy = make_knowledge_freshness_policy(freshness_policy.semantic_payload)
    if source.artifact_id != provenance.artifact_id or policy.artifact_id != freshness_policy.artifact_id:
        _fail("Noncanonical external knowledge artifact")
    if source.semantic_payload["knowledge_freshness_policy"] != _ref(policy, "KnowledgeFreshnessPolicy"):
        _fail("External provenance freshness reference mismatch")
    age = _milliseconds(parse_utc(knowledge_evaluation_at_utc)) - _milliseconds(
        parse_utc(source.semantic_payload["retrieved_at_utc"])
    )
    if age < 0:
        return {
            "age_ms": age, "freshness_state": None,
            "claim_eligible": False, "claim_strength_cap": "NONE",
            "required_explanation_code": "negative_knowledge_age",
            "failure_code": "negative_knowledge_age",
        }
    p = policy.semantic_payload
    state = ("fresh" if age <= p["fresh_max_age_ms"] else
             "stale" if age <= p["stale_max_age_ms"] else "expired")
    rule = next(row for row in p["freshness_state_rules"] if row["freshness_state"] == state)
    selected = rule
    if dimension_name is not None:
        if dimension_name not in {
            "platform_family", "device_class", "manufacturer_family", "model_family",
        }:
            _fail("Invalid dimension override request")
        selected = next((row for row in rule["dimension_overrides"]
                         if row["dimension_name"] == dimension_name), rule)
    return {
        "age_ms": age, "freshness_state": state,
        "claim_eligible": selected["claim_eligible"],
        "claim_strength_cap": selected["claim_strength_cap"],
        "required_explanation_code": selected["required_explanation_code"],
        "failure_code": None,
    }


def _trusted_utc_now() -> str:
    return format_utc(datetime.now(timezone.utc))


def _candidate_refs(candidates: tuple[ExternalKnowledgeCandidate | None, ...]) -> list[dict[str, str]]:
    refs: dict[str, dict[str, str]] = {}
    for candidate in candidates:
        if candidate is None:
            continue
        if not isinstance(candidate, ExternalKnowledgeCandidate):
            _fail("Invalid F-E5 candidate")
        for artifact, kind in (
            (candidate.governance, "SourceGovernanceRecord"),
            (candidate.freshness_policy, "KnowledgeFreshnessPolicy"),
            (candidate.provenance, "KnowledgeProvenanceManifest"),
        ):
            reference = _ref(artifact, kind)
            refs[reference["artifact_id"]] = reference
    return list(refs.values())


def run_fe5_external_admission_gate(
    k1_candidate: ExternalKnowledgeCandidate | None,
    k2b_candidate: ExternalKnowledgeCandidate | None,
    k4_candidate: ExternalKnowledgeCandidate | None,
    *, candidate_repository_commit_sha: str,
    candidate_repository_tree_sha: str,
    environment_identity: str,
    retained_evidence_refs: list[dict[str, Any]],
    decision_record_refs: list[str],
) -> FE5GateExecution:
    """Capture one trusted clock and emit machine-identifiable PASS or FAIL."""
    captured = _trusted_utc_now()
    parse_utc(captured)
    candidates = (k1_candidate, k2b_candidate, k4_candidate)
    input_refs = _candidate_refs(candidates)
    reasons: list[str] = []
    reports: list[dict[str, Any]] = []
    if len(input_refs) != 9:
        reasons.append("candidate_artifact_refs_not_nine_distinct")
    families = [candidate.source_family_id for candidate in candidates if candidate is not None]
    if len(families) != 3 or set(families) != set(_FAMILIES) or len(set(families)) != 3:
        reasons.append("mandatory_external_source_set_mismatch")
    for candidate in candidates:
        if candidate is None:
            continue
        family = candidate.source_family_id
        if family not in _FAMILIES:
            reasons.append("unexpected_external_source_family")
            continue
        slot, character, caveat, _fresh, _stale = _FAMILIES[family]
        if (candidate.knowledge_slot != slot or candidate.source_character != character
                or candidate.claim_caveat != caveat):
            reasons.append(f"{family}:source_contract_mismatch")
        governance = candidate.governance.semantic_payload
        policy = candidate.freshness_policy.semantic_payload
        provenance = candidate.provenance.semantic_payload
        try:
            make_source_governance_record(governance)
            make_knowledge_freshness_policy(policy)
            make_external_knowledge_provenance_manifest(provenance)
        except DeviceFingerprintValidationError:
            reasons.append(f"{family}:invalid_source_artifact")
            continue
        if provenance["provenance_kind"] != "external":
            reasons.append(f"{family}:non_external_provenance")
            continue
        if (provenance["source_governance_record"] != _ref(candidate.governance, "SourceGovernanceRecord")
                or provenance["knowledge_freshness_policy"] != _ref(candidate.freshness_policy, "KnowledgeFreshnessPolicy")):
            reasons.append(f"{family}:provenance_reference_mismatch")
            continue
        if policy["source_family_id"] != family or candidate.freshness_policy.artifact_id != _policy(family).artifact_id:
            reasons.append(f"{family}:freshness_policy_mismatch")
            continue
        expected_metadata = _SOURCE_METADATA.get(
            family,
            f"IEEE-RA-MA-L-MA-M-MA-S:bundle-sha256={provenance['source_artifact_sha256']}",
        )
        if (provenance["source_provider_version_metadata"] != expected_metadata
                or provenance["importer_identity"] != _IMPORTERS[family]
                or provenance["importer_version"] != "1"
                or (family == "satori_dhcp" and provenance["source_artifact_sha256"] != SATORI_SOURCE_SHA256)):
            reasons.append(f"{family}:source_provenance_mismatch")
            continue
        if (governance["unresolved_restrictions"]
                or governance["modification_import_status"] == "NOT_ADMITTED"
                or any(value == "UNKNOWN_NOT_ADMITTED" for value in governance.values())):
            reasons.append(f"{family}:governance_not_admitted")
        freshness = evaluate_external_knowledge_freshness(
            candidate.provenance, candidate.freshness_policy,
            knowledge_evaluation_at_utc=captured,
        )
        if freshness["failure_code"] is not None:
            reasons.append(f"{family}:{freshness['failure_code']}")
        elif not freshness["claim_eligible"]:
            reasons.append(f"{family}:knowledge_expired_or_ineligible")
        reports.append({
            "source_family_id": family, "source_character": candidate.source_character,
            "source_artifact_sha256": provenance["source_artifact_sha256"],
            "retrieved_at_utc": provenance["retrieved_at_utc"],
            **freshness,
            "governance_artifact_ref": _ref(candidate.governance, "SourceGovernanceRecord"),
            "freshness_artifact_ref": _ref(candidate.freshness_policy, "KnowledgeFreshnessPolicy"),
            "provenance_artifact_ref": _ref(candidate.provenance, "KnowledgeProvenanceManifest"),
        })
    if not retained_evidence_refs:
        reasons.append("retained_evidence_required")
    if not decision_record_refs:
        reasons.append("owner_decision_required")
    status = "FAIL" if reasons else "PASS"
    manifest = make_gate_result_manifest({
        "gate_id": "F-E5", "gate_contract_version": "R14-F-E5-v1",
        "status": status,
        "candidate_repository_commit_sha": candidate_repository_commit_sha,
        "candidate_repository_tree_sha": candidate_repository_tree_sha,
        "input_artifact_refs": input_refs,
        "output_artifact_refs": input_refs if status == "PASS" else [],
        "retained_evidence_refs": retained_evidence_refs,
        "proof_execution_identity": {
            "execution_id": str(uuid.uuid4()), "executor_kind": "TECHLEAD_GATE_TOOL",
            "repository_commit_sha": candidate_repository_commit_sha,
            "repository_tree_sha": candidate_repository_tree_sha,
            "procedure_or_test_suite_id": "F-E5-external-freshness-governance-v1",
            "environment_identity": environment_identity,
            "execution_artifact_sha256": None,
        },
        "trusted_time_inputs": {
            "foundation_knowledge_evaluation_at_utc": captured,
            "foundation_admission_evaluation_at_utc": None,
            "knowledge_evaluation_at_utc": None,
        },
        "decision_record_refs": decision_record_refs,
    })
    return FE5GateExecution(captured, tuple(reports), manifest, tuple(reasons))
