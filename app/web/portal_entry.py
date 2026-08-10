"""Shared entry into the existing AuthSession/AuthWorker portal flow."""

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from typing import Any

from flask import render_template

from app.auth.worker import log_auth_event
from app.auth_telemetry import events as telemetry_events
from app.logger import logger
from app.web.localization import PORTAL_TRANSLATIONS


@dataclass(frozen=True)
class PortalClientContext:
    site_id: str
    client_mac: str | None
    client_ip: str | None = None
    ap_mac: str | None = None
    ssid: str | None = None
    redirect_url: str | None = None
    radio_id: str | None = None


@dataclass(frozen=True)
class PortalEntryResult:
    """Structured result shared by HTML and JSON portal entry paths."""

    session_id: str | None
    redirect_url: str | None
    initial_state: dict[str, Any]
    status_code: int = 200
    error_message: str | None = None
    error_code: str | None = None


class PortalEntryHandler:
    def __init__(
        self,
        *,
        session_manager: Any,
        auth_worker: Any,
        executor: Any,
        auth_telemetry: Any,
        portal_counter_service: Any = None,
        counter_recording_enabled: bool = False,
    ):
        self._session_manager = session_manager
        self._auth_worker = auth_worker
        self._executor = executor
        self._auth_telemetry = auth_telemetry
        self._portal_counter_service = portal_counter_service
        self._counter_recording_enabled = counter_recording_enabled

    def open_portal(self, context: PortalClientContext):
        result = self.prepare_portal(context)
        rendered = render_template(
            "portal.html",
            session_id=result.session_id,
            redirect_url=result.redirect_url,
            initial_status=(
                result.initial_state.get("status")
                or result.initial_state.get("state")
                or "FAILED"
            ),
            initial_progress=result.initial_state.get("progress", 100),
            initial_state=result.initial_state,
            portal_translations=PORTAL_TRANSLATIONS,
            error_message=result.error_message,
        )
        if result.status_code == 200:
            return rendered
        return rendered, result.status_code

    def prepare_portal(
        self,
        context: PortalClientContext,
    ) -> PortalEntryResult:
        """Create/reuse one session and return its authoritative state."""
        try:
            session, created = self._session_manager.create_or_get(
                site_id=context.site_id,
                client_mac=context.client_mac,
                client_ip=context.client_ip,
                ap_mac=context.ap_mac,
                ssid=context.ssid,
                redirect_url=context.redirect_url,
                radio_id=context.radio_id,
            )

            if created and self._counter_recording_enabled:
                try:
                    self._portal_counter_service.record_open(
                        session_id=session.session_id,
                        opened_at=datetime.now(timezone.utc),
                    )
                except Exception:
                    logger.exception(
                        "portal_counter.write_failed session_id=%s",
                        session.session_id,
                    )

            if created:
                log_auth_event(
                    telemetry_events.SESSION_CREATED,
                    session,
                    state=session.status.value,
                    created_at=session.created_at,
                    client_mac=session.client_mac,
                    client_ip=session.client_ip,
                    site_id=session.site_id,
                )
            else:
                log_auth_event(
                    telemetry_events.SESSION_REUSED,
                    session,
                    state=session.status.value,
                    client_mac=session.client_mac,
                    client_ip=session.client_ip,
                    site_id=session.site_id,
                    reuse_reason=(
                        "active_session"
                        if session.is_active()
                        else "retry_cooldown"
                    ),
                )

            if created:
                started, reason, _error = self.submit_worker(
                    session,
                    session.current_run_number,
                    session.current_run_token,
                )
                if not started:
                    return self._session_result(
                        session,
                        status_code=500,
                        error_message=(
                            "Не удалось запустить процесс подключения."
                            if reason == "CONFIGURATION_ERROR"
                            else "Системная ошибка запуска подключения."
                        ),
                        error_code=(
                            "configuration_error"
                            if reason == "CONFIGURATION_ERROR"
                            else "worker_start_failed"
                        ),
                    )

            snapshot = self._session_manager.snapshot(session)
            if snapshot is None:
                return self._failure_result(
                    "Сессия подключения не найдена.",
                    500,
                    redirect_url=context.redirect_url,
                    error_code="session_not_found",
                )

            return PortalEntryResult(
                session_id=session.session_id,
                redirect_url=session.redirect_url,
                initial_state=dict(snapshot),
            )
        except ValueError as exc:
            logger.warning(
                "portal_entry.invalid_client site=%s mac=%s error=%s",
                context.site_id,
                context.client_mac,
                exc,
            )
            return self._failure_result(
                "Неверные данные клиента.",
                400,
                redirect_url=context.redirect_url,
                error_code="invalid_context",
            )
        except Exception:
            logger.exception(
                "portal_entry.unexpected_error site=%s mac=%s",
                context.site_id,
                context.client_mac,
            )
            return self._failure_result(
                "Внутренняя ошибка сервера.",
                500,
                redirect_url=context.redirect_url,
                error_code="internal_error",
            )

    def submit_worker(
        self,
        session,
        run_number: int,
        run_token: str,
    ) -> tuple[bool, str | None, str | None]:
        worker_claimed = self._session_manager.claim_worker(
            session,
            run_number,
            run_token,
        )
        if not worker_claimed:
            error = "Unable to claim authorization worker."
            self._session_manager.fail(
                session,
                error=error,
                final_reason="CONFIGURATION_ERROR",
                retryable=False,
                run_number=run_number,
                run_token=run_token,
            )
            self._session_manager.mark_worker_finished(
                session,
                run_number=run_number,
                run_token=run_token,
            )
            self._emit_run_start_failure(
                session,
                run_number,
                "CONFIGURATION_ERROR",
                False,
                error,
            )
            return False, "CONFIGURATION_ERROR", error

        try:
            guarded_process = partial(
                self._auth_worker.process,
                run_number=run_number,
                run_token=run_token,
            )
            self._executor.submit(
                guarded_process,
                session.session_id,
            )
            return True, None, None
        except Exception as exc:
            error = f"Worker submission failed: {exc}"
            self._session_manager.fail(
                session,
                error=error,
                final_reason="WORKER_START_FAILED",
                retryable=True,
                run_number=run_number,
                run_token=run_token,
            )
            self._session_manager.mark_worker_finished(
                session,
                run_number=run_number,
                run_token=run_token,
            )
            self._emit_run_start_failure(
                session,
                run_number,
                "WORKER_START_FAILED",
                True,
                error,
            )
            return False, "WORKER_START_FAILED", error

    def _emit_run_start_failure(
        self,
        session,
        run_number: int,
        final_reason: str,
        retryable: bool,
        error: str,
    ) -> None:
        run = self._session_manager.run_snapshot(
            session,
            run_number,
        ) or {}
        self._auth_telemetry.safe_emit(
            telemetry_events.RUN_FINISHED,
            session.session_id,
            "warning" if retryable else "error",
            site_id=session.site_id,
            client_mac=session.client_mac,
            client_ip=session.client_ip,
            run_number=run_number,
            auth_attempt=0,
            retry_request_id=run.get("retry_request_id"),
            final_state=session.status.value,
            final_reason=final_reason,
            retryable=retryable,
            duration_ms=0,
            readiness_checks=0,
            auth_attempts=0,
            error=error,
        )
        if not retryable:
            self._auth_telemetry.safe_emit_once(
                telemetry_events.SESSION_FINISHED,
                session.session_id,
                "error",
                site_id=session.site_id,
                client_mac=session.client_mac,
                client_ip=session.client_ip,
                run_number=run_number,
                auth_attempt=0,
                final_state=session.status.value,
                final_reason=final_reason,
                retryable=False,
                error=error,
            )

    def _session_result(
        self,
        session,
        *,
        status_code: int,
        error_message: str,
        error_code: str,
    ) -> PortalEntryResult:
        snapshot = self._session_manager.snapshot(session)
        if snapshot is None:
            snapshot = session.to_dict()
        return PortalEntryResult(
            session_id=session.session_id,
            redirect_url=session.redirect_url,
            initial_state=dict(snapshot),
            status_code=status_code,
            error_message=error_message,
            error_code=error_code,
        )

    @staticmethod
    def _failure_result(
        message: str,
        status_code: int,
        *,
        redirect_url: str | None = None,
        error_code: str,
    ) -> PortalEntryResult:
        return PortalEntryResult(
            session_id=None,
            redirect_url=redirect_url,
            initial_state={
                "state": "FAILED",
                "status": "FAILED",
                "retryable": False,
                "progress": 100,
                "terminal": True,
            },
            status_code=status_code,
            error_message=message,
            error_code=error_code,
        )
