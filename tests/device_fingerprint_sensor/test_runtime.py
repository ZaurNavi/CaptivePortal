import json
import socket
import struct
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.device_fingerprint_sensor.capture import InterfacePreflight
from app.device_fingerprint_sensor.capture_filter import RAW_CAPTURE_FILTER
from app.device_fingerprint_sensor.config import sensor_config_from_env
from app.device_fingerprint_sensor.eve import EveReceiver
from app.device_fingerprint_sensor.models import SensorPreflightError
from app.device_fingerprint_sensor.runtime import SensorRuntime
from app.device_fingerprint_sensor.telemetry import SensorTelemetry


def make_tree(tmp_path, *, operstate="up", ipv4="0", ipv6="0"):
    sys_root = tmp_path / "sys"; proc_root = tmp_path / "proc"
    net = sys_root / "class/net/enp8s0"; net.mkdir(parents=True)
    (net / "operstate").write_text(operstate)
    for family, value in (("ipv4", ipv4), ("ipv6", ipv6)):
        path = proc_root / f"sys/net/{family}/conf/enp8s0"; path.mkdir(parents=True)
        (path / "forwarding").write_text(value)
    (proc_root / "100").mkdir(parents=True); (proc_root / "100/cmdline").write_bytes(b"/usr/bin/python\0")
    return sys_root, proc_root


def runner(command, **_kwargs):
    if command[:2] == ["netplan", "get"]:
        return subprocess.CompletedProcess(command, 0, "false\n", "")
    if command[:3] == ["systemctl", "is-active", "NetworkManager"]:
        return subprocess.CompletedProcess(command, 3, "inactive\n", "")
    if command[0] == "ip":
        return subprocess.CompletedProcess(command, 0, "[]\n" if "route" in command else '[{"addr_info":[]}]\n', "")
    raise AssertionError(command)


def test_interface_preflight_accepts_exact_no_l3_state(tmp_path):
    sys_root, proc_root = make_tree(tmp_path)
    InterfacePreflight(sys_root=sys_root, proc_root=proc_root, runner=runner).validate()


@pytest.mark.parametrize("kind", ["unknown", "down", "dormant", "lowerlayerdown", "notpresent", "testing"])
def test_interface_preflight_rejects_every_non_up_operstate(tmp_path, kind):
    sys_root, proc_root = make_tree(tmp_path, operstate=kind)
    with pytest.raises(SensorPreflightError):
        InterfacePreflight(sys_root=sys_root, proc_root=proc_root, runner=runner).validate()


def test_interface_preflight_rejects_dhcp_process(tmp_path):
    sys_root, proc_root = make_tree(tmp_path)
    (proc_root / "100/cmdline").write_bytes(b"/sbin/dhclient\0-v\0enp8s0\0")
    with pytest.raises(SensorPreflightError):
        InterfacePreflight(sys_root=sys_root, proc_root=proc_root, runner=runner).validate()


def test_netplan_failure_or_networkmanager_profile_fails_closed(tmp_path):
    sys_root, proc_root = make_tree(tmp_path)
    def failing(command, **kwargs):
        if command[:2] == ["netplan", "get"]: return subprocess.CompletedProcess(command, 1, "", "error")
        return runner(command, **kwargs)
    with pytest.raises(SensorPreflightError):
        InterfacePreflight(sys_root=sys_root, proc_root=proc_root, runner=failing).validate()
    def nm(command, **kwargs):
        if command[:3] == ["systemctl", "is-active", "NetworkManager"]: return subprocess.CompletedProcess(command, 0, "active\n", "")
        if command[0] == "nmcli": return subprocess.CompletedProcess(command, 0, "wired:enp8s0\n", "")
        return runner(command, **kwargs)
    with pytest.raises(SensorPreflightError):
        InterfacePreflight(sys_root=sys_root, proc_root=proc_root, runner=nm).validate()


class Log:
    def info(self, *_args): pass


class CaptureLog:
    def __init__(self): self.values = []
    def info(self, value): self.values.append(value)


class Spool:
    capacity_blocked = False
    stale_dropped = 0
    def initialize(self): self.initialized = True
    def enqueue(self, values): return len(values)
    def metrics(self): return {"rows": 0, "spool_bytes": 0, "oldest_spool_age": 0}
    def close(self): self.closed = True


class Preflight:
    def __init__(self, fails=False): self.fails = fails
    def validate(self):
        if self.fails: raise SensorPreflightError("capture_interface_unavailable")


class Capture:
    def open(self): pass
    def close(self): pass
    def receive(self): raise RuntimeError


class Eve:
    truncated = 0
    invalid = 0
    def open(self): pass
    def close(self): pass
    def receive(self): raise RuntimeError


class Producer:
    permanent_fault = False
    def deliver_once(self): raise RuntimeError


def test_preflight_failure_spools_all_source_health_without_capture():
    config = sensor_config_from_env({"DEVICE_FINGERPRINT_SENSOR_ENABLED": "true"})
    spool = Spool()
    runtime = SensorRuntime(config, telemetry=SensorTelemetry(Log()), preflight=Preflight(True), capture=Capture(), eve=Eve(), spool=spool, producer=Producer())
    runtime.initialize_transport()
    assert runtime.preflight_or_report() is False
    assert runtime.state == "unavailable"


def test_repository_bpf_artifact_is_exact_frozen_expression():
    root = Path(__file__).resolve().parents[2]
    assert (root / "deploy/device-fingerprint/raw-capture.bpf").read_text(encoding="ascii").strip() == RAW_CAPTURE_FILTER


def test_raw_socket_uses_eth_p_all_and_filter_before_configured_interface_bind(monkeypatch):
    from app.device_fingerprint_sensor import capture as module
    calls = []
    class Socket:
        def settimeout(self, value): calls.append(("timeout", value))
        def setsockopt(self, *_args): calls.append("timestamp")
        def bind(self, value): calls.append(("bind", value))
        def close(self): calls.append("close")
    monkeypatch.setattr(module, "attach_frozen_filter", lambda _socket: calls.append("filter"))
    monkeypatch.setattr(module.socket, "AF_PACKET", 17, raising=False)
    raw = module.RawCapture("enp8s0", socket_factory=lambda *args: (calls.append(("socket", args)) or Socket()))
    raw.open()
    assert calls[0] == (
        "socket",
        (module.socket.AF_PACKET, module.socket.SOCK_RAW, module.socket.htons(0x0003)),
    )
    assert ("bind", ("enp8s0", 0)) in calls
    assert calls.index("filter") < next(index for index, item in enumerate(calls) if isinstance(item, tuple) and item[0] == "bind")


def test_raw_receive_timeout_is_a_neutral_poll():
    from app.device_fingerprint_sensor.capture import RawCapture

    class TimedOutSocket:
        def recvmsg(self, *_args): raise socket.timeout

    capture = RawCapture("enp8s0")
    capture.socket = TimedOutSocket()
    assert capture.receive() is None


def test_raw_receive_preserves_kernel_timestamp_semantics():
    from app.device_fingerprint_sensor.capture import RawCapture, SO_TIMESTAMPNS

    class TimestampedSocket:
        def recvmsg(self, *_args):
            return b"frame", [(socket.SOL_SOCKET, SO_TIMESTAMPNS, struct.pack("qq", 0, 123_456_789))], 0, None

    capture = RawCapture("enp8s0")
    capture.socket = TimestampedSocket()

    assert capture.receive() == (
        b"frame",
        123_456_789,
        "1970-01-01T00:00:00.123Z",
    )


def test_permanent_delivery_fault_cannot_refresh_back_to_ready():
    class PermanentProducer:
        permanent_fault = False
        def deliver_once(self):
            self.permanent_fault = True
            return SimpleNamespace(status="permanent", delay_seconds=0, delivered=0)

    config = sensor_config_from_env({"DEVICE_FINGERPRINT_SENSOR_ENABLED": "true"})
    producer = PermanentProducer()
    runtime = SensorRuntime(config, telemetry=SensorTelemetry(Log()), preflight=Preflight(), capture=Capture(), eve=Eve(), spool=Spool(), producer=producer)
    runtime._delivery_loop()
    runtime._local_health = {kind: ("available", None) for kind in runtime._local_health}
    runtime._delivery_available = True
    runtime._refresh_state()
    assert runtime.state == "degraded"
    assert runtime.reason == "delivery_permanent_reject"


def test_suricata_stats_heartbeat_controls_tls_and_quic_health():
    class Clock:
        value = 0.0
        def __call__(self): return self.value

    clock = Clock()
    config = sensor_config_from_env({"DEVICE_FINGERPRINT_SENSOR_ENABLED": "true"})
    runtime = SensorRuntime(config, telemetry=SensorTelemetry(Log()), monotonic=clock, preflight=Preflight(), capture=Capture(), eve=Eve(), spool=Spool(), producer=Producer())
    assert runtime._local_health["tls_client"] == ("unavailable", "suricata_unavailable")
    assert runtime._local_health["quic_client"] == ("unavailable", "suricata_unavailable")
    runtime._suricata_heartbeat()
    assert runtime._local_health["tls_client"] == ("available", None)
    assert runtime._local_health["quic_client"] == ("available", None)
    clock.value = 30.001
    runtime._check_suricata_heartbeat()
    assert runtime._local_health["tls_client"] == ("unavailable", "suricata_unavailable")
    assert runtime._local_health["quic_client"] == ("unavailable", "suricata_unavailable")
    runtime._suricata_heartbeat()
    assert runtime._local_health["tls_client"] == ("available", None)
    assert runtime._local_health["quic_client"] == ("available", None)


def test_periodic_metrics_include_eve_and_quic_counters_without_content():
    log = CaptureLog()
    class SecretDatagramSocket:
        def recvmsg(self, *_args): return b"SENSITIVE_EVE_DATAGRAM", [], 0, None

    eve = EveReceiver("unused")
    eve.socket = SecretDatagramSocket()
    assert eve.receive() is None
    eve.truncated = 2
    eve.invalid = 3
    config = sensor_config_from_env({"DEVICE_FINGERPRINT_SENSOR_ENABLED": "true"})
    runtime = SensorRuntime(config, telemetry=SensorTelemetry(log), preflight=Preflight(), capture=Capture(), eve=eve, spool=Spool(), producer=Producer())
    runtime.normalizer.counters.update({"eve_json_invalid": 1, "quic_version_invalid": 4})
    runtime._emit_metrics()
    payload = json.loads(log.values[-1])
    assert payload["eve_datagram_truncated"] == 2
    assert payload["eve_json_invalid"] == 4
    assert payload["quic_version_invalid"] == 4
    assert "SENSITIVE_EVE_DATAGRAM" not in log.values[-1]


def test_shutdown_terminates_workers_while_receivers_are_idle():
    class IdleCapture(Capture):
        def receive(self):
            time.sleep(0.01)
            return None

    class IdleEve(Eve):
        def receive(self):
            time.sleep(0.01)
            return None

    class EmptyProducer:
        permanent_fault = False
        def deliver_once(self):
            return SimpleNamespace(status="empty", delay_seconds=0, delivered=0)

    config = sensor_config_from_env({"DEVICE_FINGERPRINT_SENSOR_ENABLED": "true"})
    runtime = SensorRuntime(config, telemetry=SensorTelemetry(Log()), preflight=Preflight(), capture=IdleCapture(), eve=IdleEve(), spool=Spool(), producer=EmptyProducer())
    runtime.start()
    assert runtime.shutdown() is True
    assert all(not thread.is_alive() for thread in runtime.threads)


def test_suricata_service_checks_capture_interface_without_mutating_it():
    root = Path(__file__).resolve().parents[2]
    service = (root / "deploy/device-fingerprint/fingerprint-suricata.service").read_text(encoding="ascii")
    assert "ExecStartPre=/usr/bin/test -e /sys/class/net/enp8s0" in service
    assert "ip link" not in service and "ip addr" not in service
