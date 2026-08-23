from __future__ import annotations

import json

import pytest

from app.current_state.normalizer import (
    canonical_scope,
    current_client_relevant,
    normalize_current_ap,
    normalize_current_client,
)

from .conftest import NOW, SITE


def raw_client(**updates):
    row = {
        "mac": "aa-bb-cc-dd-ee-01",
        "wireless": True,
        "active": True,
        "ssid": "Zefer_Parki",
        "authStatus": 2,
        "trafficDown": 10,
        "trafficUp": 20,
    }
    row.update(updates)
    return row


@pytest.mark.parametrize(
    ("status", "expected"),
    [(2, "authorized"), (1, "pending"), (0, "other"), (3, "other"), (99, "other"), (None, "unknown"), ("2", "unknown")],
)
def test_auth_classification(status, expected):
    item = normalize_current_client(raw_client(authStatus=status), cycle_id="c", site_id=SITE, observed_at=NOW, ssids=("Zefer_Parki",))
    assert item is not None
    assert item.values["auth_classification"] == expected
    assert item.values["auth_status_code"] == (status if type(status) is int else None)


@pytest.mark.parametrize("updates", [{"active": False}, {"wireless": False}, {"ssid": "Other"}, {"ssid": "zefer_parki"}])
def test_inactive_wired_or_out_of_scope_is_excluded(updates):
    raw = raw_client(**updates)
    assert current_client_relevant(raw, ("Zefer_Parki",)) is False
    assert normalize_current_client(raw, cycle_id="c", site_id=SITE, observed_at=NOW, ssids=("Zefer_Parki",)) is None


def test_client_allowlist_fields_and_no_controller_id():
    item = normalize_current_client(
        raw_client(id="controller-secret-id", ip="192.168.1.010", apMac="11-22-33-44-55-66", radioId=1, rssi=-55, snr=30),
        cycle_id="c", site_id=SITE, observed_at=NOW, ssids=("Zefer_Parki",),
    )
    assert item is not None
    assert "controller_client_id" not in item.values
    assert item.values["ap_mac"] == "11:22:33:44:55:66"
    assert item.values["band"] == "5GHz"
    assert item.values["rssi"] == -55
    assert item.values["ip"] is None  # Non-canonical invalid IPv4 text is not persisted.


def test_nullable_counters_and_safe_total_overflow():
    missing = normalize_current_client(raw_client(trafficDown=None), cycle_id="c", site_id=SITE, observed_at=NOW, ssids=("Zefer_Parki",))
    assert missing.values["controller_traffic_total"] is None
    overflow = normalize_current_client(raw_client(trafficDown=9_223_372_036_854_775_807, trafficUp=1), cycle_id="c", site_id=SITE, observed_at=NOW, ssids=("Zefer_Parki",))
    assert overflow.values["controller_traffic_total"] is None
    assert overflow.warning_count >= 1


@pytest.mark.parametrize("field,value", [("name", "x" * 257), ("hostName", "x" * 254), ("deviceType", "x" * 129), ("apName", "bad\x00name")])
def test_unsafe_optional_text_becomes_null_with_warning(field, value):
    item = normalize_current_client(raw_client(**{field: value}), cycle_id="c", site_id=SITE, observed_at=NOW, ssids=("Zefer_Parki",))
    target = {"hostName": "hostname", "deviceType": "device_type", "apName": "ap_name"}.get(field, field)
    assert item.values[target] is None
    assert item.warning_count >= 1


def test_scope_is_canonical_and_hash_stable():
    first_json, first_hash = canonical_scope("client", SITE, ("b", "a", "b"))
    second_json, second_hash = canonical_scope("client", SITE, ("a", "b"))
    assert first_json == second_json
    assert first_hash == second_hash
    assert json.loads(first_json)["ssids"] == ["a", "b"]


@pytest.mark.parametrize(("status", "classification"), [(1, "online"), (0, "other"), (2, "other"), (None, "unknown"), ("1", "unknown")])
def test_ap_status_is_conservative(status, classification):
    item = normalize_current_ap(
        {"type": "ap", "mac": "11-22-33-44-55-66", "status": status},
        cycle_id="ap", site_id=SITE, observed_at=NOW,
    )
    assert item is not None
    assert item.values["status_classification"] == classification
    assert item.values["status_classification"] != "offline"


def test_non_ap_and_invalid_ap_identity_are_not_stored():
    assert normalize_current_ap({"type": "switch", "mac": "11-22-33-44-55-66"}, cycle_id="ap", site_id=SITE, observed_at=NOW) is None
    assert normalize_current_ap({"type": "ap", "mac": "bad"}, cycle_id="ap", site_id=SITE, observed_at=NOW) is None


def test_ap_optional_text_and_ip_are_safe():
    item = normalize_current_ap(
        {"type": "ap", "mac": "11-22-33-44-55-66", "name": "x" * 257, "ip": "192.168.1.2", "uptimeRaw": "1 day"},
        cycle_id="ap", site_id=SITE, observed_at=NOW,
    )
    assert item.values["name"] is None
    assert item.values["ip"] == "192.168.1.2"
    assert item.values["uptime_raw"] == "1 day"
    assert item.warning_count == 1
