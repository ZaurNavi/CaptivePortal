from __future__ import annotations

import pytest

from app.visitor_registry.config import (
    DEFAULT_LOG_FILE,
    VisitorSnapshotConfig,
    VisitorSnapshotConfigError,
)


VISITOR_SETTING_KEYS = {
    "visitor_snapshot_enabled",
    "visitor_snapshot_log_file",
    "visitor_snapshot_max_workers",
    "visitor_snapshot_max_pending",
    "visitor_snapshot_max_job_age_seconds",
    "visitor_snapshot_request_timeout_seconds",
    "visitor_snapshot_retry_delays_seconds",
    "visitor_snapshot_rotation_max_bytes",
    "visitor_snapshot_rotation_backup_count",
    "visitor_snapshot_shutdown_timeout_seconds",
}


def valid_settings(**overrides):
    settings = {
        "visitor_snapshot_enabled": "true",
        "visitor_snapshot_log_file": "snapshots.log",
        "visitor_snapshot_max_workers": "2",
        "visitor_snapshot_max_pending": "100",
        "visitor_snapshot_max_job_age_seconds": "30",
        "visitor_snapshot_request_timeout_seconds": "5",
        "visitor_snapshot_retry_delays_seconds": "2,5",
        "visitor_snapshot_rotation_max_bytes": "52428800",
        "visitor_snapshot_rotation_backup_count": "20",
        "visitor_snapshot_shutdown_timeout_seconds": "90",
    }
    settings.update(overrides)
    return settings


def test_disabled_is_the_safe_default():
    config = VisitorSnapshotConfig.from_settings({})
    assert config.enabled is False
    assert config.log_file == DEFAULT_LOG_FILE


def test_runtime_settings_expose_every_visitor_snapshot_key():
    from app.settings import get_settings

    actual = get_settings()
    assert VISITOR_SETTING_KEYS <= actual.keys()


def test_disabled_ignores_unused_invalid_settings():
    config = VisitorSnapshotConfig.from_settings({
        "visitor_snapshot_enabled": "false",
        "visitor_snapshot_max_workers": "0",
        "visitor_snapshot_retry_delays_seconds": "broken",
    })
    assert config.enabled is False


def test_valid_configuration_is_parsed():
    config = VisitorSnapshotConfig.from_settings(valid_settings())
    assert config.enabled is True
    assert config.max_workers == 2
    assert config.max_pending == 100
    assert config.total_capacity == 102
    assert config.retry_delays_seconds == (2.0, 5.0)
    assert config.shutdown_timeout_seconds == 90.0


@pytest.mark.parametrize("value", ["", "yes", "1", 1, None])
def test_invalid_enabled_boolean_is_rejected(value):
    with pytest.raises(VisitorSnapshotConfigError):
        VisitorSnapshotConfig.from_settings({
            "visitor_snapshot_enabled": value,
        })


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("visitor_snapshot_log_file", ""),
        ("visitor_snapshot_max_workers", 0),
        ("visitor_snapshot_max_workers", -1),
        ("visitor_snapshot_max_pending", -1),
        ("visitor_snapshot_max_job_age_seconds", 0),
        ("visitor_snapshot_request_timeout_seconds", 0),
        ("visitor_snapshot_rotation_max_bytes", 0),
        ("visitor_snapshot_rotation_backup_count", 0),
        ("visitor_snapshot_shutdown_timeout_seconds", 0),
    ],
)
def test_invalid_enabled_configuration_is_rejected(field, value):
    with pytest.raises(VisitorSnapshotConfigError):
        VisitorSnapshotConfig.from_settings(
            valid_settings(**{field: value})
        )


@pytest.mark.parametrize(
    "value",
    ["", "1", "1,2,3", "a,2", "-1,2", "nan,2", "inf,2"],
)
def test_retry_delays_require_two_finite_non_negative_numbers(value):
    with pytest.raises(VisitorSnapshotConfigError):
        VisitorSnapshotConfig.from_settings(
            valid_settings(
                visitor_snapshot_retry_delays_seconds=value
            )
        )


def test_zero_retry_delay_is_allowed():
    config = VisitorSnapshotConfig.from_settings(
        valid_settings(
            visitor_snapshot_retry_delays_seconds="0,0"
        )
    )
    assert config.retry_delays_seconds == (0.0, 0.0)
