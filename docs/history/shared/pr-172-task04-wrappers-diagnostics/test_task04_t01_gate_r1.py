"""Disposable self-tests for the external T-01 runner; never the official gate."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parent
SOURCE = Path("C:/CaptivPortal-UI-Preview")
RUNNER_FILE = HERE / "task04-t01-gate-r1.py"
SPEC = importlib.util.spec_from_file_location("task04_t01_external_runner", RUNNER_FILE)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


def ref(content):
    return {"artifact_id": content.artifact_id, "content_sha256": content.content_sha256}


def put(connection, content):
    connection.execute(
        "INSERT INTO artifacts (artifact_id, artifact_type, content_sha256, "
        "semantic_payload_json) VALUES (?,?,?,?)",
        (content.artifact_id, content.artifact_type, content.content_sha256,
         content.semantic_payload_json),
    )


def create_fake_repo(path):
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    (path / "identity.txt").write_text("disposable self-test\n", encoding="utf-8")
    (path / ".gitignore").write_text(
        "ignored.txt\n__pycache__/\n*.pyc\n.pytest_cache/\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "identity.txt", ".gitignore"], check=True)
    subprocess.run([
        "git", "-C", str(path), "-c", "user.name=T01 Test",
        "-c", "user.email=t01@example.invalid", "commit", "-q", "-m", "fixture",
    ], check=True)
    return path


@pytest.fixture
def lab(tmp_path, monkeypatch):
    assert SOURCE.is_dir()
    api = runner.load_repository_modules(SOURCE)
    from app.device_fingerprint.ff5_runtime_profile_atomicity import _Fixture

    database = tmp_path / "foundation-disposable.sqlite"
    fixture = _Fixture(database)
    registry = api.schema.build_foundation_schema_artifacts()[
        "EvidenceSchemaRegistryContract"]
    manifest_payload = fixture.leaves["FoundationAdmissionManifest"].semantic_payload
    manifest_payload["evidence_schema_registry_contract"] = ref(registry)
    manifest = api.foundation.make_foundation_admission_manifest(manifest_payload)
    profile_payload = fixture.foundation_a.semantic_payload
    profile_payload["evidence_schema_registry_contract"] = ref(registry)
    profile = api.profiles.make_foundation_runtime_profile(profile_payload)
    old_rpm = fixture.admission("foundation", fixture.foundation_a)
    rpm_payload = old_rpm.semantic_payload
    rpm_payload["candidate_profile"] = ref(profile)
    rpm_payload["foundation_admission_manifest"] = ref(manifest)
    rpm = api.profiles.make_runtime_profile_admission_manifest(rpm_payload)
    activation, validity, _ = fixture.records(rpm, 100)
    gate = api.gate_result.make_gate_result_manifest({
        "gate_id": "F-ADMIT", "gate_contract_version": "R14-F-ADMIT-v1",
        "status": "PASS", "candidate_repository_commit_sha": "a" * 40,
        "candidate_repository_tree_sha": "b" * 40,
        "input_artifact_refs": [],
        "output_artifact_refs": [ref(item) for item in
                                 (manifest, profile, rpm, activation, validity)],
        "retained_evidence_refs": [],
        "proof_execution_identity": {
            "execution_id": str(uuid.uuid4()), "executor_kind": "TECHLEAD_GATE_TOOL",
            "repository_commit_sha": "a" * 40,
            "repository_tree_sha": "b" * 40,
            "procedure_or_test_suite_id": "disposable-foundation-self-test",
            "environment_identity": "disposable-self-test",
            "execution_artifact_sha256": "c" * 64,
        },
        "trusted_time_inputs": {
            "foundation_knowledge_evaluation_at_utc": None,
            "foundation_admission_evaluation_at_utc": None,
            "knowledge_evaluation_at_utc": None,
        },
        "decision_record_refs": [],
    })
    with sqlite3.connect(database) as connection:
        for content in (registry, manifest, profile, rpm, activation, validity, gate):
            put(connection, content)
        value = activation.semantic_payload
        connection.execute(
            "INSERT INTO activations (activation_record_id, artifact_id, profile_kind, "
            "runtime_profile_id, runtime_profile_digest, activation_generation_id) "
            "VALUES (?,?,?,?,?,?)",
            (value["activation_record_id"], activation.artifact_id, "foundation",
             profile.artifact_id, profile.content_sha256,
             value["activation_generation_id"]),
        )
        connection.execute(
            "INSERT INTO active_pointers (profile_kind, runtime_profile_id, "
            "runtime_profile_digest, activation_record_id, activation_generation_id, "
            "updated_at_utc) VALUES (?,?,?,?,?,?)",
            ("foundation", profile.artifact_id, profile.content_sha256,
             value["activation_record_id"], value["activation_generation_id"],
             value["activated_at_utc"]),
        )
        validity_payload = validity.semantic_payload
        connection.execute(
            "INSERT INTO validities (validity_record_id, artifact_id, activation_record_id) "
            "VALUES (?,?,?)",
            (validity_payload["validity_record_id"], validity.artifact_id,
             value["activation_record_id"]),
        )
        connection.execute(
            "INSERT INTO validity_heads (activation_record_id, validity_record_id, "
            "updated_at_utc) VALUES (?,?,?)",
            (value["activation_record_id"], validity_payload["validity_record_id"],
             validity_payload["effective_at_utc"]),
        )
        connection.execute(
            "INSERT INTO f_admit_publications (gate_id, artifact_id, content_sha256) "
            "VALUES (?,?,?)", ("F-ADMIT", gate.artifact_id, gate.content_sha256),
        )
    repo = create_fake_repo(tmp_path / "repo-disposable")
    head = runner._git(repo, "rev-parse", "HEAD")
    tree = runner._git(repo, "show", "-s", "--format=%T", "HEAD")
    monkeypatch.setattr(runner, "EXPECTED_COMMIT", head)
    monkeypatch.setattr(runner, "EXPECTED_TREE", tree)
    monkeypatch.setattr(runner, "EXPECTED_DIGESTS", {
        "FoundationAdmissionManifest": manifest.content_sha256,
        "FoundationRuntimeProfile": profile.content_sha256,
        "RuntimeProfileAdmissionManifest": rpm.content_sha256,
        "GateResultManifest": gate.content_sha256,
        "EvidenceSchemaRegistryContract": registry.content_sha256,
    })
    monkeypatch.setattr(runner, "load_repository_modules", lambda _path: api)
    return runner.FoundationLineage(
        manifest, profile, rpm, activation, validity, gate, registry), repo, database, api


def test_import_origin_and_exact_repository_identity(tmp_path, monkeypatch):
    api = runner.load_repository_modules(SOURCE)
    assert all(Path(module.__file__).resolve().is_relative_to(SOURCE)
               for module in vars(api).values())
    repo = create_fake_repo(tmp_path / "repo")
    monkeypatch.setattr(runner, "EXPECTED_COMMIT", runner._git(repo, "rev-parse", "HEAD"))
    monkeypatch.setattr(runner, "EXPECTED_TREE", runner._git(
        repo, "show", "-s", "--format=%T", "HEAD"))
    runner.verify_repository(repo)


def test_repository_imports_do_not_write_bytecode(tmp_path):
    source = tmp_path / "disposable-import-source"
    package = source / "app" / "device_fingerprint"
    package.mkdir(parents=True)
    (source / "app" / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    for name in ("artifact_content", "foundation_admission_artifacts",
                 "runtime_profile_artifacts", "foundation_schema_artifacts",
                 "foundation_gate_artifacts", "gate_proof_artifacts", "snapshot_service",
                 "read_service", "repository", "classification_persistence", "validation"):
        (package / f"{name}.py").write_text("", encoding="utf-8")
    script = (
        "import importlib.util,sys; "
        "from pathlib import Path; "
        "spec=importlib.util.spec_from_file_location('external_t01_runner',sys.argv[1]); "
        "runner=importlib.util.module_from_spec(spec); "
        "sys.modules[spec.name]=runner; spec.loader.exec_module(runner); "
        "runner.load_repository_modules(Path(sys.argv[2])); "
        "assert sys.dont_write_bytecode"
    )
    environment = os.environ.copy()
    environment.pop("PYTHONDONTWRITEBYTECODE", None)
    environment.pop("PYTHONPYCACHEPREFIX", None)
    subprocess.run([sys.executable, "-c", script, str(RUNNER_FILE), str(source)],
                   cwd=tmp_path, env=environment, check=True)
    assert not list(source.rglob("__pycache__"))
    assert not list(source.rglob("*.pyc"))


def test_official_pytest_invocation_is_external_and_cache_free(tmp_path, monkeypatch):
    repo = tmp_path / "disposable-repo"
    repo.mkdir()
    run_dir = tmp_path / "external-run"
    run_dir.mkdir()
    captured = {}

    def fake_run(command, **kwargs):
        captured.update(command=command, kwargs=kwargs)
        return subprocess.CompletedProcess(command, 0, "self-test invocation\n")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    status, log, recorded = runner.execute_pytest(repo, run_dir)
    assert (status, log) == (0, "self-test invocation\n")
    command = captured["command"]
    assert command[:4] == [sys.executable, "-m", "pytest", "-q"]
    assert command[4:6] == ["-p", "no:cacheprovider"]
    assert command[-1] == "tests/device_fingerprint_task04_t01"
    basetemp = Path(command[command.index("--basetemp") + 1])
    assert basetemp.is_relative_to(run_dir) and not basetemp.is_relative_to(repo)
    environment = captured["kwargs"]["env"]
    assert environment["PYTHONDONTWRITEBYTECODE"] == "1"
    assert environment["PYTEST_ADDOPTS"] == ""
    assert all(Path(environment[name]).is_relative_to(run_dir)
               for name in ("TEMP", "TMP", "TMPDIR"))
    assert captured["kwargs"]["cwd"] == repo
    assert recorded == subprocess.list2cmdline(command)
    assert not list(run_dir.iterdir())


def test_foundation_exact_lineage_registry_and_read_only(lab):
    expected, _, database, api = lab
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    connection = runner.open_foundation_read_only(database)
    try:
        actual = runner.verify_foundation(connection, api)
        assert actual == expected
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("UPDATE active_pointers SET runtime_profile_digest='x'")
    finally:
        connection.rollback()
        connection.close()
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before


def test_read_only_requires_validity_tables(lab, tmp_path):
    _, _, database, _ = lab
    for table in ("validities", "validity_heads"):
        copy = tmp_path / f"missing-{table}.sqlite"
        copy.write_bytes(database.read_bytes())
        with sqlite3.connect(copy) as connection:
            connection.execute(f"DROP TABLE {table}")
        with pytest.raises(runner.Blocked, match="BLOCKED_FOUNDATION_LINEAGE"):
            runner.open_foundation_read_only(copy)


@pytest.mark.parametrize("problem", [
    "inactive", "suspended_invalidated", "missing_head", "missing_validity",
    "head_points_to_missing_validity", "wrong_relational_activation",
    "wrong_profile", "tampered_validity", "f_admit_omits_validity",
])
def test_current_validity_must_be_exact_active_f_admit_output(
        lab, tmp_path, monkeypatch, problem):
    lineage, repo, database, api = lab
    old = lineage.validity
    with sqlite3.connect(database) as connection:
        if problem in ("inactive", "suspended_invalidated", "wrong_profile"):
            payload = old.semantic_payload
            if problem == "inactive":
                payload.update(state="INACTIVE", reason_code="SUPERSEDED_SAFE",
                               inflight_commit_rule="ALLOW_PINNED_INFLIGHT")
            elif problem == "suspended_invalidated":
                payload.update(state="SUSPENDED_INVALIDATED",
                               reason_code="EXPLICIT_POLICY_SUSPEND",
                               inflight_commit_rule="REJECT_PINNED_INFLIGHT")
            else:
                payload.update(runtime_profile_id=
                               "FoundationRuntimeProfile:v1:sha256:" + "f" * 64,
                               runtime_profile_digest="f" * 64)
            replacement = api.profiles.make_runtime_profile_validity_record(payload)
            put(connection, replacement)
            connection.execute(
                "UPDATE validities SET artifact_id=? WHERE validity_record_id=?",
                (replacement.artifact_id, payload["validity_record_id"]),
            )
        elif problem == "missing_head":
            connection.execute("DELETE FROM validity_heads")
        elif problem == "missing_validity":
            connection.execute("DELETE FROM validities")
        elif problem == "head_points_to_missing_validity":
            connection.execute("UPDATE validity_heads SET validity_record_id=?",
                               (str(uuid.uuid4()),))
        elif problem == "wrong_relational_activation":
            connection.execute("UPDATE validities SET activation_record_id=?",
                               (str(uuid.uuid4()),))
        elif problem == "tampered_validity":
            connection.execute(
                "UPDATE artifacts SET semantic_payload_json=? WHERE artifact_id=?",
                (b'{}', old.artifact_id),
            )
        else:
            gate_payload = lineage.gate_result.semantic_payload
            gate_payload["output_artifact_refs"] = [
                item for item in gate_payload["output_artifact_refs"]
                if item["artifact_id"] != old.artifact_id
            ]
            replacement = api.gate_result.make_gate_result_manifest(gate_payload)
            put(connection, replacement)
            connection.execute(
                "UPDATE f_admit_publications SET artifact_id=?, content_sha256=? "
                "WHERE gate_id='F-ADMIT'",
                (replacement.artifact_id, replacement.content_sha256),
            )
            digests = dict(runner.EXPECTED_DIGESTS)
            digests["GateResultManifest"] = replacement.content_sha256
            monkeypatch.setattr(runner, "EXPECTED_DIGESTS", digests)
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    output = tmp_path / f"invalid-{problem}"
    assert runner.run_gate(repo, database, output) == 2
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    run = next(output.iterdir())
    assert {item.name for item in run.iterdir()} == {"t01-summary.txt"}
    assert "BLOCKED_FOUNDATION_LINEAGE" in (run / "t01-summary.txt").read_text(
        encoding="utf-8")


@pytest.mark.parametrize("problem", ["wrong_commit", "wrong_tree", "dirty_repo",
                                     "missing_database", "wrong_frp", "wrong_registry",
                                     "tampered_foundation_artifact", "wrong_active_profile"])
def test_blocked_preconditions(lab, tmp_path, monkeypatch, problem):
    _, repo, database, _ = lab
    if problem == "wrong_commit":
        monkeypatch.setattr(runner, "EXPECTED_COMMIT", "f" * 40)
    elif problem == "wrong_tree":
        monkeypatch.setattr(runner, "EXPECTED_TREE", "f" * 40)
    elif problem == "dirty_repo":
        (repo / "untracked.txt").write_text("dirty\n", encoding="utf-8")
    elif problem == "missing_database":
        database = tmp_path / "absent.sqlite"
    elif problem in ("wrong_frp", "wrong_registry"):
        digests = dict(runner.EXPECTED_DIGESTS)
        digests["FoundationRuntimeProfile" if problem == "wrong_frp"
                else "EvidenceSchemaRegistryContract"] = "f" * 64
        monkeypatch.setattr(runner, "EXPECTED_DIGESTS", digests)
    elif problem == "tampered_foundation_artifact":
        with sqlite3.connect(database) as connection:
            connection.execute(
                "UPDATE artifacts SET semantic_payload_json=? WHERE artifact_id=?",
                (b'{}', lab[0].manifest.artifact_id),
            )
    elif problem == "wrong_active_profile":
        with sqlite3.connect(database) as connection:
            connection.execute(
                "UPDATE active_pointers SET runtime_profile_digest=? "
                "WHERE profile_kind='foundation'", ("f" * 64,),
            )
    output = tmp_path / "blocked-output"
    before_db = hashlib.sha256(database.read_bytes()).hexdigest() if database.exists() else None
    assert runner.run_gate(repo, database, output) == 2
    if before_db is not None:
        assert hashlib.sha256(database.read_bytes()).hexdigest() == before_db
    files = set(next(output.iterdir()).iterdir())
    assert {item.name for item in files} == {"t01-summary.txt"}
    assert "BLOCKED_" in next(iter(files)).read_text(encoding="utf-8")


def test_output_inside_repository_is_rejected_without_mutation(lab):
    _, repo, database, _ = lab
    output = repo / "must-not-create"
    assert runner.run_gate(repo, database, output) == 2
    assert not output.exists()
    assert runner._git(repo, "status", "--porcelain") == ""


def test_runner_change_blocks_and_leaves_no_formal_artifacts(lab, tmp_path, monkeypatch):
    _, repo, database, _ = lab
    monkeypatch.setattr(runner, "execute_pytest", lambda _repo, _run_dir:
                        (0, "self-test stub PASS\n", "controlled self-test stub"))
    monkeypatch.setattr(runner, "execute_matrix", lambda *_args: matrix_stub())
    original_hash = runner._sha256
    calls = 0

    def changing_hash(path):
        nonlocal calls
        if path == RUNNER_FILE:
            calls += 1
            if calls > 1:
                return "0" * 64
        return original_hash(path)

    monkeypatch.setattr(runner, "_sha256", changing_hash)
    output = tmp_path / "changed-runner-output"
    assert runner.run_gate(repo, database, output) == 2
    run = next(output.iterdir())
    assert {file.name for file in run.iterdir()} == {"t01-summary.txt"}
    assert "BLOCKED_RUNNER_CHANGED" in (run / "t01-summary.txt").read_text(encoding="utf-8")


def test_injected_ignored_repository_mutation_blocks_formal_output(
        lab, tmp_path, monkeypatch):
    _, repo, database, _ = lab
    ignored = repo / "ignored.txt"
    ignored.write_bytes(b"before formal execution")
    before_db = hashlib.sha256(database.read_bytes()).hexdigest()

    def mutate_during_pytest(_repo, _run_dir):
        ignored.write_bytes(b"changed during formal execution")
        return 0, "self-test stub PASS\n", "controlled self-test stub"

    monkeypatch.setattr(runner, "execute_pytest", mutate_during_pytest)
    monkeypatch.setattr(runner, "execute_matrix", lambda *_args: matrix_stub())
    output = tmp_path / "mutated-output"
    assert runner.run_gate(repo, database, output) == 2
    run = next(output.iterdir())
    assert {item.name for item in run.iterdir()} == {"t01-summary.txt"}
    assert "BLOCKED_REPOSITORY_MUTATED" in (run / "t01-summary.txt").read_text(
        encoding="utf-8")
    assert runner._git(repo, "status", "--porcelain") == ""
    assert ignored.read_bytes() == b"changed during formal execution"
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before_db


def matrix_stub(passed=True):
    return {"cases": {f"T01-M{number:02}": {"status": "PASS" if passed else "FAIL"}
                      for number in range(1, 12)},
            "transaction_watermark_trace": {"read_sessions": 1}, "all_pass": passed}


@pytest.mark.parametrize("passed", [True, False])
def test_formal_output_split_hashes_roundtrip_and_no_mutation(
        lab, tmp_path, monkeypatch, passed):
    lineage, repo, database, api = lab
    monkeypatch.setattr(runner, "execute_pytest", lambda _repo, _run_dir:
                        (0, "self-test stub PASS\n", "controlled self-test stub"))
    monkeypatch.setattr(runner, "execute_matrix", lambda *_args: matrix_stub(passed))
    ignored = repo / "ignored.txt"
    ignored.write_bytes(b"pre-existing ignored self-test bytes")
    pyc = repo / "__pycache__" / "pre-existing.pyc"
    pyc.parent.mkdir()
    pyc.write_bytes(b"pre-existing ignored pyc-like bytes")
    pytest_cache = repo / ".pytest_cache" / "CACHEDIR.TAG"
    pytest_cache.parent.mkdir()
    pytest_cache.write_bytes(b"pre-existing ignored pytest cache bytes")
    before_filesystem = runner.repository_filesystem_fingerprint(repo)
    assert "ignored.txt" in before_filesystem
    assert "__pycache__/pre-existing.pyc" in before_filesystem
    assert ".pytest_cache/CACHEDIR.TAG" in before_filesystem
    assert not any(path.startswith(".git/") for path in before_filesystem)
    before_ignored = ignored.read_bytes(), pyc.read_bytes(), pytest_cache.read_bytes()
    before_db = hashlib.sha256(database.read_bytes()).hexdigest()
    before_status = runner._git(repo, "status", "--porcelain")
    before_head = runner._git(repo, "rev-parse", "HEAD")
    output = tmp_path / "formal-output"
    assert runner.run_gate(repo, database, output) == (0 if passed else 1)
    run = next(output.iterdir())
    result_file = run / "t01-gate-result-manifest.json"
    result = json.loads(result_file.read_bytes())
    assert result_file.read_bytes() == api.artifact.canonical_artifact_json(result)
    assert api.gate_result.make_gate_result_manifest(result["semantic_payload"]).artifact_id == result[
        "artifact_id"]
    assert result["semantic_payload"]["status"] == ("PASS" if passed else "FAIL")
    assert result["semantic_payload"]["input_artifact_refs"] == sorted(
        [ref(lineage.profile), ref(lineage.registry)], key=lambda item: item["artifact_id"])
    assert result["semantic_payload"]["decision_record_refs"] == []
    for item in result["semantic_payload"]["retained_evidence_refs"]:
        file = run / item["path_or_reference"]
        assert hashlib.sha256(file.read_bytes()).hexdigest() == item["file_sha256"]
    assert result["semantic_payload"]["proof_execution_identity"][
        "execution_artifact_sha256"] == hashlib.sha256(RUNNER_FILE.read_bytes()).hexdigest()
    proof_file = run / "t01-gate-proof-artifact.json"
    if passed:
        proof = json.loads(proof_file.read_bytes())
        assert proof_file.read_bytes() == api.artifact.canonical_artifact_json(proof)
        assert api.gate_proof.make_gate_proof_artifact(proof["semantic_payload"]).artifact_id == proof[
            "artifact_id"]
        assert proof["semantic_payload"]["proof_kind"] == "SNAPSHOT_MATERIALIZATION_EXECUTION"
        assert result["semantic_payload"]["output_artifact_refs"] == [{
            "artifact_id": proof["artifact_id"], "content_sha256": proof["content_sha256"]}]
    else:
        assert not proof_file.exists()
        assert result["semantic_payload"]["output_artifact_refs"] == []
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before_db
    assert runner.repository_filesystem_fingerprint(repo) == before_filesystem
    assert (ignored.read_bytes(), pyc.read_bytes(), pytest_cache.read_bytes()) == before_ignored
    assert runner._git(repo, "status", "--porcelain") == before_status == ""
    assert runner._git(repo, "rev-parse", "HEAD") == before_head


def test_disposable_direct_matrix_uses_real_snapshot_and_read(tmp_path):
    api = runner.load_repository_modules(SOURCE)
    from tests.device_fingerprint_task04_t01.test_snapshot_service import context

    candidate = context()
    matrix = runner.execute_matrix(tmp_path, api, candidate.profile,
                                   lambda artifact_ref: candidate.contents[artifact_ref.artifact_id])
    assert set(matrix["cases"]) == {f"T01-M{number:02}" for number in range(1, 12)}
    assert matrix["all_pass"], matrix
    assert matrix["transaction_watermark_trace"]["read_sessions"] == 1
    assert not list(tmp_path.glob("t01-matrix-*"))
