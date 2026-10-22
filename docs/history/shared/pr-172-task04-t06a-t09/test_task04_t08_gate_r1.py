"""External T-08 harness self-tests; never execute the official gate."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import socket
import sys
import tempfile

import pytest

RUNNER = Path(__file__).with_name("task04-t08-gate-r1.py")


def load_runner():
    spec = importlib.util.spec_from_file_location("t08_selftest_runner", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_import_has_no_output_or_gate_execution(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    before = tuple(tmp_path.iterdir())
    runner = load_runner()
    assert tuple(tmp_path.iterdir()) == before
    assert runner.GATE_ID == "T-08"
    assert runner.CONTRACT == "R14-T-08-v1"
    assert runner.PROOF_KIND == "OFFLINE_FAILURE_ISOLATION"
    assert runner.CASES == tuple(f"T08-M{i:02}" for i in range(1, 10))


def test_network_guard_denies_and_records_connection_attempt():
    runner = load_runner()
    original_connect = socket.socket.connect
    with runner.NetworkGuard() as guard:
        with socket.socket() as client:
            with pytest.raises(OSError, match="external network denied"):
                client.connect(("example.invalid", 443))
        with pytest.raises(OSError, match="external network denied"):
            socket.getaddrinfo("example.invalid", 443)
        with socket.socket(type=socket.SOCK_DGRAM) as datagram:
            with pytest.raises(OSError, match="external network denied"):
                datagram.sendto(b"blocked", ("127.0.0.1", 53))
        assert guard.report()["network_attempt_count"] == 3
    assert socket.socket.connect is original_connect


def test_output_path_preflight_rejects_repository_and_runner_tree(tmp_path):
    runner = load_runner()
    repo = tmp_path / "repo"
    repo.mkdir()
    foundation = tmp_path / "foundation.sqlite3"
    task01 = tmp_path / "task01.sqlite3"
    foundation.write_bytes(b"foundation")
    task01.write_bytes(b"task01")
    with pytest.raises(runner.Blocked) as err:
        runner.output_preflight(repo, foundation, task01, repo / "output")
    assert err.value.code == "BLOCKED_OUTPUT_PATH"
    with pytest.raises(runner.Blocked) as err:
        runner.output_preflight(repo, foundation, task01, RUNNER.parent / "official")
    assert err.value.code == "BLOCKED_OUTPUT_PATH"


def test_output_path_preflight_requires_empty_external_directory():
    runner = load_runner()
    with tempfile.TemporaryDirectory(prefix="t08-selftest-") as root:
        temp = Path(root)
        repo = temp / "repo"
        repo.mkdir()
        foundation = temp / "foundation.sqlite3"
        task01 = temp / "task01.sqlite3"
        foundation.write_bytes(b"foundation")
        task01.write_bytes(b"task01")
        output = temp / "official"
        output.mkdir()
        runner.output_preflight(repo, foundation, task01, output)
        (output / "existing").write_text("occupied")
        with pytest.raises(runner.Blocked) as err:
            runner.output_preflight(repo, foundation, task01, output)
        assert err.value.code == "BLOCKED_OUTPUT_PATH"


def test_formal_lineage_excludes_t07():
    runner = load_runner()
    source = RUNNER.read_text(encoding="utf-8")
    assert "inputs = sorted((ref(profile), ref(t06a_result))" in source
    assert "T07_RESULT_ID" not in source
    assert runner.PROCEDURE == "T-08-offline-failure-isolation-no-cloud-v1"


def test_candidate_static_isolation_has_no_auth_or_cloud_client_path():
    runner = load_runner()
    report = runner.static_isolation(Path(r"C:\CaptivPortal-UI-Preview"))
    assert report["auth_capport_classification_dependency"] == []
    assert report["fingerbank_runtime_identifier_files"] == []


def test_disabled_tcp_component_preserves_other_origin_construction():
    repo = Path(r"C:\CaptivPortal-UI-Preview")
    sys.path.insert(0, str(repo))
    from tests.device_fingerprint_task04_t03.test_origin_assessment import _inputs
    from app.device_fingerprint.origin_assessment import DeviceFingerprintOriginAssessmentBuilder
    inputs = _inputs(origin="tcp", tcp_disabled=True)
    origins = DeviceFingerprintOriginAssessmentBuilder(inputs).build_all()
    assert len(origins) == 6
    assert all(item.artifact_type == "OriginAssessment" for item in origins)
    tcp = next(item for item in origins if item.semantic_payload["origin_group"] == "tcp")
    assert "origin_runtime_disabled" in tcp.semantic_payload["explanation_codes"]


def test_disposable_exact_p_matrix_without_formal_gate_or_source_mutation():
    runner = load_runner()
    repo = Path(r"C:\CaptivPortal-UI-Preview")
    foundation = Path(r"C:\CaptivPortal-Lab\foundation-control-plane\device-fingerprint-control-plane.sqlite3")
    task01 = Path(r"C:\CaptivPortal-Lab\gates\task04\t07\inputs\task01-source-r2.sqlite3")
    if not all(path.is_file() for path in (foundation, task01)):
        pytest.skip("Accepted read-only input unavailable on this host")
    h = runner.helper()
    t01, t06a = h.helpers()
    t01.verify_repository(repo)
    before = (runner.sha(foundation), runner.sha(task01))
    sys.path.insert(0, str(repo))
    api = h.api_for(repo, t06a)
    api.snapshot_service = h.candidate(repo, "app.device_fingerprint.snapshot_service")
    api.origin_assessment = h.candidate(repo, "app.device_fingerprint.origin_assessment")
    profile, _proof, _result = h.verify_t06a(runner.T06A_RUN, api)
    with t01.open_foundation_read_only(foundation) as connection:
        lineage = t01.verify_foundation(connection, api)
        retention = h.resolve_retention(connection, api, t01, lineage)
    classifier = h.canonical_content(h.T06_MANIFEST_PATH, api,
        lambda payload: api.artifact.make_artifact_content("ClassifierArtifactManifest", payload),
        profile.semantic_payload["classifier_artifact_manifest"]["artifact_id"])
    with tempfile.TemporaryDirectory(prefix="t08-disposable-") as root:
        run_dir = Path(root)
        foundation_copy = run_dir / "foundation.sqlite3"
        task01_copy = run_dir / "task01.sqlite3"
        h.copy_sqlite_readonly(foundation, foundation_copy)
        h.copy_sqlite_readonly(task01, task01_copy)
        guard = runner.NetworkGuard()
        result = {case: {"status": "NOT_RUN"} for case in runner.CASES}
        runner.matrix(run_dir, api, h, foundation_copy, task01_copy,
                      profile, lineage.admission, retention, classifier, guard, result)
        assert all(result[case]["status"] == "PASS" for case in runner.CASES[:-1])
        assert guard.report()["network_attempt_count"] == 0
    assert (runner.sha(foundation), runner.sha(task01)) == before
