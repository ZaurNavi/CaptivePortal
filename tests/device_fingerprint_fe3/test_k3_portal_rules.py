from copy import deepcopy

import pytest

from app.device_fingerprint.artifact_content import ArtifactRef
from app.device_fingerprint.k3_portal_rules import (
    build_k3_internal_provenance, build_k3_portal_rule_set_v1,
    evaluate_k3_rules, make_k3_portal_rule_set,
)
from app.device_fingerprint.knowledge_artifacts import make_internal_knowledge_provenance_manifest
from app.device_fingerprint.models import DeviceFingerprintValidationError


def _reference(artifact_type, digit):
    digest = digit * 64
    return ArtifactRef(f"{artifact_type}:v1:sha256:{digest}", digest).as_dict()


def _payload():
    return build_k3_portal_rule_set_v1().semantic_payload


def test_exact_rules_vectors_and_repeated_identity():
    first = build_k3_portal_rule_set_v1()
    second = build_k3_portal_rule_set_v1()
    assert first.artifact_id == second.artifact_id
    payload = first.semantic_payload
    assert payload["admitted_feature_schema_versions"] == [1, 2]
    assert len(payload["rules"]) == 13
    assert len(payload["test_vectors"]) == 21
    assert all(rule["base_claim_strength"] == "supporting" for rule in payload["rules"])
    assert {rule["outcome_id_or_ref"] for rule in payload["rules"]} == {
        "android", "ios", "windows", "macos", "chromeos", "linux", "tablet",
    }
    for vector in payload["test_vectors"]:
        actual = evaluate_k3_rules(
            first, vector["feature_schema_version"], vector["normalized_input"],
        )
        assert actual == {
            "matched_rule_ids": vector["expected_rule_ids"],
            "dimension_outcomes": vector["expected_dimension_outcomes"],
        }


def test_rule_and_vector_order_do_not_change_identity():
    payload = _payload()
    payload["rules"].reverse()
    payload["test_vectors"].reverse()
    for rule in payload["rules"]:
        rule["input_predicates"].reverse()
    assert make_k3_portal_rule_set(payload).artifact_id == build_k3_portal_rule_set_v1().artifact_id


def test_predicate_in_set_orders_integer_values_numerically():
    payload = _payload()
    payload["test_vectors"] = []
    payload["rules"][0]["input_predicates"].append({
        "field_name": "os_major", "operator": "IN", "value": None,
        "values": [10, 2],
    })
    artifact = make_k3_portal_rule_set(payload)
    assert next(predicate for predicate in artifact.semantic_payload["rules"][0][
        "input_predicates"
    ] if predicate["field_name"] == "os_major")["values"] == [2, 10]


def test_independent_conflicting_observations_are_not_resolved_by_priority():
    artifact = build_k3_portal_rule_set_v1()
    vectors = artifact.semantic_payload["test_vectors"]
    android = next(v for v in vectors if v["test_vector_id"] == "k3.vector.platform.android.user_agent.v1")
    ios = next(v for v in vectors if v["test_vector_id"] == "k3.vector.platform.ios.user_agent.v1")
    first = evaluate_k3_rules(artifact, 1, android["normalized_input"])
    second = evaluate_k3_rules(artifact, 1, ios["normalized_input"])
    assert first["dimension_outcomes"]["platform_family"] == "android"
    assert second["dimension_outcomes"]["platform_family"] == "ios"
    assert first["matched_rule_ids"] != second["matched_rule_ids"]


@pytest.mark.parametrize("mutation", [
    lambda p: p["rules"][0]["input_predicates"][0].update(field_name="raw_user_agent"),
    lambda p: p["rules"][0]["input_predicates"][0].update(field_name="user_agent"),
    lambda p: p["rules"][0]["input_predicates"][0].update(field_name="future_field"),
    lambda p: p["rules"][0]["input_predicates"][0].update(operator="REGEX"),
    lambda p: p["rules"][0]["input_predicates"][0].update(operator=[]),
    lambda p: p["rules"][0]["input_predicates"][0].update(operator="IN", value="android"),
    lambda p: p["rules"][0]["input_predicates"][0].update(operator="IS_TRUE", value="android"),
    lambda p: p["rules"][0]["input_predicates"][0].update(values=["android"]),
    lambda p: p["rules"][0].update(base_claim_strength="invented"),
    lambda p: p["rules"][0].update(base_claim_strength="strong"),
    lambda p: p["rules"][0].update(extra_field="no"),
    lambda p: p["rules"][0]["input_predicates"].append({
        "field_name": "form_factor_tablet", "operator": "IS_TRUE", "value": None, "values": [],
    }),
])
def test_rule_validation_fails_closed(mutation):
    payload = _payload()
    mutation(payload)
    with pytest.raises(DeviceFingerprintValidationError):
        make_k3_portal_rule_set(payload)


@pytest.mark.parametrize("mutation", [
    lambda v: v.update(feature_schema_version=3),
    lambda v: v.update(feature_schema_version=2),
    lambda v: v["normalized_input"].update(raw_headers="secret"),
    lambda v: v["normalized_input"].update(form_factor_tablet=True),
    lambda v: v.update(expected_rule_ids=[]),
    lambda v: v["expected_dimension_outcomes"].update(platform_family="ios"),
])
def test_vector_validation_and_expected_results_fail_closed(mutation):
    payload = _payload()
    vector = next(v for v in payload["test_vectors"] if v["test_vector_id"] == "k3.vector.platform.android.user_agent.v1")
    mutation(vector)
    with pytest.raises(DeviceFingerprintValidationError):
        make_k3_portal_rule_set(payload)


def test_v2_payload_declared_v1_and_duplicate_ids_are_rejected():
    payload = _payload()
    vector = next(v for v in payload["test_vectors"] if v["feature_schema_version"] == 2)
    vector["feature_schema_version"] = 1
    with pytest.raises(DeviceFingerprintValidationError):
        make_k3_portal_rule_set(payload)
    payload = _payload()
    payload["rules"][1]["rule_id"] = payload["rules"][0]["rule_id"]
    with pytest.raises(DeviceFingerprintValidationError):
        make_k3_portal_rule_set(payload)
    payload = _payload()
    payload["test_vectors"][1]["test_vector_id"] = payload["test_vectors"][0]["test_vector_id"]
    with pytest.raises(DeviceFingerprintValidationError):
        make_k3_portal_rule_set(payload)


def test_k3_v1_requires_exact_version_and_both_admitted_schema_versions():
    payload = _payload()
    payload["k3_rule_set_version"] = "future"
    with pytest.raises(DeviceFingerprintValidationError):
        make_k3_portal_rule_set(payload)
    payload = _payload()
    payload["admitted_feature_schema_versions"] = [1]
    with pytest.raises(DeviceFingerprintValidationError):
        make_k3_portal_rule_set(payload)


def test_equal_strength_conflict_retains_rule_ids_and_null_projection():
    payload = _payload()
    original = next(rule for rule in payload["rules"] if rule["rule_id"] == "k3.portal.platform.android.user_agent.v1")
    competing = deepcopy(original)
    competing["rule_id"] = "k3.portal.platform.conflict.user_agent.v1"
    competing["outcome_id_or_ref"] = "ios"
    payload["rules"].append(competing)
    payload["test_vectors"] = []
    artifact = make_k3_portal_rule_set(payload)
    vector = next(v for v in _payload()["test_vectors"] if v["test_vector_id"] == "k3.vector.platform.android.user_agent.v1")
    actual = evaluate_k3_rules(artifact, 1, vector["normalized_input"])
    assert actual["matched_rule_ids"] == sorted([original["rule_id"], competing["rule_id"]])
    assert actual["dimension_outcomes"]["platform_family"] is None


def _internal_payload():
    return {
        "provenance_contract_version": 1,
        "provenance_kind": "internal",
        "rule_set_artifact": _reference("K3PortalRuleSet", "a"),
        "repository_commit_sha": "b" * 40,
        "repository_tree_sha": "c" * 40,
        "source_artifact_identity": None,
        "input_schema_compatibility": [
            {"source_kind": "portal_headers", "feature_schema_version": 2},
            {"source_kind": "portal_headers", "feature_schema_version": 1},
        ],
        "taxonomy_compatibility": _reference("ClassificationTaxonomy", "d"),
        "rule_set_version": "k3_portal_rules_v1",
    }


def test_internal_provenance_exact_arm_xor_and_canonical_compatibility():
    payload = _internal_payload()
    artifact = make_internal_knowledge_provenance_manifest(payload)
    assert artifact.semantic_payload["input_schema_compatibility"] == [
        {"source_kind": "portal_headers", "feature_schema_version": 1},
        {"source_kind": "portal_headers", "feature_schema_version": 2},
    ]
    reversed_payload = deepcopy(payload)
    reversed_payload["input_schema_compatibility"].reverse()
    assert make_internal_knowledge_provenance_manifest(reversed_payload).artifact_id == artifact.artifact_id
    alternate = deepcopy(payload)
    alternate.update(repository_commit_sha=None, repository_tree_sha=None,
                     source_artifact_identity="e" * 64)
    assert make_internal_knowledge_provenance_manifest(alternate).semantic_payload[
        "source_artifact_identity"
    ] == "e" * 64
    for changes in (
        {"repository_commit_sha": None},
        {"repository_tree_sha": None},
        {"source_artifact_identity": "e" * 64},
        {"repository_commit_sha": "INVALID"},
        {"source_artifact_identity": "INVALID"},
        {"retrieved_at_utc": "2026-09-22T00:00:00.000Z"},
    ):
        invalid = deepcopy(payload)
        invalid.update(changes)
        with pytest.raises(DeviceFingerprintValidationError):
            make_internal_knowledge_provenance_manifest(invalid)
    invalid = deepcopy(payload)
    invalid["input_schema_compatibility"].append(invalid["input_schema_compatibility"][0])
    with pytest.raises(DeviceFingerprintValidationError):
        make_internal_knowledge_provenance_manifest(invalid)


def test_k3_provenance_builder_requires_supplied_final_identifiers():
    rule_set = build_k3_portal_rule_set_v1()
    taxonomy = _reference("ClassificationTaxonomy", "d")
    artifact = build_k3_internal_provenance(
        rule_set, repository_commit_sha="b" * 40,
        repository_tree_sha="c" * 40, taxonomy_compatibility=taxonomy,
    )
    payload = artifact.semantic_payload
    assert payload["rule_set_artifact"] == {
        "artifact_id": rule_set.artifact_id, "content_sha256": rule_set.content_sha256,
    }
    assert payload["taxonomy_compatibility"] == taxonomy
    assert payload["source_artifact_identity"] is None
    assert payload["rule_set_version"] == "k3_portal_rules_v1"
    with pytest.raises(DeviceFingerprintValidationError):
        build_k3_internal_provenance(
            rule_set, repository_commit_sha="invalid", repository_tree_sha="c" * 40,
            taxonomy_compatibility=taxonomy,
        )
