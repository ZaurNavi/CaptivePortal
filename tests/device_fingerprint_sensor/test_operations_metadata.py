import copy
from datetime import datetime, timezone
import json
import os
import stat
import threading
from types import SimpleNamespace

import pytest

from app.device_fingerprint_sensor import operations_metadata as m

NOW = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)


def report():
    return dict(schema_version=m.SCHEMA, producer_unit=m.UNIT,
        producer=dict(boot_id="11111111-1111-4111-8111-111111111111", pid=123, start_ticks=100),
        epoch="22222222-2222-4222-8222-222222222222", sequence=1,
        sample_time_utc=m.stamp(NOW), sample_boottime_ns=100000000000,
        source_status="complete", stores={identity: {component: dict(presence="present", bytes=64, reason=None)
            for component in components} for identity, components in m.COMPONENTS.items()})


def encoded(value):
    return json.dumps(value, separators=(",", ":")).encode()


def test_closed_report_roundtrip_only_two_stores_and_separate_journal():
    value = report()
    assert m.decode(encoded(value)) == value
    assert len(encoded(value)) < m.LIMIT
    assert set(value["stores"]) == {"network_attribution", "sensor_spool"}
    assert set(value["stores"]["sensor_spool"]) == {"main", "wal", "shm", "journal"}
    assert set(value["stores"]["network_attribution"]) == {"main", "wal", "shm"}
    for forbidden in (b"/var/", b"/opt/", b"st_ino", b"st_dev", b"device_id", b"client_mac", b"payload", b"token"):
        assert forbidden not in encoded(value)


@pytest.mark.parametrize("case", ["schema", "unit", "extra", "path", "unknown-store", "missing-store", "extra-component",
    "missing-component", "bad-presence", "unknown-zero", "present-reason", "absent-nonzero", "negative", "bool-size",
    "float-size", "big-size", "bool-sequence", "zero-sequence", "large-sequence", "pid-bool", "start-negative",
    "epoch", "boot", "time", "time-offset", "mono-negative", "mono-bool", "status", "extra-producer", "extra-row"])
def test_report_rejects_every_unapproved_field_type_and_value(case):
    value = report()
    row = value["stores"]["sensor_spool"]["main"]
    if case == "schema": value["schema_version"] = "other"
    elif case == "unit": value["producer_unit"] = "other.service"
    elif case in {"extra", "path"}: value["path"] = "/private/CANARY"
    elif case == "unknown-store": value["stores"]["anything"] = {}
    elif case == "missing-store": del value["stores"]["network_attribution"]
    elif case == "extra-component": value["stores"]["network_attribution"]["journal"] = copy.deepcopy(row)
    elif case == "missing-component": del value["stores"]["sensor_spool"]["journal"]
    elif case == "bad-presence": row["presence"] = "healthy"
    elif case == "unknown-zero": row.update(presence="unknown", bytes=0, reason="permission_denied")
    elif case == "present-reason": row["reason"] = "permission_denied"
    elif case == "absent-nonzero": row["presence"] = "absent"
    elif case in {"negative", "bool-size", "float-size", "big-size"}: row["bytes"] = {"negative":-1,"bool-size":True,"float-size":1.0,"big-size":m.MAXIMUM+1}[case]
    elif case in {"bool-sequence", "zero-sequence", "large-sequence"}: value["sequence"] = {"bool-sequence":True,"zero-sequence":0,"large-sequence":m.MAXIMUM+1}[case]
    elif case == "pid-bool": value["producer"]["pid"] = True
    elif case == "start-negative": value["producer"]["start_ticks"] = -1
    elif case == "epoch": value["epoch"] = "raw secret"
    elif case == "boot": value["producer"]["boot_id"] = 1
    elif case == "time": value["sample_time_utc"] = "not a date"
    elif case == "time-offset": value["sample_time_utc"] = "2026-10-21T12:00:00+00:00"
    elif case == "mono-negative": value["sample_boottime_ns"] = -1
    elif case == "mono-bool": value["sample_boottime_ns"] = True
    elif case == "status": value["source_status"] = "healthy"
    elif case == "extra-producer": value["producer"]["uid"] = 1000
    elif case == "extra-row": row["inode"] = 1
    with pytest.raises((ValueError, TypeError)):
        m.decode(encoded(value))


@pytest.mark.parametrize("raw", [b"", b"{}", b"null", b"[]", b"{", b"\xff", b"{}"+b" "*4095,
    b'{"schema_version":"x","schema_version":"x"}', b'{"x":NaN}', b'{"x":Infinity}'])
def test_json_fails_closed_including_duplicate_keys_and_size(raw):
    with pytest.raises(ValueError):
        m.decode(raw)


@pytest.mark.parametrize("reason", sorted(m.REASONS))
def test_unknown_component_requires_sanitized_reason_and_partial_status(reason):
    value = report()
    value["stores"]["sensor_spool"]["main"] = m.unknown(reason)
    value["source_status"] = "partial"
    assert m.decode(encoded(value)) == value
    value["stores"]["sensor_spool"]["main"]["reason"] = "/private/EXCEPTION"
    with pytest.raises(ValueError): m.decode(encoded(value))


@pytest.mark.parametrize("fault", ["none", "absent", "denied", "io", "symlink", "directory", "owner", "negative", "bool", "large", "collision", "timeout", "cancel", "disabled"])
def test_exact_seven_metadata_probes_safe_failures_and_no_payload(fault):
    calls, clock, cancel = [], [0.0], threading.Event()
    if fault == "cancel": cancel.set()
    def probe(path):
        calls.append(path)
        if fault == "absent": raise FileNotFoundError()
        if fault == "denied": raise PermissionError("PRIVATE_PATH_CANARY")
        if fault == "io": raise OSError("PRIVATE_PATH_CANARY")
        if fault == "timeout": clock[0] = 10
        return SimpleNamespace(st_uid=1 if fault == "owner" else 1000,
            st_mode={"symlink":stat.S_IFLNK,"directory":stat.S_IFDIR}.get(fault, stat.S_IFREG),
            st_size={"negative":-1,"bool":True,"large":m.MAXIMUM+1}.get(fault, 64),
            st_dev=1, st_ino=1 if fault == "collision" else len(calls), st_nlink=1)
    paths = dict(network_attribution=None if fault == "disabled" else "/safe/attribution", sensor_spool="/safe/spool")
    rows = m.collect_components(paths, 1000, deadline=1, lstat=probe, monotonic=lambda:clock[0], cancel=cancel)
    flat = [v for components in rows.values() for v in components.values()]
    assert len(flat) == 7 and len(calls) <= 7
    assert set(calls) <= {"/safe/attribution"+suffix for suffix in ("","-wal","-shm")} | {"/safe/spool"+suffix for suffix in ("","-wal","-shm","-journal")}
    if fault == "none": assert all(v["bytes"] == 64 for v in flat)
    elif fault == "absent": assert all(v == dict(presence="absent", bytes=0, reason=None) for v in flat)
    elif fault == "disabled": assert len(calls) == 4 and all(v == m.unknown("source_disabled") for v in rows["network_attribution"].values())
    else: assert all(v["presence"] == "unknown" and v["bytes"] is None for v in flat)
    assert "PRIVATE_PATH_CANARY" not in json.dumps(rows)


@pytest.mark.parametrize("flag", [None, "false", "TRUE", "1", "garbage"])
def test_existing_flag_off_never_opens_channel_or_stats(monkeypatch, flag):
    if flag is None: monkeypatch.delenv("WEB_ADMIN_DB_SERVICES_ENABLED", raising=False)
    else: monkeypatch.setenv("WEB_ADMIN_DB_SERVICES_ENABLED", flag)
    calls = []
    def forbidden():
        calls.append(1)
        raise AssertionError("OFF must not open channel")
    publisher = m.SensorMetadataPublisher({}, channel=forbidden)
    assert publisher.publish(threading.Event()) is False
    monkeypatch.setenv("WEB_ADMIN_DB_SERVICES_ENABLED", "true")
    assert publisher.publish(threading.Event()) is False, "startup-only flag cannot change in flight"
    assert calls == []


def test_failure_throttling_no_retry_thread_or_lifecycle_error():
    clock, calls = [0.0], []
    def unavailable():
        calls.append(1)
        raise OSError("PRIVATE_CANARY")
    publisher = m.SensorMetadataPublisher({}, channel=unavailable, monotonic=lambda:clock[0], enabled=True)
    assert publisher.publish(threading.Event()) is False
    clock[0] = 59.999
    assert publisher.publish(threading.Event()) is False and calls == [1]
    clock[0] = 60.0
    assert publisher.publish(threading.Event()) is False and calls == [1,1]
    publisher.lock.acquire()
    clock[0] = 120
    assert publisher.publish(threading.Event()) is False and calls == [1,1]
    publisher.lock.release()


@pytest.mark.parametrize("fail", [False, True])
def test_runtime_only_existing_tick_after_refresh_and_metrics_fail_isolated(fail):
    from app.device_fingerprint_sensor.runtime import SensorRuntime
    calls = []
    class Stop:
        def __init__(self): self.ticks=0
        def wait(self, seconds):
            assert seconds == 60.0
            self.ticks += 1
            return self.ticks > 1
        def is_set(self): return False
    def publish(cancel):
        calls.append("publish")
        if fail: raise OSError("private")
    runtime = object.__new__(SensorRuntime)
    runtime.stop_event = Stop()
    runtime._delivery_available = False
    runtime._refresh_state = lambda:calls.append("refresh")
    runtime._emit_metrics = lambda:calls.append("metrics")
    runtime._operations_metadata = SimpleNamespace(publish=publish)
    runtime._telemetry_loop()
    assert calls == ["refresh", "metrics", "publish"]


def test_stop_and_expired_budget_never_open_channel():
    calls = []
    def forbidden():
        calls.append(1)
        raise AssertionError("no work after stop/deadline")
    cancel = threading.Event(); cancel.set()
    publisher = m.SensorMetadataPublisher({},channel=forbidden,enabled=True)
    assert publisher.publish(cancel) is False and publisher.last_attempt is None
    reader = m.SensorMetadataReader(channel=forbidden)
    assert reader.read({},NOW,deadline=0,monotonic=lambda:0)['status'] == 'unknown'
    assert calls == []


def test_optional_exporter_composition_failure_cannot_change_sensor_startup(monkeypatch):
    from tests.device_fingerprint_sensor.test_runtime import Spool, Capture, Eve, Producer, Log, Preflight
    from app.device_fingerprint_sensor.runtime import SensorRuntime
    from app.device_fingerprint_sensor.config import sensor_config_from_env
    from app.device_fingerprint_sensor.telemetry import SensorTelemetry
    def fail(*args,**kwargs): raise OSError("private")
    monkeypatch.setattr(m,'SensorMetadataPublisher',fail)
    config = sensor_config_from_env({'DEVICE_FINGERPRINT_SENSOR_ENABLED':'true'})
    runtime = SensorRuntime(config,telemetry=SensorTelemetry(Log()),spool=Spool(),capture=Capture(),
        eve=Eve(),producer=Producer(),preflight=Preflight())
    assert runtime._operations_metadata is None and runtime.state == 'initializing'


def workload_report():
    from app.operations_health import sensor_health, SENSOR_UNIT, DEPENDENCIES
    value = report()
    value.update(schema_version=m.SCHEMA_V4,
        application_health=sensor_health('ready', dict.fromkeys(DEPENDENCIES[SENSOR_UNIT], True)),
        store_checks=dict(instance=value['epoch'], checks={'sensor_spool': dict(status='passed',
            scope=['schema_version'], checked_at_utc=m.stamp(NOW), checked_store_id='a'*64,
            observed_store_id='a'*64, reason='startup_check')}),
        workload=dict(spool_pending_rows=12, spool_bytes=1048576, oldest_spool_age_seconds=42))
    return value


@pytest.mark.parametrize('count', [None, 0, 1, m.MAXIMUM])
def test_phase1_sensor_v4_roundtrip_and_old_protocols(count):
    value = workload_report()
    value['workload'] = (m.sensor_workload() if count is None else dict(spool_pending_rows=count,
        spool_bytes=1048576, oldest_spool_age_seconds=None if count == 0 else count))
    assert m.decode(encoded(value)) == value
    assert len(encoded(value)) < m.LIMIT
    for schema in (m.SCHEMA_V3, m.SCHEMA_V2, m.SCHEMA):
        old = dict(value, schema_version=schema)
        old.pop('workload')
        if schema != m.SCHEMA_V3:old.pop('store_checks')
        if schema == m.SCHEMA:old.pop('application_health')
        assert m.decode(encoded(old)) == old


@pytest.mark.parametrize('field', ['spool_pending_rows', 'spool_bytes', 'oldest_spool_age_seconds'])
@pytest.mark.parametrize('bad', [True, -1, 2**53, 1.0, '1', None])
def test_phase1_sensor_v4_rejects_mixed_or_invalid_numbers(field, bad):
    value = workload_report(); value['workload'][field] = bad
    with pytest.raises(ValueError):m.decode(encoded(value))


@pytest.mark.parametrize('fault', ['extra', 'missing', 'null', 'empty-checks', 'no-checks', 'zero-age'])
def test_phase1_sensor_v4_exact_workload_and_real_v3_prerequisites(fault):
    value = workload_report()
    if fault == 'extra':value['workload']['private'] = 'PRIVATE'
    elif fault == 'missing':value['workload'].pop('spool_bytes')
    elif fault == 'null':value['workload'] = None
    elif fault == 'empty-checks':value['store_checks']['checks'] = {}
    elif fault == 'no-checks':value.pop('store_checks')
    elif fault == 'zero-age':value['workload']['spool_pending_rows'] = 0
    with pytest.raises(ValueError):m.decode(encoded(value))


def test_phase1_memory_sample_expires_without_io_or_previous_numeric():
    sample = m.SpoolWorkloadSample(100, 0, 8192, None)
    assert sample.project(280) == dict(spool_pending_rows=0, spool_bytes=8192, oldest_spool_age_seconds=None)
    for tick in (99, 280.001, float('inf'), float('nan')):
        with pytest.raises(ValueError):sample.project(tick)


@pytest.mark.skipif(os.name != 'posix', reason='Linux/POSIX Sensor native openat report contract')
@pytest.mark.parametrize('checks_present', [False, True])
def test_phase1_publisher_never_relabels_v2_without_checks_or_reads_spool(tmp_path, monkeypatch, checks_present):
    from app import operations_verification
    value = workload_report(); tick = [0.0]; calls = []
    checks = copy.deepcopy(value['store_checks'])
    if not checks_present:checks['checks'] = {}
    monkeypatch.setattr(operations_verification, 'snapshot', lambda *a, **kw:checks)
    class TestChannel:
        sensor_uid = os.geteuid()
        def open(self):return os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
        def validate_file(self, info):m.Channel(self.sensor_uid, os.getgid()).validate_file(info)
    def workload():calls.append('memory'); return value['workload']
    p = m.SensorMetadataPublisher(dict(sensor_spool=None, network_attribution=None), enabled=True,
        channel=TestChannel, monotonic=lambda:tick[0], now=lambda:NOW, boottime=lambda:100_000_000_000,
        identity=lambda pid, uid:dict(value['producer'], pid=pid), health_provider=lambda:value['application_health'],
        workload_provider=workload)
    assert p.publish(threading.Event())
    result = m.decode((tmp_path/m.REPORT).read_bytes())
    assert result['schema_version'] == (m.SCHEMA_V4 if checks_present else m.SCHEMA_V2)
    assert ('workload' in result) == checks_present
    assert calls == (['memory'] if checks_present else [])
    tick[0] = 59; assert not p.publish(threading.Event())
    assert calls == (['memory'] if checks_present else [])
    if checks_present:
        p.workload_provider = lambda: (_ for _ in ()).throw(RuntimeError('PRIVATE'))
        tick[0] = 60; assert p.publish(threading.Event())
        assert m.decode((tmp_path/m.REPORT).read_bytes())['workload'] == m.sensor_workload()


@pytest.mark.parametrize('uid,gid,accepted',[(994,995,True),(0,995,False),(994,0,False),(994,993,False)])
def test_configured_reader_group_must_not_alias_sensor_raw_primary_group(monkeypatch,uid,gid,accepted):
    import sys
    monkeypatch.setitem(sys.modules,'pwd',SimpleNamespace(getpwnam=lambda name:SimpleNamespace(pw_uid=uid,pw_gid=993)))
    monkeypatch.setitem(sys.modules,'grp',SimpleNamespace(getgrnam=lambda name:SimpleNamespace(gr_gid=gid)))
    if accepted:
        value = m.configured_channel()
        assert value.directory == '/run/captiveportal-operations' and value.sensor_uid == uid and value.reader_gid == gid
    else:
        with pytest.raises(m.MetadataUnavailable): m.configured_channel()
