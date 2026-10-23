"""Feature boundary and passive HTTP readiness; no running service changes."""
import importlib
import os
from pathlib import Path
import threading
import time

from flask import Flask
import pytest
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.serving import make_server

from app.unified_sqlite_audit import readiness
from app.unified_sqlite_audit.model import AuditError, enabled


@pytest.mark.parametrize('raw,result',[('true',True),('false',False),('TRUE',False),('',False),
    (True,False),(False,False),(None,False),(1,False),('invalid',False)])
def test_flag_exact_and_invalid_is_off(raw,result):
    assert enabled({'sqlite_unified_audit_enabled':raw}) is result


def test_missing_flag_is_off():
    assert enabled({}) is False


@pytest.mark.parametrize('raw',['true','false','invalid'])
def test_settings_glue_preserves_every_other_existing_value(monkeypatch,raw):
    settings=importlib.import_module('app.settings')
    before=settings.get_settings()
    monkeypatch.setattr(settings,'SQLITE_UNIFIED_AUDIT_ENABLED',raw)
    after=settings.get_settings()
    assert after.pop('sqlite_unified_audit_enabled')==raw
    before.pop('sqlite_unified_audit_enabled')
    assert before==after


def test_config_declares_default_off_once_and_audit_has_no_env_reads():
    root=Path(__file__).resolve().parents[2]
    config=(root/'app/config.py').read_text(encoding='utf-8')
    assert config.count('SQLITE_UNIFIED_AUDIT_ENABLED = os.getenv("SQLITE_UNIFIED_AUDIT_ENABLED", "false")')==1
    for source in (root/'app/unified_sqlite_audit').glob('*.py'):
        assert 'os.getenv(' not in source.read_text(encoding='utf-8')


def app(monkeypatch,raw='true'):
    value=Flask(__name__)
    value.wsgi_app=ProxyFix(value.wsgi_app,x_for=1,x_host=1,x_port=1,x_proto=1)
    monkeypatch.setattr(readiness,'process_identity',lambda pid:('123','synthetic-boot'))
    readiness.install(value,{'sqlite_unified_audit_enabled':raw})
    return value


@pytest.mark.parametrize('raw',['false','invalid',None])
def test_off_has_no_route_or_extension_or_preflight(monkeypatch,raw):
    value=app(monkeypatch,raw)
    readiness.prepare_portal_state(value)
    assert 'unified_sqlite_audit' not in value.extensions
    assert value.test_client().get('/__internal/audit-ready').status_code==404


@pytest.mark.parametrize('headers,peer',[
    ({},'192.0.2.4'),({'X-Forwarded-For':'127.0.0.1'},'192.0.2.4'),
    ({'X-Forwarded-Host':'localhost'},'127.0.0.1'),({'Forwarded':'for=127.0.0.1'},'127.0.0.1'),
    ({'X-Real-IP':'127.0.0.1'},'127.0.0.1'),({'Host':'public.example'},'127.0.0.1')])
def test_public_and_proxy_ready_rejected(monkeypatch,headers,peer):
    value=app(monkeypatch)
    assert value.test_client().get('/__internal/audit-ready',headers=headers,
        environ_base={'REMOTE_ADDR':peer}).status_code==404


def test_probe_is_passive_204_and_new_app_has_distinct_run(monkeypatch):
    first=app(monkeypatch);second=app(monkeypatch)
    response=first.test_client().get('/__internal/audit-ready',base_url='http://127.0.0.1',
        environ_base={'REMOTE_ADDR':'127.0.0.1'})
    assert response.status_code==204 and response.data==b''
    assert response.headers['Cache-Control']=='no-store'
    assert response.headers['X-Audit-Run']!=second.extensions['unified_sqlite_audit_run_id']
    assert first.extensions['unified_sqlite_audit'].snapshot()['summary']['evaluated']==0


def test_fork_or_pid_reuse_never_readies(monkeypatch):
    value=app(monkeypatch)
    monkeypatch.setattr(readiness,'process_identity',lambda pid:('different-start','synthetic-boot'))
    assert value.test_client().get('/__internal/audit-ready',base_url='http://127.0.0.1',
        environ_base={'REMOTE_ADDR':'127.0.0.1'}).status_code==503


@pytest.mark.skipif(os.name!='posix',reason='Linux /proc listener and process provenance contract')
def test_real_local_http_204_is_required_not_app_creation():
    value=Flask(__name__);run_id=readiness.install(value,{'sqlite_unified_audit_enabled':'true'})
    server=make_server('127.0.0.1',0,value)
    thread=threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        proof=readiness.probe(server.server_port)
        assert proof.portal_run_id==run_id and proof.pid==os.getpid()
        assert readiness.confirm(proof)
        changed=readiness.ReadyProof(proof.portal_run_id,proof.pid,'reused',proof.boot,proof.port)
        assert not readiness.confirm(changed)
    finally:
        server.shutdown();thread.join();server.server_close()
    with pytest.raises(AuditError,match='ready_unproven'):readiness.probe(proof.port)


@pytest.mark.parametrize('raw',['false','invalid',None,'true'])
def test_actual_portal_composition_no_new_sql_or_auth_failure(monkeypatch,raw):
    import sqlite3
    from unittest.mock import Mock
    from app.settings import get_settings
    from app.web.web import create_app
    import app.unified_sqlite_audit.preflight as preflight
    settings=get_settings()
    settings.update(sqlite_unified_audit_enabled=raw,portal_counter_enabled=False,
        capport_enabled=False,omada_webhook_enabled=False)
    def forbidden(*a,**k):pytest.fail('optional audit must not open SQLite or start worker at composition')
    monkeypatch.setattr(sqlite3,'connect',forbidden)
    value=create_app(portal_counter_service=None,public_traffic_service=None,public_traffic_worker=None,
        controller=Mock(),portal_evidence_sink=None,client_hints_probe=None,settings=settings)
    assert value.test_client().get('/success').status_code==200
    assert value.extensions['portal_entry_handler'] is not None
    if raw=='true':
        def missing():raise FileNotFoundError()
        original=preflight.prepare
        monkeypatch.setattr(preflight,'prepare',lambda on,run_id:original(on,run_id,inventory_loader=missing))
        from app.unified_sqlite_audit import status as status_module
        monkeypatch.setattr(status_module,'OutcomeJournal',Mock(side_effect=FileNotFoundError))
        # Explicit unavailable inventory, no fallback source or OS changes.
        readiness.prepare_portal_state(value)
        status=value.extensions['unified_sqlite_audit'].snapshot()
        assert status['cycle_state']=='BLOCKED_NO_TRUSTED_BINDINGS'
        assert len(status['stores'])==17 and status['summary']['eligible_physical_count'] is None
    else:
        assert value.test_client().get('/__internal/audit-ready').status_code==404
        assert 'unified_sqlite_audit' not in value.extensions


def test_startup_only_ready_retry_is_finite_and_cancellable():
    times=iter([0,0,0.2,0.4,0.6,0.8,1,1.2,1.4,1.6,2])
    calls=[]
    def absent(port,**kwargs):calls.append(port);raise AuditError('ready_unproven')
    with pytest.raises(AuditError,match='ready_unproven'):
        readiness.wait_ready(8088,1,probe_fn=absent,clock=lambda:next(times),sleep=lambda s:None)
    assert 1<=len(calls)<=5
    with pytest.raises(AuditError,match='cancelled'):
        readiness.wait_ready(8088,60,cancelled=lambda:True,probe_fn=absent)
    for bad in (-1,True,301):
        with pytest.raises(AuditError):readiness.wait_ready(8088,bad,probe_fn=absent)


@pytest.mark.skipif(os.name!='posix',reason='Linux real HTTP startup race and /proc process/listener binding')
def test_oneshot_waits_for_actual_http_serving_not_app_or_type_simple_activation(tmp_path):
    value=Flask(__name__);run_id=readiness.install(value,{'sqlite_unified_audit_enabled':'true'})
    server=make_server('127.0.0.1',0,value)
    allow_http=threading.Event();waiting=threading.Event();results=[];errors=[]
    stopped=threading.Event();elapsed=[0];attempts=[]
    def delayed_probe(port,**kwargs):
        attempts.append(elapsed[0])
        if len(attempts)<=3:
            elapsed[0]=(61,301,5401)[len(attempts)-1]
            raise readiness.ReadyUnavailable()
        return readiness.probe(port,**kwargs)
    def pause(seconds):elapsed[0]+=seconds
    def serve():
        assert allow_http.wait(5)
        server.serve_forever()
    def launch():
        waiting.set()
        try:
            proof=readiness.wait_ready(server.server_port,0,until_cancelled=True,
                cancelled=stopped.is_set,probe_fn=delayed_probe,clock=lambda:elapsed[0],sleep=pause)
            from app.unified_sqlite_audit.runner import AuditCycleRunner, QualifiedManifest
            from app.unified_sqlite_audit.status import OutcomeJournal
            directory=tmp_path/'journal';directory.mkdir(mode=0o700)
            loads=[]
            def missing():loads.append(1);raise FileNotFoundError()
            cycle=AuditCycleRunner(OutcomeJournal(directory),inventory_loader=missing)
            first=cycle.run_once(proof.portal_run_id,QualifiedManifest(proof))
            again=cycle.run_once(proof.portal_run_id,QualifiedManifest(proof))
            assert first['audit_cycle_id']==again['audit_cycle_id'] and len(loads)==1
            results.append(proof)
        except BaseException as error:errors.append(error)
    thread=threading.Thread(target=serve);runner_thread=threading.Thread(target=launch)
    thread.start();runner_thread.start()
    try:
        assert waiting.wait(1)
        time.sleep(0.05)
        assert results==[]  # App exists / socket bound, but no served 204 yet.
        allow_http.set();runner_thread.join(5)
        assert not runner_thread.is_alive() and errors==[]
        assert results[0].portal_run_id==run_id and readiness.confirm(results[0])
        assert len(attempts)==4 and elapsed[0]>5400
    finally:
        stopped.set();allow_http.set();server.shutdown();thread.join(5);runner_thread.join(5);server.server_close()


@pytest.mark.parametrize('successful_attempt',[4,1505])
def test_auto_wait_has_no_elapsed_or_attempt_limit_and_manual_still_fail_fast(successful_attempt):
    calls=[];elapsed=[0]
    proof=readiness.ReadyProof('f81892ee-7497-4a89-89a0-bf4d5290ff38',1,'start','boot',8088)
    def delayed(port,**kwargs):
        calls.append(port)
        elapsed[0]=(61,301,5401)[len(calls)-1] if len(calls)<=3 else elapsed[0]+3600
        if len(calls)==successful_attempt:return proof
        raise readiness.ReadyUnavailable()
    result=readiness.wait_ready(8088,0,until_cancelled=True,probe_fn=delayed,
        clock=lambda:elapsed[0],sleep=lambda seconds:None)
    assert result is proof and len(calls)==successful_attempt and elapsed[0]>5400
    calls.clear()
    with pytest.raises(readiness.ReadyUnavailable):
        readiness.wait_ready(8088,0,probe_fn=delayed,sleep=lambda s:pytest.fail('manual fail-fast slept'))
    assert calls==[8088]


@pytest.mark.parametrize('bad',['proxy','pid','identity','listener','redirect'])
def test_auto_wait_rejects_genuine_bad_response_or_proof_without_retry(monkeypatch,bad):
    import sqlite3
    monkeypatch.setattr(sqlite3,'connect',lambda *a,**k:pytest.fail('readiness opened source'))
    headers={'X-Audit-Run':'f81892ee-7497-4a89-89a0-bf4d5290ff38',
        'X-Audit-Pid':'123','X-Audit-Start':'start','X-Audit-Boot':'boot'}
    if bad=='proxy':headers['Forwarded']='for=127.0.0.1'
    if bad=='pid':headers['X-Audit-Pid']='invalid'
    closed=[];requested=[]
    class Response:
        status=302 if bad=='redirect' else 204
        def read(self,n):return b''
        def getheaders(self):return list(headers.items())
        def getheader(self,k,default=None):return headers.get(k,default)
    class Connection:
        def __init__(self,*a,**k):pass
        def request(self,*a,**k):requested.append(1)
        def getresponse(self):return Response()
        def close(self):closed.append(1)
    monkeypatch.setattr(readiness.http.client,'HTTPConnection',Connection)
    monkeypatch.setattr(readiness,'process_identity',lambda pid:('wrong','boot') if bad=='identity' else ('start','boot'))
    monkeypatch.setattr(readiness,'_owns_listener',lambda pid,port:bad!='listener')
    with pytest.raises(readiness.ReadyRejected):
        readiness.wait_ready(8088,0,until_cancelled=True,probe_fn=readiness.probe,
            sleep=lambda seconds:pytest.fail('security rejection was retried'))
    assert requested==closed==[1]
