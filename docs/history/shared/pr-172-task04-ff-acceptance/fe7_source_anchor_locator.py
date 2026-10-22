#!/usr/bin/env python3
import hashlib
import json
import os
import sys
from pathlib import Path

K1_SHA = "4f64a405fb1debbd2e066478a7190b821424e0691399068421fdaf168da09b14"
K2B_SHA = "791444ebf9a97a492b7a94020f721d016584918c437a450ccaa5525a55c95ad0"
K4_BUNDLE_SHA = "eb81bb97240fb7754659c33c13a9139583f7f505e38bc6618f9eef51b3878ae5"

DEFAULT_ROOTS = [
    Path(r"C:\CaptivPortal-Lab"),
    Path(r"C:\CaptivPortal-UI-Preview"),
    Path.home() / "Downloads",
]

SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".cache", "site-packages"}
HASH_EXTS = {".xml", ".txt", ".fp", ".sig", ".csv", ".json", ".dat", ".gz", ".zip", ".bin", ".db", ".sqlite", ".md"}
MAX_HASH_BYTES = 256 * 1024 * 1024

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def iter_files(root: Path):
    if not root.exists():
        return
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        basep = Path(base)
        for name in files:
            p = basep / name
            try:
                if p.stat().st_size <= MAX_HASH_BYTES:
                    yield p
            except OSError:
                pass

def locate_direct_hashes(roots):
    found = {"K1": [], "K2B": []}
    for root in roots:
        for p in iter_files(root):
            try:
                if p.suffix.lower() not in HASH_EXTS:
                    n = p.name.lower()
                    if not any(k in n for k in ("satori", "dhcp", "p0f", "finger", "oui", "mam")):
                        continue
                d = sha256_file(p)
                if d == K1_SHA:
                    found["K1"].append(str(p))
                if d == K2B_SHA:
                    found["K2B"].append(str(p))
            except (OSError, PermissionError):
                continue
    return found

def canonical_json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def compute_k4_bundle(oui: Path, mam: Path, oui36: Path):
    items = [
        ("MA-L", "oui.csv", "https://standards-oui.ieee.org/oui/oui.csv", oui),
        ("MA-M", "mam.csv", "https://standards-oui.ieee.org/oui28/mam.csv", mam),
        ("MA-S", "oui36.csv", "https://standards-oui.ieee.org/oui36/oui36.csv", oui36),
    ]
    members = []
    for family, filename, url, path in items:
        data = path.read_bytes()
        members.append({
            "registry_family": family,
            "filename": filename,
            "source_url": url,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size_bytes": len(data),
        })
    payload = {"bundle_identity_version": "ieee_ra_k4_source_bundle_v1", "members": members}
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest(), members

def locate_k4_triples(roots):
    by_dir = {}
    for root in roots:
        for p in iter_files(root):
            if p.name.lower() in {"oui.csv", "mam.csv", "oui36.csv"}:
                by_dir.setdefault(str(p.parent), {})[p.name.lower()] = p

    matches = []
    tested = []
    for directory, files in sorted(by_dir.items()):
        if {"oui.csv", "mam.csv", "oui36.csv"} <= set(files):
            try:
                digest, members = compute_k4_bundle(files["oui.csv"], files["mam.csv"], files["oui36.csv"])
                row = {"directory": directory, "bundle_sha256": digest, "members": members}
                tested.append(row)
                if digest == K4_BUNDLE_SHA:
                    matches.append(row)
            except OSError:
                pass
    return matches, tested

def main():
    roots = [Path(a) for a in sys.argv[1:]] if len(sys.argv) > 1 else DEFAULT_ROOTS
    print("FE7_SOURCE_ANCHOR_LOCATOR")
    print("ROOTS=" + ";".join(str(r) for r in roots))
    direct = locate_direct_hashes(roots)
    k4_matches, k4_tested = locate_k4_triples(roots)

    print(f"K1_TARGET_SHA={K1_SHA}")
    print(f"K1_MATCH_COUNT={len(direct['K1'])}")
    for p in direct["K1"]:
        print("K1_MATCH=" + p)

    print(f"K2B_TARGET_SHA={K2B_SHA}")
    print(f"K2B_MATCH_COUNT={len(direct['K2B'])}")
    for p in direct["K2B"]:
        print("K2B_MATCH=" + p)

    print(f"K4_TARGET_BUNDLE_SHA={K4_BUNDLE_SHA}")
    print(f"K4_TRIPLES_TESTED={len(k4_tested)}")
    print(f"K4_MATCH_COUNT={len(k4_matches)}")
    for row in k4_matches:
        print("K4_MATCH_DIR=" + row["directory"])
        for member in row["members"]:
            print(f"K4_MEMBER={member['registry_family']}|{member['filename']}|{member['sha256']}|{member['size_bytes']}")

    if direct["K1"] and direct["K2B"] and k4_matches:
        print("FE7_SOURCE_ANCHORS=COMPLETE")
        return 0

    print("FE7_SOURCE_ANCHORS=INCOMPLETE")
    if k4_tested and not k4_matches:
        print("K4_NOTE=IEEE triples were found, but none matched the frozen initial bundle digest.")
        for row in k4_tested[:10]:
            print(f"K4_NONMATCH={row['directory']}|{row['bundle_sha256']}")
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
