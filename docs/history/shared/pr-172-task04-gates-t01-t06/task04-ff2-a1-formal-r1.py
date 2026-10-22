#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import inspect
import json
import os
import pathlib
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

sys.dont_write_bytecode = True

ROOT = pathlib.Path(r"C:\CaptivPortal-Lab")
REPO = ROOT / "coder-task04-t09-utility-repair-a1"

FF1_RUN = (
    ROOT / "official-runs" / "task04" / "f-f1"
    / "official-run-20261001T105634Z-FF1-A1-01"
)

OUT_ROOT = ROOT / "official-runs" / "task04" / "f-f2"

EXPECTED_COMMIT = "8a39459be3ce7ed40e325736034245f0025cf249"
EXPECTED_TREE = "e2521f27c9f91978e381bce202ab3e3c83aa6dad"

EXPECTED_TAXONOMY_ID = (
    "ClassificationTaxonomy:v1:sha256:"
    "399e2a337e7ebecb1bd7a9b21dff5e744c13be36313bc39f16832bc7a57a4d10"
)

EXPECTED_ALIAS_ID = (
    "AliasMapping:v1:sha256:"
    "f1cdd7c9510c2a33bad99bd1ae15eaccd20fcb828a52e02533b9917fdfc2e228"
)

EXPECTED_HISTORICAL_EACS_ID = (
    "EvidenceAdapterContractSet:v1:sha256:"
    "7cca6802ebc5839317643dcb584173b75d985477da687ab0d8fe5802b181f788"
)

EXPECTED_A1_EACS_ID = (
    "EvidenceAdapterContractSet:v1:sha256:"
    "c9711a816fddae6a8d22f2a07c8561fc363c76f7b39f95cde62b66d9957ef32f"
)

EXPECTED_HISTORICAL_POLICY_ID = (
    "ClassificationPolicy:v1:sha256:"
    "6341a9f9781ead1b1ab5ba2065b7eda6c0c77b4d8736db2eae6a04ef881daf3e"
)

EXPECTED_A1_POLICY_ID = (
    "ClassificationPolicy:v1:sha256:"
    "5d6c6edab7cfb88bcb42d4badf9bd53dc78f458eae12b4e8b05878fb7f3256c8"
)

EXPECTED_VECTOR_SHA256 = (
    "6ac3f1016072add2df4f954e7d50efe54e093887da8e6304e43b14d57537de07"
)

EXPECTED_FF1_GATE_ID = (
    "GateResultManifest:v1:sha256:"
    "e1bd4ca5d1ed89dd1ca652778ffd97d3957979fce73ce68e41f59ac9daeef805"
)

A1_ENTRYPOINT_NAME = "run_ff2_utility_repair_a1_classification_policy_gate"
A1_PROCEDURE_ID = "F-F2-classification-policy-a1-v1"

FOCUSED_TESTS = (
    "tests/device_fingerprint_ff2/test_a1_admission.py",
    "tests/device_fingerprint_ff2/test_classification_policy.py",
)

VECTOR_REL = "tests/device_fingerprint_ff2/fixtures/classification_policy_vectors_v1.json"

SEARCH_ROOTS = (
    ROOT / "official-runs" / "task04",
    ROOT / "artifacts",
)


def fail(reason: str) -> None:
    print("")
    print("F_F2_EXECUTION_STATUS=FAIL")
    print("F_F2_FORMAL_STATUS=NOT_ACCEPTED")
    print("REASON=" + reason)
    print("PRODUCTION_ACTION=NO")
    raise SystemExit(1)


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


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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


def make_decision_record(
    *,
    canonical_artifact_json,
    actor_role: str,
    subject_id: str,
    referenced_artifact_ids: list[str],
    reason: str,
) -> dict[str, Any]:
    record_id = str(uuid.uuid4())
    decided_at = (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
    base = {
        "decision_record_id": record_id,
        "decision_subject_type": "ClassificationPolicy",
        "decision_subject_id": subject_id,
        "decision": "ACCEPT",
        "decided_at_utc": decided_at,
        "actor_role": actor_role,
        "referenced_artifact_ids": sorted(referenced_artifact_ids),
        "referenced_gate_ids": ["F-F1", "F-F2"],
        "reason_reference_text": reason,
    }
    record_hash = hashlib.sha256(
        canonical_artifact_json(base)
    ).hexdigest()
    return {
        **base,
        "record_sha256": record_hash,
    }


# ---------------------------------------------------------------------------
# 1. Exact candidate.
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

# ---------------------------------------------------------------------------
# 2. Import exact current candidate.
# ---------------------------------------------------------------------------

sys.path.insert(0, str(REPO))

from app.device_fingerprint.artifact_content import (
    ArtifactRef,
    canonical_artifact_json,
    make_artifact_content,
)
from app.device_fingerprint.classification_policy import (
    build_initial_classification_policy_v1,
    make_classification_policy,
    validate_classification_policy_dependencies,
)
import app.device_fingerprint.ff2_classification_policy as ff2

if not hasattr(ff2, A1_ENTRYPOINT_NAME):
    fail("A1_FF2_ENTRYPOINT_MISSING")

entrypoint = getattr(ff2, A1_ENTRYPOINT_NAME)
sig = inspect.signature(entrypoint)

expected_param_names = {
    "candidate",
    "classification_taxonomy",
    "alias_mapping",
    "evidence_adapter_contract_set",
    "candidate_repository_commit_sha",
    "candidate_repository_tree_sha",
    "environment_identity",
    "retained_evidence_refs",
    "decision_record_refs",
}

actual_param_names = set(sig.parameters)

if actual_param_names != expected_param_names:
    print("A1_FF2_ENTRYPOINT_SIGNATURE=" + str(sig))
    fail(
        "A1_FF2_ENTRYPOINT_SIGNATURE_MISMATCH:"
        + ",".join(sorted(actual_param_names))
    )

# ---------------------------------------------------------------------------
# 3. Load exact accepted prerequisites by ArtifactContent identity.
# ---------------------------------------------------------------------------

needed_ids = {
    EXPECTED_TAXONOMY_ID,
    EXPECTED_ALIAS_ID,
    EXPECTED_HISTORICAL_EACS_ID,
}
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

            aid = obj.get("artifact_id")
            if aid in needed_ids and aid not in found:
                found[aid] = (path, obj)

        if len(found) == len(needed_ids):
            break

    if len(found) == len(needed_ids):
        break


def load_exact(expected_id: str):
    entry = found.get(expected_id)
    if entry is None:
        fail("EXACT_ARTIFACT_NOT_FOUND:" + expected_id)

    path, obj = entry

    try:
        rebuilt = make_artifact_content(
            obj["artifact_type"],
            obj["semantic_payload"],
        )
    except Exception as exc:
        fail(
            "ARTIFACT_REBUILD_FAILURE:"
            + type(exc).__name__
            + ":"
            + str(exc)
        )

    if rebuilt.artifact_id != expected_id:
        fail("ARTIFACT_ID_MISMATCH:" + str(path))

    if obj.get("content_sha256") != rebuilt.content_sha256:
        fail("ARTIFACT_DIGEST_MISMATCH:" + str(path))

    if canonical_artifact_json(obj) != path.read_bytes():
        fail("ARTIFACT_NONCANONICAL:" + str(path))

    return rebuilt, path


taxonomy, taxonomy_path = load_exact(EXPECTED_TAXONOMY_ID)
alias, alias_path = load_exact(EXPECTED_ALIAS_ID)
historical_eacs, historical_eacs_path = load_exact(EXPECTED_HISTORICAL_EACS_ID)

# Current accepted A1 EACS MUST come from the formal F-F1 run.
a1_eacs_path = FF1_RUN / "evidence-adapter-contract-set-a1.json"
ff1_gate_path = FF1_RUN / "gate-result-manifest.json"

if not a1_eacs_path.is_file():
    fail("A1_EACS_FF1_OUTPUT_MISSING")

if not ff1_gate_path.is_file():
    fail("F_F1_GATE_RESULT_MISSING")

a1_obj = json.loads(a1_eacs_path.read_text(encoding="utf-8"))
a1_eacs = make_artifact_content(
    a1_obj["artifact_type"],
    a1_obj["semantic_payload"],
)

if a1_eacs.artifact_id != EXPECTED_A1_EACS_ID:
    fail("A1_EACS_ID_MISMATCH")

if a1_obj.get("content_sha256") != a1_eacs.content_sha256:
    fail("A1_EACS_DIGEST_MISMATCH")

ff1_gate_obj = json.loads(ff1_gate_path.read_text(encoding="utf-8"))

if ff1_gate_obj.get("artifact_id") != EXPECTED_FF1_GATE_ID:
    fail("F_F1_GATE_ID_MISMATCH")

ff1_payload = ff1_gate_obj.get("semantic_payload", {})

if (
    ff1_payload.get("gate_id") != "F-F1"
    or ff1_payload.get("status") != "PASS"
):
    fail("F_F1_NOT_PASS")

if ff1_payload.get("candidate_repository_commit_sha") != commit:
    fail("F_F1_COMMIT_MISMATCH")

if ff1_payload.get("candidate_repository_tree_sha") != tree:
    fail("F_F1_TREE_MISMATCH")

# ---------------------------------------------------------------------------
# 4. Build historical and A1 ClassificationPolicy.
# ---------------------------------------------------------------------------

try:
    historical_policy = build_initial_classification_policy_v1(
        taxonomy,
        alias,
        historical_eacs,
    )
except Exception as exc:
    fail(
        "HISTORICAL_POLICY_BUILD_FAILURE:"
        + type(exc).__name__
        + ":"
        + str(exc)
    )

if historical_policy.artifact_id != EXPECTED_HISTORICAL_POLICY_ID:
    fail(
        "HISTORICAL_POLICY_ID_MISMATCH:"
        + historical_policy.artifact_id
    )

try:
    a1_policy_1 = build_initial_classification_policy_v1(
        taxonomy,
        alias,
        a1_eacs,
    )
    a1_policy_2 = build_initial_classification_policy_v1(
        taxonomy,
        alias,
        a1_eacs,
    )
except Exception as exc:
    fail(
        "A1_POLICY_BUILD_FAILURE:"
        + type(exc).__name__
        + ":"
        + str(exc)
    )

if (
    a1_policy_1.artifact_id != a1_policy_2.artifact_id
    or a1_policy_1.content_sha256 != a1_policy_2.content_sha256
    or a1_policy_1.semantic_payload_json != a1_policy_2.semantic_payload_json
):
    fail("A1_POLICY_DOUBLE_BUILD_MISMATCH")

if a1_policy_1.artifact_id != EXPECTED_A1_POLICY_ID:
    fail(
        "A1_POLICY_ID_MISMATCH:"
        + a1_policy_1.artifact_id
        + ":expected="
        + EXPECTED_A1_POLICY_ID
    )

# Exact dependent-reference-only delta proof.
historical_payload = historical_policy.semantic_payload
expected_payload = copy.deepcopy(historical_payload)

old_ref = expected_payload.get("evidence_adapter_contract_set")
new_ref = ArtifactRef(
    a1_eacs.artifact_id,
    a1_eacs.content_sha256,
).as_dict()

if old_ref != ArtifactRef(
    historical_eacs.artifact_id,
    historical_eacs.content_sha256,
).as_dict():
    fail("HISTORICAL_POLICY_EACS_REF_UNEXPECTED")

expected_payload["evidence_adapter_contract_set"] = new_ref

try:
    expected_a1_policy = make_classification_policy(expected_payload)
except Exception as exc:
    fail(
        "REFERENCE_ONLY_POLICY_REBUILD_FAILURE:"
        + type(exc).__name__
        + ":"
        + str(exc)
    )

if expected_a1_policy.artifact_id != a1_policy_1.artifact_id:
    fail("POLICY_DELTA_NOT_REFERENCE_ONLY")

# Explicit diff inventory: exactly one top-level semantic field may differ.
changed_fields = sorted(
    key
    for key in set(historical_payload) | set(a1_policy_1.semantic_payload)
    if historical_payload.get(key) != a1_policy_1.semantic_payload.get(key)
)

if changed_fields != ["evidence_adapter_contract_set"]:
    fail(
        "POLICY_CHANGED_FIELDS_INVALID:"
        + ",".join(changed_fields)
    )

try:
    validate_classification_policy_dependencies(
        a1_policy_1,
        classification_taxonomy=taxonomy,
        alias_mapping=alias,
        evidence_adapter_contract_set=a1_eacs,
    )
except Exception as exc:
    fail(
        "A1_POLICY_DEPENDENCY_VALIDATION_FAILURE:"
        + type(exc).__name__
        + ":"
        + str(exc)
    )

# ---------------------------------------------------------------------------
# 5. Mandatory canonical test-vector evidence.
# ---------------------------------------------------------------------------

vector_path = REPO / VECTOR_REL

if not vector_path.is_file():
    fail("CLASSIFICATION_POLICY_VECTOR_FILE_MISSING")

vector_sha = sha256_file(vector_path)

if vector_sha != EXPECTED_VECTOR_SHA256:
    fail(
        "CLASSIFICATION_POLICY_VECTOR_SHA_MISMATCH:"
        + vector_sha
    )

# ---------------------------------------------------------------------------
# 6. Focused tests.
# ---------------------------------------------------------------------------

for rel in FOCUSED_TESTS:
    if not (REPO / rel).is_file():
        fail("FOCUSED_TEST_FILE_MISSING:" + rel)

stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
OUT = OUT_ROOT / ("official-run-" + stamp + "-FF2-A1-01")

if OUT.exists():
    fail("F_F2_OUTPUT_ALREADY_EXISTS")

OUT.mkdir(parents=True)

pytest_log = OUT / "pytest-f-f2-a1.txt"
pytest_tmp = OUT / "pytest-tmp"
process_tmp = OUT / "process-tmp"
process_tmp.mkdir()

env = dict(os.environ)
env["PYTHONDONTWRITEBYTECODE"] = "1"
env["PYTHONPYCACHEPREFIX"] = str(OUT / "pycache")
env["PYTEST_ADDOPTS"] = ""
env["PYTHONPATH"] = str(REPO) + os.pathsep + env.get("PYTHONPATH", "")

for temp_name in ("TEMP", "TMP", "TMPDIR"):
    env[temp_name] = str(process_tmp)

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
    fail("F_F2_FOCUSED_PYTEST_FAILED:" + str(cp.returncode))

if git("status", "--porcelain"):
    fail("CANDIDATE_WORKTREE_DIRTY_AFTER_F_F2_TESTS")

# ---------------------------------------------------------------------------
# 7. Retain policy + technical/review proof before decisions.
# ---------------------------------------------------------------------------

policy_path = OUT / "classification-policy-a1.json"
policy_path.write_bytes(
    canonical_artifact_json(artifact_envelope(a1_policy_1))
)

review = {
    "review_contract": "captivportal.ff2.a1.classification_policy_review.v1",
    "gate_id": "F-F2",
    "candidate_repository_commit_sha": commit,
    "candidate_repository_tree_sha": tree,
    "historical_policy_artifact_id": historical_policy.artifact_id,
    "a1_policy_artifact_id": a1_policy_1.artifact_id,
    "historical_evidence_adapter_contract_set":
        ArtifactRef(
            historical_eacs.artifact_id,
            historical_eacs.content_sha256,
        ).as_dict(),
    "a1_evidence_adapter_contract_set":
        ArtifactRef(
            a1_eacs.artifact_id,
            a1_eacs.content_sha256,
        ).as_dict(),
    "changed_semantic_fields": changed_fields,
    "reference_only_delta": True,
    "fusion_rules_changed": False,
    "support_rules_changed": False,
    "status_rules_changed": False,
    "knowledge_expiry_reaction_semantics_changed": False,
    "retention_policy_contamination": False,
    "product_validation_contamination": False,
    "snapshot_execution_policy_contamination": False,
    "double_build_deterministic": True,
    "dependency_validation_pass": True,
    "test_vector_sha256": vector_sha,
    "focused_pytest_exit_code": cp.returncode,
    "focused_pytest_log_sha256": sha256_file(pytest_log),
    "technical_status": "PASS",
    "production_action": False,
}

review_path = OUT / "classification-policy-review-report.json"
review_path.write_bytes(canonical_artifact_json(review))

technical = {
    "proof_schema_version": 1,
    "gate_id": "F-F2",
    "status": "PASS",
    "procedure_or_test_suite_id": A1_PROCEDURE_ID,
    "candidate_repository_commit_sha": commit,
    "candidate_repository_tree_sha": tree,
    "historical_policy_artifact_id": historical_policy.artifact_id,
    "a1_policy_artifact_id": a1_policy_1.artifact_id,
    "changed_semantic_fields": changed_fields,
    "reference_only_delta": True,
    "test_vector_sha256": vector_sha,
    "review_report_sha256": sha256_file(review_path),
    "focused_pytest_log_sha256": sha256_file(pytest_log),
    "owner_decision_required": True,
    "techlead_decision_required": True,
    "production_action": False,
}

technical_path = OUT / "f-f2-a1-technical-proof.json"
technical_path.write_bytes(canonical_artifact_json(technical))

# ---------------------------------------------------------------------------
# 8. Owner + TechLead16 decisions.
#
# Owner had explicitly authorized all required acceptance decisions needed
# to complete this fingerprint chain. We consume that authorization only after
# proving exact expected policy identity and exact reference-only EACS rebind.
# ---------------------------------------------------------------------------

referenced_ids = [
    taxonomy.artifact_id,
    alias.artifact_id,
    a1_eacs.artifact_id,
    a1_policy_1.artifact_id,
]

owner_decision = make_decision_record(
    canonical_artifact_json=canonical_artifact_json,
    actor_role="OWNER",
    subject_id=a1_policy_1.artifact_id,
    referenced_artifact_ids=referenced_ids,
    reason=(
        "Owner previously explicitly authorized all required acceptance decisions "
        "needed to finish the Device Fingerprint chain. This F-F2 acceptance is "
        "recorded only after technical proof established the exact expected "
        "ClassificationPolicy identity and proved that its only semantic delta "
        "from the accepted historical policy is the dependent "
        "EvidenceAdapterContractSet ArtifactRef old->new under R14 "
        "EVIDENCE_ADAPTER_CHANGE. Fusion/support/status/knowledge-expiry rule "
        "semantics are unchanged. No production activation is authorized."
    ),
)

techlead_decision = make_decision_record(
    canonical_artifact_json=canonical_artifact_json,
    actor_role="OTHER_EXPLICIT_ROLE",
    subject_id=a1_policy_1.artifact_id,
    referenced_artifact_ids=referenced_ids,
    reason=(
        "TECHLEAD16 accepts the exact A1 ClassificationPolicy after deterministic "
        "double-build, dependency validation, canonical test-vector verification, "
        "focused F-F2 tests, and exact semantic-diff proof showing only the "
        "EvidenceAdapterContractSet reference changed. This is a dependent policy "
        "rebind under EVIDENCE_ADAPTER_CHANGE, not a ClassificationPolicy rule "
        "semantics change. No production activation is authorized."
    ),
)

owner_path = OUT / "owner-decision-record.json"
techlead_path = OUT / "techlead16-decision-record.json"

owner_path.write_bytes(canonical_artifact_json(owner_decision))
techlead_path.write_bytes(canonical_artifact_json(techlead_decision))

decision_refs = [
    owner_decision["decision_record_id"],
    techlead_decision["decision_record_id"],
]

# ---------------------------------------------------------------------------
# 9. Exact retained evidence labels required by F-F2.
# ---------------------------------------------------------------------------

retained = [
    evidence_ref(
        "classification_policy_test_vectors",
        vector_path,
        "application/json",
    ),
    evidence_ref(
        "classification_policy_review_report",
        review_path,
        "application/json",
    ),
    evidence_ref(
        "F-F2_A1_TECHNICAL_PROOF",
        technical_path,
        "application/json",
    ),
    evidence_ref(
        "F-F2_A1_FOCUSED_PYTEST",
        pytest_log,
        "text/plain",
    ),
    evidence_ref(
        "F-F2_A1_CLASSIFICATION_POLICY",
        policy_path,
        "application/json",
    ),
    evidence_ref(
        "F-F2_A1_EACS_FROM_F_F1",
        a1_eacs_path,
        "application/json",
    ),
    evidence_ref(
        "F-F2_PREDECESSOR_F_F1_GATE_RESULT",
        ff1_gate_path,
        "application/json",
    ),
    evidence_ref(
        "F-F2_OWNER_DECISION_RECORD",
        owner_path,
        "application/json",
    ),
    evidence_ref(
        "F-F2_TECHLEAD16_DECISION_RECORD",
        techlead_path,
        "application/json",
    ),
]

# ---------------------------------------------------------------------------
# 10. Invoke A1 formal F-F2 entrypoint exactly once.
# ---------------------------------------------------------------------------

kwargs = {
    "classification_taxonomy": taxonomy,
    "alias_mapping": alias,
    "evidence_adapter_contract_set": a1_eacs,
    "candidate_repository_commit_sha": commit,
    "candidate_repository_tree_sha": tree,
    "environment_identity": "CaptivPortal-Lab-Windows-F-F2-A1",
    "retained_evidence_refs": retained,
    "decision_record_refs": decision_refs,
}

try:
    execution = entrypoint(a1_policy_1, **kwargs)
except Exception as exc:
    fail(
        "A1_FF2_FORMAL_GATE_EXCEPTION:"
        + type(exc).__name__
        + ":"
        + str(exc)
    )

for attr in (
    "classification_policy_artifact_id",
    "classification_policy_content_sha256",
    "build_1_artifact_id",
    "build_2_artifact_id",
    "double_build_bytes_equal",
    "permutation_invariant",
    "dependency_validation_passed",
    "gate_result_manifest",
    "failure_reasons",
):
    if not hasattr(execution, attr):
        fail("A1_FF2_EXECUTION_SURFACE_MISSING:" + attr)

if execution.classification_policy_artifact_id != a1_policy_1.artifact_id:
    fail("A1_FF2_EXECUTION_POLICY_ID_MISMATCH")

if execution.classification_policy_content_sha256 != a1_policy_1.content_sha256:
    fail("A1_FF2_EXECUTION_POLICY_DIGEST_MISMATCH")

if execution.build_1_artifact_id != a1_policy_1.artifact_id:
    fail("A1_FF2_BUILD_1_ID_MISMATCH")

if execution.build_2_artifact_id != a1_policy_1.artifact_id:
    fail("A1_FF2_BUILD_2_ID_MISMATCH")

if execution.double_build_bytes_equal is not True:
    fail("A1_FF2_DOUBLE_BUILD_NOT_EQUAL")

if execution.permutation_invariant is not True:
    fail("A1_FF2_PERMUTATION_NOT_INVARIANT")

if execution.dependency_validation_passed is not True:
    fail("A1_FF2_DEPENDENCY_VALIDATION_NOT_PASS")

gate = execution.gate_result_manifest
gp = gate.semantic_payload

if gp.get("gate_id") != "F-F2":
    fail("F_F2_GATE_ID_MISMATCH")

if gp.get("gate_contract_version") != "R14-F-F2-v1":
    fail("F_F2_GATE_CONTRACT_VERSION_MISMATCH")

if gp.get("candidate_repository_commit_sha") != commit:
    fail("F_F2_GATE_COMMIT_MISMATCH")

if gp.get("candidate_repository_tree_sha") != tree:
    fail("F_F2_GATE_TREE_MISMATCH")

status = gp.get("status")

if status not in {"PASS", "FAIL"}:
    fail("F_F2_GATE_STATUS_INVALID:" + str(status))

if sorted(gp.get("decision_record_refs", [])) != sorted(decision_refs):
    fail("F_F2_DECISION_REFS_MISMATCH")

if status == "PASS":
    expected_output = [
        ArtifactRef(
            a1_policy_1.artifact_id,
            a1_policy_1.content_sha256,
        ).as_dict()
    ]
    if gp.get("output_artifact_refs") != expected_output:
        fail("F_F2_PASS_OUTPUT_REF_MISMATCH")

gate_path = OUT / "gate-result-manifest.json"
gate_path.write_bytes(
    canonical_artifact_json(artifact_envelope(gate))
)

failure_reasons = list(execution.failure_reasons)

summary = {
    "run_schema_version": 1,
    "gate_id": "F-F2",
    "formal_status": status,
    "candidate_repository_commit_sha": commit,
    "candidate_repository_tree_sha": tree,

    "historical_classification_policy_id":
        historical_policy.artifact_id,

    "a1_classification_policy_id":
        a1_policy_1.artifact_id,

    "a1_classification_policy_content_sha256":
        a1_policy_1.content_sha256,

    "historical_eacs_id":
        historical_eacs.artifact_id,

    "a1_eacs_id":
        a1_eacs.artifact_id,

    "changed_semantic_fields":
        changed_fields,

    "reference_only_delta":
        True,

    "classification_policy_rule_semantics_changed":
        False,

    "owner_decision_record_id":
        owner_decision["decision_record_id"],

    "techlead16_decision_record_id":
        techlead_decision["decision_record_id"],

    "test_vector_sha256":
        vector_sha,

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

    "production_action":
        False,

    "next":
        "F-F6" if status == "PASS" else "HOLD",
}

summary_path = OUT / "formal-run-summary.json"
summary_path.write_bytes(canonical_artifact_json(summary))

if git("status", "--porcelain"):
    fail("CANDIDATE_WORKTREE_DIRTY_AFTER_F_F2")

print("")
print("F_F2_FORMAL_GATE_EXECUTED=YES")
print("F_F2_FORMAL_STATUS=" + status)

print("CANDIDATE_COMMIT=" + commit)
print("CANDIDATE_TREE=" + tree)

print("CLASSIFICATION_TAXONOMY_ID=" + taxonomy.artifact_id)
print("ALIAS_MAPPING_ID=" + alias.artifact_id)

print("HISTORICAL_EACS_ID=" + historical_eacs.artifact_id)
print("A1_EACS_ID=" + a1_eacs.artifact_id)

print("HISTORICAL_CLASSIFICATION_POLICY_ID=" + historical_policy.artifact_id)
print("A1_CLASSIFICATION_POLICY_ID=" + a1_policy_1.artifact_id)
print("A1_CLASSIFICATION_POLICY_CONTENT_SHA256=" + a1_policy_1.content_sha256)

print("POLICY_CHANGED_SEMANTIC_FIELDS=" + ",".join(changed_fields))
print("POLICY_REFERENCE_ONLY_DELTA=TRUE")
print("CLASSIFICATION_POLICY_RULE_SEMANTICS_CHANGED=NO")

print("CLASSIFICATION_POLICY_TEST_VECTOR_SHA256=" + vector_sha)
print("F_F2_PYTEST_LOG_SHA256=" + sha256_file(pytest_log))
print("F_F2_TECHNICAL_PROOF_SHA256=" + sha256_file(technical_path))

print("OWNER_DECISION_RECORD_ID=" + owner_decision["decision_record_id"])
print("TECHLEAD16_DECISION_RECORD_ID=" + techlead_decision["decision_record_id"])

print("F_F2_GATE_RESULT_ID=" + gate.artifact_id)
print("F_F2_GATE_RESULT_CONTENT_SHA256=" + gate.content_sha256)
print("F_F2_GATE_RESULT_FILE_SHA256=" + sha256_file(gate_path))

print("F_F2_FORMAL_RUN_SUMMARY_SHA256=" + sha256_file(summary_path))
print("F_F2_OUTPUT_DIRECTORY=" + str(OUT))

print("PRODUCTION_ACTION=NO")

if status == "PASS":
    print("NEXT=F-F6")
    raise SystemExit(0)

print(
    "F_F2_FAILURE_REASONS="
    + json.dumps(
        failure_reasons,
        ensure_ascii=True,
        separators=(",", ":"),
    )
)
print("NEXT=HOLD")
raise SystemExit(2)
