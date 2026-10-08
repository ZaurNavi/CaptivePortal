"""Disposable Stage-3 migration/typing/domain proof; no Controller or production I/O."""
import json
import logging
import sqlite3
import uuid
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from app.admin_web.controller_settings import ControllerConfigurationReadService
from app.admin_web.models import AdminPrincipal
from app.controllers.omada_config import build_omada_runtime_config, public_omada_snapshot
from app.settings_control.bootstrap import bootstrap_settings_control
from app.settings_control.definitions import SettingsDefinitionRegistry
from app.settings_control.models import SettingsError
from app.settings_control.repository import SettingsRepository, _V1_DDL, _TRIGGERS
from app.settings_control.resolver import resolve_settings
from app.settings_control.services import parse_changes
from . import CONTROLLER_BASE, stack, mutation

SECRET = "AS03_unique_sentinel_NOT_IN_NEW_PERSISTENCE_x9"
PRINCIPAL = AdminPrincipal("operator")


def write(boot, changes=None, *, generation=0, key=None, domain="controller"):
    return boot.admin_context.mutation_service.mutate(json.dumps({"changes": changes or [
        {"key": "OMADA_URL", "operation": "set", "value": " https://new.invalid:8043/ "}]}),
        principal=PRINCIPAL, source_ip="127.0.0.1", request_id=str(uuid.uuid4()),
        idempotency_key=key or str(uuid.uuid4()), expected_generation=generation, domain=domain)


def read(boot):
    return ControllerConfigurationReadService(public_omada_snapshot(build_omada_runtime_config(boot.runtime_settings, boot.controller_secret_resolution),
        frozenset(), boot.resolved_snapshot, boot.controller_secret_resolution), boot.admin_context.read_service,
        boot.admin_context.secret_metadata_service).read(str(uuid.uuid4()))


def v1_database(path):
    # The exact accepted Stage-1 DDL retained by the repository migration boundary.
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA foreign_keys=ON")
        for sql in (*_V1_DDL, *_TRIGGERS):
            db.execute(sql)
        db.execute("PRAGMA user_version=1")
        db.execute("INSERT INTO settings_generations VALUES(0,NULL,'global','2026-10-06T00:00:00.000Z','system','settings_bootstrap',NULL)")
        db.execute("INSERT INTO settings_generations VALUES(7,0,'global','2026-10-06T01:00:00.000Z','platform_operator','operator','request')")
        db.execute("INSERT INTO settings_overrides VALUES(7,'WEB_ADMIN_DEVICE_PAGE_SIZE','integer',123)")
        db.execute("INSERT INTO settings_target_state VALUES('captive-portal.service',7,'2026-10-06T02:00:00.000Z')")
        db.execute("INSERT INTO settings_activation_events VALUES(3,7,'captive-portal.service','2026-10-06T02:00:00.000Z','adopted',7,NULL)")
        db.execute("INSERT INTO settings_activation_events VALUES(4,7,'captive-portal.service','2026-10-06T03:00:00.000Z','failed',7,'settings_validation_failed')")
        db.execute("""INSERT INTO settings_mutation_audit VALUES(2,7,0,'platform_operator','operator',
            '127.0.0.1','request','identity','2026-10-06T01:00:00.000Z','global',NULL,
            'WEB_ADMIN_DEVICE_PAGE_SIZE','set',NULL,123,100,123,'main_service_restart','captive-portal.service')""")
        body = '{ "changed": true, "configured_generation": 7, "original": "body preserved" }'
        db.execute("INSERT INTO settings_idempotency VALUES(5,'platform_operator','operator','global','identity','hash',201,?,7,1,'2026-10-06T01:00:00.000Z')", (body,))
    return body


def test_v1_migration_preserves_all_history_and_replay_bytes(tmp_path):
    path = tmp_path / "v1.sqlite3"
    original = v1_database(path)
    with sqlite3.connect(path) as db:
        histories = {name: db.execute("SELECT * FROM " + name).fetchall() for name in
                     ("settings_generations", "settings_target_state", "settings_activation_events")}
        old_audit = db.execute("SELECT * FROM settings_mutation_audit").fetchone()
    repository = SettingsRepository(path)
    assert repository.configured() == (7, {"WEB_ADMIN_DEVICE_PAGE_SIZE": 123})
    with repository.transaction() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 3
        for name, rows in histories.items():
            assert [tuple(row) for row in db.execute("SELECT * FROM " + name)] == rows
        audit = db.execute("SELECT * FROM settings_mutation_audit").fetchone()
        v1_columns = [sql for sql in _V1_DDL if sql.startswith("CREATE TABLE settings_mutation_audit")][0]
        assert "setting_domain" not in v1_columns
        assert tuple(audit[name] for name in audit.keys() if name not in ("setting_domain", "value_type")) == old_audit
        assert audit["setting_domain"] == "general" and audit["value_type"] == "integer"
        replay = db.execute("SELECT * FROM settings_idempotency").fetchone()
        assert replay["result_response_json"] == original and replay["mutation_domain"] == "general"
        assert db.execute("SELECT string_value FROM settings_overrides").fetchone()[0] is None
    SettingsRepository(path)  # Reopening v2 is idempotent.


def test_migration_failure_rolls_back_schema_and_history(tmp_path, monkeypatch):
    path = tmp_path / "v1.sqlite3"
    v1_database(path)
    old = SettingsRepository._migrate_v1
    def fail(db):
        old(db)
        raise SettingsError("settings_store_unavailable")
    monkeypatch.setattr(SettingsRepository, "_migrate_v1", staticmethod(fail))
    before = path.read_bytes()
    with pytest.raises(SettingsError):
        SettingsRepository(path)
    assert path.read_bytes() == before
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        assert len(db.execute("PRAGMA table_info(settings_overrides)").fetchall()) == 4


@pytest.mark.parametrize("row", [
    ("OMADA_URL", "binary", None, "https://a.invalid"),
    ("OMADA_URL", "string", 3, "https://a.invalid"),
    ("OMADA_URL", "string", None, None),
    ("WEB_ADMIN_DEVICE_PAGE_SIZE", "integer", None, "3"),
])
def test_typed_ddl_rejects_invalid_rows(tmp_path, row):
    repository = SettingsRepository(tmp_path / "settings.sqlite3")
    with pytest.raises(SettingsError):
        with repository.transaction(write=True) as db:
            db.execute("INSERT INTO settings_overrides VALUES(0,?,?,?,?)", row)


@pytest.mark.parametrize("key,value", [("OMADA_CLIENT_SECRET", SECRET), ("VERIFY_SSL", "true"), ("OMADA_ID", " raw ")])
def test_repository_refuses_unadmitted_or_noncanonical_override(tmp_path, key, value):
    repository = SettingsRepository(tmp_path / "settings.sqlite3")
    with pytest.raises(SettingsError):
        with repository.transaction(write=True) as db:
            repository.create_generation(db, parent=0, principal=PRINCIPAL, request_id="request",
                created_at="2026-10-07T00:00:00.000Z", overrides={key: value})
    assert repository.configured() == (0, {})


def test_typed_coexistence_atomic_ownership_noop_clear_and_replay(tmp_path):
    boot = stack(tmp_path, client_secret=SECRET)
    boot.activation_service.adopt(boot.runtime_settings, None)
    key = str(uuid.uuid4())
    first = write(boot, key=key)
    assert first.status == 201 and first.body["changed_keys"] == ["OMADA_URL"]
    assert set(first.body) == {"api_version", "request_id", "scope", "resource", "changed", "changed_keys",
        "configured_generation", "effective_generation", "activation_state", "restart_required"}
    assert "https://new.invalid" not in json.dumps(first.body)
    noop = write(boot, generation=1)
    assert noop.status == 200 and noop.body["changed"] is False and noop.body["changed_keys"] == []
    mutation(boot, generation=1, key=key)  # Same UUID, different domain is independent.
    assert write(boot, key=key).body == first.body  # Stale CAS replays original receipt.
    with pytest.raises(SettingsError, match="idempotency_conflict"):
        write(boot, key=key, changes=[{"key": "OMADA_ID", "operation": "set", "value": "new"}])
    repository = boot.admin_context.read_service.repository
    assert repository.configured() == (2, {"OMADA_URL": "https://new.invalid:8043", "WEB_ADMIN_DEVICE_PAGE_SIZE": 120})
    cleared = write(boot, generation=2, changes=[{"key": "OMADA_URL", "operation": "clear_override"}])
    assert cleared.status == 201 and repository.configured() == (3, {"WEB_ADMIN_DEVICE_PAGE_SIZE": 120})
    with repository.transaction() as db:
        for table in ("settings_overrides", "settings_mutation_audit", "settings_idempotency", "settings_activation_events"):
            assert SECRET not in repr([tuple(row) for row in db.execute("SELECT * FROM " + table)])
        assert db.execute("SELECT COUNT(*) FROM settings_idempotency WHERE idempotency_key=?", (key,)).fetchone()[0] == 2


def test_explicit_same_environment_scalar_is_ownership_change(tmp_path):
    boot = stack(tmp_path)
    result = write(boot, changes=[{"key": "OMADA_ID", "operation": "set", "value": " installation "}])
    assert result.body["changed"] and result.body["configured_generation"] == 1


def test_shadowed_invalid_lower_value_and_clear_are_fail_closed(tmp_path):
    boot = stack(tmp_path)
    write(boot, changes=[{"key": "OMADA_URL", "operation": "set", "value": "https://new.invalid"}])
    masked = stack(tmp_path, omada_url="invalid-base")
    assert masked.runtime_settings["omada_url"] == "https://new.invalid"
    before = masked.admin_context.read_service.repository.configured()
    with pytest.raises(SettingsError, match="validation_failed"):
        write(masked, generation=1, changes=[{"key": "OMADA_URL", "operation": "clear_override"}])
    assert masked.admin_context.read_service.repository.configured() == before


def test_failed_receipt_persistence_rolls_back_everything(tmp_path, monkeypatch):
    boot = stack(tmp_path)
    import app.settings_control.repository as repository_module
    monkeypatch.setattr(repository_module, "canonical_json", lambda _body: "x" * 65537)
    with pytest.raises(SettingsError) as error:
        write(boot)
    assert (error.value.code, error.value.status) == ("internal_error", 500)
    repository = boot.admin_context.read_service.repository
    assert repository.configured() == (0, {})
    with repository.transaction() as db:
        for table in ("settings_overrides", "settings_mutation_audit", "settings_idempotency"):
            assert db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] == 0


def test_effective_generation_source_pending_and_store_outage(tmp_path):
    boot = stack(tmp_path, client_secret=SECRET)
    boot.activation_service.adopt(boot.runtime_settings, None)
    initial = read(boot)
    assert initial["api_version"] == "admin.settings.controller.v3"
    mutation(boot)
    general_pending = read(boot)
    assert general_pending["restart_required"] and general_pending["pending_controller_setting_count"] == 0
    write(boot, generation=1)
    pending = read(boot)
    assert pending["pending_controller_setting_count"] == 1
    assert pending["fields"]["controller_url"]["pending_source"] == "persisted_override"
    newer = stack(tmp_path, client_secret=SECRET)
    newer.activation_service.adopt(newer.runtime_settings, None)
    adopted = read(newer)
    assert adopted["effective_generation"] == 2 and adopted["pending_controller_setting_count"] == 0
    assert adopted["fields"]["controller_url"]["effective_source"] == "persisted_override"
    newer.admin_context.read_service.repository.db_path = str(tmp_path / "missing" / "broken.sqlite3")
    outage = read(newer)
    assert outage["store_state"] == "unavailable" and outage["configured_generation"] is None
    assert outage["effective_generation"] == 2
    for name in ("controller_url", "controller_id", "client_id"):
        assert all(outage["fields"][name][key] is None for key in
            ("configured_value", "configured_source", "persisted_override_value", "pending_value", "pending_source"))
    assert SECRET not in json.dumps(outage)
    assert SECRET not in repr(public_omada_snapshot(build_omada_runtime_config(newer.runtime_settings, newer.controller_secret_resolution), frozenset(), secret_resolution=newer.controller_secret_resolution))


@pytest.mark.parametrize("key", ["WEB_ADMIN_DEVICE_PAGE_SIZE", "OMADA_CLIENT_SECRET", "VERIFY_SSL", "UNKNOWN"])
def test_controller_domain_rejects_other_keys(key):
    with pytest.raises(SettingsError, match="invalid_request"):
        parse_changes(json.dumps({"changes": [{"key": key, "operation": "set", "value": "bad"}]}), domain="controller")


@pytest.mark.parametrize("value", [False, 1, None, [], {}])
def test_controller_set_requires_string(value):
    with pytest.raises(SettingsError, match="invalid_request"):
        parse_changes(json.dumps({"changes": [{"key": "OMADA_ID", "operation": "set", "value": value}]}), domain="controller")


@pytest.mark.parametrize("value", ["", " ", "https://a.invalid:0", "https://a.invalid/path", "https://user@a.invalid", "https://a.invalid?x", "https://a.invalid#x", "https://a.invalid:bad", "https://a .invalid"])
def test_canonical_validation_rejects_invalid_urls_without_echo(value):
    with pytest.raises(SettingsError, match="validation_failed") as error:
        parse_changes(json.dumps({"changes": [{"key": "OMADA_URL", "operation": "set", "value": value}]}), domain="controller")
    assert all(set(detail) == {"key", "reason"} for detail in error.value.details)


@pytest.mark.parametrize("scheme", ["http", "https"])
def test_one_validator_canonicalizes_runtime_and_settings(scheme):
    value = f" {scheme}://a.invalid:8043/ "
    change = parse_changes(json.dumps({"changes": [{"key": "OMADA_URL", "operation": "set", "value": value}]}), domain="controller")[0]
    runtime = build_omada_runtime_config({**CONTROLLER_BASE, "omada_url": value})
    assert change.value == runtime.controller_url == value.strip()[:-1]


def test_secret_prerequisite_failure_is_safe_and_atomic(tmp_path):
    boot = stack(tmp_path, client_secret=SECRET)
    read_service = boot.admin_context.read_service
    from dataclasses import replace
    secrets = boot.admin_context.secret_mutation_service.secrets
    secrets._deployment = replace(secrets._deployment, value="")
    with pytest.raises(SettingsError, match="validation_failed") as error:
        mutation(boot)
    assert error.value.details == ({"key": None, "reason": "controller_prerequisite_invalid"},)
    assert read_service.repository.configured() == (0, {})


def test_multi_field_invalidity_is_atomic_and_general_rejects_controller(tmp_path):
    boot = stack(tmp_path)
    with pytest.raises(SettingsError, match="validation_failed"):
        write(boot, changes=[{"key": "OMADA_ID", "operation": "set", "value": "valid"},
                             {"key": "OMADA_URL", "operation": "set", "value": "invalid"}])
    with pytest.raises(SettingsError, match="invalid_request"):
        write(boot, domain="general")
    assert boot.admin_context.read_service.repository.configured() == (0, {})


@pytest.mark.parametrize("key,internal", [("OMADA_ID", "omada_id"), ("OMADA_CLIENT_ID", "client_id")])
def test_no_new_id_charset_case_or_length_semantics_and_invalid_clear(tmp_path, key, internal):
    boot = stack(tmp_path)
    value = "MiXeD 中文 /: " + "x" * 16000
    write(boot, changes=[{"key": key, "operation": "set", "value": " " + value + " "}])
    assert boot.admin_context.read_service.repository.configured()[1][key] == value
    masked = stack(tmp_path, **{internal: ""})
    with pytest.raises(SettingsError, match="validation_failed"):
        write(masked, generation=1, changes=[{"key": key, "operation": "clear_override"}])
    assert masked.admin_context.read_service.repository.configured()[0] == 1


def test_replay_skips_candidate_validation(tmp_path, monkeypatch):
    boot = stack(tmp_path)
    key = str(uuid.uuid4())
    original = write(boot, key=key)
    monkeypatch.setattr(boot.admin_context.mutation_service.validation, "validate", lambda _: pytest.fail("replay validation"))
    assert write(boot, key=key).body == original.body


def test_corrupt_migration_shape_fails_without_recreation(tmp_path):
    path = tmp_path / "v1.sqlite3"
    v1_database(path)
    with sqlite3.connect(path) as db:
        db.execute("ALTER TABLE settings_overrides ADD COLUMN unexpected TEXT")
    before = path.read_bytes()
    with pytest.raises(SettingsError, match="settings_store_unavailable"):
        SettingsRepository(path)
    assert path.read_bytes() == before
