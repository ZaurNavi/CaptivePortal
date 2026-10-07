import pytest
from app.network_metadata import cli
from . import configuration, IDENTITY


def test_disabled_zero_operational_side_effects(monkeypatch):
    monkeypatch.delenv("NETWORK_METADATA_ENABLED", raising=False)
    def forbidden(*_, **__):
        pytest.fail("disabled operational side effect")
    for name in ("configure_logger", "capture_loaded_artifact_identity", "WriterLock", "NetworkMetadataRepository",
                 "FingerprintCaptureHealthAdapterV1", "NetworkMetadataService"):
        monkeypatch.setattr(cli, name, forbidden)
    assert cli.main(["run"]) == 0


def test_invalid_configuration_safe(monkeypatch, capsys):
    monkeypatch.setenv("NETWORK_METADATA_ENABLED", "TRUE")
    assert cli.main(["run"]) == 2
    assert "TRUE" not in capsys.readouterr().err


def test_identity_failure_safe(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "network_metadata_config_from_env", lambda: configuration(tmp_path))
    monkeypatch.setattr(cli, "capture_loaded_artifact_identity", lambda *_: (_ for _ in ()).throw(RuntimeError("secret-payload")))
    assert cli.main(["run"]) == 1
    assert "secret-payload" not in capsys.readouterr().err


def test_enabled_clean_stop_and_signal_binding(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "network_metadata_config_from_env", lambda: configuration(tmp_path))
    monkeypatch.setattr(cli, "capture_loaded_artifact_identity", lambda *_: IDENTITY)
    calls, handlers = [], {}
    class Service:
        def __init__(self, *_):
            pass
        def stop(self):
            calls.append("stop")
        def run_forever(self):
            for handler in list(handlers.values()):
                handler(None, None)
    def signal(signum, handler):
        previous = handlers.get(signum)
        handlers[signum] = handler
        return previous
    monkeypatch.setattr(cli, "NetworkMetadataService", Service)
    monkeypatch.setattr(cli.signal, "signal", signal)
    assert cli.main(["run"]) == 0
    assert calls == ["stop", "stop"]


def test_writer_lock_failure_safe(tmp_path, monkeypatch, capsys):
    from app.network_metadata.repository import WriterLock
    cfg = configuration(tmp_path)
    monkeypatch.setattr(cli, "network_metadata_config_from_env", lambda: cfg)
    monkeypatch.setattr(cli, "capture_loaded_artifact_identity", lambda *_: IDENTITY)
    with WriterLock(cfg.writer_lock_path):
        assert cli.main(["run"]) == 1
    assert capsys.readouterr().err == "Network metadata service unavailable\n"
