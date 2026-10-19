"""Explicit administrative abandonment of ONE old LAB epoch; never a reap proof.

No socket/startup integration, environment input, reset, new epoch or submit.
The root operator supplies fresh containment observations, not audit results.
The CLI has fixed trusted paths and no overrides. All writes require both old
permanent flocks; an uncertain transition must return to independent review.
"""
from __future__ import annotations

import copy
import hashlib
import os
from pathlib import Path
import stat
import sys
import time

from . import contracts as c
from .live_coordinator import OperationalStateStore
from .live_policy import ROOT, state, make_result, require, integer
from .live_receipts import directory, filesystem_magic, identity
from .locks import LockSpec, PermanentLock, trusted_open

EPOCH='475efdfc-1ee0-44b7-9829-98552752a3e4'
JOB='8f5a1f66-3b5b-464e-801f-17de2ce72a39'
ATTEMPT='dc1bc15e-a8b1-44f8-a44a-836bb727491c'
SERVICE='qio226-abc-coordinator-lab.service'
EVIDENCE_ROOT='/var/lib/captive-portal/db-audit-recovery'
RECEIPT='containment.v1.json'
BACKUP='old-epoch-'+EPOCH+'.queue-before.json'
CHECKS=frozenset({'original_unit_stopped','original_cgroup_and_descendants_absent',
    'coordinator_and_worker_absent','process_fd_owners_absent',
    'old_child_launch_paths_contained','unexpected_legacy_auditors_absent',
    'launches_fenced_for_operator_window','socket_absent'})
STORES=('public_traffic','network_service_intelligence','traffic_projection')


def abandon(value):
    """Pure exact old-state transition; no invented historical wait or PASS."""
    state(value)
    require(value['controller_epoch']==EPOCH and value['next_sequence']==4
        and len(value['jobs'])==3 and value['last_attempt_by_store']=={}
        and value['last_verified_success_by_store']=={},'orphan_hold')
    for seq,(job,store) in enumerate(zip(value['jobs'],STORES),1):
        require(job['seq']==seq and job['store_id']==store and job['audit_result'] is None,'orphan_hold')
        require(job['state']==('claimed' if seq==1 else 'queued'),'orphan_hold')
    first=value['jobs'][0]
    require(first['job_id']==JOB and first['attempt_id']==ATTEMPT
        and first['claim_epoch']==EPOCH and first['worker_pid'] is None,'orphan_hold')
    changed=copy.deepcopy(value);now=c.utc();first=changed['jobs'][0]
    output=make_result(first,'incomplete','restarted_after_claim')
    first.update(state='deferred',reason_code='restarted_after_claim',updated_at=now,audit_result=output)
    changed['last_attempt_by_store']['public_traffic']=copy.deepcopy(output)
    # No result/attempt/worker is fabricated for the two never-started jobs.
    for job in changed['jobs'][1:]:job.update(state='canceled',reason_code='canceled',updated_at=now)
    return state(changed)


def attestation(value, *, now_ns, boot_id):
    """Closed root-operator declarations; these are NOT kernel reap receipts.

    Raw read-only evidence is retained outside the active queue. Each of TWO
    separate current observations references its own immutable evidence digest.
    Missing inventory/containment is HOLD, not an inferred negative result.
    """
    c.closed(value,{'schema','epoch','job_id','attempt_id','queue_identity','queue_sha256',
        'queue_bytes','owner_identity','heavy_identity','boot_id','service','observations'})
    require(value['schema']=='db_audit_coordinator.abandon.old_epoch.v1'
        and (value['epoch'],value['job_id'],value['attempt_id'])==(EPOCH,JOB,ATTEMPT)
        and value['boot_id']==boot_id and value['service']==SERVICE,'orphan_hold')
    c.identifier(boot_id);c.digest(value['queue_sha256']);integer(value['queue_bytes'],1,c.MAX_BYTES)
    for key in ('queue_identity','owner_identity','heavy_identity'):
        pair=value[key];require(type(pair) is list and len(pair)==2,'orphan_hold')
        integer(pair[0]);integer(pair[1],1)
    require(len({tuple(value[key]) for key in ('queue_identity','owner_identity','heavy_identity')})==3,'orphan_hold')
    observations=value['observations']
    require(type(observations) is list and len(observations)==2,'orphan_hold')
    previous=-1;digests=set()
    for observation in observations:
        c.closed(observation,{'captured_ns','evidence_sha256','main_pid','checks'})
        captured=integer(observation['captured_ns'])
        require(previous<captured<=now_ns and now_ns-captured<60_000_000_000,'orphan_hold')
        c.digest(observation['evidence_sha256']);digests.add(observation['evidence_sha256'])
        require(type(observation['main_pid']) is int and observation['main_pid']==0,'orphan_hold')
        c.closed(observation['checks'],CHECKS)
        require(all(flag is True for flag in observation['checks'].values()),'orphan_hold')
        previous=captured
    require(len(digests)==2,'orphan_hold')
    return value


class _HeavyLock:
    """Same permanent flock, accepting ONLY its existing root:worker 0640."""
    def __init__(self,path,expected):self.path,self.expected,self.fd=path,tuple(expected),None
    def check(self):
        before=self.path.lstat()
        require(identity(before)==self.expected and stat.S_ISREG(before.st_mode)
            and before.st_uid==0 and stat.S_IMODE(before.st_mode)==0o640
            and before.st_nlink==1 and before.st_size==0,'unsafe_path')
        if self.fd is not None:require(identity(os.fstat(self.fd))==self.expected,'unsafe_path')
    def __enter__(self):
        import fcntl
        self.check()
        fd=os.open(self.path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK)
        try:
            require(identity(os.fstat(fd))==self.expected,'unsafe_path')
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.fd=fd;self.check();return self
        except Exception:
            self.fd=None;os.close(fd);raise c.CoordinatorError('orphan_hold') from None
    def __exit__(self,*args):
        if self.fd is not None:os.close(self.fd);self.fd=None


def _raw(path,expected=None):
    fd=trusted_open(path,0,identity=expected)
    with os.fdopen(fd,'rb') as stream:raw=stream.read(c.MAX_BYTES+1)
    require(len(raw)<=c.MAX_BYTES,'orphan_hold')
    return raw


def _evidence(directory_fd,name,raw):
    """No clobber, exact bytes, root-only immutable-by-policy evidence copy.

    0400 is not a claim of filesystem immutable flags. A partial/failed fsync
    leaves evidence for review and blocks retry; it is never silently replaced.
    """
    fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o400,dir_fd=directory_fd)
    try:
        offset=0
        while offset<len(raw):
            written=os.write(fd,raw[offset:]);require(written>0,'orphan_hold');offset+=written
        os.fsync(fd)
    finally:os.close(fd)
    os.fsync(directory_fd)


def _recover(root,evidence_root, *, boot_id, now=time.monotonic_ns):
    """Private fixture seam; CLI never accepts paths, UIDs or clock overrides."""
    require(os.name=='posix' and os.geteuid()==0,'unauthorized')
    root=Path(root);evidence_root=Path(evidence_root)
    directory_fd=directory(str(root));evidence_fd=None
    try:
        require(stat.S_IMODE(os.fstat(directory_fd).st_mode)==0o710,'unsafe_path')
        evidence_fd=directory(str(evidence_root))
        require(stat.S_IMODE(os.fstat(evidence_fd).st_mode)==0o700
            and evidence_root!=root and root not in evidence_root.parents,'unsafe_path')
        require(filesystem_magic(directory_fd)==0xEF53 and filesystem_magic(evidence_fd)==0xEF53,'not_admitted')
        receipt_raw=_raw(evidence_root/RECEIPT)
        receipt=attestation(c.decode(receipt_raw),now_ns=now(),boot_id=boot_id)
        for number,observation in enumerate(receipt['observations'],1):
            raw=_raw(evidence_root/f'observation-{number}.txt')
            require(bool(raw) and hashlib.sha256(raw).hexdigest()==observation['evidence_sha256'],'orphan_hold')
        owner_path=root/'coordinator.lock';queue_path=root/'queue-state.v1.json'
        owner_info=owner_path.lstat()
        require(owner_info.st_size==0 and stat.S_IMODE(owner_info.st_mode)==0o600,'unsafe_path')
        spec=LockSpec(str(owner_path),0,*receipt['owner_identity'])
        with PermanentLock(spec) as owner, _HeavyLock(root/'heavy.lock',receipt['heavy_identity']) as heavy:
            original=_raw(queue_path,receipt['queue_identity'])
            require(len(original)==receipt['queue_bytes']
                and hashlib.sha256(original).hexdigest()==receipt['queue_sha256'],'orphan_hold')
            changed=abandon(c.decode(original))
            store=OperationalStateStore(queue_path,0,owner)
            require(store.identity==tuple(receipt['queue_identity']),'orphan_hold')
            # Any earlier attempt, even interrupted before queue commit, needs
            # independent review. Never overwrite its immutable evidence.
            _evidence(evidence_fd,BACKUP,original)
            _evidence(evidence_fd,BACKUP+'.attestation.json',receipt_raw)
            require(_raw(evidence_root/BACKUP)==original,'orphan_hold')
            require(identity(root.lstat())==identity(os.fstat(directory_fd))
                and identity(evidence_root.lstat())==identity(os.fstat(evidence_fd)),'unsafe_path')
            require(_raw(evidence_root/RECEIPT)==receipt_raw,'orphan_hold')
            # Revalidate time, locks, original bytes and exact inode immediately
            # before the ONE existing atomic file+directory-fsynced transition.
            attestation(receipt,now_ns=now(),boot_id=boot_id)
            owner.check();heavy.check()
            require(_raw(queue_path,receipt['queue_identity'])==original,'orphan_hold')
            store.commit(changed)
            require(state(c.decode(_raw(queue_path,store.identity)))==changed,'queue_unknown')
            owner.check();heavy.check()
            return 'administratively_abandoned_unverified'
    finally:
        if evidence_fd is not None:os.close(evidence_fd)
        os.close(directory_fd)


def main(argv=None):
    args=sys.argv[1:] if argv is None else argv
    if args!=['abandon-old-epoch']:return 2
    try:
        require(os.name=='posix' and os.geteuid()==0,'unauthorized')
        # Fixed kernel origin, never an ENV supplied namespace or boot receipt.
        boot=Path('/proc/sys/kernel/random/boot_id').read_text(encoding='ascii').strip()
        _recover(ROOT,EVIDENCE_ROOT,boot_id=boot)
    except Exception:
        print('db_audit_coordinator stage=operator_abandonment reason_code=orphan_hold',file=sys.stderr)
        return 3
    print('administratively_abandoned_unverified')
    return 0


if __name__=='__main__':raise SystemExit(main())
