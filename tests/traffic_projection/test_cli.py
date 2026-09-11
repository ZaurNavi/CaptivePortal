from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app.artifact_identity import ArtifactIdentityError, LoadedArtifactIdentity
from app.traffic_projection import cli


IDENTITY = LoadedArtifactIdentity(
    "a" * 40,
    "b" * 40,
    "traffic-projection.service",
    "2026-09-11T12:00:00.000Z",
)


class Service:
    instances = []

    def __init__(self, config, **kwargs):
        self.config = config
        self.kwargs = kwargs
        self.calls = []
        Service.instances.append(self)

    def serve_forever(self):
        self.calls.append(("run",))

    def initialize(self):
        self.calls.append(("initialize",))

    def worker_iteration(self):
        self.calls.append(("build",))

    def mark_ready(self):
        self.calls.append(("mark-ready",))

    def activate(self):
        self.calls.append(("activate",))

    def fail_version(self):
        self.calls.append(("mark-failed",))

    def repair_site(self, site):
        self.calls.append(("repair-site", site))

    def rebuild_range(self, site, **kwargs):
        self.calls.append(("rebuild-range", site, kwargs))

    def cleanup(self):
        self.calls.append(("cleanup",))

    def stop(self):
        self.calls.append(("stop",))


@contextmanager
def _lock(_path):
    yield


@pytest.fixture(autouse=True)
def cli_fakes(monkeypatch):
    Service.instances.clear()
    config = SimpleNamespace(enabled=True, writer_lock_path="lock")
    monkeypatch.setattr(cli, "get_settings", lambda: object())
    monkeypatch.setattr(cli, "traffic_projection_config_from_settings", lambda _s: config)
    monkeypatch.setattr(cli, "configure_traffic_projection_logger", lambda: object())
    monkeypatch.setattr(cli, "TrafficProjectionService", Service)
    monkeypatch.setattr(cli, "writer_lock", _lock)
    return config


def test_cli_run_captures_identity_configures_signals_and_starts(monkeypatch):
    captures = []
    handlers = {}
    monkeypatch.setattr(
        cli,
        "capture_loaded_artifact_identity",
        lambda name: captures.append(name) or IDENTITY,
    )
    monkeypatch.setattr(
        cli.signal,
        "signal",
        lambda number, handler: handlers.__setitem__(number, handler),
    )
    assert cli.main(["run"]) == 0
    service = Service.instances[0]
    assert captures == ["traffic-projection.service"]
    assert service.kwargs["artifact_identity"] is IDENTITY
    assert service.calls == [("run",)]
    handlers[cli.signal.SIGTERM](cli.signal.SIGTERM, None)
    handlers[cli.signal.SIGINT](cli.signal.SIGINT, None)
    assert service.calls[-2:] == [("stop",), ("stop",)]


@pytest.mark.parametrize("command", ["run", "repair-site"])
def test_cli_identity_failure_exits_one_before_service_or_writer(
    monkeypatch, capsys, command
):
    lock_called = []
    monkeypatch.setattr(
        cli,
        "capture_loaded_artifact_identity",
        lambda _name: (_ for _ in ()).throw(ArtifactIdentityError("git secret")),
    )

    @contextmanager
    def forbidden_lock(_path):
        lock_called.append(True)
        yield

    monkeypatch.setattr(cli, "writer_lock", forbidden_lock)
    arguments = [command] + (["--site-id", "site-a"] if command == "repair-site" else [])
    with pytest.raises(SystemExit) as raised:
        cli.main(arguments)
    assert raised.value.code == 1
    assert capsys.readouterr().err == (
        "traffic-projection: loaded artifact identity unavailable\n"
    )
    assert Service.instances == []
    assert lock_called == []


def test_cli_repair_site_binds_repair_identity(monkeypatch):
    repair_identity = LoadedArtifactIdentity(
        "a" * 40,
        "b" * 40,
        "traffic-projection-repair",
        "2026-09-11T12:00:00.000Z",
    )
    captures = []
    monkeypatch.setattr(
        cli,
        "capture_loaded_artifact_identity",
        lambda name: captures.append(name) or repair_identity,
    )
    assert cli.main(["repair-site", "--site-id", "site-a"]) == 0
    service = Service.instances[0]
    assert captures == ["traffic-projection-repair"]
    assert service.kwargs["artifact_identity"] is repair_identity
    assert service.calls == [("initialize",), ("repair-site", "site-a")]


@pytest.mark.parametrize(
    "arguments",
    [
        ["build"], ["mark-ready"], ["activate"], ["mark-failed"],
        ["cleanup"],
        ["rebuild-range", "--site-id", "site-a", "--from-utc", "a", "--to-utc", "b"],
    ],
)
def test_cli_other_commands_do_not_capture_or_fabricate_identity(
    monkeypatch, arguments
):
    monkeypatch.setattr(
        cli,
        "capture_loaded_artifact_identity",
        lambda _name: pytest.fail("identity capture was not optional"),
    )
    assert cli.main(arguments) == 0
    assert Service.instances[0].kwargs["artifact_identity"] is None
