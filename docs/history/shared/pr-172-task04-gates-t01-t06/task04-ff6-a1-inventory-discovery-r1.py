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

HISTORICAL_INITIAL_ARTIFACT_DIR = (
    ROOT / "artifacts" / "fe7-real-admission-20260924-102919" / "artifacts"
)

SEARCH_ROOTS = (
    ROOT / "official-runs",
    ROOT / "artifacts",
)

TARGET_EVIDENCE_LABELS = {
    "artifact_dependency_graph",
    "artifact_cycle_test_fixtures",
    "artifact_topological_ordering",
}

A1_CURRENT_IDS = {
    "K1_GOVERNANCE":
        "SourceGovernanceRecord:v1:sha256:"
        "3737b8bae599956ed4738a527a89890b9f74c0b316900f8b49a5bb4695f7a0c1",
    "K1_FRESHNESS":
        "KnowledgeFreshnessPolicy:v1:sha256:"
        "0d33089e064fc58de96eb0c32789e9382fd2e26d213932cdf370b12b1ec6d3a5",
    "K1_PROVENANCE":
        "KnowledgeProvenanceManifest:v1:sha256:"
        "199176ab51188a95cc9e10a05298b71024d2e194140538a6c3aec1050b70a61d",
    "K1_RECORD_SET":
        "CanonicalKnowledgeRecordSet:v1:sha256:"
        "e6a347de462242f6ef70684e33be3bc16d1d11b7e3ced00271e0363ecbbefe5c",

    "K3_RULE_SET":
        "K3PortalRuleSet:v1:sha256:"
        "93ea1f384efe7d1dbbc9c513d09d9e62bdddd9448c0ee070423bc4f54176ed1a",
    "K3_PROVENANCE":
        "KnowledgeProvenanceManifest:v1:sha256:"
        "ddf14f16eac6a6840e299fde11aafe9489d6bb075e04c3d09d4205e4bd197d15",

    "K4_GOVERNANCE":
        "SourceGovernanceRecord:v1:sha256:"
        "5f0a3777a274daa4acedec11d29da34bc1fbe1f23e593188fcf8b0d03adf8125",
    "K4_FRESHNESS":
        "KnowledgeFreshnessPolicy:v1:sha256:"
        "9a3a58d72dfb660b9a639b7558424cd55d213f8306e586c1b263aa4cda0d3df5",
    "K4_PROVENANCE":
        "KnowledgeProvenanceManifest:v1:sha256:"
        "68c84447525d42946a5a49b42ea9a82093f4da7ff8e8311843e229b444adeb49",
    "K4_RECORD_SET":
        "CanonicalKnowledgeRecordSet:v1:sha256:"
        "689f61da6cc8ace5a89677688b685f2a4d479d89bc9582239407d2d42e83536e",

    "KNOWLEDGE_BUNDLE":
        "KnowledgeBundle:v1:sha256:"
        "70c39dcb9ebca5b07f80b0846c394b244c6f700fc4c738e43625f767de0eb660",

    "EACS":
        "EvidenceAdapterContractSet:v1:sha256:"
        "c9711a816fddae6a8d22f2a07c8561fc363c76f7b39f95cde62b66d9957ef32f",

    "CLASSIFICATION_POLICY":
        "ClassificationPolicy:v1:sha256:"
        "5d6c6edab7cfb88bcb42d4badf9bd53dc78f458eae12b4e8b05878fb7f3256c8",
}

HISTORICAL_SUPERSEDED_IDS = {
    "EACS":
        "EvidenceAdapterContractSet:v1:sha256:"
        "7cca6802ebc5839317643dcb584173b75d985477da687ab0d8fe5802b181f788",
    "CLASSIFICATION_POLICY":
        "ClassificationPolicy:v1:sha256:"
        "6341a9f9781ead1b1ab5ba2065b7eda6c0c77b4d8736db2eae6a04ef881daf3e",
}


def fail(reason: str) -> None:
    print("")
    print("F_F6_DISCOVERY_STATUS=FAIL")
    print("FORMAL_F_F6_EXECUTED=NO")
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


def safe_json(path: pathlib.Path) -> dict[str, Any] | None:
    try:
        if path.stat().st_size > 64 * 1024 * 1024:
            return None
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 1. Exact repaired candidate. No mutation.
# ---------------------------------------------------------------------------

if not REPO.is_dir():
    fail("REPAIRED_REPO_MISSING")

commit = git("rev-parse", "HEAD").lower()
tree = git("rev-parse", "HEAD^{tree}").lower()
status = git("status", "--porcelain")

if commit != EXPECTED_COMMIT:
    fail("CANDIDATE_COMMIT_MISMATCH:" + commit)

if tree != EXPECTED_TREE:
    fail("CANDIDATE_TREE_MISMATCH:" + tree)

if status:
    fail("CANDIDATE_WORKTREE_NOT_CLEAN")

sys.path.insert(0, str(REPO))

from app.device_fingerprint.artifact_content import (
    make_artifact_content,
)
from app.device_fingerprint.artifact_dependency_graph import (
    extract_direct_artifact_refs,
)

# ---------------------------------------------------------------------------
# 2. Bounded search for historical F-F6 result/proof/evidence.
# ---------------------------------------------------------------------------

historical_ff6_gate_results = []
historical_ff6_proofs = []
historical_ff6_evidence_refs = []
candidate_evidence_files = []

for root in SEARCH_ROOTS:
    if not root.exists():
        continue

    for current, dirs, files in os.walk(root):
        dirs[:] = [
            d for d in dirs
            if d not in {
                ".git", ".venv", "venv", "__pycache__",
                "node_modules", ".pytest_cache", "tmp",
            }
        ]

        for name in files:
            lower = name.lower()
            path = pathlib.Path(current) / name

            # Filename-level candidate evidence discovery.
            if any(
                token in lower
                for token in (
                    "artifact_dependency_graph",
                    "artifact-dependency-graph",
                    "artifact_cycle_test_fixtures",
                    "artifact-cycle-test-fixtures",
                    "artifact_topological_ordering",
                    "artifact-topological-ordering",
                )
            ):
                candidate_evidence_files.append(path.resolve())

            if not lower.endswith(".json"):
                continue

            obj = safe_json(path)
            if obj is None:
                continue

            # ArtifactContent GateResultManifest.
            if obj.get("artifact_type") == "GateResultManifest":
                payload = obj.get("semantic_payload")
                if (
                    isinstance(payload, dict)
                    and payload.get("gate_id") == "F-F6"
                ):
                    historical_ff6_gate_results.append(
                        {
                            "path": str(path.resolve()),
                            "file_sha256": sha256_file(path),
                            "artifact_id": obj.get("artifact_id"),
                            "status": payload.get("status"),
                            "candidate_commit": payload.get(
                                "candidate_repository_commit_sha"
                            ),
                            "candidate_tree": payload.get(
                                "candidate_repository_tree_sha"
                            ),
                            "input_artifact_refs": payload.get(
                                "input_artifact_refs", []
                            ),
                            "output_artifact_refs": payload.get(
                                "output_artifact_refs", []
                            ),
                            "retained_evidence_refs": payload.get(
                                "retained_evidence_refs", []
                            ),
                        }
                    )

                    for row in payload.get("retained_evidence_refs", []):
                        if (
                            isinstance(row, dict)
                            and row.get("evidence_label")
                            in TARGET_EVIDENCE_LABELS
                        ):
                            historical_ff6_evidence_refs.append(
                                {
                                    "gate_result_path": str(path.resolve()),
                                    **row,
                                }
                            )

            # ArtifactContent GateProofArtifact.
            if obj.get("artifact_type") == "GateProofArtifact":
                payload = obj.get("semantic_payload")
                if (
                    isinstance(payload, dict)
                    and payload.get("source_gate_id") == "F-F6"
                    and payload.get("proof_kind")
                    == "ARTIFACT_GRAPH_ACYCLICITY"
                ):
                    historical_ff6_proofs.append(
                        {
                            "path": str(path.resolve()),
                            "file_sha256": sha256_file(path),
                            "artifact_id": obj.get("artifact_id"),
                            "candidate_commit": payload.get(
                                "candidate_repository_commit_sha"
                            ),
                            "candidate_tree": payload.get(
                                "candidate_repository_tree_sha"
                            ),
                            "input_artifact_refs": payload.get(
                                "input_artifact_refs", []
                            ),
                            "canonical_result_summary": payload.get(
                                "canonical_result_summary"
                            ),
                            "retained_evidence_refs": payload.get(
                                "retained_evidence_refs", []
                            ),
                        }
                    )

# Dedupe discovered paths.
candidate_evidence_files = sorted(
    {str(p): p for p in candidate_evidence_files}.values(),
    key=lambda p: str(p).lower(),
)

# ---------------------------------------------------------------------------
# 3. Inventory historical initial-admission artifact directory.
# ---------------------------------------------------------------------------

initial_inventory = []
artifact_by_id: dict[str, dict[str, Any]] = {}

if HISTORICAL_INITIAL_ARTIFACT_DIR.is_dir():
    for path in sorted(
        HISTORICAL_INITIAL_ARTIFACT_DIR.glob("*.json"),
        key=lambda p: p.name.lower(),
    ):
        obj = safe_json(path)
        if obj is None:
            continue

        aid = obj.get("artifact_id")
        atype = obj.get("artifact_type")
        payload = obj.get("semantic_payload")

        row = {
            "path": str(path.resolve()),
            "filename": path.name,
            "file_sha256": sha256_file(path),
            "artifact_id": aid,
            "artifact_type": atype,
            "content_sha256": obj.get("content_sha256"),
            "reconstructed_identity_valid": False,
            "direct_artifact_refs": [],
        }

        if (
            isinstance(aid, str)
            and isinstance(atype, str)
            and isinstance(payload, dict)
        ):
            try:
                rebuilt = make_artifact_content(atype, payload)
                row["reconstructed_identity_valid"] = (
                    rebuilt.artifact_id == aid
                    and rebuilt.content_sha256 == obj.get("content_sha256")
                )

                if row["reconstructed_identity_valid"]:
                    refs = extract_direct_artifact_refs(rebuilt)
                    row["direct_artifact_refs"] = [
                        {
                            "artifact_id": ref.artifact_id,
                            "content_sha256": ref.content_sha256,
                        }
                        for ref in refs
                    ]
                    artifact_by_id[aid] = row
            except Exception as exc:
                row["reconstruction_error"] = (
                    type(exc).__name__ + ":" + str(exc)
                )

        initial_inventory.append(row)

# ---------------------------------------------------------------------------
# 4. Resolve retained evidence path references where possible.
# ---------------------------------------------------------------------------

resolved_historical_evidence = []

for ref in historical_ff6_evidence_refs:
    raw = ref.get("path_or_reference")
    resolved = None

    if isinstance(raw, str) and raw:
        p = pathlib.Path(raw)
        if p.is_file():
            resolved = p.resolve()

    if resolved is None:
        expected_sha = ref.get("file_sha256")
        label = ref.get("evidence_label")

        for candidate in candidate_evidence_files:
            try:
                if expected_sha and sha256_file(candidate) != expected_sha:
                    continue
            except OSError:
                continue

            # SHA is authoritative; filename label similarity is only a bonus.
            resolved = candidate
            break

    row = dict(ref)
    row["resolved_path"] = str(resolved) if resolved else None

    if resolved is not None:
        row["resolved_sha256"] = sha256_file(resolved)
        row["resolved_json"] = safe_json(resolved)

    resolved_historical_evidence.append(row)

# ---------------------------------------------------------------------------
# 5. Historical F-F6 input identity inventory, if found.
# ---------------------------------------------------------------------------

historical_input_ids = set()

for gate in historical_ff6_gate_results:
    if gate["status"] == "PASS":
        for ref in gate["input_artifact_refs"]:
            if isinstance(ref, dict) and isinstance(ref.get("artifact_id"), str):
                historical_input_ids.add(ref["artifact_id"])

for proof in historical_ff6_proofs:
    for ref in proof["input_artifact_refs"]:
        if isinstance(ref, dict) and isinstance(ref.get("artifact_id"), str):
            historical_input_ids.add(ref["artifact_id"])

historical_input_resolution = []

for aid in sorted(historical_input_ids):
    historical_input_resolution.append(
        {
            "artifact_id": aid,
            "found_in_initial_artifact_dir": aid in artifact_by_id,
            "initial_artifact_path": (
                artifact_by_id[aid]["path"]
                if aid in artifact_by_id
                else None
            ),
            "artifact_type": (
                artifact_by_id[aid]["artifact_type"]
                if aid in artifact_by_id
                else aid.split(":", 1)[0]
            ),
        }
    )

# ---------------------------------------------------------------------------
# 6. Identify initial lineage roots and their closure availability.
# ---------------------------------------------------------------------------

root_types = {
    "FoundationAdmissionManifest",
    "FoundationRuntimeProfile",
    "RuntimeProfileAdmissionManifest",
}

initial_lineage_roots = [
    row
    for row in initial_inventory
    if row.get("artifact_type") in root_types
    and row.get("reconstructed_identity_valid") is True
]

def walk_available_closure(root_id: str) -> dict[str, Any]:
    visited = set()
    missing = set()
    stack = [root_id]

    while stack:
        aid = stack.pop()

        if aid in visited:
            continue

        visited.add(aid)
        row = artifact_by_id.get(aid)

        if row is None:
            missing.add(aid)
            continue

        for ref in row.get("direct_artifact_refs", []):
            dep = ref.get("artifact_id")
            if isinstance(dep, str):
                stack.append(dep)

    return {
        "root_artifact_id": root_id,
        "reachable_ids": sorted(visited),
        "reachable_count": len(visited),
        "missing_dependency_ids": sorted(missing),
        "missing_dependency_count": len(missing),
    }

initial_root_closures = [
    walk_available_closure(row["artifact_id"])
    for row in initial_lineage_roots
]

# ---------------------------------------------------------------------------
# 7. Report current A1 identities and whether exact files are discoverable.
#    This is discovery only; no candidate graph is constructed.
# ---------------------------------------------------------------------------

current_id_locations: dict[str, list[str]] = {
    label: [] for label in A1_CURRENT_IDS
}

target_current_ids = set(A1_CURRENT_IDS.values())

for root in SEARCH_ROOTS:
    if not root.exists():
        continue

    for current, dirs, files in os.walk(root):
        dirs[:] = [
            d for d in dirs
            if d not in {
                ".git", ".venv", "venv", "__pycache__",
                "node_modules", ".pytest_cache", "tmp",
            }
        ]

        for name in files:
            if not name.lower().endswith(".json"):
                continue

            path = pathlib.Path(current) / name
            obj = safe_json(path)

            if obj is None:
                continue

            aid = obj.get("artifact_id")

            if aid not in target_current_ids:
                continue

            for label, expected in A1_CURRENT_IDS.items():
                if aid == expected:
                    current_id_locations[label].append(
                        str(path.resolve())
                    )

# ---------------------------------------------------------------------------
# 8. Retain one discovery report only. No formal gate, no semantic artifact.
# ---------------------------------------------------------------------------

stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
OUT = (
    ROOT / "official-runs" / "task04" / "f-f6"
    / ("inventory-discovery-" + stamp + "-A1")
)

if OUT.exists():
    fail("DISCOVERY_OUTPUT_ALREADY_EXISTS")

OUT.mkdir(parents=True)

report = {
    "report_contract":
        "captivportal.task04.a1.ff6_inventory_discovery.v1",

    "candidate_repository_commit_sha": commit,
    "candidate_repository_tree_sha": tree,

    "formal_f_f6_executed": False,
    "production_action": False,

    "historical_initial_artifact_directory": {
        "path": str(HISTORICAL_INITIAL_ARTIFACT_DIR),
        "exists": HISTORICAL_INITIAL_ARTIFACT_DIR.is_dir(),
        "artifact_file_count": len(initial_inventory),
        "reconstructed_valid_count": sum(
            1
            for row in initial_inventory
            if row.get("reconstructed_identity_valid") is True
        ),
    },

    "historical_ff6_gate_results":
        historical_ff6_gate_results,

    "historical_ff6_proofs":
        historical_ff6_proofs,

    "historical_ff6_evidence_refs":
        resolved_historical_evidence,

    "historical_ff6_input_resolution":
        historical_input_resolution,

    "historical_ff6_input_count":
        len(historical_input_ids),

    "initial_artifact_inventory":
        initial_inventory,

    "initial_lineage_roots": [
        {
            "artifact_id": row["artifact_id"],
            "artifact_type": row["artifact_type"],
            "path": row["path"],
        }
        for row in initial_lineage_roots
    ],

    "initial_lineage_root_closures":
        initial_root_closures,

    "current_a1_ids":
        A1_CURRENT_IDS,

    "current_a1_id_locations":
        {
            label: sorted(set(paths))
            for label, paths in current_id_locations.items()
        },

    "historical_superseded_ids":
        HISTORICAL_SUPERSEDED_IDS,

    "disposition":
        "DISCOVERY_ONLY_NO_F_F6_GATE",
}

report_path = OUT / "f-f6-inventory-discovery.json"
report_path.write_text(
    json.dumps(
        report,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ),
    encoding="utf-8",
)

report_sha = sha256_file(report_path)

if git("status", "--porcelain"):
    fail("CANDIDATE_WORKTREE_DIRTY_AFTER_DISCOVERY")

# ---------------------------------------------------------------------------
# 9. Console summary for TechLead.
# ---------------------------------------------------------------------------

print("")
print("F_F6_DISCOVERY_STATUS=PASS")
print("FORMAL_F_F6_EXECUTED=NO")
print("CANDIDATE_COMMIT=" + commit)
print("CANDIDATE_TREE=" + tree)

print(
    "HISTORICAL_INITIAL_ARTIFACT_DIR_EXISTS="
    + ("YES" if HISTORICAL_INITIAL_ARTIFACT_DIR.is_dir() else "NO")
)
print(
    "HISTORICAL_INITIAL_ARTIFACT_FILE_COUNT="
    + str(len(initial_inventory))
)
print(
    "HISTORICAL_INITIAL_ARTIFACT_RECONSTRUCTED_VALID_COUNT="
    + str(
        sum(
            1
            for row in initial_inventory
            if row.get("reconstructed_identity_valid") is True
        )
    )
)

print(
    "HISTORICAL_F_F6_GATE_RESULT_COUNT="
    + str(len(historical_ff6_gate_results))
)
print(
    "HISTORICAL_F_F6_PROOF_COUNT="
    + str(len(historical_ff6_proofs))
)
print(
    "HISTORICAL_F_F6_INPUT_COUNT="
    + str(len(historical_input_ids))
)

for gate in historical_ff6_gate_results:
    print(
        "HISTORICAL_F_F6_GATE="
        + str(gate.get("artifact_id"))
        + "|status="
        + str(gate.get("status"))
        + "|commit="
        + str(gate.get("candidate_commit"))
        + "|tree="
        + str(gate.get("candidate_tree"))
        + "|path="
        + str(gate.get("path"))
    )

for proof in historical_ff6_proofs:
    print(
        "HISTORICAL_F_F6_PROOF="
        + str(proof.get("artifact_id"))
        + "|path="
        + str(proof.get("path"))
    )

for row in historical_input_resolution:
    print(
        "HISTORICAL_INPUT="
        + row["artifact_id"]
        + "|type="
        + row["artifact_type"]
        + "|initial_file="
        + (
            row["initial_artifact_path"]
            if row["initial_artifact_path"]
            else "NOT_FOUND"
        )
    )

for root in initial_lineage_roots:
    print(
        "INITIAL_LINEAGE_ROOT="
        + root["artifact_type"]
        + "|"
        + root["artifact_id"]
        + "|"
        + root["path"]
    )

for closure in initial_root_closures:
    print(
        "INITIAL_ROOT_CLOSURE="
        + closure["root_artifact_id"]
        + "|reachable="
        + str(closure["reachable_count"])
        + "|missing="
        + str(closure["missing_dependency_count"])
    )

for label in sorted(A1_CURRENT_IDS):
    locations = sorted(set(current_id_locations[label]))
    print(
        "A1_ARTIFACT="
        + label
        + "|"
        + A1_CURRENT_IDS[label]
        + "|files="
        + str(len(locations))
    )
    for location in locations:
        print(
            "A1_ARTIFACT_FILE="
            + label
            + "|"
            + location
        )

print("DISCOVERY_REPORT=" + str(report_path))
print("DISCOVERY_REPORT_SHA256=" + report_sha)
print("PRODUCTION_ACTION=NO")
print("NEXT=TECHLEAD_BUILD_EXACT_F_F6_INVENTORY")
