from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

LAB = Path(r"C:\CaptivPortal-Lab")
LIVE_DB = LAB / "foundation-control-plane" / "device-fingerprint-control-plane.sqlite3"
R5_TOOL = LAB / "tools" / "task04-taccept-final-a1-r5-20261003.py"
R5_TOOL_SHA = "f6e9a99f791ee2c2ce724fc622caf8b59d557a5ca86c5f93178e8a51857e4e2a"
R5_RUN = LAB / "official-runs" / "task04" / "taccept" / "official-run-20261003T065247Z-TACCEPT-A1-R5-01"

PROFILE_ID = "ClassificationRuntimeProfile:v1:sha256:1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c"

FILES = {
    "ACCEPTANCE": R5_RUN / "task04-acceptance-manifest.json",
    "RPM": R5_RUN / "classification-runtime-profile-admission-manifest.json",
    "FINAL_GATE": R5_RUN / "taccept-gate-result-manifest.json",
    "OWNER_DECISION": R5_RUN / "owner-decision.json",
}

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("taccept_r5_exact", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("R5_IMPORT_SPEC_FAILED")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod

def load_doc(api, path: Path):
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    content = api["make_artifact_content"](raw["artifact_type"], raw["semantic_payload"])
    if content.artifact_id != raw["artifact_id"] or content.content_sha256 != raw["content_sha256"]:
        raise RuntimeError(f"DOCUMENT_IDENTITY_MISMATCH:{path.name}")
    return content

def db_has(conn, artifact_id: str, digest: str) -> bool:
    row = conn.execute(
        "SELECT content_sha256 FROM artifacts WHERE artifact_id=?", (artifact_id,)
    ).fetchone()
    return row is not None and row[0] == digest

def reason(exc: BaseException) -> str:
    return getattr(exc, "reason_code", str(exc) or exc.__class__.__name__)

def print_ref_state(conn, label, refs):
    missing = []
    for ref in refs:
        if not db_has(conn, ref.artifact_id, ref.content_sha256):
            missing.append(f"{ref.artifact_id}|SHA={ref.content_sha256}")
    print(f"{label}_REF_COUNT={len(refs)}")
    print(f"{label}_MISSING_REF_COUNT={len(missing)}")
    for item in missing[:12]:
        print(f"{label}_MISSING_REF={item}")
    if len(missing) > 12:
        print(f"{label}_MISSING_REF_TRUNCATED={len(missing)-12}")

def trace_closure(api, store, conn, root):
    runtime_refs = api["runtime_refs"]
    seen = set()
    stack = [(root, "<ROOT>")]
    while stack:
        content, parent = stack.pop()
        if content.artifact_id in seen:
            continue
        seen.add(content.artifact_id)

        edges = conn.execute(
            "SELECT dependency_id,dependency_digest FROM artifact_dependencies "
            "WHERE owner_id=? ORDER BY dependency_id",
            (content.artifact_id,),
        ).fetchall()
        actual = tuple(api["ArtifactRef"](row[0], row[1]) for row in edges)
        declared = runtime_refs(content)

        if content.artifact_type in (
            "FoundationRuntimeProfile",
            "ClassificationRuntimeProfile",
            "RuntimeProfileAdmissionManifest",
        ):
            if actual != declared:
                print(f"CLOSURE_DIAG_STATUS=RUNTIME_EDGE_SET_MISMATCH")
                print(f"CLOSURE_DIAG_OWNER={content.artifact_id}")
                print(f"CLOSURE_DIAG_OWNER_TYPE={content.artifact_type}")
                print(f"CLOSURE_DIAG_DECLARED_COUNT={len(declared)}")
                print(f"CLOSURE_DIAG_ACTUAL_COUNT={len(actual)}")
                dset = {(x.artifact_id, x.content_sha256) for x in declared}
                aset = {(x.artifact_id, x.content_sha256) for x in actual}
                for aid, dig in sorted(dset - aset):
                    print(f"CLOSURE_DIAG_MISSING_EDGE={aid}|SHA={dig}")
                for aid, dig in sorted(aset - dset):
                    print(f"CLOSURE_DIAG_EXTRA_EDGE={aid}|SHA={dig}")
                return False

        for ref in actual:
            row = conn.execute(
                "SELECT artifact_type,content_sha256,semantic_payload_json,artifact_id "
                "FROM artifacts WHERE artifact_id=?",
                (ref.artifact_id,),
            ).fetchone()
            if row is None:
                print("CLOSURE_DIAG_STATUS=TARGET_ROW_MISSING")
                print(f"CLOSURE_DIAG_OWNER={content.artifact_id}")
                print(f"CLOSURE_DIAG_TARGET={ref.artifact_id}")
                return False
            if row["content_sha256"] != ref.content_sha256:
                print("CLOSURE_DIAG_STATUS=TARGET_DIGEST_MISMATCH")
                print(f"CLOSURE_DIAG_OWNER={content.artifact_id}")
                print(f"CLOSURE_DIAG_TARGET={ref.artifact_id}")
                print(f"CLOSURE_DIAG_EDGE_SHA={ref.content_sha256}")
                print(f"CLOSURE_DIAG_ROW_SHA={row['content_sha256']}")
                return False
            try:
                child = store._load(conn, ref.artifact_id, ref.content_sha256)
            except Exception as exc:
                print("CLOSURE_DIAG_STATUS=TARGET_LOAD_FAILED")
                print(f"CLOSURE_DIAG_OWNER={content.artifact_id}")
                print(f"CLOSURE_DIAG_TARGET={ref.artifact_id}")
                print(f"CLOSURE_DIAG_ERROR={reason(exc)}")
                return False
            stack.append((child, content.artifact_id))

    print(f"CLOSURE_DIAG_STATUS=STRUCTURAL_TRACE_PASS")
    print(f"CLOSURE_DIAG_VISITED={len(seen)}")
    return True

def main():
    print("MODE=DISPOSABLE_DB_REPLAY")
    print("LIVE_DB_WRITE=NO")
    print("PRODUCTION_ACTION=NO")

    if not LIVE_DB.is_file():
        raise SystemExit("REPLAY_ERROR=LIVE_DB_NOT_FOUND")
    live_before = sha256(LIVE_DB)
    print(f"LIVE_DB_SHA256_BEFORE={live_before}")
    if not R5_TOOL.is_file() or sha256(R5_TOOL) != R5_TOOL_SHA:
        raise SystemExit("REPLAY_ERROR=R5_TOOL_IDENTITY_MISMATCH")
    for label, path in FILES.items():
        if not path.is_file():
            raise SystemExit(f"REPLAY_ERROR=R5_{label}_FILE_MISSING")

    owner = json.loads(FILES["OWNER_DECISION"].read_text(encoding="utf-8-sig"))
    print(f"OWNER_DECISION_ID={owner.get('decision_record_id')}")
    print(f"OWNER_DECISION_RECORD_SHA256={owner.get('record_sha256')}")
    print(f"OWNER_DECISION={owner.get('decision')}")

    r5 = load_module(R5_TOOL)
    api = r5.load_candidate_api()

    # Build the same bounded artifact source index as R5, but suppress its verbose inventory.
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture):
        index = r5.build_artifact_index(api)
    print(f"REPLAY_SOURCE_INDEX_COUNT={len(index)}")

    acceptance = load_doc(api, FILES["ACCEPTANCE"])
    rpm = load_doc(api, FILES["RPM"])
    final_gate = load_doc(api, FILES["FINAL_GATE"])

    crp = index.get(PROFILE_ID)
    if crp is None:
        raise SystemExit("REPLAY_ERROR=CRP_NOT_IN_R5_SOURCE_INDEX")

    ap = acceptance.semantic_payload
    classifier_ref = ap["classifier_artifact_manifest"]
    classifier = index.get(classifier_ref["artifact_id"])
    if classifier is None or classifier.content_sha256 != classifier_ref["content_sha256"]:
        raise SystemExit("REPLAY_ERROR=CLASSIFIER_NOT_IN_R5_SOURCE_INDEX")

    gates = []
    for ref in ap["pre_acceptance_task04_gate_result_manifests"]:
        item = index.get(ref["artifact_id"])
        if item is None or item.content_sha256 != ref["content_sha256"]:
            raise SystemExit(f"REPLAY_ERROR=GATE_NOT_IN_R5_SOURCE_INDEX:{ref['artifact_id']}")
        gates.append(item)

    comparisons = []
    for ref in ap["accepted_product_validation_comparison_records"]:
        item = index.get(ref["artifact_id"])
        if item is None or item.content_sha256 != ref["content_sha256"]:
            raise SystemExit(f"REPLAY_ERROR=COMPARISON_NOT_IN_R5_SOURCE_INDEX:{ref['artifact_id']}")
        comparisons.append(item)

    leaf_contents = [*gates, *comparisons, classifier]
    crp_refs = api["runtime_refs"](crp)
    acceptance_refs = api["extract_refs"](acceptance)
    rpm_refs = api["runtime_refs"](rpm)
    final_gate_refs = api["extract_refs"](final_gate)

    temp_root = LAB / "diagnostics" / "taccept-r5-runtime-replay-v1"
    temp_root.mkdir(parents=True, exist_ok=True)
    temp_db = temp_root / "control-disposable.sqlite3"
    if temp_db.exists():
        temp_db.unlink()
    shutil.copy2(LIVE_DB, temp_db)

    store = api["ControlStore"](temp_db)
    conn = store._connect()
    fail_stage = None
    try:
        conn.execute("BEGIN IMMEDIATE")

        # Compact preflight against the disposable copy.
        print_ref_state(conn, "CRP_PREPUT", crp_refs)

        for i, content in enumerate(leaf_contents, 1):
            try:
                store._put(conn, content, ())
            except Exception as exc:
                fail_stage = f"PUT_LEAF_{i}_{content.artifact_type}"
                print(f"FAIL_STAGE={fail_stage}")
                print(f"FAIL_ARTIFACT={content.artifact_id}")
                print(f"FAIL_REASON={reason(exc)}")
                return 2
        print(f"PUT_LEAVES=PASS|COUNT={len(leaf_contents)}")

        stages = [
            ("PUT_CRP", crp, crp_refs),
            ("PUT_ACCEPTANCE", acceptance, acceptance_refs),
            ("PUT_RPM", rpm, rpm_refs),
            ("PUT_FINAL_GATE", final_gate, final_gate_refs),
        ]
        for label, content, refs in stages:
            print_ref_state(conn, f"{label}_PRECHECK", refs)
            try:
                store._put(conn, content, refs)
                print(f"{label}=PASS")
            except Exception as exc:
                fail_stage = label
                print(f"FAIL_STAGE={label}")
                print(f"FAIL_ARTIFACT={content.artifact_id}")
                print(f"FAIL_REASON={reason(exc)}")
                return 2

        print("CLOSURE_RPM_TRACE_BEGIN=YES")
        trace_closure(api, store, conn, rpm)
        try:
            store._closure(conn, rpm)
            print("CLOSURE_RPM=PASS")
        except Exception as exc:
            fail_stage = "CLOSURE_RPM"
            print("FAIL_STAGE=CLOSURE_RPM")
            print(f"FAIL_ARTIFACT={rpm.artifact_id}")
            print(f"FAIL_REASON={reason(exc)}")
            return 2

        print("CLOSURE_CRP_TRACE_BEGIN=YES")
        trace_closure(api, store, conn, crp)
        try:
            store._closure(conn, crp)
            print("CLOSURE_CRP=PASS")
        except Exception as exc:
            fail_stage = "CLOSURE_CRP"
            print("FAIL_STAGE=CLOSURE_CRP")
            print(f"FAIL_ARTIFACT={crp.artifact_id}")
            print(f"FAIL_REASON={reason(exc)}")
            return 2

        print("REPLAY_STATUS=PASS")
        return 0
    finally:
        if conn.in_transaction:
            conn.rollback()
        conn.close()
        live_after = sha256(LIVE_DB)
        print(f"LIVE_DB_SHA256_AFTER={live_after}")
        print(f"LIVE_DB_UNCHANGED={'YES' if live_before == live_after else 'NO'}")
        try:
            if temp_db.exists():
                temp_db.unlink()
        except OSError:
            pass

if __name__ == "__main__":
    raise SystemExit(main())
