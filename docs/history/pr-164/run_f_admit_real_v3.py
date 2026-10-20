#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

EXPECTED_MAIN_COMMIT = "340e47ec7de3974ac328a7daf1b9936d0f7e5162"
EXPECTED_MAIN_TREE = "a05b1aae9ca84dee427f1a6a58efd38cd41ee48c"

EXACT = {
    "F-E5_GATE": "GateResultManifest:v1:sha256:b73b4c74189588a3457852dd7320c482a9b30f60c8cbdcff8f57843267b66124",
    "F-E7_GATE": "GateResultManifest:v1:sha256:7b9c66874cf9c6ddbb9cd60e09f4acf7f3ad736e69c872500b7041ecd727a7af",
    "KNOWLEDGE_BUNDLE": "KnowledgeBundle:v1:sha256:0fbdc70c2c25489a28d6446403e2facb7de6704f3a915af512b72cc9d0d10b3b",
    "TTL_PROOF": "TTLCapturePlacementProof:v1:sha256:c48ffafa3856c4708a35e644bb4cc2b468275af9790df579a366d7ac71fc0ca2",
    "TAXONOMY": "ClassificationTaxonomy:v1:sha256:399e2a337e7ebecb1bd7a9b21dff5e744c13be36313bc39f16832bc7a57a4d10",
    "ALIAS": "AliasMapping:v1:sha256:f1cdd7c9510c2a33bad99bd1ae15eaccd20fcb828a52e02533b9917fdfc2e228",
    "EACS": "EvidenceAdapterContractSet:v1:sha256:7cca6802ebc5839317643dcb584173b75d985477da687ab0d8fe5802b181f788",
    "CLASSIFICATION_POLICY": "ClassificationPolicy:v1:sha256:6341a9f9781ead1b1ab5ba2065b7eda6c0c77b4d8736db2eae6a04ef881daf3e",
    "RETENTION_POLICY": "ClassificationRetentionPolicy:v1:sha256:029c3534e076db6f7293c78e8a86c425b10c786d58713e77a077a19dfdda3e72",
    "PRODUCT_POLICY": "ProductValidationPolicy:v1:sha256:806779ca1844e55083a2c1c464cf8d94a9bdd0b2f97436d203b63fd03e81bea5",
    "FF5_PROOF": "GateProofArtifact:v1:sha256:0a097295fa65e6ba3ee95755670328aea4584712ae8d72829b6c04e1cac4f023",
    "FF5_GATE": "GateResultManifest:v1:sha256:77385a12e1e77a4a226320d39db4a4f0b90924e6b9a09cf19051732febc86ac7",
    "FF6_PROOF": "GateProofArtifact:v1:sha256:7b52b74baa2868505def90b2555a80b082ee4e2b27734a2292d5e3e002078896",
    "FA4_PROOF": "GateProofArtifact:v1:sha256:ae1dbca5d44be872d0ff1661c884b8dcde595a0257cadf7b45b697a36de2a9f6",
    "K2A_PACKAGE": "K2AConformancePackage:v1:sha256:bbe6fa22ac50e568ee4580faac4ad09f7301bb38f6af2ab2075b8adc39262328",
    "K2A_GOV_ARCHIVE": "SourceGovernanceRecord:v1:sha256:11af2d31c21c97c8a7df57bc4be0d491708aaa82081fd9129e35d0eb9ecd02ea",
    "K2A_GOV_CORPUS": "SourceGovernanceRecord:v1:sha256:13920c1f5bc09b17d0d500de30df2d8c295da8f38d340a4d016d294d9bf34c9b",
    "K2A_GOV_ORACLE": "SourceGovernanceRecord:v1:sha256:997614c80816e8130401a0d1f7ad1c72ac03834bbba311d973d92fa390289074",
}

MISSING_FORMAL_GATES = (
    "F-A1", "F-A2", "F-A3", "F-A4", "F-A5",
    "F-B0", "F-B1", "F-B2", "F-B3",
    "F-C1", "F-C2", "F-C3", "F-D1",
    "F-E1", "F-E2", "F-E3", "F-E4", "F-F1",
)

PR_BASIS = {
    "F-A1": [129], "F-A2": [129], "F-A3": [130], "F-A4": [149], "F-A5": [141],
    "F-B0": [143, 145], "F-B1": [144, 145], "F-B2": [146], "F-B3": [146],
    "F-C1": [131, 132, 133, 134, 135], "F-C2": [136, 147], "F-C3": [148],
    "F-D1": [138, 139, 140, 141],
    "F-E1": [150], "F-E2": [151], "F-E3": [152], "F-E4": [153], "F-F1": [157],
}

ACCEPTED_CLASSIFICATION_FOUNDATION_VALID_FROM_UTC = "2026-09-18T10:43:29.014Z"

def utc_ms() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())

def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")

def git(*args: str) -> str:
    p = subprocess.run(["git", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       text=True, check=False)
    if p.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{p.stderr.strip()}")
    return p.stdout.strip()

def iter_artifact_dicts(value: Any):
    if isinstance(value, dict):
        required = {"artifact_type", "artifact_schema_version", "artifact_id",
                    "content_sha256", "semantic_payload"}
        if required <= set(value):
            yield value
        for child in value.values():
            yield from iter_artifact_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_artifact_dicts(child)

def artifact_dict(content) -> dict[str, Any]:
    return {
        "artifact_type": content.artifact_type,
        "artifact_schema_version": content.artifact_schema_version,
        "artifact_id": content.artifact_id,
        "content_sha256": content.content_sha256,
        "semantic_payload": content.semantic_payload,
    }

def save_artifact(path: Path, content) -> None:
    write_json(path, artifact_dict(content))

def ref(content) -> dict[str, str]:
    from app.device_fingerprint.artifact_content import ArtifactRef
    return ArtifactRef(content.artifact_id, content.content_sha256).as_dict()

def main() -> int:
    repo = Path.cwd()
    if not (repo / "app" / "device_fingerprint").is_dir():
        print("F_ADMIT_REAL_STATUS=STOP")
        print("STOP_REASON=run_from_CaptivPortal_repository_root")
        return 2
    sys.path.insert(0, str(repo))

    # Exact accepted merged main. No tests and no code mutation.
    subprocess.run(["git", "fetch", "origin",
                    "refs/heads/main:refs/remotes/origin/main", "--quiet"], check=True)
    main_commit = git("rev-parse", "origin/main")
    main_tree = git("rev-parse", "origin/main^{tree}")
    head_tree = git("rev-parse", "HEAD^{tree}")
    if (main_commit, main_tree) != (EXPECTED_MAIN_COMMIT, EXPECTED_MAIN_TREE):
        print("F_ADMIT_REAL_STATUS=STOP")
        print(f"STOP_REASON=origin_main_changed:{main_commit}:{main_tree}")
        return 3
    if head_tree != EXPECTED_MAIN_TREE:
        print("F_ADMIT_REAL_STATUS=STOP")
        print(f"STOP_REASON=worktree_tree_not_accepted_main:{head_tree}")
        return 4
    if git("status", "--short"):
        print("F_ADMIT_REAL_STATUS=STOP")
        print("STOP_REASON=working_tree_not_clean")
        return 5

    from app.device_fingerprint.artifact_content import (
        ArtifactContent, ArtifactRef, make_artifact_content,
    )
    from app.device_fingerprint.artifact_dependency_graph import extract_direct_artifact_refs
    from app.device_fingerprint.classification_policy import (
        build_initial_classification_policy_v1,
    )
    from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore
    from app.device_fingerprint.evidence_adapter_contracts import (
        build_initial_evidence_adapter_contract_set_v1,
    )
    from app.device_fingerprint.f_admit_foundation import (
        InitialFoundationInputs, execute_initial_foundation_admission,
    )
    from app.device_fingerprint.foundation_admission_artifacts import (
        MANDATORY_PRE_ADMISSION_GATES, make_architecture_contract_reference,
    )
    from app.device_fingerprint.foundation_gate_artifacts import make_gate_result_manifest
    from app.device_fingerprint.foundation_schema_artifacts import build_foundation_schema_artifacts
    from app.device_fingerprint.gate_proof_artifacts import make_gate_proof_artifact
    from app.device_fingerprint.health_retention_contract import (
        final_source_health_policy, make_task01_health_retention_contract,
    )
    from app.device_fingerprint.k2a_conformance_artifacts import (
        build_k2a_conformance_package, build_k2a_source_governance_candidates,
    )
    from app.device_fingerprint.knowledge_bundle import KnowledgeBundleCandidate
    from app.device_fingerprint.source_health_emitter_contracts import (
        build_network_sensor_source_health_emitter_contract,
        build_periodic_portal_source_health_emitter_contract,
        build_portal_source_health_emitter_contract,
    )
    from app.device_fingerprint.taxonomy_artifacts import (
        build_alias_mapping_v1, build_classification_taxonomy_v1,
    )
    from research.device_fingerprint_fa4.finalization import (
        build_snapshot_performance_gate_proof,
    )

    artifact_root = Path(r"C:\CaptivPortal-Lab\artifacts")
    if not artifact_root.is_dir():
        raise RuntimeError("C:\\CaptivPortal-Lab\\artifacts is missing")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = artifact_root / f"f-admit-real-{stamp}"
    out.mkdir(parents=True, exist_ok=False)

    # Canonical artifact pool: only actual ArtifactContent bodies count.
    pool: dict[str, ArtifactContent] = {}
    source_paths: dict[str, set[str]] = defaultdict(set)

    def add(content: ArtifactContent, source: str) -> None:
        if not isinstance(content, ArtifactContent):
            raise RuntimeError("non-ArtifactContent")
        previous = pool.get(content.artifact_id)
        if previous is not None and previous != content:
            raise RuntimeError(f"artifact immutable conflict: {content.artifact_id}")
        pool[content.artifact_id] = content
        source_paths[content.artifact_id].add(source)

    for path in list(artifact_root.rglob("*.json")):
        if out in path.parents:
            continue
        try:
            if path.stat().st_size > 50 * 1024 * 1024:
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for row in iter_artifact_dicts(data):
            try:
                content = make_artifact_content(row["artifact_type"], row["semantic_payload"])
                if (row["artifact_schema_version"] != 1
                        or content.artifact_id != row["artifact_id"]
                        or content.content_sha256 != row["content_sha256"]):
                    continue
                add(content, str(path))
            except Exception:
                continue

    # Add deterministic current builders as non-historical fallback bodies.
    schema = build_foundation_schema_artifacts()
    for content in schema.values():
        add(content, "current-main:build_foundation_schema_artifacts")

    taxonomy = build_classification_taxonomy_v1()
    alias = build_alias_mapping_v1()
    add(taxonomy, "current-main:build_classification_taxonomy_v1")
    add(alias, "current-main:build_alias_mapping_v1")

    for content in (
        build_network_sensor_source_health_emitter_contract(),
        build_portal_source_health_emitter_contract(),
        build_periodic_portal_source_health_emitter_contract(),
    ):
        add(content, "current-main:source-health-emitter-builder")

    health_fallback = final_source_health_policy()
    add(health_fallback, "current-main:final_source_health_policy")
    retention_fallback = make_task01_health_retention_contract(
        health_fallback,
        retained_evidence_horizon_seconds=2_592_000,
        retained_health_horizon_seconds=2_592_600,
    )
    add(retention_fallback, "current-main:health-retention-builder")
    k2a_fallback = build_k2a_conformance_package()
    if k2a_fallback.artifact_id != EXACT["K2A_PACKAGE"]:
        raise RuntimeError("current K2A package identity differs from accepted PR #147")
    add(k2a_fallback, "current-main:build_k2a_conformance_package")
    k2a_governance_fallback = build_k2a_source_governance_candidates()
    expected_k2a_governance_ids = {
        EXACT["K2A_GOV_ARCHIVE"], EXACT["K2A_GOV_CORPUS"], EXACT["K2A_GOV_ORACLE"],
    }
    if {item.artifact_id for item in k2a_governance_fallback} != expected_k2a_governance_ids:
        raise RuntimeError("current K2A governance identities differ from accepted PR #147")
    for content in k2a_governance_fallback:
        add(content, "current-main:build_k2a_source_governance_candidates:accepted-PR147")

    eacs_fallback = build_initial_evidence_adapter_contract_set_v1(
        schema["EvidenceSchemaRegistryContract"])
    add(eacs_fallback, "current-main:build_initial_evidence_adapter_contract_set_v1")
    classification_fallback = build_initial_classification_policy_v1(
        taxonomy, alias, eacs_fallback)
    add(classification_fallback, "current-main:build_initial_classification_policy_v1")

    def require_id(aid: str) -> ArtifactContent:
        content = pool.get(aid)
        if content is None:
            raise RuntimeError(f"required accepted artifact body missing: {aid}")
        return content

    # Exact retained formal gates already present.
    fe5_gate = require_id(EXACT["F-E5_GATE"])
    fe7_gate = require_id(EXACT["F-E7_GATE"])
    ff5_gate = require_id(EXACT["FF5_GATE"])
    ff5_proof = require_id(EXACT["FF5_PROOF"])
    ff6_proof = require_id(EXACT["FF6_PROOF"])
    knowledge_bundle = require_id(EXACT["KNOWLEDGE_BUNDLE"])
    ttl_proof = require_id(EXACT["TTL_PROOF"])

    # Accepted F-F6 proof is the immutable inventory anchor for the pre-F-ADMIT
    # structural Foundation set. Historical proof INPUTS are not recursively
    # required by F-ADMIT, but their exact artifact identities safely identify
    # the already-accepted structural artifacts.
    ff6_inventory_ids = {
        ArtifactRef.from_dict(x).artifact_id
        for x in ff6_proof.semantic_payload["input_artifact_refs"]
    }

    def ff6_type(kind: str, *, many: bool = False):
        values = [
            pool[aid] for aid in sorted(ff6_inventory_ids)
            if aid in pool and pool[aid].artifact_type == kind
        ]
        if many:
            if not values:
                raise RuntimeError(f"no accepted F-F6 inventory artifacts of type {kind}")
            return tuple(values)
        if len(values) != 1:
            raise RuntimeError(
                f"expected exactly one accepted F-F6 {kind}, found {len(values)}: "
                + ",".join(x.artifact_id for x in values)
            )
        return values[0]

    def global_type(kind: str):
        values = [x for x in pool.values() if x.artifact_type == kind]
        if len(values) != 1:
            raise RuntimeError(
                f"expected unique {kind}, found {len(values)}: "
                + ",".join(x.artifact_id for x in values)
            )
        return values[0]

    def existing_proofs(kind: str, *, source_gate_id: str | None = None) -> list[ArtifactContent]:
        values = [
            x for x in pool.values()
            if x.artifact_type == "GateProofArtifact"
            and x.semantic_payload.get("proof_kind") == kind
            and (source_gate_id is None or x.semantic_payload.get("source_gate_id") == source_gate_id)
        ]
        return list({x.artifact_id: x for x in values}.values())

    architecture_candidates = [
        x for x in pool.values()
        if x.artifact_type == "ArchitectureContractReference"
        and x.semantic_payload.get("architecture_contract_name")
            == "DEVICE-FINGERPRINT-03A-R2 / TASK-04"
        and x.semantic_payload.get("architecture_revision") == "R14"
        and x.semantic_payload.get("architecture_status") == "FINAL"
    ]
    if len(architecture_candidates) != 1:
        raise RuntimeError(f"expected one R14 FINAL ArchitectureContractReference, found "
                           f"{len(architecture_candidates)}")
    architecture = architecture_candidates[0]
    if make_architecture_contract_reference(architecture.semantic_payload) != architecture:
        raise RuntimeError("R14 ArchitectureContractReference is noncanonical")

    # Structural accepted artifacts.
    schema_migration = ff6_type("Task01SchemaMigrationContract")
    watermark = ff6_type("Task01WatermarkReadContract")
    generation_recovery = ff6_type("Task01GenerationRecoveryContract")
    snapshot_content = ff6_type("SnapshotContentPolicy")
    snapshot_execution = ff6_type("SnapshotExecutionPolicy")
    registry = ff6_type("EvidenceSchemaRegistryContract")
    timeline = ff6_type("EvidenceSourceBindingTimeline")
    clock_policy = ff6_type("BindingClockPolicy")
    source_health_policy = ff6_type("SourceHealthPolicy")
    health_retention = ff6_type("Task01HealthRetentionContract")
    tcp_schema = ff6_type("TcpSynV2SchemaContract")
    k2a = ff6_type("K2AConformancePackage")
    portal_schema = ff6_type("PortalHeadersV2SchemaContract")
    capability = ff6_type("CapabilityDisposition")
    eacs = require_id(EXACT["EACS"])
    classification_policy = require_id(EXACT["CLASSIFICATION_POLICY"])
    classification_retention_policy = require_id(EXACT["RETENTION_POLICY"])
    product_validation_policy = require_id(EXACT["PRODUCT_POLICY"])

    if registry.artifact_id != schema["EvidenceSchemaRegistryContract"].artifact_id:
        raise RuntimeError("accepted F-F6 registry differs from current frozen registry")
    if tcp_schema.artifact_id != schema["TcpSynV2SchemaContract"].artifact_id:
        raise RuntimeError("accepted F-F6 TCP schema differs from current frozen schema")
    if portal_schema.artifact_id != schema["PortalHeadersV2SchemaContract"].artifact_id:
        raise RuntimeError("accepted F-F6 portal schema differs from current frozen schema")
    if capability.artifact_id != schema["CapabilityDisposition"].artifact_id:
        raise RuntimeError("accepted F-F6 capability differs from current frozen disposition")
    if eacs.artifact_id != eacs_fallback.artifact_id:
        raise RuntimeError("accepted F-F1 adapter set differs from current frozen builder")

    # F-A3 was accepted before the project systematically retained GateProofArtifact
    # bodies. R14 nevertheless requires a canonical SNAPSHOT_CONCURRENCY output.
    # Materialize the missing formal proof NOW from the retained accepted PR #130
    # result; do not rerun the concurrency test.
    fa3_basis_path = out / "f-a3-retained-acceptance-basis.json"
    fa3_basis = {
        "recorded_at_utc": utc_ms(),
        "source_gate_id": "F-A3",
        "source_pr": "https://github.com/ZaurNavi/CaptivePortal/pull/130",
        "accepted_head": "7d133b7c5199bf22cc4f3f8965ce040f372300eb",
        "accepted_tree": "97048a21b1af965fe5fe0784a498882370e61a5f",
        "retained_acceptance": {
            "single_read_transaction": "PASS",
            "concurrent_delayed_insert_consistency": "PASS",
            "concurrent_retention_delete_consistency": "PASS",
            "wal_checkpoint_consistency": "PASS",
            "tests": "15 passed",
            "compileall": "PASS",
            "git_diff_check": "PASS",
            "production_change": "NO",
        },
        "materialization_semantics": (
            "Formal R14 GateProofArtifact registration of an already accepted F-A3 proof. "
            "No proof/test rerun and no historical timestamp fabrication."
        ),
    }
    write_json(fa3_basis_path, fa3_basis)
    fa3_evidence = [{
        "evidence_label": "f_a3_retained_acceptance_pr130",
        "file_sha256": sha256_file(fa3_basis_path),
        "media_type": "application/json",
        "path_or_reference": str(fa3_basis_path),
    }]
    fa3_existing = existing_proofs("SNAPSHOT_CONCURRENCY", source_gate_id="F-A3")
    if len(fa3_existing) > 1:
        raise RuntimeError(
            "multiple retained F-A3 SNAPSHOT_CONCURRENCY proof bodies: "
            + ",".join(x.artifact_id for x in fa3_existing)
        )
    if fa3_existing:
        snapshot_concurrency_proof = fa3_existing[0]
    else:
        snapshot_concurrency_proof = make_gate_proof_artifact({
            "proof_kind": "SNAPSHOT_CONCURRENCY",
            "source_gate_id": "F-A3",
            "candidate_repository_commit_sha": "7d133b7c5199bf22cc4f3f8965ce040f372300eb",
            "candidate_repository_tree_sha": "97048a21b1af965fe5fe0784a498882370e61a5f",
            "input_artifact_refs": [
                ref(schema_migration), ref(watermark), ref(generation_recovery),
            ],
            "procedure_or_test_suite_id": "F-A3-retained-acceptance-registration-v1",
            "proof_execution_identity": {
                "execution_id": str(uuid.uuid4()),
                "executor_kind": "TECHLEAD_RETAINED_ACCEPTANCE_MATERIALIZER",
                "repository_commit_sha": main_commit,
                "repository_tree_sha": main_tree,
                "procedure_or_test_suite_id": "F-A3-retained-acceptance-registration-v1",
                "environment_identity": "Windows-Central-Lab-TechLead14",
                "execution_artifact_sha256": None,
            },
            "canonical_result_summary": (
                "PASS; retained PR #130 acceptance: one-read-transaction snapshot consistency, "
                "concurrent delayed-insert consistency, concurrent retention-delete consistency, "
                "WAL checkpoint consistency; 15 tests passed; compileall PASS; git diff --check PASS; "
                "formal artifact materialized without proof rerun"
            ),
            "retained_evidence_refs": fa3_evidence,
        })
        add(snapshot_concurrency_proof, "retrospective-formalization:F-A3:PR130")
        save_artifact(out / "materialized-proof-artifacts" / "F-A3-SNAPSHOT_CONCURRENCY.json",
                      snapshot_concurrency_proof)

    # F-A4 already has an exact accepted deterministic proof builder in the repo.
    # Re-materialize that exact accepted artifact if its body is absent locally.
    fa4_existing = [
        x for x in existing_proofs("SNAPSHOT_PERFORMANCE", source_gate_id="F-A4")
        if x.artifact_id == EXACT["FA4_PROOF"]
    ]
    if len(fa4_existing) > 1:
        raise RuntimeError("duplicate exact accepted F-A4 proof body")
    if fa4_existing:
        snapshot_performance_proof = fa4_existing[0]
    else:
        snapshot_performance_proof = build_snapshot_performance_gate_proof(
            "a7a12ba846b6367ff41d59afee4571277c90f20d",
            "02b6af353643a4321a6f14d01735b9c0e305842e",
        )
        if snapshot_performance_proof.artifact_id != EXACT["FA4_PROOF"]:
            raise RuntimeError(
                "deterministic F-A4 proof identity mismatch: "
                + snapshot_performance_proof.artifact_id
            )
        add(snapshot_performance_proof, "current-main:exact-F-A4-proof-builder")
        save_artifact(out / "materialized-proof-artifacts" / "F-A4-SNAPSHOT_PERFORMANCE.json",
                      snapshot_performance_proof)

    if ff5_proof.semantic_payload.get("proof_kind") != "RUNTIME_PROFILE_ATOMICITY":
        raise RuntimeError("wrong F-F5 proof kind")
    if ff6_proof.semantic_payload.get("proof_kind") != "ARTIFACT_GRAPH_ACYCLICITY":
        raise RuntimeError("wrong F-F6 proof kind")

    # Current real KnowledgeBundle exact dependencies.
    kb = knowledge_bundle.semantic_payload
    def by_ref(value: dict[str, str], kind: str | None = None) -> ArtifactContent:
        r = ArtifactRef.from_dict(value)
        c = require_id(r.artifact_id)
        if c.content_sha256 != r.content_sha256:
            raise RuntimeError(f"digest mismatch for {r.artifact_id}")
        if kind is not None and c.artifact_type != kind:
            raise RuntimeError(f"wrong type for {r.artifact_id}")
        return c

    current_taxonomy = by_ref(kb["classification_taxonomy"], "ClassificationTaxonomy")
    current_alias = by_ref(kb["alias_mapping"], "AliasMapping")
    if current_taxonomy.artifact_id != EXACT["TAXONOMY"] or current_alias.artifact_id != EXACT["ALIAS"]:
        raise RuntimeError("real KnowledgeBundle taxonomy/alias identity mismatch")

    k1_records = by_ref(kb["k1_record_set"], "CanonicalKnowledgeRecordSet")
    k2b_records = by_ref(kb["k2b_record_set"], "CanonicalKnowledgeRecordSet")
    k3_rules = by_ref(kb["k3_portal_rule_set"], "K3PortalRuleSet")
    k4_records = by_ref(kb["k4_record_set"], "CanonicalKnowledgeRecordSet")

    def provenance_for_record(record: ArtifactContent) -> ArtifactContent:
        return by_ref(record.semantic_payload["knowledge_provenance"], "KnowledgeProvenanceManifest")

    k1_prov = provenance_for_record(k1_records)
    k2b_prov = provenance_for_record(k2b_records)
    k4_prov = provenance_for_record(k4_records)

    k3_prov_candidates = [
        by_ref(x, "KnowledgeProvenanceManifest")
        for x in kb["knowledge_provenance_manifests"]
    ]
    k3_prov_candidates = [
        x for x in k3_prov_candidates
        if x.semantic_payload.get("provenance_kind") == "internal"
        and x.semantic_payload.get("rule_set_artifact") == ref(k3_rules)
    ]
    if len(k3_prov_candidates) != 1:
        raise RuntimeError("cannot resolve exact K3 internal provenance")
    k3_prov = k3_prov_candidates[0]

    def external_lineage(prov: ArtifactContent):
        p = prov.semantic_payload
        if p.get("provenance_kind") != "external":
            raise RuntimeError(f"expected external provenance: {prov.artifact_id}")
        return (
            by_ref(p["source_governance_record"], "SourceGovernanceRecord"),
            by_ref(p["knowledge_freshness_policy"], "KnowledgeFreshnessPolicy"),
        )

    k1_gov, k1_fresh = external_lineage(k1_prov)
    k2b_gov, k2b_fresh = external_lineage(k2b_prov)
    k4_gov, k4_fresh = external_lineage(k4_prov)

    knowledge_candidate = KnowledgeBundleCandidate(
        current_taxonomy, current_alias,
        k1_records, k1_prov, k1_gov, k1_fresh,
        k2b_records, k2b_prov, k2b_gov, k2b_fresh,
        k3_rules, k3_prov,
        k4_records, k4_prov, k4_gov, k4_fresh,
    )

    # Source-health emitter set is derived from exact accepted timeline/policy refs,
    # not guessed from every historical emitter body in the folder.
    emitter_refs = {
        r for c in (timeline, source_health_policy)
        for r in extract_direct_artifact_refs(c)
        if r.artifact_id.startswith("SourceHealthEmitterContract:v1:sha256:")
    }
    emitters = tuple(sorted(
        (by_ref(r.as_dict(), "SourceHealthEmitterContract") for r in emitter_refs),
        key=lambda x: x.artifact_id,
    ))
    if not emitters:
        raise RuntimeError("accepted source-health emitter set is empty")

    # F-C2 has sibling canonical outputs: the K2A package PLUS three governance
    # records. The governance records are intentionally NOT direct dependencies
    # of K2AConformancePackage. Bind them to the exact accepted PR #147 IDs.
    if k2a.artifact_id != EXACT["K2A_PACKAGE"]:
        raise RuntimeError("accepted F-F6 K2A package differs from accepted PR #147")
    k2a_governance = tuple(sorted(
        (require_id(aid) for aid in expected_k2a_governance_ids),
        key=lambda x: x.artifact_id,
    ))
    if {item.artifact_id for item in k2a_governance} != expected_k2a_governance_ids:
        raise RuntimeError("K2A governance accepted-output set mismatch")

    # Find retained exact formal gates that were already materialized.
    pass_gates: dict[str, list[ArtifactContent]] = defaultdict(list)
    for content in pool.values():
        if content.artifact_type == "GateResultManifest":
            p = content.semantic_payload
            if p.get("status") == "PASS":
                pass_gates[p.get("gate_id")].append(content)

    def gate_with_outputs(gate_id: str, output_ids: set[str]) -> ArtifactContent:
        values = []
        for gate in pass_gates.get(gate_id, []):
            actual = {x["artifact_id"] for x in gate.semantic_payload["output_artifact_refs"]}
            if output_ids <= actual:
                values.append(gate)
        by_id = {x.artifact_id: x for x in values}
        values = list(by_id.values())
        if len(values) != 1:
            raise RuntimeError(
                f"expected one retained PASS {gate_id} matching outputs, found {len(values)}: "
                + ",".join(x.artifact_id for x in values)
            )
        return values[0]

    fe6_gate = gate_with_outputs("F-E6", {EXACT["TAXONOMY"], EXACT["ALIAS"]})
    ff2_gate = gate_with_outputs("F-F2", {EXACT["CLASSIFICATION_POLICY"]})
    ff3_gate = gate_with_outputs("F-F3", {EXACT["RETENTION_POLICY"]})
    ff4_gate = gate_with_outputs("F-F4", {EXACT["PRODUCT_POLICY"]})
    ff6_gate = gate_with_outputs("F-F6", {EXACT["FF6_PROOF"]})

    retained_gates: dict[str, ArtifactContent] = {
        "F-E5": fe5_gate, "F-E6": fe6_gate, "F-E7": fe7_gate,
        "F-F2": ff2_gate, "F-F3": ff3_gate, "F-F4": ff4_gate,
        "F-F5": ff5_gate, "F-F6": ff6_gate,
    }

    # Define exact outputs of the 18 historically accepted gates that lacked a
    # retained formal GateResultManifest body in the lab artifact directory.
    outputs: dict[str, tuple[ArtifactContent, ...]] = {
        "F-A1": (schema_migration, watermark),
        "F-A2": (generation_recovery,),
        "F-A3": (snapshot_concurrency_proof,),
        "F-A4": (snapshot_content, snapshot_execution, snapshot_performance_proof),
        "F-A5": (registry,),
        "F-B0": emitters,
        "F-B1": (timeline, clock_policy),
        "F-B2": (source_health_policy,),
        "F-B3": (health_retention,),
        "F-C1": (tcp_schema,),
        "F-C2": (k2a, *k2a_governance),
        "F-C3": (ttl_proof,),
        "F-D1": (portal_schema, capability),
        "F-E1": (k1_prov, k1_records, k1_gov, k1_fresh),
        "F-E2": (k2b_prov, k2b_records, k2b_gov, k2b_fresh),
        "F-E3": (k3_rules, k3_prov),
        "F-E4": (k4_prov, k4_records, k4_gov, k4_fresh),
        "F-F1": (eacs,),
    }

    # Current exact ArtifactContent inputs where R14 names an accepted artifact input.
    inputs_by_gate: dict[str, tuple[ArtifactContent, ...]] = {
        "F-A1": (),
        "F-A2": (schema_migration, watermark),
        "F-A3": (schema_migration, watermark, generation_recovery),
        "F-A4": (schema_migration, watermark, registry),
        "F-A5": (tcp_schema, portal_schema, capability),
        "F-B0": (),
        "F-B1": emitters,
        "F-B2": (*emitters, timeline, clock_policy),
        "F-B3": (source_health_policy,),
        "F-C1": (),
        "F-C2": (tcp_schema,),
        "F-C3": (),
        "F-D1": (),
        "F-E1": (),
        "F-E2": (k2a,),
        "F-E3": (registry, current_taxonomy),
        "F-E4": (),
        "F-F1": (registry, capability, k2a, k1_records, k3_rules, k4_records),
    }

    owner_decision_id = str(uuid.uuid4())
    owner_decision_path = out / "owner-decision-record.json"
    owner_decision = {
        "decision_record_id": owner_decision_id,
        "recorded_at_utc": utc_ms(),
        "decision": "AUTHORIZE_RETAINED_GATE_RESULT_MATERIALIZATION_AND_INITIAL_F_ADMIT",
        "basis": (
            "Owner explicitly authorized continuation of F-E7/F-ADMIT work and, after PR #164 merge, "
            "explicitly instructed TechLead14 to continue. This record is created now and is not backdated."
        ),
        "scope": [*MISSING_FORMAL_GATES, "F-ADMIT"],
        "production_application_deploy_authorized": False,
    }
    write_json(owner_decision_path, owner_decision)

    materialization_basis_path = out / "retained-acceptance-materialization-basis.json"
    materialization_basis = {
        "recorded_at_utc": utc_ms(),
        "repository_commit": main_commit,
        "repository_tree": main_tree,
        "purpose": (
            "Materialize formal GateResultManifest bodies for already accepted Foundation gates whose "
            "status/output acceptance predated systematic local GateResult retention. No gate proof is rerun."
        ),
        "r14_rule": "Gate status cannot exist only in chat prose.",
        "gates": {
            gate_id: {
                "status": "PREVIOUSLY_ACCEPTED__FORMAL_MANIFEST_MATERIALIZED_NOW",
                "accepted_output_artifact_ids": [x.artifact_id for x in outputs[gate_id]],
                "retained_github_prs": PR_BASIS[gate_id],
                "github_urls": [
                    f"https://github.com/ZaurNavi/CaptivePortal/pull/{number}"
                    for number in PR_BASIS[gate_id]
                ],
            }
            for gate_id in MISSING_FORMAL_GATES
        },
        "no_rerun": {
            "central_lab": True,
            "gate_proof_suites": True,
            "topology_capture": True,
            "external_source_download": True,
            "coder_work": True,
        },
        "owner_decision_record_id": owner_decision_id,
    }
    write_json(materialization_basis_path, materialization_basis)

    basis_evidence = {
        "evidence_label": "retained_foundation_acceptance_materialization",
        "file_sha256": sha256_file(materialization_basis_path),
        "media_type": "application/json",
        "path_or_reference": str(materialization_basis_path),
    }
    owner_evidence = {
        "evidence_label": "owner_decision_record",
        "file_sha256": sha256_file(owner_decision_path),
        "media_type": "application/json",
        "path_or_reference": str(owner_decision_path),
    }

    script_sha = sha256_file(Path(__file__))
    materialized_gates: dict[str, ArtifactContent] = {}
    materialized_dir = out / "materialized-gate-results"

    for gate_id in MISSING_FORMAL_GATES:
        gate = make_gate_result_manifest({
            "gate_id": gate_id,
            "gate_contract_version": f"R14-{gate_id}-v1",
            "status": "PASS",
            "candidate_repository_commit_sha": None,
            "candidate_repository_tree_sha": None,
            "input_artifact_refs": [ref(x) for x in inputs_by_gate[gate_id]],
            "output_artifact_refs": [ref(x) for x in outputs[gate_id]],
            "retained_evidence_refs": [basis_evidence, owner_evidence],
            "proof_execution_identity": {
                "execution_id": str(uuid.uuid4()),
                "executor_kind": "TECHLEAD_GATE_RESULT_MATERIALIZER",
                "repository_commit_sha": main_commit,
                "repository_tree_sha": main_tree,
                "procedure_or_test_suite_id": "R14-retained-acceptance-materialization-v3",
                "environment_identity": "Windows-Central-Lab-TechLead14",
                "execution_artifact_sha256": script_sha,
            },
            "trusted_time_inputs": {
                "foundation_knowledge_evaluation_at_utc": None,
                "foundation_admission_evaluation_at_utc": None,
                "knowledge_evaluation_at_utc": None,
            },
            "decision_record_refs": [owner_decision_id],
        })
        materialized_gates[gate_id] = gate
        add(gate, f"materialized-now:{gate_id}")
        save_artifact(materialized_dir / f"{gate_id}.json", gate)

    prerequisite_gates = {**retained_gates, **materialized_gates}
    if set(prerequisite_gates) != set(MANDATORY_PRE_ADMISSION_GATES):
        missing = set(MANDATORY_PRE_ADMISSION_GATES) - set(prerequisite_gates)
        extra = set(prerequisite_gates) - set(MANDATORY_PRE_ADMISSION_GATES)
        raise RuntimeError(f"gate inventory mismatch missing={sorted(missing)} extra={sorted(extra)}")

    # Every exact gate output body must resolve now.
    all_gate_outputs: list[ArtifactContent] = []
    for gate_id in MANDATORY_PRE_ADMISSION_GATES:
        gate = prerequisite_gates[gate_id]
        if gate.semantic_payload["status"] != "PASS":
            raise RuntimeError(f"{gate_id} is not PASS")
        for raw in gate.semantic_payload["output_artifact_refs"]:
            r = ArtifactRef.from_dict(raw)
            c = require_id(r.artifact_id)
            if c.content_sha256 != r.content_sha256:
                raise RuntimeError(f"{gate_id} output digest mismatch {r.artifact_id}")
            all_gate_outputs.append(c)

    # Verify exact F-E5/F-E7 current real knowledge time.
    knowledge_time = fe5_gate.semantic_payload["trusted_time_inputs"][
        "foundation_knowledge_evaluation_at_utc"]
    if (knowledge_time != "2026-09-24T06:30:01.479Z"
            or fe7_gate.semantic_payload["trusted_time_inputs"][
                "foundation_knowledge_evaluation_at_utc"] != knowledge_time):
        raise RuntimeError("real F-E5/F-E7 trusted knowledge time mismatch")

    # Use accepted Task-01 v2 migration target for both frozen Task-01 v2
    # database-generation and watermark-generation contract versions.
    migration_payload = schema_migration.semantic_payload
    if migration_payload.get("from_schema_version") != 1 or migration_payload.get("to_schema_version") != 2:
        raise RuntimeError("Task-01 accepted v1->v2 migration contract mismatch")
    task01_generation_contract_version = migration_payload["to_schema_version"]

    # Foundation snapshot contract is current R14 V1.
    snapshot_contract_version = 1

    # Build exact semantic closure needed by all outputs/named artifacts.
    roots = {
        x.artifact_id: x
        for x in (
            architecture, *prerequisite_gates.values(), *all_gate_outputs,
            registry, eacs, knowledge_bundle, timeline, clock_policy,
            source_health_policy, *emitters, snapshot_content, snapshot_execution,
            classification_policy, classification_retention_policy, product_validation_policy,
            k2a, health_retention, ttl_proof,
            current_taxonomy, current_alias,
            k1_records, k1_prov, k1_gov, k1_fresh,
            k2b_records, k2b_prov, k2b_gov, k2b_fresh,
            k3_rules, k3_prov,
            k4_records, k4_prov, k4_gov, k4_fresh,
        )
    }

    boundary_gate_ids = {x.artifact_id for x in prerequisite_gates.values()}
    closure: dict[str, ArtifactContent] = {}

    def add_closure(content: ArtifactContent) -> None:
        if content.artifact_id in closure:
            return
        closure[content.artifact_id] = content
        # Accepted prerequisite GateResults and GateProofs are immutable boundary leaves.
        if content.artifact_id in boundary_gate_ids or content.artifact_type == "GateProofArtifact":
            return
        for r in extract_direct_artifact_refs(content):
            dep = require_id(r.artifact_id)
            if dep.content_sha256 != r.content_sha256:
                raise RuntimeError(f"dependency digest mismatch {content.artifact_id} -> {r.artifact_id}")
            add_closure(dep)

    for content in roots.values():
        add_closure(content)

    # F-ADMIT retained evidence: current materialization record + owner record +
    # exact real F-E7 acceptance summary + accepted Central Lab log when present.
    f_admit_evidence = [basis_evidence, owner_evidence]

    fe7_summary = Path(
        r"C:\CaptivPortal-Lab\artifacts\fe7-real-admission-20260924-102919\acceptance-summary.json")
    if fe7_summary.is_file():
        f_admit_evidence.append({
            "evidence_label": "real_fe7_acceptance_summary",
            "file_sha256": sha256_file(fe7_summary),
            "media_type": "application/json",
            "path_or_reference": str(fe7_summary),
        })

    lab_log = Path(
        r"C:\CaptivPortal-Lab\logs\lab-test-v7-strict-20260924-222255-DETACHED.log")
    if lab_log.is_file():
        f_admit_evidence.append({
            "evidence_label": "f_admit_implementation_central_lab_v7",
            "file_sha256": sha256_file(lab_log),
            "media_type": "text/plain",
            "path_or_reference": str(lab_log),
        })

    # Stable LAB control-plane path. This is Foundation admission state, not app deploy.
    cp_dir = Path(r"C:\CaptivPortal-Lab\foundation-control-plane")
    cp_dir.mkdir(parents=True, exist_ok=True)
    db_path = cp_dir / "device-fingerprint-control-plane.sqlite3"
    store = DeviceFingerprintControlPlaneStore(db_path)
    store.initialize()

    existing = store.get_active_pointer("foundation")
    if existing is not None:
        print("F_ADMIT_REAL_STATUS=STOP")
        print("STOP_REASON=foundation_pointer_already_exists")
        print(f"RUNTIME_PROFILE_ID={existing.runtime_profile_id}")
        print(f"ACTIVATION_RECORD_ID={existing.activation_record_id}")
        print(f"CONTROL_PLANE_DB={db_path}")
        return 30

    execution_identity = {
        "execution_id": str(uuid.uuid4()),
        "executor_kind": "TECHLEAD_GATE_TOOL",
        "repository_commit_sha": main_commit,
        "repository_tree_sha": main_tree,
        "procedure_or_test_suite_id": "R14-F-ADMIT-initial-foundation-v1",
        "environment_identity": "Windows-Central-Lab-TechLead14",
        "execution_artifact_sha256": script_sha,
    }

    inputs = InitialFoundationInputs(
        prerequisite_gates=prerequisite_gates,
        named_artifacts={
            "architecture_contract_reference": architecture,
            "evidence_schema_registry_contract": registry,
            "evidence_adapter_contract_set": eacs,
            "knowledge_bundle": knowledge_bundle,
            "evidence_source_binding_timeline": timeline,
            "binding_clock_policy": clock_policy,
            "source_health_policy": source_health_policy,
            "snapshot_content_policy": snapshot_content,
            "snapshot_execution_policy": snapshot_execution,
            "classification_policy": classification_policy,
            "classification_retention_policy": classification_retention_policy,
            "product_validation_policy": product_validation_policy,
            "k2a_conformance_package": k2a,
            "portal_headers_v2_capability_disposition": capability,
            "task01_health_retention_contract": health_retention,
        },
        source_health_emitter_contracts=emitters,
        knowledge_candidate=knowledge_candidate,
        immutable_dependencies=tuple(sorted(closure.values(), key=lambda x: x.artifact_id)),
        ttl_capture_placement_proof=ttl_proof,
        architecture_document_sha256=architecture.semantic_payload["architecture_document_sha256"],
        foundation_repository_commit_sha=main_commit,
        foundation_repository_tree_sha=main_tree,
        foundation_knowledge_evaluation_at_utc=knowledge_time,
        classification_foundation_valid_from_utc=ACCEPTED_CLASSIFICATION_FOUNDATION_VALID_FROM_UTC,
        task01_database_schema_generation_contract_version=task01_generation_contract_version,
        task01_watermark_generation_contract_version=task01_generation_contract_version,
        snapshot_contract_version=snapshot_contract_version,
        proof_execution_identity=execution_identity,
        retained_evidence_refs=f_admit_evidence,
        owner_decision_record_refs=(owner_decision_id,),
    )

    # One real F-ADMIT execution. The orchestrator itself captures trusted
    # admission time exactly once and re-evaluates K1/K2B/K4 at that instant.
    plan = execute_initial_foundation_admission(
        inputs, store, trusted_admission_clock=utc_ms)

    pointer = store.get_active_pointer("foundation")
    if pointer is None:
        raise RuntimeError("Foundation ActiveProfilePointer missing after F-ADMIT")
    validity = store.get_validity_head(pointer.activation_record_id)
    if validity is None or validity.semantic_payload.get("state") != "ACTIVE":
        raise RuntimeError("Foundation ACTIVE validity head missing after F-ADMIT")
    if pointer.runtime_profile_id != plan.foundation_runtime_profile.artifact_id:
        raise RuntimeError("Foundation pointer/profile mismatch")

    with store._connect() as conn:
        publication = conn.execute(
            "SELECT gate_id, artifact_id, content_sha256 "
            "FROM f_admit_publications WHERE gate_id='F-ADMIT'").fetchone()
    if publication is None:
        raise RuntimeError("durable F-ADMIT publication missing")
    if (publication["artifact_id"] != plan.f_admit_gate_result_manifest.artifact_id
            or publication["content_sha256"] != plan.f_admit_gate_result_manifest.content_sha256):
        raise RuntimeError("durable F-ADMIT publication identity mismatch")

    outputs_dir = out / "f-admit-outputs"
    for label, content in (
        ("OriginRuntimeAdmission", plan.origin_runtime_admission),
        ("FoundationAdmissionManifest", plan.foundation_admission_manifest),
        ("FoundationRuntimeProfile", plan.foundation_runtime_profile),
        ("RuntimeProfileAdmissionManifest", plan.runtime_profile_admission_manifest),
        ("RuntimeProfileActivationRecord", plan.activation_record),
        ("RuntimeProfileValidityRecord", plan.initial_validity_record),
        ("F-ADMIT-GateResultManifest", plan.f_admit_gate_result_manifest),
    ):
        save_artifact(outputs_dir / f"{label}.json", content)

    gate_inventory = {
        gate_id: {
            "artifact_id": prerequisite_gates[gate_id].artifact_id,
            "content_sha256": prerequisite_gates[gate_id].content_sha256,
            "materialized_now": gate_id in materialized_gates,
            "outputs": prerequisite_gates[gate_id].semantic_payload["output_artifact_refs"],
        }
        for gate_id in MANDATORY_PRE_ADMISSION_GATES
    }
    write_json(out / "prerequisite-gate-inventory.json", gate_inventory)

    summary = {
        "F_ADMIT_STATUS": "PASS",
        "FOUNDATION_PROFILE_ACTIVATED": True,
        "PRODUCTION_APPLICATION_DEPLOY": False,
        "repository_commit": main_commit,
        "repository_tree": main_tree,
        "foundation_knowledge_evaluation_at_utc": knowledge_time,
        "foundation_admission_evaluation_at_utc": plan.admission_evaluation_at_utc,
        "materialized_historical_gate_result_count": len(materialized_gates),
        "retained_gate_result_count": len(retained_gates),
        "total_prerequisite_gate_count": len(prerequisite_gates),
        "OriginRuntimeAdmission": plan.origin_runtime_admission.artifact_id,
        "FoundationAdmissionManifest": plan.foundation_admission_manifest.artifact_id,
        "FoundationRuntimeProfile": plan.foundation_runtime_profile.artifact_id,
        "RuntimeProfileAdmissionManifest": plan.runtime_profile_admission_manifest.artifact_id,
        "RuntimeProfileActivationRecord": plan.activation_record.artifact_id,
        "RuntimeProfileValidityRecord": plan.initial_validity_record.artifact_id,
        "F_ADMIT_GateResultManifest": plan.f_admit_gate_result_manifest.artifact_id,
        "active_pointer": {
            "profile_kind": pointer.profile_kind,
            "runtime_profile_id": pointer.runtime_profile_id,
            "runtime_profile_digest": pointer.runtime_profile_digest,
            "activation_record_id": pointer.activation_record_id,
            "activation_generation_id": pointer.activation_generation_id,
            "updated_at_utc": pointer.updated_at_utc,
        },
        "validity_head_state": validity.semantic_payload["state"],
        "control_plane_db": str(db_path),
        "output_dir": str(out),
        "tests_rerun": False,
        "central_lab_rerun": False,
        "coder_involved": False,
        "topology_retested": False,
        "external_sources_redownloaded": False,
    }
    write_json(out / "F-ADMIT-ACCEPTANCE-SUMMARY.json", summary)

    print("============================================================")
    print("PASS: REAL F-ADMIT / INITIAL FOUNDATION ACTIVATION")
    print("============================================================")
    print("F_ADMIT_STATUS=PASS")
    print("FOUNDATION_PROFILE_ACTIVATED=YES")
    print("PRODUCTION_APPLICATION_DEPLOY=NO")
    print(f"MAIN_COMMIT={main_commit}")
    print(f"MAIN_TREE={main_tree}")
    print(f"FOUNDATION_KNOWLEDGE_EVALUATION_AT_UTC={knowledge_time}")
    print(f"FOUNDATION_ADMISSION_EVALUATION_AT_UTC={plan.admission_evaluation_at_utc}")
    print(f"MATERIALIZED_MISSING_GATE_RESULTS={len(materialized_gates)}")
    print(f"TOTAL_PREREQUISITE_GATES={len(prerequisite_gates)}")
    print(f"ORIGIN_RUNTIME_ADMISSION={plan.origin_runtime_admission.artifact_id}")
    print(f"FOUNDATION_ADMISSION_MANIFEST={plan.foundation_admission_manifest.artifact_id}")
    print(f"FOUNDATION_RUNTIME_PROFILE={plan.foundation_runtime_profile.artifact_id}")
    print(f"FOUNDATION_RPAM={plan.runtime_profile_admission_manifest.artifact_id}")
    print(f"ACTIVATION_RECORD={plan.activation_record.artifact_id}")
    print(f"VALIDITY_RECORD={plan.initial_validity_record.artifact_id}")
    print(f"F_ADMIT_GATE_MANIFEST={plan.f_admit_gate_result_manifest.artifact_id}")
    print(f"ACTIVE_POINTER_PROFILE={pointer.runtime_profile_id}")
    print(f"VALIDITY_HEAD_STATE={validity.semantic_payload['state']}")
    print("TESTS_RERUN=NO")
    print("CENTRAL_LAB_RERUN=NO")
    print("CODER_INVOLVED=NO")
    print("TOPOLOGY_RETESTED=NO")
    print("EXTERNAL_SOURCES_REDOWNLOADED=NO")
    print(f"CONTROL_PLANE_DB={db_path}")
    print(f"OUTPUT_DIR={out}")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print("F_ADMIT_REAL_STATUS=STOP")
        print("STOP_REASON=" + type(exc).__name__)
        print("STOP_DETAIL=" + str(exc))
        raise
