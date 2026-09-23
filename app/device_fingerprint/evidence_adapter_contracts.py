"""Immutable F-F1 evidence-adapter contracts; no classification runtime."""

from __future__ import annotations

from copy import deepcopy
from types import MappingProxyType
from typing import Any

from .artifact_content import ArtifactContent, ArtifactRef, canonical_set, make_artifact_content
from .k2a_conformance_artifacts import make_k2a_conformance_package
from .k3_portal_rules import make_k3_portal_rule_set
from .knowledge_artifacts import make_canonical_k1_record_set, make_canonical_k4_record_set
from .models import DeviceFingerprintValidationError

DIMENSIONS = ("platform_family", "device_class", "manufacturer_family", "model_family")
TASK01_FIELDS = frozenset({
    "adapter_kind", "adapter_contract_id", "origin_group", "source_kind",
    "feature_schema_version", "supported_source_subtypes", "extractor_name_constraints",
    "extractor_version_constraints", "rule_version_constraints", "quality_valid_behavior",
    "quality_partial_behavior", "quality_degraded_behavior", "required_fields_by_dimension",
    "legacy_current_role", "claim_derivation", "base_claim_strength_ceiling",
    "semantic_projection_id", "unsupported_behavior",
})
MAC_FIELDS = frozenset({
    "adapter_kind", "adapter_contract_id", "origin_group", "input_observed_mac_source",
    "knowledge_slot", "locally_administered_behavior", "globally_administered_match_mode",
    "raw_result_semantic", "manufacturer_mapping_mode", "platform_claim_mode",
    "device_class_claim_mode", "model_claim_mode", "claim_derivation",
    "base_claim_strength_ceiling", "semantic_projection_id",
})
TOP_FIELDS = frozenset({"adapter_contract_set_version", "evidence_schema_registry", "adapter_entries"})
PROJECTION_IDS = (
    "dhcp.k1.candidate-set.v1",
    "tcp.legacy-nonfusion.no-claim.v1",
    "tcp.k2a-k2b.semantic-outcomes.v1",
    "tls.ja4.no-claim.v1",
    "quic.ja4.no-claim.v1",
    "portal.k3.semantic-outcomes.v1",
    "mac.k4.semantic-outcomes.v1",
)
TCP_SYN_V1_NON_FUSION_REASON = "legacy_tcp_schema_insufficient_for_exact_k2a_contract"
NON_FUSION_REASON_BY_ADAPTER_CONTRACT_ID = MappingProxyType({
    "ff1.tcp_syn.1.legacy-nonfusion.v1": TCP_SYN_V1_NON_FUSION_REASON,
})
_ORIGINS = frozenset({"dhcp", "portal", "tcp", "tls", "quic"})
_SOURCE_ORIGIN = {"dhcp": "dhcp", "portal_headers": "portal", "tcp_syn": "tcp",
                  "tls_client": "tls", "quic_client": "quic"}
_DERIVATIONS = frozenset({"declared", "deterministic_mapping", "fingerprint_match", "registry_mapping"})
_STRENGTHS = frozenset({"strong", "supporting"})
_ROLES = frozenset({"CURRENT", "LEGACY_NON_FUSION", "LEGACY_SUPPORTED"})
_TCP_V2_FIELDS = (
    "ip_df", "ip_ecn_bits", "ip_id_zero", "ip_option_length_bytes", "ip_reserved_flag",
    "ip_version", "observed_ttl", "tcp_ack_first_octet_lsb_set", "tcp_ack_number_nonzero",
    "tcp_cwr", "tcp_ece", "tcp_fin", "tcp_header_length_bytes", "tcp_ns",
    "tcp_option_records", "tcp_payload_present", "tcp_push", "tcp_rst",
    "tcp_sequence_zero", "tcp_urg", "tcp_urg_pointer_nonzero", "tcp_window",
)


def _fail(message: str) -> None:
    raise DeviceFingerprintValidationError(message)


class _AdapterRegistryCompatibilityError(DeviceFingerprintValidationError):
    """Registry/disposition versus adapter-set incompatibility only."""


def _registry_fail(message: str) -> None:
    raise _AdapterRegistryCompatibilityError(message)


def _shape(value: Any, expected: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        _fail(f"Invalid {label} shape")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"Invalid {label}")
    return value


def _ref(value: Any, kind: str) -> dict[str, str]:
    ref = ArtifactRef.from_dict(value)
    if not ref.artifact_id.startswith(f"{kind}:v1:sha256:"):
        _fail(f"Invalid {kind} reference")
    return ref.as_dict()


def _resolve(content: ArtifactContent, kind: str, builder: Any | None = None) -> dict[str, Any]:
    if not isinstance(content, ArtifactContent) or content.artifact_type != kind:
        _fail(f"Invalid {kind} dependency")
    payload = content.semantic_payload
    if builder is not None and builder(payload).semantic_payload_json != content.semantic_payload_json:
        _fail(f"Invalid {kind} dependency content")
    return payload


def _text_set(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        _fail(f"Invalid {label}")
    return canonical_set([_text(item, label) for item in value], lambda item: item)


def _entry(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        _fail("Invalid adapter entry")
    kind = raw.get("adapter_kind")
    if kind == "TASK01_EVIDENCE":
        value = dict(_shape(raw, TASK01_FIELDS, "Task-01 adapter"))
        _text(value["adapter_contract_id"], "adapter contract ID")
        if not isinstance(value["origin_group"], str) or value["origin_group"] not in _ORIGINS:
            _fail("Invalid Task-01 origin")
        if (not isinstance(value["source_kind"], str)
                or _SOURCE_ORIGIN.get(value["source_kind"]) != value["origin_group"]):
            _fail("Invalid Task-01 source/origin combination")
        version = value["feature_schema_version"]
        if type(version) is not int or not 1 <= version <= 2147483647:
            _fail("Invalid feature schema version")
        for field in ("supported_source_subtypes", "extractor_name_constraints",
                      "extractor_version_constraints", "rule_version_constraints"):
            value[field] = _text_set(value[field], field)
        if not value["supported_source_subtypes"]:
            _fail("Adapter requires a source subtype")
        _text(value["quality_valid_behavior"], "valid quality behavior")
        if value["quality_partial_behavior"] != "SUPPORTING_CAP_IF_REQUIRED_FIELDS_PRESENT":
            _fail("Invalid partial quality behavior")
        if value["quality_degraded_behavior"] != "NO_CLAIM":
            _fail("Invalid degraded quality behavior")
        fields = value["required_fields_by_dimension"]
        if not isinstance(fields, dict) or set(fields) != set(DIMENSIONS):
            _fail("Invalid required dimension fields")
        value["required_fields_by_dimension"] = {
            dimension: _text_set(fields[dimension], dimension) for dimension in DIMENSIONS
        }
        if not isinstance(value["legacy_current_role"], str) or value["legacy_current_role"] not in _ROLES:
            _fail("Invalid legacy/current role")
        if not isinstance(value["claim_derivation"], str) or value["claim_derivation"] not in _DERIVATIONS:
            _fail("Invalid claim derivation")
        if (not isinstance(value["base_claim_strength_ceiling"], str)
                or value["base_claim_strength_ceiling"] not in _STRENGTHS):
            _fail("Invalid claim strength ceiling")
        _text(value["semantic_projection_id"], "semantic projection ID")
        if value["unsupported_behavior"] != "UNSUPPORTED_EVIDENCE_CONTRACT_NO_CLAIM":
            _fail("Invalid unsupported behavior")
        if bool(value["extractor_name_constraints"]) != bool(value["extractor_version_constraints"]):
            _fail("Extractor constraint sets disagree")
        if not value["extractor_name_constraints"] and value["legacy_current_role"] != "LEGACY_NON_FUSION":
            _fail("Empty extractor constraints require non-fusion")
        return value
    if kind == "MAC_REGISTRY":
        value = dict(_shape(raw, MAC_FIELDS, "MAC registry adapter"))
        _text(value["adapter_contract_id"], "adapter contract ID")
        fixed = {
            "origin_group": "mac_registry",
            "input_observed_mac_source": "EvidenceSnapshotContent.observed_mac",
            "knowledge_slot": "K4",
            "locally_administered_behavior": "NO_IEEE_CLAIM",
            "globally_administered_match_mode": "MA_S_M_L_LONGEST_PREFIX",
            "raw_result_semantic": "mac_assignment_org",
            "manufacturer_mapping_mode": "EXPLICIT_ADMITTED_ASSIGNMENT_ORG_TO_MANUFACTURER_ONLY",
            "platform_claim_mode": "NO_CLAIM",
            "device_class_claim_mode": "NO_CLAIM",
            "model_claim_mode": "NO_CLAIM",
            "claim_derivation": "registry_mapping",
        }
        if any(value[field] != expected for field, expected in fixed.items()):
            _fail("Invalid MAC registry semantics")
        if (not isinstance(value["base_claim_strength_ceiling"], str)
                or value["base_claim_strength_ceiling"] not in _STRENGTHS):
            _fail("Invalid MAC claim strength ceiling")
        _text(value["semantic_projection_id"], "semantic projection ID")
        return value
    _fail("Unknown adapter kind")


def task01_contract_claim_eligible(entry: dict[str, Any], *, source_kind: str,
                                   feature_schema_version: int, source_subtype: str,
                                   extractor_name: str, extractor_version: str,
                                   rule_version: str | None, quality_state: str,
                                   normalized_payload: dict[str, Any],
                                   dimension_name: str) -> bool:
    """Check contract eligibility only; K1/K2A/K3 claim evaluation is out of scope."""
    value = _entry(entry)
    if value["adapter_kind"] != "TASK01_EVIDENCE" or dimension_name not in DIMENSIONS:
        _fail("Invalid Task-01 eligibility request")
    required = value["required_fields_by_dimension"][dimension_name]
    if (not required or value["legacy_current_role"] == "LEGACY_NON_FUSION"
            or value["quality_valid_behavior"].startswith("AUDIT_ONLY_")
            or value["source_kind"] != source_kind
            or value["feature_schema_version"] != feature_schema_version
            or source_subtype not in value["supported_source_subtypes"]
            or (value["extractor_name_constraints"]
                and extractor_name not in value["extractor_name_constraints"])
            or (value["extractor_version_constraints"]
                and extractor_version not in value["extractor_version_constraints"])
            or rule_version not in (value["rule_version_constraints"] or [None])
            or quality_state not in {"valid", "partial"}
            or not isinstance(normalized_payload, dict)):
        return False
    if quality_state == "partial" and not set(required) <= set(normalized_payload):
        return False
    return True


def make_evidence_adapter_contract_set(payload: dict[str, Any]) -> ArtifactContent:
    """Validate the reusable closed R14 tagged union and materialize canonical SETs."""
    value = dict(_shape(payload, TOP_FIELDS, "EvidenceAdapterContractSet"))
    if type(value["adapter_contract_set_version"]) is not int or not 1 <= value["adapter_contract_set_version"] <= 2147483647:
        _fail("Invalid adapter contract set version")
    value["evidence_schema_registry"] = _ref(value["evidence_schema_registry"], "EvidenceSchemaRegistryContract")
    entries = value["adapter_entries"]
    if not isinstance(entries, list):
        _fail("Invalid adapter entries")
    normalized = [_entry(entry) for entry in entries]
    ids = [entry["adapter_contract_id"] for entry in normalized]
    if len(ids) != len(set(ids)):
        _fail("Duplicate adapter contract ID")
    value["adapter_entries"] = canonical_set(normalized, lambda entry: entry["adapter_contract_id"])
    return make_artifact_content("EvidenceAdapterContractSet", value)


def _task(identifier: str, origin: str, source: str, version: int, subtypes: list[str],
          extractors: list[str], versions: list[str], behavior: str, role: str,
          derivation: str, projection: str, required: dict[str, list[str]]) -> dict[str, Any]:
    return {
        "adapter_kind": "TASK01_EVIDENCE", "adapter_contract_id": identifier,
        "origin_group": origin, "source_kind": source, "feature_schema_version": version,
        "supported_source_subtypes": subtypes, "extractor_name_constraints": extractors,
        "extractor_version_constraints": versions, "rule_version_constraints": [],
        "quality_valid_behavior": behavior,
        "quality_partial_behavior": "SUPPORTING_CAP_IF_REQUIRED_FIELDS_PRESENT",
        "quality_degraded_behavior": "NO_CLAIM",
        "required_fields_by_dimension": {dimension: required.get(dimension, []) for dimension in DIMENSIONS},
        "legacy_current_role": role, "claim_derivation": derivation,
        "base_claim_strength_ceiling": "supporting", "semantic_projection_id": projection,
        "unsupported_behavior": "UNSUPPORTED_EVIDENCE_CONTRACT_NO_CLAIM",
    }


_INITIAL_ENTRIES = (
    _task("ff1.dhcp.1.k1.v1", "dhcp", "dhcp", 1,
          ["decline", "discover", "inform", "release", "request"],
          ["packet-dhcp"], ["1.0.0"], "EVALUATE_K1_CANDIDATE_SET", "CURRENT",
          "fingerprint_match", PROJECTION_IDS[0], {
              "platform_family": ["message_type", "option_order", "parameter_request_list", "vendor_class"],
              "device_class": ["message_type", "option_order", "parameter_request_list", "vendor_class"],
          }),
    _task("ff1.tcp_syn.1.legacy-nonfusion.v1", "tcp", "tcp_syn", 1, ["ipv4"],
          [], [], "AUDIT_ONLY_NO_CLAIM", "LEGACY_NON_FUSION", "fingerprint_match",
          PROJECTION_IDS[1], {}),
    _task("ff1.tcp_syn.2.k2a-k2b.v1", "tcp", "tcp_syn", 2, ["ipv4"],
          ["packet-tcp-syn"], ["2.0.0"], "EVALUATE_K2A_K2B", "CURRENT",
          "fingerprint_match", PROJECTION_IDS[2], {"platform_family": list(_TCP_V2_FIELDS)}),
    _task("ff1.tls_client.1.ja4-audit.v1", "tls", "tls_client", 1, ["client_hello"],
          ["suricata-tls-ja4"], ["8.0.6"], "AUDIT_ONLY_NO_JA4_SEMANTIC_CLAIM",
          "CURRENT", "fingerprint_match", PROJECTION_IDS[3], {}),
    _task("ff1.quic_client.1.ja4-audit.v1", "quic", "quic_client", 1, ["client_hello"],
          ["suricata-quic-ja4"], ["8.0.6"], "AUDIT_ONLY_NO_JA4_SEMANTIC_CLAIM",
          "CURRENT", "fingerprint_match", PROJECTION_IDS[4], {}),
    _task("ff1.portal_headers.1.k3.v1", "portal", "portal_headers", 1,
          ["capport_login", "omada_external_portal"], ["portal-http-parser"], ["1.0.0"],
          "EVALUATE_K3_RULE_SET", "LEGACY_SUPPORTED", "deterministic_mapping",
          PROJECTION_IDS[5], {"platform_family": ["platform_family", "platform_source",
                                                   "sec_ch_ua_platform_present", "ua_present"]}),
    _task("ff1.portal_headers.2.k3.v1", "portal", "portal_headers", 2,
          ["capport_login", "omada_external_portal"], ["portal-http-parser"], ["1.0.0"],
          "EVALUATE_K3_RULE_SET", "CURRENT", "deterministic_mapping",
          PROJECTION_IDS[5], {"device_class": ["form_factor_desktop", "form_factor_tablet",
                                                 "form_factors_source"]}),
    {
        "adapter_kind": "MAC_REGISTRY", "adapter_contract_id": "ff1.mac_registry.k4.v1",
        "origin_group": "mac_registry", "input_observed_mac_source": "EvidenceSnapshotContent.observed_mac",
        "knowledge_slot": "K4", "locally_administered_behavior": "NO_IEEE_CLAIM",
        "globally_administered_match_mode": "MA_S_M_L_LONGEST_PREFIX",
        "raw_result_semantic": "mac_assignment_org",
        "manufacturer_mapping_mode": "EXPLICIT_ADMITTED_ASSIGNMENT_ORG_TO_MANUFACTURER_ONLY",
        "platform_claim_mode": "NO_CLAIM", "device_class_claim_mode": "NO_CLAIM",
        "model_claim_mode": "NO_CLAIM", "claim_derivation": "registry_mapping",
        "base_claim_strength_ceiling": "supporting",
        "semantic_projection_id": PROJECTION_IDS[6],
    },
)


def build_initial_evidence_adapter_contract_set_v1(
    evidence_schema_registry: ArtifactContent,
) -> ArtifactContent:
    _resolve(evidence_schema_registry, "EvidenceSchemaRegistryContract")
    return make_evidence_adapter_contract_set({
        "adapter_contract_set_version": 1,
        "evidence_schema_registry": ArtifactRef(
            evidence_schema_registry.artifact_id, evidence_schema_registry.content_sha256,
        ).as_dict(),
        "adapter_entries": deepcopy(list(_INITIAL_ENTRIES)),
    })


def validate_evidence_adapter_contract_set_dependencies(
    contract_set: ArtifactContent, *, evidence_schema_registry: ArtifactContent,
    capability_disposition: ArtifactContent, k2a_conformance_package: ArtifactContent,
    k1_record_set: ArtifactContent, k3_portal_rule_set: ArtifactContent,
    k4_record_set: ArtifactContent,
) -> bool:
    """Resolve supplied contracts without pinning one initial identity."""
    contract = _resolve(contract_set, "EvidenceAdapterContractSet",
                        make_evidence_adapter_contract_set)
    try:
        registry = _resolve(evidence_schema_registry, "EvidenceSchemaRegistryContract")
        disposition = _resolve(capability_disposition, "CapabilityDisposition")
        ArtifactRef.from_dict(contract["evidence_schema_registry"]).resolve(
            evidence_schema_registry, "EvidenceSchemaRegistryContract")
    except DeviceFingerprintValidationError as exc:
        raise _AdapterRegistryCompatibilityError("Invalid registry/disposition dependency") from exc
    _resolve(k2a_conformance_package, "K2AConformancePackage", make_k2a_conformance_package)
    k1 = _resolve(k1_record_set, "CanonicalKnowledgeRecordSet", make_canonical_k1_record_set)
    k3 = _resolve(k3_portal_rule_set, "K3PortalRuleSet", make_k3_portal_rule_set)
    k4 = _resolve(k4_record_set, "CanonicalKnowledgeRecordSet", make_canonical_k4_record_set)
    if (set(registry) != {"registry_contract_version", "evidence_canonical_json_version",
                          "schema_entries", "portal_headers_v2_disposition"}
            or type(registry["registry_contract_version"]) is not int
            or registry["registry_contract_version"] < 1
            or registry["evidence_canonical_json_version"] != "EvidenceCanonicalJsonV1"
            or not isinstance(registry["schema_entries"], list)):
        _registry_fail("Invalid evidence registry")
    try:
        ArtifactRef.from_dict(_ref(registry["portal_headers_v2_disposition"],
                                   "CapabilityDisposition")).resolve(
                                       capability_disposition, "CapabilityDisposition")
    except DeviceFingerprintValidationError as exc:
        raise _AdapterRegistryCompatibilityError("Invalid registry disposition reference") from exc
    if (set(disposition) != {"capability_id", "status", "reason_codes",
                            "fallback_source_kind", "fallback_feature_schema_version"}
            or disposition["capability_id"] != "portal_headers/2"):
        _registry_fail("Incompatible capability disposition")
    if disposition["status"] not in ("ADMITTED", "NOT_ADMITTED"):
        _registry_fail("Invalid capability disposition status")
    codes = disposition["reason_codes"]
    if not isinstance(codes, list) or any(not isinstance(code, str) or not code for code in codes):
        _registry_fail("Invalid capability reason codes")
    try:
        if canonical_set(codes, lambda code: code) != codes:
            _registry_fail("Noncanonical capability reason-code SET")
    except DeviceFingerprintValidationError as exc:
        raise _AdapterRegistryCompatibilityError("Invalid capability reason-code SET") from exc
    if disposition["status"] == "ADMITTED":
        if (disposition["fallback_source_kind"] is not None
                or disposition["fallback_feature_schema_version"] is not None):
            _registry_fail("ADMITTED disposition cannot declare fallback")
    elif (disposition["fallback_source_kind"] != "portal_headers"
          or type(disposition["fallback_feature_schema_version"]) is not int
          or disposition["fallback_feature_schema_version"] != 1):
        _registry_fail("Invalid NOT_ADMITTED fallback")
    if (k1["knowledge_slot"] != "K1" or k4["knowledge_slot"] != "K4"
            or k3["portal_schema_family"] != "portal_headers"):
        _fail("Invalid knowledge prerequisite")
    if any(outcome["dimension_name"] in {"manufacturer_family", "model_family"}
           and outcome["outcome_kind"] != "NO_CLAIM"
           for record in k1["records"] for outcome in record["candidate_taxonomy_refs"]):
        _fail("K1 manufacturer/model claim forbidden")
    schemas: dict[tuple[str, int], str] = {}
    for row in registry["schema_entries"]:
        if not isinstance(row, dict) or set(row) != {"source_kind", "feature_schema_version",
                                                    "schema_status", "validator_contract_id",
                                                    "schema_contract_ref"}:
            _registry_fail("Invalid registry schema entry")
        key = (row["source_kind"], row["feature_schema_version"])
        if (not isinstance(row["source_kind"], str)
                or type(row["feature_schema_version"]) is not int
                or not 1 <= row["feature_schema_version"] <= 2147483647
                or not isinstance(row["validator_contract_id"], str)
                or not row["validator_contract_id"]
                or key in schemas
                or not isinstance(row["schema_status"], str)
                or row["schema_status"] not in {"SUPPORTED", "KNOWN_NON_FUSION"}):
            _registry_fail("Invalid registry schema entry")
        contract_ref = row["schema_contract_ref"]
        if contract_ref is not None:
            if (not isinstance(contract_ref, dict)
                    or set(contract_ref) != {"contract_kind", "ref"}):
                _registry_fail("Invalid registry schema contract reference")
            if not isinstance(contract_ref["contract_kind"], str):
                _registry_fail("Invalid registry schema contract kind")
            expected_kind = {"TCP_SYN_V2": "TcpSynV2SchemaContract",
                             "PORTAL_HEADERS_V2": "PortalHeadersV2SchemaContract"}.get(
                                 contract_ref["contract_kind"])
            if expected_kind is None:
                _registry_fail("Invalid registry schema contract kind")
            try:
                _ref(contract_ref["ref"], expected_kind)
            except DeviceFingerprintValidationError as exc:
                raise _AdapterRegistryCompatibilityError("Invalid schema contract reference") from exc
            if ((contract_ref["contract_kind"] == "TCP_SYN_V2") != (key == ("tcp_syn", 2))
                    or (contract_ref["contract_kind"] == "PORTAL_HEADERS_V2") !=
                    (key == ("portal_headers", 2))):
                _registry_fail("Incompatible registry schema contract")
        elif key in {("tcp_syn", 2), ("portal_headers", 2)}:
            _registry_fail("Missing registry schema contract")
        schemas[key] = row["schema_status"]
    entries = contract["adapter_entries"]
    task_entries = [row for row in entries if row["adapter_kind"] == "TASK01_EVIDENCE"]
    task_keys = [(row["source_kind"], row["feature_schema_version"]) for row in task_entries]
    if len(task_keys) != len(set(task_keys)) or set(task_keys) != set(schemas):
        _registry_fail("Adapter/registry schema coverage mismatch")
    if len([row for row in entries if row["adapter_kind"] == "MAC_REGISTRY"]) != 1:
        _fail("Exactly one MAC registry adapter required")
    for row in task_entries:
        status = schemas[(row["source_kind"], row["feature_schema_version"])]
        if (status == "KNOWN_NON_FUSION") != (row["legacy_current_role"] == "LEGACY_NON_FUSION"):
            _registry_fail("Adapter/registry fusion status mismatch")
        if row["source_kind"] == "portal_headers" and row["feature_schema_version"] == 2:
            if 2 not in k3["admitted_feature_schema_versions"]:
                _fail("K3 does not admit portal V2")
    portal_v1 = ("portal_headers", 1)
    portal_v2 = ("portal_headers", 2)
    if disposition["status"] == "ADMITTED":
        if schemas.get(portal_v2) != "SUPPORTED":
            _registry_fail("ADMITTED portal V2 absent or unsupported")
    elif (portal_v2 in schemas or schemas.get(portal_v1) != "SUPPORTED"):
        _registry_fail("NOT_ADMITTED portal fallback incompatible with registry")
    return True
