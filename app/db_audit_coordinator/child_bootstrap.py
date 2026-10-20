"""Private blocked operational child. No public DB selector or live fallback."""
from __future__ import annotations

import fcntl
import hashlib
import os
from pathlib import Path
import select
import stat
import sys
import time

from . import contracts as c
from .live_policy import Deadlines,make_result,require,state,integer,physical_generation
from .live_profile import PilotProfile
from .live_receipts import directory,identity,guest_sample,start_ticks,membership,proc_text
from .live_cgroup import Leaf,mountpoint
from . import live_sqlite

AUTH_KEYS={'job_id','attempt_id','claim_epoch','nonce','claim_fd','profile_fd','result_fd','cancel_fd',
    'supervisor_pid','supervisor_start','leaf','leaf_device','leaf_inode','gate_device','gate_inode','started_ns'}


def verify_parent(supervisor_pid,supervisor_start):
    """Require one coherent PID/proc namespace; never map to a host PID.

    A procfs mounted for an ancestor namespace can resolve /proc/1 to the wrong
    process while numeric PPid/start-tick checks accidentally appear to agree.
    Check the kernel's own self mapping before looking up the supplied parent.
    """
    try:
        own=os.getpid();parent=os.getppid()
        require(os.readlink('/proc/self')==str(own),'unauthorized')
        lines=proc_text(own,'status').splitlines()
        nspid=[line.split()[1:] for line in lines if line.startswith('NSpid:')]
        ppid=[line.split()[1:] for line in lines if line.startswith('PPid:')]
        require(nspid==[[str(own)]] and ppid==[[str(parent)]]
            and parent==supervisor_pid and start_ticks(parent)==supervisor_start,'unauthorized')
    except (c.CoordinatorError,OSError,ValueError,IndexError):
        raise c.CoordinatorError('unauthorized') from None


def pipe_data(fd,seconds):
    info=os.fstat(fd);require(stat.S_ISFIFO(info.st_mode),'unauthorized')
    deadline=time.monotonic()+seconds;raw=bytearray()
    while len(raw)<=4096:
        remaining=deadline-time.monotonic();require(remaining>0,'unauthorized')
        require(bool(select.select([fd],[],[],remaining)[0]),'unauthorized')
        data=os.read(fd,4097-len(raw))
        if not data:break
        raw.extend(data)
    require(len(raw)<=4096,'unauthorized')
    return c.decode(bytes(raw),4096),identity(info)


def readonly_document(fd, *, sealed=False):
    info=os.fstat(fd);require(stat.S_ISREG(info.st_mode) and info.st_size<=c.MAX_BYTES,'unauthorized')
    if sealed:
        required=fcntl.F_SEAL_WRITE|fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_SEAL
        require(fcntl.fcntl(fd,fcntl.F_GET_SEALS)&required==required,'unauthorized')
    else: require(fcntl.fcntl(fd,fcntl.F_GETFL)&os.O_ACCMODE==os.O_RDONLY,'unauthorized')
    os.lseek(fd,0,os.SEEK_SET)
    raw=os.read(fd,c.MAX_BYTES+1);require(len(raw)<=c.MAX_BYTES,'unauthorized')
    return c.decode(raw)


def authorize(fd):
    data,pipe_identity=pipe_data(fd,300);os.close(fd)
    c.closed(data,AUTH_KEYS)
    for key in ('job_id','attempt_id','claim_epoch'):c.identifier(data[key])
    c.digest(data['nonce'])
    for key in ('supervisor_pid','supervisor_start','leaf_inode','gate_inode'):integer(data[key],1)
    for key in ('leaf_device','gate_device','started_ns'):integer(data[key])
    for key in ('claim_fd','profile_fd','result_fd','cancel_fd'):integer(data[key],0,2**20)
    require(len({data[key] for key in ('claim_fd','profile_fd','result_fd','cancel_fd')})==4
        and fd not in {data[key] for key in ('claim_fd','profile_fd','result_fd','cancel_fd')},'unauthorized')
    for key,access in (('result_fd',os.O_WRONLY),('cancel_fd',os.O_RDONLY)):
        require(stat.S_ISFIFO(os.fstat(data[key]).st_mode)
            and fcntl.fcntl(data[key],fcntl.F_GETFL)&os.O_ACCMODE==access,'unauthorized')
    verify_parent(data['supervisor_pid'],data['supervisor_start'])
    # Sealed copy of the just-fsynced running record. The child has NO writable
    # queue descriptor and cannot open or replace the root-only JSON file.
    queue=state(readonly_document(data['claim_fd'],sealed=True))
    job=next((item for item in queue['jobs'] if item['job_id']==data['job_id']),None)
    require(job is not None and job['state']=='running' and job['worker_pid']==os.getpid()
        and queue['controller_epoch']==data['claim_epoch']
        and (job['auth_device'],job['auth_inode'])==pipe_identity
        and all(job[key]==data[key] for key in ('job_id','attempt_id','claim_epoch'))
        and hashlib.sha256(data['nonce'].encode()).hexdigest()==job['auth_hash'],'unauthorized')
    profile=PilotProfile.parse(readonly_document(data['profile_fd'],sealed=True))
    require(profile.enabled and os.geteuid()==profile.worker_uid and os.getegid()==profile.worker_gid
        and set(os.getgroups())<=set(profile.worker_groups)|{profile.worker_gid},'unauthorized')
    require(Path(__file__).resolve().parents[2]==Path(profile.release_root)
        and Path.cwd()==Path(profile.release_root)
        and Path(sys.executable).resolve()==Path(profile.python).resolve(),'unauthorized')
    policy=profile.store(job['store_id'])
    require(job['source_generation']==physical_generation(policy.store_id,policy.device,policy.inode)
        and (job['method_version'],job['validator_version'],job['source_generation'])==policy.metadata(),'unauthorized')
    return data,job,profile,policy


class Gate:
    """Independent read-only group FD; child cannot write locks/queue/source."""
    def __init__(self,path,device,inode):
        self.path,self.expected,self.fd,self.pid=path,(device,inode),None,os.getpid()

    def acquire(self):
        parent=directory(str(Path(self.path).parent),uid=0,search_only=True);os.close(parent)
        before=os.stat(self.path,follow_symlinks=False)
        require(stat.S_ISREG(before.st_mode) and before.st_uid==0 and before.st_nlink==1
            and not before.st_mode & 0o022 and identity(before)==self.expected,'unsafe_path')
        require(not os.access(self.path,os.W_OK,effective_ids=True),'unsafe_path')
        self.fd=os.open(self.path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
        require(identity(os.fstat(self.fd))==self.expected,'unsafe_path')
        try:fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise c.CoordinatorError('gate_busy') from None
        self.check();return self

    def check(self):
        require(self.fd is not None and self.pid==os.getpid()
            and identity(os.fstat(self.fd))==self.expected
            and identity(os.stat(self.path,follow_symlinks=False))==self.expected,'unsafe_path')


def verify_origin(profile):
    """No user site/PYTHONPATH, writable import root or stale app bytecode."""
    for entry in sys.path:
        target=Path(entry or os.getcwd()).resolve()
        # A missing stdlib zip is normal; its enclosing directory is qualified.
        parent=target if target.is_dir() else target.parent
        fd=directory(str(parent),uid=0);os.close(fd)
        require(not os.access(parent,os.W_OK,effective_ids=True),'unsafe_path')
        if target.exists():
            info=target.stat();require(info.st_uid==0 and not info.st_mode & 0o022,'unsafe_path')


def execute(auth_fd):
    data,job,profile,policy=authorize(auth_fd)
    deadline=Deadlines(data['started_ns'],policy.attempt_seconds)
    leaf=Leaf(mountpoint(),data['leaf'],(data['leaf_device'],data['leaf_inode']))
    gate=Gate(profile.root+'/heavy.lock',data['gate_device'],data['gate_inode'])
    started=data['started_ns'];first=None;last=None;last_probe=0
    result=None
    try:
        deadline.receipt(data['started_ns'])
        leaf.contained(os.getpid(),policy.memory_max_bytes,start_ticks(os.getpid()))
        verify_origin(profile)
        gate.acquire()  # ALL source/SQLite/page/WAL/resource reads are after OWN flock.
        def guard(force=False):
            nonlocal first,last,last_probe
            deadline.check();gate.check();leaf.check()
            if select.select([data['cancel_fd']],[],[],0)[0]:
                raise c.CoordinatorError('coordinator_unavailable')
            now=time.monotonic_ns()
            if force or now-last_probe>=500_000_000:
                leaf.contained(os.getpid(),policy.memory_max_bytes)
                sample=guest_sample(leaf.samples());deadline.receipt(sample.captured_ns)
                sample.check(last)
                if first is None:first=sample
                last=sample;last_probe=now
            deadline.receipt(last.captured_ns)
        guard(True)
        # Real worker UID has no write permission on source or its parent; this
        # is in addition to mode=ro and prevents native sidecar creation/write.
        require(not os.access(policy.source,os.W_OK,effective_ids=True)
            and not os.access(str(Path(policy.source).parent),os.W_OK,effective_ids=True),'unsafe_path')
        def admit(image,wal):
            guard(True);last.admit(policy,image,wal)
        snapshot=live_sqlite.audit(policy,guard,admit)
        guard(True)
        result=make_result(job,'passed','audit_passed',snapshot=snapshot,
            duration_ms=(time.monotonic_ns()-started)//1_000_000)
    except Exception as error:
        reason='gate_busy' if isinstance(error,c.CoordinatorError) and error.code=='gate_busy' else 'preflight_denied'
        if select.select([data['cancel_fd']],[],[],0)[0]:reason='canceled'
        kind='failed' if isinstance(error,live_sqlite.AuditFailure) and reason!='canceled' else 'incomplete'
        if kind=='failed':reason='audit_failed'
        result=make_result(job,kind,reason,duration_ms=(time.monotonic_ns()-started)//1_000_000)
    finally:
        leaf.close()
        for key in ('claim_fd','profile_fd','cancel_fd'):
            try:os.close(data[key])
            except OSError:pass
    if result['result']=='passed':
        try:deadline.check()
        except Exception:result=make_result(job,'incomplete','timeout',duration_ms=(time.monotonic_ns()-started)//1_000_000)
    raw=c.encode(result,4096)
    require(os.write(data['result_fd'],raw)==len(raw))
    os.close(data['result_fd'])
    # Never unlock/close global gate here: process exit is its release boundary.
    return 0 if result['result']=='passed' else 2


def main(argv=None):
    args=sys.argv[1:] if argv is None else argv
    if os.name!='posix' or len(args)!=1 or not args[0].isascii() or not args[0].isdecimal():return 2
    try:return execute(int(args[0]))
    except Exception:return 3


if __name__=='__main__':os._exit(main())
