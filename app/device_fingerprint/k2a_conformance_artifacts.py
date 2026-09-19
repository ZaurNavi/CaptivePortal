"""Immutable R14 K2A conformance and external-source governance artifacts."""

from __future__ import annotations

import re
from typing import Any

from .artifact_content import ArtifactContent, canonical_set, make_artifact_content
from .models import DeviceFingerprintValidationError

_SHA256 = re.compile(r"[0-9a-f]{64}")
_K2A_FIELDS = frozenset({
    "p0f_implementation_identity", "p0f_implementation_digest",
    "p0f_reference_corpus_identity", "p0f_reference_corpus_digest",
    "supported_request_scope", "p0f_runtime_serializer_contract_version",
    "matcher_implementation_contract_version", "conformance_fixture_refs",
    "conformance_status",
})
_FIXTURE_FIELDS = frozenset({"fixture_set_id", "fixture_set_digest"})
_GOVERNANCE_FIELDS = frozenset({
    "governance_contract_version", "source_name", "source_provenance",
    "license_identifier", "license_source_reference", "license_text_sha256",
    "local_storage_status", "modification_import_status",
    "redistribution_status", "attribution_requirement", "commercial_use_status",
    "review_basis_semantics", "unresolved_restrictions",
})
_LOCAL_STORAGE = frozenset({"NOT_STORED", "STORED_LOCAL", "STORED_BUNDLED"})
_MODIFICATION = frozenset({
    "UNMODIFIED_SOURCE", "IMPORTED_NORMALIZED", "MODIFIED_WITH_PERMISSION",
    "NOT_ADMITTED",
})
_REDISTRIBUTION = frozenset({
    "ALLOWED", "RESTRICTED", "PROHIBITED", "NOT_APPLICABLE",
    "UNKNOWN_NOT_ADMITTED",
})
_ATTRIBUTION = frozenset({"REQUIRED", "NOT_REQUIRED", "UNKNOWN_NOT_ADMITTED"})
_COMMERCIAL = frozenset({
    "ALLOWED", "RESTRICTED", "PROHIBITED", "NOT_APPLICABLE",
    "UNKNOWN_NOT_ADMITTED",
})

_ARCHIVE_SHA256 = "543b68638e739be5c3e818c3958c3b124ac0ccb8be62ba274b4241dbdec00e7f"
_CORPUS_SHA256 = "45f27bcc65de0f64bc69356dc0662e3366e05e67a0e98fd2251808e253b6be40"
_ORACLE_SHA256 = "81ac7a7851980afd1f825b15e7ab4655a221f23b8f99d3c337c49752242811d3"
_LICENSE_SHA256 = "961c2671591840a60ec9b927dc6036ec5fc5fd861869647c2c4bc1050da48261"
_FIXTURE_SHA256 = "e579af6bb7086cf424b31c965bd30ed6a6fb4e12c5c9cab765158f36ee76241b"
_SCOPE = (
    "IPv4 outbound/request-side initial TCP SYN semantics derived exclusively "
    "from validated tcp_syn/2 evidence for pinned p0f 3.09b request matcher conformance"
)


def _fail() -> None:
    raise DeviceFingerprintValidationError("Invalid K2A foundation artifact")


def _shape(value: Any, fields: frozenset[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        _fail()
    return value


def _text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail()
    return value


def _digest(value: Any) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        _fail()
    return value


def _enum(value: Any, allowed: frozenset[str]) -> str:
    if value not in allowed or not isinstance(value, str):
        _fail()
    return value


def make_k2a_conformance_package(payload: dict[str, Any]) -> ArtifactContent:
    """Validate the exact C.3.36 payload and canonicalize its fixture SET."""
    value = _shape(payload, _K2A_FIELDS)
    for field in (
        "p0f_implementation_identity", "p0f_reference_corpus_identity",
        "supported_request_scope", "p0f_runtime_serializer_contract_version",
        "matcher_implementation_contract_version",
    ):
        _text(value[field])
    _digest(value["p0f_implementation_digest"])
    _digest(value["p0f_reference_corpus_digest"])
    if value["conformance_status"] != "PASS":
        _fail()
    fixtures = value["conformance_fixture_refs"]
    if not isinstance(fixtures, list) or not fixtures:
        _fail()
    for fixture in fixtures:
        _shape(fixture, _FIXTURE_FIELDS)
        _text(fixture["fixture_set_id"])
        _digest(fixture["fixture_set_digest"])
    fixtures = canonical_set(fixtures, lambda fixture: fixture["fixture_set_id"])
    return make_artifact_content("K2AConformancePackage", {
        **value, "conformance_fixture_refs": fixtures,
    })


def make_source_governance_record(payload: dict[str, Any]) -> ArtifactContent:
    """Validate the exact C.3.20 payload and its admission-related invariants."""
    value = _shape(payload, _GOVERNANCE_FIELDS)
    version = value["governance_contract_version"]
    if type(version) is not int or not 0 < version <= 2**31 - 1:
        _fail()
    for field in (
        "source_name", "source_provenance", "license_identifier",
        "license_source_reference", "review_basis_semantics",
    ):
        _text(value[field])
    _enum(value["local_storage_status"], _LOCAL_STORAGE)
    modification = _enum(value["modification_import_status"], _MODIFICATION)
    redistribution = _enum(value["redistribution_status"], _REDISTRIBUTION)
    attribution = _enum(value["attribution_requirement"], _ATTRIBUTION)
    commercial = _enum(value["commercial_use_status"], _COMMERCIAL)
    license_digest = value["license_text_sha256"]
    if license_digest is not None:
        _digest(license_digest)
    restrictions = value["unresolved_restrictions"]
    if not isinstance(restrictions, list):
        _fail()
    for restriction in restrictions:
        _text(restriction)
    restrictions = canonical_set(restrictions, lambda restriction: restriction)
    has_unknown = (
        redistribution == "UNKNOWN_NOT_ADMITTED"
        or attribution == "UNKNOWN_NOT_ADMITTED"
        or commercial == "UNKNOWN_NOT_ADMITTED"
    )
    if (has_unknown or restrictions) and modification != "NOT_ADMITTED":
        _fail()
    return make_artifact_content("SourceGovernanceRecord", {
        **value, "unresolved_restrictions": restrictions,
    })


def build_k2a_conformance_package() -> ArtifactContent:
    return make_k2a_conformance_package({
        "p0f_implementation_identity": "p0f 3.09b pinned x86_64 binary",
        "p0f_implementation_digest": _ORACLE_SHA256,
        "p0f_reference_corpus_identity": "p0f 3.09b upstream p0f.fp (external, not admitted)",
        "p0f_reference_corpus_digest": _CORPUS_SHA256,
        "supported_request_scope": _SCOPE,
        "p0f_runtime_serializer_contract_version": "p0f_runtime_ipv4_request_v1",
        "matcher_implementation_contract_version": "p0f_3_09b_ipv4_request_matcher_v1",
        "conformance_fixture_refs": [{
            "fixture_set_id": "k2a_synthetic_ipv4_request_v1",
            "fixture_set_digest": _FIXTURE_SHA256,
        }],
        "conformance_status": "PASS",
    })


def _governance_payload(source_name: str, provenance: str, license_reference: str,
                        review_basis: str) -> dict[str, Any]:
    return {
        "governance_contract_version": 1,
        "source_name": source_name,
        "source_provenance": provenance,
        "license_identifier": "LGPL-2.1-only",
        "license_source_reference": license_reference,
        "license_text_sha256": _LICENSE_SHA256,
        "local_storage_status": "STORED_LOCAL",
        "modification_import_status": "UNMODIFIED_SOURCE",
        "redistribution_status": "NOT_APPLICABLE",
        "attribution_requirement": "REQUIRED",
        "commercial_use_status": "ALLOWED",
        "review_basis_semantics": review_basis,
        "unresolved_restrictions": [],
    }


def build_k2a_source_governance_candidates() -> tuple[ArtifactContent, ...]:
    """Return three separate candidates; this does not admit any source."""
    candidates = (
        make_source_governance_record(_governance_payload(
            "p0f 3.09b upstream source archive",
            "Pinned p0f_3.09b.orig.tar.gz used for local K2A source inspection; "
            f"SHA256 {_ARCHIVE_SHA256}",
            "p0f-3.09b/docs/COPYING and upstream source headers",
            "Candidate scope is controlled local/offline K2A source inspection and "
            "conformance only; source is not vendored, distributed, deployed, or imported "
            "into CaptivPortal production. Future vendoring or distribution requires "
            "separate review.",
        )),
        make_source_governance_record(_governance_payload(
            "p0f 3.09b p0f.fp reference corpus",
            "Pinned upstream p0f.fp used only as controlled local K2A oracle reference; "
            f"SHA256 {_CORPUS_SHA256}",
            "p0f.fp copyright/license header and p0f-3.09b/docs/COPYING",
            "Candidate scope is read-only controlled local K2A oracle/conformance reference. "
            "Full upstream p0f.fp is not imported, vendored, redistributed, or selected as "
            "CaptivPortal production K2B knowledge. K2B requires separate governance.",
        )),
        make_source_governance_record(_governance_payload(
            "p0f 3.09b local oracle binary",
            "Pinned local x86_64 build produced from the pinned unmodified p0f 3.09b source "
            f"for controlled offline K2A conformance; SHA256 {_ORACLE_SHA256}",
            "p0f-3.09b/docs/COPYING and upstream source headers",
            "Candidate scope is explicit controlled local/offline execution as the pinned K2A "
            "oracle only. Binary is not vendored, redistributed, deployed, or used as a "
            "CaptivPortal production runtime dependency.",
        )),
    )
    return tuple(sorted(candidates, key=lambda candidate: (
        candidate.artifact_id, candidate.semantic_payload_json,
    )))
