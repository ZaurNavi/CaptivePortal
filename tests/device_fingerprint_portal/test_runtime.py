from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.device_fingerprint_portal.config import SITE_ID, portal_config_from_env
from app.device_fingerprint_portal.models import DeliveryResult, PortalEvidenceCandidate
from app.device_fingerprint_portal.runtime import PortalEvidenceRuntime

UTC = timezone.utc


class Clock:
    monotonic_value = 0.0
    now_value = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
    def monotonic(self): return self.monotonic_value
    def now(self): return self.now_value
    def advance(self, seconds):
        self.monotonic_value += seconds; self.now_value += timedelta(seconds=seconds)


class Producer:
    def __init__(self, outcomes=None): self.outcomes=list(outcomes or [DeliveryResult("success",0)]); self.evidence=[]; self.health=[]
    def deliver_evidence(self, events):
        self.evidence.append(list(events)); return self.outcomes.pop(0)
    def deliver_source_health(self, events):
        self.health.append(list(events)); return DeliveryResult("success",0)


def candidate(clock, payload=None):
    return PortalEvidenceCandidate("capport_login", clock.now().isoformat(timespec="milliseconds").replace("+00:00","Z"), payload or {
        "platform_family":"android", "mobile_boolean":True, "browser_runtime_family":"chromium",
        "webview_or_captive_context":None, "model_family":None, "os_major":14,
        "platform_source":"user_agent", "mobile_source":"user_agent", "runtime_source":"user_agent",
        "context_source":None, "model_source":None, "os_major_source":"user_agent",
        "ua_present":True, "sec_ch_ua_present":False, "sec_ch_ua_platform_present":False,
        "sec_ch_ua_mobile_present":False,
    }, "valid")


def session(**changes):
    values = dict(site_id=SITE_ID, client_mac="AA:BB:CC:DD:EE:FF", client_ip="192.168.8.10", ssid="Zefer_Parki", ap_mac="SECRET")
    values.update(changes); return SimpleNamespace(**values)


def runtime(outcomes=None):
    clock=Clock(); producer=Producer(outcomes); config=portal_config_from_env({})
    value=PortalEvidenceRuntime(config, producer=producer, monotonic=clock.monotonic, now=clock.now)
    return value, producer, clock


def test_scope_envelope_coalescing_and_no_ap_identity():
    value, _producer, clock = runtime()
    assert value.try_submit(session(), candidate(clock))
    assert not value.try_submit(session(), candidate(clock))
    item=value.queue.get_nowait(); assert item.event["observed_mac"] == "AA:BB:CC:DD:EE:FF"
    assert item.event["observed_ip"] == "192.168.8.10"
    assert "ap_mac" not in repr(item.event).lower()
    assert not value.try_submit(session(client_mac=None), candidate(clock))
    assert not value.try_submit(session(site_id="other"), candidate(clock))
    assert not value.try_submit(session(client_ip="10.0.0.1"), candidate(clock))
    assert not value.try_submit(session(ssid="Other"), candidate(clock))
    assert value.try_submit(session(client_ip=None, client_mac="AA:BB:CC:DD:EE:01", ssid=None), candidate(clock))


def test_coalescer_key_keeps_mac_payload_and_subtype_independent():
    value, _producer, clock = runtime()
    original = candidate(clock)
    changed = candidate(clock, {**original.payload, "os_major": 13})
    assert value.try_submit(session(), original)
    assert value.try_submit(session(client_mac="AA:BB:CC:DD:EE:01"), original)
    assert value.try_submit(session(), changed)
    assert value.try_submit(session(), replace(original, source_subtype="omada_external_portal"))
    assert value.queue.qsize() == 4
    assert not value.try_submit(session(), original)


def test_transient_cooldown_shortens_key_and_blocks_http_until_expiry():
    value, producer, clock = runtime([DeliveryResult("transient",30,503), DeliveryResult("success",0,200)])
    assert value.try_submit(session(), candidate(clock)); item=list(value.queue.queue)[0]; original=value.coalescer.expiry(item.coalescer_key)
    value.process_once(); assert value.cooldown_until == 30; assert value.coalescer.expiry(item.coalescer_key) == 30 < original
    different=candidate(clock, {**candidate(clock).payload, "os_major":13})
    assert value.try_submit(session(), different); value.process_once(); assert len(producer.evidence) == 1
    clock.advance(30); assert value.try_submit(session(), candidate(clock)); value.process_once(); assert len(producer.evidence) == 2
    assert [event["status"] for event in producer.health[-1]] == ["unavailable", "available"]


@pytest.mark.parametrize("result", [
    DeliveryResult("transient", 30, 503),
    DeliveryResult("transient", 7, 429),
    DeliveryResult("permanent", 300, 404),
    DeliveryResult("config_unavailable", 300),
])
def test_cooldown_and_coalescer_deadline_start_after_delivery_outcome(result):
    clock = Clock()

    class AdvancingProducer(Producer):
        def deliver_evidence(self, events):
            self.evidence.append(list(events))
            clock.advance(2)
            return result

    producer = AdvancingProducer()
    value = PortalEvidenceRuntime(
        portal_config_from_env({}),
        producer=producer,
        monotonic=clock.monotonic,
        now=clock.now,
    )
    assert value.try_submit(session(), candidate(clock))
    item = list(value.queue.queue)[0]
    value.process_once()
    expected = 2 + result.cooldown_seconds
    assert value.cooldown_until == expected
    assert value.coalescer.expiry(item.coalescer_key) == expected
    clock.advance(result.cooldown_seconds)
    assert value.try_submit(session(), candidate(clock))


def test_exception_cooldown_starts_after_failed_delivery_returns_control():
    clock = Clock()

    class RaisingProducer(Producer):
        def deliver_evidence(self, events):
            list(events)
            clock.advance(2)
            raise RuntimeError("contained")

    value = PortalEvidenceRuntime(
        portal_config_from_env({}),
        producer=RaisingProducer(),
        monotonic=clock.monotonic,
        now=clock.now,
    )
    assert value.try_submit(session(), candidate(clock))
    item = list(value.queue.queue)[0]
    value.process_once()
    assert value.cooldown_until == 32
    assert value.coalescer.expiry(item.coalescer_key) == 32


def test_transient_health_epoch_starts_at_post_delivery_outcome_time():
    clock = Clock()
    initial = clock.now_value

    class AdvancingTransientProducer(Producer):
        def deliver_evidence(self, events):
            self.evidence.append(list(events))
            clock.advance(2)
            return DeliveryResult("transient", 30, 503)

    value = PortalEvidenceRuntime(
        portal_config_from_env({}),
        producer=AdvancingTransientProducer(),
        monotonic=clock.monotonic,
        now=clock.now,
    )
    assert value.try_submit(session(), candidate(clock))
    value.process_once()
    assert value.unavailable_started_at == initial + timedelta(seconds=2)


def test_initial_available_health_uses_post_delivery_outcome_time():
    clock = Clock()
    initial = clock.now_value

    class AdvancingSuccessProducer(Producer):
        def deliver_evidence(self, events):
            self.evidence.append(list(events))
            clock.advance(2)
            return DeliveryResult("success", 0, 200)

    producer = AdvancingSuccessProducer()
    value = PortalEvidenceRuntime(
        portal_config_from_env({}),
        producer=producer,
        monotonic=clock.monotonic,
        now=clock.now,
    )
    assert value.try_submit(session(), candidate(clock))
    value.process_once()
    assert producer.health[0][0]["observed_at"] == (
        initial + timedelta(seconds=2)
    ).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def test_recovery_health_preserves_failure_outcome_and_uses_success_outcome_time():
    clock = Clock()
    initial = clock.now_value

    class AdvancingOutcomeProducer(Producer):
        def deliver_evidence(self, events):
            self.evidence.append(list(events))
            clock.advance(2)
            return self.outcomes.pop(0)

    producer = AdvancingOutcomeProducer([
        DeliveryResult("transient", 30, 503),
        DeliveryResult("success", 0, 200),
    ])
    value = PortalEvidenceRuntime(
        portal_config_from_env({}),
        producer=producer,
        monotonic=clock.monotonic,
        now=clock.now,
    )
    assert value.try_submit(session(), candidate(clock))
    value.process_once()
    first_failure = initial + timedelta(seconds=2)
    assert value.unavailable_started_at == first_failure
    clock.advance(30)
    assert value.try_submit(session(), candidate(clock))
    value.process_once()
    assert [event["status"] for event in producer.health[-1]] == ["unavailable", "available"]
    assert producer.health[-1][0]["observed_at"] == first_failure.isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")
    assert producer.health[-1][1]["observed_at"] == (
        initial + timedelta(seconds=34)
    ).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def test_config_unavailable_from_unknown_does_not_fabricate_central_unavailable():
    value, producer, clock = runtime([
        DeliveryResult("config_unavailable", 300),
        DeliveryResult("success", 0, 200),
    ])
    assert value.try_submit(session(), candidate(clock))
    value.process_once()
    assert value.health_state == "unknown"
    assert value.unavailable_started_at is None
    clock.advance(300)
    assert value.try_submit(session(), candidate(clock))
    value.process_once()
    assert [[event["status"] for event in batch] for batch in producer.health] == [["available"]]


def test_config_unavailable_from_available_does_not_create_health_transition():
    value, producer, clock = runtime([
        DeliveryResult("success", 0, 200),
        DeliveryResult("config_unavailable", 300),
        DeliveryResult("success", 0, 200),
    ])
    for client_mac in ("AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"):
        assert value.try_submit(session(client_mac=client_mac), candidate(clock))
        value.process_once()
    assert value.health_state == "available"
    assert value.unavailable_started_at is None
    clock.advance(300)
    assert value.try_submit(session(client_mac="AA:BB:CC:DD:EE:03"), candidate(clock))
    value.process_once()
    assert [[event["status"] for event in batch] for batch in producer.health] == [["available"]]


def test_repeated_transient_failures_preserve_first_unavailable_timestamp():
    value, producer, clock = runtime([
        DeliveryResult("transient", 30, 503),
        DeliveryResult("transient", 30, 503),
        DeliveryResult("success", 0, 200),
    ])
    first_unavailable = clock.now_value
    for client_mac in ("AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"):
        assert value.try_submit(session(client_mac=client_mac), candidate(clock))
        value.process_once()
        clock.advance(30)
    assert value.unavailable_started_at == first_unavailable
    assert value.try_submit(session(client_mac="AA:BB:CC:DD:EE:03"), candidate(clock))
    value.process_once()
    health = producer.health[-1]
    assert [event["status"] for event in health] == ["unavailable", "available"]
    assert health[0]["observed_at"] == first_unavailable.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def test_source_health_submission_failure_does_not_change_evidence_success():
    class HealthFailureProducer(Producer):
        def deliver_source_health(self, events):
            list(events)
            raise RuntimeError("contained")

    clock = Clock()
    producer = HealthFailureProducer()
    value = PortalEvidenceRuntime(
        portal_config_from_env({}),
        producer=producer,
        monotonic=clock.monotonic,
        now=clock.now,
    )
    assert value.try_submit(session(), candidate(clock))
    assert value.process_once() == 1
    assert value.health_state == "available"
    assert value.unavailable_started_at is None


def test_stale_queue_item_is_removed_and_can_be_readmitted_immediately():
    value, producer, clock = runtime(); assert value.try_submit(session(), candidate(clock)); first=list(value.queue.queue)[0]
    clock.advance(301); value.process_once(); assert producer.evidence == []; assert value.coalescer.expiry(first.coalescer_key) is None
    assert value.try_submit(session(), candidate(clock))


def test_initial_health_once_and_stale_recovery_omits_unavailable():
    value, producer, clock = runtime([DeliveryResult("success",0), DeliveryResult("transient",30), DeliveryResult("success",0)])
    value.try_submit(session(), candidate(clock)); value.process_once(); assert [[e["status"] for e in batch] for batch in producer.health] == [["available"]]
    clock.advance(21601); value.try_submit(session(), candidate(clock)); value.process_once()
    clock.advance(86401); value.try_submit(session(), candidate(clock)); value.process_once()
    assert [event["status"] for event in producer.health[-1]] == ["available"]


def test_worker_thread_contract_is_one_named_daemon():
    value, _producer, _clock = runtime(); value.start()
    assert value.thread.name == "device-fingerprint-portal" and value.thread.daemon
    value.stop(); value.thread.join(timeout=1)
