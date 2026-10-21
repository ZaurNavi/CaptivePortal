#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import pathlib
import re
import subprocess
import sys
import unicodedata
import uuid
from collections import defaultdict
from datetime import datetime, timezone

# Never write bytecode into the candidate checkout.
sys.dont_write_bytecode = True

REPO = pathlib.Path(r"C:\CaptivPortal-Lab\coder-task04-t09-utility-repair-a1")
SOURCE_DIR = pathlib.Path(
    r"C:\CaptivPortal-Lab\official-runs\task04\f-e4\k4-refresh-20261001T094909600Z"
)
OUT_ROOT = pathlib.Path(r"C:\CaptivPortal-Lab\official-runs\task04\f-e4")

EXPECTED_COMMIT = "8a39459be3ce7ed40e325736034245f0025cf249"
EXPECTED_TREE = "e2521f27c9f91978e381bce202ab3e3c83aa6dad"
HISTORICAL_BASE_COMMIT = "74f7c7add401e5fec0469d49770466c2747c03cf"

RETRIEVAL_WINDOW_START_UTC = "2026-10-01T09:49:09.849Z"
RETRIEVAL_WINDOW_END_UTC = "2026-10-01T09:50:30.800Z"
PROVENANCE_RETRIEVED_AT_UTC = "2026-10-01T09:50:30.800Z"

EXPECTED_K4_FRESHNESS_DIGEST = (
    "9a3a58d72dfb660b9a639b7558424cd55d213f8306e586c1b263aa4cda0d3df5"
)

EXPECTED_SOURCES = {
    "MA-L": {
        "filename": "oui.csv",
        "url": "https://standards-oui.ieee.org/oui/oui.csv",
        "bits": 24,
        "width": 6,
        "bytes": 3851653,
        "sha256": "387471290f8cbcecbad1ac76e6ee442e543f855394690caf3b787ca9b16a24c8",
        "start": "2026-10-01T09:49:09.983Z",
        "end": "2026-10-01T09:50:15.313Z",
    },
    "MA-M": {
        "filename": "mam.csv",
        "url": "https://standards-oui.ieee.org/oui28/mam.csv",
        "bits": 28,
        "width": 7,
        "bytes": 755381,
        "sha256": "0d8481a68997d76f3193da904e144af43918a71e15ab5d54e1c9074e366f39a0",
        "start": "2026-10-01T09:50:15.389Z",
        "end": "2026-10-01T09:50:24.643Z",
    },
    "MA-S": {
        "filename": "oui36.csv",
        "url": "https://standards-oui.ieee.org/oui36/oui36.csv",
        "bits": 36,
        "width": 9,
        "bytes": 669748,
        "sha256": "268ad0b8511044dd0dad4441a99566c787f363b525973e6b8b9c6b125c3d49ed",
        "start": "2026-10-01T09:50:24.656Z",
        "end": "2026-10-01T09:50:30.757Z",
    },
}
HEADER = ["Registry", "Assignment", "Organization Name", "Organization Address"]
HEX_RE = re.compile(r"^[0-9A-Fa-f]+$")

K4_IMPL = "app/device_fingerprint/k4_ieee_import.py"
K4_TEST = "tests/device_fingerprint_fe4/test_k4_ieee_import.py"


def fail(reason: str) -> None:
    print("")
    print("F_E4_FORMAL_STATUS=FAIL")
    print("REASON=" + reason)
    print("PRODUCTION_ACTION=NO")
    raise SystemExit(1)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args: str) -> str:
    cp = subprocess.run(
        ["git", "-C", str(REPO), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if cp.returncode != 0:
        fail("GIT_FAILURE:" + " ".join(args) + ":" + cp.stderr.strip())
    return cp.stdout.strip()


def artifact_envelope(content) -> dict:
    return {
        "artifact_id": content.artifact_id,
        "artifact_schema_version": content.artifact_schema_version,
        "artifact_type": content.artifact_type,
        "content_sha256": content.content_sha256,
        "semantic_payload": content.semantic_payload,
    }


def write_artifact(path: pathlib.Path, content, canonical_artifact_json) -> None:
    path.write_bytes(canonical_artifact_json(artifact_envelope(content)))


def evidence_ref(label: str, path: pathlib.Path, media_type: str) -> dict:
    return {
        "evidence_label": label,
        "file_sha256": sha256_file(path),
        "media_type": media_type,
        "path_or_reference": str(path),
    }


def utc_ms_now(format_utc) -> str:
    return format_utc(datetime.now(timezone.utc))


def canonical_mac_from_hex(value: str) -> str:
    padded = value + "0" * (12 - len(value))
    return ":".join(padded[i:i+2] for i in range(0, 12, 2))


# ---------------------------------------------------------------------------
# 1. Exact repaired candidate and unchanged K4 implementation/test lineage
# ---------------------------------------------------------------------------

if not REPO.is_dir():
    fail("REPAIRED_REPO_MISSING")

commit = git("rev-parse", "HEAD").lower()
tree = git("rev-parse", "HEAD^{tree}").lower()
if commit != EXPECTED_COMMIT:
    fail("CANDIDATE_COMMIT_MISMATCH:" + commit)
if tree != EXPECTED_TREE:
    fail("CANDIDATE_TREE_MISMATCH:" + tree)
if git("status", "--porcelain"):
    fail("CANDIDATE_WORKTREE_NOT_CLEAN_BEFORE_GATE")

for rel in (K4_IMPL, K4_TEST):
    if not (REPO / rel).is_file():
        fail("REQUIRED_CANDIDATE_FILE_MISSING:" + rel)
    old_blob = git("rev-parse", f"{HISTORICAL_BASE_COMMIT}:{rel}").lower()
    new_blob = git("rev-parse", f"HEAD:{rel}").lower()
    if old_blob != new_blob:
        fail(f"K4_FROZEN_FILE_CHANGED:{rel}:old={old_blob}:new={new_blob}")

# ---------------------------------------------------------------------------
# 2. Pin exact retained real IEEE retrieval bytes; never re-download.
# ---------------------------------------------------------------------------

raw_by_family: dict[str, bytes] = {}
retrieval_members: list[dict] = []

for family in ("MA-L", "MA-M", "MA-S"):
    meta = EXPECTED_SOURCES[family]
    path = SOURCE_DIR / meta["filename"]
    if not path.is_file():
        fail("RETAINED_IEEE_SOURCE_MISSING:" + family)
    raw = path.read_bytes()
    actual_sha = sha256_bytes(raw)
    if len(raw) != meta["bytes"]:
        fail(f"IEEE_SOURCE_SIZE_CHANGED:{family}:{len(raw)}")
    if actual_sha != meta["sha256"]:
        fail(f"IEEE_SOURCE_SHA_CHANGED:{family}:{actual_sha}")
    raw_by_family[family] = raw
    retrieval_members.append({
        "registry_family": family,
        "filename": meta["filename"],
        "source_url": meta["url"],
        "size_bytes": len(raw),
        "sha256": actual_sha,
        "retrieval_start_utc": meta["start"],
        "retrieval_end_utc": meta["end"],
    })

# ---------------------------------------------------------------------------
# 3. Import exact local candidate APIs.
# ---------------------------------------------------------------------------

sys.path.insert(0, str(REPO))

from app.device_fingerprint.artifact_content import ArtifactRef, canonical_artifact_json
from app.device_fingerprint.fe5_external_knowledge import (
    build_ieee_k4_external_provenance,
    build_ieee_k4_freshness_policy,
)
from app.device_fingerprint.foundation_gate_artifacts import make_gate_result_manifest
from app.device_fingerprint.k4_ieee_import import (
    build_ieee_k4_source_governance_candidate,
    compute_ieee_k4_source_bundle_sha256,
    import_ieee_k4_bytes,
    is_ieee_assignment_lookup_eligible,
    match_k4_records,
)
from app.device_fingerprint.validation import format_utc

ma_l = raw_by_family["MA-L"]
ma_m = raw_by_family["MA-M"]
ma_s = raw_by_family["MA-S"]

bundle_sha = compute_ieee_k4_source_bundle_sha256(ma_l, ma_m, ma_s)

# ---------------------------------------------------------------------------
# 4. Build unchanged governance/freshness and NEW real provenance.
# ---------------------------------------------------------------------------

governance = build_ieee_k4_source_governance_candidate()
freshness = build_ieee_k4_freshness_policy()

if freshness.content_sha256 != EXPECTED_K4_FRESHNESS_DIGEST:
    fail("K4_FRESHNESS_POLICY_IDENTITY_CHANGED:" + freshness.content_sha256)

gov_payload = governance.semantic_payload
if gov_payload.get("source_name") != "IEEE Registration Authority MA-L/MA-M/MA-S Public Listings":
    fail("K4_GOVERNANCE_SOURCE_NAME_CHANGED")
if gov_payload.get("unresolved_restrictions") != []:
    fail("K4_GOVERNANCE_UNRESOLVED_RESTRICTIONS")
if "Duplicate assignment prefixes are preserved safely." not in gov_payload.get(
    "review_basis_semantics", ""
):
    fail("K4_GOVERNANCE_DUPLICATE_AMBIGUITY_CONTRACT_MISSING")

provenance = build_ieee_k4_external_provenance(
    ma_l,
    ma_m,
    ma_s,
    retrieved_at_utc=PROVENANCE_RETRIEVED_AT_UTC,
    governance=governance,
    freshness_policy=freshness,
)

prov_payload = provenance.semantic_payload
if prov_payload["source_artifact_sha256"] != bundle_sha:
    fail("K4_PROVENANCE_SOURCE_BUNDLE_MISMATCH")
if prov_payload["retrieved_at_utc"] != PROVENANCE_RETRIEVED_AT_UTC:
    fail("K4_PROVENANCE_RETRIEVED_AT_MISMATCH")
if prov_payload["importer_identity"] != "captivportal.k4_ieee_import":
    fail("K4_PROVENANCE_IMPORTER_IDENTITY_CHANGED")
if prov_payload["importer_version"] != "1":
    fail("K4_PROVENANCE_IMPORTER_VERSION_CHANGED")
if prov_payload["source_governance_record"] != ArtifactRef(
    governance.artifact_id, governance.content_sha256
).as_dict():
    fail("K4_PROVENANCE_GOVERNANCE_REF_MISMATCH")
if prov_payload["knowledge_freshness_policy"] != ArtifactRef(
    freshness.artifact_id, freshness.content_sha256
).as_dict():
    fail("K4_PROVENANCE_FRESHNESS_REF_MISMATCH")

# ---------------------------------------------------------------------------
# 5. Build NEW K4 record set from exact retrieved bytes.
# ---------------------------------------------------------------------------

provenance_ref = ArtifactRef(provenance.artifact_id, provenance.content_sha256)
record_set = import_ieee_k4_bytes(
    ma_l, ma_m, ma_s, knowledge_provenance=provenance_ref
)

rp = record_set.semantic_payload
if rp["knowledge_slot"] != "K4":
    fail("K4_RECORD_SET_SLOT_MISMATCH")
if rp["knowledge_provenance"] != provenance_ref.as_dict():
    fail("K4_RECORD_SET_PROVENANCE_REF_MISMATCH")

records = rp["records"]
if not records:
    fail("K4_RECORD_SET_EMPTY")

# ---------------------------------------------------------------------------
# 6. Duplicate-aware real-source proof.
#    Historical audit R1 incorrectly rejected any duplicate prefix.
#    Frozen importer semantics preserve ambiguity:
#      - identical semantic duplicate -> one semantic record
#      - same prefix, distinct normalized organization -> all records retained
# ---------------------------------------------------------------------------

raw_group_rows: dict[tuple[str, str], list[dict]] = defaultdict(list)
raw_unique_semantics: dict[tuple[str, str], set[str]] = defaultdict(set)
raw_total_rows = 0

for family in ("MA-L", "MA-M", "MA-S"):
    meta = EXPECTED_SOURCES[family]
    try:
        text = raw_by_family[family].decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        fail(f"IEEE_SOURCE_NOT_UTF8:{family}:{exc}")

    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    header = next(reader, None)
    if header != HEADER:
        fail(f"IEEE_HEADER_MISMATCH:{family}:{header!r}")

    for line_no, row in enumerate(reader, 2):
        raw_total_rows += 1
        if len(row) != 4:
            fail(f"IEEE_ROW_WIDTH_INVALID:{family}:{line_no}")
        registry, assignment, organization, _address = row
        if registry != family:
            fail(f"IEEE_REGISTRY_INVALID:{family}:{line_no}:{registry}")
        if len(assignment) != meta["width"] or HEX_RE.fullmatch(assignment) is None:
            fail(f"IEEE_ASSIGNMENT_INVALID:{family}:{line_no}:{assignment}")
        label = unicodedata.normalize("NFC", organization)
        if not label.strip():
            fail(f"IEEE_EMPTY_ORG:{family}:{line_no}")
        prefix = assignment.lower()
        key = (family, prefix)
        raw_group_rows[key].append({"line": line_no, "label": label})
        raw_unique_semantics[key].add(label)

duplicate_prefix_groups = {
    key: rows for key, rows in raw_group_rows.items() if len(rows) > 1
}
duplicate_extra_rows = sum(len(rows) - 1 for rows in duplicate_prefix_groups.values())
ambiguous_duplicate_groups = {
    key: rows
    for key, rows in duplicate_prefix_groups.items()
    if len(raw_unique_semantics[key]) > 1
}
identical_only_duplicate_groups = {
    key: rows
    for key, rows in duplicate_prefix_groups.items()
    if len(raw_unique_semantics[key]) == 1
}

actual_group_semantics: dict[tuple[str, str], set[str]] = defaultdict(set)
source_ids: set[str] = set()
canonical_ids: set[str] = set()

for record in records:
    if record["record_type"] != "K4_IEEE_ASSIGNMENT":
        fail("K4_NON_IEEE_RECORD_PRESENT")
    family = record["registry_family"]
    if family not in EXPECTED_SOURCES:
        fail("K4_RECORD_UNKNOWN_FAMILY:" + str(family))
    meta = EXPECTED_SOURCES[family]
    prefix = record["prefix_hex"]
    if (
        len(prefix) != meta["width"]
        or prefix != prefix.lower()
        or re.fullmatch(r"[0-9a-f]+", prefix) is None
        or record["prefix_length_bits"] != meta["bits"]
    ):
        fail("K4_RECORD_PREFIX_NOT_CANONICAL:" + record["canonical_record_id"])
    if record["manufacturer_mapping"] is not None:
        fail("K4_AUTOMATIC_MANUFACTURER_MAPPING_PRESENT")
    if record["source_record_identity"] in source_ids:
        fail("K4_DUPLICATE_SOURCE_RECORD_IDENTITY")
    source_ids.add(record["source_record_identity"])
    if record["canonical_record_id"] in canonical_ids:
        fail("K4_DUPLICATE_CANONICAL_RECORD_ID")
    canonical_ids.add(record["canonical_record_id"])

    key = (family, prefix)
    actual_group_semantics[key].add(record["assignment_org_label"])

expected_group_semantics = {
    key: set(labels) for key, labels in raw_unique_semantics.items()
}

if set(actual_group_semantics) != set(expected_group_semantics):
    missing = len(set(expected_group_semantics) - set(actual_group_semantics))
    extra = len(set(actual_group_semantics) - set(expected_group_semantics))
    fail(f"K4_GROUP_SET_MISMATCH:missing={missing}:extra={extra}")

semantic_mismatch = [
    key
    for key in expected_group_semantics
    if actual_group_semantics[key] != expected_group_semantics[key]
]
if semantic_mismatch:
    fail("K4_DUPLICATE_SEMANTIC_PRESERVATION_MISMATCH:" + repr(semantic_mismatch[0]))

expected_unique_records = sum(len(values) for values in expected_group_semantics.values())
if len(records) != expected_unique_records:
    fail(
        f"K4_CANONICAL_RECORD_COUNT_MISMATCH:"
        f"expected={expected_unique_records}:actual={len(records)}"
    )

# ---------------------------------------------------------------------------
# 7. Real-source lookup invariants plus explicit ambiguity behavior.
# ---------------------------------------------------------------------------

if is_ieee_assignment_lookup_eligible("02:00:00:00:00:00"):
    fail("K4_UL_ELIGIBILITY_REGRESSION")
if match_k4_records(record_set, "02:00:00:00:00:00") != ():
    fail("K4_UL_LOOKUP_REGRESSION")

prefix_sets = {
    fam: set(prefix for f, prefix in expected_group_semantics if f == fam)
    for fam in ("MA-L", "MA-M", "MA-S")
}

# Find a real globally-administered nested prefix and prove longest-prefix selection.
actual_longest_prefix_fixture = None
for family, bits, width, parent_family, parent_width in (
    ("MA-S", 36, 9, "MA-M", 7),
    ("MA-S", 36, 9, "MA-L", 6),
    ("MA-M", 28, 7, "MA-L", 6),
):
    for prefix in sorted(prefix_sets[family]):
        if int(prefix[:2], 16) & 0x02:
            continue
        if prefix[:parent_width] not in prefix_sets[parent_family]:
            continue
        mac = canonical_mac_from_hex(prefix)
        selected = match_k4_records(record_set, mac)
        if not selected:
            continue
        if any(r["prefix_length_bits"] != bits or r["prefix_hex"] != prefix for r in selected):
            fail("K4_LONGEST_PREFIX_REGRESSION:" + prefix)
        expected_labels = expected_group_semantics[(family, prefix)]
        actual_labels = {r["assignment_org_label"] for r in selected}
        if actual_labels != expected_labels:
            fail("K4_LONGEST_PREFIX_AMBIGUITY_SET_MISMATCH:" + prefix)
        actual_longest_prefix_fixture = {
            "mac": mac,
            "selected_registry_family": family,
            "selected_prefix_hex": prefix,
            "selected_prefix_length_bits": bits,
            "selected_record_count": len(selected),
            "selected_org_semantic_count": len(actual_labels),
            "parent_registry_family": parent_family,
            "parent_prefix_hex": prefix[:parent_width],
        }
        break
    if actual_longest_prefix_fixture is not None:
        break

if actual_longest_prefix_fixture is None:
    fail("K4_NO_REAL_LONGEST_PREFIX_FIXTURE_AVAILABLE")

# Explicitly prove that at least one duplicate prefix is retained safely.
if not duplicate_prefix_groups:
    fail("K4_EXPECTED_REFRESH_DUPLICATES_NOT_FOUND")

first_duplicate_key = sorted(duplicate_prefix_groups)[0]
first_duplicate_fixture = {
    "registry_family": first_duplicate_key[0],
    "prefix_hex": first_duplicate_key[1],
    "raw_row_count": len(duplicate_prefix_groups[first_duplicate_key]),
    "unique_normalized_org_semantics": len(raw_unique_semantics[first_duplicate_key]),
    "imported_semantic_record_count": len(actual_group_semantics[first_duplicate_key]),
}
if (
    first_duplicate_fixture["unique_normalized_org_semantics"]
    != first_duplicate_fixture["imported_semantic_record_count"]
):
    fail("K4_FIRST_DUPLICATE_FIXTURE_MISMATCH")

# ---------------------------------------------------------------------------
# 8. Output directory and focused accepted F-E4 test surface.
# ---------------------------------------------------------------------------

stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
OUT = OUT_ROOT / ("official-run-" + stamp + "-FE4-A1-K4-REFRESH-R2")
if OUT.exists():
    fail("F_E4_OUTPUT_ALREADY_EXISTS")
OUT.mkdir(parents=True)

pytest_log = OUT / "pytest-f-e4.txt"
pytest_tmp = OUT / "pytest-tmp"
process_tmp = OUT / "process-tmp"
process_tmp.mkdir()

pytest_env = dict(os.environ)
pytest_env["PYTHONPATH"] = str(REPO) + os.pathsep + pytest_env.get("PYTHONPATH", "")
pytest_env["PYTHONDONTWRITEBYTECODE"] = "1"
pytest_env["PYTHONPYCACHEPREFIX"] = str(OUT / "pycache")
pytest_env["PYTEST_ADDOPTS"] = ""
for temp_name in ("TEMP", "TMP", "TMPDIR"):
    pytest_env[temp_name] = str(process_tmp)

pytest_cmd = [
    sys.executable,
    "-m",
    "pytest",
    "-q",
    "-p",
    "no:cacheprovider",
    "--basetemp",
    str(pytest_tmp),
    K4_TEST,
]
cp = subprocess.run(
    pytest_cmd,
    cwd=str(REPO),
    env=pytest_env,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    encoding="utf-8",
    errors="replace",
    check=False,
)
pytest_log.write_text(cp.stdout, encoding="utf-8")
if cp.returncode != 0:
    print(cp.stdout)
    fail("F_E4_FOCUSED_PYTEST_FAILED:" + str(cp.returncode))

# Ensure test execution did not dirty the candidate.
if git("status", "--porcelain"):
    fail("CANDIDATE_WORKTREE_DIRTY_AFTER_F_E4_TESTS")

# ---------------------------------------------------------------------------
# 9. Retain artifacts and duplicate-aware technical proof.
# ---------------------------------------------------------------------------

gov_path = OUT / "k4-source-governance.json"
fresh_path = OUT / "k4-freshness-policy.json"
prov_path = OUT / "k4-provenance-refreshed.json"
record_path = OUT / "k4-record-set-refreshed.json"

write_artifact(gov_path, governance, canonical_artifact_json)
write_artifact(fresh_path, freshness, canonical_artifact_json)
write_artifact(prov_path, provenance, canonical_artifact_json)
write_artifact(record_path, record_set, canonical_artifact_json)

historical_failed_audit_log = SOURCE_DIR / "ieee-k4-fe4-audit.stdout.txt"

retrieval_binding = {
    "evidence_contract": "captivportal.fe4.ieee_k4_refresh_retrieval_binding.v2",
    "architecture_disposition": "TASK-04-T09-A1-ROUTE-A",
    "candidate_repository_commit_sha": commit,
    "candidate_repository_tree_sha": tree,
    "retrieval_window_start_utc": RETRIEVAL_WINDOW_START_UTC,
    "retrieval_window_end_utc": RETRIEVAL_WINDOW_END_UTC,
    "provenance_retrieved_at_utc": PROVENANCE_RETRIEVED_AT_UTC,
    "retrieval_timestamp_basis": (
        "Exact timestamps retained from the real three-file IEEE retrieval console evidence; "
        "source bytes are independently re-bound here by exact size and SHA-256. "
        "No source re-download and no timestamp substitution."
    ),
    "members": retrieval_members,
    "source_bundle_sha256": bundle_sha,
    "production_action": False,
}
retrieval_binding_path = OUT / "k4-refresh-retrieval-binding.json"
retrieval_binding_path.write_bytes(canonical_artifact_json(retrieval_binding))

duplicate_summary = [
    {
        "registry_family": family,
        "prefix_hex": prefix,
        "raw_row_count": len(rows),
        "unique_normalized_org_semantics": len(raw_unique_semantics[(family, prefix)]),
        "imported_semantic_record_count": len(actual_group_semantics[(family, prefix)]),
    }
    for (family, prefix), rows in sorted(duplicate_prefix_groups.items())
]

technical_proof = {
    "proof_schema_version": 2,
    "gate_id": "F-E4",
    "status": "PASS",
    "procedure_or_test_suite_id": "F-E4-ieee-k4-refresh-duplicate-aware-r2",
    "architecture_disposition": "TASK-04-T09-A1-ROUTE-A",
    "candidate_repository_commit_sha": commit,
    "candidate_repository_tree_sha": tree,
    "frozen_k4_implementation_blob_unchanged": True,
    "frozen_k4_test_blob_unchanged": True,
    "source": {
        "source_family_id": "ieee_ra_mac",
        "source_bundle_sha256": bundle_sha,
        "retrieval_window_start_utc": RETRIEVAL_WINDOW_START_UTC,
        "retrieval_window_end_utc": RETRIEVAL_WINDOW_END_UTC,
        "retrieved_at_utc": PROVENANCE_RETRIEVED_AT_UTC,
        "raw_rows_total": raw_total_rows,
    },
    "duplicate_semantics": {
        "historical_audit_r1_disposition": (
            "SUPERSEDED_FOR_REFRESH_PROOF_ONLY: it rejected any duplicate prefix, "
            "while the already-admitted frozen K4 importer/governance explicitly preserve "
            "duplicate-prefix ambiguity safely."
        ),
        "duplicate_prefix_group_count": len(duplicate_prefix_groups),
        "duplicate_extra_source_row_count": duplicate_extra_rows,
        "ambiguous_duplicate_group_count": len(ambiguous_duplicate_groups),
        "identical_only_duplicate_group_count": len(identical_only_duplicate_groups),
        "all_raw_group_semantics_equal_imported_group_semantics": True,
        "first_duplicate_fixture": first_duplicate_fixture,
        "duplicate_groups": duplicate_summary,
    },
    "k4_contract": {
        "canonical_record_count": len(records),
        "raw_result_semantic": "mac_assignment_org",
        "manufacturer_mapping_all_null": True,
        "longest_prefix_order": ["MA-S", "MA-M", "MA-L"],
        "locally_administered_behavior": "NO_IEEE_CLAIM",
        "actual_longest_prefix_fixture": actual_longest_prefix_fixture,
    },
    "artifacts": {
        "source_governance": ArtifactRef(
            governance.artifact_id, governance.content_sha256
        ).as_dict(),
        "knowledge_freshness_policy": ArtifactRef(
            freshness.artifact_id, freshness.content_sha256
        ).as_dict(),
        "new_knowledge_provenance": ArtifactRef(
            provenance.artifact_id, provenance.content_sha256
        ).as_dict(),
        "new_k4_record_set": ArtifactRef(
            record_set.artifact_id, record_set.content_sha256
        ).as_dict(),
    },
    "focused_pytest": {
        "command": subprocess.list2cmdline(pytest_cmd),
        "exit_code": cp.returncode,
        "log_sha256": sha256_file(pytest_log),
    },
    "historical_failed_audit_r1": (
        {
            "path": str(historical_failed_audit_log),
            "sha256": sha256_file(historical_failed_audit_log),
            "classification": "TOOLING_FALSE_REJECTION_OF_ALREADY_ADMITTED_DUPLICATE_AMBIGUITY",
        }
        if historical_failed_audit_log.is_file()
        else None
    ),
    "governance_semantics_changed": False,
    "freshness_policy_semantics_changed": False,
    "importer_semantics_changed": False,
    "taxonomy_semantics_changed": False,
    "production_action": False,
}
technical_path = OUT / "f-e4-technical-proof.json"
technical_path.write_bytes(canonical_artifact_json(technical_proof))

# ---------------------------------------------------------------------------
# 10. Owner DecisionRecord.
# Owner already explicitly authorized all acceptance decisions needed to
# complete the fingerprint chain. Route A requires unchanged K4 governance.
# This records that acceptance only after technical proof has passed.
# ---------------------------------------------------------------------------

decision_id = str(uuid.uuid4())
decision_base = {
    "decision_record_id": decision_id,
    "decision_subject_type": "SourceGovernanceRecord",
    "decision_subject_id": governance.artifact_id,
    "decision": "ACCEPT",
    "decided_at_utc": utc_ms_now(format_utc),
    "actor_role": "OWNER",
    "referenced_artifact_ids": sorted([
        governance.artifact_id,
        freshness.artifact_id,
        provenance.artifact_id,
        record_set.artifact_id,
    ]),
    "referenced_gate_ids": ["F-E4"],
    "reason_reference_text": (
        "Owner previously explicitly authorized all required acceptance decisions needed "
        "to finish the Device Fingerprint chain. Under Architect2 TASK-04/T-09 A1 Route A, "
        "the existing K4 external governance and freshness policy are reused unchanged. "
        "The real current IEEE MA-L/MA-M/MA-S retrieval passed duplicate-aware validation "
        "using the already-admitted frozen K4 importer semantics. This acceptance does not "
        "authorize production activation."
    ),
}
decision_hash = hashlib.sha256(canonical_artifact_json(decision_base)).hexdigest()
decision = {**decision_base, "record_sha256": decision_hash}
decision_path = OUT / "owner-decision-record.json"
decision_path.write_bytes(canonical_artifact_json(decision))

# ---------------------------------------------------------------------------
# 11. Formal GateResultManifest.
# Inputs: unchanged governance + freshness.
# Outputs: NEW provenance + NEW K4 CKRS.
# F-E5, not F-E4, owns the central foundation knowledge evaluation time.
# ---------------------------------------------------------------------------

script_path = pathlib.Path(__file__).resolve()
retained = [
    evidence_ref("F-E4_IEEE_MA_L_SOURCE", SOURCE_DIR / "oui.csv", "text/csv"),
    evidence_ref("F-E4_IEEE_MA_M_SOURCE", SOURCE_DIR / "mam.csv", "text/csv"),
    evidence_ref("F-E4_IEEE_MA_S_SOURCE", SOURCE_DIR / "oui36.csv", "text/csv"),
    evidence_ref("F-E4_REFRESH_RETRIEVAL_BINDING", retrieval_binding_path, "application/json"),
    evidence_ref("F-E4_DUPLICATE_AWARE_TECHNICAL_PROOF", technical_path, "application/json"),
    evidence_ref("F-E4_FOCUSED_PYTEST", pytest_log, "text/plain"),
    evidence_ref("F-E4_OWNER_DECISION", decision_path, "application/json"),
    evidence_ref("F-E4_K4_IMPLEMENTATION_SOURCE", REPO / K4_IMPL, "text/x-python"),
    evidence_ref("F-E4_K4_TEST_SOURCE", REPO / K4_TEST, "text/x-python"),
]
if historical_failed_audit_log.is_file():
    retained.append(
        evidence_ref(
            "F-E4_HISTORICAL_AUDIT_R1_FALSE_DUPLICATE_REJECTION",
            historical_failed_audit_log,
            "text/plain",
        )
    )

gate = make_gate_result_manifest({
    "gate_id": "F-E4",
    "gate_contract_version": "R14-F-E4-v1",
    "status": "PASS",
    "candidate_repository_commit_sha": commit,
    "candidate_repository_tree_sha": tree,
    "input_artifact_refs": [
        ArtifactRef(governance.artifact_id, governance.content_sha256).as_dict(),
        ArtifactRef(freshness.artifact_id, freshness.content_sha256).as_dict(),
    ],
    "output_artifact_refs": [
        ArtifactRef(provenance.artifact_id, provenance.content_sha256).as_dict(),
        ArtifactRef(record_set.artifact_id, record_set.content_sha256).as_dict(),
    ],
    "retained_evidence_refs": retained,
    "proof_execution_identity": {
        "execution_id": str(uuid.uuid4()),
        "executor_kind": "TECHLEAD_GATE_TOOL",
        "repository_commit_sha": commit,
        "repository_tree_sha": tree,
        "procedure_or_test_suite_id": "F-E4-ieee-k4-refresh-duplicate-aware-r2",
        "environment_identity": "CaptivPortal-Lab-Windows-F-E4-A1-RouteA",
        "execution_artifact_sha256": sha256_file(script_path),
    },
    "trusted_time_inputs": {
        "foundation_knowledge_evaluation_at_utc": None,
        "foundation_admission_evaluation_at_utc": None,
        "knowledge_evaluation_at_utc": None,
    },
    "decision_record_refs": [decision_id],
})

if gate.semantic_payload["status"] != "PASS":
    fail("F_E4_GATE_STATUS_NOT_PASS")
if len(gate.semantic_payload["output_artifact_refs"]) != 2:
    fail("F_E4_OUTPUT_ARTIFACT_COUNT_NOT_TWO")

gate_path = OUT / "gate-result-manifest.json"
gate_path.write_bytes(canonical_artifact_json(artifact_envelope(gate)))

summary = {
    "run_schema_version": 1,
    "gate_id": "F-E4",
    "formal_status": "PASS",
    "candidate_repository_commit_sha": commit,
    "candidate_repository_tree_sha": tree,
    "architecture_disposition": "TASK-04-T09-A1-ROUTE-A",
    "source_bundle_sha256": bundle_sha,
    "retrieved_at_utc": PROVENANCE_RETRIEVED_AT_UTC,
    "raw_source_row_count": raw_total_rows,
    "duplicate_prefix_group_count": len(duplicate_prefix_groups),
    "duplicate_extra_source_row_count": duplicate_extra_rows,
    "ambiguous_duplicate_group_count": len(ambiguous_duplicate_groups),
    "identical_only_duplicate_group_count": len(identical_only_duplicate_groups),
    "canonical_k4_record_count": len(records),
    "unchanged_source_governance_id": governance.artifact_id,
    "unchanged_freshness_policy_id": freshness.artifact_id,
    "new_k4_provenance_id": provenance.artifact_id,
    "new_k4_record_set_id": record_set.artifact_id,
    "owner_decision_record_id": decision_id,
    "gate_result_id": gate.artifact_id,
    "gate_result_content_sha256": gate.content_sha256,
    "technical_proof_sha256": sha256_file(technical_path),
    "pytest_log_sha256": sha256_file(pytest_log),
    "production_action": False,
    "next_gate": "F-E5",
}
summary_path = OUT / "formal-run-summary.json"
summary_path.write_bytes(canonical_artifact_json(summary))

if git("status", "--porcelain"):
    fail("CANDIDATE_WORKTREE_DIRTY_AFTER_F_E4_FORMALIZATION")

print("")
print("F_E4_FORMAL_STATUS=PASS")
print("CANDIDATE_COMMIT=" + commit)
print("CANDIDATE_TREE=" + tree)
print("K4_SOURCE_BUNDLE_SHA256=" + bundle_sha)
print("K4_RETRIEVED_AT_UTC=" + PROVENANCE_RETRIEVED_AT_UTC)
print("K4_RAW_SOURCE_ROWS=" + str(raw_total_rows))
print("K4_DUPLICATE_PREFIX_GROUPS=" + str(len(duplicate_prefix_groups)))
print("K4_DUPLICATE_EXTRA_ROWS=" + str(duplicate_extra_rows))
print("K4_AMBIGUOUS_DUPLICATE_GROUPS=" + str(len(ambiguous_duplicate_groups)))
print("K4_IDENTICAL_ONLY_DUPLICATE_GROUPS=" + str(len(identical_only_duplicate_groups)))
print("K4_CANONICAL_RECORDS=" + str(len(records)))
print("K4_GOVERNANCE_ID=" + governance.artifact_id)
print("K4_FRESHNESS_POLICY_ID=" + freshness.artifact_id)
print("NEW_K4_PROVENANCE_ID=" + provenance.artifact_id)
print("NEW_K4_RECORD_SET_ID=" + record_set.artifact_id)
print("OWNER_DECISION_RECORD_ID=" + decision_id)
print("F_E4_TECHNICAL_PROOF_SHA256=" + sha256_file(technical_path))
print("F_E4_PYTEST_LOG_SHA256=" + sha256_file(pytest_log))
print("F_E4_GATE_RESULT_ID=" + gate.artifact_id)
print("F_E4_GATE_RESULT_CONTENT_SHA256=" + gate.content_sha256)
print("F_E4_FORMAL_RUN_SUMMARY_SHA256=" + sha256_file(summary_path))
print("F_E4_OUTPUT_DIRECTORY=" + str(OUT))
print("GOVERNANCE_SEMANTICS_CHANGED=NO")
print("FRESHNESS_POLICY_SEMANTICS_CHANGED=NO")
print("IMPORTER_SEMANTICS_CHANGED=NO")
print("PRODUCTION_ACTION=NO")
print("NEXT=F-E5")
