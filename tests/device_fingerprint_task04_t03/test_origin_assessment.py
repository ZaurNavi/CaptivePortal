"""Exact OriginAssessment shape, pure lineage, and conservative origin semantics."""

from __future__ import annotations

from dataclasses import fields, replace

import pytest

from app.device_fingerprint.artifact_content import ArtifactRef, make_artifact_content
from app.device_fingerprint.binding_contracts import (
    make_binding_clock_policy, make_evidence_source_binding_timeline,
)
from app.device_fingerprint.evidence_adapter_contracts import (
    DIMENSIONS, build_initial_evidence_adapter_contract_set_v1,
    make_evidence_adapter_contract_set, task01_contract_claim_eligible,
)
from app.device_fingerprint.foundation_admission_artifacts import make_origin_runtime_admission
from app.device_fingerprint.k3_portal_rules import build_k3_portal_rule_set_v1
from app.device_fingerprint.knowledge_artifacts import make_canonical_k4_record_set
from app.device_fingerprint.knowledge_artifacts import make_canonical_k1_record_set
from app.device_fingerprint.snapshot_service import (
    EvidenceSnapshotMaterialization, MaterializedEvidenceEntry,
)
from app.device_fingerprint.knowledge_bundle import build_initial_knowledge_bundle_v1
from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.portal_schemas import PORTAL_HEADER_V2_KEYS
from app.device_fingerprint.origin_assessment import (
    DeviceFingerprintOriginAssessmentBuilder, OriginAssessmentInputs,
    _merge_contributions, _reduce_claims, make_origin_assessment,
)
from app.device_fingerprint.runtime_profile_artifacts import make_foundation_runtime_profile
from app.device_fingerprint.source_evaluability import DeviceFingerprintSourceEvaluabilityBuilder
from tests.device_fingerprint import SITE
from tests.device_fingerprint_fe7.test_knowledge_bundle import candidate
from tests.device_fingerprint_task04_t01.test_snapshot_service import MAC, START, END, aid, context, evidence
from research.device_fingerprint_fe1.fixtures import build_k1_fixture_definitions
from tests.device_fingerprint.test_network_schemas import quic, tcp_v2, tls
from tests.device_fingerprint_task04_t01.test_snapshot_service import health


def _ref(content):
    return ArtifactRef(content.artifact_id, content.content_sha256).as_dict()


def _inputs(*, evidence_rows=(), health_rows=(), knowledge_time="2026-09-22T22:30:34.464Z",
            origin="dhcp", mac=MAC, tcp_disabled=False):
    ctx = context(evidence_rows, health_rows)
    if origin != "dhcp":
        source = {"portal": "portal_headers", "tcp": "tcp_syn", "tls": "tls_client",
                  "quic": "quic_client"}[origin]
        producer = "portal-zefer-01" if origin == "portal" else "sensor-zefer-01"
        capture = "zefer-portal-http-01" if origin == "portal" else "zefer-span-01"
        emitter = next(content for content in ctx.contents.values()
                       if content.artifact_type == "SourceHealthEmitterContract"
                       and source in content.semantic_payload["source_kinds"])
        epoch = {
            "binding_epoch_id": "P", "site_id": SITE, "origin_group": origin,
            "source_kind": source, "capture_source_id": capture, "producer_id": producer,
            "source_health_emitter_contract": _ref(emitter),
            "effective_from_utc": "2026-09-15T11:00:00.000Z", "effective_to_utc": None,
        }
        timeline = make_evidence_source_binding_timeline({
            "binding_timeline_contract_version": 1, "binding_epochs": [epoch]}, [emitter])
        clock_ref = ctx.profile.semantic_payload["binding_clock_policy"]
        clock_payload = ctx.contents[clock_ref["artifact_id"]].semantic_payload
        if producer not in {row["producer_id"] for row in clock_payload["producer_clock_domains"]}:
            clock_payload["producer_clock_domains"].append({
                "clock_domain_id": "portal-clock", "producer_id": producer})
        clock = make_binding_clock_policy(clock_payload)
        ctx.contents[timeline.artifact_id] = timeline
        ctx.contents[clock.artifact_id] = clock
        profile_payload = ctx.profile.semantic_payload
        profile_payload.update(evidence_source_binding_timeline=_ref(timeline), binding_clock_policy=_ref(clock))
        ctx.profile = make_foundation_runtime_profile(profile_payload)
        ctx.service._profile = ctx.profile
    if tcp_disabled:
        disabled = make_origin_runtime_admission({
            "origin_runtime_admission_contract_version": 1, "tcp_state": "DISABLED",
            "tcp_reason_code": "PROFILE_POLICY_DISABLED", "ttl_capture_placement_proof": None,
        })
        ctx.contents[disabled.artifact_id] = disabled
        profile_payload = ctx.profile.semantic_payload
        profile_payload["origin_runtime_admission"] = _ref(disabled)
        profile_payload["ttl_capture_placement_proof"] = None
        ctx.profile = make_foundation_runtime_profile(profile_payload)
        ctx.service._profile = ctx.profile
    result = ctx.service.build(SITE, mac, START, END)
    source = DeviceFingerprintSourceEvaluabilityBuilder(
        foundation_runtime_profile=ctx.profile,
        artifact_resolver=lambda reference: ctx.contents[reference.artifact_id],
    ).build(result.evidence_snapshot_content)
    knowledge = candidate()
    bundle = build_initial_knowledge_bundle_v1(knowledge)
    registry = ctx.contents[ctx.profile.semantic_payload["evidence_schema_registry_contract"]["artifact_id"]]
    adapter = build_initial_evidence_adapter_contract_set_v1(registry)
    return OriginAssessmentInputs(
        result.evidence_snapshot_content, result.materialization, source,
        adapter, bundle, knowledge, knowledge_time,
    )


def _candidate(value="android", strength="supporting", evidence_id="one"):
    return {
        "candidate_kind": "CANONICAL_VALUE", "candidate_value_id": value,
        "out_of_scope_taxon_ref": None, "claim_strength": strength,
        "claim_derivation": "fingerprint_match", "knowledge_refs": [],
        "evidence_refs": [{
            "evidence_id": aid(sum(ord(letter) for letter in evidence_id)), "payload_sha256": "a" * 64,
            "feature_schema_version": 1,
            "adapter_contract_id": "EvidenceAdapterContractSet:v1:sha256:" + "b" * 64,
            "adapter_contract_digest": "b" * 64,
        }],
    }


def test_six_origin_artifacts_have_exact_four_dimensions_and_stable_identity():
    inputs = _inputs()
    builder = DeviceFingerprintOriginAssessmentBuilder(inputs)
    first = builder.build_all()
    second = builder.build_all()
    assert [row.artifact_id for row in first] == [row.artifact_id for row in second]
    assert {row.semantic_payload["origin_group"] for row in first} == {
        "dhcp", "portal", "tcp", "tls", "quic", "mac_registry"}
    for row in first:
        assert {dimension["dimension_name"] for dimension in row.semantic_payload["dimension_assessments"]} == set(DIMENSIONS)
        assert all(dimension["internal_state"] == "no_claim" for dimension in row.semantic_payload["dimension_assessments"])


def test_exact_schema_and_pinned_snapshot_evaluability_refs():
    inputs = _inputs()
    row = DeviceFingerprintOriginAssessmentBuilder(inputs).build("dhcp")
    payload = row.semantic_payload
    kwargs = {
        "evidence_snapshot_content": inputs.evidence_snapshot_content,
        "source_evaluability": inputs.source_evaluability,
        "evidence_adapter_contract_set": inputs.evidence_adapter_contract_set,
        "knowledge_bundle": inputs.knowledge_bundle,
        "knowledge": inputs.knowledge,
    }
    assert make_origin_assessment(payload, **kwargs) == row
    for change in ({"extra": True}, {"dimension_assessments": []},
                   {"source_evaluability": _ref(inputs.evidence_snapshot_content)}):
        wrong = {**payload, **change}
        with pytest.raises(DeviceFingerprintValidationError):
            make_origin_assessment(wrong, **kwargs)


def test_origin_artifact_input_order_permutation_keeps_identity():
    inputs = _inputs(evidence_rows=[_dhcp_row(1), _dhcp_row(2)])
    artifact = DeviceFingerprintOriginAssessmentBuilder(inputs).build("dhcp")
    payload = artifact.semantic_payload
    payload["dimension_assessments"].reverse()
    payload["evidence_refs"].reverse()
    kwargs = {
        "evidence_snapshot_content": inputs.evidence_snapshot_content,
        "source_evaluability": inputs.source_evaluability,
        "evidence_adapter_contract_set": inputs.evidence_adapter_contract_set,
        "knowledge_bundle": inputs.knowledge_bundle,
        "knowledge": inputs.knowledge,
    }
    assert make_origin_assessment(payload, **kwargs) == artifact


def test_exact_evidence_and_knowledge_reference_lineage_is_enforced():
    inputs = _inputs(evidence_rows=[_dhcp_row()])
    artifact = DeviceFingerprintOriginAssessmentBuilder(inputs).build("dhcp")
    kwargs = {
        "evidence_snapshot_content": inputs.evidence_snapshot_content,
        "source_evaluability": inputs.source_evaluability,
        "evidence_adapter_contract_set": inputs.evidence_adapter_contract_set,
        "knowledge_bundle": inputs.knowledge_bundle,
        "knowledge": inputs.knowledge,
    }
    wrong_evidence = artifact.semantic_payload
    wrong_evidence["evidence_refs"][0]["payload_sha256"] = "f" * 64
    with pytest.raises(DeviceFingerprintValidationError, match="EvidenceRef"):
        make_origin_assessment(wrong_evidence, **kwargs)
    wrong_knowledge = artifact.semantic_payload
    wrong_knowledge["knowledge_refs"][0]["canonical_knowledge_record_id"] = "unknown-record"
    with pytest.raises(DeviceFingerprintValidationError, match="KnowledgeRef"):
        make_origin_assessment(wrong_knowledge, **kwargs)


@pytest.mark.parametrize("strong,supporting,expected,conflict", [
    (("android", "android"), (), "resolved", None),
    (("android", "ios"), (), "conflicting", "strong"),
    (("android",), ("android",), "resolved", None),
    (("android",), ("ios",), "resolved", "supporting"),
    ((), ("android", "android"), "resolved", None),
    ((), ("android", "ios"), "conflicting", "supporting"),
])
def test_same_origin_strength_matrix(strong, supporting, expected, conflict):
    rows = [_candidate(value, "strong", f"s{index}") for index, value in enumerate(strong)]
    rows += [_candidate(value, "supporting", f"p{index}") for index, value in enumerate(supporting)]
    output = _reduce_claims("platform_family", rows)
    assert output["internal_state"] == expected
    assert output["conflict_strength"] == conflict
    if conflict:
        assert output["same_origin_contradiction_records"]
    assert _reduce_claims("platform_family", list(reversed(rows))) == output


def test_k1_alternatives_are_ambiguous_only_for_differing_dimension():
    rows = [_candidate("smartphone", evidence_id="one"),
            _candidate("tablet", evidence_id="one")]
    assert _reduce_claims("device_class", rows, k1_ambiguous=True)["internal_state"] == "ambiguous"
    assert _reduce_claims("platform_family", [_candidate("android", evidence_id="one"),
                                              _candidate("android", evidence_id="two")],
                          k1_ambiguous=True)["selected_canonical_value_id"] == "android"
    assert _reduce_claims("device_class", [
        _candidate("smartphone", evidence_id="one"),
        _candidate("tablet", evidence_id="two")], k1_ambiguous=True)["internal_state"] == "conflicting"


def test_negative_knowledge_age_fails_closed():
    with pytest.raises(DeviceFingerprintValidationError, match="Negative knowledge age"):
        DeviceFingerprintOriginAssessmentBuilder(_inputs(knowledge_time="2026-09-15T12:00:00.000Z"))


def test_materialization_and_source_identity_mismatch_fail_closed():
    inputs = _inputs()
    wrong_snapshot = make_artifact_content("EvidenceSnapshotContent", {"synthetic": True})
    from dataclasses import replace
    for changed in (replace(inputs, evidence_snapshot_content=wrong_snapshot),
                    replace(inputs, source_evaluability=wrong_snapshot)):
        with pytest.raises((DeviceFingerprintValidationError, KeyError, TypeError)):
            DeviceFingerprintOriginAssessmentBuilder(changed)
    wrong_materialization = EvidenceSnapshotMaterialization(
        ArtifactRef("EvidenceSnapshotContent:v1:sha256:" + "f" * 64, "f" * 64), ())
    with pytest.raises(DeviceFingerprintValidationError):
        DeviceFingerprintOriginAssessmentBuilder(replace(inputs, materialization=wrong_materialization))
    wrong_source_payload = inputs.source_evaluability.semantic_payload
    wrong_source_payload["evidence_snapshot_content"] = _ref(wrong_snapshot)
    wrong_source = make_artifact_content("SourceEvaluability", wrong_source_payload)
    with pytest.raises(DeviceFingerprintValidationError):
        DeviceFingerprintOriginAssessmentBuilder(replace(inputs, source_evaluability=wrong_source))


def _dhcp_row(number=1, **changes):
    row = evidence(number, payload=changes.pop("payload", None))
    row.update(source_subtype="discover", extractor_name="packet-dhcp")
    row.update(changes)
    return row


def _with_descriptor(inputs, **changes):
    """Change a T-01 descriptor at the T-03 boundary without re-running T-01."""
    snapshot_payload = inputs.evidence_snapshot_content.semantic_payload
    descriptor = snapshot_payload["evidence_descriptors"][0]
    descriptor.update(changes)
    snapshot = make_artifact_content("EvidenceSnapshotContent", snapshot_payload)
    materialized = tuple(MaterializedEvidenceEntry(
        descriptor if entry.descriptor["evidence_id"] == descriptor["evidence_id"] else entry.descriptor,
        entry.normalized_payload) for entry in inputs.materialization.ordered_entries)
    materialization = EvidenceSnapshotMaterialization(
        ArtifactRef(snapshot.artifact_id, snapshot.content_sha256), materialized)
    source_payload = inputs.source_evaluability.semantic_payload
    source_payload["evidence_snapshot_content"] = _ref(snapshot)
    source = make_artifact_content("SourceEvaluability", source_payload)
    return replace(inputs, evidence_snapshot_content=snapshot,
                   materialization=materialization, source_evaluability=source)


def test_present_dhcp_evidence_remains_usable_without_health_coverage():
    inputs = _inputs(evidence_rows=[_dhcp_row()])
    output = DeviceFingerprintOriginAssessmentBuilder(inputs).build("dhcp").semantic_payload
    assert output["evidence_refs"]
    assert output["knowledge_refs"]
    assert next(row for row in output["dimension_assessments"]
                if row["dimension_name"] == "platform_family")["internal_state"] == "resolved"


def test_present_evidence_during_acquisition_unavailable_still_claims():
    unavailable = health()
    unavailable.update(status="unavailable", reason_code="capture_interface_unavailable")
    inputs = _inputs(evidence_rows=[_dhcp_row()], health_rows=[unavailable])
    output = DeviceFingerprintOriginAssessmentBuilder(inputs).build("dhcp").semantic_payload
    assert "evidence_present_during_acquisition_unavailable" in output["explanation_codes"]
    assert next(row for row in output["dimension_assessments"]
                if row["dimension_name"] == "platform_family")["internal_state"] == "resolved"


def test_missing_evidence_never_creates_negative_claim():
    unavailable = health()
    unavailable.update(status="unavailable", reason_code="capture_interface_unavailable")
    inputs = _inputs(health_rows=[unavailable])
    output = DeviceFingerprintOriginAssessmentBuilder(inputs).build("dhcp").semantic_payload
    assert not output["evidence_refs"]
    assert all(not row["candidate_set"] for row in output["dimension_assessments"])
    assert all(row["internal_state"] in {"no_claim", "not_evaluable"}
               for row in output["dimension_assessments"])


def test_partial_quality_requires_each_admitted_dimension_field():
    inputs = _inputs()
    adapter = next(row for row in inputs.evidence_adapter_contract_set.semantic_payload["adapter_entries"]
                   if row.get("source_kind") == "dhcp")
    from tests.device_fingerprint_task04_t01.test_snapshot_service import KNOWN
    kwargs = {
        "source_kind": "dhcp", "feature_schema_version": 1,
        "source_subtype": "discover", "extractor_name": "packet-dhcp",
        "extractor_version": "1.0.0", "rule_version": None,
        "quality_state": "partial", "dimension_name": "platform_family",
    }
    assert task01_contract_claim_eligible(adapter, normalized_payload=KNOWN, **kwargs)
    missing = dict(KNOWN)
    missing.pop("vendor_class")
    assert not task01_contract_claim_eligible(adapter, normalized_payload=missing, **kwargs)


def test_partial_quality_caps_an_otherwise_strong_admitted_claim():
    original = _inputs(evidence_rows=[_dhcp_row(quality_state="partial")])
    k1_payload = original.knowledge.k1_record_set.semantic_payload
    for record in k1_payload["records"]:
        for outcome in record["candidate_taxonomy_refs"]:
            if outcome["outcome_kind"] == "CANONICAL_VALUE":
                outcome["base_claim_strength"] = "strong"
    changed_knowledge = replace(original.knowledge,
                                k1_record_set=make_canonical_k1_record_set(k1_payload))
    bundle = build_initial_knowledge_bundle_v1(changed_knowledge)
    adapter_payload = original.evidence_adapter_contract_set.semantic_payload
    for entry in adapter_payload["adapter_entries"]:
        if entry.get("source_kind") == "dhcp":
            entry["base_claim_strength_ceiling"] = "strong"
    adapter = make_evidence_adapter_contract_set(adapter_payload)
    inputs = replace(original, knowledge=changed_knowledge, knowledge_bundle=bundle,
                     evidence_adapter_contract_set=adapter)
    output = DeviceFingerprintOriginAssessmentBuilder(inputs).build("dhcp").semantic_payload
    platform = next(row for row in output["dimension_assessments"]
                    if row["dimension_name"] == "platform_family")
    assert platform["effective_claim_strength"] == "supporting"


def _portal_row(number=1, *, payload=None, quality="valid", version=1):
    if payload is None:
        rules = build_k3_portal_rule_set_v1().semantic_payload
        payload = next(row["normalized_input"] for row in rules["test_vectors"]
                       if row["test_vector_id"] == "k3.vector.platform.android.sec_ch_ua_platform.v1")
    row = evidence(number, payload=payload, version=version)
    row.update(source_kind="portal_headers", source_subtype="capport_login",
               producer_id="portal-zefer-01", capture_source_id="zefer-portal-http-01",
               extractor_name="portal-http-parser", extractor_version="1.0.0",
               quality_state=quality)
    return row


def test_portal_k3_uses_only_normalized_provenance_and_no_mobile_heuristic():
    payload = build_k3_portal_rule_set_v1().semantic_payload
    platform = next(row["normalized_input"] for row in payload["test_vectors"]
                    if row["test_vector_id"] == "k3.vector.platform.android.sec_ch_ua_platform.v1")
    mobile = next(row["normalized_input"] for row in payload["test_vectors"]
                  if row["test_vector_id"] == "k3.vector.mobile_boolean.no_class.v1")
    inputs = _inputs(evidence_rows=[_portal_row(1, payload=platform),
                                   _portal_row(2, payload=mobile)], origin="portal")
    output = DeviceFingerprintOriginAssessmentBuilder(inputs).build("portal").semantic_payload
    dimensions = {row["dimension_name"]: row for row in output["dimension_assessments"]}
    assert dimensions["platform_family"]["selected_canonical_value_id"] == "android", dimensions
    assert dimensions["device_class"]["internal_state"] == "no_claim"
    assert output["knowledge_refs"]
    assert all(row["knowledge_provenance_id"] == inputs.knowledge.k3_provenance.artifact_id
               for row in output["knowledge_refs"])


@pytest.mark.parametrize("quality,claim", [("valid", True), ("partial", True), ("degraded", False)])
def test_portal_quality_semantics(quality, claim):
    inputs = _inputs(evidence_rows=[_portal_row(quality=quality)], origin="portal")
    output = DeviceFingerprintOriginAssessmentBuilder(inputs).build("portal").semantic_payload
    platform = next(row for row in output["dimension_assessments"]
                    if row["dimension_name"] == "platform_family")
    assert bool(platform["candidate_set"]) is claim
    if quality == "partial":
        assert platform["effective_claim_strength"] == "supporting"


def test_unsupported_future_schema_is_audit_visible_without_claim():
    inputs = _inputs(evidence_rows=[_portal_row(version=99)], origin="portal")
    output = DeviceFingerprintOriginAssessmentBuilder(inputs).build("portal").semantic_payload
    assert "unsupported_evidence_contract" in output["explanation_codes"]
    assert len(output["evidence_refs"]) == 1
    assert all(row["internal_state"] == "no_claim" for row in output["dimension_assessments"])


def test_expired_external_k1_emits_no_new_claim():
    inputs = _inputs(evidence_rows=[_dhcp_row()], knowledge_time="2030-01-01T00:00:00.000Z")
    output = DeviceFingerprintOriginAssessmentBuilder(inputs).build("dhcp").semantic_payload
    assert "knowledge_source_expired" in output["explanation_codes"]
    assert all(row["internal_state"] == "no_claim" for row in output["dimension_assessments"])


def test_stale_external_k1_uses_admitted_explanation_and_ceiling():
    inputs = _inputs(evidence_rows=[_dhcp_row()], knowledge_time="2027-10-01T00:00:00.000Z")
    output = DeviceFingerprintOriginAssessmentBuilder(inputs).build("dhcp").semantic_payload
    assert "knowledge_source_stale" in output["explanation_codes"]
    platform = next(row for row in output["dimension_assessments"]
                    if row["dimension_name"] == "platform_family")
    assert platform["selected_canonical_value_id"] == "android"
    assert platform["effective_claim_strength"] == "supporting"


def test_identical_semantic_repetition_never_creates_another_vote():
    one = _inputs(evidence_rows=[_portal_row(1)], origin="portal")
    many = _inputs(evidence_rows=[_portal_row(1), _portal_row(2)], origin="portal")
    a = DeviceFingerprintOriginAssessmentBuilder(one).build("portal").semantic_payload
    b = DeviceFingerprintOriginAssessmentBuilder(many).build("portal").semantic_payload
    a_platform = next(row for row in a["dimension_assessments"] if row["dimension_name"] == "platform_family")
    b_platform = next(row for row in b["dimension_assessments"] if row["dimension_name"] == "platform_family")
    assert (a_platform["internal_state"], a_platform["effective_claim_strength"]) == (
        b_platform["internal_state"], b_platform["effective_claim_strength"])
    assert len(b_platform["candidate_set"]) == 1


def test_cross_version_no_claim_does_not_invent_a_semantic_contribution():
    rules = build_k3_portal_rule_set_v1().semantic_payload
    v1 = next(row["normalized_input"] for row in rules["test_vectors"]
              if row["test_vector_id"] == "k3.vector.unknown_model_ua.no_claim.v1")
    v2 = next(row["normalized_input"] for row in rules["test_vectors"]
              if row["test_vector_id"] == "k3.vector.unknown_model_ch.no_claim.v2")
    assert set(v2) == PORTAL_HEADER_V2_KEYS
    inputs = _inputs(evidence_rows=[_portal_row(1, payload=v1, version=1),
                                   _portal_row(2, payload=v2, version=2)], origin="portal")
    output = DeviceFingerprintOriginAssessmentBuilder(inputs).build("portal").semantic_payload
    assert all(not row["candidate_set"] for row in output["dimension_assessments"])
    assert len(output["evidence_refs"]) == 2


def test_mac_registry_local_admin_and_raw_assignment_not_manufacturer():
    local = _inputs()
    local_output = DeviceFingerprintOriginAssessmentBuilder(local).build("mac_registry").semantic_payload
    assert "no_ieee_assignment_claim" in local_output["explanation_codes"]
    global_mac = _inputs(mac="00:11:22:33:44:55")
    global_output = DeviceFingerprintOriginAssessmentBuilder(global_mac).build("mac_registry").semantic_payload
    assert "mac_assignment_org_not_manufacturer" in global_output["explanation_codes"]
    assert all(row["internal_state"] == "no_claim" for row in global_output["dimension_assessments"])


def test_mac_registry_explicit_admitted_org_mapping_only():
    original = _inputs(mac="00:11:22:33:44:55")
    k = original.knowledge
    k4_payload = k.k4_record_set.semantic_payload
    k4_payload["records"][0]["manufacturer_mapping"] = {
        "manufacturer_id": "synthetic-manufacturer", "mapping_version": "1",
        "review_basis": "synthetic review", "base_claim_strength": "supporting",
    }
    k4 = make_canonical_k4_record_set(k4_payload)
    changed_knowledge = replace(k, k4_record_set=k4)
    bundle = build_initial_knowledge_bundle_v1(changed_knowledge)
    inputs = replace(original, knowledge=changed_knowledge, knowledge_bundle=bundle)
    output = DeviceFingerprintOriginAssessmentBuilder(inputs).build("mac_registry").semantic_payload
    manufacturer = next(row for row in output["dimension_assessments"]
                        if row["dimension_name"] == "manufacturer_family")
    assert manufacturer["selected_canonical_value_id"] == "synthetic-manufacturer"
    assert manufacturer["effective_claim_strength"] == "supporting"


def test_mac_registry_longest_prefix_and_dhcp_origin_purity():
    original = _inputs(evidence_rows=[_dhcp_row()], mac=MAC)
    k = original.knowledge
    k4_payload = k.k4_record_set.semantic_payload
    base = k4_payload["records"][0]
    k4_payload["records"] = []
    for family, bits, prefix, label in (
        ("MA-L", 24, "001122", "long"),
        ("MA-M", 28, "0011223", "medium"),
        ("MA-S", 36, "001122334", "short"),
    ):
        record = dict(base)
        record.update(registry_family=family, prefix_length_bits=bits, prefix_hex=prefix,
                      canonical_record_id="synthetic-" + label,
                      source_record_identity="synthetic-source-" + label,
                      manufacturer_mapping={
                          "manufacturer_id": "manufacturer-" + label,
                          "mapping_version": "1", "review_basis": "synthetic review",
                          "base_claim_strength": "supporting",
                      })
        k4_payload["records"].append(record)
    k4 = make_canonical_k4_record_set(k4_payload)
    changed_knowledge = replace(k, k4_record_set=k4)
    bundle = build_initial_knowledge_bundle_v1(changed_knowledge)
    changed = replace(original, knowledge=changed_knowledge, knowledge_bundle=bundle)
    dhcp = DeviceFingerprintOriginAssessmentBuilder(changed).build("dhcp").semantic_payload
    assert next(row for row in dhcp["dimension_assessments"]
                if row["dimension_name"] == "manufacturer_family")["internal_state"] == "no_claim"

    global_input = _inputs(mac="00:11:22:33:44:55")
    global_input = replace(global_input, knowledge=changed_knowledge, knowledge_bundle=bundle)
    mac = DeviceFingerprintOriginAssessmentBuilder(global_input).build("mac_registry").semantic_payload
    assert next(row for row in mac["dimension_assessments"]
                if row["dimension_name"] == "manufacturer_family")["selected_canonical_value_id"] == "manufacturer-short"


def test_k1_complete_candidate_enumeration_ambiguity_and_permutation():
    fixture = build_k1_fixture_definitions()["all_non_any_multi_candidate"]
    first = _inputs(evidence_rows=[_dhcp_row(payload=fixture["evidence"])])
    knowledge = first.knowledge
    k1_payload = fixture["record_set"].semantic_payload
    k1_payload["knowledge_provenance"] = _ref(knowledge.k1_provenance)
    k1 = make_canonical_k1_record_set(k1_payload)
    changed_knowledge = replace(knowledge, k1_record_set=k1)
    bundle = build_initial_knowledge_bundle_v1(changed_knowledge)
    inputs = replace(first, knowledge=changed_knowledge, knowledge_bundle=bundle)
    output = DeviceFingerprintOriginAssessmentBuilder(inputs).build("dhcp").semantic_payload
    dimensions = {row["dimension_name"]: row for row in output["dimension_assessments"]}
    assert dimensions["platform_family"]["selected_canonical_value_id"] == "android", dimensions
    assert dimensions["device_class"]["internal_state"] == "ambiguous"
    assert {row["candidate_value_id"] for row in dimensions["device_class"]["candidate_set"]} == {
        "smartphone", "tablet"}
    reordered = k1.semantic_payload
    reordered["records"].reverse()
    assert make_canonical_k1_record_set(reordered) == k1


def test_k1_no_match_is_empty_and_row_order_is_identity_stable():
    fixture = build_k1_fixture_definitions()["one_non_any_mismatch"]
    first = _inputs(evidence_rows=[_dhcp_row(payload=fixture["evidence"])])
    payload = fixture["record_set"].semantic_payload
    payload["knowledge_provenance"] = _ref(first.knowledge.k1_provenance)
    changed_knowledge = replace(first.knowledge, k1_record_set=make_canonical_k1_record_set(payload))
    bundle = build_initial_knowledge_bundle_v1(changed_knowledge)
    inputs = replace(first, knowledge=changed_knowledge, knowledge_bundle=bundle)
    output = DeviceFingerprintOriginAssessmentBuilder(inputs).build("dhcp").semantic_payload
    assert "k1_empty_candidate_set" in output["explanation_codes"]
    assert all(not row["candidate_set"] for row in output["dimension_assessments"])

    forward = _inputs(evidence_rows=[_dhcp_row(1), _dhcp_row(2)])
    reverse = _inputs(evidence_rows=[_dhcp_row(2), _dhcp_row(1)])
    assert DeviceFingerprintOriginAssessmentBuilder(forward).build("dhcp") == (
        DeviceFingerprintOriginAssessmentBuilder(reverse).build("dhcp"))


def _network_row(origin, *, version=1, number=1):
    source = {"tcp": "tcp_syn", "tls": "tls_client", "quic": "quic_client"}[origin]
    payload = {
        "tcp": {
            "ip_version": 4, "observed_ttl": 64, "tcp_window": 65535,
            "mss": 1460, "window_scale": 8, "sack_permitted": True,
            "timestamps_present": True, "tcp_option_order": [2, 4, 8, 1, 3],
        },
        "tls": tls(), "quic": quic(),
    }[origin]
    row = evidence(number, payload=payload, version=version)
    row.update(source_kind=source, source_subtype="ipv4" if origin == "tcp" else "client_hello",
               extractor_name={"tcp": "packet-tcp-syn", "tls": "suricata-tls-ja4",
                               "quic": "suricata-quic-ja4"}[origin],
               extractor_version="1.0.0" if origin == "tcp" else "8.0.6")
    return row


def test_tcp_v2_uses_admitted_k2a_matcher_and_k2b_claim_ceiling():
    payload = tcp_v2(ip_df=False, ip_id_zero=False, tcp_sequence_zero=False,
                     tcp_header_length_bytes=20, tcp_option_records=[])
    row = _network_row("tcp", version=2)
    from app.device_fingerprint.validation import canonical_json, canonical_sha256
    row["payload_json"] = canonical_json(payload)
    row["payload_sha256"] = canonical_sha256(row["payload_json"])
    row["extractor_version"] = "2.0.0"
    inputs = _inputs(evidence_rows=[row], origin="tcp")
    output = DeviceFingerprintOriginAssessmentBuilder(inputs).build("tcp").semantic_payload
    platform = next(dimension for dimension in output["dimension_assessments"]
                    if dimension["dimension_name"] == "platform_family")
    assert platform["selected_canonical_value_id"] == "linux"
    assert platform["effective_claim_strength"] == "supporting"


def test_legacy_tcp_v1_cannot_add_a_vote_to_v2_semantic_claim():
    payload = tcp_v2(ip_df=False, ip_id_zero=False, tcp_sequence_zero=False,
                     tcp_header_length_bytes=20, tcp_option_records=[])
    current = _network_row("tcp", version=2, number=2)
    from app.device_fingerprint.validation import canonical_json, canonical_sha256
    current["payload_json"] = canonical_json(payload)
    current["payload_sha256"] = canonical_sha256(current["payload_json"])
    current["extractor_version"] = "2.0.0"
    inputs = _inputs(evidence_rows=[_network_row("tcp", number=1), current], origin="tcp")
    output = DeviceFingerprintOriginAssessmentBuilder(inputs).build("tcp").semantic_payload
    platform = next(row for row in output["dimension_assessments"]
                    if row["dimension_name"] == "platform_family")
    assert len(output["evidence_refs"]) == 2
    assert len(platform["candidate_set"]) == 1
    assert platform["selected_canonical_value_id"] == "linux"
    assert "legacy_tcp_schema_insufficient_for_exact_k2a_contract" in output["explanation_codes"]


@pytest.mark.parametrize("origin,reason", [
    ("tcp", "legacy_tcp_schema_insufficient_for_exact_k2a_contract"),
    ("tls", "ja4_no_semantic_claim"),
    ("quic", "ja4_no_semantic_claim"),
])
def test_legacy_tcp_and_ja4_are_audit_only(origin, reason):
    inputs = _inputs(evidence_rows=[_network_row(origin)], origin=origin)
    output = DeviceFingerprintOriginAssessmentBuilder(inputs).build(origin).semantic_payload
    assert reason in output["explanation_codes"]
    assert len(output["evidence_refs"]) == 1
    assert all(row["internal_state"] == "no_claim" for row in output["dimension_assessments"])


def test_pinned_tcp_disabled_emits_no_semantic_claim_with_audit_visible_row():
    inputs = _inputs(evidence_rows=[_network_row("tcp")], origin="tcp", tcp_disabled=True)
    assert inputs.evidence_snapshot_content.semantic_payload["origin_runtime_admission"]["tcp_state"] == "DISABLED"
    output = DeviceFingerprintOriginAssessmentBuilder(inputs).build("tcp").semantic_payload
    assert "origin_runtime_disabled" in output["explanation_codes"]
    assert len(output["evidence_refs"]) == 1
    assert all(row["internal_state"] == "no_claim" for row in output["dimension_assessments"])


def test_t03_input_boundary_has_no_later_runtime_profile_or_foundation_proof():
    assert [field.name for field in fields(OriginAssessmentInputs)] == [
        "evidence_snapshot_content", "materialization", "source_evaluability",
        "evidence_adapter_contract_set", "knowledge_bundle", "knowledge",
        "knowledge_evaluation_at_utc",
    ]
    assert DeviceFingerprintOriginAssessmentBuilder(_inputs()).build_all()


@pytest.mark.parametrize("change", [
    {"source_subtype": "wrong-subtype"},
    {"extractor_name": "wrong-extractor"},
    {"extractor_version": "9.9.9"},
    {"rule_version": "unexpected-rule"},
])
def test_adapter_incompatibility_is_audit_only_before_k1_matcher(change, monkeypatch):
    import app.device_fingerprint.origin_assessment as module

    inputs = _with_descriptor(_inputs(evidence_rows=[_dhcp_row()]), **change)
    def forbidden(*_args, **_kwargs):
        pytest.fail("K1 matcher ran for an incompatible row")
    monkeypatch.setattr(module, "match_k1_records", forbidden)
    output = DeviceFingerprintOriginAssessmentBuilder(inputs).build("dhcp").semantic_payload
    assert "unsupported_evidence_contract" in output["explanation_codes"]
    assert len(output["evidence_refs"]) == 1
    assert not output["knowledge_refs"]
    assert all(not row["candidate_set"] and not row["broad_unresolved_taxon_refs"]
               for row in output["dimension_assessments"])


def test_degraded_compatible_evidence_does_not_run_k1_matcher(monkeypatch):
    import app.device_fingerprint.origin_assessment as module

    inputs = _inputs(evidence_rows=[_dhcp_row(quality_state="degraded")])
    def forbidden(*_args, **_kwargs):
        pytest.fail("K1 matcher ran for a degraded row")
    monkeypatch.setattr(module, "match_k1_records", forbidden)
    output = DeviceFingerprintOriginAssessmentBuilder(inputs).build("dhcp").semantic_payload
    assert "degraded_evidence_no_claim" in output["explanation_codes"]
    assert len(output["evidence_refs"]) == 1
    assert not output["knowledge_refs"]


def test_incompatible_portal_and_tcp_rows_never_reach_k3_or_k2a(monkeypatch):
    import app.device_fingerprint.k3_portal_rules as k3
    import app.device_fingerprint.origin_assessment as module
    from app.device_fingerprint.validation import canonical_json, canonical_sha256

    def forbidden(*_args, **_kwargs):
        pytest.fail("Semantic matcher ran for an incompatible row")

    portal = _with_descriptor(_inputs(evidence_rows=[_portal_row()], origin="portal"),
                              extractor_name="wrong-extractor")
    monkeypatch.setattr(k3, "evaluate_k3_rules", forbidden)
    portal_output = DeviceFingerprintOriginAssessmentBuilder(portal).build("portal").semantic_payload
    assert "unsupported_evidence_contract" in portal_output["explanation_codes"]
    assert len(portal_output["evidence_refs"]) == 1 and not portal_output["knowledge_refs"]

    payload = tcp_v2(ip_df=False, ip_id_zero=False, tcp_sequence_zero=False,
                     tcp_header_length_bytes=20, tcp_option_records=[])
    row = _network_row("tcp", version=2)
    row["payload_json"] = canonical_json(payload)
    row["payload_sha256"] = canonical_sha256(row["payload_json"])
    row["extractor_version"] = "2.0.0"
    tcp = _with_descriptor(_inputs(evidence_rows=[row], origin="tcp"),
                           extractor_version="wrong-version")
    monkeypatch.setattr(module, "match_request", forbidden)
    tcp_output = DeviceFingerprintOriginAssessmentBuilder(tcp).build("tcp").semantic_payload
    assert "unsupported_evidence_contract" in tcp_output["explanation_codes"]
    assert len(tcp_output["evidence_refs"]) == 1 and not tcp_output["knowledge_refs"]


def _dimension_from(output, name):
    return next(row for row in output["dimension_assessments"] if row["dimension_name"] == name)


def test_dhcp_semantic_outcome_dedup_unions_refs_across_different_payloads():
    from tests.device_fingerprint_task04_t01.test_snapshot_service import KNOWN

    variant = dict(KNOWN, maximum_message_size=1400)
    rows = [_dhcp_row(1), _dhcp_row(2, payload=variant)]
    forward = DeviceFingerprintOriginAssessmentBuilder(_inputs(evidence_rows=rows)).build("dhcp")
    reverse = DeviceFingerprintOriginAssessmentBuilder(_inputs(evidence_rows=rows[::-1])).build("dhcp")
    assert forward == reverse
    platform = _dimension_from(forward.semantic_payload, "platform_family")
    assert len(platform["candidate_set"]) == 1
    assert len(platform["candidate_set"][0]["evidence_refs"]) == 2
    assert len(platform["candidate_set"][0]["knowledge_refs"]) == 1


@pytest.mark.parametrize("version,vector_id,dimension,target", [
    (1, "k3.vector.platform.android.sec_ch_ua_platform.v1", "platform_family", "android"),
    (2, "k3.vector.tablet.declared.v2", "device_class", "tablet"),
])
def test_portal_same_semantic_repetition_unions_refs_canonically(version, vector_id, dimension, target):
    rules = build_k3_portal_rule_set_v1().semantic_payload
    normalized = next(row["normalized_input"] for row in rules["test_vectors"]
                      if row["test_vector_id"] == vector_id)
    rows = [_portal_row(1, payload=normalized, version=version),
            _portal_row(2, payload=normalized, version=version)]
    forward = DeviceFingerprintOriginAssessmentBuilder(
        _inputs(evidence_rows=rows, origin="portal")).build("portal")
    reverse = DeviceFingerprintOriginAssessmentBuilder(
        _inputs(evidence_rows=rows[::-1], origin="portal")).build("portal")
    assert forward == reverse
    selected = _dimension_from(forward.semantic_payload, dimension)
    assert selected["selected_canonical_value_id"] == target
    assert len(selected["candidate_set"]) == 1
    candidate = selected["candidate_set"][0]
    assert len(candidate["evidence_refs"]) == 2
    assert len(candidate["knowledge_refs"]) == 1
    assert candidate["evidence_refs"] == sorted(candidate["evidence_refs"], key=lambda ref: ref["evidence_id"])


def test_cross_version_portal_claims_remain_separate_dimensions():
    rules = build_k3_portal_rule_set_v1().semantic_payload
    platform = next(row["normalized_input"] for row in rules["test_vectors"]
                    if row["test_vector_id"] == "k3.vector.platform.android.sec_ch_ua_platform.v1")
    tablet = next(row["normalized_input"] for row in rules["test_vectors"]
                  if row["test_vector_id"] == "k3.vector.tablet.declared.v2")
    rows = [_portal_row(1, payload=platform, version=1),
            _portal_row(2, payload=tablet, version=2)]
    output = DeviceFingerprintOriginAssessmentBuilder(
        _inputs(evidence_rows=rows, origin="portal")).build("portal").semantic_payload
    assert _dimension_from(output, "platform_family")["selected_canonical_value_id"] == "android"
    assert _dimension_from(output, "device_class")["selected_canonical_value_id"] == "tablet"
    assert len(_dimension_from(output, "platform_family")["candidate_set"]) == 1
    assert len(_dimension_from(output, "device_class")["candidate_set"]) == 1


def test_distinct_k3_derivations_are_distinct_but_rule_id_is_not_merge_identity():
    rules = build_k3_portal_rule_set_v1().semantic_payload
    declared = next(row["normalized_input"] for row in rules["test_vectors"]
                    if row["test_vector_id"] == "k3.vector.platform.android.sec_ch_ua_platform.v1")
    mapped = next(row["normalized_input"] for row in rules["test_vectors"]
                  if row["test_vector_id"] == "k3.vector.platform.android.user_agent.v1")
    rows = [_portal_row(1, payload=declared), _portal_row(2, payload=mapped)]
    output = DeviceFingerprintOriginAssessmentBuilder(
        _inputs(evidence_rows=rows, origin="portal")).build("portal").semantic_payload
    platform = _dimension_from(output, "platform_family")
    assert platform["selected_canonical_value_id"] == "android"
    assert platform["claim_derivations"] == ["declared", "deterministic_mapping"]
    assert len(platform["candidate_set"]) == 2

    first, second = (dict(candidate) for candidate in platform["candidate_set"])
    second["claim_derivation"] = first["claim_derivation"]
    merged = _merge_contributions([
        ("portal.k3.semantic-outcomes.v1", "platform_family", first),
        ("portal.k3.semantic-outcomes.v1", "platform_family", second),
    ])
    assert len(merged) == 1
    assert len(merged[0]["evidence_refs"]) == 2
    assert len(merged[0]["knowledge_refs"]) == 2


def _constructor_kwargs(inputs):
    return {
        "evidence_snapshot_content": inputs.evidence_snapshot_content,
        "source_evaluability": inputs.source_evaluability,
        "evidence_adapter_contract_set": inputs.evidence_adapter_contract_set,
        "knowledge_bundle": inputs.knowledge_bundle,
        "knowledge": inputs.knowledge,
    }


def test_closed_dimension_validator_rejects_no_claim_with_candidate_and_unbacked_selection():
    inputs = _inputs(evidence_rows=[_dhcp_row()])
    baseline = DeviceFingerprintOriginAssessmentBuilder(inputs).build("dhcp").semantic_payload
    for field, value in (("internal_state", "no_claim"),
                         ("selected_canonical_value_id", "ios")):
        changed = baseline.copy()
        platform = _dimension_from(changed, "platform_family")
        platform[field] = value
        if field == "internal_state":
            platform["selected_canonical_value_id"] = None
            platform["effective_claim_strength"] = None
        with pytest.raises(DeviceFingerprintValidationError):
            make_origin_assessment(changed, **_constructor_kwargs(inputs))


def test_closed_dimension_validator_rejects_unbacked_out_of_scope_selection():
    inputs = _inputs(evidence_rows=[_dhcp_row()])
    changed = DeviceFingerprintOriginAssessmentBuilder(inputs).build("dhcp").semantic_payload
    platform = _dimension_from(changed, "platform_family")
    platform["internal_state"] = "recognized_out_of_scope"
    platform["selected_canonical_value_id"] = None
    platform["selected_out_of_scope_taxon_ref"] = "unbacked-taxon"
    with pytest.raises(DeviceFingerprintValidationError):
        make_origin_assessment(changed, **_constructor_kwargs(inputs))


def test_closed_dimension_validator_rejects_conflict_and_derivation_mismatch():
    inputs = _inputs(evidence_rows=[_dhcp_row()])
    baseline = DeviceFingerprintOriginAssessmentBuilder(inputs).build("dhcp").semantic_payload
    changed = baseline.copy()
    _dimension_from(changed, "platform_family")["claim_derivations"] = ["declared"]
    with pytest.raises(DeviceFingerprintValidationError):
        make_origin_assessment(changed, **_constructor_kwargs(inputs))

    conflicting = _reduce_claims("platform_family", [
        _candidate("android", "strong", "one"), _candidate("ios", "strong", "two")])
    assert conflicting["internal_state"] == "conflicting"
    changed = baseline.copy()
    changed["dimension_assessments"] = [conflicting if row["dimension_name"] == "platform_family" else row
                                        for row in changed["dimension_assessments"]]
    conflicting["conflict_strength"] = "supporting"
    with pytest.raises(DeviceFingerprintValidationError):
        make_origin_assessment(changed, **_constructor_kwargs(inputs))
    conflicting["conflict_strength"] = "strong"
    conflicting["same_origin_contradiction_records"][0]["incompatible_candidate_keys"] = ["missing"]
    with pytest.raises(DeviceFingerprintValidationError):
        make_origin_assessment(changed, **_constructor_kwargs(inputs))


def test_strong_selected_with_supporting_incompatibility_requires_retained_contradiction():
    inputs = _inputs(evidence_rows=[_dhcp_row()])
    changed = DeviceFingerprintOriginAssessmentBuilder(inputs).build("dhcp").semantic_payload
    platform = _reduce_claims("platform_family", [
        _candidate("android", "strong", "one"), _candidate("ios", "supporting", "two")])
    assert platform["internal_state"] == "resolved"
    platform["same_origin_contradiction_records"] = []
    changed["dimension_assessments"] = [platform if row["dimension_name"] == "platform_family" else row
                                        for row in changed["dimension_assessments"]]
    with pytest.raises(DeviceFingerprintValidationError):
        make_origin_assessment(changed, **_constructor_kwargs(inputs))


@pytest.mark.parametrize("origin", ["tls", "quic"])
def test_ja4_origin_rejects_semantic_knowledge_ref_with_typed_failure(origin):
    inputs = _inputs(evidence_rows=[_network_row(origin)], origin=origin)
    changed = DeviceFingerprintOriginAssessmentBuilder(inputs).build(origin).semantic_payload
    dhcp_inputs = _inputs(evidence_rows=[_dhcp_row()])
    dhcp = DeviceFingerprintOriginAssessmentBuilder(dhcp_inputs).build("dhcp").semantic_payload
    changed["knowledge_refs"] = dhcp["knowledge_refs"]
    with pytest.raises(DeviceFingerprintValidationError):
        make_origin_assessment(changed, **_constructor_kwargs(inputs))


def test_tcp_distinct_normalized_rows_with_same_k2b_outcome_merge_provenance():
    from app.device_fingerprint.validation import canonical_json, canonical_sha256

    first_payload = tcp_v2(ip_df=False, ip_id_zero=False, tcp_sequence_zero=False,
                           tcp_header_length_bytes=20, tcp_option_records=[])
    second_payload = dict(first_payload, observed_ttl=63)
    rows = []
    for number, payload in ((1, first_payload), (2, second_payload)):
        row = _network_row("tcp", version=2, number=number)
        row["payload_json"] = canonical_json(payload)
        row["payload_sha256"] = canonical_sha256(row["payload_json"])
        row["extractor_version"] = "2.0.0"
        rows.append(row)
    forward = DeviceFingerprintOriginAssessmentBuilder(
        _inputs(evidence_rows=rows, origin="tcp")).build("tcp")
    reverse = DeviceFingerprintOriginAssessmentBuilder(
        _inputs(evidence_rows=rows[::-1], origin="tcp")).build("tcp")
    assert forward == reverse
    platform = _dimension_from(forward.semantic_payload, "platform_family")
    assert platform["selected_canonical_value_id"] == "linux"
    assert len(platform["candidate_set"]) == 1
    assert len(platform["candidate_set"][0]["evidence_refs"]) == 2
    assert len(platform["candidate_set"][0]["knowledge_refs"]) == 1


def test_broad_semantic_projection_unions_distinct_evidence_references():
    first = _candidate(evidence_id="one")
    second = _candidate(evidence_id="two")
    entries = []
    for candidate in (first, second):
        entries.append(("dhcp.k1.candidate-set.v1", "device_class", {
            "reference_kind": "BROAD_TAXON", "canonical_taxon_or_source_ref": "mobile",
            "explanation_code": "k1_broad_unresolved",
            "evidence_refs": candidate["evidence_refs"], "knowledge_refs": [],
        }))
    merged = _merge_contributions(entries, broad=True)
    assert len(merged) == 1
    assert len(merged[0]["evidence_refs"]) == 2


def _tcp_health_rows(status="available", reason=None):
    rows = []
    for index in range(12):
        total_minutes = 30 + index * 5
        stamp = f"2026-09-15T{11 + total_minutes // 60:02d}:{total_minutes % 60:02d}:00.000Z"
        row = health(index + 1, observed_at=stamp)
        row.update(source_kind="tcp_syn", status=status, reason_code=reason)
        rows.append(row)
    return rows


@pytest.mark.parametrize("status,reason,expected_aggregate", [
    ("unavailable", "capture_interface_unavailable", "not_evaluable"),
    ("available", None, "evaluable"),
])
def test_disabled_tcp_zero_rows_precedes_real_t02_coverage(status, reason, expected_aggregate):
    inputs = _inputs(origin="tcp", tcp_disabled=True,
                     health_rows=_tcp_health_rows(status, reason))
    assert [entry["aggregate_evaluability_state"] for entry in
            inputs.source_evaluability.semantic_payload["source_entries"]] == [expected_aggregate]
    output = DeviceFingerprintOriginAssessmentBuilder(inputs).build("tcp").semantic_payload
    assert not output["evidence_refs"]
    for dimension in output["dimension_assessments"]:
        assert dimension["internal_state"] == "no_claim"
        assert dimension["selected_canonical_value_id"] is None
        assert dimension["selected_out_of_scope_taxon_ref"] is None
        assert dimension["effective_claim_strength"] is None
        assert dimension["conflict_strength"] is None
        assert not dimension["candidate_set"]
        assert not dimension["same_origin_contradiction_records"]
        assert not dimension["claim_derivations"]
        assert "origin_runtime_disabled" in dimension["explanation_codes"]


def test_disabled_tcp_zero_rows_unknown_coverage_is_no_claim():
    inputs = _inputs(origin="tcp", tcp_disabled=True)
    assert [entry["aggregate_evaluability_state"] for entry in
            inputs.source_evaluability.semantic_payload["source_entries"]] == ["unknown"]
    output = DeviceFingerprintOriginAssessmentBuilder(inputs).build("tcp").semantic_payload
    assert all(row["internal_state"] == "no_claim" for row in output["dimension_assessments"])
    assert "origin_runtime_disabled" in output["explanation_codes"]


def test_enabled_tcp_zero_rows_preserves_not_evaluable_coverage():
    inputs = _inputs(origin="tcp", health_rows=_tcp_health_rows(
        "unavailable", "capture_interface_unavailable"))
    assert [entry["aggregate_evaluability_state"] for entry in
            inputs.source_evaluability.semantic_payload["source_entries"]] == ["not_evaluable"]
    output = DeviceFingerprintOriginAssessmentBuilder(inputs).build("tcp").semantic_payload
    assert all(row["internal_state"] == "not_evaluable" for row in output["dimension_assessments"])


def test_disabled_tcp_keeps_valid_v2_audit_row_without_invoking_any_k2_matcher(monkeypatch):
    import app.device_fingerprint.origin_assessment as module
    from app.device_fingerprint.validation import canonical_json, canonical_sha256

    normalized = tcp_v2(ip_df=False, ip_id_zero=False, tcp_sequence_zero=False,
                        tcp_header_length_bytes=20, tcp_option_records=[])
    row = _network_row("tcp", version=2)
    row["payload_json"] = canonical_json(normalized)
    row["payload_sha256"] = canonical_sha256(row["payload_json"])
    row["extractor_version"] = "2.0.0"
    inputs = _inputs(evidence_rows=[row], origin="tcp", tcp_disabled=True,
                     health_rows=_tcp_health_rows())

    def forbidden(*_args, **_kwargs):
        pytest.fail("Disabled TCP invoked semantic K2A/K2B matcher")

    for name in ("adapt_tcp_syn_v2", "parse_request_signature", "match_request"):
        monkeypatch.setattr(module, name, forbidden)
    output = DeviceFingerprintOriginAssessmentBuilder(inputs).build("tcp").semantic_payload
    assert len(output["evidence_refs"]) == 1
    assert all(row["internal_state"] == "no_claim" and not row["candidate_set"]
               for row in output["dimension_assessments"])
    assert "origin_runtime_disabled" in output["explanation_codes"]


def test_disabled_tcp_health_input_order_has_stable_artifact_identity():
    rows = _tcp_health_rows("unavailable", "capture_interface_unavailable")
    forward = _inputs(origin="tcp", tcp_disabled=True, health_rows=rows)
    reverse = _inputs(origin="tcp", tcp_disabled=True, health_rows=rows[::-1])
    first = DeviceFingerprintOriginAssessmentBuilder(forward).build("tcp")
    second = DeviceFingerprintOriginAssessmentBuilder(reverse).build("tcp")
    assert first.artifact_id == second.artifact_id
    assert first.content_sha256 == second.content_sha256
