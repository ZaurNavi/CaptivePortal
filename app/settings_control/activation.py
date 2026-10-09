"""Main-runtime lifecycle capability; never included in SettingsAdminContext."""
from .models import SettingsError


class SettingsActivationService:
    def __init__(self, repository, snapshot, read_service, feature_plan):
        self.repository, self.snapshot, self.read_service = repository, snapshot, read_service
        self.feature_plan = feature_plan

    def adopt(self, runtime_settings, admin_runtime, analytics_runtime, *, feature_plan):
        # Exact startup snapshot, not a fresh configured-head lookup.
        if runtime_settings is not self.snapshot.values:
            self.fail("snapshot_mismatch")
            raise SettingsError("settings_activation_failed", 500)
        admin_enabled = runtime_settings.get("web_admin_enabled", "false") in (True, "true")
        if admin_enabled and admin_runtime is None:
            # An absent runtime alone is not positive Settings-validation evidence.
            raise SettingsError("settings_activation_unavailable", 503)
        if (feature_plan is not self.feature_plan or self.feature_plan.generation_id != self.snapshot.generation_id
                or getattr(admin_runtime, "feature_plan", None) is not self.feature_plan
                or getattr(analytics_runtime, "feature_plan", None) is not self.feature_plan):
            self.fail("features_configuration_adoption_failed")
            raise SettingsError("settings_activation_failed", 500)
        invalid = admin_enabled and admin_runtime.config is None
        # Deferred AP-24H keeps its pre-Stage-6 adoption boundary and category.
        if runtime_settings.get("web_admin_home_ap_24h_enabled", "false") in (True, "true"):
            config = getattr(admin_runtime, "home_ap_24h_config", None)
            invalid |= config is None or not config.enabled
        if invalid:
            self.fail("admin_configuration_adoption_failed")
            raise SettingsError("settings_activation_failed", 500)
        if admin_enabled:
            for feature_id, attribute in (
                ("home.activity", "home_activity_config"),
                ("home.health", "home_health_config"),
            ):
                if self.feature_plan.enabled(feature_id):
                    config = getattr(admin_runtime, attribute, None)
                    invalid |= config is None or not config.enabled
        if admin_enabled:
            if self.feature_plan.enabled("devices.list_context"):
                config = getattr(admin_runtime, "device_list_context_config", None)
                invalid |= config is None or not config.enabled or admin_runtime.device_list_context_cursor_codec is None
            expected_mode = "projection" if self.feature_plan.enabled("traffic.projection_read") else "base"
            invalid |= analytics_runtime.historical_source_mode != expected_mode
        if invalid:
            self.fail("features_configuration_adoption_failed")
            raise SettingsError("settings_activation_failed", 500)
        if admin_enabled and admin_runtime.blueprint is None:
            raise SettingsError("settings_activation_unavailable", 503)
        self.repository.activation(self.snapshot.generation_id, True)
        self.read_service._adopted = True

    def fail(self, safe_error_code):
        if safe_error_code not in {"features_configuration_adoption_failed", "snapshot_mismatch", "admin_configuration_adoption_failed", "settings_validation_failed", "controller_configuration_adoption_failed", "portal_configuration_adoption_failed",
                "controller_secret_key_unavailable", "controller_secret_permissions_invalid", "controller_secret_reference_missing",
                "controller_secret_decrypt_failed", "controller_secret_integrity_failed", "controller_secret_configuration_invalid"}:
            raise ValueError("invalid activation failure category")
        self.repository.activation(self.snapshot.generation_id, False, safe_error_code)
