"""Issue 245 Part A: explicit, standalone, no-clobber empty v2 provisioning."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import stat
import sys
import tempfile
import uuid

import pytest

from app.artifact_identity import LoadedArtifactIdentity
from app.device_fingerprint import cli, provisioning as p
from app.device_fingerprint.repository import DeviceFingerprintRepository, open_read_only, writer_lock
from app.device_fingerprint.models import DeviceFingerprintStorageUnavailable
from app.device_fingerprint.schema import SCHEMA_SQL

POSIX = pytest.mark.skipif(sys.platform != 'linux', reason='Linux local filesystem atomic Evidence provisioning contract')
IDENTITY = LoadedArtifactIdentity('a' * 40, 'b' * 40, 'test-provision', '2026-10-19T00:00:00.000Z')


@pytest.fixture
def install():
    if sys.platform != 'linux':
        pytest.skip('Linux protected filesystem fixture; Windows platform refusal tested separately')
    # Root-only fixture stays on native ext4 too, not volatile /run tmpfs.
    parent = '/var/lib' if os.geteuid() == 0 else '/home/zaur_navi/captivportal-lab'
    folder = Path(tempfile.mkdtemp(prefix='issue245-', dir=parent))
    try:
        yield folder
    finally:
        shutil.rmtree(folder)


def settings(folder, **overrides):
    folder = PurePosixPath(folder.as_posix())
    result = dict(device_fingerprint_db_path=str(folder / 'evidence.sqlite3'),
                  device_fingerprint_writer_lock_path=str(folder / 'evidence.writer.lock'),
                  device_fingerprint_max_db_bytes='67108864', device_fingerprint_evidence_enabled='false',
                  device_fingerprint_producers_json='unusable-credentials-are-not-needed')
    result.update(overrides)
    return result


def provision(folder, **overrides):
    return p.provision_empty_v2(settings(folder, **overrides), artifact_identity=IDENTITY)


@pytest.mark.parametrize('enabled', ['true', 'false'])
def test_offline_resolution_is_strict_even_when_disabled(enabled):
    value = p.resolve_provision_settings(settings(Path('/safe'), device_fingerprint_evidence_enabled=enabled))
    assert value == p.ProvisionSettings('/safe/evidence.sqlite3', '/safe/evidence.writer.lock', 67108864)


@pytest.mark.parametrize('invalid', ['', '/', 'relative/db', '/safe/../db', '/safe//db', '/safe/./db', '/safe/db/',
    '//safe/db', '/safe/a\nsecret', '/safe/with space', '/safe/.evidence-v2-stage-reserved', None, 123])
@pytest.mark.parametrize('key', ['device_fingerprint_db_path', 'device_fingerprint_writer_lock_path'])
def test_bad_paths_rejected_without_filesystem_authority(key, invalid):
    with pytest.raises(p.ProvisionHold, match='HOLD_INVALID_CONFIGURATION'):
        p.resolve_provision_settings(settings(Path('/safe'), **{key: invalid}))


@pytest.mark.parametrize('cap', ['67108863', '8589934593', 'bad', True, 12.5])
def test_configured_limit_not_disabled_default(cap):
    with pytest.raises(p.ProvisionHold):
        p.resolve_provision_settings(settings(Path('/safe'), device_fingerprint_max_db_bytes=cap))


@pytest.mark.parametrize('suffix', ['', '-wal', '-shm', '-journal'])
def test_lock_cannot_alias_db_or_sidecar(suffix):
    with pytest.raises(p.ProvisionHold):
        p.resolve_provision_settings(settings(Path('/safe'), device_fingerprint_writer_lock_path='/safe/evidence.sqlite3' + suffix))


@POSIX
def test_fresh_exact_schema_generation_empty_and_unchanged_repository_admission(install):
    result = provision(install)
    assert result.code == 'PROVISIONED'
    assert uuid.UUID(result.database_generation_id).version == 4
    assert str(uuid.UUID(result.database_generation_id)) == result.database_generation_id
    assert (result.artifact_sha, result.artifact_tree) == ('a' * 40, 'b' * 40)
    db = install / 'evidence.sqlite3'
    assert db.read_bytes().startswith(b'SQLite format 3\0')
    assert stat.S_IMODE(db.stat().st_mode) == 0o600 and db.stat().st_nlink == 1
    assert set(f.name for f in install.iterdir()) == {'evidence.sqlite3', 'evidence.writer.lock'}
    with sqlite3.connect(db) as connection, sqlite3.connect(':memory:') as reference:
        reference.executescript(SCHEMA_SQL)
        sql = "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
        assert connection.execute(sql).fetchall() == reference.execute(sql).fetchall()
        assert connection.execute('PRAGMA user_version').fetchone() == (2,)
        assert connection.execute('SELECT * FROM device_fingerprint_storage_state').fetchall() == [(1, result.database_generation_id, 0)]
        assert connection.execute('SELECT count(*) FROM device_fingerprint_evidence').fetchone() == (0,)
        assert connection.execute('SELECT count(*) FROM device_fingerprint_source_health_events').fetchone() == (0,)
    connection.close(); reference.close()
    repo = DeviceFingerprintRepository(str(db), max_db_bytes=67108864)
    repo.initialize()
    assert repo.connection.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
    assert repo.connection.execute('PRAGMA synchronous').fetchone()[0] == 1
    assert repo.connection.execute('PRAGMA busy_timeout').fetchone()[0] == 500
    assert repo.connection.execute('PRAGMA wal_autocheckpoint').fetchone()[0] == 1000
    assert repo.connection.execute('PRAGMA journal_size_limit').fetchone()[0] == 67108864
    reader = open_read_only(str(db))
    assert reader.execute('PRAGMA query_only').fetchone()[0] == 1
    with pytest.raises(sqlite3.DatabaseError): reader.execute('DELETE FROM device_fingerprint_storage_state')
    reader.close(); repo.close()
    repo.initialize(); repo.close()


@POSIX
@pytest.mark.parametrize('existing', ['empty-v2', 'garbage', 'partial', 'v1', 'v3', 'nonempty'])
def test_existing_target_never_rewritten_or_lock_created(install, existing):
    db = install / 'evidence.sqlite3'
    if existing == 'empty-v2': assert provision(install).code == 'PROVISIONED'
    elif existing == 'garbage': db.write_bytes(b'not a database')
    else:
        with sqlite3.connect(db) as connection:
            connection.execute('CREATE TABLE existing(value)')
            if existing == 'nonempty': connection.execute("INSERT INTO existing VALUES ('keep')")
            connection.execute('PRAGMA user_version=' + {'partial': '0', 'v1': '1', 'v3': '3', 'nonempty': '2'}[existing])
    db.chmod(0o600)
    before = (db.stat().st_ino, db.read_bytes())
    files = {x.name: x.read_bytes() for x in install.iterdir()}
    result = provision(install)
    assert result.code == 'ALREADY_EXISTS_NO_CHANGE'
    assert (db.stat().st_ino, db.read_bytes()) == before
    assert {x.name: x.read_bytes() for x in install.iterdir()} == files


@POSIX
@pytest.mark.parametrize('suffix', ['-wal', '-shm', '-journal'])
def test_orphan_sidecar_no_new_lock_or_db(install, suffix):
    sidecar = install / ('evidence.sqlite3' + suffix); sidecar.write_bytes(b'foreign')
    assert provision(install).code == 'HOLD_ORPHAN_SIDECAR'
    assert list(install.iterdir()) == [sidecar] and sidecar.read_bytes() == b'foreign'


@POSIX
def test_runtime_remains_create_disabled(install):
    db = install / 'evidence.sqlite3'
    with pytest.raises(DeviceFingerprintStorageUnavailable):
        DeviceFingerprintRepository(str(db), max_db_bytes=67108864).initialize()
    assert not list(install.iterdir())


@POSIX
def test_runtime_writer_lock_blocks_provisioner_without_creating_stage(install):
    lock = install / 'evidence.writer.lock'
    with writer_lock(str(lock)):
        before = lock.read_bytes()
        assert provision(install).code == 'HOLD_WRITER_LOCKED'
        assert lock.read_bytes() == before
        assert {x.name for x in install.iterdir()} == {lock.name}


def test_native_windows_and_other_platforms_fail_before_filesystem(monkeypatch, capsys):
    monkeypatch.setattr(p.sys, 'platform', 'win32')
    monkeypatch.setattr(p, '_parent', lambda *a: pytest.fail('Windows filesystem mutation'))
    result = p.provision_empty_v2(settings(Path('/safe')), artifact_identity=IDENTITY)
    assert result.code == 'HOLD_PLATFORM_UNSUPPORTED' and result.database_generation_id is None
    monkeypatch.setattr(cli, 'get_settings', lambda: settings(Path('/safe')))
    monkeypatch.setattr(cli, 'capture_loaded_artifact_identity', lambda _: IDENTITY)
    assert cli.main(['provision-empty-v2']) == 1
    assert json.loads(capsys.readouterr().out)['code'] == 'HOLD_PLATFORM_UNSUPPORTED'


def test_cli_provision_is_separate_disabled_branch_with_bounded_json(monkeypatch, capsys):
    config = settings(Path('/safe'))
    calls = []
    monkeypatch.setattr(cli, 'get_settings', lambda: config)
    monkeypatch.setattr(cli, 'capture_loaded_artifact_identity', lambda _: IDENTITY)
    monkeypatch.setattr(cli, 'device_fingerprint_config_from_settings', lambda *_: pytest.fail('disabled config bypass'))
    monkeypatch.setattr(cli, 'DeviceFingerprintRuntime', lambda *a, **kw: pytest.fail('runtime started'))
    def invoke(value, **kwargs):
        assert value is config and kwargs['artifact_identity'] is IDENTITY
        calls.append(value)
        return p.ProvisionResult('PROVISIONED', str(uuid.uuid4()), IDENTITY.artifact_sha, IDENTITY.artifact_tree)
    monkeypatch.setattr(p, 'provision_empty_v2', invoke)
    assert cli.main(['provision-empty-v2']) == 0 and len(calls) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload['code'] == 'PROVISIONED' and 'unusable' not in str(payload)


@pytest.mark.parametrize('argument', ['--db-path', '--force', '--uuid', '--sql', '--generation'])
def test_cli_has_no_operator_override_seam(argument, monkeypatch):
    monkeypatch.setattr(cli, 'get_settings', lambda: pytest.fail('invalid args reached settings'))
    with pytest.raises(SystemExit) as error: cli.main(['provision-empty-v2', argument, 'untrusted'])
    assert error.value.code == 2


def test_cli_source_identity_failure_no_provision_and_no_secret(monkeypatch, capsys):
    monkeypatch.setattr(cli, 'get_settings', lambda: {})
    monkeypatch.setattr(cli, 'capture_loaded_artifact_identity', lambda _: (_ for _ in ()).throw(ValueError('SECRET_CANARY')))
    monkeypatch.setattr(p, 'provision_empty_v2', lambda *a, **kw: pytest.fail('no source identity'))
    assert cli.main(['provision-empty-v2']) == 1
    assert json.loads(capsys.readouterr().out)['code'] == 'HOLD_SOURCE_IDENTITY'


def test_nested_ancestry_exception_is_literal_role_bound_not_operator_input():
    import inspect
    assert p._PORTAL_PARENT == PurePosixPath('/opt/CaptivePortal/data')
    assert p._NESTED_PARENT == PurePosixPath('/opt/CaptivePortal/data/evidence')
    assert not inspect.signature(p._portal_role).parameters
    assert 'trusted_uid' not in inspect.signature(p.provision_empty_v2).parameters
