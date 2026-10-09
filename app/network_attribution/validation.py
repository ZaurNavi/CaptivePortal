"""NI validation reuses only existing scalar identity/time contracts."""

import hashlib
import ipaddress
import json
from dataclasses import asdict

from app.device_fingerprint.validation import (
    parse_utc, validate_machine_id, validate_site_id,
)
from app.device_fingerprint.models import DeviceFingerprintValidationError

from .models import NetworkAddressBindingFactV1, NetworkAttributionValidationError


def query_values(site_id, ipv4, event_at):
    try:
        validate_site_id(site_id)
        if not isinstance(ipv4, str) or str(ipaddress.IPv4Address(ipv4)) != ipv4:
            raise ValueError
        parse_utc(event_at)
        return site_id, ipv4, event_at
    except (ValueError, TypeError, DeviceFingerprintValidationError):
        raise NetworkAttributionValidationError("invalid_query") from None


def source_values(site_id, capture_source_id, event_at):
    try:
        validate_site_id(site_id)
        validate_machine_id(capture_source_id)
        parse_utc(event_at)
    except (ValueError, TypeError, DeviceFingerprintValidationError):
        raise NetworkAttributionValidationError("invalid_source") from None


def canonical_mac(value):
    if not isinstance(value, str):
        raise NetworkAttributionValidationError("invalid_mac")
    parts = value.split(":")
    try:
        raw = bytes(int(part, 16) for part in parts)
    except (ValueError, OverflowError):
        raise NetworkAttributionValidationError("invalid_mac") from None
    if (len(raw) != 6 or any(len(part) != 2 for part in parts)
            or raw == b"\0" * 6 or raw[0] & 1):
        raise NetworkAttributionValidationError("invalid_mac")
    return ":".join(f"{part:02X}" for part in raw)


def fact_identity(values):
    semantic = {key: value for key, value in values.items() if key not in {"fact_id", "ingested_at"}}
    return hashlib.sha256(json.dumps(semantic, sort_keys=True, allow_nan=False,
                                    separators=(",", ":")).encode("ascii")).hexdigest()


def make_fact(**values):
    values["schema_version"] = 1
    values["client_mac"] = canonical_mac(values["client_mac"])
    values["fact_id"] = fact_identity(values)
    fact = NetworkAddressBindingFactV1(**values)
    validate_fact(fact)
    return fact


def validate_fact(fact):
    if type(fact) is not NetworkAddressBindingFactV1:
        raise NetworkAttributionValidationError("invalid_fact")
    query_values(fact.site_id, fact.ipv4, fact.event_at)
    source_values(fact.site_id, fact.capture_source_id, fact.ingested_at)
    if (type(fact.schema_version) is not int or fact.schema_version != 1
            or canonical_mac(fact.client_mac) != fact.client_mac
            or type(fact.xid) is not int or not 0 <= fact.xid <= 0xFFFFFFFF
            or fact.fact_id != fact_identity(asdict(fact))):
        raise NetworkAttributionValidationError("invalid_fact")
    expected = {"ack": "trusted_dhcp_ack", "release": "validated_client_release",
                "decline": "validated_client_decline"}.get(fact.message_type)
    if expected is None or fact.authority_class != expected:
        raise NetworkAttributionValidationError("invalid_authority")
    if fact.message_type == "ack":
        query_values(fact.site_id, fact.server_ipv4, fact.event_at)
        query_values(fact.site_id, fact.option54_ipv4, fact.event_at)
        if type(fact.lease_seconds) is not int or not 1 <= fact.lease_seconds <= 86400:
            raise NetworkAttributionValidationError("invalid_lease")
    elif any(value is not None for value in (fact.server_ipv4, fact.option54_ipv4, fact.lease_seconds)):
        raise NetworkAttributionValidationError("invalid_client_fact")
