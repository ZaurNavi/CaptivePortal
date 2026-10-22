from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_HEAD = "e08e99ee00cc0bb2bbd9f1fd0cbd96cfa5a2e32c"
EXPECTED_PARENT = "f6615836ff83aba211f9cc5da935c6ff5fbe561c"
EXPECTED_TREE = "c1a30597d4b5474856ff14fa57c5b9cb3ef24b88"
EXPECTED_POLICY_ID = "ClassificationPolicy:v1:sha256:6341a9f9781ead1b1ab5ba2065b7eda6c0c77b4d8736db2eae6a04ef881daf3e"
EXPECTED_POLICY_SHA256 = "6341a9f9781ead1b1ab5ba2065b7eda6c0c77b4d8736db2eae6a04ef881daf3e"
EXPECTED_VECTOR_SHA256 = "6ac3f1016072add2df4f954e7d50efe54e093887da8e6304e43b14d57537de07"
EXPECTED_PATCH_SHA256 = "eba80fef879fa1d29503b9eeda6b8d2736d53dc93687f8570ed4108af7a6ec7b"

TAXONOMY_ID = "ClassificationTaxonomy:v1:sha256:399e2a337e7ebecb1bd7a9b21dff5e744c13be36313bc39f16832bc7a57a4d10"
ALIAS_ID = "AliasMapping:v1:sha256:f1cdd7c9510c2a33bad99bd1ae15eaccd20fcb828a52e02533b9917fdfc2e228"
ADAPTER_ID = "EvidenceAdapterContractSet:v1:sha256:7cca6802ebc5839317643dcb584173b75d985477da687ab0d8fe5802b181f788"

VECTOR_REL = Path("tests/device_fingerprint_ff2/fixtures/classification_policy_vectors_v1.json")
PATCH_PATH = Path(r"C:\CaptivPortal-Lab\artifacts\TASK-DEVICE-FINGERPRINT-FF2-CLASSIFICATION-POLICY-01-FIX1.patch")


def die(message: str):
    raise SystemExit(f"STOP: {message}")


def run_git(repo: Path, *args: str) -> str:
    p = subprocess.run(
        ["git", *args], cwd=repo, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
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
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def write_canonical_json(path: Path, obj: dict, canonical_artifact_json) -> str:
    raw = canonical_artifact_json(obj) + b"\n"
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("worktree", nargs="?", default=r"C:\CaptivPortal-Lab\coder-work")
    parser.add_argument("--out", default=r"C:\CaptivPortal-Lab\artifacts\ff2-real-acceptance-e08e99ee")
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

    vector = repo / VECTOR_REL
    if not vector.is_file():
        die(f"vector file missing: {vector}")
    vector_sha = sha256_file(vector)
    if vector_sha != EXPECTED_VECTOR_SHA256:
        die(f"vector SHA mismatch: {vector_sha}")

    if not PATCH_PATH.is_file():
        die(f"reviewed patch missing: {PATCH_PATH}")
    patch_sha = sha256_file(PATCH_PATH)
    if patch_sha != EXPECTED_PATCH_SHA256:
        die(f"patch SHA mismatch: {patch_sha}")

    sys.path.insert(0, str(repo))

    from app.device_fingerprint.artifact_content import canonical_artifact_json
    from app.device_fingerprint.classification_policy import build_initial_classification_policy_v1
    from app.device_fingerprint.evidence_adapter_contracts import build_initial_evidence_adapter_contract_set_v1
    from app.device_fingerprint.ff2_classification_policy import run_ff2_classification_policy_gate
    from app.device_fingerprint.foundation_schema_artifacts import build_foundation_schema_artifacts
    from app.device_fingerprint.taxonomy_artifacts import build_alias_mapping_v1, build_classification_taxonomy_v1

    registry = build_foundation_schema_artifacts()["EvidenceSchemaRegistryContract"]
    taxonomy = build_classification_taxonomy_v1()
    alias = build_alias_mapping_v1()
    adapters = build_initial_evidence_adapter_contract_set_v1(registry)

    if taxonomy.artifact_id != TAXONOMY_ID:
        die(f"taxonomy ID mismatch: {taxonomy.artifact_id}")
    if alias.artifact_id != ALIAS_ID:
        die(f"alias ID mismatch: {alias.artifact_id}")
    if adapters.artifact_id != ADAPTER_ID:
        die(f"adapter ID mismatch: {adapters.artifact_id}")

    policy = build_initial_classification_policy_v1(taxonomy, alias, adapters)
    if policy.artifact_id != EXPECTED_POLICY_ID:
        die(f"policy ID mismatch: {policy.artifact_id}")
    if policy.content_sha256 != EXPECTED_POLICY_SHA256:
        die(f"policy SHA mismatch: {policy.content_sha256}")

    if out.exists():
        die(f"acceptance output directory already exists: {out}")
    out.mkdir(parents=True)

    review = {
        "adapter_contract_set_id": adapters.artifact_id,
        "alias_mapping_id": alias.artifact_id,
        "baseline_commit": EXPECTED_PARENT,
        "classification_policy_id": policy.artifact_id,
        "classification_policy_sha256": policy.content_sha256,
        "compatibility_result": "PASS_137",
        "compileall_result": "PASS",
        "decision_requirement": "OWNER_PLUS_TECHLEAD_ACCEPT",
        "diff_check_result": "PASS",
        "focused_result": "PASS_77",
        "lab_candidate_head": head,
        "lab_candidate_tree": tree,
        "owner_acceptance": "ACCEPT",
        "patch_sha256": patch_sha,
        "report_contract": "R14-F-F2-TECHLEAD14-REVIEW-v1",
        "source_review": "PASS",
        "taxonomy_id": taxonomy.artifact_id,
        "techlead14_acceptance": "ACCEPT",
        "test_vector_sha256": vector_sha,
    }
    review_path = out / "classification-policy-review-report.json"
    review_sha = write_canonical_json(review_path, review, canonical_artifact_json)

    def make_decision(actor_role: str, reason: str, filename: str):
        record_id = str(uuid.uuid4())
        body = {
            "actor_role": actor_role,
            "decided_at_utc": utc_now_ms(),
            "decision": "ACCEPT",
            "decision_record_id": record_id,
            "decision_subject_id": policy.artifact_id,
            "decision_subject_type": "ClassificationPolicy",
            "reason_reference_text": reason,
            "referenced_artifact_ids": [policy.artifact_id],
            "referenced_gate_ids": [],
        }
        body["record_sha256"] = hashlib.sha256(canonical_artifact_json(body)).hexdigest()
        path = out / filename
        file_sha = write_canonical_json(path, body, canonical_artifact_json)
        return record_id, file_sha, path

    owner_id, owner_file_sha, owner_path = make_decision(
        "OWNER",
        "OWNER ACCEPT F-F2 ClassificationPolicy " + EXPECTED_POLICY_SHA256,
        "decision-owner.json",
    )
    techlead_id, techlead_file_sha, techlead_path = make_decision(
        "OTHER_EXPLICIT_ROLE",
        "TECHLEAD14 ACCEPT F-F2 ClassificationPolicy " + EXPECTED_POLICY_SHA256 + "; source review PASS; FIX-1 PASS.",
        "decision-techlead14.json",
    )

    evidence = [
        {
            "evidence_label": "classification_policy_test_vectors",
            "file_sha256": vector_sha,
            "media_type": "application/json",
            "path_or_reference": str(vector),
        },
        {
            "evidence_label": "classification_policy_review_report",
            "file_sha256": review_sha,
            "media_type": "application/json",
            "path_or_reference": str(review_path),
        },
    ]

    execution = run_ff2_classification_policy_gate(
        policy,
        classification_taxonomy=taxonomy,
        alias_mapping=alias,
        evidence_adapter_contract_set=adapters,
        candidate_repository_commit_sha=head,
        candidate_repository_tree_sha=tree,
        environment_identity="windows-central-lab-ff2-real-admission",
        retained_evidence_refs=evidence,
        decision_record_refs=[owner_id, techlead_id],
    )

    manifest = execution.gate_result_manifest
    payload = manifest.semantic_payload

    if payload["status"] != "PASS":
        die(f"real F-F2 gate FAIL: {execution.failure_reasons}")
    if execution.failure_reasons:
        die(f"unexpected failure reasons: {execution.failure_reasons}")
    if len(payload["input_artifact_refs"]) != 3:
        die("real gate input-ref count != 3")
    if len(payload["output_artifact_refs"]) != 1:
        die("real gate output-ref count != 1")
    if payload["output_artifact_refs"][0]["artifact_id"] != policy.artifact_id:
        die("real gate output is not exact ClassificationPolicy")
    if payload["decision_record_refs"] != sorted([owner_id, techlead_id]):
        die("real gate decision refs mismatch")
    if any(v is not None for v in payload["trusted_time_inputs"].values()):
        die("real gate unexpectedly captured trusted semantic time")

    manifest_doc = {
        "artifact_id": manifest.artifact_id,
        "artifact_schema_version": manifest.artifact_schema_version,
        "artifact_type": manifest.artifact_type,
        "content_sha256": manifest.content_sha256,
        "semantic_payload": manifest.semantic_payload,
    }
    gate_path = out / "ff2-gate-result-manifest.json"
    gate_file_sha = write_canonical_json(gate_path, manifest_doc, canonical_artifact_json)

    summary = {
        "DECISION_OWNER_ID": owner_id,
        "DECISION_OWNER_FILE_SHA256": owner_file_sha,
        "DECISION_TECHLEAD14_ID": techlead_id,
        "DECISION_TECHLEAD14_FILE_SHA256": techlead_file_sha,
        "F_F2_FAILURE_REASONS": list(execution.failure_reasons),
        "F_F2_GATE_ARTIFACT_ID": manifest.artifact_id,
        "F_F2_GATE_CONTENT_SHA256": manifest.content_sha256,
        "F_F2_GATE_FILE_SHA256": gate_file_sha,
        "F_F2_INPUT_REF_COUNT": len(payload["input_artifact_refs"]),
        "F_F2_OUTPUT_REF_COUNT": len(payload["output_artifact_refs"]),
        "F_F2_STATUS": payload["status"],
        "LAB_HEAD": head,
        "LAB_TREE": tree,
        "POLICY_ARTIFACT_ID": policy.artifact_id,
        "REVIEW_REPORT_SHA256": review_sha,
        "VECTOR_SHA256": vector_sha,
        "WORKTREE_CLEAN_AFTER_GATE": run_git(repo, "status", "--short") == "",
    }
    summary_path = out / "acceptance-summary.json"
    write_canonical_json(summary_path, summary, canonical_artifact_json)

    print("============================================================")
    print("F-F2 REAL ACCEPTANCE GATE")
    print("============================================================")
    for key in sorted(summary):
        print(f"{key}={summary[key]}")
    print(f"OWNER_DECISION_PATH={owner_path}")
    print(f"TECHLEAD14_DECISION_PATH={techlead_path}")
    print(f"REVIEW_REPORT_PATH={review_path}")
    print(f"GATE_MANIFEST_PATH={gate_path}")
    print(f"SUMMARY_PATH={summary_path}")
    print("============================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
