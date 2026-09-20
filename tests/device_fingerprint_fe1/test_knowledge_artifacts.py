from copy import deepcopy

import pytest

from app.device_fingerprint.artifact_content import ArtifactRef
from app.device_fingerprint.knowledge_artifacts import (
    make_canonical_k1_record_set,
    make_external_knowledge_provenance_manifest,
    make_knowledge_freshness_policy,
    match_k1_records,
    project_k1_candidate_dimensions,
)
from app.device_fingerprint.models import DeviceFingerprintValidationError
from research.device_fingerprint_fe1.fixtures import build_k1_fixture_definitions


def _reference(artifact_type: str, digit: str) -> dict[str, str]:
    digest = digit * 64
    return ArtifactRef(
        artifact_id=f"{artifact_type}:v1:sha256:{digest}", content_sha256=digest,
    ).as_dict()


def _freshness_payload():
    return {
        "knowledge_freshness_policy_version": 1,
        "source_family_id": "fixture.external",
        "fresh_max_age_ms": 1000,
        "stale_max_age_ms": 2000,
        "freshness_state_rules": [
            {
                "freshness_state": "expired",
                "claim_eligible": False,
                "claim_strength_cap": "NONE",
                "required_explanation_code": "knowledge_source_expired",
                "dimension_overrides": [],
            },
            {
                "freshness_state": "fresh",
                "claim_eligible": True,
                "claim_strength_cap": "NO_ADDITIONAL_CAP",
                "required_explanation_code": None,
                "dimension_overrides": [],
            },
            {
                "freshness_state": "stale",
                "claim_eligible": True,
                "claim_strength_cap": "supporting",
                "required_explanation_code": "knowledge_source_stale",
                "dimension_overrides": [{
                    "dimension_name": "device_class",
                    "claim_eligible": False,
                    "claim_strength_cap": "NONE",
                    "required_explanation_code": "stale_device_class_disabled",
                }],
            },
        ],
    }


def test_freshness_policy_is_closed_canonical_and_fail_closed():
    artifact = make_knowledge_freshness_policy(_freshness_payload())
    assert [row["freshness_state"] for row in artifact.semantic_payload[
        "freshness_state_rules"
    ]] == ["fresh", "stale", "expired"]

    invalid = _freshness_payload()
    invalid["fresh_max_age_ms"] = 2001
    with pytest.raises(DeviceFingerprintValidationError):
        make_knowledge_freshness_policy(invalid)

    invalid = _freshness_payload()
    invalid["freshness_state_rules"][0]["claim_eligible"] = True
    with pytest.raises(DeviceFingerprintValidationError):
        make_knowledge_freshness_policy(invalid)


def test_freshness_state_permutation_has_frozen_order_and_identity():
    first_payload = _freshness_payload()
    second_payload = _freshness_payload()
    second_payload["freshness_state_rules"] = list(reversed(
        second_payload["freshness_state_rules"]
    ))
    first = make_knowledge_freshness_policy(first_payload)
    second = make_knowledge_freshness_policy(second_payload)
    assert first.artifact_id == second.artifact_id
    assert first.semantic_payload == second.semantic_payload
    assert [row["freshness_state"] for row in first.semantic_payload[
        "freshness_state_rules"
    ]] == ["fresh", "stale", "expired"]


def test_external_provenance_has_exact_external_shape():
    artifact = make_external_knowledge_provenance_manifest({
        "provenance_contract_version": 1,
        "provenance_kind": "external",
        "source_artifact_sha256": "a" * 64,
        "source_governance_record": _reference("SourceGovernanceRecord", "b"),
        "retrieved_at_utc": "2026-09-20T00:00:00.000Z",
        "source_provider_version_metadata": "fixture revision 1",
        "knowledge_freshness_policy": _reference("KnowledgeFreshnessPolicy", "c"),
        "importer_identity": "fixture-importer",
        "importer_version": "1.0.0",
    })
    assert artifact.artifact_type == "KnowledgeProvenanceManifest"
    invalid = artifact.semantic_payload
    invalid["repository_commit_sha"] = "d" * 40
    with pytest.raises(DeviceFingerprintValidationError):
        make_external_knowledge_provenance_manifest(invalid)


def test_required_fixture_modes_conjunction_candidates_and_projection():
    fixtures = build_k1_fixture_definitions()
    for name in ("all_any", "all_non_any_multi_candidate", "one_non_any_mismatch",
                 "nullable_exact_value"):
        definition = fixtures[name]
        actual = tuple(record["canonical_record_id"] for record in match_k1_records(
            definition["record_set"], definition["evidence"],
        ))
        assert actual == definition["expected_candidate_ids"]

    multi = fixtures["all_non_any_multi_candidate"]
    projection = project_k1_candidate_dimensions(match_k1_records(
        multi["record_set"], multi["evidence"],
    ))
    assert projection["platform_family"] == {
        "status": "resolved", "canonical_values": ["android"],
    }
    assert projection["device_class"] == {
        "status": "ambiguous", "canonical_values": ["smartphone", "tablet"],
    }
    assert project_k1_candidate_dimensions(())["platform_family"]["status"] == (
        "empty_candidate_set"
    )


def test_row_order_is_identity_and_candidate_set_invariant():
    fixture = build_k1_fixture_definitions()["row_order_permutation"]
    assert fixture["first"].artifact_id == fixture["second"].artifact_id
    first = match_k1_records(fixture["first"], fixture["evidence"])
    second = match_k1_records(fixture["second"], fixture["evidence"])
    assert tuple(row["canonical_record_id"] for row in first) == tuple(
        row["canonical_record_id"] for row in second
    )


def test_k1_has_no_non_dhcp_predicate_path_and_evidence_is_closed():
    fixture = build_k1_fixture_definitions()["all_any"]
    bad_evidence = {**fixture["evidence"], "mac": "02:00:00:00:00:01"}
    with pytest.raises(DeviceFingerprintValidationError):
        match_k1_records(fixture["record_set"], bad_evidence)

    payload = deepcopy(fixture["record_set"].semantic_payload)
    payload["records"][0]["dhcp_predicates"]["ipttl"] = {
        "mode": "EXACT_VALUE", "value": 64,
    }
    with pytest.raises(DeviceFingerprintValidationError):
        make_canonical_k1_record_set(payload)
