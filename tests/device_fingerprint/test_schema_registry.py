import pytest

from app.device_fingerprint.models import DeviceFingerprintUnsupportedSchema, DeviceFingerprintValidationError
from app.device_fingerprint.schema_registry import EvidenceSchemaRegistry, build_production_schema_registry


def test_production_registry_is_frozen_and_contains_task02_schemas():
    registry = build_production_schema_registry()
    assert registry.frozen
    for source_kind in ("dhcp", "tcp_syn", "tls_client", "quic_client"):
        with pytest.raises(DeviceFingerprintValidationError):
            registry.validate(source_kind, 1, {})
    with pytest.raises(DeviceFingerprintUnsupportedSchema):
        registry.validate("portal_ua", 1, {})


def test_test_schema_normalizes_before_freeze():
    registry = EvidenceSchemaRegistry()
    registry.register("dhcp", 1, lambda value: {"vendor_class": value["vendor_class"].lower()} if set(value) == {"vendor_class"} else (_ for _ in ()).throw(DeviceFingerprintValidationError()))
    with pytest.raises(DeviceFingerprintValidationError):
        registry.register("dhcp", 1, lambda value: value)
    registry.freeze()
    assert registry.validate("dhcp", 1, {"vendor_class": "ANDROID"}) == {"vendor_class": "android"}
    with pytest.raises(DeviceFingerprintValidationError):
        registry.register("tcp_syn", 1, lambda value: value)
    with pytest.raises(DeviceFingerprintValidationError):
        registry.validate("dhcp", 1, {"vendor_class": "android", "unexpected": True})
    with pytest.raises(DeviceFingerprintUnsupportedSchema):
        registry.validate("tcp_syn", 1, {})


def test_validator_output_must_be_safe_json_mapping():
    for result in (b"bytes", {"raw_packet": "x"}, {"number": float("nan")}, {1: "bad"}):
        registry = EvidenceSchemaRegistry()
        registry.register("dhcp", 1, lambda _value, result=result: result)
        registry.freeze()
        with pytest.raises(DeviceFingerprintValidationError):
            registry.validate("dhcp", 1, {})
