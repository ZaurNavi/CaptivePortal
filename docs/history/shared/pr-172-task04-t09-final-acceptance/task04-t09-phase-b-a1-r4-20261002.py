"""External R14 T-09 R4: consume frozen Phase-A truth, isolate compatibility from product workers.

Phase A is historical/frozen and cannot be recreated by R4.
B first executes the exact 9/9 candidate compatibility recheck in a dedicated
fresh PRECHECK process, then sequentially launches a fresh interpreter for each
controlled device using the real pre-acceptance product path on private disposable
database snapshots.  This preserves the frozen 96 MiB SnapshotExecutionPolicy
without contaminating the product snapshot worker with compatibility-preflight memory.
C requires a separately supplied, post-review Owner DecisionRecord.

Importing this module does not run a phase, import the candidate, or access a DB.
No pytest, fixture injection, profile activation, source-DB SQL, or cloud calls.
The caller must retain the printed lock SHA256 outside the run directory and
provide it to the next phase. A lock never contains a recursive hash of itself.
Its independently supplied digest binds its complete retained-file inventory.
"""

from __future__ import annotations

import argparse
import ctypes
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
from types import SimpleNamespace
import uuid

COMMIT = "8a39459be3ce7ed40e325736034245f0025cf249"
TREE = "e2521f27c9f91978e381bce202ab3e3c83aa6dad"
PHASE_A_LOCK_SHA = "1142010057ddaa8564fe076160f35595e84ae51c5dae6d798d5e8bbb839c6ac1"
PHASE_A_RUNNER_SHA = "8d5c0857d184dd6014287b7506b03f20f1bd181b30590a9b83cc8fb884b15d44"
PHASE_A_RUNNER_PATH = Path(r"C:\CaptivPortal-Lab\tools\task04-t09-phase-a-r2-lock-upgrade-a1-20261002.py")
PROFILE_ID = "ClassificationRuntimeProfile:v1:sha256:1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c"
POLICY_ID = "ProductValidationPolicy:v1:sha256:806779ca1844e55083a2c1c464cf8d94a9bdd0b2f97436d203b63fd03e81bea5"
T06A_RESULT_ID = "GateResultManifest:v1:sha256:cd102f0fca7adb9e09ce1ff69d2109b34691e7362fd071a0617fc300547db406"
T06A_PROOF_ID = "GateProofArtifact:v1:sha256:6e404961cce296382f03b37e54111b6d535a1e1c44432a8e8f6269290bf64267"
LAB_ROOT = Path(r"C:\CaptivPortal-Lab")
T07_PATH = LAB_ROOT / "tools/task04-t07-gate-a1-20261002.py"
T07_SHA = "bbe90933dd4526f4b0cb3c1db65ada38161de0147c476a5be2105bcb7cecf9ac"
T06A_RUN = LAB_ROOT / "official-runs/task04/t06a/official-run-20261001T124442Z-T06A-A1-01/fe25e9fc-7b03-485b-ae68-0f806fd96af6"
GATE_ID = "T-09"
CONTRACT = "R14-T-09-v1"
PROCEDURE = "T-09-controlled-product-validation-pre-result-ground-truth-v1"
DEVICES = (
    {"controlled_device_lab_label": "OWNER_ANDROID", "site_id": "6a64f17630da7c70d232187a",
     "observed_mac": "be:00:7d:9b:04:2e", "platform_family_ground_truth": "android",
     "device_class_ground_truth": "smartphone", "manufacturer_id_ground_truth": None,
     "model_family_id_ground_truth": None, "ground_truth_method": "OWNER_CONTROLLED_DEVICE",
     "window_start_utc": "2026-09-30T09:04:08.388Z", "window_end_utc": "2026-09-30T09:08:09.000Z"},
    {"controlled_device_lab_label": "OWNER_WINDOWS_LAPTOP", "site_id": "6a64f17630da7c70d232187a",
     "observed_mac": "cc:f9:e4:d6:ab:1e", "platform_family_ground_truth": "windows",
     "device_class_ground_truth": "laptop", "manufacturer_id_ground_truth": None,
     "model_family_id_ground_truth": None, "ground_truth_method": "OWNER_CONTROLLED_DEVICE",
     "window_start_utc": "2026-09-30T09:23:00.176Z", "window_end_utc": "2026-09-30T09:30:15.000Z"},
)
DIMENSIONS = (
    ("platform_family", "platform_family_ground_truth", "platform_result"),
    ("device_class", "device_class_ground_truth", "device_class_result"),
    ("manufacturer_family", "manufacturer_id_ground_truth", "manufacturer_result"),
    ("model_family", "model_family_id_ground_truth", "model_result"),
)
GT_FIELDS = frozenset(DEVICES[0]) | {"validation_run_id", "recorded_at_utc"}
REGISTRATION_FIELDS = frozenset({"registration_schema_version", "registration_id", "artifact_id",
    "registered_at_utc", "registered_by_role", "repository_commit_sha", "repository_tree_sha",
    "decision_record_refs", "notes_reference_metadata"})
REGISTRATION_ROLE = "EXTERNAL_LAB_TOOL"
SUPPORT = {"none": 0, "low": 1, "medium": 2, "high": 3}
STATUSES = {"resolved", "recognized_out_of_scope", "unknown", "insufficient_evidence", "conflicting_evidence"}


class Blocked(RuntimeError):
    pass


def require(condition, code):
    if not condition:
        raise Blocked(code)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def uuid4(value):
    require(isinstance(value, str) and str(uuid.UUID(value)) == value and uuid.UUID(value).version == 4,
            "INVALID_UUID_V4")


def ref(item):
    return {"artifact_id": item.artifact_id, "content_sha256": item.content_sha256}


def document(item):
    return {"artifact_type": item.artifact_type, "artifact_schema_version": 1,
            **ref(item), "semantic_payload": item.semantic_payload}


def write(api, path, value):
    # Exclusive creation: never replace evidence from a prior phase/execution.
    with Path(path).open("xb") as stream:
        stream.write(api.artifact.canonical_artifact_json(value) + b"\n")


def read(api, path):
    raw = Path(path).read_bytes()
    value = api.artifact.decode_artifact_json(raw.decode("utf-8"))
    require(raw == api.artifact.canonical_artifact_json(value) + b"\n", "NONCANONICAL_RETAINED_FILE")
    return value


def load_content(api, path, builder=None):
    doc = read(api, path)
    require(set(doc) == {"artifact_type", "artifact_schema_version", "artifact_id", "content_sha256", "semantic_payload"},
            "ARTIFACT_DOCUMENT_SHAPE")
    content = (builder(doc["semantic_payload"]) if builder else
               api.artifact.make_artifact_content(doc["artifact_type"], doc["semantic_payload"]))
    require(document(content) == doc, "ARTIFACT_IDENTITY_MISMATCH")
    return content


def helpers():
    require(sha(T07_PATH) == T07_SHA, "PINNED_T07_HELPER_CHANGED")
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("t09_pinned_t07", T07_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    t01, t06a = module.helpers()
    require(module.COMMIT == COMMIT and module.TREE == TREE and module.PROFILE_ID == PROFILE_ID
            and module.T06A_RESULT_ID == T06A_RESULT_ID and module.T06A_PROOF_ID == T06A_PROOF_ID,
            "HELPER_CANDIDATE_MISMATCH")
    return module, t01, t06a


def minimal_api(repo, helper):
    # Phase A deliberately excludes assembly, fusion, persistence and result APIs.
    sys.path.insert(0, str(repo))
    names = {"artifact": "artifact_content", "foundation": "foundation_admission_artifacts",
             "profiles": "runtime_profile_artifacts", "schema": "foundation_schema_artifacts",
             "gate_result": "foundation_gate_artifacts", "gate_proof": "gate_proof_artifacts",
             "validation": "validation", "product_policy": "product_validation_policy"}
    return SimpleNamespace(**{key: helper.candidate(repo, "app.device_fingerprint." + name)
                              for key, name in names.items()})


def db_identity(path):
    path = Path(path).resolve(strict=True)
    require(path.is_file(), "INPUT_DB_MISSING")
    return {str(p): {"bytes": p.stat().st_size, "sha256": sha(p)}
            for p in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm")) if p.exists()}


def disposable_snapshot(source, target):
    # Copy bytes first. Never even open the source DB via SQLite: read-only SQLite
    # can update a source -shm. Copying a stable main/WAL/SHM set avoids that.
    source = Path(source).resolve(strict=True)
    before = db_identity(source)
    staging = target.parent / (target.stem + "-raw-input")
    staging.mkdir()
    for raw in before:
        shutil.copyfile(raw, staging / Path(raw).name)
    require(db_identity(source) == before, "INPUT_DB_CHANGED_DURING_SNAPSHOT")
    for raw, identity in before.items():
        p = staging / Path(raw).name
        require(p.stat().st_size == identity["bytes"] and sha(p) == identity["sha256"], "SNAPSHOT_COPY_MISMATCH")
    original = sqlite3.connect((staging / source.name).as_uri() + "?mode=ro", uri=True)
    dest = sqlite3.connect(target)
    try:
        original.execute("PRAGMA query_only=ON")
        original.backup(dest)
        # Only the disposable destination is changed. A rollback-journal snapshot
        # allows later read-only opens without writing WAL/SHM beside the input.
        require(dest.execute("PRAGMA journal_mode=DELETE").fetchone()[0].lower() == "delete", "SNAPSHOT_JOURNAL_MODE")
    finally:
        dest.close()
        original.close()
    require(db_identity(source) == before, "INPUT_DB_MUTATED")
    return before


@contextmanager
def no_network():
    saved = []
    attempts = []
    def deny(*_args, **_kwargs):
        attempts.append("DENIED")
        raise Blocked("NETWORK_ATTEMPT_FORBIDDEN")
    for obj, name in ((socket, "create_connection"), (socket, "getaddrinfo"),
                      (socket.socket, "connect"), (socket.socket, "connect_ex"),
                      (socket.socket, "sendto"), (socket.socket, "sendall"), (socket.socket, "send")):
        saved.append((obj, name, getattr(obj, name)))
        setattr(obj, name, deny)
    try:
        yield attempts
    finally:
        for obj, name, value in reversed(saved):
            setattr(obj, name, value)
        require(not attempts, "NETWORK_ATTEMPT_FORBIDDEN")


def new_directory(path, repo, protected):
    path = Path(path).resolve()
    require(path.is_relative_to(LAB_ROOT.resolve()) and path != LAB_ROOT.resolve()
            and not path.is_relative_to(repo) and not repo.is_relative_to(path), "OUTPUT_OUTSIDE_LAB_BOUNDARY")
    require(not path.exists(), "OUTPUT_ALREADY_EXISTS")
    for item in protected:
        item = Path(item).resolve()
        require(not item.is_relative_to(path) and not path.is_relative_to(item), "OUTPUT_INPUT_OVERLAP")
    path.mkdir(parents=True)
    return path


def normalized_device(api, device):
    return {**device, "observed_mac": api.validation.validate_mac(device["observed_mac"])}


def ground_truth(api, payload):
    require(isinstance(payload, dict) and set(payload) == GT_FIELDS, "GROUND_TRUTH_CLOSED_SCHEMA")
    uuid4(payload["validation_run_id"])
    api.validation.validate_site_id(payload["site_id"])
    require(api.validation.validate_mac(payload["observed_mac"]) == payload["observed_mac"], "GROUND_TRUTH_MAC")
    for key in ("window_start_utc", "window_end_utc", "recorded_at_utc"):
        api.validation.parse_utc(payload[key])
    require(payload["window_start_utc"] < payload["window_end_utc"], "GROUND_TRUTH_WINDOW")
    require(payload["ground_truth_method"] in {"OWNER_CONTROLLED_DEVICE", "PHYSICAL_DEVICE_INSPECTION",
            "OS_DEVICE_SETTINGS", "INDEPENDENT_ASSET_RECORD"}, "GROUND_TRUTH_METHOD")
    for key in ("controlled_device_lab_label", "platform_family_ground_truth"):
        require(isinstance(payload[key], str) and bool(payload[key]), "GROUND_TRUTH_TEXT")
    for key in ("device_class_ground_truth", "manufacturer_id_ground_truth", "model_family_id_ground_truth"):
        require(payload[key] is None or isinstance(payload[key], str) and bool(payload[key]), "GROUND_TRUTH_NULLABLE_TEXT")
    return api.artifact.make_artifact_content("ControlledValidationGroundTruthRecord", payload)


def artifact_registration(api, payload, gt, registration_deadline):
    """Closed §10.2 audit record, NOT semantic ArtifactContent or Owner approval.

    notes_reference_metadata carries §10.2's notes/reference metadata. Phase A
    registers mechanically via the external tool and has no decision to invent;
    the ordered decision_record_refs SET is therefore exactly empty here.
    """
    require(isinstance(payload, dict) and set(payload) == REGISTRATION_FIELDS,
            "ARTIFACT_REGISTRATION_CLOSED_SCHEMA")
    require(type(payload["registration_schema_version"]) is int
            and payload["registration_schema_version"] == 1, "ARTIFACT_REGISTRATION_VERSION")
    uuid4(payload["registration_id"])
    require(gt.artifact_type == "ControlledValidationGroundTruthRecord"
            and payload["artifact_id"] == gt.artifact_id, "ARTIFACT_REGISTRATION_GROUND_TRUTH_BINDING")
    registered = api.validation.parse_utc(payload["registered_at_utc"])
    require(api.validation.parse_utc(gt.semantic_payload["recorded_at_utc"]) <= registered
            <= api.validation.parse_utc(registration_deadline), "ARTIFACT_REGISTRATION_NOT_PRE_RESULT")
    require(payload["registered_by_role"] == REGISTRATION_ROLE
            and payload["repository_commit_sha"] == COMMIT and payload["repository_tree_sha"] == TREE,
            "ARTIFACT_REGISTRATION_CANDIDATE_ROLE")
    require(type(payload["decision_record_refs"]) is list and payload["decision_record_refs"] == [],
            "ARTIFACT_REGISTRATION_UNSUPPLIED_DECISION")
    require(payload["notes_reference_metadata"] == {
        "registration_context": "T09_PHASE_A_PRE_RESULT",
        "validation_run_id": gt.semantic_payload["validation_run_id"],
    }, "ARTIFACT_REGISTRATION_METADATA")
    return payload


def comparison(api, gt, request, result, policy):
    require(request.artifact_type == "ClassificationRequestManifest" and result.artifact_type == "ClassificationResult"
            and result.semantic_payload["classification_request_digest"] == request.content_sha256, "COMPARISON_REQUEST_RESULT_BINDING")
    outcomes = []
    for dimension, truth_key, result_key in DIMENSIONS:
        actual = result.semantic_payload[result_key]
        expected = gt.semantic_payload[truth_key]
        known = expected is not None
        require(actual["dimension_name"] == dimension and actual["status"] in STATUSES
                and actual["support_level"] in SUPPORT, "COMPARISON_DIMENSION_CONTRACT")
        failed = known and ((actual["status"] == "resolved" and actual["canonical_value_id"] != expected)
                 or (dimension in {"platform_family", "device_class"} and actual["status"] == "recognized_out_of_scope"))
        outcomes.append({"dimension_name": dimension, "ground_truth_known": known,
            "expected_value_or_ref": expected, "actual_status": actual["status"],
            "actual_value_or_ref": actual["canonical_value_id"], "support_level": actual["support_level"],
            "comparison_outcome": "NOT_APPLICABLE" if not known else "FAIL" if failed else "PASS"})
    p = policy.semantic_payload
    platform = next(row for row in outcomes if row["dimension_name"] == "platform_family")
    family = gt.semantic_payload["platform_family_ground_truth"]
    utility = (platform["actual_status"] == "resolved" and platform["actual_value_or_ref"] == p[family + "_required_platform"]
               and SUPPORT[platform["support_level"]] >= SUPPORT[p[family + "_min_support"]])
    passed = utility and not any(row["comparison_outcome"] == "FAIL" for row in outcomes)
    return api.artifact.make_artifact_content("ProductValidationComparisonRecord", {
        "validation_run_id": gt.semantic_payload["validation_run_id"], "ground_truth_record": ref(gt),
        "classification_request": ref(request), "classification_result": ref(result),
        "per_dimension_outcomes": api.artifact.canonical_set(outcomes, lambda row: row["dimension_name"]),
        "overall_validation_outcome": "PASS" if passed else "FAIL"})


def make_lock(api, directory, name, fields, files):
    # Cover every retained file, including the disposable persistence DB and raw
    # SQLite staging files; explicit files must be part of this complete set.
    all_files = sorted(p for p in directory.rglob("*") if p.is_file())
    require(all(p in all_files for p in files), "LOCK_FILE_INVENTORY_INCOMPLETE")
    inventory = {p.relative_to(directory).as_posix(): {"sha256": sha(p), "bytes": p.stat().st_size}
                 for p in all_files}
    value = {**fields, "retained_files": inventory}
    write(api, directory / name, value)
    return sha(directory / name)


def verify_lock(api, path, expected_sha, phase):
    if phase == "A":
        require(expected_sha == PHASE_A_LOCK_SHA and sha(PHASE_A_RUNNER_PATH) == PHASE_A_RUNNER_SHA,
                "FROZEN_R1_PHASE_A_PROVENANCE_MISMATCH")
    producer_sha = PHASE_A_RUNNER_SHA if phase == "A" else sha(Path(__file__))
    require(re.fullmatch(r"[0-9a-f]{64}", expected_sha or "") is not None and sha(path) == expected_sha, "LOCK_IDENTITY_CHANGED")
    lock = read(api, path)
    require(lock["phase"] == phase and lock["candidate_commit"] == COMMIT and lock["candidate_tree"] == TREE
            and lock["runner_sha256"] == producer_sha and lock["helper_sha256"] == T07_SHA,
            "LOCK_CANDIDATE_RUNNER_MISMATCH")
    uuid4(lock["validation_run_id"])
    require(lock["retained_files"], "EMPTY_LOCK_INVENTORY")
    for name, identity in lock["retained_files"].items():
        require(not Path(name).is_absolute() and ".." not in Path(name).parts and name != path.name, "INVALID_LOCK_MEMBER")
        member = path.parent / name
        require(member.resolve(strict=True).is_relative_to(path.parent.resolve()) and not member.is_symlink()
                and member.stat().st_size == identity["bytes"] and sha(member) == identity["sha256"], "LOCK_MEMBER_CHANGED")
    actual_files = {p.relative_to(path.parent).as_posix() for p in path.parent.rglob("*") if p.is_file() and p != path}
    require(actual_files == set(lock["retained_files"]), "LOCK_UNREGISTERED_FILE")
    if phase == "B":
        require(lock["phase_a_lock_sha256"] == PHASE_A_LOCK_SHA
                and lock["phase_a_runner_sha256"] == PHASE_A_RUNNER_SHA
                and lock["phase_b_runner_sha256"] == producer_sha,
                "PHASE_B_PRODUCER_PROVENANCE_MISMATCH")
        preflight_ref = lock.get("compatibility_preflight")
        require(isinstance(preflight_ref, dict)
                and set(preflight_ref) == {"file", "file_sha256", "preflight_execution_id",
                                           "process_id", "runner_sha256"},
                "PHASE_B_COMPATIBILITY_PREFLIGHT_REF")
        uuid4(preflight_ref["preflight_execution_id"])
        require(type(preflight_ref["process_id"]) is int and preflight_ref["process_id"] > 0
                and preflight_ref["runner_sha256"] == producer_sha,
                "PHASE_B_COMPATIBILITY_PREFLIGHT_PROVENANCE")
        preflight_file = preflight_ref["file"]
        require(preflight_file in lock["retained_files"]
                and lock["retained_files"][preflight_file]["sha256"] == preflight_ref["file_sha256"],
                "PHASE_B_COMPATIBILITY_PREFLIGHT_NOT_RETAINED")
        worker_refs = lock["worker_executions"]
        require(isinstance(worker_refs, list) and len(worker_refs) == len(DEVICES), "PHASE_B_WORKER_COUNT")
        for index, (worker_ref, device) in enumerate(zip(worker_refs, DEVICES), 1):
            worker_file = f"worker-{index}/worker-completion.json"
            require(worker_ref["device_label"] == device["controlled_device_lab_label"]
                    and worker_ref["file"] == worker_file and worker_ref["runner_sha256"] == producer_sha
                    and worker_ref["file_sha256"] == lock["retained_files"][worker_file]["sha256"],
                    "PHASE_B_WORKER_PROVENANCE_MISMATCH")
    return lock

def context(args, output, full=False):
    h, t01, t06a = helpers()
    repo = args.repo.resolve(strict=True)
    t01.verify_repository(repo)
    fingerprint = t01.repository_filesystem_fingerprint(repo)
    api = minimal_api(repo, h)
    foundation_copy = output / "foundation-snapshot.sqlite3"
    source_identity = disposable_snapshot(args.foundation_db, foundation_copy)
    profile, proof, result = h.verify_t06a(T06A_RUN, api)
    require(profile.artifact_id == PROFILE_ID and proof.artifact_id == T06A_PROOF_ID
            and result.artifact_id == T06A_RESULT_ID, "T06A_IDENTITY_MISMATCH")
    with closing(t01.open_foundation_read_only(foundation_copy)) as conn:
        lineage = t01.verify_foundation(conn, api)
        foundation = t01._resolve_artifact(conn, api, profile.semantic_payload["foundation_runtime_profile"])
        require(foundation == lineage.profile, "EXACT_P_FOUNDATION_LINEAGE_MISMATCH")
        policy = t01._resolve_artifact(conn, api, lineage.manifest.semantic_payload["product_validation_policy"])
        require(policy.artifact_id == POLICY_ID and api.product_policy.make_product_validation_policy(policy.semantic_payload) == policy,
                "PRODUCT_VALIDATION_POLICY_MISMATCH")
    valid_from = foundation.semantic_payload["classification_foundation_valid_from_utc"]
    api.validation.parse_utc(valid_from)
    for device in DEVICES:
        require(api.validation.parse_utc(device["window_start_utc"]) >= api.validation.parse_utc(valid_from), "WINDOW_BEFORE_FOUNDATION_VALID_FROM")
    if full:
        extended = t06a.load_api(repo)
        for key, name in {"assembly": "request_assembly", "control": "control_plane_store",
                          "retention": "classification_retention_policy"}.items():
            setattr(extended, key, h.candidate(repo, "app.device_fingerprint." + name))
        extended.product_policy = api.product_policy
        api = extended
    return SimpleNamespace(h=h, t01=t01, t06a=t06a, api=api, repo=repo, fingerprint=fingerprint,
        foundation_copy=foundation_copy, source_identity=source_identity, profile=profile,
        foundation=foundation, lineage=lineage, policy=policy, valid_from=valid_from,
        t06a_proof=proof, t06a_result=result, runner_sha256=sha(Path(__file__)))


def finish_integrity(ctx, args):
    require(db_identity(args.foundation_db) == ctx.source_identity, "FOUNDATION_SOURCE_MUTATED")
    ctx.t01.verify_repository(ctx.repo)
    ctx.t01._require_repository_unchanged(ctx.repo, ctx.fingerprint)
    require(sha(T07_PATH) == T07_SHA, "HELPER_CHANGED_DURING_PHASE")
    require(sha(Path(__file__)) == ctx.runner_sha256, "RUNNER_CHANGED_DURING_PHASE")
    require(sha(PHASE_A_RUNNER_PATH) == PHASE_A_RUNNER_SHA, "FROZEN_R1_RUNNER_CHANGED")
    ctx.h.helpers()  # Recheck pinned T01/T06A identities without executing gates.


def phase_a(args):
    raise Blocked("PHASE_A_FROZEN_R1_ONLY_NO_R2_RECREATION")


def checked_phase_a(ctx, args):
    api = ctx.api
    lock = verify_lock(api, args.phase_a_lock, args.phase_a_lock_sha256, "A")
    require(lock["profile"] == ref(ctx.profile) and lock["foundation"] == ref(ctx.foundation)
            and lock["product_validation_policy"] == ref(ctx.policy)
            and lock["classification_foundation_valid_from_utc"] == ctx.valid_from
            and lock["device_bindings"] == [normalized_device(api, d) for d in DEVICES], "PHASE_A_EXACT_BINDING_CHANGED")
    records = []
    lock_created = api.validation.parse_utc(lock["lock_created_at_utc"])
    require(api.validation.parse_utc(lock["executed_at_utc"]) <= lock_created,
            "PHASE_A_LOCK_TIME_INVALID")
    registrations = lock["ground_truth_registrations"]
    require(isinstance(registrations, list) and len(registrations) == len(DEVICES),
            "PHASE_A_REGISTRATION_INVENTORY")
    registration_ids = set()
    for index, device in enumerate(DEVICES, 1):
        gt = load_content(api, args.phase_a_lock.parent / f"ground-truth-{index}.json", lambda p: ground_truth(api, p))
        require(gt.semantic_payload == {**normalized_device(api, device), "validation_run_id": lock["validation_run_id"],
                "recorded_at_utc": lock["executed_at_utc"]} and ref(gt) == lock["ground_truth_refs"][index - 1], "GROUND_TRUTH_RELABELED")
        registration_path = args.phase_a_lock.parent / f"ground-truth-registration-{index}.json"
        registration = artifact_registration(api, read(api, registration_path), gt, lock["lock_created_at_utc"])
        binding = {"registration_id": registration["registration_id"], "artifact_id": gt.artifact_id,
                   "file": registration_path.name, "file_sha256": sha(registration_path)}
        require(registrations[index - 1] == binding
                and lock["retained_files"][registration_path.name]["sha256"] == binding["file_sha256"],
                "PHASE_A_REGISTRATION_IDENTITY_CHANGED")
        require(registration["registration_id"] not in registration_ids, "PHASE_A_DUPLICATE_REGISTRATION_ID")
        registration_ids.add(registration["registration_id"])
        records.append(gt)
    return lock, records


def device_class_count(comparisons, policy):
    return sum(any(row["dimension_name"] == "device_class" and row["actual_status"] == "resolved"
                   and row["actual_value_or_ref"] == row["expected_value_or_ref"] and row["ground_truth_known"]
                   and SUPPORT[row["support_level"]] >= SUPPORT[policy.semantic_payload["device_class_min_support"]]
                   for row in item.semantic_payload["per_dimension_outcomes"]) for item in comparisons)


def memory_guard(limit):
    """Enforce the supplied Windows process-memory limit, never bypass it."""
    if sys.platform != "win32" or type(limit) is not int or limit <= 0:
        raise Blocked("PROCESS_MEMORY_MEASUREMENT_UNAVAILABLE")
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                    ("PrivateUsage", ctypes.c_size_t)]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = (wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD)
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    require(bool(psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb)),
            "PROCESS_MEMORY_MEASUREMENT_UNAVAILABLE")
    return max(counters.WorkingSetSize, counters.PrivateUsage) <= limit


def copy_locked_bytes(source, destination, identity):
    require(source.is_file() and source.stat().st_size == identity["bytes"]
            and sha(source) == identity["sha256"], "WORKER_OUTPUT_IDENTITY_CHANGED")
    raw = source.read_bytes()
    require(len(raw) == identity["bytes"] and hashlib.sha256(raw).hexdigest() == identity["sha256"],
            "WORKER_OUTPUT_CHANGED_DURING_READ")
    with destination.open("xb") as stream:
        stream.write(raw)
    require(destination.stat().st_size == identity["bytes"] and sha(destination) == identity["sha256"],
            "WORKER_OUTPUT_COPY_MISMATCH")


def compatibility_preflight(args):
    """Execute exact T-06A 9/9 compatibility in a dedicated fresh process."""
    require(args.phase_a_lock is not None and args.phase_a_lock_sha256 == PHASE_A_LOCK_SHA,
            "PREFLIGHT_PHASE_A_REQUIRED")
    require(args.runner_sha256 == sha(Path(__file__)), "PREFLIGHT_RUNNER_IDENTITY_MISMATCH")
    require(re.fullmatch(r"[0-9a-f]{64}", args.parent_foundation_sha256 or "") is not None
            and sha(args.foundation_db) == args.parent_foundation_sha256,
            "PREFLIGHT_PARENT_FOUNDATION_IDENTITY")
    started = now()
    output = new_directory(args.output, args.repo.resolve(),
        [args.foundation_db, args.phase_a_lock.parent, T06A_RUN])
    with no_network() as attempts:
        ctx = context(args, output, full=True)
        api, h, t01 = ctx.api, ctx.h, ctx.t01
        lock, _truths = checked_phase_a(ctx, args)
        require(api.validation.parse_utc(started) > api.validation.parse_utc(lock["lock_created_at_utc"]),
                "PREFLIGHT_MUST_FOLLOW_PHASE_A_LOCK")

        classifier = h.canonical_content(h.T06_MANIFEST_PATH, api,
            lambda p: api.artifact.make_artifact_content("ClassifierArtifactManifest", p),
            ctx.profile.semantic_payload["classifier_artifact_manifest"]["artifact_id"])
        control = api.control.DeviceFingerprintControlPlaneStore(ctx.foundation_copy)

        ctx.t06a._A1_OVERLAY.clear()
        ctx.t06a._A1_OVERLAY_SOURCES.clear()
        a1_overlay, _a1_overlay_sources = ctx.t06a.load_a1_overlay(api)
        ctx.t06a._A1_OVERLAY.update(a1_overlay)
        ctx.t06a._A1_OVERLAY_SOURCES.update(_a1_overlay_sources)

        overlay = h.ImmutableOverlay(control, classifier, a1_overlay)
        contents = {key: overlay.load_artifact(value["artifact_id"], value["content_sha256"])
                    for key, value in ctx.profile.semantic_payload.items() if isinstance(value, dict)}
        with closing(t01.open_foundation_read_only(ctx.foundation_copy)) as conn:
            compatibility = ctx.t06a.compatibility(conn, api, contents, ctx.lineage)
            require(len(compatibility) == 9 and all(row["status"] == "PASS" for row in compatibility),
                    "PROFILE_COMPATIBILITY_FAILED")
        require(not attempts, "NETWORK_ATTEMPT_FORBIDDEN")
        completed = now()
        report = {
            "compatibility_preflight_schema_version": 1,
            "preflight_execution_id": str(uuid.uuid4()),
            "process_id": os.getpid(),
            "started_at_utc": started,
            "completed_at_utc": completed,
            "runner_sha256": ctx.runner_sha256,
            "candidate_commit": COMMIT,
            "candidate_tree": TREE,
            "phase_a_lock_sha256": PHASE_A_LOCK_SHA,
            "parent_foundation_sha256": args.parent_foundation_sha256,
            "profile": ref(ctx.profile),
            "foundation": ref(ctx.foundation),
            "t06a_result": ref(ctx.t06a_result),
            "t06a_proof": ref(ctx.t06a_proof),
            "a1_immutable_overlay_artifact_count": len(a1_overlay),
            "a1_immutable_overlay_artifact_ids": sorted(a1_overlay),
            "checks": compatibility,
            "network_attempt_count": 0,
            "status": "PASS",
        }
        report_path = output / "compatibility-preflight.json"
        write(api, report_path, report)
        require(read(api, report_path) == report, "PREFLIGHT_REPORT_ROUNDTRIP")
        checked_phase_a(ctx, args)
        require(sha(args.foundation_db) == args.parent_foundation_sha256,
                "PREFLIGHT_PARENT_FOUNDATION_CHANGED")
        finish_integrity(ctx, args)
        digest = sha(report_path)
    print("COMPATIBILITY_PREFLIGHT_STATUS=PASS")
    print(f"COMPATIBILITY_PREFLIGHT_SHA256={digest}")
    return 0


def verify_compatibility_preflight(ctx, args, path, expected_sha, parent_foundation_sha256,
                                   expected_a1_overlay_ids=None):
    api = ctx.api
    path = Path(path).resolve(strict=True)
    require(re.fullmatch(r"[0-9a-f]{64}", expected_sha or "") is not None
            and sha(path) == expected_sha, "COMPATIBILITY_PREFLIGHT_IDENTITY_CHANGED")
    report = read(api, path)
    fields = {
        "compatibility_preflight_schema_version", "preflight_execution_id", "process_id",
        "started_at_utc", "completed_at_utc", "runner_sha256", "candidate_commit",
        "candidate_tree", "phase_a_lock_sha256", "parent_foundation_sha256", "profile",
        "foundation", "t06a_result", "t06a_proof", "a1_immutable_overlay_artifact_count",
        "a1_immutable_overlay_artifact_ids", "checks", "network_attempt_count", "status",
    }
    require(isinstance(report, dict) and set(report) == fields
            and report["compatibility_preflight_schema_version"] == 1,
            "COMPATIBILITY_PREFLIGHT_CLOSED_SCHEMA")
    uuid4(report["preflight_execution_id"])
    require(type(report["process_id"]) is int and report["process_id"] > 0
            and report["process_id"] != os.getpid(),
            "COMPATIBILITY_PREFLIGHT_PROCESS_ID")
    started = api.validation.parse_utc(report["started_at_utc"])
    completed = api.validation.parse_utc(report["completed_at_utc"])
    require(started <= completed <= api.validation.parse_utc(now()),
            "COMPATIBILITY_PREFLIGHT_TIME")
    require(report["runner_sha256"] == ctx.runner_sha256
            and report["candidate_commit"] == COMMIT and report["candidate_tree"] == TREE
            and report["phase_a_lock_sha256"] == PHASE_A_LOCK_SHA
            and report["parent_foundation_sha256"] == parent_foundation_sha256
            and report["profile"] == ref(ctx.profile)
            and report["foundation"] == ref(ctx.foundation)
            and report["t06a_result"] == ref(ctx.t06a_result)
            and report["t06a_proof"] == ref(ctx.t06a_proof)
            and report["network_attempt_count"] == 0 and report["status"] == "PASS",
            "COMPATIBILITY_PREFLIGHT_BINDING_MISMATCH")
    checks = report["checks"]
    require(isinstance(checks, list) and len(checks) == 9
            and all(isinstance(row, dict) and row.get("status") == "PASS" for row in checks),
            "COMPATIBILITY_PREFLIGHT_NOT_PASS")
    require(report["a1_immutable_overlay_artifact_count"] == 17
            and isinstance(report["a1_immutable_overlay_artifact_ids"], list)
            and len(report["a1_immutable_overlay_artifact_ids"]) == 17
            and len(set(report["a1_immutable_overlay_artifact_ids"])) == 17,
            "COMPATIBILITY_PREFLIGHT_A1_INVENTORY")
    if expected_a1_overlay_ids is not None:
        require(report["a1_immutable_overlay_artifact_ids"] == sorted(expected_a1_overlay_ids),
                "COMPATIBILITY_PREFLIGHT_A1_IDENTITY_MISMATCH")
    return report


def device_worker(args):
    """One fresh product process, one real request, private snapshots and persistence DB."""
    require(args.device_label in {d["controlled_device_lab_label"] for d in DEVICES}, "WORKER_DEVICE_NOT_CONTROLLED")
    require(args.runner_sha256 == sha(Path(__file__)), "WORKER_RUNNER_IDENTITY_MISMATCH")
    require(args.compatibility_report is not None and args.compatibility_report_sha256 is not None,
            "COMPATIBILITY_PREFLIGHT_REPORT_REQUIRED")
    parent_inputs = {"foundation_sha256": args.parent_foundation_sha256, "task01_sha256": args.parent_task01_sha256}
    require(sha(args.foundation_db) == parent_inputs["foundation_sha256"]
            and sha(args.task01_db) == parent_inputs["task01_sha256"], "WORKER_PARENT_INPUT_CHANGED")
    output = new_directory(args.output, args.repo.resolve(),
        [args.foundation_db, args.task01_db, args.phase_a_lock.parent, args.compatibility_report, T06A_RUN])
    with no_network():
        ctx = context(args, output, full=True)
        api, h, t01 = ctx.api, ctx.h, ctx.t01
        lock, truths = checked_phase_a(ctx, args)
        index = next(i for i, d in enumerate(DEVICES, 1) if d["controlled_device_lab_label"] == args.device_label)
        gt = truths[index - 1]
        started = now()
        require(api.validation.parse_utc(started) > api.validation.parse_utc(lock["lock_created_at_utc"]),
                "REGISTRATION_LOCK_MUST_PREEXIST_RESULT")
        source_copy = output / "task01-snapshot.sqlite3"
        source_identity = disposable_snapshot(args.task01_db, source_copy)
        classifier = h.canonical_content(h.T06_MANIFEST_PATH, api,
            lambda p: api.artifact.make_artifact_content("ClassifierArtifactManifest", p),
            ctx.profile.semantic_payload["classifier_artifact_manifest"]["artifact_id"])
        control = api.control.DeviceFingerprintControlPlaneStore(ctx.foundation_copy)

        # A1 bootstrap parity with the accepted T-06A execution.
        ctx.t06a._A1_OVERLAY.clear()
        ctx.t06a._A1_OVERLAY_SOURCES.clear()
        a1_overlay, a1_overlay_sources = ctx.t06a.load_a1_overlay(api)
        ctx.t06a._A1_OVERLAY.update(a1_overlay)
        ctx.t06a._A1_OVERLAY_SOURCES.update(a1_overlay_sources)

        overlay = h.ImmutableOverlay(control, classifier, a1_overlay)
        contents = {key: overlay.load_artifact(value["artifact_id"], value["content_sha256"])
                    for key, value in ctx.profile.semantic_payload.items() if isinstance(value, dict)}

        # Heavyweight §11.3/T-06A compatibility was executed in a separate fresh PRECHECK
        # process.  This worker verifies that canonical PASS report against the exact same
        # candidate/profile/foundation/A1 inventory before entering the normal product path.
        preflight = verify_compatibility_preflight(
            ctx, args, args.compatibility_report, args.compatibility_report_sha256,
            parent_inputs["foundation_sha256"], expected_a1_overlay_ids=a1_overlay.keys())
        compatibility = preflight["checks"]

        def compatible(profile, foundation, bundle, _knowledge, policy, adapters, manifest):
            return (profile == ctx.profile and foundation == ctx.foundation
                    and bundle == contents["knowledge_bundle"] and policy == contents["classification_policy"]
                    and adapters == contents["evidence_adapter_contract_set"] and manifest == classifier)
        reader = api.read.DeviceFingerprintReadService(str(source_copy), retention_days=30)
        service = api.assembly.DeviceFingerprintRequestAssembly(control_plane_store=overlay,
            read_service=reader, compatibility_hook=compatible, utc_clock=now, process_memory_guard=memory_guard)

        snapshot_before = db_identity(source_copy)
        foundation_before = db_identity(ctx.foundation_copy)
        checked_phase_a(ctx, args)
        p = gt.semantic_payload
        # Exactly one controlled device is classified during this process lifetime.
        assembled = service.assemble_pre_acceptance_candidate(
            ctx.profile, p["site_id"], p["observed_mac"], p["window_start_utc"], p["window_end_utc"])
        require(assembled.execution_context == "PRE_ACCEPTANCE_CANDIDATE"
                and assembled.classification_runtime_profile == ctx.profile
                and assembled.foundation_runtime_profile == ctx.foundation and not overlay.pin_calls,
                "PRODUCT_PATH_PROFILE_MISMATCH")
        snapshot = assembled.evidence_snapshot_content.semantic_payload
        require(all(snapshot[key] == p[key] for key in ("site_id", "observed_mac", "window_start_utc", "window_end_utc")),
                "PRODUCT_WINDOW_BINDING_MISMATCH")

        # Persistence-only prerequisites execute after successful RequestAssembly so they
        # cannot consume the frozen SnapshotExecutionPolicy process-memory envelope.
        with closing(t01.open_foundation_read_only(ctx.foundation_copy)) as conn:
            retention = h.resolve_retention(conn, api, t01, ctx.lineage)
        store = api.persistence.DeviceFingerprintClassificationStore(output / "classification.sqlite3",
            source_copy, control_plane_store=overlay, utc_clock=now)
        store.initialize()
        core = store.persist(assembled, retention_policy=retention,
            pre_acceptance_foundation_runtime_profile_admission_manifest=ctx.lineage.admission)
        require(store.load_core(core.classification_id) == core
                and core.classification_result_id == assembled.classification_result.artifact_id
                and core.classification_request_manifest_id == assembled.classification_request_manifest.artifact_id,
                "PRODUCT_PERSISTENCE_MISMATCH")
        cmp = comparison(api, gt, assembled.classification_request_manifest, assembled.classification_result, ctx.policy)
        retained = []
        for kind, item in (("request", assembled.classification_request_manifest),
                           ("result", assembled.classification_result), ("comparison", cmp)):
            path = output / f"{kind}-{index}.json"
            write(api, path, document(item))
            require(load_content(api, path) == item, "PRODUCT_ARTIFACT_ROUNDTRIP")
            retained.append(path)
        entry = {"controlled_device_lab_label": p["controlled_device_lab_label"], "ground_truth": ref(gt),
                 "request": ref(assembled.classification_request_manifest), "result": ref(assembled.classification_result),
                 "comparison": ref(cmp), "classification_id": core.classification_id}
        write(api, output / "compatibility-report.json", {"checks": compatibility})
        retained.append(output / "compatibility-report.json")
        checked_phase_a(ctx, args)
        require(sha(args.compatibility_report) == args.compatibility_report_sha256,
                "COMPATIBILITY_PREFLIGHT_CHANGED_DURING_WORKER")
        verify_compatibility_preflight(
            ctx, args, args.compatibility_report, args.compatibility_report_sha256,
            parent_inputs["foundation_sha256"], expected_a1_overlay_ids=a1_overlay.keys())
        require(db_identity(args.task01_db) == source_identity and db_identity(source_copy) == snapshot_before
                and db_identity(ctx.foundation_copy) == foundation_before, "WORKER_INPUT_OR_COPY_MUTATED")
        require(sha(args.foundation_db) == parent_inputs["foundation_sha256"]
                and sha(args.task01_db) == parent_inputs["task01_sha256"], "WORKER_PARENT_INPUT_CHANGED")
        finish_integrity(ctx, args)
        digest = make_lock(api, output, "worker-completion.json", {
            "phase": "WORKER", "validation_run_id": lock["validation_run_id"],
            "worker_execution_id": str(uuid.uuid4()), "process_id": os.getpid(),
            "candidate_commit": COMMIT, "candidate_tree": TREE, "runner_sha256": ctx.runner_sha256,
            "helper_sha256": T07_SHA, "phase_a_lock_sha256": PHASE_A_LOCK_SHA,
            "phase_a_runner_sha256": PHASE_A_RUNNER_SHA, "phase_b_runner_sha256": ctx.runner_sha256,
            "profile": ref(ctx.profile), "foundation": ref(ctx.foundation),
            "product_validation_policy": ref(ctx.policy), "parent_inputs": parent_inputs,
            "compatibility_preflight": {
                "file_sha256": args.compatibility_report_sha256,
                "preflight_execution_id": preflight["preflight_execution_id"],
                "process_id": preflight["process_id"],
                "runner_sha256": preflight["runner_sha256"],
            },
            "a1_immutable_overlay_artifact_count": len(a1_overlay),
            "a1_immutable_overlay_artifact_ids": sorted(a1_overlay),
            "a1_immutable_overlay_sources": a1_overlay_sources,
            "device_label": args.device_label, "request_count": 1, "entry": entry,
            "started_at_utc": started, "completed_at_utc": now(), "status": "WORKER_COMPLETE",
            "network_attempt_count": 0}, retained)
    print("WORKER_STATUS=COMPLETE")
    print(f"WORKER_COMPLETION_SHA256={digest}")
    return 0

def validate_worker(ctx, args, directory, expected_digest, index, gt, parent_inputs, preflight):
    """Validate output/persisted bindings without invoking classification in parent."""
    api = ctx.api
    worker = verify_lock(api, directory / "worker-completion.json", expected_digest, "WORKER")
    require(worker["status"] == "WORKER_COMPLETE" and worker["request_count"] == 1
            and worker["device_label"] == DEVICES[index - 1]["controlled_device_lab_label"]
            and worker["validation_run_id"] == gt.semantic_payload["validation_run_id"]
            and worker["phase_a_lock_sha256"] == PHASE_A_LOCK_SHA
            and worker["phase_a_runner_sha256"] == PHASE_A_RUNNER_SHA
            and worker["phase_b_runner_sha256"] == ctx.runner_sha256
            and worker["profile"] == ref(ctx.profile) and worker["foundation"] == ref(ctx.foundation)
            and worker["product_validation_policy"] == ref(ctx.policy)
            and worker["parent_inputs"] == parent_inputs
            and worker["compatibility_preflight"] == {
                "file_sha256": preflight["file_sha256"],
                "preflight_execution_id": preflight["report"]["preflight_execution_id"],
                "process_id": preflight["report"]["process_id"],
                "runner_sha256": preflight["report"]["runner_sha256"],
            }
            and worker["a1_immutable_overlay_artifact_count"] == 17
            and len(worker["a1_immutable_overlay_artifact_ids"]) == 17
            and worker["network_attempt_count"] == 0,
            "WORKER_EXECUTION_BINDING_MISMATCH")
    uuid4(worker["worker_execution_id"])
    require(type(worker["process_id"]) is int and worker["process_id"] > 0
            and worker["process_id"] != os.getpid()
            and worker["process_id"] != preflight["report"]["process_id"],
            "WORKER_NOT_SEPARATE_PROCESS")
    a, _ = checked_phase_a(ctx, args)
    require(api.validation.parse_utc(worker["started_at_utc"]) > api.validation.parse_utc(a["lock_created_at_utc"])
            and worker["started_at_utc"] <= worker["completed_at_utc"] <= now(), "WORKER_EXECUTION_TIME")
    req = load_content(api, directory / f"request-{index}.json")
    result = load_content(api, directory / f"result-{index}.json")
    cmp = load_content(api, directory / f"comparison-{index}.json")
    entry = worker["entry"]
    expected_entry = {"controlled_device_lab_label": worker["device_label"], "ground_truth": ref(gt),
        "request": ref(req), "result": ref(result), "comparison": ref(cmp),
        "classification_id": entry["classification_id"]}
    require(entry == expected_entry, "WORKER_ARTIFACT_BINDING_MISMATCH")
    uuid4(entry["classification_id"])
    for key, module in {"request": "classification_request", "fusion": "fusion", "origin": "origin_assessment",
                        "assembly": "request_assembly"}.items():
        if not hasattr(api, key):
            setattr(api, key, ctx.h.candidate(ctx.repo, "app.device_fingerprint." + module))
    database = directory / "classification.sqlite3"
    with closing(sqlite3.connect(database.resolve(strict=True).as_uri() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        rows = conn.execute("SELECT * FROM classifications").fetchall()
        require(len(rows) == 1, "WORKER_PERSISTENCE_REQUEST_COUNT")
        row = dict(rows[0])
        p = gt.semantic_payload
        require(row["classification_id"] == entry["classification_id"] and row["execution_context"] == "PRE_ACCEPTANCE_CANDIDATE"
                and row["site_id"] == p["site_id"] and row["observed_mac"] == p["observed_mac"]
                and row["classification_runtime_profile_id"] == ctx.profile.artifact_id
                and row["classification_runtime_profile_digest"] == ctx.profile.content_sha256
                and row["foundation_runtime_profile_id"] == ctx.foundation.artifact_id
                and row["foundation_runtime_profile_digest"] == ctx.foundation.content_sha256
                and row["runtime_profile_activation_record_id"] is None, "WORKER_PERSISTENCE_LINEAGE")
        for kind, item in (("classification_request_manifest", req), ("classification_result", result)):
            require(row[kind + "_id"] == item.artifact_id and row[kind + "_digest"] == item.content_sha256
                    and ctx.t01._resolve_artifact(conn, api, ref(item)) == item, "WORKER_PERSISTED_ARTIFACT_MISMATCH")
        named = {key: ctx.t01._resolve_artifact(conn, api, value)
                 for key, value in req.semantic_payload.items() if key != "knowledge_evaluation_at_utc"}
        require(api.request.make_classification_request_manifest(req.semantic_payload, **named) == req, "WORKER_REQUEST_SCHEMA")
        for key in ("classification_policy", "knowledge_bundle", "evidence_adapter_contract_set", "classifier_artifact_manifest"):
            require(ref(named[key]) == ctx.profile.semantic_payload[key], "WORKER_REQUEST_EXACT_PROFILE")
        snapshot = named["evidence_snapshot_content"].semantic_payload
        require(all(snapshot[key] == p[key] for key in ("site_id", "observed_mac", "window_start_utc", "window_end_utc")),
                "WORKER_SNAPSHOT_WINDOW")
        policy = named["classification_policy"].semantic_payload
        rp = result.semantic_payload
        result_fields = {"classification_request_digest", "classification_policy", "knowledge_bundle",
                         "classifier_artifact_manifest", "evidence_snapshot_content", "source_evaluability",
                         "platform_result", "device_class_result", "manufacturer_result", "model_result",
                         "global_classification_status", "origin_assessments"}
        require(result.artifact_type == "ClassificationResult" and set(rp) == result_fields
                and rp["classification_request_digest"] == req.content_sha256, "WORKER_RESULT_SCHEMA")
        for key in ("classification_policy", "knowledge_bundle", "classifier_artifact_manifest", "evidence_snapshot_content", "source_evaluability"):
            require(rp[key] == ref(named[key]), "WORKER_RESULT_REQUEST_BINDING")
        statuses = {}
        for dimension, _, key in DIMENSIONS:
            actual = rp[key]
            require(actual["dimension_name"] == dimension, "WORKER_DIMENSION_NAME")
            api.fusion._validate_dimension_result(actual, set(policy["recognized_out_of_scope_applicability"]))
            statuses[dimension] = actual["status"]
        expected_global = api.fusion._first_rule(policy["global_status_derivation"], {
            "ANY_DIMENSION_CONFLICTING": "conflicting_evidence" in statuses.values(),
            "ALL_FOUR_DIMENSIONS_RESOLVED": all(s == "resolved" for s in statuses.values()),
            "ANY_DIMENSION_RESOLVED": "resolved" in statuses.values(),
            "ANY_PLATFORM_OR_DEVICE_CLASS_OUT_OF_SCOPE": any(statuses[d] == "recognized_out_of_scope" for d in ("platform_family", "device_class")),
            "ANY_DIMENSION_INSUFFICIENT": "insufficient_evidence" in statuses.values(), "OTHERWISE": True})
        require(rp["global_classification_status"] == expected_global, "WORKER_GLOBAL_STATUS")
        origin_refs = rp["origin_assessments"]
        require(len(origin_refs) == len(api.origin.ORIGINS)
                and api.artifact.canonical_set(origin_refs, lambda r: r["artifact_id"]) == origin_refs, "WORKER_ORIGIN_REFS")
        origins = [ctx.t01._resolve_artifact(conn, api, value) for value in origin_refs]
        knowledge = api.assembly.DeviceFingerprintRequestAssembly.reconstruct_knowledge_bundle(
            named["knowledge_bundle"], lambda reference: ctx.t01._resolve_artifact(conn, api, reference.as_dict()))
        require({o.semantic_payload["origin_group"] for o in origins} == set(api.origin.ORIGINS)
                and all(api.origin.make_origin_assessment(o.semantic_payload,
                    evidence_snapshot_content=named["evidence_snapshot_content"], source_evaluability=named["source_evaluability"],
                    evidence_adapter_contract_set=named["evidence_adapter_contract_set"],
                    knowledge_bundle=named["knowledge_bundle"], knowledge=knowledge) == o for o in origins),
                "WORKER_ORIGIN_SCHEMA")
    require(cmp == comparison(api, gt, req, result, ctx.policy), "WORKER_COMPARISON_MISMATCH")
    compatibility = read(api, directory / "compatibility-report.json")
    require(set(compatibility) == {"checks"} and compatibility["checks"] == preflight["report"]["checks"],
            "WORKER_COMPATIBILITY_PREFLIGHT_MISMATCH")
    verify_lock(api, directory / "worker-completion.json", expected_digest, "WORKER")
    return worker, entry, cmp, compatibility["checks"]

def phase_b(args):
    """Parent orchestrates compatibility preflight + isolated product workers."""
    require(args.phase_a_lock_sha256 == PHASE_A_LOCK_SHA, "FROZEN_PHASE_A_LOCK_REQUIRED")
    output = new_directory(args.output, args.repo.resolve(),
        [args.foundation_db, args.task01_db, args.phase_a_lock.parent, T06A_RUN])
    with no_network():
        ctx = context(args, output)
        api = ctx.api
        lock, truths = checked_phase_a(ctx, args)
        started = now()
        require(api.validation.parse_utc(started) > api.validation.parse_utc(lock["lock_created_at_utc"]),
                "REGISTRATION_LOCK_MUST_PREEXIST_RESULT")
        source_copy = output / "task01-snapshot.sqlite3"
        source_identity = disposable_snapshot(args.task01_db, source_copy)
        snapshot_before, foundation_before = db_identity(source_copy), db_identity(ctx.foundation_copy)
        parent_inputs = {"foundation_sha256": sha(ctx.foundation_copy), "task01_sha256": sha(source_copy)}

        # R4 repair: exact 9/9 compatibility runs once in a separate fresh process.
        # It is retained and cryptographically bound; product workers verify it rather
        # than carrying its transient memory into the frozen snapshot memory envelope.
        preflight_directory = output / "compatibility-preflight"
        preflight_command = [sys.executable, "-I", "-B", str(Path(__file__).resolve()), "PRECHECK",
            "--repo", str(ctx.repo), "--foundation-db", str(ctx.foundation_copy),
            "--output", str(preflight_directory),
            "--phase-a-lock", str(args.phase_a_lock.resolve()), "--phase-a-lock-sha256", PHASE_A_LOCK_SHA,
            "--runner-sha256", ctx.runner_sha256,
            "--parent-foundation-sha256", parent_inputs["foundation_sha256"]]
        preflight_completed = subprocess.run(preflight_command, cwd=output, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1800, shell=False)
        retained = []
        for suffix, raw in (("stdout", preflight_completed.stdout), ("stderr", preflight_completed.stderr)):
            path = output / f"compatibility-preflight-{suffix}.log"
            with path.open("xb") as stream:
                stream.write(raw)
            retained.append(path)
        require(preflight_completed.returncode == 0, "COMPATIBILITY_PREFLIGHT_ABNORMAL_EXIT_OR_FAILURE")
        preflight_lines = preflight_completed.stdout.decode("utf-8").splitlines()
        require(len(preflight_lines) == 2 and preflight_lines[0] == "COMPATIBILITY_PREFLIGHT_STATUS=PASS"
                and preflight_lines[1].startswith("COMPATIBILITY_PREFLIGHT_SHA256="),
                "COMPATIBILITY_PREFLIGHT_COMPLETION_PROTOCOL")
        preflight_sha = preflight_lines[1].split("=", 1)[1]
        preflight_path = preflight_directory / "compatibility-preflight.json"
        preflight_report = verify_compatibility_preflight(
            ctx, args, preflight_path, preflight_sha, parent_inputs["foundation_sha256"])
        preflight = {
            "file": preflight_path.relative_to(output).as_posix(),
            "file_sha256": preflight_sha,
            "preflight_execution_id": preflight_report["preflight_execution_id"],
            "process_id": preflight_report["process_id"],
            "runner_sha256": preflight_report["runner_sha256"],
            "report": preflight_report,
        }
        retained.append(preflight_path)

        entries, comparisons, workers, worker_digests, compatibility = [], [], [], [], []
        for index, gt in enumerate(truths, 1):
            checked_phase_a(ctx, args)
            require(db_identity(source_copy) == snapshot_before and db_identity(ctx.foundation_copy) == foundation_before,
                    "PARENT_IMMUTABLE_INPUT_CHANGED")
            require(sha(preflight_path) == preflight_sha, "COMPATIBILITY_PREFLIGHT_CHANGED")
            verify_compatibility_preflight(
                ctx, args, preflight_path, preflight_sha, parent_inputs["foundation_sha256"])
            directory = output / f"worker-{index}"
            command = [sys.executable, "-I", "-B", str(Path(__file__).resolve()), "WORKER",
                "--repo", str(ctx.repo), "--foundation-db", str(ctx.foundation_copy),
                "--task01-db", str(source_copy), "--output", str(directory),
                "--phase-a-lock", str(args.phase_a_lock.resolve()), "--phase-a-lock-sha256", PHASE_A_LOCK_SHA,
                "--device-label", gt.semantic_payload["controlled_device_lab_label"],
                "--runner-sha256", ctx.runner_sha256,
                "--parent-foundation-sha256", parent_inputs["foundation_sha256"],
                "--parent-task01-sha256", parent_inputs["task01_sha256"],
                "--compatibility-report", str(preflight_path),
                "--compatibility-report-sha256", preflight_sha]
            completed = subprocess.run(command, cwd=output, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1800, shell=False)
            for suffix, raw in (("stdout", completed.stdout), ("stderr", completed.stderr)):
                path = output / f"worker-{index}-{suffix}.log"
                with path.open("xb") as stream:
                    stream.write(raw)
                retained.append(path)
            require(completed.returncode == 0, f"WORKER_{index}_ABNORMAL_EXIT_OR_FAILURE")
            lines = completed.stdout.decode("utf-8").splitlines()
            require(len(lines) == 2 and lines[0] == "WORKER_STATUS=COMPLETE"
                    and lines[1].startswith("WORKER_COMPLETION_SHA256="), "WORKER_COMPLETION_PROTOCOL")
            digest = lines[1].split("=", 1)[1]
            worker, entry, cmp, checks = validate_worker(
                ctx, args, directory, digest, index, gt, parent_inputs, preflight)
            require(not any(w["worker_execution_id"] == worker["worker_execution_id"] for w in workers), "WORKER_EXECUTION_REUSED")
            require(worker["process_id"] != preflight_report["process_id"], "PREFLIGHT_PROCESS_REUSED_AS_WORKER")
            workers.append(worker)
            worker_digests.append(digest)
            entries.append(entry)
            comparisons.append(cmp)
            compatibility.append({"controlled_device_lab_label": worker["device_label"], "checks": checks})
            for kind in ("request", "result", "comparison"):
                name = f"{kind}-{index}.json"
                copy_locked_bytes(directory / name, output / name, worker["retained_files"][name])
                retained.append(output / name)
        count = device_class_count(comparisons, ctx.policy)
        passed = all(c.semantic_payload["overall_validation_outcome"] == "PASS" for c in comparisons) and count >= ctx.policy.semantic_payload["minimum_correct_device_class_count_across_controlled_devices"]
        report = {"state": "OWNER_REVIEW_REQUIRED", "validation_run_id": lock["validation_run_id"],
            "profile": ref(ctx.profile), "product_validation_policy": ref(ctx.policy), "candidate_commit": COMMIT, "candidate_tree": TREE,
            "entries": entries, "correct_device_class_count": count, "policy_outcome": "PASS" if passed else "FAIL",
            "automatic_learning": False, "production_activation": False}
        write(api, output / "privacy-safe-comparison-report.json", report)
        retained.append(output / "privacy-safe-comparison-report.json")
        write(api, output / "compatibility-report.json", {
            "compatibility_preflight": {
                "file": preflight["file"],
                "file_sha256": preflight_sha,
                "preflight_execution_id": preflight_report["preflight_execution_id"],
                "process_id": preflight_report["process_id"],
                "runner_sha256": preflight_report["runner_sha256"],
            },
            "controlled_device_checks": compatibility,
        })
        retained.append(output / "compatibility-report.json")
        worker_refs = []
        for index, (worker, gt) in enumerate(zip(workers, truths), 1):
            path = output / f"worker-{index}" / "worker-completion.json"
            digest = worker_digests[index - 1]
            require(worker == validate_worker(ctx, args, path.parent, digest, index, gt, parent_inputs, preflight)[0],
                    "WORKER_CHANGED_BEFORE_AGGREGATION")
            for kind in ("request", "result", "comparison"):
                copied = output / f"{kind}-{index}.json"
                identity = worker["retained_files"][copied.name]
                require(copied.stat().st_size == identity["bytes"] and sha(copied) == identity["sha256"],
                        "AGGREGATED_WORKER_ARTIFACT_CHANGED")
            worker_refs.append({"device_label": worker["device_label"], "worker_execution_id": worker["worker_execution_id"],
                "file": path.relative_to(output).as_posix(), "file_sha256": digest,
                "runner_sha256": worker["runner_sha256"], "process_id": worker["process_id"]})
        checked_phase_a(ctx, args)
        require(sha(preflight_path) == preflight_sha, "COMPATIBILITY_PREFLIGHT_CHANGED_BEFORE_LOCK")
        verify_compatibility_preflight(
            ctx, args, preflight_path, preflight_sha, parent_inputs["foundation_sha256"])
        require(db_identity(args.task01_db) == source_identity and db_identity(source_copy) == snapshot_before
                and db_identity(ctx.foundation_copy) == foundation_before, "INPUT_OR_COPY_MUTATED")
        finish_integrity(ctx, args)
        digest = make_lock(api, output, "phase-b-lock.json", {"phase": "B", "validation_run_id": lock["validation_run_id"],
            "candidate_commit": COMMIT, "candidate_tree": TREE, "runner_sha256": ctx.runner_sha256, "helper_sha256": T07_SHA,
            "phase_a_lock_sha256": PHASE_A_LOCK_SHA, "phase_a_runner_sha256": PHASE_A_RUNNER_SHA,
            "phase_b_runner_sha256": ctx.runner_sha256,
            "compatibility_preflight": {
                "file": preflight["file"], "file_sha256": preflight_sha,
                "preflight_execution_id": preflight_report["preflight_execution_id"],
                "process_id": preflight_report["process_id"], "runner_sha256": preflight_report["runner_sha256"],
            },
            "worker_executions": worker_refs,
            "started_at_utc": started, "completed_at_utc": now(), "state": "OWNER_REVIEW_REQUIRED",
            "entries": entries, "policy_outcome": report["policy_outcome"],
            "task01_source_identity": source_identity, "foundation_source_identity": ctx.source_identity}, retained)
    print("PHASE_B_STATUS=OWNER_REVIEW_REQUIRED")
    print(f"POLICY_OUTCOME={report['policy_outcome']}")
    print(f"PHASE_B_LOCK_PATH={output / 'phase-b-lock.json'}")
    print(f"PHASE_B_LOCK_SHA256={digest}")
    for entry in entries:
        print(api.artifact.canonical_artifact_json(entry).decode())
    return 0

def owner_decision(api, path, lock_a, lock_b, artifacts):
    # The supplied external audit JSON uses reason_reference_text for §10.3's
    # reason/reference text. This is an audit envelope, never ArtifactContent.
    d = read(api, path)
    fields = {"decision_record_id", "decision_subject_type", "decision_subject_id", "decision", "decided_at_utc",
              "actor_role", "referenced_artifact_ids", "referenced_gate_ids", "reason_reference_text", "record_sha256"}
    require(set(d) == fields, "OWNER_DECISION_CLOSED_SCHEMA")
    uuid4(d["decision_record_id"])
    unsigned = {key: value for key, value in d.items() if key != "record_sha256"}
    require(hashlib.sha256(api.artifact.canonical_artifact_json(unsigned)).hexdigest() == d["record_sha256"], "OWNER_DECISION_DIGEST")
    require(d["actor_role"] == "OWNER" and d["decision"] in {"ACCEPT", "REJECT"}
            and d["decision_subject_type"] == "TASK04_PRODUCT_VALIDATION" and d["decision_subject_id"] == lock_a["validation_run_id"], "OWNER_DECISION_SCOPE")
    require(api.validation.parse_utc(d["decided_at_utc"]) > api.validation.parse_utc(lock_b["completed_at_utc"])
            and api.validation.parse_utc(d["decided_at_utc"]) <= api.validation.parse_utc(now()), "OWNER_REVIEW_MUST_FOLLOW_RESULTS")
    required_ids = sorted({item.artifact_id for item in artifacts})
    require(d["referenced_artifact_ids"] == required_ids and d["referenced_gate_ids"] == [GATE_ID]
            and isinstance(d["reason_reference_text"], str) and bool(d["reason_reference_text"]), "OWNER_REVIEW_EXACT_ARTIFACTS")
    return d


def phase_c(args):
    output = new_directory(args.output, args.repo.resolve(), [args.foundation_db, args.phase_a_lock.parent, args.phase_b_lock.parent, args.owner_decision, T06A_RUN])
    with no_network():
        ctx = context(args, output)
        api = ctx.api
        a, truths = checked_phase_a(ctx, args)
        b = verify_lock(api, args.phase_b_lock, args.phase_b_lock_sha256, "B")
        require(b["phase_a_lock_sha256"] == args.phase_a_lock_sha256 and b["validation_run_id"] == a["validation_run_id"]
                and b["state"] == "OWNER_REVIEW_REQUIRED" and len(b["entries"]) == 2, "PHASE_CHAIN_MISMATCH")
        report_name = "privacy-safe-comparison-report.json"
        report_identity = b["retained_files"].get(report_name)
        require(isinstance(report_identity, dict) and set(report_identity) == {"sha256", "bytes"},
                "PHASE_B_PRIVACY_REPORT_NOT_REGISTERED")
        report_source = args.phase_b_lock.parent / report_name
        require(report_source.is_file() and report_source.stat().st_size == report_identity["bytes"]
                and sha(report_source) == report_identity["sha256"], "PHASE_B_PRIVACY_REPORT_IDENTITY")
        # Retain the locked bytes, not a decoded/reconstructed/normalized report.
        report_bytes = report_source.read_bytes()
        require(len(report_bytes) == report_identity["bytes"]
                and hashlib.sha256(report_bytes).hexdigest() == report_identity["sha256"],
                "PHASE_B_PRIVACY_REPORT_CHANGED_DURING_READ")
        report_destination = output / report_name
        with report_destination.open("xb") as stream:
            stream.write(report_bytes)
        require(report_destination.stat().st_size == report_identity["bytes"]
                and sha(report_destination) == report_identity["sha256"], "PHASE_C_PRIVACY_REPORT_COPY_MISMATCH")
        artifacts, comparisons = list(truths), []
        for index, gt in enumerate(truths, 1):
            req = load_content(api, args.phase_b_lock.parent / f"request-{index}.json")
            result = load_content(api, args.phase_b_lock.parent / f"result-{index}.json")
            cmp = load_content(api, args.phase_b_lock.parent / f"comparison-{index}.json")
            require(cmp == comparison(api, gt, req, result, ctx.policy), "COMPARISON_RECOMPUTATION_MISMATCH")
            entry = b["entries"][index - 1]
            require(entry["ground_truth"] == ref(gt) and entry["request"] == ref(req) and entry["result"] == ref(result)
                    and entry["comparison"] == ref(cmp) and entry["controlled_device_lab_label"] == gt.semantic_payload["controlled_device_lab_label"], "REVIEW_BINDING_MISMATCH")
            artifacts.extend((req, result, cmp))
            comparisons.append(cmp)
        decision = owner_decision(api, args.owner_decision, a, b, artifacts)
        policy_pass = (all(c.semantic_payload["overall_validation_outcome"] == "PASS" for c in comparisons)
                       and device_class_count(comparisons, ctx.policy) >= ctx.policy.semantic_payload["minimum_correct_device_class_count_across_controlled_devices"])
        require(b["policy_outcome"] == ("PASS" if policy_pass else "FAIL"), "PHASE_B_POLICY_MISMATCH")
        passed = policy_pass and decision["decision"] == "ACCEPT"
        write(api, output / "owner-decision.json", decision)
        # Preserve exact prior retained evidence; no relabeling of A/B outputs.
        for path, name in ((args.phase_a_lock, "phase-a-lock.json"), (args.phase_b_lock, "phase-b-lock.json")):
            with (output / name).open("xb") as stream:
                stream.write(path.read_bytes())
        # Preserve the original audit bytes, never create a post-result registration.
        for index, gt in enumerate(truths, 1):
            binding = a["ground_truth_registrations"][index - 1]
            source = args.phase_a_lock.parent / binding["file"]
            destination = output / binding["file"]
            with destination.open("xb") as stream:
                stream.write(source.read_bytes())
            registration = artifact_registration(api, read(api, destination), gt, a["lock_created_at_utc"])
            require(sha(destination) == binding["file_sha256"]
                    and registration["registration_id"] == binding["registration_id"],
                    "PHASE_C_REGISTRATION_PRESERVATION")
        for index, item in enumerate(artifacts, 1):
            write(api, output / f"reviewed-artifact-{index}.json", document(item))
        execution = {"execution_id": str(uuid.uuid4()), "executor_kind": "TECHLEAD_GATE_TOOL",
            "repository_commit_sha": COMMIT, "repository_tree_sha": TREE, "procedure_or_test_suite_id": PROCEDURE,
            "environment_identity": ctx.t01._environment_identity(), "execution_artifact_sha256": sha(Path(__file__))}
        write(api, output / "t09-execution-evidence.json", {"validation_run_id": a["validation_run_id"],
            "executed_at_utc": now(), "status": "PASS" if passed else "FAIL", "policy_outcome": b["policy_outcome"],
            "owner_decision_record_id": decision["decision_record_id"], "owner_decision_record_sha256": decision["record_sha256"],
            "phase_a_lock_sha256": args.phase_a_lock_sha256, "phase_b_lock_sha256": args.phase_b_lock_sha256,
            "phase_a_ground_truth_registrations": a["ground_truth_registrations"],
            "profile": ref(ctx.profile), "candidate_commit": COMMIT, "candidate_tree": TREE,
            "network_attempt_count": 0, "production_action": False})
        checked_phase_a(ctx, args)
        verify_lock(api, args.phase_b_lock, args.phase_b_lock_sha256, "B")
        finish_integrity(ctx, args)
        require(report_destination.stat().st_size == report_identity["bytes"]
                and sha(report_destination) == report_identity["sha256"], "PHASE_C_PRIVACY_REPORT_CHANGED")
        retained = [{"evidence_label": path.stem, "file_sha256": sha(path), "media_type": "application/json",
                     "path_or_reference": path.name} for path in sorted(output.glob("*.json"))]
        require({"evidence_label": report_destination.stem, "file_sha256": report_identity["sha256"],
                 "media_type": "application/json", "path_or_reference": report_name} in retained,
                "FINAL_RETAINED_EVIDENCE_MISSING_PRIVACY_REPORT")
        inputs = [ref(item) for item in (ctx.profile, ctx.foundation, ctx.policy, ctx.t06a_result, ctx.t06a_proof)]
        proof = api.gate_proof.make_gate_proof_artifact({"proof_kind": "TASK04_PRODUCT_VALIDATION", "source_gate_id": GATE_ID,
            "candidate_repository_commit_sha": COMMIT, "candidate_repository_tree_sha": TREE,
            "input_artifact_refs": inputs + [ref(item) for item in artifacts],
            "procedure_or_test_suite_id": PROCEDURE, "proof_execution_identity": execution,
            "canonical_result_summary": f"validation_run={a['validation_run_id']};status={'PASS' if passed else 'FAIL'};controlled_devices=2;owner_review=RECORDED;automatic_learning=NO",
            "retained_evidence_refs": retained})
        gate = api.gate_result.make_gate_result_manifest({"gate_id": GATE_ID, "gate_contract_version": CONTRACT,
            "status": "PASS" if passed else "FAIL", "candidate_repository_commit_sha": COMMIT, "candidate_repository_tree_sha": TREE,
            "input_artifact_refs": inputs, "output_artifact_refs": [ref(item) for item in (*truths, *comparisons, proof)] if passed else [],
            "retained_evidence_refs": retained, "proof_execution_identity": execution,
            "trusted_time_inputs": {"foundation_knowledge_evaluation_at_utc": None, "foundation_admission_evaluation_at_utc": None, "knowledge_evaluation_at_utc": None},
            "decision_record_refs": [decision["decision_record_id"]]})
        for filename, item, builder in (("t09-gate-proof-artifact.json", proof, api.gate_proof.make_gate_proof_artifact),
                                        ("t09-gate-result-manifest.json", gate, api.gate_result.make_gate_result_manifest)):
            write(api, output / filename, document(item))
            require(load_content(api, output / filename, builder) == item, "FORMAL_ARTIFACT_ROUNDTRIP")
    print(f"GATE_EXECUTION_STATUS={'PASS' if passed else 'FAIL'}")
    print(f"GATE_PROOF_ARTIFACT={proof.artifact_id}")
    print(f"GATE_RESULT_MANIFEST={gate.artifact_id}")
    return 0 if passed else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("B", "C", "WORKER", "PRECHECK"),
                        help="Phase A is frozen evidence and cannot be recreated")
    parser.add_argument("--repo", type=Path, default=Path(r"C:\CaptivPortal-UI-Preview"))
    parser.add_argument("--foundation-db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="new external LAB directory; never reused")
    parser.add_argument("--task01-db", type=Path)
    parser.add_argument("--phase-a-lock", type=Path)
    parser.add_argument("--phase-a-lock-sha256")
    parser.add_argument("--phase-b-lock", type=Path)
    parser.add_argument("--phase-b-lock-sha256")
    parser.add_argument("--owner-decision", type=Path, help="external canonical §10.3 audit envelope; reason_reference_text stores reason/reference text")
    parser.add_argument("--device-label", choices=tuple(d["controlled_device_lab_label"] for d in DEVICES))
    parser.add_argument("--runner-sha256")
    parser.add_argument("--parent-foundation-sha256")
    parser.add_argument("--parent-task01-sha256")
    parser.add_argument("--compatibility-report", type=Path)
    parser.add_argument("--compatibility-report-sha256")
    args = parser.parse_args(argv)
    for field in (("task01_db", "phase_a_lock", "phase_a_lock_sha256", "device_label", "runner_sha256",
                   "parent_foundation_sha256", "parent_task01_sha256", "compatibility_report",
                   "compatibility_report_sha256") if args.phase == "WORKER" else
                  ("phase_a_lock", "phase_a_lock_sha256", "runner_sha256",
                   "parent_foundation_sha256") if args.phase == "PRECHECK" else
                  ("task01_db", "phase_a_lock", "phase_a_lock_sha256") if args.phase == "B" else
                  ("phase_a_lock", "phase_a_lock_sha256", "phase_b_lock", "phase_b_lock_sha256", "owner_decision") if args.phase == "C" else ()):
        if getattr(args, field) is None:
            parser.error("required: --" + field.replace("_", "-"))
    try:
        return {"B": phase_b, "C": phase_c, "WORKER": device_worker,
                "PRECHECK": compatibility_preflight}[args.phase](args)
    except Exception as exc:
        # Prerequisite/integrity/operational errors never fabricate formal PASS/FAIL outputs.
        print("GATE_EXECUTION_STATUS=BLOCKED")
        reason = str(exc) if isinstance(exc, Blocked) else getattr(exc, "reason_code", type(exc).__name__)
        print(f"BLOCKER={reason}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
