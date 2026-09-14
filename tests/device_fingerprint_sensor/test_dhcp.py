import ipaddress
import struct

import pytest

from app.device_fingerprint_sensor.dhcp import parse_dhcp_frame
from app.device_fingerprint_sensor.config import sensor_config_from_env
from app.device_fingerprint_sensor.normalizer import NetworkNormalizer


MAC = bytes.fromhex("001122334455")


def frame(*, message=1, source="0.0.0.0", ciaddr="0.0.0.0", yiaddr="0.0.0.0", options=b""):
    bootp = bytearray(236)
    bootp[0:3] = bytes((1 if message in {1, 3, 4, 7, 8} else 2, 1, 6))
    struct.pack_into("!I", bootp, 4, 123)
    bootp[12:16] = ipaddress.ip_address(ciaddr).packed
    bootp[16:20] = ipaddress.ip_address(yiaddr).packed
    bootp[28:34] = MAC
    payload = bytes(bootp) + b"\x63\x82\x53\x63" + bytes((53, 1, message)) + options + b"\xff"
    udp = struct.pack("!HHHH", 68 if message in {1,3,4,7,8} else 67, 67 if message in {1,3,4,7,8} else 68, 8 + len(payload), 0) + payload
    ip = bytearray(20)
    ip[0] = 0x45; ip[8] = 64; ip[9] = 17
    struct.pack_into("!H", ip, 2, 20 + len(udp))
    ip[12:16] = ipaddress.ip_address(source).packed
    ethernet = b"\xff" * 6 + MAC + b"\x08\x00"
    return ethernet + bytes(ip) + udp


def option(code, value):
    return bytes((code, len(value))) + value


def test_client_payload_extracts_only_approved_features():
    raw = frame(options=(
        option(55, b"\x01\x03\x06") + option(60, b"android") +
        option(61, b"\x01" + MAC) + option(57, b"\x05\xdc") +
        option(80, b"") + option(114, b"") + option(108, b"\x00\x00\x00\x01") +
        option(12, b"private-host")
    ))
    parsed = parse_dhcp_frame(raw)
    assert parsed is not None
    assert parsed.payload == {
        "message_type": "discover", "parameter_request_list": [1, 3, 6],
        "option_order": [53, 55, 60, 61, 57, 80, 114, 108, 12],
        "vendor_class": "android", "client_identifier_kind": "mac",
        "maximum_message_size": 1500, "rapid_commit_requested": True,
        "capport_requested": True, "ipv6_only_preferred_requested": True,
        "hostname_present": True,
    }
    assert "private-host" not in repr(parsed.payload)


def test_server_authority_fields_are_correlation_only():
    raw = frame(message=5, source="192.168.10.1", yiaddr="192.168.8.20", options=option(54, ipaddress.ip_address("192.168.10.1").packed) + option(51, (3600).to_bytes(4, "big")))
    parsed = parse_dhcp_frame(raw)
    assert parsed.message_type == "ack"
    assert parsed.option54 == "192.168.10.1"
    assert parsed.payload is None


def test_truncated_or_malformed_options_emit_nothing():
    assert parse_dhcp_frame(b"short") is None
    assert parse_dhcp_frame(frame(options=b"\x37\x08\x01")) is None


@pytest.mark.parametrize("options", [
    option(60, b"a" * 129),
    option(57, b"\x05"),
    option(57, (575).to_bytes(2, "big")),
    option(50, b"\xc0\xa8\x08"),
    option(51, b"\x00\x00\x01"),
    option(54, b"\xc0\xa8\x0a"),
    option(80, b"\x01"),
    option(108, b"\x00\x00\x01"),
])
def test_known_dhcp_option_invalid_shapes_fail_before_normalization(options):
    assert parse_dhcp_frame(frame(options=options)) is None


def test_zero_address_client_is_released_only_by_exact_guest_authority():
    normalizer = NetworkNormalizer(sensor_config_from_env({"DEVICE_FINGERPRINT_SENSOR_ENABLED": "true"}), monotonic=lambda: 0)
    observed = "2026-09-14T00:00:00.000Z"
    assert normalizer.raw(frame(), observed) == []
    wrong = frame(message=2, source="192.168.0.1", yiaddr="192.168.8.20", options=option(54, ipaddress.ip_address("192.168.0.1").packed))
    assert normalizer.raw(wrong, observed) == []
    valid = frame(message=2, source="192.168.10.1", yiaddr="192.168.8.20", options=option(54, ipaddress.ip_address("192.168.10.1").packed))
    released = normalizer.raw(valid, observed)
    assert len(released) == 1
    assert released[0].document["observed_ip"] is None
    assert released[0].document["source_kind"] == "dhcp"


def test_vlan10_dhcp_client_is_not_inferred_as_guest():
    normalizer = NetworkNormalizer(sensor_config_from_env({"DEVICE_FINGERPRINT_SENSOR_ENABLED": "true"}), monotonic=lambda: 0)
    assert normalizer.raw(frame(source="192.168.0.20", ciaddr="192.168.0.20"), "2026-09-14T00:00:00.000Z") == []


def test_decline_requires_confirmed_binding_even_with_guest_source_or_requested_ip():
    normalizer = NetworkNormalizer(sensor_config_from_env({"DEVICE_FINGERPRINT_SENSOR_ENABLED": "true"}), monotonic=lambda: 0)
    observed = "2026-09-14T00:00:00.000Z"
    requested = option(50, ipaddress.ip_address("192.168.8.20").packed)
    assert normalizer.raw(frame(message=4, source="192.168.8.20", options=requested), observed) == []
    assert normalizer.raw(frame(message=4, options=requested), observed) == []

    ack = frame(
        message=5,
        source="192.168.10.1",
        yiaddr="192.168.8.20",
        options=option(54, ipaddress.ip_address("192.168.10.1").packed) + option(51, (3600).to_bytes(4, "big")),
    )
    assert normalizer.raw(ack, observed) == []
    allowed = normalizer.raw(frame(message=4, options=requested), observed)
    assert len(allowed) == 1
    assert allowed[0].document["source_subtype"] == "decline"


def test_release_accepts_actual_guest_address_but_cache_fallback_must_match():
    normalizer = NetworkNormalizer(sensor_config_from_env({"DEVICE_FINGERPRINT_SENSOR_ENABLED": "true"}), monotonic=lambda: 0)
    observed = "2026-09-14T00:00:00.000Z"
    direct = normalizer.raw(frame(message=7, source="192.168.8.20", ciaddr="192.168.8.20"), observed)
    assert len(direct) == 1
    requested = option(50, ipaddress.ip_address("192.168.8.20").packed)
    assert normalizer.raw(frame(message=7, options=requested), observed) == []
