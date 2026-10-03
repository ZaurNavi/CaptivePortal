"""Normal Task-04 production assembly/persistence; relation-only crash recovery."""

from pathlib import Path
import os

from app.device_fingerprint.request_assembly import DeviceFingerprintRequestAssembly
from .compatibility import preflight, same_pin, ExactPinStore
from .models import IntegrationError, plus, parse_utc


def process_memory_guard(limit):
    try:
        if type(limit) is not int or limit <= 0:
            return False
        resident_pages = int(Path("/proc/self/statm").read_text(encoding="ascii").split()[1])
        page_size = os.sysconf("SC_PAGE_SIZE")
        return resident_pages >= 0 and page_size > 0 and resident_pages * page_size <= limit
    except (OSError, ValueError, IndexError, AttributeError):
        return False


class ClassificationExecutor:
    def __init__(self, control, evidence_read, classification_store, classification_read, *, clock,
                 preflight_fn=preflight, assembly_factory=DeviceFingerprintRequestAssembly,
                 memory_guard=process_memory_guard):
        self.control, self.evidence_read = control, evidence_read
        self.persistence, self.read = classification_store, classification_read
        self.clock, self.preflight = clock, preflight_fn
        self.assembly_factory, self.memory_guard = assembly_factory, memory_guard

    def execute(self, job, *, recovery_only=False):
        previous = self.read.get_by_id(job.planned_classification_id)
        if previous is not None:
            core = previous.core
            if (core.site_id, core.observed_mac, core.execution_context) != (
                    job.site_id, job.observed_mac, "PRODUCTION"):
                raise IntegrationError("classification_identity_conflict")
            record = self.persistence.load_artifact(core.snapshot_record_id, core.snapshot_record_digest)
            ref = record.semantic_payload["evidence_snapshot_content"]
            snapshot = self.persistence.load_artifact(ref["artifact_id"], ref["content_sha256"]).semantic_payload
            if (snapshot["site_id"], snapshot["observed_mac"], snapshot["window_end_utc"]) != (
                    job.site_id, job.observed_mac, plus(job.authorized_at_utc, 120)):
                raise IntegrationError("classification_identity_conflict")
            return core, snapshot["window_start_utc"], snapshot["window_end_utc"]
        if recovery_only:
            raise IntegrationError(job.last_reason_code or "integration_unavailable")
        prepared = self.preflight(self.control)
        end = plus(job.authorized_at_utc, 120)
        start = max(plus(job.authorized_at_utc, -300), prepared.contents[1].semantic_payload[
            "classification_foundation_valid_from_utc"])
        if parse_utc(start) >= parse_utc(end):
            raise IntegrationError("integration_window_not_authoritative")
        assembly = self.assembly_factory(
            control_plane_store=ExactPinStore(self.control, prepared.pin), read_service=self.evidence_read,
            compatibility_hook=prepared.hook, utc_clock=self.clock, process_memory_guard=self.memory_guard)
        try:
            result = assembly.assemble_production(job.site_id, job.observed_mac, start, end)
            if not same_pin(result.pinned_runtime_profile, prepared.pin):
                raise IntegrationError("runtime_profile_incompatible")
        except Exception as exc:
            if getattr(exc, "reason_code", None) == "runtime_profile_incompatible":
                changed = not same_pin(self.control.pin_active_profile("classification"), prepared.pin)
                raise IntegrationError("profile_changed_during_job" if changed else "runtime_profile_incompatible") from exc
            raise
        core = self.persistence.persist(result, retention_policy=prepared.retention,
                                        classification_id=job.planned_classification_id)
        return core, start, end
