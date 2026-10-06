from dataclasses import replace
import pytest
from app.settings_control.resolver import resolve_settings
from app.settings_control.validation import SettingsValidationService
from app.settings_control.models import SettingsError
import app.settings_control.validation as validators


@pytest.mark.parametrize("value", [True, 0, 501, 1.5, "100"])
def test_primitive_validation_even_when_disabled(value):
    snapshot = resolve_settings({}, {}, {}, 0)
    snapshot = replace(snapshot, values={**snapshot.values, "web_admin_device_page_size": value})
    with pytest.raises(SettingsError, match="validation_failed"):
        SettingsValidationService().validate(snapshot)


def test_existing_semantic_authorities_called(monkeypatch):
    calls = []
    for name in ("admin_web", "home_activity", "home_health", "home_ap_24h"):
        function = getattr(validators, name + "_config_from_settings")
        def wrapper(*args, _name=name, _function=function, **kwargs):
            calls.append(_name)
            return _function(*args, **kwargs)
        monkeypatch.setattr(validators, name + "_config_from_settings", wrapper)
    SettingsValidationService().validate(resolve_settings({}, {}, {}, 0))
    assert calls == ["admin_web", "home_activity", "home_health", "home_ap_24h"]


def test_cross_setting_validation_remains_authoritative():
    from tests.admin_web.conftest import enabled_settings
    snapshot = resolve_settings(enabled_settings(web_admin_home_live_request_timeout_seconds="5"), {}, {}, 0)
    with pytest.raises(SettingsError, match="validation_failed"):
        SettingsValidationService().validate(snapshot)
