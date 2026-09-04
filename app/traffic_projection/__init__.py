"""Derived Historical Traffic projection foundation."""

from .config import projection_read_enabled, traffic_projection_config_from_settings
from .models import (
    PROJECTION_VERSION,
    ProjectionHealth,
    ProjectedRangeSelection,
    TrafficProjectionConfig,
    TrafficProjectionConfigError,
    TrafficProjectionDiverged,
    TrafficProjectionSourceUnavailable,
    TrafficProjectionStorageCorrupt,
    TrafficProjectionStorageUnavailable,
    TrafficProjectionValidationError,
    TrafficProjectionVersionUnavailable,
    TrafficProjectionWriterUnavailable,
)
from .read_service import TrafficProjectionReadService
from .repository import TrafficProjectionRepository
from .service import TrafficProjectionService
from .telemetry import TrafficProjectionTelemetry

__all__ = [
    "PROJECTION_VERSION",
    "ProjectionHealth",
    "ProjectedRangeSelection",
    "TrafficProjectionConfig",
    "TrafficProjectionConfigError",
    "TrafficProjectionDiverged",
    "TrafficProjectionSourceUnavailable",
    "TrafficProjectionStorageCorrupt",
    "TrafficProjectionStorageUnavailable",
    "TrafficProjectionValidationError",
    "TrafficProjectionVersionUnavailable",
    "TrafficProjectionWriterUnavailable",
    "TrafficProjectionReadService",
    "TrafficProjectionRepository",
    "TrafficProjectionService",
    "TrafficProjectionTelemetry",
    "projection_read_enabled",
    "traffic_projection_config_from_settings",
]
