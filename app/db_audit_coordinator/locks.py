"""Attested permanent inodes. Only a worker opens the heavy gate."""
from __future__ import annotations

from dataclasses import dataclass
import errno
import os
from pathlib import Path
import stat

from .contracts import CoordinatorError


def protected_parent(path, uid):
    raw = os.fspath(path)
    path = Path(raw)
    if (os.name != "posix" or not path.is_absolute() or str(path) != raw or ".." in path.parts
            or any(ord(char)<32 or ord(char)==127 for char in raw)):
        raise CoordinatorError("unsafe_path")
    for directory in (path.parent, *path.parent.parents):
        info = directory.lstat()
        sticky_root = info.st_uid == 0 and info.st_mode & stat.S_ISVTX
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid not in {0,uid}
                or info.st_mode & 0o022 and not sticky_root):
            raise CoordinatorError("unsafe_path")
    return path


def trusted_open(path, uid, *, identity=None, flags=None):
    """Never creates a file; descriptors close on every failed trust check."""
    descriptor = None
    try:
        path = protected_parent(path, uid)
        before = path.lstat()
        descriptor = os.open(path, (os.O_RDONLY if flags is None else flags) | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != uid or info.st_mode & 0o077 or info.st_nlink != 1
                or (before.st_dev,before.st_ino) != (info.st_dev,info.st_ino)
                or identity is not None and (info.st_dev,info.st_ino) != tuple(identity)):
            raise CoordinatorError("unsafe_path")
        return descriptor
    except (OSError, ValueError):
        if descriptor is not None: os.close(descriptor)
        raise CoordinatorError("unsafe_path") from None
    except CoordinatorError:
        if descriptor is not None: os.close(descriptor)
        raise


@dataclass(frozen=True)
class LockSpec:
    path: str
    uid: int
    device: int
    inode: int


class PermanentLock:
    def __init__(self, spec):
        self.spec, self.fd, self.pid = spec, None, os.getpid()

    def acquire(self):
        if self.fd is not None: raise CoordinatorError("coordinator_unavailable")
        if os.name != "posix": raise CoordinatorError("not_admitted")
        import fcntl
        descriptor = trusted_open(self.spec.path, self.spec.uid, identity=(self.spec.device,self.spec.inode))
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.fd = descriptor
            self.check()
        except OSError as error:
            os.close(descriptor)
            raise CoordinatorError("gate_busy" if error.errno in {errno.EAGAIN,errno.EACCES} else "unsafe_path") from None
        except Exception:
            self.fd = None; os.close(descriptor); raise
        return self

    def check(self):
        if self.fd is None or self.pid != os.getpid(): raise CoordinatorError("unsafe_path")
        fresh = trusted_open(self.spec.path,self.spec.uid,identity=(self.spec.device,self.spec.inode))
        os.close(fresh)

    def close(self):
        # Closing only our independently opened FD; never issue LOCK_UN.
        if self.fd is not None:
            os.close(self.fd); self.fd = None

    def __enter__(self): return self.acquire()
    def __exit__(self,*args): self.close()
