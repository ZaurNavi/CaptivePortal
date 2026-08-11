"""Site-aware Observation Storage Foundation v1.

The package is deliberately not wired into ``run.py`` in TASK 01A.
Importing it performs no I/O, starts no worker, and makes no Omada call.
"""

from .cleanup import ObservationCleanup, ObservationCleanupWorker
from .config import observation_config_from_settings
from .models import (
    ApConfigSnapshot,
    ApObservation,
    ApRadioObservation,
    CleanupResult,
    ClientObservation,
    ObservationConfig,
    ObservationConfigError,
    ObservationCycle,
    ObservationPage,
    ObservationSchemaError,
    ObservationStorageError,
    ObservationValidationError,
    StorageFailureCategory,
)
from .read_service import ObservationReadService
from .repository import ObservationRepository

__all__ = [
    "ApConfigSnapshot",
    "ApObservation",
    "ApRadioObservation",
    "CleanupResult",
    "ClientObservation",
    "ObservationCleanup",
    "ObservationCleanupWorker",
    "ObservationConfig",
    "ObservationConfigError",
    "ObservationCycle",
    "ObservationPage",
    "ObservationReadService",
    "ObservationRepository",
    "ObservationSchemaError",
    "ObservationStorageError",
    "ObservationValidationError",
    "StorageFailureCategory",
    "observation_config_from_settings",
]
