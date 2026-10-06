import sqlite3
import uuid
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import pytest
from app.settings_control.models import SettingsError
from . import stack, mutation


def test_changed_noop_replay_audit_full_snapshot(tmp_path):
    boot = stack(tmp_path)
    boot.activation_service.adopt(boot.runtime_settings, None)
    key = str(uuid.uuid4())
    first = mutation(boot, key=key)
    assert first.status == 201 and first.body["changed"]
    assert first.body["configured_generation"] == 1 and first.body["effective_generation"] == 0
    assert first.body["activation_state"] == "pending_main_restart" and first.body["restart_required"]
    assert len(first.body["settings"]) == 12
    noop_key = str(uuid.uuid4())
    noop = mutation(boot, generation=1, key=noop_key)
    assert noop.status == 200 and not noop.body["changed"]
    mutation(boot, generation=1, changes=[{"key": "WEB_ADMIN_VISIT_PAGE_SIZE", "operation": "set", "value": 140}])
    newer = stack(tmp_path)
    newer.activation_service.adopt(newer.runtime_settings, None)
    assert mutation(boot, key=key).body == first.body
    assert mutation(boot, generation=1, key=noop_key).body == noop.body
    with pytest.raises(SettingsError, match="idempotency_conflict"):
        mutation(boot, key=key, changes=[{"key": "WEB_ADMIN_DEVICE_PAGE_SIZE", "operation": "set", "value": 130}])
    repository = boot.admin_context.read_service.repository
    with repository.transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM settings_generations").fetchone()[0] == 3
        assert db.execute("SELECT COUNT(*) FROM settings_mutation_audit").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM settings_idempotency").fetchone()[0] == 3
        row = db.execute("SELECT * FROM settings_mutation_audit ORDER BY audit_id LIMIT 1").fetchone()
        assert row["previous_persisted_override"] is None and row["new_persisted_override"] == 120
        assert row["principal_type"] == "platform_operator"


def test_clear_override_and_atomic_validation_failure(tmp_path):
    boot = stack(tmp_path, web_admin_device_page_size="115")
    mutation(boot)
    cleared = mutation(boot, generation=1, changes=[{"key": "WEB_ADMIN_DEVICE_PAGE_SIZE", "operation": "clear_override"}])
    assert cleared.body["settings"][0]["configured_value"] == 115
    assert cleared.body["settings"][0]["persisted_override_value"] is None
    with pytest.raises(SettingsError, match="validation_failed"):
        mutation(boot, generation=2, changes=[{"key": "WEB_ADMIN_DEVICE_PAGE_SIZE", "operation": "set", "value": 130},
                                           {"key": "WEB_ADMIN_VISIT_PAGE_SIZE", "operation": "set", "value": 501}])
    assert boot.admin_context.read_service.repository.configured() == (2, {})


def test_concurrent_head_cas_exactly_one_child(tmp_path):
    boot = stack(tmp_path)
    def write(_index):
        try:
            return mutation(boot).status
        except SettingsError as error:
            return error.status
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(write, range(2))) == [201, 412]
    assert boot.admin_context.read_service.repository.configured()[0] == 1


def test_disabled_consumer_and_silence_are_not_failure(tmp_path):
    boot = stack(tmp_path)
    model = boot.admin_context.read_service.read()
    assert model["settings"][0]["activation_state"] == "runtime_unavailable"
    boot.activation_service.adopt(boot.runtime_settings, None)
    model = boot.admin_context.read_service.read()
    assert all(item["consumer_state"] == "consumer_disabled" and item["effective_value"] is None for item in model["settings"])
    mutation(boot)
    assert boot.admin_context.read_service.read()["settings"][0]["activation_state"] == "pending_main_restart"


def test_change_and_object_order_preserve_idempotent_result(tmp_path):
    boot = stack(tmp_path)
    key = str(uuid.uuid4())
    changes = [{"key": "WEB_ADMIN_DEVICE_PAGE_SIZE", "operation": "set", "value": 120},
               {"key": "WEB_ADMIN_VISIT_PAGE_SIZE", "operation": "set", "value": 130}]
    first = mutation(boot, key=key, changes=changes)
    reversed_changes = [dict(reversed(list(change.items()))) for change in reversed(changes)]
    replay = mutation(boot, key=key, changes=reversed_changes)
    assert replay.status == first.status == 201
    assert replay.body == first.body


def test_read_side_replay_and_conflict_need_no_writer(tmp_path, monkeypatch):
    boot = stack(tmp_path)
    key = str(uuid.uuid4())
    original = mutation(boot, key=key)
    mutation(boot, generation=1, changes=[{"key": "WEB_ADMIN_VISIT_PAGE_SIZE", "operation": "set", "value": 140}])
    repository = boot.admin_context.read_service.repository
    transaction = repository.transaction

    @contextmanager
    def read_only_replay(*, write=False):
        assert not write, "Existing idempotency must not acquire a writer"
        with transaction() as db:
            yield db

    monkeypatch.setattr(repository, "transaction", read_only_replay)
    with sqlite3.connect(repository.db_path, isolation_level=None) as competitor:
        competitor.execute("BEGIN IMMEDIATE")
        try:
            replay = mutation(boot, key=key)
            assert replay.status == original.status == 201
            assert replay.body == original.body
            with pytest.raises(SettingsError, match="idempotency_conflict") as error:
                mutation(boot, key=key, changes=[{"key": "WEB_ADMIN_DEVICE_PAGE_SIZE", "operation": "set", "value": 130}])
            assert error.value.status == 409
        finally:
            competitor.rollback()


def test_writer_rechecks_identity_after_read_side_miss(tmp_path, monkeypatch):
    boot = stack(tmp_path)
    key = str(uuid.uuid4())
    original = mutation(boot, key=key)
    repository = boot.admin_context.read_service.repository
    calls = []
    idempotency = repository.idempotency
    def miss(*_args):
        calls.append("read_lookup")
        return None
    def recheck(*args):
        calls.append("writer_recheck")
        return idempotency(*args)
    monkeypatch.setattr(repository, "lookup_idempotency", miss)
    monkeypatch.setattr(repository, "idempotency", recheck)
    # Stale If-Match must not defeat a success found by the mandatory re-check.
    replay = mutation(boot, key=key)
    assert replay.body == original.body and replay.status == original.status
    assert calls == ["read_lookup", "writer_recheck"]
    assert repository.configured()[0] == 1
