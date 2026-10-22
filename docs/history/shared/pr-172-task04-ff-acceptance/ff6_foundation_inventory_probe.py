from __future__ import annotations

import hashlib
import json
import sys
import unicodedata
from pathlib import Path
from typing import Any

MANDATORY_PRE_FF6_GATES = (
    "F-A1", "F-A2", "F-A3", "F-A4", "F-A5",
    "F-B0", "F-B1", "F-B2", "F-B3",
    "F-C1", "F-C2", "F-C3",
    "F-D1",
    "F-E1", "F-E2", "F-E3", "F-E4", "F-E5", "F-E6", "F-E7",
    "F-F1", "F-F2", "F-F3", "F-F4", "F-F5",
)

ENVELOPE_KEYS = {
    "artifact_type",
    "artifact_schema_version",
    "semantic_payload",
    "content_sha256",
    "artifact_id",
}


def normalized(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError("non-string JSON key")
            nk = unicodedata.normalize("NFC", key)
            if nk in result:
                raise ValueError("NFC key collision")
            result[nk] = normalized(child)
        return result
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
    if not isinstance(digest, str) or len(digest) != 64:
        return False
    digest_input = canonical_json_bytes({
        "artifact_type": artifact_type,
        "artifact_schema_version": 1,
        "semantic_payload": payload,
    })
    computed = hashlib.sha256(digest_input).hexdigest()
    return digest == computed and artifact_id == f"{artifact_type}:v1:sha256:{computed}"


def walk(value: Any, source_file: Path, found: list[dict[str, Any]]) -> None:
    if isinstance(value, dict):
        if set(value) == ENVELOPE_KEYS:
            found.append({
                "source_file": str(source_file),
                "envelope": value,
                "identity_valid": envelope_identity_valid(value),
            })
            return
        for child in value.values():
            walk(child, source_file, found)
    elif isinstance(value, list):
        for child in value:
            walk(child, source_file, found)


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"C:\CaptivPortal-Lab\artifacts")
    out = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else root / "ff6-foundation-inventory-probe.json"
    )

    if not root.is_dir():
        print(f"ERROR: directory not found: {root}")
        return 2

    found: list[dict[str, Any]] = []
    unreadable: list[dict[str, str]] = []

    for path in sorted(root.rglob("*.json"), key=lambda p: str(p).lower()):
        if path.resolve() == out.resolve():
            continue
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
            walk(obj, path, found)
        except Exception as exc:
            unreadable.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})

    by_id: dict[str, dict[str, Any]] = {}
    duplicate_locations: dict[str, list[str]] = {}
    invalid_identity: list[dict[str, str]] = []

    for row in found:
        env = row["envelope"]
        aid = env["artifact_id"]
        if not row["identity_valid"]:
            invalid_identity.append({
                "artifact_id": aid,
                "source_file": row["source_file"],
            })
            continue
        if aid in by_id:
            duplicate_locations.setdefault(aid, [by_id[aid]["source_file"]]).append(row["source_file"])
        else:
            by_id[aid] = row

    gates: dict[str, list[dict[str, Any]]] = {}
    for aid, row in by_id.items():
        env = row["envelope"]
        if env["artifact_type"] != "GateResultManifest":
            continue
        payload = env["semantic_payload"]
        gate_id = payload.get("gate_id")
        if not isinstance(gate_id, str):
            continue
        gates.setdefault(gate_id, []).append({
            "artifact_id": aid,
            "content_sha256": env["content_sha256"],
            "status": payload.get("status"),
            "candidate_repository_commit_sha": payload.get("candidate_repository_commit_sha"),
            "candidate_repository_tree_sha": payload.get("candidate_repository_tree_sha"),
            "input_artifact_refs": payload.get("input_artifact_refs", []),
            "output_artifact_refs": payload.get("output_artifact_refs", []),
            "source_file": row["source_file"],
        })

    for rows in gates.values():
        rows.sort(key=lambda r: (r["artifact_id"], r["source_file"]))

    missing_gate_ids = [gate for gate in MANDATORY_PRE_FF6_GATES if gate not in gates]
    non_pass_gate_ids = [
        gate for gate in MANDATORY_PRE_FF6_GATES
        if gate in gates and not any(row["status"] == "PASS" for row in gates[gate])
    ]
    ambiguous_pass_gate_ids = [
        gate for gate in MANDATORY_PRE_FF6_GATES
        if sum(row["status"] == "PASS" for row in gates.get(gate, ())) > 1
    ]

    referenced_ids: set[str] = set()
    for rows in gates.values():
        for row in rows:
            if row["status"] != "PASS":
                continue
            for ref in list(row["input_artifact_refs"]) + list(row["output_artifact_refs"]):
                if isinstance(ref, dict) and isinstance(ref.get("artifact_id"), str):
                    referenced_ids.add(ref["artifact_id"])

    missing_referenced_envelopes = sorted(aid for aid in referenced_ids if aid not in by_id)

    artifact_type_counts: dict[str, int] = {}
    for row in by_id.values():
        at = row["envelope"]["artifact_type"]
        artifact_type_counts[at] = artifact_type_counts.get(at, 0) + 1

    report = {
        "probe_version": "FF6-foundation-inventory-probe-v1",
        "scan_root": str(root),
        "json_files_scanned": sum(1 for _ in root.rglob("*.json")),
        "valid_unique_artifact_envelopes": len(by_id),
        "artifact_type_counts": dict(sorted(artifact_type_counts.items())),
        "mandatory_pre_ff6_gate_ids": list(MANDATORY_PRE_FF6_GATES),
        "missing_gate_ids": missing_gate_ids,
        "non_pass_gate_ids": non_pass_gate_ids,
        "ambiguous_pass_gate_ids": ambiguous_pass_gate_ids,
        "gate_result_manifests": {k: v for k, v in sorted(gates.items())},
        "missing_referenced_artifact_envelopes": missing_referenced_envelopes,
        "invalid_identity_envelopes": invalid_identity,
        "duplicate_artifact_locations": duplicate_locations,
        "unreadable_json_files": unreadable,
        "all_artifacts": [
            {
                "artifact_id": aid,
                "artifact_type": row["envelope"]["artifact_type"],
                "content_sha256": row["envelope"]["content_sha256"],
                "source_file": row["source_file"],
            }
            for aid, row in sorted(by_id.items())
        ],
    }

    out.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("=" * 72)
    print("F-F6 FOUNDATION INVENTORY PROBE")
    print("=" * 72)
    print(f"SCAN_ROOT={root}")
    print(f"VALID_UNIQUE_ARTIFACT_ENVELOPES={len(by_id)}")
    print(f"GATE_IDS_FOUND={len(gates)}")
    print(f"MISSING_MANDATORY_GATE_IDS={','.join(missing_gate_ids) if missing_gate_ids else 'NONE'}")
    print(f"NON_PASS_MANDATORY_GATE_IDS={','.join(non_pass_gate_ids) if non_pass_gate_ids else 'NONE'}")
    print(f"AMBIGUOUS_PASS_GATE_IDS={','.join(ambiguous_pass_gate_ids) if ambiguous_pass_gate_ids else 'NONE'}")
    print(f"MISSING_REFERENCED_ARTIFACT_ENVELOPES={len(missing_referenced_envelopes)}")
    print(f"INVALID_IDENTITY_ENVELOPES={len(invalid_identity)}")
    print(f"UNREADABLE_JSON_FILES={len(unreadable)}")
    print(f"REPORT={out}")
    print("=" * 72)

    for gate in MANDATORY_PRE_FF6_GATES:
        rows = gates.get(gate, [])
        passes = [r for r in rows if r["status"] == "PASS"]
        print(f"{gate}: PASS_MANIFESTS={len(passes)}")
        for row in passes:
            print(f"  {row['artifact_id']}")
            print(f"  FILE={row['source_file']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
