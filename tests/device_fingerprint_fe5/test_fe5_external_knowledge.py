from datetime import datetime, timedelta, timezone
import inspect

import pytest

from app.device_fingerprint.artifact_content import ArtifactRef
import app.device_fingerprint.fe5_external_knowledge as fe5
from app.device_fingerprint.k2a_conformance_artifacts import make_source_governance_record
from app.device_fingerprint.k4_ieee_import import compute_ieee_k4_source_bundle_sha256
from app.device_fingerprint.knowledge_artifacts import (
    make_external_knowledge_provenance_manifest, make_knowledge_freshness_policy,
)
from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.validation import format_utc

_NOW = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
_NOW_TEXT = "2026-09-23T12:00:00.000Z"
_DECISION = "22222222-2222-4222-8222-222222222222"  # Synthetic test-only ref.
_EVIDENCE = [{"evidence_label": "synthetic_source_audit", "file_sha256": "e" * 64,
              "media_type": "application/json", "path_or_reference": "test://audit"}]
_SPEC = {
    "satori_dhcp": ("K1", "current",
        "direct admitted DHCP taxonomy mappings only; supporting authority; ambiguity preserved",
        "captivportal.k1_satori_import", fe5.SATORI_SOURCE_SHA256,
        fe5._SOURCE_METADATA["satori_dhcp"]),
    "p0f3_legacy_tcp": ("K2B", "legacy",
        "platform_family only; supporting authority; legacy source; other dimensions NO_CLAIM",
        "captivportal.k2b_p0f_import", "b" * 64,
        fe5._SOURCE_METADATA["p0f3_legacy_tcp"]),
    "ieee_ra_mac": ("K4", "current",
        "raw mac_assignment_org only; manufacturer_mapping remains null unless separately reviewed",
        "captivportal.k4_ieee_import", "c" * 64,
        "IEEE-RA-MA-L-MA-M-MA-S:bundle-sha256=" + "c" * 64),
}
_POLICIES = {
    "satori_dhcp": fe5.build_satori_k1_freshness_policy,
    "p0f3_legacy_tcp": fe5.build_p0f_k2b_freshness_policy,
    "ieee_ra_mac": fe5.build_ieee_k4_freshness_policy,
}


def _ref(artifact):
    return ArtifactRef(artifact.artifact_id, artifact.content_sha256).as_dict()


def _governance(family):
    return make_source_governance_record({
        "governance_contract_version": 1, "source_name": f"synthetic {family}",
        "source_provenance": "synthetic retained-test fixture",
        "license_identifier": "test-only", "license_source_reference": "test-only",
        "license_text_sha256": None, "local_storage_status": "STORED_LOCAL",
        "modification_import_status": "IMPORTED_NORMALIZED",
        "redistribution_status": "ALLOWED", "attribution_requirement": "NOT_REQUIRED",
        "commercial_use_status": "ALLOWED", "review_basis_semantics": "test-only",
        "unresolved_restrictions": [],
    })


def _candidate(family, age_ms, *, governance=None, policy=None):
    slot, character, caveat, importer, digest, metadata = _SPEC[family]
    governance = governance or _governance(family)
    policy = policy or _POLICIES[family]()
    retrieved_at = format_utc(_NOW - timedelta(milliseconds=age_ms))
    provenance = make_external_knowledge_provenance_manifest({
        "provenance_contract_version": 1, "provenance_kind": "external",
        "source_artifact_sha256": digest,
        "source_governance_record": _ref(governance),
        "retrieved_at_utc": retrieved_at,
        "source_provider_version_metadata": metadata,
        "knowledge_freshness_policy": _ref(policy),
        "importer_identity": importer, "importer_version": "1",
    })
    return fe5.ExternalKnowledgeCandidate(
        slot, family, character, caveat, governance, policy, provenance,
    )


def _run(monkeypatch, k1, k2b, k4, *, evidence=_EVIDENCE, decisions=(_DECISION,)):
    calls = []
    def trusted_now():
        calls.append(True)
        return _NOW_TEXT
    monkeypatch.setattr(fe5, "_trusted_utc_now", trusted_now)
    result = fe5.run_fe5_external_admission_gate(
        k1, k2b, k4,
        candidate_repository_commit_sha="a" * 40,
        candidate_repository_tree_sha="b" * 40,
        environment_identity="synthetic-fixture",
        retained_evidence_refs=list(evidence), decision_record_refs=list(decisions),
    )
    assert calls == [True]
    assert result.foundation_knowledge_evaluation_at_utc == _NOW_TEXT
    assert result.gate_result_manifest.semantic_payload["trusted_time_inputs"] == {
        "foundation_knowledge_evaluation_at_utc": _NOW_TEXT,
        "foundation_admission_evaluation_at_utc": None,
        "knowledge_evaluation_at_utc": None,
    }
    return result


def test_policy_identifiers_thresholds_rules_and_no_overrides():
    expected = {
        "satori_dhcp": (31536000000, 63072000000),
        "p0f3_legacy_tcp": (0, 9223372036854775807),
        "ieee_ra_mac": (172800000, 604800000),
    }
    for family, (fresh, stale) in expected.items():
        first = _POLICIES[family]()
        assert first.artifact_id == _POLICIES[family]().artifact_id
        payload = first.semantic_payload
        assert payload["source_family_id"] == family
        assert (payload["fresh_max_age_ms"], payload["stale_max_age_ms"]) == (fresh, stale)
        assert [rule["freshness_state"] for rule in payload["freshness_state_rules"]] == [
            "fresh", "stale", "expired",
        ]
        assert [(r["claim_eligible"], r["claim_strength_cap"],
                 r["required_explanation_code"], r["dimension_overrides"])
                for r in payload["freshness_state_rules"]] == [
            (True, "NO_ADDITIONAL_CAP", None, []),
            (True, "supporting", "knowledge_source_stale", []),
            (False, "NONE", "knowledge_source_expired", []),
        ]


@pytest.mark.parametrize("family,age,state,eligible,cap", [
    ("satori_dhcp", 0, "fresh", True, "NO_ADDITIONAL_CAP"),
    ("satori_dhcp", 31536000000, "fresh", True, "NO_ADDITIONAL_CAP"),
    ("satori_dhcp", 31536000001, "stale", True, "supporting"),
    ("satori_dhcp", 63072000000, "stale", True, "supporting"),
    ("satori_dhcp", 63072000001, "expired", False, "NONE"),
    ("p0f3_legacy_tcp", 0, "fresh", True, "NO_ADDITIONAL_CAP"),
    ("p0f3_legacy_tcp", 1, "stale", True, "supporting"),
    ("p0f3_legacy_tcp", 315360000000, "stale", True, "supporting"),
    ("ieee_ra_mac", 172800000, "fresh", True, "NO_ADDITIONAL_CAP"),
    ("ieee_ra_mac", 172800001, "stale", True, "supporting"),
    ("ieee_ra_mac", 604800000, "stale", True, "supporting"),
    ("ieee_ra_mac", 604800001, "expired", False, "NONE"),
])
def test_exact_integer_millisecond_freshness_boundaries(family, age, state, eligible, cap):
    candidate = _candidate(family, age)
    result = fe5.evaluate_external_knowledge_freshness(
        candidate.provenance, candidate.freshness_policy,
        knowledge_evaluation_at_utc=_NOW_TEXT,
    )
    assert result["age_ms"] == age
    assert (result["freshness_state"], result["claim_eligible"],
            result["claim_strength_cap"]) == (state, eligible, cap)


@pytest.mark.parametrize("family", list(_SPEC))
def test_negative_age_has_machine_failure_code(family):
    candidate = _candidate(family, -1)
    result = fe5.evaluate_external_knowledge_freshness(
        candidate.provenance, candidate.freshness_policy,
        knowledge_evaluation_at_utc=_NOW_TEXT,
    )
    assert result["age_ms"] == -1
    assert result["failure_code"] == "negative_knowledge_age"
    assert not result["claim_eligible"]


def test_generic_dimension_override_replaces_only_that_dimension():
    payload = fe5.build_ieee_k4_freshness_policy().semantic_payload
    stale = next(rule for rule in payload["freshness_state_rules"] if rule["freshness_state"] == "stale")
    stale["dimension_overrides"] = [{
        "dimension_name": "device_class", "claim_eligible": False,
        "claim_strength_cap": "NONE", "required_explanation_code": "device_class_stale_disabled",
    }]
    policy = make_knowledge_freshness_policy(payload)
    candidate = _candidate("ieee_ra_mac", 172800001, policy=policy)
    general = fe5.evaluate_external_knowledge_freshness(
        candidate.provenance, policy, knowledge_evaluation_at_utc=_NOW_TEXT,
    )
    device = fe5.evaluate_external_knowledge_freshness(
        candidate.provenance, policy, knowledge_evaluation_at_utc=_NOW_TEXT,
        dimension_name="device_class",
    )
    assert general["claim_eligible"] and general["claim_strength_cap"] == "supporting"
    assert not device["claim_eligible"] and device["claim_strength_cap"] == "NONE"


def test_provenance_builders_use_exact_source_identity_and_resolve_artifacts(monkeypatch):
    governance = _governance("satori_dhcp")
    policy = fe5.build_satori_k1_freshness_policy()
    with pytest.raises(DeviceFingerprintValidationError):
        fe5.build_satori_k1_external_provenance(
            b"wrong pinned source", retrieved_at_utc=_NOW_TEXT,
            governance=governance, freshness_policy=policy,
        )
    monkeypatch.setattr(fe5, "verify_p0f_source_bytes", lambda raw: "b" * 64 if raw == b"pinned" else None)
    p0f = fe5.build_p0f_k2b_external_provenance(
        b"pinned", retrieved_at_utc=_NOW_TEXT, governance=governance,
        freshness_policy=fe5.build_p0f_k2b_freshness_policy(),
    )
    assert p0f.semantic_payload["source_artifact_sha256"] == "b" * 64
    assert p0f.semantic_payload["source_provider_version_metadata"].endswith("source_character=legacy")
    source = (b"MA-L", b"MA-M", b"MA-S")
    ieee = fe5.build_ieee_k4_external_provenance(
        *source, retrieved_at_utc=_NOW_TEXT, governance=governance,
        freshness_policy=fe5.build_ieee_k4_freshness_policy(),
    )
    assert ieee.semantic_payload["source_artifact_sha256"] == compute_ieee_k4_source_bundle_sha256(*source)
    assert ieee.semantic_payload["source_provider_version_metadata"].endswith(
        ieee.semantic_payload["source_artifact_sha256"]
    )
    with pytest.raises(DeviceFingerprintValidationError):
        fe5.build_ieee_k4_external_provenance(
            *source, retrieved_at_utc="2026-09-23T12:00:00Z",
            governance=governance, freshness_policy=fe5.build_ieee_k4_freshness_policy(),
        )
    with pytest.raises(DeviceFingerprintValidationError):
        fe5.build_ieee_k4_external_provenance(
            *source, retrieved_at_utc=_NOW_TEXT,
            governance=fe5.build_ieee_k4_freshness_policy(),
            freshness_policy=fe5.build_ieee_k4_freshness_policy(),
        )


def test_public_gate_signature_has_no_caller_controlled_time_argument():
    parameters = inspect.signature(fe5.run_fe5_external_admission_gate).parameters
    assert set(parameters) == {
        "k1_candidate", "k2b_candidate", "k4_candidate",
        "candidate_repository_commit_sha", "candidate_repository_tree_sha",
        "environment_identity", "retained_evidence_refs", "decision_record_refs",
    }
    assert not any("time" in name or "now" in name for name in parameters)


def test_gate_passes_fresh_current_and_stale_legacy_with_nine_exact_refs(monkeypatch):
    candidates = (_candidate("satori_dhcp", 0), _candidate("p0f3_legacy_tcp", 1),
                  _candidate("ieee_ra_mac", 0))
    result = _run(monkeypatch, *candidates)
    manifest = result.gate_result_manifest.semantic_payload
    assert manifest["status"] == "PASS"
    assert manifest["gate_id"] == "F-E5"
    assert manifest["gate_contract_version"] == "R14-F-E5-v1"
    assert len(manifest["input_artifact_refs"]) == len(manifest["output_artifact_refs"]) == 9
    assert manifest["input_artifact_refs"] == manifest["output_artifact_refs"]
    assert [row["freshness_state"] for row in result.per_source] == ["fresh", "stale", "fresh"]
    assert not result.failure_reasons


def test_gate_all_stale_is_usable(monkeypatch):
    result = _run(monkeypatch, _candidate("satori_dhcp", 31536000001),
                  _candidate("p0f3_legacy_tcp", 1),
                  _candidate("ieee_ra_mac", 172800001))
    assert result.gate_result_manifest.semantic_payload["status"] == "PASS"
    assert [row["freshness_state"] for row in result.per_source] == ["stale"] * 3


def test_gate_cannot_pass_with_fewer_than_nine_distinct_candidate_artifacts(monkeypatch):
    shared_governance = _governance("shared")
    result = _run(monkeypatch,
                  _candidate("satori_dhcp", 0, governance=shared_governance),
                  _candidate("p0f3_legacy_tcp", 1, governance=shared_governance),
                  _candidate("ieee_ra_mac", 0, governance=shared_governance))
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []
    assert "candidate_artifact_refs_not_nine_distinct" in result.failure_reasons


@pytest.mark.parametrize("family", list(_SPEC))
def test_gate_negative_age_is_fail_manifest(monkeypatch, family):
    ages = {name: 0 for name in _SPEC}
    ages[family] = -1
    result = _run(monkeypatch, *(_candidate(name, age) for name, age in ages.items()))
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []
    assert any("negative_knowledge_age" in reason for reason in result.failure_reasons)


@pytest.mark.parametrize("family,expired_age", [
    ("satori_dhcp", 63072000001), ("ieee_ra_mac", 604800001),
])
def test_gate_expired_mandatory_source_is_fail_manifest(monkeypatch, family, expired_age):
    ages = {name: 0 for name in _SPEC}
    ages[family] = expired_age
    result = _run(monkeypatch, *(_candidate(name, age) for name, age in ages.items()))
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []


def test_gate_governance_rejection_and_provenance_ref_mismatch_fail(monkeypatch):
    bad_governance = _governance("satori_dhcp").semantic_payload
    bad_governance.update(modification_import_status="NOT_ADMITTED",
                          redistribution_status="UNKNOWN_NOT_ADMITTED")
    rejected = _candidate("satori_dhcp", 0,
                          governance=make_source_governance_record(bad_governance))
    normal = (_candidate("p0f3_legacy_tcp", 1), _candidate("ieee_ra_mac", 0))
    result = _run(monkeypatch, rejected, *normal)
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert any("governance_not_admitted" in reason for reason in result.failure_reasons)
    first = _candidate("satori_dhcp", 0)
    wrong_provenance = make_external_knowledge_provenance_manifest({
        **first.provenance.semantic_payload,
        "source_governance_record": _ref(_governance("other")),
    })
    mismatched = fe5.ExternalKnowledgeCandidate(
        first.knowledge_slot, first.source_family_id, first.source_character,
        first.claim_caveat, first.governance, first.freshness_policy, wrong_provenance,
    )
    result = _run(monkeypatch, mismatched, *normal)
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert any("provenance_reference_mismatch" in reason for reason in result.failure_reasons)
    wrong_freshness = make_external_knowledge_provenance_manifest({
        **first.provenance.semantic_payload,
        "knowledge_freshness_policy": _ref(fe5.build_ieee_k4_freshness_policy()),
    })
    mismatched = fe5.ExternalKnowledgeCandidate(
        first.knowledge_slot, first.source_family_id, first.source_character,
        first.claim_caveat, first.governance, first.freshness_policy, wrong_freshness,
    )
    result = _run(monkeypatch, mismatched, *normal)
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert any("provenance_reference_mismatch" in reason for reason in result.failure_reasons)


@pytest.mark.parametrize("mode", ["missing", "duplicate", "extra", "wrong_slot", "wrong_character", "wrong_caveat"])
def test_gate_exact_source_set_and_candidate_semantics_fail_machine_readably(monkeypatch, mode):
    k1 = _candidate("satori_dhcp", 0)
    k2b = _candidate("p0f3_legacy_tcp", 1)
    k4 = _candidate("ieee_ra_mac", 0)
    if mode == "missing":
        k4 = None
    elif mode == "duplicate":
        k4 = k1
    elif mode == "extra":
        k4 = fe5.ExternalKnowledgeCandidate(
            k4.knowledge_slot, "unexpected_source", k4.source_character,
            k4.claim_caveat, k4.governance, k4.freshness_policy, k4.provenance,
        )
    elif mode == "wrong_slot":
        k4 = fe5.ExternalKnowledgeCandidate(
            "K1", k4.source_family_id, k4.source_character, k4.claim_caveat,
            k4.governance, k4.freshness_policy, k4.provenance,
        )
    elif mode == "wrong_character":
        k4 = fe5.ExternalKnowledgeCandidate(
            k4.knowledge_slot, k4.source_family_id, "legacy", k4.claim_caveat,
            k4.governance, k4.freshness_policy, k4.provenance,
        )
    else:
        k4 = fe5.ExternalKnowledgeCandidate(
            k4.knowledge_slot, k4.source_family_id, k4.source_character,
            "manufacturer inferred", k4.governance, k4.freshness_policy, k4.provenance,
        )
    result = _run(monkeypatch, k1, k2b, k4)
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []


@pytest.mark.parametrize("evidence,decisions", [([], (_DECISION,)), (_EVIDENCE, ())])
def test_gate_pass_requires_retained_evidence_and_owner_decision(monkeypatch, evidence, decisions):
    result = _run(monkeypatch, _candidate("satori_dhcp", 0),
                  _candidate("p0f3_legacy_tcp", 1), _candidate("ieee_ra_mac", 0),
                  evidence=evidence, decisions=decisions)
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []
