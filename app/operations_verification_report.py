"""One-shot bounded tmpfs startup report for existing non-Portal owners.

No provisioner, timer, DB probe or daemon. Shared-admin self-report only.
Sensor/NI02 use their existing versioned channels instead of this transport.
"""
import hashlib
import json
import os
import threading
import time
import uuid
from datetime import datetime,timezone

from app.device_fingerprint_sensor import operations_metadata as m
from app.network_metadata_projection.operations_health import Channel
from .operations_verification import snapshot,validate_checks

SCHEMA='captivprod.ops.owner-startup-check.v1'
UNITS={'fingerprint-evidence.service':'evidence','network-metadata.service':'ni01',
    'network-service-recognition.service':'ni04','traffic-projection.service':'traffic-projection'}
REPORT='startup-checks.json'
_lock=threading.Lock()
_sequences={}


def configured_channel(unit):
    import pwd
    m.require(unit in UNITS)
    # Only the shared-admin channel is admitted here. No account/permission is
    # changed: another effective UID or missing provisioning means no evidence.
    uid=pwd.getpwnam('admin').pw_uid
    m.require(uid>0)
    return Channel(uid,'/run/captiveportal-operations/'+UNITS[unit])


def decode(raw,unit):
    m.require(type(raw) is bytes and 0<len(raw)<=m.LIMIT and unit in UNITS)
    def pairs(items):
        value={}
        for key,item in items:m.require(key not in value);value[key]=item
        return value
    def invalid(_):raise ValueError('invalid JSON')
    value=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=invalid)
    m.require(type(value) is dict and set(value)=={'schema_version','producer_unit','producer','epoch','sequence',
        'sample_time_utc','sample_boottime_ns','store_checks'})
    m.require(value['schema_version']==SCHEMA and value['producer_unit']==unit)
    producer=value['producer']
    m.require(type(producer) is dict and set(producer)=={'boot_id','pid','start_ticks'})
    m.require(type(producer['boot_id']) is str and str(uuid.UUID(producer['boot_id']))==producer['boot_id'])
    m.require(m.integer(producer['pid'],2**31-1,1) and m.integer(producer['start_ticks'],minimum=1))
    m.require(type(value['epoch']) is str and str(uuid.UUID(value['epoch']))==value['epoch'])
    m.require(m.integer(value['sequence'],minimum=1) and m.integer(value['sample_boottime_ns'],2**63-1))
    sampled=m.parse_stamp(value['sample_time_utc'])
    validate_checks(value['store_checks'],unit,sampled)
    m.require(value['store_checks']['instance']==value['epoch'])
    return value


def publish_startup(unit,*,channel=configured_channel,identity=m.process_identity,now=lambda:datetime.now(timezone.utc),
                    monotonic=time.monotonic,boottime=m.boot_ns):
    if unit not in UNITS or not _lock.acquire(blocking=False):return False
    folder=fd=name=None
    try:
        deadline=monotonic()+m.BUDGET
        source=channel(unit);m.require(os.geteuid()==source.uid)
        folder=source.open();checks=snapshot(unit)
        producer=identity(os.getpid(),source.uid)
        key=(os.getpid(),unit);sequence=_sequences.get(key,0)+1;_sequences[key]=sequence
        value=dict(schema_version=SCHEMA,producer_unit=unit,producer=producer,epoch=checks['instance'],sequence=sequence,
            sample_time_utc=m.stamp(now()),sample_boottime_ns=boottime(),store_checks=checks)
        raw=json.dumps(value,ensure_ascii=True,allow_nan=False,separators=(',',':')).encode('ascii');decode(raw,unit)
        try:
            info=os.stat(REPORT,dir_fd=folder,follow_symlinks=False);source.validate_file(info)
            m.require(info.st_dev==os.fstat(folder).st_dev)
        except FileNotFoundError:pass
        m.require(monotonic()<deadline)
        name='.startup-'+uuid.uuid4().hex
        fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,0o600,dir_fd=folder)
        source.validate_file(os.fstat(fd));m.require(os.write(fd,raw)==len(raw))
        os.close(fd);fd=None
        m.require(monotonic()<deadline)
        os.replace(name,REPORT,src_dir_fd=folder,dst_dir_fd=folder);name=None
        return True
    except Exception:return False
    finally:
        if fd is not None:os.close(fd)
        if name is not None and folder is not None:
            try:os.unlink(name,dir_fd=folder)
            except OSError:pass
        if folder is not None:os.close(folder)
        _lock.release()


class Reader:
    def __init__(self,unit,*,channel=configured_channel,identity=m.process_identity,boottime=m.boot_ns):
        m.require(unit in UNITS)
        self.unit,self.channel,self.identity,self.boottime=unit,channel,identity,boottime
        self.last=None

    def read(self,service,now,*,deadline,monotonic=time.monotonic,cancel=None):
        folder=fd=None
        try:
            m.require(service['operational_state']=='running' and service['main_pid'] is not None)
            m.require(monotonic()<deadline and not (cancel and cancel.is_set()))
            source=self.channel(self.unit);folder=source.open()
            fd=os.open(REPORT,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,dir_fd=folder)
            before=os.fstat(fd);source.validate_file(before)
            m.require(before.st_dev==os.fstat(folder).st_dev)
            raw=os.read(fd,m.LIMIT+1);after=os.fstat(fd);source.validate_file(after)
            current=os.stat(REPORT,dir_fd=folder,follow_symlinks=False);source.validate_file(current)
            m.require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==
                (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)
                and (current.st_dev,current.st_ino)==(before.st_dev,before.st_ino) and len(raw)==before.st_size)
            value=decode(raw,self.unit);producer=self.identity(service['main_pid'],source.uid)
            m.require(value['producer']==producer)
            sampled=m.parse_stamp(value['sample_time_utc'])
            start=datetime.fromisoformat(service['started_at_utc'].replace('Z','+00:00'))
            m.require(sampled>=start and value['sample_boottime_ns']>=producer['start_ticks']*1_000_000_000//os.sysconf('SC_CLK_TCK'))
            m.require(all(row['checked_at_utc'] is None or m.parse_stamp(row['checked_at_utc'])>=start for row in value['store_checks']['checks'].values()))
            age=(now-sampled).total_seconds();boot_age=(self.boottime()-value['sample_boottime_ns'])/1e9
            m.require(age>=0 and boot_age>=0 and abs(age-boot_age)<=5)
            digest=hashlib.sha256(raw).digest()
            if self.last is not None and self.last[0]==producer:
                m.require(value['epoch']==self.last[1] and value['sequence']>=self.last[2] and sampled>=self.last[4])
                if value['sequence']==self.last[2]:m.require(digest==self.last[3])
            m.require(monotonic()<deadline and not (cancel and cancel.is_set()))
            self.last=producer,value['epoch'],value['sequence'],digest,sampled
            return dict(status='stale' if max(age,boot_age)>m.TTL else 'fresh',producer=producer,
                checks=value['store_checks'],expires_boottime_ns=value['sample_boottime_ns']+int(m.TTL*1e9))
        except Exception:return dict(status='unknown')
        finally:
            if fd is not None:os.close(fd)
            if folder is not None:os.close(folder)
