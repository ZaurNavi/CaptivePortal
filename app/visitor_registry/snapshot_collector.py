"""Bounded, fail-open authorized-client snapshot collection."""

from __future__ import annotations

import ipaddress
import logging
import re
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from app.auth_telemetry.schemas import sanitize_text
from app.common.mac import format_mac_colon
from app.logger import logger as application_logger
from app.models import Result

from .config import (
    VisitorSnapshotConfig,
    VisitorSnapshotConfigError,
)
from .protocols import ClientSnapshotProvider, SnapshotDataWriter
from .snapshot_ids import build_snapshot_id
from .snapshot_models import (
    AuthorizedClientAuthContext,
    AuthorizedClientSnapshotRequest,
    NormalizedSnapshotJob,
    ProviderFailure,
    SnapshotSubmitOutcome,
)
from .snapshot_normalizer import (
    SnapshotNormalizationError,
    normalize_client_snapshot,
    safe_raw_snapshot,
)
from .snapshot_writer import VisitorSnapshotWriter
from .telemetry import VisitorSnapshotTelemetry


SCHEMA_VERSION = 1
MAX_MESSAGE_LENGTH = 512
_FINAL_PROVIDER_CATEGORIES = frozenset({
    "client_not_available",
    "timeout",
    "network_error",
    "controller_error",
    "http_error",
    "malformed_response",
})
_PROVIDER_CATEGORY_MAP = {
    "token_error": "controller_error",
    "invalid_request": "internal_error",
}


@dataclass
class _JobRuntime:
    job: NormalizedSnapshotJob
    queue_delay_ms: int | None = None
    attempts: int = 0
    request_duration_seconds: float = 0.0
    finalized: bool = False


class DisabledVisitorSnapshotCollector:
    """No-thread implementation used by safe defaults and unit tests."""

    def __init__(
        self,
        telemetry: VisitorSnapshotTelemetry | None = None,
    ):
        self._telemetry = telemetry or VisitorSnapshotTelemetry()
        self._lock = threading.RLock()
        self._started = False

    def start(self) -> bool:
        with self._lock:
            if self._started:
                return False
            self._started = True
        self._telemetry.emit(
            "visitor_snapshot_collector_disabled",
            enabled=False,
        )
        return False

    def submit(
        self,
        request: AuthorizedClientSnapshotRequest,
    ) -> SnapshotSubmitOutcome:
        return SnapshotSubmitOutcome.DISABLED

    def stop_accepting(self) -> None:
        return None

    def drain_and_stop(
        self,
        timeout_seconds: float,
    ) -> None:
        return None


DISABLED_VISITOR_SNAPSHOT_COLLECTOR = (
    DisabledVisitorSnapshotCollector()
)


class UnavailableVisitorSnapshotCollector:
    """Fail-open implementation for invalid config or startup failure."""

    def __init__(
        self,
        *,
        telemetry: VisitorSnapshotTelemetry | None = None,
        stage: str,
        exception_type: str | None = None,
    ):
        self._telemetry = telemetry or VisitorSnapshotTelemetry()
        self._stage = stage
        self._exception_type = exception_type
        self._lock = threading.RLock()
        self._started = False

    def start(self) -> bool:
        with self._lock:
            if self._started:
                return False
            self._started = True
        self._telemetry.emit(
            "visitor_snapshot_collector_unavailable",
            "error",
            stage=self._stage,
            exception_type=self._exception_type,
        )
        return False

    def submit(
        self,
        request: AuthorizedClientSnapshotRequest,
    ) -> SnapshotSubmitOutcome:
        return SnapshotSubmitOutcome.UNAVAILABLE

    def stop_accepting(self) -> None:
        return None

    def drain_and_stop(
        self,
        timeout_seconds: float,
    ) -> None:
        return None


class AuthorizedClientSnapshotCollector:
    def __init__(
        self,
        *,
        config: VisitorSnapshotConfig,
        provider: ClientSnapshotProvider,
        writer: SnapshotDataWriter,
        telemetry: VisitorSnapshotTelemetry | None = None,
        executor_factory: Callable[..., ThreadPoolExecutor] = (
            ThreadPoolExecutor
        ),
        monotonic: Callable[[], float] = time.monotonic,
        utcnow: Callable[[], datetime] | None = None,
    ):
        self.config = config
        self._provider = provider
        self._writer = writer
        self._telemetry = telemetry or VisitorSnapshotTelemetry()
        self._executor_factory = executor_factory
        self._monotonic = monotonic
        self._utcnow = utcnow or (
            lambda: datetime.now(timezone.utc)
        )
        self._lock = threading.RLock()
        self._drain_timeout_lock = threading.RLock()
        self._capacity = threading.BoundedSemaphore(
            config.total_capacity
        )
        self._active_keys: set[str] = set()
        self._futures: dict[Future[Any], _JobRuntime] = {}
        self._executor: ThreadPoolExecutor | None = None
        self._shutdown_event = threading.Event()
        self._state = "new"
        self._stopped_emitted = False
        self._unavailable_emitted = False
        self._drain_timeout_emitted = False
        self._close_when_idle = False

    @property
    def accepting(self) -> bool:
        with self._lock:
            return self._state == "accepting"

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @property
    def active_job_count(self) -> int:
        with self._lock:
            return len(self._active_keys)

    def start(self) -> bool:
        with self._lock:
            if self._state == "accepting":
                return True
            if self._state != "new":
                return False

        try:
            writer_available = self._writer.initialize()
        except Exception as exc:
            self._mark_unavailable("writer_initialization", exc)
            return False
        if not writer_available:
            self._mark_unavailable("writer_initialization")
            return False

        try:
            executor = self._executor_factory(
                max_workers=self.config.max_workers,
                thread_name_prefix="visitor_snapshot_",
            )
        except Exception as exc:
            try:
                self._writer.close()
            except Exception:
                pass
            self._mark_unavailable("executor_start", exc)
            return False

        with self._lock:
            if self._state != "new":
                executor.shutdown(wait=False, cancel_futures=True)
                return False
            self._executor = executor
            self._state = "accepting"
        self._telemetry.emit(
            "visitor_snapshot_collector_started",
            max_workers=self.config.max_workers,
            max_pending=self.config.max_pending,
        )
        return True

    def submit(
        self,
        request: AuthorizedClientSnapshotRequest,
    ) -> SnapshotSubmitOutcome:
        with self._lock:
            state = self._state
        if state == "unavailable":
            return SnapshotSubmitOutcome.UNAVAILABLE
        if state in {"stopping", "stopped"}:
            return SnapshotSubmitOutcome.SHUTTING_DOWN
        if state != "accepting":
            return SnapshotSubmitOutcome.UNAVAILABLE

        try:
            job = self._normalize_request(request)
        except Exception as exc:
            self._telemetry.emit(
                "visitor_snapshot_invalid_context",
                "error",
                exception_type=type(exc).__name__,
            )
            return SnapshotSubmitOutcome.INVALID_CONTEXT

        runtime = _JobRuntime(job=job)
        deferred_outcome: SnapshotSubmitOutcome | None = None
        with self._lock:
            if self._state != "accepting":
                return SnapshotSubmitOutcome.SHUTTING_DOWN
            if job.idempotency_key in self._active_keys:
                deferred_outcome = (
                    SnapshotSubmitOutcome.DUPLICATE_SUPPRESSED
                )
            elif not self._capacity.acquire(blocking=False):
                deferred_outcome = SnapshotSubmitOutcome.QUEUE_REJECTED
            else:
                self._active_keys.add(job.idempotency_key)
                executor = self._executor
                try:
                    if executor is None:
                        raise RuntimeError(
                            "Visitor Snapshot executor is unavailable"
                        )
                    future = executor.submit(self._process_job, runtime)
                    self._futures[future] = runtime
                    future.add_done_callback(self._future_done)
                except Exception as exc:
                    self._active_keys.discard(job.idempotency_key)
                    self._capacity.release()
                    self._mark_unavailable_locked(
                        "executor_submit",
                        exc,
                    )
                    return SnapshotSubmitOutcome.UNAVAILABLE

        if deferred_outcome is (
            SnapshotSubmitOutcome.DUPLICATE_SUPPRESSED
        ):
            self._telemetry.emit(
                "visitor_snapshot_duplicate_suppressed",
                snapshot_id=job.snapshot_id,
                auth_session_id=job.auth_session_id,
                requested_mac=job.requested_mac,
            )
            return deferred_outcome
        if deferred_outcome is SnapshotSubmitOutcome.QUEUE_REJECTED:
            self._queue_rejected(runtime)
            return deferred_outcome

        self._telemetry.emit(
            "visitor_snapshot_job_submitted",
            snapshot_id=job.snapshot_id,
            auth_session_id=job.auth_session_id,
            requested_mac=job.requested_mac,
        )
        return SnapshotSubmitOutcome.ACCEPTED

    def stop_accepting(self) -> None:
        with self._lock:
            if self._state in {"accepting", "unavailable"}:
                self._state = "stopping"

    def drain_and_stop(self, timeout_seconds: float) -> None:
        self.stop_accepting()
        try:
            timeout = max(0.0, float(timeout_seconds))
        except (TypeError, ValueError):
            timeout = 0.0

        with self._lock:
            if self._state in {"new", "unavailable"} and not (
                self._futures
            ):
                self._state = "stopped"
                self._finish_stopped()
                return
            if self._state == "stopped":
                return
            futures = set(self._futures)
            executor = self._executor

        if futures:
            _, not_done = wait(futures, timeout=timeout)
        else:
            not_done = set()

        if not_done:
            with self._drain_timeout_lock:
                if not self._drain_timeout_emitted:
                    self._telemetry.emit(
                        "visitor_snapshot_drain_timeout",
                        "warning",
                        timeout_seconds=timeout,
                        unfinished_job_count=len(not_done),
                    )
                    self._drain_timeout_emitted = True
                self._shutdown_event.set()
                for future in not_done:
                    future.cancel()

        if executor is not None:
            try:
                executor.shutdown(
                    wait=False,
                    cancel_futures=True,
                )
            except Exception as exc:
                self._telemetry.emit(
                    "visitor_snapshot_stop_failed",
                    "error",
                    exception_type=type(exc).__name__,
                )

        finish = False
        with self._lock:
            self._executor = None
            if self._futures:
                self._close_when_idle = True
            else:
                self._state = "stopped"
                finish = True
        if finish:
            self._finish_stopped()

    def _normalize_request(
        self,
        request: AuthorizedClientSnapshotRequest,
    ) -> NormalizedSnapshotJob:
        if not isinstance(request, AuthorizedClientSnapshotRequest):
            raise ValueError("snapshot request has an invalid type")
        auth_session_id = _required_string(
            request.auth_session_id,
            "auth_session_id",
        )
        site_id = _required_string(request.site_id, "site_id")
        requested_mac = format_mac_colon(request.requested_mac)
        authorized_at = _utc_datetime(request.authorized_at)
        context = request.auth_context
        if not isinstance(context, AuthorizedClientAuthContext):
            raise ValueError("auth_context has an invalid type")
        if type(context.auth_run_number) is not int or (
            context.auth_run_number <= 0
        ):
            raise ValueError("auth_run_number must be positive")
        if type(context.authorization_attempt) is not int or (
            context.authorization_attempt < 0
        ):
            raise ValueError(
                "authorization_attempt must be non-negative"
            )
        auth_final_reason = _required_string(
            context.auth_final_reason,
            "auth_final_reason",
        )
        normalized_context = AuthorizedClientAuthContext(
            client_ip=_optional_ip(context.client_ip),
            portal_ssid=_optional_string(context.portal_ssid),
            portal_ap_mac=_optional_mac(context.portal_ap_mac),
            portal_radio_id=_optional_string(
                context.portal_radio_id
            ),
            auth_run_number=context.auth_run_number,
            authorization_attempt=context.authorization_attempt,
            auth_final_reason=auth_final_reason,
            retry_request_id=_optional_string(
                context.retry_request_id
            ),
        )
        snapshot_id = build_snapshot_id(
            auth_session_id,
            requested_mac,
        )
        return NormalizedSnapshotJob(
            snapshot_id=snapshot_id,
            idempotency_key=(
                f"{auth_session_id}:{requested_mac}"
            ),
            auth_session_id=auth_session_id,
            site_id=site_id,
            requested_mac=requested_mac,
            authorized_at=authorized_at,
            auth_context=normalized_context,
            submitted_monotonic=self._monotonic(),
        )

    def _process_job(self, runtime: _JobRuntime) -> None:
        runtime.queue_delay_ms = _milliseconds(
            self._monotonic() - runtime.job.submitted_monotonic
        )
        try:
            self._run_attempts(runtime)
        except Exception as exc:
            self._finalize_failed(
                runtime,
                error_category="internal_error",
                message=(
                    "Unexpected Visitor Snapshot collector failure: "
                    f"{type(exc).__name__}"
                ),
            )

    def _run_attempts(self, runtime: _JobRuntime) -> None:
        last_failure = ProviderFailure(
            failure_category="internal_error",
            retryable=False,
            http_status=None,
            error_code=None,
            message="Client snapshot failed",
        )
        for attempt_index in range(3):
            if self._shutdown_event.is_set():
                self._shutdown_cancelled(runtime)
                return
            if self._is_stale(runtime.job):
                self._finalize_failed(
                    runtime,
                    error_category="snapshot_stale",
                    message="Authorized client snapshot job is stale",
                )
                return

            started = self._monotonic()
            try:
                result = self._provider.get_client_snapshot(
                    runtime.job.site_id,
                    runtime.job.requested_mac,
                    self.config.request_timeout_seconds,
                )
            except Exception as exc:
                result = Result.fail(
                    error="SNAPSHOT_REQUEST_FAILED",
                    message=(
                        "Snapshot provider raised "
                        f"{type(exc).__name__}"
                    ),
                    data={
                        "http_status": None,
                        "error_code": None,
                        "failure_category": "internal_error",
                        "retryable": False,
                    },
                )
            duration = self._monotonic() - started
            runtime.request_duration_seconds += duration
            runtime.attempts += 1

            if isinstance(result, Result) and result.success:
                self._handle_success(runtime, result)
                return

            last_failure = _provider_failure(result)
            if not last_failure.retryable or attempt_index >= 2:
                break
            delay = self.config.retry_delays_seconds[attempt_index]
            self._telemetry.emit(
                "visitor_snapshot_retry_scheduled",
                "warning",
                snapshot_id=runtime.job.snapshot_id,
                auth_session_id=runtime.job.auth_session_id,
                requested_mac=runtime.job.requested_mac,
                attempt=runtime.attempts,
                delay_seconds=delay,
                failure_category=last_failure.failure_category,
            )
            if self._shutdown_event.wait(delay):
                self._shutdown_cancelled(runtime)
                return

        category = _PROVIDER_CATEGORY_MAP.get(
            last_failure.failure_category,
            last_failure.failure_category,
        )
        if category not in _FINAL_PROVIDER_CATEGORIES:
            category = "internal_error"
        self._finalize_failed(
            runtime,
            error_category=category,
            message=last_failure.message,
            error_code=last_failure.error_code,
            http_status=last_failure.http_status,
        )

    def _handle_success(
        self,
        runtime: _JobRuntime,
        result: Result,
    ) -> None:
        data = result.data if isinstance(result.data, dict) else {}
        raw_result = data.get("raw_result")
        try:
            normalized = normalize_client_snapshot(raw_result)
        except SnapshotNormalizationError as exc:
            raw_snapshot = None
            if exc.raw_serializable:
                try:
                    raw_snapshot, redacted_count = safe_raw_snapshot(
                        raw_result
                    )
                    if redacted_count:
                        self._emit_redaction(runtime, redacted_count)
                except SnapshotNormalizationError:
                    raw_snapshot = None
            path = _safe_path(exc.path)
            message = str(exc)
            if path:
                message = f"{message} at path: {path}"
            self._finalize_failed(
                runtime,
                error_category="normalization_error",
                message=message,
                http_status=_optional_http_status(
                    data.get("http_status")
                ),
                error_code=_optional_error_code(
                    data.get("error_code")
                ),
                raw_controller_snapshot=raw_snapshot,
            )
            return

        if normalized.redacted_field_count:
            self._emit_redaction(
                runtime,
                normalized.redacted_field_count,
            )
        returned_mac = normalized.client["mac"]
        if returned_mac != runtime.job.requested_mac:
            self._finalize_failed(
                runtime,
                error_category="mac_mismatch",
                message="Controller returned a different client MAC",
                http_status=_optional_http_status(
                    data.get("http_status")
                ),
                error_code=_optional_error_code(
                    data.get("error_code")
                ),
                returned_mac=returned_mac,
                raw_controller_snapshot=(
                    normalized.raw_controller_snapshot
                ),
            )
            return

        captured_at = self._utcnow()
        record = self._base_record(
            runtime,
            event="visitor.client_snapshot.captured",
            event_time_name="captured_at",
            event_time=captured_at,
        )
        record.update({
            "client": normalized.client,
            "raw_controller_snapshot": (
                normalized.raw_controller_snapshot
            ),
        })
        self._finalize_record(runtime, record)

    def _queue_rejected(self, runtime: _JobRuntime) -> None:
        self._telemetry.emit(
            "visitor_snapshot_queue_rejected",
            "warning",
            snapshot_id=runtime.job.snapshot_id,
            auth_session_id=runtime.job.auth_session_id,
            requested_mac=runtime.job.requested_mac,
        )
        self._finalize_failed(
            runtime,
            error_category="queue_rejected",
            message="Visitor Snapshot queue capacity is full",
        )

    def _shutdown_cancelled(self, runtime: _JobRuntime) -> None:
        self._telemetry.emit(
            "visitor_snapshot_shutdown_cancelled",
            "warning",
            snapshot_id=runtime.job.snapshot_id,
            auth_session_id=runtime.job.auth_session_id,
            requested_mac=runtime.job.requested_mac,
            attempts=runtime.attempts,
        )
        self._finalize_failed(
            runtime,
            error_category="shutdown_cancelled",
            message="Visitor Snapshot job was cancelled during shutdown",
        )

    def _emit_redaction(
        self,
        runtime: _JobRuntime,
        count: int,
    ) -> None:
        self._telemetry.emit(
            "visitor_snapshot_sensitive_field_redacted",
            "warning",
            snapshot_id=runtime.job.snapshot_id,
            auth_session_id=runtime.job.auth_session_id,
            redacted_field_count=count,
        )

    def _finalize_failed(
        self,
        runtime: _JobRuntime,
        *,
        error_category: str,
        message: str,
        error_code: int | str | None = None,
        http_status: int | None = None,
        returned_mac: str | None = None,
        raw_controller_snapshot: dict[str, Any] | None = None,
    ) -> None:
        failed_at = self._utcnow()
        record = self._base_record(
            runtime,
            event="visitor.client_snapshot.failed",
            event_time_name="failed_at",
            event_time=failed_at,
        )
        record.update({
            "error_category": error_category,
            "error_code": error_code,
            "http_status": http_status,
            "message": _safe_message(message),
        })
        if returned_mac is not None:
            record["returned_mac"] = returned_mac
        if raw_controller_snapshot is not None:
            record["raw_controller_snapshot"] = (
                raw_controller_snapshot
            )
        self._finalize_record(runtime, record)

    def _base_record(
        self,
        runtime: _JobRuntime,
        *,
        event: str,
        event_time_name: str,
        event_time: datetime,
    ) -> dict[str, Any]:
        job = runtime.job
        return {
            "schema_version": SCHEMA_VERSION,
            "event": event,
            "snapshot_id": job.snapshot_id,
            event_time_name: _timestamp(event_time),
            "authorized_at": _timestamp(job.authorized_at),
            "auth_session_id": job.auth_session_id,
            "site_id": job.site_id,
            "requested_mac": job.requested_mac,
            "attempts": runtime.attempts,
            "queue_delay_ms": runtime.queue_delay_ms,
            "request_duration_ms": _milliseconds(
                runtime.request_duration_seconds
            ),
            "snapshot_lag_ms": _snapshot_lag_ms(
                event_time,
                job.authorized_at,
            ),
            "auth_context": asdict(job.auth_context),
        }

    def _finalize_record(
        self,
        runtime: _JobRuntime,
        record: dict[str, Any],
    ) -> None:
        with self._lock:
            if runtime.finalized:
                return
            runtime.finalized = True
        try:
            self._writer.write(record)
        except Exception as exc:
            self._telemetry.emit(
                "visitor_snapshot_write_failed",
                "error",
                snapshot_id=runtime.job.snapshot_id,
                exception_type=type(exc).__name__,
            )
            self._mark_unavailable("writer_write", exc)

    def _future_done(self, future: Future[Any]) -> None:
        with self._lock:
            runtime = self._futures.get(future)
        if runtime is None:
            return
        if future.cancelled():
            self._shutdown_cancelled(runtime)
        else:
            try:
                error = future.exception()
            except Exception as exc:
                error = exc
            if error is not None:
                self._finalize_failed(
                    runtime,
                    error_category="internal_error",
                    message=(
                        "Visitor Snapshot worker failed: "
                        f"{type(error).__name__}"
                    ),
                )

        finish = False
        with self._lock:
            self._futures.pop(future, None)
            self._active_keys.discard(
                runtime.job.idempotency_key
            )
            try:
                self._capacity.release()
            except ValueError:
                pass
            if self._close_when_idle and not self._futures:
                self._state = "stopped"
                finish = True
        if finish:
            self._finish_stopped()

    def _is_stale(self, job: NormalizedSnapshotJob) -> bool:
        age = (
            self._utcnow().astimezone(timezone.utc)
            - job.authorized_at
        ).total_seconds()
        return age > self.config.max_job_age_seconds

    def _mark_unavailable(
        self,
        stage: str,
        error: Exception | None = None,
    ) -> None:
        with self._lock:
            self._mark_unavailable_locked(stage, error)

    def _mark_unavailable_locked(
        self,
        stage: str,
        error: Exception | None = None,
    ) -> None:
        already_emitted = self._unavailable_emitted
        if self._state not in {"stopping", "stopped"}:
            self._state = "unavailable"
            self._shutdown_event.set()
        self._unavailable_emitted = True
        if already_emitted:
            return
        self._telemetry.emit(
            "visitor_snapshot_collector_unavailable",
            "error",
            stage=stage,
            exception_type=(
                type(error).__name__
                if error is not None
                else None
            ),
        )

    def _finish_stopped(self) -> None:
        with self._lock:
            if self._stopped_emitted:
                return
            self._stopped_emitted = True
        try:
            self._writer.close()
        except Exception as exc:
            self._telemetry.emit(
                "visitor_snapshot_stop_failed",
                "error",
                exception_type=type(exc).__name__,
            )
        self._telemetry.emit(
            "visitor_snapshot_collector_stopped",
        )


def create_visitor_snapshot_collector(
    *,
    settings: dict[str, Any],
    provider: ClientSnapshotProvider,
    telemetry_service: Any | None = None,
    logger: logging.Logger = application_logger,
) -> (
    AuthorizedClientSnapshotCollector
    | DisabledVisitorSnapshotCollector
    | UnavailableVisitorSnapshotCollector
):
    telemetry = (
        VisitorSnapshotTelemetry(logger=logger)
        if telemetry_service is None
        else VisitorSnapshotTelemetry(
            telemetry_provider=lambda: telemetry_service,
            logger=logger,
        )
    )
    try:
        config = VisitorSnapshotConfig.from_settings(settings)
    except VisitorSnapshotConfigError as exc:
        return UnavailableVisitorSnapshotCollector(
            telemetry=telemetry,
            stage="invalid_configuration",
            exception_type=type(exc).__name__,
        )
    if not config.enabled:
        return DisabledVisitorSnapshotCollector(telemetry)
    writer = VisitorSnapshotWriter(
        config.log_file,
        rotation_max_bytes=config.rotation_max_bytes,
        rotation_backup_count=config.rotation_backup_count,
    )
    return AuthorizedClientSnapshotCollector(
        config=config,
        provider=provider,
        writer=writer,
        telemetry=telemetry,
    )


def _provider_failure(result: Any) -> ProviderFailure:
    if not isinstance(result, Result):
        return ProviderFailure(
            failure_category="malformed_response",
            retryable=True,
            http_status=None,
            error_code=None,
            message="Snapshot provider returned an invalid result",
        )
    data = result.data if isinstance(result.data, dict) else {}
    category = data.get("failure_category")
    retryable = data.get("retryable")
    if not isinstance(category, str) or type(retryable) is not bool:
        return ProviderFailure(
            failure_category="malformed_response",
            retryable=True,
            http_status=_optional_http_status(
                data.get("http_status")
            ),
            error_code=_optional_error_code(
                data.get("error_code")
            ),
            message="Snapshot provider failure contract is malformed",
        )
    return ProviderFailure(
        failure_category=category,
        retryable=retryable,
        http_status=_optional_http_status(data.get("http_status")),
        error_code=_optional_error_code(data.get("error_code")),
        message=_safe_message(result.message or result.error or category),
    )


def _required_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _optional_ip(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def _optional_mac(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return format_mac_colon(value)
    except ValueError:
        return None


def _utc_datetime(value: Any) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError("authorized_at must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("authorized_at must be timezone-aware")
    return value.astimezone(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")


def _milliseconds(seconds: float) -> int:
    return max(0, int(round(seconds * 1000)))


def _snapshot_lag_ms(
    event_time: datetime,
    authorized_at: datetime,
) -> int | None:
    try:
        return _milliseconds(
            (
                event_time.astimezone(timezone.utc)
                - authorized_at.astimezone(timezone.utc)
            ).total_seconds()
        )
    except Exception:
        return None


def _optional_http_status(value: Any) -> int | None:
    return value if type(value) is int and value > 0 else None


def _optional_error_code(value: Any) -> int | str | None:
    if isinstance(value, bool):
        return None
    return value if isinstance(value, (int, str)) else None


def _safe_message(value: Any) -> str:
    text = str(value)
    text = re.sub(
        r"(?i)\bauthorization\b\s*[:=]\s*"
        r"(?:(?:bearer|accesstoken)\s*[= ]\s*)?"
        r"[^\s,;]+",
        "Authorization=[REDACTED]",
        text,
    )
    text = re.sub(
        r"(?i)\b(access[_ -]?token|client[_ -]?secret|"
        r"password|cookie)\b\s*[:=]\s*[^\s,;]+",
        r"\1=[REDACTED]",
        text,
    )
    return sanitize_text(text, MAX_MESSAGE_LENGTH)


def _safe_path(value: str | None) -> str | None:
    if value is None:
        return None
    return sanitize_text(value, 256)
