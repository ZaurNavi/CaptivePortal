#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from contextlib import closing
from pathlib import Path
import sys

GATE = Path(r"C:\CaptivPortal-Lab\tools\task04-t09-phase-b-a1-r2-20261002.py")
EXPECTED_GATE_SHA = "fceb54dc653978f8aaaa9720ab9441c844748c971ff40e5920046563da1df1c8"
REPO = Path(r"C:\CaptivPortal-Lab\coder-task04-t09-utility-repair-a1")
FOUNDATION_COPY = Path(
    r"C:\CaptivPortal-Lab\official-runs\task04\t09"
    r"\phase-b-20261002T074414Z-T09-A1-R2-01"
    r"\worker-1\foundation-snapshot.sqlite3"
)
EXPECTED_COMMIT = "8a39459be3ce7ed40e325736034245f0025cf249"
EXPECTED_TREE = "e2521f27c9f91978e381bce202ab3e3c83aa6dad"
EXPECTED_PROFILE = (
    "ClassificationRuntimeProfile:v1:sha256:"
    "1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c"
)


def sha(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_gate():
    if sha(GATE) != EXPECTED_GATE_SHA:
        raise RuntimeError("GATE_SHA_MISMATCH")
    spec = importlib.util.spec_from_file_location("t09_diag_gate", GATE)
    if spec is None or spec.loader is None:
        raise RuntimeError("GATE_IMPORT_SPEC")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def print_rows(label, rows):
    print(f"\n=== {label} ===")
    print(f"ROW_COUNT={len(rows)}")
    for row in rows:
        print(
            f"{row['check_id']}|STATUS={row['status']}|"
            f"FAILURE_CODE={row.get('failure_code')}|"
            f"DETAIL={row.get('failure_detail')}"
        )
    print(f"ALL_PASS={all(r['status'] == 'PASS' for r in rows)}")


def main():
    gate = load_gate()
    h, t01, t06a = gate.helpers()

    import subprocess
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

    if not FOUNDATION_COPY.is_file():
        raise RuntimeError("FOUNDATION_COPY_MISSING")

    before_sha = sha(FOUNDATION_COPY)
    print(f"FOUNDATION_COPY_SHA256_BEFORE={before_sha}")

    api = t06a.load_api(REPO)
    for key, name in {
        "assembly": "request_assembly",
        "control": "control_plane_store",
        "retention": "classification_retention_policy",
    }.items():
        setattr(api, key, h.candidate(REPO, "app.device_fingerprint." + name))

    profile, proof, result = h.verify_t06a(gate.T06A_RUN, api)
    if profile.artifact_id != EXPECTED_PROFILE:
        raise RuntimeError("PROFILE_ID_MISMATCH")

    with closing(t01.open_foundation_read_only(FOUNDATION_COPY)) as conn:
        lineage = t01.verify_foundation(conn, api)
        classifier = h.canonical_content(
            h.T06_MANIFEST_PATH,
            api,
            lambda p: api.artifact.make_artifact_content(
                "ClassifierArtifactManifest", p
            ),
            profile.semantic_payload["classifier_artifact_manifest"]["artifact_id"],
        )

        control = api.control.DeviceFingerprintControlPlaneStore(FOUNDATION_COPY)
        overlay, overlay_sources = t06a.load_a1_overlay(api)
        immutable = h.ImmutableOverlay(control, classifier, overlay)

        contents = {
            key: immutable.load_artifact(
                value["artifact_id"], value["content_sha256"]
            )
            for key, value in profile.semantic_payload.items()
            if isinstance(value, dict)
        }

        # Reproduce current worker state: load_a1_overlay() called, but module globals empty.
        t06a._A1_OVERLAY.clear()
        t06a._A1_OVERLAY_SOURCES.clear()
        rows_before = t06a.compatibility(conn, api, contents, lineage)
        print_rows("COMPATIBILITY_WITH_EMPTY_T06A_GLOBAL_OVERLAY", rows_before)

        # Reproduce official T-06A A1 initialization.
        t06a._A1_OVERLAY.update(overlay)
        t06a._A1_OVERLAY_SOURCES.update(overlay_sources)
        rows_after = t06a.compatibility(conn, api, contents, lineage)
        print_rows("COMPATIBILITY_WITH_OFFICIAL_A1_GLOBAL_OVERLAY", rows_after)

    after_sha = sha(FOUNDATION_COPY)
    print(f"\nFOUNDATION_COPY_SHA256_AFTER={after_sha}")
    print(f"FOUNDATION_COPY_BYTE_IDENTITY={'PASS' if before_sha == after_sha else 'FAIL'}")
    print(f"A1_OVERLAY_ARTIFACT_COUNT={len(overlay)}")
    print("REQUEST_ASSEMBLY_EXECUTED=NO")
    print("CLASSIFICATION_EXECUTED=NO")
    print("T09_FORMAL_PHASE_B_RERUN=NO")
    print("PRODUCTION_ACTION=NO")
    print("DIAGNOSTIC_STATUS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
