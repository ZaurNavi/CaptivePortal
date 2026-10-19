import os
import subprocess
import sys

import pytest

from app.db_audit_coordinator import contracts as c
from app.db_audit_coordinator.locks import PermanentLock,trusted_open
from tests.db_audit_coordinator import lab

pytestmark=pytest.mark.skipif(sys.platform!='linux',reason='Real Linux flock inode/lifetime contract')


def test_F01_real_second_pid_cannot_acquire_permanent_gate(tmp_path):
    fixture=lab(tmp_path);lock=PermanentLock(fixture.gate).acquire()
    code='from app.db_audit_coordinator.locks import *;from app.db_audit_coordinator.contracts import CoordinatorError;import sys;\nspec=LockSpec(sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),int(sys.argv[4]));\ntry:PermanentLock(spec).acquire()\nexcept CoordinatorError as e:sys.exit(42 if e.code=="gate_busy" else 43)\n'
    try:
        process=subprocess.run([sys.executable,'-c',code,fixture.gate.path,str(fixture.gate.uid),str(fixture.gate.device),str(fixture.gate.inode)],timeout=4)
        assert process.returncode==42 and lock.fd is not None
    finally:lock.close()
    with PermanentLock(fixture.gate):pass


@pytest.mark.parametrize('kind',['missing','symlink','permission','replacement','directory','hardlink','unsafe-parent'])
def test_F17_attested_gate_inode_never_recreated_or_followed(tmp_path,kind):
    fixture=lab(tmp_path);path=fixture.root/'heavy.lock'
    if kind in {'missing','symlink','directory','hardlink'}:path.unlink()
    if kind=='symlink':path.symlink_to(fixture.root/'source.sentinel')
    if kind=='permission':path.chmod(0o666)
    if kind=='directory':path.mkdir()
    if kind=='hardlink':os.link(fixture.root/'source.sentinel',path)
    if kind=='unsafe-parent':fixture.root.chmod(0o777)
    if kind=='replacement':
        replacement=fixture.root/'replacement.lock'
        replacement.write_bytes(b'new-inode');replacement.chmod(0o600)
        assert replacement.stat().st_ino!=fixture.gate.inode
        os.replace(replacement,path)
    try:
        with pytest.raises(c.CoordinatorError):PermanentLock(fixture.gate).acquire()
    finally:
        if kind=='unsafe-parent':fixture.root.chmod(0o700)
    if kind=='missing':assert not path.exists()


def test_single_queue_owner_and_runtime_replacement_fail_closed(tmp_path):
    fixture=lab(tmp_path)
    with PermanentLock(fixture.owner) as owner:
        with pytest.raises(c.CoordinatorError,match='gate_busy'):PermanentLock(fixture.owner).acquire()
        path=fixture.root/'queue-owner.lock';path.unlink();path.write_bytes(b'new');path.chmod(0o600)
        with pytest.raises(c.CoordinatorError,match='unsafe_path'):owner.check()
