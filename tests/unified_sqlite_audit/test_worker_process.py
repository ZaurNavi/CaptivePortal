"""Actual child exit/reaping and cancellation; cgroup/RO admission MOCKED.

These tests are lifecycle evidence, NOT native sandbox or swap qualification.
"""
from dataclasses import replace
import json
import os
from pathlib import Path
import sqlite3
import time

import pytest
from app.unified_sqlite_audit import runner
from test_snapshot import fixture


def complete_child(channel,job,validators):
    os.setsid()
    image=sqlite3.connect(':memory:')
    image.execute('SELECT 1').fetchone();image.close()
    channel.send_bytes(json.dumps(dict(result={'pid_for_lifecycle_test':os.getpid()},reason='complete')).encode())
    channel.close()


def broken_child(channel,job,validators):
    os.setsid();channel.send_bytes(b'not JSON');channel.close()


def waiting_child(channel,job,validators):
    os.setsid()
    while True:time.sleep(0.05)


@pytest.mark.skipif(os.name!='posix',reason='Linux real process session/reaping lifecycle, mocked cgroup view')
@pytest.mark.parametrize('child',[complete_child,broken_child,waiting_child])
def test_actual_child_exit_fd_ram_release_and_cancel_no_deadline(tmp_path,monkeypatch,child):
    writer,job=fixture(tmp_path);job=replace(job,cgroup='/fixture.service')
    original=Path.read_text
    def read(path,*args,**kwargs):
        if str(path)=='/sys/fs/cgroup/fixture.service/cgroup.procs':return str(os.getpid())
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'read_text',read)
    monkeypatch.setattr(runner,'native_admission',lambda j:True)
    monkeypatch.setattr(runner,'_child',child)
    start=time.monotonic()
    try:
        outcome=runner.SerialWorker().run(job,lambda:child is waiting_child and time.monotonic()-start>0.1)
        assert outcome.released is True
        if child is complete_child:
            assert outcome.reason=='complete'
            assert not Path('/proc/'+str(outcome.result['pid_for_lifecycle_test'])).exists()
        else:
            assert outcome.result is None
            assert outcome.reason==('cancelled' if child is waiting_child else 'worker_failed')
    finally:writer.close()
