from datetime import timedelta

import pytest

from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.read_service import DeviceFingerprintReadService
from app.device_fingerprint.validation import format_utc
from tests.device_fingerprint import NOW, SITE, evidence_event, health_event, producer
from tests.device_fingerprint.test_repository import service


def test_bounded_keyset_evidence_and_latest_point_health(tmp_path):
    cfg, _repo, svc = service(tmp_path)
    read = DeviceFingerprintReadService(cfg.db_path, retention_days=30)
    assert read.latest_source_health(SITE, "zefer-span-01", "dhcp", through_utc=format_utc(NOW)) is None
    events = [evidence_event(source_event_id=f"{number:08d}-1111-4111-8111-111111111111") for number in (1, 2)]
    svc.evidence_batch(producer(), {"producer_id": producer().producer_id, "events": events})
    svc.source_health_batch(producer(), {"producer_id": producer().producer_id, "events": [health_event()]})
    first = read.list_evidence(SITE, "AA:BB:CC:DD:EE:FF", format_utc(NOW - timedelta(hours=1)), format_utc(NOW + timedelta(seconds=1)), limit=1)
    assert len(first["items"]) == 1 and first["next_cursor"]
    second = read.list_evidence(SITE, "AA:BB:CC:DD:EE:FF", format_utc(NOW - timedelta(hours=1)), format_utc(NOW + timedelta(seconds=1)), limit=1, cursor=first["next_cursor"])
    assert len(second["items"]) == 1
    latest = read.latest_source_health(SITE, "zefer-span-01", "dhcp", through_utc=format_utc(NOW))
    assert latest["status"] == "available" and "observed_at" in latest
    assert "through_utc" not in latest and "ended_at" not in latest


def test_read_range_limit_and_cursor_are_strict(tmp_path):
    cfg, _repo, _svc = service(tmp_path)
    read = DeviceFingerprintReadService(cfg.db_path, retention_days=30)
    with pytest.raises(DeviceFingerprintValidationError):
        read.list_evidence(SITE, "AA:BB:CC:DD:EE:FF", format_utc(NOW - timedelta(days=31)), format_utc(NOW), limit=100)
    with pytest.raises(DeviceFingerprintValidationError):
        read.list_evidence(SITE, "AA:BB:CC:DD:EE:FF", format_utc(NOW), format_utc(NOW), limit=100)
    with pytest.raises(DeviceFingerprintValidationError):
        read.list_evidence(SITE, "AA:BB:CC:DD:EE:FF", format_utc(NOW - timedelta(days=1)), format_utc(NOW), limit=501)


@pytest.mark.parametrize("status", ["available", "unavailable", "unsupported"])
def test_source_health_is_an_exact_point_event_without_interval_claim(tmp_path, status):
    cfg, _repo, svc = service(tmp_path)
    read = DeviceFingerprintReadService(cfg.db_path, retention_days=30)
    assert read.latest_source_health(
        SITE, "zefer-span-01", "dhcp", through_utc=format_utc(NOW)
    ) is None
    svc.source_health_batch(producer(), {
        "producer_id": producer().producer_id,
        "events": [health_event(status=status)],
    })
    latest = read.latest_source_health(
        SITE, "zefer-span-01", "dhcp", through_utc=format_utc(NOW)
    )
    assert latest["status"] == status
    assert latest["observed_at"] == format_utc(NOW)
    assert set(latest).isdisjoint({
        "observed_mac", "observed_ip", "from_utc", "through_utc", "ended_at",
    })
