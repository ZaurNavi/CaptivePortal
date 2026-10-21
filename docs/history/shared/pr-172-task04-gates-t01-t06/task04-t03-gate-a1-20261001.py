"""External R14 T-03 acceptance harness. Official execution is Owner/TechLead-only.

Importing this module performs no repository, Foundation DB, or gate operation.
"""

from __future__ import annotations

import argparse
import copy
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
from pathlib import Path
from types import SimpleNamespace
from typing import Any


sys.dont_write_bytecode = True
EXPECTED_COMMIT = "8a39459be3ce7ed40e325736034245f0025cf249"
EXPECTED_TREE = "e2521f27c9f91978e381bce202ab3e3c83aa6dad"
GATE_ID = "T-03"
GATE_CONTRACT = "R14-T-03-v1"
PROCEDURE = "T-03-origin-assessment-execution-v1"
PROOF_KIND = "ORIGIN_ASSESSMENT_EXECUTION"
T01_HELPER_SHA256 = "ac8a73606c8136fae3486ec63ee3ffe200852bbdbf53dc4b72144f369055f6b4"
T01_HELPER = Path(r"C:\CaptivPortal-Lab\tools\task04-t01-gate-a1-20261001.py")
CASE_IDS = tuple(f"T03-M{number:02d}" for number in range(1, 13))
_HELPER = None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def _ref(content: Any) -> dict[str, str]:
    return {"artifact_id": content.artifact_id,
            "content_sha256": content.content_sha256}


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


def _runner_intact(path: Path, expected: str) -> bool:
    try:
        return _sha256(path) == expected and _sha256(T01_HELPER) == T01_HELPER_SHA256
    except OSError:
        return False


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
            raise ValueError("outside candidate repository")
    except (OSError, TypeError, ValueError) as exc:
        raise _t01().Blocked("BLOCKED_CANDIDATE_IDENTITY") from exc
    return module


def load_api(repo: Path) -> SimpleNamespace:
    base = _t01().load_repository_modules(repo)
    names = {
        "origin": "app.device_fingerprint.origin_assessment",
        "adapter": "app.device_fingerprint.evidence_adapter_contracts",
        "bundle": "app.device_fingerprint.knowledge_bundle",
        "k1": "app.device_fingerprint.knowledge_artifacts",
        "k3": "app.device_fingerprint.k3_portal_rules",
        "source": "app.device_fingerprint.source_evaluability",
    }
    modules = {key: _candidate_module(repo, name) for key, name in names.items()}
    return SimpleNamespace(**vars(base), **modules, repo=repo.resolve())


def resolve_admitted(connection: sqlite3.Connection, api: SimpleNamespace,
                     lineage: Any) -> dict[str, Any]:
    """Resolve exact initial F-ADMIT refs, then validate their complete dependency graph."""
    helper = _t01()
    try:
        manifest = lineage.manifest.semantic_payload
        adapter = helper._resolve_artifact(connection, api, manifest["evidence_adapter_contract_set"])
        bundle = helper._resolve_artifact(connection, api, manifest["knowledge_bundle"])
        if adapter.artifact_type != "EvidenceAdapterContractSet" or bundle.artifact_type != "KnowledgeBundle":
            raise ValueError("Incorrect admitted artifact types")
        payload = bundle.semantic_payload
        fields = ("classification_taxonomy", "alias_mapping", "k1_record_set",
                  "k2b_record_set", "k3_portal_rule_set", "k4_record_set")
        resolved = {name: helper._resolve_artifact(connection, api, payload[name]) for name in fields}
        if len({resolved[name].artifact_id for name in ("k1_record_set", "k2b_record_set",
                                                       "k4_record_set")}) != 3:
            raise ValueError("Knowledge slots collapse to one record set")
        inventories = {}
        for name in ("knowledge_provenance_manifests", "source_governance_records",
                     "knowledge_freshness_policies"):
            inventories[name] = [helper._resolve_artifact(connection, api, ref)
                                 for ref in payload[name]]
        by_ref = lambda name: {item.artifact_id: item for item in inventories[name]}
        def member(name, ref):
            return by_ref(name)[ref["artifact_id"]]
        candidate = api.bundle.KnowledgeBundleCandidate(
            classification_taxonomy=resolved["classification_taxonomy"],
            alias_mapping=resolved["alias_mapping"],
            k1_record_set=resolved["k1_record_set"],
            k1_provenance=member("knowledge_provenance_manifests",
                                 resolved["k1_record_set"].semantic_payload["knowledge_provenance"]),
            k1_governance=None, k1_freshness_policy=None,
            k2b_record_set=resolved["k2b_record_set"],
            k2b_provenance=member("knowledge_provenance_manifests",
                                  resolved["k2b_record_set"].semantic_payload["knowledge_provenance"]),
            k2b_governance=None, k2b_freshness_policy=None,
            k3_portal_rule_set=resolved["k3_portal_rule_set"],
            k3_provenance=None,
            k4_record_set=resolved["k4_record_set"],
            k4_provenance=member("knowledge_provenance_manifests",
                                 resolved["k4_record_set"].semantic_payload["knowledge_provenance"]),
            k4_governance=None, k4_freshness_policy=None,
        )
        from dataclasses import replace
        k3_provenance = next(item for item in inventories["knowledge_provenance_manifests"]
                             if item.semantic_payload.get("provenance_kind") == "internal")
        candidate = replace(candidate, k3_provenance=k3_provenance)
        for slot in ("k1", "k2b", "k4"):
            provenance = getattr(candidate, f"{slot}_provenance").semantic_payload
            candidate = replace(candidate, **{
                f"{slot}_governance": member("source_governance_records",
                                              provenance["source_governance_record"]),
                f"{slot}_freshness_policy": member("knowledge_freshness_policies",
                                                   provenance["knowledge_freshness_policy"]),
            })
        if not api.bundle.validate_knowledge_bundle_dependencies(bundle, candidate):
            raise ValueError("KnowledgeBundle dependency validation failed")
        if api.adapter.make_evidence_adapter_contract_set(adapter.semantic_payload) != adapter:
            raise ValueError("Noncanonical adapter")
        if adapter.semantic_payload["evidence_schema_registry"] != _ref(lineage.registry):
            raise ValueError("Adapter registry mismatch")
        capability = helper._resolve_artifact(
            connection, api, manifest["portal_headers_v2_capability_disposition"])
        k2a = helper._resolve_artifact(connection, api, manifest["k2a_conformance_package"])
        api.adapter.validate_evidence_adapter_contract_set_dependencies(
            adapter, evidence_schema_registry=lineage.registry,
            capability_disposition=capability, k2a_conformance_package=k2a,
            k1_record_set=candidate.k1_record_set,
            k3_portal_rule_set=candidate.k3_portal_rule_set,
            k4_record_set=candidate.k4_record_set)
        return {"adapter": adapter, "bundle": bundle, "candidate": candidate,
                "resolved": resolved, "inventories": inventories}
    except Exception as exc:
        raise helper.Blocked("BLOCKED_FOUNDATION_LINEAGE") from exc


def execute_pytest(repo: Path, run_dir: Path) -> tuple[int, str, str]:
    with tempfile.TemporaryDirectory(prefix="t03-pytest-", dir=run_dir) as temporary:
        temporary_path = Path(temporary)
        process_temp = temporary_path / "process-temp"
        process_temp.mkdir()
        command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                   "--basetemp", str(temporary_path / "pytest-temp"),
                   "tests/device_fingerprint_task04_t03"]
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
            return 1, f"T-03 pytest execution error: {type(exc).__name__}\n", subprocess.list2cmdline(command)


def _case_trace(inputs: Any, assessment: Any, origin: str) -> dict[str, Any]:
    payload = assessment.semantic_payload
    dimensions = payload["dimension_assessments"]
    return {"origin_group": origin, "origin_assessment": _ref(assessment),
            "evidence_snapshot_content": _ref(inputs.evidence_snapshot_content),
            "source_evaluability": _ref(inputs.source_evaluability),
            "knowledge_bundle": _ref(inputs.knowledge_bundle),
            "evidence_refs": payload["evidence_refs"],
            "knowledge_refs": payload["knowledge_refs"],
            "explanation_codes": payload["explanation_codes"],
            "dimension_internal_states": {row["dimension_name"]: row["internal_state"]
                                          for row in dimensions},
            "claim_strengths": {row["dimension_name"]: row["effective_claim_strength"]
                                for row in dimensions},
            "conflict_strengths": {row["dimension_name"]: row["conflict_strength"]
                                   for row in dimensions}}


def _m12_no_fabricated_inputs(tests: Any, api: SimpleNamespace) -> None:
    from dataclasses import replace
    inputs = tests._inputs(evidence_rows=[tests._dhcp_row()])
    output = api.origin.DeviceFingerprintOriginAssessmentBuilder(inputs).build("dhcp")
    kwargs = tests._constructor_kwargs(inputs)
    for field, value in (("source_kind", "portal_headers"),
                         ("feature_schema_version", 99),
                         ("quality_state", "degraded")):
        changed = tests._with_descriptor(inputs, **{field: value})
        changed_kwargs = tests._constructor_kwargs(changed)
        try:
            api.origin.make_origin_assessment(output.semantic_payload, **changed_kwargs)
        except api.origin.DeviceFingerprintValidationError:
            pass
        else:
            raise AssertionError(f"Fabricated {field} accepted")
    source_payload = inputs.source_evaluability.semantic_payload
    source_payload["source_entries"] = []
    altered_source = api.artifact.make_artifact_content("SourceEvaluability", source_payload)
    try:
        api.origin.make_origin_assessment(
            output.semantic_payload, **{**kwargs, "source_evaluability": altered_source})
    except api.origin.DeviceFingerprintValidationError:
        pass
    else:
        raise AssertionError("Fabricated coverage accepted")


def execute_matrix(api: SimpleNamespace) -> tuple[dict[str, Any], dict[str, Any]]:
    """Exercise the candidate's own controlled fixtures and real T-01/T-02/T-03 builders."""
    tests = _candidate_module(api.repo, "tests.device_fingerprint_task04_t03.test_origin_assessment")
    t01_tests = _candidate_module(api.repo, "tests.device_fingerprint_task04_t01.test_snapshot_service")
    _candidate_module(api.repo, "research.device_fingerprint_fe1.fixtures")
    cases: dict[str, Any] = {}
    retained: dict[str, dict[str, Any]] = {}
    traces: dict[str, Any] = {}
    fixture_source = Path(tests.__file__).resolve().relative_to(api.repo).as_posix()

    def retain(inputs: Any, output: Any, origin: str, case_id: str):
        rebuilt = api.origin.make_origin_assessment(
            output.semantic_payload, evidence_snapshot_content=inputs.evidence_snapshot_content,
            source_evaluability=inputs.source_evaluability,
            evidence_adapter_contract_set=inputs.evidence_adapter_contract_set,
            knowledge_bundle=inputs.knowledge_bundle, knowledge=inputs.knowledge)
        _require(rebuilt == output, "OriginAssessment round-trip mismatch")
        for content in (inputs.evidence_snapshot_content, inputs.source_evaluability, output,
                        inputs.knowledge_bundle, inputs.knowledge.k1_record_set,
                        inputs.knowledge.k2b_record_set, inputs.knowledge.k3_portal_rule_set,
                        inputs.knowledge.k4_record_set):
            retained[content.artifact_id] = _document(content)
        traces.setdefault(case_id, []).append(_case_trace(inputs, output, origin))

    def capture(case_id: str, origin: str = "dhcp", rows=(),
                knowledge_time="2026-09-22T22:30:34.464Z", mac=None):
        kwargs = {"evidence_rows": list(rows),
                  "origin": "dhcp" if origin == "mac_registry" else origin,
                  "knowledge_time": knowledge_time}
        if mac is not None:
            kwargs["mac"] = mac
        inputs = tests._inputs(**kwargs)
        output = api.origin.DeviceFingerprintOriginAssessmentBuilder(inputs).build(origin)
        retain(inputs, output, origin, case_id)
        return inputs, output

    def check(case_id: str, functions: list[tuple[Any, tuple]], captures: list[tuple] | None = None):
        material = {"case_id": case_id, "fixture_module": fixture_source,
                    "fixture_module_sha256": _sha256(Path(tests.__file__)),
                    "functions": [function.__name__ for function, _ in functions],
                    "capture_spec": captures or []}
        fixture_sha = hashlib.sha256(_json_bytes(material)).hexdigest()
        original_builder = tests.DeviceFingerprintOriginAssessmentBuilder
        class RecordingBuilder(original_builder):
            def build(self, origin):
                output = super().build(origin)
                retain(self._inputs, output, origin, case_id)
                return output
        try:
            tests.DeviceFingerprintOriginAssessmentBuilder = RecordingBuilder
            for function, args in functions:
                function(*args)
            for spec in captures or []:
                capture(case_id, *spec)
            cases[case_id] = {"status": "PASS", "input_fixture_sha256": fixture_sha,
                              "trace": traces.get(case_id, [])}
        except Exception as exc:
            cases[case_id] = {"status": "FAIL", "input_fixture_sha256": fixture_sha,
                              "failure_type": type(exc).__name__, "failure": str(exc)[:500]}
        finally:
            tests.DeviceFingerprintOriginAssessmentBuilder = original_builder

    # Each matrix cell invokes concrete candidate regression fixtures; capture() additionally
    # retains complete canonical artifacts from the same candidate execution path.
    check("T03-M01", [(tests.test_k1_complete_candidate_enumeration_ambiguity_and_permutation, ()),
                      (tests.test_k1_alternatives_are_ambiguous_only_for_differing_dimension, ())],
          [("dhcp",)])
    check("T03-M02", [(tests.test_origin_artifact_input_order_permutation_keeps_identity, ()),
                      (tests.test_dhcp_semantic_outcome_dedup_unions_refs_across_different_payloads, ())],
          [("dhcp", [tests._dhcp_row(1), tests._dhcp_row(2)])])
    check("T03-M03", [(tests.test_k1_no_match_is_empty_and_row_order_is_identity_stable, ())],
          [("dhcp",)])
    check("T03-M04", [(tests.test_portal_k3_uses_only_normalized_provenance_and_no_mobile_heuristic, ()),
                      (tests.test_identical_semantic_repetition_never_creates_another_vote, ()),
                      (tests.test_portal_same_semantic_repetition_unions_refs_canonically,
                       (1, "k3.vector.platform.android.sec_ch_ua_platform.v1", "platform_family", "android"))],
          [("portal", [tests._portal_row(1), tests._portal_row(2)])])
    check("T03-M05", [(tests.test_partial_quality_requires_each_admitted_dimension_field, ()),
                      (tests.test_partial_quality_caps_an_otherwise_strong_admitted_claim, ()),
                      (tests.test_portal_quality_semantics, ("valid", True)),
                      (tests.test_portal_quality_semantics, ("partial", True)),
                      (tests.test_portal_quality_semantics, ("degraded", False))],
          [("portal", [tests._portal_row(quality="partial")])])
    check("T03-M06", [(tests.test_unsupported_future_schema_is_audit_visible_without_claim, ())],
          [("portal", [tests._portal_row(version=99)])])
    check("T03-M07", [(tests.test_expired_external_k1_emits_no_new_claim, ()),
                      (tests.test_negative_knowledge_age_fails_closed, ())],
          [("dhcp", [tests._dhcp_row()], "2030-01-01T00:00:00.000Z")])
    check("T03-M08", [(tests.test_legacy_tcp_and_ja4_are_audit_only,
                       ("tls", "ja4_no_semantic_claim")),
                      (tests.test_legacy_tcp_and_ja4_are_audit_only,
                       ("quic", "ja4_no_semantic_claim"))],
          [("tls", [tests._network_row("tls")]),
           ("quic", [tests._network_row("quic")])])
    check("T03-M09", [(tests.test_same_origin_strength_matrix,
                       (("android", "android"), (), "resolved", None)),
                      (tests.test_same_origin_strength_matrix,
                       (("android", "ios"), (), "conflicting", "strong")),
                      (tests.test_same_origin_strength_matrix,
                       (("android",), ("ios",), "resolved", "supporting")),
                      (tests.test_same_origin_strength_matrix,
                       ((), ("android", "ios"), "conflicting", "supporting"))],
          [("dhcp", [tests._dhcp_row()])])
    check("T03-M10", [(tests.test_mac_registry_local_admin_and_raw_assignment_not_manufacturer, ())],
          [("mac_registry",), ("mac_registry", [], "2026-09-22T22:30:34.464Z",
                              "00:11:22:33:44:55")])
    check("T03-M11", [(tests.test_mac_registry_longest_prefix_and_dhcp_origin_purity, ()),
                      (tests.test_mac_registry_explicit_admitted_org_mapping_only, ())],
          [("mac_registry", [], "2026-09-22T22:30:34.464Z", "00:11:22:33:44:55")])
    check("T03-M12", [(tests.test_exact_schema_and_pinned_snapshot_evaluability_refs, ()),
                      (tests.test_exact_evidence_and_knowledge_reference_lineage_is_enforced, ()),
                      (tests.test_materialization_and_source_identity_mismatch_fail_closed, ()),
                      (tests.test_closed_dimension_validator_rejects_no_claim_with_candidate_and_unbacked_selection, ()),
                      (tests.test_closed_dimension_validator_rejects_conflict_and_derivation_mismatch, ()),
                      (_m12_no_fabricated_inputs, (tests, api))],
          [("dhcp", [tests._dhcp_row()])])
    _require(set(cases) == set(CASE_IDS), "T-03 matrix case set mismatch")
    return ({"cases": cases, "all_pass": all(row["status"] == "PASS" for row in cases.values()),
             "traces": traces},
            {"lineage_kind": "CONTROLLED_CANDIDATE_FIXTURES_NOT_FORMAL_ADMITTED_INPUTS",
             "artifacts": [retained[key] for key in sorted(retained)]})


def _evidence_refs(run_dir: Path) -> list[dict[str, str]]:
    return [{"evidence_label": label, "file_sha256": _sha256(run_dir / filename),
             "media_type": media, "path_or_reference": filename}
            for label, filename, media in (
                ("t03-execution-evidence", "t03-execution-evidence.json", "application/json"),
                ("t03-artifacts", "t03-artifacts.json", "application/json"),
                ("t03-pytest-log", "t03-pytest.log", "text/plain"))]


def _formal_outputs(run_dir: Path, api: SimpleNamespace, lineage: Any,
                    admitted: dict[str, Any], runner_sha: str, passed: bool):
    helper = _t01()
    resolved = admitted["resolved"]
    inputs = [_ref(content) for content in (lineage.profile, admitted["adapter"],
              admitted["bundle"], resolved["k1_record_set"], resolved["k2b_record_set"],
              resolved["k3_portal_rule_set"], resolved["k4_record_set"])]
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
            "canonical_result_summary": "T-03:pytest=PASS;matrix=12/12 PASS",
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
        helper._write_and_roundtrip(run_dir / "t03-gate-proof-artifact.json", proof,
                                    api.gate_proof.make_gate_proof_artifact,
                                    api.artifact.canonical_artifact_json)
    helper._write_and_roundtrip(run_dir / "t03-gate-result-manifest.json", result,
                                api.gate_result.make_gate_result_manifest,
                                api.artifact.canonical_artifact_json)
    (run_dir / "t03-summary.txt").write_text(
        f"GATE_EXECUTION_STATUS={'PASS' if passed else 'FAIL'}\n"
        f"GATE_RESULT_MANIFEST={result.artifact_id}\n"
        f"GATE_PROOF_ARTIFACT={proof.artifact_id if proof else 'NONE'}\n", encoding="utf-8")
    return proof, result


def _blocked(run_dir: Path, status: str) -> int:
    for name in ("t03-execution-evidence.json", "t03-artifacts.json", "t03-pytest.log",
                 "t03-gate-proof-artifact.json", "t03-gate-result-manifest.json"):
        (run_dir / name).unlink(missing_ok=True)
    (run_dir / "t03-summary.txt").write_text(
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
        (run_dir / "t03-pytest.log").write_text(pytest_log, encoding="utf-8")
        try:
            matrix, artifacts = execute_matrix(api)
        except helper.Blocked as exc:
            return _blocked(run_dir, exc.status)
        except Exception as exc:
            matrix, artifacts = {"cases": {}, "all_pass": False,
                                 "execution_failure_type": type(exc).__name__}, {"artifacts": []}
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
            "admitted_formal_inputs": {
                "EvidenceAdapterContractSet": _ref(admitted["adapter"]),
                "KnowledgeBundle": _ref(admitted["bundle"]),
                **{name: _ref(content) for name, content in admitted["resolved"].items()}},
            "admitted_transitive_inventory": {
                name: [_ref(content) for content in contents]
                for name, contents in admitted["inventories"].items()},
            "pytest_command": pytest_command, "pytest_exit_status": pytest_status,
            "matrix": matrix}
        (run_dir / "t03-execution-evidence.json").write_bytes(_json_bytes(evidence))
        (run_dir / "t03-artifacts.json").write_bytes(_json_bytes(artifacts))
        integrity = _integrity_block(runner_path, runner_sha)
        if integrity is not None:
            return _blocked(run_dir, integrity)
        passed = pytest_status == 0 and matrix["all_pass"]
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