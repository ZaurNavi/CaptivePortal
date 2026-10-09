import pytest
from types import SimpleNamespace
import run as runtime
from app.settings_control.models import SettingsError
from tests.visitor_registry.test_snapshot_runtime import _prepare_main
from . import stack


def feature_composition(boot, monkeypatch):
    monkeypatch.setattr(runtime, "_analytics_runtime", SimpleNamespace(
        feature_plan=boot.feature_plan, historical_source_mode="base"))
    return SimpleNamespace(feature_plan=boot.feature_plan)



@pytest.mark.parametrize("failure", [None, "durable_write", "configuration"])
def test_exact_snapshot_durable_adoption_precedes_serving(tmp_path, monkeypatch, failure):
    events, _controller, _collector, _registry, app, _observed = _prepare_main(monkeypatch)
    monkeypatch.setattr(runtime, "capture_loaded_artifact_identity", lambda *_args:
                        SimpleNamespace(json_line=lambda: "synthetic settings startup test"))
    from tests.admin_web.conftest import enabled_settings
    admin_settings = enabled_settings() if failure == "configuration" else {}
    boot = stack(tmp_path, **admin_settings, host="127.0.0.1", port=8088, debug=False,
                 omada_url="https://controller.invalid", omada_id="installation",
                 client_id="application", client_secret="fixture-secret", verify_ssl=False)
    # Use the real activation service and snapshot, with a disposable disabled Admin.
    monkeypatch.setattr(runtime, "bootstrap_settings_control", lambda **_kwargs: boot)
    original = boot.activation_service.repository.activation
    def activation(*args, **kwargs):
        events.append("durable_adoption")
        if failure == "durable_write":
            raise SettingsError("settings_store_unavailable")
        return original(*args, **kwargs)
    monkeypatch.setattr(boot.activation_service.repository, "activation", activation)
    monkeypatch.setattr(runtime, "_admin_web_runtime", SimpleNamespace(config=None, feature_plan=boot.feature_plan) if failure == "configuration" else feature_composition(boot, monkeypatch))
    monkeypatch.setattr(runtime, "_configure_admin_web", lambda *_args, **_kwargs: None)
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
        assert "collector.start" not in events
        if failure == "configuration":
            repository = boot.activation_service.repository
            with repository.transaction() as db:
                assert repository.effective(db) is None
                assert db.execute("SELECT activation_result FROM settings_activation_events").fetchone()[0] == "failed"
    else:
        runtime.main()
        assert events.index("durable_adoption") < events.index("app.run")
        assert boot.admin_context.read_service._adopted


@pytest.mark.parametrize("failure", [None, "durable_write", "provider", "projection", "worker"])
def test_all_controller_consumers_follow_adoption(tmp_path, monkeypatch, failure):
    events, controller, collector, registry, app, observed = _prepare_main(monkeypatch)
    monkeypatch.setattr(runtime, "capture_loaded_artifact_identity", lambda *_:
        SimpleNamespace(json_line=lambda: "synthetic Stage3 identity"))
    boot = stack(tmp_path, host="127.0.0.1", port=8088, debug=False)
    monkeypatch.setattr(runtime, "bootstrap_settings_control", lambda **_: boot)
    original = boot.activation_service.repository.activation
    def activation(*args, **kwargs):
        if failure == "durable_write":
            raise SettingsError("settings_store_unavailable")
        result = original(*args, **kwargs)
        events.append("committed_adoption" if args[1] else "failed_attestation")
        return result
    monkeypatch.setattr(boot.activation_service.repository, "activation", activation)
    def start(name):
        def invoke(*args):
            assert boot.admin_context.read_service._adopted, "Controller I/O before adoption"
            events.append(name)
            if failure == "worker":
                raise RuntimeError("synthetic worker failure")
        return invoke
    monkeypatch.setattr(collector, "start", start("collector.start"))
    pending = SimpleNamespace(start=start("pending.start"), stop=lambda *_: None)
    observation = SimpleNamespace(prepare_read_boundary=lambda: events.append("observation.prepare"),
        start=start("observation.start"), stop=lambda: None)
    current = SimpleNamespace(start=start("current.start"), stop=lambda: None, read_service=None)
    monkeypatch.setattr(runtime, "create_pending_session_cleaner", lambda **_: pending)
    monkeypatch.setattr(runtime, "create_observation_foundation", lambda **_: observation)
    monkeypatch.setattr(runtime, "_configure_current_state", lambda *_: setattr(runtime, "_current_state_runtime", current))
    monkeypatch.setattr(runtime, "_configure_admin_web", lambda *_, **__: setattr(runtime, "_admin_web_runtime", feature_composition(boot, monkeypatch)))
    if failure == "provider":
        monkeypatch.setattr(runtime, "create_controller", lambda _: (_ for _ in ()).throw(RuntimeError("composition failure")))
    if failure == "projection":
        monkeypatch.setattr(runtime, "public_omada_snapshot", lambda *_: (_ for _ in ()).throw(RuntimeError("projection failure")))
    monkeypatch.setattr("requests.sessions.Session.request", lambda *a, **k: pytest.fail("live I/O"))
    if failure in ("durable_write", "provider"):
        with pytest.raises(Exception):
            runtime.main()
        assert not app.run_calls
        assert not any(name in events for name in ("pending.start", "observation.start", "current.start", "collector.start"))
        with boot.admin_context.read_service.repository.transaction() as db:
            assert boot.admin_context.read_service.repository.effective(db) is None
    else:
        runtime.main()
        for name in ("pending.start", "observation.start", "current.start", "collector.start", "app.run"):
            assert events.index("committed_adoption") < events.index(name)
        with boot.admin_context.read_service.repository.transaction() as db:
            assert boot.admin_context.read_service.repository.effective(db) == 0
            assert [row[0] for row in db.execute("SELECT activation_result FROM settings_activation_events")] == ["adopted"]


@pytest.mark.parametrize("failure", ["store", "configuration"])
def test_enabled_bootstrap_failure_precedes_provider(tmp_path, monkeypatch, failure):
    events, *_ = _prepare_main(monkeypatch)
    monkeypatch.setattr(runtime, "capture_loaded_artifact_identity", lambda *_:
        SimpleNamespace(json_line=lambda: "synthetic Stage3 identity"))
    from . import CONTROLLER_BASE
    settings = {**CONTROLLER_BASE, "web_admin_settings_enabled": True,
                "settings_db_path": str(tmp_path / "settings.sqlite3")}
    if failure == "store":
        settings["settings_db_path"] = str(tmp_path / "missing" / "bad.sqlite3")
    else:
        settings["omada_url"] = "invalid"
    monkeypatch.setattr(runtime, "get_settings", lambda: settings)
    with pytest.raises(SettingsError):
        runtime.main()
    assert "create_controller" not in events
    assert "create_app" not in events


@pytest.mark.parametrize("adoption_failure", [False, True])
def test_local_observation_preparation_precedes_composition_and_adoption(tmp_path, monkeypatch, adoption_failure):
    from app.analytics.runtime import _observation_read_service, _check_source
    from tests.observations.test_runtime import enabled, Telemetry
    from tests.observations.test_read_boundary_preparation import workers

    events, _, collector, _, app, _ = _prepare_main(monkeypatch)
    (tmp_path / "data").mkdir(mode=0o750)
    boot = stack(tmp_path, **enabled(tmp_path), host="127.0.0.1", port=8088, debug=False)
    monkeypatch.setattr(runtime, "bootstrap_settings_control", lambda **_: boot)
    monkeypatch.setattr(runtime, "capture_loaded_artifact_identity", lambda *_:
        SimpleNamespace(json_line=lambda: "synthetic FIX2 startup identity"))
    monkeypatch.setattr("requests.sessions.Session.request", lambda *a, **k: pytest.fail("network"))
    provider_calls = []

    def provider_call(name):
        assert boot.admin_context.read_service._adopted, "provider call before durable adoption"
        provider_calls.append(name)

    provider = SimpleNamespace(probe=provider_call)
    monkeypatch.setattr(runtime, "create_controller", lambda _: provider)
    real_factory = runtime.create_observation_foundation
    captured = {}

    def start(name, *, provider_capable=True):
        def invoke(*_args):
            assert boot.admin_context.read_service._adopted
            events.append(name)
            if provider_capable:
                provider.probe(name)
            return True
        return invoke

    def observation_factory(**kwargs):
        observation = real_factory(**{**kwargs, "telemetry": Telemetry()})
        captured["observation"] = observation
        initialize = observation.repository.initialize

        def local_initialize():
            assert not boot.admin_context.read_service._adopted
            assert provider_calls == []
            events.append("observation.initialize")
            return initialize()

        monkeypatch.setattr(observation.repository, "initialize", local_initialize)
        prepare = observation.prepare_read_boundary

        def local_prepare():
            events.append("observation.prepare")
            return prepare()

        monkeypatch.setattr(observation, "prepare_read_boundary", local_prepare)
        for name, worker in zip(("client", "ap", "cleanup", "integrity"), workers(observation)):
            monkeypatch.setattr(worker, "start", start("worker." + name,
                provider_capable=name in ("client", "ap")))
        original_start = observation.start

        def observation_start():
            events.append("observation.start")
            assert boot.admin_context.read_service._adopted
            return original_start()

        monkeypatch.setattr(observation, "start", observation_start)
        return observation

    monkeypatch.setattr(runtime, "create_observation_foundation", observation_factory)
    monkeypatch.setattr(runtime, "create_pending_session_cleaner", lambda **_:
        SimpleNamespace(start=start("pending.start")))
    monkeypatch.setattr(collector, "start", start("collector.start"))
    current = SimpleNamespace(start=start("current.start"), read_service=None)
    monkeypatch.setattr(runtime, "_configure_current_state", lambda *_:
        setattr(runtime, "_current_state_runtime", current))

    def analytics(*_):
        events.append("configure_analytics")
        observation = captured["observation"]
        assert observation.read_boundary_ready and observation.state == "disabled"
        assert _check_source("observations", _observation_read_service(observation)).available
        assert all(not worker.running for worker in workers(observation))
        assert provider_calls == []

    def admin(*_, **__):
        events.append("configure_admin_web")
        assert not boot.admin_context.read_service._adopted and provider_calls == []
        runtime._admin_web_runtime = feature_composition(boot, monkeypatch)

    monkeypatch.setattr(runtime, "_configure_analytics", analytics)
    monkeypatch.setattr(runtime, "_configure_admin_web", admin)
    activation = boot.activation_service.repository.activation

    def adopt(*args, **kwargs):
        assert provider_calls == []
        if adoption_failure:
            raise SettingsError("settings_store_unavailable")
        result = activation(*args, **kwargs)
        events.append("durable_adoption")
        return result

    monkeypatch.setattr(boot.activation_service.repository, "activation", adopt)
    if adoption_failure:
        with pytest.raises(SettingsError):
            runtime.main()
        assert provider_calls == [] and not app.run_calls
        assert "observation.start" not in events
    else:
        runtime.main()
        required = ["observation.prepare", "configure_analytics", "configure_admin_web",
                    "durable_adoption", "pending.start", "observation.start",
                    "current.start", "collector.start", "app.run"]
        positions = [events.index(name) for name in required]
        assert positions == sorted(positions)
        assert events.count("observation.initialize") == 1
        assert provider_calls == ["pending.start", "worker.client", "worker.ap", "current.start", "collector.start"]
