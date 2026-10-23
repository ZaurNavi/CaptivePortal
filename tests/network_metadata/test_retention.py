from . import requires_posix_io
import pytest
from dataclasses import replace
from datetime import timedelta
from app.network_metadata.health import HealthController
from app.network_metadata.read_service import NetworkMetadataReadService
from app.network_metadata.validation import ni_format_utc
from app.network_metadata.retention import RetentionPolicy
from . import store, record, source_event, outcome, seed_blocked, SITE


@pytest.mark.parametrize("family", ["dns", "tls", "quic"])
@pytest.mark.parametrize("age", [timedelta(seconds=86399), timedelta(seconds=86400),
    timedelta(seconds=86401), timedelta(days=14), timedelta(days=30)])
@requires_posix_io
def test_late_first_ingest_exact_retention_boundaries(tmp_path, family, age):
    with store(tmp_path) as state:
        event = source_event(family, timestamp=ni_format_utc(state.clock() - age))
        data = record(event)
        (tmp_path / "source.jsonl").write_bytes(data + b"\n")
        item = outcome(state.config.capture_scope_binding, data, generation=state.generation.source_generation_id)
        sql = []
        state.repo.connection.set_trace_callback(sql.append)
        result = state.repo.ingest_batch([item], state.run, state.health, state.anchor)
        state.repo.connection.set_trace_callback(None)
        assert state.repo.load_active()[1].committed_byte_offset == item.end
        assert state.health.last_output == item.output_event_at
        assert state.health.output == state.health.ingest == "usable"
        if age > timedelta(days=1):
            assert result["committed"] == 0 and state.health.last_ingested is None
            for suffix in ("observations", "source_records", "sensitive_endpoints", "dns", "tls", "quic",
                           "dns_queries", "dns_answers", "tls_alpn"):
                assert state.repo.connection.execute(f"SELECT count(*) FROM network_metadata_{suffix}").fetchone()[0] == 0
            assert tuple(state.repo.connection.execute("SELECT fault_category,count FROM network_metadata_ingest_fault_aggregates").fetchone()) == ("retention_expired_event", 1)
            end = ni_format_utc(state.clock() - timedelta(microseconds=1))
            assert NetworkMetadataReadService(state.config.db_path).list_observations(
                SITE, item.output_event_at, end)["items"] == []
        else:
            expired = False  # Equal core/sensitive horizons: no retained expired parent.
            assert result["committed"] == 1 and state.health.last_ingested == item.output_event_at
            source_row = state.repo.connection.execute("SELECT * FROM network_metadata_source_records").fetchone()
            assert source_row["ingested_at"] == ni_format_utc(state.clock())
            assert source_row["digest_state"] == ("expired" if expired else "retained")
            assert source_row["source_record_sha256"] == (None if expired else item.normalized.source_record_sha256)
            assert source_row["semantic_payload_sha256"] == (None if expired else item.normalized.semantic_payload_sha256)
            assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_sensitive_endpoints").fetchone()[0] == int(not expired)
            payload = state.repo.connection.execute(f"SELECT * FROM network_metadata_{family}").fetchone()
            presence = "expired" if expired else "observed_retained"
            if family == "dns":
                assert payload["query_names_presence_state"] == payload["answer_values_presence_state"] == presence
                for suffix in ("dns_queries", "dns_answers"):
                    assert state.repo.connection.execute(f"SELECT count(*) FROM network_metadata_{suffix}").fetchone()[0] == int(not expired)
            else:
                assert payload["sni_presence_state"] == presence
                assert payload["sni"] == (None if expired else event[family]["sni"])
                if family == "tls":
                    assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_tls_alpn").fetchone()[0] == 3
        if age > timedelta(days=1):
            written = "\n".join(command for command in sql if command.startswith(("INSERT", "UPDATE")))
            for sensitive in ("ni-query-sentinel.example", "ni-sni-sentinel.example", "ni-quic-sentinel.example",
                              "203.0.113.93", "10.73.0.7", "2001:db8::93", item.normalized.source_record_sha256,
                              item.normalized.semantic_payload_sha256):
                assert sensitive not in written


@pytest.mark.parametrize("family", ["dns", "tls", "quic"])
@requires_posix_io
def test_late_never_observed_sensitive_stays_not_observed(tmp_path, family):
    with store(tmp_path) as state:
        event = source_event(family, timestamp=ni_format_utc(state.clock() - timedelta(seconds=86399)))
        if family == "dns":
            event[family]["queries"] = []
            event[family]["answers"] = [{"rrtype": "MX", "rdata": "not-retained"}]
        else:
            event[family]["sni"] = None
        data = record(event)
        (tmp_path / "source.jsonl").write_bytes(data + b"\n")
        state.repo.ingest_batch([outcome(state.config.capture_scope_binding, data,
            generation=state.generation.source_generation_id)], state.run, state.health, state.anchor)
        row = state.repo.connection.execute(f"SELECT * FROM network_metadata_{family}").fetchone()
        fields = ("query_names_presence_state", "answer_values_presence_state") if family == "dns" else ("sni_presence_state",)
        assert all(row[field] == "not_observed" for field in fields)


@pytest.mark.parametrize("age", [2, 31])
@pytest.mark.parametrize("disposition", ["duplicate_noop", "source_record_identity_conflict",
    "normalizer_determinism_conflict", "replay_identity_evidence_expired"])
@requires_posix_io
def test_touched_identity_retention_preserves_proven_disposition(tmp_path, age, disposition):
    with store(tmp_path) as state:
        item = outcome(state.config.capture_scope_binding, generation=state.generation.source_generation_id)
        state.repo.ingest_batch([item], state.run, state.health, state.anchor)
        before = dict(state.repo.connection.execute("SELECT * FROM network_metadata_observations").fetchone())
        if disposition == "source_record_identity_conflict":
            state.repo.connection.execute("UPDATE network_metadata_source_records SET source_record_sha256=?", ("f" * 64,))
        elif disposition == "normalizer_determinism_conflict":
            state.repo.connection.execute("UPDATE network_metadata_source_records SET semantic_payload_sha256=?", ("f" * 64,))
        elif disposition == "replay_identity_evidence_expired":
            state.repo.connection.execute("UPDATE network_metadata_source_records SET digest_state='expired',source_record_sha256=NULL,semantic_payload_sha256=NULL")
        state.repo.connection.execute("UPDATE network_metadata_checkpoint SET committed_byte_offset=0,continuity_anchor_start_offset=0,continuity_anchor_length=0,continuity_anchor_sha256=NULL")
        state.repo.connection.execute("UPDATE network_metadata_source_generations SET committed_byte_offset=0")
        state.clock.advance(days=age)
        health = HealthController(state.config.capture_scope_binding.capture_source_id)
        health.reload(state.repo)
        health.source_available()
        result = state.repo.ingest_batch([item], state.run, health, state.anchor)
        assert result["committed"] == 0
        if disposition == "duplicate_noop":
            assert result["duplicates"] == 1 and result["blocked"] is None
            assert state.repo.load_active()[1].committed_byte_offset == item.end
        else:
            assert result["blocked"] == disposition
            assert state.repo.load_active()[0].blocked_reason_code == disposition
            assert state.repo.latest_health()["metadata_ingest_health"] == "unavailable"
        row = state.repo.connection.execute("SELECT * FROM network_metadata_observations").fetchone()
        if age > 1:
            assert row is None
        else:
            for field in ("event_at", "ingested_at", "ingest_run_id", "source_health_ref"):
                assert row[field] == before[field]
            assert row["sensitive_endpoint_presence_state"] == "expired"
            assert tuple(state.repo.connection.execute("SELECT digest_state,source_record_sha256,semantic_payload_sha256 FROM network_metadata_source_records").fetchone()) == ("expired", None, None)


@pytest.mark.parametrize("family", ["dns", "tls", "quic"])
@requires_posix_io
def test_core_cascades_once_at_shared_sensitive_horizon(tmp_path, family):
    data = record(source_event(family))
    with store(tmp_path, source=data + b"\n") as state:
        item = outcome(state.config.capture_scope_binding, data, generation=state.generation.source_generation_id)
        state.repo.ingest_batch([item], state.run, state.health, state.anchor)
        state.clock.advance(days=1)
        result = RetentionPolicy(state.repo).run()
        assert result["sensitive"] == result["core"] == 0
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_sensitive_endpoints").fetchone()[0] == 1
        state.clock.advance(seconds=1)
        sql = []
        state.repo.connection.set_trace_callback(sql.append)
        result = RetentionPolicy(state.repo).run()
        state.repo.connection.set_trace_callback(None)
        assert result["core"] == 1 and result["sensitive"] == 0
        assert not any(command.startswith('UPDATE network_metadata_') for command in sql)
        for suffix in ('observations','source_records','sensitive_endpoints','dns','tls','quic','dns_queries','dns_answers','tls_alpn'):
            assert state.repo.connection.execute('SELECT count(*) FROM network_metadata_'+suffix).fetchone()[0] == 0
        assert state.repo.connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert state.repo.load_active()[1].committed_byte_offset == item.end


@requires_posix_io
def test_not_observed_does_not_turn_expired(tmp_path):
    event = source_event("tls")
    event["tls"]["sni"] = None
    data = record(event)
    with store(tmp_path, source=data + b"\n") as state:
        state.repo.ingest_batch([outcome(state.config.capture_scope_binding, data,
            generation=state.generation.source_generation_id)], state.run, state.health, state.anchor)
        state.clock.advance(seconds=86399)
        RetentionPolicy(state.repo).run()
        assert state.repo.connection.execute("SELECT sni_presence_state FROM network_metadata_tls").fetchone()[0] == "not_observed"


@requires_posix_io
def test_block_survives_46_day_diagnostic_expiry_and_restart(tmp_path):
    with store(tmp_path) as state:
        generation, checkpoint = seed_blocked(state)
        state.clock.advance(days=46)
        cleanup = RetentionPolicy(state.repo).run()
        assert cleanup["health"] > 0 and cleanup["faults"] == 1 and cleanup["core"] == 1
        state.repo.recover()
        assert state.repo.load_active() == (generation, checkpoint)
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_capture_scope_bindings").fetchone()[0] == 1
        assert state.repo.connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_closed_lineage_24_hours_and_active_preserved(tmp_path):
    with store(tmp_path) as state:
        old = state.generation.source_generation_id
        new, _ = state.repo.transition_generation(binding=state.config.capture_scope_binding, boot_id=state.generation.host_boot_id,
            physical=(state.generation.st_dev, state.generation.st_ino), close_reason="source_rotated_live")
        state.repo.persist_health(state.health, new, force=True)
        state.clock.advance(days=3)
        result = RetentionPolicy(state.repo).run()
        assert result["generations"] == 1
        assert state.repo.load_active()[0].source_generation_id == new.source_generation_id
        assert state.repo.connection.execute("SELECT source_generation_id FROM network_metadata_source_generations WHERE source_generation_id=?", (old,)).fetchone() is None


@pytest.mark.parametrize("fixture", ["all_full", "mixed", "all_empty", "small"])
def test_retention_global_nonempty_batch_budget_and_priority(tmp_path, monkeypatch, fixture):
    from app.network_metadata.models import RETENTION_MAX_BATCHES_PER_PASS, RETENTION_PARENT_BATCH_ROWS
    assert RETENTION_MAX_BATCHES_PER_PASS == 20 and RETENTION_PARENT_BATCH_ROWS == 5000
    classes = ("core", "health", "faults", "generations", "bindings", "runs")
    with store(tmp_path) as state:
        policy = RetentionPolicy(state.repo)
        probes, mutations, sql = [], [], []
        seen = dict.fromkeys(classes, 0)
        def select(category, cutoffs):
            assert not state.repo.connection.in_transaction
            assert tuple(cutoffs) == (1,)
            probes.append(category)
            index = seen[category]
            seen[category] += 1
            if fixture == "all_empty":
                return []
            if fixture == "small":
                return list(range(37)) if index == 0 else []
            if fixture == "mixed" and (
                    category == "core" and index >= 2 or category == "health" and index >= 3):
                return []
            return list(range(5000))
        def delete(category, ids):
            assert state.repo.connection.in_transaction
            assert 0 < len(ids) <= 5000
            mutations.append((category, len(ids)))
        monkeypatch.setattr(policy, "_select", select)
        monkeypatch.setattr(policy, "_delete", delete)
        state.repo.connection.set_trace_callback(sql.append)
        totals = policy.run()
        state.repo.connection.set_trace_callback(None)
        assert tuple(key for key in totals if key != 'sensitive') == classes
        assert totals['sensitive'] == 0
        if fixture == "all_full":
            assert mutations == [("core", 5000)] * 20
            assert probes == ["core"] * 20
            assert totals == dict(core=100000, sensitive=0, health=0, faults=0, generations=0, bindings=0, runs=0)
        elif fixture == "mixed":
            assert mutations == [("core", 5000)] * 2 + [("health", 5000)] * 3 + [("faults", 5000)] * 15
            assert probes == ["core"] * 3 + ["health"] * 4 + ["faults"] * 15
            assert totals == dict(core=10000, sensitive=0, health=15000, faults=75000, generations=0, bindings=0, runs=0)
        elif fixture == "all_empty":
            assert not mutations and probes == list(classes)
            assert all(value == 0 for value in totals.values())
        else:
            assert mutations == [(category, 37) for category in classes]
            assert probes == [category for category in classes for _ in range(2)]
            assert {key:value for key,value in totals.items() if key != 'sensitive'} == dict.fromkeys(classes, 37)
        assert len(mutations) <= 20
        assert sql.count("BEGIN IMMEDIATE") == sql.count("COMMIT") == len(mutations)


@requires_posix_io
def test_gc_preserves_current_health_active_run_checkpoint_and_rejects_old_replay(tmp_path):
    from app.network_metadata.models import NetworkMetadataValidationError
    with store(tmp_path) as state:
        item = outcome(state.config.capture_scope_binding, generation=state.generation.source_generation_id)
        state.repo.ingest_batch([item], state.run, state.health, state.anchor)
        checkpoint = state.repo.load_active()[1]
        latest = state.repo.latest_health()['health_id']
        state.clock.advance(days=3)
        assert RetentionPolicy(state.repo).run()['core'] == 1
        assert state.repo.load_active()[1] == checkpoint
        assert state.repo.latest_health()['health_id'] == latest
        assert state.repo.connection.execute('SELECT 1 FROM network_metadata_ingest_runs WHERE ingest_run_id=?',(state.run,)).fetchone()
        with pytest.raises(NetworkMetadataValidationError):
            state.repo.ingest_batch([item], state.run, state.health, state.anchor)
        assert state.repo.connection.execute('SELECT count(*) FROM network_metadata_observations').fetchone()[0] == 0
        fresh = record(source_event(timestamp=ni_format_utc(state.clock())))
        (tmp_path/'source.jsonl').write_bytes(record()+b'\n'+fresh+b'\n')
        new = outcome(state.config.capture_scope_binding, fresh, start=item.end, generation=state.generation.source_generation_id)
        assert state.repo.ingest_batch([new], state.run, state.health, state.anchor)['committed'] == 1
        assert state.repo.load_active()[1].committed_byte_offset == new.end


@requires_posix_io
def test_core_gc_rollback_preserves_children_and_checkpoint(tmp_path, monkeypatch):
    with store(tmp_path) as state:
        item = outcome(state.config.capture_scope_binding, generation=state.generation.source_generation_id)
        state.repo.ingest_batch([item], state.run, state.health, state.anchor)
        checkpoint = state.repo.load_active()[1]
        state.clock.advance(days=2)
        policy = RetentionPolicy(state.repo)
        original = policy._delete
        def crash(kind, ids):
            original(kind, ids)
            raise RuntimeError('synthetic_gc_before_commit')
        monkeypatch.setattr(policy, '_delete', crash)
        with pytest.raises(RuntimeError, match='synthetic_gc_before_commit'):policy.run()
        assert state.repo.connection.execute('SELECT count(*) FROM network_metadata_observations').fetchone()[0] == 1
        assert state.repo.connection.execute('SELECT count(*) FROM network_metadata_source_records').fetchone()[0] == 1
        assert state.repo.load_active()[1] == checkpoint
        assert state.repo.connection.execute('PRAGMA foreign_key_check').fetchall() == []


@pytest.mark.parametrize('age', [86399, 86400, 86401])
@pytest.mark.parametrize('field', ['event_at', 'ingested_at'])
@requires_posix_io
def test_native_gc_disagreeing_event_ingest_boundary(tmp_path, age, field):
    with store(tmp_path) as state:
        item = outcome(state.config.capture_scope_binding, generation=state.generation.source_generation_id)
        state.repo.ingest_batch([item], state.run, state.health, state.anchor)
        # Simulate a persisted native history age mix; do not rewrite source time
        # during production admission/retry. The other time remains fresh.
        cutoff_value = ni_format_utc(state.clock()-timedelta(seconds=age))
        with state.repo.transaction():
            state.repo.connection.execute('UPDATE network_metadata_observations SET '+field+'=?',(cutoff_value,))
            if field == 'ingested_at':state.repo.connection.execute('UPDATE network_metadata_source_records SET ingested_at=?',(cutoff_value,))
        result = RetentionPolicy(state.repo).run()
        assert result['core'] == int(age > 86400) and result['sensitive'] == 0
        assert state.repo.connection.execute('SELECT count(*) FROM network_metadata_observations').fetchone()[0] == int(age <= 86400)
        assert state.repo.load_active()[1].committed_byte_offset == item.end


def _v3c_old_schema():
    """Exact frozen V1, not a reconstructed approximation of the old layout."""
    import subprocess
    from pathlib import Path
    source = subprocess.check_output([
        'git', 'show', 'afdfd4f9b9a8798e71db5aed984e4196b5645090:app/network_metadata/schema.py',
    ], cwd=Path(__file__).resolve().parents[2])
    namespace = {'__name__': 'frozen_ni01_schema', '__package__': 'app.network_metadata'}
    exec(compile(source, '<frozen-base-ni01-schema>', 'exec'), namespace)
    return namespace


def _v3c_data_snapshot(connection):
    from app.network_metadata.schema import TABLE_DDL
    return {name: tuple(tuple(row) for row in connection.execute('SELECT * FROM '+name+' ORDER BY rowid'))
            for name in TABLE_DDL}


def test_v3c_fresh_exact_nonunique_health_fk_index_and_durability(tmp_path):
    from app.network_metadata.schema import INDEX_DDL, validate_schema
    name = 'idx_nm_observations_source_health_ref'
    with store(tmp_path) as state:
        conn = state.repo.connection
        validate_schema(conn, writer=True)
        assert INDEX_DDL[name] == 'network_metadata_observations(source_health_ref)'
        assert tuple(conn.execute("SELECT sql FROM sqlite_master WHERE name=?", (name,)).fetchone()) == (
            'CREATE INDEX '+name+' ON '+INDEX_DDL[name],)
        row = next(row for row in conn.execute('PRAGMA index_list(network_metadata_observations)') if row[1] == name)
        assert row[2:] == (0, 'c', 0)  # Nonunique, explicit, not partial.
        assert [row[2] for row in conn.execute('PRAGMA index_info('+name+')')] == ['source_health_ref']
        for pragma, value in [('user_version', 1), ('foreign_keys', 1), ('synchronous', 2), ('journal_mode', 'wal')]:
            assert conn.execute('PRAGMA '+pragma).fetchone()[0] == value


@requires_posix_io
def test_v3c_old_offline_index_upgrade_and_layout_rollback_only(tmp_path, monkeypatch):
    from contextlib import closing
    import sqlite3
    import app.network_metadata.repository as repository
    from app.network_metadata.models import NetworkMetadataStorageCorrupt
    from app.network_metadata.schema import validate_schema
    old = _v3c_old_schema()
    name = 'idx_nm_observations_source_health_ref'
    with monkeypatch.context() as patch:
        patch.setattr(repository, 'create_schema', old['create_schema'])
        patch.setattr(repository, 'validate_schema', old['validate_schema'])
        with store(tmp_path) as state:
            item = outcome(state.config.capture_scope_binding, generation=state.generation.source_generation_id)
            state.repo.ingest_batch([item], state.run, state.health, state.anchor)
            before = _v3c_data_snapshot(state.repo.connection)
            old['validate_schema'](state.repo.connection, writer=True)
            config, clock = state.config, state.clock
    # Old writer is closed before explicit disposable offline maintenance.
    probe = repository.NetworkMetadataRepository(config, clock=clock)
    try:
        with pytest.raises(NetworkMetadataStorageCorrupt):
            probe.initialize()
    finally:
        probe.close()
    with closing(sqlite3.connect(config.db_path, isolation_level=None)) as conn:
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA synchronous=FULL')
        assert conn.execute('SELECT 1 FROM sqlite_master WHERE name=?', (name,)).fetchone() is None
        assert _v3c_data_snapshot(conn) == before  # No startup auto-DDL or data repair.
        with pytest.raises(NetworkMetadataStorageCorrupt):
            validate_schema(conn, writer=True)
        conn.execute('CREATE INDEX '+name+' ON network_metadata_observations(source_health_ref)')
        validate_schema(conn, writer=True)
        assert _v3c_data_snapshot(conn) == before
        with pytest.raises(NetworkMetadataStorageCorrupt):
            old['validate_schema'](conn, writer=True)
        # FK protection remains enforced even with the faster child lookup.
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute('DELETE FROM network_metadata_source_health WHERE health_id IN '
                         '(SELECT source_health_ref FROM network_metadata_observations)')
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
        assert _v3c_data_snapshot(conn) == before
    upgraded = repository.NetworkMetadataRepository(config, clock=clock).initialize()
    assert _v3c_data_snapshot(upgraded.connection) == before
    upgraded.close()
    with closing(sqlite3.connect(config.db_path, isolation_level=None)) as conn:
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA synchronous=FULL')
        conn.execute('DROP INDEX '+name)
        old['validate_schema'](conn, writer=True)
        with pytest.raises(NetworkMetadataStorageCorrupt):
            validate_schema(conn, writer=True)
        assert _v3c_data_snapshot(conn) == before  # Layout rollback, NOT purged-history restoration.


@pytest.mark.parametrize('damage', ['missing', 'wrong_column', 'unique', 'partial', 'extra'])
def test_v3c_strict_index_signature_rejects_other_layouts(tmp_path, damage):
    from app.network_metadata.models import NetworkMetadataStorageCorrupt
    from app.network_metadata.schema import validate_schema
    name = 'idx_nm_observations_source_health_ref'
    with store(tmp_path) as state:
        conn = state.repo.connection
        if damage != 'extra':
            conn.execute('DROP INDEX '+name)
        if damage == 'wrong_column':
            conn.execute('CREATE INDEX '+name+' ON network_metadata_observations(ingest_run_id)')
        elif damage == 'unique':
            conn.execute('CREATE UNIQUE INDEX '+name+' ON network_metadata_observations(source_health_ref)')
        elif damage == 'partial':
            conn.execute('CREATE INDEX '+name+' ON network_metadata_observations(source_health_ref) WHERE event_at IS NOT NULL')
        elif damage == 'extra':
            conn.execute('CREATE INDEX unapproved_extra_index ON network_metadata_observations(source_health_ref)')
        with pytest.raises(NetworkMetadataStorageCorrupt):
            validate_schema(conn, writer=True)
