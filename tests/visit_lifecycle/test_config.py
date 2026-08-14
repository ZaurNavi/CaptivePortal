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
