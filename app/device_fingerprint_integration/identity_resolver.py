"""Only exact Site-qualified Registry and Visit read boundaries confer identity."""

from app.device_fingerprint.validation import validate_uuid
from .models import IdentityResolution, plus


class ExactIdentityResolver:
    def __init__(self, registry_read, visit_read):
        self.registry = registry_read
        self.visits = visit_read

    def resolve(self, job):
        snapshot = self.registry.get_snapshot_by_auth_session(
            job.auth_session_id, site_id=job.site_id, client_mac=job.observed_mac)
        if snapshot is None:
            # Do not downgrade a previously exact durable relation when a read is absent.
            return IdentityResolution(job.identity_state, "identity_proof_unavailable",
                                      job.registry_snapshot_id, job.device_id, job.visit_id)
        if (snapshot["site_id"], snapshot["auth_session_id"], snapshot["requested_mac"]) != (
                job.site_id, job.auth_session_id, job.observed_mac):
            return IdentityResolution("CONFLICT", "registry_relation_mismatch",
                                      job.registry_snapshot_id, job.device_id, job.visit_id)
        device = validate_uuid(snapshot["device_id"])
        snapshot_id = validate_uuid(snapshot["snapshot_id"])
        if job.device_id is not None and job.device_id != device:
            return IdentityResolution("CONFLICT", "identity_device_conflict",
                                      job.registry_snapshot_id, job.device_id, job.visit_id)
        # Preserve the original exact snapshot anchor; do not overwrite immutable facts.
        snapshot_id = job.registry_snapshot_id or snapshot_id
        visit = self.visits.get_open_visit(job.site_id, job.observed_mac)
        def matches(visit):
            return visit is not None and (visit.site_id, visit.client_mac,
                visit.start_auth_session_id, visit.start_auth_run_number) == (
                job.site_id, job.observed_mac, job.auth_session_id, job.auth_run_number)
        if matches(visit):
            candidates = [visit]
        else:
            # Fixed range and one bounded page; no nearest-timestamp/global scan.
            page = self.visits.list_visits(job.site_id, plus(job.authorized_at_utc, -3600),
                                          plus(job.authorized_at_utc, 3600),
                                          client_mac=job.observed_mac, limit=100)
            candidates = page.items
        exact = {visit.visit_id: visit for visit in candidates if (
            visit.site_id == job.site_id and visit.client_mac == job.observed_mac
            and visit.start_auth_session_id == job.auth_session_id
            and visit.start_auth_run_number == job.auth_run_number)}
        if len(exact) > 1:
            return IdentityResolution("CONFLICT", "identity_visit_conflict", snapshot_id, device, job.visit_id)
        visit = next(iter(exact.values()), None)
        if visit is not None:
            validate_uuid(visit.visit_id)
            if visit.device_id is not None and visit.device_id != device:
                return IdentityResolution("CONFLICT", "identity_device_conflict", snapshot_id, device, job.visit_id)
            if job.visit_id is not None and job.visit_id != visit.visit_id:
                return IdentityResolution("CONFLICT", "identity_visit_conflict", snapshot_id, device, job.visit_id)
            return IdentityResolution("DEVICE_AND_VISIT_RESOLVED", None, snapshot_id, device, visit.visit_id)
        return IdentityResolution("DEVICE_AND_VISIT_RESOLVED" if job.visit_id else "DEVICE_RESOLVED",
                                  None, snapshot_id, device, job.visit_id)
