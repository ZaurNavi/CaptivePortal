"""R14 pure cross-origin fusion and ClassificationResult regression matrix."""

from __future__ import annotations

import ast
import inspect
from dataclasses import replace

import pytest

from app.device_fingerprint.artifact_content import make_artifact_content
from app.device_fingerprint.classification_policy import build_initial_classification_policy_v1
import app.device_fingerprint.fusion as fusion_module
from app.device_fingerprint.fusion import (
    DeviceFingerprintFusionCore, FusionInputs, _fusion_cell, _validate_dimension_result,
    _first_rule, fuse_classification,
)
from app.device_fingerprint.knowledge_artifacts import make_canonical_k1_record_set
from app.device_fingerprint.knowledge_bundle import build_initial_knowledge_bundle_v1
from app.device_fingerprint.taxonomy_artifacts import make_classification_taxonomy
from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.origin_assessment import (
    DeviceFingerprintOriginAssessmentBuilder, _reduce_claims, make_origin_assessment,
)
from tests.device_fingerprint_task04_t03.test_origin_assessment import (
    _dhcp_row, _inputs, _portal_row, _r2_k1_no_match_inputs,
)
from tests.device_fingerprint_task04_t03.test_origin_assessment import _network_row
from tests.device_fingerprint.test_network_schemas import tcp_v2
from app.device_fingerprint.validation import canonical_json, canonical_sha256
from research.device_fingerprint_fe1.fixtures import build_k1_fixture_definitions


def _base_from_source(source):
    policy = build_initial_classification_policy_v1(
        source.knowledge.classification_taxonomy, source.knowledge.alias_mapping,
        source.evidence_adapter_contract_set)
    return FusionInputs(
        classification_request_digest="a" * 64,
        classification_policy=policy,
        classification_taxonomy=source.knowledge.classification_taxonomy,
        alias_mapping=source.knowledge.alias_mapping,
        evidence_adapter_contract_set=source.evidence_adapter_contract_set,
        knowledge_bundle=source.knowledge_bundle,
        knowledge=source.knowledge,
        classifier_artifact_manifest=make_artifact_content("ClassifierArtifactManifest", {"synthetic": True}),
        evidence_snapshot_content=source.evidence_snapshot_content,
        source_evaluability=source.source_evaluability,
        origin_assessments=DeviceFingerprintOriginAssessmentBuilder(source).build_all(),
    )


@pytest.fixture(scope="module")
def baseline():
    return _base_from_source(_inputs())


def _candidate(value: str, strength: str = "strong", *, outside: bool = False,
               derivation: str = "fingerprint_match") -> dict:
    return {
        "candidate_kind": "OUT_OF_SCOPE_TAXON" if outside else "CANONICAL_VALUE",
        "candidate_value_id": None if outside else value,
        "out_of_scope_taxon_ref": value if outside else None,
        "claim_strength": strength, "claim_derivation": derivation,
        "knowledge_refs": [], "evidence_refs": [],
    }


def _change(base: FusionInputs, origin: str, dimension: str, *, candidates=(),
            explanation=(), broad=(), state: str | None = None) -> FusionInputs:
    """Reconstruct a canonical synthetic T-03 output, never bypass its validator."""
    updated = []
    for artifact in base.origin_assessments:
        if artifact.semantic_payload["origin_group"] != origin:
            updated.append(artifact)
            continue
        payload = artifact.semantic_payload
        for index, row in enumerate(payload["dimension_assessments"]):
            if row["dimension_name"] != dimension:
                continue
            if candidates or state == "no_claim" or broad:
                new = _reduce_claims(dimension, list(candidates), broad=list(broad),
                                     explanations=list(explanation), k1_ambiguous=origin == "dhcp",
                                     evaluated_evidence_refs=row["evidence_refs"] if state == "no_claim" else [])
            else:
                new = {**row, "explanation_codes": sorted(set(explanation)),
                       "broad_unresolved_taxon_refs": list(broad)}
                if state is not None:
                    new["internal_state"] = state
            payload["dimension_assessments"][index] = new
            break
        updated.append(make_origin_assessment(
            payload, evidence_snapshot_content=base.evidence_snapshot_content,
            source_evaluability=base.source_evaluability,
            evidence_adapter_contract_set=base.evidence_adapter_contract_set,
            knowledge_bundle=base.knowledge_bundle, knowledge=base.knowledge))
    return replace(base, origin_assessments=tuple(updated))


def _platform(inputs: FusionInputs) -> dict:
    return fuse_classification(inputs).semantic_payload["platform_result"]


@pytest.mark.parametrize("malformed", [False, True])
def test_public_fusion_entry_points_reject_invalid_knowledge_closure(baseline, malformed):
    if malformed:
        bad = replace(baseline, knowledge_bundle=make_artifact_content("KnowledgeBundle", {"extra": True}))
    else:
        bad = replace(baseline, knowledge=replace(baseline.knowledge, k1_record_set=baseline.knowledge.k4_record_set))
    with pytest.raises(DeviceFingerprintValidationError):
        fuse_classification(bad)
    with pytest.raises(DeviceFingerprintValidationError):
        DeviceFingerprintFusionCore(bad)


def test_public_fusion_validates_knowledge_once_including_six_origin_rebuilds(baseline, monkeypatch):
    import app.device_fingerprint.knowledge_bundle as module
    calls = []
    original = module.validate_knowledge_bundle_dependencies
    def counted(bundle, candidate):
        calls.append((bundle, candidate))
        return original(bundle, candidate)
    monkeypatch.setattr(module, "validate_knowledge_bundle_dependencies", counted)
    first = fuse_classification(baseline)
    assert len(calls) == 1
    core = DeviceFingerprintFusionCore(baseline)
    assert core.fuse() == first and core.fuse() == first
    assert len(calls) == 2


def test_exact_six_origins_permutation_and_stable_result(baseline):
    first = fuse_classification(baseline)
    reverse = fuse_classification(replace(baseline, origin_assessments=tuple(reversed(baseline.origin_assessments))))
    assert first == reverse == DeviceFingerprintFusionCore(baseline).fuse()
    assert first.artifact_type == "ClassificationResult"
    assert len(first.semantic_payload["origin_assessments"]) == 6


@pytest.mark.parametrize("mutation", [
    lambda b: replace(b, origin_assessments=b.origin_assessments[:-1]),
    lambda b: replace(b, origin_assessments=b.origin_assessments[:-1] + (b.origin_assessments[0],)),
    lambda b: replace(b, origin_assessments=b.origin_assessments + (b.origin_assessments[0],)),
    lambda b: replace(b, classification_request_digest="A" * 64),
    lambda b: replace(b, classifier_artifact_manifest=b.classification_policy),
    lambda b: replace(b, classification_taxonomy=b.alias_mapping),
    lambda b: replace(b, alias_mapping=b.classification_taxonomy),
    lambda b: replace(b, evidence_adapter_contract_set=b.classification_taxonomy),
    lambda b: replace(b, knowledge_bundle=b.classification_policy),
    lambda b: replace(b, origin_assessments=(b.classification_policy, *b.origin_assessments[1:])),
])
def test_malformed_lineage_rejected_with_typed_error(baseline, mutation):
    with pytest.raises(DeviceFingerprintValidationError):
        DeviceFingerprintFusionCore(mutation(baseline))


def test_origin_snapshot_evaluability_and_noncanonical_mismatch_rejected(baseline):
    artifact = baseline.origin_assessments[0]
    for field, reference in (
        ("evidence_snapshot_content", baseline.source_evaluability),
        ("source_evaluability", baseline.evidence_snapshot_content),
    ):
        payload = artifact.semantic_payload
        payload[field] = {"artifact_id": reference.artifact_id,
                          "content_sha256": reference.content_sha256}
        changed = make_artifact_content("OriginAssessment", payload)
        with pytest.raises(DeviceFingerprintValidationError):
            DeviceFingerprintFusionCore(replace(
                baseline, origin_assessments=(changed, *baseline.origin_assessments[1:])))
    payload = artifact.semantic_payload
    payload["dimension_assessments"].reverse()
    changed = make_artifact_content("OriginAssessment", payload)
    with pytest.raises(DeviceFingerprintValidationError):
        DeviceFingerprintFusionCore(replace(
            baseline, origin_assessments=(changed, *baseline.origin_assessments[1:])))


def test_valid_policy_taxonomy_must_equal_valid_knowledge_bundle_taxonomy(baseline):
    taxonomy_payload = baseline.classification_taxonomy.semantic_payload
    taxonomy_payload["manufacturer_records"].append({
        "manufacturer_id": "synthetic-vendor", "display_label": "Synthetic Vendor",
    })
    alternate_taxonomy = make_classification_taxonomy(taxonomy_payload)
    alternate_policy = build_initial_classification_policy_v1(
        alternate_taxonomy, baseline.alias_mapping, baseline.evidence_adapter_contract_set)
    with pytest.raises(DeviceFingerprintValidationError, match="KnowledgeBundle/ClassificationPolicy"):
        DeviceFingerprintFusionCore(replace(
            baseline, classification_policy=alternate_policy,
            classification_taxonomy=alternate_taxonomy))


def test_all_forty_policy_cells_are_looked_up_without_alternate_matrix(baseline):
    payload = baseline.classification_policy.semantic_payload
    rows = payload["cross_origin_fusion_matrix"]
    assert len(rows) == 40
    keys = (
        "strong_clean_present", "strong_clean_disagree", "strong_internal_conflict_present",
        "supporting_clean_present", "supporting_clean_disagree",
        "supporting_internal_conflict_present",
        "supporting_vs_selected_strong_incompatible_present",
    )
    for row in rows:
        assert _fusion_cell(payload, tuple(row[key] for key in keys)) == row
    with pytest.raises(DeviceFingerprintValidationError):
        _fusion_cell(payload, (False, True, False, False, False, False, False))
    with pytest.raises(DeviceFingerprintValidationError):
        _fusion_cell(payload, (0,) * 7)


def test_strong_selection_and_independent_high_support(baseline):
    one = _change(baseline, "dhcp", "platform_family", candidates=[_candidate("android")])
    assert (_platform(one)["status"], _platform(one)["support_level"]) == ("resolved", "medium")
    two = _change(one, "portal", "platform_family", candidates=[_candidate("android")])
    assert (_platform(two)["status"], _platform(two)["support_level"]) == ("resolved", "high")
    assert _platform(two)["supporting_origin_groups"] == ["dhcp", "portal"]
    assert fuse_classification(two).semantic_payload["global_classification_status"] == "partial"


def test_derivation_never_changes_outcome(baseline):
    outputs = []
    for derivation in ("declared", "deterministic_mapping", "fingerprint_match", "registry_mapping"):
        changed = _change(baseline, "portal", "platform_family",
                          candidates=[_candidate("android", derivation=derivation)])
        outputs.append((_platform(changed)["status"], _platform(changed)["support_level"]))
    assert outputs == [("resolved", "medium")] * 4


def test_strong_disagreement_and_strong_internal_conflict(baseline):
    first = _change(baseline, "portal", "platform_family", candidates=[_candidate("android")])
    disagree = _change(first, "tcp", "platform_family", candidates=[_candidate("ios")])
    assert _platform(disagree)["status"] == "conflicting_evidence"
    assert _platform(disagree)["contradicting_origin_groups"] == ["portal", "tcp"]
    conflict = _change(first, "tcp", "platform_family",
                       candidates=[_candidate("android"), _candidate("ios")])
    assert _platform(conflict)["status"] == "conflicting_evidence"
    assert "tcp" in _platform(conflict)["contradicting_origin_groups"]


def test_strong_supporting_contradiction_and_cap(baseline):
    first = _change(baseline, "portal", "platform_family", candidates=[_candidate("android")])
    agree = _change(first, "dhcp", "platform_family", candidates=[_candidate("android", "supporting")])
    assert _platform(agree)["support_level"] == "medium"
    disagree = _change(first, "dhcp", "platform_family", candidates=[_candidate("ios", "supporting")])
    result = _platform(disagree)
    assert result["canonical_value_id"] == "android"
    assert result["support_level"] == "medium"
    assert result["contradicting_origin_groups"] == ["dhcp"]
    assert "cross_origin_supporting_contradiction" in result["explanation_codes"]
    two_strong = _change(first, "tcp", "platform_family", candidates=[_candidate("android")])
    capped = _change(two_strong, "dhcp", "platform_family", candidates=[_candidate("ios", "supporting")])
    assert _platform(capped)["support_level"] == "medium"


def test_supporting_internal_conflict_and_same_origin_retention(baseline):
    first = _change(baseline, "portal", "platform_family", candidates=[_candidate("android")])
    conflict = _change(first, "dhcp", "platform_family",
                       candidates=[_candidate("android", "supporting"), _candidate("ios", "supporting")])
    assert (_platform(conflict)["status"], _platform(conflict)["support_level"]) == ("resolved", "medium")
    without_strong = _change(baseline, "dhcp", "platform_family",
                             candidates=[_candidate("android", "supporting"), _candidate("ios", "supporting")])
    assert _platform(without_strong)["status"] == "conflicting_evidence"
    retained = _change(baseline, "portal", "platform_family",
                       candidates=[_candidate("android"), _candidate("ios", "supporting")])
    result = _platform(retained)
    assert result["status"] == "resolved" and result["support_level"] == "medium"
    assert result["supporting_origin_groups"] == ["portal"]
    assert result["contradicting_origin_groups"] == ["portal"]
    two_strong = _change(retained, "tcp", "platform_family", candidates=[_candidate("android")])
    assert _platform(two_strong)["support_level"] == "medium"
    assert "portal" in _platform(two_strong)["contradicting_origin_groups"]
    with_supporting_conflict = _change(
        _change(first, "tcp", "platform_family", candidates=[_candidate("android")]),
        "dhcp", "platform_family",
        candidates=[_candidate("android", "supporting"), _candidate("ios", "supporting")])
    assert _platform(with_supporting_conflict)["support_level"] == "medium"


def test_same_origin_contradiction_is_not_cross_origin_matrix_bit(baseline, monkeypatch):
    retained = _change(baseline, "portal", "platform_family",
                       candidates=[_candidate("android"), _candidate("ios", "supporting")])
    agreeing = _change(retained, "dhcp", "platform_family",
                       candidates=[_candidate("android", "supporting")])
    original_lookup = fusion_module._fusion_cell
    keys = []

    def recording_lookup(policy, bits):
        keys.append(bits)
        return original_lookup(policy, bits)

    monkeypatch.setattr(fusion_module, "_fusion_cell", recording_lookup)
    result = _platform(agreeing)
    assert result["status"] == "resolved" and result["canonical_value_id"] == "android"
    assert result["support_level"] == "medium"
    assert result["supporting_origin_groups"] == ["dhcp", "portal"]
    assert result["contradicting_origin_groups"] == ["portal"]
    assert "same_origin_supporting_contradiction" in result["explanation_codes"]
    assert "cross_origin_supporting_contradiction" not in result["explanation_codes"]
    assert next(bits for bits in keys if bits[0])[-1] is False


def test_true_cross_origin_supporting_contradiction_sets_matrix_bit(baseline, monkeypatch):
    retained = _change(baseline, "portal", "platform_family",
                       candidates=[_candidate("android"), _candidate("ios", "supporting")])
    incompatible = _change(retained, "dhcp", "platform_family",
                           candidates=[_candidate("ios", "supporting")])
    original_lookup = fusion_module._fusion_cell
    keys = []

    def recording_lookup(policy, bits):
        keys.append(bits)
        return original_lookup(policy, bits)

    monkeypatch.setattr(fusion_module, "_fusion_cell", recording_lookup)
    result = _platform(incompatible)
    assert result["canonical_value_id"] == "android" and result["support_level"] == "medium"
    assert result["contradicting_origin_groups"] == ["dhcp", "portal"]
    assert "cross_origin_supporting_contradiction" in result["explanation_codes"]
    assert next(bits for bits in keys if bits[0])[-1] is True


def test_supporting_internal_conflict_uses_its_own_matrix_bit(baseline, monkeypatch):
    strong = _change(baseline, "portal", "platform_family", candidates=[_candidate("android")])
    conflict = _change(strong, "dhcp", "platform_family", candidates=[
        _candidate("android", "supporting"), _candidate("ios", "supporting")])
    original_lookup = fusion_module._fusion_cell
    keys = []

    def recording_lookup(policy, bits):
        keys.append(bits)
        return original_lookup(policy, bits)

    monkeypatch.setattr(fusion_module, "_fusion_cell", recording_lookup)
    result = _platform(conflict)
    assert result["canonical_value_id"] == "android"
    assert result["support_level"] == "medium"
    assert next(bits for bits in keys if bits[0])[5] is True


def test_supporting_agreement_disagreement_and_origin_unit(baseline):
    one = _change(baseline, "portal", "platform_family", candidates=[_candidate("android", "supporting")])
    assert (_platform(one)["status"], _platform(one)["support_level"]) == ("resolved", "low")
    same = _change(one, "dhcp", "platform_family", candidates=[_candidate("android", "supporting")])
    assert _platform(same)["support_level"] == "low"
    different = _change(one, "dhcp", "platform_family", candidates=[_candidate("ios", "supporting")])
    assert _platform(different)["status"] == "conflicting_evidence"
    repeated = _change(baseline, "portal", "platform_family", candidates=[
        _candidate("android", "strong", derivation="declared"),
        _candidate("android", "strong", derivation="fingerprint_match")])
    assert _platform(repeated)["support_level"] == "medium"


def test_one_hundred_portal_rows_remain_one_independent_origin():
    source = _inputs(evidence_rows=[_portal_row(number) for number in range(1, 101)], origin="portal")
    result = _platform(_base_from_source(source))
    assert result["canonical_value_id"] == "android"
    assert result["supporting_origin_groups"] == ["portal"]
    assert result["support_level"] == "low"


@pytest.mark.parametrize("dimension,outside,strength,expected", [
    ("platform_family", "unmapped-platform", "supporting", "low"),
    ("device_class", "unmapped-device", "strong", "medium"),
])
def test_out_of_scope_supported_only_for_frozen_dimensions(baseline, dimension, outside, strength, expected):
    changed = _change(baseline, "portal", dimension,
                      candidates=[_candidate(outside, strength, outside=True)])
    key = "platform_result" if dimension == "platform_family" else "device_class_result"
    result = fuse_classification(changed).semantic_payload[key]
    assert result["status"] == "recognized_out_of_scope"
    assert result["support_level"] == expected
    assert result["out_of_scope_taxon_references"] == [outside]
    assert result["display_label_ref"] is None
    with pytest.raises(DeviceFingerprintValidationError):
        _change(baseline, "portal", "manufacturer_family",
                candidates=[_candidate("outside", outside=True)])


def test_two_independent_strong_out_of_scope_origins_reach_high(baseline):
    one = _change(baseline, "portal", "platform_family",
                  candidates=[_candidate("unmapped-platform", outside=True)])
    two = _change(one, "tcp", "platform_family",
                  candidates=[_candidate("unmapped-platform", outside=True)])
    result = _platform(two)
    assert result["status"] == "recognized_out_of_scope"
    assert result["support_level"] == "high"
    assert result["out_of_scope_taxon_references"] == ["unmapped-platform"]


def test_out_of_scope_reference_set_deduplicates_across_origins(baseline):
    one = _change(baseline, "portal", "platform_family",
                  candidates=[_candidate("unmapped-platform", "supporting", outside=True)])
    two = _change(one, "tcp", "platform_family",
                  candidates=[_candidate("unmapped-platform", "supporting", outside=True)])
    assert _platform(two)["out_of_scope_taxon_references"] == ["unmapped-platform"]


def test_canonical_reference_and_explanation_unions(baseline):
    rule = baseline.knowledge.k3_portal_rule_set.semantic_payload["rules"][0]
    provenance = baseline.knowledge.k3_provenance
    kref = {
        "knowledge_bundle_id": baseline.knowledge_bundle.artifact_id,
        "knowledge_bundle_digest": baseline.knowledge_bundle.content_sha256,
        "canonical_knowledge_record_id": rule["rule_id"],
        "knowledge_provenance_id": provenance.artifact_id,
        "knowledge_provenance_digest": provenance.content_sha256,
        "rule_or_source_record_identity": rule["rule_id"],
    }
    candidate = _candidate("android")
    candidate["knowledge_refs"] = [kref]
    changed = _change(baseline, "portal", "platform_family", candidates=[candidate],
                      explanation=["fixture_reason"])
    changed = _change(changed, "dhcp", "platform_family", explanation=["fixture_reason"])
    result = _platform(changed)
    assert result["knowledge_references"] == [kref]
    assert result["explanation_codes"].count("fixture_reason") == 1
    assert result["supporting_origin_groups"] == ["portal"]


@pytest.mark.parametrize("reason", [
    "unsupported_evidence_contract", "degraded_evidence_no_claim",
    "legacy_tcp_schema_insufficient_for_exact_k2a_contract",
])
def test_unusable_no_claim_is_not_semantic_information(baseline, reason):
    changed = _change(baseline, "tcp", "platform_family", explanation=[reason])
    result = _platform(changed)
    assert result["status"] == "insufficient_evidence"
    assert "fusion_no_adequate_supported_evidence_path" in result["explanation_codes"]
    assert "fusion_semantic_information_unresolved" not in result["explanation_codes"]


def test_only_not_evaluable_and_disabled_tcp_are_insufficient(baseline):
    disabled = _change(baseline, "tcp", "platform_family", explanation=["origin_runtime_disabled"])
    assert _platform(disabled)["status"] == _platform(baseline)["status"] == "insufficient_evidence"
    not_evaluable = _change(baseline, "tls", "platform_family", state="not_evaluable")
    assert _platform(not_evaluable)["not_evaluable_origin_groups"] == ["tls"]
    assert _platform(not_evaluable)["status"] == "insufficient_evidence"


def test_broad_unresolved_is_not_conflict_and_does_not_override_selection(baseline):
    broad = {
        "reference_kind": "BROAD_TAXON", "canonical_taxon_or_source_ref": "unknown-platform",
        "evidence_refs": [], "knowledge_refs": [], "explanation_code": "k1_broad_unresolved",
    }
    only = _change(baseline, "dhcp", "platform_family", broad=[broad])
    result = _platform(only)
    assert result["status"] == "insufficient_evidence"
    assert "fusion_semantic_information_unresolved" in result["explanation_codes"]
    selected = _change(only, "portal", "platform_family", candidates=[_candidate("android")])
    assert _platform(selected)["status"] == "resolved"
    assert _platform(selected)["contradicting_origin_groups"] == []
    assert _platform(selected)["out_of_scope_taxon_references"] == []


def test_only_ambiguous_k1_candidate_information_is_insufficient():
    fixture = build_k1_fixture_definitions()["all_non_any_multi_candidate"]
    source = _inputs(evidence_rows=[_dhcp_row(payload=fixture["evidence"])])
    payload = fixture["record_set"].semantic_payload
    payload["knowledge_provenance"] = {
        "artifact_id": source.knowledge.k1_provenance.artifact_id,
        "content_sha256": source.knowledge.k1_provenance.content_sha256,
    }
    knowledge = replace(source.knowledge, k1_record_set=make_canonical_k1_record_set(payload))
    source = replace(source, knowledge=knowledge,
                     knowledge_bundle=build_initial_knowledge_bundle_v1(knowledge))
    result = fuse_classification(_base_from_source(source)).semantic_payload["device_class_result"]
    assert result["status"] == "insufficient_evidence"
    assert "fusion_semantic_information_unresolved" in result["explanation_codes"]


def test_present_supported_dhcp_path_without_k1_claim_is_unknown_only_where_applicable():
    base = _base_from_source(_inputs(evidence_rows=[_dhcp_row()]))
    for dimension in ("platform_family", "device_class"):
        base = _change(base, "dhcp", dimension, state="no_claim", explanation=["k1_empty_candidate_set"])
    payload = fuse_classification(base).semantic_payload
    assert payload["platform_result"]["status"] == "unknown"
    assert payload["device_class_result"]["status"] == "unknown"
    assert payload["model_result"]["status"] == "insufficient_evidence"
    assert payload["platform_result"]["knowledge_references"] == []


@pytest.mark.parametrize("quality,missing_required,expected", [
    ("valid", False, "unknown"),
    ("partial", False, "unknown"),
    ("partial", True, "insufficient_evidence"),
    ("degraded", False, "insufficient_evidence"),
])
def test_r2_k1_no_match_status_uses_evaluated_dimension_lineage(quality, missing_required, expected):
    source = _r2_k1_no_match_inputs(quality=quality, missing_required=missing_required)
    result = _platform(_base_from_source(source))
    assert result["status"] == expected
    assert result["support_level"] == "none"


@pytest.mark.parametrize("unusable", [
    _dhcp_row(2, quality_state="degraded"),
    _dhcp_row(2, source_subtype="wrong-subtype"),
])
def test_r2_usable_no_match_wins_over_unusable_audit_row(unusable):
    source = _r2_k1_no_match_inputs(extra_rows=[unusable])
    result = _platform(_base_from_source(source))
    assert result["status"] == "unknown"
    assert "fusion_no_usable_semantic_knowledge" in result["explanation_codes"]


@pytest.mark.parametrize("row", [
    _dhcp_row(source_subtype="wrong-subtype"),
    _dhcp_row(quality_state="degraded"),
])
def test_r2_unusable_evidence_alone_is_insufficient(row):
    result = _platform(_base_from_source(_inputs(evidence_rows=[row])))
    assert result["status"] == "insufficient_evidence"


def test_portal_v1_does_not_become_device_class_path():
    base = _base_from_source(_inputs(evidence_rows=[_portal_row(version=1)], origin="portal"))
    base = _change(base, "portal", "platform_family", state="no_claim", explanation=["k3_no_claim"])
    payload = fuse_classification(base).semantic_payload
    assert payload["platform_result"]["status"] == "unknown"
    assert payload["device_class_result"]["status"] == "insufficient_evidence"


def test_portal_v2_no_claim_is_device_class_path_only():
    from app.device_fingerprint.k3_portal_rules import build_k3_portal_rule_set_v1

    vectors = build_k3_portal_rule_set_v1().semantic_payload["test_vectors"]
    payload = next(row["normalized_input"] for row in vectors
                   if row["test_vector_id"] == "k3.vector.unknown_model_ch.no_claim.v2")
    base = _base_from_source(_inputs(
        evidence_rows=[_portal_row(payload=payload, version=2)], origin="portal"))
    result = fuse_classification(base).semantic_payload
    assert result["device_class_result"]["status"] == "unknown"
    assert result["platform_result"]["status"] == "insufficient_evidence"


def test_legacy_tcp_v1_audit_row_is_not_a_semantic_path():
    base = _base_from_source(_inputs(evidence_rows=[_network_row("tcp")], origin="tcp"))
    result = _platform(base)
    assert result["status"] == "insufficient_evidence"
    assert "legacy_tcp_schema_insufficient_for_exact_k2a_contract" in result["explanation_codes"]


def test_present_tcp_v2_k2_no_match_is_unknown_for_platform_only():
    normalized = tcp_v2(ip_df=False, ip_id_zero=False, tcp_sequence_zero=False,
                        tcp_header_length_bytes=20, tcp_option_records=[])
    row = _network_row("tcp", version=2)
    row["payload_json"] = canonical_json(normalized)
    row["payload_sha256"] = canonical_sha256(row["payload_json"])
    row["extractor_version"] = "2.0.0"
    base = _base_from_source(_inputs(evidence_rows=[row], origin="tcp"))
    base = _change(base, "tcp", "platform_family", state="no_claim", explanation=["k2a_no_match"])
    payload = fuse_classification(base).semantic_payload
    assert payload["platform_result"]["status"] == "unknown"
    assert payload["device_class_result"]["status"] == "insufficient_evidence"


@pytest.mark.parametrize("origin", ["tls", "quic"])
def test_present_ja4_audit_only_is_not_usable_path(origin):
    base = _base_from_source(_inputs(evidence_rows=[_network_row(origin)], origin=origin))
    payload = fuse_classification(base).semantic_payload
    assert payload["platform_result"]["status"] == "insufficient_evidence"
    assert payload["platform_result"]["support_level"] == "none"
    assert payload["model_result"]["status"] == "insufficient_evidence"
    assessed = next(item for item in base.origin_assessments
                    if item.semantic_payload["origin_group"] == origin)
    assert all(row["evidence_refs"] == [] for row in assessed.semantic_payload["dimension_assessments"])


def test_expired_knowledge_on_present_supported_path_is_unknown():
    base = _base_from_source(_inputs(evidence_rows=[_dhcp_row()], knowledge_time="2030-01-01T00:00:00.000Z"))
    payload = fuse_classification(base).semantic_payload
    assert payload["platform_result"]["status"] == "unknown"
    assert payload["device_class_result"]["status"] == "unknown"


def test_mac_registry_no_assignment_unknown_and_unmapped_org_insufficient(baseline):
    payload = fuse_classification(baseline).semantic_payload
    assert payload["manufacturer_result"]["status"] == "insufficient_evidence"
    assert "fusion_no_adequate_supported_evidence_path" in payload["manufacturer_result"]["explanation_codes"]
    global_no_match = _base_from_source(_inputs(mac="00:33:44:55:66:77"))
    assert fuse_classification(global_no_match).semantic_payload["manufacturer_result"]["status"] == "unknown"
    global_unmapped = _base_from_source(_inputs(mac="00:11:22:33:44:55"))
    assert fuse_classification(global_unmapped).semantic_payload["manufacturer_result"]["status"] == (
        "insufficient_evidence")


def test_expired_k4_with_supported_registry_path_is_unknown():
    base = _base_from_source(_inputs(mac="00:11:22:33:44:55",
                                    knowledge_time="2030-01-01T00:00:00.000Z"))
    result = fuse_classification(base).semantic_payload["manufacturer_result"]
    assert result["status"] == "unknown"
    assert "knowledge_source_expired" in result["explanation_codes"]


def test_global_policy_statuses_from_constructed_dimensions(baseline):
    all_resolved = baseline
    for dimension, value in (("platform_family", "android"), ("device_class", "smartphone"),
                             ("manufacturer_family", "vendor"), ("model_family", "model")):
        all_resolved = _change(all_resolved, "portal", dimension, candidates=[_candidate(value)])
    assert fuse_classification(all_resolved).semantic_payload["global_classification_status"] == "classified"
    conflicted = _change(all_resolved, "tcp", "platform_family", candidates=[_candidate("ios")])
    assert fuse_classification(conflicted).semantic_payload["global_classification_status"] == "conflicting_evidence"
    outside = _change(baseline, "portal", "platform_family",
                      candidates=[_candidate("other-platform", "supporting", outside=True)])
    assert fuse_classification(outside).semantic_payload["global_classification_status"] == "recognized_out_of_scope"
    assert _first_rule(baseline.classification_policy.semantic_payload["global_status_derivation"],
                       {"OTHERWISE": True}) == "unknown"


def test_result_exact_closed_shapes_and_global_policy(baseline):
    result = fuse_classification(baseline).semantic_payload
    assert set(result) == {
        "classification_request_digest", "classification_policy", "knowledge_bundle",
        "classifier_artifact_manifest", "evidence_snapshot_content", "source_evaluability",
        "platform_result", "device_class_result", "manufacturer_result", "model_result",
        "global_classification_status", "origin_assessments",
    }
    expected_dimension_fields = {
        "dimension_name", "canonical_value_id", "display_label_ref", "status", "support_level",
        "supporting_origin_groups", "contradicting_origin_groups", "not_evaluable_origin_groups",
        "out_of_scope_taxon_references", "explanation_codes", "knowledge_references",
    }
    for field in ("platform_result", "device_class_result", "manufacturer_result", "model_result"):
        assert set(result[field]) == expected_dimension_fields
        assert result[field]["display_label_ref"] is None
    assert result["global_classification_status"] == "insufficient_evidence"
    bad = dict(result["platform_result"], status="conflicting_evidence")
    with pytest.raises(DeviceFingerprintValidationError):
        _validate_dimension_result(bad, {"platform_family", "device_class"})


def test_fusion_module_has_no_runtime_io_clock_or_environment_imports():
    source = ast.parse(inspect.getsource(fusion_module))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(source) if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(source) if isinstance(node, ast.ImportFrom)
    }
    assert imported.isdisjoint({"os", "pathlib", "socket", "time", "datetime", "sqlite3", "requests"})
    called = {node.func.id for node in ast.walk(source)
              if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert called.isdisjoint({"open", "connect", "getenv", "now", "utcnow"})
