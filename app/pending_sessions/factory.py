from __future__ import annotations

from dataclasses import dataclass

from .action_guard import ActionGuard
from .cleaner import PendingClientSessionCleaner
from .config import PendingSessionCleanerConfig
from .journal import JournalWriter
from .protection import AuthManagerPendingSessionProtection
from .telemetry import CleanerTelemetryAdapter
from .worker import PendingSessionWorker


@dataclass
class DisabledPendingSessionCleaner:
    config: PendingSessionCleanerConfig

    def start(self) -> bool:
        return False

    def run_once(self):
        return None

    def stop(self, timeout_seconds: float) -> bool:
        return True


@dataclass
class UnavailablePendingSessionCleaner:
    error: str
    config: PendingSessionCleanerConfig | None = None

    def start(self) -> bool:
        return False

    def run_once(self):
        return None

    def stop(self, timeout_seconds: float) -> bool:
        return True


def create_pending_session_cleaner(
    *,
    settings: dict,
    provider,
    auth_manager,
    telemetry,
):
    adapter = CleanerTelemetryAdapter(telemetry)
    try:
        config = PendingSessionCleanerConfig.from_settings(settings)
    except Exception as exc:
        adapter.safe_emit_system(
            "pending_session_cleaner_unavailable",
            level="critical",
            stage="configuration",
            exception_type=type(exc).__name__,
        )
        return UnavailablePendingSessionCleaner(str(exc))

    if not config.enabled:
        return DisabledPendingSessionCleaner(config)

    try:
        journal = JournalWriter(
            config.log_file,
            max_bytes=config.rotation_max_bytes,
            backup_count=config.rotation_backup_count,
        )
        protection = AuthManagerPendingSessionProtection(
            auth_manager
        )
        cleaner = PendingClientSessionCleaner(
            config=config,
            provider=provider,
            protection=protection,
            journal=journal,
            telemetry=adapter,
            action_guard=ActionGuard(
                cooldown_seconds=config.action_cooldown_seconds,
                max_actions_per_mac_per_hour=(
                    config.max_actions_per_mac_per_hour
                ),
            ),
        )
        return PendingSessionWorker(cleaner)
    except Exception as exc:
        adapter.safe_emit_system(
            "pending_session_cleaner_unavailable",
            level="critical",
            stage="construction",
            exception_type=type(exc).__name__,
        )
        return UnavailablePendingSessionCleaner(
            str(exc),
            config=config,
        )
