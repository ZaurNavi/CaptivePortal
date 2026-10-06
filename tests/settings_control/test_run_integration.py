import pytest
from types import SimpleNamespace
import run as runtime
from app.settings_control.models import SettingsError
from tests.visitor_registry.test_snapshot_runtime import _prepare_main
from . import stack


@pytest.mark.parametrize("failure", [None, "durable_write", "configuration"])
def test_exact_snapshot_durable_adoption_precedes_serving(tmp_path, monkeypatch, failure):
    events, _controller, _collector, _registry, app, _observed = _prepare_main(monkeypatch)
    monkeypatch.setattr(runtime, "capture_loaded_artifact_identity", lambda *_args:
                        SimpleNamespace(json_line=lambda: "synthetic settings startup test"))
    from tests.admin_web.conftest import enabled_settings
    admin_settings = enabled_settings() if failure == "configuration" else {}
    boot = stack(tmp_path, **admin_settings, host="127.0.0.1", port=8088, debug=False)
    # Use the real activation service and snapshot, with a disposable disabled Admin.
    monkeypatch.setattr(runtime, "bootstrap_settings_control", lambda **_kwargs: boot)
    original = boot.activation_service.repository.activation
    def activation(*args, **kwargs):
        events.append("durable_adoption")
        if failure == "durable_write":
            raise SettingsError("settings_store_unavailable")
        return original(*args, **kwargs)
    monkeypatch.setattr(boot.activation_service.repository, "activation", activation)
    monkeypatch.setattr(runtime, "_admin_web_runtime", SimpleNamespace(config=None) if failure == "configuration" else None)
    monkeypatch.setattr(runtime, "_configure_admin_web", lambda *_args: None)
    def factory(**kwargs):
        assert kwargs["settings"] is boot.runtime_settings
        # The old test helper only observes host; supply an otherwise equivalent fake app.
        events.append("create_app")
        return app
    monkeypatch.setattr(runtime, "create_app", factory)
    if failure:
        with pytest.raises(SettingsError):
            runtime.main()
        assert not app.run_calls
        if failure == "configuration":
            repository = boot.activation_service.repository
            with repository.transaction() as db:
                assert repository.effective(db) is None
                assert db.execute("SELECT activation_result FROM settings_activation_events").fetchone()[0] == "failed"
    else:
        runtime.main()
        assert events.index("durable_adoption") < events.index("app.run")
        assert boot.admin_context.read_service._adopted
