"""Root-controlled one-file tmpfs promotion and descriptor-bound RO T3."""
import ctypes
import hashlib
import os
import sqlite3
import stat

from . import contracts as c
from .live_policy import require,integer
from .live_receipts import identity,filesystem_magic,proc_text
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


def final_receipt(fd,worker_gid):
    import fcntl
    flags=fcntl.fcntl(fd,fcntl.F_GETFL);info=os.fstat(fd)
    require(flags&os.O_ACCMODE==os.O_RDONLY and flags&os.O_DIRECTORY and not flags&os.O_PATH
        and stat.S_ISDIR(info.st_mode) and info.st_uid==0 and info.st_gid==worker_gid
        and stat.S_IMODE(info.st_mode)==0o750 and filesystem_magic(fd)==TMPFS_MAGIC,'unsafe_path')
    return dict(device=info.st_dev,inode=info.st_ino,gid=info.st_gid)


def pin_final(job,image_fd,worker_gid):
    """Root derives final FD from THIS authenticated job, not a client path."""
    require(os.geteuid()==0,'unauthorized');job.check()
    fd=os.open(job.final,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        receipt=final_receipt(fd,worker_gid)
        require(identity(os.stat(job.final,follow_symlinks=False))==identity(os.fstat(fd))
            and identity(os.stat('snapshot.sqlite3',dir_fd=fd,follow_symlinks=False))==identity(os.fstat(image_fd))
            and os.fstat(image_fd).st_dev==receipt['device']
            and set(os.listdir(fd))=={'snapshot.sqlite3'},'unsafe_path')
        return fd,receipt
    except Exception:os.close(fd);raise


def validate(fd,parent,receipt,folder_receipt,policy,guard,*,trace=None):
    """Owns/closes BOTH FDs. Private self-proc directory-FD bridge, no CWD change.

    Native SQLite expands an ordinary relative URI back to an inaccessible
    absolute path. Only the authenticated final DIRECTORY FD + fixed basename
    may bridge that traversal. No image-FD URI, source path or custom VFS.
    """
    from .live_sqlite import T3Trace
    trace=trace or T3Trace()
    db=None;domain_active=False;guard_error=None
    try:
        from .live_sqlite import validate_snapshot
        from .r4_ipc import snapshot_pair
        snapshot_pair((fd,parent))
        c.closed(receipt,{'device','inode','size','sha256'})
        integer(receipt['device']);integer(receipt['inode'],1);integer(receipt['size'],1);c.digest(receipt['sha256'])
        c.closed(folder_receipt,{'device','inode','gid'})
        integer(folder_receipt['device']);integer(folder_receipt['inode'],1);integer(folder_receipt['gid'],1)
        require(os.geteuid()!=0 and final_receipt(parent,os.getegid())==folder_receipt
            and receipt['device']==folder_receipt['device'],'unsafe_path')
        cwd=identity(os.stat('.'))
        # Decimal descriptor comes ONLY from validated SCM_RIGHTS, never input.
        alias='/proc/self/fd/'+str(parent)
        location=alias+'/snapshot.sqlite3'
        def stamp(info):
            return (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid,info.st_nlink,
                info.st_size,info.st_mtime_ns,info.st_ctime_ns)
        image_stamp=stamp(os.fstat(fd));directory_stamp=stamp(os.fstat(parent))
        def pinned_fast():
            trace.count('guard_fast_count')
            try:guard()  # Original deadline/cancel/flock/proc/cgroup resource gate, EVERY time.
            except Exception as error:
                trace.mark('resource_guard');trace.fail(error,'resource_guard');raise
            try:
                own=os.getpid();lines=proc_text(own,'status').splitlines()
                require(os.readlink('/proc/self')==str(own)
                    and [line.split()[1:] for line in lines if line.startswith('NSpid:')]==[[str(own)]]
                    and [line.split()[1:] for line in lines if line.startswith('PPid:')]==[[str(os.getppid())]]
                    and identity(os.stat(alias))==identity(os.fstat(parent))
                    and os.access(alias,os.X_OK,effective_ids=True)
                    and not os.access(alias,os.W_OK,effective_ids=True)
                    and identity(os.stat('.'))==cwd,'unauthorized')
                metadata=os.stat('snapshot.sqlite3',dir_fd=parent,follow_symlinks=False)
                image=os.fstat(fd)
                require(stat.S_ISREG(metadata.st_mode) and metadata.st_uid==0 and metadata.st_nlink==1
                    and metadata.st_gid==os.getegid() and stat.S_IMODE(metadata.st_mode)==0o440
                    and stamp(metadata)==stamp(image)==image_stamp
                    and image.st_size==receipt['size'] and 0<image.st_size<=policy.image_max_bytes
                    and identity(metadata)==(receipt['device'],receipt['inode'])
                    and stamp(os.fstat(parent))==directory_stamp
                    and final_receipt(parent,os.getegid())==folder_receipt
                    and identity(os.stat(location,follow_symlinks=False))==identity(metadata)
                    and set(os.listdir(parent))=={'snapshot.sqlite3'}
                    and not os.access('snapshot.sqlite3',os.W_OK,dir_fd=parent,effective_ids=True),'unsafe_path')
            except Exception as error:
                trace.mark('snapshot_pinned');trace.fail(error,'snapshot_tamper');raise
        def pinned_strong():
            pinned_fast();trace.mark('image_digest');trace.count('digest_full_count')
            require(digest_fd(fd,policy.image_max_bytes)==receipt,'unsafe_path')
            trace.count('digest_bytes_verified',receipt['size']);pinned_fast()
        pinned_strong()  # Initial positive authenticated content handoff.
        trace.stage='image_open';trace.mark('sqlite_open')
        db=sqlite3.connect('file:'+location+'?mode=ro&immutable=1',uri=True,isolation_level=None,timeout=0)
        db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON');db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA temp_store=MEMORY')
        def interrupt():
            nonlocal guard_error
            trace.count('progress_callbacks')
            try:pinned_fast();return 0
            except Exception as error:
                guard_error=error;return 1
        db.set_progress_handler(interrupt,1000)
        pinned_strong()  # Re-correlate topology/content after SQLite open.
        domain_active=True
        try:result=validate_snapshot(db,policy,pinned_fast,trace=trace)
        except Exception:
            if guard_error is not None:raise guard_error from None
            raise
        domain_active=False
        db.close();db=None
        with trace.phase('image_digest_final','image_digest'):
            pinned_strong()  # AFTER SQLite closes, before ANY success receipt.
        trace.stage='complete';trace.mark('t3_complete')
        return result
    except Exception as error:
        if isinstance(error,MemoryError):
            trace.mark('resource_guard');trace.fail(error,'resource_guard')
        elif isinstance(error,ImportError):
            trace.mark('unexpected');trace.fail(error,'unexpected')
        else:trace.fail(error,'domain' if domain_active else 'snapshot_tamper')
        raise
    finally:
        try:
            if db is not None:db.close()
        finally:
            for opened in {fd,parent}:
                try:os.close(opened)
                except OSError:pass  # A rejected closed FD must not leak the other slot.
