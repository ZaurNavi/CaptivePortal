"""Focused fixtures for the isolated fingerprint evidence service."""

from __future__ import annotations

import ipaddress
import logging
from datetime import datetime, timezone
from types import SimpleNamespace

from app.device_fingerprint.models import DeviceFingerprintConfig, DeviceFingerprintProducer

UTC = timezone.utc
NOW = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)
SITE = "6a64f17630da7c70d232187a"
TOKEN = "A" * 32


def producer() -> DeviceFingerprintProducer:
    return DeviceFingerprintProducer("sensor-zefer-01", TOKEN, "zefer-span-01", SITE, (ipaddress.ip_network("192.168.8.0/22"),), ("dhcp", "tcp_syn"))


def config(tmp_path, **overrides):
    values = dict(
        enabled=True, db_path=str(tmp_path / "fingerprint.sqlite3"),
        writer_lock_path=str(tmp_path / "fingerprint.lock"), bind_address="127.0.0.1",
        port=9443, tls_cert_path=str(tmp_path / "server.crt"),
        tls_key_path=str(tmp_path / "server.key"),
        allowed_networks=(ipaddress.ip_network("127.0.0.0/8"),), producers=(producer(),),
        retention_days=30, max_future_skew_seconds=120,
        max_delayed_event_age_seconds=86400, max_db_bytes=67_108_864,
        max_http_request_bytes=65_536, max_events_per_batch=100,
        max_payload_bytes=8192, max_concurrent_ingest_requests=2,
    )
    values.update(overrides)
    return DeviceFingerprintConfig(**values)


def evidence_event(**overrides):
    value = {
        "source_event_id": "11111111-1111-4111-8111-111111111111",
        "source_kind": "dhcp", "source_subtype": None,
        "extractor_name": "dhcp-v1", "extractor_version": "1.0.0",
        "feature_schema_version": 1, "rule_version": None, "site_id": SITE,
        "capture_source_id": "zefer-span-01", "observed_at": "2026-09-14T12:00:00.000Z",
        "observed_mac": "aa-bb-cc-dd-ee-ff", "observed_ip": "192.168.8.10",
        "quality_state": "valid", "payload": {"vendor_class": "android"},
    }
    value.update(overrides)
    return value


def health_event(**overrides):
    value = {
        "source_health_event_id": "22222222-2222-4222-8222-222222222222",
        "site_id": SITE, "capture_source_id": "zefer-span-01", "source_kind": "dhcp",
        "status": "available", "reason_code": None,
        "observed_at": "2026-09-14T12:00:00.000Z",
    }
    value.update(overrides)
    return value


class Identity:
    def safe_fields(self):
        return {"artifact_sha": "a" * 40, "artifact_tree": "b" * 40,
                "service_name": "fingerprint-evidence.service",
                "process_started_at": "2026-09-14T11:59:00.000Z"}


def logger():
    return logging.getLogger("device-fingerprint-test")
