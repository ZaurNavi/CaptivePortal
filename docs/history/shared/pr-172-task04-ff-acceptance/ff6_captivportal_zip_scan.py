from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import unicodedata
import zipfile
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
    ".json", ".txt", ".md", ".log", ".out", ".patch", ".yaml", ".yml", ".csv",
}

MANIFEST_ID_RE = re.compile(r"GateResultManifest:v1:sha256:[0-9a-f]{64}")
MAX_ENTRY_BYTES = 50 * 1024 * 1024
MAX_NESTED_ZIP_BYTES = 100 * 1024 * 1024
MAX_DEPTH = 3


def normalized(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError("non-string JSON key")
            nk = unicodedata.normalize("NFC", key)
            if nk in out:
                raise ValueError("NFC key collision")
            out[nk] = normalized(child)
        return out
    if isinstance(value, list):
        return [normalized(v) for v in value]
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if value is None or type(value) in (bool, int):
        return value
    raise ValueError("unsupported JSON value")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        normalized(value),
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def envelope_identity_valid(obj: dict[str, Any]) -> bool:
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
    digest_input = canonical_json_bytes({
        "artifact_type": artifact_type,
        "artifact_schema_version": 1,
        "semantic_payload": payload,
    })
    computed = hashlib.sha256(digest_input).hexdigest()
    return digest == computed and artifact_id == f"{artifact_type}:v1:sha256:{computed}"


def walk_json(value: Any, source: str, exact: list[dict[str, Any]]) -> None:
    if isinstance(value, dict):
        if set(value) == ENVELOPE_KEYS:
            if envelope_identity_valid(value):
                exact.append({
                    "source": source,
                    "artifact_type": value["artifact_type"],
                    "artifact_id": value["artifact_id"],
                    "content_sha256": value["content_sha256"],
                    "semantic_payload": value["semantic_payload"],
                })
            return
        for child in value.values():
            walk_json(child, source, exact)
    elif isinstance(value, list):
        for child in value:
            walk_json(child, source, exact)


def text_snippets(text: str, gate: str) -> list[str]:
    lines = text.splitlines()
    out = []
    needle = gate.lower()
    for idx, line in enumerate(lines):
        if needle not in line.lower():
            continue
        lo = max(0, idx - 3)
        hi = min(len(lines), idx + 7)
        out.append("\n".join(lines[lo:hi])[:4000])
        if len(out) >= 3:
            break
    return out


def process_text(
    data: bytes,
    source: str,
    suffix: str,
    exact: list[dict[str, Any]],
    text_leads: dict[str, list[dict[str, Any]]],
    manifest_id_leads: list[dict[str, Any]],
) -> None:
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:
        return

    if suffix == ".json":
        try:
            walk_json(json.loads(text), source, exact)
        except Exception:
            pass

    ids = sorted(set(MANIFEST_ID_RE.findall(text)))
    if ids:
        manifest_id_leads.append({"source": source, "manifest_ids": ids})

    low = text.lower()
    for gate in TARGET_GATES:
        if gate.lower() not in low:
            continue
        text_leads[gate].append({
            "source": source,
            "gate_snippets": text_snippets(text, gate),
            "gate_result_manifest_ids_in_entry": ids,
        })


def scan_zip_bytes(
    zip_bytes: bytes,
    archive_label: str,
    depth: int,
    exact: list[dict[str, Any]],
    text_leads: dict[str, list[dict[str, Any]]],
    manifest_id_leads: list[dict[str, Any]],
    stats: dict[str, int],
    errors: list[dict[str, str]],
) -> None:
    if depth > MAX_DEPTH:
        stats["nested_depth_skipped"] += 1
        return

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                stats["entries_seen"] += 1
                name = info.filename
                source = f"{archive_label}!/{name}"
                suffix = Path(name).suffix.lower()

                if info.file_size > MAX_ENTRY_BYTES and suffix != ".zip":
                    stats["large_entries_skipped"] += 1
                    continue

                if suffix == ".zip":
                    if info.file_size > MAX_NESTED_ZIP_BYTES:
                        stats["large_nested_zips_skipped"] += 1
                        continue
                    try:
                        nested = zf.read(info)
                        stats["nested_zips_seen"] += 1
                        scan_zip_bytes(
                            nested, source, depth + 1,
                            exact, text_leads, manifest_id_leads, stats, errors,
                        )
                    except Exception as exc:
                        errors.append({"source": source, "error": f"{type(exc).__name__}: {exc}"})
                    continue

                if suffix not in TEXT_EXTENSIONS:
                    continue

                try:
                    data = zf.read(info)
                    stats["text_entries_scanned"] += 1
                    process_text(
                        data, source, suffix,
                        exact, text_leads, manifest_id_leads,
                    )
                except Exception as exc:
                    errors.append({"source": source, "error": f"{type(exc).__name__}: {exc}"})
    except Exception as exc:
        errors.append({"source": archive_label, "error": f"{type(exc).__name__}: {exc}"})


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"C:\Users\Zaur Navi\Downloads")
    out = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else Path(r"C:\CaptivPortal-Lab\artifacts\ff6-captivportal-zip-scan.json")
    )

    if not root.is_dir():
        print(f"ERROR: directory not found: {root}")
        return 2

    candidates = sorted(
        {
            p for p in root.rglob("*.zip")
            if (
                "captivportal" in p.name.lower()
                or "device-fingerprint" in p.name.lower()
                or "device_fingerprint" in p.name.lower()
            )
        },
        key=lambda p: str(p).lower(),
    )

    exact: list[dict[str, Any]] = []
    text_leads: dict[str, list[dict[str, Any]]] = {gate: [] for gate in TARGET_GATES}
    manifest_id_leads: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    stats = {
        "archives_seen": 0,
        "entries_seen": 0,
        "text_entries_scanned": 0,
        "nested_zips_seen": 0,
        "large_entries_skipped": 0,
        "large_nested_zips_skipped": 0,
        "nested_depth_skipped": 0,
    }

    for path in candidates:
        stats["archives_seen"] += 1
        try:
            data = path.read_bytes()
            scan_zip_bytes(
                data, str(path), 0,
                exact, text_leads, manifest_id_leads, stats, errors,
            )
        except Exception as exc:
            errors.append({"source": str(path), "error": f"{type(exc).__name__}: {exc}"})

    exact_by_gate: dict[str, list[dict[str, Any]]] = {gate: [] for gate in TARGET_GATES}
    for row in exact:
        if row["artifact_type"] != "GateResultManifest":
            continue
        payload = row["semantic_payload"]
        gate = payload.get("gate_id")
        if gate not in exact_by_gate:
            continue
        exact_by_gate[gate].append({
            "artifact_id": row["artifact_id"],
            "content_sha256": row["content_sha256"],
            "status": payload.get("status"),
            "candidate_repository_commit_sha": payload.get("candidate_repository_commit_sha"),
            "candidate_repository_tree_sha": payload.get("candidate_repository_tree_sha"),
            "source": row["source"],
        })

    for rows in exact_by_gate.values():
        rows.sort(key=lambda x: (x["artifact_id"], x["source"]))

    missing = [
        gate for gate in TARGET_GATES
        if not any(row.get("status") == "PASS" for row in exact_by_gate[gate])
    ]

    report = {
        "scanner_version": "FF6-CaptivPortal-zip-scan-v1",
        "root": str(root),
        "candidate_archives": [str(p) for p in candidates],
        "stats": stats,
        "exact_gate_result_manifests": exact_by_gate,
        "missing_exact_pass_gate_ids": missing,
        "textual_gate_leads": text_leads,
        "manifest_id_leads": manifest_id_leads,
        "errors": errors,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("=" * 76)
    print("F-F6 CAPTIVPORTAL ZIP SCAN")
    print("=" * 76)
    print(f"ROOT={root}")
    print(f"CANDIDATE_ARCHIVES={len(candidates)}")
    print(f"ARCHIVES_SEEN={stats['archives_seen']}")
    print(f"ENTRIES_SEEN={stats['entries_seen']}")
    print(f"TEXT_ENTRIES_SCANNED={stats['text_entries_scanned']}")
    print(f"NESTED_ZIPS_SEEN={stats['nested_zips_seen']}")
    print(f"EXACT_PASS_MANIFESTS_FOUND={sum(any(r.get('status') == 'PASS' for r in rows) for rows in exact_by_gate.values())}")
    print("MISSING_EXACT_PASS_GATE_IDS=" + (",".join(missing) if missing else "NONE"))
    print(f"TEXT_ENTRIES_WITH_MANIFEST_IDS={len(manifest_id_leads)}")
    print(f"ERRORS={len(errors)}")
    print(f"REPORT={out}")
    print("=" * 76)

    for gate in TARGET_GATES:
        passes = [row for row in exact_by_gate[gate] if row.get("status") == "PASS"]
        print(f"{gate}: EXACT_PASS={len(passes)} TEXT_LEADS={len(text_leads[gate])}")
        for row in passes:
            print(f"  {row['artifact_id']}")
            print(f"  SOURCE={row['source']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
