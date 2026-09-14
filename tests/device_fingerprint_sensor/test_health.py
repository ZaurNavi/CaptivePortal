from app.device_fingerprint_sensor.config import sensor_config_from_env
from app.device_fingerprint_sensor.health import SourceHealthTracker


class Clock:
    value = 0.0
    def __call__(self): return self.value


def test_health_emits_transition_and_300_second_heartbeat_without_identity():
    clock = Clock(); tracker = SourceHealthTracker(sensor_config_from_env({"DEVICE_FINGERPRINT_SENSOR_ENABLED": "true"}), monotonic=clock)
    first = tracker.transition("dhcp", "available", None)
    assert first.document["source_kind"] == "dhcp"
    assert "observed_mac" not in first.document and "observed_ip" not in first.document
    assert tracker.transition("dhcp", "available", None) is None
    clock.value = 300
    assert tracker.transition("dhcp", "available", None) is not None


def test_ready_requires_all_four_sources_available():
    clock = Clock(); tracker = SourceHealthTracker(sensor_config_from_env({"DEVICE_FINGERPRINT_SENSOR_ENABLED": "true"}), monotonic=clock)
    tracker.raw("available", None)
    assert not tracker.ready
    tracker.suricata("available", None)
    assert tracker.ready
