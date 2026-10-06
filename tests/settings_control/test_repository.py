import sqlite3
import ast
from pathlib import Path
import pytest
from app.settings_control.repository import SettingsRepository
from app.settings_control.models import SettingsError
from . import stack, mutation


def test_physical_bootstrap_identity_and_idempotent_schema(tmp_path):
    repository = SettingsRepository(tmp_path / "settings.sqlite3")
    SettingsRepository(repository.db_path)
    with repository.transaction() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert db.execute("PRAGMA busy_timeout").fetchone()[0] == 1000
        root = db.execute("SELECT * FROM settings_generations").fetchone()
        assert tuple(root)[:3] == (0, None, "global")
        assert tuple(root)[4:] == ("system", "settings_bootstrap", None)
        assert root[3].endswith("Z")
        assert tuple(db.execute("SELECT * FROM settings_target_state").fetchone()) == ("captive-portal.service", None, None)
        for table in ("settings_overrides", "settings_mutation_audit", "settings_idempotency", "settings_activation_events"):
            assert db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] == 0
    assert repository.configured() == (0, {})


@pytest.mark.parametrize("mode", ["newer", "old_nonempty", "shape", "corrupt", "unknown_key"])
def test_incompatible_store_is_not_recreated(tmp_path, mode):
    path = tmp_path / "settings.sqlite3"
    if mode == "corrupt":
        path.write_bytes(b"not SQLite")
    else:
        repository = SettingsRepository(path)
        with sqlite3.connect(path) as db:
            if mode == "newer":
                db.execute("PRAGMA user_version=2")
            elif mode == "old_nonempty":
                db.execute("PRAGMA user_version=0")
            elif mode == "shape":
                db.execute("ALTER TABLE settings_target_state ADD COLUMN unexpected TEXT")
            else:
                db.execute("INSERT INTO settings_generations VALUES(1,0,'global','2026-10-06T00:00:00.000Z','platform_operator','operator','request')")
                db.execute("INSERT INTO settings_overrides VALUES(1,'UNKNOWN','integer',100)")
    before = path.read_bytes()
    with pytest.raises(SettingsError):
        SettingsRepository(path)
    assert path.read_bytes() == before


def test_history_immutability_fk_and_uniqueness(tmp_path):
    boot = stack(tmp_path)
    mutation(boot)
    repository = boot.admin_context.read_service.repository
    for sql in ("DELETE FROM settings_generations", "UPDATE settings_overrides SET integer_value=99",
                "DELETE FROM settings_mutation_audit", "UPDATE settings_idempotency SET result_changed=0",
                "INSERT INTO settings_overrides VALUES(999,'WEB_ADMIN_DEVICE_PAGE_SIZE','integer',100)",
                "INSERT INTO settings_overrides VALUES(1,'WEB_ADMIN_DEVICE_PAGE_SIZE','integer',100)"):
        with pytest.raises(SettingsError):
            with repository.transaction(write=True) as db:
                db.execute(sql)


def test_busy_writer_fails_without_success(tmp_path):
    boot = stack(tmp_path)
    db = sqlite3.connect(boot.admin_context.read_service.repository.db_path)
    db.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(SettingsError, match="settings_store_unavailable"):
            mutation(boot)
    finally:
        db.rollback(); db.close()
    assert boot.admin_context.read_service.repository.configured() == (0, {})


def test_settings_sqlite_access_is_owned_only_by_repository():
    package = Path(__file__).resolve().parents[2] / "app/settings_control"
    for path in package.glob("*.py"):
        if path.name == "repository.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {"execute", "executemany", "executescript", "connect"}, path.name
            if isinstance(node, ast.Import):
                assert all(alias.name != "sqlite3" for alias in node.names), path.name
            if isinstance(node, ast.ImportFrom):
                assert node.module != "sqlite3", path.name
