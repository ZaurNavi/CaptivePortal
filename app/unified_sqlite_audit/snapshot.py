"""Standard WAL-aware online backup and complete checks on ONE RAM connection.

No provisioning, cross-UID transport, source repair, disk snapshot or audit timeout.
The native guard only INSPECTS containment provisioned by the source owner.
"""
import hashlib
import os
from pathlib import Path
import sqlite3
import stat
import time
import uuid

from app.operations_verification import opaque_identity
from .model import AuditError, bounded, stamp

METHOD = 'sqlite_online_backup_ram_v1'


def generation(path):
    """Opaque freshness observation, NOT an application/SQLite commit generation."""
    metadata=[]
    for suffix in ('','-wal','-shm'):
        try:
            info=os.lstat(str(path)+suffix)
        except FileNotFoundError:
            if not suffix:raise AuditError('source_unavailable') from None
            metadata.append(None);continue
        if not stat.S_ISREG(info.st_mode):raise AuditError('source_unavailable')
        metadata.append((info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns))
    return hashlib.sha256(repr(metadata).encode('ascii')).hexdigest()


def require_identity(job):
    """Keep path/inode rejection independent of ordinary live WAL advancement."""
    path=Path(job.path)
    try:
        if (not path.is_absolute() or path.resolve(strict=True)!=path
                or opaque_identity(path.lstat())!=job.source_id):
            raise AuditError('source_changed')
    except OSError:
        raise AuditError('source_changed') from None


def native_admission(job):
    """Positive Linux RO + cgroup-v2 inspection, not a caller-provided `ro=True`.

    Unknown/unsupported containment fails BEFORE sqlite.connect. This task never
    mounts, creates cgroups, changes ACLs/UIDs or writes kernel controls.
    """
    try:
        if os.name != 'posix' or not hasattr(os,'ST_RDONLY'):
            raise AuditError('resource_unqualified')
        process={line.split(':',1)[0]:line.split(':',1)[1].strip()
                 for line in Path('/proc/self/status').read_text().splitlines() if ':' in line}
        if (int(process['CapEff'],16)!=0 or process['NoNewPrivs']!='1'
                or not os.statvfs('/sys/fs/cgroup').f_flag & os.ST_RDONLY):
            raise AuditError('resource_unqualified')
        if (job.uid != os.geteuid() or job.gid != os.getegid() or not job.no_competing_audit
                or not bounded(job.max_snapshot_bytes,1) or not bounded(job.host_memory_budget_bytes,1)):
            raise AuditError('resource_unqualified')
        path=Path(job.path)
        if not path.is_absolute() or path.resolve(strict=True) != path:
            raise AuditError('source_unavailable')
        info=path.lstat()
        if not stat.S_ISREG(info.st_mode) or opaque_identity(info) != job.source_id:
            raise AuditError('source_changed')
        # mode=ro alone is insufficient. Both family and containing directory
        # must already be on OS read-only mounts (including WAL/SHM).
        for entry in (path.parent,path,*[Path(str(path)+s) for s in ('-wal','-shm') if os.path.lexists(str(path)+s)]):
            if not os.statvfs(entry).f_flag & os.ST_RDONLY:
                raise AuditError('resource_unqualified')
            if entry.is_symlink():raise AuditError('source_unavailable')
        groups=Path('/proc/self/cgroup').read_text(encoding='ascii').splitlines()
        if len(groups)!=1 or not groups[0].startswith('0::/'):
            raise AuditError('resource_unqualified')
        relative=groups[0][3:]
        if relative=='/' or relative!=job.cgroup or '..' in relative.split('/'):
            raise AuditError('resource_unqualified')
        # A cgroup namespace hiding ancestors cannot attest effective limits.
        mounts=[line.split() for line in Path('/proc/self/mountinfo').read_text().splitlines()
                if ' - cgroup2 ' in line]
        if len(mounts)!=1 or mounts[0][3]!='/' or mounts[0][4]!='/sys/fs/cgroup':
            raise AuditError('resource_unqualified')
        root=Path('/sys/fs/cgroup');leaf=root/relative.lstrip('/')
        nodes=[leaf,*[p for p in leaf.parents if p==root or root in p.parents]]
        limits=[];swap_limits=[]
        if int((leaf/'memory.swap.current').read_text())!=0:
            raise AuditError('resource_unqualified')
        for node in nodes:
            for name,target in (('memory.max',limits),('memory.swap.max',swap_limits)):
                file=node/name
                if not file.exists():
                    if node!=root:raise AuditError('resource_unqualified')
                    continue
                text=file.read_text().strip()
                if text!='max':target.append(int(text))
            swap=node/'memory.swap.current'
            if swap.exists() and int(swap.read_text())!=0:
                raise AuditError('resource_unqualified')
        if not limits or min(limits)<=0 or not swap_limits or min(swap_limits)!=0:
            raise AuditError('resource_unqualified')
        # Host reserve is owner-attested in the private qualification, guest
        # headroom and finite effective limit are independently inspected now.
        limit=min(limits)
        current=int((leaf/'memory.current').read_text())
        required=job.max_snapshot_bytes*2+64*1024*1024
        available=int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                           if line.startswith('MemAvailable:')))*1024
        if limit>job.host_memory_budget_bytes or limit-current<required or available<required:
            raise AuditError('resource_unqualified')
        return True
    except (OSError, ValueError, StopIteration, IndexError, KeyError):
        raise AuditError('resource_unqualified') from None


def _read_only_authorizer(action, arg1, arg2, database, trigger):
    if action in {sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ,sqlite3.SQLITE_FUNCTION,
                  sqlite3.SQLITE_RECURSIVE}:
        return sqlite3.SQLITE_OK
    if action==sqlite3.SQLITE_PRAGMA and str(arg1).lower() in {
            'integrity_check','foreign_key_check','user_version','table_info','index_list',
            'index_info','foreign_key_list','page_size','page_count','database_list'} and (arg2 is None or str(arg1).lower() in {
                'table_info','index_list','index_info','foreign_key_list'}):
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


class SourceSnapshotAndT3:
    def __init__(self, *, validators=None, admission=native_admission, cancelled=lambda:False,
                 clock=time.monotonic):
        # Registry supplied explicitly by reviewed owner code, never by JSON or
        # import-string plugins. Same snapshot connection, not a second DB open.
        self.validators=dict(validators or {})
        self.admission=admission
        self.cancelled=cancelled
        self.clock=clock

    def run(self, admitted_store):
        job=admitted_store
        self.admission(job)
        if self.cancelled():raise AuditError('cancelled')
        require_identity(job)
        started=self.clock();before=generation(job.path)
        result=dict(method=METHOD,snapshot_id=str(uuid.uuid4()),snapshot_at=stamp(),verified_at=None,
            physical_verdict='NOT_EVALUATED',domain_verdict='NOT_ADMITTED',integrity=None,fk=None,
            domain_t3='NOT_ADMITTED',reason='domain_validator_absent',duration_ms=None,
            source_generation=None,state='RUNNING',assurance_scope='SNAPSHOT_ONLY',
            source_observation_before=before,source_observation_snapshot=None,source_observation_after=None,
            live_freshness='UNKNOWN',snapshot_receipt=None)
        source=target=None
        try:
            source=sqlite3.connect(Path(job.path).as_uri()+'?mode=ro',uri=True,timeout=0)
            source.set_authorizer(_read_only_authorizer)
            page_size=source.execute('PRAGMA page_size').fetchone()[0]
            target=sqlite3.connect(':memory:')
            target.execute('PRAGMA temp_store=MEMORY')  # RAM checks must not spill temp B-trees to disk.

            def progress(status,remaining,total):
                if self.cancelled():raise AuditError('cancelled')
                if total*page_size>job.max_snapshot_bytes:raise AuditError('resource_unqualified')
                # No time-based correctness cutoff. Cancellation and actual
                # containment failures, not elapsed duration, end a healthy job.

            source.backup(target,pages=32,progress=progress,sleep=0.05)
            source.close();source=None
            require_identity(job)
            result['snapshot_at']=stamp()
            result['source_observation_snapshot']=generation(job.path)
            if self.cancelled():raise AuditError('cancelled')
            target.set_authorizer(_read_only_authorizer)
            target.set_progress_handler(lambda:1 if self.cancelled() else 0,1000)
            count=0;valid=True
            cursor=target.execute('PRAGMA integrity_check')
            try:
                for row in cursor:
                    count+=1;valid=valid and row==('ok',)
            finally:cursor.close()
            result['integrity']='PASS' if valid and count==1 else 'FAIL'
            # Enumerate ALL FK violations; no first-row/fetchone success shortcut.
            count=0;cursor=target.execute('PRAGMA foreign_key_check')
            try:
                for _ in cursor:count+=1
            finally:cursor.close()
            result['fk']='PASS' if count==0 else 'FAIL'
            physical='INTEGRITY_FAIL' if result['integrity']=='FAIL' else 'FK_FAIL' if count else 'PASS'
            result['physical_verdict']=physical
            result['state']='PASSED' if physical=='PASS' else physical
            if physical!='PASS':result['reason']='physical_failed'
            validator=self.validators.get((job.store_id,job.domain_validator_id))
            if physical=='PASS' and validator is not None and job.domain_validator_id is not None:
                try:valid=validator(target) is True
                except Exception:valid=False
                result.update(domain_verdict='PASS' if valid else 'FAIL',domain_t3='PASS' if valid else 'FAIL',
                    state='PASSED' if valid else 'DOMAIN_FAIL',reason='verified' if valid else 'domain_failed')
            if self.cancelled():raise AuditError('cancelled')
            require_identity(job)
            after=generation(job.path)
            result['source_observation_after']=after
            result['live_freshness']=('UNCHANGED_OBSERVATION' if
                before==result['source_observation_snapshot']==after else 'ADVANCED')
        except sqlite3.Error:
            raise AuditError('source_unavailable') from None
        finally:
            if source is not None:source.close()
            if target is not None:target.close()
        result['duration_ms']=max(0,int((self.clock()-started)*1000))
        # Provisional until parent positively reaps worker and all descendants.
        return result
