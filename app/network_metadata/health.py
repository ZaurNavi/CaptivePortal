"""Immutable local health snapshots and the one admitted Fingerprint read adapter."""
import copy
import json
import os
import uuid

from app.device_fingerprint.read_service import DeviceFingerprintReadService
from app.device_fingerprint.validation import format_utc, parse_utc
from .models import NetworkMetadataSourceHealthV1, CONFLICT_CATEGORIES
from .validation import ni_timestamp

ACQUISITION_REASONS = frozenset({"capture_interface_unavailable", "raw_parser_unavailable",
                               "suricata_unavailable", "eve_datagram_truncated"})
CAPTURE_REASONS = ACQUISITION_REASONS | {"capture_health_read_unavailable"}
FILTERS = frozenset({"pre_binding_event", "outside_intended_scope", "unsupported_address_family_for_scope",
                     "retention_expired_event"})


class FingerprintCaptureHealthAdapterV1:
    def __init__(self, db_path=None, *, reader=None):
        try:
            self.reader = reader if reader is not None else DeviceFingerprintReadService(
                db_path or os.environ.get("DEVICE_FINGERPRINT_DB_PATH", "/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3"),
                retention_days=30)
        except Exception:
            self.reader = None

    def evaluate(self, binding, now):
        try:
            rows, ages = [], []
            for kind in ("tls_client", "quic_client"):
                row = self.reader.latest_source_health(binding.site_id, binding.capture_source_id, kind,
                                                       through_utc=format_utc(now))
                rows.append(row)
                ages.append((now - parse_utc(row["observed_at"])).total_seconds() if row is not None else None)
            if any(age is not None and age < 0 for age in ages):
                return "unknown", ()
            reasons = sorted({row["reason_code"] for row, age in zip(rows, ages)
                if row is not None and 0 <= age <= 600 and row["status"] == "unavailable"
                and row["reason_code"] in ACQUISITION_REASONS})
            if reasons:
                return "unavailable", tuple(reasons)
            if all(row is not None and 0 <= age <= 600 and row["status"] == "available"
                   and row["reason_code"] is None for row, age in zip(rows, ages)):
                return "usable", ()
            if all(age is not None and age > 600 for age in ages):
                return "stale", ()
            return "unknown", ()
        except Exception:
            return "unknown", ("capture_health_read_unavailable",)


class HealthController:
    def __init__(self, capture_source_id):
        self.capture_source_id = capture_source_id
        self.capture = self.output = self.ingest = "unknown"
        self.capture_reasons, self.local_reasons = (), set()
        self.last_output = self.last_ingested = self.committed_offset = None
        self.last_snapshot = None
        self.fault_since_heartbeat = False
        self.last_heartbeat = None

    def copy(self):
        return copy.deepcopy(self)

    def adopt(self, candidate):
        self.__dict__.update(candidate.__dict__)

    def reload(self, repository):
        row = repository.latest_health(self.capture_source_id)
        if row is None:
            return
        self.last_snapshot = NetworkMetadataSourceHealthV1(
            **{key: row[key] for key in row.keys() if key != "reason_codes_json"},
            reason_codes=tuple(json.loads(row["reason_codes_json"])))
        self.last_output, self.last_ingested = row["last_output_event_at"], row["last_ingested_event_at"]
        self.committed_offset = row["committed_byte_offset"]
        self.capture, self.output, self.ingest = row["capture_health"], row["metadata_output_health"], row["metadata_ingest_health"]
        reasons = set(self.last_snapshot.reason_codes)
        self.capture_reasons = tuple(sorted(reasons & CAPTURE_REASONS))
        self.local_reasons = reasons - CAPTURE_REASONS
        self.fault_since_heartbeat = False

    def set_capture(self, state, reasons):
        self.capture, self.capture_reasons = state, reasons

    def source_available(self, *, gap=False):
        self.local_reasons.discard("source_absent")
        self.local_reasons.discard("source_unavailable")
        if gap:
            self.local_reasons.add("source_continuity_mismatch")
            self.fault_since_heartbeat = True
        # Restored local fault evidence is not erased by descriptor recovery.
        if self.local_reasons:
            self.output = "partial"
            self.ingest = "usable" if self.local_reasons == {"source_continuity_mismatch"} else "partial"
        else:
            self.output = self.ingest = "usable"

    def unavailable(self, reason, *, source=False):
        self.ingest = "unavailable"
        if source:
            self.output = "unavailable"
        self.local_reasons.add(reason)

    def block(self, reason):
        if reason not in CONFLICT_CATEGORIES:
            raise ValueError("Invalid blocked category")
        self.output = self.ingest = "unavailable"
        self.local_reasons = {reason}

    def observe_output_time(self, event_at):
        if event_at is not None and (self.last_output is None
                or ni_timestamp(event_at, canonical=True) > ni_timestamp(self.last_output, canonical=True)):
            self.last_output = event_at

    def observe_source(self, outcome):
        self.observe_output_time(outcome.output_event_at)
        if outcome.normalized is None and outcome.category not in FILTERS:
            self.output = self.ingest = "partial"
            self.local_reasons.add(outcome.category)
            self.fault_since_heartbeat = True

    def observation_committed(self, event_at):
        if self.last_ingested is None or ni_timestamp(event_at, canonical=True) > ni_timestamp(self.last_ingested, canonical=True):
            self.last_ingested = event_at

    def heartbeat(self, *, source_available, store_operational=True, blocked_reason=None):
        if blocked_reason:
            self.block(blocked_reason)
        elif source_available and store_operational:
            if not self.fault_since_heartbeat:
                self.output = self.ingest = "usable"
                self.local_reasons.clear()
        self.fault_since_heartbeat = False

    def ensure(self, repository, generation, now, *, force=False):
        generation_id = generation.source_generation_id if generation else None
        reasons = tuple(sorted(set(self.capture_reasons) | self.local_reasons))
        key = (generation_id, self.capture, self.output, self.ingest, reasons)
        old = self.last_snapshot
        old_key = (old.source_generation_id, old.capture_health, old.metadata_output_health,
                   old.metadata_ingest_health, old.reason_codes) if old else None
        due = old is None or (ni_timestamp(now) - ni_timestamp(old.evaluated_at)).total_seconds() >= 60
        if force or due or key != old_key:
            snapshot = NetworkMetadataSourceHealthV1(str(uuid.uuid4()), now, self.capture_source_id,
                generation_id, self.capture, self.output, self.ingest, self.last_output,
                self.last_ingested, self.committed_offset, reasons)
            repository.insert_health(snapshot)
            self.last_snapshot = snapshot
        return self.last_snapshot.health_id
