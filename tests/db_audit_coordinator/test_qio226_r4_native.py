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


DIRFD_DRIVER=r'''
import array,errno,json,os,shutil,sqlite3,sys,tempfile,uuid
from dataclasses import replace
from pathlib import Path
from app.db_audit_coordinator import contracts as c,r4_ipc,r4_snapshot,r4_sandbox
from app.db_audit_coordinator.live_receipts import identity
from app.db_audit_coordinator.live_sqlite import validate_snapshot
from tests.db_audit_coordinator.test_b2_live_sqlite import disposable
assert os.geteuid()==0 and os.getpid()==1
store,fault=sys.argv[1:];root=Path(tempfile.mkdtemp(prefix='qio226-04d-private-'));root.chmod(0o755)
namespace=ram=writer=None;image_fd=final_fd=None
def sha(path):return __import__('hashlib').sha256(Path(path).read_bytes()).hexdigest()
try:
 protected=root/'socket-parent';protected.mkdir(mode=0o750);os.chown(protected,0,992)
 base=protected/'ram-jobs';base.mkdir(mode=0o711)
 namespace=r4_sandbox.MountNamespace().enter()
 ram=r4_sandbox.PrivateTmpfs(namespace,str(uuid.uuid4()),str(uuid.uuid4()),16*1024**2,64,1003,1004,993,_base=str(base))
 source=root/'source';source.mkdir(mode=0o700)
 writer,policy=disposable(source,store)
 gid=996 if store=='traffic_projection' else 1004
 for file in source.iterdir():os.chown(file,1003,gid)
 os.chown(source,1003,gid);policy=replace(policy,uid=1003,gid=gid)
 image=ram.final/'snapshot.sqlite3'
 db=sqlite3.connect(image,isolation_level=None);writer.backup(db);db.close()
 os.chown(image,0,993);image.chmod(0o440)
 # Fixture control preloads unchanged canonical adapters before actual UID drop.
 db=sqlite3.connect(image.as_uri()+'?mode=ro&immutable=1',uri=True);db.row_factory=sqlite3.Row
 db.execute('PRAGMA foreign_keys=ON');expected=validate_snapshot(db,policy,lambda:None);db.close()
 before={p.name:sha(p) for p in source.iterdir()};image_before=sha(image)
 image_fd=os.open(image,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
 final_fd,folder=r4_snapshot.pin_final(ram,image_fd,993)
 receipt=r4_snapshot.digest_fd(image_fd,policy.image_max_bytes)
 if fault=='directory_gid':os.chown(ram.final,0,994)
 elif fault=='directory_mode':ram.final.chmod(0o770)
 elif fault=='directory_owner':os.chown(ram.final,995,993)
 elif fault=='directory_inode':folder['inode']+=1
 elif fault=='directory_device':folder['device']+=1
 elif fault=='image_owner':os.chown(image,995,993)
 elif fault=='image_gid':os.chown(image,0,994)
 elif fault=='image_mode':image.chmod(0o640)
 elif fault=='image_digest':receipt['sha256']='0'*64
 elif fault=='image_size':receipt['size']+=1
 elif fault=='symlink':image.rename(ram.final/'other');image.symlink_to('other')
 elif fault=='hardlink':os.link(image,ram.final/'other')
 elif fault=='sidecar':(ram.final/'snapshot.sqlite3-wal').touch()
 elif fault=='stage_directory':
  os.close(final_fd);final_fd=os.open(ram.stage,os.O_RDONLY|os.O_DIRECTORY)
 elif fault=='foreign_directory':
  other=ram.root/'other-final';other.mkdir(mode=0o750);os.chown(other,0,993)
  os.close(final_fd);final_fd=os.open(other,os.O_RDONLY|os.O_DIRECTORY)
 left,right=r4_ipc.pair();control,child_control=r4_ipc.pair();read,write=os.pipe()
 os.chdir(root);parent_pid=os.getpid();child=os.fork()
 if child==0:
  left.close();control.close();os.close(read)
  keep={0,1,2,right.fileno(),child_control.fileno(),write}
  for item in os.listdir('/proc/self/fd'):
   opened=int(item)
   if opened not in keep:
    try:os.close(opened)
    except OSError:pass
  r4_sandbox.drop_owner(995,993)
  result=dict(uid=os.geteuid(),gid=os.getegid(),groups=os.getgroups(),original_lab_db_pass=False)
  try:
   assert result['uid']==995 and result['gid']==993 and result['groups']==[]
   assert os.readlink('/proc/self')==str(os.getpid())
   try:os.stat(image)
   except PermissionError as error:assert error.errno==errno.EACCES;result['absolute_eacces']=True
   else:raise AssertionError('absolute path accessible')
   cwd=identity(os.stat('.'));fd_count=len(os.listdir('/proc/self/fd'));received=None
   try:
    kind,payload,received=r4_ipc.receive(right,'1'*64,0,parent_pid,seconds=5,allow_snapshot=True)
    assert kind=='snapshot' and len(received)==2
    if fault=='closed_image':os.close(received[0])
    elif fault=='closed_directory':os.close(received[1])
    elif fault=='host_proc':
     original_readlink=os.readlink
     os.readlink=lambda name,*args,**kwargs:'999999' if name=='/proc/self' else original_readlink(name,*args,**kwargs)
    elif fault=='missing_proc_alias':
     original_stat=os.stat
     def stat(name,*args,**kwargs):
      if isinstance(name,str) and name.startswith('/proc/self/fd/'):raise FileNotFoundError(errno.ENOENT,'synthetic')
      return original_stat(name,*args,**kwargs)
     os.stat=stat
    ticks=[0];test_cwd=os.open('.',os.O_RDONLY|os.O_DIRECTORY) if fault=='cwd_change' else None
    opened_databases=[];native_connect=sqlite3.connect
    def connect(filename,**kwargs):
     assert filename=='file:/proc/self/fd/'+str(received[1])+'/snapshot.sqlite3?mode=ro&immutable=1'
     assert kwargs==dict(uri=True,isolation_level=None,timeout=0)
     db=native_connect(filename,**kwargs);opened_databases.append(db);return db
    sqlite3.connect=connect
    def guard():
     ticks[0]+=1
     assert identity(os.stat('.'))==cwd
     if ticks[0]==3:
      if fault=='cancel':raise c.CoordinatorError('canceled')
      if fault=='deadline':raise c.CoordinatorError('not_admitted')
      if fault=='cwd_change':os.chdir('/')  # Test-only violation: validator must reject it.
      if fault=='tamper_during_t3':
       child_control.send(b'T');assert child_control.recv(1)==b'A'
    try:
     answer=r4_snapshot.validate(received[0],received[1],payload['image'],payload['directory'],policy,guard)
     assert fault=='positive',fault
     assert answer==expected;result['canonical_t3']='PASS';result['guard_calls']=ticks[0]
    except Exception as error:
     assert fault!='positive',(type(error).__name__,str(error))
     result['rejected']=type(error).__name__
     if fault=='cwd_change':
      assert identity(os.stat('.'))!=cwd;result['injected_cwd_change_rejected']=True
    finally:
     if test_cwd is not None:os.fchdir(test_cwd);os.close(test_cwd)  # Fixture restores its own fault.
     for db in opened_databases:
      try:db.execute('SELECT 1')
      except sqlite3.ProgrammingError:pass
      else:raise AssertionError('SQLite connection leaked')
     for opened in received:
      try:os.fstat(opened)
      except OSError as error:assert error.errno==errno.EBADF
      else:raise AssertionError('FD leaked')
   except c.CoordinatorError as error:
    assert fault=='hardlink';result['rejected']=type(error).__name__
   assert identity(os.stat('.'))==cwd
   assert len(os.listdir('/proc/self/fd'))==fd_count
   result.update(cwd_unchanged=True,received_fds_closed=True)
   os.write(write,json.dumps(result).encode());os._exit(0)
  except BaseException as error:
   os.write(write,json.dumps(dict(error=type(error).__name__,message=str(error))).encode());os._exit(2)
 right.close();child_control.close();os.close(write)
 # Send raw rights only to allow receiver negative tests to prove closure.
 left.sendmsg([c.encode(dict(kind='snapshot',binding='1'*64,payload=dict(image=receipt,directory=folder)))],
  [( __import__('socket').SOL_SOCKET,__import__('socket').SCM_RIGHTS,array.array('i',[image_fd,final_fd]))])
 if fault=='tamper_during_t3':
  control.settimeout(5);assert control.recv(1)==b'T'
  image.rename(ram.final/'old-image');image.write_bytes((ram.final/'old-image').read_bytes())
  os.chown(image,0,993);image.chmod(0o440);control.send(b'A')
 result=json.loads(os.read(read,8192));pid,status=os.waitpid(child,0)
 assert pid==child and os.waitstatus_to_exitcode(status)==0,result
 assert before=={p.name:sha(p) for p in source.iterdir()}
 if fault=='positive':
  assert image_before==sha(image) and set(os.listdir(final_fd))=={'snapshot.sqlite3'}
 result.update(store=store,source_bytes_unchanged=True,private_pidns=True,
  worker_t3='PASS' if fault=='positive' else 'REJECTED',fault=fault,kernel=os.uname().release)
 print(json.dumps(result))
 os.close(image_fd);image_fd=None;os.close(final_fd);final_fd=None;os.close(read)
 left.close();control.close()
finally:
 os.chdir('/')
 for opened in (image_fd,final_fd):
  if opened is not None:os.close(opened)
 if writer is not None:writer.close()
 if ram is not None:
  for folder in (ram.stage,ram.final):
   for file in folder.iterdir():file.unlink()
  extra=ram.root/'other-final'
  if extra.exists():extra.rmdir()
  ram.cleanup()
 if namespace is not None:namespace.restore()
 assert str(root.resolve()).startswith('/tmp/qio226-04d-private-')
 shutil.rmtree(root)
'''


@NATIVE
@pytest.mark.parametrize('store',['public_traffic','network_service_intelligence','traffic_projection'])
def test_04D_private_pidns_two_fd_native_canonical_t3_without_parent_traversal(store,record_property):
    process=subprocess.run(['unshare','--mount','--pid','--fork','--propagation','private','--mount-proc',
        sys.executable,'-B','-E','-s','-c',DIRFD_DRIVER,store,'positive'],cwd=ROOT,
        capture_output=True,text=True,timeout=20)
    assert process.returncode==0,process.stdout+process.stderr
    result=json.loads(process.stdout)
    assert result['canonical_t3']=='PASS' and result['uid']==995 and result['groups']==[]
    assert result['absolute_eacces'] and result['cwd_unchanged'] and result['received_fds_closed']
    assert result['source_bytes_unchanged'] and result['original_lab_db_pass'] is False
    record_property('04d_native_dirfd',json.dumps(result,sort_keys=True))


@NATIVE
@pytest.mark.parametrize('fault',['directory_gid','directory_mode','directory_owner','directory_inode',
    'directory_device','image_owner','image_gid','image_mode','image_size','image_digest','symlink',
    'hardlink','sidecar','stage_directory','foreign_directory','closed_image','closed_directory',
    'host_proc','missing_proc_alias','cancel','deadline','tamper_during_t3','cwd_change'])
def test_04D_private_pidns_invalid_fd_view_tamper_cancel_and_deadline_fail_closed(fault,record_property):
    process=subprocess.run(['unshare','--mount','--pid','--fork','--propagation','private','--mount-proc',
        sys.executable,'-B','-E','-s','-c',DIRFD_DRIVER,'public_traffic',fault],cwd=ROOT,
        capture_output=True,text=True,timeout=20)
    assert process.returncode==0,process.stdout+process.stderr
    result=json.loads(process.stdout)
    assert result['worker_t3']=='REJECTED' and result['rejected']
    assert result['cwd_unchanged'] and result['received_fds_closed'] and result['source_bytes_unchanged']
    assert result['original_lab_db_pass'] is False
    record_property('04d_native_rejection',json.dumps(result,sort_keys=True))


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
scenario=sys.argv[3] if len(sys.argv)>3 else ''
if scenario.startswith('04e_'):
 import time
 from app.db_audit_coordinator import contracts as c
 if scenario=='04e_unreported':time.sleep(.1);os._exit(3)
 if scenario=='04e_expired':
  read=helper.readonly_document
  def document(*args,**kwargs):
   value=read(*args,**kwargs);value['deadline_ns']=time.monotonic_ns()-1;return value
  helper.readonly_document=document
 else:
  stage=scenario.removeprefix('04e_');original_mark=helper.OwnerTrace.mark
  def mark(self,name):
   original_mark(self,name)
   if name==stage:
    if stage=='begin_wait':os.kill(os.getpid(),9)  # Real abrupt death, no Python failure handler.
    raise PermissionError(13,'SECRET /source/path SQL nonce CANARY')
  helper.OwnerTrace.mark=mark
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
if scenario.startswith('04f_'):
 import sqlite3,time
 native_connect=sqlite3.connect
 if scenario=='04f_busy_deadline':
  original_read=helper.readonly_document;captured={}
  def read(*args,**kwargs):
   document=original_read(*args,**kwargs);captured['document']=document;return document
  helper.readonly_document=read
  original_mark=helper.OwnerTrace.mark
  def deadline_mark(self,name):
   original_mark(self,name)
   if name=='backup_start':captured['document']['deadline_ns']=time.monotonic_ns()+50_000_000
  helper.OwnerTrace.mark=deadline_mark
 class CallbackSource(sqlite3.Connection):
  def backup(self,target,**kwargs):
   progress=kwargs['progress'];blocker=None;first=True
   if scenario in {'04f_busy_once','04f_busy_deadline','04f_busy_wait'}:
    blocker=native_connect('/stage/snapshot.sqlite3',isolation_level=None,timeout=0)
    blocker.execute('BEGIN EXCLUSIVE')  # Disposable destination contention; never original source writes.
   def observed(code,remaining,total):
    nonlocal first
    if scenario=='04f_bad_status' and first:code=8
    elif scenario=='04f_page_budget' and first:code,remaining,total=0,0,2**26//4096+1
    first=False
    progress(code,remaining,total)
    if scenario=='04f_busy_once' and code==5:
     blocker.execute('ROLLBACK')
   kwargs['progress']=observed
   try:return super().backup(target,**kwargs)
   finally:
    if blocker is not None:blocker.close()
 def callback_connect(filename,*args,**kwargs):
  if filename=='file:/source/input.sqlite3?mode=ro':kwargs['factory']=CallbackSource
  return native_connect(filename,*args,**kwargs)
 helper.sqlite3.connect=callback_connect
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
  code="import time,os;time.sleep(.2);os._exit(3)" if sys.argv[1]=='pre_ready_exit' else WORKER_DRIVER
  runtime.LiveCoordinator.command=lambda self,fd:[sys.executable,'-B','-E','-s','-c',code,str(fd),str(ram)]
  popen=subprocess.Popen;log=open(root/'children.log','wb')
  def launched(args,**kwargs):
   if 'app.db_audit_coordinator.r4_owner_helper' in args:
    scenario=sys.argv[1]
    if scenario=='cancel_B' and subject._r4.job['store_id']=='network_service_intelligence':scenario='helper_death'
    if scenario=='04f_busy_cancel':scenario='04f_busy_wait' if subject._r4.job['store_id']=='network_service_intelligence' else 'positive'
    args=[sys.executable,'-B','-E','-s','-c',OWNER_DRIVER,args[-1],str(ram),scenario]
   kwargs['stderr']=log
   return popen(args,**kwargs)
  subprocess.Popen=launched
  old_hold=r4_release.Session.hold
  def diagnostic(self,*args,**kwargs):
   if sys.exc_info()[0]:traceback.print_exc()
   old_hold(self,*args,**kwargs)
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
     elif (sys.argv[1]=='helper_death' or (sys.argv[1] in {'cancel_B','04f_busy_cancel'} and number==1)) and 'owner' in session.children:
      child=session.children['owner']
      try:open_stage=any(os.readlink('/proc/'+str(child.pid)+'/fd/'+fd).endswith('/stage/snapshot.sqlite3')
          for fd in os.listdir('/proc/'+str(child.pid)+'/fd'))
      except FileNotFoundError:open_stage=False
      if open_stage:
       if sys.argv[1] in {'cancel_B','04f_busy_cancel'}:subject._notify_cancel()
       else:child.process.kill()
       fault_killed=True
   if sys.argv[1] in faults:
    assert subject.orphan_hold and subject._r4 is not None
    assert [job['state'] for job in subject.store.read()['jobs']]==['running','queued','queued']
    assert not subject.dispatch_one() and not subject.store.read()['last_verified_success_by_store']
    if sys.argv[1] in {'cap_shrunk','swap_enabled','tasks_changed'}:assert gate_checks==[]
    print(json.dumps(dict(fault=sys.argv[1],orphan_hold=True,next_fifo=False)))
    break
   if sys.argv[1] in {'validator_death','pre_ready_exit'}:
    assert (fault_killed or sys.argv[1]=='pre_ready_exit') and subject.orphan_hold and subject._r4 is not None
    assert [job['state'] for job in subject.store.read()['jobs']]==['running','queued','queued']
    assert not subject.dispatch_one() and not subject.store.read()['last_verified_success_by_store']
    diagnostic=subject._r4.first_hold_diagnostic
    if sys.argv[1]=='pre_ready_exit':
     assert diagnostic['gate_id']=='worker_bootstrap' and diagnostic['child_exit_code']==3
     assert not diagnostic['source_gate_verified'] and not diagnostic['source_open_started']
     assert set(subject._r4.children)=={'worker'} and gate_checks==[]
    print(json.dumps(dict(crash=sys.argv[1],orphan_hold=True,next_fifo=False,diagnostic=diagnostic,
     source_hashes_unchanged=before==[hashes(p.source) for p in policies])))
    break
   if sys.argv[1].startswith('04e_') and subject.orphan_hold:
    assert [job['state'] for job in subject.store.read()['jobs']]==['running','queued','queued']
    assert subject.store.read()['jobs'][0]['audit_result'] is None
    assert not subject.dispatch_one() and not subject.store.read()['last_verified_success_by_store']
    print(json.dumps(dict(fault=sys.argv[1],positive_release=False,orphan_hold=True,
     source_hashes_unchanged=before==[hashes(p.source) for p in policies])))
    break
   if subject.orphan_hold or subject.process is not None:
    log.flush();raise AssertionError((subject._r4.phase,subject.store.read(),(root/'children.log').read_text()))
   assert len(subject.r4_proofs)==number+1
   assert subject.r4_proofs[-1]['empty_observations']==2
   if sys.argv[1].startswith('04e_'):break
   if sys.argv[1]=='helper_death':break
  if sys.argv[1].startswith('04e_'):
   final=subject.store.read()
   if not subject.orphan_hold:
    assert [job['state'] for job in final['jobs']]==['deferred','queued','queued']
    assert final['jobs'][0]['reason_code']=='worker_crashed' and final['jobs'][0]['audit_result']['snapshot_id'] is None
    assert subject.r4_proofs[-1]['helper_reaped'] and subject.r4_proofs[-1]['cleanup_complete']
    assert subject.r4_proofs[-1]['snapshot'] is None
    assert not final['last_verified_success_by_store']
    print(json.dumps(dict(fault=sys.argv[1],positive_release=True,source_hashes_unchanged=before==[hashes(p.source) for p in policies])))
  elif sys.argv[1] in {'validator_death','pre_ready_exit'} or sys.argv[1] in faults:pass
  elif sys.argv[1]=='helper_death':
   assert fault_killed and subject.store.read()['jobs'][0]['state']=='deferred'
   assert subject.store.read()['jobs'][0]['audit_result']['reason_code']=='worker_crashed'
   assert subject.store.read()['jobs'][0]['audit_result']['result']=='incomplete'
   assert subject.r4_proofs[-1]['helper_reaped'] and subject.r4_proofs[-1]['snapshot'] is None
   print(json.dumps(dict(crash='helper_death',positive_release=True,source_hashes_unchanged=before==[hashes(p.source) for p in policies])))
  else:
   final=subject.store.read();states=[job['state'] for job in final['jobs']]
   failed_callbacks={'04f_bad_status','04f_page_budget','04f_busy_deadline'}
   expected=['deferred']*3 if sys.argv[1] in failed_callbacks else ['completed','failed','completed'] if sys.argv[1]=='controlled_B' else ['completed','canceled','completed'] if sys.argv[1] in {'cancel_B','04f_busy_cancel'} else ['completed']*3
   assert states==expected,states
   if sys.argv[1] in {'cancel_B','04f_busy_cancel'}:assert fault_killed and final['jobs'][1]['audit_result']['result']=='incomplete'
   if sys.argv[1] in failed_callbacks:
    assert not final['last_verified_success_by_store']
    assert all(p['snapshot'] is None for p in subject.r4_proofs)
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
   if session.final_fd is not None:os.close(session.final_fd)
   if session.owner_trace_fd is not None:os.close(session.owner_trace_fd)
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
@pytest.mark.parametrize('stage',['auth_document','profile_parse','parent_verify','parent_verified',
    'namespace_view','artifact','imports','receipt_open','chroot','chroot_entered','credential_drop',
    'credentials_dropped','owner_ready','begin_wait','source_guard','source_open','source_opened',
    'source_metadata','destination_open','backup_start','backup_progress','backup_complete',
    'connections_close','owner_done','owner_done_sent','cleanup','unreported','expired'])
def test_04E_native_actual_owner_boundary_is_reported_once_after_positive_reap(stage,record_property):
    process=subprocess.run([sys.executable,'-B','-E','-s','-c',PIPELINE_DRIVER,'04e_'+stage],cwd=ROOT,
        capture_output=True,text=True,timeout=30)
    assert process.returncode==0,process.stdout+process.stderr
    result=json.loads(process.stdout)
    assert result['source_hashes_unchanged']
    assert result['positive_release'] or stage in {'begin_wait','owner_ready'} and result['orphan_hold']
    events=[json.loads(line) for line in process.stderr.splitlines() if line.startswith('{"event":"qio226_r4_owner_outcome"')]
    assert len(events)==1
    item=events[0]
    assert item['stage']==('owner_ready' if stage=='expired' else stage)
    assert item['child_exit_code']==(-9 if stage=='begin_wait' else 3)
    if stage=='unreported':assert item['report_status']=='unavailable'
    elif stage=='begin_wait':assert item['report_status']=='stage_only'
    else:assert item['report_status']=='failure'
    if stage=='expired':assert item['outcome']=='deadline' and item['stop_reason']=='deadline'
    elif not item['owner_ready_received']:assert item['outcome']=='pre_ready_exit'
    else:assert item['outcome']=='backup_abort'
    assert not any(value in json.dumps(item) for value in ('SECRET','CANARY','/source','nonce','SQL'))
    record_property('04e_owner_diagnostic',json.dumps(item,sort_keys=True))


@NATIVE
def test_04E_native_real_cancel_and_success_keep_original_three_job_release_semantics(record_property):
    process=subprocess.run([sys.executable,'-B','-E','-s','-c',PIPELINE_DRIVER,'cancel_B'],cwd=ROOT,
        capture_output=True,text=True,timeout=60)
    assert process.returncode==0,process.stdout+process.stderr
    result=json.loads(process.stdout)
    assert result['states']==['completed','canceled','completed'] and result['source_hashes_unchanged']
    events=[json.loads(line) for line in process.stderr.splitlines() if line.startswith('{"event":"qio226_r4_owner_outcome"')]
    assert len(events)==3 and [event['outcome'] for event in events]==['complete','canceled','complete']
    # Existing CoordinatorError normalizes canceled to this closed API code;
    # diagnostic stop_reason disambiguates it without changing that contract.
    assert events[1]['coordinator_code']=='coordinator_unavailable' and events[1]['stop_reason']=='canceled'
    assert [event['child_exit_code'] for event in events]==[0,3,0]
    assert [events[i]['stage'] for i in (0,2)]==['finished','finished']
    record_property('04e_cancel_and_success',json.dumps(events,sort_keys=True))


@NATIVE
@pytest.mark.parametrize('scenario',['04f_busy_once','04f_busy_deadline','04f_bad_status','04f_page_budget','04f_busy_cancel'])
def test_04F_actual_owner_callback_abi_bounded_failure_and_positive_release(scenario,record_property):
    process=subprocess.run([sys.executable,'-B','-E','-s','-c',PIPELINE_DRIVER,scenario],cwd=ROOT,
        capture_output=True,text=True,timeout=60)
    assert process.returncode==0,process.stdout+process.stderr
    result=json.loads(process.stdout)
    assert result['source_hashes_unchanged'] and len(result['proofs'])==3
    events=[json.loads(line) for line in process.stderr.splitlines() if line.startswith('{"event":"qio226_r4_owner_outcome"')]
    assert len(events)==3
    assert all(p['helper_reaped'] and p['gatekeeper_reaped'] and p['cleanup_complete']
        and p['shmem_zero'] and p['empty_observations']==2 for p in result['proofs'])
    if scenario=='04f_busy_once':
        assert result['states']==['completed']*3
        assert all(e['backup']['busy']==1 and e['backup']['done']==1 and e['backup']['complete']
            and e['outcome']=='complete' and e['child_exit_code']==0 for e in events)
    elif scenario=='04f_busy_cancel':
        assert result['states']==['completed','canceled','completed']
        assert events[1]['stop_reason']=='canceled' and not events[1]['owner_done_received']
        assert events[1]['backup']['status']==5 and events[1]['backup']['busy']>0
    else:
        assert result['states']==['deferred']*3
        assert all(e['child_exit_code']==3 and not e['owner_done_received'] for e in events)
        if scenario=='04f_busy_deadline':
            assert all(e['stop_reason']=='deadline' and e['backup']['status']==5 for e in events)
        else:
            check='callback_status' if scenario=='04f_bad_status' else 'callback_page_budget'
            assert all(e['backup']['check']==check and e['coordinator_code']=='not_admitted' for e in events)
    record_property('04f_native_callback_and_release',json.dumps(dict(scenario=scenario,events=events,result=result),sort_keys=True))


@NATIVE
def test_04D_pre_ready_worker_exit_has_positive_reap_and_one_private_first_hold(record_property):
    process=subprocess.run([sys.executable,'-B','-E','-s','-c',PIPELINE_DRIVER,'pre_ready_exit'],cwd=ROOT,
        capture_output=True,text=True,timeout=30)
    assert process.returncode==0,process.stdout+process.stderr
    result=json.loads(process.stdout)
    events=[json.loads(line) for line in process.stderr.splitlines() if line.startswith('{"event":"qio226_r4_first_hold"')]
    assert len(events)==1 and events[0]==result['diagnostic']
    assert events[0]['event']=='qio226_r4_first_hold' and events[0]['child_exit_code']==3
    assert events[0]['gate_id']=='worker_bootstrap' and events[0]['child_role']=='worker'
    assert not events[0]['source_gate_verified'] and not events[0]['source_open_started']
    assert result['orphan_hold'] and not result['next_fifo'] and result['source_hashes_unchanged']
    record_property('04d_synthetic_first_hold',json.dumps(events[0],sort_keys=True))


@NATIVE
@pytest.mark.parametrize('scenario',['stage_sidecar','stage_symlink','stage_hardlink','rename_collision','source_replaced','image_tamper',
    'cap_shrunk','swap_enabled','tasks_changed'])
def test_K04_K05_native_incomplete_alias_or_tampered_image_cannot_pass(scenario,record_property):
    process=subprocess.run([sys.executable,'-B','-E','-s','-c',PIPELINE_DRIVER,scenario],cwd=ROOT,
        capture_output=True,text=True,timeout=60)
    assert process.returncode==0,process.stdout+process.stderr
    result=json.loads(process.stdout)
    assert result['fault']==scenario and result['orphan_hold'] and not result['next_fifo']
    events=[json.loads(line) for line in process.stderr.splitlines() if line.startswith('{"event":"qio226_r4_first_hold"')]
    assert len(events)==1 and events[0]['event']=='qio226_r4_first_hold'
    if scenario in {'cap_shrunk','swap_enabled','tasks_changed'}:
        assert events[0]['gate_id']=='resource_leaf' and events[0]['child_role'] is None
        assert events[0]['child_exit_code'] is None and not events[0]['source_open_started']
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
