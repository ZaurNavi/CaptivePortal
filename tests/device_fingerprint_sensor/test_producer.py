from datetime import datetime, timezone

import requests

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
