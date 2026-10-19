"""Explicit offline first installation. Never called by repository startup.

Only a stopped, cooperating writer and a protected local directory are supported.
Failures preserve private stages for reconciliation; a published target is never
removed, repaired or overwritten, including after an ambiguous fsync failure.
"""
from __future__ import annotations

import ctypes
import errno
import os
from pathlib import Path, PurePosixPath
import sqlite3
import stat
import struct
import sys
import uuid
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from typing import Mapping, Any

from app.artifact_identity import LoadedArtifactIdentity
from .config import device_fingerprint_max_db_bytes_from_settings
from .models import DeviceFingerprintWriterUnavailable
from .repository import DeviceFingerprintRepository, _create_v2_schema, enforce_storage_cap, writer_lock
from .schema import SCHEMA_VERSION, STORAGE_STATE_TABLE

_SIDECARS = ('-wal', '-shm', '-journal')
_STAGE_PREFIX = '.evidence-v2-stage-'
_MAX_NEW_BYTES = 1_048_576
# Linux persistent local ext, XFS, Btrfs, overlay. No tmpfs/NFS/CIFS/9p/FUSE.
_LOCAL_FS = {0xEF53, 0x58465342, 0x9123683E, 0x794C7630}
_PORTAL_PARENT = PurePosixPath('/opt/CaptivePortal/data')
_NESTED_PARENT = _PORTAL_PARENT / 'evidence'


class ProvisionHold(Exception):
    def __init__(self, code='HOLD_UNSAFE_TARGET'):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ProvisionSettings:
    db_path: str
    writer_lock_path: str
    max_db_bytes: int


@dataclass(frozen=True, slots=True)
class ProvisionResult:
    code: str
    database_generation_id: str | None = None
    artifact_sha: str | None = None
    artifact_tree: str | None = None
    schema_version: int = SCHEMA_VERSION


def resolve_provision_settings(settings: Mapping[str, Any]) -> ProvisionSettings:
    """Do not consume disabled-runtime config, credentials, Site or TLS settings."""
    try:
        paths = []
        for key in ('device_fingerprint_db_path', 'device_fingerprint_writer_lock_path'):
            raw = settings[key]
            if (type(raw) is not str or not 1 <= len(os.fsencode(raw)) <= 4096
                    or any(ord(c) < 33 or ord(c) == 127 for c in raw)
                    or not PurePosixPath(raw).is_absolute() or raw.startswith('//')
                    or str(PurePosixPath(raw)) != raw or '..' in PurePosixPath(raw).parts
                    or not PurePosixPath(raw).name
                    or len(os.fsencode(PurePosixPath(raw).name)) > 200
                    or PurePosixPath(raw).name.startswith(_STAGE_PREFIX)):
                raise ValueError
            paths.append(raw)
        db, lock = paths
        if db == lock or any(db + s == lock or lock + s == db for s in _SIDECARS):
            raise ValueError
        cap = device_fingerprint_max_db_bytes_from_settings(settings)
        return ProvisionSettings(db, lock, cap)
    except Exception:
        raise ProvisionHold('HOLD_INVALID_CONFIGURATION') from None


def _identity(info):
    return info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid


def _directory(info):
    if not stat.S_ISDIR(info.st_mode) or info.st_uid not in (0, os.geteuid()) or info.st_mode & 0o022:
        raise ProvisionHold('HOLD_UNTRUSTED_PARENT')


def _file(info, *, links=1):
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_nlink != links
            or stat.S_IMODE(info.st_mode) not in (0o600, 0o640)):
        raise ProvisionHold()


def _local_filesystem(fd):
    buffer = ctypes.create_string_buffer(256)
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.fstatfs(fd, buffer) != 0 or (ctypes.c_long.from_buffer(buffer).value & 0xFFFFFFFF) not in _LOCAL_FS:
        raise ProvisionHold('HOLD_UNSUPPORTED_FILESYSTEM')
    return ctypes.c_long.from_buffer(buffer).value & 0xFFFFFFFF


def _portal_role():
    """Fixed native host role, never a caller/env-supplied trusted UID."""
    try:
        import pwd
        entry = pwd.getpwnam('captivportal')
        if (entry.pw_name != 'captivportal' or type(entry.pw_uid) is not int
                or type(entry.pw_gid) is not int or entry.pw_uid in (0, os.geteuid())
                or not 0 < entry.pw_uid < 0xFFFFFFFF or not 0 <= entry.pw_gid < 0xFFFFFFFF):
            raise ValueError
        return entry.pw_uid, entry.pw_gid
    except Exception:
        raise ProvisionHold('HOLD_UNTRUSTED_PARENT') from None


def _search_acl(fd, info, named_uid):
    """Read kernel ACL of the pinned inode, not fgetxattr on an O_PATH FD.

    /proc/self/fd is a kernel FD reference, not a configuration symlink bypass.
    A restricted process must be able to obtain this receipt or remain HOLD.
    The host role remains cooperatively trusted; installed-role attestation is
    still an independent #243 prerequisite, not established by this function.
    """
    try:
        reference = '/proc/self/fd/' + str(fd)
        before = os.stat(reference)
        if _identity(before) != _identity(info) or stat.S_IMODE(info.st_mode) != 0o710:
            raise ValueError
        raw = os.getxattr(reference, 'system.posix_acl_access')
        # The approved access ACL has precisely owner rwx, named role --x,
        # owning group ---, mask --x, other ---. No extra named principals.
        expected = struct.pack('<I', 2) + b''.join(struct.pack('<HHI', tag, perm, uid) for tag, perm, uid in (
            (1, 7, 0xFFFFFFFF), (2, 1, named_uid), (4, 0, 0xFFFFFFFF),
            (16, 1, 0xFFFFFFFF), (32, 0, 0xFFFFFFFF)))
        if raw != expected:
            raise ValueError
        try:
            os.getxattr(reference, 'system.posix_acl_default')
        except OSError as exc:
            if exc.errno != errno.ENODATA:
                raise
        else:
            raise ValueError
        after = os.stat(reference)
        if _identity(after) != _identity(before) or before.st_ctime_ns != after.st_ctime_ns:
            raise ValueError
        return raw
    except (OSError, ValueError):
        raise ProvisionHold('HOLD_UNTRUSTED_PARENT') from None


@contextmanager
def _parent(path: Path, *, nested=False):
    """Keep every directory pinned; later phases recheck the entire path chain."""
    opened = []
    pins = []
    try:
        role = _portal_role() if nested else None
        fd = os.open('/', os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        opened.append(fd)
        _directory(os.fstat(fd))
        root_id = _identity(os.fstat(fd))
        if nested and os.fstat(fd).st_uid != 0:
            raise ProvisionHold('HOLD_UNTRUSTED_PARENT')
        current = PurePosixPath('/')
        def admit(child, component, info):
            if not nested:
                _directory(info)
                return None
            if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o022:
                raise ProvisionHold('HOLD_UNTRUSTED_PARENT')
            if _portal_role() != role:
                raise ProvisionHold('HOLD_UNTRUSTED_PARENT')
            if component == _PORTAL_PARENT:
                if (info.st_uid, info.st_gid) != role:
                    raise ProvisionHold('HOLD_UNTRUSTED_PARENT')
                return _search_acl(child, info, os.geteuid())
            if component == _NESTED_PARENT:
                if info.st_uid != os.geteuid():
                    raise ProvisionHold('HOLD_WRITER_IDENTITY')
                return _search_acl(child, info, role[0])
            if info.st_uid != 0:
                raise ProvisionHold('HOLD_UNTRUSTED_PARENT')
            return None
        for name in path.parent.parts[1:]:
            current = current / name
            before = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if not stat.S_ISDIR(before.st_mode) or before.st_mode & 0o022:
                raise ProvisionHold('HOLD_UNTRUSTED_PARENT')
            flags = os.O_RDONLY if current == path.parent else os.O_PATH
            child = os.open(name, flags | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            opened.append(child)
            if _identity(before) != _identity(os.fstat(child)):
                raise ProvisionHold('HOLD_PARENT_CHANGED')
            receipt = admit(child, current, before)
            pins.append((fd, name, child, current, _identity(before), receipt))
            fd = child
        if os.fstat(fd).st_uid != os.geteuid():
            raise ProvisionHold('HOLD_WRITER_IDENTITY')
        filesystem = _local_filesystem(fd)
        if nested and filesystem != 0xEF53:
            raise ProvisionHold('HOLD_UNSUPPORTED_FILESYSTEM')
        def check():
            if (_identity(os.fstat(opened[0])) != root_id
                    or _identity(os.stat('/', follow_symlinks=False)) != root_id):
                raise ProvisionHold('HOLD_PARENT_CHANGED')
            for parent, name, child, component, expected, receipt in pins:
                info = os.stat(name, dir_fd=parent, follow_symlinks=False)
                if _identity(info) != expected or _identity(os.fstat(child)) != expected:
                    raise ProvisionHold('HOLD_PARENT_CHANGED')
                if admit(child, component, info) != receipt:
                    raise ProvisionHold('HOLD_PARENT_CHANGED')
        yield fd, check
    finally:
        for handle in reversed(opened):
            os.close(handle)


def _stat(fd, name):
    try:
        return os.stat(name, dir_fd=fd, follow_symlinks=False)
    except FileNotFoundError:
        return None


def _absent(fd, name):
    target = _stat(fd, name)
    if target is not None:
        _file(target)
        raise ProvisionHold('ALREADY_EXISTS_NO_CHANGE')
    if any(_stat(fd, name + suffix) is not None for suffix in _SIDECARS):
        raise ProvisionHold('HOLD_ORPHAN_SIDECAR')


def _lock_authority(fd, name):
    before = _stat(fd, name)
    if before is None:
        try:
            handle = os.open(name, os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_RDWR | os.O_CLOEXEC,
                             0o600, dir_fd=fd)
        except FileExistsError:
            before = _stat(fd, name)
        else:
            try:
                os.fchmod(handle, 0o640)  # Only our newly created lock, never an existing inode.
                os.write(handle, b'\0')
                os.fsync(handle)
            finally:
                os.close(handle)
            os.fsync(fd)
            before = _stat(fd, name)
    _file(before)
    if stat.S_IMODE(before.st_mode) != 0o640 or before.st_size != 1:
        raise ProvisionHold('HOLD_LOCK_AUTHORITY')
    handle = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
    try:
        if _identity(os.fstat(handle)) != _identity(before) or os.read(handle, 2) != b'\0':
            raise ProvisionHold('HOLD_LOCK_AUTHORITY')
    finally:
        os.close(handle)
    return _identity(before)


def _sidecars_absent(fd, name):
    if any(_stat(fd, name + s) is not None for s in _SIDECARS):
        raise ProvisionHold('HOLD_NONSTANDALONE_STAGE')


def _build_stage(path: Path, generation: str, cap: int):
    connection = sqlite3.connect(path.as_uri() + '?mode=rw', uri=True, isolation_level=None)
    try:
        enforce_storage_cap(connection, cap)
        connection.execute('BEGIN IMMEDIATE')
        try:
            _create_v2_schema(connection)
            connection.execute(f'INSERT INTO {STORAGE_STATE_TABLE} VALUES (1,?,0)', (generation,))
            connection.execute('COMMIT')
        except BaseException:
            if connection.in_transaction:
                connection.execute('ROLLBACK')
            raise
    finally:
        connection.close()


def _verify_empty(path: Path, generation: str, cap: int):
    info = path.lstat()
    _file(info)
    if not 0 < info.st_size <= min(cap, _MAX_NEW_BYTES):
        raise ProvisionHold('HOLD_STAGE_SIZE')
    connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, isolation_level=None)
    steps = 0
    def bounded():
        nonlocal steps
        steps += 1
        return int(steps > 1000)
    try:
        connection.set_progress_handler(bounded, 1000)
        connection.execute('PRAGMA query_only=ON')
        DeviceFingerprintRepository._validate_connection(connection)
        if connection.execute('PRAGMA journal_mode').fetchone()[0] != 'delete':
            raise ProvisionHold('HOLD_NONSTANDALONE_STAGE')
        if connection.execute("SELECT 1 FROM sqlite_master WHERE type IN ('view','trigger') LIMIT 1").fetchone():
            raise ProvisionHold('HOLD_INVALID_STAGE')
        state = connection.execute(f'SELECT singleton_id,database_generation_id,last_ingest_sequence FROM {STORAGE_STATE_TABLE}').fetchall()
        if state != [(1, generation, 0)] or any(connection.execute('SELECT count(*) FROM ' + name).fetchone()[0]
                for name in ('device_fingerprint_evidence', 'device_fingerprint_source_health_events')):
            raise ProvisionHold('HOLD_INVALID_STAGE')
    finally:
        connection.close()
    after = path.lstat()
    if (_identity(after), after.st_size, after.st_mtime_ns, after.st_ctime_ns) != (
            _identity(info), info.st_size, info.st_mtime_ns, info.st_ctime_ns):
        raise ProvisionHold('HOLD_STAGE_CHANGED')


def provision_empty_v2(settings: Mapping[str, Any], *, artifact_identity: LoadedArtifactIdentity) -> ProvisionResult:
    """Python-only settings/identity injection; no operator path/SQL/UUID options."""
    published = False
    stage_fd = None
    try:
        config = resolve_provision_settings(settings)
        if sys.platform != 'linux' or os.name != 'posix':
            raise ProvisionHold('HOLD_PLATFORM_UNSUPPORTED')
        if type(artifact_identity) is not LoadedArtifactIdentity:
            raise ProvisionHold('HOLD_SOURCE_IDENTITY')
        db, lock = Path(config.db_path), Path(config.writer_lock_path)
        nested = db.parent == _NESTED_PARENT and lock.parent == _NESTED_PARENT
        if (db.parent == _NESTED_PARENT or lock.parent == _NESTED_PARENT) and not nested:
            raise ProvisionHold('HOLD_UNTRUSTED_PARENT')
        with ExitStack() as stack:
            db_fd, check_db = stack.enter_context(_parent(db, nested=nested))
            lock_fd, check_lock = stack.enter_context(_parent(lock, nested=nested))
            _absent(db_fd, db.name)
            check_db(); check_lock()
            lock_id = _lock_authority(lock_fd, lock.name)
            check_db(); check_lock()
            with writer_lock(str(lock)) as authority:
                if _identity(os.fstat(authority.fileno())) != lock_id or _identity(lock.lstat()) != lock_id:
                    raise ProvisionHold('HOLD_LOCK_AUTHORITY')
                check_db(); check_lock(); _absent(db_fd, db.name)
                stage_name = _STAGE_PREFIX + uuid.uuid4().hex
                stage_fd = os.open(stage_name, os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_RDWR | os.O_CLOEXEC,
                                   0o600, dir_fd=db_fd)
                stage_id = _identity(os.fstat(stage_fd))
                stage = db.parent / stage_name
                generation = str(uuid.uuid4())
                _build_stage(stage, generation, config.max_db_bytes)
                check_db(); check_lock()
                if _identity(stage.lstat()) != stage_id:
                    raise ProvisionHold('HOLD_STAGE_CHANGED')
                _sidecars_absent(db_fd, stage_name)
                _verify_empty(stage, generation, config.max_db_bytes)
                os.fsync(stage_fd)
                check_db(); check_lock(); _absent(db_fd, db.name)
                os.link(stage_name, db.name, src_dir_fd=db_fd, dst_dir_fd=db_fd, follow_symlinks=False)
                published = True
                os.fsync(db_fd)
                linked = _stat(db_fd, db.name)
                _file(linked, links=2)
                if _identity(linked) != stage_id or _identity(_stat(db_fd, stage_name)) != stage_id:
                    raise ProvisionHold('HOLD_STAGE_CHANGED')
                os.unlink(stage_name, dir_fd=db_fd)  # Only our proven private staging inode.
                os.fsync(db_fd)
                check_db(); check_lock()
                _sidecars_absent(db_fd, db.name)
                _verify_empty(db, generation, config.max_db_bytes)
                if _identity(db.lstat()) != stage_id:
                    raise ProvisionHold('HOLD_STAGE_CHANGED')
                os.close(stage_fd)
                stage_fd = None
                return ProvisionResult('PROVISIONED', generation, artifact_identity.artifact_sha, artifact_identity.artifact_tree)
    except DeviceFingerprintWriterUnavailable:
        return ProvisionResult('HOLD_WRITER_LOCKED')
    except ProvisionHold as exc:
        return ProvisionResult('HOLD_PUBLISHED_RECONCILE' if published else exc.code)
    except Exception:
        return ProvisionResult('HOLD_PUBLISHED_RECONCILE' if published else 'HOLD_PROVISION_FAILED')
    finally:
        if stage_fd is not None:
            try:
                os.close(stage_fd)
            except OSError:
                pass  # Already HOLD; never mask the original failure or retry publication.
