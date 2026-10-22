from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_HEAD = "427b4e8e9389a6181f878fc0a2ead201f868124f"
EXPECTED_PARENT = "c259364febe4401983ea5f1ede4a255077b8db84"
EXPECTED_TREE = "8a36835d5a8d046d494e15ddcde40ed419de0413"

EXPECTED_POLICY_SHA256 = "806779ca1844e55083a2c1c464cf8d94a9bdd0b2f97436d203b63fd03e81bea5"
EXPECTED_POLICY_ID = "ProductValidationPolicy:v1:sha256:" + EXPECTED_POLICY_SHA256

EXPECTED_PATCH_SHA256 = "a03e775183c9c5108e147087bf31a38f1c91ccc89220f07e8dfea1527657bdb3"
PATCH_PATH = Path(
    r"C:\CaptivPortal-Lab\artifacts\TASK-DEVICE-FINGERPRINT-FF4-PRODUCT-VALIDATION-POLICY-01.patch"
)

REVIEW_LABEL = "product_validation_policy_review"
OWNER_REG_LABEL = "product_validation_owner_decision_registration"

EXPECTED_PAYLOAD = {
    "product_validation_policy_version": 1,
    "known_dimension_wrong_resolved_behavior": "FAIL",
    "false_out_of_scope_behavior": "FAIL",
    "android_required_platform": "android",
    "android_min_support": "medium",
    "windows_required_platform": "windows",
    "windows_min_support": "medium",
    "minimum_correct_device_class_count_across_controlled_devices": 1,
    "device_class_min_support": "medium",
    "ground_truth_must_preexist_result": True,
    "automatic_learning_forbidden": True,
}


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
    return datetime.now(timezone.utc).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")


def write_canonical_json(path: Path, obj: dict, canonical_artifact_json) -> str:
    raw = canonical_artifact_json(obj) + b"\n"
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def validate_uuid4_text(value: str) -> None:
    try:
        parsed = uuid.UUID(value)
    except ValueError:
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
        default=r"C:\CaptivPortal-Lab\artifacts\ff4-real-acceptance-427b4e8e",
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
    from app.device_fingerprint.ff4_product_validation_policy import (
        run_ff4_product_validation_policy_gate,
    )
    from app.device_fingerprint.product_validation_policy import (
        build_initial_product_validation_policy_v1,
    )

    policy = build_initial_product_validation_policy_v1()

    if policy.artifact_id != EXPECTED_POLICY_ID:
        die(f"policy artifact ID mismatch: {policy.artifact_id}")
    if policy.content_sha256 != EXPECTED_POLICY_SHA256:
        die(f"policy SHA mismatch: {policy.content_sha256}")
    if policy.semantic_payload != EXPECTED_PAYLOAD:
        die(f"initial policy payload mismatch: {policy.semantic_payload!r}")

    if out.exists():
        die(f"acceptance output directory already exists: {out}")
    out.mkdir(parents=True)

    # Policy review evidence. This records the already Owner-approved policy
    # before any controlled classifier result is used to alter validation criteria.
    review = {
        "review_contract": "R14-F-F4-POLICY-REVIEW-v1",
        "product_validation_policy_id": policy.artifact_id,
        "product_validation_policy_sha256": policy.content_sha256,
        "policy_frozen_before_classifier_results_viewed": True,
        "result_driven_relabeling_forbidden": True,
        "automatic_learning_forbidden": True,
        "ground_truth_must_preexist_result": True,
        "wrong_resolved_known_dimension_behavior": "FAIL",
        "false_out_of_scope_behavior": "FAIL",
        "android_requirement": {
            "platform_family": "android",
            "minimum_support": "medium",
        },
        "windows_requirement": {
            "platform_family": "windows",
            "minimum_support": "medium",
        },
        "device_class_requirement": {
            "minimum_correct_count_across_controlled_devices": 1,
            "minimum_support": "medium",
        },
        "controlled_device_roles_required": [
            "OWNER_ANDROID_SMARTPHONE",
            "OWNER_WINDOWS_LAPTOP",
        ],
        "t09_execution_not_performed_by_ff4": True,
        "lab_candidate_head": head,
        "lab_candidate_tree": tree,
        "reviewed_patch_sha256": patch_sha,
    }
    review_path = out / "product-validation-policy-review.json"
    review_sha = write_canonical_json(
        review_path, review, canonical_artifact_json
    )

    # Exact R14 DecisionRecord audit contract.
    owner_id = str(uuid.uuid4())
    validate_uuid4_text(owner_id)

    owner_body = {
        "decision_record_id": owner_id,
        "decision_subject_type": "ProductValidationPolicy",
        "decision_subject_id": policy.artifact_id,
        "decision": "ACCEPT",
        "decided_at_utc": utc_now_ms(),
        "actor_role": "OWNER",
        "referenced_artifact_ids": [policy.artifact_id],
        "referenced_gate_ids": [],
        "reason_reference_text": (
            "OWNER ACCEPT F-F4; validation criteria frozen before classifier "
            "results are used: wrong resolved known dimension FAIL; false "
            "out-of-scope FAIL; Android/Windows platform support >= medium; "
            "at least one correct device_class >= medium; pre-result ground "
            "truth required; automatic learning forbidden."
        ),
    }

    # Arrays are already lexicographically sorted and SET-like.
    if owner_body["referenced_artifact_ids"] != sorted(
        set(owner_body["referenced_artifact_ids"])
    ):
        die("Owner DecisionRecord artifact refs are not canonical SET-like")
    if owner_body["referenced_gate_ids"] != sorted(
        set(owner_body["referenced_gate_ids"])
    ):
        die("Owner DecisionRecord gate refs are not canonical SET-like")

    owner_body["record_sha256"] = hashlib.sha256(
        canonical_artifact_json(owner_body)
    ).hexdigest()

    if owner_body["actor_role"] != "OWNER":
        die("Owner DecisionRecord actor mismatch")
    if owner_body["decision"] != "ACCEPT":
        die("Owner DecisionRecord decision mismatch")
    if owner_body["decision_subject_type"] != "ProductValidationPolicy":
        die("Owner DecisionRecord subject type mismatch")
    if owner_body["decision_subject_id"] != policy.artifact_id:
        die("Owner DecisionRecord subject ID mismatch")
    if owner_body["referenced_artifact_ids"] != [policy.artifact_id]:
        die("Owner DecisionRecord artifact refs mismatch")
    if owner_body["referenced_gate_ids"] != []:
        die("Owner DecisionRecord gate refs must be empty before F-F4 execution")

    owner_path = out / "decision-owner.json"
    owner_file_sha = write_canonical_json(
        owner_path, owner_body, canonical_artifact_json
    )

    evidence = [
        {
            "evidence_label": REVIEW_LABEL,
            "file_sha256": review_sha,
            "media_type": "application/json",
            "path_or_reference": str(review_path),
        },
        {
            "evidence_label": OWNER_REG_LABEL,
            "file_sha256": owner_file_sha,
            "media_type": "application/json",
            "path_or_reference": str(owner_path),
        },
    ]

    execution = run_ff4_product_validation_policy_gate(
        policy,
        candidate_repository_commit_sha=head,
        candidate_repository_tree_sha=tree,
        environment_identity="windows-central-lab-ff4-real-admission",
        retained_evidence_refs=evidence,
        decision_record_refs=[owner_id],
    )

    manifest = execution.gate_result_manifest
    gate = manifest.semantic_payload

    if gate["status"] != "PASS":
        die(f"real F-F4 gate FAIL: {execution.failure_reasons}")
    if execution.failure_reasons:
        die(f"unexpected F-F4 failure reasons: {execution.failure_reasons}")
    if gate["gate_id"] != "F-F4":
        die("wrong gate ID")
    if gate["gate_contract_version"] != "R14-F-F4-v1":
        die("wrong gate contract version")
    if gate["candidate_repository_commit_sha"] != head:
        die("gate candidate commit mismatch")
    if gate["candidate_repository_tree_sha"] != tree:
        die("gate candidate tree mismatch")
    if gate["input_artifact_refs"] != []:
        die("F-F4 input artifact refs must be empty")
    if len(gate["output_artifact_refs"]) != 1:
        die("F-F4 output artifact ref count != 1")
    if gate["output_artifact_refs"][0]["artifact_id"] != policy.artifact_id:
        die("F-F4 output is not exact policy")
    if gate["output_artifact_refs"][0]["content_sha256"] != policy.content_sha256:
        die("F-F4 output digest mismatch")
    if gate["decision_record_refs"] != [owner_id]:
        die("F-F4 decision refs mismatch")
    if any(value is not None for value in gate["trusted_time_inputs"].values()):
        die("F-F4 unexpectedly captured trusted semantic time")

    labels = [row["evidence_label"] for row in gate["retained_evidence_refs"]]
    if sorted(labels) != sorted([REVIEW_LABEL, OWNER_REG_LABEL]):
        die(f"F-F4 retained evidence labels mismatch: {labels}")

    manifest_doc = {
        "artifact_id": manifest.artifact_id,
        "artifact_schema_version": manifest.artifact_schema_version,
        "artifact_type": manifest.artifact_type,
        "content_sha256": manifest.content_sha256,
        "semantic_payload": manifest.semantic_payload,
    }
    gate_path = out / "ff4-gate-result-manifest.json"
    gate_file_sha = write_canonical_json(
        gate_path, manifest_doc, canonical_artifact_json
    )

    summary = {
        "F_F4_FAILURE_REASONS": list(execution.failure_reasons),
        "F_F4_GATE_ARTIFACT_ID": manifest.artifact_id,
        "F_F4_GATE_CONTENT_SHA256": manifest.content_sha256,
        "F_F4_GATE_FILE_SHA256": gate_file_sha,
        "F_F4_INPUT_REF_COUNT": len(gate["input_artifact_refs"]),
        "F_F4_OUTPUT_REF_COUNT": len(gate["output_artifact_refs"]),
        "F_F4_STATUS": gate["status"],
        "LAB_HEAD": head,
        "LAB_TREE": tree,
        "OWNER_DECISION_FILE_SHA256": owner_file_sha,
        "OWNER_DECISION_ID": owner_id,
        "PATCH_SHA256": patch_sha,
        "POLICY_ARTIFACT_ID": policy.artifact_id,
        "POLICY_CONTENT_SHA256": policy.content_sha256,
        "POLICY_REVIEW_SHA256": review_sha,
        "WORKTREE_CLEAN_AFTER_GATE": run_git(repo, "status", "--short") == "",
    }

    summary_path = out / "acceptance-summary.json"
    write_canonical_json(summary_path, summary, canonical_artifact_json)

    print("============================================================")
    print("F-F4 REAL ACCEPTANCE GATE")
    print("============================================================")
    for key in sorted(summary):
        print(f"{key}={summary[key]}")
    print(f"POLICY_REVIEW_PATH={review_path}")
    print(f"OWNER_DECISION_PATH={owner_path}")
    print(f"GATE_MANIFEST_PATH={gate_path}")
    print(f"SUMMARY_PATH={summary_path}")
    print("============================================================")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
