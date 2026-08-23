from __future__ import annotations

import pytest

from app.current_state.config import current_state_config_from_settings
from app.current_state.models import CurrentStateConfigError

from .conftest import SITE


def test_disabled_default_is_safe():
    config = current_state_config_from_settings({})
    assert config.enabled is False
    assert config.client_interval_seconds == 60
    assert config.ap_interval_seconds == 60
    assert config.db_path.endswith("current_state.sqlite3")


def test_disabled_component_ignores_dormant_invalid_settings():
    config = current_state_config_from_settings({
        "current_state_enabled": "false",
        "current_state_db_path": object(),
        "current_state_client_interval_seconds": "not-a-number",
        "current_state_site_ids": "not-a-site",
        "current_state_client_ssids_json": "not-json",
    })
    assert config.enabled is False
    assert config.db_path.endswith("current_state.sqlite3")
    assert config.client_interval_seconds == 60


def test_enabled_exact_scope_and_defaults(enabled_settings):
    config = current_state_config_from_settings(enabled_settings)
    assert config.site_ids == (SITE,)
    assert config.client_ssids == ("Zefer_Parki",)
    assert config.history_retention_hours == 48
    assert config.history_max_client_rows == 5_000_000


@pytest.mark.parametrize("value", ["", "ABC", "A" * 24, "a" * 23, "a" * 25, f"{SITE},{SITE}"])
def test_invalid_or_duplicate_site_rejected(enabled_settings, value):
    enabled_settings["current_state_site_ids"] = value
    with pytest.raises(CurrentStateConfigError):
        current_state_config_from_settings(enabled_settings)


@pytest.mark.parametrize("value", ["", "{}", "null", "[1]", '[""]', '["x","x"]', "[NaN]"])
def test_invalid_ssid_json_rejected(enabled_settings, value):
    enabled_settings["current_state_client_ssids_json"] = value
    with pytest.raises(CurrentStateConfigError):
        current_state_config_from_settings(enabled_settings)


@pytest.mark.parametrize("ssid", ["x" * 33, "bad\x00ssid", "\ud800"])
def test_unsafe_or_overlong_ssid_rejected(enabled_settings, ssid):
    import json
    enabled_settings["current_state_client_ssids_json"] = json.dumps([ssid])
    with pytest.raises(CurrentStateConfigError):
        current_state_config_from_settings(enabled_settings)


def test_ssid_json_is_lossless_for_spaces_commas_and_case(enabled_settings):
    enabled_settings["current_state_client_ssids_json"] = '["Lobby WiFi","VIP,Guests","  LeadingSpace","Case"]'
    config = current_state_config_from_settings(enabled_settings)
    assert config.client_ssids == ("Lobby WiFi", "VIP,Guests", "  LeadingSpace", "Case")
    assert "case" not in config.client_ssids


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("current_state_client_interval_seconds", "9"),
        ("current_state_ap_interval_seconds", "601"),
        ("current_state_request_timeout_seconds", "0"),
        ("current_state_client_page_size", "501"),
        ("current_state_client_max_pages", "101"),
        ("current_state_client_max_rows", "50001"),
        ("current_state_ap_page_size", "101"),
        ("current_state_ap_max_rows", "5001"),
        ("current_state_history_retention_hours", "23"),
        ("current_state_history_max_client_rows", "99999"),
        ("current_state_cleanup_max_cycles_per_run", "0"),
        ("current_state_cleanup_max_rows_per_transaction", "1000001"),
        ("current_state_sqlite_busy_timeout_ms", "5001"),
        ("current_state_shutdown_timeout_seconds", "0"),
    ],
)
def test_numeric_bounds_rejected(enabled_settings, key, value):
    enabled_settings[key] = value
    with pytest.raises(CurrentStateConfigError):
        current_state_config_from_settings(enabled_settings)


def test_stale_must_exceed_fresh(enabled_settings):
    enabled_settings["current_state_client_fresh_max_age_seconds"] = "60"
    enabled_settings["current_state_client_stale_max_age_seconds"] = "60"
    with pytest.raises(CurrentStateConfigError):
        current_state_config_from_settings(enabled_settings)


def test_safe_repr_does_not_expose_ssids(config):
    assert "Zefer_Parki" not in repr(config)
    assert "ssid_count=1" in repr(config)
