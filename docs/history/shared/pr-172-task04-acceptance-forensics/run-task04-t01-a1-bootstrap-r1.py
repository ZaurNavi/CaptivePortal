#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys
from datetime import datetime, timezone

BASE = pathlib.Path(
    r"C:\CaptivPortal-Lab\gates\task04\t01\task04-t01-gate-rebind-20260929.py"
)
EXPECTED_BASE_SHA256 = (
    "ee17cbd9a1c6e8e5ac510559ca0d6a21768a26fbb90ae98cb1ed4550d0446668"
)

OLD_COMMIT = b"74f7c7add401e5fec0469d49770466c2747c03cf"
OLD_TREE = b"7e93a4863909c3e807a9d8239924d13e0a0d7f71"

NEW_COMMIT = b"8a39459be3ce7ed40e325736034245f0025cf249"
NEW_TREE = b"e2521f27c9f91978e381bce202ab3e3c83aa6dad"

REPO = pathlib.Path(
    r"C:\CaptivPortal-Lab\coder-task04-t09-utility-repair-a1"
)
FOUNDATION_DB = pathlib.Path(
    r"C:\CaptivPortal-Lab\foundation-control-plane\device-fingerprint-control-plane.sqlite3"
)

TOOLS = pathlib.Path(r"C:\CaptivPortal-Lab\tools")
A1_RUNNER = TOOLS / "task04-t01-gate-a1-20261001.py"
OUTPUT_ROOT = pathlib.Path(
    r"C:\CaptivPortal-Lab\official-runs\task04\t01"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(reason: str) -> None:
    print("")
    print("T01_A1_BOOTSTRAP_STATUS=FAIL")
    print("FORMAL_T01_EXECUTED=NO")
    print("REASON=" + reason)
    print("PRODUCTION_ACTION=NO")
    raise SystemExit(1)


if not BASE.is_file():
    fail("HISTORICAL_T01_HELPER_MISSING:" + str(BASE))

base_bytes = BASE.read_bytes()
base_sha = sha256_bytes(base_bytes)

print("HISTORICAL_T01_HELPER_SHA256=" + base_sha)

if base_sha != EXPECTED_BASE_SHA256:
    fail(
        "HISTORICAL_T01_HELPER_SHA256_MISMATCH:"
        + "expected="
        + EXPECTED_BASE_SHA256
        + ":actual="
        + base_sha
    )

if base_bytes.count(OLD_COMMIT) != 1:
    fail(
        "OLD_COMMIT_OCCURRENCE_COUNT_NOT_ONE:"
        + str(base_bytes.count(OLD_COMMIT))
    )

if base_bytes.count(OLD_TREE) != 1:
    fail(
        "OLD_TREE_OCCURRENCE_COUNT_NOT_ONE:"
        + str(base_bytes.count(OLD_TREE))
    )

patched = base_bytes.replace(OLD_COMMIT, NEW_COMMIT)
patched = patched.replace(OLD_TREE, NEW_TREE)

if OLD_COMMIT in patched or OLD_TREE in patched:
    fail("OLD_CANDIDATE_IDENTITY_REMAINS_AFTER_PATCH")

if patched.count(NEW_COMMIT) != 1:
    fail("NEW_COMMIT_OCCURRENCE_COUNT_NOT_ONE")

if patched.count(NEW_TREE) != 1:
    fail("NEW_TREE_OCCURRENCE_COUNT_NOT_ONE")

TOOLS.mkdir(parents=True, exist_ok=True)

if A1_RUNNER.exists():
    existing = A1_RUNNER.read_bytes()
    if existing != patched:
        fail("A1_T01_RUNNER_ALREADY_EXISTS_WITH_DIFFERENT_BYTES")
else:
    A1_RUNNER.write_bytes(patched)

runner_sha = sha256_file(A1_RUNNER)

print("A1_T01_RUNNER_PATH=" + str(A1_RUNNER))
print("A1_T01_RUNNER_SHA256=" + runner_sha)

# Compile outside repository; syntax verification only.
compile_dir = pathlib.Path(
    r"C:\CaptivPortal-Lab\tmp\task04-t01-a1-bootstrap-pyc"
)
compile_dir.mkdir(parents=True, exist_ok=True)
compiled = compile_dir / "task04-t01-gate-a1-20261001.pyc"

cp_compile = subprocess.run(
    [
        sys.executable,
        "-m",
        "py_compile",
        str(A1_RUNNER),
    ],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    encoding="utf-8",
    errors="replace",
    check=False,
    env={
        **__import__("os").environ,
        "PYTHONPYCACHEPREFIX": str(compile_dir),
    },
)

if cp_compile.returncode != 0:
    print(cp_compile.stdout)
    fail("A1_T01_RUNNER_PY_COMPILE_FAILED")

print("A1_T01_RUNNER_PY_COMPILE=PASS")

if not REPO.is_dir():
    fail("A1_REPOSITORY_MISSING:" + str(REPO))

if not FOUNDATION_DB.is_file():
    fail("FOUNDATION_CONTROL_DB_MISSING:" + str(FOUNDATION_DB))

def git(*args: str) -> str:
    cp = subprocess.run(
        ["git", "-C", str(REPO), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if cp.returncode != 0:
        fail("GIT_FAILURE:" + " ".join(args) + ":" + cp.stderr.strip())
    return cp.stdout.strip()

commit = git("rev-parse", "HEAD")
tree = git("show", "-s", "--format=%T", "HEAD")
status = git("status", "--porcelain")

print("CANDIDATE_COMMIT=" + commit)
print("CANDIDATE_TREE=" + tree)

if commit.encode("ascii") != NEW_COMMIT:
    fail("CANDIDATE_COMMIT_MISMATCH")
if tree.encode("ascii") != NEW_TREE:
    fail("CANDIDATE_TREE_MISMATCH")
if status:
    fail("CANDIDATE_WORKTREE_NOT_CLEAN")

stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
output_dir = OUTPUT_ROOT / ("official-run-" + stamp + "-T01-A1-01")

if output_dir.exists():
    fail("T01_OUTPUT_DIRECTORY_ALREADY_EXISTS")

OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

command = [
    sys.executable,
    str(A1_RUNNER),
    "--repo",
    str(REPO),
    "--foundation-control-db",
    str(FOUNDATION_DB),
    "--output-dir",
    str(output_dir),
]

print("T01_COMMAND=" + subprocess.list2cmdline(command))

cp = subprocess.run(
    command,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    encoding="utf-8",
    errors="replace",
    check=False,
    env={
        **__import__("os").environ,
        "PYTHONPYCACHEPREFIX": str(
            pathlib.Path(
                r"C:\CaptivPortal-Lab\tmp\task04-t01-a1-run-pyc"
            )
        ),
    },
)

print(cp.stdout, end="" if cp.stdout.endswith("\n") else "\n")

print("T01_PROCESS_EXIT_CODE=" + str(cp.returncode))
print("T01_OUTPUT_ROOT=" + str(output_dir))

if cp.returncode != 0:
    print("T01_A1_BOOTSTRAP_STATUS=FORMAL_GATE_NONZERO")
    print("PRODUCTION_ACTION=NO")
    raise SystemExit(cp.returncode)

# Locate the runner-created UUID run directory and summarize immutable outputs.
runs = [p for p in output_dir.iterdir() if p.is_dir()]
if len(runs) != 1:
    fail("T01_RUN_DIRECTORY_COUNT_NOT_ONE:" + str(len(runs)))

run = runs[0]
summary_path = run / "t01-summary.txt"
result_path = run / "t01-gate-result-manifest.json"
proof_path = run / "t01-gate-proof-artifact.json"
evidence_path = run / "t01-execution-evidence.json"
pytest_path = run / "t01-pytest.log"

for path in (
    summary_path,
    result_path,
    proof_path,
    evidence_path,
    pytest_path,
):
    if not path.is_file():
        fail("T01_EXPECTED_OUTPUT_MISSING:" + str(path))

import json

result = json.loads(result_path.read_text(encoding="utf-8"))
proof = json.loads(proof_path.read_text(encoding="utf-8"))
evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

rp = result.get("semantic_payload", {})
pp = proof.get("semantic_payload", {})

if rp.get("gate_id") != "T-01":
    fail("T01_GATE_ID_MISMATCH")
if rp.get("gate_contract_version") != "R14-T-01-v1":
    fail("T01_GATE_CONTRACT_MISMATCH")
if rp.get("status") != "PASS":
    fail("T01_GATE_RESULT_NOT_PASS")
if rp.get("candidate_repository_commit_sha") != NEW_COMMIT.decode():
    fail("T01_GATE_COMMIT_MISMATCH")
if rp.get("candidate_repository_tree_sha") != NEW_TREE.decode():
    fail("T01_GATE_TREE_MISMATCH")
if rp.get("decision_record_refs") != []:
    fail("T01_UNEXPECTED_DECISION_RECORD_REFS")

if pp.get("proof_kind") != "SNAPSHOT_MATERIALIZATION_EXECUTION":
    fail("T01_PROOF_KIND_MISMATCH")
if pp.get("source_gate_id") != "T-01":
    fail("T01_PROOF_SOURCE_GATE_MISMATCH")

matrix = evidence.get("matrix", {})
cases = matrix.get("cases", {})
if len(cases) != 11:
    fail("T01_CASE_COUNT_NOT_ELEVEN")
if matrix.get("all_pass") is not True:
    fail("T01_MATRIX_NOT_PASS")
if set(cases) != {f"T01-M{i:02d}" for i in range(1, 12)}:
    fail("T01_CASE_SET_MISMATCH")
if any(row.get("status") != "PASS" for row in cases.values()):
    fail("T01_CASE_FAILURE_PRESENT")
if matrix.get("transaction_watermark_trace", {}).get("read_sessions") != 1:
    fail("T01_TRANSACTION_READ_SESSION_COUNT_MISMATCH")
if evidence.get("pytest_exit_status") != 0:
    fail("T01_PYTEST_NOT_PASS")

# Exact runner identity must be bound into the proof execution identity.
execution_sha = rp.get("proof_execution_identity", {}).get(
    "execution_artifact_sha256"
)
if execution_sha != runner_sha:
    fail(
        "T01_EXECUTION_ARTIFACT_SHA_MISMATCH:"
        + str(execution_sha)
        + ":expected="
        + runner_sha
    )

# Candidate repository must remain exact/clean after execution.
if git("rev-parse", "HEAD") != NEW_COMMIT.decode():
    fail("CANDIDATE_COMMIT_CHANGED_AFTER_T01")
if git("show", "-s", "--format=%T", "HEAD") != NEW_TREE.decode():
    fail("CANDIDATE_TREE_CHANGED_AFTER_T01")
if git("status", "--porcelain"):
    fail("CANDIDATE_WORKTREE_DIRTY_AFTER_T01")

print("")
print("T01_A1_BOOTSTRAP_STATUS=PASS")
print("T01_FORMAL_GATE_EXECUTED=YES")
print("T01_FORMAL_STATUS=PASS")
print("T01_CASES_PASS=11/11")
print("T01_TRANSACTION_READ_SESSIONS=1")
print("T01_GATE_RESULT_ID=" + str(result["artifact_id"]))
print("T01_GATE_RESULT_CONTENT_SHA256=" + str(result["content_sha256"]))
print("T01_GATE_RESULT_FILE_SHA256=" + sha256_file(result_path))
print("T01_GATE_PROOF_ID=" + str(proof["artifact_id"]))
print("T01_GATE_PROOF_CONTENT_SHA256=" + str(proof["content_sha256"]))
print("T01_GATE_PROOF_FILE_SHA256=" + sha256_file(proof_path))
print("T01_EXECUTION_EVIDENCE_SHA256=" + sha256_file(evidence_path))
print("T01_PYTEST_LOG_SHA256=" + sha256_file(pytest_path))
print("T01_RUN_DIRECTORY=" + str(run))
print("OWNER_DECISION_REQUIRED=NO")
print("PRODUCTION_ACTION=NO")
print("NEXT=T-02")
