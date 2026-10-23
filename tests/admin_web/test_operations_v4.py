"""Issue324 Phase 1: closed workload projection, no new sampler/source I/O."""
import copy
import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.admin_web import operations_service as ops
from app.admin_web.operations_schema import validate_v3, validate_v4
from app.device_fingerprint_sensor.operations_metadata import sensor_workload
from app.operations_app_health import ni04_workload
from app.operations_health import NI04_UNIT
from tests.admin_web.test_db_services_routes import operations_app, logged_in
from tests.admin_web.test_operations_owner_health import OwnerReader
from tests.admin_web.test_operations_v2 import Reader, workload_service
from tests.admin_web.test_operations_service import NOW

API = '/admin/api/v4/operations/db-services'


class WorkloadReader:
    def __init__(self, reader, workload):
        self.reader, self.workload = reader, workload

    def read(self, *args, **kwargs):
        return dict(self.reader.read(*args, **kwargs), workload=copy.deepcopy(self.workload))

    def __getattr__(self, key):return getattr(self.reader, key)


def phase1_service(monkeypatch, rows=12, backlog=17):
    service, ni02, calls, tick, boot = workload_service(monkeypatch)
    sensor = WorkloadReader(Reader(), dict(spool_pending_rows=rows, spool_bytes=1048576,
        oldest_spool_age_seconds=None if rows == 0 else 42))
    owner = WorkloadReader(OwnerReader(NI04_UNIT, 'usable'), dict(feed_backlog_entries=backlog))
    service._sensor_metadata = sensor; service._sensor_health.reader = sensor
    service._owner_health_readers['network_service_recognition'] = owner
    service._owner_health['network_service_recognition'].reader = owner
    return service, sensor, owner, ni02, calls, tick, boot


@pytest.mark.parametrize('rows,backlog', [(0, 0), (1, 1), (12, 17), (2**53-1, 2**53-1)])
def test_v4_exact_closed_projection_reuses_reads_and_keeps_legacy(monkeypatch, rows, backlog):
    import sqlite3
    service, sensor, owner, ni02, calls, *_ = phase1_service(monkeypatch, rows, backlog)
    monkeypatch.setattr(sqlite3, 'connect', Mock(side_effect=AssertionError('Admin SQL forbidden')))
    try:
        old = [service.read('same', version=v) for v in (1, 2, 3)]
        model = validate_v4(service.read('same', version=4))
        assert model['workload'] == dict(network_metadata_projection=dict(pending_attribution_count=1815),
            fingerprint_sensor=sensor.workload, network_service_recognition=ni04_workload())
        assert calls == [1] and sensor.calls == owner.calls == ni02.calls == 1
        projected = dict(model, api_version=ops.API_VERSION_V3,
            workload={'network_metadata_projection': model['workload']['network_metadata_projection']})
        assert validate_v3(projected) == old[2]
        assert 'workload' not in old[0] and 'workload' not in old[1]
        assert all(len(row['application_health_evidence']) == 7 for row in model['services'])
        assert (len(model['services']), len(model['databases']), len(model['topology']['nodes']), len(model['topology']['edges'])) == (9, 17, 31, 45)
        assert len(json.dumps(model).encode()) < ops.RESPONSE_LIMIT
        for token in ('boot_id', 'start_ticks', 'epoch', '/run/', 'producer'):
            assert token not in json.dumps(model)
    finally:service.close()


@pytest.mark.parametrize('source', ['fingerprint_sensor', 'network_service_recognition'])
@pytest.mark.parametrize('fault', ['stale-cache', 'expired', 'invalid', 'old', 'before-start', 'wrong-pid', 'stale', 'missing', 'degraded-cache', 'start-changed'])
def test_v4_never_carries_numeric_across_missing_stale_or_mismatched_proof(monkeypatch, source, fault):
    service, sensor, owner, _, calls, tick, boot = phase1_service(monkeypatch)
    reader = sensor if source == 'fingerprint_sensor' else owner
    collector = service._sensor_health if source == 'fingerprint_sensor' else service._owner_health[source]
    empty = sensor_workload() if source == 'fingerprint_sensor' else ni04_workload()
    try:
        initial = service.read('initial', version=4)['workload'][source]
        assert (initial != empty) == (source == 'fingerprint_sensor')
        if fault == 'stale-cache':tick[0] = 91; service._last_attempt = 91
        elif fault == 'expired':boot[0] += 180_000_000_001
        else:
            row = next(r for r in service._cache[0]['services'] if r['id'] == source)
            report = reader.read(row, NOW)
            if fault == 'invalid':report['workload'] = {'PRIVATE': 1}
            elif fault == 'old':report.pop('workload')
            elif fault == 'before-start':report['observed_at'] = '2000-01-01T00:00:00.000Z'
            elif fault == 'wrong-pid':report['producer'] = dict(report['producer'], pid=999)
            elif fault == 'start-changed':row['started_at_utc'] = '2099-01-01T00:00:00.000Z'
            elif fault == 'degraded-cache':
                report['health'].update(state='degraded', reason='source_degraded')
                collector.collect(report, row, NOW)
                report = {'status': 'unknown'}
            else:report = {'status': 'stale' if fault == 'stale' else 'unknown'}
            service._cache[0]['_health_records'][source] = collector.collect(report, row, NOW)
        assert validate_v4(service.read('after', version=4))['workload'][source] == empty
        assert calls == [1]
    finally:service.close()


@pytest.mark.parametrize('field', ['spool_pending_rows', 'spool_bytes', 'oldest_spool_age_seconds', 'feed_backlog_entries'])
@pytest.mark.parametrize('bad', [True, -1, 2**53, 1.0, '1'])
def test_v4_rejects_invalid_integer_types(monkeypatch, field, bad):
    service, *_ = phase1_service(monkeypatch)
    try:model = service.read('fixture', version=4)
    finally:service.close()
    source = 'network_service_recognition' if field == 'feed_backlog_entries' else 'fingerprint_sensor'
    model['workload'][source][field] = bad
    with pytest.raises(ops.OperationsError):validate_v4(model)


@pytest.mark.parametrize('fault', ['extra-root', 'extra-workload', 'extra-sensor', 'extra-ni04', 'missing', 'null-object',
    'mixed-null', 'zero-age', 'unknown-size', 'wrong-evidence', 'wrong-check', 'wrong-version'])
def test_v4_reuses_entire_v3_privacy_contract(monkeypatch, fault):
    service, *_ = phase1_service(monkeypatch)
    try:model = service.read('fixture', version=4)
    finally:service.close()
    w = model['workload']; s = w['fingerprint_sensor']
    if fault == 'extra-root':model['private'] = 'PRIVATE'
    elif fault == 'extra-workload':w['private'] = {}
    elif fault == 'extra-sensor':s['private'] = 1
    elif fault == 'extra-ni04':w['network_service_recognition']['private'] = 1
    elif fault == 'missing':s.pop('spool_bytes')
    elif fault == 'null-object':w['fingerprint_sensor'] = None
    elif fault == 'mixed-null':s['spool_pending_rows'] = None
    elif fault == 'zero-age':s['spool_pending_rows'] = 0
    elif fault == 'unknown-size':s['spool_bytes'] = None
    elif fault == 'wrong-evidence':model['services'][0]['application_health_evidence']['pid'] = 123
    elif fault == 'wrong-check':model['databases'][0]['store_verification']['status'] = 'invented'
    elif fault == 'wrong-version':model['api_version'] = ops.API_VERSION_V3
    with pytest.raises(ops.OperationsError):validate_v4(model)


@pytest.mark.parametrize('method', ['get', 'head', 'post', 'put'])
def test_v4_route_auth_and_method_contract(monkeypatch, method):
    app, runtime, _ = operations_app(monkeypatch)
    runtime.operations_service.close(); service, *_ = phase1_service(monkeypatch)
    runtime.operations_service = service
    try:
        response = app.test_client().get(API, base_url='https://localhost')
        assert response.status_code == 401 and response.json['api_version'] == ops.API_VERSION_V4
        response = getattr(logged_in(app), method)(API, base_url='https://localhost')
        assert response.status_code == (200 if method in {'get', 'head'} else 405)
        if method == 'get':validate_v4(response.json)
        if method == 'head':assert response.data == b''
    finally:runtime.clear()


@pytest.mark.parametrize('fault', ['query', 'body', 'http', 'network', 'permission', 'disabled', 'pending', 'size'])
def test_v4_route_fail_closed_boundaries(monkeypatch, fault):
    app, runtime, _ = operations_app(monkeypatch, flag='false' if fault == 'disabled' else 'true',
        grants='admin.read.settings.global' if fault == 'permission' else 'admin.read.operations')
    service, *_ = phase1_service(monkeypatch)
    try:model = service.read('fixture', version=4)
    finally:service.close()
    if runtime.operations_service:runtime.operations_service.close()
    runtime.operations_service = Mock(); runtime.operations_service.read.return_value = model
    if fault == 'pending':runtime.operations_service.read.side_effect = ops.OperationsError('snapshot_pending')
    if fault == 'size':monkeypatch.setattr(ops, 'RESPONSE_LIMIT', 10)
    kwargs = dict(base_url='https://localhost'); path = API
    if fault == 'query':path += '?private=PRIVATE'
    if fault == 'body':kwargs['data'] = b'PRIVATE'
    if fault == 'http':kwargs['base_url'] = 'http://localhost'
    if fault == 'network':kwargs['environ_overrides'] = {'REMOTE_ADDR': '203.0.113.90'}
    try:
        response = logged_in(app).get(path, **kwargs)
        assert response.status_code == dict(query=400, body=400, http=403, network=403,
            permission=403, disabled=404, pending=503, size=503)[fault]
        assert response.json['api_version'] == ops.API_VERSION_V4
        assert b'PRIVATE' not in response.data
    finally:runtime.clear()


@pytest.mark.parametrize('scenario', ['valid', 'zero', 'unknown', 'stale', 'refresh-failure', 'fallback-v3', 'fallback-v2', 'fallback-v1',
    '401', '403', '500', '503', 'bad-json', 'bad-version', 'bad-count', 'bad-tuple', 'bad-check', 'extra-workload'])
def test_v4_dom_existing_cards_topology_strict_fallback_and_no_old_count(monkeypatch, tmp_path, scenario):
    service, *_ = phase1_service(monkeypatch, rows=0 if scenario == 'zero' else 12, backlog=0 if scenario == 'zero' else 17)
    try:model = service.read('fixture', version=4)
    finally:service.close()
    if scenario == 'unknown':model['workload'].update(fingerprint_sensor=sensor_workload(), network_service_recognition=ni04_workload())
    if scenario == 'stale':model['sample_status'] = 'stale'
    fixture = tmp_path/'v4.json'; fixture.write_text(json.dumps(model), encoding='utf-8')
    root = Path(__file__).parents[2]; node = shutil.which('node'); assert node
    result = subprocess.run([node, str(Path(__file__).with_name('db_services_v4_ui.cjs')),
        str(root/'app/admin_web/static/db_services.js'), str(fixture), scenario], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
