"""Explicit composition: Portal gets enqueue only; CLI owns the classifier worker."""

from .config import integration_config_from_settings
from .repository import IntegrationRepository
from .submitter import (
    DISABLED_FINGERPRINT_INTEGRATION_SUBMITTER, DurableFingerprintIntegrationSubmitter, emit,
)


def create_fingerprint_integration_submitter(settings):
    try:
        config = integration_config_from_settings(settings)
        if not config.enabled:
            return DISABLED_FINGERPRINT_INTEGRATION_SUBMITTER
        repository = IntegrationRepository(config.db_path)
        repository.initialize()
        return DurableFingerprintIntegrationSubmitter(repository)
    except Exception:
        emit("fingerprint.integration_worker_health", reason_code="integration_unavailable")
        return DISABLED_FINGERPRINT_INTEGRATION_SUBMITTER


def create_worker(settings):
    # These imports/composition never execute in the main Portal process.
    from app.device_fingerprint.classification_read import DeviceFingerprintClassificationReadService
    from app.device_fingerprint.classification_persistence import DeviceFingerprintClassificationStore
    from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore
    from app.device_fingerprint.read_service import DeviceFingerprintReadService
    from app.visitor_registry.registry_config import registry_config_from_settings
    from app.visitor_registry.registry_repository import VisitorRegistryRepository
    from app.visitor_registry.registry_read_service import VisitorRegistryReadService
    from app.visitor_registry.registry_service import VisitorRegistryService
    from app.visit_lifecycle.config import visit_config_from_settings
    from app.visit_lifecycle.repository import VisitRepository
    from app.visit_lifecycle.read_service import VisitLifecycleReadService
    from .executor import ClassificationExecutor
    from .compatibility import ReadOnlyControlPlaneStoreMixin
    from .identity_resolver import ExactIdentityResolver
    from .worker import IntegrationWorker
    from .models import utc_now

    config = integration_config_from_settings(settings)
    if not config.enabled:
        raise ValueError("Integration worker is disabled")
    repository = IntegrationRepository(config.db_path)
    repository.initialize()
    class ReadOnlyControl(ReadOnlyControlPlaneStoreMixin, DeviceFingerprintControlPlaneStore):
        pass
    control = ReadOnlyControl(config.control_plane_db_path)
    classification_read = DeviceFingerprintClassificationReadService(config.classification_db_path)
    classification_store = DeviceFingerprintClassificationStore(
        config.classification_db_path, config.evidence_db_path, control_plane_store=control)
    # Existing domain constructors only: do not initialize/migrate/write Registry/Visit/Task-01.
    registry_config = registry_config_from_settings({**settings, "visitor_registry_enabled": False})
    registry_read = VisitorRegistryReadService(VisitorRegistryRepository(registry_config),
        VisitorRegistryService(settings.get("portal_counter_timezone", "UTC")), configured_enabled=False)
    visit_read = VisitLifecycleReadService(VisitRepository(visit_config_from_settings(
        {**settings, "visit_lifecycle_enabled": False})))
    evidence_read = DeviceFingerprintReadService(config.evidence_db_path,
                                                retention_days=int(settings.get("device_fingerprint_retention_days", 30)))
    executor = ClassificationExecutor(control, evidence_read, classification_store, classification_read, clock=utc_now)
    return IntegrationWorker(repository, executor, ExactIdentityResolver(registry_read, visit_read))
