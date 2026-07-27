from pathlib import Path
from unittest.mock import Mock

from flask import Flask

from app.auth.manager import AuthSessionManager
from app.auth.session import AuthStatus
from app.web.portal_entry import (
    PortalClientContext,
    PortalEntryHandler,
)


class FailingExecutor:
    def submit(self, *args, **kwargs):
        raise RuntimeError("executor unavailable")


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
