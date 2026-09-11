from __future__ import annotations

import io
import json
import logging

from app.traffic_projection.telemetry import (
    TrafficProjectionTelemetry,
    configure_traffic_projection_logger,
)


class ClosingHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.was_closed = False

    def emit(self, _record):
        pass

    def close(self):
        self.was_closed = True
        super().close()


def test_projection_logger_owns_one_plain_message_handler(capsys):
    logger = logging.getLogger("captivportal.traffic_projection")
    old = ClosingHandler()
    logger.handlers[:] = [old, logging.NullHandler()]

    configured = configure_traffic_projection_logger()
    assert configured is logger
    assert logger.name == "captivportal.traffic_projection"
    assert logger.level == logging.INFO
    assert logger.propagate is False
    assert len(logger.handlers) == 1
    assert type(logger.handlers[0]) is logging.StreamHandler
    assert logger.handlers[0].level == logging.INFO
    assert logger.handlers[0].formatter._fmt == "%(message)s"
    assert old.was_closed is True

    configure_traffic_projection_logger()
    assert len(logger.handlers) == 1
    TrafficProjectionTelemetry(logger).emit("traffic_projection_test", status="ok")
    line = capsys.readouterr().err.strip()
    assert json.loads(line) == {"event": "traffic_projection_test", "status": "ok"}
    assert len(line.splitlines()) == 1


def _capture_logger():
    stream = io.StringIO()
    logger = logging.Logger("test-projection")
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger, stream


def test_telemetry_emits_canonical_safe_json_and_runtime_identity():
    logger, stream = _capture_logger()
    telemetry = TrafficProjectionTelemetry(
        logger,
        runtime_fields={
            "artifact_sha": "a" * 40,
            "artifact_tree": "b" * 40,
            "service_name": "worker",
            "process_started_at": "2026-09-11T12:00:00.000Z",
            "unknown": "omit",
        },
    )
    telemetry.emit(
        "traffic_projection_product_health",
        artifact_sha="c" * 40,
        site_id="site-a",
        reconcile_sweep_from_utc="2026-09-01T00:00:00.000Z",
        reconcile_cursor_cycle_id="cycle-a",
        source_count=4,
        projection_count=3,
        count_delta=1,
        error_category="x" * 300,
        duration_ms=float("nan"),
        unsupported=object(),
    )
    raw = stream.getvalue().strip()
    assert "\n" not in raw
    payload = json.loads(raw)
    assert payload["artifact_sha"] == "a" * 40
    assert payload["artifact_tree"] == "b" * 40
    assert payload["service_name"] == "worker"
    assert payload["source_count"] == 4
    assert payload["projection_count"] == 3
    assert payload["count_delta"] == 1
    assert len(payload["error_category"]) == 256
    assert "duration_ms" not in payload
    assert "unsupported" not in payload


def test_identity_optional_telemetry_omits_runtime_keys():
    logger, stream = _capture_logger()
    TrafficProjectionTelemetry(logger).emit(
        "traffic_projection_scan_failed",
        projection_version="v1",
        error_category=None,
    )
    payload = json.loads(stream.getvalue())
    assert payload == {
        "error_category": None,
        "event": "traffic_projection_scan_failed",
        "projection_version": "v1",
    }
    assert not {
        "artifact_sha", "artifact_tree", "service_name", "process_started_at"
    } & payload.keys()


def test_telemetry_normalization_never_raises_into_business_logic():
    class BrokenLogger:
        def info(self, *_args, **_kwargs):
            raise RuntimeError("logging unavailable")

    telemetry = TrafficProjectionTelemetry(BrokenLogger())
    telemetry.emit("traffic_projection_test", status=object())
