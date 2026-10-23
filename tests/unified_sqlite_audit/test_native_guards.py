"""Deterministic guard decision tests; mocked kernel views are NOT OS acceptance."""
from dataclasses import replace
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.unified_sqlite_audit.model import AuditError
from app.unified_sqlite_audit.snapshot import native_admission
from test_snapshot import fixture


@pytest.fixture
def kernel_view(tmp_path,monkeypatch):
    writer,job=fixture(tmp_path)
    job=replace(job,cgroup='/audit.service')
    files={
        '/proc/self/status':'CapEff:\t0000000000000000\nNoNewPrivs:\t1\n',
        '/proc/self/cgroup':'0::/audit.service\n',
        '/proc/self/mountinfo':'1 0 0:1 / /sys/fs/cgroup ro - cgroup2 cgroup rw\n',
        '/proc/meminfo':'MemAvailable: 1048576 kB\n',
        '/sys/fs/cgroup/audit.service/memory.max':str(256*1024*1024),
        '/sys/fs/cgroup/audit.service/memory.swap.max':'0',
        '/sys/fs/cgroup/audit.service/memory.swap.current':'0',
        '/sys/fs/cgroup/audit.service/memory.current':str(1024*1024),
        '/sys/fs/cgroup/memory.swap.current':'0',
    }
    read=Path.read_text;exists=Path.exists
    def read_text(path,*args,**kwargs):
        if str(path) in files:return files[str(path)]
        if str(path).startswith('/sys/fs/cgroup/'):raise FileNotFoundError()
        return read(path,*args,**kwargs)
    def present(path):
        return str(path) in files if str(path).startswith('/sys/fs/cgroup/') else exists(path)
    monkeypatch.setattr(Path,'read_text',read_text)
    monkeypatch.setattr(Path,'exists',present)
    monkeypatch.setattr(os,'statvfs',lambda path:SimpleNamespace(f_flag=getattr(os,'ST_RDONLY',1)))
    try:yield files,job
    finally:writer.close()


@pytest.mark.skipif(os.name!='posix',reason='Linux cgroup-v2 admission decision contract; mocked views only')
def test_guard_accepts_only_finite_effective_no_swap_qualified_view(kernel_view):
    files,job=kernel_view
    assert native_admission(job) is True
    files['/sys/fs/cgroup/memory.swap.max']='max'  # Leaf zero still enforces no swap.
    assert native_admission(job) is True
    files['/sys/fs/cgroup/memory.max']=str(128*1024*1024)
    assert native_admission(job) is True


@pytest.mark.skipif(os.name!='posix',reason='Linux cgroup-v2 admission negatives; mocked views only')
@pytest.mark.parametrize('key,value',[
    ('/proc/self/status','CapEff:\t0000000000000001\nNoNewPrivs:\t1\n'),
    ('/proc/self/status','CapEff:\t0\nNoNewPrivs:\t0\n'),
    ('/proc/self/cgroup','0::/\n'),
    ('/proc/self/mountinfo','1 0 0:1 /hidden /sys/fs/cgroup ro - cgroup2 cgroup rw\n'),
    ('/sys/fs/cgroup/audit.service/memory.max','max'),
    ('/sys/fs/cgroup/audit.service/memory.max','0'),
    ('/sys/fs/cgroup/audit.service/memory.swap.max','max'),
    ('/sys/fs/cgroup/audit.service/memory.swap.current','1'),
    ('/sys/fs/cgroup/memory.swap.current','1'),
    ('/sys/fs/cgroup/audit.service/memory.current',str(240*1024*1024)),
    ('/proc/meminfo','MemAvailable: 1 kB\n'),
    ('/sys/fs/cgroup/audit.service/memory.swap.current','unknown'),
])
def test_guard_unknown_unsafe_or_pressure_rejects_before_source_open(kernel_view,monkeypatch,key,value):
    import sqlite3
    files,job=kernel_view;files[key]=value
    monkeypatch.setattr(sqlite3,'connect',lambda *a,**k:pytest.fail('source opened before admission'))
    with pytest.raises(AuditError,match='resource_unqualified'):native_admission(job)


@pytest.mark.skipif(os.name!='posix',reason='Linux mount RO admission negative; no mount mutations')
def test_declaration_of_ro_is_insufficient_without_actual_mount_ro(kernel_view,monkeypatch):
    _,job=kernel_view
    monkeypatch.setattr(os,'statvfs',lambda path:SimpleNamespace(f_flag=0))
    with pytest.raises(AuditError,match='resource_unqualified'):native_admission(job)
