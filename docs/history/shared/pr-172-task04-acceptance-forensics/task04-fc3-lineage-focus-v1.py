from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

DB = Path(r"C:\CaptivPortal-Lab\foundation-control-plane\device-fingerprint-control-plane.sqlite3")

TARGET_ID = (
    "TTLCapturePlacementProof:v1:sha256:"
    "c47c4235ddb2fd55c9851484f2fc242fe49a31e6b08d8ac44388368266989e1f"
)
TARGET_SHA = TARGET_ID.rsplit(":", 1)[1]

KNOWN = {
    "F_C3_GATE_PROOF": (
        "GateProofArtifact:v1:sha256:"
        "ae1dbca5d44be872d0ff1661c884b8dcde595a0257cadf7b45b697a36de2a9f6"
    ),
    "FOUNDATION_GATE_RESULT": (
        "GateResultManifest:v1:sha256:"
        "b157b62dc3f0bedd6fc6b1124658ea02d079e5a06013c4521e5c364d78262292"
    ),
    "FOUNDATION_ADMISSION": (
        "FoundationAdmissionManifest:v1:sha256:"
        "44f2b26b297c7c126a7b224b8db8f88873893a0cc6819e4e18f6106af00de4ff"
    ),
    "FOUNDATION_RPM": (
        "RuntimeProfileAdmissionManifest:v1:sha256:"
        "95231fa3dee79b8d0b00a4f645664d3d80d3d4b1b6ca48fc4865191d24b12db6"
    ),
    "TARGET_TTL_PROOF": TARGET_ID,
}

ARTIFACT_ID_RE = re.compile(r"[A-Za-z0-9_]+:v\\d+:sha256:[0-9a-f]{64}")

def fail(msg: str, code: int = 2) -> None:
    print(f"FOCUS_ERROR={msg}")
    print("FOCUS_STATUS=BLOCKED")
    raise SystemExit(code)

def decode_payload(raw):
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if not isinstance(raw, str):
        return raw
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
        "semantic_payload": decode_payload(row[3]),
    }

def collect_interesting(value, path="$", out=None):
    if out is None:
        out = []
    if len(out) >= 40:
        return out

    if isinstance(value, dict):
        for k in sorted(value):
            v = value[k]
            p = f"{path}.{k}"
            lk = str(k).lower()
            key_interesting = any(
                token in lk for token in ("ttl", "topology", "evidence", "capture", "proof", "origin")
            )
            if key_interesting and isinstance(v, (str, int, bool, type(None))):
                out.append((p, v))
            collect_interesting(v, p, out)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            collect_interesting(item, f"{path}[{i}]", out)
    elif isinstance(value, str):
        if TARGET_SHA in value or TARGET_ID in value:
            out.append((path, value))
        else:
            m = ARTIFACT_ID_RE.fullmatch(value)
            if m and any(token in value for token in (
                "TTLCapturePlacementProof",
                "OriginRuntimeAdmission",
                "GateProofArtifact",
                "GateResultManifest",
            )):
                out.append((path, value))
    return out

def main() -> int:
    if not DB.exists():
        fail(f"DB_NOT_FOUND:{DB}")

    uri = DB.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        quick = conn.execute("PRAGMA quick_check").fetchone()
        quick_value = quick[0] if quick else None
        print(f"DB={DB}")
        print("READ_ONLY=YES")
        print(f"QUICK_CHECK={quick_value}")

        required_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(artifacts)").fetchall()
        }
        expected = {"artifact_id", "artifact_type", "content_sha256", "semantic_payload_json"}
        if not expected.issubset(required_cols):
            fail("UNEXPECTED_ARTIFACTS_SCHEMA")

        found = {}
        for label, artifact_id in KNOWN.items():
            artifact = get_artifact(conn, artifact_id)
            found[label] = artifact
            if artifact is None:
                print(f"{label}=ABSENT")
            else:
                print(
                    f"{label}=PRESENT"
                    f"|TYPE={artifact['artifact_type']}"
                    f"|SHA={artifact['content_sha256']}"
                )

        mention_rows = conn.execute(
            """
            SELECT artifact_id, artifact_type
            FROM artifacts
            WHERE CAST(semantic_payload_json AS TEXT) LIKE ?
            ORDER BY artifact_id
            """,
            (f"%{TARGET_SHA}%",),
        ).fetchall()

        print(f"TARGET_PAYLOAD_MENTION_COUNT={len(mention_rows)}")
        for artifact_id, artifact_type in mention_rows[:20]:
            print(f"TARGET_PAYLOAD_MENTION={artifact_type}|{artifact_id}")

        dep_tables = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        dep_rows = []
        if "artifact_dependencies" in dep_tables:
            dep_cols = {
                row[1] for row in conn.execute(
                    "PRAGMA table_info(artifact_dependencies)"
                ).fetchall()
            }
            if {"owner_id", "dependency_id", "dependency_digest"}.issubset(dep_cols):
                dep_rows = conn.execute(
                    """
                    SELECT owner_id, dependency_id, dependency_digest
                    FROM artifact_dependencies
                    WHERE dependency_id = ? OR dependency_digest = ?
                    ORDER BY owner_id, dependency_id
                    """,
                    (TARGET_ID, TARGET_SHA),
                ).fetchall()

        print(f"TARGET_DEPENDENCY_EDGE_COUNT={len(dep_rows)}")
        for owner_id, dependency_id, dependency_digest in dep_rows[:20]:
            print(
                "TARGET_DEPENDENCY_EDGE="
                f"{owner_id}|{dependency_id}|{dependency_digest}"
            )

        for label in (
            "F_C3_GATE_PROOF",
            "FOUNDATION_GATE_RESULT",
            "FOUNDATION_ADMISSION",
            "FOUNDATION_RPM",
        ):
            artifact = found[label]
            if artifact is None:
                continue
            hits = collect_interesting(artifact["semantic_payload"])
            print(f"{label}_INTERESTING_COUNT={len(hits)}")
            for path, value in hits[:25]:
                rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                if len(rendered) > 300:
                    rendered = rendered[:297] + "..."
                print(f"{label}_HIT={path}|{rendered}")

        target_present = found["TARGET_TTL_PROOF"] is not None
        dangling = (not target_present) and (bool(mention_rows) or bool(dep_rows))

        if target_present:
            print("FOCUS_STATUS=TARGET_CONTENT_PRESENT")
        elif dangling:
            print("FOCUS_STATUS=DANGLING_REF_CONFIRMED")
        else:
            print("FOCUS_STATUS=TARGET_NOT_PRESENT_AND_NO_DB_REF_FOUND")

        return 0
    except (sqlite3.Error, UnicodeError, json.JSONDecodeError) as exc:
        fail(f"{type(exc).__name__}:{exc}")
    finally:
        conn.close()

if __name__ == "__main__":
    sys.exit(main())
