"""Minimal disposable tmpfs self-report delivery; NOT UID isolation evidence."""
from datetime import datetime,timedelta,timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

import pytest

from app.network_metadata_projection import operations_health as h
from app.device_fingerprint_sensor import operations_metadata as m
from tests.admin_web.test_sensor_metadata_native import demote,PORTAL,READERS,PRIVATE

ROOT=Path(__file__).resolve().parents[2]
native=pytest.mark.skipif(sys.platform!='linux' or not hasattr(os,'geteuid') or os.geteuid()!=0,
    reason='Linux root disposable NI02B shared-UID tmpfs self-report mechanics')
DRIVER=r'''
import json,os,sys,time,threading,sqlite3
from datetime import datetime,timezone
from app.network_metadata_projection.operations_health import Channel,HealthPublisher
from app.operations_health import ni02_health,DEPENDENCIES,NI02_UNIT
from app.device_fingerprint_sensor.operations_metadata import stamp
def blocked(*a,**k):raise AssertionError('SQL/fsync forbidden for health')
sqlite3.connect=blocked;os.fsync=os.fdatasync=blocked
def io():
 with open('/proc/self/io') as f:return {k:int(v) for k,v in (line.split(':',1) for line in f)}
count=2143 if sys.argv[2]=='backlog' else 0
health=ni02_health('attribution_unavailable' if count else 'usable',dict.fromkeys(DEPENDENCIES[NI02_UNIT],True),count,native_reason='pending_attribution' if count else None)
at=stamp(datetime.now(timezone.utc))
p=HealthPublisher(enabled=True,channel=lambda:Channel(os.getuid(),sys.argv[1]))
before=io();wall=time.monotonic();cpu=time.process_time()
ok=p.publish(health,dict(source_confirmed_at=at,writer_committed_at=at,pending_observed_at=at),threading.Event())
elapsed=time.monotonic()-wall;cpu=time.process_time()-cpu;after=io()
print(json.dumps(dict(ok=ok,pid=os.getpid(),wall=elapsed,cpu=cpu,threads=len(threading.enumerate()),
 io_delta={k:after[k]-before[k] for k in before})),flush=True)
sys.stdin.readline()
'''


@native
@pytest.mark.parametrize('case',['healthy','backlog','missing','stale','malformed','pid','boot','start_ticks'])
def test_ni02_shared_UID_report_shape_freshness_and_bounded_IO(case,record_property):
    folder=Path(tempfile.mkdtemp(prefix='issue295-wp3-ni02-',dir='/run'));process=None
    try:
        folder.chmod(0o755);child=folder/'ni02b';child.mkdir();os.chown(child,PORTAL,PRIVATE);child.chmod(0o700)
        code=folder/'code'
        for name in ('app/network_metadata_projection/operations_health.py','app/device_fingerprint_sensor/operations_metadata.py','app/operations_health.py','app/operations_verification.py'):
            target=code/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes());target.chmod(0o644)
        for directory in [code,*[p for p in code.rglob('*') if p.is_dir()]]:directory.chmod(0o755)
        env=dict(os.environ,PYTHONPATH=str(code),PYTHONDONTWRITEBYTECODE='1')
        process=subprocess.Popen(['/usr/bin/python3.10','-c',DRIVER,str(child),case],env=env,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,preexec_fn=demote(PORTAL,PRIVATE,[]))
        line=process.stdout.readline();assert line,process.stderr.read()
        accounting=json.loads(line);assert accounting['ok'],accounting
        path=child/h.REPORT;value=json.loads(path.read_bytes())
        assert path.stat().st_size<=4096 and accounting['threads']==1 and accounting['io_delta']['write_bytes']==0
        assert value['provenance']=='source_self_reported_shared_uid'
        service=dict(operational_state='running',main_pid=accounting['pid'],started_at_utc=value['sample_time_utc'])
        now=m.parse_stamp(value['sample_time_utc']);boot=value['sample_boottime_ns']
        if case=='missing':path.unlink()
        elif case=='malformed':path.write_bytes(b'{"schema_version":"PRIVATE_CANARY"}')
        elif case in {'pid','boot','start_ticks'}:
            if case=='pid':value['producer']['pid']+=1
            elif case=='boot':value['producer']['boot_id']='00000000-0000-4000-8000-000000000001'
            else:value['producer']['start_ticks']+=1
            path.write_bytes(json.dumps(value).encode())
        elif case=='stale':now+=timedelta(seconds=181);boot+=181_000_000_000
        reader=h.HealthReader(channel=lambda:h.Channel(PORTAL,str(child)),boottime=lambda:boot)
        result=reader.read(service,now,deadline=time.monotonic()+1)
        assert result['status']==('unknown' if case in {'missing','malformed','pid','boot','start_ticks'} else 'stale' if case=='stale' else 'fresh')
        if case in {'healthy','backlog'}:
            assert result['health']['state']=='healthy'
            assert result['health']['pending_count']==(2143 if case=='backlog' else 0)
        assert 'PRIVATE_CANARY' not in json.dumps(result)
        record_property('ni02_shared_uid_informational',json.dumps(dict(case=case,accounting=accounting,
            report_bytes=len(json.dumps(value).encode()),provenance=value['provenance'],result=result),sort_keys=True))
    finally:
        if process is not None:
            try:process.communicate('stop\n',timeout=2)
            except subprocess.TimeoutExpired:process.kill();process.communicate(timeout=2)
        shutil.rmtree(folder)
