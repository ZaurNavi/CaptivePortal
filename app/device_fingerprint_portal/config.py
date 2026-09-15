"""Strict isolated environment configuration for the Task-03 portal producer."""

from __future__ import annotations

import ipaddress
import os
from collections.abc import Mapping
from pathlib import Path
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

    producer_id = exact("PRODUCER_ID")
    capture_source_id = exact("CAPTURE_SOURCE_ID")
    site_id = exact("SITE_ID")
    guest_cidrs = tuple(ipaddress.ip_network(item, strict=True) for item in exact("GUEST_CIDRS").split(","))
    allowed_ssids = tuple(exact("ALLOWED_SSIDS").split(","))
    base_url = exact("EVIDENCE_BASE_URL")
    parsed = urlsplit(base_url)
    if parsed.scheme != "https" or parsed.query or parsed.fragment:
        raise PortalEvidenceConfigError("Portal evidence URL is invalid")
    ca_cert_path = _absolute(exact("CA_CERT_PATH"), "CA_CERT_PATH")
    credential_path = _absolute(exact("CREDENTIAL_PATH"), "CREDENTIAL_PATH")
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
    if not (value.startswith("/") or Path(value).is_absolute()):
        raise PortalEvidenceConfigError(f"DEVICE_FINGERPRINT_PORTAL_{name} must be absolute")
    return value
