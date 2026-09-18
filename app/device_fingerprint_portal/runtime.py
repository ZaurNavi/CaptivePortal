"""Non-blocking portal sink and isolated background delivery runtime."""

from __future__ import annotations

import ipaddress
import queue
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from app.common.mac import format_mac_colon, parse_mac
from app.device_fingerprint.validation import canonical_json, canonical_sha256, format_utc, parse_utc
from app.device_fingerprint.portal_schemas import validate_portal_headers_v1

from .coalescer import PortalEvidenceCoalescer
from .models import DeliveryResult, PortalEvidenceCandidate, PortalEvidenceConfig, QueuedPortalEvidence
from .producer import PortalEvidenceProducer
from .telemetry import PortalEvidenceTelemetry, safe_emit

UTC = timezone.utc
_HEARTBEAT_INTERVAL_SECONDS = 60


class PortalEvidenceRuntime:
    def __init__(self, config: PortalEvidenceConfig, *, producer: Any = None,
                 telemetry: Any = None, monotonic=time.monotonic, now=None,
                 output_queue: queue.Queue[QueuedPortalEvidence] | None = None,
                 coalescer: PortalEvidenceCoalescer | None = None) -> None:
        self.config = config
        self.telemetry = telemetry or PortalEvidenceTelemetry()
        self.monotonic = monotonic
        self.now = now or (lambda: datetime.now(UTC))
        self.queue = output_queue or queue.Queue(maxsize=config.queue_max_events)
        self.coalescer = coalescer or PortalEvidenceCoalescer(
            expiry_seconds=config.coalesce_seconds,
            max_entries=config.coalesce_max_entries,
            monotonic=monotonic,
        )
        self.producer = producer or PortalEvidenceProducer(config)
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.cooldown_until = 0.0
        self.health_state = "unknown"
        self.unavailable_started_at: datetime | None = None
        self.next_heartbeat_at: float | None = None

    def start(self) -> None:
        if self.thread is not None:
            raise RuntimeError("Portal evidence runtime already started")
        if self.config.enabled:
            self.next_heartbeat_at = self.monotonic() + _HEARTBEAT_INTERVAL_SECONDS
        self.thread = threading.Thread(
            target=self._worker_loop,
            name="device-fingerprint-portal",
            daemon=True,
        )
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()

    def try_submit(self, session: Any, candidate: PortalEvidenceCandidate) -> bool:
        try:
            if (
                candidate.source_subtype not in {"omada_external_portal", "capport_login"}
                or candidate.quality_state not in {"valid", "partial"}
            ):
                raise ValueError("invalid portal evidence candidate")
            parse_utc(candidate.observed_at)
            normalized_payload = dict(validate_portal_headers_v1(candidate.payload))
            if session.site_id != self.config.site_id:
                safe_emit(self.telemetry, "portal_evidence_dropped", drop_site_scope=1)
                return False
            if not session.client_mac:
                safe_emit(self.telemetry, "portal_evidence_dropped", drop_missing_mac=1)
                return False
            canonical_mac = format_mac_colon(parse_mac(session.client_mac))
            observed_ip = session.client_ip
            if observed_ip is not None:
                parsed_ip = ipaddress.ip_address(observed_ip)
                if not any(parsed_ip in network for network in self.config.guest_cidrs):
                    safe_emit(self.telemetry, "portal_evidence_dropped", drop_ip_scope=1)
                    return False
                observed_ip = str(parsed_ip)
            if session.ssid is not None and session.ssid not in self.config.allowed_ssids:
                safe_emit(self.telemetry, "portal_evidence_dropped", drop_ssid_scope=1)
                return False
            payload_json = canonical_json(normalized_payload)
            key = (
                session.site_id,
                canonical_mac,
                candidate.source_subtype,
                canonical_sha256(payload_json),
            )

            def item_factory(admitted_at: float) -> QueuedPortalEvidence:
                event = {
                    "source_event_id": str(uuid.uuid4()),
                    "source_kind": "portal_headers",
                    "source_subtype": candidate.source_subtype,
                    "extractor_name": "portal-http-parser",
                    "extractor_version": "1.0.0",
                    "feature_schema_version": 1,
                    "rule_version": None,
                    "site_id": session.site_id,
                    "capture_source_id": self.config.capture_source_id,
                    "observed_at": candidate.observed_at,
                    "observed_mac": canonical_mac,
                    "observed_ip": observed_ip,
                    "quality_state": candidate.quality_state,
                    "payload": normalized_payload,
                }
                return QueuedPortalEvidence(event, key, admitted_at)

            result = self.coalescer.try_admit(key, self.queue, item_factory)
            field = {
                "admitted": "events_queued", "coalesced": "events_coalesced",
                "busy": "drop_coalescer_busy", "full": "drop_queue_full",
            }[result.status]
            safe_emit(self.telemetry, "portal_evidence_admission", **{field: 1})
            return result.status == "admitted"
        except Exception:
            safe_emit(self.telemetry, "portal_evidence_dropped", drop_malformed=1)
            return False

    def process_once(self, *, block: bool = False) -> int:
        try:
            if block:
                timeout = 0.1
                if self.next_heartbeat_at is not None:
                    timeout = min(timeout, max(0.0, self.next_heartbeat_at - self.monotonic()))
                first = self.queue.get(timeout=timeout)
            else:
                first = self.queue.get_nowait()
        except queue.Empty:
            return 0
        items = [first]
        while len(items) < self.config.batch_size:
            try:
                items.append(self.queue.get_nowait())
            except queue.Empty:
                break
        pre_send_now = self.now()
        active: list[QueuedPortalEvidence] = []
        for item in items:
            try:
                age = (pre_send_now - parse_utc(item.event["observed_at"])).total_seconds()
            except Exception:
                age = self.config.queue_max_age_seconds + 1
            if age > self.config.queue_max_age_seconds:
                self.coalescer.remove((item.coalescer_key,))
                safe_emit(self.telemetry, "portal_evidence_dropped", drop_queue_stale=1)
            else:
                active.append(item)
        if not active:
            return len(items)
        current = self.monotonic()
        if current < self.cooldown_until:
            self.coalescer.shorten((item.coalescer_key for item in active), self.cooldown_until)
            return len(items)
        try:
            result = self.producer.deliver_evidence(item.event for item in active)
        except Exception:
            result = DeliveryResult("transient", self.config.transient_cooldown_seconds)
        outcome_now = self.now()
        if result.status == "success":
            safe_emit(self.telemetry, "portal_evidence_delivery", delivery_success=len(active), batch_size=len(active))
            self._evidence_success(outcome_now)
        else:
            failure_monotonic = self.monotonic()
            self.cooldown_until = failure_monotonic + result.cooldown_seconds
            self.coalescer.shorten((item.coalescer_key for item in active), self.cooldown_until)
            if result.status == "transient":
                if self.health_state != "unavailable":
                    self.unavailable_started_at = outcome_now
                self.health_state = "unavailable"
            event = "portal_evidence_producer_config_unavailable" if result.status == "config_unavailable" else "portal_evidence_delivery_failed"
            safe_emit(
                self.telemetry, event,
                error_category=result.status, http_status=result.http_status,
                cooldown_seconds=result.cooldown_seconds,
                delivery_transient=1 if result.status == "transient" else 0,
                delivery_permanent=1 if result.status in {"permanent", "config_unavailable"} else 0,
            )
        return len(items)

    def _worker_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.process_once(block=True)
                self._heartbeat_if_due()
            except Exception:
                safe_emit(
                    self.telemetry,
                    "portal_evidence_worker_failure",
                    error_category="contained_worker_exception",
                    runtime_state="degraded",
                )

    def _heartbeat_if_due(self) -> bool:
        deadline = self.next_heartbeat_at
        if deadline is None or self.monotonic() < deadline:
            return False
        self.next_heartbeat_at = deadline + _HEARTBEAT_INTERVAL_SECONDS
        while self.next_heartbeat_at <= self.monotonic():
            self.next_heartbeat_at += _HEARTBEAT_INTERVAL_SECONDS

        observed_at = self.now()
        events: list[dict[str, Any]] = []
        unavailable = self.unavailable_started_at
        if (self.health_state == "unavailable" and unavailable is not None
                and (observed_at - unavailable).total_seconds() <= 86400):
            events.append(self._health_event("unavailable", "ingest_delivery_unavailable", unavailable))
        events.append(self._health_event("available", None, observed_at))
        try:
            result = self.producer.deliver_source_health(events)
        except Exception:
            result = DeliveryResult("transient", self.config.transient_cooldown_seconds)
        if result.status == "success":
            self.health_state = "available"
            self.unavailable_started_at = None
            safe_emit(self.telemetry, "portal_evidence_source_health", source_health_transition="available")
        elif result.status == "transient":
            if self.health_state != "unavailable":
                self.unavailable_started_at = self.now()
            self.health_state = "unavailable"
        return True

    def _evidence_success(self, recovered_at: datetime) -> None:
        events: list[dict[str, Any]] = []
        if self.health_state == "unknown":
            events.append(self._health_event("available", None, recovered_at))
        elif self.health_state == "unavailable":
            unavailable = self.unavailable_started_at
            if unavailable is not None and (recovered_at - unavailable).total_seconds() <= 86400:
                events.append(self._health_event("unavailable", "ingest_delivery_unavailable", unavailable))
            events.append(self._health_event("available", None, recovered_at))
        else:
            return
        self.health_state = "available"
        self.unavailable_started_at = None
        try:
            self.producer.deliver_source_health(events)
        except Exception:
            pass
        safe_emit(self.telemetry, "portal_evidence_source_health", source_health_transition="available")

    def _health_event(self, status: str, reason: str | None, observed_at: datetime) -> dict[str, Any]:
        return {
            "source_health_event_id": str(uuid.uuid4()),
            "site_id": self.config.site_id,
            "capture_source_id": self.config.capture_source_id,
            "source_kind": "portal_headers",
            "status": status,
            "reason_code": reason,
            "observed_at": format_utc(observed_at),
        }
