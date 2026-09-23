"""Offline-only pinned Satori DHCP importer for the R14 K1 foundation."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifact_content import ArtifactContent, ArtifactRef, canonical_artifact_json
from .k2a_conformance_artifacts import make_source_governance_record
from .knowledge_artifacts import make_canonical_k1_record_set
from .models import DeviceFingerprintValidationError

SATORI_SOURCE_COMMIT = "c5dfcfbff31620e35248aa86da0c67f2ad4982f5"
SATORI_SOURCE_PATH = "fingerprints/dhcp.xml"
SATORI_SOURCE_BLOB_SHA1 = "a82926690c28d2147534f24bdbdbeb0d1a2970fb"
SATORI_SOURCE_SHA256 = "4f64a405fb1debbd2e066478a7190b821424e0691399068421fdaf168da09b14"
SATORI_LICENSE_CHANGE_COMMIT = "7116da4ce7ab768b4fb0b3bcb44001f952f24d5d"

_SIGNAL_FIELDS = frozenset({"dhcpoption55", "dhcpoptions", "dhcpvendorcode"})
_TEST_METADATA_FIELDS = frozenset({"weight", "matchtype", "dhcptype"})
_MESSAGE_TYPES = {
    "Discover": "discover",
    "Request": "request",
    "Inform": "inform",
    "Decline": "decline",
    "Release": "release",
    "Any": "ANY",
}
_REJECTED_MESSAGE_TYPES = frozenset({"ACK", "Offer", "NAK"})
SATORI_PLATFORM_TAXONOMY_MAPPING = {
    "Android": "android",
    "iOS": "ios",
    "Windows": "windows",
    "Mac OS": "macos",
    "ChromeOS": "chromeos",
    "Linux": "linux",
}
SATORI_DEVICE_CLASS_TAXONOMY_MAPPING = {
    "Smartphone": "smartphone",
    "Tablet": "tablet",
    "tablet": "tablet",
    "Laptop": "laptop",
}


@dataclass(frozen=True, slots=True)
class SatoriK1ImportAudit:
    fingerprints_total: int
    source_tests_total: int
    source_tests_accepted: int
    source_tests_rejected: int
    canonical_records_unique: int
    predicate_groups_total: int
    ambiguous_predicate_groups: int
    records_in_ambiguous_groups: int


@dataclass(frozen=True, slots=True)
class SatoriK1ImportResult:
    record_set: ArtifactContent
    audit: SatoriK1ImportAudit


ACCEPTED_SATORI_AUDIT = SatoriK1ImportAudit(
    fingerprints_total=481,
    source_tests_total=2787,
    source_tests_accepted=903,
    source_tests_rejected=1884,
    canonical_records_unique=903,
    predicate_groups_total=448,
    ambiguous_predicate_groups=164,
    records_in_ambiguous_groups=619,
)


def _fail(message: str) -> None:
    raise DeviceFingerprintValidationError(message)


def _local_name(tag: Any) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def _elements(root: ET.Element, name: str):
    return (element for element in root.iter() if _local_name(element.tag) == name)


def _provenance_ref(value: ArtifactRef | dict[str, Any]) -> dict[str, str]:
    reference = value if isinstance(value, ArtifactRef) else ArtifactRef.from_dict(value)
    if not reference.artifact_id.startswith("KnowledgeProvenanceManifest:v1:sha256:"):
        _fail("Invalid K1 knowledge provenance reference")
    return reference.as_dict()


def _parse_byte_sequence(value: str) -> list[int]:
    if not isinstance(value, str):
        _fail("Invalid Satori DHCP sequence")
    if value == "":
        return []
    pieces = value.split(",")
    if len(pieces) > 64 or any(piece == "" or piece.strip() != piece for piece in pieces):
        _fail("Invalid Satori DHCP sequence")
    try:
        parsed = [int(piece, 10) for piece in pieces]
    except ValueError as exc:
        raise DeviceFingerprintValidationError("Invalid Satori DHCP sequence") from exc
    if any(not 0 <= item <= 255 for item in parsed):
        _fail("Invalid Satori DHCP sequence")
    return parsed


def _any_predicates() -> dict[str, dict[str, Any]]:
    return {
        "message_type": {"mode": "ANY"},
        "parameter_request_list": {"mode": "ANY"},
        "option_order": {"mode": "ANY"},
        "vendor_class": {"mode": "ANY"},
        "client_identifier_kind": {"mode": "ANY"},
        "maximum_message_size": {"mode": "ANY"},
        "rapid_commit_requested": {"mode": "ANY"},
        "capport_requested": {"mode": "ANY"},
        "ipv6_only_preferred_requested": {"mode": "ANY"},
        "hostname_present": {"mode": "ANY"},
    }


def _taxonomy_outcome(dimension: str, raw: str | None, mapping: dict[str, str]) -> dict:
    if raw is None:
        kind = "NO_CLAIM"
        target = None
        strength = None
    elif raw in mapping:
        kind = "CANONICAL_VALUE"
        target = mapping[raw]
        strength = "supporting"
    else:
        kind = "UNMAPPED"
        target = None
        strength = None
    return {
        "dimension_name": dimension,
        "outcome_kind": kind,
        "canonical_target_id": target,
        "broad_taxon_ref": None,
        "out_of_scope_taxon_ref": None,
        "base_claim_strength": strength,
    }


def _candidate_taxonomy(fingerprint_attributes: dict[str, str]) -> list[dict[str, Any]]:
    platform_value = fingerprint_attributes.get("os_class")
    if platform_value is None:
        platform_value = fingerprint_attributes.get("os_name")
    return [
        _taxonomy_outcome("platform_family", platform_value, SATORI_PLATFORM_TAXONOMY_MAPPING),
        _taxonomy_outcome(
            "device_class", fingerprint_attributes.get("device_type"),
            SATORI_DEVICE_CLASS_TAXONOMY_MAPPING,
        ),
        _taxonomy_outcome("manufacturer_family", None, {}),
        _taxonomy_outcome("model_family", None, {}),
    ]


def _has_direct_taxonomy_mapping(fingerprint_attributes: dict[str, str]) -> bool:
    platform_value = fingerprint_attributes.get("os_class")
    if platform_value is None:
        platform_value = fingerprint_attributes.get("os_name")
    return platform_value in SATORI_PLATFORM_TAXONOMY_MAPPING or (
        fingerprint_attributes.get("device_type") in SATORI_DEVICE_CLASS_TAXONOMY_MAPPING
    )


def _record(
    fingerprint_attributes: dict[str, str],
    test_attributes: dict[str, str],
) -> dict[str, Any] | None:
    if not _has_direct_taxonomy_mapping(fingerprint_attributes):
        return None
    if test_attributes.get("matchtype") != "exact":
        return None
    if set(test_attributes) - (_TEST_METADATA_FIELDS | _SIGNAL_FIELDS):
        return None
    signals = sorted(_SIGNAL_FIELDS & set(test_attributes))
    if len(signals) != 1:
        return None
    raw_message_type = test_attributes.get("dhcptype")
    if raw_message_type in _REJECTED_MESSAGE_TYPES or raw_message_type not in _MESSAGE_TYPES:
        return None
    message_type = _MESSAGE_TYPES[raw_message_type]
    predicates = _any_predicates()
    if message_type != "ANY":
        predicates["message_type"] = {"mode": "EXACT_VALUE", "value": message_type}
    signal = signals[0]
    try:
        if signal == "dhcpoption55":
            predicates["parameter_request_list"] = {
                "mode": "EXACT_SEQUENCE",
                "value": _parse_byte_sequence(test_attributes[signal]),
            }
        elif signal == "dhcpoptions":
            predicates["option_order"] = {
                "mode": "EXACT_SEQUENCE",
                "value": _parse_byte_sequence(test_attributes[signal]),
            }
        else:
            vendor = test_attributes[signal]
            if (not vendor or len(vendor) > 128
                    or any(not 0x20 <= ord(character) <= 0x7E for character in vendor)):
                return None
            predicates["vendor_class"] = {"mode": "EXACT_VALUE", "value": vendor}
    except DeviceFingerprintValidationError:
        return None
    source_material = {
        "source_commit": SATORI_SOURCE_COMMIT,
        "source_path": SATORI_SOURCE_PATH,
        "source_sha256": SATORI_SOURCE_SHA256,
        "fingerprint_attributes": dict(fingerprint_attributes),
        "test_attributes": dict(test_attributes),
    }
    source_digest = hashlib.sha256(canonical_artifact_json(source_material)).hexdigest()
    source_identity = f"satori-dhcp-source:{source_digest}"
    taxonomy = _candidate_taxonomy(fingerprint_attributes)
    canonical_material = {
        "source_record_identity": source_identity,
        "dhcp_predicates": predicates,
        "candidate_taxonomy_refs": taxonomy,
    }
    canonical_digest = hashlib.sha256(canonical_artifact_json(canonical_material)).hexdigest()
    return {
        "record_type": "K1_DHCP",
        "canonical_record_id": f"k1-dhcp-satori:{canonical_digest}",
        "dhcp_predicates": predicates,
        "candidate_taxonomy_refs": taxonomy,
        "source_record_identity": source_identity,
    }


def _parse_verified_source(
    source_bytes: bytes,
    knowledge_provenance: ArtifactRef | dict[str, Any],
) -> SatoriK1ImportResult:
    if b"<!DOCTYPE" in source_bytes.upper() or b"<!ENTITY" in source_bytes.upper():
        _fail("Satori XML declarations are forbidden")
    try:
        root = ET.fromstring(source_bytes)
    except (ET.ParseError, ValueError) as exc:
        raise DeviceFingerprintValidationError("Invalid Satori DHCP XML") from exc
    fingerprints = list(_elements(root, "fingerprint"))
    accepted_records = []
    tests_total = 0
    for fingerprint in fingerprints:
        fingerprint_attributes = dict(fingerprint.attrib)
        tests = list(_elements(fingerprint, "test"))
        tests_total += len(tests)
        for test in tests:
            candidate = _record(fingerprint_attributes, dict(test.attrib))
            if candidate is not None:
                accepted_records.append(candidate)
    record_set = make_canonical_k1_record_set({
        "record_set_contract_version": 1,
        "knowledge_slot": "K1",
        "knowledge_provenance": _provenance_ref(knowledge_provenance),
        "records": accepted_records,
    })
    canonical_records = record_set.semantic_payload["records"]
    predicate_groups: dict[bytes, list[dict[str, Any]]] = {}
    for record in canonical_records:
        key = canonical_artifact_json(record["dhcp_predicates"])
        predicate_groups.setdefault(key, []).append(record)
    ambiguous = [group for group in predicate_groups.values() if len(group) > 1]
    audit = SatoriK1ImportAudit(
        fingerprints_total=len(fingerprints),
        source_tests_total=tests_total,
        source_tests_accepted=len(accepted_records),
        source_tests_rejected=tests_total - len(accepted_records),
        canonical_records_unique=len(canonical_records),
        predicate_groups_total=len(predicate_groups),
        ambiguous_predicate_groups=len(ambiguous),
        records_in_ambiguous_groups=sum(len(group) for group in ambiguous),
    )
    return SatoriK1ImportResult(record_set=record_set, audit=audit)


def import_satori_dhcp_bytes(
    source_bytes: bytes,
    knowledge_provenance: ArtifactRef | dict[str, Any],
) -> SatoriK1ImportResult:
    """Import exact pinned local bytes; never fetch and never retain raw source."""
    if not isinstance(source_bytes, bytes):
        _fail("Satori source must be bytes")
    if hashlib.sha256(source_bytes).hexdigest() != SATORI_SOURCE_SHA256:
        _fail("Satori DHCP source digest mismatch")
    result = _parse_verified_source(source_bytes, knowledge_provenance)
    if result.audit != ACCEPTED_SATORI_AUDIT:
        _fail("Satori DHCP import audit anchors changed")
    return result


def import_satori_dhcp_path(
    source_path: str | Path,
    knowledge_provenance: ArtifactRef | dict[str, Any],
) -> SatoriK1ImportResult:
    """Read a caller-supplied local path and import it without network access."""
    try:
        source_bytes = Path(source_path).read_bytes()
    except (OSError, TypeError, ValueError) as exc:
        raise DeviceFingerprintValidationError("Satori DHCP source is unavailable") from exc
    return import_satori_dhcp_bytes(source_bytes, knowledge_provenance)


def build_satori_source_governance_candidate() -> ArtifactContent:
    """Build the frozen current local/offline Satori K1 governance candidate."""
    return make_source_governance_record({
        "governance_contract_version": 1,
        "source_name": "Satori DHCP fingerprint corpus",
        "source_provenance": (
            "Pinned xnih/satori commit " + SATORI_SOURCE_COMMIT + ", path "
            + SATORI_SOURCE_PATH + ", Git blob SHA-1 " + SATORI_SOURCE_BLOB_SHA1
            + ", source SHA-256 " + SATORI_SOURCE_SHA256
        ),
        "license_identifier": "GPL-2.0-only",
        "license_source_reference": (
            "Pinned xnih/satori repository LICENSE plus upstream license-change commit "
            + SATORI_LICENSE_CHANGE_COMMIT
        ),
        "license_text_sha256": None,
        "local_storage_status": "STORED_LOCAL",
        "modification_import_status": "IMPORTED_NORMALIZED",
        "redistribution_status": "NOT_APPLICABLE",
        "attribution_requirement": "REQUIRED",
        "commercial_use_status": "ALLOWED",
        "review_basis_semantics": (
            "Current admitted scope is local/offline K1 source ingestion and canonical "
            "artifact generation only. Raw Satori source and generated Satori-derived "
            "corpus are not vendored, committed, or redistributed through the CaptivPortal "
            "public repository. Any later redistribution requires separate governance review."
        ),
        "unresolved_restrictions": [],
    })
