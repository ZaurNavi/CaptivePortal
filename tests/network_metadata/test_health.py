from datetime import timedelta
from types import SimpleNamespace
import pytest
from app.network_metadata.health import FingerprintCaptureHealthAdapterV1, HealthController
from app.network_metadata.models import RecordOutcome
from app.network_metadata.validation import ni_format_utc
from app.device_fingerprint.validation import format_utc
from . import Clock, configuration, store, outcome, record, source_event


class Reader:
    def __init__(self, rows):
        self.rows, self.calls = rows, []

    def latest_source_health(self, site, capture, kind, *, through_utc):
        self.calls.append((site, capture, kind, through_utc))
        if isinstance(self.rows, Exception):
            raise self.rows
        return self.rows.get(kind)


@pytest.mark.parametrize("statuses,ages,expected", [(("available", "available"), (0, 600), "usable"),
    (("available", "available"), (601, 900), "stale"), (("available", "available"), (0, 601), "unknown"),
    (("available", "available"), (-1, 0), "unknown"), (("available", None), (0, 0), "unknown"),
    (("unsupported", "available"), (0, 0), "unknown")])
def test_capture_projection(tmp_path, statuses, ages, expected):
    clock = Clock()
    rows = {kind: dict(observed_at=format_utc(clock() - timedelta(seconds=age)), status=status, reason_code=None)
            for kind, status, age in zip(("tls_client", "quic_client"), statuses, ages) if status is not None}
    reader = Reader(rows)
    adapter = FingerprintCaptureHealthAdapterV1(reader=reader)
    assert adapter.evaluate(configuration(tmp_path).capture_scope_binding, clock())[0] == expected
    assert len(reader.calls) == 2


@pytest.mark.parametrize("reason,expected", [("suricata_unavailable", "unavailable"), ("raw_parser_unavailable", "unavailable"),
    ("eve_datagram_truncated", "unavailable"), ("capture_interface_unavailable", "unavailable"),
    ("ingest_delivery_unavailable", "unknown")])
def test_capture_acquisition_only(tmp_path, reason, expected):
    clock = Clock()
    row = dict(observed_at=format_utc(clock()), status="unavailable", reason_code=reason)
    adapter = FingerprintCaptureHealthAdapterV1(reader=Reader({"tls_client": row}))
    assert adapter.evaluate(configuration(tmp_path).capture_scope_binding, clock())[0] == expected


def test_capture_failure_is_safe(tmp_path):
    adapter = FingerprintCaptureHealthAdapterV1(reader=Reader(RuntimeError("secret")))
    assert adapter.evaluate(configuration(tmp_path).capture_scope_binding, Clock()()) == ("unknown", ("capture_health_read_unavailable",))


def test_capture_constructor_failure_is_unknown(tmp_path, monkeypatch):
    from app.network_metadata import health
    monkeypatch.setattr(health, "DeviceFingerprintReadService", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("private")))
    adapter = FingerprintCaptureHealthAdapterV1()
    assert adapter.evaluate(configuration(tmp_path).capture_scope_binding, Clock()()) == ("unknown", ("capture_health_read_unavailable",))


def test_health_not_per_observation_and_heartbeat(tmp_path):
    data = record()
    with store(tmp_path, source=(data + b"\n") * 2) as state:
        first = outcome(state.config.capture_scope_binding, data, generation=state.generation.source_generation_id)
        second = outcome(state.config.capture_scope_binding, data, start=first.end, generation=state.generation.source_generation_id)
        before = state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_health").fetchone()[0]
        state.repo.ingest_batch([first, second], state.run, state.health, state.anchor)
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_health").fetchone()[0] == before
        state.clock.advance(seconds=60)
        state.repo.persist_health(state.health, state.repo.load_active()[0])
        row = state.repo.latest_health()
        assert row["last_ingested_event_at"] == first.normalized.event_at
        assert row["committed_byte_offset"] == second.end


def test_fault_transition_source_order_and_clean_interval_recovery(tmp_path):
    with store(tmp_path, source=b"x\n" + record() + b"\n") as state:
        from app.network_metadata.models import RecordOutcome
        from app.network_metadata.canonical import sha256
        fault = RecordOutcome(0, 2, 1, "invalid_json", source_record_sha256=sha256(b"x"))
        item = outcome(state.config.capture_scope_binding, start=2, generation=state.generation.source_generation_id)
        state.repo.ingest_batch([fault, item], state.run, state.health, state.anchor)
        health_ref = state.repo.connection.execute("SELECT source_health_ref FROM network_metadata_observations").fetchone()[0]
        assert state.repo.connection.execute("SELECT metadata_ingest_health FROM network_metadata_source_health WHERE health_id=?", (health_ref,)).fetchone()[0] == "partial"
        state.health.heartbeat(source_available=True)
        assert state.health.ingest == "partial"
        state.health.heartbeat(source_available=True)
        assert state.health.ingest == "usable"


def test_newer_then_older_commits_never_regress_health_after_reload(tmp_path):
    with store(tmp_path) as state:
        newer = ni_format_utc(state.clock() + timedelta(seconds=1))
        older = ni_format_utc(state.clock() - timedelta(days=1))
        first_data = record(source_event(timestamp=newer))
        second_data = record(source_event(timestamp=older))
        (tmp_path / "source.jsonl").write_bytes(first_data + b"\n" + second_data + b"\n")
        first = outcome(state.config.capture_scope_binding, first_data, generation=state.generation.source_generation_id)
        second = outcome(state.config.capture_scope_binding, second_data, start=first.end, generation=state.generation.source_generation_id)
        state.repo.ingest_batch([first], state.run, state.health, state.anchor)
        state.clock.advance(seconds=60)
        state.repo.persist_health(state.health, state.repo.load_active()[0])
        reloaded = HealthController(state.config.capture_scope_binding.capture_source_id)
        reloaded.reload(state.repo)
        reloaded.source_available()
        assert reloaded.last_output == reloaded.last_ingested == newer
        state.repo.ingest_batch([second], state.run, reloaded, state.anchor)
        assert reloaded.last_output == reloaded.last_ingested == newer
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_observations").fetchone()[0] == 2
        again = HealthController(state.config.capture_scope_binding.capture_source_id)
        again.reload(state.repo)
        assert again.last_output == again.last_ingested == newer


@pytest.mark.parametrize("disposition", ["duplicate_noop", "source_record_identity_conflict",
    "normalizer_determinism_conflict", "replay_identity_evidence_expired"])
def test_replay_output_and_ingest_separation_after_reload(tmp_path, disposition):
    with store(tmp_path) as state:
        original_data = record(source_event(timestamp=ni_format_utc(state.clock() - timedelta(days=1))))
        (tmp_path / "source.jsonl").write_bytes(original_data + b"\n")
        first = outcome(state.config.capture_scope_binding, original_data, generation=state.generation.source_generation_id)
        state.repo.ingest_batch([first], state.run, state.health, state.anchor)
        state.clock.advance(seconds=60)
        state.repo.persist_health(state.health, state.repo.load_active()[0])
        ingested = state.health.last_ingested
        incoming = first
        if disposition != "duplicate_noop":
            incoming_data = record(source_event(timestamp=ni_format_utc(state.clock())))
            incoming = outcome(state.config.capture_scope_binding, incoming_data, generation=state.generation.source_generation_id)
            (tmp_path / "source.jsonl").write_bytes(incoming_data + b"\n")
            if disposition == "normalizer_determinism_conflict":
                state.repo.connection.execute("UPDATE network_metadata_source_records SET source_record_sha256=?,semantic_payload_sha256=?",
                    (incoming.normalized.source_record_sha256, "f" * 64))
            elif disposition == "replay_identity_evidence_expired":
                state.repo.connection.execute("UPDATE network_metadata_source_records SET digest_state='expired',source_record_sha256=NULL,semantic_payload_sha256=NULL")
        state.repo.connection.execute("UPDATE network_metadata_checkpoint SET committed_byte_offset=0,continuity_anchor_start_offset=0,continuity_anchor_length=0,continuity_anchor_sha256=NULL")
        state.repo.connection.execute("UPDATE network_metadata_source_generations SET committed_byte_offset=0")
        reloaded = HealthController(state.config.capture_scope_binding.capture_source_id)
        reloaded.reload(state.repo)
        reloaded.source_available()
        result = state.repo.ingest_batch([incoming], state.run, reloaded, state.anchor)
        assert result["committed"] == 0
        assert reloaded.last_ingested == ingested
        assert reloaded.last_output == incoming.output_event_at
        if disposition == "duplicate_noop":
            assert result["duplicates"] == 1
        else:
            assert result["blocked"] == disposition
            row = state.repo.latest_health()
            assert row["last_output_event_at"] == incoming.output_event_at
            assert row["last_ingested_event_at"] == ingested
            assert row["metadata_ingest_health"] == row["metadata_output_health"] == "unavailable"


@pytest.mark.parametrize("category", ["pre_binding_event", "outside_intended_scope",
    "unsupported_address_family_for_scope", "schema_invalid", "retention_expired_event"])
def test_trustworthy_filtered_or_fault_output_is_monotonic_without_ingest(category):
    health = HealthController("synthetic-sensor")
    health.source_available()
    newer, older = "2026-10-07T12:00:00.000000Z", "2026-10-06T12:00:00.000000Z"
    health.observe_source(RecordOutcome(0, 2, 1, category, output_event_at=newer))
    health.observe_source(RecordOutcome(2, 4, 1, category, output_event_at=older))
    assert health.last_output == newer and health.last_ingested is None
    if category != "schema_invalid":
        assert health.output == health.ingest == "usable"


@pytest.mark.parametrize("data", [b"\xff", b"{", b'{"x":1,"x":2}', b"[]",
    b'{"event_type":"other","timestamp":"2026-10-07T12:00:00Z"}',
    b'{"event_type":"dns"}', b'{"event_type":"dns","timestamp":"invalid"}'])
def test_untrustworthy_timestamp_does_not_update_health(tmp_path, data):
    item = outcome(configuration(tmp_path).capture_scope_binding, data)
    assert item.output_event_at is None
    health = HealthController("synthetic-sensor")
    health.source_available()
    health.observe_source(item)
    assert health.last_output is health.last_ingested is None


def test_expired_filter_advances_output_without_ingested_time(tmp_path):
    with store(tmp_path) as state:
        def item_at(age, start):
            data = record(source_event(timestamp=ni_format_utc(state.clock() - timedelta(days=age))))
            return data, outcome(state.config.capture_scope_binding, data, start=start,
                generation=state.generation.source_generation_id)
        old_data, old = item_at(29, 0)
        expired_data, expired = item_at(31, old.end)
        (tmp_path / "source.jsonl").write_bytes(old_data + b"\n" + expired_data + b"\n")
        state.repo.ingest_batch([old], state.run, state.health, state.anchor)
        state.clock.advance(seconds=60)
        state.repo.persist_health(state.health, state.repo.load_active()[0])
        before_ingested = state.health.last_ingested
        state.clock.advance(days=3)
        # A >30d event is newer than the previous output watermark, but still expired now.
        expired_data = record(source_event(timestamp=ni_format_utc(state.clock() - timedelta(days=31))))
        expired = outcome(state.config.capture_scope_binding, expired_data, start=old.end,
            generation=state.generation.source_generation_id)
        (tmp_path / "source.jsonl").write_bytes(old_data + b"\n" + expired_data + b"\n")
        state.repo.ingest_batch([expired], state.run, state.health, state.anchor)
        assert state.health.last_output == expired.output_event_at
        assert state.health.last_ingested == before_ingested
        assert state.health.ingest == state.health.output == "usable"
        reloaded = HealthController("synthetic-sensor")
        reloaded.reload(state.repo)
        assert reloaded.last_output == expired.output_event_at and reloaded.last_ingested == before_ingested


def test_reload_scopes_capture_and_restores_state_reason_ownership(tmp_path):
    with store(tmp_path) as state:
        own = state.health
        own.set_capture("unavailable", ("suricata_unavailable", "capture_health_read_unavailable"))
        own.local_reasons = {"invalid_json"}
        own.output = own.ingest = "partial"
        own.last_output = own.last_ingested = "2026-10-07T12:00:00.000000Z"
        own.committed_offset = 0
        state.repo.persist_health(own, state.generation)
        other = HealthController("other-capture")
        other.source_available()
        state.repo.persist_health(other, state.generation)
        reloaded = HealthController(own.capture_source_id)
        reloaded.reload(state.repo)
        assert reloaded.capture == "unavailable"
        assert reloaded.output == reloaded.ingest == "partial"
        assert set(reloaded.capture_reasons) == {"suricata_unavailable", "capture_health_read_unavailable"}
        assert reloaded.local_reasons == {"invalid_json"}
        assert reloaded.last_output == reloaded.last_ingested == own.last_output
        assert reloaded.last_snapshot == own.last_snapshot and reloaded.committed_offset == 0
        assert not reloaded.fault_since_heartbeat
        reloaded.source_available()
        assert reloaded.output == reloaded.ingest == "partial"


@pytest.mark.parametrize("reason", ["source_absent", "source_unavailable"])
@pytest.mark.parametrize("prior_fault", [False, True])
def test_source_recovery_clears_only_source_availability_reasons(reason, prior_fault):
    health = HealthController("synthetic-sensor")
    health.unavailable(reason, source=True)
    if prior_fault:
        health.local_reasons.add("invalid_json")
    health.source_available()
    assert reason not in health.local_reasons
    assert health.output == health.ingest == ("partial" if prior_fault else "usable")
    assert health.local_reasons == ({"invalid_json"} if prior_fault else set())


@pytest.mark.parametrize("category", ["invalid_json", "schema_invalid"])
@pytest.mark.parametrize("fault_first", [False, True])
def test_all_new_observations_reference_final_partial_batch_health(tmp_path, monkeypatch, category, fault_first):
    with store(tmp_path) as state:
        valid_at = ni_format_utc(state.clock() + timedelta(seconds=1))
        data = record(source_event(timestamp=valid_at))
        fault_data = b"{"
        if category == "schema_invalid":
            event = source_event(timestamp=ni_format_utc(state.clock() + timedelta(seconds=2)))
            event["dns"]["version"] = 2
            fault_data = record(event)
        parts = [fault_data, data] if fault_first else [data, fault_data]
        (tmp_path / "source.jsonl").write_bytes(b"\n".join(parts) + b"\n")
        items, offset = [], 0
        for part in parts:
            item = outcome(state.config.capture_scope_binding, part, start=offset,
                generation=state.generation.source_generation_id)
            items.append(item)
            offset = item.end
        fault = next(item for item in items if item.normalized is None)
        assert fault.category == category
        before = state.repo.latest_health()["health_id"]
        count = state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_health").fetchone()[0]
        ensured, sql = [], []
        ensure = HealthController.ensure
        def final_ensure(candidate, repository, generation, now, **kwargs):
            assert repository.connection.in_transaction
            assert candidate.output == candidate.ingest == "partial"
            assert candidate.local_reasons == {category}
            assert candidate.committed_offset == offset
            assert candidate.last_ingested == valid_at
            ensured.append(1)
            return ensure(candidate, repository, generation, now, **kwargs)
        monkeypatch.setattr(HealthController, "ensure", final_ensure)
        state.repo.connection.set_trace_callback(sql.append)
        result = state.repo.ingest_batch(items, state.run, state.health, state.anchor)
        state.repo.connection.set_trace_callback(None)
        assert result == dict(committed=1, duplicates=0, blocked=None)
        assert ensured == [1]
        latest = state.repo.latest_health()
        observation = state.repo.connection.execute("SELECT * FROM network_metadata_observations").fetchone()
        assert observation["source_health_ref"] == latest["health_id"] != before
        assert latest["metadata_output_health"] == latest["metadata_ingest_health"] == "partial"
        assert latest["reason_codes_json"] == '["' + category + '"]'
        assert latest["last_ingested_event_at"] == valid_at
        assert latest["last_output_event_at"] == max(item.output_event_at for item in items if item.output_event_at)
        assert latest["committed_byte_offset"] == state.repo.load_active()[1].committed_byte_offset == offset
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_health").fetchone()[0] == count + 1
        health_insert = next(index for index, command in enumerate(sql) if command.startswith("INSERT INTO network_metadata_source_health"))
        observation_insert = next(index for index, command in enumerate(sql) if command.startswith("INSERT INTO network_metadata_observations"))
        assert health_insert < observation_insert
        assert sql.count("BEGIN IMMEDIATE") == sql.count("COMMIT") == 1


@pytest.mark.parametrize("size", [2, 100])
def test_clean_batch_reuses_health_ref_but_advances_in_memory_watermarks(tmp_path, monkeypatch, size):
    with store(tmp_path) as state:
        items, parts, offset = [], [], 0
        for index in range(size):
            data = record(source_event(timestamp=ni_format_utc(state.clock() + timedelta(microseconds=index))))
            item = outcome(state.config.capture_scope_binding, data, start=offset,
                generation=state.generation.source_generation_id)
            items.append(item)
            parts.append(data)
            offset = item.end
        (tmp_path / "source.jsonl").write_bytes(b"\n".join(parts) + b"\n")
        before = dict(state.repo.latest_health())
        count = state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_health").fetchone()[0]
        ensured = []
        ensure = HealthController.ensure
        def once(candidate, repository, generation, now, **kwargs):
            ensured.append(1)
            return ensure(candidate, repository, generation, now, **kwargs)
        monkeypatch.setattr(HealthController, "ensure", once)
        assert state.repo.ingest_batch(items, state.run, state.health, state.anchor)["committed"] == size
        assert ensured == [1]
        assert state.repo.connection.execute("SELECT DISTINCT source_health_ref FROM network_metadata_observations").fetchall()[0][0] == before["health_id"]
        assert state.repo.connection.execute("SELECT count(DISTINCT source_health_ref) FROM network_metadata_observations").fetchone()[0] == 1
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_health").fetchone()[0] == count
        assert dict(state.repo.latest_health()) == before
        assert state.health.last_output == state.health.last_ingested == items[-1].output_event_at
        assert state.health.committed_offset == state.repo.load_active()[1].committed_byte_offset == offset
        state.clock.advance(seconds=60)
        state.repo.persist_health(state.health, state.repo.load_active()[0])
        latest = state.repo.latest_health()
        assert latest["last_output_event_at"] == latest["last_ingested_event_at"] == items[-1].output_event_at
        assert latest["committed_byte_offset"] == offset
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_health").fetchone()[0] == count + 1


def test_replayed_observation_keeps_original_health_and_all_first_ingest_provenance(tmp_path):
    with store(tmp_path, source=record() + b"\n{\n") as state:
        first = outcome(state.config.capture_scope_binding, generation=state.generation.source_generation_id)
        fault = outcome(state.config.capture_scope_binding, b"{", start=first.end,
            generation=state.generation.source_generation_id)
        state.repo.ingest_batch([first], state.run, state.health, state.anchor)
        original = tuple(state.repo.connection.execute("SELECT * FROM network_metadata_observations").fetchone())
        original_ref = state.repo.latest_health()["health_id"]
        ingested_at = state.health.last_ingested
        with state.repo.transaction():
            state.repo.connection.execute("UPDATE network_metadata_checkpoint SET committed_byte_offset=0,continuity_anchor_start_offset=0,continuity_anchor_length=0,continuity_anchor_sha256=NULL")
            state.repo.connection.execute("UPDATE network_metadata_source_generations SET committed_byte_offset=0")
        state.clock.advance(seconds=5)
        from . import IDENTITY
        replay_run = state.repo.create_ingest_run(IDENTITY)
        assert replay_run != state.run
        result = state.repo.ingest_batch([first, fault], replay_run, state.health, state.anchor)
        assert result == dict(committed=0, duplicates=1, blocked=None)
        assert tuple(state.repo.connection.execute("SELECT * FROM network_metadata_observations").fetchone()) == original
        assert state.repo.latest_health()["health_id"] != original_ref
        assert state.repo.latest_health()["metadata_ingest_health"] == "partial"
        assert state.health.last_ingested == ingested_at
        assert state.health.committed_offset == fault.end


@pytest.mark.parametrize("category", ["invalid_json", "schema_invalid", "record_too_large"])
def test_fault_only_batch_persists_one_final_transition_snapshot(tmp_path, category):
    from app.network_metadata.canonical import sha256
    with store(tmp_path, source=b"x\n") as state:
        item = RecordOutcome(0, 2, 1, category, source_record_sha256=sha256(b"x"))
        before = state.repo.latest_health()["health_id"]
        count = state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_health").fetchone()[0]
        assert state.repo.ingest_batch([item], state.run, state.health, state.anchor) == dict(committed=0, duplicates=0, blocked=None)
        latest = state.repo.latest_health()
        assert latest["health_id"] != before
        assert latest["metadata_output_health"] == latest["metadata_ingest_health"] == "partial"
        assert latest["reason_codes_json"] == '["' + category + '"]'
        assert latest["last_output_event_at"] is latest["last_ingested_event_at"] is None
        assert latest["committed_byte_offset"] == state.repo.load_active()[1].committed_byte_offset == 2
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_health").fetchone()[0] == count + 1
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_observations").fetchone()[0] == 0
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_records").fetchone()[0] == 0
        assert tuple(state.repo.connection.execute("SELECT fault_category,count FROM network_metadata_ingest_fault_aggregates").fetchone()) == (category, 1)
