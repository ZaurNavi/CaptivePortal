"""Recovery observability uses disposable stores, never persisted retry history."""
import json
import logging
from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.network_metadata_projection.telemetry import (
    ProjectionTelemetry, RETRY_COUNTER_FIELDS, MAX_COUNTER,
)
from .support import stack
from .test_projection import edges


@pytest.fixture
def state(tmp_path, caplog):
    value = stack(tmp_path)
    value.service.telemetry = ProjectionTelemetry(logging.getLogger("recovery-test"))
    caplog.set_level(logging.INFO, logger="recovery-test")
    try:
        yield value
    finally:
        value.repo.close()


def counters(caplog):
    return [json.loads(record.message) for record in caplog.records
            if record.name == "recovery-test" and
            json.loads(record.message).get("event") == "attribution_retry_counters"][-1]


@pytest.mark.parametrize("field", sorted(RETRY_COUNTER_FIELDS))
@pytest.mark.parametrize("value", [0, 1, MAX_COUNTER])
def test_each_counter_accepts_only_safe_bounds(caplog, field, value):
    caplog.set_level(logging.INFO, logger="recovery-test")
    ProjectionTelemetry(logging.getLogger("recovery-test")).emit("attribution_retry_counters", **{field: value})
    assert counters(caplog) == {"event": "attribution_retry_counters", field: value}


@pytest.mark.parametrize("field", sorted(RETRY_COUNTER_FIELDS))
@pytest.mark.parametrize("value", [-1, MAX_COUNTER + 1, 1.5, "1", None, True, False])
def test_bad_counter_values_fail_closed(field, value):
    with pytest.raises(ValueError):
        ProjectionTelemetry().emit("attribution_retry_counters", **{field: value})


@pytest.mark.parametrize("field", ["ip", "mac", "device_id", "sni", "dns", "binding_id",
    "observation_id", "payload", "site_id", "reason_code", "unknown"])
def test_new_event_has_no_identifier_or_payload_fields(field):
    with pytest.raises(ValueError):
        ProjectionTelemetry().emit("attribution_retry_counters", **{field: "privacy-canary"})


def test_closed_event_separation_and_existing_telemetry(caplog):
    caplog.set_level(logging.INFO, logger="recovery-test")
    telemetry = ProjectionTelemetry(logging.getLogger("recovery-test"))
    for event, values in [("unknown", {}), ("attribution_retry_counters", {}),
                          ("batch_committed", {"pending_attribution_count": 1}),
                          ("batch_committed", {"payload": "private"})]:
        with pytest.raises(ValueError):
            telemetry.emit(event, **values)
    telemetry.emit("batch_committed", count=2)
    assert json.loads(caplog.records[-1].message) == {"event": "batch_committed", "count": 2}


@pytest.mark.parametrize("outcome", ["unavailable", "resolved", "ambiguous", "unattributed",
    "outside_historical_horizon", "unsupported_address_family", "endpoint_absent"])
def test_retry_role_outcomes_and_immutable_opposite_edge(state, caplog, outcome):
    state.attribution.states["10.73.0.8"] = "unavailable"
    state.service.poll()
    old = edges(state)
    before = dict(state.repo.connection.execute("SELECT * FROM projection_pending_attribution").fetchone())
    state.service.retry()  # Not eligible before the existing 30-second boundary.
    assert counters(caplog)["attribution_retry_attempted_roles"] == 0
    state.clock.advance(seconds=30)
    state.attribution.calls.clear()
    state.attribution.states = {"10.73.0.7": "invalid", "10.73.0.8": outcome}
    state.service.retry()
    report = counters(caplog)
    assert set(report) == {"event"} | RETRY_COUNTER_FIELDS
    assert report["attribution_retry_attempted_roles"] == 1
    assert report["attribution_retry_resolved_roles"] == int(outcome == "resolved")
    assert report["attribution_retry_still_unavailable_roles"] == int(outcome == "unavailable")
    assert report["attribution_retry_terminal_roles"] == int(outcome not in {"resolved", "unavailable"})
    assert report["pending_attribution_count"] == int(outcome == "unavailable")
    assert report["pending_oldest_age_seconds"] == (30 if outcome == "unavailable" else 0)
    assert report["attribution_retry_expired_unresolved"] == 0
    assert [call[1] for call in state.attribution.calls] == ["10.73.0.8"]
    assert all(row in edges(state) for row in old)
    assert len(edges(state)) == (2 if outcome == "resolved" else 1)
    if outcome == "unavailable":
        after = dict(state.repo.connection.execute("SELECT * FROM projection_pending_attribution").fetchone())
        assert after["first_pending_at"] == before["first_pending_at"]
        assert after["next_retry_at"] > before["next_retry_at"]
    else:
        state.clock.advance(seconds=30)
        state.service.retry()
        assert counters(caplog)["attribution_retry_attempted_roles"] == 0
        assert len(edges(state)) == (2 if outcome == "resolved" else 1)
    for private in ("10.73.", "00:11:", "observation_id", "device_id", "binding_id", "sni", "payload"):
        assert private not in json.dumps(report)


@pytest.mark.parametrize("missing", [True, False])
def test_expired_retry_counter_without_new_edge_or_rewrite(state, caplog, missing):
    state.attribution.states["10.73.0.8"] = "unavailable"
    state.service.poll()
    old = edges(state)
    state.clock.advance(seconds=30)
    state.source.records = ([] if missing else [
        replace(state.source.records[0], sensitive_endpoint_presence_state="expired", src_ip=None, dst_ip=None)])
    state.service.retry()
    report = counters(caplog)
    assert report["attribution_retry_expired_unresolved"] == 1
    assert report["attribution_retry_attempted_roles"] == report["pending_attribution_count"] == 0
    assert edges(state) == old


def test_pending_reason_requires_actual_read_and_preserves_failure_on_empty_poll(state, caplog):
    state.attribution.states["10.73.0.8"] = "unavailable"
    state.service.poll()
    assert (state.repo.live_state, state.repo.live_reason) == ("attribution_unavailable", "pending_attribution")
    state.attribution.get_authority_horizon = lambda _: SimpleNamespace(state="unavailable")
    state.clock.advance(seconds=30)
    state.service.retry()
    assert state.repo.live_reason == "attribution_authority_unavailable"
    assert counters(caplog)["attribution_authority_unavailable_count"] == 1
    assert counters(caplog)["attribution_retry_still_unavailable_roles"] == 1
    state.service.poll()  # Empty successful source poll is not an authority probe.
    assert state.repo.live_reason == "attribution_authority_unavailable"
    state.repo.attribution_read_state = None  # A fresh process has no demonstrated authority read.
    state.service.poll()
    assert state.repo.live_reason == "attribution_authority_unavailable"


def test_store_exception_is_not_pending_only_even_with_successful_horizon(state):
    original = state.attribution.resolve_ipv4
    def resolve(site, ip, event):
        if ip == "10.73.0.8":
            raise OSError("private-store-canary")
        return original(site, ip, event)
    state.attribution.resolve_ipv4 = resolve
    state.service.poll()
    assert state.repo.live_reason == "attribution_authority_unavailable"
    assert len(edges(state)) == 1


@pytest.mark.parametrize("runtime", ["blocked_conflict", "capacity_halted", "capacity_waiting_reader", "source_unavailable"])
def test_retry_success_does_not_erase_stronger_runtime_failure(state, runtime):
    state.repo.runtime(runtime, runtime)
    # Check success-state precedence itself. Normal post-commit capacity
    # maintenance may legitimately clear recovered pressure, independently.
    state.repo.success_state()
    assert state.repo.live_state == runtime


def test_retry_invalid_retains_pending_and_blocks_without_reinterpretation(state):
    state.attribution.states["10.73.0.8"] = "unavailable"
    state.service.poll()
    before = tuple(state.repo.connection.execute("SELECT * FROM projection_pending_attribution").fetchone())
    old = edges(state)
    state.clock.advance(seconds=30)
    state.attribution.states["10.73.0.8"] = "invalid"
    state.service.tick()
    assert state.repo.live_state == "blocked_conflict"
    assert tuple(state.repo.connection.execute("SELECT * FROM projection_pending_attribution").fetchone()) == before
    assert edges(state) == old


def test_failed_retry_commit_cannot_publish_resolved_outcome(state, caplog):
    state.attribution.states["10.73.0.8"] = "unavailable"
    state.service.poll()
    old = edges(state)
    state.clock.advance(seconds=30)
    state.attribution.states.clear()
    def fail(point):
        if point == "before_commit":
            raise RuntimeError("disposable transaction failure")
    state.repo.crash_point = fail
    with pytest.raises(RuntimeError):
        state.service.retry()
    assert edges(state) == old
    assert state.service._retry_counts["attribution_retry_attempted_roles"] == 1
    assert state.service._retry_counts["attribution_retry_resolved_roles"] == 0
    state.repo.crash_point = lambda _: None
    state.service.retry()
    assert counters(caplog)["attribution_retry_attempted_roles"] == 2
    assert counters(caplog)["attribution_retry_resolved_roles"] == 1


def test_idle_empty_poll_keeps_safe_reason_without_extra_writes(state):
    config = replace(state.config, idle_write_reduction_enabled=True)
    state.repo.config = state.service.config = config
    tick = [100.0]
    state.repo.monotonic = state.service.monotonic = lambda: tick[0]
    state.attribution.states["10.73.0.8"] = "unavailable"
    state.service.poll()
    assert state.repo.source_verified_in_run is True
    assert state.repo.live_reason == "pending_attribution"
    changes = state.repo.connection.total_changes
    calls = tuple(state.attribution.calls)
    for _ in range(3):
        tick[0] += 1
        state.clock.advance(seconds=1)
        state.service.poll()
    assert state.repo.connection.total_changes == changes
    assert tuple(state.attribution.calls) == calls
    assert state.repo.live_reason == "pending_attribution"
    tick[0] += 10
    state.clock.advance(seconds=10)
    state.service.poll()
    assert state.repo.connection.total_changes > changes
    assert state.repo.live_reason == "pending_attribution"


def test_failure_then_confirmed_retry_recovers_reason_without_rewriting_edges(state):
    state.attribution.states["10.73.0.8"] = "unavailable"
    original = state.attribution.get_authority_horizon
    state.attribution.get_authority_horizon = lambda _: SimpleNamespace(state="unavailable")
    state.service.poll()
    assert state.repo.live_reason == "attribution_authority_unavailable"
    state.clock.advance(seconds=30)
    state.attribution.get_authority_horizon = original
    state.service.retry()
    assert state.repo.live_reason == "pending_attribution"
    old = edges(state)
    state.clock.advance(seconds=30)
    state.attribution.states.clear()
    state.service.retry()
    assert state.repo.live_reason is None
    assert all(row in edges(state) for row in old)


def test_existing_success_aggregation_remains_independent(caplog):
    caplog.set_level(logging.INFO, logger="recovery-test")
    telemetry = ProjectionTelemetry(logging.getLogger("recovery-test"))
    clock = [0.0]
    telemetry.enable_aggregation(monotonic=lambda: clock[0])
    telemetry.emit("batch_committed", count=2)
    telemetry.emit("attribution_retry_counters", pending_attribution_count=1)
    assert counters(caplog)["pending_attribution_count"] == 1
    clock[0] += 61
    telemetry.flush_due()
    summaries = [json.loads(record.message) for record in caplog.records]
    assert any(row.get("record_count") == 2 and row.get("batch_count") == 1 for row in summaries)
