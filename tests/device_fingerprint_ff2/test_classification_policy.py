"""Frozen F-F2 policy, independent retained vectors, and synthetic gate mechanics."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from inspect import signature
from itertools import product
from pathlib import Path

import pytest

from app.device_fingerprint.artifact_content import (
    ArtifactRef, canonical_artifact_json, make_artifact_content,
)
from app.device_fingerprint.classification_policy import (
    _FUSION_INPUTS,
    build_initial_classification_policy_v1, make_classification_policy,
    validate_classification_policy_dependencies,
)
from app.device_fingerprint.evidence_adapter_contracts import (
    build_initial_evidence_adapter_contract_set_v1, make_evidence_adapter_contract_set,
)
from app.device_fingerprint.ff2_classification_policy import run_ff2_classification_policy_gate
from app.device_fingerprint.foundation_schema_artifacts import build_foundation_schema_artifacts
from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.taxonomy_artifacts import (
    build_alias_mapping_v1, build_classification_taxonomy_v1,
    make_alias_mapping, make_classification_taxonomy,
)

_VECTOR = Path(__file__).parent / "fixtures" / "classification_policy_vectors_v1.json"
_BASELINE = "f6615836ff83aba211f9cc5da935c6ff5fbe561c"
_TREE = "948dea0ec66f753394c0949daebc7a62f6a8d961"
_DECISIONS = ["00000000-0000-4000-8000-000000000001",
              "00000000-0000-4000-8000-000000000002"]
_UNSET = object()


def _deps():
    registry = build_foundation_schema_artifacts()["EvidenceSchemaRegistryContract"]
    return {
        "classification_taxonomy": build_classification_taxonomy_v1(),
        "alias_mapping": build_alias_mapping_v1(),
        "evidence_adapter_contract_set": build_initial_evidence_adapter_contract_set_v1(registry),
    }


def _candidate(**deps):
    return build_initial_classification_policy_v1(**(deps or _deps()))


def _vectors():
    return json.loads(_VECTOR.read_bytes())


def _evidence():
    return [
        {"evidence_label": "classification_policy_test_vectors",
         "file_sha256": hashlib.sha256(_VECTOR.read_bytes()).hexdigest(),
         "media_type": "application/json", "path_or_reference": "test://ff2-vectors"},
        {"evidence_label": "classification_policy_review_report",
         "file_sha256": "d" * 64, "media_type": "text/plain",
         "path_or_reference": "test://synthetic-review-fixture"},
    ]


def _gate(candidate=None, *, deps=None, evidence=_UNSET, decisions=None):
    dependencies = deps or _deps()
    return run_ff2_classification_policy_gate(
        candidate or _candidate(**dependencies), **dependencies,
        candidate_repository_commit_sha=_BASELINE,
        candidate_repository_tree_sha=_TREE,
        environment_identity="synthetic-ff2",
        retained_evidence_refs=_evidence() if evidence is _UNSET else evidence,
        decision_record_refs=_DECISIONS if decisions is None else decisions,
    )


def _raw_candidate(payload):
    return make_artifact_content("ClassificationPolicy", payload)


def test_exact_initial_policy_and_dependency_references():
    deps = _deps()
    candidate = _candidate(**deps)
    payload = candidate.semantic_payload
    assert len(payload) == 14
    assert payload["policy_schema_version"] == 1
    for field, content in deps.items():
        assert payload[field] == ArtifactRef(content.artifact_id, content.content_sha256).as_dict()
    assert validate_classification_policy_dependencies(candidate, **deps)
    assert [content.artifact_id for content in deps.values()] == [
        "ClassificationTaxonomy:v1:sha256:399e2a337e7ebecb1bd7a9b21dff5e744c13be36313bc39f16832bc7a57a4d10",
        "AliasMapping:v1:sha256:f1cdd7c9510c2a33bad99bd1ae15eaccd20fcb828a52e02533b9917fdfc2e228",
        "EvidenceAdapterContractSet:v1:sha256:7cca6802ebc5839317643dcb584173b75d985477da687ab0d8fe5802b181f788",
    ]
    assert len(deps["evidence_adapter_contract_set"].semantic_payload["adapter_entries"]) == 8


def test_retained_json_is_canonical_and_independent_expected_policy_vectors():
    raw = _VECTOR.read_bytes()
    spec = _vectors()
    assert raw == canonical_artifact_json(spec) + b"\n"
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert set(spec) == {
        "spec_schema_version", "policy_contract", "same_origin_ambiguity_vectors",
        "same_origin_conflict_vectors", "cross_origin_fusion_vectors",
        "support_level_vectors", "dimension_status_vectors",
        "recognized_out_of_scope_dimensions", "global_status_vectors",
        "freshness_execution_semantics",
    }
    assert (spec["spec_schema_version"], spec["policy_contract"]) == (1, "R14-F-F2-v1")
    counts = (1, 6, 40, 4, 6, 2, 6)
    names = (
        "same_origin_ambiguity_vectors", "same_origin_conflict_vectors",
        "cross_origin_fusion_vectors", "support_level_vectors", "dimension_status_vectors",
        "recognized_out_of_scope_dimensions", "global_status_vectors",
    )
    assert tuple(len(spec[name]) for name in names) == counts
    payload = _candidate().semantic_payload
    mapping = {
        "same_origin_ambiguity_vectors": "same_origin_ambiguity_conflict_rules",
        "same_origin_conflict_vectors": "same_origin_conflict_strength_rules",
        "cross_origin_fusion_vectors": "cross_origin_fusion_matrix",
        "support_level_vectors": "support_level_rules",
        "dimension_status_vectors": "dimension_result_rules",
        "recognized_out_of_scope_dimensions": "recognized_out_of_scope_applicability",
        "global_status_vectors": "global_status_derivation",
        "freshness_execution_semantics": "knowledge_freshness_policy_execution_semantics",
    }
    assert {name: payload[field] for name, field in mapping.items()} == {
        name: spec[name] for name in mapping}


def test_claim_derivation_strength_and_same_origin_rules_are_exact():
    payload = _candidate().semantic_payload
    assert payload["claim_derivation_semantics"] == {
        name: "PROVENANCE_ONLY_NO_AUTHORITY_ORDER" for name in (
            "declared", "deterministic_mapping", "fingerprint_match", "registry_mapping")}
    assert payload["claim_strength_semantics"] == {"supporting": 1, "strong": 2}
    assert payload["same_origin_ambiguity_conflict_rules"] == [{
        "rule": "COMPATIBLE_CANDIDATE_VARIATION", "projection_mode": "PER_DIMENSION",
        "compatible_multi_candidate_outcome": "AMBIGUOUS_NOT_CONFLICT"}]
    rows = payload["same_origin_conflict_strength_rules"]
    assert len(rows) == 6
    assert {(r["left_strength"], r["right_strength"], r["compatibility"]): r["outcome"]
            for r in rows} == {
        ("strong", "strong", "SAME"): "RESOLVED_STRONG",
        ("strong", "strong", "INCOMPATIBLE"): "CONFLICT_STRONG",
        ("strong", "supporting", "SAME"): "RESOLVED_STRONG",
        ("strong", "supporting", "INCOMPATIBLE"):
            "RESOLVED_STRONG_WITH_SUPPORTING_CONTRADICTION",
        ("supporting", "supporting", "SAME"): "RESOLVED_SUPPORTING",
        ("supporting", "supporting", "INCOMPATIBLE"): "CONFLICT_SUPPORTING",
    }


def test_exhaustive_fusion_domain_and_every_frozen_precedence_branch():
    rows = _candidate().semantic_payload["cross_origin_fusion_matrix"]
    indexed = {tuple(row[name] for name in _FUSION_INPUTS): row for row in rows}
    valid = []
    for bits in product((False, True), repeat=7):
        strong, strong_disagree, strong_conflict, supporting, supporting_disagree, _, opposed = bits
        if (strong_disagree and not strong
                or supporting_disagree and not supporting
                or opposed and (not strong or strong_disagree or strong_conflict or not supporting)):
            continue
        valid.append(bits)
    assert (len(valid), 128 - len(valid), len(indexed)) == (40, 88, 40)
    assert set(indexed) == set(valid)
    vector_rows = _vectors()["cross_origin_fusion_vectors"]
    vector_indexed = {tuple(row[name] for name in _FUSION_INPUTS): row for row in vector_rows}
    assert indexed == vector_indexed
    cases = {
        (True, False, True, True, False, False, False): ("CONFLICTING_EVIDENCE", False, "NONE"),
        (True, True, False, True, False, False, False): ("CONFLICTING_EVIDENCE", False, "NONE"),
        (True, False, False, True, False, False, False): ("SELECT_STRONG", False, "NONE"),
        (True, False, False, True, False, False, True): ("SELECT_STRONG", True, "MEDIUM"),
        (True, False, False, False, False, True, False): ("SELECT_STRONG", True, "MEDIUM"),
        (False, False, False, False, False, True, False): ("CONFLICTING_EVIDENCE", False, "NONE"),
        (False, False, False, True, True, False, False): ("CONFLICTING_EVIDENCE", False, "NONE"),
        (False, False, False, True, False, False, False): ("SELECT_SUPPORTING", False, "NONE"),
        (False, False, False, False, False, False, False): ("NO_CONCRETE_SELECTION", False, "NONE"),
    }
    for bits, expected in cases.items():
        row = indexed[bits]
        assert (row["outcome"], row["record_supporting_contradiction"], row["support_cap"]) == expected


def test_support_dimension_global_and_freshness_sequences_are_exact():
    payload = _candidate().semantic_payload
    assert [(r["rule_order"], r["condition"], r["result"])
            for r in payload["support_level_rules"]] == [
        (1, "HIGH_ALL_REQUIREMENTS", "high"),
        (2, "MEDIUM_STRONG_NO_DECISIVE_CONFLICT", "medium"),
        (3, "LOW_SUPPORTING_ONLY_ALL_AGREE", "low"),
        (4, "NONE_UNRESOLVED", "none"),
    ]
    assert [(r["precedence"], r["condition"], r["result"])
            for r in payload["dimension_result_rules"]] == [
        (1, "DECISIVE_CONFLICT", "conflicting_evidence"),
        (2, "SELECTABLE_IN_SCOPE", "resolved"),
        (3, "SELECTABLE_OUT_OF_SCOPE_WHERE_ALLOWED", "recognized_out_of_scope"),
        (4, "SEMANTIC_INFO_UNRESOLVED", "insufficient_evidence"),
        (5, "SUPPORTED_EVIDENCE_NO_USABLE_SEMANTIC_KNOWLEDGE", "unknown"),
        (6, "NO_ADEQUATE_SUPPORTED_EVIDENCE_PATH", "insufficient_evidence"),
    ]
    assert payload["recognized_out_of_scope_applicability"] == ["device_class", "platform_family"]
    assert [(r["precedence"], r["condition"], r["result"])
            for r in payload["global_status_derivation"]] == [
        (1, "ANY_DIMENSION_CONFLICTING", "conflicting_evidence"),
        (2, "ALL_FOUR_DIMENSIONS_RESOLVED", "classified"),
        (3, "ANY_DIMENSION_RESOLVED", "partial"),
        (4, "ANY_PLATFORM_OR_DEVICE_CLASS_OUT_OF_SCOPE", "recognized_out_of_scope"),
        (5, "ANY_DIMENSION_INSUFFICIENT", "insufficient_evidence"),
        (6, "OTHERWISE", "unknown"),
    ]
    assert payload["knowledge_freshness_policy_execution_semantics"] == {
        "evaluation_time_source": "CLASSIFICATION_REQUEST_KNOWLEDGE_EVALUATION_AT_UTC",
        "negative_age_behavior": "REQUEST_FAIL",
        "policy_source": "KNOWLEDGE_PROVENANCE_REFERENCED_POLICY",
        "dimension_override_precedence": "MATCHING_DIMENSION_OVERRIDE_REPLACES_GENERAL_STATE_RULE",
        "strength_cap_mode": "MINIMUM_AUTHORITY",
        "expired_behavior": "NO_NEW_CLAIM",
    }
    assert not set(payload) & {"source_name_priority", "claim_derivation_priority", "fresh_max_age_ms"}


def test_double_build_and_set_permutations_preserve_identity_not_sequence_permutations():
    deps = _deps()
    left, right = _candidate(**deps), _candidate(**deps)
    assert (left.semantic_payload_json, left.content_sha256, left.artifact_id) == (
        right.semantic_payload_json, right.content_sha256, right.artifact_id)
    payload = left.semantic_payload
    for name in ("same_origin_ambiguity_conflict_rules", "same_origin_conflict_strength_rules",
                 "cross_origin_fusion_matrix", "recognized_out_of_scope_applicability"):
        payload[name].reverse()
    assert make_classification_policy(payload).artifact_id == left.artifact_id
    for name in ("support_level_rules", "dimension_result_rules", "global_status_derivation"):
        changed = left.semantic_payload
        changed[name].reverse()
        with pytest.raises(DeviceFingerprintValidationError):
            make_classification_policy(changed)


def test_generic_alternate_dependencies_validate_but_initial_gate_rejects_anchors():
    deps = _deps()
    tax = deps["classification_taxonomy"].semantic_payload
    tax["manufacturer_records"] = [{"manufacturer_id": "synthetic", "display_label": "Synthetic"}]
    deps["classification_taxonomy"] = make_classification_taxonomy(tax)
    candidate = _candidate(**deps)
    assert validate_classification_policy_dependencies(candidate, **deps)
    result = _gate(candidate, deps=deps)
    assert "initial_taxonomy_identity_mismatch" in result.failure_reasons
    assert "classification_policy_dependency_invalid" not in result.failure_reasons
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []


def test_synthetic_gate_pass_has_exact_inputs_output_decisions_and_null_times():
    assert "initial_admission" not in signature(run_ff2_classification_policy_gate).parameters
    result = _gate()
    manifest = result.gate_result_manifest.semantic_payload
    assert manifest["status"] == "PASS", result.failure_reasons
    assert (len(manifest["input_artifact_refs"]), len(manifest["output_artifact_refs"])) == (3, 1)
    assert manifest["decision_record_refs"] == _DECISIONS
    assert {row["evidence_label"] for row in manifest["retained_evidence_refs"]} == {
        "classification_policy_test_vectors", "classification_policy_review_report"}
    vector_ref = next(row for row in manifest["retained_evidence_refs"]
                      if row["evidence_label"] == "classification_policy_test_vectors")
    assert vector_ref["file_sha256"] == hashlib.sha256(_VECTOR.read_bytes()).hexdigest()
    assert all(value is None for value in manifest["trusted_time_inputs"].values())
    assert (manifest["gate_id"], manifest["gate_contract_version"]) == ("F-F2", "R14-F-F2-v1")
    assert manifest["proof_execution_identity"]["executor_kind"] == "TECHLEAD_GATE_TOOL"
    assert result.double_build_bytes_equal and result.permutation_invariant
    assert result.dependency_validation_passed and result.failure_reasons == ()


@pytest.mark.parametrize("evidence,decisions,reason", [
    ([], _DECISIONS, "retained_evidence_required"),
    (_evidence(), [], "owner_techlead_decisions_required"),
    (_evidence(), _DECISIONS[:1], "owner_techlead_decisions_required"),
    (_evidence(), [_DECISIONS[0], _DECISIONS[0]], "owner_techlead_decisions_required"),
])
def test_gate_requires_evidence_and_two_distinct_decisions(evidence, decisions, reason):
    result = _gate(evidence=evidence, decisions=decisions)
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []
    assert reason in result.failure_reasons


def test_unrelated_evidence_cannot_substitute_for_both_mandatory_proofs():
    unrelated = deepcopy(_evidence()[1])
    unrelated["evidence_label"] = "unrelated_proof"
    result = _gate(evidence=[unrelated])
    assert set(result.failure_reasons) == {
        "classification_policy_test_vectors_evidence_invalid",
        "classification_policy_review_report_required",
    }
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []


@pytest.mark.parametrize("evidence,expected_reason", [
    ([_evidence()[1]], "classification_policy_test_vectors_evidence_invalid"),
    ([_evidence()[0]], "classification_policy_review_report_required"),
])
def test_each_mandatory_proof_label_is_required(evidence, expected_reason):
    result = _gate(evidence=evidence)
    assert expected_reason in result.failure_reasons
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []


@pytest.mark.parametrize("field,bad_value", [
    ("file_sha256", "a" * 64),
    ("media_type", "text/plain"),
])
def test_vector_ref_requires_exact_sha_and_json_media_type(field, bad_value):
    evidence = deepcopy(_evidence())
    evidence[0][field] = bad_value
    result = _gate(evidence=evidence)
    assert "classification_policy_test_vectors_evidence_invalid" in result.failure_reasons
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []


@pytest.mark.parametrize("label_index,expected_reason", [
    (0, "classification_policy_test_vectors_evidence_invalid"),
    (1, "classification_policy_review_report_required"),
])
def test_duplicate_mandatory_label_fails_even_for_identical_refs(label_index, expected_reason):
    evidence = deepcopy(_evidence())
    evidence.append(deepcopy(evidence[label_index]))
    result = _gate(evidence=evidence)
    assert expected_reason in result.failure_reasons
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []


def test_duplicate_vector_label_fails_even_if_only_one_ref_has_correct_sha():
    evidence = deepcopy(_evidence())
    duplicate = deepcopy(evidence[0])
    duplicate["file_sha256"] = "a" * 64
    evidence.append(duplicate)
    result = _gate(evidence=evidence)
    assert "classification_policy_test_vectors_evidence_invalid" in result.failure_reasons
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []


def test_exact_mandatory_evidence_plus_unrelated_extra_still_passes():
    evidence = deepcopy(_evidence())
    extra = deepcopy(evidence[1])
    extra["evidence_label"] = "unrelated_extra_proof"
    evidence.append(extra)
    result = _gate(evidence=evidence)
    manifest = result.gate_result_manifest.semantic_payload
    assert result.failure_reasons == ()
    assert manifest["status"] == "PASS"
    assert len(manifest["retained_evidence_refs"]) == 3
    assert (len(manifest["input_artifact_refs"]), len(manifest["output_artifact_refs"])) == (3, 1)


def test_identical_unrelated_extra_refs_remain_generic_manifest_error():
    evidence = deepcopy(_evidence())
    extra = deepcopy(evidence[1])
    extra["evidence_label"] = "unrelated_extra_proof"
    evidence.extend([extra, deepcopy(extra)])
    with pytest.raises(DeviceFingerprintValidationError):
        _gate(evidence=evidence)


@pytest.mark.parametrize("bad_evidence", [
    None, "not-a-list", [None], [{}], [{"evidence_label": []}],
    [{"evidence_label": "classification_policy_test_vectors"}],
])
def test_malformed_retained_evidence_api_never_leaks_builtin_errors_or_passes(bad_evidence):
    with pytest.raises(DeviceFingerprintValidationError):
        _gate(evidence=bad_evidence)


@pytest.mark.parametrize("mutation", [
    lambda p: p.pop("policy_schema_version"),
    lambda p: p.update(extra=True),
    lambda p: p.update(classification_taxonomy=p["alias_mapping"]),
    lambda p: p.update(alias_mapping={"artifact_id": "bad", "content_sha256": "a" * 64}),
    lambda p: p["claim_derivation_semantics"].update(extra="PROVENANCE_ONLY_NO_AUTHORITY_ORDER"),
    lambda p: p["claim_derivation_semantics"].pop("declared"),
    lambda p: p["claim_derivation_semantics"].update(declared="HIGHER_AUTHORITY"),
    lambda p: p["claim_strength_semantics"].update(extra=3),
    lambda p: p["claim_strength_semantics"].update(strong=1, supporting=2),
    lambda p: p["same_origin_ambiguity_conflict_rules"].clear(),
    lambda p: p["same_origin_ambiguity_conflict_rules"].append({"rule": "OTHER"}),
    lambda p: p["same_origin_ambiguity_conflict_rules"][0].update(projection_mode="WHOLE_DEVICE"),
    lambda p: p["same_origin_conflict_strength_rules"].pop(),
    lambda p: p["same_origin_conflict_strength_rules"].append({"left_strength": "other"}),
    lambda p: p["same_origin_conflict_strength_rules"].append({
        "left_strength": "supporting", "right_strength": "strong", "compatibility": "SAME",
        "outcome": "RESOLVED_STRONG"}),
    lambda p: next(row for row in p["same_origin_conflict_strength_rules"]
                   if row["left_strength"] == "strong" and row["right_strength"] == "strong"
                   and row["compatibility"] == "INCOMPATIBLE").update(outcome="RESOLVED_STRONG"),
    lambda p: next(row for row in p["same_origin_conflict_strength_rules"]
                   if row["left_strength"] == "strong" and row["right_strength"] == "supporting"
                   and row["compatibility"] == "INCOMPATIBLE").update(outcome="CONFLICT_STRONG"),
    lambda p: p["support_level_rules"].reverse(),
    lambda p: p["support_level_rules"].pop(),
    lambda p: p["support_level_rules"][0].update(condition="HIGH_ALLOWS_CONTRADICTION"),
    lambda p: p["dimension_result_rules"].reverse(),
    lambda p: p["dimension_result_rules"][3].update(result="ambiguous"),
    lambda p: p["recognized_out_of_scope_applicability"].append("manufacturer_family"),
    lambda p: p["recognized_out_of_scope_applicability"].append("model_family"),
    lambda p: p["global_status_derivation"].reverse(),
    lambda p: p["global_status_derivation"][0].update(condition="ANY_DIMENSION_RESOLVED"),
    lambda p: p["global_status_derivation"][0].update(result="classified"),
    lambda p: p["knowledge_freshness_policy_execution_semantics"].update(
        evaluation_time_source="WALL_CLOCK"),
    lambda p: p["knowledge_freshness_policy_execution_semantics"].update(
        fresh_max_age_ms=100),
    lambda p: p["knowledge_freshness_policy_execution_semantics"].update(
        dimension_override_precedence="GENERAL_RULE_WINS"),
    lambda p: p["knowledge_freshness_policy_execution_semantics"].update(
        strength_cap_mode="MAXIMUM_AUTHORITY"),
    lambda p: p["knowledge_freshness_policy_execution_semantics"].update(
        expired_behavior="CLAIM_ALLOWED"),
    lambda p: p["knowledge_freshness_policy_execution_semantics"].update(
        negative_age_behavior="IGNORE"),
    lambda p: p.update(ClassificationRetentionPolicy={}),
    lambda p: p.update(ProductValidationPolicy={}),
    lambda p: p.update(SnapshotExecutionPolicy={}),
    lambda p: p.update(SnapshotContentPolicy={}),
    lambda p: p.update(SourceHealthPolicy={}),
])
def test_closed_schema_and_frozen_rule_mutations_rejected(mutation):
    payload = _candidate().semantic_payload
    mutation(payload)
    with pytest.raises(DeviceFingerprintValidationError):
        make_classification_policy(payload)


@pytest.mark.parametrize("mutation", [
    lambda p: p["cross_origin_fusion_matrix"].pop(),
    lambda p: p["cross_origin_fusion_matrix"].append(deepcopy(p["cross_origin_fusion_matrix"][0])),
    lambda p: p["cross_origin_fusion_matrix"][0].update(
        strong_clean_present=False, strong_clean_disagree=True),
    lambda p: p["cross_origin_fusion_matrix"][0].update(outcome="SELECT_STRONG"),
    lambda p: p["cross_origin_fusion_matrix"][0].update(record_supporting_contradiction=True),
    lambda p: p["cross_origin_fusion_matrix"][0].update(support_cap="MEDIUM"),
])
def test_fusion_missing_duplicate_invalid_and_wrong_outcome_rejected(mutation):
    payload = _candidate().semantic_payload
    mutation(payload)
    with pytest.raises(DeviceFingerprintValidationError):
        make_classification_policy(payload)


@pytest.mark.parametrize("field,builder,reason", [
    ("classification_taxonomy", "taxonomy", "initial_taxonomy_identity_mismatch"),
    ("alias_mapping", "alias", "initial_alias_identity_mismatch"),
    ("evidence_adapter_contract_set", "adapter", "initial_adapter_identity_mismatch"),
])
def test_alternate_prerequisite_identity_fails_only_initial_anchor(field, builder, reason):
    deps = _deps()
    payload = deps[field].semantic_payload
    if builder == "taxonomy":
        payload["manufacturer_records"] = [{"manufacturer_id": "other", "display_label": "Other"}]
        deps[field] = make_classification_taxonomy(payload)
    elif builder == "alias":
        payload["source_taxonomy_mappings"].append({
            "source_id": "synthetic", "dimension_name": "platform_family",
            "source_taxon": "unmapped", "mapping_kind": "UNMAPPED", "target_id_or_ref": None})
        deps[field] = make_alias_mapping(payload)
    else:
        payload["adapter_entries"][0]["semantic_projection_id"] = "synthetic.alternate.projection"
        deps[field] = make_evidence_adapter_contract_set(payload)
    candidate = _candidate(**deps)
    assert validate_classification_policy_dependencies(candidate, **deps)
    result = _gate(candidate, deps=deps)
    assert reason in result.failure_reasons
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []


def test_wrong_dependency_content_and_invalid_candidate_have_distinct_gate_reasons():
    candidate = _candidate()
    deps = _deps()
    alternate = deps["classification_taxonomy"].semantic_payload
    alternate["manufacturer_records"] = [{"manufacturer_id": "other", "display_label": "Other"}]
    deps["classification_taxonomy"] = make_classification_taxonomy(alternate)
    dependency_failure = _gate(candidate, deps=deps)
    assert "classification_policy_dependency_invalid" in dependency_failure.failure_reasons
    assert dependency_failure.gate_result_manifest.semantic_payload["output_artifact_refs"] == []
    payload = candidate.semantic_payload
    payload["cross_origin_fusion_matrix"].pop()
    incomplete = _gate(_raw_candidate(payload))
    assert "classification_policy_matrix_incomplete" in incomplete.failure_reasons
    assert incomplete.gate_result_manifest.semantic_payload["output_artifact_refs"] == []
    payload = candidate.semantic_payload
    payload["cross_origin_fusion_matrix"][0]["outcome"] = "SELECT_STRONG"
    mismatch = _gate(_raw_candidate(payload))
    assert "classification_policy_matrix_mismatch" in mismatch.failure_reasons
    assert mismatch.gate_result_manifest.semantic_payload["output_artifact_refs"] == []
    payload = candidate.semantic_payload
    payload["SourceHealthPolicy"] = {}
    contamination = _gate(_raw_candidate(payload))
    assert "classification_policy_cross_layer_contamination" in contamination.failure_reasons
    assert contamination.gate_result_manifest.semantic_payload["output_artifact_refs"] == []


def test_generic_dependencies_reject_alias_target_and_invalid_adapter_content():
    deps = _deps()
    alias_payload = deps["alias_mapping"].semantic_payload
    alias_payload["source_taxonomy_mappings"].append({
        "source_id": "synthetic", "dimension_name": "platform_family",
        "source_taxon": "unadmitted", "mapping_kind": "CANONICAL_VALUE",
        "target_id_or_ref": "unadmitted-platform"})
    deps["alias_mapping"] = make_alias_mapping(alias_payload)
    candidate = _candidate(**deps)
    with pytest.raises(DeviceFingerprintValidationError):
        validate_classification_policy_dependencies(candidate, **deps)

    deps = _deps()
    bad_adapter = deps["evidence_adapter_contract_set"].semantic_payload
    bad_adapter["adapter_entries"][0]["adapter_kind"] = "UNKNOWN"
    deps["evidence_adapter_contract_set"] = make_artifact_content(
        "EvidenceAdapterContractSet", bad_adapter)
    candidate = _candidate(**deps)
    with pytest.raises(DeviceFingerprintValidationError):
        validate_classification_policy_dependencies(candidate, **deps)
