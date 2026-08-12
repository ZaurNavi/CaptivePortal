from __future__ import annotations

from pathlib import Path

import pytest

from app.observations.config import observation_config_from_settings
from app.observations.models import ObservationConfigError
from app.settings import get_settings


def values(tmp_path: Path, **updates):
    result = {
        "observation_foundation_enabled": "true",
        "observation_db_path": str(tmp_path / "observations.sqlite3"),
        "observation_client_enabled": "false",
        "observation_ap_enabled": "true",
        "observation_site_ids": "site-a,site-b",
        "observation_request_timeout_seconds": "5",
        "observation_ap_initial_delay_seconds": "10",
        "observation_ap_interval_seconds": "30",
        "observation_ap_inventory_interval_seconds": "300",
        "observation_ap_inventory_max_stale_seconds": "900",
        "observation_ap_config_interval_seconds": "21600",
        "observation_ap_page_size": "100",
        "observation_ap_max_pages": "10",
        "observation_ap_max_rows": "500",
        "observation_ap_dynamic_max_requests_per_cycle": "200",
        "observation_ap_config_max_requests_per_cycle": "200",
        "observation_ap_cycle_max_duration_seconds": "120",
        "observation_ap_config_cycle_max_duration_seconds": "180",
        "observation_rate_max_gap_seconds": "180",
    }
    result.update(updates)
    return result


def test_ap_defaults_are_exported_but_master_is_disabled():
    settings = get_settings()
    assert settings["observation_foundation_enabled"] == "false"
    assert settings["observation_ap_enabled"] == "true"
    assert settings["observation_ap_page_size"] == "100"
    assert settings["observation_rate_max_gap_seconds"] == "180"


def test_ap_config_parses_complete_contract(tmp_path):
    config = observation_config_from_settings(values(tmp_path))
    assert config.client_enabled is False
    assert config.ap_enabled is True
    assert config.site_ids == ("site-a", "site-b")
    assert config.ap_inventory_max_stale_seconds == 900
    assert config.ap_dynamic_max_requests_per_cycle == 200
    assert config.rate_max_gap_seconds == 180


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("observation_ap_enabled", "yes"),
        ("observation_site_ids", ""),
        ("observation_request_timeout_seconds", "61"),
        ("observation_ap_page_size", "101"),
        ("observation_ap_max_pages", "0"),
        ("observation_ap_max_rows", "10001"),
        ("observation_ap_dynamic_max_requests_per_cycle", "0"),
        ("observation_ap_config_max_requests_per_cycle", "10001"),
        ("observation_ap_cycle_max_duration_seconds", "nan"),
        ("observation_ap_inventory_max_stale_seconds", "299"),
        ("observation_rate_max_gap_seconds", "149"),
    ],
)
def test_invalid_ap_config_is_localized(tmp_path, key, value):
    with pytest.raises(ObservationConfigError):
        observation_config_from_settings(values(tmp_path, **{key: value}))


def test_disabled_ap_does_not_validate_ap_only_values(tmp_path):
    config = observation_config_from_settings(values(
        tmp_path,
        observation_client_enabled="true",
        observation_ap_enabled="false",
        observation_ap_page_size="invalid",
    ))
    assert config.client_enabled is True
    assert config.ap_enabled is False
    assert config.ap_page_size == 100


def test_enabled_master_requires_at_least_one_collector(tmp_path):
    with pytest.raises(ObservationConfigError):
        observation_config_from_settings(values(
            tmp_path,
            observation_client_enabled="false",
            observation_ap_enabled="false",
        ))
