from __future__ import annotations

from pathlib import Path

import pytest

from app.observations.config import observation_config_from_settings
from app.observations.models import ObservationConfigError
from app.settings import get_settings


def settings(tmp_path: Path, **updates):
    values = {
        "observation_foundation_enabled": "true",
        "observation_db_path": str(tmp_path / "observations.sqlite3"),
        "observation_dynamic_retention_days": "180",
        "observation_config_retention_days": "730",
        "observation_cleanup_initial_delay_seconds": "900",
        "observation_cleanup_interval_seconds": "86400",
        "observation_cleanup_batch_size": "5000",
        "observation_cleanup_max_duration_seconds": "30",
        "observation_shutdown_timeout_seconds": "20",
        "observation_client_enabled": "true",
        "observation_site_ids": " site-a,site-b,site-a ",
        "observation_client_ssids": "Zefer_Parki, Guest ,Zefer_Parki",
        "observation_client_initial_delay_seconds": "15",
        "observation_client_interval_seconds": "60",
        "observation_request_timeout_seconds": "5",
        "observation_client_page_size": "500",
        "observation_client_max_pages": "20",
        "observation_client_max_rows": "10000",
    }
    values.update(updates)
    return values


def test_client_defaults_are_exported_but_foundation_stays_disabled():
    current = get_settings()
    assert current["observation_foundation_enabled"] == "false"
    assert current["observation_client_enabled"] == "true"
    assert current["observation_client_page_size"] == "500"


def test_enabled_client_config_parses_csv_and_bounds(tmp_path):
    config = observation_config_from_settings(settings(tmp_path))
    assert config.client_enabled is True
    assert config.site_ids == ("site-a", "site-b")
    assert config.client_ssids == ("Zefer_Parki", "Guest")
    assert config.client_initial_delay_seconds == 15.0
    assert config.client_interval_seconds == 60.0
    assert config.request_timeout_seconds == 5.0
    assert config.client_page_size == 500
    assert config.client_max_pages == 20
    assert config.client_max_rows == 10_000


def test_empty_ssid_means_all_and_disabled_client_needs_no_sites(tmp_path):
    all_ssids = observation_config_from_settings(
        settings(tmp_path, observation_client_ssids="")
    )
    assert all_ssids.client_ssids == ()

    disabled = observation_config_from_settings(settings(
        tmp_path,
        observation_client_enabled="false",
        observation_site_ids="",
        observation_client_page_size="invalid-while-disabled",
    ))
    assert disabled.client_enabled is False
    assert disabled.site_ids == ()


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("observation_client_enabled", "yes"),
        ("observation_site_ids", ""),
        ("observation_site_ids", "site-a,,site-b"),
        ("observation_client_ssids", "one,"),
        ("observation_client_initial_delay_seconds", True),
        ("observation_client_interval_seconds", "nan"),
        ("observation_request_timeout_seconds", "61"),
        ("observation_client_page_size", "501"),
        ("observation_client_max_pages", "21"),
        ("observation_client_max_rows", "10001"),
    ],
)
def test_invalid_client_config_is_localized(tmp_path, key, value):
    with pytest.raises(ObservationConfigError):
        observation_config_from_settings(settings(tmp_path, **{key: value}))


def test_master_disabled_does_not_validate_client_values():
    config = observation_config_from_settings({
        "observation_foundation_enabled": "false",
        "observation_client_enabled": "invalid",
        "observation_site_ids": ",",
    })
    assert config.enabled is False
    assert config.client_enabled is False
