"""Whole synthetic F-F6 proof, retained evidence, and gate status."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from app.device_fingerprint.artifact_dependency_graph import ArtifactDependencyGraphError
from app.device_fingerprint.ff6_artifact_graph_acyclicity import (
    CANDIDATE_REQUIRED_CHECKS, FOUNDATION_CANDIDATE, SYNTHETIC_REQUIRED_CHECKS,
    SYNTHETIC_TEST, _fixtures, execute_ff6_artifact_graph_acyclicity_candidate,
    execute_ff6_artifact_graph_acyclicity_scenarios,
    run_ff6_artifact_graph_acyclicity_gate,
)

_SHA = "a" * 40
_TREE = "b" * 40
_LABELS = (
    "artifact_dependency_graph", "artifact_cycle_test_fixtures",
    "artifact_topological_ordering",
)
_SYNTHETIC_CHECK_NAMES = {
    "concrete_graph_acyclic", "concrete_dependency_closure", "concrete_digest_binding",
    "raw_reference_extraction_complete", "registered_fixture_schema_valid",
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
}
_CANDIDATE_CHECK_NAMES = (_SYNTHETIC_CHECK_NAMES - {"registered_fixture_schema_valid"}) | {
    "foundation_candidate_graph_analyzed"}


def _evidence():
    return [{"evidence_label": label, "file_sha256": f"{index:x}" * 64,
             "media_type": "application/json", "path_or_reference": "synthetic://ff6-proof"}
            for index, label in enumerate(_LABELS, start=1)]


def _execution():
    return execute_ff6_artifact_graph_acyclicity_candidate(
        concrete_artifact_contents=_fixtures(),
        candidate_repository_commit_sha=_SHA, candidate_repository_tree_sha=_TREE)


def _gate(execution, evidence=None):
    return run_ff6_artifact_graph_acyclicity_gate(
        execution, candidate_repository_commit_sha=_SHA,
        candidate_repository_tree_sha=_TREE, environment_identity="synthetic-ff6-windows",
        retained_evidence_refs=_evidence() if evidence is None else evidence)


def test_candidate_path_fixture_proof_and_canonical_gate_pass():
    execution = _execution()
    assert execution.execution_mode == FOUNDATION_CANDIDATE
    assert set(execution.checks) == _CANDIDATE_CHECK_NAMES == CANDIDATE_REQUIRED_CHECKS
    assert all(execution.checks.values())
    assert execution.failure_reasons == ()
    assert len(execution.concrete_artifact_refs) == len(execution.concrete_graph["nodes"]) == 5
    assert execution.concrete_graph["execution_mode"] == FOUNDATION_CANDIDATE
    assert len(execution.cycle_test_fixtures) == 6
    assert execution.cycle_test_fixtures["foundation_profile_lineage"] == {
        "reason": "foundation_schema_template_invalid", "cycle_witness": []}
    json.dumps({"concrete": execution.concrete_graph,
                "foundation": execution.foundation_template_graph,
                "task04": execution.task04_template_graph,
                "cycles": execution.cycle_test_fixtures,
                "orderings": execution.topological_orderings})
    result = _gate(execution)
    manifest = result.gate_result_manifest.semantic_payload
    proof = result.gate_proof_artifact.semantic_payload
    assert manifest["status"] == "PASS"
    assert result.failure_reasons == ()
    assert proof["proof_kind"] == "ARTIFACT_GRAPH_ACYCLICITY"
    assert proof["source_gate_id"] == manifest["gate_id"] == "F-F6"
    assert manifest["gate_contract_version"] == "R14-F-F6-v1"
    assert proof["procedure_or_test_suite_id"] == "F-F6-artifact-graph-acyclicity-v1"
    assert manifest["proof_execution_identity"]["procedure_or_test_suite_id"] == (
        "F-F6-artifact-graph-acyclicity-gate-v1")
    assert manifest["proof_execution_identity"]["executor_kind"] == "TECHLEAD_GATE_TOOL"
    assert manifest["input_artifact_refs"] == list(execution.concrete_artifact_refs)
    assert proof["input_artifact_refs"] == list(execution.concrete_artifact_refs)
    assert len(manifest["output_artifact_refs"]) == 1
    assert manifest["output_artifact_refs"][0]["artifact_id"] == result.gate_proof_artifact.artifact_id
    assert manifest["decision_record_refs"] == []
    assert set(manifest["trusted_time_inputs"].values()) == {None}
    assert [row["evidence_label"] for row in manifest["retained_evidence_refs"]] == sorted(_LABELS)
    assert proof["canonical_result_summary"] == (
        "foundation_template=ACYCLIC;task04_template=ACYCLIC;"
        "concrete_graph=ACYCLIC;cycle_regressions=5/5")


def test_synthetic_self_test_cannot_receive_canonical_acceptance():
    synthetic = execute_ff6_artifact_graph_acyclicity_scenarios(
        candidate_repository_commit_sha=_SHA, candidate_repository_tree_sha=_TREE)
    assert synthetic.execution_mode == SYNTHETIC_TEST
    assert set(synthetic.checks) == _SYNTHETIC_CHECK_NAMES == SYNTHETIC_REQUIRED_CHECKS
    assert all(synthetic.checks.values())
    assert synthetic.failure_reasons == ()
    gate = _gate(synthetic)
    assert gate.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert "foundation_candidate_graph_required" in gate.failure_reasons
    assert gate.gate_result_manifest.semantic_payload["output_artifact_refs"] == []


def test_candidate_input_order_is_deterministic_and_empty_is_rejected():
    contents = _fixtures()
    forward = execute_ff6_artifact_graph_acyclicity_candidate(
        concrete_artifact_contents=contents,
        candidate_repository_commit_sha=_SHA, candidate_repository_tree_sha=_TREE)
    reverse = execute_ff6_artifact_graph_acyclicity_candidate(
        concrete_artifact_contents=reversed(contents),
        candidate_repository_commit_sha=_SHA, candidate_repository_tree_sha=_TREE)
    for field in ("nodes", "edges", "topological_order"):
        assert forward.concrete_graph[field] == reverse.concrete_graph[field]
    assert forward.concrete_artifact_refs == reverse.concrete_artifact_refs
    with pytest.raises(ArtifactDependencyGraphError) as error:
        execute_ff6_artifact_graph_acyclicity_candidate(
            concrete_artifact_contents=[],
            candidate_repository_commit_sha=_SHA, candidate_repository_tree_sha=_TREE)
    assert error.value.reason_code == "artifact_dependency_graph_invalid"


def test_candidate_path_analyzes_only_supplied_contents():
    supplied = (_fixtures()[0],)
    candidate = execute_ff6_artifact_graph_acyclicity_candidate(
        concrete_artifact_contents=iter(supplied),
        candidate_repository_commit_sha=_SHA, candidate_repository_tree_sha=_TREE)
    assert [row["node_id"] for row in candidate.concrete_graph["nodes"]] == [
        supplied[0].artifact_id]
    assert [row["artifact_id"] for row in candidate.concrete_artifact_refs] == [
        supplied[0].artifact_id]
    assert candidate.concrete_graph["execution_mode"] == FOUNDATION_CANDIDATE


def test_candidate_gate_rejects_omitted_or_unanalysed_input_refs():
    execution = _execution()
    for refs in (execution.concrete_artifact_refs[:-1],
                 execution.concrete_artifact_refs + ({
                     "artifact_id": "Extra:v1:sha256:" + "f" * 64,
                     "content_sha256": "f" * 64,
                 },)):
        gate = _gate(replace(execution, concrete_artifact_refs=refs))
        assert gate.gate_result_manifest.semantic_payload["status"] == "FAIL"
        assert "artifact_dependency_graph_invalid" in gate.failure_reasons
        assert gate.gate_result_manifest.semantic_payload["output_artifact_refs"] == []


def test_forced_cycle_yields_fail_and_no_output_artifact():
    execution = _execution()
    failed = replace(execution, checks={**execution.checks,
                                        "mutual_artifact_cycle_regression_detected": False},
                     failure_reasons=("artifact_dependency_cycle",))
    result = _gate(failed)
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert "artifact_dependency_cycle" in result.failure_reasons
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []


@pytest.mark.parametrize("evidence,reason", [
    ([], "retained_evidence_required"),
    (_evidence()[:1], "artifact_topological_ordering_required"),
    (_evidence() + [_evidence()[0]], "artifact_dependency_graph_required"),
])
def test_mandatory_evidence_absence_or_duplicate_fails(evidence, reason):
    result = _gate(_execution(), evidence)
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []
    assert reason in result.failure_reasons


def test_unrelated_extra_evidence_is_allowed():
    evidence = _evidence() + [{"evidence_label": "other", "file_sha256": "f" * 64,
                              "media_type": "text/plain", "path_or_reference": None}]
    assert _gate(_execution(), evidence).gate_result_manifest.semantic_payload["status"] == "PASS"


def test_candidate_identity_mismatch_cannot_pass():
    execution = _execution()
    invalid = replace(execution, concrete_graph={**execution.concrete_graph,
                                                 "candidate_tree": "c" * 40})
    result = _gate(invalid)
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert "artifact_dependency_graph_invalid" in result.failure_reasons
