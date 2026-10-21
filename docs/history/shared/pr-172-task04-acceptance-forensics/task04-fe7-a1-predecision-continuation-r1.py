#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(r"C:\CaptivPortal-Lab")
REPO = ROOT / "coder-task04-t09-utility-repair-a1"
FE7_ROOT = ROOT / "official-runs" / "task04" / "f-e7"

EXPECTED_COMMIT = "8a39459be3ce7ed40e325736034245f0025cf249"
EXPECTED_TREE = "e2521f27c9f91978e381bce202ab3e3c83aa6dad"
F_E5_TIME = "2026-10-01T10:25:29.793Z"
F_E5_GATE_ID = (
    "GateResultManifest:v1:sha256:"
    "fdee6045ea263d722a5e3c571b24515729a3d80173df8e5df93b8277307026c0"
)

EXPECTED_STATES = {
    "k1": ("fresh", True, "NO_ADDITIONAL_CAP"),
    "k2b": ("stale", True, "supporting"),
    "k4": ("fresh", True, "NO_ADDITIONAL_CAP"),
}


def fail(reason: str) -> None:
    print("")
    print("F_E7_PREDECISION_CONTINUATION_STATUS=FAIL")
    print("FORMAL_F_E7_EXECUTED=NO")
    print("REASON=" + reason)
    print("PRODUCTION_ACTION=NO")
    raise SystemExit(1)


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


def load_json(path: pathlib.Path) -> dict[str, Any]:
    if not path.is_file():
        fail("EVIDENCE_MISSING:" + str(path))
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail("EVIDENCE_PARSE_FAILURE:" + str(path) + ":" + repr(exc))
    if not isinstance(obj, dict):
        fail("EVIDENCE_NOT_OBJECT:" + str(path))
    return obj


# 1. Exact candidate still pinned and clean.
if not REPO.is_dir():
    fail("REPAIRED_REPO_MISSING")

commit = git("rev-parse", "HEAD").lower()
tree = git("rev-parse", "HEAD^{tree}").lower()

if commit != EXPECTED_COMMIT:
    fail("CANDIDATE_COMMIT_MISMATCH:" + commit)
if tree != EXPECTED_TREE:
    fail("CANDIDATE_TREE_MISMATCH:" + tree)
if git("status", "--porcelain"):
    fail("CANDIDATE_WORKTREE_NOT_CLEAN")

# 2. Find exactly one incomplete predecision run.
if not FE7_ROOT.is_dir():
    fail("F_E7_ROOT_MISSING")

candidates = []
for path in sorted(FE7_ROOT.glob("predecision-build-*-FE7-A1-01")):
    if not path.is_dir():
        continue
    required = [
        path / "knowledge-bundle.json",
        path / "build-input-manifest.json",
        path / "validation-report.json",
        path / "per-source-freshness-evaluation.json",
        path / "retained-artifact-locations.json",
    ]
    if all(p.is_file() for p in required) and not (path / "predecision-summary.json").exists():
        candidates.append(path)

if len(candidates) != 1:
    for item in candidates:
        print("INCOMPLETE_PREDECISION_CANDIDATE=" + str(item))
    fail("INCOMPLETE_PREDECISION_RUN_COUNT:" + str(len(candidates)))

OUT = candidates[0]

bundle_path = OUT / "knowledge-bundle.json"
input_manifest_path = OUT / "build-input-manifest.json"
validation_report_path = OUT / "validation-report.json"
freshness_report_path = OUT / "per-source-freshness-evaluation.json"
locations_path = OUT / "retained-artifact-locations.json"
summary_path = OUT / "predecision-summary.json"

bundle = load_json(bundle_path)
manifest = load_json(input_manifest_path)
validation = load_json(validation_report_path)
freshness_report = load_json(freshness_report_path)
locations = load_json(locations_path)

# 3. Validate retained technical proof rather than rerunning it.
if manifest.get("candidate_repository_commit_sha") != commit:
    fail("INPUT_MANIFEST_COMMIT_MISMATCH")
if manifest.get("candidate_repository_tree_sha") != tree:
    fail("INPUT_MANIFEST_TREE_MISMATCH")
if manifest.get("foundation_knowledge_evaluation_at_utc") != F_E5_TIME:
    fail("INPUT_MANIFEST_F_E5_TIME_MISMATCH")
if manifest.get("source_f_e5_gate_result_id") != F_E5_GATE_ID:
    fail("INPUT_MANIFEST_F_E5_GATE_MISMATCH")
if manifest.get("dependency_count") != 16:
    fail("INPUT_MANIFEST_DEPENDENCY_COUNT_MISMATCH")
if len(manifest.get("dependency_artifact_ids", [])) != 16:
    fail("INPUT_MANIFEST_DEPENDENCY_LIST_COUNT_MISMATCH")
if len(set(manifest.get("dependency_artifact_ids", []))) != 16:
    fail("INPUT_MANIFEST_DEPENDENCY_IDS_NOT_DISTINCT")
if manifest.get("raw_vendor_runtime_dependencies") != []:
    fail("RAW_VENDOR_RUNTIME_DEPENDENCY_PRESENT")
if manifest.get("ja4_semantic_slot_present") is not False:
    fail("JA4_SEMANTIC_SLOT_PRESENT")

if validation.get("double_build_identity_equal") is not True:
    fail("DOUBLE_BUILD_IDENTITY_NOT_PROVEN")
if validation.get("double_build_content_sha256_equal") is not True:
    fail("DOUBLE_BUILD_DIGEST_NOT_PROVEN")
if validation.get("double_build_canonical_bytes_equal") is not True:
    fail("DOUBLE_BUILD_BYTES_NOT_PROVEN")
if validation.get("dependency_validation_passed") is not True:
    fail("DEPENDENCY_VALIDATION_NOT_PROVEN")

bundle_id = validation.get("knowledge_bundle_artifact_id")
bundle_digest = validation.get("knowledge_bundle_content_sha256")
if not isinstance(bundle_id, str) or not bundle_id.startswith("KnowledgeBundle:v1:sha256:"):
    fail("INVALID_KNOWLEDGE_BUNDLE_ID")
if not isinstance(bundle_digest, str) or len(bundle_digest) != 64:
    fail("INVALID_KNOWLEDGE_BUNDLE_DIGEST")
if validation.get("build_1_artifact_id") != bundle_id:
    fail("BUILD_1_ID_MISMATCH")
if validation.get("build_2_artifact_id") != bundle_id:
    fail("BUILD_2_ID_MISMATCH")
if validation.get("build_1_content_sha256") != bundle_digest:
    fail("BUILD_1_DIGEST_MISMATCH")
if validation.get("build_2_content_sha256") != bundle_digest:
    fail("BUILD_2_DIGEST_MISMATCH")

if bundle.get("artifact_id") != bundle_id:
    fail("BUNDLE_FILE_ID_MISMATCH")
if bundle.get("content_sha256") != bundle_digest:
    fail("BUNDLE_FILE_DIGEST_MISMATCH")
if bundle_id.rsplit(":", 1)[-1] != bundle_digest:
    fail("BUNDLE_ID_DIGEST_MISMATCH")

if freshness_report.get("foundation_knowledge_evaluation_at_utc") != F_E5_TIME:
    fail("FRESHNESS_REPORT_F_E5_TIME_MISMATCH")
if freshness_report.get("clock_observed_by_f_e7") is not False:
    fail("F_E7_REPLACEMENT_CLOCK_WAS_USED")

rows = freshness_report.get("per_source")
if not isinstance(rows, list) or len(rows) != 3:
    fail("FRESHNESS_REPORT_SOURCE_COUNT_MISMATCH")

freshness = {}
for row in rows:
    if not isinstance(row, dict):
        fail("MALFORMED_FRESHNESS_ROW")
    slot = row.get("slot")
    if slot in freshness:
        fail("DUPLICATE_FRESHNESS_SLOT:" + str(slot))
    freshness[slot] = row

if set(freshness) != set(EXPECTED_STATES):
    fail("FRESHNESS_SLOT_SET_MISMATCH")

for slot, (expected_state, expected_eligible, expected_cap) in EXPECTED_STATES.items():
    row = freshness[slot]
    if row.get("age_ms", -1) < 0:
        fail(slot.upper() + "_NEGATIVE_AGE")
    if row.get("failure_code") is not None:
        fail(slot.upper() + "_FAILURE_CODE_PRESENT")
    if row.get("freshness_state") != expected_state:
        fail(slot.upper() + "_FRESHNESS_STATE_MISMATCH")
    if row.get("claim_eligible") is not expected_eligible:
        fail(slot.upper() + "_CLAIM_ELIGIBILITY_MISMATCH")
    if row.get("claim_strength_cap") != expected_cap:
        fail(slot.upper() + "_CLAIM_STRENGTH_CAP_MISMATCH")

# 4. Obtain source SHA / retrieved_at from exact retained provenance artifacts.
locs = locations.get("locations")
if not isinstance(locs, dict):
    fail("RETAINED_LOCATIONS_MISSING")

source_states = {}
for slot, key in (
    ("k1", "k1_provenance"),
    ("k2b", "k2b_provenance"),
    ("k4", "k4_provenance"),
):
    raw_path = locs.get(key)
    if not isinstance(raw_path, str) or not raw_path:
        fail("PROVENANCE_LOCATION_MISSING:" + slot)
    prov_path = pathlib.Path(raw_path)
    prov = load_json(prov_path)
    payload = prov.get("semantic_payload")
    if not isinstance(payload, dict):
        fail("PROVENANCE_PAYLOAD_MISSING:" + slot)

    source_sha = payload.get("source_artifact_sha256")
    retrieved_at = payload.get("retrieved_at_utc")
    if not isinstance(source_sha, str) or len(source_sha) != 64:
        fail("PROVENANCE_SOURCE_SHA_INVALID:" + slot)
    if not isinstance(retrieved_at, str) or not retrieved_at:
        fail("PROVENANCE_RETRIEVED_AT_INVALID:" + slot)

    row = freshness[slot]
    source_states[slot] = {
        "source_artifact_sha256": source_sha,
        "retrieved_at_utc": retrieved_at,
        "age_ms": row["age_ms"],
        "freshness_state": row["freshness_state"],
        "claim_eligible": row["claim_eligible"],
        "claim_strength_cap": row["claim_strength_cap"],
    }

# 5. Write only the missing summary.
summary = {
    "run_schema_version": 1,
    "phase": "F-E7_PREDECISION_TECHNICAL_BUILD",
    "technical_status": "PASS",
    "formal_f_e7_executed": False,
    "owner_acceptance_required": True,
    "candidate_repository_commit_sha": commit,
    "candidate_repository_tree_sha": tree,
    "foundation_knowledge_evaluation_at_utc": F_E5_TIME,
    "knowledge_bundle_artifact_id": bundle_id,
    "knowledge_bundle_content_sha256": bundle_digest,
    "dependency_count": 16,
    "dependency_validation_passed": True,
    "double_build_deterministic": True,
    "source_states": source_states,
    "evidence_sha256": {
        "knowledge_bundle_json": sha256_file(bundle_path),
        "build_input_manifest": sha256_file(input_manifest_path),
        "validation_report": sha256_file(validation_report_path),
        "per_source_freshness_evaluation": sha256_file(freshness_report_path),
        "retained_artifact_locations": sha256_file(locations_path),
    },
    "continuation_note": (
        "Summary completed after the original predecision run raised KeyError while "
        "reading a non-existent source_artifact_sha256 field from freshness evaluation. "
        "No bundle build, dependency validation, or freshness evaluation was rerun."
    ),
    "production_action": False,
    "next": "OWNER_ACCEPT_EXACT_KNOWLEDGE_BUNDLE",
}

# Use deterministic compact canonical JSON locally; this summary is retained
# evidence, not an ArtifactContent identity.
summary_bytes = json.dumps(
    summary,
    ensure_ascii=True,
    sort_keys=True,
    separators=(",", ":"),
).encode("utf-8")
summary_path.write_bytes(summary_bytes)

if git("status", "--porcelain"):
    fail("CANDIDATE_WORKTREE_DIRTY_AFTER_CONTINUATION")

print("")
print("F_E7_PREDECISION_CONTINUATION_STATUS=PASS")
print("F_E7_PREDECISION_STATUS=PASS")
print("FORMAL_F_E7_EXECUTED=NO")
print("TECHNICAL_CHECKS_RERUN=NO")
print("CANDIDATE_COMMIT=" + commit)
print("CANDIDATE_TREE=" + tree)
print("FOUNDATION_KNOWLEDGE_EVALUATION_AT_UTC=" + F_E5_TIME)
print("DEPENDENCY_COUNT=16")
print("DEPENDENCY_VALIDATION_PASS=TRUE")
print("DOUBLE_BUILD_DETERMINISTIC=TRUE")
print("KNOWLEDGE_BUNDLE_ID=" + bundle_id)
print("KNOWLEDGE_BUNDLE_CONTENT_SHA256=" + bundle_digest)

for slot in ("k1", "k2b", "k4"):
    row = source_states[slot]
    prefix = slot.upper()
    print(prefix + "_SOURCE_SHA256=" + row["source_artifact_sha256"])
    print(prefix + "_RETRIEVED_AT_UTC=" + row["retrieved_at_utc"])
    print(prefix + "_FRESHNESS_STATE=" + row["freshness_state"])
    print(prefix + "_CLAIM_ELIGIBLE=" + str(row["claim_eligible"]).upper())
    print(prefix + "_CLAIM_STRENGTH_CAP=" + row["claim_strength_cap"])

print("KNOWLEDGE_BUNDLE_FILE_SHA256=" + sha256_file(bundle_path))
print("BUILD_INPUT_MANIFEST_SHA256=" + sha256_file(input_manifest_path))
print("VALIDATION_REPORT_SHA256=" + sha256_file(validation_report_path))
print("PER_SOURCE_FRESHNESS_EVALUATION_SHA256=" + sha256_file(freshness_report_path))
print("RETAINED_ARTIFACT_LOCATIONS_SHA256=" + sha256_file(locations_path))
print("PREDECISION_SUMMARY_SHA256=" + sha256_file(summary_path))
print("F_E7_PREDECISION_OUTPUT_DIRECTORY=" + str(OUT))
print("OWNER_ACCEPTANCE_REQUIRED=YES")
print("PRODUCTION_ACTION=NO")
print("NEXT=OWNER_ACCEPT_EXACT_KNOWLEDGE_BUNDLE")
