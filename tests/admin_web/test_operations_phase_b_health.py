"""Issue298 B2/B4 and complete nine-source v2 boundary; no active probes."""
import copy
from datetime import timedelta
import json
import os
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

from flask import Blueprint, Flask
import pytest

from app.admin_web import operations_service as ops
from app.admin_web.operations_schema import validate_v2
from app.admin_web.runtime import bind_core_operations_snapshot, core_operations_snapshot
from app.operations_health import OWNER_SERVICES, DEPENDENCIES, SENSOR_UNIT, NI02_UNIT, sensor_health, ni02_health
from app.auth.health import AuthorizationHealthTracker, OUTCOME_BLOCKING_FAILURE, OUTCOME_RETRYABLE_FAILURE, OUTCOME_VERIFIED_SUCCESS
from tests.admin_web.test_operations_v2 import Reader, ORIGIN
from tests.admin_web.test_operations_inventory import resolved
from tests.admin_web.test_operations_service import NOW, regular, systemd_text

SITES = ('a'*24, 'b'*24)


def core_app(capport=False):
    app = Flask(__name__); blueprint = Blueprint('synthetic_admin', __name__)
    app.register_blueprint(blueprint)
    tracker = AuthorizationHealthTracker(SITES)
    runtime = SimpleNamespace(config=SimpleNamespace(enabled=True), state='active', blueprint=blueprint,
        query_service=object(), operations_service=Mock())
    app.extensions.update(admin_web_runtime=runtime, authorization_health_tracker=tracker,
        portal_entry_handler=SimpleNamespace(_auth_worker=object(), _session_manager=object(), _executor=object()))
    if capport:app.extensions['capport_service'] = object()
    bind_core_operations_snapshot(app, dict(capport_enabled=capport))
    return app, tracker, runtime


@pytest.mark.parametrize('capport', [True, False])
def test_core_composition_no_auth_traffic_is_healthy_and_optional_workers_do_not_matter(capport):
    app, tracker, runtime = core_app(capport)
    assert core_operations_snapshot(app, NOW) == dict(health=dict(state='healthy', reason='core_composed'), observed_at=NOW)
    assert len([key for key in app.extensions if key == 'operations_core_composition']) == 1
    runtime.operations_service.set_core_snapshot_provider.assert_called_once()
    callback = runtime.operations_service.set_core_snapshot_provider.call_args.args[0]
    assert callback(NOW)['health']['state'] == 'healthy'


@pytest.mark.parametrize('fault,state', [('handler','unavailable'), ('auth','unavailable'), ('executor','unavailable'),
    ('capport','degraded'), ('admin-route','degraded'), ('admin-state','degraded'), ('intent','unknown'), ('marker','unknown')])
def test_core_required_composition_failures_without_synthetic_checks(fault, state):
    app, tracker, runtime = core_app(True)
    if fault == 'handler':app.extensions['portal_entry_handler'] = None
    elif fault == 'auth':app.extensions['portal_entry_handler']._auth_worker = None
    elif fault == 'executor':app.extensions['portal_entry_handler']._executor = None
    elif fault == 'capport':app.extensions.pop('capport_service')
    elif fault == 'admin-route':app.blueprints.clear()
    elif fault == 'admin-state':runtime.state = 'unavailable'
    elif fault == 'intent':app.extensions['operations_core_composition'] = (os.getpid(), 'invalid', True)
    elif fault == 'marker':app.extensions.pop('operations_core_composition')
    assert core_operations_snapshot(app, NOW)['health']['state'] == state


def test_enabled_admin_unavailable_with_registered_blueprint_is_not_healthy():
    app, tracker, runtime = core_app(capport=True)
    assert runtime.config.enabled is True
    assert runtime.blueprint.name in app.blueprints
    runtime.state = 'unavailable'
    runtime.query_service = None
    result = core_operations_snapshot(app, NOW)
    assert result['health']['state'] != 'healthy'
    assert result == dict(health=dict(state='degraded', reason='core_component_degraded'), observed_at=NOW)


@pytest.mark.parametrize('fault', ['query', 'runtime', 'blueprint', 'disabled'])
def test_enabled_admin_missing_required_readiness_is_degraded(fault):
    app, tracker, runtime = core_app()
    if fault == 'query':runtime.query_service = None
    elif fault == 'runtime':app.extensions.pop('admin_web_runtime')
    elif fault == 'blueprint':runtime.blueprint = None
    elif fault == 'disabled':runtime.state = 'disabled'
    assert core_operations_snapshot(app, NOW)['health'] == dict(state='degraded', reason='core_component_degraded')


@pytest.mark.parametrize('status', [None, 'initializing', 'unexpected', True])
@pytest.mark.parametrize('query_present', [True, False])
def test_enabled_admin_indeterminate_status_never_becomes_healthy(status, query_present):
    app, tracker, runtime = core_app()
    runtime.state = status
    runtime.query_service = object() if query_present else None
    assert core_operations_snapshot(app, NOW)['health'] == dict(state='unknown', reason='dependencies_unconfirmed')


@pytest.mark.parametrize('intent', [None, 'true', 1])
def test_unknown_effective_admin_intent_stays_unknown(intent):
    app, tracker, runtime = core_app()
    runtime.config.enabled = intent
    bind_core_operations_snapshot(app, dict(capport_enabled=False))
    assert core_operations_snapshot(app, NOW)['health'] == dict(state='unknown', reason='dependencies_unconfirmed')


@pytest.mark.parametrize('runtime_present', [True, False])
def test_effectively_disabled_admin_and_capport_are_not_outages(runtime_present):
    app, tracker, runtime = core_app(capport=False)
    runtime.config.enabled = False
    bind_core_operations_snapshot(app, dict(capport_enabled=False))
    runtime.state = 'disabled'
    runtime.query_service = None
    runtime.blueprint = None
    app.blueprints.clear()
    if not runtime_present:app.extensions.pop('admin_web_runtime')
    assert core_operations_snapshot(app, NOW)['health'] == dict(state='healthy', reason='core_composed')


@pytest.mark.parametrize('outcomes,age,state,reason', [
    ((OUTCOME_VERIFIED_SUCCESS, OUTCOME_VERIFIED_SUCCESS), 0, 'healthy', 'core_composed'),
    ((OUTCOME_RETRYABLE_FAILURE, None), 30, 'degraded', 'authorization_degraded'),
    ((OUTCOME_BLOCKING_FAILURE, None), 30, 'degraded', 'authorization_degraded'),
    ((OUTCOME_BLOCKING_FAILURE, OUTCOME_BLOCKING_FAILURE), 30, 'degraded', 'authorization_degraded'),
    ((OUTCOME_BLOCKING_FAILURE, OUTCOME_BLOCKING_FAILURE), 181, 'healthy', 'core_composed'),
    ((OUTCOME_RETRYABLE_FAILURE, None), -1, 'unknown', 'dependencies_unconfirmed'),
])
def test_core_existing_auth_outcomes_are_recent_bounded_and_not_e2e_claim(outcomes, age, state, reason):
    app, tracker, runtime = core_app()
    for site, outcome in zip(SITES, outcomes):
        if outcome:tracker.record(site, outcome, NOW-timedelta(seconds=age))
    result = core_operations_snapshot(app, NOW)
    assert result['health'] == dict(state=state, reason=reason)
    assert result['observed_at'] == (NOW-timedelta(seconds=age) if state in {'degraded','unavailable'} else NOW)
    if age == 30:
        for site in SITES:tracker.record(site, OUTCOME_VERIFIED_SUCCESS, NOW)
        assert core_operations_snapshot(app, NOW)['health']['state'] == 'healthy'


def test_core_provider_failure_or_fork_is_unknown(monkeypatch):
    app, tracker, runtime = core_app()
    tracker.snapshots = Mock(side_effect=RuntimeError('PRIVATE'))
    assert core_operations_snapshot(app, NOW)['health'] == dict(state='unknown', reason='dependencies_unconfirmed')
    from app.admin_web import runtime as module
    pid = os.getpid(); monkeypatch.setattr(module.os, 'getpid', lambda: pid+1)
    assert core_operations_snapshot(app, NOW)['health']['state'] == 'unknown'


class FileReader(Reader):
    def __init__(self, unit, health):
        super().__init__(); self.unit, self.health, self.status = unit, health, 'fresh'
        self.channel = lambda: SimpleNamespace(uid=1000)
    def read(self, *args, **kwargs):
        self.calls += 1
        if self.status != 'fresh':return dict(status=self.status)
        return dict(status='fresh', health=self.health, producer=self.producer, observed_at=ops.timestamp(NOW),
            age=0, expires_boottime_ns=ORIGIN+180_000_000_000)


def complete_service(monkeypatch):
    boot = [ORIGIN]; calls = []; monkeypatch.setattr(ops, 'boot_ns', lambda: boot[0])
    sensor = Reader()
    ni02 = FileReader(NI02_UNIT, ni02_health('usable', dict.fromkeys(DEPENDENCIES[NI02_UNIT],True), 0))
    owners = {key: FileReader(unit, dict(state='healthy', reason='source_ready')) for key, unit in OWNER_SERVICES.items()}
    app, tracker, _ = core_app()
    def acquire(cancel):
        calls.append(1); blocks = systemd_text().split('\n\n')
        blocks[0] = blocks[0].replace('MainPID=123', 'MainPID='+str(os.getpid()))
        return '\n\n'.join(blocks)
    value = ops.AdminOperationsReadService(resolved(), acquire=acquire, lstat=regular, monotonic=lambda: 0, now=lambda: NOW,
        sensor_metadata=sensor, ni02_health=ni02, owner_health_readers=owners,
        core_snapshot=lambda now: core_operations_snapshot(app, now))
    return value, sensor, ni02, owners, boot, calls, tracker


def row(model, key):return next(item for item in model['services'] if item['id'] == key)


def test_all_nine_sources_valid_v2_cached_and_v1_still_unchanged(monkeypatch):
    service, sensor, ni02, owners, boot, calls, tracker = complete_service(monkeypatch)
    try:
        model = validate_v2(service.read('all-nine', version=2))
        assert model['summary']['application_health']['healthy'] == 9
        assert row(model,'portal_core')['application_health_evidence']['source'] == 'portal_in_process'
        assert row(model,'fingerprint_suricata')['application_health_evidence']['source'] == 'observed_via_sensor'
        assert len(model['services']) == 9 and len(model['databases']) == 17
        assert len(model['topology']['nodes']) == 31 and len(model['topology']['edges']) == 45
        assert len(json.dumps(model).encode()) < ops.RESPONSE_LIMIT
        assert all(item['application_health'] == 'unknown' for item in service.read('v1')['services'])
        for _ in range(3):service.read('cached', version=2)
        assert calls == [1] and sensor.calls == ni02.calls == 1 and all(reader.calls == 1 for reader in owners.values())
        boot[0] += 180_000_000_001
        assert validate_v2(service.read('expired',version=2))['summary']['application_health']['healthy'] == 0
    finally:service.close()


@pytest.mark.parametrize('dependency', [True, False])
@pytest.mark.parametrize('fault', ['none','missing','stale','pid','invalid','stopped','sensor-stopped','old-incarnation','expiry'])
def test_suricata_uses_one_fresh_validated_sensor_boolean(monkeypatch, dependency, fault):
    service, sensor_reader, *_ = complete_service(monkeypatch)
    sensor = dict(operational_state='running', main_pid=123)
    suricata = dict(operational_state='running', started_at_utc=ops.timestamp(NOW-timedelta(seconds=60)))
    deps = dict.fromkeys(DEPENDENCIES[SENSOR_UNIT], True); deps['suricata'] = dependency
    report = sensor_reader.read(sensor, NOW); report['health'] = sensor_health('ready', deps)
    if fault == 'missing':report.pop('health')
    elif fault == 'stale':report['status'] = 'stale'
    elif fault == 'pid':report['producer']['pid'] = 124
    elif fault == 'invalid':report['health']['dependencies']['suricata'] = 'true'
    elif fault == 'stopped':suricata['operational_state'] = 'stopped'
    elif fault == 'sensor-stopped':sensor['operational_state'] = 'stopped'
    elif fault == 'old-incarnation':suricata['started_at_utc'] = ops.timestamp(NOW+timedelta(seconds=1))
    elif fault == 'expiry':report['expires_boottime_ns'] = ORIGIN-1
    before = copy.deepcopy(report)
    try:
        result = service._suricata_health(report, sensor, suricata, NOW)['evidence']
        assert result['state'] == ('healthy' if dependency else 'unavailable') if fault == 'none' else result['state'] == ('stale' if fault == 'stale' else 'unknown')
        assert sensor_reader.calls == 1 and report == before
        if fault == 'none':assert result['source'] == 'observed_via_sensor'
    finally:service.close()


def test_core_binding_and_auth_fact_age_not_extended(monkeypatch):
    service, _, _, _, boot, _, tracker = complete_service(monkeypatch)
    tracker.record(SITES[0], OUTCOME_RETRYABLE_FAILURE, NOW-timedelta(seconds=30))
    try:
        core = row(validate_v2(service.read('aged',version=2)), 'portal_core')['application_health_evidence']
        assert core['state'] == 'degraded' and core['age'] == 30 and core['observed_at'] == ops.timestamp(NOW-timedelta(seconds=30))
        boot[0] += 150_000_000_001
        assert row(service.read('expiry',version=2), 'portal_core')['application_health'] == 'stale'
        assert service._core_health(dict(operational_state='running',main_pid=os.getpid()+1), NOW)['evidence']['state'] == 'unknown'
    finally:service.close()


@pytest.mark.parametrize('key', ['portal_core','fingerprint_suricata','fingerprint_classification','traffic_projection'])
@pytest.mark.parametrize('fault', ['source','reason','pair','ttl','extra'])
def test_phase_b_server_validation_is_closed(monkeypatch, key, fault):
    service, *_ = complete_service(monkeypatch)
    try:model = service.read('negative',version=2)
    finally:service.close()
    target = row(model,key); evidence = target['application_health_evidence']
    if fault == 'source':evidence['source'] = 'sensor_native.v2'
    elif fault == 'reason':evidence['reason'] = '/PRIVATE'
    elif fault == 'pair':target['application_health'] = evidence['state'] = 'unavailable'
    elif fault == 'ttl':evidence['ttl'] = 181
    elif fault == 'extra':evidence['raw_path'] = '/PRIVATE'
    with pytest.raises(ops.OperationsError):validate_v2(model)


@pytest.mark.parametrize('bad', [False, True])
def test_v2_authenticated_route_accepts_complete_sources_or_safe_503(monkeypatch, bad):
    from tests.admin_web.test_db_services_routes import operations_app, logged_in
    app, runtime, _ = operations_app(monkeypatch); runtime.operations_service.close()
    service, *_ = complete_service(monkeypatch); runtime.operations_service = service
    if bad:
        model = service.read('bad',version=2); row(model,'portal_core')['application_health_evidence']['source'] = 'observed_via_sensor'
        service.read = Mock(return_value=model)
    try:
        response = logged_in(app).get('/admin/api/v2/operations/db-services',base_url='https://localhost')
        assert response.status_code == (503 if bad else 200)
    finally:runtime.clear()


@pytest.mark.parametrize('scenario', ['b-valid','b-rebuilding','b-bad-source','b-bad-reason','b-cross-proxy'])
def test_phase_b_javascript_closed_sources_and_visible_provenance(monkeypatch, tmp_path, scenario):
    service, *_ = complete_service(monkeypatch)
    try:model = service.read('js',version=2)
    finally:service.close()
    if scenario == 'b-rebuilding':
        target = row(model,'traffic_projection'); target['application_health'] = target['application_health_evidence']['state'] = 'degraded'
        target['application_health_evidence']['reason'] = 'projection_rebuilding'
    fixture = tmp_path/'fixture.json'; fixture.write_text(json.dumps(model), encoding='utf-8')
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([shutil.which('node'), str(Path(__file__).with_name('db_services_v2_ui.cjs')),
        str(root/'app/admin_web/static/db_services.js'), str(fixture), scenario],capture_output=True,text=True)
    assert result.returncode == 0, result.stdout+result.stderr


def test_core_sampler_and_cached_reads_do_not_add_sql_http_or_provider_calls(monkeypatch):
    import sqlite3
    import requests
    service, *_ = complete_service(monkeypatch)
    service._core_snapshot = Mock(wraps=service._core_snapshot)
    sql = Mock(side_effect=AssertionError('no SQL'))
    http = Mock(side_effect=AssertionError('no HTTP'))
    monkeypatch.setattr(sqlite3, 'connect', sql)
    monkeypatch.setattr(requests.sessions.Session, 'request', http)
    try:
        for _ in range(4):assert row(service.read('memory',version=2),'portal_core')['application_health'] == 'healthy'
        assert service._core_snapshot.call_count == 1
        sql.assert_not_called(); http.assert_not_called()
    finally:service.close()
