import copy
import os
import stat
import sys

import pytest

from app.db_audit_coordinator import contracts as c
from app.db_audit_coordinator.locks import PermanentLock
from app.db_audit_coordinator.state_store import StateStore,atomic_publish
from tests.db_audit_coordinator import lab,submit,cleanup

pytestmark=pytest.mark.skipif(sys.platform!='linux',reason='Real Linux protected JSON fsync/rename contract')


def test_file_then_directory_fsync_precedes_ack_and_queue_inode_may_replace(tmp_path):
    fixture=lab(tmp_path);calls=[]
    def sync(fd):calls.append('dir' if stat.S_ISDIR(os.fstat(fd).st_mode) else 'file');os.fsync(fd)
    subject=fixture.coordinator(sync=sync)
    try:
        old=subject.store.identity;result=submit(subject)
        assert result['status']=='queued' and calls==['file','dir','file','dir']
        assert subject.store.identity!=old
        assert os.fstat(subject.owner.fd).st_ino==fixture.owner.inode
        assert subject.store.read()['jobs'][0]['job_id']==result['job']['job_id']
    finally:cleanup(subject)


@pytest.mark.parametrize('phase',['file','dir'])
def test_F06_sync_failure_has_no_false_ack_and_poisoned_writer_stops(tmp_path,phase):
    fixture=lab(tmp_path);subject=fixture.coordinator();key='12345678-1234-1234-1234-1234567890ab'
    def broken(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode)==(phase=='dir'):raise OSError('PRIVATE_FAULT')
        os.fsync(fd)
    subject.store.sync=broken
    try:
        with pytest.raises(c.CoordinatorError,match='queue_unknown' if phase=='dir' else 'queue_unavailable'):
            submit(subject,key=key)
        with pytest.raises(c.CoordinatorError):subject.dispatch_one()
    finally:cleanup(subject)
    restarted=fixture.coordinator()
    try:
        retry=submit(restarted,key=key)
        assert retry['status']==('duplicate' if phase=='dir' else 'queued')
        assert len(restarted.store.read()['jobs'])==1
    finally:cleanup(restarted)


@pytest.mark.parametrize('kind',['missing','garbage','symlink','permission','inode'])
def test_F17_queue_missing_corruption_permissions_and_replacement_never_reset(tmp_path,kind):
    fixture=lab(tmp_path);subject=fixture.coordinator();path=fixture.root/'queue-state.v1.json'
    if kind=='missing':path.unlink()
    if kind=='garbage':path.write_bytes(b'bad-json')
    if kind=='symlink':path.unlink();path.symlink_to(fixture.root/'source.sentinel')
    if kind=='permission':path.chmod(0o666)
    if kind=='inode':
        replacement=fixture.root/'replacement';replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);os.replace(replacement,path)
    try:
        with pytest.raises(c.CoordinatorError,match='queue_unavailable'):subject.store.read()
        with pytest.raises(c.CoordinatorError):submit(subject)
        if kind=='missing':assert not path.exists()
    finally:cleanup(subject)


def test_unprovisioned_queue_never_created_and_orphan_temp_never_promoted(tmp_path):
    fixture=lab(tmp_path);path=fixture.root/'queue-state.v1.json';raw=path.read_bytes();path.unlink()
    (fixture.root/'.queue-orphan.tmp').write_bytes(raw)
    with pytest.raises(c.CoordinatorError):fixture.coordinator()
    assert not path.exists()
