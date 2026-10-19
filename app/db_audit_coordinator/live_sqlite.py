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

from . import contracts as c
from .live_policy import StorePolicy, integer, require
from .locks import protected_parent


class AuditFailure(Exception):
    """Completed RAM image failed logical T3; contains no source payload."""


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


def validate_snapshot(db, policy, guard):
    require(db.execute('PRAGMA user_version').fetchone()[0]==policy.schema_version)
    count=0
    for row in db.execute('PRAGMA integrity_check'):
        guard(); count+=1; require(tuple(row)==('ok',))
    require(count==1)
    require(db.execute('PRAGMA foreign_key_check').fetchone() is None)
    if policy.store_id=='fingerprint_evidence':
        from app.device_fingerprint.audit_runner import validate_snapshot as fingerprint_t3
        from app.device_fingerprint.repository import DeviceFingerprintRepository
        fingerprint_t3(db,guard)
        mark=DeviceFingerprintRepository.read_ingest_watermark(db)
        c.identifier(mark['database_generation_id'])
        kind='native_lineage'; lineage=hashlib.sha256(mark['database_generation_id'].encode()).hexdigest()
        watermark=hashlib.sha256(c.encode(mark)).hexdigest()
    else:
        if policy.store_id=='public_traffic': from .adapter_public_traffic import validate
        elif policy.store_id=='traffic_projection': from .adapter_traffic_projection import validate
        elif policy.store_id=='network_service_intelligence': from .adapter_service_intelligence import validate
        else: raise c.CoordinatorError('not_admitted')
        kind,lineage,watermark=validate(db,guard)
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
