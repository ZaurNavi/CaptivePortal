"""Stage B R3 canaries use real retained Observation and strict History paths."""
import sqlite3
from dataclasses import replace

import pytest

from app.analytics.historical_traffic import HistoricalTrafficReadService
from app.analytics.models import HistoricalTrafficPartialCoverageOverlayV1
from app.analytics.source_gateway import QueryDeadline
from app.admin_web.historical_traffic_serialization import (
    serialize_historical_traffic, serialize_partial_historical_traffic, HistoricalTrafficSerializationError,
)
from app.admin_web.traffic_network_ranges import resolve_traffic_network_range
from app.analytics.validation import parse_utc
from tests.analytics.test_historical_traffic import _cycle, _row, EVALUATED

SITE = "partial-history-site"
START = "2025-12-31T12:00:00.000Z"
AT = "2026-01-01T11:57:00.000Z"
MACS = [f"02:AA:BB:CC:DD:{n:02X}" for n in range(1, 7)]


def publish(stack, cycle="partial", *, at=AT, pairs=None, lan=None, site=SITE, result="partial"):
    pairs = pairs if pairs is not None else [(10, 1), (5, 1), (3, 1), (None, None)]
    rows = [_row(cycle, MACS[i], at, wired=pair, lan=(None, None) if lan is None else lan[i], site=site)
            for i, pair in enumerate(pairs)]
    for row in rows:
        if result == "partial":
            row.update(partial=True, radios_ok=False)
        for key in ("wired_download_rate_reason", "wired_upload_rate_reason", "lan_rx_rate_reason", "lan_tx_rate_reason"):
            if row[key] != "ok":
                row[key] = "source_unavailable"
    _cycle(stack, cycle, at, rows, site=site, result=result, complete=result == "success")


def read(stack, *, gateway=None, **extra):
    return HistoricalTrafficReadService(gateway or stack.gateway).get_site_history_partial_coverage(
        SITE, from_utc=START, to_utc=EVALUATED, evaluated_at_utc=EVALUATED, **extra)


def wire(value, **options):
    return serialize_partial_historical_traffic(value, SITE,
        resolved_range=resolve_traffic_network_range("24h", parse_utc(EVALUATED, "at")), **options)


def test_R3_T19_empty_retained_query_is_not_absence(analytics_stack):
    value = wire(read(analytics_stack))
    o = value["partial_coverage"]
    assert o["status"] == "source_coverage_insufficient" and o["reason"] == "raw_observation_range_unproven"
    assert o["has_partial_measurements"] is o["source_coverage_insufficient"] is None
    assert o["partial_cycle_count_examined"] == 0 and o["buckets"] == []
    assert o["comparison_allowed"] is o["ap_share_allowed"] is False


def test_R3_T20_T22_original_AP4_positive_even_when_prefix_short(analytics_stack):
    publish(analytics_stack)
    value = read(analytics_stack)
    o = wire(value)["partial_coverage"]
    assert o["status"] == "partial_evidence" and o["has_partial_measurements"] is True
    assert o["source_coverage_insufficient"] is True
    b = o["buckets"][0]
    assert (b["download_mbps"], b["upload_mbps"], b["total_mbps"]) == (18, 3, 21)
    assert b["observed_ap_opportunities"] == 4 and b["measured_pair_ap_opportunities"] == 3
    assert b["coverage_ratio"] == .75 and b["status"] == "partial_measured"
    assert b["reasons"] == ["source_cycle_partial", "source_unavailable"]
    with pytest.raises(TypeError):
        value.partial_coverage.evidence["buckets"][0]["total_mbps"] = 0


def test_R3_T21_empty_partial_query_with_positive_prefix_shortage(analytics_stack):
    publish(analytics_stack, result="success", pairs=[(1, 2)])
    o = wire(read(analytics_stack))["partial_coverage"]
    assert o["reason"] == "raw_observation_range_incomplete"
    assert o["source_coverage_insufficient"] is True and o["has_partial_measurements"] is None
    assert o["partial_cycle_count_admitted"] == 0


def test_positive_with_unknown_continuity_and_site_isolation(analytics_stack):
    _cycle(analytics_stack, "prefix", START, result="failed", complete=False, site=SITE)
    publish(analytics_stack)
    publish(analytics_stack, "other", site="site-b", pairs=[(999, 999)])
    o = wire(read(analytics_stack))["partial_coverage"]
    assert o["has_partial_measurements"] is True and o["source_coverage_insufficient"] is None
    assert o["partial_cycle_count_examined"] == 1 and o["buckets"][0]["total_mbps"] == 21


@pytest.mark.parametrize("pairs,state,values,counts", [
    ([(None, None)], "partial_unmeasured", (None, None, None), (0, 0, 0)),
    ([(4, None)], "partial_directional", (4, None, None), (1, 0, 0)),
    ([(None, 2)], "partial_directional", (None, 2, None), (0, 1, 0)),
    ([(4, None), (None, 2)], "partial_directional", (4, 2, None), (1, 1, 0)),
    ([(0, 0)], "partial_measured", (0, 0, 0), (1, 1, 1)),
])
def test_R3_T23_T24_directional_populations_and_real_zero(analytics_stack, pairs, state, values, counts):
    publish(analytics_stack, pairs=pairs)
    b = wire(read(analytics_stack))["partial_coverage"]["buckets"][0]
    assert b["status"] == state
    assert tuple(b[k] for k in ("download_mbps", "upload_mbps", "total_mbps")) == values
    assert tuple(b[k] for k in ("download_sample_count", "upload_sample_count", "measured_sample_count")) == counts


def test_R1_independent_cycle_denominators_and_opportunity_ratio_7_over_9(analytics_stack):
    publish(analytics_stack, "a", pairs=[(1, 1)] * 3 + [(None, None)])
    publish(analytics_stack, "b", at="2026-01-01T11:58:00.000Z", pairs=[(2, 2)] * 4 + [(None, None)])
    b = wire(read(analytics_stack))["partial_coverage"]["buckets"][0]
    assert b["coverage_ratio"] == pytest.approx(7 / 9)
    assert (b["min_observed_ap_count"], b["max_observed_ap_count"]) == (4, 5)
    assert (b["min_measured_ap_count"], b["max_measured_ap_count"]) == (3, 4)
    assert b["total_mbps"] == 11


def test_Total_is_not_sum_of_independently_denominated_means(analytics_stack):
    publish(analytics_stack, "a", pairs=[(4, 2)])
    publish(analytics_stack, "b", at="2026-01-01T11:58:00.000Z", pairs=[(10, None)])
    b = wire(read(analytics_stack))["partial_coverage"]["buckets"][0]
    assert (b["download_mbps"], b["upload_mbps"], b["total_mbps"]) == (7, 2, 6)
    assert (b["download_sample_count"], b["upload_sample_count"], b["measured_sample_count"]) == (2, 1, 1)


@pytest.mark.parametrize("wired,lan,source,reason", [
    ([(1, 2)], [(3, 4)], "wired", "primary_full_partial_bucket_coverage"),
    ([(None, None)], [(3, 4)], "lan", "fallback_full_partial_bucket_coverage"),
    ([(1, 2), (None, None)], [(3, None), (None, 4)], "wired", "primary_higher_partial_pair_coverage"),
    ([(1, None), (None, 2)], [(3, 4), (None, None)], "lan", "fallback_higher_partial_pair_coverage"),
    ([(1, None), (None, None)], [(3, None), (None, 4)], "lan", "fallback_higher_partial_direction_coverage"),
    ([(1, None)], [(3, None)], "wired", "primary_preferred_partial_tie_or_higher"),
])
def test_R3_T27_one_bucket_family_never_mix(analytics_stack, wired, lan, source, reason):
    publish(analytics_stack, pairs=wired, lan=lan)
    b = wire(read(analytics_stack))["partial_coverage"]["buckets"][0]
    assert (b["selected_source"], b["selection_reason"]) == (source, reason)


@pytest.mark.parametrize("column,value", [("items_seen", 5), ("source_rows_reported", None),
    ("items_skipped", 1), ("data_quality_warning_count", 1)])
def test_corrupt_cycles_rejected_without_rejecting_positive_neighbors(analytics_stack, column, value):
    publish(analytics_stack, "good")
    publish(analytics_stack, "bad", at="2026-01-01T11:58:00.000Z")
    with sqlite3.connect(analytics_stack.observations.db_path) as c:
        c.execute(f"UPDATE observation_cycles SET {column}=? WHERE cycle_id='bad'", (value,))
    o = wire(read(analytics_stack))["partial_coverage"]
    assert (o["partial_cycle_count_examined"], o["partial_cycle_count_admitted"], o["partial_cycle_count_integrity_rejected"]) == (2, 1, 1)
    assert o["buckets"][0]["total_mbps"] == 21


@pytest.mark.parametrize("bound", ["MAX_PARTIAL_CYCLES_PER_REQUEST", "MAX_PARTIAL_AP_ROWS_PER_REQUEST"])
def test_R3_T25_any_cap_discards_even_already_accumulated_positive(analytics_stack, monkeypatch, bound):
    publish(analytics_stack, "a")
    publish(analytics_stack, "b", at="2026-01-01T11:58:00.000Z")
    monkeypatch.setattr("app.analytics.source_gateway." + bound, 1 if "CYCLES" in bound else 4)
    o = wire(read(analytics_stack))["partial_coverage"]
    assert o["status"] == "capacity_limited" and o["buckets"] == []
    assert all(o[k] is None for k in ("partial_cycle_count_examined", "partial_cycle_count_admitted", "partial_cycle_count_integrity_rejected", "partial_ap_rows_examined", "has_partial_measurements"))


def test_R3_T26_overlay_failure_preserves_strict_result(analytics_stack, monkeypatch):
    publish(analytics_stack, result="success", pairs=[(1, 2)])
    def broken(**kwargs):
        raise sqlite3.OperationalError("private source unavailable")
    monkeypatch.setattr(analytics_stack.gateway, "read_partial_ap_traffic_evidence", broken)
    v = read(analytics_stack)
    o = wire(v)["partial_coverage"]
    assert o["status"] == "unavailable" and o["buckets"] == []
    assert v.strict.buckets[-1].total_mbps == 3
    assert "private" not in str(o)


def test_R3_T28_strict_statistics_peak_and_overlap_unchanged(analytics_stack):
    publish(analytics_stack, "strict-a", at="2026-01-01T11:56:00.000Z", result="success", pairs=[(20, 4)])
    publish(analytics_stack, "strict-b", at="2026-01-01T11:59:00.000Z", result="success", pairs=[(20, 4)])
    publish(analytics_stack)
    v = read(analytics_stack, include_period_statistics=True, include_peak_load=True, include_ap_share=True)
    out = wire(v, include_period_statistics=True, include_peak_load=True, include_ap_share=True)
    old = serialize_historical_traffic(v.strict, SITE,
        resolved_range=resolve_traffic_network_range("24h", parse_utc(EVALUATED, "at")),
        include_period_statistics=True, include_peak_load=True, include_ap_share=True)
    assert out["buckets"] == old["buckets"]
    assert out["period_statistics"] == old["period_statistics"]
    assert out["peak_load"] == old["peak_load"]
    assert out["period_statistics"]["average"]["total_mbps"] == 24
    assert out["partial_coverage"]["buckets"][0]["total_mbps"] == 21
    assert out["comparison_state"] == "unavailable_partial_coverage"
    assert out["ap_traffic_share"]["status"] == "insufficient_data"
    assert all(item[k] is None for item in out["ap_traffic_share"]["items"]
               for k in ("download_share_fraction", "upload_share_fraction", "total_share_fraction"))


@pytest.mark.parametrize("key,value", [("has_partial_measurements", False), ("source_coverage_insufficient", False),
                                       ("comparison_allowed", True), ("reason", "no_partial_measurements")])
def test_serializer_rejects_forbidden_absence_and_permission(analytics_stack, key, value):
    v = read(analytics_stack)
    altered = replace(v, partial_coverage=HistoricalTrafficPartialCoverageOverlayV1({**v.partial_coverage.evidence, key: value}))
    with pytest.raises(HistoricalTrafficSerializationError):
        wire(altered)


@pytest.mark.parametrize("winner", ["wired", "lan"])
def test_bucket_priority_more_full_cycles_over_more_pairs(analytics_stack, winner):
    primary = [(1, 1)] * 4
    sparse = [(10, 10)] * 3 + [(None, None)]
    absent = [(None, None)] * 4
    for name, w, l in (("a", primary, sparse), ("b", absent, sparse)):
        publish(analytics_stack, name, pairs=w if winner == "wired" else l,
                lan=l if winner == "wired" else w)
    b = wire(read(analytics_stack))["partial_coverage"]["buckets"][0]
    assert b["selected_source"] == winner
    assert b["selection_reason"] == ("primary_more_full_partial_cycles" if winner == "wired" else "fallback_more_full_partial_cycles")
    assert b["total_mbps"] == 8 and b["measured_sample_count"] == 1


def test_half_open_range_and_non_numeric_lifecycles(analytics_stack):
    for name, at, result in (("at-start", START, "partial"), ("at-end", EVALUATED, "partial"),
                             ("failed", AT, "failed"), ("shutdown", AT, "shutdown")):
        publish(analytics_stack, name, at=at, result=result)
    o = wire(read(analytics_stack))["partial_coverage"]
    assert o["partial_cycle_count_examined"] == 1
    assert o["buckets"][0]["bucket_start_utc"] == START


@pytest.mark.parametrize("column,value", [("wired_download_rate_reason", "counter_reset"),
                                         ("wired_observed_at", "2026-01-01T11:58:00.000Z")])
def test_bad_rate_shape_or_timestamp_rejects_entire_partial_cycle(analytics_stack, column, value):
    publish(analytics_stack)
    with sqlite3.connect(analytics_stack.observations.db_path) as c:
        c.execute(f"UPDATE ap_observations SET {column}=? WHERE cycle_id='partial' AND ap_mac=?", (value, MACS[0]))
    o = wire(read(analytics_stack))["partial_coverage"]
    assert o["partial_cycle_count_integrity_rejected"] == 1
    assert o["has_partial_measurements"] is None and o["buckets"] == []


def test_RO_snapshot_and_bounded_fetch_all_after_local_deadline(analytics_stack, monkeypatch):
    from contextlib import contextmanager
    publish(analytics_stack)
    original = analytics_stack.gateway._partial_evidence_connection
    clock = [0.0]
    @contextmanager
    def checked(deadline):
        assert deadline.expires_at == 5.0
        with original(deadline) as c:
            assert c.execute("PRAGMA query_only").fetchone()[0] == 1
            with pytest.raises(sqlite3.OperationalError):
                c.execute("DELETE FROM observation_cycles")
            c.rollback()
            yield c
        clock[0] = 6.0
    monkeypatch.setattr(analytics_stack.gateway, "_partial_evidence_connection", checked)
    # Crossing the deadline after return from the source must discard evidence too.
    original_read = analytics_stack.gateway.read_partial_ap_traffic_evidence
    def delayed(**kwargs):
        result = original_read(**kwargs)
        kwargs["deadline"].require_remaining()
        return result
    monkeypatch.setattr(analytics_stack.gateway, "read_partial_ap_traffic_evidence", delayed)
    o = wire(read(analytics_stack, deadline=QueryDeadline(10.0, lambda: clock[0])))["partial_coverage"]
    assert o["status"] == "capacity_limited" and o["buckets"] == []
    assert o["partial_cycle_count_admitted"] is None


def test_projection_gateway_reads_raw_partial_RO_without_projection_mutation(tmp_path):
    import hashlib
    from contextlib import contextmanager
    from app.traffic_projection.read_service import TrafficProjectionReadService
    from tests.traffic_projection.test_projected_read import _fixture
    observation, repository = _fixture(tmp_path)
    # Add raw partial evidence only; no projector/upsert is called for it.
    with sqlite3.connect(observation) as c:
        c.execute("INSERT INTO observation_cycles SELECT 'raw-partial',kind,site_id,state,started_at,finished_at,abandoned_at,0,'partial',source_rows_reported,items_seen,items_stored,items_skipped,2,data_quality_warning_count,created_at,updated_at FROM observation_cycles WHERE cycle_id='cycle-0'")
        columns = [row[1] for row in c.execute("PRAGMA table_info(ap_observations)") if row[1] != "row_id"]
        expressions = ["'raw-partial'" if col == "cycle_id" else col for col in columns]
        c.execute(f"INSERT INTO ap_observations ({','.join(columns)}) SELECT {','.join(expressions)} FROM ap_observations WHERE cycle_id='cycle-0'")
    before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (observation, repository.db_path)}
    gateway = TrafficProjectionReadService(repository, current_observation_db_path=str(observation))
    original = gateway._partial_evidence_connection
    @contextmanager
    def verified(deadline):
        with original(deadline) as c:
            assert c.execute("PRAGMA query_only").fetchone()[0] == 1
            assert c.execute("PRAGMA database_list").fetchall()[0][2] == str(observation)
            with pytest.raises(sqlite3.OperationalError):
                c.execute("DELETE FROM observation_cycles")
            c.rollback()
            yield c
    gateway._partial_evidence_connection = verified
    args = dict(from_utc="2026-09-02T10:00:00.000Z", to_utc="2026-09-03T10:00:00.000Z",
                evaluated_at_utc="2026-09-03T10:00:00.000Z", current_cycle_id="cycle-1")
    v = HistoricalTrafficReadService(gateway).get_site_history_partial_coverage("site-a", **args)
    assert v.partial_coverage.evidence["status"] == "partial_evidence"
    assert v.partial_coverage.evidence["buckets"][0]["total_mbps"] == 3
    assert before == {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (observation, repository.db_path)}
    with sqlite3.connect(repository.db_path) as c:
        assert c.execute("SELECT count(*) FROM traffic_projection_cycles WHERE cycle_id='raw-partial'").fetchone()[0] == 0


def test_7d_axis_and_historical_four_three_four_recovery(analytics_stack):
    for cycle, at, pairs in (("before", "2026-01-01T11:42:00.000Z", [(10, 1), (5, 1), (3, 1), (2, 1)]),
                             ("incident", "2026-01-01T11:47:00.000Z", [(10, 1), (5, 1), (3, 1), (None, None)]),
                             ("after", "2026-01-01T11:52:00.000Z", [(10, 1), (5, 1), (3, 1), (2, 1)])):
        publish(analytics_stack, cycle, at=at, pairs=pairs)
    v = read(analytics_stack)
    assert [b["total_mbps"] for b in v.partial_coverage.evidence["buckets"]] == [24, 21, 24]
    assert [b["coverage_ratio"] for b in v.partial_coverage.evidence["buckets"]] == [1, .75, 1]
    v7 = HistoricalTrafficReadService(analytics_stack.gateway).get_site_history_partial_coverage(
        SITE, from_utc="2025-12-25T12:00:00.000Z", to_utc=EVALUATED, evaluated_at_utc=EVALUATED)
    assert len(v7.strict.buckets) == 672 and v7.strict.range.bucket_seconds == 900
    assert v7.partial_coverage.evidence["partial_cycle_count_admitted"] == 3


@pytest.mark.parametrize("bound", ["cycles", "rows"])
def test_exact_physical_raw_read_caps_and_streaming_batches(analytics_stack, monkeypatch, bound):
    from contextlib import contextmanager
    from app.analytics.source_gateway import (
        MAX_PARTIAL_CYCLES_PER_REQUEST, MAX_PARTIAL_AP_ROWS_PER_REQUEST,
        PARTIAL_AP_ROW_BATCH_SIZE, PartialTrafficCapacityLimited,
    )
    assert (MAX_PARTIAL_CYCLES_PER_REQUEST, MAX_PARTIAL_AP_ROWS_PER_REQUEST, PARTIAL_AP_ROW_BATCH_SIZE) == (10080, 150000, 2000)
    publish(analytics_stack, pairs=[(1, 1)])
    with sqlite3.connect(analytics_stack.observations.db_path) as c:
        if bound == "cycles":
            columns = [r[1] for r in c.execute("PRAGMA table_info(observation_cycles)")]
            expressions = ["?" if name == "cycle_id" else name for name in columns]
            c.executemany(f"INSERT INTO observation_cycles ({','.join(columns)}) SELECT {','.join(expressions)} FROM observation_cycles WHERE cycle_id='partial'",
                          [(f"extra-{n:05d}",) for n in range(10080)])
        else:
            columns = [r[1] for r in c.execute("PRAGMA table_info(ap_observations)") if r[1] != "row_id"]
            expressions = ["?" if name == "ap_mac" else name for name in columns]
            c.executemany(f"INSERT INTO ap_observations ({','.join(columns)}) SELECT {','.join(expressions)} FROM ap_observations WHERE cycle_id='partial' AND ap_mac=?",
                          [(f"02:00:{n >> 24 & 255:02X}:{n >> 16 & 255:02X}:{n >> 8 & 255:02X}:{n & 255:02X}", MACS[0]) for n in range(150000)])
    sizes, consumed = [], [0]
    original = analytics_stack.gateway._partial_evidence_connection
    class Cursor:
        def __init__(self, cursor): self.cursor = cursor
        def __getattr__(self, name): return getattr(self.cursor, name)
        def __iter__(self): return iter(self.cursor)
        def fetchmany(self, size):
            batch = self.cursor.fetchmany(size)
            sizes.append((size, len(batch)))
            return batch
    class Connection:
        def __init__(self, connection): self.connection = connection
        def __getattr__(self, name): return getattr(self.connection, name)
        def execute(self, *args): return Cursor(self.connection.execute(*args))
    @contextmanager
    def measured(deadline):
        with original(deadline) as c:
            yield Connection(c)
    monkeypatch.setattr(analytics_stack.gateway, "_partial_evidence_connection", measured)
    def consume(cycle, rows):
        consumed[0] += 1
        for _ in rows: pass
        return False
    with pytest.raises(PartialTrafficCapacityLimited):
        analytics_stack.gateway.read_partial_ap_traffic_evidence(
            site_id=SITE, from_utc=START, to_utc=EVALUATED,
            deadline=QueryDeadline.after(60), consume_cycle=consume)
    assert consumed[0] == (10080 if bound == "cycles" else 1)
    assert sizes and all(size == 2000 and length <= 2000 for size, length in sizes)
