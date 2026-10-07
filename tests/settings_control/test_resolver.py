import pytest
from app.settings_control.resolver import resolve_settings
from app.settings_control.models import SettingsError
from . import CONTROLLER_BASE


def test_override_environment_default_and_clear():
    key = "WEB_ADMIN_DEVICE_PAGE_SIZE"
    base = {**CONTROLLER_BASE, key.lower(): "125"}
    env = {key}
    override = resolve_settings(base, env, {key: 150}, 1)
    assert override.values[key.lower()] == 150
    assert override.base_value_by_key[key] == 125 and override.base_source_by_key[key] == "environment"
    cleared = resolve_settings(base, env, {}, 2)
    assert cleared.values[key.lower()] == 125 and cleared.persisted_override_by_key[key] is None
    default = resolve_settings(CONTROLLER_BASE, {}, {}, 0)
    assert default.values[key.lower()] == 100 and default.base_source_by_key[key] == "repository_default"
    with pytest.raises(TypeError):
        default.values[key.lower()] = 42


@pytest.mark.parametrize("value", [True, "not-int", 1.2, None])
def test_invalid_explicit_environment_not_replaced(value):
    with pytest.raises(SettingsError):
        resolve_settings({"web_admin_device_page_size": value}, {"WEB_ADMIN_DEVICE_PAGE_SIZE"}, {"WEB_ADMIN_DEVICE_PAGE_SIZE": 100}, 1)
