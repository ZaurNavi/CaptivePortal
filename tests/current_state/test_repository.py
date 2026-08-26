from __future__ import annotations

import os
import sqlite3
import stat
import threading
from dataclasses import replace
from pathlib import Path

import pytest

from app.current_state.models import (
    CurrentStateConfigError,
    CurrentStateSchemaError,
    CurrentStateStorageError,
    CurrentStateValidationError,
)
from app.current_state import repository as repository_module
from app.current_state.repository import CurrentStateRepository

from .conftest import OTHER_SITE, SITE, ap_row, client_row, cycle


@pytest.fixture
def repository(config):
    repo = CurrentStateRepository(config)
    assert repo.initialize() is True
    return repo


def test_schema_v1_and_required_indexes(repository):
    with repository.read_connection() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        names = {row[0] for row in connection.execute("SELECT name FROM sqlite_schema WHERE type='index'")}
        assert "idx_current_cycles_kind_site_started" in names
        assert "idx_current_client_auth" in names
        assert "idx_current_client_ap" in names
        assert "idx_current_client_uptime" in names
        assert "idx_current_client_traffic" in names
        assert "idx_current_ap_status" in names
        assert "idx_current_client_cycle_mac" not in names


def test_existing_exact_database_reopens(repository):
    assert repository.initialize() is False


@pytest.mark.parametrize("message", ("database is locked", "database is busy"))
def test_existing_database_transient_contention_is_retryable(
    repository, monkeypatch, message
):
    monkeypatch.delattr(repository_module.sqlite3, "SQLITE_BUSY", raising=False)
    monkeypatch.delattr(repository_module.sqlite3, "SQLITE_LOCKED", raising=False)

    def busy(*_args, **_kwargs):
        raise sqlite3.OperationalError(message)

    monkeypatch.setattr(sqlite3, "connect", busy)
    with pytest.raises(CurrentStateStorageError):
        repository.initialize()


@pytest.mark.parametrize(
    ("sqlite_errorcode", "expected"),
    (
        (5, True),
        (6, True),
        (261, True),
        (262, True),
        (1, False),
    ),
)
def test_transient_contention_uses_stable_primary_codes_without_optional_constants(
    monkeypatch, sqlite_errorcode, expected
):
    monkeypatch.delattr(repository_module.sqlite3, "SQLITE_BUSY", raising=False)
    monkeypatch.delattr(repository_module.sqlite3, "SQLITE_LOCKED", raising=False)
    error = sqlite3.OperationalError("contention without a stable message")
    error.sqlite_errorcode = sqlite_errorcode

    assert repository_module._transient_sqlite_contention(error) is expected


class _FetchOne:
    def __init__(self, value):
        self._value = value

    def fetchone(self):
        return (self._value,)


class _QuickCheckConnection:
    def __init__(
        self,
        *,
        quick_check_result="ok",
        quick_check_error=None,
        invoke_progress=False,
    ):
        self.quick_check_result = quick_check_result
        self.quick_check_error = quick_check_error
        self.invoke_progress = invoke_progress
        self.progress_handler = None
        self.row_factory = None
        self.closed = False

    def execute(self, statement):
        if statement == "PRAGMA query_only=ON":
            return _FetchOne(None)
        if statement == "PRAGMA user_version":
            return _FetchOne(repository_module.SCHEMA_VERSION)
        if statement == "PRAGMA quick_check":
            if self.invoke_progress:
                assert self.progress_handler is not None
                assert self.progress_handler() == 1
            if self.quick_check_error is not None:
                raise self.quick_check_error
            return _FetchOne(self.quick_check_result)
        raise AssertionError(f"Unexpected SQL: {statement}")

    def set_progress_handler(self, callback, _steps):
        self.progress_handler = callback

    def close(self):
        self.closed = True


def _install_quick_check_connection(monkeypatch, connection):
    signature = (("table", "current_state_cycles", "current_state_cycles", "sql"),)
    monkeypatch.setattr(repository_module, "_schema_signature", lambda _connection: signature)
    monkeypatch.setattr(repository_module, "_expected_schema_signature", lambda: signature)
    monkeypatch.setattr(repository_module.sqlite3, "connect", lambda *_args, **_kwargs: connection)


def test_self_interrupted_quick_check_is_retryable_storage_error(
    repository, monkeypatch
):
    connection = _QuickCheckConnection(
        quick_check_error=sqlite3.OperationalError("interrupted"),
        invoke_progress=True,
    )
    _install_quick_check_connection(monkeypatch, connection)
    clock = iter((100.0, 110.001))
    monkeypatch.setattr(repository_module.time, "monotonic", lambda: next(clock))

    with pytest.raises(CurrentStateStorageError) as failure:
        repository.initialize()

    assert not isinstance(failure.value, CurrentStateSchemaError)
    assert connection.progress_handler is None
    assert connection.closed is True


def test_unrelated_interrupted_operational_error_remains_schema_error(
    repository, monkeypatch
):
    connection = _QuickCheckConnection(
        quick_check_error=sqlite3.OperationalError("interrupted"),
        invoke_progress=False,
    )
    _install_quick_check_connection(monkeypatch, connection)
    monkeypatch.setattr(repository_module.time, "monotonic", lambda: 100.0)

    with pytest.raises(CurrentStateSchemaError):
        repository.initialize()


def test_failed_quick_check_result_remains_schema_error(repository, monkeypatch):
    connection = _QuickCheckConnection(
        quick_check_result="database disk image is malformed"
    )
    _install_quick_check_connection(monkeypatch, connection)
    monkeypatch.setattr(repository_module.time, "monotonic", lambda: 100.0)

    with pytest.raises(CurrentStateSchemaError, match="integrity check failed"):
        repository.initialize()


def test_wrong_user_version_rejected_without_recreation(config):
    connection = sqlite3.connect(config.db_path)
    connection.execute("CREATE TABLE foreign_table(value TEXT)")
    connection.commit()
    connection.close()
    before = os.path.getsize(config.db_path)
    with pytest.raises(CurrentStateSchemaError):
        CurrentStateRepository(config).initialize()
    assert os.path.getsize(config.db_path) == before
    connection = sqlite3.connect(config.db_path)
    assert connection.execute("SELECT name FROM sqlite_schema WHERE name='foreign_table'").fetchone()
    connection.close()


def test_modified_or_extra_schema_rejected(repository):
    connection = sqlite3.connect(repository.config.db_path)
    connection.execute("CREATE TABLE foreign_table(value TEXT)")
    connection.commit()
    connection.close()
    with pytest.raises(CurrentStateSchemaError):
        repository.initialize()


def test_corrupt_existing_database_is_rejected_without_deletion(config):
    marker = b"not-a-sqlite-database"
    Path(config.db_path).write_bytes(marker)
    with pytest.raises(CurrentStateSchemaError):
        CurrentStateRepository(config).initialize()
    assert Path(config.db_path).read_bytes() == marker


def test_nonregular_target_rejected(config):
    os.mkdir(config.db_path)
    with pytest.raises(CurrentStateConfigError):
        CurrentStateRepository(config).initialize()


def test_target_symlink_rejected(config, tmp_path):
    target = tmp_path / "real.sqlite3"
    target.touch()
    try:
        os.symlink(target, config.db_path)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(CurrentStateConfigError):
        CurrentStateRepository(config).initialize()


def test_symlink_parent_rejected(enabled_settings, tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    try:
        os.symlink(real, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")
    enabled_settings["current_state_db_path"] = str(link / "current.sqlite3")
    from app.current_state.config import current_state_config_from_settings
    with pytest.raises(CurrentStateConfigError):
        CurrentStateRepository(current_state_config_from_settings(enabled_settings)).initialize()


def test_database_collision_rejected(enabled_settings):
    enabled_settings["observation_db_path"] = enabled_settings["current_state_db_path"]
    from app.current_state.config import current_state_config_from_settings
    with pytest.raises(CurrentStateConfigError):
        CurrentStateRepository(current_state_config_from_settings(enabled_settings)).initialize()


@pytest.mark.parametrize("key", [
    "observation_db_path",
    "visit_lifecycle_db_path",
    "visitor_registry_db_path",
    "portal_counter_db_path",
    "public_traffic_db_path",
])
def test_database_collision_rejected_for_every_sqlite_owner(enabled_settings, key):
    enabled_settings[key] = enabled_settings["current_state_db_path"]
    from app.current_state.config import current_state_config_from_settings
    with pytest.raises(CurrentStateConfigError):
        CurrentStateRepository(current_state_config_from_settings(enabled_settings)).initialize()


def test_public_web_tree_target_is_rejected(enabled_settings):
    from app.current_state.config import current_state_config_from_settings
    import app.current_state.repository as repository_module

    project_app = Path(repository_module.__file__).resolve().parents[1]
    enabled_settings["current_state_db_path"] = str(
        project_app / "admin_web" / "static" / "current-state.sqlite3"
    )
    with pytest.raises(CurrentStateConfigError):
        CurrentStateRepository(current_state_config_from_settings(enabled_settings)).initialize()


@pytest.mark.skipif(os.name != "posix", reason="POSIX parent mode contract")
def test_publicly_accessible_parent_is_rejected(enabled_settings, tmp_path):
    parent = tmp_path / "public-parent"
    parent.mkdir(mode=0o755)
    os.chmod(parent, 0o755)
    enabled_settings["current_state_db_path"] = str(parent / "current.sqlite3")
    from app.current_state.config import current_state_config_from_settings
    with pytest.raises(CurrentStateConfigError):
        CurrentStateRepository(current_state_config_from_settings(enabled_settings)).initialize()


@pytest.mark.skipif(os.name != "posix", reason="POSIX mode contract")
def test_database_and_sidecars_use_0640(repository):
    assert stat.S_IMODE(os.stat(repository.config.db_path).st_mode) == 0o640
    with repository._connect(write=True) as connection:
        connection.execute("CREATE TEMP TABLE t(value INTEGER)")
        for suffix in ("-wal", "-shm"):
            path = repository.config.db_path + suffix
            if os.path.exists(path):
                assert stat.S_IMODE(os.stat(path).st_mode) == 0o640


def test_atomic_client_publication_and_zero_snapshot(repository):
    repository.publish_cycle(cycle())
    with repository.read_connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM current_state_cycles").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM current_client_state").fetchone()[0] == 0
    parent = cycle(cycle_id="client-rows", items_stored=2)
    rows = [client_row(cycle_id="client-rows"), client_row(cycle_id="client-rows", mac="AA:BB:CC:DD:EE:02")]
    repository.publish_cycle(parent, client_rows=rows)
    with repository.read_connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM current_client_state WHERE cycle_id='client-rows'").fetchone()[0] == 2


def test_wal_reader_never_observes_half_published_cycle(repository, monkeypatch):
    import app.current_state.repository as repository_module

    inserted_parent = threading.Event()
    release_writer = threading.Event()
    original = repository_module._insert_rows

    def paused_insert(connection, table, columns, rows):
        inserted_parent.set()
        assert release_writer.wait(2.0)
        original(connection, table, columns, rows)

    monkeypatch.setattr(repository_module, "_insert_rows", paused_insert)
    parent = cycle(cycle_id="atomic", items_stored=2, items_seen=2)
    rows = [
        client_row(cycle_id="atomic"),
        client_row(cycle_id="atomic", mac="AA:BB:CC:DD:EE:02"),
    ]
    error = []

    def publish():
        try:
            repository.publish_cycle(parent, client_rows=rows)
        except Exception as exc:  # pragma: no cover - assertion reports detail
            error.append(exc)

    thread = threading.Thread(target=publish)
    thread.start()
    assert inserted_parent.wait(2.0)
    with repository.read_connection() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM current_state_cycles WHERE cycle_id='atomic'"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM current_client_state WHERE cycle_id='atomic'"
        ).fetchone()[0] == 0
    release_writer.set()
    thread.join(2.0)
    assert not thread.is_alive()
    assert error == []
    with repository.read_connection() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM current_state_cycles WHERE cycle_id='atomic'"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM current_client_state WHERE cycle_id='atomic'"
        ).fetchone()[0] == 2


def test_failed_cycle_is_not_empty_success(repository):
    repository.publish_cycle(cycle(cycle_id="failed", result="failed", items_seen=0))
    stored = repository.get_cycle("failed")
    assert stored.result == "failed"
    assert stored.complete is False


@pytest.mark.parametrize("result,complete", [("success", False), ("failed", True), ("partial", True), ("shutdown", True)])
def test_success_complete_invariant_rejected(repository, result, complete):
    item = replace(cycle(result=result), complete=complete)
    with pytest.raises(CurrentStateValidationError):
        repository.publish_cycle(item)


def test_repository_rejects_cross_site_and_cross_kind(repository):
    parent = cycle(cycle_id="parent", items_stored=1)
    with pytest.raises(CurrentStateValidationError):
        repository.publish_cycle(parent, client_rows=[client_row(cycle_id="parent", site_id=OTHER_SITE)])
    with pytest.raises(CurrentStateValidationError):
        repository.publish_cycle(parent, ap_rows=[ap_row(cycle_id="parent")])


def test_repository_rejects_invalid_identity_scope_and_observed_at(repository):
    parent = cycle(cycle_id="parent", items_stored=1)
    with pytest.raises(CurrentStateValidationError):
        repository.publish_cycle(
            parent,
            client_rows=[client_row(cycle_id="parent", mac="not-a-valid-mac!!")],
        )
    with pytest.raises(CurrentStateValidationError):
        repository.publish_cycle(
            parent,
            client_rows=[client_row(cycle_id="parent", ssid="Other")],
        )
    with pytest.raises(CurrentStateValidationError):
        repository.publish_cycle(
            parent,
            client_rows=[client_row(cycle_id="parent", observed_at="2026-08-23T10:00:01.000Z")],
        )


def test_database_composite_foreign_key_rejects_cross_site_and_kind(repository):
    repository.publish_cycle(cycle(cycle_id="parent"))
    connection = sqlite3.connect(repository.config.db_path)
    connection.execute("PRAGMA foreign_keys=ON")
    columns = ",".join(client_row().keys())
    placeholders = ",".join("?" for _ in client_row())
    bad_site = client_row(cycle_id="parent", site_id=OTHER_SITE)
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(f"INSERT INTO current_client_state ({columns}) VALUES ({placeholders})", tuple(bad_site.values()))
    bad_kind = client_row(cycle_id="parent", cycle_kind="ap")
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(f"INSERT INTO current_client_state ({columns}) VALUES ({placeholders})", tuple(bad_kind.values()))
    connection.close()


def test_read_connection_is_query_only(repository):
    with repository.read_connection() as connection:
        assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("DELETE FROM current_state_cycles")


def test_query_plans_use_required_indexes(repository):
    plans = repository.explain(
        "SELECT * FROM current_state_cycles WHERE kind=? AND site_id=? ORDER BY capture_started_at DESC LIMIT 1",
        ("client", SITE),
    )
    assert any("idx_current_cycles_kind_site_started" in item for item in plans)
    plans = repository.explain(
        "SELECT * FROM current_client_state WHERE cycle_id=? AND auth_classification=? ORDER BY client_mac LIMIT 101",
        ("x", "authorized"),
    )
    assert any("idx_current_client_auth" in item for item in plans)
