"""Auth-facing enqueue only; never import or invoke classification machinery."""

import logging
import json
from typing import Protocol

from .models import utc_now

logger = logging.getLogger("captivportal.fingerprint.integration")
_TELEMETRY_FIELDS = frozenset({
    "integration_id", "site_id", "observed_mac", "auth_session_id", "auth_run_number",
    "classification_id", "device_id", "visit_id", "reason_code", "attempt_count",
})


def emit(event, **fields):
    # No exception messages, raw controller/evidence objects or result bodies.
    try:
        safe = {key: value for key, value in fields.items() if key in _TELEMETRY_FIELDS}
        logger.info(json.dumps({"event": event, **safe}, sort_keys=True, separators=(",", ":")))
    except Exception:
        pass


class FingerprintIntegrationSubmitter(Protocol):
    def submit_authorized(self, request): ...


class _DisabledSubmitter:
    def submit_authorized(self, request):
        return None


DISABLED_FINGERPRINT_INTEGRATION_SUBMITTER = _DisabledSubmitter()


class DurableFingerprintIntegrationSubmitter:
    def __init__(self, repository, *, clock=utc_now):
        self.repository, self.clock = repository, clock

    def submit_authorized(self, request):
        identity, inserted = self.repository.enqueue(request, self.clock())
        emit("fingerprint.integration_job_queued" if inserted else "fingerprint.integration_job_duplicate",
             integration_id=identity, site_id=request.site_id, observed_mac=request.observed_mac,
             auth_session_id=request.auth_session_id, auth_run_number=request.auth_run_number)
        return identity
