#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import traceback
import urllib.request
import uuid
from datetime import datetime, timezone
from dataclasses import asdict
from pathlib import Path
from typing import Any

EXPECTED_MAIN_COMMIT = "1383e5acb8912694bde05d95ba68329ebb66a1ec"
EXPECTED_MAIN_TREE = "802a4d1fcb611232626cbcad82a3e95b3e16509d"

ACCEPTED_TAXONOMY_ID = (
    "ClassificationTaxonomy:v1:sha256:"
    "399e2a337e7ebecb1bd7a9b21dff5e744c13be36313bc39f16832bc7a57a4d10"
)
ACCEPTED_ALIAS_ID = (
    "AliasMapping:v1:sha256:"
    "f1cdd7c9510c2a33bad99bd1ae15eaccd20fcb828a52e02533b9917fdfc2e228"
)
ACCEPTED_K3_ID = (
    "K3PortalRuleSet:v1:sha256:"
    "5e47945da04c60baf8dc1d1a7777a4e2efa2dfa0e80bf7639a97ba51d6fdb28f"
)
ACCEPTED_K3_PROVENANCE_ID = (
    "KnowledgeProvenanceManifest:v1:sha256:"
    "99029f81d6ca8c2afc6d48640ac4c1f47f01c78baa2836d68dcec5d0adc28b92"
)
ACCEPTED_K3_REPO_COMMIT = "ce948017cde0b82a778bd07cc9dffe72189aa0bb"
ACCEPTED_K3_REPO_TREE = "5464f749fa119132071fa25d6dc50ea57a3aa840"

URLS = {
    "k1": (
        "https://raw.githubusercontent.com/xnih/satori/"
        "c5dfcfbff31620e35248aa86da0c67f2ad4982f5/fingerprints/dhcp.xml"
    ),
    "k2b": (
        "https://raw.githubusercontent.com/peace-maker/p0f3-database/"
        "7687e779c42c256c1f36b8c48da7e1f8fe24c2d4/p0f.fp"
    ),
    "k4_ma_l": "https://standards-oui.ieee.org/oui/oui.csv",
    "k4_ma_m": "https://standards-oui.ieee.org/oui28/mam.csv",
    "k4_ma_s": "https://standards-oui.ieee.org/oui36/oui36.csv",
}

def utc_ms() -> str:
    now = datetime.now(timezone.utc)
    ms = now.microsecond // 1000
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms:03d}Z"

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())

def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

def git(*args: str) -> str:
    p = subprocess.run(
        ["git", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if p.returncode:
        raise RuntimeError(
            "git " + " ".join(args) + " failed:\n" + p.stderr.strip()
        )
    return p.stdout.strip()

def fetch_bytes(url: str, attempts: int = 3) -> tuple[bytes, str]:
    last = None
    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "CaptivPortal-TechLead14-FE7-Real-Admission/1.0",
                    "Accept": "*/*",
                },
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            if not data:
                raise RuntimeError("empty response")
            return data, utc_ms()
        except Exception as exc:
            last = exc
            if attempt != attempts:
                time.sleep(2)
    raise RuntimeError(f"download failed: {url}: {last}")

def ref(artifact) -> dict[str, str]:
    from app.device_fingerprint.artifact_content import ArtifactRef
    return ArtifactRef(artifact.artifact_id, artifact.content_sha256).as_dict()

def artifact_dict(artifact) -> dict[str, Any]:
    return {
        "artifact_type": artifact.artifact_type,
        "artifact_schema_version": artifact.artifact_schema_version,
        "artifact_id": artifact.artifact_id,
        "content_sha256": artifact.content_sha256,
        "semantic_payload": artifact.semantic_payload,
    }

def save_artifact(root: Path, label: str, artifact) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in label)
    p = root / "artifacts" / f"{safe}.json"
    write_json(p, artifact_dict(artifact))
    return p

def evidence_ref(label: str, path: Path) -> dict[str, Any]:
    return {
        "evidence_label": label,
        "file_sha256": sha256_file(path),
        "media_type": "application/json",
        "path_or_reference": str(path),
    }

def make_ext_candidate(fe5, family: str, governance, policy, provenance):
    slot, character, caveat, _fresh, _stale = fe5._FAMILIES[family]
    return fe5.ExternalKnowledgeCandidate(
        slot,
        family,
        character,
        caveat,
        governance,
        policy,
        provenance,
    )

def verify_k4_real(record_set, match_k4_records) -> dict[str, Any]:
    records = record_set.semantic_payload["records"]
    if not records:
        raise RuntimeError("K4 record set is empty")

    expected_width = {24: 6, 28: 7, 36: 9}
    counts = {24: 0, 28: 0, 36: 0}
    for row in records:
        bits = row["prefix_length_bits"]
        prefix = row["prefix_hex"]
        if bits not in expected_width:
            raise RuntimeError("K4 invalid prefix length")
        if len(prefix) != expected_width[bits]:
            raise RuntimeError("K4 invalid prefix width")
        if prefix != prefix.lower():
            raise RuntimeError("K4 prefix is not lowercase")
        if any(c not in "0123456789abcdef" for c in prefix):
            raise RuntimeError("K4 prefix contains non-hex data")
        if row["registry_family"] != {24: "MA-L", 28: "MA-M", 36: "MA-S"}[bits]:
            raise RuntimeError("K4 registry-family mismatch")
        if row["manufacturer_mapping"] is not None:
            raise RuntimeError("K4 unexpected automatic manufacturer mapping")
        counts[bits] += 1

    if match_k4_records(record_set, "02:00:00:00:00:01") != ():
        raise RuntimeError("K4 locally-administered MAC exclusion failed")

    longest_prefix_examples = {}
    for bits in (36, 28, 24):
        candidate = next(
            (
                r for r in records
                if r["prefix_length_bits"] == bits
                and (int(r["prefix_hex"][:2], 16) & 0x02) == 0
            ),
            None,
        )
        if candidate is None:
            continue
        hex12 = (candidate["prefix_hex"] + "0" * 12)[:12]
        mac = ":".join(hex12[i:i+2] for i in range(0, 12, 2))
        matched = match_k4_records(record_set, mac)
        if not matched:
            raise RuntimeError(f"K4 no lookup result for admitted {bits}-bit prefix")
        max_bits = max(r["prefix_length_bits"] for r in matched)
        if max_bits < bits:
            raise RuntimeError("K4 longest-prefix semantics failed")
        longest_prefix_examples[str(bits)] = {
            "mac": mac,
            "matched_prefix_bits": sorted(
                {r["prefix_length_bits"] for r in matched}, reverse=True
            ),
        }

    return {
        "record_count": len(records),
        "prefix_counts": counts,
        "locally_administered_exclusion": "PASS",
        "longest_prefix_examples": longest_prefix_examples,
        "manufacturer_mapping_default": "NULL_ONLY",
    }

def verify_k2b_real(record_set) -> dict[str, Any]:
    records = record_set.semantic_payload["records"]
    if not records:
        raise RuntimeError("K2B record set is empty")
    platforms = {}
    for row in records:
        if row["rule_representation"] != "p0f_runtime_ipv4_request_v1":
            raise RuntimeError("K2B wrong rule representation")
        if row["source_character"] != "legacy":
            raise RuntimeError("K2B wrong source character")
        for claim in row["dimension_claims"]:
            dim = claim["dimension_name"]
            if dim == "platform_family":
                if claim["outcome_kind"] != "CANONICAL_VALUE":
                    raise RuntimeError("K2B platform claim not canonical")
                if claim["base_claim_strength"] != "supporting":
                    raise RuntimeError("K2B legacy platform claim exceeds supporting")
                platforms[claim["canonical_target_id"]] = (
                    platforms.get(claim["canonical_target_id"], 0) + 1
                )
            else:
                if claim["outcome_kind"] != "NO_CLAIM":
                    raise RuntimeError("K2B non-platform claim is not NO_CLAIM")
    return {"record_count": len(records), "platform_counts": platforms}

def verify_k1_real(record_set) -> dict[str, Any]:
    records = record_set.semantic_payload["records"]
    if not records:
        raise RuntimeError("K1 record set is empty")
    allowed = {
        "message_type",
        "parameter_request_list",
        "option_order",
        "vendor_class",
        "client_identifier_kind",
        "maximum_message_size",
        "rapid_commit_requested",
        "capport_requested",
        "ipv6_only_preferred_requested",
        "hostname_present",
    }
    for row in records:
        predicates = row["dhcp_predicates"]
        if set(predicates) != allowed:
            raise RuntimeError("K1 predicate field set mismatch")
    return {"record_count": len(records), "dhcp_only_predicate_contract": "PASS"}

def main() -> int:
    repo = Path.cwd()
    if not (repo / "app" / "device_fingerprint").is_dir():
        print("F_E7_REAL_ADMISSION=STOP")
        print("STOP_REASON=Run from CaptivePortal repository root")
        return 2

    subprocess.run(
        ["git", "fetch", "origin", "refs/heads/main:refs/remotes/origin/main", "--quiet"],
        check=True,
    )
    main_commit = git("rev-parse", "origin/main")
    main_tree = git("rev-parse", "origin/main^{tree}")
    head_tree = git("rev-parse", "HEAD^{tree}")
    if main_commit != EXPECTED_MAIN_COMMIT or main_tree != EXPECTED_MAIN_TREE:
        print("F_E7_REAL_ADMISSION=STOP")
        print(f"STOP_REASON=origin/main identity changed: {main_commit} / {main_tree}")
        return 3
    if head_tree != main_tree:
        print("F_E7_REAL_ADMISSION=STOP")
        print(f"STOP_REASON=working code tree differs from accepted main tree: {head_tree}")
        return 4
    if git("status", "--short"):
        print("F_E7_REAL_ADMISSION=STOP")
        print("STOP_REASON=working tree is not clean")
        return 5

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = Path(r"C:\CaptivPortal-Lab\artifacts") / f"fe7-real-admission-{stamp}"
    (out / "artifacts").mkdir(parents=True, exist_ok=False)

    from app.device_fingerprint import fe5_external_knowledge as fe5
    from app.device_fingerprint.fe7_knowledge_bundle import run_fe7_knowledge_bundle_gate
    from app.device_fingerprint.k1_satori_import import (
        ACCEPTED_SATORI_AUDIT,
        SATORI_SOURCE_SHA256,
        build_satori_source_governance_candidate,
        import_satori_dhcp_bytes,
    )
    from app.device_fingerprint.k2b_p0f_import import (
        ACCEPTED_P0F_AUDIT,
        build_p0f_k2b_source_governance_candidate,
        import_p0f_k2b_bytes,
    )
    from app.device_fingerprint.k4_ieee_import import (
        build_ieee_k4_source_governance_candidate,
        compute_ieee_k4_source_bundle_sha256,
        import_ieee_k4_bytes,
        match_k4_records,
    )
    from app.device_fingerprint.taxonomy_artifacts import (
        build_alias_mapping_v1,
        build_classification_taxonomy_v1,
    )
    from app.device_fingerprint.k3_portal_rules import (
        build_k3_internal_provenance,
        build_k3_portal_rule_set_v1,
    )
    from app.device_fingerprint.knowledge_bundle import KnowledgeBundleCandidate

    # Owner authorization is already explicit; record it now, do not backdate it.
    decision_ids = {
        "F-E1": str(uuid.uuid4()),
        "F-E2": str(uuid.uuid4()),
        "F-E4": str(uuid.uuid4()),
        "F-E5": str(uuid.uuid4()),
        "F-E7": str(uuid.uuid4()),
    }
    decision_file = out / "owner-decisions.json"
    write_json(decision_file, {
        "recorded_at_utc": utc_ms(),
        "owner_authorization_basis": (
            "Owner explicitly authorized continuation of F-E7/F-ADMIT work in "
            "CaptivPortal TechLead14 conversation; no backdating."
        ),
        "decision_records": [
            {
                "decision_record_id": decision_ids[gate],
                "gate_id": gate,
                "decision": "ACCEPT_IF_GATE_PROOF_PASS",
            }
            for gate in ("F-E1", "F-E2", "F-E4", "F-E5", "F-E7")
        ],
    })

    # Current authoritative/pinned source retrieval. Raw bytes stay in memory only.
    k1_bytes, k1_retrieved = fetch_bytes(URLS["k1"])
    k2b_bytes, k2b_retrieved = fetch_bytes(URLS["k2b"])
    ma_l, k4_l_retrieved = fetch_bytes(URLS["k4_ma_l"])
    ma_m, k4_m_retrieved = fetch_bytes(URLS["k4_ma_m"])
    ma_s, k4_s_retrieved = fetch_bytes(URLS["k4_ma_s"])
    k4_retrieved = max(k4_l_retrieved, k4_m_retrieved, k4_s_retrieved)

    source_evidence_file = out / "source-retrieval-evidence.json"
    write_json(source_evidence_file, {
        "repository_commit": main_commit,
        "repository_tree": main_tree,
        "retrieved": {
            "k1_satori": {
                "url": URLS["k1"],
                "retrieved_at_utc": k1_retrieved,
                "sha256": sha256_bytes(k1_bytes),
                "size_bytes": len(k1_bytes),
            },
            "k2b_p0f": {
                "url": URLS["k2b"],
                "retrieved_at_utc": k2b_retrieved,
                "sha256": sha256_bytes(k2b_bytes),
                "size_bytes": len(k2b_bytes),
            },
            "k4_ieee": {
                "retrieved_at_utc": k4_retrieved,
                "bundle_sha256": compute_ieee_k4_source_bundle_sha256(ma_l, ma_m, ma_s),
                "members": [
                    {
                        "family": "MA-L", "url": URLS["k4_ma_l"],
                        "sha256": sha256_bytes(ma_l), "size_bytes": len(ma_l),
                        "retrieved_at_utc": k4_l_retrieved,
                    },
                    {
                        "family": "MA-M", "url": URLS["k4_ma_m"],
                        "sha256": sha256_bytes(ma_m), "size_bytes": len(ma_m),
                        "retrieved_at_utc": k4_m_retrieved,
                    },
                    {
                        "family": "MA-S", "url": URLS["k4_ma_s"],
                        "sha256": sha256_bytes(ma_s), "size_bytes": len(ma_s),
                        "retrieved_at_utc": k4_s_retrieved,
                    },
                ],
            },
        },
        "raw_source_retention": "NO_RAW_SOURCE_WRITTEN_BY_RUNNER",
    })

    # F-E1 real candidate.
    k1_gov = build_satori_source_governance_candidate()
    k1_policy = fe5.build_satori_k1_freshness_policy()
    k1_prov = fe5.build_satori_k1_external_provenance(
        k1_bytes,
        retrieved_at_utc=k1_retrieved,
        governance=k1_gov,
        freshness_policy=k1_policy,
    )
    k1_import = import_satori_dhcp_bytes(k1_bytes, ref(k1_prov))
    if k1_import.audit != ACCEPTED_SATORI_AUDIT:
        raise RuntimeError("F-E1 accepted Satori import audit mismatch")
    k1_proof = verify_k1_real(k1_import.record_set)

    # F-E2 real candidate.
    k2b_gov = build_p0f_k2b_source_governance_candidate(k2b_bytes)
    k2b_policy = fe5.build_p0f_k2b_freshness_policy()
    k2b_prov = fe5.build_p0f_k2b_external_provenance(
        k2b_bytes,
        retrieved_at_utc=k2b_retrieved,
        governance=k2b_gov,
        freshness_policy=k2b_policy,
    )
    k2b_import = import_p0f_k2b_bytes(k2b_bytes, ref(k2b_prov))
    if k2b_import.audit != ACCEPTED_P0F_AUDIT:
        raise RuntimeError("F-E2 accepted p0f import audit mismatch")
    k2b_proof = verify_k2b_real(k2b_import.record_set)

    # F-E4 real candidate.
    k4_gov = build_ieee_k4_source_governance_candidate()
    k4_policy = fe5.build_ieee_k4_freshness_policy()
    k4_prov = fe5.build_ieee_k4_external_provenance(
        ma_l, ma_m, ma_s,
        retrieved_at_utc=k4_retrieved,
        governance=k4_gov,
        freshness_policy=k4_policy,
    )
    k4_record_set = import_ieee_k4_bytes(
        ma_l, ma_m, ma_s, knowledge_provenance=ref(k4_prov)
    )
    k4_proof = verify_k4_real(k4_record_set, match_k4_records)

    reattestation_file = out / "knowledge-source-reattestation.json"
    write_json(reattestation_file, {
        "status": "PASS",
        "repository_commit": main_commit,
        "repository_tree": main_tree,
        "F-E1": {
            "status": "PASS",
            "owner_decision_ref": decision_ids["F-E1"],
            "source_sha256": SATORI_SOURCE_SHA256,
            "import_audit": asdict(k1_import.audit),
            "proof": k1_proof,
        },
        "F-E2": {
            "status": "PASS",
            "owner_decision_ref": decision_ids["F-E2"],
            "source_sha256": k2b_import.source_sha256,
            "import_audit": asdict(k2b_import.audit),
            "proof": k2b_proof,
        },
        "F-E4": {
            "status": "PASS",
            "owner_decision_ref": decision_ids["F-E4"],
            "source_bundle_sha256": k4_prov.semantic_payload["source_artifact_sha256"],
            "proof": k4_proof,
        },
        "note": (
            "Bounded current Owner/TechLead source re-attestation using frozen production "
            "importers and exact real source bytes. No full-suite rerun."
        ),
    })

    base_evidence = [
        evidence_ref("fe7_current_source_retrieval", source_evidence_file),
        evidence_ref("fe1_fe2_fe4_current_reattestation", reattestation_file),
        evidence_ref("owner_decisions", decision_file),
    ]

    # Official F-E5. This function captures the trusted clock internally.
    k1_candidate = make_ext_candidate(fe5, "satori_dhcp", k1_gov, k1_policy, k1_prov)
    k2b_candidate = make_ext_candidate(fe5, "p0f3_legacy_tcp", k2b_gov, k2b_policy, k2b_prov)
    k4_candidate = make_ext_candidate(fe5, "ieee_ra_mac", k4_gov, k4_policy, k4_prov)

    fe5_result = fe5.run_fe5_external_admission_gate(
        k1_candidate,
        k2b_candidate,
        k4_candidate,
        candidate_repository_commit_sha=main_commit,
        candidate_repository_tree_sha=main_tree,
        environment_identity="Windows-Central-Lab-TechLead14-real-knowledge-admission",
        retained_evidence_refs=base_evidence,
        decision_record_refs=[
            decision_ids["F-E1"],
            decision_ids["F-E2"],
            decision_ids["F-E4"],
            decision_ids["F-E5"],
        ],
    )
    fe5_gate_file = save_artifact(out, "F-E5-gate-result", fe5_result.gate_result_manifest)
    if fe5_result.gate_result_manifest.semantic_payload["status"] != "PASS":
        write_json(out / "STOP.json", {
            "stage": "F-E5",
            "failure_reasons": list(fe5_result.failure_reasons),
            "trusted_time": fe5_result.foundation_knowledge_evaluation_at_utc,
            "per_source": list(fe5_result.per_source),
        })
        print("F_E7_REAL_ADMISSION=STOP")
        print("STOP_STAGE=F-E5")
        print("F_E5_FAILURE_REASONS=" + ",".join(fe5_result.failure_reasons))
        print("OUTPUT_DIR=" + str(out))
        return 20

    # Accepted taxonomy / aliases / K3 lineage.
    taxonomy = build_classification_taxonomy_v1()
    aliases = build_alias_mapping_v1()
    if taxonomy.artifact_id != ACCEPTED_TAXONOMY_ID:
        raise RuntimeError("accepted taxonomy identity mismatch")
    if aliases.artifact_id != ACCEPTED_ALIAS_ID:
        raise RuntimeError("accepted alias identity mismatch")

    k3_rules = build_k3_portal_rule_set_v1()
    if k3_rules.artifact_id != ACCEPTED_K3_ID:
        raise RuntimeError("accepted K3 rule-set identity mismatch")
    k3_prov = build_k3_internal_provenance(
        k3_rules,
        repository_commit_sha=ACCEPTED_K3_REPO_COMMIT,
        repository_tree_sha=ACCEPTED_K3_REPO_TREE,
        taxonomy_compatibility=ref(taxonomy),
    )
    if k3_prov.artifact_id != ACCEPTED_K3_PROVENANCE_ID:
        raise RuntimeError("accepted K3 provenance identity mismatch")

    bundle_candidate = KnowledgeBundleCandidate(
        taxonomy,
        aliases,
        k1_import.record_set,
        k1_prov,
        k1_gov,
        k1_policy,
        k2b_import.record_set,
        k2b_prov,
        k2b_gov,
        k2b_policy,
        k3_rules,
        k3_prov,
        k4_record_set,
        k4_prov,
        k4_gov,
        k4_policy,
    )

    fe7_evidence = base_evidence + [
        evidence_ref("F-E5_PASS_GateResultManifest", fe5_gate_file),
    ]
    fe7_result = run_fe7_knowledge_bundle_gate(
        bundle_candidate,
        foundation_knowledge_evaluation_at_utc=fe5_result.foundation_knowledge_evaluation_at_utc,
        candidate_repository_commit_sha=main_commit,
        candidate_repository_tree_sha=main_tree,
        environment_identity="Windows-Central-Lab-TechLead14-real-knowledge-admission",
        retained_evidence_refs=fe7_evidence,
        decision_record_refs=[decision_ids["F-E7"]],
    )

    fe7_gate_file = save_artifact(out, "F-E7-gate-result", fe7_result.gate_result_manifest)
    if fe7_result.gate_result_manifest.semantic_payload["status"] != "PASS":
        write_json(out / "STOP.json", {
            "stage": "F-E7",
            "failure_reasons": list(fe7_result.failure_reasons),
            "foundation_knowledge_evaluation_at_utc": (
                fe5_result.foundation_knowledge_evaluation_at_utc
            ),
            "per_source": list(fe7_result.per_source),
        })
        print("F_E7_REAL_ADMISSION=STOP")
        print("STOP_STAGE=F-E7")
        print("F_E7_FAILURE_REASONS=" + ",".join(fe7_result.failure_reasons))
        print("OUTPUT_DIR=" + str(out))
        return 21

    # Persist all immutable dependencies and final bundle.
    artifacts = {
        "classification-taxonomy": taxonomy,
        "alias-mapping": aliases,
        "k1-governance": k1_gov,
        "k1-freshness-policy": k1_policy,
        "k1-provenance": k1_prov,
        "k1-record-set": k1_import.record_set,
        "k2b-governance": k2b_gov,
        "k2b-freshness-policy": k2b_policy,
        "k2b-provenance": k2b_prov,
        "k2b-record-set": k2b_import.record_set,
        "k3-rule-set": k3_rules,
        "k3-provenance": k3_prov,
        "k4-governance": k4_gov,
        "k4-freshness-policy": k4_policy,
        "k4-provenance": k4_prov,
        "k4-record-set": k4_record_set,
        "knowledge-bundle": __import__(
            "app.device_fingerprint.knowledge_bundle",
            fromlist=["build_initial_knowledge_bundle_v1"],
        ).build_initial_knowledge_bundle_v1(bundle_candidate),
    }

    inventory = []
    for label, artifact in artifacts.items():
        p = save_artifact(out, label, artifact)
        inventory.append({
            "label": label,
            "artifact_id": artifact.artifact_id,
            "content_sha256": artifact.content_sha256,
            "file": str(p),
            "file_sha256": sha256_file(p),
        })

    bundle = artifacts["knowledge-bundle"]
    if bundle.artifact_id != fe7_result.knowledge_bundle_artifact_id:
        raise RuntimeError("persisted bundle identity does not match F-E7 output")

    write_json(out / "accepted-artifact-inventory.json", inventory)
    summary = {
        "F_E1_REATTESTATION": "PASS",
        "F_E2_REATTESTATION": "PASS",
        "F_E4_REATTESTATION": "PASS",
        "F_E5_STATUS": "PASS",
        "F_E7_STATUS": "PASS",
        "repository_commit": main_commit,
        "repository_tree": main_tree,
        "foundation_knowledge_evaluation_at_utc": (
            fe5_result.foundation_knowledge_evaluation_at_utc
        ),
        "F_E5_gate_result_manifest": fe5_result.gate_result_manifest.artifact_id,
        "F_E7_gate_result_manifest": fe7_result.gate_result_manifest.artifact_id,
        "KnowledgeBundle": bundle.artifact_id,
        "KnowledgeBundle_content_sha256": bundle.content_sha256,
        "F_E7_input_ref_count": len(
            fe7_result.gate_result_manifest.semantic_payload["input_artifact_refs"]
        ),
        "F_E7_output_ref_count": len(
            fe7_result.gate_result_manifest.semantic_payload["output_artifact_refs"]
        ),
        "dependency_validation_passed": fe7_result.dependency_validation_passed,
        "double_build_equal": (
            fe7_result.build_1_artifact_id == fe7_result.build_2_artifact_id
            and fe7_result.build_1_content_sha256 == fe7_result.build_2_content_sha256
        ),
        "per_source": list(fe7_result.per_source),
        "owner_decision_refs": decision_ids,
        "FULL_TEST_SUITE_RERUN": "NO",
        "CENTRAL_LAB_RERUN": "NO",
        "F_ADMIT_RUN": "NO",
        "PRODUCTION_ACTION": "NO",
        "output_dir": str(out),
    }
    write_json(out / "acceptance-summary.json", summary)

    print("============================================================")
    print("PASS: REAL F-E7 KNOWLEDGE ADMISSION")
    print("============================================================")
    print("F_E1_REATTESTATION=PASS")
    print("F_E2_REATTESTATION=PASS")
    print("F_E4_REATTESTATION=PASS")
    print("F_E5_STATUS=PASS")
    print("F_E7_STATUS=PASS")
    print("FOUNDATION_KNOWLEDGE_EVALUATION_AT_UTC=" +
          fe5_result.foundation_knowledge_evaluation_at_utc)
    print("F_E5_GATE_MANIFEST=" + fe5_result.gate_result_manifest.artifact_id)
    print("F_E7_GATE_MANIFEST=" + fe7_result.gate_result_manifest.artifact_id)
    print("KNOWLEDGE_BUNDLE=" + bundle.artifact_id)
    print("F_E7_INPUT_REF_COUNT=" + str(summary["F_E7_input_ref_count"]))
    print("F_E7_OUTPUT_REF_COUNT=" + str(summary["F_E7_output_ref_count"]))
    print("DEPENDENCY_VALIDATION=PASS")
    print("DOUBLE_BUILD=PASS")
    print("FULL_TEST_SUITE_RERUN=NO")
    print("CENTRAL_LAB_RERUN=NO")
    print("F_ADMIT_RUN=NO")
    print("PRODUCTION_ACTION=NO")
    print("OUTPUT_DIR=" + str(out))
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        print("F_E7_REAL_ADMISSION=STOP")
        print("STOP_STAGE=UNHANDLED")
        traceback.print_exc()
        raise SystemExit(99)
