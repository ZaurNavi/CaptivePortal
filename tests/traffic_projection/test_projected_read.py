from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

from app.analytics.historical_traffic import (
    HistoricalTrafficReadService,
    HistoricalTrafficSourceUnavailable,
)
from app.analytics.source_gateway import AnalyticsSourceGateway, QueryDeadline
from app.observations.repository import _schema_sql as observation_schema_sql
from app.traffic_projection.models import PROJECTION_VERSION, TrafficProjectionConfig
from app.traffic_projection.read_service import TrafficProjectionReadService
from app.traffic_projection.repository import TrafficProjectionRepository
from app.traffic_projection.service import (
    SEMANTIC_CONTRACT_SHA256,
    TrafficProjectionService,
)
from app.traffic_projection.source import TrafficProjectionSource


SITE = "site-a"
NOW = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class _ObservationReader:
    def __init__(self, path):
        self.path = path

    @contextmanager
    def analytics_read_connection(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()


def _fixture(tmp_path):
    observation = tmp_path / "observations.sqlite3"
    connection = sqlite3.connect(observation)
    connection.executescript(observation_schema_sql())
    for number, minute in enumerate((58, 59)):
        started = f"2026-09-03T09:{minute}:00.000Z"
        finished = f"2026-09-03T09:{minute}:01.000Z"
        cycle_id = f"cycle-{number}"
        connection.execute(
            "INSERT INTO observation_cycles VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (cycle_id, "ap_dynamic", SITE, "completed", started, finished, None,
             1, "success", 1, 1, 1, 0, 0, 0, started, finished),
        )
        connection.execute(
            """INSERT INTO ap_observations(
               cycle_id,observed_at,site_id,ap_mac,partial,overview_ok,
               wired_uplink_ok,lan_traffic_ok,radios_ok,wired_observed_at,
               lan_observed_at,name,wired_download_mbps,wired_upload_mbps,
               wired_download_rate_reason,wired_upload_rate_reason,
               lan_rx_mbps,lan_tx_mbps,lan_rx_rate_reason,lan_tx_rate_reason)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cycle_id, finished, SITE, "AA:BB:CC:DD:EE:FF", 0, 1, 1, 1, 1,
             finished, finished, "AP", 1 + number, 2 + number, "ok", "ok",
             3 + number, 4 + number, "ok", "ok"),
        )
    connection.commit()
    connection.close()
    repository = TrafficProjectionRepository(str(tmp_path / "projection.sqlite3"))
    repository.initialize()
    repository.ensure_version(SEMANTIC_CONTRACT_SHA256, NOW)
    repository.ensure_site(SITE)
    source = TrafficProjectionSource(str(observation))
    for number in range(2):
        repository.upsert_cycle(source.cycle(SITE, f"cycle-{number}"), NOW)
    repository.update_site(
        SITE, status="healthy", source_head_utc="2026-09-03T09:59:00.000Z",
        source_head_cycle_id="cycle-1", last_incremental_progress_at=NOW,
        last_full_reconcile_completed_at=NOW,
        last_full_reconcile_source_head_utc="2026-09-03T09:59:00.000Z",
        last_full_reconcile_source_head_cycle_id="cycle-1",
        last_deep_audit_at=NOW,
        backlog_cycle_count=0,
        available_from_utc="2026-09-03T09:58:01.000Z",
        available_through_utc="2026-09-03T09:59:01.000Z",
        source_watermark_utc="2026-09-03T09:59:01.000Z",
        source_boundary_proof_at=NOW,
        source_boundary_proof_head_utc="2026-09-03T09:59:00.000Z",
        source_boundary_proof_head_cycle_id="cycle-1",
    )
    repository.mark_ready(
        NOW, (SITE,), {SITE: ("2026-09-03T09:59:00.000Z", "cycle-1")}
    )
    repository.activate(
        NOW, (SITE,), {SITE: ("2026-09-03T09:59:00.000Z", "cycle-1")}
    )
    return observation, repository


def test_projection_reuses_existing_historical_semantic_owner(tmp_path):
    observation, repository = _fixture(tmp_path)
    gateway = TrafficProjectionReadService(
        repository, current_observation_db_path=str(observation)
    )
    service = HistoricalTrafficReadService(gateway)
    result = service.get_site_history(
        SITE, from_utc="2026-09-03T09:00:00.000Z",
        to_utc="2026-09-03T10:00:00.000Z",
        evaluated_at_utc="2026-09-03T10:00:00.000Z",
        include_period_statistics=True, include_peak_load=True,
        include_ap_traffic=True, include_ap_share=True,
        current_cycle_id="cycle-1",
    )
    assert result.status in {"ok", "partial"}
    assert result.period_statistics is not None
    assert result.peak_load is not None
    assert result.ap_traffic is not None
    assert result.ap_traffic_share is not None


def test_projected_all_products_match_canonical_raw_semantics(tmp_path):
    observation, repository = _fixture(tmp_path)
    arguments = {
        "site_id": SITE,
        "from_utc": "2026-09-03T09:00:00.000Z",
        "to_utc": "2026-09-03T10:00:00.000Z",
        "evaluated_at_utc": "2026-09-03T10:00:00.000Z",
        "include_period_statistics": True,
        "include_peak_load": True,
        "include_ap_traffic": True,
        "include_ap_share": True,
        "current_cycle_id": "cycle-1",
    }
    raw = HistoricalTrafficReadService(AnalyticsSourceGateway(
        _ObservationReader(observation), None, None
    )).get_site_history(**arguments)
    projected = HistoricalTrafficReadService(TrafficProjectionReadService(
        repository, current_observation_db_path=str(observation)
    )).get_site_history(**arguments)

    assert projected == raw


def test_projected_all_products_reuse_one_range_and_one_ap_evidence_read(
    tmp_path,
):
    observation, repository = _fixture(tmp_path)

    class InspectingGateway(TrafficProjectionReadService):
        range_reads = 0
        ap_evidence_reads = 0
        query_only_values: list[int] = []

        def _projected_combined_rows(self, connection, **kwargs):
            self.range_reads += 1
            self.query_only_values.append(
                int(connection.execute("PRAGMA query_only").fetchone()[0])
            )
            return super()._projected_combined_rows(connection, **kwargs)

        def _load_ap_evidence(self, connection, **kwargs):
            if self._ap_evidence.get() is None:  # noqa: SLF001
                self.ap_evidence_reads += 1
            return super()._load_ap_evidence(connection, **kwargs)

    gateway = InspectingGateway(
        repository, current_observation_db_path=str(observation)
    )
    result = HistoricalTrafficReadService(gateway).get_site_history(
        SITE,
        from_utc="2026-09-03T09:00:00.000Z",
        to_utc="2026-09-03T10:00:00.000Z",
        evaluated_at_utc="2026-09-03T10:00:00.000Z",
        include_period_statistics=True,
        include_peak_load=True,
        include_ap_traffic=True,
        include_ap_share=True,
        current_cycle_id="cycle-1",
    )

    assert result.period_statistics is not None
    assert result.peak_load is not None
    assert result.ap_traffic is not None
    assert result.ap_traffic_share is not None
    assert gateway.range_reads == 1
    assert gateway.ap_evidence_reads == 1
    assert gateway.query_only_values == [1]


def test_no_automatic_raw_fallback_when_projection_not_healthy(tmp_path):
    observation, repository = _fixture(tmp_path)
    repository.update_site(SITE, status="diverged")
    service = HistoricalTrafficReadService(TrafficProjectionReadService(
        repository, current_observation_db_path=str(observation)
    ))
    with pytest.raises(HistoricalTrafficSourceUnavailable):
        service.get_site_history(
            SITE, from_utc="2026-09-03T09:00:00.000Z",
            to_utc="2026-09-03T10:00:00.000Z",
            evaluated_at_utc="2026-09-03T10:00:00.000Z",
        )


def test_read_health_uses_wall_clock_not_historical_evaluated_at(tmp_path):
    observation, repository = _fixture(tmp_path)
    repository.update_site(
        SITE,
        last_full_reconcile_completed_at="2026-09-03T09:59:00.000Z",
    )
    service = HistoricalTrafficReadService(TrafficProjectionReadService(
        repository,
        current_observation_db_path=str(observation),
        clock=lambda: "2026-09-03T11:00:00.000Z",
    ))
    with pytest.raises(HistoricalTrafficSourceUnavailable):
        service.get_site_history(
            SITE,
            from_utc="2026-09-03T09:00:00.000Z",
            to_utc="2026-09-03T10:00:00.000Z",
            evaluated_at_utc="2026-09-03T10:00:00.000Z",
        )


def test_unsupported_active_semantic_contract_fails_closed(tmp_path):
    observation, repository = _fixture(tmp_path)
    with repository.write_connection() as connection:
        connection.execute(
            "UPDATE traffic_projection_versions SET semantic_contract_sha256=? "
            "WHERE status='active'",
            ("f" * 64,),
        )
        connection.commit()
    service = HistoricalTrafficReadService(TrafficProjectionReadService(
        repository, current_observation_db_path=str(observation)
    ))
    with pytest.raises(HistoricalTrafficSourceUnavailable):
        service.get_site_history(
            SITE,
            from_utc="2026-09-03T09:00:00.000Z",
            to_utc="2026-09-03T10:00:00.000Z",
            evaluated_at_utc="2026-09-03T10:00:00.000Z",
        )


def test_projection_query_plan_uses_materialized_indexes(tmp_path):
    _, repository = _fixture(tmp_path)
    with repository.read_connection() as connection:
        plans = tuple(row[3] for row in connection.execute(
            """EXPLAIN QUERY PLAN SELECT cycle_id FROM traffic_projection_cycles
               WHERE projection_version=? AND site_id=?
                 AND source_started_at>=? AND source_started_at<?
               ORDER BY source_started_at,cycle_id""",
            (PROJECTION_VERSION, SITE, "2026-09-03T09:00:00.000Z",
             "2026-09-03T10:00:00.000Z"),
        ))
    assert any("idx_projection_cycles_started" in plan for plan in plans)


def test_projection_read_uses_one_outer_transaction_and_pins_revision(tmp_path):
    observation, repository = _fixture(tmp_path)
    gateway = TrafficProjectionReadService(
        repository, current_observation_db_path=str(observation)
    )
    token = gateway._request.set((SITE, "cycle-1"))  # noqa: SLF001
    try:
        with gateway._connection(  # noqa: SLF001
            "observations", QueryDeadline.after(5)
        ) as connection:
            assert connection.in_transaction is True
            before = connection.execute(
                "SELECT projection_revision FROM traffic_projection_site_state "
                "WHERE projection_version=? AND site_id=?",
                (PROJECTION_VERSION, SITE),
            ).fetchone()[0]
            with repository.write_connection() as writer:
                writer.execute(
                    "UPDATE traffic_projection_site_state "
                    "SET projection_revision=projection_revision+1 "
                    "WHERE projection_version=? AND site_id=?",
                    (PROJECTION_VERSION, SITE),
                )
                writer.commit()
            after = connection.execute(
                "SELECT projection_revision FROM traffic_projection_site_state "
                "WHERE projection_version=? AND site_id=?",
                (PROJECTION_VERSION, SITE),
            ).fetchone()[0]
            assert connection.in_transaction is True
            assert before == after
    finally:
        gateway._request.reset(token)  # noqa: SLF001


def test_all_historical_semantic_statements_run_inside_outer_snapshot(tmp_path):
    observation, repository = _fixture(tmp_path)

    class InspectingGateway(TrafficProjectionReadService):
        statement_transactions: list[bool] = []

        def _one(self, connection, sql, parameters, deadline):
            self.statement_transactions.append(connection.in_transaction)
            return super()._one(connection, sql, parameters, deadline)

        def _all(self, connection, sql, parameters, deadline):
            self.statement_transactions.append(connection.in_transaction)
            return super()._all(connection, sql, parameters, deadline)

    gateway = InspectingGateway(
        repository, current_observation_db_path=str(observation)
    )
    HistoricalTrafficReadService(gateway).get_site_history(
        SITE,
        from_utc="2026-09-03T09:00:00.000Z",
        to_utc="2026-09-03T10:00:00.000Z",
        evaluated_at_utc="2026-09-03T10:00:00.000Z",
        include_period_statistics=True,
        include_peak_load=True,
        include_ap_traffic=True,
        include_ap_share=True,
        current_cycle_id="cycle-1",
    )
    assert len(gateway.statement_transactions) > 1
    assert all(gateway.statement_transactions)


def test_projection_read_preserves_worker_captured_authoritative_source_bounds(
    tmp_path,
):
    observation = tmp_path / "observations.sqlite3"
    connection = sqlite3.connect(observation)
    connection.executescript(observation_schema_sql())

    def insert(cycle_id, started, finished, rate):
        connection.execute(
            "INSERT INTO observation_cycles VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (cycle_id, "ap_dynamic", SITE, "completed", started, finished, None,
             1, "success", 1, 1, 1, 0, 0, 0, started, finished),
        )
        connection.execute(
            """INSERT INTO ap_observations(
               cycle_id,observed_at,site_id,ap_mac,partial,overview_ok,
               wired_uplink_ok,lan_traffic_ok,radios_ok,wired_observed_at,
               lan_observed_at,name,wired_download_mbps,wired_upload_mbps,
               wired_download_rate_reason,wired_upload_rate_reason,
               lan_rx_mbps,lan_tx_mbps,lan_rx_rate_reason,lan_tx_rate_reason)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cycle_id, finished, SITE, "AA:BB:CC:DD:EE:FF", 0, 1, 1, 1, 1,
             finished, finished, "AP", rate, rate, "ok", "ok",
             rate, rate, "ok", "ok"),
        )

    insert(
        "old-authoritative",
        "2026-08-01T09:00:00.000Z",
        "2026-08-01T09:00:01.000Z",
        1.0,
    )
    insert(
        "current",
        "2026-09-03T09:59:00.000Z",
        "2026-09-03T09:59:01.000Z",
        2.0,
    )
    connection.commit()
    repository = TrafficProjectionRepository(str(tmp_path / "projection.sqlite3"))
    service = TrafficProjectionService(
        TrafficProjectionConfig(
            enabled=True,
            db_path=str(tmp_path / "projection.sqlite3"),
            writer_lock_path=str(tmp_path / "projection.lock"),
            source_db_path=str(observation),
            site_ids=(SITE,),
        ),
        repository=repository,
        clock=lambda: "2026-09-03T10:00:00.000Z",
    )
    service.run_once()
    # Exercise projection retention explicitly: an old materialized row may be
    # removed, but the separately captured authoritative Observation boundary
    # must survive unchanged.
    repository.upsert_cycle(
        service.source.cycle(SITE, "old-authoritative"),
        "2026-09-03T10:00:00.000Z",
    )
    assert repository.delete_before(
        SITE, "2026-08-20T00:00:00.000Z"
    ) == 1
    service.mark_ready()
    service.activate()
    assert repository.cycle_count(
        SITE,
        from_utc="2026-07-01T00:00:00.000Z",
        through=("2026-09-03T09:59:00.000Z", "current"),
    ) == 1
    result = HistoricalTrafficReadService(TrafficProjectionReadService(
        repository,
        current_observation_db_path=str(observation),
        clock=lambda: "2026-09-03T10:00:00.000Z",
    )).get_site_history(
        SITE,
        from_utc="2026-09-03T09:00:00.000Z",
        to_utc="2026-09-03T10:00:00.000Z",
        evaluated_at_utc="2026-09-03T10:00:00.000Z",
    )
    assert result.coverage.available_from_utc == "2026-08-01T09:00:01.000Z"
    assert result.coverage.available_through_utc == "2026-09-03T09:59:01.000Z"
    assert result.coverage.source_watermark_utc == "2026-09-03T09:59:01.000Z"
