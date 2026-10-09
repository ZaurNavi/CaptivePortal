from dataclasses import asdict

import pytest

from app.network_metadata.projection_source import NetworkMetadataProjectionSourceReadService
from app.network_metadata.models import NetworkMetadataStorageUnavailable
from app.network_metadata.retention import RetentionPolicy
from tests.network_metadata import store, outcome, record, source_event


def seed(state, count=1):
    data = record()
    items = [outcome(state.config.capture_scope_binding, data, start=index * (len(data) + 1),
                     generation=state.generation.source_generation_id) for index in range(count)]
    state.repo.ingest_batch(items, state.run, state.health, state.anchor)
    return NetworkMetadataProjectionSourceReadService(state.config.db_path)


def test_exact_source_record_batch_offset_zero_and_retention(tmp_path):
    with store(tmp_path, source=(record() + b"\n") * 3) as state:
        reader = seed(state, 3)
        generation = reader.list_source_generations()[0]
        first = reader.read_projection_batch(generation.source_generation_id, None, 1)[0]
        assert first.record_start_byte_offset == 0
        assert first.event_at == "2026-10-07T12:00:00.123456Z"
        assert first.src_ip == "10.73.0.7" and first.dst_ip == "2001:db8::93"
        assert first.capture_scope_ipv4_cidrs == ("10.73.0.0/24",)
        assert reader.get_projection_source_record(first.observation_id) == first
        assert reader.get_source_progress(generation.source_generation_id).committed_byte_offset > 0
        rest = reader.read_projection_batch(generation.source_generation_id, 0, 256)
        assert len(rest) == 2 and all(item.record_start_byte_offset > 0 for item in rest)
        assert not any(key in asdict(first) for key in ("dns", "sni", "raw_payload"))
        state.clock.advance(days=15)
        RetentionPolicy(state.repo).run()
        expired = reader.get_projection_source_record(first.observation_id)
        assert expired.sensitive_endpoint_presence_state == "expired"
        assert expired.src_ip is expired.dst_ip is expired.src_port is expired.dst_port is None


@pytest.mark.parametrize("damage", [
    "PRAGMA user_version=2", "CREATE TABLE extra(value)",
    "DELETE FROM network_metadata_sensitive_endpoints",
    "UPDATE network_metadata_capture_scope_bindings SET ipv4_cidrs_json='[\"10.74.0.0/24\"]'",
    "UPDATE network_metadata_observations SET source_event_identity='bad'",
    "UPDATE network_metadata_observations SET event_at='2026-10-07T12:00:00.123Z'",
    "UPDATE network_metadata_observations SET site_id='ffffffffffffffffffffffff'",
    "UPDATE network_metadata_source_generations SET logical_source_id='other-source'",
    "DELETE FROM network_metadata_capture_scope_bindings",
    "DELETE FROM network_metadata_source_health",
    "DELETE FROM network_metadata_ingest_runs",
    "UPDATE network_metadata_source_health SET source_generation_id=NULL",
    "UPDATE network_metadata_source_health SET capture_source_id='different-source'",
    "UPDATE network_metadata_ingest_runs SET normalizer_version='different-version'",
])
def test_untrusted_source_fails_without_mutation(tmp_path, damage):
    with store(tmp_path) as state:
        reader = seed(state)
        # Damage only this disposable source; point reads must detect broken FKs.
        state.repo.connection.execute("PRAGMA foreign_keys=OFF")
        state.repo.connection.execute(damage)
        before = state.repo.connection.total_changes
        with pytest.raises(NetworkMetadataStorageUnavailable):
            reader.read_projection_batch(state.generation.source_generation_id, None, 256)
        assert state.repo.connection.total_changes == before


@pytest.mark.parametrize("method", ["list_source_generations", "read_projection_batch",
    "get_projection_source_record", "get_source_progress"])
def test_source_connections_read_only_and_no_raw_payload_tables(tmp_path, monkeypatch, method, record_property):
    import sqlite3
    with store(tmp_path) as state:
        reader = seed(state)
        observation = reader.read_projection_batch(state.generation.source_generation_id, None, 1)[0]
        calls, statements, original = [], [], sqlite3.connect
        def connect(*args, **kwargs):
            calls.append(args[0])
            connection = original(*args, **kwargs)
            connection.set_trace_callback(statements.append)
            return connection
        monkeypatch.setattr(sqlite3, "connect", connect)
        arguments = {"list_source_generations": (),
            "read_projection_batch": (state.generation.source_generation_id, None, 1),
            "get_projection_source_record": (observation.observation_id,),
            "get_source_progress": (state.generation.source_generation_id,)}
        getattr(reader, method)(*arguments[method])
        assert all(value == ":memory:" or value.endswith("?mode=ro") for value in calls)
        assert "PRAGMA query_only=ON" in statements
        assert "PRAGMA foreign_keys=ON" in statements and "PRAGMA busy_timeout=500" in statements
        assert "BEGIN" in statements
        for pragma in ("foreign_key_check", "quick_check", "integrity_check"):
            count = sum(value.lower().startswith("pragma " + pragma) for value in statements)
            record_property(pragma + "_count", count)
            assert count == 0
        selects = [value.lower() for value in statements if value.lower().startswith("select")]
        assert not any("from network_metadata_dns" in value or "from network_metadata_source_records" in value for value in selects)


def test_not_observed_does_not_reconstruct_endpoints(tmp_path):
    with store(tmp_path) as state:
        reader = seed(state)
        # Disposable schema-valid retained-state fixture, not a normalizer change.
        state.repo.connection.execute("UPDATE network_metadata_observations SET sensitive_endpoint_presence_state='not_observed'")
        state.repo.connection.execute("DELETE FROM network_metadata_sensitive_endpoints")
        result = reader.read_projection_batch(state.generation.source_generation_id, None, 1)[0]
        assert result.sensitive_endpoint_presence_state == "not_observed"
        assert result.src_ip is result.dst_ip is None


def test_source_generation_order_is_opened_time_then_identity(tmp_path):
    from tests.network_metadata import BOOT
    with store(tmp_path) as state:
        reader = seed(state)
        state.repo.transition_generation(binding=state.config.capture_scope_binding, boot_id=BOOT,
            physical=(1, 2), close_reason="rotation")
        state.clock.advance(seconds=1)
        state.repo.transition_generation(binding=state.config.capture_scope_binding, boot_id=BOOT,
            physical=(1, 3), close_reason="rotation")
        generations = reader.list_source_generations()
        keys = [(item.opened_at_utc, item.source_generation_id) for item in generations]
        assert len(keys) == 3 and keys == sorted(keys)
