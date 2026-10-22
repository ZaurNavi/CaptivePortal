"""Disposable T-06A state-machine tests; never execute the official gate."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import shutil
import sqlite3
import sys
from dataclasses import fields
from pathlib import Path

import pytest


sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "task04-t06a-gate-r1.py"
REPO = Path(r"C:\CaptivPortal-UI-Preview")
OFFICIAL_T06 = Path(r"C:\CaptivPortal-Lab\gates\task04\t06\official-run-20260928-T06-01\cd91039c-a105-4cb0-8957-1ca4a22dda0d")
T04_SELFTEST = HERE.parents[0] / "t04" / "test_task04_t04_gate_r1.py"
T04_SHA256 = "168151ad52fcf2aa328ffd79ff9556d251bc1b2790b4c3a4b83c07b061ac7546"
spec = importlib.util.spec_from_file_location("task04_t06a_test_target", RUNNER)
assert spec and spec.loader
gate = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gate
spec.loader.exec_module(gate)


def _t04_fixture():
    assert gate.sha256(T04_SELFTEST) == T04_SHA256
    source = importlib.util.spec_from_file_location("task04_t06a_disposable_t04", T04_SELFTEST)
    assert source and source.loader
    module = importlib.util.module_from_spec(source)
    sys.modules[source.name] = module
    source.loader.exec_module(module)
    return module


def _run_dir(output: Path) -> Path:
    children = list(output.iterdir())
    assert len(children) == 1
    return children[0]


@pytest.fixture
def lab(tmp_path, monkeypatch):
    """Build an external disposable Foundation with real candidate builders."""
    prepared = _t04_fixture().full_run_lab.__wrapped__(tmp_path, monkeypatch)
    helper = gate.t01()
    # T-04's older disposable profile carried a null TTL reference while its
    # disposable OriginRuntimeAdmission was ENABLED. Align that synthetic
    # profile/activation lineage with the already closed Origin/TTL contract.
    ttl = prepared.extras["OriginRuntimeAdmission"].semantic_payload["ttl_capture_placement_proof"]
    profile_payload = prepared.profile.semantic_payload
    profile_payload["ttl_capture_placement_proof"] = ttl
    profile = prepared.api.profiles.make_foundation_runtime_profile(profile_payload)
    admission_payload = prepared.admission.semantic_payload
    admission_payload["candidate_profile"] = gate.ref(profile)
    admission = prepared.api.profiles.make_runtime_profile_admission_manifest(admission_payload)
    activation_payload = prepared.activation.semantic_payload
    activation_payload.update(runtime_profile_id=profile.artifact_id,
                              runtime_profile_digest=profile.content_sha256,
                              runtime_profile_admission_manifest_id=admission.artifact_id,
                              runtime_profile_admission_manifest_digest=admission.content_sha256)
    activation = prepared.api.profiles.make_runtime_profile_activation_record(activation_payload)
    validity_payload = prepared.validity.semantic_payload
    validity_payload.update(runtime_profile_id=profile.artifact_id,
                            runtime_profile_digest=profile.content_sha256)
    validity = prepared.api.profiles.make_runtime_profile_validity_record(validity_payload)
    result_payload = prepared.result.semantic_payload
    result_payload["output_artifact_refs"] = [gate.ref(value) for value in (
        prepared.manifest, profile, admission, activation, validity)]
    result = prepared.api.gate_result.make_gate_result_manifest(result_payload)
    with sqlite3.connect(prepared.database) as connection:
        for content in (profile, admission, activation, validity, result):
            connection.execute("INSERT OR REPLACE INTO artifacts (artifact_id, artifact_type, "
                               "content_sha256, semantic_payload_json) VALUES (?,?,?,?)",
                               (content.artifact_id, content.artifact_type,
                                content.content_sha256, content.semantic_payload_json))
        connection.execute("UPDATE active_pointers SET runtime_profile_id=?, runtime_profile_digest=? "
                           "WHERE profile_kind='foundation'", (profile.artifact_id, profile.content_sha256))
        connection.execute("UPDATE activations SET artifact_id=?, runtime_profile_id=?, "
                           "runtime_profile_digest=? WHERE activation_record_id=?",
                           (activation.artifact_id, profile.artifact_id, profile.content_sha256,
                            activation.semantic_payload["activation_record_id"]))
        connection.execute("UPDATE validities SET artifact_id=? WHERE validity_record_id=?",
                           (validity.artifact_id, validity.semantic_payload["validity_record_id"]))
        connection.execute("UPDATE f_admit_publications SET artifact_id=?, content_sha256=? "
                           "WHERE gate_id='F-ADMIT'", (result.artifact_id, result.content_sha256))
    prepared.profile, prepared.admission = profile, admission
    prepared.activation, prepared.validity, prepared.result = activation, validity, result
    monkeypatch.setattr(helper, "EXPECTED_DIGESTS", {
        "FoundationAdmissionManifest": prepared.manifest.content_sha256,
        "FoundationRuntimeProfile": prepared.profile.content_sha256,
        "RuntimeProfileAdmissionManifest": prepared.admission.content_sha256,
        "GateResultManifest": prepared.result.content_sha256,
        "EvidenceSchemaRegistryContract": prepared.registry.content_sha256,
    })
    monkeypatch.setattr(gate, "EXACT_IDS", {
        "foundation_runtime_profile": prepared.profile.artifact_id,
        "knowledge_bundle": prepared.source.knowledge_bundle.artifact_id,
        "classification_policy": prepared.baseline.classification_policy.artifact_id,
        "evidence_adapter_contract_set": prepared.source.evidence_adapter_contract_set.artifact_id,
    })
    api = gate.load_api(REPO)
    # The older T-04 fixture persists only its direct run inputs. Add every
    # transitive real/synthetic disposable dependency for the T-06A graph test.
    ff5 = gate.candidate_module(REPO, "app.device_fingerprint.ff5_runtime_profile_atomicity")
    side = ff5._Fixture(tmp_path / "disposable-leaves.sqlite")
    t01_fixture = gate.candidate_module(REPO, "tests.device_fingerprint_task04_t01.test_snapshot_service")
    context = t01_fixture.context()
    contents = [*side.leaves.values(), *context.contents.values()]
    contents.extend(getattr(prepared.source.knowledge, field.name)
                    for field in fields(prepared.source.knowledge))
    with sqlite3.connect(prepared.database) as connection:
        for content in {item.artifact_id: item for item in contents}.values():
            connection.execute("INSERT OR IGNORE INTO artifacts (artifact_id, artifact_type, "
                               "content_sha256, semantic_payload_json) VALUES (?,?,?,?)",
                               (content.artifact_id, content.artifact_type,
                                content.content_sha256, content.semantic_payload_json))
    run_input = tmp_path / "t06-input-copy"
    run_input.mkdir()
    for name in ("t06-manifest.json", "t06-gate-result-manifest.json",
                 "t06-build-identity.json", "t06-implementation-inventory.json",
                 "t06-implementation-identity-registration.json"):
        shutil.copyfile(OFFICIAL_T06 / name, run_input / name)
    return prepared, api, run_input


def _run(lab, tmp_path: Path, suffix: str) -> tuple[int, Path]:
    prepared, _, t06_input = lab
    output = tmp_path / suffix
    result = gate.run_gate(REPO, prepared.database, t06_input, output)
    return result, _run_dir(output)


def test_candidate_and_t06_accepted_roundtrip(lab):
    _, api, source = lab
    gate.t01().verify_repository(REPO)
    manifest, result = gate.verify_t06_input(source, api)
    assert manifest.artifact_id == gate.T06_MANIFEST_ID
    assert result.artifact_id == gate.T06_RESULT_ID
    assert result.semantic_payload["status"] == "PASS"
    assert result.semantic_payload["output_artifact_refs"] == [gate.ref(manifest)]


def test_exact_candidate_profile_identity_from_frozen_refs():
    api = gate.load_api(REPO)
    payload = {"classification_runtime_profile_contract_version": gate.profile_version(api)}
    payload.update({field: {"artifact_id": artifact_id,
                            "content_sha256": artifact_id.rsplit(":", 1)[1]}
                    for field, artifact_id in gate.EXACT_IDS.items()})
    payload["classifier_artifact_manifest"] = {
        "artifact_id": gate.T06_MANIFEST_ID,
        "content_sha256": gate.T06_MANIFEST_ID.rsplit(":", 1)[1]}
    profile = api.profiles.make_classification_runtime_profile(payload)
    assert set(profile.semantic_payload) == set(payload)
    assert profile.artifact_id == api.profiles.make_classification_runtime_profile(
        dict(reversed(list(payload.items())))).artifact_id
    print("CANDIDATE_PROFILE_ARTIFACT_ID=" + profile.artifact_id)


def test_profile_closed_shape_permutation_and_back_reference(lab):
    prepared, api, source = lab
    classifier, _ = gate.verify_t06_input(source, api)
    contents = {"foundation_runtime_profile": prepared.profile,
                "knowledge_bundle": prepared.source.knowledge_bundle,
                "classification_policy": prepared.baseline.classification_policy,
                "evidence_adapter_contract_set": prepared.source.evidence_adapter_contract_set,
                "classifier_artifact_manifest": classifier}
    a = gate.build_profile(api, contents)
    b = gate.build_profile(api, dict(reversed(list(contents.items()))), reverse=True)
    assert a == b
    assert api.artifact.canonical_artifact_json(gate.document(a)) == api.artifact.canonical_artifact_json(gate.document(b))
    assert set(a.semantic_payload) == {"classification_runtime_profile_contract_version", *contents}
    injected = a.semantic_payload
    injected["task04_acceptance_manifest"] = gate.ref(classifier)
    with pytest.raises(Exception):
        api.profiles.make_classification_runtime_profile(injected)


def test_full_pass_readonly_and_deterministic_graph(lab, tmp_path):
    prepared, api, source = lab
    before_db = prepared.database.read_bytes()
    before_repo = gate.t01().repository_filesystem_fingerprint(REPO)
    status, run = _run(lab, tmp_path, "pass")
    assert status == 0, (run / "t06a-compatibility-report.json").read_text()
    report = json.loads((run / "t06a-compatibility-report.json").read_text())
    assert report["all_pass"] and [row["check_id"] for row in report["checks"]] == [
        f"C{i:02}" for i in range(1, 10)]
    graph = json.loads((run / "t06a-dependency-graph.json").read_text())
    assert graph["node_count"] > 5 and graph["edge_count"] > 4
    assert len(graph["topological_order"]) == graph["node_count"]
    assert len(set(graph["topological_order"])) == graph["node_count"]
    assert all("Task04AcceptanceManifest" not in node["artifact_type"] for node in graph["nodes"])
    with gate.t01().open_foundation_read_only(prepared.database) as connection:
        first = api.artifact.decode_artifact_json(
            (run / "t06a-classification-runtime-profile.json").read_text())
        profile = api.profiles.make_classification_runtime_profile(first["semantic_payload"])
        classifier, _ = gate.verify_t06_input(source, api)
        assert graph == gate.concrete_graph(connection, api, profile, classifier)
    result = api.artifact.decode_artifact_json((run / "t06a-gate-result-manifest.json").read_text())
    assert result["semantic_payload"]["status"] == "PASS"
    assert len(result["semantic_payload"]["output_artifact_refs"]) == 2
    assert prepared.database.read_bytes() == before_db
    assert gate.t01().repository_filesystem_fingerprint(REPO) == before_repo


@pytest.mark.parametrize("check", [f"C{i:02}" for i in range(1, 10)])
def test_each_compatibility_check_fails_closed(lab, check):
    prepared, api, source = lab
    classifier, _ = gate.verify_t06_input(source, api)
    contents = {"foundation_runtime_profile": prepared.profile,
                "knowledge_bundle": prepared.source.knowledge_bundle,
                "classification_policy": prepared.baseline.classification_policy,
                "evidence_adapter_contract_set": prepared.source.evidence_adapter_contract_set,
                "classifier_artifact_manifest": classifier}
    # Mutate one actual in-memory semantic value; the persisted DB and T-06
    # files remain intact. Generic ArtifactContent deliberately bypasses the
    # target builder so the compatibility check, not construction, must fail.
    field = {
        "C01": "knowledge_bundle", "C02": "knowledge_bundle",
        "C03": "classification_policy", "C04": "classifier_artifact_manifest",
        "C05": "classifier_artifact_manifest", "C06": "evidence_adapter_contract_set",
        "C07": "classifier_artifact_manifest", "C08": "classifier_artifact_manifest",
        "C09": "foundation_runtime_profile",
    }[check]
    original = contents[field]
    payload = original.semantic_payload
    wrong_ref = gate.ref(prepared.source.knowledge.classification_taxonomy)
    alias_ref = gate.ref(prepared.source.knowledge.alias_mapping)
    if check == "C01":
        payload["classification_taxonomy"] = alias_ref
    elif check == "C02":
        payload["alias_mapping"] = wrong_ref
    elif check == "C03":
        payload["evidence_adapter_contract_set"] = wrong_ref
    elif check == "C04":
        payload["adapter_implementation_identities"][0]["mode"] = "NON_FUSION_HANDLER"
    elif check == "C05":
        payload["snapshot_contract_version"] += 1
    elif check == "C06":
        payload["evidence_schema_registry"] = wrong_ref
    elif check == "C07":
        payload["k2a_matcher_implementation_version"] = "wrong-k2a"
    elif check == "C08":
        payload["classification_result_schema_version"] += 1
    elif check == "C09":
        payload["origin_runtime_admission"] = wrong_ref
    contents[field] = api.artifact.make_artifact_content(original.artifact_type, payload)
    with gate.t01().open_foundation_read_only(prepared.database) as connection:
        foundation = gate.t01().verify_foundation(connection, api)
        rows = gate.compatibility(connection, api, contents, foundation)
    targeted = next(row for row in rows if row["check_id"] == check)
    assert targeted["status"] == "FAIL" and targeted["failure_code"] == f"{check}_MISMATCH"


def test_full_fail_has_no_profile_or_proof_and_is_readonly(lab, tmp_path, monkeypatch):
    prepared, api, _ = lab
    before_db = prepared.database.read_bytes()
    before_repo = gate.t01().repository_filesystem_fingerprint(REPO)
    original = gate.compatibility
    def mismatch(*args):
        rows = original(*args)
        rows[0]["status"] = "FAIL"
        rows[0]["failure_code"] = "C01_MISMATCH"
        return rows
    monkeypatch.setattr(gate, "compatibility", mismatch)
    status, run = _run(lab, tmp_path, "fail")
    assert status == 1
    assert not (run / "t06a-classification-runtime-profile.json").exists()
    assert not (run / "t06a-gate-proof-artifact.json").exists()
    result = api.artifact.decode_artifact_json((run / "t06a-gate-result-manifest.json").read_text())
    assert result["semantic_payload"]["status"] == "FAIL"
    assert result["semantic_payload"]["output_artifact_refs"] == []
    assert prepared.database.read_bytes() == before_db
    assert gate.t01().repository_filesystem_fingerprint(REPO) == before_repo


def test_t06_wrong_identity_and_status_block_or_fail(lab, tmp_path):
    prepared, api, input_dir = lab
    path = input_dir / "t06-gate-result-manifest.json"
    original = path.read_bytes()
    value = api.artifact.decode_artifact_json(original.decode("utf-8"))
    payload = value["semantic_payload"]
    payload["status"] = "FAIL"
    payload["output_artifact_refs"] = []
    nonpass = api.gate_result.make_gate_result_manifest(payload)
    path.write_bytes(api.artifact.canonical_artifact_json(gate.document(nonpass)) + b"\n")
    status, run = _run(lab, tmp_path, "wrong-status")
    assert status == 1
    assert not (run / "t06a-classification-runtime-profile.json").exists()
    formal = api.artifact.decode_artifact_json((run / "t06a-gate-result-manifest.json").read_text())
    assert formal["semantic_payload"]["status"] == "FAIL"
    path.write_bytes(original.replace(gate.T06_MANIFEST_ID.encode(), b"ClassifierArtifactManifest:v1:sha256:" + b"0" * 64))
    status, run = _run(lab, tmp_path, "wrong-ref")
    assert status in (1, 2)
    assert not (run / "t06a-gate-proof-artifact.json").exists()


def test_missing_dependency_and_digest_mismatch_fail(lab):
    prepared, api, source = lab
    classifier, _ = gate.verify_t06_input(source, api)
    contents = {"foundation_runtime_profile": prepared.profile,
                "knowledge_bundle": prepared.source.knowledge_bundle,
                "classification_policy": prepared.baseline.classification_policy,
                "evidence_adapter_contract_set": prepared.source.evidence_adapter_contract_set,
                "classifier_artifact_manifest": classifier}
    profile = gate.build_profile(api, contents)
    with sqlite3.connect(prepared.database) as connection:
        connection.execute("DELETE FROM artifacts WHERE artifact_id=?",
                           (prepared.source.knowledge_bundle.artifact_id,))
    with gate.t01().open_foundation_read_only(prepared.database) as connection:
        with pytest.raises(gate.SemanticFailure, match="DEPENDENCY_MISSING_OR_DIGEST"):
            gate.concrete_graph(connection, api, profile, classifier)
    changed = profile.semantic_payload
    changed["knowledge_bundle"]["content_sha256"] = "0" * 64
    with pytest.raises(Exception):
        api.profiles.make_classification_runtime_profile(changed)


def test_persisted_dependency_digest_mismatch_fails(lab):
    prepared, api, source = lab
    classifier, _ = gate.verify_t06_input(source, api)
    profile = gate.build_profile(api, {
        "foundation_runtime_profile": prepared.profile,
        "knowledge_bundle": prepared.source.knowledge_bundle,
        "classification_policy": prepared.baseline.classification_policy,
        "evidence_adapter_contract_set": prepared.source.evidence_adapter_contract_set,
        "classifier_artifact_manifest": classifier})
    with sqlite3.connect(prepared.database) as connection:
        connection.execute("UPDATE artifacts SET content_sha256=? WHERE artifact_id=?",
                           ("0" * 64, prepared.source.knowledge_bundle.artifact_id))
    with gate.t01().open_foundation_read_only(prepared.database) as connection:
        with pytest.raises(gate.SemanticFailure, match="DEPENDENCY_MISSING_OR_DIGEST"):
            gate.concrete_graph(connection, api, profile, classifier)


def test_full_dependency_cycle_is_formal_fail(lab, tmp_path, monkeypatch):
    _, api, _ = lab
    def cycle(*_args):
        raise api.graph.ArtifactDependencyGraphError("artifact_dependency_cycle",
                                                      ("A", "B", "A"))
    monkeypatch.setattr(gate, "concrete_graph", cycle)
    status, run = _run(lab, tmp_path, "cycle")
    assert status == 1
    assert not (run / "t06a-classification-runtime-profile.json").exists()
    assert not (run / "t06a-gate-proof-artifact.json").exists()
    result = api.artifact.decode_artifact_json((run / "t06a-gate-result-manifest.json").read_text())
    assert result["semantic_payload"]["status"] == "FAIL"
    assert result["semantic_payload"]["output_artifact_refs"] == []


def test_cycle_detection_and_order_from_candidate_graph(lab):
    _, api, _ = lab
    nodes = api.graph.build_required_cycle_regression_fixtures()["mutual_artifact"]
    with pytest.raises(api.graph.ArtifactDependencyGraphError, match="artifact_dependency_cycle"):
        api.graph.analyze_artifact_dependency_graph(nodes)
    normal = api.graph.build_task04_schema_template_graph()
    one = api.graph.analyze_artifact_dependency_graph(normal)
    two = api.graph.analyze_artifact_dependency_graph(reversed(normal))
    assert one.topological_order == two.topological_order


def test_blocked_paths_runner_repo_and_missing_input(lab, tmp_path, monkeypatch):
    prepared, _, source = lab
    original = gate.t01()._git
    monkeypatch.setattr(gate.t01(), "_git", lambda repo, *args: (
        " M changed" if args == ("status", "--porcelain") else original(repo, *args)))
    status, run = _run(lab, tmp_path, "dirty-repo")
    assert status == 2 and not (run / "t06a-gate-result-manifest.json").exists()
    monkeypatch.undo()
    def repository_mutated(*_args):
        raise gate.t01().Blocked("BLOCKED_REPOSITORY_MUTATED")
    monkeypatch.setattr(gate.t01(), "_require_repository_unchanged", repository_mutated)
    status, run = _run(lab, tmp_path, "repo-mutated-during-run")
    assert status == 2 and not (run / "t06a-gate-result-manifest.json").exists()
    monkeypatch.undo()
    calls = {"runner": 0}
    def changed_hash(path):
        if path == RUNNER:
            calls["runner"] += 1
            if calls["runner"] > 1:
                return "0" * 64
        return hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(gate, "sha256", changed_hash)
    status, run = _run(lab, tmp_path, "runner-mutated")
    assert status == 2 and not (run / "t06a-gate-result-manifest.json").exists()


def test_missing_t06_files_block(lab, tmp_path):
    _, _, source = lab
    (source / "t06-manifest.json").unlink()
    status, run = _run(lab, tmp_path, "missing-input")
    assert status == 2
    assert not (run / "t06a-gate-result-manifest.json").exists()
