"""One per-run cycle, one child/image, positive release before the next job."""
from dataclasses import dataclass
import json
import multiprocessing
import os
from pathlib import Path
import signal
import time
import uuid

from app.admin_web.operations_inventory import STORES, load_inventory
from .model import AuditError, LIMIT, identifier, project, stamp
from .preflight import prepare
from .readiness import confirm
from .snapshot import SourceSnapshotAndT3, native_admission, generation, require_identity


@dataclass(frozen=True)
class QualifiedManifest:
    ready: object
    qualifications: tuple = ()


@dataclass(frozen=True)
class WorkerOutcome:
    result: dict | None
    released: bool
    reason: str


def _child(channel,job,validators):
    # No arbitrary IPC import strings/pickle results; parent accepts bounded JSON.
    try:
        os.setsid()
        result=SourceSnapshotAndT3(validators=validators).run(job)
        channel.send_bytes(json.dumps(dict(result=result,reason='complete'),allow_nan=False).encode())
    except AuditError as error:
        channel.send_bytes(json.dumps(dict(result=None,reason=error.reason)).encode())
    except BaseException:
        try:channel.send_bytes(b'{"result":null,"reason":"worker_failed"}')
        except (OSError,EOFError):pass
        # multiprocessing must not serialize/print a private traceback to journald.
        channel.close()
        os._exit(1)
    finally:channel.close()


def _group_gone(pid):
    try:os.killpg(pid,0)
    except ProcessLookupError:return True
    except PermissionError:return False
    return False


class SerialWorker:
    """POSIX owner-qualified worker. Windows tests use portable injected seams.

    No healthy-job timeout. The two short waits below are ONLY cancellation /
    failed-IPC cleanup escalation, never an integrity/T3 acceptance criterion.
    """
    def __init__(self,validators=None):self.validators=dict(validators or {})

    def run(self,job,cancelled):
        if os.name!='posix':return WorkerOutcome(None,True,'resource_unqualified')
        try:native_admission(job)
        except AuditError as error:return WorkerOutcome(None,True,error.reason)
        context=multiprocessing.get_context('fork')
        read,write=context.Pipe(duplex=False)
        child=context.Process(target=_child,args=(write,job,self.validators),daemon=False)
        child.start();write.close()
        message=None;reason='worker_failed';cleanup=False
        try:
            while child.is_alive():
                if cancelled():reason='cancelled';cleanup=True;break
                if read.poll(0.05):
                    try:message=read.recv_bytes(LIMIT)
                    except (OSError,EOFError):cleanup=True
                    break
            if cleanup:
                try:os.killpg(child.pid,signal.SIGTERM)
                except ProcessLookupError:child.terminate()
                child.join(2)
                if child.is_alive():
                    try:os.killpg(child.pid,signal.SIGKILL)
                    except ProcessLookupError:child.kill()
                    child.join(2)
            else:
                # A healthy job/result has no elapsed cutoff; reaping is required.
                while child.is_alive() and not cancelled():child.join(0.05)
                if child.is_alive():
                    cleanup=True;reason='cancelled'
                    try:os.killpg(child.pid,signal.SIGTERM)
                    except ProcessLookupError:child.terminate()
                    child.join(2)
                    if child.is_alive():
                        try:os.killpg(child.pid,signal.SIGKILL)
                        except ProcessLookupError:child.kill()
                        child.join(2)
            if message is None and read.poll():
                try:message=read.recv_bytes(LIMIT)
                except (OSError,EOFError):pass
            # Worker address space, DB FDs and RAM vanish on positive waitpid.
            # Descendants sharing its session must also be gone. The worker has
            # no authority to launch other sessions; only reviewed validators.
            try:
                remaining={int(p) for p in (Path('/sys/fs/cgroup')/job.cgroup.lstrip('/')/'cgroup.procs').read_text().split()}
            except (OSError,ValueError,AttributeError):remaining=None
            released=(child.exitcode is not None and not Path(f'/proc/{child.pid}').exists()
                      and _group_gone(child.pid) and remaining=={os.getpid()})
            if not released:return WorkerOutcome(None,False,'release_unproven')
            if cleanup or child.exitcode!=0:return WorkerOutcome(None,True,reason)
            try:
                value=json.loads(message)
                if type(value)!=dict or set(value)!={'result','reason'}:raise ValueError()
                return WorkerOutcome(value['result'],True,value['reason'])
            except (ValueError,TypeError):return WorkerOutcome(None,True,'worker_failed')
        finally:
            read.close()
            if not child.is_alive():child.close()


class AuditCycleRunner:
    def __init__(self,journal,*,worker=None,inventory_loader=load_inventory,
                 ready_check=confirm,cancelled=lambda:False,validators=None):
        self.journal=journal
        self.validators=dict(validators or {})
        self.worker=worker if worker is not None else SerialWorker(self.validators)
        self.inventory_loader=inventory_loader
        self.ready_check=ready_check
        self.cancelled=cancelled

    def run_once(self,portal_run_id,qualified_manifest):
        proof=qualified_manifest.ready
        if (not identifier(portal_run_id) or proof.portal_run_id!=portal_run_id or not self.ready_check(proof)):
            raise AuditError('ready_unproven')
        with self.journal.claim() as acquired:
            previous=self.journal.read()
            if acquired is False:
                if previous is not None and previous['portal_run_id']==portal_run_id:
                    return project(previous)
                raise AuditError('release_unproven')
            if previous is not None and previous['portal_run_id']==portal_run_id:
                if previous['cycle_state']=='RUNNING':
                    # A lost previous executor is NOT proof that its worker died.
                    previous.update(cycle_state='ORPHAN_HOLD',reason='release_unproven')
                    for row in previous['stores']:
                        if row['deep']['state']=='RUNNING':
                            row['deep'].update(state='ORPHAN_HOLD',physical_verdict='INCOMPLETE',
                                domain_verdict='INCOMPLETE',reason='release_unproven')
                    self.journal.write(previous)
                return project(previous)
            if previous is not None and previous['cycle_state'] in {'RUNNING','ORPHAN_HOLD'}:
                # An orphan from an older portal epoch blocks NEW admissions too.
                previous.update(cycle_state='ORPHAN_HOLD',reason='release_unproven')
                self.journal.write(previous)
                return project(previous)
            value,admitted,_=prepare(True,portal_run_id,inventory_loader=self.inventory_loader,
                qualifications=qualified_manifest.qualifications)
            value['audit_cycle_id']=str(uuid.uuid4())
            if value['cycle_state']=='BLOCKED_NO_TRUSTED_BINDINGS':
                self.journal.write(value);return project(value)
            value.update(cycle_state='RUNNING',reason='running')
            # History retained separately, only for the exact same bound source.
            for row in value['stores']:
                if previous is not None:
                    old=next(r for r in previous['stores'] if r['store_id']==row['store_id'])
                    for key in ('last_verified_physical_success','last_verified_domain_success','last_verified_success'):
                        row[key]=old[key]
                    if old['last_verified_physical_success'] is not None:
                        row['freshness']='HISTORICAL' if old['effective_path_identity']==row['effective_path_identity'] else 'STALE'
                job=admitted.get(row['store_id'])
                if job is not None:
                    row['eligible_domain']=(job.domain_validator_id is not None and
                        (job.store_id,job.domain_validator_id) in self.validators)
                    row['deep'].update(state='QUEUED')
                elif row['deep']['state']!='DISABLED':
                    row['deep'].update(state='NOT_ADMITTED',physical_verdict='NOT_ADMITTED',
                        domain_verdict='NOT_ADMITTED',reason=row['admission_reason'])
            self.journal.write(value)
            for item,row in zip(STORES,value['stores']):
                job=admitted.get(item.id)
                if job is None:continue
                if self.cancelled() or not self.ready_check(proof):
                    value.update(cycle_state='INTERRUPTED',reason='cancelled' if self.cancelled() else 'ready_unproven')
                    break
                row['deep'].update(state='RUNNING',physical_verdict='RUNNING',reason='running')
                self.journal.write(value)
                outcome=self.worker.run(job,self.cancelled)
                if not outcome.released:
                    row['deep'].update(state='ORPHAN_HOLD',physical_verdict='INCOMPLETE',
                        domain_verdict='INCOMPLETE',reason='release_unproven')
                    value.update(cycle_state='ORPHAN_HOLD',reason='release_unproven')
                    self.journal.write(value);return project(value)
                if not self.ready_check(proof):outcome=WorkerOutcome(None,True,'ready_unproven')
                if outcome.result is not None:
                    try:
                        require_identity(job)
                        after=generation(job.path)
                        outcome.result['source_observation_after']=after
                        if (outcome.result.get('live_freshness')=='ADVANCED' or
                                outcome.result.get('source_observation_before')!=after or
                                outcome.result.get('source_observation_snapshot')!=after):
                            outcome.result['live_freshness']='ADVANCED'
                    except (OSError,AuditError,AttributeError):outcome=WorkerOutcome(None,True,'source_changed')
                if outcome.result is None:
                    reason=outcome.reason
                    state='RESOURCE_DEFERRED' if reason=='resource_unqualified' else 'STALE' if reason=='source_changed' else 'INCOMPLETE'
                    verdict='RESOURCE_BLOCKED' if state=='RESOURCE_DEFERRED' else 'STALE' if state=='STALE' else 'INCOMPLETE'
                    row['deep'].update(state=state,physical_verdict=verdict,domain_verdict='INCOMPLETE',reason=reason)
                    value.update(cycle_state='INTERRUPTED',reason='incomplete')
                    self.journal.write(value);break
                result=outcome.result
                if type(result)!=dict or set(result)!=set(row['deep']):raise AuditError('invalid_status')
                row['deep']=result
                # The provisional worker result cannot publish its own receipt.
                row['deep']['verified_at']=stamp()
                receipt=dict(snapshot_id=result['snapshot_id'],source_id=job.source_id,
                    portal_run_id=portal_run_id,verified_at=result['verified_at'],method=result['method'])
                result['snapshot_receipt']=receipt  # Proof of this exact released RAM image only.
                row['freshness']='STALE' if result['live_freshness']=='ADVANCED' else 'CURRENT'
                # Stale live observations do not advance historical success axes.
                # The independently verified snapshot result/receipt remain visible.
                if result['physical_verdict']=='PASS' and row['freshness']=='CURRENT':
                    row['last_verified_physical_success']=receipt
                    if result['domain_verdict']=='PASS':
                        row['last_verified_domain_success']=receipt
                        row['last_verified_success']=receipt
                project(value)  # Fail closed BEFORE persisting a worker payload.
                self.journal.write(value)
            if value['cycle_state']=='RUNNING':
                eligible=[r for r in value['stores'] if r['eligible_physical']]
                value.update(cycle_state='COMPLETE' if eligible and all(r['deep']['physical_verdict']=='PASS'
                    and (not r['eligible_domain'] or r['deep']['domain_verdict']=='PASS') for r in eligible) else 'PARTIAL',reason='complete')
            for row in value['stores']:
                if row['deep']['state']=='QUEUED':
                    row['deep'].update(state='INCOMPLETE',physical_verdict='INCOMPLETE',domain_verdict='INCOMPLETE',reason='incomplete')
            self.journal.write(value)
            return project(value)
