"""Task-04 T-ACCEPT read-only prerequisite inventory.

Purpose:
- locate exact PASS GateResultManifest artifacts for T-05/T-06A/T-07/T-08/T-09;
- prove each retained run is bound to the exact frozen ClassificationRuntimeProfile;
- recover the exact active/admitted Foundation RuntimeProfileAdmissionManifest lineage;
- perform NO artifact writes, NO profile admission, NO activation, NO production action.

This tool is intentionally read-only and stops on ambiguity.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
from pathlib import Path

LAB = Path(r"C:\CaptivPortal-Lab")
REPO = LAB / "coder-task04-t09-utility-repair-a1"
TASK04_RUNS = LAB / "official-runs" / "task04"
CONTROL_DB = LAB / "foundation-control-plane" / "device-fingerprint-control-plane.sqlite3"

EXPECTED_COMMIT = "8a39459be3ce7ed40e325736034245f0025cf249"
EXPECTED_TREE = "e2521f27c9f91978e381bce202ab3e3c83aa6dad"
PROFILE_ID = "ClassificationRuntimeProfile:v1:sha256:1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c"
PROFILE_SHA = "1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c"
EXPECTED_T06A = "GateResultManifest:v1:sha256:cd102f0fca7adb9e09ce1ff69d2109b34691e7362fd071a0617fc300547db406"
EXPECTED_T09 = "GateResultManifest:v1:sha256:d231fd0729c1820788f2f708c1135f04d4891d7033c1b3aeb76591fbbe7e895e"
GATES = ("T-05", "T-06A", "T-07", "T-08", "T-09")


def fail(code: str) -> None:
    print("TACCEPT_INVENTORY_STATUS=BLOCKED")
    print(f"BLOCKER={code}")
    raise SystemExit(2)


def run_git(*args: str) -> str:
    cp = subprocess.run(
        ["git", "-C", str(REPO), *args],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    return cp.stdout.strip()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def contains_string(value, target: str) -> bool:
    if value == target:
        return True
    if isinstance(value, dict):
        return any(contains_string(v, target) for v in value.values())
    if isinstance(value, list):
        return any(contains_string(v, target) for v in value)
    return False


def json_docs(root: Path):
    for path in sorted(root.rglob("*.json")):
        try:
            if path.stat().st_size > 16 * 1024 * 1024:
                continue
            raw = path.read_text(encoding="utf-8-sig")
            value = json.loads(raw)
        except Exception:
            continue
        if isinstance(value, dict):
            yield path, value


def ref_of(doc: dict) -> dict[str, str] | None:
    aid = doc.get("artifact_id")
    digest = doc.get("content_sha256")
    if isinstance(aid, str) and isinstance(digest, str) and aid.endswith(digest):
        return {"artifact_id": aid, "content_sha256": digest}
    return None


def payload(doc: dict) -> dict:
    value = doc.get("semantic_payload")
    return value if isinstance(value, dict) else {}


def gate_id(doc: dict) -> str | None:
    p = payload(doc)
    for key in ("gate_id", "source_gate_id"):
        value = p.get(key)
        if isinstance(value, str):
            return value
    return None


def gate_status(doc: dict) -> str | None:
    p = payload(doc)
    value = p.get("status")
    return value if isinstance(value, str) else None


def candidate_matches(doc: dict) -> bool:
    p = payload(doc)
    commit_fields = (
        p.get("candidate_repository_commit_sha"),
        p.get("repository_commit_sha"),
        p.get("candidate_commit"),
    )
    tree_fields = (
        p.get("candidate_repository_tree_sha"),
        p.get("repository_tree_sha"),
        p.get("candidate_tree"),
    )
    commits = [x for x in commit_fields if isinstance(x, str)]
    trees = [x for x in tree_fields if isinstance(x, str)]
    return (not commits or EXPECTED_COMMIT in commits) and (not trees or EXPECTED_TREE in trees)


def parent_run_has_profile(path: Path) -> bool:
    # Search only the containing gate-run subtree, not all Task-04 history.
    parts = path.parts
    try:
        idx = parts.index("task04")
    except ValueError:
        return False
    # Prefer nearest top-level gate folder (t05/t06a/t07/t08/t09), then exact run subtree.
    gate_root = Path(*parts[: idx + 2])
    for p, doc in json_docs(gate_root):
        if contains_string(doc, PROFILE_ID):
            return True
    return False


def collect_gate_results() -> dict[str, tuple[Path, dict]]:
    found: dict[str, list[tuple[Path, dict]]] = {g: [] for g in GATES}
    for path, doc in json_docs(TASK04_RUNS):
        if doc.get("artifact_type") != "GateResultManifest":
            continue
        gid = gate_id(doc)
        if gid not in found:
            continue
        if gate_status(doc) != "PASS":
            continue
        if not candidate_matches(doc):
            continue
        ref = ref_of(doc)
        if ref is None:
            continue
        if gid == "T-06A" and ref["artifact_id"] != EXPECTED_T06A:
            continue
        if gid == "T-09" and ref["artifact_id"] != EXPECTED_T09:
            continue
        found[gid].append((path, doc))

    selected: dict[str, tuple[Path, dict]] = {}
    for gid in GATES:
        # Deduplicate identical artifact IDs that may exist as copied evidence.
        by_id: dict[str, tuple[Path, dict]] = {}
        for path, doc in found[gid]:
            aid = doc["artifact_id"]
            existing = by_id.get(aid)
            if existing is None or len(str(path)) < len(str(existing[0])):
                by_id[aid] = (path, doc)
        items = list(by_id.values())
        if len(items) != 1:
            print(f"{gid}_PASS_CANDIDATE_COUNT={len(items)}")
            for path, doc in items:
                print(f"{gid}_CANDIDATE={doc.get('artifact_id')}|{path}")
            fail(f"{gid}_PASS_RESULT_AMBIGUOUS_OR_MISSING")
        selected[gid] = items[0]
    return selected


def sqlite_ro(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def decode_payload(row: sqlite3.Row) -> dict:
    raw = row["semantic_payload_json"]
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    value = json.loads(raw)
    if not isinstance(value, dict):
        fail("CONTROL_PLANE_ARTIFACT_PAYLOAD_NOT_OBJECT")
    return value


def artifact_row(conn: sqlite3.Connection, artifact_id: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT artifact_id,artifact_type,content_sha256,semantic_payload_json "
        "FROM artifacts WHERE artifact_id=?",
        (artifact_id,),
    ).fetchone()
    if row is None:
        fail(f"CONTROL_PLANE_ARTIFACT_MISSING:{artifact_id}")
    return row


def active_foundation_lineage(conn: sqlite3.Connection, foundation_profile_ref: dict) -> tuple[dict, dict]:
    ptr = conn.execute(
        "SELECT profile_kind,runtime_profile_id,runtime_profile_digest,activation_record_id,"
        "activation_generation_id,updated_at_utc FROM active_pointers WHERE profile_kind='foundation'"
    ).fetchone()
    if ptr is None:
        fail("FOUNDATION_ACTIVE_POINTER_MISSING")
    print(f"FOUNDATION_ACTIVE_PROFILE_ID={ptr['runtime_profile_id']}")
    print(f"FOUNDATION_ACTIVE_PROFILE_SHA256={ptr['runtime_profile_digest']}")
    print(f"FOUNDATION_ACTIVE_ACTIVATION_RECORD_ID={ptr['activation_record_id']}")
    if ptr["runtime_profile_id"] != foundation_profile_ref["artifact_id"] or \
            ptr["runtime_profile_digest"] != foundation_profile_ref["content_sha256"]:
        fail("CRP_FOUNDATION_PROFILE_NOT_CURRENT_ACTIVE_FOUNDATION")

    act = conn.execute(
        "SELECT artifact_id FROM activations WHERE activation_record_id=?",
        (ptr["activation_record_id"],),
    ).fetchone()
    if act is None:
        fail("FOUNDATION_ACTIVATION_ROW_MISSING")
    act_doc_row = artifact_row(conn, act["artifact_id"])
    act_payload = decode_payload(act_doc_row)
    rpm_id = act_payload.get("runtime_profile_admission_manifest_id")
    rpm_sha = act_payload.get("runtime_profile_admission_manifest_digest")
    if not isinstance(rpm_id, str) or not isinstance(rpm_sha, str):
        fail("FOUNDATION_ACTIVATION_RPM_REF_MISSING")

    rpm_row = artifact_row(conn, rpm_id)
    if rpm_row["artifact_type"] != "RuntimeProfileAdmissionManifest" or rpm_row["content_sha256"] != rpm_sha:
        fail("FOUNDATION_RPM_IDENTITY_MISMATCH")
    rpm = decode_payload(rpm_row)
    if rpm.get("profile_kind") != "foundation" or rpm.get("compatibility_validation_result") != "PASS":
        fail("FOUNDATION_RPM_NOT_ACCEPTED")
    candidate = rpm.get("candidate_profile")
    if candidate != foundation_profile_ref:
        fail("FOUNDATION_RPM_PROFILE_MISMATCH")

    fam_ref = rpm.get("foundation_admission_manifest")
    if not isinstance(fam_ref, dict):
        fail("FOUNDATION_RPM_FAM_REF_MISSING")
    fam_row = artifact_row(conn, fam_ref.get("artifact_id", ""))
    if fam_row["artifact_type"] != "FoundationAdmissionManifest" or \
            fam_row["content_sha256"] != fam_ref.get("content_sha256"):
        fail("FOUNDATION_ADMISSION_MANIFEST_IDENTITY_MISMATCH")
    fam = decode_payload(fam_row)

    print(f"FOUNDATION_RPM_ID={rpm_row['artifact_id']}")
    print(f"FOUNDATION_RPM_SHA256={rpm_row['content_sha256']}")
    print(f"FOUNDATION_RPM_UPDATE_CLASS={rpm.get('update_class')}")
    print(f"FOUNDATION_ADMISSION_MANIFEST_ID={fam_row['artifact_id']}")
    print(f"FOUNDATION_ADMISSION_MANIFEST_SHA256={fam_row['content_sha256']}")
    return (
        {"artifact_id": rpm_row["artifact_id"], "content_sha256": rpm_row["content_sha256"]},
        {"artifact_id": fam_row["artifact_id"], "content_sha256": fam_row["content_sha256"]},
    )


def main() -> int:
    for p in (REPO, TASK04_RUNS, CONTROL_DB):
        if not p.exists():
            fail(f"REQUIRED_PATH_MISSING:{p}")

    commit = run_git("rev-parse", "HEAD")
    tree = run_git("show", "-s", "--format=%T", "HEAD")
    status = run_git("status", "--porcelain")
    print(f"CANDIDATE_COMMIT={commit}")
    print(f"CANDIDATE_TREE={tree}")
    print(f"CANDIDATE_CLEAN={'YES' if not status else 'NO'}")
    if commit != EXPECTED_COMMIT or tree != EXPECTED_TREE or status:
        fail("CANDIDATE_IDENTITY_CHANGED")

    selected = collect_gate_results()
    for gid in GATES:
        path, doc = selected[gid]
        ref = ref_of(doc)
        profile_present = parent_run_has_profile(path)
        print(f"{gid}_GATE_RESULT_ID={ref['artifact_id']}")
        print(f"{gid}_GATE_RESULT_SHA256={ref['content_sha256']}")
        print(f"{gid}_GATE_RESULT_PATH={path}")
        print(f"{gid}_RUN_CONTAINS_EXACT_PROFILE={'YES' if profile_present else 'NO'}")
        if not profile_present:
            fail(f"{gid}_EXACT_PROFILE_NOT_FOUND_IN_RETAINED_RUN")

    # Find exact ClassificationRuntimeProfile document and recover its Foundation ref.
    crp_docs = []
    for path, doc in json_docs(TASK04_RUNS):
        if doc.get("artifact_type") == "ClassificationRuntimeProfile" and doc.get("artifact_id") == PROFILE_ID:
            if doc.get("content_sha256") != PROFILE_SHA:
                fail("CRP_DIGEST_MISMATCH")
            crp_docs.append((path, doc))
    if not crp_docs:
        fail("EXACT_CLASSIFICATION_RUNTIME_PROFILE_DOCUMENT_MISSING")
    semantic_payloads = {
        json.dumps(payload(doc), sort_keys=True, separators=(",", ":"))
        for _, doc in crp_docs
    }
    if len(semantic_payloads) != 1:
        fail("CRP_SEMANTIC_CONTENT_AMBIGUOUS")
    crp_path, crp = crp_docs[0]
    foundation_ref = payload(crp).get("foundation_runtime_profile")
    if not isinstance(foundation_ref, dict) or set(foundation_ref) != {"artifact_id", "content_sha256"}:
        fail("CRP_FOUNDATION_REF_INVALID")
    print(f"CLASSIFICATION_RUNTIME_PROFILE_ID={PROFILE_ID}")
    print(f"CLASSIFICATION_RUNTIME_PROFILE_SHA256={PROFILE_SHA}")
    print(f"CLASSIFICATION_RUNTIME_PROFILE_DOCUMENT_COUNT={len(crp_docs)}")
    print(f"CLASSIFICATION_RUNTIME_PROFILE_SAMPLE_PATH={crp_path}")
    print(f"CRP_FOUNDATION_PROFILE_ID={foundation_ref['artifact_id']}")
    print(f"CRP_FOUNDATION_PROFILE_SHA256={foundation_ref['content_sha256']}")

    control_before = sha256(CONTROL_DB)
    print(f"CONTROL_DB_SHA256_BEFORE={control_before}")
    conn = sqlite_ro(CONTROL_DB)
    try:
        quick = [r[0] for r in conn.execute("PRAGMA quick_check").fetchall()]
        print(f"CONTROL_DB_QUICK_CHECK={'PASS' if quick == ['ok'] else 'FAIL'}")
        if quick != ["ok"]:
            fail("CONTROL_DB_QUICK_CHECK_FAILED")
        rpm_ref, fam_ref = active_foundation_lineage(conn, foundation_ref)
        class_ptr = conn.execute(
            "SELECT runtime_profile_id,runtime_profile_digest FROM active_pointers "
            "WHERE profile_kind='classification'"
        ).fetchone()
        if class_ptr is None:
            print("CLASSIFICATION_ACTIVE_POINTER=ABSENT")
        else:
            print(f"CLASSIFICATION_ACTIVE_POINTER={class_ptr['runtime_profile_id']}|{class_ptr['runtime_profile_digest']}")
            if class_ptr["runtime_profile_id"] == PROFILE_ID:
                fail("CANDIDATE_ALREADY_ACTIVE_BEFORE_TACCEPT")
    finally:
        conn.close()

    control_after = sha256(CONTROL_DB)
    print(f"CONTROL_DB_SHA256_AFTER={control_after}")
    print(f"CONTROL_DB_UNCHANGED={'YES' if control_before == control_after else 'NO'}")
    if control_before != control_after:
        fail("CONTROL_DB_CHANGED_DURING_READ_ONLY_INVENTORY")

    print(f"T09_EXPECTED_FINAL_ID={EXPECTED_T09}")
    print("PRODUCTION_ACTION=NO")
    print("PROFILE_ACTIVATION=NO")
    print("ARTIFACT_WRITE=NO")
    print("TACCEPT_INVENTORY_STATUS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
