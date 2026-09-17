"""Closed-world immutable F-A5 schema artifacts (no runtime activation)."""

from __future__ import annotations

from typing import Any

from .artifact_content import (
    ArtifactContent, ArtifactRef, canonical_set, make_artifact_content,
)
from .models import DeviceFingerprintValidationError
from .network_schemas import (
    _TCP_V2_BOOLEAN_KEYS, _TCP_V2_KEYS, _TCP_V2_OPTION_COMMON,
    _TCP_V2_OPTION_FIELDS, validate_dhcp_v1, validate_quic_v1,
    validate_tcp_syn_v1, validate_tcp_syn_v2, validate_tls_v1,
)
from .portal_schemas import validate_portal_headers_v1, validate_portal_headers_v2
from .schema_registry import build_production_schema_registry

_TCP_INT_BOUNDS = {
    "ip_version": (4, 4), "observed_ttl": (0, 255),
    "ip_option_length_bytes": (0, 40), "ip_ecn_bits": (0, 3),
    "tcp_header_length_bytes": (20, 60), "tcp_window": (0, 65535),
}
_TCP_BOOLEAN_FIELDS = frozenset({
    "ip_id_zero", "ip_df", "ip_reserved_flag", "tcp_sequence_zero",
    "tcp_ack_number_nonzero", "tcp_ack_first_octet_lsb_set",
    "tcp_urg_pointer_nonzero", "tcp_fin", "tcp_rst", "tcp_push",
    "tcp_urg", "tcp_ns", "tcp_ece", "tcp_cwr", "tcp_payload_present",
})
_TCP_TYPES = {**{name: "INT" for name in _TCP_INT_BOUNDS},
              **{name: "BOOL" for name in _TCP_BOOLEAN_FIELDS},
              "tcp_option_records": "ARRAY"}
_VARIANTS = (
    ("EOL", 0, "eol", False), ("NOP", 1, "nop", False),
    ("MSS", 2, "mss", True), ("WINDOW_SCALE", 3, "window_scale", True),
    ("SACK_PERMITTED", 4, "sack_permitted", True),
    ("TIMESTAMP", 8, "timestamp", True),
    ("UNKNOWN", None, "unknown", True),
)
_OPTION_COMMON = frozenset({
    "record_type", "kind", "declared_length", "available_value_length",
    "structure_state",
})
_OPTION_ADDITIONAL = {
    "eol": frozenset({"eol_padding_length", "eol_padding_nonzero",
                      "eol_padding_nonzero_before_final_byte"}),
    "nop": frozenset(), "mss": frozenset({"mss"}),
    "window_scale": frozenset({"window_scale_raw"}),
    "sack_permitted": frozenset(),
    "timestamp": frozenset({"timestamp_value_zero", "timestamp_echo_nonzero"}),
    "unknown": frozenset(),
}
_PORTAL_FIELDS = (
    ("model_family", "STRING", "portal_ch_model_v1", "Sec-CH-UA-Model"),
    ("os_major", "INTEGER", "portal_ch_platform_version_major_v1", "Sec-CH-UA-Platform-Version"),
    ("form_factor_mobile", "BOOLEAN", "portal_ch_form_factor_membership_v1", "Sec-CH-UA-Form-Factors"),
    ("form_factor_tablet", "BOOLEAN", "portal_ch_form_factor_membership_v1", "Sec-CH-UA-Form-Factors"),
    ("form_factor_desktop", "BOOLEAN", "portal_ch_form_factor_membership_v1", "Sec-CH-UA-Form-Factors"),
)
_PROVENANCE = {
    "model_family": ("model_source", "sec_ch_ua_model"),
    "os_major": ("os_major_source", "sec_ch_ua_platform_version"),
    "form_factor_mobile": ("form_factors_source", "sec_ch_ua_form_factors"),
    "form_factor_tablet": ("form_factors_source", "sec_ch_ua_form_factors"),
    "form_factor_desktop": ("form_factors_source", "sec_ch_ua_form_factors"),
}
_RUNTIME_VALIDATORS = {
    ("dhcp", 1): validate_dhcp_v1,
    ("tcp_syn", 1): validate_tcp_syn_v1,
    ("tcp_syn", 2): validate_tcp_syn_v2,
    ("tls_client", 1): validate_tls_v1,
    ("quic_client", 1): validate_quic_v1,
    ("portal_headers", 1): validate_portal_headers_v1,
    ("portal_headers", 2): validate_portal_headers_v2,
}


def _fail() -> None:
    raise DeviceFingerprintValidationError("Invalid foundation schema artifact")


def assert_runtime_registry_coherence() -> None:
    """Pin both exact keys and executable validator identity."""
    registry = build_production_schema_registry()
    if not registry.frozen or registry._validators != _RUNTIME_VALIDATORS:
        _fail()
    if (set(_TCP_TYPES) != _TCP_V2_KEYS
            or _TCP_BOOLEAN_FIELDS != _TCP_V2_BOOLEAN_KEYS
            or _OPTION_COMMON != _TCP_V2_OPTION_COMMON
            or _OPTION_ADDITIONAL != _TCP_V2_OPTION_FIELDS):
        _fail()


def _tcp_payload() -> dict[str, Any]:
    assert_runtime_registry_coherence()
    fields = []
    for name, field_type in _TCP_TYPES.items():
        bounds = _TCP_INT_BOUNDS.get(name, (None, None))
        fields.append({
            "field_name": name, "field_type": field_type, "nullable": False,
            "minimum_int": bounds[0], "maximum_int": bounds[1],
            "enum_values": [], "privacy_role": "required_minimized_protocol_semantic",
        })
    variants = []
    for variant_id, kind, record_type, malformed in _VARIANTS:
        variants.append({
            "variant_id": variant_id,
            "kind_match_mode": "OTHER" if kind is None else "EXACT",
            "kind_value": kind,
            "excluded_kind_values": [0, 1, 2, 3, 4, 8] if kind is None else [],
            "exact_fields": canonical_set(
                list(_OPTION_COMMON | _OPTION_ADDITIONAL[record_type]),
                lambda value: value,
            ),
            "malformed_observable_supported": malformed,
        })
    return {
        "schema_family": "tcp_syn", "feature_schema_version": 2,
        "source_kind": "tcp_syn",
        "supported_scope_identity": "tcp_syn_v2_ipv4_outbound_guest_request_syn_pre_router_rspan_v1",
        "top_level_field_contracts": canonical_set(fields, lambda value: value["field_name"]),
        "tcp_option_record_variant_contracts": canonical_set(variants, lambda value: value["variant_id"]),
        "privacy_minimization_contract_version": "tcp_syn_v2_privacy_minimization_v1",
        "malformed_observable_contract_version": "tcp_syn_v2_malformed_observable_v1",
        "evidence_canonical_json_identity": "EvidenceCanonicalJsonV1",
    }


def _portal_payload() -> dict[str, Any]:
    fields = [{
        "field_id": name, "value_type": value_type, "nullable": True,
        "enum_values": [], "normalization_rule_id": rule,
        "source_header_id": header,
    } for name, value_type, rule, header in _PORTAL_FIELDS]
    provenance = [{
        "normalized_field_id": name, "provenance_field_id": source[0],
        "allowed_source_values": [source[1]],
    } for name, source in _PROVENANCE.items()]
    return {
        "schema_family": "portal_headers", "feature_schema_version": 2,
        "source_kind": "portal_headers",
        "normalized_field_contracts": canonical_set(fields, lambda value: value["field_id"]),
        "normalized_provenance_contracts": canonical_set(provenance, lambda value: value["normalized_field_id"]),
        "privacy_non_durability_contract_version": "portal_headers_v2_privacy_non_durability_v1",
        "accept_ch_bounded_lifecycle_contract_version": "portal_headers_v2_accept_ch_bounded_lifecycle_v1",
        "evidence_canonical_json_identity": "EvidenceCanonicalJsonV1",
    }


def _disposition_payload() -> dict[str, Any]:
    return {
        "capability_id": "portal_headers/2", "status": "ADMITTED",
        "reason_codes": [], "fallback_source_kind": None,
        "fallback_feature_schema_version": None,
    }


def _ref(content: ArtifactContent) -> dict[str, str]:
    return ArtifactRef(content.artifact_id, content.content_sha256).as_dict()


def _registry_payload(tcp: ArtifactContent, portal: ArtifactContent,
                      disposition: ArtifactContent) -> dict[str, Any]:
    ArtifactRef.from_dict(_ref(tcp)).resolve(tcp, "TcpSynV2SchemaContract")
    ArtifactRef.from_dict(_ref(portal)).resolve(portal, "PortalHeadersV2SchemaContract")
    ArtifactRef.from_dict(_ref(disposition)).resolve(disposition, "CapabilityDisposition")
    assert_runtime_registry_coherence()
    entries = []
    for (source_kind, version) in _RUNTIME_VALIDATORS:
        status = "KNOWN_NON_FUSION" if (source_kind, version) == ("tcp_syn", 1) else "SUPPORTED"
        contract_ref = None
        if (source_kind, version) == ("tcp_syn", 2):
            contract_ref = {"contract_kind": "TCP_SYN_V2", "ref": _ref(tcp)}
        if (source_kind, version) == ("portal_headers", 2):
            contract_ref = {"contract_kind": "PORTAL_HEADERS_V2", "ref": _ref(portal)}
        entries.append({
            "source_kind": source_kind, "feature_schema_version": version,
            "schema_status": status,
            "validator_contract_id": f"device_fingerprint.validator.{source_kind}.v{version}",
            "schema_contract_ref": contract_ref,
        })
    return {
        "registry_contract_version": 1,
        "evidence_canonical_json_version": "EvidenceCanonicalJsonV1",
        "schema_entries": canonical_set(entries, lambda value: (
            value["source_kind"], value["feature_schema_version"])),
        "portal_headers_v2_disposition": _ref(disposition),
    }


def _ordered_payload(artifact_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Canonicalize only the SET fields declared by these four contracts."""
    value = dict(payload)
    if artifact_type == "TcpSynV2SchemaContract":
        for field, key in (("top_level_field_contracts", "field_name"),
                           ("tcp_option_record_variant_contracts", "variant_id")):
            value[field] = canonical_set(value[field], lambda row: row[key])
        for row in value["tcp_option_record_variant_contracts"]:
            row["excluded_kind_values"] = canonical_set(row["excluded_kind_values"], lambda item: item)
            row["exact_fields"] = canonical_set(row["exact_fields"], lambda item: item)
    elif artifact_type == "PortalHeadersV2SchemaContract":
        for field, key in (("normalized_field_contracts", "field_id"),
                           ("normalized_provenance_contracts", "normalized_field_id")):
            value[field] = canonical_set(value[field], lambda row: row[key])
        for row in value["normalized_field_contracts"]:
            row["enum_values"] = canonical_set(row["enum_values"], lambda item: item)
        for row in value["normalized_provenance_contracts"]:
            row["allowed_source_values"] = canonical_set(row["allowed_source_values"], lambda item: item)
    elif artifact_type == "CapabilityDisposition":
        value["reason_codes"] = canonical_set(value["reason_codes"], lambda item: item)
    elif artifact_type == "EvidenceSchemaRegistryContract":
        value["schema_entries"] = canonical_set(value["schema_entries"], lambda row: (
            row["source_kind"], row["feature_schema_version"]))
    else:
        _fail()
    return value


def build_foundation_schema_artifacts() -> dict[str, ArtifactContent]:
    tcp = make_artifact_content("TcpSynV2SchemaContract", _tcp_payload())
    portal = make_artifact_content("PortalHeadersV2SchemaContract", _portal_payload())
    disposition = make_artifact_content("CapabilityDisposition", _disposition_payload())
    registry = make_artifact_content(
        "EvidenceSchemaRegistryContract", _registry_payload(tcp, portal, disposition))
    return {item.artifact_type: item for item in (tcp, portal, disposition, registry)}


def validate_foundation_payload(artifact_type: str, payload: dict[str, Any]) -> ArtifactContent:
    """Reject all fields and semantics outside the four frozen F-A5 payloads."""
    if not isinstance(payload, dict):
        _fail()
    expected = build_foundation_schema_artifacts().get(artifact_type)
    if expected is None:
        _fail()
    try:
        ordered = _ordered_payload(artifact_type, payload)
        actual = make_artifact_content(artifact_type, ordered)
    except (KeyError, TypeError, AttributeError) as exc:
        raise DeviceFingerprintValidationError("Invalid foundation schema artifact") from exc
    if actual.semantic_payload_json != expected.semantic_payload_json:
        _fail()
    return actual
