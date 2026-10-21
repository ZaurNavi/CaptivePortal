"""External T-05 gate. Importing this module never executes the official gate."""

from __future__ import annotations

import argparse
import builtins
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import importlib.util
import inspect
import io
import json
import os
from pathlib import Path
import pickle
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from types import SimpleNamespace
from typing import Any

sys.dont_write_bytecode = True

COMMIT = "74f7c7add401e5fec0469d49770466c2747c03cf"
TREE = "7e93a4863909c3e807a9d8239924d13e0a0d7f71"
PROFILE_ID = "ClassificationRuntimeProfile:v1:sha256:75f9d0107d852d58899e869dc9c64c7b311f7423930c60b828a0aa30d2f4c3ff"
T06A_PROOF_ID = "GateProofArtifact:v1:sha256:00bbf679be6e35d48b93d302ff7439065df78cdac507d6cc8e15f4f1876a35b0"
T06A_RESULT_ID = "GateResultManifest:v1:sha256:9bdcc53e59104010202e2aa1eb44b49c348eda27eed95061d66322de4ed95735"
T01_PATH = Path(__file__).resolve().parents[1] / "t01" / "task04-t01-gate-rebind-20260929.py"
T01_SHA = "ee17cbd9a1c6e8e5ac510559ca0d6a21768a26fbb90ae98cb1ed4550d0446668"
T06A_PATH = Path(__file__).resolve().parents[1] / "t06a" / "task04-t06a-gate-rebind-20260929.py"
T06A_SHA = "667bc5777ef2d9c6b6f1277c53e09b9dc6e3c4a8d23b42cfd0867ba19647d814"
T06_MANIFEST_PATH = Path(__file__).resolve().parents[1] / "t06" / "official-rebind-20260929-T06-01" / "e5514fd4-27b8-493e-9544-beb70d168c1a" / "t06-manifest.json"
GATE_ID = "T-05"
CONTRACT = "R14-T-05-v1"
PROCEDURE = "T-05-request-assembly-determinism-v1"
PROOF_KIND = "REQUEST_ASSEMBLY_DETERMINISM"
CASES = tuple(f"T05-M{i:02}" for i in range(1, 13))
RETAINED = (
    "t05-execution-evidence.json", "t05-direct-matrix.json", "t05-pointer-switch-trace.json",
    "t05-pure-core-io-proof.json", "t05-freshness-report.json", "t05-pytest.log",
    "t05-summary.txt",
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


def pinned(path: Path, digest: str, name: str):
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
    if not T01_PATH.is_file() or sha(T01_PATH) != T01_SHA:
        raise Blocked("BLOCKED_HARDENED_HELPER_CHANGED", "T-01")
    if not T06A_PATH.is_file() or sha(T06A_PATH) != T06A_SHA:
        raise Blocked("BLOCKED_HARDENED_HELPER_CHANGED", "T-06A")
    if _T01 is None:
        _T01 = pinned(T01_PATH, T01_SHA, "t05_pinned_t01")
    if _T06A is None:
        _T06A = pinned(T06A_PATH, T06A_SHA, "t05_pinned_t06a")
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
        "fusion": "app.device_fingerprint.fusion",
        "classification_request": "app.device_fingerprint.classification_request",
        "control": "app.device_fingerprint.control_plane_store",
        "freshness": "app.device_fingerprint.fe5_external_knowledge",
        "snapshot_fixture": "tests.device_fingerprint_task04_t01.test_snapshot_service",
    }.items()}
    return SimpleNamespace(**(vars(base) | extra))


def canonical_content(path: Path, api: Any, builder: Any, expected_id: str):
    try:
        raw = path.read_bytes()
        value = api.artifact.decode_artifact_json(raw.decode("utf-8"))
        if set(value) != {"artifact_type", "artifact_schema_version", "artifact_id",
                          "content_sha256", "semantic_payload"}:
            raise ValueError("shape")
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
    p = result.semantic_payload
    expected = sorted([ref(profile), ref(proof)], key=lambda item: item["artifact_id"])
    if (p["gate_id"] != "T-06A" or p["gate_contract_version"] != "R14-T-06A-v1"
            or p["status"] != "PASS" or p["candidate_repository_commit_sha"] != COMMIT
            or p["candidate_repository_tree_sha"] != TREE
            or sorted(p["output_artifact_refs"], key=lambda item: item["artifact_id"]) != expected
            or proof.semantic_payload["proof_kind"] != "CLASSIFICATION_PROFILE_COMPATIBILITY"
            or proof.semantic_payload["source_gate_id"] != "T-06A"
            or proof.semantic_payload["candidate_repository_commit_sha"] != COMMIT
            or proof.semantic_payload["candidate_repository_tree_sha"] != TREE
            or proof.semantic_payload["proof_execution_identity"]["execution_artifact_sha256"] != T06A_SHA):
        raise Blocked("BLOCKED_T06A_PREREQUISITE", "result or proof contract")
    try:
        for row in p["retained_evidence_refs"]:
            name = row["path_or_reference"]
            if Path(name).name != name or name not in T06A_FILES or sha(run_dir / name) != row["file_sha256"]:
                raise ValueError("retained evidence")
        execution = json.loads((run_dir / "t06a-execution-evidence.json").read_text())
        if (execution["runner_sha256"] != T06A_SHA or
                execution["profile"] != ref(profile) or
                execution["t01_helper_sha256"] != T01_SHA):
            raise ValueError("execution identity")
    except Exception as exc:
        raise Blocked("BLOCKED_T06A_PREREQUISITE", "evidence") from exc
    return profile, proof, result


class ReadOnlyArtifacts:
    """Only immutable refs; mutable current pointers are intentionally inaccessible."""

    def __init__(self, connection, api, helper):
        self.connection, self.api, self.helper = connection, api, helper
        self.extra: dict[str, Any] = {}
        self.loads: list[str] = []
        self.pins: list[str] = []

    def load_artifact(self, artifact_id, digest=None):
        self.loads.append(artifact_id)
        if artifact_id in self.extra:
            item = self.extra[artifact_id]
        else:
            item = self.helper._load_artifact(self.connection, self.api,
                                              artifact_id.split(":", 1)[0],
                                              artifact_id.rsplit(":", 1)[1])
        if digest is not None and item.content_sha256 != digest:
            raise ValueError("digest mismatch")
        return item

    def pin_active_profile(self, kind):
        self.pins.append(kind)
        raise AssertionError("candidate execution must not pin any pointer")


def _time_for(api, profile, store, t01):
    foundation = store.load_artifact(**_ref_kwargs(profile.semantic_payload["foundation_runtime_profile"]))
    epoch, start, end, observed = t01._window(
        api, foundation, lambda artifact_ref: store.load_artifact(
            artifact_ref.artifact_id, artifact_ref.content_sha256))
    bundle = store.load_artifact(**_ref_kwargs(profile.semantic_payload["knowledge_bundle"]))
    knowledge = api.assembly.DeviceFingerprintRequestAssembly.reconstruct_knowledge_bundle(
        bundle, lambda artifact_ref: store.load_artifact(
            artifact_ref.artifact_id, artifact_ref.content_sha256))
    retrieved = [getattr(knowledge, f"{slot}_provenance").semantic_payload["retrieved_at_utc"]
                 for slot in ("k1", "k2b", "k4")]
    now = max(api.validation.parse_utc(item) for item in [end, *retrieved]) + timedelta(seconds=1)
    return foundation, knowledge, epoch, start, end, observed, api.validation.format_utc(now)


def _ref_kwargs(value):
    return {"artifact_id": value["artifact_id"], "digest": value["content_sha256"]}


def _assembly(api, store, read, clock):
    return api.assembly.DeviceFingerprintRequestAssembly(
        control_plane_store=store, read_service=read, compatibility_hook=lambda *_: True,
        utc_clock=lambda: clock, process_memory_guard=lambda _limit: True)


def _tuple(result):
    return [ref(getattr(result, field)) for field in (
        "classification_runtime_profile", "foundation_runtime_profile", "knowledge_bundle",
        "classification_policy", "evidence_adapter_contract_set", "classifier_artifact_manifest")]


def _result_trace(result):
    request = result.classification_request_manifest
    classification = result.classification_result
    if classification.semantic_payload["classification_request_digest"] != request.content_sha256:
        raise SemanticFailure("RESULT_REQUEST_DIGEST")
    return {"request": ref(request), "result": ref(classification),
            "result_classification_request_digest": classification.semantic_payload[
                "classification_request_digest"],
            "knowledge_evaluation_at_utc": result.knowledge_evaluation_at_utc,
            "execution_set": _tuple(result)}


def _pin(api, profile, time_utc):
    pointer = api.control.ActiveProfilePointerV1(
        "classification", profile.artifact_id, profile.content_sha256,
        "11111111-1111-4111-8111-111111111111",
        "22222222-2222-4222-8222-222222222222", time_utc)
    return api.control.PinnedRuntimeProfile(
        pointer, profile,
        api.artifact.make_artifact_content("RuntimeProfileAdmissionManifest", {}),
        api.artifact.make_artifact_content("RuntimeProfileActivationRecord", {}),
        api.artifact.make_artifact_content("RuntimeProfileValidityRecord", {}))


class SwitchStore(ReadOnlyArtifacts):
    def __init__(self, base, old, new, time_utc):
        super().__init__(base.connection, base.api, base.helper)
        self.extra = dict(base.extra)
        self.current = old
        self.old, self.new = old, new
        self.time_utc = time_utc
        self.lock = threading.RLock()
        self.request_context = threading.local()
        self.operation_trace: list[dict[str, Any]] = []
        self.sequence = 0
        self.pins_by_thread = {}
        self.foundation_pointer_reads = 0
        self.mutable_current = {"foundation": old.semantic_payload["foundation_runtime_profile"]}

    def record(self, operation, *, request_label=None, **arguments):
        with self.lock:
            self.sequence += 1
            self.operation_trace.append({
                "sequence": self.sequence,
                "request_label": request_label or getattr(self.request_context, "label", None),
                "thread_ident": threading.get_ident(),
                "thread_name": threading.current_thread().name,
                "operation": operation,
                "arguments": arguments,
            })

    def begin_request(self, label):
        self.request_context.label = label
        self.request_context.pinned_profile = None
        self.record("REQUEST_START")

    def end_request(self):
        self.record("REQUEST_END")
        self.request_context.label = None
        self.request_context.pinned_profile = None

    def load_artifact(self, artifact_id, digest=None):
        pinned_profile = getattr(self.request_context, "pinned_profile", None)
        foundation_ref = (pinned_profile.semantic_payload["foundation_runtime_profile"]
                          if pinned_profile is not None else None)
        source = ("pinned_classification_runtime_profile.foundation_runtime_profile"
                  if foundation_ref is not None and artifact_id == foundation_ref["artifact_id"]
                  else "immutable_artifact_ref")
        self.record("LOAD_ARTIFACT", artifact_id=artifact_id,
                    requested_digest=digest, source=source)
        return super().load_artifact(artifact_id, digest)

    def pin_active_profile(self, kind):
        with self.lock:
            self.record("PIN_ACTIVE_PROFILE", kind=kind)
            if kind != "classification":
                self.foundation_pointer_reads += 1
                raise SemanticFailure("FOUNDATION_POINTER_READ")
            item = self.current
            ident = threading.get_ident()
            self.pins_by_thread[ident] = self.pins_by_thread.get(ident, 0) + 1
            self.request_context.pinned_profile = item
        return _pin(self.api, item, self.time_utc)

    def switch(self):
        with self.lock:
            old = self.current
            self.current = self.new
            self.mutable_current.update({
                field: self.new.semantic_payload[field] for field in (
                    "foundation_runtime_profile", "knowledge_bundle", "classification_policy")})
            self.record("POINTER_SWITCH", old_profile=ref(old), new_profile=ref(self.new),
                        mutable_current_foundation=self.mutable_current["foundation"])


def _assert_pin_first(operation_trace):
    if [row["sequence"] for row in operation_trace] != list(range(1, len(operation_trace) + 1)):
        raise SemanticFailure("CLASSIFICATION_NOT_PINNED_FIRST", "non-monotonic trace")
    first, counts = {}, {}
    for label in ("A", "B"):
        rows = [row for row in operation_trace if row["request_label"] == label]
        starts = [row for row in rows if row["operation"] == "REQUEST_START"]
        ends = [row for row in rows if row["operation"] == "REQUEST_END"]
        if len(starts) != 1 or len(ends) != 1 or starts[0]["sequence"] >= ends[0]["sequence"]:
            raise SemanticFailure("CLASSIFICATION_NOT_PINNED_FIRST", f"request {label} boundary")
        store_ops = [row for row in rows if starts[0]["sequence"] < row["sequence"] < ends[0]["sequence"]
                     and row["operation"] in ("PIN_ACTIVE_PROFILE", "LOAD_ARTIFACT")]
        pins = [row for row in store_ops if row["operation"] == "PIN_ACTIVE_PROFILE"
                and row["arguments"]["kind"] == "classification"]
        if (not store_ops or store_ops[0]["operation"] != "PIN_ACTIVE_PROFILE"
                or store_ops[0]["arguments"]["kind"] != "classification" or len(pins) != 1
                or any(row["operation"] == "PIN_ACTIVE_PROFILE" and
                       row["arguments"]["kind"] != "classification" for row in store_ops)):
            raise SemanticFailure("CLASSIFICATION_NOT_PINNED_FIRST", f"request {label}")
        first[label] = "PIN_ACTIVE_PROFILE:classification"
        counts[label] = len(pins)
    return {"pin_first_per_request": {"A": True, "B": True},
            "first_store_operation": first,
            "classification_pin_count_per_request": counts}


def _pointer_matrix(api, base, profile, read, site, mac, start, end, clock):
    # The alternate profile is a controlled fixture, never a formal input ref.
    payload = profile.semantic_payload
    old_classifier = api.artifact.make_artifact_content("ClassifierArtifactManifest", {"controlled_alternate": True})
    payload["classifier_artifact_manifest"] = ref(old_classifier)
    old = api.profiles.make_classification_runtime_profile(payload)
    store = SwitchStore(base, old, profile, clock)
    # SQLite's accepted read transaction belongs to the main thread.  The
    # controlled switch fixture snapshots only the immutable refs already
    # resolved by the successful exact-P assembly before spawning request A.
    for artifact_id in set(base.loads):
        store.extra[artifact_id] = base.load_artifact(artifact_id)
    store.extra[old_classifier.artifact_id] = old_classifier
    store.record("CONTROLLED_ALTERNATE_PROFILE_NOT_FORMAL_T05_INPUT", profile=ref(old))
    reached = threading.Event()
    release = threading.Event()
    errors = []
    results = {}
    original = store.pin_active_profile

    def pin_with_barrier(kind):
        item = original(kind)
        if threading.current_thread().name == "T05-request-A":
            store.record("REQUEST_A_CLASSIFICATION_PINNED", profile=ref(item.runtime_profile))
            reached.set()
            if not release.wait(60):
                raise RuntimeError("switch barrier timeout")
        return item

    store.pin_active_profile = pin_with_barrier
    service = _assembly(api, store, read, clock)

    def request_a():
        store.begin_request("A")
        try:
            results["A"] = service.assemble_production(site, mac, start, end)
        except Exception as exc:
            errors.append(exc)
        finally:
            store.end_request()

    thread = threading.Thread(target=request_a, name="T05-request-A")
    thread.start()
    if not reached.wait(60):
        release.set()
        thread.join()
        raise SemanticFailure("POINTER_BARRIER_NOT_REACHED")
    store.record("REQUEST_A_BARRIER_REACHED", request_label="A")
    store.switch()
    release.set()
    thread.join(120)
    if thread.is_alive() or errors:
        raise SemanticFailure("POINTER_SWITCH_EXECUTION", repr(errors))
    store.record("REQUEST_A_RESOLVED", request_label="A", execution_set=_tuple(results["A"]))
    store.begin_request("B")
    try:
        results["B"] = service.assemble_production(site, mac, start, end)
    finally:
        store.end_request()
    store.record("REQUEST_B_RESOLVED", request_label="B", execution_set=_tuple(results["B"]))
    pin_first = _assert_pin_first(store.operation_trace)
    if (_tuple(results["A"])[0] != ref(old) or _tuple(results["B"])[0] != ref(profile)
            or any(store.pins_by_thread.get(ident) != 1 for ident in store.pins_by_thread)
            or len(store.pins_by_thread) != 2 or store.foundation_pointer_reads):
        raise SemanticFailure("MIXED_GENERATION")
    for key, item in (("A", old), ("B", profile)):
        expected = [ref(item)] + [item.semantic_payload[field] for field in (
            "foundation_runtime_profile", "knowledge_bundle", "classification_policy",
            "evidence_adapter_contract_set", "classifier_artifact_manifest")]
        if _tuple(results[key]) != expected:
            raise SemanticFailure("TORN_EXECUTION_SET", key)
    return {"operation_trace": store.operation_trace, "mixed_generation_detected": False,
            "foundation_pointer_read_count": store.foundation_pointer_reads,
            **pin_first,
            "old_request": _result_trace(results["A"]),
            "new_request": _result_trace(results["B"])}


def _run_pytest(repo: Path, run_dir: Path):
    temp = run_dir / "pytest-temp"
    temp.mkdir()
    command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
               "--basetemp", str(temp / "base"), "tests/device_fingerprint_task04_04d_request"]
    env = dict(os.environ)
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTEST_ADDOPTS="", TEMP=str(temp), TMP=str(temp),
               TMPDIR=str(temp), PYTHONPYCACHEPREFIX=str(temp / "pycache"))
    result = subprocess.run(command, cwd=repo, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                            errors="replace", timeout=1800)
    (run_dir / "t05-pytest.log").write_text(result.stdout, encoding="utf-8")
    return result.returncode, command


def _freshness(api, knowledge):
    records = {}
    for slot in ("k1", "k2b", "k4"):
        provenance = getattr(knowledge, f"{slot}_provenance")
        policy = getattr(knowledge, f"{slot}_freshness_policy")
        p = policy.semantic_payload
        origin = api.validation.parse_utc(provenance.semantic_payload["retrieved_at_utc"])
        instants = {"fresh": origin + timedelta(milliseconds=p["fresh_max_age_ms"])}
        if p["stale_max_age_ms"] > p["fresh_max_age_ms"]:
            instants["stale"] = origin + timedelta(milliseconds=p["fresh_max_age_ms"] + 1)
        try:
            instants["expired"] = origin + timedelta(milliseconds=p["stale_max_age_ms"] + 1)
        except OverflowError:
            # The exact accepted p0f freshness policy uses INT64_MAX. There
            # is no representable UTC instant at which that source expires.
            pass
        slot_rows = []
        for expected, instant in instants.items():
            actual = api.freshness.evaluate_external_knowledge_freshness(
                provenance, policy, knowledge_evaluation_at_utc=api.validation.format_utc(instant))
            if actual["freshness_state"] != expected:
                raise SemanticFailure("FRESHNESS_POLICY_MISMATCH", slot)
            slot_rows.append({"expected": expected, "evaluation_at_utc": api.validation.format_utc(instant),
                              "actual": actual})
        records[slot] = {"provenance": ref(provenance), "policy": ref(policy), "cases": slot_rows,
                         "expired_representable": "expired" in instants}
    return records


def _matching_k1_row(api, helper, epoch, observed, ingested, knowledge):
    # Select a concrete accepted K1 record rather than inventing a DHCP claim.
    source = next(record for record in knowledge.k1_record_set.semantic_payload["records"]
                  if {item["dimension_name"]: item["canonical_target_id"]
                      for item in record["candidate_taxonomy_refs"]
                      if item["outcome_kind"] == "CANONICAL_VALUE"}.get("platform_family") == "android")
    payload = dict(helper.KNOWN_DHCP)
    for field, predicate in source["dhcp_predicates"].items():
        if predicate["mode"] in ("EXACT_VALUE", "EXACT_SEQUENCE"):
            payload[field] = predicate["value"]
    row = helper._fixture_row(api, epoch, observed, ingested, 1,
                              raw=api.validation.canonical_json(payload))
    row.update(source_subtype=payload["message_type"], extractor_name="packet-dhcp")
    return row, source["canonical_record_id"]


def _guarded_core_child(repo: Path, input_path: Path, variant: str):
    sys.path.insert(0, str(repo))
    inputs = pickle.loads(input_path.read_bytes())
    fusion = candidate(repo, "app.device_fingerprint.fusion")
    # CPython imports _strptime lazily on its first datetime.strptime call.
    # Warm the interpreter runtime before the measured pure-core boundary.
    datetime.strptime("2020-01-01T00:00:00.000Z", "%Y-%m-%dT%H:%M:%S.%fZ")
    attempts = []
    stacks = []
    events = {"sqlite3.connect", "socket.connect", "socket.getaddrinfo", "socket.__new__",
              "open", "os.open", "subprocess.Popen", "os.system"}
    def audit(event, args):
        if event in events:
            attempts.append(event)
            frame = sys._getframe(1)
            stack = []
            for _ in range(18):
                if frame is None:
                    break
                stack.append(f"{frame.f_code.co_filename}:{frame.f_lineno}:{frame.f_code.co_name}")
                frame = frame.f_back
            stacks.append(stack)
            raise RuntimeError("pure-core prohibited I/O: " + event)
    sys.addaudithook(audit)
    original_getenv = os.getenv
    def no_getenv(*_args, **_kwargs):
        attempts.append("os.getenv")
        raise RuntimeError("pure-core prohibited environment lookup")
    os.getenv = no_getenv
    class NoEnvironment(dict):
        def _blocked(self, *_args, **_kwargs):
            attempts.append("os.environ")
            raise RuntimeError("pure-core prohibited environment lookup")
        __getitem__ = get = __contains__ = items = keys = values = _blocked
    os.environ = NoEnvironment()
    if variant == "ambient-clock-shift":
        time.time = lambda: 1.0
    elif variant == "ambient-clock-future":
        time.time = lambda: 9999999999.0
    try:
        if variant.startswith("probe-"):
            if variant == "probe-sqlite":
                sqlite3.connect(":memory:")
            elif variant == "probe-network":
                socket.socket()
            elif variant == "probe-filesystem":
                open(input_path, "rb")
            else:
                raise ValueError("unknown probe")
            raise RuntimeError("I/O probe unexpectedly succeeded")
        result = fusion.fuse_classification(inputs)
        value = {"artifact_id": result.artifact_id, "content_sha256": result.content_sha256,
                 "attempted_blocked_events": attempts, "attempt_stacks": stacks,
                 "attempt_count": len(attempts),
                 "ambient_clock_variant": variant}
    except BaseException as exc:
        value = {"error": type(exc).__name__, "detail": str(exc)[:200],
                 "attempted_blocked_events": attempts, "attempt_stacks": stacks,
                 "attempt_count": len(attempts)}
    # stdout uses the already-open console and does not open files.
    print(json.dumps(value, sort_keys=True))
    return 0 if "error" not in value and not attempts else 1


def _guarded_core(repo: Path, run_dir: Path, inputs: Any, expected: Any):
    temporary = run_dir / "pure-core-input.pkl"
    temporary.write_bytes(pickle.dumps(inputs, protocol=4))
    rows = []
    try:
        for variant in ("baseline", "ambient-clock-shift", "ambient-clock-future", "environment-variant"):
            environment = dict(os.environ)
            environment.update(PYTHONDONTWRITEBYTECODE="1", PYTHONPYCACHEPREFIX=str(run_dir / "pycache"))
            cwd = run_dir
            if variant == "environment-variant":
                environment["T05_UNRELATED_CONFIG"] = "deliberately-different"
                environment["TEMP"] = str(run_dir / "different-temp")
                (run_dir / "different-temp").mkdir(exist_ok=True)
                cwd = run_dir / "different-temp"
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--pure-core-child",
                                     str(repo), str(temporary), variant], cwd=cwd, env=environment,
                                    capture_output=True, text=True, timeout=60)
            try:
                payload = json.loads(result.stdout.strip().splitlines()[-1])
            except Exception as exc:
                raise SemanticFailure("PURE_CORE_CHILD_UNREADABLE", result.stderr[:200]) from exc
            rows.append(payload)
            if (result.returncode or payload.get("attempt_count") != 0 or
                    payload.get("artifact_id") != expected.artifact_id or
                    payload.get("content_sha256") != expected.content_sha256):
                raise SemanticFailure("PURE_CORE_IO_OR_DETERMINISM",
                                      variant + ":" + json.dumps(payload, sort_keys=True)[:2000])
    finally:
        temporary.unlink(missing_ok=True)
    return {"pure_core_entry": "fuse_classification(FusionInputs)",
            "pure_core_exit": "ClassificationResult", "blocked_operation_classes": [
                "sqlite", "network", "filesystem", "subprocess", "environment"],
            "runs": rows, "attempt_count": 0, "result": ref(expected)}


def _direct_matrix(repo, run_dir, api, helper, connection, profile, classifier):
    store = ReadOnlyArtifacts(connection, api, helper)
    store.extra[classifier.artifact_id] = classifier
    foundation, knowledge, epoch, start, end, observed, clock = _time_for(api, profile, store, helper)
    ingested = api.validation.format_utc(api.validation.parse_utc(end) + timedelta(minutes=1))
    row, matched_k1_record = _matching_k1_row(api, helper, epoch, observed, ingested, knowledge)
    read = api.snapshot_fixture.FakeRead([row])
    site, mac = epoch["site_id"], helper.MAC
    assembly = _assembly(api, store, read, clock)
    captured = []
    original_fuse = api.assembly.fuse_classification
    def record_fuse(inputs):
        captured.append(inputs)
        return original_fuse(inputs)
    api.assembly.fuse_classification = record_fuse
    try:
        result = assembly.assemble_pre_acceptance_candidate(profile, site, mac, start, end)
    finally:
        api.assembly.fuse_classification = original_fuse
    if not captured or result.execution_context != "PRE_ACCEPTANCE_CANDIDATE" or store.pins:
        raise SemanticFailure("EXACT_P_ASSEMBLY")
    expected_set = [ref(profile)] + [profile.semantic_payload[field] for field in (
        "foundation_runtime_profile", "knowledge_bundle", "classification_policy",
        "evidence_adapter_contract_set", "classifier_artifact_manifest")]
    if _tuple(result) != expected_set:
        raise SemanticFailure("EXACT_P_SET_MISMATCH")
    request = result.classification_request_manifest
    fields = {"evidence_snapshot_content", "source_evaluability", "knowledge_bundle",
              "classification_policy", "evidence_adapter_contract_set",
              "classifier_artifact_manifest", "knowledge_evaluation_at_utc"}
    if (set(request.semantic_payload) != fields or
            any(term.encode() in request.semantic_payload_json for term in (
                PROFILE_ID, "RuntimeProfileAdmissionManifest", "RuntimeProfileActivationRecord",
                "RuntimeProfileValidityRecord", "PRE_ACCEPTANCE_CANDIDATE", "DecisionRecord"))):
        raise SemanticFailure("REQUEST_LINEAGE_CONTAMINATION")
    # A valid but operationally different profile lineage cannot alter this request.
    alternate = _pointer_matrix(api, store, profile, read, site, mac, start, end, clock)
    if alternate["new_request"]["request"] != ref(request):
        raise SemanticFailure("REQUEST_OPERATIONAL_LINEAGE_DEPENDENCE")
    pure_a = original_fuse(captured[0])
    pure_b = original_fuse(captured[0])
    permuted = replace(captured[0], origin_assessments=tuple(reversed(captured[0].origin_assessments)))
    pure_permuted = original_fuse(permuted)
    if pure_a != pure_b or pure_a != pure_permuted or pure_a != result.classification_result:
        raise SemanticFailure("PURE_CORE_NONDETERMINISTIC")
    io_proof = _guarded_core(repo, run_dir, captured[0], pure_a)
    signature = inspect.signature(assembly.assemble_production)
    if set(signature.parameters) != {"site_id", "observed_mac", "window_start_utc", "window_end_utc"}:
        raise SemanticFailure("PRODUCTION_SIGNATURE")
    for name, value in (("candidate_classification_runtime_profile", profile),
                        ("knowledge_evaluation_at_utc", clock)):
        try:
            assembly.assemble_production(site, mac, start, end, **{name: value})
        except TypeError:
            continue
        raise SemanticFailure("CALLER_BACKDATE_ACCEPTED", name)
    earliest = min(api.validation.parse_utc(getattr(knowledge, f"{slot}_provenance")
                   .semantic_payload["retrieved_at_utc"]) for slot in ("k1", "k2b", "k4"))
    negative_clock = api.validation.format_utc(earliest - timedelta(milliseconds=1))
    negative = _assembly(api, store, read, negative_clock)
    try:
        negative.assemble_pre_acceptance_candidate(profile, site, mac, start, end)
    except api.assembly.RequestAssemblyError as exc:
        if exc.reason_code != "negative_knowledge_age":
            raise SemanticFailure("NEGATIVE_AGE_WRONG_REASON", exc.reason_code) from exc
    else:
        raise SemanticFailure("NEGATIVE_AGE_ACCEPTED")
    freshness = _freshness(api, knowledge)
    # K1's exact policy has a bounded expiry; p0f/K2B intentionally does not.
    expired_at = (api.validation.parse_utc(knowledge.k1_provenance.semantic_payload[
        "retrieved_at_utc"]) + timedelta(milliseconds=knowledge.k1_freshness_policy.semantic_payload[
            "stale_max_age_ms"] + 1))
    expired_result = _assembly(api, store, read, api.validation.format_utc(expired_at)).assemble_pre_acceptance_candidate(
        profile, site, mac, start, end)
    if expired_result.classification_result is None:
        raise SemanticFailure("EXPIRED_SOURCE_CRASH")
    dhcp = next(item for item in expired_result.origin_assessments
                if item.semantic_payload["origin_group"] == "dhcp")
    platform = next(item for item in dhcp.semantic_payload["dimension_assessments"]
                    if item["dimension_name"] == "platform_family")
    if (platform["internal_state"] != "no_claim" or
            "knowledge_source_expired" not in platform["explanation_codes"]):
        raise SemanticFailure("EXPIRED_SOURCE_CLAIM_NOT_SUPPRESSED")
    matrix = {key: {"status": "PASS", "trace": {}} for key in CASES}
    matrix["T05-M01"]["trace"] = _result_trace(result)
    matrix["T05-M02"]["trace"] = {"fields": sorted(fields), "operational_lineage_absent": True,
                                    "candidate_and_production_same_semantics_identical": True}
    matrix["T05-M03"]["trace"] = {
        "pin_first_per_request": alternate["pin_first_per_request"],
        "first_store_operation": alternate["first_store_operation"],
        "classification_pin_count_per_request": alternate["classification_pin_count_per_request"],
        "foundation_pointer_read_count": alternate["foundation_pointer_read_count"],
    }
    matrix["T05-M04"]["trace"] = alternate
    matrix["T05-M05"]["trace"] = {"mutable_current_changed_after_pin": True,
                                    "execution_set_old": alternate["old_request"]["execution_set"]}
    matrix["T05-M06"]["trace"] = {"request": ref(request),
                                    "repeated_results": [ref(pure_a), ref(pure_b), ref(pure_permuted)],
                                    "origin_enumeration_reversed": True}
    matrix["T05-M07"]["trace"] = io_proof
    matrix["T05-M08"]["trace"] = {"trusted_knowledge_time": clock,
                                    "ambient_variants": io_proof["runs"][1:3]}
    matrix["T05-M09"]["trace"] = {"production_signature": list(signature.parameters),
                                    "injected_profile_rejected": True, "injected_time_rejected": True}
    matrix["T05-M10"]["trace"] = {"negative_evaluation_at_utc": negative_clock,
                                    "reason_code": "negative_knowledge_age", "request": None, "result": None}
    matrix["T05-M11"]["trace"] = {"policy_matrix": freshness,
                                    "matched_k1_record_id": matched_k1_record,
                                    "expired_result": _result_trace(expired_result),
                                    "origin_assessments": [item.semantic_payload for item in
                                                           expired_result.origin_assessments]}
    matrix["T05-M12"]["trace"] = {"environment_variant": io_proof["runs"][3],
                                    "identical_result": True}
    return matrix, alternate, io_proof, {"policies": freshness,
        "negative_age": matrix["T05-M10"]["trace"],
        "expired_source": matrix["T05-M11"]["trace"]}, [_result_trace(result), _result_trace(expired_result)]


def _formal(api, helper, run_dir, profile, prerequisite, runner_sha, passed):
    identity = {"execution_id": str(uuid.uuid4()), "executor_kind": "TECHLEAD_GATE_TOOL",
                "repository_commit_sha": COMMIT, "repository_tree_sha": TREE,
                "procedure_or_test_suite_id": PROCEDURE,
                "environment_identity": helper._environment_identity(),
                "execution_artifact_sha256": runner_sha}
    evidence = [{"evidence_label": name.rsplit(".", 1)[0], "file_sha256": sha(run_dir / name),
                 "media_type": "text/plain" if name.endswith((".log", ".txt")) else "application/json",
                 "path_or_reference": name} for name in RETAINED]
    inputs = sorted([ref(prerequisite), ref(profile)], key=lambda row: row["artifact_id"])
    proof = None
    if passed:
        proof = api.gate_proof.make_gate_proof_artifact({
            "proof_kind": PROOF_KIND, "source_gate_id": GATE_ID,
            "candidate_repository_commit_sha": COMMIT, "candidate_repository_tree_sha": TREE,
            "input_artifact_refs": inputs, "procedure_or_test_suite_id": PROCEDURE,
            "proof_execution_identity": identity,
            "canonical_result_summary": f"profile={PROFILE_ID};matrix=12/12 PASS;pointer_switch=PASS;pure_core_io=PASS;determinism=PASS;freshness=PASS",
            "retained_evidence_refs": evidence})
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
        "decision_record_refs": []})
    if proof is not None:
        helper._write_and_roundtrip(run_dir / "t05-gate-proof-artifact.json", proof,
                                    api.gate_proof.make_gate_proof_artifact,
                                    api.artifact.canonical_artifact_json)
    helper._write_and_roundtrip(run_dir / "t05-gate-result-manifest.json", result,
                                api.gate_result.make_gate_result_manifest,
                                api.artifact.canonical_artifact_json)
    return proof, result


def _blocked(run_dir, code):
    if run_dir is not None:
        for name in ("t05-gate-result-manifest.json", "t05-gate-proof-artifact.json"):
            (run_dir / name).unlink(missing_ok=True)
        (run_dir / "t05-summary.txt").write_text(f"GATE_EXECUTION_STATUS={code}\n", encoding="utf-8")
    print(f"GATE_EXECUTION_STATUS={code}")
    return 2


def run_gate(repo: Path, foundation_db: Path, t06a_run_dir: Path, output_dir: Path) -> int:
    run_dir = None
    connection = None
    runner = Path(__file__).resolve()
    runner_sha = sha(runner)
    try:
        helper, t06a = helpers()
        repo = repo.resolve(strict=True)
        foundation_db = foundation_db.resolve(strict=True)
        t06a_run_dir = t06a_run_dir.resolve(strict=True)
        output_dir = output_dir.resolve()
        if (output_dir.is_relative_to(repo) or output_dir.is_relative_to(t06a_run_dir) or
                output_dir == foundation_db.parent or output_dir == runner.parent or
                (output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())))):
            raise Blocked("BLOCKED_OUTPUT_DIR")
        output_dir.mkdir(parents=True, exist_ok=True)
        run_dir = output_dir / str(uuid.uuid4())
        run_dir.mkdir(exist_ok=False)
        helper.verify_repository(repo)
        before_repo = helper.repository_filesystem_fingerprint(repo)
        before_db = sha(foundation_db)
        sys.path.insert(0, str(repo))
        api = api_for(repo, t06a)
        profile, _prior_proof, prerequisite = verify_t06a(t06a_run_dir, api)
        connection = helper.open_foundation_read_only(foundation_db)
        foundation = helper.verify_foundation(connection, api)
        if profile.semantic_payload["foundation_runtime_profile"] != ref(foundation.profile):
            raise Blocked("BLOCKED_FOUNDATION_LINEAGE", "P foundation ref")
        classifier = canonical_content(T06_MANIFEST_PATH, api,
            lambda payload: api.artifact.make_artifact_content("ClassifierArtifactManifest", payload),
            profile.semantic_payload["classifier_artifact_manifest"]["artifact_id"])
        pytest_status, command = _run_pytest(repo, run_dir)
        matrix = {key: {"status": "NOT_RUN", "trace": {}} for key in CASES}
        pointer, io_proof, freshness, results = {}, {}, {}, []
        failure = None
        failure_detail = None
        if pytest_status != 0:
            failure = "EXISTING_REQUEST_SUITE_FAILED"
        else:
            try:
                matrix, pointer, io_proof, freshness, results = _direct_matrix(
                    repo, run_dir, api, helper, connection, profile, classifier)
            except Exception as exc:
                failure = exc.code if isinstance(exc, SemanticFailure) else type(exc).__name__
                failure_detail = str(exc)[:400]
        write_json(run_dir / "t05-direct-matrix.json", {"cases": matrix,
                   "all_pass": len(matrix) == 12 and all(row["status"] == "PASS" for row in matrix.values()),
                   "failure_code": failure, "failure_detail": failure_detail})
        write_json(run_dir / "t05-pointer-switch-trace.json", pointer)
        write_json(run_dir / "t05-pure-core-io-proof.json", io_proof)
        write_json(run_dir / "t05-freshness-report.json", freshness)
        write_json(run_dir / "t05-execution-evidence.json", {
            "candidate_commit": COMMIT, "candidate_tree": TREE, "runner_sha256": runner_sha,
            "t01_helper_sha256": T01_SHA, "t06a_runner_sha256": T06A_SHA,
            "t06a_gate_result": ref(prerequisite), "t06a_gate_proof": ref(_prior_proof),
            "exact_profile": ref(profile), "pytest_command": command, "pytest_exit_status": pytest_status,
            "matrix_statuses": {key: row["status"] for key, row in matrix.items()},
            "exact_p_request_result_identities": results,
            "repository_immutability": "PASS", "foundation_db_byte_identity": "PASS",
            "failure_code": failure})
        (run_dir / "t05-summary.txt").write_text(
            f"GATE_EXECUTION_STATUS={'PASS' if failure is None else 'FAIL'}\n"
            f"PROFILE={PROFILE_ID}\nFAILURE_CODE={failure or 'NONE'}\n", encoding="utf-8")
        if sha(runner) != runner_sha or sha(T01_PATH) != T01_SHA or sha(T06A_PATH) != T06A_SHA:
            raise Blocked("BLOCKED_RUNNER_CHANGED")
        helper._require_repository_unchanged(repo, before_repo)
        if sha(foundation_db) != before_db:
            raise Blocked("BLOCKED_FOUNDATION_MUTATED")
        _formal(api, helper, run_dir, profile, prerequisite, runner_sha, failure is None)
        helper._require_repository_unchanged(repo, before_repo)
        if sha(foundation_db) != before_db or sha(runner) != runner_sha:
            raise Blocked("BLOCKED_EXECUTION_MUTATED")
        print(f"GATE_EXECUTION_STATUS={'PASS' if failure is None else 'FAIL'}")
        return 0 if failure is None else 1
    except Blocked as exc:
        return _blocked(run_dir, exc.code)
    except Exception as exc:
        if "helper" in locals() and isinstance(exc, helper.Blocked):
            return _blocked(run_dir, exc.status)
        return _blocked(run_dir, "BLOCKED_EXECUTION_BASIS_" + type(exc).__name__)
    finally:
        if connection is not None:
            connection.rollback()
            connection.close()


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "--pure-core-child":
        return _guarded_core_child(Path(argv[1]), Path(argv[2]), argv[3])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--foundation-control-db", type=Path, required=True)
    parser.add_argument("--t06a-run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    return run_gate(args.repo, args.foundation_control_db, args.t06a_run_dir, args.output_dir)


if __name__ == "__main__":
    raise SystemExit(main())
