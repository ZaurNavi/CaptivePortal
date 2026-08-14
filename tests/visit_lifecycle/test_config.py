from __future__ import annotations

import pytest

from app.visit_lifecycle import VisitLifecycleConfigError
from app.visit_lifecycle.config import visit_config_from_settings


def test_disabled_is_safe_default_and_does_not_parse_other_values():
    config = visit_config_from_settings({})
    assert config.enabled is False
    assert config.db_path == "/opt/CaptivePortal/data/visits.sqlite3"


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("visit_lifecycle_db_path", "relative.sqlite3"),
        ("visit_lifecycle_reconcile_interval_seconds", 0),
        ("visit_lifecycle_reconcile_batch_size", -1),
        ("visit_lifecycle_start_busy_timeout_ms", 60_001),
        ("visit_lifecycle_start_writer_slot_wait_ms", 60_001),
        ("visit_lifecycle_reader_writer_slot_wait_ms", 0),
        ("visit_lifecycle_reconciliation_writer_slot_wait_ms", -1),
        ("visit_lifecycle_sqlite_busy_timeout_ms", 60_001),
        ("visit_lifecycle_start_max_attempts", 11),
        ("visit_lifecycle_start_total_budget_ms", 0),
        ("visit_lifecycle_scan_interval_seconds", float("inf")),
    ],
)
def test_enabled_invalid_configuration_fails_component_only(key, value):
    settings = {"visit_lifecycle_enabled": True, key: value}
    with pytest.raises(VisitLifecycleConfigError):
        visit_config_from_settings(settings)


def test_strict_boolean_contract():
    assert visit_config_from_settings(
        {"visit_lifecycle_enabled": "true"}
    ).enabled is True
    with pytest.raises(VisitLifecycleConfigError):
        visit_config_from_settings({"visit_lifecycle_enabled": "yes"})


def test_writer_contention_defaults_are_explicit_and_separate():
    config = visit_config_from_settings({"visit_lifecycle_enabled": True})
    assert config.start_writer_slot_wait_ms == 750
    assert config.reader_writer_slot_wait_ms == 250
    assert config.reconciliation_writer_slot_wait_ms == 250
    assert config.sqlite_busy_timeout_ms == 500
    assert config.start_max_attempts == 3
    assert config.start_total_budget_ms == 2_000


def test_new_start_slot_setting_wins_and_legacy_alias_is_supported():
    legacy = visit_config_from_settings({
        "visit_lifecycle_enabled": True,
        "visit_lifecycle_start_busy_timeout_ms": "321",
    })
    preferred = visit_config_from_settings({
        "visit_lifecycle_enabled": True,
        "visit_lifecycle_start_busy_timeout_ms": "321",
        "visit_lifecycle_start_writer_slot_wait_ms": "654",
    })
    assert legacy.start_writer_slot_wait_ms == 321
    assert preferred.start_writer_slot_wait_ms == 654
