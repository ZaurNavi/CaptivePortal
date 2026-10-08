"""One-shot startup resolution; enabled Store failures are fail-closed."""
from .activation import SettingsActivationService
from .models import SettingsAdminContext, SettingsBootstrapResult, ResolvedSettingsSnapshot, SettingsError
from .repository import SettingsRepository
from .resolver import resolve_settings, freeze
from .services import SettingsReadService, SettingsMutationService
from .validation import SettingsValidationService


def bootstrap_settings_control(*, base_settings, explicit_environment_names, logger, secret_filesystem=None):
    enabled = base_settings.get("web_admin_settings_enabled", "false") in (True, "true")
    empty = freeze({})
    ordinary_base = freeze({key: value for key, value in base_settings.items() if key != "client_secret"})
    fallback = ResolvedSettingsSnapshot(None, ordinary_base, empty, empty, empty)
    if not enabled:
        return SettingsBootstrapResult(False, "disabled", base_settings, fallback, SettingsAdminContext(False, "disabled"))
    try:
        repository = SettingsRepository(base_settings.get("settings_db_path", "/opt/CaptivePortal/data/settings.sqlite3"))
        generation, overrides = repository.configured()
    except SettingsError as error:
        if error.code.startswith("controller_secret_"):
            logger.error("settings.secret_validation_failed")
            raise
        logger.error("settings.store_unavailable")
        raise SettingsError("settings_store_unavailable") from None
    except (TypeError, ValueError, OSError):
        logger.error("settings.store_unavailable")
        raise SettingsError("settings_store_unavailable") from None
    try:
        snapshot = resolve_settings(ordinary_base, explicit_environment_names, overrides, generation)
        from .controller_secret import ControllerSecretRepository, ControllerSecretMutationService
        secrets = ControllerSecretRepository(repository, secret_filesystem, base_settings.get("client_secret"),
            "environment" if "OMADA_CLIENT_SECRET" in explicit_environment_names else "repository_default")
        secret_resolution = secrets.resolve(generation, base_settings, explicit_environment_names)
        SettingsValidationService().validate(snapshot, secret_resolution=secret_resolution)
    except SettingsError as error:
        try:
            repository.activation(generation, False, error.code if error.code.startswith("controller_secret_") else "settings_validation_failed")
        except SettingsError:
            logger.error("settings.failure_attestation_unavailable")
        raise
    read = SettingsReadService(repository, ordinary_base, explicit_environment_names, snapshot)
    mutation = SettingsMutationService(repository, read)
    mutation.secret_repository = secrets
    secret_mutation = ControllerSecretMutationService(secrets, read)
    return SettingsBootstrapResult(True, "available", snapshot.values, snapshot,
        SettingsAdminContext(True, "available", read, mutation, secret_mutation, secrets.safe_metadata_service()),
        SettingsActivationService(repository, snapshot, read), secret_resolution)
