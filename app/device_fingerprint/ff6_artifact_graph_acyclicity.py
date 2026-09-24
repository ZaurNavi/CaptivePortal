"""Disposable, synthetic F-F6 graph proof and gate materialization."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from .artifact_content import ArtifactContent, ArtifactRef, canonical_artifact_json, canonical_set, make_artifact_content
from .artifact_dependency_graph import (
    FOUNDATION_TYPES, TASK04_SPECIFIC_TYPES, ArtifactDependencyAnalysis,
    ArtifactDependencyGraphError, analyze_artifact_dependency_graph,
    build_concrete_artifact_graph, build_foundation_schema_template_graph,
    build_required_cycle_regression_fixtures, build_task04_schema_template_graph,
    extract_direct_artifact_refs, matches_exact_template_authority,
)
from .fe5_external_knowledge import build_satori_k1_freshness_policy
from .foundation_gate_artifacts import make_gate_result_manifest
from .gate_proof_artifacts import make_gate_proof_artifact
from .k2a_conformance_artifacts import make_source_governance_record
from .knowledge_artifacts import (
    make_external_knowledge_provenance_manifest, make_knowledge_freshness_policy,
)
from .models import DeviceFingerprintValidationError
from .runtime_profile_artifacts import (
    make_foundation_runtime_profile, make_runtime_profile_activation_record,
    make_runtime_profile_admission_manifest, make_runtime_profile_validity_record,
)
from .taxonomy_artifacts import (
    build_alias_mapping_v1, build_classification_taxonomy_v1,
    make_alias_mapping, make_classification_taxonomy,
)


_LABELS = (
    "artifact_dependency_graph", "artifact_cycle_test_fixtures",
    "artifact_topological_ordering",
)
SYNTHETIC_TEST = "SYNTHETIC_TEST"
FOUNDATION_CANDIDATE = "FOUNDATION_CANDIDATE"

_COMMON_CHECKS = (
    "concrete_graph_acyclic", "concrete_dependency_closure", "concrete_digest_binding",
    "raw_reference_extraction_complete",
    "deterministic_topological_order", "foundation_schema_coverage_complete",
    "foundation_exact_edge_authority", "foundation_runtime_profile_admission_backref_rejected",
    "foundation_template_acyclic", "foundation_runtime_profile_has_no_admission_backref",
    "foundation_rpm_prerequisite_only", "foundation_gate_output_direction_correct",
    "knowledge_freshness_direction_correct", "capability_disposition_direction_correct",
    "task04_schema_coverage_complete", "task04_exact_edge_authority", "task04_template_acyclic",
    "candidate_crp_precedes_acceptance_manifest",
    "classification_runtime_profile_has_no_acceptance_backref",
    "task04_rpm_prerequisite_only", "task04_gate_output_direction_correct",
    "history_uuid_refs_not_artifact_edges", "gate_output_cycle_regression_detected",
    "runtime_profile_lineage_cycle_regression_detected",
    "capability_gate_cycle_regression_detected",
    "knowledge_freshness_provenance_cycle_regression_detected",
    "mutual_artifact_cycle_regression_detected",
)
SYNTHETIC_REQUIRED_CHECKS = frozenset((*_COMMON_CHECKS, "registered_fixture_schema_valid"))
CANDIDATE_REQUIRED_CHECKS = frozenset((*_COMMON_CHECKS, "foundation_candidate_graph_analyzed"))
_REASON = {key: "artifact_dependency_graph_invalid" for key in (
    SYNTHETIC_REQUIRED_CHECKS | CANDIDATE_REQUIRED_CHECKS)}
_REASON.update({
    "concrete_graph_acyclic": "artifact_dependency_cycle",
    "concrete_dependency_closure": "artifact_dependency_missing",
    "concrete_digest_binding": "artifact_dependency_digest_mismatch",
    "foundation_candidate_graph_analyzed": "foundation_candidate_graph_required",
    "deterministic_topological_order": "artifact_topological_order_unavailable",
    "foundation_schema_coverage_complete": "foundation_schema_template_invalid",
    "foundation_exact_edge_authority": "foundation_schema_template_invalid",
    "foundation_runtime_profile_admission_backref_rejected": "foundation_schema_template_invalid",
    "foundation_template_acyclic": "artifact_dependency_cycle",
    "foundation_runtime_profile_has_no_admission_backref": "foundation_schema_template_invalid",
    "foundation_rpm_prerequisite_only": "foundation_schema_template_invalid",
    "foundation_gate_output_direction_correct": "foundation_schema_template_invalid",
    "knowledge_freshness_direction_correct": "foundation_schema_template_invalid",
    "capability_disposition_direction_correct": "foundation_schema_template_invalid",
    "task04_schema_coverage_complete": "task04_schema_template_invalid",
    "task04_exact_edge_authority": "task04_schema_template_invalid",
    "task04_template_acyclic": "artifact_dependency_cycle",
    "candidate_crp_precedes_acceptance_manifest": "task04_schema_template_invalid",
    "classification_runtime_profile_has_no_acceptance_backref": "task04_schema_template_invalid",
    "task04_rpm_prerequisite_only": "task04_schema_template_invalid",
    "task04_gate_output_direction_correct": "task04_schema_template_invalid",
    "history_uuid_refs_not_artifact_edges": "artifact_dependency_graph_invalid",
    **{key: "artifact_dependency_cycle" for key in _COMMON_CHECKS[-5:]},
})


@dataclass(frozen=True, slots=True)
class FF6ScenarioExecution:
    execution_mode: str
    concrete_graph: dict[str, Any]
    foundation_template_graph: dict[str, Any]
    task04_template_graph: dict[str, Any]
    cycle_test_fixtures: dict[str, Any]
    topological_orderings: dict[str, list[str]]
    concrete_artifact_refs: tuple[dict[str, str], ...]
    checks: dict[str, bool]
    failure_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FF6GateExecution:
    gate_proof_artifact: ArtifactContent
    gate_result_manifest: ArtifactContent
    failure_reasons: tuple[str, ...]


def _ref(content: ArtifactContent) -> dict[str, str]:
    return ArtifactRef(content.artifact_id, content.content_sha256).as_dict()


def _document(analysis: ArtifactDependencyAnalysis) -> dict[str, Any]:
    return {
        "nodes": [{"node_id": item.node_id, "artifact_type": item.artifact_type,
                   "node_kind": item.node_kind,
                   "direct_dependency_ids": list(item.direct_dependency_ids)}
                  for item in analysis.nodes],
        "edges": [list(edge) for edge in analysis.edges],
        "topological_order": list(analysis.topological_order),
    }


def _reason(callback) -> str | None:
    try:
        callback()
    except ArtifactDependencyGraphError as exc:
        return exc.reason_code
    return None


def _fixtures() -> tuple[ArtifactContent, ...]:
    """Closed-world, builder-validated synthetic inputs; no external corpus."""
    taxonomy = build_classification_taxonomy_v1()
    alias = build_alias_mapping_v1()
    freshness = build_satori_k1_freshness_policy()
    governance = make_source_governance_record({
        "governance_contract_version": 1,
        "source_name": "synthetic FF6 source", "source_provenance": "retained test fixture",
        "license_identifier": "test-only", "license_source_reference": "test-only",
        "license_text_sha256": None, "local_storage_status": "STORED_LOCAL",
        "modification_import_status": "IMPORTED_NORMALIZED",
        "redistribution_status": "ALLOWED", "attribution_requirement": "NOT_REQUIRED",
        "commercial_use_status": "ALLOWED", "review_basis_semantics": "test-only",
        "unresolved_restrictions": [],
    })
    provenance = make_external_knowledge_provenance_manifest({
        "provenance_contract_version": 1, "provenance_kind": "external",
        "source_artifact_sha256": "a" * 64,
        "source_governance_record": _ref(governance),
        "retrieved_at_utc": "2026-09-20T00:00:00.000Z",
        "source_provider_version_metadata": "synthetic fixture revision 1",
        "knowledge_freshness_policy": _ref(freshness),
        "importer_identity": "ff6-fixture-importer", "importer_version": "1.0.0",
    })
    return taxonomy, alias, freshness, governance, provenance


def _fixture_schemas_valid(contents: tuple[ArtifactContent, ...]) -> bool:
    builders = {
        "ClassificationTaxonomy": make_classification_taxonomy,
        "AliasMapping": make_alias_mapping,
        "KnowledgeFreshnessPolicy": make_knowledge_freshness_policy,
        "SourceGovernanceRecord": make_source_governance_record,
        "KnowledgeProvenanceManifest": make_external_knowledge_provenance_manifest,
    }
    try:
        return all(builders[item.artifact_type](item.semantic_payload) == item for item in contents)
    except (DeviceFingerprintValidationError, KeyError, TypeError, ValueError):
        return False


def _raw_reference_probe() -> bool:
    """Exercise registered runtime shapes and frozen Task-04 raw-reference shapes."""
    digest = "1" * 64
    def typed(kind: str) -> dict[str, str]:
        return {"artifact_id": f"{kind}:v1:sha256:{digest}", "content_sha256": digest}

    profile = make_foundation_runtime_profile({
        "foundation_profile_contract_version": 1,
        "classification_foundation_valid_from_utc": "2026-09-20T00:00:00.000Z",
        **{field: typed(kind) for field, kind in (
            ("evidence_source_binding_timeline", "EvidenceSourceBindingTimeline"),
            ("binding_clock_policy", "BindingClockPolicy"),
            ("source_health_policy", "SourceHealthPolicy"),
            ("snapshot_content_policy", "SnapshotContentPolicy"),
            ("snapshot_execution_policy", "SnapshotExecutionPolicy"),
            ("evidence_schema_registry_contract", "EvidenceSchemaRegistryContract"),
            ("task01_health_retention_contract", "Task01HealthRetentionContract"),
            ("origin_runtime_admission", "OriginRuntimeAdmission"))},
        "source_health_emitter_contracts": [], "ttl_capture_placement_proof": None,
        "snapshot_contract_version": 1,
    })
    rpm = make_runtime_profile_admission_manifest({
        "runtime_profile_admission_contract_version": 1, "profile_kind": "foundation",
        "candidate_profile": _ref(profile), "previous_active_profile": None,
        "expected_previous_activation_record_id": None,
        "expected_previous_activation_generation_id": None,
        "update_class": "INITIAL_FOUNDATION", "prerequisite_gate_results": [],
        "compatibility_validation_result": "PASS",
        "candidate_repository_commit_sha": "a" * 40,
        "candidate_repository_tree_sha": "b" * 40,
        "foundation_admission_manifest": typed("FoundationAdmissionManifest"),
        "task04_acceptance_manifest": None,
        "foundation_runtime_profile_admission_manifest": None,
    })
    activation_id = "00000000-0000-4000-8000-000000000001"
    activation = make_runtime_profile_activation_record({
        "activation_contract_version": 1, "activation_record_id": activation_id,
        "profile_kind": "foundation", "runtime_profile_id": profile.artifact_id,
        "runtime_profile_digest": profile.content_sha256,
        "runtime_profile_admission_manifest_id": rpm.artifact_id,
        "runtime_profile_admission_manifest_digest": rpm.content_sha256,
        "previous_activation_record_id": None,
        "previous_active_profile_id": None, "previous_active_profile_digest": None,
        "activated_at_utc": "2026-09-20T00:00:00.000Z",
        "activation_reason_update_class": "INITIAL_FOUNDATION",
        "activation_result": "ACTIVE",
        "activation_generation_id": "00000000-0000-4000-8000-000000000002",
    })
    validity = make_runtime_profile_validity_record({
        "runtime_profile_validity_contract_version": 1,
        "validity_record_id": "00000000-0000-4000-8000-000000000003",
        "profile_kind": "foundation", "runtime_profile_id": profile.artifact_id,
        "runtime_profile_digest": profile.content_sha256,
        "activation_record_id": activation_id, "state": "ACTIVE", "reason_code": "ACTIVATED",
        "effective_at_utc": "2026-09-20T00:00:00.000Z",
        "inflight_commit_rule": "ALLOW_PINNED_INFLIGHT",
        "previous_validity_record_id": None,
    })
    knowledge_bundle, provenance, adapter = (
        typed("KnowledgeBundle"), typed("KnowledgeProvenanceManifest"),
        typed("EvidenceAdapterContractSet"))
    probe = make_artifact_content("FF6RawReferenceProbe", {
        "origin_runtime_admission": {
            **typed("OriginRuntimeAdmission"),
            "ttl_capture_placement_proof": typed("TTLCapturePlacementProof"),
            "source_health_emitter_contract": typed("SourceHealthEmitterContract"),
        },
        "knowledge_references": [{
            "knowledge_bundle_id": knowledge_bundle["artifact_id"],
            "knowledge_bundle_digest": knowledge_bundle["content_sha256"],
            "canonical_knowledge_record_id": "ff6.fixture.record",
            "knowledge_provenance_id": provenance["artifact_id"],
            "knowledge_provenance_digest": provenance["content_sha256"],
            "rule_or_source_record_identity": "ff6.fixture.source",
        }],
        "evidence_references": [{
            "evidence_id": "00000000-0000-4000-8000-000000000004",
            "payload_sha256": digest,
            "feature_schema_version": 1,
            "adapter_contract_id": adapter["artifact_id"],
            "adapter_contract_digest": adapter["content_sha256"],
        }],
        "some_id": typed("Ignored")["artifact_id"],
        "some_digest": digest,
    })
    expected_probe = {kind for kind in (
        "OriginRuntimeAdmission", "TTLCapturePlacementProof", "SourceHealthEmitterContract",
        "KnowledgeBundle", "KnowledgeProvenanceManifest", "EvidenceAdapterContractSet")}
    return (make_runtime_profile_activation_record(activation.semantic_payload) == activation
            and make_runtime_profile_validity_record(validity.semantic_payload) == validity
            and {ref.artifact_id for ref in extract_direct_artifact_refs(activation)} == {
                profile.artifact_id, rpm.artifact_id}
            and {ref.artifact_id for ref in extract_direct_artifact_refs(validity)} == {
                profile.artifact_id}
            and {ref.artifact_id.split(":", 1)[0] for ref in extract_direct_artifact_refs(probe)}
            == expected_probe)


def execute_ff6_artifact_graph_acyclicity_scenarios(
    *, candidate_repository_commit_sha: str, candidate_repository_tree_sha: str,
) -> FF6ScenarioExecution:
    return _execute_ff6(
        _fixtures(), execution_mode=SYNTHETIC_TEST,
        candidate_repository_commit_sha=candidate_repository_commit_sha,
        candidate_repository_tree_sha=candidate_repository_tree_sha,
    )


def execute_ff6_artifact_graph_acyclicity_candidate(
    *, concrete_artifact_contents, candidate_repository_commit_sha: str,
    candidate_repository_tree_sha: str,
) -> FF6ScenarioExecution:
    """Analyze supplied Foundation contents; the acceptance runner owns inventory completeness."""
    try:
        contents = tuple(concrete_artifact_contents)
    except TypeError as exc:
        raise ArtifactDependencyGraphError("artifact_dependency_graph_invalid") from exc
    if not contents:
        raise ArtifactDependencyGraphError("artifact_dependency_graph_invalid")
    return _execute_ff6(
        contents, execution_mode=FOUNDATION_CANDIDATE,
        candidate_repository_commit_sha=candidate_repository_commit_sha,
        candidate_repository_tree_sha=candidate_repository_tree_sha,
    )


def _execute_ff6(
    contents: tuple[ArtifactContent, ...], *, execution_mode: str,
    candidate_repository_commit_sha: str, candidate_repository_tree_sha: str,
) -> FF6ScenarioExecution:
    if execution_mode not in (SYNTHETIC_TEST, FOUNDATION_CANDIDATE) or not contents:
        raise ArtifactDependencyGraphError("artifact_dependency_graph_invalid")
    nodes = build_concrete_artifact_graph(contents)
    concrete = analyze_artifact_dependency_graph(nodes)
    foundation = analyze_artifact_dependency_graph(build_foundation_schema_template_graph())
    task04 = analyze_artifact_dependency_graph(build_task04_schema_template_graph())
    cdoc, fdoc, tdoc = (_document(item) for item in (concrete, foundation, task04))
    cdoc.update({"execution_mode": execution_mode, "candidate_commit": candidate_repository_commit_sha,
                 "candidate_tree": candidate_repository_tree_sha})
    fnodes = {node.node_id: node for node in foundation.nodes}
    tnodes = {node.node_id: node for node in task04.nodes}
    f = lambda name: "template:foundation:" + name
    t = lambda name: "template:task04:" + name
    index = {node_id: position for position, node_id in enumerate(task04.topological_order)}
    f_admission, f_profile, f_rpm, f_gate = (fnodes[f(name)] for name in (
        "FoundationAdmissionManifest", "FoundationRuntimeProfile",
        "RuntimeProfileAdmissionManifest", "GateResultManifest"))
    crp, acceptance, c_rpm, c_gate = (tnodes[t(name)] for name in (
        "ClassificationRuntimeProfile", "Task04AcceptanceManifest",
        "RuntimeProfileAdmissionManifest", "GateResultManifest"))
    provenance = fnodes[f("KnowledgeProvenanceManifest:K1")]
    freshness = fnodes[f("KnowledgeFreshnessPolicy:K1")]
    capability, pre_gate = fnodes[f("CapabilityDisposition")], fnodes[f("PrerequisiteGateResultManifest")]
    last_gate = t("GateResultManifest")
    order_chain = [f("KnowledgeFreshnessPolicy:K1"), f("KnowledgeProvenanceManifest:K1"),
                   f("KnowledgeBundle"), t("ClassificationRuntimeProfile"),
                   t("Task04AcceptanceManifest"), t("RuntimeProfileAdmissionManifest"), last_gate]
    ttl_chain = [f("TTLCapturePlacementProof"), f("OriginRuntimeAdmission"),
                 f("FoundationAdmissionManifest")]
    missing = make_artifact_content("SyntheticDependent", {
        "synthetic_ff6_fixture_only": True, "dependency": _ref(contents[0])})
    wrong_digest = make_artifact_content("SyntheticDependent", {
        "synthetic_ff6_fixture_only": True,
        "dependency": {"artifact_id": contents[0].artifact_id, "content_sha256": "0" * 64}})
    raw_references_valid = _raw_reference_probe()
    foundation_backref = build_required_cycle_regression_fixtures()["foundation_profile_lineage"]
    checks = {
        "concrete_graph_acyclic": len(concrete.topological_order) == len(nodes),
        "concrete_dependency_closure": _reason(lambda: build_concrete_artifact_graph([missing]))
        == "artifact_dependency_missing",
        "concrete_digest_binding": _reason(lambda: build_concrete_artifact_graph([
            contents[0], wrong_digest])) == "artifact_dependency_digest_mismatch",
        "raw_reference_extraction_complete": raw_references_valid,
        "deterministic_topological_order": (
            canonical_artifact_json(_document(analyze_artifact_dependency_graph(reversed(nodes))))
            == canonical_artifact_json(_document(concrete))
            and canonical_artifact_json(_document(analyze_artifact_dependency_graph(
                reversed(build_task04_schema_template_graph())))) == canonical_artifact_json(tdoc)),
        "foundation_schema_coverage_complete": {node.artifact_type for node in foundation.nodes}
        == FOUNDATION_TYPES,
        "foundation_exact_edge_authority": matches_exact_template_authority(foundation.nodes, "foundation"),
        "foundation_runtime_profile_admission_backref_rejected": (
            not matches_exact_template_authority(foundation_backref, "foundation")
            and _reason(lambda: analyze_artifact_dependency_graph(foundation_backref)) is None),
        "foundation_template_acyclic": len(foundation.topological_order) == len(foundation.nodes),
        "foundation_runtime_profile_has_no_admission_backref": (
            f_admission.node_id not in f_profile.direct_dependency_ids
            and all(not dependency.startswith("template:task04:") for node in foundation.nodes
                    for dependency in node.direct_dependency_ids)),
        "foundation_rpm_prerequisite_only": (
            {f("FoundationRuntimeProfile"), f("FoundationAdmissionManifest"),
             f("PrerequisiteGateResultManifest")} == set(f_rpm.direct_dependency_ids)
            and f_gate.node_id not in f_rpm.direct_dependency_ids),
        "foundation_gate_output_direction_correct": (
            {f("PrerequisiteGateResultManifest"), capability.node_id,
             f_admission.node_id, f_profile.node_id, f_rpm.node_id,
             f("OriginRuntimeAdmission"), f("RuntimeProfileActivationRecord"),
             f("RuntimeProfileValidityRecord")} == set(f_gate.direct_dependency_ids)
            and f_gate.node_id not in f_admission.direct_dependency_ids),
        "knowledge_freshness_direction_correct": (
            freshness.node_id in provenance.direct_dependency_ids
            and provenance.node_id not in freshness.direct_dependency_ids
            and provenance.node_id in fnodes[f("KnowledgeBundle")].direct_dependency_ids),
        "capability_disposition_direction_correct": (
            capability.node_id in pre_gate.direct_dependency_ids
            and capability.direct_dependency_ids == ()),
        "task04_schema_coverage_complete": (
            {node.artifact_type for node in task04.nodes}.difference(FOUNDATION_TYPES)
            == TASK04_SPECIFIC_TYPES),
        "task04_exact_edge_authority": matches_exact_template_authority(task04.nodes, "task04"),
        "task04_template_acyclic": len(task04.topological_order) == len(task04.nodes),
        "candidate_crp_precedes_acceptance_manifest": (
            crp.node_id in acceptance.direct_dependency_ids
            and all(index[left] < index[right] for left, right in zip(order_chain, order_chain[1:]))
            and all(index[left] < index[right] for left, right in zip(ttl_chain, ttl_chain[1:]))),
        "classification_runtime_profile_has_no_acceptance_backref": (
            acceptance.node_id not in crp.direct_dependency_ids
            and len(crp.direct_dependency_ids) == 5),
        "task04_rpm_prerequisite_only": (
            {crp.node_id, acceptance.node_id, f_admission.node_id,
             f_rpm.node_id, t("PrerequisiteGateResultManifest")}
            == set(c_rpm.direct_dependency_ids)
            and c_gate.node_id not in c_rpm.direct_dependency_ids),
        "task04_gate_output_direction_correct": (
            {t("PrerequisiteGateResultManifest"), t("ProductValidationComparisonRecord"),
             acceptance.node_id, c_rpm.node_id} == set(c_gate.direct_dependency_ids)
            and c_gate.node_id not in acceptance.direct_dependency_ids),
        "history_uuid_refs_not_artifact_edges": raw_references_valid,
    }
    if execution_mode == SYNTHETIC_TEST:
        checks["registered_fixture_schema_valid"] = _fixture_schemas_valid(contents)
    else:
        checks["foundation_candidate_graph_analyzed"] = (
            bool(contents) and len(concrete.nodes) == len(concrete.topological_order))
    cycle_fixtures = {}
    for label, fixture in build_required_cycle_regression_fixtures().items():
        witness = ()
        if label == "foundation_profile_lineage":
            cycle_fixtures[label] = {
                "reason": "foundation_schema_template_invalid"
                if not matches_exact_template_authority(fixture, "foundation") else None,
                "cycle_witness": [],
            }
            continue
        try:
            analyze_artifact_dependency_graph(fixture)
        except ArtifactDependencyGraphError as exc:
            if exc.reason_code == "artifact_dependency_cycle":
                witness = exc.cycle_witness
        cycle_fixtures[label] = {"reason": "artifact_dependency_cycle" if witness else None,
                                 "cycle_witness": list(witness)}
    for check, label in (
        ("gate_output_cycle_regression_detected", "gate_output"),
        ("runtime_profile_lineage_cycle_regression_detected", "runtime_profile_lineage"),
        ("capability_gate_cycle_regression_detected", "capability_gate"),
        ("knowledge_freshness_provenance_cycle_regression_detected", "knowledge_freshness_provenance"),
        ("mutual_artifact_cycle_regression_detected", "mutual_artifact"),
    ):
        checks[check] = (cycle_fixtures[label]["reason"] == "artifact_dependency_cycle"
                         and bool(cycle_fixtures[label]["cycle_witness"]))
    by_id = {item.artifact_id: item for item in contents}
    refs = tuple(canonical_set([_ref(by_id[node.node_id]) for node in concrete.nodes],
                               lambda item: item["artifact_id"]))
    reasons = tuple(sorted({_REASON[name] for name, result in checks.items() if not result}))
    return FF6ScenarioExecution(
        execution_mode, cdoc, fdoc, tdoc, cycle_fixtures,
        {"concrete": cdoc["topological_order"], "foundation": fdoc["topological_order"],
         "task04": tdoc["topological_order"]},
        refs, checks, reasons)


def _concrete_ref_inventory_valid(execution: FF6ScenarioExecution) -> bool:
    """The gate inputs must be exactly the artifacts represented by the analyzed graph."""
    try:
        nodes = execution.concrete_graph["nodes"]
        if not isinstance(nodes, list) or not nodes:
            return False
        expected = tuple(canonical_set([{
            "artifact_id": node["node_id"],
            "content_sha256": node["node_id"].rsplit(":", 1)[1],
        } for node in nodes], lambda ref: ref["artifact_id"]))
        return (execution.concrete_artifact_refs == expected
                and all(node["node_kind"] == "CONCRETE"
                        and node["node_id"].startswith(f"{node['artifact_type']}:v1:sha256:")
                        for node in nodes))
    except (DeviceFingerprintValidationError, KeyError, TypeError, ValueError):
        return False


def run_ff6_artifact_graph_acyclicity_gate(
    execution: FF6ScenarioExecution, *, candidate_repository_commit_sha: str,
    candidate_repository_tree_sha: str, environment_identity: str,
    retained_evidence_refs: list[dict[str, Any]],
) -> FF6GateExecution:
    if not isinstance(execution, FF6ScenarioExecution) or not isinstance(retained_evidence_refs, list):
        raise DeviceFingerprintValidationError("Invalid F-F6 execution")
    reasons = set(execution.failure_reasons)
    required_checks = {
        SYNTHETIC_TEST: SYNTHETIC_REQUIRED_CHECKS,
        FOUNDATION_CANDIDATE: CANDIDATE_REQUIRED_CHECKS,
    }.get(execution.execution_mode)
    if execution.execution_mode != FOUNDATION_CANDIDATE:
        reasons.add("foundation_candidate_graph_required")
    if (required_checks is None or set(execution.checks) != required_checks
            or not execution.concrete_artifact_refs
            or any(type(value) is not bool for value in execution.checks.values())
            or execution.concrete_graph.get("execution_mode") != execution.execution_mode
            or execution.concrete_graph.get("candidate_commit") != candidate_repository_commit_sha
            or execution.concrete_graph.get("candidate_tree") != candidate_repository_tree_sha
            or not _concrete_ref_inventory_valid(execution)):
        reasons.add("artifact_dependency_graph_invalid")
    for name, passed in execution.checks.items():
        if not passed:
            reasons.add(_REASON.get(name, "artifact_dependency_graph_invalid"))
    if not retained_evidence_refs:
        reasons.add("retained_evidence_required")
    for row in retained_evidence_refs:
        if not isinstance(row, dict) or not isinstance(row.get("evidence_label"), str):
            raise DeviceFingerprintValidationError("Invalid F-F6 evidence")
    for label in _LABELS:
        if sum(row["evidence_label"] == label for row in retained_evidence_refs) != 1:
            reasons.add(f"{label}_required")
    evidence_rows = []
    seen = set()
    for row in retained_evidence_refs:
        identity = (row["evidence_label"], json.dumps(row, sort_keys=True, default=str))
        if row["evidence_label"] in _LABELS and identity in seen:
            continue
        seen.add(identity)
        evidence_rows.append(row)
    summary = ("foundation_template=ACYCLIC;task04_template=ACYCLIC;"
               "concrete_graph=ACYCLIC;cycle_regressions=5/5") if not reasons else (
                   "F-F6 FAIL:" + ",".join(sorted(reasons)))
    proof_identity = {
        "execution_id": str(uuid.uuid4()), "executor_kind": "TECHLEAD_GATE_TOOL",
        "repository_commit_sha": candidate_repository_commit_sha,
        "repository_tree_sha": candidate_repository_tree_sha,
        "procedure_or_test_suite_id": "F-F6-artifact-graph-acyclicity-v1",
        "environment_identity": environment_identity, "execution_artifact_sha256": None,
    }
    proof = make_gate_proof_artifact({
        "proof_kind": "ARTIFACT_GRAPH_ACYCLICITY", "source_gate_id": "F-F6",
        "candidate_repository_commit_sha": candidate_repository_commit_sha,
        "candidate_repository_tree_sha": candidate_repository_tree_sha,
        "input_artifact_refs": list(execution.concrete_artifact_refs),
        "procedure_or_test_suite_id": "F-F6-artifact-graph-acyclicity-v1",
        "proof_execution_identity": proof_identity,
        "canonical_result_summary": summary, "retained_evidence_refs": evidence_rows,
    })
    result = make_gate_result_manifest({
        "gate_id": "F-F6", "gate_contract_version": "R14-F-F6-v1",
        "status": "FAIL" if reasons else "PASS",
        "candidate_repository_commit_sha": candidate_repository_commit_sha,
        "candidate_repository_tree_sha": candidate_repository_tree_sha,
        "input_artifact_refs": list(execution.concrete_artifact_refs),
        "output_artifact_refs": [_ref(proof)] if not reasons else [],
        "retained_evidence_refs": evidence_rows,
        "proof_execution_identity": {**proof_identity, "execution_id": str(uuid.uuid4()),
                                     "procedure_or_test_suite_id": "F-F6-artifact-graph-acyclicity-gate-v1"},
        "trusted_time_inputs": {
            "foundation_knowledge_evaluation_at_utc": None,
            "foundation_admission_evaluation_at_utc": None,
            "knowledge_evaluation_at_utc": None,
        },
        "decision_record_refs": [],
    })
    return FF6GateExecution(proof, result, tuple(sorted(reasons)))
