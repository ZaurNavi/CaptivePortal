"""R4 Linux-only mount primitives. No source DB open, CLI or global setup.

Call only in a dedicated job mount namespace after independent gate admission.
The root launcher is trusted; source-owner is not given a host directory FD or
a host /proc view inside its chroot. Never mount anything in the host namespace.
"""
from __future__ import annotations

import ctypes
import errno
import os
import re
from pathlib import Path
import stat

from .live_policy import integer,path,require
from .live_receipts import directory,identity

CLONE_NEWNS=0x00020000
MS_RDONLY=1
MS_NOSUID=2
MS_NODEV=4
MS_NOEXEC=8
MS_REMOUNT=32
MS_BIND=4096
MS_REC=16384
MS_PRIVATE=1<<18
TMPFS_MAGIC=0x01021994
RAM_ROOT='/run/captive-portal/db-audit/ram-jobs'


def _libc():return ctypes.CDLL(None,use_errno=True)


def _call(name,*args):
    require(os.name=='posix' and os.geteuid()==0,'unauthorized')
    if getattr(_libc(),name)(*args)!=0:
        raise OSError(ctypes.get_errno(),'r4_kernel_denied')


def mount(source,target,kind=None,flags=0,data=None):
    def raw(value):return None if value is None else os.fsencode(value)
    _call('mount',raw(source),raw(target),raw(kind),ctypes.c_ulong(flags),raw(data))


class MountNamespace:
    """Enter once; restore the pinned original namespace, never lazy-unmount."""
    def __init__(self):self.original=None;self.current=None
    def enter(self):
        require(self.original is None,'not_admitted')
        self.original=os.open('/proc/self/ns/mnt',os.O_RDONLY|os.O_CLOEXEC)
        try:
            old=identity(os.fstat(self.original))
            _call('unshare',CLONE_NEWNS)
            self.current=identity(os.stat('/proc/self/ns/mnt'))
            require(self.current!=old,'not_admitted')
            mount(None,'/',flags=MS_REC|MS_PRIVATE)
            return self
        except Exception:
            self.restore();raise
    def check(self):
        require(self.current is not None and identity(os.stat('/proc/self/ns/mnt'))==self.current,'unsafe_path')
    def restore(self):
        if self.original is not None:
            fd=self.original
            try:_call('setns',fd,CLONE_NEWNS)
            finally:os.close(fd);self.original=None;self.current=None


def mount_record(target):
    """Exact pathname with no mountinfo escape/alias ambiguity."""
    path(str(target));matches=[]
    with open('/proc/self/mountinfo',encoding='ascii') as stream:
        for line in stream:
            before,separator,after=line.partition(' - ')
            fields=before.split();tail=after.split()
            require(separator and len(fields)>=6 and len(tail)==3,'not_admitted')
            if fields[4]==str(target):matches.append((fields,tail))
    require(len(matches)==1,'unsafe_path')
    return matches[0]


def limits(tail,size,inodes):
    options={}
    for item in tail[2].split(','):
        key,separator,value=item.partition('=')
        require(key not in options,'not_admitted');options[key]=value if separator else None
    raw=options.get('size','')
    match=re.fullmatch(r'([0-9]+)([kmg]?)',raw)
    require(match is not None and options.get('nr_inodes')==str(inodes),'not_admitted')
    actual=int(match[1])*{'':1,'k':1024,'m':1024**2,'g':1024**3}[match[2]]
    # Kernel rounds mount size to a whole page. Profiles must be page-aligned;
    # never admit a silently larger image filesystem.
    require(actual==size,'not_admitted')


def _root_directory(target,mode):
    target.mkdir(mode=mode)
    target.chmod(mode)
    fd=directory(str(target),uid=0)
    try:require(os.fstat(fd).st_uid==0 and stat.S_IMODE(os.fstat(fd).st_mode)==mode,'unsafe_path')
    finally:os.close(fd)


class PrivateTmpfs:
    """One root-controlled mount, stage/final dirs on that SAME finite tmpfs.

    Private _base is a disposable native-test seam; production launcher supplies
    only the fixed RAM_ROOT whose root-owned preprovisioned inode is qualified.
    """
    def __init__(self,namespace,epoch,attempt,size,inodes,owner_uid,owner_gid,worker_gid,*,_base=RAM_ROOT):
        from . import contracts as c
        c.identifier(epoch);c.identifier(attempt);integer(size,4096);integer(inodes,16,256)
        integer(owner_uid,1,2**32-1);integer(owner_gid,1,2**32-1);integer(worker_gid,1,2**32-1)
        namespace.check();self.namespace=namespace;self.mounts=[];self.mounted=False
        self.base=Path(_base);self.epoch=self.base/epoch;self.root=self.epoch/attempt
        fd=directory(str(self.base),uid=0)
        try:require(os.fstat(fd).st_uid==0 and not os.fstat(fd).st_mode&0o022,'unsafe_path')
        finally:os.close(fd)
        # Never adopt an existing attempt or mount. Epoch directory is shared
        # only among reviewed attempts, but never writable by either worker.
        try:_root_directory(self.epoch,0o711)
        except FileExistsError:
            fd=directory(str(self.epoch),uid=0)
            try:require(os.fstat(fd).st_uid==0 and stat.S_IMODE(os.fstat(fd).st_mode)==0o711,'unsafe_path')
            finally:os.close(fd)
        _root_directory(self.root,0o711)
        try:
            mount('tmpfs',str(self.root),'tmpfs',MS_NOSUID|MS_NODEV|MS_NOEXEC,
                f'size={size},nr_inodes={inodes},mode=0711')
            self.mounted=True
            fields,tail=mount_record(self.root)
            require(tail[0]=='tmpfs' and {'rw','nosuid','nodev','noexec'}<=set(fields[5].split(',')),'not_admitted')
            limits(tail,size,inodes)
            self.stamp=identity(self.root.stat());self.size=size;self.inodes=inodes
            self.stage=self.root/'stage';_root_directory(self.stage,0o300)
            os.chown(self.stage,owner_uid,owner_gid)
            self.final=self.root/'final';_root_directory(self.final,0o750)
            os.chown(self.final,0,worker_gid)
            self.owner_root=self.root/'owner-root';_root_directory(self.owner_root,0o755)
        except Exception:
            self.cleanup();raise
    def check(self):
        self.namespace.check()
        require(self.mounted and identity(self.root.stat())==self.stamp,'unsafe_path')
        fields,tail=mount_record(self.root)
        require(tail[0]=='tmpfs' and {'nosuid','nodev','noexec'}<=set(fields[5].split(',')),'unsafe_path')
        limits(tail,self.size,self.inodes)
    def bind(self,source_fd,target,*,writable=False,is_directory=False,code=False):
        self.check();target=Path(target)
        require(self.owner_root in target.parents,'unsafe_path')
        if is_directory:_root_directory(target,0o755)
        else:
            fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o400)
            os.close(fd)
        expected=identity(os.fstat(source_fd))
        mount('/proc/self/fd/'+str(source_fd),str(target),flags=MS_BIND)
        self.mounts.append(target)
        flags=MS_BIND|MS_REMOUNT|MS_NOSUID|MS_NODEV|(0 if code else MS_NOEXEC)|(0 if writable else MS_RDONLY)
        mount(None,str(target),flags=flags)
        fields,_=mount_record(target)
        require(identity(target.stat())==expected and ('rw' if writable else 'ro') in fields[5].split(','),'unsafe_path')
    def source_view(self,source_fds):
        """Only three exact native files; no origin parent, /proc or host root."""
        require(set(source_fds) in ({'main'},{'main','wal','shm'}),'not_admitted')
        source=self.owner_root/'source';_root_directory(source,0o555)
        for kind,fd in source_fds.items():
            info=os.fstat(fd)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink==1,'unsafe_path')
            suffix={'main':'','wal':'-wal','shm':'-shm'}[kind]
            self.bind(fd,source/('input.sqlite3'+suffix))
        stage_fd=os.open(self.stage,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:self.bind(stage_fd,self.owner_root/'stage',writable=True,is_directory=True)
        finally:os.close(stage_fd)
        # No host /proc, home, dev, opt, writable directory or origin path is
        # made visible. The already-imported helper uses read-only regular
        # proc receipt FDs, never an escaping directory FD.
    def cleanup(self):
        self.namespace.check()
        # Strict reverse mount order; never MNT_DETACH, rm -rf or path globs.
        for target in reversed(self.mounts):_call('umount2',os.fsencode(target),0)
        self.mounts=[]
        if self.mounted:
            # Caller must close/reap helpers/validators and explicitly remove
            # its known stage/final files first. Residual files prohibit cleanup.
            for name in ('stage','final'):
                folder=getattr(self,name,None)
                require(folder is None or not any(folder.iterdir()),'orphan_hold')
            _call('umount2',os.fsencode(self.root),0);self.mounted=False
        self.root.rmdir()


def drop_owner(uid,gid):
    """After trusted chroot/setup, before ANY SQLite source I/O."""
    integer(uid,1,2**32-1);integer(gid,1,2**32-1)
    _call('prctl',38,1,0,0,0)  # PR_SET_NO_NEW_PRIVS
    _call('prctl',47,4,0,0,0)  # PR_CAP_AMBIENT_CLEAR_ALL
    for capability in range(64):
        try:_call('prctl',24,capability,0,0,0)  # PR_CAPBSET_DROP
        except OSError as error:
            if error.errno!=errno.EINVAL:raise
    os.setgroups([]);os.setresgid(gid,gid,gid);os.setresuid(uid,uid,uid)
    require(os.getresuid()==(uid,uid,uid) and os.getresgid()==(gid,gid,gid) and os.getgroups()==[],'unauthorized')
