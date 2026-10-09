import ipaddress
import sqlite3
import struct
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone

import pytest

from app.device_fingerprint.validation import format_utc
from app.device_fingerprint_sensor.config import sensor_config_from_env
from app.network_attribution.config import network_attribution_config_from_env
from app.network_attribution.dhcp_authority import authority_fact_from_frame
from app.network_attribution.models import (
    NetworkAttributionConfig, NetworkAttributionConflict,
    NetworkAttributionStorageUnavailable, NetworkAttributionValidationError,
)
from app.network_attribution.read_service import NetworkAttributionReadService
from app.network_attribution.repository import NetworkAttributionRepository

T0 = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
SITE = "6a64f17630da7c70d232187a"
OTHER_SITE = "6a64f17630da7c70d232187b"
SOURCE = "zefer-span-01"
MAC = "00:11:22:33:44:55"
OTHER_MAC = "00:11:22:33:44:66"
IP = "192.168.8.20"
OTHER_IP = "192.168.8.21"


def ts(seconds=0):
    return format_utc(T0 + timedelta(seconds=seconds))


def option(code, value):
    return bytes((code, len(value))) + value


def frame(*, message=5, mac=MAC, ip=IP, server="192.168.10.1", option54="192.168.10.1",
          lease=3600, xid=123, extra=b""):
    raw_mac = bytes.fromhex(mac.replace(":", ""))
    data = bytearray(236)
    data[:3] = bytes((2 if message == 5 else 1, 1, 6))
    struct.pack_into("!I", data, 4, xid)
    data[28:34] = raw_mac
    if message == 5:
        data[16:20] = ipaddress.IPv4Address(ip).packed
    elif message == 7:
        data[12:16] = ipaddress.IPv4Address(ip).packed
    options = option(53, bytes((message,)))
    if message == 4:
        options += option(50, ipaddress.IPv4Address(ip).packed)
    if option54 is not None:
        options += option(54, ipaddress.IPv4Address(option54).packed)
    if lease is not None:
        options += option(51, lease.to_bytes(4, "big"))
    payload = bytes(data) + b"\x63\x82\x53\x63" + options + extra + b"\xff"
    udp = struct.pack("!HHHH", 67 if message == 5 else 68, 68 if message == 5 else 67, 8 + len(payload), 0) + payload
    header = bytearray(20)
    header[0], header[8], header[9] = 0x45, 64, 17
    struct.pack_into("!H", header, 2, 20 + len(udp))
    header[12:16] = ipaddress.IPv4Address(server if message == 5 else ip).packed
    return b"\xff" * 6 + raw_mac + b"\x08\x00" + bytes(header) + udp


def fact(seconds=0, *, sensor=None, **kwargs):
    sensor = sensor or sensor_config_from_env({"DEVICE_FINGERPRINT_SENSOR_ENABLED": "true"})
    return authority_fact_from_frame(frame(**kwargs), ts(seconds), ts(seconds + 1), sensor)


@pytest.fixture
def store(tmp_path):
    config = NetworkAttributionConfig(True, str(tmp_path / "attribution.sqlite3"))
    repository = NetworkAttributionRepository(config, clock=lambda: T0).initialize()
    repository.coverage(SITE, SOURCE, "usable", ts())
    reader = NetworkAttributionReadService(config, clock=lambda: T0)
    yield repository, reader, config
    repository.close()


def held_reader(config):
    connection = sqlite3.connect(config.db_path, isolation_level=None)
    connection.execute("PRAGMA query_only=ON")
    connection.execute("BEGIN")
    connection.execute("SELECT * FROM source_coverage").fetchall()
    return connection


def footprint(config):
    from pathlib import Path
    return sum(path.stat().st_size for path in (
        Path(config.db_path), Path(config.db_path + "-wal"),
        Path(config.db_path + "-shm")) if path.exists())


def test_r1_a_held_reader_does_not_kill_writer(store):
    repository, _, config = store
    assert repository.connection.execute("PRAGMA wal_autocheckpoint").fetchone()[0] == 1000
    reader = held_reader(config)
    try:
        before = reader.execute("SELECT verified_through FROM source_coverage").fetchone()[0]
        # Reproduce the old mandatory-TRUNCATE busy condition, independently
        # of the new write path, against a committed WAL snapshot.
        assert repository.connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0] == 1
        repository.confirm_capture(SITE, SOURCE, ts(1))
        repository.confirm_capture(SITE, SOURCE, ts(2))
        assert reader.in_transaction
        assert reader.execute("SELECT verified_through FROM source_coverage").fetchone()[0] == before
        assert repository.connection.execute("SELECT verified_through FROM source_coverage").fetchone()[0] == ts(2)
        assert repository.maintain_wal() is False
    finally:
        reader.close()
    assert repository.maintain_wal() is True


def test_r1_c_bounded_maintenance_reclaims_after_reader_release(store):
    from pathlib import Path
    repository, _, config = store
    reader = held_reader(config)
    try:
        for second in range(1, 21):
            repository.confirm_capture(SITE, SOURCE, ts(second))
            assert repository.maintain_wal() is False
            assert footprint(config) <= config.max_db_bytes
        wal_before = Path(config.db_path + "-wal").stat().st_size
        assert wal_before > 0
    finally:
        reader.close()
    assert repository.maintain_wal() is True
    assert Path(config.db_path + "-wal").stat().st_size == 0
    assert footprint(config) < config.max_db_bytes
    repository.confirm_capture(SITE, SOURCE, ts(21))


def test_r1_c_actual_footprint_exhaustion_still_fails_closed(tmp_path):
    config = NetworkAttributionConfig(True, str(tmp_path / "bounded.sqlite3"), 262144)
    repository = NetworkAttributionRepository(config, clock=lambda: T0).initialize()
    repository.coverage(SITE, SOURCE, "usable", ts())
    reader = held_reader(config)
    try:
        with pytest.raises(NetworkAttributionStorageUnavailable, match="attribution_capacity_exhausted"):
            for second in range(1, 129):
                repository.confirm_capture(SITE, SOURCE, ts(second))
                repository.maintain_wal()
            pytest.fail("configured WAL footprint cap was not enforced")
        assert footprint(config) > config.max_db_bytes
        with pytest.raises(NetworkAttributionStorageUnavailable):
            repository.confirm_capture(SITE, SOURCE, ts(130))
        service = NetworkAttributionReadService(config, clock=lambda: T0)
        assert service.resolve_ipv4(SITE, IP, ts()).state == "unavailable"
        assert reader.execute("SELECT count(*) FROM source_coverage").fetchone()[0] == 1
    finally:
        reader.close()
        repository.close()


@pytest.mark.parametrize("message,busy", [("database is locked", True), ("disk I/O error", False)])
def test_r1_maintenance_busy_is_deferred_but_io_failure_is_unavailable(store, monkeypatch, message, busy):
    repository, _, _ = store
    original = repository.connection

    class Connection:
        def execute(self, statement):
            assert statement == "PRAGMA wal_checkpoint(PASSIVE)"
            raise sqlite3.OperationalError(message)

    monkeypatch.setattr(repository, "connection", Connection())
    try:
        if busy:
            assert repository.maintain_wal() is False
        else:
            with pytest.raises(NetworkAttributionStorageUnavailable):
                repository.maintain_wal()
    finally:
        repository.connection = original


def test_r1_d_resolve_has_no_per_query_full_integrity_scan(tmp_path, monkeypatch):
    from app.network_attribution import schema
    original_integrity, original_connect = schema.validate_storage_integrity, sqlite3.connect
    integrity_calls, statements = [], []

    def integrity(connection):
        integrity_calls.append(connection)
        return original_integrity(connection)

    def connect(*args, **kwargs):
        connection = original_connect(*args, **kwargs)
        connection.set_trace_callback(statements.append)
        return connection

    monkeypatch.setattr(schema, "validate_storage_integrity", integrity)
    monkeypatch.setattr(sqlite3, "connect", connect)
    config = NetworkAttributionConfig(True, str(tmp_path / "hot-path.sqlite3"))
    repository = NetworkAttributionRepository(config, clock=lambda: T0).initialize()
    try:
        assert len(integrity_calls) == 1
        assert "PRAGMA quick_check" in statements
        assert "PRAGMA foreign_key_check" in statements
        repository.coverage(SITE, SOURCE, "usable", ts())
        repository.record(fact())
        reader = NetworkAttributionReadService(config, clock=lambda: T0)
        statements.clear()
        for _ in range(5):
            assert reader.resolve_ipv4(SITE, IP, ts()).state == "resolved"
        assert len(integrity_calls) == 1
        assert not any(statement.lower().startswith(("pragma quick_check", "pragma foreign_key_check"))
                       for statement in statements)
        assert statements.count("PRAGMA user_version") == 5
    finally:
        repository.close()
    # Re-opening the writer retains full validation, including its read-only probe.
    statements.clear()
    repository.initialize()
    try:
        assert len(integrity_calls) == 3
        assert statements.count("PRAGMA quick_check") == 2
        assert statements.count("PRAGMA foreign_key_check") == 2
    finally:
        repository.close()


@pytest.mark.parametrize("mutation", [
    "PRAGMA user_version=2",
    "CREATE TABLE foreign_table(value TEXT)",
    "DELETE FROM attribution_schema",
])
def test_r1_e_read_schema_is_revalidated_and_fails_closed(store, mutation):
    repository, reader, _ = store
    repository.record(fact())
    assert reader.resolve_ipv4(SITE, IP, ts()).state == "resolved"
    repository.connection.execute(mutation)
    assert reader.resolve_ipv4(SITE, IP, ts()).state == "unavailable"


def resolve(store, seconds, *, site=SITE, ip=IP):
    repository, reader, _ = store
    active = repository.connection.execute("SELECT * FROM source_coverage WHERE site_id=? AND capture_source_id=? AND coverage_until IS NULL", (site, SOURCE)).fetchone()
    if active and active["state"] == "usable" and ts(seconds) >= active["verified_through"]:
        repository.confirm_capture(site, SOURCE, ts(seconds))
    return reader.resolve_ipv4(site, ip, ts(seconds))


def test_trusted_ack_exact_finite_fact_and_interval(store):
    repository, _, _ = store
    value = fact()
    interval = repository.record(value)
    assert interval.valid_from == interval.last_confirmed_at == ts()
    assert interval.valid_until == interval.lease_expires_at == ts(3600)
    assert interval.start_fact_id == interval.last_fact_id == value.fact_id
    assert value.authority_class == "trusted_dhcp_ack"
    assert value.client_mac == MAC
    result = resolve(store, 0)
    assert result.state == "resolved" and result.attribution_source == "trusted_dhcp_v4"
    assert "device_id" not in asdict(result)
    with pytest.raises(sqlite3.IntegrityError):
        repository.connection.execute("UPDATE authority_facts SET lease_seconds=1")


@pytest.mark.parametrize("kwargs", [
    {"server": "192.168.0.1"}, {"option54": "192.168.0.1"}, {"option54": None},
    {"ip": "192.168.0.20"}, {"lease": None}, {"lease": 0}, {"lease": 86401},
    {"mac": "00:00:00:00:00:00"}, {"mac": "FF:FF:FF:FF:FF:FF"},
    {"message": 1}, {"message": 2}, {"message": 3},
])
def test_untrusted_or_non_authority_packets_are_rejected(kwargs):
    assert fact(**kwargs) is None


@pytest.mark.parametrize("extra", [option(51, (3600).to_bytes(4, "big")), option(54, b"\x01\x02\x03\x04"), option(53, b"\x05"), b"\x32\x04\x01"])
def test_malformed_or_duplicate_authority_options_rejected(extra):
    assert fact(extra=extra) is None


def test_fragment_and_bootp_shape_rejected():
    sensor = sensor_config_from_env({"DEVICE_FINGERPRINT_SENSOR_ENABLED": "true"})
    for offset, value in ((20, 0x20), (42, 1), (43, 2)):
        raw = bytearray(frame())
        raw[offset] = value
        assert authority_fact_from_frame(bytes(raw), ts(), ts(), sensor) is None


def test_renewal_one_interval_and_historical_confirmation(store):
    repository, _, _ = store
    original = repository.record(fact(0, lease=1200))
    renewed = repository.record(fact(600, lease=1800, xid=124))
    assert original.binding_id == renewed.binding_id
    assert renewed.valid_from == ts()
    assert renewed.last_confirmed_at == ts(600)
    assert renewed.valid_until == renewed.lease_expires_at == ts(2400)
    assert repository.connection.execute("SELECT count(*) FROM binding_intervals").fetchone()[0] == 1
    assert resolve(store, 100).state == "resolved"


@pytest.mark.parametrize("kwargs,reason,old_ip,new_ip,new_mac", [
    ({"ip": OTHER_IP}, "superseded_same_mac", IP, OTHER_IP, MAC),
    ({"mac": OTHER_MAC}, "superseded_same_ip", IP, IP, OTHER_MAC),
])
def test_exact_reassignment_and_reuse_boundary(store, kwargs, reason, old_ip, new_ip, new_mac):
    repository, _, _ = store
    old = repository.record(fact())
    new = repository.record(fact(600, **kwargs))
    old_row = repository.connection.execute("SELECT * FROM binding_intervals WHERE binding_id=?", (old.binding_id,)).fetchone()
    assert old_row["valid_until"] == new.valid_from == ts(600)
    assert old_row["end_reason"] == reason
    assert resolve(store, 599, ip=old_ip).client_mac == MAC
    result = resolve(store, 600, ip=new_ip)
    assert result.state == "resolved" and result.client_mac == new_mac
    if old_ip != new_ip:
        assert resolve(store, 600, ip=old_ip).state == "unattributed"


def test_expiry_no_timer_mutation_half_open_boundaries(store):
    repository, _, _ = store
    repository.record(fact(10, lease=20))
    assert resolve(store, 9).state == "unattributed"
    assert resolve(store, 10).state == "resolved"
    assert resolve(store, 29).state == "resolved"
    assert resolve(store, 30).state == "unattributed"
    assert repository.connection.execute("SELECT valid_until FROM binding_intervals").fetchone()[0] == ts(30)
    next_lease = repository.record(fact(30, lease=20))
    assert next_lease.valid_from == ts(30)
    assert repository.connection.execute("SELECT count(*) FROM binding_intervals").fetchone()[0] == 2


@pytest.mark.parametrize("message,reason", [(7, "client_release"), (4, "client_decline")])
def test_valid_client_termination_and_unmatched_ignore(store, message, reason):
    repository, _, _ = store
    assert repository.record(fact(0, message=message)) is None
    original = repository.record(fact(1))
    assert repository.record(fact(10, message=message, ip=OTHER_IP)) is None
    assert repository.record(fact(10, message=message, mac=OTHER_MAC)) is None
    repository.confirm_capture(SITE, SOURCE, ts(20))
    terminated = repository.record(fact(20, message=message))
    assert terminated.binding_id == original.binding_id and terminated.end_reason == reason
    assert terminated.valid_until == ts(20)
    assert resolve(store, 19).state == "resolved"
    assert resolve(store, 20).state == "unattributed"
    stored = repository.connection.execute("SELECT * FROM authority_facts WHERE message_type<> 'ack'").fetchone()
    assert stored["server_ipv4"] is stored["option54_ipv4"] is stored["lease_seconds"] is None
    assert repository.record(fact(21, message=message)) is None


@pytest.mark.parametrize("kwargs", [{"mac": OTHER_MAC}, {"ip": OTHER_IP}])
def test_exact_time_conflict_does_not_overwrite_and_fences_source(store, kwargs):
    repository, _, _ = store
    original = repository.record(fact(1))
    with pytest.raises(NetworkAttributionConflict):
        repository.record(fact(1, **kwargs))
    row = dict(repository.connection.execute("SELECT * FROM binding_intervals").fetchone())
    assert row == asdict(original)
    assert repository.connection.execute("SELECT count(*) FROM authority_facts").fetchone()[0] == 1
    assert resolve(store, 2).state == "unavailable"


def test_duplicate_fact_idempotent(store):
    repository, _, _ = store
    first = fact()
    repository.record(first)
    assert repository.record(replace(first, ingested_at=ts(2))) is None
    assert repository.connection.execute("SELECT count(*) FROM authority_facts").fetchone()[0] == 1


def test_same_pair_same_timestamp_equivalent_ack_is_not_a_primary_conflict(store):
    repository, _, _ = store
    original = repository.record(fact(xid=123))
    repeated = repository.record(fact(xid=124))
    assert repeated.binding_id == original.binding_id
    assert repeated.valid_from == original.valid_from
    assert repeated.valid_until == original.valid_until
    assert resolve(store, 0).state == "resolved"


@pytest.mark.parametrize("message", [4, 7])
def test_same_timestamp_client_termination_uses_exact_current_binding(store, message):
    repository, _, _ = store
    original = repository.record(fact())
    closed = repository.record(fact(message=message))
    assert closed.binding_id == original.binding_id
    assert closed.valid_from == closed.valid_until == ts()
    assert resolve(store, 0).state == "unattributed"


def test_coverage_horizon_and_site_isolation(store):
    repository, _, _ = store
    assert resolve(store, -1).state == "outside_historical_horizon"
    assert resolve(store, 0).state == "unattributed"
    repository.record(fact())
    assert resolve(store, 1, site=OTHER_SITE).state == "unavailable"
    repository.coverage(OTHER_SITE, SOURCE, "usable", ts())
    sensor = replace(sensor_config_from_env({"DEVICE_FINGERPRINT_SENSOR_ENABLED": "true"}), site_id=OTHER_SITE)
    repository.record(fact(0, sensor=sensor, mac=OTHER_MAC))
    assert resolve(store, 1, site=OTHER_SITE).client_mac == OTHER_MAC
    assert resolve(store, 1).client_mac == MAC


def test_outage_recovery_new_ack_and_historical_results(store):
    repository, _, _ = store
    original = repository.record(fact())
    repository.coverage(SITE, SOURCE, "unavailable", ts(600), "raw_capture_unavailable")
    repository.coverage(SITE, SOURCE, "usable", ts(900))
    assert resolve(store, 300).state == "resolved"
    during = resolve(store, 700)
    assert (during.state, during.reason) == ("unavailable", "source_coverage_unavailable")
    after = resolve(store, 1200)
    assert (after.state, after.reason) == ("unavailable", "source_coverage_gap")
    assert repository.connection.execute("SELECT valid_until FROM binding_intervals").fetchone()[0] == original.valid_until
    renewed = repository.record(fact(1500, xid=456))
    assert renewed.binding_id == original.binding_id
    assert resolve(store, 1500).state == "resolved"
    # Future renewal must not erase a historical gap or prior good coverage.
    assert resolve(store, 300).state == "resolved"
    assert resolve(store, 1200).reason == "source_coverage_gap"


def test_absence_is_not_guessed_across_a_recovered_gap(store):
    repository, _, _ = store
    repository.coverage(SITE, SOURCE, "unavailable", ts(10), "raw_capture_unavailable")
    repository.coverage(SITE, SOURCE, "usable", ts(20))
    assert resolve(store, 21).reason == "source_coverage_gap"
    repository.record(fact(22, lease=10))
    assert resolve(store, 22).state == "resolved"
    assert resolve(store, 32).state == "unattributed"


@pytest.mark.parametrize("message", [4, 7])
def test_client_termination_cannot_use_a_binding_unproven_after_a_gap(store, message):
    repository, _, _ = store
    original = repository.record(fact())
    repository.coverage(SITE, SOURCE, "unavailable", ts(10), "raw_capture_unavailable")
    repository.coverage(SITE, SOURCE, "usable", ts(20))
    repository.confirm_capture(SITE, SOURCE, ts(25))
    assert repository.record(fact(25, message=message)) is None
    assert dict(repository.connection.execute("SELECT * FROM binding_intervals").fetchone()) == asdict(original)
    repository.record(fact(26))
    repository.confirm_capture(SITE, SOURCE, ts(27))
    assert repository.record(fact(27, message=message)).valid_until == ts(27)


def test_ambiguity_is_never_selected_and_coverage_has_precedence(store):
    repository, _, _ = store
    binding = repository.record(fact())
    # Explicit corrupted/overlapping candidate fixture, not an alternative writer path.
    second = asdict(binding)
    second.update(binding_id="overlapping-fixture", client_mac=OTHER_MAC)
    repository._insert("binding_intervals", second)
    repository.connection.execute("INSERT INTO binding_fact_links VALUES(?,?)", (second["binding_id"], binding.start_fact_id))
    assert resolve(store, 1).state == "ambiguous"
    repository.coverage(SITE, SOURCE, "unavailable", ts(2), "raw_capture_unavailable")
    assert resolve(store, 3).state == "unavailable"


def test_open_coverage_does_not_predict_past_last_durable_capture_confirmation(store):
    repository, reader, config = store
    repository.record(fact())
    repository.confirm_capture(SITE, SOURCE, ts(10))
    assert reader.resolve_ipv4(SITE, IP, ts(10)).state == "resolved"
    assert reader.resolve_ipv4(SITE, IP, ts(11)).state == "unavailable"
    repository.close()  # Simulated unclean process exit: no shutdown coverage event.
    repository.initialize()
    repository.capture_started(SITE, SOURCE, ts(20))
    assert store[1].resolve_ipv4(SITE, IP, ts(10)).state == "resolved"
    assert resolve(store, 21).reason == "source_coverage_gap"
    repository.record(fact(22))
    assert resolve(store, 22).state == "resolved"


@pytest.mark.parametrize("site,ip,event", [("bad", IP, ts()), (SITE, "::1", ts()), (SITE, "192.168.008.20", ts()), (SITE, IP, "today"), (None, IP, ts())])
def test_invalid_inputs(store, site, ip, event):
    assert store[1].resolve_ipv4(site, ip, event).state == "invalid"


def test_schema_pragmas_and_durable_reopen(store):
    repository, _, _ = store
    repository.record(fact())
    for pragma, expected in (("user_version", 1), ("foreign_keys", 1), ("journal_mode", "wal"), ("synchronous", 2), ("busy_timeout", 500)):
        assert repository.connection.execute("PRAGMA " + pragma).fetchone()[0] == expected
    repository.close()
    repository.initialize()
    assert resolve(store, 1).state == "resolved"


def test_foreign_schema_rejected_without_mutating_database(tmp_path):
    path = tmp_path / "foreign.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE old_contract(value)")
        connection.execute("PRAGMA user_version=7")
    before = path.read_bytes()
    config = NetworkAttributionConfig(True, str(path))
    with pytest.raises(NetworkAttributionStorageUnavailable):
        NetworkAttributionRepository(config).initialize()
    assert path.read_bytes() == before
    assert NetworkAttributionReadService(config).resolve_ipv4(SITE, IP, ts()).state == "unavailable"


def test_missing_and_capacity_exhausted_store_fail_closed(tmp_path):
    config = NetworkAttributionConfig(True, str(tmp_path / "absent-parent" / "test.sqlite3"))
    with pytest.raises(NetworkAttributionStorageUnavailable):
        NetworkAttributionRepository(config).initialize()
    assert NetworkAttributionReadService(config).resolve_ipv4(SITE, IP, ts()).state == "unavailable"
    tiny = NetworkAttributionConfig(True, str(tmp_path / "tiny.sqlite3"), 1)
    with pytest.raises(NetworkAttributionStorageUnavailable):
        NetworkAttributionRepository(tiny).initialize()


def test_single_writer_lock(store):
    with pytest.raises(NetworkAttributionStorageUnavailable):
        NetworkAttributionRepository(store[2]).initialize()
    assert resolve(store, 0).state == "unattributed"


def test_retention_keeps_referenced_facts_and_explicit_horizon(store):
    repository, reader, _ = store
    repository.record(fact(0, lease=20))
    repository.record(fact(21, lease=20))
    repository.coverage(SITE, SOURCE, "unavailable", ts(60), "sensor_shutdown")
    repository.retain(at=ts(30 * 86400 + 45))
    assert repository.connection.execute("SELECT count(*) FROM binding_intervals").fetchone()[0] == 0
    assert repository.connection.execute("SELECT count(*) FROM authority_facts").fetchone()[0] == 0
    assert reader.resolve_ipv4(SITE, IP, ts(40)).state == "outside_historical_horizon"


def test_retention_is_one_bounded_batch_and_keeps_required_start_fact(store):
    repository, _, _ = store
    for seconds in range(120):
        repository.record(fact(seconds, lease=1))
    repository.retain(at=ts(30 * 86400 + 121))
    assert repository.connection.execute("SELECT count(*) FROM binding_intervals").fetchone()[0] == 20
    assert repository.connection.execute("SELECT count(*) FROM authority_facts").fetchone()[0] == 20
    assert not repository.connection.execute("PRAGMA foreign_key_check").fetchall()


def test_long_lived_renewal_retains_start_and_pre_horizon_confirmation(store):
    repository, reader, _ = store
    original = repository.record(fact(0, lease=86400))
    for day in range(1, 33):
        # Renew before expiry to keep one interval, including a 30-day retention run.
        repository.record(fact(day * 86000, lease=86400))
    cutoff = 3 * 86000
    repository.retain(at=ts(cutoff + 30 * 86400))
    assert repository.connection.execute("SELECT count(*) FROM binding_intervals").fetchone()[0] == 1
    assert repository.connection.execute("SELECT fact_id FROM authority_facts WHERE fact_id=?", (original.start_fact_id,)).fetchone()
    repository.confirm_capture(SITE, SOURCE, ts(32 * 86000))
    assert reader.resolve_ipv4(SITE, IP, ts(cutoff)).state == "resolved"


def test_default_off_config_does_not_create_or_read_store(tmp_path):
    config = network_attribution_config_from_env({"NETWORK_ATTRIBUTION_ENABLED": "false", "NETWORK_ATTRIBUTION_DB_PATH": "invalid"})
    assert config == NetworkAttributionConfig()
    assert NetworkAttributionReadService(config).resolve_ipv4(SITE, IP, ts()).reason == "attribution_disabled"
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("env", [{"NETWORK_ATTRIBUTION_ENABLED": "yes"},
    {"NETWORK_ATTRIBUTION_ENABLED": "true", "NETWORK_ATTRIBUTION_DB_PATH": "relative"},
    {"NETWORK_ATTRIBUTION_ENABLED": "true", "NETWORK_ATTRIBUTION_MAX_DB_BYTES": "2147483649"},
    {"NETWORK_ATTRIBUTION_ENABLED": "true", "NETWORK_ATTRIBUTION_MAX_DB_BYTES": "0"}])
def test_config_closed_limits(env):
    with pytest.raises(NetworkAttributionValidationError):
        network_attribution_config_from_env(env)
