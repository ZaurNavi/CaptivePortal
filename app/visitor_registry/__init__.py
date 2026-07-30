"""Authorized Client Snapshot Collector public API."""

from .config import (
    VisitorSnapshotConfig,
    VisitorSnapshotConfigError,
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
    "DISABLED_VISITOR_SNAPSHOT_COLLECTOR",
    "DisabledVisitorSnapshotCollector",
    "SnapshotSubmitOutcome",
    "VISITOR_SNAPSHOT_NAMESPACE",
    "VisitorSnapshotConfig",
    "VisitorSnapshotConfigError",
    "VisitorSnapshotWriteError",
    "VisitorSnapshotWriter",
    "UnavailableVisitorSnapshotCollector",
    "build_snapshot_id",
    "create_visitor_snapshot_collector",
]
