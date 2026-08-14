"""Write-side Visit Lifecycle application service."""

from __future__ import annotations

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
    ) -> VisitStartOutcome:
        start = normalize_start_request(request)
        outcome = self.repository.create_or_reuse_start(
            start,
            now_utc=utc_now(),
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

    def process_journal_line(
        self,
        *,
        progress: ReaderProgress,
        evidence: OfflineEvidence | None,
        now_utc: str,
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
        )
        self._emit_offline_outcome(outcome)
        return outcome

    def retry_pending(self, *, now_utc: str) -> int:
        outcomes = self.repository.process_pending_events(
            now_utc=now_utc,
            limit=self.repository.config.pending_offline_batch_size,
            max_clock_skew_seconds=(
                self.repository.config.max_offline_clock_skew_seconds
            ),
            max_duration_drift_seconds=(
                self.repository.config.max_reported_duration_drift_seconds
            ),
        )
        for outcome in outcomes:
            self._emit_offline_outcome(outcome)
        return len(outcomes)

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
            self.telemetry.emit("visit.closed", **fields)
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
