import os
import sqlite3
from dataclasses import replace
from pathlib import Path
from datetime import timedelta

import pytest

from app.network_metadata_projection.models import (PROJECTION_TRANSACTION_HEADROOM_BYTES as HEADROOM,
    ProjectionConfig, ProjectionCapacity, ProjectionUnavailable, ProjectionValidationError, RegistryEvaluation)
from app.network_metadata_projection.config import projection_config_from_env
from app.network_metadata_projection.repository import ProjectionRepository
from app.network_metadata_projection.cli import main
from .support import stack, source_record, SITE, MAC, IDENTITY


def test_default_off_no_db_lock_upstream_or_identity(tmp_path, monkeypatch):
    from app.network_metadata_projection import cli
    monkeypatch.setenv("NETWORK_METADATA_PROJECTION_ENABLED", "false")
    monkeypatch.setenv("NETWORK_METADATA_PROJECTION_DB_PATH", str(tmp_path / "unused.sqlite3"))
    def forbidden(*args, **kwargs):
        pytest.fail("disabled runtime accessed dependency")
    monkeypatch.setattr(cli, "capture_loaded_artifact_identity", forbidden)
    monkeypatch.setattr(cli, "network_attribution_config_from_env", forbidden)
    monkeypatch.setattr(cli, "ProjectionRepository", forbidden)
    assert main(["run"]) == 0
    assert not list(tmp_path.iterdir())
    assert projection_config_from_env({"NETWORK_METADATA_PROJECTION_ENABLED": "false", "NETWORK_METADATA_PROJECTION_MAX_DB_BYTES": "bad"}) == ProjectionConfig()


@pytest.mark.parametrize("value", ["0", "67108863", "68719476737", "NaN"])
def test_closed_capacity_config(value):
    with pytest.raises(ProjectionValidationError):
        projection_config_from_env({"NETWORK_METADATA_PROJECTION_ENABLED": "true", "NETWORK_METADATA_PROJECTION_MAX_DB_BYTES": value})


@pytest.mark.parametrize("name", ["batch_max_observations", "poll_interval_seconds",
    "attribution_retry_interval_seconds", "attribution_retry_batch_size", "registry_reconcile_interval_seconds",
    "registry_reconcile_batch_size", "retention_interval_seconds", "retention_batch_size",
    "retention_max_batches_per_pass", "shutdown_timeout_seconds"])
def test_processing_config_accepts_only_frozen_value(tmp_path, name):
    default = getattr(ProjectionConfig(), name)
    env = {"NETWORK_METADATA_PROJECTION_ENABLED": "true",
        "NETWORK_METADATA_PROJECTION_DB_PATH": str(tmp_path / "projection.sqlite3"),
        "NETWORK_METADATA_DB_PATH": str(tmp_path / "source.sqlite3"),
        "VISITOR_REGISTRY_DB_PATH": str(tmp_path / "registry.sqlite3"),
        "NETWORK_METADATA_PROJECTION_" + name.upper(): str(default)}
    assert getattr(projection_config_from_env(env), name) == default
    for changed in (default - 1, default + 1):
        env["NETWORK_METADATA_PROJECTION_" + name.upper()] = str(changed)
        with pytest.raises(ProjectionValidationError):
            projection_config_from_env(env)
        env["NETWORK_METADATA_PROJECTION_ENABLED"] = "false"
        assert projection_config_from_env(env) == ProjectionConfig()
        env["NETWORK_METADATA_PROJECTION_ENABLED"] = "true"


@pytest.mark.parametrize("capacity", [67108864, 17179869184, 68719476736])
def test_admitted_capacity_range_preserved(tmp_path, capacity):
    env = {"NETWORK_METADATA_PROJECTION_ENABLED": "true",
        "NETWORK_METADATA_PROJECTION_DB_PATH": str(tmp_path / "projection.sqlite3"),
        "NETWORK_METADATA_DB_PATH": str(tmp_path / "source.sqlite3"),
        "VISITOR_REGISTRY_DB_PATH": str(tmp_path / "registry.sqlite3"),
        "NETWORK_METADATA_PROJECTION_MAX_DB_BYTES": str(capacity)}
    assert projection_config_from_env(env).max_db_bytes == capacity


@pytest.mark.parametrize("damage", ["CREATE TABLE foreign_table(value)", "PRAGMA user_version=2", "DROP TABLE projection_pending_attribution"])
def test_foreign_schema_preserved_and_writer_lock(tmp_path, damage):
    value = stack(tmp_path)
    try:
        with pytest.raises(ProjectionUnavailable):
            ProjectionRepository(value.config).initialize()
    finally:
        value.repo.close()
    with sqlite3.connect(value.config.db_path) as connection:
        connection.execute(damage)
    before = Path(value.config.db_path).read_bytes()
    with pytest.raises(ProjectionUnavailable):
        ProjectionRepository(value.config).initialize()
    assert Path(value.config.db_path).read_bytes() == before


@pytest.mark.skipif(os.name != "posix", reason="Mandatory Linux writer/WAL proof")
def test_held_reader_pressure_defers_checkpoint_then_recovers(tmp_path):
    value = stack(tmp_path)
    reader = sqlite3.connect(value.config.db_path, isolation_level=None)
    try:
        reader.execute("BEGIN")
        reader.execute("SELECT * FROM projection_runtime_state").fetchall()
        value.service.poll()
        before = dict(value.repo.checkpoint(value.source.records[0].source_generation_id))
        # Unexpected journal is included in the real footprint, not an exemption.
        journal = Path(value.config.db_path + "-journal")
        journal.write_bytes(b"\0" * (value.config.max_db_bytes - value.repo.footprint() - HEADROOM + 1))
        value.source.records.append(source_record(1))
        with pytest.raises(ProjectionCapacity):
            value.service.poll()
        assert value.repo.live_state == "capacity_waiting_reader"
        assert dict(value.repo.checkpoint(value.source.records[0].source_generation_id)) == before
        assert value.repo.footprint() <= value.config.max_db_bytes
        reader.close()
        assert value.repo.maintain_capacity()
        value.service.poll()
        assert value.repo.checkpoint(value.source.records[0].source_generation_id)["last_record_start_byte_offset"] == 1
    finally:
        reader.close()
        value.repo.close()


def test_hard_cap_live_status_does_not_write_overflow(tmp_path):
    value = stack(tmp_path)
    try:
        before = value.repo.connection.total_changes
        Path(value.config.db_path + "-journal").write_bytes(b"\0" * value.config.max_db_bytes)
        value.repo.set_failure("source_unavailable", "source_unavailable")
        assert value.repo.live_state == "capacity_halted"
        assert value.repo.connection.total_changes == before
        assert value.repo.checkpoint(value.source.records[0].source_generation_id) is None
    finally:
        value.repo.close()


@pytest.mark.skipif(os.name != "posix", reason="Mandatory Linux post-commit capacity proof")
def test_post_commit_pressure_keeps_durable_disposition_and_auto_recovers(tmp_path):
    value = stack(tmp_path)
    reader = sqlite3.connect(value.config.db_path, isolation_level=None)
    journal = Path(value.config.db_path + "-journal")
    try:
        reader.execute("BEGIN")
        reader.execute("SELECT * FROM projection_runtime_state").fetchall()
        def sidecar_pressure(point):
            if point == "after_commit":
                journal.write_bytes(b"\0" * (value.config.max_db_bytes - value.repo.footprint() - HEADROOM + 1))
        value.repo.crash_point = sidecar_pressure
        value.service.poll()
        assert value.repo.live_state == "capacity_waiting_reader"
        checkpoint = dict(value.repo.checkpoint(value.source.records[0].source_generation_id))
        assert checkpoint["last_record_start_byte_offset"] == 0
        assert len(value.repo.existing_edges(value.source.records[0].observation_id)) == 2
        value.repo.crash_point = lambda _: None
        reader.close()
        assert value.repo.maintain_capacity()
        assert dict(value.repo.checkpoint(value.source.records[0].source_generation_id)) == checkpoint
        assert value.repo.footprint() <= value.config.max_db_bytes
    finally:
        reader.close()
        value.repo.close()


@pytest.mark.skipif(os.name != "posix", reason="Mandatory Linux fixed 16 MiB growth proof")
@pytest.mark.parametrize("pending", [False, True])
def test_maximum_256_observation_transaction_growth_under_fixed_headroom(tmp_path, pending, record_property):
    records = []
    for index in range(256):
        src = f"254.254.{100 + index // 78}.{100 + index % 78 * 2}"
        dst = f"254.254.{100 + index // 78}.{101 + index % 78 * 2}"
        records.append(source_record(9223372036854775550 + index, src_ip=src, dst_ip=dst,
                                    capture_source_id="x" * 64, network_scope_id="y" * 64,
                                    capture_scope_ipv4_cidrs=("0.0.0.0/0",)))
    value = stack(tmp_path, records)
    try:
        for index, record in enumerate(records):
            for role in ("src", "dst"):
                address = getattr(record, role + "_ip")
                number = index * 2 + (role == "dst")
                mac = "00:12:34:56:" + f"{number // 256:02X}:{number % 256:02X}"
                value.attribution.macs[address] = mac
                value.registry.values[mac] = RegistryEvaluation("authoritative", f"00000000-0000-4000-8000-{number:012x}")
                if pending and role == "dst":
                    value.attribution.states[address] = "unavailable"
        baseline, samples = value.repo.footprint(), []
        value.repo.crash_point = lambda point: samples.append(value.repo.footprint())
        value.service.poll()
        samples.append(value.repo.footprint())
        delta = max(samples) - baseline
        assert value.repo.connection.execute("SELECT count(*) FROM device_network_metadata_edges").fetchone()[0] == (256 if pending else 512)
        assert value.repo.connection.execute("SELECT count(*) FROM projection_site_mac_bindings").fetchone()[0] == (256 if pending else 512)
        assert value.repo.connection.execute("SELECT count(*) FROM projection_registry_binding_events").fetchone()[0] == (256 if pending else 512)
        assert value.repo.connection.execute("SELECT count(*) FROM projection_pending_attribution").fetchone()[0] == (256 if pending else 0)
        assert delta <= HEADROOM
        record_property("max_footprint_growth_bytes", delta)
        record_property("fixed_headroom_bytes", HEADROOM)
        print(f"NI02B_MAX_TRANSACTION pending={pending} delta_bytes={delta} headroom_bytes={HEADROOM}")
    finally:
        value.repo.close()
