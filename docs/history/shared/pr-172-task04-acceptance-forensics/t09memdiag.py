#!/usr/bin/env python3
from __future__ import annotations

from contextlib import closing
import ctypes
from ctypes import wintypes
import importlib.util
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

GATE = Path(r"C:\CaptivPortal-Lab\tools\task04-t09-phase-b-a1-r3-20261002.py")
EXPECTED_GATE_SHA = "f3ceab4ed4d83bbc5e75e951a320eabd5832992999ba0aa9b3d3f431fcc93ae6"
REPO = Path(r"C:\CaptivPortal-Lab\coder-task04-t09-utility-repair-a1")
WORKER = Path(
    r"C:\CaptivPortal-Lab\official-runs\task04\t09"
    r"\phase-b-20261002T081546Z-T09-A1-R3-01\worker-1"
)
FOUNDATION = WORKER / "foundation-snapshot.sqlite3"
TASK01 = WORKER / "task01-snapshot.sqlite3"
PHASE_A_LOCK = Path(
    r"C:\CaptivPortal-Lab\official-runs\task04\t09"
    r"\phase-a-r2-upgrade-20261002T071712Z-T09-A1-01\phase-a-lock.json"
)
EXPECTED_PHASE_A_LOCK_SHA = "1142010057ddaa8564fe076160f35595e84ae51c5dae6d798d5e8bbb839c6ac1"

EXPECTED_COMMIT = "8a39459be3ce7ed40e325736034245f0025cf249"
EXPECTED_TREE = "e2521f27c9f91978e381bce202ab3e3c83aa6dad"


def sha(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_gate():
    if sha(GATE) != EXPECTED_GATE_SHA:
        raise RuntimeError("GATE_SHA_MISMATCH")
    spec = importlib.util.spec_from_file_location("t09_memdiag_gate", GATE)
    if spec is None or spec.loader is None:
        raise RuntimeError("GATE_IMPORT_SPEC")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class Counters(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


def process_memory():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = (
        wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD
    )
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    c = Counters()
    c.cb = ctypes.sizeof(c)
    if not psapi.GetProcessMemoryInfo(
        kernel.GetCurrentProcess(), ctypes.byref(c), c.cb
    ):
        raise RuntimeError("PROCESS_MEMORY_MEASUREMENT_FAILED")
    return {
        "working_set": int(c.WorkingSetSize),
        "private_usage": int(c.PrivateUsage),
        "peak_working_set": int(c.PeakWorkingSetSize),
        "peak_pagefile": int(c.PeakPagefileUsage),
        "guard_value": max(int(c.WorkingSetSize), int(c.PrivateUsage)),
    }


def mib(value: int) -> str:
    return f"{value / (1024 * 1024):.3f}"


def show_memory(label: str):
    m = process_memory()
    print(
        f"{label}|WORKING_SET={m['working_set']}({mib(m['working_set'])}MiB)|"
        f"PRIVATE={m['private_usage']}({mib(m['private_usage'])}MiB)|"
        f"GUARD_VALUE={m['guard_value']}({mib(m['guard_value'])}MiB)"
    )
    return m


def main():
    if sys.platform != "win32":
        raise RuntimeError("WINDOWS_REQUIRED")

    gate = load_gate()

    commit = subprocess.check_output(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True
    ).strip()
    tree = subprocess.check_output(
        ["git", "-C", str(REPO), "show", "-s", "--format=%T", "HEAD"], text=True
    ).strip()
    status = subprocess.check_output(
        ["git", "-C", str(REPO), "status", "--porcelain"], text=True
    )
    print(f"CANDIDATE_COMMIT={commit}")
    print(f"CANDIDATE_TREE={tree}")
    print(f"CANDIDATE_WORKTREE_CLEAN={'YES' if not status else 'NO'}")
    if commit != EXPECTED_COMMIT or tree != EXPECTED_TREE or status:
        raise RuntimeError("CANDIDATE_IDENTITY_MISMATCH")

    for p in (FOUNDATION, TASK01, PHASE_A_LOCK):
        if not p.is_file():
            raise RuntimeError(f"REQUIRED_INPUT_MISSING:{p}")
    if sha(PHASE_A_LOCK) != EXPECTED_PHASE_A_LOCK_SHA:
        raise RuntimeError("PHASE_A_LOCK_SHA_MISMATCH")

    foundation_before = sha(FOUNDATION)
    task01_before = sha(TASK01)
    show_memory("MEMORY_AFTER_GATE_IMPORT")

    h, t01, t06a = gate.helpers()
    minimal = gate.minimal_api(REPO, h)
    api = t06a.load_api(REPO)
    for key, name in {
        "assembly": "request_assembly",
        "control": "control_plane_store",
        "retention": "classification_retention_policy",
    }.items():
        setattr(api, key, h.candidate(REPO, "app.device_fingerprint." + name))
    api.product_policy = minimal.product_policy
    show_memory("MEMORY_AFTER_FULL_API_IMPORT")

    profile, proof, result = h.verify_t06a(gate.T06A_RUN, api)

    with closing(t01.open_foundation_read_only(FOUNDATION)) as conn:
        lineage = t01.verify_foundation(conn, api)
        foundation = t01._resolve_artifact(
            conn, api, profile.semantic_payload["foundation_runtime_profile"]
        )
        policy = t01._resolve_artifact(
            conn, api, lineage.manifest.semantic_payload["product_validation_policy"]
        )
        retention = h.resolve_retention(conn, api, t01, lineage)

    control = api.control.DeviceFingerprintControlPlaneStore(FOUNDATION)
    exec_ref = foundation.semantic_payload["snapshot_execution_policy"]
    execution_policy = control.load_artifact(
        exec_ref["artifact_id"], exec_ref["content_sha256"]
    )
    execution_payload = execution_policy.semantic_payload
    print(f"SNAPSHOT_EXECUTION_POLICY_ID={execution_policy.artifact_id}")
    print("SNAPSHOT_EXECUTION_POLICY_PAYLOAD_BEGIN")
    for key in sorted(execution_payload):
        print(f"{key}={execution_payload[key]}")
    print("SNAPSHOT_EXECUTION_POLICY_PAYLOAD_END")

    limit = execution_payload["process_memory_guard_bytes"]
    print(f"PROCESS_MEMORY_GUARD_BYTES={limit}")
    print(f"PROCESS_MEMORY_GUARD_MIB={mib(limit)}")

    classifier = h.canonical_content(
        h.T06_MANIFEST_PATH,
        api,
        lambda p: api.artifact.make_artifact_content("ClassifierArtifactManifest", p),
        profile.semantic_payload["classifier_artifact_manifest"]["artifact_id"],
    )

    t06a._A1_OVERLAY.clear()
    t06a._A1_OVERLAY_SOURCES.clear()
    a1_overlay, a1_overlay_sources = t06a.load_a1_overlay(api)
    t06a._A1_OVERLAY.update(a1_overlay)
    t06a._A1_OVERLAY_SOURCES.update(a1_overlay_sources)

    overlay = h.ImmutableOverlay(control, classifier, a1_overlay)
    contents = {
        key: overlay.load_artifact(value["artifact_id"], value["content_sha256"])
        for key, value in profile.semantic_payload.items()
        if isinstance(value, dict)
    }

    with closing(t01.open_foundation_read_only(FOUNDATION)) as conn:
        compatibility = t06a.compatibility(conn, api, contents, lineage)
    print(
        "COMPATIBILITY_9_OF_9="
        + ("YES" if len(compatibility) == 9 and all(r["status"] == "PASS" for r in compatibility) else "NO")
    )
    show_memory("MEMORY_AFTER_COMPATIBILITY")

    lock, truths = gate.checked_phase_a(
        SimpleNamespace(
            api=api,
            profile=profile,
            foundation=foundation,
            policy=policy,
            valid_from=foundation.semantic_payload["classification_foundation_valid_from_utc"],
        ),
        SimpleNamespace(
            phase_a_lock=PHASE_A_LOCK,
            phase_a_lock_sha256=EXPECTED_PHASE_A_LOCK_SHA,
        ),
    )
    gt = truths[0]

    calls = []

    def diagnostic_guard(supplied_limit):
        m = process_memory()
        passed = m["guard_value"] <= supplied_limit
        calls.append((supplied_limit, m, passed))
        print(
            f"MEMORY_GUARD_CALL={len(calls)}|LIMIT={supplied_limit}({mib(supplied_limit)}MiB)|"
            f"WORKING_SET={m['working_set']}({mib(m['working_set'])}MiB)|"
            f"PRIVATE={m['private_usage']}({mib(m['private_usage'])}MiB)|"
            f"GUARD_VALUE={m['guard_value']}({mib(m['guard_value'])}MiB)|"
            f"PASS={'YES' if passed else 'NO'}|"
            f"OVER_BY_BYTES={max(0, m['guard_value'] - supplied_limit)}"
        )
        return passed

    def compatible(p, f, bundle, _knowledge, cp, adapters, manifest):
        return (
            p == profile
            and f == foundation
            and bundle == contents["knowledge_bundle"]
            and cp == contents["classification_policy"]
            and adapters == contents["evidence_adapter_contract_set"]
            and manifest == classifier
        )

    reader = api.read.DeviceFingerprintReadService(str(TASK01), retention_days=30)
    service = api.assembly.DeviceFingerprintRequestAssembly(
        control_plane_store=overlay,
        read_service=reader,
        compatibility_hook=compatible,
        utc_clock=gate.now,
        process_memory_guard=diagnostic_guard,
    )
    show_memory("MEMORY_BEFORE_ASSEMBLE_DIAGNOSTIC")

    p = gt.semantic_payload
    try:
        service.assemble_pre_acceptance_candidate(
            profile,
            p["site_id"],
            p["observed_mac"],
            p["window_start_utc"],
            p["window_end_utc"],
        )
        print("ASSEMBLE_DIAGNOSTIC_UNEXPECTEDLY_SUCCEEDED=YES")
    except Exception as exc:
        print(f"ASSEMBLE_DIAGNOSTIC_EXCEPTION_TYPE={type(exc).__name__}")
        print(f"ASSEMBLE_DIAGNOSTIC_REASON_CODE={getattr(exc, 'reason_code', None)}")
        print(f"ASSEMBLE_DIAGNOSTIC_TEXT={exc}")

    print(f"MEMORY_GUARD_CALL_COUNT={len(calls)}")
    print(f"FOUNDATION_SHA_UNCHANGED={'YES' if sha(FOUNDATION) == foundation_before else 'NO'}")
    print(f"TASK01_SHA_UNCHANGED={'YES' if sha(TASK01) == task01_before else 'NO'}")
    print("CLASSIFICATION_RESULT_PERSISTED=NO")
    print("T09_FORMAL_PHASE_B_RERUN=NO")
    print("PRODUCTION_ACTION=NO")
    print("DIAGNOSTIC_STATUS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
