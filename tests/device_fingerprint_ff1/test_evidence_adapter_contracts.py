"""F-F1 contract-only fixtures; no classifier, external corpus, or production access."""

from __future__ import annotations

from copy import deepcopy
from inspect import signature

import pytest

from app.device_fingerprint.artifact_content import ArtifactRef, make_artifact_content
from app.device_fingerprint.evidence_adapter_contracts import (
    DIMENSIONS, NON_FUSION_REASON_BY_ADAPTER_CONTRACT_ID, PROJECTION_IDS,
    TCP_SYN_V1_NON_FUSION_REASON, _AdapterRegistryCompatibilityError, _TCP_V2_FIELDS,
    build_initial_evidence_adapter_contract_set_v1,
    make_evidence_adapter_contract_set, task01_contract_claim_eligible,
    validate_evidence_adapter_contract_set_dependencies,
)
from app.device_fingerprint.ff1_evidence_adapter_contracts import run_ff1_evidence_adapter_contract_gate
from app.device_fingerprint.foundation_schema_artifacts import build_foundation_schema_artifacts
from app.device_fingerprint.k2a_conformance_artifacts import build_k2a_conformance_package
from app.device_fingerprint.k3_portal_rules import build_k3_portal_rule_set_v1
from app.device_fingerprint.knowledge_artifacts import make_canonical_k4_record_set
from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.network_schemas import _TCP_V2_KEYS
from app.device_fingerprint.portal_schemas import PORTAL_HEADER_KEYS, PORTAL_HEADER_V2_KEYS
from research.device_fingerprint_fe1.fixtures import build_k1_fixture_definitions

_COMMIT = "c5f13b3c6bb750381611aba330de0c0281765b05"
_TREE = "3afa284d4fc0955488293b8e12b7f5721a443606"
_EVIDENCE = [{"evidence_label": "synthetic-ff1", "file_sha256": "e" * 64,
              "media_type": "application/json", "path_or_reference": "test://ff1"}]


def _refs():
    schema = build_foundation_schema_artifacts()
    registry = schema["EvidenceSchemaRegistryContract"]
    k1 = build_k1_fixture_definitions()["all_any"]["record_set"]
    provenance = ArtifactRef("KnowledgeProvenanceManifest:v1:sha256:" + "a" * 64, "a" * 64)
    k4 = make_canonical_k4_record_set({
        "record_set_contract_version": 1, "knowledge_slot": "K4",
        "knowledge_provenance": provenance.as_dict(),
        "records": [{
            "record_type": "K4_IEEE_ASSIGNMENT", "canonical_record_id": "synthetic-k4",
            "prefix_hex": "001122", "prefix_length_bits": 24,
            "assignment_org_id": "synthetic-org", "assignment_org_label": "Synthetic Org",
            "registry_family": "MA-L", "source_record_identity": "synthetic-source",
            "manufacturer_mapping": None,
        }],
    })
    return {
        "evidence_schema_registry": registry,
        "capability_disposition": schema["CapabilityDisposition"],
        "k2a_conformance_package": build_k2a_conformance_package(),
        "k1_record_set": k1,
        "k3_portal_rule_set": build_k3_portal_rule_set_v1(),
        "k4_record_set": k4,
    }


def _entries():
    refs = _refs()
    return build_initial_evidence_adapter_contract_set_v1(
        refs["evidence_schema_registry"]).semantic_payload["adapter_entries"]


def _entry(source: str, version: int):
    return next(row for row in _entries() if row.get("source_kind") == source
                and row.get("feature_schema_version") == version)


def _gate(candidate=None, **changes):
    refs = _refs()
    refs.update(changes)
    if candidate is None:
        candidate = build_initial_evidence_adapter_contract_set_v1(refs["evidence_schema_registry"])
    return run_ff1_evidence_adapter_contract_gate(
        candidate, **refs, candidate_repository_commit_sha=_COMMIT,
        candidate_repository_tree_sha=_TREE, environment_identity="synthetic-ff1",
        retained_evidence_refs=_EVIDENCE,
    )


def _changed_entry(source: str, version: int, field: str, value):
    payload = build_initial_evidence_adapter_contract_set_v1(
        _refs()["evidence_schema_registry"]).semantic_payload
    row = next(row for row in payload["adapter_entries"] if row.get("source_kind") == source
               and row.get("feature_schema_version") == version)
    row[field] = value
    return payload


def _disposition_configuration(status: str, *, fallback_source_kind=None,
                               fallback_feature_schema_version=None, reason_codes=None,
                               remove_v1=False, remove_v2=False):
    refs = _refs()
    disposition = refs["capability_disposition"].semantic_payload
    disposition.update(status=status, fallback_source_kind=fallback_source_kind,
                       fallback_feature_schema_version=fallback_feature_schema_version,
                       reason_codes=[] if reason_codes is None else reason_codes)
    new_disposition = make_artifact_content("CapabilityDisposition", disposition)
    registry = refs["evidence_schema_registry"].semantic_payload
    registry["portal_headers_v2_disposition"] = ArtifactRef(
        new_disposition.artifact_id, new_disposition.content_sha256).as_dict()
    registry["schema_entries"] = [row for row in registry["schema_entries"]
                                  if not (row["source_kind"] == "portal_headers" and (
                                      remove_v1 and row["feature_schema_version"] == 1 or
                                      remove_v2 and row["feature_schema_version"] == 2))]
    new_registry = make_artifact_content("EvidenceSchemaRegistryContract", registry)
    payload = build_initial_evidence_adapter_contract_set_v1(new_registry).semantic_payload
    payload["adapter_entries"] = [row for row in payload["adapter_entries"]
                                  if not (row.get("source_kind") == "portal_headers" and (
                                      remove_v1 and row.get("feature_schema_version") == 1 or
                                      remove_v2 and row.get("feature_schema_version") == 2))]
    candidate = make_evidence_adapter_contract_set(payload)
    return candidate, refs | {"evidence_schema_registry": new_registry,
                              "capability_disposition": new_disposition}


def test_initial_exact_matrix_registry_and_gate_pass():
    refs = _refs()
    candidate = build_initial_evidence_adapter_contract_set_v1(refs["evidence_schema_registry"])
    payload = candidate.semantic_payload
    assert set(payload) == {"adapter_contract_set_version", "evidence_schema_registry", "adapter_entries"}
    assert payload["adapter_contract_set_version"] == 1
    assert len(payload["adapter_entries"]) == 8
    assert len([row for row in payload["adapter_entries"] if row["adapter_kind"] == "MAC_REGISTRY"]) == 1
    assert len([row for row in payload["adapter_entries"] if row["adapter_kind"] == "TASK01_EVIDENCE"]) == 7
    assert validate_evidence_adapter_contract_set_dependencies(candidate, **refs)
    result = _gate(candidate)
    manifest = result.gate_result_manifest.semantic_payload
    assert manifest["status"] == "PASS", result.failure_reasons
    assert len(manifest["input_artifact_refs"]) == 6
    assert len(manifest["output_artifact_refs"]) == 1
    assert manifest["decision_record_refs"] == []
    assert all(value is None for value in manifest["trusted_time_inputs"].values())
    assert result.double_build_bytes_equal and result.permutation_invariant
    assert result.failure_reasons == ()


def test_initial_artifact_identity_is_unchanged_by_code_level_fix():
    registry = _refs()["evidence_schema_registry"]
    candidate = build_initial_evidence_adapter_contract_set_v1(registry)
    digest = "7cca6802ebc5839317643dcb584173b75d985477da687ab0d8fe5802b181f788"
    assert candidate.artifact_id == "EvidenceAdapterContractSet:v1:sha256:" + digest
    assert candidate.content_sha256 == digest


def test_exact_tcp_v1_non_fusion_reason_is_immutable_interpretation_metadata_only():
    assert TCP_SYN_V1_NON_FUSION_REASON == "legacy_tcp_schema_insufficient_for_exact_k2a_contract"
    assert dict(NON_FUSION_REASON_BY_ADAPTER_CONTRACT_ID) == {
        "ff1.tcp_syn.1.legacy-nonfusion.v1": TCP_SYN_V1_NON_FUSION_REASON,
    }
    with pytest.raises(TypeError):
        NON_FUSION_REASON_BY_ADAPTER_CONTRACT_ID["other"] = "changed"
    row = _entry("tcp_syn", 1)
    assert row["adapter_contract_id"] in NON_FUSION_REASON_BY_ADAPTER_CONTRACT_ID
    assert row["legacy_current_role"] == "LEGACY_NON_FUSION"
    assert row["quality_valid_behavior"] == "AUDIT_ONLY_NO_CLAIM"
    candidate = build_initial_evidence_adapter_contract_set_v1(_refs()["evidence_schema_registry"])
    assert "legacy_tcp_schema_insufficient_for_exact_k2a_contract" not in candidate.semantic_payload_json.decode()
    assert candidate.content_sha256 == "7cca6802ebc5839317643dcb584173b75d985477da687ab0d8fe5802b181f788"


def test_initial_entries_freeze_exact_protocol_metadata_and_projection_ids():
    expected = {
        ("dhcp", 1): ("ff1.dhcp.1.k1.v1", "dhcp", "EVALUATE_K1_CANDIDATE_SET", PROJECTION_IDS[0]),
        ("tcp_syn", 1): ("ff1.tcp_syn.1.legacy-nonfusion.v1", "tcp", "AUDIT_ONLY_NO_CLAIM", PROJECTION_IDS[1]),
        ("tcp_syn", 2): ("ff1.tcp_syn.2.k2a-k2b.v1", "tcp", "EVALUATE_K2A_K2B", PROJECTION_IDS[2]),
        ("tls_client", 1): ("ff1.tls_client.1.ja4-audit.v1", "tls", "AUDIT_ONLY_NO_JA4_SEMANTIC_CLAIM", PROJECTION_IDS[3]),
        ("quic_client", 1): ("ff1.quic_client.1.ja4-audit.v1", "quic", "AUDIT_ONLY_NO_JA4_SEMANTIC_CLAIM", PROJECTION_IDS[4]),
        ("portal_headers", 1): ("ff1.portal_headers.1.k3.v1", "portal", "EVALUATE_K3_RULE_SET", PROJECTION_IDS[5]),
        ("portal_headers", 2): ("ff1.portal_headers.2.k3.v1", "portal", "EVALUATE_K3_RULE_SET", PROJECTION_IDS[5]),
    }
    assert {(row["source_kind"], row["feature_schema_version"]):
            (row["adapter_contract_id"], row["origin_group"], row["quality_valid_behavior"],
             row["semantic_projection_id"])
            for row in _entries() if row["adapter_kind"] == "TASK01_EVIDENCE"} == expected
    assert set(expected) == {(row["source_kind"], row["feature_schema_version"])
                             for row in _refs()["evidence_schema_registry"].semantic_payload["schema_entries"]}


@pytest.mark.parametrize("source,version,subtypes,extractors,versions,role", [
    ("dhcp", 1, ["decline", "discover", "inform", "release", "request"], ["packet-dhcp"], ["1.0.0"], "CURRENT"),
    ("tcp_syn", 1, ["ipv4"], [], [], "LEGACY_NON_FUSION"),
    ("tcp_syn", 2, ["ipv4"], ["packet-tcp-syn"], ["2.0.0"], "CURRENT"),
    ("tls_client", 1, ["client_hello"], ["suricata-tls-ja4"], ["8.0.6"], "CURRENT"),
    ("quic_client", 1, ["client_hello"], ["suricata-quic-ja4"], ["8.0.6"], "CURRENT"),
    ("portal_headers", 1, ["capport_login", "omada_external_portal"], ["portal-http-parser"], ["1.0.0"], "LEGACY_SUPPORTED"),
    ("portal_headers", 2, ["capport_login", "omada_external_portal"], ["portal-http-parser"], ["1.0.0"], "CURRENT"),
])
def test_exact_metadata_and_quality(source, version, subtypes, extractors, versions, role):
    row = _entry(source, version)
    assert (row["supported_source_subtypes"], row["extractor_name_constraints"],
            row["extractor_version_constraints"], row["legacy_current_role"]) == (
                subtypes, extractors, versions, role)
    assert row["rule_version_constraints"] == []
    assert row["quality_partial_behavior"] == "SUPPORTING_CAP_IF_REQUIRED_FIELDS_PRESENT"
    assert row["quality_degraded_behavior"] == "NO_CLAIM"
    assert row["base_claim_strength_ceiling"] == "supporting"
    assert row["unsupported_behavior"] == "UNSUPPORTED_EVIDENCE_CONTRACT_NO_CLAIM"


def test_exact_required_fields_and_non_fusion_paths():
    assert _entry("dhcp", 1)["required_fields_by_dimension"] == {
        "platform_family": ["message_type", "option_order", "parameter_request_list", "vendor_class"],
        "device_class": ["message_type", "option_order", "parameter_request_list", "vendor_class"],
        "manufacturer_family": [], "model_family": [],
    }
    assert _entry("tcp_syn", 2)["required_fields_by_dimension"]["platform_family"] == list(_TCP_V2_FIELDS)
    assert set(_TCP_V2_FIELDS) == _TCP_V2_KEYS
    assert all(_entry("tcp_syn", 2)["required_fields_by_dimension"][name] == []
               for name in DIMENSIONS if name != "platform_family")
    assert _entry("portal_headers", 1)["required_fields_by_dimension"]["platform_family"] == [
        "platform_family", "platform_source", "sec_ch_ua_platform_present", "ua_present"]
    assert _entry("portal_headers", 2)["required_fields_by_dimension"]["device_class"] == [
        "form_factor_desktop", "form_factor_tablet", "form_factors_source"]
    assert set(_entry("portal_headers", 1)["required_fields_by_dimension"]["platform_family"]) <= PORTAL_HEADER_KEYS
    assert set(_entry("portal_headers", 2)["required_fields_by_dimension"]["device_class"]) <= PORTAL_HEADER_V2_KEYS
    for source in ("tls_client", "quic_client"):
        assert all(not fields for fields in _entry(source, 1)["required_fields_by_dimension"].values())
    assert all(not fields for fields in _entry("tcp_syn", 1)["required_fields_by_dimension"].values())
    assert _entry("tcp_syn", 1)["semantic_projection_id"] == "tcp.legacy-nonfusion.no-claim.v1"


def test_k3_rule_level_derivation_and_no_shortcut_routes():
    k3 = _refs()["k3_portal_rule_set"].semantic_payload
    rules = k3["rules"]
    declared = next(row for row in rules if row["rule_id"].endswith("android.sec_ch_ua_platform.v1"))
    mapped = next(row for row in rules if row["rule_id"].endswith("android.user_agent.v1"))
    tablet = next(row for row in rules if row["dimension_name"] == "device_class")
    assert _entry("portal_headers", 1)["claim_derivation"] == "deterministic_mapping"
    assert (declared["claim_derivation"], mapped["claim_derivation"]) == ("declared", "deterministic_mapping")
    assert (tablet["claim_derivation"], tablet["base_claim_strength"], tablet["outcome_id_or_ref"]) == (
        "declared", "supporting", "tablet")
    assert {p["field_name"] for p in tablet["input_predicates"]} == {
        "form_factor_tablet", "form_factor_desktop", "form_factors_source"}
    assert not any(p["field_name"] in {"mobile_boolean", "form_factor_mobile", "browser_runtime_family",
                                          "model_family", "os_major"}
                   for row in rules for p in row["input_predicates"])
    no_class_vectors = {row["test_vector_id"]: row for row in k3["test_vectors"]
                        if row["test_vector_id"] in {
                            "k3.vector.mobile_boolean.no_class.v1",
                            "k3.vector.mobile_form_factor.no_class.v2",
                            "k3.vector.desktop_form_factor.no_class.v2",
                            "k3.vector.unknown_model_ch.no_claim.v2",
                        }}
    assert len(no_class_vectors) == 4
    assert all(row["expected_rule_ids"] == [] for row in no_class_vectors.values())


def test_mac_registry_exact_semantics_and_no_task01_fields():
    row = next(row for row in _entries() if row["adapter_kind"] == "MAC_REGISTRY")
    assert row == {
        "adapter_kind": "MAC_REGISTRY", "adapter_contract_id": "ff1.mac_registry.k4.v1",
        "origin_group": "mac_registry", "input_observed_mac_source": "EvidenceSnapshotContent.observed_mac",
        "knowledge_slot": "K4", "locally_administered_behavior": "NO_IEEE_CLAIM",
        "globally_administered_match_mode": "MA_S_M_L_LONGEST_PREFIX",
        "raw_result_semantic": "mac_assignment_org",
        "manufacturer_mapping_mode": "EXPLICIT_ADMITTED_ASSIGNMENT_ORG_TO_MANUFACTURER_ONLY",
        "platform_claim_mode": "NO_CLAIM", "device_class_claim_mode": "NO_CLAIM",
        "model_claim_mode": "NO_CLAIM", "claim_derivation": "registry_mapping",
        "base_claim_strength_ceiling": "supporting",
        "semantic_projection_id": "mac.k4.semantic-outcomes.v1",
    }


def test_partial_degraded_and_metadata_contract_eligibility():
    row = _entry("dhcp", 1)
    kwargs = {"source_kind": "dhcp", "feature_schema_version": 1, "source_subtype": "request",
              "extractor_name": "packet-dhcp", "extractor_version": "1.0.0",
              "rule_version": None, "quality_state": "partial",
              "normalized_payload": {name: 1 for name in row["required_fields_by_dimension"]["platform_family"]},
              "dimension_name": "platform_family"}
    assert task01_contract_claim_eligible(row, **kwargs)
    assert not task01_contract_claim_eligible(row, **(kwargs | {"normalized_payload": {}}))
    assert not task01_contract_claim_eligible(row, **(kwargs | {"quality_state": "degraded"}))
    assert not task01_contract_claim_eligible(row, **(kwargs | {"dimension_name": "manufacturer_family"}))
    for changed in ({"source_subtype": "unknown"}, {"extractor_name": "wrong"},
                    {"extractor_version": "9"}, {"rule_version": "1"},
                    {"feature_schema_version": 2}, {"source_kind": "tls_client"}):
        assert not task01_contract_claim_eligible(row, **(kwargs | changed))
    assert not task01_contract_claim_eligible(_entry("tcp_syn", 1), **(
        kwargs | {"source_kind": "tcp_syn", "source_subtype": "ipv4", "extractor_name": "",
                  "extractor_version": "", "dimension_name": "platform_family"}))
    tcp = _entry("tcp_syn", 2)
    tcp_kwargs = kwargs | {
        "source_kind": "tcp_syn", "feature_schema_version": 2, "source_subtype": "ipv4",
        "extractor_name": "packet-tcp-syn", "extractor_version": "2.0.0",
        "normalized_payload": {field: 0 for field in _TCP_V2_FIELDS},
    }
    assert task01_contract_claim_eligible(tcp, **tcp_kwargs)
    missing = dict(tcp_kwargs["normalized_payload"])
    missing.pop("tcp_ns")
    assert not task01_contract_claim_eligible(tcp, **(tcp_kwargs | {"normalized_payload": missing}))


@pytest.mark.parametrize("mutation", [
    lambda p: p.update(extra=True),
    lambda p: p.pop("evidence_schema_registry"),
    lambda p: p["adapter_entries"].append(deepcopy(p["adapter_entries"][0])),
    lambda p: p["adapter_entries"][0].update(adapter_kind="UNKNOWN"),
    lambda p: p["adapter_entries"][0].update(origin_group="mac_registry"),
    lambda p: p["adapter_entries"][0].update(source_kind="tls_client"),
    lambda p: next(r for r in p["adapter_entries"] if r["adapter_kind"] == "MAC_REGISTRY").update(source_kind="dhcp"),
    lambda p: next(r for r in p["adapter_entries"] if r["adapter_kind"] == "MAC_REGISTRY").update(feature_schema_version=1),
    lambda p: next(r for r in p["adapter_entries"] if r["adapter_kind"] == "MAC_REGISTRY").update(quality_state="valid"),
    lambda p: next(r for r in p["adapter_entries"] if r["adapter_kind"] == "MAC_REGISTRY").update(locally_administered_behavior="IEEE_LOOKUP"),
    lambda p: next(r for r in p["adapter_entries"] if r["adapter_kind"] == "MAC_REGISTRY").update(manufacturer_mapping_mode="DIRECT"),
    lambda p: next(r for r in p["adapter_entries"] if r["adapter_kind"] == "MAC_REGISTRY").update(globally_administered_match_mode="MA_L_FIRST"),
    lambda p: p.update(evidence_schema_registry={"artifact_id": "bad", "content_sha256": "a" * 64}),
    lambda p: p["evidence_schema_registry"].update(content_sha256="b" * 64),
])
def test_closed_schema_and_union_rejections(mutation):
    payload = build_initial_evidence_adapter_contract_set_v1(
        _refs()["evidence_schema_registry"]).semantic_payload
    mutation(payload)
    with pytest.raises(DeviceFingerprintValidationError):
        make_evidence_adapter_contract_set(payload)


@pytest.mark.parametrize("source,version,field,value", [
    ("tcp_syn", 1, "quality_valid_behavior", "EVALUATE_K2A_K2B"),
    ("tcp_syn", 2, "required_fields_by_dimension", {name: [] for name in DIMENSIONS}),
    ("tls_client", 1, "quality_valid_behavior", "EVALUATE_JA4_PLATFORM"),
    ("quic_client", 1, "quality_valid_behavior", "EVALUATE_JA4_PLATFORM"),
    ("tls_client", 1, "base_claim_strength_ceiling", "strong"),
    ("quic_client", 1, "base_claim_strength_ceiling", "strong"),
    ("dhcp", 1, "base_claim_strength_ceiling", "strong"),
    ("portal_headers", 1, "semantic_projection_id", "portal.k3.v1-only"),
    ("portal_headers", 2, "supported_source_subtypes", ["future"]),
    ("portal_headers", 2, "feature_schema_version", 3),
])
def test_initial_matrix_drift_fails_public_gate(source, version, field, value):
    payload = _changed_entry(source, version, field, value)
    candidate = make_evidence_adapter_contract_set(payload)
    result = _gate(candidate)
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []
    assert "initial_matrix_mismatch" in result.failure_reasons


@pytest.mark.parametrize("source,version,field,value", [
    ("tcp_syn", 1, "legacy_current_role", "CURRENT"),
    ("dhcp", 1, "quality_degraded_behavior", "EVALUATE_K1_CANDIDATE_SET"),
])
def test_structurally_forbidden_initial_drift_fails_generic_builder(source, version, field, value):
    with pytest.raises(DeviceFingerprintValidationError):
        make_evidence_adapter_contract_set(_changed_entry(source, version, field, value))


def test_generic_alternate_registry_is_valid_but_initial_gate_fails():
    refs = _refs()
    payload = refs["evidence_schema_registry"].semantic_payload
    payload["schema_entries"][0]["validator_contract_id"] = "synthetic.alternate.validator"
    alternate = make_artifact_content("EvidenceSchemaRegistryContract", payload)
    candidate = build_initial_evidence_adapter_contract_set_v1(alternate)
    changed = refs | {"evidence_schema_registry": alternate}
    assert validate_evidence_adapter_contract_set_dependencies(candidate, **changed)
    result = _gate(candidate, evidence_schema_registry=alternate)
    assert "initial_registry_identity_mismatch" in result.failure_reasons
    assert "adapter_registry_incompatible" not in result.failure_reasons
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []


def test_generic_not_admitted_is_coherent_but_initial_gate_rejects_it():
    candidate, refs = _disposition_configuration(
        "NOT_ADMITTED", fallback_source_kind="portal_headers",
        fallback_feature_schema_version=1, remove_v2=True)
    assert validate_evidence_adapter_contract_set_dependencies(candidate, **refs)
    result = _gate(candidate, **refs)
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []
    assert {"initial_registry_identity_mismatch", "initial_capability_disposition_mismatch",
            "initial_matrix_mismatch"} <= set(result.failure_reasons)
    assert "adapter_registry_incompatible" not in result.failure_reasons


def test_malformed_disposition_rejected_without_portal_v2_adapter():
    candidate, refs = _disposition_configuration("DEFERRED", remove_v2=True)
    with pytest.raises(_AdapterRegistryCompatibilityError):
        validate_evidence_adapter_contract_set_dependencies(candidate, **refs)
    result = _gate(candidate, **refs)
    assert "adapter_registry_incompatible" in result.failure_reasons
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []


@pytest.mark.parametrize("status", ["UNKNOWN", "SUPPORTED", "DISABLED", None, ""])
def test_other_disposition_statuses_fail_closed(status):
    candidate, refs = _disposition_configuration(status, remove_v2=True)
    with pytest.raises(_AdapterRegistryCompatibilityError):
        validate_evidence_adapter_contract_set_dependencies(candidate, **refs)


@pytest.mark.parametrize("status,source,version,remove_v2", [
    ("ADMITTED", "portal_headers", None, False),
    ("ADMITTED", None, 1, False),
    ("NOT_ADMITTED", None, 1, True),
    ("NOT_ADMITTED", "portal_headers", None, True),
    ("NOT_ADMITTED", "dhcp", 1, True),
    ("NOT_ADMITTED", "portal_headers", 2, True),
    ("NOT_ADMITTED", "portal_headers", 1, False),
    ("ADMITTED", None, None, True),
])
def test_invalid_disposition_fallback_or_v2_presence_fails(
        status, source, version, remove_v2):
    candidate, refs = _disposition_configuration(
        status, fallback_source_kind=source,
        fallback_feature_schema_version=version, remove_v2=remove_v2)
    with pytest.raises(_AdapterRegistryCompatibilityError):
        validate_evidence_adapter_contract_set_dependencies(candidate, **refs)


@pytest.mark.parametrize("remove_v1,mark_nonfusion", [(True, False), (False, True)])
def test_not_admitted_requires_supported_portal_v1_fallback(remove_v1, mark_nonfusion):
    candidate, refs = _disposition_configuration(
        "NOT_ADMITTED", fallback_source_kind="portal_headers",
        fallback_feature_schema_version=1, remove_v1=remove_v1, remove_v2=True)
    if mark_nonfusion:
        registry_payload = refs["evidence_schema_registry"].semantic_payload
        next(row for row in registry_payload["schema_entries"] if row["source_kind"] ==
             "portal_headers" and row["feature_schema_version"] == 1)["schema_status"] = "KNOWN_NON_FUSION"
        registry = make_artifact_content("EvidenceSchemaRegistryContract", registry_payload)
        candidate_payload = candidate.semantic_payload
        candidate_payload["evidence_schema_registry"] = ArtifactRef(
            registry.artifact_id, registry.content_sha256).as_dict()
        candidate = make_evidence_adapter_contract_set(candidate_payload)
        refs["evidence_schema_registry"] = registry
    with pytest.raises(_AdapterRegistryCompatibilityError):
        validate_evidence_adapter_contract_set_dependencies(candidate, **refs)


@pytest.mark.parametrize("reason_codes", [
    "reason", [""], ["repeat", "repeat"], ["z", "a"],
])
def test_invalid_disposition_reason_codes_fail(reason_codes):
    candidate, refs = _disposition_configuration("ADMITTED", reason_codes=reason_codes)
    with pytest.raises(_AdapterRegistryCompatibilityError):
        validate_evidence_adapter_contract_set_dependencies(candidate, **refs)


@pytest.mark.parametrize("status,reason_codes,remove_v2", [
    ("ADMITTED", ["synthetic_reason"], False),
    ("NOT_ADMITTED", [], True),
])
def test_generic_disposition_does_not_invent_reason_code_cardinality(
        status, reason_codes, remove_v2):
    candidate, refs = _disposition_configuration(
        status, fallback_source_kind="portal_headers" if remove_v2 else None,
        fallback_feature_schema_version=1 if remove_v2 else None,
        reason_codes=reason_codes, remove_v2=remove_v2)
    assert validate_evidence_adapter_contract_set_dependencies(candidate, **refs)


def test_gate_separates_registry_and_non_registry_dependency_reasons():
    refs = _refs()
    candidate = build_initial_evidence_adapter_contract_set_v1(refs["evidence_schema_registry"])
    payload = candidate.semantic_payload
    payload["adapter_entries"].pop()
    registry_failure = _gate(make_evidence_adapter_contract_set(payload))
    assert "adapter_registry_incompatible" in registry_failure.failure_reasons
    assert "adapter_dependency_invalid" not in registry_failure.failure_reasons
    assert registry_failure.gate_result_manifest.semantic_payload["output_artifact_refs"] == []

    k1_payload = refs["k1_record_set"].semantic_payload
    k1_payload["knowledge_slot"] = "K2B"
    bad_k1 = make_artifact_content("CanonicalKnowledgeRecordSet", k1_payload)
    dependency_failure = _gate(candidate, k1_record_set=bad_k1)
    assert "adapter_dependency_invalid" in dependency_failure.failure_reasons
    assert "adapter_registry_incompatible" not in dependency_failure.failure_reasons
    assert dependency_failure.gate_result_manifest.semantic_payload["output_artifact_refs"] == []


def test_registry_disposition_reference_mismatch_has_registry_failure_reason():
    candidate, refs = _disposition_configuration("ADMITTED", reason_codes=["synthetic_reason"])
    wrong_disposition = _refs()["capability_disposition"]
    result = _gate(candidate, **(refs | {"capability_disposition": wrong_disposition}))
    assert "adapter_registry_incompatible" in result.failure_reasons
    assert "adapter_dependency_invalid" not in result.failure_reasons
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []


def test_missing_schema_and_nonadmitted_disposition_fail_generic_validation():
    refs = _refs()
    registry = refs["evidence_schema_registry"].semantic_payload
    registry["schema_entries"].pop()
    alternate = make_artifact_content("EvidenceSchemaRegistryContract", registry)
    candidate = build_initial_evidence_adapter_contract_set_v1(alternate)
    with pytest.raises(DeviceFingerprintValidationError):
        validate_evidence_adapter_contract_set_dependencies(
            candidate, **(refs | {"evidence_schema_registry": alternate}))
    disposition = refs["capability_disposition"].semantic_payload
    disposition["status"] = "DEFERRED"
    alternate_disposition = make_artifact_content("CapabilityDisposition", disposition)
    registry = refs["evidence_schema_registry"].semantic_payload
    registry["portal_headers_v2_disposition"] = ArtifactRef(
        alternate_disposition.artifact_id, alternate_disposition.content_sha256).as_dict()
    alternate_registry = make_artifact_content("EvidenceSchemaRegistryContract", registry)
    candidate = build_initial_evidence_adapter_contract_set_v1(alternate_registry)
    with pytest.raises(DeviceFingerprintValidationError):
        validate_evidence_adapter_contract_set_dependencies(candidate, **(refs | {
            "evidence_schema_registry": alternate_registry,
            "capability_disposition": alternate_disposition,
        }))


@pytest.mark.parametrize("field,expected_reason", [
    ("capability_disposition", "initial_capability_disposition_mismatch"),
    ("k2a_conformance_package", "initial_k2a_identity_mismatch"),
    ("k3_portal_rule_set", "initial_k3_identity_mismatch"),
])
def test_wrong_initial_prerequisite_identity_never_produces_output(field, expected_reason):
    refs = _refs()
    payload = refs[field].semantic_payload
    if field == "capability_disposition":
        payload["status"] = "DEFERRED"
    elif field == "k2a_conformance_package":
        payload["p0f_implementation_identity"] = "synthetic alternate p0f"
    else:
        payload["rules"][0]["explanation_code"] = "synthetic_alternate_rule"
    alternate = make_artifact_content(refs[field].artifact_type, payload)
    candidate = build_initial_evidence_adapter_contract_set_v1(refs["evidence_schema_registry"])
    result = _gate(candidate, **{field: alternate})
    assert expected_reason in result.failure_reasons
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []


def test_missing_or_ninth_adapter_is_never_initially_admitted():
    refs = _refs()
    initial = build_initial_evidence_adapter_contract_set_v1(refs["evidence_schema_registry"])
    missing = initial.semantic_payload
    missing["adapter_entries"].pop()
    result = _gate(make_evidence_adapter_contract_set(missing))
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []
    extra = initial.semantic_payload
    added = deepcopy(_entry("dhcp", 1))
    added["adapter_contract_id"] = "ff1.synthetic.ninth.v1"
    extra["adapter_entries"].append(added)
    result = _gate(make_evidence_adapter_contract_set(extra))
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []


def test_latest_schema_wins_and_unknown_opportunistic_paths_are_not_admitted():
    refs = _refs()
    initial = build_initial_evidence_adapter_contract_set_v1(refs["evidence_schema_registry"])
    payload = initial.semantic_payload
    payload["adapter_entries"] = [row for row in payload["adapter_entries"]
                                  if not (row.get("source_kind") == "portal_headers"
                                          and row.get("feature_schema_version") == 1)]
    assert _gate(make_evidence_adapter_contract_set(payload)).gate_result_manifest.semantic_payload["status"] == "FAIL"
    payload = initial.semantic_payload
    future = deepcopy(_entry("portal_headers", 2))
    future["adapter_contract_id"] = "ff1.portal_headers.3.opportunistic.v1"
    future["feature_schema_version"] = 3
    payload["adapter_entries"].append(future)
    assert _gate(make_evidence_adapter_contract_set(payload)).gate_result_manifest.semantic_payload["status"] == "FAIL"


def test_projection_contracts_are_same_origin_and_row_identity_never_vote_identity():
    entries = _entries()
    assert len(PROJECTION_IDS) == 7
    assert _entry("portal_headers", 1)["semantic_projection_id"] == (
        _entry("portal_headers", 2)["semantic_projection_id"])
    assert _entry("tcp_syn", 1)["semantic_projection_id"] != (
        _entry("tcp_syn", 2)["semantic_projection_id"])
    assert _entry("tcp_syn", 1)["quality_valid_behavior"] == "AUDIT_ONLY_NO_CLAIM"
    assert len({row["semantic_projection_id"] for row in entries}) == 7
    assert all(not any(term in row["semantic_projection_id"] for term in
                       ("evidence_id", "source_event_id", "row_count", "observed_at"))
               for row in entries)


def test_double_build_and_all_declared_set_permutations_preserve_identity():
    registry = _refs()["evidence_schema_registry"]
    a = build_initial_evidence_adapter_contract_set_v1(registry)
    b = build_initial_evidence_adapter_contract_set_v1(registry)
    assert (a.artifact_id, a.content_sha256, a.semantic_payload_json) == (
        b.artifact_id, b.content_sha256, b.semantic_payload_json)
    payload = a.semantic_payload
    payload["adapter_entries"].reverse()
    for row in payload["adapter_entries"]:
        if row["adapter_kind"] == "TASK01_EVIDENCE":
            for field in ("supported_source_subtypes", "extractor_name_constraints",
                          "extractor_version_constraints", "rule_version_constraints"):
                row[field].reverse()
            for fields in row["required_fields_by_dimension"].values():
                fields.reverse()
    assert make_evidence_adapter_contract_set(payload).semantic_payload_json == a.semantic_payload_json


def test_public_gate_has_no_initial_admission_bypass_and_no_failed_output():
    assert "initial_admission" not in signature(run_ff1_evidence_adapter_contract_gate).parameters
    refs = _refs()
    candidate = build_initial_evidence_adapter_contract_set_v1(refs["evidence_schema_registry"])
    with pytest.raises(TypeError):
        run_ff1_evidence_adapter_contract_gate(
            candidate, **refs, candidate_repository_commit_sha=_COMMIT,
            candidate_repository_tree_sha=_TREE, environment_identity="synthetic-ff1",
            retained_evidence_refs=_EVIDENCE, initial_admission=False)
    result = run_ff1_evidence_adapter_contract_gate(
        candidate, **refs, candidate_repository_commit_sha=_COMMIT,
        candidate_repository_tree_sha=_TREE, environment_identity="synthetic-ff1",
        retained_evidence_refs=[])
    assert result.gate_result_manifest.semantic_payload["status"] == "FAIL"
    assert result.gate_result_manifest.semantic_payload["output_artifact_refs"] == []
    assert "retained_evidence_required" in result.failure_reasons
