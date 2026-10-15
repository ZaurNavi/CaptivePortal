"""Strict isolated environment configuration for the Task-03 portal producer."""

from __future__ import annotations

import ipaddress
import os
import re
from collections.abc import Mapping
from urllib.parse import urlsplit

from .models import PortalEvidenceConfig, PortalEvidenceConfigError

PRODUCER_ID = "portal-zefer-01"
CAPTURE_SOURCE_ID = "zefer-portal-http-01"
SITE_ID = "6a64f17630da7c70d232187a"
GUEST_CIDRS = "192.168.8.0/22"
ALLOWED_SSIDS = "Zefer_Parki"
EVIDENCE_BASE_URL = "https://192.168.0.202:9443/api/internal/device-fingerprint/v1"
CA_CERT_PATH = "/etc/captive-portal/device-fingerprint/portal-ca.crt"
CREDENTIAL_PATH = "/etc/captive-portal/device-fingerprint/portal.bearer"


def portal_config_from_env(env: Mapping[str, str] | None = None) -> PortalEvidenceConfig:
    values = os.environ if env is None else env
    enabled = _boolean(values.get("DEVICE_FINGERPRINT_PORTAL_ENABLED", "false"))
    defaults = {
        "PRODUCER_ID": PRODUCER_ID,
        "CAPTURE_SOURCE_ID": CAPTURE_SOURCE_ID,
        "SITE_ID": SITE_ID,
        "GUEST_CIDRS": GUEST_CIDRS,
        "ALLOWED_SSIDS": ALLOWED_SSIDS,
        "EVIDENCE_BASE_URL": EVIDENCE_BASE_URL,
        "CA_CERT_PATH": CA_CERT_PATH,
        "CREDENTIAL_PATH": CREDENTIAL_PATH,
        "QUEUE_MAX_EVENTS": "256",
        "BATCH_SIZE": "50",
        "QUEUE_MAX_AGE_SECONDS": "300",
        "COALESCE_SECONDS": "21600",
        "COALESCE_MAX_ENTRIES": "8192",
        "CONNECT_TIMEOUT_SECONDS": "0.5",
        "READ_TIMEOUT_SECONDS": "2.0",
        "TRANSIENT_COOLDOWN_SECONDS": "30",
        "REJECT_COOLDOWN_SECONDS": "300",
    }
    source = values if enabled else {}

    def exact(name: str) -> str:
        raw = source.get("DEVICE_FINGERPRINT_PORTAL_" + name, defaults[name])
        if not isinstance(raw, str) or raw != defaults[name] or "\x00" in raw:
            raise PortalEvidenceConfigError(f"DEVICE_FINGERPRINT_PORTAL_{name} is invalid")
        return raw

    def value(name: str) -> str:
        raw = source.get("DEVICE_FINGERPRINT_PORTAL_" + name, defaults[name])
        if not isinstance(raw, str) or not raw or any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in raw):
            raise PortalEvidenceConfigError(f"DEVICE_FINGERPRINT_PORTAL_{name} is invalid")
        return raw

    producer_id = value("PRODUCER_ID")
    capture_source_id = value("CAPTURE_SOURCE_ID")
    site_id = value("SITE_ID")
    if (re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", producer_id) is None
            or re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", capture_source_id) is None
            or re.fullmatch(r"[0-9a-f]{24}", site_id) is None):
        raise PortalEvidenceConfigError("Portal evidence identity is invalid")
    guest_cidrs = _cidrs(value("GUEST_CIDRS"))
    allowed_ssids = _ssids(value("ALLOWED_SSIDS"))
    base_url = _evidence_url(value("EVIDENCE_BASE_URL"))
    ca_cert_path = _absolute(value("CA_CERT_PATH"), "CA_CERT_PATH")
    credential_path = _absolute(value("CREDENTIAL_PATH"), "CREDENTIAL_PATH")
    return PortalEvidenceConfig(
        enabled=enabled,
        producer_id=producer_id,
        capture_source_id=capture_source_id,
        site_id=site_id,
        guest_cidrs=guest_cidrs,
        allowed_ssids=allowed_ssids,
        evidence_base_url=base_url,
        ca_cert_path=ca_cert_path,
        credential_path=credential_path,
        queue_max_events=int(exact("QUEUE_MAX_EVENTS")),
        batch_size=int(exact("BATCH_SIZE")),
        queue_max_age_seconds=int(exact("QUEUE_MAX_AGE_SECONDS")),
        coalesce_seconds=int(exact("COALESCE_SECONDS")),
        coalesce_max_entries=int(exact("COALESCE_MAX_ENTRIES")),
        connect_timeout_seconds=float(exact("CONNECT_TIMEOUT_SECONDS")),
        read_timeout_seconds=float(exact("READ_TIMEOUT_SECONDS")),
        transient_cooldown_seconds=int(exact("TRANSIENT_COOLDOWN_SECONDS")),
        reject_cooldown_seconds=int(exact("REJECT_COOLDOWN_SECONDS")),
    )


def _boolean(value: object) -> bool:
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    raise PortalEvidenceConfigError("DEVICE_FINGERPRINT_PORTAL_ENABLED must be true or false")


def _absolute(value: str, name: str) -> str:
    if not value.startswith("/") or value != value.strip():
        raise PortalEvidenceConfigError(f"DEVICE_FINGERPRINT_PORTAL_{name} must be absolute")
    return value


def _cidrs(raw: str) -> tuple[object, ...]:
    try:
        items = raw.split(",")
        if not 1 <= len(items) <= 16:
            raise ValueError
        result = tuple(ipaddress.IPv4Network(item, strict=True) for item in items)
        if any("/" not in item or str(network) != item or network.prefixlen == 0
               for item, network in zip(items, result)):
            raise ValueError
        if any(first.overlaps(second) for index, first in enumerate(result) for second in result[index + 1:]):
            raise ValueError
        return result
    except ValueError:
        raise PortalEvidenceConfigError("DEVICE_FINGERPRINT_PORTAL_GUEST_CIDRS is invalid") from None


def _ssids(raw: str) -> tuple[str, ...]:
    try:
        values = tuple(raw.split(","))
        if (not 1 <= len(values) <= 16 or len(set(values)) != len(values)
                or any(not value.strip() or not 1 <= len(value.encode("utf-8")) <= 32
                       or "*" in value for value in values)):
            raise ValueError
        return values
    except (ValueError, UnicodeError):
        raise PortalEvidenceConfigError("DEVICE_FINGERPRINT_PORTAL_ALLOWED_SSIDS is invalid") from None


def _evidence_url(raw: str) -> str:
    try:
        if (not raw.isascii() or not raw.startswith("https://")
                or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in raw)
                or any(char in raw for char in "%\\@?#[]")):
            raise ValueError
        parsed = urlsplit(raw)
        prefix = "/api/internal/device-fingerprint/v1"
        if parsed.scheme != "https" or parsed.path not in (prefix, prefix + "/") or not parsed.netloc:
            raise ValueError
        authority = parsed.netloc.split(":")
        if len(authority) not in (1, 2):
            raise ValueError
        host = authority[0]
        try:
            address = ipaddress.IPv4Address(host)
        except ValueError:
            if (not 1 <= len(host) <= 253 or any(re.fullmatch(
                r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label) is None for label in host.split("."))
                    or re.fullmatch(r"(?:[0-9]+|0[xX][0-9a-fA-F]*)", host.rsplit(".", 1)[-1]) is not None):
                raise ValueError
        else:
            if str(address) != host or (host != "127.0.0.1" and not any(address in ipaddress.IPv4Network(cidr)
                    for cidr in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))):
                raise ValueError
        if len(authority) == 2:
            port = authority[1]
            if not 1 <= len(port) <= 5 or re.fullmatch(r"[1-9][0-9]*", port) is None or not 1 <= int(port) <= 65535:
                raise ValueError
        return raw[:-1] if parsed.path.endswith("/") else raw
    except ValueError:
        raise PortalEvidenceConfigError("DEVICE_FINGERPRINT_PORTAL_EVIDENCE_BASE_URL is invalid") from None
