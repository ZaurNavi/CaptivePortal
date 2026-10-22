#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

sys.dont_write_bytecode = True

ROOT = pathlib.Path(r"C:\CaptivPortal-Lab")
REPO = ROOT / "coder-task04-t09-utility-repair-a1"

EXPECTED_COMMIT = "8a39459be3ce7ed40e325736034245f0025cf249"
EXPECTED_TREE = "e2521f27c9f91978e381bce202ab3e3c83aa6dad"
HISTORICAL_PRE_A1_COMMIT = "74f7c7add401e5fec0469d49770466c2747c03cf"

F_E5_TIME = "2026-10-01T10:25:29.793Z"
F_E5_RUN = (
    ROOT / "official-runs" / "task04" / "f-e5"
    / "official-run-20261001T102529Z-FE5-A1-CURRENT-01"
)
F_E5_GATE_ID = (
    "GateResultManifest:v1:sha256:"
    "fdee6045ea263d722a5e3c571b24515729a3d80173df8e5df93b8277307026c0"
)

EXPECTED_IDS = {
    "taxonomy":
        "ClassificationTaxonomy:v1:sha256:"
        "399e2a337e7ebecb1bd7a9b21dff5e744c13be36313bc39f16832bc7a57a4d10",
    "alias":
        "AliasMapping:v1:sha256:"
        "f1cdd7c9510c2a33bad99bd1ae15eaccd20fcb828a52e02533b9917fdfc2e228",

    "k1_record":
        "CanonicalKnowledgeRecordSet:v1:sha256:"
        "e6a347de462242f6ef70684e33be3bc16d1d11b7e3ced00271e0363ecbbefe5c",
    "k1_prov":
        "KnowledgeProvenanceManifest:v1:sha256:"
        "199176ab51188a95cc9e10a05298b71024d2e194140538a6c3aec1050b70a61d",
    "k1_gov":
        "SourceGovernanceRecord:v1:sha256:"
        "3737b8bae599956ed4738a527a89890b9f74c0b316900f8b49a5bb4695f7a0c1",
    "k1_policy":
        "KnowledgeFreshnessPolicy:v1:sha256:"
        "0d33089e064fc58de96eb0c32789e9382fd2e26d213932cdf370b12b1ec6d3a5",

    "k3_rules":
        "K3PortalRuleSet:v1:sha256:"
        "93ea1f384efe7d1dbbc9c513d09d9e62bdddd9448c0ee070423bc4f54176ed1a",
    "k3_prov":
        "KnowledgeProvenanceManifest:v1:sha256:"
        "ddf14f16eac6a6840e299fde11aafe9489d6bb075e04c3d09d4205e4bd197d15",

    "k4_record":
        "CanonicalKnowledgeRecordSet:v1:sha256:"
        "689f61da6cc8ace5a89677688b685f2a4d479d89bc9582239407d2d42e83536e",
    "k4_prov":
        "KnowledgeProvenanceManifest:v1:sha256:"
        "68c84447525d42946a5a49b42ea9a82093f4da7ff8e8311843e229b444adeb49",
    "k4_gov":
        "SourceGovernanceRecord:v1:sha256:"
        "5f0a3777a274daa4acedec11d29da34bc1fbe1f23e593188fcf8b0d03adf8125",
    "k4_policy":
        "KnowledgeFreshnessPolicy:v1:sha256:"
        "9a3a58d72dfb660b9a639b7558424cd55d213f8306e586c1b263aa4cda0d3df5",

    "k2_gov":
        "SourceGovernanceRecord:v1:sha256:"
        "06c0c3e63404fff1f0a96fec0a264c46b1429a21defaffc5556fb00a0385897c",
    "k2_policy":
        "KnowledgeFreshnessPolicy:v1:sha256:"
        "c509e8343debf97a6295d0a8ed56255d69f724346c2ac20b2955b891614e4f09",
    "k2_prov":
        "KnowledgeProvenanceManifest:v1:sha256:"
        "4638e78d5b85df2247ca7f3e0fbbab7326c9ddbbff719dbe3b9e2468a634627b",
}

P0F_PATH = ROOT / "artifacts" / "fe5-external-governance" / "sources" / "p0f.fp"
P0F_SHA256 = "791444ebf9a97a492b7a94020f721d016584918c437a450ccaa5525a55c95ad0"

# These modules were not part of A1 implementation scope. Pin them against the
# historical exact candidate so this predecision proof cannot silently consume a
# changed F-E7 algorithm.
UNCHANGED_F_E7_FILES = (
    "app/device_fingerprint/knowledge_bundle.py",
    "app/device_fingerprint/fe7_knowledge_bundle.py",
)

SCAN_ROOTS = (
    ROOT / "official-runs" / "task04",
    ROOT / "artifacts",
)


def die(reason: str) -> None:
    print("")
    print("F_E7_PREDECISION_STATUS=FAIL")
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
        die("GIT_FAILURE:" + " ".join(args) + ":" + cp.stderr.strip())
    return cp.stdout.strip()


def artifact_envelope(content: Any) -> dict[str, Any]:
    return {
        "artifact_type": content.artifact_type,
        "artifact_schema_version": content.artifact_schema_version,
        "semantic_payload": content.semantic_payload,
        "content_sha256": content.content_sha256,
        "artifact_id": content.artifact_id,
    }


# ---------------------------------------------------------------------------
# 1. Exact candidate + unchanged F-E7 implementation.
# ---------------------------------------------------------------------------

if not REPO.is_dir():
    die("REPAIRED_REPO_MISSING")

commit = git("rev-parse", "HEAD").lower()
tree = git("rev-parse", "HEAD^{tree}").lower()

if commit != EXPECTED_COMMIT:
    die("CANDIDATE_COMMIT_MISMATCH:" + commit)
if tree != EXPECTED_TREE:
    die("CANDIDATE_TREE_MISMATCH:" + tree)
if git("status", "--porcelain"):
    die("CANDIDATE_WORKTREE_NOT_CLEAN")

for rel in UNCHANGED_F_E7_FILES:
    old_blob = git("rev-parse", f"{HISTORICAL_PRE_A1_COMMIT}:{rel}").lower()
    new_blob = git("rev-parse", f"HEAD:{rel}").lower()
    if old_blob != new_blob:
        die(f"UNEXPECTED_F_E7_IMPLEMENTATION_CHANGE:{rel}:old={old_blob}:new={new_blob}")

# ---------------------------------------------------------------------------
# 2. Import exact candidate validators/builders.
# ---------------------------------------------------------------------------

sys.path.insert(0, str(REPO))

from app.device_fingerprint.artifact_content import (
    ArtifactRef,
    canonical_artifact_json,
    make_artifact_content,
)
from app.device_fingerprint.fe5_external_knowledge import (
    evaluate_external_knowledge_freshness,
)
from app.device_fingerprint.k2b_p0f_import import import_p0f_k2b_bytes
from app.device_fingerprint.knowledge_bundle import (
    KnowledgeBundleCandidate,
    build_initial_knowledge_bundle_v1,
    validate_knowledge_bundle_dependencies,
)

# ---------------------------------------------------------------------------
# 3. Verify exact accepted F-E5 lineage.
# ---------------------------------------------------------------------------

f_e5_gate_path = F_E5_RUN / "gate-result-manifest.json"
if not f_e5_gate_path.is_file():
    die("F_E5_GATE_RESULT_MISSING")

try:
    f_e5_gate_obj = json.loads(f_e5_gate_path.read_text(encoding="utf-8"))
except Exception as exc:
    die("F_E5_GATE_RESULT_PARSE_FAILURE:" + repr(exc))

if f_e5_gate_obj.get("artifact_id") != F_E5_GATE_ID:
    die("F_E5_GATE_RESULT_ID_MISMATCH")

f_e5_payload = f_e5_gate_obj.get("semantic_payload", {})
if f_e5_payload.get("gate_id") != "F-E5" or f_e5_payload.get("status") != "PASS":
    die("F_E5_NOT_ACCEPTED_PASS")
if f_e5_payload.get("candidate_repository_commit_sha") != commit:
    die("F_E5_CANDIDATE_COMMIT_MISMATCH")
if f_e5_payload.get("candidate_repository_tree_sha") != tree:
    die("F_E5_CANDIDATE_TREE_MISMATCH")
if f_e5_payload.get("trusted_time_inputs", {}).get(
    "foundation_knowledge_evaluation_at_utc"
) != F_E5_TIME:
    die("F_E5_TRUSTED_TIME_MISMATCH")

# ---------------------------------------------------------------------------
# 4. Find exact retained artifact envelopes by immutable artifact ID.
# ---------------------------------------------------------------------------

needed_ids = set(EXPECTED_IDS.values())
found: dict[str, tuple[pathlib.Path, dict[str, Any]]] = {}

for scan_root in SCAN_ROOTS:
    if not scan_root.exists():
        continue
    for current, dirs, files in os.walk(scan_root):
        dirs[:] = [
            d for d in dirs
            if d not in {".git", ".venv", "venv", "__pycache__", "node_modules", ".pytest_cache"}
        ]
        for name in files:
            if not name.lower().endswith(".json"):
                continue
            path = pathlib.Path(current) / name
            try:
                # Skip unexpectedly huge JSON evidence; canonical artifact
                # envelopes here are small enough for this bound.
                if path.stat().st_size > 32 * 1024 * 1024:
                    continue
                obj = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            artifact_id = obj.get("artifact_id")
            if artifact_id in needed_ids and artifact_id not in found:
                found[artifact_id] = (path, obj)
        if len(found) == len(needed_ids):
            break
    if len(found) == len(needed_ids):
        break


def load_exact(expected_id: str):
    entry = found.get(expected_id)
    if entry is None:
        die("EXACT_ARTIFACT_NOT_FOUND:" + expected_id)
    path, obj = entry
    if set(("artifact_type", "semantic_payload", "content_sha256", "artifact_id")) - set(obj):
        die("ARTIFACT_ENVELOPE_INCOMPLETE:" + str(path))
    try:
        rebuilt = make_artifact_content(obj["artifact_type"], obj["semantic_payload"])
    except Exception as exc:
        die("ARTIFACT_REBUILD_FAILURE:" + str(path) + ":" + repr(exc))
    if rebuilt.artifact_id != expected_id:
        die("ARTIFACT_ID_REBUILD_MISMATCH:" + str(path))
    if obj["artifact_id"] != rebuilt.artifact_id:
        die("STORED_ARTIFACT_ID_MISMATCH:" + str(path))
    if obj["content_sha256"] != rebuilt.content_sha256:
        die("STORED_ARTIFACT_DIGEST_MISMATCH:" + str(path))
    return rebuilt, path


taxonomy, taxonomy_path = load_exact(EXPECTED_IDS["taxonomy"])
alias, alias_path = load_exact(EXPECTED_IDS["alias"])

k1_record, k1_record_path = load_exact(EXPECTED_IDS["k1_record"])
k1_prov, k1_prov_path = load_exact(EXPECTED_IDS["k1_prov"])
k1_gov, k1_gov_path = load_exact(EXPECTED_IDS["k1_gov"])
k1_policy, k1_policy_path = load_exact(EXPECTED_IDS["k1_policy"])

k3_rules, k3_rules_path = load_exact(EXPECTED_IDS["k3_rules"])
k3_prov, k3_prov_path = load_exact(EXPECTED_IDS["k3_prov"])

k4_record, k4_record_path = load_exact(EXPECTED_IDS["k4_record"])
k4_prov, k4_prov_path = load_exact(EXPECTED_IDS["k4_prov"])
k4_gov, k4_gov_path = load_exact(EXPECTED_IDS["k4_gov"])
k4_policy, k4_policy_path = load_exact(EXPECTED_IDS["k4_policy"])

k2_gov, k2_gov_path = load_exact(EXPECTED_IDS["k2_gov"])
k2_policy, k2_policy_path = load_exact(EXPECTED_IDS["k2_policy"])
k2_prov, k2_prov_path = load_exact(EXPECTED_IDS["k2_prov"])

# ---------------------------------------------------------------------------
# 5. Exact K2B record set from accepted unchanged p0f bytes + accepted provenance.
# ---------------------------------------------------------------------------

if not P0F_PATH.is_file():
    die("PINNED_P0F_SOURCE_MISSING:" + str(P0F_PATH))

p0f_bytes = P0F_PATH.read_bytes()
if hashlib.sha256(p0f_bytes).hexdigest() != P0F_SHA256:
    die("PINNED_P0F_SOURCE_SHA256_MISMATCH")

try:
    k2_import = import_p0f_k2b_bytes(
        p0f_bytes,
        ArtifactRef(k2_prov.artifact_id, k2_prov.content_sha256),
    )
except Exception as exc:
    die("K2B_REIMPORT_FAILURE:" + type(exc).__name__ + ":" + str(exc))

k2_record = k2_import.record_set
if k2_record.semantic_payload.get("knowledge_slot") != "K2B":
    die("K2B_RECORD_SET_SLOT_MISMATCH")
if len(k2_record.semantic_payload.get("records", [])) != 43:
    die("K2B_RECORD_SET_COUNT_MISMATCH")

# ---------------------------------------------------------------------------
# 6. Explicit A1 lineage invariants.
# ---------------------------------------------------------------------------

k3pp = k3_prov.semantic_payload
if k3pp.get("repository_commit_sha") != commit:
    die("K3_PROVENANCE_COMMIT_MISMATCH")
if k3pp.get("repository_tree_sha") != tree:
    die("K3_PROVENANCE_TREE_MISMATCH")
if k3pp.get("rule_set_artifact") != ArtifactRef(
    k3_rules.artifact_id, k3_rules.content_sha256
).as_dict():
    die("K3_PROVENANCE_RULE_SET_REF_MISMATCH")
if k3pp.get("taxonomy_compatibility") != ArtifactRef(
    taxonomy.artifact_id, taxonomy.content_sha256
).as_dict():
    die("K3_PROVENANCE_TAXONOMY_REF_MISMATCH")

# ---------------------------------------------------------------------------
# 7. Build exact 16-dependency KnowledgeBundle candidate.
# ---------------------------------------------------------------------------

candidate = KnowledgeBundleCandidate(
    classification_taxonomy=taxonomy,
    alias_mapping=alias,
    k1_record_set=k1_record,
    k1_provenance=k1_prov,
    k1_governance=k1_gov,
    k1_freshness_policy=k1_policy,
    k2b_record_set=k2_record,
    k2b_provenance=k2_prov,
    k2b_governance=k2_gov,
    k2b_freshness_policy=k2_policy,
    k3_portal_rule_set=k3_rules,
    k3_provenance=k3_prov,
    k4_record_set=k4_record,
    k4_provenance=k4_prov,
    k4_governance=k4_gov,
    k4_freshness_policy=k4_policy,
)

try:
    bundle_1 = build_initial_knowledge_bundle_v1(candidate)
    bundle_2 = build_initial_knowledge_bundle_v1(candidate)
except Exception as exc:
    die("KNOWLEDGE_BUNDLE_BUILD_FAILURE:" + type(exc).__name__ + ":" + str(exc))

if bundle_1.artifact_id != bundle_2.artifact_id:
    die("DOUBLE_BUILD_ARTIFACT_ID_MISMATCH")
if bundle_1.content_sha256 != bundle_2.content_sha256:
    die("DOUBLE_BUILD_CONTENT_SHA256_MISMATCH")
if bundle_1.semantic_payload_json != bundle_2.semantic_payload_json:
    die("DOUBLE_BUILD_CANONICAL_BYTES_MISMATCH")

try:
    deps_ok = validate_knowledge_bundle_dependencies(bundle_1, candidate)
except Exception as exc:
    die("KNOWLEDGE_BUNDLE_DEPENDENCY_VALIDATION_FAILURE:" + type(exc).__name__ + ":" + str(exc))

if deps_ok is not True:
    die("KNOWLEDGE_BUNDLE_DEPENDENCY_VALIDATION_NOT_TRUE")

# ---------------------------------------------------------------------------
# 8. Re-evaluate external-source usability at exact inherited F-E5 time.
#    F-E7 MUST NOT observe a replacement current clock.
# ---------------------------------------------------------------------------

freshness = {}
for slot, provenance, policy in (
    ("k1", k1_prov, k1_policy),
    ("k2b", k2_prov, k2_policy),
    ("k4", k4_prov, k4_policy),
):
    try:
        row = evaluate_external_knowledge_freshness(
            provenance,
            policy,
            knowledge_evaluation_at_utc=F_E5_TIME,
        )
    except Exception as exc:
        die(f"{slot.upper()}_FRESHNESS_EVALUATION_FAILURE:"
            + type(exc).__name__ + ":" + str(exc))
    freshness[slot] = row
    if row.get("age_ms", -1) < 0:
        die(slot.upper() + "_NEGATIVE_SOURCE_AGE")
    if row.get("failure_code") is not None:
        die(slot.upper() + "_FRESHNESS_FAILURE_CODE:" + str(row.get("failure_code")))
    if row.get("claim_eligible") is not True:
        die(slot.upper() + "_NOT_CLAIM_ELIGIBLE_AT_F_E5_TIME")
    if row.get("freshness_state") == "expired":
        die(slot.upper() + "_EXPIRED_AT_F_E5_TIME")

expected_states = {
    "k1": ("fresh", "NO_ADDITIONAL_CAP"),
    "k2b": ("stale", "supporting"),
    "k4": ("fresh", "NO_ADDITIONAL_CAP"),
}
for slot, (state, cap) in expected_states.items():
    row = freshness[slot]
    if row.get("freshness_state") != state:
        die(
            f"{slot.upper()}_UNEXPECTED_FRESHNESS_STATE:"
            f"{row.get('freshness_state')}:expected={state}"
        )
    if row.get("claim_strength_cap") != cap:
        die(
            f"{slot.upper()}_UNEXPECTED_CLAIM_STRENGTH_CAP:"
            f"{row.get('claim_strength_cap')}:expected={cap}"
        )

# ---------------------------------------------------------------------------
# 9. Exact distinct dependency inventory = 16.
# ---------------------------------------------------------------------------

dependency_artifacts = (
    taxonomy, alias,
    k1_record, k1_prov, k1_gov, k1_policy,
    k2_record, k2_prov, k2_gov, k2_policy,
    k3_rules, k3_prov,
    k4_record, k4_prov, k4_gov, k4_policy,
)
dependency_ids = sorted(a.artifact_id for a in dependency_artifacts)

if len(dependency_ids) != 16:
    die("DEPENDENCY_COUNT_NOT_SIXTEEN")
if len(set(dependency_ids)) != 16:
    die("DEPENDENCY_IDENTITIES_NOT_DISTINCT")

# ---------------------------------------------------------------------------
# 10. Retain predecision technical proof. No formal F-E7 gate yet.
# ---------------------------------------------------------------------------

stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
OUT = (
    ROOT / "official-runs" / "task04" / "f-e7"
    / ("predecision-build-" + stamp + "-FE7-A1-01")
)
if OUT.exists():
    die("PREDECISION_OUTPUT_ALREADY_EXISTS")
OUT.mkdir(parents=True)

bundle_path = OUT / "knowledge-bundle.json"
bundle_path.write_bytes(canonical_artifact_json(artifact_envelope(bundle_1)))

input_manifest = {
    "proof_contract": "captivportal.fe7.a1.predecision_input_manifest.v1",
    "candidate_repository_commit_sha": commit,
    "candidate_repository_tree_sha": tree,
    "foundation_knowledge_evaluation_at_utc": F_E5_TIME,
    "source_f_e5_gate_result_id": F_E5_GATE_ID,
    "dependency_artifact_ids": dependency_ids,
    "dependency_count": len(dependency_ids),
    "raw_vendor_runtime_dependencies": [],
    "ja4_semantic_slot_present": False,
    "production_action": False,
}
input_manifest_path = OUT / "build-input-manifest.json"
input_manifest_path.write_bytes(canonical_artifact_json(input_manifest))

validation_report = {
    "proof_contract": "captivportal.fe7.a1.predecision_validation.v1",
    "double_build_identity_equal": True,
    "double_build_content_sha256_equal": True,
    "double_build_canonical_bytes_equal": True,
    "dependency_validation_passed": True,
    "knowledge_bundle_artifact_id": bundle_1.artifact_id,
    "knowledge_bundle_content_sha256": bundle_1.content_sha256,
    "build_1_artifact_id": bundle_1.artifact_id,
    "build_1_content_sha256": bundle_1.content_sha256,
    "build_2_artifact_id": bundle_2.artifact_id,
    "build_2_content_sha256": bundle_2.content_sha256,
    "production_action": False,
}
validation_report_path = OUT / "validation-report.json"
validation_report_path.write_bytes(canonical_artifact_json(validation_report))

freshness_report = {
    "proof_contract": "captivportal.fe7.a1.inherited_freshness_evaluation.v1",
    "foundation_knowledge_evaluation_at_utc": F_E5_TIME,
    "clock_observed_by_f_e7": False,
    "per_source": [
        {"slot": slot, **freshness[slot]}
        for slot in ("k1", "k2b", "k4")
    ],
    "production_action": False,
}
freshness_report_path = OUT / "per-source-freshness-evaluation.json"
freshness_report_path.write_bytes(canonical_artifact_json(freshness_report))

artifact_locations = {
    "proof_contract": "captivportal.fe7.a1.retained_artifact_locations.v1",
    "locations": {
        "taxonomy": str(taxonomy_path),
        "alias": str(alias_path),
        "k1_record": str(k1_record_path),
        "k1_provenance": str(k1_prov_path),
        "k1_governance": str(k1_gov_path),
        "k1_freshness_policy": str(k1_policy_path),
        "k2b_p0f_source": str(P0F_PATH),
        "k2b_provenance": str(k2_prov_path),
        "k2b_governance": str(k2_gov_path),
        "k2b_freshness_policy": str(k2_policy_path),
        "k3_rule_set": str(k3_rules_path),
        "k3_provenance": str(k3_prov_path),
        "k4_record": str(k4_record_path),
        "k4_provenance": str(k4_prov_path),
        "k4_governance": str(k4_gov_path),
        "k4_freshness_policy": str(k4_policy_path),
        "f_e5_gate_result": str(f_e5_gate_path),
    },
    "production_action": False,
}
artifact_locations_path = OUT / "retained-artifact-locations.json"
artifact_locations_path.write_bytes(canonical_artifact_json(artifact_locations))

summary = {
    "run_schema_version": 1,
    "phase": "F-E7_PREDECISION_TECHNICAL_BUILD",
    "technical_status": "PASS",
    "formal_f_e7_executed": False,
    "owner_acceptance_required": True,
    "candidate_repository_commit_sha": commit,
    "candidate_repository_tree_sha": tree,
    "foundation_knowledge_evaluation_at_utc": F_E5_TIME,
    "knowledge_bundle_artifact_id": bundle_1.artifact_id,
    "knowledge_bundle_content_sha256": bundle_1.content_sha256,
    "dependency_count": 16,
    "dependency_validation_passed": True,
    "double_build_deterministic": True,
    "source_states": {
        slot: {
            "source_artifact_sha256": freshness[slot]["source_artifact_sha256"],
            "retrieved_at_utc": freshness[slot]["retrieved_at_utc"],
            "age_ms": freshness[slot]["age_ms"],
            "freshness_state": freshness[slot]["freshness_state"],
            "claim_eligible": freshness[slot]["claim_eligible"],
            "claim_strength_cap": freshness[slot]["claim_strength_cap"],
        }
        for slot in ("k1", "k2b", "k4")
    },
    "evidence_sha256": {
        "knowledge_bundle_json": sha256_file(bundle_path),
        "build_input_manifest": sha256_file(input_manifest_path),
        "validation_report": sha256_file(validation_report_path),
        "per_source_freshness_evaluation": sha256_file(freshness_report_path),
        "retained_artifact_locations": sha256_file(artifact_locations_path),
    },
    "production_action": False,
    "next": "OWNER_ACCEPT_EXACT_KNOWLEDGE_BUNDLE",
}
summary_path = OUT / "predecision-summary.json"
summary_path.write_bytes(canonical_artifact_json(summary))

if git("status", "--porcelain"):
    die("CANDIDATE_WORKTREE_DIRTY_AFTER_PREDECISION_BUILD")

print("")
print("F_E7_PREDECISION_STATUS=PASS")
print("FORMAL_F_E7_EXECUTED=NO")
print("CANDIDATE_COMMIT=" + commit)
print("CANDIDATE_TREE=" + tree)
print("FOUNDATION_KNOWLEDGE_EVALUATION_AT_UTC=" + F_E5_TIME)
print("DEPENDENCY_COUNT=16")
print("DEPENDENCY_VALIDATION_PASS=TRUE")
print("DOUBLE_BUILD_DETERMINISTIC=TRUE")
print("KNOWLEDGE_BUNDLE_ID=" + bundle_1.artifact_id)
print("KNOWLEDGE_BUNDLE_CONTENT_SHA256=" + bundle_1.content_sha256)
print("K2B_RECORD_SET_ID=" + k2_record.artifact_id)
print("K2B_RECORD_SET_CONTENT_SHA256=" + k2_record.content_sha256)

for slot in ("k1", "k2b", "k4"):
    row = freshness[slot]
    prefix = slot.upper()
    print(prefix + "_FRESHNESS_STATE=" + row["freshness_state"])
    print(prefix + "_CLAIM_ELIGIBLE=" + str(row["claim_eligible"]).upper())
    print(prefix + "_CLAIM_STRENGTH_CAP=" + row["claim_strength_cap"])

print("KNOWLEDGE_BUNDLE_FILE_SHA256=" + sha256_file(bundle_path))
print("BUILD_INPUT_MANIFEST_SHA256=" + sha256_file(input_manifest_path))
print("VALIDATION_REPORT_SHA256=" + sha256_file(validation_report_path))
print("PER_SOURCE_FRESHNESS_EVALUATION_SHA256=" + sha256_file(freshness_report_path))
print("PREDECISION_SUMMARY_SHA256=" + sha256_file(summary_path))
print("F_E7_PREDECISION_OUTPUT_DIRECTORY=" + str(OUT))
print("OWNER_ACCEPTANCE_REQUIRED=YES")
print("PRODUCTION_ACTION=NO")
print("NEXT=OWNER_ACCEPT_EXACT_KNOWLEDGE_BUNDLE")
