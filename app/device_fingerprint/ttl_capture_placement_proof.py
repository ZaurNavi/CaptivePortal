"""Immutable R14 F-C3 TTL capture-placement proof contract."""

from __future__ import annotations

import re
from typing import Any

from .artifact_content import ArtifactContent, canonical_set, make_artifact_content
from .models import DeviceFingerprintValidationError

PROOF_METHOD = "TOPOLOGY_CONFIGURATION"
DISTANCE_SEMANTICS = "OBSERVED_TTL_EQUALS_CLIENT_TTL_MINUS_CAPTURE_DISTANCE_L3_HOPS"
MIRROR_POSITIONS = frozenset({
    "BEFORE_FIRST_L3", "AFTER_FIRST_L3", "EXACT_DECLARED_DISTANCE",
})
DIRECTIONS = frozenset({"INGRESS", "EGRESS", "BOTH", "EXACT_MIRROR_CONTRACT"})
EVIDENCE_KINDS = frozenset({
    "CURRENT_NETWORK_TOPOLOGY",
    "SWITCH_MIRROR_CONFIGURATION",
    "GUEST_VLAN_MIRROR_SCOPE",
    "SENSOR_MIRROR_DESTINATION",
    "FIRST_L3_GATEWAY_PLACEMENT",
    "NO_PRE_OBSERVATION_L3_FORWARDER",
})

_SHA256 = re.compile(r"[0-9a-f]{64}")
_TOP_LEVEL_FIELDS = frozenset({
    "proof_method", "capture_topology_identity", "capture_topology_descriptor",
    "direction", "topology_configuration_evidence_refs",
    "capture_distance_l3_hops", "proven_distance_semantics",
    "proof_valid_for_topology_identity",
})
_DESCRIPTOR_FIELDS = frozenset({
    "guest_ingress_path_identity", "mirror_source_identity",
    "mirror_destination_identity", "first_l3_gateway_identity",
    "mirror_position_relative_to_first_l3",
})
_EVIDENCE_REF_FIELDS = frozenset({"evidence_kind", "evidence_sha256"})


def _fail() -> None:
    raise DeviceFingerprintValidationError("Invalid TTL capture-placement proof")


def _shape(value: Any, fields: frozenset[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        _fail()
    return value


def _text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail()
    return value


def _enum(value: Any, allowed: frozenset[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        _fail()
    return value


def make_ttl_capture_placement_proof(payload: dict[str, Any]) -> ArtifactContent:
    """Validate the exact R14 C.3.37 schema and canonicalize evidence refs."""
    value = _shape(payload, _TOP_LEVEL_FIELDS)
    if value["proof_method"] != PROOF_METHOD:
        _fail()

    topology_identity = _text(value["capture_topology_identity"])
    descriptor = _shape(value["capture_topology_descriptor"], _DESCRIPTOR_FIELDS)
    for field in (
        "guest_ingress_path_identity", "mirror_source_identity",
        "mirror_destination_identity", "first_l3_gateway_identity",
    ):
        _text(descriptor[field])
    _enum(descriptor["mirror_position_relative_to_first_l3"], MIRROR_POSITIONS)
    _enum(value["direction"], DIRECTIONS)

    distance = value["capture_distance_l3_hops"]
    if type(distance) is not int or not 0 <= distance <= 255:
        _fail()
    if value["proven_distance_semantics"] != DISTANCE_SEMANTICS:
        _fail()
    if value["proof_valid_for_topology_identity"] != topology_identity:
        _fail()

    evidence_refs = value["topology_configuration_evidence_refs"]
    if not isinstance(evidence_refs, list):
        _fail()
    evidence_kinds: list[str] = []
    for evidence_ref in evidence_refs:
        _shape(evidence_ref, _EVIDENCE_REF_FIELDS)
        kind = evidence_ref["evidence_kind"]
        if not isinstance(kind, str) or kind not in EVIDENCE_KINDS:
            _fail()
        digest = evidence_ref["evidence_sha256"]
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            _fail()
        evidence_kinds.append(kind)
    if len(evidence_kinds) != len(set(evidence_kinds)) or set(evidence_kinds) != EVIDENCE_KINDS:
        _fail()
    evidence_refs = canonical_set(evidence_refs, lambda item: item["evidence_kind"])

    return make_artifact_content("TTLCapturePlacementProof", {
        **value,
        "capture_topology_descriptor": descriptor,
        "topology_configuration_evidence_refs": evidence_refs,
    })
