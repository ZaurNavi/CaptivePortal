"""Root-controlled one-file tmpfs promotion and descriptor-bound RO T3."""
import ctypes
import hashlib
import os
from pathlib import Path
import sqlite3
import stat

from . import contracts as c
from .live_policy import require,integer
from .live_receipts import identity,filesystem_magic,directory
from .r4_sandbox import TMPFS_MAGIC


def digest_fd(fd,maximum):
    before=os.fstat(fd)
    require(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<before.st_size<=maximum,'unsafe_path')
    digest=hashlib.sha256();offset=0
    while offset<before.st_size:
        raw=os.pread(fd,min(1024**2,before.st_size-offset),offset)
        require(bool(raw),'unsafe_path');digest.update(raw);offset+=len(raw)
    after=os.fstat(fd)
    require((identity(before),before.st_size,before.st_mtime_ns,before.st_ctime_ns)==
        (identity(after),after.st_size,after.st_mtime_ns,after.st_ctime_ns),'unsafe_path')
    return dict(device=before.st_dev,inode=before.st_ino,size=before.st_size,sha256=digest.hexdigest())


def promote(job,policy,worker_gid,*,helper):
    from .r4_release import Child
    require(type(helper) is Child and helper.reaped()==0 and os.geteuid()==0,'orphan_hold');job.check()
    require(set(os.listdir(job.stage))=={'snapshot.sqlite3'},'orphan_hold')
    stage=os.open(job.stage,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    final=os.open(job.final,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    fd=None
    try:
        require(filesystem_magic(stage)==filesystem_magic(final)==TMPFS_MAGIC,'unsafe_path')
        fd=os.open('snapshot.sqlite3',os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=stage)
        before=digest_fd(fd,policy.image_max_bytes)
        header=os.pread(fd,100,0)
        # Online Backup copies WAL header modes too. A complete closed image
        # can legitimately contain 02/02 without requiring any WAL sidecar;
        # immutable reopen + full T3 proves its own self-contained pages.
        require(len(header)==100 and header[:16]==b'SQLite format 3\0'
            and header[18:20] in {b'\1\1',b'\2\2'},'unsafe_path')
        os.fchown(fd,0,worker_gid);os.fchmod(fd,0o440)
        # No overwrite fallback and no cross-filesystem copy/link promotion.
        libc=ctypes.CDLL(None,use_errno=True)
        require(libc.renameat2(stage,b'snapshot.sqlite3',final,b'snapshot.sqlite3',1)==0,'unsafe_path')
        info=os.stat('snapshot.sqlite3',dir_fd=final,follow_symlinks=False)
        require(identity(info)==(before['device'],before['inode']) and info.st_nlink==1,'unsafe_path')
        require(digest_fd(fd,policy.image_max_bytes)==before,'unsafe_path')
        output=fd;fd=None
        return output,before
    finally:
        if fd is not None:os.close(fd)
        os.close(stage);os.close(final)


def validate(fd,location,receipt,policy,guard):
    """Final frozen snapshot ONLY. URI is never constructed from source path."""
    from .live_sqlite import validate_snapshot
    import fcntl
    c.closed(receipt,{'device','inode','size','sha256'})
    integer(receipt['device']);integer(receipt['inode'],1);integer(receipt['size'],1);c.digest(receipt['sha256'])
    require(fcntl.fcntl(fd,fcntl.F_GETFL)&os.O_ACCMODE==os.O_RDONLY,'unauthorized')
    parent=directory(str(Path(location).parent),uid=0);db=None
    try:
        info=os.fstat(parent)
        require(info.st_uid==0 and not info.st_mode&0o022 and filesystem_magic(parent)==TMPFS_MAGIC,'unsafe_path')
        def pinned():
            guard();metadata=os.stat(location,follow_symlinks=False)
            require(stat.S_ISREG(metadata.st_mode) and metadata.st_uid==0 and metadata.st_nlink==1
                and stat.S_IMODE(metadata.st_mode)==0o440 and not os.access(location,os.W_OK,effective_ids=True)
                and identity(metadata)==(receipt['device'],receipt['inode']),'unsafe_path')
            require(digest_fd(fd,policy.image_max_bytes)==receipt,'unsafe_path')
        pinned()
        db=sqlite3.connect(Path(location).as_uri()+'?mode=ro&immutable=1',uri=True,isolation_level=None,timeout=0)
        db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON');db.execute('PRAGMA foreign_keys=ON')
        db.set_progress_handler(lambda:(guard(),0)[1],1000)
        pinned()  # Correlate pathname before/after the native SQLite open.
        result=validate_snapshot(db,policy,guard)
        db.close();db=None;pinned()
        return result
    finally:
        if db is not None:db.close()
        os.close(parent)
