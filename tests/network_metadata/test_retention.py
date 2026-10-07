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
