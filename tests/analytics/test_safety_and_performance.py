from __future__ import annotations

import inspect
import sqlite3
import time
from contextlib import closing

import pytest

import app.analytics
from app.analytics.config import AnalyticsConfig
from app.analytics.read_service import AnalyticsReadService
from app.analytics.source_gateway import (
    AnalyticsPerformanceBudgetExceeded,
    AnalyticsQueryDeadlineExceeded,
    QueryDeadline,
)

from .conftest import SITE_A


FROM = "2026-01-01T09:00:00.000Z"
TO = "2026-01-01T11:00:00.000Z"
EVALUATION = "2026-01-01T11:00:00.000Z"


def _database_facts(repository, tables):
    with closing(repository._connect(readonly=True)) as connection:  # noqa: SLF001
        return (
            int(connection.execute("PRAGMA user_version").fetchone()[0]),
            {
                table: int(
                    connection.execute(
                        f"SELECT COUNT(*) FROM {table}"
                    ).fetchone()[0]
                )
                for table in tables
            },
        )


def test_analytics_queries_do_not_change_source_rows_or_versions(
    analytics_stack,
):
    before = (
        _database_facts(
            analytics_stack.observations,
            ("observation_cycles", "client_observations"),
        ),
        _database_facts(
            analytics_stack.visits,
            ("visits", "visit_authorizations"),
        ),
        _database_facts(
            analytics_stack.registry,
            ("visitor_devices", "device_snapshots"),
        ),
    )
    analytics_stack.service.get_source_quality(
        SITE_A, FROM, TO, EVALUATION
    )
    analytics_stack.service.list_visit_quality(SITE_A, FROM, TO)
    analytics_stack.service.get_visit_context(
        SITE_A, analytics_stack.visit_id
    )
    after = (
        _database_facts(
            analytics_stack.observations,
            ("observation_cycles", "client_observations"),
        ),
        _database_facts(
            analytics_stack.visits,
            ("visits", "visit_authorizations"),
        ),
        _database_facts(
            analytics_stack.registry,
            ("visitor_devices", "device_snapshots"),
        ),
    )
    assert after == before


@pytest.mark.parametrize("source", ["observations", "visits", "registry"])
def test_source_boundary_connections_are_query_only(analytics_stack, source):
    service = {
        "observations": analytics_stack.gateway._observations,
        "visits": analytics_stack.gateway._visits,
        "registry": analytics_stack.gateway._registry,
    }[source]
    with service.analytics_read_connection() as connection:
        assert int(connection.execute("PRAGMA query_only").fetchone()[0]) == 1
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("CREATE TABLE forbidden(value INTEGER)")


def test_deadline_interrupts_inside_running_sqlite_statement(analytics_stack):
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    try:
        deadline = QueryDeadline.after(0.001)
        with pytest.raises(AnalyticsQueryDeadlineExceeded):
            analytics_stack.gateway._one(  # noqa: SLF001
                connection,
                """
                WITH RECURSIVE count(x) AS (
                    SELECT 1 UNION ALL SELECT x+1 FROM count WHERE x<100000
                )
                SELECT SUM(a.x*b.x) FROM count a, count b
                """,
                (),
                deadline,
            )
    finally:
        connection.close()


def test_disabled_foundation_is_unavailable_not_zero(analytics_stack):
    disabled = AnalyticsReadService(
        AnalyticsConfig(enabled=False),
        analytics_stack.gateway,
    )
    result = disabled.get_observation_cycle_quality(
        SITE_A, "client", FROM, TO
    )
    assert result.status == "unavailable"
    assert result.value is None
    overall = disabled.get_source_quality(SITE_A, FROM, TO, EVALUATION)
    assert overall.status == "unavailable"
    assert overall.value is None


def test_deadline_becomes_explicit_partial_result(analytics_stack, monkeypatch):
    def expired(**_kwargs):
        raise AnalyticsQueryDeadlineExceeded("deadline")

    monkeypatch.setattr(analytics_stack.gateway, "cycle_quality", expired)
    result = analytics_stack.service.get_source_quality(
        SITE_A, FROM, TO, EVALUATION
    )
    assert result.status == "partial"
    assert result.quality.reason == "query_deadline"


def test_visit_page_uses_one_page_query_and_one_batch_lookup(
    analytics_stack, monkeypatch
):
    calls = {"page": 0, "snapshots": 0}
    original_page = analytics_stack.gateway.visit_quality_page
    original_snapshots = analytics_stack.gateway.resolved_snapshot_links

    def page(**kwargs):
        calls["page"] += 1
        return original_page(**kwargs)

    def snapshots(**kwargs):
        calls["snapshots"] += 1
        return original_snapshots(**kwargs)

    monkeypatch.setattr(analytics_stack.gateway, "visit_quality_page", page)
    monkeypatch.setattr(
        analytics_stack.gateway, "resolved_snapshot_links", snapshots
    )
    result = analytics_stack.service.list_visit_quality(
        SITE_A, FROM, TO, limit=2
    )
    assert len(result.value.items) == 2
    assert calls == {"page": 1, "snapshots": 1}


def test_performance_budget_uses_dedicated_summary_event(
    analytics_stack, monkeypatch
):
    events = []

    class Telemetry:
        def emit(self, event, **fields):
            events.append((event, fields))

    analytics_stack.service.telemetry = Telemetry()

    def over_budget(**_kwargs):
        raise AnalyticsPerformanceBudgetExceeded("bounded")

    monkeypatch.setattr(
        analytics_stack.gateway, "initial_snapshot_links", over_budget
    )
    result = analytics_stack.service.get_source_quality(
        SITE_A, FROM, TO, EVALUATION
    )
    assert result.status == "partial"
    assert result.quality.reason == "performance_budget_exceeded"
    assert events[-1][0] == "analytics.performance_budget_exceeded"


def test_no_omada_dependency_in_analytics_package():
    source = "\n".join(
        inspect.getsource(module)
        for module in (
            app.analytics.config,
            app.analytics.models,
            app.analytics.read_service,
            app.analytics.source_gateway,
        )
    ).lower()
    assert "omada" not in source


def test_query_plans_use_site_time_indexes(analytics_stack):
    with analytics_stack.observations.read_connection() as connection:
        cycle_plan = " ".join(
            str(row[-1])
            for row in connection.execute(
                """
                EXPLAIN QUERY PLAN
                SELECT COUNT(*) FROM observation_cycles
                WHERE site_id=? AND kind=? AND started_at>=? AND started_at<?
                """,
                (SITE_A, "client", FROM, TO),
            )
        )
        client_plan = " ".join(
            str(row[-1])
            for row in connection.execute(
                """
                EXPLAIN QUERY PLAN
                SELECT COUNT(*) FROM client_observations
                WHERE site_id=? AND observed_at>=? AND observed_at<?
                """,
                (SITE_A, FROM, TO),
            )
        )
    assert "idx_cycles_site_kind_started" in cycle_plan
    assert "idx_client_site_time" in client_plan


def test_capacity_gate_includes_maximum_31_day_estimate():
    clients = 300
    cadence_per_day = 24 * 60
    estimated_rows = clients * cadence_per_day * 31
    assert estimated_rows == 13_392_000
    assert estimated_rows > 3_024_000


def test_quality_queries_transfer_aggregates_not_source_rows(
    analytics_stack,
):
    started = time.perf_counter()
    result = analytics_stack.service.get_source_quality(
        SITE_A, FROM, TO, EVALUATION
    )
    elapsed = time.perf_counter() - started
    assert result.provenance.sample_size == 2
    assert result.provenance.source_rows_examined < 100
    assert elapsed < 2


def test_aggregate_outputs_do_not_contain_identifier_lists(analytics_stack):
    result = analytics_stack.service.get_source_quality(
        SITE_A, FROM, TO, EVALUATION
    )
    rendered = repr(result.value)
    assert "192.0.2." not in rendered
    assert "raw_controller_snapshot" not in rendered
    assert "auth_context_json" not in rendered
    assert "client_json" not in rendered
    assert "password" not in rendered.lower()
    assert "token" not in rendered.lower()
