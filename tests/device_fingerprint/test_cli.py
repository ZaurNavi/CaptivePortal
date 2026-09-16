from types import SimpleNamespace

import pytest

import app.device_fingerprint.cli as cli
import app.settings as settings_module
from app.artifact_identity import ArtifactIdentityError
from app.device_fingerprint.models import DeviceFingerprintMigrationRequired
from tests.device_fingerprint import config as fingerprint_config


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


def test_offline_migration_and_recovery_are_explicit_commands(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(settings_module, "DEVICE_FINGERPRINT_EVIDENCE_ENABLED", "false")
    monkeypatch.setattr(settings_module, "DEVICE_FINGERPRINT_DB_PATH", str(tmp_path / "db"))
    monkeypatch.setattr(settings_module, "DEVICE_FINGERPRINT_WRITER_LOCK_PATH", str(tmp_path / "lock"))
    monkeypatch.setattr(settings_module, "DEVICE_FINGERPRINT_MAX_DB_BYTES", "134217728")
    monkeypatch.setattr(settings_module, "DEVICE_FINGERPRINT_PRODUCERS_JSON", "invalid-disabled-producer-config")
    calls = []
    from app.device_fingerprint.storage_v2 import MigrationResult, RecoveryResult
    def migration(*args, **kwargs):
        calls.append(("migration", args, kwargs))
        return MigrationResult(str(tmp_path / "db"), 4096, "1:2", "a" * 36, 0, "b" * 64, 4096)
    def recovery(*args, **kwargs):
        calls.append(("recovery", args, kwargs))
        return RecoveryResult("c" * 36, 0)
    monkeypatch.setattr(cli, "migrate_v1_to_v2", migration)
    monkeypatch.setattr(cli, "recover_database_generation", recovery)
    monkeypatch.setattr(cli, "capture_loaded_artifact_identity", lambda *_args: (_ for _ in ()).throw(AssertionError("offline command must not start service")))
    assert cli.main(["migrate-v1-to-v2", "--backup-path", str(tmp_path / "backup")]) == 0
    assert cli.main(["recover-generation", "--trigger", "DATABASE_BACKUP_RESTORE"]) == 0
    output = capsys.readouterr().out.splitlines()
    assert len(output) == 2
    assert '"backup_sha256": "' + "b" * 64 + '"' in output[0]
    assert '"source_identity": "1:2"' in output[0]
    assert '"database_generation_id": "' + "c" * 36 + '"' in output[1]
    assert calls == [
        ("migration", (str(tmp_path / "db"),), {"writer_lock_path": str(tmp_path / "lock"), "backup_path": str(tmp_path / "backup"), "max_db_bytes": 134_217_728}),
        ("recovery", (str(tmp_path / "db"),), {"writer_lock_path": str(tmp_path / "lock"), "trigger": "DATABASE_BACKUP_RESTORE", "max_db_bytes": 134_217_728}),
    ]


@pytest.mark.parametrize("invalid_cap", ["67108863", "8589934593", "not-an-integer"])
def test_offline_commands_reject_invalid_configured_storage_cap(monkeypatch, tmp_path, invalid_cap):
    monkeypatch.setattr(settings_module, "DEVICE_FINGERPRINT_EVIDENCE_ENABLED", "false")
    monkeypatch.setattr(settings_module, "DEVICE_FINGERPRINT_MAX_DB_BYTES", invalid_cap)
    monkeypatch.setattr(cli, "migrate_v1_to_v2", lambda *_args, **_kwargs: pytest.fail("migration must not start"))
    monkeypatch.setattr(cli, "recover_database_generation", lambda *_args, **_kwargs: pytest.fail("recovery must not start"))
    assert cli.main(["migrate-v1-to-v2", "--backup-path", str(tmp_path / "backup")]) == 1
    assert cli.main(["recover-generation", "--trigger", "DATABASE_BACKUP_RESTORE"]) == 1


def test_disabled_run_ignores_unrelated_invalid_runtime_configuration(monkeypatch):
    monkeypatch.setattr(settings_module, "DEVICE_FINGERPRINT_EVIDENCE_ENABLED", "false")
    monkeypatch.setattr(settings_module, "DEVICE_FINGERPRINT_MAX_DB_BYTES", "not-an-integer")
    monkeypatch.setattr(settings_module, "DEVICE_FINGERPRINT_PRODUCERS_JSON", "invalid-disabled-producer-config")
    monkeypatch.setattr(settings_module, "DEVICE_FINGERPRINT_PORT", "invalid-disabled-port")
    assert cli.main(["run"]) == 0


def test_normal_run_does_not_attempt_offline_migration(monkeypatch, tmp_path):
    cfg = fingerprint_config(tmp_path)
    monkeypatch.setattr(cli, "get_settings", lambda: {})
    monkeypatch.setattr(cli, "device_fingerprint_config_from_settings", lambda _settings: cfg)
    monkeypatch.setattr(cli, "capture_loaded_artifact_identity", lambda *_args: SimpleNamespace(safe_fields=lambda: {}))
    monkeypatch.setattr(cli, "configure_device_fingerprint_logger", lambda: SimpleNamespace(error=lambda *a, **k: None))
    monkeypatch.setattr(cli, "DeviceFingerprintTelemetry", lambda *a, **k: SimpleNamespace(emit=lambda *a, **k: None))
    class Lock:
        def __enter__(self): return self
        def __exit__(self, *_args): pass
    monkeypatch.setattr(cli, "writer_lock", lambda _path: Lock())
    class Repository:
        def __init__(self, *_args, **_kwargs): pass
        def initialize(self): raise DeviceFingerprintMigrationRequired("Fingerprint repository migration is required")
        def close(self): pass
    monkeypatch.setattr(cli, "DeviceFingerprintRepository", Repository)
    monkeypatch.setattr(cli, "migrate_v1_to_v2", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("migration must not run")))
    monkeypatch.setattr(cli, "create_device_fingerprint_app", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("app must not run")))
    assert cli.main(["run"]) == 1
