"""Offline versioned transition, strict drift rejection and crash atomicity."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from contextlib import contextmanager

import pytest

from app.network_metadata_projection.models import ProjectionUnavailable, ProjectionConfig
from app.network_metadata_projection.repository import ProjectionRepository
from app.network_metadata_projection.schema import validate_schema, signature
from app.network_metadata_projection.ni03_top1_migration import (
    INDEX, migrate, validate_index_version, _records_digest, main,
)
from .test_protocol_latest_snapshot import seed

BASE = "6abbfe6b4546d7931696061f8703a7b413303a29"


@contextmanager
def connect(path):
    c = sqlite3.connect(path, isolation_level=None)
    c.execute("PRAGMA foreign_keys=ON")
    try:
        yield c
    finally:
        c.close()


@pytest.fixture(params=[False, True], ids=["core", "ni04-extension"])
def old_store(tmp_path, request):
    state = seed(tmp_path, 7, extension=request.param)
    state.repo.connection.execute(f"DROP INDEX {INDEX}")
    validate_index_version(state.repo.connection, installed=False)
    state.repo.close()
    return state


def test_upgrade_noop_restart_downgrade_old_code_and_all_records_preserved(old_store):
    state = old_store
    with connect(state.config.db_path) as c:
        before_schema, before_records = signature(c), _records_digest(c)
        with pytest.raises(ProjectionUnavailable):
            validate_schema(c)
    # Compare with ACTUAL baseline code, not merely our generated old signature.
    root = Path(__file__).resolve().parents[2]
    namespace = {"__package__": "app.network_metadata_projection", "__name__": "baseline_schema"}
    source = subprocess.check_output(["git", "show", BASE + ":app/network_metadata_projection/schema.py"], cwd=root)
    exec(compile(source, "baseline_schema.py", "exec"), namespace)
    with connect(state.config.db_path) as c:
        variant = namespace["validate_schema"](c, integrity=True)
    assert migrate(state.config, direction="up", maintenance_confirmed=True)
    assert not migrate(state.config, direction="up", maintenance_confirmed=True)
    with connect(state.config.db_path) as c:
        assert validate_schema(c, integrity=True) == variant
        assert c.execute("PRAGMA user_version").fetchone()[0] == 2
        assert _records_digest(c) == before_records
        assert tuple(row for row in signature(c) if row[1] != INDEX) == before_schema
        with pytest.raises(ProjectionUnavailable):
            namespace["validate_schema"](c)
    repo = ProjectionRepository(state.config).initialize()
    assert repo.service_recognition_extension_present == (variant == "CORE_PLUS_EXTENSION_V1")
    repo.close()
    assert migrate(state.config, direction="down", maintenance_confirmed=True)
    assert not migrate(state.config, direction="down", maintenance_confirmed=True)
    with connect(state.config.db_path) as c:
        assert namespace["validate_schema"](c, integrity=True) == variant
        assert signature(c) == before_schema and _records_digest(c) == before_records


@pytest.mark.parametrize("damage", [
    "CREATE INDEX alien ON device_network_metadata_edges(event_at)",
    "CREATE INDEX idx_projection_mac_family_event_latest ON device_network_metadata_edges(event_at)",
    "DROP TRIGGER immutable_device_network_metadata_edges",
    "PRAGMA user_version=1",
    "CREATE TABLE projection_service_recognition_partial(x)",
    "DROP INDEX idx_projection_mac_event",
])
def test_unknown_or_partial_schema_never_repaired(old_store, damage):
    with connect(old_store.config.db_path) as c:
        c.execute(damage)
        before = signature(c), _records_digest(c)
    with pytest.raises(ProjectionUnavailable):
        migrate(old_store.config, direction="up", maintenance_confirmed=True)
    with connect(old_store.config.db_path) as c:
        assert (signature(c), _records_digest(c)) == before


@pytest.mark.parametrize("point", ["preflight", "index_changed", "postflight"])
@pytest.mark.parametrize("direction", ["up", "down"])
def test_failure_before_commit_rolls_back_entire_transition(old_store, point, direction):
    if direction == "down":
        migrate(old_store.config, direction="up", maintenance_confirmed=True)
    with connect(old_store.config.db_path) as c:
        before = signature(c), _records_digest(c)
    class Crash(BaseException):
        pass
    def fail(stage):
        if stage == point:
            raise Crash()
    with pytest.raises(Crash):
        migrate(old_store.config, direction=direction, maintenance_confirmed=True, crash_point=fail)
    with connect(old_store.config.db_path) as c:
        assert (signature(c), _records_digest(c)) == before
    assert migrate(old_store.config, direction=direction, maintenance_confirmed=True)


@pytest.mark.parametrize("direction", ["up", "down"])
def test_actual_process_death_rolls_back_and_releases_writer_lock(old_store, direction):
    if direction == "down":
        migrate(old_store.config, direction="up", maintenance_confirmed=True)
    with connect(old_store.config.db_path) as c:
        before = signature(c), _records_digest(c)
    script = (
        "import os,sys; from app.network_metadata_projection.models import ProjectionConfig; "
        "from app.network_metadata_projection.ni03_top1_migration import migrate; "
        "migrate(ProjectionConfig(True,sys.argv[1]),direction=sys.argv[2],maintenance_confirmed=True,"
        "crash_point=lambda p: os._exit(73) if p=='index_changed' else None)")
    process = subprocess.run([sys.executable, "-c", script, old_store.config.db_path, direction], check=False)
    assert process.returncode == 73
    with connect(old_store.config.db_path) as c:
        assert (signature(c), _records_digest(c)) == before
        validate_index_version(c, installed=direction == "down")
    assert migrate(old_store.config, direction=direction, maintenance_confirmed=True)


@pytest.mark.parametrize("direction", ["up", "down"])
def test_committed_process_death_is_durable_then_retry_is_noop(old_store, direction):
    if direction == "down":
        migrate(old_store.config, direction="up", maintenance_confirmed=True)
    with connect(old_store.config.db_path) as c:
        records = _records_digest(c)
    script = (
        "import os,sys; from app.network_metadata_projection.models import ProjectionConfig; "
        "from app.network_metadata_projection.ni03_top1_migration import migrate; "
        "migrate(ProjectionConfig(True,sys.argv[1]),direction=sys.argv[2],maintenance_confirmed=True,"
        "crash_point=lambda p: os._exit(73) if p=='committed' else None)")
    process = subprocess.run([sys.executable, "-c", script, old_store.config.db_path, direction], check=False)
    assert process.returncode == 73
    with connect(old_store.config.db_path) as c:
        validate_index_version(c, installed=direction == "up")
        assert _records_digest(c) == records
    assert not migrate(old_store.config, direction=direction, maintenance_confirmed=True)


def test_writer_lock_and_explicit_maintenance_are_mandatory(old_store):
    for confirmation in (False, None, 1):
        with pytest.raises(ProjectionUnavailable):
            migrate(old_store.config, direction="up", maintenance_confirmed=confirmation)
    owner = ProjectionRepository(old_store.config)
    owner._lock()
    try:
        with pytest.raises(ProjectionUnavailable):
            migrate(old_store.config, direction="up", maintenance_confirmed=True)
    finally:
        owner.close()
    assert migrate(old_store.config, direction="up", maintenance_confirmed=True)


def test_missing_store_cli_disabled_config_cannot_create_db(tmp_path, monkeypatch, capsys):
    path = str(tmp_path / "absent.sqlite3")
    with pytest.raises(ProjectionUnavailable):
        migrate(ProjectionConfig(True, path), direction="up", maintenance_confirmed=True)
    assert not Path(path).exists() and not Path(path + ".writer.lock").exists()
    import app.network_metadata_projection.config as configuration
    monkeypatch.setattr(configuration, "projection_config_from_env", lambda: ProjectionConfig(False, path))
    assert main(["up", "--maintenance-confirmed"]) == 1
    assert capsys.readouterr().out == "NI03_TOP1_INDEX_V1:unavailable\n"
    assert not Path(path).exists()


def test_foreign_key_corruption_is_not_accepted_or_repaired(old_store):
    with connect(old_store.config.db_path) as c:
        c.execute("PRAGMA foreign_keys=OFF")
        c.execute("DELETE FROM projection_runs")
        assert c.execute("PRAGMA foreign_key_check").fetchone() is not None
        before = signature(c), _records_digest(c)
    with pytest.raises(ProjectionUnavailable):
        migrate(old_store.config, direction="up", maintenance_confirmed=True)
    with connect(old_store.config.db_path) as c:
        assert (signature(c), _records_digest(c)) == before


def test_failed_index_build_sqlite_error_leaves_old_schema(old_store):
    def failed_build(stage):
        if stage == "index_changed":
            raise sqlite3.OperationalError("synthetic full disk")
    with pytest.raises(ProjectionUnavailable):
        migrate(old_store.config, direction="up", maintenance_confirmed=True, crash_point=failed_build)
    with connect(old_store.config.db_path) as c:
        validate_index_version(c, installed=False)
    assert migrate(old_store.config, direction="up", maintenance_confirmed=True)
