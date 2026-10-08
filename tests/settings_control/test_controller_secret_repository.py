import json
import sqlite3
import uuid
import pytest
from app.settings_control.repository import SettingsRepository, _V2_DDL, _TRIGGERS
from app.settings_control.controller_secret import binding, validate_secret_history
from app.settings_control.models import SettingsError, TARGET
from . import mutation
from .stage4_helpers import secret_stack, secret_mutation, SENTINEL


def test_v2_migration_preserves_history_and_receipts(tmp_path):
    path = tmp_path / "settings.sqlite3"
    with sqlite3.connect(path) as db:
        for sql in (*_V2_DDL, *_TRIGGERS): db.execute(sql)
        db.execute("PRAGMA user_version=2")
        db.execute("INSERT INTO settings_generations VALUES(0,NULL,'global','2026-10-01T00:00:00.000Z','system','settings_bootstrap',NULL)")
        db.execute("INSERT INTO settings_generations VALUES(1,0,'global','2026-10-01T00:00:01.000Z','platform_operator','operator','request')")
        db.execute("INSERT INTO settings_target_state VALUES(?,1,'2026-10-01T00:00:02.000Z')", (TARGET,))
        db.execute("INSERT INTO settings_activation_events VALUES(1,1,?,'2026-10-01T00:00:02.000Z','adopted',1,NULL)", (TARGET,))
        db.execute("INSERT INTO settings_overrides VALUES(1,'OMADA_ID','string',NULL,'changed')")
        db.execute("INSERT INTO settings_overrides VALUES(1,'WEB_ADMIN_DEVICE_PAGE_SIZE','integer',125,NULL)")
        for key, domain, kind, old, new in (
                ("OMADA_ID", "controller", "string", "installation", "changed"),
                ("WEB_ADMIN_DEVICE_PAGE_SIZE", "general", "integer", 100, 125)):
            db.execute("""INSERT INTO settings_mutation_audit (
                generation_id,parent_generation_id,principal_type,principal_name,source_ip,
                request_id,idempotency_key,timestamp_utc,scope_type,scope_id,setting_key,operation,
                setting_domain,value_type,previous_persisted_override,new_persisted_override,
                previous_configured_value,new_configured_value,apply_requirement,activation_target)
                VALUES(1,0,'platform_operator','operator','local','request','key',
                '2026-10-01T00:00:01.000Z','global',NULL,?,'set',?,?,NULL,?,?,?,
                'main_service_restart',?)""", (key, domain, kind, new, old, new, TARGET))
        receipt = '{"configured_generation":1,"changed":true}'
        db.execute("INSERT INTO settings_idempotency VALUES(1,'platform_operator','operator','global','controller','key',?,201,?,1,1,'2026-10-01T00:00:01.000Z')", ("a" * 64, receipt))
        before = {table: db.execute(f"SELECT * FROM {table}").fetchall() for table in (
            "settings_generations", "settings_overrides", "settings_target_state", "settings_activation_events", "settings_mutation_audit")}
    repository = SettingsRepository(path)
    with repository.transaction() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 3
        for table, rows in before.items(): assert [tuple(row) for row in db.execute(f"SELECT * FROM {table}")] == rows
        row = db.execute("SELECT * FROM settings_idempotency").fetchone()
        assert row["request_fingerprint_kind"] == "sha256_canonical_json_v1"
        assert row["request_fingerprint"] == "a" * 64 and row["result_response_json"] == receipt
        for table in ("controller_secret_versions", "settings_secret_bindings", "settings_secret_mutation_audit"):
            assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_binding_copy_both_domains_gc_and_historical_refs(tmp_path):
    boot, _ = secret_stack(tmp_path)
    boot.activation_service.adopt(boot.runtime_settings, None)
    secret_mutation(boot)
    repository = boot.admin_context.read_service.repository
    with repository.transaction() as db: first = binding(db, 1)
    mutation(boot, generation=1)
    ordinary = boot.admin_context.mutation_service
    from app.admin_web.models import AdminPrincipal
    ordinary.mutate(json.dumps({"changes": [{"key": "OMADA_ID", "operation": "set", "value": "different"}]}),
        principal=AdminPrincipal("operator"), source_ip="local", request_id=str(uuid.uuid4()), idempotency_key=str(uuid.uuid4()), expected_generation=2, domain="controller")
    with repository.transaction() as db:
        assert binding(db, 2) == binding(db, 3) == first
    repository.activation(3, True)
    secret_mutation(boot, generation=3, value="pending-two")
    secret_mutation(boot, generation=4, value="pending-three")
    with repository.transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM controller_secret_versions").fetchone()[0] == 2
        assert binding(db, 4) is not None
        assert db.execute("SELECT 1 FROM controller_secret_versions WHERE secret_version_id=?", (binding(db, 4),)).fetchone() is None
        validate_secret_history(db)
    repository.activation(5, False, "controller_configuration_adoption_failed")
    with repository.transaction() as db: assert db.execute("SELECT COUNT(*) FROM controller_secret_versions").fetchone()[0] == 2
    repository.activation(5, True)
    with repository.transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM controller_secret_versions").fetchone()[0] == 1
        validate_secret_history(db)
    SettingsRepository(repository.db_path)


@pytest.mark.parametrize("failure", ["receipt", "audit", "generation"])
def test_mutation_transaction_failure_rolls_back_everything(tmp_path, monkeypatch, failure):
    boot, _ = secret_stack(tmp_path)
    repository = boot.admin_context.read_service.repository
    target = boot.admin_context.secret_mutation_service.secrets if failure == "audit" else repository
    attribute = {"receipt": "save_idempotency", "audit": "audit", "generation": "create_generation"}[failure]
    def fail(*_a, **_k): raise RuntimeError("synthetic write failure")
    monkeypatch.setattr(target, attribute, fail)
    with pytest.raises(RuntimeError): secret_mutation(boot)
    with repository.transaction() as db:
        assert repository.head(db) == 0
        for table in ("controller_secret_versions", "settings_secret_bindings", "settings_secret_mutation_audit", "settings_idempotency"):
            assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_live_reference_and_closed_schema_fail_closed(tmp_path):
    boot, _ = secret_stack(tmp_path)
    secret_mutation(boot)
    repository = boot.admin_context.read_service.repository
    with repository.transaction(write=True) as db: db.execute("DELETE FROM controller_secret_versions")
    with pytest.raises(SettingsError, match="controller_secret_reference_missing"): repository.initialize()


def test_immutable_bindings_audit_versions_and_no_plaintext_db(tmp_path, caplog):
    boot, _ = secret_stack(tmp_path)
    secret_mutation(boot)
    repository = boot.admin_context.read_service.repository
    for sql in ("UPDATE controller_secret_versions SET created_at_utc='changed'", "DELETE FROM settings_secret_bindings", "UPDATE settings_secret_mutation_audit SET source_ip='changed'"):
        with pytest.raises(SettingsError):
            with repository.transaction(write=True) as db: db.execute(sql)
    with repository.transaction() as db:
        for table in ("settings_overrides", "settings_secret_mutation_audit", "settings_idempotency"):
            assert SENTINEL not in repr([tuple(row) for row in db.execute(f"SELECT * FROM {table}")])
        assert db.execute("SELECT COUNT(*) FROM settings_secret_bindings WHERE generation_id=0").fetchone()[0] == 0
    assert SENTINEL.encode() not in (tmp_path / "settings.sqlite3").read_bytes()
    assert SENTINEL not in caplog.text
