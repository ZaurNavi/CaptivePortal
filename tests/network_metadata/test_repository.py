import os
import sqlite3
from dataclasses import replace
import pytest
from app.network_metadata.models import NetworkMetadataStorageCorrupt, NetworkMetadataValidationError, NetworkMetadataWriterUnavailable
from app.network_metadata.repository import NetworkMetadataRepository, WriterLock
from app.network_metadata.canonical import ni01_canonical_json
from app.network_metadata.schema import TABLE_DDL, INDEX_DDL
from app.network_metadata.retention import RetentionPolicy
from . import store, outcome, seed_blocked, configuration, record


@pytest.mark.parametrize("category", ["invalid_utf8", "invalid_json", "duplicate_json_member", "non_object_json",
    "schema_invalid", "unexpected_family", "pre_binding_event", "outside_intended_scope",
    "unsupported_address_family_for_scope", "record_too_large", "same_raw_non_normalized", "expired_non_normalized"])
def test_all_complete_replay_outcomes_obey_source_identity_precedence(tmp_path, category):
    from . import source_event
    from app.network_metadata.models import RecordOutcome
    from app.network_metadata.source import BinarySourceReader
    with store(tmp_path) as state:
        first = outcome(state.config.capture_scope_binding, generation=state.generation.source_generation_id)
        state.repo.ingest_batch([first], state.run, state.health, state.anchor)
        before = tuple(state.repo.connection.execute("SELECT * FROM network_metadata_observations").fetchone())
        if category in {"same_raw_non_normalized", "expired_non_normalized"}:
            incoming = replace(first, normalized=None, category="schema_invalid")
            if category == "expired_non_normalized":
                state.repo.connection.execute("UPDATE network_metadata_source_records SET digest_state='expired',source_record_sha256=NULL,semantic_payload_sha256=NULL")
            expected = "replay_identity_evidence_expired" if category == "expired_non_normalized" else "normalizer_determinism_conflict"
        else:
            event = source_event()
            if category == "schema_invalid":
                event["dns"]["version"] = 2
            elif category == "unexpected_family":
                event["event_type"] = "other"
            elif category == "pre_binding_event":
                event["timestamp"] = "2025-01-01T00:00:00Z"
            elif category == "outside_intended_scope":
                event["src_ip"] = "203.0.113.7"
            elif category == "unsupported_address_family_for_scope":
                event["src_ip"] = "2001:db8::7"
            data = {"invalid_utf8": b"\xff", "invalid_json": b"{", "duplicate_json_member": b'{"x":1,"x":2}',
                    "non_object_json": b"[]", "record_too_large": b"x" * 5000}.get(category, record(event))
            (tmp_path / "source.jsonl").write_bytes(data + b"\n")
            if category == "record_too_large":
                complete = BinarySourceReader(state.fd, max_record_bytes=4096).read_batch(1, 1048576)[0]
                incoming = RecordOutcome(complete.start, complete.end, complete.byte_length, category,
                    source_record_sha256=complete.source_record_sha256)
            else:
                incoming = outcome(state.config.capture_scope_binding, data, generation=state.generation.source_generation_id)
                assert incoming.category == category
            expected = "source_record_identity_conflict"
        state.repo.connection.execute("UPDATE network_metadata_checkpoint SET committed_byte_offset=0,continuity_anchor_start_offset=0,continuity_anchor_length=0,continuity_anchor_sha256=NULL")
        state.repo.connection.execute("UPDATE network_metadata_source_generations SET committed_byte_offset=0")
        result = state.repo.ingest_batch([incoming], state.run, state.health, state.anchor)
        assert result["blocked"] == expected
        generation, checkpoint = state.repo.load_active()
        assert generation.processing_state == "blocked"
        assert checkpoint.committed_byte_offset == generation.blocked_record_start_byte_offset == 0
        assert tuple(state.repo.connection.execute("SELECT * FROM network_metadata_observations").fetchone()) == before
        assert [tuple(row) for row in state.repo.connection.execute("SELECT fault_category,count FROM network_metadata_ingest_fault_aggregates")] == [(expected, 1)]


@pytest.mark.parametrize("raw_digest", [None, "f" * 63, "F" * 64, "z" * 64])
def test_complete_ingest_requires_valid_raw_digest(tmp_path, raw_digest):
    with store(tmp_path) as state:
        item = outcome(state.config.capture_scope_binding, generation=state.generation.source_generation_id)
        with pytest.raises(NetworkMetadataValidationError):
            state.repo.ingest_batch([replace(item, source_record_sha256=raw_digest)], state.run, state.health, state.anchor)
        assert state.repo.load_active()[1].committed_byte_offset == 0


def test_binding_first_persist_and_identical_noop(tmp_path):
    cfg = configuration(tmp_path)
    repo = NetworkMetadataRepository(cfg)
    try:
        repo.initialize()
        assert repo.connection.execute("SELECT count(*) FROM network_metadata_capture_scope_bindings").fetchone()[0] == 0
        repo.persist_binding(cfg.capture_scope_binding)
        before = tuple(repo.connection.execute("SELECT * FROM network_metadata_capture_scope_bindings").fetchone())
        assert before
        assert repo.connection.execute("SELECT ipv4_cidrs_json FROM network_metadata_capture_scope_bindings").fetchone()[0] == ni01_canonical_json(list(cfg.capture_scope_binding.ipv4_cidrs)).decode("utf-8")
        changes = repo.connection.total_changes
        repo.persist_binding(cfg.capture_scope_binding)
        assert repo.connection.total_changes == changes
        assert [tuple(row) for row in repo.connection.execute("SELECT * FROM network_metadata_capture_scope_bindings")] == [before]
    finally:
        repo.close()


@pytest.mark.parametrize("column,value", [
    ("site_id", "abcdef0123456789abcdef01"),
    ("capture_source_id", "other-sensor"),
    ("network_scope_id", "other-scope"),
    ("ipv4_cidrs_json", '["10.74.0.0/24"]'),
    ("valid_from_utc", "2026-01-02T00:00:00.000000Z"),
])
def test_binding_same_digest_mismatch_rejected_without_repair(tmp_path, column, value):
    with store(tmp_path) as state:
        binding = state.config.capture_scope_binding
        state.repo.connection.execute(
            f"UPDATE network_metadata_capture_scope_bindings SET {column}=? WHERE binding_digest=?",
            (value, binding.binding_digest))
        before = tuple(state.repo.connection.execute("SELECT * FROM network_metadata_capture_scope_bindings").fetchone())
        changes = state.repo.connection.total_changes
        with pytest.raises(NetworkMetadataStorageCorrupt):
            state.repo.persist_binding(binding)
        assert state.repo.connection.total_changes == changes
        assert tuple(state.repo.connection.execute("SELECT * FROM network_metadata_capture_scope_bindings").fetchone()) == before
        assert not state.repo.connection.in_transaction


def test_exact_schema_pragmas_spine_and_provenance(tmp_path):
    with store(tmp_path) as state:
        conn = state.repo.connection
        assert {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")} == set(TABLE_DDL)
        for pragma, expected in (("user_version", 1), ("foreign_keys", 1), ("synchronous", 2), ("busy_timeout", 500),
                                  ("journal_mode", "wal"), ("wal_autocheckpoint", 1000), ("journal_size_limit", 67108864)):
            assert conn.execute("PRAGMA " + pragma).fetchone()[0] == expected
        assert conn.execute("PRAGMA max_page_count").fetchone()[0] <= state.config.max_db_bytes // conn.execute("PRAGMA page_size").fetchone()[0]
        item = outcome(state.config.capture_scope_binding, generation=state.generation.source_generation_id)
        state.repo.ingest_batch([item], state.run, state.health, state.anchor)
        row = conn.execute("SELECT flow_id_decimal,transaction_id_decimal,source_health_ref,ingest_run_id FROM network_metadata_observations").fetchone()
        assert row[:2] == ("18446744073709551615", "18446744073709551615")
        assert row[2] and row[3] == state.run
        assert state.repo.load_active()[1].committed_byte_offset == len(record()) + 1
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_second_posix_writer_rejected(tmp_path):
    path = str(tmp_path / "db.writer.lock")
    with WriterLock(path):
        with pytest.raises(NetworkMetadataWriterUnavailable):
            with WriterLock(path):
                pass
        assert os.stat(path).st_mode & 0o777 == 0o640


@pytest.mark.parametrize("damage", ["PRAGMA user_version=2", "CREATE TABLE extra(x)", "DROP INDEX idx_nm_observations_site_event",
    "DELETE FROM network_metadata_schema", "UPDATE network_metadata_schema SET created_at_utc='invalid'"])
def test_schema_drift_fails_without_recreate(tmp_path, damage):
    with store(tmp_path) as state:
        state.repo.connection.execute(damage)
        state.repo.close()
        with pytest.raises(NetworkMetadataStorageCorrupt):
            state.repo.initialize()


def test_duplicate_noop_preserves_all_fields(tmp_path):
    with store(tmp_path) as state:
        item = outcome(state.config.capture_scope_binding, generation=state.generation.source_generation_id)
        state.repo.ingest_batch([item], state.run, state.health, state.anchor)
        before = tuple(state.repo.connection.execute("SELECT * FROM network_metadata_observations").fetchone())
        assert state.repo.identity_outcome(state.generation.source_generation_id, item) == "duplicate_noop"
        with state.repo.transaction():
            state.repo.connection.execute("UPDATE network_metadata_checkpoint SET committed_byte_offset=0,continuity_anchor_start_offset=0,continuity_anchor_length=0,continuity_anchor_sha256=NULL")
            state.repo.connection.execute("UPDATE network_metadata_source_generations SET committed_byte_offset=0")
        state.clock.advance(seconds=5)
        result = state.repo.ingest_batch([item], state.run, state.health, state.anchor)
        assert result["duplicates"] == 1 and result["committed"] == 0
        assert tuple(state.repo.connection.execute("SELECT * FROM network_metadata_observations").fetchone()) == before


@pytest.mark.parametrize("category", ["source_record_identity_conflict", "normalizer_determinism_conflict", "replay_identity_evidence_expired"])
def test_conflicts_are_durable_and_atomic(tmp_path, category):
    with store(tmp_path) as state:
        generation, checkpoint = seed_blocked(state, category)
        assert generation.processing_state == "blocked" and generation.blocked_reason_code == category
        assert generation.blocked_record_start_byte_offset == generation.committed_byte_offset == checkpoint.committed_byte_offset == 0
        assert generation.closed_at_utc is None
        health = state.repo.latest_health()
        assert health["metadata_ingest_health"] == "unavailable" and category in health["reason_codes_json"]
        state.repo.recover()
        assert state.repo.load_active()[0].processing_state == "blocked"
        with pytest.raises(NetworkMetadataStorageCorrupt):
            state.repo.transition_generation(binding=state.config.capture_scope_binding, boot_id=generation.host_boot_id,
                physical=(generation.st_dev, generation.st_ino), close_reason="source_rotated_live")


@pytest.mark.parametrize("update", ["blocked_reason_code='source_record_identity_conflict'",
    "processing_state='blocked'", "processing_state='blocked',blocked_reason_code='source_record_identity_conflict',blocked_at_utc='2026-10-07T12:00:00.000000Z'",
    "processing_state='blocked',blocked_reason_code='source_record_identity_conflict',blocked_record_start_byte_offset=0",
    "processing_state='blocked',blocked_reason_code='source_record_identity_conflict',blocked_at_utc='2026-10-07T12:00:00.000000Z',blocked_record_start_byte_offset=1"])
def test_generation_schema_rejects_invalid_block_state(tmp_path, update):
    with store(tmp_path) as state:
        with pytest.raises(sqlite3.IntegrityError):
            state.repo.connection.execute("UPDATE network_metadata_source_generations SET " + update)


def test_blocked_cannot_be_closed_in_schema_or_model(tmp_path):
    with store(tmp_path) as state:
        generation, _ = seed_blocked(state)
        with pytest.raises(sqlite3.IntegrityError):
            state.repo.connection.execute("UPDATE network_metadata_source_generations SET closed_at_utc='2026-10-07T12:00:00.000000Z',end_offset=0,close_reason='source_rotated_live'")
        with pytest.raises(NetworkMetadataValidationError):
            replace(generation, blocked_record_start_byte_offset=1)
        with pytest.raises(NetworkMetadataValidationError):
            replace(generation, processing_state="runnable")


@pytest.mark.parametrize("damage", ["UPDATE network_metadata_source_generations SET blocked_record_start_byte_offset=1",
    "UPDATE network_metadata_checkpoint SET committed_byte_offset=1,continuity_anchor_length=1,continuity_anchor_sha256='" + "0" * 64 + "'",
    "UPDATE network_metadata_checkpoint SET source_generation_id='aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa'",
    "DELETE FROM network_metadata_checkpoint"])
def test_blocked_startup_consistency_corruption(tmp_path, damage):
    with store(tmp_path) as state:
        seed_blocked(state)
        state.repo.connection.execute("PRAGMA ignore_check_constraints=ON")
        state.repo.connection.execute("PRAGMA foreign_keys=OFF")
        state.repo.connection.execute(damage)
        with pytest.raises(NetworkMetadataStorageCorrupt):
            state.repo.load_active()


def test_batch_order_rejected(tmp_path):
    with store(tmp_path) as state:
        item = outcome(state.config.capture_scope_binding, start=1, generation=state.generation.source_generation_id)
        with pytest.raises(NetworkMetadataValidationError):
            state.repo.ingest_batch([item], state.run, state.health, state.anchor)


def test_fault_aggregation_processing_clock_bucket(tmp_path):
    from app.network_metadata.models import RecordOutcome
    from app.network_metadata.canonical import sha256
    with store(tmp_path, source=b"x\nx\n") as state:
        state.repo.ingest_batch([RecordOutcome(0, 2, 1, "invalid_json", source_record_sha256=sha256(b"x")),
                               RecordOutcome(2, 4, 1, "invalid_json", source_record_sha256=sha256(b"x"))],
                               state.run, state.health, state.anchor)
        fault = state.repo.connection.execute("SELECT * FROM network_metadata_ingest_fault_aggregates").fetchone()
        assert fault["count"] == 2 and fault["first_relevant_offset"] == 0 and fault["last_relevant_offset"] == 2
        assert fault["aggregation_epoch_start_utc"] == "2026-10-07T12:00:00.000000Z"
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_records").fetchone()[0] == 0


def test_existing_empty_newer_schema_not_reinitialized(tmp_path):
    cfg = configuration(tmp_path)
    with sqlite3.connect(cfg.db_path) as connection:
        connection.execute("PRAGMA user_version=2")
    repo = NetworkMetadataRepository(cfg)
    try:
        with pytest.raises(NetworkMetadataStorageCorrupt):
            repo.initialize()
        assert repo.connection.execute("PRAGMA user_version").fetchone()[0] == 2
    finally:
        repo.close()


def test_headroom_halts_without_checkpoint_change(tmp_path, monkeypatch):
    from app.network_metadata.models import NetworkMetadataStorageLimit
    with store(tmp_path) as state:
        monkeypatch.setattr(state.repo, "footprint", lambda: {"combined": state.config.max_db_bytes, "wal": 0, "main": 0})
        with pytest.raises(NetworkMetadataStorageLimit):
            state.repo.ingest_batch([outcome(state.config.capture_scope_binding, generation=state.generation.source_generation_id)],
                                   state.run, state.health, state.anchor)
        assert state.repo.load_active()[1].committed_byte_offset == 0


@pytest.mark.parametrize("timestamp", ["2026-02-30T12:00:00.000000Z", "2026-01-01T25:00:00.000000Z", "0000-01-01T00:00:00.000000Z"])
def test_schema_rejects_noncanonical_block_timestamp(tmp_path, timestamp):
    with store(tmp_path) as state:
        with pytest.raises(sqlite3.IntegrityError):
            state.repo.connection.execute("UPDATE network_metadata_source_generations SET processing_state='blocked',blocked_reason_code='source_record_identity_conflict',blocked_at_utc=?,blocked_record_start_byte_offset=0", (timestamp,))


def test_bounded_wal_maintenance_with_held_reader(tmp_path, monkeypatch):
    with store(tmp_path) as state:
        reader = sqlite3.connect(state.config.db_path, isolation_level=None)
        try:
            reader.execute("BEGIN")
            reader.execute("SELECT count(*) FROM network_metadata_source_generations").fetchone()
            item = outcome(state.config.capture_scope_binding, generation=state.generation.source_generation_id)
            state.repo.ingest_batch([item], state.run, state.health, state.anchor)
            actual = state.repo.footprint
            def large_wal():
                values = actual()
                values["wal"] = 67108865
                values["combined"] = values["main"] + values["wal"] + values["shm"] + values["journal"]
                return values
            monkeypatch.setattr(state.repo, "footprint", large_wal)
            commands = []
            state.repo.connection.set_trace_callback(commands.append)
            state.repo.wal_maintenance()
            assert commands.count("PRAGMA wal_checkpoint(PASSIVE)") == 1
            assert commands.count("PRAGMA wal_checkpoint(TRUNCATE)") <= 1
            assert reader.execute("SELECT count(*) FROM network_metadata_observations").fetchone()[0] == 0
            assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_observations").fetchone()[0] == 1
        finally:
            reader.close()


def test_stat_failure_not_zero_footprint(tmp_path, monkeypatch):
    from app.network_metadata.models import NetworkMetadataStorageUnavailable
    with store(tmp_path) as state:
        monkeypatch.setattr(os, "stat", lambda *_: (_ for _ in ()).throw(PermissionError()))
        with pytest.raises(NetworkMetadataStorageUnavailable):
            state.repo.footprint()
