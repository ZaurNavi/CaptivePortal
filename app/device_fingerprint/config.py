"""Strict independent configuration for fingerprint evidence v1."""

from __future__ import annotations

import ipaddress
import json
import re
from pathlib import Path
from typing import Any, Mapping

from .models import (
    DeviceFingerprintConfig,
    DeviceFingerprintConfigError,
    DeviceFingerprintProducer,
    DeviceFingerprintValidationError,
)
from .validation import validate_machine_id, validate_site_id, validate_source_kind


BUSY_TIMEOUT_MS = 500
WAL_AUTOCHECKPOINT_PAGES = 1000
JOURNAL_SIZE_LIMIT_BYTES = 67_108_864
MAX_HTTP_RESPONSE_BYTES = 65_536
RETENTION_SCAN_INTERVAL_SECONDS = 300
RETENTION_DELETE_CHUNK_ROWS = 500
MAX_RETENTION_CHUNKS_PER_PASS = 20
SOURCE_HEALTH_RETENTION_DAYS = 30
SOURCE_HEALTH_RETENTION_MARGIN_SECONDS = 600
SHUTDOWN_TIMEOUT_SECONDS = 20.0

DEFAULT_DB_PATH = "/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3"
DEFAULT_WRITER_LOCK_PATH = "/opt/CaptivePortal/data/device_fingerprint_evidence.writer.lock"
DEFAULT_BIND_ADDRESS = "192.168.0.202"
DEFAULT_PORT = 9443
DEFAULT_TLS_CERT_PATH = "/etc/captive-portal/device-fingerprint/server.crt"
DEFAULT_TLS_KEY_PATH = "/etc/captive-portal/device-fingerprint/server.key"
DEFAULT_ALLOWED_NETWORKS = "192.168.0.0/24"
DEFAULT_RETENTION_DAYS = 30
DEFAULT_MAX_FUTURE_SKEW_SECONDS = 120
DEFAULT_MAX_DELAYED_EVENT_AGE_SECONDS = 86_400
DEFAULT_MAX_DB_BYTES = 1_073_741_824
DEFAULT_MAX_HTTP_REQUEST_BYTES = 1_048_576
DEFAULT_MAX_EVENTS_PER_BATCH = 100
DEFAULT_MAX_PAYLOAD_BYTES = 8_192
DEFAULT_MAX_CONCURRENT_INGEST_REQUESTS = 2

_PRODUCER_KEYS = frozenset({
    "producer_id", "bearer_token", "capture_source_id", "site_id",
    "allowed_guest_cidrs", "allowed_source_kinds",
})


def device_fingerprint_max_db_bytes_from_settings(settings: Mapping[str, Any]) -> int:
    return _integer(
        settings.get("device_fingerprint_max_db_bytes", DEFAULT_MAX_DB_BYTES),
        "DEVICE_FINGERPRINT_MAX_DB_BYTES", 67_108_864, 8_589_934_592,
    )


def device_fingerprint_config_from_settings(settings: Mapping[str, Any]) -> DeviceFingerprintConfig:
    enabled = _bool(settings.get("device_fingerprint_evidence_enabled", "false"), "DEVICE_FINGERPRINT_EVIDENCE_ENABLED")
    if not enabled:
        return DeviceFingerprintConfig(
            enabled=False,
            db_path=_string_or_default(settings.get("device_fingerprint_db_path"), DEFAULT_DB_PATH),
            writer_lock_path=_string_or_default(settings.get("device_fingerprint_writer_lock_path"), DEFAULT_WRITER_LOCK_PATH),
            bind_address=_string_or_default(settings.get("device_fingerprint_bind_address"), DEFAULT_BIND_ADDRESS),
            port=DEFAULT_PORT,
            tls_cert_path=_string_or_default(settings.get("device_fingerprint_tls_cert_path"), DEFAULT_TLS_CERT_PATH),
            tls_key_path=_string_or_default(settings.get("device_fingerprint_tls_key_path"), DEFAULT_TLS_KEY_PATH),
            allowed_networks=(), producers=(), retention_days=DEFAULT_RETENTION_DAYS,
            max_future_skew_seconds=DEFAULT_MAX_FUTURE_SKEW_SECONDS,
            max_delayed_event_age_seconds=DEFAULT_MAX_DELAYED_EVENT_AGE_SECONDS,
            max_db_bytes=DEFAULT_MAX_DB_BYTES,
            max_http_request_bytes=DEFAULT_MAX_HTTP_REQUEST_BYTES,
            max_events_per_batch=DEFAULT_MAX_EVENTS_PER_BATCH,
            max_payload_bytes=DEFAULT_MAX_PAYLOAD_BYTES,
            max_concurrent_ingest_requests=DEFAULT_MAX_CONCURRENT_INGEST_REQUESTS,
        )
    db_path = _absolute(settings.get("device_fingerprint_db_path", DEFAULT_DB_PATH), "DEVICE_FINGERPRINT_DB_PATH")
    lock_path = _absolute(settings.get("device_fingerprint_writer_lock_path", DEFAULT_WRITER_LOCK_PATH), "DEVICE_FINGERPRINT_WRITER_LOCK_PATH")
    cert_path = _absolute(settings.get("device_fingerprint_tls_cert_path", DEFAULT_TLS_CERT_PATH), "DEVICE_FINGERPRINT_TLS_CERT_PATH")
    key_path = _absolute(settings.get("device_fingerprint_tls_key_path", DEFAULT_TLS_KEY_PATH), "DEVICE_FINGERPRINT_TLS_KEY_PATH")
    if Path(db_path).resolve(strict=False) == Path(lock_path).resolve(strict=False):
        raise DeviceFingerprintConfigError("Fingerprint DB and writer lock paths must be distinct")
    if Path(cert_path).resolve(strict=False) == Path(key_path).resolve(strict=False):
        raise DeviceFingerprintConfigError("Fingerprint TLS certificate and key paths must be distinct")
    bind = settings.get("device_fingerprint_bind_address", DEFAULT_BIND_ADDRESS)
    if not isinstance(bind, str) or not bind.strip():
        raise DeviceFingerprintConfigError("DEVICE_FINGERPRINT_BIND_ADDRESS is invalid")
    try:
        ipaddress.ip_address(bind)
    except ValueError as exc:
        raise DeviceFingerprintConfigError("DEVICE_FINGERPRINT_BIND_ADDRESS is invalid") from exc
    allowed = _networks(settings.get("device_fingerprint_api_allowed_networks", DEFAULT_ALLOWED_NETWORKS), "DEVICE_FINGERPRINT_API_ALLOWED_NETWORKS")
    producers = _producers(settings.get("device_fingerprint_producers_json", ""))
    return DeviceFingerprintConfig(
        enabled=True, db_path=db_path, writer_lock_path=lock_path,
        bind_address=bind, port=_integer(settings.get("device_fingerprint_port", DEFAULT_PORT), "DEVICE_FINGERPRINT_PORT", 1, 65535),
        tls_cert_path=cert_path, tls_key_path=key_path,
        allowed_networks=allowed, producers=producers,
        retention_days=_integer(settings.get("device_fingerprint_retention_days", DEFAULT_RETENTION_DAYS), "DEVICE_FINGERPRINT_RETENTION_DAYS", 1, 90),
        max_future_skew_seconds=_integer(settings.get("device_fingerprint_max_future_skew_seconds", DEFAULT_MAX_FUTURE_SKEW_SECONDS), "DEVICE_FINGERPRINT_MAX_FUTURE_SKEW_SECONDS", 0, 600),
        max_delayed_event_age_seconds=_integer(settings.get("device_fingerprint_max_delayed_event_age_seconds", DEFAULT_MAX_DELAYED_EVENT_AGE_SECONDS), "DEVICE_FINGERPRINT_MAX_DELAYED_EVENT_AGE_SECONDS", 60, 604800),
        max_db_bytes=device_fingerprint_max_db_bytes_from_settings(settings),
        max_http_request_bytes=_integer(settings.get("device_fingerprint_max_http_request_bytes", DEFAULT_MAX_HTTP_REQUEST_BYTES), "DEVICE_FINGERPRINT_MAX_HTTP_REQUEST_BYTES", 65_536, 4_194_304),
        max_events_per_batch=_integer(settings.get("device_fingerprint_max_events_per_batch", DEFAULT_MAX_EVENTS_PER_BATCH), "DEVICE_FINGERPRINT_MAX_EVENTS_PER_BATCH", 1, 500),
        max_payload_bytes=_integer(settings.get("device_fingerprint_max_payload_bytes", DEFAULT_MAX_PAYLOAD_BYTES), "DEVICE_FINGERPRINT_MAX_PAYLOAD_BYTES", 256, 65_536),
        max_concurrent_ingest_requests=_integer(settings.get("device_fingerprint_max_concurrent_ingest_requests", DEFAULT_MAX_CONCURRENT_INGEST_REQUESTS), "DEVICE_FINGERPRINT_MAX_CONCURRENT_INGEST_REQUESTS", 1, 8),
    )


def _string_or_default(value: Any, default: str) -> str:
    return value if isinstance(value, str) else default


def _bool(value: Any, name: str) -> bool:
    if type(value) is bool:
        return value
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    raise DeviceFingerprintConfigError(f"{name} must be true or false")


def _integer(value: Any, name: str, minimum: int, maximum: int) -> int:
    if type(value) not in {int, str}:
        raise DeviceFingerprintConfigError(f"{name} is invalid")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise DeviceFingerprintConfigError(f"{name} is invalid") from exc
    if parsed < minimum or parsed > maximum:
        raise DeviceFingerprintConfigError(f"{name} is outside the allowed range")
    return parsed


def _absolute(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or not Path(value.strip()).is_absolute():
        raise DeviceFingerprintConfigError(f"{name} must be an absolute path")
    return str(Path(value.strip()))


def _networks(value: Any, name: str) -> tuple[Any, ...]:
    if isinstance(value, str):
        values = value.split(",")
    elif isinstance(value, list):
        values = value
    else:
        raise DeviceFingerprintConfigError(f"{name} is invalid")
    if not 1 <= len(values) <= 32:
        raise DeviceFingerprintConfigError(f"{name} is invalid")
    if any(not isinstance(item, str) or not item for item in values):
        raise DeviceFingerprintConfigError(f"{name} is invalid")
    try:
        networks = tuple(ipaddress.ip_network(item, strict=True) for item in values)
    except ValueError as exc:
        raise DeviceFingerprintConfigError(f"{name} is invalid") from exc
    if len(set(networks)) != len(networks):
        raise DeviceFingerprintConfigError(f"{name} contains duplicates")
    return networks


def _producers(value: Any) -> tuple[DeviceFingerprintProducer, ...]:
    try:
        raw = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError) as exc:
        raise DeviceFingerprintConfigError("DEVICE_FINGERPRINT_PRODUCERS_JSON is invalid") from exc
    if not isinstance(raw, list) or not 1 <= len(raw) <= 32:
        raise DeviceFingerprintConfigError("DEVICE_FINGERPRINT_PRODUCERS_JSON is invalid")
    result = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != _PRODUCER_KEYS:
            raise DeviceFingerprintConfigError("DEVICE_FINGERPRINT_PRODUCERS_JSON has invalid keys")
        try:
            producer_id = validate_machine_id(item["producer_id"])
            capture_id = validate_machine_id(item["capture_source_id"])
            site_id = validate_site_id(item["site_id"])
            token = item["bearer_token"]
            if not isinstance(token, str) or re.fullmatch(r"[A-Za-z0-9_-]{32,256}", token) is None:
                raise ValueError
            networks = _networks(item["allowed_guest_cidrs"], "allowed_guest_cidrs")
            kinds_raw = item["allowed_source_kinds"]
            if not isinstance(kinds_raw, list) or not 1 <= len(kinds_raw) <= 32:
                raise ValueError
            kinds = tuple(validate_source_kind(kind) for kind in kinds_raw)
            if len(set(kinds)) != len(kinds):
                raise ValueError
        except (TypeError, ValueError, DeviceFingerprintValidationError) as exc:
            raise DeviceFingerprintConfigError("DEVICE_FINGERPRINT_PRODUCERS_JSON is invalid") from exc
        result.append(DeviceFingerprintProducer(producer_id, token, capture_id, site_id, networks, kinds))
    for values, label in (([p.producer_id for p in result], "producer"), ([p.capture_source_id for p in result], "capture source"), ([p.bearer_token for p in result], "token")):
        if len(set(values)) != len(values):
            raise DeviceFingerprintConfigError(f"Duplicate fingerprint {label}")
    return tuple(result)
