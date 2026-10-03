"""A1 policy admission test source; formal execution belongs to TechLead."""

from copy import deepcopy
from inspect import signature

import pytest

from app.device_fingerprint.artifact_content import make_artifact_content
from app.device_fingerprint.classification_policy import build_initial_classification_policy_v1
from app.device_fingerprint.evidence_adapter_contracts import (
    build_utility_repair_a1_evidence_adapter_contract_set_v1, make_evidence_adapter_contract_set,
)
from app.device_fingerprint.ff2_classification_policy import (
    run_ff2_classification_policy_gate, run_ff2_utility_repair_a1_classification_policy_gate,
)
from app.device_fingerprint.foundation_schema_artifacts import build_foundation_schema_artifacts
from app.device_fingerprint.taxonomy_artifacts import make_alias_mapping, make_classification_taxonomy
from tests.device_fingerprint_ff2.test_classification_policy import (
    _BASELINE, _TREE, _DECISIONS, _deps, _evidence,
)


def _a1_deps():
    deps = _deps()
    deps["evidence_adapter_contract_set"] = build_utility_repair_a1_evidence_adapter_contract_set_v1(
        build_foundation_schema_artifacts()["EvidenceSchemaRegistryContract"])
    return deps


def _gate(deps=None, candidate=None, *, historical=False, evidence=None, decisions=None):
    deps = _a1_deps() if deps is None else deps
    candidate = build_initial_classification_policy_v1(**deps) if candidate is None else candidate
    entrypoint = (run_ff2_classification_policy_gate if historical else
                  run_ff2_utility_repair_a1_classification_policy_gate)
    return entrypoint(
        candidate, **deps, candidate_repository_commit_sha=_BASELINE,
        candidate_repository_tree_sha=_TREE, environment_identity="synthetic-a1-ff2",
        retained_evidence_refs=_evidence() if evidence is None else evidence,
        decision_record_refs=_DECISIONS if decisions is None else decisions,
    )


def _assert_fail(result):
    manifest = result.gate_result_manifest.semantic_payload
    assert manifest["status"] == "FAIL"
    assert manifest["output_artifact_refs"] == []
    assert result.failure_reasons


def test_a1_does_not_repurpose_historical_admission():
    assert _gate(_deps(), historical=True).gate_result_manifest.semantic_payload["status"] == "PASS"
    historical = _gate(historical=True)
    _assert_fail(historical)
    assert "initial_adapter_identity_mismatch" in historical.failure_reasons
    _assert_fail(_gate(_deps()))
    assert "a1" not in signature(run_ff2_classification_policy_gate).parameters


def test_a1_accepts_only_reference_rebind_with_original_revision_and_new_procedure():
    result = _gate()
    manifest = result.gate_result_manifest.semantic_payload
    assert manifest["status"] == "PASS", result.failure_reasons
    assert (manifest["gate_id"], manifest["gate_contract_version"]) == ("F-F2", "R14-F-F2-v1")
    assert manifest["proof_execution_identity"]["procedure_or_test_suite_id"] == "F-F2-classification-policy-a1-v1"
    assert result.double_build_bytes_equal and result.permutation_invariant
    assert result.dependency_validation_passed
    assert manifest["decision_record_refs"] == _DECISIONS
    old = build_initial_classification_policy_v1(**_deps()).semantic_payload
    new = build_initial_classification_policy_v1(**_a1_deps()).semantic_payload
    assert [name for name in old if old[name] != new[name]] == ["evidence_adapter_contract_set"]


def test_a1_rejects_other_adapter_delta_even_with_matching_policy_ref():
    deps = _a1_deps()
    payload = deps["evidence_adapter_contract_set"].semantic_payload
    next(row for row in payload["adapter_entries"] if row.get("source_kind") == "tls_client")[
        "base_claim_strength_ceiling"] = "strong"
    deps["evidence_adapter_contract_set"] = make_evidence_adapter_contract_set(payload)
    result = _gate(deps)
    _assert_fail(result)
    assert "a1_adapter_identity_mismatch" in result.failure_reasons


@pytest.mark.parametrize("name", ["classification_taxonomy", "alias_mapping"])
def test_a1_keeps_exact_taxonomy_and_alias_identity(name):
    deps = _a1_deps()
    payload = deps[name].semantic_payload
    if name == "classification_taxonomy":
        payload["manufacturer_records"] = [{"manufacturer_id": "synthetic", "display_label": "Synthetic"}]
        deps[name] = make_classification_taxonomy(payload)
    else:
        payload["source_taxonomy_mappings"].append({
            "source_id": "synthetic", "dimension_name": "platform_family", "source_taxon": "unknown",
            "mapping_kind": "UNMAPPED", "target_id_or_ref": None})
        deps[name] = make_alias_mapping(payload)
    result = _gate(deps)
    _assert_fail(result)
    assert f"a1_{name}_identity_mismatch" in result.failure_reasons


@pytest.mark.parametrize("field", [
    "same_origin_ambiguity_conflict_rules", "same_origin_conflict_strength_rules",
    "cross_origin_fusion_matrix", "support_level_rules", "dimension_result_rules",
    "global_status_derivation", "knowledge_freshness_policy_execution_semantics",
])
def test_a1_rejects_any_policy_semantic_change(field):
    deps = _a1_deps()
    payload = build_initial_classification_policy_v1(**deps).semantic_payload
    if isinstance(payload[field], list):
        key = ({"same_origin_ambiguity_conflict_rules": "compatible_multi_candidate_outcome",
                "same_origin_conflict_strength_rules": "outcome",
                "cross_origin_fusion_matrix": "outcome"}.get(field, "result"))
        payload[field][0][key] = "changed"
    else:
        payload[field]["expired_behavior"] = "ALLOW_NEW_CLAIM"
    _assert_fail(_gate(deps, make_artifact_content("ClassificationPolicy", payload)))


def test_a1_rejects_recognized_out_of_scope_semantic_change():
    deps = _a1_deps()
    payload = build_initial_classification_policy_v1(**deps).semantic_payload
    payload["recognized_out_of_scope_applicability"].append("manufacturer_family")
    _assert_fail(_gate(deps, make_artifact_content("ClassificationPolicy", payload)))


@pytest.mark.parametrize("evidence,decisions,reason", [
    ([], _DECISIONS, "retained_evidence_required"),
    (_evidence()[:1], _DECISIONS, "classification_policy_review_report_required"),
    (_evidence()[1:], _DECISIONS, "classification_policy_test_vectors_evidence_invalid"),
    (_evidence(), [], "owner_techlead_decisions_required"),
    (_evidence(), [_DECISIONS[0], _DECISIONS[0]], "owner_techlead_decisions_required"),
])
def test_a1_keeps_evidence_and_decision_requirements(evidence, decisions, reason):
    result = _gate(evidence=evidence, decisions=decisions)
    _assert_fail(result)
    assert reason in result.failure_reasons


def test_a1_rejects_wrong_vector_identity_and_duplicate_review():
    evidence = deepcopy(_evidence())
    evidence[0]["file_sha256"] = "a" * 64
    _assert_fail(_gate(evidence=evidence))
    evidence = deepcopy(_evidence())
    evidence.append(deepcopy(evidence[1]))
    _assert_fail(_gate(evidence=evidence))
