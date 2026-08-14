from __future__ import annotations

import logging
import uuid
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.visit_lifecycle import (
    VisitLifecycleConfig,
    VisitLifecycleService,
    VisitRepository,
    VisitStartRequest,
    VisitTelemetry,
)


@pytest.fixture
def visit_config(tmp_path):
    return VisitLifecycleConfig(
        enabled=True,
        db_path=str(tmp_path / "visits.sqlite3"),
        webhook_source=str(tmp_path / "omada_webhook_normalized.log"),
        scan_interval_seconds=5.0,
        reconcile_interval_seconds=30.0,
        max_line_bytes=1_048_576,
        reader_max_lines_per_scan=5_000,
        reader_max_bytes_per_scan=16_777_216,
        reader_max_duration_seconds=20.0,
        reconcile_batch_size=500,
        pending_offline_batch_size=500,
        offline_match_grace_seconds=30.0,
        start_writer_slot_wait_ms=5_000,
        reader_writer_slot_wait_ms=5_000,
        reconciliation_writer_slot_wait_ms=5_000,
        sqlite_busy_timeout_ms=5_000,
        start_max_attempts=3,
        start_total_budget_ms=2_000,
        shutdown_timeout_seconds=20.0,
        max_offline_clock_skew_seconds=120.0,
        max_reported_duration_drift_seconds=300.0,
    )


@pytest.fixture
def visit_repository(visit_config):
    repository = VisitRepository(visit_config)
    assert repository.initialize() is True
    return repository


@pytest.fixture
def visit_service(visit_repository):
    return VisitLifecycleService(
        visit_repository,
        VisitTelemetry(logging.getLogger("test.visit_lifecycle")),
    )


def make_request(
    *,
    auth_session_id: str | None = None,
    site_id: str = "site-a",
    client_mac: str = "02:11:22:33:44:55",
    authorized_at: datetime | None = None,
    auth_run_number: int = 1,
    authorization_attempt: int | None = 1,
    final_reason: str = "AUTHORIZED_AFTER_ATTEMPT",
    client_ip: str | None = "192.0.2.10",
    portal_ssid: str | None = "Zefer_Parki",
    portal_ap_mac: str | None = "02:AA:BB:CC:DD:EE",
    portal_radio_id: int | str | None = "0",
) -> VisitStartRequest:
    return VisitStartRequest(
        auth_session_id=auth_session_id or str(uuid.uuid4()),
        site_id=site_id,
        client_mac=client_mac,
        authorized_at=authorized_at
        or datetime(2026, 8, 13, 10, 0, tzinfo=timezone.utc),
        auth_run_number=auth_run_number,
        authorization_attempt=authorization_attempt,
        final_reason=final_reason,
        client_ip=client_ip,
        portal_ssid=portal_ssid,
        portal_ap_mac=portal_ap_mac,
        portal_radio_id=portal_radio_id,
    )


def config_with(config: VisitLifecycleConfig, **changes):
    return replace(config, **changes)
