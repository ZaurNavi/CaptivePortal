from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.analytics.source_gateway import QueryDeadline
from app.network_metadata.validation import ni_format_utc
from app.network_protocol_intelligence.read_service import DeviceProtocolIntelligenceReadService, _READ_SLOTS, _COVERAGE
from app.network_protocol_intelligence.models import (
    ProtocolUnavailable, ProtocolValidationError, ProtocolBusy, ProtocolDeadline,
    ProtocolCoverageV1, public_summary, freshness,
)

SITE = "0123456789abcdef01234567"
DEVICE = "10000000-0000-4000-8000-000000000001"
MAC = "02:00:00:00:00:01"
AT = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)


class Reader:
    def __init__(self, facts=(), state="usable", binding="authoritative", bound=DEVICE):
        self.value = dict(runtime_state=state, binding_state=binding, bound_device_id=bound, facts=facts)
        self.calls = []

    def read_protocol_evidence_snapshot(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.value


def fact(protocol="dns", age=1, edge="a"):
    return dict(source_event_family=protocol, event_at=ni_format_utc(AT - timedelta(seconds=age)), edge_id=edge)


def summary(reader, **kwargs):
    return DeviceProtocolIntelligenceReadService(reader).get_device_protocol_summary(
        SITE, DEVICE, MAC, evaluated_at_utc=ni_format_utc(AT), deadline=kwargs.get("deadline", QueryDeadline.after(20)))


def test_protocol_aggregation_order_and_narrow_read_contract():
    reader = Reader([fact("tls", 20), fact("dns", 20), fact("quic", 20), fact("dns", 30)])
    value = public_summary(summary(reader))
    assert [p["protocol_id"] for p in value["recent_protocols"]] == ["dns", "tls", "quic"]
    assert value["last_protocol_observation"]["protocol_id"] == "dns"
    assert len(reader.calls) == 1
    args, kwargs = reader.calls[0]
    assert args == (SITE, DEVICE, MAC, ni_format_utc(AT - timedelta(days=1)), ni_format_utc(AT))
    assert kwargs["max_rows"] == 20000
    assert 0 < kwargs["deadline"].expires_at - kwargs["deadline"].monotonic() <= 5
    assert not any(key in str(value) for key in ("edge_id", "client_mac", "source_event_family"))


@pytest.mark.parametrize("age,recent,accepted", [(3600, True, True), (3600.000001, False, True),
    (86400, False, True), (86400.000001, False, False), (0, False, False), (-1, False, False)])
def test_event_window_boundaries(age, recent, accepted):
    if not accepted:
        with pytest.raises(ProtocolUnavailable):
            summary(Reader([fact(age=age)]))
    else:
        value = summary(Reader([fact(age=age)]))
        assert bool(value.recent_protocols) is recent


@pytest.mark.parametrize("age,expected", [(0, "fresh"), (300, "fresh"), (300.000001, "recent"),
    (3600, "recent"), (3600.000001, "stale"), (86400, "stale")])
def test_base_freshness_boundaries(age, expected):
    assert freshness(age, ProtocolCoverageV1("current_pipeline", "usable", "usable", "usable", False)) == expected


@pytest.mark.parametrize("state,expected", [("usable", "fresh"), ("registry_degraded", "fresh"),
    ("attribution_unavailable", "recent"), ("source_unavailable", "stale"),
    ("capacity_waiting_reader", "recent"), ("capacity_halted", "recent"), ("blocked_conflict", "recent"),
    ("degraded", "recent"), ("initializing", "stale"), ("stopping", "stale")])
def test_exact_coverage_caps(state, expected):
    value = summary(Reader([fact()], state=state))
    assert value.freshness_state == expected
    assert (value.coverage.projection_state, value.coverage.source_state, value.coverage.attribution_state) == _COVERAGE[state]
    assert value.coverage.historical_window_completeness_claimed is False


@pytest.mark.parametrize("binding,identity", [(None, "absent"), ("not_yet_registry_resolved", "pending"),
    ("registry_unavailable", "unavailable")])
def test_identity_pending(binding, identity):
    value = summary(Reader(binding=binding, bound=None))
    assert value.evidence_state == "identity_pending" and value.identity_binding_state == identity
    assert value.freshness_state == "unavailable"
    assert value.availability_state == "degraded"
    assert value.coverage.projection_state == "usable"


@pytest.mark.parametrize("binding", ["authoritative", "not_yet_registry_resolved", "registry_unavailable", None])
@pytest.mark.parametrize("state", ["usable", "degraded"])
def test_availability_requires_usable_projection_and_authoritative_identity(binding, state):
    value = summary(Reader(state=state, binding=binding, bound=DEVICE if binding == "authoritative" else None))
    expected = "usable" if state == "usable" and binding == "authoritative" else "degraded"
    assert value.availability_state == expected
    assert value.coverage.projection_state == state
    assert public_summary(value)["availability_state"] == expected
    with pytest.raises(ProtocolUnavailable):
        public_summary(replace(value, availability_state="degraded" if expected == "usable" else "usable"))


@pytest.mark.parametrize("reader", [Reader([fact("tcp")]), Reader([fact("udp")]), Reader([fact("other")]),
    Reader(state="unexpected"), Reader(bound="20000000-0000-4000-8000-000000000002"),
    Reader([fact()], binding="not_yet_registry_resolved", bound=None), Reader(binding="bad")])
def test_integrity_fail_closed(reader):
    with pytest.raises(ProtocolUnavailable):
        summary(reader)


def test_row_limit_no_partial_summary():
    assert summary(Reader([fact()] * 20000)).evidence_state == "present"
    with pytest.raises(ProtocolUnavailable):
        summary(Reader([fact()] * 20001))


def test_deadline_and_shared_two_slot_gate_release():
    with pytest.raises(ProtocolDeadline):
        summary(Reader(), deadline=QueryDeadline.after(-1))
    assert _READ_SLOTS.acquire(False) and _READ_SLOTS.acquire(False)
    try:
        with pytest.raises(ProtocolBusy):
            summary(Reader())
    finally:
        _READ_SLOTS.release(); _READ_SLOTS.release()
    assert summary(Reader()).evidence_state == "empty"


def test_serializer_refuses_malformed_and_extra_shapes():
    value = summary(Reader([fact()]))
    for invalid in (replace(value, schema_version=True), replace(value, freshness_state="other"),
                    replace(value, coverage=replace(value.coverage, historical_window_completeness_claimed=True)),
                    replace(value, window=replace(value.window, duration_seconds=1)), {**public_summary(value), "peer_ip": "private"}):
        with pytest.raises(ProtocolUnavailable):
            public_summary(invalid)


def test_no_facts_has_no_last_observation():
    value = summary(Reader(state="attribution_unavailable"))
    assert value.evidence_state == "empty" and value.last_protocol_observation is None
    assert value.freshness_state == "unavailable"


def test_microsecond_order_and_bad_retained_timestamp_fail_closed():
    value = summary(Reader([fact("dns", 1.000001), fact("tls", 1)]))
    assert value.last_protocol_observation.protocol_id == "tls"
    assert [item.protocol_id for item in value.recent_protocols] == ["tls", "dns"]
    with pytest.raises(ProtocolUnavailable):
        summary(Reader([{**fact(), "event_at": "not-a-time"}]))


@pytest.mark.parametrize("site,device,mac,time", [("bad", DEVICE, MAC, ni_format_utc(AT)),
    (SITE, "bad", MAC, ni_format_utc(AT)), (SITE, DEVICE, "bad", ni_format_utc(AT)),
    (SITE, DEVICE, MAC, "2026-10-09T12:00:00Z")])
def test_semantic_validation_safe(site, device, mac, time):
    with pytest.raises(ProtocolValidationError):
        DeviceProtocolIntelligenceReadService(Reader()).get_device_protocol_summary(
            site, device, mac, evaluated_at_utc=time, deadline=QueryDeadline.after(5))
