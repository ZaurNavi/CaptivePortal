#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SOURCES = {
    "MA-L": {
        "url": "https://standards-oui.ieee.org/oui/oui.csv",
        "filename": "oui.csv",
        "width": 6,
        "bits": 24,
    },
    "MA-M": {
        "url": "https://standards-oui.ieee.org/oui28/mam.csv",
        "filename": "mam.csv",
        "width": 7,
        "bits": 28,
    },
    "MA-S": {
        "url": "https://standards-oui.ieee.org/oui36/oui36.csv",
        "filename": "oui36.csv",
        "width": 9,
        "bits": 36,
    },
}
HEADER = ["Registry", "Assignment", "Organization Name", "Organization Address"]
HEX_RE = re.compile(r"^[0-9A-Fa-f]+$")

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def canonical_json_bytes(value) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")

def download(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "CaptivPortal-FE4-IEEE-Audit/1.1 (+Owner-authorized research)",
            "Accept": "text/csv,text/plain;q=0.9,*/*;q=0.1",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()

def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)

def parse_registry(registry: str, meta: dict, data: bytes):
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SystemExit(f"{registry}: not UTF-8: {exc}")
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        header = next(reader)
    except StopIteration:
        raise SystemExit(f"{registry}: empty CSV")
    if header != HEADER:
        raise SystemExit(f"{registry}: header mismatch: {header!r}")

    source_records = []
    malformed = []
    private_count = 0
    first_octet_ul_set = 0

    # IEEE public listings can contain duplicate Assignment values.
    # Preserve all distinct assignment organizations for one prefix.
    # Collapse only exact K4-semantic repetition:
    # same prefix + same exact organization label.
    by_prefix = {}

    for lineno, row in enumerate(reader, 2):
        if len(row) != 4:
            malformed.append({"line": lineno, "reason": "column_count", "row": row})
            continue
        reg, assignment, org_name, org_address = row
        if reg != registry:
            malformed.append({"line": lineno, "reason": "registry", "value": reg})
            continue
        if len(assignment) != meta["width"] or HEX_RE.fullmatch(assignment) is None:
            malformed.append({"line": lineno, "reason": "assignment", "value": assignment})
            continue
        if not org_name:
            malformed.append({"line": lineno, "reason": "empty_org_name"})
            continue

        prefix = assignment.lower()
        org_name_nfc = nfc(org_name)
        org_id_payload = {
            "source_family": "ieee_ra_public_listing",
            "organization_name": org_name_nfc,
        }
        org_id = (
            "ieee-assignment-org:v1:sha256:"
            + sha256(canonical_json_bytes(org_id_payload))
        )
        if org_name_nfc == "Private":
            private_count += 1

        first_octet = int(prefix[:2], 16)
        if first_octet & 0x02:
            first_octet_ul_set += 1

        record = {
            "registry_family": registry,
            "prefix_hex": prefix,
            "prefix_length_bits": meta["bits"],
            "assignment_org_id": org_id,
            "assignment_org_label": org_name_nfc,
            "source_line": lineno,
            "manufacturer_mapping": None,
        }
        source_records.append(record)
        by_prefix.setdefault(prefix, []).append(record)

    if malformed:
        raise SystemExit(
            f"{registry}: malformed rows present; first={malformed[0]!r}, total={len(malformed)}"
        )

    semantic_records = []
    duplicate_prefix_groups = []
    exact_semantic_duplicate_rows = 0
    ambiguous_prefix_groups = []

    for prefix, rows in sorted(by_prefix.items()):
        by_org = {}
        for row in rows:
            by_org.setdefault(
                (row["assignment_org_id"], row["assignment_org_label"]),
                []
            ).append(row)

        for (_org_id, _org_label), same_org_rows in sorted(by_org.items()):
            semantic_records.append(same_org_rows[0])
            exact_semantic_duplicate_rows += max(0, len(same_org_rows) - 1)

        if len(rows) > 1:
            duplicate_prefix_groups.append({
                "prefix_hex": prefix,
                "source_row_count": len(rows),
                "distinct_assignment_org_count": len(by_org),
                "organizations": sorted({
                    row["assignment_org_label"] for row in rows
                }),
                "source_lines": [row["source_line"] for row in rows],
            })
        if len(by_org) > 1:
            ambiguous_prefix_groups.append({
                "prefix_hex": prefix,
                "distinct_assignment_org_count": len(by_org),
                "organizations": sorted({
                    row["assignment_org_label"] for row in rows
                }),
                "source_lines": [row["source_line"] for row in rows],
            })

    summary = {
        "source_row_count": len(source_records),
        "semantic_record_count": len(semantic_records),
        "private_row_count": private_count,
        "source_prefixes_with_ul_bit_set": first_octet_ul_set,
        "duplicate_prefix_group_count": len(duplicate_prefix_groups),
        "exact_semantic_duplicate_rows_collapsed": exact_semantic_duplicate_rows,
        "ambiguous_prefix_group_count": len(ambiguous_prefix_groups),
        "duplicate_prefix_groups": duplicate_prefix_groups,
        "ambiguous_prefix_groups": ambiguous_prefix_groups,
    }
    return source_records, semantic_records, summary

def is_locally_administered(mac_hex: str) -> bool:
    return bool(int(mac_hex[:2], 16) & 0x02)

def lookup(mac_hex: str, indexes):
    mac_hex = mac_hex.lower()
    if not re.fullmatch(r"[0-9a-f]{12}", mac_hex):
        raise ValueError("MAC must be 12 lowercase hex characters")
    if is_locally_administered(mac_hex):
        return {
            "eligible": False,
            "reason": "locally_administered",
            "matched_registry": None,
            "matches": [],
        }

    # Longest prefix chooses the registry/prefix length, never one arbitrary row.
    # At the selected prefix preserve every distinct assignment-org outcome.
    for registry, width in (("MA-S", 9), ("MA-M", 7), ("MA-L", 6)):
        matches = indexes[registry].get(mac_hex[:width], [])
        if matches:
            return {
                "eligible": True,
                "reason": None,
                "matched_registry": registry,
                "matches": matches,
            }

    return {
        "eligible": True,
        "reason": None,
        "matched_registry": None,
        "matches": [],
    }

def sample_mac_from_prefix(prefix: str) -> str:
    return prefix + "0" * (12 - len(prefix))

def set_ul_bit(mac_hex: str) -> str:
    first = int(mac_hex[:2], 16) | 0x02
    return f"{first:02x}" + mac_hex[2:]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--dir", default="ieee-k4-source",
        help="Directory for official IEEE CSV files and audit output"
    )
    ap.add_argument(
        "--no-download", action="store_true",
        help="Audit existing oui.csv/mam.csv/oui36.csv without downloading"
    )
    args = ap.parse_args()

    root = Path(args.dir)
    root.mkdir(parents=True, exist_ok=True)

    source_files = {}
    file_results = {}
    all_records = {}

    for registry, meta in SOURCES.items():
        path = root / meta["filename"]
        if not args.no_download:
            print(f"DOWNLOAD {registry}: {meta['url']}")
            data = download(meta["url"])
            path.write_bytes(data)
        else:
            data = path.read_bytes()

        source_files[registry] = data
        source_records, semantic_records, summary = parse_registry(registry, meta, data)
        all_records[registry] = {
            "source_records": source_records,
            "semantic_records": semantic_records,
        }
        file_results[registry] = {
            "url": meta["url"],
            "filename": meta["filename"],
            "size_bytes": len(data),
            "sha256": sha256(data),
            "registry_family": registry,
            "prefix_length_bits": meta["bits"],
            "assignment_width_hex": meta["width"],
            **summary,
        }

    # Composite immutable source-family identity: fixed family order + exact file digests.
    bundle_manifest = {
        "bundle_identity_version": "ieee_ra_k4_source_bundle_v1",
        "members": [
            {
                "registry_family": registry,
                "filename": SOURCES[registry]["filename"],
                "source_url": SOURCES[registry]["url"],
                "sha256": file_results[registry]["sha256"],
                "size_bytes": file_results[registry]["size_bytes"],
            }
            for registry in ("MA-L", "MA-M", "MA-S")
        ],
    }
    bundle_sha256 = sha256(canonical_json_bytes(bundle_manifest))

    indexes = {}
    for reg, record_sets in all_records.items():
        index = {}
        for record in record_sets["semantic_records"]:
            index.setdefault(record["prefix_hex"], []).append(record)
        for prefix in index:
            index[prefix] = sorted(
                index[prefix],
                key=lambda row: (
                    row["assignment_org_id"],
                    row["assignment_org_label"],
                ),
            )
        indexes[reg] = index

    ma_l = indexes["MA-L"]
    ma_m = indexes["MA-M"]
    ma_s = indexes["MA-S"]

    nesting = {
        "ma_m_nested_under_ma_l": sum(1 for p in ma_m if p[:6] in ma_l),
        "ma_s_nested_under_ma_m": sum(1 for p in ma_s if p[:7] in ma_m),
        "ma_s_nested_under_ma_l": sum(1 for p in ma_s if p[:6] in ma_l),
    }

    fixtures = []

    # Longest-prefix proof: prefer a real MA-S nested under MA-M, else under MA-L.
    nested_s = next((p for p in ma_s if p[:7] in ma_m), None)
    if nested_s is not None:
        mac = sample_mac_from_prefix(nested_s)
        result = lookup(mac, indexes)
        fixtures.append({
            "fixture": "ma_s_over_ma_m",
            "mac": mac,
            "expected_registry": "MA-S",
            "actual_registry": result["matched_registry"],
            "assignment_org_count": len(result["matches"]),
            "pass": result["matched_registry"] == "MA-S" and bool(result["matches"]),
        })

    nested_m = next((p for p in ma_m if p[:6] in ma_l), None)
    if nested_m is not None:
        mac = sample_mac_from_prefix(nested_m)
        result = lookup(mac, indexes)
        fixtures.append({
            "fixture": "ma_m_over_ma_l",
            "mac": mac,
            "expected_registry": "MA-M",
            "actual_registry": result["matched_registry"],
            "assignment_org_count": len(result["matches"]),
            "pass": result["matched_registry"] == "MA-M" and bool(result["matches"]),
        })

    # Plain MA-L fixture when possible.
    ma_m_parent6 = {prefix[:6] for prefix in ma_m}
    ma_s_parent6 = {prefix[:6] for prefix in ma_s}
    plain_l = next(
        (prefix for prefix in ma_l
         if prefix not in ma_m_parent6
         and prefix not in ma_s_parent6
         and (int(prefix[:2], 16) & 0x02) == 0),
        None,
    )
    if plain_l is not None:
        mac = sample_mac_from_prefix(plain_l)
        result = lookup(mac, indexes)
        fixtures.append({
            "fixture": "ma_l_direct",
            "mac": mac,
            "expected_registry": "MA-L",
            "actual_registry": result["matched_registry"],
            "assignment_org_count": len(result["matches"]),
            "pass": result["matched_registry"] == "MA-L" and bool(result["matches"]),
        })

    # U/L exclusion proof using a globally administered source-derived MAC if possible.
    global_prefix = next(
        (p for p in list(ma_s) + list(ma_m) + list(ma_l)
         if (int(p[:2], 16) & 0x02) == 0),
        None,
    )
    if global_prefix is None:
        raise SystemExit("No globally administered source prefix available for U/L fixture")
    global_mac = sample_mac_from_prefix(global_prefix)
    local_mac = set_ul_bit(global_mac)
    local_result = lookup(local_mac, indexes)
    fixtures.append({
        "fixture": "locally_administered_exclusion",
        "source_global_mac": global_mac,
        "locally_administered_mac": local_mac,
        "expected_eligible": False,
        "actual_eligible": local_result["eligible"],
        "pass": local_result["eligible"] is False and not local_result["matches"],
    })

    # Prove that an official duplicate prefix with distinct organizations
    # preserves all assignment-org outcomes and never performs first-row selection.
    ambiguous_fixture = None
    for registry in ("MA-S", "MA-M", "MA-L"):
        for prefix, matches in indexes[registry].items():
            if len(matches) > 1 and (int(prefix[:2], 16) & 0x02) == 0:
                mac = sample_mac_from_prefix(prefix)
                result = lookup(mac, indexes)
                ambiguous_fixture = {
                    "fixture": "duplicate_prefix_preserves_all_assignment_orgs",
                    "prefix_hex": prefix,
                    "mac": mac,
                    "expected_registry": registry,
                    "expected_assignment_org_ids": sorted(
                        item["assignment_org_id"] for item in matches
                    ),
                    "actual_registry": result["matched_registry"],
                    "actual_assignment_org_ids": sorted(
                        item["assignment_org_id"] for item in result["matches"]
                    ),
                    "pass": (
                        result["matched_registry"] == registry
                        and sorted(item["assignment_org_id"] for item in result["matches"])
                        == sorted(item["assignment_org_id"] for item in matches)
                    ),
                }
                break
        if ambiguous_fixture is not None:
            break
    if ambiguous_fixture is not None:
        fixtures.append(ambiguous_fixture)

    if not all(f["pass"] for f in fixtures):
        raise SystemExit(f"Lookup fixture failure: {fixtures!r}")

    total_rows = sum(v["source_row_count"] for v in file_results.values())

    report = {
        "audit_contract": "captivportal.fe4.ieee_k4_source_audit.v1.1",
        "audited_at_utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "source_family": "IEEE Registration Authority Public Listings MA-L/MA-M/MA-S",
        "source_character": "current",
        "raw_result_semantic": "mac_assignment_org",
        "automatic_manufacturer_mapping": False,
        "initial_manufacturer_mapping": None,
        "files": file_results,
        "total_rows": total_rows,
        "source_bundle_manifest": bundle_manifest,
        "source_bundle_sha256": bundle_sha256,
        "duplicates": {
            "policy": (
                "preserve all distinct assignment_org outcomes at the selected "
                "longest prefix; collapse only exact K4-semantic repetitions; "
                "never first-row select"
            ),
            "duplicate_prefix_group_count": sum(
                value["duplicate_prefix_group_count"] for value in file_results.values()
            ),
            "ambiguous_prefix_group_count": sum(
                value["ambiguous_prefix_group_count"] for value in file_results.values()
            ),
            "exact_semantic_duplicate_rows_collapsed": sum(
                value["exact_semantic_duplicate_rows_collapsed"]
                for value in file_results.values()
            ),
        },
        "prefix_nesting": nesting,
        "lookup_contract": {
            "globally_administered_order": ["MA-S", "MA-M", "MA-L"],
            "locally_administered_behavior": "NO_IEEE_CLAIM",
        },
        "fixtures": fixtures,
        "result": "PASS",
    }

    out = root / "ieee-k4-fe4-audit.json"
    out.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    print()
    print("F-E4 IEEE K4 SOURCE AUDIT = PASS")
    for reg in ("MA-L", "MA-M", "MA-S"):
        r = file_results[reg]
        print(
            f"{reg}: source_rows={r['source_row_count']} "
            f"semantic_records={r['semantic_record_count']} "
            f"duplicate_prefix_groups={r['duplicate_prefix_group_count']} "
            f"ambiguous_prefix_groups={r['ambiguous_prefix_group_count']} "
            f"bytes={r['size_bytes']} sha256={r['sha256']}"
        )
    print(f"TOTAL_ROWS={total_rows}")
    print(f"SOURCE_BUNDLE_SHA256={bundle_sha256}")
    print(f"NESTING={json.dumps(nesting, sort_keys=True)}")
    print(f"REPORT={out.resolve()}")

if __name__ == "__main__":
    main()
