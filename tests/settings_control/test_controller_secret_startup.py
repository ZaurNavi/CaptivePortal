import logging
import pytest
from app.controllers.omada_config import build_omada_runtime_config, public_omada_snapshot
from app.settings_control.bootstrap import bootstrap_settings_control
from app.settings_control.models import SettingsError
from .stage4_helpers import secret_stack, secret_mutation, SENTINEL


def test_managed_precedence_one_resolution_no_ordinary_override(tmp_path, monkeypatch):
    boot, filesystem = secret_stack(tmp_path)
    boot.activation_service.adopt(boot.runtime_settings, None)
    secret_mutation(boot)
    base = {**boot.runtime_settings, "client_secret": ""}
    monkeypatch.setattr("requests.sessions.Session.request", lambda *_a, **_k: pytest.fail("pre-adoption I/O"))
    restarted = bootstrap_settings_control(base_settings=base, explicit_environment_names={"OMADA_CLIENT_SECRET"}, logger=logging.getLogger("s4"), secret_filesystem=filesystem)
    assert "client_secret" not in restarted.runtime_settings
    assert "client_secret" not in restarted.resolved_snapshot.values
    assert "client_secret" not in restarted.admin_context.read_service.base_settings
    resolution = restarted.controller_secret_resolution
    assert resolution.value == SENTINEL and resolution.source == "managed_secret_override"
    assert SENTINEL not in repr(restarted)
    config = build_omada_runtime_config(restarted.runtime_settings, resolution)
    public = public_omada_snapshot(config, frozenset({"OMADA_CLIENT_SECRET"}), restarted.resolved_snapshot, resolution)
    assert config.client_secret == SENTINEL and public.client_secret_source == "managed_secret_override"
    assert SENTINEL not in repr(config) + repr(public)
    with restarted.admin_context.read_service.repository.transaction() as db:
        assert restarted.admin_context.read_service.repository.effective(db) == 0
    restarted.activation_service.adopt(restarted.runtime_settings, None)
    from . import mutation
    assert mutation(restarted, generation=1).status == 201


@pytest.mark.parametrize("failure", ["key", "permissions", "wrong_key", "ciphertext", "missing_version"])
def test_managed_failure_no_fallback_or_effective_advance(tmp_path, failure):
    boot, filesystem = secret_stack(tmp_path)
    boot.activation_service.adopt(boot.runtime_settings, None)
    secret_mutation(boot)
    repository = boot.admin_context.read_service.repository
    if failure == "key": filesystem.key_valid = False
    if failure == "permissions": filesystem.db_valid = False
    if failure == "wrong_key": filesystem.master = bytes(32)
    if failure == "ciphertext":
        import sqlite3
        with sqlite3.connect(repository.db_path) as db:
            db.execute("DROP TRIGGER controller_secret_versions_immutable_update")
            db.execute("UPDATE controller_secret_versions SET ciphertext=?", (bytes(4116),))
            from app.settings_control.repository import _SECRET_TRIGGERS
            db.execute(_SECRET_TRIGGERS[0])
    if failure == "missing_version":
        with repository.transaction(write=True) as db:
            db.execute("DELETE FROM controller_secret_versions")
    with pytest.raises(SettingsError, match="controller_secret_"):
        bootstrap_settings_control(base_settings=boot.runtime_settings, explicit_environment_names=set(), logger=logging.getLogger("s4"), secret_filesystem=filesystem)
    with repository.transaction() as db:
        assert repository.effective(db) == 0
        row = db.execute("SELECT activation_result,safe_error_code FROM settings_activation_events ORDER BY event_id DESC LIMIT 1").fetchone()
        if failure != "missing_version":
            assert row[0] == "failed" and row[1].startswith("controller_secret_")
        else:
            # Initialization rejected invalid history before a usable repository
            # existed; no successful adoption or fabricated attestation occurs.
            assert row[0] == "adopted" and row[1] is None


@pytest.mark.parametrize("unavailable", ["key", "db_security"])
def test_deployment_without_key_startup_is_normal(tmp_path, unavailable):
    from .stage4_helpers import DisposableFilesystem
    filesystem = DisposableFilesystem()
    if unavailable == "key":
        filesystem.key_valid = False
    else:
        filesystem.db_valid = False
    boot, _ = secret_stack(tmp_path, filesystem=filesystem)
    assert boot.controller_secret_resolution.source == "environment"
    assert not boot.admin_context.secret_metadata_service.available()
    boot.activation_service.adopt(boot.runtime_settings, None)


def test_startup_and_ordinary_mutation_keep_secret_outside_validation_snapshot(tmp_path, monkeypatch):
    from app.settings_control.validation import SettingsValidationService
    from . import mutation
    original = SettingsValidationService.validate
    seen = []
    def checked(self, snapshot, *, secret_resolution):
        assert "client_secret" not in snapshot.values
        assert secret_resolution is not None
        seen.append((snapshot, secret_resolution.source))
        return original(self, snapshot, secret_resolution=secret_resolution)
    monkeypatch.setattr(SettingsValidationService, "validate", checked)
    boot, _ = secret_stack(tmp_path)
    assert seen[0][0] is boot.resolved_snapshot
    assert mutation(boot).status == 201
    assert len(seen) == 2 and all(source == "environment" for _, source in seen)
    service = boot.admin_context.mutation_service
    service.secret_repository = None
    with pytest.raises(SettingsError) as error:
        # Invoke the real validator to prove there is no missing-resolution fallback.
        monkeypatch.setattr(SettingsValidationService, "validate", original)
        mutation(boot, generation=1)
    assert error.value.details == ({"key": None, "reason": "controller_prerequisite_invalid"},)
    assert service.repository.configured()[0] == 1
