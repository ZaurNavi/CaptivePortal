"""Issue298: exactly three Phase A sources, cached v2 only, Phase B stays unknown."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from app.admin_web import operations_service as ops
from app.admin_web.operations_schema import validate_v2
from app.operations_health import OWNER_SERVICES as FILE_SERVICES, owner_health
from tests.admin_web.test_operations_inventory import resolved
from tests.admin_web.test_operations_service import NOW, regular, systemd_text
from tests.admin_web.test_operations_v2 import Reader, ORIGIN

OWNER_SERVICES = {key: FILE_SERVICES[key] for key in
    ('fingerprint_evidence', 'network_metadata', 'network_service_recognition')}


class OwnerReader(Reader):
    def __init__(self, unit, native):
        super().__init__(); self.unit, self.native, self.status = unit, native, 'fresh'
        self.channel = lambda: SimpleNamespace(uid=1000)

    def read(self, *args, **kwargs):
        self.calls += 1
        if self.status != 'fresh':return dict(status=self.status)
        return dict(status='fresh', health=owner_health(self.unit, self.native), producer=self.producer,
            observed_at=ops.timestamp(NOW), age=0, expires_boottime_ns=ORIGIN+180_000_000_000)


def service_for(monkeypatch, natives=None):
    clock = [ORIGIN]; tick = [0.0]; calls = []
    monkeypatch.setattr(ops, 'boot_ns', lambda: clock[0])
    natives = natives or dict(fingerprint_evidence='ready', network_metadata=SimpleNamespace(
        capture='usable', output='usable', ingest='usable', local_reasons=set()), network_service_recognition='backfilling')
    owners = {key: OwnerReader(unit, natives[key]) for key, unit in OWNER_SERVICES.items()}
    reports = {key: Reader('missing') for key in FILE_SERVICES}
    reports.update(owners)
    def acquire(cancel):calls.append(1); return systemd_text()
    value = ops.AdminOperationsReadService(resolved(), acquire=acquire, lstat=regular,
        now=lambda: NOW, monotonic=lambda: tick[0], sensor_metadata=Reader('missing'), owner_health_readers=reports)
    return value, owners, clock, tick, calls


def row_for(model, key):return next(row for row in model['services'] if row['id'] == key)


@pytest.mark.parametrize('count', [None, 0, 1, 2**53-1])
def test_phase1_ni04_v2_closed_report_and_legacy_decode(count):
    from app import operations_app_health as h
    from app.operations_health import NI04_UNIT, EVIDENCE_UNIT
    from tests.test_operations_app_health import report, raw
    old = report(); assert h.decode(raw(old), NI04_UNIT) == old
    new = dict(old, schema_version=h.SCHEMA_V2, workload=dict(feed_backlog_entries=count))
    assert h.decode(raw(new), NI04_UNIT) == new
    assert len(raw(new)) < h.m.LIMIT
    new['producer_unit'] = EVIDENCE_UNIT
    with pytest.raises(ValueError):h.decode(raw(new), EVIDENCE_UNIT)


@pytest.mark.parametrize('bad', [True, -1, 2**53, 1.0, '1', {}, [], float('nan')])
def test_phase1_ni04_workload_rejects_invalid_count(bad):
    from app import operations_app_health as h
    from app.operations_health import NI04_UNIT
    from tests.test_operations_app_health import report, raw
    value = dict(report(), schema_version=h.SCHEMA_V2, workload=dict(feed_backlog_entries=bad))
    with pytest.raises(ValueError):h.decode(raw(value), NI04_UNIT)


@pytest.mark.parametrize('fault', ['null', 'extra', 'missing', 'v1-with-workload'])
def test_phase1_ni04_v2_exact_root_and_metric(fault):
    from app import operations_app_health as h
    from app.operations_health import NI04_UNIT
    from tests.test_operations_app_health import report, raw
    value = dict(report(), schema_version=h.SCHEMA_V2, workload=dict(feed_backlog_entries=1))
    if fault == 'null':value['workload'] = None
    elif fault == 'extra':value['workload']['private'] = 1
    elif fault == 'missing':value.pop('workload')
    else:value['schema_version'] = h.SCHEMA
    with pytest.raises(ValueError):h.decode(raw(value), NI04_UNIT)


@pytest.mark.skipif(__import__('os').name != 'posix', reason='Linux/POSIX owner native openat report contract')
def test_phase1_backlog_changes_do_not_trigger_owner_transition_writes(tmp_path, monkeypatch):
    from app import operations_app_health as h
    from app.operations_health import NI04_UNIT
    from tests.test_operations_app_health import TestChannel, report, NOW as NATIVE_NOW
    tick = [0.0]; writes = []
    original = h.os.replace
    def replace(*args, **kwargs):writes.append(tick[0]); return original(*args, **kwargs)
    monkeypatch.setattr(h.os, 'replace', replace)
    p = h.HealthPublisher(NI04_UNIT, enabled=True, channel=lambda unit:TestChannel(tmp_path),
        monotonic=lambda:tick[0], now=lambda:NATIVE_NOW, boottime=lambda:100_000_000_000,
        identity=lambda pid, uid:dict(report()['producer'], pid=pid))
    health = owner_health(NI04_UNIT, 'usable')
    for instant in range(121):
        tick[0] = instant
        assert p.publish(health) == (instant % 60 == 0)
        assert p.last_health == health and 'workload' not in p.last_health
    assert writes == [0, 60, 120]
    assert h.decode((tmp_path/h.REPORT).read_bytes(), NI04_UNIT)['workload'] == dict(feed_backlog_entries=None,visit_outbox_unacked=None)


@pytest.mark.skipif(__import__('os').name != 'posix', reason='Linux/POSIX owner native openat report contract')
@pytest.mark.parametrize('fault', ['valid', 'stale', 'pid', 'start', 'boot', 'sequence', 'before-start'])
def test_phase1_ni04_reader_workload_uses_same_single_file_and_binding(tmp_path, monkeypatch, fault):
    from app import operations_app_health as h
    from tests.test_operations_app_health import reader_for, report, write_report, NOW as NATIVE_NOW
    value = dict(report(), schema_version=h.SCHEMA_V2, workload=dict(feed_backlog_entries=17))
    path, reader, service = reader_for(tmp_path, value, identity=lambda pid, uid:report()['producer'])
    calls = []; original = h.os.read
    def read(*args):calls.append(1); return original(*args)
    monkeypatch.setattr(h.os, 'read', read)
    first = reader.read(service, NATIVE_NOW, deadline=1, monotonic=lambda:0)
    assert first['status'] == 'fresh' and first['workload'] == value['workload'] and calls == [1]
    if fault == 'stale':
        from datetime import timedelta
        value['sequence'] += 1; value['sample_boottime_ns'] += 1_000_000_000
        value['sample_time_utc'] = h.m.stamp(NATIVE_NOW + timedelta(seconds=1))
        reader.boottime = lambda:282_000_000_000
        now = NATIVE_NOW + timedelta(seconds=182)
    else:
        now = NATIVE_NOW
        if fault in {'pid', 'start', 'boot'}:
            key = {'pid':'pid', 'start':'start_ticks', 'boot':'boot_id'}[fault]
            value['producer'][key] = ('33333333-3333-4333-8333-333333333333' if fault == 'boot' else value['producer'][key]+1)
        elif fault == 'sequence':value['sequence'] = 0
        elif fault == 'before-start':service['started_at_utc'] = '2099-01-01T00:00:00.000Z'
    write_report(path, value)
    second = reader.read(service, now, deadline=1, monotonic=lambda:0)
    assert calls == [1, 1]
    assert second['status'] == ('fresh' if fault == 'valid' else 'stale' if fault == 'stale' else 'unknown')
    assert ('workload' in second) == (fault == 'valid')


def test_three_owners_share_existing_sampler_and_v1_remains_unchanged(monkeypatch):
    service, owners, clock, tick, calls = service_for(monkeypatch)
    try:
        old = service.read('old'); model = validate_v2(service.read('new', version=2))
        for key in OWNER_SERVICES:
            row = row_for(model, key); evidence = row['application_health_evidence']
            assert row['application_health'] == 'healthy'
            assert evidence['source'] == 'source_self_reported_shared_uid'
            assert set(evidence) == {'state', 'source', 'observed_at', 'received_at', 'age', 'ttl', 'reason'}
            assert evidence['ttl'] == 180 and evidence['age'] == 0
            assert row['operational_state'] == 'running'
            assert owners[key].calls == 1
        assert row_for(model, 'network_service_recognition')['application_health_evidence']['reason'] == 'backfilling_incomplete_coverage'
        for key in ('portal_core', 'fingerprint_suricata', 'fingerprint_classification', 'traffic_projection'):
            evidence = row_for(model, key)['application_health_evidence']
            assert evidence['state'] == 'unknown' and evidence['source'] == 'none'
        assert all(row['application_health'] == 'unknown' for row in old['services'])
        for current, previous in zip(model['services'], old['services']):
            assert {k: current[k] for k in previous if k != 'application_health'} == {k: v for k, v in previous.items() if k != 'application_health'}
        assert len(model['services']) == 9 and len(model['databases']) == 17
        assert len(model['topology']['nodes']) == 31 and len(model['topology']['edges']) == 45
        assert len(json.dumps(model).encode()) < ops.RESPONSE_LIMIT
        assert all(token not in json.dumps(model) for token in ('boot_id', 'start_ticks', 'epoch', 'app-health.json', '/run/'))
        assert calls == [1]
        for _ in range(4):service.read('cached', version=2)
        assert calls == [1] and all(reader.calls == 1 for reader in owners.values())
        clock[0] += 180_000_000_001
        expired = validate_v2(service.read('ttl', version=2))
        assert all(row_for(expired, key)['application_health'] == 'stale' for key in OWNER_SERVICES)
        assert calls == [1] and all(reader.calls == 1 for reader in owners.values())
    finally:service.close()


@pytest.mark.parametrize('state', ['unknown', 'stale'])
def test_missing_stale_reports_never_turn_running_owner_green(monkeypatch, state):
    service, owners, *_ = service_for(monkeypatch)
    for reader in owners.values():reader.status = state
    try:
        model = validate_v2(service.read('missing', version=2))
        for key in OWNER_SERVICES:
            row = row_for(model, key)
            assert row['application_health'] == state and row['operational_state'] == 'running'
    finally:service.close()


@pytest.mark.parametrize('key', ['portal_core', 'fingerprint_suricata', 'fingerprint_classification', 'traffic_projection'])
def test_every_phase_b_id_rejects_wrong_source_pairing(monkeypatch, key):
    service, *_ = service_for(monkeypatch)
    try:model = service.read('phase-b', version=2)
    finally:service.close()
    row = row_for(model, key)
    row['application_health'] = 'healthy'
    row['application_health_evidence'] = copy.deepcopy(row_for(model, 'fingerprint_evidence')['application_health_evidence'])
    row['application_health_evidence']['source'] = 'sensor_native.v2'
    with pytest.raises(ops.OperationsError):validate_v2(model)


def test_authenticated_v2_route_accepts_new_sources_without_new_endpoint_or_sampling(monkeypatch):
    from tests.admin_web.test_db_services_routes import operations_app, logged_in
    app, runtime, _ = operations_app(monkeypatch)
    runtime.operations_service.close()
    service, owners, _, _, calls = service_for(monkeypatch)
    runtime.operations_service = service
    try:
        client = logged_in(app)
        for _ in range(2):
            response = client.get('/admin/api/v2/operations/db-services', base_url='https://localhost')
            assert response.status_code == 200
            assert row_for(response.json, 'network_service_recognition')['application_health_evidence']['reason'] == 'backfilling_incomplete_coverage'
        assert calls == [1] and all(reader.calls == 1 for reader in owners.values())
    finally:runtime.clear()


@pytest.mark.parametrize('native,state,reason', [
    ('lagging', 'degraded', 'source_lagging'), ('capacity_halted', 'unavailable', 'capacity_limited'),
    ('blocked_conflict', 'unavailable', 'blocked_conflict'), ('unknown', 'unknown', 'dependencies_unconfirmed'),
    ('stopping', 'unknown', 'source_stopping'), ('usable', 'healthy', 'source_ready'),
])
def test_ni04_owner_native_states_pass_both_projection_and_closed_schema(monkeypatch, native, state, reason):
    service, owners, *_ = service_for(monkeypatch)
    owners['network_service_recognition'].native = native
    try:
        row = row_for(validate_v2(service.read('state', version=2)), 'network_service_recognition')
        assert row['application_health'] == state and row['application_health_evidence']['reason'] == reason
    finally:service.close()


@pytest.mark.parametrize('fault', ['phase-b', 'wrong-source', 'extra', 'wrong-pair', 'wrong-owner', 'unknown-reason', 'old-source-new-reason', 'no-source-native-reason'])
def test_server_validator_does_not_expand_phase_b_or_allow_free_form_evidence(monkeypatch, fault):
    service, *_ = service_for(monkeypatch)
    try:model = service.read('schema', version=2)
    finally:service.close()
    row = row_for(model, 'network_service_recognition'); evidence = row['application_health_evidence']
    if fault == 'phase-b':
        other = row_for(model, 'portal_core'); other['application_health'] = 'healthy'
        other['application_health_evidence'] = copy.deepcopy(evidence)
    elif fault == 'wrong-source':evidence['source'] = 'sensor_native.v2'
    elif fault == 'extra':evidence['raw_path'] = '/PRIVATE'
    elif fault == 'wrong-pair':evidence['state'] = row['application_health'] = 'unavailable'
    elif fault == 'wrong-owner':
        other = row_for(model, 'fingerprint_evidence'); other['application_health_evidence'] = copy.deepcopy(evidence)
    elif fault == 'unknown-reason':evidence['reason'] = '/PRIVATE'
    elif fault == 'old-source-new-reason':row_for(model, 'fingerprint_sensor')['application_health_evidence']['reason'] = 'backfilling_incomplete_coverage'
    elif fault == 'no-source-native-reason':
        row['application_health'] = evidence['state'] = 'unknown'
        evidence.update(source='none', reason='source_initializing')
    with pytest.raises(ops.OperationsError):validate_v2(model)


@pytest.mark.parametrize('scenario', ['owner-valid', 'owner-backfill', 'owner-bad-source', 'owner-phase-b', 'owner-bad-pair', 'owner-wrong-owner'])
def test_owner_javascript_schema_and_visible_node_card_reason(monkeypatch, tmp_path, scenario):
    service, *_ = service_for(monkeypatch)
    try:model = service.read('js', version=2)
    finally:service.close()
    path = tmp_path/'model.json'; path.write_text(json.dumps(model), encoding='utf-8')
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([shutil.which('node'), str(Path(__file__).with_name('db_services_v2_ui.cjs')),
        str(root/'app/admin_web/static/db_services.js'), str(path), scenario], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout+result.stderr
