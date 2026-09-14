import ipaddress
import struct

from app.device_fingerprint_sensor.tcp_syn import parse_tcp_syn_frame


def syn(*, source="192.168.8.20", flags=0x02, options=b"\x02\x04\x05\xb4\x04\x02\x08\x0a" + b"\0" * 8):
    while len(options) % 4:
        options += b"\x01"
    tcp = bytearray(20 + len(options))
    struct.pack_into("!HH", tcp, 0, 12345, 443)
    tcp[12] = ((20 + len(options)) // 4) << 4
    tcp[13] = flags
    struct.pack_into("!H", tcp, 14, 65535)
    tcp[20:] = options
    ip = bytearray(20)
    ip[0] = 0x45; ip[8] = 64; ip[9] = 6
    struct.pack_into("!H", ip, 2, 20 + len(tcp))
    ip[12:16] = ipaddress.ip_address(source).packed
    ip[16:20] = ipaddress.ip_address("1.1.1.1").packed
    return bytes.fromhex("aabbccddeeff0011223344550800") + bytes(ip) + bytes(tcp)


def test_ipv4_guest_syn_is_normalized_without_destination_or_ports():
    parsed = parse_tcp_syn_frame(syn(), (ipaddress.ip_network("192.168.8.0/22"),))
    assert parsed is not None
    mac, ip, payload = parsed
    assert mac == "00:11:22:33:44:55"
    assert ip == "192.168.8.20"
    assert payload["mss"] == 1460
    assert payload["sack_permitted"] is True
    assert payload["timestamps_present"] is True
    assert "destination" not in payload and "port" not in payload


def test_ack_or_non_guest_or_truncated_is_rejected():
    guest = (ipaddress.ip_network("192.168.8.0/22"),)
    assert parse_tcp_syn_frame(syn(flags=0x12), guest) is None
    assert parse_tcp_syn_frame(syn(source="192.168.0.20"), guest) is None
    assert parse_tcp_syn_frame(syn()[:30], guest) is None


def test_malformed_known_tcp_options_fail_closed():
    guest = (ipaddress.ip_network("192.168.8.0/22"),)
    malformed = (
        b"\x02\x03\x01",
        b"\x03\x02",
        b"\x03\x03\x0f",
        b"\x04\x03\x00",
        b"\x08\x09" + b"\x00" * 7,
    )
    for options in malformed:
        assert parse_tcp_syn_frame(syn(options=options), guest) is None
