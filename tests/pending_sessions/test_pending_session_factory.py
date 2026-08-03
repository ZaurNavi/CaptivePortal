from app.pending_sessions.factory import (
    DisabledPendingSessionCleaner,
    UnavailablePendingSessionCleaner,
    create_pending_session_cleaner,
)


class Telemetry:
    def __init__(self):
        self.calls = []

    def safe_emit_system(self, event, *, level="info", **fields):
        self.calls.append((event, level, fields))
        return True


def test_disabled_factory_has_no_thread_journal_or_provider_calls(tmp_path):
    path = tmp_path / "must-not-exist.log"
    telemetry = Telemetry()

    component = create_pending_session_cleaner(
        settings={
            "pending_session_cleaner_enabled": "false",
            "pending_session_cleaner_log_file": str(path),
        },
        provider=object(),
        auth_manager=object(),
        telemetry=telemetry,
    )

    assert isinstance(component, DisabledPendingSessionCleaner)
    assert component.start() is False
    assert component.run_once() is None
    assert component.stop(1) is True
    assert path.exists() is False


def test_invalid_enabled_config_is_unavailable_and_fail_open():
    telemetry = Telemetry()
    component = create_pending_session_cleaner(
        settings={"pending_session_cleaner_enabled": "true"},
        provider=object(),
        auth_manager=object(),
        telemetry=telemetry,
    )

    assert isinstance(component, UnavailablePendingSessionCleaner)
    assert component.start() is False
    assert component.stop(1) is True
    assert telemetry.calls[0][0] == (
        "pending_session_cleaner_unavailable"
    )
