import json

import pytest

from app.device_fingerprint.models import DeviceFingerprintUnsupportedSchema, DeviceFingerprintValidationError
from app.device_fingerprint.payload_integrity import verify_persisted_payload
from app.device_fingerprint.schema_registry import EvidenceSchemaRegistry, build_production_schema_registry
from app.device_fingerprint.validation import canonical_json, canonical_sha256
from .test_portal_schema import payload_v2


def verify(source_kind="portal_headers", version=2, value=None, *, encoded=None, digest=None, registry=None):
    if value is None:
        value = payload_v2()
    if encoded is None:
        encoded = canonical_json(value)
    if digest is None:
        digest = canonical_sha256(encoded)
    if registry is None:
        registry = build_production_schema_registry()
    return verify_persisted_payload(source_kind, version, encoded, digest, registry)


def test_known_nokia_g21_payload_materializes_with_verified_bytes():
    value = payload_v2()
    result = verify(value=value)
    expected_bytes = len(canonical_json(value).encode("utf-8"))
    assert result.schema_supported is True
    assert result.materialized_payload == value
    assert result.reason_code is None
    assert result.verified_payload_bytes == expected_bytes
    assert result.materialized_payload_bytes == expected_bytes


def test_known_schema_invalid_payload_hard_fails():
    value = {**payload_v2(), "form_factor_mobile": False,
             "form_factor_tablet": False, "form_factor_desktop": False}
    with pytest.raises(DeviceFingerprintValidationError):
        verify(value=value)


@pytest.mark.parametrize("source_kind,version", [
    ("portal_headers", 3), ("tcp_syn", 3), ("future_source", 1),
])
def test_unknown_intact_schema_is_unsupported_without_fallback(source_kind, version):
    result = verify(source_kind, version)
    assert result.schema_supported is False
    assert result.materialized_payload is None
    assert result.reason_code == "unsupported_evidence_contract"
    assert result.verified_payload_bytes == len(canonical_json(payload_v2()).encode("utf-8"))
    assert result.materialized_payload_bytes == 0


def test_unknown_schema_never_invokes_any_registered_validator():
    calls = []
    registry = EvidenceSchemaRegistry()
    registry.register("portal_headers", 1, lambda value: calls.append(value))
    registry.freeze()
    assert verify("portal_headers", 3, registry=registry).schema_supported is False
    assert calls == []


def test_registered_validator_error_is_not_misclassified_as_unknown():
    registry = EvidenceSchemaRegistry()
    def reject(_value):
        raise DeviceFingerprintUnsupportedSchema("Registered validator rejected payload")
    registry.register("portal_headers", 2, reject)
    registry.freeze()
    with pytest.raises(DeviceFingerprintValidationError, match="Registered validator rejected"):
        verify(registry=registry)


@pytest.mark.parametrize("encoded", [
    "{", '{"a":1} trailing', "null", "[]", "42", '"x"',
    '{"a":NaN}', '{"a":Infinity}', '{"a":-Infinity}',
    '{"a":1,"a":2}', '{"a":{"b":1,"b":2}}',
])
def test_invalid_json_hard_fails_before_known_or_unknown_schema_lookup(encoded):
    for version in (2, 3):
        with pytest.raises(DeviceFingerprintValidationError):
            verify(version=version, encoded=encoded, digest=canonical_sha256(encoded))


@pytest.mark.parametrize("transform", [
    lambda encoded: encoded.replace(":", ": ", 1),
    lambda _encoded: json.dumps(payload_v2(), ensure_ascii=True, separators=(",", ":")),
    lambda encoded: encoded + "\n",
])
def test_noncanonical_text_hard_fails(transform):
    encoded = transform(canonical_json(payload_v2()))
    for version in (2, 3):
        with pytest.raises(DeviceFingerprintValidationError):
            verify(version=version, encoded=encoded, digest=canonical_sha256(encoded))


@pytest.mark.parametrize("version", [2, 3])
def test_mismatched_or_malformed_sha_hard_fails(version):
    for digest in ("0" * 64, "A" * 64, "0" * 63, "g" * 64):
        with pytest.raises(DeviceFingerprintValidationError):
            verify(version=version, digest=digest)


def test_integrity_precedes_registry_lookup_even_for_unknown_schema():
    registry = EvidenceSchemaRegistry()  # deliberately unfrozen
    with pytest.raises(DeviceFingerprintValidationError, match="digest mismatch"):
        verify(version=99, digest="0" * 64, registry=registry)
