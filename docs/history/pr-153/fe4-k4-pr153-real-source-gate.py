#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

EXPECTED_HEAD = "868767eefe95e87654483067f8db59587e2d1882"
EXPECTED_TREE = "439c666b0811b96f78cd4526c12abcaceaf70865"

EXPECTED = {
    "MA-L": {
        "filename": "oui.csv",
        "rows": 40217,
        "sha256": "95ea96dc4d13b25dba653ad603379ea4c40a8a2f01f8168d3375136375da7092",
    },
    "MA-M": {
        "filename": "mam.csv",
        "rows": 6598,
        "sha256": "baa37a78b3cc58c6160e3064121428455b45fe0eb3fcadb1c92885354f12be13",
    },
    "MA-S": {
        "filename": "oui36.csv",
        "rows": 7197,
        "sha256": "7296daa2bba47a0a37475c1e1082e16c15ab876bddda2a549f91186cedec4e17",
    },
}
EXPECTED_TOTAL = 54012
EXPECTED_BUNDLE = "eb81bb97240fb7754659c33c13a9139583f7f505e38bc6618f9eef51b3878ae5"
EXPECTED_AMBIGUOUS_PREFIX_GROUPS = 2

def fail(message: str) -> None:
    raise SystemExit(f"F-E4 REAL-SOURCE GATE = FAIL\n{message}")

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def run_git(repo: Path, *args: str) -> str:
    import subprocess
    cp = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if cp.returncode != 0:
        fail(f"git {' '.join(args)} failed: {cp.stderr.strip()}")
    return cp.stdout.strip()

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="Local CaptivePortal repo checkout")
    ap.add_argument("--source-dir", required=True, help="Directory with oui.csv/mam.csv/oui36.csv")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    source_dir = Path(args.source_dir).resolve()

    if not (repo / ".git").exists():
        fail(f"Not a Git repository: {repo}")

    head = run_git(repo, "rev-parse", "HEAD")
    tree = run_git(repo, "rev-parse", "HEAD^{tree}")
    if head != EXPECTED_HEAD:
        fail(f"Wrong HEAD: {head}; expected PR head {EXPECTED_HEAD}")
    if tree != EXPECTED_TREE:
        fail(f"Wrong tree: {tree}; expected {EXPECTED_TREE}")

    sys.path.insert(0, str(repo))
    try:
        from app.device_fingerprint.k4_ieee_import import (
            compute_ieee_k4_source_bundle_sha256,
            import_ieee_k4_bytes,
            match_k4_records,
        )
    except Exception as exc:
        fail(f"Cannot import PR-head K4 implementation: {exc!r}")

    blobs: dict[str, bytes] = {}
    for family in ("MA-L", "MA-M", "MA-S"):
        meta = EXPECTED[family]
        path = source_dir / meta["filename"]
        if not path.is_file():
            fail(f"Missing {family} source: {path}")
        data = path.read_bytes()
        digest = sha256(data)
        if digest != meta["sha256"]:
            fail(
                f"{family} SHA mismatch: {digest}; expected {meta['sha256']}. "
                "Do not redownload for this gate."
            )
        blobs[family] = data

    bundle = compute_ieee_k4_source_bundle_sha256(
        blobs["MA-L"], blobs["MA-M"], blobs["MA-S"]
    )
    if bundle != EXPECTED_BUNDLE:
        fail(f"Bundle SHA mismatch: {bundle}; expected {EXPECTED_BUNDLE}")

    # The importer validates only the ref shape/type at this gate.
    # We intentionally use a deterministic non-resolved placeholder because
    # F-E5 owns the final external provenance/freshness binding.
    dummy_digest = "0" * 64
    provenance_ref = {
        "artifact_id": f"KnowledgeProvenanceManifest:v1:sha256:{dummy_digest}",
        "content_sha256": dummy_digest,
    }

    record_set = import_ieee_k4_bytes(
        blobs["MA-L"],
        blobs["MA-M"],
        blobs["MA-S"],
        knowledge_provenance=provenance_ref,
    )
    payload = record_set.semantic_payload
    records = payload["records"]

    counts = collections.Counter(r["registry_family"] for r in records)
    for family in ("MA-L", "MA-M", "MA-S"):
        expected_rows = EXPECTED[family]["rows"]
        if counts[family] != expected_rows:
            fail(
                f"{family} canonical record count={counts[family]}; "
                f"expected {expected_rows}"
            )

    if len(records) != EXPECTED_TOTAL:
        fail(f"Total canonical records={len(records)}; expected {EXPECTED_TOTAL}")

    if any(r["manufacturer_mapping"] is not None for r in records):
        fail("At least one imported record has non-null manufacturer_mapping")

    # Different Private assignments must never collapse to one organization identity.
    private_records = [r for r in records if r["assignment_org_label"] == "Private"]
    private_ids = {r["assignment_org_id"] for r in private_records}
    if len(private_ids) != len(private_records):
        fail(
            "Private assignment_org_id collision: distinct Private assignments "
            "were collapsed"
        )

    # Count real ambiguous prefix groups after semantic dedup.
    grouped: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
    for r in records:
        grouped[(r["registry_family"], r["prefix_hex"])].append(r)

    ambiguous = {
        key: rows
        for key, rows in grouped.items()
        if len({r["assignment_org_id"] for r in rows}) > 1
    }
    if len(ambiguous) != EXPECTED_AMBIGUOUS_PREFIX_GROUPS:
        fail(
            f"Ambiguous prefix groups={len(ambiguous)}; "
            f"expected {EXPECTED_AMBIGUOUS_PREFIX_GROUPS}"
        )

    # Known official duplicate prefix must preserve every distinct assignment org.
    key = ("MA-L", "080030")
    expected_080030 = grouped.get(key, [])
    if len({r["assignment_org_id"] for r in expected_080030}) < 2:
        fail("Expected official MA-L duplicate prefix 080030 was not preserved")

    lookup_080030 = match_k4_records(record_set, "08:00:30:00:00:00")
    expected_ids = sorted(r["canonical_record_id"] for r in expected_080030)
    actual_ids = sorted(r["canonical_record_id"] for r in lookup_080030)
    if actual_ids != expected_ids:
        fail("080030 lookup did not return every preserved assignment-org record")

    # U/L gate on same low bytes: 0a sets the locally administered bit.
    if match_k4_records(record_set, "0a:00:30:00:00:00") != ():
        fail("Locally administered MAC produced a K4 match")

    result = {
        "gate": "F-E4_REAL_SOURCE_PR_HEAD_V1",
        "result": "PASS",
        "pr_head": head,
        "pr_tree": tree,
        "source_sha256": {
            family: EXPECTED[family]["sha256"]
            for family in ("MA-L", "MA-M", "MA-S")
        },
        "source_bundle_sha256": bundle,
        "canonical_records": len(records),
        "records_by_registry": dict(counts),
        "ambiguous_prefix_groups": len(ambiguous),
        "ambiguous_prefixes": [
            {
                "registry_family": family,
                "prefix_hex": prefix,
                "assignment_org_count": len({
                    r["assignment_org_id"] for r in rows
                }),
                "assignment_org_labels": sorted({
                    r["assignment_org_label"] for r in rows
                }),
            }
            for (family, prefix), rows in sorted(ambiguous.items())
        ],
        "private_record_count": len(private_records),
        "private_assignment_org_id_count": len(private_ids),
        "manufacturer_mapping_non_null_count": 0,
        "lookup_080030_record_count": len(lookup_080030),
        "locally_administered_lookup_record_count": 0,
    }

    out = source_dir / "fe4-k4-pr153-real-source-gate.json"
    out.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )

    print("F-E4 REAL-SOURCE GATE = PASS")
    print(f"PR_HEAD={head}")
    print(f"PR_TREE={tree}")
    print(f"MA-L={counts['MA-L']}")
    print(f"MA-M={counts['MA-M']}")
    print(f"MA-S={counts['MA-S']}")
    print(f"TOTAL={len(records)}")
    print(f"BUNDLE_SHA256={bundle}")
    print(f"AMBIGUOUS_PREFIX_GROUPS={len(ambiguous)}")
    print(f"PRIVATE_RECORDS={len(private_records)}")
    print(f"LOOKUP_080030_RECORDS={len(lookup_080030)}")
    print("MANUFACTURER_MAPPING_NON_NULL=0")
    print("LOCALLY_ADMINISTERED_MATCHES=0")
    print(f"REPORT={out}")

if __name__ == "__main__":
    main()
