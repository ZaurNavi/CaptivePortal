from dataclasses import replace
import pytest
from app.settings_control.resolver import resolve_settings
from app.settings_control.validation import SettingsValidationService
from app.settings_control.models import SettingsError
from app.settings_control.controller_secret import OmadaClientSecretResolution
import app.settings_control.validation as validators
from . import CONTROLLER_BASE


def snapshot_with_secret_resolution(**values):
    base = {key: value for key, value in CONTROLLER_BASE.items() if key != "client_secret"}
    base.update(values)
    return resolve_settings(base, {}, {}, 0), OmadaClientSecretResolution("synthetic-secret", "repository_default", 0)


@pytest.mark.parametrize("value", [True, 0, 501, 1.5, "100"])
def test_primitive_validation_even_when_disabled(value):
    snapshot, resolution = snapshot_with_secret_resolution()
    snapshot = replace(snapshot, values={**snapshot.values, "web_admin_device_page_size": value})
    with pytest.raises(SettingsError, match="validation_failed"):
        SettingsValidationService().validate(snapshot, secret_resolution=resolution)


def test_existing_semantic_authorities_called(monkeypatch):
    calls = []
    for name in ("admin_web", "home_activity", "home_health", "home_ap_24h"):
        function = getattr(validators, name + "_config_from_settings")
        def wrapper(*args, _name=name, _function=function, **kwargs):
            calls.append(_name)
            return _function(*args, **kwargs)
        monkeypatch.setattr(validators, name + "_config_from_settings", wrapper)
    snapshot, resolution = snapshot_with_secret_resolution()
    SettingsValidationService().validate(snapshot, secret_resolution=resolution)
    assert calls == ["admin_web", "home_activity", "home_health", "home_ap_24h"]


def test_cross_setting_validation_remains_authoritative():
    from tests.admin_web.conftest import enabled_settings
    snapshot, resolution = snapshot_with_secret_resolution(**enabled_settings(web_admin_home_live_enabled="true", web_admin_home_live_request_timeout_seconds="5"))
    with pytest.raises(SettingsError, match="validation_failed"):
        SettingsValidationService().validate(snapshot, secret_resolution=resolution)


@pytest.mark.parametrize("resolution", [None, object()])
def test_missing_or_invalid_resolution_cannot_fall_back_to_snapshot_secret(resolution):
    snapshot = resolve_settings(CONTROLLER_BASE, {}, {}, 0)
    with pytest.raises(SettingsError) as error:
        SettingsValidationService().validate(snapshot, secret_resolution=resolution)
    assert (error.value.code, error.value.status) == ("validation_failed", 422)
    assert error.value.details == ({"key": None, "reason": "controller_prerequisite_invalid"},)
    assert error.value.__cause__ is None


def test_canonical_builder_receives_original_mapping_and_separate_resolution(monkeypatch):
    snapshot, resolution = snapshot_with_secret_resolution()
    original = validators.build_omada_runtime_config
    calls = []
    def checked(values, *, secret_resolution):
        assert values is snapshot.values and "client_secret" not in values
        assert secret_resolution is resolution
        calls.append(True)
        return original(values, secret_resolution=secret_resolution)
    monkeypatch.setattr(validators, "build_omada_runtime_config", checked)
    validator = SettingsValidationService()
    validator.validate(snapshot, secret_resolution=resolution)
    assert calls == [True] and "client_secret" not in snapshot.values
    assert resolution not in vars(validator).values()


def test_invalid_resolved_secret_preserves_controller_prerequisite_validation():
    snapshot, _ = snapshot_with_secret_resolution()
    with pytest.raises(SettingsError) as error:
        SettingsValidationService().validate(snapshot,
            secret_resolution=OmadaClientSecretResolution("", "environment", 0))
    assert error.value.details == ({"key": None, "reason": "controller_prerequisite_invalid"},)
