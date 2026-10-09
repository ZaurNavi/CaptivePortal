"""Primitive validation plus existing authoritative semantic validators."""
from app.admin_web.config import admin_web_config_from_settings
from app.admin_web.home_activity_config import home_activity_config_from_settings
from app.admin_web.home_health_config import home_health_config_from_settings
from app.admin_web.home_ap_24h_config import home_ap_24h_config_from_settings
from app.current_state.config import current_state_config_from_settings
from .definitions import SettingsDefinitionRegistry
from .features import AdminFeaturePlanV1
from app.admin_web.device_list_context_config import device_list_context_config_from_settings
from app.traffic_projection.config import traffic_projection_read_config_from_settings
from .models import SettingsError
from app.controllers.omada_config import build_omada_runtime_config, normalize_controller_setting
from app.portal_presentation import PortalPresentationConfigV1, PortalPresentationConfigError
from app.exceptions import ConfigurationError


class SettingsValidationService:
    def __init__(self, registry=None):
        self.registry = registry or SettingsDefinitionRegistry()

    def _validate_general(self, snapshot, *, feature_plan=None):
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
        plan = feature_plan if feature_plan is not None else AdminFeaturePlanV1.from_snapshot(snapshot, self.registry)
        selected = plan.composition_settings(snapshot.values)
        admin_enabled = selected.get("web_admin_enabled", "false") in (True, "true")
        try:
            admin = admin_web_config_from_settings(selected, feature_plan=plan)
            current = None
            if selected.get("web_admin_home_activity_enabled") in (True, "true"):
                current = current_state_config_from_settings(selected)
            home_activity_config_from_settings(selected, admin_config=admin, current_state_config=current)
            home_health_config_from_settings(selected, admin_config=admin)
            device_list_context_config_from_settings(selected, admin_config=admin)
            if admin_enabled and plan.enabled("traffic.projection_read"):
                traffic_projection_read_config_from_settings(selected)
            home_ap_24h_config_from_settings(snapshot.values, admin_config=admin)
        except (ValueError, TypeError) as exc:
            message = str(exc)
            key = None
            for item in self.registry.for_domain("features"):
                prefix = item.key.removesuffix("_ENABLED")
                if prefix in message:
                    key = item.key
                    break
            if key is None:
                if "Activity" in message or "Current State" in message:
                    key = "WEB_ADMIN_HOME_ACTIVITY_ENABLED"
                elif "Projection" in message or "OBSERVATION" in message:
                    key = "WEB_ADMIN_TRAFFIC_PROJECTION_READ_ENABLED"
                elif "Home Health" in message:
                    key = "WEB_ADMIN_HOME_HEALTH_ENABLED"
            raise SettingsError("validation_failed", 422,
                                ({"key": key, "reason": "configuration_prerequisite_invalid"},)) from None

    @staticmethod
    def _validate_portal(snapshot):
        try:
            PortalPresentationConfigV1.from_settings(snapshot.values)
        except PortalPresentationConfigError as error:
            raise SettingsError("validation_failed", 422, ({"key": error.key, "reason": error.reason},)) from None

    def validate_portal_candidate(self, snapshot):
        self._validate_general(snapshot)
        try:
            for item in self.registry.for_domain("controller"):
                normalize_controller_setting(item.key, snapshot.values.get(item.settings_dict_key))
        except ConfigurationError:
            raise SettingsError("validation_failed", 422, ({"key": None, "reason": "controller_prerequisite_invalid"},)) from None
        self._validate_portal(snapshot)

    def validate_features_candidate(self, snapshot):
        """Validate candidate feature selection without resolving Controller secrets."""
        plan = AdminFeaturePlanV1.from_snapshot(snapshot, self.registry)
        self._validate_general(snapshot, feature_plan=plan)
        try:
            for item in self.registry.for_domain("controller"):
                normalize_controller_setting(item.key, snapshot.values.get(item.settings_dict_key))
        except ConfigurationError:
            raise SettingsError("validation_failed", 422, ({"key": None, "reason": "controller_prerequisite_invalid"},)) from None
        self._validate_portal(snapshot)

    def validate(self, snapshot, *, secret_resolution=None, feature_plan=None):
        self._validate_general(snapshot, feature_plan=feature_plan)
        try:
            from .controller_secret import OmadaClientSecretResolution
            if not isinstance(secret_resolution, OmadaClientSecretResolution):
                raise ConfigurationError("Missing Controller secret resolution")
            build_omada_runtime_config(snapshot.values, secret_resolution=secret_resolution)
        except (ConfigurationError, KeyError, TypeError):
            raise SettingsError("validation_failed", 422, ({"key": None, "reason": "controller_prerequisite_invalid"},)) from None
        self._validate_portal(snapshot)
