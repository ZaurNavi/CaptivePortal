"""Disposable G1 harness. Helpers never point at configured CaptivPortal DBs."""
from dataclasses import dataclass
import os
from pathlib import Path
import time
import uuid

from app.db_audit_coordinator import contracts as c
from app.db_audit_coordinator.admission import FixturePlan, FixtureAdmission, FixtureCompletionFence, FixtureFilesystem
from app.db_audit_coordinator.coordinator import Coordinator
from app.db_audit_coordinator.locks import LockSpec
from app.db_audit_coordinator.state_store import atomic_publish


@dataclass
class Lab:
    root: Path
    owner: LockSpec
    gate: LockSpec

    def coordinator(self,mode="pass",*,fence=None,sync=os.fsync,timeout=3):
        plan=FixturePlan(str(self.root),mode,timeout)
        return Coordinator(self.root,self.owner,self.gate,admission=FixtureAdmission(plan,self.owner.uid),
            fence=fence if fence is not None else FixtureCompletionFence(),filesystem=FixtureFilesystem(),sync=sync)


def lab(tmp_path):
    root=tmp_path/"private"
    root.mkdir(mode=0o700);root.chmod(0o700)
    for name in ("queue-owner.lock","heavy.lock","fixture.marker","source.sentinel"):
        path=root/name;path.write_bytes(b"disposable-fixture-only");path.chmod(0o600)
    uid=os.geteuid()
    def spec(name):
        path=root/name;metadata=path.stat()
        return LockSpec(str(path),uid,metadata.st_dev,metadata.st_ino)
    atomic_publish(root/"queue-state.v1.json",c.empty_state(),uid)
    return Lab(root,spec("queue-owner.lock"),spec("heavy.lock"))


def submit(subject,store="visits",origin="manual",key=None):
    return subject.submit(store,key or str(uuid.uuid4()),origin,c.scope(os.geteuid()))


def complete(subject):
    subject._wake_read.settimeout(6)
    subject._wake_read.recv(1)
    process=subject.process
    assert process is not None and process.returncode is not None
    assert subject.finish()
    assert process.wait(timeout=0)==process.returncode
    return process


def marker(laboratory,job,phase,timeout=5):
    path=laboratory.root/(job+"."+phase)
    deadline=time.monotonic()+timeout
    while not path.exists() and time.monotonic()<deadline:time.sleep(.01)
    assert path.exists(),phase
    return path


def cleanup(subject):
    process=subject.process
    if process is not None and process.poll() is None:
        if subject.cancel_fd is not None:
            try:os.write(subject.cancel_fd,b"c")
            except OSError:pass
        try:process.wait(timeout=4)
        except Exception:process.kill();process.wait(timeout=3)
    if subject.cancel_fd is not None:
        os.close(subject.cancel_fd);subject.cancel_fd=None
    subject.close()
