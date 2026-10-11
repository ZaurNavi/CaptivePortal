"""Stage A canaries exercise actual retained Observation / Current State reads."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from app.analytics.current_traffic import CurrentTrafficReadService, CurrentTrafficValidationError
from app.analytics.source_gateway import QueryDeadline, AnalyticsQueryDeadlineExceeded
from app.observations.config import MAX_AP_ROWS
from app.current_state.config import current_state_config_from_settings
from app.current_state.repository import CurrentStateRepository
from app.current_state.read_service import CurrentStateReadService
from app.admin_web.current_traffic_serialization import serialize_partial_current_summary, serialize_partial_current_ap_page
from tests.current_state.conftest import cycle as status_cycle, ap_row
from tests.analytics.test_current_traffic import _row

SITE = "0123456789abcdef01234567"
OTHER = "b" * 24
START = "2026-01-01T12:00:00.000Z"
OBSERVED = "2026-01-01T12:00:30.000Z"
FINISHED = "2026-01-01T12:00:40.000Z"
EVALUATED = "2026-01-01T12:01:00.000Z"
MACS = [f"02:AA:BB:CC:DD:0{n}" for n in range(1, 5)]
POLICY = dict(fresh_max_age_seconds=90, stale_max_age_seconds=180, max_ap_skew_seconds=60)
MISSING = (None, None, "source_unavailable", "source_unavailable")


@pytest.fixture
def retained(analytics_stack, tmp_path):
    config = current_state_config_from_settings({
        "current_state_enabled": "true", "current_state_db_path": str(tmp_path / "status.sqlite3"),
        "current_state_site_ids": SITE + "," + OTHER,
        "current_state_client_ssids_json": '["test"]',
    })
    repository = CurrentStateRepository(config)
    repository.initialize()
    return analytics_stack, CurrentStateReadService(repository)


def publish(retained, *, cycle_id="incident", missing=None, fourth="online", result="partial", site=SITE,
            status_at=OBSERVED, inventory=None, wired=None, lan=None, timestamps=None, started=START, finished=FINISHED):
    stack, status = retained
    rows = []
    for index, mac in enumerate(MACS):
        pair = [(10, 1), (5, 1), (3, 1), (2, 1)][index]
        rates = (*pair, "ok", "ok")
        if index == 3 and missing is not None:
            rates = (None, None, missing, missing)
        item = _row(cycle_id, mac, wired=rates if wired is None else wired[index],
                    lan=MISSING if lan is None else lan[index], observed=(timestamps or [OBSERVED] * 4)[index])
        item["site_id"] = site
        if result == "partial":
            item.update(partial=True, radios_ok=False)
        rows.append(item)
    stack.observations.create_cycle(kind="ap_dynamic", site_id=site, started_at=started, cycle_id=cycle_id)
    stack.observations.insert_ap_batch([(item, ()) for item in rows])
    stack.observations.finalize_cycle(cycle_id, finished_at=finished, complete=result == "success", result=result,
                                      source_rows_reported=4, items_seen=4, items_stored=4, error_count=2 if result == "partial" else 0)
    if status_at is not None:
        codes = {"online": 1, "offline": 0, "other": 2, "unknown": None}
        states = inventory or dict(zip(MACS, ["online", "online", "online", fourth]))
        sr = [ap_row(cycle_id="status-" + cycle_id, site_id=site, mac=mac, observed_at=status_at,
                     status_classification=classification, status_code=codes[classification]) for mac, classification in states.items()]
        parent = replace(status_cycle(kind="ap", cycle_id="status-" + cycle_id, site_id=site, started=status_at, items_stored=len(sr)),
                         unknown_status_count=sum(row["status_classification"] == "unknown" for row in sr))
        status.repository.publish_cycle(parent, ap_rows=sr)
    return rows


def summary(retained, *, site=SITE, **options):
    stack, status = retained
    return CurrentTrafficReadService(stack.gateway).get_current_site_traffic_partial_coverage(
        site, status_read_service=status, evaluated_at_utc=options.pop("evaluated_at_utc", EVALUATED), **(POLICY | options))


def page(retained, *, cycle_id="incident", **options):
    stack, status = retained
    return CurrentTrafficReadService(stack.gateway).list_current_ap_traffic_partial_coverage(
        SITE, cycle_id=cycle_id, status_read_service=status, evaluated_at_utc=EVALUATED, **(POLICY | options))


def test_A_T01_all_four_pairs_prove_installed_even_when_global_partial(retained):
    publish(retained)
    value = summary(retained)
    assert value.measurement_state == "complete_installed"
    assert dict(value.traffic) == dict(download_mbps=20, upload_mbps=4, total_mbps=24, unit="Mbps")
    assert value.snapshot["source_result"] == "partial" and value.snapshot["source_complete"] is False
    assert serialize_partial_current_summary(value, SITE)["population_scope"] == "installed"
    with pytest.raises(TypeError):
        value.coverage["installed_ap_count"] = 0


def test_A_T02_AP4_incident_exact_null_not_zero_and_pinned_page(retained):
    publish(retained, missing="source_unavailable", fourth="offline")
    value = summary(retained)
    assert value.measurement_state == "complete_online_population"
    assert value.population_scope == "confirmed_online"
    assert (value.traffic["download_mbps"], value.traffic["upload_mbps"], value.traffic["total_mbps"]) == (18, 3, 21)
    assert value.coverage["online_ap_count"] == 3 and value.coverage["installed_ap_count"] == 4
    assert value.coverage["offline_excluded_ap_count"] == 1
    first = page(retained, limit=2)
    second = page(retained, limit=2, cursor=first.page.next_cursor)
    assert first.summary == second.summary == value
    last = second.items[-1]
    assert last["coverage_role"] == "offline_excluded" and last["status_classification"] == "offline"
    assert last["download_mbps"] is None and last["upload_mbps"] is None and last["total_mbps"] is None
    result, metadata = serialize_partial_current_ap_page(second, SITE, cycle_id="incident", limit=2)
    assert metadata["next_cursor"] is None and result["items"][-1]["total_mbps"] is None
    with pytest.raises(CurrentTrafficValidationError):
        page(retained, cycle_id="other", cursor=first.page.next_cursor)


@pytest.mark.parametrize("fourth,status_at,reason", [
    ("online", OBSERVED, "online_measurement_missing"),
    ("other", OBSERVED, "other_status_measurement_missing"),
    ("unknown", OBSERVED, "unknown_status_measurement_missing"),
    ("offline", "2026-01-01T11:58:00.000Z", "status_evidence_stale"),
    ("offline", None, "status_evidence_unavailable"),
    ("offline", "2026-01-01T12:00:41.000Z", "status_evidence_unavailable"),
])
def test_A_T03_T04_no_unproven_offline_exclusion(retained, fourth, status_at, reason):
    publish(retained, missing="source_unavailable", fourth=fourth, status_at=status_at)
    value = summary(retained)
    assert value.measurement_state == "partial_measured" and value.traffic["total_mbps"] == 21
    assert reason in value.coverage["coverage_reasons"]
    assert value.coverage["offline_excluded_ap_count"] == 0


@pytest.mark.parametrize("rates,expected", [(MISSING, None), ((0, 0, "ok", "ok"), 0)])
def test_A_T05_actual_zero_vs_no_measurements(retained, rates, expected):
    publish(retained, wired=[rates] * 4)
    value = summary(retained)
    assert value.traffic["total_mbps"] == expected
    assert value.measurement_state == ("unavailable" if expected is None else "complete_installed")


def test_A_T06_T14_original_incident_replay_and_automatic_recovery(retained):
    replay = []
    for index, (missing, fourth, expected) in enumerate([
        (None, "online", "complete_installed"),
        ("source_unavailable", "offline", "complete_online_population"),
        ("no_baseline", "online", "partial_measured"),
        ("counter_reset", "online", "partial_measured"),
        (None, "online", "complete_installed"),
    ]):
        at = datetime(2026, 1, 1, 12, tzinfo=timezone.utc) + timedelta(minutes=index)
        stamp = lambda seconds: (at + timedelta(seconds=seconds)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        publish(retained, cycle_id=f"replay-{index}", missing=missing, fourth=fourth, status_at=stamp(30),
                started=stamp(0), finished=stamp(40), timestamps=[stamp(30)] * 4)
        value = summary(retained, evaluated_at_utc=stamp(60))
        assert value.snapshot["cycle_id"] == f"replay-{index}"
        assert value.measurement_state == expected
        replay.append(value.traffic["total_mbps"])
    assert replay == [24, 21, 21, 21, 24]


def test_A_T07_population_mismatch_and_site_isolation(retained):
    inventory = dict(zip(MACS[:3] + ["02:AA:BB:CC:DD:99"], ["online"] * 3 + ["offline"]))
    publish(retained, missing="source_unavailable", inventory=inventory)
    value = summary(retained)
    assert value.measurement_state == "partial_measured" and value.coverage["population_match_state"] == "mismatch"
    assert value.coverage["inventory_only_ap_count"] == value.coverage["observation_only_ap_count"] == 1
    assert value.status_evidence["state"] == "population_mismatch"
    assert summary(retained, site=OTHER).measurement_state == "unavailable"


@pytest.mark.parametrize("evaluated,expected", [
    (EVALUATED, "fresh"), ("2026-01-01T12:02:01.000Z", "stale"),
    ("2026-01-01T12:03:31.000Z", "unavailable"), ("2026-01-01T12:00:29.000Z", "unavailable"),
])
def test_A_T08_freshness_clock_boundaries(retained, evaluated, expected):
    publish(retained)
    value = summary(retained, evaluated_at_utc=evaluated)
    assert value.snapshot["freshness_status"] == expected
    if expected == "unavailable":
        assert value.traffic["total_mbps"] is None


def test_A_T08_temporal_skew_suppresses_sum_not_diagnostic_AP_pairs(retained):
    publish(retained, timestamps=[START, OBSERVED, OBSERVED, OBSERVED])
    value = summary(retained, max_ap_skew_seconds=29)
    assert value.measurement_state == "unavailable" and value.traffic["total_mbps"] is None
    assert "temporal_skew" in value.coverage["coverage_reasons"]
    assert page(retained, max_ap_skew_seconds=29).items[0]["rate_status"] == "valid"


@pytest.mark.parametrize("wired,lan,missing,fourth,source,reason", [
    (4, 4, None, "online", "wired", "primary_full_observation_coverage"),
    (3, 4, None, "online", "lan", "fallback_full_observation_coverage"),
    (3, 3, None, "offline", "wired", "primary_full_online_coverage"),
    (2, 3, None, "offline", "lan", "fallback_full_online_coverage"),
    (1, 2, None, "online", "lan", "fallback_higher_measured_coverage"),
    (2, 2, None, "online", "wired", "primary_preferred_tie_or_higher"),
])
def test_A_T09_exact_source_priority_no_family_mixing(retained, wired, lan, missing, fourth, source, reason):
    publish(retained, fourth=fourth,
            wired=[(10, 1, "ok", "ok") if n < wired else MISSING for n in range(4)],
            lan=[(20, 2, "ok", "ok") if n < lan else MISSING for n in range(4)])
    value = summary(retained)
    assert value.source_selection["selected_source"] == source
    assert value.source_selection["selection_reason"] == reason
    assert value.source_selection["source_mixing_allowed"] is False
    assert value.traffic["total_mbps"] == (wired * 11 if source == "wired" else lan * 22)


@pytest.mark.parametrize("field,value", [("items_skipped", 1), ("source_rows_reported", 3),
                                         ("items_seen", 3), ("data_quality_warning_count", 1)])
def test_A_T10_newest_corrupt_cycle_no_old_numeric_fallback(retained, field, value):
    publish(retained, cycle_id="old", result="success")
    publish(retained, cycle_id="new", started="2026-01-01T12:00:01.000Z")
    with sqlite3.connect(retained[0].observations.db_path) as connection:
        connection.execute(f"UPDATE observation_cycles SET {field}=? WHERE cycle_id='new'", (value,))
    current = summary(retained)
    assert current.measurement_state == "unavailable" and current.traffic["total_mbps"] is None
    assert "source_integrity_unavailable" in current.coverage["coverage_reasons"]


@pytest.mark.parametrize("missing", ["counter_reset", "no_baseline", "gap_too_large", "invalid_elapsed", None])
def test_A_T11_offline_conflict_not_silently_excluded(retained, missing):
    publish(retained, fourth="offline", missing=missing)
    value = summary(retained)
    assert "status_measurement_conflict" in value.coverage["coverage_reasons"]
    assert value.measurement_state != "complete_online_population"
    assert value.coverage["offline_excluded_ap_count"] == 0


def test_partial_all_observed_pairs_without_installed_proof_not_complete(retained):
    publish(retained, status_at=None)
    assert summary(retained).measurement_state == "partial_measured"


def test_strict_success_full_population_retains_installed_proof(retained):
    publish(retained, result="success", status_at=None)
    assert summary(retained).measurement_state == "complete_installed"


def test_directional_sums_do_not_invent_missing_total(retained):
    publish(retained, wired=[(1, None, "ok", "source_unavailable")] * 4)
    value = summary(retained)
    assert value.measurement_state == "partial_measured"
    assert (value.traffic["download_mbps"], value.traffic["upload_mbps"], value.traffic["total_mbps"]) == (4, None, None)


def test_failed_attempt_keeps_prior_numbers_with_truthful_metadata(retained):
    publish(retained)
    repository = retained[0].observations
    repository.create_cycle(kind="ap_dynamic", site_id=SITE, started_at="2026-01-01T12:00:41.000Z", cycle_id="failed")
    repository.finalize_cycle("failed", finished_at="2026-01-01T12:00:42.000Z", complete=False, result="failed")
    value = summary(retained)
    assert value.snapshot["cycle_id"] == "incident" and value.snapshot["using_previous_snapshot"] is True
    assert value.snapshot["latest_attempt_result"] == "failed" and value.traffic["total_mbps"] == 24


def test_deadline_is_not_swallowed_as_incomplete_measurement(retained):
    with pytest.raises(AnalyticsQueryDeadlineExceeded):
        summary(retained, deadline=QueryDeadline.after(0))


def test_same_mac_other_site_cannot_supply_missing_status_or_rate(retained):
    publish(retained, cycle_id="local", missing="source_unavailable", status_at=None)
    publish(retained, cycle_id="foreign", site=OTHER, fourth="offline", missing="source_unavailable")
    local = summary(retained)
    foreign = summary(retained, site=OTHER)
    assert local.measurement_state == "partial_measured" and local.status_evidence["state"] == "unavailable"
    assert foreign.measurement_state == "complete_online_population"


@pytest.mark.parametrize("field,value", [
    ("wired_download_mbps", -1), ("wired_download_mbps", None),
    ("wired_download_rate_reason", "counter_reset"),
    ("wired_observed_at", "2026-01-01T11:59:59.000Z"),
    ("wired_observed_at", "2026-01-01T12:00:41.000Z"),
    ("ap_mac", "02:aa:bb:cc:dd:01"), ("site_id", OTHER),
])
def test_A_T10_retained_shape_corruption_fail_closed(retained, field, value):
    publish(retained)
    # Read payload comes from the real SQLite gateway; corruption is injected
    # only at the read boundary to cover shapes that storage constraints reject.
    data = retained[0].gateway.read_current_partial_traffic_evidence(site_id=SITE, cycle_id=None, deadline=QueryDeadline.after(2))
    rows = [dict(row) for row in data["rows"]]
    rows[0][field] = value
    class Gateway:
        def read_current_partial_traffic_evidence(self, **kwargs):
            return dict(data) | {"rows": rows}
    result = CurrentTrafficReadService(Gateway()).get_current_site_traffic_partial_coverage(
        SITE, status_read_service=retained[1], evaluated_at_utc=EVALUATED, **POLICY)
    assert result.measurement_state == "unavailable" and result.traffic["total_mbps"] is None
    assert "source_integrity_unavailable" in result.coverage["coverage_reasons"]


def test_strict_success_inventory_conflict_is_still_not_complete(retained):
    publish(retained, result="success", inventory=dict(zip(MACS[:3], ["online"] * 3)))
    result = summary(retained)
    assert result.measurement_state == "partial_measured" and "population_mismatch" in result.coverage["coverage_reasons"]


def test_partial_current_reads_do_not_write_source_databases(retained):
    import hashlib
    publish(retained, missing="source_unavailable", fourth="offline")
    paths = [retained[0].observations.db_path, retained[1].repository.db_path]
    for path in paths:
        with sqlite3.connect(path) as connection:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    before = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
    summary(retained)
    page(retained)
    assert [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths] == before


@pytest.mark.parametrize("error", [
    sqlite3.OperationalError("database is locked"),
    sqlite3.DatabaseError("database disk image is malformed"),
    PermissionError("synthetic status path is inaccessible"),
    FileNotFoundError("synthetic status path is missing"),
    OSError("synthetic status I/O failure"),
])
def test_R1_P1_status_storage_failure_preserves_measured_partial(retained, monkeypatch, error):
    publish(retained, missing="source_unavailable", fourth="offline")
    def fail_open(*, write):
        assert write is False
        raise error
    monkeypatch.setattr(retained[1].repository, "_connect", fail_open)
    value = summary(retained)
    assert value.measurement_state == "partial_measured"
    assert value.population_scope == "measured_only"
    assert dict(value.traffic) == dict(download_mbps=18, upload_mbps=3, total_mbps=21, unit="Mbps")
    assert value.status_evidence["state"] == "unavailable"
    assert "status_evidence_unavailable" in value.coverage["coverage_reasons"]
    assert value.coverage["offline_excluded_ap_count"] == 0
    assert serialize_partial_current_summary(value, SITE)["traffic"]["total_mbps"] == 21
    assert page(retained).items[-1]["coverage_role"] != "offline_excluded"


@pytest.mark.parametrize("interrupted", [False, True])
def test_R1_P1_status_timeout_is_not_partial_fallback(retained, interrupted):
    publish(retained, missing="source_unavailable", fourth="offline")
    clock = [0.0]
    deadline = QueryDeadline.after(1, monotonic=lambda: clock[0])
    class StatusReader:
        def read_ap_status_evidence_at(self, site, finished, *, deadline):
            clock[0] = 1.0
            if interrupted:
                raise sqlite3.OperationalError("interrupted")
            deadline.require_remaining()
    with pytest.raises(AnalyticsQueryDeadlineExceeded):
        CurrentTrafficReadService(retained[0].gateway).get_current_site_traffic_partial_coverage(
            SITE, status_read_service=StatusReader(), evaluated_at_utc=EVALUATED,
            deadline=deadline, **POLICY)


@pytest.mark.parametrize("error", [RuntimeError("synthetic programming defect"),
                                  sqlite3.ProgrammingError("synthetic programming defect"),
                                  sqlite3.InterfaceError("synthetic programming defect")])
def test_R1_P1_status_programming_error_is_not_swallowed(retained, error):
    publish(retained, missing="source_unavailable", fourth="offline")
    class StatusReader:
        def read_ap_status_evidence_at(self, *args, **kwargs):
            raise error
    with pytest.raises(type(error), match="synthetic programming defect"):
        CurrentTrafficReadService(retained[0].gateway).get_current_site_traffic_partial_coverage(
            SITE, status_read_service=StatusReader(), evaluated_at_utc=EVALUATED, **POLICY)


@pytest.mark.parametrize("count", [MAX_AP_ROWS + 1, 1_000_000_000])
def test_R1_P2_oversized_count_never_materializes_rows(retained, monkeypatch, count):
    publish(retained, result="success", cycle_id="old")
    publish(retained, cycle_id="new", started="2026-01-01T12:00:01.000Z")
    gateway = retained[0].gateway
    original_one = gateway._one
    def counted(connection, sql, parameters, deadline):
        value = original_one(connection, sql, parameters, deadline)
        if "SELECT COUNT(*) AS n FROM ap_observations" in sql:
            return {"n": count}
        if "SELECT * FROM observation_cycles" in sql:
            return dict(value) | {"items_stored": count, "items_seen": count, "source_rows_reported": count}
        return value
    def forbidden_bulk_fetch(*args, **kwargs):
        pytest.fail("oversized current cycle must not request bulk AP rows")
    monkeypatch.setattr(gateway, "_one", counted)
    monkeypatch.setattr(gateway, "_all", forbidden_bulk_fetch)
    value = summary(retained)
    assert value.measurement_state == "unavailable"
    assert value.traffic["total_mbps"] is None
    assert "source_integrity_unavailable" in value.coverage["coverage_reasons"]


@pytest.mark.parametrize("count", [MAX_AP_ROWS, MAX_AP_ROWS + 1])
def test_R1_P2_retained_rows_at_hard_limit_and_above(retained, monkeypatch, count):
    repository = retained[0].observations
    repository.create_cycle(kind="ap_dynamic", site_id=SITE, started_at=START, cycle_id="large")
    def mac(index):
        suffix = f"{index:08X}"
        return "02:AA:" + ":".join(suffix[i:i + 2] for i in range(0, 8, 2))
    repository.insert_ap_batch([
        (_row("large", mac(index), wired=(1, 2, "ok", "ok"), lan=MISSING, observed=OBSERVED) | {"site_id": SITE}, ())
        for index in range(count)
    ])
    repository.finalize_cycle("large", finished_at=FINISHED, complete=False, result="partial",
                              source_rows_reported=count, items_seen=count, items_stored=count, error_count=2)
    gateway = retained[0].gateway
    original_all = gateway._all
    calls = []
    def bounded_all(connection, sql, parameters, deadline):
        calls.append(tuple(parameters))
        assert parameters[-1] <= MAX_AP_ROWS + 1
        return original_all(connection, sql, parameters, deadline)
    monkeypatch.setattr(gateway, "_all", bounded_all)
    value = summary(retained)
    if count > MAX_AP_ROWS:
        assert calls == []
        assert value.measurement_state == "unavailable" and value.traffic["total_mbps"] is None
        assert "source_integrity_unavailable" in value.coverage["coverage_reasons"]
    else:
        assert calls == [("large", MAX_AP_ROWS + 1)]
        assert value.measurement_state == "partial_measured"
        assert value.coverage["measured_pair_ap_count"] == MAX_AP_ROWS
        assert value.traffic["total_mbps"] == 3 * MAX_AP_ROWS
        first = page(retained, cycle_id="large", limit=250)
        assert len(first.items) == 250 and first.page.next_cursor is not None
        assert first.summary == value
