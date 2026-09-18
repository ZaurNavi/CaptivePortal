"""F-B0 immutable content, strict shape, and current-emitter behavior proof."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.device_fingerprint.artifact_content import canonical_artifact_json
from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.source_health_emitter_contracts import (
    build_network_sensor_source_health_emitter_contract,
    build_portal_source_health_emitter_contract,
    build_source_health_emitter_contracts,
    make_source_health_emitter_contract,
)
from app.device_fingerprint_sensor.config import sensor_config_from_env
from app.device_fingerprint_sensor.health import HEARTBEAT_SECONDS, SOURCE_KINDS, SourceHealthTracker
from app.device_fingerprint_sensor.models import SensorPreflightError
from app.device_fingerprint_sensor.runtime import SensorRuntime
from app.device_fingerprint_sensor.telemetry import SensorTelemetry
from app.device_fingerprint_portal.models import DeliveryResult
from tests.device_fingerprint_portal.test_runtime import candidate, runtime as portal_runtime, session
from tests.device_fingerprint_sensor.test_spool import Clock as SpoolClock
from tests.device_fingerprint_sensor.test_spool import event as spool_event
from tests.device_fingerprint_sensor.test_spool import spool as make_spool


def test_exact_emitter_contract_contents_and_deterministic_collection():
    sensor = build_network_sensor_source_health_emitter_contract()
    portal = build_portal_source_health_emitter_contract()
    assert {item.artifact_id for item in build_source_health_emitter_contracts()} == {
        sensor.artifact_id, portal.artifact_id,
    }
    assert list(build_source_health_emitter_contracts()) == sorted(
        (sensor, portal), key=lambda item: item.artifact_id,
    )
    assert sensor.artifact_schema_version == portal.artifact_schema_version == 1
    assert sensor.artifact_type == portal.artifact_type == "SourceHealthEmitterContract"
    sensor_payload, portal_payload = sensor.semantic_payload, portal.semantic_payload
    assert sensor_payload["producer_service_implementation_identity"] == (
        "CaptivPortal/device_fingerprint_sensor/source-health@8e6173bf7ea566bdfb3823fc58bc728ca14e3893"
    )
    assert portal_payload["producer_service_implementation_identity"] == (
        "CaptivPortal/device_fingerprint_portal/source-health@8e6173bf7ea566bdfb3823fc58bc728ca14e3893"
    )
    assert set(sensor_payload["source_kinds"]) == set(SOURCE_KINDS)
    assert portal_payload["source_kinds"] == ["portal_headers"]
    assert sensor_payload["heartbeat_behavior_cadence_semantics"] == {
        "mode": "PERIODIC", "nominal_interval_ms": 300_000,
        "same_state_heartbeat_required": True,
    }
    assert portal_payload["heartbeat_behavior_cadence_semantics"] == {
        "mode": "EVENT_DRIVEN", "nominal_interval_ms": None,
        "same_state_heartbeat_required": False,
    }
    assert sensor_payload["persisted_status_emission_semantics"] == {
        "allowed_statuses": ["available", "unavailable", "unsupported"],
        "status_transition_delivery_required_when_transport_available": True,
    }
    assert portal_payload["persisted_status_emission_semantics"] == {
        "allowed_statuses": ["available", "unavailable"],
        "status_transition_delivery_required_when_transport_available": True,
    }
    assert {row["reason_code"]: row["failure_domain_semantics"] for row in sensor_payload["reason_code_definitions"]} == {
        "capture_interface_unavailable": "ACQUISITION",
        "raw_parser_unavailable": "ACQUISITION",
        "suricata_unavailable": "ACQUISITION",
        "eve_datagram_truncated": "ACQUISITION",
        "ingest_delivery_unavailable": "DELIVERY",
    }
    assert [row["reason_code"] for row in portal_payload["reason_code_definitions"]] == [
        "ingest_delivery_unavailable",
    ]
    assert all(row["status_compatibility"] == ["unavailable"] for row in (
        sensor_payload["reason_code_definitions"] + portal_payload["reason_code_definitions"]
    ))
    assert sensor_payload["delivery_spool_loss_behavior_relevant_to_coverage"] == {
        "producer_spool_mode": "BOUNDED_LOSSY",
        "lossless_interval_completion_claim_permitted": False,
        "evidence_eviction_possible": True,
        "capacity_block_possible": True,
    }
    assert portal_payload["delivery_spool_loss_behavior_relevant_to_coverage"] == {
        "producer_spool_mode": "BOUNDED_LOSSY",
        "lossless_interval_completion_claim_permitted": False,
        "evidence_eviction_possible": True,
        "capacity_block_possible": False,
    }
    for payload in (sensor_payload, portal_payload):
        assert payload["emitter_contract_version"] == 1
        assert payload["source_health_event_compatibility_version"] == 1
        assert payload["task01_delayed_event_interaction"] == {
            "must_obey_task01_delayed_event_contract": True,
            "historical_health_backfill_permitted_when_within_task01_limit": True,
            "recovery_never_proves_missing_interval_complete": True,
        }


@pytest.mark.parametrize("mutate", [
    lambda p: p.update(extra=True),
    lambda p: p.update(emitter_contract_version=0),
    lambda p: p.update(source_health_event_compatibility_version=True),
    lambda p: p.update(producer_service_implementation_identity=""),
    lambda p: p.update(source_kinds=[]),
    lambda p: p.update(source_kinds=["dhcp", "dhcp"]),
    lambda p: p["heartbeat_behavior_cadence_semantics"].update(extra=True),
    lambda p: p["heartbeat_behavior_cadence_semantics"].update(mode="UNKNOWN"),
    lambda p: p["heartbeat_behavior_cadence_semantics"].update(nominal_interval_ms=None),
    lambda p: p["heartbeat_behavior_cadence_semantics"].update(nominal_interval_ms=0),
    lambda p: p["heartbeat_behavior_cadence_semantics"].update(same_state_heartbeat_required=1),
    lambda p: p["persisted_status_emission_semantics"].update(extra=True),
    lambda p: p["persisted_status_emission_semantics"].update(allowed_statuses=["unknown"]),
    lambda p: p["reason_code_definitions"][0].update(extra=True),
    lambda p: p["reason_code_definitions"][0].update(failure_domain_semantics="UNKNOWN"),
    lambda p: p["reason_code_definitions"].append(deepcopy(p["reason_code_definitions"][0])),
    lambda p: p["delivery_spool_loss_behavior_relevant_to_coverage"].update(extra=True),
    lambda p: p["delivery_spool_loss_behavior_relevant_to_coverage"].update(lossless_interval_completion_claim_permitted=True),
    lambda p: p["task01_delayed_event_interaction"].update(must_obey_task01_delayed_event_contract=False),
    lambda p: p["task01_delayed_event_interaction"].update(recovery_never_proves_missing_interval_complete=False),
])
def test_invalid_contract_shape_fails_closed(mutate):
    payload = deepcopy(build_network_sensor_source_health_emitter_contract().semantic_payload)
    mutate(payload)
    with pytest.raises(DeviceFingerprintValidationError):
        make_source_health_emitter_contract(payload)


def test_event_driven_interval_and_set_tie_break_are_strict():
    payload = deepcopy(build_portal_source_health_emitter_contract().semantic_payload)
    payload["heartbeat_behavior_cadence_semantics"]["nominal_interval_ms"] = 300_000
    with pytest.raises(DeviceFingerprintValidationError):
        make_source_health_emitter_contract(payload)
    payload["heartbeat_behavior_cadence_semantics"]["nominal_interval_ms"] = None
    same_primary = deepcopy(payload["reason_code_definitions"][0])
    same_primary["exact_meaning"] += " (alternate explicit semantics)"
    payload["reason_code_definitions"].append(same_primary)
    result = make_source_health_emitter_contract(payload)
    assert len(result.semantic_payload["reason_code_definitions"]) == 2
    assert result.semantic_payload["reason_code_definitions"] == sorted(
        result.semantic_payload["reason_code_definitions"],
        key=lambda row: (row["reason_code"], canonical_artifact_json(row)),
    )


@pytest.mark.parametrize("builder", [
    build_network_sensor_source_health_emitter_contract,
    build_portal_source_health_emitter_contract,
])
def test_semantic_identity_is_stable_and_changes_with_meaning(builder):
    first, second = builder(), builder()
    assert first.content_sha256 == second.content_sha256
    assert first.artifact_id == second.artifact_id
    changed = deepcopy(first.semantic_payload)
    changed["reason_code_definitions"][0]["exact_meaning"] += " (changed)"
    alternate = make_source_health_emitter_contract(changed)
    assert alternate.content_sha256 != first.content_sha256
    assert alternate.artifact_id != first.artifact_id


def test_network_sensor_tracker_and_runtime_emit_declared_status_reasons():
    class Clock:
        value = 0.0
        def __call__(self):
            return self.value

    class Spool:
        capacity_blocked = False
        def __init__(self):
            self.events = []
        def enqueue(self, values):
            self.events.extend(values)

    class Log:
        def info(self, *_args):
            pass

    class Capture:
        def receive(self):
            raise RuntimeError("raw capture fault")

    class Eve:
        truncated = 0
        def receive(self):
            self.truncated += 1
            sensor.stop_event.set()
            return None

    class Preflight:
        def validate(self):
            raise SensorPreflightError("capture_interface_unavailable")

    class Producer:
        permanent_fault = False
        def deliver_once(self):
            sensor.stop_event.set()
            return SimpleNamespace(status="retry", delay_seconds=0, delivered=0)

    clock = Clock()
    config = sensor_config_from_env({"DEVICE_FINGERPRINT_SENSOR_ENABLED": "true"})
    assert HEARTBEAT_SECONDS == 300
    assert SOURCE_KINDS == ("dhcp", "tcp_syn", "tls_client", "quic_client")
    tracker = SourceHealthTracker(config, monotonic=clock)
    assert tracker.transition("dhcp", "available", None) is not None
    clock.value = 299
    assert tracker.transition("dhcp", "available", None) is None
    clock.value = 300
    assert tracker.transition("dhcp", "available", None) is not None
    assert tracker.transition("dhcp", "unavailable", "raw_parser_unavailable") is not None
    assert tracker.transition("dhcp", "unsupported", None) is not None

    spool = Spool()
    sensor = SensorRuntime(config, telemetry=SensorTelemetry(Log()), monotonic=clock,
                           preflight=Preflight(), capture=Capture(), eve=Eve(),
                           spool=spool, producer=Producer())
    assert sensor.preflight_or_report() is False
    sensor._raw_loop()
    sensor._suricata_heartbeat()
    clock.value += 31
    sensor._check_suricata_heartbeat()
    sensor.stop_event.clear()
    sensor._eve_loop()
    sensor.stop_event.clear()
    sensor._delivery_loop()
    assert {event.document["reason_code"] for event in spool.events if event.document["reason_code"]} == {
        "capture_interface_unavailable", "raw_parser_unavailable",
        "suricata_unavailable", "eve_datagram_truncated",
        "ingest_delivery_unavailable",
    }
    assert {event.document["status"] for event in spool.events} >= {"available", "unavailable"}


def test_sensor_spool_stale_eviction_and_capacity_block_are_real(tmp_path):
    clock = SpoolClock()
    value = make_spool(tmp_path, clock, max_events=2)
    value.enqueue([spool_event(1), spool_event(2)])
    value.enqueue([spool_event(3)])
    assert value.evicted == 1
    value.enqueue([spool_event(4, observed="2026-09-12T00:00:00.000Z")])
    assert value.stale_dropped == 1
    value.close()
    (tmp_path / "blocked").mkdir()
    blocked = make_spool(tmp_path / "blocked", clock, max_events=1)
    blocked.enqueue([spool_event(5, endpoint="source_health")])
    assert blocked.enqueue([spool_event(6, endpoint="source_health")]) == 0
    assert blocked.capacity_blocked is True
    blocked.close()


def test_portal_event_driven_transitions_backfill_and_bounded_loss():
    value, producer, clock = portal_runtime()
    clock.advance(86_400)
    assert value.process_once() == 0
    assert producer.health == []
    assert value.try_submit(session(), candidate(clock))
    value.process_once()
    assert [event["status"] for event in producer.health[-1]] == ["available"]
    assert all(event["source_kind"] == "portal_headers" for batch in producer.health for event in batch)

    recovery, recovery_producer, recovery_clock = portal_runtime([
        DeliveryResult("transient", 30, 503), DeliveryResult("success", 0, 200),
    ])
    assert recovery.try_submit(session(), candidate(recovery_clock))
    recovery.process_once()
    outage_start = recovery.unavailable_started_at
    recovery_clock.advance(30)
    assert recovery.try_submit(session(), candidate(recovery_clock))
    recovery.process_once()
    assert [event["status"] for event in recovery_producer.health[-1]] == ["unavailable", "available"]
    assert recovery_producer.health[-1][0]["reason_code"] == "ingest_delivery_unavailable"
    assert recovery_producer.health[-1][0]["observed_at"] == outage_start.isoformat(
        timespec="milliseconds").replace("+00:00", "Z")

    limited, limited_producer, limited_clock = portal_runtime()
    limited.queue.maxsize = 1
    assert limited.try_submit(session(), candidate(limited_clock))
    assert not limited.try_submit(session(client_mac="AA:BB:CC:DD:EE:01"), candidate(limited_clock))
    limited_clock.advance(301)
    limited.process_once()
    assert limited_producer.evidence == []
