#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_HEAD = "e5eae589b12c578b4e5ae16742d898546e1ce061"
EXPECTED_TREE = "5464f749fa119132071fa25d6dc50ea57a3aa840"

EXPECTED_TAXONOMY_ID = (
    "ClassificationTaxonomy:v1:sha256:"
    "399e2a337e7ebecb1bd7a9b21dff5e744c13be36313bc39f16832bc7a57a4d10"
)
EXPECTED_ALIAS_ID = (
    "AliasMapping:v1:sha256:"
    "f1cdd7c9510c2a33bad99bd1ae15eaccd20fcb828a52e02533b9917fdfc2e228"
)

OWNER_DECISION_ID = "15d69dc7-83f3-4891-8e79-b9c27d6cea87"

OWNER_AUTHORIZATION_TEXT = (
    "Авторизую F-E6 V1 taxonomy scope: platform_family = "
    "{android, ios, windows, macos, chromeos, linux}; device_class = "
    "{smartphone, tablet, laptop}; ios включает iOS+iPadOS; "
    "recognized_out_of_scope допустим только для platform_family/device_class; "
    "initial manufacturer_records/model_family_records и manufacturer/model aliases = empty; "
    "production source_taxonomy_mappings ограничить exact K1/Satori mappings, уже принятыми "
    "в importer; K2B/K3 canonical outputs только проверять на совместимость с taxonomy без "
    "дублирования mappings; Phone/Mobile/Desktop, out-of-scope и multiple-alias cases использовать "
    "только как deterministic F-E6 proof fixtures, без расширения production V1 taxonomy."
)

REVIEWED_PATCH_SHA256 = "57813b19033a65e38f7d3b76359d8ff6c573615146f565cf7d4489018f966956"


def die(message: str) -> None:
    print("F-E6 REAL ADMISSION GATE = FAIL")
    print(message)
    raise SystemExit(1)


def run(cmd: list[str], *, cwd: Path | None = None) -> str:
    try:
        cp = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        stderr = getattr(exc, "stderr", "") or ""
        die(f"Command failed: {' '.join(cmd)}\n{stderr.strip()}")
    return cp.stdout.strip()


def git(repo: Path, *args: str) -> str:
    return run(["git", "-C", str(repo), *args])


def discover_repo(root: Path) -> Path:
    candidates: set[Path] = set()
    probes = [root]
    try:
        probes += [p for p in root.iterdir() if p.is_dir()]
    except OSError as exc:
        die(f"Cannot list root {root}: {exc!r}")

    # One extra level is enough for the CaptivPortal-Lab worktree layout.
    for first in list(probes):
        if first == root:
            continue
        try:
            probes += [p for p in first.iterdir() if p.is_dir()]
        except OSError:
            pass

    for probe in probes:
        try:
            top = subprocess.run(
                ["git", "-C", str(probe), "rev-parse", "--show-toplevel"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            continue
        if top:
            candidates.add(Path(top).resolve())

    matches = []
    for repo in sorted(candidates):
        try:
            head = git(repo, "rev-parse", "HEAD")
            tree = git(repo, "rev-parse", "HEAD^{tree}")
        except SystemExit:
            continue
        if head == EXPECTED_HEAD and tree == EXPECTED_TREE:
            matches.append(repo)

    if len(matches) != 1:
        die(
            "Could not resolve exactly one PR #155 checkout at expected HEAD/TREE. "
            f"Matches: {[str(p) for p in matches]}"
        )
    return matches[0]


def utc_ms_now() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_canonical_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


def artifact_envelope(content: Any) -> dict[str, Any]:
    return {
        "artifact_type": content.artifact_type,
        "artifact_schema_version": content.artifact_schema_version,
        "semantic_payload": content.semantic_payload,
        "content_sha256": content.content_sha256,
        "artifact_id": content.artifact_id,
    }


def evidence_ref(label: str, path: Path) -> dict[str, Any]:
    return {
        "evidence_label": label,
        "file_sha256": sha256_file(path),
        "media_type": "application/json",
        "path_or_reference": str(path),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=r"C:\CaptivPortal-Lab")
    ap.add_argument("--repo", default=None)
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        die(f"Root not found: {root}")

    if args.repo:
        repo = Path(args.repo).resolve()
        if not repo.is_dir():
            die(f"Repo not found: {repo}")
        head = git(repo, "rev-parse", "HEAD")
        tree = git(repo, "rev-parse", "HEAD^{tree}")
        if head != EXPECTED_HEAD or tree != EXPECTED_TREE:
            die(
                f"Explicit repo identity mismatch: HEAD={head}, TREE={tree}; "
                f"expected HEAD={EXPECTED_HEAD}, TREE={EXPECTED_TREE}"
            )
    else:
        repo = discover_repo(root)
        head = git(repo, "rev-parse", "HEAD")
        tree = git(repo, "rev-parse", "HEAD^{tree}")

    # Load the exact PR #155 implementation.
    sys.path.insert(0, str(repo))
    try:
        from app.device_fingerprint.artifact_content import canonical_artifact_json
        from app.device_fingerprint.fe6_taxonomy_aliases import run_fe6_taxonomy_alias_gate
        from app.device_fingerprint.taxonomy_artifacts import (
            build_alias_mapping_v1,
            build_classification_taxonomy_v1,
        )
    except Exception as exc:
        die(f"Cannot import PR #155 implementation: {exc!r}")

    taxonomy = build_classification_taxonomy_v1()
    alias_mapping = build_alias_mapping_v1()

    if taxonomy.artifact_id != EXPECTED_TAXONOMY_ID:
        die(f"ClassificationTaxonomy identity mismatch: {taxonomy.artifact_id}")
    if alias_mapping.artifact_id != EXPECTED_ALIAS_ID:
        die(f"AliasMapping identity mismatch: {alias_mapping.artifact_id}")

    out_dir = root / "artifacts" / "fe6-taxonomy-aliases"
    out_dir.mkdir(parents=True, exist_ok=True)

    captured_at = utc_ms_now()

    authorization_evidence = {
        "evidence_contract": "captivportal.fe6.owner_authorization_evidence.v1",
        "gate_id": "F-E6",
        "owner_authorization_text": OWNER_AUTHORIZATION_TEXT,
        "formal_recorded_at_utc": captured_at,
        "reviewed_patch_sha256": REVIEWED_PATCH_SHA256,
        "candidate_repository_commit_sha": EXPECTED_HEAD,
        "candidate_repository_tree_sha": EXPECTED_TREE,
        "classification_taxonomy_artifact_id": taxonomy.artifact_id,
        "classification_taxonomy_content_sha256": taxonomy.content_sha256,
        "alias_mapping_artifact_id": alias_mapping.artifact_id,
        "alias_mapping_content_sha256": alias_mapping.content_sha256,
        "note": (
            "This evidence records the Owner's explicit F-E6 V1 scope authorization "
            "already given in the project conversation; formal_recorded_at_utc is the "
            "audit-record creation time, not a backdated chat timestamp."
        ),
    }
    authorization_path = out_dir / "fe6-owner-authorization-evidence.json"
    write_canonical_json(authorization_path, authorization_evidence)

    decision_core = {
        "decision_record_id": OWNER_DECISION_ID,
        "decision_subject_type": "FOUNDATION_TAXONOMY_ALIAS_ADMISSION",
        "decision_subject_id": "F-E6",
        "decision": "ACCEPT",
        "decided_at_utc": captured_at,
        "actor_role": "OWNER",
        "referenced_artifact_ids": sorted([taxonomy.artifact_id, alias_mapping.artifact_id]),
        "referenced_gate_ids": ["F-E6"],
        "reason_reference_text": (
            "Formal audit record of the Owner-authorized F-E6 V1 taxonomy scope. "
            f"Authorization evidence SHA256={sha256_file(authorization_path)}."
        ),
    }
    record_sha256 = hashlib.sha256(canonical_artifact_json(decision_core)).hexdigest()
    decision_record = {**decision_core, "record_sha256": record_sha256}
    decision_path = out_dir / "fe6-owner-decision-record.json"
    write_canonical_json(decision_path, decision_record)

    retained = [
        evidence_ref("F-E6_OWNER_AUTHORIZATION", authorization_path),
        evidence_ref("F-E6_OWNER_DECISION_RECORD", decision_path),
    ]

    try:
        result = run_fe6_taxonomy_alias_gate(
            taxonomy,
            alias_mapping,
            candidate_repository_commit_sha=EXPECTED_HEAD,
            candidate_repository_tree_sha=EXPECTED_TREE,
            environment_identity="OWNER_LOCAL_PR155_REAL_ADMISSION",
            retained_evidence_refs=retained,
            decision_record_refs=[OWNER_DECISION_ID],
        )
    except Exception as exc:
        die(f"Gate invocation raised: {exc!r}")

    manifest = result.gate_result_manifest
    gate_path = out_dir / "fe6-gate-result-manifest.json"
    write_canonical_json(gate_path, artifact_envelope(manifest))

    execution_report = {
        "execution_contract": "captivportal.fe6.real_admission_execution.v1",
        "repository": str(repo),
        "candidate_repository_commit_sha": head,
        "candidate_repository_tree_sha": tree,
        "taxonomy_artifact_id": result.taxonomy_artifact_id,
        "taxonomy_content_sha256": result.taxonomy_content_sha256,
        "alias_mapping_artifact_id": result.alias_mapping_artifact_id,
        "alias_mapping_content_sha256": result.alias_mapping_content_sha256,
        "fixture_results": result.fixture_results,
        "gate_status": manifest.semantic_payload["status"],
        "gate_artifact_id": manifest.artifact_id,
        "gate_content_sha256": manifest.content_sha256,
        "failure_reasons": list(result.failure_reasons),
        "owner_decision_id": OWNER_DECISION_ID,
        "owner_decision_record_sha256": record_sha256,
        "retained_evidence_refs": retained,
    }
    execution_path = out_dir / "fe6-gate-execution.json"
    write_canonical_json(execution_path, execution_report)

    print(f"PR_HEAD={head}")
    print(f"PR_TREE={tree}")
    print(f"REPO={repo}")
    print(f"TAXONOMY_ARTIFACT_ID={taxonomy.artifact_id}")
    print(f"TAXONOMY_CONTENT_SHA256={taxonomy.content_sha256}")
    print(f"ALIAS_MAPPING_ARTIFACT_ID={alias_mapping.artifact_id}")
    print(f"ALIAS_MAPPING_CONTENT_SHA256={alias_mapping.content_sha256}")
    for name in sorted(result.fixture_results):
        print(f"FIXTURE_{name}={result.fixture_results[name]}")
    print(f"GATE_STATUS={manifest.semantic_payload['status']}")
    print(f"GATE_ARTIFACT_ID={manifest.artifact_id}")
    print(f"GATE_CONTENT_SHA256={manifest.content_sha256}")
    print(f"OWNER_DECISION_ID={OWNER_DECISION_ID}")
    print(f"OWNER_DECISION_RECORD_SHA256={record_sha256}")
    print(f"FAILURE_REASONS={list(result.failure_reasons)}")
    print(f"AUTHORIZATION_EVIDENCE={authorization_path}")
    print(f"DECISION_RECORD={decision_path}")
    print(f"GATE_REPORT={gate_path}")
    print(f"EXECUTION_REPORT={execution_path}")

    if manifest.semantic_payload["status"] == "PASS" and not result.failure_reasons:
        print("F-E6 REAL ADMISSION GATE = PASS")
        return

    print("F-E6 REAL ADMISSION GATE = FAIL")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
