import json

from app.auth_telemetry.service import AuthorizationTelemetry


def test_system_event_omits_session_but_auth_event_keeps_it(
    tmp_path,
):
    log_path = tmp_path / "telemetry.log"
    telemetry = AuthorizationTelemetry(
        enabled=True,
        log_path=str(log_path),
        level="INFO",
    )

    assert telemetry.safe_emit_system(
        "capport.api_request",
        client_ip="192.168.1.10",
    )
    assert telemetry.safe_emit(
        "auth.session_created",
        "session-1",
        client_ip="192.168.1.10",
    )

    records = [
        json.loads(line)
        for line in log_path.read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    assert len(records) == 2
    assert records[0]["event"] == "capport.api_request"
    assert "session_id" not in records[0]
    assert records[1]["event"] == "auth.session_created"
    assert records[1]["session_id"] == "session-1"

    AuthorizationTelemetry(enabled=False, log_path="")
