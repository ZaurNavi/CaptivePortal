"""External R14 T-09 controlled validation: three explicit, non-automatic phases.

A locks independent Owner-supplied truth before any result is accessed.
B uses the real pre-acceptance product path on disposable database snapshots.
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
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import sys
from types import SimpleNamespace
import uuid

COMMIT = "74f7c7add401e5fec0469d49770466c2747c03cf"
TREE = "7e93a4863909c3e807a9d8239924d13e0a0d7f71"
PROFILE_ID = "ClassificationRuntimeProfile:v1:sha256:75f9d0107d852d58899e869dc9c64c7b311f7423930c60b828a0aa30d2f4c3ff"
POLICY_ID = "ProductValidationPolicy:v1:sha256:806779ca1844e55083a2c1c464cf8d94a9bdd0b2f97436d203b63fd03e81bea5"
T06A_RESULT_ID = "GateResultManifest:v1:sha256:5af29fa71f171d1d03e30b1583b26f60f8e539dd49bad97b3b96067be3883e82"
T06A_PROOF_ID = "GateProofArtifact:v1:sha256:984640314cbfe2d091fc60c54ed43144e223b730579f425c8728b40cc1e4b003"
LAB_ROOT = Path(r"C:\CaptivPortal-Lab")
T07_PATH = LAB_ROOT / "gates/task04/t07/task04-t07-gate-r3.py"
T07_SHA = "1a133178530b31f4ccea7b025868afac6103447a09daf3cae75a33798ec9db01"
T06A_RUN = LAB_ROOT / "gates/task04/t06a/official-rebind-20260929-T06A-02/28f009b9-2eb7-480c-95c1-fe5e1c00e1b5"
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
    require(re.fullmatch(r"[0-9a-f]{64}", expected_sha or "") is not None and sha(path) == expected_sha, "LOCK_IDENTITY_CHANGED")
    lock = read(api, path)
    require(lock["phase"] == phase and lock["candidate_commit"] == COMMIT and lock["candidate_tree"] == TREE
            and lock["runner_sha256"] == sha(Path(__file__)) and lock["helper_sha256"] == T07_SHA,
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
    ctx.h.helpers()  # Recheck pinned T01/T06A identities without executing gates.


def phase_a(args):
    output = new_directory(args.output, args.repo.resolve(), [args.foundation_db, T06A_RUN])
    with no_network():
        ctx = context(args, output)
        api = ctx.api
        run_id, recorded = str(uuid.uuid4()), now()
        records, registrations = [], []
        retained = []
        for index, device in enumerate(DEVICES, 1):
            item = ground_truth(api, {**normalized_device(api, device), "validation_run_id": run_id, "recorded_at_utc": recorded})
            path = output / f"ground-truth-{index}.json"
            write(api, path, document(item))
            require(load_content(api, path, lambda p: ground_truth(api, p)) == item, "GROUND_TRUTH_ROUNDTRIP")
            retained.append(path)
            records.append(ref(item))
            registered_at = now()
            registration = artifact_registration(api, {
                "registration_schema_version": 1, "registration_id": str(uuid.uuid4()),
                "artifact_id": item.artifact_id, "registered_at_utc": registered_at,
                "registered_by_role": REGISTRATION_ROLE, "repository_commit_sha": COMMIT,
                "repository_tree_sha": TREE, "decision_record_refs": [],
                "notes_reference_metadata": {"registration_context": "T09_PHASE_A_PRE_RESULT",
                                             "validation_run_id": run_id},
            }, item, registered_at)
            registration_path = output / f"ground-truth-registration-{index}.json"
            write(api, registration_path, registration)
            require(artifact_registration(api, read(api, registration_path), item, registered_at) == registration,
                    "ARTIFACT_REGISTRATION_ROUNDTRIP")
            retained.append(registration_path)
            registrations.append({"registration_id": registration["registration_id"],
                "artifact_id": item.artifact_id, "file": registration_path.name,
                "file_sha256": sha(registration_path)})
        for name, item in (("exact-profile.json", ctx.profile), ("exact-foundation.json", ctx.foundation),
                           ("exact-product-policy.json", ctx.policy), ("t06a-result.json", ctx.t06a_result), ("t06a-proof.json", ctx.t06a_proof)):
            write(api, output / name, document(item))
            retained.append(output / name)
        finish_integrity(ctx, args)
        lock_created = now()
        for index, device in enumerate(DEVICES, 1):
            gt = load_content(api, output / f"ground-truth-{index}.json", lambda p: ground_truth(api, p))
            artifact_registration(api, read(api, output / f"ground-truth-registration-{index}.json"), gt, lock_created)
        digest = make_lock(api, output, "phase-a-lock.json", {
            "phase": "A", "validation_run_id": run_id, "execution_id": run_id, "executed_at_utc": recorded,
            "lock_created_at_utc": lock_created,
            "candidate_commit": COMMIT, "candidate_tree": TREE, "runner_sha256": sha(Path(__file__)),
            "helper_sha256": T07_SHA, "profile": ref(ctx.profile), "foundation": ref(ctx.foundation),
            "product_validation_policy": ref(ctx.policy), "classification_foundation_valid_from_utc": ctx.valid_from,
            "ground_truth_refs": records, "ground_truth_registrations": registrations,
            "device_bindings": [normalized_device(api, d) for d in DEVICES],
            "foundation_source_identity": ctx.source_identity}, retained)
    print("PHASE_A_STATUS=GROUND_TRUTH_LOCKED")
    print(f"PHASE_A_LOCK_PATH={output / 'phase-a-lock.json'}")
    print(f"PHASE_A_LOCK_SHA256={digest}")
    return 0


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


def phase_b(args):
    output = new_directory(args.output, args.repo.resolve(), [args.foundation_db, args.task01_db, args.phase_a_lock.parent, T06A_RUN])
    with no_network():
        ctx = context(args, output, full=True)
        api, h, t01 = ctx.api, ctx.h, ctx.t01
        lock, truths = checked_phase_a(ctx, args)
        started = now()
        require(api.validation.parse_utc(started) > api.validation.parse_utc(lock["executed_at_utc"]), "GROUND_TRUTH_MUST_PREEXIST_RESULT")
        require(api.validation.parse_utc(started) > api.validation.parse_utc(lock["lock_created_at_utc"]),
                "REGISTRATION_LOCK_MUST_PREEXIST_RESULT")
        source_copy = output / "task01-snapshot.sqlite3"
        source_identity = disposable_snapshot(args.task01_db, source_copy)
        classifier = h.canonical_content(h.T06_MANIFEST_PATH, api,
            lambda p: api.artifact.make_artifact_content("ClassifierArtifactManifest", p),
            ctx.profile.semantic_payload["classifier_artifact_manifest"]["artifact_id"])
        control = api.control.DeviceFingerprintControlPlaneStore(ctx.foundation_copy)
        overlay = h.ImmutableOverlay(control, classifier)
        contents = {key: overlay.load_artifact(value["artifact_id"], value["content_sha256"])
                    for key, value in ctx.profile.semantic_payload.items() if isinstance(value, dict)}
        with closing(t01.open_foundation_read_only(ctx.foundation_copy)) as conn:
            compatibility = ctx.t06a.compatibility(conn, api, contents, ctx.lineage)
            require(len(compatibility) == 9 and all(row["status"] == "PASS" for row in compatibility), "PROFILE_COMPATIBILITY_FAILED")
            retention = h.resolve_retention(conn, api, t01, ctx.lineage)
        def compatible(profile, foundation, bundle, _knowledge, policy, adapters, manifest):
            return (profile == ctx.profile and foundation == ctx.foundation
                    and bundle == contents["knowledge_bundle"] and policy == contents["classification_policy"]
                    and adapters == contents["evidence_adapter_contract_set"] and manifest == classifier)
        reader = api.read.DeviceFingerprintReadService(str(source_copy), retention_days=30)
        service = api.assembly.DeviceFingerprintRequestAssembly(control_plane_store=overlay,
            read_service=reader, compatibility_hook=compatible, utc_clock=now, process_memory_guard=memory_guard)
        store = api.persistence.DeviceFingerprintClassificationStore(output / "classification.sqlite3",
            source_copy, control_plane_store=overlay, utc_clock=now)
        store.initialize()
        snapshot_before = db_identity(source_copy)
        foundation_before = db_identity(ctx.foundation_copy)
        retained, entries, comparisons = [], [], []
        for index, gt in enumerate(truths, 1):
            checked_phase_a(ctx, args)  # Verify lock again immediately before result creation.
            p = gt.semantic_payload
            assembled = service.assemble_pre_acceptance_candidate(ctx.profile, p["site_id"], p["observed_mac"], p["window_start_utc"], p["window_end_utc"])
            require(assembled.execution_context == "PRE_ACCEPTANCE_CANDIDATE" and assembled.classification_runtime_profile == ctx.profile
                    and assembled.foundation_runtime_profile == ctx.foundation and not overlay.pin_calls, "PRODUCT_PATH_PROFILE_MISMATCH")
            snapshot = assembled.evidence_snapshot_content.semantic_payload
            require(all(snapshot[key] == p[key] for key in ("site_id", "observed_mac", "window_start_utc", "window_end_utc")), "PRODUCT_WINDOW_BINDING_MISMATCH")
            core = store.persist(assembled, retention_policy=retention,
                pre_acceptance_foundation_runtime_profile_admission_manifest=ctx.lineage.admission)
            require(store.load_core(core.classification_id) == core and core.classification_result_id == assembled.classification_result.artifact_id
                    and core.classification_request_manifest_id == assembled.classification_request_manifest.artifact_id, "PRODUCT_PERSISTENCE_MISMATCH")
            cmp = comparison(api, gt, assembled.classification_request_manifest, assembled.classification_result, ctx.policy)
            comparisons.append(cmp)
            for kind, item in (("request", assembled.classification_request_manifest), ("result", assembled.classification_result), ("comparison", cmp)):
                path = output / f"{kind}-{index}.json"
                write(api, path, document(item))
                require(load_content(api, path) == item, "PRODUCT_ARTIFACT_ROUNDTRIP")
                retained.append(path)
            entries.append({"controlled_device_lab_label": p["controlled_device_lab_label"], "ground_truth": ref(gt),
                "request": ref(assembled.classification_request_manifest), "result": ref(assembled.classification_result), "comparison": ref(cmp),
                "classification_id": core.classification_id})
        count = device_class_count(comparisons, ctx.policy)
        passed = all(c.semantic_payload["overall_validation_outcome"] == "PASS" for c in comparisons) and count >= ctx.policy.semantic_payload["minimum_correct_device_class_count_across_controlled_devices"]
        report = {"state": "OWNER_REVIEW_REQUIRED", "validation_run_id": lock["validation_run_id"],
            "profile": ref(ctx.profile), "product_validation_policy": ref(ctx.policy), "candidate_commit": COMMIT, "candidate_tree": TREE,
            "entries": entries, "correct_device_class_count": count, "policy_outcome": "PASS" if passed else "FAIL",
            "automatic_learning": False, "production_activation": False}
        # No raw packet/payload/header/UA/CH/IP or personal identity in this report.
        write(api, output / "privacy-safe-comparison-report.json", report)
        retained.append(output / "privacy-safe-comparison-report.json")
        write(api, output / "compatibility-report.json", {"checks": compatibility})
        retained.append(output / "compatibility-report.json")
        checked_phase_a(ctx, args)
        require(db_identity(args.task01_db) == source_identity and db_identity(source_copy) == snapshot_before
                and db_identity(ctx.foundation_copy) == foundation_before, "INPUT_OR_COPY_MUTATED")
        finish_integrity(ctx, args)
        digest = make_lock(api, output, "phase-b-lock.json", {"phase": "B", "validation_run_id": lock["validation_run_id"],
            "candidate_commit": COMMIT, "candidate_tree": TREE, "runner_sha256": sha(Path(__file__)), "helper_sha256": T07_SHA,
            "phase_a_lock_sha256": args.phase_a_lock_sha256, "started_at_utc": started, "completed_at_utc": now(),
            "state": "OWNER_REVIEW_REQUIRED", "entries": entries, "policy_outcome": report["policy_outcome"],
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
    parser.add_argument("phase", choices=("A", "B", "C"))
    parser.add_argument("--repo", type=Path, default=Path(r"C:\CaptivPortal-UI-Preview"))
    parser.add_argument("--foundation-db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="new external LAB directory; never reused")
    parser.add_argument("--task01-db", type=Path)
    parser.add_argument("--phase-a-lock", type=Path)
    parser.add_argument("--phase-a-lock-sha256")
    parser.add_argument("--phase-b-lock", type=Path)
    parser.add_argument("--phase-b-lock-sha256")
    parser.add_argument("--owner-decision", type=Path, help="external canonical §10.3 audit envelope; reason_reference_text stores reason/reference text")
    args = parser.parse_args(argv)
    for field in (("task01_db", "phase_a_lock", "phase_a_lock_sha256") if args.phase == "B" else
                  ("phase_a_lock", "phase_a_lock_sha256", "phase_b_lock", "phase_b_lock_sha256", "owner_decision") if args.phase == "C" else ()):
        if getattr(args, field) is None:
            parser.error("required: --" + field.replace("_", "-"))
    try:
        return {"A": phase_a, "B": phase_b, "C": phase_c}[args.phase](args)
    except Exception as exc:
        # Prerequisite/integrity errors never fabricate formal PASS/FAIL outputs.
        print("GATE_EXECUTION_STATUS=BLOCKED")
        print(f"BLOCKER={str(exc) if isinstance(exc, Blocked) else type(exc).__name__}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
