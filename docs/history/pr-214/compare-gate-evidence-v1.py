"""Fail-closed full-ledger comparison, not a baseline FAIL allowlist."""
import argparse
import json
from pathlib import Path

from pytest_platform_contract import ContractError, GATE, digest, exact, strict_json, validate_manifest, validate_outcomes, manifest_digest


def validate_ledger(ledger, manifest):
    exact(ledger, {"schema_version", "gate_identity", "context", "collected", "outcomes", "deselected", "collection_errors", "pytest_exit_code", "contract_failures", "status"})
    if ledger["schema_version"] != 1 or ledger["gate_identity"] != GATE:
        raise ContractError("ledger_identity")
    context = ledger["context"]
    exact(context, {"schema_version", "gate_identity", "platform", "repo", "head", "tree", "manifest_sha256", "plugin_sha256", "environment", "source_inventory", "expected_collection", "launcher_sha256"})
    if context["gate_identity"] != GATE or context["schema_version"] != 1 or ledger["collected"] != context["expected_collection"]:
        raise ContractError("collection_drift")
    reasons = validate_outcomes(manifest, context["platform"], ledger["collected"], ledger["outcomes"], ledger["deselected"], ledger["collection_errors"])
    if ledger["pytest_exit_code"]:
        reasons.append("pytest_exit_nonzero:" + str(ledger["pytest_exit_code"]))
    if ledger["contract_failures"] != sorted(set(reasons)) or ledger["status"] != ("FAIL" if reasons else "PASS"):
        raise ContractError("claimed_status_contradiction")
    return reasons


def compare_pair(baseline, candidate, manifest, *, approved_added_ids=()):
    validate_manifest(manifest)
    base_reasons = validate_ledger(baseline, manifest)
    candidate_reasons = validate_ledger(candidate, manifest)
    a, b = baseline["context"], candidate["context"]
    environment_keys = ("python", "sqlite", "sqlite_compile_options", "interpreter_sha256", "packages")
    if a["platform"] != b["platform"] or any(a["environment"].get(k) != b["environment"].get(k) for k in environment_keys):
        raise ContractError("paired_environment_drift")
    if any(a[k] != b[k] for k in ("manifest_sha256", "plugin_sha256", "launcher_sha256")):
        raise ContractError("paired_infrastructure_drift")
    base_ids, candidate_ids = set(baseline["collected"]), set(candidate["collected"])
    # New legitimate candidate tests need a separately reviewed inventory delta.
    # Phase 1 chooses conservative HOLD rather than silently omitting them.
    if base_ids - candidate_ids or candidate_ids - base_ids != set(approved_added_ids):
        raise ContractError("paired_collection_delta_requires_disposition")
    new_failures = sorted(k for k in candidate_ids if candidate["outcomes"][k]["status"] != baseline["outcomes"].get(k, {}).get("status")
                          and candidate["outcomes"][k]["status"] in {"FAIL", "ERROR", "SKIP", "XFAIL", "XPASS", "INCOMPLETE"})
    return {"differential_no_new_failures": not new_failures, "new_failures": new_failures,
            "explicitly_approved_added_ids": sorted(approved_added_ids),
            "baseline_strict": "FAIL" if base_reasons else "PASS", "candidate_strict": "FAIL" if candidate_reasons else "PASS"}


def validate_context_lock(ledger, lock, manifest_sha):
    exact(lock, {"schema_version", "gate_identity", "status", "approval", "profiles", "infrastructure_sha256", "approved_artifacts", "collection_inventories"})
    if lock["schema_version"] != 1 or lock["gate_identity"] != GATE or lock["status"] != "APPROVED":
        raise ContractError("draft_environment_not_admitted")
    exact(lock["approval"], {"authority", "reference", "body_sha256"})
    if (lock["approval"]["authority"] != "TECH_LEAD_21" or not lock["approval"]["reference"]
            or lock["approval"]["body_sha256"] != manifest_digest(lock)):
        raise ContractError("environment_approval_binding")
    context = ledger["context"]
    artifact = {"head": context["head"], "tree": context["tree"]}
    if artifact not in lock["approved_artifacts"]:
        raise ContractError("unapproved_artifact")
    if context["expected_collection"] != lock["collection_inventories"].get(context["tree"]):
        raise ContractError("unapproved_collection_inventory")
    hashes = lock["infrastructure_sha256"]
    launcher = "run-platform-gates-v1.cmd" if context["platform"] == "windows" else "run-linux-platform-gates-v1.sh"
    if (context["manifest_sha256"] != manifest_sha or manifest_sha != hashes.get("platform-manifest-v1.json")
            or context["plugin_sha256"] != hashes.get("pytest_platform_contract.py")
            or context["launcher_sha256"] != hashes.get(launcher)):
        raise ContractError("unapproved_infrastructure")
    profile = lock["profiles"][context["platform"]]
    for key in ("python", "sqlite", "sqlite_compile_options", "interpreter", "interpreter_sha256", "packages"):
        if context["environment"].get(key) != profile.get(key):
            raise ContractError("unapproved_environment:" + key)


def composite(windows, linux, manifest):
    a = validate_ledger(windows, manifest)
    b = validate_ledger(linux, manifest)
    if windows["context"]["platform"] != "windows" or linux["context"]["platform"] != "linux":
        raise ContractError("composite_platform")
    for key in ("head", "tree", "manifest_sha256", "plugin_sha256"):
        if windows["context"][key] != linux["context"][key]:
            raise ContractError("cross_platform_artifact_drift")
    if set(windows["collected"]) != set(linux["collected"]):
        raise ContractError("cross_platform_collection_drift")
    missing = [r["node_id"] for r in manifest["transfers"] if linux["outcomes"].get(r["linux_node_id"], {}).get("status") != "PASS"]
    return {"gate_identity": GATE, "status": "PASS" if not a and not b and not missing else "FAIL",
            "windows_failures": a, "linux_failures": b, "linux_missing_pass": missing}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--environment-lock", required=True)
    parser.add_argument("--environment-lock-sha256", required=True)
    parser.add_argument("--baseline-windows", required=True)
    parser.add_argument("--candidate-windows", required=True)
    parser.add_argument("--baseline-linux", required=True)
    parser.add_argument("--candidate-linux", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    manifest = validate_manifest(strict_json(args.manifest), require_approved=True)
    if digest(args.environment_lock) != args.environment_lock_sha256:
        raise ContractError("environment_lock_hash")
    lock = strict_json(args.environment_lock)
    inputs = {key: strict_json(getattr(args, key)) for key in ("baseline_windows", "candidate_windows", "baseline_linux", "candidate_linux")}
    for ledger in inputs.values():
        validate_context_lock(ledger, lock, digest(args.manifest))
        if ledger["context"]["manifest_sha256"] != digest(args.manifest):
            raise ContractError("ledger_manifest_binding")
    def approved_additions(lane):
        # Both exact inventories must first be admitted in the reviewed environment lock.
        return set(inputs["candidate_" + lane]["context"]["expected_collection"]) - set(inputs["baseline_" + lane]["context"]["expected_collection"])
    result = {"gate_identity": GATE, "historical_v7_pass_claim": False,
              "windows_differential": compare_pair(inputs["baseline_windows"], inputs["candidate_windows"], manifest, approved_added_ids=approved_additions("windows")),
              "linux_differential": compare_pair(inputs["baseline_linux"], inputs["candidate_linux"], manifest, approved_added_ids=approved_additions("linux")),
              "baseline": composite(inputs["baseline_windows"], inputs["baseline_linux"], manifest),
              "candidate": composite(inputs["candidate_windows"], inputs["candidate_linux"], manifest),
              "input_sha256": {key: digest(getattr(args, key)) for key in inputs},
              "approved_environment_lock_sha256": digest(args.environment_lock)}
    result["status"] = "PASS" if result["baseline"]["status"] == result["candidate"]["status"] == "PASS" else "BASELINE_OR_CANDIDATE_BLOCKED"
    with Path(args.output).open("x", encoding="utf-8") as output:
        json.dump(result, output, sort_keys=True, indent=2)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as error:
        print("BLOCKED=" + str(error))
        raise SystemExit(2)
