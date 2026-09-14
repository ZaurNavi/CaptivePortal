import pytest

from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.network_schemas import (
    validate_dhcp_v1, validate_quic_v1, validate_tcp_syn_v1, validate_tls_v1,
)
from app.device_fingerprint.schema_registry import build_production_schema_registry


def tls(**changes):
    value = {
        "ja4": "t13d0203h2_0123456789ab_abcdef012345",
        "ja4_a": "t13d0203h2", "ja4_b": "0123456789ab", "ja4_c": "abcdef012345",
        "tls_version_family": "tls1_3", "client_alpns": ["h2", "http/1.1"],
        "ech_extension_present": False, "grease_extension_present": True,
    }
    value.update(changes)
    return value


def quic(**changes):
    value = {
        "ja4": "q13d0203h3_0123456789ab_abcdef012345",
        "ja4_a": "q13d0203h3", "ja4_b": "0123456789ab", "ja4_c": "abcdef012345",
        "quic_version": "0x00000001", "ech_extension_present": None,
        "grease_extension_present": None,
    }
    value.update(changes)
    return value


def test_production_registry_contains_exact_task02_schemas():
    registry = build_production_schema_registry()
    assert registry.frozen
    assert registry.validate("tls_client", 1, tls())["ja4_a"].startswith("t")
    assert registry.validate("quic_client", 1, quic())["ja4_a"].startswith("q")


@pytest.mark.parametrize("alpns", [None, ["h2", "http/1.1"], ["h2", "h2"]])
def test_tls_alpns_valid_and_ordered(alpns):
    assert validate_tls_v1(tls(client_alpns=alpns))["client_alpns"] == alpns


@pytest.mark.parametrize("alpns", [["x"] * 17, ["x" * 256], [1], ["bad value"], ["\x7f"]])
def test_tls_alpns_malformed_fails(alpns):
    with pytest.raises(DeviceFingerprintValidationError):
        validate_tls_v1(tls(client_alpns=alpns))


def test_empty_alpn_is_normalizer_only_and_validator_rejects_it():
    with pytest.raises(DeviceFingerprintValidationError):
        validate_tls_v1(tls(client_alpns=[]))


@pytest.mark.parametrize("change", [
    {"ja4_a": "t12d0203h2"}, {"ja4_b": "1123456789ab"},
    {"ja4_c": "bbcdef012345"}, {"ja4_b": "ABCDEF012345"},
    {"ja4": "t13d0203h2*0123456789ab*abcdef012345"},
])
def test_ja4_redundant_fields_must_match(change):
    with pytest.raises(DeviceFingerprintValidationError):
        validate_tls_v1(tls(**change))


def test_family_is_strict():
    with pytest.raises(DeviceFingerprintValidationError):
        validate_quic_v1(quic(ja4="t13d0203h3_0123456789ab_abcdef012345", ja4_a="t13d0203h3"))


def test_quic_version_is_canonical():
    assert validate_quic_v1(quic())["quic_version"] == "0x00000001"
    for value in ("1", "0x1", "0xABCDEF01", 1):
        with pytest.raises(DeviceFingerprintValidationError):
            validate_quic_v1(quic(quic_version=value))


def test_dhcp_exact_payload_contract():
    payload = {
        "message_type": "discover", "parameter_request_list": [1, 3, 6],
        "option_order": [53, 55], "vendor_class": "android-dhcp-13",
        "client_identifier_kind": "mac", "maximum_message_size": 1500,
        "rapid_commit_requested": False, "capport_requested": True,
        "ipv6_only_preferred_requested": False, "hostname_present": True,
    }
    assert validate_dhcp_v1(payload) == payload
    with pytest.raises(DeviceFingerprintValidationError):
        validate_dhcp_v1({**payload, "hostname": "secret"})


def test_tcp_exact_payload_contract():
    payload = {
        "ip_version": 4, "observed_ttl": 64, "tcp_window": 65535,
        "mss": 1460, "window_scale": 8, "sack_permitted": True,
        "timestamps_present": True, "tcp_option_order": [2, 4, 8, 1, 3],
    }
    assert validate_tcp_syn_v1(payload) == payload
    with pytest.raises(DeviceFingerprintValidationError):
        validate_tcp_syn_v1({**payload, "window_scale": 15})
