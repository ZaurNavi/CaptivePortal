import logging

from app.device_fingerprint_portal.telemetry import PortalEvidenceTelemetry


def test_telemetry_is_safe_field_only(caplog):
    telemetry=PortalEvidenceTelemetry(logging.getLogger("portal-test"))
    with caplog.at_level(logging.INFO, logger="portal-test"):
        telemetry.emit("event", events_queued=1, observed_mac="AA:BB", raw_user_agent="SECRET", model_family="SECRET-MODEL", authorization="Bearer SECRET")
    text=caplog.text
    assert "events_queued" in text
    assert "AA:BB" not in text and "SECRET" not in text
