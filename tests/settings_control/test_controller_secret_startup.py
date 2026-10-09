from . import adopt
import logging
import pytest
from app.controllers.omada_config import build_omada_runtime_config, public_omada_snapshot
from app.settings_control.bootstrap import bootstrap_settings_control
from app.settings_control.models import SettingsError
from .stage4_helpers import secret_stack, secret_mutation, SENTINEL


def test_secret_definition_is_immutable_and_outside_ordinary_registry():
    from dataclasses import asdict, FrozenInstanceError
    from app.settings_control.controller_secret import ControllerSecretDefinitionV1, CONTROLLER_SECRET_DEFINITION
    from app.settings_control.definitions import SettingsDefinitionRegistry
    definition = ControllerSecretDefinitionV1()
    assert definition == CONTROLLER_SECRET_DEFINITION
    assert asdict(definition) == {"key": "OMADA_CLIENT_SECRET", "scope": "global",
        "secret_class": "write_only_secret", "apply_requirement": "main_service_restart",
        "activation_target": "captive-portal.service"}
    for name in asdict(definition):
        with pytest.raises(FrozenInstanceError):
            setattr(definition, name, "changed")
    registry = SettingsDefinitionRegistry()
    assert registry.get("OMADA_CLIENT_SECRET") is None
    assert len(tuple(registry)) == 46
    assert len(registry.for_domain("general")) == 12
    assert len(registry.for_domain("controller")) == 3
    assert len(registry.for_domain("portal")) == 14
    assert len(registry.for_domain("features")) == 17


def test_admin_metadata_boundary_contains_only_safe_facts(tmp_path, monkeypatch):
    from dataclasses import fields
    from app.settings_control.controller_secret import ControllerSecretMetadataService, OmadaClientSecretResolution
    from app.admin_web.controller_settings import ControllerConfigurationReadService
    boot, _ = secret_stack(tmp_path, client_secret=SENTINEL)
    metadata = boot.admin_context.secret_metadata_service
    secrets = boot.admin_context.secret_mutation_service.secrets
    assert type(metadata) is ControllerSecretMetadataService and metadata is not secrets
    assert {item.name for item in fields(metadata)} == {
        "repository", "filesystem", "deployment_presence", "deployment_source"}
    assert not any(hasattr(metadata, name) for name in ("_deployment", "resolve", "value", "secrets"))
    seen = set()
    def inspect(value):
        if id(value) in seen:
            return
        seen.add(id(value))
        assert not isinstance(value, OmadaClientSecretResolution)
        if isinstance(value, str):
            assert SENTINEL not in value
        elif isinstance(value, dict):
            for key, item in value.items():
                inspect(key)
                inspect(item)
        elif isinstance(value, (tuple, list, set, frozenset)):
            for item in value:
                inspect(item)
        elif not isinstance(value, type):
            inspect(getattr(value, "__dict__", {}))
            for name in getattr(type(value), "__slots__", ()):
                if hasattr(value, name):
                    inspect(getattr(value, name))
    inspect(metadata)
    config = build_omada_runtime_config(boot.runtime_settings, boot.controller_secret_resolution)
    public = public_omada_snapshot(config, frozenset({"OMADA_CLIENT_SECRET"}),
                                  boot.resolved_snapshot, boot.controller_secret_resolution)
    adopt(boot)
    read = ControllerConfigurationReadService(public, boot.admin_context.read_service, metadata)
    assert read.secret_metadata_service is metadata
    secret_mutation(boot)
    monkeypatch.setattr("app.settings_control.controller_secret.decrypt_secret",
                        lambda *_a: pytest.fail("Controller GET decrypt"))
    monkeypatch.setattr(secrets, "value", lambda *_a: pytest.fail("raw repository read"))
    current = read.read("disposable-request")
    assert current["fields"]["client_secret"]["configured_source"] == "managed_secret_override"
    assert current["fields"]["client_secret"]["pending_replacement"] is True
    assert SENTINEL not in repr(metadata) + repr(current)
    seen.clear()
    inspect(metadata)  # No managed-secret material appears after mutation either.


def test_managed_precedence_one_resolution_no_ordinary_override(tmp_path, monkeypatch):
    boot, filesystem = secret_stack(tmp_path)
    adopt(boot)
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
    adopt(restarted)
    from . import mutation
    assert mutation(restarted, generation=1).status == 201


@pytest.mark.parametrize("failure", ["key", "permissions", "wrong_key", "ciphertext", "missing_version"])
def test_managed_failure_no_fallback_or_effective_advance(tmp_path, failure):
    boot, filesystem = secret_stack(tmp_path)
    adopt(boot)
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
    adopt(boot)


def test_startup_and_ordinary_mutation_keep_secret_outside_validation_snapshot(tmp_path, monkeypatch):
    from app.settings_control.validation import SettingsValidationService
    from . import mutation
    original = SettingsValidationService.validate
    seen = []
    def checked(self, snapshot, *, secret_resolution, feature_plan=None):
        assert "client_secret" not in snapshot.values
        assert secret_resolution is not None
        seen.append((snapshot, secret_resolution.source, feature_plan))
        return original(self, snapshot, secret_resolution=secret_resolution, feature_plan=feature_plan)
    monkeypatch.setattr(SettingsValidationService, "validate", checked)
    boot, _ = secret_stack(tmp_path)
    assert seen[0][0] is boot.resolved_snapshot
    assert seen[0][2] is boot.feature_plan
    assert mutation(boot).status == 201
    assert len(seen) == 2 and all(source == "environment" for _, source, _ in seen)
    service = boot.admin_context.mutation_service
    service.secret_repository = None
    with pytest.raises(SettingsError) as error:
        # Invoke the real validator to prove there is no missing-resolution fallback.
        monkeypatch.setattr(SettingsValidationService, "validate", original)
        mutation(boot, generation=1)
    assert error.value.details == ({"key": None, "reason": "controller_prerequisite_invalid"},)
    assert service.repository.configured()[0] == 1
