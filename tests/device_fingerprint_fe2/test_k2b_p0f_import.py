"""Narrow K2B contract and offline import proofs without external corpus data."""

from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

from app.device_fingerprint.artifact_content import ArtifactRef
from app.device_fingerprint.k2b_p0f_import import (
    P0F_SOURCE_SIZE,
    _parse_verified_source,
    build_p0f_k2b_source_governance_candidate,
    import_p0f_k2b_bytes,
    verify_p0f_source_bytes,
)
from app.device_fingerprint.knowledge_artifacts import (
    canonical_k2b_match_rule,
    make_canonical_k2b_record_set,
)
from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.p0f_semantics import RUNTIME_CONTRACT, parse_request_signature

_DIGEST = "0" * 64
_PROVENANCE = ArtifactRef(
    artifact_id=f"KnowledgeProvenanceManifest:v1:sha256:{_DIGEST}",
    content_sha256=_DIGEST,
).as_dict()
_RULE = "4:64:0:0:65535,0:::0"


def _source(*lines: str) -> bytes:
    return ("\n".join(lines) + "\n").encode("utf-8")


def _synthetic_import(*lines: str):
    source = _source("[tcp:request]", *lines)
    return _parse_verified_source(source, _PROVENANCE, hashlib.sha256(source).hexdigest())


def _records(result):
    return result.record_set.semantic_payload["records"]


def test_k2b_exact_closed_record_and_k2a_round_trip():
    result = _synthetic_import("label = s:unix:Linux:fixture", f"sig =   {_RULE}   ")
    record = _records(result)[0]
    assert result.record_set.semantic_payload["knowledge_slot"] == "K2B"
    assert set(record) == {
        "record_type", "canonical_record_id", "rule_representation",
        "canonical_match_rule", "dimension_claims", "source_character",
        "source_record_identity",
    }
    assert record["rule_representation"] == RUNTIME_CONTRACT
    assert record["canonical_match_rule"] == _RULE
    assert canonical_k2b_match_rule(f"  {_RULE}  ") == _RULE
    assert canonical_k2b_match_rule(record["canonical_match_rule"]) == _RULE
    assert parse_request_signature(_RULE, signature_id="fixture", generic=False,
                                   userland=False) == parse_request_signature(
        record["canonical_match_rule"], signature_id="fixture", generic=False,
        userland=False,
    )
    assert make_canonical_k2b_record_set(
        result.record_set.semantic_payload,
    ).artifact_id == result.record_set.artifact_id

    bad = deepcopy(result.record_set.semantic_payload)
    bad["records"][0]["extra"] = "forbidden"
    with pytest.raises(DeviceFingerprintValidationError):
        make_canonical_k2b_record_set(bad)
    bad = deepcopy(result.record_set.semantic_payload)
    bad["records"][0]["rule_representation"] = "another-rule-language"
    with pytest.raises(DeviceFingerprintValidationError):
        make_canonical_k2b_record_set(bad)
    bad = deepcopy(result.record_set.semantic_payload)
    bad["records"][0]["canonical_match_rule"] = f" {_RULE}"
    with pytest.raises(DeviceFingerprintValidationError):
        make_canonical_k2b_record_set(bad)


@pytest.mark.parametrize(("label", "platform"), [
    ("s:unix:Linux:fixture", "linux"),
    ("s:unix:Linux:(Android)", "android"),
    ("s:win:Windows:fixture", "windows"),
    ("s:unix:Mac OS X:fixture", "macos"),
    ("s:unix:iOS:fixture", "ios"),
])
def test_only_direct_specific_platform_claim_is_supporting(label, platform):
    result = _synthetic_import(f"label = {label}", f"sig = {_RULE}")
    record = _records(result)[0]
    assert record["source_character"] == "legacy"
    claims = {claim["dimension_name"]: claim for claim in record["dimension_claims"]}
    assert claims["platform_family"]["outcome_kind"] == "CANONICAL_VALUE"
    assert claims["platform_family"]["canonical_target_id"] == platform
    assert claims["platform_family"]["base_claim_strength"] == "supporting"
    for dimension in ("device_class", "manufacturer_family", "model_family"):
        assert claims[dimension]["outcome_kind"] == "NO_CLAIM"
        assert claims[dimension]["base_claim_strength"] is None
    assert all(claim["base_claim_strength"] != "strong" for claim in claims.values())


def test_specific_linux_version_flavor_is_supporting_linux():
    result = _synthetic_import(
        "label = s:unix:Linux:4.x and newer", f"sig = {_RULE}",
    )
    platform = next(claim for claim in _records(result)[0]["dimension_claims"]
                    if claim["dimension_name"] == "platform_family")
    assert platform["canonical_target_id"] == "linux"
    assert platform["base_claim_strength"] == "supporting"


def test_non_specific_mixed_unsupported_and_other_sections_are_excluded():
    result = _synthetic_import(
        "label = g:unix:Linux:generic", f"sig = {_RULE}",
        "label = s:!:NMap:userland", f"sig = {_RULE}",
        "label = s:unix:MacOS X:10.9 or newer (sometimes iPhone or iPad)", f"sig = {_RULE}",
        "label = s:other:UnknownOS:fixture", f"sig = {_RULE}",
        "label = malformed", f"sig = {_RULE}",
        "[mtu]", "label = s:win:Windows:fixture", f"sig = {_RULE}",
        "[tcp:response]", "label = s:win:Windows:fixture", f"sig = {_RULE}",
        "[http:request]", "label = s:win:Windows:fixture", f"sig = {_RULE}",
        "[http:response]", "label = s:win:Windows:fixture", f"sig = {_RULE}",
    )
    assert result.audit.tcp_request_source_signatures == 5
    assert _records(result) == []


def test_admitted_malformed_rule_fails_closed():
    with pytest.raises(DeviceFingerprintValidationError, match="Invalid K2B match rule"):
        _synthetic_import("label = s:unix:Linux:fixture", "sig = 4:bad:signature")


def test_source_claim_identity_is_order_independent_and_duplicates_collapse():
    linux = ("label = s:unix:Linux:fixture", f"sig = {_RULE}")
    windows = ("label = s:win:Windows:fixture", f"sig = {_RULE}")
    first = _synthetic_import(*linux, *linux, *windows)
    second = _synthetic_import(*windows, *linux, *linux)
    assert first.audit.tcp_request_source_signatures == 3
    assert first.audit.admitted_canonical_records == 2
    assert first.record_set.artifact_id == second.record_set.artifact_id
    assert first.record_set.semantic_payload == second.record_set.semantic_payload
    assert len({row["source_record_identity"] for row in _records(first)}) == 2
    assert len({row["canonical_match_rule"] for row in _records(first)}) == 1


def test_pinned_source_size_and_blob_mismatch_fail_before_import():
    with pytest.raises(DeviceFingerprintValidationError, match="byte length"):
        verify_p0f_source_bytes(b"synthetic")
    with pytest.raises(DeviceFingerprintValidationError, match="Git blob"):
        verify_p0f_source_bytes(b"x" * P0F_SOURCE_SIZE)
    with pytest.raises(DeviceFingerprintValidationError, match="byte length"):
        import_p0f_k2b_bytes(b"synthetic", _PROVENANCE)
    with pytest.raises(DeviceFingerprintValidationError, match="byte length"):
        build_p0f_k2b_source_governance_candidate(b"synthetic")
