"""Disposable self-tests only; never run official T-06 on the accepted Foundation DB."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "task04-t06-gate-r1.py"
REPO = Path(r"C:\CaptivPortal-UI-Preview")
REGISTRATION = Path(r"C:\Users\Zaur Navi\Downloads\R14_T06_IMPLEMENTATION_IDENTITY_REGISTRATION_V1.json")
ARCHITECTURE = Path(r"C:\Users\Zaur Navi\Downloads\DEVICE-FINGERPRINT-03A-R2_TASK-04_ARCHITECTURE_DECISION_R14_FINAL_REPAIRED_ACCEPTED_TTL_TOPOLOGY_REGISTERED.md")
T04_SELFTEST = HERE.parents[0] / "t04" / "test_task04_t04_gate_r1.py"
T04_SELFTEST_SHA256 = "168151ad52fcf2aa328ffd79ff9556d251bc1b2790b4c3a4b83c07b061ac7546"
SPEC = importlib.util.spec_from_file_location("task04_t06_gate_selftest_target", RUNNER)
assert SPEC is not None and SPEC.loader is not None
gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)


def _t04_selftest():
    assert gate._sha256(T04_SELFTEST) == T04_SELFTEST_SHA256
    spec = importlib.util.spec_from_file_location("task04_t04_disposable_foundation_fixture", T04_SELFTEST)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def lab(tmp_path, monkeypatch):
    prepared = _t04_selftest().full_run_lab.__wrapped__(tmp_path, monkeypatch)
    helper = gate._t01()
    helper.EXPECTED_DIGESTS = {
        "FoundationAdmissionManifest": prepared.manifest.content_sha256,
        "FoundationRuntimeProfile": prepared.profile.content_sha256,
        "RuntimeProfileAdmissionManifest": prepared.admission.content_sha256,
        "GateResultManifest": prepared.result.content_sha256,
        "EvidenceSchemaRegistryContract": prepared.registry.content_sha256,
    }
    return prepared


def _admitted(lab):
    return {"adapter": lab.source.evidence_adapter_contract_set,
            "knowledge": lab.source.knowledge_bundle,
            "k2a": lab.extras["K2AConformancePackage"],
            "disposition": lab.extras["CapabilityDisposition"],
            "registry": lab.registry}


def _run_directory(output):
    children = list(output.iterdir())
    assert len(children) == 1 and children[0].is_dir()
    return children[0]


def test_exact_candidate_and_registration_bytes():
    helper = gate._t01()
    helper.verify_repository(REPO)
    assert helper._git(REPO, "rev-parse", "HEAD") == gate.EXPECTED_COMMIT
    assert helper._git(REPO, "show", "-s", "--format=%T", "HEAD") == gate.EXPECTED_TREE
    registration, raw = gate.validate_registration(REGISTRATION, ARCHITECTURE)
    assert hashlib.sha256(raw).hexdigest() == gate.REGISTRATION_SHA256
    assert registration == gate.REGISTRATION
    assert gate._sha256(ARCHITECTURE) == gate.ARCHITECTURE_SHA256


@pytest.mark.parametrize("mutation", [
    "registration_type", "registration_schema_version", "repository_commit_sha",
    "repository_tree_sha", "classification_engine_semver", "pure_core_contract_version",
    "architecture_revision", "architecture_document_sha256", "scope", "extra", "missing",
])
def test_registration_closed_values_block(mutation):
    changed = dict(gate.REGISTRATION)
    if mutation == "extra":
        changed["unapproved"] = True
    elif mutation == "missing":
        changed.pop("scope")
    else:
        changed[mutation] = 2 if mutation == "registration_schema_version" else "wrong"
    with pytest.raises(gate.SemanticFailure, match="REGISTRATION_CONTENT_MISMATCH"):
        gate._validate_registration_fields(changed)


def test_missing_or_mutated_registration_and_architecture_block(tmp_path):
    with pytest.raises(gate.Blocked, match="BLOCKED_IMPLEMENTATION_IDENTITY_REGISTRATION"):
        gate.validate_registration(tmp_path / "missing.json", ARCHITECTURE)
    changed = tmp_path / "registration.json"
    changed.write_bytes(REGISTRATION.read_bytes() + b" ")
    with pytest.raises(gate.SemanticFailure, match="REGISTRATION_DIGEST_MISMATCH"):
        gate.validate_registration(changed, ARCHITECTURE)
    changed_architecture = tmp_path / "R14.md"
    changed_architecture.write_bytes(ARCHITECTURE.read_bytes() + b" ")
    with pytest.raises(gate.SemanticFailure, match="ARCHITECTURE_DIGEST_MISMATCH"):
        gate.validate_registration(REGISTRATION, changed_architecture)
    with pytest.raises(gate.Blocked, match="BLOCKED_ARCHITECTURE_IDENTITY"):
        gate.validate_registration(REGISTRATION, tmp_path / "missing-R14.md")


def test_dirty_candidate_helper_runner_and_outside_module_blocks(tmp_path, monkeypatch):
    helper = gate._t01()
    original_git = helper._git
    monkeypatch.setattr(helper, "_git", lambda repo, *args: (
        " M dirty" if args == ("status", "--porcelain") else original_git(repo, *args)))
    with pytest.raises(helper.Blocked, match="BLOCKED_CANDIDATE_IDENTITY"):
        helper.verify_repository(REPO)
    monkeypatch.undo()
    monkeypatch.setattr(gate, "T01_HELPER_SHA256", "0" * 64)
    with pytest.raises(gate.Blocked, match="BLOCKED_HARDENED_HELPER_CHANGED"):
        gate._t01()
    monkeypatch.undo()
    gate._runner_guard(RUNNER, gate._sha256(RUNNER))
    modified = tmp_path / "runner.py"
    modified.write_bytes(RUNNER.read_bytes() + b"# mutation\n")
    with pytest.raises(gate.Blocked, match="BLOCKED_RUNNER_CHANGED"):
        gate._runner_guard(modified, gate._sha256(RUNNER))
    outside_path = tmp_path / "outside.py"
    outside_path.write_text("# disposable outside-repository implementation\n")
    outside = SimpleNamespace(__file__=str(outside_path), callable=lambda: None)
    with pytest.raises(gate.Blocked, match="BLOCKED_CANDIDATE_IDENTITY"):
        gate._symbol_identity(REPO, outside, "callable")


def test_readonly_foundation_and_active_validity(lab):
    helper = gate._t01()
    before = gate._sha256(lab.database)
    api = gate.load_api(REPO)
    with helper.open_foundation_read_only(lab.database) as connection:
        assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
        lineage = helper.verify_foundation(connection, api)
        assert lineage.validity.semantic_payload["state"] == "ACTIVE"
        admitted = gate.resolve_foundation(connection, api, lineage)
        assert admitted["adapter"].artifact_id == lab.source.evidence_adapter_contract_set.artifact_id
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("INSERT INTO artifacts (artifact_id) VALUES ('not-allowed')")
    assert gate._sha256(lab.database) == before


def test_missing_validity_head_blocks(lab):
    helper = gate._t01()
    with sqlite3.connect(lab.database) as connection:
        connection.execute("DELETE FROM validity_heads")
    api = gate.load_api(REPO)
    with helper.open_foundation_read_only(lab.database) as connection:
        with pytest.raises(helper.Blocked, match="BLOCKED_FOUNDATION_LINEAGE"):
            helper.verify_foundation(connection, api)


def test_admitted_inventory_closed_variants_and_permutation(lab):
    api = gate.load_api(REPO)
    admitted = _admitted(lab)
    first, inventory = gate.build_inventory(api, admitted)
    second, reversed_inventory = gate.build_inventory(api, admitted, reverse=True)
    assert first == second
    assert len(inventory) == len(reversed_inventory) == 8
    assert {(row["source_kind"], row["feature_schema_version"])
            for row in first if row["adapter_kind"] == "TASK01_EVIDENCE"} == (
                set(gate.BASE_TASK_KEYS) | {("portal_headers", 2)})
    tcp_legacy = next(row for row in first if row.get("source_kind") == "tcp_syn"
                      and row.get("feature_schema_version") == 1)
    assert tcp_legacy["mode"] == "NON_FUSION_HANDLER"
    tcp_current = next(row for row in first if row.get("source_kind") == "tcp_syn"
                       and row.get("feature_schema_version") == 2)
    assert tcp_current["mode"] == "FUSION"
    assert next(row for row in first if row.get("feature_schema_version") == 2
                and row.get("source_kind") == "portal_headers")["mode"] == "OPTIONAL_IF_ADMITTED"
    mac = next(row for row in first if row["adapter_kind"] == "MAC_REGISTRY")
    assert set(mac) == {"adapter_kind", "origin_group", "implementation_id",
                        "implementation_digest", "mode"}
    assert mac["origin_group"] == "mac_registry" and mac["mode"] == "FUSION"
    assert all(row["repository_relative_source_path"] ==
               "app/device_fingerprint/origin_assessment.py" for row in inventory)


def test_portal_v2_nonadmitted_inventory_and_invalid_coverage(lab):
    api = gate.load_api(REPO)
    admitted = _admitted(lab)
    registry = copy.deepcopy(admitted["registry"].semantic_payload)
    registry["schema_entries"] = [row for row in registry["schema_entries"]
                                  if (row["source_kind"], row["feature_schema_version"]) !=
                                  ("portal_headers", 2)]
    adapter = copy.deepcopy(admitted["adapter"].semantic_payload)
    adapter["adapter_entries"] = [row for row in adapter["adapter_entries"]
                                  if not (row.get("source_kind") == "portal_headers" and
                                          row.get("feature_schema_version") == 2)]
    disposition = {**admitted["disposition"].semantic_payload, "status": "NOT_ADMITTED"}
    variant = {**admitted, "registry": SimpleNamespace(semantic_payload=registry),
               "adapter": SimpleNamespace(semantic_payload=adapter),
               "disposition": SimpleNamespace(semantic_payload=disposition)}
    semantic, _ = gate.build_inventory(api, variant)
    assert len(semantic) == 7
    assert not any(row.get("source_kind") == "portal_headers" and
                   row.get("feature_schema_version") == 2 for row in semantic)
    invalid = copy.deepcopy(adapter)
    invalid["adapter_entries"].append(copy.deepcopy(invalid["adapter_entries"][0]))
    with pytest.raises(ValueError, match="coverage"):
        gate.build_inventory(api, {**variant, "adapter": SimpleNamespace(semantic_payload=invalid)})
    invalid = copy.deepcopy(adapter)
    invalid["adapter_entries"].pop(0)
    with pytest.raises(ValueError, match="coverage"):
        gate.build_inventory(api, {**variant, "adapter": SimpleNamespace(semantic_payload=invalid)})
    invalid = copy.deepcopy(adapter)
    invalid["adapter_entries"].append(next(row for row in admitted["adapter"].semantic_payload[
        "adapter_entries"] if row.get("source_kind") == "portal_headers" and
        row.get("feature_schema_version") == 2))
    with pytest.raises(ValueError, match="coverage"):
        gate.build_inventory(api, {**variant, "adapter": SimpleNamespace(semantic_payload=invalid)})


def test_manifest_shape_roundtrip_determinism_and_file_digest_binding(lab, monkeypatch):
    api = gate.load_api(REPO)
    helper = gate._t01()
    with helper.open_foundation_read_only(lab.database) as connection:
        lineage = helper.verify_foundation(connection, api)
        admitted = gate.resolve_foundation(connection, api, lineage)
        first, inventory, evidence = gate.construct_manifest(api, lineage, admitted,
                                                              gate.REGISTRATION)
        second, _, _ = gate.construct_manifest(api, lineage, admitted,
                                               gate.REGISTRATION, reverse=True)
    assert first == second
    assert set(first.semantic_payload) == gate.MANIFEST_FIELDS
    assert first.artifact_schema_version == 1
    assert first.semantic_payload["classification_engine_semver"] == "1.0.0"
    assert first.semantic_payload["pure_core_contract_version"] == "R14-PURE-CORE-V1"
    assert first.semantic_payload["build_package_digest"] is None
    assert api.artifact.make_artifact_content("ClassifierArtifactManifest",
                                              first.semantic_payload) == first
    assert evidence["k2a_matcher"]["version"] == api.p0f.MATCHER_CONTRACT
    assert evidence["artifact_canonical_json_implementation"]["implementation_digest"] == gate._sha256(
        Path(api.artifact.__file__))
    assert evidence["evidence_canonical_json_compatibility"]["implementation_digest"] == gate._sha256(
        Path(api.validation.__file__))
    assert len(inventory) == 8
    actual = gate._sha256(Path(api.origin.__file__))
    real_sha = gate._sha256
    monkeypatch.setattr(gate, "_sha256", lambda path: "0" * 64 if Path(path) == Path(
        api.origin.__file__) else real_sha(path))
    changed, _, _ = gate.construct_manifest(api, lineage, admitted, gate.REGISTRATION)
    assert changed.content_sha256 != first.content_sha256
    assert actual != "0" * 64


def test_closed_manifest_shape_rejects_mac_task_fields(lab):
    api = gate.load_api(REPO)
    helper = gate._t01()
    with helper.open_foundation_read_only(lab.database) as connection:
        lineage = helper.verify_foundation(connection, api)
        admitted = gate.resolve_foundation(connection, api, lineage)
        manifest, _, _ = gate.construct_manifest(api, lineage, admitted, gate.REGISTRATION)
    changed = copy.deepcopy(manifest.semantic_payload)
    mac = next(row for row in changed["adapter_implementation_identities"]
               if row["adapter_kind"] == "MAC_REGISTRY")
    mac["source_kind"] = "fabricated"
    with pytest.raises(ValueError, match="MAC_REGISTRY tagged shape"):
        gate.verify_manifest_shape(api, changed)
    changed = copy.deepcopy(manifest.semantic_payload)
    changed["unapproved"] = True
    with pytest.raises(ValueError, match="field set"):
        gate.verify_manifest_shape(api, changed)


def test_unknown_required_version_blocks(lab, monkeypatch):
    api = gate.load_api(REPO)
    helper = gate._t01()
    with helper.open_foundation_read_only(lab.database) as connection:
        lineage = helper.verify_foundation(connection, api)
        admitted = gate.resolve_foundation(connection, api, lineage)
        monkeypatch.setattr(api.p0f, "MATCHER_CONTRACT", None)
        with pytest.raises(gate.SemanticFailure, match="IMPLEMENTATION_IDENTITY_UNRESOLVED"):
            gate.construct_manifest(api, lineage, admitted, gate.REGISTRATION)


@pytest.mark.parametrize("outcome", ["PASS", "FAIL", "BLOCKED"])
def test_full_run_gate_state_separation_and_immutability(lab, tmp_path, monkeypatch, outcome):
    helper = gate._t01()
    repo_before = helper.repository_filesystem_fingerprint(REPO)
    db_before = gate._sha256(lab.database)
    if outcome == "FAIL":
        monkeypatch.setattr(gate, "construct_manifest", lambda *_args, **_kwargs: (
            _ for _ in ()).throw(ValueError("disposable semantic verification failure")))
    registration = REGISTRATION
    if outcome == "BLOCKED":
        registration = tmp_path / "missing-registration.json"
    output = tmp_path / "t06-run-output"
    status = gate.run_gate(REPO, lab.database, registration, ARCHITECTURE, output)
    run_dir = _run_directory(output)
    expected = {"PASS": 0, "FAIL": 1, "BLOCKED": 2}[outcome]
    assert status == expected
    summary = (run_dir / "t06-summary.txt").read_text(encoding="utf-8")
    assert f"GATE_EXECUTION_STATUS={'BLOCKED_IMPLEMENTATION_IDENTITY_REGISTRATION' if outcome == 'BLOCKED' else outcome}" in summary
    manifest_file = run_dir / "t06-manifest.json"
    result_file = run_dir / "t06-gate-result-manifest.json"
    assert manifest_file.is_file() is (outcome == "PASS")
    assert result_file.is_file() is (outcome != "BLOCKED")
    if outcome != "BLOCKED":
        result = json.loads(result_file.read_bytes())["semantic_payload"]
        assert result["status"] == outcome and result["gate_id"] == "T-06"
        assert result["gate_contract_version"] == "R14-T-06-v1"
        assert result["decision_record_refs"] == []
        assert (len(result["output_artifact_refs"]) == 1) is (outcome == "PASS")
        for row in result["retained_evidence_refs"]:
            assert row["file_sha256"] == gate._sha256(run_dir / row["path_or_reference"])
        registration_ref = next(row for row in result["retained_evidence_refs"]
                                if row["evidence_label"] ==
                                "t06-implementation-identity-registration")
        assert registration_ref["file_sha256"] == gate.REGISTRATION_SHA256
        if outcome == "PASS":
            manifest = json.loads(manifest_file.read_bytes())
            assert manifest["artifact_type"] == "ClassifierArtifactManifest"
            assert manifest["content_sha256"] == (
                "cae20d120812e99f67d7d6827ac423ee0ad1d887497ac3f607cced7a161e6cb2")
            assert manifest["semantic_payload"]["classification_engine_semver"] == "1.0.0"
            assert manifest["semantic_payload"]["pure_core_contract_version"] == "R14-PURE-CORE-V1"
            assert result["output_artifact_refs"] == [{
                "artifact_id": manifest["artifact_id"],
                "content_sha256": manifest["content_sha256"]}]
    assert helper.repository_filesystem_fingerprint(REPO) == repo_before
    assert gate._sha256(lab.database) == db_before


def _assert_formal_fail(output):
    run_dir = _run_directory(output)
    assert not (run_dir / "t06-manifest.json").exists()
    result_path = run_dir / "t06-gate-result-manifest.json"
    assert result_path.is_file()
    result = json.loads(result_path.read_bytes())["semantic_payload"]
    assert result["gate_id"] == "T-06" and result["gate_contract_version"] == "R14-T-06-v1"
    assert result["status"] == "FAIL" and result["output_artifact_refs"] == []
    for row in result["retained_evidence_refs"]:
        assert row["file_sha256"] == gate._sha256(run_dir / row["path_or_reference"])
    return run_dir, result


def _assert_blocked(output, status):
    run_dir = _run_directory(output)
    assert f"GATE_EXECUTION_STATUS={status}" in (run_dir / "t06-summary.txt").read_text()
    assert not (run_dir / "t06-manifest.json").exists()
    assert not (run_dir / "t06-gate-result-manifest.json").exists()


def test_full_run_registration_digest_and_values_are_formal_fail(lab, tmp_path):
    helper = gate._t01()
    repo_before = helper.repository_filesystem_fingerprint(REPO)
    db_before = gate._sha256(lab.database)
    variants = {"wrong-digest": REGISTRATION.read_bytes() + b" "}
    for field in ("registration_type", "registration_schema_version", "repository_commit_sha",
                  "repository_tree_sha", "architecture_revision", "architecture_document_sha256",
                  "classification_engine_semver", "pure_core_contract_version", "scope"):
        changed = dict(gate.REGISTRATION)
        changed[field] = 2 if field == "registration_schema_version" else "wrong"
        variants[field] = gate._json_bytes(changed)
    variants["extra-field"] = gate._json_bytes({**gate.REGISTRATION, "unapproved": True})
    changed = dict(gate.REGISTRATION)
    changed.pop("scope")
    variants["missing-field"] = gate._json_bytes(changed)
    for label, raw in variants.items():
        supplied = tmp_path / f"{label}.json"
        supplied.write_bytes(raw)
        output = tmp_path / f"{label}-output"
        assert gate.run_gate(REPO, lab.database, supplied, ARCHITECTURE, output) == 1, label
        run_dir, _ = _assert_formal_fail(output)
        retained = run_dir / "t06-supplied-implementation-identity-registration.json"
        assert retained.read_bytes() == raw
        evidence = json.loads((run_dir / "t06-build-identity.json").read_bytes())
        assert evidence["actual_registration_sha256"] == hashlib.sha256(raw).hexdigest()
        assert evidence["expected_registration_sha256"] == gate.REGISTRATION_SHA256
        assert evidence["validation_failure_code"] == "REGISTRATION_DIGEST_MISMATCH"
    assert helper.repository_filesystem_fingerprint(REPO) == repo_before
    assert gate._sha256(lab.database) == db_before


def test_full_run_missing_unreadable_inputs_block_and_architecture_digest_fails(lab, tmp_path):
    helper = gate._t01()
    repo_before = helper.repository_filesystem_fingerprint(REPO)
    db_before = gate._sha256(lab.database)
    cases = [
        ("registration-missing", tmp_path / "missing.json", ARCHITECTURE,
         "BLOCKED_IMPLEMENTATION_IDENTITY_REGISTRATION"),
        ("registration-unreadable", tmp_path, ARCHITECTURE,
         "BLOCKED_IMPLEMENTATION_IDENTITY_REGISTRATION"),
        ("architecture-missing", REGISTRATION, tmp_path / "missing-R14.md",
         "BLOCKED_ARCHITECTURE_IDENTITY"),
        ("architecture-unreadable", REGISTRATION, tmp_path,
         "BLOCKED_ARCHITECTURE_IDENTITY"),
    ]
    for label, registration, architecture, status in cases:
        output = tmp_path / f"{label}-output"
        assert gate.run_gate(REPO, lab.database, registration, architecture, output) == 2
        _assert_blocked(output, status)
    wrong_architecture = tmp_path / "wrong-R14.md"
    wrong_architecture.write_bytes(ARCHITECTURE.read_bytes() + b" ")
    output = tmp_path / "architecture-digest-output"
    assert gate.run_gate(REPO, lab.database, REGISTRATION, wrong_architecture, output) == 1
    run_dir, _ = _assert_formal_fail(output)
    evidence = json.loads((run_dir / "t06-build-identity.json").read_bytes())
    assert evidence["validation_failure_code"] == "ARCHITECTURE_DIGEST_MISMATCH"
    assert evidence["expected_architecture_sha256"] == gate.ARCHITECTURE_SHA256
    assert evidence["actual_architecture_sha256"] == gate._sha256(wrong_architecture)
    assert helper.repository_filesystem_fingerprint(REPO) == repo_before
    assert gate._sha256(lab.database) == db_before


@pytest.mark.parametrize("failure", ["k2a-version", "required-symbol", "foundation-invalid"])
def test_full_run_semantic_identity_fail_and_invalid_foundation_block(
        lab, tmp_path, monkeypatch, failure):
    helper = gate._t01()
    repo_before = helper.repository_filesystem_fingerprint(REPO)
    if failure == "k2a-version":
        api = gate.load_api(REPO)
        monkeypatch.setattr(api.p0f, "MATCHER_CONTRACT", None)
    elif failure == "required-symbol":
        original = gate._symbol_identity
        def missing_symbol(repo, module, symbol, role=None):
            if symbol == "DeviceFingerprintOriginAssessmentBuilder.build":
                raise gate.SemanticFailure("IMPLEMENTATION_IDENTITY_UNRESOLVED", symbol)
            return original(repo, module, symbol, role)
        monkeypatch.setattr(gate, "_symbol_identity", missing_symbol)
    else:
        with sqlite3.connect(lab.database) as connection:
            connection.execute("DELETE FROM validity_heads")
    db_before = gate._sha256(lab.database)
    output = tmp_path / "semantic-state-output"
    status = gate.run_gate(REPO, lab.database, REGISTRATION, ARCHITECTURE, output)
    if failure == "foundation-invalid":
        assert status == 2
        _assert_blocked(output, "BLOCKED_FOUNDATION_LINEAGE")
    else:
        assert status == 1
        run_dir, _ = _assert_formal_fail(output)
        evidence = json.loads((run_dir / "t06-build-identity.json").read_bytes())
        assert evidence["validation_failure_code"] == "IMPLEMENTATION_IDENTITY_UNRESOLVED"
    assert helper.repository_filesystem_fingerprint(REPO) == repo_before
    assert gate._sha256(lab.database) == db_before


@pytest.mark.parametrize("mutation", ["repository", "runner"])
def test_full_run_gate_immutability_mutation_blocks(lab, tmp_path, monkeypatch, mutation):
    helper = gate._t01()
    original_fingerprint = helper.repository_filesystem_fingerprint(REPO)
    original_db = gate._sha256(lab.database)
    calls = {"count": 0}
    if mutation == "repository":
        original_guard = helper._require_repository_unchanged
        def changed_repo(repo, expected):
            calls["count"] += 1
            if calls["count"] >= 2:
                raise helper.Blocked("BLOCKED_REPOSITORY_MUTATED")
            return original_guard(repo, expected)
        monkeypatch.setattr(helper, "_require_repository_unchanged", changed_repo)
    else:
        original_guard = gate._runner_guard
        def changed_runner(path, expected):
            calls["count"] += 1
            if calls["count"] >= 2:
                raise gate.Blocked("BLOCKED_RUNNER_CHANGED")
            return original_guard(path, expected)
        monkeypatch.setattr(gate, "_runner_guard", changed_runner)
    output = tmp_path / "blocked-mutation-output"
    assert gate.run_gate(REPO, lab.database, REGISTRATION, ARCHITECTURE, output) == 2
    run_dir = _run_directory(output)
    expected_status = "BLOCKED_REPOSITORY_MUTATED" if mutation == "repository" else "BLOCKED_RUNNER_CHANGED"
    assert f"GATE_EXECUTION_STATUS={expected_status}" in (run_dir / "t06-summary.txt").read_text()
    assert not (run_dir / "t06-manifest.json").exists()
    assert not (run_dir / "t06-gate-result-manifest.json").exists()
    assert helper.repository_filesystem_fingerprint(REPO) == original_fingerprint
    assert gate._sha256(lab.database) == original_db
