"""F-C3 TTL capture-placement proof schema and canonical identity tests."""

from __future__ import annotations

from copy import deepcopy

import pytest

from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.ttl_capture_placement_proof import (
    DISTANCE_SEMANTICS, EVIDENCE_KINDS, make_ttl_capture_placement_proof,
)


def proof_payload() -> dict:
    return {
        "proof_method": "TOPOLOGY_CONFIGURATION",
        "capture_topology_identity": "zefer-guest-pre-router-rspan-v1",
        "capture_topology_descriptor": {
            "guest_ingress_path_identity": "guest-client-ap-catalyst-vlan10-vlan20",
            "mirror_source_identity": "catalyst-rspan-session-1-vlan10-vlan20-both",
            "mirror_destination_identity": "sensor-zefer-01-enp8s0",
            "first_l3_gateway_identity": "cisco-3845-guest-gateway",
            "mirror_position_relative_to_first_l3": "BEFORE_FIRST_L3",
        },
        "direction": "BOTH",
        "topology_configuration_evidence_refs": [
            {"evidence_kind": kind, "evidence_sha256": f"{index + 1:064x}"}
            for index, kind in enumerate(sorted(EVIDENCE_KINDS))
        ],
        "capture_distance_l3_hops": 0,
        "proven_distance_semantics": DISTANCE_SEMANTICS,
        "proof_valid_for_topology_identity": "zefer-guest-pre-router-rspan-v1",
    }


def rejected(payload: dict) -> None:
    with pytest.raises(DeviceFingerprintValidationError):
        make_ttl_capture_placement_proof(payload)


def test_valid_current_topology_proof_is_accepted():
    artifact = make_ttl_capture_placement_proof(proof_payload())
    assert artifact.artifact_type == "TTLCapturePlacementProof"
    assert artifact.artifact_schema_version == 1
    assert artifact.semantic_payload["capture_topology_descriptor"][
        "mirror_position_relative_to_first_l3"
    ] == "BEFORE_FIRST_L3"
    assert artifact.semantic_payload["direction"] == "BOTH"
    assert artifact.semantic_payload["capture_distance_l3_hops"] == 0


def test_top_level_descriptor_and_evidence_ref_are_closed_world():
    payload = proof_payload()
    payload["legacy_sender_ttl"] = 64
    rejected(payload)
    payload = proof_payload()
    payload["capture_topology_descriptor"]["extra"] = True
    rejected(payload)
    payload = proof_payload()
    payload["topology_configuration_evidence_refs"][0]["extra"] = True
    rejected(payload)


@pytest.mark.parametrize("legacy_field", [
    "sender_ttl", "sensor_ttl", "same_syn_correlation", "packet_correlation_identity",
])
def test_legacy_live_ttl_and_packet_correlation_fields_are_rejected(legacy_field):
    payload = proof_payload()
    payload[legacy_field] = "forbidden"
    rejected(payload)


def test_all_six_evidence_kinds_are_required():
    artifact = make_ttl_capture_placement_proof(proof_payload())
    assert {row["evidence_kind"] for row in artifact.semantic_payload[
        "topology_configuration_evidence_refs"
    ]} == EVIDENCE_KINDS
    payload = proof_payload()
    payload["topology_configuration_evidence_refs"].pop()
    rejected(payload)


def test_duplicate_kind_is_rejected_even_with_different_hashes():
    payload = proof_payload()
    duplicate = deepcopy(payload["topology_configuration_evidence_refs"][0])
    duplicate["evidence_sha256"] = "f" * 64
    payload["topology_configuration_evidence_refs"].append(duplicate)
    rejected(payload)


def test_unknown_evidence_kind_is_rejected():
    payload = proof_payload()
    payload["topology_configuration_evidence_refs"][0]["evidence_kind"] = "OTHER"
    rejected(payload)


def test_same_sha_across_different_evidence_kinds_is_accepted():
    payload = proof_payload()
    for evidence_ref in payload["topology_configuration_evidence_refs"]:
        evidence_ref["evidence_sha256"] = "a" * 64
    artifact = make_ttl_capture_placement_proof(payload)
    assert {row["evidence_sha256"] for row in artifact.semantic_payload[
        "topology_configuration_evidence_refs"
    ]} == {"a" * 64}


@pytest.mark.parametrize("digest", ["bad", "a" * 63, "A" * 64])
def test_malformed_or_uppercase_sha_is_rejected(digest):
    payload = proof_payload()
    payload["topology_configuration_evidence_refs"][0]["evidence_sha256"] = digest
    rejected(payload)


@pytest.mark.parametrize("distance", [0, 255])
def test_distance_boundaries_are_accepted(distance):
    payload = proof_payload()
    payload["capture_distance_l3_hops"] = distance
    assert make_ttl_capture_placement_proof(payload).semantic_payload[
        "capture_distance_l3_hops"
    ] == distance


@pytest.mark.parametrize("distance", [-1, 256, False, True])
def test_invalid_distance_is_rejected(distance):
    payload = proof_payload()
    payload["capture_distance_l3_hops"] = distance
    rejected(payload)


@pytest.mark.parametrize(("field", "value"), [
    ("proof_method", "LIVE_PACKET"),
    ("direction", "UNKNOWN"),
    ("proven_distance_semantics", "OBSERVED_TTL_EQUALS_CLIENT_TTL"),
])
def test_wrong_fixed_or_enum_top_level_values_are_rejected(field, value):
    payload = proof_payload()
    payload[field] = value
    rejected(payload)


def test_wrong_mirror_position_is_rejected():
    payload = proof_payload()
    payload["capture_topology_descriptor"]["mirror_position_relative_to_first_l3"] = "UNKNOWN"
    rejected(payload)


def test_topology_identity_mismatch_is_rejected():
    payload = proof_payload()
    payload["proof_valid_for_topology_identity"] = "another-topology"
    rejected(payload)


def test_evidence_order_does_not_change_artifact_identity():
    payload = proof_payload()
    forward = make_ttl_capture_placement_proof(payload)
    payload["topology_configuration_evidence_refs"].reverse()
    reverse = make_ttl_capture_placement_proof(payload)
    assert forward.artifact_id == reverse.artifact_id
    assert forward.content_sha256 == reverse.content_sha256
    assert forward.semantic_payload_json == reverse.semantic_payload_json


def test_same_semantic_input_is_deterministic():
    first = make_ttl_capture_placement_proof(proof_payload())
    second = make_ttl_capture_placement_proof(proof_payload())
    assert first.artifact_id == second.artifact_id
    assert first.content_sha256 == second.content_sha256
