"""R14 TASK-04 T-ACCEPT R5 — final INITIAL_CLASSIFICATION acceptance/admission.

Owner authorization:
The Owner explicitly confirmed the T-09 result and stated that all remaining
Device Fingerprint acceptance is accepted so the project can be completed.
This tool materializes that already-given Owner authorization only if every
exact T-ACCEPT prerequisite and final technical check passes.

R5 retains all R4 exact retained-artifact resolution and repairs only concrete graph
boundary semantics: historical prerequisite GateResultManifest artifacts and
GateProofArtifact payloads are immutable audit leaves, matching the accepted R14
F-ADMIT admission boundary and the Task-04 schema template. Their historical test
input/output refs are not current runtime-closure edges. The terminal T-ACCEPT
GateResultManifest is NOT a leaf. No candidate/profile/acceptance semantics change.

This gate:
- verifies the exact candidate commit/tree and clean worktree;
- resolves the complete mandatory Task-04 pre-acceptance gate set;
- pins the exact T-06A ClassificationRuntimeProfile;
- re-runs the exact 9/9 compatibility preflight in a fresh process;
- constructs a NEW Task04AcceptanceManifest;
- constructs INITIAL_CLASSIFICATION RuntimeProfileAdmissionManifest;
- re-runs concrete artifact dependency graph acyclicity;
- creates the immutable Owner DecisionRecord;
- atomically persists acceptance/admission lineage + final T-ACCEPT GateResult;
- DOES NOT activate the classification profile and DOES NOT change any pointer.

No production classification traffic is enabled by this gate.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import unicodedata
import uuid
from typing import Any

LAB = Path(r"C:\CaptivPortal-Lab")
REPO = LAB / "coder-task04-t09-utility-repair-a1"
RUNS = LAB / "official-runs" / "task04"
CONTROL_DB = LAB / "foundation-control-plane" / "device-fingerprint-control-plane.sqlite3"
RETAINED_SEARCH_ROOTS = (
    LAB / "official-runs",
    LAB / "gates",
    LAB / "foundation-control-plane",
    LAB / "artifacts",
)

R5_GATE = LAB / "tools" / "task04-t09-phase-b-a1-r5-20261002.py"
R5_GATE_SHA = "a80456c02b875eb5b9ef7205683473f79be0a039a18434898ad2a46d8ad0063f"
PHASE_A_LOCK = (
    LAB / "official-runs" / "task04" / "t09"
    / "phase-a-r2-upgrade-20261002T071712Z-T09-A1-01" / "phase-a-lock.json"
)
PHASE_A_LOCK_SHA = "1142010057ddaa8564fe076160f35595e84ae51c5dae6d798d5e8bbb839c6ac1"
PHASE_B_R5_LOCK = (
    LAB / "official-runs" / "task04" / "t09"
    / "phase-b-20261002T105950Z-T09-A1-R5-01" / "phase-b-lock.json"
)
PHASE_B_R5_LOCK_SHA = "93256ffa5224693a1823b0ece4bba5f7a2eb919eb022a08d59e6837a89603a05"

COMMIT = "8a39459be3ce7ed40e325736034245f0025cf249"
TREE = "e2521f27c9f91978e381bce202ab3e3c83aa6dad"
PROFILE_ID = "ClassificationRuntimeProfile:v1:sha256:1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c"
PROFILE_SHA = "1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c"
FOUNDATION_PROFILE_ID = "FoundationRuntimeProfile:v1:sha256:9287f48e01426a0440c06644821ebbbdf8f052f08d930968748f3bf6c3e9f4d5"
FOUNDATION_PROFILE_SHA = "9287f48e01426a0440c06644821ebbbdf8f052f08d930968748f3bf6c3e9f4d5"
FOUNDATION_RPM_ID = "RuntimeProfileAdmissionManifest:v1:sha256:95231fa3dee79b8d0b00a4f645664d3d80d3d4b1b6ca48fc4865191d24b12db6"
FOUNDATION_RPM_SHA = "95231fa3dee79b8d0b00a4f645664d3d80d3d4b1b6ca48fc4865191d24b12db6"
FOUNDATION_ADMISSION_ID = "FoundationAdmissionManifest:v1:sha256:44f2b26b297c7c126a7b224b8db8f88873893a0cc6819e4e18f6106af00de4ff"
FOUNDATION_ADMISSION_SHA = "44f2b26b297c7c126a7b224b8db8f88873893a0cc6819e4e18f6106af00de4ff"

T09_RESULT_ID = "GateResultManifest:v1:sha256:d231fd0729c1820788f2f708c1135f04d4891d7033c1b3aeb76591fbbe7e895e"
T09_RESULT_SHA = "d231fd0729c1820788f2f708c1135f04d4891d7033c1b3aeb76591fbbe7e895e"

MANDATORY_GATES = (
    "T-01", "T-02", "T-03", "T-04", "T-05",
    "T-06", "T-06A", "T-07", "T-08", "T-09",
)

PINNED_GATE_RESULTS = {
    "T-05": "GateResultManifest:v1:sha256:b344e1f19857c5fa5604228923b0b15aa779e9e687d5273f4fe97cd66cf59677",
    "T-06A": "GateResultManifest:v1:sha256:cd102f0fca7adb9e09ce1ff69d2109b34691e7362fd071a0617fc300547db406",
    "T-07": "GateResultManifest:v1:sha256:b38558ad35b3771cc53a422fbfe08bfef7cc92d32d106000d78da6c69b0594cb",
    "T-08": "GateResultManifest:v1:sha256:eb317ea4855a38d76407c0beda566adb4c8d06e57f729e417c2f93abb59e4862",
    "T-09": T09_RESULT_ID,
}

OWNER_AUTHORIZATION_REFERENCE = (
    "Owner explicitly confirmed the controlled T-09 result and stated that all "
    "remaining Device Fingerprint acceptance is accepted; this DecisionRecord is "
    "materialized only after the exact T-ACCEPT technical checks pass."
)

GIT = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
ARTIFACT_ID = re.compile(r"[A-Za-z][A-Za-z0-9]*:v1:sha256:[0-9a-f]{64}")
UTC_MS = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z")


class Blocked(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise Blocked(code)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    require(isinstance(value, str) and UTC_MS.fullmatch(value) is not None, "INVALID_UTC_MS")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)


def normalized(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, child in value.items():
            require(isinstance(key, str), "CANONICAL_JSON_NON_STRING_KEY")
            k = unicodedata.normalize("NFC", key)
            require(k not in out, "CANONICAL_JSON_NFC_KEY_COLLISION")
            out[k] = normalized(child)
        return out
    if isinstance(value, (list, tuple)):
        return [normalized(child) for child in value]
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if value is None or type(value) in (bool, int):
        return value
    raise Blocked("CANONICAL_JSON_UNSUPPORTED_TYPE")


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        normalized(value), ensure_ascii=True, allow_nan=False,
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    require(not path.exists(), "OUTPUT_FILE_ALREADY_EXISTS")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(canonical_json(value) + b"\n")


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    require(isinstance(value, dict), "JSON_OBJECT_REQUIRED")
    return value


def ref(content) -> dict[str, str]:
    return {"artifact_id": content.artifact_id, "content_sha256": content.content_sha256}


def document(content) -> dict:
    return {
        "artifact_type": content.artifact_type,
        "artifact_schema_version": content.artifact_schema_version,
        "artifact_id": content.artifact_id,
        "content_sha256": content.content_sha256,
        "semantic_payload": content.semantic_payload,
    }


def run_git(*args: str) -> str:
    cp = subprocess.run(
        ["git", "-C", str(REPO), *args],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    return cp.stdout.strip()


@contextmanager
def no_network():
    saved = []
    attempts = []

    def deny(*_args, **_kwargs):
        attempts.append("DENIED")
        raise Blocked("NETWORK_ATTEMPT_FORBIDDEN")

    for obj, name in (
        (socket, "create_connection"), (socket, "getaddrinfo"),
        (socket.socket, "connect"), (socket.socket, "connect_ex"),
        (socket.socket, "sendto"), (socket.socket, "sendall"), (socket.socket, "send"),
    ):
        saved.append((obj, name, getattr(obj, name)))
        setattr(obj, name, deny)
    try:
        yield attempts
    finally:
        for obj, name, original in reversed(saved):
            setattr(obj, name, original)
        require(not attempts, "NETWORK_ATTEMPT_FORBIDDEN")


def load_candidate_api():
    # Exact repository identity is verified before this is called.
    sys.path.insert(0, str(REPO))
    from app.device_fingerprint.artifact_content import (
        ArtifactContent, ArtifactRef, canonical_set, make_artifact_content,
    )
    from app.device_fingerprint.artifact_dependency_graph import (
        ArtifactDependencyNode, analyze_artifact_dependency_graph,
        build_concrete_artifact_graph, extract_direct_artifact_refs,
    )
    from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore
    from app.device_fingerprint.foundation_gate_artifacts import make_gate_result_manifest
    from app.device_fingerprint.runtime_profile_artifacts import (
        direct_artifact_refs, make_classification_runtime_profile,
        make_runtime_profile_admission_manifest,
    )
    return {
        "ArtifactContent": ArtifactContent,
        "ArtifactRef": ArtifactRef,
        "canonical_set": canonical_set,
        "make_artifact_content": make_artifact_content,
        "ArtifactDependencyNode": ArtifactDependencyNode,
        "analyze_graph": analyze_artifact_dependency_graph,
        "build_graph": build_concrete_artifact_graph,
        "extract_refs": extract_direct_artifact_refs,
        "ControlStore": DeviceFingerprintControlPlaneStore,
        "make_gate_result": make_gate_result_manifest,
        "runtime_refs": direct_artifact_refs,
        "make_crp": make_classification_runtime_profile,
        "make_rpm": make_runtime_profile_admission_manifest,
    }


def add_content(index: dict[str, Any], content) -> None:
    existing = index.get(content.artifact_id)
    if existing is not None:
        require(existing == content, "ARTIFACT_ID_CONTENT_CONFLICT")
    else:
        index[content.artifact_id] = content


def ingest_artifact_sqlite(api, index: dict[str, Any], path: Path) -> int:
    """Load immutable ArtifactContent rows from a retained classification/control SQLite DB read-only."""
    ArtifactContent = api["ArtifactContent"]
    before = sha(path)
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    count = 0
    try:
        conn.execute("PRAGMA query_only=ON")
        quick = [row[0] for row in conn.execute("PRAGMA quick_check").fetchall()]
        require(quick == ["ok"], f"ARTIFACT_SQLITE_QUICK_CHECK_FAILED:{path}")
        tables = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "artifacts" not in tables:
            return 0
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(artifacts)").fetchall()
        }
        required = {"artifact_id", "artifact_type", "content_sha256", "semantic_payload_json"}
        require(required <= columns, f"ARTIFACT_SQLITE_SCHEMA_MISMATCH:{path}")
        for row in conn.execute(
            "SELECT artifact_id,artifact_type,content_sha256,semantic_payload_json FROM artifacts"
        ):
            raw = row["semantic_payload_json"]
            if isinstance(raw, str):
                raw = raw.encode("utf-8")
            content = ArtifactContent(
                row["artifact_type"], 1, raw, row["content_sha256"], row["artifact_id"]
            )
            # Re-materialize generic content to prove content-address identity.
            rebuilt = api["make_artifact_content"](content.artifact_type, content.semantic_payload)
            require(rebuilt == content, f"ARTIFACT_SQLITE_CONTENT_IDENTITY_MISMATCH:{path}")
            add_content(index, content)
            count += 1
    finally:
        conn.close()
    require(sha(path) == before, f"ARTIFACT_SQLITE_CHANGED_DURING_READ:{path}")
    return count


def build_artifact_index(api) -> dict[str, Any]:
    index: dict[str, Any] = {}
    make = api["make_artifact_content"]
    ArtifactContent = api["ArtifactContent"]

    # Durable control-plane ArtifactContent first.
    control_count = ingest_artifact_sqlite(api, index, CONTROL_DB)
    print(f"TACCEPT_INDEX_CONTROL_DB_ARTIFACT_ROWS={control_count}")

    # Full semantic closures retained by T-07/T-09 product persistence live in
    # classification.sqlite3 files and are intentionally not duplicated as JSON.
    sqlite_paths = sorted(
        path for path in RUNS.rglob("classification.sqlite3")
        if path.is_file()
    )
    require(sqlite_paths, "RETAINED_CLASSIFICATION_SQLITE_NOT_FOUND")
    sqlite_rows = 0
    for path in sqlite_paths:
        count = ingest_artifact_sqlite(api, index, path)
        sqlite_rows += count
        print(f"TACCEPT_INDEX_CLASSIFICATION_DB={path}|ARTIFACT_ROWS={count}")
    print(f"TACCEPT_INDEX_CLASSIFICATION_DB_COUNT={len(sqlite_paths)}")
    print(f"TACCEPT_INDEX_CLASSIFICATION_ARTIFACT_ROWS={sqlite_rows}")

    # Retained Task-04 evidence.
    for path in sorted(RUNS.rglob("*.json")):
        try:
            if path.stat().st_size > 32 * 1024 * 1024:
                continue
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(raw, dict):
                continue
            if not {"artifact_type", "artifact_schema_version", "artifact_id",
                    "content_sha256", "semantic_payload"} <= set(raw):
                continue
            if raw["artifact_schema_version"] != 1 or not isinstance(raw["semantic_payload"], dict):
                continue
            content = make(raw["artifact_type"], raw["semantic_payload"])
            if (content.artifact_id != raw["artifact_id"]
                    or content.content_sha256 != raw["content_sha256"]):
                continue
            add_content(index, content)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError):
            continue
    return index


def gate_exact_candidate(gate) -> bool:
    p = gate.semantic_payload
    return (
        p.get("status") == "PASS"
        and p.get("candidate_repository_commit_sha") == COMMIT
        and p.get("candidate_repository_tree_sha") == TREE
    )


def select_prerequisite_gates(api, index: dict[str, Any], classifier_ref: dict) -> dict[str, Any]:
    validate = api["make_gate_result"]
    candidates: dict[str, list[Any]] = {g: [] for g in MANDATORY_GATES}

    for content in index.values():
        if content.artifact_type != "GateResultManifest":
            continue
        try:
            if validate(content.semantic_payload) != content:
                continue
        except Exception:
            continue
        gate_id = content.semantic_payload.get("gate_id")
        if gate_id not in candidates or not gate_exact_candidate(content):
            continue
        candidates[gate_id].append(content)

    selected: dict[str, Any] = {}
    for gate_id in MANDATORY_GATES:
        by_id = {item.artifact_id: item for item in candidates[gate_id]}
        if gate_id in PINNED_GATE_RESULTS:
            expected = PINNED_GATE_RESULTS[gate_id]
            require(expected in by_id, f"{gate_id}_PINNED_PASS_RESULT_MISSING")
            selected[gate_id] = by_id[expected]
            continue
        if gate_id == "T-06":
            # T-06 must be the PASS that produced the classifier artifact used by exact P.
            matching = []
            for item in by_id.values():
                outputs = item.semantic_payload.get("output_artifact_refs", [])
                if classifier_ref in outputs:
                    matching.append(item)
            require(len(matching) == 1, "T-06_EXACT_CLASSIFIER_GATE_AMBIGUOUS_OR_MISSING")
            selected[gate_id] = matching[0]
            continue
        require(len(by_id) == 1, f"{gate_id}_EXACT_PASS_RESULT_AMBIGUOUS_OR_MISSING")
        selected[gate_id] = next(iter(by_id.values()))

    # Exact tested-profile use requirements for profile-dependent gates.
    for gate_id in ("T-05", "T-06A", "T-07", "T-08", "T-09"):
        require(
            PROFILE_ID in json.dumps(
                selected[gate_id].semantic_payload, sort_keys=True, separators=(",", ":")
            ),
            f"{gate_id}_EXACT_PROFILE_NOT_BOUND",
        )
    return selected


def make_task04_acceptance_manifest(api, payload: dict[str, Any]):
    expected = {
        "foundation_admission_manifest",
        "task04_candidate_repository_commit_sha",
        "task04_candidate_repository_tree_sha",
        "classifier_artifact_manifest",
        "tested_classification_runtime_profile",
        "mandatory_pre_acceptance_task04_gate_ids",
        "pre_acceptance_task04_gate_result_manifests",
        "accepted_classification_result_schema_version",
        "accepted_persistence_audit_contract_version",
        "accepted_product_validation_comparison_records",
    }
    require(isinstance(payload, dict) and set(payload) == expected, "TASK04_ACCEPTANCE_SHAPE")
    ArtifactRef = api["ArtifactRef"]
    canonical_set = api["canonical_set"]

    def typed_ref(value: Any, kind: str) -> dict[str, str]:
        r = ArtifactRef.from_dict(value)
        require(r.artifact_id.startswith(f"{kind}:v1:sha256:"), f"TASK04_ACCEPTANCE_REF_{kind}")
        return r.as_dict()

    require(GIT.fullmatch(payload["task04_candidate_repository_commit_sha"]) is not None,
            "TASK04_ACCEPTANCE_COMMIT")
    require(GIT.fullmatch(payload["task04_candidate_repository_tree_sha"]) is not None,
            "TASK04_ACCEPTANCE_TREE")
    require(payload["task04_candidate_repository_commit_sha"] == COMMIT
            and payload["task04_candidate_repository_tree_sha"] == TREE,
            "TASK04_ACCEPTANCE_CANDIDATE_MISMATCH")

    gate_ids = payload["mandatory_pre_acceptance_task04_gate_ids"]
    require(isinstance(gate_ids, list) and all(isinstance(x, str) and x for x in gate_ids),
            "TASK04_ACCEPTANCE_GATE_IDS")
    gate_ids = canonical_set(gate_ids, lambda x: x)
    require(gate_ids == sorted(MANDATORY_GATES), "TASK04_ACCEPTANCE_GATE_SET")

    gate_refs = payload["pre_acceptance_task04_gate_result_manifests"]
    require(isinstance(gate_refs, list), "TASK04_ACCEPTANCE_GATE_REFS")
    gate_refs = canonical_set(
        [typed_ref(x, "GateResultManifest") for x in gate_refs],
        lambda x: x["artifact_id"],
    )

    comparisons = payload["accepted_product_validation_comparison_records"]
    require(isinstance(comparisons, list), "TASK04_ACCEPTANCE_COMPARISON_REFS")
    comparisons = canonical_set(
        [typed_ref(x, "ProductValidationComparisonRecord") for x in comparisons],
        lambda x: x["artifact_id"],
    )

    require(type(payload["accepted_classification_result_schema_version"]) is int
            and payload["accepted_classification_result_schema_version"] > 0,
            "TASK04_ACCEPTANCE_RESULT_SCHEMA_VERSION")
    require(isinstance(payload["accepted_persistence_audit_contract_version"], str)
            and bool(payload["accepted_persistence_audit_contract_version"]),
            "TASK04_ACCEPTANCE_PERSISTENCE_CONTRACT")

    normalized_payload = {
        **payload,
        "foundation_admission_manifest": typed_ref(
            payload["foundation_admission_manifest"], "FoundationAdmissionManifest"),
        "classifier_artifact_manifest": typed_ref(
            payload["classifier_artifact_manifest"], "ClassifierArtifactManifest"),
        "tested_classification_runtime_profile": typed_ref(
            payload["tested_classification_runtime_profile"], "ClassificationRuntimeProfile"),
        "mandatory_pre_acceptance_task04_gate_ids": gate_ids,
        "pre_acceptance_task04_gate_result_manifests": gate_refs,
        "accepted_product_validation_comparison_records": comparisons,
    }
    return api["make_artifact_content"]("Task04AcceptanceManifest", normalized_payload)


def load_t09_comparisons_and_result_version(index: dict[str, Any]):
    require(sha(PHASE_B_R5_LOCK) == PHASE_B_R5_LOCK_SHA, "T09_R5_PHASE_B_LOCK_CHANGED")
    lock = read_json(PHASE_B_R5_LOCK)
    require(lock.get("phase") == "B" and lock.get("state") == "OWNER_REVIEW_REQUIRED"
            and lock.get("policy_outcome") == "PASS", "T09_R5_PHASE_B_STATE")
    entries = lock.get("entries")
    require(isinstance(entries, list) and len(entries) == 2, "T09_R5_ENTRY_COUNT")

    comparisons = []
    result_versions = set()
    labels = set()
    for entry in entries:
        labels.add(entry.get("controlled_device_lab_label"))
        cmp_ref = entry.get("comparison")
        result_ref = entry.get("result")
        require(isinstance(cmp_ref, dict) and isinstance(result_ref, dict),
                "T09_R5_ENTRY_REFS")
        comparison = index.get(cmp_ref.get("artifact_id"))
        result = index.get(result_ref.get("artifact_id"))
        require(comparison is not None and comparison.artifact_type == "ProductValidationComparisonRecord"
                and ref(comparison) == cmp_ref, "T09_R5_COMPARISON_NOT_RETRIEVABLE")
        require(result is not None and result.artifact_type == "ClassificationResult"
                and ref(result) == result_ref, "T09_R5_RESULT_NOT_RETRIEVABLE")
        require(comparison.semantic_payload.get("overall_validation_outcome") == "PASS",
                "T09_R5_COMPARISON_NOT_PASS")
        comparisons.append(comparison)
        result_versions.add(result.artifact_schema_version)

    require(labels == {"OWNER_ANDROID", "OWNER_WINDOWS_LAPTOP"}, "T09_R5_DEVICE_SET")
    require(result_versions == {1}, "CLASSIFICATION_RESULT_SCHEMA_VERSION_AMBIGUOUS")
    return comparisons, 1


def load_foundation_lineage(api):
    Store = api["ControlStore"]
    store = Store(CONTROL_DB)
    pointer = store.get_active_pointer("foundation")
    require(pointer is not None, "FOUNDATION_ACTIVE_POINTER_MISSING")
    require(pointer.runtime_profile_id == FOUNDATION_PROFILE_ID
            and pointer.runtime_profile_digest == FOUNDATION_PROFILE_SHA,
            "FOUNDATION_ACTIVE_PROFILE_MISMATCH")

    foundation_profile = store.load_artifact(FOUNDATION_PROFILE_ID, FOUNDATION_PROFILE_SHA)
    foundation_rpm = store.load_artifact(FOUNDATION_RPM_ID, FOUNDATION_RPM_SHA)
    foundation_admission = store.load_artifact(FOUNDATION_ADMISSION_ID, FOUNDATION_ADMISSION_SHA)
    require(foundation_rpm.semantic_payload["profile_kind"] == "foundation"
            and foundation_rpm.semantic_payload["candidate_profile"] == ref(foundation_profile)
            and foundation_rpm.semantic_payload["foundation_admission_manifest"] == ref(foundation_admission),
            "FOUNDATION_LINEAGE_MISMATCH")
    require(store.get_active_pointer("classification") is None,
            "CLASSIFICATION_POINTER_MUST_BE_ABSENT_BEFORE_INITIAL_ACCEPTANCE")

    # No previously admitted classification RPM for this exact candidate.
    with store._connect() as conn:
        prior = []
        for row in conn.execute(
            "SELECT artifact_id,content_sha256,semantic_payload_json FROM artifacts "
            "WHERE artifact_type='RuntimeProfileAdmissionManifest'"
        ):
            raw = row["semantic_payload_json"]
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            payload = json.loads(raw)
            if payload.get("profile_kind") == "classification" and payload.get("candidate_profile") == {
                "artifact_id": PROFILE_ID, "content_sha256": PROFILE_SHA
            }:
                prior.append(row["artifact_id"])
        require(not prior, "CLASSIFICATION_PROFILE_ALREADY_ADMITTED")
    return store, foundation_profile, foundation_rpm, foundation_admission


def run_compatibility_preflight(output: Path) -> dict:
    require(R5_GATE.is_file() and sha(R5_GATE) == R5_GATE_SHA, "R5_GATE_IDENTITY_CHANGED")
    require(PHASE_A_LOCK.is_file() and sha(PHASE_A_LOCK) == PHASE_A_LOCK_SHA,
            "PHASE_A_LOCK_IDENTITY_CHANGED")
    compat_dir = output / "compatibility-preflight"
    require(not compat_dir.exists(), "COMPATIBILITY_OUTPUT_EXISTS")
    parent_sha = sha(CONTROL_DB)
    cmd = [
        sys.executable, "-I", "-B", str(R5_GATE), "PRECHECK",
        "--repo", str(REPO),
        "--foundation-db", str(CONTROL_DB),
        "--phase-a-lock", str(PHASE_A_LOCK),
        "--phase-a-lock-sha256", PHASE_A_LOCK_SHA,
        "--output", str(compat_dir),
        "--runner-sha256", R5_GATE_SHA,
        "--parent-foundation-sha256", parent_sha,
    ]
    cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(cp.stdout, end="")
    require(cp.returncode == 0, "TACCEPT_COMPATIBILITY_PREFLIGHT_BLOCKED")
    report_path = compat_dir / "compatibility-preflight.json"
    require(report_path.is_file(), "TACCEPT_COMPATIBILITY_REPORT_MISSING")
    report = read_json(report_path)
    require(report.get("status") == "PASS"
            and report.get("candidate_commit") == COMMIT
            and report.get("candidate_tree") == TREE
            and report.get("profile") == {"artifact_id": PROFILE_ID, "content_sha256": PROFILE_SHA}
            and isinstance(report.get("checks"), list)
            and len(report["checks"]) == 9
            and all(isinstance(x, dict) and x.get("status") == "PASS" for x in report["checks"]),
            "TACCEPT_COMPATIBILITY_REPORT_NOT_PASS")
    return {
        "path": report_path,
        "sha256": sha(report_path),
        "report": report,
    }


def _artifact_from_json_candidate(api, raw: Any, expected_id: str):
    """Return exact ArtifactContent from an envelope or raw semantic payload, else None."""
    make = api["make_artifact_content"]
    expected_type = expected_id.split(":", 1)[0]
    if not isinstance(raw, dict):
        return None

    # Canonical retained envelope.
    if (
        raw.get("artifact_id") == expected_id
        and raw.get("artifact_type") == expected_type
        and raw.get("artifact_schema_version") == 1
        and isinstance(raw.get("semantic_payload"), dict)
    ):
        try:
            content = make(expected_type, raw["semantic_payload"])
        except Exception:
            return None
        if content.artifact_id == expected_id and content.content_sha256 == raw.get("content_sha256"):
            return content

    # Some older retained gates stored the exact semantic payload without an envelope.
    try:
        content = make(expected_type, raw)
    except Exception:
        return None
    return content if content.artifact_id == expected_id else None


def _walk_json_for_artifact(api, value: Any, expected_id: str):
    if isinstance(value, dict):
        direct = _artifact_from_json_candidate(api, value, expected_id)
        if direct is not None:
            return direct
        for child in value.values():
            found = _walk_json_for_artifact(api, child, expected_id)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _walk_json_for_artifact(api, child, expected_id)
            if found is not None:
                return found
    return None


def locate_retained_artifact(api, index: dict[str, Any], artifact_id: str, expected_sha: str):
    """Resolve one missing exact artifact from retained audit stores only.

    Search order is deterministic: retained JSON first, then SQLite artifact stores.
    Every discovered artifact is content-address verified. No source is modified.
    """
    existing = index.get(artifact_id)
    if existing is not None:
        require(existing.content_sha256 == expected_sha, "LAZY_RESOLVER_EXISTING_DIGEST_MISMATCH")
        return existing

    require(ARTIFACT_ID.fullmatch(artifact_id) is not None, "LAZY_RESOLVER_INVALID_ARTIFACT_ID")
    require(SHA256.fullmatch(expected_sha) is not None and artifact_id.endswith(expected_sha),
            "LAZY_RESOLVER_INVALID_EXPECTED_DIGEST")

    # 1) JSON retained evidence. We accept either an ArtifactContent envelope or the
    # exact raw semantic payload if it reconstructs to the requested content address.
    for root in RETAINED_SEARCH_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.json")):
            try:
                if path.stat().st_size > 64 * 1024 * 1024:
                    continue
                raw = json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            found = _walk_json_for_artifact(api, raw, artifact_id)
            if found is None:
                continue
            require(found.content_sha256 == expected_sha, "LAZY_RESOLVER_JSON_DIGEST_MISMATCH")
            add_content(index, found)
            print(f"TACCEPT_LAZY_ARTIFACT_RESOLVED={artifact_id}|SOURCE_JSON={path}")
            return found

    # 2) SQLite retained artifact stores. Probe schema read-only; run quick_check and
    # source SHA-before/after only on the DB that actually contains the requested row.
    sqlite_candidates = []
    seen = set()
    for root in RETAINED_SEARCH_ROOTS:
        if not root.exists():
            continue
        for pattern in ("*.sqlite3", "*.sqlite", "*.db"):
            for path in root.rglob(pattern):
                if path.is_file():
                    resolved = path.resolve()
                    if resolved not in seen:
                        seen.add(resolved)
                        sqlite_candidates.append(path)
    for path in sorted(sqlite_candidates):
        try:
            conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=1)
            conn.row_factory = sqlite3.Row
            try:
                conn.execute("PRAGMA query_only=ON")
                table = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='artifacts'"
                ).fetchone()
                if table is None:
                    continue
                columns = {
                    row[1] for row in conn.execute("PRAGMA table_info(artifacts)").fetchall()
                }
                required = {"artifact_id", "artifact_type", "content_sha256", "semantic_payload_json"}
                if not required <= columns:
                    continue
                row = conn.execute(
                    "SELECT artifact_id,artifact_type,content_sha256,semantic_payload_json "
                    "FROM artifacts WHERE artifact_id=?",
                    (artifact_id,),
                ).fetchone()
                if row is None:
                    continue

                before = sha(path)
                quick = [r[0] for r in conn.execute("PRAGMA quick_check").fetchall()]
                require(quick == ["ok"], f"LAZY_RESOLVER_SQLITE_QUICK_CHECK_FAILED:{path}")
                raw_payload = row["semantic_payload_json"]
                if isinstance(raw_payload, str):
                    raw_payload = raw_payload.encode("utf-8")
                content = api["ArtifactContent"](
                    row["artifact_type"], 1, raw_payload, row["content_sha256"], row["artifact_id"]
                )
                rebuilt = api["make_artifact_content"](
                    content.artifact_type, content.semantic_payload
                )
                require(rebuilt == content, f"LAZY_RESOLVER_SQLITE_CONTENT_IDENTITY:{path}")
                require(content.artifact_id == artifact_id
                        and content.content_sha256 == expected_sha,
                        "LAZY_RESOLVER_SQLITE_DIGEST_MISMATCH")
            finally:
                conn.close()
            require(sha(path) == before, f"LAZY_RESOLVER_SQLITE_CHANGED:{path}")
            add_content(index, content)
            print(f"TACCEPT_LAZY_ARTIFACT_RESOLVED={artifact_id}|SOURCE_SQLITE={path}")
            return content
        except sqlite3.Error:
            continue

    raise Blocked(f"AUDIT_LINEAGE_NOT_RETRIEVABLE:{artifact_id}")


def historical_gate_leaf_ids(foundation_admission, task04_gates: dict[str, Any]) -> frozenset[str]:
    """Return only already-completed prerequisite GateResultManifest identities.

    R14 Task-04 concrete graph semantics treat PrerequisiteGateResultManifest as a
    leaf. The accepted Foundation implementation applies the same boundary to its
    prerequisite gates; GateProofArtifact is also an immutable audit leaf.
    """
    refs = foundation_admission.semantic_payload.get(
        "pre_admission_gate_result_manifests"
    )
    require(isinstance(refs, list) and refs,
            "FOUNDATION_PREREQUISITE_GATE_REFS_MISSING")

    ids: set[str] = set()
    for value in refs:
        require(
            isinstance(value, dict)
            and set(value) == {"artifact_id", "content_sha256"}
            and isinstance(value["artifact_id"], str)
            and value["artifact_id"].startswith("GateResultManifest:v1:sha256:")
            and isinstance(value["content_sha256"], str)
            and value["artifact_id"].endswith(value["content_sha256"]),
            "FOUNDATION_PREREQUISITE_GATE_REF_INVALID",
        )
        ids.add(value["artifact_id"])

    ids.update(gate.artifact_id for gate in task04_gates.values())
    return frozenset(ids)


def bounded_direct_refs(api, content, historical_gate_ids: frozenset[str]):
    # Exact R14 boundary:
    # - completed prerequisite GateResultManifests are immutable audit leaves;
    # - GateProofArtifact payloads are immutable audit leaves;
    # - the newly constructed terminal T-ACCEPT GateResult is not in
    #   historical_gate_ids and therefore keeps its direct dependency edges.
    if content.artifact_id in historical_gate_ids or content.artifact_type == "GateProofArtifact":
        return ()
    return api["extract_refs"](content)


def resolve_closure(
    api,
    index: dict[str, Any],
    seeds: list[Any],
    historical_gate_ids: frozenset[str],
) -> dict[str, Any]:
    closure: dict[str, Any] = {}
    pending = list(seeds)
    while pending:
        content = pending.pop()
        old = closure.get(content.artifact_id)
        if old is not None:
            require(old == content, "CONCRETE_GRAPH_ARTIFACT_CONFLICT")
            continue
        closure[content.artifact_id] = content
        for reference in bounded_direct_refs(api, content, historical_gate_ids):
            target = index.get(reference.artifact_id)
            if target is None:
                target = locate_retained_artifact(
                    api, index, reference.artifact_id, reference.content_sha256
                )
            require(target.content_sha256 == reference.content_sha256,
                    "CONCRETE_GRAPH_DEPENDENCY_DIGEST_MISMATCH")
            pending.append(target)
    return closure


def build_bounded_concrete_graph(
    api,
    closure: dict[str, Any],
    historical_gate_ids: frozenset[str],
):
    Node = api["ArtifactDependencyNode"]
    nodes = []
    for artifact_id, content in sorted(closure.items()):
        refs = bounded_direct_refs(api, content, historical_gate_ids)
        for reference in refs:
            target = closure.get(reference.artifact_id)
            require(target is not None, "CONCRETE_GRAPH_DEPENDENCY_MISSING")
            require(target.content_sha256 == reference.content_sha256,
                    "CONCRETE_GRAPH_DEPENDENCY_DIGEST_MISMATCH")
        nodes.append(Node(
            artifact_id,
            content.artifact_type,
            "CONCRETE",
            tuple(reference.artifact_id for reference in refs),
        ))
    return tuple(nodes)


def owner_decision(acceptance, rpm, gates, comparisons, foundation_rpm, foundation_admission) -> dict:
    decided_at = canonical_now()
    ids = {
        acceptance.artifact_id, rpm.artifact_id, PROFILE_ID,
        foundation_rpm.artifact_id, foundation_admission.artifact_id,
        *(item.artifact_id for item in gates.values()),
        *(item.artifact_id for item in comparisons),
    }
    unsigned = {
        "decision_record_id": str(uuid.uuid4()),
        "decision_subject_type": "TASK04_ACCEPTANCE",
        "decision_subject_id": acceptance.artifact_id,
        "decision": "ACCEPT",
        "decided_at_utc": decided_at,
        "actor_role": "OWNER",
        "referenced_artifact_ids": sorted(ids),
        "referenced_gate_ids": ["T-ACCEPT"],
        "reason_reference_text": OWNER_AUTHORIZATION_REFERENCE,
    }
    return {
        **unsigned,
        "record_sha256": hashlib.sha256(canonical_json(unsigned)).hexdigest(),
    }


def persist_acceptance_atomically(
    api, store, classifier, crp, gates, comparisons, acceptance, rpm, final_gate
):
    extract_refs = api["extract_refs"]
    runtime_refs = api["runtime_refs"]

    # Historical pre-acceptance gate results and ProductValidationComparisonRecord
    # bytes are retained as immutable audit leaves. Task04AcceptanceManifest
    # explicitly binds them; production execution does not traverse their full
    # historical test graphs.
    leaf_contents = [
        *[gates[g] for g in MANDATORY_GATES],
        *comparisons,
        classifier,
    ]

    crp_refs = runtime_refs(crp)
    acceptance_refs = extract_refs(acceptance)
    rpm_refs = runtime_refs(rpm)
    final_gate_refs = extract_refs(final_gate)

    # Fail closed on the runtime-profile declared dependency contract.
    require(tuple(crp_refs) == tuple(runtime_refs(crp)), "CRP_DEPENDENCY_REF_INSTABILITY")
    require(tuple(rpm_refs) == tuple(runtime_refs(rpm)), "RPM_DEPENDENCY_REF_INSTABILITY")

    with store._connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            before_class_pointer = conn.execute(
                "SELECT 1 FROM active_pointers WHERE profile_kind='classification'"
            ).fetchone()
            require(before_class_pointer is None, "CLASSIFICATION_POINTER_APPEARED_BEFORE_COMMIT")
            before_class_activations = conn.execute(
                "SELECT COUNT(*) FROM activations WHERE profile_kind='classification'"
            ).fetchone()[0]

            for content in leaf_contents:
                store._put(conn, content, ())
            store._put(conn, crp, crp_refs)
            store._put(conn, acceptance, acceptance_refs)
            store._put(conn, rpm, rpm_refs)
            store._put(conn, final_gate, final_gate_refs)

            # Full admission closure must already be resolvable before commit.
            store._closure(conn, rpm)
            store._closure(conn, crp)

            after_class_pointer = conn.execute(
                "SELECT 1 FROM active_pointers WHERE profile_kind='classification'"
            ).fetchone()
            after_class_activations = conn.execute(
                "SELECT COUNT(*) FROM activations WHERE profile_kind='classification'"
            ).fetchone()[0]
            require(after_class_pointer is None, "TACCEPT_MUST_NOT_ACTIVATE_CLASSIFICATION")
            require(after_class_activations == before_class_activations,
                    "TACCEPT_CREATED_CLASSIFICATION_ACTIVATION")
            conn.commit()
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        output = args.output.resolve()
        require(output.is_relative_to(LAB.resolve()), "OUTPUT_OUTSIDE_LAB")
        require(not output.exists(), "OUTPUT_ALREADY_EXISTS")
        output.mkdir(parents=True)

        for p in (REPO, RUNS, CONTROL_DB, R5_GATE, PHASE_A_LOCK, PHASE_B_R5_LOCK):
            require(p.exists(), f"REQUIRED_PATH_MISSING:{p}")

        runner_sha = sha(Path(__file__))
        print(f"TACCEPT_RUNNER_SHA256={runner_sha}")
        print("TACCEPT_PREVIOUS_R2_STATUS=BLOCKED_BEFORE_ACCEPTANCE_WRITE")
        print("TACCEPT_PREVIOUS_R2_BLOCKER=INCOMPLETE_RETAINED_FOUNDATION_ARTIFACT_RESOLUTION")
        print("TACCEPT_PREVIOUS_R3_STATUS=BLOCKED_BEFORE_ACCEPTANCE_WRITE")
        print("TACCEPT_PREVIOUS_R3_BLOCKER=RETAINED_SEARCH_ROOT_OMITTED_LAB_ARTIFACTS")
        print("TACCEPT_FORENSICS_TARGET_ARTIFACT_RETRIEVABLE=YES")
        print("TACCEPT_R4_REPAIR=ADD_LAB_ARTIFACTS_TO_EXACT_LAZY_RESOLVER")
        print("TACCEPT_PREVIOUS_R4_STATUS=BLOCKED_BEFORE_ACCEPTANCE_WRITE")
        print("TACCEPT_PREVIOUS_R4_BLOCKER=OVEREXPANDED_HISTORICAL_GATE_PROOF_INPUTS")
        print("TACCEPT_R5_REPAIR=R14_BOUNDED_HISTORICAL_AUDIT_GRAPH")

        commit = run_git("rev-parse", "HEAD")
        tree = run_git("show", "-s", "--format=%T", "HEAD")
        status = run_git("status", "--porcelain")
        print(f"CANDIDATE_COMMIT={commit}")
        print(f"CANDIDATE_TREE={tree}")
        print(f"CANDIDATE_CLEAN={'YES' if not status else 'NO'}")
        require(commit == COMMIT and tree == TREE and not status, "CANDIDATE_IDENTITY_CHANGED")

        api = load_candidate_api()
        index = build_artifact_index(api)
        print(f"TACCEPT_ARTIFACT_INDEX_COUNT={len(index)}")

        crp = index.get(PROFILE_ID)
        require(crp is not None and crp.artifact_type == "ClassificationRuntimeProfile"
                and crp.content_sha256 == PROFILE_SHA
                and api["make_crp"](crp.semantic_payload) == crp,
                "EXACT_CLASSIFICATION_RUNTIME_PROFILE_MISSING")
        require(crp.semantic_payload["foundation_runtime_profile"] == {
            "artifact_id": FOUNDATION_PROFILE_ID, "content_sha256": FOUNDATION_PROFILE_SHA
        }, "CRP_FOUNDATION_PROFILE_MISMATCH")

        classifier_ref = crp.semantic_payload["classifier_artifact_manifest"]
        classifier = index.get(classifier_ref["artifact_id"])
        require(classifier is not None and classifier.artifact_type == "ClassifierArtifactManifest"
                and ref(classifier) == classifier_ref,
                "EXACT_CLASSIFIER_MANIFEST_MISSING")

        gates = select_prerequisite_gates(api, index, classifier_ref)
        print("TACCEPT_MANDATORY_GATE_SET=" + ",".join(MANDATORY_GATES))
        for gid in MANDATORY_GATES:
            print(f"{gid}_RESULT={gates[gid].artifact_id}")

        # T-09 exact final result is hard-pinned, not merely any PASS.
        require(gates["T-09"].artifact_id == T09_RESULT_ID
                and gates["T-09"].content_sha256 == T09_RESULT_SHA,
                "T09_FINAL_RESULT_IDENTITY_MISMATCH")

        comparisons, result_schema_version = load_t09_comparisons_and_result_version(index)
        print(f"ACCEPTED_CLASSIFICATION_RESULT_SCHEMA_VERSION={result_schema_version}")
        print("ACCEPTED_PRODUCT_VALIDATION_COMPARISONS="
              + ",".join(sorted(x.artifact_id for x in comparisons)))

        persistence_contract = gates["T-07"].semantic_payload["gate_contract_version"]
        require(isinstance(persistence_contract, str) and persistence_contract,
                "T07_PERSISTENCE_CONTRACT_VERSION_MISSING")
        print(f"ACCEPTED_PERSISTENCE_AUDIT_CONTRACT_VERSION={persistence_contract}")

        store, foundation_profile, foundation_rpm, foundation_admission = load_foundation_lineage(api)
        print(f"FOUNDATION_ACTIVE_PROFILE={foundation_profile.artifact_id}")
        print(f"FOUNDATION_RPM={foundation_rpm.artifact_id}")
        print(f"FOUNDATION_ADMISSION={foundation_admission.artifact_id}")
        print("CLASSIFICATION_ACTIVE_POINTER_BEFORE=ABSENT")

        accepted_foundation_ttl_ref = foundation_admission.semantic_payload.get(
            "ttl_capture_placement_proof"
        )
        require(
            isinstance(accepted_foundation_ttl_ref, dict)
            and set(accepted_foundation_ttl_ref) == {"artifact_id", "content_sha256"},
            "FOUNDATION_ACCEPTED_TTL_REF_INVALID",
        )
        accepted_foundation_ttl = store.load_artifact(
            accepted_foundation_ttl_ref["artifact_id"],
            accepted_foundation_ttl_ref["content_sha256"],
        )
        require(
            accepted_foundation_ttl is not None
            and accepted_foundation_ttl.artifact_type == "TTLCapturePlacementProof",
            "FOUNDATION_ACCEPTED_TTL_NOT_RETRIEVABLE",
        )
        require(
            foundation_profile.semantic_payload.get("ttl_capture_placement_proof")
            == accepted_foundation_ttl_ref,
            "FOUNDATION_PROFILE_TTL_REF_MISMATCH",
        )
        origin_ref = foundation_admission.semantic_payload.get("origin_runtime_admission")
        require(
            isinstance(origin_ref, dict)
            and set(origin_ref) == {"artifact_id", "content_sha256"},
            "FOUNDATION_ORIGIN_REF_INVALID",
        )
        origin = store.load_artifact(origin_ref["artifact_id"], origin_ref["content_sha256"])
        require(origin is not None and origin.artifact_type == "OriginRuntimeAdmission",
                "FOUNDATION_ORIGIN_NOT_RETRIEVABLE")
        require(
            origin.semantic_payload.get("ttl_capture_placement_proof")
            == accepted_foundation_ttl_ref,
            "FOUNDATION_ORIGIN_TTL_REF_MISMATCH",
        )
        print(
            "TACCEPT_ACCEPTED_FOUNDATION_TTL_PROOF="
            f"{accepted_foundation_ttl.artifact_id}"
        )

        historical_gate_ids = historical_gate_leaf_ids(foundation_admission, gates)
        print(f"TACCEPT_HISTORICAL_GATE_LEAF_COUNT={len(historical_gate_ids)}")
        print("TACCEPT_HISTORICAL_GATEPROOF_POLICY=OPAQUE_AUDIT_LEAF")

        control_before = sha(CONTROL_DB)
        compatibility = run_compatibility_preflight(output)
        require(sha(CONTROL_DB) == control_before, "CONTROL_DB_CHANGED_BY_COMPATIBILITY_PREFLIGHT")
        print("TACCEPT_COMPATIBILITY_9_OF_9=PASS")
        print(f"TACCEPT_COMPATIBILITY_REPORT_SHA256={compatibility['sha256']}")

        gate_refs = [ref(gates[g]) for g in MANDATORY_GATES]
        comparison_refs = [ref(x) for x in comparisons]

        acceptance = make_task04_acceptance_manifest(api, {
            "foundation_admission_manifest": ref(foundation_admission),
            "task04_candidate_repository_commit_sha": COMMIT,
            "task04_candidate_repository_tree_sha": TREE,
            "classifier_artifact_manifest": ref(classifier),
            "tested_classification_runtime_profile": ref(crp),
            "mandatory_pre_acceptance_task04_gate_ids": list(MANDATORY_GATES),
            "pre_acceptance_task04_gate_result_manifests": gate_refs,
            "accepted_classification_result_schema_version": result_schema_version,
            "accepted_persistence_audit_contract_version": persistence_contract,
            "accepted_product_validation_comparison_records": comparison_refs,
        })

        rpm = api["make_rpm"]({
            "runtime_profile_admission_contract_version": 1,
            "profile_kind": "classification",
            "candidate_profile": ref(crp),
            "previous_active_profile": None,
            "expected_previous_activation_record_id": None,
            "expected_previous_activation_generation_id": None,
            "update_class": "INITIAL_CLASSIFICATION",
            "prerequisite_gate_results": gate_refs,
            "compatibility_validation_result": "PASS",
            "candidate_repository_commit_sha": COMMIT,
            "candidate_repository_tree_sha": TREE,
            "foundation_admission_manifest": ref(foundation_admission),
            "task04_acceptance_manifest": ref(acceptance),
            "foundation_runtime_profile_admission_manifest": ref(foundation_rpm),
        })

        # The acceptance and RPM must not mutate exact P.
        require(ref(crp) == {
            "artifact_id": PROFILE_ID, "content_sha256": PROFILE_SHA
        }, "PROFILE_REBUILT_AFTER_T09")

        # Add newly constructed artifacts to the resolver before concrete graph analysis.
        add_content(index, acceptance)
        add_content(index, rpm)

        seeds = [
            crp, classifier, foundation_profile, foundation_rpm, foundation_admission,
            acceptance, rpm, *gates.values(), *comparisons,
        ]
        closure = resolve_closure(api, index, seeds, historical_gate_ids)
        nodes = build_bounded_concrete_graph(api, closure, historical_gate_ids)
        graph = api["analyze_graph"](nodes)
        require(len(graph.topological_order) == len(nodes), "CONCRETE_GRAPH_NOT_ACYCLIC")

        graph_report = {
            "report_schema_version": 1,
            "scope": "T-ACCEPT_PRE_FINAL_GATE",
            "candidate_commit": COMMIT,
            "candidate_tree": TREE,
            "classification_runtime_profile": ref(crp),
            "task04_acceptance_manifest": ref(acceptance),
            "classification_runtime_profile_admission_manifest": ref(rpm),
            "concrete_node_count": len(nodes),
            "concrete_edge_count": len(graph.edges),
            "topological_order": list(graph.topological_order),
            "status": "PASS",
        }
        graph_path = output / "taccept-concrete-acyclicity-report.json"
        write_json(graph_path, graph_report)
        print(f"TACCEPT_CONCRETE_GRAPH_NODE_COUNT={len(nodes)}")
        print(f"TACCEPT_CONCRETE_GRAPH_EDGE_COUNT={len(graph.edges)}")
        print("TACCEPT_CONCRETE_GRAPH_ACYCLIC=PASS")

        acceptance_report = {
            "report_schema_version": 1,
            "gate_id": "T-ACCEPT",
            "candidate_commit": COMMIT,
            "candidate_tree": TREE,
            "classification_runtime_profile": ref(crp),
            "classifier_artifact_manifest": ref(classifier),
            "foundation_runtime_profile": ref(foundation_profile),
            "foundation_runtime_profile_admission_manifest": ref(foundation_rpm),
            "foundation_admission_manifest": ref(foundation_admission),
            "mandatory_pre_acceptance_gate_results": {
                gid: ref(gates[gid]) for gid in MANDATORY_GATES
            },
            "accepted_product_validation_comparison_records": comparison_refs,
            "accepted_classification_result_schema_version": result_schema_version,
            "accepted_persistence_audit_contract_version": persistence_contract,
            "compatibility_report_sha256": compatibility["sha256"],
            "concrete_acyclicity_report_sha256": sha(graph_path),
            "update_class": "INITIAL_CLASSIFICATION",
            "classification_active_pointer_before": None,
            "production_activation": False,
            "status": "PASS",
        }
        acceptance_report_path = output / "taccept-acceptance-report.json"
        write_json(acceptance_report_path, acceptance_report)

        # Materialize the Owner decision only after every technical T-ACCEPT check above passed.
        decision = owner_decision(
            acceptance, rpm, gates, comparisons, foundation_rpm, foundation_admission
        )
        decision_path = output / "owner-decision.json"
        write_json(decision_path, decision)
        unsigned = {k: v for k, v in decision.items() if k != "record_sha256"}
        require(
            hashlib.sha256(canonical_json(unsigned)).hexdigest() == decision["record_sha256"],
            "OWNER_DECISION_DIGEST_MISMATCH",
        )
        print(f"TACCEPT_OWNER_DECISION_RECORD_ID={decision['decision_record_id']}")
        print(f"TACCEPT_OWNER_DECISION_RECORD_SHA256={decision['record_sha256']}")
        print("TACCEPT_OWNER_DECISION=ACCEPT")

        evidence_refs = [
            {
                "evidence_label": "TACCEPT_COMPATIBILITY_9_OF_9",
                "file_sha256": compatibility["sha256"],
                "media_type": "application/json",
                "path_or_reference": str(compatibility["path"]),
            },
            {
                "evidence_label": "TACCEPT_CONCRETE_ACYCLICITY",
                "file_sha256": sha(graph_path),
                "media_type": "application/json",
                "path_or_reference": str(graph_path),
            },
            {
                "evidence_label": "TACCEPT_ACCEPTANCE_REPORT",
                "file_sha256": sha(acceptance_report_path),
                "media_type": "application/json",
                "path_or_reference": str(acceptance_report_path),
            },
            {
                "evidence_label": "TACCEPT_OWNER_DECISION",
                "file_sha256": sha(decision_path),
                "media_type": "application/json",
                "path_or_reference": str(decision_path),
            },
        ]

        fam_payload = foundation_admission.semantic_payload
        final_gate = api["make_gate_result"]({
            "gate_id": "T-ACCEPT",
            "gate_contract_version": "R14-T-ACCEPT-v1",
            "status": "PASS",
            "candidate_repository_commit_sha": COMMIT,
            "candidate_repository_tree_sha": TREE,
            "input_artifact_refs": [
                *gate_refs,
                ref(crp), ref(classifier), ref(foundation_admission), ref(foundation_rpm),
                *comparison_refs,
            ],
            "output_artifact_refs": [ref(acceptance), ref(rpm)],
            "retained_evidence_refs": evidence_refs,
            "proof_execution_identity": {
                "execution_id": str(uuid.uuid4()),
                "executor_kind": "EXTERNAL_TECHLEAD_ACCEPTANCE_TOOL",
                "repository_commit_sha": COMMIT,
                "repository_tree_sha": TREE,
                "procedure_or_test_suite_id": "R14-T-ACCEPT-INITIAL-CLASSIFICATION-v1",
                "environment_identity": "OWNER_WINDOWS_LAB_TASK04_TACCEPT",
                "execution_artifact_sha256": runner_sha,
            },
            "trusted_time_inputs": {
                "foundation_knowledge_evaluation_at_utc":
                    fam_payload.get("foundation_knowledge_evaluation_at_utc"),
                "foundation_admission_evaluation_at_utc":
                    fam_payload.get("foundation_admission_evaluation_at_utc"),
                "knowledge_evaluation_at_utc": None,
            },
            "decision_record_refs": [decision["decision_record_id"]],
        })
        add_content(index, final_gate)

        # Final graph includes the terminal T-ACCEPT GateResult itself.
        final_closure = resolve_closure(
            api, index, [*seeds, final_gate], historical_gate_ids
        )
        final_nodes = build_bounded_concrete_graph(
            api, final_closure, historical_gate_ids
        )
        final_graph = api["analyze_graph"](final_nodes)
        require(len(final_graph.topological_order) == len(final_nodes),
                "FINAL_CONCRETE_GRAPH_NOT_ACYCLIC")
        print("TACCEPT_FINAL_CONCRETE_GRAPH_ACYCLIC=PASS")

        # Retain exact semantic outputs before the atomic DB transaction.
        write_json(output / "task04-acceptance-manifest.json", document(acceptance))
        write_json(output / "classification-runtime-profile-admission-manifest.json", document(rpm))
        write_json(output / "taccept-gate-result-manifest.json", document(final_gate))

        # No network is permitted in the final acceptance/admission mutation.
        with no_network():
            persist_acceptance_atomically(
                api, store, classifier, crp, gates, comparisons, acceptance, rpm, final_gate
            )

        # Post-commit exact verification. No profile activation is allowed.
        stored_acceptance = store.load_artifact(acceptance.artifact_id, acceptance.content_sha256)
        stored_rpm = store.load_artifact(rpm.artifact_id, rpm.content_sha256)
        stored_gate = store.load_artifact(final_gate.artifact_id, final_gate.content_sha256)
        require(stored_acceptance == acceptance and stored_rpm == rpm and stored_gate == final_gate,
                "TACCEPT_POSTCOMMIT_ARTIFACT_MISMATCH")
        require(store.get_active_pointer("classification") is None,
                "TACCEPT_CHANGED_CLASSIFICATION_POINTER")
        foundation_pointer_after = store.get_active_pointer("foundation")
        require(foundation_pointer_after is not None
                and foundation_pointer_after.runtime_profile_id == FOUNDATION_PROFILE_ID
                and foundation_pointer_after.runtime_profile_digest == FOUNDATION_PROFILE_SHA,
                "TACCEPT_CHANGED_FOUNDATION_POINTER")

        control_after = sha(CONTROL_DB)
        lock = {
            "lock_schema_version": 1,
            "gate_id": "T-ACCEPT",
            "status": "PASS",
            "candidate_commit": COMMIT,
            "candidate_tree": TREE,
            "classification_runtime_profile": ref(crp),
            "task04_acceptance_manifest": ref(acceptance),
            "classification_runtime_profile_admission_manifest": ref(rpm),
            "gate_result_manifest": ref(final_gate),
            "owner_decision_record_id": decision["decision_record_id"],
            "owner_decision_record_sha256": decision["record_sha256"],
            "foundation_runtime_profile_admission_manifest": ref(foundation_rpm),
            "foundation_admission_manifest": ref(foundation_admission),
            "update_class": "INITIAL_CLASSIFICATION",
            "classification_active_pointer_after": None,
            "production_activation": False,
            "control_db_sha256_before": control_before,
            "control_db_sha256_after": control_after,
            "retained_files": {
                path.name: {"sha256": sha(path)}
                for path in (
                    compatibility["path"], graph_path, acceptance_report_path, decision_path,
                    output / "task04-acceptance-manifest.json",
                    output / "classification-runtime-profile-admission-manifest.json",
                    output / "taccept-gate-result-manifest.json",
                )
            },
        }
        lock_path = output / "taccept-lock.json"
        write_json(lock_path, lock)

        print("")
        print("TACCEPT_GATE_EXECUTION_STATUS=PASS")
        print("TACCEPT_FINAL_GATE_STATUS=PASS")
        print(f"TACCEPT_TASK04_ACCEPTANCE_MANIFEST={acceptance.artifact_id}")
        print(f"TACCEPT_CLASSIFICATION_RPM={rpm.artifact_id}")
        print(f"TACCEPT_GATE_RESULT_MANIFEST={final_gate.artifact_id}")
        print(f"TACCEPT_OWNER_DECISION_RECORD_ID={decision['decision_record_id']}")
        print("TACCEPT_UPDATE_CLASS=INITIAL_CLASSIFICATION")
        print("TACCEPT_PROFILE_COMPATIBILITY=PASS")
        print("TACCEPT_ARTIFACT_GRAPH_ACYCLIC=PASS")
        print("TACCEPT_CLASSIFICATION_ACTIVE_POINTER=ABSENT")
        print("TACCEPT_PRODUCTION_ACTIVATION=NO")
        print("DEVICE_FINGERPRINT_TASK04_STATUS=ACCEPTED_PRODUCTION_ELIGIBLE")
        print(f"TACCEPT_LOCK_PATH={lock_path}")
        print(f"TACCEPT_LOCK_SHA256={sha(lock_path)}")
        return 0

    except Exception as exc:
        print("")
        print("TACCEPT_GATE_EXECUTION_STATUS=BLOCKED")
        reason = str(exc) if isinstance(exc, Blocked) else getattr(exc, "reason_code", type(exc).__name__)
        print(f"TACCEPT_BLOCKER={reason}")
        print("TACCEPT_PRODUCTION_ACTIVATION=NO")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
