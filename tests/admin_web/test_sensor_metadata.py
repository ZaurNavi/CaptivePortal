from datetime import timedelta
import json
from types import SimpleNamespace

import pytest

from app.admin_web.operations_service import AdminOperationsReadService
from app.admin_web import operations_service as ops
from tests.admin_web.test_operations_inventory import resolved
from tests.admin_web.test_operations_service import NOW, regular, systemd_text
from tests.device_fingerprint_sensor.test_operations_metadata import report


@pytest.mark.parametrize("kind", ["fresh", "missing", "stale", "denied", "journal-only", "collision", "crash"])
def test_v1_uses_only_export_no_sensor_filesystem_fallback_and_journal_not_wal(kind):
    bound, calls, reports = resolved(), [], []
    value = report()
    for identity, rows in value["stores"].items():
        rows["main"]["bytes"], rows["wal"]["bytes"], rows["shm"]["bytes"] = 64, 0, 64
    value["stores"]["sensor_spool"]["journal"]["bytes"] = 999
    if kind == "denied":
        value["stores"]["sensor_spool"]["main"] = dict(presence="unknown",bytes=None,reason="permission_denied")
    if kind == "journal-only":
        value["stores"]["sensor_spool"]["journal"] = dict(presence="unknown",bytes=None,reason="stat_unavailable")
    if kind == "collision":
        value["stores"]["sensor_spool"]["main"] = dict(presence="unknown",bytes=None,reason="identity_collision")
    class Reader:
        def read(self, service, now, **kwargs):
            reports.append(service["id"])
            assert service["id"] == "fingerprint_sensor"
            if kind == "crash": raise OSError("PRIVATE_REPORT_ERROR")
            if kind in {"missing", "stale"}: return dict(status="stale" if kind == "stale" else "unknown", reason="metadata_stale" if kind == "stale" else "metadata_unavailable", stores=None)
            return dict(status="fresh", reason=None, stores=value["stores"], expires_boottime_ns=ops.boot_ns()+180_000_000_000)
    def probe(path):
        assert not path.startswith(tuple(bound.paths[s] for s in ("network_attribution", "sensor_spool"))), "raw Sensor stat forbidden"
        calls.append(path)
        return regular(path)
    service = AdminOperationsReadService(bound, acquire=lambda c:systemd_text(), lstat=probe,
        now=lambda:NOW, sensor_metadata=Reader())
    try:
        model = service.read("safe")
        assert len(calls) == 45 and reports == ["fingerprint_sensor"]
        assert model["api_version"] == "admin.operations.db-services.v1"
        assert len(model["services"]) == 9 and len(model["databases"]) == 17
        assert len(model["topology"]["nodes"]) == 31 and len(model["topology"]["edges"]) == 45
        assert all(row["application_health"] == "unknown" for row in model["services"])
        sensor = next(r for r in model["databases"] if r["id"] == "sensor_spool")
        assert not {"journal_bytes", "metadata_source", "metadata_age"} & set(sensor), "no breaking V1 DTO extension"
        assert sensor["health_evidence"] == "none" and sensor["schema_observed_version"] is None
        if kind in {"missing", "stale", "crash", "denied", "collision"}:
            assert sensor["operational_state"] == ("stale" if kind == "stale" else "unknown")
            assert sensor["total_footprint_bytes"] is None
        else:
            assert sensor["total_footprint_bytes"] == 128 and sensor["wal_bytes"] == 0
        assert len(json.dumps(model).encode()) < 48000 and "PRIVATE_REPORT_ERROR" not in json.dumps(model)
    finally:
        service.close()


def test_unprovisioned_reader_fails_closed_without_artifact_read_on_unknown_process():
    from app.device_fingerprint_sensor.operations_metadata import SensorMetadataReader
    calls = []
    def forbidden():
        calls.append(1)
        raise AssertionError("no channel read without process identity")
    reader = SensorMetadataReader(channel=forbidden)
    result = reader.read(dict(operational_state="unknown",main_pid=None), NOW,
                         deadline=1, monotonic=lambda:0)
    assert result == dict(status="unknown",reason="metadata_unavailable",stores=None)
    assert calls == []


def test_source_ttl_expires_inside_fresh_30_second_cache_without_new_collection(monkeypatch):
    clock, calls = [0], []
    monkeypatch.setattr(ops,'boot_ns',lambda:clock[0])
    value = report()
    class Reader:
        def read(self,*args,**kwargs):
            calls.append(1)
            return dict(status='fresh',reason=None,stores=value['stores'],expires_boottime_ns=1_000_000_000)
    service = AdminOperationsReadService(resolved(),acquire=lambda c:systemd_text(),lstat=regular,
        now=lambda:NOW,sensor_metadata=Reader(),monotonic=lambda:0)
    try:
        assert service.read('first')['summary']['databases']['present_unverified'] == 17
        clock[0] = 1_000_000_001
        model = service.read('expired-source')
        assert calls == [1] and model['sample_status'] == 'fresh'
        assert model['summary']['databases']['present_unverified'] == 15
        for row in model['databases']:
            if row['id'] in {'network_attribution','sensor_spool'}:
                assert row['operational_state'] == 'stale' and row['total_footprint_bytes'] is None
        assert '_sensor_expires_boottime_ns' not in model
    finally:
        service.close()
