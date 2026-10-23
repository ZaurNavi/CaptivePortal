"""Issue298 Phase A: memory-only truth and bounded informational report transport."""
import copy
import json
import os
import threading
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app import operations_app_health as h
from app.operations_health import EVIDENCE_UNIT, NI01_UNIT, NI04_UNIT, OWNER_UNITS, owner_health, validate_owner
from app.network_metadata_projection.operations_health import Channel
from tests.device_fingerprint_sensor.test_operations_metadata import NOW, report as sensor_report
from tests.network_service_recognition.test_materialization_worker import lane

POSIX = pytest.mark.skipif(os.name != 'posix', reason='Linux/POSIX owner report openat contract')


def report(unit=NI04_UNIT):
    original = sensor_report()
    return {key: copy.deepcopy(original[key]) for key in
            ('producer', 'epoch', 'sequence', 'sample_time_utc', 'sample_boottime_ns')} | dict(
        schema_version=h.SCHEMA, producer_unit=unit, application_health=owner_health(unit, 'usable'))


def raw(value):return json.dumps(value, separators=(',', ':')).encode()


@pytest.mark.parametrize('unit,native,state,reason', [
    (EVIDENCE_UNIT, 'ready', 'healthy', 'source_ready'),
    (EVIDENCE_UNIT, 'degraded', 'degraded', 'source_degraded'),
    (EVIDENCE_UNIT, 'unavailable', 'unavailable', 'source_unavailable'),
    (EVIDENCE_UNIT, 'initializing', 'unknown', 'source_initializing'),
    (EVIDENCE_UNIT, 'stopping', 'unknown', 'source_stopping'),
    (EVIDENCE_UNIT, None, 'unknown', 'dependencies_unconfirmed'),
    (NI04_UNIT, 'usable', 'healthy', 'source_ready'),
    (NI04_UNIT, 'backfilling', 'healthy', 'backfilling_incomplete_coverage'),
    (NI04_UNIT, 'lagging', 'degraded', 'source_lagging'),
    (NI04_UNIT, 'source_unavailable', 'unavailable', 'source_unavailable'),
    (NI04_UNIT, 'recognition_unavailable', 'unavailable', 'source_unavailable'),
    (NI04_UNIT, 'capacity_halted', 'unavailable', 'capacity_limited'),
    (NI04_UNIT, 'blocked_conflict', 'unavailable', 'blocked_conflict'),
    (NI04_UNIT, 'initializing', 'unknown', 'source_initializing'),
    (NI04_UNIT, 'stopping', 'unknown', 'source_stopping'),
    (NI04_UNIT, 'unknown', 'unknown', 'dependencies_unconfirmed'),
])
def test_closed_native_owner_mapping(unit, native, state, reason):
    assert owner_health(unit, native) == dict(state=state, reason=reason)


@pytest.mark.parametrize('capture,output,ingest,reasons,state,reason', [
    ('usable', 'usable', 'usable', set(), 'healthy', 'source_ready'),
    ('unknown', 'usable', 'usable', set(), 'unknown', 'dependencies_unconfirmed'),
    ('unknown', 'partial', 'usable', set(), 'degraded', 'source_degraded'),
    ('stale', 'usable', 'unknown', set(), 'degraded', 'source_stale'),
    ('unavailable', 'partial', 'unknown', set(), 'unavailable', 'source_unavailable'),
    ('usable', 'usable', 'unavailable', set(), 'unavailable', 'source_unavailable'),
    ('usable', 'usable', 'usable', {'source_absent'}, 'unknown', 'dependencies_unconfirmed'),
    ('usable', 'usable', 'usable', None, 'unknown', 'dependencies_unconfirmed'),
])
def test_ni01_precedence_uses_only_native_memory(capture, output, ingest, reasons, state, reason):
    native = SimpleNamespace(capture=capture, output=output, ingest=ingest, local_reasons=reasons,
        ensure=Mock(side_effect=AssertionError('no SQL')), evaluate=Mock(side_effect=AssertionError('no probe')))
    assert owner_health(NI01_UNIT, native) == dict(state=state, reason=reason)
    assert native.ensure.mock_calls == native.evaluate.mock_calls == []


def test_ni01_known_blocked_condition_has_highest_precedence():
    from app.network_metadata.models import CONFLICT_CATEGORIES
    for reason in CONFLICT_CATEGORIES:
        native = SimpleNamespace(capture='unknown', output='partial', ingest='usable', local_reasons={reason})
        assert owner_health(NI01_UNIT, native) == dict(state='unavailable', reason='source_unavailable')


@pytest.mark.parametrize('unit', sorted(OWNER_UNITS))
@pytest.mark.parametrize('fault', ['extra', 'state', 'reason', 'mismatch', 'stale', 'dependency', 'wrong-owner-reason'])
def test_owner_health_is_closed_and_never_accepts_arbitrary_details(unit, fault):
    value = dict(state='healthy', reason='source_ready')
    if fault == 'extra':value['path'] = '/PRIVATE'
    elif fault == 'state':value['state'] = 'ready'
    elif fault == 'reason':value['reason'] = '/PRIVATE'
    elif fault == 'mismatch':value['state'] = 'unknown'
    elif fault == 'stale':value.update(state='stale', reason='report_stale')
    elif fault == 'dependency':value['dependencies'] = {}
    elif fault == 'wrong-owner-reason':value.update(state='healthy' if unit != NI04_UNIT else 'degraded',
        reason='backfilling_incomplete_coverage' if unit != NI04_UNIT else 'source_stale')
    with pytest.raises(ValueError):validate_owner(value, unit)


@pytest.mark.parametrize('fault', ['schema', 'unit', 'extra', 'producer', 'pid', 'start', 'boot', 'epoch',
    'sequence', 'sequence-large', 'time', 'mono', 'mono-large', 'health', 'duplicate', 'json', 'nan', 'oversize'])
def test_wire_rejects_unapproved_fields_and_values(fault):
    value = report()
    if fault == 'schema':value['schema_version'] = 'startup-checks'
    elif fault == 'unit':value['producer_unit'] = 'portal.service'
    elif fault == 'extra':value['payload'] = '/PRIVATE'
    elif fault == 'producer':value['producer']['uid'] = 1000
    elif fault == 'pid':value['producer']['pid'] = True
    elif fault == 'start':value['producer']['start_ticks'] = 0
    elif fault in {'boot', 'epoch'}:
        if fault == 'boot':value['producer']['boot_id'] = 'x'
        else:value['epoch'] = 'x'
    elif fault == 'sequence':value['sequence'] = False
    elif fault == 'sequence-large':value['sequence'] = 2**53
    elif fault == 'time':value['sample_time_utc'] = NOW.isoformat()
    elif fault == 'mono':value['sample_boottime_ns'] = -1
    elif fault == 'mono-large':value['sample_boottime_ns'] = 2**63
    elif fault == 'health':value['application_health']['reason'] = '/PRIVATE'
    data = raw(value)
    if fault == 'duplicate':data = data[:-1] + b',"sequence":1}'
    elif fault == 'json':data = b'{'
    elif fault == 'nan':data = data[:-1] + b',"x":NaN}'
    elif fault == 'oversize':data = b' ' * 4097
    with pytest.raises(ValueError):h.decode(data, NI04_UNIT)


def test_wire_roundtrip_and_off_flag_is_startup_only_without_channel_calls(monkeypatch):
    assert h.decode(raw(report()), NI04_UNIT) == report()
    assert set(report()) == {'schema_version', 'producer_unit', 'producer', 'epoch', 'sequence',
        'sample_time_utc', 'sample_boottime_ns', 'application_health'}
    monkeypatch.setenv('WEB_ADMIN_DB_SERVICES_ENABLED', 'false')
    channel = Mock(side_effect=AssertionError('no I/O'))
    publisher = h.HealthPublisher(NI04_UNIT, channel=channel)
    monkeypatch.setenv('WEB_ADMIN_DB_SERVICES_ENABLED', 'true')
    assert not publisher.publish(owner_health(NI04_UNIT, 'usable'))
    channel.assert_not_called()


class TestChannel:
    """Disposable directory; actual production file checks, no system /run writes."""
    __test__ = False
    def __init__(self, directory):self.directory, self.uid = directory, os.geteuid()
    def open(self):return os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    def validate_file(self, info):Channel(self.uid).validate_file(info)


def write_report(path, value):
    path.write_bytes(raw(value)); path.chmod(0o600)


def reader_for(tmp_path, value=None, identity=None, boot=None):
    value = value or report(); path = tmp_path / h.REPORT; write_report(path, value)
    identity = identity or (lambda pid, uid: dict(value['producer'], pid=pid))
    reader = h.HealthReader(NI04_UNIT, channel=lambda unit: TestChannel(tmp_path), identity=identity,
        boottime=boot or (lambda: 100_000_000_000))
    service = dict(operational_state='running', main_pid=123, started_at_utc=h.m.stamp(NOW-timedelta(seconds=30)))
    return path, reader, service


@POSIX
@pytest.mark.parametrize('fault', ['none', 'mode', 'symlink', 'hardlink', 'directory', 'owner', 'pid', 'start',
    'boot', 'not-running', 'future', 'utc-boot-drift', 'before-start', 'stale', 'deadline', 'cancel', 'oversize'])
def test_real_file_reader_fails_closed(tmp_path, fault):
    value = report()
    if fault == 'pid':value['producer']['pid'] = 124
    elif fault == 'start':value['producer']['start_ticks'] += 1
    elif fault == 'boot':value['producer']['boot_id'] = '33333333-3333-4333-8333-333333333333'
    elif fault == 'future':value['sample_time_utc'] = h.m.stamp(NOW+timedelta(seconds=1))
    elif fault in {'stale', 'utc-boot-drift'}:value['sample_time_utc'] = h.m.stamp(NOW-timedelta(seconds=181))
    path, reader, service = reader_for(tmp_path, value, identity=lambda pid, uid: report()['producer'],
        boot=(lambda: 281_000_000_000) if fault == 'stale' else None)
    cancel = threading.Event()
    if fault == 'mode':path.chmod(0o644)
    elif fault == 'symlink':path.rename(tmp_path/'target'); path.symlink_to('target')
    elif fault == 'hardlink':os.link(path, tmp_path/'link')
    elif fault == 'directory':path.unlink(); path.mkdir()
    elif fault == 'owner':reader.channel = lambda: SimpleNamespace(open=lambda: TestChannel(tmp_path).open(),
        validate_file=lambda info: Channel(os.geteuid()+1).validate_file(info), uid=os.geteuid()+1)
    elif fault == 'not-running':service['operational_state'] = 'stopped'
    elif fault == 'stale':service['started_at_utc'] = h.m.stamp(NOW-timedelta(seconds=300))
    elif fault == 'before-start':service['started_at_utc'] = h.m.stamp(NOW+timedelta(seconds=1))
    elif fault == 'cancel':cancel.set()
    elif fault == 'oversize':path.write_bytes(b' ' * 4097)
    result = reader.read(service, NOW, deadline=0 if fault == 'deadline' else 1,
        monotonic=lambda: 0, cancel=cancel)
    assert result['status'] == ('fresh' if fault == 'none' else 'stale' if fault == 'stale' else 'unknown')
    assert ('health' in result) == (fault == 'none')
    assert '/PRIVATE' not in json.dumps(result)


@POSIX
@pytest.mark.parametrize('fault', ['lower', 'mutated-same', 'epoch', 'reversed-time', 'same', 'next', 'restart'])
def test_sequence_replay_and_process_incarnation(tmp_path, fault):
    path, reader, service = reader_for(tmp_path)
    read = lambda: reader.read(service, NOW, deadline=1, monotonic=lambda: 0)
    assert read()['status'] == 'fresh'
    value = report()
    if fault == 'lower':reader.last = (*reader.last[:2], 2, *reader.last[3:])
    elif fault == 'mutated-same':value['application_health'] = owner_health(NI04_UNIT, 'lagging')
    elif fault == 'epoch':value['epoch'] = '33333333-3333-4333-8333-333333333333'
    elif fault == 'reversed-time':value['sequence'] = 2; value['sample_boottime_ns'] -= 1
    elif fault == 'next':value['sequence'] = 2
    elif fault == 'restart':
        service['main_pid'] = 124; value['producer']['pid'] = 124
        value['epoch'] = '33333333-3333-4333-8333-333333333333'
    write_report(path, value)
    assert read()['status'] == ('fresh' if fault in {'same', 'next', 'restart'} else 'unknown')


@POSIX
def test_atomic_replacement_during_read_is_rejected_and_descriptors_closed(tmp_path, monkeypatch):
    path, reader, service = reader_for(tmp_path)
    original = h.os.read
    def racing(fd, count):
        data = original(fd, count)
        replacement = tmp_path/'next'; write_report(replacement, report()); replacement.replace(path)
        return data
    before = len(os.listdir('/proc/self/fd'))
    monkeypatch.setattr(h.os, 'read', racing)
    assert reader.read(service, NOW, deadline=1, monotonic=lambda: 0)['status'] == 'unknown'
    assert len(os.listdir('/proc/self/fd')) == before


@POSIX
def test_atomic_publisher_cadence_sequence_cleanup_and_reader_roundtrip(tmp_path, monkeypatch):
    tick = [0.0]
    publisher = h.HealthPublisher(NI04_UNIT, enabled=True, channel=lambda unit: TestChannel(tmp_path),
        monotonic=lambda: tick[0], now=lambda: NOW, boottime=lambda: 100_000_000_000,
        identity=lambda pid, uid: dict(report()['producer'], pid=pid))
    healthy = owner_health(NI04_UNIT, 'usable'); degraded = owner_health(NI04_UNIT, 'lagging')
    assert publisher.publish(healthy) and publisher.sequence == 1
    old = (tmp_path/h.REPORT).read_bytes()
    for instant in (0, 1, 59.9):
        tick[0] = instant; assert not publisher.publish(healthy)
    tick[0] = 60; assert publisher.publish(healthy) and publisher.sequence == 2
    tick[0] = 60.5; assert not publisher.publish(degraded)
    tick[0] = 61; assert publisher.publish(degraded) and publisher.sequence == 3
    assert h.decode(old, NI04_UNIT)['sequence'] == 1
    assert [p.name for p in tmp_path.iterdir()] == [h.REPORT]
    monkeypatch.setattr(h.os, 'replace', Mock(side_effect=OSError('PRIVATE')))
    tick[0] = 121; assert not publisher.publish(healthy)
    assert publisher.sequence == 3 and [p.name for p in tmp_path.iterdir()] == [h.REPORT]
    assert h.decode((tmp_path/h.REPORT).read_bytes(), NI04_UNIT)['application_health'] == degraded


@POSIX
@pytest.mark.parametrize('fault', ['short-write', 'unsafe-existing-mode', 'existing-link', 'timeout', 'identity-error'])
def test_publisher_failure_keeps_old_report_and_successful_sequence(tmp_path, monkeypatch, fault):
    value = report(); path = tmp_path/h.REPORT; write_report(path, value); original = path.read_bytes()
    tick = [0]
    publisher = _real_publisher(NI04_UNIT, tmp_path)
    if fault == 'short-write':monkeypatch.setattr(h.os, 'write', lambda fd, raw: len(raw)-1)
    elif fault == 'unsafe-existing-mode':path.chmod(0o644)
    elif fault == 'existing-link':path.rename(tmp_path/'target'); path.symlink_to('target')
    elif fault == 'timeout':
        def slow_identity(pid, uid):tick[0] = 1; return dict(value['producer'], pid=pid)
        publisher.monotonic = lambda: tick[0]; publisher.identity = slow_identity
    elif fault == 'identity-error':publisher.identity = Mock(side_effect=OSError('PRIVATE'))
    assert not publisher.publish(owner_health(NI04_UNIT, 'usable'))
    assert publisher.sequence == 0 and path.read_bytes() == original
    assert not any(p.name.startswith('.app-health-') for p in tmp_path.iterdir())


@POSIX
def test_publisher_no_retry_on_missing_channel_and_no_overlap(tmp_path):
    tick = [0.0]; channel = Mock(side_effect=PermissionError('PRIVATE'))
    publisher = h.HealthPublisher(EVIDENCE_UNIT, enabled=True, channel=channel, monotonic=lambda: tick[0])
    health = owner_health(EVIDENCE_UNIT, 'ready')
    for instant in (0, 1, 59, 60):
        tick[0] = instant; assert not publisher.publish(health)
    assert channel.call_count == 2 and publisher.sequence == 0
    with publisher.lock:assert not publisher.publish(health)
    assert channel.call_count == 2


def test_owner_hooks_publish_from_memory_without_repository_calls(tmp_path):
    from app.device_fingerprint.service import DeviceFingerprintRuntime
    from app.network_metadata.service import NetworkMetadataService
    from app.network_service_recognition.worker import ServiceMaterializationWorker
    capture = Mock()
    evidence = SimpleNamespace(condition=threading.Condition(), state='ready', _app_health=capture,
        repository=Mock(side_effect=AssertionError('no DB')))
    DeviceFingerprintRuntime._publish_app_health(evidence)
    capture.publish.assert_called_once_with(owner_health(EVIDENCE_UNIT, 'ready'), force=False)
    capture.reset_mock()
    ni01 = SimpleNamespace(health=SimpleNamespace(capture='usable', output='usable', ingest='usable', local_reasons=set()),
        _app_health=capture, repository=Mock(side_effect=AssertionError('no DB')))
    NetworkMetadataService._publish_app_health(ni01)
    capture.publish.assert_called_once_with(dict(state='healthy', reason='source_ready'), force=False)
    capture.reset_mock()
    repo = Mock(); repo.live_state = 'backfilling'
    ni04 = SimpleNamespace(repository=repo, _app_health=capture)
    ServiceMaterializationWorker._publish_app_health(ni04)
    capture.publish.assert_called_once_with(owner_health(NI04_UNIT, 'backfilling'), force=False)
    assert repo.mock_calls == []
    assert evidence.repository.mock_calls == ni01.repository.mock_calls == []


def test_owner_hook_write_failure_is_fail_open():
    from app.device_fingerprint.service import DeviceFingerprintRuntime
    from app.network_metadata.service import NetworkMetadataService
    from app.network_service_recognition.worker import ServiceMaterializationWorker
    publisher = SimpleNamespace(publish=Mock(side_effect=OSError('PRIVATE')))
    DeviceFingerprintRuntime._publish_app_health(SimpleNamespace(condition=threading.Condition(), state='ready', _app_health=publisher))
    NetworkMetadataService._publish_app_health(SimpleNamespace(health=None, _app_health=publisher))
    ServiceMaterializationWorker._publish_app_health(SimpleNamespace(repository=SimpleNamespace(live_state='usable'), _app_health=publisher))
    assert publisher.publish.call_count == 3


def _real_publisher(unit, directory):
    return h.HealthPublisher(unit, enabled=True, channel=lambda requested: TestChannel(directory),
        monotonic=lambda: 0, now=lambda: NOW, boottime=lambda: 100_000_000_000,
        identity=lambda pid, uid: dict(report()['producer'], pid=pid))


@POSIX
def test_evidence_real_report_emits_no_sql_and_never_calls_health_payload(tmp_path, monkeypatch):
    from tests.device_fingerprint.test_service import runtime
    value = runtime(tmp_path); sql = []
    value._app_health = _real_publisher(EVIDENCE_UNIT, tmp_path)
    monkeypatch.setattr(value, 'health_payload', Mock(side_effect=AssertionError('no diagnostic path')))
    value.repository.connection.set_trace_callback(sql.append)
    try:
        value._publish_app_health()
        assert sql == [] and value.state == 'ready'
        assert h.decode((tmp_path/h.REPORT).read_bytes(), EVIDENCE_UNIT)['application_health']['state'] == 'healthy'
        value.health_payload.assert_not_called()
    finally:value.repository.close()


@POSIX
def test_ni01_real_report_emits_no_sql_or_extra_native_evaluation(tmp_path, monkeypatch):
    from tests.network_metadata import store
    from tests.network_metadata.test_service import service_for
    with store(tmp_path) as state:
        value = service_for(state); value.startup()
        try:
            value.poll_once(); sql = []
            value._app_health = _real_publisher(NI01_UNIT, tmp_path)
            state.repo.connection.set_trace_callback(sql.append)
            monkeypatch.setattr(value.health, 'ensure', Mock(side_effect=AssertionError('no persistence')))
            value._publish_app_health()
            assert sql == []
            assert h.decode((tmp_path/h.REPORT).read_bytes(), NI01_UNIT)['application_health']['state'] in {'healthy', 'unknown'}
            value.health.ensure.assert_not_called()
        finally:value.close()


@POSIX
def test_ni04_real_report_has_no_runtime_transaction_or_other_sql(lane, tmp_path, monkeypatch):
    lane.worker.cycle(); sql = []
    lane.worker._app_health = _real_publisher(NI04_UNIT, tmp_path)
    lane.repo.connection.set_trace_callback(sql.append)
    monkeypatch.setattr(lane.repo, 'runtime', Mock(side_effect=AssertionError('no extra runtime write')))
    lane.worker._publish_app_health()
    assert sql == []
    assert h.decode((tmp_path/h.REPORT).read_bytes(), NI04_UNIT)['application_health']['state'] == 'healthy'
    lane.repo.runtime.assert_not_called()
