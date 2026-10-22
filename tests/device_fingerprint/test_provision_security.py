"""Issue 245: fail-closed filesystem/transaction/publish and native POSIX roles."""
import errno
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from app.device_fingerprint import provisioning as p
from app.device_fingerprint.repository import writer_lock
from tests.device_fingerprint.test_provision_empty_v2 import IDENTITY, POSIX, install, provision, settings


@POSIX
@pytest.mark.parametrize('key', ['device_fingerprint_db_path', 'device_fingerprint_writer_lock_path', 'device_fingerprint_max_db_bytes'])
def test_invalid_settings_have_zero_side_effects(install, key):
    assert p.provision_empty_v2(settings(install, **{key: 'invalid'}), artifact_identity=IDENTITY).code == 'HOLD_INVALID_CONFIGURATION'
    assert not list(install.iterdir())


@POSIX
@pytest.mark.parametrize('fault', ['db_symlink', 'db_dangling', 'db_hardlink', 'db_directory', 'db_mode',
    'lock_symlink', 'lock_hardlink', 'lock_directory', 'lock_unsafe_mode', 'lock_private_mode', 'lock_foreign_content',
    'parent_symlink', 'parent_group_write', 'parent_world_write', 'missing_parent'])
def test_untrusted_targets_and_parents_are_not_modified(install, fault):
    target = install / 'evidence.sqlite3'
    lock = install / 'evidence.writer.lock'
    config = settings(install)
    if fault.startswith('db_'):
        if fault == 'db_directory': target.mkdir()
        elif fault in ('db_symlink', 'db_dangling'):
            other = install / 'other'
            if fault == 'db_symlink': other.write_bytes(b'foreign')
            target.symlink_to(other)
        else:
            target.write_bytes(b'foreign'); target.chmod(0o600)
            if fault == 'db_hardlink': os.link(target, install / 'alias')
            else: target.chmod(0o666)
    elif fault.startswith('lock_'):
        if fault == 'lock_directory': lock.mkdir()
        elif fault == 'lock_symlink': lock.symlink_to(install / 'missing')
        else:
            lock.write_bytes(b'foreign' if fault == 'lock_foreign_content' else b'\0'); lock.chmod(0o640)
            if fault == 'lock_hardlink': os.link(lock, install / 'alias')
            elif fault == 'lock_unsafe_mode': lock.chmod(0o660)
            elif fault == 'lock_private_mode': lock.chmod(0o600)
    elif fault == 'parent_symlink':
        (install / 'alias').symlink_to(install, target_is_directory=True)
        config = settings(install / 'alias')
    elif fault == 'missing_parent': config = settings(install / 'missing')
    else: install.chmod(0o720 if fault == 'parent_group_write' else 0o702)
    before = {str(x): (x.lstat().st_ino, x.lstat().st_mode) for x in install.iterdir()}
    result = p.provision_empty_v2(config, artifact_identity=IDENTITY)
    assert result.code.startswith('HOLD_')
    assert {str(x): (x.lstat().st_ino, x.lstat().st_mode) for x in install.iterdir()} == before


@POSIX
@pytest.mark.parametrize('failure', ['schema', 'commit', 'close', 'verify', 'post_verify', 'disk_full', 'link', 'fsync_stage', 'fsync_publish', 'fsync_cleanup'])
def test_failure_never_reports_success_or_deletes_published_target(install, monkeypatch, failure):
    with writer_lock(str(install / 'evidence.writer.lock')): pass
    if failure in ('schema', 'disk_full'):
        def fail(connection):
            connection.execute('CREATE TABLE transient(value)')
            raise sqlite3.OperationalError('database or disk is full' if failure == 'disk_full' else 'fault')
        monkeypatch.setattr(p, '_create_v2_schema', fail)
    elif failure in ('commit', 'close'):
        connect = sqlite3.connect
        class Connection:
            def __init__(self, *a, **kw): self.conn = connect(*a, **kw)
            def __getattr__(self, name): return getattr(self.conn, name)
            def execute(self, sql, *a):
                if sql == 'COMMIT' and failure == 'commit': raise sqlite3.OperationalError('commit fault')
                return self.conn.execute(sql, *a)
            def close(self):
                self.conn.close()
                if failure == 'close': raise sqlite3.OperationalError('close fault')
        monkeypatch.setattr(p.sqlite3, 'connect', Connection)
    elif failure == 'verify': monkeypatch.setattr(p, '_verify_empty', lambda *a: (_ for _ in ()).throw(p.ProvisionHold()))
    elif failure == 'post_verify':
        verify = p._verify_empty
        def fail(path, *args):
            if path.name == 'evidence.sqlite3': raise p.ProvisionHold()
            return verify(path, *args)
        monkeypatch.setattr(p, '_verify_empty', fail)
    elif failure == 'link': monkeypatch.setattr(p.os, 'link', lambda *a, **kw: (_ for _ in ()).throw(OSError(errno.EXDEV, 'cross device')))
    else:
        fsync = os.fsync; calls = []
        fault_at = {'fsync_stage': 1, 'fsync_publish': 2, 'fsync_cleanup': 3}[failure]
        def fail(fd):
            calls.append(fd)
            if len(calls) == fault_at: raise OSError('fsync fault')
            return fsync(fd)
        monkeypatch.setattr(p.os, 'fsync', fail)
    result = provision(install)
    assert result.code.startswith('HOLD_') and result.database_generation_id is None
    target = install / 'evidence.sqlite3'
    if failure in ('post_verify', 'fsync_publish', 'fsync_cleanup'):
        assert result.code == 'HOLD_PUBLISHED_RECONCILE' and target.is_file()
        connection = sqlite3.connect(target)
        assert connection.execute('PRAGMA user_version').fetchone()[0] == 2
        assert connection.execute('SELECT last_ingest_sequence FROM device_fingerprint_storage_state').fetchone()[0] == 0
        connection.close()
    else: assert not target.exists()


@POSIX
def test_no_clobber_even_if_target_appears_at_atomic_link(install, monkeypatch):
    link = os.link
    def conflict(*args, **kwargs):
        target = install / 'evidence.sqlite3'
        target.write_bytes(b'foreign-database-canary'); target.chmod(0o600)
        return link(*args, **kwargs)
    monkeypatch.setattr(p.os, 'link', conflict)
    assert provision(install).code.startswith('HOLD_')
    assert (install / 'evidence.sqlite3').read_bytes() == b'foreign-database-canary'


@POSIX
def test_parent_substitution_stops_before_publication(install, monkeypatch):
    directory = install / 'writer'; directory.mkdir(mode=0o700)
    build = p._build_stage
    def substitute(*args):
        build(*args)
        directory.rename(install / 'quarantined-parent')
        directory.mkdir(mode=0o700)
    monkeypatch.setattr(p, '_build_stage', substitute)
    assert provision(directory).code == 'HOLD_PARENT_CHANGED'
    assert not list(directory.iterdir())
    assert not (install / 'quarantined-parent/evidence.sqlite3').exists()


def _concurrent(config, start, queue):
    start.wait(5)
    result = p.provision_empty_v2(config, artifact_identity=IDENTITY)
    queue.put((result.code, result.database_generation_id))


@POSIX
def test_two_native_processes_publish_at_most_one_generation(install):
    context = multiprocessing.get_context('fork')
    start = context.Event(); queue = context.Queue()
    children = [context.Process(target=_concurrent, args=(settings(install), start, queue)) for _ in range(2)]
    for child in children: child.start()
    start.set()
    results = [queue.get(timeout=15) for _ in children]
    for child in children:
        child.join(15); assert child.exitcode == 0
    assert sum(code == 'PROVISIONED' for code, _ in results) == 1
    assert all(code == 'PROVISIONED' or code == 'ALREADY_EXISTS_NO_CHANGE' or code.startswith('HOLD_') for code, _ in results)
    generation = next(value for code, value in results if code == 'PROVISIONED')
    with sqlite3.connect(install / 'evidence.sqlite3') as connection:
        assert connection.execute('SELECT database_generation_id FROM device_fingerprint_storage_state').fetchone()[0] == generation
    connection.close(); queue.close(); queue.join_thread()


@POSIX
@pytest.mark.parametrize('phase', ['before_publish', 'during_schema', 'after_link'])
def test_crash_quarantines_stage_and_never_auto_promotes_or_replaces(install, phase):
    context = multiprocessing.get_context('fork')
    def crash():
        if phase == 'before_publish':
            original = p._verify_empty
            def verify(*args):
                original(*args)
                os._exit(77)
            p._verify_empty = verify
        elif phase == 'during_schema':
            def schema(connection):
                connection.execute('CREATE TABLE interrupted(value)')
                os._exit(77)
            p._create_v2_schema = schema
        else:
            original = os.link
            def linked(*args, **kwargs):
                original(*args, **kwargs)
                os._exit(77)
            p.os.link = linked
        provision(install)
    child = context.Process(target=crash); child.start(); child.join(10)
    assert child.exitcode == 77
    assert (install / 'evidence.sqlite3').exists() is (phase == 'after_link')
    stages = list(install.glob('.evidence-v2-stage-*'))
    assert stages
    before = {path: (path.stat().st_ino, path.read_bytes()) for path in stages}
    if phase == 'after_link':
        authoritative = (install / 'evidence.sqlite3').read_bytes()
        assert provision(install).code.startswith('HOLD_')
        assert (install / 'evidence.sqlite3').read_bytes() == authoritative
    else: assert provision(install).code == 'PROVISIONED'
    assert {path: (path.stat().st_ino, path.read_bytes()) for path in stages} == before


@POSIX
def test_unsupported_filesystem_refused_before_lock(install, monkeypatch):
    monkeypatch.setattr(p, '_local_filesystem', lambda fd: (_ for _ in ()).throw(p.ProvisionHold('HOLD_UNSUPPORTED_FILESYSTEM')))
    assert provision(install).code == 'HOLD_UNSUPPORTED_FILESYSTEM'
    assert not list(install.iterdir())


@POSIX
def test_configured_cap_reaches_staging_not_disabled_default(install, monkeypatch):
    cap = p.enforce_storage_cap
    calls = []
    def enforce(connection, maximum):
        calls.append(maximum)
        return cap(connection, maximum)
    monkeypatch.setattr(p, 'enforce_storage_cap', enforce)
    assert provision(install, device_fingerprint_max_db_bytes='134217728').code == 'PROVISIONED'
    assert calls == [134217728]


@POSIX
def test_private_stage_open_failure_no_authoritative_file(install, monkeypatch):
    original = os.open
    def fail(name, flags, *args, **kwargs):
        if str(name).startswith(p._STAGE_PREFIX): raise OSError(errno.ENOSPC, 'no space')
        return original(name, flags, *args, **kwargs)
    monkeypatch.setattr(p.os, 'open', fail)
    assert provision(install).code == 'HOLD_PROVISION_FAILED'
    assert {x.name for x in install.iterdir()} == {'evidence.writer.lock'}


@POSIX
def test_native_disposable_writer_reader_group_wal_permissions(install):
    if os.geteuid() != 0:
        pytest.skip('root-only disposable UID/GID separation, rerun by isolated Linux root focused suite')
    # Synthetic Lab roles only; never installed service identities or account changes.
    writer_uid, reader_uid, read_gid = 65001, 65002, 65002
    install.chmod(0o755)
    directory = install / 'writer'; directory.mkdir(mode=0o750); os.chown(directory, writer_uid, read_gid)
    unrelated = install / 'portal.sqlite3'; unrelated.write_bytes(b'private-other-store'); unrelated.chmod(0o600)
    prefix = ('from tests.device_fingerprint.test_provision_security import *; '
              'from tests.device_fingerprint.test_provision_security import _reader_role, _reader_after_close, _reader_unavailable; ')
    writer = prefix + (
        f'os.setgroups([]); os.setgid({read_gid}); os.setuid({writer_uid}); '
        f'root=Path({str(directory)!r}); '
        'assert provision(root).code=="PROVISIONED"; '
        'repo=p.DeviceFingerprintRepository(str(root/"evidence.sqlite3"),max_db_bytes=67108864); '
        'repo.initialize(); repo.close(); repo.initialize(); '
        'repo.connection.execute("UPDATE device_fingerprint_storage_state SET last_ingest_sequence=1"); '
        'print("WRITER_READY",flush=True); sys.stdin.read(1); repo.close()')
    process = subprocess.Popen([sys.executable, '-B', '-c', writer], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == 'WRITER_READY'
        assert (directory / 'evidence.sqlite3-wal').exists() and (directory / 'evidence.sqlite3-shm').exists()
        reader = prefix + f'_reader_role({str(directory)!r},{str(unrelated)!r},{reader_uid},{read_gid})'
        result = subprocess.run([sys.executable, '-B', '-c', reader], capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stdout + result.stderr
        for suffix in ('-wal', '-shm'):
            path = directory / ('evidence.sqlite3' + suffix)
            mode = path.stat().st_mode & 0o777
            path.chmod(0o600)
            try:
                denied = prefix + f'_reader_unavailable({str(directory)!r},{reader_uid},{read_gid})'
                result = subprocess.run([sys.executable, '-B', '-c', denied], capture_output=True, text=True, timeout=15)
                assert result.returncode == 0, result.stdout + result.stderr
            finally: path.chmod(mode)
        process.stdin.write('x'); process.stdin.flush()
        assert process.wait(10) == 0, process.stderr.read()
        # Writer owns cleanup/recovery; a RO reopen may succeed or fail closed, never create sidecars.
        reader = prefix + f'_reader_after_close({str(directory)!r},{reader_uid},{read_gid})'
        result = subprocess.run([sys.executable, '-B', '-c', reader], capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        if process.poll() is None:
            process.kill(); process.wait(10)


def _reader_role(directory, unrelated, uid, gid):
    from app.device_fingerprint.repository import open_read_only
    os.setgroups([]); os.setgid(gid); os.setuid(uid)
    root = Path(directory)
    connection = open_read_only(str(root / 'evidence.sqlite3'))
    assert connection.execute('SELECT last_ingest_sequence FROM device_fingerprint_storage_state').fetchone()[0] == 1
    for sql in ('DELETE FROM device_fingerprint_storage_state',
                'INSERT OR REPLACE INTO device_fingerprint_storage_state SELECT * FROM device_fingerprint_storage_state',
                'UPDATE device_fingerprint_storage_state SET last_ingest_sequence=2', 'CREATE TABLE forbidden(value)'):
        try: connection.execute(sql)
        except sqlite3.OperationalError as exc: assert 'readonly' in str(exc).lower()
        else: raise AssertionError('reader SQL write allowed')
    connection.close()
    for name in ('evidence.sqlite3', 'evidence.writer.lock', 'evidence.sqlite3-wal', 'evidence.sqlite3-shm'):
        try: fd = os.open(root / name, os.O_RDWR)
        except PermissionError: pass
        else: os.close(fd); raise AssertionError('reader OS write allowed')
        try: os.unlink(root / name)
        except PermissionError: pass
        else: raise AssertionError('reader unlink allowed')
    for name in ('another.sqlite3', 'another.lock', 'new-wal', 'new-shm'):
        try: fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except PermissionError: pass
        else: os.close(fd); raise AssertionError('reader file creation allowed')
    try: Path(unrelated).read_bytes()
    except PermissionError: pass
    else: raise AssertionError('unrelated Portal store readable')


def _reader_after_close(directory, uid, gid):
    from app.device_fingerprint.repository import open_read_only
    os.setgroups([]); os.setgid(gid); os.setuid(uid)
    root = Path(directory); before = {x.name for x in root.iterdir()}
    try:
        connection = open_read_only(str(root / 'evidence.sqlite3'))
        try:
            assert connection.execute('SELECT last_ingest_sequence FROM device_fingerprint_storage_state').fetchone()[0] == 1
        finally: connection.close()
    except (sqlite3.DatabaseError, p.DeviceFingerprintWriterUnavailable, RuntimeError):
        pass  # Existing helper is allowed to be unavailable until controlled writer reopen.
    assert {x.name for x in root.iterdir()} == before


def _reader_unavailable(directory, uid, gid):
    from app.device_fingerprint.repository import open_read_only
    from app.device_fingerprint.models import DeviceFingerprintStorageUnavailable
    os.setgroups([]); os.setgid(gid); os.setuid(uid)
    connection = None
    try:
        connection = open_read_only(str(Path(directory) / 'evidence.sqlite3'))
        connection.execute('SELECT last_ingest_sequence FROM device_fingerprint_storage_state').fetchone()
    except (DeviceFingerprintStorageUnavailable, sqlite3.DatabaseError):
        pass
    else: raise AssertionError('unreadable WAL/SHM silently treated as available')
    finally:
        if connection is not None: connection.close()


@POSIX
def test_native_acl_write_mask_rejected_read_traverse_acl_preserved(install):
    if os.geteuid() != 0:
        pytest.skip('root-only disposable native ACL policy, rerun in Linux root focused suite')
    import ctypes
    import ctypes.util
    library = ctypes.util.find_library('acl')
    if not library:
        pytest.skip('native libacl unavailable: ACL check NOT_EXECUTED; independent TechLead gate required')
    acl = ctypes.CDLL(library, use_errno=True)
    acl.acl_from_text.argtypes = [ctypes.c_char_p]; acl.acl_from_text.restype = ctypes.c_void_p
    acl.acl_set_file.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p]
    acl.acl_free.argtypes = [ctypes.c_void_p]
    def apply(text):
        value = acl.acl_from_text(text.encode('ascii'))
        assert value
        try: assert acl.acl_set_file(os.fsencode(install), 0x8000, value) == 0
        finally: acl.acl_free(value)
    apply('u::rwx,u:65002:rwx,g::---,m::rwx,o::---')
    assert provision(install).code == 'HOLD_UNTRUSTED_PARENT' and not list(install.iterdir())
    apply('u::rwx,u:65002:r-x,g::---,m::r-x,o::---')
    before = os.getxattr(install, 'system.posix_acl_access')
    assert provision(install).code == 'PROVISIONED'
    assert os.getxattr(install, 'system.posix_acl_access') == before


@POSIX
@pytest.mark.parametrize('target', ['db', 'lock', 'parent'])
def test_native_foreign_owner_rejected_without_chown_or_reset(install, target):
    if os.geteuid() != 0:
        pytest.skip('root-only disposable foreign-owner check; Linux root focused suite')
    path = install if target == 'parent' else install / ('evidence.sqlite3' if target == 'db' else 'evidence.writer.lock')
    if target != 'parent': path.write_bytes(b'foreign'); path.chmod(0o640)
    os.chown(path, 65001, -1)
    before = (path.lstat().st_ino, path.lstat().st_uid, path.lstat().st_mode)
    assert provision(install).code.startswith('HOLD_')
    assert (path.lstat().st_ino, path.lstat().st_uid, path.lstat().st_mode) == before


def _native_acl(path, text, *, default=False):
    import ctypes
    import ctypes.util
    library = ctypes.util.find_library('acl')
    assert library, 'mandatory native Lab ACL dependency is unavailable'
    acl = ctypes.CDLL(library, use_errno=True)
    acl.acl_from_text.argtypes = [ctypes.c_char_p]; acl.acl_from_text.restype = ctypes.c_void_p
    acl.acl_set_file.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p]
    acl.acl_free.argtypes = [ctypes.c_void_p]
    value = acl.acl_from_text(text.encode('ascii'))
    assert value
    try: assert acl.acl_set_file(os.fsencode(path), 0x4000 if default else 0x8000, value) == 0
    finally: acl.acl_free(value)


@pytest.fixture
def portal_ancestry(install, monkeypatch):
    if os.geteuid() != 0:
        pytest.skip('root-only literal-shape Portal-owned execute-only ACL fixture; root suite required')
    import pwd
    from pathlib import PurePosixPath
    from types import SimpleNamespace
    install.chmod(0o755)
    code = install / 'opt/CaptivePortal'; code.mkdir(parents=True, mode=0o755)
    data = code / 'data'; data.mkdir()
    final = data / 'evidence'; final.mkdir()
    # Independent synthetic roles; no host accounts/groups or production UID constants.
    portal, writer = 65103, 65104
    os.chown(data, portal, portal); os.chown(final, writer, writer)
    _native_acl(data, f'u::rwx,u:{writer}:--x,g::---,m::--x,o::---')
    _native_acl(final, f'u::rwx,u:{portal}:--x,g::---,m::--x,o::---')
    monkeypatch.setattr(p, '_PORTAL_PARENT', PurePosixPath(data))
    monkeypatch.setattr(p, '_NESTED_PARENT', PurePosixPath(final))
    def native_role(name):
        assert name == 'captivportal'
        return SimpleNamespace(pw_name=name, pw_uid=portal, pw_gid=portal)
    monkeypatch.setattr(pwd, 'getpwnam', native_role)
    return data, final, portal, writer


def _restricted_provision(config, writer, queue, *, probe=None):
    os.setgroups([]); os.setgid(writer); os.setuid(writer)
    checks = {}
    try:
        if probe is not None:
            try: fd = os.open(probe, os.O_RDONLY | os.O_DIRECTORY)
            except PermissionError: checks['ordinary_read_denied'] = True
            else: os.close(fd); raise AssertionError('intermediary directory unexpectedly readable')
            fd = os.open(probe, os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                checks['opath_pin'] = os.fstat(fd).st_ino
                checks['native_acl_bytes'] = len(os.getxattr('/proc/self/fd/' + str(fd), 'system.posix_acl_access'))
            finally: os.close(fd)
        result = p.provision_empty_v2(config, artifact_identity=IDENTITY)
        checks['code'] = result.code
        checks['generation'] = result.database_generation_id
        if result.code == 'PROVISIONED':
            db = Path(config['device_fingerprint_db_path'])
            connection = sqlite3.connect(db)
            try:
                p.DeviceFingerprintRepository._validate_connection(connection)
                assert connection.execute('SELECT last_ingest_sequence FROM device_fingerprint_storage_state').fetchone()[0] == 0
                assert connection.execute('SELECT count(*) FROM device_fingerprint_evidence').fetchone()[0] == 0
                assert connection.execute('SELECT count(*) FROM device_fingerprint_source_health_events').fetchone()[0] == 0
            finally: connection.close()
        queue.put(checks)
    except BaseException as exc:
        queue.put({'error': type(exc).__name__, 'detail': str(exc)})


def _run_restricted(config, writer, *, probe=None):
    context = multiprocessing.get_context('fork'); queue = context.Queue()
    child = context.Process(target=_restricted_provision, args=(config, writer, queue), kwargs={'probe': probe})
    child.start()
    try:
        result = queue.get(timeout=15)
        child.join(15); assert child.exitcode == 0
        assert 'error' not in result, result
        return result
    finally:
        if child.is_alive(): child.kill(); child.join(5)
        queue.close(); queue.join_thread()


@POSIX
def test_portal_owned_search_only_intermediary_provisions_exact_empty_v2(portal_ancestry):
    data, final, _, writer = portal_ancestry
    assert not list(final.iterdir())
    result = _run_restricted(settings(final), writer, probe=str(data))
    assert result['ordinary_read_denied'] and result['opath_pin'] == data.stat().st_ino
    assert result['native_acl_bytes'] == 44
    assert result['code'] == 'PROVISIONED', result
    assert {item.name for item in final.iterdir()} == {'evidence.sqlite3', 'evidence.writer.lock'}
    assert (final / 'evidence.sqlite3').stat().st_uid == writer
    assert (final / 'evidence.sqlite3').stat().st_nlink == 1
    print('PORTAL_0710_RDONLY_DENIED_OPATH_NATIVE_ACL_PROVISION_V2=PASS')


@POSIX
@pytest.mark.parametrize('fault', ['foreign-owner', 'wrong-role', 'role-unavailable', 'missing-search',
    'writer-write', 'named-user-write', 'named-group-write', 'masked-extra-user', 'group-write', 'world-write',
    'data-default-acl', 'final-default-acl', 'blocked-final', 'unreadable-receipt',
    'data-symlink', 'final-symlink', 'code-symlink', 'opt-symlink', 'extra-foreign-intermediate', 'deeper-parent', 'mixed-lock-parent'])
def test_nested_trust_profile_rejects_every_unapproved_shape(portal_ancestry, monkeypatch, fault):
    import pwd
    from types import SimpleNamespace
    data, final, portal, writer = portal_ancestry
    config = settings(final)
    if fault == 'foreign-owner': os.chown(data, portal + 2, -1)
    elif fault == 'wrong-role':
        monkeypatch.setattr(pwd, 'getpwnam', lambda _: SimpleNamespace(pw_name='captivportal', pw_uid=portal + 2, pw_gid=portal + 2))
    elif fault == 'role-unavailable': monkeypatch.setattr(pwd, 'getpwnam', lambda _: (_ for _ in ()).throw(KeyError()))
    elif fault == 'missing-search': _native_acl(data, 'u::rwx,g::---,o::---')
    elif fault in ('writer-write', 'named-user-write', 'named-group-write', 'masked-extra-user', 'group-write', 'world-write'):
        named = f'u:{writer}:--x'
        if fault == 'writer-write': named = f'u:{writer}:rwx'
        if fault in ('named-user-write', 'masked-extra-user'): named += f',u:{writer+2}:rwx'
        group = 'g::rwx' if fault == 'group-write' else 'g::---'
        if fault == 'named-group-write': group += f',g:{writer+2}:rwx'
        mask = '--x' if fault in ('masked-extra-user', 'world-write') else 'rwx'
        other = '-w-' if fault == 'world-write' else '---'
        _native_acl(data, f'u::rwx,{named},{group},m::{mask},o::{other}')
    elif fault in ('data-default-acl', 'final-default-acl'):
        _native_acl(data if fault == 'data-default-acl' else final, 'u::rwx,g::---,o::---', default=True)
    elif fault == 'blocked-final': final.chmod(0o600)
    elif fault == 'unreadable-receipt':
        monkeypatch.setattr(p.os, 'getxattr', lambda *a, **kw: (_ for _ in ()).throw(PermissionError()))
    elif fault.endswith('-symlink'):
        path = data if fault == 'data-symlink' else final if fault == 'final-symlink' else data.parent.parent if fault == 'opt-symlink' else data.parent
        moved = path.with_name(path.name + '-quarantined'); path.rename(moved); path.symlink_to(moved, target_is_directory=True)
    elif fault in ('extra-foreign-intermediate', 'deeper-parent'):
        directory = data / 'extra'; directory.mkdir(); os.chown(directory, portal + 2 if fault == 'extra-foreign-intermediate' else writer, -1)
        directory.chmod(0o711)
        child = directory / 'evidence'; child.mkdir(); os.chown(child, writer, writer); child.chmod(0o700)
        config = settings(child)
    else: config['device_fingerprint_writer_lock_path'] = str(data / 'alternate.lock')
    result = _run_restricted(config, writer)
    assert result['code'].startswith('HOLD_'), result
    assert not (Path(config['device_fingerprint_db_path'])).exists()
    assert not (final / 'evidence.writer.lock').exists()


@POSIX
@pytest.mark.parametrize('phase', [1, 3, 5, 6], ids=['before-lock', 'before-stage', 'before-publish', 'post-publish'])
@pytest.mark.parametrize('changed', ['inode', 'device', 'acl'])
@pytest.mark.parametrize('target', ['data', 'evidence'])
def test_nested_metadata_substitution_checked_at_every_boundary(portal_ancestry, monkeypatch, phase, changed, target):
    from contextlib import contextmanager
    from types import SimpleNamespace
    data, final, _, writer = portal_ancestry
    original_parent, original_stat, original_xattr = p._parent, p.os.stat, p.os.getxattr
    active = [False]
    def substituted(name, *args, **kwargs):
        info = original_stat(name, *args, **kwargs)
        if active[0] and name == target and changed != 'acl':
            fields = {key: getattr(info, key) for key in ('st_dev', 'st_ino', 'st_uid', 'st_gid', 'st_mode')}
            fields['st_ino' if changed == 'inode' else 'st_dev'] += 1
            return SimpleNamespace(**fields)
        return info
    monkeypatch.setattr(p.os, 'stat', substituted)
    def changed_acl(reference, name):
        raw = original_xattr(reference, name)
        if active[0] and changed == 'acl' and name == 'system.posix_acl_access':
            inode = original_stat(reference).st_ino
            if inode == original_stat(data if target == 'data' else final).st_ino:
                return b'\0' + raw[1:]
        return raw
    monkeypatch.setattr(p.os, 'getxattr', changed_acl)
    @contextmanager
    def guarded(path, **kwargs):
        with original_parent(path, **kwargs) as (fd, check):
            calls = [0]
            def verify():
                calls[0] += 1
                if path.name == 'evidence.sqlite3' and calls[0] == phase: active[0] = True
                check()
            yield fd, verify
    monkeypatch.setattr(p, '_parent', guarded)
    result = _run_restricted(settings(final), writer)
    assert result['code'].startswith('HOLD_'), result
    if phase == 6:
        assert result['code'] == 'HOLD_PUBLISHED_RECONCILE'
        with sqlite3.connect(final / 'evidence.sqlite3') as connection:
            p.DeviceFingerprintRepository._validate_connection(connection)
        connection.close()
    else: assert not (final / 'evidence.sqlite3').exists()
