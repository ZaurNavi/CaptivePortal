"""F-C2 immutable package and governance candidate contract tests."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.device_fingerprint.artifact_content import canonical_artifact_json
from app.device_fingerprint.k2a_conformance_artifacts import (
    build_k2a_conformance_package, build_k2a_source_governance_candidates,
    make_k2a_conformance_package, make_source_governance_record,
)
from app.device_fingerprint.models import DeviceFingerprintValidationError

ROOT = Path(__file__).resolve().parents[2]
K2A = ROOT / "research" / "device_fingerprint_k2a"


def package_payload() -> dict:
    return deepcopy(build_k2a_conformance_package().semantic_payload)


def governance_payload() -> dict:
    return deepcopy(build_k2a_source_governance_candidates()[0].semantic_payload)


def test_exact_package_matches_retained_candidate_and_is_deterministic():
    retained = json.loads(
        (K2A / "evidence" / "K2AConformancePackage.candidate.json").read_text("ascii")
    )
    first = build_k2a_conformance_package()
    second = build_k2a_conformance_package()
    assert first.artifact_type == "K2AConformancePackage"
    assert first.artifact_schema_version == 1
    assert first.artifact_id == (
        "K2AConformancePackage:v1:sha256:"
        "bbe6fa22ac50e568ee4580faac4ad09f7301bb38f6af2ab2075b8adc39262328"
    )
    assert first.semantic_payload == retained
    assert first == second
    assert first.semantic_payload_json == canonical_artifact_json(retained)
    assert json.loads(first.digest_input_json) == {
        "artifact_type": "K2AConformancePackage",
        "artifact_schema_version": 1,
        "semantic_payload": retained,
    }


@pytest.mark.parametrize("mutate", [
    lambda p: p.update(extra=True),
    lambda p: p.update(p0f_implementation_identity=""),
    lambda p: p.update(p0f_implementation_digest="A" * 64),
    lambda p: p.update(p0f_reference_corpus_digest="0" * 63),
    lambda p: p.update(conformance_status="FAIL"),
    lambda p: p.update(conformance_fixture_refs=[]),
    lambda p: p["conformance_fixture_refs"][0].update(extra=True),
    lambda p: p["conformance_fixture_refs"][0].update(fixture_set_id=""),
    lambda p: p["conformance_fixture_refs"][0].update(fixture_set_digest="bad"),
])
def test_package_fails_closed_for_bad_shape_or_values(mutate):
    payload = package_payload()
    mutate(payload)
    with pytest.raises(DeviceFingerprintValidationError):
        make_k2a_conformance_package(payload)


def test_fixture_ref_set_uses_primary_key_then_canonical_bytes_and_rejects_duplicates():
    payload = package_payload()
    original = payload["conformance_fixture_refs"][0]
    payload["conformance_fixture_refs"] = [
        {"fixture_set_id": "z", "fixture_set_digest": "f" * 64},
        {"fixture_set_id": "a", "fixture_set_digest": "e" * 64},
        original,
    ]
    result = make_k2a_conformance_package(payload).semantic_payload
    assert [row["fixture_set_id"] for row in result["conformance_fixture_refs"]] == [
        "a", "k2a_synthetic_ipv4_request_v1", "z",
    ]
    payload["conformance_fixture_refs"].append(deepcopy(original))
    with pytest.raises(DeviceFingerprintValidationError):
        make_k2a_conformance_package(payload)


def test_three_governance_candidates_match_retained_review_material():
    expected = json.loads((K2A / "source_governance_candidates.json").read_text("utf-8"))
    first = build_k2a_source_governance_candidates()
    second = build_k2a_source_governance_candidates()
    assert len(first) == 3
    assert first == second
    assert all(item.artifact_type == "SourceGovernanceRecord" for item in first)
    assert all(item.artifact_schema_version == 1 for item in first)
    assert {canonical_artifact_json(item.semantic_payload) for item in first} == {
        canonical_artifact_json(item) for item in expected
    }
    assert {item.semantic_payload["source_name"] for item in first} == {
        "p0f 3.09b upstream source archive",
        "p0f 3.09b p0f.fp reference corpus",
        "p0f 3.09b local oracle binary",
    }
    assert {item.artifact_id for item in first} == {
        "SourceGovernanceRecord:v1:sha256:11af2d31c21c97c8a7df57bc4be0d491708aaa82081fd9129e35d0eb9ecd02ea",
        "SourceGovernanceRecord:v1:sha256:13920c1f5bc09b17d0d500de30df2d8c295da8f38d340a4d016d294d9bf34c9b",
        "SourceGovernanceRecord:v1:sha256:997614c80816e8130401a0d1f7ad1c72ac03834bbba311d973d92fa390289074",
    }
    assert all(item.semantic_payload["unresolved_restrictions"] == [] for item in first)


@pytest.mark.parametrize("mutate", [
    lambda p: p.update(extra=True),
    lambda p: p.update(governance_contract_version=0),
    lambda p: p.update(governance_contract_version=True),
    lambda p: p.update(source_name=" "),
    lambda p: p.update(license_text_sha256="A" * 64),
    lambda p: p.update(local_storage_status="UNKNOWN"),
    lambda p: p.update(modification_import_status="MODIFIED"),
    lambda p: p.update(redistribution_status="UNKNOWN"),
    lambda p: p.update(attribution_requirement="OPTIONAL"),
    lambda p: p.update(commercial_use_status="UNKNOWN"),
])
def test_governance_record_fails_closed_for_bad_shape_enums_or_sha(mutate):
    payload = governance_payload()
    mutate(payload)
    with pytest.raises(DeviceFingerprintValidationError):
        make_source_governance_record(payload)


def test_license_text_digest_is_independent_of_governed_source_storage():
    payload = governance_payload()
    payload["local_storage_status"] = "NOT_STORED"
    payload["license_text_sha256"] = "1" * 64
    assert make_source_governance_record(payload).semantic_payload["license_text_sha256"] == "1" * 64
    payload["local_storage_status"] = "STORED_LOCAL"
    payload["license_text_sha256"] = None
    assert make_source_governance_record(payload).semantic_payload["license_text_sha256"] is None
    payload["license_text_sha256"] = "malformed"
    with pytest.raises(DeviceFingerprintValidationError):
        make_source_governance_record(payload)


def test_unresolved_restrictions_are_canonical_and_require_not_admitted_status():
    payload = governance_payload()
    payload["modification_import_status"] = "NOT_ADMITTED"
    payload["unresolved_restrictions"] = ["z restriction", "a restriction"]
    result = make_source_governance_record(payload).semantic_payload
    assert result["unresolved_restrictions"] == ["a restriction", "z restriction"]
    payload["unresolved_restrictions"].append("z restriction")
    with pytest.raises(DeviceFingerprintValidationError):
        make_source_governance_record(payload)
    payload = governance_payload()
    payload["unresolved_restrictions"] = ["material unresolved restriction"]
    with pytest.raises(DeviceFingerprintValidationError):
        make_source_governance_record(payload)


@pytest.mark.parametrize("field", [
    "redistribution_status", "attribution_requirement", "commercial_use_status",
])
def test_material_unknown_status_requires_not_admitted(field):
    payload = governance_payload()
    payload[field] = "UNKNOWN_NOT_ADMITTED"
    with pytest.raises(DeviceFingerprintValidationError):
        make_source_governance_record(payload)
    payload["modification_import_status"] = "NOT_ADMITTED"
    assert make_source_governance_record(payload).semantic_payload[field] == "UNKNOWN_NOT_ADMITTED"
