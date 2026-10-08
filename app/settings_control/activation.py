"""Main-runtime lifecycle capability; never included in SettingsAdminContext."""
from .models import SettingsError


class SettingsActivationService:
    def __init__(self, repository, snapshot, read_service):
        self.repository, self.snapshot, self.read_service = repository, snapshot, read_service

    def adopt(self, runtime_settings, admin_runtime):
        # Exact startup snapshot, not a fresh configured-head lookup.
        if runtime_settings is not self.snapshot.values:
            self.fail("snapshot_mismatch")
            raise SettingsError("settings_activation_failed", 500)
        admin_enabled = runtime_settings.get("web_admin_enabled", "false") in (True, "true")
        if admin_enabled and admin_runtime is None:
            # An absent runtime alone is not positive Settings-validation evidence.
            raise SettingsError("settings_activation_unavailable", 503)
        invalid = admin_enabled and admin_runtime.config is None
        if admin_runtime is not None:
            for enabled_key, attribute in (
                ("web_admin_home_activity_enabled", "home_activity_config"),
                ("web_admin_home_health_enabled", "home_health_config"),
                ("web_admin_home_ap_24h_enabled", "home_ap_24h_config"),
            ):
                if runtime_settings.get(enabled_key, "false") in (True, "true"):
                    config = getattr(admin_runtime, attribute, None)
                    invalid |= config is None or not config.enabled
        if invalid:
            self.fail("admin_configuration_adoption_failed")
            raise SettingsError("settings_activation_failed", 500)
        if admin_enabled and admin_runtime.blueprint is None:
            raise SettingsError("settings_activation_unavailable", 503)
        self.repository.activation(self.snapshot.generation_id, True)
        self.read_service._adopted = True

    def fail(self, safe_error_code):
        if safe_error_code not in {"snapshot_mismatch", "admin_configuration_adoption_failed", "settings_validation_failed", "controller_configuration_adoption_failed", "portal_configuration_adoption_failed",
                "controller_secret_key_unavailable", "controller_secret_permissions_invalid", "controller_secret_reference_missing",
                "controller_secret_decrypt_failed", "controller_secret_integrity_failed", "controller_secret_configuration_invalid"}:
            raise ValueError("invalid activation failure category")
        self.repository.activation(self.snapshot.generation_id, False, safe_error_code)
