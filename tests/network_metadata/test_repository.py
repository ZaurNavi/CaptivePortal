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
from contextlib import contextmanager
from types import SimpleNamespace
from . import Clock, BOOT, IDENTITY


@contextmanager
def _a_store(tmp_path, enabled, *, source=None):
    """Disposable single-writer fixture; flag applied before actual initialization."""
    from app.network_metadata.health import HealthController
    from app.network_metadata.source import continuity_anchor
    tmp_path.mkdir(parents=True, exist_ok=True)
    config = configuration(tmp_path, NETWORK_METADATA_IO_HOTPATH_V1_ENABLED="true" if enabled else "false")
    clock, events = Clock(), []
    class Telemetry:
        def emit(self, event, **fields):
            events.append((event, fields))
    (tmp_path / "source.jsonl").write_bytes(record() + b"\n" if source is None else source)
    repo = NetworkMetadataRepository(config, clock=clock, telemetry=Telemetry()).initialize()
    fd = os.open(config.source_path, os.O_RDONLY)
    try:
        repo.persist_binding(config.capture_scope_binding)
        run = repo.create_ingest_run(IDENTITY)
        info = os.fstat(fd)
        generation, _ = repo.transition_generation(binding=config.capture_scope_binding, boot_id=BOOT,
            physical=(info.st_dev, info.st_ino))
        health = HealthController(config.capture_scope_binding.capture_source_id)
        health.source_available()
        repo.persist_health(health, generation)
        yield SimpleNamespace(repo=repo, config=config, clock=clock, fd=fd, run=run,
            health=health, generation=generation, events=events,
            anchor=lambda offset: continuity_anchor(fd, offset))
    finally:
        os.close(fd)
        repo.close()


def _a_outcomes(state, data):
    offset, result = 0, []
    for raw in data:
        item = outcome(state.config.capture_scope_binding, raw, start=offset,
            generation=state.generation.source_generation_id)
        result.append(item)
        offset = item.end
    return result


def _a_rewind(state):
    with state.repo.transaction():
        state.repo.connection.execute("UPDATE network_metadata_checkpoint SET committed_byte_offset=0,continuity_anchor_start_offset=0,continuity_anchor_length=0,continuity_anchor_sha256=NULL")
        state.repo.connection.execute("UPDATE network_metadata_source_generations SET committed_byte_offset=0")


def _a_rows(repo):
    """All persistent fields; normalize only physical fixture inode and opt-in lineage."""
    snapshot = {}
    for table in TABLE_DDL:
        rows = [dict(row) for row in repo.connection.execute("SELECT * FROM " + table)]
        for row in rows:
            if table == "network_metadata_source_generations":
                row["st_dev"] = row["st_ino"] = "<disposable physical identity>"
            if table == "network_metadata_ingest_runs":
                row["configuration_digest"] = "<explicitly different flag/path lineage>"
        snapshot[table] = sorted(ni01_canonical_json(row).decode() for row in rows)
    return snapshot


def _a_sql(sql):
    return dict(
        range_probes=sum(q.startswith("SELECT 1 FROM network_metadata_source_records WHERE") for q in sql),
        identities=sum(q.startswith("SELECT digest_state,source_record_sha256,semantic_payload_sha256 FROM network_metadata_source_records") for q in sql),
        insert_pragmas=sum(q.startswith("PRAGMA table_info(") for q in sql),
        fault_upserts=sum("INSERT INTO network_metadata_ingest_fault_aggregates" in q for q in sql),
    )


@pytest.mark.parametrize("category", ["duplicate_noop", "source_record_identity_conflict",
    "normalizer_determinism_conflict", "replay_identity_evidence_expired"])
@pytest.mark.parametrize("index", [0, 1, 2])
def test_io_hotpath_overlap_first_conflict_matches_off(tmp_path, monkeypatch, category, index):
    import uuid
    snapshots = []
    for enabled in (False, True):
        ids = iter(uuid.UUID(f"00000000-0000-4000-8000-{n:012d}") for n in range(1, 50))
        monkeypatch.setattr(uuid, "uuid4", lambda: next(ids))
        with _a_store(tmp_path / str(enabled), enabled, source=(record() + b"\n") * 3) as state:
            items = _a_outcomes(state, [record()] * 3)
            state.repo.ingest_batch(items, state.run, state.health, state.anchor)
            for position, item in enumerate(items):
                if position != index:
                    state.repo.connection.execute("DELETE FROM network_metadata_observations WHERE observation_id=?",
                        (item.normalized.observation_id,))
            if category != "duplicate_noop":
                change = {
                    "source_record_identity_conflict": "source_record_sha256='" + "f" * 64 + "'",
                    "normalizer_determinism_conflict": "semantic_payload_sha256='" + "f" * 64 + "'",
                    "replay_identity_evidence_expired": "digest_state='expired',source_record_sha256=NULL,semantic_payload_sha256=NULL",
                }[category]
                state.repo.connection.execute("UPDATE network_metadata_source_records SET " + change)
            _a_rewind(state)
            sql, reached = [], []
            actual = state.repo.identity_outcome
            def identity(generation_id, item):
                reached.append(item.start)
                return actual(generation_id, item)
            monkeypatch.setattr(state.repo, "identity_outcome", identity)
            state.repo.connection.set_trace_callback(sql.append)
            result = state.repo.ingest_batch(items, state.run, state.health, state.anchor)
            state.repo.connection.set_trace_callback(None)
            expected_count = 3 if category == "duplicate_noop" else index + 1
            assert reached == [item.start for item in items[:expected_count]]
            assert _a_sql(sql)["range_probes"] == int(enabled)
            assert _a_sql(sql)["identities"] == expected_count
            if category == "duplicate_noop":
                assert result == dict(committed=2, duplicates=1, blocked=None)
            else:
                assert result == dict(committed=index, duplicates=0, blocked=category)
                assert state.repo.load_active()[1].committed_byte_offset == items[index].start
                assert state.repo.load_active()[0].blocked_record_start_byte_offset == items[index].start
            snapshots.append((_a_rows(state.repo), result, state.events))
    assert snapshots[0] == snapshots[1]


def test_io_hotpath_range_gap_and_generation_isolation(tmp_path, monkeypatch):
    with _a_store(tmp_path, True, source=(record() + b"\n") * 2) as state:
        items = _a_outcomes(state, [record()] * 2)
        gap = outcome(state.config.capture_scope_binding, start=1,
            generation=state.generation.source_generation_id)
        with state.repo.transaction() as now:
            state.repo._observation(gap, state.generation, state.run, state.health.last_snapshot.health_id, now)
        assert not state.repo.identity_range_empty(state.generation.source_generation_id, 0, items[-1].start)
        assert state.repo.identity_range_empty("00000000-0000-4000-8000-000000000099", 0, items[-1].start)
        reached, original = [], state.repo.identity_outcome
        def identity(generation_id, item):
            reached.append(item.start)
            return original(generation_id, item)
        monkeypatch.setattr(state.repo, "identity_outcome", identity)
        assert state.repo.ingest_batch(items, state.run, state.health, state.anchor)["committed"] == 2
        assert reached == [item.start for item in items]


@pytest.mark.parametrize("bad", [(0,), (True,), ("1",), (), (1, 2), 1, {"value": 1}])
def test_io_hotpath_malformed_probe_is_unavailable_not_empty(tmp_path, bad):
    from app.network_metadata.models import NetworkMetadataStorageUnavailable
    with _a_store(tmp_path, True) as state:
        actual = state.repo.connection
        class Connection:
            def __getattr__(self, name):
                return getattr(actual, name)
            def execute(self, sql, *args):
                if sql.startswith("SELECT 1 FROM network_metadata_source_records"):
                    return SimpleNamespace(fetchone=lambda: bad)
                return actual.execute(sql, *args)
        state.repo.connection = Connection()
        with pytest.raises(NetworkMetadataStorageUnavailable):
            state.repo.ingest_batch(_a_outcomes(state, [record()]), state.run, state.health, state.anchor)
        assert actual.execute("SELECT committed_byte_offset FROM network_metadata_checkpoint").fetchone()[0] == 0
        assert not actual.in_transaction
        assert actual.execute("SELECT count(*) FROM network_metadata_observations").fetchone()[0] == 0


def test_io_hotpath_probe_sql_failure_never_commits(tmp_path):
    from app.network_metadata.models import NetworkMetadataStorageUnavailable
    with _a_store(tmp_path, True) as state:
        before = _a_rows(state.repo)
        def authorize(action, table, *_):
            return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_READ and table == "network_metadata_source_records" else sqlite3.SQLITE_OK
        state.repo.connection.set_authorizer(authorize)
        with pytest.raises(NetworkMetadataStorageUnavailable):
            state.repo.ingest_batch(_a_outcomes(state, [record()]), state.run, state.health, state.anchor)
        # Restore default authorization on supported Python 3.10, without None.
        state.repo.connection.set_authorizer(lambda *_: sqlite3.SQLITE_OK)
        assert _a_rows(state.repo) == before


def test_io_hotpath_validated_cache_lifecycle_and_closed_insert(tmp_path):
    from app.network_metadata.models import NetworkMetadataStorageUnavailable
    with _a_store(tmp_path, True) as state:
        repo = state.repo
        assert set(repo._insert_columns) == set(TABLE_DDL)
        assert all(type(columns) is frozenset and columns for columns in repo._insert_columns.values())
        with pytest.raises(TypeError):
            repo._insert_columns["extra"] = frozenset()
        sql = []
        repo.connection.set_trace_callback(sql.append)
        for table, values in [("not_a_table", {}), ("network_metadata_checkpoint", {"not_a_column": 1})]:
            with pytest.raises(NetworkMetadataValidationError):
                repo._insert(table, values)
        assert _a_sql(sql)["insert_pragmas"] == 0
        original_snapshot, original_connection = repo._insert_columns, repo.connection
        repo.recover()
        assert repo._insert_columns is not original_snapshot
        assert repo._insert_columns_connection is repo.connection is not original_connection
        repo.config = replace(repo.config, db_path=str(tmp_path / "another.sqlite3"))
        with pytest.raises(NetworkMetadataStorageUnavailable):
            repo._insert("network_metadata_checkpoint", {})
        repo.config = state.config
        current = repo.connection
        other = sqlite3.connect(":memory:")
        try:
            repo.connection = other
            with pytest.raises(NetworkMetadataStorageUnavailable):
                repo._insert("network_metadata_checkpoint", {})
        finally:
            repo.connection = current
            other.close()
        repo.close()
        assert repo._insert_columns is repo._insert_columns_connection is repo._insert_columns_path is None
        with pytest.raises(NetworkMetadataStorageUnavailable):
            repo._insert("network_metadata_checkpoint", {})
        repo.initialize()
        assert repo._insert_columns_connection is repo.connection


@pytest.mark.parametrize("failure", ["schema_validation", "introspection", "replaced_schema"])
def test_io_hotpath_failed_initialize_never_adopts_cache(tmp_path, monkeypatch, failure):
    from app.network_metadata import repository as module
    from app.network_metadata.models import NetworkMetadataStorageUnavailable
    cfg = configuration(tmp_path, NETWORK_METADATA_IO_HOTPATH_V1_ENABLED="true")
    repo = NetworkMetadataRepository(cfg)
    with pytest.raises(NetworkMetadataStorageUnavailable):
        repo._insert("network_metadata_checkpoint", {})
    actual_validate = module.validate_schema
    if failure == "replaced_schema":
        repo.initialize()
        repo.connection.execute("DROP INDEX idx_nm_observations_site_event")
        repo.close()
    else:
        def validate(connection):
            assert repo._insert_columns is None
            actual_validate(connection)
            if failure == "schema_validation":
                raise NetworkMetadataStorageCorrupt()
            connection.set_authorizer(lambda action, name, *_: sqlite3.SQLITE_DENY
                if action == sqlite3.SQLITE_PRAGMA and name == "table_info" else sqlite3.SQLITE_OK)
        monkeypatch.setattr(module, "validate_schema", validate)
    with pytest.raises(NetworkMetadataStorageUnavailable):
        repo.initialize()
    assert repo.connection is repo._insert_columns is repo._insert_columns_connection is None


@pytest.mark.parametrize("count", [0, 1, 10, 256])
@pytest.mark.parametrize("many", [False, True])
def test_io_hotpath_fault_sql_grouping_and_complete_equivalence(tmp_path, monkeypatch, count, many):
    import uuid
    raw = [b"{", b"\xff", b"[]"] if many else [b"{"]
    data = [raw[index % len(raw)] for index in range(count)]
    snapshots, metrics = [], []
    for enabled in (False, True):
        ids = iter(uuid.UUID(f"00000000-0000-4000-8000-{n:012d}") for n in range(1, 30))
        monkeypatch.setattr(uuid, "uuid4", lambda: next(ids))
        with _a_store(tmp_path / str(enabled), enabled, source=b"\n".join(data) + (b"\n" if data else b"")) as state:
            items = _a_outcomes(state, data)
            if count:
                with state.repo.transaction() as now:
                    for _ in range(3):
                        state.repo._fault(state.generation.source_generation_id, "invalid_json", now, 999)
                state.clock.advance(seconds=5)
            sql = []
            state.repo.connection.set_trace_callback(sql.append)
            result = state.repo.ingest_batch(items, state.run, state.health, state.anchor)
            state.repo.connection.set_trace_callback(None)
            group_count = len({item.category for item in items})
            assert _a_sql(sql)["fault_upserts"] == (group_count if enabled else count)
            if count:
                row = state.repo.connection.execute("SELECT * FROM network_metadata_ingest_fault_aggregates WHERE fault_category='invalid_json'").fetchone()
                assert row["first_relevant_offset"] == 999
                assert row["first_seen_utc"] == "2026-10-07T12:00:00.000000Z"
                assert row["last_relevant_offset"] == [item for item in items if item.category == "invalid_json"][-1].start
                assert state.events[-1][0] == "health_transition"
                assert next(fields["count"] for event, fields in reversed(state.events)
                    if event == "ingest_fault_aggregate_updated") == count
            snapshots.append((_a_rows(state.repo), result, state.events))
            metrics.append(_a_sql(sql))
    assert snapshots[0] == snapshots[1]
    print("NI01_A_FAULT_SQL", {"events": count, "many_categories": many, "off": metrics[0], "on": metrics[1]})


def test_io_hotpath_fault_epochs_stable_flush_and_invalid_category(tmp_path):
    with _a_store(tmp_path, True) as state:
        groups = {}
        generation = state.generation.source_generation_id
        for category, now, offset in [
            ("invalid_json", "2026-10-07T12:06:00.000000Z", 7),
            ("schema_invalid", "2026-10-07T12:00:00.000000Z", 2),
            ("invalid_json", "2026-10-07T12:00:00.000000Z", 5),
            ("invalid_json", "2026-10-07T12:06:00.000000Z", 1),
        ]:
            state.repo._accumulate_fault(groups, generation, category, now, offset)
        before = {key: list(value) for key, value in groups.items()}
        for category in ("unknown", True, []):
            with pytest.raises(NetworkMetadataValidationError):
                state.repo._accumulate_fault(groups, generation, category, "2026-10-07T12:00:00.000000Z", 0)
            assert groups == before
        sql = []
        state.repo.connection.set_trace_callback(sql.append)
        with state.repo.transaction():
            state.repo._flush_fault_groups(groups)
        assert _a_sql(sql)["fault_upserts"] == 3
        rows = list(state.repo.connection.execute("SELECT fault_category,aggregation_epoch_start_utc,count,first_relevant_offset,last_relevant_offset FROM network_metadata_ingest_fault_aggregates ORDER BY rowid"))
        assert [tuple(row) for row in rows] == [
            ("invalid_json", "2026-10-07T12:00:00.000000Z", 1, 5, 5),
            ("invalid_json", "2026-10-07T12:05:00.000000Z", 2, 7, 1),
            ("schema_invalid", "2026-10-07T12:00:00.000000Z", 1, 2, 2),
        ]


@pytest.mark.parametrize("failure", ["overflow", "sql", "invalid_category"])
def test_io_hotpath_fault_failure_rolls_back_entire_batch(tmp_path, monkeypatch, failure):
    from app.network_metadata.models import INT64_MAX, NetworkMetadataStorageUnavailable
    with _a_store(tmp_path, True, source=record() + b"\n{\n") as state:
        items = _a_outcomes(state, [record(), b"{"])
        if failure == "overflow":
            with state.repo.transaction() as now:
                state.repo._fault(state.generation.source_generation_id, "invalid_json", now, 1)
                state.repo.connection.execute("UPDATE network_metadata_ingest_fault_aggregates SET count=?", (INT64_MAX,))
        elif failure == "invalid_category":
            items[-1] = replace(items[-1], category="not_admitted")
        before = _a_rows(state.repo)
        if failure == "sql":
            state.repo.connection.set_authorizer(lambda action, table, *_: sqlite3.SQLITE_DENY
                if action == sqlite3.SQLITE_INSERT and table == "network_metadata_ingest_fault_aggregates" else sqlite3.SQLITE_OK)
        with pytest.raises(NetworkMetadataValidationError if failure == "invalid_category" else NetworkMetadataStorageUnavailable):
            state.repo.ingest_batch(items, state.run, state.health, state.anchor)
        state.repo.connection.set_authorizer(lambda *_: sqlite3.SQLITE_OK)
        assert _a_rows(state.repo) == before
        assert state.repo.load_active()[1].committed_byte_offset == 0
        assert not state.repo.connection.in_transaction


def test_io_hotpath_external_ddl_sql_failure_is_not_schema_bypass(tmp_path):
    from app.network_metadata.models import NetworkMetadataStorageUnavailable
    with _a_store(tmp_path, True) as state:
        state.repo.connection.execute("DROP TABLE network_metadata_dns_queries")
        health_before = state.repo.latest_health()["health_id"]
        with pytest.raises(NetworkMetadataStorageUnavailable):
            state.repo.ingest_batch(_a_outcomes(state, [record()]), state.run, state.health, state.anchor)
        assert state.repo.latest_health()["health_id"] == health_before
        assert state.repo.load_active()[1].committed_byte_offset == 0
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_observations").fetchone()[0] == 0


@pytest.mark.parametrize("enabled", [False, True])
def test_io_hotpath_mixed_fault_duplicate_conflict_freezes_only_reached_prefix(tmp_path, enabled):
    from . import source_event
    data = [record(), b"{", b"{", record(source_event("tls")), record(source_event("quic")), record()]
    with _a_store(tmp_path, enabled, source=b"\n".join(data) + b"\n") as state:
        items = _a_outcomes(state, data)
        state.repo.ingest_batch(items[:5], state.run, state.health, state.anchor)
        state.repo.connection.execute("DELETE FROM network_metadata_observations WHERE observation_id=?",
            (items[0].normalized.observation_id,))
        state.repo.connection.execute("DELETE FROM network_metadata_ingest_fault_aggregates")
        state.repo.connection.execute("UPDATE network_metadata_source_records SET source_record_sha256=? WHERE record_start_byte_offset=?",
            ("f" * 64, items[4].start))
        _a_rewind(state)
        sql = []
        state.repo.connection.set_trace_callback(sql.append)
        result = state.repo.ingest_batch(items, state.run, state.health, state.anchor)
        state.repo.connection.set_trace_callback(None)
        assert result == dict(committed=1, duplicates=1, blocked="source_record_identity_conflict")
        assert state.repo.load_active()[1].committed_byte_offset == items[4].start
        assert _a_sql(sql)["fault_upserts"] == (2 if enabled else 3)
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_observations WHERE observation_id=?",
            (items[5].normalized.observation_id,)).fetchone()[0] == 0
        assert [tuple(row) for row in state.repo.connection.execute(
            "SELECT fault_category,count FROM network_metadata_ingest_fault_aggregates ORDER BY fault_category")] == [
                ("invalid_json", 2), ("source_record_identity_conflict", 1)]
        assert next(fields["count"] for event, fields in reversed(state.events)
            if event == "ingest_fault_aggregate_updated") == 3
        before = _a_rows(state.repo)
        with pytest.raises(NetworkMetadataStorageCorrupt):
            state.repo.ingest_batch(items, state.run, state.health, state.anchor)
        assert _a_rows(state.repo) == before


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("age", [15, 31])
def test_io_hotpath_retention_expiry_semantics_are_preserved(tmp_path, enabled, age):
    from datetime import timedelta
    from app.network_metadata.validation import ni_format_utc
    from . import source_event, Clock
    data = record(source_event(timestamp=ni_format_utc(Clock()() - timedelta(days=age))))
    with _a_store(tmp_path, enabled, source=data + b"\n") as state:
        items = _a_outcomes(state, [data])
        result = state.repo.ingest_batch(items, state.run, state.health, state.anchor)
        assert state.repo.load_active()[1].committed_byte_offset == items[0].end
        if age == 31:
            assert result["committed"] == 0
            assert tuple(state.repo.connection.execute("SELECT fault_category,count FROM network_metadata_ingest_fault_aggregates").fetchone()) == ("retention_expired_event", 1)
            assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_observations").fetchone()[0] == 0
        else:
            assert result["committed"] == 1
            assert state.repo.connection.execute("SELECT sensitive_endpoint_presence_state FROM network_metadata_observations").fetchone()[0] == "expired"
            assert tuple(state.repo.connection.execute("SELECT digest_state,source_record_sha256,semantic_payload_sha256 FROM network_metadata_source_records").fetchone()) == ("expired", None, None)
            assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_sensitive_endpoints").fetchone()[0] == 0
            _a_rewind(state)
            assert state.repo.ingest_batch(items, state.run, state.health, state.anchor)["blocked"] == "replay_identity_evidence_expired"


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
