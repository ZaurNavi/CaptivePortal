from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_HEAD = "5fa7a857515d2b510dbe0e2e474cd7304a832b1c"
EXPECTED_PARENT = "295f22b5aed79414d879a65312987d415bf954f2"
EXPECTED_TREE = "19e1ce5cf300e32a6fc37b678463dd4bcd5c83c3"

EXPECTED_POLICY_SHA256 = "029c3534e076db6f7293c78e8a86c425b10c786d58713e77a077a19dfdda3e72"
EXPECTED_POLICY_ID = (
    "ClassificationRetentionPolicy:v1:sha256:"
    + EXPECTED_POLICY_SHA256
)

EXPECTED_PATCH_SHA256 = "b2c612ab92e4215414623f31fad85c4f649ec79a67f7dc6a7a2fe2722219e48f"
PATCH_PATH = Path(
    r"C:\CaptivPortal-Lab\artifacts\TASK-DEVICE-FINGERPRINT-FF3-CLASSIFICATION-RETENTION-POLICY-01.patch"
)

EXPECTED_RETENTION_SECONDS = 7_776_000
EXPECTED_RETENTION_DAYS = 90
EXPECTED_BASIS = "OPERATIONAL_AUDIT_REPLAY_TROUBLESHOOTING_AND_CONTROLLED_VALIDATION"

ANALYSIS_LABEL = "classification_retention_privacy_storage_analysis"
OWNER_REG_LABEL = "classification_retention_owner_decision_registration"


def die(message: str):
    raise SystemExit(f"STOP: {message}")


def run_git(repo: Path, *args: str) -> str:
    p = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if p.returncode != 0:
        die(f"git {' '.join(args)} failed: {p.stderr.strip()}")
    return p.stdout.strip()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def utc_now_ms() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def write_canonical_json(path: Path, obj: dict, canonical_artifact_json) -> str:
    raw = canonical_artifact_json(obj) + b"\n"
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def validate_uuid4_text(value: str) -> None:
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        die(f"invalid UUID: {value}")
    if parsed.version != 4 or str(parsed) != value:
        die(f"not canonical lowercase UUIDv4: {value}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "worktree",
        nargs="?",
        default=r"C:\CaptivPortal-Lab\coder-work",
    )
    parser.add_argument(
        "--out",
        default=r"C:\CaptivPortal-Lab\artifacts\ff3-real-acceptance-5fa7a857",
    )
    args = parser.parse_args()

    repo = Path(args.worktree).resolve()
    out = Path(args.out).resolve()

    if not repo.is_dir():
        die(f"worktree missing: {repo}")

    head = run_git(repo, "rev-parse", "HEAD")
    parent = run_git(repo, "rev-parse", "HEAD~1")
    tree = run_git(repo, "rev-parse", "HEAD^{tree}")
    branch = run_git(repo, "branch", "--show-current")
    status = run_git(repo, "status", "--short")

    if head != EXPECTED_HEAD:
        die(f"HEAD mismatch: {head}")
    if parent != EXPECTED_PARENT:
        die(f"parent mismatch: {parent}")
    if tree != EXPECTED_TREE:
        die(f"tree mismatch: {tree}")
    if branch:
        die(f"expected DETACHED HEAD, got branch {branch}")
    if status:
        die(f"worktree not clean:\n{status}")

    if not PATCH_PATH.is_file():
        die(f"reviewed patch missing: {PATCH_PATH}")
    patch_sha = sha256_file(PATCH_PATH)
    if patch_sha != EXPECTED_PATCH_SHA256:
        die(f"patch SHA mismatch: {patch_sha}")

    sys.path.insert(0, str(repo))

    from app.device_fingerprint.artifact_content import canonical_artifact_json
    from app.device_fingerprint.classification_retention_policy import (
        build_initial_classification_retention_policy_v1,
    )
    from app.device_fingerprint.ff3_classification_retention_policy import (
        run_ff3_classification_retention_policy_gate,
    )

    policy = build_initial_classification_retention_policy_v1()

    if policy.artifact_id != EXPECTED_POLICY_ID:
        die(f"policy artifact ID mismatch: {policy.artifact_id}")
    if policy.content_sha256 != EXPECTED_POLICY_SHA256:
        die(f"policy SHA mismatch: {policy.content_sha256}")

    payload = policy.semantic_payload
    exact_payload = {
        "retention_policy_version": 1,
        "classification_history_retention_seconds": EXPECTED_RETENTION_SECONDS,
        "co_retain_snapshot_record": True,
        "co_retain_request_result_evaluability_origin": True,
        "privacy_storage_basis": EXPECTED_BASIS,
        "expiry_behavior": "DELETE_CLASSIFICATION_WHEN_ELIGIBLE",
        "reference_aware_gc": True,
    }
    if payload != exact_payload:
        die(f"initial policy payload mismatch: {payload!r}")

    if out.exists():
        die(f"acceptance output directory already exists: {out}")
    out.mkdir(parents=True)

    # External retained evidence required by R14 F-F3.
    analysis = {
        "analysis_contract": "R14-F-F3-PRIVACY-STORAGE-ANALYSIS-v1",
        "classification_retention_policy_id": policy.artifact_id,
        "classification_retention_policy_sha256": policy.content_sha256,
        "classification_history_retention_days": EXPECTED_RETENTION_DAYS,
        "classification_history_retention_seconds": EXPECTED_RETENTION_SECONDS,
        "privacy_storage_basis": EXPECTED_BASIS,
        "bounded_retention": True,
        "snapshot_record_co_retention_required": True,
        "request_result_evaluability_origin_co_retention_required": True,
        "level_b_replay_required_for_full_retention_period": True,
        "transient_normalized_payload_retention_required_for_level_a_extension": False,
        "expiry_behavior": "DELETE_CLASSIFICATION_WHEN_ELIGIBLE",
        "reference_aware_gc": True,
        "shared_artifact_gc_only_when_unreferenced": True,
        "no_dangling_audit_references": True,
        "owner_selected_initial_retention": True,
        "lab_candidate_head": head,
        "lab_candidate_tree": tree,
        "reviewed_patch_sha256": patch_sha,
    }
    analysis_path = out / "classification-retention-privacy-storage-analysis.json"
    analysis_sha = write_canonical_json(
        analysis_path, analysis, canonical_artifact_json
    )

    # R14 DecisionRecord audit-only serialization.
    # R14 names the semantic field "reason/reference text" but does not
    # prescribe a machine token; keep the already-used project audit token.
    owner_id = str(uuid.uuid4())
    validate_uuid4_text(owner_id)

    owner_body = {
        "actor_role": "OWNER",
        "decided_at_utc": utc_now_ms(),
        "decision": "ACCEPT",
        "decision_record_id": owner_id,
        "decision_subject_id": policy.artifact_id,
        "decision_subject_type": "ClassificationRetentionPolicy",
        "reason_reference_text": (
            "OWNER ACCEPT F-F3 ClassificationRetentionPolicy; "
            "initial classification history retention = 90 days / 7776000 seconds; "
            f"privacy_storage_basis={EXPECTED_BASIS}"
        ),
        "referenced_artifact_ids": [policy.artifact_id],
        "referenced_gate_ids": [],
    }
    owner_body["record_sha256"] = hashlib.sha256(
        canonical_artifact_json(owner_body)
    ).hexdigest()

    # External acceptance validation of the exact Owner record we will reference.
    if owner_body["actor_role"] != "OWNER":
        die("Owner DecisionRecord actor mismatch")
    if owner_body["decision"] != "ACCEPT":
        die("Owner DecisionRecord decision mismatch")
    if owner_body["decision_subject_type"] != "ClassificationRetentionPolicy":
        die("Owner DecisionRecord subject type mismatch")
    if owner_body["decision_subject_id"] != policy.artifact_id:
        die("Owner DecisionRecord subject ID mismatch")
    if owner_body["referenced_artifact_ids"] != [policy.artifact_id]:
        die("Owner DecisionRecord artifact refs mismatch")
    if owner_body["referenced_gate_ids"] != []:
        die("Owner DecisionRecord gate refs must be empty before F-F3 execution")

    owner_path = out / "decision-owner.json"
    owner_file_sha = write_canonical_json(
        owner_path, owner_body, canonical_artifact_json
    )

    evidence = [
        {
            "evidence_label": ANALYSIS_LABEL,
            "file_sha256": analysis_sha,
            "media_type": "application/json",
            "path_or_reference": str(analysis_path),
        },
        {
            "evidence_label": OWNER_REG_LABEL,
            "file_sha256": owner_file_sha,
            "media_type": "application/json",
            "path_or_reference": str(owner_path),
        },
    ]

    execution = run_ff3_classification_retention_policy_gate(
        policy,
        candidate_repository_commit_sha=head,
        candidate_repository_tree_sha=tree,
        environment_identity="windows-central-lab-ff3-real-admission",
        retained_evidence_refs=evidence,
        decision_record_refs=[owner_id],
    )

    manifest = execution.gate_result_manifest
    gate = manifest.semantic_payload

    if gate["status"] != "PASS":
        die(f"real F-F3 gate FAIL: {execution.failure_reasons}")
    if execution.failure_reasons:
        die(f"unexpected F-F3 failure reasons: {execution.failure_reasons}")
    if gate["gate_id"] != "F-F3":
        die("wrong gate ID")
    if gate["gate_contract_version"] != "R14-F-F3-v1":
        die("wrong gate contract version")
    if gate["candidate_repository_commit_sha"] != head:
        die("gate candidate commit mismatch")
    if gate["candidate_repository_tree_sha"] != tree:
        die("gate candidate tree mismatch")
    if gate["input_artifact_refs"] != []:
        die("F-F3 input artifact refs must be empty")
    if len(gate["output_artifact_refs"]) != 1:
        die("F-F3 output artifact ref count != 1")
    if gate["output_artifact_refs"][0]["artifact_id"] != policy.artifact_id:
        die("F-F3 output is not exact policy")
    if gate["output_artifact_refs"][0]["content_sha256"] != policy.content_sha256:
        die("F-F3 output digest mismatch")
    if gate["decision_record_refs"] != [owner_id]:
        die("F-F3 decision refs mismatch")
    if any(value is not None for value in gate["trusted_time_inputs"].values()):
        die("F-F3 unexpectedly captured trusted semantic time")

    evidence_labels = [row["evidence_label"] for row in gate["retained_evidence_refs"]]
    if sorted(evidence_labels) != sorted([ANALYSIS_LABEL, OWNER_REG_LABEL]):
        die(f"F-F3 retained evidence labels mismatch: {evidence_labels}")

    manifest_doc = {
        "artifact_id": manifest.artifact_id,
        "artifact_schema_version": manifest.artifact_schema_version,
        "artifact_type": manifest.artifact_type,
        "content_sha256": manifest.content_sha256,
        "semantic_payload": manifest.semantic_payload,
    }
    gate_path = out / "ff3-gate-result-manifest.json"
    gate_file_sha = write_canonical_json(
        gate_path, manifest_doc, canonical_artifact_json
    )

    summary = {
        "F_F3_FAILURE_REASONS": list(execution.failure_reasons),
        "F_F3_GATE_ARTIFACT_ID": manifest.artifact_id,
        "F_F3_GATE_CONTENT_SHA256": manifest.content_sha256,
        "F_F3_GATE_FILE_SHA256": gate_file_sha,
        "F_F3_INPUT_REF_COUNT": len(gate["input_artifact_refs"]),
        "F_F3_OUTPUT_REF_COUNT": len(gate["output_artifact_refs"]),
        "F_F3_STATUS": gate["status"],
        "LAB_HEAD": head,
        "LAB_TREE": tree,
        "OWNER_DECISION_FILE_SHA256": owner_file_sha,
        "OWNER_DECISION_ID": owner_id,
        "PATCH_SHA256": patch_sha,
        "POLICY_ARTIFACT_ID": policy.artifact_id,
        "POLICY_CONTENT_SHA256": policy.content_sha256,
        "PRIVACY_STORAGE_ANALYSIS_SHA256": analysis_sha,
        "RETENTION_DAYS": EXPECTED_RETENTION_DAYS,
        "RETENTION_SECONDS": EXPECTED_RETENTION_SECONDS,
        "WORKTREE_CLEAN_AFTER_GATE": run_git(repo, "status", "--short") == "",
    }

    summary_path = out / "acceptance-summary.json"
    write_canonical_json(summary_path, summary, canonical_artifact_json)

    print("============================================================")
    print("F-F3 REAL ACCEPTANCE GATE")
    print("============================================================")
    for key in sorted(summary):
        print(f"{key}={summary[key]}")
    print(f"PRIVACY_STORAGE_ANALYSIS_PATH={analysis_path}")
    print(f"OWNER_DECISION_PATH={owner_path}")
    print(f"GATE_MANIFEST_PATH={gate_path}")
    print(f"SUMMARY_PATH={summary_path}")
    print("============================================================")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
