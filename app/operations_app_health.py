"""Tiny same-admin in-memory owner health transport. No startup checks or probes.

Only Phase A owners; file evidence is self-reported, never an authorization or
independent attestation. Reuses the already-provisioned secure tmpfs channels.
"""
import hashlib
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone

from app.device_fingerprint_sensor import operations_metadata as m
from app.operations_verification_report import configured_channel
from app.operations_health import OWNER_UNITS, validate_owner

SCHEMA = "captivprod.ops.owner-app-health.v1"
REPORT = "app-health.json"
PROVENANCE = "source_self_reported_shared_uid"


def decode(raw, unit):
    m.require(unit in OWNER_UNITS and type(raw) is bytes and 0 < len(raw) <= m.LIMIT)
    def pairs(items):
        result = {}
        for key, value in items:
            m.require(key not in result); result[key] = value
        return result
    def invalid(_):raise m.MetadataUnavailable()
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid)
    m.require(type(value) is dict and set(value) == {'schema_version', 'producer_unit', 'producer',
        'epoch', 'sequence', 'sample_time_utc', 'sample_boottime_ns', 'application_health'})
    m.require(value['schema_version'] == SCHEMA and value['producer_unit'] == unit)
    producer = value['producer']
    m.require(type(producer) is dict and set(producer) == {'boot_id', 'pid', 'start_ticks'})
    for item in (producer['boot_id'], value['epoch']):
        m.require(type(item) is str and str(uuid.UUID(item)) == item)
    m.require(m.integer(producer['pid'], 2**31-1, 1) and m.integer(producer['start_ticks'], minimum=1)
        and m.integer(value['sequence'], minimum=1) and m.integer(value['sample_boottime_ns'], 2**63-1))
    m.parse_stamp(value['sample_time_utc'])
    validate_owner(value['application_health'], unit)
    return value


def _stamp(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns,
        info.st_uid, info.st_gid, info.st_mode, info.st_nlink)


class HealthPublisher:
    def __init__(self, unit, *, enabled=None, channel=configured_channel, monotonic=time.monotonic,
                 now=lambda: datetime.now(timezone.utc), boottime=m.boot_ns, identity=m.process_identity):
        m.require(unit in OWNER_UNITS)
        self.unit, self.channel, self.monotonic, self.now = unit, channel, monotonic, now
        self.boottime, self.identity = boottime, identity
        self.enabled = os.environ.get('WEB_ADMIN_DB_SERVICES_ENABLED', 'false') == 'true' if enabled is None else enabled is True
        self.epoch, self.sequence, self.pid = str(uuid.uuid4()), 0, os.getpid()
        self.last_attempt = self.last_health = None
        self.lock = threading.Lock()

    def publish(self, health, *, force=False):
        if not self.enabled or not self.lock.acquire(blocking=False):return False
        folder = fd = name = None
        try:
            validate_owner(health, self.unit)
            pid = os.getpid(); tick = self.monotonic()
            if pid != self.pid:
                self.pid, self.epoch, self.sequence = pid, str(uuid.uuid4()), 0
                self.last_attempt = self.last_health = None
            # Idle renewals every 60s; state transitions at most once per second.
            interval = m.INTERVAL if health == self.last_health else 1.0
            if not force and self.last_attempt is not None and tick-self.last_attempt < interval:return False
            self.last_attempt, self.last_health = tick, dict(health)
            deadline = tick + m.BUDGET
            source = self.channel(self.unit); m.require(os.geteuid() == source.uid)
            folder = source.open(); sequence = self.sequence + 1
            value = dict(schema_version=SCHEMA, producer_unit=self.unit, producer=self.identity(pid, source.uid),
                epoch=self.epoch, sequence=sequence, sample_time_utc=m.stamp(self.now()),
                sample_boottime_ns=self.boottime(), application_health=health)
            raw = json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(',', ':')).encode('ascii')
            decode(raw, self.unit)
            try:
                info = os.stat(REPORT, dir_fd=folder, follow_symlinks=False); source.validate_file(info)
                m.require(info.st_dev == os.fstat(folder).st_dev)
            except FileNotFoundError:pass
            m.require(self.monotonic() < deadline)
            name = '.app-health-' + uuid.uuid4().hex
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                0o600, dir_fd=folder)
            source.validate_file(os.fstat(fd)); m.require(os.write(fd, raw) == len(raw))
            os.close(fd); fd = None
            m.require(self.monotonic() < deadline)
            os.replace(name, REPORT, src_dir_fd=folder, dst_dir_fd=folder); name = None
            self.sequence = sequence
            return True
        except Exception:return False
        finally:
            if fd is not None:
                try:os.close(fd)
                except OSError:pass
            if name is not None and folder is not None:
                try:os.unlink(name, dir_fd=folder)
                except OSError:pass
            if folder is not None:
                try:os.close(folder)
                except OSError:pass
            self.lock.release()


class HealthReader:
    def __init__(self, unit, *, channel=configured_channel, identity=m.process_identity, boottime=m.boot_ns):
        m.require(unit in OWNER_UNITS)
        self.unit, self.channel, self.identity, self.boottime = unit, lambda: channel(unit), identity, boottime
        self.last = None

    def read(self, service, now, *, deadline, monotonic=time.monotonic, cancel=None):
        folder = fd = None
        try:
            m.require(monotonic() < deadline and not (cancel and cancel.is_set())
                and service['operational_state'] == 'running' and service['main_pid'] is not None)
            source = self.channel(); folder = source.open()
            fd = os.open(REPORT, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=folder)
            before = os.fstat(fd); source.validate_file(before)
            m.require(before.st_dev == os.fstat(folder).st_dev)
            raw = os.read(fd, m.LIMIT + 1)
            after = os.fstat(fd); source.validate_file(after)
            current = os.stat(REPORT, dir_fd=folder, follow_symlinks=False); source.validate_file(current)
            m.require(_stamp(before) == _stamp(after) == _stamp(current) and len(raw) == before.st_size)
            value = decode(raw, self.unit); producer = self.identity(service['main_pid'], source.uid)
            m.require(value['producer'] == producer)
            sampled = m.parse_stamp(value['sample_time_utc']); sample_boot = value['sample_boottime_ns']
            m.require(sampled >= datetime.fromisoformat(service['started_at_utc'].replace('Z', '+00:00'))
                and sample_boot >= producer['start_ticks'] * 1_000_000_000 // os.sysconf('SC_CLK_TCK'))
            age = (now-sampled).total_seconds(); boot_age = (self.boottime()-sample_boot)/1e9
            m.require(age >= 0 and boot_age >= 0 and abs(age-boot_age) <= 5)
            sha = hashlib.sha256(raw).digest()
            if self.last is not None and self.last[0] == producer:
                m.require(value['epoch'] == self.last[1] and value['sequence'] >= self.last[2]
                    and sampled >= self.last[4] and sample_boot >= self.last[5])
                if value['sequence'] == self.last[2]:m.require(sha == self.last[3])
            m.require(monotonic() < deadline and not (cancel and cancel.is_set()))
            self.last = producer, value['epoch'], value['sequence'], sha, sampled, sample_boot
            if max(age, boot_age) > m.TTL:return dict(status='stale', reason='report_stale')
            return dict(status='fresh', health=value['application_health'], producer=producer,
                observed_at=value['sample_time_utc'], age=max(age, boot_age),
                expires_boottime_ns=sample_boot + int(m.TTL*1e9))
        except Exception:return dict(status='unknown', reason='report_unavailable')
        finally:
            if fd is not None:
                try:os.close(fd)
                except OSError:pass
            if folder is not None:
                try:os.close(folder)
                except OSError:pass
