import json
import logging
import threading
import uuid
from unittest.mock import patch

import pytest
from flask import Flask

from app.integrations.omada import (
    OmadaWebhookConfig,
    OmadaWebhookJournal,
    OmadaWebhookNormalizedJournal,
    OmadaWebhookProcessor,
    OmadaWebhookReceiver,
    create_omada_webhook_blueprint,
)
from app.integrations.omada.webhook_normalized_journal import (
    NormalizedJournalWriteError,
)
from app.integrations.omada.webhook_routes import WEBHOOK_PATH


ALLOWED_IP = "192.168.0.222"
ONLINE = (
    "[client:Galaxy-A24:32-84-C9-40-38-88] "
    "(IP: 192.168.1.96) went online on "
    "[ap:EC-75-0C-18-6F-F8:EC-75-0C-18-6F-F8] "
    'with SSID "Zefer_Parki" on channel 64.'
)
UNAUTHORIZED = (
    "[client:12-4E-9B-DE-22-A7] "
    "was unauthorized by Main Administrator "
    "z******vi@gmail.com."
)


def build_app(tmp_path, *, normalized_journal=None, logger=None):
    raw_path = tmp_path / "omada_webhook.log"
    normalized_path = tmp_path / "omada_webhook_normalized.log"
    config = OmadaWebhookConfig.from_settings({
        "omada_webhook_enabled": True,
        "omada_webhook_allowed_ips": ALLOWED_IP,
        "omada_webhook_auth_mode": "ip_only",
        "omada_webhook_shared_secret": "",
        "omada_webhook_header_token": "",
        "omada_webhook_max_body_bytes": 1_048_576,
        "omada_webhook_log_file": str(raw_path),
        "omada_webhook_normalized_log_file": str(
            normalized_path
        ),
    })
    raw_journal = OmadaWebhookJournal(str(raw_path))
    normalized_journal = (
        normalized_journal
        or OmadaWebhookNormalizedJournal(str(normalized_path))
    )
    processor = OmadaWebhookProcessor(normalized_journal)
    logger = logger or logging.getLogger(
        f"test.omada.normalized.{uuid.uuid4()}"
    )
    logger.setLevel(logging.DEBUG)
    receiver = OmadaWebhookReceiver(
        config=config,
        journal=raw_journal,
        logger=logger,
        processor=processor,
    )
    app = Flask(__name__)
    app.register_blueprint(
        create_omada_webhook_blueprint(
            config=config,
            receiver=receiver,
            logger=logger,
        )
    )
    app.config["TESTING"] = True
    return app, raw_path, normalized_path


def payload():
    return {
        "Site": "Home",
        "description": "Omada webhook",
        "shardSecret": "live-secret",
        "text": [ONLINE, UNAUTHORIZED],
        "Controller": "Omada Controller_051C41",
        "timestamp": 1_785_238_468_934,
    }


def post(app):
    return app.test_client(use_cookies=False).post(
        WEBHOOK_PATH,
        json=payload(),
        environ_base={"REMOTE_ADDR": ALLOWED_IP},
    )


def records(path):
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


def captured_events(caplog, event_name):
    return [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.getMessage().startswith("{")
        and json.loads(record.getMessage()).get("event")
        == event_name
    ]


def test_live_receiver_writes_raw_first_and_one_normalized_line_per_text(
    tmp_path,
):
    app, raw_path, normalized_path = build_app(tmp_path)

    response = post(app)
    raw_events = records(raw_path)
    normalized = records(normalized_path)

    assert response.status_code == 204
    assert len(raw_events) == 1
    assert raw_events[0]["event"] == "omada.webhook_received"
    assert raw_events[0]["parsed_payload"]["shardSecret"] == (
        "***REDACTED***"
    )
    assert len(normalized) == 2
    assert [event["event"] for event in normalized] == [
        "omada.client_online",
        "omada.client_unauthorized",
    ]
    assert normalized[0]["webhook_id"] == raw_events[0]["webhook_id"]
    assert normalized[1]["webhook_id"] == raw_events[0]["webhook_id"]
    assert [event["text_index"] for event in normalized] == [0, 1]
    normalized_bytes = normalized_path.read_bytes()
    assert b"live-secret" not in normalized_bytes
    assert b"shardSecret" not in normalized_bytes


def test_normalization_failure_keeps_raw_and_returns_204(
    tmp_path,
    caplog,
):
    logger = logging.getLogger(
        f"test.omada.normalization.failure.{uuid.uuid4()}"
    )
    app, raw_path, normalized_path = build_app(
        tmp_path,
        logger=logger,
    )

    with (
        patch(
            "app.integrations.omada.webhook_processor."
            "normalize_webhook",
            side_effect=RuntimeError("must-not-enter-log"),
        ),
        caplog.at_level(logging.ERROR, logger=logger.name),
    ):
        response = post(app)

    assert response.status_code == 204
    assert len(records(raw_path)) == 1
    assert not normalized_path.exists()
    failure_events = captured_events(
        caplog,
        "omada.webhook_normalization_failed",
    )
    assert len(failure_events) == 1
    event = failure_events[0]
    raw = records(raw_path)[0]
    assert event["webhook_id"] == raw["webhook_id"]
    assert event["payload_sha256"] == raw["payload_sha256"]
    assert event["exception_type"] == "RuntimeError"
    assert event["error_code"] == "NORMALIZATION_FAILED"
    assert captured_events(
        caplog,
        "omada.webhook_processing_failed",
    ) == []
    assert "must-not-enter-log" not in caplog.text
    assert "live-secret" not in caplog.text


class FailingNormalizedJournal:
    log_file = "/safe/normalized/path.log"

    def append_many(self, events):
        raise NormalizedJournalWriteError(
            normalized_event_id=events[0]["normalized_event_id"],
            target_path=self.log_file,
            exception_type="OSError",
        )


def test_normalized_write_failure_keeps_raw_and_returns_204(
    tmp_path,
    caplog,
):
    logger = logging.getLogger(
        f"test.omada.normalized.write.failure.{uuid.uuid4()}"
    )
    app, raw_path, normalized_path = build_app(
        tmp_path,
        normalized_journal=FailingNormalizedJournal(),
        logger=logger,
    )

    with caplog.at_level(logging.ERROR, logger=logger.name):
        response = post(app)

    assert response.status_code == 204
    assert len(records(raw_path)) == 1
    assert not normalized_path.exists()
    failure_events = captured_events(
        caplog,
        "omada.webhook_normalized_write_failed",
    )
    assert len(failure_events) == 1
    event = failure_events[0]
    assert event["webhook_id"] == records(raw_path)[0]["webhook_id"]
    assert event["normalized_event_id"].endswith(":0")
    assert event["target_path"] == "/safe/normalized/path.log"
    assert event["exception_type"] == "OSError"
    assert event["error_code"] == "NORMALIZED_LOG_WRITE_FAILED"
    assert captured_events(
        caplog,
        "omada.webhook_processing_failed",
    ) == []
    assert "live-secret" not in caplog.text


def test_writer_keeps_each_concurrent_batch_contiguous(tmp_path):
    path = tmp_path / "normalized.log"
    journal = OmadaWebhookNormalizedJournal(str(path))
    barrier = threading.Barrier(5)

    def write_batch(batch_number):
        barrier.wait()
        journal.append_many([
            {
                "normalized_event_id": f"{batch_number}:0",
                "batch": batch_number,
                "index": 0,
            },
            {
                "normalized_event_id": f"{batch_number}:1",
                "batch": batch_number,
                "index": 1,
            },
        ])

    threads = [
        threading.Thread(target=write_batch, args=(number,))
        for number in range(4)
    ]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(timeout=5)
        assert not thread.is_alive()
    journal.close()

    written = records(path)
    assert len(written) == 8
    positions = {}
    for position, event in enumerate(written):
        positions.setdefault(event["batch"], []).append(position)
    assert all(
        batch_positions[1] == batch_positions[0] + 1
        for batch_positions in positions.values()
    )


def test_batch_writer_can_leave_valid_prefix_and_reports_failed_id(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "normalized.log"
    journal = OmadaWebhookNormalizedJournal(str(path))
    handler = journal._get_handler()
    original_emit = handler.emit
    emit_count = 0

    def fail_second_emit(record):
        nonlocal emit_count
        emit_count += 1
        if emit_count == 2:
            raise OSError("simulated second-event failure")
        original_emit(record)

    monkeypatch.setattr(handler, "emit", fail_second_emit)
    batch = [
        {
            "normalized_event_id": "webhook-id:0",
            "event": "first",
        },
        {
            "normalized_event_id": "webhook-id:1",
            "event": "second",
        },
    ]

    with pytest.raises(NormalizedJournalWriteError) as error:
        journal.append_many(batch)
    journal.close()

    assert error.value.normalized_event_id == "webhook-id:1"
    assert error.value.target_path == str(path)
    assert error.value.exception_type == "OSError"
    assert records(path) == [batch[0]]
