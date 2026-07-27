"""Shared entry into the existing AuthSession/AuthWorker portal flow."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from flask import render_template

from app.auth.worker import log_auth_event
from app.auth_telemetry import events as telemetry_events
from app.logger import logger


@dataclass(frozen=True)
class PortalClientContext:
    site_id: str
    client_mac: str
    client_ip: str | None = None
    ap_mac: str | None = None
    ssid: str | None = None
    redirect_url: str | None = None
    radio_id: str | None = None


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
                response = self._start_worker(session)
                if response is not None:
                    return response

            snapshot = self._session_manager.snapshot(session)
            if snapshot is None:
                return self._error_page(
                    "Сессия подключения не найдена.",
                    500,
                    redirect_url=context.redirect_url,
                )

            return render_template(
                "portal.html",
                session_id=session.session_id,
                redirect_url=session.redirect_url,
                initial_status=snapshot["status"],
                initial_progress=snapshot["progress"],
                error_message=None,
            )
        except ValueError as exc:
            logger.warning(
                "portal_entry.invalid_client site=%s mac=%s error=%s",
                context.site_id,
                context.client_mac,
                exc,
            )
            return self._error_page(
                "Неверные данные клиента.",
                400,
                redirect_url=context.redirect_url,
            )
        except Exception:
            logger.exception(
                "portal_entry.unexpected_error site=%s mac=%s",
                context.site_id,
                context.client_mac,
            )
            return self._error_page(
                "Внутренняя ошибка сервера.",
                500,
                redirect_url=context.redirect_url,
            )

    def _start_worker(self, session):
        worker_claimed = self._session_manager.claim_worker(session)
        if not worker_claimed:
            self._session_manager.fail(
                session,
                error="Unable to claim authorization worker.",
            )
            self._emit_internal_failure(
                session,
                "Unable to claim authorization worker.",
            )
            return self._error_page(
                "Не удалось запустить процесс подключения.",
                500,
                session=session,
            )

        try:
            self._executor.submit(
                self._auth_worker.process,
                session.session_id,
            )
            return None
        except Exception as exc:
            self._session_manager.fail(
                session,
                error=f"Worker submission failed: {exc}",
            )
            self._session_manager.mark_worker_finished(session)
            self._emit_internal_failure(session, str(exc))
            return self._error_page(
                "Системная ошибка запуска подключения.",
                500,
                session=session,
            )

    def _emit_internal_failure(self, session, error: str) -> None:
        self._auth_telemetry.safe_emit_once(
            telemetry_events.SESSION_FINISHED,
            session.session_id,
            "error",
            site_id=session.site_id,
            client_mac=session.client_mac,
            client_ip=session.client_ip,
            final_state=session.status.value,
            final_reason="INTERNAL_ERROR",
            duration_ms=0,
            readiness_checks=0,
            auth_attempts=0,
            error=error,
        )

    @staticmethod
    def _error_page(
        message: str,
        status_code: int,
        *,
        redirect_url: str | None = None,
        session=None,
    ):
        return render_template(
            "portal.html",
            session_id=(
                session.session_id if session is not None else None
            ),
            redirect_url=(
                session.redirect_url
                if session is not None
                else redirect_url
            ),
            initial_status=(
                session.status.value
                if session is not None
                else "FAILED"
            ),
            initial_progress=(
                session.progress if session is not None else 100
            ),
            error_message=message,
        ), status_code
