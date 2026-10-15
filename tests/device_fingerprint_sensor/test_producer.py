from datetime import datetime, timezone

import requests
import pytest

from app.device_fingerprint_sensor.config import sensor_config_from_env
from app.device_fingerprint_sensor.models import NormalizedEvent
from app.device_fingerprint_sensor.producer import EvidenceProducer
from app.device_fingerprint_sensor.spool import SensorSpool


class Response:
    def __init__(self, status, headers=None): self.status_code, self.headers = status, headers or {}


class Session:
    def __init__(self, values): self.values, self.calls = list(values), []
    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        value = self.values.pop(0)
        if isinstance(value, Exception): raise value
        return value


def setup(tmp_path, monkeypatch, responses):
    credential = tmp_path / "device-fingerprint-bearer"; credential.write_text("a" * 32)
    config = sensor_config_from_env({"DEVICE_FINGERPRINT_SENSOR_ENABLED": "true", "CREDENTIALS_DIRECTORY": str(tmp_path), "DEVICE_FINGERPRINT_SENSOR_SPOOL_PATH": str(tmp_path / "spool.sqlite3"), "DEVICE_FINGERPRINT_SENSOR_CA_CERT_PATH": str(tmp_path / "ca.crt")})
    spool = SensorSpool(
        config.spool_path,
        total_budget_bytes=1_000_000,
        main_db_max_bytes=500_000,
        max_events=200,
        now=lambda: datetime(2026, 9, 14, tzinfo=timezone.utc),
    )
    spool.initialize()
    event = NormalizedEvent("evidence", "00000000-0000-4000-8000-000000000001", "dhcp", "2026-09-14T00:00:00.000Z", {"safe": True})
    spool.enqueue([event])
    session = Session(responses)
    return config, spool, session, EvidenceProducer(config, spool, session=session, random_value=lambda: 0.5)


def test_https_delivery_uses_ca_bearer_and_acknowledges(tmp_path, monkeypatch):
    config, spool, session, producer = setup(tmp_path, monkeypatch, [Response(200)])
    result = producer.deliver_once()
    assert result.status == "delivered" and spool.metrics()["rows"] == 0
    url, options = session.calls[0]
    assert url.startswith("https://") and options["verify"] == config.ca_cert_path
    assert options["headers"]["Authorization"] == "Bearer " + "a" * 32


def test_retry_keeps_stable_event_and_honors_retry_after(tmp_path, monkeypatch):
    _config, spool, _session, producer = setup(tmp_path, monkeypatch, [Response(429, {"Retry-After": "60"}), Response(200)])
    assert producer.deliver_once().delay_seconds == 60
    assert spool.metrics()["rows"] == 1
    assert producer.deliver_once().status == "delivered"


def test_transport_backoff_and_permanent_rejection(tmp_path, monkeypatch):
    _config, spool, _session, producer = setup(tmp_path, monkeypatch, [requests.ConnectionError(), Response(400)])
    assert producer.deliver_once().delay_seconds == 1
    assert producer.deliver_once().status == "permanent"
    assert producer.deliver_once().status == "permanent"
    assert spool.metrics()["rows"] == 1


def test_stale_rows_never_reach_producer_http(tmp_path, monkeypatch):
    _config, spool, session, producer = setup(tmp_path, monkeypatch, [Response(200)])
    rows = [
        (
            "evidence", f"stale-{index}", "dhcp", "2026-09-12T00:00:00.000Z",
            '{"stale":true}', "2026-09-12T00:00:00.000Z",
        )
        for index in range(101)
    ]
    with spool.connection:
        spool.connection.executemany(
            "INSERT INTO sensor_spool(endpoint,event_id,source_kind,observed_at,payload_json,created_at) VALUES(?,?,?,?,?,?)",
            rows,
        )
    assert producer.deliver_once().status == "delivered"
    sent = session.calls[0][1]["json"]["events"]
    assert sent == [{"safe": True}]
    assert spool.metrics()["rows"] == 0


@pytest.mark.parametrize("status", [200, 401, 403])
def test_T07_T08_T09_configured_identity_health_and_ca_no_fallback(tmp_path, status):
    from app.device_fingerprint_sensor.normalizer import NetworkNormalizer
    from app.device_fingerprint_sensor.health import SourceHealthTracker
    credential = tmp_path / "device-fingerprint-bearer"
    credential.write_text("b" * 32, encoding="ascii")
    config = sensor_config_from_env({"DEVICE_FINGERPRINT_SENSOR_ENABLED": "true", "CREDENTIALS_DIRECTORY": str(tmp_path),
        "DEVICE_FINGERPRINT_SENSOR_PRODUCER_ID": "lab-sensor-02", "DEVICE_FINGERPRINT_SENSOR_CAPTURE_SOURCE_ID": "lab-span-02",
        "DEVICE_FINGERPRINT_SENSOR_SITE_ID": "a" * 24, "DEVICE_FINGERPRINT_SENSOR_GUEST_CIDRS": "10.20.0.0/24",
        "DEVICE_FINGERPRINT_SENSOR_EVIDENCE_BASE_URL": "https://evidence.example:9443/api/internal/device-fingerprint/v1",
        "DEVICE_FINGERPRINT_SENSOR_SPOOL_PATH": str(tmp_path / "fresh-spool.sqlite3"),
        "DEVICE_FINGERPRINT_SENSOR_CA_CERT_PATH": str(tmp_path / "new-ca.crt")})
    now = datetime(2026, 10, 15, tzinfo=timezone.utc)
    spool = SensorSpool(config.spool_path, total_budget_bytes=1_000_000, main_db_max_bytes=500_000,
        max_events=200, now=lambda: now)
    spool.initialize()
    try:
        normalized = NetworkNormalizer(config, monotonic=lambda: 0.0).eve({
            "event_type": "tls", "timestamp": "2026-10-15T00:00:00.000000Z", "src_ip": "10.20.0.7",
            "ether": {"src_mac": "AA:BB:CC:DD:EE:FF"},
            "tls": {"ja4": "t13d0203h2_0123456789ab_abcdef012345", "client_alpns": []},
        })
        health = SourceHealthTracker(config, monotonic=lambda: 0.0, now=lambda: now).all("available", None)
        assert len(normalized) == 1 and len(health) == 4
        for event in normalized + health:
            assert event.document["site_id"] == config.site_id
            assert event.document["capture_source_id"] == config.capture_source_id
        spool.enqueue(normalized + health)
        transport = Session([Response(status), Response(status)])
        producer = EvidenceProducer(config, spool, session=transport)
        first = producer.deliver_once()
        if status == 200:
            assert producer.deliver_once().status == "delivered"
            assert spool.metrics()["rows"] == 0
        else:
            assert first.status == "permanent"
            assert producer.deliver_once().status == "permanent" and len(transport.calls) == 1
            assert spool.metrics()["rows"] == 5
        for url, options in transport.calls:
            assert url.startswith(config.evidence_base_url + "/")
            assert options["verify"] == config.ca_cert_path
            assert options["headers"]["Authorization"] == "Bearer " + "b" * 32
            assert options["json"]["producer_id"] == "lab-sensor-02"
            assert all(event["site_id"] == "a" * 24 and event["capture_source_id"] == "lab-span-02" for event in options["json"]["events"])
    finally:
        spool.close()


def test_T08_missing_sensor_loadcredential_never_posts(tmp_path, monkeypatch):
    from dataclasses import replace
    from app.device_fingerprint_sensor.models import SensorError
    config, spool, transport, _producer = setup(tmp_path, monkeypatch, [Response(200)])
    producer = EvidenceProducer(replace(config, credential_path=str(tmp_path / "missing-bearer")), spool, session=transport)
    try:
        with pytest.raises(SensorError):
            producer.deliver_once()
        assert transport.calls == [] and spool.metrics()["rows"] == 1
    finally:
        spool.close()


def test_T09_parser_never_relabels_or_opens_existing_spool(tmp_path, monkeypatch):
    import sqlite3
    old = sensor_config_from_env({})
    path = tmp_path / "old-spool.sqlite3"
    now = datetime(2026, 10, 15, tzinfo=timezone.utc)
    spool = SensorSpool(str(path), total_budget_bytes=1_000_000, main_db_max_bytes=500_000, max_events=200, now=lambda: now)
    spool.initialize()
    old_payload = {"site_id": old.site_id, "capture_source_id": old.capture_source_id}
    spool.enqueue([NormalizedEvent("evidence", "old-event", "dhcp", "2026-10-15T00:00:00.000Z", old_payload)])
    spool.close()
    before = path.read_bytes()
    with monkeypatch.context() as patch:
        patch.setattr(sqlite3, "connect", lambda *_a, **_k: pytest.fail("parser must not open old spool"))
        config = sensor_config_from_env({"DEVICE_FINGERPRINT_SENSOR_ENABLED": "true",
            "DEVICE_FINGERPRINT_SENSOR_PRODUCER_ID": "lab-new-producer", "DEVICE_FINGERPRINT_SENSOR_SITE_ID": "a" * 24,
            "DEVICE_FINGERPRINT_SENSOR_CAPTURE_SOURCE_ID": "lab-new-source", "DEVICE_FINGERPRINT_SENSOR_GUEST_CIDRS": "10.20.0.0/24",
            "DEVICE_FINGERPRINT_SENSOR_SPOOL_PATH": str(path)})
    assert config.site_id != old.site_id and path.read_bytes() == before
    spool.initialize()
    try:
        assert spool.batch(100)[1][0][1] == old_payload
    finally:
        spool.close()
    # Activating the changed identity against this nonempty spool is operational HOLD.


def test_T08_sensor_tls_failure_never_acknowledges(tmp_path, monkeypatch):
    config, spool, transport, producer = setup(tmp_path, monkeypatch,
        [requests.exceptions.SSLError("synthetic peer trust failure")])
    try:
        assert producer.deliver_once().status == "retry"
        assert transport.calls[0][1]["verify"] == config.ca_cert_path
        assert spool.metrics()["rows"] == 1
    finally:
        spool.close()
