"""Offline import of the pinned legacy p0f TCP request knowledge source."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifact_content import ArtifactContent, ArtifactRef, canonical_artifact_json
from .k2a_conformance_artifacts import make_source_governance_record
from .knowledge_artifacts import canonical_k2b_match_rule, make_canonical_k2b_record_set
from .models import DeviceFingerprintValidationError
from .p0f_semantics import RUNTIME_CONTRACT

P0F_SOURCE_COMMIT = "7687e779c42c256c1f36b8c48da7e1f8fe24c2d4"
P0F_SOURCE_PATH = "p0f.fp"
P0F_SOURCE_BLOB_SHA1 = "c4b38b7e5b5621c70df56aa49127b5aaae1ec7e8"
P0F_SOURCE_SIZE = 36529

_PLATFORM_COUNTS = (
    ("android", 3), ("chromeos", 0), ("ios", 1),
    ("linux", 25), ("macos", 2), ("windows", 12),
)
_PLATFORM_NAMES = {
    "Windows": "windows", "Mac OS X": "macos", "iOS": "ios",
}
_DIMENSIONS = (
    "platform_family", "device_class", "manufacturer_family", "model_family",
)


@dataclass(frozen=True, slots=True)
class P0fK2BImportAudit:
    tcp_request_source_signatures: int
    admitted_canonical_records: int
    platform_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class P0fK2BImportResult:
    record_set: ArtifactContent
    source_sha256: str
    audit: P0fK2BImportAudit


ACCEPTED_P0F_AUDIT = P0fK2BImportAudit(
    tcp_request_source_signatures=94,
    admitted_canonical_records=43,
    platform_counts=_PLATFORM_COUNTS,
)


def _fail(message: str) -> None:
    raise DeviceFingerprintValidationError(message)


def verify_p0f_source_bytes(source_bytes: bytes) -> str:
    """Verify the pinned Git blob and return the calculated source SHA-256."""
    if not isinstance(source_bytes, bytes) or len(source_bytes) != P0F_SOURCE_SIZE:
        _fail("Pinned p0f source byte length mismatch")
    blob_input = f"blob {len(source_bytes)}\0".encode("ascii") + source_bytes
    if hashlib.sha1(blob_input).hexdigest() != P0F_SOURCE_BLOB_SHA1:
        _fail("Pinned p0f source Git blob mismatch")
    return hashlib.sha256(source_bytes).hexdigest()


def _provenance_ref(value: ArtifactRef | dict[str, Any]) -> dict[str, str]:
    reference = value if isinstance(value, ArtifactRef) else ArtifactRef.from_dict(value)
    if not reference.artifact_id.startswith("KnowledgeProvenanceManifest:v1:sha256:"):
        _fail("Invalid K2B knowledge provenance reference")
    return reference.as_dict()


def _platform(label: str) -> str | None:
    parts = label.split(":", 3)
    if len(parts) != 4 or any(not part for part in parts):
        return None
    label_type, label_class, name, flavor = parts
    if label_type != "s" or label_class == "!":
        return None
    if name == "Linux":
        return "android" if flavor == "(Android)" else "linux"
    # The named mixed Mac/iPhone/iPad flavor is outside the admitted V1 scope.
    if name == "Mac OS X" and flavor == "10.9 or newer (sometimes iPhone or iPad)":
        return None
    return _PLATFORM_NAMES.get(name)


def _dimension_claims(platform: str) -> list[dict[str, Any]]:
    return [{
        "dimension_name": dimension,
        "outcome_kind": "CANONICAL_VALUE" if dimension == "platform_family" else "NO_CLAIM",
        "canonical_target_id": platform if dimension == "platform_family" else None,
        "broad_taxon_ref": None,
        "out_of_scope_taxon_ref": None,
        "base_claim_strength": "supporting" if dimension == "platform_family" else None,
    } for dimension in _DIMENSIONS]


def _record(label: str, raw_rule: str, platform: str) -> dict[str, Any]:
    rule = canonical_k2b_match_rule(raw_rule)
    source_material = {
        "source_commit": P0F_SOURCE_COMMIT,
        "source_path": P0F_SOURCE_PATH,
        "source_blob_sha1": P0F_SOURCE_BLOB_SHA1,
        "source_label": label,
        "canonical_match_rule": rule,
    }
    source_digest = hashlib.sha256(canonical_artifact_json(source_material)).hexdigest()
    source_identity = f"p0f-k2b-source:v1:sha256:{source_digest}"
    claims = _dimension_claims(platform)
    canonical_material = {
        "source_record_identity": source_identity,
        "canonical_match_rule": rule,
        "dimension_claims": claims,
        "source_character": "legacy",
    }
    canonical_digest = hashlib.sha256(canonical_artifact_json(canonical_material)).hexdigest()
    return {
        "record_type": "K2B_TCP",
        "canonical_record_id": f"k2b-p0f:v1:sha256:{canonical_digest}",
        "rule_representation": RUNTIME_CONTRACT,
        "canonical_match_rule": rule,
        "dimension_claims": claims,
        "source_character": "legacy",
        "source_record_identity": source_identity,
    }


def _parse_verified_source(
    source_bytes: bytes,
    knowledge_provenance: ArtifactRef | dict[str, Any],
    source_sha256: str,
) -> P0fK2BImportResult:
    try:
        text = source_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DeviceFingerprintValidationError("Invalid p0f source encoding") from exc
    section = ""
    label = ""
    platform: str | None = None
    signature_count = 0
    records_by_source: dict[str, dict[str, Any]] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith((";", "#")):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            label = ""
            platform = None
            continue
        if section != "tcp:request" or "=" not in stripped:
            continue
        key, _, raw_value = stripped.partition("=")
        key = key.strip()
        if key == "label":
            label = raw_value.strip()
            platform = _platform(label)
        elif key == "sig":
            signature_count += 1
            if platform is None:
                continue
            record = _record(label, raw_value, platform)
            identity = record["source_record_identity"]
            previous = records_by_source.setdefault(identity, record)
            if previous != record:
                _fail("Conflicting p0f source record identity")
    record_set = make_canonical_k2b_record_set({
        "record_set_contract_version": 1,
        "knowledge_slot": "K2B",
        "knowledge_provenance": _provenance_ref(knowledge_provenance),
        "records": list(records_by_source.values()),
    })
    counts = {platform: 0 for platform, _ in _PLATFORM_COUNTS}
    for record in record_set.semantic_payload["records"]:
        for claim in record["dimension_claims"]:
            if claim["dimension_name"] == "platform_family":
                counts[claim["canonical_target_id"]] += 1
    audit = P0fK2BImportAudit(
        tcp_request_source_signatures=signature_count,
        admitted_canonical_records=len(records_by_source),
        platform_counts=tuple(sorted(counts.items())),
    )
    return P0fK2BImportResult(record_set, source_sha256, audit)


def import_p0f_k2b_bytes(
    source_bytes: bytes, knowledge_provenance: ArtifactRef | dict[str, Any],
) -> P0fK2BImportResult:
    """Import only the exact pinned local source; never fetch or retain raw data."""
    source_sha256 = verify_p0f_source_bytes(source_bytes)
    result = _parse_verified_source(source_bytes, knowledge_provenance, source_sha256)
    if result.audit != ACCEPTED_P0F_AUDIT:
        _fail("Pinned p0f K2B import audit anchors changed")
    return result


def import_p0f_k2b_path(
    source_path: str | Path, knowledge_provenance: ArtifactRef | dict[str, Any],
) -> P0fK2BImportResult:
    """Read an explicitly supplied local file and apply the pinned import contract."""
    try:
        source_bytes = Path(source_path).read_bytes()
    except (OSError, TypeError, ValueError) as exc:
        raise DeviceFingerprintValidationError("Pinned p0f source is unavailable") from exc
    return import_p0f_k2b_bytes(source_bytes, knowledge_provenance)


def build_p0f_k2b_source_governance_candidate(source_bytes: bytes) -> ArtifactContent:
    """Build a governance candidate using the verified local source digest."""
    source_sha256 = verify_p0f_source_bytes(source_bytes)
    return make_source_governance_record({
        "governance_contract_version": 1,
        "source_name": "peace-maker p0f3 production TCP fingerprint corpus",
        "source_provenance": (
            "Pinned peace-maker/p0f3-database commit " + P0F_SOURCE_COMMIT
            + ", path " + P0F_SOURCE_PATH + ", Git blob SHA-1 "
            + P0F_SOURCE_BLOB_SHA1 + ", source SHA-256 " + source_sha256
        ),
        "license_identifier": "LGPL-2.0-only",
        "license_source_reference": "Pinned p0f.fp license header and pinned repository LICENSE",
        "license_text_sha256": None,
        "local_storage_status": "STORED_LOCAL",
        "modification_import_status": "IMPORTED_NORMALIZED",
        "redistribution_status": "NOT_APPLICABLE",
        "attribution_requirement": "REQUIRED",
        "commercial_use_status": "ALLOWED",
        "review_basis_semantics": (
            "Source is used only as local/offline external knowledge input and is classified "
            "as legacy. Raw p0f.fp is not vendored into CaptivPortal; the generated K2B "
            "corpus is not committed into the public CaptivPortal repository. Only the "
            "bounded specific TCP request subset is normalized. Any future redistribution "
            "requires separate governance review."
        ),
        "unresolved_restrictions": [],
    })
