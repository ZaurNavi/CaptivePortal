"""Synthetic F-E7 proofs; no external corpus or Owner decision is created."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from inspect import signature

import pytest

from app.device_fingerprint.artifact_content import ArtifactContent, ArtifactRef, make_artifact_content
from app.device_fingerprint.fe5_external_knowledge import (
    build_ieee_k4_freshness_policy, build_p0f_k2b_freshness_policy,
    build_satori_k1_freshness_policy,
)
import app.device_fingerprint.fe7_knowledge_bundle as fe7
from app.device_fingerprint.fe7_knowledge_bundle import run_fe7_knowledge_bundle_gate
from app.device_fingerprint.k2a_conformance_artifacts import make_source_governance_record
from app.device_fingerprint.k2b_p0f_import import _parse_verified_source
from app.device_fingerprint.k3_portal_rules import (
    build_k3_internal_provenance, build_k3_portal_rule_set_v1,
)
from app.device_fingerprint.knowledge_artifacts import (
    make_canonical_k1_record_set, make_canonical_k2b_record_set,
    make_canonical_k4_record_set, make_external_knowledge_provenance_manifest,
    make_knowledge_freshness_policy,
)
from app.device_fingerprint.knowledge_bundle import (
    KnowledgeBundleCandidate, build_initial_knowledge_bundle_v1,
    make_knowledge_bundle, validate_knowledge_bundle_dependencies,
)
from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.taxonomy_artifacts import (
    build_alias_mapping_v1, build_classification_taxonomy_v1,
)
from research.device_fingerprint_fe1.fixtures import build_k1_fixture_definitions

_TIME = "2026-09-22T22:30:34.464Z"
_DECISION = "22222222-2222-4222-8222-222222222222"  # Synthetic UUIDv4 only.
_EVIDENCE = [{"evidence_label": "synthetic-fe7-build", "file_sha256": "e" * 64,
              "media_type": "application/json", "path_or_reference": "test://fe7"}]
_COMMIT = "ce948017cde0b82a778bd07cc9dffe72189aa0bb"
_TREE = "5464f749fa119132071fa25d6dc50ea57a3aa840"


def _ref(content: ArtifactContent) -> dict[str, str]:
    return ArtifactRef(content.artifact_id, content.content_sha256).as_dict()


def _governance(slot: str) -> ArtifactContent:
    return make_source_governance_record({
        "governance_contract_version": 1,
        "source_name": f"synthetic {slot}",
        "source_provenance": "synthetic retained fixture",
        "license_identifier": "test-only", "license_source_reference": "test-only",
        "license_text_sha256": None, "local_storage_status": "STORED_LOCAL",
        "modification_import_status": "IMPORTED_NORMALIZED",
        "redistribution_status": "ALLOWED", "attribution_requirement": "NOT_REQUIRED",
        "commercial_use_status": "ALLOWED", "review_basis_semantics": "test-only",
        "unresolved_restrictions": [],
    })


def _provenance(slot: str, governance: ArtifactContent, policy: ArtifactContent,
                retrieved: str) -> ArtifactContent:
    return make_external_knowledge_provenance_manifest({
        "provenance_contract_version": 1, "provenance_kind": "external",
        "source_artifact_sha256": {"k1": "a", "k2b": "b", "k4": "c"}[slot] * 64,
        "source_governance_record": _ref(governance),
        "retrieved_at_utc": retrieved,
        "source_provider_version_metadata": f"synthetic-{slot}",
        "knowledge_freshness_policy": _ref(policy),
        "importer_identity": "synthetic-importer", "importer_version": "1",
    })


def _record_set(slot: str, provenance: ArtifactContent) -> ArtifactContent:
    if slot == "k1":
        payload = build_k1_fixture_definitions()["all_any"]["record_set"].semantic_payload
        payload["knowledge_provenance"] = _ref(provenance)
        return make_canonical_k1_record_set(payload)
    if slot == "k2b":
        raw = b"[tcp:request]\nlabel = s:unix:Linux:fixture\nsig = 4:64:0:0:65535,0:::0\n"
        payload = _parse_verified_source(raw, _ref(provenance), "d" * 64).record_set.semantic_payload
        return make_canonical_k2b_record_set(payload)
    return make_canonical_k4_record_set({
        "record_set_contract_version": 1, "knowledge_slot": "K4",
        "knowledge_provenance": _ref(provenance),
        "records": [{
            "record_type": "K4_IEEE_ASSIGNMENT", "canonical_record_id": "synthetic-k4",
            "prefix_hex": "001122", "prefix_length_bits": 24,
            "assignment_org_id": "synthetic-org", "assignment_org_label": "Synthetic Org",
            "registry_family": "MA-L", "source_record_identity": "synthetic-source",
            "manufacturer_mapping": None,
        }],
    })


def candidate() -> KnowledgeBundleCandidate:
    taxonomy = build_classification_taxonomy_v1()
    aliases = build_alias_mapping_v1()
    policies = {
        "k1": build_satori_k1_freshness_policy(),
        "k2b": build_p0f_k2b_freshness_policy(),
        "k4": build_ieee_k4_freshness_policy(),
    }
    governance = {slot: _governance(slot) for slot in ("k1", "k2b", "k4")}
    provenance = {
        slot: _provenance(slot, governance[slot], policies[slot],
                          "2026-09-22T22:30:34.463Z" if slot == "k2b" else _TIME)
        for slot in ("k1", "k2b", "k4")
    }
    k3_rules = build_k3_portal_rule_set_v1()
    k3_provenance = build_k3_internal_provenance(
        k3_rules, repository_commit_sha=_COMMIT, repository_tree_sha=_TREE,
        taxonomy_compatibility=_ref(taxonomy),
    )
    return KnowledgeBundleCandidate(
        taxonomy, aliases,
        _record_set("k1", provenance["k1"]), provenance["k1"], governance["k1"], policies["k1"],
        _record_set("k2b", provenance["k2b"]), provenance["k2b"], governance["k2b"], policies["k2b"],
        k3_rules, k3_provenance,
        _record_set("k4", provenance["k4"]), provenance["k4"], governance["k4"], policies["k4"],
    )


def _gate_kwargs(**changes):
    kwargs = {
        "foundation_knowledge_evaluation_at_utc": _TIME,
        "candidate_repository_commit_sha": "a" * 40,
        "candidate_repository_tree_sha": "b" * 40,
        "environment_identity": "synthetic-fe7",
        "retained_evidence_refs": _EVIDENCE,
        "decision_record_refs": [_DECISION],
    }
    kwargs.update(changes)
    return kwargs


def _gate(value: KnowledgeBundleCandidate, **changes):
    return run_fe7_knowledge_bundle_gate(value, **_gate_kwargs(**changes))


def _rebuilt_record_set(value: KnowledgeBundleCandidate, slot: str,
                        provenance: ArtifactContent) -> KnowledgeBundleCandidate:
    old = getattr(value, f"{slot}_record_set")
    payload = old.semantic_payload
    payload["knowledge_provenance"] = _ref(provenance)
    builder = {"k1": make_canonical_k1_record_set,
               "k2b": make_canonical_k2b_record_set,
               "k4": make_canonical_k4_record_set}[slot]
    return replace(value, **{f"{slot}_provenance": provenance,
                             f"{slot}_record_set": builder(payload)})


def test_exact_schema_rejects_missing_extra_wrong_type_ja4_and_nonpositive_version():
    payload = build_initial_knowledge_bundle_v1(candidate()).semantic_payload
    assert set(payload) == {
        "bundle_schema_version", "classification_taxonomy", "alias_mapping",
        "knowledge_provenance_manifests", "source_governance_records",
        "knowledge_freshness_policies", "k1_record_set", "k2b_record_set",
        "k3_portal_rule_set", "k4_record_set",
    }
    for mutation in (
        lambda p: p.pop("alias_mapping"),
        lambda p: p.update(extra="forbidden"),
        lambda p: p.update(ja4_record_set=p["k1_record_set"]),
        lambda p: p.update(tls_knowledge=p["k1_record_set"]),
        lambda p: p.update(quic_knowledge=p["k1_record_set"]),
        lambda p: p.update(bundle_schema_version=0),
        lambda p: p.update(bundle_schema_version=True),
        lambda p: p.update(classification_taxonomy=p["alias_mapping"]),
        lambda p: p.update(k3_portal_rule_set=p["k1_record_set"]),
        lambda p: p.update(alias_mapping={"artifact_id": p["alias_mapping"]["artifact_id"]}),
    ):
        invalid = deepcopy(payload)
        mutation(invalid)
        with pytest.raises(DeviceFingerprintValidationError):
            make_knowledge_bundle(invalid)


def test_canonical_reference_sets_are_exact_and_permutation_invariant():
    value = candidate()
    bundle = build_initial_knowledge_bundle_v1(value)
    payload = bundle.semantic_payload
    assert len(payload["knowledge_provenance_manifests"]) == 4
    assert len(payload["source_governance_records"]) == 3
    assert len(payload["knowledge_freshness_policies"]) == 3
    assert payload["source_governance_records"] == sorted(
        payload["source_governance_records"], key=lambda ref: ref["artifact_id"],
    )
    for key in ("knowledge_provenance_manifests", "source_governance_records",
                "knowledge_freshness_policies"):
        permuted = deepcopy(payload)
        permuted[key].reverse()
        assert make_knowledge_bundle(permuted).artifact_id == bundle.artifact_id
        duplicate = deepcopy(payload)
        duplicate[key].append(deepcopy(duplicate[key][0]))
        with pytest.raises(DeviceFingerprintValidationError):
            make_knowledge_bundle(duplicate)
    assert validate_knowledge_bundle_dependencies(bundle, value)
    assert bundle.artifact_id == build_initial_knowledge_bundle_v1(value).artifact_id
    assert bundle.content_sha256 == build_initial_knowledge_bundle_v1(value).content_sha256
    assert bundle.semantic_payload_json == build_initial_knowledge_bundle_v1(value).semantic_payload_json
    assert "ja4" not in bundle.semantic_payload_json.decode().lower()
    assert not any(term in bundle.semantic_payload_json.decode().lower() for term in
                   ("source_path", "source_url", "satori xml", "p0f text", "ieee csv"))


@pytest.mark.parametrize("inventory", [
    "knowledge_provenance_manifests", "source_governance_records", "knowledge_freshness_policies",
])
@pytest.mark.parametrize("change", ["missing", "extra"])
def test_missing_or_extra_transitive_inventory_fails(inventory, change):
    value = candidate()
    payload = build_initial_knowledge_bundle_v1(value).semantic_payload
    if change == "missing":
        payload[inventory].pop()
    else:
        kind = {
            "knowledge_provenance_manifests": "KnowledgeProvenanceManifest",
            "source_governance_records": "SourceGovernanceRecord",
            "knowledge_freshness_policies": "KnowledgeFreshnessPolicy",
        }[inventory]
        digest = "f" * 64
        payload[inventory].append(ArtifactRef(f"{kind}:v1:sha256:{digest}", digest).as_dict())
    with pytest.raises(DeviceFingerprintValidationError):
        validate_knowledge_bundle_dependencies(make_knowledge_bundle(payload), value)


@pytest.mark.parametrize("slot", ["k1", "k2b", "k4"])
def test_record_set_must_resolve_its_exact_external_provenance(slot):
    value = candidate()
    altered = getattr(value, f"{slot}_record_set").semantic_payload
    altered["knowledge_provenance"] = _ref(value.k3_provenance)
    builder = {"k1": make_canonical_k1_record_set,
               "k2b": make_canonical_k2b_record_set,
               "k4": make_canonical_k4_record_set}[slot]
    bad = replace(value, **{f"{slot}_record_set": builder(altered)})
    with pytest.raises(DeviceFingerprintValidationError):
        validate_knowledge_bundle_dependencies(build_initial_knowledge_bundle_v1(bad), bad)


@pytest.mark.parametrize("slot", ["k1", "k2b", "k4"])
def test_external_governance_and_freshness_refs_must_resolve_exactly(slot):
    value = candidate()
    for field in ("source_governance_record", "knowledge_freshness_policy"):
        payload = getattr(value, f"{slot}_provenance").semantic_payload
        other = "k4" if slot != "k4" else "k1"
        payload[field] = _ref(getattr(
            value, f"{other}_{'governance' if field == 'source_governance_record' else 'freshness_policy'}",
        ))
        wrong = make_external_knowledge_provenance_manifest(payload)
        bad = _rebuilt_record_set(value, slot, wrong)
        with pytest.raises(DeviceFingerprintValidationError):
            validate_knowledge_bundle_dependencies(build_initial_knowledge_bundle_v1(bad), bad)


def test_k3_internal_provenance_rule_and_taxonomy_links_are_exact():
    value = candidate()
    payload = value.k3_provenance.semantic_payload
    payload["taxonomy_compatibility"] = _ref(value.alias_mapping)
    from app.device_fingerprint.knowledge_artifacts import make_internal_knowledge_provenance_manifest
    with pytest.raises(DeviceFingerprintValidationError):
        make_internal_knowledge_provenance_manifest(payload)
    payload = value.k3_provenance.semantic_payload
    payload["rule_set_artifact"] = _ref(value.k1_record_set)
    wrong = make_internal_knowledge_provenance_manifest(payload)
    bad = replace(value, k3_provenance=wrong)
    with pytest.raises(DeviceFingerprintValidationError):
        validate_knowledge_bundle_dependencies(build_initial_knowledge_bundle_v1(bad), bad)
    payload = value.k3_provenance.semantic_payload
    payload["taxonomy_compatibility"] = _ref(make_artifact_content(
        "ClassificationTaxonomy", value.classification_taxonomy.semantic_payload | {"extra": "bad"},
    ))
    wrong = make_internal_knowledge_provenance_manifest(payload)
    bad = replace(value, k3_provenance=wrong)
    with pytest.raises(DeviceFingerprintValidationError):
        validate_knowledge_bundle_dependencies(build_initial_knowledge_bundle_v1(bad), bad)


def test_k3_provenance_allows_other_repository_identity_when_links_resolve():
    value = candidate()
    alternate = build_k3_internal_provenance(
        value.k3_portal_rule_set,
        repository_commit_sha="a" * 40,
        repository_tree_sha="b" * 40,
        taxonomy_compatibility=_ref(value.classification_taxonomy),
    )
    changed = replace(value, k3_provenance=alternate)
    bundle = build_initial_knowledge_bundle_v1(changed)
    assert validate_knowledge_bundle_dependencies(bundle, changed)
    result = _gate(changed)
    assert result.gate_result_manifest.semantic_payload["status"] == "PASS"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == [_ref(bundle)]


@pytest.mark.parametrize("slot", ["k1", "k2b", "k4"])
def test_empty_mandatory_record_slots_fail(slot):
    value = candidate()
    payload = getattr(value, f"{slot}_record_set").semantic_payload
    payload["records"] = []
    builder = {"k1": make_canonical_k1_record_set,
               "k2b": make_canonical_k2b_record_set,
               "k4": make_canonical_k4_record_set}[slot]
    bad = replace(value, **{f"{slot}_record_set": builder(payload)})
    result = _gate(bad)
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []


@pytest.mark.parametrize("field", ["rules", "test_vectors"])
def test_empty_k3_mandatory_structure_fails(field):
    value = candidate()
    payload = value.k3_portal_rule_set.semantic_payload
    payload[field] = []
    bad = replace(value, k3_portal_rule_set=make_artifact_content("K3PortalRuleSet", payload))
    assert _gate(bad).gate_result_manifest.semantic_payload["status"] == "FAIL"


@pytest.mark.parametrize("slot", ["k1", "k2b", "k3", "k4"])
def test_missing_mandatory_slot_returns_fail_manifest(slot):
    value = candidate()
    field = "k3_provenance" if slot == "k3" else f"{slot}_record_set"
    result = _gate(replace(value, **{field: None}))
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []


def test_wrong_record_slot_returns_fail_manifest():
    value = candidate()
    payload = value.k1_record_set.semantic_payload
    payload["knowledge_slot"] = "K2B"
    result = _gate(replace(value, k1_record_set=make_artifact_content(
        "CanonicalKnowledgeRecordSet", payload,
    )))
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []


def test_gate_pass_has_sixteen_inputs_one_output_and_inherited_time():
    value = candidate()
    result = _gate(value)
    manifest = result.gate_result_manifest.semantic_payload
    assert manifest["status"] == "PASS", result.failure_reasons
    assert result.dependency_validation_passed
    assert len(manifest["input_artifact_refs"]) == 16
    assert len(manifest["output_artifact_refs"]) == 1
    assert manifest["output_artifact_refs"][0]["artifact_id"] == result.knowledge_bundle_artifact_id
    assert result.build_1_artifact_id == result.build_2_artifact_id
    assert result.build_1_content_sha256 == result.build_2_content_sha256
    assert [(row["slot"], row["freshness_state"], row["claim_eligible"])
            for row in result.per_source] == [
        ("k1", "fresh", True), ("k2b", "stale", True), ("k4", "fresh", True),
    ]
    assert result.per_source[1]["claim_strength_cap"] == "supporting"
    assert manifest["trusted_time_inputs"] == {
        "foundation_knowledge_evaluation_at_utc": _TIME,
        "foundation_admission_evaluation_at_utc": None,
        "knowledge_evaluation_at_utc": None,
    }


def test_gate_rejects_nonidentical_independent_double_build(monkeypatch):
    import app.device_fingerprint.fe7_knowledge_bundle as fe7

    original = fe7.build_initial_knowledge_bundle_v1
    calls = []

    def differing_second_build(value):
        artifact = original(value)
        calls.append(True)
        if len(calls) == 2:
            payload = artifact.semantic_payload
            payload["bundle_schema_version"] = 2
            return make_knowledge_bundle(payload)
        return artifact

    monkeypatch.setattr(fe7, "build_initial_knowledge_bundle_v1", differing_second_build)
    result = _gate(candidate())
    assert calls == [True, True]
    assert "double_build_identity_mismatch" in result.failure_reasons
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []


@pytest.mark.parametrize("mode", ["expired", "negative", "ineligible"])
def test_gate_unusable_source_is_fail_with_no_output(mode):
    value = candidate()
    if mode == "expired":
        retrieved = "2010-01-01T00:00:00.000Z"
    elif mode == "negative":
        retrieved = "2026-09-22T22:30:34.465Z"
    else:
        retrieved = _TIME
    policy = value.k1_freshness_policy
    if mode == "ineligible":
        payload = policy.semantic_payload
        fresh = next(row for row in payload["freshness_state_rules"] if row["freshness_state"] == "fresh")
        fresh.update(claim_eligible=False, claim_strength_cap="NONE",
                     required_explanation_code="synthetic_ineligible")
        policy = make_knowledge_freshness_policy(payload)
    provenance = _provenance("k1", value.k1_governance, policy, retrieved)
    bad = _rebuilt_record_set(replace(value, k1_freshness_policy=policy), "k1", provenance)
    result = _gate(bad)
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []
    assert "k1_knowledge_not_usable" in result.failure_reasons


@pytest.mark.parametrize("evidence,decisions", [([], [_DECISION]), (_EVIDENCE, [])])
def test_gate_requires_retained_evidence_and_owner_decision(evidence, decisions):
    result = _gate(candidate(), retained_evidence_refs=evidence, decision_record_refs=decisions)
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []


def test_public_gate_has_no_initial_admission_bypass():
    assert "initial_admission" not in signature(run_fe7_knowledge_bundle_gate).parameters
    with pytest.raises(TypeError):
        run_fe7_knowledge_bundle_gate(candidate(), **_gate_kwargs(initial_admission=False))


def test_supplied_prerequisite_time_is_used_without_historical_pin():
    supplied_time = "2026-09-23T00:00:00.000Z"
    result = _gate(candidate(), foundation_knowledge_evaluation_at_utc=supplied_time)
    manifest = result.gate_result_manifest.semantic_payload
    assert manifest["status"] == "PASS", result.failure_reasons
    assert manifest["trusted_time_inputs"]["foundation_knowledge_evaluation_at_utc"] == supplied_time
    assert len(manifest["input_artifact_refs"]) == 16
