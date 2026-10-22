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

EXPECTED_HEAD = "bd4e5911af76956adf084158714e70f0e34e4e01"
EXPECTED_TREE = "4cde58a5a09f0fd7a2d483af731eb39d0dce25e7"

SATORI_SHA256 = "4f64a405fb1debbd2e066478a7190b821424e0691399068421fdaf168da09b14"
IEEE_BUNDLE_SHA256 = "eb81bb97240fb7754659c33c13a9139583f7f505e38bc6618f9eef51b3878ae5"
P0F_GIT_BLOB_SHA1 = "c4b38b7e5b5621c70df56aa49127b5aaae1ec7e8"
P0F_SIZE = 36529

# Accepted K1 source-audit acquisition time retained in project evidence.
SATORI_RETRIEVED_AT_UTC = "2026-09-19T21:00:50.036Z"

# TechLead-side fresh pinned-source retrieval evidence, performed after PR #154 publication.
# The provenance timestamp uses the START of the retrieval window, conservatively.
P0F_RETRIEVED_AT_UTC = "2026-09-22T22:16:00.456Z"
P0F_RETRIEVAL_WINDOW_END_UTC = "2026-09-22T22:16:13.728Z"

# Owner authorization already given in project chat.
# Chat source exposes second precision; R14 UtcMs representation is normalized with .000.
OWNER_DECISION_ID = "1c26c5a2-6ee5-4bc8-aa3b-af253891e489"
OWNER_DECIDED_AT_UTC = "2026-09-22T21:15:43.000Z"

OWNER_AUTHORIZATION = (
    "Авторизую F-E5 V1 freshness policy: satori_dhcp = 365d fresh / 730d stale; "
    "p0f3_legacy_tcp = 0ms fresh / INT64_MAX stale, stale usable supporting; "
    "ieee_ra_mac = 48h fresh / 7d stale; для changing sources stale usable только "
    "с supporting ceiling, expired = no claim; без dimension overrides. "
    "Принимаю существующий governance K1/K2B/K4 для F-E5 admission."
)

def die(message: str) -> None:
    raise SystemExit(f"F-E5 REAL ADMISSION GATE = FAIL\n{message}")

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def git(repo: Path, *args: str) -> str:
    cp = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if cp.returncode != 0:
        die(f"git {' '.join(args)} failed for {repo}: {cp.stderr.strip()}")
    return cp.stdout.strip()

def find_repo(root: Path) -> Path:
    candidates: list[Path] = []
    for current, dirs, _files in os.walk(root):
        # Avoid scanning bulky irrelevant internals.
        dirs[:] = [d for d in dirs if d not in {
            ".venv", "venv", "__pycache__", "node_modules", ".pytest_cache"
        }]
        if ".git" in dirs:
            repo = Path(current)
            try:
                if git(repo, "rev-parse", "HEAD") == EXPECTED_HEAD:
                    candidates.append(repo)
            except SystemExit:
                pass
            dirs.remove(".git")
    if len(candidates) != 1:
        die(
            "Could not resolve exactly one PR #154 checkout at expected HEAD. "
            f"Matches: {[str(p) for p in candidates]}"
        )
    repo = candidates[0]
    tree = git(repo, "rev-parse", "HEAD^{tree}")
    if tree != EXPECTED_TREE:
        die(f"PR checkout tree mismatch: {tree}; expected {EXPECTED_TREE}")
    return repo

def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        die(f"Cannot parse JSON {path}: {exc!r}")

def find_named(artifacts: Path, name: str) -> Path:
    hits = list(artifacts.rglob(name))
    if len(hits) != 1:
        die(f"Expected exactly one {name} under {artifacts}; found {hits}")
    return hits[0]

def find_satori_source(artifacts: Path) -> Path:
    hits = []
    for path in artifacts.rglob("dhcp.xml"):
        try:
            if sha256_file(path) == SATORI_SHA256:
                hits.append(path)
        except OSError:
            continue
    if len(hits) != 1:
        die(f"Expected exactly one verified Satori dhcp.xml; found {hits}")
    return hits[0]

def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()

def find_p0f_source(artifacts: Path) -> Path:
    hits = []
    for path in artifacts.rglob("p0f.fp"):
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if len(data) == P0F_SIZE and git_blob_sha1(data) == P0F_GIT_BLOB_SHA1:
            hits.append(path)
    if len(hits) != 1:
        die(f"Expected exactly one verified pinned p0f.fp; found {hits}")
    return hits[0]

def artifact_envelope(content: Any) -> dict[str, Any]:
    return {
        "artifact_type": content.artifact_type,
        "artifact_schema_version": content.artifact_schema_version,
        "semantic_payload": content.semantic_payload,
        "content_sha256": content.content_sha256,
        "artifact_id": content.artifact_id,
    }

def write_canonical_json(path: Path, obj: Any) -> None:
    path.write_text(
        json.dumps(obj, ensure_ascii=True, allow_nan=False, sort_keys=True,
                   separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

def evidence_ref(label: str, path: Path, media_type: str = "application/json") -> dict[str, Any]:
    return {
        "evidence_label": label,
        "file_sha256": sha256_file(path),
        "media_type": media_type,
        "path_or_reference": str(path),
    }

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--root",
        default=r"C:\CaptivPortal-Lab",
        help="CaptivPortal-Lab root containing artifacts/",
    )
    ap.add_argument(
        "--repo",
        default=None,
        help="Exact local PR #154 checkout; preferred when using Git worktrees.",
    )
    args = ap.parse_args()

    root = Path(args.root).resolve()
    artifacts = root / "artifacts"
    if not artifacts.is_dir():
        die(f"Artifacts directory not found: {artifacts}")

    if args.repo:
        repo = Path(args.repo).resolve()
        try:
            head = git(repo, "rev-parse", "HEAD")
            tree = git(repo, "rev-parse", "HEAD^{tree}")
        except SystemExit:
            raise
        if head != EXPECTED_HEAD:
            die(f"Explicit repo HEAD mismatch: {head}; expected {EXPECTED_HEAD}")
        if tree != EXPECTED_TREE:
            die(f"Explicit repo tree mismatch: {tree}; expected {EXPECTED_TREE}")
    else:
        repo = find_repo(root)
    sys.path.insert(0, str(repo))

    from app.device_fingerprint.artifact_content import canonical_artifact_json
    from app.device_fingerprint.fe5_external_knowledge import (
        ExternalKnowledgeCandidate,
        build_ieee_k4_external_provenance,
        build_ieee_k4_freshness_policy,
        build_p0f_k2b_external_provenance,
        build_p0f_k2b_freshness_policy,
        build_satori_k1_external_provenance,
        build_satori_k1_freshness_policy,
        run_fe5_external_admission_gate,
    )
    from app.device_fingerprint.k1_satori_import import (
        build_satori_source_governance_candidate,
    )
    from app.device_fingerprint.k2b_p0f_import import (
        build_p0f_k2b_source_governance_candidate,
        verify_p0f_source_bytes,
    )
    from app.device_fingerprint.k4_ieee_import import (
        build_ieee_k4_source_governance_candidate,
        compute_ieee_k4_source_bundle_sha256,
    )

    # -------- retained source evidence / source bytes --------

    # The original accepted K1 audit is retained in Project evidence, but it
    # need not be copied into the Owner's local artifacts tree. Re-verify the
    # exact admitted source bytes locally and recreate a compact retained
    # source-evidence record using the frozen accepted acquisition timestamp.
    satori_path = find_satori_source(root)
    satori_bytes = satori_path.read_bytes()
    if sha256_bytes(satori_bytes) != SATORI_SHA256:
        die("Satori source bytes changed after discovery")
    satori_retrieved = SATORI_RETRIEVED_AT_UTC

    p0f_path = find_p0f_source(root)
    p0f_bytes = p0f_path.read_bytes()
    p0f_sha256 = verify_p0f_source_bytes(p0f_bytes)

    ieee_audit = find_named(artifacts, "ieee-k4-fe4-audit.json")
    ieee_report = load_json(ieee_audit)
    try:
        ieee_retrieved = ieee_report["audited_at_utc"]
        ieee_report_bundle = ieee_report["source_bundle_sha256"]
    except Exception:
        die("ieee-k4-fe4-audit.json lacks audited_at_utc/source_bundle_sha256")
    if ieee_report_bundle != IEEE_BUNDLE_SHA256:
        die(f"IEEE audit bundle mismatch: {ieee_report_bundle}")

    ieee_dir = ieee_audit.parent
    ma_l_path = ieee_dir / "oui.csv"
    ma_m_path = ieee_dir / "mam.csv"
    ma_s_path = ieee_dir / "oui36.csv"
    for p in (ma_l_path, ma_m_path, ma_s_path):
        if not p.is_file():
            die(f"Missing retained IEEE source file: {p}")
    ma_l, ma_m, ma_s = (p.read_bytes() for p in (ma_l_path, ma_m_path, ma_s_path))
    actual_ieee_bundle = compute_ieee_k4_source_bundle_sha256(ma_l, ma_m, ma_s)
    if actual_ieee_bundle != IEEE_BUNDLE_SHA256:
        die(f"Actual IEEE bundle mismatch: {actual_ieee_bundle}")

    # -------- exact accepted governance + freshness --------

    k1_gov = build_satori_source_governance_candidate()
    k2_gov = build_p0f_k2b_source_governance_candidate(p0f_bytes)
    k4_gov = build_ieee_k4_source_governance_candidate()

    k1_policy = build_satori_k1_freshness_policy()
    k2_policy = build_p0f_k2b_freshness_policy()
    k4_policy = build_ieee_k4_freshness_policy()

    expected_policy_digests = {
        "satori_dhcp": "0d33089e064fc58de96eb0c32789e9382fd2e26d213932cdf370b12b1ec6d3a5",
        "p0f3_legacy_tcp": "c509e8343debf97a6295d0a8ed56255d69f724346c2ac20b2955b891614e4f09",
        "ieee_ra_mac": "9a3a58d72dfb660b9a639b7558424cd55d213f8306e586c1b263aa4cda0d3df5",
    }
    actual_policy_digests = {
        "satori_dhcp": k1_policy.content_sha256,
        "p0f3_legacy_tcp": k2_policy.content_sha256,
        "ieee_ra_mac": k4_policy.content_sha256,
    }
    if actual_policy_digests != expected_policy_digests:
        die(f"Freshness policy identity mismatch: {actual_policy_digests}")

    # K1 uses exact acquisition time retained by its source audit.
    k1_prov = build_satori_k1_external_provenance(
        satori_bytes,
        retrieved_at_utc=satori_retrieved,
        governance=k1_gov,
        freshness_policy=k1_policy,
    )

    # K2B is explicitly legacy. A fresh TechLead-side retrieval of the exact
    # pinned Git blob was performed after PR publication. Its age > 0 ms is
    # intentionally stale-but-usable under the Owner-authorized V1 policy.
    k2_prov = build_p0f_k2b_external_provenance(
        p0f_bytes,
        retrieved_at_utc=P0F_RETRIEVED_AT_UTC,
        governance=k2_gov,
        freshness_policy=k2_policy,
    )

    # The IEEE audit downloads the three official files and immediately audits
    # them in the same run; audited_at_utc is retained as conservative acquisition evidence.
    k4_prov = build_ieee_k4_external_provenance(
        ma_l, ma_m, ma_s,
        retrieved_at_utc=ieee_retrieved,
        governance=k4_gov,
        freshness_policy=k4_policy,
    )

    k1 = ExternalKnowledgeCandidate(
        "K1", "satori_dhcp", "current",
        "direct admitted DHCP taxonomy mappings only; supporting authority; ambiguity preserved",
        k1_gov, k1_policy, k1_prov,
    )
    k2 = ExternalKnowledgeCandidate(
        "K2B", "p0f3_legacy_tcp", "legacy",
        "platform_family only; supporting authority; legacy source; other dimensions NO_CLAIM",
        k2_gov, k2_policy, k2_prov,
    )
    k4 = ExternalKnowledgeCandidate(
        "K4", "ieee_ra_mac", "current",
        "raw mac_assignment_org only; manufacturer_mapping remains null unless separately reviewed",
        k4_gov, k4_policy, k4_prov,
    )

    # -------- retained F-E5 rationale + p0f retrieval evidence --------

    out_dir = artifacts / "fe5-external-governance"
    out_dir.mkdir(parents=True, exist_ok=True)

    p0f_retrieval_evidence = {
        "evidence_contract": "captivportal.fe5.p0f_retrieval.v1",
        "repository": "peace-maker/p0f3-database",
        "commit": "7687e779c42c256c1f36b8c48da7e1f8fe24c2d4",
        "path": "p0f.fp",
        "git_blob_sha1": P0F_GIT_BLOB_SHA1,
        "local_verified_source_sha256": p0f_sha256,
        "retrieval_window_start_utc": P0F_RETRIEVED_AT_UTC,
        "retrieval_window_end_utc": P0F_RETRIEVAL_WINDOW_END_UTC,
        "provenance_retrieved_at_utc": P0F_RETRIEVED_AT_UTC,
        "retrieval_basis": (
            "TechLead-side retrieval of exact pinned GitHub blob after PR #154 publication; "
            "provenance uses start of retrieval window conservatively. Local retained p0f.fp "
            "must verify to the same Git blob SHA-1 before admission."
        ),
    }
    p0f_ev_path = out_dir / "fe5-p0f-retrieval-evidence.json"
    write_canonical_json(p0f_ev_path, p0f_retrieval_evidence)

    satori_source_evidence = {
        "evidence_contract": "captivportal.fe5.satori_source_evidence.v1",
        "repository": "xnih/satori",
        "commit": "c5dfcfbff31620e35248aa86da0c67f2ad4982f5",
        "path": "fingerprints/dhcp.xml",
        "git_blob_sha1": "a82926690c28d2147534f24bdbdbeb0d1a2970fb",
        "source_sha256": SATORI_SHA256,
        "retrieved_at_utc": SATORI_RETRIEVED_AT_UTC,
        "local_verified_path": str(satori_path),
        "local_verified_sha256": sha256_file(satori_path),
        "basis": (
            "Accepted K1 source-audit acquisition timestamp retained in project evidence; "
            "this F-E5 run independently re-verifies the exact admitted local dhcp.xml SHA256."
        ),
    }
    satori_ev_path = out_dir / "fe5-satori-source-evidence.json"
    write_canonical_json(satori_ev_path, satori_source_evidence)

    rationale = {
        "evidence_contract": "captivportal.fe5.freshness-rationale.v1",
        "owner_authorization": OWNER_AUTHORIZATION,
        "policies": {
            "satori_dhcp": {
                "fresh_max_age_ms": 31536000000,
                "stale_max_age_ms": 63072000000,
                "source_character": "current",
                "rationale": "Observed slow-changing Satori DHCP corpus; Owner-authorized 365d fresh / 730d stale.",
            },
            "p0f3_legacy_tcp": {
                "fresh_max_age_ms": 0,
                "stale_max_age_ms": 9223372036854775807,
                "source_character": "legacy",
                "rationale": "Explicit legacy corpus; any positive age is stale but remains supporting-only usable.",
            },
            "ieee_ra_mac": {
                "fresh_max_age_ms": 172800000,
                "stale_max_age_ms": 604800000,
                "source_character": "current",
                "rationale": "Official changing IEEE RA listing; Owner-authorized 48h fresh / 7d stale.",
            },
        },
        "state_rules": {
            "fresh": {
                "claim_eligible": True,
                "claim_strength_cap": "NO_ADDITIONAL_CAP",
                "required_explanation_code": None,
            },
            "stale": {
                "claim_eligible": True,
                "claim_strength_cap": "supporting",
                "required_explanation_code": "knowledge_source_stale",
            },
            "expired": {
                "claim_eligible": False,
                "claim_strength_cap": "NONE",
                "required_explanation_code": "knowledge_source_expired",
            },
        },
        "dimension_overrides": [],
        "pr154_head": EXPECTED_HEAD,
        "pr154_tree": EXPECTED_TREE,
    }
    rationale_path = out_dir / "fe5-freshness-rationale.json"
    write_canonical_json(rationale_path, rationale)

    # -------- Owner DecisionRecord audit registration --------

    decision_core = {
        "decision_record_id": OWNER_DECISION_ID,
        "decision_subject_type": "FOUNDATION_EXTERNAL_KNOWLEDGE_ADMISSION",
        "decision_subject_id": "F-E5",
        "decision": "ACCEPT",
        "decided_at_utc": OWNER_DECIDED_AT_UTC,
        "actor_role": "OWNER",
        "referenced_artifact_ids": sorted([
            k1_gov.artifact_id, k1_policy.artifact_id,
            k2_gov.artifact_id, k2_policy.artifact_id,
            k4_gov.artifact_id, k4_policy.artifact_id,
        ]),
        "referenced_gate_ids": ["F-E5"],
        "reason_reference_text": (
            OWNER_AUTHORIZATION
            + " Decision timestamp comes from the Owner authorization chat event at "
              "second precision and is normalized to R14 UtcMs by zero-filling milliseconds."
        ),
    }
    decision_record = {
        **decision_core,
        "record_sha256": hashlib.sha256(canonical_artifact_json(decision_core)).hexdigest(),
    }
    decision_path = out_dir / "fe5-owner-decision-record.json"
    write_canonical_json(decision_path, decision_record)

    retained_evidence = [
        evidence_ref("K1_SATORI_SOURCE_EVIDENCE", satori_ev_path),
        evidence_ref("K4_IEEE_SOURCE_AUDIT", ieee_audit),
        evidence_ref("K2B_P0F_RETRIEVAL_EVIDENCE", p0f_ev_path),
        evidence_ref("F_E5_FRESHNESS_THRESHOLD_RATIONALE", rationale_path),
        evidence_ref("F_E5_OWNER_DECISION_RECORD", decision_path),
    ]

    # -------- the one real admission gate --------

    execution = run_fe5_external_admission_gate(
        k1, k2, k4,
        candidate_repository_commit_sha=EXPECTED_HEAD,
        candidate_repository_tree_sha=EXPECTED_TREE,
        environment_identity="OWNER_LOCAL_WINDOWS_PR154",
        retained_evidence_refs=retained_evidence,
        decision_record_refs=[OWNER_DECISION_ID],
    )

    gate = execution.gate_result_manifest
    gate_envelope = artifact_envelope(gate)

    accepted = [
        k1_gov, k1_policy, k1_prov,
        k2_gov, k2_policy, k2_prov,
        k4_gov, k4_policy, k4_prov,
    ]

    artifacts_path = out_dir / "fe5-accepted-external-artifacts.json"
    write_canonical_json(artifacts_path, {
        "candidate_repository_commit_sha": EXPECTED_HEAD,
        "candidate_repository_tree_sha": EXPECTED_TREE,
        "artifacts": [artifact_envelope(a) for a in sorted(accepted, key=lambda x: x.artifact_id)],
    })

    gate_path = out_dir / "fe5-gate-result-manifest.json"
    write_canonical_json(gate_path, gate_envelope)

    execution_path = out_dir / "fe5-gate-execution.json"
    write_canonical_json(execution_path, {
        "foundation_knowledge_evaluation_at_utc": execution.foundation_knowledge_evaluation_at_utc,
        "per_source": list(execution.per_source),
        "failure_reasons": list(execution.failure_reasons),
        "gate_result_manifest": gate_envelope,
        "source_paths": {
            "satori": str(satori_path),
            "p0f": str(p0f_path),
            "ieee_ma_l": str(ma_l_path),
            "ieee_ma_m": str(ma_m_path),
            "ieee_ma_s": str(ma_s_path),
        },
        "source_evidence_paths": {
            "satori_source_evidence": str(satori_ev_path),
            "ieee_audit": str(ieee_audit),
            "p0f_retrieval": str(p0f_ev_path),
            "freshness_rationale": str(rationale_path),
            "owner_decision_record": str(decision_path),
        },
    })

    print(f"PR_HEAD={EXPECTED_HEAD}")
    print(f"PR_TREE={EXPECTED_TREE}")
    print(f"REPO={repo}")
    print(f"K1_RETRIEVED_AT_UTC={satori_retrieved}")
    print(f"K2B_RETRIEVED_AT_UTC={P0F_RETRIEVED_AT_UTC}")
    print(f"K2B_SOURCE_SHA256={p0f_sha256}")
    print(f"K4_RETRIEVED_AT_UTC={ieee_retrieved}")
    print(f"K4_BUNDLE_SHA256={actual_ieee_bundle}")
    for row in execution.per_source:
        print(
            f"{row['source_family_id']}: "
            f"state={row['freshness_state']} age_ms={row['age_ms']} "
            f"eligible={row['claim_eligible']} cap={row['claim_strength_cap']}"
        )
    print(f"GATE_STATUS={gate.semantic_payload['status']}")
    print(f"GATE_ARTIFACT_ID={gate.artifact_id}")
    print(f"GATE_CONTENT_SHA256={gate.content_sha256}")
    print(f"OWNER_DECISION_ID={OWNER_DECISION_ID}")
    print(f"FAILURE_REASONS={list(execution.failure_reasons)}")
    print(f"GATE_REPORT={gate_path}")
    print(f"EXECUTION_REPORT={execution_path}")
    print(f"ACCEPTED_ARTIFACTS={artifacts_path}")
    print(f"DECISION_RECORD={decision_path}")

    if gate.semantic_payload["status"] != "PASS":
        raise SystemExit(1)

    print("F-E5 REAL ADMISSION GATE = PASS")

if __name__ == "__main__":
    main()
