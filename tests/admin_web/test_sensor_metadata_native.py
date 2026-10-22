"""Disposable tmpfs/three-principal proofs, never installed or production paths."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time

import pytest

from app.device_fingerprint_sensor import operations_metadata as m

native = pytest.mark.skipif(sys.platform != "linux" or not hasattr(os, "geteuid") or os.geteuid() != 0,
    reason="Linux root-only disposable tmpfs Sensor/Portal principal isolation proof")
SENSOR, PORTAL, OUTSIDER, READERS, PRIVATE = 62031, 62032, 62033, 62034, 62035
ROOT = Path(__file__).parents[2]

SENSOR_SCRIPT = r'''
import json, os, sys, threading, time, sqlite3
from app.device_fingerprint_sensor.operations_metadata import SensorMetadataPublisher, Channel
directory, paths = sys.argv[1], json.loads(sys.argv[2])
p = SensorMetadataPublisher(paths, channel=lambda:Channel(os.getuid(), 62034, directory), enabled=True)
if len(sys.argv)>3:
    from app.operations_health import sensor_health, DEPENDENCIES, SENSOR_UNIT
    p.health_provider=lambda:sensor_health(sys.argv[3],dict.fromkeys(DEPENDENCIES[SENSOR_UNIT],True))
def blocked(*args,**kwargs): raise AssertionError("DB/fsync forbidden for metadata")
sqlite3.connect = blocked
os.fsync = os.fdatasync = blocked
def counters():
    with open('/proc/self/io') as stream:
        return {k:int(v) for k,v in (line.split(':',1) for line in stream)}
before = counters()
cpu, wall = time.process_time(), time.monotonic()
ok = p.publish(threading.Event())
elapsed, cpu = time.monotonic()-wall, time.process_time()-cpu
after = counters()
print(json.dumps(dict(ok=ok,pid=os.getpid(),wall_seconds=elapsed,cpu_seconds=cpu,
    io_delta={k:after[k]-before[k] for k in before},threads=len(threading.enumerate()))), flush=True)
for command in sys.stdin:
    if command.strip() == "fail":
        old = os.replace
        os.replace = lambda *a,**kw: (_ for _ in ()).throw(OSError("PRIVATE_CANARY"))
        p.last_attempt = None
        result = p.publish(threading.Event())
        os.replace = old
        print(json.dumps(dict(ok=result)), flush=True)
    else: break
'''
PORTAL_SCRIPT = r'''
from datetime import datetime, timezone
import json, os, sys, time
from app.device_fingerprint_sensor.operations_metadata import Channel, SensorMetadataReader
directory, service, raw_path = sys.argv[1], json.loads(sys.argv[2]), sys.argv[3]
denied = False
try:
    os.open(raw_path, os.O_RDONLY)
except PermissionError:
    denied = True
reader = SensorMetadataReader(channel=lambda:Channel(62031,62034,directory))
result = reader.read(service,datetime.now(timezone.utc),deadline=time.monotonic()+1)
print(json.dumps(dict(report=result,raw_denied=denied)))
'''


def demote(uid, gid, groups):
    def apply():
        os.setgroups(groups)
        os.setgid(gid)
        os.setuid(uid)
        os.umask(0o027)
    return apply


@pytest.fixture
def channel(request):
    if sys.platform != "linux" or not hasattr(os, "geteuid") or os.geteuid() != 0:
        pytest.skip("Linux root-only disposable tmpfs Sensor/Portal principal isolation proof")
    folder = Path(tempfile.mkdtemp(prefix="issue295-wp2-", dir="/run"))
    process = None
    try:
        folder.chmod(0o755)
        child = folder / m.CHILD
        child.mkdir()
        os.chown(child, SENSOR, READERS)
        child.chmod(0o2750)
        private = folder / "private"
        private.mkdir()
        os.chown(private, SENSOR, PRIVATE)
        private.chmod(0o700)
        paths = {"network_attribution": str(private / "attribution.sqlite3"), "sensor_spool": str(private / "spool.sqlite3")}
        for path in paths.values():
            Path(path).write_bytes(b"synthetic non-database source canary")
            os.chown(path, SENSOR, PRIVATE)
            Path(path).chmod(0o600)
        # journal is a real distinct file; WAL/SHM are verified ENOENT.
        journal = paths["sensor_spool"] + "-journal"
        Path(journal).write_bytes(b"journal-canary")
        os.chown(journal, SENSOR, PRIVATE)
        Path(journal).chmod(0o600)
        initial = {p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in [*paths.values(), journal]}
        # Disposable principals must not receive access to the developer home.
        # Export ONLY the exact pure protocol module into this root-owned Lab
        # sandbox, not a changed source copy or a production source path.
        code = folder / 'code'
        module = code / 'app/device_fingerprint_sensor/operations_metadata.py'
        module.parent.mkdir(parents=True)
        for directory in (code, code / 'app', module.parent): directory.chmod(0o755)
        raw_source = (ROOT / 'app/device_fingerprint_sensor/operations_metadata.py').read_bytes()
        module.write_bytes(raw_source); module.chmod(0o644)
        assert module.read_bytes() == raw_source
        checks = code / 'app/operations_verification.py'
        checks.write_bytes((ROOT / 'app/operations_verification.py').read_bytes()); checks.chmod(0o644)
        variant = getattr(request, 'param', None)
        if variant is not None:
            common = code / 'app/operations_health.py'
            common.write_bytes((ROOT / 'app/operations_health.py').read_bytes()); common.chmod(0o644)
        env = dict(os.environ, PYTHONPATH=str(code), PYTHONDONTWRITEBYTECODE="1")
        process = subprocess.Popen(['/usr/bin/python3.10', '-c', SENSOR_SCRIPT, str(folder), json.dumps(paths), *([] if variant is None else [variant])],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
            preexec_fn=demote(SENSOR, PRIVATE, []))
        line = process.stdout.readline()
        assert line, process.stderr.read()
        first = json.loads(line)
        assert first['ok'] is True, process.stderr.read() if process.poll() is not None else first
        report_file = child / m.REPORT
        value = json.loads(report_file.read_bytes())
        service = dict(operational_state="running", main_pid=first['pid'], started_at_utc=value['sample_time_utc'])
        yield dict(folder=folder, child=child, report=report_file, paths=paths, process=process, env=env, service=service, value=value, accounting=first,variant=variant)
        assert {p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in initial} == initial
    finally:
        if process is not None:
            try:
                process.communicate('stop\n', timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=2)
        shutil.rmtree(folder)


def portal(channel, uid=PORTAL, groups=None):
    result = subprocess.run(['/usr/bin/python3.10', '-c', PORTAL_SCRIPT, str(channel['folder']),
        json.dumps(channel['service']), channel['paths']['sensor_spool']], env=channel['env'],
        preexec_fn=demote(uid, PRIVATE+1, [READERS] if groups is None else groups),
        capture_output=True, text=True, timeout=2, check=True)
    return json.loads(result.stdout)


@native
@pytest.mark.parametrize('fault', ['valid', 'missing', 'oversize', 'truncated', 'symlink', 'fifo', 'hardlink',
    'file-mode', 'file-owner', 'file-group', 'dir-mode', 'dir-owner', 'dir-group', 'parent-mode', 'dir-symlink',
    'pid', 'boot', 'start', 'extra-field', 'duplicate-key', 'schema'])
def test_native_cross_principal_report_without_raw_database_access(channel, fault):
    path, value = channel['report'], channel['value']
    if fault == 'missing': path.unlink()
    elif fault == 'oversize': path.write_bytes(b' ' * 4097)
    elif fault == 'truncated': path.write_bytes(b'{')
    elif fault == 'symlink':
        path.rename(path.with_name('original'))
        path.symlink_to(path.with_name('original'))
    elif fault == 'fifo': path.unlink(); os.mkfifo(path)
    elif fault == 'hardlink': os.link(path, path.with_name('alias'))
    elif fault == 'file-mode': path.chmod(0o666)
    elif fault == 'file-owner': os.chown(path, OUTSIDER, READERS)
    elif fault == 'file-group': os.chown(path, SENSOR, PRIVATE)
    elif fault == 'dir-mode': channel['child'].chmod(0o2770)
    elif fault == 'dir-owner': os.chown(channel['child'], OUTSIDER, READERS)
    elif fault == 'dir-group': os.chown(channel['child'], SENSOR, PRIVATE)
    elif fault == 'parent-mode': channel['folder'].chmod(0o777)
    elif fault == 'dir-symlink':
        channel['child'].rename(channel['child'].with_name('original-dir'))
        channel['child'].symlink_to(channel['child'].with_name('original-dir'))
    elif fault in {'pid', 'boot', 'start', 'extra-field', 'schema', 'duplicate-key'}:
        if fault == 'pid': value['producer']['pid'] += 1
        if fault == 'boot': value['producer']['boot_id'] = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
        if fault == 'start': value['producer']['start_ticks'] += 1
        if fault == 'extra-field': value['path'] = '/PRIVATE_CANARY'
        if fault == 'schema': value['schema_version'] = 'other'
        raw = json.dumps(value)
        if fault == 'duplicate-key': raw = raw[:-1] + ',"sequence":1}'
        path.write_text(raw)
    result = portal(channel)
    assert result['raw_denied'] is True
    assert result['report']['status'] == ('fresh' if fault == 'valid' else 'unknown')
    if fault == 'valid':
        rows = result['report']['stores']['sensor_spool']
        assert rows['wal']['bytes'] == rows['shm']['bytes'] == 0
        assert rows['journal']['bytes'] == len(b'journal-canary')
    else:
        assert result['report']['stores'] is None
        assert 'PRIVATE_CANARY' not in json.dumps(result)


@native
def test_native_outsider_cannot_read_export_or_raw_database(channel):
    result = portal(channel, uid=OUTSIDER, groups=[])
    assert result['raw_denied'] is True and result['report']['status'] == 'unknown'


@native
@pytest.mark.parametrize('age,boot_age,status', [(0,0,'fresh'),(180,180,'fresh'),(180.001,180.001,'stale'),
    (-1,0,'unknown'), (1,-1,'unknown'),(0,6,'unknown'),(200,0,'unknown')])
def test_native_freshness_clock_skew_and_180_second_ttl(channel, age, boot_age, status):
    value = channel['value']
    reader = m.SensorMetadataReader(channel=lambda:m.Channel(SENSOR,READERS,str(channel['folder'])),
        boottime=lambda:value['sample_boottime_ns']+int(boot_age*1e9))
    result = reader.read(channel['service'],m.parse_stamp(value['sample_time_utc'])+timedelta(seconds=age),deadline=time.monotonic()+1)
    assert result['status'] == status


@native
@pytest.mark.parametrize('mutation', ['sequence', 'same-sequence-change', 'epoch', 'time-regression'])
def test_native_epoch_replay_and_invalid_report_do_not_erase_last_good_identity(channel, mutation):
    value = channel['value']
    reader = m.SensorMetadataReader(channel=lambda:m.Channel(SENSOR,READERS,str(channel['folder'])))
    def read(): return reader.read(channel['service'],datetime.now(timezone.utc),deadline=time.monotonic()+1)
    assert read()['status'] == 'fresh'
    previous = reader.last
    if mutation == 'sequence': value['sequence'] = 0
    elif mutation == 'same-sequence-change': value['stores']['sensor_spool']['journal']['bytes'] += 1
    elif mutation == 'epoch': value['epoch'] = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
    else:
        value['sequence'] += 1
        value['sample_time_utc'] = m.stamp(m.parse_stamp(value['sample_time_utc'])-timedelta(seconds=1))
        value['sample_boottime_ns'] -= 1000000000
    channel['report'].write_text(json.dumps(value))
    assert read()['status'] == 'unknown' and reader.last == previous


@native
def test_native_failed_replace_preserves_previous_atomic_report_and_cleans_only_own_temp(channel):
    before = channel['report'].read_bytes()
    process = channel['process']
    process.stdin.write('fail\n'); process.stdin.flush()
    assert json.loads(process.stdout.readline()) == {'ok':False}
    assert channel['report'].read_bytes() == before
    assert list(channel['child'].iterdir()) == [channel['report']]
    assert portal(channel)['report']['status'] == 'fresh'


@native
def test_native_atomic_replace_during_read_is_rejected(channel, monkeypatch):
    old = m.os.read
    fired = []
    def raced(fd, size):
        raw = old(fd, size)
        if size == m.LIMIT+1 and not fired:
            fired.append(1)
            replacement = channel['report'].with_name('replacement')
            replacement.write_bytes(channel['report'].read_bytes())
            os.chown(replacement,SENSOR,READERS); replacement.chmod(0o640)
            os.replace(replacement,channel['report'])
        return raw
    monkeypatch.setattr(m.os,'read',raced)
    reader = m.SensorMetadataReader(channel=lambda:m.Channel(SENSOR,READERS,str(channel['folder'])))
    result = reader.read(channel['service'],datetime.now(timezone.utc),deadline=time.monotonic()+1)
    assert fired == [1] and result['status'] == 'unknown'


@native
def test_native_dead_process_rejected_and_new_process_epoch_replaces_old(channel):
    reader = m.SensorMetadataReader(channel=lambda:m.Channel(SENSOR,READERS,str(channel['folder'])))
    def read(service): return reader.read(service,datetime.now(timezone.utc),deadline=time.monotonic()+1)
    assert read(channel['service'])['status'] == 'fresh'
    old_epoch = reader.last[1]
    channel['process'].kill(); channel['process'].wait(timeout=2)
    assert read(channel['service'])['status'] == 'unknown'
    new = subprocess.Popen(['/usr/bin/python3.10','-c',SENSOR_SCRIPT,str(channel['folder']),json.dumps(channel['paths'])],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=channel['env'],
        preexec_fn=demote(SENSOR,PRIVATE,[]))
    try:
        first = json.loads(new.stdout.readline())
        assert first['ok'] is True
        value = json.loads(channel['report'].read_bytes())
        service = dict(channel['service'],main_pid=first['pid'],started_at_utc=value['sample_time_utc'])
        assert read(service)['status'] == 'fresh' and reader.last[1] != old_epoch
    finally:
        new.communicate('stop\n',timeout=2)


@native
def test_native_descriptor_cleanup_and_tmpfs_not_optional(channel, monkeypatch):
    reader = m.SensorMetadataReader(channel=lambda:m.Channel(SENSOR,READERS,str(channel['folder'])))
    count = len(list(Path('/proc/self/fd').iterdir()))
    for _ in range(20):
        assert reader.read(channel['service'],datetime.now(timezone.utc),deadline=time.monotonic()+1)['status'] == 'fresh'
    assert len(list(Path('/proc/self/fd').iterdir())) == count
    directory = os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    try:
        # Deterministic negative f_type, even if the host's / also uses tmpfs.
        from types import SimpleNamespace
        def other_filesystem(fd, buffer):
            m.ctypes.cast(buffer,m.ctypes.POINTER(m.ctypes.c_long))[0] = 0xEF53
            return 0
        monkeypatch.setattr(m.ctypes,'CDLL',lambda *args,**kwargs:SimpleNamespace(fstatfs=other_filesystem))
        with pytest.raises(m.MetadataUnavailable): m._tmpfs(directory)
    finally:
        os.close(directory)


@native
def test_native_missing_channel_no_provisioning_and_no_output_created(channel):
    path = str(channel['folder'] / 'not-provisioned')
    reader = m.SensorMetadataReader(channel=lambda:m.Channel(SENSOR,READERS,path))
    assert reader.read(channel['service'],datetime.now(timezone.utc),deadline=time.monotonic()+1)['status'] == 'unknown'
    assert not Path(path).exists()
    assert channel['accounting']['threads'] == 1
    assert channel['accounting']['io_delta']['write_bytes'] == 0


@native
@pytest.mark.parametrize('channel',['ready','degraded','unavailable','initializing','stopping'],indirect=True)
def test_WP3_native_versioned_health_uses_same_trusted_metadata_channel(channel,record_property):
    result=portal(channel)
    assert result['raw_denied'] and result['report']['status']=='fresh'
    value=json.loads(channel['report'].read_bytes())
    assert value['schema_version']==m.SCHEMA_V2 and len(channel['report'].read_bytes())<=4096
    expected={'ready':'healthy','degraded':'degraded','unavailable':'unavailable','initializing':'unknown','stopping':'unknown'}
    assert result['report']['health']['state']==expected[channel['variant']]
    assert result['report']['health']==value['application_health']
    assert result['report']['producer']['pid']==channel['service']['main_pid']
    assert channel['accounting']['threads']==1 and channel['accounting']['io_delta']['write_bytes']==0
    record_property('wp3_native_sensor',json.dumps(dict(schema=value['schema_version'],health=result['report']['health'],
        bytes=len(channel['report'].read_bytes()),raw_denied=True,accounting=channel['accounting']),sort_keys=True))


@native
@pytest.mark.parametrize('channel',['degraded'],indirect=True)
@pytest.mark.parametrize('fault',['invalid_health','forged_green','restarted','expired'])
def test_WP3_native_invalid_report_cannot_erase_degraded_or_refresh_TTL(channel,fault):
    from app.admin_web.operations_health import SensorHealthEvidence,project
    reader=m.SensorMetadataReader(channel=lambda:m.Channel(SENSOR,READERS,str(channel['folder'])))
    cache=SensorHealthEvidence(reader);now=datetime.now(timezone.utc);service=channel['service']
    first=reader.read(service,now,deadline=time.monotonic()+1)
    retained=cache.collect(first,service,now)
    assert project(retained)['state']=='degraded'
    value=json.loads(channel['report'].read_bytes())
    if fault=='invalid_health':value['application_health']['reason']='/PRIVATE_CANARY'
    elif fault=='forged_green':value['application_health']['state']='healthy'
    elif fault=='restarted':service=dict(service,main_pid=service['main_pid']+1000000)
    else:value['sequence']=0
    channel['report'].write_text(json.dumps(value))
    bad=reader.read(service,now,deadline=time.monotonic()+1)
    assert bad['status']=='unknown'
    kept=cache.collect(bad,service,now)
    result=project(kept,boottime=lambda:retained['expires']+1 if fault=='expired' else m.boot_ns())
    assert result['state']==('unknown' if fault=='restarted' else 'stale' if fault=='expired' else 'degraded')
    assert 'PRIVATE_CANARY' not in json.dumps(result)
