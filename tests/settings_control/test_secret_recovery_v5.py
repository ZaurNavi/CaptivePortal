"""Current v5 break-glass recovery carries Features without secret readback."""
import pytest
from app.settings_control.repository import SettingsRepository
from app.settings_control.secret_recovery import clear_managed_secret
from app.settings_control.controller_secret import binding
from app.settings_control.models import SettingsError
from .stage4_helpers import DisposableFilesystem
from app.admin_web.models import AdminPrincipal
from app.settings_control.controller_secret import ControllerSecretRepository
from .test_schema_v4_portal import dump_tables
from .test_schema_v5_features import populated_v4


def test_v5_recovery_preserves_features_history_receipts_and_effective(tmp_path, monkeypatch):
    # Opaque retained synthetic ciphertext: recovery must never decrypt it.
    path = tmp_path / "settings.sqlite3"
    populated_v4(path)
    repository = SettingsRepository(path)
    principal = AdminPrincipal("operator")
    with repository.transaction(write=True) as db:
        overrides = {**repository.overrides(db, 7), "WEB_ADMIN_TRAFFIC_HISTORY_ENABLED": "true"}
        generation = repository.create_generation(db, parent=7, principal=principal,
            request_id="r", created_at="2026-10-09T00:00:00.000Z", overrides=overrides)
        repository.append_mutation_audit(db, generation=generation, parent=7, principal=principal,
            source_ip="local", request_id="r", idempotency_key="feature", timestamp="2026-10-09T00:00:00.000Z",
            key="WEB_ADMIN_TRAFFIC_HISTORY_ENABLED", operation="set", previous_override=None,
            new_override="true", previous_value="false", new_value="true", domain="features", value_type="string",
            apply_requirement="main_service_restart", activation_target="captive-portal.service")
        repository.save_idempotency(db, principal, "feature", "hash", 201,
            {"configured_generation": generation, "changed": True}, "features")
    repository.activation(generation, True)
    filesystem = DisposableFilesystem()
    before = dump_tables(repository.db_path)
    overrides = repository.configured()[1]
    reads = filesystem.key_reads
    filesystem.key_valid = False
    def forbidden(*args, **kwargs):
        pytest.fail("recovery must not initialize, migrate, resolve or decrypt")
    monkeypatch.setattr(SettingsRepository, "initialize", forbidden)
    monkeypatch.setattr(SettingsRepository, "_migrate_v4", forbidden)
    monkeypatch.setattr(ControllerSecretRepository, "resolve", forbidden)
    monkeypatch.setattr("app.settings_control.controller_secret.decrypt_secret", forbidden)
    reopened = SettingsRepository.open_existing_for_recovery(repository.db_path)
    assert clear_managed_secret(reopened, generation, filesystem=filesystem, operator=lambda: "local") == (generation + 1, True)
    assert filesystem.key_reads == reads
    assert reopened.configured() == (generation + 1, overrides)
    assert overrides["WEB_ADMIN_TRAFFIC_HISTORY_ENABLED"] == "true"
    with reopened.transaction() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 5
        assert binding(db, generation + 1) is None and binding(db, generation) is not None
        assert reopened.effective(db) == generation
    after = dump_tables(repository.db_path)
    for table in ("settings_mutation_audit", "settings_idempotency", "settings_activation_events", "settings_target_state"):
        assert after[table] == before[table]
    assert after["settings_secret_mutation_audit"][:-1] == before["settings_secret_mutation_audit"]
    assert clear_managed_secret(reopened, generation + 1, filesystem=filesystem) == (generation + 1, False)
    unchanged = dump_tables(repository.db_path)
    with pytest.raises(SettingsError) as error:
        clear_managed_secret(reopened, 2, filesystem=filesystem)
    assert error.value.status == 412 and dump_tables(repository.db_path) == unchanged


def test_recovery_refuses_missing_or_old_v4_without_migration(tmp_path):
    missing = tmp_path / "missing.sqlite3"
    with pytest.raises(SettingsError):
        SettingsRepository.open_existing_for_recovery(missing)
    assert not missing.exists()
    old = tmp_path / "v4.sqlite3"
    populated_v4(old)
    before = old.read_bytes()
    with pytest.raises(SettingsError):
        SettingsRepository.open_existing_for_recovery(old)
    assert old.read_bytes() == before
