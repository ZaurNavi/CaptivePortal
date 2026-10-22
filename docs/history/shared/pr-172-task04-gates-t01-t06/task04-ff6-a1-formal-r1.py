#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import platform
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

sys.dont_write_bytecode = True

ROOT = pathlib.Path(r"C:\CaptivPortal-Lab")
REPO = ROOT / "coder-task04-t09-utility-repair-a1"

EXPECTED_COMMIT = "8a39459be3ce7ed40e325736034245f0025cf249"
EXPECTED_TREE = "e2521f27c9f91978e381bce202ab3e3c83aa6dad"

HISTORICAL_FF6_ROOT = (
    ROOT / "artifacts" / "ff6-real-acceptance-b419ab3"
)
HISTORICAL_GATE_PATH = (
    HISTORICAL_FF6_ROOT / "ff6-gate-result-manifest.json"
)
HISTORICAL_PROOF_PATH = (
    HISTORICAL_FF6_ROOT / "ff6-gate-proof-artifact.json"
)
HISTORICAL_MATERIALIZED = (
    HISTORICAL_FF6_ROOT / "materialized"
)

EXPECTED_HISTORICAL_GATE_ID = (
    "GateResultManifest:v1:sha256:"
    "b157b62dc3f0bedd6fc6b1124658ea02d079e5a06013c4521e5c364d78262292"
)
EXPECTED_HISTORICAL_PROOF_ID = (
    "GateProofArtifact:v1:sha256:"
    "7b52b74baa2868505def90b2555a80b082ee4e2b27734a2292d5e3e002078896"
)
EXPECTED_HISTORICAL_COMMIT = "b419ab357a267be3c62096a6ed45b67dad4889f2"
EXPECTED_HISTORICAL_TREE = "9a9b66cb86e2001d6bf25a2f48d787f85a804061"
EXPECTED_HISTORICAL_INPUT_COUNT = 45
EXPECTED_CURRENT_INPUT_COUNT = 45
EXPECTED_REPLACEMENT_COUNT = 9

BASELINE_REF = "74f7c7add401e5fec0469d49770466c2747c03cf"
UNCHANGED_PATHS = (
    "app/device_fingerprint/ff6_artifact_graph_acyclicity.py",
    "app/device_fingerprint/artifact_dependency_graph.py",
    "tests/device_fingerprint_ff6/test_ff6_artifact_graph_acyclicity.py",
)

OLD_EACS_ID = (
    "EvidenceAdapterContractSet:v1:sha256:"
    "7cca6802ebc5839317643dcb584173b75d985477da687ab0d8fe5802b181f788"
)
NEW_EACS_ID = (
    "EvidenceAdapterContractSet:v1:sha256:"
    "c9711a816fddae6a8d22f2a07c8561fc363c76f7b39f95cde62b66d9957ef32f"
)

OLD_POLICY_ID = (
    "ClassificationPolicy:v1:sha256:"
    "6341a9f9781ead1b1ab5ba2065b7eda6c0c77b4d8736db2eae6a04ef881daf3e"
)
NEW_POLICY_ID = (
    "ClassificationPolicy:v1:sha256:"
    "5d6c6edab7cfb88bcb42d4badf9bd53dc78f458eae12b4e8b05878fb7f3256c8"
)

OLD_KB_ID = (
    "KnowledgeBundle:v1:sha256:"
    "d2d7297aaad7e9312b083d5fe1046b02697ae08757dde9545f6d068e209c7939"
)
NEW_KB_ID = (
    "KnowledgeBundle:v1:sha256:"
    "70c39dcb9ebca5b07f80b0846c394b244c6f700fc4c738e43625f767de0eb660"
)

CURRENT_ARTIFACT_PATHS = {
    # K1
    "k1_governance": (
        ROOT / "official-runs" / "task04" / "a1-k1-materialization-evidence"
        / "repair-20261001T075732Z" / "k1-source-governance.json"
    ),
    "k1_freshness": (
        ROOT / "official-runs" / "task04" / "a1-k1-materialization-evidence"
        / "repair-20261001T075732Z" / "k1-freshness-policy.json"
    ),
    "k1_provenance": (
        ROOT / "official-runs" / "task04" / "a1-k1-materialization-evidence"
        / "repair-20261001T075732Z" / "k1-provenance-v2.json"
    ),
    "k1_record_set": (
        ROOT / "official-runs" / "task04" / "a1-k1-materialization-evidence"
        / "repair-20261001T075732Z" / "k1-record-set-v2.json"
    ),

    # K3
    "k3_rule_set": (
        ROOT / "official-runs" / "task04" / "f-e3"
        / "official-run-20261001T082752Z-FE3-A1"
        / "k3-portal-rule-set.json"
    ),
    "k3_provenance": (
        ROOT / "official-runs" / "task04" / "f-e3"
        / "official-run-20261001T082752Z-FE3-A1"
        / "k3-internal-provenance.json"
    ),

    # K4
    "k4_governance": (
        ROOT / "official-runs" / "task04" / "f-e4"
        / "official-run-20261001T101057Z-FE4-A1-K4-REFRESH-R2"
        / "k4-source-governance.json"
    ),
    "k4_freshness": (
        ROOT / "official-runs" / "task04" / "f-e4"
        / "official-run-20261001T101057Z-FE4-A1-K4-REFRESH-R2"
        / "k4-freshness-policy.json"
    ),
    "k4_provenance": (
        ROOT / "official-runs" / "task04" / "f-e4"
        / "official-run-20261001T101057Z-FE4-A1-K4-REFRESH-R2"
        / "k4-provenance-refreshed.json"
    ),
    "k4_record_set": (
        ROOT / "official-runs" / "task04" / "f-e4"
        / "official-run-20261001T101057Z-FE4-A1-K4-REFRESH-R2"
        / "k4-record-set-refreshed.json"
    ),

    # Bundle / adapters / policy
    "knowledge_bundle": (
        ROOT / "official-runs" / "task04" / "f-e7"
        / "predecision-build-20261001T103557Z-FE7-A1-01"
        / "knowledge-bundle.json"
    ),
    "eacs": (
        ROOT / "official-runs" / "task04" / "f-f1"
        / "official-run-20261001T105634Z-FF1-A1-01"
        / "evidence-adapter-contract-set-a1.json"
    ),
    "classification_policy": (
        ROOT / "official-runs" / "task04" / "f-f2"
        / "official-run-20261001T111321Z-FF2-A1-02"
        / "classification-policy-a1.json"
    ),
}

EXPECTED_CURRENT_IDS = {
    "k1_governance":
        "SourceGovernanceRecord:v1:sha256:"
        "3737b8bae599956ed4738a527a89890b9f74c0b316900f8b49a5bb4695f7a0c1",
    "k1_freshness":
        "KnowledgeFreshnessPolicy:v1:sha256:"
        "0d33089e064fc58de96eb0c32789e9382fd2e26d213932cdf370b12b1ec6d3a5",
    "k1_provenance":
        "KnowledgeProvenanceManifest:v1:sha256:"
        "199176ab51188a95cc9e10a05298b71024d2e194140538a6c3aec1050b70a61d",
    "k1_record_set":
        "CanonicalKnowledgeRecordSet:v1:sha256:"
        "e6a347de462242f6ef70684e33be3bc16d1d11b7e3ced00271e0363ecbbefe5c",
    "k3_rule_set":
        "K3PortalRuleSet:v1:sha256:"
        "93ea1f384efe7d1dbbc9c513d09d9e62bdddd9448c0ee070423bc4f54176ed1a",
    "k3_provenance":
        "KnowledgeProvenanceManifest:v1:sha256:"
        "ddf14f16eac6a6840e299fde11aafe9489d6bb075e04c3d09d4205e4bd197d15",
    "k4_governance":
        "SourceGovernanceRecord:v1:sha256:"
        "5f0a3777a274daa4acedec11d29da34bc1fbe1f23e593188fcf8b0d03adf8125",
    "k4_freshness":
        "KnowledgeFreshnessPolicy:v1:sha256:"
        "9a3a58d72dfb660b9a639b7558424cd55d213f8306e586c1b263aa4cda0d3df5",
    "k4_provenance":
        "KnowledgeProvenanceManifest:v1:sha256:"
        "68c84447525d42946a5a49b42ea9a82093f4da7ff8e8311843e229b444adeb49",
    "k4_record_set":
        "CanonicalKnowledgeRecordSet:v1:sha256:"
        "689f61da6cc8ace5a89677688b685f2a4d479d89bc9582239407d2d42e83536e",
    "knowledge_bundle": NEW_KB_ID,
    "eacs": NEW_EACS_ID,
    "classification_policy": NEW_POLICY_ID,
}


def fail(reason: str, *, exit_code: int = 1) -> None:
    print("")
    print("F_F6_FORMAL_GATE_EXECUTED=NO")
    print("F_F6_FORMAL_STATUS=FAIL")
    print("REASON=" + reason)
    print("PRODUCTION_ACTION=NO")
    raise SystemExit(exit_code)


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


def read_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail("JSON_READ_FAILURE:" + str(path) + ":" + type(exc).__name__)
    if not isinstance(obj, dict):
        fail("JSON_NOT_OBJECT:" + str(path))
    return obj


def write_json(path: pathlib.Path, value: Any) -> None:
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )


def artifact_document(content) -> dict[str, Any]:
    return {
        "artifact_id": content.artifact_id,
        "artifact_schema_version": content.artifact_schema_version,
        "artifact_type": content.artifact_type,
        "content_sha256": content.content_sha256,
        "semantic_payload": content.semantic_payload,
    }


def ref_ids(rows: Any) -> set[str]:
    if not isinstance(rows, list):
        fail("REF_SET_NOT_LIST")
    result = set()
    for row in rows:
        if (
            not isinstance(row, dict)
            or set(row) != {"artifact_id", "content_sha256"}
            or not isinstance(row["artifact_id"], str)
        ):
            fail("INVALID_ARTIFACT_REF")
        result.add(row["artifact_id"])
    return result


def exact_artifact_from_file(path: pathlib.Path, make_artifact_content):
    if not path.is_file():
        fail("ARTIFACT_FILE_MISSING:" + str(path))
    obj = read_json(path)
    required = {
        "artifact_id",
        "artifact_schema_version",
        "artifact_type",
        "content_sha256",
        "semantic_payload",
    }
    if set(obj) != required:
        fail("ARTIFACT_FILE_SHAPE_INVALID:" + str(path))
    if obj["artifact_schema_version"] != 1:
        fail("ARTIFACT_SCHEMA_VERSION_INVALID:" + str(path))
    content = make_artifact_content(
        obj["artifact_type"],
        obj["semantic_payload"],
    )
    if (
        content.artifact_id != obj["artifact_id"]
        or content.content_sha256 != obj["content_sha256"]
    ):
        fail("ARTIFACT_IDENTITY_INVALID:" + str(path))
    return content


# ---------------------------------------------------------------------------
# 1. Exact candidate + clean worktree.
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

# F-F6 implementation surface was outside A1 source delta.
for rel in UNCHANGED_PATHS:
    current_blob = git("rev-parse", "HEAD:" + rel)
    baseline_blob = git("rev-parse", BASELINE_REF + ":" + rel)
    if current_blob != baseline_blob:
        fail(
            "F_F6_IMPLEMENTATION_SURFACE_CHANGED:"
            + rel
            + ":current="
            + current_blob
            + ":baseline="
            + baseline_blob
        )

sys.path.insert(0, str(REPO))

from app.device_fingerprint.artifact_content import make_artifact_content
from app.device_fingerprint.ff6_artifact_graph_acyclicity import (
    execute_ff6_artifact_graph_acyclicity_candidate,
    run_ff6_artifact_graph_acyclicity_gate,
)

# ---------------------------------------------------------------------------
# 2. Historical accepted F-F6 anchors.
# ---------------------------------------------------------------------------

for required in (
    HISTORICAL_GATE_PATH,
    HISTORICAL_PROOF_PATH,
    HISTORICAL_MATERIALIZED,
):
    if not required.exists():
        fail("HISTORICAL_F_F6_ANCHOR_MISSING:" + str(required))

hist_gate = exact_artifact_from_file(
    HISTORICAL_GATE_PATH,
    make_artifact_content,
)
hist_proof = exact_artifact_from_file(
    HISTORICAL_PROOF_PATH,
    make_artifact_content,
)

if hist_gate.artifact_id != EXPECTED_HISTORICAL_GATE_ID:
    fail("HISTORICAL_GATE_ID_MISMATCH")

if hist_proof.artifact_id != EXPECTED_HISTORICAL_PROOF_ID:
    fail("HISTORICAL_PROOF_ID_MISMATCH")

hist_gate_payload = hist_gate.semantic_payload

if hist_gate_payload.get("gate_id") != "F-F6":
    fail("HISTORICAL_GATE_NOT_F_F6")

if hist_gate_payload.get("status") != "PASS":
    fail("HISTORICAL_GATE_NOT_PASS")

if (
    hist_gate_payload.get("candidate_repository_commit_sha")
    != EXPECTED_HISTORICAL_COMMIT
):
    fail("HISTORICAL_GATE_COMMIT_MISMATCH")

if (
    hist_gate_payload.get("candidate_repository_tree_sha")
    != EXPECTED_HISTORICAL_TREE
):
    fail("HISTORICAL_GATE_TREE_MISMATCH")

historical_input_refs = hist_gate_payload.get("input_artifact_refs")
historical_input_ids = ref_ids(historical_input_refs)

if len(historical_input_ids) != EXPECTED_HISTORICAL_INPUT_COUNT:
    fail(
        "HISTORICAL_INPUT_COUNT_MISMATCH:"
        + str(len(historical_input_ids))
    )

if OLD_KB_ID not in historical_input_ids:
    fail("HISTORICAL_OLD_KB_MISSING")
if OLD_EACS_ID not in historical_input_ids:
    fail("HISTORICAL_OLD_EACS_MISSING")
if OLD_POLICY_ID not in historical_input_ids:
    fail("HISTORICAL_OLD_POLICY_MISSING")

# ---------------------------------------------------------------------------
# 3. Resolve the exact 45 historical ArtifactContent files.
#    The historical materialized directory is the authoritative local corpus
#    produced for the accepted b419ab3 F-F6 run.
# ---------------------------------------------------------------------------

historical_by_id = {}
historical_path_by_id = {}

for path in sorted(
    HISTORICAL_MATERIALIZED.rglob("*.json"),
    key=lambda p: str(p).lower(),
):
    obj = read_json(path)
    artifact_keys = {
        "artifact_id",
        "artifact_schema_version",
        "artifact_type",
        "content_sha256",
        "semantic_payload",
    }

    # The historical directory is allowed to contain auxiliary retained JSON.
    # Only exact ArtifactContent wrapper shapes participate in the identity
    # index; auxiliary files are evidence, not candidate graph nodes.
    if set(obj) != artifact_keys:
        continue

    content = exact_artifact_from_file(
        path,
        make_artifact_content,
    )
    aid = content.artifact_id
    if aid in historical_by_id:
        # Same semantic identity may exist twice only if exact ArtifactContent
        # reconstructs to the same identity; retain the lexicographically first
        # path for evidence provenance.
        continue
    historical_by_id[aid] = content
    historical_path_by_id[aid] = str(path.resolve())

missing_hist = sorted(
    historical_input_ids.difference(historical_by_id)
)

if missing_hist:
    print("MISSING_HISTORICAL_IDS=" + ",".join(missing_hist))
    fail("HISTORICAL_MATERIALIZED_INVENTORY_INCOMPLETE")

historical_contents = {
    aid: historical_by_id[aid]
    for aid in historical_input_ids
}

# Historical gate input ref must match reconstructed content exactly.
for ref in historical_input_refs:
    content = historical_contents[ref["artifact_id"]]
    if content.content_sha256 != ref["content_sha256"]:
        fail(
            "HISTORICAL_INPUT_DIGEST_MISMATCH:"
            + ref["artifact_id"]
        )

# ---------------------------------------------------------------------------
# 4. Load exact current A1 artifacts from already-executed formal/evidence runs.
# ---------------------------------------------------------------------------

current = {}
current_source_paths = {}

for role, path in CURRENT_ARTIFACT_PATHS.items():
    content = exact_artifact_from_file(
        path,
        make_artifact_content,
    )
    expected = EXPECTED_CURRENT_IDS[role]
    if content.artifact_id != expected:
        fail(
            "CURRENT_A1_ID_MISMATCH:"
            + role
            + ":actual="
            + content.artifact_id
            + ":expected="
            + expected
        )
    current[role] = content
    current_source_paths[content.artifact_id] = str(path.resolve())

new_kb = current["knowledge_bundle"]
old_kb = historical_contents[OLD_KB_ID]

old_kb_payload = old_kb.semantic_payload
new_kb_payload = new_kb.semantic_payload

# Taxonomy / alias / K2B / governance / freshness are intentionally unchanged.
for field in (
    "classification_taxonomy",
    "alias_mapping",
    "k2b_record_set",
):
    if old_kb_payload[field] != new_kb_payload[field]:
        fail("UNEXPECTED_KB_COMMON_REF_DELTA:" + field)

if (
    old_kb_payload["source_governance_records"]
    != new_kb_payload["source_governance_records"]
):
    fail("UNEXPECTED_KB_GOVERNANCE_SET_DELTA")

if (
    old_kb_payload["knowledge_freshness_policies"]
    != new_kb_payload["knowledge_freshness_policies"]
):
    fail("UNEXPECTED_KB_FRESHNESS_SET_DELTA")

# Exact K1/K3/K4 current slot replacements.
slot_replacements = {
    old_kb_payload["k1_record_set"]["artifact_id"]:
        new_kb_payload["k1_record_set"]["artifact_id"],
    old_kb_payload["k3_portal_rule_set"]["artifact_id"]:
        new_kb_payload["k3_portal_rule_set"]["artifact_id"],
    old_kb_payload["k4_record_set"]["artifact_id"]:
        new_kb_payload["k4_record_set"]["artifact_id"],
}

old_provenance_ids = ref_ids(
    old_kb_payload["knowledge_provenance_manifests"]
)
new_provenance_ids = ref_ids(
    new_kb_payload["knowledge_provenance_manifests"]
)

old_only_provenance = sorted(
    old_provenance_ids - new_provenance_ids
)
new_only_provenance = sorted(
    new_provenance_ids - old_provenance_ids
)
common_provenance = sorted(
    old_provenance_ids & new_provenance_ids
)

# K2B provenance is the one unchanged provenance identity.
if len(common_provenance) != 1:
    fail(
        "UNEXPECTED_COMMON_PROVENANCE_COUNT:"
        + str(len(common_provenance))
    )

if len(old_only_provenance) != 3:
    fail(
        "UNEXPECTED_OLD_ONLY_PROVENANCE_COUNT:"
        + str(len(old_only_provenance))
    )

if len(new_only_provenance) != 3:
    fail(
        "UNEXPECTED_NEW_ONLY_PROVENANCE_COUNT:"
        + str(len(new_only_provenance))
    )

expected_new_provenance_ids = {
    current["k1_provenance"].artifact_id,
    current["k3_provenance"].artifact_id,
    current["k4_provenance"].artifact_id,
}

if set(new_only_provenance) != expected_new_provenance_ids:
    fail("NEW_PROVENANCE_SET_DOES_NOT_MATCH_A1_ARTIFACTS")

# Ensure new KB references the exact A1 slot artifacts.
if (
    new_kb_payload["k1_record_set"]["artifact_id"]
    != current["k1_record_set"].artifact_id
):
    fail("NEW_KB_K1_RECORD_REF_MISMATCH")

if (
    new_kb_payload["k3_portal_rule_set"]["artifact_id"]
    != current["k3_rule_set"].artifact_id
):
    fail("NEW_KB_K3_RULE_REF_MISMATCH")

if (
    new_kb_payload["k4_record_set"]["artifact_id"]
    != current["k4_record_set"].artifact_id
):
    fail("NEW_KB_K4_RECORD_REF_MISMATCH")

# A1 retained governance/freshness identities are byte-independent semantic
# identities already present in historical graph; verify current copies match.
for role in (
    "k1_governance",
    "k1_freshness",
    "k4_governance",
    "k4_freshness",
):
    if current[role].artifact_id not in historical_input_ids:
        fail("UNCHANGED_A1_DEPENDENCY_NOT_IN_HISTORICAL_GRAPH:" + role)

# ---------------------------------------------------------------------------
# 5. Exact nine one-for-one replacements.
# ---------------------------------------------------------------------------

old_replaced_ids = {
    OLD_KB_ID,
    OLD_EACS_ID,
    OLD_POLICY_ID,
    *slot_replacements.keys(),
    *old_only_provenance,
}

new_replacement_ids = {
    NEW_KB_ID,
    NEW_EACS_ID,
    NEW_POLICY_ID,
    *slot_replacements.values(),
    *new_only_provenance,
}

if len(old_replaced_ids) != EXPECTED_REPLACEMENT_COUNT:
    fail(
        "OLD_REPLACEMENT_COUNT_MISMATCH:"
        + str(len(old_replaced_ids))
    )

if len(new_replacement_ids) != EXPECTED_REPLACEMENT_COUNT:
    fail(
        "NEW_REPLACEMENT_COUNT_MISMATCH:"
        + str(len(new_replacement_ids))
    )

if not old_replaced_ids.issubset(historical_input_ids):
    fail("OLD_REPLACEMENTS_NOT_SUBSET_OF_HISTORICAL_GRAPH")

# Map every new replacement identity to exact loaded current ArtifactContent.
current_by_id = {
    content.artifact_id: content
    for content in current.values()
}

missing_new_contents = sorted(
    new_replacement_ids.difference(current_by_id)
)

if missing_new_contents:
    print("MISSING_NEW_CONTENTS=" + ",".join(missing_new_contents))
    fail("NEW_REPLACEMENT_CONTENT_NOT_LOADED")

candidate_by_id = {
    aid: content
    for aid, content in historical_contents.items()
    if aid not in old_replaced_ids
}

for aid in sorted(new_replacement_ids):
    candidate_by_id[aid] = current_by_id[aid]

if len(candidate_by_id) != EXPECTED_CURRENT_INPUT_COUNT:
    fail(
        "CURRENT_CANDIDATE_INPUT_COUNT_MISMATCH:"
        + str(len(candidate_by_id))
    )

candidate_ids = set(candidate_by_id)

if old_replaced_ids & candidate_ids:
    fail("SUPERSEDED_A1_IDENTITIES_REMAIN_IN_CURRENT_GRAPH")

if not new_replacement_ids.issubset(candidate_ids):
    fail("A1_REPLACEMENT_IDENTITIES_MISSING_FROM_CURRENT_GRAPH")

# The unchanged K2B provenance remains exactly the common provenance identity.
if common_provenance[0] not in candidate_ids:
    fail("UNCHANGED_K2B_PROVENANCE_MISSING")

# Every direct new-KB dependency must be present before F-F6 is called.
new_kb_direct_ids = {
    new_kb_payload["classification_taxonomy"]["artifact_id"],
    new_kb_payload["alias_mapping"]["artifact_id"],
    new_kb_payload["k1_record_set"]["artifact_id"],
    new_kb_payload["k2b_record_set"]["artifact_id"],
    new_kb_payload["k3_portal_rule_set"]["artifact_id"],
    new_kb_payload["k4_record_set"]["artifact_id"],
    *ref_ids(new_kb_payload["knowledge_provenance_manifests"]),
    *ref_ids(new_kb_payload["source_governance_records"]),
    *ref_ids(new_kb_payload["knowledge_freshness_policies"]),
}

missing_kb_dependencies = sorted(
    new_kb_direct_ids.difference(candidate_ids)
)

if missing_kb_dependencies:
    print(
        "MISSING_NEW_KB_DIRECT_DEPENDENCIES="
        + ",".join(missing_kb_dependencies)
    )
    fail("NEW_KB_DIRECT_DEPENDENCY_CLOSURE_INCOMPLETE")

# ---------------------------------------------------------------------------
# 6. Focused unchanged F-F6 tests on exact A1 candidate.
# ---------------------------------------------------------------------------

stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
OUT = (
    ROOT / "official-runs" / "task04" / "f-f6"
    / ("official-run-" + stamp + "-FF6-A1-01")
)

if OUT.exists():
    fail("F_F6_OUTPUT_ALREADY_EXISTS")

OUT.mkdir(parents=True)

pytest_log = OUT / "pytest-f-f6.txt"
pytest_tmp = ROOT / "tmp" / ("task04-ff6-a1-pytest-" + stamp)
pycache = ROOT / "tmp" / ("task04-ff6-a1-pyc-" + stamp)

env = os.environ.copy()
env["PYTHONPYCACHEPREFIX"] = str(pycache)

cp = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "--basetemp",
        str(pytest_tmp),
        "tests/device_fingerprint_ff6/test_ff6_artifact_graph_acyclicity.py",
    ],
    cwd=str(REPO),
    env=env,
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
    fail("F_F6_FOCUSED_PYTEST_FAILED")

if git("status", "--porcelain"):
    fail("CANDIDATE_WORKTREE_DIRTY_AFTER_PYTEST")

# ---------------------------------------------------------------------------
# 7. Execute real current-candidate F-F6.
# ---------------------------------------------------------------------------

candidate_contents = tuple(
    candidate_by_id[aid]
    for aid in sorted(candidate_by_id)
)

execution = execute_ff6_artifact_graph_acyclicity_candidate(
    concrete_artifact_contents=candidate_contents,
    candidate_repository_commit_sha=commit,
    candidate_repository_tree_sha=tree,
)

if execution.failure_reasons:
    print(
        "F_F6_EXECUTION_FAILURE_REASONS="
        + ",".join(execution.failure_reasons)
    )

if not all(execution.checks.values()):
    failed_checks = sorted(
        name
        for name, passed in execution.checks.items()
        if not passed
    )
    print(
        "F_F6_FAILED_CHECKS="
        + ",".join(failed_checks)
    )

if len(execution.concrete_artifact_refs) != EXPECTED_CURRENT_INPUT_COUNT:
    fail(
        "F_F6_EXECUTION_REF_COUNT_MISMATCH:"
        + str(len(execution.concrete_artifact_refs))
    )

if (
    len(execution.concrete_graph["nodes"])
    != EXPECTED_CURRENT_INPUT_COUNT
):
    fail(
        "F_F6_CONCRETE_NODE_COUNT_MISMATCH:"
        + str(len(execution.concrete_graph["nodes"]))
    )

if (
    len(execution.topological_orderings["concrete"])
    != EXPECTED_CURRENT_INPUT_COUNT
):
    fail("F_F6_TOPOLOGICAL_ORDER_COUNT_MISMATCH")

# ---------------------------------------------------------------------------
# 8. Retained evidence required by R14 F-F6.
# ---------------------------------------------------------------------------

graph_path = OUT / "artifact-dependency-graph.json"
cycles_path = OUT / "artifact-cycle-test-fixtures.json"
ordering_path = OUT / "artifact-topological-ordering.json"
inventory_path = OUT / "f-f6-input-inventory.json"

write_json(
    graph_path,
    {
        "candidate_repository_commit_sha": commit,
        "candidate_repository_tree_sha": tree,
        "execution_mode": execution.execution_mode,
        "concrete_graph": execution.concrete_graph,
        "foundation_template_graph":
            execution.foundation_template_graph,
        "task04_template_graph":
            execution.task04_template_graph,
        "checks": execution.checks,
        "failure_reasons": list(execution.failure_reasons),
    },
)

write_json(
    cycles_path,
    {
        "candidate_repository_commit_sha": commit,
        "candidate_repository_tree_sha": tree,
        "cycle_test_fixtures":
            execution.cycle_test_fixtures,
    },
)

write_json(
    ordering_path,
    {
        "candidate_repository_commit_sha": commit,
        "candidate_repository_tree_sha": tree,
        "topological_orderings":
            execution.topological_orderings,
    },
)

replacement_rows = []

for old_id in sorted(old_replaced_ids):
    new_id = None

    if old_id == OLD_KB_ID:
        new_id = NEW_KB_ID
    elif old_id == OLD_EACS_ID:
        new_id = NEW_EACS_ID
    elif old_id == OLD_POLICY_ID:
        new_id = NEW_POLICY_ID
    elif old_id in slot_replacements:
        new_id = slot_replacements[old_id]
    elif old_id in old_only_provenance:
        # Provenance set is SET-like; role mapping is proven by new KB +
        # exact current artifacts, not guessed from historical ordering.
        new_id = "SET_REPLACED_BY_CURRENT_PROVENANCE_SET"

    replacement_rows.append(
        {
            "old_artifact_id": old_id,
            "new_artifact_id_or_set_marker": new_id,
        }
    )

write_json(
    inventory_path,
    {
        "inventory_contract":
            "captivportal.task04.a1.ff6.current_candidate.v1",
        "historical_gate_result_id":
            hist_gate.artifact_id,
        "historical_gate_path":
            str(HISTORICAL_GATE_PATH.resolve()),
        "historical_proof_id":
            hist_proof.artifact_id,
        "historical_input_count":
            len(historical_input_ids),
        "current_input_count":
            len(candidate_ids),
        "replacement_count":
            len(old_replaced_ids),
        "old_replaced_artifact_ids":
            sorted(old_replaced_ids),
        "new_replacement_artifact_ids":
            sorted(new_replacement_ids),
        "replacement_rows":
            replacement_rows,
        "common_unchanged_provenance_ids":
            common_provenance,
        "current_candidate_artifact_ids":
            sorted(candidate_ids),
        "historical_materialized_paths": {
            aid: historical_path_by_id[aid]
            for aid in sorted(historical_input_ids)
        },
        "current_a1_source_paths":
            current_source_paths,
        "old_kb_artifact_id":
            old_kb.artifact_id,
        "new_kb_artifact_id":
            new_kb.artifact_id,
        "new_kb_direct_dependency_ids":
            sorted(new_kb_direct_ids),
        "superseded_identity_intersection_with_current":
            sorted(old_replaced_ids & candidate_ids),
        "production_action":
            False,
    },
)

def evidence_ref(
    label: str,
    path: pathlib.Path,
    media_type: str,
) -> dict[str, Any]:
    return {
        "evidence_label": label,
        "file_sha256": sha256_file(path),
        "media_type": media_type,
        "path_or_reference": str(path.resolve()),
    }

retained_evidence = [
    evidence_ref(
        "artifact_dependency_graph",
        graph_path,
        "application/json",
    ),
    evidence_ref(
        "artifact_cycle_test_fixtures",
        cycles_path,
        "application/json",
    ),
    evidence_ref(
        "artifact_topological_ordering",
        ordering_path,
        "application/json",
    ),
    evidence_ref(
        "a1_candidate_input_inventory",
        inventory_path,
        "application/json",
    ),
    evidence_ref(
        "f_f6_focused_pytest",
        pytest_log,
        "text/plain",
    ),
    evidence_ref(
        "historical_f_f6_pass_manifest",
        HISTORICAL_GATE_PATH,
        "application/json",
    ),
    evidence_ref(
        "historical_f_f6_pass_proof",
        HISTORICAL_PROOF_PATH,
        "application/json",
    ),
]

environment_identity = (
    "windows;"
    + "python="
    + platform.python_version()
    + ";platform="
    + platform.platform()
)

gate = run_ff6_artifact_graph_acyclicity_gate(
    execution,
    candidate_repository_commit_sha=commit,
    candidate_repository_tree_sha=tree,
    environment_identity=environment_identity,
    retained_evidence_refs=retained_evidence,
)

proof = gate.gate_proof_artifact
manifest = gate.gate_result_manifest
status = manifest.semantic_payload["status"]

proof_path = OUT / "gate-proof-artifact.json"
manifest_path = OUT / "gate-result-manifest.json"
summary_path = OUT / "formal-run-summary.json"

write_json(proof_path, artifact_document(proof))
write_json(manifest_path, artifact_document(manifest))

summary = {
    "run_contract":
        "captivportal.task04.a1.ff6.formal.v1",
    "gate_id":
        "F-F6",
    "gate_contract_version":
        manifest.semantic_payload["gate_contract_version"],
    "status":
        status,
    "candidate_repository_commit_sha":
        commit,
    "candidate_repository_tree_sha":
        tree,
    "historical_gate_result_id":
        hist_gate.artifact_id,
    "historical_input_count":
        len(historical_input_ids),
    "a1_replacement_count":
        len(old_replaced_ids),
    "current_input_count":
        len(candidate_ids),
    "all_checks_pass":
        all(execution.checks.values()),
    "failure_reasons":
        list(gate.failure_reasons),
    "concrete_topological_order_count":
        len(execution.topological_orderings["concrete"]),
    "cycle_regression_fixture_count":
        len(execution.cycle_test_fixtures),
    "required_cycle_regressions_pass": {
        key: execution.checks[key]
        for key in (
            "gate_output_cycle_regression_detected",
            "runtime_profile_lineage_cycle_regression_detected",
            "capability_gate_cycle_regression_detected",
            "knowledge_freshness_provenance_cycle_regression_detected",
            "mutual_artifact_cycle_regression_detected",
        )
    },
    "gate_proof_artifact_id":
        proof.artifact_id,
    "gate_result_manifest_id":
        manifest.artifact_id,
    "gate_result_manifest_content_sha256":
        manifest.content_sha256,
    "gate_result_manifest_file_sha256":
        sha256_file(manifest_path),
    "gate_proof_file_sha256":
        sha256_file(proof_path),
    "pytest_log_sha256":
        sha256_file(pytest_log),
    "inventory_sha256":
        sha256_file(inventory_path),
    "graph_sha256":
        sha256_file(graph_path),
    "cycles_sha256":
        sha256_file(cycles_path),
    "ordering_sha256":
        sha256_file(ordering_path),
    "production_action":
        False,
}

write_json(summary_path, summary)

if git("status", "--porcelain"):
    fail("CANDIDATE_WORKTREE_DIRTY_AFTER_F_F6")

# ---------------------------------------------------------------------------
# 9. Formal outcome.
# ---------------------------------------------------------------------------

print("")
print("F_F6_FORMAL_GATE_EXECUTED=YES")
print("F_F6_FORMAL_STATUS=" + status)
print("CANDIDATE_COMMIT=" + commit)
print("CANDIDATE_TREE=" + tree)
print(
    "HISTORICAL_F_F6_GATE_RESULT_ID="
    + hist_gate.artifact_id
)
print(
    "HISTORICAL_F_F6_PROOF_ID="
    + hist_proof.artifact_id
)
print(
    "HISTORICAL_INPUT_ARTIFACT_COUNT="
    + str(len(historical_input_ids))
)
print(
    "A1_REPLACEMENT_COUNT="
    + str(len(old_replaced_ids))
)
print(
    "CURRENT_INPUT_ARTIFACT_COUNT="
    + str(len(candidate_ids))
)
print(
    "SUPERSEDED_IDENTITIES_PRESENT="
    + ("YES" if old_replaced_ids & candidate_ids else "NO")
)
print(
    "ALL_F_F6_CHECKS_PASS="
    + ("YES" if all(execution.checks.values()) else "NO")
)
print(
    "CONCRETE_TOPOLOGICAL_ORDER_COUNT="
    + str(len(execution.topological_orderings["concrete"]))
)
print(
    "CYCLE_REGRESSIONS_5_OF_5="
    + (
        "YES"
        if all(
            execution.checks[key]
            for key in (
                "gate_output_cycle_regression_detected",
                "runtime_profile_lineage_cycle_regression_detected",
                "capability_gate_cycle_regression_detected",
                "knowledge_freshness_provenance_cycle_regression_detected",
                "mutual_artifact_cycle_regression_detected",
            )
        )
        else "NO"
    )
)
print(
    "F_F6_GATE_PROOF_ID="
    + proof.artifact_id
)
print(
    "F_F6_GATE_RESULT_ID="
    + manifest.artifact_id
)
print(
    "F_F6_GATE_RESULT_CONTENT_SHA256="
    + manifest.content_sha256
)
print(
    "F_F6_GATE_RESULT_FILE_SHA256="
    + sha256_file(manifest_path)
)
print(
    "F_F6_GATE_PROOF_FILE_SHA256="
    + sha256_file(proof_path)
)
print(
    "F_F6_INPUT_INVENTORY_SHA256="
    + sha256_file(inventory_path)
)
print(
    "F_F6_DEPENDENCY_GRAPH_SHA256="
    + sha256_file(graph_path)
)
print(
    "F_F6_CYCLE_FIXTURES_SHA256="
    + sha256_file(cycles_path)
)
print(
    "F_F6_TOPOLOGICAL_ORDERING_SHA256="
    + sha256_file(ordering_path)
)
print(
    "F_F6_PYTEST_LOG_SHA256="
    + sha256_file(pytest_log)
)
print(
    "F_F6_FORMAL_RUN_SUMMARY_SHA256="
    + sha256_file(summary_path)
)
print(
    "F_F6_OUTPUT_DIRECTORY="
    + str(OUT.resolve())
)
print("OWNER_DECISION_REQUIRED=NO")
print("PRODUCTION_ACTION=NO")

if status == "PASS":
    print("NEXT=TASK04_T01")
    raise SystemExit(0)

print(
    "F_F6_FAILURE_REASONS="
    + ",".join(gate.failure_reasons)
)
print("NEXT=STOP_AND_REVIEW_F_F6_FAILURE")
raise SystemExit(1)
