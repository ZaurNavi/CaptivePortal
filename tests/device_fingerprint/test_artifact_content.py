import json
from decimal import Decimal

import pytest

from app.device_fingerprint.artifact_content import (
    ArtifactContent, ArtifactRef, canonical_artifact_json, canonical_set,
    decode_artifact_json, make_artifact_content,
)
from app.device_fingerprint.models import DeviceFingerprintValidationError


def test_canonical_json_v1_pinned_fixture_and_nfc_equivalence():
    value = {"nested": {"sequence": [True, False, None, 7, 0, -3]},
             "ascii": "plain", "bmp": "caf\u00e9", "astral": "\U0001f600",
             "escapes": '"\\\n\t\x01'}
    encoded = canonical_artifact_json(value)
    assert encoded == (
        b'{"ascii":"plain","astral":"\\ud83d\\ude00","bmp":"caf\\u00e9",'
        b'"escapes":"\\\"\\\\\\n\\t\\u0001","nested":{"sequence":[true,false,null,7,0,-3]}}'
    )
    assert not encoded.endswith(b"\n")
    assert canonical_artifact_json({"\u00e9": "cafe\u0301"}) == canonical_artifact_json({"e\u0301": "caf\u00e9"})


@pytest.mark.parametrize("value", [
    {"e\u0301": 1, "\u00e9": 2}, {1: "bad"}, {"x": 1.0},
    {"x": Decimal("1")}, {"x": float("nan")}, {"x": float("inf")},
    {"nested": [float("-inf")]},
])
def test_canonical_rejects_noncanonical_or_noninteger_values(value):
    with pytest.raises(DeviceFingerprintValidationError):
        canonical_artifact_json(value)


@pytest.mark.parametrize("raw", [
    '{"a":1,"a":2}', '{"a":{"b":1,"b":2}}',
    '{"a":NaN}', '{"a":Infinity}', '{"a":-Infinity}',
])
def test_import_decode_rejects_duplicates_and_nonstandard_constants(raw):
    with pytest.raises(DeviceFingerprintValidationError):
        decode_artifact_json(raw)


def test_sequence_order_is_preserved_and_declared_set_is_permutation_invariant():
    assert canonical_artifact_json({"sequence": [2, 1]}) != canonical_artifact_json({"sequence": [1, 2]})
    assert canonical_set([{"id": "b"}, {"id": "a"}], lambda row: row["id"]) == [
        {"id": "a"}, {"id": "b"},
    ]
    assert canonical_set([3, 1, 2], lambda item: item) == [1, 2, 3]
    with pytest.raises(DeviceFingerprintValidationError):
        canonical_set([{"id": "a", "v": 1}, {"id": "a", "v": 2}], lambda row: row["id"])
    with pytest.raises(DeviceFingerprintValidationError):
        canonical_set(["a", "a"], lambda item: item)


def test_artifact_content_identity_is_stable_and_mutation_changes_identity():
    first = make_artifact_content("Fixture", {"items": ["a"], "flag": True})
    same = make_artifact_content("Fixture", {"flag": True, "items": ["a"]})
    changed = make_artifact_content("Fixture", {"items": ["b"], "flag": True})
    assert first.semantic_payload_json == same.semantic_payload_json
    assert first.digest_input_json == same.digest_input_json
    assert first.content_sha256 == same.content_sha256
    assert first.artifact_id == same.artifact_id
    assert first.content_sha256 != changed.content_sha256
    assert first.artifact_id != changed.artifact_id
    assert json.loads(first.digest_input_json) == {
        "artifact_type": "Fixture", "artifact_schema_version": 1,
        "semantic_payload": {"items": ["a"], "flag": True},
    }
    returned = first.semantic_payload
    returned["items"].append("mutated")
    assert first.semantic_payload == {"items": ["a"], "flag": True}
    with pytest.raises(DeviceFingerprintValidationError):
        ArtifactContent("Fixture", 1, first.semantic_payload_json, "0" * 64, first.artifact_id)


def test_artifact_ref_exact_digest_type_and_resolution():
    content = make_artifact_content("Fixture", {"x": 1})
    ref = ArtifactRef(content.artifact_id, content.content_sha256)
    assert ArtifactRef.from_dict(ref.as_dict()) == ref
    ref.resolve(content, "Fixture")
    with pytest.raises(DeviceFingerprintValidationError):
        ArtifactRef(content.artifact_id, "0" * 64)
    with pytest.raises(DeviceFingerprintValidationError):
        ref.resolve(content, "Other")
    other = make_artifact_content("Fixture", {"x": 2})
    with pytest.raises(DeviceFingerprintValidationError):
        ref.resolve(other, "Fixture")
    with pytest.raises(DeviceFingerprintValidationError):
        ArtifactRef.from_dict({**ref.as_dict(), "extra": 1})
