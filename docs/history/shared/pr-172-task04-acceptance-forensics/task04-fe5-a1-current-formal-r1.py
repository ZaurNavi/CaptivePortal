#!/usr/bin/env python3
from __future__ import annotations

import hashlib
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

EXPECTED_COMMIT = "8a39459be3ce7ed40e325736034245f0025cf249"
EXPECTED_TREE = "e2521f27c9f91978e381bce202ab3e3c83aa6dad"
HISTORICAL_PRE_A1_COMMIT = "74f7c7add401e5fec0469d49770466c2747c03cf"

# ---------------------------------------------------------------------------
# Already-formally-accepted A1 K1 artifacts.
# ---------------------------------------------------------------------------

K1_EVIDENCE = (
    ROOT / "official-runs" / "task04" / "a1-k1-materialization-evidence"
    / "repair-20261001T075732Z"
)
K1_FE1_RUN = (
    ROOT / "official-runs" / "task04" / "f-e1"
    / "official-run-20261001-FE1-A1-01"
)
K1_IDS = {
    "k1-source-governance.json":
        "SourceGovernanceRecord:v1:sha256:"
        "3737b8bae599956ed4738a527a89890b9f74c0b316900f8b49a5bb4695f7a0c1",
    "k1-freshness-policy.json":
        "KnowledgeFreshnessPolicy:v1:sha256:"
        "0d33089e064fc58de96eb0c32789e9382fd2e26d213932cdf370b12b1ec6d3a5",
    "k1-provenance-v2.json":
        "KnowledgeProvenanceManifest:v1:sha256:"
        "199176ab51188a95cc9e10a05298b71024d2e194140538a6c3aec1050b70a61d",
}
K1_OWNER_DECISION_ID = "befcc4e0-e10d-4b83-9adc-2fc3f0dd2314"
K1_EXPECTED_RETRIEVED_AT_UTC = "2026-10-01T06:34:49.000Z"

# ---------------------------------------------------------------------------
# Historical unchanged K2B / p0f V1 source + policy authorization.
# ---------------------------------------------------------------------------

P0F_SHA256 = "791444ebf9a97a492b7a94020f721d016584918c437a450ccaa5525a55c95ad0"
P0F_GIT_BLOB_SHA1 = "c4b38b7e5b5621c70df56aa49127b5aaae1ec7e8"
P0F_SIZE = 36529
P0F_RETRIEVED_AT_UTC = "2026-09-22T22:16:00.456Z"
P0F_RETRIEVAL_WINDOW_END_UTC = "2026-09-22T22:16:13.728Z"
P0F_EXPECTED_FRESHNESS_DIGEST = (
    "c509e8343debf97a6295d0a8ed56255d69f724346c2ac20b2955b891614e4f09"
)

HISTORICAL_FE5_OWNER_DECISION_ID = "1c26c5a2-6ee5-4bc8-aa3b-af253891e489"
HISTORICAL_FE5_OWNER_DECIDED_AT_UTC = "2026-09-22T21:15:43.000Z"
HISTORICAL_FE5_OWNER_AUTHORIZATION = (
    "Авторизую F-E5 V1 freshness policy: satori_dhcp = 365d fresh / 730d stale; "
    "p0f3_legacy_tcp = 0ms fresh / INT64_MAX stale, stale usable supporting; "
    "ieee_ra_mac = 48h fresh / 7d stale; для changing sources stale usable только "
    "с supporting ceiling, expired = no claim; без dimension overrides. "
    "Принимаю существующий governance K1/K2B/K4 для F-E5 admission."
)

# ---------------------------------------------------------------------------
# Newly accepted refreshed K4 artifacts from F-E4 R2.
# ---------------------------------------------------------------------------

K4_FE4_RUN = (
    ROOT / "official-runs" / "task04" / "f-e4"
    / "official-run-20261001T101057Z-FE4-A1-K4-REFRESH-R2"
)
K4_IDS = {
    "k4-source-governance.json":
        "SourceGovernanceRecord:v1:sha256:"
        "5f0a3777a274daa4acedec11d29da34bc1fbe1f23e593188fcf8b0d03adf8125",
    "k4-freshness-policy.json":
        "KnowledgeFreshnessPolicy:v1:sha256:"
        "9a3a58d72dfb660b9a639b7558424cd55d213f8306e586c1b263aa4cda0d3df5",
    "k4-provenance-refreshed.json":
        "KnowledgeProvenanceManifest:v1:sha256:"
        "68c84447525d42946a5a49b42ea9a82093f4da7ff8e8311843e229b444adeb49",
}
K4_OWNER_DECISION_ID = "8dc86bbf-23ce-41bd-b5a3-f1230c501683"
K4_EXPECTED_RETRIEVED_AT_UTC = "2026-10-01T09:50:30.800Z"
K4_EXPECTED_SOURCE_BUNDLE_SHA256 = (
    "34b596dddfa200c1c2559d30e5131933b4807dea4f73ac0d14dfccefec55eecc"
)
K4_EXPECTED_FE4_GATE_ID = (
    "GateResultManifest:v1:sha256:"
    "dc4ab75e2a3313acb787d709659d6fb8b522f202eac5fbf23873df2424864c28"
)

# Exact A1 F-E5 source-contract strings. These are pinned independently here so
# a candidate drift cannot self-authorize by supplying both expectation and value.
K1_CAVEAT = (
    "direct admitted DHCP taxonomy mappings only; supporting platform authority; "
    "strong canonical device-class authority subject to freshness and evidence caps; ambiguity preserved"
)
K2B_CAVEAT = (
    "platform_family only; supporting authority; legacy source; other dimensions NO_CLAIM"
)
K4_CAVEAT = (
    "raw mac_assignment_org only; manufacturer_mapping remains null unless separately reviewed"
)

F_E5_CODE = "app/device_fingerprint/fe5_external_knowledge.py"
K2B_CODE = "app/device_fingerprint/k2b_p0f_import.py"


def execution_fail(reason: str) -> None:
    print("")
    print("F_E5_EXECUTION_STATUS=FAIL")
    print("F_E5_FORMAL_GATE_EXECUTED=NO")
    print("REASON=" + reason)
    print("PRODUCTION_ACTION=NO")
    raise SystemExit(1)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(
        f"blob {len(data)}\0".encode("ascii") + data
    ).hexdigest()


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
        execution_fail("GIT_FAILURE:" + " ".join(args) + ":" + cp.stderr.strip())
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
        execution_fail("RETAINED_EVIDENCE_MISSING:" + str(path))
    return {
        "evidence_label": label,
        "file_sha256": sha256_file(path),
        "media_type": media_type,
        "path_or_reference": str(path),
    }


def validate_decision_record(
    path: pathlib.Path,
    *,
    expected_id: str,
    canonical_artifact_json,
) -> dict[str, Any]:
    if not path.is_file():
        execution_fail("DECISION_RECORD_MISSING:" + str(path))
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        execution_fail("DECISION_RECORD_PARSE_FAILURE:" + repr(exc))
    if obj.get("decision_record_id") != expected_id:
        execution_fail("DECISION_RECORD_ID_MISMATCH:" + str(path))
    record_hash = obj.get("record_sha256")
    if not isinstance(record_hash, str):
        execution_fail("DECISION_RECORD_HASH_MISSING:" + str(path))
    base = dict(obj)
    base.pop("record_sha256", None)
    actual_hash = hashlib.sha256(canonical_artifact_json(base)).hexdigest()
    if actual_hash != record_hash:
        execution_fail("DECISION_RECORD_HASH_MISMATCH:" + str(path))
    if obj.get("decision") not in {"ACCEPT", "APPROVE_EXCEPTION", "ACKNOWLEDGE_RISK"}:
        execution_fail("DECISION_RECORD_NOT_ACCEPTING:" + str(path))
    if obj.get("actor_role") != "OWNER":
        execution_fail("DECISION_RECORD_NOT_OWNER:" + str(path))
    return obj


def discover_p0f() -> tuple[pathlib.Path, bytes, list[str]]:
    roots = [
        ROOT / "artifacts",
        ROOT / "official-runs",
        ROOT / "inputs",
    ]
    exact_hits: list[pathlib.Path] = []
    seen: set[str] = set()

    # Prefer named source files and avoid scanning repository/.venv internals.
    for base in roots:
        if not base.exists():
            continue
        try:
            candidates = list(base.rglob("p0f.fp"))
        except OSError:
            candidates = []
        for path in candidates:
            try:
                key = str(path.resolve()).lower()
                if key in seen or not path.is_file() or path.stat().st_size != P0F_SIZE:
                    continue
                seen.add(key)
                data = path.read_bytes()
            except OSError:
                continue
            if (
                sha256_bytes(data) == P0F_SHA256
                and git_blob_sha1(data) == P0F_GIT_BLOB_SHA1
            ):
                exact_hits.append(path.resolve())

    # Historical retained layouts were not required to preserve the original
    # filename. If named discovery misses, do a bounded exact-size scan under
    # artifacts only.
    if not exact_hits:
        base = ROOT / "artifacts"
        if base.exists():
            for current, dirs, files in os.walk(base):
                dirs[:] = [
                    d for d in dirs
                    if d not in {".git", ".venv", "venv", "__pycache__", "node_modules", ".pytest_cache"}
                ]
                for name in files:
                    path = pathlib.Path(current) / name
                    try:
                        if path.stat().st_size != P0F_SIZE:
                            continue
                        data = path.read_bytes()
                    except OSError:
                        continue
                    if (
                        sha256_bytes(data) == P0F_SHA256
                        and git_blob_sha1(data) == P0F_GIT_BLOB_SHA1
                    ):
                        exact_hits.append(path.resolve())

    unique_hits = sorted({str(p): p for p in exact_hits}.values(), key=lambda p: str(p).lower())
    if not unique_hits:
        execution_fail("PINNED_P0F_SOURCE_NOT_FOUND")

    # Multiple retained copies of identical pinned bytes are not a semantic
    # ambiguity. Use deterministic lexicographic path only for evidence location.
    selected = unique_hits[0]
    data = selected.read_bytes()
    return selected, data, [str(p) for p in unique_hits]


# ---------------------------------------------------------------------------
# 1. Candidate pin / clean tree.
# ---------------------------------------------------------------------------

if not REPO.is_dir():
    execution_fail("REPAIRED_REPO_MISSING")

commit = git("rev-parse", "HEAD").lower()
tree = git("rev-parse", "HEAD^{tree}").lower()
if commit != EXPECTED_COMMIT:
    execution_fail("CANDIDATE_COMMIT_MISMATCH:" + commit)
if tree != EXPECTED_TREE:
    execution_fail("CANDIDATE_TREE_MISMATCH:" + tree)
if git("status", "--porcelain"):
    execution_fail("CANDIDATE_WORKTREE_NOT_CLEAN")

# K2B product importer must remain byte-identical to pre-A1 candidate.
old_k2b_blob = git("rev-parse", f"{HISTORICAL_PRE_A1_COMMIT}:{K2B_CODE}").lower()
new_k2b_blob = git("rev-parse", f"HEAD:{K2B_CODE}").lower()
if old_k2b_blob != new_k2b_blob:
    execution_fail(
        f"K2B_IMPORTER_CHANGED_UNEXPECTEDLY:old={old_k2b_blob}:new={new_k2b_blob}"
    )

# ---------------------------------------------------------------------------
# 2. Import exact current candidate APIs.
# ---------------------------------------------------------------------------

sys.path.insert(0, str(REPO))

from app.device_fingerprint.artifact_content import (
    ArtifactRef,
    canonical_artifact_json,
    make_artifact_content,
)
from app.device_fingerprint.fe5_external_knowledge import (
    ExternalKnowledgeCandidate,
    build_p0f_k2b_external_provenance,
    build_p0f_k2b_freshness_policy,
    run_fe5_external_admission_gate,
)
from app.device_fingerprint.k2b_p0f_import import (
    build_p0f_k2b_source_governance_candidate,
    verify_p0f_source_bytes,
)

# ---------------------------------------------------------------------------
# 3. Load and independently reconstruct exact accepted K1/K4 artifacts.
# ---------------------------------------------------------------------------

def load_artifact(path: pathlib.Path, expected_id: str):
    if not path.is_file():
        execution_fail("ARTIFACT_FILE_MISSING:" + str(path))
    raw = path.read_bytes()
    try:
        obj = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        execution_fail("ARTIFACT_PARSE_FAILURE:" + str(path) + ":" + repr(exc))
    try:
        rebuilt = make_artifact_content(obj["artifact_type"], obj["semantic_payload"])
    except Exception as exc:
        execution_fail("ARTIFACT_REBUILD_FAILURE:" + str(path) + ":" + repr(exc))
    if rebuilt.artifact_id != expected_id:
        execution_fail(
            f"ARTIFACT_ID_MISMATCH:{path.name}:"
            f"expected={expected_id}:actual={rebuilt.artifact_id}"
        )
    if obj.get("artifact_id") != rebuilt.artifact_id:
        execution_fail("STORED_ARTIFACT_ID_MISMATCH:" + str(path))
    if obj.get("content_sha256") != rebuilt.content_sha256:
        execution_fail("STORED_ARTIFACT_DIGEST_MISMATCH:" + str(path))
    if canonical_artifact_json(obj) != raw:
        execution_fail("NONCANONICAL_ARTIFACT_FILE:" + str(path))
    return rebuilt

k1_gov = load_artifact(K1_EVIDENCE / "k1-source-governance.json", K1_IDS["k1-source-governance.json"])
k1_policy = load_artifact(K1_EVIDENCE / "k1-freshness-policy.json", K1_IDS["k1-freshness-policy.json"])
k1_prov = load_artifact(K1_EVIDENCE / "k1-provenance-v2.json", K1_IDS["k1-provenance-v2.json"])

if k1_prov.semantic_payload.get("retrieved_at_utc") != K1_EXPECTED_RETRIEVED_AT_UTC:
    execution_fail("K1_RETRIEVED_AT_DRIFT")
if k1_prov.semantic_payload.get("source_governance_record") != ArtifactRef(
    k1_gov.artifact_id, k1_gov.content_sha256
).as_dict():
    execution_fail("K1_PROVENANCE_GOVERNANCE_REF_MISMATCH")
if k1_prov.semantic_payload.get("knowledge_freshness_policy") != ArtifactRef(
    k1_policy.artifact_id, k1_policy.content_sha256
).as_dict():
    execution_fail("K1_PROVENANCE_FRESHNESS_REF_MISMATCH")

k4_gov = load_artifact(K4_FE4_RUN / "k4-source-governance.json", K4_IDS["k4-source-governance.json"])
k4_policy = load_artifact(K4_FE4_RUN / "k4-freshness-policy.json", K4_IDS["k4-freshness-policy.json"])
k4_prov = load_artifact(K4_FE4_RUN / "k4-provenance-refreshed.json", K4_IDS["k4-provenance-refreshed.json"])

if k4_prov.semantic_payload.get("retrieved_at_utc") != K4_EXPECTED_RETRIEVED_AT_UTC:
    execution_fail("K4_RETRIEVED_AT_DRIFT")
if k4_prov.semantic_payload.get("source_artifact_sha256") != K4_EXPECTED_SOURCE_BUNDLE_SHA256:
    execution_fail("K4_SOURCE_BUNDLE_DRIFT")
if k4_prov.semantic_payload.get("source_governance_record") != ArtifactRef(
    k4_gov.artifact_id, k4_gov.content_sha256
).as_dict():
    execution_fail("K4_PROVENANCE_GOVERNANCE_REF_MISMATCH")
if k4_prov.semantic_payload.get("knowledge_freshness_policy") != ArtifactRef(
    k4_policy.artifact_id, k4_policy.content_sha256
).as_dict():
    execution_fail("K4_PROVENANCE_FRESHNESS_REF_MISMATCH")

# Verify F-E4 GateResult that admitted these exact refreshed K4 artifacts.
k4_gate_path = K4_FE4_RUN / "gate-result-manifest.json"
if not k4_gate_path.is_file():
    execution_fail("K4_FE4_GATE_RESULT_MISSING")
k4_gate_obj = json.loads(k4_gate_path.read_text(encoding="utf-8"))
if k4_gate_obj.get("artifact_id") != K4_EXPECTED_FE4_GATE_ID:
    execution_fail("K4_FE4_GATE_RESULT_ID_MISMATCH")
if k4_gate_obj.get("semantic_payload", {}).get("status") != "PASS":
    execution_fail("K4_FE4_NOT_PASS")

# Current Owner DecisionRecords for changed K1 and refreshed K4 governance.
k1_decision_path = K1_FE1_RUN / "owner-decision-record.json"
k4_decision_path = K4_FE4_RUN / "owner-decision-record.json"
k1_decision = validate_decision_record(
    k1_decision_path,
    expected_id=K1_OWNER_DECISION_ID,
    canonical_artifact_json=canonical_artifact_json,
)
k4_decision = validate_decision_record(
    k4_decision_path,
    expected_id=K4_OWNER_DECISION_ID,
    canonical_artifact_json=canonical_artifact_json,
)

# ---------------------------------------------------------------------------
# 4. Rebind unchanged legacy K2B from exact retained p0f bytes.
# ---------------------------------------------------------------------------

p0f_path, p0f_bytes, p0f_exact_copy_paths = discover_p0f()

if len(p0f_bytes) != P0F_SIZE:
    execution_fail("P0F_SIZE_MISMATCH")
if sha256_bytes(p0f_bytes) != P0F_SHA256:
    execution_fail("P0F_SHA256_MISMATCH")
if git_blob_sha1(p0f_bytes) != P0F_GIT_BLOB_SHA1:
    execution_fail("P0F_GIT_BLOB_SHA1_MISMATCH")
if verify_p0f_source_bytes(p0f_bytes) != P0F_SHA256:
    execution_fail("P0F_PRODUCT_VERIFIER_MISMATCH")

k2_gov = build_p0f_k2b_source_governance_candidate(p0f_bytes)
k2_policy = build_p0f_k2b_freshness_policy()
if k2_policy.content_sha256 != P0F_EXPECTED_FRESHNESS_DIGEST:
    execution_fail(
        "K2B_FRESHNESS_POLICY_CHANGED:"
        + k2_policy.content_sha256
    )

k2_prov = build_p0f_k2b_external_provenance(
    p0f_bytes,
    retrieved_at_utc=P0F_RETRIEVED_AT_UTC,
    governance=k2_gov,
    freshness_policy=k2_policy,
)

k2pp = k2_prov.semantic_payload
if k2pp.get("source_artifact_sha256") != P0F_SHA256:
    execution_fail("K2B_PROVENANCE_SOURCE_SHA_MISMATCH")
if k2pp.get("retrieved_at_utc") != P0F_RETRIEVED_AT_UTC:
    execution_fail("K2B_PROVENANCE_RETRIEVED_AT_MISMATCH")
if k2pp.get("source_provider_version_metadata") != (
    "peace-maker/p0f3-database@7687e779c42c256c1f36b8c48da7e1f8fe24c2d4:"
    "p0f.fp;source_character=legacy"
):
    execution_fail("K2B_PROVIDER_METADATA_DRIFT")
if k2pp.get("importer_identity") != "captivportal.k2b_p0f_import":
    execution_fail("K2B_IMPORTER_IDENTITY_DRIFT")
if k2pp.get("importer_version") != "1":
    execution_fail("K2B_IMPORTER_VERSION_DRIFT")

# ---------------------------------------------------------------------------
# 5. Construct exact three-source F-E5 candidates.
# ---------------------------------------------------------------------------

k1 = ExternalKnowledgeCandidate(
    "K1",
    "satori_dhcp",
    "current",
    K1_CAVEAT,
    k1_gov,
    k1_policy,
    k1_prov,
)
k2 = ExternalKnowledgeCandidate(
    "K2B",
    "p0f3_legacy_tcp",
    "legacy",
    K2B_CAVEAT,
    k2_gov,
    k2_policy,
    k2_prov,
)
k4 = ExternalKnowledgeCandidate(
    "K4",
    "ieee_ra_mac",
    "current",
    K4_CAVEAT,
    k4_gov,
    k4_policy,
    k4_prov,
)

# ---------------------------------------------------------------------------
# 6. Prepare immutable evidence before F-E5 captures its own trusted clock.
# ---------------------------------------------------------------------------

stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
OUT = (
    ROOT / "official-runs" / "task04" / "f-e5"
    / ("official-run-" + stamp + "-FE5-A1-CURRENT-01")
)
if OUT.exists():
    execution_fail("F_E5_OUTPUT_ALREADY_EXISTS")
OUT.mkdir(parents=True)

# Write reconstructed unchanged K2B artifacts for current audit lineage.
def write_artifact(path: pathlib.Path, content: Any) -> None:
    path.write_bytes(canonical_artifact_json(artifact_envelope(content)))

k2_gov_path = OUT / "k2b-source-governance.json"
k2_policy_path = OUT / "k2b-freshness-policy.json"
k2_prov_path = OUT / "k2b-provenance.json"
write_artifact(k2_gov_path, k2_gov)
write_artifact(k2_policy_path, k2_policy)
write_artifact(k2_prov_path, k2_prov)

p0f_verification = {
    "evidence_contract": "captivportal.fe5.a1.p0f_retained_source_verification.v1",
    "source_family_id": "p0f3_legacy_tcp",
    "selected_retained_path": str(p0f_path),
    "all_exact_retained_copy_paths": p0f_exact_copy_paths,
    "size_bytes": len(p0f_bytes),
    "sha256": P0F_SHA256,
    "git_blob_sha1": P0F_GIT_BLOB_SHA1,
    "retrieved_at_utc": P0F_RETRIEVED_AT_UTC,
    "retrieval_window_end_utc": P0F_RETRIEVAL_WINDOW_END_UTC,
    "source_character": "legacy",
    "semantic_change": False,
    "production_action": False,
}
p0f_verification_path = OUT / "p0f-retained-source-verification.json"
p0f_verification_path.write_bytes(canonical_artifact_json(p0f_verification))

decision_lineage = {
    "evidence_contract": "captivportal.fe5.a1.owner_decision_lineage.v1",
    "purpose": (
        "Consume existing Owner decisions; do not fabricate a new Owner decision for F-E5."
    ),
    "current_k1_governance_decision": {
        "decision_record_id": K1_OWNER_DECISION_ID,
        "decision_record_file": str(k1_decision_path),
        "decision_record_file_sha256": sha256_file(k1_decision_path),
        "decision_record_sha256": k1_decision["record_sha256"],
    },
    "historical_v1_freshness_and_unchanged_k2b_authorization": {
        "decision_record_id": HISTORICAL_FE5_OWNER_DECISION_ID,
        "decided_at_utc": HISTORICAL_FE5_OWNER_DECIDED_AT_UTC,
        "authorization_text": HISTORICAL_FE5_OWNER_AUTHORIZATION,
        "scope_note": (
            "Consumed for unchanged V1 freshness policies and unchanged legacy K2B governance. "
            "It is not used to claim acceptance of the changed A1 K1 governance."
        ),
    },
    "current_k4_governance_decision": {
        "decision_record_id": K4_OWNER_DECISION_ID,
        "decision_record_file": str(k4_decision_path),
        "decision_record_file_sha256": sha256_file(k4_decision_path),
        "decision_record_sha256": k4_decision["record_sha256"],
    },
    "production_action": False,
}
decision_lineage_path = OUT / "owner-decision-lineage.json"
decision_lineage_path.write_bytes(canonical_artifact_json(decision_lineage))

freshness_rationale = {
    "evidence_contract": "captivportal.fe5.a1.freshness_rationale.v1",
    "policies": {
        "satori_dhcp": {
            "fresh_max_age_ms": 31536000000,
            "stale_max_age_ms": 63072000000,
            "retrieved_at_utc": K1_EXPECTED_RETRIEVED_AT_UTC,
            "expected_current_state_for_this_immediate_run": "fresh",
        },
        "p0f3_legacy_tcp": {
            "fresh_max_age_ms": 0,
            "stale_max_age_ms": 9223372036854775807,
            "retrieved_at_utc": P0F_RETRIEVED_AT_UTC,
            "expected_current_state": "stale",
            "stale_claim_strength_cap": "supporting",
        },
        "ieee_ra_mac": {
            "fresh_max_age_ms": 172800000,
            "stale_max_age_ms": 604800000,
            "retrieved_at_utc": K4_EXPECTED_RETRIEVED_AT_UTC,
            "expected_current_state_for_this_immediate_run": "fresh",
        },
    },
    "trusted_clock_rule": (
        "F-E5 gate captures foundation_knowledge_evaluation_at_utc itself; "
        "no caller-supplied or backdated evaluation timestamp."
    ),
    "production_action": False,
}
freshness_rationale_path = OUT / "freshness-rationale.json"
freshness_rationale_path.write_bytes(canonical_artifact_json(freshness_rationale))

# Retained evidence intentionally consumes already-valid F-E1 and F-E4 formal
# outputs rather than rerunning those gates.
retained = [
    evidence_ref(
        "F-E5_A1_CURRENT_K1_GOVERNANCE",
        K1_EVIDENCE / "k1-source-governance.json",
        "application/json",
    ),
    evidence_ref(
        "F-E5_A1_CURRENT_K1_FRESHNESS",
        K1_EVIDENCE / "k1-freshness-policy.json",
        "application/json",
    ),
    evidence_ref(
        "F-E5_A1_CURRENT_K1_PROVENANCE",
        K1_EVIDENCE / "k1-provenance-v2.json",
        "application/json",
    ),
    evidence_ref(
        "F-E5_A1_K1_F_E1_GATE",
        K1_FE1_RUN / "gate-result-manifest.json",
        "application/json",
    ),
    evidence_ref(
        "F-E5_UNCHANGED_K2B_SOURCE",
        p0f_path,
        "text/plain",
    ),
    evidence_ref(
        "F-E5_UNCHANGED_K2B_RETAINED_SOURCE_VERIFICATION",
        p0f_verification_path,
        "application/json",
    ),
    evidence_ref(
        "F-E5_UNCHANGED_K2B_GOVERNANCE",
        k2_gov_path,
        "application/json",
    ),
    evidence_ref(
        "F-E5_UNCHANGED_K2B_FRESHNESS",
        k2_policy_path,
        "application/json",
    ),
    evidence_ref(
        "F-E5_UNCHANGED_K2B_PROVENANCE",
        k2_prov_path,
        "application/json",
    ),
    evidence_ref(
        "F-E5_REFRESHED_K4_GOVERNANCE",
        K4_FE4_RUN / "k4-source-governance.json",
        "application/json",
    ),
    evidence_ref(
        "F-E5_REFRESHED_K4_FRESHNESS",
        K4_FE4_RUN / "k4-freshness-policy.json",
        "application/json",
    ),
    evidence_ref(
        "F-E5_REFRESHED_K4_PROVENANCE",
        K4_FE4_RUN / "k4-provenance-refreshed.json",
        "application/json",
    ),
    evidence_ref(
        "F-E5_REFRESHED_K4_F_E4_GATE",
        K4_FE4_RUN / "gate-result-manifest.json",
        "application/json",
    ),
    evidence_ref(
        "F-E5_OWNER_DECISION_LINEAGE",
        decision_lineage_path,
        "application/json",
    ),
    evidence_ref(
        "F-E5_FRESHNESS_RATIONALE",
        freshness_rationale_path,
        "application/json",
    ),
    evidence_ref(
        "F-E5_CURRENT_GATE_IMPLEMENTATION",
        REPO / F_E5_CODE,
        "text/x-python",
    ),
]

decision_refs = [
    K1_OWNER_DECISION_ID,
    HISTORICAL_FE5_OWNER_DECISION_ID,
    K4_OWNER_DECISION_ID,
]

# ---------------------------------------------------------------------------
# 7. Execute exactly one formal current-time F-E5 gate.
# ---------------------------------------------------------------------------

try:
    execution = run_fe5_external_admission_gate(
        k1,
        k2,
        k4,
        candidate_repository_commit_sha=commit,
        candidate_repository_tree_sha=tree,
        environment_identity="CaptivPortal-Lab-Windows-F-E5-A1-current",
        retained_evidence_refs=retained,
        decision_record_refs=decision_refs,
    )
except Exception as exc:
    execution_fail("F_E5_GATE_EXCEPTION:" + type(exc).__name__ + ":" + str(exc))

gate = execution.gate_result_manifest
gate_path = OUT / "gate-result-manifest.json"
gate_path.write_bytes(canonical_artifact_json(artifact_envelope(gate)))

per_source = list(execution.per_source)
per_source_path = OUT / "per-source-freshness-evaluation.json"
per_source_path.write_bytes(canonical_artifact_json({
    "foundation_knowledge_evaluation_at_utc":
        execution.foundation_knowledge_evaluation_at_utc,
    "per_source": per_source,
    "failure_reasons": list(execution.failure_reasons),
}))

# ---------------------------------------------------------------------------
# 8. Independent postconditions on the formal result.
# ---------------------------------------------------------------------------

payload = gate.semantic_payload
if payload.get("gate_id") != "F-E5":
    execution_fail("F_E5_GATE_ID_MISMATCH_AFTER_EXECUTION")
if payload.get("gate_contract_version") != "R14-F-E5-v1":
    execution_fail("F_E5_GATE_CONTRACT_VERSION_MISMATCH_AFTER_EXECUTION")
if payload.get("candidate_repository_commit_sha") != commit:
    execution_fail("F_E5_GATE_COMMIT_MISMATCH_AFTER_EXECUTION")
if payload.get("candidate_repository_tree_sha") != tree:
    execution_fail("F_E5_GATE_TREE_MISMATCH_AFTER_EXECUTION")

trusted = execution.foundation_knowledge_evaluation_at_utc
if payload.get("trusted_time_inputs", {}).get(
    "foundation_knowledge_evaluation_at_utc"
) != trusted:
    execution_fail("F_E5_TRUSTED_TIME_NOT_BOUND_TO_GATE")

if sorted(payload.get("decision_record_refs", [])) != sorted(decision_refs):
    execution_fail("F_E5_DECISION_LINEAGE_NOT_BOUND")

if len(payload.get("input_artifact_refs", [])) != 9:
    execution_fail("F_E5_INPUT_REF_COUNT_NOT_NINE")

reports = {row["source_family_id"]: row for row in per_source}
if set(reports) != {"satori_dhcp", "p0f3_legacy_tcp", "ieee_ra_mac"}:
    execution_fail("F_E5_PER_SOURCE_SET_MISMATCH")

# For this immediate Route-A execution the refreshed changing sources must still
# be fresh; K2B is intentionally stale-but-eligible/supporting.
expected_states = {
    "satori_dhcp": ("fresh", True, "NO_ADDITIONAL_CAP"),
    "p0f3_legacy_tcp": ("stale", True, "supporting"),
    "ieee_ra_mac": ("fresh", True, "NO_ADDITIONAL_CAP"),
}
for family, (state, eligible, cap) in expected_states.items():
    row = reports[family]
    if row.get("freshness_state") != state:
        execution_fail(
            f"F_E5_UNEXPECTED_FRESHNESS_STATE:{family}:"
            f"{row.get('freshness_state')}:expected={state}"
        )
    if row.get("claim_eligible") is not eligible:
        execution_fail("F_E5_CLAIM_ELIGIBILITY_MISMATCH:" + family)
    if row.get("claim_strength_cap") != cap:
        execution_fail("F_E5_CLAIM_STRENGTH_CAP_MISMATCH:" + family)

summary = {
    "run_schema_version": 1,
    "gate_id": "F-E5",
    "formal_status": payload["status"],
    "candidate_repository_commit_sha": commit,
    "candidate_repository_tree_sha": tree,
    "foundation_knowledge_evaluation_at_utc": trusted,
    "failure_reasons": list(execution.failure_reasons),
    "decision_record_refs": sorted(decision_refs),
    "source_states": {
        family: {
            "source_artifact_sha256": reports[family]["source_artifact_sha256"],
            "retrieved_at_utc": reports[family]["retrieved_at_utc"],
            "age_ms": reports[family]["age_ms"],
            "freshness_state": reports[family]["freshness_state"],
            "claim_eligible": reports[family]["claim_eligible"],
            "claim_strength_cap": reports[family]["claim_strength_cap"],
            "required_explanation_code": reports[family]["required_explanation_code"],
        }
        for family in sorted(reports)
    },
    "accepted_external_artifacts": {
        "k1": {
            "governance": k1_gov.artifact_id,
            "freshness_policy": k1_policy.artifact_id,
            "provenance": k1_prov.artifact_id,
        },
        "k2b": {
            "governance": k2_gov.artifact_id,
            "freshness_policy": k2_policy.artifact_id,
            "provenance": k2_prov.artifact_id,
        },
        "k4": {
            "governance": k4_gov.artifact_id,
            "freshness_policy": k4_policy.artifact_id,
            "provenance": k4_prov.artifact_id,
        },
    },
    "gate_result": {
        "artifact_id": gate.artifact_id,
        "content_sha256": gate.content_sha256,
        "file_sha256": sha256_file(gate_path),
    },
    "per_source_evaluation_sha256": sha256_file(per_source_path),
    "production_action": False,
    "next_gate": "F-E7" if payload["status"] == "PASS" else None,
}
summary_path = OUT / "formal-run-summary.json"
summary_path.write_bytes(canonical_artifact_json(summary))

if git("status", "--porcelain"):
    execution_fail("CANDIDATE_WORKTREE_DIRTY_AFTER_F_E5")

# ---------------------------------------------------------------------------
# 9. Final status. Semantic FAIL remains a retained formal FAIL, never execution
# failure and never silently converted to PASS.
# ---------------------------------------------------------------------------

print("")
print("F_E5_FORMAL_GATE_EXECUTED=YES")
print("F_E5_FORMAL_STATUS=" + payload["status"])
print("CANDIDATE_COMMIT=" + commit)
print("CANDIDATE_TREE=" + tree)
print("FOUNDATION_KNOWLEDGE_EVALUATION_AT_UTC=" + trusted)

for family in ("satori_dhcp", "p0f3_legacy_tcp", "ieee_ra_mac"):
    row = reports[family]
    prefix = {
        "satori_dhcp": "K1",
        "p0f3_legacy_tcp": "K2B",
        "ieee_ra_mac": "K4",
    }[family]
    print(f"{prefix}_SOURCE_FAMILY={family}")
    print(f"{prefix}_SOURCE_SHA256={row['source_artifact_sha256']}")
    print(f"{prefix}_RETRIEVED_AT_UTC={row['retrieved_at_utc']}")
    print(f"{prefix}_AGE_MS={row['age_ms']}")
    print(f"{prefix}_FRESHNESS_STATE={row['freshness_state']}")
    print(f"{prefix}_CLAIM_ELIGIBLE={str(row['claim_eligible']).upper()}")
    print(f"{prefix}_CLAIM_STRENGTH_CAP={row['claim_strength_cap']}")

print("K1_GOVERNANCE_ID=" + k1_gov.artifact_id)
print("K1_FRESHNESS_POLICY_ID=" + k1_policy.artifact_id)
print("K1_PROVENANCE_ID=" + k1_prov.artifact_id)

print("K2B_GOVERNANCE_ID=" + k2_gov.artifact_id)
print("K2B_FRESHNESS_POLICY_ID=" + k2_policy.artifact_id)
print("K2B_PROVENANCE_ID=" + k2_prov.artifact_id)
print("K2B_PINNED_SOURCE_PATH=" + str(p0f_path))

print("K4_GOVERNANCE_ID=" + k4_gov.artifact_id)
print("K4_FRESHNESS_POLICY_ID=" + k4_policy.artifact_id)
print("K4_PROVENANCE_ID=" + k4_prov.artifact_id)

print("F_E5_DECISION_RECORD_REFS=" + ",".join(sorted(decision_refs)))
print("F_E5_GATE_RESULT_ID=" + gate.artifact_id)
print("F_E5_GATE_RESULT_CONTENT_SHA256=" + gate.content_sha256)
print("F_E5_GATE_RESULT_FILE_SHA256=" + sha256_file(gate_path))
print("F_E5_PER_SOURCE_EVALUATION_SHA256=" + sha256_file(per_source_path))
print("F_E5_FORMAL_RUN_SUMMARY_SHA256=" + sha256_file(summary_path))
print("F_E5_OUTPUT_DIRECTORY=" + str(OUT))
print("PRODUCTION_ACTION=NO")

if payload["status"] == "PASS":
    print("NEXT=F-E7")
    raise SystemExit(0)

print("F_E5_FAILURE_REASONS=" + json.dumps(
    list(execution.failure_reasons),
    ensure_ascii=True,
    separators=(",", ":"),
))
print("NEXT=HOLD")
raise SystemExit(2)
