"""Disposable self-tests for external T-02 harness. Never the official T-02 gate."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest


HERE = Path(__file__).resolve().parent
SOURCE = Path("C:/CaptivPortal-UI-Preview")
RUNNER_FILE = HERE / "task04-t02-gate-r1.py"
SPEC = importlib.util.spec_from_file_location("task04_t02_external_runner", RUNNER_FILE)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


def _ref(content):
    return {"artifact_id": content.artifact_id, "content_sha256": content.content_sha256}


def _insert(connection, content):
    connection.execute(
        "INSERT INTO artifacts (artifact_id, artifact_type, content_sha256, "
        "semantic_payload_json) VALUES (?,?,?,?)",
        (content.artifact_id, content.artifact_type, content.content_sha256,
         content.semantic_payload_json))


def _fake_repo(path):
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    (path / "identity.txt").write_text("self-test\n", encoding="utf-8")
    (path / ".gitignore").write_text("ignored.txt\n*.pyc\n__pycache__/\n.pytest_cache/\n",
                                      encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "identity.txt", ".gitignore"], check=True)
    subprocess.run(["git", "-C", str(path), "-c", "user.name=T02 Fixture",
                    "-c", "user.email=t02@example.invalid", "commit", "-q", "-m", "fixture"],
                   check=True)
    return path


@pytest.fixture
def lab(tmp_path, monkeypatch):
    assert SOURCE.is_dir()
    helper = runner._t01()
    api = runner.load_api(SOURCE)
    from app.device_fingerprint.ff5_runtime_profile_atomicity import _Fixture

    database = tmp_path / "foundation-disposable.sqlite"
    fixture = _Fixture(database)
    registry = api.schema.build_foundation_schema_artifacts()[
        "EvidenceSchemaRegistryContract"]
    manifest_payload = fixture.leaves["FoundationAdmissionManifest"].semantic_payload
    manifest_payload["evidence_schema_registry_contract"] = _ref(registry)
    manifest = api.foundation.make_foundation_admission_manifest(manifest_payload)
    profile_payload = fixture.foundation_a.semantic_payload
    profile_payload["evidence_schema_registry_contract"] = _ref(registry)
    profile = api.profiles.make_foundation_runtime_profile(profile_payload)
    rpm_payload = fixture.admission("foundation", fixture.foundation_a).semantic_payload
    rpm_payload["candidate_profile"] = _ref(profile)
    rpm_payload["foundation_admission_manifest"] = _ref(manifest)
    rpm = api.profiles.make_runtime_profile_admission_manifest(rpm_payload)
    activation, validity, _ = fixture.records(rpm, 100)
    gate = api.gate_result.make_gate_result_manifest({
        "gate_id": "F-ADMIT", "gate_contract_version": "R14-F-ADMIT-v1",
        "status": "PASS", "candidate_repository_commit_sha": "a" * 40,
        "candidate_repository_tree_sha": "b" * 40,
        "input_artifact_refs": [], "output_artifact_refs": [
            _ref(item) for item in (manifest, profile, rpm, activation, validity)],
        "retained_evidence_refs": [], "proof_execution_identity": {
            "execution_id": str(uuid.uuid4()), "executor_kind": "TECHLEAD_GATE_TOOL",
            "repository_commit_sha": "a" * 40, "repository_tree_sha": "b" * 40,
            "procedure_or_test_suite_id": "disposable-t02-self-test",
            "environment_identity": "disposable-self-test",
            "execution_artifact_sha256": "c" * 64},
        "trusted_time_inputs": {
            "foundation_knowledge_evaluation_at_utc": None,
            "foundation_admission_evaluation_at_utc": None,
            "knowledge_evaluation_at_utc": None}, "decision_record_refs": []})
    with sqlite3.connect(database) as connection:
        for content in (registry, manifest, profile, rpm, activation, validity, gate):
            _insert(connection, content)
        value = activation.semantic_payload
        connection.execute(
            "INSERT INTO activations (activation_record_id, artifact_id, profile_kind, "
            "runtime_profile_id, runtime_profile_digest, activation_generation_id) "
            "VALUES (?,?,?,?,?,?)",
            (value["activation_record_id"], activation.artifact_id, "foundation",
             profile.artifact_id, profile.content_sha256, value["activation_generation_id"]))
        connection.execute(
            "INSERT INTO active_pointers (profile_kind, runtime_profile_id, "
            "runtime_profile_digest, activation_record_id, activation_generation_id, "
            "updated_at_utc) VALUES (?,?,?,?,?,?)",
            ("foundation", profile.artifact_id, profile.content_sha256,
             value["activation_record_id"], value["activation_generation_id"],
             value["activated_at_utc"]))
        validity_value = validity.semantic_payload
        connection.execute(
            "INSERT INTO validities (validity_record_id, artifact_id, activation_record_id) "
            "VALUES (?,?,?)",
            (validity_value["validity_record_id"], validity.artifact_id,
             value["activation_record_id"]))
        connection.execute(
            "INSERT INTO validity_heads (activation_record_id, validity_record_id, "
            "updated_at_utc) VALUES (?,?,?)",
            (value["activation_record_id"], validity_value["validity_record_id"],
             validity_value["effective_at_utc"]))
        connection.execute(
            "INSERT INTO f_admit_publications (gate_id, artifact_id, content_sha256) "
            "VALUES (?,?,?)", ("F-ADMIT", gate.artifact_id, gate.content_sha256))
    repo = _fake_repo(tmp_path / "repo-disposable")
    head = helper._git(repo, "rev-parse", "HEAD")
    tree = helper._git(repo, "show", "-s", "--format=%T", "HEAD")
    monkeypatch.setattr(helper, "EXPECTED_COMMIT", head)
    monkeypatch.setattr(helper, "EXPECTED_TREE", tree)
    monkeypatch.setattr(helper, "EXPECTED_DIGESTS", {
        "FoundationAdmissionManifest": manifest.content_sha256,
        "FoundationRuntimeProfile": profile.content_sha256,
        "RuntimeProfileAdmissionManifest": rpm.content_sha256,
        "GateResultManifest": gate.content_sha256,
        "EvidenceSchemaRegistryContract": registry.content_sha256})
    monkeypatch.setattr(runner, "EXPECTED_COMMIT", head)
    monkeypatch.setattr(runner, "EXPECTED_TREE", tree)
    monkeypatch.setattr(runner, "load_api", lambda _repo: api)
    lineage = helper.FoundationLineage(manifest, profile, rpm, activation, validity, gate, registry)
    return lineage, repo, database, api


def test_repository_identity_and_ignored_fingerprint(lab, tmp_path):
    _, repo, _, _ = lab
    helper = runner._t01()
    helper.verify_repository(repo)
    before = helper.repository_filesystem_fingerprint(repo)
    (repo / "ignored.txt").write_text("ignored-byte", encoding="utf-8")
    with pytest.raises(helper.Blocked, match="BLOCKED_REPOSITORY_MUTATED"):
        helper._require_repository_unchanged(repo, before)


@pytest.mark.parametrize("mutation", ("wrong_commit", "wrong_tree", "dirty"))
def test_wrong_candidate_identity_blocked(lab, monkeypatch, mutation):
    _, repo, _, _ = lab
    helper = runner._t01()
    if mutation == "wrong_commit":
        monkeypatch.setattr(helper, "EXPECTED_COMMIT", "0" * 40)
    elif mutation == "wrong_tree":
        monkeypatch.setattr(helper, "EXPECTED_TREE", "0" * 40)
    else:
        (repo / "dirty.txt").write_text("dirty", encoding="utf-8")
    with pytest.raises(helper.Blocked, match="BLOCKED_CANDIDATE_IDENTITY"):
        helper.verify_repository(repo)


@pytest.mark.parametrize("mutation", ("missing_db", "inactive", "missing_head",
                                          "tampered_dependency"))
def test_foundation_lineage_fail_closed(lab, tmp_path, mutation):
    lineage, _, database, api = lab
    helper = runner._t01()
    if mutation == "missing_db":
        with pytest.raises(helper.Blocked, match="BLOCKED_FOUNDATION_LINEAGE"):
            helper.open_foundation_read_only(tmp_path / "missing.sqlite")
        return
    with sqlite3.connect(database) as connection:
        if mutation == "inactive":
            payload = lineage.validity.semantic_payload
            previous_id = payload["validity_record_id"]
            payload["validity_record_id"] = str(uuid.uuid4())
            payload["previous_validity_record_id"] = previous_id
            payload["state"] = "INACTIVE"
            payload["reason_code"] = "SUPERSEDED_SAFE"
            payload["inflight_commit_rule"] = "ALLOW_PINNED_INFLIGHT"
            inactive = api.profiles.make_runtime_profile_validity_record(payload)
            _insert(connection, inactive)
            connection.execute("INSERT INTO validities (validity_record_id, artifact_id, "
                               "activation_record_id) VALUES (?,?,?)",
                               (payload["validity_record_id"], inactive.artifact_id,
                                payload["activation_record_id"]))
            connection.execute("UPDATE validity_heads SET validity_record_id=?",
                               (payload["validity_record_id"],))
        elif mutation == "missing_head":
            connection.execute("DELETE FROM validity_heads")
        else:
            connection.execute("UPDATE artifacts SET content_sha256=? WHERE "
                               "artifact_type='FoundationRuntimeProfile'", ("0" * 64,))
    connection = helper.open_foundation_read_only(database)
    try:
        with pytest.raises(helper.Blocked, match="BLOCKED_FOUNDATION_LINEAGE"):
            helper.verify_foundation(connection, api)
    finally:
        connection.rollback()
        connection.close()


def test_pytest_subprocess_environment_and_external_temp(tmp_path, monkeypatch):
    observed = {}
    class Result:
        returncode = 0
        stdout = "self-test pytest stub\n"
    def fake_run(command, **kwargs):
        observed.update(command=command, kwargs=kwargs)
        return Result()
    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    status, log, _ = runner.execute_pytest(SOURCE, tmp_path)
    assert status == 0 and log == Result.stdout
    command = observed["command"]
    environment = observed["kwargs"]["env"]
    assert command[-1] == "tests/device_fingerprint_task04_t02"
    assert command[command.index("-p") + 1] == "no:cacheprovider"
    assert "--basetemp" in command
    assert not Path(command[command.index("--basetemp") + 1]).is_relative_to(SOURCE)
    assert environment["PYTHONDONTWRITEBYTECODE"] == "1"
    assert environment["PYTEST_ADDOPTS"] == ""
    assert all(Path(environment[name]).is_relative_to(tmp_path) for name in
               ("TEMP", "TMP", "TMPDIR"))


def test_direct_matrix_uses_real_builders_and_retains_artifacts(tmp_path):
    api = runner.load_api(SOURCE)
    from tests.device_fingerprint_task04_t01.test_snapshot_service import context
    ctx = context()
    pinned = {field: ctx.contents[ctx.profile.semantic_payload[field]["artifact_id"]]
              for field in ("source_health_policy", "evidence_source_binding_timeline",
                            "binding_clock_policy")}
    resolver = lambda ref: ctx.contents[ref.artifact_id]
    matrix, inventory = runner._execute_matrix(tmp_path, api, ctx.profile, pinned, resolver)
    assert set(matrix["cases"]) == set(runner.CASE_IDS)
    assert matrix["all_pass"], json.dumps(matrix, indent=2)
    assert matrix["cases"]["T02-M07"]["fixture_mode"] == "ADMITTED_FOUNDATION_CUTOVER"
    assert matrix["cases"]["T02-M07"]["fixture_source_module_relative_path"] is None
    assert matrix["traces"]["freshness"]
    assert matrix["traces"]["cutover"]
    assert len(matrix["traces"]["present_evidence"]) == 3
    assert inventory["artifacts"]
    assert {document["artifact_type"] for document in inventory["artifacts"]} == {
        "EvidenceSnapshotContent", "SourceEvaluability"}
    for document in inventory["artifacts"]:
        assert set(document) == {"artifact_type", "artifact_schema_version", "artifact_id",
                                 "content_sha256", "semantic_payload"}


def _no_admitted_cutover(api):
    from tests.device_fingerprint_task04_t01.test_snapshot_service import context
    ctx = context()
    admitted = ctx.contents[ctx.profile.semantic_payload[
        "evidence_source_binding_timeline"]["artifact_id"]]
    second = admitted.semantic_payload["binding_epochs"][-1]
    emitter = ctx.contents[second["source_health_emitter_contract"]["artifact_id"]]
    timeline = api.binding.make_evidence_source_binding_timeline({
        "binding_timeline_contract_version": 1, "binding_epochs": [second]}, [emitter])
    ctx.contents[timeline.artifact_id] = timeline
    profile_payload = ctx.profile.semantic_payload
    profile_payload["evidence_source_binding_timeline"] = _ref(timeline)
    profile = api.profiles.make_foundation_runtime_profile(profile_payload)
    pinned = {field: ctx.contents[profile.semantic_payload[field]["artifact_id"]]
              for field in ("source_health_policy", "evidence_source_binding_timeline",
                            "binding_clock_policy")}
    return profile, pinned, lambda ref: ctx.contents[ref.artifact_id]


def test_no_admitted_cutover_executes_controlled_candidate_fixture(tmp_path):
    api = runner.load_api(SOURCE)
    profile, pinned, resolver = _no_admitted_cutover(api)
    matrix, inventory = runner._execute_matrix(tmp_path, api, profile, pinned, resolver)
    m07 = matrix["cases"]["T02-M07"]
    assert matrix["all_pass"], json.dumps(matrix, indent=2)
    assert set(matrix["cases"]) == set(runner.CASE_IDS)
    assert m07["status"] == "PASS"
    assert m07["fixture_mode"] == "CONTROLLED_CANDIDATE_CUTOVER_FIXTURE"
    assert m07["fixture_source_module_relative_path"] == (
        "tests/device_fingerprint_task04_t01/test_snapshot_service.py")
    assert m07["fixture_foundation_runtime_profile"] != _ref(profile)
    assert m07["fixture_evidence_source_binding_timeline"] != _ref(pinned[
        "evidence_source_binding_timeline"])
    assert m07["old_binding_epoch_id"] != m07["new_binding_epoch_id"]
    assert m07["cutover_guard_seconds"] > 0
    assert m07["evidence_snapshot_content"]["artifact_id"]
    assert m07["source_evaluability"]["artifact_id"]
    assert len([item for item in inventory["artifacts"] if item["artifact_type"] ==
                "SourceEvaluability"]) > 0


def test_controlled_cutover_semantic_failure_stays_fail(tmp_path, monkeypatch):
    api = runner.load_api(SOURCE)
    profile, pinned, resolver = _no_admitted_cutover(api)
    original = runner._health_row
    def bad_old_health(epoch, observed, number, status, reason, ingested):
        if number == 70:
            status, reason = "unavailable", "capture_interface_unavailable"
        return original(epoch, observed, number, status, reason, ingested)
    monkeypatch.setattr(runner, "_health_row", bad_old_health)
    matrix, _ = runner._execute_matrix(tmp_path, api, profile, pinned, resolver)
    assert set(matrix["cases"]) == set(runner.CASE_IDS)
    assert matrix["cases"]["T02-M07"]["fixture_mode"] == (
        "CONTROLLED_CANDIDATE_CUTOVER_FIXTURE")
    assert matrix["cases"]["T02-M07"]["status"] == "FAIL"
    assert not matrix["all_pass"]


def test_controlled_fixture_module_origin_fail_closed(tmp_path, monkeypatch):
    api = runner.load_api(SOURCE)
    outside = tmp_path / "not-candidate-module.py"
    outside.write_text("fixture outside candidate", encoding="utf-8")
    real_import = runner.importlib.import_module
    def wrong_origin(name):
        if name == "tests.device_fingerprint_task04_t01.test_snapshot_service":
            return SimpleNamespace(__file__=str(outside), context=lambda: None)
        return real_import(name)
    monkeypatch.setattr(runner.importlib, "import_module", wrong_origin)
    with pytest.raises(runner._t01().Blocked, match="BLOCKED_CANDIDATE_IDENTITY"):
        runner._controlled_cutover_context(api)


def test_exact_pinned_dependency_resolution_and_wrong_policy_block(tmp_path):
    api = runner.load_api(SOURCE)
    from tests.device_fingerprint_task04_t01.test_snapshot_service import context
    ctx = context()
    path = tmp_path / "pinned-disposable.sqlite"
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("CREATE TABLE artifacts (artifact_id TEXT, artifact_type TEXT, "
                           "content_sha256 TEXT, semantic_payload_json TEXT)")
        for content in ctx.contents.values():
            _insert(connection, content)
        lineage = SimpleNamespace(profile=ctx.profile)
        pinned, resolver = runner.resolve_pinned(connection, api, lineage)
        assert set(pinned) == {"source_health_policy", "evidence_source_binding_timeline",
                               "binding_clock_policy"}
        for field, content in pinned.items():
            assert _ref(content) == ctx.profile.semantic_payload[field]
        builder = api.source.DeviceFingerprintSourceEvaluabilityBuilder(
            foundation_runtime_profile=ctx.profile, artifact_resolver=resolver)
        assert builder is not None
        connection.execute("UPDATE artifacts SET content_sha256=? WHERE artifact_id=?",
                           ("0" * 64, pinned["source_health_policy"].artifact_id))
        with pytest.raises(runner._t01().Blocked, match="BLOCKED_FOUNDATION_LINEAGE"):
            runner.resolve_pinned(connection, api, lineage)


def test_formal_artifacts_and_evidence_hashes(lab, tmp_path):
    lineage, _, database, api = lab
    run_dir = tmp_path / "formal-disposable"
    run_dir.mkdir()
    for name in ("t02-execution-evidence.json", "t02-artifacts.json", "t02-pytest.log"):
        (run_dir / name).write_bytes(b"disposable self-test\n")
    pinned = {}
    connection = runner._t01().open_foundation_read_only(database)
    try:
        for field in ("source_health_policy", "evidence_source_binding_timeline",
                      "binding_clock_policy"):
            reference = lineage.profile.semantic_payload[field]
            pinned[field] = runner._t01()._resolve_artifact(connection, api, reference)
    finally:
        connection.rollback()
        connection.close()
    proof, result = runner._formal_outputs(run_dir, api, lineage, pinned, "a" * 64, True)
    assert proof.semantic_payload["proof_kind"] == "SOURCE_EVALUABILITY_EXECUTION"
    assert result.semantic_payload["gate_id"] == "T-02"
    assert result.semantic_payload["gate_contract_version"] == "R14-T-02-v1"
    assert result.semantic_payload["status"] == "PASS"
    expected = [_ref(lineage.profile), *(_ref(item) for item in pinned.values())]
    assert {tuple(sorted(ref.items())) for ref in result.semantic_payload["input_artifact_refs"]} == {
        tuple(sorted(ref.items())) for ref in expected}
    for ref in result.semantic_payload["retained_evidence_refs"]:
        assert ref["file_sha256"] == runner._sha256(run_dir / ref["path_or_reference"])
    fail_dir = tmp_path / "formal-fail"
    fail_dir.mkdir()
    for name in ("t02-execution-evidence.json", "t02-artifacts.json", "t02-pytest.log"):
        (fail_dir / name).write_bytes(b"disposable fail self-test\n")
    no_proof, failed = runner._formal_outputs(fail_dir, api, lineage, pinned, "a" * 64, False)
    assert no_proof is None and failed.semantic_payload["status"] == "FAIL"
    assert failed.semantic_payload["output_artifact_refs"] == []
    assert not (fail_dir / "t02-gate-proof-artifact.json").exists()


def test_runner_hash_and_blocked_formal_output(tmp_path, monkeypatch):
    assert runner._sha256(RUNNER_FILE) == hashlib.sha256(RUNNER_FILE.read_bytes()).hexdigest()
    assert runner._sha256(runner.T01_HELPER) == runner.T01_HELPER_SHA256
    run_dir = tmp_path / "blocked"
    run_dir.mkdir()
    (run_dir / "t02-gate-result-manifest.json").write_text("disposable", encoding="utf-8")
    assert runner._blocked(run_dir, "BLOCKED_RUNNER_CHANGED") == 2
    assert not (run_dir / "t02-gate-result-manifest.json").exists()
    assert "BLOCKED_RUNNER_CHANGED" in (run_dir / "t02-summary.txt").read_text()


@pytest.mark.parametrize("outcome", ("pass", "fail", "ignored_mutation",
                                     "runner_mutation", "fixture_origin"))
def test_disposable_gate_state_machine_and_no_foundation_write(lab, tmp_path,
                                                                monkeypatch, outcome):
    lineage, repo, database, api = lab
    foundation_before = hashlib.sha256(database.read_bytes()).hexdigest()
    repository_before = runner._t01().repository_filesystem_fingerprint(repo)
    connection = runner._t01().open_foundation_read_only(database)
    try:
        pinned = {field: runner._t01()._resolve_artifact(
            connection, api, lineage.profile.semantic_payload[field]) for field in (
                "source_health_policy", "evidence_source_binding_timeline",
                "binding_clock_policy")}
    finally:
        connection.rollback()
        connection.close()
    monkeypatch.setattr(runner, "resolve_pinned", lambda *_: (pinned, lambda _ref: None))
    matrix = {"cases": {case: {"status": "PASS", "input_fixture_sha256": "a" * 64}
                        for case in runner.CASE_IDS}, "traces": {}, "all_pass": True}
    if outcome == "fixture_origin":
        monkeypatch.setattr(api, "repo", repo)
        monkeypatch.setattr(runner, "execute_matrix",
                            lambda *_: runner._controlled_cutover_context(api))
    else:
        monkeypatch.setattr(runner, "execute_matrix", lambda *_: (matrix, {"artifacts": []}))
    def fake_pytest(_repo, _run_dir):
        if outcome == "ignored_mutation":
            (repo / "ignored.txt").write_text("unexpected", encoding="utf-8")
        return (1 if outcome == "fail" else 0, "disposable pytest stub\n",
                "python -m pytest -q tests/device_fingerprint_task04_t02")
    monkeypatch.setattr(runner, "execute_pytest", fake_pytest)
    original_sha = runner._sha256
    if outcome == "runner_mutation":
        calls = {"runner": 0}
        def changed_sha(path):
            if Path(path).resolve() == RUNNER_FILE:
                calls["runner"] += 1
                if calls["runner"] >= 2:
                    return "0" * 64
            return original_sha(path)
        monkeypatch.setattr(runner, "_sha256", changed_sha)
    output = tmp_path / "external-output"
    status = runner.run_gate(repo, database, output)
    run_dir = next(output.iterdir())
    if outcome in ("ignored_mutation", "runner_mutation", "fixture_origin"):
        assert status == 2
        assert not (run_dir / "t02-gate-result-manifest.json").exists()
        assert not (run_dir / "t02-gate-proof-artifact.json").exists()
    else:
        assert status == (0 if outcome == "pass" else 1)
        result = json.loads((run_dir / "t02-gate-result-manifest.json").read_bytes())
        assert result["semantic_payload"]["status"] == ("PASS" if outcome == "pass" else "FAIL")
        assert result["semantic_payload"]["gate_id"] == "T-02"
        assert result["semantic_payload"]["gate_contract_version"] == "R14-T-02-v1"
        assert (run_dir / "t02-gate-proof-artifact.json").exists() == (outcome == "pass")
        for ref in result["semantic_payload"]["retained_evidence_refs"]:
            assert ref["file_sha256"] == original_sha(run_dir / ref["path_or_reference"])
    assert hashlib.sha256(database.read_bytes()).hexdigest() == foundation_before
    if outcome != "ignored_mutation":
        assert runner._t01().repository_filesystem_fingerprint(repo) == repository_before
