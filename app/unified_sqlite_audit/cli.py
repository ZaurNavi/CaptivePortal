"""Disabled-by-default, one-shot composition root. Never provisions or schedules."""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import signal
import stat

from app.admin_web.operations_inventory import STORES, load_inventory
from .model import AdmittedStore, AuditError, LIMIT, bounded, catalog, digest, enabled, project
from .readiness import probe, wait_ready
from .runner import AuditCycleRunner, QualifiedManifest
from .status import OutcomeJournal, UnifiedSqliteAuditReadService


def parse_qualifications(raw,inventory,run_id):
    """Root-attested subset of EXISTING bindings, not a second path/owner catalog.

    Pure parser; CLI protection is mandatory before calling it on disk content.
    No path comes from this file. No validator import or read permission is
    inferred from a declaration; the worker independently inspects OS controls.
    """
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise AuditError('resource_unqualified')
            result[key]=value
        return result
    try:
        if len(raw)>32768:raise ValueError()
        value=json.loads(raw,object_pairs_hook=pairs)
        if (type(value)!=dict or set(value)!={'version','portal_run_id','stores'}
                or value['version']!='audit.owner-qualification.v1' or value['portal_run_id']!=run_id
                or type(value['stores'])!=list or len(value['stores'])>len(STORES)):
            raise ValueError()
        result=[];seen=set();known={s.id for s in STORES}
        for row in value['stores']:
            if type(row)!=dict or set(row)!={'store_id','source_id','uid','gid','max_snapshot_bytes',
                    'host_memory_budget_bytes','no_competing_audit','cgroup'}:raise ValueError()
            identity=row['store_id'];cgroup=row['cgroup']
            if (type(identity)!=str or identity not in known or identity in seen
                    or inventory.store_intents[identity]!='expected' or not digest(row['source_id'])
                    or not bounded(row['uid']) or not bounded(row['gid'])
                    or not bounded(row['max_snapshot_bytes'],1) or not bounded(row['host_memory_budget_bytes'],1)
                    or row['no_competing_audit'] is not True or type(cgroup)!=str or not 1<len(cgroup)<=256
                    or not cgroup.isascii() or any(ord(c)<33 for c in cgroup)
                    or PurePosixPath(cgroup).as_posix()!=cgroup or not cgroup.startswith('/')
                    or '..' in PurePosixPath(cgroup).parts):raise ValueError()
            seen.add(identity)
            result.append(AdmittedStore(path=inventory.paths[identity],**row))
        return tuple(result)
    except (ValueError,TypeError,KeyError,RecursionError):
        raise AuditError('resource_unqualified') from None


def load_qualifications(path,inventory,run_id):
    path=Path(path)
    if not path.is_absolute():raise AuditError('resource_unqualified')
    for parent in (path.parent,*path.parent.parents):
        info=parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid!=0 or info.st_mode & 0o022:
            raise AuditError('resource_unqualified')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        info=os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode & 0o022
                or info.st_nlink!=1 or info.st_size>32768):raise AuditError('resource_unqualified')
        raw=os.read(fd,32769)
        return parse_qualifications(raw,inventory,run_id)
    finally:os.close(fd)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('run-once','status'))
    parser.add_argument('--port',type=int,help='Explicit qualified override; otherwise SAME get_settings port as portal')
    waiting=parser.add_mutually_exclusive_group()
    waiting.add_argument('--wait-ready-seconds',type=int,default=0,help='Optional finite MANUAL retry; default is fail-fast')
    waiting.add_argument('--wait-until-ready-or-cancelled',action='store_true',help='Automatic oneshot: no elapsed/attempt ceiling')
    parser.add_argument('--journal-dir',default='/run/captiveportal-unified-sqlite-audit')
    parser.add_argument('--qualifications',help='Explicit root-owned CURRENT-run owner/SysAdmin attestation; optional')
    args=parser.parse_args(argv)
    from app.settings import get_settings
    settings=get_settings()
    if not enabled(settings):
        print(json.dumps(project(catalog())))
        return 0  # No directory/stat/probe/inventory/process/journal work on OFF.
    try:
        port=settings['port'] if args.port is None else args.port
        if type(port) is not int or not 1<=port<=65535:raise AuditError('ready_unproven')
        journal=OutcomeJournal(args.journal_dir)
        if args.command=='status':
            try:current_run=probe(port).portal_run_id
            except AuditError:current_run=None
            print(json.dumps(UnifiedSqliteAuditReadService(catalog(True),journal=journal,portal_run_id=current_run).snapshot()))
            return 0
        cancelled=False
        def stop(_signum,_frame):
            nonlocal cancelled
            cancelled=True
        old={s:signal.signal(s,stop) for s in (signal.SIGTERM,signal.SIGINT)}
        try:
            ready=wait_ready(port,args.wait_ready_seconds,
                until_cancelled=args.wait_until_ready_or_cancelled,cancelled=lambda:cancelled)
            try:inventory=load_inventory()
            except (OSError,ValueError):inventory=None
            qualifications=()
            if args.qualifications and inventory is not None:
                qualifications=load_qualifications(args.qualifications,inventory,ready.portal_run_id)
            value=AuditCycleRunner(journal,inventory_loader=lambda:inventory if inventory is not None else load_inventory(),
                cancelled=lambda:cancelled).run_once(ready.portal_run_id,QualifiedManifest(ready,qualifications))
        finally:
            for signum,handler in old.items():signal.signal(signum,handler)
        print(json.dumps(value))
        return 0 if value['cycle_state'] in {'COMPLETE','PARTIAL'} else 2
    except (OSError,AuditError,ValueError):
        # Do not print OS/SQLite exceptions, private paths or qualification content.
        print('{"api_version":"audit.unified.v1","error":"audit_unavailable"}')
        return 2


if __name__=='__main__':
    raise SystemExit(main())
