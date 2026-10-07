import json
import time
from app.network_metadata.retention import RetentionPolicy
from . import store, source_event, record, outcome

CAPACITY_METRICS = {}


def test_3000_temporary_observation_capacity(tmp_path):
    data = [record(source_event(family)) for family in ("dns", "tls", "quic") for _ in range(1000)]
    source = b"\n".join(data) + b"\n"
    with store(tmp_path, source=source) as state:
        start, offset = time.monotonic(), 0
        for index in range(0, 3000, 256):
            batch = []
            for item in data[index:index + 256]:
                event = outcome(state.config.capture_scope_binding, item, start=offset,
                                generation=state.generation.source_generation_id)
                batch.append(event)
                offset = event.end
            state.repo.ingest_batch(batch, state.run, state.health, state.anchor)
        elapsed = time.monotonic() - start
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_observations").fetchone()[0] == 3000
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_sensitive_endpoints").fetchone()[0] == 3000
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_records").fetchone()[0] == 3000
        assert state.repo.load_active()[1].committed_byte_offset == offset == len(source)
        footprint = state.repo.footprint()
        metrics = dict(EVENT_COUNT=3000, MAIN_DB_BYTES=footprint["main"], WAL_BYTES=footprint["wal"],
            SHM_BYTES=footprint["shm"], JOURNAL_BYTES=footprint["journal"], COMBINED_BYTES=footprint["combined"],
            FREELIST_COUNT=state.repo.connection.execute("PRAGMA freelist_count").fetchone()[0],
            BYTES_PER_OBSERVATION=footprint["combined"] / 3000, INGEST_ELAPSED_SECONDS=elapsed,
            CHECKPOINT_END_OFFSET=offset, EXPECTED_SOURCE_END_OFFSET=len(source))
        state.clock.advance(days=31)
        cleanup_start = time.monotonic()
        RetentionPolicy(state.repo).run()
        state.repo.wal_maintenance(retention_ran=True)
        metrics["CLEANUP_ELAPSED_SECONDS"] = time.monotonic() - cleanup_start
        metrics["POST_CLEANUP_COMBINED_BYTES"] = state.repo.footprint()["combined"]
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_observations").fetchone()[0] == 0
        assert state.repo.connection.execute("PRAGMA foreign_key_check").fetchall() == []
        CAPACITY_METRICS.update(metrics)
        print("NI01_CAPACITY=" + json.dumps(metrics, sort_keys=True))
