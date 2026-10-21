"""R4 exact-child, gate and release facts; never a second queue writer."""
from __future__ import annotations

import os
from pathlib import Path
import select
import stat
import time

from .live_policy import require,integer
from .live_receipts import identity,start_ticks,membership,read_at

GATES=frozenset({'claim_publish','worker_bootstrap','worker_reap','gate_owner','resource_leaf',
    'owner_helper','snapshot_promotion','snapshot_dirfd','t3','release_cleanup','channel_closed','shutdown','deadline'})
SUBPHASES=frozenset({'claim','leaf_create','leaf_enter','namespace','tmpfs','spawn','identity','running_publish',
    'auth_release','wait','source_inspect','source_open','source_view','ready','reap','promote','pin_final',
    'send','source_recheck','close_fds','unlink','unmount','ack','namespace_restore','leaf_exit','empty','terminal'})
PHASES=frozenset({'claim','gate','owner','validating','release'})
EXCEPTIONS=frozenset({'CoordinatorError','EvidenceError','PermissionError','FileNotFoundError','FileExistsError',
    'BrokenPipeError','TimeoutError','OSError','ValueError','TypeError','RuntimeError','AuditFailure','InterruptedError'})

OWNER_STAGES=('auth_document','profile_parse','profile_parsed','parent_verify','parent_verified',
    'namespace_view','namespace_verified','artifact','artifact_verified','imports','imports_verified',
    'receipt_open','chroot','chroot_entered','credential_drop','credentials_dropped','credential_receipts',
    'credentials_verified','owner_ready','owner_ready_sent','begin_wait','begin_received','source_guard',
    'source_open','source_opened','source_metadata','source_metadata_verified','destination_open',
    'destination_opened','backup_start','backup_progress','backup_complete','connections_close',
    'owner_done','owner_done_sent','cleanup','finished')
OWNER_DIAGNOSTIC_LIMIT=4096
OWNER_EXCEPTIONS=EXCEPTIONS|{'OperationalError','DatabaseError','TimeoutExpired','CalledProcessError','MemoryError'}
OWNER_BACKUP_CHECKS=frozenset({'backup_call','callback_guard','callback_step_budget','callback_types',
    'callback_status','callback_counts','callback_page_budget','busy_wait','callback_valid',
    'completion','post_backup_guard','finished'})
OWNER_BACKUP_FIELDS={'check','status','remaining','total','steps','page_size','complete',
    'ok','done','busy','locked','other'}
OWNER_ROW_LIMIT=768


def validate_owner_backup(value):
    """Closed numeric diagnostic, not an admission/release proof."""
    from . import contracts as c
    c.closed(value,OWNER_BACKUP_FIELDS)
    require(value['check'] in OWNER_BACKUP_CHECKS and type(value['complete']) is bool,'unauthorized')
    integer(value['steps'],0,100001);integer(value['page_size'],512,65536)
    for name in ('status','remaining','total'):
        if value[name] is not None:integer(value[name],0 if name=='status' else -1,2**31-1)
    for name in ('ok','done','busy','locked','other'):integer(value[name],0,100001)
    require(sum(value[name] for name in ('ok','done','busy','locked','other'))==value['steps'],'unauthorized')
    require(not value['complete'] or value['status']==101 and value['remaining']==0
        and type(value['total']) is int and value['total']>0,'unauthorized')
    return value


class BackupProgress:
    """Pure owner-side callback policy, shared with its closed diagnostic sink.

    SQLITE_BUSY/LOCKED can report 0/0 before any pages are copied. They are NOT
    completion. CPython owns the retry loop; the existing deadline, cancellation,
    source guard and 100000 callback cap still own this attempt. No per-call log.
    No Linux bootstrap imports are needed to test this pure policy on Windows.
    """
    def __init__(self,trace,guard,wait,page_size,image_max_bytes):
        self.trace,self.guard,self.wait=trace,guard,wait
        self.size,self.maximum=page_size,image_max_bytes
        self.complete=False
        trace.backup=dict(check='backup_call',status=None,remaining=None,total=None,steps=0,
            page_size=page_size,complete=False,ok=0,done=0,busy=0,locked=0,other=0)
    def __call__(self,code,remaining,total):
        value=self.trace.backup
        if value['steps']==0:self.trace.mark('backup_progress')
        value['steps']+=1
        category={0:'ok',101:'done',5:'busy',6:'locked'}.get(code,'other') if type(code) is int else 'other'
        value[category]+=1
        value['status']=code if type(code) is int and 0<=code<=2**31-1 else None
        for key,number in (('remaining',remaining),('total',total)):
            value[key]=number if type(number) is int and -1<=number<=2**31-1 else None
        self.complete=value['complete']=False
        value['check']='callback_guard';self.guard()
        value['check']='callback_step_budget';require(value['steps']<=100000,'not_admitted')
        value['check']='callback_types'
        require(all(type(number) is int for number in (code,remaining,total)),'not_admitted')
        value['check']='callback_status';require(code in {0,101,5,6},'not_admitted')
        value['check']='callback_counts';require(0<=remaining<=total<=2**31-1,'not_admitted')
        value['check']='callback_page_budget'
        require(total*self.size<=self.maximum and (code in {5,6} or total>0),'not_admitted')
        if code==101:
            value['check']='callback_counts';require(remaining==0,'not_admitted')
            self.complete=value['complete']=True
        if code in {5,6}:
            value['check']='busy_wait';self.wait()
        value['check']='callback_valid'
    def finish(self):
        self.trace.backup['check']='completion';require(self.complete,'not_admitted')
        self.trace.backup['check']='post_backup_guard';self.guard()
        self.trace.backup['check']='finished';self.trace.backup_result()


class OwnerTrace:
    """Private inherited nonblocking FIFO; bounded enums, no arbitrary stderr.

    One marker per boundary, first progress only, at most one failure record.
    Diagnostic write refusal never changes the helper's original outcome.
    """
    def __init__(self,fd):
        import fcntl
        integer(fd,3,2**20)
        flags=fcntl.fcntl(fd,fcntl.F_GETFL)
        require(stat.S_ISFIFO(os.fstat(fd).st_mode) and flags&os.O_ACCMODE==os.O_WRONLY
            and flags&os.O_NONBLOCK,'unauthorized')
        os.set_inheritable(fd,False)
        self.fd=fd;self.stage=None;self.failed=False;self.stop_reason=None;self.backup=None;self.backup_reported=False
    def write(self,value):
        from . import contracts as c
        try:os.write(self.fd,c.encode(value,OWNER_ROW_LIMIT)+b'\n')
        except OSError:pass
    def mark(self,stage):
        require(stage in OWNER_STAGES,'invalid_request')
        if not self.failed and stage!=self.stage:
            require(self.stage is None or OWNER_STAGES.index(stage)>OWNER_STAGES.index(self.stage),'invalid_request')
            self.stage=stage;self.write(dict(stage=stage))
    def backup_result(self):
        require(self.stage=='backup_progress' and not self.failed and not self.backup_reported,'invalid_request')
        self.write(dict(stage=self.stage,backup=validate_owner_backup(self.backup)))
        self.backup_reported=True
    def failure(self,error):
        from . import contracts as c
        if self.failed:return
        self.failed=True
        code=getattr(error,'code',None) if isinstance(error,c.CoordinatorError) else None
        number=getattr(error,'errno',None) if isinstance(error,OSError) else None
        value=dict(stage=self.stage,exception_class=type(error).__name__ if type(error).__name__ in OWNER_EXCEPTIONS else 'unknown',
            coordinator_code=code if type(code) is str and code in c.ERRORS else None,
            os_errno=number if type(number) is int and 0<number<=4095 else None,stop_reason=self.stop_reason)
        if self.backup is not None and not self.backup_reported:value['backup']=validate_owner_backup(self.backup)
        self.write(value)
    def close(self):os.close(self.fd)


def owner_trace(raw):
    """Root parses only the closed diagnostic surface, never adopts it as proof."""
    from . import contracts as c
    try:
        require(type(raw) is bytes and 0<len(raw)<=OWNER_DIAGNOSTIC_LIMIT and raw.endswith(b'\n'),'unauthorized')
        rows=raw.splitlines();require(len(rows)<=len(OWNER_STAGES)+2,'unauthorized')
        last=-1;failure=None;backup=None
        for line in rows:
            value=c.decode(line,OWNER_ROW_LIMIT);require(type(value) is dict and value.get('stage') in OWNER_STAGES,'unauthorized')
            index=OWNER_STAGES.index(value['stage'])
            if set(value)=={'stage'}:
                require(failure is None and index>last,'unauthorized');last=index
            elif set(value)=={'stage','backup'}:
                require(failure is None and backup is None and index==last
                    and value['stage']=='backup_progress','unauthorized')
                backup=validate_owner_backup(value['backup'])
            else:
                if 'backup' in value:
                    require(backup is None and index>=OWNER_STAGES.index('backup_start'),'unauthorized')
                    backup=validate_owner_backup(value['backup'])
                c.closed(value,{'stage','exception_class','coordinator_code','os_errno','stop_reason'}
                    |({'backup'} if 'backup' in value else set()))
                require(failure is None and index==last
                    and value['exception_class'] in OWNER_EXCEPTIONS|{'unknown'}
                    and (value['coordinator_code'] is None or type(value['coordinator_code']) is str and value['coordinator_code'] in c.ERRORS)
                    and (value['os_errno'] is None or type(value['os_errno']) is int and 0<value['os_errno']<=4095)
                    and value['stop_reason'] in {None,'canceled','deadline'},'unauthorized')
                failure=value
        result=dict(report_status='failure' if failure else 'stage_only',stage=OWNER_STAGES[last],
            exception_class=None if failure is None else failure['exception_class'],
            coordinator_code=None if failure is None else failure['coordinator_code'],
            os_errno=None if failure is None else failure['os_errno'],
            stop_reason=None if failure is None else failure['stop_reason'])
        if backup is not None:result['backup']=backup
        return result
    except Exception:
        return dict(report_status='unavailable' if raw==b'' else 'invalid',stage='unreported',
            exception_class=None,coordinator_code=None,os_errno=None,stop_reason=None)


def hold_diagnostic(session,error=None,child_name=None):
    """Closed data only; never str(error), traceback, source, paths or nonce."""
    from . import contracts as c
    def uuid(value):
        try:return c.identifier(value)
        except c.CoordinatorError:return None
    code=getattr(error,'code',None) if isinstance(error,c.CoordinatorError) else None
    number=getattr(error,'errno',None) if isinstance(error,OSError) else None
    child=getattr(session,'children',{}).get(child_name);exit_code=None
    if child is not None and child.waited:
        try:exit_code=child.reaped()
        except Exception:exit_code=None
    if type(exit_code) is not int or not -255<=exit_code<=255:exit_code=None
    job=session.job;seq=job.get('seq')
    return dict(event='qio226_r4_first_hold',version=1,job_id=uuid(job.get('job_id')),
        attempt_id=uuid(job.get('attempt_id')),seq=seq if type(seq) is int and 0<seq<=c.MAX_INTEGER else None,
        phase=session.phase if getattr(session,'phase',None) in PHASES else 'claim',
        gate_id=session.gate_id if getattr(session,'gate_id',None) in GATES else 'resource_leaf',
        subphase=session.subphase if getattr(session,'subphase',None) in SUBPHASES else 'wait',
        exception_class=type(error).__name__ if type(error).__name__ in EXCEPTIONS else 'unknown' if error else None,
        coordinator_code=code if type(code) is str and code in c.ERRORS else None,
        os_errno=number if type(number) is int and 0<number<=4095 else None,
        child_role=child_name if child_name in {'worker','owner'} else None,child_exit_code=exit_code,
        source_gate_verified=getattr(session,'source_gate_verified',False) is True,
        source_open_started=getattr(session,'source_open_started',False) is True)


def emit_hold(value):
    """Trusted root daemon stderr is routed to protected journal by launcher."""
    import sys
    from . import contracts as c
    if os.geteuid()==0:print(c.encode(value,2048).decode('ascii'),file=sys.stderr,flush=True)


class Child:
    """Capture pidfd/start while blocked child is alive; one parent wait only."""
    def __init__(self,process):
        import threading
        require(process.returncode is None,'orphan_hold')
        self.process=process;self.supervisor=os.getpid();self.pidfd=os.pidfd_open(process.pid,0)
        try:self.start=start_ticks(process.pid)
        except Exception:os.close(self.pidfd);raise
        self.waited=False;self.exited=threading.Event()
    @property
    def pid(self):return self.process.pid
    def wait(self):
        # Called once by the dedicated reaper, never inferred from /proc absence.
        self.process.wait();self.waited=True;self.exited.set()
    def reaped(self):
        require(os.getpid()==self.supervisor and self.waited and self.process.returncode is not None,'orphan_hold')
        poller=select.poll();poller.register(self.pidfd,select.POLLIN)
        require(bool(poller.poll(0)),'orphan_hold')
        return self.process.returncode
    def close(self):
        require(self.waited,'orphan_hold')
        if self.pidfd is not None:os.close(self.pidfd);self.pidfd=None


def gate_owner(child,gate_path,expected,fd_number,leaf,cap,namespace):
    """Current kernel lock ownership, not the child's unverified ready string."""
    integer(fd_number,3,2**20)
    require(not child.waited and start_ticks(child.pid)==child.start
        and membership(child.pid)==leaf.relative,'unauthorized')
    require(identity(os.stat('/proc/'+str(child.pid)+'/ns/mnt'))==tuple(namespace),'unauthorized')
    gate=Path(gate_path);info=gate.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid==0 and info.st_nlink==1
        and not info.st_mode&0o022 and identity(info)==tuple(expected),'unsafe_path')
    actual=os.stat('/proc/'+str(child.pid)+'/fd/'+str(fd_number))
    require(identity(actual)==tuple(expected),'unauthorized')
    wanted=f'{os.major(info.st_dev):02x}:{os.minor(info.st_dev):02x}:{info.st_ino}'
    found=[]
    with open('/proc/locks',encoding='ascii') as stream:
        for line in stream:
            fields=line.split()
            if len(fields)==8 and fields[1:4]==['FLOCK','ADVISORY','WRITE'] and fields[5]==wanted:
                found.append(int(fields[4]))
    require(found==[child.pid],'unauthorized')
    sample=leaf.samples()[-1]
    require(sample.maximum==cap and sample.swap_max==sample.swap_current==0
        and set(sample.procs)=={os.getpid(),child.pid},'not_admitted')


class Residence:
    """Root joins the SAME leaf before allocation; leaves only after cleanup."""
    def __init__(self,leaf):
        self.leaf=leaf;self.pid=os.getpid();self.old=membership(self.pid);self.fd=None
    def enter(self):
        require(self.fd is None and self.old!=self.leaf.relative,'not_admitted')
        target='/sys/fs/cgroup'+('' if self.old=='/' else self.old)+'/cgroup.procs'
        self.fd=os.open(target,os.O_WRONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
        self.leaf.write('cgroup.procs',str(self.pid))
        require(membership(self.pid)==self.leaf.relative,'not_admitted')
    def leave(self):
        require(self.fd is not None and os.getpid()==self.pid,'orphan_hold')
        os.write(self.fd,str(self.pid).encode('ascii'))
        require(membership(self.pid)==self.old,'orphan_hold')
        os.close(self.fd);self.fd=None


def shmem(leaf):
    leaf.check();raw=read_at(leaf.fd,'memory.stat',trusted_uid=0)
    values={}
    for line in raw.splitlines():
        key,value=line.split();require(key not in values,'not_admitted')
        values[key]=integer(int(value))
    require('shmem' in values,'not_admitted')
    require(read_at(leaf.fd,'memory.swap.current',trusted_uid=0).strip()=='0','not_admitted')
    return values['shmem']


def empty_twice(leaf):
    first=leaf.empty();second=leaf.empty()
    require(first[0]==second[0] and first[1]<second[1] and shmem(leaf)==0,'orphan_hold')
    return 2


class Session:
    """Root event-driven R4 job. All durable writes stay on owner event loop.

    Reader/reaper threads only deliver kernel/IPC facts and wake the selector;
    no polling scheduler, queue writes or source access occurs in them.
    """
    def __init__(self,owner,job,current):
        import queue
        self.owner,self.job,self.current=owner,job,current
        self.profile=owner.profile;self.policy=self.profile.store(job['store_id'])
        require(self.profile.r4 is not None and self.profile.r4.enabled,'not_admitted')
        self.events=queue.Queue();self.threads=[];self.channels={};self.children={}
        self.namespace=self.residence=self.ram=self.leaf=None
        self.sources={};self.image_fd=None;self.image=None;self.before=self.after=None
        self.final_fd=None
        self.owner_ready=self.backup_done=self.released=self.done=self.canceled=False
        self.decision=None;self.previous=None;self.phase='claim';self.held=False
        self.failure_reason=None
        self.kill_sent=False
        self.gate_id='claim_publish';self.subphase='claim'
        self.source_gate_verified=self.source_open_started=False
        self.first_hold_diagnostic=None
        self.owner_trace_fd=None;self.owner_diagnostic=None
        self.started=time.monotonic_ns();self.deadline=self.started+self.policy.attempt_seconds*10**9

    def left(self):
        value=(self.deadline-time.monotonic_ns())/1e9
        require(value>0,'not_admitted');return value

    def wake(self):
        try:self.owner._wake_write.send(b'r')
        except OSError:pass

    def at(self,gate,subphase):
        require(gate in GATES and subphase in SUBPHASES,'invalid_request')
        self.gate_id,self.subphase=gate,subphase

    def watch(self,name,child,endpoint,uid):
        import threading
        from . import r4_ipc
        def reap():
            try:child.wait();self.events.put(('reaped',name,None))
            except Exception as error:self.events.put(('reap_failed',name,error))
            self.wake()
        def packets():
            try:
                while True:
                    kind,payload,fd=r4_ipc.receive(endpoint,self.binding,uid,child.pid,seconds=self.left())
                    require(fd is None,'unauthorized')
                    self.events.put((kind,name,payload));self.wake()
                    if kind in {'owner_done','released'}:return
            except Exception as error:
                self.events.put(('channel_closed',name,error));self.wake()
        for function in (reap,packets):
            thread=threading.Thread(target=function,daemon=True);self.threads.append(thread);thread.start()

    def guard(self):
        from .live_receipts import guest_sample
        self.left();self.leaf.check();self.namespace.check()
        require(membership(os.getpid())==self.leaf.relative,'not_admitted')
        nodes=self.leaf.samples()
        require(nodes[-1].maximum==self.policy.memory_max_bytes,'not_admitted')
        sample=guest_sample(nodes);sample.check(self.previous)
        require(read_at(self.leaf.fd,'pids.max',trusted_uid=0).strip()==str(self.profile.r4.task_limit),'not_admitted')
        self.previous=sample
        return sample

    def start(self):
        import hashlib
        import subprocess
        import uuid
        from dataclasses import asdict
        from . import contracts as c,r4_ipc
        from .live_coordinator import memory_document,fill_document
        from .live_cgroup import create_leaf
        from .r4_sandbox import MountNamespace,PrivateTmpfs
        root=self.owner;ar=aw=cr=cw=rr=rw=None
        claim=profile_fd=child_endpoint=None
        try:
            ar,aw=os.pipe2(os.O_CLOEXEC);cr,cw=os.pipe2(os.O_CLOEXEC);rr,rw=os.pipe2(os.O_CLOEXEC)
            nonce=os.urandom(32).hex();pipe=os.fstat(ar)
            self.job.update(state='claimed',claim_epoch=self.current['controller_epoch'],attempt_id=str(uuid.uuid4()),
                run_id=str(uuid.uuid4()),updated_at=c.utc(),reason_code='claimed',
                auth_hash=hashlib.sha256(nonce.encode()).hexdigest(),auth_device=pipe.st_dev,auth_inode=pipe.st_ino,
                resource_envelope=dict(fixture_only=False,memory_limit_bytes=self.policy.memory_max_bytes,
                    timeout_seconds=self.policy.attempt_seconds))
            root._commit(self.current)  # BEFORE leaf/namespace/child/source exposure.
            self.at('resource_leaf','leaf_create')
            self.leaf=create_leaf(self.profile.delegated,(self.profile.delegated_device,self.profile.delegated_inode),
                self.job,self.policy.memory_max_bytes,worker_gid=self.profile.worker_gid,tasks=self.profile.r4.task_limit)
            self.at('resource_leaf','leaf_enter');self.residence=Residence(self.leaf);self.residence.enter()
            self.at('resource_leaf','namespace')
            self.namespace=MountNamespace().enter()
            self.namespace_stamp=self.namespace.current
            self.at('resource_leaf','tmpfs')
            self.ram=PrivateTmpfs(self.namespace,self.job['claim_epoch'],self.job['attempt_id'],
                self.policy.image_max_bytes,self.profile.r4.nr_inodes,self.policy.uid,self.policy.gid,self.profile.worker_gid)
            parent,child_endpoint=r4_ipc.pair();self.channels['worker']=parent
            claim=memory_document(None);profile_fd=memory_document(asdict(self.profile))
            self.at('worker_bootstrap','spawn')
            process=subprocess.Popen(root.command(ar),cwd=self.profile.release_root,
                env={'PATH':'/usr/bin:/bin','HOME':'/nonexistent','LANG':'C.UTF-8'},
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                close_fds=True,pass_fds=(ar,cr,rw,claim,profile_fd,child_endpoint.fileno()),shell=False,
                user=self.profile.worker_uid,group=self.profile.worker_gid,extra_groups=self.profile.worker_groups)
            root.process=process;root.active=self.job['job_id'];root.cancel_fd=cw;cw=None
            worker=Child(process);self.children['worker']=worker
            self.at('worker_bootstrap','identity')
            require(membership(worker.pid)==self.leaf.relative,'unauthorized')
            node=self.leaf.samples()[-1]
            require(node.maximum==self.policy.memory_max_bytes and node.swap_max==node.swap_current==0
                and set(node.procs)=={os.getpid(),worker.pid},'not_admitted')
            self.job.update(state='running',worker_pid=worker.pid,reason_code='running',updated_at=c.utc())
            self.at('claim_publish','running_publish')
            root._commit(self.current);fill_document(claim,root.store.read())
            self.binding=r4_ipc.claim_binding(self.job,self.profile,self.leaf,self.namespace.current)
            payload=dict(job_id=self.job['job_id'],attempt_id=self.job['attempt_id'],claim_epoch=self.job['claim_epoch'],
                nonce=nonce,claim_fd=claim,profile_fd=profile_fd,result_fd=rw,cancel_fd=cr,
                supervisor_pid=os.getpid(),supervisor_start=start_ticks(os.getpid()),leaf=self.leaf.relative,
                leaf_device=self.leaf.identity[0],leaf_inode=self.leaf.identity[1],
                gate_device=root.gate_spec.device,gate_inode=root.gate_spec.inode,started_ns=self.started,
                r4_fd=child_endpoint.fileno())
            self.at('worker_bootstrap','auth_release')
            raw=c.encode(payload,4096);require(os.write(aw,raw)==len(raw))
            self.phase='gate';self.watch('worker',worker,parent,self.profile.worker_uid)
        except Exception as error:
            self.hold(error,child_name='worker');raise
        finally:
            if child_endpoint is not None:child_endpoint.close()
            for fd in (ar,aw,cr,cw,rr,rw,claim,profile_fd):
                if fd is not None:os.close(fd)

    def launch_owner(self,payload):
        import subprocess
        from dataclasses import asdict
        from . import contracts as c,r4_ipc,live_sqlite
        from .live_coordinator import memory_document
        c.closed(payload,{'lock_fd','namespace'})
        require(self.phase=='gate' and not self.canceled
            and payload['namespace']==list(self.namespace.current),'unauthorized')
        self.at('gate_owner','identity')
        gate_owner(self.children['worker'],self.owner.gate_spec.path,
            (self.owner.gate_spec.device,self.owner.gate_spec.inode),payload['lock_fd'],self.leaf,
            self.policy.memory_max_bytes,self.namespace.current)
        self.source_gate_verified=True
        self.at('resource_leaf','wait');sample=self.guard()
        # Independent gate is NOW positively verified. All source metadata/FD
        # acquisition starts here, never in queue admission/namespace startup.
        self.at('gate_owner','source_inspect');self.source_open_started=True
        self.before=live_sqlite.inspect_source(self.policy)
        require(self.before[1]['-wal'] is not None and self.before[1]['-shm'] is not None,'not_admitted')
        sample.admit(self.policy,self.policy.image_max_bytes,self.before[1]['-wal'][2])
        self.at('owner_helper','source_open')
        for kind,suffix in (('main',''),('wal','-wal'),('shm','-shm')):
            fd=os.open(self.policy.source+suffix,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
            expected=self.before[0] if kind=='main' else self.before[1][suffix]
            require(identity(os.fstat(fd))==expected[:2],'unsafe_path');self.sources[kind]=fd
        self.at('owner_helper','source_view');self.ram.source_view(self.sources)
        parent,child=r4_ipc.pair();self.channels['owner']=parent
        self.owner_trace_fd,diagnostic=os.pipe2(os.O_CLOEXEC|os.O_NONBLOCK)
        auth=None
        try:
            auth=memory_document(dict(profile=asdict(self.profile),queue=self.owner.store.read(),job_id=self.job['job_id'],
            binding=self.binding,root=str(self.ram.root),namespace=list(self.namespace.current),leaf=self.leaf.relative,
            parent_pid=os.getpid(),parent_start=start_ticks(os.getpid()),deadline_ns=self.deadline,channel_fd=child.fileno(),
            diagnostic_fd=diagnostic,source_identities={kind:list(identity(os.fstat(fd))) for kind,fd in self.sources.items()}))
            self.at('owner_helper','spawn')
            process=subprocess.Popen([self.profile.python,'-B','-E','-s','-m',
                'app.db_audit_coordinator.r4_owner_helper',str(auth)],cwd=self.profile.release_root,
                env={'PATH':'/usr/bin:/bin','HOME':'/nonexistent','LANG':'C.UTF-8'},
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                close_fds=True,pass_fds=(auth,child.fileno(),diagnostic),shell=False)
            helper=Child(process);self.children['owner']=helper
            require(membership(helper.pid)==self.leaf.relative,'unauthorized')
            self.phase='owner';self.watch('owner',helper,parent,self.policy.uid)
        finally:
            if auth is not None:os.close(auth)
            os.close(diagnostic);child.close()

    def owner_outcome(self,helper):
        """Exactly one root log after positive reap; never changes queue/result."""
        from . import contracts as c
        if self.owner_diagnostic is not None:return
        code=helper.reaped()
        raw=b''
        if self.owner_trace_fd is not None:
            try:
                try:raw=os.read(self.owner_trace_fd,OWNER_DIAGNOSTIC_LIMIT+1)
                except OSError:pass
            finally:os.close(self.owner_trace_fd);self.owner_trace_fd=None
        detail=owner_trace(raw)
        outcome=('complete' if code==0 and self.backup_done and not self.canceled else
            'canceled' if self.canceled or detail['stop_reason']=='canceled' else
            'deadline' if detail['stop_reason']=='deadline' else
            'pre_ready_exit' if not self.owner_ready else 'backup_abort')
        self.owner_diagnostic=dict(event='qio226_r4_owner_outcome',version=1,
            job_id=c.identifier(self.job['job_id']),attempt_id=c.identifier(self.job['attempt_id']),
            seq=integer(self.job['seq'],1),child_exit_code=code,outcome=outcome,
            owner_ready_received=self.owner_ready,owner_done_received=self.backup_done,**detail)
        emit_hold(self.owner_diagnostic)  # Same protected root-only bounded sink.

    def cancel(self):
        from . import r4_ipc
        self.canceled=True
        if 'owner' in self.channels:
            try:r4_ipc.send(self.channels['owner'],'cancel',self.binding,{})
            except Exception:pass
        # While the helper is active the worker must keep waiting, not report
        # completion before positive helper reap. The pipe cancels an active T3.
        if self.phase=='gate':self.hold()
        if self.owner.cancel_fd is not None:
            try:os.write(self.owner.cancel_fd,b'c')
            except OSError:pass

    def pump(self):
        import hashlib
        import queue
        from . import contracts as c,r4_ipc,r4_snapshot,live_sqlite
        if self.done or self.held:return False
        try:
            self.at('resource_leaf','wait')
            self.guard()
            while True:
                try:kind,name,payload=self.events.get_nowait()
                except queue.Empty:break
                if kind=='gate_ready':self.launch_owner(payload)
                elif kind=='owner_ready':
                    self.at('owner_helper','ready')
                    c.closed(payload,{'pid'})
                    require(name=='owner' and self.phase=='owner' and payload['pid']==self.children['owner'].pid,'unauthorized')
                    require(set(self.leaf.samples()[-1].procs)=={os.getpid(),*(child.pid for child in self.children.values())},'unauthorized')
                    self.guard();self.owner_ready=True
                    r4_ipc.send(self.channels['owner'],'begin',self.binding,{})
                elif kind=='owner_done':
                    c.closed(payload,{'complete','page_size'})
                    require(name=='owner' and self.owner_ready and payload['complete'] is True,'unauthorized')
                    integer(payload['page_size'],512,65536);self.backup_done=True
                elif kind=='t3_done':
                    self.at('t3','ready')
                    c.closed(payload,{'result','reason_code','snapshot_metadata'})
                    require(name=='worker' and payload['result'] in {'passed','failed','incomplete'},'unauthorized')
                    require((payload['result'],payload['reason_code']) in {('passed','audit_passed'),
                        ('failed','audit_failed'),('incomplete','canceled')},'unauthorized')
                    self.decision=payload
                elif kind=='released':
                    self.at('release_cleanup','ack')
                    require(name=='worker' and payload=={} and self.phase=='release','orphan_hold');self.released=True
                elif kind=='channel_closed':
                    if name=='worker' and not self.released:
                        self.at('worker_bootstrap' if not self.source_gate_verified else 'channel_closed','wait')
                        child=self.children['worker']
                        if not child.waited:child.exited.wait(.25)  # Sole reaper, bounded event wait; no PID inference.
                        self.hold(payload,child_name='worker');return False
                elif kind=='reap_failed':
                    self.at('worker_reap' if name=='worker' else 'owner_helper','reap')
                    self.hold(payload,child_name=name);return False
                elif kind!='reaped':raise c.CoordinatorError('unauthorized')
            helper=self.children.get('owner')
            if helper is not None and helper.waited and self.phase=='owner':
                self.at('owner_helper','reap')
                code=helper.reaped()
                self.owner_outcome(helper)
                require(set(self.leaf.samples()[-1].procs)=={os.getpid(),self.children['worker'].pid},'orphan_hold')
                self.guard()
                node=self.leaf.samples()[-1]
                self.memory=dict(maximum=node.maximum,current_after_backup=node.current,
                    shmem_after_backup=shmem(self.leaf),swap_current=node.swap_current)
                if self.backup_done and code==0 and not self.canceled:
                    stage=self.ram.stage/'snapshot.sqlite3'
                    require(shmem(self.leaf)>=stage.stat().st_size,'not_admitted')
                    self.at('snapshot_promotion','promote')
                    self.image_fd,self.image=r4_snapshot.promote(self.ram,self.policy,self.profile.worker_gid,helper=helper)
                    self.at('snapshot_dirfd','pin_final')
                    self.final_fd,folder=r4_snapshot.pin_final(self.ram,self.image_fd,self.profile.worker_gid)
                    self.at('snapshot_dirfd','send')
                    r4_ipc.send(self.channels['worker'],'snapshot',self.binding,
                        dict(image=self.image,directory=folder),fds=(self.image_fd,self.final_fd))
                    self.phase='validating'
                else:
                    self.failure_reason='canceled' if self.canceled else 'worker_crashed' if code!=0 else 'preflight_denied'
                    r4_ipc.send(self.channels['worker'],'cancel',self.binding,{})
                    self.phase='validating'
            if self.decision is not None and self.phase=='validating':
                self.at('release_cleanup','source_recheck')
                require(helper is not None and helper.waited,'orphan_hold')
                self.after=live_sqlite.inspect_source(self.policy)
                require(self.before[0][:2]==self.after[0][:2],'unsafe_path')
                for side in ('-wal','-shm'):
                    require(self.before[1][side][:2]==self.after[1][side][:2],'unsafe_path')
                if self.image_fd is not None:
                    require(r4_snapshot.digest_fd(self.image_fd,self.policy.image_max_bytes)==self.image,'unsafe_path')
                    os.close(self.image_fd);self.image_fd=None
                self.at('release_cleanup','close_fds')
                if self.final_fd is not None:os.close(self.final_fd);self.final_fd=None
                for fd in self.sources.values():os.close(fd)
                self.sources={}
                self.at('release_cleanup','unlink')
                for folder in (self.ram.stage,self.ram.final):
                    for name in os.listdir(folder):
                        require(name in {'snapshot.sqlite3','snapshot.sqlite3-wal','snapshot.sqlite3-shm','snapshot.sqlite3-journal'},'orphan_hold')
                        target=folder/name;info=target.lstat()
                        require(stat.S_ISREG(info.st_mode) and info.st_nlink==1,'orphan_hold');target.unlink()
                self.at('release_cleanup','unmount');self.ram.cleanup()
                # Worker still owns its sealed claim/profile memfds (also
                # charged shmem). Zero belongs AFTER its positive final reap,
                # not before the authenticated permission to release the gate.
                self.phase='release';r4_ipc.send(self.channels['worker'],'release',self.binding,{})
            worker=self.children['worker']
            if self.released and worker.waited:
                self.at('worker_reap','reap')
                require(worker.reaped()==(0 if self.decision['result']=='passed' else 2),'orphan_hold')
                for channel in self.channels.values():channel.close()
                for thread in self.threads:thread.join(timeout=1);require(not thread.is_alive(),'orphan_hold')
                self.at('release_cleanup','namespace_restore');self.namespace.restore()
                self.at('release_cleanup','leaf_exit');self.residence.leave()
                self.at('release_cleanup','empty')
                observations=empty_twice(self.leaf)
                proof=dict(binding_sha256=self.binding,
                    source_pre_sha256=hashlib.sha256(c.encode(self.before)).hexdigest(),
                    source_post_sha256=hashlib.sha256(c.encode(self.after)).hexdigest(),snapshot=self.image,
                    leaf_identity=list(self.leaf.identity),namespace_identity=list(self.namespace_stamp),
                    helper_reaped=True,gatekeeper_reaped=True,cleanup_complete=True,shmem_zero=True,
                    empty_observations=observations,scope='guest_vm_only',
                    source_observations=c.decode(c.encode(dict(pre=self.before,post=self.after))),
                    memory_observations=self.memory)
                from .live_policy import make_result
                if self.failure_reason is not None:
                    self.decision=dict(result='incomplete',reason_code=self.failure_reason,snapshot_metadata=None)
                elif self.canceled:
                    self.decision=dict(result='incomplete',reason_code='canceled',snapshot_metadata=None)
                result=make_result(self.job,self.decision['result'],self.decision['reason_code'],
                    snapshot=self.decision['snapshot_metadata'],receipt=proof,
                    duration_ms=(time.monotonic_ns()-self.started)//1000000)
                # One bounded, closed root-only attended receipt, no source
                # payload/path/nonce. Queue keeps its SHA256 commitment so 128
                # historical jobs stay within the unchanged 256KiB contract.
                import sys
                print(c.encode(dict(r4_release_proof=proof),8192).decode('ascii'),file=sys.stderr,flush=True)
                current=self.owner._state();job=next(j for j in current['jobs'] if j['job_id']==self.job['job_id'])
                import copy
                job.update(state='completed' if result['result']=='passed' else 'failed' if result['result']=='failed' else 'canceled' if result['reason_code']=='canceled' else 'deferred',
                    audit_result=result,reason_code=result['reason_code'],updated_at=c.utc())
                current['last_attempt_by_store'][job['store_id']]=copy.deepcopy(result)
                if result['result']=='passed':current['last_verified_success_by_store'][job['store_id']]=copy.deepcopy(result)
                self.at('claim_publish','terminal');self.owner._commit(current)
                self.proof=proof;self.done=True
                for child in self.children.values():child.close()
                self.leaf.close()
                if self.owner.cancel_fd is not None:os.close(self.owner.cancel_fd);self.owner.cancel_fd=None
                self.owner.process=self.owner.active=None;self.owner.orphan_hold=False
                return True
            return False
        except Exception as error:
            self.hold(error);return False

    def hold(self,error=None,*,child_name=None):
        from . import contracts as c
        first=not self.held
        self.held=True;self.owner.orphan_hold=True
        # This is NOT terminal/reap/cleanup. Retain the entire job and locks;
        # no new FIFO admission, no automatic reset, unmount or historical PASS.
        try:
            current=self.owner._state();job=next(j for j in current['jobs'] if j['job_id']==self.job['job_id'])
            if job['reason_code']!='orphan_hold':job['reason_code']='orphan_hold';self.owner._commit(current)
        except Exception as write_error:
            if error is None:error=write_error
        if first:
            self.first_hold_diagnostic=hold_diagnostic(self,error,child_name)
            emit_hold(self.first_hold_diagnostic)
            helper=getattr(self,'children',{}).get('owner')
            if helper is not None:
                if not helper.waited:
                    helper.exited.wait(max(0,min(.25,(self.deadline-time.monotonic_ns())/1e9)))
                if helper.waited:
                    try:self.owner_outcome(helper)
                    except c.CoordinatorError:pass  # Uncertain reap is never an exit-status receipt.

    def expire(self):
        if self.done:return
        if time.monotonic_ns()>=self.deadline and not self.kill_sent:
            self.at('deadline','wait')
            self.hold()
            if self.leaf is not None:self.leaf.write('cgroup.kill','1')
            self.kill_sent=True
            # Root is deliberately in this same leaf: expiry may kill the
            # supervisor too. That remains durable ORPHAN_HOLD, never next FIFO.
