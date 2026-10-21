#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

EXPECTED_MAIN_COMMIT = "340e47ec7de3974ac328a7daf1b9936d0f7e5162"
EXPECTED_MAIN_TREE = "a05b1aae9ca84dee427f1a6a58efd38cd41ee48c"

MANDATORY_GATES = (
    "F-A1", "F-A2", "F-A3", "F-A4", "F-A5",
    "F-B0", "F-B1", "F-B2", "F-B3",
    "F-C1", "F-C2", "F-C3",
    "F-D1",
    "F-E1", "F-E2", "F-E3", "F-E4", "F-E5", "F-E6", "F-E7",
    "F-F1", "F-F2", "F-F3", "F-F4", "F-F5", "F-F6",
)

EXACT_GATE_IDS = {
    "F-E5": "GateResultManifest:v1:sha256:b73b4c74189588a3457852dd7320c482a9b30f60c8cbdcff8f57843267b66124",
    "F-E7": "GateResultManifest:v1:sha256:7b9c66874cf9c6ddbb9cd60e09f4acf7f3ad736e69c872500b7041ecd727a7af",
    "F-F5": "GateResultManifest:v1:sha256:77385a12e1e77a4a226320d39db4a4f0b90924e6b9a09cf19051732febc86ac7",
}

OUTPUT_ANCHORS = {
    "F-C3": {
        "TTLCapturePlacementProof:v1:sha256:c48ffafa3856c4708a35e644bb4cc2b468275af9790df579a366d7ac71fc0ca2",
    },
    "F-E6": {
        "ClassificationTaxonomy:v1:sha256:399e2a337e7ebecb1bd7a9b21dff5e744c13be36313bc39f16832bc7a57a4d10",
        "AliasMapping:v1:sha256:f1cdd7c9510c2a33bad99bd1ae15eaccd20fcb828a52e02533b9917fdfc2e228",
    },
    "F-E7": {
        "KnowledgeBundle:v1:sha256:0fbdc70c2c25489a28d6446403e2facb7de6704f3a915af512b72cc9d0d10b3b",
    },
    "F-F1": {
        "EvidenceAdapterContractSet:v1:sha256:7cca6802ebc5839317643dcb584173b75d985477da687ab0d8fe5802b181f788",
    },
    "F-F2": {
        "ClassificationPolicy:v1:sha256:6341a9f9781ead1b1ab5ba2065b7eda6c0c77b4d8736db2eae6a04ef881daf3e",
    },
    "F-F3": {
        "ClassificationRetentionPolicy:v1:sha256:029c3534e076db6f7293c78e8a86c425b10c786d58713e77a077a19dfdda3e72",
    },
    "F-F4": {
        "ProductValidationPolicy:v1:sha256:806779ca1844e55083a2c1c464cf8d94a9bdd0b2f97436d203b63fd03e81bea5",
    },
    "F-F5": {
        "GateProofArtifact:v1:sha256:0a097295fa65e6ba3ee95755670328aea4584712ae8d72829b6c04e1cac4f023",
    },
    "F-F6": {
        "GateProofArtifact:v1:sha256:7b52b74baa2868505def90b2555a80b082ee4e2b27734a2292d5e3e002078896",
    },
}

EXACT_REQUIRED_ARTIFACTS = {
    "KnowledgeBundle:v1:sha256:0fbdc70c2c25489a28d6446403e2facb7de6704f3a915af512b72cc9d0d10b3b",
    "TTLCapturePlacementProof:v1:sha256:c48ffafa3856c4708a35e644bb4cc2b468275af9790df579a366d7ac71fc0ca2",
    "GateProofArtifact:v1:sha256:0a097295fa65e6ba3ee95755670328aea4584712ae8d72829b6c04e1cac4f023",
    "GateProofArtifact:v1:sha256:7b52b74baa2868505def90b2555a80b082ee4e2b27734a2292d5e3e002078896",
}

def git(*args: str) -> str:
    p = subprocess.run(
        ["git", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if p.returncode:
        raise RuntimeError("git " + " ".join(args) + " failed:\n" + p.stderr.strip())
    return p.stdout.strip()

def iter_artifact_dicts(value: Any):
    if isinstance(value, dict):
        required = {"artifact_type", "artifact_schema_version", "artifact_id", "content_sha256", "semantic_payload"}
        if required <= set(value):
            yield value
        for child in value.values():
            yield from iter_artifact_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_artifact_dicts(child)

def main() -> int:
    repo = Path.cwd()
    if not (repo / "app" / "device_fingerprint").is_dir():
        print("F_ADMIT_PREFLIGHT=STOP")
        print("STOP_REASON=run_from_repository_root")
        return 2

    # Make local production modules importable even when script lives in Downloads.
    sys.path.insert(0, str(repo))

    # Exact merged main identity only; no tests.
    subprocess.run(
        ["git", "fetch", "origin", "refs/heads/main:refs/remotes/origin/main", "--quiet"],
        check=True,
    )
    main_commit = git("rev-parse", "origin/main")
    main_tree = git("rev-parse", "origin/main^{tree}")
    head_tree = git("rev-parse", "HEAD^{tree}")
    if main_commit != EXPECTED_MAIN_COMMIT or main_tree != EXPECTED_MAIN_TREE:
        print("F_ADMIT_PREFLIGHT=STOP")
        print(f"STOP_REASON=origin_main_identity_changed:{main_commit}:{main_tree}")
        return 3
    if head_tree != main_tree:
        print("F_ADMIT_PREFLIGHT=STOP")
        print(f"STOP_REASON=worktree_tree_not_merged_main:{head_tree}")
        return 4
    if git("status", "--short"):
        print("F_ADMIT_PREFLIGHT=STOP")
        print("STOP_REASON=working_tree_not_clean")
        return 5

    from app.device_fingerprint.artifact_content import make_artifact_content

    artifact_root = Path(r"C:\CaptivPortal-Lab\artifacts")
    if not artifact_root.is_dir():
        print("F_ADMIT_PREFLIGHT=STOP")
        print("STOP_REASON=artifact_root_missing")
        return 6

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_dir = artifact_root / f"f-admit-preflight-{stamp}"
    report_dir.mkdir(parents=True, exist_ok=False)

    artifacts: dict[str, dict[str, Any]] = {}
    sources: dict[str, list[str]] = defaultdict(list)
    conflicts: list[dict[str, str]] = []
    invalid_candidates: list[dict[str, str]] = []
    files_scanned = 0
    json_files = 0

    # Snapshot file list before creating report payloads.
    candidates = [p for p in artifact_root.rglob("*.json") if report_dir not in p.parents]

    for path in candidates:
        files_scanned += 1
        try:
            if path.stat().st_size > 50 * 1024 * 1024:
                continue
            value = json.loads(path.read_text(encoding="utf-8"))
            json_files += 1
        except Exception:
            continue
        for row in iter_artifact_dicts(value):
            try:
                if row["artifact_schema_version"] != 1:
                    raise ValueError("schema version")
                canonical = make_artifact_content(row["artifact_type"], row["semantic_payload"])
                if canonical.artifact_id != row["artifact_id"] or canonical.content_sha256 != row["content_sha256"]:
                    raise ValueError("identity mismatch")
            except Exception as exc:
                invalid_candidates.append({"path": str(path), "reason": str(exc)})
                continue

            aid = row["artifact_id"]
            normalized = {
                "artifact_type": row["artifact_type"],
                "artifact_schema_version": 1,
                "artifact_id": aid,
                "content_sha256": row["content_sha256"],
                "semantic_payload": row["semantic_payload"],
            }
            earlier = artifacts.get(aid)
            if earlier is not None and earlier != normalized:
                conflicts.append({"artifact_id": aid, "path": str(path)})
                continue
            artifacts[aid] = normalized
            sources[aid].append(str(path))

    pass_gates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in artifacts.values():
        if row["artifact_type"] != "GateResultManifest":
            continue
        payload = row["semantic_payload"]
        gate_id = payload.get("gate_id")
        if gate_id in MANDATORY_GATES and payload.get("status") == "PASS":
            pass_gates[gate_id].append(row)

    selected: dict[str, dict[str, Any]] = {}
    gate_issues: dict[str, Any] = {}

    for gate_id in MANDATORY_GATES:
        candidates_for_gate = list(pass_gates.get(gate_id, []))

        exact_id = EXACT_GATE_IDS.get(gate_id)
        if exact_id:
            candidates_for_gate = [x for x in candidates_for_gate if x["artifact_id"] == exact_id]

        anchors = OUTPUT_ANCHORS.get(gate_id)
        if anchors:
            anchored = []
            for row in candidates_for_gate:
                outputs = {
                    ref.get("artifact_id")
                    for ref in row["semantic_payload"].get("output_artifact_refs", [])
                    if isinstance(ref, dict)
                }
                if anchors <= outputs:
                    anchored.append(row)
            candidates_for_gate = anchored

        if len(candidates_for_gate) == 1:
            selected[gate_id] = candidates_for_gate[0]
        elif len(candidates_for_gate) == 0:
            gate_issues[gate_id] = {
                "status": "MISSING_EXACT_PASS_GATE",
                "discovered_pass_candidates": [x["artifact_id"] for x in pass_gates.get(gate_id, [])],
                "required_exact_id": EXACT_GATE_IDS.get(gate_id),
                "required_output_anchors": sorted(OUTPUT_ANCHORS.get(gate_id, set())),
            }
        else:
            gate_issues[gate_id] = {
                "status": "AMBIGUOUS_PASS_GATE",
                "candidates": [x["artifact_id"] for x in candidates_for_gate],
            }

    missing_outputs: list[dict[str, str]] = []
    resolved_output_ids: set[str] = set()
    for gate_id, gate in selected.items():
        for ref in gate["semantic_payload"].get("output_artifact_refs", []):
            aid = ref.get("artifact_id")
            digest = ref.get("content_sha256")
            resolved_output_ids.add(aid)
            body = artifacts.get(aid)
            if body is None:
                missing_outputs.append({
                    "gate_id": gate_id, "artifact_id": aid, "reason": "artifact_body_missing"
                })
            elif body["content_sha256"] != digest:
                missing_outputs.append({
                    "gate_id": gate_id, "artifact_id": aid, "reason": "digest_mismatch"
                })

    missing_exact_artifacts = sorted(aid for aid in EXACT_REQUIRED_ARTIFACTS if aid not in artifacts)

    architecture_candidates = []
    for row in artifacts.values():
        if row["artifact_type"] != "ArchitectureContractReference":
            continue
        p = row["semantic_payload"]
        if (
            p.get("architecture_contract_name") == "DEVICE-FINGERPRINT-03A-R2 / TASK-04"
            and p.get("architecture_revision") == "R14"
            and p.get("architecture_status") == "FINAL"
        ):
            architecture_candidates.append(row["artifact_id"])

    knowledge_gate = selected.get("F-E5")
    knowledge_time = None
    if knowledge_gate:
        knowledge_time = knowledge_gate["semantic_payload"].get("trusted_time_inputs", {}).get(
            "foundation_knowledge_evaluation_at_utc"
        )

    status = "PASS" if (
        not conflicts
        and not gate_issues
        and not missing_outputs
        and not missing_exact_artifacts
        and len(architecture_candidates) == 1
        and knowledge_time is not None
    ) else "STOP"

    report = {
        "status": status,
        "origin_main_commit": main_commit,
        "origin_main_tree": main_tree,
        "artifact_root": str(artifact_root),
        "files_scanned": files_scanned,
        "json_files_parsed": json_files,
        "artifact_count": len(artifacts),
        "selected_prerequisite_gates": {
            gate_id: selected[gate_id]["artifact_id"]
            for gate_id in MANDATORY_GATES
            if gate_id in selected
        },
        "gate_issues": gate_issues,
        "missing_selected_gate_outputs": missing_outputs,
        "missing_exact_required_artifacts": missing_exact_artifacts,
        "architecture_contract_candidates": architecture_candidates,
        "foundation_knowledge_evaluation_at_utc": knowledge_time,
        "known_exact_knowledge_bundle": (
            "KnowledgeBundle:v1:sha256:0fbdc70c2c25489a28d6446403e2facb7de6704f3a915af512b72cc9d0d10b3b"
            if "KnowledgeBundle:v1:sha256:0fbdc70c2c25489a28d6446403e2facb7de6704f3a915af512b72cc9d0d10b3b"
            in artifacts else None
        ),
        "conflicts": conflicts,
        "invalid_artifact_candidates_count": len(invalid_candidates),
        "resolved_prerequisite_output_count": len(resolved_output_ids),
        "real_f_admit_executed": False,
        "foundation_profile_activated": False,
        "control_plane_mutated": False,
    }

    report_path = report_dir / "preflight-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("============================================================")
    print(f"F-ADMIT REAL PREFLIGHT = {status}")
    print("============================================================")
    print(f"MAIN_COMMIT={main_commit}")
    print(f"MAIN_TREE={main_tree}")
    print(f"ARTIFACT_COUNT={len(artifacts)}")
    print(f"MANDATORY_GATE_COUNT={len(MANDATORY_GATES)}")
    print(f"SELECTED_GATE_COUNT={len(selected)}")
    print(f"GATE_ISSUE_COUNT={len(gate_issues)}")
    print(f"MISSING_SELECTED_OUTPUT_COUNT={len(missing_outputs)}")
    print(f"MISSING_EXACT_ARTIFACT_COUNT={len(missing_exact_artifacts)}")
    print(f"ARCHITECTURE_CANDIDATE_COUNT={len(architecture_candidates)}")
    print(f"FOUNDATION_KNOWLEDGE_EVALUATION_AT_UTC={knowledge_time}")
    print("REAL_F_ADMIT_EXECUTED=NO")
    print("FOUNDATION_PROFILE_ACTIVATED=NO")
    print("CONTROL_PLANE_MUTATED=NO")
    print(f"REPORT={report_path}")

    if gate_issues:
        print("")
        print("GATE_ISSUES:")
        for gate_id in MANDATORY_GATES:
            if gate_id in gate_issues:
                issue = gate_issues[gate_id]
                print(f"  {gate_id}: {issue['status']}")
                if issue.get("candidates"):
                    for item in issue["candidates"]:
                        print(f"    candidate={item}")
                if issue.get("discovered_pass_candidates"):
                    for item in issue["discovered_pass_candidates"]:
                        print(f"    discovered={item}")

    if missing_outputs:
        print("")
        print("MISSING_SELECTED_OUTPUTS:")
        for item in missing_outputs:
            print(f"  {item['gate_id']} -> {item['artifact_id']} [{item['reason']}]")

    if missing_exact_artifacts:
        print("")
        print("MISSING_EXACT_ARTIFACTS:")
        for aid in missing_exact_artifacts:
            print(f"  {aid}")

    if len(architecture_candidates) != 1:
        print("")
        print("ARCHITECTURE_CONTRACT_CANDIDATES:")
        for aid in architecture_candidates:
            print(f"  {aid}")

    return 0 if status == "PASS" else 20

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print("F_ADMIT_PREFLIGHT=STOP")
        print("STOP_REASON=UNHANDLED")
        print(type(exc).__name__ + ": " + str(exc))
        raise
