#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

sys.dont_write_bytecode = True

ROOT = pathlib.Path(r"C:\CaptivPortal-Lab")
REPO = ROOT / "coder-task04-t09-utility-repair-a1"

PRE = (
    ROOT / "official-runs" / "task04" / "f-e7"
    / "predecision-build-20261001T103557Z-FE7-A1-01"
)

F_E5_RUN = (
    ROOT / "official-runs" / "task04" / "f-e5"
    / "official-run-20261001T102529Z-FE5-A1-CURRENT-01"
)

EXPECTED_COMMIT = "8a39459be3ce7ed40e325736034245f0025cf249"
EXPECTED_TREE = "e2521f27c9f91978e381bce202ab3e3c83aa6dad"

EXPECTED_BUNDLE_ID = (
    "KnowledgeBundle:v1:sha256:"
    "70c39dcb9ebca5b07f80b0846c394b244c6f700fc4c738e43625f767de0eb660"
)
EXPECTED_BUNDLE_DIGEST = (
    "70c39dcb9ebca5b07f80b0846c394b244c6f700fc4c738e43625f767de0eb660"
)

F_E5_TIME = "2026-10-01T10:25:29.793Z"
F_E5_GATE_ID = (
    "GateResultManifest:v1:sha256:"
    "fdee6045ea263d722a5e3c571b24515729a3d80173df8e5df93b8277307026c0"
)

EXPECTED_EVIDENCE_SHA = {
    "knowledge-bundle.json":
        "1267fdadae251286153c5749a37c78b13cea2e5c33e658e52a5d5e032cb79410",
    "build-input-manifest.json":
        "9af864e3615fc68addba019fc5034fcb46d155a5bf855e4620db921f884a1a53",
    "validation-report.json":
        "1da4c8aa9a5fbe3f261165ef99351f90dba391ccb945e460270c63c7267d03a2",
    "per-source-freshness-evaluation.json":
        "1e4bc2f22464a2ccf486d99af0d2d301a32703f0ac56e60d39dcfeb3bbe77522",
    "retained-artifact-locations.json":
        "403cd070c7a8eeabdafdc3ced98be38cbb844e3fa56d6ddd243c1058c6f2a342",
    "predecision-summary.json":
        "07829bf320ebb50978f39bb559dbcd731e0730ba61adeac292c3bbf45e693378",
}

# Owner explicitly accepted this exact bundle in the current conversation.
OWNER_ACCEPTANCE_TEXT = (
    "Owner explicitly confirms and accepts exact KnowledgeBundle "
    "KnowledgeBundle:v1:sha256:"
    "70c39dcb9ebca5b07f80b0846c394b244c6f700fc4c738e43625f767de0eb660 "
    "for FOUNDATION F-E7 under R14 / TASK-04 T-09 Utility Repair A1. "
    "No production activation is authorized."
)


def fail(reason: str) -> None:
    print("")
    print("F_E7_FORMAL_FINALIZATION=FAIL")
    print("F_E7_FORMAL_STATUS=NOT_EMITTED")
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
        fail("RETAINED_EVIDENCE_MISSING:" + str(path))
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail("RETAINED_EVIDENCE_PARSE_FAILURE:" + str(path) + ":" + repr(exc))
    if not isinstance(obj, dict):
        fail("RETAINED_EVIDENCE_NOT_OBJECT:" + str(path))
    return obj


def evidence_ref(label: str, path: pathlib.Path, media_type: str) -> dict[str, Any]:
    if not path.is_file():
        fail("RETAINED_EVIDENCE_MISSING:" + str(path))
    return {
        "evidence_label": label,
        "file_sha256": sha256_file(path),
        "media_type": media_type,
        "path_or_reference": str(path),
    }


def digest_from_artifact_id(artifact_id: str) -> str:
    if not isinstance(artifact_id, str):
        fail("INVALID_ARTIFACT_ID_TYPE")
    parts = artifact_id.split(":")
    if len(parts) != 4 or parts[1] != "v1" or parts[2] != "sha256":
        fail("INVALID_ARTIFACT_ID:" + artifact_id)
    digest = parts[3]
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        fail("INVALID_ARTIFACT_DIGEST:" + artifact_id)
    return digest


# ---------------------------------------------------------------------------
# 1. Exact candidate / clean tree.
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
    fail("CANDIDATE_WORKTREE_NOT_CLEAN")

# ---------------------------------------------------------------------------
# 2. Import canonical artifact/gate utilities only.
#    No bundle build or freshness evaluation is executed here.
# ---------------------------------------------------------------------------

sys.path.insert(0, str(REPO))

from app.device_fingerprint.artifact_content import (
    ArtifactRef,
    canonical_artifact_json,
    make_artifact_content,
)
from app.device_fingerprint.foundation_gate_artifacts import (
    make_gate_result_manifest,
)
from app.device_fingerprint.validation import format_utc

# ---------------------------------------------------------------------------
# 3. Pin exact retained predecision evidence by hashes already emitted.
# ---------------------------------------------------------------------------

if not PRE.is_dir():
    fail("F_E7_PREDECISION_DIRECTORY_MISSING")

for filename, expected_sha in EXPECTED_EVIDENCE_SHA.items():
    path = PRE / filename
    if not path.is_file():
        fail("PREDECISION_EVIDENCE_MISSING:" + filename)
    actual_sha = sha256_file(path)
    if actual_sha != expected_sha:
        fail(
            "PREDECISION_EVIDENCE_SHA_MISMATCH:"
            + filename
            + ":expected="
            + expected_sha
            + ":actual="
            + actual_sha
        )

bundle_path = PRE / "knowledge-bundle.json"
manifest_path = PRE / "build-input-manifest.json"
validation_path = PRE / "validation-report.json"
freshness_path = PRE / "per-source-freshness-evaluation.json"
locations_path = PRE / "retained-artifact-locations.json"
predecision_summary_path = PRE / "predecision-summary.json"

bundle_obj = load_json(bundle_path)
manifest = load_json(manifest_path)
validation = load_json(validation_path)
freshness = load_json(freshness_path)
predecision_summary = load_json(predecision_summary_path)

# ---------------------------------------------------------------------------
# 4. Validate retained technical PASS without rerunning technical work.
# ---------------------------------------------------------------------------

if manifest.get("candidate_repository_commit_sha") != commit:
    fail("PREDECISION_MANIFEST_COMMIT_MISMATCH")
if manifest.get("candidate_repository_tree_sha") != tree:
    fail("PREDECISION_MANIFEST_TREE_MISMATCH")
if manifest.get("foundation_knowledge_evaluation_at_utc") != F_E5_TIME:
    fail("PREDECISION_MANIFEST_TRUSTED_TIME_MISMATCH")
if manifest.get("source_f_e5_gate_result_id") != F_E5_GATE_ID:
    fail("PREDECISION_MANIFEST_F_E5_GATE_MISMATCH")
if manifest.get("dependency_count") != 16:
    fail("PREDECISION_DEPENDENCY_COUNT_MISMATCH")

dependency_ids = manifest.get("dependency_artifact_ids")
if (
    not isinstance(dependency_ids, list)
    or len(dependency_ids) != 16
    or len(set(dependency_ids)) != 16
):
    fail("PREDECISION_DEPENDENCY_SET_INVALID")

if validation.get("double_build_identity_equal") is not True:
    fail("PREDECISION_DOUBLE_BUILD_IDENTITY_NOT_PASS")
if validation.get("double_build_content_sha256_equal") is not True:
    fail("PREDECISION_DOUBLE_BUILD_DIGEST_NOT_PASS")
if validation.get("double_build_canonical_bytes_equal") is not True:
    fail("PREDECISION_DOUBLE_BUILD_BYTES_NOT_PASS")
if validation.get("dependency_validation_passed") is not True:
    fail("PREDECISION_DEPENDENCY_VALIDATION_NOT_PASS")

if validation.get("knowledge_bundle_artifact_id") != EXPECTED_BUNDLE_ID:
    fail("PREDECISION_BUNDLE_ID_MISMATCH")
if validation.get("knowledge_bundle_content_sha256") != EXPECTED_BUNDLE_DIGEST:
    fail("PREDECISION_BUNDLE_DIGEST_MISMATCH")

if freshness.get("foundation_knowledge_evaluation_at_utc") != F_E5_TIME:
    fail("PREDECISION_FRESHNESS_TIME_MISMATCH")
if freshness.get("clock_observed_by_f_e7") is not False:
    fail("PREDECISION_USED_NEW_F_E7_CLOCK")

if predecision_summary.get("technical_status") != "PASS":
    fail("PREDECISION_SUMMARY_NOT_PASS")
if predecision_summary.get("formal_f_e7_executed") is not False:
    fail("PREDECISION_SUMMARY_CLAIMS_FORMAL_EXECUTION")
if predecision_summary.get("knowledge_bundle_artifact_id") != EXPECTED_BUNDLE_ID:
    fail("PREDECISION_SUMMARY_BUNDLE_ID_MISMATCH")
if predecision_summary.get("knowledge_bundle_content_sha256") != EXPECTED_BUNDLE_DIGEST:
    fail("PREDECISION_SUMMARY_BUNDLE_DIGEST_MISMATCH")

# Reconstruct the exact retained bundle ArtifactContent and canonical bytes.
try:
    rebuilt_bundle = make_artifact_content(
        bundle_obj["artifact_type"],
        bundle_obj["semantic_payload"],
    )
except Exception as exc:
    fail("RETAINED_BUNDLE_REBUILD_FAILURE:" + type(exc).__name__ + ":" + str(exc))

if rebuilt_bundle.artifact_id != EXPECTED_BUNDLE_ID:
    fail("RETAINED_BUNDLE_ARTIFACT_ID_MISMATCH")
if rebuilt_bundle.content_sha256 != EXPECTED_BUNDLE_DIGEST:
    fail("RETAINED_BUNDLE_CONTENT_DIGEST_MISMATCH")
if bundle_obj.get("artifact_id") != rebuilt_bundle.artifact_id:
    fail("STORED_BUNDLE_ARTIFACT_ID_MISMATCH")
if bundle_obj.get("content_sha256") != rebuilt_bundle.content_sha256:
    fail("STORED_BUNDLE_CONTENT_DIGEST_MISMATCH")
if canonical_artifact_json(bundle_obj) != bundle_path.read_bytes():
    fail("RETAINED_BUNDLE_NONCANONICAL")

# ---------------------------------------------------------------------------
# 5. Pin accepted F-E5 predecessor exactly.
# ---------------------------------------------------------------------------

f_e5_gate_path = F_E5_RUN / "gate-result-manifest.json"
f_e5_gate = load_json(f_e5_gate_path)

if f_e5_gate.get("artifact_id") != F_E5_GATE_ID:
    fail("F_E5_GATE_ID_MISMATCH")

f_e5_payload = f_e5_gate.get("semantic_payload")
if not isinstance(f_e5_payload, dict):
    fail("F_E5_GATE_PAYLOAD_MISSING")
if f_e5_payload.get("gate_id") != "F-E5":
    fail("F_E5_GATE_NAME_MISMATCH")
if f_e5_payload.get("status") != "PASS":
    fail("F_E5_NOT_PASS")
if f_e5_payload.get("candidate_repository_commit_sha") != commit:
    fail("F_E5_COMMIT_MISMATCH")
if f_e5_payload.get("candidate_repository_tree_sha") != tree:
    fail("F_E5_TREE_MISMATCH")
if f_e5_payload.get("trusted_time_inputs", {}).get(
    "foundation_knowledge_evaluation_at_utc"
) != F_E5_TIME:
    fail("F_E5_TRUSTED_TIME_MISMATCH")

# ---------------------------------------------------------------------------
# 6. OWNER DecisionRecord for the exact materialized bundle.
# ---------------------------------------------------------------------------

stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
OUT = (
    ROOT / "official-runs" / "task04" / "f-e7"
    / ("official-run-" + stamp + "-FE7-A1-FINAL")
)

if OUT.exists():
    fail("F_E7_FORMAL_OUTPUT_ALREADY_EXISTS")

OUT.mkdir(parents=True)

decision_id = str(uuid.uuid4())
decided_at = format_utc(datetime.now(timezone.utc))

decision_base = {
    "decision_record_id": decision_id,
    "decision_subject_type": "KnowledgeBundle",
    "decision_subject_id": EXPECTED_BUNDLE_ID,
    "decision": "ACCEPT",
    "decided_at_utc": decided_at,
    "actor_role": "OWNER",
    "referenced_artifact_ids": [
        EXPECTED_BUNDLE_ID,
        F_E5_GATE_ID,
    ],
    "referenced_gate_ids": [
        "F-E5",
        "F-E7",
    ],
    "reason_reference_text": OWNER_ACCEPTANCE_TEXT,
}

decision_hash = hashlib.sha256(
    canonical_artifact_json(decision_base)
).hexdigest()

decision = {
    **decision_base,
    "record_sha256": decision_hash,
}

decision_path = OUT / "owner-decision-record.json"
decision_path.write_bytes(canonical_artifact_json(decision))

# ---------------------------------------------------------------------------
# 7. Formal GateResultManifest(F-E7=PASS).
#    Input refs are exact 16 dependencies retained by predecision proof.
# ---------------------------------------------------------------------------

input_refs = [
    {
        "artifact_id": artifact_id,
        "content_sha256": digest_from_artifact_id(artifact_id),
    }
    for artifact_id in sorted(dependency_ids)
]

if len(input_refs) != 16:
    fail("FORMAL_F_E7_INPUT_REF_COUNT_NOT_SIXTEEN")

script_path = pathlib.Path(__file__).resolve()

retained = [
    evidence_ref(
        "F-E7_PREDECISION_KNOWLEDGE_BUNDLE",
        bundle_path,
        "application/json",
    ),
    evidence_ref(
        "F-E7_PREDECISION_BUILD_INPUT_MANIFEST",
        manifest_path,
        "application/json",
    ),
    evidence_ref(
        "F-E7_PREDECISION_VALIDATION_REPORT",
        validation_path,
        "application/json",
    ),
    evidence_ref(
        "F-E7_PREDECISION_INHERITED_FRESHNESS_EVALUATION",
        freshness_path,
        "application/json",
    ),
    evidence_ref(
        "F-E7_PREDECISION_RETAINED_ARTIFACT_LOCATIONS",
        locations_path,
        "application/json",
    ),
    evidence_ref(
        "F-E7_PREDECISION_SUMMARY",
        predecision_summary_path,
        "application/json",
    ),
    evidence_ref(
        "F-E7_PREDECESSOR_F_E5_GATE_RESULT",
        f_e5_gate_path,
        "application/json",
    ),
    evidence_ref(
        "F-E7_OWNER_DECISION_RECORD",
        decision_path,
        "application/json",
    ),
]

gate = make_gate_result_manifest({
    "gate_id": "F-E7",
    "gate_contract_version": "R14-F-E7-v1",
    "status": "PASS",

    "candidate_repository_commit_sha": commit,
    "candidate_repository_tree_sha": tree,

    "input_artifact_refs": input_refs,

    "output_artifact_refs": [
        ArtifactRef(
            EXPECTED_BUNDLE_ID,
            EXPECTED_BUNDLE_DIGEST,
        ).as_dict(),
    ],

    "retained_evidence_refs": retained,

    "proof_execution_identity": {
        "execution_id": str(uuid.uuid4()),
        "executor_kind": "TECHLEAD_GATE_TOOL",
        "repository_commit_sha": commit,
        "repository_tree_sha": tree,
        "procedure_or_test_suite_id":
            "F-E7-A1-formal-finalizer-from-predecision-v1",
        "environment_identity":
            "CaptivPortal-Lab-Windows-F-E7-A1-FINAL",
        "execution_artifact_sha256":
            sha256_file(script_path),
    },

    "trusted_time_inputs": {
        "foundation_knowledge_evaluation_at_utc":
            F_E5_TIME,
        "foundation_admission_evaluation_at_utc":
            None,
        "knowledge_evaluation_at_utc":
            None,
    },

    "decision_record_refs": [
        decision_id,
    ],
})

gp = gate.semantic_payload

if gp.get("status") != "PASS":
    fail("F_E7_GATE_STATUS_NOT_PASS")
if gp.get("gate_id") != "F-E7":
    fail("F_E7_GATE_ID_NOT_F_E7")
if gp.get("candidate_repository_commit_sha") != commit:
    fail("F_E7_GATE_COMMIT_MISMATCH")
if gp.get("candidate_repository_tree_sha") != tree:
    fail("F_E7_GATE_TREE_MISMATCH")
if len(gp.get("input_artifact_refs", [])) != 16:
    fail("F_E7_GATE_INPUT_REF_COUNT_MISMATCH")
if gp.get("output_artifact_refs") != [
    ArtifactRef(EXPECTED_BUNDLE_ID, EXPECTED_BUNDLE_DIGEST).as_dict()
]:
    fail("F_E7_GATE_OUTPUT_REF_MISMATCH")
if gp.get("trusted_time_inputs", {}).get(
    "foundation_knowledge_evaluation_at_utc"
) != F_E5_TIME:
    fail("F_E7_GATE_TRUSTED_TIME_MISMATCH")
if gp.get("decision_record_refs") != [decision_id]:
    fail("F_E7_GATE_OWNER_DECISION_NOT_BOUND")

gate_obj = {
    "artifact_type": gate.artifact_type,
    "artifact_schema_version": gate.artifact_schema_version,
    "semantic_payload": gate.semantic_payload,
    "content_sha256": gate.content_sha256,
    "artifact_id": gate.artifact_id,
}

gate_path = OUT / "gate-result-manifest.json"
gate_path.write_bytes(canonical_artifact_json(gate_obj))

# ---------------------------------------------------------------------------
# 8. Formal summary.
# ---------------------------------------------------------------------------

summary = {
    "run_schema_version": 1,
    "gate_id": "F-E7",
    "formal_status": "PASS",

    "candidate_repository_commit_sha": commit,
    "candidate_repository_tree_sha": tree,

    "foundation_knowledge_evaluation_at_utc":
        F_E5_TIME,

    "knowledge_bundle_artifact_id":
        EXPECTED_BUNDLE_ID,

    "knowledge_bundle_content_sha256":
        EXPECTED_BUNDLE_DIGEST,

    "technical_proof_reused":
        True,

    "technical_checks_rerun":
        False,

    "dependency_count":
        16,

    "owner_decision_record_id":
        decision_id,

    "owner_decision_record_sha256":
        decision_hash,

    "gate_result_id":
        gate.artifact_id,

    "gate_result_content_sha256":
        gate.content_sha256,

    "gate_result_file_sha256":
        sha256_file(gate_path),

    "predecision_summary_sha256":
        EXPECTED_EVIDENCE_SHA["predecision-summary.json"],

    "production_action":
        False,

    "next":
        "F-F1",
}

summary_path = OUT / "formal-run-summary.json"
summary_path.write_bytes(canonical_artifact_json(summary))

if git("status", "--porcelain"):
    fail("CANDIDATE_WORKTREE_DIRTY_AFTER_F_E7_FINALIZATION")

# ---------------------------------------------------------------------------
# 9. Final output.
# ---------------------------------------------------------------------------

print("")
print("F_E7_OWNER_DECISION=ACCEPT")
print("OWNER_DECISION_RECORD_ID=" + decision_id)
print("OWNER_DECISION_RECORD_SHA256=" + decision_hash)
print("OWNER_DECISION_RECORD_FILE_SHA256=" + sha256_file(decision_path))

print("F_E7_FORMAL_STATUS=PASS")
print("CANDIDATE_COMMIT=" + commit)
print("CANDIDATE_TREE=" + tree)

print("FOUNDATION_KNOWLEDGE_EVALUATION_AT_UTC=" + F_E5_TIME)
print("DEPENDENCY_COUNT=16")
print("TECHNICAL_PROOF_REUSED=YES")
print("TECHNICAL_CHECKS_RERUN=NO")

print("KNOWLEDGE_BUNDLE_ID=" + EXPECTED_BUNDLE_ID)
print("KNOWLEDGE_BUNDLE_CONTENT_SHA256=" + EXPECTED_BUNDLE_DIGEST)

print("F_E7_GATE_RESULT_ID=" + gate.artifact_id)
print("F_E7_GATE_RESULT_CONTENT_SHA256=" + gate.content_sha256)
print("F_E7_GATE_RESULT_FILE_SHA256=" + sha256_file(gate_path))

print("F_E7_FORMAL_RUN_SUMMARY_SHA256=" + sha256_file(summary_path))
print("F_E7_OUTPUT_DIRECTORY=" + str(OUT))

print("FOUNDATION_RUNTIME_PROFILE_CHANGE=NO")
print("PRODUCTION_ACTION=NO")
print("NEXT=F-F1")
