"""Only actual composed Portal/Visit instances, bounded locks, never SQLite."""
import os
import logging
import threading
import time
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock
from flask import Flask
import pytest
from app.admin_web.runtime import AdminWebRuntime,bind_core_operations_snapshot,core_workload_snapshot
from app.device_fingerprint_portal.runtime import PortalEvidenceRuntime
from app.device_fingerprint_portal.config import portal_config_from_env
from app.visit_lifecycle.runtime import VisitLifecycleRuntime
from app.visit_lifecycle.repository import VisitRepository
from app.visit_lifecycle.telemetry import VisitTelemetry
from tests.visit_lifecycle.conftest import visit_config


@pytest.fixture
def composed(visit_config):
    app=Flask(__name__);portal=PortalEvidenceRuntime(replace(portal_config_from_env({}),enabled=True),producer=object())
    portal._worker_loop=lambda:portal.stop_event.wait(10)
    portal.start()
    visit=VisitLifecycleRuntime(config=visit_config,repository=VisitRepository(visit_config),telemetry=VisitTelemetry(logging.getLogger(__name__)))
    visit.state='active'
    admin=AdminWebRuntime(state='active',config=SimpleNamespace(enabled=True),operations_service=Mock(),operations_visit_runtime=visit)
    app.extensions.update(admin_web_runtime=admin,portal_evidence_runtime=portal)
    bind_core_operations_snapshot(app,{'capport_enabled':False})
    yield app,portal,visit,admin
    portal.stop();portal.thread.join(2)


@pytest.mark.parametrize('depth,foreground,background',[(0,0,0),(3,2,4)])
def test_actual_queue_waiter_snapshot_excludes_holder_with_zero_sql(composed,monkeypatch,depth,foreground,background):
    import sqlite3
    app,portal,visit,_=composed
    monkeypatch.setattr(sqlite3,'connect',Mock(side_effect=AssertionError('Core SQL forbidden')))
    for _ in range(depth):portal.queue.put_nowait(object())
    coordinator=visit.repository._write_coordinator
    with coordinator._condition:
        coordinator._holder_operation='held'
        coordinator._foreground.extend([object()]*foreground);coordinator._background.extend([object()]*background)
    portal.queue.qsize=Mock(wraps=portal.queue.qsize)
    coordinator._waiting_counts=Mock(wraps=coordinator._waiting_counts)
    assert core_workload_snapshot(app)==dict(portal_evidence_queue_depth=depth,
        visit_writer_foreground_waiters=foreground,visit_writer_background_waiters=background)
    assert portal.queue.qsize.call_count==coordinator._waiting_counts.call_count==1
    assert len(portal.queue.queue)==depth


@pytest.mark.parametrize('fault',['pid','binding','portal-stopped','portal-disabled','portal-replaced','visit-stopping','visit-unavailable','visit-replaced','missing'])
def test_unavailable_or_changed_composition_never_invents_zero(composed,monkeypatch,fault):
    app,portal,visit,admin=composed
    if fault=='pid':monkeypatch.setattr('app.admin_web.runtime.os.getpid',lambda:-1)
    elif fault=='binding':app.extensions['admin_web_runtime']=AdminWebRuntime(state='active')
    elif fault=='portal-stopped':portal.stop()
    elif fault=='portal-disabled':portal.config=replace(portal.config,enabled=False)
    elif fault=='portal-replaced':app.extensions['portal_evidence_runtime']=object()
    elif fault=='visit-stopping':visit.state='stopping'
    elif fault=='visit-unavailable':visit.available=False
    elif fault=='visit-replaced':admin.operations_visit_runtime=object()
    else:app.extensions.pop('operations_core_workload_binding')
    result=core_workload_snapshot(app)
    if fault in {'pid','binding','missing'}:assert all(v is None for v in result.values())
    elif fault.startswith('portal'):assert result['portal_evidence_queue_depth'] is None
    else:assert result['visit_writer_foreground_waiters'] is result['visit_writer_background_waiters'] is None


def test_live_contending_writers_are_waiters_not_holder_and_sampler_does_not_block(composed,monkeypatch):
    import sqlite3
    from app.visit_lifecycle.repository import WRITE_OPERATION_START,WRITE_OPERATION_READER
    app,_,visit,_=composed;coordinator=visit.repository._write_coordinator
    monkeypatch.setattr(sqlite3,'connect',Mock(side_effect=AssertionError('sampler never opens SQLite')))
    held=threading.Event();release=threading.Event();completed=[]
    def holder():
        with coordinator.acquire(WRITE_OPERATION_READER,timeout_ms=2000):held.set();release.wait(3)
    def waiter(operation):
        with coordinator.acquire(operation,timeout_ms=2000):completed.append(operation)
    threads=[threading.Thread(target=holder)]
    threads[0].start();assert held.wait(1)
    threads.extend([threading.Thread(target=waiter,args=(op,)) for op in (WRITE_OPERATION_START,WRITE_OPERATION_READER)])
    for thread in threads[1:]:thread.start()
    try:
        deadline=time.monotonic()+1
        while coordinator._waiting_counts()!=(1,1) and time.monotonic()<deadline:time.sleep(.001)
        assert coordinator._waiting_counts()==(1,1)
        result=core_workload_snapshot(app)
        assert (result['visit_writer_foreground_waiters'],result['visit_writer_background_waiters'])==(1,1)
        assert not completed and coordinator._holder_operation==WRITE_OPERATION_READER
    finally:
        release.set()
        for thread in threads:thread.join(2);assert not thread.is_alive()
    assert len(completed)==2 and coordinator._waiting_counts()==(0,0)
