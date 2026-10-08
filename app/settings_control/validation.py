"""Primitive validation plus existing authoritative semantic validators."""
from app.admin_web.config import admin_web_config_from_settings
from app.admin_web.home_activity_config import home_activity_config_from_settings
from app.admin_web.home_health_config import home_health_config_from_settings
from app.admin_web.home_ap_24h_config import home_ap_24h_config_from_settings
from app.current_state.config import current_state_config_from_settings
from .definitions import SettingsDefinitionRegistry
from .models import SettingsError
from app.controllers.omada_config import build_omada_runtime_config
from app.exceptions import ConfigurationError


class SettingsValidationService:
    def __init__(self, registry=None):
        self.registry = registry or SettingsDefinitionRegistry()

    def validate(self, snapshot, *, secret_resolution=None):
        details = []
        for item in self.registry:
            if item.domain != "general":
                continue
            value = snapshot.values[item.settings_dict_key]
            if type(value) is not int:
                details.append({"key": item.key, "reason": "integer_required"})
            elif not item.min_value <= value <= item.max_value:
                details.append({"key": item.key, "reason": "out_of_range"})
            base = snapshot.base_value_by_key[item.key]
            if not item.min_value <= base <= item.max_value:
                details.append({"key": item.key, "reason": "invalid_base_value"})
        if details:
            raise SettingsError("validation_failed", 422, details)
        try:
            admin = admin_web_config_from_settings(snapshot.values)
            current = None
            if snapshot.values.get("web_admin_home_activity_enabled") in (True, "true"):
                current = current_state_config_from_settings(snapshot.values)
            home_activity_config_from_settings(snapshot.values, admin_config=admin, current_state_config=current)
            home_health_config_from_settings(snapshot.values, admin_config=admin)
            home_ap_24h_config_from_settings(snapshot.values, admin_config=admin)
        except (ValueError, TypeError) as exc:
            raise SettingsError("validation_failed", 422, ({"key": None, "reason": "semantic_validation_failed"},)) from exc
        try:
            from .controller_secret import OmadaClientSecretResolution
            if not isinstance(secret_resolution, OmadaClientSecretResolution):
                raise ConfigurationError("Missing Controller secret resolution")
            build_omada_runtime_config(snapshot.values, secret_resolution=secret_resolution)
        except (ConfigurationError, KeyError, TypeError):
            raise SettingsError("validation_failed", 422, ({"key": None, "reason": "controller_prerequisite_invalid"},)) from None
