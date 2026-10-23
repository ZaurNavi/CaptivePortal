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


def large_projection_fixture(db):
    """Canonical 117MiB+ C with 16k REAL adapter rows, no surviving padding."""
    from app.traffic_projection.models import PROJECTION_VERSION,SEMANTIC_CONTRACT_SHA256
    at='2026-10-19T00:00:00.000Z'
    db.execute('INSERT INTO traffic_projection_versions(projection_version,projection_schema_version,source,source_schema_version,semantic_contract_sha256,status,created_at) VALUES(?,1,?,1,?,?,?)',
        (PROJECTION_VERSION,'observations',SEMANTIC_CONTRACT_SHA256,'active',at))
    db.execute('BEGIN')
    db.executemany('INSERT INTO traffic_projection_site_state(projection_version,site_id,projection_revision,status,last_error_category) VALUES(?,?,0,?,?)',
        ((PROJECTION_VERSION,'synthetic-site-'+str(n),'healthy','x'*8192) for n in range(16000)))
    db.execute('COMMIT')
    assert db.execute('PRAGMA page_size').fetchone()[0]*db.execute('PRAGMA page_count').fetchone()[0]>=117*1024**2


def dense_04I_projection_fixture(db,cycles=65536):
    """Synthetic C: one site, real cycles/AP rows, no padding or large errors.

    Row count is a declared synthetic workload, NOT inferred original C data.
    All keys/times are deterministic so 04H/04I image hashes can be compared.
    """
    from datetime import datetime,timedelta,timezone
    from app.traffic_projection.models import PROJECTION_VERSION,SEMANTIC_CONTRACT_SHA256
    at='2026-10-19T00:00:00.000Z';version=PROJECTION_VERSION;site='synthetic-site-04i'
    db.execute('INSERT INTO traffic_projection_versions(projection_version,projection_schema_version,source,source_schema_version,semantic_contract_sha256,status,created_at) VALUES(?,1,?,1,?,?,?)',
        (version,'observations',SEMANTIC_CONTRACT_SHA256,'active',at))
    db.execute("INSERT INTO traffic_projection_site_state(projection_version,site_id,projection_revision,status) VALUES(?,?,0,'healthy')",(version,site))
    columns=[r[1] for r in db.execute('PRAGMA table_info(traffic_projection_cycles)')]
    required={r[1]:r[2] for r in db.execute('PRAGMA table_info(traffic_projection_cycles)') if r[3]}
    base={name:(0 if kind=='INTEGER' else at if name.endswith('_at') else 'synthetic') for name,kind in required.items()}
    base.update(projection_version=version,site_id=site,source_kind='ap_traffic',source_state='completed',
        source_revision_marker='a'*64,source_semantic_fingerprint='b'*64,integrity_ok=1,
        stored_row_count=2,items_seen=2,items_stored=2,source_complete=1,source_result='success',
        metric_facts_present=1,wired_complete=1,lan_complete=1,wired_pair_count=2,lan_pair_count=2,
        wired_download_mbps=12.5,wired_upload_mbps=3.25,lan_download_mbps=7.5,lan_upload_mbps=1.25,
        wired_ok_count=2,lan_ok_count=2)
    start=datetime(2026,10,1,tzinfo=timezone.utc)
    def cycle_rows():
        for n in range(cycles):
            stamp=(start+timedelta(seconds=15*n)).isoformat(timespec='milliseconds').replace('+00:00','Z')
            row=dict(base,cycle_id=f'synthetic-cycle-{n:08d}',source_started_at=stamp,source_finished_at=stamp,
                source_updated_at=stamp,projected_at=stamp,wired_oldest_at=stamp,wired_newest_at=stamp,
                lan_oldest_at=stamp,lan_newest_at=stamp)
            yield tuple(row.get(name) for name in columns)
    db.execute('BEGIN')
    db.executemany('INSERT INTO traffic_projection_cycles('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')',cycle_rows())
    db.executemany('INSERT INTO traffic_projection_ap_cycles VALUES('+','.join('?' for _ in range(21))+')',
        ((version,site,f'synthetic-cycle-{n:08d}',f'02:00:00:00:00:{ap:02x}',f'Synthetic AP {ap}',
          0,1,1,1,1,at,at,6.25,1.625,'ok','ok',3.75,.625,'ok','ok',at)
         for n in range(cycles) for ap in range(2)))
    db.execute('COMMIT')
    return dict(cycles=cycles,ap_rows=cycles*2,total_rows=cycles*3+2,
        image_bytes=db.execute('PRAGMA page_size').fetchone()[0]*db.execute('PRAGMA page_count').fetchone()[0])


DIRFD_DRIVER=r'''
import array,errno,json,os,shutil,sqlite3,sys,tempfile,uuid,time,types,subprocess
from dataclasses import replace
from pathlib import Path
from app.db_audit_coordinator import contracts as c,r4_ipc,r4_snapshot,r4_sandbox
from app.db_audit_coordinator.live_receipts import identity
from app.db_audit_coordinator.live_sqlite import validate_snapshot,T3Trace
from tests.db_audit_coordinator.test_b2_live_sqlite import disposable
from tests.db_audit_coordinator.test_qio226_r4_native import large_projection_fixture
assert os.geteuid()==0 and os.getpid()==1
store,fault=sys.argv[1:];root=Path(tempfile.mkdtemp(prefix='qio226-04d-private-'));root.chmod(0o755)
namespace=ram=writer=None;image_fd=final_fd=None
def sha(path):return __import__('hashlib').sha256(Path(path).read_bytes()).hexdigest()
try:
 protected=root/'socket-parent';protected.mkdir(mode=0o750);os.chown(protected,0,992)
 base=protected/'ram-jobs';base.mkdir(mode=0o711)
 namespace=r4_sandbox.MountNamespace().enter()
 large=fault.startswith('04h_large')
 ram=r4_sandbox.PrivateTmpfs(namespace,str(uuid.uuid4()),str(uuid.uuid4()),(192 if large else 16)*1024**2,64,1003,1004,993,_base=str(base))
 source=root/'source';source.mkdir(mode=0o700)
 writer,policy=disposable(source,store)
 if fault=='vm_cancel':
  writer.executemany('INSERT INTO traffic_daily VALUES(?,?,?,?,?)',(('2026-10-19','vm-fixture-'+str(n),1,1,'2026-10-19T00:00:00.000Z') for n in range(1500)))
 if large:
  large_projection_fixture(writer)
  policy=replace(policy,image_max_bytes=192*1024**2,source_max_bytes=192*1024**2,memory_max_bytes=512*1024**2,attempt_seconds=1200)
 old_module=None
 if fault=='04h_large_baseline_prefix':
  raw=subprocess.check_output(['git','-c','safe.directory='+os.getcwd(),'show','46e66c36bbb61b2bd80e0ca9025c21e554a55eaa:app/db_audit_coordinator/r4_snapshot.py'])
  old_module=types.ModuleType('app.db_audit_coordinator._04g_snapshot');old_module.__package__='app.db_audit_coordinator'
  exec(compile(raw,'04G-exact-r4_snapshot.py','exec'),old_module.__dict__)
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
    ticks=[0];trace=T3Trace();digest_calls=[]
    actual_digest=r4_snapshot.digest_fd
    def measured_digest(fd,maximum):
     value=actual_digest(fd,maximum);digest_calls.append(value['size'])
     if fault=='final_digest' and len(digest_calls)==3:return dict(value,sha256='0'*64)
     return value
    r4_snapshot.digest_fd=measured_digest
    if old_module is not None:old_module.digest_fd=measured_digest
    if fault=='unexpected_import':
     from app.db_audit_coordinator import live_sqlite
     def missing(*args,**kwargs):raise ModuleNotFoundError('SECRET synthetic missing dependency')
     live_sqlite.validate_snapshot=missing
    test_cwd=os.open('.',os.O_RDONLY|os.O_DIRECTORY) if fault=='cwd_change' else None
    opened_databases=[];native_connect=sqlite3.connect
    def connect(filename,**kwargs):
     assert filename=='file:/proc/self/fd/'+str(received[1])+'/snapshot.sqlite3?mode=ro&immutable=1'
     assert kwargs==dict(uri=True,isolation_level=None,timeout=0)
     if fault=='tamper_after_close':
      class FinalClose(sqlite3.Connection):
       def close(self):
        super().close();child_control.send(b'T');assert child_control.recv(1)==b'A'
      kwargs['factory']=FinalClose
     db=native_connect(filename,**kwargs);opened_databases.append(db);return db
    sqlite3.connect=connect
    def guard():
     ticks[0]+=1
     assert identity(os.stat('.'))==cwd
     if fault=='vm_cancel' and trace.counts['progress_callbacks']:raise c.CoordinatorError('canceled')
     if fault=='row_cancel' and trace.stage=='adapter_validate':raise c.CoordinatorError('canceled')
     if fault in {'04h_large_baseline_prefix','04h_large_candidate_prefix'} and ticks[0]>=12:
      raise c.CoordinatorError('canceled')
     if ticks[0]==3:
      if fault=='cancel':raise c.CoordinatorError('canceled')
      if fault=='deadline':raise c.CoordinatorError('not_admitted')
      if fault=='cwd_change':os.chdir('/')  # Test-only violation: validator must reject it.
      if fault in {'tamper_during_t3','same_size_rewrite','restore_mtime'}:
       child_control.send(b'T');assert child_control.recv(1)==b'A'
    try:
     wall=time.monotonic();cpu=time.process_time()
     if old_module is not None:answer=old_module.validate(received[0],received[1],payload['image'],payload['directory'],policy,guard)
     else:answer=r4_snapshot.validate(received[0],received[1],payload['image'],payload['directory'],policy,guard,trace=trace)
     assert fault in {'positive','04h_large'},fault
     assert answer==expected;result['canonical_t3']='PASS';result['guard_calls']=ticks[0]
    except Exception as error:
     assert fault not in {'positive','04h_large'},(type(error).__name__,str(error))
     result['rejected']=type(error).__name__
     if fault=='cwd_change':
      assert identity(os.stat('.'))!=cwd;result['injected_cwd_change_rejected']=True
    finally:
     result['t3_diagnostic']=trace.document();result['actual_digest_calls']=len(digest_calls)
     result.update(guard_calls=ticks[0],full_bytes_hashed=sum(digest_calls),image_bytes=receipt['size'],
      wall_seconds=time.monotonic()-wall,cpu_seconds=time.process_time()-cpu,
      actual_adapter_rows=16000 if large else None)
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
 if fault in {'tamper_during_t3','same_size_rewrite','restore_mtime','tamper_after_close'}:
  control.settimeout(5);assert control.recv(1)==b'T'
  if fault=='tamper_during_t3':
   image.rename(ram.final/'old-image');image.write_bytes((ram.final/'old-image').read_bytes())
   os.chown(image,0,993);image.chmod(0o440)
  else:
   metadata=image.stat();write_fd=os.open(image,os.O_WRONLY)
   os.pwrite(write_fd,b'changed!' if fault=='tamper_after_close' else os.pread(image_fd,8,100),100);os.close(write_fd)
   if fault=='restore_mtime':os.utime(image,ns=(metadata.st_atime_ns,metadata.st_mtime_ns))
  control.send(b'A')
 result=json.loads(os.read(read,8192));pid,status=os.waitpid(child,0)
 assert pid==child and os.waitstatus_to_exitcode(status)==0,result
 assert before=={p.name:sha(p) for p in source.iterdir()}
 if fault in {'positive','04h_large'}:
  assert image_before==sha(image) and set(os.listdir(final_fd))=={'snapshot.sqlite3'}
 result.update(store=store,source_bytes_unchanged=True,private_pidns=True,
  worker_t3='PASS' if fault in {'positive','04h_large'} else 'REJECTED',fault=fault,kernel=os.uname().release)
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
@pytest.mark.parametrize('fault',['same_size_rewrite','restore_mtime','tamper_after_close','final_digest','vm_cancel','row_cancel','unexpected_import'])
def test_04H_native_fast_stat_strong_final_hash_and_wrapped_interrupt_fail_closed(fault,record_property):
    process=subprocess.run(['unshare','--mount','--pid','--fork','--propagation','private','--mount-proc',
        sys.executable,'-B','-E','-s','-c',DIRFD_DRIVER,'public_traffic',fault],cwd=ROOT,
        capture_output=True,text=True,timeout=30)
    assert process.returncode==0,process.stdout+process.stderr
    result=json.loads(process.stdout);diagnostic=result['t3_diagnostic']
    assert result['worker_t3']=='REJECTED' and result['received_fds_closed'] and result['source_bytes_unchanged']
    if fault in {'vm_cancel','row_cancel'}:
        assert diagnostic['category']=='resource_guard' and diagnostic['check']=='resource_guard'
        assert diagnostic['exception_class']=='CoordinatorError'
    elif fault=='unexpected_import':
        assert diagnostic['category']=='unexpected' and diagnostic['check']=='unexpected'
        assert diagnostic['exception_class']=='ModuleNotFoundError'
    else:assert diagnostic['category']=='snapshot_tamper'
    if fault=='final_digest':assert result['actual_digest_calls']==3 and diagnostic['check']=='image_digest'
    record_property('04h_native_guard',json.dumps(result,sort_keys=True))


@NATIVE
def test_04H_117MiB_real_C_rows_full_T3_and_measured_hash_amplification(record_property):
    results={}
    for fault in ('04h_large_baseline_prefix','04h_large_candidate_prefix','04h_large'):
        process=subprocess.run(['unshare','--mount','--pid','--fork','--propagation','private','--mount-proc',
            sys.executable,'-B','-E','-s','-c',DIRFD_DRIVER,'traffic_projection',fault],cwd=ROOT,
            capture_output=True,text=True,timeout=1200)
        assert process.returncode==0,process.stdout+process.stderr
        results[fault]=json.loads(process.stdout)
    baseline=results['04h_large_baseline_prefix'];prefix=results['04h_large_candidate_prefix'];full=results['04h_large']
    assert baseline['guard_calls']==prefix['guard_calls']==12
    assert baseline['actual_digest_calls']==11 and prefix['actual_digest_calls']==2
    assert baseline['full_bytes_hashed']>full['full_bytes_hashed']>prefix['full_bytes_hashed']
    assert full['image_bytes']>=117*1024**2 and full['actual_adapter_rows']==16000
    assert full['worker_t3']=='PASS' and full['guard_calls']>16000
    assert full['actual_digest_calls']==full['t3_diagnostic']['digest_full_count']==3
    assert full['t3_diagnostic']['progress_callbacks']>0 and full['t3_diagnostic']['check']=='t3_complete'
    assert full['full_bytes_hashed']==3*full['image_bytes']
    assert all(r['source_bytes_unchanged'] and r['received_fds_closed'] for r in results.values())
    record_property('04h_large_C_hash_evidence',json.dumps(results,sort_keys=True))


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


PLATEAU_DRIVER=r'''
import hashlib,json,os,select,socket,sqlite3,sys,tempfile,uuid
from pathlib import Path
from app.db_audit_coordinator.r4_sandbox import MountNamespace,PrivateTmpfs,drop_owner
mode=sys.argv[1];pinned=sys.argv[2]=='pinned'
with tempfile.TemporaryDirectory(prefix='qio226-04g-native-') as temporary:
 root=Path(temporary);root.chmod(0o711)
 folder=root/'original';folder.mkdir(mode=0o700);path=folder/'source.db'
 # Fixture construction ONLY. A writer exit with an empty native WAL leaves
 # no DMS holder; no operator/source checkpoint is part of the implementation.
 def build():
  db=sqlite3.connect(path,isolation_level=None)
  db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=FULL')
  db.execute('CREATE TABLE evidence(id INTEGER PRIMARY KEY,value TEXT NOT NULL)')
  db.execute('BEGIN')
  db.executemany('INSERT INTO evidence VALUES(?,?)',[(i,'x'*4000) for i in range(1,227)])
  db.execute('COMMIT')
  return db
 writer=keeper=None
 if mode in {'empty_wal','nonempty_wal'}:
  pid=os.fork()
  if pid==0:
   db=build()
   if mode=='empty_wal':assert db.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()==(0,0,0)
   os._exit(0)  # Native file state, no fabricated SHM/header/lock.
  assert os.waitstatus_to_exitcode(os.waitpid(pid,0)[1])==0
 else:
  writer=build()
  keeper=sqlite3.connect(path,isolation_level=None);keeper.execute('BEGIN')
  assert keeper.execute('SELECT count(*) FROM evidence').fetchone()==(226,)
 for file in folder.iterdir():os.chown(file,1000,1000);file.chmod(0o600)
 os.chown(folder,1000,1000)
 suffixes=('','-wal','-shm')
 before={s:hashlib.sha256(Path(str(path)+s).read_bytes()).hexdigest() for s in suffixes}
 wal_size=Path(str(path)+'-wal').stat().st_size
 base=root/'jobs';base.mkdir(mode=0o711)
 ns=MountNamespace().enter();job=None;fds={}
 try:
  fds={key:os.open(str(path)+suffix,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
       for key,suffix in (('main',''),('wal','-wal'),('shm','-shm'))}
  job=PrivateTmpfs(ns,str(uuid.uuid4()),str(uuid.uuid4()),4*1024**2,64,1000,1000,1001,_base=str(base))
  job.source_view(fds)
  read,write=os.pipe();parent,child=socket.socketpair()
  pid=os.fork()
  if pid==0:
   try:
    os.close(read);parent.close()
    for item in os.listdir('/proc/self/fd'):
     fd=int(item)
     if fd>2 and fd not in {write,child.fileno()}:
      try:os.close(fd)
      except OSError:pass
    os.chroot(str(job.owner_root));os.chdir('/');drop_owner(1000,1000)
    assert not Path('/proc').exists()
    for suffix in suffixes:
     try:fd=os.open('/source/input.sqlite3'+suffix,os.O_WRONLY)
     except OSError:pass
     else:os.close(fd);raise AssertionError('source_write_allowed')
    src=sqlite3.connect('file:/source/input.sqlite3?mode=ro',uri=True,isolation_level=None,timeout=0)
    src.execute('PRAGMA query_only=ON');src.execute('PRAGMA busy_timeout=0')
    if pinned:src.execute('BEGIN')
    src.execute('PRAGMA user_version').fetchone();src.execute('PRAGMA page_size').fetchone()
    count=src.execute('PRAGMA page_count').fetchone()[0];assert count==228
    dst=sqlite3.connect('/stage/snapshot.sqlite3',isolation_level=None,timeout=0)
    calls=[];complete=False
    def progress(code,remaining,total):
     calls.append([code,remaining,total])
     if len(calls)>=8:raise RuntimeError('finite_fixture_stop')
     if mode=='mutating' and code==0:
      child.sendall(b'w');assert child.recv(1)==b'a'
    try:
     src.backup(dst,pages=128,progress=progress,sleep=0)
     complete=True
     assert dst.execute('SELECT count(*),min(length(value)) FROM evidence').fetchone()==(226,4000)
     assert dst.execute('SELECT value FROM evidence WHERE id=1').fetchone()==('x'*4000,)
     assert dst.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
    except RuntimeError as error:assert str(error)=='finite_fixture_stop'
    assert src.in_transaction==pinned
    dst.close();src.close()
    try:src.execute('SELECT 1')
    except sqlite3.ProgrammingError:pass
    else:raise AssertionError('connection_not_closed')
    os.write(write,json.dumps(dict(calls=calls,complete=complete,page_count=count)).encode());os._exit(0)
   except BaseException as error:
    os.write(write,json.dumps(dict(error=type(error).__name__)).encode());os._exit(3)
  os.close(write);child.close();updates=0
  while True:
   ready=select.select([read,parent],[],[],10)[0];assert ready
   if parent in ready:
    request=parent.recv(1)
    if request:
     assert request==b'w' and writer is not None;updates+=1
     writer.execute('UPDATE evidence SET value=? WHERE id=1',(str(updates).ljust(4000,'!'),))
     parent.sendall(b'a')
   if read in ready:
    raw=os.read(read,4096);os.close(read);break
  parent.close();_,status=os.waitpid(pid,0);result=json.loads(raw)
  assert os.waitstatus_to_exitcode(status)==0,result
  result.update(mode=mode,pinned=pinned,writer_commits=updates,wal_bytes_before=wal_size,
   python=sys.version,sqlite=sqlite3.sqlite_version,source_hashes_unchanged={s:
    hashlib.sha256(Path(str(path)+s).read_bytes()).hexdigest()==digest for s,digest in before.items()})
  for item in job.stage.iterdir():item.unlink()
  print(json.dumps(result,sort_keys=True))
 finally:
  for fd in fds.values():os.close(fd)
  if job is not None:job.cleanup()
  ns.restore()
  if keeper is not None:keeper.close()
  if writer is not None:writer.close()
'''


@NATIVE
@pytest.mark.parametrize('mode',['empty_wal','nonempty_wal','stable_writer','mutating'])
@pytest.mark.parametrize('view',['autocommit','pinned'])
def test_04G_native_exact_128_page_plateau_and_single_read_view(mode,view,record_property):
    process=subprocess.run([sys.executable,'-B','-E','-s','-c',PLATEAU_DRIVER,mode,view],
        cwd=ROOT,capture_output=True,text=True,timeout=20)
    assert process.returncode==0,process.stdout+process.stderr
    result=json.loads(process.stdout);calls=result['calls']
    stalled=view=='autocommit' and mode in {'empty_wal','mutating'}
    assert result['complete'] is not stalled
    if stalled:assert calls==[[0,100,228]]*8  # EXACT 128-page plateau, not BUSY.
    else:assert calls==[[0,100,228],[101,0,228]]
    if mode=='mutating':assert result['writer_commits']==(7 if stalled else 1)
    else:assert result['writer_commits']==0 and all(result['source_hashes_unchanged'].values())
    if mode=='empty_wal':assert result['wal_bytes_before']==0
    record_property('04g_native_plateau',json.dumps(result,sort_keys=True))


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
if len(sys.argv)>3 and sys.argv[3].startswith('04i_'):
 from tests.db_audit_coordinator.test_qio226_r4_native import install_04I_cost_probe
 install_04I_cost_probe()
elif len(sys.argv)>3 and sys.argv[3].startswith('04j_'):
 from tests.db_audit_coordinator.test_qio226_r4_native import install_04I_cost_probe,install_04J_sample_probe
 install_04I_cost_probe();install_04J_sample_probe()
elif len(sys.argv)>3 and sys.argv[3]=='04k_age':
 from tests.db_audit_coordinator.test_qio226_r4_native import install_04K_worker_clock
 install_04K_worker_clock()
try:os._exit(worker.execute(int(sys.argv[1])))
except BaseException:traceback.print_exc();os._exit(3)
'''


def install_04I_cost_probe():
    """QA-only aggregate observer. NEVER installed or an authorization source.

    Every original guard/VM callback and digest still executes. Timings overlap
    (SQLite/canonical include guard CPU); they must not be summed as disjoint.
    At most six checkpoints and one final record per T3, no row/SQL logging.
    """
    import resource
    import sqlite3
    import time
    from app.db_audit_coordinator import contracts,r4_snapshot
    from app.traffic_projection.repository import TrafficProjectionRepository
    native_validate=r4_snapshot.validate
    def measured(fd,parent,receipt,folder_receipt,policy,guard,**kwargs):
        trace=kwargs['trace'];started=time.monotonic();cpu=time.process_time();usage=resource.getrusage(resource.RUSAGE_SELF)
        def io():
            try:
                return {key:int(value) for key,value in (line.split(':') for line in Path('/proc/self/io').read_text().splitlines())
                    if key in {'rchar','wchar','syscr','syscw','read_bytes','write_bytes','cancelled_write_bytes'}}
            except PermissionError:return {}  # Some UID-drop procfs denies io; never change dumpability.
        initial_io=io();counts=dict(guard=0,encode=0);cost=dict(guard_wall=0.,guard_cpu=0.,encode_cpu=0.,canonical_wall=0.,canonical_cpu=0.)
        scans={name:dict(count=0,wall=0.,cpu=0.) for name in ('integrity_check','foreign_key_check','quick_check')}
        canonical_deep=[];phase_cost={};checkpoints={1,10000,50000,100000,200000,400000}
        def emit(kind):
            now_usage=resource.getrusage(resource.RUSAGE_SELF);current=io()
            print(json.dumps(dict(event='qio226_04i_private_cost',kind=kind,store=policy.store_id,
                uid=os.geteuid(),gid=os.getegid(),groups=os.getgroups(),elapsed_s=time.monotonic()-started,
                cpu_s=time.process_time()-cpu,user_s=now_usage.ru_utime-usage.ru_utime,system_s=now_usage.ru_stime-usage.ru_stime,
                peak_rss_kib=now_usage.ru_maxrss,io={key:current[key]-initial_io[key] for key in initial_io},
                counts=counts,cost=cost,phase_cost=phase_cost,scans=scans,canonical_deep=canonical_deep,
                image_sha256=receipt['sha256'],image_bytes=receipt['size'],trace=trace.document()),sort_keys=True),file=sys.stderr,flush=True)
        def observed_guard():
            stage=trace.stage;wall=time.monotonic();tick=time.process_time()
            try:return guard()
            finally:
                wall=time.monotonic()-wall;tick=time.process_time()-tick
                counts['guard']+=1;cost['guard_wall']+=wall;cost['guard_cpu']+=tick
                bucket=phase_cost.setdefault(stage,dict(guard_count=0,guard_wall=0.,guard_cpu=0.))
                bucket['guard_count']+=1;bucket['guard_wall']+=wall;bucket['guard_cpu']+=tick
                if counts['guard'] in checkpoints:emit('checkpoint')
        encode=contracts.encode;canonical=TrafficProjectionRepository._validate;connect=sqlite3.connect
        def observed_encode(*args,**options):
            tick=time.process_time()
            try:return encode(*args,**options)
            finally:counts['encode']+=1;cost['encode_cpu']+=time.process_time()-tick
        def observed_canonical(db,*,deep=True):
            canonical_deep.append(deep);wall=time.monotonic();tick=time.process_time()
            try:return canonical(db,deep=deep)
            finally:cost['canonical_wall']+=time.monotonic()-wall;cost['canonical_cpu']+=time.process_time()-tick
        class ObservedConnection(sqlite3.Connection):
            def execute(self,sql,*args,**options):
                name=sql.removeprefix('PRAGMA ')
                if name not in scans:return super().execute(sql,*args,**options)
                item=scans[name];item['count']+=1;wall=time.monotonic();tick=time.process_time()
                try:return super().execute(sql,*args,**options)
                finally:item['wall']+=time.monotonic()-wall;item['cpu']+=time.process_time()-tick
        def observed_connect(*args,**options):
            # T3 only. Canonical expected-signature :memory: connection unchanged.
            if args and isinstance(args[0],str) and args[0].startswith('file:/proc/self/fd/'):
                assert 'factory' not in options;options['factory']=ObservedConnection
            return connect(*args,**options)
        contracts.encode=observed_encode;TrafficProjectionRepository._validate=staticmethod(observed_canonical);sqlite3.connect=observed_connect
        try:return native_validate(fd,parent,receipt,folder_receipt,policy,observed_guard,**kwargs)
        finally:
            contracts.encode=encode;TrafficProjectionRepository._validate=staticmethod(canonical);sqlite3.connect=connect
            emit('final')
    r4_snapshot.validate=measured


def pipeline_04I_driver():
    """Exact disposable 04H pipeline, dense fixture and bounded QA observations.

    Literal substitutions are asserted unique; no production/profile/guard seam
    is added beyond the explicitly existing uninstalled-provenance QA harness.
    """
    replacements=[
        ("large=sys.argv[1]=='04h_large'", "large=sys.argv[1]=='04i_dense'"),
        ("modern=sys.argv[1].startswith('04h_')", "modern=True"),
        ("large_projection_fixture(writer)", "dense_04I_projection_fixture(writer)"),
        ("import large_projection_fixture", "import dense_04I_projection_fixture"),
        ("str(fd),str(ram)]", "str(fd),str(ram),sys.argv[1]]"),
        ("log=open(root/'children.log','wb')", "log=open(root/'children.log','wb');os.fchmod(log.fileno(),0o600)"),
        ("if log is not None:log.close()", "if log is not None:\n  log.flush();print((root/'children.log').read_text(),file=sys.stderr,flush=True);log.close()"),
    ]
    result=PIPELINE_DRIVER
    for old,new in replacements:
        assert result.count(old)==1,old
        result=result.replace(old,new)
    return result

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
  # 04K supersedes the old elapsed-abort expectation. Advance the clock while
  # genuinely BUSY, then release contention; it must finish naturally instead.
  original_mark=helper.OwnerTrace.mark
  def deadline_mark(self,name):
   original_mark(self,name)
   if name=='backup_start':
    real_ns=time.monotonic_ns;time.monotonic_ns=lambda:real_ns()+5401*10**9
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
    if scenario in {'04f_busy_once','04f_busy_deadline'} and code==5:
     blocker.execute('ROLLBACK')
   kwargs['progress']=observed
   try:return super().backup(target,**kwargs)
   finally:
    if blocker is not None:blocker.close()
 def callback_connect(filename,*args,**kwargs):
  if filename=='file:/source/input.sqlite3?mode=ro':kwargs['factory']=CallbackSource
  return native_connect(filename,*args,**kwargs)
 helper.sqlite3.connect=callback_connect
if scenario=='04k_age':
 from tests.db_audit_coordinator.test_qio226_r4_native import install_04K_owner_clock
 install_04K_owner_clock(helper)
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
from tests.db_audit_coordinator.test_b2_live_policy import profile,policy as fixture_policy,STORES
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
  large=sys.argv[1]=='04h_large'
  modern=sys.argv[1].startswith('04h_')
  if modern:
   os.chown(queue,0,993);os.chown(queue/'heavy.lock',0,993)
  policies=[]
  source_gids={'public_traffic':1004,'network_service_intelligence':1004,'traffic_projection':996}
  for store in STORES:
   source=root/store;source.mkdir(mode=0o700)
   if sys.argv[1]=='04g_quiescent':
    fixture_pid=os.fork()
    if fixture_pid==0:
     writer,policy=disposable(source,store)
     # Free pages enlarge the real canonical image without changing its final
     # schema/domain. No padding table survives fixture construction.
     writer.execute('CREATE TABLE fixture_padding(value)');writer.execute('BEGIN')
     writer.executemany('INSERT INTO fixture_padding VALUES(?)',[('x'*4000,)]*226)
     writer.execute('COMMIT');writer.execute('DROP TABLE fixture_padding')
     assert writer.execute('PRAGMA page_count').fetchone()[0]>128
     assert writer.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()==(0,0,0)
     os._exit(0)
    assert os.waitstatus_to_exitcode(os.waitpid(fixture_pid,0)[1])==0
    target=source/(store+'.db');info=target.stat()
    policy=fixture_policy(store,source=str(target),device=info.st_dev,inode=info.st_ino,uid=info.st_uid,gid=info.st_gid)
   else:
    writer,policy=disposable(source,store);writers.append(writer)
    if large and store=='traffic_projection':
     from tests.db_audit_coordinator.test_qio226_r4_native import large_projection_fixture
     large_projection_fixture(writer)
     policy=replace(policy,source_max_bytes=192*1024**2,wal_max_bytes=192*1024**2,image_max_bytes=192*1024**2,
      backup_overhead_bytes=16*1024**2,validator_overhead_bytes=32*1024**2,margin_bytes=16*1024**2,memory_max_bytes=512*1024**2)
   # Controlled B failure: disposable original fixture is invalid from birth;
   # no runtime source writes, no production failure injection API.
   if store=='network_service_intelligence' and sys.argv[1]=='controlled_B':
    writer.execute("UPDATE service_materialization_generations SET ruleset_digest_sha256='bad'")
   if store=='public_traffic' and sys.argv[1]=='04h_A_failure':
    writer.execute("UPDATE traffic_daily SET local_date='invalid-synthetic-date'")
   for file in source.iterdir():os.chown(file,1003,source_gids[store]);file.chmod(0o600)
   os.chown(source,1003,source_gids[store])
   policies.append(replace(policy,uid=1003,gid=source_gids[store],memory_max_bytes=(512 if large else 256)*1024**2,attempt_seconds=1200 if large else 30))
  ram=root/'ram';ram.mkdir(mode=0o711)
  cfg=R4Installation(R4_METHOD,True,1003,r4_sandbox.RAM_ROOT,ram.stat().st_dev,ram.stat().st_ino,16,64)
  value=profile(enabled=True,root=str(queue),release_root=os.getcwd(),python=sys.executable,
   delegated='/'+name+'/delegated',delegated_device=delegated.stat().st_dev,delegated_inode=delegated.stat().st_ino,
   worker_uid=995 if modern else 1000,worker_gid=993 if modern else 1000,worker_groups=(),stores=tuple(policies),r4=cfg)
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
   until=time.monotonic()+(1200 if large else 15)
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
       if sys.argv[1] in {'cancel_B','04f_busy_cancel'}:
        subject.cancel_scoped(session.job['job_id'],session.job['attempt_id'],session.job['claim_epoch'],c.scope(1002))
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
   failed_callbacks={'04f_bad_status','04f_page_budget'}
   expected=['failed','completed','completed'] if sys.argv[1]=='04h_A_failure' else ['deferred']*3 if sys.argv[1] in failed_callbacks else ['completed','failed','completed'] if sys.argv[1]=='controlled_B' else ['completed','canceled','completed'] if sys.argv[1] in {'cancel_B','04f_busy_cancel'} else ['completed']*3
   assert states==expected,states
   if sys.argv[1] in {'cancel_B','04f_busy_cancel'}:assert fault_killed and final['jobs'][1]['audit_result']['result']=='incomplete'
   if sys.argv[1] in failed_callbacks:
    assert not final['last_verified_success_by_store']
    assert all(p['snapshot'] is None for p in subject.r4_proofs)
   assert before==[hashes(policy.source) for policy in policies]
   assert not subject.dispatch_one() and not subject.orphan_hold
   assert len(gate_checks)==6
   print(json.dumps(dict(states=states,source_hashes_unchanged=True,proofs=subject.r4_proofs,
    kernel=os.uname().release,installed_qualification='NOT_CLAIMED_QA_ONLY',uids=[0,value.worker_uid,1003],
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
    assert item['stage']==('imports_verified' if stage=='expired' else stage)
    assert item['child_exit_code']==(-9 if stage=='begin_wait' else 3)
    if stage=='unreported':assert item['report_status']=='unavailable'
    elif stage=='begin_wait':assert item['report_status']=='stage_only'
    else:assert item['report_status']=='failure'
    if stage=='expired':
        # A forged finite deadline is now an invalid private auth document,
        # not an elapsed-job timeout. Closed schema/authorization stays strict.
        assert item['coordinator_code']=='unauthorized' and item['stop_reason'] is None
        assert item['outcome']=='pre_ready_exit'
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
    if scenario in {'04f_busy_once','04f_busy_deadline'}:
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
        check='callback_status' if scenario=='04f_bad_status' else 'callback_page_budget'
        assert all(e['backup']['check']==check and e['coordinator_code']=='not_admitted' for e in events)
    record_property('04f_native_callback_and_release',json.dumps(dict(scenario=scenario,events=events,result=result),sort_keys=True))


@NATIVE
def test_04G_actual_owner_empty_wal_large_canonical_ABC_done_T3_and_positive_release(record_property):
    process=subprocess.run([sys.executable,'-B','-E','-s','-c',PIPELINE_DRIVER,'04g_quiescent'],cwd=ROOT,
        capture_output=True,text=True,timeout=60)
    assert process.returncode==0,process.stdout+process.stderr
    result=json.loads(process.stdout)
    events=[json.loads(line) for line in process.stderr.splitlines() if line.startswith('{"event":"qio226_r4_owner_outcome"')]
    assert result['states']==['completed']*3 and result['source_hashes_unchanged']
    assert len(events)==len(result['proofs'])==3
    for event,proof in zip(events,result['proofs']):
        backup=event['backup']
        assert backup['status']==101 and backup['remaining']==0 and backup['total']>128
        assert backup['done']==1 and backup['busy']==backup['locked']==backup['other']==0
        assert backup['steps']==(backup['total']+127)//128 and backup['complete']
        assert event['owner_done_received'] and event['outcome']=='complete' and event['child_exit_code']==0
        assert proof['snapshot'] is not None and proof['helper_reaped'] and proof['gatekeeper_reaped']
        assert proof['cleanup_complete'] and proof['shmem_zero'] and proof['empty_observations']==2
        assert proof['memory_observations']['swap_current']==0
    record_property('04g_actual_owner_ABC_T3',json.dumps(dict(events=events,result=result),sort_keys=True))


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


@NATIVE
@pytest.mark.parametrize('scenario',['04h_large','04h_A_failure'])
def test_04H_actual_UID995_authenticated_T3_private_summary_and_positive_release(scenario,record_property):
    import hashlib
    import shutil
    import sysconfig
    import tempfile
    # UID995 cannot traverse the owner's HOME. Copy existing qualified TEST
    # dependencies and exact source into a disposable traversable root. No
    # package install, global chmod, HOME change or import stub is allowed.
    with tempfile.TemporaryDirectory(prefix='qio226-04h-readable-fixture-') as temporary:
        qualified=Path(temporary);qualified.chmod(0o755)
        release=qualified/'release';release.mkdir()
        shutil.copytree(ROOT/'app',release/'app',ignore=shutil.ignore_patterns('__pycache__'))
        (release/'tests').mkdir()
        shutil.copytree(ROOT/'tests/db_audit_coordinator',release/'tests/db_audit_coordinator',ignore=shutil.ignore_patterns('__pycache__'))
        interpreter=qualified/'bin/python';interpreter.parent.mkdir();shutil.copy2(Path(sys.executable).resolve(),interpreter)
        (qualified/'pyvenv.cfg').write_text('home = /usr/bin\ninclude-system-site-packages = false\nversion = 3.10\n')
        packages=qualified/'lib/python3.10/site-packages';packages.parent.mkdir(parents=True)
        shutil.copytree(sysconfig.get_path('purelib'),packages,ignore=shutil.ignore_patterns('__pycache__'))
        hashes={str(path.relative_to(release)):hashlib.sha256(path.read_bytes()).hexdigest() for path in (release/'app').rglob('*.py')}
        assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in hashes.items())
        process=subprocess.run(['unshare','--mount','--pid','--fork','--propagation','private','--mount-proc',
            str(interpreter),'-B','-E','-s','-c',PIPELINE_DRIVER,scenario],cwd=release,
            capture_output=True,text=True,timeout=1250)
    assert process.returncode==0,process.stdout+process.stderr
    result=json.loads(process.stdout)
    diagnostics=[json.loads(line) for line in process.stderr.splitlines() if line.startswith('{')
        and json.loads(line).get('event')=='qio226_r4_t3_outcome']
    record_property('04h_authenticated_raw',json.dumps(dict(result=result,diagnostics=diagnostics),sort_keys=True))
    assert len(diagnostics)==3 and result['uids']==[0,995,1003]
    assert result['source_hashes_unchanged'] and len(result['proofs'])==3
    assert all(p['helper_reaped'] and p['gatekeeper_reaped'] and p['cleanup_complete'] and p['shmem_zero']
        and p['empty_observations']==2 for p in result['proofs'])
    if scenario=='04h_large':
        assert result['states']==['completed']*3
        assert all(d['check']=='t3_complete' and d['digest_full_count']==3 for d in diagnostics)
        assert result['proofs'][2]['snapshot']['size']>=117*1024**2
        assert diagnostics[2]['guard_fast_count']>16000 and diagnostics[2]['progress_callbacks']>0
    else:
        assert result['states']==['failed','completed','completed']
        assert diagnostics[0]['category']=='domain' and diagnostics[0]['check']=='pt_traffic_daily_date'
        assert result['proofs'][0]['snapshot'] is not None  # Backup completed; NOT source-corruption proof.
    assert 'invalid-synthetic-date' not in json.dumps(diagnostics)
    record_property('04h_authenticated_pipeline',json.dumps(dict(result=result,diagnostics=diagnostics),sort_keys=True))


def test_04I_dense_fixture_has_only_canonical_rows_and_deterministic_image(tmp_path):
    from app.traffic_projection.repository import schema_sql
    from app.db_audit_coordinator.live_sqlite import validate_snapshot
    from tests.db_audit_coordinator.test_b2_live_policy import policy
    import hashlib
    digests=[]
    for number in range(2):
        target=tmp_path/f'synthetic-{number}.db'
        import sqlite3
        db=sqlite3.connect(target,isolation_level=None);db.row_factory=sqlite3.Row;db.executescript(schema_sql())
        result=dense_04I_projection_fixture(db,cycles=3)
        assert result['total_rows']==11
        assert db.execute('SELECT count(*) FROM traffic_projection_cycles').fetchone()[0]==3
        assert db.execute('SELECT count(*) FROM traffic_projection_ap_cycles').fetchone()[0]==6
        assert db.execute('PRAGMA foreign_key_check').fetchone() is None
        assert validate_snapshot(db,policy('traffic_projection'),lambda:None)['page_count']>0
        db.close();digests.append(hashlib.sha256(target.read_bytes()).hexdigest())
    assert digests[0]==digests[1]


def run_04I_readable_pipeline(source_root,scenario):
    """Existing qualified interpreter/dependencies, copied without installation.

    Benchmark runner may supply exact clean 04H app plus this SAME QA harness.
    Returns source blob inventory; does not pretend the QA copy is a Git tree.
    """
    import hashlib
    import shutil
    import sysconfig
    import tempfile
    with tempfile.TemporaryDirectory(prefix='qio226-04i-readable-fixture-') as temporary:
        qualified=Path(temporary);qualified.chmod(0o755)
        release=qualified/'release';release.mkdir()
        shutil.copytree(source_root/'app',release/'app',ignore=shutil.ignore_patterns('__pycache__'))
        (release/'tests').mkdir()
        shutil.copytree(ROOT/'tests/db_audit_coordinator',release/'tests/db_audit_coordinator',ignore=shutil.ignore_patterns('__pycache__'))
        interpreter=qualified/'bin/python';interpreter.parent.mkdir();shutil.copy2(Path(sys.executable).resolve(),interpreter)
        (qualified/'pyvenv.cfg').write_text('home = /usr/bin\ninclude-system-site-packages = false\nversion = 3.10\n')
        packages=qualified/'lib/python3.10/site-packages';packages.parent.mkdir(parents=True)
        shutil.copytree(sysconfig.get_path('purelib'),packages,ignore=shutil.ignore_patterns('__pycache__'))
        blobs={str(path.relative_to(release)):hashlib.sha256(path.read_bytes()).hexdigest() for path in (release/'app').rglob('*.py')}
        assert all(hashlib.sha256((source_root/name).read_bytes()).hexdigest()==digest for name,digest in blobs.items())
        process=subprocess.run(['unshare','--mount','--pid','--fork','--propagation','private','--mount-proc',
            str(interpreter),'-B','-E','-s','-c',pipeline_04I_driver(),scenario],cwd=release,
            capture_output=True,text=True,timeout=1250)
    return process,blobs


@NATIVE
def test_04I_private_cost_probe_preserves_UID995_guards_and_positive_release(record_property):
    process,blobs=run_04I_readable_pipeline(ROOT,'04i_small')
    assert process.returncode==0,process.stdout+process.stderr
    result=json.loads(process.stdout)
    observations=[json.loads(line) for line in process.stderr.splitlines() if line.startswith('{')
        and json.loads(line).get('event')=='qio226_04i_private_cost']
    finals=[row for row in observations if row['kind']=='final']
    assert len(finals)==3 and result['states']==['completed']*3 and result['source_hashes_unchanged']
    for record,proof in zip(finals,result['proofs']):
        assert record['uid']==995 and record['gid']==993 and record['groups']==[]
        assert record['counts']['guard']==record['trace']['guard_fast_count']>0
        assert record['scans']['integrity_check']['count']==record['scans']['foreign_key_check']['count']==1
        assert record['scans']['quick_check']['count']==0
        assert record['trace']['digest_full_count']==3 and record['trace']['digest_bytes_verified']==3*record['image_bytes']
        assert proof['helper_reaped'] and proof['gatekeeper_reaped'] and proof['cleanup_complete'] and proof['shmem_zero']
        assert proof['empty_observations']==2 and proof['memory_observations']['swap_current']==0
    assert finals[2]['canonical_deep']==[False]
    assert len(observations)<=21 and len(blobs)>0
    record_property('04i_private_cost_smoke',json.dumps(dict(result=result,observations=observations),sort_keys=True))


class Guard04JProbe:
    """Aggregate actual kernel opens/reads; never substitute kernel data.

    QA only, one worker thread. No per-row log or production instrumentation.
    read_at/open/read wrappers always execute the original functions. Root
    optional controls may be absent: attempted fields != successful opens.
    """
    def __enter__(self):
        from app.db_audit_coordinator import live_cgroup as lc
        self.lc=lc;self.active=False;self.sampling=False;self.reading=None;self.opened=None
        self.locations={};self.directories={};self.last_nodes=None
        self.stats=dict(guards=0,passed=0,samples=0,read_at=0,opens=0,reads=0,bytes=0,
            min_samples=None,max_samples=0,errors={},ancestors={})
        self.original=(lc.Leaf.samples,lc.directory,lc.read_at,os.open,os.read)
        samples,directory,read_at,opened,read=self.original
        def sample(leaf):
            if not self.active:return samples(leaf)
            self.stats['samples']+=1;self.sampling=True
            components=leaf.relative.strip('/').split('/')
            names=['/']+['/'+'/'.join(components[:n]) for n in range(1,len(components)+1)]
            self.locations={leaf.mount+('' if name=='/' else name):str(n) for n,name in enumerate(names)}
            self.directories={}
            try:
                nodes=samples(leaf)
                assert nodes is not self.last_nodes and len(nodes)==len(names)
                self.last_nodes=nodes
                return nodes
            finally:self.sampling=False
        def directory_call(value,*args,**kwargs):
            fd=directory(value,*args,**kwargs)
            if self.active and self.sampling:
                name=os.fspath(value)
                assert name in self.locations
                self.directories[fd]=self.locations[name]
            return fd
        def read_call(fd,name,*args,**kwargs):
            if not (self.active and self.sampling):return read_at(fd,name,*args,**kwargs)
            depth=self.directories[fd]
            bucket=self.stats['ancestors'].setdefault(depth,{})
            field=bucket.setdefault(name,dict(read_at=0,opens=0,reads=0,bytes=0))
            self.stats['read_at']+=1;field['read_at']+=1;self.reading=(fd,field)
            try:return read_at(fd,name,*args,**kwargs)
            finally:self.reading=None;self.opened=None
        def open_call(*args,**kwargs):
            fd=opened(*args,**kwargs)
            if self.reading is not None and kwargs.get('dir_fd')==self.reading[0]:
                self.opened=fd;self.stats['opens']+=1;self.reading[1]['opens']+=1
            return fd
        def kernel_read(fd,count):
            value=read(fd,count)
            if self.reading is not None and fd==self.opened:
                self.stats['reads']+=1;self.stats['bytes']+=len(value)
                self.reading[1]['reads']+=1;self.reading[1]['bytes']+=len(value)
            return value
        lc.Leaf.samples=sample;lc.directory=directory_call;lc.read_at=read_call
        os.open=open_call;os.read=kernel_read
        return self

    def guard(self,original):
        def observed(*args,**kwargs):
            assert not self.active
            self.active=True;before=self.stats['samples'];self.stats['guards']+=1
            try:
                result=original(*args,**kwargs)
                count=self.stats['samples']-before
                assert count==1
                self.stats['passed']+=1
                self.stats['min_samples']=count if self.stats['min_samples'] is None else min(self.stats['min_samples'],count)
                self.stats['max_samples']=max(self.stats['max_samples'],count)
                return result
            except BaseException as error:
                code=getattr(error,'code',type(error).__name__)
                self.stats['errors'][code]=self.stats['errors'].get(code,0)+1
                raise
            finally:self.active=False
        return observed

    def __exit__(self,*args):
        self.lc.Leaf.samples,self.lc.directory,self.lc.read_at,os.open,os.read=self.original


def install_04J_sample_probe():
    from app.db_audit_coordinator import r4_snapshot
    original=r4_snapshot.validate
    def measured(fd,parent,receipt,folder_receipt,policy,guard,**kwargs):
        with Guard04JProbe() as probe:
            try:return original(fd,parent,receipt,folder_receipt,policy,probe.guard(guard),**kwargs)
            finally:
                print(json.dumps(dict(event='qio226_04j_kernel_samples',store=policy.store_id,
                    uid=os.geteuid(),gid=os.getegid(),stats=probe.stats),sort_keys=True),file=sys.stderr,flush=True)
    r4_snapshot.validate=measured


def pipeline_04J_driver():
    code=pipeline_04I_driver();old="large=sys.argv[1]=='04i_dense'"
    assert code.count(old)==1
    return code.replace(old,"large=sys.argv[1]=='04j_dense'",1)


def run_04J_readable_pipeline(source_root,scenario):
    # Reuse every 04I copy/interpreter/UID/FD/fixture/release instruction. Only
    # select this test-only driver; original 04I function remains unchanged.
    import inspect
    source=inspect.getsource(run_04I_readable_pipeline)
    assert source.count('pipeline_04I_driver()')==1
    source=source.replace('def run_04I_readable_pipeline(', 'def qualified_04J_pipeline(',1)
    source=source.replace('pipeline_04I_driver()', 'pipeline_04J_driver()',1)
    namespace=dict(globals());exec(compile(source,__file__,'exec'),namespace)
    return namespace['qualified_04J_pipeline'](source_root,scenario)


@NATIVE
def test_04J_actual_UID995_ABC_full_T3_one_kernel_hierarchy_per_guard(record_property):
    process,blobs=run_04J_readable_pipeline(ROOT,'04j_small')
    assert process.returncode==0,process.stdout+process.stderr
    result=json.loads(process.stdout);records=[json.loads(line) for line in process.stderr.splitlines() if line.startswith('{')]
    samples=[r for r in records if r.get('event')=='qio226_04j_kernel_samples']
    finals=[r for r in records if r.get('event')=='qio226_04i_private_cost' and r['kind']=='final']
    assert len(samples)==len(finals)==len(result['proofs'])==3
    assert result['states']==['completed']*3 and result['source_hashes_unchanged']
    for measured,timing,proof in zip(samples,finals,result['proofs']):
        stats=measured['stats'];count=stats['guards']
        assert measured['uid']==995 and measured['gid']==993 and timing['groups']==[]
        assert count==stats['passed']==stats['samples']==timing['counts']['guard']==timing['trace']['guard_fast_count']>0
        assert stats['min_samples']==stats['max_samples']==1 and stats['errors']=={}
        assert set(stats['ancestors'])=={'0','1','2','3'}
        for fields in stats['ancestors'].values():
            assert set(fields)=={'memory.max','memory.current','memory.swap.max','memory.swap.current','memory.events',
                'memory.pressure','cgroup.events','cgroup.procs','cgroup.controllers','cgroup.subtree_control'}
            assert all(f['read_at']==count for f in fields.values())
        assert stats['opens']>0 and stats['reads']>=stats['opens'] and stats['bytes']>0
        assert timing['trace']['digest_full_count']==3 and timing['trace']['digest_bytes_verified']==3*timing['image_bytes']
        assert timing['scans']['integrity_check']['count']==timing['scans']['foreign_key_check']['count']==1
        assert timing['scans']['quick_check']['count']==0
        assert all(proof[k] for k in ('helper_reaped','gatekeeper_reaped','cleanup_complete','shmem_zero'))
        assert proof['empty_observations']==2 and proof['memory_observations']['swap_current']==0
    assert finals[2]['canonical_deep']==[False] and blobs
    record_property('04j_native_kernel_ABC',json.dumps(dict(result=result,samples=samples,finals=finals),sort_keys=True))


GUARD_04J_DRIVER=r'''
import json,os,select,shutil,signal,subprocess,tempfile,time,uuid
from pathlib import Path
from types import SimpleNamespace
from app.db_audit_coordinator import child_bootstrap as worker,contracts as c
from app.db_audit_coordinator.live_cgroup import Leaf
from app.db_audit_coordinator.live_policy import Deadlines,require
from app.db_audit_coordinator.live_receipts import guest_sample,membership
from tests.db_audit_coordinator.test_qio226_r4_crash import compile_04J_guard
from tests.db_audit_coordinator.test_qio226_r4_native import Guard04JProbe
assert os.geteuid()==0 and os.getpid()==1
fault=__import__('sys').argv[1];top=Path('/sys/fs/cgroup')/('qio226-04j-guard-'+uuid.uuid4().hex)
root=Path(tempfile.mkdtemp(prefix='qio226-04j-guard-'));root.chmod(0o755)
pid=None;mounts=[];fds=[]
def write(folder,key,value):(folder/key).write_text(str(value))
def bound_file(target,value):
 path=root/('counter-'+str(len(mounts)));path.write_text(value);path.chmod(0o444)
 subprocess.run(['mount','--bind',str(path),str(target)],check=True,capture_output=True);mounts.append(target)
try:
 top.mkdir();write(top,'memory.max',256*1024**2);write(top,'memory.swap.max',0);write(top,'cgroup.subtree_control','+memory +pids')
 parent=top/'delegated';parent.mkdir();write(parent,'memory.max',192*1024**2);write(parent,'memory.swap.max',0)
 write(parent,'cgroup.subtree_control','+memory +pids')
 leaf=parent/'worker';other=parent/'other'
 for location in (leaf,other):
  location.mkdir(mode=0o750);os.chown(location,0,993)
  write(location,'memory.max',128*1024**2);write(location,'memory.swap.max',0);write(location,'pids.max',8)
 lock=root/'heavy.lock';lock.touch(mode=0o640);os.chown(lock,0,993)
 expected=(lock.stat().st_dev,lock.stat().st_ino);leaf_id=(leaf.stat().st_dev,leaf.stat().st_ino)
 commands_r,commands_w=os.pipe();results_r,results_w=os.pipe();cancel_r,cancel_w=os.pipe()
 fds=[commands_r,commands_w,results_r,results_w,cancel_r,cancel_w]
 pid=os.fork()
 if pid==0:
  try:
   os.close(commands_w);os.close(results_r);os.close(cancel_w)
   assert os.read(commands_r,1)==b'G'
   # Compile exact source while root can traverse the checkout; execute only
   # after the real UID/GID drop. Never chmod HOME/source to aid the fixture.
   namespace={};guard=compile_04J_guard(namespace)
   os.setgroups([]);os.setgid(993);os.setuid(995)
   actual=Leaf('/sys/fs/cgroup',str(leaf).removeprefix('/sys/fs/cgroup'),leaf_id)
   gate=worker.Gate(str(lock),*expected).acquire()
   namespace.update(deadline=Deadlines(time.monotonic_ns(),10),gate=gate,leaf=actual,
    data={'cancel_fd':cancel_r},policy=SimpleNamespace(memory_max_bytes=128*1024**2),
    os=os,select=select,c=c,require=require,membership=membership,guest_sample=guest_sample)
   with Guard04JProbe() as probe:
    observed=probe.guard(guard)
    def report():
     try:observed();outcome='passed'
     except c.CoordinatorError as error:outcome=error.code
     raw=json.dumps(dict(outcome=outcome,uid=os.geteuid(),gid=os.getegid(),groups=os.getgroups(),stats=probe.stats))+'\n'
     assert os.write(results_w,raw.encode())==len(raw.encode())
    report();assert os.read(commands_r,1)==b'G'
    if fault=='deadline':namespace['deadline']=Deadlines(0,1)
    if fault=='real_oom':payload=bytearray(128*1024**2);raise AssertionError('kernel did not enforce own leaf memory.max')
    report()
   actual.close();os.close(gate.fd);os._exit(0)
  except BaseException:
   __import__('traceback').print_exc();os._exit(3)
 os.close(commands_r);fds.remove(commands_r);os.close(results_w);fds.remove(results_w)
 stream=os.fdopen(results_r,'r');fds.remove(results_r)
 write(leaf,'cgroup.procs',pid);os.write(commands_w,b'G')
 first=json.loads(stream.readline());assert first['outcome']=='passed' and first['stats']['samples']==1
 if fault=='cancel':os.write(cancel_w,b'x')
 elif fault=='gate':
  changed=root/'replacement';changed.touch(mode=0o640);os.chown(changed,0,993);os.replace(changed,lock)
 elif fault=='membership':write(other,'cgroup.procs',pid)
 elif fault=='mount':
  subprocess.run(['mount','--bind',str(other),str(leaf)],check=True,capture_output=True);mounts.append(leaf)
 elif fault=='memory_max':write(leaf,'memory.max',129*1024**2)
 elif fault=='swap_max':write(leaf,'memory.swap.max',4096)
 elif fault=='swap_current':bound_file(leaf/'memory.swap.current','1\n')
 elif fault=='ancestor_memory':bound_file(parent/'memory.current',str(256*1024**2)+'\n')
 elif fault=='ancestor_swap':bound_file(parent/'memory.swap.current','1\n')
 elif fault=='ancestor_subtree':bound_file(parent/'cgroup.subtree_control','pids\n')
 elif fault=='ancestor_pressure':bound_file(parent/'memory.pressure','some avg10=0.01 avg60=0.00 avg300=0.00 total=1\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=0\n')
 elif fault=='leaf_oom_counter':bound_file(leaf/'memory.events',(leaf/'memory.events').read_text().replace('oom 0','oom 1'))
 elif fault=='real_oom':write(leaf,'memory.max',32*1024**2)
 os.write(commands_w,b'G');line=stream.readline()
 _,status=os.waitpid(pid,0);pid=None
 if fault=='real_oom':
  assert not line and os.waitstatus_to_exitcode(status)==-signal.SIGKILL
  events=dict(row.split() for row in (leaf/'memory.events').read_text().splitlines())
  assert int(events['oom_kill'])>=1
  final=dict(outcome='kernel_resource_killed',oom_kill=int(events['oom_kill']),positive_R4_release=False)
 else:
  assert os.waitstatus_to_exitcode(status)==0
  final=json.loads(line)
  expected='coordinator_unavailable' if fault=='cancel' else 'unsafe_path' if fault in {'gate','mount'} else 'unauthorized' if fault=='membership' else 'passed' if fault in {'none','deadline'} else 'not_admitted'
  assert final['outcome']==expected and final['outcome']!='audit_failed'
  stats=final['stats'];assert stats['guards']==2
  assert stats['samples']==(1 if fault in {'cancel','gate','membership','mount'} else 2)
 stream.close()
 print(json.dumps(dict(fault=fault,first=first,final=final,kernel=os.uname().release,
  bound_counter_fault=(fault in {'swap_current','ancestor_memory','ancestor_swap','ancestor_subtree','ancestor_pressure','leaf_oom_counter'}),
  scope='NATIVE_EXACT_GUARD_BODY_NOT_R4_RELEASE_OR_ORIGINALS')))
finally:
 if pid is not None:
  try:os.kill(pid,signal.SIGKILL)
  except ProcessLookupError:pass
  os.waitpid(pid,0)
 for target in reversed(mounts):subprocess.run(['umount',str(target)],check=True,capture_output=True)
 for fd in fds:os.close(fd)
 if top.exists():
  assert top.parent==Path('/sys/fs/cgroup') and top.name.startswith('qio226-04j-guard-')
  for folder in sorted(top.rglob('*'),key=lambda p:len(p.parts),reverse=True):
   if folder.is_dir():folder.rmdir()
  top.rmdir()
 assert root.parent==Path('/tmp') and root.name.startswith('qio226-04j-guard-')
 shutil.rmtree(root)
'''


@NATIVE
@pytest.mark.parametrize('fault',['none','cancel','deadline','gate','membership','mount','memory_max','swap_max',
    'swap_current','ancestor_memory','ancestor_swap','ancestor_subtree','ancestor_pressure','leaf_oom_counter','real_oom'])
def test_04J_native_fresh_guard_kernel_controls_and_exact_resource_failure(fault,record_property):
    process=subprocess.run(['unshare','--mount','--pid','--fork','--propagation','private','--mount-proc',
        sys.executable,'-B','-E','-s','-c',GUARD_04J_DRIVER,fault],cwd=ROOT,capture_output=True,text=True,timeout=20)
    assert process.returncode==0,process.stdout+process.stderr
    result=json.loads(process.stdout);first=result['first']
    assert first['uid']==995 and first['gid']==993 and first['groups']==[]
    assert first['stats']['samples']==first['stats']['guards']==first['stats']['passed']==1
    assert set(first['stats']['ancestors'])=={'0','1','2','3'}
    assert first['stats']['opens']>0 and first['stats']['reads']>=first['stats']['opens']
    if fault=='none':
        assert result['final']['stats']['samples']==result['final']['stats']['passed']==2
        assert result['final']['stats']['min_samples']==result['final']['stats']['max_samples']==1
    record_property('04j_native_guard',json.dumps(result,sort_keys=True))


def install_04K_worker_clock():
    """QA-only clock advance; authentic worker/FDs/guards/T3 remain untouched."""
    import time
    from app.db_audit_coordinator import r4_ipc,r4_snapshot
    original_ns=time.monotonic_ns;age=1201
    time.monotonic_ns=lambda:original_ns()+age*10**9
    receive=r4_ipc.receive;validate=r4_snapshot.validate
    def received(*args,**kwargs):
        assert kwargs['seconds'] is None
        result=receive(*args,**kwargs)
        print(json.dumps(dict(event='04k_worker_wait',age=age,kind=result[0],deadline=None)),file=sys.stderr,flush=True)
        return result
    def validating(*args,**kwargs):
        nonlocal age
        age=5401
        result=validate(*args,**kwargs)
        print(json.dumps(dict(event='04k_worker_T3',age=age,passed=True)),file=sys.stderr,flush=True)
        return result
    r4_ipc.receive=received;r4_snapshot.validate=validating


def install_04K_owner_clock(helper):
    """Advance the actual helper clock before ready/begin and Backup callbacks."""
    import time
    original_ns=time.monotonic_ns;age=1201;calls=0
    time.monotonic_ns=lambda:original_ns()+age*10**9
    read=helper.readonly_document;mark=helper.OwnerTrace.mark
    callback=helper.BackupProgress.__call__;finish=helper.BackupProgress.finish
    def document(*args,**kwargs):
        result=read(*args,**kwargs)
        assert result['deadline_ns'] is None
        return result
    def marked(self,name):
        nonlocal age
        if name=='backup_start':age=5401
        mark(self,name)
    def progress(self,*args):
        nonlocal calls
        assert age==5401
        calls+=1
        return callback(self,*args)
    def finished(self):
        finish(self)
        assert calls>0
        print(json.dumps(dict(event='04k_owner_backup',age=age,callbacks=calls,
            complete=self.complete,deadline=None)),file=sys.stderr,flush=True)
    helper.readonly_document=document;helper.OwnerTrace.mark=marked
    helper.BackupProgress.__call__=progress;helper.BackupProgress.finish=finished


def pipeline_04K_driver():
    code=pipeline_04I_driver()
    replacements=[
        ("original=open('/proc/self/cgroup')", "real_ns=time.monotonic_ns;clock_age=0\ntime.monotonic_ns=lambda:real_ns()+clock_age*10**9\noriginal=open('/proc/self/cgroup')"),
        ("   assert subject.dispatch_one()", "   clock_age=0\n   assert subject.dispatch_one()\n   clock_age=5401\n   assert (time.monotonic_ns()-subject._r4.started)//10**9>=5401\n   assert subject._r4.deadline is None and subject.timeout() is None\n   subject.expire();assert not subject.orphan_hold\n   print(json.dumps(dict(event='04k_root_age',age=clock_age,deadline=None,held=False)),file=sys.stderr,flush=True)"),
        ("    subject.finish()", "    assert subject.timeout() is None\n    subject.expire();subject.finish()"),
    ]
    for old,new in replacements:
        assert code.count(old)==1,old
        code=code.replace(old,new,1)
    return code


def run_04K_readable_pipeline(source_root,scenario):
    import inspect
    source=inspect.getsource(run_04I_readable_pipeline)
    assert source.count('pipeline_04I_driver()')==1
    source=source.replace('def run_04I_readable_pipeline(', 'def qualified_04K_pipeline(',1)
    source=source.replace('pipeline_04I_driver()', 'pipeline_04K_driver()',1)
    namespace=dict(globals());exec(source,namespace)
    return namespace['qualified_04K_pipeline'](source_root,scenario)


@NATIVE
def test_04K_aged_root_owner_worker_Backup_T3_IPC_naturally_complete_with_real_release(record_property):
    process,blobs=run_04K_readable_pipeline(ROOT,'04k_age')
    assert process.returncode==0,process.stdout+process.stderr
    result=json.loads(process.stdout)
    assert result['states']==['completed']*3 and result['source_hashes_unchanged']
    assert result['uids']==[0,995,1003]
    assert len(result['proofs'])==3 and len(blobs)>0
    for proof in result['proofs']:
        assert proof['helper_reaped'] and proof['gatekeeper_reaped'] and proof['cleanup_complete']
        assert proof['shmem_zero'] and proof['empty_observations']==2
        assert proof['source_pre_sha256']==proof['source_post_sha256']
        assert proof['memory_observations']['swap_current']==0
        assert proof['snapshot']['size']>0 and len(proof['snapshot']['sha256'])==64
    events=[json.loads(line) for line in process.stderr.splitlines() if line.startswith('{')]
    backup=[e for e in events if e.get('event')=='04k_owner_backup']
    t3=[e for e in events if e.get('event')=='04k_worker_T3']
    waits=[e for e in events if e.get('event')=='04k_worker_wait']
    roots=[e for e in events if e.get('event')=='04k_root_age']
    assert len(backup)==len(t3)==len(roots)==3 and len(waits)==6
    assert all(e['age']==5401 and e['deadline'] is None and not e['held'] for e in roots)
    assert all(e['age']==5401 and e['complete'] and e['callbacks']>0 and e['deadline'] is None for e in backup)
    assert all(e['age']==5401 and e['passed'] for e in t3)
    assert [e['age'] for e in waits]==[1201,5401]*3
    assert [e['kind'] for e in waits]==['snapshot','release']*3
    assert all(e['deadline'] is None for e in waits)
    record_property('04k_age_native',json.dumps(dict(result=result,backup=backup,t3=t3,waits=waits,roots=roots),sort_keys=True))
