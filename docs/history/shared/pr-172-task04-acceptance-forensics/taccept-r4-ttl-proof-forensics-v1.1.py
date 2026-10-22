"""T-ACCEPT R4 TTL proof forensics v1.1 — read-only whole-lab exact artifact search.

Target:
TTLCapturePlacementProof:v1:sha256:
c47c4235ddb2fd55c9851484f2fc242fe49a31e6b08d8ac44388368266989e1f

Also records any retained ArtifactContent or dependency references to this exact TTL proof.

No artifacts are created, mutated, reconstructed into stores, or activated.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

LAB = Path(r"C:\CaptivPortal-Lab")
REPO = LAB / "coder-task04-t09-utility-repair-a1"

TARGET_ID = (
    "TTLCapturePlacementProof:v1:sha256:"
    "c47c4235ddb2fd55c9851484f2fc242fe49a31e6b08d8ac44388368266989e1f"
)
TARGET_SHA = "c47c4235ddb2fd55c9851484f2fc242fe49a31e6b08d8ac44388368266989e1f"
OWNER_GATE_ID = (
    "GateResultManifest:v1:sha256:"
    "b157b62dc3f0bedd6fc6b1124658ea02d079e5a06013c4521e5c364d78262292"
)

TEXT_EXTS = {
    ".json", ".jsonl", ".txt", ".md", ".py", ".ps1", ".yaml", ".yml",
    ".log", ".csv", ".tsv", ".ini", ".cfg", ".toml",
}
SQLITE_EXTS = {".sqlite3", ".sqlite", ".db"}
MAX_TEXT_BYTES = 256 * 1024 * 1024


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_only_sqlite(path: Path):
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=1)


def safe_rel(path: Path) -> str:
    try:
        return str(path.relative_to(LAB))
    except ValueError:
        return str(path)


def contains_bytes(path: Path, needles: tuple[bytes, ...]) -> bool:
    try:
        with path.open("rb") as stream:
            overlap = max(len(x) for x in needles) - 1
            tail = b""
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    return False
                buf = tail + chunk
                if any(needle in buf for needle in needles):
                    return True
                tail = buf[-overlap:] if overlap > 0 else b""
    except (OSError, PermissionError):
        return False


def json_walk(value, path=()):
    if isinstance(value, dict):
        yield path, value
        for key, child in value.items():
            yield from json_walk(child, (*path, str(key)))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from json_walk(child, (*path, str(i)))


def inspect_text(path: Path):
    result = {
        "path": safe_rel(path),
        "kind": "TEXT",
        "target_literal": False,
        "target_digest": False,
        "owner_gate_literal": False,
        "artifact_envelope_exact": False,
        "json_locations": [],
    }
    try:
        size = path.stat().st_size
        if size > MAX_TEXT_BYTES:
            return None
        raw = path.read_bytes()
    except (OSError, PermissionError):
        return None

    result["target_literal"] = TARGET_ID.encode() in raw
    result["target_digest"] = TARGET_SHA.encode() in raw
    result["owner_gate_literal"] = OWNER_GATE_ID.encode() in raw
    if not (result["target_literal"] or result["target_digest"] or result["owner_gate_literal"]):
        return None

    if path.suffix.lower() in {".json", ".jsonl"}:
        texts = []
        try:
            if path.suffix.lower() == ".jsonl":
                texts = [line for line in raw.decode("utf-8-sig").splitlines() if line.strip()]
            else:
                texts = [raw.decode("utf-8-sig")]
        except UnicodeError:
            texts = []
        for n, text in enumerate(texts):
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                continue
            for jpath, obj in json_walk(value):
                if obj.get("artifact_id") == TARGET_ID:
                    result["artifact_envelope_exact"] = True
                    result["json_locations"].append(
                        {"line_or_doc": n + 1, "json_path": ".".join(jpath), "type": "TARGET_ENVELOPE"}
                    )
                if obj.get("artifact_id") == OWNER_GATE_ID:
                    result["json_locations"].append(
                        {"line_or_doc": n + 1, "json_path": ".".join(jpath), "type": "OWNER_GATE_ENVELOPE"}
                    )
    return result


def inspect_sqlite(path: Path):
    hit = {
        "path": safe_rel(path),
        "kind": "SQLITE",
        "target_artifact_row": None,
        "target_dependency_rows": [],
        "owner_gate_row": None,
        "owner_gate_dependency_rows": [],
        "payload_mentions": [],
        "quick_check": None,
        "sha256_before": None,
        "sha256_after": None,
    }
    conn = None
    try:
        conn = read_only_sqlite(path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        tables = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if not ({"artifacts", "artifact_dependencies"} & tables):
            return None

        before = sha256(path)
        hit["sha256_before"] = before
        quick = [row[0] for row in conn.execute("PRAGMA quick_check").fetchall()]
        hit["quick_check"] = quick

        if "artifacts" in tables:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(artifacts)")}
            required = {"artifact_id", "artifact_type", "content_sha256", "semantic_payload_json"}
            if required <= cols:
                rows = conn.execute(
                    "SELECT artifact_id,artifact_type,content_sha256,length(semantic_payload_json) AS bytes "
                    "FROM artifacts WHERE artifact_id=? OR content_sha256=? OR artifact_type=? "
                    "ORDER BY artifact_id",
                    (TARGET_ID, TARGET_SHA, "TTLCapturePlacementProof"),
                ).fetchall()
                exact_rows = [
                    dict(row) for row in rows
                    if row["artifact_id"] == TARGET_ID and row["content_sha256"] == TARGET_SHA
                ]
                if exact_rows:
                    hit["target_artifact_row"] = exact_rows[0]
                elif rows:
                    hit["target_candidate_rows"] = [dict(row) for row in rows]
                row = conn.execute(
                    "SELECT artifact_id,artifact_type,content_sha256,length(semantic_payload_json) AS bytes "
                    "FROM artifacts WHERE artifact_id=?",
                    (OWNER_GATE_ID,),
                ).fetchone()
                if row:
                    hit["owner_gate_row"] = dict(row)

                # Find refs in payload bytes/text without printing payload.
                for needle, label in ((TARGET_ID, "TARGET_ID"), (OWNER_GATE_ID, "OWNER_GATE_ID")):
                    try:
                        rows = conn.execute(
                            "SELECT artifact_id,artifact_type,content_sha256 "
                            "FROM artifacts WHERE CAST(semantic_payload_json AS TEXT) LIKE ?",
                            (f"%{needle}%",),
                        ).fetchall()
                        for row in rows:
                            hit["payload_mentions"].append(
                                {"needle": label, **dict(row)}
                            )
                    except sqlite3.Error:
                        pass

        if "artifact_dependencies" in tables:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(artifact_dependencies)")}
            if {"owner_id", "dependency_id", "dependency_digest"} <= cols:
                rows = conn.execute(
                    "SELECT owner_id,dependency_id,dependency_digest "
                    "FROM artifact_dependencies "
                    "WHERE dependency_id=? OR owner_id=? OR dependency_digest=? "
                    "ORDER BY owner_id,dependency_id",
                    (TARGET_ID, TARGET_ID, TARGET_SHA),
                ).fetchall()
                hit["target_dependency_rows"] = [dict(row) for row in rows]

                rows = conn.execute(
                    "SELECT owner_id,dependency_id,dependency_digest "
                    "FROM artifact_dependencies WHERE owner_id=? OR dependency_id=? "
                    "ORDER BY owner_id,dependency_id",
                    (OWNER_GATE_ID, OWNER_GATE_ID),
                ).fetchall()
                hit["owner_gate_dependency_rows"] = [dict(row) for row in rows]

        conn.close()
        conn = None
        after = sha256(path)
        hit["sha256_after"] = after
        if before != after:
            hit["read_only_integrity"] = "FAIL"
        else:
            hit["read_only_integrity"] = "PASS"

        meaningful = (
            hit["target_artifact_row"]
            or hit.get("target_candidate_rows")
            or hit["target_dependency_rows"]
            or hit["owner_gate_row"]
            or hit["owner_gate_dependency_rows"]
            or hit["payload_mentions"]
        )
        return hit if meaningful else None
    except (sqlite3.Error, OSError, PermissionError):
        return None
    finally:
        if conn is not None:
            conn.close()


def git_search():
    result = {}
    try:
        cp = subprocess.run(
            ["git", "-C", str(REPO), "grep", "-n", "-F", TARGET_SHA, "--", "."],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60,
        )
        result["worktree_grep_rc"] = cp.returncode
        result["worktree_grep"] = cp.stdout.splitlines()[:100]
    except Exception as exc:
        result["worktree_grep_error"] = type(exc).__name__

    try:
        cp = subprocess.run(
            ["git", "-C", str(REPO), "log", "--all", "--oneline", "-S", TARGET_SHA],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120,
        )
        result["history_pickaxe_rc"] = cp.returncode
        result["history_pickaxe"] = cp.stdout.splitlines()[:100]
    except Exception as exc:
        result["history_pickaxe_error"] = type(exc).__name__
    return result


def main() -> int:
    print("FORENSICS_TOOL_VERSION=1.1")
    print(f"FORENSICS_TARGET_ID={TARGET_ID}")
    print("FORENSICS_REFERENCE_SCAN=EXACT_TTL_PROOF_ONLY")
    print(f"FORENSICS_ROOT={LAB}")
    print("MODE=READ_ONLY")
    print("PRODUCTION_ACTION=NO")
    print("ARTIFACT_WRITE=NO")

    if not LAB.is_dir():
        print("FORENSICS_STATUS=BLOCKED")
        print("BLOCKER=LAB_ROOT_MISSING")
        return 2

    text_hits = []
    sqlite_hits = []
    scanned_files = 0
    scanned_sqlite = 0
    skipped = 0

    # One deterministic walk of the entire lab. Avoid .git object contents as raw
    # filesystem data; git history is queried separately using git itself.
    for root, dirs, files in os.walk(LAB):
        root_path = Path(root)
        dirs[:] = sorted(d for d in dirs if d not in {".git", "__pycache__", ".pytest_cache"})
        for name in sorted(files):
            path = root_path / name
            scanned_files += 1
            suffix = path.suffix.lower()

            if suffix in SQLITE_EXTS:
                scanned_sqlite += 1
                hit = inspect_sqlite(path)
                if hit:
                    sqlite_hits.append(hit)
                continue

            if suffix in TEXT_EXTS:
                hit = inspect_text(path)
                if hit:
                    text_hits.append(hit)
                continue

            # For unknown extensions, do a cheap streaming literal probe if reasonably sized.
            try:
                if path.stat().st_size <= MAX_TEXT_BYTES and contains_bytes(
                    path, (TARGET_ID.encode(), TARGET_SHA.encode(), OWNER_GATE_ID.encode())
                ):
                    text_hits.append({
                        "path": safe_rel(path),
                        "kind": "BINARY_LITERAL_HIT",
                        "target_literal": contains_bytes(path, (TARGET_ID.encode(),)),
                        "target_digest": contains_bytes(path, (TARGET_SHA.encode(),)),
                        "owner_gate_literal": contains_bytes(path, (OWNER_GATE_ID.encode(),)),
                        "artifact_envelope_exact": False,
                        "json_locations": [],
                    })
            except OSError:
                skipped += 1

    git = git_search()

    print(f"FILES_SCANNED={scanned_files}")
    print(f"SQLITE_SCANNED={scanned_sqlite}")
    print(f"TEXT_OR_LITERAL_HIT_COUNT={len(text_hits)}")
    print(f"SQLITE_HIT_COUNT={len(sqlite_hits)}")

    target_envelope_hits = [x for x in text_hits if x.get("artifact_envelope_exact")]
    target_db_rows = [x for x in sqlite_hits if x.get("target_artifact_row")]
    target_any_literal = [x for x in text_hits if x.get("target_literal") or x.get("target_digest")]

    for i, hit in enumerate(text_hits, 1):
        print("TEXT_HIT_" + str(i) + "=" + json.dumps(hit, sort_keys=True, separators=(",", ":")))
    for i, hit in enumerate(sqlite_hits, 1):
        print("SQLITE_HIT_" + str(i) + "=" + json.dumps(hit, sort_keys=True, separators=(",", ":")))

    print("GIT_SEARCH=" + json.dumps(git, sort_keys=True, separators=(",", ":")))

    if target_db_rows or target_envelope_hits:
        print("TARGET_ARTIFACT_RETRIEVABLE=YES")
        print("FORENSICS_STATUS=PASS")
        return 0

    if target_any_literal or any(
        x.get("target_dependency_rows")
        or any(m.get("needle") == "TARGET_ID" for m in x.get("payload_mentions", []))
        for x in sqlite_hits
    ):
        print("TARGET_ARTIFACT_RETRIEVABLE=NO")
        print("TARGET_REFERENCE_ONLY=YES")
        print("FORENSICS_STATUS=PASS")
        return 0

    print("TARGET_ARTIFACT_RETRIEVABLE=NO")
    print("TARGET_REFERENCE_ONLY=NO")
    print("FORENSICS_STATUS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
