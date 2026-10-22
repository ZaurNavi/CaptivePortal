from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

TARGET_GATES = (
    "F-A1", "F-A2", "F-A3", "F-A4", "F-A5",
    "F-B0", "F-B1", "F-B2", "F-B3",
    "F-C1", "F-C2", "F-C3",
    "F-D1",
    "F-E1", "F-E2", "F-E3", "F-E4", "F-E7",
    "F-F1",
)

ENVELOPE_KEYS = {
    "artifact_type",
    "artifact_schema_version",
    "semantic_payload",
    "content_sha256",
    "artifact_id",
}

TEXT_EXTENSIONS = {
    ".json", ".txt", ".md", ".log", ".out", ".patch", ".yaml", ".yml",
}

ARTIFACT_ID_RE = re.compile(
    r"GateResultManifest:v1:sha256:[0-9a-f]{64}"
)


def normalized(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError("non-string key")
            nk = unicodedata.normalize("NFC", key)
            if nk in out:
                raise ValueError("NFC collision")
            out[nk] = normalized(child)
        return out
    if isinstance(value, list):
        return [normalized(v) for v in value]
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if value is None or type(value) in (bool, int):
        return value
    raise ValueError("unsupported JSON value")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        normalized(value),
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def valid_envelope(obj: dict[str, Any]) -> bool:
    if set(obj) != ENVELOPE_KEYS:
        return False
    if obj.get("artifact_schema_version") != 1:
        return False
    artifact_type = obj.get("artifact_type")
    payload = obj.get("semantic_payload")
    digest = obj.get("content_sha256")
    artifact_id = obj.get("artifact_id")
    if not isinstance(artifact_type, str) or not isinstance(payload, dict):
        return False
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        return False
    expected = hashlib.sha256(canonical_bytes({
        "artifact_type": artifact_type,
        "artifact_schema_version": 1,
        "semantic_payload": payload,
    })).hexdigest()
    return digest == expected and artifact_id == f"{artifact_type}:v1:sha256:{expected}"


def walk_json(value: Any, source: Path, exact: list[dict[str, Any]]) -> None:
    if isinstance(value, dict):
        if set(value) == ENVELOPE_KEYS:
            env = value
            if valid_envelope(env):
                exact.append({
                    "source_file": str(source),
                    "artifact_type": env["artifact_type"],
                    "artifact_id": env["artifact_id"],
                    "content_sha256": env["content_sha256"],
                    "semantic_payload": env["semantic_payload"],
                })
            return
        for child in value.values():
            walk_json(child, source, exact)
    elif isinstance(value, list):
        for child in value:
            walk_json(child, source, exact)


def safe_read_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > 100 * 1024 * 1024:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeError):
        return None


def main() -> int:
    args = sys.argv[1:]
    if not args:
        roots = [
            Path(r"C:\CaptivPortal-Lab"),
            Path(r"C:\CaptivPortal-UI-Preview"),
            Path.home() / "Downloads",
        ]
    else:
        roots = [Path(arg) for arg in args]

    roots = [root.resolve() for root in roots if root.exists()]
    if not roots:
        print("ERROR: no scan roots exist")
        return 2

    report_path = Path(r"C:\CaptivPortal-Lab\artifacts\ff6-historical-acceptance-locator.json")
    exact: list[dict[str, Any]] = []
    text_leads: dict[str, list[dict[str, Any]]] = {gate: [] for gate in TARGET_GATES}
    manifest_id_leads: list[dict[str, Any]] = []
    scanned = 0
    skipped_large = 0
    errors: list[dict[str, str]] = []

    excluded_dirs = {
        ".git", ".venv", "venv", "__pycache__", "node_modules",
        ".pytest_cache", ".mypy_cache",
    }

    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in excluded_dirs]
            for filename in filenames:
                path = Path(dirpath) / filename
                if path.resolve() == report_path.resolve():
                    continue
                if path.suffix.lower() not in TEXT_EXTENSIONS:
                    continue
                scanned += 1
                try:
                    if path.stat().st_size > 100 * 1024 * 1024:
                        skipped_large += 1
                        continue
                except OSError as exc:
                    errors.append({"path": str(path), "error": str(exc)})
                    continue

                text = safe_read_text(path)
                if text is None:
                    continue

                if path.suffix.lower() == ".json":
                    try:
                        walk_json(json.loads(text), path, exact)
                    except Exception:
                        pass

                manifest_ids = sorted(set(ARTIFACT_ID_RE.findall(text)))
                if manifest_ids:
                    manifest_id_leads.append({
                        "path": str(path),
                        "manifest_ids": manifest_ids,
                    })

                lower_text = text.lower()
                for gate in TARGET_GATES:
                    if gate.lower() not in lower_text:
                        continue
                    lines = text.splitlines()
                    snippets = []
                    for idx, line in enumerate(lines):
                        if gate.lower() in line.lower():
                            lo = max(0, idx - 3)
                            hi = min(len(lines), idx + 7)
                            snippet = "\n".join(lines[lo:hi])
                            snippets.append(snippet[:4000])
                            if len(snippets) >= 3:
                                break
                    text_leads[gate].append({
                        "path": str(path),
                        "gate_snippets": snippets,
                        "gate_result_manifest_ids_in_file": manifest_ids,
                    })

    exact_by_gate: dict[str, list[dict[str, Any]]] = {gate: [] for gate in TARGET_GATES}
    for row in exact:
        if row["artifact_type"] != "GateResultManifest":
            continue
        payload = row["semantic_payload"]
        gate_id = payload.get("gate_id")
        if gate_id in exact_by_gate:
            exact_by_gate[gate_id].append({
                "artifact_id": row["artifact_id"],
                "content_sha256": row["content_sha256"],
                "status": payload.get("status"),
                "candidate_repository_commit_sha": payload.get("candidate_repository_commit_sha"),
                "candidate_repository_tree_sha": payload.get("candidate_repository_tree_sha"),
                "source_file": row["source_file"],
            })

    for rows in exact_by_gate.values():
        rows.sort(key=lambda r: (r["artifact_id"], r["source_file"]))

    missing_exact = [
        gate for gate in TARGET_GATES
        if not any(row.get("status") == "PASS" for row in exact_by_gate[gate])
    ]

    report = {
        "probe_version": "FF6-historical-acceptance-locator-v1",
        "roots": [str(root) for root in roots],
        "files_scanned": scanned,
        "large_files_skipped": skipped_large,
        "exact_gate_result_manifests": exact_by_gate,
        "missing_exact_pass_gate_ids": missing_exact,
        "textual_gate_leads": text_leads,
        "gate_result_manifest_id_leads": manifest_id_leads,
        "errors": errors,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("=" * 76)
    print("F-F6 HISTORICAL ACCEPTANCE LOCATOR")
    print("=" * 76)
    print("ROOTS=" + " ; ".join(str(root) for root in roots))
    print(f"FILES_SCANNED={scanned}")
    print(f"EXACT_PASS_MANIFESTS_FOUND={sum(any(r.get('status') == 'PASS' for r in rows) for rows in exact_by_gate.values())}")
    print("MISSING_EXACT_PASS_GATE_IDS=" + (",".join(missing_exact) if missing_exact else "NONE"))
    print(f"TEXT_FILES_WITH_MANIFEST_IDS={len(manifest_id_leads)}")
    print(f"REPORT={report_path}")
    print("=" * 76)

    for gate in TARGET_GATES:
        pass_rows = [row for row in exact_by_gate[gate] if row.get("status") == "PASS"]
        print(f"{gate}: EXACT_PASS={len(pass_rows)} TEXT_LEADS={len(text_leads[gate])}")
        for row in pass_rows:
            print(f"  {row['artifact_id']}")
            print(f"  FILE={row['source_file']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
