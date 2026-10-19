"""One protected JSON writer. File+directory fsync is the only commit point."""
from __future__ import annotations

import os
from pathlib import Path
import stat
import uuid

from . import contracts as c
from .locks import protected_parent, trusted_open


def read_json(path, uid, identity=None):
    descriptor = trusted_open(path,uid,identity=identity)
    with os.fdopen(descriptor,"rb") as handle:
        raw = handle.read(c.MAX_BYTES+1)
    return c.decode(raw)


def atomic_publish(path, value, uid, *, sync=os.fsync, expected_identity=None, parent_access=0):
    """No directory provisioning; orphan temps are never promoted on restart."""
    if parent_access not in {0,0o010} or parent_access==0o010 and uid!=0:
        raise c.CoordinatorError("unsafe_path")
    path = protected_parent(path,uid)
    raw = c.encode(value)
    directory = descriptor = None
    renamed = False
    temporary = ".queue-"+str(uuid.uuid4())+".tmp"
    try:
        parent = path.parent.lstat()
        directory = os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        opened = os.fstat(directory)
        if (opened.st_dev,opened.st_ino)!=(parent.st_dev,parent.st_ino) or opened.st_uid!=uid or opened.st_mode&0o077 != parent_access:
            raise c.CoordinatorError("unsafe_path")
        if expected_identity is not None:
            target = trusted_open(path,uid,identity=expected_identity); os.close(target)
        elif path.exists() or path.is_symlink():
            target = trusted_open(path,uid); os.close(target)
        descriptor = os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=directory)
        offset=0
        while offset<len(raw):
            written=os.write(descriptor,raw[offset:])
            if written<=0:raise OSError()
            offset+=written
        sync(descriptor)
        os.close(descriptor); descriptor=None
        os.replace(temporary,path.name,src_dir_fd=directory,dst_dir_fd=directory)
        renamed=True
        sync(directory)
        result=os.stat(path.name,dir_fd=directory,follow_symlinks=False)
        return result.st_dev,result.st_ino
    except Exception:
        # No caller may ACK or continue claiming after unknown post-rename sync.
        raise c.CoordinatorError("queue_unknown" if renamed else "queue_unavailable") from None
    finally:
        if descriptor is not None:os.close(descriptor)
        if directory is not None:
            if not renamed:
                try:os.unlink(temporary,dir_fd=directory)
                except OSError:pass
            os.close(directory)


class StateStore:
    validate = staticmethod(c.state)
    parent_access = 0
    def __init__(self,path,uid,owner=None,*,sync=os.fsync):
        self.path,self.uid,self.owner,self.sync=Path(path),uid,owner,sync
        self.failed=False
        try:
            metadata=self.path.lstat()
            self.identity=(metadata.st_dev,metadata.st_ino)
            self.parent_identity=(self.path.parent.lstat().st_dev,self.path.parent.lstat().st_ino)
            self.read()
        except Exception:raise c.CoordinatorError("queue_unavailable") from None

    def read(self):
        if self.failed:raise c.CoordinatorError("queue_unavailable")
        try:
            parent=self.path.parent.lstat()
            if (parent.st_dev,parent.st_ino)!=self.parent_identity:raise ValueError()
            return self.validate(read_json(self.path,self.uid,self.identity))
        except Exception:
            self.failed=True
            raise c.CoordinatorError("queue_unavailable") from None

    def commit(self,value):
        if self.failed or self.owner is None:raise c.CoordinatorError("queue_unavailable")
        try:
            self.owner.check(); self.read(); self.validate(value)
            self.identity=atomic_publish(self.path,value,self.uid,sync=self.sync,expected_identity=self.identity,
                parent_access=self.parent_access)
        except Exception as error:
            self.failed=True
            if isinstance(error,c.CoordinatorError):raise
            raise c.CoordinatorError("queue_unavailable") from None
