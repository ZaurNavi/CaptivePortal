"""04B disposable kernel gates. No original LAB/source/profile access."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[2]
NATIVE=pytest.mark.skipif(sys.platform!='linux' or getattr(os,'geteuid',lambda:-1)()!=0,
    reason='R4 native disposable root mount/UID contract; not a Windows kernel PASS')


@NATIVE
@pytest.mark.parametrize('store',['public_traffic','network_service_intelligence','traffic_projection'])
@pytest.mark.parametrize('fault',['none','main_uid','main_gid','wal_gid','shm_gid','other_store_policy'])
def test_04C_disposable_native_source_main_and_sidecar_owner_pin_remains_strict(store,fault,record_property):
    from dataclasses import replace
    import tempfile
    from app.db_audit_coordinator import live_sqlite,contracts as c
    from tests.db_audit_coordinator.test_b2_live_sqlite import disposable,hashes
    groups={'public_traffic':1004,'network_service_intelligence':1004,'traffic_projection':996}
    with tempfile.TemporaryDirectory(prefix='qio226-04c-owner-') as temporary:
        root=Path(temporary);root.chmod(0o711)
        source=root/'source';source.mkdir(mode=0o700)
        writer,policy=disposable(source,store)
        try:
            gid=groups[store]
            for file in source.iterdir():os.chown(file,1003,gid);file.chmod(0o600)
            os.chown(source,1003,gid)
            policy=replace(policy,uid=1003,gid=gid)
            before=hashes(policy.source)
            if fault=='main_uid':os.chown(policy.source,1005,gid)
            elif fault in {'main_gid','wal_gid','shm_gid'}:
                suffix={'main_gid':'','wal_gid':'-wal','shm_gid':'-shm'}[fault]
                os.chown(policy.source+suffix,1003,1005)
            elif fault=='other_store_policy':
                policy=replace(policy,gid=996 if gid==1004 else 1004)
            if fault=='none':
                main,sides=live_sqlite.inspect_source(policy)
                assert main[:2]==(policy.device,policy.inode) and sides['-wal'] and sides['-shm']
            else:
                with pytest.raises(c.CoordinatorError):live_sqlite.inspect_source(policy)
            assert before==hashes(policy.source)
            record_property('04c_source_pin',json.dumps(dict(store=store,uid=1003,gid=gid,fault=fault,
                source_hashes_unchanged=True),sort_keys=True))
        finally:writer.close()


SOURCE_VIEW_DRIVER=r'''
import hashlib,json,os,sqlite3,tempfile,uuid
from pathlib import Path
from app.db_audit_coordinator.r4_sandbox import MountNamespace,PrivateTmpfs,drop_owner
with tempfile.TemporaryDirectory(prefix='qio226-r4-native-') as temporary:
 root=Path(temporary);root.chmod(0o711)
 source=root/'original';source.mkdir(mode=0o700)
 dbpath=source/'original.sqlite3'
 db=sqlite3.connect(dbpath,isolation_level=None)
 db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=FULL')
 db.execute('CREATE TABLE evidence(sequence INTEGER PRIMARY KEY,value TEXT NOT NULL)')
 db.execute("INSERT INTO evidence VALUES(1,'committed-in-native-wal')")
 for file in source.iterdir():os.chown(file,1000,1000);file.chmod(0o600)
 source.chmod(0o700);os.chown(source,1000,1000)
 original={suffix:hashlib.sha256(Path(str(dbpath)+suffix).read_bytes()).hexdigest() for suffix in ('','-wal')}
 base=root/'jobs';base.mkdir(mode=0o711)
 namespace=MountNamespace().enter();job=None
 # File capabilities must be opened in this mount namespace, after entry;
 # a descriptor pinned to a mount outside it is not silently rebound by path.
 fds={key:os.open(str(dbpath)+suffix,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
  for key,suffix in (('main',''),('wal','-wal'),('shm','-shm'))}
 try:
  job=PrivateTmpfs(namespace,str(uuid.uuid4()),str(uuid.uuid4()),4*1024**2,64,1000,1000,1001,_base=str(base))
  job.source_view(fds)
  read,write=os.pipe()
  pid=os.fork()
  if pid==0:
   try:
    os.close(read)
    status=os.open('/proc/self/status',os.O_RDONLY|os.O_CLOEXEC)
    for item in os.listdir('/proc/self/fd'):
     fd=int(item)
     if fd>2 and fd not in {write,status}:
      try:os.close(fd)
      except OSError:pass
    os.chroot(str(job.owner_root));os.chdir('/');drop_owner(1000,1000)
    denied=[]
    for name in ('input.sqlite3','input.sqlite3-wal','input.sqlite3-shm'):
     try:fd=os.open('/source/'+name,os.O_WRONLY)
     except OSError as error:denied.append(error.errno)
     else:os.close(fd);raise AssertionError('OS source write was possible')
    assert not os.path.exists('/proc') and not os.path.exists(str(dbpath))
    src=sqlite3.connect('file:/source/input.sqlite3?mode=ro',uri=True,isolation_level=None,timeout=0)
    src.execute('PRAGMA query_only=ON')
    dst=sqlite3.connect('/stage/snapshot.sqlite3',isolation_level=None)
    src.backup(dst,pages=1,sleep=0)
    rows=dst.execute('SELECT * FROM evidence').fetchall()
    dst.close();src.close()
    os.lseek(status,0,os.SEEK_SET);text=os.read(status,16384).decode();os.close(status)
    caps=[line for line in text.splitlines() if line.startswith(('CapInh:','CapPrm:','CapEff:','CapBnd:','CapAmb:'))]
    assert len(caps)==5 and all(int(line.split()[1],16)==0 for line in caps)
    assert 'NoNewPrivs:\t1' in text
    os.write(write,json.dumps(dict(result='backup_complete',denied=denied,rows=rows,caps_zero=True)).encode())
    os._exit(0)
   except BaseException as error:
    os.write(write,json.dumps(dict(result='HOLD_R4_SOURCE_VIEW',error=type(error).__name__)).encode());os._exit(3)
  os.close(write);raw=os.read(read,4096);os.close(read)
  _,status=os.waitpid(pid,0);result=json.loads(raw)
  assert os.waitstatus_to_exitcode(status)==0,result
  assert result['rows']==[[1,'committed-in-native-wal']]
  result['source_hash_unchanged']=all(hashlib.sha256(Path(str(dbpath)+suffix).read_bytes()).hexdigest()==digest for suffix,digest in original.items())
  assert result['source_hash_unchanged']
  assert (job.stage/'snapshot.sqlite3').exists()
  result['snapshot_header_modes']=list((job.stage/'snapshot.sqlite3').read_bytes()[18:20])
  (job.stage/'snapshot.sqlite3').unlink()
  print(json.dumps(result,sort_keys=True))
 finally:
  for fd in fds.values():os.close(fd)
  if job is not None:job.cleanup()
  namespace.restore();db.close()
'''


@NATIVE
def test_K02_native_owner_readonly_view_and_wal_backup(record_property):
    process=subprocess.run([sys.executable,'-B','-E','-s','-c',SOURCE_VIEW_DRIVER],cwd=ROOT,
        capture_output=True,text=True,timeout=15)
    assert process.returncode==0,process.stdout+process.stderr
    result=json.loads(process.stdout)
    assert result['result']=='backup_complete' and result['source_hash_unchanged'] and result['caps_zero']
    record_property('native_source_view',json.dumps(result,sort_keys=True))


CHARGE_DRIVER=r'''
import json,os,tempfile,time,uuid
from pathlib import Path
from app.db_audit_coordinator.r4_sandbox import MountNamespace,PrivateTmpfs,drop_owner
name='qio226-disposable-'+uuid.uuid4().hex
leaf=Path('/sys/fs/cgroup')/name
original=open('/proc/self/cgroup').read().strip().split('::',1)[1]
assert original=='/'
back=os.open('/sys/fs/cgroup/cgroup.procs',os.O_WRONLY|os.O_CLOEXEC)
namespace=None;job=None;moved=False;children=[]
def write(name,value):(leaf/name).write_text(str(value))
def counters():return {line.split()[0]:int(line.split()[1]) for line in (leaf/'memory.stat').read_text().splitlines()}
def amount(name):return int((leaf/name).read_text().strip())
def child(uid,gid,action):
 pid=os.fork()
 if pid==0:
  try:
   drop_owner(uid,gid)
   assert open('/proc/self/cgroup').read().strip()=='0::/'+name
   action();os._exit(0)
  except BaseException:os._exit(3)
 children.append(pid)
 waited,status=os.waitpid(pid,0);children.remove(pid)
 assert waited==pid and os.waitstatus_to_exitcode(status)==0
try:
 leaf.mkdir()
 write('memory.max',128*1024**2);write('memory.swap.max',0);write('pids.max',8)
 assert amount('memory.max')==128*1024**2 and amount('memory.swap.max')==0
 write('cgroup.procs',os.getpid());moved=True
 with tempfile.TemporaryDirectory(prefix='qio226-r4-charge-') as temporary:
  base=Path(temporary);base.chmod(0o711)
  namespace=MountNamespace().enter()
  job=PrivateTmpfs(namespace,str(uuid.uuid4()),str(uuid.uuid4()),4*1024**2,64,1000,1000,1001,_base=str(base))
  before=counters().get('shmem',0)
  payload=job.stage/'payload'
  def allocate():
   fd=os.open(payload,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
   try:
    for _ in range(32):assert os.write(fd,b'x'*65536)==65536
   finally:os.close(fd)
  child(1000,1000,allocate)
  charged=counters().get('shmem',0);current=amount('memory.current')
  assert charged-before>=2*1024**2 and current>=charged and amount('memory.swap.current')==0
  final=job.final/'payload';os.rename(payload,final);os.chown(final,0,1001);final.chmod(0o440)
  def validate():
   fd=os.open(final,os.O_RDONLY)
   try:assert os.read(fd,8)==b'x'*8
   finally:os.close(fd)
  child(1001,1001,validate)
  assert amount('memory.swap.current')==0
  assert (leaf/'cgroup.procs').read_text().split()==[str(os.getpid())]
  final.unlink();job.cleanup();job=None
  for _ in range(100):
   if counters().get('shmem',0)==0:break
   time.sleep(.01)
  assert counters().get('shmem',0)==0
  namespace.restore();namespace=None
  os.write(back,str(os.getpid()).encode());moved=False
  observations=[]
  for _ in range(2):
   assert (leaf/'cgroup.procs').read_text().strip()==''
   assert 'populated 0' in (leaf/'cgroup.events').read_text()
   assert amount('memory.swap.current')==0
   observations.append(time.monotonic_ns())
  assert observations[0]<observations[1]
  print(json.dumps(dict(shmem_before=before,shmem_after_owner=charged,memory_current=current,
   swap_current=0,shmem_after_cleanup=0,owner_uid=1000,validator_uid=1001,
   same_leaf=True,positive_waits=2,empty_observations=2,kernel=os.uname().release)))
finally:
 for pid in children:
  try:os.kill(pid,9);os.waitpid(pid,0)
  except ProcessLookupError:pass
 if job is not None:
  for target in (job.stage/'payload',job.final/'payload'):
   if target.exists():target.unlink()
  job.cleanup()
 if namespace is not None:namespace.restore()
 if moved:os.write(back,str(os.getpid()).encode())
 os.close(back)
 if leaf.exists():leaf.rmdir()
'''


@NATIVE
def test_K03_native_same_leaf_tmpfs_owner_charge_zero_swap_and_release(record_property):
    process=subprocess.run([sys.executable,'-B','-E','-s','-c',CHARGE_DRIVER],cwd=ROOT,
        capture_output=True,text=True,timeout=15)
    assert process.returncode==0,process.stdout+process.stderr
    result=json.loads(process.stdout)
    assert result['shmem_after_owner']>=2*1024**2 and result['same_leaf']
    assert result['swap_current']==0 and result['shmem_after_cleanup']==0
    record_property('native_memcg_charge',json.dumps(result,sort_keys=True))


WORKER_DRIVER=r'''
import os,sys,traceback
from app.db_audit_coordinator import child_bootstrap as worker,r4_sandbox
r4_sandbox.RAM_ROOT=sys.argv[2]
# Deliberately uninstalled QA interpreter/repository. This harness proves native
# transport + canonical T3, NOT immutable installed release qualification F2.
worker.verify_origin=lambda profile:None
original=worker.r4_snapshot if hasattr(worker,'r4_snapshot') else None
try:os._exit(worker.execute(int(sys.argv[1])))
except BaseException:traceback.print_exc();os._exit(3)
'''

OWNER_DRIVER=r'''
import os,sys,traceback
from app.db_audit_coordinator import r4_owner_helper as helper
from app.db_audit_coordinator.live_profile import PilotProfile
helper.RAM_ROOT=sys.argv[2]
PilotProfile.artifact=lambda self:None
helper.import_roots=lambda:None  # QA provenance exception, never installed F2 PASS.
drop=helper.drop_owner
def exact_owner(uid,gid):
 drop(uid,gid)  # REAL credential change, not a test substitute.
 assert os.getresuid()==(1003,)*3 and os.getresgid()==(gid,)*3 and gid in {1004,996}
 assert os.getgroups()==[]
 assert os.stat('/stage').st_uid==uid and os.stat('/stage').st_gid==gid
 for suffix in ('','-wal','-shm'):
  info=os.stat('/source/input.sqlite3'+suffix)
  assert (info.st_uid,info.st_gid)==(uid,gid)
helper.drop_owner=exact_owner
if len(sys.argv)>3 and sys.argv[3]=='helper_death':
 import sqlite3,time
 original=sqlite3.connect
 class SlowSource(sqlite3.Connection):
  def backup(self,target,**kwargs):
   progress=kwargs['progress']
   def pause(*args):time.sleep(3);progress(*args)
   kwargs.update(pages=1,progress=pause)
   return super().backup(target,**kwargs)
 def connect(*args,**kwargs):kwargs['factory']=SlowSource;return original(*args,**kwargs)
 helper.sqlite3.connect=connect
try:os._exit(helper.run(int(sys.argv[1])))
except BaseException:traceback.print_exc();os._exit(3)
'''


PIPELINE_DRIVER=r'''
import copy,hashlib,json,os,select,sqlite3,subprocess,sys,tempfile,time,traceback,uuid
from dataclasses import replace
from pathlib import Path
from app.db_audit_coordinator import contracts as c,live_coordinator as runtime,r4_sandbox,r4_release
from app.db_audit_coordinator.live_profile import PilotProfile,R4Installation
from app.db_audit_coordinator.live_receipts import identity
from app.db_audit_coordinator.live_policy import R4_METHOD,empty_state
from tests.db_audit_coordinator.test_b2_live_policy import profile,STORES
from tests.db_audit_coordinator.test_b2_live_sqlite import disposable,hashes
from tests.db_audit_coordinator.test_qio226_r4_native import WORKER_DRIVER,OWNER_DRIVER
assert os.geteuid()==0
name='qio226-r4-pipeline-'+uuid.uuid4().hex
top=Path('/sys/fs/cgroup')/name
original=open('/proc/self/cgroup').read().strip().split('::',1)[1];assert original=='/'
back=os.open('/sys/fs/cgroup/cgroup.procs',os.O_WRONLY|os.O_CLOEXEC)
subject=None;writers=[];log=None;root=None;moved=False
def write(folder,key,value):(folder/key).write_text(str(value))
try:
 top.mkdir();write(top,'memory.max',768*1024**2);write(top,'memory.swap.max',0)
 write(top,'cgroup.subtree_control','+memory +pids')
 delegated=top/'delegated';delegated.mkdir();write(delegated,'cgroup.subtree_control','+memory +pids')
 control=delegated/'control';control.mkdir()
 write(control,'cgroup.procs',os.getpid());moved=True
 with __import__('contextlib').nullcontext(tempfile.mkdtemp(prefix='qio226-r4-pipeline-')) as temporary:
  root=Path(temporary);root.chmod(0o711)
  queue=root/'queue';queue.mkdir(mode=0o710);os.chown(queue,0,1000)
  (queue/'queue-state.v1.json').write_bytes(c.encode(empty_state()));(queue/'queue-state.v1.json').chmod(0o600)
  for filename,mode in (('coordinator.lock',0o600),('heavy.lock',0o640)):
   file=queue/filename;file.touch(mode=mode);os.chown(file,0,1000)
  policies=[]
  source_gids={'public_traffic':1004,'network_service_intelligence':1004,'traffic_projection':996}
  for store in STORES:
   source=root/store;source.mkdir(mode=0o700)
   writer,policy=disposable(source,store);writers.append(writer)
   # Controlled B failure: disposable original fixture is invalid from birth;
   # no runtime source writes, no production failure injection API.
   if store=='network_service_intelligence' and sys.argv[1]=='controlled_B':
    writer.execute("UPDATE service_materialization_generations SET ruleset_digest_sha256='bad'")
   for file in source.iterdir():os.chown(file,1003,source_gids[store]);file.chmod(0o600)
   os.chown(source,1003,source_gids[store])
   policies.append(replace(policy,uid=1003,gid=source_gids[store],memory_max_bytes=256*1024**2,attempt_seconds=30))
  ram=root/'ram';ram.mkdir(mode=0o711)
  cfg=R4Installation(R4_METHOD,True,1003,r4_sandbox.RAM_ROOT,ram.stat().st_dev,ram.stat().st_ino,16,64)
  value=profile(enabled=True,root=str(queue),release_root=os.getcwd(),python=sys.executable,
   delegated='/'+name+'/delegated',delegated_device=delegated.stat().st_dev,delegated_inode=delegated.stat().st_ino,
   worker_uid=1000,worker_gid=1000,worker_groups=(),stores=tuple(policies),r4=cfg)
  runtime.LiveCoordinator.qualify=lambda self,profile:None
  PilotProfile.artifact=lambda self:None
  # Explicit path seam in this disposable native harness only.
  Tmpfs=r4_sandbox.PrivateTmpfs
  r4_sandbox.PrivateTmpfs=lambda *args,**kwargs:Tmpfs(*args,**kwargs,_base=str(ram))
  runtime.LiveCoordinator.command=lambda self,fd:[sys.executable,'-B','-E','-s','-c',WORKER_DRIVER,str(fd),str(ram)]
  popen=subprocess.Popen;log=open(root/'children.log','wb')
  def launched(args,**kwargs):
   if 'app.db_audit_coordinator.r4_owner_helper' in args:
    scenario=sys.argv[1]
    if scenario=='cancel_B' and subject._r4.job['store_id']=='network_service_intelligence':scenario='helper_death'
    args=[sys.executable,'-B','-E','-s','-c',OWNER_DRIVER,args[-1],str(ram),scenario]
   kwargs['stderr']=log
   return popen(args,**kwargs)
  subprocess.Popen=launched
  old_hold=r4_release.Session.hold
  def diagnostic(self):
   if sys.exc_info()[0]:traceback.print_exc()
   old_hold(self)
  r4_release.Session.hold=diagnostic
  from app.db_audit_coordinator import r4_snapshot
  promote=r4_snapshot.promote;stage_receipts=[]
  faults={'stage_sidecar','stage_symlink','stage_hardlink','rename_collision','source_replaced','image_tamper',
   'cap_shrunk','swap_enabled','tasks_changed'}
  def promotion(job,policy,gid,**kwargs):
   scenario=sys.argv[1];stage=job.stage/'snapshot.sqlite3'
   assert (job.stage.stat().st_uid,job.stage.stat().st_gid)==(policy.uid,policy.gid)
   assert (stage.stat().st_uid,stage.stat().st_gid)==(policy.uid,policy.gid)
   stage_receipts.append(dict(store=policy.store_id,uid=stage.stat().st_uid,gid=stage.stat().st_gid))
   if scenario=='stage_sidecar':(job.stage/'snapshot.sqlite3-wal').write_bytes(b'not-a-complete-image')
   elif scenario=='stage_symlink':
    stage.rename(job.stage/'other');stage.symlink_to('other')
   elif scenario=='stage_hardlink':os.link(stage,job.stage/'other')
   elif scenario=='rename_collision':(job.final/'snapshot.sqlite3').write_bytes(b'preexisting')
   elif scenario=='source_replaced':
    source=Path(policy.source);other=source.with_suffix('.replacement')
    other.write_bytes(source.read_bytes());os.chown(other,policy.uid,policy.gid);other.chmod(0o600);os.replace(other,source)
   fd,receipt=promote(job,policy,gid,**kwargs)
   if scenario=='image_tamper':
    target=job.final/'snapshot.sqlite3'
    target.chmod(0o640)
    with target.open('r+b') as file:file.seek(100);file.write(b'corruption')
    target.chmod(0o440)
   return fd,receipt
  r4_snapshot.promote=promotion
  subject=runtime.LiveCoordinator(value)
  original_inspect=runtime.__dict__.get('live_sqlite')
  from app.db_audit_coordinator import live_sqlite
  inspect=live_sqlite.inspect_source;gate_checks=[]
  def locked_source(policy):
   import fcntl
   assert subject._r4 is not None and subject._r4.phase in {'gate','validating'}
   fd=os.open(queue/'heavy.lock',os.O_RDONLY)
   try:
    try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:gate_checks.append('own_fd_competitor_denied')
    else:raise AssertionError('source opened without independent gatekeeper flock')
   finally:os.close(fd)
   return inspect(policy)
  live_sqlite.inspect_source=locked_source
  before=[hashes(policy.source) for policy in policies]
  items=[dict(store_id=store,idempotency_key=str(uuid.uuid4())) for store in STORES]
  reply=subject.submit_batch(items,c.scope(1002));assert len(reply['jobs'])==3
  fault_killed=False;directory_receipts=[]
  for number in range(3):
   assert subject.dispatch_one()
   selected=subject._r4.policy;info=subject._r4.ram.stage.stat()
   assert (info.st_uid,info.st_gid)==(selected.uid,selected.gid)
   directory_receipts.append(dict(store=selected.store_id,uid=info.st_uid,gid=info.st_gid))
   if sys.argv[1]=='cap_shrunk':subject._r4.leaf.write('memory.max',str(128*1024**2))
   elif sys.argv[1]=='swap_enabled':subject._r4.leaf.write('memory.swap.max','4096')
   elif sys.argv[1]=='tasks_changed':subject._r4.leaf.write('pids.max','15')
   if sys.argv[1]=='supervisor_death':
    print(json.dumps(dict(root=str(root),cgroup=str(top),queue=str(queue),
     sources=[dict(path=p.source,hashes=hashes(p.source)) for p in policies])),flush=True)
    os.kill(os.getpid(),9)
   until=time.monotonic()+15
   while subject.process is not None and time.monotonic()<until and not subject.orphan_hold:
    if select.select([subject._wake_read],[],[],.1)[0]:subject._wake_read.recv(1)
    subject.finish()
    session=subject._r4
    if session is not None and not fault_killed:
     if sys.argv[1]=='validator_death' and 'worker' in session.children:
      session.children['worker'].process.kill();fault_killed=True
     elif (sys.argv[1]=='helper_death' or (sys.argv[1]=='cancel_B' and number==1)) and 'owner' in session.children:
      child=session.children['owner']
      try:open_stage=any(os.readlink('/proc/'+str(child.pid)+'/fd/'+fd).endswith('/stage/snapshot.sqlite3')
          for fd in os.listdir('/proc/'+str(child.pid)+'/fd'))
      except FileNotFoundError:open_stage=False
      if open_stage:
       if sys.argv[1]=='cancel_B':subject._notify_cancel()
       else:child.process.kill()
       fault_killed=True
   if sys.argv[1] in faults:
    assert subject.orphan_hold and subject._r4 is not None
    assert [job['state'] for job in subject.store.read()['jobs']]==['running','queued','queued']
    assert not subject.dispatch_one() and not subject.store.read()['last_verified_success_by_store']
    if sys.argv[1] in {'cap_shrunk','swap_enabled','tasks_changed'}:assert gate_checks==[]
    print(json.dumps(dict(fault=sys.argv[1],orphan_hold=True,next_fifo=False)))
    break
   if sys.argv[1]=='validator_death':
    assert fault_killed and subject.orphan_hold and subject._r4 is not None
    assert [job['state'] for job in subject.store.read()['jobs']]==['running','queued','queued']
    assert not subject.dispatch_one() and not subject.store.read()['last_verified_success_by_store']
    print(json.dumps(dict(crash='validator_death',orphan_hold=True,next_fifo=False,source_hashes_unchanged=before==[hashes(p.source) for p in policies])))
    break
   if subject.orphan_hold or subject.process is not None:
    log.flush();raise AssertionError((subject._r4.phase,subject.store.read(),(root/'children.log').read_text()))
   assert len(subject.r4_proofs)==number+1
   assert subject.r4_proofs[-1]['empty_observations']==2
   if sys.argv[1]=='helper_death':break
  if sys.argv[1]=='validator_death' or sys.argv[1] in faults:pass
  elif sys.argv[1]=='helper_death':
   assert fault_killed and subject.store.read()['jobs'][0]['state']=='deferred'
   assert subject.store.read()['jobs'][0]['audit_result']['reason_code']=='worker_crashed'
   assert subject.store.read()['jobs'][0]['audit_result']['result']=='incomplete'
   assert subject.r4_proofs[-1]['helper_reaped'] and subject.r4_proofs[-1]['snapshot'] is None
   print(json.dumps(dict(crash='helper_death',positive_release=True,source_hashes_unchanged=before==[hashes(p.source) for p in policies])))
  else:
   final=subject.store.read();states=[job['state'] for job in final['jobs']]
   expected=['completed','failed','completed'] if sys.argv[1]=='controlled_B' else ['completed','canceled','completed'] if sys.argv[1]=='cancel_B' else ['completed']*3
   assert states==expected,states
   if sys.argv[1]=='cancel_B':assert fault_killed and final['jobs'][1]['audit_result']['result']=='incomplete'
   assert before==[hashes(policy.source) for policy in policies]
   assert not subject.dispatch_one() and not subject.orphan_hold
   assert len(gate_checks)==6
   print(json.dumps(dict(states=states,source_hashes_unchanged=True,proofs=subject.r4_proofs,
    kernel=os.uname().release,installed_qualification='NOT_CLAIMED_QA_ONLY',uids=[0,1000,1003],
    stages=directory_receipts,promoted_stages=stage_receipts)))
  if not subject.orphan_hold:subject.close();subject=None
  for writer in writers:writer.close()
  writers=[]
finally:
 # Exact test-owned children/mounts/cgroup ONLY; no production queue recovery.
 if subject is not None:
  session=subject._r4
  if session is not None:
   for child in session.children.values():
    if child.process.poll() is None:child.process.kill()
    child.process.wait(timeout=5)
   for thread in session.threads:thread.join(timeout=2)
   if session.image_fd is not None:os.close(session.image_fd)
   for fd in session.sources.values():os.close(fd)
   if session.ram is not None and session.ram.mounted:
    for folder in (session.ram.stage,session.ram.final):
     for file in folder.iterdir():file.unlink()
    session.ram.cleanup()
   if session.namespace is not None:session.namespace.restore()
   if session.residence is not None:session.residence.leave()
  subject.close()
 for writer in writers:writer.close()
 if log is not None:log.close()
 if moved:os.write(back,str(os.getpid()).encode())
 os.close(back)
 if top.exists():
  for folder in sorted(top.rglob('*'),key=lambda p:len(p.parts),reverse=True):
   if folder.is_dir():folder.rmdir()
  top.rmdir()
 if root is not None:
  assert str(root.resolve()).startswith('/tmp/qio226-r4-pipeline-')
  __import__('shutil').rmtree(root)
'''


@NATIVE
@pytest.mark.parametrize('scenario',['positive','controlled_B','cancel_B'])
def test_K01_K05_K06_K08_native_three_store_physical_transport_and_positive_fifo_release(scenario,record_property):
    process=subprocess.run([sys.executable,'-B','-E','-s','-c',PIPELINE_DRIVER,scenario],cwd=ROOT,
        capture_output=True,text=True,timeout=60)
    assert process.returncode==0,process.stdout+process.stderr
    result=json.loads(process.stdout)
    assert result['source_hashes_unchanged'] and len(result['proofs'])==3
    assert result['installed_qualification']=='NOT_CLAIMED_QA_ONLY'
    assert result['stages']==[dict(store=store,uid=1003,gid=gid) for store,gid in
        [('public_traffic',1004),('network_service_intelligence',1004),('traffic_projection',996)]]
    assert result['promoted_stages']==[item for item in result['stages']
        if scenario!='cancel_B' or item['store']!='network_service_intelligence']
    record_property('native_pipeline',json.dumps(result,sort_keys=True))


@NATIVE
@pytest.mark.parametrize('scenario',['helper_death','validator_death'])
def test_K07_native_kill_exact_helper_or_validator_never_fabricates_success(scenario,record_property):
    process=subprocess.run([sys.executable,'-B','-E','-s','-c',PIPELINE_DRIVER,scenario],cwd=ROOT,
        capture_output=True,text=True,timeout=60)
    assert process.returncode==0,process.stdout+process.stderr
    result=json.loads(process.stdout)
    assert result['crash']==scenario and result['source_hashes_unchanged']
    if scenario=='validator_death':assert result['orphan_hold'] and not result['next_fifo']
    else:assert result['positive_release']
    record_property('native_fault',json.dumps(result,sort_keys=True))


@NATIVE
@pytest.mark.parametrize('scenario',['stage_sidecar','stage_symlink','stage_hardlink','rename_collision','source_replaced','image_tamper',
    'cap_shrunk','swap_enabled','tasks_changed'])
def test_K04_K05_native_incomplete_alias_or_tampered_image_cannot_pass(scenario,record_property):
    process=subprocess.run([sys.executable,'-B','-E','-s','-c',PIPELINE_DRIVER,scenario],cwd=ROOT,
        capture_output=True,text=True,timeout=60)
    assert process.returncode==0,process.stdout+process.stderr
    result=json.loads(process.stdout)
    assert result['fault']==scenario and result['orphan_hold'] and not result['next_fifo']
    record_property('native_reject',json.dumps(result,sort_keys=True))


@NATIVE
def test_K07_native_supervisor_sigkill_keeps_durable_running_and_never_starts_B(record_property):
    import hashlib
    import shutil
    import time
    process=subprocess.Popen([sys.executable,'-B','-E','-s','-c',PIPELINE_DRIVER,'supervisor_death'],cwd=ROOT,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    output,error=process.communicate(timeout=20)
    assert process.returncode==-9,error
    ticket=json.loads(output);root=Path(ticket['root']);group=Path(ticket['cgroup'])
    assert str(root.resolve()).startswith('/tmp/qio226-r4-pipeline-')
    assert group.parent==Path('/sys/fs/cgroup') and group.name.startswith('qio226-r4-pipeline-')
    try:
        until=time.monotonic()+5
        while 'populated 1' in (group/'cgroup.events').read_text() and time.monotonic()<until:time.sleep(.01)
        assert 'populated 0' in (group/'cgroup.events').read_text()
        state=json.loads((Path(ticket['queue'])/'queue-state.v1.json').read_text())
        assert [job['state'] for job in state['jobs']]==['running','queued','queued']
        assert state['jobs'][0]['audit_result'] is None and not state['last_verified_success_by_store']
        for item in ticket['sources']:
            for suffix,digest in item['hashes'].items():
                assert hashlib.sha256(Path(item['path']+suffix).read_bytes()).hexdigest()==digest
        record_property('supervisor_death','SIGKILL; durable running; no terminal; next B/C queued; source hashes unchanged')
    finally:
        # Only this known disposable cgroup. Kernel refuses rmdir if not empty;
        # no recovery/reset or PID-based guesses in the implementation.
        if 'populated 1' in (group/'cgroup.events').read_text():(group/'cgroup.kill').write_text('1')
        for folder in sorted(group.rglob('*'),key=lambda p:len(p.parts),reverse=True):
            if folder.is_dir():folder.rmdir()
        group.rmdir();shutil.rmtree(root)
