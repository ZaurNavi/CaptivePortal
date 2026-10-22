"""Bounded mode=ro source -> :memory: Online Backup. No source repair/writes.

SOURCE/WAL identities are checked around each operation. Native RO sidecars
must already exist for WAL sources; read-only worker credentials cannot create
or write them. Concurrent writer growth is allowed but bounded, never confused
with audit writes or a fixed preflight watermark. No immutable=1/disk fallback.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sqlite3
import stat
import time
from contextlib import contextmanager

from . import contracts as c
from .live_policy import StorePolicy, integer, require
from .locks import protected_parent


class AuditFailure(Exception):
    """Completed RAM image failed logical T3; contains no source payload."""


T3_CHECKS=frozenset({'unreported','unexpected','resource_guard','snapshot_pinned','image_digest',
    'sqlite_open','sqlite_user_version','sqlite_integrity','sqlite_foreign_key','snapshot_metadata','t3_complete',
    'pt_schema_signature','pt_counter_singleton','pt_traffic_daily_date','pt_traffic_daily_numeric',
    'pt_event_type','pt_event_offset_order','pt_event_counted_fields','pt_event_event_date',
    'pt_reader_offset','pt_reader_flags','pt_reset_scope','pt_reset_numeric','pt_watermark_encode',
    'tp_canonical_deep','tp_schema_signature','tp_versions','tp_site_state','tp_cycles','tp_ap_cycles',
    'fingerprint_validate','service_intelligence_validate'})
T3_STAGES=frozenset({'image_handoff','image_open','integrity_check','foreign_key_check',
    'adapter_validate','image_digest_final','complete'})
T3_TIMINGS=('integrity_check_ms','foreign_key_check_ms','adapter_validate_ms','image_digest_final_ms')
T3_EXCEPTIONS=frozenset({'none','unknown','CoordinatorError','AuditFailure','OperationalError','DatabaseError',
    'IntegrityError','ProgrammingError','ValueError','TypeError','OSError','PermissionError','FileNotFoundError',
    'RuntimeError','MemoryError','TimeoutError','InterruptedError','OverflowError','ImportError','ModuleNotFoundError'})
T3_CATEGORIES=frozenset({'none','domain','resource_guard','snapshot_tamper','unexpected'})


def validate_t3_diagnostic(value):
    c.closed(value,{'check','stage','category','exception_class','guard_fast_count','digest_full_count',
        'digest_bytes_verified','progress_callbacks','elapsed_ms',*T3_TIMINGS})
    require(value['check'] in T3_CHECKS and value['stage'] in T3_STAGES
        and value['category'] in T3_CATEGORIES and value['exception_class'] in T3_EXCEPTIONS,'unauthorized')
    for key in ('guard_fast_count','progress_callbacks'):integer(value[key],0,100000)
    integer(value['digest_full_count'],0,3);integer(value['digest_bytes_verified'],0,3*2**31)
    for key in ('elapsed_ms',*T3_TIMINGS):integer(value[key],0,5400000)
    return value


class T3Trace:
    """One fixed-size private attempt summary; never an authority or row log."""
    def __init__(self,clock=time.monotonic_ns):
        self.clock=clock;self.started=clock();self.check='unreported';self.stage='image_handoff'
        self.category='none';self.exception_class='none'
        self.counts=dict(guard_fast_count=0,digest_full_count=0,digest_bytes_verified=0,progress_callbacks=0)
        self.timings=dict.fromkeys(T3_TIMINGS,0)

    def mark(self,check):
        require(check in T3_CHECKS,'invalid_request');self.check=check

    def count(self,key,amount=1):
        bounds=dict(guard_fast_count=100000,digest_full_count=3,digest_bytes_verified=3*2**31,progress_callbacks=100000)
        self.counts[key]=min(bounds[key],self.counts[key]+amount)

    def fail(self,error,category):
        # An SQLite progress callback wraps exceptions as 'interrupted'. Keep
        # the actual guard classification, not an invented domain corruption.
        if self.category!='none':return
        self.category=category
        name=type(error).__name__;self.exception_class=name if name in T3_EXCEPTIONS else 'unknown'

    @contextmanager
    def phase(self,stage,check):
        require(stage in T3_STAGES,'invalid_request')
        self.stage=stage;self.mark(check);started=self.clock()
        try:yield
        finally:
            key=stage+'_ms'
            if key in self.timings:self.timings[key]=min(5400000,(self.clock()-started)//1000000)

    def document(self):
        return validate_t3_diagnostic(dict(check=self.check,stage=self.stage,category=self.category,
            exception_class=self.exception_class,elapsed_ms=min(5400000,max(0,(self.clock()-self.started)//1000000)),
            **self.counts,**self.timings))


def file_identity(path, policy, *, main=False):
    protected_parent(path,policy.uid)
    before=path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_uid==policy.uid
        and before.st_gid==policy.gid and not before.st_mode & 0o022, 'unsafe_path')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK)
    try:
        after=os.fstat(fd)
        require((before.st_dev,before.st_ino)==(after.st_dev,after.st_ino), 'unsafe_path')
        if main: require((after.st_dev,after.st_ino)==(policy.device,policy.inode), 'unsafe_path')
        return after.st_dev,after.st_ino,after.st_size
    finally: os.close(fd)


def inspect_source(policy):
    require(type(policy) is StorePolicy)
    path=Path(policy.source)
    main=file_identity(path,policy,main=True)
    require(0<main[2]<=policy.source_max_bytes)
    sides={}
    for suffix in ('-wal','-shm','-journal'):
        target=Path(str(path)+suffix)
        try: sides[suffix]=file_identity(target,policy)
        except FileNotFoundError: sides[suffix]=None
    require(sides['-journal'] is None or sides['-journal'][2]==0)
    require(sides['-wal'] is None or sides['-wal'][2]<=policy.wal_max_bytes)
    require(sides['-shm'] is None or sides['-shm'][2]<=policy.backup_overhead_bytes)
    return main,sides


def metadata(db):
    page_size=db.execute('PRAGMA page_size').fetchone()[0]
    page_count=db.execute('PRAGMA page_count').fetchone()[0]
    integer(page_size,512,65536); integer(page_count,1)
    require(page_size & (page_size-1)==0)
    return page_size,page_count


def validate_snapshot(db, policy, guard, *, trace=None):
    trace=trace or T3Trace()
    check=trace.mark
    check('sqlite_user_version')
    require(db.execute('PRAGMA user_version').fetchone()[0]==policy.schema_version)
    count=0
    with trace.phase('integrity_check','sqlite_integrity'):
        for row in db.execute('PRAGMA integrity_check'):
            guard(); count+=1; require(tuple(row)==('ok',))
        require(count==1)
    with trace.phase('foreign_key_check','sqlite_foreign_key'):
        require(db.execute('PRAGMA foreign_key_check').fetchone() is None)
    with trace.phase('adapter_validate','unexpected'):
        if policy.store_id=='fingerprint_evidence':
            from app.device_fingerprint.audit_runner import validate_snapshot as fingerprint_t3
            from app.device_fingerprint.repository import DeviceFingerprintRepository
            check('fingerprint_validate');fingerprint_t3(db,guard)
            mark=DeviceFingerprintRepository.read_ingest_watermark(db)
            c.identifier(mark['database_generation_id'])
            kind='native_lineage'; lineage=hashlib.sha256(mark['database_generation_id'].encode()).hexdigest()
            watermark=hashlib.sha256(c.encode(mark)).hexdigest()
        else:
            if policy.store_id=='public_traffic':
                from .adapter_public_traffic import validate
                kind,lineage,watermark=validate(db,guard,check=check)
            elif policy.store_id=='traffic_projection':
                from .adapter_traffic_projection import validate
                kind,lineage,watermark=validate(db,guard,check=check)
            elif policy.store_id=='network_service_intelligence':
                from .adapter_service_intelligence import validate
                check('service_intelligence_validate');kind,lineage,watermark=validate(db,guard)
            else: raise c.CoordinatorError('not_admitted')
    check('snapshot_metadata')
    size,count=metadata(db)
    return dict(schema_version=policy.schema_version,generation_kind=kind,lineage_sha256=lineage,
        watermark_sha256=watermark,page_size=size,page_count=count)


def audit(policy, guard, admit, *, after_backup=None):
    """Caller must own global flock and verified containment BEFORE this call.

    guard rechecks deadline/cancel/local memory/lock/identity during backup/T3.
    admit receives exact page/WAL geometry before allocating the only RAM image.
    after_backup is a private in-process unit-test seam, never a public selector.
    """
    source=destination=None
    baseline=None
    def same_source():
        fresh=inspect_source(policy)
        require(fresh[0][:2]==baseline[0][:2], 'unsafe_path')
        for suffix in ('-wal','-shm'):
            old,new=baseline[1][suffix],fresh[1][suffix]
            require((old is None)==(new is None) and (old is None or old[:2]==new[:2]), 'unsafe_path')
        return fresh
    try:
        guard(); baseline=inspect_source(policy)
        # Detect WAL before SQLite is opened, so missing sidecars cannot be
        # auto-created by an accidentally writable test/setup identity.
        fd=os.open(policy.source,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try: header=os.read(fd,100)
        finally: os.close(fd)
        require(len(header)==100 and header[:16]==b'SQLite format 3\x00')
        if header[18:20]==b'\x02\x02':
            require(baseline[1]['-wal'] is not None and baseline[1]['-shm'] is not None)
        source=sqlite3.connect(Path(policy.source).as_uri()+'?mode=ro',uri=True,timeout=0,isolation_level=None)
        source.row_factory=sqlite3.Row
        source.execute('PRAGMA query_only=ON'); source.execute('PRAGMA foreign_keys=ON')
        source.execute('PRAGMA busy_timeout=0')
        journal=source.execute('PRAGMA journal_mode').fetchone()[0].lower()
        require(journal in {'wal','delete'})
        if journal=='wal': require(baseline[1]['-wal'] is not None and baseline[1]['-shm'] is not None)
        same_source()
        size,count=metadata(source); require(size*count<=policy.image_max_bytes)
        require(source.execute('PRAGMA user_version').fetchone()[0]==policy.schema_version)
        wal=baseline[1]['-wal'][2] if baseline[1]['-wal'] else 0
        admit(size*count,wal)
        destination=sqlite3.connect(':memory:',isolation_level=None)
        destination.row_factory=sqlite3.Row
        destination.execute(f'PRAGMA page_size={size}'); destination.execute('PRAGMA foreign_keys=ON')
        destination.execute('PRAGMA temp_store=MEMORY')
        completed=False; restarts=0; previous=None; steps=0
        def progress(code, remaining, total):
            nonlocal completed,restarts,previous,steps
            guard(); steps+=1
            require(code in {0,101} and type(total) is int and total>0 and total*size<=policy.image_max_bytes)
            require(type(remaining) is int and 0<=remaining<=total)
            if previous is not None and remaining>previous: restarts+=1
            require(restarts<=8 and steps<=100000)
            previous=remaining; completed=code==101 and remaining==0
            fresh=same_source(); admit(total*size, fresh[1]['-wal'][2] if fresh[1]['-wal'] else 0)
        source.backup(destination,pages=128,progress=progress,sleep=0)
        require(completed)
        if after_backup is not None: after_backup(destination)
        same_source(); guard()
        destination.execute('PRAGMA query_only=ON')
        def interrupt():
            try: guard(); return 0
            except Exception: return 1
        destination.set_progress_handler(interrupt,10000)
        try:
            result=validate_snapshot(destination,policy,guard)
        except Exception:
            # Cancellation/resource/deadline failures are not corruption verdicts.
            guard()
            raise AuditFailure() from None
        same_source(); guard()
        return result
    finally:
        if destination is not None: destination.close()
        if source is not None: source.close()
