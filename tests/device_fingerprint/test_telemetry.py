import json
import logging

from app.device_fingerprint.telemetry import DeviceFingerprintTelemetry


class Handler(logging.Handler):
    def __init__(self):
        super().__init__(); self.messages = []
    def emit(self, record):
        self.messages.append(record.getMessage())


def test_telemetry_omits_payload_secret_mac_ip_and_unknown_fields():
    logger = logging.Logger("safe"); handler = Handler(); logger.addHandler(handler)
    telemetry = DeviceFingerprintTelemetry(logger)
    telemetry.emit("device_fingerprint_ingest_completed", producer_id="sensor", payload={"secret": True}, bearer_token="secret", observed_mac="AA:BB", observed_ip="1.2.3.4", inserted=1)
    result = json.loads(handler.messages[0])
    assert result == {"event": "device_fingerprint_ingest_completed", "inserted": 1, "producer_id": "sensor"}
