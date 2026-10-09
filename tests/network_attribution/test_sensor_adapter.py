from datetime import timedelta
from types import SimpleNamespace

from app.device_fingerprint_sensor.config import sensor_config_from_env
from app.device_fingerprint_sensor.runtime import SensorRuntime
from app.network_attribution.dhcp_authority import DhcpAuthorityRecorder
from app.network_attribution.models import NetworkAttributionConfig

from .test_authority import T0, frame, ts


def test_r1_b_real_recorder_survives_held_reader(tmp_path):
    import sqlite3
    from .test_authority import IP
    from app.network_attribution.read_service import NetworkAttributionReadService

    now = [T0]
    sensor = sensor_config_from_env({"DEVICE_FINGERPRINT_SENSOR_ENABLED": "true"})
    config = NetworkAttributionConfig(True, str(tmp_path / "concurrent.sqlite3"))
    telemetry = Telemetry()
    recorder = DhcpAuthorityRecorder(config, sensor, telemetry=telemetry, clock=lambda: now[0])
    recorder.start()
    reader = sqlite3.connect(config.db_path, isolation_level=None)
    try:
        reader.execute("PRAGMA query_only=ON")
        reader.execute("BEGIN")
        snapshot = reader.execute("SELECT * FROM source_coverage").fetchall()
        now[0] += timedelta(seconds=1)
        recorder.poll()  # Includes first bounded retention/checkpoint maintenance.
        recorder.record_frame(frame(), ts(1))
        now[0] += timedelta(seconds=60)
        recorder.poll()  # Repeat maintenance with the same pinned snapshot.
        assert recorder.permanent_fault is False
        assert telemetry.entries == []
        assert reader.execute("SELECT * FROM source_coverage").fetchall() == snapshot
        assert reader.execute("SELECT count(*) FROM authority_facts").fetchone()[0] == 0
        service = NetworkAttributionReadService(config, clock=lambda: now[0])
        assert service.resolve_ipv4(sensor.site_id, IP, ts(1)).state == "resolved"
    finally:
        reader.close()
        recorder.shutdown()


class Telemetry:
    def __init__(self):
        self.entries = []

    def emit(self, event, **fields):
        self.entries.append((event, fields))


class Spool:
    capacity_blocked = False

    def __init__(self):
        self.events = []

    def enqueue(self, events):
        self.events.extend(events)

    def initialize(self):
        pass

    def close(self):
        pass


def runtime(*, config=None, recorder=None):
    sensor = sensor_config_from_env({"DEVICE_FINGERPRINT_SENSOR_ENABLED": "true"})
    spool, telemetry = Spool(), Telemetry()
    instance = SensorRuntime(sensor, telemetry=telemetry, spool=spool, producer=SimpleNamespace(),
        eve=SimpleNamespace(close=lambda: None), attribution_config=config, attribution_recorder=recorder,
        monotonic=lambda: 0, now=lambda: T0)
    raw = frame(message=3)

    class Capture:
        def __init__(self):
            self.frames = iter([(raw, 0, ts()), (raw, 0, ts())])

        def receive(self):
            received = next(self.frames, None)
            if received is None:
                instance.stop_event.set()
            return received

        def close(self):
            pass

    instance.capture = Capture()
    return instance, spool, telemetry


def test_disabled_adapter_preserves_normalized_outputs_and_never_constructs_recorder(monkeypatch):
    import app.network_attribution.dhcp_authority as module
    monkeypatch.setattr(module, "DhcpAuthorityRecorder", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()))
    baseline, baseline_spool, baseline_log = runtime()
    disabled, disabled_spool, disabled_log = runtime(config=NetworkAttributionConfig())
    baseline._raw_loop()
    disabled._raw_loop()
    assert baseline._attribution is disabled._attribution is None
    assert len(baseline_spool.events) == len(disabled_spool.events) == 1
    left, right = baseline_spool.events[0].document.copy(), disabled_spool.events[0].document.copy()
    left.pop("source_event_id")
    right.pop("source_event_id")
    assert left == right
    assert baseline_log.entries == disabled_log.entries == []


def test_recorder_exception_does_not_suppress_fingerprint_output_and_dedup_precedes_both():
    order = []

    class Recorder:
        def record_frame(self, raw, observed_at):
            assert len(spool.events) == 1  # Existing normalization/spooling completed first.
            order.append("record")
            raise RuntimeError("private-frame-not-to-be-logged")

        def fault(self, reason):
            order.append(reason)

        def poll(self):
            pass

    instance, spool, telemetry = runtime(config=NetworkAttributionConfig(True), recorder=Recorder())
    instance._raw_loop()
    assert len(spool.events) == 1 and order == ["record", "attribution_recorder_unavailable"]
    assert instance._local_health["dhcp"][1] != "attribution_recorder_unavailable"
    assert telemetry.entries == []


def test_real_repository_failure_leaves_fingerprint_raw_output_usable(tmp_path):
    sensor = sensor_config_from_env({"DEVICE_FINGERPRINT_SENSOR_ENABLED": "true"})
    config = NetworkAttributionConfig(True, str(tmp_path / "missing" / "attribution.sqlite3"))
    recorder = DhcpAuthorityRecorder(config, sensor, telemetry=Telemetry(), clock=lambda: T0)
    recorder.start()
    assert recorder.permanent_fault
    instance, spool, _ = runtime(config=config, recorder=recorder)
    instance._raw_loop()
    assert len(spool.events) == 1
    assert len(recorder.telemetry.entries) == 1


def test_capture_error_fences_ni_without_using_fingerprint_health_for_ni():
    faults = []
    recorder = SimpleNamespace(fault=faults.append)
    instance, _, _ = runtime(config=NetworkAttributionConfig(True), recorder=recorder)
    instance.capture.receive = lambda: (_ for _ in ()).throw(OSError())
    instance._raw_loop()
    assert faults == ["raw_capture_unavailable"]
    assert instance._local_health["dhcp"] == ("unavailable", "raw_parser_unavailable")


def test_sidecar_start_requires_preflight_and_raw_open(monkeypatch):
    order = []
    recorder = SimpleNamespace(start=lambda: order.append("attribution"), shutdown=lambda: None,
                               fault=lambda reason: order.append(reason))
    instance, _, _ = runtime(config=NetworkAttributionConfig(True), recorder=recorder)
    instance.preflight = SimpleNamespace(validate=lambda: order.append("preflight"))
    instance.capture.open = lambda: order.append("raw_open")
    instance.eve.open = lambda: order.append("eve_open")
    import app.device_fingerprint_sensor.runtime as module
    monkeypatch.setattr(module.threading, "Thread", lambda **_kwargs: SimpleNamespace(start=lambda: None))
    assert instance.preflight_or_report()
    instance.start()
    assert order == ["preflight", "eve_open", "raw_open", "attribution"]


def test_recorder_shutdown_poll_and_permanent_fault_are_bounded(tmp_path):
    sensor = sensor_config_from_env({"DEVICE_FINGERPRINT_SENSOR_ENABLED": "true"})
    config = NetworkAttributionConfig(True, str(tmp_path / "attribution.sqlite3"))
    clock = [T0]
    telemetry = Telemetry()
    recorder = DhcpAuthorityRecorder(config, sensor, telemetry=telemetry, clock=lambda: clock[0])
    recorder.start()
    recorder.record_frame(frame(), ts())
    assert not recorder.permanent_fault
    clock[0] += timedelta(seconds=1)
    recorder.poll()
    assert recorder.repository.connection.execute("SELECT verified_through FROM source_coverage").fetchone()[0] == ts(1)
    recorder.fault("attribution_recorder_unavailable")
    recorder.fault("attribution_recorder_unavailable")
    assert len(telemetry.entries) == 1
    recorder.record_frame(frame(), ts(1))
    recorder.shutdown()
    assert recorder.repository.connection is None


def test_queued_pre_activation_ack_is_not_backfilled_or_a_permanent_fault(tmp_path):
    sensor = sensor_config_from_env({"DEVICE_FINGERPRINT_SENSOR_ENABLED": "true"})
    config = NetworkAttributionConfig(True, str(tmp_path / "attribution.sqlite3"))
    recorder = DhcpAuthorityRecorder(config, sensor, telemetry=Telemetry(), clock=lambda: T0 + timedelta(seconds=10))
    recorder.start()
    recorder.record_frame(frame(), ts(9))
    assert not recorder.permanent_fault
    assert recorder.repository.connection.execute("SELECT count(*) FROM authority_facts").fetchone()[0] == 0
    recorder.record_frame(frame(), ts(10))
    assert recorder.repository.connection.execute("SELECT count(*) FROM authority_facts").fetchone()[0] == 1
    recorder.shutdown()


def test_live_client_termination_between_idle_polls_is_recorded(tmp_path):
    sensor = sensor_config_from_env({"DEVICE_FINGERPRINT_SENSOR_ENABLED": "true"})
    config = NetworkAttributionConfig(True, str(tmp_path / "attribution.sqlite3"))
    clock = [T0]
    recorder = DhcpAuthorityRecorder(config, sensor, telemetry=Telemetry(), clock=lambda: clock[0])
    recorder.start()
    recorder.record_frame(frame(), ts())
    clock[0] += timedelta(milliseconds=500)
    recorder.record_frame(frame(message=7), ts(.5))
    assert not recorder.permanent_fault
    row = recorder.repository.connection.execute("SELECT * FROM binding_intervals").fetchone()
    assert row["end_reason"] == "client_release" and row["valid_until"] == ts(.5)
    recorder.shutdown()
