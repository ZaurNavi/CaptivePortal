from pathlib import Path
from unittest.mock import Mock, patch

from flask import Flask

from app.auth.manager import (
    AuthSessionManager,
    SESSION_TTL_SECONDS,
)
from app.auth.session import AuthStatus
from app.auth_telemetry import events as telemetry_events
from app.web.portal_entry import (
    PortalClientContext,
    PortalEntryHandler,
)


class FailingExecutor:
    def submit(self, *args, **kwargs):
        raise RuntimeError("executor unavailable")


class CapturingExecutor:
    def __init__(self):
        self.submissions = []

    def submit(self, function, session_id):
        self.submissions.append((function, session_id))
        return object()


def test_worker_submit_failure_finishes_session_safely():
    manager = AuthSessionManager()
    telemetry = Mock()
    handler = PortalEntryHandler(
        session_manager=manager,
        auth_worker=Mock(),
        executor=FailingExecutor(),
        auth_telemetry=telemetry,
    )
    template_dir = (
        Path(__file__).parents[1] / "app" / "web" / "templates"
    )
    app = Flask(__name__, template_folder=str(template_dir))

    with app.test_request_context("/"):
        response, status_code = handler.open_portal(
            PortalClientContext(
                site_id="site-1",
                client_mac="AA:BB:CC:DD:EE:FF",
                client_ip="192.168.1.10",
            )
        )

    session = manager.get_by_client(
        "site-1",
        "AA:BB:CC:DD:EE:FF",
    )
    assert status_code == 500
    assert "Системная ошибка" in response
    assert session.status == AuthStatus.FAILED
    assert session.retryable is True
    assert session.final_reason == "WORKER_START_FAILED"
    assert session._worker_finished is True
    telemetry.safe_emit.assert_called_once()


def test_expired_portal_entry_starts_new_session_without_expired_page():
    manager = AuthSessionManager()
    executor = CapturingExecutor()
    handler = PortalEntryHandler(
        session_manager=manager,
        auth_worker=Mock(),
        executor=executor,
        auth_telemetry=Mock(),
    )
    template_dir = (
        Path(__file__).parents[1] / "app" / "web" / "templates"
    )
    app = Flask(__name__, template_folder=str(template_dir))
    context = PortalClientContext(
        site_id="site-1",
        client_mac="AA:BB:CC:DD:EE:FF",
        client_ip="192.168.1.10",
    )

    with (
        app.test_request_context("/"),
        patch("app.web.portal_entry.log_auth_event") as log_auth_event,
    ):
        first_html = handler.open_portal(context)
        old_session = manager.get_by_client(
            context.site_id,
            context.client_mac,
        )
        old_session._created_monotonic -= SESSION_TTL_SECONDS + 1
        second_html = handler.open_portal(context)

    new_session = manager.get_by_client(
        context.site_id,
        context.client_mac,
    )
    new_snapshot = manager.snapshot(new_session)

    assert old_session.session_id in first_html
    assert new_session.session_id != old_session.session_id
    assert old_session.session_id not in second_html
    assert new_session.session_id in second_html
    assert new_snapshot["state"] == "WAITING"
    assert new_session.is_active() is True
    assert old_session.status == AuthStatus.EXPIRED
    logged_events = [
        (call.args[0], call.args[1].session_id)
        for call in log_auth_event.call_args_list
    ]
    assert logged_events.count(
        (telemetry_events.SESSION_CREATED, new_session.session_id)
    ) == 1
    assert not any(
        event == telemetry_events.SESSION_REUSED
        for event, _session_id in logged_events
    )
    assert [
        session_id
        for _function, session_id in executor.submissions
    ].count(new_session.session_id) == 1
    assert len(executor.submissions) == 2
