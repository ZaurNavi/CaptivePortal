"""JSON Lines formatter."""

import json
import logging


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = record.msg if isinstance(record.msg, dict) else {
            "event": "auth.telemetry_format_error",
            "error": "Telemetry payload was not a dictionary.",
        }
        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )
