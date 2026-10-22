"""External R14 T-06 ClassifierArtifactManifest construction harness.

Official execution is reserved for Owner and TechLead15. Import has no side effects.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import platform
import re
import sqlite3
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any


sys.dont_write_bytecode = True
EXPECTED_COMMIT = "8a39459be3ce7ed40e325736034245f0025cf249"
EXPECTED_TREE = "e2521f27c9f91978e381bce202ab3e3c83aa6dad"
T01_HELPER = Path(r"C:\CaptivPortal-Lab\tools\task04-t01-gate-a1-20261001.py")
T01_HELPER_SHA256 = "ac8a73606c8136fae3486ec63ee3ffe200852bbdbf53dc4b72144f369055f6b4"
REGISTRATION_SHA256 = "5dcbd6bb79157e046f1795f2c2789d4fbc799685a71a9dc4281dc058dd1809c6"
ARCHITECTURE_SHA256 = "115991601919fa1748ab47c613f5c6dff0a12101f4f47654ca1cebbfa7e696b5"
GATE_ID = "T-06"
GATE_CONTRACT = "R14-T-06-v1"
PROCEDURE = "T-06-exact-classifier-artifact-construction-v1"
MANIFEST_FIELDS = frozenset({
    "repository_commit_sha", "repository_tree_sha", "classification_engine_semver",
    "artifact_canonical_json_version", "evidence_canonical_json_compatibility_identity",
    "pure_core_contract_version", "classification_result_schema_version",
    "snapshot_contract_version", "adapter_implementation_identities",
    "k2a_matcher_implementation_version", "build_package_digest",
})
REGISTRATION = {
    "architecture_document_sha256": ARCHITECTURE_SHA256,
    "architecture_revision": "R14",
    "classification_engine_semver": "1.0.0",
    "pure_core_contract_version": "R14-PURE-CORE-V1",
    "registration_schema_version": 1,
    "registration_type": "R14T06ImplementationIdentityRegistrationV1",
    "repository_commit_sha": EXPECTED_COMMIT,
    "repository_tree_sha": EXPECTED_TREE,
    "scope": "TASK-04 T-06 ClassifierArtifactManifest implementation identity only",
}
BASE_TASK_KEYS = frozenset({("dhcp", 1), ("tcp_syn", 1), ("tcp_syn", 2),
                            ("tls_client", 1), ("quic_client", 1),
                            ("portal_headers", 1)})
_HELPER = None


class Blocked(RuntimeError):
    def __init__(self, status: str, detail: str = ""):
        super().__init__(f"{status}: {detail}" if detail else status)
        self.status = status
        self.detail = detail


class SemanticFailure(ValueError):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ref(content: Any) -> dict[str, str]:
    return {"artifact_id": content.artifact_id, "content_sha256": content.content_sha256}


def _document(content: Any) -> dict[str, Any]:
    return {"artifact_type": content.artifact_type,
            "artifact_schema_version": content.artifact_schema_version,
            "artifact_id": content.artifact_id,
            "content_sha256": content.content_sha256,
            "semantic_payload": content.semantic_payload}


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                       separators=(",", ":")) + "\n").encode("utf-8")


def _require(condition: bool, detail: str) -> None:
    if not condition:
        raise ValueError(detail)


def _t01():
    global _HELPER
    if not T01_HELPER.is_file() or _sha256(T01_HELPER) != T01_HELPER_SHA256:
        raise Blocked("BLOCKED_HARDENED_HELPER_CHANGED")
    if _HELPER is None:
        spec = importlib.util.spec_from_file_location("task04_t01_hardened_helper_t06", T01_HELPER)
        if spec is None or spec.loader is None:
            raise Blocked("BLOCKED_HARDENED_HELPER_CHANGED")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _HELPER = module
    return _HELPER


def _runner_guard(path: Path, expected_digest: str) -> None:
    if _sha256(path) != expected_digest:
        raise Blocked("BLOCKED_RUNNER_CHANGED")
    _t01()


def _validate_registration_fields(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != set(REGISTRATION):
        raise SemanticFailure("REGISTRATION_CONTENT_MISMATCH", "registration field set")
    for key, expected in REGISTRATION.items():
        if type(value[key]) is not type(expected) or value[key] != expected:
            raise SemanticFailure("REGISTRATION_CONTENT_MISMATCH", key)
    return value


def _validate_registration_bytes(raw: bytes, architecture_raw: bytes) -> dict[str, Any]:
    if hashlib.sha256(raw).hexdigest() != REGISTRATION_SHA256:
        raise SemanticFailure("REGISTRATION_DIGEST_MISMATCH", "registration SHA256")
    try:
        registration = _validate_registration_fields(json.loads(raw.decode("utf-8")))
    except SemanticFailure:
        raise
    except (UnicodeError, ValueError, TypeError) as exc:
        raise SemanticFailure("REGISTRATION_CONTENT_MISMATCH", "invalid JSON") from exc
    if hashlib.sha256(architecture_raw).hexdigest() != registration["architecture_document_sha256"]:
        raise SemanticFailure("ARCHITECTURE_DIGEST_MISMATCH", "R14 document SHA256")
    return registration


def validate_registration(path: Path, architecture_contract: Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise Blocked("BLOCKED_IMPLEMENTATION_IDENTITY_REGISTRATION", "registration unreadable") from exc
    try:
        architecture_raw = architecture_contract.read_bytes()
    except OSError as exc:
        raise Blocked("BLOCKED_ARCHITECTURE_IDENTITY", "R14 document unavailable") from exc
    registration = _validate_registration_bytes(raw, architecture_raw)
    return registration, raw


def _candidate_module(repo: Path, name: str):
    module = importlib.import_module(name)
    try:
        path = Path(module.__file__).resolve(strict=True)
        if not path.is_relative_to(repo.resolve(strict=True)):
            raise ValueError("outside repository")
    except (OSError, TypeError, ValueError) as exc:
        raise Blocked("BLOCKED_CANDIDATE_IDENTITY", name) from exc
    return module


def load_api(repo: Path) -> SimpleNamespace:
    base = _t01().load_repository_modules(repo)
    modules = {key: _candidate_module(repo, name) for key, name in {
        "adapter": "app.device_fingerprint.evidence_adapter_contracts",
        "origin": "app.device_fingerprint.origin_assessment",
        "fusion": "app.device_fingerprint.fusion",
        "p0f": "app.device_fingerprint.p0f_semantics",
        "bundle": "app.device_fingerprint.knowledge_bundle",
        "integrity": "app.device_fingerprint.payload_integrity",
    }.items()}
    return SimpleNamespace(**vars(base), **modules, repo=repo.resolve())


def resolve_foundation(connection: sqlite3.Connection, api: SimpleNamespace,
                       lineage: Any) -> dict[str, Any]:
    helper = _t01()
    try:
        manifest = lineage.manifest.semantic_payload
        adapter = helper._resolve_artifact(connection, api, manifest["evidence_adapter_contract_set"])
        knowledge = helper._resolve_artifact(connection, api, manifest["knowledge_bundle"])
        k2a = helper._resolve_artifact(connection, api, manifest["k2a_conformance_package"])
        disposition = helper._resolve_artifact(
            connection, api, manifest["portal_headers_v2_capability_disposition"])
        if (adapter.artifact_type != "EvidenceAdapterContractSet"
                or knowledge.artifact_type != "KnowledgeBundle"
                or k2a.artifact_type != "K2AConformancePackage"
                or disposition.artifact_type != "CapabilityDisposition"):
            raise ValueError("Foundation artifact type mismatch")
        bundle = knowledge.semantic_payload
        records = {name: helper._resolve_artifact(connection, api, bundle[name])
                   for name in ("k1_record_set", "k3_portal_rule_set", "k4_record_set")}
        if api.bundle.make_knowledge_bundle(bundle) != knowledge:
            raise ValueError("KnowledgeBundle noncanonical")
        if not api.adapter.validate_evidence_adapter_contract_set_dependencies(
                adapter, evidence_schema_registry=lineage.registry,
                capability_disposition=disposition, k2a_conformance_package=k2a,
                k1_record_set=records["k1_record_set"],
                k3_portal_rule_set=records["k3_portal_rule_set"],
                k4_record_set=records["k4_record_set"]):
            raise ValueError("Adapter dependencies invalid")
        return {"adapter": adapter, "knowledge": knowledge, "k2a": k2a,
                "disposition": disposition, "registry": lineage.registry}
    except Exception as exc:
        raise Blocked("BLOCKED_FOUNDATION_LINEAGE", "admitted adapter/schema dependencies") from exc


def _symbol_identity(repo: Path, module: Any, symbol: str, role: str | None = None) -> dict[str, str]:
    try:
        value = module
        for part in symbol.split("."):
            value = getattr(value, part)
        if not callable(value):
            raise ValueError("symbol not executable")
        path = Path(module.__file__).resolve(strict=True)
    except (AttributeError, OSError, TypeError, ValueError) as exc:
        raise SemanticFailure("IMPLEMENTATION_IDENTITY_UNRESOLVED", symbol) from exc
    try:
        relative = path.relative_to(repo.resolve(strict=True)).as_posix()
    except (OSError, ValueError) as exc:
        raise Blocked("BLOCKED_CANDIDATE_IDENTITY", symbol) from exc
    if path.suffix != ".py":
        raise SemanticFailure("IMPLEMENTATION_IDENTITY_UNRESOLVED", symbol)
    qualified = symbol if role is None else f"{symbol}/{role}"
    return {"implementation_id": f"python:{relative}:{qualified}",
            "implementation_digest": _sha256(path),
            "repository_relative_source_path": relative,
            "qualified_implementation_symbol_or_role": qualified}


def _registry_keys(payload: dict[str, Any]) -> dict[tuple[str, int], str]:
    rows = payload["schema_entries"]
    keys = {(row["source_kind"], row["feature_schema_version"]): row["schema_status"]
            for row in rows}
    _require(len(keys) == len(rows), "duplicate admitted schema")
    return keys


def build_inventory(api: SimpleNamespace, admitted: dict[str, Any],
                    *, reverse: bool = False) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    registry = admitted["registry"].semantic_payload
    disposition = admitted["disposition"].semantic_payload
    entries = admitted["adapter"].semantic_payload["adapter_entries"]
    admitted_v2 = disposition["status"] == "ADMITTED"
    expected = set(BASE_TASK_KEYS)
    if admitted_v2:
        expected.add(("portal_headers", 2))
    schemas = _registry_keys(registry)
    _require(set(schemas) == expected, "admitted registry coverage mismatch")
    task = [row for row in entries if row["adapter_kind"] == "TASK01_EVIDENCE"]
    mac = [row for row in entries if row["adapter_kind"] == "MAC_REGISTRY"]
    keys = [(row["source_kind"], row["feature_schema_version"]) for row in task]
    _require(len(keys) == len(set(keys)) and set(keys) == expected and len(mac) == 1,
             "adapter contract coverage mismatch")
    if reverse:
        task = list(reversed(task))
    inventory = []
    semantic = []
    for row in task:
        source, version = row["source_kind"], row["feature_schema_version"]
        mode = ("NON_FUSION_HANDLER" if (source, version) == ("tcp_syn", 1)
                else "OPTIONAL_IF_ADMITTED" if (source, version) == ("portal_headers", 2)
                else "FUSION")
        _require((schemas[(source, version)] == "KNOWN_NON_FUSION") ==
                 (mode == "NON_FUSION_HANDLER"), "fusion role mismatch")
        _require((row["legacy_current_role"] == "LEGACY_NON_FUSION") ==
                 (mode == "NON_FUSION_HANDLER"), "legacy role mismatch")
        if source in ("tls_client", "quic_client"):
            _require(row["quality_valid_behavior"].startswith("AUDIT_ONLY_"),
                     "TLS/QUIC semantic claim expansion")
        identity = _symbol_identity(api.repo, api.origin, "DeviceFingerprintOriginAssessmentBuilder.build",
                                    f"{source}/{version}/{mode}")
        semantic.append({"adapter_kind": "TASK01_EVIDENCE", "source_kind": source,
                         "feature_schema_version": version, "implementation_id": identity[
                             "implementation_id"], "implementation_digest": identity[
                                 "implementation_digest"], "mode": mode})
        inventory.append({**semantic[-1], **identity,
                          "adapter_contract_id": row["adapter_contract_id"],
                          "legacy_current_role": row["legacy_current_role"],
                          "semantic_projection_id": row["semantic_projection_id"],
                          "quality_valid_behavior": row["quality_valid_behavior"],
                          "admission_basis": "ADMITTED" if (source, version) ==
                          ("portal_headers", 2) else "REGISTRY_SUPPORTED"})
    _require(mac[0]["origin_group"] == "mac_registry", "MAC origin mismatch")
    identity = _symbol_identity(api.repo, api.origin, "DeviceFingerprintOriginAssessmentBuilder.build",
                                "mac_registry/FUSION")
    semantic.append({"adapter_kind": "MAC_REGISTRY", "origin_group": "mac_registry",
                     "implementation_id": identity["implementation_id"],
                     "implementation_digest": identity["implementation_digest"],
                     "mode": "FUSION"})
    inventory.append({**semantic[-1], **identity,
                      "adapter_contract_id": mac[0]["adapter_contract_id"],
                      "semantic_projection_id": mac[0]["semantic_projection_id"],
                      "admission_basis": "ADMITTED_MAC_REGISTRY"})
    if reverse:
        semantic.reverse()
        inventory.reverse()
    canonical = api.artifact.canonical_set(semantic, lambda row: (
        row["adapter_kind"], row.get("source_kind", "mac_registry"),
        row.get("feature_schema_version", row["implementation_id"])))
    _require(len(canonical) == len(expected) + 1, "duplicate implementation identity")
    return canonical, inventory


def _version_sources(api: SimpleNamespace, lineage: Any, admitted: dict[str, Any]) -> dict[str, Any]:
    try:
        fixture = _candidate_module(api.repo, "tests.device_fingerprint_task04_t04.test_fusion")
        origin_fixture = _candidate_module(api.repo,
                                           "tests.device_fingerprint_task04_t03.test_origin_assessment")
        controlled = fixture._base_from_source(origin_fixture._inputs())
        result = api.fusion.fuse_classification(controlled)
        if result.artifact_type != "ClassificationResult" or type(result.artifact_schema_version) is not int:
            raise ValueError("Classifier result schema not recoverable")
        result_version = result.artifact_schema_version
        snapshot_version = lineage.profile.semantic_payload["snapshot_contract_version"]
        if type(result_version) is not int or result_version < 1 or type(snapshot_version) is not int or snapshot_version < 1:
            raise ValueError("Non-positive contract version")
        if not isinstance(api.p0f.MATCHER_CONTRACT, str) or not api.p0f.MATCHER_CONTRACT:
            raise ValueError("Matcher version unavailable")
        if admitted["registry"].semantic_payload["evidence_canonical_json_version"] != "EvidenceCanonicalJsonV1":
            raise ValueError("Evidence canonical JSON mismatch")
        return {"classification_result_schema_version": result_version,
                "snapshot_contract_version": snapshot_version,
                "k2a_matcher_implementation_version": api.p0f.MATCHER_CONTRACT}
    except Blocked:
        raise
    except Exception as exc:
        raise SemanticFailure("IMPLEMENTATION_IDENTITY_UNRESOLVED",
                              type(exc).__name__) from exc


def verify_manifest_shape(api: SimpleNamespace, payload: Any) -> None:
    _require(isinstance(payload, dict) and set(payload) == MANIFEST_FIELDS,
             "ClassifierArtifactManifest field set")
    _require(payload["repository_commit_sha"] == EXPECTED_COMMIT and
             payload["repository_tree_sha"] == EXPECTED_TREE, "classifier repository identity")
    for field in ("classification_engine_semver", "artifact_canonical_json_version",
                  "evidence_canonical_json_compatibility_identity", "pure_core_contract_version",
                  "k2a_matcher_implementation_version"):
        _require(isinstance(payload[field], str) and bool(payload[field]), field)
    _require(payload["artifact_canonical_json_version"] == "ArtifactCanonicalJsonV1",
             "artifact canonical JSON version")
    for field in ("classification_result_schema_version", "snapshot_contract_version"):
        _require(type(payload[field]) is int and 1 <= payload[field] <= 2147483647, field)
    digest = payload["build_package_digest"]
    _require(digest is None or (isinstance(digest, str) and
             re.fullmatch(r"[0-9a-f]{64}", digest) is not None), "build digest")
    rows = payload["adapter_implementation_identities"]
    _require(isinstance(rows, list), "adapter identity SET")
    keys = []
    for row in rows:
        _require(isinstance(row, dict), "adapter identity row")
        kind = row.get("adapter_kind")
        if kind == "TASK01_EVIDENCE":
            _require(set(row) == {"adapter_kind", "source_kind", "feature_schema_version",
                                  "implementation_id", "implementation_digest", "mode"},
                     "TASK01_EVIDENCE tagged shape")
            _require(isinstance(row["source_kind"], str) and bool(row["source_kind"]) and
                     type(row["feature_schema_version"]) is int and
                     row["feature_schema_version"] > 0 and
                     row["mode"] in {"FUSION", "NON_FUSION_HANDLER", "OPTIONAL_IF_ADMITTED"},
                     "TASK01_EVIDENCE tagged values")
            keys.append((kind, row["source_kind"], row["feature_schema_version"]))
        elif kind == "MAC_REGISTRY":
            _require(set(row) == {"adapter_kind", "origin_group", "implementation_id",
                                  "implementation_digest", "mode"} and
                     row["origin_group"] == "mac_registry" and row["mode"] == "FUSION",
                     "MAC_REGISTRY tagged shape")
            keys.append((kind, "mac_registry", row["implementation_id"]))
        else:
            raise ValueError("unknown adapter identity kind")
        _require(isinstance(row["implementation_id"], str) and
                 row["implementation_id"].startswith("python:") and
                 isinstance(row["implementation_digest"], str) and
                 re.fullmatch(r"[0-9a-f]{64}", row["implementation_digest"]) is not None,
                 "implementation identity/digest")
    _require(len(keys) == len(set(keys)), "duplicate adapter identity tuple")
    _require(api.artifact.canonical_set(rows, lambda row: (
        row["adapter_kind"], row.get("source_kind", "mac_registry"),
        row.get("feature_schema_version", row["implementation_id"]))) == rows,
        "adapter identity SET ordering")


def construct_manifest(api: SimpleNamespace, lineage: Any, admitted: dict[str, Any],
                       registration: dict[str, Any], *, reverse: bool = False):
    adapters, inventory = build_inventory(api, admitted, reverse=reverse)
    versions = _version_sources(api, lineage, admitted)
    artifact_json = _symbol_identity(api.repo, api.artifact, "canonical_artifact_json")
    evidence_json = _symbol_identity(api.repo, api.validation, "canonical_json")
    k2a = _symbol_identity(api.repo, api.p0f, "match_request")
    payload = {
        "repository_commit_sha": EXPECTED_COMMIT,
        "repository_tree_sha": EXPECTED_TREE,
        "classification_engine_semver": registration["classification_engine_semver"],
        "artifact_canonical_json_version": "ArtifactCanonicalJsonV1",
        "evidence_canonical_json_compatibility_identity":
            f"EvidenceCanonicalJsonV1:{evidence_json['implementation_id']}:sha256:{evidence_json['implementation_digest']}",
        "pure_core_contract_version": registration["pure_core_contract_version"],
        "classification_result_schema_version": versions["classification_result_schema_version"],
        "snapshot_contract_version": versions["snapshot_contract_version"],
        "adapter_implementation_identities": adapters,
        "k2a_matcher_implementation_version": versions["k2a_matcher_implementation_version"],
        "build_package_digest": None,
    }
    verify_manifest_shape(api, payload)
    content = api.artifact.make_artifact_content("ClassifierArtifactManifest", payload)
    _require(content.artifact_schema_version == 1, "ClassifierArtifactManifest schema")
    reconstructed = api.artifact.make_artifact_content(content.artifact_type,
                                                       content.semantic_payload)
    _require(reconstructed == content, "ClassifierArtifactManifest round-trip")
    encoded = api.artifact.canonical_artifact_json(_document(content))
    _require(api.artifact.decode_artifact_json(encoded.decode("utf-8")) == _document(content),
             "ClassifierArtifactManifest canonical JSON round-trip")
    evidence = {
        "candidate_commit": EXPECTED_COMMIT, "candidate_tree": EXPECTED_TREE,
        "python_version": platform.python_version(), "python_platform": platform.platform(),
        "repository_identity_proof": {"commit": EXPECTED_COMMIT, "tree": EXPECTED_TREE},
        "build_package_digest_decision": {"value": None,
            "rationale": "All classifier-specific executed Python modules are repository files under the exact frozen Git tree; no generated/vendor-packaged classifier executable bytes are used."},
        "artifact_canonical_json_implementation": artifact_json,
        "evidence_canonical_json_compatibility": {
            **evidence_json, "contract_version": "EvidenceCanonicalJsonV1",
            "registry_contract": _ref(admitted["registry"]),
            "payload_integrity_module_sha256": _sha256(Path(api.integrity.__file__))},
        "version_sources": {"classification_engine_semver": "authoritative-registration",
            "pure_core_contract_version": "authoritative-registration",
            "classification_result_schema_version": {
                "value": versions["classification_result_schema_version"],
                "source": "candidate DeviceFingerprintFusionCore.fuse controlled ClassificationResult"},
            "snapshot_contract_version": {"value": versions["snapshot_contract_version"],
                "source": "accepted FoundationRuntimeProfile"}},
        "k2a_matcher": {**k2a, "version": versions["k2a_matcher_implementation_version"],
                        "k2a_conformance_package": _ref(admitted["k2a"])},
        "identity_registration": {key: registration[key] for key in REGISTRATION},
        "identity_registration_sha256": REGISTRATION_SHA256,
        "architecture_document_sha256": ARCHITECTURE_SHA256,
    }
    return content, inventory, evidence


def _write(path: Path, value: Any) -> None:
    path.write_bytes(_json_bytes(value))


def _evidence_refs(run_dir: Path) -> list[dict[str, str]]:
    supplied = "t06-supplied-implementation-identity-registration.json"
    registration = ("t06-supplied-implementation-identity-registration", supplied)
    if not (run_dir / supplied).is_file():
        registration = ("t06-implementation-identity-registration",
                        "t06-implementation-identity-registration.json")
    return [{"evidence_label": label, "file_sha256": _sha256(run_dir / filename),
             "media_type": "application/octet-stream" if filename == supplied else "application/json",
             "path_or_reference": filename}
            for label, filename in (
                registration,
                ("t06-build-identity", "t06-build-identity.json"),
                ("t06-implementation-inventory", "t06-implementation-inventory.json"))]


def _formal_result(run_dir: Path, api: SimpleNamespace, lineage: Any,
                   admitted: dict[str, Any], manifest: Any | None, runner_sha: str):
    inputs = [_ref(item) for item in (lineage.profile, admitted["registry"],
              admitted["adapter"], admitted["k2a"], admitted["disposition"]) ]
    identity = {"execution_id": str(uuid.uuid4()), "executor_kind": "TECHLEAD_GATE_TOOL",
                "repository_commit_sha": EXPECTED_COMMIT, "repository_tree_sha": EXPECTED_TREE,
                "procedure_or_test_suite_id": PROCEDURE,
                "environment_identity": _t01()._environment_identity(),
                "execution_artifact_sha256": runner_sha}
    result = api.gate_result.make_gate_result_manifest({
        "gate_id": GATE_ID, "gate_contract_version": GATE_CONTRACT,
        "status": "PASS" if manifest else "FAIL",
        "candidate_repository_commit_sha": EXPECTED_COMMIT,
        "candidate_repository_tree_sha": EXPECTED_TREE,
        "input_artifact_refs": inputs,
        "output_artifact_refs": [_ref(manifest)] if manifest else [],
        "retained_evidence_refs": _evidence_refs(run_dir),
        "proof_execution_identity": identity,
        "trusted_time_inputs": {"foundation_knowledge_evaluation_at_utc": None,
                                "foundation_admission_evaluation_at_utc": None,
                                "knowledge_evaluation_at_utc": None},
        "decision_record_refs": [],
    })
    _t01()._write_and_roundtrip(run_dir / "t06-gate-result-manifest.json", result,
                                api.gate_result.make_gate_result_manifest,
                                api.artifact.canonical_artifact_json)
    return result


def _blocked(run_dir: Path | None, status: str, detail: str = "") -> int:
    if run_dir is not None:
        for name in ("t06-manifest.json", "t06-gate-result-manifest.json"):
            (run_dir / name).unlink(missing_ok=True)
        (run_dir / "t06-summary.txt").write_text(
            f"GATE_EXECUTION_STATUS={status}\nUNRESOLVED={detail}\n"
            "GATE_RESULT_MANIFEST=NONE\n", encoding="utf-8")
    print(f"GATE_EXECUTION_STATUS={status}")
    if detail:
        print(f"UNRESOLVED={detail}")
    return 2


def run_gate(repo: Path, foundation_db: Path, registration_path: Path,
             architecture_contract: Path, output_dir: Path) -> int:
    run_dir = None
    connection = None
    original = None
    db_digest = None
    runner = Path(__file__).resolve()
    runner_sha = _sha256(runner)
    try:
        helper = _t01()
        repo = repo.resolve(strict=True)
        output_dir = output_dir.resolve()
        if (output_dir.is_relative_to(repo) or output_dir.exists() and
                (not output_dir.is_dir() or any(output_dir.iterdir()))):
            raise Blocked("BLOCKED_OUTPUT_DIR")
        output_dir.mkdir(parents=True, exist_ok=True)
        run_dir = output_dir / str(uuid.uuid4())
        run_dir.mkdir(exist_ok=False)
        _runner_guard(runner, runner_sha)
        helper.verify_repository(repo)
        original = helper.repository_filesystem_fingerprint(repo)
        try:
            db_digest = _sha256(foundation_db)
        except OSError as exc:
            raise Blocked("BLOCKED_FOUNDATION_LINEAGE", "Foundation DB unavailable") from exc
        api = load_api(repo)
        connection = helper.open_foundation_read_only(foundation_db)
        lineage = helper.verify_foundation(connection, api)
        admitted = resolve_foundation(connection, api, lineage)
        helper._require_repository_unchanged(repo, original)
        try:
            raw_registration = registration_path.read_bytes()
        except OSError as exc:
            raise Blocked("BLOCKED_IMPLEMENTATION_IDENTITY_REGISTRATION",
                          "registration unreadable") from exc
        try:
            raw_architecture = architecture_contract.read_bytes()
        except OSError as exc:
            raise Blocked("BLOCKED_ARCHITECTURE_IDENTITY",
                          "R14 document unavailable") from exc
        supplied_registration_sha = hashlib.sha256(raw_registration).hexdigest()
        supplied_architecture_sha = hashlib.sha256(raw_architecture).hexdigest()
        registration_name = ("t06-implementation-identity-registration.json"
                             if supplied_registration_sha == REGISTRATION_SHA256 else
                             "t06-supplied-implementation-identity-registration.json")
        (run_dir / registration_name).write_bytes(raw_registration)
        if _sha256(run_dir / registration_name) != supplied_registration_sha:
            raise Blocked("BLOCKED_IMPLEMENTATION_IDENTITY_REGISTRATION",
                          "retained registration changed")
        registration = None
        try:
            registration = _validate_registration_bytes(raw_registration, raw_architecture)
            first, inventory, evidence = construct_manifest(api, lineage, admitted, registration)
            second, reverse_inventory, _ = construct_manifest(
                api, lineage, admitted, registration, reverse=True)
            _require(first == second and first.artifact_id == second.artifact_id and
                     first.content_sha256 == second.content_sha256,
                     "ClassifierArtifactManifest nondeterministic")
            _require({item["implementation_id"] for item in inventory} ==
                     {item["implementation_id"] for item in reverse_inventory},
                     "Implementation inventory permutation mismatch")
            helper._write_and_roundtrip(
                run_dir / "t06-manifest.json", first,
                lambda payload: api.artifact.make_artifact_content(
                    "ClassifierArtifactManifest", payload),
                api.artifact.canonical_artifact_json)
            passed = True
        except Blocked:
            raise
        except Exception as exc:
            passed = False
            first = None
            inventory = []
            (run_dir / "t06-manifest.json").unlink(missing_ok=True)
            evidence = {"candidate_commit": EXPECTED_COMMIT, "candidate_tree": EXPECTED_TREE,
                        "expected_registration_sha256": REGISTRATION_SHA256,
                        "actual_registration_sha256": supplied_registration_sha,
                        "expected_architecture_sha256": ARCHITECTURE_SHA256,
                        "actual_architecture_sha256": supplied_architecture_sha,
                        "validation": "FAIL",
                        "validation_failure_code": exc.code if isinstance(
                            exc, SemanticFailure) else "SEMANTIC_MANIFEST_VERIFICATION_FAILURE",
                        "semantic_failure_type": type(exc).__name__,
                        "semantic_failure": str(exc)[:500],
                        "identity_registration": registration}
        _write(run_dir / "t06-build-identity.json", evidence)
        _write(run_dir / "t06-implementation-inventory.json", {"entries": inventory})
        _runner_guard(runner, runner_sha)
        helper._require_repository_unchanged(repo, original)
        if _sha256(foundation_db) != db_digest:
            raise Blocked("BLOCKED_FOUNDATION_MUTATED")
        if _sha256(registration_path) != supplied_registration_sha:
            raise Blocked("BLOCKED_IMPLEMENTATION_IDENTITY_REGISTRATION",
                          "registration changed during execution")
        if _sha256(architecture_contract) != supplied_architecture_sha:
            raise Blocked("BLOCKED_ARCHITECTURE_IDENTITY",
                          "R14 document changed during execution")
        try:
            result = _formal_result(run_dir, api, lineage, admitted, first, runner_sha)
        except Exception as exc:
            raise Blocked("BLOCKED_FORMAL_RESULT_CONSTRUCTION", type(exc).__name__) from exc
        helper._require_repository_unchanged(repo, original)
        _runner_guard(runner, runner_sha)
        if _sha256(foundation_db) != db_digest:
            raise Blocked("BLOCKED_FOUNDATION_MUTATED")
        (run_dir / "t06-summary.txt").write_text(
            f"GATE_EXECUTION_STATUS={'PASS' if passed else 'FAIL'}\n"
            f"CLASSIFIER_ARTIFACT_MANIFEST={first.artifact_id if first else 'NONE'}\n"
            f"GATE_RESULT_MANIFEST={result.artifact_id}\n", encoding="utf-8")
        print(f"GATE_EXECUTION_STATUS={'PASS' if passed else 'FAIL'}")
        return 0 if passed else 1
    except Blocked as exc:
        return _blocked(run_dir, exc.status, exc.detail)
    except Exception as exc:
        if "helper" in locals() and isinstance(exc, helper.Blocked):
            return _blocked(run_dir, exc.status)
        return _blocked(run_dir, "BLOCKED_CANDIDATE_IDENTITY", type(exc).__name__)
    finally:
        if connection is not None:
            connection.rollback()
            connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--foundation-control-db", type=Path, required=True)
    parser.add_argument("--implementation-identity-registration", type=Path, required=True)
    parser.add_argument("--architecture-contract", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args(argv)
    return run_gate(arguments.repo, arguments.foundation_control_db,
                    arguments.implementation_identity_registration,
                    arguments.architecture_contract, arguments.output_dir)


if __name__ == "__main__":
    raise SystemExit(main())