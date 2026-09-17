import pytest

from app.device_fingerprint.models import DeviceFingerprintUnsupportedSchema, DeviceFingerprintValidationError
from app.device_fingerprint.schema_registry import EvidenceSchemaRegistry, build_production_schema_registry
from .test_network_schemas import quic, tcp_v2, tls
from .test_portal_schema import payload as portal_v1, payload_v2 as portal_v2


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


def test_production_registry_has_exactly_seven_executable_contracts():
    registry = build_production_schema_registry()
    fixtures = {
        ("dhcp", 1): {
            "message_type": "discover", "parameter_request_list": [1, 3, 6],
            "option_order": [53, 55], "vendor_class": "android-dhcp-13",
            "client_identifier_kind": "mac", "maximum_message_size": 1500,
            "rapid_commit_requested": False, "capport_requested": True,
            "ipv6_only_preferred_requested": False, "hostname_present": True,
        },
        ("tcp_syn", 1): {
            "ip_version": 4, "observed_ttl": 64, "tcp_window": 65535,
            "mss": 1460, "window_scale": 8, "sack_permitted": True,
            "timestamps_present": True, "tcp_option_order": [2, 4, 8, 1, 3],
        },
        ("tcp_syn", 2): tcp_v2(),
        ("tls_client", 1): tls(),
        ("quic_client", 1): quic(),
        ("portal_headers", 1): portal_v1(),
        ("portal_headers", 2): portal_v2(),
    }
    assert set(registry._validators) == set(fixtures)
    for (source_kind, version), value in fixtures.items():
        assert registry.validate(source_kind, version, value) == value
    for source_kind, version in (("portal_headers", 3), ("tcp_syn", 3), ("future_source", 1)):
        with pytest.raises(DeviceFingerprintUnsupportedSchema):
            registry.validate(source_kind, version, {})
