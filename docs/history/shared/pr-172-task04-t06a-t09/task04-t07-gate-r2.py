"""External T-07 acceptance harness. Importing this module never runs the gate."""

from __future__ import annotations

import argparse
from dataclasses import fields, replace
from datetime import timedelta
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from types import SimpleNamespace
import uuid
from typing import Any

sys.dont_write_bytecode = True

COMMIT = "74f7c7add401e5fec0469d49770466c2747c03cf"
TREE = "7e93a4863909c3e807a9d8239924d13e0a0d7f71"
PROFILE_ID = "ClassificationRuntimeProfile:v1:sha256:75f9d0107d852d58899e869dc9c64c7b311f7423930c60b828a0aa30d2f4c3ff"
T06A_RESULT_ID = "GateResultManifest:v1:sha256:9bdcc53e59104010202e2aa1eb44b49c348eda27eed95061d66322de4ed95735"
T06A_PROOF_ID = "GateProofArtifact:v1:sha256:00bbf679be6e35d48b93d302ff7439065df78cdac507d6cc8e15f4f1876a35b0"
T01_PATH = Path(__file__).resolve().parents[1] / "t01" / "task04-t01-gate-rebind-20260929.py"
T01_SHA = "ee17cbd9a1c6e8e5ac510559ca0d6a21768a26fbb90ae98cb1ed4550d0446668"
T06A_PATH = Path(__file__).resolve().parents[1] / "t06a" / "task04-t06a-gate-rebind-20260929.py"
T06A_SHA = "667bc5777ef2d9c6b6f1277c53e09b9dc6e3c4a8d23b42cfd0867ba19647d814"
T06_MANIFEST_PATH = (Path(__file__).resolve().parents[1] / "t06" /
    "official-rebind-20260929-T06-01" / "e5514fd4-27b8-493e-9544-beb70d168c1a" /
    "t06-manifest.json")
GATE_ID = "T-07"
CONTRACT = "R14-T-07-v1"
PROOF_KIND = "CLASSIFICATION_AUDIT_PERSISTENCE"
PROCEDURE = "T-07-classification-persistence-audit-replay-gc-v1"
AUDIT_CLOSURE_CONTRACT = "R14-T07-BOUNDED-SECTION120-V1"
HISTORICAL_MISSING_ARTIFACT = (
    "CanonicalKnowledgeRecordSet:v1:sha256:"
    "850c808a6c2f2895c06b349d423db80936f4eed8a26ced745b8503019983c2d2"
)
CASES = tuple(f"T07-M{i:02}" for i in range(1, 13))
RETAINED = (
    "t07-execution-evidence.json", "t07-persistence-core.json",
    "t07-classification-db-inventory.json", "t07-audit-replay-report.json",
    "t07-gc-report.json", "t07-production-admission-guard.json",
    "t07-pytest.log", "t07-summary.txt",
)
T06A_FILES = (
    "t06a-classification-runtime-profile.json", "t06a-gate-proof-artifact.json",
    "t06a-gate-result-manifest.json", "t06a-compatibility-report.json",
    "t06a-dependency-graph.json", "t06a-execution-evidence.json",
)
_T01 = None
_T06A = None


class Blocked(RuntimeError):
    def __init__(self, code: str, detail: str = ""):
        self.code, self.detail = code, detail
        super().__init__(f"{code}: {detail}" if detail else code)


class SemanticFailure(RuntimeError):
    def __init__(self, code: str, detail: str = ""):
        self.code, self.detail = code, detail
        super().__init__(f"{code}: {detail}" if detail else code)


def require(condition: bool, code: str, detail: str = "") -> None:
    if not condition:
        raise SemanticFailure(code, detail)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ref(item: Any) -> dict[str, str]:
    return {"artifact_id": item.artifact_id, "content_sha256": item.content_sha256}


def document(item: Any) -> dict[str, Any]:
    return {"artifact_type": item.artifact_type,
            "artifact_schema_version": item.artifact_schema_version,
            "artifact_id": item.artifact_id, "content_sha256": item.content_sha256,
            "semantic_payload": item.semantic_payload}


def write_json(path: Path, value: Any) -> None:
    path.write_bytes((json.dumps(value, sort_keys=True, ensure_ascii=True,
                                 allow_nan=False, separators=(",", ":")) + "\n").encode())


def _pinned(path: Path, digest: str, name: str):
    if not path.is_file() or sha(path) != digest:
        raise Blocked("BLOCKED_HARDENED_HELPER_CHANGED", str(path))
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise Blocked("BLOCKED_HARDENED_HELPER_CHANGED", str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def helpers():
    global _T01, _T06A
    if _T01 is None:
        _T01 = _pinned(T01_PATH, T01_SHA, "t07_pinned_t01")
    elif sha(T01_PATH) != T01_SHA:
        raise Blocked("BLOCKED_HARDENED_HELPER_CHANGED", "T-01")
    if _T06A is None:
        _T06A = _pinned(T06A_PATH, T06A_SHA, "t07_pinned_t06a")
    elif sha(T06A_PATH) != T06A_SHA:
        raise Blocked("BLOCKED_HARDENED_HELPER_CHANGED", "T-06A")
    return _T01, _T06A


def candidate(repo: Path, name: str):
    module = importlib.import_module(name)
    if not Path(module.__file__).resolve(strict=True).is_relative_to(repo):
        raise Blocked("BLOCKED_CANDIDATE_IDENTITY", name)
    return module


def api_for(repo: Path, t06a: Any) -> SimpleNamespace:
    base = t06a.load_api(repo)
    extra = {key: candidate(repo, name) for key, name in {
        "assembly": "app.device_fingerprint.request_assembly",
        "control": "app.device_fingerprint.control_plane_store",
        "retention": "app.device_fingerprint.classification_retention_policy",
        "graph": "app.device_fingerprint.artifact_dependency_graph",
        "snapshot_artifacts": "app.device_fingerprint.snapshot_artifacts",
        "persistence": "app.device_fingerprint.classification_persistence",
        "read": "app.device_fingerprint.read_service",
        "persistence_fixture": "tests.device_fingerprint_task04_04d_persistence.test_classification_persistence",
    }.items()}
    return SimpleNamespace(**(vars(base) | extra))


def canonical_content(path: Path, api: Any, builder: Any, expected_id: str):
    try:
        raw = path.read_bytes()
        value = api.artifact.decode_artifact_json(raw.decode("utf-8"))
        if set(value) != {"artifact_type", "artifact_schema_version", "artifact_id",
                          "content_sha256", "semantic_payload"}:
            raise ValueError("document shape")
        built = builder(value["semantic_payload"])
        canonical = api.artifact.canonical_artifact_json(value)
        if (document(built) != value or built.artifact_id != expected_id or
                raw not in (canonical, canonical + b"\n")):
            raise ValueError("identity or canonical bytes")
        return built
    except Exception as exc:
        raise Blocked("BLOCKED_T06A_PREREQUISITE", path.name) from exc


def verify_t06a(run_dir: Path, api: Any):
    if not all((run_dir / name).is_file() for name in T06A_FILES):
        raise Blocked("BLOCKED_T06A_PREREQUISITE", "missing input")
    profile = canonical_content(run_dir / T06A_FILES[0], api,
                                api.profiles.make_classification_runtime_profile, PROFILE_ID)
    proof = canonical_content(run_dir / T06A_FILES[1], api,
                              api.gate_proof.make_gate_proof_artifact, T06A_PROOF_ID)
    result = canonical_content(run_dir / T06A_FILES[2], api,
                               api.gate_result.make_gate_result_manifest, T06A_RESULT_ID)
    payload = result.semantic_payload
    expected_outputs = sorted([ref(profile), ref(proof)], key=lambda row: row["artifact_id"])
    if (payload["gate_id"] != "T-06A" or payload["gate_contract_version"] != "R14-T-06A-v1"
            or payload["status"] != "PASS" or payload["candidate_repository_commit_sha"] != COMMIT
            or payload["candidate_repository_tree_sha"] != TREE
            or sorted(payload["output_artifact_refs"], key=lambda row: row["artifact_id"]) != expected_outputs
            or proof.semantic_payload["source_gate_id"] != "T-06A"
            or proof.semantic_payload["proof_kind"] != "CLASSIFICATION_PROFILE_COMPATIBILITY"
            or proof.semantic_payload["candidate_repository_commit_sha"] != COMMIT
            or proof.semantic_payload["candidate_repository_tree_sha"] != TREE
            or proof.semantic_payload["proof_execution_identity"]["execution_artifact_sha256"] != T06A_SHA):
        raise Blocked("BLOCKED_T06A_PREREQUISITE", "result/proof contract")
    try:
        for row in payload["retained_evidence_refs"]:
            name = row["path_or_reference"]
            if Path(name).name != name or name not in T06A_FILES or sha(run_dir / name) != row["file_sha256"]:
                raise ValueError("retained evidence")
        execution = json.loads((run_dir / "t06a-execution-evidence.json").read_text())
        if (execution["runner_sha256"] != T06A_SHA or execution["profile"] != ref(profile)
                or execution["t01_helper_sha256"] != T01_SHA):
            raise ValueError("execution identity")
    except Exception as exc:
        raise Blocked("BLOCKED_T06A_PREREQUISITE", "evidence") from exc
    return profile, proof, result


def resolve_retention(connection, api, helper, lineage):
    try:
        policy_ref = lineage.manifest.semantic_payload["classification_retention_policy"]
        policy = helper._resolve_artifact(connection, api, policy_ref)
        if (policy.artifact_type != "ClassificationRetentionPolicy" or
                api.retention.make_classification_retention_policy(policy.semantic_payload) != policy):
            raise ValueError("retention contract")
        return policy
    except Exception as exc:
        raise Blocked("BLOCKED_RETENTION_POLICY", type(exc).__name__) from exc


def copy_sqlite_readonly(source: Path, target: Path) -> None:
    if target.exists():
        raise Blocked("BLOCKED_OUTPUT_DIR", "database copy exists")
    original = None
    destination = None
    try:
        original = sqlite3.connect(f"{source.resolve(strict=True).as_uri()}?mode=ro", uri=True)
        original.execute("PRAGMA query_only=ON")
        destination = sqlite3.connect(target)
        original.backup(destination)
    except (sqlite3.Error, OSError) as exc:
        raise Blocked("BLOCKED_INPUT_DATABASE", str(source)) from exc
    finally:
        if destination is not None:
            destination.close()
        if original is not None:
            original.close()


class ImmutableOverlay:
    """Disposable accepted Foundation store plus external immutable classifier ref."""

    def __init__(self, control, classifier):
        self.control = control
        self.extra = {classifier.artifact_id: classifier}
        self.pin_calls: list[str] = []

    def load_artifact(self, artifact_id, expected_content_sha256=None):
        if artifact_id in self.extra:
            item = self.extra[artifact_id]
            if expected_content_sha256 is not None and item.content_sha256 != expected_content_sha256:
                raise ValueError("immutable overlay digest mismatch")
            return item
        return self.control.load_artifact(artifact_id, expected_content_sha256)

    def pin_active_profile(self, kind):
        self.pin_calls.append(kind)
        raise SemanticFailure("PRE_ACCEPTANCE_POINTER_READ", kind)


def _ref_kwargs(value):
    return value["artifact_id"], value["content_sha256"]


def _controlled_time(api, profile, overlay, helper):
    foundation = overlay.load_artifact(*_ref_kwargs(profile.semantic_payload["foundation_runtime_profile"]))
    epoch, start, end, observed = helper._window(
        api, foundation, lambda item: overlay.load_artifact(item.artifact_id, item.content_sha256))
    bundle = overlay.load_artifact(*_ref_kwargs(profile.semantic_payload["knowledge_bundle"]))
    knowledge = api.assembly.DeviceFingerprintRequestAssembly.reconstruct_knowledge_bundle(
        bundle, lambda item: overlay.load_artifact(item.artifact_id, item.content_sha256))
    retrieved = [getattr(knowledge, f"{slot}_provenance").semantic_payload["retrieved_at_utc"]
                 for slot in ("k1", "k2b", "k4")]
    now = max(api.validation.parse_utc(item) for item in [end, *retrieved]) + timedelta(seconds=1)
    return foundation, knowledge, epoch, start, end, observed, api.validation.format_utc(now)


def _controlled_dhcp_row(api, helper, epoch, observed, ingested, knowledge, sequence):
    source = next(record for record in knowledge.k1_record_set.semantic_payload["records"]
                  if {item["dimension_name"]: item["canonical_target_id"]
                      for item in record["candidate_taxonomy_refs"]
                      if item["outcome_kind"] == "CANONICAL_VALUE"}.get("platform_family") == "android")
    payload = dict(helper.KNOWN_DHCP)
    for field, predicate in source["dhcp_predicates"].items():
        if predicate["mode"] in ("EXACT_VALUE", "EXACT_SEQUENCE"):
            payload[field] = predicate["value"]
    row = helper._fixture_row(api, epoch, observed, ingested, sequence,
                              raw=api.validation.canonical_json(payload))
    row.update(source_subtype=payload["message_type"], extractor_name="packet-dhcp")
    return row


def _add_controlled_source_row(path, api, helper, epoch, observed, end, knowledge):
    ingested = api.validation.format_utc(api.validation.parse_utc(end) + timedelta(minutes=1))
    with sqlite3.connect(path) as connection:
        state = connection.execute("SELECT last_ingest_sequence FROM device_fingerprint_storage_state "
                                   "WHERE singleton_id=1").fetchone()
        require(state is not None, "TASK01_SOURCE_SCHEMA")
        sequence = state[0] + 1
        row = _controlled_dhcp_row(api, helper, epoch, observed, ingested, knowledge, sequence)
        columns = tuple(row)
        connection.execute("INSERT INTO device_fingerprint_evidence (" + ",".join(columns) + ") VALUES ("
                           + ",".join("?" for _ in columns) + ")",
                           tuple(row[name] for name in columns))
        connection.execute("UPDATE device_fingerprint_storage_state SET last_ingest_sequence=? "
                           "WHERE singleton_id=1", (sequence,))
    return {"evidence_id": row["evidence_id"], "ingest_sequence": sequence,
            "observed_at": observed, "source_kind": row["source_kind"]}


EXPECTED_CORE_FIELDS = (
    "classification_id", "site_id", "observed_mac", "classified_at_utc",
    "execution_context", "classification_runtime_profile_id",
    "classification_runtime_profile_digest", "foundation_runtime_profile_id",
    "foundation_runtime_profile_digest", "runtime_profile_activation_record_id",
    "classification_request_manifest_id", "classification_request_manifest_digest",
    "classification_result_id", "classification_result_digest", "snapshot_record_id",
    "snapshot_record_digest", "classification_retention_policy_id",
    "classification_retention_policy_digest",
)
FUTURE_CORE_COLUMNS = frozenset({
    "task04_acceptance_manifest_id", "runtime_profile_admission_manifest_id",
    "decision_record_id", "gate_result_manifest_id", "production_activation_record_id",
})
REQUIRED_AUDIT_TYPES = frozenset({
    "SnapshotRecord", "EvidenceSnapshotContent", "SourceEvaluability", "OriginAssessment",
    "ClassificationRequestManifest", "ClassificationResult", "FoundationRuntimeProfile",
    "ClassificationRuntimeProfile", "KnowledgeBundle", "ClassificationPolicy",
    "EvidenceAdapterContractSet", "ClassifierArtifactManifest", "ClassificationRetentionPolicy",
})
SEMANTIC_CORE_REFS = (
    ("classification_runtime_profile_id", "classification_runtime_profile_digest"),
    ("foundation_runtime_profile_id", "foundation_runtime_profile_digest"),
    ("classification_request_manifest_id", "classification_request_manifest_digest"),
    ("classification_result_id", "classification_result_digest"),
    ("snapshot_record_id", "snapshot_record_digest"),
    ("classification_retention_policy_id", "classification_retention_policy_digest"),
)


def _declared_edge(owner: str, value: dict[str, str]) -> tuple[str, str, str]:
    require(isinstance(value, dict) and set(value) == {"artifact_id", "content_sha256"}
            and isinstance(value["artifact_id"], str)
            and isinstance(value["content_sha256"], str),
            "AUDIT_DEPENDENCY_EDGE_MISMATCH", owner)
    return owner, value["artifact_id"], value["content_sha256"]


def _semantic_closure(contents, classifications, api):
    """Derive the runtime/replay graph from exact core refs, never audit history."""
    pending = []
    for core in classifications:
        for id_field, digest_field in SEMANTIC_CORE_REFS:
            artifact_id, digest = core[id_field], core[digest_field]
            target = contents.get(artifact_id)
            require(target is not None and target.content_sha256 == digest,
                    "AUDIT_RUNTIME_CLOSURE_MISSING", str(artifact_id))
            pending.append(artifact_id)
    semantic = set()
    while pending:
        artifact_id = pending.pop()
        if artifact_id in semantic:
            continue
        content = contents[artifact_id]
        require(content.artifact_type not in {
            "RuntimeProfileAdmissionManifest", "FoundationAdmissionManifest",
            "Task04AcceptanceManifest"}, "AUDIT_RUNTIME_CLOSURE_BOUNDARY", artifact_id)
        semantic.add(artifact_id)
        for reference in api.graph.extract_direct_artifact_refs(content):
            target = contents.get(reference.artifact_id)
            require(target is not None and target.content_sha256 == reference.content_sha256,
                    "AUDIT_RUNTIME_CLOSURE_MISSING", reference.artifact_id)
            pending.append(reference.artifact_id)
    return semantic


def _bounded_expected_edges(content, api, semantic):
    """Validate §120 admission edges separately from strict semantic replay edges."""
    owner, payload = content.artifact_id, content.semantic_payload
    if content.artifact_type == "RuntimeProfileAdmissionManifest":
        require(api.profiles.make_runtime_profile_admission_manifest(payload) == content,
                "AUDIT_CONTENT_MISMATCH", owner)
        fields = ("candidate_profile", "foundation_admission_manifest",
                  "task04_acceptance_manifest",
                  "foundation_runtime_profile_admission_manifest")
        return {_declared_edge(owner, payload[field]) for field in fields
                if payload[field] is not None}
    if content.artifact_type == "FoundationAdmissionManifest":
        require(api.origin_admission.make_foundation_admission_manifest(payload) == content,
                "AUDIT_CONTENT_MISMATCH", owner)
        opaque = {item["artifact_id"] for item in
                  payload["pre_admission_gate_result_manifests"]}
        return {(owner, item.artifact_id, item.content_sha256)
                for item in api.graph.extract_direct_artifact_refs(content)
                if item.artifact_id in semantic and item.artifact_id not in opaque}
    if content.artifact_type == "Task04AcceptanceManifest":
        fields = ("tested_classification_runtime_profile", "classifier_artifact_manifest",
                  "foundation_admission_manifest")
        return {_declared_edge(owner, payload[field]) for field in fields}
    return {(owner, item.artifact_id, item.content_sha256)
            for item in api.graph.extract_direct_artifact_refs(content)}


def _inventory(store, api):
    """Read the real SQLite schema and validate all immutable bytes, refs and edges."""
    with store._connect() as conn:
        schema = {row["name"]: row["sql"] for row in conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        columns = {name: [row["name"] for row in conn.execute(f"PRAGMA table_info({name})")]
                   for name in schema}
        required_tables = {"classifications", "artifacts", "artifact_dependencies",
                           "classification_roots"}
        require(required_tables <= set(schema), "CLASSIFICATION_SCHEMA_MISMATCH")
        require(tuple(columns["classifications"]) == EXPECTED_CORE_FIELDS,
                "CLASSIFICATION_SCHEMA_MISMATCH")
        require(not (set(columns["classifications"]) & FUTURE_CORE_COLUMNS),
                "FUTURE_CORE_PLACEHOLDER")
        artifacts = list(conn.execute("SELECT artifact_id, artifact_type, content_sha256, "
                                      "semantic_payload_json FROM artifacts ORDER BY artifact_id"))
        ids = {row["artifact_id"]: row for row in artifacts}
        edges = list(conn.execute("SELECT owner_id, dependency_id, dependency_digest "
                                  "FROM artifact_dependencies ORDER BY owner_id, dependency_id"))
        roots = list(conn.execute("SELECT classification_id, artifact_id, content_sha256 "
                                  "FROM classification_roots ORDER BY classification_id, artifact_id"))
        classifications = list(conn.execute("SELECT * FROM classifications"))
        contents = {}
        for row in artifacts:
            content = store.load_artifact(row["artifact_id"], row["content_sha256"])
            require(content.artifact_type == row["artifact_type"] and
                    content.semantic_payload_json == row["semantic_payload_json"],
                    "AUDIT_CONTENT_MISMATCH", row["artifact_id"])
            contents[row["artifact_id"]] = content
        semantic = _semantic_closure(contents, classifications, api)
        rpm_refs = set()
        foundation_refs = set()
        rpm_ref_count = 0
        foundation_ref_count = 0
        for row in artifacts:
            content = contents[row["artifact_id"]]
            expected = _bounded_expected_edges(content, api, semantic)
            actual = {(edge["owner_id"], edge["dependency_id"], edge["dependency_digest"])
                      for edge in edges if edge["owner_id"] == row["artifact_id"]}
            require(actual == expected, "AUDIT_DEPENDENCY_EDGE_MISMATCH", row["artifact_id"])
            if content.artifact_type == "RuntimeProfileAdmissionManifest":
                opaque = content.semantic_payload["prerequisite_gate_results"]
                rpm_ref_count += len(opaque)
                rpm_refs.update((content.artifact_id, item["artifact_id"]) for item in opaque)
            elif content.artifact_type == "FoundationAdmissionManifest":
                opaque = content.semantic_payload["pre_admission_gate_result_manifests"]
                foundation_ref_count += len(opaque)
                foundation_refs.update((content.artifact_id, item["artifact_id"])
                                       for item in opaque)
        rpm_opaque_edges = sum((edge["owner_id"], edge["dependency_id"]) in rpm_refs
                               for edge in edges)
        foundation_opaque_edges = sum((edge["owner_id"], edge["dependency_id"])
                                      in foundation_refs for edge in edges)
        require(rpm_opaque_edges == 0 and foundation_opaque_edges == 0,
                "OPAQUE_GATE_DEPENDENCY_EDGE")
        dangling = 0
        for edge in edges:
            target = ids.get(edge["dependency_id"])
            if edge["owner_id"] not in ids or target is None or (
                    target["content_sha256"] != edge["dependency_digest"]):
                dangling += 1
        classification_ids = {row["classification_id"] for row in classifications}
        for root in roots:
            target = ids.get(root["artifact_id"])
            if target is None or target["content_sha256"] != root["content_sha256"]:
                dangling += 1
            if root["classification_id"] not in classification_ids:
                dangling += 1
        require(dangling == 0, "DANGLING_AUDIT_REFERENCE")
        historical_present = HISTORICAL_MISSING_ARTIFACT in ids
        historical_edges = sum(edge["dependency_id"] == HISTORICAL_MISSING_ARTIFACT
                               for edge in edges)
        historical_roots = sum(root["artifact_id"] == HISTORICAL_MISSING_ARTIFACT
                               for root in roots)
        unjustified_ckrs = [row["artifact_id"] for row in artifacts
                            if row["artifact_type"] == "CanonicalKnowledgeRecordSet"
                            and row["artifact_id"] not in semantic]
        require(not historical_present and historical_edges == 0 and historical_roots == 0
                and not unjustified_ckrs, "HISTORICAL_GATE_ARTIFACT_RETAINED")
        return {"table_schema": schema, "table_columns": columns,
                "classification_count": len(classifications), "artifact_count": len(artifacts),
                "dependency_edge_count": len(edges), "root_count": len(roots),
                "audit_closure_contract": AUDIT_CLOSURE_CONTRACT,
                "historical_missing_artifact": HISTORICAL_MISSING_ARTIFACT,
                "historical_missing_artifact_present_in_classification_db": historical_present,
                "historical_missing_artifact_dependency_edge_count": historical_edges,
                "historical_missing_artifact_root_count": historical_roots,
                "synthetic_historical_replacement_count": len(unjustified_ckrs),
                "opaque_rpm_prerequisite_gate_ref_count": rpm_ref_count,
                "opaque_rpm_prerequisite_dependency_edge_count": rpm_opaque_edges,
                "opaque_foundation_gate_ref_count": foundation_ref_count,
                "opaque_foundation_gate_dependency_edge_count": foundation_opaque_edges,
                "artifact_refs": [{"artifact_id": row["artifact_id"],
                                   "content_sha256": row["content_sha256"],
                                   "artifact_type": row["artifact_type"]} for row in artifacts],
                "dangling_ref_scan_result": {"dangling_count": dangling, "pass": True}}


def _snapshot_lineage(store, api, assembly, core):
    snapshot = store.load_artifact(core.snapshot_record_id, core.snapshot_record_digest)
    require(snapshot == assembly.snapshot_record, "SNAPSHOT_RECORD_MISMATCH")
    resolved = {}
    for field, kind in (("evidence_snapshot_content", "EvidenceSnapshotContent"),
                        ("foundation_runtime_profile", "FoundationRuntimeProfile"),
                        ("snapshot_content_policy", "SnapshotContentPolicy"),
                        ("snapshot_execution_policy", "SnapshotExecutionPolicy")):
        item = snapshot.semantic_payload[field]
        content = store.load_artifact(item["artifact_id"], item["content_sha256"])
        require(content.artifact_type == kind and ref(content) == item,
                "SNAPSHOT_LINEAGE_DANGLING", field)
        resolved[field] = content
    require(api.snapshot_artifacts.make_snapshot_record(snapshot.semantic_payload,
            **resolved) == snapshot, "SNAPSHOT_RECORD_MISMATCH")
    return {"snapshot_record": ref(snapshot),
            "resolved_refs": {name: ref(content) for name, content in resolved.items()}}


def _counts(store):
    with store._connect() as conn:
        return {name: conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for name in (
            "classifications", "artifacts", "artifact_dependencies", "classification_roots")}


def _production_guard(api, run_dir, assembly, retention, overlay, source_copy):
    """M11 exact P rejects; M12 separately exercises real CAS with disposable fixtures."""
    unadmitted_path = run_dir / "unadmitted-classification.sqlite3"
    unadmitted = api.persistence.DeviceFingerprintClassificationStore(
        unadmitted_path, source_copy, control_plane_store=overlay)
    unadmitted.initialize()
    production = replace(assembly, execution_context="PRODUCTION")
    try:
        unadmitted.persist(production, retention_policy=retention)
    except api.persistence.ClassificationPersistenceError as exc:
        reason = exc.reason_code
    else:
        raise SemanticFailure("UNADMITTED_PRODUCTION_COMMITTED")
    require(reason == "production_profile_not_admitted" and _counts(unadmitted)["classifications"] == 0,
            "UNADMITTED_PRODUCTION_REASON")
    cases = {}
    for label, invalidation in (("active", None),
                                ("suspended", "EXPLICIT_POLICY_SUSPEND"),
                                ("ttl_capture_proof_invalidated", "TTL_CAPTURE_PROOF_INVALIDATED")):
        directory = run_dir / f"guard-{label}"
        directory.mkdir()
        store, fixture, candidate_assembly, fixture_retention, _, active = (
            api.persistence_fixture.real_production_setup(directory))
        if invalidation is None:
            core = store.persist(candidate_assembly, retention_policy=fixture_retention)
            require(core.execution_context == "PRODUCTION", "ACTIVE_PRODUCTION_GUARD")
            cases[label] = {"status": "COMMITTED", "classification_id": core.classification_id,
                            "classification_count": _counts(store)["classifications"]}
            continue
        invalidated = api.profiles.make_runtime_profile_validity_record({
            **active.semantic_payload, "validity_record_id": str(uuid.uuid4()),
            "state": "SUSPENDED_INVALIDATED", "reason_code": invalidation,
            "inflight_commit_rule": "REJECT_PINNED_INFLIGHT",
            "previous_validity_record_id": active.semantic_payload["validity_record_id"],
        })
        fixture.store.transition_validity(
            invalidated, expected_head_validity_record_id=active.semantic_payload["validity_record_id"])
        try:
            store.persist(candidate_assembly, retention_policy=fixture_retention)
        except api.persistence.ClassificationPersistenceError as exc:
            rejected_reason = exc.reason_code
        else:
            raise SemanticFailure("INVALIDATED_PRODUCTION_COMMITTED", label)
        require(rejected_reason == "runtime_profile_invalidated" and
                _counts(store)["classifications"] == 0, "INVALIDATION_GUARD_MISMATCH", label)
        cases[label] = {"status": "REJECTED", "reason_code": rejected_reason,
                        "validity_state": "SUSPENDED_INVALIDATED",
                        "inflight_commit_rule": "REJECT_PINNED_INFLIGHT",
                        "classification_count": 0}
    return {"unadmitted_exact_p": {"reason_code": reason, "classification_committed": False,
                                     "profile": ref(assembly.classification_runtime_profile)},
            "controlled_validity_cases": cases, "production_activation": False}


def _direct_matrix(run_dir, api, helper, foundation_copy, source_copy, profile,
                   foundation_admission, retention, classifier):
    with helper.open_foundation_read_only(foundation_copy) as connection:
        historical_present_in_foundation = connection.execute(
            "SELECT 1 FROM artifacts WHERE artifact_id=?",
            (HISTORICAL_MISSING_ARTIFACT,)).fetchone() is not None
        foundation_manifest = helper._resolve_artifact(
            connection, api,
            foundation_admission.semantic_payload["foundation_admission_manifest"])
    require(not historical_present_in_foundation,
            "HISTORICAL_GATE_ARTIFACT_PRESENT_IN_FOUNDATION")
    require(foundation_manifest.artifact_type == "FoundationAdmissionManifest",
            "FOUNDATION_AUDIT_CONTENT_MISMATCH")
    control = api.control.DeviceFingerprintControlPlaneStore(foundation_copy)
    overlay = ImmutableOverlay(control, classifier)
    foundation, knowledge, epoch, start, end, observed, clock = (
        _controlled_time(api, profile, overlay, helper))
    require(profile.semantic_payload["foundation_runtime_profile"] == ref(foundation),
            "FOUNDATION_PROFILE_DUPLICATE_REF")
    fixture_row = _add_controlled_source_row(source_copy, api, helper, epoch, observed, end, knowledge)
    reader = api.read.DeviceFingerprintReadService(str(source_copy), retention_days=30)
    service = api.assembly.DeviceFingerprintRequestAssembly(
        control_plane_store=overlay, read_service=reader,
        compatibility_hook=lambda *_: True, utc_clock=lambda: clock,
        process_memory_guard=lambda _limit: True)
    assembly = service.assemble_pre_acceptance_candidate(
        profile, epoch["site_id"], helper.MAC, start, end)
    require(assembly.execution_context == "PRE_ACCEPTANCE_CANDIDATE" and
            assembly.classification_runtime_profile == profile and
            assembly.foundation_runtime_profile == foundation and not overlay.pin_calls,
            "PRE_ACCEPTANCE_ASSEMBLY_MISMATCH")
    require(retention == api.retention.build_initial_classification_retention_policy_v1(),
            "RETENTION_POLICY_CANDIDATE_MISMATCH")
    first_time = api.validation.parse_utc(clock)
    second_time = first_time + timedelta(days=1)
    times = iter((api.validation.format_utc(first_time), api.validation.format_utc(second_time)))
    classification_path = run_dir / "acceptance-classification.sqlite3"
    require(classification_path != source_copy and not classification_path.is_relative_to(
        Path(__file__).resolve().parent), "CLASSIFICATION_DATABASE_PATH")
    store = api.persistence.DeviceFingerprintClassificationStore(
        classification_path, source_copy, control_plane_store=overlay,
        utc_clock=lambda: next(times))
    store.initialize()
    core_a = store.persist(assembly, retention_policy=retention,
                           pre_acceptance_foundation_runtime_profile_admission_manifest=foundation_admission)
    core_b = store.persist(assembly, retention_policy=retention,
                           pre_acceptance_foundation_runtime_profile_admission_manifest=foundation_admission)
    core_fields = tuple(field.name for field in fields(api.persistence.ClassificationCoreRecord))
    require(core_fields == EXPECTED_CORE_FIELDS and core_a == store.load_core(core_a.classification_id)
            and core_b == store.load_core(core_b.classification_id), "PRE_ACCEPTANCE_CORE_SCHEMA")
    require(core_a.execution_context == "PRE_ACCEPTANCE_CANDIDATE" and
            core_a.runtime_profile_activation_record_id is None and
            (core_a.classification_runtime_profile_id,
             core_a.classification_runtime_profile_digest) == (
                 profile.artifact_id, profile.content_sha256) and
            (core_a.foundation_runtime_profile_id, core_a.foundation_runtime_profile_digest) == (
                foundation.artifact_id, foundation.content_sha256) and
            (core_a.classification_retention_policy_id,
             core_a.classification_retention_policy_digest) == (
                 retention.artifact_id, retention.content_sha256), "PRE_ACCEPTANCE_CORE_MISMATCH")
    initial_inventory = _inventory(store, api)
    require(initial_inventory["classification_count"] == 2 and
            REQUIRED_AUDIT_TYPES <= {row["artifact_type"] for row in initial_inventory["artifact_refs"]},
            "AUDIT_CLOSURE_INCOMPLETE")
    retained_rpm = store.load_artifact(foundation_admission.artifact_id,
                                       foundation_admission.content_sha256)
    retained_foundation_manifest = store.load_artifact(
        foundation_manifest.artifact_id, foundation_manifest.content_sha256)
    require(retained_rpm == foundation_admission and
            retained_rpm.semantic_payload_json == foundation_admission.semantic_payload_json and
            retained_foundation_manifest == foundation_manifest and
            retained_foundation_manifest.semantic_payload_json ==
                foundation_manifest.semantic_payload_json,
            "IMMUTABLE_OPAQUE_AUDIT_CONTENT_MISMATCH")
    rpm_gate_refs = retained_rpm.semantic_payload["prerequisite_gate_results"]
    foundation_gate_refs = retained_foundation_manifest.semantic_payload[
        "pre_admission_gate_result_manifests"]
    require(rpm_gate_refs == foundation_admission.semantic_payload["prerequisite_gate_results"]
            and foundation_gate_refs == foundation_manifest.semantic_payload[
                "pre_admission_gate_result_manifests"]
            and bool(rpm_gate_refs) and bool(foundation_gate_refs),
            "OPAQUE_AUDIT_REFERENCES_MISSING")
    with store._connect() as connection:
        rpm_opaque_edges = sum(connection.execute(
            "SELECT COUNT(*) FROM artifact_dependencies WHERE owner_id=? AND dependency_id=?",
            (retained_rpm.artifact_id, item["artifact_id"])).fetchone()[0]
            for item in rpm_gate_refs)
        foundation_opaque_edges = sum(connection.execute(
            "SELECT COUNT(*) FROM artifact_dependencies WHERE owner_id=? AND dependency_id=?",
            (retained_foundation_manifest.artifact_id, item["artifact_id"])).fetchone()[0]
            for item in foundation_gate_refs)
    require(rpm_opaque_edges == 0 and foundation_opaque_edges == 0,
            "OPAQUE_GATE_DEPENDENCY_EDGE")
    opaque_audit = {
        "audit_closure_contract": AUDIT_CLOSURE_CONTRACT,
        "historical_missing_artifact": HISTORICAL_MISSING_ARTIFACT,
        "historical_gate_artifact_present_before_persist": historical_present_in_foundation,
        "historical_missing_artifact_present_in_foundation_copy": historical_present_in_foundation,
        "historical_missing_artifact_present_in_classification_db":
            initial_inventory["historical_missing_artifact_present_in_classification_db"],
        "historical_missing_artifact_dependency_edge_count":
            initial_inventory["historical_missing_artifact_dependency_edge_count"],
        "historical_missing_artifact_root_count":
            initial_inventory["historical_missing_artifact_root_count"],
        "synthetic_historical_replacement_count":
            initial_inventory["synthetic_historical_replacement_count"],
        "opaque_rpm_prerequisite_gate_ref_count": len(rpm_gate_refs),
        "opaque_rpm_prerequisite_dependency_edge_count": rpm_opaque_edges,
        "opaque_foundation_gate_ref_count": len(foundation_gate_refs),
        "opaque_foundation_gate_dependency_edge_count": foundation_opaque_edges,
        "immutable_rpm_content_ref": ref(retained_rpm),
        "immutable_foundation_manifest_content_ref": ref(retained_foundation_manifest),
    }
    roots = {row["artifact_id"] for row in initial_inventory["artifact_refs"]}
    require(not any(item.startswith(("Task04AcceptanceManifest:", "DecisionRecord:")) for item in roots),
            "FUTURE_ACCEPTANCE_PLACEHOLDER")
    with store._connect() as conn:
        future_admission = conn.execute("SELECT COUNT(*) FROM artifacts WHERE artifact_type="
            "'RuntimeProfileAdmissionManifest' AND semantic_payload_json LIKE "
            "'%classification%'").fetchone()[0]
    require(future_admission == 0, "FUTURE_ACCEPTANCE_PLACEHOLDER")
    snapshot_lineage = _snapshot_lineage(store, api, assembly, core_a)
    before_mismatch = _counts(store)
    wrong_foundation = api.artifact.make_artifact_content("FoundationRuntimeProfile", {"controlled": True})
    try:
        store.persist(replace(assembly, foundation_runtime_profile=wrong_foundation),
                      retention_policy=retention,
                      pre_acceptance_foundation_runtime_profile_admission_manifest=foundation_admission)
    except api.persistence.ClassificationPersistenceError:
        pass
    else:
        raise SemanticFailure("FOUNDATION_PROFILE_DUPLICATE_REF_ALLOWED")
    require(_counts(store) == before_mismatch, "FOUNDATION_MISMATCH_COMMITTED")

    # The only removed database is this exact run-directory copy, never --task01-db.
    require(source_copy.parent == run_dir and source_copy.is_file(), "TASK01_DISPOSABLE_DELETE_SCOPE")
    with store._connect() as conn:
        result_bytes_before = bytes(conn.execute(
            "SELECT semantic_payload_json FROM artifacts WHERE artifact_id=?",
            (assembly.classification_result.artifact_id,)).fetchone()[0])
    source_copy.unlink()
    wall_clock_reads = [0]
    def forbidden_clock():
        wall_clock_reads[0] += 1
        raise AssertionError("current clock read during Level-B replay")
    store._clock = forbidden_clock
    replayed = store.replay_level_b(core_a.classification_id)
    require(replayed == assembly.classification_result and wall_clock_reads[0] == 0,
            "LEVEL_B_REPLAY_MISMATCH")
    with store._connect() as conn:
        result_bytes_after = bytes(conn.execute(
            "SELECT semantic_payload_json FROM artifacts WHERE artifact_id=?",
            (assembly.classification_result.artifact_id,)).fetchone()[0])
    require(result_bytes_before == result_bytes_after, "REPLAY_MUTATED_RESULT")

    seconds = retention.semantic_payload["classification_history_retention_seconds"]
    before_boundary = api.validation.format_utc(first_time + timedelta(seconds=seconds,
                                                                         milliseconds=-1))
    at_boundary = api.validation.format_utc(first_time + timedelta(seconds=seconds))
    before_expired = store.expire_and_gc(now_utc=before_boundary)
    require(before_expired == 0 and store.load_core(core_a.classification_id) == core_a,
            "RETENTION_PRE_BOUNDARY")
    boundary_expired = store.expire_and_gc(now_utc=at_boundary)
    require(boundary_expired == 1 and _counts(store)["classifications"] == 1,
            "RETENTION_BOUNDARY")
    shared = {}
    for name in ("classification_runtime_profile", "foundation_runtime_profile",
                 "knowledge_bundle", "classification_policy", "evidence_adapter_contract_set",
                 "classifier_artifact_manifest", "classification_result"):
        artifact = getattr(assembly, name)
        shared[name] = ref(store.load_artifact(artifact.artifact_id, artifact.content_sha256))
    require(store.replay_level_b(core_b.classification_id) == assembly.classification_result,
            "SHARED_ARTIFACT_GC")
    after_first = _inventory(store, api)
    second_boundary = api.validation.format_utc(second_time + timedelta(seconds=seconds))
    last_expired = store.expire_and_gc(now_utc=second_boundary)
    after_all = _inventory(store, api)
    require(last_expired == 1 and all(after_all[name] == 0 for name in (
        "classification_count", "artifact_count", "dependency_edge_count", "root_count")),
        "UNREFERENCED_ARTIFACT_NOT_GC_ELIGIBLE")

    fault_path = run_dir / "fault-classification.sqlite3"
    def fault(stage):
        require(stage == "before_commit", "FAULT_HOOK_STAGE")
        raise sqlite3.OperationalError("controlled pre-commit fault")
    fault_store = api.persistence.DeviceFingerprintClassificationStore(
        fault_path, source_copy, control_plane_store=overlay, utc_clock=lambda: clock,
        fault_hook=fault)
    fault_store.initialize()
    try:
        fault_store.persist(assembly, retention_policy=retention,
                            pre_acceptance_foundation_runtime_profile_admission_manifest=foundation_admission)
    except api.persistence.ClassificationPersistenceError as exc:
        fault_reason = exc.reason_code
    else:
        raise SemanticFailure("ATOMIC_FAULT_COMMITTED")
    require(fault_reason == "persistence_unavailable" and all(value == 0 for value in
            _counts(fault_store).values()), "ATOMIC_ROLLBACK_INCOMPLETE")

    guard = _production_guard(api, run_dir, assembly, retention, overlay, source_copy)
    matrix = {key: {"status": "PASS", "trace": {}} for key in CASES}
    matrix["T07-M01"]["trace"] = {"core": {field: getattr(core_a, field) for field in core_fields}}
    matrix["T07-M02"]["trace"] = {"future_core_columns": [],
                                    "future_classification_admission_roots": future_admission,
                                    "activation_record_id": None}
    matrix["T07-M03"]["trace"] = {"profile_foundation_ref": profile.semantic_payload[
        "foundation_runtime_profile"], "assembly_foundation_ref": ref(foundation),
        "core_foundation_ref": {"artifact_id": core_a.foundation_runtime_profile_id,
                                "content_sha256": core_a.foundation_runtime_profile_digest},
        "controlled_mismatch_rejected": True}
    matrix["T07-M04"]["trace"] = {"required_types": sorted(REQUIRED_AUDIT_TYPES),
                                    "artifact_count": initial_inventory["artifact_count"],
                                    "dangling_count": 0, **opaque_audit,
                                    "runtime_replay_direct_edges_exact": True,
                                    "bounded_admission_edges_exact": True}
    matrix["T07-M05"]["trace"] = snapshot_lineage
    matrix["T07-M06"]["trace"] = {"original_result": ref(assembly.classification_result),
        "replayed_result": ref(replayed), "disposable_task01_removed": True,
        "wall_clock_read_count": wall_clock_reads[0], "result_bytes_identical": True}
    matrix["T07-M07"]["trace"] = {"first_expired": True, "shared_artifacts": shared,
        "remaining_replay_exact": True, "remaining_classification_count": 1,
        "historical_gate_only_identity": HISTORICAL_MISSING_ARTIFACT,
        "historical_gate_only_root_count": after_first[
            "historical_missing_artifact_root_count"],
        "historical_gate_only_dependency_edge_count": after_first[
            "historical_missing_artifact_dependency_edge_count"],
        "opaque_gate_only_gc_protection": False}
    matrix["T07-M08"]["trace"] = {"retention_seconds": seconds,
        "before_boundary_utc": before_boundary, "before_expired_count": before_expired,
        "at_boundary_utc": at_boundary, "at_boundary_expired_count": boundary_expired}
    matrix["T07-M09"]["trace"] = {"last_expired_count": last_expired,
                                     "after_all": after_all}
    matrix["T07-M10"]["trace"] = {"fault_stage": "before_commit",
        "reason_code": fault_reason, "post_fault_counts": _counts(fault_store)}
    matrix["T07-M11"]["trace"] = guard["unadmitted_exact_p"]
    matrix["T07-M12"]["trace"] = guard["controlled_validity_cases"]
    reports = {
        "core": {"core_row": {field: getattr(core_a, field) for field in core_fields},
                 "exact_profile": ref(profile), "foundation_profile": ref(foundation),
                 "retention_policy": ref(retention), "execution_context": core_a.execution_context,
                 "activation_record_id": core_a.runtime_profile_activation_record_id,
                 "schema_columns": initial_inventory["table_columns"]["classifications"],
                 "future_placeholder_absent": True, "same_production_schema": True,
                 "post_acceptance_row_mutation_required": False},
        "inventory": {**initial_inventory, "after_first_gc": after_first,
                      "after_all_gc": after_all, "classification_db_sha256": sha(classification_path),
                      "classification_db_path": str(classification_path),
                      "task01_source_copy_deleted": True,
                      "historical_missing_artifact_present_in_foundation_copy":
                          historical_present_in_foundation,
                      "exact_opaque_audit_boundary": opaque_audit},
        "replay": {"original_request": ref(assembly.classification_request_manifest),
                   "original_result": ref(assembly.classification_result),
                   "replayed_result": ref(replayed), "disposable_task01_source_removed": True,
                   "wall_clock_read_count": wall_clock_reads[0],
                   "stored_result_bytes_before_sha256": hashlib.sha256(result_bytes_before).hexdigest(),
                   "stored_result_bytes_after_sha256": hashlib.sha256(result_bytes_after).hexdigest(),
                   "replay_exact": True, "snapshot_lineage": snapshot_lineage,
                   "controlled_source_row": fixture_row},
        "gc": {"retention_policy": ref(retention), "retention_seconds": seconds,
               "audit_closure_contract": AUDIT_CLOSURE_CONTRACT,
               "historical_missing_artifact": HISTORICAL_MISSING_ARTIFACT,
               "pre_boundary": matrix["T07-M08"]["trace"],
               "shared_artifact_protected": matrix["T07-M07"]["trace"],
               "unreferenced_artifact_gc": matrix["T07-M09"]["trace"],
               "dangling_edges_after_gc": 0},
        "guard": guard,
    }
    return matrix, reports


def _run_pytest(repo: Path, run_dir: Path):
    temp = run_dir / "pytest-temp"
    temp.mkdir()
    command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
               "--basetemp", str(temp / "base"), "tests/device_fingerprint_task04_04d_persistence"]
    env = dict(os.environ)
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTEST_ADDOPTS="", TEMP=str(temp),
               TMP=str(temp), TMPDIR=str(temp), PYTHONPYCACHEPREFIX=str(temp / "pycache"))
    try:
        result = subprocess.run(command, cwd=repo, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                errors="replace", timeout=1800)
        output = result.stdout
        status = result.returncode
    except (OSError, subprocess.SubprocessError) as exc:
        output = f"T-07 persistence suite execution failed: {type(exc).__name__}: {exc}\n"
        status = 1
    (run_dir / "t07-pytest.log").write_text(output, encoding="utf-8")
    return status, command


def _formal(api, helper, run_dir, profile, t06a_result, retention, foundation_admission,
            runner_sha, passed):
    identity = {"execution_id": str(uuid.uuid4()), "executor_kind": "TECHLEAD_GATE_TOOL",
                "repository_commit_sha": COMMIT, "repository_tree_sha": TREE,
                "procedure_or_test_suite_id": PROCEDURE,
                "environment_identity": helper._environment_identity(),
                "execution_artifact_sha256": runner_sha}
    evidence = [{"evidence_label": name.rsplit(".", 1)[0], "file_sha256": sha(run_dir / name),
                 "media_type": "text/plain" if name.endswith((".log", ".txt")) else "application/json",
                 "path_or_reference": name} for name in RETAINED]
    inputs = sorted([ref(item) for item in (t06a_result, profile, retention, foundation_admission)],
                    key=lambda row: row["artifact_id"])
    proof = None
    if passed:
        proof = api.gate_proof.make_gate_proof_artifact({
            "proof_kind": PROOF_KIND, "source_gate_id": GATE_ID,
            "candidate_repository_commit_sha": COMMIT, "candidate_repository_tree_sha": TREE,
            "input_artifact_refs": inputs, "procedure_or_test_suite_id": PROCEDURE,
            "proof_execution_identity": identity,
            "canonical_result_summary": (
                f"profile={PROFILE_ID};matrix=12/12 PASS;level_b_replay=PASS;"
                "reference_gc=PASS;production_admission_guard=PASS"),
            "retained_evidence_refs": evidence,
        })
    result = api.gate_result.make_gate_result_manifest({
        "gate_id": GATE_ID, "gate_contract_version": CONTRACT,
        "status": "PASS" if passed else "FAIL",
        "candidate_repository_commit_sha": COMMIT, "candidate_repository_tree_sha": TREE,
        "input_artifact_refs": inputs,
        "output_artifact_refs": [ref(proof)] if proof is not None else [],
        "retained_evidence_refs": evidence, "proof_execution_identity": identity,
        "trusted_time_inputs": {"foundation_knowledge_evaluation_at_utc": None,
                                "foundation_admission_evaluation_at_utc": None,
                                "knowledge_evaluation_at_utc": None},
        "decision_record_refs": [],
    })
    if proof is not None:
        helper._write_and_roundtrip(run_dir / "t07-gate-proof-artifact.json", proof,
                                    api.gate_proof.make_gate_proof_artifact,
                                    api.artifact.canonical_artifact_json)
    helper._write_and_roundtrip(run_dir / "t07-gate-result-manifest.json", result,
                                api.gate_result.make_gate_result_manifest,
                                api.artifact.canonical_artifact_json)
    return proof, result


def _blocked(run_dir, code):
    if run_dir is not None:
        for name in ("t07-gate-proof-artifact.json", "t07-gate-result-manifest.json"):
            (run_dir / name).unlink(missing_ok=True)
        (run_dir / "t07-summary.txt").write_text(
            f"GATE_EXECUTION_STATUS={code}\n", encoding="utf-8")
    print(f"GATE_EXECUTION_STATUS={code}")
    return 2


def run_gate(repo: Path, foundation_db: Path, task01_db: Path,
             t06a_run_dir: Path, output_dir: Path) -> int:
    """Official entry point; self-test invokes it only with disposable input copies."""
    run_dir = None
    runner = Path(__file__).resolve()
    runner_sha = sha(runner)
    try:
        helper, t06a = helpers()
        repo = repo.resolve(strict=True)
        foundation_db = foundation_db.resolve(strict=True)
        task01_db = task01_db.resolve(strict=True)
        t06a_run_dir = t06a_run_dir.resolve(strict=True)
        output_dir = output_dir.resolve()
        if (not foundation_db.is_file() or not task01_db.is_file()
                or foundation_db == task01_db or output_dir.is_relative_to(repo)
                or output_dir.is_relative_to(t06a_run_dir)
                or output_dir == foundation_db.parent or output_dir == task01_db.parent
                or output_dir == runner.parent
                or (output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())))):
            raise Blocked("BLOCKED_OUTPUT_OR_INPUT_PATH")
        output_dir.mkdir(parents=True, exist_ok=True)
        run_dir = output_dir / str(uuid.uuid4())
        run_dir.mkdir(exist_ok=False)
        helper.verify_repository(repo)
        before_repo = helper.repository_filesystem_fingerprint(repo)
        before_foundation = sha(foundation_db)
        before_task01 = sha(task01_db)
        sys.path.insert(0, str(repo))
        api = api_for(repo, t06a)
        profile, t06a_proof, t06a_result = verify_t06a(t06a_run_dir, api)
        with helper.open_foundation_read_only(foundation_db) as connection:
            lineage = helper.verify_foundation(connection, api)
            retention = resolve_retention(connection, api, helper, lineage)
        if profile.semantic_payload["foundation_runtime_profile"] != ref(lineage.profile):
            raise Blocked("BLOCKED_FOUNDATION_LINEAGE", "P Foundation ref")
        classifier = canonical_content(
            T06_MANIFEST_PATH, api,
            lambda payload: api.artifact.make_artifact_content("ClassifierArtifactManifest", payload),
            profile.semantic_payload["classifier_artifact_manifest"]["artifact_id"])
        copy_sqlite_readonly(foundation_db, run_dir / "foundation-disposable.sqlite3")
        copy_sqlite_readonly(task01_db, run_dir / "task01-disposable.sqlite3")
        foundation_copy = run_dir / "foundation-disposable.sqlite3"
        task01_copy = run_dir / "task01-disposable.sqlite3"
        with helper.open_foundation_read_only(foundation_copy) as connection:
            copy_lineage = helper.verify_foundation(connection, api)
            copy_retention = resolve_retention(connection, api, helper, copy_lineage)
        if (copy_lineage != lineage or copy_retention != retention):
            raise Blocked("BLOCKED_FOUNDATION_LINEAGE", "disposable copy mismatch")
        suite_status, suite_command = _run_pytest(repo, run_dir)
        matrix = {key: {"status": "NOT_RUN", "trace": {}} for key in CASES}
        reports = {"core": {}, "inventory": {}, "replay": {}, "gc": {}, "guard": {}}
        failure = None
        failure_detail = None
        if suite_status != 0:
            failure = "EXISTING_PERSISTENCE_SUITE_FAILED"
        else:
            try:
                if retention != api.retention.build_initial_classification_retention_policy_v1():
                    raise SemanticFailure("RETENTION_POLICY_CANDIDATE_MISMATCH")
                matrix, reports = _direct_matrix(run_dir, api, helper, foundation_copy,
                    task01_copy, profile, copy_lineage.admission, retention, classifier)
            except Exception as exc:
                failure = exc.code if isinstance(exc, SemanticFailure) else type(exc).__name__
                failure_detail = str(exc)[:400]
        all_pass = failure is None and len(matrix) == 12 and all(
            row["status"] == "PASS" for row in matrix.values())
        if not all_pass and failure is None:
            failure = "T07_MATRIX_INCOMPLETE"
        reports["inventory"]["accepted_task01_db_sha256_before"] = before_task01
        reports["inventory"]["accepted_task01_db_sha256_after"] = sha(task01_db)
        reports["inventory"]["accepted_foundation_db_sha256_before"] = before_foundation
        reports["inventory"]["accepted_foundation_db_sha256_after"] = sha(foundation_db)
        for name, key in (("t07-persistence-core.json", "core"),
                          ("t07-classification-db-inventory.json", "inventory"),
                          ("t07-audit-replay-report.json", "replay"),
                          ("t07-gc-report.json", "gc"),
                          ("t07-production-admission-guard.json", "guard")):
            write_json(run_dir / name, reports[key])
        write_json(run_dir / "t07-execution-evidence.json", {
            "candidate_commit": COMMIT, "candidate_tree": TREE,
            "audit_closure_contract": AUDIT_CLOSURE_CONTRACT,
            "historical_missing_artifact": HISTORICAL_MISSING_ARTIFACT,
            **{key: reports["inventory"].get("exact_opaque_audit_boundary", {}).get(key)
               for key in (
                   "historical_gate_artifact_present_before_persist",
                   "historical_missing_artifact_present_in_foundation_copy",
                   "historical_missing_artifact_present_in_classification_db",
                   "historical_missing_artifact_dependency_edge_count",
                   "historical_missing_artifact_root_count",
                   "opaque_rpm_prerequisite_gate_ref_count",
                   "opaque_rpm_prerequisite_dependency_edge_count",
                   "opaque_foundation_gate_ref_count",
                   "opaque_foundation_gate_dependency_edge_count")},
            "runner_sha256": runner_sha, "t01_helper_sha256": T01_SHA,
            "t06a_runner_sha256": T06A_SHA, "t06a_gate_result": ref(t06a_result),
            "t06a_gate_proof": ref(t06a_proof), "exact_profile": ref(profile),
            "accepted_retention_policy": ref(retention),
            "foundation_runtime_profile_admission_manifest": ref(lineage.admission),
            "pytest_command": suite_command, "pytest_exit_status": suite_status,
            "direct_matrix": matrix, "all_pass": all_pass,
            "failure_code": failure, "failure_detail": failure_detail,
            "repository_immutability": "PASS", "task01_db_byte_identity": "PASS",
            "foundation_db_byte_identity": "PASS",
        })
        (run_dir / "t07-summary.txt").write_text(
            f"GATE_EXECUTION_STATUS={'PASS' if all_pass else 'FAIL'}\n"
            f"PROFILE={PROFILE_ID}\nFAILURE_CODE={failure or 'NONE'}\n",
            encoding="utf-8")
        if sha(runner) != runner_sha or sha(T01_PATH) != T01_SHA or sha(T06A_PATH) != T06A_SHA:
            raise Blocked("BLOCKED_RUNNER_CHANGED")
        helper._require_repository_unchanged(repo, before_repo)
        if sha(foundation_db) != before_foundation or sha(task01_db) != before_task01:
            raise Blocked("BLOCKED_INPUT_DATABASE_MUTATED")
        _formal(api, helper, run_dir, profile, t06a_result, retention, lineage.admission,
                runner_sha, all_pass)
        print(f"GATE_EXECUTION_STATUS={'PASS' if all_pass else 'FAIL'}")
        return 0 if all_pass else 1
    except Blocked as exc:
        return _blocked(run_dir, exc.code)
    except Exception as exc:
        return _blocked(run_dir, f"BLOCKED_EXECUTION_ERROR_{type(exc).__name__}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="External T-07 formal acceptance harness")
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--foundation-control-db", type=Path, required=True)
    parser.add_argument("--task01-db", type=Path, required=True)
    parser.add_argument("--t06a-run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    return run_gate(args.repo, args.foundation_control_db, args.task01_db,
                    args.t06a_run_dir, args.output_dir)


if __name__ == "__main__":
    raise SystemExit(main())
