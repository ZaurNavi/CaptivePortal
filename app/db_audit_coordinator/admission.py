"""G1 interfaces deny production. Fixture qualification is explicitly not LAB admission."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tempfile

from .contracts import CoordinatorError, integer
from .locks import protected_parent, trusted_open


class Admission:
    def envelope(self,job):
        raise CoordinatorError("not_admitted")


class CompletionFence:
    def released(self,job,process=None):
        return False

    def exitcode(self,job,process=None):
        return None


class FilesystemAdmission:
    def validate(self,root,uid):
        raise CoordinatorError("not_admitted")


class FixtureFilesystem(FilesystemAdmission):
    """Explicit disposable-root qualification, NOT an operational FS attestation."""
    def validate(self,root,uid):
        path=Path(root)
        temporary=Path(tempfile.gettempdir()).resolve()
        if not path.is_absolute() or temporary not in path.parents:
            raise CoordinatorError("not_admitted")
        protected_parent(path/"queue-state.v1.json",uid)


@dataclass(frozen=True)
class FixturePlan:
    root: str
    mode: str = "pass"
    timeout_seconds: int = 3

    def validate(self,uid):
        integer(self.timeout_seconds,10)
        if self.timeout_seconds<1 or self.mode not in {"pass","fail","crash","hold_preflight","hold_audit","timeout","crash_before_status_sync","crash_after_status_sync"}:
            raise CoordinatorError("not_admitted")
        path=Path(self.root)
        # G1 cannot be pointed at a configured application store, even privately.
        temporary=Path(tempfile.gettempdir()).resolve()
        if not path.is_absolute() or temporary not in path.parents or path==temporary:
            raise CoordinatorError("not_admitted")
        protected_parent(path/"fixture.marker",uid)
        for name in ("fixture.marker","source.sentinel"):
            descriptor=trusted_open(path/name,uid)
            try:
                if os.fstat(descriptor).st_size>4096:raise CoordinatorError("not_admitted")
            finally:os.close(descriptor)
        return self


class FixtureAdmission(Admission):
    def __init__(self,plan,uid):self.plan=plan
    def envelope(self,job):
        return dict(fixture_only=True,memory_limit_bytes=64*1024**2,timeout_seconds=self.plan.timeout_seconds)


class FixtureCompletionFence(CompletionFence):
    """Sufficient ONLY for the built-in tiny, no-grandchild sentinel operation.

    Existing child Popen.wait returncode is positive reap proof, not PID absence
    or TTL. Restart receipts may only be populated after actual waitpid by the
    fixture supervisor; there is no production cgroup qualification here.
    """
    def __init__(self):self.reaped={}
    def released(self,job,process=None):
        if process is not None:
            if process.pid!=job["worker_pid"] or process.returncode is None:return False
            if process.wait(timeout=0)!=process.returncode:return False
            return True
        return job["worker_pid"] in self.reaped and self.reaped[job["worker_pid"]][0]==job["attempt_id"]

    def exitcode(self,job,process=None):
        return process.returncode if process is not None else self.reaped.get(job["worker_pid"],(None,None))[1]
