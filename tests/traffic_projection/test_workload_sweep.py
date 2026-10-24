"""Whole-current-Site proof only; no extra worker iteration or source query."""
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from app.traffic_projection.service import TrafficProjectionService
from app.traffic_projection.models import TrafficProjectionConfig,ProjectionRunResult,TrafficProjectionSourceUnavailable
from .test_projection import NOW


def worker(tmp_path,values):
    sites=tuple(values);repo=SimpleNamespace(projection_version='v',site_state=lambda s:{'status':'healthy'},version_status=lambda:'active')
    obj=TrafficProjectionService(TrafficProjectionConfig(enabled=True,db_path=str(tmp_path/'traffic.db'),
        writer_lock_path=str(tmp_path/'lock'),source_db_path=str(tmp_path/'source.db'),site_ids=sites),
        repository=repo,projection_version='v',source=object(),monotonic=lambda:0)
    obj.initialize=Mock();obj._reconciliation_due=Mock(return_value=False)
    obj._record_worker_failure=Mock();obj.repair_site=Mock()
    def incremental(site,**kwargs):
        value=values[site]
        if isinstance(value,Exception):raise value
        obj._incremental_workload=None if value is None else (site,value)
        return ProjectionRunResult(site,0,0,0,0,0,0,False)
    obj.incremental_site=Mock(side_effect=incremental)
    return obj


@pytest.mark.parametrize('values,expected',[({'a':0,'b':0},0),({'a':1,'b':0},1),({'a':0,'b':1},1),
    ({'a':None,'b':0},None),({'a':0,'b':TrafficProjectionSourceUnavailable('test')},None),({},None)])
def test_whole_sweep_zero_one_and_incomplete(tmp_path,values,expected):
    obj=worker(tmp_path,values);assert obj.operations_workload()['incremental_backlog_present'] is None
    obj._maintain_version(obj,is_target=False)
    assert obj.operations_workload()['incremental_backlog_present']==expected
    assert obj.incremental_site.call_count==len(values)
    calls=obj.incremental_site.call_count
    for _ in range(100):assert obj.operations_workload()['incremental_backlog_present']==expected
    assert obj.incremental_site.call_count==calls


@pytest.mark.parametrize('fault',['target','reconcile','repair','stop','pid','sites','version','source','expiry','observer-failure','restart'])
def test_unknown_instead_of_stale_global_zero(tmp_path,monkeypatch,fault):
    obj=worker(tmp_path,{'a':0,'b':0});obj._maintain_version(obj,is_target=False)
    assert obj.operations_workload()['incremental_backlog_present']==0
    if fault=='target':
        obj.invalidate_operations_workload();obj._maintain_version(obj,is_target=True)
    elif fault=='reconcile':obj._reconciliation_due.return_value=True;obj.reconcile_site=Mock();obj._maintain_version(obj,is_target=False)
    elif fault=='repair':obj.repository.site_state=lambda s:{'status':'rebuilding','last_error_category':'repair_delete'};obj._maintain_version(obj,is_target=False)
    elif fault=='stop':obj._stop.set()
    elif fault=='pid':monkeypatch.setattr('app.traffic_projection.service.os.getpid',lambda:-1)
    elif fault=='sites':obj.config=SimpleNamespace(site_ids=('a','b','new'))
    elif fault=='version':obj.projection_version='replacement'
    elif fault=='source':obj.source=object()
    elif fault=='expiry':obj._monotonic=lambda:181
    elif fault=='observer-failure':
        obj._health_observer=SimpleNamespace(observe_service_site=lambda *a,**k:obj.invalidate_operations_workload())
        obj._maintain_version(obj,is_target=False)
    else:obj=worker(tmp_path,{'a':0,'b':0})
    assert obj.operations_workload()['incremental_backlog_present'] is None


@pytest.mark.parametrize('state,available',[('stale',True),('rebuilding',True),('unavailable',False),('healthy',False)])
def test_existing_observation_invalidates_counter_without_new_probe(tmp_path,state,available):
    from app.traffic_projection.health_observer import TrafficProjectionHealthObserver
    from .test_health_observer import _observation,Telemetry
    obj=worker(tmp_path,{'a':0});obj._maintain_version(obj,is_target=False)
    observation=_observation(state);observation['source_available']=available
    obj.health_observation=Mock(return_value=observation)
    observer=TrafficProjectionHealthObserver(obj,telemetry=Telemetry(),monotonic=lambda:0)
    observer._app_health.enabled=False
    observer.observe_service_site(obj,'a')
    assert obj.health_observation.call_count==1
    assert obj.operations_workload()['incremental_backlog_present'] is None


@pytest.mark.parametrize('row_count,expected',[(1,0),(100,1)])
def test_real_incremental_boolean_is_captured_from_existing_batch(tmp_path,row_count,expected):
    from .test_projection import _repository,_observation_db,_insert_cycle,SITE
    repo=_repository(tmp_path);source=tmp_path/'observations.db';connection=_observation_db(source)
    for n in range(row_count):_insert_cycle(connection,cycle_id='cycle-'+str(n).zfill(3))
    connection.close()
    config=TrafficProjectionConfig(enabled=True,db_path=str(repo.path) if hasattr(repo,'path') else str(tmp_path/'projection.sqlite3'),
        source_db_path=str(source),writer_lock_path=str(tmp_path/'lock'),site_ids=(SITE,))
    service=TrafficProjectionService(config,repository=repo,clock=lambda:NOW)
    repo.update_site(SITE,status='healthy')
    service.incremental_site(SITE)
    assert service._incremental_workload==(SITE,expected)
    # A per-Site result cannot claim an entire active-owner snapshot by itself.
    assert service.operations_workload()['incremental_backlog_present'] is None
