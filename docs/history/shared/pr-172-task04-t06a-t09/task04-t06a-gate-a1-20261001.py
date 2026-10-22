"""External T-06A classification profile compatibility gate.

Import is side-effect free. Official execution belongs to Owner/TechLead15.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import sqlite3
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any


sys.dont_write_bytecode = True
EXPECTED_COMMIT = "8a39459be3ce7ed40e325736034245f0025cf249"
EXPECTED_TREE = "e2521f27c9f91978e381bce202ab3e3c83aa6dad"
T01_HELPER = Path(r"C:\CaptivPortal-Lab\tools\task04-t01-gate-a1-20261001.py")
T01_SHA256 = "ac8a73606c8136fae3486ec63ee3ffe200852bbdbf53dc4b72144f369055f6b4"
T06_RUNNER = Path(r"C:\CaptivPortal-Lab\tools\task04-t06-gate-a1-20261001.py")
T06_SHA256 = "0d2b5f4c8543a6ab578d1a4c84f613650dc4e72e497c6485c618b5c87f1dca61"
T06_MANIFEST_ID = "ClassifierArtifactManifest:v1:sha256:3a1aadd86fbf90c7a0d97f7310a18090c69d755b9a50b2034aa3c289c56bd957"
T06_RESULT_ID = "GateResultManifest:v1:sha256:250b29ca6c64d7ea8c082ea798c93bf8a684ac7b7479b9f1e167618e40faf70c"
EXACT_IDS = {
    "foundation_runtime_profile": "FoundationRuntimeProfile:v1:sha256:9287f48e01426a0440c06644821ebbbdf8f052f08d930968748f3bf6c3e9f4d5",
    "knowledge_bundle": "KnowledgeBundle:v1:sha256:70c39dcb9ebca5b07f80b0846c394b244c6f700fc4c738e43625f767de0eb660",
    "classification_policy": "ClassificationPolicy:v1:sha256:5d6c6edab7cfb88bcb42d4badf9bd53dc78f458eae12b4e8b05878fb7f3256c8",
    "evidence_adapter_contract_set": "EvidenceAdapterContractSet:v1:sha256:c9711a816fddae6a8d22f2a07c8561fc363c76f7b39f95cde62b66d9957ef32f",
}
GATE_ID = "T-06A"
GATE_CONTRACT = "R14-T-06A-v1"
PROCEDURE = "T-06A-classification-runtime-profile-compatibility-v1"
PROOF_KIND = "CLASSIFICATION_PROFILE_COMPATIBILITY"
PROFILE_VERSION = 1  # Candidate's existing ff5_runtime_profile_atomicity._Fixture profile version.
_HELPER = None
_T06 = None

ROOT = Path(r"C:\CaptivPortal-Lab")
P0F_PATH = ROOT / "artifacts" / "fe5-external-governance" / "sources" / "p0f.fp"
P0F_SHA256 = "791444ebf9a97a492b7a94020f721d016584918c437a450ccaa5525a55c95ad0"

A1_ARTIFACT_SPECS = {
    "k1_governance": (
        "SourceGovernanceRecord",
        "SourceGovernanceRecord:v1:sha256:3737b8bae599956ed4738a527a89890b9f74c0b316900f8b49a5bb4695f7a0c1",
        ROOT / "official-runs" / "task04" / "a1-k1-materialization-evidence"
        / "repair-20261001T075732Z" / "k1-source-governance.json",
    ),
    "k1_freshness": (
        "KnowledgeFreshnessPolicy",
        "KnowledgeFreshnessPolicy:v1:sha256:0d33089e064fc58de96eb0c32789e9382fd2e26d213932cdf370b12b1ec6d3a5",
        ROOT / "official-runs" / "task04" / "a1-k1-materialization-evidence"
        / "repair-20261001T075732Z" / "k1-freshness-policy.json",
    ),
    "k1_provenance": (
        "KnowledgeProvenanceManifest",
        "KnowledgeProvenanceManifest:v1:sha256:199176ab51188a95cc9e10a05298b71024d2e194140538a6c3aec1050b70a61d",
        ROOT / "official-runs" / "task04" / "a1-k1-materialization-evidence"
        / "repair-20261001T075732Z" / "k1-provenance-v2.json",
    ),
    "k1_record_set": (
        "CanonicalKnowledgeRecordSet",
        "CanonicalKnowledgeRecordSet:v1:sha256:e6a347de462242f6ef70684e33be3bc16d1d11b7e3ced00271e0363ecbbefe5c",
        ROOT / "official-runs" / "task04" / "a1-k1-materialization-evidence"
        / "repair-20261001T075732Z" / "k1-record-set-v2.json",
    ),
    "k2b_governance": (
        "SourceGovernanceRecord",
        "SourceGovernanceRecord:v1:sha256:06c0c3e63404fff1f0a96fec0a264c46b1429a21defaffc5556fb00a0385897c",
        ROOT / "official-runs" / "task04" / "f-e5"
        / "official-run-20261001T102529Z-FE5-A1-CURRENT-01" / "k2b-source-governance.json",
    ),
    "k2b_freshness": (
        "KnowledgeFreshnessPolicy",
        "KnowledgeFreshnessPolicy:v1:sha256:c509e8343debf97a6295d0a8ed56255d69f724346c2ac20b2955b891614e4f09",
        ROOT / "official-runs" / "task04" / "f-e5"
        / "official-run-20261001T102529Z-FE5-A1-CURRENT-01" / "k2b-freshness-policy.json",
    ),
    "k2b_provenance": (
        "KnowledgeProvenanceManifest",
        "KnowledgeProvenanceManifest:v1:sha256:4638e78d5b85df2247ca7f3e0fbbab7326c9ddbbff719dbe3b9e2468a634627b",
        ROOT / "official-runs" / "task04" / "f-e5"
        / "official-run-20261001T102529Z-FE5-A1-CURRENT-01" / "k2b-provenance.json",
    ),
    "k3_rule_set": (
        "K3PortalRuleSet",
        "K3PortalRuleSet:v1:sha256:93ea1f384efe7d1dbbc9c513d09d9e62bdddd9448c0ee070423bc4f54176ed1a",
        ROOT / "official-runs" / "task04" / "f-e3"
        / "official-run-20261001T082752Z-FE3-A1" / "k3-portal-rule-set.json",
    ),
    "k3_provenance": (
        "KnowledgeProvenanceManifest",
        "KnowledgeProvenanceManifest:v1:sha256:ddf14f16eac6a6840e299fde11aafe9489d6bb075e04c3d09d4205e4bd197d15",
        ROOT / "official-runs" / "task04" / "f-e3"
        / "official-run-20261001T082752Z-FE3-A1" / "k3-internal-provenance.json",
    ),
    "k4_governance": (
        "SourceGovernanceRecord",
        "SourceGovernanceRecord:v1:sha256:5f0a3777a274daa4acedec11d29da34bc1fbe1f23e593188fcf8b0d03adf8125",
        ROOT / "official-runs" / "task04" / "f-e4"
        / "official-run-20261001T101057Z-FE4-A1-K4-REFRESH-R2" / "k4-source-governance.json",
    ),
    "k4_freshness": (
        "KnowledgeFreshnessPolicy",
        "KnowledgeFreshnessPolicy:v1:sha256:9a3a58d72dfb660b9a639b7558424cd55d213f8306e586c1b263aa4cda0d3df5",
        ROOT / "official-runs" / "task04" / "f-e4"
        / "official-run-20261001T101057Z-FE4-A1-K4-REFRESH-R2" / "k4-freshness-policy.json",
    ),
    "k4_provenance": (
        "KnowledgeProvenanceManifest",
        "KnowledgeProvenanceManifest:v1:sha256:68c84447525d42946a5a49b42ea9a82093f4da7ff8e8311843e229b444adeb49",
        ROOT / "official-runs" / "task04" / "f-e4"
        / "official-run-20261001T101057Z-FE4-A1-K4-REFRESH-R2" / "k4-provenance-refreshed.json",
    ),
    "k4_record_set": (
        "CanonicalKnowledgeRecordSet",
        "CanonicalKnowledgeRecordSet:v1:sha256:689f61da6cc8ace5a89677688b685f2a4d479d89bc9582239407d2d42e83536e",
        ROOT / "official-runs" / "task04" / "f-e4"
        / "official-run-20261001T101057Z-FE4-A1-K4-REFRESH-R2" / "k4-record-set-refreshed.json",
    ),
    "knowledge_bundle": (
        "KnowledgeBundle",
        EXACT_IDS["knowledge_bundle"],
        ROOT / "official-runs" / "task04" / "f-e7"
        / "predecision-build-20261001T103557Z-FE7-A1-01" / "knowledge-bundle.json",
    ),
    "evidence_adapter_contract_set": (
        "EvidenceAdapterContractSet",
        EXACT_IDS["evidence_adapter_contract_set"],
        ROOT / "official-runs" / "task04" / "f-f1"
        / "official-run-20261001T105634Z-FF1-A1-01" / "evidence-adapter-contract-set-a1.json",
    ),
    "classification_policy": (
        "ClassificationPolicy",
        EXACT_IDS["classification_policy"],
        ROOT / "official-runs" / "task04" / "f-f2"
        / "official-run-20261001T111321Z-FF2-A1-02" / "classification-policy-a1.json",
    ),
}
EXPECTED_K2B_RECORD_SET_ID = (
    "CanonicalKnowledgeRecordSet:v1:sha256:"
    "6c863319fa9260ea76ac2b73209b5c4a3e5736e24ee71930a24a663467eb6834"
)
_A1_OVERLAY: dict[str, Any] = {}
_A1_OVERLAY_SOURCES: dict[str, dict[str, str]] = {}


class Blocked(RuntimeError):
    def __init__(self, code: str, detail: str = ""):
        self.code, self.detail = code, detail
        super().__init__(f"{code}: {detail}" if detail else code)


class SemanticFailure(ValueError):
    def __init__(self, code: str, detail: str = ""):
        self.code, self.detail = code, detail
        super().__init__(f"{code}: {detail}" if detail else code)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ref(content: Any) -> dict[str, str]:
    return {"artifact_id": content.artifact_id, "content_sha256": content.content_sha256}


def document(content: Any) -> dict[str, Any]:
    return {"artifact_type": content.artifact_type,
            "artifact_schema_version": content.artifact_schema_version,
            "artifact_id": content.artifact_id,
            "content_sha256": content.content_sha256,
            "semantic_payload": content.semantic_payload}


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                       separators=(",", ":")) + "\n").encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.write_bytes(json_bytes(value))


def _pinned_module(path: Path, digest: str, name: str):
    if not path.is_file() or sha256(path) != digest:
        raise Blocked("BLOCKED_HARDENED_HELPER_CHANGED", path.name)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise Blocked("BLOCKED_HARDENED_HELPER_CHANGED", path.name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def t01():
    global _HELPER
    if not T01_HELPER.is_file() or sha256(T01_HELPER) != T01_SHA256:
        raise Blocked("BLOCKED_HARDENED_HELPER_CHANGED", "T-01")
    if _HELPER is None:
        _HELPER = _pinned_module(T01_HELPER, T01_SHA256, "task04_t06a_t01")
    return _HELPER


def t06():
    global _T06
    if not T06_RUNNER.is_file() or sha256(T06_RUNNER) != T06_SHA256:
        raise Blocked("BLOCKED_HARDENED_HELPER_CHANGED", "T-06")
    if _T06 is None:
        _T06 = _pinned_module(T06_RUNNER, T06_SHA256, "task04_t06a_t06")
    return _T06


def candidate_module(repo: Path, name: str):
    module = importlib.import_module(name)
    if not Path(module.__file__).resolve(strict=True).is_relative_to(repo):
        raise Blocked("BLOCKED_CANDIDATE_IDENTITY", name)
    return module


def load_api(repo: Path) -> SimpleNamespace:
    base = t06().load_api(repo)
    extra = {key: candidate_module(repo, name) for key, name in {
        "graph": "app.device_fingerprint.artifact_dependency_graph",
        "policy": "app.device_fingerprint.classification_policy",
        "taxonomy": "app.device_fingerprint.taxonomy_artifacts",
        "request": "app.device_fingerprint.classification_request",
        "origin_admission": "app.device_fingerprint.foundation_admission_artifacts",
        "k2b": "app.device_fingerprint.k2b_p0f_import",
        "knowledge_artifacts": "app.device_fingerprint.knowledge_artifacts",
        "runtime_fixture": "app.device_fingerprint.ff5_runtime_profile_atomicity",
    }.items()}
    return SimpleNamespace(**vars(base), **extra)


def _content_from_file(path: Path, api: SimpleNamespace, builder, expected_id: str | None):
    if not path.is_file():
        raise Blocked("BLOCKED_T06_INPUT_MISSING", path.name)
    try:
        raw = path.read_bytes()
        value = api.artifact.decode_artifact_json(raw.decode("utf-8"))
        if set(value) != {"artifact_type", "artifact_schema_version", "artifact_id",
                          "content_sha256", "semantic_payload"}:
            raise ValueError("document shape")
        built = builder(value["semantic_payload"])
        canonical = api.artifact.canonical_artifact_json(value)
        if (document(built) != value or
                (expected_id is not None and built.artifact_id != expected_id) or
                raw not in (canonical, canonical + b"\n")):
            raise ValueError("noncanonical or wrong identity")
        return built
    except Blocked:
        raise
    except Exception as exc:
        raise SemanticFailure("T06_ARTIFACT_INVALID", f"{path.name}:{type(exc).__name__}:{exc}") from exc



def _retained_artifact_from_file(
    path: Path,
    api: SimpleNamespace,
    artifact_type: str,
    expected_id: str,
):
    if not path.is_file():
        raise Blocked("BLOCKED_A1_OVERLAY", "missing:" + str(path))
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if set(value) != {
            "artifact_type",
            "artifact_schema_version",
            "artifact_id",
            "content_sha256",
            "semantic_payload",
        }:
            raise ValueError("document shape")
        if value["artifact_type"] != artifact_type or value["artifact_schema_version"] != 1:
            raise ValueError("artifact type/schema")
        built = api.artifact.make_artifact_content(artifact_type, value["semantic_payload"])
        if (
            document(built) != value
            or built.artifact_id != expected_id
            or built.content_sha256 != value["content_sha256"]
        ):
            raise ValueError("artifact identity/digest")
        return built
    except Blocked:
        raise
    except Exception as exc:
        raise Blocked(
            "BLOCKED_A1_OVERLAY",
            path.name + ":" + type(exc).__name__ + ":" + str(exc)[:200],
        ) from exc


def load_a1_overlay(api: SimpleNamespace) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
    overlay: dict[str, Any] = {}
    sources: dict[str, dict[str, str]] = {}

    for role, (artifact_type, expected_id, path) in A1_ARTIFACT_SPECS.items():
        content = _retained_artifact_from_file(
            path,
            api,
            artifact_type,
            expected_id,
        )
        overlay[content.artifact_id] = content
        sources[content.artifact_id] = {
            "role": role,
            "source": str(path.resolve()),
            "file_sha256": sha256(path),
        }

    if not P0F_PATH.is_file() or sha256(P0F_PATH) != P0F_SHA256:
        raise Blocked("BLOCKED_A1_OVERLAY", "p0f source identity")
    provenance = overlay[A1_ARTIFACT_SPECS["k2b_provenance"][1]]
    try:
        imported = api.k2b.import_p0f_k2b_bytes(
            P0F_PATH.read_bytes(),
            api.artifact.ArtifactRef(
                provenance.artifact_id,
                provenance.content_sha256,
            ),
        )
        record_set = imported.record_set
    except Exception as exc:
        raise Blocked("BLOCKED_A1_OVERLAY", f"k2b rebuild:{type(exc).__name__}") from exc

    if record_set.artifact_id != EXPECTED_K2B_RECORD_SET_ID:
        raise Blocked(
            "BLOCKED_A1_OVERLAY",
            "k2b exact identity mismatch:" + record_set.artifact_id,
        )
    overlay[record_set.artifact_id] = record_set
    sources[record_set.artifact_id] = {
        "role": "k2b_record_set",
        "source": "DETERMINISTIC_REBUILD:" + str(P0F_PATH.resolve()),
        "file_sha256": P0F_SHA256,
    }

    bundle = overlay[EXACT_IDS["knowledge_bundle"]]
    direct_required = {
        bundle.semantic_payload["k1_record_set"]["artifact_id"],
        bundle.semantic_payload["k2b_record_set"]["artifact_id"],
        bundle.semantic_payload["k3_portal_rule_set"]["artifact_id"],
        bundle.semantic_payload["k4_record_set"]["artifact_id"],
        *[row["artifact_id"] for row in bundle.semantic_payload["knowledge_provenance_manifests"]],
        *[row["artifact_id"] for row in bundle.semantic_payload["source_governance_records"]],
        *[row["artifact_id"] for row in bundle.semantic_payload["knowledge_freshness_policies"]],
    }
    missing = sorted(direct_required.difference(overlay))
    if missing:
        raise Blocked("BLOCKED_A1_OVERLAY", "missing bundle direct deps:" + ",".join(missing))
    return overlay, sources


def verify_t06_input(run_dir: Path, api: SimpleNamespace, *, allow_nonpass: bool = False):
    manifest = _content_from_file(
        run_dir / "t06-manifest.json", api,
        lambda payload: api.artifact.make_artifact_content("ClassifierArtifactManifest", payload),
        T06_MANIFEST_ID)
    result = _content_from_file(run_dir / "t06-gate-result-manifest.json", api,
                                api.gate_result.make_gate_result_manifest, None)
    payload = result.semantic_payload
    if payload["status"] != "PASS":
        if (payload["gate_id"] != "T-06" or
                payload["gate_contract_version"] != "R14-T-06-v1" or
                payload["candidate_repository_commit_sha"] != EXPECTED_COMMIT or
                payload["candidate_repository_tree_sha"] != EXPECTED_TREE):
            raise SemanticFailure("T06_RESULT_MISMATCH")
        if allow_nonpass:
            return manifest, result
        raise SemanticFailure("T06_NOT_PASS")
    if result.artifact_id != T06_RESULT_ID:
        raise SemanticFailure("T06_RESULT_MISMATCH", "exact accepted result identity")
    if (payload["gate_id"] != "T-06" or payload["gate_contract_version"] != "R14-T-06-v1"
            or payload["candidate_repository_commit_sha"] != EXPECTED_COMMIT
            or payload["candidate_repository_tree_sha"] != EXPECTED_TREE
            or payload["output_artifact_refs"] != [ref(manifest)]):
        raise SemanticFailure("T06_RESULT_MISMATCH")
    try:
        t06().verify_manifest_shape(api, manifest.semantic_payload)
        for evidence in payload["retained_evidence_refs"]:
            name = evidence["path_or_reference"]
            if (not isinstance(name, str) or Path(name).name != name or
                    sha256(run_dir / name) != evidence["file_sha256"]):
                raise ValueError("T-06 evidence digest")
    except Exception as exc:
        raise SemanticFailure("T06_RESULT_MISMATCH", type(exc).__name__) from exc
    return manifest, result


def resolve_exact(connection: sqlite3.Connection, api: SimpleNamespace, field: str):
    artifact_id = EXACT_IDS[field]
    if artifact_id in _A1_OVERLAY:
        content = _A1_OVERLAY[artifact_id]
    else:
        content = t01()._load_artifact(
            connection, api, artifact_id.split(":", 1)[0], artifact_id.rsplit(":", 1)[1]
        )
    if content.artifact_id != artifact_id:
        raise Blocked("BLOCKED_FOUNDATION_LINEAGE", field)
    return content


def resolve_dependency(connection: sqlite3.Connection, api: SimpleNamespace,
                       reference: dict[str, str]):
    artifact_id = reference["artifact_id"]
    content = _A1_OVERLAY.get(artifact_id)
    if content is not None:
        if content.content_sha256 != reference["content_sha256"]:
            raise ValueError("A1 overlay digest mismatch")
        return content
    return t01()._resolve_artifact(connection, api, reference)


def profile_version(api: SimpleNamespace) -> int:
    # Resolve from executable candidate fixture, not a gate-invented compatibility table.
    try:
        candidate = api.runtime_fixture._Fixture
        import inspect
        source = inspect.getsource(candidate)
        if '"classification_runtime_profile_contract_version": 1' not in source:
            raise ValueError("candidate profile version not frozen")
        return PROFILE_VERSION
    except Exception as exc:
        raise Blocked("BLOCKED_IMPLEMENTATION_IDENTITY_UNRESOLVED",
                      "classification_runtime_profile_contract_version") from exc


def build_profile(api: SimpleNamespace, contents: dict[str, Any], *, reverse: bool = False):
    fields = ["foundation_runtime_profile", "knowledge_bundle", "classification_policy",
              "evidence_adapter_contract_set", "classifier_artifact_manifest"]
    if reverse:
        fields.reverse()
    payload = {"classification_runtime_profile_contract_version": profile_version(api)}
    payload.update((field, ref(contents[field])) for field in fields)
    profile = api.profiles.make_classification_runtime_profile(payload)
    if set(profile.semantic_payload) != set(fields) | {"classification_runtime_profile_contract_version"}:
        raise SemanticFailure("PROFILE_CLOSED_SHAPE")
    return profile


def _check(check_id: str, inputs: list[dict[str, str]], observed: dict[str, Any], operation):
    try:
        operation()
        return {"check_id": check_id, "status": "PASS", "input_refs": inputs,
                "observed_values": observed, "failure_code": None, "failure_detail": None}
    except Exception as exc:
        return {"check_id": check_id, "status": "FAIL", "input_refs": inputs,
                "observed_values": observed, "failure_code": f"{check_id}_MISMATCH",
                "failure_detail": f"{type(exc).__name__}: {str(exc)[:300]}"}


def _require(value: bool, reason: str) -> None:
    if not value:
        raise ValueError(reason)


def compatibility(connection: sqlite3.Connection, api: SimpleNamespace,
                  contents: dict[str, Any], foundation: Any) -> list[dict[str, Any]]:
    bundle = contents["knowledge_bundle"]
    policy = contents["classification_policy"]
    adapter = contents["evidence_adapter_contract_set"]
    classifier = contents["classifier_artifact_manifest"]
    f_profile = contents["foundation_runtime_profile"]
    bp, pp, ap, cp, fp = (item.semantic_payload for item in
                           (bundle, policy, adapter, classifier, f_profile))
    resolve = lambda value: resolve_dependency(connection, api, value)
    tax = resolve(bp["classification_taxonomy"])
    alias = resolve(bp["alias_mapping"])
    registry = resolve(fp["evidence_schema_registry_contract"])
    origin = resolve(fp["origin_runtime_admission"])
    k2a = resolve(foundation.manifest.semantic_payload["k2a_conformance_package"])
    disposition = resolve(foundation.manifest.semantic_payload["portal_headers_v2_capability_disposition"])
    source = contents.values()
    refs = [ref(value) for value in source]

    def current_admitted():
        records = {
            "k1_record_set": resolve(bp["k1_record_set"]),
            "k3_portal_rule_set": resolve(bp["k3_portal_rule_set"]),
            "k4_record_set": resolve(bp["k4_record_set"]),
        }
        return {
            "adapter": adapter,
            "knowledge": bundle,
            "k2a": k2a,
            "disposition": disposition,
            "registry": registry,
            **records,
        }

    rows = []
    rows.append(_check("C01", [ref(bundle), ref(policy), ref(tax)],
        {"bundle_taxonomy": bp["classification_taxonomy"], "policy_taxonomy": pp["classification_taxonomy"]},
        lambda: _require(bp["classification_taxonomy"] == pp["classification_taxonomy"] == ref(tax),
                         "taxonomy identity")))
    rows.append(_check("C02", [ref(bundle), ref(policy), ref(alias)],
        {"bundle_alias": bp["alias_mapping"], "policy_alias": pp["alias_mapping"]},
        lambda: (_require(bp["alias_mapping"] == pp["alias_mapping"] == ref(alias), "alias identity"),
                 api.taxonomy.validate_alias_mapping_against_taxonomy(tax, alias),
                 api.policy.validate_classification_policy_dependencies(policy,
                     classification_taxonomy=tax, alias_mapping=alias,
                     evidence_adapter_contract_set=adapter))))
    rows.append(_check("C03", [ref(policy), ref(adapter)],
        {"policy_adapter": pp["evidence_adapter_contract_set"], "profile_adapter": ref(adapter)},
        lambda: _require(pp["evidence_adapter_contract_set"] == ref(adapter), "policy/adapter identity")))
    def c04():
        admitted = current_admitted()
        expected, _ = t06().build_inventory(api, admitted)
        _require(cp["adapter_implementation_identities"] == expected, "classifier adapter coverage")
        _require(api.artifact.make_artifact_content("ClassifierArtifactManifest", cp) == classifier,
                 "classifier canonical identity")
    rows.append(_check("C04", [ref(adapter), ref(classifier), ref(registry)],
        {"adapter_count": len(ap["adapter_entries"]),
         "implementation_count": len(cp["adapter_implementation_identities"])}, c04))
    rows.append(_check("C05", [ref(f_profile), ref(classifier)],
        {"foundation_snapshot_contract": fp["snapshot_contract_version"],
         "classifier_snapshot_contract": cp["snapshot_contract_version"]},
        lambda: _require(fp["snapshot_contract_version"] == cp["snapshot_contract_version"],
                         "snapshot contract version")))
    def c06():
        admitted = current_admitted()
        _require(admitted["registry"] == registry and admitted["adapter"] == adapter,
                 "candidate adapter/registry identity")
        _require(
            api.adapter.validate_evidence_adapter_contract_set_dependencies(
                adapter,
                evidence_schema_registry=registry,
                capability_disposition=disposition,
                k2a_conformance_package=k2a,
                k1_record_set=admitted["k1_record_set"],
                k3_portal_rule_set=admitted["k3_portal_rule_set"],
                k4_record_set=admitted["k4_record_set"],
            ),
            "candidate adapter dependencies",
        )
    rows.append(_check("C06", [ref(f_profile), ref(registry), ref(adapter)],
        {"foundation_registry": fp["evidence_schema_registry_contract"],
         "adapter_registry": ap["evidence_schema_registry"]}, c06))
    def c07():
        _require(cp["k2a_matcher_implementation_version"] == api.p0f.MATCHER_CONTRACT,
                 "K2A matcher version")
        _require(k2a.semantic_payload["matcher_implementation_contract_version"] ==
                 cp["k2a_matcher_implementation_version"], "K2A package version")
        record_set = resolve(bp["k2b_record_set"])
        _require(api.knowledge_artifacts.make_canonical_k2b_record_set(
            record_set.semantic_payload) == record_set and
            bp["k2b_record_set"] == ref(record_set), "K2B record set")
        provenance_ref = record_set.semantic_payload["knowledge_provenance"]
        provenance = resolve(provenance_ref)
        _require(provenance_ref in bp["knowledge_provenance_manifests"] and
                 provenance_ref == ref(provenance) and
                 api.knowledge_artifacts.make_external_knowledge_provenance_manifest(
                     provenance.semantic_payload) == provenance and
                 provenance.semantic_payload["source_governance_record"] in
                     bp["source_governance_records"] and
                 provenance.semantic_payload["knowledge_freshness_policy"] in
                     bp["knowledge_freshness_policies"], "K2B provenance")
        _require(api.k2b.ACCEPTED_P0F_AUDIT.admitted_canonical_records > 0, "K2B audit")
    rows.append(_check("C07", [ref(classifier), ref(k2a), ref(bundle)],
        {"classifier_k2a_version": cp["k2a_matcher_implementation_version"],
         "k2b_record_set": bp["k2b_record_set"]}, c07))
    def c08():
        admitted = current_admitted()
        versions = t06()._version_sources(api, foundation, admitted)
        _require(fp["foundation_profile_contract_version"] == 1 and
                 profile_version(api) == 1 and
                 bp["bundle_schema_version"] == 1 and
                 pp["policy_schema_version"] == 1 and
                 cp["classification_result_schema_version"] == versions[
                     "classification_result_schema_version"] and
                 cp["snapshot_contract_version"] == versions["snapshot_contract_version"] and
                 cp["k2a_matcher_implementation_version"] == versions[
                     "k2a_matcher_implementation_version"], "candidate contract versions")
        _require(callable(api.request.make_classification_request_manifest) and
                 callable(api.fusion.fuse_classification), "request/classification contracts")
    rows.append(_check("C08", refs, {"foundation_profile_contract_version": fp[
        "foundation_profile_contract_version"], "classification_result_schema_version": cp[
        "classification_result_schema_version"]}, c08))
    def c09():
        _require(api.origin_admission.make_origin_runtime_admission(origin.semantic_payload) == origin,
                 "OriginRuntimeAdmission contract")
        op = origin.semantic_payload
        if op["tcp_state"] == "ENABLED":
            ttl = resolve(op["ttl_capture_placement_proof"])
            _require(op["tcp_reason_code"] == "TTL_PROOF_VALID" and
                     ttl == resolve(fp["ttl_capture_placement_proof"]), "enabled TCP TTL")
        else:
            _require(op["tcp_state"] == "DISABLED" and op["tcp_reason_code"] in
                     {"TTL_PROOF_INVALID", "PROFILE_POLICY_DISABLED"}, "disabled TCP")
        _require(callable(api.origin.DeviceFingerprintOriginAssessmentBuilder.build),
                 "candidate origin semantics")
    rows.append(_check("C09", [ref(f_profile), ref(origin)],
        {"tcp_state": origin.semantic_payload.get("tcp_state"),
         "tcp_reason_code": origin.semantic_payload.get("tcp_reason_code")}, c09))
    return rows


def concrete_graph(connection: sqlite3.Connection, api: SimpleNamespace, root: Any,
                   external: Any) -> dict[str, Any]:
    by_id = {root.artifact_id: root, external.artifact_id: external}
    pending = [root]
    while pending:
        item = pending.pop()
        for dep in api.graph.extract_direct_artifact_refs(item):
            existing = by_id.get(dep.artifact_id)
            if existing is None:
                if dep.artifact_id == external.artifact_id:
                    existing = external
                else:
                    try:
                        existing = resolve_dependency(connection, api, dep.as_dict())
                    except Exception as exc:
                        raise SemanticFailure("DEPENDENCY_MISSING_OR_DIGEST", dep.artifact_id) from exc
                by_id[existing.artifact_id] = existing
                pending.append(existing)
            if existing.content_sha256 != dep.content_sha256:
                raise SemanticFailure("DEPENDENCY_DIGEST_MISMATCH", dep.artifact_id)
    nodes = api.graph.build_concrete_artifact_graph(by_id.values())
    analysis = api.graph.analyze_artifact_dependency_graph(nodes)
    if any(node.artifact_type == "Task04AcceptanceManifest" for node in analysis.nodes):
        raise SemanticFailure("ACCEPTANCE_BACK_REFERENCE")
    return {"root_profile_ref": ref(root), "node_count": len(analysis.nodes),
            "edge_count": len(analysis.edges), "nodes": [
                {"node_id": node.node_id, "artifact_type": node.artifact_type,
                 "node_kind": node.node_kind, "direct_dependency_ids": list(node.direct_dependency_ids)}
                for node in analysis.nodes],
            "edges": [list(edge) for edge in analysis.edges],
            "topological_order": list(analysis.topological_order), "cycle_witness": None}


def _evidence_refs(run_dir: Path) -> list[dict[str, str]]:
    return [{"evidence_label": name.removesuffix(".json"), "file_sha256": sha256(run_dir / name),
             "media_type": "application/json", "path_or_reference": name}
            for name in ("t06a-compatibility-report.json", "t06a-dependency-graph.json",
                         "t06a-execution-evidence.json")]


def _formal(run_dir: Path, api: SimpleNamespace, inputs: dict[str, Any],
            profile: Any | None, runner_sha: str):
    identity = {"execution_id": str(uuid.uuid4()), "executor_kind": "TECHLEAD_GATE_TOOL",
                "repository_commit_sha": EXPECTED_COMMIT, "repository_tree_sha": EXPECTED_TREE,
                "procedure_or_test_suite_id": PROCEDURE,
                "environment_identity": t01()._environment_identity(),
                "execution_artifact_sha256": runner_sha}
    evidence = _evidence_refs(run_dir)
    formal_inputs = [ref(inputs[key]) for key in (
        "t06_gate_result", "foundation_runtime_profile", "knowledge_bundle",
        "classification_policy", "evidence_adapter_contract_set", "classifier_artifact_manifest")]
    proof = None
    if profile is not None:
        proof = api.gate_proof.make_gate_proof_artifact({
            "proof_kind": PROOF_KIND, "source_gate_id": GATE_ID,
            "candidate_repository_commit_sha": EXPECTED_COMMIT,
            "candidate_repository_tree_sha": EXPECTED_TREE,
            "input_artifact_refs": formal_inputs,
            "procedure_or_test_suite_id": PROCEDURE,
            "proof_execution_identity": identity,
            "canonical_result_summary": f"profile={profile.artifact_id};C01-C09=PASS;graph=ACYCLIC",
            "retained_evidence_refs": evidence})
    result = api.gate_result.make_gate_result_manifest({
        "gate_id": GATE_ID, "gate_contract_version": GATE_CONTRACT,
        "status": "PASS" if profile is not None else "FAIL",
        "candidate_repository_commit_sha": EXPECTED_COMMIT,
        "candidate_repository_tree_sha": EXPECTED_TREE,
        "input_artifact_refs": formal_inputs,
        "output_artifact_refs": [ref(profile), ref(proof)] if profile is not None else [],
        "retained_evidence_refs": evidence,
        "proof_execution_identity": identity,
        "trusted_time_inputs": {"foundation_knowledge_evaluation_at_utc": None,
                                "foundation_admission_evaluation_at_utc": None,
                                "knowledge_evaluation_at_utc": None},
        "decision_record_refs": []})
    if proof is not None:
        t01()._write_and_roundtrip(run_dir / "t06a-gate-proof-artifact.json", proof,
                                   api.gate_proof.make_gate_proof_artifact,
                                   api.artifact.canonical_artifact_json)
    t01()._write_and_roundtrip(run_dir / "t06a-gate-result-manifest.json", result,
                               api.gate_result.make_gate_result_manifest,
                               api.artifact.canonical_artifact_json)
    return proof, result


def _blocked(run_dir: Path | None, code: str, detail: str = "") -> int:
    if run_dir is not None:
        for name in ("t06a-classification-runtime-profile.json", "t06a-gate-proof-artifact.json",
                     "t06a-gate-result-manifest.json"):
            (run_dir / name).unlink(missing_ok=True)
        (run_dir / "t06a-summary.txt").write_text(
            f"GATE_EXECUTION_STATUS={code}\nUNRESOLVED={detail}\n"
            "PROFILE=NONE\nGATE_PROOF_ARTIFACT=NONE\nGATE_RESULT_MANIFEST=NONE\n",
            encoding="utf-8")
    print(f"GATE_EXECUTION_STATUS={code}")
    return 2


def run_gate(repo: Path, foundation_db: Path, t06_run_dir: Path, output_dir: Path) -> int:
    run_dir = None
    connection = None
    runner = Path(__file__).resolve()
    runner_sha = sha256(runner)
    try:
        helper = t01()
        t06()
        repo = repo.resolve(strict=True)
        foundation_db = foundation_db.resolve(strict=True)
        t06_run_dir = t06_run_dir.resolve(strict=True)
        output_dir = output_dir.resolve()
        if (output_dir.is_relative_to(repo) or output_dir.is_relative_to(t06_run_dir)
                or output_dir == foundation_db.parent or
                output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir()))):
            raise Blocked("BLOCKED_OUTPUT_DIR")
        output_dir.mkdir(parents=True, exist_ok=True)
        run_dir = output_dir / str(uuid.uuid4())
        run_dir.mkdir(exist_ok=False)
        if sha256(runner) != runner_sha:
            raise Blocked("BLOCKED_RUNNER_CHANGED")
        helper.verify_repository(repo)
        before_repo = helper.repository_filesystem_fingerprint(repo)
        before_db = sha256(foundation_db)
        api = load_api(repo)
        _A1_OVERLAY.clear()
        _A1_OVERLAY_SOURCES.clear()
        overlay, overlay_sources = load_a1_overlay(api)
        _A1_OVERLAY.update(overlay)
        _A1_OVERLAY_SOURCES.update(overlay_sources)
        connection = helper.open_foundation_read_only(foundation_db)
        foundation = helper.verify_foundation(connection, api)
        try:
            classifier, t06_result = verify_t06_input(t06_run_dir, api, allow_nonpass=True)
        except Blocked:
            raise
        except SemanticFailure as exc:
            if exc.code == "T06_ARTIFACT_INVALID":
                raise Blocked("BLOCKED_T06_INPUT_INVALID", exc.detail) from exc
            raise
        contents = {field: resolve_exact(connection, api, field) for field in EXACT_IDS}
        if contents["foundation_runtime_profile"] != foundation.profile:
            raise Blocked("BLOCKED_FOUNDATION_LINEAGE", "profile identity")
        contents.update(classifier_artifact_manifest=classifier, t06_gate_result=t06_result)
        profile = None
        graph = {"root_profile_ref": None, "node_count": 0, "edge_count": 0,
                 "nodes": [], "edges": [], "topological_order": [], "cycle_witness": None}
        report = []
        failure = None
        failure_detail = None
        try:
            if t06_result.semantic_payload["status"] != "PASS":
                raise SemanticFailure("T06_NOT_PASS")
            first = build_profile(api, contents)
            second = build_profile(api, contents, reverse=True)
            if (first != second or api.artifact.canonical_artifact_json(document(first)) !=
                    api.artifact.canonical_artifact_json(document(second))):
                raise SemanticFailure("PROFILE_NONDETERMINISTIC")
            report = compatibility(connection, api, contents, foundation)
            if any(row["status"] != "PASS" for row in report):
                raise SemanticFailure("COMPATIBILITY_MISMATCH")
            graph = concrete_graph(connection, api, first, classifier)
            repeat = concrete_graph(connection, api, second, classifier)
            if graph != repeat:
                raise SemanticFailure("GRAPH_NONDETERMINISTIC")
            profile = first
        except Exception as exc:
            failure = exc.code if isinstance(exc, SemanticFailure) else type(exc).__name__
            failure_detail = str(exc)[:300]
            if isinstance(exc, api.graph.ArtifactDependencyGraphError):
                failure = exc.reason_code
                graph["cycle_witness"] = list(exc.cycle_witness) or None
        write_json(run_dir / "t06a-compatibility-report.json", {"checks": report,
                   "all_pass": len(report) == 9 and all(row["status"] == "PASS" for row in report),
                   "failure_code": failure, "failure_detail": failure_detail})
        write_json(run_dir / "t06a-dependency-graph.json", graph)
        write_json(run_dir / "t06a-execution-evidence.json", {
            "candidate_commit": EXPECTED_COMMIT, "candidate_tree": EXPECTED_TREE,
            "runner_sha256": runner_sha, "t01_helper_sha256": T01_SHA256,
            "t06_runner_sha256": T06_SHA256,
            "a1_immutable_overlay_sources": _A1_OVERLAY_SOURCES,
            "t06_gate_result": ref(t06_result), "classifier_artifact_manifest": ref(classifier),
            **{field: ref(contents[field]) for field in EXACT_IDS},
            "profile": ref(profile) if profile is not None else None,
            "compatibility_all_pass": profile is not None,
            "dependency_graph_acyclic": profile is not None,
            "no_acceptance_back_reference": profile is not None,
            "failure_code": failure})
        if profile is not None:
            helper._write_and_roundtrip(run_dir / "t06a-classification-runtime-profile.json",
                                        profile, api.profiles.make_classification_runtime_profile,
                                        api.artifact.canonical_artifact_json)
        if (sha256(runner) != runner_sha or sha256(T01_HELPER) != T01_SHA256 or
                sha256(T06_RUNNER) != T06_SHA256):
            raise Blocked("BLOCKED_RUNNER_CHANGED")
        helper._require_repository_unchanged(repo, before_repo)
        if sha256(foundation_db) != before_db:
            raise Blocked("BLOCKED_FOUNDATION_MUTATED")
        proof, result = _formal(run_dir, api, contents, profile, runner_sha)
        helper._require_repository_unchanged(repo, before_repo)
        if sha256(foundation_db) != before_db or sha256(runner) != runner_sha:
            raise Blocked("BLOCKED_EXECUTION_MUTATED")
        (run_dir / "t06a-summary.txt").write_text(
            f"GATE_EXECUTION_STATUS={'PASS' if profile is not None else 'FAIL'}\n"
            f"PROFILE={profile.artifact_id if profile is not None else 'NONE'}\n"
            f"GATE_PROOF_ARTIFACT={proof.artifact_id if proof is not None else 'NONE'}\n"
            f"GATE_RESULT_MANIFEST={result.artifact_id}\n", encoding="utf-8")
        print(f"GATE_EXECUTION_STATUS={'PASS' if profile is not None else 'FAIL'}")
        return 0 if profile is not None else 1
    except Blocked as exc:
        return _blocked(run_dir, exc.code, exc.detail)
    except Exception as exc:
        if "helper" in locals() and isinstance(exc, helper.Blocked):
            return _blocked(run_dir, exc.status)
        return _blocked(run_dir, "BLOCKED_EXECUTION_BASIS", type(exc).__name__)
    finally:
        if connection is not None:
            connection.rollback()
            connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--foundation-control-db", required=True, type=Path)
    parser.add_argument("--t06-run-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    return run_gate(args.repo, args.foundation_control_db, args.t06_run_dir, args.output_dir)


if __name__ == "__main__":
    raise SystemExit(main())