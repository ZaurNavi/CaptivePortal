from __future__ import annotations

import json
from pathlib import Path

from app.observations.ap_normalizer import (
    build_ap_config,
    canonical_ap_mac,
    normalize_ap_lan,
    normalize_ap_overview,
    normalize_ap_radios,
    normalize_ap_wired,
)


FIXTURES = Path(__file__).parent / "fixtures" / "omada"


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))["result"]


def safe_override():
    value = fixture("11_override_v2.json")
    for item in value["ssidOverrides"]:
        item.pop("ssidPassword", None)
    return value


def config_sections():
    return {
        "general_config": fixture("06_general_config.json"),
        "ip_setting": fixture("07_ip_setting.json"),
        "radio_config": fixture("08_radio_config.json"),
        "ofdma": fixture("09_ofdma.json"),
        "available_channels": fixture("10_available_channel.json"),
        "safe_overrides": safe_override(),
        "rf_scan_state": fixture("12_rf_scan_result_v2.json"),
    }


def test_inventory_and_dynamic_authoritative_shapes_normalize():
    inventory = fixture("01_devices.json")["data"][0]
    assert canonical_ap_mac(inventory) == "02:00:00:00:00:01"

    overview = normalize_ap_overview(fixture("02_ap_overview.json"))
    assert overview["wlan_id"] == 1
    assert overview["uptime_seconds"] == 1570998
    assert "wlan_id" not in normalize_ap_overview({"wlanId": "9" * 1000})

    wired = normalize_ap_wired(fixture("03_wired_uplink.json"))
    assert wired["wired_rate_raw"] == 1000
    assert wired["wired_down_bytes"] == 245897982444
    assert normalize_ap_wired({"wiredUplink": {"rate": "1000.5"}})["wired_rate_raw"] == 1000.5
    assert "wired_rate_raw" not in normalize_ap_wired({"wiredUplink": {"rate": "fast"}})

    lan = normalize_ap_lan(fixture("04_lan_traffic_info.json"))
    assert lan["lan_rx_bytes"] == 245897982444
    assert lan["lan_tx_error_packets"] == 0

    radios = normalize_ap_radios(fixture("05_radios.json"))
    assert [row["band"] for row in radios] == ["2g", "5g"]
    assert radios[0]["radio_id"] is None
    assert radios[0]["actual_channel"] == 11
    assert radios[1]["frequency_mhz"] == 5320

    fallback = fixture("05_radios.json")
    fallback["wp2g"]["actualChannel"] = "controller-specific"
    fallback_rows = normalize_ap_radios(fallback)
    assert fallback_rows[0]["actual_channel_raw"] == "controller-specific"
    assert "actual_channel" not in fallback_rows[0]
    assert "frequency_mhz" not in fallback_rows[0]


def test_unknown_dynamic_fields_are_not_persisted_and_bad_types_drop():
    overview = normalize_ap_overview({
        "name": " AP ",
        "cpuUtil": "one",
        "token": "TEST_ACCESS_TOKEN_SHOULD_NOT_LEAK",
    })
    assert overview == {"name": "AP"}
    assert normalize_ap_wired({"wiredUplink": []}) is None
    assert normalize_ap_lan({"lanTraffic": None}) is None


def test_complete_config_is_canonical_stable_and_secret_free():
    first = build_ap_config(config_sections())
    second = build_ap_config(dict(reversed(tuple(config_sections().items()))))
    assert first is not None
    assert second is not None
    assert first.config_json == second.config_json
    assert first.sha256 == second.sha256
    assert "TEST_WIFI_PASSWORD_SHOULD_NOT_LEAK" not in first.config_json
    parsed = json.loads(first.config_json)
    assert parsed["general"]["location"] == {}
    assert parsed["available_channels"][0]["radio_id"] == 0
    assert parsed["rf_scan"]["status5g2"] == 1


def test_valid_empty_config_sections_remain_complete():
    sections = config_sections()
    sections["available_channels"] = []
    sections["safe_overrides"] = {"ssidOverrides": []}
    sections["rf_scan_state"] = None
    result = build_ap_config(sections)
    assert result is not None
    parsed = json.loads(result.config_json)
    assert parsed["available_channels"] == []
    assert parsed["overrides"] == []
    assert parsed["rf_scan"] is None


def test_partial_unsafe_or_secret_config_never_hashes():
    missing = config_sections()
    missing.pop("ofdma")
    assert build_ap_config(missing) is None

    password = config_sections()
    password["safe_overrides"]["ssidOverrides"][0]["ssidPassword"] = (
        "TEST_WIFI_PASSWORD_SHOULD_NOT_LEAK"
    )
    assert build_ap_config(password) is None

    too_deep = config_sections()
    nested = {}
    cursor = nested
    for _ in range(10):
        cursor["child"] = {}
        cursor = cursor["child"]
    too_deep["general_config"]["unknown"] = nested
    assert build_ap_config(too_deep) is None

    too_long = config_sections()
    too_long["general_config"]["unknown"] = "x" * 4097
    assert build_ap_config(too_long) is None


def test_unknown_nested_config_keys_are_dropped():
    sections = config_sections()
    sections["ip_setting"]["dhcpIpSetting"]["unknownSecret"] = "drop"
    sections["radio_config"]["radioSetting5g"]["unknown"] = {"deep": "drop"}
    result = build_ap_config(sections)
    assert result is not None
    assert "unknownSecret" not in result.config_json
    assert '"unknown"' not in result.config_json


def test_known_config_paths_reject_unconfirmed_types():
    sections = config_sections()
    sections["ip_setting"]["dhcpIpSetting"]["fallback"] = "true"
    assert build_ap_config(sections) is None

    sections = config_sections()
    sections["radio_config"]["radioSetting2g"]["txPower"] = "20"
    assert build_ap_config(sections) is None

    sections = config_sections()
    sections["safe_overrides"]["ssidOverrides"][0]["vlanEnable"] = 0
    assert build_ap_config(sections) is None
