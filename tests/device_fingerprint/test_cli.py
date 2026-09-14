from types import SimpleNamespace

import app.device_fingerprint.cli as cli
from app.artifact_identity import ArtifactIdentityError


def test_disabled_run_exits_before_logger_identity_lock_db_or_app(monkeypatch):
    monkeypatch.setattr(cli, "get_settings", lambda: {})
    called = []
    monkeypatch.setattr(cli, "configure_device_fingerprint_logger", lambda: called.append("logger"))
    monkeypatch.setattr(cli, "capture_loaded_artifact_identity", lambda _name: called.append("identity"))
    assert cli.main(["run"]) == 0
    assert called == []


def test_enabled_run_uses_exact_direct_tls_app_signature(monkeypatch, tmp_path):
    cfg = SimpleNamespace(enabled=True, db_path=str(tmp_path / "db"), writer_lock_path=str(tmp_path / "lock"), max_db_bytes=67_108_864, bind_address="127.0.0.1", port=9443, tls_cert_path="cert", tls_key_path="key")
    monkeypatch.setattr(cli, "get_settings", lambda: {"ignored": True})
    monkeypatch.setattr(cli, "device_fingerprint_config_from_settings", lambda _settings: cfg)
    identity = SimpleNamespace(safe_fields=lambda: {})
    monkeypatch.setattr(cli, "capture_loaded_artifact_identity", lambda _name: identity)
    monkeypatch.setattr(cli, "configure_device_fingerprint_logger", lambda: SimpleNamespace(error=lambda *a, **k: None))
    calls = []
    class Repository:
        def __init__(self, *a, **k): pass
        def initialize(self): calls.append("initialize")
        def close(self): calls.append("close")
    monkeypatch.setattr(cli, "DeviceFingerprintRepository", Repository)
    class Runtime:
        def __init__(self, config, repository, registry, **kwargs): self.repository=repository
        def initialize(self): self.repository.initialize()
        def configure_registry(self, registry): calls.append("registry")
        def start_maintenance(self): calls.append("thread")
        def mark_ready(self): calls.append("ready")
        def signal_stop(self, *args): pass
        def finalize(self, release_lock=None): self.repository.close(); release_lock(); return True
    monkeypatch.setattr(cli, "DeviceFingerprintRuntime", Runtime)
    class App:
        def run(self, **kwargs): calls.append(kwargs)
    monkeypatch.setattr(cli, "create_device_fingerprint_app", lambda *a, **k: App())
    class Lock:
        def __enter__(self): calls.append("lock")
        def __exit__(self, *args): calls.append("unlock")
    monkeypatch.setattr(cli, "writer_lock", lambda _path: Lock())
    monkeypatch.setattr(cli, "signal", SimpleNamespace(SIGTERM=1, SIGINT=2, signal=lambda *a: None))
    monkeypatch.setattr(cli, "DeviceFingerprintTelemetry", lambda *a, **k: SimpleNamespace(emit=lambda *a, **k: None))
    assert cli.main(["run"]) == 0
    assert calls.index("lock") < calls.index("initialize") < calls.index("registry") < calls.index("thread") < calls.index("ready")
    assert calls.count("thread") == 1
    kwargs = next(item for item in calls if isinstance(item, dict))
    assert kwargs == {"host": "127.0.0.1", "port": 9443, "debug": False, "use_reloader": False, "threaded": True, "ssl_context": ("cert", "key"), "request_handler": cli.DeviceFingerprintSafeRequestHandler}


def test_artifact_identity_failure_exits_before_lock_db_and_app(monkeypatch, tmp_path):
    cfg = SimpleNamespace(enabled=True)
    monkeypatch.setattr(cli, "get_settings", lambda: {})
    monkeypatch.setattr(cli, "device_fingerprint_config_from_settings", lambda _settings: cfg)
    errors = []
    monkeypatch.setattr(cli, "configure_device_fingerprint_logger", lambda: SimpleNamespace(error=lambda *args: errors.append(args)))
    monkeypatch.setattr(cli, "capture_loaded_artifact_identity", lambda _name: (_ for _ in ()).throw(ArtifactIdentityError()))
    monkeypatch.setattr(cli, "writer_lock", lambda _path: (_ for _ in ()).throw(AssertionError("lock must not be acquired")))
    assert cli.main(["run"]) == 1
    assert errors
