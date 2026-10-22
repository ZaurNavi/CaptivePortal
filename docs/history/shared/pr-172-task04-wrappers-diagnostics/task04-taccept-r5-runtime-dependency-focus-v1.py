from __future__ import annotations

import json
import sqlite3
import hashlib
from pathlib import Path

DB = Path(r"C:\CaptivPortal-Lab\foundation-control-plane\device-fingerprint-control-plane.sqlite3")
R5 = Path(r"C:\CaptivPortal-Lab\official-runs\task04\taccept\official-run-20261003T065247Z-TACCEPT-A1-R5-01")

PROFILE_ID = "ClassificationRuntimeProfile:v1:sha256:1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c"
PROFILE_SHA = "1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c"

R5_OUTPUTS = {
    "ACCEPTANCE": R5 / "task04-acceptance-manifest.json",
    "RPM": R5 / "classification-runtime-profile-admission-manifest.json",
    "FINAL_GATE": R5 / "taccept-gate-result-manifest.json",
    "OWNER_DECISION": R5 / "owner-decision.json",
}

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def artifact_id_from_doc(path: Path):
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw.get("artifact_id")

def main():
    if not DB.exists():
        raise SystemExit(f"CHECK_ERROR=DB_NOT_FOUND:{DB}")

    print(f"DB={DB}")
    before = sha256(DB)
    print(f"DB_SHA256_BEFORE={before}")
    print("MODE=READ_ONLY")

    conn = sqlite3.connect(DB.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only=ON")
        qc = conn.execute("PRAGMA quick_check").fetchone()[0]
        print(f"QUICK_CHECK={qc}")

        row = conn.execute(
            "SELECT artifact_id, artifact_type, content_sha256, semantic_payload_json "
            "FROM artifacts WHERE artifact_id=?",
            (PROFILE_ID,),
        ).fetchone()

        if row is None:
            print("PROFILE_P_IN_CONTROL_DB=NO")
        else:
            print("PROFILE_P_IN_CONTROL_DB=YES")
            print(f"PROFILE_P_TYPE={row['artifact_type']}")
            print(f"PROFILE_P_SHA={row['content_sha256']}")
            payload = json.loads(row["semantic_payload_json"])
            declared_fields = (
                "foundation_runtime_profile",
                "knowledge_bundle",
                "classification_policy",
                "evidence_adapter_contract_set",
                "classifier_artifact_manifest",
            )
            declared = []
            for field in declared_fields:
                ref = payload[field]
                declared.append((ref["artifact_id"], ref["content_sha256"], field))

            edges = conn.execute(
                "SELECT dependency_id, dependency_digest "
                "FROM artifact_dependencies WHERE owner_id=? ORDER BY dependency_id",
                (PROFILE_ID,),
            ).fetchall()
            actual = {(r["dependency_id"], r["dependency_digest"]) for r in edges}

            print(f"PROFILE_P_DECLARED_DEP_COUNT={len(declared)}")
            print(f"PROFILE_P_ACTUAL_EDGE_COUNT={len(edges)}")
            for aid, digest, field in declared:
                dep = conn.execute(
                    "SELECT artifact_type, content_sha256 FROM artifacts WHERE artifact_id=?",
                    (aid,),
                ).fetchone()
                present = dep is not None and dep["content_sha256"] == digest
                edge = (aid, digest) in actual
                print(
                    f"PROFILE_P_DEP={field}|{aid}"
                    f"|TARGET_PRESENT={'YES' if present else 'NO'}"
                    f"|EDGE_PRESENT={'YES' if edge else 'NO'}"
                )

        for label, path in R5_OUTPUTS.items():
            print(f"R5_{label}_FILE={'PRESENT' if path.exists() else 'ABSENT'}")
            if not path.exists():
                continue
            print(f"R5_{label}_FILE_SHA256={sha256(path)}")
            if label != "OWNER_DECISION":
                aid = artifact_id_from_doc(path)
                print(f"R5_{label}_ARTIFACT_ID={aid}")
                if aid:
                    exists = conn.execute(
                        "SELECT 1 FROM artifacts WHERE artifact_id=?", (aid,)
                    ).fetchone() is not None
                    print(f"R5_{label}_IN_CONTROL_DB={'YES' if exists else 'NO'}")
            else:
                raw = json.loads(path.read_text(encoding="utf-8"))
                print(f"R5_OWNER_DECISION_ID={raw.get('decision_record_id')}")
                print(f"R5_OWNER_DECISION_RECORD_SHA256={raw.get('record_sha256')}")
                print(f"R5_OWNER_DECISION_VALUE={raw.get('decision')}")

        class_pointer = conn.execute(
            "SELECT runtime_profile_id FROM active_pointers WHERE profile_kind='classification'"
        ).fetchone()
        print(f"CLASSIFICATION_ACTIVE_POINTER={'PRESENT' if class_pointer else 'ABSENT'}")

    finally:
        conn.close()

    after = sha256(DB)
    print(f"DB_SHA256_AFTER={after}")
    print(f"DB_UNCHANGED={'YES' if before == after else 'NO'}")

    # Single compact verdict.
    conn = sqlite3.connect(DB.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT semantic_payload_json FROM artifacts WHERE artifact_id=?",
            (PROFILE_ID,),
        ).fetchone()
        if row is None:
            print("CHECK_STATUS=PROFILE_P_NOT_PREEXISTING")
            return
        payload = json.loads(row["semantic_payload_json"])
        refs = [
            payload[k] for k in (
                "foundation_runtime_profile",
                "knowledge_bundle",
                "classification_policy",
                "evidence_adapter_contract_set",
                "classifier_artifact_manifest",
            )
        ]
        edges = conn.execute(
            "SELECT dependency_id, dependency_digest FROM artifact_dependencies WHERE owner_id=?",
            (PROFILE_ID,),
        ).fetchall()
        actual = {(r["dependency_id"], r["dependency_digest"]) for r in edges}
        declared = {(r["artifact_id"], r["content_sha256"]) for r in refs}
        if not actual and declared:
            print("CHECK_STATUS=PREEXISTING_PROFILE_WITHOUT_RUNTIME_EDGES_CONFIRMED")
        elif actual != declared:
            print("CHECK_STATUS=PREEXISTING_PROFILE_EDGE_SET_MISMATCH")
        else:
            print("CHECK_STATUS=PROFILE_EDGES_COMPLETE")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
