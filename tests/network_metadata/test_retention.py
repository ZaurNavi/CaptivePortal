import pytest
from dataclasses import replace
from datetime import timedelta
from app.network_metadata.health import HealthController
from app.network_metadata.read_service import NetworkMetadataReadService
from app.network_metadata.validation import ni_format_utc
from app.network_metadata.retention import RetentionPolicy
from . import store, record, source_event, outcome, seed_blocked, SITE


@pytest.mark.parametrize("family", ["dns", "tls", "quic"])
@pytest.mark.parametrize("age", [timedelta(days=14) - timedelta(microseconds=1), timedelta(days=14),
    timedelta(days=14, microseconds=1), timedelta(days=30), timedelta(days=30, microseconds=1)])
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
        if age > timedelta(days=30):
            assert result["committed"] == 0 and state.health.last_ingested is None
            for suffix in ("observations", "source_records", "sensitive_endpoints", "dns", "tls", "quic",
                           "dns_queries", "dns_answers", "tls_alpn"):
                assert state.repo.connection.execute(f"SELECT count(*) FROM network_metadata_{suffix}").fetchone()[0] == 0
            assert tuple(state.repo.connection.execute("SELECT fault_category,count FROM network_metadata_ingest_fault_aggregates").fetchone()) == ("retention_expired_event", 1)
            end = ni_format_utc(state.clock() - timedelta(microseconds=1))
            assert NetworkMetadataReadService(state.config.db_path).list_observations(
                SITE, item.output_event_at, end)["items"] == []
        else:
            expired = age > timedelta(days=14)
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
        if age > timedelta(days=14):
            written = "\n".join(command for command in sql if command.startswith(("INSERT", "UPDATE")))
            for sensitive in ("ni-query-sentinel.example", "ni-sni-sentinel.example", "ni-quic-sentinel.example",
                              "203.0.113.93", "10.73.0.7", "2001:db8::93", item.normalized.source_record_sha256,
                              item.normalized.semantic_payload_sha256):
                assert sensitive not in written


@pytest.mark.parametrize("family", ["dns", "tls", "quic"])
def test_late_never_observed_sensitive_stays_not_observed(tmp_path, family):
    with store(tmp_path) as state:
        event = source_event(family, timestamp=ni_format_utc(state.clock() - timedelta(days=15)))
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


@pytest.mark.parametrize("age", [15, 31])
@pytest.mark.parametrize("disposition", ["duplicate_noop", "source_record_identity_conflict",
    "normalizer_determinism_conflict", "replay_identity_evidence_expired"])
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
        if age > 30:
            assert row is None
        else:
            for field in ("event_at", "ingested_at", "ingest_run_id", "source_health_ref"):
                assert row[field] == before[field]
            assert row["sensitive_endpoint_presence_state"] == "expired"
            assert tuple(state.repo.connection.execute("SELECT digest_state,source_record_sha256,semantic_payload_sha256 FROM network_metadata_source_records").fetchone()) == ("expired", None, None)


@pytest.mark.parametrize("family", ["dns", "tls", "quic"])
def test_sensitive_then_core_retention(tmp_path, family):
    data = record(source_event(family))
    with store(tmp_path, source=data + b"\n") as state:
        item = outcome(state.config.capture_scope_binding, data, generation=state.generation.source_generation_id)
        state.repo.ingest_batch([item], state.run, state.health, state.anchor)
        state.clock.advance(days=15)
        result = RetentionPolicy(state.repo).run()
        assert result["sensitive"] == 1 and result["core"] == 0
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_sensitive_endpoints").fetchone()[0] == 0
        assert tuple(state.repo.connection.execute("SELECT digest_state,source_record_sha256,semantic_payload_sha256 FROM network_metadata_source_records").fetchone()) == ("expired", None, None)
        payload = state.repo.connection.execute(f"SELECT * FROM network_metadata_{family}").fetchone()
        if family == "dns":
            assert payload["query_names_presence_state"] == payload["answer_values_presence_state"] == "expired"
            assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_dns_queries").fetchone()[0] == 0
        else:
            assert payload["sni"] is None and payload["sni_presence_state"] == "expired"
        state.clock.advance(days=16)
        assert RetentionPolicy(state.repo).run()["core"] == 1
        assert state.repo.connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert state.repo.load_active()[1].committed_byte_offset == item.end


def test_not_observed_does_not_turn_expired(tmp_path):
    event = source_event("tls")
    event["tls"]["sni"] = None
    data = record(event)
    with store(tmp_path, source=data + b"\n") as state:
        state.repo.ingest_batch([outcome(state.config.capture_scope_binding, data,
            generation=state.generation.source_generation_id)], state.run, state.health, state.anchor)
        state.clock.advance(days=15)
        RetentionPolicy(state.repo).run()
        assert state.repo.connection.execute("SELECT sni_presence_state FROM network_metadata_tls").fetchone()[0] == "not_observed"


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


def test_closed_lineage_90_days_and_active_preserved(tmp_path):
    with store(tmp_path) as state:
        old = state.generation.source_generation_id
        new, _ = state.repo.transition_generation(binding=state.config.capture_scope_binding, boot_id=state.generation.host_boot_id,
            physical=(state.generation.st_dev, state.generation.st_ino), close_reason="source_rotated_live")
        state.clock.advance(days=91)
        result = RetentionPolicy(state.repo).run()
        assert result["generations"] == 1
        assert state.repo.load_active()[0].source_generation_id == new.source_generation_id
        assert state.repo.connection.execute("SELECT source_generation_id FROM network_metadata_source_generations WHERE source_generation_id=?", (old,)).fetchone() is None


@pytest.mark.parametrize("fixture", ["all_full", "mixed", "all_empty", "small"])
def test_retention_global_nonempty_batch_budget_and_priority(tmp_path, monkeypatch, fixture):
    from app.network_metadata.models import RETENTION_MAX_BATCHES_PER_PASS, RETENTION_PARENT_BATCH_ROWS
    assert RETENTION_MAX_BATCHES_PER_PASS == 20 and RETENTION_PARENT_BATCH_ROWS == 5000
    classes = ("sensitive", "core", "health", "faults", "generations", "bindings", "runs")
    with store(tmp_path) as state:
        policy = RetentionPolicy(state.repo)
        probes, mutations, sql = [], [], []
        seen = dict.fromkeys(classes, 0)
        def select(category, cutoffs):
            assert not state.repo.connection.in_transaction
            assert tuple(cutoffs) == (14, 30, 45, 90)
            probes.append(category)
            index = seen[category]
            seen[category] += 1
            if fixture == "all_empty":
                return []
            if fixture == "small":
                return list(range(37)) if index == 0 else []
            if fixture == "mixed" and (
                    category == "sensitive" and index >= 2 or category == "core" and index >= 3):
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
        assert tuple(totals) == classes
        if fixture == "all_full":
            assert mutations == [("sensitive", 5000)] * 20
            assert probes == ["sensitive"] * 20
            assert totals == dict(zip(classes, [100000, 0, 0, 0, 0, 0, 0]))
        elif fixture == "mixed":
            assert mutations == [("sensitive", 5000)] * 2 + [("core", 5000)] * 3 + [("health", 5000)] * 15
            assert probes == ["sensitive"] * 3 + ["core"] * 4 + ["health"] * 15
            assert totals == dict(zip(classes, [10000, 15000, 75000, 0, 0, 0, 0]))
        elif fixture == "all_empty":
            assert not mutations and probes == list(classes)
            assert totals == dict.fromkeys(classes, 0)
        else:
            assert mutations == [(category, 37) for category in classes]
            assert probes == [category for category in classes for _ in range(2)]
            assert totals == dict.fromkeys(classes, 37)
        assert len(mutations) <= 20
        assert sql.count("BEGIN IMMEDIATE") == sql.count("COMMIT") == len(mutations)


# B-only fixtures: real file-backed schema/repository and disposable synthetic rows.
from contextlib import contextmanager
import json
import os
import sqlite3
import time
from types import SimpleNamespace
from . import configuration, Clock, BOOT, IDENTITY
from app.network_metadata.repository import NetworkMetadataRepository
from app.network_metadata.source import continuity_anchor
from app.network_metadata.canonical import observation_uuid, source_event_identity
from app.network_metadata.models import NetworkMetadataStorageUnavailable, NetworkMetadataStorageCorrupt
from app.network_metadata.schema import _signature, validate_schema


@contextmanager
def _b_store(tmp_path, *, a=False, b=True, source=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    config = configuration(tmp_path, NETWORK_METADATA_IO_HOTPATH_V1_ENABLED=str(a).lower(),
        NETWORK_METADATA_RETENTION_INDEXED_V1_ENABLED=str(b).lower())
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


def _b_cutoffs(state):
    return {days: ni_format_utc(state.clock() - timedelta(days=days)) for days in (14, 30, 45, 90)}


def _b_seed(state, times):
    """Bulk clone a real envelope; all V1 constraints/FKs remain enabled."""
    item = outcome(state.config.capture_scope_binding, generation=state.generation.source_generation_id)
    state.repo.ingest_batch([item], state.run, state.health, state.anchor)
    template = dict(state.repo.connection.execute("SELECT * FROM network_metadata_observations").fetchone())
    state.repo.connection.execute("DELETE FROM network_metadata_observations")
    rows, expected = [], []
    for index, (event, ingested, presence) in enumerate(times):
        identity = source_event_identity(state.generation.source_generation_id, index)
        observation = observation_uuid("dns", identity)
        row = {**template, "observation_id": observation, "source_event_identity": identity,
            "record_start_byte_offset": index, "event_at": event, "ingested_at": ingested,
            "sensitive_endpoint_presence_state": presence}
        rows.append(tuple(row.values()))
        expected.append((observation, event, ingested, presence))
    with state.repo.transaction():
        state.repo.connection.executemany("INSERT INTO network_metadata_observations (" +
            ",".join(template) + ") VALUES(" + ",".join("?" for _ in template) + ")", rows)
    return expected


def _b_expected(rows, kind, cutoffs):
    age = cutoffs[14 if kind == "sensitive" else 30]
    eligible = [row for row in rows if min(row[1:3]) < age and
        (kind == "core" or row[3] != "expired")]
    return [row[0] for row in sorted(eligible, key=lambda row: (min(row[1:3]), row[0]))]


@pytest.mark.parametrize("kind", ["sensitive", "core"])
@pytest.mark.parametrize("count", [0, 1, 5000, 5001, 20000])
def test_b_top_k_and_eventual_completeness_vs_legacy(tmp_path, kind, count):
    with _b_store(tmp_path) as state:
        now, age = state.clock(), 15 if kind == "sensitive" else 31
        def times():
            for i in range(count):
                old = ni_format_utc(now - timedelta(days=age, microseconds=(i * 17) % 971))
                fresh = ni_format_utc(now + timedelta(days=1))
                # Equal-age ties, both opposite clock orderings, overlapping streams.
                yield ((old, fresh) if i % 3 == 0 else (fresh, old) if i % 3 == 1 else (old, old)) + ("observed_retained",)
            yield (ni_format_utc(now), ni_format_utc(now), "not_observed")
        rows = _b_seed(state, times())
        policy, cutoffs = RetentionPolicy(state.repo), _b_cutoffs(state)
        expected = _b_expected(rows, kind, cutoffs)
        seen = []
        while True:
            sql = []
            state.repo.connection.set_trace_callback(sql.append)
            selected = policy._select(kind, cutoffs)
            state.repo.connection.set_trace_callback(None)
            selects = [s for s in sql if s.startswith("SELECT")]
            assert len(selects) == 2 and all("LIMIT 5000" in s for s in selects)
            branch_rows = [state.repo.connection.execute(s).fetchall() for s in selects]
            assert all(len(part) <= 5000 for part in branch_rows)
            assert sum(map(len, branch_rows)) <= 10000
            assert selected == expected[len(seen):len(seen) + 5000]
            if not selected:
                break
            assert len(selected) <= 5000 and len(set(selected)) == len(selected)
            seen.extend(selected)
            with state.repo.transaction():
                policy._delete(kind, selected)
        assert seen == expected and len(seen) == count
        assert state.repo.connection.execute("PRAGMA foreign_key_check").fetchall() == []
    # Same synthetic eligibility under the literal legacy SQL, not same order.
    with _b_store(tmp_path / "legacy", b=False) as legacy:
        legacy_rows = _b_seed(legacy, [row[1:] for row in rows])
        legacy_policy, seen = RetentionPolicy(legacy.repo), []
        while selected := legacy_policy._select(kind, cutoffs):
            seen.extend(selected)
            with legacy.repo.transaction():
                legacy_policy._delete(kind, selected)
        assert set(seen) == set(_b_expected(legacy_rows, kind, cutoffs))
        assert len(seen) == count


@pytest.mark.parametrize("kind", ["sensitive", "core"])
def test_b_strict_boundaries_mixed_presence_and_future(tmp_path, kind):
    with _b_store(tmp_path) as state:
        boundary = state.clock() - timedelta(days=14 if kind == "sensitive" else 30)
        times = []
        for presence in ("expired", "not_observed", "observed_retained"):
            for delta in (-1, 0, 1):
                timestamp = ni_format_utc(boundary + timedelta(microseconds=delta))
                future = ni_format_utc(state.clock() + timedelta(days=5))
                times.extend([(timestamp, future, presence), (future, timestamp, presence),
                    (timestamp, timestamp, presence)])
        rows = _b_seed(state, times)
        assert RetentionPolicy(state.repo)._select(kind, _b_cutoffs(state)) == _b_expected(rows, kind, _b_cutoffs(state))


@pytest.mark.parametrize("field", ["event_at", "ingested_at"])
@pytest.mark.parametrize("value", ["2026-08-01T00:00:00Z", "2026-08-01T00:00:00.000000+00:00",
    "2026-02-30T00:00:00.000000Z", "2026-08-01T00:00:00.000Z", "invalid", None])
def test_b_malformed_returned_timestamp_fails_closed(tmp_path, field, value):
    with _b_store(tmp_path) as state:
        old, fresh = "2026-08-01T00:00:00.000000Z", ni_format_utc(state.clock())
        _b_seed(state, [(old, fresh, "observed_retained")])
        # A NULL is excluded by the real NOT NULL schema, all others by selector.
        if value is None:
            with pytest.raises(sqlite3.IntegrityError):
                state.repo.connection.execute(f"UPDATE network_metadata_observations SET {field}=?", (value,))
            return
        state.repo.connection.execute(f"UPDATE network_metadata_observations SET {field}=?", (value,))
        # Force the other valid age field to qualify even if malformed text sorts late.
        other = "ingested_at" if field == "event_at" else "event_at"
        state.repo.connection.execute(f"UPDATE network_metadata_observations SET {other}=?", (old,))
        checkpoint = state.repo.load_active()
        before = list(state.repo.connection.execute("SELECT * FROM network_metadata_observations"))
        with pytest.raises(NetworkMetadataStorageCorrupt):
            RetentionPolicy(state.repo).run()
        assert list(state.repo.connection.execute("SELECT * FROM network_metadata_observations")) == before
        assert state.repo.load_active() == checkpoint
        assert not any(event == "retention_completed" for event, _ in state.events)


@pytest.mark.parametrize("failure", ["duplicate_tuple", "bad_identity", "ineligible", "sqlite_error", "interrupt"])
def test_b_selection_integrity_errors_never_mean_empty(failure):
    from app.network_metadata.models import NetworkMetadataConfig
    identity = observation_uuid("dns", "synthetic-b")
    old, newer = "2026-08-01T00:00:00.000000Z", "2026-08-02T00:00:00.000000Z"
    class Connection:
        calls = 0
        def execute(self, *_):
            self.calls += 1
            if failure == "sqlite_error":
                raise sqlite3.OperationalError("disposable denied query")
            if failure == "interrupt":
                raise sqlite3.OperationalError("interrupted")
            if failure == "bad_identity":
                return [(identity.upper(), old, old)]
            if failure == "ineligible":
                return [(identity, "2026-12-01T00:00:00.000000Z", old)]
            return [(identity, newer if self.calls == 2 else old, old)]
    repo = SimpleNamespace(config=NetworkMetadataConfig(retention_indexed_v1_enabled=True), connection=Connection())
    expected = NetworkMetadataStorageUnavailable if failure in {"sqlite_error", "interrupt"} else NetworkMetadataStorageCorrupt
    with pytest.raises(expected):
        RetentionPolicy(repo)._select("sensitive", {14: "2026-09-01T00:00:00.000000Z"})


@pytest.mark.parametrize("a,b", [(False, False), (True, False), (False, True), (True, True)])
@pytest.mark.parametrize("family", ["dns", "tls", "quic"])
def test_b_ab_lineage_cascade_schema_and_replay(tmp_path, a, b, family):
    data = record(source_event(family))
    with _b_store(tmp_path, a=a, b=b, source=data + b"\n") as state:
        item = outcome(state.config.capture_scope_binding, data, generation=state.generation.source_generation_id)
        state.repo.ingest_batch([item], state.run, state.health, state.anchor)
        signature = _signature(state.repo.connection)
        checkpoint = state.repo.load_active()
        assert state.repo.connection.execute(
            "SELECT configuration_digest FROM network_metadata_ingest_runs WHERE ingest_run_id=?",
            (state.run,)).fetchone()[0] == state.config.configuration_digest
        for pragma, expected in (("journal_mode", "wal"), ("synchronous", 2), ("foreign_keys", 1), ("user_version", 1)):
            assert state.repo.connection.execute("PRAGMA " + pragma).fetchone()[0] == expected
        state.clock.advance(days=15)
        policy = RetentionPolicy(state.repo)
        assert policy.run()["sensitive"] == 1
        assert tuple(state.repo.connection.execute("SELECT digest_state,source_record_sha256,semantic_payload_sha256 FROM network_metadata_source_records").fetchone()) == ("expired", None, None)
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_sensitive_endpoints").fetchone()[0] == 0
        assert state.repo.load_active() == checkpoint
        # Retention has not advanced replay authority; expired evidence still blocks replay.
        with state.repo.transaction():
            state.repo.connection.execute("UPDATE network_metadata_checkpoint SET committed_byte_offset=0,continuity_anchor_start_offset=0,continuity_anchor_length=0,continuity_anchor_sha256=NULL")
            state.repo.connection.execute("UPDATE network_metadata_source_generations SET committed_byte_offset=0")
        assert state.repo.ingest_batch([item], state.run, state.health, state.anchor)["blocked"] == "replay_identity_evidence_expired"
        blocked = state.repo.load_active()
        state.clock.advance(days=16)
        assert policy.run()["core"] == 1
        for suffix in ("observations", "source_records", "sensitive_endpoints", "dns", "dns_queries", "dns_answers", "tls", "tls_alpn", "quic"):
            assert state.repo.connection.execute(f"SELECT count(*) FROM network_metadata_{suffix}").fetchone()[0] == 0
        assert state.repo.load_active() == blocked
        state.repo.recover()
        assert state.repo.load_active() == blocked
        assert _signature(state.repo.connection) == signature
        validate_schema(state.repo.connection)
        assert state.repo.connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_b_actual_global_twenty_batch_budget_no_source_read(tmp_path, monkeypatch):
    with _b_store(tmp_path) as state:
        old = ni_format_utc(state.clock() - timedelta(days=15))
        _b_seed(state, [(old, old, "observed_retained")] * 100001)
        checkpoint = state.repo.load_active()
        # No dependency on available source at retention time; never reopen/read it.
        os.unlink(state.config.source_path)
        policy, lengths, sql = RetentionPolicy(state.repo), [], []
        original = policy._delete
        def delete(kind, ids):
            assert state.repo.connection.in_transaction
            lengths.append((kind, len(ids)))
            original(kind, ids)
        monkeypatch.setattr(policy, "_delete", delete)
        state.repo.connection.set_trace_callback(sql.append)
        result = policy.run()
        state.repo.connection.set_trace_callback(None)
        assert result["sensitive"] == 100000 and sum(result.values()) == 100000
        assert lengths == [("sensitive", 5000)] * 20
        assert sql.count("BEGIN IMMEDIATE") == sql.count("COMMIT") == 20
        assert state.repo.load_active() == checkpoint
        assert policy.run()["sensitive"] == 1


def test_b_capacity_stops_before_select_or_success(tmp_path, monkeypatch):
    with _b_store(tmp_path) as state:
        policy, checkpoint = RetentionPolicy(state.repo), state.repo.load_active()
        monkeypatch.setattr(state.repo, "footprint", lambda: {"combined": state.config.max_db_bytes})
        monkeypatch.setattr(policy, "_select", lambda *_: pytest.fail("no selection under capacity pressure"))
        assert sum(policy.run().values()) == 0
        assert state.repo.load_active() == checkpoint
        assert not state.repo.connection.in_transaction
        assert not any(event == "retention_completed" for event, _ in state.events)


def test_b_reader_snapshot_wal_and_atomic_delete_failure(tmp_path):
    with _b_store(tmp_path) as state:
        item = outcome(state.config.capture_scope_binding, generation=state.generation.source_generation_id)
        state.repo.ingest_batch([item], state.run, state.health, state.anchor)
        checkpoint = state.repo.load_active()
        state.clock.advance(days=15)
        with sqlite3.connect(f"file:{state.config.db_path}?mode=ro", uri=True, isolation_level=None) as reader:
            reader.execute("BEGIN")
            assert reader.execute("SELECT sensitive_endpoint_presence_state FROM network_metadata_observations").fetchone()[0] == "observed_retained"
            # Failure after sensitive child DELETE must roll back the whole batch.
            def deny_update(action, table, *_):
                return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_UPDATE and table == "network_metadata_observations" else sqlite3.SQLITE_OK
            state.repo.connection.set_authorizer(deny_update)
            try:
                with pytest.raises(NetworkMetadataStorageUnavailable):
                    RetentionPolicy(state.repo).run()
            finally:
                state.repo.connection.set_authorizer(lambda *_: sqlite3.SQLITE_OK)
            assert not state.repo.connection.in_transaction
            assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_sensitive_endpoints").fetchone()[0] == 1
            assert state.repo.load_active() == checkpoint
            assert not any(event == "retention_completed" for event, _ in state.events)
            assert RetentionPolicy(state.repo).run()["sensitive"] == 1
            assert reader.execute("SELECT sensitive_endpoint_presence_state FROM network_metadata_observations").fetchone()[0] == "observed_retained"
            reader.execute("COMMIT")
            assert reader.execute("SELECT sensitive_endpoint_presence_state FROM network_metadata_observations").fetchone()[0] == "expired"
        assert state.repo.load_active() == checkpoint


@pytest.mark.parametrize("kind", ["sensitive", "core"])
def test_b_explain_actual_queries_and_expired_heavy_prefix(tmp_path, kind, record_property):
    measurements = []
    for prefix in (0, 100000):
        with _b_store(tmp_path / str(prefix)) as state:
            now = state.clock()
            def times():
                for i in range(prefix):
                    old = ni_format_utc(now - timedelta(days=60, microseconds=prefix - i))
                    yield old, old, "expired"
                for i in range(5001):
                    old = ni_format_utc(now - timedelta(days=31, microseconds=5001 - i))
                    yield old, old, "observed_retained"
            rows = _b_seed(state, times())
            state.repo.connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            cutoffs, policy, sql, steps = _b_cutoffs(state), RetentionPolicy(state.repo), [], [0]
            def progress():
                steps[0] += 1000
                return 0
            state.repo.connection.set_trace_callback(sql.append)
            state.repo.connection.set_progress_handler(progress, 1000)
            start = time.perf_counter()
            try:
                selected = policy._select(kind, cutoffs)
            finally:
                elapsed = time.perf_counter() - start
                state.repo.connection.set_progress_handler(None, 0)
                state.repo.connection.set_trace_callback(None)
            assert selected == _b_expected(rows, kind, cutoffs)[:5000]
            assert len(sql) == 2
            plans = []
            for query, field in zip(sql, ("event", "ingested")):
                plan = [row[3] for row in state.repo.connection.execute("EXPLAIN QUERY PLAN " + query)]
                assert any("SEARCH" in detail and "idx_nm_observations_" + field in detail for detail in plan)
                assert not any("SCAN" in detail or "TEMP B-TREE" in detail for detail in plan)
                assert len(state.repo.connection.execute(query).fetchall()) == 5000
                plans.append(plan)
            extra = " AND sensitive_endpoint_presence_state!='expired'" if kind == "sensitive" else ""
            age = cutoffs[14 if kind == "sensitive" else 30]
            legacy_plan = [row[3] for row in state.repo.connection.execute(
                "EXPLAIN QUERY PLAN SELECT observation_id FROM network_metadata_observations WHERE (event_at<? OR ingested_at<?)" + extra +
                " ORDER BY observation_id LIMIT 5000", (age, age))]
            measurements.append(dict(kind=kind, expired_prefix_rows=prefix, eligible_tail_rows=5001,
                returned_unique=len(selected), sql_vm_steps_lower_bound=steps[0], elapsed_seconds=elapsed,
                main_db_bytes=state.repo.footprint()["main"], plans=plans, legacy_plan=legacy_plan))
    if kind == "sensitive":
        assert measurements[1]["sql_vm_steps_lower_bound"] > measurements[0]["sql_vm_steps_lower_bound"] * 5
    report = dict(measurements=measurements, status="B_ACTIVATION_HOLD_EXPIRED_PREFIX",
        limitation="VM steps/one local latency sample are not physical page reads or independent performance acceptance")
    record_property("b_expired_prefix_evidence", json.dumps(report, sort_keys=True))
    print("B_EXPIRED_PREFIX=" + json.dumps(report, sort_keys=True))


def test_b_off_sql_and_other_classes_remain_literal_legacy(tmp_path):
    with _b_store(tmp_path, b=False) as state:
        policy, sql, cutoffs = RetentionPolicy(state.repo), [], _b_cutoffs(state)
        state.repo.connection.set_trace_callback(sql.append)
        policy._select("sensitive", cutoffs)
        state.repo.connection.set_trace_callback(None)
        assert len(sql) == 1
        assert "WHERE (event_at<" in sql[0] and " OR ingested_at<" in sql[0]
        assert " ORDER BY observation_id LIMIT 5000" in sql[0]
        for kind in ("health", "faults", "generations", "bindings", "runs"):
            traces = []
            for enabled in (False, True):
                state.repo.config = replace(state.config, retention_indexed_v1_enabled=enabled)
                commands = []
                state.repo.connection.set_trace_callback(commands.append)
                result = policy._select(kind, cutoffs)
                state.repo.connection.set_trace_callback(None)
                traces.append((commands, result))
            assert traces[0] == traces[1]
