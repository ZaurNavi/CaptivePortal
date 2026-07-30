from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.visitor_registry.snapshot_normalizer import (
    SnapshotNormalizationError,
    normalize_client_snapshot,
)


FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "omada"
    / "client_snapshot_success.json"
)


@pytest.fixture
def raw_result():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["result"]


def test_full_fixture_is_normalized_without_mutation(raw_result):
    original = copy.deepcopy(raw_result)
    normalized = normalize_client_snapshot(raw_result)
    assert raw_result == original
    assert normalized.client == {
        "mac": "02:11:22:33:44:55",
        "controller_client_id": "test-client-id-001",
        "name": "test-android-device",
        "hostname": "test-android-device",
        "system_name": "test-android-device",
        "device_type": "android",
        "connect_device_type": "ap",
        "ssid": "Zefer_Parki",
        "ap_name": "Test-AP",
        "dot1x_identity": "",
        "connect_type": 1,
        "signal_level": 55,
        "signal_rank": 3,
        "wifi_mode": 4,
        "radio_id": 0,
        "channel": 11,
        "rx_rate": 6000,
        "tx_rate": 1000,
        "rssi": -68,
        "snr": 27,
        "vid": 0,
        "traffic_down": 2591757,
        "traffic_up": 409150,
        "uptime": 3176,
        "last_seen": 1785353153815,
        "auth_status": 0,
        "down_packet": 2762,
        "up_packet": 2115,
        "activity": 0,
        "connected_to_wireless_router": False,
        "wireless": True,
        "power_save": True,
        "blocked": False,
        "guest": False,
        "active": True,
        "manager": False,
        "ip_setting": {"useFixedAddr": False},
        "rate_limit": original["rateLimit"],
        "client_lock_to_ap_setting": {"enable": False},
        "multi_link": [],
        "ip": "192.0.2.27",
        "ipv6_list": [],
        "ap_mac": "02:AA:BB:CC:DD:EE",
    }
    assert (
        normalized.raw_controller_snapshot["futureUnknownField"]
        == {"preserved": True}
    )


@pytest.mark.parametrize(
    ("source", "normalized"),
    [
        ("connectType", "connect_type"),
        ("signalLevel", "signal_level"),
        ("active", "active"),
        ("rateLimit", "rate_limit"),
        ("multiLink", "multi_link"),
    ],
)
def test_wrong_optional_types_become_null(
    raw_result,
    source,
    normalized,
):
    raw_result[source] = "wrong"
    result = normalize_client_snapshot(raw_result)
    assert result.client[normalized] is None
    assert result.raw_controller_snapshot[source] == "wrong"


def test_bool_is_not_an_integer_or_number(raw_result):
    raw_result["channel"] = True
    raw_result["activity"] = False
    result = normalize_client_snapshot(raw_result)
    assert result.client["channel"] is None
    assert result.client["activity"] is None


def test_ip_and_ipv6_are_strict_and_canonical(raw_result):
    raw_result["ip"] = "2001:0db8::1"
    raw_result["ipv6List"] = [
        "2001:0db8::2",
        "192.0.2.1",
        "bad",
        1,
    ]
    result = normalize_client_snapshot(raw_result)
    assert result.client["ip"] == "2001:db8::1"
    assert result.client["ipv6_list"] == ["2001:db8::2"]


def test_invalid_optional_ap_mac_becomes_null(raw_result):
    raw_result["apMac"] = "bad"
    assert normalize_client_snapshot(
        raw_result
    ).client["ap_mac"] is None


@pytest.mark.parametrize("value", [None, "", "not-a-mac", 123])
def test_required_client_mac_is_strict(raw_result, value):
    raw_result["mac"] = value
    with pytest.raises(SnapshotNormalizationError):
        normalize_client_snapshot(raw_result)


def test_recursive_secret_redaction_preserves_allowed_identity(raw_result):
    raw_result["accessToken"] = "top-secret"
    raw_result["nested"] = {
        "PASSWORD": "secret",
        "authorization": "Bearer secret",
        "mac": "02-11-22-33-44-55",
        "list": [{"set-cookie": "session=secret"}],
    }
    raw_result["rateLimit"]["clientSecret"] = "secret"
    result = normalize_client_snapshot(raw_result)
    assert result.redacted_field_count == 5
    assert result.raw_controller_snapshot["accessToken"] == "[REDACTED]"
    assert result.raw_controller_snapshot["nested"]["PASSWORD"] == (
        "[REDACTED]"
    )
    assert result.raw_controller_snapshot["nested"]["mac"] == (
        "02-11-22-33-44-55"
    )
    assert (
        result.client["rate_limit"]["clientSecret"]
        == "[REDACTED]"
    )


@pytest.mark.parametrize(
    ("value", "path"),
    [
        (float("nan"), "rateLimit.value"),
        (float("inf"), "rateLimit.value"),
        (float("-inf"), "rateLimit.value"),
        (object(), "rateLimit.value"),
        ("\ud800", "rateLimit.value"),
    ],
)
def test_non_json_values_fail_with_a_safe_path(
    raw_result,
    value,
    path,
):
    raw_result["rateLimit"]["value"] = value
    with pytest.raises(SnapshotNormalizationError) as caught:
        normalize_client_snapshot(raw_result)
    assert caught.value.path == path
    assert caught.value.raw_serializable is False
