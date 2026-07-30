"""Visitor Snapshot Collector and Visitor Device Registry public API."""

from .config import (
    VisitorSnapshotConfig,
    VisitorSnapshotConfigError,
)
from .device_ids import (
    VISITOR_DEVICE_NAMESPACE,
    build_device_id,
)
from .registry_config import (
    registry_config_from_settings,
    registry_timezone_from_settings,
)
from .registry_models import (
    REGISTRY_SCHEMA_VERSION,
    RegistryConfig,
    RegistryConfigError,
)
from .registry_worker import (
    DISABLED_VISITOR_REGISTRY,
    DisabledVisitorRegistry,
    UnavailableVisitorRegistry,
    VisitorRegistryWorker,
    create_visitor_registry,
)
from .snapshot_collector import (
    AuthorizedClientSnapshotCollector,
    DISABLED_VISITOR_SNAPSHOT_COLLECTOR,
    DisabledVisitorSnapshotCollector,
    UnavailableVisitorSnapshotCollector,
    create_visitor_snapshot_collector,
)
from .snapshot_ids import (
    VISITOR_SNAPSHOT_NAMESPACE,
    build_snapshot_id,
)
from .snapshot_models import (
    AuthorizedClientAuthContext,
    AuthorizedClientSnapshotRequest,
    SnapshotSubmitOutcome,
)
from .snapshot_writer import (
    VisitorSnapshotWriteError,
    VisitorSnapshotWriter,
)

__all__ = [
    "AuthorizedClientAuthContext",
    "AuthorizedClientSnapshotCollector",
    "AuthorizedClientSnapshotRequest",
    "DISABLED_VISITOR_REGISTRY",
    "DISABLED_VISITOR_SNAPSHOT_COLLECTOR",
    "DisabledVisitorRegistry",
    "DisabledVisitorSnapshotCollector",
    "REGISTRY_SCHEMA_VERSION",
    "SnapshotSubmitOutcome",
    "VISITOR_DEVICE_NAMESPACE",
    "VISITOR_SNAPSHOT_NAMESPACE",
    "RegistryConfig",
    "RegistryConfigError",
    "VisitorSnapshotConfig",
    "VisitorSnapshotConfigError",
    "VisitorSnapshotWriteError",
    "VisitorSnapshotWriter",
    "UnavailableVisitorSnapshotCollector",
    "UnavailableVisitorRegistry",
    "VisitorRegistryWorker",
    "build_device_id",
    "build_snapshot_id",
    "create_visitor_registry",
    "create_visitor_snapshot_collector",
    "registry_config_from_settings",
    "registry_timezone_from_settings",
]
