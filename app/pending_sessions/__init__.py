"""
Pending sessions package public exports.

No side-effects on import.
"""
from .config import PendingSessionCleanerConfig
from .protocols import PendingClientSessionProvider, PendingSessionProtection
from .models import (
    PendingClientObservation,
    PendingClientCandidate,
    ClassificationResult,
    PaginationResult,
    ProtectionDecision,
    PendingScanSummary,
)
from .classifier import PendingSessionClassifier
from .pagination import paginate_site_inventory
from .journal import JournalWriter, JournalWriteError
from .telemetry import CleanerTelemetryAdapter
from .action_guard import ActionGuard, ActionGuardDecision
from .protection import AuthManagerPendingSessionProtection
from .cleaner import PendingClientSessionCleaner
from .worker import PendingSessionWorker
from .factory import (
    DisabledPendingSessionCleaner,
    UnavailablePendingSessionCleaner,
    create_pending_session_cleaner,
)

__all__ = [
    "PendingSessionCleanerConfig",
    "PendingClientSessionProvider",
    "PendingSessionProtection",
    "PendingClientObservation",
    "PendingClientCandidate",
    "ClassificationResult",
    "PaginationResult",
    "ProtectionDecision",
    "PendingScanSummary",
    "PendingSessionClassifier",
    "paginate_site_inventory",
    "JournalWriter",
    "JournalWriteError",
    "CleanerTelemetryAdapter",
    "ActionGuard",
    "ActionGuardDecision",
    "AuthManagerPendingSessionProtection",
    "PendingClientSessionCleaner",
    "PendingSessionWorker",
    "DisabledPendingSessionCleaner",
    "UnavailablePendingSessionCleaner",
    "create_pending_session_cleaner",
]
