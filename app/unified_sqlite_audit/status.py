"""One bounded protected outcome journal; writes occur only at state transitions."""
from contextlib import contextmanager
import copy
import json
import os
from pathlib import Path
import stat
import uuid

from .model import AuditError, LIMIT, catalog, project, validate


def _directory(path):
    path = Path(path)
    if not path.is_absolute():raise AuditError('journal_invalid')
    for current in (path, *path.parents):
        info = current.lstat()
        sticky_root = current != path and info.st_uid == 0 and bool(info.st_mode & stat.S_ISVTX)
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid not in {0,os.geteuid()}
                or info.st_mode & 0o022 and not sticky_root):
            raise AuditError('journal_invalid')
    return path


class OutcomeJournal:
    """Directory must be provisioned explicitly; never creates source/other dirs."""
    def __init__(self, directory):
        self.directory = _directory(directory)
        self.path = self.directory / 'outcome.json'

    @contextmanager
    def claim(self):
        import fcntl
        _directory(self.directory)
        fd = os.open(self.directory/'cycle.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        try:
            self._safe(fd)
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                yield False  # Read existing cycle only; never wait/enqueue a second job.
                return
            yield True  # Global heavy fence, including releases.
        finally:
            os.close(fd)

    @staticmethod
    def _safe(fd):
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_uid != os.geteuid() or info.st_mode & 0o077):
            raise AuditError('journal_invalid')

    def read(self):
        _directory(self.directory)
        try:
            fd = os.open(self.path,os.O_RDONLY|os.O_NOFOLLOW)
        except FileNotFoundError:
            return None
        try:
            self._safe(fd)
            with os.fdopen(fd,'rb',closefd=False) as stream:
                raw = stream.read(LIMIT+1)
            if len(raw)>LIMIT:raise AuditError('journal_invalid')
            def closed(pairs):
                result={}
                for key,value in pairs:
                    if key in result:raise AuditError('journal_invalid')
                    result[key]=value
                return result
            envelope=json.loads(raw,object_pairs_hook=closed)
            if (type(envelope)!=dict or set(envelope)!={'version','executor','status'}
                    or envelope['version']!='audit.journal.v1'):raise AuditError('journal_invalid')
            owner=envelope['executor']
            if (type(owner)!=dict or set(owner)!={'pid','start','boot'} or type(owner['pid'])!=int
                    or owner['pid']<=0 or type(owner['start'])!=str or not owner['start'].isdigit()
                    or type(owner['boot'])!=str or len(owner['boot'])!=36):raise AuditError('journal_invalid')
            value=validate(envelope['status'])
            if value['cycle_state']=='RUNNING':
                from .readiness import process_identity
                try:alive=process_identity(owner['pid'])==(owner['start'],owner['boot'])
                except (OSError,ValueError,IndexError):alive=False
                if not alive:
                    value.update(cycle_state='ORPHAN_HOLD',reason='release_unproven')
                    for row in value['stores']:
                        if row['deep']['state']=='RUNNING':
                            row['deep'].update(state='ORPHAN_HOLD',physical_verdict='INCOMPLETE',
                                domain_verdict='INCOMPLETE',reason='release_unproven')
                    value=project(value)
            return value
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
            raise AuditError('journal_invalid') from None
        finally:
            os.close(fd)

    def write(self,value):
        value = project(value)
        from .readiness import process_identity
        start,boot=process_identity(os.getpid())
        envelope=dict(version='audit.journal.v1',executor=dict(pid=os.getpid(),start=start,boot=boot),status=value)
        raw = json.dumps(envelope,allow_nan=False,separators=(',',':')).encode()
        if len(raw)>LIMIT:raise AuditError('journal_invalid')
        _directory(self.directory)
        temporary = self.directory / ('.outcome-'+str(uuid.uuid4()))
        fd = os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:
            with os.fdopen(fd,'wb',closefd=False) as stream:
                stream.write(raw);stream.flush();os.fsync(fd)
            os.replace(temporary,self.path)
            directory_fd = os.open(self.directory,os.O_DIRECTORY|os.O_NOFOLLOW)
            try:os.fsync(directory_fd)
            finally:os.close(directory_fd)
        finally:
            os.close(fd)
            try:temporary.unlink()
            except FileNotFoundError:pass


class UnifiedSqliteAuditReadService:
    """The only public projection. No source DB, discovery or worker on reads."""
    def __init__(self, initial=None, *, journal=None, portal_run_id=None):
        self.initial = copy.deepcopy(initial if initial is not None else catalog())
        self.journal = journal
        self.portal_run_id = portal_run_id

    def snapshot(self):
        value = copy.deepcopy(self.initial)
        if self.journal is not None:
            try:
                saved = self.journal.read()
                if saved is not None:value=saved
            except (OSError,AuditError,TypeError,KeyError):
                value=catalog(True,portal_run_id=self.portal_run_id)
                value.update(cycle_state='BLOCKED',reason='journal_invalid')
        if (self.portal_run_id is not None and value['portal_run_id'] != self.portal_run_id
                or self.journal is not None and self.portal_run_id is None and value['audit_cycle_id'] is not None):
            # Historical proof is never current assurance after a portal restart.
            for row in value['stores']:
                row['freshness']='HISTORICAL'
                row['deep'].update(state='STALE',physical_verdict='STALE',domain_verdict='STALE',reason='source_changed')
            value.update(cycle_state='INTERRUPTED',reason='prior_incomplete')
        elif value['cycle_state']=='RUNNING':
            # Readers do not invent completion or promote provisional results.
            pass
        return project(value)
