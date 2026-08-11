from __future__ import annotations

from pathlib import Path

import pytest

from app.observations.config import observation_config_from_settings
from app.observations.models import ObservationConfigError
from app.settings import get_settings


def enabled_settings(tmp_path: Path, **updates) -> dict:
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
    }
    values.update(updates)
    return values


def test_master_default_is_disabled_and_exported_by_settings():
    settings = get_settings()
    assert settings["observation_foundation_enabled"] == "false"
    assert settings["observation_db_path"] == (
        "/opt/CaptivePortal/data/observations.sqlite3"
    )


def test_disabled_config_does_not_validate_runtime_path():
    config = observation_config_from_settings({
        "observation_foundation_enabled": "false",
        "observation_db_path": "relative-is-unused.sqlite3",
        "observation_cleanup_batch_size": "invalid-while-disabled",
    })
    assert config.enabled is False
    assert config.cleanup_batch_size == 5000


def test_valid_enabled_config(tmp_path: Path):
    config = observation_config_from_settings(enabled_settings(tmp_path))
    assert config.enabled is True
    assert config.dynamic_retention_days == 180
    assert config.config_retention_days == 730
    assert config.cleanup_batch_size == 5000


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("observation_foundation_enabled", "yes"),
        ("observation_db_path", "relative.sqlite3"),
        ("observation_dynamic_retention_days", "0"),
        ("observation_config_retention_days", "-1"),
        ("observation_cleanup_initial_delay_seconds", "0"),
        ("observation_cleanup_interval_seconds", "nan"),
        ("observation_cleanup_batch_size", "100001"),
        ("observation_cleanup_max_duration_seconds", "inf"),
        ("observation_shutdown_timeout_seconds", True),
    ],
)
def test_invalid_enabled_config_is_localized(
    tmp_path: Path,
    key: str,
    value: object,
):
    with pytest.raises(ObservationConfigError):
        observation_config_from_settings(
            enabled_settings(tmp_path, **{key: value})
        )


def test_env_example_keeps_foundation_disabled_and_has_no_site_values():
    example = (Path(__file__).parents[2] / ".env.example").read_text(
        encoding="utf-8"
    )
    assert "OBSERVATION_FOUNDATION_ENABLED=false" in example
    assert "OBSERVATION_SITE_IDS=" not in example
    assert "OBSERVATION_CLIENT_SSIDS=" not in example
