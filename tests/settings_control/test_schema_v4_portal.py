"""Exact v3-to-v4 forward migration, no historical row rewriting."""
import sqlite3
import uuid
import pytest
from app.settings_control.repository import SettingsRepository, _V3_DDL, _TRIGGERS, _SECRET_TRIGGERS
from app.settings_control.models import SettingsError


def populated_v3(path):
    version = str(uuid.uuid4())
    with sqlite3.connect(path) as db:
        for sql in (*_V3_DDL, *_TRIGGERS, *_SECRET_TRIGGERS): db.execute(sql)
        db.execute("PRAGMA user_version=3")
        db.execute("INSERT INTO settings_generations VALUES(0,NULL,'global','2026-10-08T00:00:00.000Z','system','settings_bootstrap',NULL)")
        db.execute("INSERT INTO settings_generations VALUES(7,0,'global','2026-10-08T01:00:00.000Z','platform_operator','operator','r')")
        db.execute("INSERT INTO settings_target_state VALUES('captive-portal.service',7,'2026-10-08T01:00:00.000Z')")
        db.execute("INSERT INTO settings_overrides VALUES(7,'WEB_ADMIN_DEVICE_PAGE_SIZE','integer',123,NULL)")
        db.execute("INSERT INTO settings_overrides VALUES(7,'OMADA_ID','string',NULL,'installation-7')")
        db.execute("INSERT INTO controller_secret_versions VALUES(?,'OMADA_CLIENT_SECRET',1,?,?,?)", (version, b'n' * 12, b'x' * 4116, '2026-10-08T01:00:00.000Z'))
        db.execute("INSERT INTO settings_secret_bindings VALUES(7,'OMADA_CLIENT_SECRET',?)", (version,))
        db.execute("INSERT INTO settings_activation_events VALUES(3,7,'captive-portal.service','2026-10-08T01:00:00.000Z','adopted',7,NULL)")
        db.execute("""INSERT INTO settings_mutation_audit VALUES(2,7,0,'platform_operator','operator','127.0.0.1','r','i',
            '2026-10-08T01:00:00.000Z','global',NULL,'OMADA_ID','set','controller','string',NULL,'installation-7',
            'installation','installation-7','main_service_restart','captive-portal.service')""")
        db.execute("""INSERT INTO settings_secret_mutation_audit VALUES(2,7,0,'platform_operator','operator','127.0.0.1','r','i',
            '2026-10-08T01:00:00.000Z','global',NULL,'OMADA_CLIENT_SECRET','replace_secret',0,1,'environment','managed_secret_override',
            'main_service_restart','captive-portal.service')""")
        db.execute("""INSERT INTO settings_idempotency VALUES(5,'platform_operator','operator','global','controller','i',
            'sha256_canonical_json_v1','hash',201,'{ "configured_generation": 7, "changed": true }',7,1,'2026-10-08T01:00:00.000Z')""")
    return version


def dump_tables(path):
    with sqlite3.connect(path) as db:
        return {row[0]: db.execute('SELECT * FROM "' + row[0] + '"').fetchall() for row in
                db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()}


def test_populated_v3_migrates_one_transaction_and_preserves_every_row(tmp_path, monkeypatch):
    path = tmp_path / "v3.sqlite3"
    populated_v3(path)
    before = dump_tables(path)
    traces = []
    connect = sqlite3.connect
    def traced(*args, **kwargs):
        db = connect(*args, **kwargs); db.set_trace_callback(traces.append); return db
    monkeypatch.setattr(sqlite3, "connect", traced)
    repository = SettingsRepository(path)
    assert sum(sql == "BEGIN IMMEDIATE" for sql in traces) == 1
    assert sum(sql == "COMMIT" for sql in traces) == 1
    assert dump_tables(path) == before
    assert repository.configured() == (7, {"WEB_ADMIN_DEVICE_PAGE_SIZE": 123, "OMADA_ID": "installation-7"})
    with repository.transaction() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 5
        assert repository.effective(db) == 7
        assert db.execute("SELECT 1 FROM settings_overrides WHERE setting_key LIKE 'PORTAL_%'").fetchone() is None
        assert not db.execute("SELECT name FROM sqlite_master WHERE name LIKE '%_v3'").fetchall()
    SettingsRepository(path)


def test_migration_failure_rolls_back_all_ddl_and_rows(tmp_path, monkeypatch):
    path = tmp_path / "v3.sqlite3"
    populated_v3(path)
    original = path.read_bytes()
    validate = SettingsRepository._validate_schema
    from app.settings_control.repository import _DDL
    def fail(db, ddl):
        if ddl is _DDL: raise SettingsError("settings_store_unavailable")
        return validate(db, ddl)
    monkeypatch.setattr(SettingsRepository, "_validate_schema", staticmethod(fail))
    with pytest.raises(SettingsError): SettingsRepository(path)
    assert path.read_bytes() == original


def test_v3_cannot_contain_preexisting_portal_overrides(tmp_path):
    path = tmp_path / "invalid-v3.sqlite3"
    populated_v3(path)
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO settings_overrides VALUES(7,'PORTAL_UI_TITLE_EN','string',NULL,'unexpected')")
    original = path.read_bytes()
    with pytest.raises(SettingsError): SettingsRepository(path)
    assert path.read_bytes() == original


@pytest.mark.parametrize("corruption", ["trigger", "column", "future_version", "invalid_portal"])
def test_v4_schema_and_invalid_durable_values_fail_closed(tmp_path, corruption):
    path = tmp_path / "settings.sqlite3"
    SettingsRepository(path)
    with sqlite3.connect(path) as db:
        if corruption == "trigger": db.execute("DROP TRIGGER settings_idempotency_immutable_update")
        elif corruption == "column": db.execute("ALTER TABLE settings_idempotency ADD COLUMN unexpected TEXT")
        elif corruption == "future_version": db.execute("PRAGMA user_version=6")
        else:
            db.execute("INSERT INTO settings_generations VALUES(1,0,'global','2026-10-08T01:00:00.000Z','platform_operator','operator','r')")
            db.execute("INSERT INTO settings_overrides VALUES(1,'PORTAL_UI_TITLE_EN','string',NULL,' bad ')")
    before = path.read_bytes()
    with pytest.raises(SettingsError, match="settings_store_unavailable"): SettingsRepository(path)
    assert path.read_bytes() == before


def test_portal_sqlite_audit_text_type_constraints(tmp_path):
    repository = SettingsRepository(tmp_path / "v4.sqlite3")
    for value in (5, None, b"text"):
        with pytest.raises(SettingsError):
            with repository.transaction(write=True) as db:
                repository.append_mutation_audit(db, generation=0, parent=0, principal=type('P', (), {'principal_type': 'platform_operator', 'username': 'operator'})(),
                    source_ip='local', request_id='r', idempotency_key='i', timestamp='2026-10-08T00:00:00.000Z', key='PORTAL_UI_TITLE_EN',
                    operation='set', previous_override=None, new_override=value, previous_value='old', new_value=value,
                    apply_requirement='main_service_restart', activation_target='captive-portal.service', domain='portal', value_type='string')
