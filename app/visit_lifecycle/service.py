"""Write-side Visit Lifecycle application service."""

from __future__ import annotations

import threading
from typing import Callable

from .models import (
    OfflineEvidence,
    OfflineProcessingOutcome,
    ReaderProgress,
    VisitStartOutcome,
    VisitStartRequest,
    normalize_start_request,
    utc_now,
)
from .repository import VisitRepository
from .telemetry import VisitTelemetry


class VisitLifecycleService:
    def __init__(
        self,
        repository: VisitRepository,
        telemetry: VisitTelemetry,
    ):
        self.repository = repository
        self.telemetry = telemetry

    def submit_authorized(
        self,
        request: VisitStartRequest,
        *,
        deadline: float | None = None,
        cancel_event: threading.Event | None = None,
    ) -> VisitStartOutcome:
        start = normalize_start_request(request)
        outcome = self.repository.create_or_reuse_start(
            start,
            now_utc=utc_now(),
            deadline=deadline,
            cancel_event=cancel_event,
        )
        if outcome.status == "opened":
            self.telemetry.emit(
                "visit.opened",
                visit_id=outcome.visit_id,
                site_id=start.site_id,
                client_mac=start.client_mac,
            )
        elif outcome.status == "reused":
            self.telemetry.emit(
                "visit.start_reused",
                visit_id=outcome.visit_id,
                site_id=start.site_id,
                client_mac=start.client_mac,
            )
        if outcome.authorization_attached:
            self.telemetry.emit(
                "visit.authorization_attached",
                visit_id=outcome.visit_id,
                site_id=start.site_id,
                client_mac=start.client_mac,
                auth_run_number=start.auth_run_number,
            )
        return outcome

    def wake_write_waiters(self) -> None:
        self.repository.wake_write_waiters()

    def process_journal_line(
        self,
        *,
        progress: ReaderProgress,
        evidence: OfflineEvidence | None,
        now_utc: str,
        deadline: float | None = None,
        cancel_event: threading.Event | None = None,
    ) -> OfflineProcessingOutcome | None:
        outcome = self.repository.apply_journal_line(
            progress=progress,
            evidence=evidence,
            now_utc=now_utc,
            grace_seconds=self.repository.config.offline_match_grace_seconds,
            max_clock_skew_seconds=(
                self.repository.config.max_offline_clock_skew_seconds
            ),
            max_duration_drift_seconds=(
                self.repository.config.max_reported_duration_drift_seconds
            ),
            deadline=deadline,
            cancel_event=cancel_event,
        )
        self._emit_offline_outcome(outcome)
        return outcome

    def retry_pending(
        self,
        *,
        now_utc: str,
        deadline: float | None = None,
        cancel_event: threading.Event | None = None,
        on_committed_progress: Callable[[int], None] | None = None,
    ) -> int:
        def committed(
            outcomes: tuple[OfflineProcessingOutcome, ...],
        ) -> None:
            self._emit_committed_chunk(outcomes)
            if on_committed_progress is not None:
                on_committed_progress(len(outcomes))

        outcomes = self.repository.process_pending_events(
            now_utc=now_utc,
            limit=self.repository.config.pending_offline_batch_size,
            max_clock_skew_seconds=(
                self.repository.config.max_offline_clock_skew_seconds
            ),
            max_duration_drift_seconds=(
                self.repository.config.max_reported_duration_drift_seconds
            ),
            deadline=deadline,
            cancel_event=cancel_event,
            on_committed_chunk=committed,
        )
        return len(outcomes)

    def _emit_committed_chunk(
        self,
        outcomes: tuple[OfflineProcessingOutcome, ...],
    ) -> None:
        for outcome in outcomes:
            self._emit_offline_outcome(outcome)

    def _emit_offline_outcome(
        self,
        outcome: OfflineProcessingOutcome | None,
    ) -> None:
        if outcome is None:
            return
        fields = {
            "event_id": outcome.event_id,
            "visit_id": outcome.visit_id,
            "reason": outcome.reason,
        }
        if outcome.duplicate:
            self.telemetry.emit("visit.offline_duplicate", **fields)
        elif outcome.processing_result == "closed":
            self.telemetry.emit(
                "visit.closed",
                close_time_source=outcome.close_time_source,
                **fields,
            )
            if outcome.duration_drift_exceeded:
                self.telemetry.emit(
                    "visit.offline_duration_drift",
                    "warning",
                    duration_drift_seconds=outcome.duration_drift_seconds,
                    duration_drift_threshold_seconds=(
                        outcome.duration_drift_threshold_seconds
                    ),
                    duration_drift_exceeded=True,
                    close_time_source=outcome.close_time_source,
                    **fields,
                )
        elif outcome.processing_result == "unmatched":
            self.telemetry.emit(
                "visit.offline_unmatched",
                "warning",
                **fields,
            )
        elif outcome.processing_result == "invalid":
            self.telemetry.emit(
                "visit.offline_invalid",
                "warning",
                **fields,
            )
