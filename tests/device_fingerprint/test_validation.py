from datetime import timedelta

import pytest

from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.validation import *
from tests.device_fingerprint import NOW, SITE


def test_canonical_identifiers_mac_ip_uuid_and_timestamp():
    assert validate_site_id(SITE) == SITE
    assert validate_mac("aa-bb-cc-dd-ee-ff") == "AA:BB:CC:DD:EE:FF"
    assert validate_ip("192.168.8.1") == "192.168.8.1"
    assert validate_ip("2001:0db8:0000:0000:0000:0000:0000:0001") == "2001:db8::1"
    assert validate_uuid("11111111-1111-4111-8111-111111111111")
    assert parse_utc("2026-09-14T12:00:00.000Z") == NOW
    assert validate_machine_id("sensor-01") == "sensor-01"
    assert validate_source_kind("tcp_syn") == "tcp_syn"
    assert validate_version("1.0.0+one") == "1.0.0+one"


@pytest.mark.parametrize("value", ["2026-09-14T12:00:00Z", "2026-09-14T12:00:00.00Z", "2026-09-14T12:00:00.000+00:00"])
def test_timestamp_is_exact_utc_milliseconds(value):
    with pytest.raises(DeviceFingerprintValidationError):
        parse_utc(value)


def test_clock_bounds_and_enums():
    with pytest.raises(DeviceFingerprintValidationError):
        validate_observed_at(format_utc(NOW + timedelta(seconds=121)), now=NOW, max_future_skew_seconds=120, max_delayed_event_age_seconds=60)
    with pytest.raises(DeviceFingerprintValidationError):
        validate_observed_at(format_utc(NOW - timedelta(seconds=61)), now=NOW, max_future_skew_seconds=120, max_delayed_event_age_seconds=60)
    assert validate_quality("partial") == "partial"
    assert validate_health_status("unsupported") == "unsupported"
    assert validate_reason_code("parser_unavailable") == "parser_unavailable"


def test_payload_forbidden_fields_and_nonfinite_fail():
    for payload in ({"sni": "private"}, {"nested": {"raw_headers": {}}}, {"rate": float("inf")}):
        with pytest.raises(DeviceFingerprintValidationError):
            canonical_json(payload)
    assert "destination_ip" not in {"source_event_id", "source_kind", "payload"}


@pytest.mark.parametrize("validator,value", [
    (validate_site_id, "A" * 24), (validate_machine_id, "bad value"),
    (validate_source_kind, "tls-client"), (validate_version, " bad"),
    (validate_uuid, "11111111-1111-4111-8111-11111111111A"),
    (validate_ip, "not-an-ip"), (validate_mac, "not-a-mac"),
    (validate_reason_code, "raw error text"),
])
def test_noncanonical_values_fail(validator, value):
    with pytest.raises(DeviceFingerprintValidationError):
        validator(value)


def test_nullable_ip_subtype_reason_and_exact_enums():
    assert validate_ip(None) is None
    assert validate_nullable_machine_id(None) is None
    assert validate_reason_code(None) is None
    for value in ("available", "valid", None, 1):
        if value not in {"valid", "partial", "degraded"}:
            with pytest.raises(DeviceFingerprintValidationError):
                validate_quality(value)
        if value not in {"available", "unavailable", "unsupported"}:
            with pytest.raises(DeviceFingerprintValidationError):
                validate_health_status(value)
