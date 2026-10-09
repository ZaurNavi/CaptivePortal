"""T1 exact NI-01 event-time queries against the unchanged ms writer."""
from dataclasses import asdict
from datetime import timedelta

import pytest

from app.network_attribution.models import NetworkAttributionValidationError
from app.network_attribution.validation import make_fact, query_values, read_query_values, validate_fact
from .test_authority import SITE, SOURCE, IP, MAC, T0, fact, store, ts


def ack(repository, milliseconds, *, lease=1):
    values = asdict(fact(0, lease=lease))
    values.pop("fact_id")
    values.pop("schema_version")
    values["event_at"] = (T0 + timedelta(milliseconds=milliseconds)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    values["ingested_at"] = values["event_at"]
    return repository.record(make_fact(**values))


def micro(suffix):
    return "2026-10-09T12:00:" + suffix + "Z"


@pytest.mark.parametrize("suffix,state", [
    ("00.122999", "unattributed"), ("00.123000", "resolved"),
    ("00.123001", "resolved"), ("01.122999", "resolved"),
    ("01.123000", "unattributed"), ("01.123001", "unattributed"),
])
def test_exact_half_open_binding_boundaries(store, suffix, state):
    repository, reader, _ = store
    binding = ack(repository, 123)
    repository.confirm_capture(SITE, SOURCE, ts(2))
    value = micro(suffix)
    result = reader.resolve_ipv4(SITE, IP, value)
    assert result.state == state
    assert result.event_at == value
    if state == "resolved":
        assert result.event_at == value
        assert result.binding_id == binding.binding_id
        assert result.client_mac == MAC


@pytest.mark.parametrize("suffix,state", [
    ("00.122999", "resolved"), ("00.123000", "resolved"),
    ("00.123001", "unavailable"),
])
def test_exact_open_watermark(store, suffix, state):
    repository, reader, _ = store
    repository.record(fact(0))
    repository.confirm_capture(SITE, SOURCE, micro("00.123"))
    result = reader.resolve_ipv4(SITE, IP, micro(suffix))
    assert result.state == state
    if state == "unavailable":
        assert result.reason == "source_coverage_unavailable"


@pytest.mark.parametrize("suffix,state", [
    ("10.499999", "resolved"), ("10.500000", "unavailable"), ("10.500001", "unavailable"),
    ("11.499999", "unavailable"), ("11.500000", "resolved"), ("11.500001", "resolved"),
])
def test_outage_and_recovery_half_open_boundaries(store, suffix, state):
    repository, reader, _ = store
    repository.record(fact(0))
    repository.coverage(SITE, SOURCE, "unavailable", micro("10.500"), "capture_gap")
    repository.coverage(SITE, SOURCE, "usable", micro("11.500"))
    ack(repository, 11500, lease=100)
    repository.confirm_capture(SITE, SOURCE, ts(12))
    assert reader.resolve_ipv4(SITE, IP, micro(suffix)).state == state


def test_recovery_without_new_ack_does_not_erase_historical_gap(store):
    repository, reader, _ = store
    repository.record(fact(0))
    repository.coverage(SITE, SOURCE, "unavailable", ts(1), "capture_gap")
    repository.coverage(SITE, SOURCE, "usable", ts(2))
    repository.confirm_capture(SITE, SOURCE, ts(3))
    assert reader.resolve_ipv4(SITE, IP, micro("02.000001")).reason == "source_coverage_gap"


@pytest.mark.parametrize("suffix,state", [
    ("00.122999", "outside_historical_horizon"),
    ("00.123000", "resolved"), ("00.123001", "resolved"),
])
def test_exact_horizon(store, suffix, state):
    repository, reader, _ = store
    repository.record(fact(0))
    repository.confirm_capture(SITE, SOURCE, ts(1))
    repository.connection.execute("UPDATE authority_horizon SET first_usable_at=?,retained_from=?",
                                  (micro("00.123"), micro("00.123")))
    assert reader.resolve_ipv4(SITE, IP, micro(suffix)).state == state


@pytest.mark.parametrize("suffix", ["00.123", "00.123000", "00.123456"])
def test_read_accepts_only_two_canonical_precisions(suffix):
    exact, floor = read_query_values(SITE, IP, micro(suffix))
    assert floor == micro("00.123")
    assert exact.microsecond == (123456 if suffix.endswith("123456") else 123000)


@pytest.mark.parametrize("value", [
    micro("00.1"), micro("00.12"), micro("00.1234"), micro("00.12345"), micro("00.1234567"),
    "2026-10-09T12:00:00Z", "2026-10-09T12:00:00.123+00:00",
    "2026-02-30T12:00:00.123000Z", "2026-10-09T24:00:00.123000Z",
])
def test_invalid_read_query_formats(store, value):
    assert store[1].resolve_ipv4(SITE, IP, value).state == "invalid"
    with pytest.raises(NetworkAttributionValidationError):
        read_query_values(SITE, IP, value)


def test_writer_stays_ms_only():
    query_values(SITE, IP, micro("00.123"))
    with pytest.raises(NetworkAttributionValidationError):
        query_values(SITE, IP, micro("00.123000"))
    values = asdict(fact(0))
    values.pop("fact_id")
    values.pop("schema_version")
    values["event_at"] = micro("00.123456")
    with pytest.raises(NetworkAttributionValidationError):
        make_fact(**values)
    validate_fact(fact(0))


def test_millis_micros_equivalence_preserves_caller_representation(store):
    repository, reader, _ = store
    binding = ack(repository, 123)
    repository.confirm_capture(SITE, SOURCE, ts(1))
    ms, us = [reader.resolve_ipv4(SITE, IP, micro(value)) for value in ("00.123", "00.123000")]
    assert ms.state == us.state == "resolved"
    left, right = asdict(ms), asdict(us)
    assert left.pop("event_at") == micro("00.123")
    assert right.pop("event_at") == micro("00.123000")
    assert left == right and ms.binding_id == binding.binding_id


def test_horizon_is_read_only_bounded_and_disabled_safe(store, monkeypatch):
    import sqlite3
    from app.network_attribution.read_service import NetworkAttributionReadService
    from app.network_attribution.models import NetworkAttributionConfig
    repository, reader, _ = store
    statements, original = [], sqlite3.connect
    def connect(*args, **kwargs):
        if args[0] != ":memory:":
            assert args[0].endswith("?mode=ro")
        connection = original(*args, **kwargs)
        connection.set_trace_callback(statements.append)
        return connection
    monkeypatch.setattr(sqlite3, "connect", connect)
    result = reader.get_authority_horizon(SITE)
    assert result.state == "available" and result.first_usable_at == result.retained_from == ts()
    assert "PRAGMA query_only=ON" in statements
    assert not any("quick_check" in value or "foreign_key_check" in value for value in statements)
    assert reader.get_authority_horizon("f" * 24).state == "unavailable"
    assert NetworkAttributionReadService(NetworkAttributionConfig()).get_authority_horizon(SITE).reason == "attribution_disabled"
    repository.connection.execute("PRAGMA user_version=2")
    assert reader.get_authority_horizon(SITE).state == "unavailable"
