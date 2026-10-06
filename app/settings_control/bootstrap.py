"""One-shot startup resolution, disabled/store-unavailable fail-open boundary."""
from .activation import SettingsActivationService
from .models import SettingsAdminContext, SettingsBootstrapResult, ResolvedSettingsSnapshot, SettingsError
from .repository import SettingsRepository
from .resolver import resolve_settings, freeze
from .services import SettingsReadService, SettingsMutationService
from .validation import SettingsValidationService


def bootstrap_settings_control(*, base_settings, explicit_environment_names, logger):
    enabled = base_settings.get("web_admin_settings_enabled", "false") in (True, "true")
    empty = freeze({})
    fallback = ResolvedSettingsSnapshot(None, freeze(dict(base_settings)), empty, empty, empty)
    if not enabled:
        return SettingsBootstrapResult(False, "disabled", base_settings, fallback, SettingsAdminContext(False, "disabled"))
    try:
        repository = SettingsRepository(base_settings.get("settings_db_path", "/opt/CaptivePortal/data/settings.sqlite3"))
        generation, overrides = repository.configured()
    except (SettingsError, TypeError, ValueError, OSError):
        logger.error("settings.store_unavailable")
        return SettingsBootstrapResult(True, "unavailable", base_settings, fallback, SettingsAdminContext(True, "unavailable"))
    try:
        snapshot = resolve_settings(base_settings, explicit_environment_names, overrides, generation)
        SettingsValidationService().validate(snapshot)
    except SettingsError:
        try:
            repository.activation(generation, False, "settings_validation_failed")
        except SettingsError:
            logger.error("settings.failure_attestation_unavailable")
        raise
    read = SettingsReadService(repository, freeze(dict(base_settings)), explicit_environment_names, snapshot)
    mutation = SettingsMutationService(repository, read)
    return SettingsBootstrapResult(True, "available", snapshot.values, snapshot,
        SettingsAdminContext(True, "available", read, mutation), SettingsActivationService(repository, snapshot, read))
