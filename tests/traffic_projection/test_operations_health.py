"""Issue298 B3: bounded current-owner cache, no second observation."""
from types import SimpleNamespace

import pytest

from app.traffic_projection.health_observer import TrafficProjectionHealthObserver
from .test_health_observer import Service, Root, Telemetry, _observation, NoThread


def observer_for(statuses):
    tick = [0.0]; output = []
    services = tuple(Service('v'+str(i), ('site-'+str(i),), observation=_observation(state))
                     for i, state in enumerate(statuses))
    root = Root(services)
    value = TrafficProjectionHealthObserver(root, telemetry=Telemetry(), monotonic=lambda: tick[0])
    value._app_health = SimpleNamespace(enabled=True, publish=lambda health, **kw: output.append(dict(health)))
    return value, root, tick, output


@pytest.mark.parametrize('statuses,state,reason', [
    (('healthy', 'healthy'), 'healthy', 'source_ready'),
    (('healthy', 'unknown'), 'unknown', 'dependencies_unconfirmed'),
    (('healthy', 'stale'), 'degraded', 'projection_stale'),
    (('healthy', 'catching_up'), 'degraded', 'projection_catching_up'),
    (('rebuilding', 'unknown'), 'degraded', 'projection_rebuilding'),
    (('unavailable', 'unknown'), 'degraded', 'source_degraded'),
    (('unavailable', 'diverged'), 'unavailable', 'source_unavailable'),
    (('unknown', 'unknown'), 'unknown', 'dependencies_unconfirmed'),
    ((), 'unknown', 'dependencies_unconfirmed'),
])
def test_current_sites_aggregate_with_unknown_denominator(statuses, state, reason):
    observer, root, tick, output = observer_for(statuses)
    observer._observe_once()
    assert output[-1] == dict(state=state, reason=reason)
    assert all(len(service.calls) == 1 for service in root.services)
    calls = [list(service.calls) for service in root.services]
    observer._publish_app_health_locked()
    assert calls == [service.calls for service in root.services], 'aggregate must never observe again'


def test_freshness_missing_and_known_partial_failure(monkeypatch):
    observer, root, tick, output = observer_for(('healthy', 'healthy'))
    observer._observe_once(); assert output[-1]['state'] == 'healthy'
    key = next(iter(observer.known_owned_keys)); observer._app_site_states.pop(key)
    observer._publish_app_health_locked(); assert output[-1]['state'] == 'unknown'
    observer._app_site_states[key] = ('unavailable', 0)
    observer._publish_app_health_locked(); assert output[-1]['state'] == 'degraded'
    tick[0] = 55.001
    observer._publish_app_health_locked(); assert output[-1]['state'] == 'unknown'
    assert all(len(service.calls) == 1 for service in root.services)
    observer._observe_once(); assert output[-1]['state'] == 'healthy'


def test_targets_in_denominator_and_retired_versions_are_removed():
    observer, root, tick, output = observer_for(('healthy', 'rebuilding'))
    observer._observe_once(); assert output[-1]['reason'] == 'projection_rebuilding'
    retired = (root.services[1].projection_version, root.services[1].config.site_ids[0])
    root.services = root.services[:1]
    observer._observe_once(); assert output[-1]['state'] == 'healthy'
    assert retired not in observer._app_site_states
    assert set(observer._app_site_states) == observer.known_owned_keys


def test_incomplete_owner_enumeration_is_unknown_and_recovers():
    observer, root, tick, output = observer_for(('healthy', 'healthy'))
    observer._observe_once()
    root.enumeration_failure = RuntimeError('PRIVATE'); observer._observe_once()
    assert output[-1] == dict(state='unknown', reason='dependencies_unconfirmed')
    assert not observer._app_ownership_confirmed
    root.enumeration_failure = None; observer._observe_once()
    assert output[-1]['state'] == 'healthy'


def test_cache_bounded_to_current_owners_over_many_retirements():
    observer, root, tick, output = observer_for(('healthy',))
    for i in range(100):
        root.services = (Service('version-'+str(i)),)
        observer._observe_once()
        assert len(observer._app_site_states) == len(observer.known_owned_keys) == 1


def test_publisher_errors_and_flag_do_not_add_health_observations_or_native_events():
    traces = []
    for enabled in (False, True):
        observer, root, tick, output = observer_for(('healthy', 'rebuilding'))
        def failed(*args, **kwargs):raise OSError('PRIVATE')
        observer._app_health = SimpleNamespace(enabled=enabled, publish=failed)
        observer._observe_once(); tick[0] = 55; observer._observe_once()
        traces.append(([service.calls for service in root.services], observer.telemetry.events))
    assert traces[0] == traces[1]


def test_start_seeds_all_sites_and_stop_cannot_be_overwritten_green(monkeypatch):
    from app.traffic_projection import health_observer as module
    monkeypatch.setattr(module.threading, 'Thread', NoThread)
    observer, root, tick, output = observer_for(('healthy', 'healthy'))
    observer.start(root.services)
    assert output[0]['state'] == 'unknown' and output[-1]['state'] == 'healthy'
    observer.request_stop()
    observer.observe_service_site(root.services[0], root.services[0].config.site_ids[0])
    assert output[-1] == dict(state='unknown', reason='source_stopping')


@pytest.mark.skipif(__import__('os').name != 'posix', reason='Linux/POSIX owner report openat contract')
def test_real_projection_sql_trace_is_identical_and_report_aggregate_has_zero_sql(tmp_path, monkeypatch):
    import sqlite3
    from .test_projection import _repository, SITE, NOW
    from app.traffic_projection.service import TrafficProjectionService
    from app.operations_health import TRAFFIC_UNIT
    from tests.test_operations_app_health import _real_publisher
    repo = _repository(tmp_path)
    service = TrafficProjectionService(SimpleNamespace(site_ids=(SITE,)), repository=repo,
        source=SimpleNamespace(head=lambda site: (NOW, 'synthetic-cycle')), clock=lambda:NOW)
    original = sqlite3.connect; sql = []
    def connect(*args, **kwargs):
        connection = original(*args, **kwargs); connection.set_trace_callback(sql.append); return connection
    monkeypatch.setattr(sqlite3, 'connect', connect)
    traces = []
    for enabled in (False, True):
        observer = TrafficProjectionHealthObserver(Root((service,)), telemetry=Telemetry(), monotonic=lambda:0)
        observer._app_health = _real_publisher(TRAFFIC_UNIT, tmp_path)
        observer._app_health.enabled = enabled
        sql.clear(); observer._observe_once(); traces.append(list(sql))
        assert traces[-1], 'native health observation must remain real, not a fake no-op'
        sql.clear(); observer._publish_app_health_locked()
        assert sql == [], 'cached aggregate/report must not touch SQLite'
        if enabled:assert (tmp_path/'app-health.json').is_file()
    assert traces[0] == traces[1], 'report ON cannot add a query/PRAGMA/transaction'
