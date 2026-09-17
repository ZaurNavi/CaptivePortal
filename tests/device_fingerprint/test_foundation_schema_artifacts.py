from copy import deepcopy

import pytest

from app.device_fingerprint.foundation_schema_artifacts import (
    assert_runtime_registry_coherence, build_foundation_schema_artifacts,
    validate_foundation_payload,
)
from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.network_schemas import _TCP_V2_KEYS
from app.device_fingerprint.portal_schemas import PORTAL_HEADER_V2_KEYS


def test_four_frozen_artifacts_have_stable_identity_and_exact_dependency_refs():
    first = build_foundation_schema_artifacts()
    again = build_foundation_schema_artifacts()
    assert set(first) == {
        "TcpSynV2SchemaContract", "PortalHeadersV2SchemaContract",
        "CapabilityDisposition", "EvidenceSchemaRegistryContract",
    }
    assert {key: value.content_sha256 for key, value in first.items()} == {
        "TcpSynV2SchemaContract": "7d15812e100f7b7c2e3f3549a685db2a241042a61ae25bdece122916a4026e98",
        "PortalHeadersV2SchemaContract": "4fb5782b1c042e470dafb52c9db456b0639495be44f0c18dee7a20d2db7bd89d",
        "CapabilityDisposition": "53ae5181e5a1fc8aa371214ded51c2ca719aafc21ba27c745b3cfafe5a77ae50",
        "EvidenceSchemaRegistryContract": "090d763e99247ca3b10be34976069e4e7e708be0899e21a15c6e103a015f7814",
    }
    assert [(key, value.artifact_id) for key, value in first.items()] == [
        (key, value.artifact_id) for key, value in again.items()
    ]
    for key, value in first.items():
        assert value.semantic_payload_json == again[key].semantic_payload_json
        assert value.digest_input_json == again[key].digest_input_json
        assert validate_foundation_payload(key, value.semantic_payload).artifact_id == value.artifact_id
    registry = first["EvidenceSchemaRegistryContract"].semantic_payload
    for source, version, contract_kind, target in (
        ("tcp_syn", 2, "TCP_SYN_V2", first["TcpSynV2SchemaContract"]),
        ("portal_headers", 2, "PORTAL_HEADERS_V2", first["PortalHeadersV2SchemaContract"]),
    ):
        row = next(row for row in registry["schema_entries"]
                   if (row["source_kind"], row["feature_schema_version"]) == (source, version))
        assert row["schema_contract_ref"] == {
            "contract_kind": contract_kind,
            "ref": {"artifact_id": target.artifact_id, "content_sha256": target.content_sha256},
        }
    disposition = first["CapabilityDisposition"]
    assert registry["portal_headers_v2_disposition"] == {
        "artifact_id": disposition.artifact_id,
        "content_sha256": disposition.content_sha256,
    }


def test_tcp_syn_v2_contract_matches_frozen_schema_and_repaired_unknown():
    payload = build_foundation_schema_artifacts()["TcpSynV2SchemaContract"].semantic_payload
    assert set(payload) == {
        "schema_family", "feature_schema_version", "source_kind", "supported_scope_identity",
        "top_level_field_contracts", "tcp_option_record_variant_contracts",
        "privacy_minimization_contract_version", "malformed_observable_contract_version",
        "evidence_canonical_json_identity",
    }
    fields = {row["field_name"]: row for row in payload["top_level_field_contracts"]}
    assert set(fields) == _TCP_V2_KEYS
    assert fields["tcp_ack_first_octet_lsb_set"]["field_type"] == "BOOL"
    assert fields["tcp_ns"]["field_type"] == "BOOL"
    assert all(row["nullable"] is False for row in fields.values())
    variants = {row["variant_id"]: row for row in payload["tcp_option_record_variant_contracts"]}
    assert set(variants) == {"EOL", "NOP", "MSS", "WINDOW_SCALE", "SACK_PERMITTED", "TIMESTAMP", "UNKNOWN"}
    assert "eol_padding_nonzero_before_final_byte" in variants["EOL"]["exact_fields"]
    assert variants["UNKNOWN"]["kind_match_mode"] == "OTHER"
    assert variants["UNKNOWN"]["kind_value"] is None
    assert variants["UNKNOWN"]["excluded_kind_values"] == [0, 1, 2, 3, 4, 8]


def test_portal_contract_and_admitted_disposition_are_exact():
    artifacts = build_foundation_schema_artifacts()
    portal = artifacts["PortalHeadersV2SchemaContract"].semantic_payload
    fields = {row["field_id"]: row for row in portal["normalized_field_contracts"]}
    provenance = {row["normalized_field_id"]: row for row in portal["normalized_provenance_contracts"]}
    assert set(fields) | {"model_source", "os_major_source", "form_factors_source"} == PORTAL_HEADER_V2_KEYS
    assert set(provenance) == set(fields)
    assert fields["model_family"]["source_header_id"] == "Sec-CH-UA-Model"
    assert fields["os_major"]["source_header_id"] == "Sec-CH-UA-Platform-Version"
    assert all(fields[name]["source_header_id"] == "Sec-CH-UA-Form-Factors"
               for name in ("form_factor_mobile", "form_factor_tablet", "form_factor_desktop"))
    assert provenance["model_family"] == {
        "normalized_field_id": "model_family", "provenance_field_id": "model_source",
        "allowed_source_values": ["sec_ch_ua_model"],
    }
    assert artifacts["CapabilityDisposition"].semantic_payload == {
        "capability_id": "portal_headers/2", "status": "ADMITTED", "reason_codes": [],
        "fallback_source_kind": None, "fallback_feature_schema_version": None,
    }


def test_final_registry_exact_entries_and_runtime_binding():
    assert_runtime_registry_coherence()
    payload = build_foundation_schema_artifacts()["EvidenceSchemaRegistryContract"].semantic_payload
    entries = {(row["source_kind"], row["feature_schema_version"]): row
               for row in payload["schema_entries"]}
    assert set(entries) == {
        ("dhcp", 1), ("tcp_syn", 1), ("tcp_syn", 2),
        ("tls_client", 1), ("quic_client", 1),
        ("portal_headers", 1), ("portal_headers", 2),
    }
    assert entries[("tcp_syn", 1)]["schema_status"] == "KNOWN_NON_FUSION"
    assert entries[("tcp_syn", 2)]["schema_status"] == "SUPPORTED"
    assert entries[("portal_headers", 2)]["schema_status"] == "SUPPORTED"
    assert all(row["schema_contract_ref"] is None for key, row in entries.items()
               if key not in {("tcp_syn", 2), ("portal_headers", 2)})
    assert "GateResultManifest" not in str(payload)


@pytest.mark.parametrize("artifact_type,field", [
    ("TcpSynV2SchemaContract", "top_level_field_contracts"),
    ("PortalHeadersV2SchemaContract", "normalized_field_contracts"),
    ("CapabilityDisposition", "reason_codes"),
    ("EvidenceSchemaRegistryContract", "schema_entries"),
])
def test_extra_semantic_fields_are_closed_world(artifact_type, field):
    payload = build_foundation_schema_artifacts()[artifact_type].semantic_payload
    payload["extra"] = True
    with pytest.raises(DeviceFingerprintValidationError):
        validate_foundation_payload(artifact_type, payload)
    payload.pop("extra")
    if payload[field]:
        payload[field][0]["extra"] = True
        with pytest.raises(DeviceFingerprintValidationError):
            validate_foundation_payload(artifact_type, payload)


@pytest.mark.parametrize("artifact_type,field", [
    ("TcpSynV2SchemaContract", "top_level_field_contracts"),
    ("PortalHeadersV2SchemaContract", "normalized_field_contracts"),
    ("EvidenceSchemaRegistryContract", "schema_entries"),
])
def test_set_permutation_identity_and_duplicate_primary_rejection(artifact_type, field):
    content = build_foundation_schema_artifacts()[artifact_type]
    payload = content.semantic_payload
    payload[field] = list(reversed(payload[field]))
    assert validate_foundation_payload(artifact_type, payload).artifact_id == content.artifact_id
    payload[field].append(deepcopy(payload[field][0]))
    with pytest.raises(DeviceFingerprintValidationError):
        validate_foundation_payload(artifact_type, payload)
