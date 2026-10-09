"""Exact v5 migration preserves immutable rows, IDs and receipt bytes."""
import sqlite3
import pytest
from app.settings_control.repository import (
    SettingsRepository, _V1_DDL, _V2_DDL, _V4_DDL, _TRIGGERS, _SECRET_TRIGGERS, _DDL)
from app.settings_control.models import SettingsError
from app.settings_control.definitions import SettingsDefinitionRegistry
from .test_schema_v4_portal import populated_v3, dump_tables


def populated_v4(path):
    populated_v3(path)
    repository = SettingsRepository.__new__(SettingsRepository)
    repository.registry = SettingsDefinitionRegistry()
    with sqlite3.connect(path) as db:
        repository._migrate_v3(db)
        db.execute("INSERT INTO settings_overrides VALUES(7,'PORTAL_UI_TITLE_EN','string',NULL,'Guest seven')")
        db.execute("""INSERT INTO settings_mutation_audit VALUES(9,7,0,'platform_operator','operator','local','r','p',
            '2026-10-08T01:00:00.000Z','global',NULL,'PORTAL_UI_TITLE_EN','set','portal','string',
            NULL,'Guest seven','Guest','Guest seven','main_service_restart','captive-portal.service')""")
        db.execute("""INSERT INTO settings_idempotency VALUES(9,'platform_operator','operator','global','portal','p',
            'sha256_canonical_json_v1','hash',201,'{ "changed": true, "configured_generation": 7 }',
            7,1,'2026-10-08T01:00:00.000Z')""")
        db.execute("""INSERT INTO settings_idempotency VALUES(10,'platform_operator','operator','global','controller_secret','s',
            'hmac_sha256_controller_secret_v1','hash',200,'{ "configured_generation": 7, "changed": false }',
            7,0,'2026-10-08T01:00:00.000Z')""")


@pytest.mark.parametrize("populated", [False, True])
def test_exact_v4_to_v5_preserves_every_row_and_receipt_bytes(tmp_path, monkeypatch, populated):
    path = tmp_path / "v4.sqlite3"
    if populated:
        populated_v4(path)
    else:
        with sqlite3.connect(path) as db:
            for sql in (*_V4_DDL, *_TRIGGERS, *_SECRET_TRIGGERS):
                db.execute(sql)
            db.execute("PRAGMA user_version=4")
            db.execute("INSERT INTO settings_generations VALUES(0,NULL,'global','2026-10-08T00:00:00.000Z','system','settings_bootstrap',NULL)")
            db.execute("INSERT INTO settings_target_state VALUES('captive-portal.service',NULL,NULL)")
    before = dump_tables(path)
    trace, connect = [], sqlite3.connect
    def traced(*args, **kwargs):
        db = connect(*args, **kwargs)
        db.set_trace_callback(trace.append)
        return db
    monkeypatch.setattr(sqlite3, "connect", traced)
    repository = SettingsRepository(path)
    assert trace.count("BEGIN IMMEDIATE") == trace.count("COMMIT") == 1
    assert dump_tables(path) == before
    with repository.transaction() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 5
        assert repository.effective(db) == (7 if populated else None)
        assert not db.execute("SELECT name FROM sqlite_master WHERE name LIKE '%_v4'").fetchall()
        assert not db.execute("SELECT 1 FROM settings_overrides WHERE setting_key LIKE 'WEB_ADMIN_TRAFFIC%'").fetchall()
        assert not db.execute("SELECT 1 FROM settings_idempotency WHERE mutation_domain='features'").fetchall()
    SettingsRepository(path)
    assert dump_tables(path) == before


@pytest.mark.parametrize("version", [1, 2, 3])
def test_legacy_chain_reaches_exact_v5(tmp_path, version):
    path = tmp_path / "legacy.sqlite3"
    if version == 3:
        populated_v3(path)
    else:
        with sqlite3.connect(path) as db:
            for sql in (*( _V1_DDL if version == 1 else _V2_DDL), *_TRIGGERS):
                db.execute(sql)
            db.execute(f"PRAGMA user_version={version}")
            db.execute("INSERT INTO settings_generations VALUES(0,NULL,'global','2026-10-08T00:00:00.000Z','system','settings_bootstrap',NULL)")
            db.execute("INSERT INTO settings_target_state VALUES('captive-portal.service',NULL,NULL)")
    repository = SettingsRepository(path)
    with repository.transaction() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 5
        repository._validate_schema(db, _DDL)
        root = db.execute("SELECT created_by_principal_type,created_by_principal_name FROM settings_generations WHERE generation_id=0").fetchone()
        assert tuple(root) == ("system", "settings_bootstrap")


def test_v4_migration_failure_rolls_back_exact_bytes(tmp_path, monkeypatch):
    path = tmp_path / "v4.sqlite3"
    populated_v4(path)
    before = path.read_bytes()
    validate = SettingsRepository._validate_schema
    def fail(db, ddl):
        if ddl is _DDL:
            raise SettingsError("settings_store_unavailable")
        return validate(db, ddl)
    monkeypatch.setattr(SettingsRepository, "_validate_schema", staticmethod(fail))
    with pytest.raises(SettingsError):
        SettingsRepository(path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("damage", ["trigger", "column", "future", "bad_feature", "pre_v5_feature"])
def test_schema_and_feature_storage_fail_closed_without_repair(tmp_path, damage):
    path = tmp_path / "invalid.sqlite3"
    if damage == "pre_v5_feature":
        populated_v4(path)
    else:
        SettingsRepository(path)
    with sqlite3.connect(path) as db:
        if damage == "trigger":
            db.execute("DROP TRIGGER settings_idempotency_immutable_delete")
        elif damage == "column":
            db.execute("ALTER TABLE settings_overrides ADD COLUMN unauthorized TEXT")
        elif damage == "future":
            db.execute("PRAGMA user_version=6")
        else:
            generation = 7 if damage == "pre_v5_feature" else 1
            if generation == 1:
                db.execute("INSERT INTO settings_generations VALUES(1,0,'global','2026-10-08T01:00:00.000Z','platform_operator','operator','r')")
            db.execute("INSERT INTO settings_overrides VALUES(?,'WEB_ADMIN_TRAFFIC_ENABLED','string',NULL,?)",
                       (generation, "true" if damage == "pre_v5_feature" else "TRUE"))
    before = path.read_bytes()
    with pytest.raises(SettingsError):
        SettingsRepository(path)
    assert path.read_bytes() == before
