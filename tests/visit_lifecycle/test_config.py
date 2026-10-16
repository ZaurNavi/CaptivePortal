from __future__ import annotations

import pytest

from app.visit_lifecycle import VisitLifecycleConfigError
from app.visit_lifecycle.config import visit_config_from_settings


def test_disabled_is_safe_default_and_does_not_parse_other_values():
    config = visit_config_from_settings({})
    assert config.enabled is False
    assert config.db_path == "/opt/CaptivePortal/data/visits.sqlite3"
    assert config.reader_scan_telemetry_compact_enabled is False


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


@pytest.mark.parametrize("value,expected", [(True, True), (False, False), ("true", True), ("false", False)])
def test_compact_flag_uses_existing_strict_boolean_parser(value, expected):
    config = visit_config_from_settings({"visit_lifecycle_enabled": True,
        "visit_lifecycle_reader_scan_telemetry_compact_enabled": value})
    assert config.reader_scan_telemetry_compact_enabled is expected


@pytest.mark.parametrize("value", [None, 0, 1, "", "1", "0", "yes", "on", [], {}])
def test_compact_invalid_boolean_rejected(value):
    with pytest.raises(VisitLifecycleConfigError, match="VISIT_LIFECYCLE_READER_SCAN_TELEMETRY_COMPACT_ENABLED"):
        visit_config_from_settings({"visit_lifecycle_enabled": True,
            "visit_lifecycle_reader_scan_telemetry_compact_enabled": value})


def test_enabled_compact_default_is_off_and_constructor_remains_compatible(visit_config):
    from dataclasses import asdict
    from app.visit_lifecycle.models import VisitLifecycleConfig
    assert visit_config_from_settings({"visit_lifecycle_enabled": True}).reader_scan_telemetry_compact_enabled is False
    legacy = asdict(visit_config)
    del legacy["reader_scan_telemetry_compact_enabled"]
    assert VisitLifecycleConfig(**legacy).reader_scan_telemetry_compact_enabled is False


@pytest.mark.parametrize("env_value,expected", [(None, False), ("false", False), ("true", True), ("invalid", None)])
def test_compact_environment_to_settings_to_config_route(monkeypatch, env_value, expected):
    import json
    import subprocess
    import sys
    from pathlib import Path
    name = "VISIT_LIFECYCLE_READER_SCAN_TELEMETRY_COMPACT_ENABLED"
    monkeypatch.setenv("VISIT_LIFECYCLE_ENABLED", "true")
    monkeypatch.delenv(name, raising=False)
    if env_value is not None:
        monkeypatch.setenv(name, env_value)
    program = (
        "import json; from app.settings import get_settings; "
        "from app.visit_lifecycle.config import visit_config_from_settings; "
        "print(json.dumps(visit_config_from_settings(get_settings()).reader_scan_telemetry_compact_enabled))"
    )
    result = subprocess.run([sys.executable, "-c", program], cwd=Path(__file__).resolve().parents[2],
                            capture_output=True, text=True, timeout=20)
    if expected is None:
        assert result.returncode != 0 and name in result.stderr
    else:
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) is expected
