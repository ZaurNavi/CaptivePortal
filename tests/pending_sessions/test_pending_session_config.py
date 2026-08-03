import pytest

from app.pending_sessions import PendingSessionCleanerConfig
from app.pending_sessions.config import (
    parse_bool,
    parse_float_list_strict,
    parse_float_strict,
    parse_int_strict,
    parse_ssid_list_strict,
)


def enabled_settings(**overrides):
    settings = {
        "pending_session_cleaner_enabled": "true",
        "capport_site_id": "site-1",
        "pending_session_cleaner_ssids": "Guest,Park WiFi",
        "pending_session_cleaner_initial_delay_seconds": "10",
        "pending_session_cleaner_scan_interval_seconds": "60",
        "pending_session_cleaner_max_scan_duration_seconds": "50",
        "pending_session_cleaner_min_uptime_seconds": "120",
        "pending_session_cleaner_portal_grace_seconds": "45",
        "pending_session_cleaner_uptime_regression_tolerance_seconds": "5",
        "pending_session_cleaner_request_timeout_seconds": "5",
        "pending_session_cleaner_get_retry_delays_seconds": "1,3",
        "pending_session_cleaner_verify_delays_seconds": "1,4",
        "pending_session_cleaner_page_size": "500",
        "pending_session_cleaner_max_pages": "20",
        "pending_session_cleaner_max_clients": "10000",
        "pending_session_cleaner_max_actions_per_scan": "1",
        "pending_session_cleaner_action_cooldown_seconds": "180",
        "pending_session_cleaner_max_actions_per_mac_per_hour": "3",
        "pending_session_cleaner_log_file": "/opt/CaptivePortal/logs/pending_session_cleaner.log",
        "pending_session_cleaner_rotation_max_bytes": "52428800",
        "pending_session_cleaner_rotation_backup_count": "20",
        "pending_session_cleaner_shutdown_timeout_seconds": "20",
    }
    settings.update(overrides)
    return settings


def test_disabled_by_default_ignores_unrelated_invalid_values():
    config = PendingSessionCleanerConfig.from_settings(
        {"pending_session_cleaner_page_size": "not-an-int"}
    )

    assert config.enabled is False
    assert config.site_id is None
    assert config.ssids == ()
    assert config.max_actions_per_scan == 1


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (True, True),
        (False, False),
        ("true", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("false", False),
        ("0", False),
        ("no", False),
        ("off", False),
    ],
)
def test_parse_bool_accepts_only_explicit_values(raw, expected):
    assert parse_bool(raw, name="flag") is expected


@pytest.mark.parametrize("raw", [None, 1, 0, "enabled", "", "maybe"])
def test_parse_bool_rejects_ambiguous_values(raw):
    with pytest.raises(ValueError):
        parse_bool(raw, name="flag")


def test_enabled_configuration_is_strictly_parsed():
    config = PendingSessionCleanerConfig.from_settings(enabled_settings())

    assert config.enabled is True
    assert config.site_id == "site-1"
    assert config.ssids == ("Guest", "Park WiFi")
    assert config.get_retry_delays_seconds == (1.0, 3.0)
    assert config.verify_delays_seconds == (1.0, 4.0)
    assert config.page_size == 500
    assert config.max_clients == 10000


@pytest.mark.parametrize(
    "overrides",
    [
        {"capport_site_id": ""},
        {"pending_session_cleaner_ssids": "Guest,"},
        {"pending_session_cleaner_scan_interval_seconds": "0"},
        {"pending_session_cleaner_request_timeout_seconds": "nan"},
        {"pending_session_cleaner_page_size": True},
        {"pending_session_cleaner_get_retry_delays_seconds": "1"},
        {"pending_session_cleaner_verify_delays_seconds": "1,2,3"},
        {"pending_session_cleaner_log_file": "relative/path.log"},
        {"pending_session_cleaner_shutdown_timeout_seconds": "-1"},
    ],
)
def test_enabled_configuration_rejects_invalid_values(overrides):
    with pytest.raises(ValueError):
        PendingSessionCleanerConfig.from_settings(enabled_settings(**overrides))


def test_strict_scalar_parsers_reject_bool_and_non_finite_values():
    with pytest.raises(ValueError):
        parse_int_strict(True, name="count")
    with pytest.raises(ValueError):
        parse_float_strict(False, name="seconds")
    with pytest.raises(ValueError):
        parse_float_strict("inf", name="seconds")


def test_list_parsers_reject_empty_or_negative_elements():
    with pytest.raises(ValueError):
        parse_float_list_strict("1,,3", name="delays")
    with pytest.raises(ValueError):
        parse_float_list_strict("1,-1", name="delays")
    with pytest.raises(ValueError):
        parse_ssid_list_strict("Guest, ", name="ssids")
