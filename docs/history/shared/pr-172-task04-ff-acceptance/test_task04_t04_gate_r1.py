"""Disposable self-tests for the external T-04 harness, never the official gate."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sqlite3
import sys
import uuid
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace

import pytest


sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "task04-t04-gate-r1.py"
REPO = Path(r"C:\CaptivPortal-UI-Preview")
SPEC = importlib.util.spec_from_file_location("task04_t04_gate_selftest_target", RUNNER)
assert SPEC is not None and SPEC.loader is not None
gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)


def test_exact_candidate_identity_and_immutability_guard(tmp_path, monkeypatch):
    helper = gate._t01()
    helper.verify_repository(REPO)
    assert helper._git(REPO, "rev-parse", "HEAD") == gate.EXPECTED_COMMIT
    assert helper._git(REPO, "show", "-s", "--format=%T", "HEAD") == gate.EXPECTED_TREE
    original = helper.repository_filesystem_fingerprint(REPO)
    helper._require_repository_unchanged(REPO, original)
    root = tmp_path / "fingerprint"
    root.mkdir()
    (root / "ignored.bin").write_bytes(b"A")
    before = helper.repository_filesystem_fingerprint(root)
    (root / "ignored.bin").write_bytes(b"B")
    with pytest.raises(helper.Blocked, match="BLOCKED_REPOSITORY_MUTATED"):
        helper._require_repository_unchanged(root, before)


@pytest.mark.parametrize("difference", ["commit", "tree", "dirty"])
def test_candidate_identity_blocks(monkeypatch, difference):
    helper = gate._t01()
    original = helper._git
    def changed(repo, *args):
        if difference == "commit" and args == ("rev-parse", "HEAD"):
            return "0" * 40
        if difference == "tree" and args == ("show", "-s", "--format=%T", "HEAD"):
            return "0" * 40
        if difference == "dirty" and args == ("status", "--porcelain"):
            return " M file"
        return original(repo, *args)
    monkeypatch.setattr(helper, "_git", changed)
    with pytest.raises(helper.Blocked, match="BLOCKED_CANDIDATE_IDENTITY"):
        helper.verify_repository(REPO)


def test_helper_runner_and_fixture_origin_guards(monkeypatch, tmp_path):
    assert gate._sha256(gate.T01_HELPER) == gate.T01_HELPER_SHA256
    runner_digest = gate._sha256(RUNNER)
    assert gate._integrity_block(RUNNER, runner_digest) is None
    monkeypatch.setattr(gate, "T01_HELPER_SHA256", "0" * 64)
    assert gate._integrity_block(RUNNER, runner_digest) == "BLOCKED_HARDENED_HELPER_CHANGED"
    with pytest.raises(RuntimeError, match="BLOCKED_HARDENED_HELPER_CHANGED"):
        gate._t01()
    monkeypatch.undo()
    mutated = tmp_path / "runner.py"
    mutated.write_bytes(RUNNER.read_bytes() + b"# changed\n")
    assert gate._integrity_block(mutated, runner_digest) == "BLOCKED_RUNNER_CHANGED"
    monkeypatch.setattr(gate.importlib, "import_module", lambda _name: SimpleNamespace(
        __file__=r"C:\outside\fixture.py"))
    with pytest.raises(gate._t01().Blocked, match="BLOCKED_CANDIDATE_IDENTITY"):
        gate._candidate_module(REPO, "outside.fixture")


def test_pytest_environment_and_external_temp(monkeypatch, tmp_path):
    observed = {}
    def fake_run(command, *, cwd, env, **_kwargs):
        observed.update(command=command, cwd=cwd, env=env)
        return SimpleNamespace(returncode=0, stdout="candidate suite passed\n")
    monkeypatch.setattr(gate.subprocess, "run", fake_run)
    status, log, text = gate.execute_pytest(REPO, tmp_path)
    assert status == 0 and "candidate suite passed" in log
    assert observed["command"][-1] == "tests/device_fingerprint_task04_t04"
    assert observed["command"][observed["command"].index("-p") + 1] == "no:cacheprovider"
    base = Path(observed["command"][observed["command"].index("--basetemp") + 1])
    assert base.is_relative_to(tmp_path) and not base.is_relative_to(REPO)
    assert observed["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
    assert observed["env"]["PYTEST_ADDOPTS"] == ""
    assert all(Path(observed["env"][key]).is_relative_to(tmp_path)
               for key in ("TEMP", "TMP", "TMPDIR"))
    assert "--basetemp" in text


def test_complete_policy_vectors_and_direct_scenarios():
    api = gate.load_api(REPO)
    tests = gate._candidate_module(REPO, "tests.device_fingerprint_task04_t04.test_fusion")
    t03 = gate._candidate_module(REPO, "tests.device_fingerprint_task04_t03.test_origin_assessment")
    baseline = tests._base_from_source(t03._inputs())
    original = gate._t01().repository_filesystem_fingerprint(REPO)
    vectors = gate.execute_policy_vectors(api, baseline.classification_policy)
    matrix, artifacts = gate.execute_matrix(api)
    gate._t01()._require_repository_unchanged(REPO, original)
    assert vectors["all_pass"] and vectors["cell_count"] == 40
    assert len(vectors["vectors"]) == 40
    assert vectors["classification_policy"] == gate._ref(baseline.classification_policy)
    assert all(row["expected"] == row["observed"] and row["status"] == "PASS"
               for row in vectors["vectors"])
    assert set(matrix["cases"]) == set(gate.CASE_IDS)
    assert matrix["all_pass"], {key: value for key, value in matrix["cases"].items()
                                if value["status"] != "PASS"}
    assert all(matrix["cases"][case]["trace"] for case in gate.CASE_IDS)
    assert {item["artifact_type"] for item in artifacts["artifacts"]} == {"ClassificationResult"}
    assert artifacts["classifier_artifact_manifest_fixture_not_T06_acceptance"] is True
    assert matrix["cases"]["T04-M09"]["trace"][-1]["tcp_disabled"]["audit_evidence_count"] > 0


@pytest.fixture
def full_run_lab(tmp_path, monkeypatch):
    """Real closed candidate builders in an external, disposable Foundation DB."""
    api = gate.load_api(REPO)
    helper = gate._t01()
    t03 = gate._candidate_module(REPO, "tests.device_fingerprint_task04_t03.test_origin_assessment")
    t04 = gate._candidate_module(REPO, "tests.device_fingerprint_task04_t04.test_fusion")
    t01 = gate._candidate_module(REPO, "tests.device_fingerprint_task04_t01.test_snapshot_service")
    ff5 = gate._candidate_module(REPO, "app.device_fingerprint.ff5_runtime_profile_atomicity")
    source = t03._inputs()
    baseline = t04._base_from_source(source)
    context = t01.context()
    knowledge = source.knowledge
    registry = context.contents[context.profile.semantic_payload[
        "evidence_schema_registry_contract"]["artifact_id"]]
    extra_types = {"CapabilityDisposition", "K2AConformancePackage", "OriginRuntimeAdmission"}
    extras = {content.artifact_type: content for content in context.contents.values()
              if content.artifact_type in extra_types}
    assert set(extras) == extra_types
    database = tmp_path / "disposable-t04-foundation.sqlite"
    fixture = ff5._Fixture(database)
    manifest_payload = fixture.leaves["FoundationAdmissionManifest"].semantic_payload
    manifest_payload.update({
        "evidence_schema_registry_contract": gate._ref(registry),
        "evidence_adapter_contract_set": gate._ref(source.evidence_adapter_contract_set),
        "knowledge_bundle": gate._ref(source.knowledge_bundle),
        "classification_policy": gate._ref(baseline.classification_policy),
        "origin_runtime_admission": gate._ref(extras["OriginRuntimeAdmission"]),
        "portal_headers_v2_capability_disposition": gate._ref(extras["CapabilityDisposition"]),
        "k2a_conformance_package": gate._ref(extras["K2AConformancePackage"]),
    })
    for name in ("knowledge_provenance_manifests", "source_governance_records",
                 "knowledge_freshness_policies"):
        manifest_payload[name] = source.knowledge_bundle.semantic_payload[name]
    manifest = api.foundation.make_foundation_admission_manifest(manifest_payload)
    profile_payload = fixture.foundation_a.semantic_payload
    profile_payload["evidence_schema_registry_contract"] = gate._ref(registry)
    profile_payload["origin_runtime_admission"] = gate._ref(extras["OriginRuntimeAdmission"])
    profile = api.profiles.make_foundation_runtime_profile(profile_payload)
    admission_payload = fixture.admission("foundation", fixture.foundation_a).semantic_payload
    admission_payload["candidate_profile"] = gate._ref(profile)
    admission_payload["foundation_admission_manifest"] = gate._ref(manifest)
    admission = api.profiles.make_runtime_profile_admission_manifest(admission_payload)
    activation, validity, _ = fixture.records(admission, 100)
    result = api.gate_result.make_gate_result_manifest({
        "gate_id": "F-ADMIT", "gate_contract_version": "R14-F-ADMIT-v1",
        "status": "PASS", "candidate_repository_commit_sha": "a" * 40,
        "candidate_repository_tree_sha": "b" * 40,
        "input_artifact_refs": [], "output_artifact_refs": [
            gate._ref(item) for item in (manifest, profile, admission, activation, validity)],
        "retained_evidence_refs": [], "proof_execution_identity": {
            "execution_id": str(uuid.uuid4()), "executor_kind": "TECHLEAD_GATE_TOOL",
            "repository_commit_sha": "a" * 40, "repository_tree_sha": "b" * 40,
            "procedure_or_test_suite_id": "disposable-t04-full-run-self-test",
            "environment_identity": "disposable-self-test",
            "execution_artifact_sha256": "c" * 64},
        "trusted_time_inputs": {
            "foundation_knowledge_evaluation_at_utc": None,
            "foundation_admission_evaluation_at_utc": None,
            "knowledge_evaluation_at_utc": None},
        "decision_record_refs": []})
    documents = [registry, manifest, profile, admission, activation, validity, result,
                 source.evidence_adapter_contract_set, source.knowledge_bundle,
                 baseline.classification_policy, *extras.values(),
                 *(getattr(knowledge, field.name) for field in fields(knowledge))]
    with sqlite3.connect(database) as connection:
        for content in {item.artifact_id: item for item in documents}.values():
            connection.execute(
                "INSERT INTO artifacts (artifact_id, artifact_type, content_sha256, "
                "semantic_payload_json) VALUES (?,?,?,?)",
                (content.artifact_id, content.artifact_type, content.content_sha256,
                 content.semantic_payload_json))
        active = activation.semantic_payload
        valid = validity.semantic_payload
        connection.execute(
            "INSERT INTO activations (activation_record_id, artifact_id, profile_kind, "
            "runtime_profile_id, runtime_profile_digest, activation_generation_id) "
            "VALUES (?,?,?,?,?,?)",
            (active["activation_record_id"], activation.artifact_id, "foundation",
             profile.artifact_id, profile.content_sha256, active["activation_generation_id"]))
        connection.execute(
            "INSERT INTO active_pointers (profile_kind, runtime_profile_id, "
            "runtime_profile_digest, activation_record_id, activation_generation_id, "
            "updated_at_utc) VALUES (?,?,?,?,?,?)",
            ("foundation", profile.artifact_id, profile.content_sha256,
             active["activation_record_id"], active["activation_generation_id"],
             active["activated_at_utc"]))
        connection.execute(
            "INSERT INTO validities (validity_record_id, artifact_id, activation_record_id) "
            "VALUES (?,?,?)",
            (valid["validity_record_id"], validity.artifact_id, active["activation_record_id"]))
        connection.execute(
            "INSERT INTO validity_heads (activation_record_id, validity_record_id, updated_at_utc) "
            "VALUES (?,?,?)",
            (active["activation_record_id"], valid["validity_record_id"],
             valid["effective_at_utc"]))
        connection.execute(
            "INSERT INTO f_admit_publications (gate_id, artifact_id, content_sha256) "
            "VALUES (?,?,?)", ("F-ADMIT", result.artifact_id, result.content_sha256))
    monkeypatch.setattr(helper, "EXPECTED_DIGESTS", {
        "FoundationAdmissionManifest": manifest.content_sha256,
        "FoundationRuntimeProfile": profile.content_sha256,
        "RuntimeProfileAdmissionManifest": admission.content_sha256,
        "GateResultManifest": result.content_sha256,
        "EvidenceSchemaRegistryContract": registry.content_sha256})
    return SimpleNamespace(database=database, api=api, manifest=manifest, profile=profile,
                           admission=admission, activation=activation, validity=validity,
                           result=result, registry=registry, source=source, baseline=baseline,
                           extras=extras)


def _stub_semantics(monkeypatch, *, pytest_exit=0):
    matrix = {"cases": {case: {"status": "PASS", "input_fixture_sha256": "a" * 64}
                        for case in gate.CASE_IDS}, "traces": {}, "all_pass": True}
    monkeypatch.setattr(gate, "execute_pytest", lambda _repo, _run_dir: (
        pytest_exit, "disposable T-04 pytest stub\n",
        "python -m pytest -q tests/device_fingerprint_task04_t04"))
    monkeypatch.setattr(gate, "execute_matrix", lambda _api: (
        matrix, {"lineage_kind": "CONTROLLED_CANDIDATE_FIXTURES_NOT_FORMAL_ADMITTED_INPUTS",
                 "artifacts": []}))


def test_disposable_foundation_is_read_only_and_active(full_run_lab):
    helper = gate._t01()
    original = hashlib.sha256(full_run_lab.database.read_bytes()).hexdigest()
    with helper.open_foundation_read_only(full_run_lab.database) as connection:
        assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
        lineage = helper.verify_foundation(connection, full_run_lab.api)
        assert lineage.validity.semantic_payload["state"] == "ACTIVE"
        assert gate.resolve_admitted(connection, full_run_lab.api, lineage)[
            "policy"].artifact_id == full_run_lab.baseline.classification_policy.artifact_id
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("INSERT INTO artifacts (artifact_id) VALUES ('forbidden')")
    assert hashlib.sha256(full_run_lab.database.read_bytes()).hexdigest() == original


def test_missing_active_validity_head_blocks(full_run_lab):
    helper = gate._t01()
    with sqlite3.connect(full_run_lab.database) as connection:
        connection.execute("DELETE FROM validity_heads")
    with helper.open_foundation_read_only(full_run_lab.database) as connection:
        with pytest.raises(helper.Blocked, match="BLOCKED_FOUNDATION_LINEAGE"):
            helper.verify_foundation(connection, full_run_lab.api)


@pytest.mark.parametrize("artifact_name", [
    "ClassificationPolicy", "ClassificationTaxonomy", "AliasMapping",
    "EvidenceAdapterContractSet", "OriginRuntimeAdmission",
])
def test_tampered_admitted_artifact_blocks(full_run_lab, artifact_name):
    helper = gate._t01()
    refs = {
        "ClassificationPolicy": full_run_lab.baseline.classification_policy,
        "ClassificationTaxonomy": full_run_lab.source.knowledge.classification_taxonomy,
        "AliasMapping": full_run_lab.source.knowledge.alias_mapping,
        "EvidenceAdapterContractSet": full_run_lab.source.evidence_adapter_contract_set,
        "OriginRuntimeAdmission": full_run_lab.extras["OriginRuntimeAdmission"],
    }
    target = refs[artifact_name]
    with sqlite3.connect(full_run_lab.database) as connection:
        connection.execute("UPDATE artifacts SET content_sha256=? WHERE artifact_id=?",
                           ("0" * 64, target.artifact_id))
    with helper.open_foundation_read_only(full_run_lab.database) as connection:
        lineage = helper.verify_foundation(connection, full_run_lab.api)
        with pytest.raises(helper.Blocked, match="BLOCKED_FOUNDATION_LINEAGE"):
            gate.resolve_admitted(connection, full_run_lab.api, lineage)


def _run_output(output_dir):
    runs = list(output_dir.iterdir())
    assert len(runs) == 1 and runs[0].is_dir()
    return runs[0]


@pytest.mark.parametrize("outcome", ["PASS", "FAIL"])
def test_complete_run_gate_pass_fail(full_run_lab, tmp_path, monkeypatch, outcome):
    helper = gate._t01()
    _stub_semantics(monkeypatch, pytest_exit=0 if outcome == "PASS" else 1)
    db_before = hashlib.sha256(full_run_lab.database.read_bytes()).hexdigest()
    repo_before = helper.repository_filesystem_fingerprint(REPO)
    output = tmp_path / "formal-run-output"
    code = gate.run_gate(REPO, full_run_lab.database, output)
    run_dir = _run_output(output)
    assert code == (0 if outcome == "PASS" else 1)
    assert f"GATE_EXECUTION_STATUS={outcome}" in (run_dir / "t04-summary.txt").read_text()
    assert hashlib.sha256(full_run_lab.database.read_bytes()).hexdigest() == db_before
    assert helper.repository_filesystem_fingerprint(REPO) == repo_before
    proof_file = run_dir / "t04-gate-proof-artifact.json"
    result_file = run_dir / "t04-gate-result-manifest.json"
    assert result_file.is_file()
    assert proof_file.is_file() is (outcome == "PASS")
    result = json.loads(result_file.read_bytes())["semantic_payload"]
    assert result["status"] == outcome
    assert result["gate_id"] == "T-04"
    assert result["gate_contract_version"] == "R14-T-04-v1"
    assert result["candidate_repository_commit_sha"] == gate.EXPECTED_COMMIT
    assert result["candidate_repository_tree_sha"] == gate.EXPECTED_TREE
    if outcome == "PASS":
        proof_doc = json.loads(proof_file.read_bytes())
        proof = proof_doc["semantic_payload"]
        assert proof["proof_kind"] == "FUSION_EXECUTION"
        assert proof["candidate_repository_commit_sha"] == gate.EXPECTED_COMMIT
        assert proof["candidate_repository_tree_sha"] == gate.EXPECTED_TREE
        assert result["output_artifact_refs"] == [{
            "artifact_id": proof_doc["artifact_id"],
            "content_sha256": proof_doc["content_sha256"]}]
    else:
        assert result["output_artifact_refs"] == []
    for ref in result["retained_evidence_refs"]:
        assert ref["file_sha256"] == gate._sha256(run_dir / ref["path_or_reference"])
    assert {"t04-execution-evidence.json", "t04-artifacts.json", "t04-vector-results.json",
            "t04-pytest.log"} <= {file.name for file in run_dir.iterdir()}


@pytest.mark.parametrize("mutation", ["repository", "runner"])
def test_complete_run_gate_mutation_blocks(full_run_lab, tmp_path, monkeypatch, mutation):
    helper = gate._t01()
    _stub_semantics(monkeypatch)
    db_before = hashlib.sha256(full_run_lab.database.read_bytes()).hexdigest()
    repo_before = helper.repository_filesystem_fingerprint(REPO)
    if mutation == "repository":
        original_guard = helper._require_repository_unchanged
        calls = {"count": 0}
        def simulated_change(repo, original):
            calls["count"] += 1
            if calls["count"] >= 2:
                raise helper.Blocked("BLOCKED_REPOSITORY_MUTATED")
            return original_guard(repo, original)
        monkeypatch.setattr(helper, "_require_repository_unchanged", simulated_change)
    else:
        original_integrity = gate._integrity_block
        calls = {"count": 0}
        def simulated_runner_change(path, digest):
            calls["count"] += 1
            if calls["count"] >= 2:
                return "BLOCKED_RUNNER_CHANGED"
            return original_integrity(path, digest)
        monkeypatch.setattr(gate, "_integrity_block", simulated_runner_change)
    output = tmp_path / "blocked-run-output"
    assert gate.run_gate(REPO, full_run_lab.database, output) == 2
    run_dir = _run_output(output)
    expected = "BLOCKED_REPOSITORY_MUTATED" if mutation == "repository" else "BLOCKED_RUNNER_CHANGED"
    assert f"GATE_EXECUTION_STATUS={expected}" in (run_dir / "t04-summary.txt").read_text()
    assert sorted(file.name for file in run_dir.iterdir()) == ["t04-summary.txt"]
    assert hashlib.sha256(full_run_lab.database.read_bytes()).hexdigest() == db_before
    assert helper.repository_filesystem_fingerprint(REPO) == repo_before
