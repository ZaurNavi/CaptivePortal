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


def _b_r3_expected(rows, kind, cutoffs):
    expected = _b_expected(rows, kind, cutoffs)
    fallback = False
    if kind == "sensitive":
        for field in (1, 2):
            prefix = sorted((row for row in rows if row[field] < cutoffs[14]),
                key=lambda row: (row[field], row[0]))[:5000]
            if any(row[3] == "expired" for row in prefix):
                fallback = True
                break
    return (sorted(expected) if fallback else expected)[:5000], fallback


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
        remaining = rows[:]
        seen = []
        while True:
            sql = []
            state.repo.connection.set_trace_callback(sql.append)
            selected = policy._select(kind, cutoffs)
            state.repo.connection.set_trace_callback(None)
            selects = [s for s in sql if s.startswith("SELECT")]
            wanted, fallback = _b_r3_expected(remaining, kind, cutoffs)
            assert len(selects) in ((2, 3) if fallback else (2,))
            assert all("LIMIT 5000" in s for s in selects)
            if fallback:
                assert sum("SELECT observation_id FROM" in s for s in selects) == 1
            branch_rows = [state.repo.connection.execute(s).fetchall() for s in selects]
            assert all(len(part) <= 5000 for part in branch_rows)
            assert sum(len(part) for s, part in zip(selects, branch_rows)
                if "SELECT observation_id FROM" not in s) <= 10000
            assert selected == wanted
            if not selected:
                break
            assert len(selected) <= 5000 and len(set(selected)) == len(selected)
            seen.extend(selected)
            with state.repo.transaction():
                policy._delete(kind, selected)
            chosen = set(selected)
            remaining = [(row[0], row[1], row[2], "expired") if row[0] in chosen else row
                for row in remaining] if kind == "sensitive" else [row for row in remaining if row[0] not in chosen]
        assert set(seen) == set(expected) and len(seen) == count
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
        wanted, fallback = _b_r3_expected(rows, kind, _b_cutoffs(state))
        assert fallback is (kind == "sensitive")
        assert RetentionPolicy(state.repo)._select(kind, _b_cutoffs(state)) == wanted


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
        RetentionPolicy(repo)._select("core", {30: "2026-09-01T00:00:00.000000Z"})


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
            wanted, fallback = _b_r3_expected(rows, kind, cutoffs)
            assert selected == wanted
            assert len(sql) == 2
            plans = []
            for query, field in zip(sql, ("event", "ingested")):
                plan = [row[3] for row in state.repo.connection.execute("EXPLAIN QUERY PLAN " + query)]
                if fallback and "SELECT observation_id FROM" in query:
                    assert any("SCAN" in detail and "sqlite_autoindex_network_metadata_observations_1" in detail for detail in plan)
                else:
                    assert any("SEARCH" in detail and "idx_nm_observations_" + field in detail for detail in plan)
                    assert not any("SCAN" in detail or "TEMP B-TREE" in detail for detail in plan)
                assert not (fallback and "SELECT observation_id,event_at" in query and "!='expired'" in query)
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
    report = dict(measurements=measurements, status="B_ACTIVATION_HOLD_INDEPENDENT_REVIEW",
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


class _R3MeasuredConnection:
    """Observe real cursor consumption and complete SQL VM cost, not disk IOPS."""
    def __init__(self, connection):
        self.connection = connection
        self.calls = []
        self.active = []

    def execute(self, sql, parameters):
        stats = dict(sql=sql, parameters=list(parameters), visited=0, vm_steps_lower_bound=0,
            closed=False, elapsed_seconds=0.0)
        self.calls.append(stats)
        def progress():
            stats["vm_steps_lower_bound"] += 100
            return 0
        self.connection.set_progress_handler(progress, 100)
        start = time.perf_counter()
        real = self.connection.execute(sql, parameters)
        owner = self
        class Cursor:
            def __iter__(self):
                return self
            def __next__(self):
                try:
                    row = next(real)
                except StopIteration:
                    stats["elapsed_seconds"] = time.perf_counter() - start
                    owner.connection.set_progress_handler(None, 0)
                    raise
                stats["visited"] += 1
                return row
            def close(self):
                real.close()
                owner.connection.set_progress_handler(None, 0)
                stats["closed"] = True
                if not stats["elapsed_seconds"]:
                    stats["elapsed_seconds"] = time.perf_counter() - start
        cursor = Cursor()
        self.active.append(cursor)
        return cursor

    def close_all(self):
        for cursor, stats in zip(self.active, self.calls):
            if not stats["closed"]:
                cursor.close()


def _r3_select(state, *, kind="sensitive", policy_type=RetentionPolicy, b=True):
    real, config = state.repo.connection, state.repo.config
    measured = _R3MeasuredConnection(real)
    state.repo.connection = measured
    state.repo.config = replace(config, retention_indexed_v1_enabled=b)
    try:
        started = time.perf_counter()
        selected = policy_type(state.repo)._select(kind, _b_cutoffs(state))
        elapsed = time.perf_counter() - started
        # Capture lifecycle before instrumentation cleans up untouched legacy/R2 cursors.
        closed = [call["closed"] for call in measured.calls]
    finally:
        measured.close_all()
        state.repo.connection, state.repo.config = real, config
    return selected, measured.calls, elapsed, closed


@pytest.mark.parametrize("branch", ["event_at", "ingested_at"])
@pytest.mark.parametrize("position", [0, 2499, 4999])
def test_b_r3_lazy_single_fallback_positions(tmp_path, branch, position):
    with _b_store(tmp_path) as state:
        def times():
            for i in range(5000):
                old = ni_format_utc(state.clock() - timedelta(days=15, microseconds=5000 - i))
                future = ni_format_utc(state.clock() + timedelta(days=1))
                pair = (old, future) if branch == "event_at" else (future, old)
                yield pair + ("expired" if i == position else "not_observed" if i % 2 else "observed_retained",)
        rows = _b_seed(state, times())
        selected, calls, _, closed = _r3_select(state)
        legacy, _, _, _ = _r3_select(state, b=False)
        assert selected == legacy == sorted(_b_expected(rows, "sensitive", _b_cutoffs(state)))
        assert all(closed)
        raw = [call for call in calls if "SELECT observation_id,event_at" in call["sql"]]
        assert len(raw) == (1 if branch == "event_at" else 2)
        assert raw[-1]["visited"] == position + 1
        if branch == "ingested_at":
            assert raw[0]["visited"] == 0
        assert len(calls) == len(raw) + 1
        assert calls[-1]["sql"] == (
            "SELECT observation_id FROM network_metadata_observations WHERE (event_at<? OR ingested_at<?)"
            " AND sensitive_endpoint_presence_state!='expired' ORDER BY observation_id LIMIT 5000")
        assert calls[-1]["parameters"] == [_b_cutoffs(state)[14]] * 2
        assert all("!='expired'" not in call["sql"] for call in raw)


def test_b_r3_expired_after_cap_not_seen_and_both_raw_index_plans(tmp_path):
    with _b_store(tmp_path) as state:
        times = [(ni_format_utc(state.clock() - timedelta(days=15, microseconds=5001 - i)),) * 2 +
            ("expired" if i == 5000 else "not_observed",) for i in range(5001)]
        rows = _b_seed(state, times)
        selected, calls, _, closed = _r3_select(state)
        assert selected == _b_expected(rows, "sensitive", _b_cutoffs(state))[:5000]
        assert len(calls) == 2 and all(closed)
        assert [call["visited"] for call in calls] == [5000, 5000]
        for call, field in zip(calls, ("event", "ingested")):
            plans = [row[3] for row in state.repo.connection.execute(
                "EXPLAIN QUERY PLAN " + call["sql"], call["parameters"])]
            assert any("SEARCH" in plan and "idx_nm_observations_" + field in plan for plan in plans)
            assert not any("SCAN" in plan or "TEMP B-TREE" in plan for plan in plans)


@pytest.mark.parametrize("fault", ["id", "version", "event", "ingested", "ineligible",
    "state", "null", "bool", "duplicate_time", "duplicate_state"])
@pytest.mark.parametrize("branch", [0, 1])
def test_b_r3_corruption_closes_cursor_no_fallback(fault, branch):
    import uuid
    identity = observation_uuid("dns", "r3-negative")
    old = "2026-08-01T00:00:00.000000Z"
    valid = (identity, old, old, "observed_retained")
    invalid = list(valid)
    invalid[3] = "expired"  # Validation must precede accepting this trigger.
    if fault == "id":
        invalid[0] = identity.upper()
    elif fault == "version":
        invalid[0] = str(uuid.uuid4())
    elif fault == "event":
        invalid[1] = "2026-08-01T00:00:00Z"
    elif fault == "ingested":
        invalid[2] = "2026-08-01T00:00:00.000Z"
    elif fault == "ineligible":
        invalid[1 + branch] = "2026-12-01T00:00:00.000000Z"
    elif fault in {"state", "null", "bool"}:
        invalid[3] = {"state": "other", "null": None, "bool": True}[fault]
    elif fault == "duplicate_time":
        invalid[1] = "2026-08-02T00:00:00.000000Z"
    class Cursor:
        def __init__(self, rows):
            self.rows, self.visited, self.closed = iter(rows), 0, False
        def __iter__(self):
            return self
        def __next__(self):
            self.visited += 1
            return next(self.rows)
        def close(self):
            self.closed = True
    class Connection:
        def __init__(self):
            self.cursors, self.sql = [], []
        def execute(self, sql, _):
            assert all(cursor.closed for cursor in self.cursors)
            self.sql.append(sql)
            assert "SELECT observation_id FROM" not in sql, "corruption must not fallback"
            index = len(self.sql) - 1
            if fault.startswith("duplicate"):
                data = [valid, tuple(invalid)] if branch == 0 else [valid] if index == 0 else [tuple(invalid)]
            else:
                data = [tuple(invalid)] if index == branch else []
            cursor = Cursor(data)
            self.cursors.append(cursor)
            return cursor
    connection = Connection()
    repo = SimpleNamespace(connection=connection, config=SimpleNamespace(retention_indexed_v1_enabled=True))
    with pytest.raises(NetworkMetadataStorageCorrupt):
        RetentionPolicy(repo)._select("sensitive", {14: "2026-09-01T00:00:00.000000Z"})
    assert all(cursor.closed for cursor in connection.cursors)
    assert len(connection.sql) <= 2


@pytest.mark.parametrize("where", ["event", "ingested", "fallback"])
@pytest.mark.parametrize("phase", ["execute", "iterate", "interrupt", "close"])
def test_b_r3_sqlite_errors_close_without_retry_or_fallback(where, phase):
    identity, old = observation_uuid("dns", "r3-sqlite"), "2026-08-01T00:00:00.000000Z"
    class Cursor:
        def __init__(self, data, fail):
            self.data, self.fail, self.closed = iter(data), fail, False
        def __iter__(self):
            return self
        def __next__(self):
            if self.fail and phase in {"iterate", "interrupt"}:
                raise sqlite3.OperationalError("interrupted" if phase == "interrupt" else "disposable failure")
            return next(self.data)
        def close(self):
            self.closed = True
            if self.fail and phase == "close":
                raise sqlite3.OperationalError("disposable close failure")
    class Connection:
        def __init__(self):
            self.cursors, self.queries = [], []
        def execute(self, sql, _):
            assert all(cursor.closed for cursor in self.cursors)
            label = "fallback" if "SELECT observation_id FROM" in sql else "event" if "WHERE event_at" in sql else "ingested"
            self.queries.append(label)
            fail = label == where
            if fail and phase == "execute":
                raise sqlite3.OperationalError("disposable open failure")
            data = [(identity, old, old, "expired")] if where == "fallback" and label == "event" else []
            cursor = Cursor(data, fail)
            self.cursors.append(cursor)
            return cursor
    connection = Connection()
    repo = SimpleNamespace(connection=connection, config=SimpleNamespace(retention_indexed_v1_enabled=True))
    with pytest.raises(NetworkMetadataStorageUnavailable):
        RetentionPolicy(repo)._select("sensitive", {14: "2026-09-01T00:00:00.000000Z"})
    assert all(cursor.closed for cursor in connection.cursors)
    assert connection.queries == (["event"] if where == "event" else ["event", "ingested"] if where == "ingested" else ["event", "fallback"])


def test_b_r3_fallback_invalid_id_is_corruption_and_cursor_closed():
    identity, old = observation_uuid("dns", "r3-legacy-invalid"), "2026-08-01T00:00:00.000000Z"
    cursors = []
    class Cursor:
        def __init__(self, data):
            self.data, self.closed = iter(data), False
        def __iter__(self):
            return self
        def __next__(self):
            return next(self.data)
        def close(self):
            self.closed = True
    class Connection:
        def execute(self, sql, _):
            assert all(cursor.closed for cursor in cursors)
            cursor = Cursor([(identity, old, old, "expired")] if not cursors else [(identity.upper(),)])
            cursors.append(cursor)
            return cursor
    repo = SimpleNamespace(connection=Connection(), config=SimpleNamespace(retention_indexed_v1_enabled=True))
    with pytest.raises(NetworkMetadataStorageCorrupt):
        RetentionPolicy(repo)._select("sensitive", {14: "2026-09-01T00:00:00.000000Z"})
    assert len(cursors) == 2 and all(cursor.closed for cursor in cursors)


@pytest.mark.parametrize("distribution", ["all_eligible", "interleaved", "expired_prefix"])
def test_b_r3_complete_legacy_fallback_cost_comparison(tmp_path, distribution, record_property):
    import subprocess
    previous = "166a1546c96cdfc09b624b614b6b0080c425a3d3"
    source = subprocess.check_output(["git", "show", previous + ":app/network_metadata/retention.py"])
    namespace = {"__name__": "app.network_metadata._r2_evidence", "__package__": "app.network_metadata"}
    exec(compile(source, previous + "/retention.py", "exec"), namespace)
    r2 = namespace["RetentionPolicy"]
    with _b_store(tmp_path) as state:
        def times():
            if distribution == "expired_prefix":
                for i in range(100000):
                    old = ni_format_utc(state.clock() - timedelta(days=60, microseconds=100000 - i))
                    yield old, old, "expired"
                count = 5001
            else:
                count = 20000
            for i in range(count):
                old = ni_format_utc(state.clock() - timedelta(days=31, microseconds=count - i))
                yield old, old, "expired" if distribution == "interleaved" and i % 2 == 0 else "observed_retained"
        rows = _b_seed(state, times())
        state.repo.connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        records = []
        # Fresh SQLite connection, then immediate same-connection warm repetition.
        # Identical immutable DB; deterministic three rounds. No OS cache flush claims.
        orders = [("legacy", "r2", "r3"), ("r3", "legacy", "r2"), ("r2", "r3", "legacy")]
        for round_index, order in enumerate(orders):
            for mode in order:
                # Reopen connection via existing recovery; OS cache may remain warm.
                state.repo.recover()
                for cache in ("fresh_connection", "warm_connection"):
                    selected, calls, elapsed, closed = _r3_select(state,
                        policy_type=r2 if mode == "r2" else RetentionPolicy, b=mode != "legacy")
                    expected = _b_expected(rows, "sensitive", _b_cutoffs(state))
                    if mode == "legacy" or (mode == "r3" and distribution != "all_eligible"):
                        assert selected == sorted(expected)[:5000]
                    else:
                        assert selected == expected[:5000]
                    fallback = [call for call in calls if "SELECT observation_id FROM" in call["sql"]]
                    if mode == "r3":
                        assert all(closed)
                        assert len(fallback) == (0 if distribution == "all_eligible" else 1)
                        assert [call["visited"] for call in calls if "SELECT observation_id,event_at" in call["sql"]] == ([5000, 5000] if distribution == "all_eligible" else [1])
                    for call in calls:
                        call["plan"] = [row[3] for row in state.repo.connection.execute(
                            "EXPLAIN QUERY PLAN " + call["sql"], call["parameters"])]
                    records.append(dict(mode=mode, cache=cache, round=round_index, order=list(order), elapsed_seconds=elapsed,
                        sql_vm_steps_lower_bound=sum(call["vm_steps_lower_bound"] for call in calls), calls=calls))
        import statistics
        summary = {mode: dict(median_seconds=statistics.median(row["elapsed_seconds"] for row in records if row["mode"] == mode),
            vm_steps=[row["sql_vm_steps_lower_bound"] for row in records if row["mode"] == mode]) for mode in ("legacy", "r2", "r3")}
        report = dict(distribution=distribution, r2_source_commit=previous, measurements=records, summary=summary,
            method="3 ordered rounds, fresh SQLite connection then immediate same-connection warm repetition; shared file-backed V1 DB, OS cache not flushed and cold-disk performance NOT established; SQL progress every 100 VM steps; no physical I/O claim")
        print("R3_COMPLETE_COST=" + json.dumps(report, sort_keys=True))
        record_property("r3_complete_cost", json.dumps(report, sort_keys=True))
        # Stable finite cleanup includes the entire repeated legacy fallback, with real writes.
        started, pass_measurements, checkpoint = time.perf_counter(), [], state.repo.load_active()
        policy = RetentionPolicy(state.repo)
        seen = []
        while True:
            selected, calls, elapsed, closed = _r3_select(state)
            assert all(closed)
            pass_measurements.append(dict(selected=len(selected), elapsed_seconds=elapsed,
                sql_vm_steps_lower_bound=sum(call["vm_steps_lower_bound"] for call in calls), calls=calls))
            if not selected:
                break
            wanted, _ = _b_r3_expected(rows, "sensitive", _b_cutoffs(state))
            assert selected == wanted and len(selected) <= 5000
            seen.extend(selected)
            with state.repo.transaction():
                policy._delete("sensitive", selected)
            chosen = set(selected)
            rows = [(row[0], row[1], row[2], "expired") if row[0] in chosen else row for row in rows]
        assert len(seen) == len(set(seen)) == len(expected)
        assert set(seen) == set(expected)
        assert state.repo.load_active() == checkpoint
        assert state.repo.connection.execute("PRAGMA foreign_key_check").fetchall() == []
        print("R3_STABLE_CATCHUP=" + json.dumps(dict(distribution=distribution, eligible=len(expected),
            batches=(len(expected) + 4999) // 5000, elapsed_seconds=time.perf_counter() - started,
            selections=pass_measurements, total_selection_vm_steps=sum(row["sql_vm_steps_lower_bound"] for row in pass_measurements))))
