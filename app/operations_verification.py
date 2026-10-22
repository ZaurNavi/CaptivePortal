"""Bounded historical owner startup evidence. Never opens or queries SQLite.

Capture only the existing initialize result. A report is not a new check and
does not authenticate a shared-UID owner independently of its own process.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from functools import wraps
import hashlib
import os
import re
import stat
import threading
import uuid

PORTAL = 'captive-portal.service'
SENSOR = 'fingerprint-sensor.service'
NI02 = 'network-metadata-projection.service'
OWNERS = {
    'portal_counter': PORTAL, 'public_traffic': PORTAL, 'visitor_registry': PORTAL,
    'visits': PORTAL, 'observations': PORTAL, 'current_state': PORTAL,
    'traffic_projection': 'traffic-projection.service',
    'fingerprint_evidence': 'fingerprint-evidence.service',
    'fingerprint_classification': 'fingerprint-classification.service',
    'fingerprint_control_plane': 'fingerprint-classification.service',
    'fingerprint_integration': PORTAL, 'network_metadata': 'network-metadata.service',
    'network_attribution': SENSOR, 'network_metadata_projection': NI02,
    'network_service_intelligence': 'network-service-recognition.service',
    'settings': PORTAL, 'sensor_spool': SENSOR,
}
SCOPES = ('schema_version', 'schema_signature', 'quick_check', 'foreign_key_check', 'integrity_check')
ALLOWED = {
    'visitor_registry': SCOPES[:3], 'visits': SCOPES[:4], 'observations': SCOPES[:2],
    'current_state': SCOPES[:3], 'traffic_projection': SCOPES[:4],
    'fingerprint_evidence': SCOPES[:2], 'fingerprint_integration': SCOPES[:2],
    'network_metadata': SCOPES[:2], 'network_attribution': SCOPES[:4],
    'network_metadata_projection': SCOPES[:4], 'network_service_intelligence': SCOPES[:4],
    'settings': SCOPES[:4], 'sensor_spool': ('schema_version', 'quick_check'),
}
ROW_KEYS = {'status','scope','checked_at_utc','checked_store_id','observed_store_id','reason'}
REASONS = {'startup_check','startup_check_failed','startup_unavailable','check_not_run'}
_lock = threading.RLock()
_pid, _instance, _rows, _paths = os.getpid(), str(uuid.uuid4()), {}, {}
_attempts=threading.local()


def checked(function,*args,**kwargs):
    """Observe failure of this exact existing check, even if init sanitizes it."""
    try:return function(*args,**kwargs)
    except Exception:
        stack=getattr(_attempts,'stack',[])
        if stack:stack[-1]=True
        raise


def stamp(now):
    return now.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')


def parse_stamp(value):
    if type(value) is not str or len(value) != 24:raise ValueError('invalid check time')
    parsed=datetime.strptime(value,'%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
    if stamp(parsed)!=value:raise ValueError('invalid check time')
    return parsed


def opaque_identity(info):
    if (not stat.S_ISREG(info.st_mode) or type(info.st_dev) is not int or type(info.st_ino) is not int
            or info.st_dev < 0 or info.st_ino <= 0):return None
    return hashlib.sha256(f'ops-store-v1:{info.st_dev}:{info.st_ino}'.encode('ascii')).hexdigest()


def file_identity(path):
    try:return opaque_identity(os.lstat(path))
    except (OSError,ValueError,TypeError,AttributeError):return None


def _current_process():
    global _pid,_instance
    if _pid != os.getpid():
        _pid,_instance=os.getpid(),str(uuid.uuid4())
        _rows.clear();_paths.clear()  # Never attest a parent's inherited check.


def validate_checks(value, unit, sampled_at=None):
    if type(value) is not dict or set(value)!={'instance','checks'}:raise ValueError('invalid owner checks')
    if type(value['instance']) is not str or str(uuid.UUID(value['instance']))!=value['instance']:raise ValueError('invalid check instance')
    rows=value['checks']
    if type(rows) is not dict or len(rows)>17:raise ValueError('invalid checks')
    for db_id,row in rows.items():
        if OWNERS.get(db_id)!=unit or type(row) is not dict or set(row)!=ROW_KEYS:raise ValueError('invalid check owner')
        if type(row['status']) is not str or row['status'] not in {'passed','failed','not_run','unknown'}:raise ValueError('invalid check state')
        scopes=row['scope']
        if (type(scopes) is not list or any(type(s) is not str for s in scopes) or len(set(scopes))!=len(scopes)
                or scopes!=[s for s in SCOPES if s in scopes] or not set(scopes)<=set(ALLOWED.get(db_id,()))):raise ValueError('invalid check scope')
        if row['status']=='passed' and not scopes:raise ValueError('empty passed scope')
        if type(row['reason']) is not str or row['reason'] not in REASONS:raise ValueError('invalid check reason')
        expected={'passed':'startup_check','failed':'startup_check_failed','not_run':'check_not_run','unknown':'startup_unavailable'}[row['status']]
        if row['reason']!=expected:raise ValueError('invalid check reason')
        if row['checked_at_utc'] is not None:
            at=parse_stamp(row['checked_at_utc'])
            if sampled_at is not None and at>sampled_at:raise ValueError('future check')
        elif row['status'] in {'passed','failed'}:raise ValueError('missing check time')
        for key in ('checked_store_id','observed_store_id'):
            if row[key] is not None and (type(row[key]) is not str or re.fullmatch('[0-9a-f]{64}',row[key]) is None):raise ValueError('invalid store identity')
    return value


def startup_check(db_id, path, scopes, *, failures=()):
    """Wrap an unchanged initializer; no additional SQL/transaction/fsync.

    Only named schema/check exceptions mean FAILED. I/O/config/startup refusal
    means UNKNOWN, not a fabricated corrupt-database diagnosis. On failure the
    completed scope is conservatively empty (no claim about failed subchecks).
    """
    if db_id not in ALLOWED:raise ValueError('unknown check hook')
    def decorate(function):
        @wraps(function)
        def initialize(self,*args,**kwargs):
            target=path(self)
            before=file_identity(target)
            with _lock:
                _current_process();_rows.pop(db_id,None);_paths.pop(db_id,None)
            stack=getattr(_attempts,'stack',None)
            if stack is None:stack=_attempts.stack=[]
            stack.append(False)
            try:
                try:result=function(self,*args,**kwargs)
                except Exception as error:
                    _record(db_id,target,'failed' if stack[-1] or isinstance(error,failures) else 'unknown',[],before)
                    raise
            finally:stack.pop()
            actual=scopes(result) if callable(scopes) else scopes
            _record(db_id,target,'passed' if actual else 'not_run',actual,before)
            return result
        return initialize
    return decorate


def _record(db_id,path,status,scopes,before):
    # Reporting must never change an initializer's success/failure semantics.
    try:
        after=file_identity(path)
        if status=='passed' and (after is None or before is not None and before!=after):status='unknown'
        reason={'passed':'startup_check','failed':'startup_check_failed','not_run':'check_not_run','unknown':'startup_unavailable'}[status]
        row=dict(status=status,scope=[s for s in SCOPES if s in scopes],
            checked_at_utc=stamp(datetime.now(timezone.utc)) if status!='not_run' else None,
            checked_store_id=after,observed_store_id=after,reason=reason)
        validate_checks(dict(instance=_instance,checks={db_id:row}),OWNERS[db_id])
        with _lock:
            _current_process();_rows[db_id]=row;_paths[db_id]=str(path)
        if OWNERS[db_id] not in {PORTAL,SENSOR,NI02} and os.environ.get('WEB_ADMIN_DB_SERVICES_ENABLED','false')=='true':
            from .operations_verification_report import publish_startup
            publish_startup(OWNERS[db_id])
    except Exception:pass


def snapshot(unit, *, observed=None, refresh=False, paths=None):
    with _lock:
        _current_process()
        rows={k:copy.deepcopy(v) for k,v in _rows.items() if OWNERS[k]==unit
            and (paths is None or k in paths and str(paths[k])==_paths[k])}
        registered_paths=dict(_paths);instance=_instance
    for db_id,row in rows.items():
        if observed is not None:row['observed_store_id']=observed.get(db_id)
        elif refresh:row['observed_store_id']=file_identity(registered_paths[db_id])
    return validate_checks(dict(instance=instance,checks=rows),unit)


def not_attested():
    return dict(status='not_attested',scope=None,as_of=None,source='none')


def project(db_id, record, current_id, *, intent, source_current, stale=False):
    """Public historical proof, independent of file-presence/app-health axes."""
    if db_id=='settings' and intent=='optional_disabled':
        return dict(status='not_applicable',scope=None,as_of=None,source='none',freshness='not_applicable',reason='configured_disabled')
    if record is None:return not_attested()
    row=record['row'];status=row['status'];reason=row['reason']
    if status=='not_run':return dict(status='not_attested',scope=None,as_of=None,source='none',freshness='unknown',reason='check_not_run')
    same=current_id is not None and row['checked_store_id']==current_id
    if not same or not source_current or stale:
        status='stale' if row['checked_at_utc'] is not None else 'unknown'
        reason='store_changed' if not same else 'source_stale'
    if status=='unknown':reason='startup_unavailable'
    return dict(status=status,scope=row['scope'] or None,as_of=row['checked_at_utc'],source=OWNERS[db_id],
        freshness='current_report' if same and source_current and not stale else 'stale',reason=reason)


def validate_public(value,db_id):
    if value==not_attested():return value  # Backward compatible v2 producer.
    if type(value) is not dict or set(value)!={'status','scope','as_of','source','freshness','reason'}:raise ValueError('invalid public check')
    if value['status'] not in {'passed','failed','unknown','stale','not_applicable','not_attested'}:raise ValueError('invalid public state')
    if value['source'] not in {'none',OWNERS[db_id]}:raise ValueError('invalid public owner')
    if value['freshness'] not in {'current_report','stale','unknown','not_applicable'}:raise ValueError('invalid public freshness')
    if value['reason'] not in REASONS|{'store_changed','source_stale','configured_disabled'}:raise ValueError('invalid public reason')
    scopes=value['scope']
    if scopes is not None and (type(scopes) is not list or any(type(s) is not str for s in scopes)
            or scopes!=[s for s in SCOPES if s in scopes] or not set(scopes)<=set(ALLOWED.get(db_id,()))):raise ValueError('invalid public scope')
    if value['as_of'] is not None:parse_stamp(value['as_of'])
    if value['status'] in {'passed','failed','stale'} and (value['source']=='none' or value['as_of'] is None):raise ValueError('missing historical proof')
    if value['status']=='passed' and (not scopes or value['freshness']!='current_report' or value['reason']!='startup_check'):raise ValueError('invalid passed proof')
    if value['status']=='failed' and (value['freshness']!='current_report' or value['reason']!='startup_check_failed'):raise ValueError('invalid failed proof')
    if value['status']=='unknown' and value['reason']!='startup_unavailable':raise ValueError('invalid unknown proof')
    if value['status']=='stale' and (value['freshness']!='stale' or value['reason'] not in {'store_changed','source_stale'}):raise ValueError('invalid stale proof')
    if value['status'] in {'not_applicable','not_attested'}:
        if value['scope'] is not None or value['as_of'] is not None or value['source']!='none':raise ValueError('invented check')
        if value['status']=='not_applicable' and (db_id!='settings' or value['freshness']!='not_applicable' or value['reason']!='configured_disabled'):raise ValueError('invalid disabled check')
        if value['status']=='not_attested' and (value['freshness']!='unknown' or value['reason']!='check_not_run'):raise ValueError('invalid missing check')
    return value
