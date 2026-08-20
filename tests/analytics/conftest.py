from __future__ import annotations

import os
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from app.analytics import AnalyticsConfig
from app.analytics.read_service import AnalyticsReadService
from app.analytics.source_gateway import AnalyticsSourceGateway
from app.observations.models import ObservationConfig
from app.observations.read_service import ObservationReadService
from app.observations.repository import ObservationRepository
from app.visit_lifecycle.models import (
    NormalizedVisitStart,
    VisitLifecycleConfig,
)
from app.visit_lifecycle.read_service import VisitLifecycleReadService
from app.visit_lifecycle.repository import VisitRepository
from app.visitor_registry.registry_models import RegistryConfig
from app.visitor_registry.registry_read_service import (
    VisitorRegistryReadService,
)
from app.visitor_registry.registry_repository import (
    VisitorRegistryRepository,
)
from app.visitor_registry.registry_service import VisitorRegistryService


UTC = timezone.utc
SITE_A = "site-a"
SITE_B = "site-b"
CLIENT_A = "02:11:22:33:44:55"
CLIENT_B = "02:11:22:33:44:66"
AP_A = "02:AA:BB:CC:DD:EE"
DEVICE_A = "11111111-1111-4111-8111-111111111111"
SNAPSHOT_A = "22222222-2222-4222-8222-222222222222"
AUTH_A = "33333333-3333-4333-8333-333333333333"


@dataclass
class AnalyticsStack:
    service: AnalyticsReadService
    gateway: AnalyticsSourceGateway
    observations: ObservationRepository
    visits: VisitRepository
    registry: VisitorRegistryRepository
    visit_id: str
    open_visit_id: str


@pytest.fixture
def analytics_stack(tmp_path) -> AnalyticsStack:
    data = tmp_path / "data"
    logs = tmp_path / "logs"
    data.mkdir(mode=0o750)
    logs.mkdir(mode=0o750)
    if os.name == "posix":
        data.chmod(0o750)
        logs.chmod(0o750)

    observation_config = ObservationConfig(
        enabled=True,
        db_path=str(data / "observations.sqlite3"),
        dynamic_retention_days=180,
        config_retention_days=730,
        cleanup_initial_delay_seconds=900,
        cleanup_interval_seconds=86400,
        cleanup_batch_size=5000,
        cleanup_max_duration_seconds=30,
        shutdown_timeout_seconds=20,
    )
    observations = ObservationRepository(observation_config)
    observations.initialize("2026-01-01T00:00:00.000Z")

    visit_config = VisitLifecycleConfig(
        enabled=True,
        db_path=str(data / "visits.sqlite3"),
        webhook_source=str(logs / "normalized.log"),
        scan_interval_seconds=5,
        reconcile_interval_seconds=30,
        max_line_bytes=1_048_576,
        reader_max_lines_per_scan=5_000,
        reader_max_bytes_per_scan=16_777_216,
        reader_max_duration_seconds=20,
        reconcile_batch_size=500,
        pending_offline_batch_size=500,
        offline_match_grace_seconds=30,
        start_writer_slot_wait_ms=750,
        reader_writer_slot_wait_ms=250,
        reconciliation_writer_slot_wait_ms=250,
        sqlite_busy_timeout_ms=500,
        start_max_attempts=3,
        start_total_budget_ms=2_000,
        shutdown_timeout_seconds=20,
        max_offline_clock_skew_seconds=120,
        max_reported_duration_drift_seconds=300,
    )
    visits = VisitRepository(visit_config)
    visits.initialize()

    registry_config = RegistryConfig(
        enabled=True,
        db_path=str(data / "visitor_registry.sqlite3"),
        source_log_path=str(logs / "visitor_snapshots.log"),
        source_backup_count=20,
        timezone_name="UTC",
        scan_interval_seconds=5,
        shutdown_timeout_seconds=10,
        max_line_bytes=4_194_304,
    )
    registry = VisitorRegistryRepository(registry_config)
    registry.initialize("2026-01-01T00:00:00.000Z")

    _seed_observations(observations)
    visit_id, open_visit_id = _seed_visits(visits)
    _seed_registry(registry)

    observation_read = ObservationReadService(observations)
    visit_read = VisitLifecycleReadService(visits)
    registry_read = VisitorRegistryReadService(
        registry,
        VisitorRegistryService("UTC"),
        configured_enabled=True,
    )
    gateway = AnalyticsSourceGateway(
        observation_read, visit_read, registry_read
    )
    service = AnalyticsReadService(
        AnalyticsConfig(enabled=True),
        gateway,
        clock=lambda: datetime(2026, 1, 1, 11, 0, tzinfo=UTC),
    )
    return AnalyticsStack(
        service=service,
        gateway=gateway,
        observations=observations,
        visits=visits,
        registry=registry,
        visit_id=visit_id,
        open_visit_id=open_visit_id,
    )


def _seed_observations(repository: ObservationRepository) -> None:
    for cycle_id, timestamp, complete, result, site, mac in (
        ("client-good-1", "2026-01-01T10:00:00.000Z", True, "success", SITE_A, CLIENT_A),
        ("client-partial", "2026-01-01T10:01:00.000Z", False, "partial", SITE_A, CLIENT_A),
        ("client-good-2", "2026-01-01T10:03:30.000Z", True, "success", SITE_A, CLIENT_A),
        ("client-boundary", "2026-01-01T11:00:00.000Z", True, "success", SITE_A, CLIENT_A),
        ("client-other-site", "2026-01-01T10:02:00.000Z", True, "success", SITE_B, CLIENT_B),
    ):
        repository.create_cycle(
            kind="client", site_id=site, started_at=timestamp,
            cycle_id=cycle_id,
        )
        repository.insert_client_batch([{
            "cycle_id": cycle_id,
            "observed_at": timestamp,
            "site_id": site,
            "client_mac": mac,
            "source_inventory_complete": complete,
            "ssid": "ssid-a",
            "ap_mac": AP_A if complete else None,
            "radio_id": 1 if complete else None,
            "band": "5GHz" if complete else None,
            "channel": 36 if complete else None,
            "rssi": -55 if complete else None,
            "snr": 25 if complete else None,
            "traffic_down": 100 if complete else None,
            "traffic_up": 50 if complete else None,
        }])
        repository.finalize_cycle(
            cycle_id,
            finished_at=timestamp,
            complete=complete,
            result=result,
            source_rows_reported=1,
            items_seen=1,
            items_stored=1,
        )

    timestamp = "2026-01-01T10:00:30.000Z"
    repository.create_cycle(
        kind="ap_dynamic", site_id=SITE_A, started_at=timestamp,
        cycle_id="ap-good",
    )
    repository.insert_ap_batch([({
        "cycle_id": "ap-good",
        "observed_at": timestamp,
        "site_id": SITE_A,
        "ap_mac": AP_A,
        "partial": False,
        "overview_ok": True,
        "wired_uplink_ok": True,
        "lan_traffic_ok": True,
        "radios_ok": True,
        "cpu_util": 20.0,
        "mem_util": None,
    }, [{
        "radio_observed_at": timestamp,
        "band": "5GHz",
        "radio_id": 1,
        "tx_util": 10.0,
        "rx_util": 5.0,
        "interference_util": 2.0,
        "busy_util": 17.0,
        "rx_retry_packets": 1,
        "tx_retry_packets": 2,
        "rx_error_packets": 0,
        "tx_error_packets": 0,
        "rx_drop_packets": 0,
        "tx_drop_packets": 0,
        "radio_rx_mbps": 1.5,
        "radio_tx_mbps": 2.5,
    }])])
    repository.finalize_cycle(
        "ap-good",
        finished_at=timestamp,
        complete=True,
        result="success",
        source_rows_reported=1,
        items_seen=1,
        items_stored=1,
    )
    repository.create_cycle(
        kind="ap_config", site_id=SITE_A, started_at=timestamp,
        cycle_id="config-good",
    )
    repository.finalize_cycle(
        "config-good", finished_at=timestamp,
        complete=True, result="success",
    )


def _seed_visits(repository: VisitRepository) -> tuple[str, str]:
    first = repository.create_or_reuse_start(
        NormalizedVisitStart(
            auth_session_id=AUTH_A,
            site_id=SITE_A,
            client_mac=CLIENT_A,
            authorized_at="2026-01-01T09:59:00.000Z",
            auth_run_number=1,
            authorization_attempt=1,
            final_reason="AUTHORIZED",
            client_ip="192.0.2.10",
            portal_ssid="ssid-a",
            portal_ap_mac=AP_A,
            portal_radio_id=1,
        ),
        now_utc="2026-01-01T09:59:00.000Z",
    )
    assert first.visit_id is not None
    second = repository.create_or_reuse_start(
        NormalizedVisitStart(
            auth_session_id="44444444-4444-4444-8444-444444444444",
            site_id=SITE_A,
            client_mac=CLIENT_B,
            authorized_at="2026-01-01T10:30:00.000Z",
            auth_run_number=1,
            authorization_attempt=1,
            final_reason="AUTHORIZED",
            client_ip=None,
            portal_ssid="ssid-a",
            portal_ap_mac=None,
            portal_radio_id=None,
        ),
        now_utc="2026-01-01T10:30:00.000Z",
    )
    assert second.visit_id is not None
    with closing(repository._connect()) as connection:  # noqa: SLF001
        connection.execute(
            """
            UPDATE visits SET
                device_id=?, initial_snapshot_id=?,
                status='closed', closed_at=?,
                close_reason='client_offline',
                close_time_source='controller_timestamp',
                duration_seconds=300,
                updated_at=?
            WHERE visit_id=?
            """,
            (
                DEVICE_A,
                SNAPSHOT_A,
                "2026-01-01T10:04:00.000Z",
                "2026-01-01T10:04:00.000Z",
                first.visit_id,
            ),
        )
        connection.commit()
    return first.visit_id, second.visit_id


def _seed_registry(repository: VisitorRegistryRepository) -> None:
    with closing(repository._connect()) as connection:  # noqa: SLF001
        connection.execute(
            """
            INSERT INTO visitor_devices (
                device_id, mac, first_seen_at, last_seen_at,
                current_authorized_at, current_captured_at,
                current_snapshot_id, last_auth_session_id, last_site_id,
                last_ip, last_ssid, last_ap_name, last_ap_mac,
                last_rssi, last_snr, snapshot_count, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                DEVICE_A, CLIENT_A,
                "2026-01-01T09:59:00.000Z",
                "2026-01-01T10:00:01.000Z",
                "2026-01-01T09:59:00.000Z",
                "2026-01-01T10:00:01.000Z",
                SNAPSHOT_A, AUTH_A, SITE_A,
                "192.0.2.10", "ssid-a", "AP-A", AP_A,
                -55, 25, 1,
                "2026-01-01T10:00:01.000Z",
                "2026-01-01T10:00:01.000Z",
            ),
        )
        connection.execute(
            """
            INSERT INTO device_snapshots (
                snapshot_id, device_id, event_sha256, schema_version,
                auth_session_id, site_id, requested_mac,
                authorized_at, captured_at, auth_final_reason,
                auth_run_number, authorization_attempt,
                device_type, ssid, ap_mac, radio_id, channel,
                rssi, snr, traffic_down, traffic_up,
                auth_context_json, client_json,
                raw_controller_snapshot_json,
                source_identity, source_path,
                source_offset_start, source_offset_end, processed_at
            ) VALUES (
                ?, ?, ?, 1, ?, ?, ?, ?, ?, 'AUTHORIZED', 1, 1,
                'phone', 'ssid-a', ?, 1, 36, -55, 25, 100, 50,
                '{}', '{}', '{}', 'source', 'fixture', 0, 1, ?
            )
            """,
            (
                SNAPSHOT_A, DEVICE_A, "a" * 64, AUTH_A, SITE_A,
                CLIENT_A, "2026-01-01T09:59:00.000Z",
                "2026-01-01T10:00:01.000Z", AP_A,
                "2026-01-01T10:00:01.000Z",
            ),
        )
        connection.commit()
