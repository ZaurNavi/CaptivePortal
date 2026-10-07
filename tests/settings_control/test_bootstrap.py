import logging
import pytest
from app.settings_control.bootstrap import bootstrap_settings_control
from app.settings_control.models import SettingsError
from . import stack


def test_disabled_no_store_access_or_creation(tmp_path, monkeypatch):
    import app.settings_control.bootstrap as module
    monkeypatch.setattr(module, "SettingsRepository", lambda *_args: pytest.fail("disabled store opened"))
    base = {"settings_db_path": str(tmp_path / "not-created.sqlite3")}
    boot = bootstrap_settings_control(base_settings=base, explicit_environment_names=set(), logger=logging.getLogger("test"))
    assert boot.runtime_settings is base and boot.resolved_snapshot.generation_id is None
    assert boot.store_state == "disabled" and boot.activation_service is None
    assert not (tmp_path / "not-created.sqlite3").exists()


def test_unavailable_parent_fails_closed_and_no_mkdir(tmp_path):
    with pytest.raises(SettingsError, match="settings_store_unavailable"):
        stack(tmp_path, settings_db_path=str(tmp_path / "missing" / "settings.sqlite3"))
    assert not (tmp_path / "missing").exists()


def test_available_invalid_configuration_aborts_not_hidden_fallback(tmp_path):
    with pytest.raises(SettingsError, match="validation_failed"):
        stack(tmp_path, web_admin_device_page_size="bad")
    import sqlite3
    with sqlite3.connect(tmp_path / "settings.sqlite3") as db:
        assert db.execute("SELECT activation_result,safe_error_code FROM settings_activation_events").fetchone() == ("failed", "settings_validation_failed")
