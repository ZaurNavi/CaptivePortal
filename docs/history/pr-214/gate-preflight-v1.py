"""Preparation and Owner-only launcher. No implicit gate or installation.

SQLite diagnostic invokes EXPLAIN on disposable fixture DBs, never test cases.
Official execution is blocked until BOTH external locks are separately approved.
"""
import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
from pytest_platform_contract import ContractError, GATE, digest, exact, strict_json, validate_manifest, manifest_digest, source_origins

FILES = ("platform-manifest-v1.json", "pytest_platform_contract.py", "gate-preflight-v1.py",
         "compare-gate-evidence-v1.py", "test_gate_platform_contract.py",
         "run-platform-gates-v1.cmd", "run-linux-platform-gates-v1.sh")


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True, stderr=subprocess.PIPE).strip()


def ensure_lab(repo):
    repo = Path(repo).resolve()
    roots = ([Path("C:/CaptivPortal-Lab").resolve()] if os.name == "nt" else
             [Path("/home/zaur_navi/captivportal-lab").resolve()])
    if not any(repo != root and root in repo.parents for root in roots):
        raise ContractError("outside_dedicated_lab")
    return repo


def repository_identity(repo, head, tree):
    repo = ensure_lab(repo)
    if git(repo, "rev-parse", "--show-toplevel").replace("\\", "/") != repo.as_posix():
        raise ContractError("native_git_worktree_required")
    value = {"head": git(repo, "rev-parse", "HEAD"), "tree": git(repo, "rev-parse", "HEAD^{tree}"),
             "status": git(repo, "status", "--porcelain", "--untracked-files=normal")}
    if value != {"head": head, "tree": tree, "status": ""}:
        raise ContractError("exact_clean_artifact_required")
    return value


def safe_environment(output, repo):
    # Explicitly omit ALL production/feature/secret/provider vars and pytest hooks.
    allowed = ("SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "USERPROFILE", "HOME", "LANG", "LC_ALL")
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    binaries = [str(Path(sys.executable).parent)]
    for command in ("git", "node"):
        executable = shutil.which(command)
        if not executable:
            raise ContractError("missing_tool:" + command)
        binaries.append(str(Path(executable).resolve().parent))
    binaries.extend([str(Path(os.environ.get("SYSTEMROOT", "C:/Windows")) / "System32")] if os.name == "nt" else ["/usr/bin", "/bin"])
    env.update(PATH=os.pathsep.join(dict.fromkeys(binaries)),
               PYTHONPATH=os.pathsep.join((str(repo), str(HERE))),
               PYTHONPYCACHEPREFIX=str(output / "pycache"),
               PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONNOUSERSITE="1",
               TEMP=str(output / "tmp"), TMP=str(output / "tmp"), TMPDIR=str(output / "tmp"))
    (output / "tmp").mkdir(exist_ok=True)
    return env


def source_inventory(repo):
    paths = git(repo, "ls-files").splitlines()
    return {p: digest(repo / p) for p in paths if p.endswith((".py", ".ini", ".toml", ".js", ".cjs"))}


def environment_metadata():
    connection = sqlite3.connect(":memory:")
    try:
        options = sorted(row[0] for row in connection.execute("PRAGMA compile_options"))
    finally:
        connection.close()
    return {"interpreter": str(Path(sys.executable).resolve()), "interpreter_sha256": digest(sys.executable),
            "python": platform.python_version(), "platform": platform.platform(),
            "sqlite": sqlite3.sqlite_version, "sqlite_compile_options": options,
            "packages": dict(sorted((d.metadata["Name"].lower(), d.version) for d in importlib.metadata.distributions() if d.metadata.get("Name"))),
            "sys_path": list(sys.path), "environment_keys": sorted(os.environ)}


def origins(repo):
    sys.path.insert(0, str(repo))
    return source_origins(repo)


def sqlite_diagnostic(repo, output):
    # Reuse fixture SETUP, not the two read-only tests or their assertions.
    from tests.analytics.conftest import analytics_stack
    from app.analytics.source_gateway import QueryDeadline
    scratch = output / "sqlite-fixture"
    scratch.mkdir()
    stack = analytics_stack.__wrapped__(scratch)
    plans = {}
    for name, peak in (("peak", True), ("statistics", False)):
        lines = stack.gateway.explain_historical_traffic_combined(
            site_id="site-a", from_utc="2026-01-01T11:55:00.000Z", to_utc="2026-01-01T12:00:00.000Z",
            evaluated_at_utc="2026-01-01T12:00:00.000Z", bucket_seconds=300,
            gap_threshold_seconds=180, max_site_sample_source_skew_seconds=60,
            deadline=QueryDeadline.after(10), **({"include_peak_load": True} if peak else {}))
        plans[name] = {"lines": list(lines), "validated_cycles_materializations": "\n".join(lines).count("MATERIALIZE validated_cycles")}
    return {"status": "DIAGNOSTIC_ONLY", "test_functions_executed": False, "plans": plans,
            "origins": {"fixture": str(Path(sys.modules[analytics_stack.__module__].__file__).resolve()),
                        "gateway": str(Path(sys.modules[stack.gateway.__class__.__module__].__file__).resolve())}}


def approved_lock(lock, repo, launcher, lock_sha, profile):
    lock_path = HERE / "gate-environment-lock-v1.json"
    if digest(lock_path) != lock_sha:
        raise ContractError("environment_lock_hash")
    exact(lock, {"schema_version", "gate_identity", "status", "approval", "profiles", "infrastructure_sha256", "approved_artifacts", "collection_inventories"})
    if lock["schema_version"] != 1 or lock["gate_identity"] != GATE or lock["status"] != "APPROVED" or not lock["approval"]:
        raise ContractError("draft_environment_not_admitted")
    exact(lock["approval"], {"authority", "reference", "body_sha256"})
    if (lock["approval"]["authority"] != "TECH_LEAD_21" or not lock["approval"]["reference"]
            or lock["approval"]["body_sha256"] != manifest_digest(lock)):
        raise ContractError("environment_approval_binding")
    if set(lock["infrastructure_sha256"]) != set(FILES):
        raise ContractError("infrastructure_scope")
    for name in FILES:
        if digest(HERE / name) != lock["infrastructure_sha256"][name]:
            raise ContractError("infrastructure_origin:" + name)
    if Path(launcher).resolve().parent != HERE or Path(launcher).name != (
            "run-platform-gates-v1.cmd" if profile == "windows" else "run-linux-platform-gates-v1.sh"):
        raise ContractError("explicit_launcher_origin")
    observed = environment_metadata()
    expected = lock["profiles"][profile]
    for key in ("python", "sqlite", "sqlite_compile_options", "interpreter_sha256", "packages"):
        if observed[key] != expected[key]:
            raise ContractError("environment_drift:" + key)
    return observed


def write_once(path, value):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(value, handle, sort_keys=True, indent=2)


def launch_owner_gate(args, repo, output, before, metadata):
    manifest_path = HERE / "platform-manifest-v1.json"
    manifest = validate_manifest(strict_json(manifest_path), require_approved=True)
    lock = strict_json(HERE / "gate-environment-lock-v1.json")
    profile = "windows" if os.name == "nt" else "linux"
    observed = approved_lock(lock, repo, args.launcher, args.lock_sha256, profile)
    artifact = {"head": args.head, "tree": args.tree}
    if artifact not in lock["approved_artifacts"]:
        raise ContractError("unapproved_composed_tree")
    expected = lock["collection_inventories"].get(args.tree)
    if not expected:
        raise ContractError("collection_inventory_not_frozen")
    context = {"schema_version": 1, "gate_identity": GATE, "platform": profile,
               "repo": str(repo), "head": args.head, "tree": args.tree,
               "manifest_sha256": digest(manifest_path), "plugin_sha256": digest(HERE / "pytest_platform_contract.py"),
               "environment": observed, "source_inventory": source_inventory(repo),
               "expected_collection": expected, "launcher_sha256": digest(args.launcher)}
    context_path = output / "context.json"
    write_once(context_path, context)
    command = [sys.executable, "-m", "pytest", "tests", "-q", "-rs", "-p", "pytest_platform_contract",
               "--platform-contract-context=" + str(context_path), "--platform-contract-manifest=" + str(manifest_path),
               "--platform-contract-ledger=" + str(output / "outcome-ledger.json"),
               "--platform-contract-transfer", "--basetemp=" + str(output / "pytest-tmp"),
               "--junitxml=" + str(output / "junit.xml")]
    env = safe_environment(output, repo)
    write_once(output / "invocation.json", {"gate_identity": GATE, "command": command, "environment_keys": sorted(env)})
    with (output / "pytest.log").open("xb") as log:
        status = subprocess.run(command, cwd=repo, env=env, stdout=log, stderr=subprocess.STDOUT).returncode
    after = repository_identity(repo, args.head, args.tree)
    if before != after or source_inventory(repo) != context["source_inventory"]:
        raise ContractError("artifact_changed")
    for name in FILES:
        if digest(HERE / name) != lock["infrastructure_sha256"][name]:
            raise ContractError("infrastructure_changed")
    write_once(output / "owner-execution.json", {"gate_identity": GATE, "status": "FAIL" if status else "WINDOWS_LINUX_LANE_COMPLETE",
               "pytest_exit_code": status, "before": before, "after": after, "metadata": metadata,
               "ledger_sha256": digest(output / "outcome-ledger.json")})
    return status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--tree", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--sqlite-diagnostic", action="store_true")
    parser.add_argument("--run-owner-gate", action="store_true")
    parser.add_argument("--launcher")
    parser.add_argument("--lock-sha256")
    args = parser.parse_args()
    if args.sqlite_diagnostic and args.run_owner_gate:
        raise ContractError("diagnostic_is_not_gate")
    repo = ensure_lab(args.repo)
    before = repository_identity(repo, args.head, args.tree)
    output = Path(args.output).resolve()
    if output.exists() or repo == output or repo in output.parents:
        raise ContractError("fresh_external_output_required")
    output.mkdir(parents=True)
    metadata = {"git": before, "origins": origins(repo), "environment": environment_metadata(),
                "preflight_sha256": digest(__file__), "source_inventory": source_inventory(repo),
                "gate_identity": GATE, "kind": "PREPARATION_ONLY"}
    if args.run_owner_gate:
        return launch_owner_gate(args, repo, output, before, metadata)
    if args.sqlite_diagnostic:
        metadata["sqlite_diagnostic"] = sqlite_diagnostic(repo, output)
    metadata["git_after"] = repository_identity(repo, args.head, args.tree)
    if metadata["source_inventory"] != source_inventory(repo):
        raise ContractError("diagnostic_source_changed")
    write_once(output / "preparation-evidence.json", metadata)
    print("PREPARATION_EVIDENCE=" + str(output / "preparation-evidence.json"))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as error:
        print("BLOCKED=" + str(error), file=sys.stderr)
        raise SystemExit(2)
