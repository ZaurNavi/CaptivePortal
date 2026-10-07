import os
import json
import io
import logging
from datetime import timedelta
from dataclasses import replace
import pytest
from app.network_metadata.service import NetworkMetadataService
from app.network_metadata.repository import NetworkMetadataRepository
from app.network_metadata.config import make_capture_scope_binding
from app.network_metadata.models import NetworkMetadataStorageUnavailable
from app.network_metadata.telemetry import NetworkMetadataTelemetry
from app.network_metadata.validation import ni_format_utc
from . import configuration, Clock, Capture, IDENTITY, BOOT, store, seed_blocked, record, source_event, binding_input


def service_for(state, **kwargs):
    return NetworkMetadataService(state.config, state.repo, IDENTITY, Capture(),
        monotonic=lambda: state.clock.tick, boot_id_provider=lambda: BOOT, **kwargs)


@pytest.mark.parametrize("change", ["restart", "replacement", "boot", "binding", "missing", "retention"])
def test_blocked_restart_never_opens_source_or_resolves(tmp_path, change):
    with store(tmp_path) as state:
        generation, checkpoint = seed_blocked(state)
        before_health_count = state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_health").fetchone()[0]
        if change == "replacement":
            path = tmp_path / "source.jsonl"
            path.rename(tmp_path / "historical-source")
            path.write_bytes(record() + b"\n")
        elif change == "missing":
            (tmp_path / "source.jsonl").unlink()
        elif change == "binding":
            value = binding_input()
            value["network_scope_id"] = "changed-binding"
            state.config = replace(state.config, capture_scope_binding=make_capture_scope_binding(value))
        elif change == "retention":
            state.clock.advance(days=46)
        def forbidden(*_):
            pytest.fail("blocked startup must not inspect/open/read source or boot")
        service = NetworkMetadataService(state.config, state.repo, IDENTITY, Capture(),
            monotonic=lambda: state.clock.tick, source_opener=forbidden, boot_id_provider=forbidden)
        service.startup()
        if change != "retention":
            assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_health").fetchone()[0] == before_health_count
        for _ in range(3):
            state.clock.advance(seconds=60)
            service.poll_once()
        assert state.repo.load_active() == (generation, checkpoint)
        assert state.repo.latest_health()["metadata_ingest_health"] == "unavailable"
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_generations").fetchone()[0] == 1
        service.close()


def test_source_absent_alive_then_append(tmp_path):
    clock, cfg = Clock(), configuration(tmp_path)
    repo = NetworkMetadataRepository(cfg, clock=clock)
    service = NetworkMetadataService(cfg, repo, IDENTITY, Capture(), monotonic=lambda: clock.tick, boot_id_provider=lambda: BOOT)
    try:
        service.startup()
        assert repo.load_active() == (None, None)
        assert repo.latest_health()["metadata_output_health"] == "unavailable"
        assert json.loads(repo.latest_health()["reason_codes_json"]) == ["source_absent"]
        (tmp_path / "source.jsonl").write_bytes(record() + b"\n")
        assert service.poll_once()
        assert repo.connection.execute("SELECT count(*) FROM network_metadata_observations").fetchone()[0] == 1
        assert not service.poll_once()
        clock.advance(seconds=60)
        service.poll_once()
        assert repo.latest_health()["metadata_output_health"] == "usable"
    finally:
        service.close()
        repo.close()


def test_live_rotation_drains_tail_without_raw_persistence(tmp_path):
    with store(tmp_path, source=record() + b"\nunterminated-secret") as state:
        service = service_for(state)
        service.startup()
        service.poll_once()
        old = state.repo.load_active()[0].source_generation_id
        (tmp_path / "source.jsonl").rename(tmp_path / "rotated")
        (tmp_path / "source.jsonl").write_bytes(record(source_event("quic")) + b"\n")
        service.poll_once()
        service.poll_once()
        generation, _ = state.repo.load_active()
        assert generation.source_generation_id != old
        closed = state.repo.connection.execute("SELECT close_reason,end_offset FROM network_metadata_source_generations WHERE source_generation_id=?", (old,)).fetchone()
        assert closed[0] == "source_rotated_live" and closed[1] == len(record()) + 1 + len(b"unterminated-secret")
        assert state.repo.connection.execute("SELECT count FROM network_metadata_ingest_fault_aggregates WHERE fault_category='partial_final_record'").fetchone()[0] == 1
        service.close()


def test_binding_cutover_has_no_rewind(tmp_path):
    with store(tmp_path) as state:
        service = service_for(state)
        service.startup()
        service.poll_once()
        old, checkpoint = state.repo.load_active()
        service.close()
        value = binding_input()
        value["network_scope_id"] = "new-scope"
        state.config = replace(state.config, capture_scope_binding=make_capture_scope_binding(value))
        restarted = service_for(state)
        restarted.startup()
        new, current = state.repo.load_active()
        assert old.source_generation_id != new.source_generation_id
        assert new.generation_start_offset == current.committed_byte_offset == checkpoint.committed_byte_offset
        assert current.continuity_anchor_sha256 == checkpoint.continuity_anchor_sha256
        assert not restarted.poll_once()
        restarted.close()


@pytest.mark.parametrize("source_state", ["valid", "absent", "nonregular", "stat", "open"])
def test_reboot_closes_old_generation_before_source_inspection(tmp_path, monkeypatch, source_state):
    with store(tmp_path) as state:
        original = service_for(state)
        original.startup()
        original.poll_once()
        old, checkpoint = state.repo.load_active()
        original.close()
        path = state.config.source_path
        source = tmp_path / "source.jsonl"
        if source_state in {"absent", "nonregular"}:
            source.rename(tmp_path / "pre-reboot-source")
            if source_state == "nonregular":
                source.mkdir()
        def assert_closed():
            row = state.repo.connection.execute(
                "SELECT close_reason,coverage_gap_possible,end_offset FROM network_metadata_source_generations WHERE source_generation_id=?",
                (old.source_generation_id,)).fetchone()
            assert tuple(row) == ("host_reboot_source_lost", 1, checkpoint.committed_byte_offset)
            assert state.repo.load_active() == (None, None)
        actual_stat, actual_open = os.stat, os.open
        def stat(target, *args, **kwargs):
            if target == path:
                assert_closed()
                if source_state == "stat":
                    raise PermissionError("private source failure")
            return actual_stat(target, *args, **kwargs)
        def opener(target):
            assert_closed()
            if source_state == "open":
                raise PermissionError("private source failure")
            return actual_open(target, os.O_RDONLY | os.O_NONBLOCK)
        monkeypatch.setattr(os, "stat", stat)
        new_boot = "26716a71-d675-4c17-bbe2-9c66661fc0b7"
        restarted = NetworkMetadataService(state.config, state.repo, IDENTITY, Capture(),
            monotonic=lambda: state.clock.tick, boot_id_provider=lambda: new_boot, source_opener=opener)
        try:
            restarted.startup()
            active, current = state.repo.load_active()
            if source_state == "valid":
                assert active.source_generation_id != old.source_generation_id
                assert active.host_boot_id == new_boot
                assert active.generation_start_offset == current.committed_byte_offset == 0
                assert current.continuity_anchor_length == 0 and current.continuity_anchor_sha256 is None
                assert active.capture_scope_binding_digest == state.config.capture_scope_binding.binding_digest
                assert active.coverage_gap_possible == 0
                assert restarted.health.output == "partial" and restarted.health.ingest == "usable"
                assert "source_continuity_mismatch" in restarted.health.local_reasons
            else:
                assert active is current is None
                health = state.repo.latest_health()
                assert health["source_generation_id"] is None
                assert health["metadata_output_health"] == "unavailable"
                reason = "source_absent" if source_state == "absent" else "source_unavailable"
                assert json.loads(health["reason_codes_json"]) == [reason]
            assert state.repo.connection.execute(
                "SELECT closed_at_utc FROM network_metadata_source_generations WHERE source_generation_id=?",
                (old.source_generation_id,)).fetchone()[0] is not None
        finally:
            restarted.close()


def test_source_disappears_and_same_inode_returns(tmp_path):
    with store(tmp_path) as state:
        service = service_for(state)
        service.startup()
        service.poll_once()
        generation, checkpoint = state.repo.load_active()
        path = tmp_path / "source.jsonl"
        saved = tmp_path / "hidden"
        path.rename(saved)
        service.poll_once()
        assert state.repo.load_active() == (generation, checkpoint)
        assert state.repo.latest_health()["metadata_output_health"] == "unavailable"
        saved.rename(path)
        service.poll_once()
        assert state.repo.load_active() == (generation, checkpoint)
        assert state.repo.latest_health()["metadata_output_health"] == "usable"
        service.close()


def test_runtime_storage_rollback_then_recovery(tmp_path):
    with store(tmp_path) as state:
        service = service_for(state)
        service.startup()
        original = state.repo.ingest_batch
        state.repo.ingest_batch = lambda *_: (_ for _ in ()).throw(NetworkMetadataStorageUnavailable())
        service.poll_once()
        assert service.storage_failed and state.repo.load_active()[1].committed_byte_offset == 0
        state.repo.ingest_batch = original
        service.poll_once()
        assert not service.storage_failed
        assert state.repo.load_active()[1].committed_byte_offset == len(record()) + 1
        service.close()


@pytest.mark.parametrize("change,reason", [("replacement", "source_replaced_while_reader_down"),
    ("truncation", "observed_truncation"), ("anchor", "continuity_anchor_mismatch"),
    ("boot", "host_reboot_source_lost")])
def test_runnable_restart_source_transitions(tmp_path, change, reason):
    with store(tmp_path) as state:
        original = service_for(state)
        original.startup()
        original.poll_once()
        old, checkpoint = state.repo.load_active()
        original.close()
        path = tmp_path / "source.jsonl"
        boot = BOOT
        if change == "replacement":
            path.rename(tmp_path / "old-source")
            path.write_bytes(record() + b"\n")
        elif change == "truncation":
            path.write_bytes(b"")
        elif change == "anchor":
            path.write_bytes(b"x" * checkpoint.committed_byte_offset)
        else:
            boot = "26716a71-d675-4c17-bbe2-9c66661fc0b7"
        restarted = NetworkMetadataService(state.config, state.repo, IDENTITY, Capture(),
            monotonic=lambda: state.clock.tick, boot_id_provider=lambda: boot)
        restarted.startup()
        new, current = state.repo.load_active()
        assert old.source_generation_id != new.source_generation_id and current.committed_byte_offset == 0
        row = state.repo.connection.execute("SELECT close_reason,coverage_gap_possible FROM network_metadata_source_generations WHERE source_generation_id=?", (old.source_generation_id,)).fetchone()
        assert tuple(row) == (reason, 1)
        assert restarted.health.output == "partial" and restarted.health.ingest == "usable"
        assert restarted.health.local_reasons == {"source_continuity_mismatch"}
        restarted.close()


def test_oversized_tail_closes_once_without_oversized_fault(tmp_path):
    with store(tmp_path, source=b"x" * 2000000) as state:
        state.config = replace(state.config, max_record_bytes=4096)
        service = service_for(state)
        service.startup()
        for _ in range(3):
            service.poll_once()
        assert service.reader.retained_unfinished_bytes == 0
        assert state.repo.load_active()[1].committed_byte_offset == 0
        (tmp_path / "source.jsonl").rename(tmp_path / "old-tail")
        (tmp_path / "source.jsonl").write_bytes(b"")
        for _ in range(3):
            service.poll_once()
        faults = state.repo.connection.execute("SELECT fault_category,count FROM network_metadata_ingest_fault_aggregates").fetchall()
        assert [tuple(row) for row in faults] == [("partial_final_record", 1)]
        service.close()


def test_oversized_terminated_dedicated_checkpoint(tmp_path):
    with store(tmp_path, source=b"x" * 5000 + b"\n" + record() + b"\n") as state:
        state.config = replace(state.config, max_record_bytes=4096)
        service = service_for(state)
        service.startup()
        service.poll_once()
        assert state.repo.load_active()[1].committed_byte_offset == 5001
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_observations").fetchone()[0] == 0
        service.poll_once()
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_observations").fetchone()[0] == 1
        service.close()


@pytest.mark.parametrize("failure", ["nonregular", "open", "stat", "fstat", "read"])
def test_source_unavailable_preserves_checkpoint_and_safe_health(tmp_path, monkeypatch, failure):
    with store(tmp_path) as state:
        output = io.StringIO()
        logger = logging.Logger("test-source-health")
        logger.addHandler(logging.StreamHandler(output))
        state.repo.telemetry = NetworkMetadataTelemetry(logger)
        path = state.config.source_path
        secret = "private OS failure " + path
        def unavailable(*_):
            raise PermissionError(secret)
        service = service_for(state, source_opener=unavailable) if failure == "open" else service_for(state)
        before = state.repo.load_active()
        try:
            if failure == "nonregular":
                (tmp_path / "source.jsonl").rename(tmp_path / "held-source")
                (tmp_path / "source.jsonl").mkdir()
            elif failure == "stat":
                original = os.stat
                def stat(target, *args, **kwargs):
                    if target == path:
                        unavailable()
                    return original(target, *args, **kwargs)
                monkeypatch.setattr(os, "stat", stat)
            service.startup()
            if failure == "fstat":
                original = os.fstat
                def fstat(fd):
                    if fd != state.fd:
                        unavailable()
                    return original(fd)
                monkeypatch.setattr(os, "fstat", fstat)
            elif failure == "read":
                monkeypatch.setattr(os, "pread", unavailable)
            assert service.started
            assert not service.poll_once()
            assert state.repo.load_active() == before
            health = state.repo.latest_health()
            assert health["metadata_output_health"] == health["metadata_ingest_health"] == "unavailable"
            assert json.loads(health["reason_codes_json"]) == ["source_unavailable"]
            assert not service.storage_failed
            # Physical I/O wrappers expose only the stable generic error, never OS text.
            with pytest.raises(NetworkMetadataStorageUnavailable) as raised:
                if failure in {"nonregular", "stat"}:
                    service._path_info()
                elif failure == "read":
                    service.reader.read_batch(1, 1024)
                else:
                    service._open()
            assert path not in str(raised.value) and secret not in str(raised.value)
            assert path not in output.getvalue() and secret not in output.getvalue()
        finally:
            service.close()


@pytest.mark.parametrize("restart", [False, True])
def test_pending_reboot_gap_survives_absence_and_restart(tmp_path, restart):
    with store(tmp_path) as state:
        (tmp_path / "source.jsonl").unlink()
        new_boot = "26716a71-d675-4c17-bbe2-9c66661fc0b7"
        def build():
            return NetworkMetadataService(state.config, state.repo, IDENTITY, Capture(),
                monotonic=lambda: state.clock.tick, boot_id_provider=lambda: new_boot)
        service = build()
        try:
            service.startup()
            assert state.repo.load_active() == (None, None)
            assert state.repo.latest_closed_generation_gap_possible()
            assert service.health.output == "unavailable" and "source_absent" in service.health.local_reasons
            if restart:
                service.close()
                service = build()
                service.startup()
            (tmp_path / "source.jsonl").write_bytes(b"")
            service.poll_once()
            assert service.health.output == "partial" and service.health.ingest == "usable"
            assert service.health.local_reasons == {"source_continuity_mismatch"}
            assert state.repo.load_active()[0].coverage_gap_possible == 0
        finally:
            service.close()


def test_first_source_and_clean_live_rotation_have_no_gap(tmp_path):
    clock, cfg = Clock(), configuration(tmp_path)
    repo = NetworkMetadataRepository(cfg, clock=clock)
    (tmp_path / "source.jsonl").write_bytes(b"")
    service = NetworkMetadataService(cfg, repo, IDENTITY, Capture(),
        monotonic=lambda: clock.tick, boot_id_provider=lambda: BOOT)
    try:
        service.startup()
        assert not repo.latest_closed_generation_gap_possible()
        assert service.health.output == "usable" and not service.health.local_reasons
        service.poll_once()
        old = repo.load_active()[0].source_generation_id
        (tmp_path / "source.jsonl").rename(tmp_path / "clean-rotation")
        (tmp_path / "source.jsonl").write_bytes(b"")
        service.poll_once()
        assert repo.load_active()[0].source_generation_id != old
        assert not repo.latest_closed_generation_gap_possible()
        assert service.health.output == service.health.ingest == "usable"
    finally:
        service.close()
        repo.close()


@pytest.mark.parametrize("new_fault", [False, True])
def test_partial_restart_preserved_until_clean_heartbeat(tmp_path, new_fault):
    with store(tmp_path, source=b"{\n") as state:
        service = service_for(state)
        service.startup()
        service.poll_once()
        before = state.repo.load_active()
        assert service.health.output == service.health.ingest == "partial"
        service.close()
        service = service_for(state)
        try:
            service.startup()
            assert state.repo.load_active() == before
            assert service.health.output == service.health.ingest == "partial"
            assert service.health.local_reasons == {"invalid_json"}
            assert not service.health.fault_since_heartbeat
            if new_fault:
                with (tmp_path / "source.jsonl").open("ab") as stream:
                    stream.write(b"{\n")
                service.poll_once()
            state.clock.advance(seconds=60)
            service.poll_once()
            assert service.health.output == ("partial" if new_fault else "usable")
        finally:
            service.close()


def test_continuity_gap_partial_preserved_on_same_generation_restart(tmp_path):
    with store(tmp_path) as state:
        service = NetworkMetadataService(state.config, state.repo, IDENTITY, Capture(),
            monotonic=lambda: state.clock.tick,
            boot_id_provider=lambda: "26716a71-d675-4c17-bbe2-9c66661fc0b7")
        service.startup()
        active = state.repo.load_active()
        service.close()
        restarted = NetworkMetadataService(state.config, state.repo, IDENTITY, Capture(),
            monotonic=lambda: state.clock.tick,
            boot_id_provider=lambda: "26716a71-d675-4c17-bbe2-9c66661fc0b7")
        try:
            restarted.startup()
            assert state.repo.load_active() == active
            assert restarted.health.output == "partial" and restarted.health.ingest == "usable"
            assert restarted.health.local_reasons == {"source_continuity_mismatch"}
        finally:
            restarted.close()


def test_100_timestamp_only_batches_then_exact_heartbeat(tmp_path):
    with store(tmp_path, source=b"") as state:
        service = service_for(state)
        try:
            service.startup()
            before = state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_health").fetchone()[0]
            for index in range(100):
                latest = ni_format_utc(state.clock() + timedelta(microseconds=index))
                with (tmp_path / "source.jsonl").open("ab") as stream:
                    stream.write(record(source_event(timestamp=latest)) + b"\n")
                assert service.poll_once()
            assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_health").fetchone()[0] == before
            assert service.health.last_output == service.health.last_ingested == latest
            state.clock.advance(seconds=60)
            service.poll_once()
            assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_health").fetchone()[0] == before + 1
            row = state.repo.latest_health()
            assert row["last_output_event_at"] == row["last_ingested_event_at"] == latest
            assert row["committed_byte_offset"] == state.repo.load_active()[1].committed_byte_offset
        finally:
            service.close()


@pytest.mark.parametrize("boundary", ["resume", "cutover", "ingest_anchor"])
def test_source_anchor_failure_is_not_sqlite_failure(tmp_path, monkeypatch, boundary):
    with store(tmp_path) as state:
        service = service_for(state)
        try:
            service.startup()
            service.poll_once()
            before = state.repo.load_active()
            assert before[1].committed_byte_offset > 0
            actual_pread = os.pread
            calls = []
            if boundary == "cutover":
                value = binding_input()
                value["network_scope_id"] = "cutover-scope"
                service.config = replace(state.config, capture_scope_binding=make_capture_scope_binding(value))
                state.repo.persist_binding(service.config.capture_scope_binding)
            if boundary == "ingest_anchor":
                with (tmp_path / "source.jsonl").open("ab") as stream:
                    stream.write(record(source_event("tls")) + b"\n")
            def pread(fd, length, offset):
                calls.append((length, offset))
                # Existing checkpoint anchor is first. Cutover anchor is second.
                # Ingest anchor is the second anchor starting at 0, after reader pread.
                fail = boundary == "resume" or (boundary == "cutover" and len(calls) == 2)
                fail = fail or (boundary == "ingest_anchor" and offset == 0 and length > before[1].committed_byte_offset)
                if fail:
                    raise PermissionError("private source path " + state.config.source_path)
                return actual_pread(fd, length, offset)
            monkeypatch.setattr(os, "pread", pread)
            assert not service.poll_once()
            assert state.repo.load_active() == before
            assert not service.storage_failed
            assert service.health.output == service.health.ingest == "unavailable"
            assert service.health.local_reasons == {"source_unavailable"}
            assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_observations").fetchone()[0] == 1
        finally:
            service.close()


@pytest.mark.parametrize("family", ["dns", "tls", "quic"])
def test_source_failure_keeps_heartbeat_and_due_retention(tmp_path, monkeypatch, family):
    with store(tmp_path, source=record(source_event(family)) + b"\n") as state:
        service = service_for(state)
        try:
            service.startup()
            service.poll_once()
            before = state.repo.load_active()
            calls = []
            def failed_pread(*_):
                calls.append(1)
                raise PermissionError("private I/O error")
            monkeypatch.setattr(os, "pread", failed_pread)
            service.poll_once()
            health_count = state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_health").fetchone()[0]
            state.clock.advance(seconds=60)
            service.poll_once()
            assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_health").fetchone()[0] == health_count + 1
            state.clock.advance(days=15)
            service.poll_once()
            assert state.repo.load_active() == before and not service.storage_failed
            assert service.health.output == service.health.ingest == "unavailable"
            assert service.health.local_reasons == {"source_unavailable"}
            assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_sensitive_endpoints").fetchone()[0] == 0
            assert tuple(state.repo.connection.execute("SELECT digest_state,source_record_sha256,semantic_payload_sha256 FROM network_metadata_source_records").fetchone()) == ("expired", None, None)
            row = state.repo.connection.execute(f"SELECT * FROM network_metadata_{family}").fetchone()
            if family == "dns":
                assert row["query_names_presence_state"] == row["answer_values_presence_state"] == "expired"
                assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_dns_queries").fetchone()[0] == 0
                assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_dns_answers").fetchone()[0] == 0
            else:
                assert row["sni"] is None and row["sni_presence_state"] == "expired"
            state.clock.advance(days=16)
            service.poll_once()
            assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_observations").fetchone()[0] == 0
            assert state.repo.load_active() == before and not service.storage_failed
            assert len(calls) == 4  # exactly one failed source operation per poll, no retry
        finally:
            service.close()


def test_real_sqlite_transaction_failure_remains_storage_failure(tmp_path):
    with store(tmp_path) as state:
        service = service_for(state)
        try:
            service.startup()
            before = state.repo.load_active()
            state.repo.connection.execute("CREATE TEMP TRIGGER injected_store_failure BEFORE INSERT ON network_metadata_observations "
                "BEGIN SELECT RAISE(ABORT, 'injected SQLite failure'); END")
            assert not service.poll_once()
            assert service.storage_failed
            assert service.health.ingest == "unavailable"
            assert service.health.local_reasons == {"storage_unavailable"}
            assert state.repo.load_active() == before
            assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_observations").fetchone()[0] == 0
        finally:
            service.close()


@pytest.mark.parametrize("restart", [False, True])
@pytest.mark.parametrize("change,reason,gap", [
    ("live_rotation", "source_rotated_live", False),
    ("running_truncation", "observed_truncation", True),
    ("running_anchor", "continuity_anchor_mismatch", True),
    ("down_replacement", "source_replaced_while_reader_down", True),
    ("down_truncation", "observed_truncation", True)])
def test_terminal_discontinuity_closes_before_failed_open_and_recovers(tmp_path, change, reason, gap, restart):
    tail = b"unfinished-tail" if change == "live_rotation" else b""
    with store(tmp_path, source=record() + b"\n" + tail) as state:
        service = service_for(state)
        try:
            service.startup()
            service.poll_once()
            old, checkpoint = state.repo.load_active()
            old_fd = service.fd
            assert service.reader.at_eof
            final_offset = service.reader.scan_offset if tail else checkpoint.committed_byte_offset
            if change.startswith("down_"):
                service.close()
            path = tmp_path / "source.jsonl"
            if change in {"live_rotation", "down_replacement"}:
                path.rename(tmp_path / "previous-source")
                path.write_bytes(b"")
            elif "truncation" in change:
                path.write_bytes(b"")
            else:
                path.write_bytes(b"x" * checkpoint.committed_byte_offset)
            opens = []
            def fail_open(_):
                # The durable close must already exist at the very first new open.
                assert state.repo.load_active() == (None, None)
                row = state.repo.connection.execute(
                    "SELECT closed_at_utc,close_reason,coverage_gap_possible,end_offset,committed_byte_offset "
                    "FROM network_metadata_source_generations WHERE source_generation_id=?",
                    (old.source_generation_id,)).fetchone()
                assert row[0] is not None
                assert tuple(row[1:]) == (reason, int(gap), final_offset, final_offset)
                assert service.fd is service.reader is None
                with pytest.raises(OSError):
                    os.fstat(old_fd)
                if tail:
                    assert tuple(state.repo.connection.execute(
                        "SELECT fault_category,count FROM network_metadata_ingest_fault_aggregates").fetchone()) == (
                        "partial_final_record", 1)
                opens.append(1)
                raise PermissionError("controlled unavailable replacement")
            service.source_opener = fail_open
            assert not service.poll_once()
            assert opens == [1]
            assert not service.storage_failed
            assert state.repo.load_active() == (None, None)
            assert service.health.committed_offset is None
            assert service.health.output == service.health.ingest == "unavailable"
            assert "source_unavailable" in service.health.local_reasons
            assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_generations").fetchone()[0] == 1
            # Failure is durable, not a disposable in-process transition decision.
            path.write_bytes(b"")
            if restart:
                service.close()
                service = service_for(state)
                service.startup()
            else:
                service.source_opener = lambda target: os.open(target, os.O_RDONLY | os.O_NONBLOCK)
                assert not service.poll_once()
            new, current = state.repo.load_active()
            assert new.source_generation_id != old.source_generation_id
            assert new.generation_start_offset == current.committed_byte_offset == 0
            assert (current.continuity_anchor_start_offset, current.continuity_anchor_length,
                current.continuity_anchor_sha256) == (0, 0, None)
            assert new.coverage_gap_possible == 0
            assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_generations").fetchone()[0] == 2
            assert service.health.output == "partial"
            if gap:
                assert "source_continuity_mismatch" in service.health.local_reasons
                assert service.health.ingest == "usable"
            else:
                assert service.health.local_reasons == {"partial_final_record"}
                assert service.health.ingest == "partial"
        finally:
            service.close()


def test_same_identity_open_failure_before_anchor_preserves_authority(tmp_path):
    with store(tmp_path) as state:
        service = service_for(state)
        try:
            service.startup()
            service.poll_once()
            before = state.repo.load_active()
            service.close()
            def fail_open(_):
                assert state.repo.load_active() == before
                raise PermissionError("controlled same-file open failure")
            service.source_opener = fail_open
            assert not service.poll_once()
            assert state.repo.load_active() == before
            assert service.health.output == service.health.ingest == "unavailable"
            assert service.health.local_reasons == {"source_unavailable"}
            assert not service.storage_failed
            service.source_opener = lambda target: os.open(target, os.O_RDONLY | os.O_NONBLOCK)
            assert not service.poll_once()
            assert state.repo.load_active() == before
            assert service.health.output == service.health.ingest == "usable"
        finally:
            service.close()


@pytest.mark.parametrize("rollback", [False, True])
def test_reader_down_anchor_mismatch_one_open_one_atomic_transition(tmp_path, monkeypatch, rollback):
    with store(tmp_path) as state:
        service = service_for(state)
        try:
            service.startup()
            service.poll_once()
            before = state.repo.load_active()
            service.close()
            (tmp_path / "source.jsonl").write_bytes(b"x" * before[1].committed_byte_offset)
            opened, transitions = [], []
            def opener(target):
                fd = os.open(target, os.O_RDONLY | os.O_NONBLOCK)
                opened.append(fd)
                return fd
            service.source_opener = opener
            transition = state.repo.transition_generation
            def tracked_transition(**kwargs):
                transitions.append(kwargs)
                return transition(**kwargs)
            monkeypatch.setattr(state.repo, "transition_generation", tracked_transition)
            if rollback:
                state.repo.connection.execute("CREATE TEMP TRIGGER fail_new_generation BEFORE INSERT ON network_metadata_source_generations "
                    "BEGIN SELECT RAISE(ABORT, 'controlled generation transaction failure'); END")
            sql = []
            state.repo.connection.set_trace_callback(sql.append)
            if rollback:
                with pytest.raises(NetworkMetadataStorageUnavailable):
                    service._lifecycle()
            else:
                service._lifecycle()
            state.repo.connection.set_trace_callback(None)
            assert len(opened) == len(transitions) == 1
            assert transitions[0]["physical"] is not None
            assert transitions[0]["close_reason"] == "continuity_anchor_mismatch"
            assert transitions[0]["gap"] is True
            assert transitions[0]["start"] == 0 and transitions[0]["anchor"] == (0, 0, None)
            if rollback:
                assert state.repo.load_active() == before
                assert service.fd is service.reader is None
                with pytest.raises(OSError):
                    os.fstat(opened[0])
                assert sql.count("ROLLBACK") == 1
                assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_generations").fetchone()[0] == 1
            else:
                assert transitions[0]["physical"] == (os.fstat(opened[0]).st_dev, os.fstat(opened[0]).st_ino)
                new, checkpoint = state.repo.load_active()
                assert new.source_generation_id != before[0].source_generation_id
                assert new.generation_start_offset == checkpoint.committed_byte_offset == 0
                assert checkpoint.continuity_anchor_sha256 is None and checkpoint.continuity_anchor_length == 0
                assert tuple(state.repo.connection.execute(
                    "SELECT close_reason,coverage_gap_possible,end_offset FROM network_metadata_source_generations "
                    "WHERE source_generation_id=?", (before[0].source_generation_id,)).fetchone()) == (
                    "continuity_anchor_mismatch", 1, before[1].committed_byte_offset)
                # Subsequent health persistence is separate; generation close+open is one commit.
                assert sum(command == "BEGIN IMMEDIATE" for command in sql) == 2
                assert sql.count("COMMIT") == 2
        finally:
            service.close()


def test_close_transaction_failure_retains_owned_old_reader(tmp_path):
    with store(tmp_path) as state:
        service = service_for(state)
        try:
            service.startup()
            service.poll_once()
            before = state.repo.load_active()
            fd, reader = service.fd, service.reader
            (tmp_path / "source.jsonl").rename(tmp_path / "old")
            (tmp_path / "source.jsonl").write_bytes(b"")
            state.repo.connection.execute("CREATE TEMP TRIGGER fail_close BEFORE UPDATE OF closed_at_utc ON network_metadata_source_generations "
                "BEGIN SELECT RAISE(ABORT, 'controlled close transaction failure'); END")
            def forbidden_open(_):
                pytest.fail("replacement must not open before closure commits")
            service.source_opener = forbidden_open
            assert not service.poll_once()
            assert service.storage_failed
            assert state.repo.load_active() == before
            assert service.fd == fd and service.reader is reader
            assert os.fstat(fd).st_ino == before[0].st_ino
        finally:
            service.close()


@pytest.mark.parametrize("return_as", ["same", "different", "truncated", "anchor"])
def test_absent_path_pauses_unread_records_then_full_reappearance_decision(tmp_path, monkeypatch, return_as):
    unread = record() + b"\n" + record(source_event("tls")) + b"\n"
    with store(tmp_path, source=unread) as state:
        service = service_for(state)
        try:
            service.startup()
            # Seed a non-zero durable checkpoint for anchor/truncation reappearance.
            if return_as in {"truncated", "anchor"}:
                service.poll_once()
                with (tmp_path / "source.jsonl").open("ab") as stream:
                    stream.write(unread)
            before = state.repo.load_active()
            count = state.repo.connection.execute("SELECT count(*) FROM network_metadata_observations").fetchone()[0]
            fd, reader = service.fd, service.reader
            scan_before = reader.scan_offset
            path, hidden = tmp_path / "source.jsonl", tmp_path / "hidden-source"
            path.rename(hidden)
            read_batch = reader.read_batch
            ingest = state.repo.ingest_batch
            import app.network_metadata.service as service_module
            normalize = service_module.normalize_record
            def forbidden(*_, **__):
                pytest.fail("canonical absence must pause read/normalize/ingest")
            with monkeypatch.context() as paused:
                paused.setattr(reader, "read_batch", forbidden)
                paused.setattr(state.repo, "ingest_batch", forbidden)
                paused.setattr(service_module, "normalize_record", forbidden)
                for _ in range(2):
                    assert not service.poll_once()
                    assert state.repo.load_active() == before
                    assert service.fd == fd and service.reader is reader
                    assert reader.scan_offset == scan_before
                    assert os.fstat(fd).st_ino == before[0].st_ino
                    assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_observations").fetchone()[0] == count
                    assert service.health.output == service.health.ingest == "unavailable"
                    assert service.health.local_reasons == {"source_absent"}
            if return_as == "different":
                path.write_bytes(record(source_event("quic")) + b"\n")
            else:
                hidden.rename(path)
                if return_as == "truncated":
                    path.write_bytes(b"")
                elif return_as == "anchor":
                    path.write_bytes(b"x" * before[1].committed_byte_offset)
            assert reader.read_batch == read_batch and state.repo.ingest_batch == ingest
            assert service_module.normalize_record is normalize
            service.poll_once()
            assert "source_absent" not in service.health.local_reasons
            if return_as == "same":
                active, checkpoint = state.repo.load_active()
                assert active.source_generation_id == before[0].source_generation_id
                assert checkpoint.committed_byte_offset == len(unread)
                assert service.fd == fd and service.reader is reader
                assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_observations").fetchone()[0] == 2
            elif return_as == "different":
                assert state.repo.load_active()[0].source_generation_id == before[0].source_generation_id
                assert state.repo.load_active()[1].committed_byte_offset == len(unread)
                assert service.fd == fd and service.reader is reader
                service.poll_once()
                active, checkpoint = state.repo.load_active()
                assert active.source_generation_id != before[0].source_generation_id
                assert checkpoint.committed_byte_offset == len(record(source_event("quic"))) + 1
                assert tuple(state.repo.connection.execute(
                    "SELECT close_reason,coverage_gap_possible,end_offset FROM network_metadata_source_generations "
                    "WHERE source_generation_id=?", (before[0].source_generation_id,)).fetchone()) == (
                    "source_rotated_live", 0, len(unread))
            else:
                assert state.repo.load_active()[0].source_generation_id != before[0].source_generation_id
                reason = "observed_truncation" if return_as == "truncated" else "continuity_anchor_mismatch"
                assert tuple(state.repo.connection.execute(
                    "SELECT close_reason,coverage_gap_possible,end_offset FROM network_metadata_source_generations "
                    "WHERE source_generation_id=?", (before[0].source_generation_id,)).fetchone()) == (
                    reason, 1, before[1].committed_byte_offset)
        finally:
            service.close()


@pytest.mark.parametrize("family", ["dns", "tls", "quic"])
def test_canonical_absence_keeps_heartbeat_retention_and_wal(tmp_path, monkeypatch, family):
    with store(tmp_path, source=record(source_event(family)) + b"\n") as state:
        service = service_for(state)
        try:
            service.startup()
            service.poll_once()
            before = state.repo.load_active()
            fd, reader = service.fd, service.reader
            (tmp_path / "source.jsonl").rename(tmp_path / "absent-canonical")
            wal_calls = []
            maintenance = state.repo.wal_maintenance
            def wal(**kwargs):
                wal_calls.append(kwargs)
                return maintenance(**kwargs)
            monkeypatch.setattr(state.repo, "wal_maintenance", wal)
            assert not service.poll_once()
            rows = state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_health").fetchone()[0]
            state.clock.advance(seconds=60)
            assert not service.poll_once()
            assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_health").fetchone()[0] == rows + 1
            state.clock.advance(days=15)
            assert not service.poll_once()
            assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_sensitive_endpoints").fetchone()[0] == 0
            assert tuple(state.repo.connection.execute("SELECT digest_state,source_record_sha256,semantic_payload_sha256 FROM network_metadata_source_records").fetchone()) == ("expired", None, None)
            payload = state.repo.connection.execute(f"SELECT * FROM network_metadata_{family}").fetchone()
            if family == "dns":
                assert payload["query_names_presence_state"] == payload["answer_values_presence_state"] == "expired"
                assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_dns_queries").fetchone()[0] == 0
                assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_dns_answers").fetchone()[0] == 0
            else:
                assert payload["sni"] is None and payload["sni_presence_state"] == "expired"
            state.clock.advance(days=16)
            assert not service.poll_once()
            assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_observations").fetchone()[0] == 0
            assert wal_calls == [dict(retention_ran=False), dict(retention_ran=False),
                dict(retention_ran=True), dict(retention_ran=True)]
            assert state.repo.load_active() == before
            assert service.fd == fd and service.reader is reader
            assert service.health.output == service.health.ingest == "unavailable"
            assert service.health.local_reasons == {"source_absent"}
            assert not service.storage_failed
        finally:
            service.close()
