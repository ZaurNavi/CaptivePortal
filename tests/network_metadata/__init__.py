"""Synthetic, temporary NI-only test support."""
import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from app.network_metadata.config import network_metadata_config_from_env
from app.network_metadata.health import HealthController
from app.network_metadata.normalizer import normalize_record
from app.network_metadata.repository import NetworkMetadataRepository
from app.network_metadata.source import continuity_anchor

SITE = "0123456789abcdef01234567"
BOOT = "ad5cc69d-8385-4130-ad42-eb167a040269"
GENERATION = "9412aebe-6e13-463b-9a93-d2e5c8475766"
IDENTITY = SimpleNamespace(artifact_sha="a" * 40, artifact_tree="b" * 40,
                          process_started_at="2026-10-07T12:00:00.000Z")


class Clock:
    def __init__(self):
        self.value = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)
        self.tick = 0

    def __call__(self):
        return self.value

    def advance(self, *, seconds=0, days=0):
        self.value += timedelta(seconds=seconds, days=days)
        self.tick += seconds + days * 86400


class Capture:
    def __init__(self):
        self.calls = 0

    def evaluate(self, *_):
        self.calls += 1
        return "unknown", ()


def binding_input(**changes):
    return dict(schema_version=1, capture_source_id="synthetic-sensor", site_id=SITE,
                network_scope_id="lab-scope", ipv4_cidrs=["10.73.0.0/24"],
                valid_from_utc="2026-01-01T00:00:00.000000Z", **changes)


def configuration(tmp_path, **variables):
    return network_metadata_config_from_env({"NETWORK_METADATA_ENABLED": "true",
        "NETWORK_METADATA_SOURCE_PATH": str(tmp_path / "source.jsonl"),
        "NETWORK_METADATA_DB_PATH": str(tmp_path / "metadata.sqlite3"),
        "NETWORK_METADATA_CAPTURE_SCOPE_BINDING_JSON": json.dumps(binding_input()), **variables})


def source_event(family="dns", **changes):
    payload = {"dns": dict(version=3, type="request", tx_id=18446744073709551615,
                           queries=[dict(rrname="ni-query-sentinel.example", rrtype="A")],
                           answers=[dict(rrtype="A", rdata="203.0.113.93")]),
               "tls": dict(version="TLSv1.3", sni="ni-sni-sentinel.example",
                           client_alpns=["h2", "h2"], server_alpns=["http/1.1"]),
               "quic": dict(version="v1", sni="ni-quic-sentinel.example")}[family]
    return {"event_type": family, "timestamp": "2026-10-07T12:00:00.123456Z",
            "src_ip": "10.73.0.7", "dest_ip": "2001:db8::93", "src_port": 12345,
            "dest_port": 443, "proto": "UDP", "flow_id": 18446744073709551615, family: payload, **changes}


def record(event=None):
    return json.dumps(event or source_event(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def outcome(binding, data=None, *, start=0, generation=GENERATION):
    data = record() if data is None else data
    return normalize_record(data, source_generation_id=generation, start=start, end=start + len(data) + 1, binding=binding)


@contextmanager
def store(tmp_path, *, source=None):
    clock, config = Clock(), configuration(tmp_path)
    data = source if source is not None else record() + b"\n"
    (tmp_path / "source.jsonl").write_bytes(data)
    repo = NetworkMetadataRepository(config, clock=clock).initialize()
    repo.persist_binding(config.capture_scope_binding)
    run = repo.create_ingest_run(IDENTITY)
    fd = os.open(config.source_path, os.O_RDONLY)
    info = os.fstat(fd)
    generation, _ = repo.transition_generation(binding=config.capture_scope_binding, boot_id=BOOT,
                                              physical=(info.st_dev, info.st_ino))
    health = HealthController(config.capture_scope_binding.capture_source_id)
    health.source_available()
    repo.persist_health(health, generation)
    try:
        yield SimpleNamespace(repo=repo, config=config, clock=clock, fd=fd, run=run,
            health=health, generation=generation, anchor=lambda offset: continuity_anchor(fd, offset))
    finally:
        os.close(fd)
        repo.close()


def seed_blocked(state, category="source_record_identity_conflict"):
    item = outcome(state.config.capture_scope_binding, generation=state.generation.source_generation_id)
    state.repo.ingest_batch([item], state.run, state.health, state.anchor)
    # Controlled damaged/replayed checkpoint fixture, not an operator recovery helper.
    with state.repo.transaction():
        state.repo.connection.execute("UPDATE network_metadata_checkpoint SET committed_byte_offset=0,continuity_anchor_start_offset=0,continuity_anchor_length=0,continuity_anchor_sha256=NULL")
        state.repo.connection.execute("UPDATE network_metadata_source_generations SET committed_byte_offset=0")
        if category == "source_record_identity_conflict":
            state.repo.connection.execute("UPDATE network_metadata_source_records SET source_record_sha256=?", ("0" * 64,))
        elif category == "normalizer_determinism_conflict":
            state.repo.connection.execute("UPDATE network_metadata_source_records SET semantic_payload_sha256=?", ("0" * 64,))
        else:
            state.repo.connection.execute("UPDATE network_metadata_source_records SET digest_state='expired',source_record_sha256=NULL,semantic_payload_sha256=NULL")
    state.repo.ingest_batch([item], state.run, state.health, state.anchor)
    return state.repo.load_active()
