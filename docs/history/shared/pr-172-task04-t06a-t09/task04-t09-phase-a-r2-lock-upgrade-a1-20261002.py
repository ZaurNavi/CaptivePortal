#!/usr/bin/env python3
"""T-09 A1 Phase-A audit-contract upgrade.

Consumes the already-frozen pre-result R1 Phase-A lock and emits a new
R2-compatible Phase-A lock without invoking RequestAssembly, fusion,
persistence, classification, or result APIs.

The exact ControlledValidationGroundTruthRecord bytes and validation_run_id
are preserved.  Only the per-artifact §10.2 pre-result registration envelopes
required by the historical R2 verifier are added.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
import uuid

LAB_ROOT = Path(r"C:\CaptivPortal-Lab")

COMMIT = "8a39459be3ce7ed40e325736034245f0025cf249"
TREE = "e2521f27c9f91978e381bce202ab3e3c83aa6dad"

SOURCE_PHASE_A_RUNNER = LAB_ROOT / "tools" / "task04-t09-phase-a-a1-20261002.py"
SOURCE_PHASE_A_RUNNER_SHA = "197b134fcc19ceead1d83e5e1598391168a4f5d4783a34331f6470f700c3df9a"

SOURCE_PHASE_A_LOCK_SHA = "6bbd4d03fe694c8a4a2cf9caef8ab79c8659bab42105a1e8a8e86df3298ac4a7"

T07_PATH = LAB_ROOT / "tools" / "task04-t07-gate-a1-20261002.py"
T07_SHA = "bbe90933dd4526f4b0cb3c1db65ada38161de0147c476a5be2105bcb7cecf9ac"

PROFILE_ID = "ClassificationRuntimeProfile:v1:sha256:1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c"
POLICY_ID = "ProductValidationPolicy:v1:sha256:806779ca1844e55083a2c1c464cf8d94a9bdd0b2f97436d203b63fd03e81bea5"

REGISTRATION_ROLE = "EXTERNAL_LAB_TOOL"

FORBIDDEN_RESULT_NAMES = {
    "phase-b-lock.json",
    "privacy-safe-comparison-report.json",
    "compatibility-report.json",
    "worker-completion.json",
}
FORBIDDEN_RESULT_PREFIXES = ("request-", "result-", "comparison-")


class RepairBlocked(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise RepairBlocked(code)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_source_runner():
    require(SOURCE_PHASE_A_RUNNER.is_file(), "SOURCE_PHASE_A_RUNNER_MISSING")
    require(sha(SOURCE_PHASE_A_RUNNER) == SOURCE_PHASE_A_RUNNER_SHA,
            "SOURCE_PHASE_A_RUNNER_IDENTITY_CHANGED")
    spec = importlib.util.spec_from_file_location("t09_a1_source_phase_a", SOURCE_PHASE_A_RUNNER)
    require(spec is not None and spec.loader is not None, "SOURCE_PHASE_A_IMPORT_SPEC")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    require(module.COMMIT == COMMIT and module.TREE == TREE
            and module.PROFILE_ID == PROFILE_ID and module.POLICY_ID == POLICY_ID,
            "SOURCE_PHASE_A_CANDIDATE_MISMATCH")
    return module


def verify_no_result_visibility(blocked_root: Path) -> list[str]:
    blocked_root = blocked_root.resolve(strict=True)
    require(blocked_root.is_dir(), "BLOCKED_PHASE_B_ROOT_NOT_DIRECTORY")

    observed: list[str] = []
    forbidden: list[str] = []
    for path in sorted(blocked_root.rglob("*")):
        rel = path.relative_to(blocked_root).as_posix()
        observed.append(rel)
        if path.is_dir() and path.name.startswith("worker-"):
            forbidden.append(rel)
        if path.is_file():
            if path.name in FORBIDDEN_RESULT_NAMES or path.name.startswith(FORBIDDEN_RESULT_PREFIXES):
                forbidden.append(rel)
            if path.name.startswith("classification") and path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
                forbidden.append(rel)
    require(not forbidden, "RESULT_VISIBILITY_ALREADY_OCCURRED:" + ",".join(forbidden))
    return observed


def exclusive_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    require(not target.exists(), "REPAIR_TARGET_MEMBER_ALREADY_EXISTS")
    with source.open("rb") as src, target.open("xb") as dst:
        shutil.copyfileobj(src, dst)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--source-phase-a-lock", type=Path, required=True)
    parser.add_argument("--source-phase-a-lock-sha256", required=True)
    parser.add_argument("--blocked-phase-b-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        require(args.source_phase_a_lock_sha256 == SOURCE_PHASE_A_LOCK_SHA,
                "SOURCE_PHASE_A_LOCK_SHA_ARGUMENT_MISMATCH")

        repo = args.repo.resolve(strict=True)
        output = args.output.resolve()
        source_lock_path = args.source_phase_a_lock.resolve(strict=True)
        blocked_root = args.blocked_phase_b_output.resolve(strict=True)

        require(repo.is_dir(), "REPO_NOT_DIRECTORY")
        require(output.is_relative_to(LAB_ROOT.resolve()) and output != LAB_ROOT.resolve(),
                "OUTPUT_OUTSIDE_LAB")
        require(not output.exists(), "OUTPUT_ALREADY_EXISTS")
        require(not output.is_relative_to(repo) and not repo.is_relative_to(output),
                "OUTPUT_REPO_OVERLAP")
        require(not output.is_relative_to(source_lock_path.parent)
                and not source_lock_path.parent.is_relative_to(output),
                "OUTPUT_SOURCE_PHASE_A_OVERLAP")
        require(not output.is_relative_to(blocked_root)
                and not blocked_root.is_relative_to(output),
                "OUTPUT_BLOCKED_RUN_OVERLAP")

        r1 = load_source_runner()
        h, t01, _t06a = r1.helpers()
        require(sha(T07_PATH) == T07_SHA, "T07_HELPER_CHANGED")

        t01.verify_repository(repo)
        fingerprint = t01.repository_filesystem_fingerprint(repo)

        # Minimal API only: artifact/foundation/profile/schema/gate/policy validation.
        # No request assembly, fusion, persistence, or result module is loaded.
        api = r1.minimal_api(repo, h)

        require(sha(source_lock_path) == SOURCE_PHASE_A_LOCK_SHA,
                "SOURCE_PHASE_A_LOCK_IDENTITY_CHANGED")
        source_lock = r1.verify_lock(
            api, source_lock_path, SOURCE_PHASE_A_LOCK_SHA, "A"
        )

        # Reconstruct the exact source Phase-A context from immutable retained files.
        source_dir = source_lock_path.parent
        profile = r1.load_content(api, source_dir / "exact-profile.json")
        foundation = r1.load_content(api, source_dir / "exact-foundation.json")
        policy = r1.load_content(api, source_dir / "exact-product-policy.json")

        require(profile.artifact_id == PROFILE_ID, "SOURCE_PROFILE_MISMATCH")
        require(policy.artifact_id == POLICY_ID, "SOURCE_POLICY_MISMATCH")
        require(source_lock["profile"] == r1.ref(profile), "SOURCE_LOCK_PROFILE_REF_MISMATCH")
        require(source_lock["foundation"] == r1.ref(foundation), "SOURCE_LOCK_FOUNDATION_REF_MISMATCH")
        require(source_lock["product_validation_policy"] == r1.ref(policy),
                "SOURCE_LOCK_POLICY_REF_MISMATCH")

        source_ctx = SimpleNamespace(
            api=api,
            profile=profile,
            foundation=foundation,
            policy=policy,
            valid_from=source_lock["classification_foundation_valid_from_utc"],
        )
        checked_lock, truths = r1.checked_phase_a(
            source_ctx,
            SimpleNamespace(
                phase_a_lock=source_lock_path,
                phase_a_lock_sha256=SOURCE_PHASE_A_LOCK_SHA,
            ),
        )
        require(checked_lock == source_lock and len(truths) == 2,
                "SOURCE_PHASE_A_REVALIDATION_FAILED")

        blocked_inventory = verify_no_result_visibility(blocked_root)

        output.mkdir(parents=True, exist_ok=False)

        # Preserve every retained R1 member byte-for-byte.
        for relative_name, identity in sorted(source_lock["retained_files"].items()):
            source = source_dir / relative_name
            require(source.resolve(strict=True).is_relative_to(source_dir.resolve()),
                    "SOURCE_MEMBER_ESCAPE")
            require(source.is_file() and not source.is_symlink(), "SOURCE_MEMBER_INVALID")
            require(source.stat().st_size == identity["bytes"] and sha(source) == identity["sha256"],
                    "SOURCE_MEMBER_IDENTITY_CHANGED")
            target = output / relative_name
            exclusive_copy(source, target)
            require(target.stat().st_size == identity["bytes"] and sha(target) == identity["sha256"],
                    "COPIED_SOURCE_MEMBER_IDENTITY_MISMATCH")

        # Preserve the original lock itself as explicit parent provenance.
        parent_lock_copy = output / "source-phase-a-r1-lock.json"
        exclusive_copy(source_lock_path, parent_lock_copy)
        require(sha(parent_lock_copy) == SOURCE_PHASE_A_LOCK_SHA,
                "SOURCE_LOCK_COPY_MISMATCH")

        # Add the R2 per-artifact pre-result audit registrations.
        registrations = []
        for index, gt in enumerate(truths, 1):
            registered_at = r1.now()
            registration = {
                "registration_schema_version": 1,
                "registration_id": str(uuid.uuid4()),
                "artifact_id": gt.artifact_id,
                "registered_at_utc": registered_at,
                "registered_by_role": REGISTRATION_ROLE,
                "repository_commit_sha": COMMIT,
                "repository_tree_sha": TREE,
                "decision_record_refs": [],
                "notes_reference_metadata": {
                    "registration_context": "T09_PHASE_A_PRE_RESULT",
                    "validation_run_id": source_lock["validation_run_id"],
                },
            }
            # Validate with the exact historical R2 audit contract semantics.
            # Source R1 does not define artifact_registration, so reproduce only
            # the closed audit checks here using its validation API.
            require(set(registration) == {
                "registration_schema_version", "registration_id", "artifact_id",
                "registered_at_utc", "registered_by_role", "repository_commit_sha",
                "repository_tree_sha", "decision_record_refs", "notes_reference_metadata",
            }, "REGISTRATION_CLOSED_SCHEMA")
            r1.uuid4(registration["registration_id"])
            require(registration["artifact_id"] == gt.artifact_id,
                    "REGISTRATION_GT_BINDING")
            require(
                api.validation.parse_utc(gt.semantic_payload["recorded_at_utc"])
                <= api.validation.parse_utc(registered_at),
                "REGISTRATION_BEFORE_GT_RECORDING",
            )

            registration_path = output / f"ground-truth-registration-{index}.json"
            r1.write(api, registration_path, registration)
            roundtrip = r1.read(api, registration_path)
            require(roundtrip == registration, "REGISTRATION_ROUNDTRIP")

            registrations.append({
                "registration_id": registration["registration_id"],
                "artifact_id": gt.artifact_id,
                "file": registration_path.name,
                "file_sha256": sha(registration_path),
            })

        lock_created = r1.now()
        for index, gt in enumerate(truths, 1):
            reg = r1.read(api, output / f"ground-truth-registration-{index}.json")
            require(
                api.validation.parse_utc(gt.semantic_payload["recorded_at_utc"])
                <= api.validation.parse_utc(reg["registered_at_utc"])
                <= api.validation.parse_utc(lock_created),
                "REGISTRATION_NOT_PRE_RESULT",
            )

        # Re-verify exact GT bytes are preserved.
        for index, gt in enumerate(truths, 1):
            source_gt = source_dir / f"ground-truth-{index}.json"
            target_gt = output / f"ground-truth-{index}.json"
            require(sha(source_gt) == sha(target_gt), "GROUND_TRUTH_BYTES_CHANGED")
            copied_gt = r1.load_content(
                api, target_gt, lambda payload: r1.ground_truth(api, payload)
            )
            require(copied_gt == gt, "GROUND_TRUTH_CONTENT_CHANGED")

        runner_sha = sha(Path(__file__).resolve())
        retained_files = sorted(
            path for path in output.rglob("*")
            if path.is_file() and path.name != "phase-a-lock.json"
        )
        inventory = {
            path.relative_to(output).as_posix(): {
                "sha256": sha(path),
                "bytes": path.stat().st_size,
            }
            for path in retained_files
        }

        new_lock = {
            "phase": "A",
            "validation_run_id": source_lock["validation_run_id"],
            "execution_id": source_lock["execution_id"],
            "executed_at_utc": source_lock["executed_at_utc"],
            "lock_created_at_utc": lock_created,
            "candidate_commit": COMMIT,
            "candidate_tree": TREE,
            "runner_sha256": runner_sha,
            "helper_sha256": T07_SHA,
            "profile": source_lock["profile"],
            "foundation": source_lock["foundation"],
            "product_validation_policy": source_lock["product_validation_policy"],
            "classification_foundation_valid_from_utc":
                source_lock["classification_foundation_valid_from_utc"],
            "ground_truth_refs": source_lock["ground_truth_refs"],
            "ground_truth_registrations": registrations,
            "device_bindings": source_lock["device_bindings"],
            "foundation_source_identity": source_lock["foundation_source_identity"],
            "source_phase_a_lock_sha256": SOURCE_PHASE_A_LOCK_SHA,
            "source_phase_a_runner_sha256": SOURCE_PHASE_A_RUNNER_SHA,
            "repair_reason": "ADD_R2_PER_ARTIFACT_PRE_RESULT_REGISTRATION_CONTRACT",
            "blocked_phase_b_pre_result_verified": True,
            "blocked_phase_b_observed_path_count": len(blocked_inventory),
            "retained_files": inventory,
        }

        lock_path = output / "phase-a-lock.json"
        r1.write(api, lock_path, new_lock)
        new_lock_sha = sha(lock_path)

        # Final integrity checks. No candidate or source evidence may change.
        t01.verify_repository(repo)
        t01._require_repository_unchanged(repo, fingerprint)
        require(sha(SOURCE_PHASE_A_RUNNER) == SOURCE_PHASE_A_RUNNER_SHA,
                "SOURCE_PHASE_A_RUNNER_CHANGED_DURING_REPAIR")
        require(sha(source_lock_path) == SOURCE_PHASE_A_LOCK_SHA,
                "SOURCE_PHASE_A_LOCK_CHANGED_DURING_REPAIR")
        require(sha(T07_PATH) == T07_SHA, "T07_CHANGED_DURING_REPAIR")
        verify_no_result_visibility(blocked_root)

        print("PHASE_A_REPAIR_STATUS=GROUND_TRUTH_LOCK_UPGRADED_PRE_RESULT")
        print("SOURCE_PHASE_A_LOCK_SHA256=" + SOURCE_PHASE_A_LOCK_SHA)
        print("GROUND_TRUTH_BYTES_PRESERVED=YES")
        print("GROUND_TRUTH_CONTENT_PRESERVED=YES")
        print("VALIDATION_RUN_ID_PRESERVED=" + source_lock["validation_run_id"])
        print("PER_ARTIFACT_REGISTRATION_COUNT=2")
        print("BLOCKED_PHASE_B_RESULT_VISIBILITY=NO")
        print("REPAIRED_PHASE_A_LOCK_PATH=" + str(lock_path))
        print("REPAIRED_PHASE_A_LOCK_SHA256=" + new_lock_sha)
        print("REPAIR_RUNNER_SHA256=" + runner_sha)
        print("PRODUCTION_ACTION=NO")
        print("NEXT=REBUILD_PHASE_B_AGAINST_REPAIRED_LOCK")
        return 0

    except Exception as exc:
        print("PHASE_A_REPAIR_STATUS=BLOCKED")
        print("BLOCKER=" + (str(exc) if str(exc) else type(exc).__name__))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
