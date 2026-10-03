"""Single logical consumer, durable leases and bounded independent identity retries."""

from contextlib import contextmanager
import os
import threading

from .models import (IntegrationError, IdentityResolution, MAX_ATTEMPTS, RETRY_DELAYS,
                     plus, utc_now)
from .submitter import emit

RETRYABLE = frozenset({"retryable_sqlite_busy", "snapshot_timeout", "snapshot_memory_pressure",
                      "knowledge_bundle_unavailable", "activation_lineage_unavailable",
                      "persistence_unavailable", "profile_changed_during_job", "integration_unavailable"})


@contextmanager
def consumer_lock(path):
    """Kernel-released on crash; expired DB lease cannot overlap a live consumer."""
    with open(str(path) + ".consumer.lock", "a+b") as handle:
        acquired = False
        try:
            if os.name == "posix":
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                import msvcrt
                handle.seek(0)
                if not handle.read(1):
                    handle.write(b"0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            acquired = True
        except OSError:
            pass
        try:
            yield acquired
        finally:
            if acquired:
                if os.name == "posix":
                    fcntl.flock(handle, fcntl.LOCK_UN)
                else:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


class IntegrationWorker:
    def __init__(self, repository, executor, identity_resolver, *, clock=utc_now):
        self.repository, self.executor, self.resolver = repository, executor, identity_resolver
        self.clock, self.stop_event = clock, threading.Event()

    def run_once(self):
        with consumer_lock(self.repository.path) as acquired:
            if not acquired:
                return False
            claimed = self.repository.claim(self.clock())
            if claimed is not None:
                job, recovery_only = claimed
                emit("fingerprint.integration_classification_started", integration_id=job.integration_id,
                     attempt_count=job.attempt_count)
                try:
                    core, start, end = self.executor.execute(job, recovery_only=recovery_only)
                except Exception as exc:
                    reason = getattr(exc, "reason_code", None) or "integration_unavailable"
                    completed_at = self.clock()
                    retry = reason in RETRYABLE and job.attempt_count < MAX_ATTEMPTS
                    conflict = reason in {"classification_identity_conflict", "integration_identity_conflict"}
                    saved = self.repository.finish(job, completed_at, state="PENDING" if retry else "NO_RESULT_FINAL",
                        reason=reason, retry_at=plus(completed_at, RETRY_DELAYS[job.attempt_count - 1]) if retry else None,
                        identity_conflict=conflict)
                    if saved:
                        emit("fingerprint.integration_classification_retry" if retry else "fingerprint.integration_classification_no_result",
                             integration_id=job.integration_id, reason_code=reason, attempt_count=job.attempt_count)
                    else:
                        emit("fingerprint.integration_worker_health", integration_id=job.integration_id,
                             reason_code="lease_lost")
                else:
                    # Failure here leaves a durable lease; restart reads planned ID before assembly.
                    if self.repository.finish(job, self.clock(), state="CLASSIFIED", core=core, start=start, end=end):
                        emit("fingerprint.integration_classification_succeeded", integration_id=job.integration_id,
                             classification_id=core.classification_id)
            identity_job = self.repository.identity_due(self.clock())
            if identity_job is not None:
                now = self.clock()
                if now >= plus(identity_job.authorized_at_utc, 3600):
                    resolution = IdentityResolution(identity_job.identity_state, "identity_proof_unavailable",
                        identity_job.registry_snapshot_id, identity_job.device_id, identity_job.visit_id)
                else:
                    try:
                        resolution = self.resolver.resolve(identity_job)
                    except Exception:
                        resolution = IdentityResolution(identity_job.identity_state, "identity_proof_unavailable",
                            identity_job.registry_snapshot_id, identity_job.device_id, identity_job.visit_id)
                self.repository.save_identity(identity_job, resolution, now)
                if resolution.state != "UNRESOLVED":
                    emit("fingerprint.integration_identity_conflict" if resolution.state == "CONFLICT"
                         else "fingerprint.integration_identity_resolved", integration_id=identity_job.integration_id,
                         device_id=resolution.device_id, visit_id=resolution.visit_id, reason_code=resolution.reason)
            return claimed is not None or identity_job is not None

    def run(self):
        while not self.stop_event.is_set():
            try:
                self.run_once()
                emit("fingerprint.integration_worker_health", reason_code="ready")
            except Exception:
                emit("fingerprint.integration_worker_health", reason_code="integration_unavailable")
            self.stop_event.wait(1)

    def stop(self):
        self.stop_event.set()
