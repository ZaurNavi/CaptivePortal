"""Deterministic offline import and raw IEEE assignment lookup for K4."""

from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
from typing import Any

from .artifact_content import ArtifactContent, ArtifactRef, canonical_artifact_json
from .k2a_conformance_artifacts import make_source_governance_record
from .knowledge_artifacts import make_canonical_k4_record_set
from .models import DeviceFingerprintValidationError

_HEADER = ["Registry", "Assignment", "Organization Name", "Organization Address"]
_FAMILIES = (
    ("MA-L", "oui.csv", "https://standards-oui.ieee.org/oui/oui.csv", 24, 6),
    ("MA-M", "mam.csv", "https://standards-oui.ieee.org/oui28/mam.csv", 28, 7),
    ("MA-S", "oui36.csv", "https://standards-oui.ieee.org/oui36/oui36.csv", 36, 9),
)
_ASSIGNMENT = re.compile(r"[0-9A-Fa-f]+")
_MAC48 = re.compile(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}")


def _fail(message: str) -> None:
    raise DeviceFingerprintValidationError(message)


def _source_bytes(value: Any) -> bytes:
    if not isinstance(value, bytes):
        _fail("IEEE source must be bytes")
    return value


def _identity(domain: str, semantic: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_artifact_json({
        "identity_version": domain, **semantic,
    })).hexdigest()
    return f"{domain}:sha256:{digest}"


def compute_ieee_k4_source_bundle_sha256(
    ma_l_bytes: bytes, ma_m_bytes: bytes, ma_s_bytes: bytes,
) -> str:
    """Hash the ordered logical three-member source bundle, never local paths."""
    members = []
    for (family, filename, url, _bits, _width), source in zip(
        _FAMILIES, (ma_l_bytes, ma_m_bytes, ma_s_bytes), strict=True,
    ):
        data = _source_bytes(source)
        members.append({
            "registry_family": family, "filename": filename, "source_url": url,
            "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data),
        })
    return hashlib.sha256(canonical_artifact_json({
        "bundle_identity_version": "ieee_ra_k4_source_bundle_v1",
        "members": members,
    })).hexdigest()


def _parse_member(source: bytes, family: str, bits: int, width: int) -> list[dict[str, Any]]:
    try:
        text = _source_bytes(source).decode("utf-8-sig", errors="strict")
        rows = csv.reader(io.StringIO(text, newline=""), strict=True)
        if next(rows, None) != _HEADER:
            _fail("Invalid IEEE CSV header")
        records = []
        for row in rows:
            if len(row) != 4:
                _fail("Invalid IEEE CSV row width")
            registry, assignment, organization, _address = row
            if registry != family or len(assignment) != width or _ASSIGNMENT.fullmatch(assignment) is None:
                _fail("Invalid IEEE assignment")
            label = unicodedata.normalize("NFC", organization)
            if not label.strip():
                _fail("Empty IEEE organization name")
            prefix = assignment.lower()
            if label == "Private":
                org_id = _identity("ieee_private_assignment_org_v1", {
                    "registry_family": family, "prefix_hex": prefix,
                })
            else:
                org_id = _identity("ieee_public_assignment_org_label_v1", {
                    "assignment_org_label": label,
                })
            semantic = {
                "registry_family": family, "prefix_hex": prefix,
                "assignment_org_id": org_id, "assignment_org_label": label,
            }
            source_id = _identity("ieee_k4_source_record_v1", semantic)
            record = {
                "record_type": "K4_IEEE_ASSIGNMENT",
                "prefix_hex": prefix, "prefix_length_bits": bits,
                **{key: semantic[key] for key in (
                    "assignment_org_id", "assignment_org_label", "registry_family",
                )},
                "source_record_identity": source_id,
                "manufacturer_mapping": None,
            }
            record["canonical_record_id"] = _identity("k4_ieee_assignment_record_v1", record)
            records.append(record)
        return records
    except (UnicodeError, csv.Error) as exc:
        raise DeviceFingerprintValidationError("Invalid IEEE CSV source") from exc


def import_ieee_k4_bytes(
    ma_l_bytes: bytes, ma_m_bytes: bytes, ma_s_bytes: bytes,
    *, knowledge_provenance: dict[str, str] | ArtifactRef,
) -> ArtifactContent:
    """Import only caller-supplied official CSV bytes; preserve prefix ambiguity."""
    provenance = (
        knowledge_provenance.as_dict()
        if isinstance(knowledge_provenance, ArtifactRef) else knowledge_provenance
    )
    distinct: dict[str, dict[str, Any]] = {}
    for (family, _filename, _url, bits, width), source in zip(
        _FAMILIES, (ma_l_bytes, ma_m_bytes, ma_s_bytes), strict=True,
    ):
        for record in _parse_member(source, family, bits, width):
            distinct[record["source_record_identity"]] = record
    return make_canonical_k4_record_set({
        "record_set_contract_version": 1,
        "knowledge_slot": "K4",
        "knowledge_provenance": provenance,
        "records": list(distinct.values()),
    })


def _canonical_mac(observed_mac: Any) -> str:
    if not isinstance(observed_mac, str) or _MAC48.fullmatch(observed_mac) is None:
        _fail("Invalid canonical Mac48")
    return observed_mac


def is_ieee_assignment_lookup_eligible(observed_mac: str) -> bool:
    """A locally administered Mac48 cannot yield an IEEE assignment claim."""
    return (int(_canonical_mac(observed_mac)[:2], 16) & 0x02) == 0


def match_k4_records(
    record_set: ArtifactContent, observed_mac: str,
) -> tuple[dict[str, Any], ...]:
    """Return every assignment at the first matching 36/28/24-bit prefix."""
    if not isinstance(record_set, ArtifactContent) or record_set.artifact_type != "CanonicalKnowledgeRecordSet":
        _fail("Invalid K4 record-set artifact")
    payload = record_set.semantic_payload
    if make_canonical_k4_record_set(payload).artifact_id != record_set.artifact_id:
        _fail("Invalid K4 record-set identity")
    if not is_ieee_assignment_lookup_eligible(observed_mac):
        return ()
    hexadecimal = observed_mac.replace(":", "")
    for bits, width in ((36, 9), (28, 7), (24, 6)):
        matches = tuple(record for record in payload["records"] if (
            record["prefix_length_bits"] == bits
            and record["prefix_hex"] == hexadecimal[:width]
        ))
        if matches:
            return matches
    return ()


def build_ieee_k4_source_governance_candidate() -> ArtifactContent:
    """Materialize the Owner/TechLead-admitted listing governance candidate."""
    return make_source_governance_record({
        "governance_contract_version": 1,
        "source_name": "IEEE Registration Authority MA-L/MA-M/MA-S Public Listings",
        "source_provenance": (
            "Official IEEE Registration Authority public listings: "
            "https://standards-oui.ieee.org/oui/oui.csv ; "
            "https://standards-oui.ieee.org/oui28/mam.csv ; "
            "https://standards-oui.ieee.org/oui36/oui36.csv"
        ),
        "license_identifier": "Public-Domain-IEEE-OUI-Public-Listing",
        "license_source_reference": (
            "Owner/TechLead review of IEEE public listings and the published "
            "public-domain/distribution statement; project governance, not independent legal advice"
        ),
        "license_text_sha256": None,
        "local_storage_status": "STORED_LOCAL",
        "modification_import_status": "IMPORTED_NORMALIZED",
        "redistribution_status": "ALLOWED",
        "attribution_requirement": "NOT_REQUIRED",
        "commercial_use_status": "ALLOWED",
        "review_basis_semantics": (
            "Owner/TechLead governance classification of the IEEE public listing and "
            "published public-domain/distribution statement; project governance, not "
            "independent legal advice. Source is changing/current and official listings "
            "are periodically updated. Raw files are not vendored in the repository. "
            "Initial manufacturer_mapping is null. Duplicate assignment prefixes are "
            "preserved safely. F-E5 owns exact freshness age thresholds."
        ),
        "unresolved_restrictions": [],
    })
