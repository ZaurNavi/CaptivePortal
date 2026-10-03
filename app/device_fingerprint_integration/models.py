"""Immutable relation-only Task-05 contracts."""

from dataclasses import dataclass
from typing import TYPE_CHECKING
from datetime import datetime, timezone, timedelta
import uuid
from app.device_fingerprint.artifact_content import ArtifactRef
if TYPE_CHECKING:
    from app.device_fingerprint.classification_read import ClassificationReadRecord

from app.device_fingerprint.validation import (
    format_utc, parse_utc, validate_mac, validate_site_id, validate_uuid,
)

SCHEMA_VERSION = 1
PRE_AUTH_LOOKBACK_SECONDS = 300
POST_AUTH_EVIDENCE_SECONDS = 120
INGEST_GRACE_SECONDS = 30
LEASE_SECONDS = 300
MAX_ATTEMPTS = 5
RETRY_DELAYS = (30, 120, 300, 600)
IDENTITY_RETRY_SECONDS = 30
IDENTITY_HORIZON_SECONDS = 3600


class IntegrationError(RuntimeError):
    def __init__(self, reason_code):
        self.reason_code = reason_code
        super().__init__(reason_code)


def uuid4(value):
    canonical = validate_uuid(value)
    if uuid.UUID(canonical).version != 4:
        raise ValueError("Invalid canonical UUIDv4")
    return canonical


def utc_now():
    return format_utc(datetime.now(timezone.utc))


def plus(timestamp, seconds):
    return format_utc(parse_utc(timestamp) + timedelta(seconds=seconds))


@dataclass(frozen=True)
class AuthorizedFingerprintRequest:
    auth_session_id: str
    auth_run_number: int
    site_id: str
    observed_mac: str
    authorized_at_utc: str

    def __post_init__(self):
        validate_uuid(self.auth_session_id)
        validate_site_id(self.site_id)
        if validate_mac(self.observed_mac) != self.observed_mac:
            raise ValueError("Noncanonical MAC")
        parse_utc(self.authorized_at_utc)
        if type(self.auth_run_number) is not int or not 1 <= self.auth_run_number < 2**63:
            raise ValueError("Invalid AuthRun number")


@dataclass(frozen=True)
class IntegrationJob:
    integration_id: str
    auth_session_id: str
    auth_run_number: int
    site_id: str
    observed_mac: str
    authorized_at_utc: str
    planned_classification_id: str
    due_at_utc: str
    classification_state: str
    attempt_count: int
    next_attempt_at_utc: str
    lease_token: str | None
    lease_until_utc: str | None
    effective_window_start_utc: str | None
    effective_window_end_utc: str | None
    classification_id: str | None
    classification_result_id: str | None
    last_reason_code: str | None
    registry_snapshot_id: str | None
    device_id: str | None
    visit_id: str | None
    identity_state: str
    identity_reason: str | None
    identity_last_attempt_at_utc: str | None
    created_at_utc: str
    updated_at_utc: str

    def __post_init__(self):
        AuthorizedFingerprintRequest(self.auth_session_id, self.auth_run_number, self.site_id,
                                     self.observed_mac, self.authorized_at_utc)
        uuid4(self.integration_id)
        uuid4(self.planned_classification_id)
        for value in (self.due_at_utc, self.next_attempt_at_utc, self.created_at_utc,
                      self.updated_at_utc, self.lease_until_utc, self.effective_window_start_utc,
                      self.effective_window_end_utc, self.identity_last_attempt_at_utc):
            if value is not None:
                parse_utc(value)
        if self.due_at_utc != plus(self.authorized_at_utc, 150):
            raise ValueError("Invalid fixed due time")
        if self.classification_state not in {"PENDING", "LEASED", "CLASSIFIED", "NO_RESULT_FINAL"}:
            raise ValueError("Invalid job state")
        if self.identity_state not in {"UNRESOLVED", "DEVICE_RESOLVED", "DEVICE_AND_VISIT_RESOLVED", "CONFLICT"}:
            raise ValueError("Invalid identity state")
        if type(self.attempt_count) is not int or not 0 <= self.attempt_count <= MAX_ATTEMPTS:
            raise ValueError("Invalid attempt count")
        if self.classification_id is not None and self.classification_id != self.planned_classification_id:
            raise ValueError("Classification identity mismatch")
        for identity in (self.registry_snapshot_id, self.device_id, self.visit_id):
            if identity is not None:
                validate_uuid(identity)
        if self.classification_state == "CLASSIFIED":
            if self.classification_id is None or self.classification_result_id is None:
                raise ValueError("Missing retained classification link")
            parts = self.classification_result_id.split(":")
            if len(parts) != 4 or parts[:3] != ["ClassificationResult", "v1", "sha256"]:
                raise ValueError("Invalid result reference")
            ArtifactRef(self.classification_result_id, parts[3])
            if self.effective_window_start_utc is None or self.effective_window_end_utc is None:
                raise ValueError("Missing effective window")
        if self.effective_window_end_utc is not None:
            if (self.effective_window_end_utc != plus(self.authorized_at_utc, 120)
                    or self.effective_window_start_utc is None
                    or self.effective_window_start_utc >= self.effective_window_end_utc
                    or self.effective_window_start_utc < plus(self.authorized_at_utc, -300)):
                raise ValueError("Invalid fixed classification window")
        if self.identity_state in {"DEVICE_RESOLVED", "DEVICE_AND_VISIT_RESOLVED"}:
            if self.registry_snapshot_id is None or self.device_id is None:
                raise ValueError("Missing exact identity anchors")
            if self.identity_state == "DEVICE_AND_VISIT_RESOLVED" and self.visit_id is None:
                raise ValueError("Missing exact Visit anchor")
        if self.lease_token is not None:
            uuid4(self.lease_token)
        if (self.classification_state == "LEASED") != (self.lease_token is not None and self.lease_until_utc is not None):
            raise ValueError("Invalid lease")


@dataclass(frozen=True)
class IdentityResolution:
    state: str = "UNRESOLVED"
    reason: str | None = None
    snapshot_id: str | None = None
    device_id: str | None = None
    visit_id: str | None = None


@dataclass(frozen=True)
class IntegratedFingerprintRecord:
    site_id: str
    device_id: str | None
    observed_mac: str
    auth_session_id: str
    auth_run_number: int
    registry_snapshot_id: str | None
    visit_id: str | None
    identity_state: str
    classification_id: str
    classification_result: "ClassificationReadRecord"
    authorized_at_utc: str
