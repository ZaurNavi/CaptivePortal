"""External R14 T-04 acceptance harness. Official execution is Owner/TechLead-only.

Importing this module has no repository, database, or gate side effects.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import uuid
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any


sys.dont_write_bytecode = True
EXPECTED_COMMIT = "74f7c7add401e5fec0469d49770466c2747c03cf"
EXPECTED_TREE = "7e93a4863909c3e807a9d8239924d13e0a0d7f71"
GATE_ID = "T-04"
GATE_CONTRACT = "R14-T-04-v1"
PROCEDURE = "T-04-cross-origin-fusion-execution-v1"
PROOF_KIND = "FUSION_EXECUTION"
T01_HELPER_SHA256 = "ee17cbd9a1c6e8e5ac510559ca0d6a21768a26fbb90ae98cb1ed4550d0446668"
T01_HELPER = Path(__file__).resolve().parents[1] / "t01" / "task04-t01-gate-rebind-20260929.py"
CASE_IDS = tuple(f"T04-M{number:02d}" for number in range(1, 11))
FUSION_INPUTS = (
    "strong_clean_present", "strong_clean_disagree", "strong_internal_conflict_present",
    "supporting_clean_present", "supporting_clean_disagree",
    "supporting_internal_conflict_present",
    "supporting_vs_selected_strong_incompatible_present",
)
_HELPER = None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def _ref(content: Any) -> dict[str, str]:
    return {"artifact_id": content.artifact_id, "content_sha256": content.content_sha256}


def _document(content: Any) -> dict[str, Any]:
    return {"artifact_type": content.artifact_type,
            "artifact_schema_version": content.artifact_schema_version,
            "artifact_id": content.artifact_id,
            "content_sha256": content.content_sha256,
            "semantic_payload": content.semantic_payload}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _t01():
    global _HELPER
    if not T01_HELPER.is_file() or _sha256(T01_HELPER) != T01_HELPER_SHA256:
        raise RuntimeError("BLOCKED_HARDENED_HELPER_CHANGED")
    if _HELPER is None:
        spec = importlib.util.spec_from_file_location("task04_t01_hardened_helper", T01_HELPER)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _HELPER = module
    return _HELPER


def _integrity_block(path: Path, expected: str) -> str | None:
    try:
        if _sha256(T01_HELPER) != T01_HELPER_SHA256:
            return "BLOCKED_HARDENED_HELPER_CHANGED"
        if _sha256(path) != expected:
            return "BLOCKED_RUNNER_CHANGED"
    except OSError:
        return "BLOCKED_RUNNER_CHANGED"
    return None


def _candidate_module(repo: Path, name: str):
    module = importlib.import_module(name)
    try:
        if not Path(module.__file__).resolve(strict=True).is_relative_to(repo.resolve(strict=True)):
            raise ValueError("Fixture outside exact candidate")
    except (OSError, TypeError, ValueError) as exc:
        raise _t01().Blocked("BLOCKED_CANDIDATE_IDENTITY") from exc
    return module


def load_api(repo: Path) -> SimpleNamespace:
    base = _t01().load_repository_modules(repo)
    modules = {key: _candidate_module(repo, name) for key, name in {
        "fusion": "app.device_fingerprint.fusion",
        "policy": "app.device_fingerprint.classification_policy",
        "bundle": "app.device_fingerprint.knowledge_bundle",
        "origin": "app.device_fingerprint.origin_assessment",
        "adapter": "app.device_fingerprint.evidence_adapter_contracts",
    }.items()}
    return SimpleNamespace(**vars(base), **modules, repo=repo.resolve())


def resolve_admitted(connection: sqlite3.Connection, api: SimpleNamespace,
                     lineage: Any) -> dict[str, Any]:
    """Resolve exact F-ADMIT semantic inputs, never a fixture substitute."""
    helper = _t01()
    try:
        manifest = lineage.manifest.semantic_payload
        adapter = helper._resolve_artifact(connection, api, manifest["evidence_adapter_contract_set"])
        bundle = helper._resolve_artifact(connection, api, manifest["knowledge_bundle"])
        policy = helper._resolve_artifact(connection, api, manifest["classification_policy"])
        runtime = helper._resolve_artifact(connection, api, manifest["origin_runtime_admission"])
        if (adapter.artifact_type != "EvidenceAdapterContractSet"
                or bundle.artifact_type != "KnowledgeBundle"
                or policy.artifact_type != "ClassificationPolicy"
                or runtime.artifact_type != "OriginRuntimeAdmission"):
            raise ValueError("Incorrect admitted artifact types")
        if lineage.profile.semantic_payload["origin_runtime_admission"] != _ref(runtime):
            raise ValueError("Foundation OriginRuntimeAdmission mismatch")
        if api.foundation.make_origin_runtime_admission(runtime.semantic_payload) != runtime:
            raise ValueError("Noncanonical OriginRuntimeAdmission")
        payload = bundle.semantic_payload
        taxonomy = helper._resolve_artifact(connection, api, payload["classification_taxonomy"])
        alias = helper._resolve_artifact(connection, api, payload["alias_mapping"])
        if api.bundle.make_knowledge_bundle(payload) != bundle:
            raise ValueError("Noncanonical KnowledgeBundle")
        if api.adapter.make_evidence_adapter_contract_set(adapter.semantic_payload) != adapter:
            raise ValueError("Noncanonical EvidenceAdapterContractSet")
        if adapter.semantic_payload["evidence_schema_registry"] != _ref(lineage.registry):
            raise ValueError("Adapter registry mismatch")
        if not api.policy.validate_classification_policy_dependencies(
                policy, classification_taxonomy=taxonomy, alias_mapping=alias,
                evidence_adapter_contract_set=adapter):
            raise ValueError("ClassificationPolicy dependency mismatch")
        if api.policy.make_classification_policy(policy.semantic_payload) != policy:
            raise ValueError("Noncanonical ClassificationPolicy")
        # Resolve the admitted KnowledgeBundle's complete reference inventory.
        records = {name: helper._resolve_artifact(connection, api, payload[name])
                   for name in ("k1_record_set", "k2b_record_set",
                                "k3_portal_rule_set", "k4_record_set")}
        inventories = {name: [helper._resolve_artifact(connection, api, ref)
                              for ref in payload[name]]
                       for name in ("knowledge_provenance_manifests",
                                    "source_governance_records", "knowledge_freshness_policies")}
        lookup = lambda name, ref: next(content for content in inventories[name]
                                        if _ref(content) == ref)
        candidate = api.bundle.KnowledgeBundleCandidate(
            classification_taxonomy=taxonomy, alias_mapping=alias,
            k1_record_set=records["k1_record_set"], k1_provenance=lookup(
                "knowledge_provenance_manifests", records["k1_record_set"].semantic_payload[
                    "knowledge_provenance"]), k1_governance=None, k1_freshness_policy=None,
            k2b_record_set=records["k2b_record_set"], k2b_provenance=lookup(
                "knowledge_provenance_manifests", records["k2b_record_set"].semantic_payload[
                    "knowledge_provenance"]), k2b_governance=None, k2b_freshness_policy=None,
            k3_portal_rule_set=records["k3_portal_rule_set"],
            k3_provenance=next(content for content in inventories["knowledge_provenance_manifests"]
                               if content.semantic_payload.get("provenance_kind") == "internal"),
            k4_record_set=records["k4_record_set"], k4_provenance=lookup(
                "knowledge_provenance_manifests", records["k4_record_set"].semantic_payload[
                    "knowledge_provenance"]), k4_governance=None, k4_freshness_policy=None)
        for slot in ("k1", "k2b", "k4"):
            provenance = getattr(candidate, f"{slot}_provenance").semantic_payload
            candidate = replace(candidate, **{
                f"{slot}_governance": lookup("source_governance_records",
                                              provenance["source_governance_record"]),
                f"{slot}_freshness_policy": lookup("knowledge_freshness_policies",
                                                   provenance["knowledge_freshness_policy"]),
            })
        if not api.bundle.validate_knowledge_bundle_dependencies(bundle, candidate):
            raise ValueError("KnowledgeBundle dependency mismatch")
        capability = helper._resolve_artifact(
            connection, api, manifest["portal_headers_v2_capability_disposition"])
        k2a = helper._resolve_artifact(connection, api, manifest["k2a_conformance_package"])
        api.adapter.validate_evidence_adapter_contract_set_dependencies(
            adapter, evidence_schema_registry=lineage.registry,
            capability_disposition=capability, k2a_conformance_package=k2a,
            k1_record_set=candidate.k1_record_set,
            k3_portal_rule_set=candidate.k3_portal_rule_set,
            k4_record_set=candidate.k4_record_set)
        return {"policy": policy, "taxonomy": taxonomy, "alias": alias,
                "adapter": adapter, "bundle": bundle, "runtime": runtime,
                "knowledge": candidate, "records": records, "inventories": inventories}
    except Exception as exc:
        raise helper.Blocked("BLOCKED_FOUNDATION_LINEAGE") from exc


def execute_pytest(repo: Path, run_dir: Path) -> tuple[int, str, str]:
    with tempfile.TemporaryDirectory(prefix="t04-pytest-", dir=run_dir) as temporary:
        path = Path(temporary)
        process_temp = path / "process-temp"
        process_temp.mkdir()
        command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                   "--basetemp", str(path / "pytest-temp"),
                   "tests/device_fingerprint_task04_t04"]
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(repo) + os.pathsep + environment.get("PYTHONPATH", "")
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYTEST_ADDOPTS"] = ""
        for name in ("TEMP", "TMP", "TMPDIR"):
            environment[name] = str(process_temp)
        try:
            result = subprocess.run(command, cwd=repo, env=environment,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, encoding="utf-8", errors="replace", timeout=1800)
            return result.returncode, result.stdout, subprocess.list2cmdline(command)
        except (OSError, subprocess.SubprocessError) as exc:
            return 1, f"T-04 pytest execution error: {type(exc).__name__}\n", subprocess.list2cmdline(command)


def execute_policy_vectors(api: SimpleNamespace, policy: Any) -> dict[str, Any]:
    """Call the candidate's own fusion-cell lookup for every admitted policy row."""
    payload = policy.semantic_payload
    _require(api.policy.make_classification_policy(payload) == policy,
             "Admitted ClassificationPolicy is noncanonical")
    rows = payload["cross_origin_fusion_matrix"]
    _require(len(rows) == 40, "Incomplete frozen policy matrix")
    vectors = []
    for row in rows:
        bits = tuple(row[name] for name in FUSION_INPUTS)
        observed = api.fusion._fusion_cell(payload, bits)
        vectors.append({"input_bits": dict(zip(FUSION_INPUTS, bits)),
                        "expected": {key: row[key] for key in (
                            "outcome", "record_supporting_contradiction", "support_cap")},
                        "observed": {key: observed[key] for key in (
                            "outcome", "record_supporting_contradiction", "support_cap")},
                        "status": "PASS" if observed == row else "FAIL"})
    _require(len({tuple(item["input_bits"].values()) for item in vectors}) == len(rows),
             "Duplicate fusion cell")
    try:
        api.fusion._fusion_cell(payload, (False, True, False, False, False, False, False))
    except api.fusion.DeviceFingerprintValidationError:
        undefined_rejected = True
    else:
        undefined_rejected = False
    return {"classification_policy": _ref(policy), "cell_count": len(rows),
            "vectors": vectors, "undefined_cell_rejected": undefined_rejected,
            "all_pass": undefined_rejected and all(item["status"] == "PASS" for item in vectors)}


def _result_trace(content: Any) -> dict[str, Any]:
    value = content.semantic_payload
    dimensions = {name: value[name] for name in (
        "platform_result", "device_class_result", "manufacturer_result", "model_result")}
    return {"classification_result": _ref(content),
            "global_classification_status": value["global_classification_status"],
            "dimension_results": {name: {
                "status": row["status"], "canonical_value_id": row["canonical_value_id"],
                "support_level": row["support_level"],
                "supporting_origin_groups": row["supporting_origin_groups"],
                "contradicting_origin_groups": row["contradicting_origin_groups"],
                "out_of_scope_taxon_references": row["out_of_scope_taxon_references"],
                "explanation_codes": row["explanation_codes"]}
                for name, row in dimensions.items()}}


def execute_matrix(api: SimpleNamespace) -> tuple[dict[str, Any], dict[str, Any]]:
    import pytest
    tests = _candidate_module(api.repo, "tests.device_fingerprint_task04_t04.test_fusion")
    t03 = _candidate_module(api.repo, "tests.device_fingerprint_task04_t03.test_origin_assessment")
    _candidate_module(api.repo, "research.device_fingerprint_fe1.fixtures")
    baseline = tests._base_from_source(t03._inputs())
    cases: dict[str, Any] = {}
    traces: dict[str, list[dict[str, Any]]] = {}
    retained: dict[str, dict[str, Any]] = {}
    fixture_module = Path(tests.__file__).resolve().relative_to(api.repo).as_posix()

    def record(case: str, inputs: Any, output: Any) -> None:
        _require(api.fusion.DeviceFingerprintFusionCore(inputs).fuse() == output,
                 "ClassificationResult reconstruction differs")
        value = output.semantic_payload
        exact = {
            "classification_policy": _ref(inputs.classification_policy),
            "knowledge_bundle": _ref(inputs.knowledge_bundle),
            "classifier_artifact_manifest": _ref(inputs.classifier_artifact_manifest),
            "evidence_snapshot_content": _ref(inputs.evidence_snapshot_content),
            "source_evaluability": _ref(inputs.source_evaluability),
        }
        _require(all(value[name] == reference for name, reference in exact.items()),
                 "ClassificationResult lineage mismatch")
        _require({item["artifact_id"] for item in value["origin_assessments"]} ==
                 {item.artifact_id for item in inputs.origin_assessments},
                 "ClassificationResult OriginAssessment set mismatch")
        retained[output.artifact_id] = _document(output)
        traces.setdefault(case, []).append(_result_trace(output))

    def check(case: str, calls: list[tuple[Any, tuple]], *, direct=None):
        fixture = {"case_id": case, "fixture_module": fixture_module,
                   "fixture_module_sha256": _sha256(Path(tests.__file__)),
                   "functions": [function.__name__ for function, _ in calls],
                   "baseline_policy": _ref(baseline.classification_policy)}
        original = tests.fuse_classification
        def recording_fuse(inputs):
            output = api.fusion.fuse_classification(inputs)
            record(case, inputs, output)
            return output
        try:
            tests.fuse_classification = recording_fuse
            for function, args in calls:
                function(*args)
            if direct is not None:
                direct(case)
            if not traces.get(case):
                recording_fuse(baseline)
            cases[case] = {"status": "PASS", "input_fixture_sha256": hashlib.sha256(
                _json_bytes(fixture)).hexdigest(), "trace": traces[case]}
        except Exception as exc:
            cases[case] = {"status": "FAIL", "input_fixture_sha256": hashlib.sha256(
                _json_bytes(fixture)).hexdigest(), "failure_type": type(exc).__name__,
                "failure": str(exc)[:500]}
        finally:
            tests.fuse_classification = original

    def with_monkeypatch(function, *args):
        with pytest.MonkeyPatch.context() as patch:
            function(*args, patch)

    def disabled_tcp(case):
        source = t03._inputs(evidence_rows=[t03._network_row("tcp")],
                             origin="tcp", tcp_disabled=True)
        snapshot = source.evidence_snapshot_content.semantic_payload
        _require(snapshot["origin_runtime_admission"]["tcp_state"] == "DISABLED",
                 "Controlled admission is not TCP disabled")
        _require(bool(snapshot["evidence_descriptors"]), "TCP evidence not audit-visible")
        fusion_input = tests._base_from_source(source)
        tcp = next(item for item in fusion_input.origin_assessments
                   if item.semantic_payload["origin_group"] == "tcp")
        _require("origin_runtime_disabled" in tcp.semantic_payload["explanation_codes"],
                 "TCP disable explanation missing")
        _require(all(row["internal_state"] == "no_claim" and not row["knowledge_refs"]
                     for row in tcp.semantic_payload["dimension_assessments"]),
                 "Disabled TCP emitted semantic claim")
        output = tests.fuse_classification(fusion_input)
        _require(output.semantic_payload["platform_result"]["status"] ==
                 "insufficient_evidence", "Disabled TCP claim entered fusion")
        traces[case][-1]["tcp_disabled"] = {
            "origin_runtime_admission": snapshot["origin_runtime_admission"],
            "audit_evidence_count": len(snapshot["evidence_descriptors"]),
            "tcp_origin_assessment": _ref(tcp)}

    def lineage_and_permutation(case):
        first = tests.fuse_classification(baseline)
        reverse = tests.fuse_classification(replace(
            baseline, origin_assessments=tuple(reversed(baseline.origin_assessments))))
        _require(first == reverse, "Origin permutation changed classification")
        for changed in (
            replace(baseline, origin_assessments=baseline.origin_assessments[:-1]),
            replace(baseline, origin_assessments=baseline.origin_assessments[:-1] +
                    (baseline.origin_assessments[0],)),
            replace(baseline, classification_policy=baseline.knowledge_bundle),
            replace(baseline, classification_taxonomy=baseline.alias_mapping),
            replace(baseline, evidence_adapter_contract_set=baseline.classification_taxonomy),
            replace(baseline, knowledge_bundle=baseline.classification_policy),
        ):
            try:
                api.fusion.DeviceFingerprintFusionCore(changed)
            except api.fusion.DeviceFingerprintValidationError:
                pass
            else:
                raise AssertionError("Malformed origin/lineage set accepted")
        traces[case][-1]["permutation_identity"] = _ref(first)

    check("T04-M01", [(tests.test_all_forty_policy_cells_are_looked_up_without_alternate_matrix,
                       (baseline,))])
    check("T04-M02", [(tests.test_strong_selection_and_independent_high_support, (baseline,)),
                      (tests.test_strong_disagreement_and_strong_internal_conflict, (baseline,))])
    check("T04-M03", [(tests.test_strong_supporting_contradiction_and_cap, (baseline,))])
    check("T04-M04", [(tests.test_supporting_agreement_disagreement_and_origin_unit,
                       (baseline,))])
    check("T04-M05", [(tests.test_supporting_internal_conflict_and_same_origin_retention,
                       (baseline,)),
                      (tests.test_strong_disagreement_and_strong_internal_conflict,
                       (baseline,)),
                      (lambda: with_monkeypatch(
                          tests.test_supporting_internal_conflict_uses_its_own_matrix_bit,
                          baseline), ())])
    check("T04-M06", [(lambda: with_monkeypatch(
        tests.test_same_origin_contradiction_is_not_cross_origin_matrix_bit,
        baseline), ())])
    check("T04-M07", [(tests.test_out_of_scope_supported_only_for_frozen_dimensions,
                       (baseline, "platform_family", "unmapped-platform", "supporting", "low")),
                      (tests.test_out_of_scope_supported_only_for_frozen_dimensions,
                       (baseline, "device_class", "unmapped-device", "strong", "medium")),
                      (tests.test_broad_unresolved_is_not_conflict_and_does_not_override_selection,
                       (baseline,))])
    check("T04-M08", [(tests.test_global_policy_statuses_from_constructed_dimensions,
                       (baseline,)),
                      (tests.test_result_exact_closed_shapes_and_global_policy, (baseline,)),
                      (tests.test_present_supported_dhcp_path_without_k1_claim_is_unknown_only_where_applicable,
                       ())])
    check("T04-M09", [], direct=disabled_tcp)
    check("T04-M10", [(tests.test_exact_six_origins_permutation_and_stable_result,
                       (baseline,)),
                      (tests.test_valid_policy_taxonomy_must_equal_valid_knowledge_bundle_taxonomy,
                       (baseline,)),
                      (tests.test_derivation_never_changes_outcome, (baseline,)),
                      (tests.test_origin_snapshot_evaluability_and_noncanonical_mismatch_rejected,
                       (baseline,))], direct=lineage_and_permutation)
    _require(set(cases) == set(CASE_IDS), "Incomplete T-04 scenario case set")
    return ({"cases": cases, "all_pass": all(row["status"] == "PASS" for row in cases.values()),
             "traces": traces},
            {"lineage_kind": "CONTROLLED_CANDIDATE_FIXTURES_NOT_FORMAL_ADMITTED_INPUTS",
             "classifier_artifact_manifest_fixture_not_T06_acceptance": True,
             "artifacts": [retained[key] for key in sorted(retained)]})


def _evidence_refs(run_dir: Path) -> list[dict[str, str]]:
    return [{"evidence_label": label, "file_sha256": _sha256(run_dir / filename),
             "media_type": media, "path_or_reference": filename}
            for label, filename, media in (
                ("t04-execution-evidence", "t04-execution-evidence.json", "application/json"),
                ("t04-artifacts", "t04-artifacts.json", "application/json"),
                ("t04-vector-results", "t04-vector-results.json", "application/json"),
                ("t04-pytest-log", "t04-pytest.log", "text/plain"))]


def _formal_outputs(run_dir: Path, api: SimpleNamespace, lineage: Any,
                    admitted: dict[str, Any], runner_sha: str, passed: bool):
    helper = _t01()
    inputs = [_ref(content) for content in (
        lineage.profile, admitted["policy"], admitted["taxonomy"], admitted["alias"],
        admitted["adapter"], admitted["bundle"], admitted["runtime"])]
    evidence = _evidence_refs(run_dir)
    identity = {"execution_id": str(uuid.uuid4()), "executor_kind": "TECHLEAD_GATE_TOOL",
                "repository_commit_sha": EXPECTED_COMMIT, "repository_tree_sha": EXPECTED_TREE,
                "procedure_or_test_suite_id": PROCEDURE,
                "environment_identity": helper._environment_identity(),
                "execution_artifact_sha256": runner_sha}
    proof = None
    if passed:
        proof = api.gate_proof.make_gate_proof_artifact({
            "proof_kind": PROOF_KIND, "source_gate_id": GATE_ID,
            "candidate_repository_commit_sha": EXPECTED_COMMIT,
            "candidate_repository_tree_sha": EXPECTED_TREE,
            "input_artifact_refs": inputs, "procedure_or_test_suite_id": PROCEDURE,
            "proof_execution_identity": identity,
            "canonical_result_summary":
                "T-04:pytest=PASS;scenarios=10/10 PASS;policy_vectors=PASS",
            "retained_evidence_refs": evidence})
    result = api.gate_result.make_gate_result_manifest({
        "gate_id": GATE_ID, "gate_contract_version": GATE_CONTRACT,
        "status": "PASS" if passed else "FAIL",
        "candidate_repository_commit_sha": EXPECTED_COMMIT,
        "candidate_repository_tree_sha": EXPECTED_TREE,
        "input_artifact_refs": inputs, "output_artifact_refs": [_ref(proof)] if proof else [],
        "retained_evidence_refs": evidence, "proof_execution_identity": identity,
        "trusted_time_inputs": {"foundation_knowledge_evaluation_at_utc": None,
                                "foundation_admission_evaluation_at_utc": None,
                                "knowledge_evaluation_at_utc": None},
        "decision_record_refs": []})
    if proof:
        helper._write_and_roundtrip(run_dir / "t04-gate-proof-artifact.json", proof,
                                    api.gate_proof.make_gate_proof_artifact,
                                    api.artifact.canonical_artifact_json)
    helper._write_and_roundtrip(run_dir / "t04-gate-result-manifest.json", result,
                                api.gate_result.make_gate_result_manifest,
                                api.artifact.canonical_artifact_json)
    (run_dir / "t04-summary.txt").write_text(
        f"GATE_EXECUTION_STATUS={'PASS' if passed else 'FAIL'}\n"
        f"GATE_RESULT_MANIFEST={result.artifact_id}\n"
        f"GATE_PROOF_ARTIFACT={proof.artifact_id if proof else 'NONE'}\n", encoding="utf-8")
    return proof, result


def _blocked(run_dir: Path, status: str) -> int:
    for name in ("t04-execution-evidence.json", "t04-artifacts.json", "t04-vector-results.json",
                 "t04-pytest.log", "t04-gate-proof-artifact.json",
                 "t04-gate-result-manifest.json"):
        (run_dir / name).unlink(missing_ok=True)
    (run_dir / "t04-summary.txt").write_text(
        f"GATE_EXECUTION_STATUS={status}\nFORMAL_GATE_RESULT_MANIFEST=NONE\n",
        encoding="utf-8")
    print(f"GATE_EXECUTION_STATUS={status}")
    return 2


def run_gate(repo: Path, foundation_db: Path, output_dir: Path) -> int:
    try:
        helper = _t01()
        repo = repo.resolve(strict=True)
    except RuntimeError:
        print("GATE_EXECUTION_STATUS=BLOCKED_HARDENED_HELPER_CHANGED")
        return 2
    except OSError:
        print("GATE_EXECUTION_STATUS=BLOCKED_CANDIDATE_IDENTITY")
        return 2
    runner_path = Path(__file__).resolve()
    runner_sha = _sha256(runner_path)
    output_dir = output_dir.resolve()
    if (output_dir.is_relative_to(repo) or output_dir.exists() and
            (not output_dir.is_dir() or any(output_dir.iterdir()))):
        print("GATE_EXECUTION_STATUS=BLOCKED_OUTPUT_DIR")
        return 2
    output_dir.mkdir(parents=True, exist_ok=True)
    run_dir = output_dir / str(uuid.uuid4())
    run_dir.mkdir(exist_ok=False)
    integrity = _integrity_block(runner_path, runner_sha)
    if integrity is not None:
        return _blocked(run_dir, integrity)
    connection = None
    try:
        helper.verify_repository(repo)
        original = helper.repository_filesystem_fingerprint(repo)
        api = load_api(repo)
        connection = helper.open_foundation_read_only(foundation_db)
        lineage = helper.verify_foundation(connection, api)
        admitted = resolve_admitted(connection, api, lineage)
        helper._require_repository_unchanged(repo, original)
    except (helper.Blocked, OSError) as exc:
        if connection is not None:
            connection.rollback()
            connection.close()
        return _blocked(run_dir, exc.status if isinstance(exc, helper.Blocked)
                        else "BLOCKED_CANDIDATE_IDENTITY")
    try:
        pytest_status, pytest_log, pytest_command = execute_pytest(repo, run_dir)
        (run_dir / "t04-pytest.log").write_text(pytest_log, encoding="utf-8")
        try:
            vectors = execute_policy_vectors(api, admitted["policy"])
            matrix, artifacts = execute_matrix(api)
        except helper.Blocked as exc:
            return _blocked(run_dir, exc.status)
        except Exception as exc:
            vectors = {"classification_policy": _ref(admitted["policy"]),
                       "vectors": [], "all_pass": False,
                       "execution_failure_type": type(exc).__name__}
            matrix, artifacts = {"cases": {}, "all_pass": False}, {"artifacts": []}
        helper._require_repository_unchanged(repo, original)
        evidence = {
            "candidate_repository_commit_sha": EXPECTED_COMMIT,
            "candidate_repository_tree_sha": EXPECTED_TREE,
            "runner_sha256": runner_sha, "hardened_helper_sha256": T01_HELPER_SHA256,
            "foundation_lineage": {name: _ref(content) for name, content in (
                ("FoundationAdmissionManifest", lineage.manifest),
                ("FoundationRuntimeProfile", lineage.profile),
                ("RuntimeProfileAdmissionManifest", lineage.admission),
                ("RuntimeProfileActivationRecord", lineage.activation),
                ("RuntimeProfileValidityRecord", lineage.validity),
                ("F-ADMIT GateResultManifest", lineage.gate_result),
                ("EvidenceSchemaRegistryContract", lineage.registry))},
            "admitted_formal_inputs": {name: _ref(admitted[name]) for name in (
                "policy", "taxonomy", "alias", "adapter", "bundle", "runtime")},
            "foundation_runtime_profile": _ref(lineage.profile),
            "pytest_command": pytest_command, "pytest_exit_status": pytest_status,
            "policy_matrix_cell_count": vectors.get("cell_count"),
            "scenario_matrix": matrix}
        (run_dir / "t04-execution-evidence.json").write_bytes(_json_bytes(evidence))
        (run_dir / "t04-artifacts.json").write_bytes(_json_bytes(artifacts))
        (run_dir / "t04-vector-results.json").write_bytes(_json_bytes(vectors))
        integrity = _integrity_block(runner_path, runner_sha)
        if integrity is not None:
            return _blocked(run_dir, integrity)
        vector_complete = (vectors.get("classification_policy") == _ref(admitted["policy"])
                           and vectors.get("cell_count") == 40
                           and len(vectors.get("vectors", ())) == 40
                           and vectors.get("all_pass") is True
                           and all(row.get("status") == "PASS"
                                   for row in vectors["vectors"]))
        matrix_complete = (set(matrix.get("cases", {})) == set(CASE_IDS)
                           and matrix.get("all_pass") is True
                           and all(row.get("status") == "PASS"
                                   for row in matrix["cases"].values()))
        passed = pytest_status == 0 and vector_complete and matrix_complete
        try:
            _formal_outputs(run_dir, api, lineage, admitted, runner_sha, passed)
        except Exception:
            return _blocked(run_dir, "BLOCKED_FORMAL_RESULT_CONSTRUCTION")
        helper._require_repository_unchanged(repo, original)
        integrity = _integrity_block(runner_path, runner_sha)
        if integrity is not None:
            return _blocked(run_dir, integrity)
        print(f"GATE_EXECUTION_STATUS={'PASS' if passed else 'FAIL'}")
        return 0 if passed else 1
    except helper.Blocked as exc:
        return _blocked(run_dir, exc.status)
    finally:
        connection.rollback()
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--foundation-control-db", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    return run_gate(args.repo, args.foundation_control_db, args.output_dir)


if __name__ == "__main__":
    raise SystemExit(main())
