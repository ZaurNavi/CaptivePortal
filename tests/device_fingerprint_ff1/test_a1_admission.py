"""Synthetic A1 admission tests prepared for TechLead; no real source data."""

from copy import deepcopy
from inspect import signature

import pytest

from app.device_fingerprint.artifact_content import make_artifact_content
from app.device_fingerprint.evidence_adapter_contracts import (
    build_initial_evidence_adapter_contract_set_v1,
    build_utility_repair_a1_evidence_adapter_contract_set_v1,
    make_evidence_adapter_contract_set,
)
from app.device_fingerprint.ff1_evidence_adapter_contracts import (
    run_ff1_evidence_adapter_contract_gate,
    run_ff1_utility_repair_a1_evidence_adapter_contract_gate,
)
from app.device_fingerprint.k3_portal_rules import build_k3_portal_rule_set_v1, make_k3_portal_rule_set
from app.device_fingerprint.knowledge_artifacts import make_canonical_k1_record_set
from app.device_fingerprint.models import DeviceFingerprintValidationError
from tests.device_fingerprint_ff1.test_evidence_adapter_contracts import (
    _COMMIT, _TREE, _EVIDENCE, _refs,
)


def _a1_inputs():
    deps = _refs()
    deps["k3_portal_rule_set"] = build_k3_portal_rule_set_v1()
    k1 = deps["k1_record_set"].semantic_payload
    for record in k1["records"]:
        for outcome in record["candidate_taxonomy_refs"]:
            if outcome["dimension_name"] == "device_class":
                outcome["base_claim_strength"] = "strong"
    deps["k1_record_set"] = make_canonical_k1_record_set(k1)
    return deps


def _gate(deps=None, candidate=None, *, historical=False, evidence=None):
    deps = _a1_inputs() if deps is None else deps
    if candidate is None:
        candidate = build_utility_repair_a1_evidence_adapter_contract_set_v1(
            deps["evidence_schema_registry"])
    entrypoint = (run_ff1_evidence_adapter_contract_gate if historical else
                  run_ff1_utility_repair_a1_evidence_adapter_contract_gate)
    return entrypoint(
        candidate, **deps, candidate_repository_commit_sha=_COMMIT,
        candidate_repository_tree_sha=_TREE, environment_identity="synthetic-a1-ff1",
        retained_evidence_refs=_EVIDENCE if evidence is None else evidence,
    )


def _assert_fail(result):
    payload = result.gate_result_manifest.semantic_payload
    assert payload["status"] == "FAIL"
    assert payload["output_artifact_refs"] == []
    assert result.failure_reasons


def test_historical_and_a1_entrypoints_are_distinct_without_bypass_flag():
    deps = _refs()
    historical = build_initial_evidence_adapter_contract_set_v1(deps["evidence_schema_registry"])
    assert _gate(deps, historical, historical=True).gate_result_manifest.semantic_payload["status"] == "PASS"
    _assert_fail(_gate(historical=True))
    _assert_fail(_gate(deps, historical))
    assert "a1" not in signature(run_ff1_evidence_adapter_contract_gate).parameters


def test_a1_accepts_exact_matrix_with_original_gate_revision_and_distinct_procedure():
    result = _gate()
    payload = result.gate_result_manifest.semantic_payload
    assert payload["status"] == "PASS", result.failure_reasons
    assert (payload["gate_id"], payload["gate_contract_version"]) == ("F-F1", "R14-F-F1-v1")
    assert payload["proof_execution_identity"]["procedure_or_test_suite_id"] == (
        "F-F1-evidence-adapter-contract-set-a1-v1")
    assert result.double_build_bytes_equal and result.permutation_invariant
    assert result.dependency_validation_passed
    assert len(payload["input_artifact_refs"]) == 6
    assert len(payload["output_artifact_refs"]) == 1


@pytest.mark.parametrize("source,version,field,value", [
    ("tcp_syn", 2, "base_claim_strength_ceiling", "strong"),
    ("tls_client", 1, "base_claim_strength_ceiling", "strong"),
    ("quic_client", 1, "base_claim_strength_ceiling", "strong"),
    ("dhcp", 1, "semantic_projection_id", "arbitrary-projection"),
    ("portal_headers", 1, "base_claim_strength_ceiling", "supporting"),
    ("portal_headers", 2, "supported_source_subtypes", ["future"]),
])
def test_a1_rejects_any_non_a1_matrix_delta(source, version, field, value):
    deps = _a1_inputs()
    payload = build_utility_repair_a1_evidence_adapter_contract_set_v1(
        deps["evidence_schema_registry"]).semantic_payload
    entry = next(row for row in payload["adapter_entries"]
                 if row.get("source_kind") == source and row.get("feature_schema_version") == version)
    entry[field] = value
    result = _gate(deps, make_evidence_adapter_contract_set(payload))
    _assert_fail(result)
    assert "a1_matrix_mismatch" in result.failure_reasons


def test_a1_rejects_extra_mac_ceiling():
    deps = _a1_inputs()
    payload = build_utility_repair_a1_evidence_adapter_contract_set_v1(
        deps["evidence_schema_registry"]).semantic_payload
    next(row for row in payload["adapter_entries"] if row["adapter_kind"] == "MAC_REGISTRY")[
        "base_claim_strength_ceiling"] = "strong"
    _assert_fail(_gate(deps, make_evidence_adapter_contract_set(payload)))


@pytest.mark.parametrize("rule_id", [
    "k3.portal.platform.android.user_agent.v1",
    "k3.portal.device_class.tablet.sec_ch_ua_form_factors.v1",
])
def test_a1_rejects_strong_k3_outside_explicit_platform(rule_id):
    deps = _a1_inputs()
    payload = deps["k3_portal_rule_set"].semantic_payload
    next(rule for rule in payload["rules"] if rule["rule_id"] == rule_id)["base_claim_strength"] = "strong"
    deps["k3_portal_rule_set"] = make_artifact_content("K3PortalRuleSet", payload)
    _assert_fail(_gate(deps))


def test_a1_requires_exact_rules_and_vectors_even_if_generic_k3_validates():
    deps = _a1_inputs()
    payload = deps["k3_portal_rule_set"].semantic_payload
    payload["test_vectors"].pop()
    deps["k3_portal_rule_set"] = make_k3_portal_rule_set(payload)
    result = _gate(deps)
    _assert_fail(result)
    assert "a1_k3_contract_mismatch" in result.failure_reasons


@pytest.mark.parametrize("dimension", ["platform_family", "manufacturer_family", "model_family"])
def test_a1_rejects_k1_strong_outside_canonical_device_class(dimension):
    deps = _a1_inputs()
    payload = deps["k1_record_set"].semantic_payload
    outcome = next(row for row in payload["records"][0]["candidate_taxonomy_refs"]
                   if row["dimension_name"] == dimension)
    outcome.update(outcome_kind="CANONICAL_VALUE", canonical_target_id="synthetic",
                   base_claim_strength="strong")
    deps["k1_record_set"] = make_canonical_k1_record_set(payload)
    _assert_fail(_gate(deps))


def test_a1_rejects_unadmitted_strong_class_target():
    deps = _a1_inputs()
    payload = deps["k1_record_set"].semantic_payload
    next(row for row in payload["records"][0]["candidate_taxonomy_refs"]
         if row["dimension_name"] == "device_class")["canonical_target_id"] = "printer"
    deps["k1_record_set"] = make_canonical_k1_record_set(payload)
    _assert_fail(_gate(deps))


def test_a1_rejects_supporting_only_k1_with_exact_a1_eacs_and_k3():
    deps = _a1_inputs()
    payload = deps["k1_record_set"].semantic_payload
    for record in payload["records"]:
        for outcome in record["candidate_taxonomy_refs"]:
            if outcome["dimension_name"] == "device_class":
                outcome["base_claim_strength"] = "supporting"
    deps["k1_record_set"] = make_canonical_k1_record_set(payload)
    result = _gate(deps)
    _assert_fail(result)
    assert "a1_k1_contract_mismatch" in result.failure_reasons
    assert "a1_k1_strong_smartphone_required" in result.failure_reasons


def test_a1_accepts_all_reviewed_strong_classes_without_selecting_one():
    deps = _a1_inputs()
    payload = deps["k1_record_set"].semantic_payload
    for target in ("tablet", "laptop"):
        record = deepcopy(payload["records"][0])
        record.update(canonical_record_id="synthetic-" + target,
                      source_record_identity="synthetic-source-" + target)
        next(row for row in record["candidate_taxonomy_refs"]
             if row["dimension_name"] == "device_class")["canonical_target_id"] = target
        payload["records"].append(record)
    deps["k1_record_set"] = make_canonical_k1_record_set(payload)
    before = deps["k1_record_set"].semantic_payload_json
    assert _gate(deps).gate_result_manifest.semantic_payload["status"] == "PASS"
    assert deps["k1_record_set"].semantic_payload_json == before
    assert len(deps["k1_record_set"].semantic_payload["records"]) == 3


@pytest.mark.parametrize("target", ["tablet", "laptop"])
def test_a1_requires_strong_smartphone_not_just_other_strong_class(target):
    deps = _a1_inputs()
    payload = deps["k1_record_set"].semantic_payload
    for record in payload["records"]:
        next(row for row in record["candidate_taxonomy_refs"]
             if row["dimension_name"] == "device_class")["canonical_target_id"] = target
    deps["k1_record_set"] = make_canonical_k1_record_set(payload)
    result = _gate(deps)
    _assert_fail(result)
    assert "a1_k1_strong_smartphone_required" in result.failure_reasons


@pytest.mark.parametrize("target", ["smartphone", "tablet", "laptop"])
def test_a1_every_direct_canonical_class_must_be_strong(target):
    deps = _a1_inputs()
    payload = deps["k1_record_set"].semantic_payload
    supporting = deepcopy(payload["records"][0])
    supporting.update(canonical_record_id="synthetic-supporting-class",
                      source_record_identity="synthetic-supporting-source")
    outcome = next(row for row in supporting["candidate_taxonomy_refs"]
                   if row["dimension_name"] == "device_class")
    outcome.update(canonical_target_id=target, base_claim_strength="supporting")
    payload["records"].append(supporting)
    deps["k1_record_set"] = make_canonical_k1_record_set(payload)
    result = _gate(deps)
    _assert_fail(result)
    assert "a1_k1_contract_mismatch" in result.failure_reasons


@pytest.mark.parametrize("kind", ["UNMAPPED", "NO_CLAIM"])
def test_a1_non_direct_device_class_remains_valid_without_promotion(kind):
    deps = _a1_inputs()
    payload = deps["k1_record_set"].semantic_payload
    other = deepcopy(payload["records"][0])
    other.update(canonical_record_id="synthetic-no-direct-class",
                 source_record_identity="synthetic-no-direct-source")
    outcome = next(row for row in other["candidate_taxonomy_refs"]
                   if row["dimension_name"] == "device_class")
    outcome.update(outcome_kind=kind, canonical_target_id=None, base_claim_strength=None)
    payload["records"].append(other)
    deps["k1_record_set"] = make_canonical_k1_record_set(payload)
    assert _gate(deps).gate_result_manifest.semantic_payload["status"] == "PASS"
    # An UNMAPPED/NO_CLAIM claim promoted to strong is itself schema-invalid.
    outcome["base_claim_strength"] = "strong"
    with pytest.raises(DeviceFingerprintValidationError):
        make_canonical_k1_record_set(payload)


@pytest.mark.parametrize("name", ["evidence_schema_registry", "capability_disposition", "k2a_conformance_package"])
def test_a1_keeps_unchanged_prerequisite_identities(name):
    deps = _a1_inputs()
    payload = deps[name].semantic_payload
    payload["synthetic_identity_drift"] = True
    deps[name] = make_artifact_content(deps[name].artifact_type, payload)
    _assert_fail(_gate(deps))


def test_a1_retained_evidence_required():
    result = _gate(evidence=[])
    _assert_fail(result)
    assert "retained_evidence_required" in result.failure_reasons


def test_a1_does_not_collapse_ambiguous_k1_records():
    deps = _a1_inputs()
    payload = deps["k1_record_set"].semantic_payload
    competing = deepcopy(payload["records"][0])
    competing.update(canonical_record_id="synthetic-other-class", source_record_identity="synthetic-other-source")
    next(row for row in competing["candidate_taxonomy_refs"] if row["dimension_name"] == "device_class")[
        "canonical_target_id"] = "tablet"
    payload["records"].append(competing)
    deps["k1_record_set"] = make_canonical_k1_record_set(payload)
    before = deps["k1_record_set"].semantic_payload_json
    assert _gate(deps).gate_result_manifest.semantic_payload["status"] == "PASS"
    assert deps["k1_record_set"].semantic_payload_json == before
    assert len(deps["k1_record_set"].semantic_payload["records"]) == 2
