"""Disposable self-tests for the external T-03 harness; never run the official gate."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sqlite3
import sys
import uuid
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace

import pytest


sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "task04-t03-gate-r1.py"
REPO = Path(r"C:\CaptivPortal-UI-Preview")
SPEC = importlib.util.spec_from_file_location("task04_t03_gate_selftest_target", RUNNER)
assert SPEC is not None and SPEC.loader is not None
gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)


def test_exact_candidate_and_complete_fingerprint_guard(tmp_path):
    helper = gate._t01()
    helper.verify_repository(REPO)
    assert helper._git(REPO, "rev-parse", "HEAD") == gate.EXPECTED_COMMIT
    assert helper._git(REPO, "show", "-s", "--format=%T", "HEAD") == gate.EXPECTED_TREE
    assert not helper._git(REPO, "status", "--porcelain")
    original = helper.repository_filesystem_fingerprint(REPO)
    helper._require_repository_unchanged(REPO, original)
    ignored = tmp_path / "ignored.fixture"
    ignored.write_bytes(b"before")
    # Same fingerprint algorithm catches even ignored/untracked changes.
    before = helper.repository_filesystem_fingerprint(tmp_path)
    ignored.write_bytes(b"after")
    with pytest.raises(helper.Blocked, match="BLOCKED_REPOSITORY_MUTATED"):
        helper._require_repository_unchanged(tmp_path, before)


@pytest.mark.parametrize("difference", ["commit", "tree", "dirty"])
def test_wrong_candidate_identity_blocks(monkeypatch, difference):
    helper = gate._t01()
    original_git = helper._git

    def wrong(repo, *args):
        if difference == "commit" and args == ("rev-parse", "HEAD"):
            return "0" * 40
        if difference == "tree" and args == ("show", "-s", "--format=%T", "HEAD"):
            return "0" * 40
        if difference == "dirty" and args == ("status", "--porcelain"):
            return "?? ignored"
        return original_git(repo, *args)

    monkeypatch.setattr(helper, "_git", wrong)
    with pytest.raises(helper.Blocked, match="BLOCKED_CANDIDATE_IDENTITY"):
        helper.verify_repository(REPO)


def test_helper_and_runner_hash_guards(monkeypatch, tmp_path):
    assert gate._sha256(gate.T01_HELPER) == gate.T01_HELPER_SHA256
    digest = gate._sha256(RUNNER)
    assert gate._runner_intact(RUNNER, digest)
    monkeypatch.setattr(gate, "T01_HELPER_SHA256", "0" * 64)
    assert not gate._runner_intact(RUNNER, digest)
    with pytest.raises(RuntimeError, match="BLOCKED_HARDENED_HELPER_CHANGED"):
        gate._t01()
    changed = tmp_path / "runner.py"
    changed.write_bytes(RUNNER.read_bytes() + b"# mutation\n")
    assert gate._sha256(changed) != digest


def test_fixture_origin_guard(monkeypatch):
    fake = SimpleNamespace(__file__=r"C:\outside\fixture.py")
    monkeypatch.setattr(gate.importlib, "import_module", lambda _name: fake)
    with pytest.raises(gate._t01().Blocked, match="BLOCKED_CANDIDATE_IDENTITY"):
        gate._candidate_module(REPO, "fixture.outside")


def test_missing_foundation_and_readonly_bytes(tmp_path):
    helper = gate._t01()
    with pytest.raises(helper.Blocked, match="BLOCKED_FOUNDATION_LINEAGE"):
        helper.open_foundation_read_only(tmp_path / "missing.sqlite")
    path = tmp_path / "foundation.sqlite"
    with sqlite3.connect(path) as db:
        for table in ("artifacts", "activations", "validities", "validity_heads",
                      "active_pointers", "f_admit_publications"):
            db.execute(f"CREATE TABLE {table} (id TEXT)")
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    db = helper.open_foundation_read_only(path)
    assert db.execute("PRAGMA query_only").fetchone()[0] == 1
    with pytest.raises(sqlite3.OperationalError):
        db.execute("INSERT INTO artifacts VALUES ('write')")
    db.rollback()
    db.close()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_active_validity_and_missing_head_fail_closed(tmp_path, monkeypatch):
    # Build a disposable control DB using the exact candidate's existing F-F5 fixture.
    api = gate.load_api(REPO)
    helper = gate._t01()
    fixture_module = gate._candidate_module(
        REPO, "app.device_fingerprint.ff5_runtime_profile_atomicity")
    database = tmp_path / "foundation-disposable.sqlite"
    fixture = fixture_module._Fixture(database)
    registry = api.schema.build_foundation_schema_artifacts()["EvidenceSchemaRegistryContract"]
    manifest_payload = fixture.leaves["FoundationAdmissionManifest"].semantic_payload
    manifest_payload["evidence_schema_registry_contract"] = gate._ref(registry)
    manifest = api.foundation.make_foundation_admission_manifest(manifest_payload)
    profile_payload = fixture.foundation_a.semantic_payload
    profile_payload["evidence_schema_registry_contract"] = gate._ref(registry)
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
        "input_artifact_refs": [],
        "output_artifact_refs": [gate._ref(item) for item in
                                 (manifest, profile, admission, activation, validity)],
        "retained_evidence_refs": [],
        "proof_execution_identity": {
            "execution_id": str(uuid.uuid4()), "executor_kind": "TECHLEAD_GATE_TOOL",
            "repository_commit_sha": "a" * 40, "repository_tree_sha": "b" * 40,
            "procedure_or_test_suite_id": "disposable-t03-self-test",
            "environment_identity": "disposable-self-test",
            "execution_artifact_sha256": "c" * 64},
        "trusted_time_inputs": {
            "foundation_knowledge_evaluation_at_utc": None,
            "foundation_admission_evaluation_at_utc": None,
            "knowledge_evaluation_at_utc": None},
        "decision_record_refs": []})
    with sqlite3.connect(database) as connection:
        for content in (registry, manifest, profile, admission, activation, validity, result):
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

    def verify():
        db = helper.open_foundation_read_only(database)
        try:
            return helper.verify_foundation(db, api)
        finally:
            db.rollback()
            db.close()

    assert verify().validity == validity
    with sqlite3.connect(database) as connection:
        connection.execute("DELETE FROM validity_heads")
    with pytest.raises(helper.Blocked, match="BLOCKED_FOUNDATION_LINEAGE"):
        verify()
    with sqlite3.connect(database) as connection:
        changed = valid.copy()
        changed["validity_record_id"] = str(uuid.uuid4())
        changed["previous_validity_record_id"] = valid["validity_record_id"]
        changed["state"] = "INACTIVE"
        changed["reason_code"] = "SUPERSEDED_SAFE"
        changed["inflight_commit_rule"] = "ALLOW_PINNED_INFLIGHT"
        inactive = api.profiles.make_runtime_profile_validity_record(changed)
        connection.execute(
            "INSERT INTO artifacts (artifact_id, artifact_type, content_sha256, "
            "semantic_payload_json) VALUES (?,?,?,?)",
            (inactive.artifact_id, inactive.artifact_type, inactive.content_sha256,
             inactive.semantic_payload_json))
        connection.execute(
            "INSERT INTO validities (validity_record_id, artifact_id, activation_record_id) "
            "VALUES (?,?,?)",
            (changed["validity_record_id"], inactive.artifact_id, active["activation_record_id"]))
        connection.execute(
            "INSERT INTO validity_heads (activation_record_id, validity_record_id, updated_at_utc) "
            "VALUES (?,?,?)",
            (active["activation_record_id"], changed["validity_record_id"],
             valid["effective_at_utc"]))
    with pytest.raises(helper.Blocked, match="BLOCKED_FOUNDATION_LINEAGE"):
        verify()


def test_pytest_command_and_environment_external(monkeypatch, tmp_path):
    seen = {}

    def subprocess_stub(command, *, cwd, env, **_kwargs):
        seen.update(command=command, cwd=cwd, env=env)
        return SimpleNamespace(returncode=0, stdout="candidate suite passed\n")

    monkeypatch.setattr(gate.subprocess, "run", subprocess_stub)
    status, output, command = gate.execute_pytest(REPO, tmp_path)
    assert status == 0 and "candidate suite passed" in output
    assert "tests/device_fingerprint_task04_t03" in seen["command"]
    assert seen["command"][seen["command"].index("-p") + 1] == "no:cacheprovider"
    base = Path(seen["command"][seen["command"].index("--basetemp") + 1])
    assert base.is_relative_to(tmp_path) and not base.is_relative_to(REPO)
    assert seen["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
    assert seen["env"]["PYTEST_ADDOPTS"] == ""
    assert all(Path(seen["env"][name]).is_relative_to(tmp_path)
               for name in ("TEMP", "TMP", "TMPDIR"))
    assert "--basetemp" in command


def test_direct_matrix_exact_semantics_and_retained_artifacts():
    api = gate.load_api(REPO)
    original = gate._t01().repository_filesystem_fingerprint(REPO)
    matrix, artifacts = gate.execute_matrix(api)
    gate._t01()._require_repository_unchanged(REPO, original)
    assert set(matrix["cases"]) == set(gate.CASE_IDS)
    assert matrix["all_pass"], {
        key: value for key, value in matrix["cases"].items() if value["status"] != "PASS"}
    assert len(matrix["cases"]) == 12
    assert artifacts["lineage_kind"] == "CONTROLLED_CANDIDATE_FIXTURES_NOT_FORMAL_ADMITTED_INPUTS"
    kinds = {row["artifact_type"] for row in artifacts["artifacts"]}
    assert {"EvidenceSnapshotContent", "SourceEvaluability", "OriginAssessment",
            "KnowledgeBundle", "CanonicalKnowledgeRecordSet", "K3PortalRuleSet"} <= kinds
    for case in matrix["cases"].values():
        assert len(case["input_fixture_sha256"]) == 64
        assert case["trace"]
    assert "ja4_no_semantic_claim" in matrix["cases"]["T03-M08"]["trace"][0]["explanation_codes"]
    assert "no_ieee_assignment_claim" in matrix["cases"]["T03-M10"]["trace"][0]["explanation_codes"]


def test_evidence_hash_freeze(tmp_path):
    for name, data in (("t03-execution-evidence.json", b"{}\n"),
                       ("t03-artifacts.json", b"{}\n"),
                       ("t03-pytest.log", b"passed\n")):
        (tmp_path / name).write_bytes(data)
    refs = gate._evidence_refs(tmp_path)
    assert len(refs) == 3
    for ref in refs:
        assert ref["file_sha256"] == gate._sha256(tmp_path / ref["path_or_reference"])


def test_output_dir_and_missing_database_block_without_formal_artifacts(tmp_path):
    out = tmp_path / "out"
    assert gate.run_gate(REPO, tmp_path / "missing.sqlite", out) == 2
    run_dirs = list(out.iterdir())
    assert len(run_dirs) == 1
    assert not list(run_dirs[0].glob("*gate*artifact.json"))
    assert not list(run_dirs[0].glob("*gate*manifest.json"))
    assert "BLOCKED_FOUNDATION_LINEAGE" in (run_dirs[0] / "t03-summary.txt").read_text()
    assert gate.run_gate(REPO, tmp_path / "missing.sqlite", out) == 2


def test_blocked_cleanup_removes_formal_outputs(tmp_path):
    for name in ("t03-gate-proof-artifact.json", "t03-gate-result-manifest.json",
                 "t03-execution-evidence.json", "t03-artifacts.json", "t03-pytest.log"):
        (tmp_path / name).write_text("stale")
    assert gate._blocked(tmp_path, "BLOCKED_RUNNER_CHANGED") == 2
    assert sorted(item.name for item in tmp_path.iterdir()) == ["t03-summary.txt"]


def test_formal_result_contract_constants():
    assert gate.GATE_ID == "T-03"
    assert gate.GATE_CONTRACT == "R14-T-03-v1"
    assert gate.PROOF_KIND == "ORIGIN_ASSESSMENT_EXECUTION"
    assert gate.PROCEDURE == "T-03-origin-assessment-execution-v1"
    assert gate.CASE_IDS == tuple(f"T03-M{number:02d}" for number in range(1, 13))


@pytest.fixture
def admitted_fixture(monkeypatch):
    api = gate.load_api(REPO)
    test_module = gate._candidate_module(REPO, "tests.device_fingerprint_task04_t03.test_origin_assessment")
    t01 = gate._candidate_module(REPO, "tests.device_fingerprint_task04_t01.test_snapshot_service")
    inputs = test_module._inputs()
    context = t01.context()
    registry_ref = context.profile.semantic_payload["evidence_schema_registry_contract"]
    registry = context.contents[registry_ref["artifact_id"]]
    extras = {item.artifact_type: item for item in context.contents.values()
              if item.artifact_type in ("CapabilityDisposition", "K2AConformancePackage")}
    assert set(extras) == {"CapabilityDisposition", "K2AConformancePackage"}
    candidate = inputs.knowledge
    artifacts = [registry, inputs.evidence_adapter_contract_set, inputs.knowledge_bundle,
                 *extras.values(), *(getattr(candidate, field.name) for field in fields(candidate))]
    by_id = {content.artifact_id: content for content in artifacts}
    manifest = SimpleNamespace(semantic_payload={
        "evidence_adapter_contract_set": gate._ref(inputs.evidence_adapter_contract_set),
        "knowledge_bundle": gate._ref(inputs.knowledge_bundle),
        "portal_headers_v2_capability_disposition": gate._ref(extras["CapabilityDisposition"]),
        "k2a_conformance_package": gate._ref(extras["K2AConformancePackage"]),
    })
    lineage = SimpleNamespace(manifest=manifest, registry=registry, profile=context.profile)
    helper = gate._t01()

    def resolve(_connection, _api, reference):
        if reference["artifact_id"] not in by_id:
            raise ValueError("missing admitted reference")
        content = by_id[reference["artifact_id"]]
        if content.content_sha256 != reference["content_sha256"]:
            raise ValueError("tampered admitted digest")
        return content

    monkeypatch.setattr(helper, "_resolve_artifact", resolve)
    return api, lineage, inputs, by_id


def test_exact_admitted_bundle_adapter_and_transitive_inventory(admitted_fixture):
    api, lineage, inputs, _ = admitted_fixture
    result = gate.resolve_admitted(None, api, lineage)
    assert result["adapter"] == inputs.evidence_adapter_contract_set
    assert result["bundle"] == inputs.knowledge_bundle
    assert set(result["resolved"]) == {
        "classification_taxonomy", "alias_mapping", "k1_record_set",
        "k2b_record_set", "k3_portal_rule_set", "k4_record_set"}
    assert len(result["inventories"]["knowledge_provenance_manifests"]) == 4
    assert len(result["inventories"]["source_governance_records"]) == 3
    assert len(result["inventories"]["knowledge_freshness_policies"]) == 3


@pytest.mark.parametrize("kind", ["adapter", "bundle", "k1", "k2b", "k3", "k4"])
def test_tampered_admitted_reference_blocks(admitted_fixture, kind):
    api, lineage, inputs, _ = admitted_fixture
    if kind in ("adapter", "bundle"):
        field = "evidence_adapter_contract_set" if kind == "adapter" else "knowledge_bundle"
        old = lineage.manifest.semantic_payload[field]
        lineage.manifest.semantic_payload[field] = {**old, "content_sha256": "0" * 64}
    else:
        field = {"k1": "k1_record_set", "k2b": "k2b_record_set",
                 "k3": "k3_portal_rule_set", "k4": "k4_record_set"}[kind]
        target_id = inputs.knowledge_bundle.semantic_payload[field]["artifact_id"]
        # Simulate a missing/tampered DB row for the exact pinned bundle dependency.
        original = gate._t01()._resolve_artifact
        def resolve(_conn, _api, reference):
            if reference["artifact_id"] == target_id:
                raise ValueError("tampered reference")
            return original(_conn, _api, reference)
        gate._t01()._resolve_artifact = resolve
        try:
            with pytest.raises(gate._t01().Blocked, match="BLOCKED_FOUNDATION_LINEAGE"):
                gate.resolve_admitted(None, api, lineage)
        finally:
            gate._t01()._resolve_artifact = original
        return
    with pytest.raises(gate._t01().Blocked, match="BLOCKED_FOUNDATION_LINEAGE"):
        gate.resolve_admitted(None, api, lineage)


def test_formal_pass_fail_contract_and_hash_bindings(tmp_path, admitted_fixture):
    api, lineage, inputs, _ = admitted_fixture
    admitted = gate.resolve_admitted(None, api, lineage)
    for passed in (True, False):
        run_dir = tmp_path / ("pass" if passed else "fail")
        run_dir.mkdir()
        for name, value in (("t03-execution-evidence.json", b"{}\n"),
                            ("t03-artifacts.json", b"{}\n"),
                            ("t03-pytest.log", b"suite result\n")):
            (run_dir / name).write_bytes(value)
        proof, result = gate._formal_outputs(run_dir, api, lineage, admitted,
                                             gate._sha256(RUNNER), passed)
        assert result.semantic_payload["status"] == ("PASS" if passed else "FAIL")
        assert result.semantic_payload["gate_id"] == "T-03"
        assert result.semantic_payload["gate_contract_version"] == "R14-T-03-v1"
        assert result.semantic_payload["decision_record_refs"] == []
        assert result.semantic_payload["output_artifact_refs"] == ([gate._ref(proof)] if passed else [])
        assert (run_dir / "t03-gate-proof-artifact.json").exists() is passed
        if passed:
            assert proof.semantic_payload["proof_kind"] == "ORIGIN_ASSESSMENT_EXECUTION"
            assert proof.semantic_payload["canonical_result_summary"] == "T-03:pytest=PASS;matrix=12/12 PASS"
        for ref in result.semantic_payload["retained_evidence_refs"]:
            assert ref["file_sha256"] == gate._sha256(run_dir / ref["path_or_reference"])


@pytest.fixture
def full_run_lab(tmp_path, monkeypatch):
    """Disposable but fully resolvable F-ADMIT/knowledge control DB for run_gate."""
    api = gate.load_api(REPO)
    helper = gate._t01()
    t03 = gate._candidate_module(REPO, "tests.device_fingerprint_task04_t03.test_origin_assessment")
    t01 = gate._candidate_module(REPO, "tests.device_fingerprint_task04_t01.test_snapshot_service")
    ff5 = gate._candidate_module(REPO, "app.device_fingerprint.ff5_runtime_profile_atomicity")
    inputs = t03._inputs()
    context = t01.context()
    knowledge = inputs.knowledge
    registry = context.contents[context.profile.semantic_payload[
        "evidence_schema_registry_contract"]["artifact_id"]]
    dependencies = {content.artifact_type: content for content in context.contents.values()
                    if content.artifact_type in ("CapabilityDisposition", "K2AConformancePackage")}
    assert set(dependencies) == {"CapabilityDisposition", "K2AConformancePackage"}
    database = tmp_path / "disposable-t03-foundation.sqlite"
    fixture = ff5._Fixture(database)
    manifest_payload = fixture.leaves["FoundationAdmissionManifest"].semantic_payload
    manifest_payload.update({
        "evidence_schema_registry_contract": gate._ref(registry),
        "evidence_adapter_contract_set": gate._ref(inputs.evidence_adapter_contract_set),
        "knowledge_bundle": gate._ref(inputs.knowledge_bundle),
        "portal_headers_v2_capability_disposition": gate._ref(dependencies["CapabilityDisposition"]),
        "k2a_conformance_package": gate._ref(dependencies["K2AConformancePackage"]),
    })
    for name in ("knowledge_provenance_manifests", "source_governance_records",
                 "knowledge_freshness_policies"):
        manifest_payload[name] = inputs.knowledge_bundle.semantic_payload[name]
    manifest = api.foundation.make_foundation_admission_manifest(manifest_payload)
    profile_payload = fixture.foundation_a.semantic_payload
    profile_payload["evidence_schema_registry_contract"] = gate._ref(registry)
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
            "procedure_or_test_suite_id": "disposable-t03-full-run-self-test",
            "environment_identity": "disposable-self-test",
            "execution_artifact_sha256": "c" * 64},
        "trusted_time_inputs": {
            "foundation_knowledge_evaluation_at_utc": None,
            "foundation_admission_evaluation_at_utc": None,
            "knowledge_evaluation_at_utc": None},
        "decision_record_refs": []})
    documents = [registry, manifest, profile, admission, activation, validity, result,
                 inputs.evidence_adapter_contract_set, inputs.knowledge_bundle,
                 *dependencies.values(),
                 *(getattr(knowledge, field.name) for field in fields(knowledge))]
    unique_documents = {content.artifact_id: content for content in documents}
    with sqlite3.connect(database) as connection:
        for content in unique_documents.values():
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
                           result=result, registry=registry, inputs=inputs)


def _stub_semantics(monkeypatch, *, pytest_exit=0):
    matrix = {"cases": {case: {"status": "PASS", "input_fixture_sha256": "a" * 64}
                        for case in gate.CASE_IDS}, "traces": {}, "all_pass": True}
    monkeypatch.setattr(gate, "execute_pytest", lambda _repo, _run_dir: (
        pytest_exit, "disposable T-03 pytest stub\n",
        "python -m pytest -q tests/device_fingerprint_task04_t03"))
    monkeypatch.setattr(gate, "execute_matrix", lambda _api: (
        matrix, {"lineage_kind": "CONTROLLED_CANDIDATE_FIXTURES_NOT_FORMAL_ADMITTED_INPUTS",
                 "artifacts": []}))


def _run_output(output_dir):
    runs = list(output_dir.iterdir())
    assert len(runs) == 1 and runs[0].is_dir()
    return runs[0]


@pytest.mark.parametrize("outcome", ["PASS", "FAIL"])
def test_full_run_gate_pass_and_fail_paths(full_run_lab, tmp_path, monkeypatch, outcome):
    helper = gate._t01()
    _stub_semantics(monkeypatch, pytest_exit=0 if outcome == "PASS" else 1)
    db_before = hashlib.sha256(full_run_lab.database.read_bytes()).hexdigest()
    repo_before = helper.repository_filesystem_fingerprint(REPO)
    output = tmp_path / "formal-run-output"
    code = gate.run_gate(REPO, full_run_lab.database, output)
    run_dir = _run_output(output)
    assert code == (0 if outcome == "PASS" else 1)
    assert f"GATE_EXECUTION_STATUS={outcome}" in (run_dir / "t03-summary.txt").read_text()
    assert hashlib.sha256(full_run_lab.database.read_bytes()).hexdigest() == db_before
    assert helper.repository_filesystem_fingerprint(REPO) == repo_before
    proof_file = run_dir / "t03-gate-proof-artifact.json"
    result_file = run_dir / "t03-gate-result-manifest.json"
    assert result_file.is_file()
    assert proof_file.is_file() is (outcome == "PASS")
    result = json.loads(result_file.read_bytes())["semantic_payload"]
    assert result["status"] == outcome
    assert result["gate_id"] == "T-03"
    assert result["gate_contract_version"] == "R14-T-03-v1"
    assert result["candidate_repository_commit_sha"] == gate.EXPECTED_COMMIT
    assert result["candidate_repository_tree_sha"] == gate.EXPECTED_TREE
    if outcome == "PASS":
        proof_document = json.loads(proof_file.read_bytes())
        proof = proof_document["semantic_payload"]
        assert proof["proof_kind"] == "ORIGIN_ASSESSMENT_EXECUTION"
        assert proof["candidate_repository_commit_sha"] == gate.EXPECTED_COMMIT
        assert proof["candidate_repository_tree_sha"] == gate.EXPECTED_TREE
        assert result["output_artifact_refs"] == [{
            "artifact_id": proof_document["artifact_id"],
            "content_sha256": proof_document["content_sha256"]}]
    else:
        assert result["output_artifact_refs"] == []
    for ref in result["retained_evidence_refs"]:
        assert ref["file_sha256"] == gate._sha256(run_dir / ref["path_or_reference"])
    assert {"t03-execution-evidence.json", "t03-artifacts.json", "t03-pytest.log"} <= {
        file.name for file in run_dir.iterdir()}


@pytest.mark.parametrize("mutation", ["repository", "runner"])
def test_full_run_gate_blocks_execution_mutation(full_run_lab, tmp_path,
                                                 monkeypatch, mutation):
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
    assert f"GATE_EXECUTION_STATUS={expected}" in (run_dir / "t03-summary.txt").read_text()
    assert sorted(file.name for file in run_dir.iterdir()) == ["t03-summary.txt"]
    assert hashlib.sha256(full_run_lab.database.read_bytes()).hexdigest() == db_before
    assert helper.repository_filesystem_fingerprint(REPO) == repo_before
