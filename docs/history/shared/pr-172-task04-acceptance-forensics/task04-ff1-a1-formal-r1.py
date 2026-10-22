#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import inspect
import json
import os
import pathlib
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

sys.dont_write_bytecode = True

ROOT = pathlib.Path(r"C:\CaptivPortal-Lab")
REPO = ROOT / "coder-task04-t09-utility-repair-a1"
OUT_ROOT = ROOT / "official-runs" / "task04" / "f-f1"

EXPECTED_COMMIT = "8a39459be3ce7ed40e325736034245f0025cf249"
EXPECTED_TREE = "e2521f27c9f91978e381bce202ab3e3c83aa6dad"

EXPECTED_IDS = {
    "registry":
        "EvidenceSchemaRegistryContract:v1:sha256:"
        "090d763e99247ca3b10be34976069e4e7e708be0899e21a15c6e103a015f7814",

    "capability":
        "CapabilityDisposition:v1:sha256:"
        "53ae5181e5a1fc8aa371214ded51c2ca719aafc21ba27c745b3cfafe5a77ae50",

    "k2a":
        "K2AConformancePackage:v1:sha256:"
        "bbe6fa22ac50e568ee4580faac4ad09f7301bb38f6af2ab2075b8adc39262328",

    "k1":
        "CanonicalKnowledgeRecordSet:v1:sha256:"
        "e6a347de462242f6ef70684e33be3bc16d1d11b7e3ced00271e0363ecbbefe5c",

    "k3":
        "K3PortalRuleSet:v1:sha256:"
        "93ea1f384efe7d1dbbc9c513d09d9e62bdddd9448c0ee070423bc4f54176ed1a",

    "k4":
        "CanonicalKnowledgeRecordSet:v1:sha256:"
        "689f61da6cc8ace5a89677688b685f2a4d479d89bc9582239407d2d42e83536e",

    # Builder identity predicted by the accepted A1 implementation handoff.
    "eacs":
        "EvidenceAdapterContractSet:v1:sha256:"
        "c9711a816fddae6a8d22f2a07c8561fc363c76f7b39f95cde62b66d9957ef32f",
}

A1_ENTRYPOINT = "run_ff1_utility_repair_a1_evidence_adapter_contract_gate"
A1_PROCEDURE = "F-F1-evidence-adapter-contract-set-a1-v1"

SEARCH_ROOTS = (
    ROOT / "official-runs" / "task04",
    ROOT / "artifacts",
)

FOCUSED_TESTS = (
    "tests/device_fingerprint_ff1/test_a1_admission.py",
    "tests/device_fingerprint_ff1/test_evidence_adapter_contracts.py",
)

SOURCE_FILES = (
    "app/device_fingerprint/evidence_adapter_contracts.py",
    "app/device_fingerprint/ff1_evidence_adapter_contracts.py",
    "tests/device_fingerprint_ff1/test_a1_admission.py",
)


def fail(reason: str) -> None:
    print("")
    print("F_F1_EXECUTION_STATUS=FAIL")
    print("F_F1_FORMAL_STATUS=NOT_ACCEPTED")
    print("REASON=" + reason)
    print("PRODUCTION_ACTION=NO")
    raise SystemExit(1)


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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


def artifact_envelope(content: Any) -> dict[str, Any]:
    return {
        "artifact_type": content.artifact_type,
        "artifact_schema_version": content.artifact_schema_version,
        "semantic_payload": content.semantic_payload,
        "content_sha256": content.content_sha256,
        "artifact_id": content.artifact_id,
    }


def evidence_ref(label: str, path: pathlib.Path, media_type: str) -> dict[str, Any]:
    if not path.is_file():
        fail("EVIDENCE_FILE_MISSING:" + str(path))
    return {
        "evidence_label": label,
        "file_sha256": sha256_file(path),
        "media_type": media_type,
        "path_or_reference": str(path),
    }


# ---------------------------------------------------------------------------
# 1. Exact local candidate.
# ---------------------------------------------------------------------------

if not REPO.is_dir():
    fail("REPAIRED_REPO_MISSING")

commit = git("rev-parse", "HEAD").lower()
tree = git("rev-parse", "HEAD^{tree}").lower()

if commit != EXPECTED_COMMIT:
    fail("CANDIDATE_COMMIT_MISMATCH:" + commit)
if tree != EXPECTED_TREE:
    fail("CANDIDATE_TREE_MISMATCH:" + tree)
if git("status", "--porcelain"):
    fail("CANDIDATE_WORKTREE_NOT_CLEAN")

for rel in SOURCE_FILES:
    if not (REPO / rel).is_file():
        fail("REQUIRED_A1_SOURCE_MISSING:" + rel)

# ---------------------------------------------------------------------------
# 2. Import current exact candidate APIs.
# ---------------------------------------------------------------------------

sys.path.insert(0, str(REPO))

from app.device_fingerprint.artifact_content import (
    ArtifactRef,
    canonical_artifact_json,
    make_artifact_content,
)
from app.device_fingerprint.evidence_adapter_contracts import (
    build_initial_evidence_adapter_contract_set_v1,
    build_utility_repair_a1_evidence_adapter_contract_set_v1,
    make_evidence_adapter_contract_set,
)
import app.device_fingerprint.ff1_evidence_adapter_contracts as ff1

if not hasattr(ff1, A1_ENTRYPOINT):
    fail("A1_FF1_ENTRYPOINT_MISSING")

entrypoint = getattr(ff1, A1_ENTRYPOINT)
signature = inspect.signature(entrypoint)

# Fail closed if the local exact-candidate formal API differs from the
# implementation handoff. We do not guess a call shape.
required_parameter_names = {
    "evidence_schema_registry",
    "capability_disposition",
    "k2a_conformance_package",
    "k1_record_set",
    "k3_portal_rule_set",
    "k4_record_set",
    "candidate_repository_commit_sha",
    "candidate_repository_tree_sha",
    "environment_identity",
    "retained_evidence_refs",
    "decision_record_refs",
}

actual_parameter_names = set(signature.parameters)

if actual_parameter_names != required_parameter_names:
    print("A1_FF1_ENTRYPOINT_SIGNATURE=" + str(signature))
    fail(
        "A1_FF1_ENTRYPOINT_SIGNATURE_MISMATCH:"
        + ",".join(sorted(actual_parameter_names))
    )

# ---------------------------------------------------------------------------
# 3. Discover exact already-retained prerequisite ArtifactContents.
# ---------------------------------------------------------------------------

needed = set(EXPECTED_IDS.values()) - {EXPECTED_IDS["eacs"]}
found: dict[str, tuple[pathlib.Path, dict[str, Any]]] = {}

for root in SEARCH_ROOTS:
    if not root.exists():
        continue

    for current, dirs, files in os.walk(root):
        dirs[:] = [
            d for d in dirs
            if d not in {
                ".git", ".venv", "venv", "__pycache__",
                "node_modules", ".pytest_cache",
            }
        ]

        for name in files:
            if not name.lower().endswith(".json"):
                continue

            path = pathlib.Path(current) / name

            try:
                if path.stat().st_size > 32 * 1024 * 1024:
                    continue
                obj = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue

            if not isinstance(obj, dict):
                continue

            artifact_id = obj.get("artifact_id")

            if artifact_id in needed and artifact_id not in found:
                found[artifact_id] = (path, obj)

        if len(found) == len(needed):
            break

    if len(found) == len(needed):
        break


def load_exact(label: str):
    expected_id = EXPECTED_IDS[label]
    entry = found.get(expected_id)

    if entry is None:
        fail("EXACT_PREREQUISITE_ARTIFACT_NOT_FOUND:" + label + ":" + expected_id)

    path, obj = entry

    try:
        rebuilt = make_artifact_content(
            obj["artifact_type"],
            obj["semantic_payload"],
        )
    except Exception as exc:
        fail(
            "PREREQUISITE_ARTIFACT_REBUILD_FAILURE:"
            + label
            + ":"
            + type(exc).__name__
            + ":"
            + str(exc)
        )

    if rebuilt.artifact_id != expected_id:
        fail("PREREQUISITE_ARTIFACT_ID_MISMATCH:" + label)

    if obj.get("artifact_id") != rebuilt.artifact_id:
        fail("STORED_PREREQUISITE_ID_MISMATCH:" + label)

    if obj.get("content_sha256") != rebuilt.content_sha256:
        fail("STORED_PREREQUISITE_DIGEST_MISMATCH:" + label)

    if canonical_artifact_json(obj) != path.read_bytes():
        fail("PREREQUISITE_ARTIFACT_NONCANONICAL:" + label)

    return rebuilt, path


registry, registry_path = load_exact("registry")
capability, capability_path = load_exact("capability")
k2a, k2a_path = load_exact("k2a")
k1, k1_path = load_exact("k1")
k3, k3_path = load_exact("k3")
k4, k4_path = load_exact("k4")

# ---------------------------------------------------------------------------
# 4. Independent A1 EACS builder proof.
# ---------------------------------------------------------------------------

historical = build_initial_evidence_adapter_contract_set_v1(registry)
a1_eacs_1 = build_utility_repair_a1_evidence_adapter_contract_set_v1(registry)
a1_eacs_2 = build_utility_repair_a1_evidence_adapter_contract_set_v1(registry)

if (
    a1_eacs_1.artifact_id != a1_eacs_2.artifact_id
    or a1_eacs_1.content_sha256 != a1_eacs_2.content_sha256
    or a1_eacs_1.semantic_payload_json != a1_eacs_2.semantic_payload_json
):
    fail("A1_EACS_DOUBLE_BUILD_MISMATCH")

if a1_eacs_1.artifact_id != EXPECTED_IDS["eacs"]:
    fail(
        "A1_EACS_ID_MISMATCH:"
        + a1_eacs_1.artifact_id
        + ":expected="
        + EXPECTED_IDS["eacs"]
    )

# Exact only-three-ceiling delta.
expected_payload = historical.semantic_payload
promoted = []

for entry in expected_payload["adapter_entries"]:
    if (
        entry["adapter_kind"] == "TASK01_EVIDENCE"
        and (entry["source_kind"], entry["feature_schema_version"])
        in {
            ("dhcp", 1),
            ("portal_headers", 1),
            ("portal_headers", 2),
        }
    ):
        entry["base_claim_strength_ceiling"] = "strong"
        promoted.append(
            (entry["source_kind"], entry["feature_schema_version"])
        )

if set(promoted) != {
    ("dhcp", 1),
    ("portal_headers", 1),
    ("portal_headers", 2),
}:
    fail("A1_EACS_PROMOTED_SET_MISMATCH")

expected_eacs = make_evidence_adapter_contract_set(expected_payload)

if expected_eacs.artifact_id != a1_eacs_1.artifact_id:
    fail("A1_EACS_NON_CEILING_SEMANTIC_DELTA")

# Input-order determinism.
permuted = a1_eacs_1.semantic_payload
permuted["adapter_entries"] = list(reversed(permuted["adapter_entries"]))

if make_evidence_adapter_contract_set(permuted).artifact_id != a1_eacs_1.artifact_id:
    fail("A1_EACS_INPUT_ORDER_NONDETERMINISTIC")

# ---------------------------------------------------------------------------
# 5. Execute focused F-F1 pytest evidence BEFORE formal gate.
# ---------------------------------------------------------------------------

stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
OUT = OUT_ROOT / ("official-run-" + stamp + "-FF1-A1-01")

if OUT.exists():
    fail("F_F1_OUTPUT_ALREADY_EXISTS")

OUT.mkdir(parents=True)

pytest_log = OUT / "pytest-f-f1-a1.txt"
pytest_tmp = OUT / "pytest-tmp"
process_tmp = OUT / "process-tmp"
process_tmp.mkdir()

for rel in FOCUSED_TESTS:
    if not (REPO / rel).is_file():
        fail("FOCUSED_TEST_FILE_MISSING:" + rel)

env = dict(os.environ)
env["PYTHONDONTWRITEBYTECODE"] = "1"
env["PYTHONPYCACHEPREFIX"] = str(OUT / "pycache")
env["PYTEST_ADDOPTS"] = ""
env["PYTHONPATH"] = str(REPO) + os.pathsep + env.get("PYTHONPATH", "")

for name in ("TEMP", "TMP", "TMPDIR"):
    env[name] = str(process_tmp)

pytest_cmd = [
    sys.executable,
    "-m",
    "pytest",
    "-q",
    "-p",
    "no:cacheprovider",
    "--basetemp",
    str(pytest_tmp),
    *FOCUSED_TESTS,
]

cp = subprocess.run(
    pytest_cmd,
    cwd=str(REPO),
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    encoding="utf-8",
    errors="replace",
    check=False,
)

pytest_log.write_text(cp.stdout, encoding="utf-8")

if cp.returncode != 0:
    print(cp.stdout)
    fail("F_F1_FOCUSED_PYTEST_FAILED:" + str(cp.returncode))

if git("status", "--porcelain"):
    fail("CANDIDATE_WORKTREE_DIRTY_AFTER_F_F1_TESTS")

# ---------------------------------------------------------------------------
# 6. Retained pre-gate proof.
# ---------------------------------------------------------------------------

technical = {
    "proof_schema_version": 1,
    "gate_id": "F-F1",
    "status": "PASS",
    "procedure_or_test_suite_id": A1_PROCEDURE,

    "candidate_repository_commit_sha": commit,
    "candidate_repository_tree_sha": tree,

    "prerequisites": {
        "evidence_schema_registry": {
            "artifact_id": registry.artifact_id,
            "content_sha256": registry.content_sha256,
        },
        "capability_disposition": {
            "artifact_id": capability.artifact_id,
            "content_sha256": capability.content_sha256,
        },
        "k2a_conformance_package": {
            "artifact_id": k2a.artifact_id,
            "content_sha256": k2a.content_sha256,
        },
        "k1_record_set": {
            "artifact_id": k1.artifact_id,
            "content_sha256": k1.content_sha256,
        },
        "k3_portal_rule_set": {
            "artifact_id": k3.artifact_id,
            "content_sha256": k3.content_sha256,
        },
        "k4_record_set": {
            "artifact_id": k4.artifact_id,
            "content_sha256": k4.content_sha256,
        },
    },

    "a1_eacs": {
        "artifact_id": a1_eacs_1.artifact_id,
        "content_sha256": a1_eacs_1.content_sha256,
        "only_promoted_adapter_keys": [
            ["dhcp", 1],
            ["portal_headers", 1],
            ["portal_headers", 2],
        ],
        "double_build_deterministic": True,
        "input_order_invariant": True,
    },

    "focused_pytest": {
        "command": subprocess.list2cmdline(pytest_cmd),
        "exit_code": cp.returncode,
        "log_sha256": sha256_file(pytest_log),
    },

    "owner_decision_required": False,
    "production_action": False,
}

technical_path = OUT / "f-f1-a1-technical-proof.json"
technical_path.write_bytes(canonical_artifact_json(technical))

# ---------------------------------------------------------------------------
# 7. Invoke exact A1 formal gate entrypoint ONCE.
# ---------------------------------------------------------------------------

retained_evidence_refs = [
    evidence_ref(
        "F-F1_A1_TECHNICAL_PROOF",
        technical_path,
        "application/json",
    ),
    evidence_ref(
        "F-F1_A1_FOCUSED_PYTEST",
        pytest_log,
        "text/plain",
    ),
    evidence_ref(
        "F-F1_EVIDENCE_SCHEMA_REGISTRY",
        registry_path,
        "application/json",
    ),
    evidence_ref(
        "F-F1_PORTAL_V2_CAPABILITY_DISPOSITION",
        capability_path,
        "application/json",
    ),
    evidence_ref(
        "F-F1_K2A_CONFORMANCE_PACKAGE",
        k2a_path,
        "application/json",
    ),
    evidence_ref(
        "F-F1_A1_K1_RECORD_SET",
        k1_path,
        "application/json",
    ),
    evidence_ref(
        "F-F1_A1_K3_RULE_SET",
        k3_path,
        "application/json",
    ),
    evidence_ref(
        "F-F1_REFRESHED_K4_RECORD_SET",
        k4_path,
        "application/json",
    ),
    evidence_ref(
        "F-F1_A1_IMPLEMENTATION",
        REPO / "app/device_fingerprint/ff1_evidence_adapter_contracts.py",
        "text/x-python",
    ),
    evidence_ref(
        "F-F1_A1_CONTRACT_BUILDER",
        REPO / "app/device_fingerprint/evidence_adapter_contracts.py",
        "text/x-python",
    ),
]

kwargs = {
    "evidence_schema_registry": registry,
    "capability_disposition": capability,
    "k2a_conformance_package": k2a,
    "k1_record_set": k1,
    "k3_portal_rule_set": k3,
    "k4_record_set": k4,
    "candidate_repository_commit_sha": commit,
    "candidate_repository_tree_sha": tree,
    "environment_identity": "CaptivPortal-Lab-Windows-F-F1-A1",
    "retained_evidence_refs": retained_evidence_refs,
    "decision_record_refs": [],
}

try:
    execution = entrypoint(**kwargs)
except Exception as exc:
    fail(
        "A1_FF1_FORMAL_GATE_EXCEPTION:"
        + type(exc).__name__
        + ":"
        + str(exc)
    )

# Fail closed on expected execution/result surface.
if not hasattr(execution, "gate_result_manifest"):
    fail("A1_FF1_EXECUTION_MISSING_GATE_RESULT_MANIFEST")

gate = execution.gate_result_manifest

if not hasattr(gate, "semantic_payload"):
    fail("A1_FF1_GATE_RESULT_NOT_ARTIFACT_CONTENT")

gp = gate.semantic_payload

if gp.get("gate_id") != "F-F1":
    fail("F_F1_GATE_ID_MISMATCH")

if gp.get("gate_contract_version") != "R14-F-F1-v1":
    fail("F_F1_GATE_CONTRACT_VERSION_MISMATCH")

if gp.get("candidate_repository_commit_sha") != commit:
    fail("F_F1_GATE_COMMIT_MISMATCH")

if gp.get("candidate_repository_tree_sha") != tree:
    fail("F_F1_GATE_TREE_MISMATCH")

if gp.get("decision_record_refs") not in ([], tuple()):
    fail("F_F1_UNEXPECTED_OWNER_DECISION_REF")

status = gp.get("status")
if status not in {"PASS", "FAIL"}:
    fail("F_F1_GATE_STATUS_INVALID:" + str(status))

# Determine output EACS from execution or formal manifest.
output_refs = gp.get("output_artifact_refs", [])

if status == "PASS":
    expected_output_ref = ArtifactRef(
        a1_eacs_1.artifact_id,
        a1_eacs_1.content_sha256,
    ).as_dict()

    if output_refs != [expected_output_ref]:
        fail("F_F1_PASS_OUTPUT_REF_MISMATCH")

# Retain exact A1 EACS candidate regardless of formal status for audit.
eacs_path = OUT / "evidence-adapter-contract-set-a1.json"
eacs_path.write_bytes(canonical_artifact_json(artifact_envelope(a1_eacs_1)))

gate_path = OUT / "gate-result-manifest.json"
gate_path.write_bytes(canonical_artifact_json(artifact_envelope(gate)))

failure_reasons = []

for attr in ("failure_reasons", "reasons"):
    if hasattr(execution, attr):
        value = getattr(execution, attr)
        if value is not None:
            failure_reasons = list(value)
        break

summary = {
    "run_schema_version": 1,
    "gate_id": "F-F1",
    "formal_status": status,

    "candidate_repository_commit_sha": commit,
    "candidate_repository_tree_sha": tree,

    "evidence_adapter_contract_set_artifact_id":
        a1_eacs_1.artifact_id,

    "evidence_adapter_contract_set_content_sha256":
        a1_eacs_1.content_sha256,

    "historical_eacs_artifact_id":
        historical.artifact_id,

    "only_semantic_delta":
        "base_claim_strength_ceiling strong for dhcp/1 and portal_headers/1,2",

    "focused_pytest_log_sha256":
        sha256_file(pytest_log),

    "technical_proof_sha256":
        sha256_file(technical_path),

    "gate_result_id":
        gate.artifact_id,

    "gate_result_content_sha256":
        gate.content_sha256,

    "gate_result_file_sha256":
        sha256_file(gate_path),

    "failure_reasons":
        failure_reasons,

    "owner_decision_required":
        False,

    "production_action":
        False,

    "next":
        "F-F2" if status == "PASS" else "HOLD",
}

summary_path = OUT / "formal-run-summary.json"
summary_path.write_bytes(canonical_artifact_json(summary))

if git("status", "--porcelain"):
    fail("CANDIDATE_WORKTREE_DIRTY_AFTER_F_F1_GATE")

print("")
print("F_F1_FORMAL_GATE_EXECUTED=YES")
print("F_F1_FORMAL_STATUS=" + status)
print("CANDIDATE_COMMIT=" + commit)
print("CANDIDATE_TREE=" + tree)

print("EVIDENCE_SCHEMA_REGISTRY_ID=" + registry.artifact_id)
print("CAPABILITY_DISPOSITION_ID=" + capability.artifact_id)
print("K2A_CONFORMANCE_PACKAGE_ID=" + k2a.artifact_id)

print("K1_RECORD_SET_ID=" + k1.artifact_id)
print("K3_RULE_SET_ID=" + k3.artifact_id)
print("K4_RECORD_SET_ID=" + k4.artifact_id)

print("HISTORICAL_EACS_ID=" + historical.artifact_id)
print("A1_EACS_ID=" + a1_eacs_1.artifact_id)
print("A1_EACS_CONTENT_SHA256=" + a1_eacs_1.content_sha256)

print("A1_PROMOTED_CEILINGS=dhcp/1,portal_headers/1,portal_headers/2")
print("A1_EACS_DOUBLE_BUILD_DETERMINISTIC=TRUE")
print("A1_EACS_INPUT_ORDER_INVARIANT=TRUE")

print("F_F1_PYTEST_LOG_SHA256=" + sha256_file(pytest_log))
print("F_F1_TECHNICAL_PROOF_SHA256=" + sha256_file(technical_path))

print("F_F1_GATE_RESULT_ID=" + gate.artifact_id)
print("F_F1_GATE_RESULT_CONTENT_SHA256=" + gate.content_sha256)
print("F_F1_GATE_RESULT_FILE_SHA256=" + sha256_file(gate_path))

print("F_F1_FORMAL_RUN_SUMMARY_SHA256=" + sha256_file(summary_path))
print("F_F1_OUTPUT_DIRECTORY=" + str(OUT))

print("OWNER_DECISION_REQUIRED=NO")
print("PRODUCTION_ACTION=NO")

if status == "PASS":
    print("NEXT=F-F2")
    raise SystemExit(0)

print(
    "F_F1_FAILURE_REASONS="
    + json.dumps(
        failure_reasons,
        ensure_ascii=True,
        separators=(",", ":"),
    )
)
print("NEXT=HOLD")
raise SystemExit(2)
