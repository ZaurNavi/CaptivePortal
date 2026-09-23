"""Closed concrete edges, deterministic ordering, and frozen schema templates."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.device_fingerprint.artifact_content import ArtifactRef, make_artifact_content
from app.device_fingerprint.artifact_dependency_graph import (
    FOUNDATION_TYPES, TASK04_SPECIFIC_TYPES, ArtifactDependencyGraphError,
    ArtifactDependencyNode, analyze_artifact_dependency_graph,
    build_concrete_artifact_graph, build_foundation_schema_template_graph,
    build_required_cycle_regression_fixtures, build_task04_schema_template_graph,
    extract_direct_artifact_refs, matches_exact_template_authority,
)
from app.device_fingerprint.runtime_profile_artifacts import (
    make_runtime_profile_activation_record, make_runtime_profile_validity_record,
)


def _ref(content):
    return ArtifactRef(content.artifact_id, content.content_sha256).as_dict()


def test_nested_closed_refs_are_extracted_once_in_canonical_order():
    first = make_artifact_content("SyntheticFirst", {"fixture": 1})
    second = make_artifact_content("SyntheticSecond", {"fixture": 2})
    parent = make_artifact_content("SyntheticParent", {
        "array": [{"nested": _ref(second)}, _ref(first), _ref(second)],
        "arbitrary_record_id": first.artifact_id,
        "arbitrary_record_digest": first.content_sha256,
    })
    refs = extract_direct_artifact_refs(parent)
    assert {ref.artifact_id for ref in refs} == {first.artifact_id, second.artifact_id}
    assert [ref.artifact_id for ref in refs] == sorted(ref.artifact_id for ref in refs)
    assert build_concrete_artifact_graph([parent, second, first]) == build_concrete_artifact_graph(
        [first, parent, second])


def test_raw_runtime_pairs_are_artifact_edges_but_history_uuids_are_not():
    def typed(kind, digit):
        digest = digit * 64
        return f"{kind}:v1:sha256:{digest}", digest

    profile, profile_digest = typed("FoundationRuntimeProfile", "1")
    rpm, rpm_digest = typed("RuntimeProfileAdmissionManifest", "2")
    predecessor, predecessor_digest = typed("FoundationRuntimeProfile", "3")
    activation_id = "00000000-0000-4000-8000-000000000001"
    activation = make_runtime_profile_activation_record({
        "activation_contract_version": 1, "activation_record_id": activation_id,
        "profile_kind": "foundation", "runtime_profile_id": profile,
        "runtime_profile_digest": profile_digest,
        "runtime_profile_admission_manifest_id": rpm,
        "runtime_profile_admission_manifest_digest": rpm_digest,
        "previous_activation_record_id": "00000000-0000-4000-8000-000000000003",
        "previous_active_profile_id": predecessor,
        "previous_active_profile_digest": predecessor_digest,
        "activated_at_utc": "2026-09-20T00:00:00.000Z",
        "activation_reason_update_class": "ROLLBACK_REACTIVATION",
        "activation_result": "ACTIVE",
        "activation_generation_id": "00000000-0000-4000-8000-000000000002",
    })
    validity = make_runtime_profile_validity_record({
        "runtime_profile_validity_contract_version": 1,
        "validity_record_id": "00000000-0000-4000-8000-000000000004",
        "profile_kind": "foundation", "runtime_profile_id": profile,
        "runtime_profile_digest": profile_digest,
        "activation_record_id": activation_id,
        "state": "ACTIVE", "reason_code": "ACTIVATED",
        "effective_at_utc": "2026-09-20T00:00:00.000Z",
        "inflight_commit_rule": "ALLOW_PINNED_INFLIGHT",
        "previous_validity_record_id": "00000000-0000-4000-8000-000000000005",
    })
    assert {ref.artifact_id for ref in extract_direct_artifact_refs(activation)} == {
        profile, rpm, predecessor}
    assert {ref.artifact_id for ref in extract_direct_artifact_refs(validity)} == {profile}
    assert make_runtime_profile_activation_record(activation.semantic_payload) == activation
    assert make_runtime_profile_validity_record(validity.semantic_payload) == validity
    assert activation_id not in {ref.artifact_id for ref in extract_direct_artifact_refs(activation)}


def test_frozen_origin_knowledge_and_evidence_raw_refs_are_not_arbitrary_pairs():
    def typed(kind, digit):
        digest = digit * 64
        return {"artifact_id": f"{kind}:v1:sha256:{digest}", "content_sha256": digest}

    origin = typed("OriginRuntimeAdmission", "1")
    ttl = typed("TTLCapturePlacementProof", "2")
    emitter = typed("SourceHealthEmitterContract", "3")
    bundle = typed("KnowledgeBundle", "4")
    provenance = typed("KnowledgeProvenanceManifest", "5")
    adapter = typed("EvidenceAdapterContractSet", "6")
    ignored = typed("Ignored", "7")
    probe = make_artifact_content("FF6RawReferenceProbe", {
        "origin_runtime_admission": {**origin,
                                     "ttl_capture_placement_proof": ttl,
                                     "source_health_emitter_contract": emitter},
        "origin_assessment": {"knowledge_refs": [{
            "knowledge_bundle_id": bundle["artifact_id"],
            "knowledge_bundle_digest": bundle["content_sha256"],
            "canonical_knowledge_record_id": "fixture.record",
            "knowledge_provenance_id": provenance["artifact_id"],
            "knowledge_provenance_digest": provenance["content_sha256"],
            "rule_or_source_record_identity": "fixture.source",
        }], "evidence_refs": [{
            "evidence_id": "00000000-0000-4000-8000-000000000008",
            "payload_sha256": "a" * 64, "feature_schema_version": 1,
            "adapter_contract_id": adapter["artifact_id"],
            "adapter_contract_digest": adapter["content_sha256"],
        }]},
        "classification_result": {"platform_result": {"knowledge_references": [{
            "knowledge_bundle_id": bundle["artifact_id"],
            "knowledge_bundle_digest": bundle["content_sha256"],
            "canonical_knowledge_record_id": "fixture.record",
            "knowledge_provenance_id": provenance["artifact_id"],
            "knowledge_provenance_digest": provenance["content_sha256"],
            "rule_or_source_record_identity": "fixture.source",
        }]}},
        "some_id": ignored["artifact_id"], "some_digest": ignored["content_sha256"],
    })
    expected = {item["artifact_id"] for item in (origin, ttl, emitter, bundle, provenance, adapter)}
    assert {ref.artifact_id for ref in extract_direct_artifact_refs(probe)} == expected
    assert ignored["artifact_id"] not in expected
    with pytest.raises(ArtifactDependencyGraphError) as error:
        extract_direct_artifact_refs(make_artifact_content("FF6RawReferenceProbe", {
            "knowledge_refs": [{
                "knowledge_bundle_id": bundle["artifact_id"],
                "knowledge_bundle_digest": "8" * 64,
                "canonical_knowledge_record_id": "fixture.record",
                "knowledge_provenance_id": provenance["artifact_id"],
                "knowledge_provenance_digest": provenance["content_sha256"],
                "rule_or_source_record_identity": "fixture.source",
            }],
        }))
    assert error.value.reason_code == "artifact_dependency_digest_mismatch"
    with pytest.raises(ArtifactDependencyGraphError) as error:
        extract_direct_artifact_refs(make_artifact_content("FF6RawReferenceProbe", {
            "origin_runtime_admission": {**typed("WrongArtifact", "9"),
                                         "ttl_capture_placement_proof": ttl},
        }))
    assert error.value.reason_code == "artifact_dependency_graph_invalid"


def test_missing_and_mismatched_concrete_dependencies_fail_closed():
    target = make_artifact_content("SyntheticTarget", {"fixture": 1})
    dependent = make_artifact_content("SyntheticDependent", {"target": _ref(target)})
    with pytest.raises(ArtifactDependencyGraphError) as error:
        build_concrete_artifact_graph([dependent])
    assert error.value.reason_code == str(error.value) == "artifact_dependency_missing"
    bad = make_artifact_content("SyntheticDependent", {"target": {
        "artifact_id": target.artifact_id, "content_sha256": "0" * 64}})
    with pytest.raises(ArtifactDependencyGraphError) as error:
        build_concrete_artifact_graph([target, bad])
    assert error.value.reason_code == "artifact_dependency_digest_mismatch"
    with pytest.raises(ArtifactDependencyGraphError) as error:
        extract_direct_artifact_refs(make_artifact_content("SyntheticDependent", {
            "first": _ref(target), "second": {"artifact_id": target.artifact_id,
                                                "content_sha256": "1" * 64}}))
    assert error.value.reason_code == "artifact_dependency_digest_mismatch"


def test_deterministic_topology_and_inventory_ignore_input_order():
    a = make_artifact_content("SyntheticA", {"fixture": "A"})
    b = make_artifact_content("SyntheticB", {"fixture": "B"})
    c = make_artifact_content("SyntheticC", {"a": _ref(a), "b": _ref(b)})
    forward = analyze_artifact_dependency_graph(build_concrete_artifact_graph([a, b, c]))
    reverse = analyze_artifact_dependency_graph(build_concrete_artifact_graph([c, b, a]))
    assert forward == reverse
    assert forward.topological_order[-1] == c.artifact_id
    assert forward.topological_order[:2] == tuple(sorted([a.artifact_id, b.artifact_id]))
    for dependent, dependency in forward.edges:
        assert forward.topological_order.index(dependency) < forward.topological_order.index(dependent)


def test_graph_nodes_reject_self_edges_duplicate_dependencies_and_missing_targets():
    with pytest.raises(ArtifactDependencyGraphError):
        ArtifactDependencyNode("not-an-artifact-id", "A", "CONCRETE", ())
    with pytest.raises(ArtifactDependencyGraphError):
        ArtifactDependencyNode("template:a", "A", "TEMPLATE", ("template:a",))
    with pytest.raises(ArtifactDependencyGraphError):
        ArtifactDependencyNode("template:a", "A", "TEMPLATE", ("template:b", "template:b"))
    node = ArtifactDependencyNode("template:a", "A", "TEMPLATE", ())
    with pytest.raises(ArtifactDependencyGraphError) as error:
        analyze_artifact_dependency_graph([node, node])
    assert error.value.reason_code == "artifact_dependency_graph_invalid"
    with pytest.raises(ArtifactDependencyGraphError) as error:
        analyze_artifact_dependency_graph([
            ArtifactDependencyNode("template:a", "A", "TEMPLATE", ("template:b",))])
    assert error.value.reason_code == "artifact_dependency_missing"


@pytest.mark.parametrize("name", [
    "gate_output", "runtime_profile_lineage", "capability_gate",
    "knowledge_freshness_provenance", "mutual_artifact",
])
def test_every_required_cycle_has_deterministic_witness(name):
    fixture = build_required_cycle_regression_fixtures()[name]
    if name != "mutual_artifact":
        positive = (build_task04_schema_template_graph() if name == "runtime_profile_lineage"
                    else build_foundation_schema_template_graph())
        assert {node.node_id for node in fixture} == {node.node_id for node in positive}
        added = {(node.node_id, dependency) for node in fixture
                 for dependency in node.direct_dependency_ids} - {
                     (node.node_id, dependency) for node in positive
                     for dependency in node.direct_dependency_ids}
        assert len(added) == 1
    witnesses = []
    for nodes in (fixture, tuple(reversed(fixture))):
        with pytest.raises(ArtifactDependencyGraphError) as error:
            analyze_artifact_dependency_graph(nodes)
        assert error.value.reason_code == str(error.value) == "artifact_dependency_cycle"
        witnesses.append(error.value.cycle_witness)
    assert witnesses[0] == witnesses[1]
    assert witnesses[0][0] == witnesses[0][-1]


def test_foundation_backref_is_authority_failure_not_cycle():
    positive = build_foundation_schema_template_graph()
    mutation = build_required_cycle_regression_fixtures()["foundation_profile_lineage"]
    assert matches_exact_template_authority(positive, "foundation")
    assert not matches_exact_template_authority(mutation, "foundation")
    assert len(analyze_artifact_dependency_graph(mutation).topological_order) == len(mutation)
    added = {(node.node_id, dependency) for node in mutation
             for dependency in node.direct_dependency_ids} - {
                 (node.node_id, dependency) for node in positive
                 for dependency in node.direct_dependency_ids}
    assert added == {("template:foundation:FoundationRuntimeProfile",
                      "template:foundation:FoundationAdmissionManifest")}


def test_exact_authority_rejects_missing_edge_and_missing_variant_node():
    positive = build_foundation_schema_template_graph()
    owner = "template:foundation:ClassificationPolicy"
    target = "template:foundation:EvidenceAdapterContractSet"
    missing_edge = tuple(replace(node, direct_dependency_ids=tuple(
        dep for dep in node.direct_dependency_ids if dep != target))
        if node.node_id == owner else node for node in positive)
    assert not matches_exact_template_authority(missing_edge, "foundation")
    missing_node = tuple(node for node in positive if node.node_id != (
        "template:foundation:KnowledgeProvenanceManifest:K4"))
    assert not matches_exact_template_authority(missing_node, "foundation")
    task04 = build_task04_schema_template_graph()
    assert matches_exact_template_authority(task04, "task04")
    assert not matches_exact_template_authority(task04[:-1], "task04")


def test_foundation_template_exact_coverage_and_edges():
    nodes = build_foundation_schema_template_graph()
    analysis = analyze_artifact_dependency_graph(nodes)
    by_id = {node.node_id: node for node in nodes}
    f = lambda name: "template:foundation:" + name
    assert {node.artifact_type for node in nodes} == FOUNDATION_TYPES
    assert matches_exact_template_authority(nodes, "foundation")
    assert len(analysis.topological_order) == len(nodes)
    assert f("FoundationAdmissionManifest") not in by_id[f("FoundationRuntimeProfile")].direct_dependency_ids
    assert by_id[f("OriginRuntimeAdmission")].direct_dependency_ids == (f("TTLCapturePlacementProof"),)
    for slot in ("K1", "K2B", "K4"):
        assert set(by_id[f(f"KnowledgeProvenanceManifest:{slot}")].direct_dependency_ids) == {
            f(f"KnowledgeFreshnessPolicy:{slot}"), f(f"SourceGovernanceRecord:{slot}")}
        assert by_id[f(f"CanonicalKnowledgeRecordSet:{slot}")].direct_dependency_ids == (
            f(f"KnowledgeProvenanceManifest:{slot}"),)
    assert set(by_id[f("KnowledgeProvenanceManifest:K3")].direct_dependency_ids) == {
        f("K3PortalRuleSet"), f("ClassificationTaxonomy")}
    assert f("KnowledgeProvenanceManifest:K1") in by_id[f("KnowledgeBundle")].direct_dependency_ids
    assert f("CapabilityDisposition") in by_id[f("PrerequisiteGateResultManifest")].direct_dependency_ids
    assert by_id[f("CapabilityDisposition")].direct_dependency_ids == ()
    assert by_id[f("GateProofArtifact")].direct_dependency_ids == ()
    assert by_id[f("Task01HealthRetentionContract")].direct_dependency_ids == (
        f("SourceHealthPolicy"),)
    assert by_id[f("EvidenceAdapterContractSet")].direct_dependency_ids == (
        f("EvidenceSchemaRegistryContract"),)
    assert set(by_id[f("ClassificationPolicy")].direct_dependency_ids) == {
        f("ClassificationTaxonomy"), f("AliasMapping"), f("EvidenceAdapterContractSet")}
    for owner in ("EvidenceSourceBindingTimeline", "SourceHealthPolicy"):
        assert set(by_id[f(owner)].direct_dependency_ids) == {
            f(f"SourceHealthEmitterContract:{slot}") for slot in (
                "NETWORK", "PORTAL_HISTORICAL", "PORTAL_PERIODIC")}
    assert f("GateResultManifest") not in by_id[f("RuntimeProfileAdmissionManifest")].direct_dependency_ids
    assert all(not dependency.startswith("template:task04:") for node in nodes
               for dependency in node.direct_dependency_ids)
    bundle = set(by_id[f("KnowledgeBundle")].direct_dependency_ids)
    assert len(bundle) == 16
    assert set(by_id[f("GateResultManifest")].direct_dependency_ids) >= {
        f("PrerequisiteGateResultManifest"), f("CapabilityDisposition"),
        f("FoundationAdmissionManifest"), f("RuntimeProfileAdmissionManifest")}
    order = analysis.topological_order
    for chain in (("TTLCapturePlacementProof", "OriginRuntimeAdmission", "FoundationAdmissionManifest"),
                  ("FoundationRuntimeProfile", "RuntimeProfileAdmissionManifest",
                   "RuntimeProfileActivationRecord", "GateResultManifest")):
        assert [order.index(f(name)) for name in chain] == sorted(order.index(f(name)) for name in chain)


def test_task04_template_exact_specific_coverage_and_bootstrap_order():
    nodes = build_task04_schema_template_graph()
    analysis = analyze_artifact_dependency_graph(nodes)
    by_id = {node.node_id: node for node in nodes}
    t = lambda name: "template:task04:" + name
    f = lambda name: "template:foundation:" + name
    assert {node.artifact_type for node in nodes}.difference(FOUNDATION_TYPES) == TASK04_SPECIFIC_TYPES
    assert matches_exact_template_authority(nodes, "task04")
    assert by_id[t("ClassificationRuntimeProfile")].direct_dependency_ids == tuple(sorted((
        f("FoundationRuntimeProfile"), f("KnowledgeBundle"), f("ClassificationPolicy"),
        f("EvidenceAdapterContractSet"), t("ClassifierArtifactManifest"))))
    assert t("Task04AcceptanceManifest") not in by_id[t("ClassificationRuntimeProfile")].direct_dependency_ids
    assert t("ClassificationRuntimeProfile") in by_id[t("Task04AcceptanceManifest")].direct_dependency_ids
    assert t("GateResultManifest") not in by_id[t("RuntimeProfileAdmissionManifest")].direct_dependency_ids
    assert t("ClassificationRequestManifest") not in by_id[t("ClassificationResult")].direct_dependency_ids
    assert set(by_id[t("EvidenceSnapshotContent")].direct_dependency_ids) == {
        f("EvidenceSourceBindingTimeline"), f("BindingClockPolicy"),
        f("EvidenceSchemaRegistryContract"), f("OriginRuntimeAdmission"),
        f("TTLCapturePlacementProof"), *(f(f"SourceHealthEmitterContract:{slot}") for slot in (
            "NETWORK", "PORTAL_HISTORICAL", "PORTAL_PERIODIC"))}
    assert set(by_id[t("ClassificationRequestManifest")].direct_dependency_ids) == {
        t("EvidenceSnapshotContent"), t("SourceEvaluability"), f("KnowledgeBundle"),
        f("ClassificationPolicy"), f("EvidenceAdapterContractSet"),
        t("ClassifierArtifactManifest")}
    assert set(by_id[t("ClassificationResult")].direct_dependency_ids) == {
        f("ClassificationPolicy"), f("KnowledgeBundle"), t("ClassifierArtifactManifest"),
        t("EvidenceSnapshotContent"), t("SourceEvaluability"), t("OriginAssessment"),
        *(f(f"KnowledgeProvenanceManifest:{slot}") for slot in ("K1", "K2B", "K3", "K4"))}
    assert set(by_id[t("OriginAssessment")].direct_dependency_ids) == {
        t("EvidenceSnapshotContent"), t("SourceEvaluability"), f("KnowledgeBundle"),
        f("EvidenceAdapterContractSet"),
        *(f(f"KnowledgeProvenanceManifest:{slot}") for slot in ("K1", "K2B", "K3", "K4"))}
    assert set(by_id[t("Task04AcceptanceManifest")].direct_dependency_ids) == {
        f("FoundationAdmissionManifest"), t("ClassifierArtifactManifest"),
        t("ClassificationRuntimeProfile"), t("PrerequisiteGateResultManifest"),
        t("ProductValidationComparisonRecord")}
    assert set(by_id[t("RuntimeProfileAdmissionManifest")].direct_dependency_ids) == {
        t("ClassificationRuntimeProfile"), f("FoundationAdmissionManifest"),
        t("Task04AcceptanceManifest"), f("RuntimeProfileAdmissionManifest"),
        t("PrerequisiteGateResultManifest")}
    assert len(analysis.topological_order) == len(nodes)
    assert set(by_id[t("GateResultManifest")].direct_dependency_ids) == {
        t("PrerequisiteGateResultManifest"), t("ProductValidationComparisonRecord"),
        t("Task04AcceptanceManifest"), t("RuntimeProfileAdmissionManifest")}
    chain = [f("KnowledgeFreshnessPolicy:K1"), f("KnowledgeProvenanceManifest:K1"),
             f("KnowledgeBundle"), t("ClassificationRuntimeProfile"),
             t("Task04AcceptanceManifest"), t("RuntimeProfileAdmissionManifest"),
             t("GateResultManifest")]
    assert [analysis.topological_order.index(node_id) for node_id in chain] == sorted(
        analysis.topological_order.index(node_id) for node_id in chain)
