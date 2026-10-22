"""Informational shared-admin report, NOT process-exclusive attestation.

Architect #295/6321505786 explicitly accepts the shared UID for display only.
Never use this channel for authorization, mutation, security or recovery.
"""
import hashlib
import json
import os
import stat
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from app.device_fingerprint_sensor import operations_metadata as m
from app.operations_health import NI02_UNIT, validate

SCHEMA = "captivprod.ops.ni02b-health.v1"
SCHEMA_V2 = "captivprod.ops.ni02b-health.v2"
PROVENANCE = "source_self_reported_shared_uid"
REPORT = "health.json"
DIRECTORY = "/run/captiveportal-operations/ni02b"


@dataclass(frozen=True)
class Channel:
    uid: int
    directory: str = DIRECTORY

    def open(self):
        parts = self.directory.split('/')
        m.require(parts[0] == '' and 2 < len(parts) <= 16 and all(p and p not in {'.','..'} for p in parts[1:]))
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            for index, part in enumerate(parts[1:]):
                parent = os.fstat(fd)
                m.require(parent.st_uid == 0 and not parent.st_mode & 0o022)
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
                os.close(fd); fd = child
            info = os.fstat(fd)
            m.require(info.st_uid == self.uid and stat.S_IMODE(info.st_mode) == 0o700)
            m._tmpfs(fd)
            result, fd = fd, None
            return result
        finally:
            if fd is not None: os.close(fd)

    def validate_file(self, info):
        m.require(stat.S_ISREG(info.st_mode) and info.st_uid == self.uid and info.st_nlink == 1
                  and stat.S_IMODE(info.st_mode) == 0o600 and 0 <= info.st_size <= m.LIMIT)


def configured_channel():
    import pwd
    uid = pwd.getpwnam('admin').pw_uid
    m.require(uid > 0)
    return Channel(uid)


def decode(raw):
    m.require(type(raw) is bytes and 0 < len(raw) <= m.LIMIT)
    def pairs(items):
        value = {}
        for key, item in items:
            m.require(key not in value); value[key] = item
        return value
    def invalid(value):raise m.MetadataUnavailable()
    value = json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=invalid)
    v2=type(value) is dict and value.get('schema_version')==SCHEMA_V2
    m.require(type(value) is dict and set(value) == {'schema_version','producer_unit','producer','epoch','sequence',
        'sample_time_utc','sample_boottime_ns','provenance','application_health','source_confirmed_at','writer_committed_at','pending_observed_at'} | ({'store_checks'} if v2 else set()))
    m.require(value['schema_version'] in {SCHEMA,SCHEMA_V2} and value['producer_unit'] == NI02_UNIT and value['provenance'] == PROVENANCE)
    producer = value['producer']
    m.require(type(producer) is dict and set(producer) == {'boot_id','pid','start_ticks'})
    m.require(type(producer['boot_id']) is str and str(uuid.UUID(producer['boot_id'])) == producer['boot_id'])
    m.require(m.integer(producer['pid'],2**31-1,1) and m.integer(producer['start_ticks'],minimum=1))
    m.require(type(value['epoch']) is str and str(uuid.UUID(value['epoch'])) == value['epoch'])
    m.require(m.integer(value['sequence'],minimum=1) and m.integer(value['sample_boottime_ns'],2**63-1))
    sampled = m.parse_stamp(value['sample_time_utc'])
    if v2:
        from app.operations_verification import validate_checks
        validate_checks(value['store_checks'],NI02_UNIT,sampled)
    health = validate(value['application_health'],NI02_UNIT)
    ages = {}
    for key in ('source_confirmed_at','writer_committed_at','pending_observed_at'):
        ages[key] = None if value[key] is None else (sampled - m.parse_stamp(value[key])).total_seconds()
        m.require(ages[key] is None or ages[key] >= 0)
    if health['state'] == 'healthy':
        m.require(ages['source_confirmed_at'] is not None and ages['source_confirmed_at'] <= 30
            and ages['writer_committed_at'] is not None and ages['writer_committed_at'] <= 180
            and ages['pending_observed_at'] is not None and ages['pending_observed_at'] <= 180)
    if health['pending_count'] is not None:
        m.require(ages['pending_observed_at'] is not None and ages['pending_observed_at'] <= 180)
    return value


class HealthPublisher:
    def __init__(self, *, enabled=None, channel=configured_channel, monotonic=time.monotonic,
                 now=lambda:datetime.now(timezone.utc), boottime=m.boot_ns, identity=m.process_identity,db_path=None):
        self.enabled = os.environ.get('WEB_ADMIN_DB_SERVICES_ENABLED','false') == 'true' if enabled is None else enabled is True
        self.channel, self.monotonic, self.now, self.boottime, self.identity = channel, monotonic, now, boottime, identity
        self.last_attempt, self.sequence, self.epoch = None, 0, str(uuid.uuid4())
        self.db_path=db_path
        self.lock = threading.Lock()

    def publish(self, health, times, cancel):
        if not self.enabled or cancel.is_set() or not self.lock.acquire(blocking=False):return False
        folder = fd = name = None
        try:
            tick = self.monotonic()
            if self.last_attempt is not None and tick-self.last_attempt < m.INTERVAL:return False
            self.last_attempt = tick; deadline = tick+m.BUDGET
            channel = self.channel(); m.require(os.geteuid() == channel.uid)
            folder = channel.open(); self.sequence += 1
            value = dict(schema_version=SCHEMA,producer_unit=NI02_UNIT,producer=self.identity(os.getpid(),channel.uid),
                epoch=self.epoch,sequence=self.sequence,sample_time_utc=m.stamp(self.now()),sample_boottime_ns=self.boottime(),
                provenance=PROVENANCE,application_health=health,**times)
            from app.operations_verification import snapshot
            checks=snapshot(NI02_UNIT,refresh=True,paths={'network_metadata_projection':self.db_path})
            if checks['checks']:value.update(schema_version=SCHEMA_V2,store_checks=checks)
            raw = json.dumps(value,allow_nan=False,ensure_ascii=True,separators=(',',':')).encode('ascii');decode(raw)
            try:
                info = os.stat(REPORT,dir_fd=folder,follow_symlinks=False);channel.validate_file(info)
                m.require(info.st_dev == os.fstat(folder).st_dev)
            except FileNotFoundError:pass
            m.require(not cancel.is_set() and self.monotonic() < deadline)
            name = '.health-'+uuid.uuid4().hex
            fd = os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,0o600,dir_fd=folder)
            channel.validate_file(os.fstat(fd));m.require(os.write(fd,raw) == len(raw))
            os.close(fd);fd = None
            m.require(not cancel.is_set() and self.monotonic() < deadline)
            os.replace(name,REPORT,src_dir_fd=folder,dst_dir_fd=folder);name = None
            return True
        except Exception:return False
        finally:
            if fd is not None:
                try:os.close(fd)
                except OSError:pass
            if name is not None and folder is not None:
                try:os.unlink(name,dir_fd=folder)
                except OSError:pass
            if folder is not None:
                try:os.close(folder)
                except OSError:pass
            self.lock.release()


class HealthReader:
    def __init__(self, *, channel=configured_channel, boottime=m.boot_ns, identity=m.process_identity):
        self.channel, self.boottime, self.identity, self.last = channel, boottime, identity, None

    def read(self,service,now,*,deadline,monotonic=time.monotonic,cancel=None):
        folder = fd = None
        try:
            m.require(monotonic() < deadline and not (cancel and cancel.is_set()))
            m.require(service['operational_state'] == 'running' and service['main_pid'] is not None)
            channel = self.channel();folder = channel.open()
            fd = os.open(REPORT,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,dir_fd=folder)
            before = os.fstat(fd);channel.validate_file(before)
            m.require(before.st_dev == os.fstat(folder).st_dev)
            raw = os.read(fd,m.LIMIT+1);after = os.fstat(fd);channel.validate_file(after)
            m.require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns) ==
                (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns))
            current = os.stat(REPORT,dir_fd=folder,follow_symlinks=False);channel.validate_file(current)
            m.require((before.st_dev,before.st_ino) == (current.st_dev,current.st_ino) and len(raw) == before.st_size)
            value = decode(raw);producer = self.identity(service['main_pid'],channel.uid)
            m.require(value['producer'] == producer)
            m.require(value['sample_boottime_ns'] >= producer['start_ticks']*1_000_000_000//os.sysconf('SC_CLK_TCK'))
            sampled = m.parse_stamp(value['sample_time_utc'])
            m.require(sampled >= datetime.fromisoformat(service['started_at_utc'].replace('Z','+00:00')))
            checks=value.get('store_checks')
            if checks is not None:
                start=datetime.fromisoformat(service['started_at_utc'].replace('Z','+00:00'))
                m.require(all(row['checked_at_utc'] is None or m.parse_stamp(row['checked_at_utc'])>=start for row in checks['checks'].values()))
            age=(now-sampled).total_seconds();boot_age=(self.boottime()-value['sample_boottime_ns'])/1e9
            m.require(age >= 0 and boot_age >= 0 and abs(age-boot_age) <= 5)
            sha=hashlib.sha256(raw).digest()
            if self.last is not None and self.last[0] == producer:
                m.require(value['epoch'] == self.last[1] and value['sequence'] >= self.last[2]
                    and sampled >= self.last[4] and value['sample_boottime_ns'] >= self.last[5])
                if value['sequence'] == self.last[2]:m.require(sha == self.last[3])
            m.require(monotonic() < deadline and not (cancel and cancel.is_set()))
            if max(age,boot_age) > m.TTL:return dict(status='stale',reason='report_stale',
                **({'checks':checks,'producer':producer} if checks is not None else {}))
            self.last=producer,value['epoch'],value['sequence'],sha,sampled,value['sample_boottime_ns']
            return dict(status='fresh',health=value['application_health'],observed_at=value['sample_time_utc'],
                age=max(age,boot_age),producer=producer,expires_boottime_ns=value['sample_boottime_ns']+int(m.TTL*1e9),
                **({'checks':checks} if checks is not None else {}))
        except Exception:return dict(status='unknown',reason='report_unavailable')
        finally:
            if fd is not None:
                try:os.close(fd)
                except OSError:pass
            if folder is not None:
                try:os.close(folder)
                except OSError:pass
