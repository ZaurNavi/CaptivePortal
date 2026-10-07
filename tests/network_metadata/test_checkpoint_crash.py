import pytest
from datetime import timedelta
from app.network_metadata.models import NetworkMetadataStorageUnavailable
from . import store, outcome, seed_blocked


@pytest.mark.parametrize("category", ["source_record_identity_conflict", "normalizer_determinism_conflict", "replay_identity_evidence_expired"])
@pytest.mark.parametrize("has_prefix", [False, True])
def test_final_conflict_health_owns_new_prefix_and_stops_evaluation(tmp_path, monkeypatch, category, has_prefix):
    from . import record, source_event
    from app.network_metadata.validation import ni_format_utc
    from app.network_metadata.retention import RetentionPolicy
    data = record()
    with store(tmp_path, source=(data + b"\n") * 2) as state:
        first = outcome(state.config.capture_scope_binding, data, generation=state.generation.source_generation_id)
        second = outcome(state.config.capture_scope_binding, data, start=first.end, generation=state.generation.source_generation_id)
        ignored_data = record(source_event(timestamp=ni_format_utc(state.clock() + timedelta(days=20))))
        ignored = outcome(state.config.capture_scope_binding, ignored_data, start=second.end,
            generation=state.generation.source_generation_id)
        (tmp_path / "source.jsonl").write_bytes((data + b"\n") * 2 + ignored_data + b"\n")
        state.repo.ingest_batch([first, second], state.run, state.health, state.anchor)
        original_ref = state.repo.latest_health()["health_id"]
        with state.repo.transaction():
            if has_prefix:
                state.repo.connection.execute("DELETE FROM network_metadata_observations WHERE observation_id=?", (first.normalized.observation_id,))
            if category == "source_record_identity_conflict":
                state.repo.connection.execute("UPDATE network_metadata_source_records SET source_record_sha256=?", ("f" * 64,))
            elif category == "normalizer_determinism_conflict":
                state.repo.connection.execute("UPDATE network_metadata_source_records SET semantic_payload_sha256=?", ("f" * 64,))
            else:
                state.repo.connection.execute("UPDATE network_metadata_source_records SET digest_state='expired',source_record_sha256=NULL,semantic_payload_sha256=NULL")
            state.repo.connection.execute("UPDATE network_metadata_checkpoint SET committed_byte_offset=0,continuity_anchor_start_offset=0,continuity_anchor_length=0,continuity_anchor_sha256=NULL")
            state.repo.connection.execute("UPDATE network_metadata_source_generations SET committed_byte_offset=0")
        # Due touched-identity retention must not erase the pre-decided disposition.
        state.clock.advance(days=15)
        expected_offsets = [first.start, second.start] if has_prefix else [first.start]
        identities = []
        identity = state.repo.identity_outcome
        def classify(generation_id, item):
            assert item.start != ignored.start
            identities.append(item.start)
            return identity(generation_id, item)
        monkeypatch.setattr(state.repo, "identity_outcome", classify)
        expire = RetentionPolicy.expire_touched_identity
        def retain(policy, generation_id, offset, now):
            assert identities == expected_offsets
            return expire(policy, generation_id, offset, now)
        monkeypatch.setattr(RetentionPolicy, "expire_touched_identity", retain)
        result = state.repo.ingest_batch([first, second, ignored], state.run, state.health, state.anchor)
        generation, checkpoint = state.repo.load_active()
        assert result == dict(committed=int(has_prefix), duplicates=0, blocked=category)
        assert identities == expected_offsets
        assert generation.processing_state == "blocked" and generation.blocked_reason_code == category
        final_offset = first.end if has_prefix else first.start
        assert checkpoint.committed_byte_offset == generation.committed_byte_offset == generation.blocked_record_start_byte_offset == final_offset
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_observations").fetchone()[0] == 2
        latest = state.repo.latest_health()
        assert latest["health_id"] != original_ref
        assert latest["metadata_output_health"] == latest["metadata_ingest_health"] == "unavailable"
        assert latest["reason_codes_json"] == '["' + category + '"]'
        assert latest["committed_byte_offset"] == final_offset
        assert latest["last_output_event_at"] == latest["last_ingested_event_at"] == first.output_event_at
        assert tuple(state.repo.connection.execute("SELECT fault_category,count FROM network_metadata_ingest_fault_aggregates").fetchone()) == (category, 1)
        assert state.repo.connection.execute("SELECT observation_id FROM network_metadata_observations WHERE observation_id=?",
            (ignored.normalized.observation_id,)).fetchone() is None
        prefix_ref = state.repo.connection.execute("SELECT source_health_ref FROM network_metadata_observations WHERE observation_id=?",
            (first.normalized.observation_id,)).fetchone()[0]
        assert prefix_ref == (latest["health_id"] if has_prefix else original_ref)


@pytest.mark.parametrize("point", ["before_observation_insert", "after_observation_insert_before_commit",
    "before_checkpoint_update", "after_checkpoint_update_before_commit", "after_commit"])
def test_all_five_crash_boundaries(tmp_path, point):
    with store(tmp_path) as state:
        item = outcome(state.config.capture_scope_binding, generation=state.generation.source_generation_id)
        def crash(label):
            if label == point:
                raise RuntimeError("injected crash")
        state.repo._crash_point = crash
        with pytest.raises(RuntimeError):
            state.repo.ingest_batch([item], state.run, state.health, state.anchor)
        state.repo.recover()
        durable = point == "after_commit"
        assert state.repo.load_active()[1].committed_byte_offset == (item.end if durable else 0)
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_observations").fetchone()[0] == int(durable)
        if not durable:
            state.repo._crash_point = lambda _: None
            state.repo.ingest_batch([item], state.run, state.health, state.anchor)
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_observations").fetchone()[0] == 1


@pytest.mark.parametrize("point", ["before_observation_insert", "after_observation_insert_before_commit",
    "before_checkpoint_update", "after_checkpoint_update_before_commit", "after_commit"])
def test_final_partial_health_rolls_back_or_commits_with_entire_batch(tmp_path, point):
    from . import record
    with store(tmp_path, source=record() + b"\n{\n") as state:
        valid = outcome(state.config.capture_scope_binding, generation=state.generation.source_generation_id)
        fault = outcome(state.config.capture_scope_binding, b"{", start=valid.end,
            generation=state.generation.source_generation_id)
        before = state.repo.load_active()
        old_snapshot = state.health.last_snapshot
        count = state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_health").fetchone()[0]
        def crash(label):
            # Even the earliest observation hook sees the FINAL partial snapshot
            # already inserted in the still-uncommitted transaction.
            if label == "before_observation_insert":
                assert state.repo.connection.in_transaction
                assert state.repo.latest_health()["metadata_ingest_health"] == "partial"
                assert state.repo.latest_health()["committed_byte_offset"] == fault.end
                assert state.health.last_snapshot == old_snapshot
            if label == point:
                raise RuntimeError("controlled batch crash")
        state.repo._crash_point = crash
        with pytest.raises(RuntimeError):
            state.repo.ingest_batch([valid, fault], state.run, state.health, state.anchor)
        state.repo.recover()
        durable = point == "after_commit"
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_health").fetchone()[0] == count + int(durable)
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_observations").fetchone()[0] == int(durable)
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_records").fetchone()[0] == int(durable)
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_ingest_fault_aggregates").fetchone()[0] == int(durable)
        assert state.repo.load_active()[1].committed_byte_offset == (fault.end if durable else 0)
        if not durable:
            assert state.repo.load_active() == before
            assert state.health.last_snapshot == old_snapshot
            assert state.health.local_reasons == set()
            assert state.health.last_output is state.health.last_ingested is None
            state.repo._crash_point = lambda _: None
            state.repo.ingest_batch([valid, fault], state.run, state.health, state.anchor)
        else:
            assert state.health.last_snapshot.health_id == state.repo.latest_health()["health_id"]
        observation = state.repo.connection.execute("SELECT source_health_ref FROM network_metadata_observations").fetchone()
        assert observation[0] == state.repo.latest_health()["health_id"] != old_snapshot.health_id
        assert state.repo.latest_health()["metadata_ingest_health"] == "partial"
        assert state.repo.latest_health()["committed_byte_offset"] == fault.end
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_health").fetchone()[0] == count + 1
        assert state.repo.connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_block_establishment_rollback_has_no_successful_claim(tmp_path):
    with store(tmp_path) as state:
        item = outcome(state.config.capture_scope_binding, generation=state.generation.source_generation_id)
        state.repo.ingest_batch([item], state.run, state.health, state.anchor)
        with state.repo.transaction():
            state.repo.connection.execute("UPDATE network_metadata_checkpoint SET committed_byte_offset=0,continuity_anchor_start_offset=0,continuity_anchor_length=0,continuity_anchor_sha256=NULL")
            state.repo.connection.execute("UPDATE network_metadata_source_generations SET committed_byte_offset=0")
            state.repo.connection.execute("UPDATE network_metadata_source_records SET source_record_sha256=?", ("f" * 64,))
        before = state.repo.latest_health()["health_id"]
        def crash(label):
            if label == "after_checkpoint_update_before_commit":
                raise RuntimeError("injected")
        state.repo._crash_point = crash
        with pytest.raises(RuntimeError):
            state.repo.ingest_batch([item], state.run, state.health, state.anchor)
        assert state.repo.load_active()[0].processing_state == "runnable"
        assert state.repo.latest_health()["health_id"] == before
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_ingest_fault_aggregates").fetchone()[0] == 0
        assert "source_record_identity_conflict" not in state.health.local_reasons


def test_expired_event_aggregate_checkpoint_and_health_commit_atomically(tmp_path):
    from datetime import timedelta
    from app.network_metadata.validation import ni_format_utc
    from . import record, source_event
    with store(tmp_path) as state:
        data = record(source_event(timestamp=ni_format_utc(state.clock() - timedelta(days=31))))
        (tmp_path / "source.jsonl").write_bytes(data + b"\n")
        item = outcome(state.config.capture_scope_binding, data, generation=state.generation.source_generation_id)
        before = state.repo.latest_health()["health_id"]
        def crash(label):
            if label == "after_checkpoint_update_before_commit":
                raise RuntimeError("injected")
        state.repo._crash_point = crash
        with pytest.raises(RuntimeError):
            state.repo.ingest_batch([item], state.run, state.health, state.anchor)
        assert state.repo.load_active()[1].committed_byte_offset == 0
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_ingest_fault_aggregates").fetchone()[0] == 0
        assert state.repo.latest_health()["health_id"] == before
        assert state.health.last_output is state.health.last_ingested is None
        state.repo._crash_point = lambda _: None
        state.repo.ingest_batch([item], state.run, state.health, state.anchor)
        assert state.repo.load_active()[1].committed_byte_offset == item.end
        assert tuple(state.repo.connection.execute("SELECT fault_category,count FROM network_metadata_ingest_fault_aggregates").fetchone()) == ("retention_expired_event", 1)
        state.clock.advance(seconds=60)
        state.repo.persist_health(state.health, state.repo.load_active()[0])
        assert state.repo.latest_health()["last_output_event_at"] == item.output_event_at
