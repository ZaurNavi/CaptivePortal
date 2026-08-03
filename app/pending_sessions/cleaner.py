from __future__ import annotations

import copy
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from app.models import Result

from .action_guard import ActionGuard
from .classifier import PendingSessionClassifier
from .config import PendingSessionCleanerConfig
from .journal import JournalWriteError, JournalWriter
from .models import (
    PendingClientCandidate,
    PendingClientObservation,
    PendingScanSummary,
)
from .pagination import paginate_site_inventory
from .protocols import (
    PendingClientSessionProvider,
    PendingSessionProtection,
)
from .telemetry import CleanerTelemetryAdapter


class _RetryingProvider:
    def __init__(self, cleaner: "PendingClientSessionCleaner") -> None:
        self._cleaner = cleaner

    def list_active_clients(self, **kwargs) -> Result:
        return self._cleaner._retry_get(
            lambda: self._cleaner.provider.list_active_clients(
                **kwargs
            )
        )


class PendingClientSessionCleaner:
    """Non-overlapping fail-open Cleaner engine."""

    def __init__(
        self,
        *,
        config: PendingSessionCleanerConfig,
        provider: PendingClientSessionProvider,
        protection: PendingSessionProtection,
        journal: JournalWriter,
        telemetry: CleanerTelemetryAdapter,
        shutdown_event: threading.Event | None = None,
        action_guard: ActionGuard | None = None,
        clock=time.monotonic,
        utcnow: Callable[[], datetime] | None = None,
    ) -> None:
        self.config = config
        self.provider = provider
        self.protection = protection
        self.journal = journal
        self.telemetry = telemetry
        self.shutdown_event = shutdown_event or threading.Event()
        self.action_guard = action_guard or ActionGuard(
            cooldown_seconds=config.action_cooldown_seconds,
            max_actions_per_mac_per_hour=(
                config.max_actions_per_mac_per_hour
            ),
            clock=clock,
        )
        self._clock = clock
        self._utcnow = utcnow or (
            lambda: datetime.now(timezone.utc)
        )
        self._scan_lock = threading.Lock()
        self._state_lock = threading.RLock()
        self._state = "starting"
        self._journal_available = True

    @property
    def state(self) -> str:
        with self._state_lock:
            return self._state

    def begin_stopping(self) -> None:
        self._set_state("stopping")
        self.shutdown_event.set()

    def close(self) -> None:
        try:
            self.journal.close()
        except Exception:
            self.telemetry.safe_emit_system(
                "pending_session_cleaner_writer_error",
                level="error",
            )

    def run_once(self) -> PendingScanSummary | None:
        if self.shutdown_event.is_set():
            return None
        if not self._scan_lock.acquire(blocking=False):
            self.telemetry.safe_emit_system(
                "pending_session_cleaner_scan_overlap_suppressed",
                level="debug",
            )
            return None
        try:
            return self._run_once_locked()
        except Exception as exc:
            self._set_state("degraded")
            self.telemetry.safe_emit_system(
                "pending_session_cleaner_internal_error",
                level="error",
                exception_type=type(exc).__name__,
            )
            return None
        finally:
            self._scan_lock.release()

    def _run_once_locked(self) -> PendingScanSummary:
        started_mono = self._clock()
        started_at = self._utcnow()
        deadline = (
            started_mono
            + self.config.max_scan_duration_seconds
        )
        scan_id = str(uuid.uuid4())
        summary = PendingScanSummary(
            scan_id=scan_id,
            started_at=_timestamp(started_at),
            finished_at=_timestamp(started_at),
            duration_ms=0,
            site_id=str(self.config.site_id),
            scan_result="failed",
            inventory_complete=False,
        )

        inventory = paginate_site_inventory(
            _RetryingProvider(self),
            site_id=str(self.config.site_id),
            page_size=self.config.page_size,
            max_pages=self.config.max_pages,
            max_clients=self.config.max_clients,
            request_timeout_seconds=(
                self.config.request_timeout_seconds
            ),
            shutdown_event=self.shutdown_event,
            budget_deadline=deadline,
        )
        summary.pages_fetched = inventory.pages_fetched
        summary.controller_total_rows = (
            inventory.controller_total_rows
        )
        summary.inventory_complete = inventory.inventory_complete
        summary.scan_result = inventory.scan_result

        classifier = PendingSessionClassifier(
            min_uptime_seconds=self.config.min_uptime_seconds,
            ssid_allowlist=self.config.ssids,
        )
        classified = classifier.classify_inventory(
            inventory.clients,
            site_id=str(self.config.site_id),
        )
        _copy_classification(summary, classified)

        if not inventory.inventory_complete:
            self._finish_scan(
                summary,
                started_mono,
                level="warning",
            )
            return summary

        actions_this_scan = 0
        candidates = classified.candidates
        for index, candidate in enumerate(candidates):
            if self.shutdown_event.is_set():
                summary.scan_result = "partial"
                self._write_completed_without_post(
                    scan_id,
                    candidate,
                    "shutdown_started",
                )
                continue
            if self._clock() >= deadline:
                summary.scan_result = "partial"
                for remaining in candidates[index:]:
                    self._write_completed_without_post(
                        scan_id,
                        remaining,
                        "scan_time_budget_exceeded",
                    )
                break

            attempted = self._process_candidate(
                summary=summary,
                scan_id=scan_id,
                candidate=candidate,
                deadline=deadline,
                actions_this_scan=actions_this_scan,
            )
            if attempted:
                actions_this_scan += 1

        if summary.scan_result == "failed":
            summary.scan_result = "success"
        self._finish_scan(summary, started_mono)
        return summary

    def _process_candidate(
        self,
        *,
        summary: PendingScanSummary,
        scan_id: str,
        candidate: PendingClientCandidate,
        deadline: float,
        actions_this_scan: int,
    ) -> bool:
        initial = candidate.observation
        first_protection = self.protection.check(
            site_id=str(self.config.site_id),
            client_mac=initial.mac,
            now=self._utcnow(),
            grace_seconds=self.config.portal_grace_seconds,
        )
        if first_protection.protected:
            summary.local_protected_count += 1
            self._write_completed_without_post(
                scan_id,
                candidate,
                _protection_result(first_protection.reason),
            )
            return False

        preflight_result = self._retry_get(
            lambda: self.provider.get_pending_client_state(
                site_id=str(self.config.site_id),
                client_mac=initial.mac,
                timeout_seconds=(
                    self.config.request_timeout_seconds
                ),
            ),
            deadline=deadline,
        )
        if not preflight_result.success:
            summary.preflight_rejected_count += 1
            self._write_completed_without_post(
                scan_id,
                candidate,
                "skipped_state_changed",
                provider_result=preflight_result,
            )
            return False

        fresh, reject_reason = self._preflight_decision(
            candidate,
            preflight_result.data.get("client"),
        )
        if fresh is None:
            summary.preflight_rejected_count += 1
            self._write_completed_without_post(
                scan_id,
                candidate,
                reject_reason,
            )
            return False

        second_protection = self.protection.check(
            site_id=str(self.config.site_id),
            client_mac=fresh.mac,
            now=self._utcnow(),
            grace_seconds=self.config.portal_grace_seconds,
        )
        if second_protection.protected:
            summary.local_protected_count += 1
            self._write_completed_without_post(
                scan_id,
                candidate,
                "skipped_local_state_changed",
                after=fresh,
            )
            return False

        summary.final_eligible_count += 1
        guard = self.action_guard.check(
            client_mac=fresh.mac,
            actions_this_scan=actions_this_scan,
            max_actions_per_scan=(
                self.config.max_actions_per_scan
            ),
            stopping=self.shutdown_event.is_set(),
            inventory_complete=summary.inventory_complete,
            budget_exhausted=self._clock() >= deadline,
            journal_available=self._journal_available,
        )
        if not guard.allowed:
            if guard.reason in {
                "cooldown_active",
                "hourly_action_limit",
            }:
                summary.rate_limited_count += 1
            if guard.reason == "scan_action_limit":
                summary.action_limit_count += 1
            self._write_completed_without_post(
                scan_id,
                candidate,
                str(guard.reason),
                after=fresh,
            )
            return False

        action_id = str(uuid.uuid4())
        planned = self._planned_event(
            action_id,
            scan_id,
            candidate,
            fresh,
        )
        try:
            self.journal.write_and_flush(planned)
            self._journal_available = True
        except JournalWriteError:
            self._journal_available = False
            self._set_state("degraded")
            summary.action_error_count += 1
            self.telemetry.safe_emit_system(
                "pending_session_cleaner_audit_unavailable",
                level="warning",
                client_mac=fresh.mac,
            )
            return False

        self.action_guard.record_attempt(fresh.mac)
        summary.reconnect_attempted_count += 1
        post_started = self._clock()
        post_attempts = 1
        command = self.provider.reconnect_client(
            site_id=str(self.config.site_id),
            client_mac=fresh.mac,
            timeout_seconds=self.config.request_timeout_seconds,
        )

        if command.error == "TOKEN_EXPIRED":
            recovered = self._recover_expired_token(
                candidate,
                deadline,
            )
            if recovered is not None:
                fresh = recovered
                post_attempts = 2
                command = self.provider.reconnect_client(
                    site_id=str(self.config.site_id),
                    client_mac=fresh.mac,
                    timeout_seconds=(
                        self.config.request_timeout_seconds
                    ),
                )

        command_outcome = _command_outcome(command)
        verification = self._verify(
            before=fresh,
            command_outcome=command_outcome,
            deadline=deadline,
        )
        result_name = verification["result"]

        if result_name in {
            "confirmed_disconnected",
            "confirmed_new_session",
            "ambiguous_confirmed_disconnected",
            "ambiguous_confirmed_new_session",
        }:
            summary.reconnect_confirmed_count += 1
        else:
            summary.reconnect_unconfirmed_count += 1
            if result_name in {
                "verification_failed",
                "ambiguous_unresolved",
                "reset_not_confirmed",
            }:
                summary.action_error_count += 1

        completed = self._completed_event(
            action_id=action_id,
            scan_id=scan_id,
            before=fresh,
            command=command,
            command_outcome=command_outcome,
            post_attempts=post_attempts,
            post_started=post_started,
            verification=verification,
        )
        try:
            self.journal.write_and_flush(completed)
            self._journal_available = True
        except JournalWriteError:
            self._journal_available = False
            self._set_state("degraded")
            self.telemetry.safe_emit_system(
                "pending_session_cleaner_writer_error",
                level="error",
                action_id=action_id,
                client_mac=fresh.mac,
            )
        return True

    def _recover_expired_token(
        self,
        candidate: PendingClientCandidate,
        deadline: float,
    ) -> PendingClientObservation | None:
        invalidate = getattr(
            self.provider,
            "_invalidate_cached_token",
            None,
        )
        if callable(invalidate):
            invalidate()
        result = self._retry_get(
            lambda: self.provider.get_pending_client_state(
                site_id=str(self.config.site_id),
                client_mac=candidate.observation.mac,
                timeout_seconds=(
                    self.config.request_timeout_seconds
                ),
            ),
            deadline=deadline,
        )
        if not result.success:
            return None
        fresh, _ = self._preflight_decision(
            candidate,
            result.data.get("client"),
        )
        if fresh is None:
            return None
        for _ in range(2):
            decision = self.protection.check(
                site_id=str(self.config.site_id),
                client_mac=fresh.mac,
                now=self._utcnow(),
                grace_seconds=self.config.portal_grace_seconds,
            )
            if decision.protected:
                return None
        return fresh

    def _preflight_decision(
        self,
        candidate: PendingClientCandidate,
        raw_client: Any,
    ) -> tuple[PendingClientObservation | None, str]:
        try:
            fresh = PendingSessionClassifier(
                min_uptime_seconds=(
                    self.config.min_uptime_seconds
                ),
                ssid_allowlist=self.config.ssids,
            )._parse_row(raw_client)
        except (KeyError, TypeError, ValueError):
            return None, "skipped_state_changed"

        before = candidate.observation
        if fresh.mac != before.mac:
            return None, "skipped_state_changed"
        if not fresh.active:
            return None, "skipped_inactive"
        if not fresh.wireless:
            return None, "skipped_state_changed"
        if fresh.auth_status == 2:
            return None, "skipped_authorized"
        if fresh.auth_status != 1 or fresh.blocked:
            return None, "skipped_state_changed"
        if fresh.uptime < self.config.min_uptime_seconds:
            return None, "skipped_session_replaced"
        if (
            fresh.uptime
            + self.config.uptime_regression_tolerance_seconds
            < candidate.list_uptime
        ):
            return None, "skipped_session_replaced"
        if fresh.ssid != before.ssid:
            return None, "skipped_ssid_changed"
        if fresh.ssid not in self.config.ssids:
            return None, "skipped_ssid_changed"
        if (
            before.ap_mac
            and fresh.ap_mac
            and fresh.ap_mac != before.ap_mac
        ):
            return None, "skipped_ap_changed"
        return fresh, ""

    def _verify(
        self,
        *,
        before: PendingClientObservation,
        command_outcome: str,
        deadline: float,
    ) -> dict[str, Any]:
        attempts = 0
        last = None
        for delay in self.config.verify_delays_seconds:
            if not self._interruptible_wait(delay, deadline):
                break
            attempts += 1
            response = self._retry_get(
                lambda: self.provider.get_pending_client_state(
                    site_id=str(self.config.site_id),
                    client_mac=before.mac,
                    timeout_seconds=(
                        self.config.request_timeout_seconds
                    ),
                ),
                deadline=deadline,
            )
            if not response.success:
                last = None
                continue
            raw = response.data.get("client")
            if not isinstance(raw, dict):
                last = None
                continue
            if raw.get("active") is False:
                return {
                    "attempts": attempts,
                    "after": copy.deepcopy(raw),
                    "result": _ambiguous_prefix(
                        command_outcome,
                        "confirmed_disconnected",
                    ),
                }
            try:
                after = PendingSessionClassifier(
                    min_uptime_seconds=0,
                    ssid_allowlist=(before.ssid,),
                )._parse_row(raw)
            except (KeyError, TypeError, ValueError):
                last = copy.deepcopy(raw)
                continue
            last = after
            if after.auth_status == 2:
                return {
                    "attempts": attempts,
                    "after": after,
                    "result": _ambiguous_prefix(
                        command_outcome,
                        "client_now_authorized",
                    ),
                }
            if (
                after.active
                and after.auth_status == 1
                and after.uptime
                + self.config.uptime_regression_tolerance_seconds
                < before.uptime
            ):
                return {
                    "attempts": attempts,
                    "after": after,
                    "result": _ambiguous_prefix(
                        command_outcome,
                        "confirmed_new_session",
                    ),
                }

        if command_outcome == "ambiguous":
            result = "ambiguous_unresolved"
        elif last is None:
            result = "verification_failed"
        else:
            result = "reset_not_confirmed"
        return {
            "attempts": attempts,
            "after": last,
            "result": result,
        }

    def _retry_get(
        self,
        operation: Callable[[], Result],
        *,
        deadline: float | None = None,
    ) -> Result:
        delays = (0.0,) + tuple(
            self.config.get_retry_delays_seconds
        )
        last = Result.fail(
            error="GET_FAILED",
            message="GET did not run",
            data={
                "failure_category": "internal_error",
                "retryable": False,
            },
        )
        for index, delay in enumerate(delays):
            if index and not self._interruptible_wait(delay, deadline):
                return last
            if self.shutdown_event.is_set():
                return last
            if deadline is not None and self._clock() >= deadline:
                return last
            last = operation()
            if last.success:
                return last
            data = last.data if isinstance(last.data, dict) else {}
            if not bool(data.get("retryable")):
                return last
        return last

    def _interruptible_wait(
        self,
        seconds: float,
        deadline: float | None,
    ) -> bool:
        seconds = max(0.0, float(seconds))
        if deadline is not None:
            remaining = deadline - self._clock()
            if remaining <= 0:
                return False
            seconds = min(seconds, remaining)
        return not self.shutdown_event.wait(seconds)

    def _planned_event(
        self,
        action_id: str,
        scan_id: str,
        candidate: PendingClientCandidate,
        fresh: PendingClientObservation,
    ) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "event": "pending_session.action.planned",
            "action_id": action_id,
            "scan_id": scan_id,
            "planned_at": _timestamp(self._utcnow()),
            "site_id": str(self.config.site_id),
            "client_mac": fresh.mac,
            "client_ip": fresh.client_ip,
            "ssid": fresh.ssid,
            "ap_mac": fresh.ap_mac,
            "radio_id": fresh.radio_id,
            "auth_status_before": fresh.auth_status,
            "active_before": fresh.active,
            "uptime_before": fresh.uptime,
            "list_uptime": candidate.list_uptime,
            "local_protection": False,
            "action": "reconnect",
        }

    def _completed_event(
        self,
        *,
        action_id: str,
        scan_id: str,
        before: PendingClientObservation,
        command: Result,
        command_outcome: str,
        post_attempts: int,
        post_started: float,
        verification: dict[str, Any],
    ) -> dict[str, Any]:
        after = verification.get("after")
        return {
            "schema_version": 1,
            "event": "pending_session.action.completed",
            "action_id": action_id,
            "scan_id": scan_id,
            "finished_at": _timestamp(self._utcnow()),
            "duration_ms": max(
                0,
                int((self._clock() - post_started) * 1000),
            ),
            "site_id": str(self.config.site_id),
            "client_mac": before.mac,
            "client_ip_before": before.client_ip,
            "client_ip_after": _field(after, "client_ip", "ip"),
            "ssid_before": before.ssid,
            "ssid_after": _field(after, "ssid", "ssid"),
            "ap_mac_before": before.ap_mac,
            "ap_mac_after": _field(after, "ap_mac", "apMac"),
            "auth_status_before": before.auth_status,
            "auth_status_after": _field(
                after,
                "auth_status",
                "authStatus",
            ),
            "active_before": before.active,
            "active_after": _field(after, "active", "active"),
            "uptime_before": before.uptime,
            "uptime_after": _field(after, "uptime", "uptime"),
            "action": "reconnect",
            "post_attempts": post_attempts,
            "command_outcome": command_outcome,
            "controller_http_status": _data(command, "http_status"),
            "controller_error_code": _data(command, "error_code"),
            "controller_message": command.message,
            "verification_attempts": verification["attempts"],
            "result": verification["result"],
        }

    def _write_completed_without_post(
        self,
        scan_id: str,
        candidate: PendingClientCandidate,
        result: str,
        *,
        after: PendingClientObservation | None = None,
        provider_result: Result | None = None,
    ) -> None:
        before = candidate.observation
        event = {
            "schema_version": 1,
            "event": "pending_session.action.completed",
            "action_id": str(uuid.uuid4()),
            "scan_id": scan_id,
            "finished_at": _timestamp(self._utcnow()),
            "duration_ms": 0,
            "site_id": str(self.config.site_id),
            "client_mac": before.mac,
            "client_ip_before": before.client_ip,
            "client_ip_after": (
                after.client_ip if after is not None else None
            ),
            "ssid_before": before.ssid,
            "ssid_after": (
                after.ssid if after is not None else None
            ),
            "ap_mac_before": before.ap_mac,
            "ap_mac_after": (
                after.ap_mac if after is not None else None
            ),
            "auth_status_before": before.auth_status,
            "auth_status_after": (
                after.auth_status if after is not None else None
            ),
            "active_before": before.active,
            "active_after": (
                after.active if after is not None else None
            ),
            "uptime_before": before.uptime,
            "uptime_after": (
                after.uptime if after is not None else None
            ),
            "action": "reconnect",
            "post_attempts": 0,
            "command_outcome": "not_sent",
            "controller_http_status": (
                _data(provider_result, "http_status")
                if provider_result is not None
                else None
            ),
            "controller_error_code": (
                _data(provider_result, "error_code")
                if provider_result is not None
                else None
            ),
            "controller_message": (
                provider_result.message
                if provider_result is not None
                else ""
            ),
            "verification_attempts": 0,
            "result": result,
        }
        try:
            self.journal.write_and_flush(event)
        except JournalWriteError:
            self._journal_available = False
            self._set_state("degraded")

    def _finish_scan(
        self,
        summary: PendingScanSummary,
        started_mono: float,
        *,
        level: str = "debug",
    ) -> None:
        summary.finished_at = _timestamp(self._utcnow())
        summary.duration_ms = max(
            0,
            int((self._clock() - started_mono) * 1000),
        )
        event = {
            "schema_version": 1,
            "event": "pending_session.scan.completed",
            **summary.__dict__,
        }
        try:
            self.journal.write_and_flush(event)
            self._journal_available = True
            if self.state == "degraded":
                self.telemetry.safe_emit_system(
                    "pending_session_cleaner_recovered",
                )
            self._set_state("active")
        except JournalWriteError:
            self._journal_available = False
            self._set_state("degraded")
            self.telemetry.safe_emit_system(
                "pending_session_cleaner_writer_error",
                level="error",
            )
        self.telemetry.safe_emit_system(
            (
                "pending_session_cleaner_scan_partial"
                if summary.scan_result != "success"
                else "pending_session_cleaner_scan_completed"
            ),
            level=(
                "warning"
                if summary.scan_result != "success"
                else level
            ),
            scan_id=summary.scan_id,
            scan_result=summary.scan_result,
            duration_ms=summary.duration_ms,
        )

    def _set_state(self, state: str) -> None:
        with self._state_lock:
            if self._state == state:
                return
            previous = self._state
            self._state = state
        self.telemetry.safe_emit_system(
            "pending_session_cleaner_state_changed",
            previous_state=previous,
            state=state,
        )


def _copy_classification(summary, classified) -> None:
    for name in (
        "clients_rows_received",
        "clients_valid",
        "clients_invalid",
        "duplicate_mac_count",
        "wireless_active_count",
        "wired_or_non_wireless_count",
        "authorized_active_count",
        "unauthorized_active_count",
        "unknown_auth_status_count",
        "below_threshold_count",
        "ssid_not_allowed_count",
        "blocked_count",
        "initial_candidate_count",
    ):
        setattr(summary, name, getattr(classified, name))
    summary.auth_status_counts = dict(
        classified.auth_status_counts
    )


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _data(result: Result | None, key: str):
    if result is None or not isinstance(result.data, dict):
        return None
    return result.data.get(key)


def _field(after, attr: str, key: str):
    if after is None:
        return None
    if isinstance(after, dict):
        return after.get(key)
    return getattr(after, attr, None)


def _command_outcome(result: Result) -> str:
    if result.success:
        return "accepted"
    data = result.data if isinstance(result.data, dict) else {}
    if bool(data.get("retryable")):
        return "ambiguous"
    return "rejected"


def _ambiguous_prefix(command_outcome: str, result: str) -> str:
    if command_outcome != "ambiguous":
        return result
    return {
        "confirmed_disconnected": (
            "ambiguous_confirmed_disconnected"
        ),
        "confirmed_new_session": (
            "ambiguous_confirmed_new_session"
        ),
        "client_now_authorized": (
            "ambiguous_client_now_authorized"
        ),
    }[result]


def _protection_result(reason: str | None) -> str:
    return {
        "active_auth_run": "skipped_local_auth_active",
        "active_auth_session": "skipped_local_auth_active",
        "authorization_retry": "skipped_local_auth_active",
        "recent_portal_activity": (
            "skipped_recent_portal_activity"
        ),
        "recently_authorized": (
            "skipped_recent_portal_activity"
        ),
        "protection_check_failed": (
            "skipped_protection_check_failed"
        ),
    }.get(reason, "skipped_local_auth_active")
