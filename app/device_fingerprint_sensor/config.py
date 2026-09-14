"""Strict sensor-only environment parsing; never imported by the core app."""

from __future__ import annotations

import ipaddress
import os
import re
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlsplit

from .models import SensorConfig, SensorConfigError

INTERFACE = "enp8s0"
PRODUCER_ID = "sensor-zefer-01"
CAPTURE_SOURCE_ID = "zefer-span-01"
SITE_ID = "6a64f17630da7c70d232187a"
GUEST_CIDRS = "192.168.8.0/22"
DHCP_SERVER_AUTHORITY = "192.168.10.1"
DHCP_OPTION54_AUTHORITY = "192.168.10.1"
EVIDENCE_BASE_URL = "https://192.168.0.202:9443/api/internal/device-fingerprint/v1"
CA_CERT_PATH = "/etc/captive-portal/device-fingerprint/sensor-ca.crt"
SPOOL_PATH = "/var/lib/captive-portal/fingerprint-sensor/spool.sqlite3"
EVE_SOCKET_PATH = "/run/captive-portal/fingerprint-sensor/suricata-eve.sock"

_MACHINE = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
_SITE = re.compile(r"[0-9a-f]{24}")


def sensor_config_from_env(env: Mapping[str, str] | None = None) -> SensorConfig:
    values = os.environ if env is None else env
    enabled = _boolean(values.get("DEVICE_FINGERPRINT_SENSOR_ENABLED", "false"), "ENABLED")
    if not enabled:
        return _build(False, {})
    return _build(True, values)


def _build(enabled: bool, env: Mapping[str, str]) -> SensorConfig:
    def value(name: str, default: str) -> str:
        raw = env.get("DEVICE_FINGERPRINT_SENSOR_" + name, default)
        if not isinstance(raw, str) or not raw.strip() or "\x00" in raw:
            raise SensorConfigError(f"DEVICE_FINGERPRINT_SENSOR_{name} is invalid")
        return raw.strip()

    interface = value("INTERFACE", INTERFACE)
    if interface != INTERFACE:
        raise SensorConfigError("DEVICE_FINGERPRINT_SENSOR_INTERFACE must be enp8s0")
    producer = value("PRODUCER_ID", PRODUCER_ID)
    capture = value("CAPTURE_SOURCE_ID", CAPTURE_SOURCE_ID)
    site = value("SITE_ID", SITE_ID)
    if _MACHINE.fullmatch(producer) is None or _MACHINE.fullmatch(capture) is None or _SITE.fullmatch(site) is None:
        raise SensorConfigError("Sensor identity is invalid")
    if producer != PRODUCER_ID or capture != CAPTURE_SOURCE_ID or site != SITE_ID:
        raise SensorConfigError("Sensor identity authority is fixed")
    cidrs = _cidrs(value("GUEST_CIDRS", GUEST_CIDRS))
    server = _ipv4(value("DHCP_SERVER_AUTHORITY", DHCP_SERVER_AUTHORITY))
    option54 = _ipv4(value("DHCP_OPTION54_AUTHORITY", DHCP_OPTION54_AUTHORITY))
    if cidrs != (ipaddress.ip_network(GUEST_CIDRS),) or server != DHCP_SERVER_AUTHORITY or option54 != DHCP_OPTION54_AUTHORITY:
        raise SensorConfigError("Sensor guest scope authority is invalid")
    base_url = value("EVIDENCE_BASE_URL", EVIDENCE_BASE_URL).rstrip("/")
    parsed = urlsplit(base_url)
    if parsed.scheme != "https" or parsed.query or parsed.fragment or not parsed.netloc or base_url != EVIDENCE_BASE_URL:
        raise SensorConfigError("DEVICE_FINGERPRINT_SENSOR_EVIDENCE_BASE_URL is invalid")
    ca = _absolute(value("CA_CERT_PATH", CA_CERT_PATH), "CA_CERT_PATH")
    spool = _absolute(value("SPOOL_PATH", SPOOL_PATH), "SPOOL_PATH")
    socket_path = _absolute(value("EVE_SOCKET_PATH", EVE_SOCKET_PATH), "EVE_SOCKET_PATH")
    credential = env.get("CREDENTIALS_DIRECTORY")
    credential_path = None
    if credential:
        credential_path = str(Path(credential) / "device-fingerprint-bearer")
    config = SensorConfig(
        enabled=enabled, interface=interface, producer_id=producer,
        capture_source_id=capture, site_id=site, guest_cidrs=cidrs,
        dhcp_server_authority=server, dhcp_option54_authority=option54,
        evidence_base_url=base_url, ca_cert_path=ca, credential_path=credential_path,
        spool_path=spool,
        spool_total_budget_bytes=_integer(env, "SPOOL_TOTAL_BUDGET_BYTES", 134217728, 1, 1 << 40),
        spool_main_db_max_bytes=_integer(env, "SPOOL_MAIN_DB_MAX_BYTES", 117440512, 1, 1 << 40),
        spool_write_headroom_bytes=_integer(env, "SPOOL_WRITE_HEADROOM_BYTES", 16777216, 0, 1 << 40),
        spool_max_events=_integer(env, "SPOOL_MAX_EVENTS", 100000, 1, 100000),
        delivery_batch_size=_integer(env, "DELIVERY_BATCH_SIZE", 100, 1, 100),
        http_timeout_seconds=float(_integer(env, "HTTP_TIMEOUT_SECONDS", 5, 1, 60)),
        raw_dedup_max_entries=_integer(env, "RAW_DEDUP_MAX_ENTRIES", 65536, 1, 65536),
        raw_dedup_horizon_ms=_exact_decimal(env, "RAW_DEDUP_HORIZON_MS", 0.25),
        core_ready_host=_exact(value("CORE_READY_HOST", "127.0.0.1"), "127.0.0.1", "CORE_READY_HOST"),
        core_ready_port=_exact_integer(env, "CORE_READY_PORT", 8088),
        core_ready_connect_timeout_seconds=float(_integer(env, "CORE_READY_CONNECT_TIMEOUT_SECONDS", 1, 1, 10)),
        core_ready_poll_interval_seconds=float(_integer(env, "CORE_READY_POLL_INTERVAL_SECONDS", 10, 1, 60)),
        core_ready_max_wait_seconds=float(_integer(env, "CORE_READY_MAX_WAIT_SECONDS", 1800, 1, 1800)),
        eve_max_datagram_bytes=_integer(env, "EVE_MAX_DATAGRAM_BYTES", 262144, 4096, 262144),
        eve_socket_path=socket_path,
        eve_socket_wait_seconds=_integer(env, "EVE_SOCKET_WAIT_SECONDS", 1830, 1, 1830),
    )
    if config.spool_main_db_max_bytes + config.spool_write_headroom_bytes > config.spool_total_budget_bytes:
        raise SensorConfigError("Sensor spool capacity budget is invalid")
    return config


def _boolean(value: object, name: str) -> bool:
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    raise SensorConfigError(f"DEVICE_FINGERPRINT_SENSOR_{name} must be true or false")


def _integer(env: Mapping[str, str], name: str, default: int, minimum: int, maximum: int) -> int:
    raw = env.get("DEVICE_FINGERPRINT_SENSOR_" + name, str(default))
    try:
        result = int(raw)
    except (TypeError, ValueError) as exc:
        raise SensorConfigError(f"DEVICE_FINGERPRINT_SENSOR_{name} is invalid") from exc
    if not minimum <= result <= maximum:
        raise SensorConfigError(f"DEVICE_FINGERPRINT_SENSOR_{name} is outside the allowed range")
    return result


def _decimal(env: Mapping[str, str], name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        result = float(env.get("DEVICE_FINGERPRINT_SENSOR_" + name, str(default)))
    except (TypeError, ValueError) as exc:
        raise SensorConfigError(f"DEVICE_FINGERPRINT_SENSOR_{name} is invalid") from exc
    if not minimum <= result <= maximum:
        raise SensorConfigError(f"DEVICE_FINGERPRINT_SENSOR_{name} is outside the allowed range")
    return result


def _cidrs(raw: str) -> tuple[object, ...]:
    try:
        result = tuple(ipaddress.ip_network(item.strip(), strict=True) for item in raw.split(","))
    except ValueError as exc:
        raise SensorConfigError("DEVICE_FINGERPRINT_SENSOR_GUEST_CIDRS is invalid") from exc
    if not result or any(network.version != 4 for network in result):
        raise SensorConfigError("DEVICE_FINGERPRINT_SENSOR_GUEST_CIDRS is invalid")
    return result


def _ipv4(raw: str) -> str:
    try:
        parsed = ipaddress.ip_address(raw)
    except ValueError as exc:
        raise SensorConfigError("DHCP authority is invalid") from exc
    if parsed.version != 4:
        raise SensorConfigError("DHCP authority is invalid")
    return str(parsed)


def _absolute(raw: str, name: str) -> str:
    if not (raw.startswith("/") or Path(raw).is_absolute()):
        raise SensorConfigError(f"DEVICE_FINGERPRINT_SENSOR_{name} must be absolute")
    return raw


def _exact(value: str, expected: str, name: str) -> str:
    if value != expected:
        raise SensorConfigError(f"DEVICE_FINGERPRINT_SENSOR_{name} is fixed")
    return value


def _exact_integer(env: Mapping[str, str], name: str, expected: int) -> int:
    value = _integer(env, name, expected, expected, expected)
    return value


def _exact_decimal(env: Mapping[str, str], name: str, expected: float) -> float:
    return _decimal(env, name, expected, expected, expected)
