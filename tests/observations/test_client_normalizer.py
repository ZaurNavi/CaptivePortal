from __future__ import annotations

import json
import math

import pytest

from app.observations.normalizer import (
    canonical_client_mac,
    classify_client,
    normalize_client_observation,
)


def full_row(**updates):
    row = {
        "mac": "aa-bb-cc-dd-ee-ff",
        "id": "client-id",
        "name": " Phone ",
        "hostName": "host",
        "systemName": "Android",
        "deviceType": "phone",
        "connectDevType": "ap",
        "ip": "192.168.001.010",
        "ipv6List": ["2001:0db8::1"],
        "ssid": "Zefer_Parki",
        "apName": "AP-1",
        "apMac": "10-20-30-40-50-60",
        "connectType": 99,
        "signalLevel": 4,
        "signalRank": 3,
        "wifiMode": "ax",
        "radioId": 1,
        "channel": 36,
        "rxRate": 100,
        "txRate": 200,
        "rssi": -55,
        "snr": 35,
        "vid": 20,
        "uptime": 60,
        "lastSeen": 1000,
        "authStatus": 2,
        "activity": 1,
        "wireless": True,
        "powerSave": False,
        "blocked": False,
        "guest": True,
        "active": True,
        "manager": False,
        "trafficDown": 1000,
        "trafficUp": 2000,
        "downPacket": 10,
        "upPacket": 20,
        "password": "TEST_WIFI_PASSWORD_SHOULD_NOT_LEAK",
        "dot1xIdentity": "secret-identity",
        "ipSetting": {"unknown": "secret"},
        "multiLink": {"unknown": "secret"},
    }
    row.update(updates)
    return row


def normalize(raw):
    return normalize_client_observation(
        raw,
        cycle_id="cycle",
        site_id="site",
        observed_at="2026-01-01T00:00:00.000Z",
        source_inventory_complete=True,
    )


def test_full_row_is_allowlisted_canonical_and_drops_structured_unknowns():
    row = normalize(full_row(ip="192.168.1.10"))
    assert row is not None
    assert row["client_mac"] == "AA:BB:CC:DD:EE:FF"
    assert row["ap_mac"] == "10:20:30:40:50:60"
    assert row["ip"] == "192.168.1.10"
    assert row["ipv6_list_json"] == '["2001:db8::1"]'
    assert row["band"] == "5GHz"
    assert row["connect_type"] == 99
    assert row["rssi"] == -55
    assert row["traffic_down"] == 1000
    serialized = json.dumps(row)
    assert "password" not in serialized
    assert "dot1x" not in serialized
    assert "ipSetting" not in serialized
    assert "multiLink" not in serialized
    assert "TEST_WIFI_PASSWORD_SHOULD_NOT_LEAK" not in serialized


def test_minimal_row_and_radio_mapping():
    row = normalize({
        "mac": "AA:BB:CC:DD:EE:FF",
        "wireless": True,
        "active": True,
        "authStatus": 2,
        "radioId": 0,
    })
    assert row == {
        "cycle_id": "cycle",
        "observed_at": "2026-01-01T00:00:00.000Z",
        "site_id": "site",
        "client_mac": "AA:BB:CC:DD:EE:FF",
        "source_inventory_complete": True,
        "radio_id": 0,
        "auth_status": 2,
        "wireless": True,
        "active": True,
        "band": "2.4GHz",
    }
    other = normalize(full_row(radioId=7, ip="192.168.1.10"))
    assert other["radio_id"] == 7
    assert "band" not in other


@pytest.mark.parametrize("value", [True, "2", 2.0, math.nan, math.inf])
def test_exact_integer_rules_do_not_coerce(value):
    row = normalize(full_row(channel=value, ip="192.168.1.10"))
    assert "channel" not in row


def test_invalid_optional_ip_ipv6_mac_and_types_become_null_or_absent():
    row = normalize(full_row(
        ip="not-an-ip",
        ipv6List=["192.168.1.1"],
        apMac="bad",
        active=1,
        trafficDown=-1,
    ))
    assert "ip" not in row
    assert "ipv6_list_json" not in row
    assert "ap_mac" not in row
    assert "active" not in row
    assert "traffic_down" not in row


def test_invalid_required_identity_skips_row():
    assert canonical_client_mac({"mac": "bad"}) is None
    assert normalize({"mac": "bad"}) is None
    assert normalize(["not", "an", "object"]) is None


@pytest.mark.parametrize(
    ("updates", "eligible", "reason", "unknown"),
    [
        ({}, True, "eligible", False),
        ({"wireless": False}, False, "not_wireless", False),
        ({"wireless": 1}, False, "not_wireless", False),
        ({"active": False}, False, "not_active", False),
        ({"authStatus": 1}, False, "not_authorized", False),
        ({"authStatus": 7}, False, "unknown_auth_status", True),
        ({"authStatus": "2"}, False, "unknown_auth_status", True),
    ],
)
def test_eligibility_is_exact(updates, eligible, reason, unknown):
    result = classify_client(full_row(**updates))
    assert result.eligible is eligible
    assert result.reason == reason
    assert result.unknown_auth_status is unknown


def test_ssid_allowlist_is_optional_exact_and_case_sensitive():
    raw = full_row(ssid="Zefer_Parki")
    assert classify_client(raw, ()).eligible is True
    assert classify_client(raw, ("Zefer_Parki",)).eligible is True
    assert classify_client(raw, ("zefer_parki",)).reason == "ssid_filtered"
