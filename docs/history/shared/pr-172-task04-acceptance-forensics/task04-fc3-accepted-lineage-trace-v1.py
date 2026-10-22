from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

DB = Path(r"C:\CaptivPortal-Lab\foundation-control-plane\device-fingerprint-control-plane.sqlite3")

TARGET_TTL_ID = (
    "TTLCapturePlacementProof:v1:sha256:"
    "c47c4235ddb2fd55c9851484f2fc242fe49a31e6b08d8ac44388368266989e1f"
)
TARGET_TTL_SHA = TARGET_TTL_ID.rsplit(":", 1)[1]

FOUNDATION_ADMISSION_ID = (
    "FoundationAdmissionManifest:v1:sha256:"
    "44f2b26b297c7c126a7b224b8db8f88873893a0cc6819e4e18f6106af00de4ff"
)
FOUNDATION_RPM_ID = (
    "RuntimeProfileAdmissionManifest:v1:sha256:"
    "95231fa3dee79b8d0b00a4f645664d3d80d3d4b1b6ca48fc4865191d24b12db6"
)

def fail(msg: str) -> None:
    print(f"TRACE_ERROR={msg}")
    print("TRACE_STATUS=BLOCKED")
    raise SystemExit(2)

def load_json(raw):
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return json.loads(raw)

def get_artifact(conn, artifact_id: str):
    row = conn.execute(
        """
        SELECT artifact_id, artifact_type, content_sha256, semantic_payload_json
        FROM artifacts
        WHERE artifact_id = ?
        """,
        (artifact_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "artifact_id": row[0],
        "artifact_type": row[1],
        "content_sha256": row[2],
        "semantic_payload": load_json(row[3]),
    }

def ref_value(payload, key):
    value = payload.get(key)
    if isinstance(value, dict):
        return value
    return None

def print_ref(label, ref):
    if ref is None:
        print(f"{label}=ABSENT")
        return
    print(
        f"{label}="
        f"{ref.get('artifact_id')}|SHA={ref.get('content_sha256')}"
    )

def main() -> int:
    if not DB.exists():
        fail(f"DB_NOT_FOUND:{DB}")

    conn = sqlite3.connect(DB.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        qc = conn.execute("PRAGMA quick_check").fetchone()
        print(f"DB={DB}")
        print("READ_ONLY=YES")
        print(f"QUICK_CHECK={qc[0] if qc else None}")

        fam = get_artifact(conn, FOUNDATION_ADMISSION_ID)
        rpm = get_artifact(conn, FOUNDATION_RPM_ID)
        if fam is None:
            fail("FOUNDATION_ADMISSION_MISSING")
        if rpm is None:
            fail("FOUNDATION_RPM_MISSING")

        fp = fam["semantic_payload"]
        rp = rpm["semantic_payload"]

        print(f"FOUNDATION_ADMISSION={fam['artifact_id']}")
        print(f"FOUNDATION_RPM={rpm['artifact_id']}")

        fam_ttl = ref_value(fp, "ttl_capture_placement_proof")
        fam_origin = ref_value(fp, "origin_runtime_admission")
        print_ref("FAM_TTL_REF", fam_ttl)
        print_ref("FAM_ORIGIN_REF", fam_origin)

        mandatory = fp.get("mandatory_pre_admission_foundation_gate_ids")
        if isinstance(mandatory, list):
            print("FAM_MANDATORY_GATES=" + ",".join(str(x) for x in mandatory))
            print(f"FAM_HAS_F_C3={'YES' if 'F-C3' in mandatory else 'NO'}")
        else:
            print("FAM_MANDATORY_GATES=UNAVAILABLE")
            print("FAM_HAS_F_C3=UNKNOWN")

        prereq_refs = fp.get("pre_admission_gate_result_manifests")
        if not isinstance(prereq_refs, list):
            fail("FAM_PREREQUISITE_GATE_REFS_UNAVAILABLE")
        print(f"FAM_PREREQUISITE_GATE_REF_COUNT={len(prereq_refs)}")

        # Resolve only GateResultManifest rows and select exact F-C3.
        gate_rows = conn.execute(
            """
            SELECT artifact_id, content_sha256, semantic_payload_json
            FROM artifacts
            WHERE artifact_type = 'GateResultManifest'
            ORDER BY artifact_id
            """
        ).fetchall()

        f_c3 = []
        for artifact_id, content_sha, raw in gate_rows:
            payload = load_json(raw)
            if payload.get("gate_id") == "F-C3":
                f_c3.append({
                    "artifact_id": artifact_id,
                    "content_sha256": content_sha,
                    "semantic_payload": payload,
                })

        print(f"F_C3_GATE_COUNT={len(f_c3)}")
        if not f_c3:
            print("TRACE_STATUS=F_C3_GATE_MISSING")
            return 0

        fam_prereq_ids = {
            x.get("artifact_id")
            for x in prereq_refs
            if isinstance(x, dict)
        }

        exact_candidates = []
        for gate in f_c3:
            p = gate["semantic_payload"]
            print(
                "F_C3_GATE="
                f"{gate['artifact_id']}|STATUS={p.get('status')}"
                f"|COMMIT={p.get('candidate_repository_commit_sha')}"
                f"|TREE={p.get('candidate_repository_tree_sha')}"
                f"|IN_FAM={'YES' if gate['artifact_id'] in fam_prereq_ids else 'NO'}"
            )

            outputs = p.get("output_artifact_refs")
            if not isinstance(outputs, list):
                outputs = []
            print(f"F_C3_OUTPUT_COUNT={len(outputs)}")

            target_output = False
            for ref in outputs:
                if not isinstance(ref, dict):
                    continue
                aid = ref.get("artifact_id")
                sha = ref.get("content_sha256")
                present = get_artifact(conn, aid) if isinstance(aid, str) else None
                print(
                    "F_C3_OUTPUT="
                    f"{aid}|SHA={sha}|PRESENT={'YES' if present else 'NO'}"
                    + (f"|TYPE={present['artifact_type']}" if present else "")
                )
                if aid == TARGET_TTL_ID and sha == TARGET_TTL_SHA:
                    target_output = True

            evidence = p.get("retained_evidence_refs")
            if isinstance(evidence, list):
                print(f"F_C3_RETAINED_EVIDENCE_COUNT={len(evidence)}")
                for idx, item in enumerate(evidence):
                    print(
                        f"F_C3_EVIDENCE_{idx}="
                        + json.dumps(item, ensure_ascii=False, separators=(",", ":"))
                    )
            else:
                print("F_C3_RETAINED_EVIDENCE_COUNT=UNAVAILABLE")

            proof_identity = p.get("proof_execution_identity")
            print(
                "F_C3_PROOF_EXECUTION_IDENTITY="
                + json.dumps(proof_identity, ensure_ascii=False, separators=(",", ":"))
            )

            if (
                p.get("status") == "PASS"
                and gate["artifact_id"] in fam_prereq_ids
                and target_output
            ):
                exact_candidates.append(gate)

        print(f"F_C3_EXACT_ACCEPTED_CANDIDATE_COUNT={len(exact_candidates)}")

        # Resolve FoundationRuntimeProfile through RPM candidate_profile.
        candidate_profile_ref = ref_value(rp, "candidate_profile")
        print_ref("FOUNDATION_RPM_CANDIDATE_PROFILE", candidate_profile_ref)

        foundation_profile = None
        if candidate_profile_ref and isinstance(candidate_profile_ref.get("artifact_id"), str):
            foundation_profile = get_artifact(conn, candidate_profile_ref["artifact_id"])

        if foundation_profile is None:
            print("FOUNDATION_PROFILE=ABSENT")
        else:
            print(
                f"FOUNDATION_PROFILE={foundation_profile['artifact_id']}"
                f"|SHA={foundation_profile['content_sha256']}"
            )
            pp = foundation_profile["semantic_payload"]
            print_ref("FOUNDATION_PROFILE_TTL_REF", ref_value(pp, "ttl_capture_placement_proof"))
            print_ref("FOUNDATION_PROFILE_ORIGIN_REF", ref_value(pp, "origin_runtime_admission"))

        origin = None
        if fam_origin and isinstance(fam_origin.get("artifact_id"), str):
            origin = get_artifact(conn, fam_origin["artifact_id"])
        if origin is None:
            print("ORIGIN_RUNTIME_ADMISSION=ABSENT")
        else:
            print(
                f"ORIGIN_RUNTIME_ADMISSION={origin['artifact_id']}"
                f"|SHA={origin['content_sha256']}"
            )
            op = origin["semantic_payload"]
            print(f"ORIGIN_TCP_STATE={op.get('tcp_state')}")
            print(f"ORIGIN_TCP_REASON_CODE={op.get('tcp_reason_code')}")
            print_ref("ORIGIN_TTL_REF", ref_value(op, "ttl_capture_placement_proof"))

        target_present = get_artifact(conn, TARGET_TTL_ID) is not None
        print(f"TARGET_TTL_CONTENT_PRESENT={'YES' if target_present else 'NO'}")

        refs = []
        for label, ref in (
            ("FAM", fam_ttl),
            ("PROFILE", ref_value(foundation_profile["semantic_payload"], "ttl_capture_placement_proof")
             if foundation_profile else None),
            ("ORIGIN", ref_value(origin["semantic_payload"], "ttl_capture_placement_proof")
             if origin else None),
        ):
            if ref and ref.get("artifact_id") == TARGET_TTL_ID and ref.get("content_sha256") == TARGET_TTL_SHA:
                refs.append(label)
        print("TARGET_TTL_EXACT_REF_OWNERS=" + (",".join(refs) if refs else "NONE"))

        if (
            len(exact_candidates) == 1
            and not target_present
            and {"FAM", "PROFILE", "ORIGIN"}.issubset(set(refs))
        ):
            print("TRACE_STATUS=HISTORICAL_F_ADMIT_PERSISTENCE_DEFECT_CONFIRMED")
        elif len(exact_candidates) == 1 and not target_present:
            print("TRACE_STATUS=F_C3_ACCEPTED_TTL_MISSING_WITH_PARTIAL_LINEAGE")
        elif target_present:
            print("TRACE_STATUS=TARGET_PRESENT")
        else:
            print("TRACE_STATUS=AMBIGUOUS_F_C3_LINEAGE")

        return 0

    except (sqlite3.Error, UnicodeError, json.JSONDecodeError) as exc:
        fail(f"{type(exc).__name__}:{exc}")
    finally:
        conn.close()

if __name__ == "__main__":
    sys.exit(main())
