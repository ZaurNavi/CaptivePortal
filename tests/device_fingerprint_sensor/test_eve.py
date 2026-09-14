import json
import socket

from app.device_fingerprint_sensor.config import sensor_config_from_env
from app.device_fingerprint_sensor.eve import EveReceiver
from app.device_fingerprint_sensor.normalizer import NetworkNormalizer


def config():
    return sensor_config_from_env({"DEVICE_FINGERPRINT_SENSOR_ENABLED": "true"})


def event(kind, body):
    return {
        "event_type": kind, "timestamp": "2026-09-14T10:00:00.123456+00:00",
        "src_ip": "192.168.8.20", "dest_ip": "1.1.1.1",
        "ether": {"src_mac": "00:11:22:33:44:55", "dest_mac": "aa:bb:cc:dd:ee:ff"},
        kind: body,
    }


def test_tls_adapter_keeps_only_approved_fields_and_empty_alpn_becomes_null():
    normalizer = NetworkNormalizer(config(), monotonic=lambda: 0)
    values = normalizer.eve(event("tls", {
        "ja4": "t13d0203h2_0123456789ab_abcdef012345", "client_alpns": [],
        "client_handshake": {"exts": [0, 65037, 2570], "version": "TLS 1.3"},
        "sni": "private.example", "ja3": "forbidden", "certificate": "forbidden",
    }))
    assert len(values) == 1
    document = values[0].document
    assert document["payload"]["client_alpns"] is None
    assert document["payload"]["ech_extension_present"] is True
    assert document["payload"]["grease_extension_present"] is True
    assert "private.example" not in repr(document)


def test_tls_invalid_alpn_and_missing_l2_emit_no_evidence():
    normalizer = NetworkNormalizer(config(), monotonic=lambda: 0)
    bad = event("tls", {"ja4": "t13d0203h2_0123456789ab_abcdef012345", "client_alpns": ["bad value"]})
    assert normalizer.eve(bad) == []
    bad["tls"]["client_alpns"] = ["h2"]
    del bad["ether"]
    assert normalizer.eve(bad) == []


def test_quic_version_and_extensions_are_normalized_without_private_fields():
    normalizer = NetworkNormalizer(config(), monotonic=lambda: 0)
    values = normalizer.eve(event("quic", {
        "ja4": "q00d0203h3_0123456789ab_abcdef012345", "version": "faceb002",
        "extensions": [{"type": 65037, "values": ["secret"]}],
        "sni": "private", "ua": "private", "cyu": "private",
    }))
    payload = values[0].document["payload"]
    assert payload["quic_version"] == "0xfaceb002"
    assert payload["ech_extension_present"] is True
    assert "secret" not in repr(values[0].document)


class FakeSocket:
    def __init__(self, payload, flags=0): self.payload, self.flags = payload, flags
    def recvmsg(self, *_args): return self.payload, [], self.flags, None


def test_receiver_rejects_truncated_and_invalid_datagrams():
    receiver = EveReceiver("unused", max_datagram_bytes=20)
    receiver.socket = FakeSocket(b"x" * 21)
    assert receiver.receive() is None and receiver.truncated == 1
    receiver.socket = FakeSocket(b"not-json")
    assert receiver.receive() is None and receiver.invalid == 1
    receiver.max_datagram_bytes = 100
    receiver.socket = FakeSocket(json.dumps({"event_type": "stats"}).encode())
    assert receiver.receive()["event_type"] == "stats"


def test_receiver_timeout_is_neutral_and_not_invalid_json():
    class TimedOutSocket:
        def recvmsg(self, *_args): raise socket.timeout

    receiver = EveReceiver("unused")
    receiver.socket = TimedOutSocket()
    assert receiver.receive() is None
    assert receiver.invalid == 0
