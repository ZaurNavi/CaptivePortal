from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

EXPECTED_PARENT = "5f562c141cdf2d095e1ee67322d1b6f0459a6946"
EXPECTED_BASE_TREE = "8a36835d5a8d046d494e15ddcde40ed419de0413"
EXPECTED_PATCH_SHA256 = "73f9b0a262322edfe520fe7d7a7df90b9d19b7c4cc50f4abb7c17e7eb3a9b000"
EXPECTED_PATCH_BASENAME = "TASK-DEVICE-FINGERPRINT-FF5-RUNTIME-PROFILE-ATOMICITY-01-FIX2.patch"

EXPECTED_PATHS = (
    "app/device_fingerprint/control_plane_store.py",
    "app/device_fingerprint/ff5_runtime_profile_atomicity.py",
    "app/device_fingerprint/gate_proof_artifacts.py",
    "app/device_fingerprint/runtime_profile_artifacts.py",
    "tests/device_fingerprint_ff5/__init__.py",
    "tests/device_fingerprint_ff5/test_runtime_profile_artifacts.py",
    "tests/device_fingerprint_ff5/test_runtime_profile_atomicity.py",
)

MANDATORY_EVIDENCE = (
    ("runtime_profile_switch_pinning_trace", "profile-switch-pinning-trace.json"),
    ("runtime_profile_transaction_crash_point_trace", "transaction-crash-point-trace.json"),
    ("runtime_profile_rollback_trace", "rollback-trace.json"),
    ("runtime_profile_cas_race_trace", "cas-race-trace.json"),
    ("runtime_profile_restart_recovery_trace", "restart-recovery-trace.json"),
    ("runtime_profile_compatibility_test_fixtures", "compatibility-test-fixtures.json"),
)

EXPECTED_CHECKS = {
    "fixture",
    "dependency",
    "crash",
    "pinning",
    "rollback",
    "validity_cas",
    "activation_cas",
    "aba",
    "recovery",
    "transaction_only_record_visibility",
    "inactive_active_pointer_fail_closed",
    "standalone_inactive_transition_forbidden",
    "invalidated_activation_cannot_be_reenabled",
    "inactive_predecessor_activation_fail_closed",
}


class AcceptanceError(RuntimeError):
    pass


def run(repo: Path, *args: str, binary: bool = False):
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise AcceptanceError(
            f"git {' '.join(args)} failed: "
            f"{proc.stderr.decode('utf-8', errors='replace').strip()}"
        )
    if binary:
        return proc.stdout
    return proc.stdout.decode("utf-8").strip()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def write_json(path: Path, value: Any) -> str:
    data = canonical_json_bytes(value) + b"\n"
    path.write_bytes(data)
    return sha256_bytes(data)


def artifact_envelope(content) -> dict[str, Any]:
    return {
        "artifact_type": content.artifact_type,
        "artifact_schema_version": content.artifact_schema_version,
        "semantic_payload": content.semantic_payload,
        "content_sha256": content.content_sha256,
        "artifact_id": content.artifact_id,
    }


def extract_new_file_from_patch(patch_text: str, target: str) -> bytes:
    marker = f"diff --git a/{target} b/{target}"
    try:
        start = patch_text.index(marker)
    except ValueError as exc:
        raise AcceptanceError(f"reviewed patch missing expected path: {target}") from exc
    next_pos = patch_text.find("\ndiff --git ", start + len(marker))
    block = patch_text[start:] if next_pos < 0 else patch_text[start:next_pos]
    lines: list[str] = []
    saw_new_file = False
    for line in block.splitlines():
        if line.startswith("new file mode "):
            saw_new_file = True
            continue
        if line.startswith(("diff --git ", "index ", "--- ", "+++ ", "@@")):
            continue
        if line.startswith("+"):
            lines.append(line[1:])
        elif line.startswith("\\ No newline"):
            continue
        elif line.startswith("-") or line.startswith(" "):
            raise AcceptanceError(f"{target} is not a pure new-file patch")
    if not saw_new_file:
        raise AcceptanceError(f"{target} is not marked as a new file")
    return ("\n".join(lines) + "\n").encode("utf-8")


def verify_candidate(repo: Path, patch_path: Path) -> tuple[str, str]:
    if sha256_bytes(patch_path.read_bytes()) != EXPECTED_PATCH_SHA256:
        raise AcceptanceError("reviewed patch SHA256 mismatch")

    head = run(repo, "rev-parse", "HEAD")
    parent_line = run(repo, "rev-list", "--parents", "-n", "1", "HEAD").split()
    if len(parent_line) != 2 or parent_line[0] != head or parent_line[1] != EXPECTED_PARENT:
        raise AcceptanceError("candidate parent mismatch or merge commit")

    tree = run(repo, "rev-parse", "HEAD^{tree}")
    branch = run(repo, "branch", "--show-current")
    if branch:
        raise AcceptanceError(f"candidate is not detached: {branch}")

    if run(repo, "status", "--porcelain"):
        raise AcceptanceError("candidate worktree is not clean")

    changed = tuple(
        line for line in run(repo, "diff", "--name-only", f"{EXPECTED_PARENT}..HEAD").splitlines()
        if line
    )
    if set(changed) != set(EXPECTED_PATHS) or len(changed) != len(EXPECTED_PATHS):
        raise AcceptanceError(f"candidate changed paths mismatch: {changed!r}")

    statuses = tuple(
        line for line in run(repo, "diff", "--name-status", f"{EXPECTED_PARENT}..HEAD").splitlines()
        if line
    )
    expected_statuses = {f"A\t{path}" for path in EXPECTED_PATHS}
    if set(statuses) != expected_statuses or len(statuses) != len(EXPECTED_PATHS):
        raise AcceptanceError(f"candidate path statuses mismatch: {statuses!r}")

    patch_text = patch_path.read_text(encoding="utf-8")
    patch_paths = tuple(
        re.findall(r"^diff --git a/(.+?) b/(.+?)$", patch_text, flags=re.MULTILINE)
    )
    normalized_patch_paths = tuple(a for a, b in patch_paths if a == b)
    if set(normalized_patch_paths) != set(EXPECTED_PATHS) or len(normalized_patch_paths) != len(EXPECTED_PATHS):
        raise AcceptanceError("reviewed patch path set mismatch")

    for path in EXPECTED_PATHS:
        expected_blob = extract_new_file_from_patch(patch_text, path)
        actual_blob = run(repo, "show", f"HEAD:{path}", binary=True)
        if actual_blob != expected_blob:
            raise AcceptanceError(f"candidate blob differs from reviewed patch: {path}")

    return head, tree


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(
            "usage: ff5_real_acceptance_gate.py <repo_path> [patch_path]",
            file=sys.stderr,
        )
        return 2

    repo = Path(sys.argv[1]).resolve()
    patch_path = (
        Path(sys.argv[2]).resolve()
        if len(sys.argv) == 3
        else Path(r"C:\CaptivPortal-Lab\artifacts") / EXPECTED_PATCH_BASENAME
    )

    try:
        head, tree = verify_candidate(repo, patch_path)

        sys.path.insert(0, str(repo))
        from app.device_fingerprint.artifact_content import ArtifactRef
        from app.device_fingerprint.ff5_runtime_profile_atomicity import (
            execute_ff5_runtime_profile_atomicity_scenarios,
            run_ff5_runtime_profile_atomicity_gate,
        )

        out_dir = Path(r"C:\CaptivPortal-Lab\artifacts") / f"ff5-real-acceptance-{head[:8]}"
        if out_dir.exists():
            raise AcceptanceError(f"refusing to overwrite existing evidence directory: {out_dir}")
        out_dir.mkdir(parents=True, exist_ok=False)

        scenario_work = out_dir / "scenario-work"
        execution = execute_ff5_runtime_profile_atomicity_scenarios(
            working_directory=scenario_work,
            candidate_repository_commit_sha=head,
            candidate_repository_tree_sha=tree,
        )

        if set(execution.checks) != EXPECTED_CHECKS:
            raise AcceptanceError(
                f"unexpected F-F5 check set: {sorted(execution.checks)}"
            )
        if not all(type(value) is bool and value for value in execution.checks.values()):
            raise AcceptanceError(f"F-F5 scenario checks not all PASS: {execution.checks!r}")
        if execution.failure_reasons:
            raise AcceptanceError(
                f"F-F5 scenario failure reasons present: {execution.failure_reasons!r}"
            )
        if len(execution.fixture_artifact_refs) != 8:
            raise AcceptanceError(
                f"unexpected fixture input ref count: {len(execution.fixture_artifact_refs)}"
            )

        if execution.transaction_crash_point_trace.get(
            "transaction_only_record_visibility"
        ) is not True:
            raise AcceptanceError("transaction-only visibility proof missing")
        if execution.restart_recovery_trace.get(
            "inactive_active_pointer_fail_closed"
        ) is not True:
            raise AcceptanceError("inactive active-pointer fail-closed proof missing")
        if execution.restart_recovery_trace.get(
            "inactive_predecessor_activation_fail_closed"
        ) is not True:
            raise AcceptanceError("inactive predecessor activation fail-closed proof missing")
        if execution.profile_switch_pinning_trace.get(
            "standalone_inactive_transition_forbidden"
        ) is not True:
            raise AcceptanceError("standalone INACTIVE rejection proof missing")
        if execution.profile_switch_pinning_trace.get(
            "invalidated_activation_cannot_be_reenabled"
        ) is not True:
            raise AcceptanceError("invalidated activation re-enable rejection proof missing")

        evidence_payloads = {
            "runtime_profile_switch_pinning_trace": execution.profile_switch_pinning_trace,
            "runtime_profile_transaction_crash_point_trace": execution.transaction_crash_point_trace,
            "runtime_profile_rollback_trace": execution.rollback_trace,
            "runtime_profile_cas_race_trace": execution.cas_race_trace,
            "runtime_profile_restart_recovery_trace": execution.restart_recovery_trace,
            "runtime_profile_compatibility_test_fixtures": execution.compatibility_test_fixtures,
        }

        evidence_refs: list[dict[str, Any]] = []
        evidence_shas: dict[str, str] = {}
        for label, filename in MANDATORY_EVIDENCE:
            path = out_dir / filename
            payload = {
                "gate_id": "F-F5",
                "gate_contract_version": "R14-F-F5-v1",
                "candidate_repository_commit_sha": head,
                "candidate_repository_tree_sha": tree,
                "reviewed_patch_sha256": EXPECTED_PATCH_SHA256,
                "evidence_label": label,
                "content": evidence_payloads[label],
            }
            digest = write_json(path, payload)
            evidence_shas[label] = digest
            evidence_refs.append(
                {
                    "evidence_label": label,
                    "file_sha256": digest,
                    "media_type": "application/json",
                    "path_or_reference": str(path),
                }
            )

        gate = run_ff5_runtime_profile_atomicity_gate(
            execution,
            candidate_repository_commit_sha=head,
            candidate_repository_tree_sha=tree,
            environment_identity="windows-central-lab-ff5-real-admission",
            retained_evidence_refs=evidence_refs,
        )

        manifest = gate.gate_result_manifest
        proof = gate.gate_proof_artifact
        mp = manifest.semantic_payload
        pp = proof.semantic_payload

        if gate.failure_reasons:
            raise AcceptanceError(
                f"real F-F5 gate returned failure reasons: {gate.failure_reasons!r}"
            )
        if mp["status"] != "PASS":
            raise AcceptanceError(f"real F-F5 gate status is {mp['status']!r}")
        if mp["gate_id"] != "F-F5" or mp["gate_contract_version"] != "R14-F-F5-v1":
            raise AcceptanceError("F-F5 gate identity mismatch")
        if (
            mp["candidate_repository_commit_sha"] != head
            or mp["candidate_repository_tree_sha"] != tree
        ):
            raise AcceptanceError("F-F5 gate candidate binding mismatch")
        if len(mp["input_artifact_refs"]) != 8:
            raise AcceptanceError("F-F5 gate input ref count mismatch")
        if len(mp["output_artifact_refs"]) != 1:
            raise AcceptanceError("F-F5 gate output ref count mismatch")

        expected_proof_ref = ArtifactRef(
            proof.artifact_id, proof.content_sha256
        ).as_dict()
        if mp["output_artifact_refs"] != [expected_proof_ref]:
            raise AcceptanceError("F-F5 gate output is not exact proof artifact")
        if mp["decision_record_refs"] != []:
            raise AcceptanceError("F-F5 must have no Owner DecisionRecord refs")
        if any(value is not None for value in mp["trusted_time_inputs"].values()):
            raise AcceptanceError("F-F5 trusted semantic times must all be null")

        if pp["proof_kind"] != "RUNTIME_PROFILE_ATOMICITY":
            raise AcceptanceError("F-F5 proof kind mismatch")
        if pp["source_gate_id"] != "F-F5":
            raise AcceptanceError("F-F5 proof source gate mismatch")
        if pp["procedure_or_test_suite_id"] != "F-F5-runtime-profile-atomicity-v1":
            raise AcceptanceError("F-F5 proof procedure mismatch")
        if (
            pp["candidate_repository_commit_sha"] != head
            or pp["candidate_repository_tree_sha"] != tree
        ):
            raise AcceptanceError("F-F5 proof candidate binding mismatch")

        manifest_labels = [
            row["evidence_label"] for row in mp["retained_evidence_refs"]
        ]
        if sorted(manifest_labels) != sorted(label for label, _ in MANDATORY_EVIDENCE):
            raise AcceptanceError("F-F5 retained evidence labels mismatch")

        proof_path = out_dir / "ff5-gate-proof-artifact.json"
        manifest_path = out_dir / "ff5-gate-result-manifest.json"
        proof_file_sha = write_json(proof_path, artifact_envelope(proof))
        manifest_file_sha = write_json(manifest_path, artifact_envelope(manifest))

        summary = {
            "status": "PASS",
            "candidate_repository_commit_sha": head,
            "candidate_repository_tree_sha": tree,
            "candidate_parent_sha": EXPECTED_PARENT,
            "reviewed_patch_sha256": EXPECTED_PATCH_SHA256,
            "fixture_input_ref_count": len(execution.fixture_artifact_refs),
            "gate_input_ref_count": len(mp["input_artifact_refs"]),
            "gate_output_ref_count": len(mp["output_artifact_refs"]),
            "decision_ref_count": len(mp["decision_record_refs"]),
            "gate_proof_artifact_id": proof.artifact_id,
            "gate_proof_content_sha256": proof.content_sha256,
            "gate_proof_file_sha256": proof_file_sha,
            "gate_result_manifest_artifact_id": manifest.artifact_id,
            "gate_result_manifest_content_sha256": manifest.content_sha256,
            "gate_result_manifest_file_sha256": manifest_file_sha,
            "checks": execution.checks,
            "failure_reasons": list(gate.failure_reasons),
            "retained_evidence_file_sha256": evidence_shas,
        }
        summary_path = out_dir / "acceptance-summary.json"
        summary_sha = write_json(summary_path, summary)

        if run(repo, "status", "--porcelain"):
            raise AcceptanceError("candidate worktree changed during F-F5 gate")

        print("=" * 68)
        print("F-F5 REAL ACCEPTANCE GATE")
        print("=" * 68)
        print("F_F5_STATUS=PASS")
        print("F_F5_FAILURE_REASONS=[]")
        print(f"LAB_HEAD={head}")
        print(f"LAB_PARENT={EXPECTED_PARENT}")
        print(f"LAB_TREE={tree}")
        print(f"PATCH_SHA256={EXPECTED_PATCH_SHA256}")
        print(f"F_F5_CHECK_COUNT={len(execution.checks)}")
        print(f"F_F5_ALL_CHECKS_PASS={all(execution.checks.values())}")
        print(f"F_F5_INPUT_REF_COUNT={len(mp['input_artifact_refs'])}")
        print(f"F_F5_OUTPUT_REF_COUNT={len(mp['output_artifact_refs'])}")
        print(f"F_F5_DECISION_REF_COUNT={len(mp['decision_record_refs'])}")
        print(f"F_F5_PROOF_ARTIFACT_ID={proof.artifact_id}")
        print(f"F_F5_PROOF_CONTENT_SHA256={proof.content_sha256}")
        print(f"F_F5_PROOF_FILE_SHA256={proof_file_sha}")
        print(f"F_F5_GATE_ARTIFACT_ID={manifest.artifact_id}")
        print(f"F_F5_GATE_CONTENT_SHA256={manifest.content_sha256}")
        print(f"F_F5_GATE_FILE_SHA256={manifest_file_sha}")
        for label, _ in MANDATORY_EVIDENCE:
            key = label.upper()
            print(f"{key}_SHA256={evidence_shas[label]}")
        print(f"SUMMARY_SHA256={summary_sha}")
        print("WORKTREE_CLEAN_AFTER_GATE=True")
        print(f"EVIDENCE_DIR={out_dir}")
        print(f"PROOF_PATH={proof_path}")
        print(f"GATE_MANIFEST_PATH={manifest_path}")
        print(f"SUMMARY_PATH={summary_path}")
        print("=" * 68)
        return 0

    except Exception as exc:
        print("=" * 68)
        print("F-F5 REAL ACCEPTANCE GATE")
        print("=" * 68)
        print("F_F5_STATUS=FAIL")
        print(f"ERROR={type(exc).__name__}: {exc}")
        print("=" * 68)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
