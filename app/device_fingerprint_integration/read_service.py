"""Internal Task-06-ready typed reads; Task-04 is the only result authority."""

from app.device_fingerprint.validation import validate_site_id, validate_uuid
from .models import IntegrationError, IntegratedFingerprintRecord


class FingerprintIntegrationReadService:
    def __init__(self, repository, classification_read):
        self.repository, self.classifications = repository, classification_read

    def _record(self, job):
        if job is None or job.classification_state != "CLASSIFIED":
            return None
        result = self.classifications.get_by_id(job.classification_id)
        if result is None:
            return None  # Task-04 retention may have legitimately removed it.
        if (result.core.site_id, result.core.observed_mac, result.core.classification_result_id) != (
                job.site_id, job.observed_mac, job.classification_result_id):
            raise IntegrationError("classification_identity_conflict")
        return IntegratedFingerprintRecord(job.site_id, job.device_id, job.observed_mac,
            job.auth_session_id, job.auth_run_number, job.registry_snapshot_id, job.visit_id,
            job.identity_state, job.classification_id, result, job.authorized_at_utc)

    def get_current_for_device(self, site_id, device_id):
        return self._record(self.repository.current_for_device(validate_site_id(site_id), validate_uuid(device_id)))

    def get_for_auth_run(self, site_id, auth_session_id, auth_run_number):
        if type(auth_run_number) is not int or auth_run_number < 1:
            raise ValueError("Invalid AuthRun")
        return self._record(self.repository.for_auth_run(validate_site_id(site_id),
                                                       validate_uuid(auth_session_id), auth_run_number))
