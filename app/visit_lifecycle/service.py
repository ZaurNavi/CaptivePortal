"""Write-side Visit Lifecycle application service."""

from __future__ import annotations

from .models import (
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
