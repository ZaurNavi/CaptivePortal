"""Optional Device Card observations preserve the existing read/ACL boundary."""
import logging
import sqlite3
import time
from types import SimpleNamespace

import pytest

from app.admin_web.device_fingerprint_presentation import ObservedDeviceHintsPresentationService
from app.admin_web.models import AdminPrincipal
from app.admin_web.query_service import AdminQueryForbidden, AdminQueryNotFound
from app.analytics.source_gateway import QueryDeadline
from app.device_fingerprint.read_service import DeviceFingerprintReadService
from tests.device_fingerprint.test_observed_hints import SITE, MAC, FIRST, AS_OF, portal, retained
from .test_query_service import _service, DEVICE_ID


@pytest.mark.parametrize("failure", [OSError("private-path-canary"), sqlite3.OperationalError("locked"),
                                     sqlite3.DatabaseError("malformed"), PermissionError("secret-canary")])
def test_A12_failure_is_additive_and_does_not_change_canonical_fingerprint(failure):
    query, _, _, _ = _service()
    before = query.device_detail(AdminPrincipal("operator"), SITE, DEVICE_ID).result
    class Broken:
        def latest_observed_hints(self, *args, **kwargs):
            raise failure
    query._observed_device_hints = ObservedDeviceHintsPresentationService(Broken())
    result = query.device_detail(AdminPrincipal("operator"), SITE, DEVICE_ID).result
    assert result == before
    assert result["observed_device_hints"] == ObservedDeviceHintsPresentationService.unavailable()
    assert "canary" not in repr(result) and "private-path" not in repr(result)


def test_A14_authorized_resolved_identity_only_and_no_list_reads():
    query, devices, _, _ = _service()
    calls = []
    class Reader:
        def latest_observed_hints(self, site, mac, **kwargs):
            calls.append((site, mac, kwargs))
            return dict(state="no_evidence", coverage="bounded_latest_256", trust="observed_unverified",
                        reported_model=None, reported_os=None, sources=[])
    query._observed_device_hints = ObservedDeviceHintsPresentationService(Reader())
    principal = AdminPrincipal("operator")
    query.list_devices(principal, SITE, limit=100)
    assert calls == []
    query.device_detail(principal, SITE, DEVICE_ID)
    assert len(calls) == 1 and calls[0][:2] == (SITE, MAC)
    assert calls[0][2]["site_first_seen_at"] == "2026-01-01T00:00:00.000Z"
    assert calls[0][2]["deadline"] is devices.calls[-1]["deadline"]
    with pytest.raises(AdminQueryForbidden):
        query.device_detail(principal, "1123456789abcdef01234567", DEVICE_ID)
    devices.get_device = lambda **kwargs: None
    with pytest.raises(AdminQueryNotFound):
        query.device_detail(principal, SITE, DEVICE_ID)
    assert len(calls) == 1


def test_A12_missing_db_does_not_create_files(tmp_path):
    path = tmp_path / "absent.sqlite3"
    service = ObservedDeviceHintsPresentationService(DeviceFingerprintReadService(str(path), retention_days=30))
    assert service.get(SITE, MAC, site_first_seen_at=FIRST, as_of_utc=AS_OF,
                       deadline=QueryDeadline.after(3))["state"] == "unavailable"
    assert list(tmp_path.iterdir()) == []


def test_A16_historical_observations_need_no_live_services(retained):
    path, _, add = retained
    add(portal())
    service = ObservedDeviceHintsPresentationService(DeviceFingerprintReadService(str(path), retention_days=30))
    dto = service.get(SITE, MAC, site_first_seen_at=FIRST, as_of_utc=AS_OF, deadline=QueryDeadline.after(5))
    assert dto["reported_model"]["observed_at_utc"] == "2026-10-17T10:00:00.000Z"
    assert dto["trust"] == "observed_unverified"
    assert set(dto).isdisjoint({"live", "confidence", "classification", "payload_json", "observed_mac"})


@pytest.mark.parametrize("retention", [17, "17"])
def test_runtime_uses_only_configured_evidence_path_and_retention(tmp_path, retention):
    from .test_runtime import create_admin_web_runtime, _device_list_context_sources
    from .conftest import enabled_settings
    registry, visits, observations, analytics = _device_list_context_sources(tmp_path)
    path = str(tmp_path / "configured-evidence.sqlite3")
    runtime = create_admin_web_runtime(enabled_settings(device_fingerprint_db_path=path,
        device_fingerprint_retention_days=retention), analytics, registry, visits, observations,
        logging.getLogger("observed-hints-test"))
    reader = runtime.query_service._observed_device_hints._reader
    assert reader.db_path == path and reader.retention_days == 17
    assert not (tmp_path / "configured-evidence.sqlite3").exists()


@pytest.mark.parametrize("retention", [True, 17.5, "bad", "17.5", 0, 91, None])
def test_runtime_invalid_evidence_retention_is_optional_not_a_coerced_config(tmp_path, retention):
    from .test_runtime import create_admin_web_runtime, _device_list_context_sources
    from .conftest import enabled_settings
    registry, visits, observations, analytics = _device_list_context_sources(tmp_path)
    runtime = create_admin_web_runtime(enabled_settings(device_fingerprint_db_path=str(tmp_path / "absent.sqlite3"),
        device_fingerprint_retention_days=retention), analytics, registry, visits, observations,
        logging.getLogger("observed-hints-invalid-config"))
    assert runtime.state == "active"
    assert runtime.query_service._observed_device_hints._reader is None
    assert not (tmp_path / "absent.sqlite3").exists()


@pytest.mark.parametrize("seconds", [0.03, 2.0])
def test_A12_real_exclusive_lock_is_optional_and_respects_remaining_deadline(retained, seconds):
    path, db, add = retained
    add(portal())
    db.execute("BEGIN EXCLUSIVE")
    service = ObservedDeviceHintsPresentationService(DeviceFingerprintReadService(str(path), retention_days=30))
    deadline = QueryDeadline.after(seconds)
    started = time.monotonic()
    try:
        dto = service.get(SITE, MAC, site_first_seen_at=FIRST, as_of_utc=AS_OF, deadline=deadline)
    finally:
        db.rollback()
    assert dto == service.unavailable()
    assert time.monotonic() - started < seconds
    # A rejected optional read left no held reader or changed connection state.
    db.execute("BEGIN EXCLUSIVE")
    db.rollback()


def test_A12_corrupt_file_fails_soft_without_mutation(tmp_path):
    path = tmp_path / "corrupt.sqlite3"
    path.write_bytes(b"synthetic invalid SQLite file")
    before = path.read_bytes()
    service = ObservedDeviceHintsPresentationService(DeviceFingerprintReadService(str(path), retention_days=30))
    assert service.get(SITE, MAC, site_first_seen_at=FIRST, as_of_utc=AS_OF,
                       deadline=QueryDeadline.after(5)) == service.unavailable()
    assert path.read_bytes() == before


@pytest.mark.parametrize("unavailable", [False, True])
def test_A12_A14_existing_authenticated_http_device_card_preserves_core(admin_app, unavailable):
    from .conftest import login
    runtime = admin_app.extensions["admin_web_runtime"]
    query = runtime.query_service
    _, devices, reads, _ = _service()
    query._devices, query._reads = devices, reads
    calls = []
    class Reader:
        def latest_observed_hints(self, site, mac, **kwargs):
            calls.append((site, mac))
            if unavailable:
                raise PermissionError("private-path-canary")
            return dict(state="no_evidence", coverage="bounded_latest_256", trust="observed_unverified",
                        reported_model=None, reported_os=None, sources=[])
    query._observed_device_hints = ObservedDeviceHintsPresentationService(Reader())
    client = admin_app.test_client()
    endpoint = f"/admin/api/v1/sites/{SITE}/devices/{DEVICE_ID}"
    assert client.get(endpoint, base_url="https://localhost").status_code == 401
    assert calls == []
    assert login(client).status_code == 302
    response = client.get(endpoint, base_url="https://localhost")
    assert response.status_code == 200
    result = response.get_json()["result"]
    assert result["identity"]["canonical_mac"] == MAC
    assert result["latest_snapshot"] and result["recent_visits"] and result["latest_client_observation"]
    assert result["fingerprint"]["state"] == "unavailable"
    assert result["observed_device_hints"]["state"] == ("unavailable" if unavailable else "no_evidence")
    assert len(calls) == 1 and "canary" not in response.get_data(as_text=True)
    assert client.get(endpoint.replace(SITE, "1123456789abcdef01234567"), base_url="https://localhost").status_code == 403
    assert len(calls) == 1
