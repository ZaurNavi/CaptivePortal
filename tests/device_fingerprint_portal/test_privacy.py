import ipaddress
from datetime import datetime, timezone
from types import SimpleNamespace

from app.device_fingerprint.models import DeviceFingerprintProducer
from app.device_fingerprint.repository import DeviceFingerprintRepository
from app.device_fingerprint.schema_registry import build_production_schema_registry
from app.device_fingerprint.service import DeviceFingerprintService
from app.device_fingerprint_portal.extractor import extract_portal_evidence_candidate
from app.device_fingerprint_portal.config import SITE_ID, portal_config_from_env
from app.device_fingerprint_portal.runtime import PortalEvidenceRuntime
from tests.device_fingerprint import config as core_config


def test_raw_headers_accept_language_and_build_canaries_are_not_normalized():
    canary="RAW-PRIVATE-CANARY"
    value=extract_portal_evidence_candidate({
        "User-Agent": f"Mozilla/5.0 (Android 14; Pixel 8 Build/{canary}) Chrome/120 Mobile",
        "sec-ch-ua": '"Chromium";v="120"',
        "Accept-Language": canary,
    }, source_subtype="omada_external_portal", observed_at=datetime.now(timezone.utc))
    assert canary not in repr(value.payload)
    assert "Accept-Language" not in repr(value.payload)


def test_only_normalized_p1_payload_reaches_task01_storage(tmp_path):
    observed = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
    canary = "PRIVATE-RAW-HEADER-CANARY"
    candidate = extract_portal_evidence_candidate({
        "User-Agent": f"Mozilla/5.0 (Android 14; Pixel 8 Build/{canary}) Chrome/120 Mobile",
        "sec-ch-ua": '"Chromium";v="120"',
    }, source_subtype="capport_login", observed_at=observed)
    portal_runtime = PortalEvidenceRuntime(
        portal_config_from_env({}),
        now=lambda: observed,
        monotonic=lambda: 1.0,
    )
    session = SimpleNamespace(
        site_id=SITE_ID, client_mac="AA:BB:CC:DD:EE:FF",
        client_ip="192.168.8.10", ssid="Zefer_Parki", ap_mac="NEVER-DURABLE",
    )
    assert portal_runtime.try_submit(session, candidate)
    event = portal_runtime.queue.get_nowait().event

    cfg = core_config(tmp_path)
    repository = DeviceFingerprintRepository(cfg.db_path, max_db_bytes=cfg.max_db_bytes)
    repository.initialize()
    producer = DeviceFingerprintProducer(
        "portal-zefer-01", "A" * 32, "zefer-portal-http-01", SITE_ID,
        (ipaddress.ip_network("192.168.8.0/22"),), ("portal_headers",),
    )
    service = DeviceFingerprintService(
        cfg, repository, build_production_schema_registry(), now=lambda: observed,
    )
    service.evidence_batch(producer, {"producer_id": producer.producer_id, "events": [event]})
    row = repository.connection.execute(
        "SELECT privacy_class,payload_json FROM device_fingerprint_evidence"
    ).fetchone()
    assert row[0] == "P1"
    assert canary not in row[1] and "NEVER-DURABLE" not in row[1]
