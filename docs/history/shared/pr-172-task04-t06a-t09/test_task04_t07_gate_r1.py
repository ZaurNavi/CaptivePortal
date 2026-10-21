"""Disposable T-07 runner self-test; it never runs the official accepted databases."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys

import pytest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "task04-t07-gate-r1.py"
REPO = Path(r"C:\CaptivPortal-UI-Preview")
ACCEPTED_FOUNDATION = Path(
    r"C:\CaptivPortal-Lab\foundation-control-plane\device-fingerprint-control-plane.sqlite3")
ACCEPTED_T06A = Path(
    r"C:\CaptivPortal-Lab\gates\task04\t06a\official-run-20260929-T06A-01\fefddd39-876d-41dc-8a79-821257b59c54")
spec = importlib.util.spec_from_file_location("task04_t07_disposable_test_target", RUNNER)
assert spec and spec.loader
gate = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gate
spec.loader.exec_module(gate)


@pytest.fixture(scope="module")
def basis(tmp_path_factory):
    """Accepted Foundation snapshot plus a disposable real Task-01 v2 source."""
    root = tmp_path_factory.mktemp("disposable-t07-basis")
    foundation = root / "foundation.sqlite3"
    gate.copy_sqlite_readonly(ACCEPTED_FOUNDATION, foundation)
    t06a = root / "t06a-copy"
    t06a.mkdir()
    for name in gate.T06A_FILES:
        shutil.copyfile(ACCEPTED_T06A / name, t06a / name)
    helper, t06a_runner = gate.helpers()
    api = gate.api_for(REPO, t06a_runner)
    task01 = root / "task01-source.sqlite3"
    helper._create_task01(api, task01, [])
    return root, foundation, task01, t06a


def one_run(output):
    children = list(output.iterdir())
    assert len(children) == 1
    return children[0]


@pytest.fixture(scope="module")
def full_pass(basis, tmp_path_factory):
    _, foundation, task01, t06a = basis
    root = tmp_path_factory.mktemp("disposable-t07-full-pass")
    out = root / "pass"
    before_foundation, before_task01 = gate.sha(foundation), gate.sha(task01)
    helper, _ = gate.helpers()
    before_repo = helper.repository_filesystem_fingerprint(REPO)
    status = gate.run_gate(REPO, foundation, task01, t06a, out)
    run = one_run(out)
    assert status == 0, (run / "t07-summary.txt").read_text()
    assert gate.sha(foundation) == before_foundation
    assert gate.sha(task01) == before_task01
    assert helper.repository_filesystem_fingerprint(REPO) == before_repo
    return run


def test_exact_candidate_profile_retention_and_foundation_admission(basis):
    _, foundation, task01, t06a = basis
    helper, t06a_runner = gate.helpers()
    helper.verify_repository(REPO)
    api = gate.api_for(REPO, t06a_runner)
    profile, proof, result = gate.verify_t06a(t06a, api)
    assert profile.artifact_id == gate.PROFILE_ID
    assert proof.artifact_id == gate.T06A_PROOF_ID
    assert result.artifact_id == gate.T06A_RESULT_ID
    with helper.open_foundation_read_only(foundation) as connection:
        lineage = helper.verify_foundation(connection, api)
        retention = gate.resolve_retention(connection, api, helper, lineage)
    assert profile.semantic_payload["foundation_runtime_profile"] == gate.ref(lineage.profile)
    assert lineage.admission.semantic_payload["profile_kind"] == "foundation"
    assert lineage.admission.semantic_payload["candidate_profile"] == gate.ref(lineage.profile)
    assert retention == api.retention.build_initial_classification_retention_policy_v1()
    assert retention.semantic_payload["classification_history_retention_seconds"] == 7_776_000
    assert foundation != task01


def test_foundation_admission_closure_on_disposable_copy(basis, tmp_path):
    _, foundation, task01, _ = basis
    helper, t06a_runner = gate.helpers()
    api = gate.api_for(REPO, t06a_runner)
    with helper.open_foundation_read_only(foundation) as connection:
        lineage = helper.verify_foundation(connection, api)
    control = api.control.DeviceFingerprintControlPlaneStore(foundation)
    store = api.persistence.DeviceFingerprintClassificationStore(
        tmp_path / "classification.sqlite3", task01, control_plane_store=control)
    closure = store._collect_closure([lineage.admission], lineage=True)
    assert lineage.admission.artifact_id in closure
    assert lineage.manifest.artifact_id in closure
    assert lineage.profile.artifact_id in closure


def test_wrong_t06a_profile_and_missing_retention_block(basis, tmp_path):
    _, foundation, task01, t06a = basis
    helper, t06a_runner = gate.helpers()
    api = gate.api_for(REPO, t06a_runner)
    wrong = tmp_path / "wrong-t06a"
    shutil.copytree(t06a, wrong)
    value = json.loads((wrong / gate.T06A_FILES[0]).read_text())
    value["artifact_id"] = "ClassificationRuntimeProfile:v1:sha256:" + "0" * 64
    gate.write_json(wrong / gate.T06A_FILES[0], value)
    with pytest.raises(gate.Blocked, match="BLOCKED_T06A_PREREQUISITE"):
        gate.verify_t06a(wrong, api)
    assert gate.run_gate(REPO, foundation, task01, wrong, tmp_path / "wrong-output") == 2
    wrong_run = one_run(tmp_path / "wrong-output")
    assert not (wrong_run / "t07-gate-result-manifest.json").exists()
    missing = tmp_path / "missing-policy.sqlite3"
    gate.copy_sqlite_readonly(foundation, missing)
    with sqlite3.connect(missing) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        reference = helper.EXPECTED_DIGESTS.get("ClassificationRetentionPolicy")
        if reference is None:
            with helper.open_foundation_read_only(foundation) as original:
                lineage = helper.verify_foundation(original, api)
            reference = lineage.manifest.semantic_payload["classification_retention_policy"]["content_sha256"]
        connection.execute("DELETE FROM artifacts WHERE artifact_id=?", (
            "ClassificationRetentionPolicy:v1:sha256:" + reference,))
    assert gate.run_gate(REPO, missing, task01, t06a, tmp_path / "missing-output") == 2
    assert not (one_run(tmp_path / "missing-output") / "t07-gate-result-manifest.json").exists()


def test_full_pass_proof_result_and_all_matrix_cases(full_pass):
    run = full_pass
    execution = json.loads((run / "t07-execution-evidence.json").read_text())
    assert execution["all_pass"]
    assert set(execution["direct_matrix"]) == set(gate.CASES)
    assert all(row["status"] == "PASS" for row in execution["direct_matrix"].values())
    proof = json.loads((run / "t07-gate-proof-artifact.json").read_text())
    result = json.loads((run / "t07-gate-result-manifest.json").read_text())
    assert proof["semantic_payload"]["proof_kind"] == gate.PROOF_KIND
    assert result["semantic_payload"]["gate_id"] == "T-07"
    assert result["semantic_payload"]["gate_contract_version"] == "R14-T-07-v1"
    assert result["semantic_payload"]["status"] == "PASS"
    assert result["semantic_payload"]["decision_record_refs"] == []
    assert result["semantic_payload"]["output_artifact_refs"] == [{
        "artifact_id": proof["artifact_id"], "content_sha256": proof["content_sha256"]}]
    required_inputs = {execution["t06a_gate_result"]["artifact_id"],
                       execution["exact_profile"]["artifact_id"],
                       execution["accepted_retention_policy"]["artifact_id"],
                       execution["foundation_runtime_profile_admission_manifest"]["artifact_id"]}
    assert required_inputs <= {row["artifact_id"] for row in result[
        "semantic_payload"]["input_artifact_refs"]}
    evidence = {row["path_or_reference"]: row["file_sha256"] for row in result[
        "semantic_payload"]["retained_evidence_refs"]}
    assert set(evidence) == set(gate.RETAINED)
    assert all(gate.sha(run / name) == digest for name, digest in evidence.items())
    assert (run / "t07-summary.txt").read_text().startswith("GATE_EXECUTION_STATUS=PASS")
    assert (run / "t07-pytest.log").read_text().count("passed") >= 1


def test_core_lineage_closure_and_no_future_placeholders(full_pass):
    run = full_pass
    core_report = json.loads((run / "t07-persistence-core.json").read_text())
    inventory = json.loads((run / "t07-classification-db-inventory.json").read_text())
    matrix = json.loads((run / "t07-execution-evidence.json").read_text())["direct_matrix"]
    core = core_report["core_row"]
    assert set(core) == set(gate.EXPECTED_CORE_FIELDS)
    assert core["execution_context"] == "PRE_ACCEPTANCE_CANDIDATE"
    assert core["classification_runtime_profile_id"] == gate.PROFILE_ID
    assert core["runtime_profile_activation_record_id"] is None
    assert (core["foundation_runtime_profile_id"], core["foundation_runtime_profile_digest"]) == (
        core_report["foundation_profile"]["artifact_id"],
        core_report["foundation_profile"]["content_sha256"])
    assert core_report["future_placeholder_absent"]
    assert core_report["same_production_schema"]
    assert not core_report["post_acceptance_row_mutation_required"]
    assert not (set(core_report["schema_columns"]) & gate.FUTURE_CORE_COLUMNS)
    assert inventory["classification_count"] == 2
    assert inventory["artifact_count"] >= len(gate.REQUIRED_AUDIT_TYPES)
    assert gate.REQUIRED_AUDIT_TYPES <= {row["artifact_type"] for row in inventory["artifact_refs"]}
    assert inventory["dangling_ref_scan_result"] == {"dangling_count": 0, "pass": True}
    assert matrix["T07-M03"]["trace"]["controlled_mismatch_rejected"]
    assert len(matrix["T07-M05"]["trace"]["resolved_refs"]) == 4
    assert inventory["accepted_task01_db_sha256_before"] == inventory[
        "accepted_task01_db_sha256_after"]
    assert inventory["accepted_foundation_db_sha256_before"] == inventory[
        "accepted_foundation_db_sha256_after"]


def test_replay_gc_retention_rollback_and_guard(full_pass):
    run = full_pass
    replay = json.loads((run / "t07-audit-replay-report.json").read_text())
    gc = json.loads((run / "t07-gc-report.json").read_text())
    guard = json.loads((run / "t07-production-admission-guard.json").read_text())
    matrix = json.loads((run / "t07-execution-evidence.json").read_text())["direct_matrix"]
    assert replay["disposable_task01_source_removed"]
    assert replay["wall_clock_read_count"] == 0
    assert replay["replay_exact"]
    assert replay["original_result"] == replay["replayed_result"]
    assert replay["stored_result_bytes_before_sha256"] == replay[
        "stored_result_bytes_after_sha256"]
    assert gc["retention_seconds"] == 7_776_000
    assert gc["pre_boundary"]["before_expired_count"] == 0
    assert gc["pre_boundary"]["at_boundary_expired_count"] == 1
    assert gc["shared_artifact_protected"]["remaining_replay_exact"]
    assert gc["unreferenced_artifact_gc"]["after_all"]["artifact_count"] == 0
    assert gc["dangling_edges_after_gc"] == 0
    assert matrix["T07-M10"]["trace"]["post_fault_counts"] == {
        "classifications": 0, "artifacts": 0, "artifact_dependencies": 0,
        "classification_roots": 0}
    assert guard["unadmitted_exact_p"]["reason_code"] == "production_profile_not_admitted"
    assert not guard["unadmitted_exact_p"]["classification_committed"]
    assert guard["controlled_validity_cases"]["active"]["status"] == "COMMITTED"
    for key in ("suspended", "ttl_capture_proof_invalidated"):
        case = guard["controlled_validity_cases"][key]
        assert case["status"] == "REJECTED"
        assert case["reason_code"] == "runtime_profile_invalidated"
        assert case["inflight_commit_rule"] == "REJECT_PINNED_INFLIGHT"
        assert case["classification_count"] == 0


def test_full_semantic_fail_writes_manifest_without_proof(basis, tmp_path, monkeypatch):
    _, foundation, task01, t06a = basis
    def focused_pytest(_repo, run):
        (run / "t07-pytest.log").write_text("controlled suite success\n")
        return 0, ["controlled", "pytest"]
    monkeypatch.setattr(gate, "_run_pytest", focused_pytest)
    monkeypatch.setattr(gate, "_direct_matrix", lambda *_: (_ for _ in ()).throw(
        gate.SemanticFailure("CONTROLLED_SEMANTIC_FAILURE")))
    out = tmp_path / "fail"
    assert gate.run_gate(REPO, foundation, task01, t06a, out) == 1
    run = one_run(out)
    result = json.loads((run / "t07-gate-result-manifest.json").read_text())
    assert result["semantic_payload"]["status"] == "FAIL"
    assert result["semantic_payload"]["output_artifact_refs"] == []
    assert not (run / "t07-gate-proof-artifact.json").exists()


def test_runner_and_repository_mutation_block(basis, tmp_path, monkeypatch):
    _, foundation, task01, t06a = basis
    def focused_pytest(_repo, run):
        (run / "t07-pytest.log").write_text("controlled suite success\n")
        return 0, ["controlled", "pytest"]
    monkeypatch.setattr(gate, "_run_pytest", focused_pytest)
    monkeypatch.setattr(gate, "_direct_matrix", lambda *_: (
        {key: {"status": "PASS", "trace": {}} for key in gate.CASES},
        {"core": {}, "inventory": {}, "replay": {}, "gc": {}, "guard": {}}))
    original_sha = gate.sha
    calls = [0]
    def changed_runner(path):
        if Path(path) == RUNNER:
            calls[0] += 1
            if calls[0] > 1:
                return "0" * 64
        return original_sha(path)
    monkeypatch.setattr(gate, "sha", changed_runner)
    out = tmp_path / "runner-mutated"
    assert gate.run_gate(REPO, foundation, task01, t06a, out) == 2
    assert not (one_run(out) / "t07-gate-result-manifest.json").exists()
    monkeypatch.setattr(gate, "sha", original_sha)
    helper, _ = gate.helpers()
    original_check = helper._require_repository_unchanged
    def changed_repo(*_args):
        raise helper.Blocked("BLOCKED_REPOSITORY_MUTATED")
    monkeypatch.setattr(helper, "_require_repository_unchanged", changed_repo)
    out = tmp_path / "repo-mutated"
    assert gate.run_gate(REPO, foundation, task01, t06a, out) == 2
    assert not (one_run(out) / "t07-gate-result-manifest.json").exists()
    monkeypatch.setattr(helper, "_require_repository_unchanged", original_check)
