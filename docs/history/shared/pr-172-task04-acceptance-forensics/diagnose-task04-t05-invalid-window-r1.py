#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import shutil
import sys
import traceback

ROOT = pathlib.Path(r"C:\CaptivPortal-Lab")
REPO = ROOT / "coder-task04-t09-utility-repair-a1"
FOUNDATION_DB = ROOT / "foundation-control-plane" / "device-fingerprint-control-plane.sqlite3"

T05_PATH = ROOT / "tools" / "task04-t05-gate-a1-20261001.py"
EXPECTED_T05_SHA = "50563b508b4876c00e1b67e62f06cfa9bac7573454dae72e8ed7b738b6e3bf6e"

T06A_RUN_DIR = (
    ROOT / "official-runs" / "task04" / "t06a"
    / "official-run-20261001T124442Z-T06A-A1-01"
    / "fe25e9fc-7b03-485b-ae68-0f806fd96af6"
)

DIAG_DIR = ROOT / "tmp" / "task04-t05-a1-invalid-window-diagnostic-r1"

EXPECTED_COMMIT = "8a39459be3ce7ed40e325736034245f0025cf249"
EXPECTED_TREE = "e2521f27c9f91978e381bce202ab3e3c83aa6dad"


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(path: pathlib.Path):
    spec = importlib.util.spec_from_file_location("task04_t05_a1_diag_source", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("T05_IMPORT_SPEC_FAILURE")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def git(*args: str) -> str:
    import subprocess
    cp = subprocess.run(
        ["git", "-C", str(REPO), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if cp.returncode != 0:
        raise RuntimeError("GIT_FAILURE:" + " ".join(args) + ":" + cp.stderr.strip())
    return cp.stdout.strip()


if not T05_PATH.is_file():
    raise SystemExit("T05_DIAG_SOURCE_MISSING=" + str(T05_PATH))

actual_sha = sha(T05_PATH)
print("T05_DIAG_SOURCE_SHA256=" + actual_sha)
if actual_sha != EXPECTED_T05_SHA:
    raise SystemExit("T05_DIAG_SOURCE_SHA256_MISMATCH")

commit = git("rev-parse", "HEAD")
tree = git("show", "-s", "--format=%T", "HEAD")
status = git("status", "--porcelain")

print("CANDIDATE_COMMIT=" + commit)
print("CANDIDATE_TREE=" + tree)
print("CANDIDATE_WORKTREE_CLEAN=" + ("YES" if not status else "NO"))

if commit != EXPECTED_COMMIT or tree != EXPECTED_TREE or status:
    raise SystemExit("T05_DIAG_CANDIDATE_IDENTITY_FAILURE")

if not FOUNDATION_DB.is_file():
    raise SystemExit("T05_DIAG_FOUNDATION_DB_MISSING")
if not T06A_RUN_DIR.is_dir():
    raise SystemExit("T05_DIAG_T06A_RUN_DIR_MISSING")

if DIAG_DIR.exists():
    shutil.rmtree(DIAG_DIR)
DIAG_DIR.mkdir(parents=True)

t05 = load_module(T05_PATH)
helper, t06a = t05.helpers()

sys.path.insert(0, str(REPO))
api = t05.api_for(REPO, t06a)

overlay, overlay_sources = t06a.load_a1_overlay(api)
profile, prior_proof, prerequisite = t05.verify_t06a(T06A_RUN_DIR, api)

connection = helper.open_foundation_read_only(FOUNDATION_DB)

try:
    foundation = helper.verify_foundation(connection, api)
    classifier = t05.canonical_content(
        t05.T06_MANIFEST_PATH,
        api,
        lambda payload: api.artifact.make_artifact_content(
            "ClassifierArtifactManifest", payload
        ),
        profile.semantic_payload["classifier_artifact_manifest"]["artifact_id"],
    )

    # Resolve the exact fixture basis before assembly.
    store = t05.ReadOnlyArtifacts(connection, api, helper)
    store.extra.update(overlay)
    store.extra[classifier.artifact_id] = classifier

    foundation2, knowledge, epoch, start, end, observed, clock = t05._time_for(
        api, profile, store, helper
    )

    retrieved = {
        slot: getattr(knowledge, f"{slot}_provenance").semantic_payload["retrieved_at_utc"]
        for slot in ("k1", "k2b", "k4")
    }

    print("")
    print("=== T05 FIXTURE TIME BASIS ===")
    print("FOUNDATION_PROFILE_ID=" + foundation2.artifact_id)
    print(
        "FOUNDATION_VALID_FROM="
        + foundation2.semantic_payload["classification_foundation_valid_from_utc"]
    )
    print("BINDING_EPOCH_ID=" + epoch["binding_epoch_id"])
    print("BINDING_EFFECTIVE_FROM=" + epoch["effective_from_utc"])
    print("BINDING_EFFECTIVE_TO=" + str(epoch["effective_to_utc"]))
    print("WINDOW_START=" + start)
    print("WINDOW_END=" + end)
    print("OBSERVED_AT=" + observed)
    print("REQUEST_ASSEMBLY_CLOCK=" + clock)
    for slot in ("k1", "k2b", "k4"):
        print(slot.upper() + "_RETRIEVED_AT=" + retrieved[slot])

    parsed_start = api.validation.parse_utc(start)
    parsed_end = api.validation.parse_utc(end)
    parsed_valid = api.validation.parse_utc(
        foundation2.semantic_payload["classification_foundation_valid_from_utc"]
    )
    parsed_clock = api.validation.parse_utc(clock)

    print("CHECK_START_LT_END=" + str(parsed_start < parsed_end).upper())
    print("CHECK_START_GTE_VALID_FROM=" + str(parsed_start >= parsed_valid).upper())
    print("CHECK_END_LTE_INITIAL_CLOCK=" + str(parsed_end <= parsed_clock).upper())

    # Instrument every real snapshot build used by _direct_matrix.
    service_cls = api.snapshot.DeviceFingerprintSnapshotService
    original_build = service_cls.build
    call_counter = {"n": 0}

    def traced_build(self, site_id, observed_mac, window_start_utc, window_end_utc):
        call_counter["n"] += 1
        n = call_counter["n"]
        captured_at = self._utc_clock()
        try:
            valid_from = self._profile.semantic_payload[
                "classification_foundation_valid_from_utc"
            ]
        except Exception:
            valid_from = "<UNAVAILABLE>"

        print("")
        print("=== SNAPSHOT BUILD CALL " + str(n) + " ===")
        print("SNAPSHOT_SITE_ID=" + str(site_id))
        print("SNAPSHOT_MAC=" + str(observed_mac))
        print("SNAPSHOT_WINDOW_START=" + str(window_start_utc))
        print("SNAPSHOT_WINDOW_END=" + str(window_end_utc))
        print("SNAPSHOT_CAPTURED_AT=" + str(captured_at))
        print("SNAPSHOT_FOUNDATION_VALID_FROM=" + str(valid_from))

        try:
            s = api.validation.parse_utc(window_start_utc)
            e = api.validation.parse_utc(window_end_utc)
            c = api.validation.parse_utc(captured_at)
            v = api.validation.parse_utc(valid_from)
            print("COND_START_LT_END=" + str(s < e).upper())
            print("COND_START_GTE_VALID_FROM=" + str(s >= v).upper())
            print("COND_END_LTE_CAPTURED_AT=" + str(e <= c).upper())
        except Exception as exc:
            print(
                "SNAPSHOT_DIAG_PARSE_FAILURE="
                + type(exc).__name__
                + ":"
                + str(exc)
            )

        try:
            result = original_build(
                self, site_id, observed_mac, window_start_utc, window_end_utc
            )
            print("SNAPSHOT_BUILD_RESULT=PASS")
            return result
        except Exception as exc:
            reason = getattr(exc, "reason_code", None)
            print("SNAPSHOT_BUILD_RESULT=EXCEPTION")
            print("SNAPSHOT_EXCEPTION_TYPE=" + type(exc).__name__)
            print("SNAPSHOT_EXCEPTION_REASON_CODE=" + str(reason))
            print("SNAPSHOT_EXCEPTION_TEXT=" + str(exc))
            raise

    service_cls.build = traced_build

    print("")
    print("=== DIRECT MATRIX REPLAY ===")
    try:
        matrix, pointer, io_proof, freshness, results = t05._direct_matrix(
            REPO, DIAG_DIR, api, helper, connection, profile, classifier
        )
    except Exception as exc:
        print("")
        print("T05_DIAG_DIRECT_MATRIX_STATUS=EXCEPTION")
        print("T05_DIAG_EXCEPTION_TYPE=" + type(exc).__name__)
        print("T05_DIAG_EXCEPTION_CODE=" + str(getattr(exc, "code", None)))
        print("T05_DIAG_EXCEPTION_REASON_CODE=" + str(getattr(exc, "reason_code", None)))
        print("T05_DIAG_EXCEPTION_TEXT=" + str(exc))
        print("T05_DIAG_SNAPSHOT_BUILD_CALLS=" + str(call_counter["n"]))
        print("T05_DIAG_TRACEBACK_BEGIN")
        traceback.print_exc()
        print("T05_DIAG_TRACEBACK_END")
    else:
        print("T05_DIAG_DIRECT_MATRIX_STATUS=PASS")
        print("T05_DIAG_SNAPSHOT_BUILD_CALLS=" + str(call_counter["n"]))
        print("T05_DIAG_MATRIX_ALL_PASS=" + str(
            all(row.get("status") == "PASS" for row in matrix.values())
        ).upper())
    finally:
        service_cls.build = original_build

finally:
    connection.rollback()
    connection.close()

print("")
print("T05_DIAGNOSTIC_REPLAY_COMPLETE=YES")
print("T05_FORMAL_GATE_RERUN=NO")
print("PRODUCTION_ACTION=NO")
