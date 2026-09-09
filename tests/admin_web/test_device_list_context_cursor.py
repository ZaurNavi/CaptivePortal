from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import asdict, replace

import pytest

from app.admin_web.cursors import filter_fingerprint
from app.admin_web.device_list_context_cursor import (
    DeviceListContextCursor,
    DeviceListContextCursorCodec,
    DeviceListContextCursorError,
)
from app.current_state.normalizer import canonical_scope


SITE = "a" * 24
OTHER_SITE = "b" * 24
DEVICE = "10000000-0000-4000-8000-000000000001"
FILTERS = {"mac": "02:00:00:00:00:01"}
SECRET = bytes.fromhex("12" * 32)
SCOPE = {
    "scope_type": "client_ssid_allowlist",
    "site_id": SITE,
    "ssids": ["Guest", "Zefer_Parki"],
}
SCOPE_HASH = canonical_scope(
    "client", SITE, tuple(SCOPE["ssids"])
)[1]
FRESH = {
    "observed_at": "2026-09-09T11:59:50.000Z",
    "capture_finished_at": "2026-09-09T11:59:55.000Z",
    "age_seconds": 10.0,
    "freshness_status": "fresh",
    "freshness_reason": "within_freshness_window",
    "complete": True,
}
STALE = {
    **FRESH,
    "age_seconds": 100.0,
    "freshness_status": "stale",
    "freshness_reason": "older_than_freshness_window",
}


def _codec(maximum=4096, secret=SECRET):
    return DeviceListContextCursorCodec(
        secret_key=secret, maximum_length=maximum
    )


def _trusted(**changes):
    value = DeviceListContextCursor(
        version=1,
        kind="devices_context",
        site_id=SITE,
        filter_fingerprint=filter_fingerprint(FILTERS),
        ordering_contract_version=1,
        overlay_mode="trusted",
        evaluated_at_utc="2026-09-09T12:00:00.000Z",
        source_execution_status="available",
        scope=SCOPE,
        snapshot=FRESH,
        current_cycle_id="cycle-1",
        source_scope_hash=SCOPE_HASH,
        last_online_rank=0,
        last_site_last_seen_at="2026-09-09T11:00:00.000Z",
        last_device_id=DEVICE,
    )
    return replace(value, **changes)


def _unknown_semantic(**changes):
    value = _trusted(
        overlay_mode="unknown",
        snapshot=STALE,
        current_cycle_id=None,
        source_scope_hash=None,
        last_online_rank=1,
    )
    return replace(value, **changes)


def _unknown_unavailable(**changes):
    value = _trusted(
        overlay_mode="unknown",
        source_execution_status="unavailable",
        scope=None,
        snapshot=None,
        current_cycle_id=None,
        source_scope_hash=None,
        last_online_rank=1,
    )
    return replace(value, **changes)


def _signed(payload, *, secret=SECRET, canonical=True):
    raw = (
        json.dumps(
            payload,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":") if canonical else (", ", ": "),
            sort_keys=True,
        ).encode("ascii")
    )
    signature = hmac.new(secret, raw, hashlib.sha256).digest()
    encode = lambda value: base64.urlsafe_b64encode(value).decode().rstrip("=")
    return f"{encode(raw)}.{encode(signature)}"


@pytest.mark.parametrize(
    "value",
    [_trusted(), _unknown_semantic(), _unknown_unavailable()],
    ids=["trusted", "unknown-semantic", "unknown-unavailable"],
)
def test_device_list_context_cursor_round_trip(value):
    token = _codec().encode(value)
    assert _codec().decode(token, site_id=SITE, filters=FILTERS) == value


def test_device_list_context_cursor_none_decodes_without_work():
    assert _codec().decode(None, site_id=SITE, filters=FILTERS) is None


@pytest.mark.parametrize("mode", ["wrong-secret", "payload", "signature"])
def test_device_list_context_cursor_detects_cryptographic_tamper(mode):
    token = _codec().encode(_trusted())
    if mode == "wrong-secret":
        decoder = _codec(secret=b"z" * 32)
    else:
        decoder = _codec()
        left, right = token.split(".")
        if mode == "payload":
            left = ("A" if left[0] != "A" else "B") + left[1:]
        else:
            right = ("A" if right[0] != "A" else "B") + right[1:]
        token = f"{left}.{right}"
    with pytest.raises(DeviceListContextCursorError):
        decoder.decode(token, site_id=SITE, filters=FILTERS)


@pytest.mark.parametrize(
    "field,value",
    [
        ("overlay_mode", "unknown"),
        ("evaluated_at_utc", "bad"),
        ("current_cycle_id", ""),
        ("source_scope_hash", "0" * 64),
        ("last_online_rank", 2),
        ("last_device_id", "bad"),
        ("site_id", OTHER_SITE),
        ("filter_fingerprint", "0" * 64),
    ],
)
def test_device_list_context_cursor_rejects_signed_field_tamper(field, value):
    payload = asdict(_trusted())
    payload[field] = value
    with pytest.raises(DeviceListContextCursorError):
        _codec().decode(_signed(payload), site_id=SITE, filters=FILTERS)


@pytest.mark.parametrize("token", ["", "a", ".a", "a.", "a.b.c", "%=.abc"])
def test_device_list_context_cursor_rejects_malformed_segments(token):
    with pytest.raises(DeviceListContextCursorError):
        _codec().decode(token, site_id=SITE, filters=FILTERS)


def test_device_list_context_cursor_rejects_wrong_signature_length():
    payload = asdict(_trusted())
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    encode = lambda value: base64.urlsafe_b64encode(value).decode().rstrip("=")
    token = f"{encode(raw)}.{encode(b'x')}"
    with pytest.raises(DeviceListContextCursorError):
        _codec().decode(token, site_id=SITE, filters=FILTERS)


def test_device_list_context_cursor_rejects_noncanonical_json():
    with pytest.raises(DeviceListContextCursorError, match="canonical"):
        _codec().decode(
            _signed(asdict(_trusted()), canonical=False),
            site_id=SITE,
            filters=FILTERS,
        )


@pytest.mark.parametrize("change", ["extra", "missing"])
def test_device_list_context_cursor_requires_exact_fields(change):
    payload = asdict(_trusted())
    if change == "extra":
        payload["extra"] = 1
    else:
        payload.pop("kind")
    with pytest.raises(DeviceListContextCursorError):
        _codec().decode(_signed(payload), site_id=SITE, filters=FILTERS)


@pytest.mark.parametrize(
    "field,value",
    [
        ("kind", "devices"),
        ("version", 2),
        ("ordering_contract_version", 2),
    ],
)
def test_device_list_context_cursor_rejects_wrong_contract(field, value):
    payload = asdict(_trusted())
    payload[field] = value
    with pytest.raises(DeviceListContextCursorError):
        _codec().decode(_signed(payload), site_id=SITE, filters=FILTERS)


def test_device_list_context_cursor_rejects_wrong_requested_site_and_filter():
    token = _codec().encode(_trusted())
    with pytest.raises(DeviceListContextCursorError):
        _codec().decode(token, site_id=OTHER_SITE, filters=FILTERS)
    with pytest.raises(DeviceListContextCursorError):
        _codec().decode(token, site_id=SITE, filters={})


def test_device_list_context_cursor_enforces_input_and_output_bounds():
    token = _codec().encode(_trusted())
    with pytest.raises(DeviceListContextCursorError):
        _codec(maximum=len(token) - 1).encode(_trusted())
    with pytest.raises(DeviceListContextCursorError):
        _codec(maximum=len(token) - 1).decode(
            token, site_id=SITE, filters=FILTERS
        )


@pytest.mark.parametrize(
    "value",
    [
        _trusted(source_execution_status="unavailable"),
        _trusted(snapshot=STALE),
        _unknown_semantic(last_online_rank=0),
        _unknown_semantic(source_execution_status="unavailable"),
        _unknown_unavailable(snapshot=STALE),
    ],
)
def test_device_list_context_cursor_rejects_cross_field_contradictions(value):
    with pytest.raises(DeviceListContextCursorError):
        _codec().encode(value)


def test_device_list_context_cursor_requires_canonical_scope_and_hash():
    unsorted = {**SCOPE, "ssids": list(reversed(SCOPE["ssids"]))}
    duplicate = {**SCOPE, "ssids": ["Guest", "Guest"]}
    for scope in (unsorted, duplicate):
        with pytest.raises(DeviceListContextCursorError):
            _codec().encode(_trusted(scope=scope))
    with pytest.raises(DeviceListContextCursorError):
        _codec().encode(_trusted(source_scope_hash="0" * 64))


def test_device_list_context_cursor_validates_before_signing():
    with pytest.raises(DeviceListContextCursorError):
        _codec().encode(_trusted(last_device_id="not-a-uuid"))
