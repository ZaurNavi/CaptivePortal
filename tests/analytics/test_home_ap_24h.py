from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager

import pytest

from app.admin_web.home_ap_24h_serialization import serialize_home_ap_24h
from app.analytics.home_ap_24h import (
    BUCKET_COUNT,
    HomeAp24ReadService,
    HomeAp24SourceUnavailable,
    _read_snapshot,
)
from app.analytics.source_gateway import QueryDeadline
from app.analytics.source_gateway import AnalyticsQueryDeadlineExceeded
from app.current_state.config import current_state_config_from_settings
from app.current_state.models import CurrentStateCycle
from app.current_state.normalizer import canonical_scope
from app.current_state.read_service import CurrentStateReadService
from app.current_state.repository import CurrentStateRepository
from app.observations.models import ObservationConfig
from app.observations.read_service import ObservationReadService
from app.observations.repository import ObservationRepository


UTC = timezone.utc
SITE = "a" * 24
AP = "AA:BB:CC:DD:EE:01"
OTHER_AP = "AA:BB:CC:DD:EE:02"
ANCHOR = datetime(2026, 8, 28, 12, tzinfo=UTC)


def stamp(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


@pytest.fixture
def sources(tmp_path):
    cs_path = tmp_path / "current.sqlite3"
    obs_path = tmp_path / "observations.sqlite3"
    config = current_state_config_from_settings({
        "current_state_enabled": "true",
        "current_state_db_path": str(cs_path),
        "current_state_site_ids": SITE,
        "current_state_client_ssids_json": '["guest"]',
        "observation_db_path": str(obs_path),
    })
    current = CurrentStateRepository(config)
    current.initialize()
    obs_config = ObservationConfig(
        enabled=True, db_path=str(obs_path), dynamic_retention_days=180,
        config_retention_days=730, cleanup_initial_delay_seconds=900,
        cleanup_interval_seconds=86400, cleanup_batch_size=5000,
        cleanup_max_duration_seconds=30, shutdown_timeout_seconds=20,
    )
    observations = ObservationRepository(obs_config)
    observations.initialize(stamp(ANCHOR - timedelta(days=2)))
    return current, observations


def current_cycle(repository, moment, rows, *, result="success", cycle_id=None):
    identifier = cycle_id or f"cs-{int(moment.timestamp())}"
    scope_json, scope_hash = canonical_scope("ap", SITE, ())
    complete = result == "success"
    cycle = CurrentStateCycle(
        cycle_id=identifier, kind="ap", site_id=SITE,
        capture_started_at=stamp(moment), capture_finished_at=stamp(moment),
        complete=complete, result=result, source_scope_version=1,
        source_scope_json=scope_json, source_scope_hash=scope_hash,
        source_rows_reported=len(rows), items_seen=len(rows),
        items_stored=len(rows), items_skipped=0, unidentified_count=0,
        duplicate_identity_count=0, unknown_status_count=0,
        error_count=0 if complete else 1, data_quality_warning_count=0,
        page_count=1, failure_category=None if complete else "controller_error",
        duration_ms=5, created_at=stamp(moment),
    )
    prepared = []
    for mac, status in rows:
        prepared.append({
            "cycle_id": identifier, "cycle_kind": "ap", "site_id": SITE,
            "observed_at": stamp(moment), "ap_mac": mac, "name": f"AP-{mac[-2:]}",
            "ip": None, "model": "EAP", "firmware_version": None,
            "status_code": status, "status_classification": "unknown",
            "last_seen_ms": None, "controller_uptime": None, "uptime_raw": None,
        })
    repository.publish_cycle(cycle, ap_rows=prepared)


def observation_cycle(
    repository,
    moment,
    *,
    partial=False,
    parent_partial=False,
    parent_result=None,
    mac=AP,
    failed_section=None,
):
    identifier = f"obs-{int(moment.timestamp())}-{mac[-2:]}"
    repository.create_cycle(kind="ap_dynamic", site_id=SITE, started_at=stamp(moment), cycle_id=identifier)
    repository.insert_ap_batch([({
        "cycle_id": identifier, "observed_at": stamp(moment), "site_id": SITE,
        "ap_mac": mac, "partial": partial,
        "overview_ok": not partial and failed_section != "overview",
        "wired_uplink_ok": failed_section != "wired_uplink",
        "lan_traffic_ok": failed_section != "lan_traffic",
        "radios_ok": failed_section != "radios",
        "overview_observed_at": stamp(moment), "wired_observed_at": stamp(moment),
        "lan_observed_at": stamp(moment), "name": "Observed AP", "model": "EAP",
    }, ())])
    result = parent_result or ("partial" if parent_partial else "success")
    repository.finalize_cycle(
        identifier, finished_at=stamp(moment), complete=result == "success",
        result=result, items_seen=1,
        items_stored=1,
    )


def service(current, observations, *, budget=200):
    return HomeAp24ReadService(
        CurrentStateReadService(current), ObservationReadService(observations),
        current_state_ap_interval_seconds=60, quality_gap_seconds=180,
        observation_dynamic_max_requests=budget,
    )


def read(value):
    return value.get_home_ap_24h(
        SITE, evaluated_at_utc=ANCHOR, limit=20,
        deadline=QueryDeadline.after(5),
    )


def jittered_samples(anchor, *, first_index=-1, omit=None, state_at=None):
    start = anchor - timedelta(hours=24)
    pattern_ms = (137, 811, 49, 693, 421, 277, 959)
    samples = []
    for index in range(first_index, 1441):
        moment = start + timedelta(
            seconds=60 * index,
            milliseconds=pattern_ms[index % len(pattern_ms)],
        )
        if moment >= anchor or (omit is not None and omit(moment, start)):
            continue
        state = "operational" if state_at is None else state_at(moment, start)
        reason = (
            "fresh_online_evidence"
            if state == "operational"
            else "controller_reported_offline"
        )
        samples.append((moment, state, reason, stamp(moment)))
    return samples


def read_injected_samples(samples, *, anchor):
    source = HomeAp24ReadService(
        object(), object(),
        current_state_ap_interval_seconds=60,
        quality_gap_seconds=180,
        observation_dynamic_max_requests=200,
    )
    current = {
        "samples": {AP: samples},
        "roster": {AP},
        "identity": {AP: (samples[0][0], "AP", "EAP")},
        "source": {
            "status": "operational",
            "schema_version": 1,
            "first_evidence_at": samples[0][3],
            "last_evidence_at": samples[-1][3],
            "complete_cycle_count": len(samples),
            "partial_cycle_count": 0,
            "failed_cycle_count": 0,
            "max_gap_seconds": 61,
        },
    }
    observations = {
        "rows": {},
        "aggregates": {},
        "roster": set(),
        "identity": {},
        "source": {
            "status": "unknown",
            "schema_version": 1,
            "first_evidence_at": None,
            "last_evidence_at": None,
            "complete_cycle_count": 0,
            "partial_cycle_count": 0,
            "failed_cycle_count": 0,
            "max_gap_seconds": None,
        },
    }
    source._read_current = lambda *_args, **_kwargs: current
    source._read_observations = lambda *_args, **_kwargs: observations
    return source.get_home_ap_24h(
        SITE,
        evaluated_at_utc=anchor,
        limit=20,
        deadline=QueryDeadline.after(5),
    )


def assert_exact_duration_partition(item):
    history = item["history"]
    assert sum(history[field] for field in (
        "operational_seconds",
        "unavailable_seconds",
        "unknown_evidence_seconds",
        "short_history_seconds",
    )) == 86400
    assert len(item["timeline"]) == 96
    assert all(
        sum(bucket[field] for field in (
            "operational_seconds",
            "unavailable_seconds",
            "unknown_evidence_seconds",
            "short_history_seconds",
        )) == 900
        for bucket in item["timeline"]
    )
    assert sum(
        bucket[field]
        for bucket in item["timeline"]
        for field in (
            "operational_seconds",
            "unavailable_seconds",
            "unknown_evidence_seconds",
            "short_history_seconds",
        )
    ) == 86400


def test_millisecond_jitter_continuous_history_partitions_exactly_and_serializes():
    anchor = datetime(2026, 8, 28, 12, 17, 53, 791000, tzinfo=UTC)
    result = read_injected_samples(jittered_samples(anchor), anchor=anchor)
    item = result["items"][0]

    assert item["history"]["operational_seconds"] == 86400
    assert item["history"]["unavailable_seconds"] == 0
    assert item["history"]["unknown_evidence_seconds"] == 0
    assert item["history"]["short_history_seconds"] == 0
    assert item["history"]["coverage_status"] == "complete"
    assert_exact_duration_partition(item)
    assert serialize_home_ap_24h(result)["items"][0]["timeline"]


def test_millisecond_jitter_mixed_state_and_source_gap_partition_exactly():
    anchor = datetime(2026, 8, 28, 12, 17, 53, 791000, tzinfo=UTC)

    def omit(moment, start):
        return start + timedelta(hours=6) <= moment < start + timedelta(
            hours=6, minutes=10
        )

    def state_at(moment, start):
        return (
            "operational"
            if moment < start + timedelta(hours=12)
            else "unavailable"
        )

    result = read_injected_samples(
        jittered_samples(anchor, omit=omit, state_at=state_at),
        anchor=anchor,
    )
    item = result["items"][0]

    assert item["history"]["operational_seconds"] > 0
    assert item["history"]["unavailable_seconds"] > 0
    assert item["history"]["unknown_evidence_seconds"] > 0
    assert item["history"]["short_history_seconds"] == 0
    assert_exact_duration_partition(item)


def test_millisecond_jitter_first_evidence_preserves_short_history_partition():
    anchor = datetime(2026, 8, 28, 12, 17, 53, 791000, tzinfo=UTC)
    result = read_injected_samples(
        jittered_samples(anchor, first_index=180),
        anchor=anchor,
    )
    item = result["items"][0]

    assert item["history"]["short_history_seconds"] > 0
    assert item["history"]["unknown_evidence_seconds"] == 0
    assert item["history"]["coverage_status"] == "complete"
    assert_exact_duration_partition(item)


def test_mapper_semantics_absence_reappearance_and_fixed_buckets(sources):
    current, observations = sources
    current_cycle(current, ANCHOR - timedelta(minutes=8), [(AP, 1), (OTHER_AP, 3)])
    current_cycle(current, ANCHOR - timedelta(minutes=6), [(OTHER_AP, 3)])
    current_cycle(current, ANCHOR - timedelta(minutes=4), [(AP, 0), (OTHER_AP, 3)])
    current_cycle(current, ANCHOR - timedelta(minutes=2), [(AP, 1), (OTHER_AP, 3)])
    observation_cycle(observations, ANCHOR - timedelta(minutes=2))
    result = read(service(current, observations))
    assert result["window"]["bucket_count"] == BUCKET_COUNT
    assert all(len(item["timeline"]) == 96 for item in result["items"])
    by_mac = {item["ap_mac"]: item for item in result["items"]}
    assert by_mac[AP]["current"]["status"] == "operational"
    assert by_mac[AP]["history"]["unavailable_seconds"] > 0
    assert by_mac[AP]["history"]["unknown_evidence_seconds"] > 0
    assert any(bucket["ap_state_reason"] == "not_in_complete_inventory" for bucket in by_mac[AP]["timeline"])
    assert by_mac[OTHER_AP]["current"]["status"] == "unknown"


@pytest.mark.parametrize("raw_status,product_status", [
    (1, "operational"),
    (0, "unavailable"),
    (3, "unknown"),
    (77, "unknown"),
    (None, "unknown"),
])
def test_historical_raw_status_uses_shared_mapper_not_persisted_label(
    sources, raw_status, product_status
):
    current, observations = sources
    current_cycle(current, ANCHOR - timedelta(minutes=2), [(AP, raw_status)])

    result = read(service(current, observations))

    item = result["items"][0]
    assert item["current"]["status"] == product_status
    assert item["history"]["status"] == product_status
    assert item["history"]["unavailable_seconds"] == (
        120 if product_status == "unavailable" else 0
    )


@pytest.mark.parametrize("result_name", ["partial", "failed"])
def test_non_authoritative_current_cycles_never_create_ap_state_sample(
    sources, result_name
):
    current, observations = sources
    current_cycle(current, ANCHOR - timedelta(minutes=2), [(AP, 1)], cycle_id="good")
    current_cycle(
        current, ANCHOR - timedelta(minutes=1), [(AP, 0)],
        result=result_name, cycle_id=f"ignored-{result_name}",
    )

    item = read(service(current, observations))["items"][0]

    assert item["current"]["status"] == "operational"
    assert item["history"]["unavailable_seconds"] == 0


def test_half_open_window_includes_from_and_excludes_to(sources):
    current, observations = sources
    current_cycle(current, ANCHOR - timedelta(hours=24), [(AP, 1)], cycle_id="at-from")
    current_cycle(current, ANCHOR, [(OTHER_AP, 1)], cycle_id="at-to")

    result = read(service(current, observations))

    assert [item["ap_mac"] for item in result["items"]] == [AP]
    assert result["window"]["from_utc"] == stamp(ANCHOR - timedelta(hours=24))
    assert result["window"]["to_utc"] == stamp(ANCHOR)
    assert sum(
        (datetime.fromisoformat(bucket["to_utc"].replace("Z", "+00:00"))
         - datetime.fromisoformat(bucket["from_utc"].replace("Z", "+00:00"))).total_seconds()
        for bucket in result["items"][0]["timeline"]
    ) == 86400


def test_first_evidence_inside_window_is_short_history_not_problem_duration(sources):
    current, observations = sources
    current_cycle(current, ANCHOR - timedelta(hours=3), [(AP, 1)])

    item = read(service(current, observations))["items"][0]

    assert item["history"]["history_eligible_from"] == stamp(ANCHOR - timedelta(hours=3))
    assert item["history"]["short_history_seconds"] == 21 * 3600
    assert item["history"]["unknown_evidence_seconds"] == 3 * 3600 - 180
    assert item["history"]["unavailable_seconds"] == 0


def test_bucket_counts_logical_samples_not_carried_intervals(sources):
    current, observations = sources
    current_cycle(current, ANCHOR - timedelta(hours=24, minutes=1), [(AP, 1)])
    current_cycle(current, ANCHOR - timedelta(hours=23, minutes=59), [(AP, 1)])

    result = read(service(current, observations))

    counts = [bucket["authoritative_state_sample_count"] for bucket in result["items"][0]["timeline"]]
    assert counts[0] == 1
    assert sum(counts) == 1
    assert result["items"][0]["history"]["authoritative_sample_count"] == 1


def test_observation_carry_in_partial_row_does_not_degrade_window(sources):
    current, observations = sources
    current_cycle(current, ANCHOR - timedelta(minutes=2), [(AP, 1)])
    observation_cycle(observations, ANCHOR - timedelta(hours=24, seconds=60), partial=True)
    observation_cycle(observations, ANCHOR - timedelta(hours=23, minutes=59))

    result = read(service(current, observations))

    quality = result["items"][0]["observation_quality"]
    assert quality["diagnostic_partial_sample_count"] == 0
    assert quality["section_problem_counts"]["overview"] == 0


def test_parent_partial_does_not_poison_complete_ap_local_row(sources):
    current, observations = sources
    current_cycle(current, ANCHOR - timedelta(minutes=2), [(AP, 1)])
    observation_cycle(observations, ANCHOR - timedelta(minutes=2), parent_partial=True)
    result = read(service(current, observations))
    assert result["sources"]["observations"]["status"] == "degraded"
    assert result["items"][0]["observation_quality"]["status"] != "degraded"
    assert result["items"][0]["observation_quality"]["complete_sample_count"] == 1


@pytest.mark.parametrize("parent_result", ["failed", "shutdown"])
def test_failed_parent_never_supplies_complete_ap_local_evidence(
    sources, parent_result
):
    current, observations = sources
    current_cycle(current, ANCHOR - timedelta(minutes=2), [(AP, 1)])
    observation_cycle(
        observations,
        ANCHOR - timedelta(minutes=2),
        parent_result=parent_result,
    )

    result = read(service(current, observations))

    source = result["sources"]["observations"]
    quality = result["items"][0]["observation_quality"]
    assert source["partial_cycle_count"] == 0
    assert source["failed_cycle_count"] == 1
    assert quality["complete_sample_count"] == 0
    assert quality["status"] == "unknown"


def test_observation_cycle_quality_categories_are_non_overlapping(sources):
    current, observations = sources
    current_cycle(current, ANCHOR - timedelta(minutes=2), [(AP, 1)])
    observation_cycle(
        observations,
        ANCHOR - timedelta(minutes=3),
        parent_partial=True,
    )
    observation_cycle(
        observations,
        ANCHOR - timedelta(minutes=2),
        parent_result="failed",
    )

    source = read(service(current, observations))["sources"]["observations"]

    assert source["partial_cycle_count"] == 1
    assert source["failed_cycle_count"] == 1
    assert source["status"] == "degraded"


def test_running_cycle_requires_completed_history_before_operational(sources):
    current, observations = sources
    current_cycle(current, ANCHOR - timedelta(minutes=2), [(AP, 1)])
    observations.create_cycle(
        kind="ap_dynamic",
        site_id=SITE,
        started_at=stamp(ANCHOR - timedelta(minutes=1)),
        cycle_id="running-only",
    )

    source = read(service(current, observations))["sources"]["observations"]

    assert source["status"] == "unknown"
    assert source["complete_cycle_count"] == 0
    assert source["partial_cycle_count"] == 0
    assert source["failed_cycle_count"] == 0


def test_current_running_cycle_does_not_degrade_completed_history(sources):
    current, observations = sources
    current_cycle(current, ANCHOR - timedelta(minutes=2), [(AP, 1)])
    observation_cycle(observations, ANCHOR - timedelta(minutes=2))
    observations.create_cycle(
        kind="ap_dynamic",
        site_id=SITE,
        started_at=stamp(ANCHOR - timedelta(minutes=1)),
        cycle_id="current-running",
    )

    source = read(service(current, observations))["sources"]["observations"]

    assert source["status"] == "operational"
    assert source["complete_cycle_count"] == 1


def test_abandoned_cycle_is_not_operational_history(sources):
    current, observations = sources
    current_cycle(current, ANCHOR - timedelta(minutes=2), [(AP, 1)])
    abandoned_at = stamp(ANCHOR - timedelta(minutes=1))
    observations.create_cycle(
        kind="ap_dynamic",
        site_id=SITE,
        started_at=abandoned_at,
        cycle_id="abandoned-only",
    )
    with sqlite3.connect(observations.db_path) as connection:
        connection.execute(
            """
            UPDATE observation_cycles
            SET state='abandoned', abandoned_at=?, complete=0, updated_at=?
            WHERE cycle_id='abandoned-only'
            """,
            (abandoned_at, abandoned_at),
        )

    source = read(service(current, observations))["sources"]["observations"]

    assert source["status"] == "degraded"
    assert source["complete_cycle_count"] == 0
    assert source["partial_cycle_count"] == 0
    assert source["failed_cycle_count"] == 0


def test_ap_local_partial_is_diagnostic_only(sources):
    current, observations = sources
    current_cycle(current, ANCHOR - timedelta(minutes=2), [(AP, 1)])
    observation_cycle(observations, ANCHOR - timedelta(minutes=2), partial=True)
    result = read(service(current, observations))
    item = result["items"][0]
    assert item["current"]["status"] == "operational"
    assert item["observation_quality"]["status"] == "degraded"
    assert item["observation_quality"]["section_problem_counts"]["overview"] == 1


@pytest.mark.parametrize("section", ["overview", "wired_uplink", "lan_traffic", "radios"])
def test_each_observation_section_failure_is_diagnostic_not_ap_state(
    sources, section
):
    current, observations = sources
    current_cycle(current, ANCHOR - timedelta(minutes=2), [(AP, 1)])
    observation_cycle(
        observations, ANCHOR - timedelta(minutes=2), failed_section=section
    )

    item = read(service(current, observations))["items"][0]

    assert item["current"]["status"] == "operational"
    assert item["observation_quality"]["status"] == "degraded"
    assert item["observation_quality"]["section_problem_counts"][section] == 1


def test_rotation_missing_row_in_parent_partial_cycle_is_unknown_not_fault(sources):
    current, observations = sources
    current_cycle(current, ANCHOR - timedelta(minutes=2), [(AP, 1), (OTHER_AP, 1)])
    observation_cycle(
        observations, ANCHOR - timedelta(minutes=2), parent_partial=True, mac=AP
    )

    by_mac = {item["ap_mac"]: item for item in read(service(current, observations))["items"]}

    assert by_mac[AP]["observation_quality"]["complete_sample_count"] == 1
    assert by_mac[OTHER_AP]["observation_quality"]["status"] == "unknown"
    assert by_mac[OTHER_AP]["current"]["status"] == "operational"


def test_observation_capacity_is_source_degradation_not_ap_fault(sources):
    current, observations = sources
    current_cycle(current, ANCHOR - timedelta(minutes=2), [(AP, 1), (OTHER_AP, 1)])
    observation_cycle(observations, ANCHOR - timedelta(minutes=2), mac=AP)
    observation_cycle(observations, ANCHOR - timedelta(minutes=1), mac=OTHER_AP)
    result = read(service(current, observations, budget=4))
    assert result["sources"]["observations"]["status"] == "degraded"
    assert "observation_cycle_capacity_exceeded" in result["sources"]["observations"]["reason_codes"]
    assert result["summary"]["current"]["operational"] == 2


def test_page_is_canonical_mac_keyset_and_summary_covers_full_roster(sources):
    current, observations = sources
    current_cycle(current, ANCHOR - timedelta(minutes=1), [(OTHER_AP, 1), (AP, 1)])
    first = service(current, observations).get_home_ap_24h(
        SITE, evaluated_at_utc=ANCHOR, limit=1, deadline=QueryDeadline.after(5)
    )
    second = service(current, observations).get_home_ap_24h(
        SITE, evaluated_at_utc=ANCHOR, after_ap_mac=first["items"][0]["ap_mac"],
        limit=1, deadline=QueryDeadline.after(5),
    )
    assert first["summary"]["ap_count_in_window"] == 2
    assert first["items"][0]["ap_mac"] == AP
    assert second["items"][0]["ap_mac"] == OTHER_AP


def test_read_model_does_not_mutate_source_databases(sources):
    current, observations = sources
    current_cycle(current, ANCHOR - timedelta(minutes=1), [(AP, 1)])
    before = (
        current.db_path.stat().st_size,
        observations.db_path.stat().st_size,
    )
    read(service(current, observations))
    after = (current.db_path.stat().st_size, observations.db_path.stat().st_size)
    assert after == before
    with current.read_connection() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1


class CountingReadService:
    def __init__(self, wrapped):
        self.wrapped = wrapped
        self.execute_count = 0

    @contextmanager
    def analytics_read_connection(self):
        with self.wrapped.analytics_read_connection() as connection:
            owner = self

            class CountingConnection:
                def execute(self, *args, **kwargs):
                    owner.execute_count += 1
                    return connection.execute(*args, **kwargs)

                def __getattr__(self, name):
                    return getattr(connection, name)

            yield CountingConnection()


def test_source_sql_statement_count_is_fixed_not_per_ap(sources):
    current, observations = sources
    current_cycle(current, ANCHOR - timedelta(minutes=2), [(AP, 1), (OTHER_AP, 1)])
    observation_cycle(observations, ANCHOR - timedelta(minutes=2), mac=AP)
    counted_current = CountingReadService(CurrentStateReadService(current))
    counted_observations = CountingReadService(ObservationReadService(observations))

    value = HomeAp24ReadService(
        counted_current,
        counted_observations,
        current_state_ap_interval_seconds=60,
        quality_gap_seconds=180,
        observation_dynamic_max_requests=200,
    )
    read(value)

    # Current State uses three and Observations uses two fixed product SELECTs,
    # plus the shared read-snapshot controls; AP count adds no source round trip.
    assert counted_current.execute_count == 6
    assert counted_observations.execute_count == 5
    with observations.read_connection() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1


class BrokenReadService:
    def analytics_read_connection(self):
        raise OSError("private path must never escape")


def test_both_unavailable_fail_closed_without_exposing_source_details():
    value = HomeAp24ReadService(
        BrokenReadService(), BrokenReadService(),
        current_state_ap_interval_seconds=60, quality_gap_seconds=180,
        observation_dynamic_max_requests=200,
    )
    with pytest.raises(HomeAp24SourceUnavailable, match="sources are unavailable"):
        read(value)


def test_one_unavailable_source_returns_independent_degraded_axis(sources):
    current, observations = sources
    observation_cycle(observations, ANCHOR - timedelta(minutes=2))
    value = HomeAp24ReadService(
        BrokenReadService(), ObservationReadService(observations),
        current_state_ap_interval_seconds=60, quality_gap_seconds=180,
        observation_dynamic_max_requests=200,
    )
    result = read(value)
    assert result["block_status"] == "degraded"
    assert result["sources"]["current_state"]["status"] == "unavailable"
    assert result["items"][0]["current"]["status"] == "unknown"
    assert result["items"][0]["observation_quality"]["complete_sample_count"] == 1
    assert all(
        bucket["ap_state_reason"] == "source_unavailable"
        and bucket["unknown_evidence_seconds"] == 900
        and bucket["short_history_seconds"] == 0
        for bucket in result["items"][0]["timeline"]
    )


def test_readable_empty_history_is_unknown_not_infrastructure_failure(sources):
    current, observations = sources
    result = read(service(current, observations))
    assert result["block_status"] == "unknown"
    assert result["block_reason"] == "no_historical_evidence"
    assert result["summary"]["ap_count_in_window"] == 0


def test_latest_complete_inventory_remains_in_roster_outside_history_window(sources):
    current, observations = sources
    current_cycle(current, ANCHOR - timedelta(hours=25), [(AP, 1)])

    result = read(service(current, observations))

    assert result["summary"]["ap_count_in_window"] == 1
    assert [item["ap_mac"] for item in result["items"]] == [AP]
    assert result["items"][0]["current"] == {
        "status": "unknown",
        "reason_code": "current_state_source_gap",
        "observed_at": None,
        "freshness_status": "unavailable",
    }
    assert result["items"][0]["history"]["coverage_status"] == "insufficient_data"
    assert result["items"][0]["history"]["unknown_evidence_seconds"] == 86400
    assert result["items"][0]["history"]["short_history_seconds"] == 0
    assert all(
        bucket["ap_state_reason"] == "current_state_source_gap"
        and bucket["short_history_seconds"] == 0
        and bucket["unknown_evidence_seconds"] == 900
        for bucket in result["items"][0]["timeline"]
    )


def test_expired_deadline_interrupts_before_source_query(sources):
    current, observations = sources
    with pytest.raises(AnalyticsQueryDeadlineExceeded):
        service(current, observations).get_home_ap_24h(
            SITE, evaluated_at_utc=ANCHOR, limit=20,
            deadline=QueryDeadline.after(0),
        )


def test_progress_handler_interrupts_running_statement_and_is_cleared():
    import sqlite3

    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA user_version=1")
    ticks = iter(range(1000000))
    deadline = QueryDeadline(20, lambda: next(ticks))
    with pytest.raises(AnalyticsQueryDeadlineExceeded):
        with _read_snapshot(connection, deadline, 1):
            connection.execute(
                "WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n WHERE x<1000000) SELECT sum(x) FROM n"
            ).fetchone()
    assert connection.execute("SELECT 1").fetchone()[0] == 1
    connection.close()


@pytest.mark.parametrize("delta_seconds, expected_coverage", [
    (180, "complete"),
    (181, "partial"),
])
def test_current_state_gap_boundary_is_deterministic(sources, delta_seconds, expected_coverage):
    current, observations = sources
    first = ANCHOR - timedelta(seconds=delta_seconds + 60)
    current_cycle(current, first, [(AP, 1)], cycle_id="edge-a")
    current_cycle(current, first + timedelta(seconds=delta_seconds), [(AP, 1)], cycle_id="edge-b")
    result = read(service(current, observations))
    assert result["items"][0]["history"]["coverage_status"] == expected_coverage


def test_other_site_rows_never_enter_roster(sources):
    current, observations = sources
    current_cycle(current, ANCHOR - timedelta(minutes=1), [(AP, 1)])
    scope_json, scope_hash = canonical_scope("ap", "b" * 24, ())
    other = CurrentStateCycle(
        cycle_id="other-site", kind="ap", site_id="b" * 24,
        capture_started_at=stamp(ANCHOR - timedelta(minutes=1)),
        capture_finished_at=stamp(ANCHOR - timedelta(minutes=1)), complete=True,
        result="success", source_scope_version=1, source_scope_json=scope_json,
        source_scope_hash=scope_hash, source_rows_reported=1, items_seen=1,
        items_stored=1, items_skipped=0, unidentified_count=0,
        duplicate_identity_count=0, unknown_status_count=0, error_count=0,
        data_quality_warning_count=0, page_count=1, failure_category=None,
        duration_ms=1, created_at=stamp(ANCHOR - timedelta(minutes=1)),
    )
    current.publish_cycle(other, ap_rows=[{
        "cycle_id": "other-site", "cycle_kind": "ap", "site_id": "b" * 24,
        "observed_at": stamp(ANCHOR - timedelta(minutes=1)), "ap_mac": OTHER_AP,
        "name": None, "ip": None, "model": None, "firmware_version": None,
        "status_code": 1, "status_classification": "online", "last_seen_ms": None,
        "controller_uptime": None, "uptime_raw": None,
    }])
    result = read(service(current, observations))
    assert [item["ap_mac"] for item in result["items"]] == [AP]
