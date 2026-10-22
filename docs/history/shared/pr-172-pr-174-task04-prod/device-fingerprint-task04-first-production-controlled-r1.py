#!/usr/bin/env python3
"""Owner/TechLead controlled first Task-04 production-classification harness.

Modes:
  --verify-only
      Read-only. Re-run accepted T-06A C01-C09 compatibility semantics against
      the exact ACTIVE production ClassificationRuntimeProfile and current
      executable repository bytes. No classification assembly or DB write.

  --commit --mac <MAC> [--window-minutes 15] --confirm FIRST_PRODUCTION_CLASSIFICATION
      Exactly one first production classification. Refuses to run if the
      Classification DB already contains any classification row.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import sqlite3
import subprocess
import sys
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.device_fingerprint.artifact_content import (
    ArtifactContent, ArtifactRef, canonical_set, make_artifact_content,
)
from app.device_fingerprint.classification_persistence import DeviceFingerprintClassificationStore
from app.device_fingerprint.classification_policy import validate_classification_policy_dependencies
from app.device_fingerprint.classification_read import DeviceFingerprintClassificationReadService
from app.device_fingerprint.classification_retention_policy import (
    build_initial_classification_retention_policy_v1,
)
from app.device_fingerprint.classification_request import make_classification_request_manifest
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore
from app.device_fingerprint.evidence_adapter_contracts import (
    validate_evidence_adapter_contract_set_dependencies,
)
from app.device_fingerprint.foundation_admission_artifacts import make_origin_runtime_admission
from app.device_fingerprint.fusion import fuse_classification
from app.device_fingerprint.k2b_p0f_import import ACCEPTED_P0F_AUDIT
from app.device_fingerprint.knowledge_artifacts import (
    make_canonical_k2b_record_set,
    make_external_knowledge_provenance_manifest,
)
from app.device_fingerprint.knowledge_bundle import make_knowledge_bundle
from app.device_fingerprint.origin_assessment import DeviceFingerprintOriginAssessmentBuilder
from app.device_fingerprint.p0f_semantics import MATCHER_CONTRACT
from app.device_fingerprint.read_service import DeviceFingerprintReadService
from app.device_fingerprint.request_assembly import DeviceFingerprintRequestAssembly
from app.device_fingerprint.runtime_profile_artifacts import make_classification_runtime_profile
from app.device_fingerprint.taxonomy_artifacts import validate_alias_mapping_against_taxonomy
from app.device_fingerprint.validation import format_utc, validate_mac


TARGET_SHA = "fecdb5a7c79e56bb49be4797ca875d6720670042"
TARGET_TREE = "85d7d41e1ad19c079cad0ae819a3fe38a068e242"
EXPECTED_CRP_ID = "ClassificationRuntimeProfile:v1:sha256:1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c"
EXPECTED_CRP_SHA = "1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c"
EXPECTED_RPM_ID = "RuntimeProfileAdmissionManifest:v1:sha256:7873028b2c3a85bf152c9bc4ea057e476591ab87d3c3a52b8cdff654beb8c98b"
EXPECTED_ACTIVATION_ID = "c9600739-38c6-4186-b67d-91ada854376f"
EXPECTED_GENERATION_ID = "a17a67e5-b291-40c3-96f6-182bf33c6da6"
SITE_ID = "6a64f17630da7c70d232187a"

BASE_TASK_KEYS = {
    ("dhcp", 1), ("tcp_syn", 1), ("tcp_syn", 2),
    ("tls_client", 1), ("quic_client", 1), ("portal_headers", 1),
}


class HarnessError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise HarnessError(message)


def ref(content: ArtifactContent) -> dict[str, str]:
    return {"artifact_id": content.artifact_id, "content_sha256": content.content_sha256}


def load_ref(store: DeviceFingerprintControlPlaneStore, value: dict[str, str]) -> ArtifactContent:
    r = ArtifactRef.from_dict(value)
    return store.load_artifact(r.artifact_id, r.content_sha256)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_repo(repo: Path) -> None:
    head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    tree = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD^{tree}"], text=True).strip()
    dirty = subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain=v1"], text=True)
    require(head == TARGET_SHA, f"REPOSITORY_HEAD_MISMATCH:{head}")
    require(tree == TARGET_TREE, f"REPOSITORY_TREE_MISMATCH:{tree}")
    require(dirty == "", "REPOSITORY_DIRTY")


def symbol_identity(repo: Path, module: Any, symbol: str, role: str) -> dict[str, str]:
    path = Path(module.__file__).resolve(strict=True)
    relative = path.relative_to(repo.resolve(strict=True)).as_posix()
    qualified = f"{symbol}/{role}"
    return {
        "implementation_id": f"python:{relative}:{qualified}",
        "implementation_digest": sha256(path),
    }


def build_inventory(repo: Path, registry: ArtifactContent, disposition: ArtifactContent,
                    adapter: ArtifactContent) -> list[dict[str, Any]]:
    import app.device_fingerprint.origin_assessment as origin_module

    schemas_payload = registry.semantic_payload
    disposition_payload = disposition.semantic_payload
    entries = adapter.semantic_payload["adapter_entries"]
    expected = set(BASE_TASK_KEYS)
    if disposition_payload["status"] == "ADMITTED":
        expected.add(("portal_headers", 2))

    schema_rows = schemas_payload["schema_entries"]
    schemas = {
        (row["source_kind"], row["feature_schema_version"]): row["schema_status"]
        for row in schema_rows
    }
    require(len(schemas) == len(schema_rows), "C04_DUPLICATE_ADMITTED_SCHEMA")
    require(set(schemas) == expected, "C04_REGISTRY_COVERAGE")

    task = [row for row in entries if row["adapter_kind"] == "TASK01_EVIDENCE"]
    mac = [row for row in entries if row["adapter_kind"] == "MAC_REGISTRY"]
    keys = [(row["source_kind"], row["feature_schema_version"]) for row in task]
    require(len(keys) == len(set(keys)) and set(keys) == expected and len(mac) == 1,
            "C04_ADAPTER_COVERAGE")

    semantic: list[dict[str, Any]] = []
    for row in task:
        source, version = row["source_kind"], row["feature_schema_version"]
        mode = (
            "NON_FUSION_HANDLER" if (source, version) == ("tcp_syn", 1)
            else "OPTIONAL_IF_ADMITTED" if (source, version) == ("portal_headers", 2)
            else "FUSION"
        )
        require((schemas[(source, version)] == "KNOWN_NON_FUSION")
                == (mode == "NON_FUSION_HANDLER"), "C04_FUSION_ROLE")
        require((row["legacy_current_role"] == "LEGACY_NON_FUSION")
                == (mode == "NON_FUSION_HANDLER"), "C04_LEGACY_ROLE")
        if source in ("tls_client", "quic_client"):
            require(row["quality_valid_behavior"].startswith("AUDIT_ONLY_"),
                    "C04_TLS_QUIC_CLAIM_EXPANSION")
        identity = symbol_identity(
            repo, origin_module, "DeviceFingerprintOriginAssessmentBuilder.build",
            f"{source}/{version}/{mode}",
        )
        semantic.append({
            "adapter_kind": "TASK01_EVIDENCE",
            "source_kind": source,
            "feature_schema_version": version,
            "implementation_id": identity["implementation_id"],
            "implementation_digest": identity["implementation_digest"],
            "mode": mode,
        })

    require(mac[0]["origin_group"] == "mac_registry", "C04_MAC_ORIGIN")
    identity = symbol_identity(
        repo, origin_module, "DeviceFingerprintOriginAssessmentBuilder.build",
        "mac_registry/FUSION",
    )
    semantic.append({
        "adapter_kind": "MAC_REGISTRY",
        "origin_group": "mac_registry",
        "implementation_id": identity["implementation_id"],
        "implementation_digest": identity["implementation_digest"],
        "mode": "FUSION",
    })
    return canonical_set(
        semantic,
        lambda row: (
            row["adapter_kind"],
            row.get("source_kind", "mac_registry"),
            row.get("feature_schema_version", row["implementation_id"]),
        ),
    )


def c08_runtime_versions(foundation: ArtifactContent, registry: ArtifactContent) -> dict[str, Any]:
    # This deliberately mirrors the accepted T-06/T-06A proof method.
    import tests.device_fingerprint_task04_t04.test_fusion as fusion_fixture
    import tests.device_fingerprint_task04_t03.test_origin_assessment as origin_fixture

    controlled = fusion_fixture._base_from_source(origin_fixture._inputs())
    result = fuse_classification(controlled)
    require(result.artifact_type == "ClassificationResult", "C08_RESULT_TYPE")
    require(type(result.artifact_schema_version) is int and result.artifact_schema_version > 0,
            "C08_RESULT_VERSION")
    snapshot_version = foundation.semantic_payload["snapshot_contract_version"]
    require(type(snapshot_version) is int and snapshot_version > 0, "C08_SNAPSHOT_VERSION")
    require(isinstance(MATCHER_CONTRACT, str) and bool(MATCHER_CONTRACT), "C08_MATCHER_VERSION")
    require(registry.semantic_payload["evidence_canonical_json_version"] == "EvidenceCanonicalJsonV1",
            "C08_EVIDENCE_CANONICAL_JSON")
    return {
        "classification_result_schema_version": result.artifact_schema_version,
        "snapshot_contract_version": snapshot_version,
        "k2a_matcher_implementation_version": MATCHER_CONTRACT,
    }


def compatibility_c01_c09(repo: Path, store: DeviceFingerprintControlPlaneStore,
                          pinned: Any) -> tuple[list[dict[str, Any]], dict[str, ArtifactContent]]:
    profile = pinned.runtime_profile
    require(profile.artifact_id == EXPECTED_CRP_ID and profile.content_sha256 == EXPECTED_CRP_SHA,
            "ACTIVE_CRP_NOT_EXPECTED")
    require(make_classification_runtime_profile(profile.semantic_payload) == profile,
            "ACTIVE_CRP_NONCANONICAL")

    p = profile.semantic_payload
    foundation = load_ref(store, p["foundation_runtime_profile"])
    bundle = load_ref(store, p["knowledge_bundle"])
    policy = load_ref(store, p["classification_policy"])
    adapter = load_ref(store, p["evidence_adapter_contract_set"])
    classifier = load_ref(store, p["classifier_artifact_manifest"])

    foundation_rpm = load_ref(
        store, pinned.admission_manifest.semantic_payload["foundation_runtime_profile_admission_manifest"]
    )
    foundation_manifest = load_ref(store, foundation_rpm.semantic_payload["foundation_admission_manifest"])
    fm = foundation_manifest.semantic_payload

    admitted_adapter = load_ref(store, fm["evidence_adapter_contract_set"])
    admitted_knowledge = load_ref(store, fm["knowledge_bundle"])
    k2a = load_ref(store, fm["k2a_conformance_package"])
    disposition = load_ref(store, fm["portal_headers_v2_capability_disposition"])
    registry = load_ref(store, foundation.semantic_payload["evidence_schema_registry_contract"])
    origin = load_ref(store, foundation.semantic_payload["origin_runtime_admission"])

    require(admitted_adapter == adapter, "FOUNDATION_CLASSIFICATION_ADAPTER_IDENTITY_MISMATCH")
    require(admitted_knowledge == bundle, "FOUNDATION_CLASSIFICATION_KNOWLEDGE_IDENTITY_MISMATCH")
    require(make_knowledge_bundle(bundle.semantic_payload) == bundle, "KNOWLEDGE_BUNDLE_NONCANONICAL")

    bp, pp, ap, cp, fp = (
        bundle.semantic_payload, policy.semantic_payload, adapter.semantic_payload,
        classifier.semantic_payload, foundation.semantic_payload,
    )
    tax = load_ref(store, bp["classification_taxonomy"])
    alias = load_ref(store, bp["alias_mapping"])

    rows: list[dict[str, Any]] = []

    def check(cid: str, fn) -> None:
        try:
            fn()
            rows.append({"check_id": cid, "status": "PASS"})
        except Exception as exc:
            rows.append({
                "check_id": cid, "status": "FAIL",
                "failure": f"{type(exc).__name__}:{str(exc)[:300]}",
            })

    check("C01", lambda: require(
        bp["classification_taxonomy"] == pp["classification_taxonomy"] == ref(tax),
        "taxonomy identity",
    ))

    def c02():
        require(bp["alias_mapping"] == pp["alias_mapping"] == ref(alias), "alias identity")
        validate_alias_mapping_against_taxonomy(tax, alias)
        validate_classification_policy_dependencies(
            policy, classification_taxonomy=tax, alias_mapping=alias,
            evidence_adapter_contract_set=adapter,
        )
    check("C02", c02)

    check("C03", lambda: require(
        pp["evidence_adapter_contract_set"] == ref(adapter), "policy/adapter identity"
    ))

    def c04():
        expected = build_inventory(repo, registry, disposition, adapter)
        require(cp["adapter_implementation_identities"] == expected, "classifier adapter coverage")
        require(make_artifact_content("ClassifierArtifactManifest", cp) == classifier,
                "classifier canonical identity")
    check("C04", c04)

    check("C05", lambda: require(
        fp["snapshot_contract_version"] == cp["snapshot_contract_version"],
        "snapshot contract version",
    ))

    def c06():
        records = {
            name: load_ref(store, bundle.semantic_payload[name])
            for name in ("k1_record_set", "k3_portal_rule_set", "k4_record_set")
        }
        require(
            validate_evidence_adapter_contract_set_dependencies(
                adapter,
                evidence_schema_registry=registry,
                capability_disposition=disposition,
                k2a_conformance_package=k2a,
                k1_record_set=records["k1_record_set"],
                k3_portal_rule_set=records["k3_portal_rule_set"],
                k4_record_set=records["k4_record_set"],
            ) is True,
            "Foundation adapter/registry dependencies",
        )
        require(admitted_adapter == adapter, "Foundation adapter identity")
    check("C06", c06)

    def c07():
        require(cp["k2a_matcher_implementation_version"] == MATCHER_CONTRACT,
                "K2A matcher version")
        require(
            k2a.semantic_payload["matcher_implementation_contract_version"]
            == cp["k2a_matcher_implementation_version"],
            "K2A package version",
        )
        record_set = load_ref(store, bp["k2b_record_set"])
        require(make_canonical_k2b_record_set(record_set.semantic_payload) == record_set,
                "K2B canonical record set")
        require(bp["k2b_record_set"] == ref(record_set), "K2B record-set identity")
        provenance_ref = record_set.semantic_payload["knowledge_provenance"]
        provenance = load_ref(store, provenance_ref)
        require(provenance_ref in bp["knowledge_provenance_manifests"],
                "K2B provenance membership")
        require(provenance_ref == ref(provenance), "K2B provenance identity")
        require(
            make_external_knowledge_provenance_manifest(provenance.semantic_payload) == provenance,
            "K2B provenance canonical",
        )
        require(
            provenance.semantic_payload["source_governance_record"]
            in bp["source_governance_records"],
            "K2B governance membership",
        )
        require(
            provenance.semantic_payload["knowledge_freshness_policy"]
            in bp["knowledge_freshness_policies"],
            "K2B freshness membership",
        )
        require(ACCEPTED_P0F_AUDIT.admitted_canonical_records > 0, "K2B audit")
    check("C07", c07)

    def c08():
        versions = c08_runtime_versions(foundation, registry)
        require(fp["foundation_profile_contract_version"] == 1, "foundation profile version")
        require(p["classification_runtime_profile_contract_version"] == 1,
                "classification profile version")
        require(bp["bundle_schema_version"] == 1, "bundle schema version")
        require(pp["policy_schema_version"] == 1, "policy schema version")
        require(
            cp["classification_result_schema_version"]
            == versions["classification_result_schema_version"],
            "classification result schema version",
        )
        require(cp["snapshot_contract_version"] == versions["snapshot_contract_version"],
                "snapshot contract version")
        require(
            cp["k2a_matcher_implementation_version"]
            == versions["k2a_matcher_implementation_version"],
            "matcher implementation version",
        )
        require(callable(make_classification_request_manifest) and callable(fuse_classification),
                "request/classification contracts")
    check("C08", c08)

    def c09():
        require(make_origin_runtime_admission(origin.semantic_payload) == origin,
                "OriginRuntimeAdmission contract")
        op = origin.semantic_payload
        if op["tcp_state"] == "ENABLED":
            ttl = load_ref(store, op["ttl_capture_placement_proof"])
            require(op["tcp_reason_code"] == "TTL_PROOF_VALID", "enabled TCP reason")
            require(fp["ttl_capture_placement_proof"] == ref(ttl), "enabled TCP TTL identity")
        else:
            require(
                op["tcp_state"] == "DISABLED"
                and op["tcp_reason_code"] in {"TTL_PROOF_INVALID", "PROFILE_POLICY_DISABLED"},
                "disabled TCP semantics",
            )
        require(callable(DeviceFingerprintOriginAssessmentBuilder.build),
                "candidate origin semantics")
    check("C09", c09)

    require(len(rows) == 9 and all(row["status"] == "PASS" for row in rows),
            "PROFILE_COMPATIBILITY_FAILED:" + json.dumps(rows, sort_keys=True))
    return rows, {
        "profile": profile, "foundation": foundation, "bundle": bundle,
        "policy": policy, "adapter": adapter, "classifier": classifier,
    }


def current_rss_guard(limit: int) -> bool:
    """Linux analogue of T-09 current WorkingSet/PrivateUsage guard; fail closed."""
    if type(limit) is not int or limit <= 0 or os.name != "posix":
        raise HarnessError("PROCESS_MEMORY_MEASUREMENT_UNAVAILABLE")
    try:
        statm = Path("/proc/self/statm").read_text(encoding="ascii").split()
        resident_pages = int(statm[1])
        rss = resident_pages * os.sysconf("SC_PAGE_SIZE")
    except Exception as exc:
        raise HarnessError("PROCESS_MEMORY_MEASUREMENT_UNAVAILABLE") from exc
    return rss <= limit


def frozen_clock() -> str:
    return format_utc(datetime.now(timezone.utc))


def db_count(path: Path, table: str) -> int:
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        require(conn.execute("PRAGMA quick_check").fetchone()[0] == "ok",
                f"{table}:QUICK_CHECK_FAILED")
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        conn.close()


def verify_active(repo: Path, control_db: Path) -> tuple[
        DeviceFingerprintControlPlaneStore, Any, list[dict[str, Any]], dict[str, ArtifactContent]]:
    exact_repo(repo)
    store = DeviceFingerprintControlPlaneStore(control_db)
    pinned = store.pin_active_profile("classification")
    require(pinned.pointer.runtime_profile_id == EXPECTED_CRP_ID, "ACTIVE_POINTER_CRP_ID")
    require(pinned.pointer.runtime_profile_digest == EXPECTED_CRP_SHA, "ACTIVE_POINTER_CRP_SHA")
    require(pinned.pointer.activation_record_id == EXPECTED_ACTIVATION_ID, "ACTIVE_POINTER_ACTIVATION")
    require(pinned.pointer.activation_generation_id == EXPECTED_GENERATION_ID,
            "ACTIVE_POINTER_GENERATION")
    require(pinned.admission_manifest.artifact_id == EXPECTED_RPM_ID, "ACTIVE_POINTER_RPM")
    require(pinned.validity_record.semantic_payload["state"] == "ACTIVE", "ACTIVE_VALIDITY")
    rows, contents = compatibility_c01_c09(repo, store, pinned)
    return store, pinned, rows, contents


def evidence_count(path: Path, mac: str, start: str, end: str) -> tuple[int, list[dict[str, Any]]]:
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        require(conn.execute("PRAGMA quick_check").fetchone()[0] == "ok", "EVIDENCE_DB_QUICK_CHECK")
        count = conn.execute(
            "SELECT COUNT(*) FROM device_fingerprint_evidence "
            "WHERE site_id=? AND observed_mac=? AND observed_at>=? AND observed_at<?",
            (SITE_ID, mac, start, end),
        ).fetchone()[0]
        rows = [dict(r) for r in conn.execute(
            "SELECT source_kind,COUNT(*) AS rows FROM device_fingerprint_evidence "
            "WHERE site_id=? AND observed_mac=? AND observed_at>=? AND observed_at<? "
            "GROUP BY source_kind ORDER BY source_kind",
            (SITE_ID, mac, start, end),
        )]
        return int(count), rows
    finally:
        conn.close()


def sqlite_backup(src_path: Path, dst_path: Path) -> None:
    src = sqlite3.connect(f"{src_path.resolve().as_uri()}?mode=ro", uri=True)
    dst = sqlite3.connect(dst_path)
    try:
        src.backup(dst)
        dst.commit()
        require(dst.execute("PRAGMA quick_check").fetchone()[0] == "ok", "BACKUP_QUICK_CHECK")
    finally:
        dst.close()
        src.close()


def write_json(path: Path, value: Any) -> None:
    raw=(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n").encode("utf-8")
    with path.open("xb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--verify-only", action="store_true")
    mode.add_argument("--commit", action="store_true")
    parser.add_argument("--repo", type=Path,
                        default=Path("/home/admin/CaptivePortal-Deploy/task04-dormant-fecdb5a7"))
    parser.add_argument("--control-db", type=Path,
                        default=Path("/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3"))
    parser.add_argument("--classification-db", type=Path,
                        default=Path("/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3"))
    parser.add_argument("--evidence-db", type=Path,
                        default=Path("/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3"))
    parser.add_argument("--mac")
    parser.add_argument("--window-minutes", type=int, default=15)
    parser.add_argument("--confirm", default="")
    parser.add_argument("--audit-root", type=Path,
                        default=Path("/home/admin/captivportal-recovery"))
    args=parser.parse_args()

    for path in (args.repo, args.control_db, args.classification_db, args.evidence_db):
        require(path.exists(), f"MISSING:{path}")

    control_sha_before=sha256(args.control_db)
    class_rows_before=db_count(args.classification_db, "classifications")

    store, pinned, compatibility, contents = verify_active(args.repo, args.control_db)
    print("T06A_COMPATIBILITY="+json.dumps(compatibility, sort_keys=True, separators=(",",":")))
    print("T06A_C01_C09=PASS")
    print(f"ACTIVE_CRP={pinned.runtime_profile.artifact_id}")
    print(f"ACTIVE_RPM={pinned.admission_manifest.artifact_id}")
    print(f"ACTIVE_ACTIVATION_RECORD_ID={pinned.pointer.activation_record_id}")
    print(f"CLASSIFICATION_ROWS_CURRENT={class_rows_before}")

    if args.verify_only:
        require(sha256(args.control_db) == control_sha_before, "CONTROL_DB_CHANGED_IN_VERIFY")
        require(db_count(args.classification_db, "classifications") == class_rows_before,
                "CLASS_DB_CHANGED_IN_VERIFY")
        print("FIRST_PRODUCTION_RUNNER_COMPATIBILITY_READINESS=PASS")
        print("CLASSIFICATION_EXECUTED=NO")
        return 0

    require(args.confirm == "FIRST_PRODUCTION_CLASSIFICATION",
            "EXPLICIT_CONFIRMATION_REQUIRED")
    require(args.mac is not None, "MAC_REQUIRED")
    require(2 <= args.window_minutes <= 120, "WINDOW_MINUTES_2_TO_120")
    mac=validate_mac(args.mac)
    require(class_rows_before == 0, "FIRST_PRODUCTION_DB_NOT_EMPTY")

    evaluation_dt=datetime.now(timezone.utc)
    window_end_dt=evaluation_dt - timedelta(seconds=2)
    window_start_dt=window_end_dt - timedelta(minutes=args.window_minutes)
    evaluation=format_utc(evaluation_dt)
    window_start=format_utc(window_start_dt)
    window_end=format_utc(window_end_dt)

    count, by_kind=evidence_count(args.evidence_db, mac, window_start, window_end)
    require(count > 0, "NO_CONTROLLED_DEVICE_EVIDENCE_IN_WINDOW")
    print(f"CONTROLLED_MAC={mac}")
    print(f"WINDOW_START_UTC={window_start}")
    print(f"WINDOW_END_UTC={window_end}")
    print(f"EVIDENCE_ROWS={count}")
    print("EVIDENCE_BY_SOURCE_KIND="+json.dumps(by_kind,sort_keys=True,separators=(",",":")))

    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    audit=args.audit_root / f"task04-first-production-classification-{stamp}"
    audit.mkdir(parents=True, exist_ok=False)
    backup=audit / "device_fingerprint_classification.pre-first-production.sqlite3"
    sqlite_backup(args.classification_db, backup)

    # Reuse exact artifacts that just passed C01-C09; the hook is identity-only,
    # matching the accepted T-09 execution pattern after external compatibility validation.
    def compatible(profile, foundation, bundle, _knowledge, policy, adapters, manifest):
        return (
            profile == contents["profile"]
            and foundation == contents["foundation"]
            and bundle == contents["bundle"]
            and policy == contents["policy"]
            and adapters == contents["adapter"]
            and manifest == contents["classifier"]
        )

    read=DeviceFingerprintReadService(str(args.evidence_db), retention_days=30)
    service=DeviceFingerprintRequestAssembly(
        control_plane_store=store,
        read_service=read,
        compatibility_hook=compatible,
        utc_clock=lambda: evaluation,
        process_memory_guard=current_rss_guard,
    )
    class_store=DeviceFingerprintClassificationStore(
        args.classification_db, args.evidence_db,
        control_plane_store=store,
        utc_clock=lambda: evaluation,
    )

    assembled=service.assemble_production(
        SITE_ID, mac, window_start, window_end,
    )
    require(assembled.execution_context == "PRODUCTION", "ASSEMBLY_CONTEXT")
    require(assembled.classification_runtime_profile == pinned.runtime_profile,
            "ASSEMBLY_PROFILE")
    require(
        assembled.runtime_profile_activation_record == pinned.activation_record,
        "ASSEMBLY_ACTIVATION_LINEAGE",
    )
    require(
        assembled.classification_result.semantic_payload["classification_request_digest"]
        == assembled.classification_request_manifest.content_sha256,
        "ASSEMBLY_REQUEST_RESULT_DIGEST",
    )

    precommit={
        "site_id":SITE_ID,
        "observed_mac":mac,
        "window_start_utc":window_start,
        "window_end_utc":window_end,
        "knowledge_evaluation_at_utc":assembled.knowledge_evaluation_at_utc,
        "classification_runtime_profile":ref(assembled.classification_runtime_profile),
        "runtime_profile_activation_record":ref(assembled.runtime_profile_activation_record),
        "classification_request_manifest":ref(assembled.classification_request_manifest),
        "classification_result":ref(assembled.classification_result),
        "classification_result_payload":assembled.classification_result.semantic_payload,
        "evidence_rows_precheck":count,
        "evidence_by_source_kind":by_kind,
        "compatibility_checks":compatibility,
    }
    write_json(audit/"precommit-assembly.json",precommit)

    # Atomic classification persistence. The store revalidates admission and captures
    # the pinned validity lineage immediately before commit.
    retention=build_initial_classification_retention_policy_v1()
    core=class_store.persist(assembled, retention_policy=retention)

    readback=DeviceFingerprintClassificationReadService(args.classification_db)
    current=readback.get_current(SITE_ID, mac)
    require(current is not None, "POSTCOMMIT_GET_CURRENT_NONE")
    require(current.core == core, "POSTCOMMIT_CORE_MISMATCH")
    require(current.result == assembled.classification_result, "POSTCOMMIT_RESULT_MISMATCH")
    replay=class_store.replay_level_b(core.classification_id)
    require(replay == assembled.classification_result, "LEVEL_B_REPLAY_MISMATCH")

    rows_after=db_count(args.classification_db, "classifications")
    require(rows_after == 1, f"POSTCOMMIT_ROW_COUNT:{rows_after}")
    require(sha256(args.control_db) == control_sha_before, "CONTROL_DB_CHANGED_BY_CLASSIFICATION")

    receipt={
        "status":"PASS",
        "action":"FIRST_PRODUCTION_CLASSIFICATION",
        "classification_id":core.classification_id,
        "core":asdict(core),
        "result_artifact":ref(assembled.classification_result),
        "result_payload":assembled.classification_result.semantic_payload,
        "request_artifact":ref(assembled.classification_request_manifest),
        "snapshot_record":ref(assembled.snapshot_record),
        "active_profile":ref(pinned.runtime_profile),
        "activation_record_id":pinned.pointer.activation_record_id,
        "activation_generation_id":pinned.pointer.activation_generation_id,
        "compatibility_checks":compatibility,
        "level_b_replay":"PASS",
        "get_current":"PASS",
        "classification_rows_before":class_rows_before,
        "classification_rows_after":rows_after,
        "control_db_sha256_unchanged":control_sha_before,
        "classification_db_backup":str(backup),
        "classification_db_backup_sha256":sha256(backup),
    }
    receipt_path=audit/"first-production-classification-receipt.json"
    write_json(receipt_path,receipt)

    print("FIRST_PRODUCTION_CLASSIFICATION=PASS")
    print(f"CLASSIFICATION_ID={core.classification_id}")
    print(f"CLASSIFICATION_RESULT_ID={assembled.classification_result.artifact_id}")
    print("GET_CURRENT=PASS")
    print("LEVEL_B_REPLAY=PASS")
    print("CLASSIFICATION_ROWS_AFTER=1")
    print("CONTROL_DB_UNCHANGED=PASS")
    print("RESULT_PAYLOAD="+json.dumps(
        assembled.classification_result.semantic_payload,
        sort_keys=True,separators=(",",":")))
    print(f"AUDIT_DIR={audit}")
    print(f"RECEIPT={receipt_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HarnessError as exc:
        print(f"FIRST_PRODUCTION_HARNESS=BLOCKED:{exc}", file=sys.stderr)
        raise SystemExit(2)
