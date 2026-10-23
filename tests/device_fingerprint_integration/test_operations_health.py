"""Issue298 B1: reuse completed worker outcomes, never add a diagnostic."""
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app import operations_app_health as reports
from app.operations_health import CLASSIFICATION_UNIT, owner_health
from .test_worker_health import idle_worker, drive, OWNED_IDLE, LOCK_MISSED, events


@pytest.mark.parametrize('outcomes,expected', [
    ([OWNED_IDLE], ['healthy']), ([LOCK_MISSED], ['degraded']),
    ([RuntimeError('PRIVATE')], ['unavailable']),
    ([LOCK_MISSED, OWNED_IDLE], ['degraded', 'healthy']),
    ([RuntimeError('PRIVATE'), OWNED_IDLE], ['unavailable', 'healthy']),
])
def test_report_uses_same_completed_native_outcome(tmp_path, monkeypatch, events, outcomes, expected):
    worker = idle_worker(tmp_path); published = []
    worker._app_health = SimpleNamespace(publish=lambda health, **kwargs: published.append(dict(health)))
    drive(worker, list(range(len(outcomes))), monkeypatch, outcomes)
    assert [item['state'] for item in published] == expected+['unknown']
    assert published[-1]['reason'] == 'source_stopping'
    assert all('PRIVATE' not in str(item) for item in published)


def test_idle_reports_keep_native_60s_cadence_and_never_probe(tmp_path, monkeypatch, events):
    worker = idle_worker(tmp_path); publish = Mock()
    worker._app_health = SimpleNamespace(publish=publish)
    drive(worker, list(range(121)), monkeypatch)
    assert [call.args[0] for call in publish.call_args_list] == [owner_health(CLASSIFICATION_UNIT, 'ready')]*3 + [owner_health(CLASSIFICATION_UNIT, 'stopping')]
    assert worker.repository.claim.call_count == worker.repository.identity_due.call_count == 121


def test_report_failure_cannot_change_worker_result_or_native_events(tmp_path, monkeypatch, events):
    worker = idle_worker(tmp_path)
    worker._app_health = SimpleNamespace(publish=Mock(side_effect=OSError('PRIVATE')))
    drive(worker, [0, 60], monkeypatch)
    assert [event['reason_code'] for event in events] == ['ready', 'ready']
    assert owner_health(CLASSIFICATION_UNIT, 'lease_lost') == dict(state='unknown', reason='dependencies_unconfirmed')


def test_classification_channel_is_exact_and_does_not_provision(monkeypatch):
    monkeypatch.setitem(sys.modules, 'pwd', SimpleNamespace(getpwnam=lambda name: SimpleNamespace(pw_uid=1000)))
    channel = reports.configured_channel(CLASSIFICATION_UNIT)
    assert channel.uid == 1000 and channel.directory == '/run/captiveportal-operations/classification'
    assert 'classification' not in reports.startup_channel.__globals__['UNITS'].values()


def test_missing_provisioning_is_fail_open_and_never_becomes_success():
    calls = []
    def missing(unit):calls.append(unit); raise FileNotFoundError('PRIVATE')
    publisher = reports.HealthPublisher(CLASSIFICATION_UNIT, enabled=True, channel=missing, monotonic=lambda: 0)
    assert not publisher.publish(owner_health(CLASSIFICATION_UNIT, 'ready'))
    assert publisher.sequence == 0 and calls == [CLASSIFICATION_UNIT]
