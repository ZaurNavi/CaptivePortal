from app.device_fingerprint_sensor import cli


class Connection:
    def close(self): pass


def test_core_readiness_retries_bounded_without_business_request():
    times = iter([0, 0, 10, 10])
    calls = []
    def connect(address, timeout):
        calls.append((address, timeout))
        if len(calls) == 1: raise OSError
        return Connection()
    assert cli.wait_for_core("127.0.0.1", 8088, connect_timeout=1, poll_interval=10, max_wait=1800, monotonic=lambda: next(times), sleep=lambda value: calls.append(("sleep", value)), connector=connect)
    assert calls[0] == (("127.0.0.1", 8088), 1)


def test_disabled_cli_returns_before_artifact_identity(monkeypatch):
    monkeypatch.setattr(cli, "sensor_config_from_env", lambda: type("C", (), {"enabled": False})())
    monkeypatch.setattr(cli, "capture_loaded_artifact_identity", lambda *_: (_ for _ in ()).throw(AssertionError()))
    assert cli.main(["run"]) == 0


def test_readiness_timeout_fails_before_runtime(monkeypatch):
    config = type("C", (), {"enabled": True, "core_ready_host": "127.0.0.1", "core_ready_port": 8088, "core_ready_connect_timeout_seconds": 1, "core_ready_poll_interval_seconds": 10, "core_ready_max_wait_seconds": 1800})()
    identity = type("I", (), {"safe_fields": lambda self: {}})()
    monkeypatch.setattr(cli, "sensor_config_from_env", lambda: config)
    monkeypatch.setattr(cli, "capture_loaded_artifact_identity", lambda *_: identity)
    monkeypatch.setattr(cli, "wait_for_core", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "SensorRuntime", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not capture")))
    assert cli.main(["run"]) == 1


def test_T06_custom_readiness_is_tcp_only_and_bounded():
    calls, now = [], [0.0]
    def connect(address, timeout):
        calls.append((address, timeout))
        raise OSError("synthetic unreachable")
    def sleep(value):
        now[0] += value
    assert cli.wait_for_core("172.18.0.1", 18089, connect_timeout=1, poll_interval=2, max_wait=5,
        monotonic=lambda: now[0], sleep=sleep, connector=connect) is False
    assert now[0] == 5 and len(calls) == 4
    assert all(call == (("172.18.0.1", 18089), 1) for call in calls)
    closed = []
    class TcpOnly:
        def close(self): closed.append(True)
    assert cli.wait_for_core("172.18.0.1", 18089, connect_timeout=1, poll_interval=2, max_wait=5,
        monotonic=lambda: 0.0, connector=lambda *_args, **_kwargs: TcpOnly())
    assert closed == [True]  # No send/recv/HTTP method exists on the synthetic socket.
