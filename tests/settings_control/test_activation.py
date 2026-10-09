from . import adopt
from types import SimpleNamespace
import pytest
from app.settings_control.models import SettingsError
from . import stack, mutation


def test_adopts_exact_g_not_new_configured_head(tmp_path):
    boot = stack(tmp_path)
    mutation(boot)
    adopt(boot)
    model = boot.admin_context.read_service.read()
    assert (model["configured_generation"], model["effective_generation"]) == (1, 0)
    adopt(boot)
    with boot.admin_context.read_service.repository.transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM settings_activation_events").fetchone()[0] == 2


def test_durable_failure_no_effective_advance(tmp_path):
    boot = stack(tmp_path)
    boot.activation_service.fail("settings_validation_failed")
    with boot.admin_context.read_service.repository.transaction() as db:
        assert boot.admin_context.read_service.repository.effective(db) is None
        assert db.execute("SELECT activation_result FROM settings_activation_events").fetchone()[0] == "failed"
    with pytest.raises(SettingsError):
        boot.activation_service.adopt(dict(boot.runtime_settings), None, None, feature_plan=boot.feature_plan)
    assert not boot.admin_context.read_service._adopted


def test_commit_failure_never_claims_adoption(tmp_path, monkeypatch):
    boot = stack(tmp_path)
    def unavailable(*_args, **_kwargs):
        raise SettingsError("settings_store_unavailable")
    monkeypatch.setattr(boot.activation_service.repository, "activation", unavailable)
    with pytest.raises(SettingsError):
        adopt(boot)
    assert not boot.admin_context.read_service._adopted


def test_no_activation_authority_in_admin_context(tmp_path):
    boot = stack(tmp_path)
    assert not hasattr(boot.admin_context, "activation_service")
    assert not hasattr(boot.admin_context.mutation_service, "adopt")


def test_absent_runtime_is_not_positive_configuration_failure(tmp_path):
    from tests.admin_web.conftest import enabled_settings
    boot = stack(tmp_path, **enabled_settings())
    with pytest.raises(SettingsError, match="settings_activation_unavailable"):
        boot.activation_service.adopt(boot.runtime_settings, None,
            SimpleNamespace(feature_plan=boot.feature_plan), feature_plan=boot.feature_plan)
    repository = boot.admin_context.read_service.repository
    with repository.transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM settings_activation_events").fetchone()[0] == 0
        assert repository.effective(db) is None
    with pytest.raises(SettingsError, match="settings_activation_failed"):
        boot.activation_service.adopt(boot.runtime_settings, SimpleNamespace(config=None),
            SimpleNamespace(feature_plan=boot.feature_plan), feature_plan=boot.feature_plan)
    with repository.transaction() as db:
        assert db.execute("SELECT activation_result FROM settings_activation_events").fetchone()[0] == "failed"
        assert repository.effective(db) is None
