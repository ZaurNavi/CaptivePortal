from __future__ import annotations

import pytest

from app.analytics.api_config import (
    AnalyticsApiConfigError,
    analytics_api_config_from_settings,
)
from app.settings import get_settings


SITE = "0123456789abcdef01234567"


def _enabled(**overrides):
    settings = {
        "analytics_api_enabled": "true",
        "analytics_api_bearer_token": "x" * 32,
        "analytics_api_allowed_networks": "127.0.0.1/32,::1/128",
        "analytics_api_allowed_site_ids": SITE,
    }
    settings.update(overrides)
    return settings


def test_api_config_defaults_are_disabled_and_loopback_only():
    config = analytics_api_config_from_settings({})
    assert config.enabled is False
    assert tuple(str(item) for item in config.allowed_networks) == (
        "127.0.0.1/32", "::1/128",
    )
    assert config.allowed_site_ids == frozenset()
    assert config.max_concurrent_requests == 2
    assert config.max_response_bytes == 1_048_576


@pytest.mark.parametrize("value", ["TRUE", "False", "1", 1, None])
def test_api_boolean_is_exact(value):
    with pytest.raises(AnalyticsApiConfigError):
        analytics_api_config_from_settings({"analytics_api_enabled": value})


@pytest.mark.parametrize("token", ["", " ", "short", 1])
def test_enabled_api_requires_strong_string_token(token):
    with pytest.raises(AnalyticsApiConfigError) as caught:
        analytics_api_config_from_settings(
            _enabled(analytics_api_bearer_token=token)
        )
    if isinstance(token, str) and len(token) >= 4:
        assert token not in str(caught.value)


def test_config_parses_ipv4_ipv6_and_canonical_sites():
    config = analytics_api_config_from_settings(_enabled())
    assert config.allowed_site_ids == frozenset({SITE})
    assert {item.version for item in config.allowed_networks} == {4, 6}


@pytest.mark.parametrize(
    "value",
    ["", "127.0.0.1", "127.0.0.0/33", "127.0.0.1/32,", "bad/24"],
)
def test_invalid_or_empty_network_list_is_rejected(value):
    with pytest.raises(AnalyticsApiConfigError):
        analytics_api_config_from_settings(
            _enabled(analytics_api_allowed_networks=value)
        )


@pytest.mark.parametrize("value", ["", "site-a", "A" * 24, f"{SITE},"])
def test_invalid_or_empty_site_allowlist_is_rejected(value):
    with pytest.raises(AnalyticsApiConfigError):
        analytics_api_config_from_settings(
            _enabled(analytics_api_allowed_site_ids=value)
        )


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("analytics_api_max_concurrent_requests", "0"),
        ("analytics_api_max_concurrent_requests", "9"),
        ("analytics_api_max_response_bytes", "65535"),
        ("analytics_api_max_response_bytes", "4194305"),
    ],
)
def test_resource_bounds_are_enforced(name, value):
    with pytest.raises(AnalyticsApiConfigError):
        analytics_api_config_from_settings(_enabled(**{name: value}))


def test_secret_is_absent_from_repr_and_validation_error():
    secret = "top-secret-credential-that-must-never-leak"
    config = analytics_api_config_from_settings(
        _enabled(analytics_api_bearer_token=secret)
    )
    assert secret not in repr(config)
    with pytest.raises(AnalyticsApiConfigError) as caught:
        analytics_api_config_from_settings(
            _enabled(
                analytics_api_bearer_token=secret,
                analytics_api_max_response_bytes="bad",
            )
        )
    assert secret not in str(caught.value)


def test_settings_export_all_analytics_and_api_inputs():
    settings = get_settings()
    expected = {
        "analytics_foundation_enabled",
        "analytics_wireless_enabled",
        "analytics_visit_enabled",
        "analytics_default_limit",
        "analytics_max_limit",
        "analytics_max_query_window_days",
        "analytics_max_query_duration_seconds",
        "analytics_quality_gap_threshold_seconds",
        "analytics_wireless_min_samples",
        "analytics_wireless_max_window_days",
        "analytics_counter_max_gap_seconds",
        "analytics_ap_join_max_lag_seconds",
        "analytics_rssi_threshold_dbm",
        "analytics_snr_threshold_db",
        "analytics_visit_min_cohort_size",
        "analytics_visit_max_window_days",
        "analytics_api_enabled",
        "analytics_api_bearer_token",
        "analytics_api_allowed_networks",
        "analytics_api_allowed_site_ids",
        "analytics_api_max_concurrent_requests",
        "analytics_api_max_response_bytes",
    }
    assert expected <= settings.keys()
