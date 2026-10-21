"""Disposable T-05 runner self-test. It never executes the official accepted DB."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import pickle
import shutil
import sqlite3
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "task04-t05-gate-r1.py"
REPO = Path(r"C:\CaptivPortal-UI-Preview")
ACCEPTED_FOUNDATION = Path(r"C:\CaptivPortal-Lab\foundation-control-plane\device-fingerprint-control-plane.sqlite3")
ACCEPTED_T06A = Path(r"C:\CaptivPortal-Lab\gates\task04\t06a\official-run-20260929-T06A-01\fefddd39-876d-41dc-8a79-821257b59c54")
spec = importlib.util.spec_from_file_location("task04_t05_disposable_test_target", RUNNER)
assert spec and spec.loader
gate = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gate
spec.loader.exec_module(gate)


@pytest.fixture(scope="module")
def basis(tmp_path_factory):
    """A transactionally copied DB and copied prerequisite files, never originals."""
    root = tmp_path_factory.mktemp("disposable-t05-basis")
    db = root / "control.sqlite3"
    source = sqlite3.connect(f"{ACCEPTED_FOUNDATION.resolve().as_uri()}?mode=ro", uri=True)
    try:
        with sqlite3.connect(db) as destination:
            source.backup(destination)
    finally:
        source.close()
    t06a = root / "t06a-copy"
    t06a.mkdir()
    for name in gate.T06A_FILES:
        shutil.copyfile(ACCEPTED_T06A / name, t06a / name)
    return root, db, t06a


def one_run(output):
    children = list(output.iterdir())
    assert len(children) == 1
    return children[0]


def test_exact_candidate_and_prerequisite_roundtrip(basis):
    _, db, t06a = basis
    helper, t06a_runner = gate.helpers()
    helper.verify_repository(REPO)
    api = gate.api_for(REPO, t06a_runner)
    p, proof, result = gate.verify_t06a(t06a, api)
    assert p.artifact_id == gate.PROFILE_ID
    assert proof.artifact_id == gate.T06A_PROOF_ID
    assert result.artifact_id == gate.T06A_RESULT_ID
    assert result.semantic_payload["status"] == "PASS"
    with helper.open_foundation_read_only(db) as connection:
        foundation = helper.verify_foundation(connection, api)
    assert p.semantic_payload["foundation_runtime_profile"] == gate.ref(foundation.profile)


def test_wrong_and_missing_t06a_are_blocked(basis, tmp_path):
    _, db, original = basis
    t06a = tmp_path / "wrong"
    shutil.copytree(original, t06a)
    (t06a / gate.T06A_FILES[0]).write_bytes(b"{}")
    out = tmp_path / "out"
    assert gate.run_gate(REPO, db, t06a, out) == 2
    run = one_run(out)
    assert not (run / "t05-gate-result-manifest.json").exists()
    assert not (run / "t05-gate-proof-artifact.json").exists()
    (t06a / gate.T06A_FILES[0]).unlink()
    assert gate.run_gate(REPO, db, t06a, tmp_path / "missing-out") == 2


def test_profile_substitution_rejected(basis, tmp_path):
    _, _, original = basis
    helper, t06a_runner = gate.helpers()
    api = gate.api_for(REPO, t06a_runner)
    t06a = tmp_path / "substitute"
    shutil.copytree(original, t06a)
    value = json.loads((t06a / gate.T06A_FILES[0]).read_text())
    value["artifact_id"] = "ClassificationRuntimeProfile:v1:sha256:" + "0" * 64
    gate.write_json(t06a / gate.T06A_FILES[0], value)
    with pytest.raises(gate.Blocked, match="BLOCKED_T06A_PREREQUISITE"):
        gate.verify_t06a(t06a, api)


def test_pure_core_guard_on_disposable_semantic_fixture(tmp_path, monkeypatch):
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    tests = gate.candidate(REPO, "tests.device_fingerprint_task04_04d_request.test_request_assembly")
    fusion = gate.candidate(REPO, "app.device_fingerprint.fusion")
    assembly_module = gate.candidate(REPO, "app.device_fingerprint.request_assembly")
    _, _, service, profile = tests.prepared()
    captured = []
    original = assembly_module.fuse_classification
    def recording(inputs):
        captured.append(inputs)
        return original(inputs)
    monkeypatch.setattr(assembly_module, "fuse_classification", recording)
    result = tests.candidate_run(service, profile)
    assert captured and isinstance(captured[0], fusion.FusionInputs)
    proof = gate._guarded_core(REPO, tmp_path, captured[0], result.classification_result)
    assert proof["attempt_count"] == 0
    probe_input = tmp_path / "probe-input.pkl"
    probe_input.write_bytes(pickle.dumps(captured[0], protocol=4))
    for variant, expected in (("probe-sqlite", "sqlite3.connect"),
                              ("probe-network", "socket.__new__"),
                              ("probe-filesystem", "open")):
        environment = dict(os.environ)
        environment["PYTHONPYCACHEPREFIX"] = str(tmp_path / "pycache")
        child = subprocess.run([sys.executable, str(RUNNER), "--pure-core-child",
                                str(REPO), str(probe_input), variant],
                               cwd=tmp_path, env=environment, capture_output=True, text=True)
        payload = json.loads(child.stdout.strip().splitlines()[-1])
        assert child.returncode == 1
        assert expected in payload["attempted_blocked_events"]


def test_exact_freshness_policies_have_representable_boundaries(basis):
    _, db, t06a = basis
    helper, t06a_runner = gate.helpers()
    api = gate.api_for(REPO, t06a_runner)
    profile, _, _ = gate.verify_t06a(t06a, api)
    with helper.open_foundation_read_only(db) as connection:
        store = gate.ReadOnlyArtifacts(connection, api, helper)
        _, knowledge, *_ = gate._time_for(api, profile, store, helper)
        report = gate._freshness(api, knowledge)
    assert report["k1"]["expired_representable"]
    assert report["k4"]["expired_representable"]
    assert not report["k2b"]["expired_representable"]
    assert {row["expected"] for row in report["k1"]["cases"]} == {
        "fresh", "stale", "expired"}


def test_expired_source_trace_on_exact_p_disposable(basis):
    _, db, t06a = basis
    helper, t06a_runner = gate.helpers()
    api = gate.api_for(REPO, t06a_runner)
    profile, _, _ = gate.verify_t06a(t06a, api)
    with helper.open_foundation_read_only(db) as connection:
        store = gate.ReadOnlyArtifacts(connection, api, helper)
        classifier = gate.canonical_content(gate.T06_MANIFEST_PATH, api,
            lambda payload: api.artifact.make_artifact_content("ClassifierArtifactManifest", payload),
            profile.semantic_payload["classifier_artifact_manifest"]["artifact_id"])
        store.extra[classifier.artifact_id] = classifier
        _, knowledge, epoch, start, end, observed, _ = gate._time_for(api, profile, store, helper)
        expired = api.validation.format_utc(api.validation.parse_utc(
            knowledge.k1_provenance.semantic_payload["retrieved_at_utc"]) +
            gate.timedelta(milliseconds=knowledge.k1_freshness_policy.semantic_payload[
                "stale_max_age_ms"] + 1))
        ingested = api.validation.format_utc(api.validation.parse_utc(end) + gate.timedelta(minutes=1))
        row, record_id = gate._matching_k1_row(api, helper, epoch, observed, ingested, knowledge)
        service = gate._assembly(api, store, api.snapshot_fixture.FakeRead([row]), expired)
        result = service.assemble_pre_acceptance_candidate(profile, epoch["site_id"],
            helper.MAC, start, end)
        dhcp = next(item.semantic_payload for item in result.origin_assessments
                    if item.semantic_payload["origin_group"] == "dhcp")
        platform = next(item for item in dhcp["dimension_assessments"]
                        if item["dimension_name"] == "platform_family")
        assert record_id.startswith("k1-dhcp-satori:")
        assert platform["internal_state"] == "no_claim"
        assert "knowledge_source_expired" in platform["explanation_codes"]


def test_load_before_classification_pin_is_semantic_failure(monkeypatch):
    """A single eventual pin cannot excuse an earlier immutable store read."""
    artifact = SimpleNamespace(artifact_id="Fixture:v1:sha256:" + "a" * 64,
                               content_sha256="a" * 64)
    profile = SimpleNamespace(artifact_id="FixtureProfile:v1:sha256:" + "b" * 64,
                              content_sha256="b" * 64,
                              semantic_payload={"foundation_runtime_profile": gate.ref(artifact)})
    base = SimpleNamespace(connection=None, api=None, helper=None, extra={artifact.artifact_id: artifact})
    store = gate.SwitchStore(base, profile, profile, "2026-09-29T00:00:00.000Z")
    monkeypatch.setattr(gate, "_pin", lambda _api, item, _time: item)
    store.begin_request("A")
    assert store.load_artifact(artifact.artifact_id, artifact.content_sha256) is artifact
    store.pin_active_profile("classification")
    store.end_request()
    store.begin_request("B")
    store.pin_active_profile("classification")
    store.end_request()
    assert [row["operation"] for row in store.operation_trace if row["request_label"] == "A"
            and row["operation"] == "PIN_ACTIVE_PROFILE"] == ["PIN_ACTIVE_PROFILE"]
    with pytest.raises(gate.SemanticFailure) as failure:
        gate._assert_pin_first(store.operation_trace)
    assert failure.value.code == "CLASSIFICATION_NOT_PINNED_FIRST"


def test_full_pass_path_and_evidence(basis, tmp_path):
    _, db, t06a = basis
    before_db = gate.sha(db)
    helper, _ = gate.helpers()
    before_repo = helper.repository_filesystem_fingerprint(REPO)
    out = tmp_path / "pass"
    status = gate.run_gate(REPO, db, t06a, out)
    run = one_run(out)
    assert status == 0, (run / "t05-summary.txt").read_text()
    matrix = json.loads((run / "t05-direct-matrix.json").read_text())
    assert set(matrix["cases"]) == set(gate.CASES)
    assert matrix["all_pass"]
    proof = json.loads((run / "t05-gate-proof-artifact.json").read_text())
    result = json.loads((run / "t05-gate-result-manifest.json").read_text())
    assert proof["semantic_payload"]["proof_kind"] == gate.PROOF_KIND
    assert result["semantic_payload"]["status"] == "PASS"
    assert result["semantic_payload"]["output_artifact_refs"] == [{
        "artifact_id": proof["artifact_id"], "content_sha256": proof["content_sha256"]}]
    assert gate.sha(db) == before_db
    assert helper.repository_filesystem_fingerprint(REPO) == before_repo
    pointer = json.loads((run / "t05-pointer-switch-trace.json").read_text())
    m03 = matrix["cases"]["T05-M03"]["trace"]
    assert m03["pin_first_per_request"] == {"A": True, "B": True}
    assert m03["first_store_operation"] == {
        "A": "PIN_ACTIVE_PROFILE:classification", "B": "PIN_ACTIVE_PROFILE:classification"}
    assert m03["classification_pin_count_per_request"] == {"A": 1, "B": 1}
    assert m03["foundation_pointer_read_count"] == 0
    assert pointer["pin_first_per_request"] == {"A": True, "B": True}
    assert pointer["first_store_operation"] == m03["first_store_operation"]
    assert pointer["classification_pin_count_per_request"] == {"A": 1, "B": 1}
    assert not pointer["mixed_generation_detected"]
    assert pointer["foundation_pointer_read_count"] == 0
    operations = pointer["operation_trace"]
    assert [row["sequence"] for row in operations] == list(range(1, len(operations) + 1))
    assert all(row["thread_ident"] is not None and row["thread_name"] for row in operations)
    for label in ("A", "B"):
        rows = [row for row in operations if row["request_label"] == label]
        assert rows[0]["operation"] == "REQUEST_START"
        request_end = next(index for index, row in enumerate(rows)
                           if row["operation"] == "REQUEST_END")
        store_ops = [row for row in rows[1:request_end]
                     if row["operation"] in {"PIN_ACTIVE_PROFILE", "LOAD_ARTIFACT"}]
        assert store_ops[0]["operation"] == "PIN_ACTIVE_PROFILE"
        assert store_ops[0]["arguments"]["kind"] == "classification"
        assert any(row["operation"] == "LOAD_ARTIFACT" and row["arguments"]["source"] ==
                   "pinned_classification_runtime_profile.foundation_runtime_profile"
                   for row in store_ops)
        assert all(row["request_label"] == label for row in store_ops)
    position = lambda operation: next(row["sequence"] for row in operations
                                      if row["operation"] == operation)
    assert (position("REQUEST_A_CLASSIFICATION_PINNED") <
            position("REQUEST_A_BARRIER_REACHED") <
            position("POINTER_SWITCH") < position("REQUEST_A_RESOLVED") <
            position("REQUEST_B_RESOLVED"))
    io_proof = json.loads((run / "t05-pure-core-io-proof.json").read_text())
    assert io_proof["attempt_count"] == 0
    assert len(io_proof["runs"]) == 4


def test_full_semantic_fail_path(basis, tmp_path, monkeypatch):
    _, db, t06a = basis
    before_db = gate.sha(db)
    helper, _ = gate.helpers()
    before_repo = helper.repository_filesystem_fingerprint(REPO)
    def focused_pytest(_repo, run):
        (run / "t05-pytest.log").write_text("controlled suite success\n")
        return 0, ["controlled", "pytest"]
    monkeypatch.setattr(gate, "_run_pytest", focused_pytest)
    monkeypatch.setattr(gate, "_direct_matrix", lambda *_: (_ for _ in ()).throw(
        gate.SemanticFailure("CONTROLLED_SEMANTIC_FAILURE")))
    out = tmp_path / "fail"
    assert gate.run_gate(REPO, db, t06a, out) == 1
    run = one_run(out)
    result = json.loads((run / "t05-gate-result-manifest.json").read_text())
    assert result["semantic_payload"]["status"] == "FAIL"
    assert result["semantic_payload"]["output_artifact_refs"] == []
    assert not (run / "t05-gate-proof-artifact.json").exists()
    assert gate.sha(db) == before_db
    assert helper.repository_filesystem_fingerprint(REPO) == before_repo


def test_runner_and_repository_mutation_block(basis, tmp_path, monkeypatch):
    _, db, t06a = basis
    def focused_pytest(_repo, run):
        (run / "t05-pytest.log").write_text("controlled suite success\n")
        return 0, ["controlled", "pytest"]
    monkeypatch.setattr(gate, "_run_pytest", focused_pytest)
    monkeypatch.setattr(gate, "_direct_matrix", lambda *_: (
        {key: {"status": "PASS", "trace": {}} for key in gate.CASES}, {}, {}, {}, []))
    original = gate.sha
    calls = [0]
    def changed_runner(path):
        if Path(path) == RUNNER:
            calls[0] += 1
            if calls[0] > 1:
                return "0" * 64
        return original(path)
    monkeypatch.setattr(gate, "sha", changed_runner)
    # Runner identity is rechecked before any formal result is retained.
    out = tmp_path / "runner-mutated"
    assert gate.run_gate(REPO, db, t06a, out) == 2
    run = one_run(out)
    assert not (run / "t05-gate-result-manifest.json").exists()
    monkeypatch.setattr(gate, "sha", original)
    helper, _ = gate.helpers()
    original_check = helper._require_repository_unchanged
    def changed_repo(*_args):
        raise helper.Blocked("BLOCKED_REPOSITORY_MUTATED")
    monkeypatch.setattr(helper, "_require_repository_unchanged", changed_repo)
    out = tmp_path / "repo-mutated"
    assert gate.run_gate(REPO, db, t06a, out) == 2
    assert not (one_run(out) / "t05-gate-result-manifest.json").exists()
    monkeypatch.setattr(helper, "_require_repository_unchanged", original_check)
