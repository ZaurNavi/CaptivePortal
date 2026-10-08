"""R1-REC-01..15: current-schema existing-only local recovery, no keys."""
import sqlite3
from pathlib import Path
import pytest
from app.settings_control.repository import SettingsRepository
from app.settings_control.models import SettingsError
from app.settings_control.secret_recovery import clear_managed_secret
from app.settings_control.controller_secret import binding
from .stage4_helpers import secret_stack, secret_mutation
from .test_portal_stage5 import portal_write
from .test_schema_v4_portal import populated_v3, dump_tables
from . import mutation
from .test_controller_stage3 import write


def test_recovery_v4_keeps_all_domains_history_receipts_and_effective(tmp_path, monkeypatch):
    boot, filesystem = secret_stack(tmp_path)
    secret_mutation(boot)
    portal_write(boot, generation=1)
    mutation(boot, generation=2)
    write(boot, generation=3)
    repository = boot.admin_context.read_service.repository
    repository.activation(4, True)
    before = dump_tables(repository.db_path)
    overrides = repository.configured()[1]
    reads = filesystem.key_reads
    filesystem.key_valid = False
    def forbidden(*args, **kwargs): raise AssertionError("recovery must not initialize or migrate")
    monkeypatch.setattr(SettingsRepository, "initialize", forbidden)
    monkeypatch.setattr(SettingsRepository, "_migrate_v3", forbidden)
    reopened = SettingsRepository.open_existing_for_recovery(repository.db_path)
    assert clear_managed_secret(reopened, 4, filesystem=filesystem, operator=lambda: "local") == (5, True)
    assert reopened.configured() == (5, overrides)
    assert filesystem.key_reads == reads
    with reopened.transaction() as db:
        assert binding(db, 5) is None and binding(db, 4) is not None
        assert reopened.effective(db) == 4
    after = dump_tables(repository.db_path)
    for table in ("settings_mutation_audit", "settings_idempotency", "settings_activation_events", "settings_target_state"):
        assert after[table] == before[table]
    assert after["settings_secret_mutation_audit"][:-1] == before["settings_secret_mutation_audit"]
    assert clear_managed_secret(reopened, 5, filesystem=filesystem) == (5, False)
    unchanged = dump_tables(repository.db_path)
    with pytest.raises(SettingsError) as error: clear_managed_secret(reopened, 4, filesystem=filesystem)
    assert error.value.status == 412 and dump_tables(repository.db_path) == unchanged


def test_recovery_never_creates_or_migrates(tmp_path):
    missing = tmp_path / "missing.sqlite3"
    with pytest.raises(SettingsError): SettingsRepository.open_existing_for_recovery(missing)
    assert not missing.exists()
    path = tmp_path / "v3.sqlite3"
    populated_v3(path)
    before = path.read_bytes()
    with pytest.raises(SettingsError): SettingsRepository.open_existing_for_recovery(path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("damage", ["trigger", "integrity", "root", "target", "secret_ref", "unknown_override"])
def test_recovery_revalidates_schema_history_reference_integrity(tmp_path, damage):
    repository = SettingsRepository(tmp_path / "v4.sqlite3")
    with sqlite3.connect(repository.db_path) as db:
        if damage == "trigger": db.execute("DROP TRIGGER settings_secret_bindings_immutable_delete")
        elif damage == "integrity":
            db.execute("PRAGMA writable_schema=ON")
            db.execute("UPDATE sqlite_master SET rootpage=99999 WHERE name='settings_overrides'")
        elif damage == "root":
            db.execute("DROP TRIGGER settings_generations_immutable_update")
            db.execute("UPDATE settings_generations SET created_by_principal_name='fake'")
            from app.settings_control.repository import _TRIGGERS
            db.execute(next(sql for sql in _TRIGGERS if sql.startswith("CREATE TRIGGER settings_generations_immutable_update")))
        elif damage == "target": db.execute("DELETE FROM settings_target_state")
        else:
            db.execute("INSERT INTO settings_generations VALUES(1,0,'global','2026-10-08T00:00:00.000Z','platform_operator','operator','r')")
            if damage == "secret_ref": db.execute("INSERT INTO settings_secret_bindings VALUES(1,'OMADA_CLIENT_SECRET','11111111-1111-4111-8111-111111111111')")
            else: db.execute("INSERT INTO settings_overrides VALUES(1,'UNKNOWN','string',NULL,'x')")
    before = Path(repository.db_path).read_bytes()
    with pytest.raises(SettingsError): SettingsRepository.open_existing_for_recovery(repository.db_path)
    assert Path(repository.db_path).read_bytes() == before


def test_recovery_filesystem_security_remains_required(tmp_path):
    boot, filesystem = secret_stack(tmp_path)
    secret_mutation(boot)
    repository = SettingsRepository.open_existing_for_recovery(boot.admin_context.read_service.repository.db_path)
    filesystem.db_valid = False
    with pytest.raises(SettingsError, match="controller_secret_permissions_invalid"):
        clear_managed_secret(repository, 1, filesystem=filesystem)
    assert repository.configured()[0] == 1
