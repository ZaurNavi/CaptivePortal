import base64
import hashlib
import io
import json
import logging
import os
import stat
import threading
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from flask import Flask, Response
from werkzeug.test import create_environ

from app.integrations.omada import (
    OmadaWebhookConfig,
    OmadaWebhookJournal,
    OmadaWebhookReceiver,
    create_omada_webhook_blueprint,
)
from app.integrations.omada.webhook_routes import WEBHOOK_PATH


ALLOWED_IP = "192.168.0.222"
FORBIDDEN_IP = "192.168.0.99"


def settings(log_path: Path, **overrides):
    values = {
        "omada_webhook_enabled": True,
        "omada_webhook_allowed_ips": ALLOWED_IP,
        "omada_webhook_auth_mode": "ip_only",
        "omada_webhook_shared_secret": "",
        "omada_webhook_header_token": "",
        "omada_webhook_max_body_bytes": 1_048_576,
        "omada_webhook_log_file": str(log_path),
        "omada_webhook_normalized_log_file": str(
            log_path.with_name(
                f"{log_path.stem}_normalized{log_path.suffix}"
            )
        ),
    }
    values.update(overrides)
    return values


def webhook_app(
    tmp_path,
    *,
    journal=None,
    processor=None,
    logger=None,
    **config_overrides,
):
    log_path = tmp_path / "omada_webhook.log"
    config = OmadaWebhookConfig.from_settings(
        settings(log_path, **config_overrides)
    )
    journal = journal or OmadaWebhookJournal(str(log_path))
    logger = logger or logging.getLogger(
        f"test.omada_webhook.{uuid.uuid4()}"
    )
    logger.setLevel(logging.DEBUG)
    if processor is None:
        receiver = OmadaWebhookReceiver(
            config=config,
            journal=journal,
            logger=logger,
        )
    else:
        receiver = OmadaWebhookReceiver(
            config=config,
            journal=journal,
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
    return app, log_path, journal


def post(
    app,
    body,
    *,
    remote_addr=ALLOWED_IP,
    content_type="application/json",
    headers=None,
    path=WEBHOOK_PATH,
):
    return app.test_client(use_cookies=False).post(
        path,
        data=body,
        content_type=content_type,
        headers=headers or {},
        environ_base={"REMOTE_ADDR": remote_addr},
    )


def records(log_path):
    if not log_path.exists():
        return []
    return [
        strict_json_loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
    ]


def strict_json_loads(value):
    def reject_constant(constant):
        raise ValueError(
            f"Non-standard JSON constant in JSONL: {constant}"
        )

    return json.loads(
        value,
        parse_constant=reject_constant,
    )


def captured_events(caplog, event):
    found = []
    for log_record in caplog.records:
        try:
            payload = json.loads(log_record.getMessage())
        except (TypeError, json.JSONDecodeError):
            continue
        if payload.get("event") == event:
            found.append(payload)
    return found


def test_valid_json_is_persisted_as_a_complete_envelope(tmp_path):
    app, log_path, _journal = webhook_app(tmp_path)
    body = b'{"event":"client.connected","unknown":{"answer":42}}'

    response = post(
        app,
        body,
        headers={"User-Agent": "Omada-Test/1.0"},
    )

    assert response.status_code == 204
    assert response.data == b""
    record = records(log_path)[0]
    assert record["level"] == "info"
    assert record["service"] == "captive_portal"
    assert record["module"] == "omada_webhook"
    assert record["event"] == "omada.webhook_received"
    assert record["schema_version"] == 1
    assert uuid.UUID(record["webhook_id"])
    assert record["received_at"].endswith("Z")
    assert record["source_ip"] == ALLOWED_IP
    assert record["http_method"] == "POST"
    assert record["request_path"] == WEBHOOK_PATH
    assert record["content_type"] == "application/json"
    assert record["content_length"] == len(body)
    assert record["actual_body_length"] == len(body)
    assert record["user_agent"] == "Omada-Test/1.0"
    assert record["payload_sha256"] == hashlib.sha256(body).hexdigest()
    assert record["payload_format"] == "json"
    assert record["body_encoding"] == "utf-8"
    assert record["parsed_payload"]["unknown"] == {"answer": 42}
    assert record["raw_body"] == body.decode("utf-8")
    assert record["raw_body_base64"] is None
    assert record["parse_error"] is None
    assert record["decode_error"] is None


def test_unknown_json_fields_are_not_rejected_or_removed(tmp_path):
    app, log_path, _journal = webhook_app(tmp_path)
    payload = {
        "futureOmadaField": {"nested": ["a", 2, False]},
        "anotherUnknown": None,
    }

    response = post(app, json.dumps(payload).encode())

    assert response.status_code == 204
    assert records(log_path)[0]["parsed_payload"] == payload


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (b"null", None),
        (b"true", True),
        (b"42", 42),
        (b'"text"', "text"),
        (b'[1,{"newField":"kept"}]', [1, {"newField": "kept"}]),
    ],
)
def test_valid_json_primitives_and_arrays_are_accepted(
    tmp_path,
    body,
    expected,
):
    app, log_path, _journal = webhook_app(tmp_path)

    response = post(app, body)

    assert response.status_code == 204
    assert records(log_path)[0]["parsed_payload"] == expected


def test_invalid_json_is_saved_as_utf8_text(tmp_path):
    app, log_path, _journal = webhook_app(tmp_path)
    body = "not-json: gələcək sahə".encode("utf-8")

    response = post(app, body)

    assert response.status_code == 204
    record = records(log_path)[0]
    assert record["payload_format"] == "text"
    assert record["raw_body"] == body.decode("utf-8")
    assert record["parsed_payload"] is None
    assert record["parse_error"] == "invalid_json"
    assert record["decode_error"] is None


@pytest.mark.parametrize(
    "body",
    [
        b'{"value":NaN}',
        b'{"value":Infinity}',
        b'{"value":-Infinity}',
    ],
)
def test_non_standard_json_constants_are_saved_as_text(
    tmp_path,
    body,
):
    app, log_path, _journal = webhook_app(tmp_path)

    response = post(app, body)

    assert response.status_code == 204
    record = records(log_path)[0]
    assert record["payload_format"] == "text"
    assert record["raw_body"] == body.decode("utf-8")
    assert record["parsed_payload"] is None
    assert record["parse_error"] == "invalid_json"


def test_surrogate_escape_produces_valid_utf8_jsonl(tmp_path):
    app, log_path, _journal = webhook_app(tmp_path)
    body = b'"\\ud800"'

    response = post(app, body)

    assert response.status_code == 204
    raw_journal = log_path.read_bytes()
    raw_journal.decode("utf-8", errors="strict")
    record = records(log_path)[0]
    assert record["payload_format"] == "json"
    assert record["parsed_payload"] == "\ud800"
    assert record["raw_body"] == body.decode("ascii")


def test_invalid_utf8_is_saved_as_base64(tmp_path):
    app, log_path, _journal = webhook_app(tmp_path)
    body = b"\xff\xfe\x80omada"

    response = post(app, body, content_type="application/octet-stream")

    assert response.status_code == 204
    record = records(log_path)[0]
    assert record["payload_format"] == "binary"
    assert record["body_encoding"] == "base64"
    assert record["raw_body"] is None
    assert record["raw_body_base64"] == base64.b64encode(body).decode()
    assert record["parsed_payload"] is None
    assert record["decode_error"] == "invalid_utf8"


def test_allowed_ip_is_accepted_and_forbidden_ip_is_not_persisted(
    tmp_path,
    caplog,
):
    app, log_path, _journal = webhook_app(tmp_path)

    accepted = post(app, b"{}", remote_addr=ALLOWED_IP)
    with caplog.at_level(logging.WARNING):
        rejected = post(
            app,
            b'{"must":"not be read"}',
            remote_addr=FORBIDDEN_IP,
        )

    assert accepted.status_code == 204
    assert rejected.status_code == 403
    assert len(records(log_path)) == 1
    assert "must" not in log_path.read_text(encoding="utf-8")
    rejection = captured_events(
        caplog,
        "omada.webhook_rejected",
    )[-1]
    assert rejection["rejection_reason"] == "source_ip_not_allowed"
    assert "reason" not in rejection


def test_empty_allowed_ip_list_denies_every_source(tmp_path):
    app, log_path, _journal = webhook_app(
        tmp_path,
        omada_webhook_allowed_ips="",
    )

    response = post(app, b"{}")

    assert response.status_code == 403
    assert records(log_path) == []


def test_allowed_ip_list_supports_commas_and_whitespace(tmp_path):
    app, log_path, _journal = webhook_app(
        tmp_path,
        omada_webhook_allowed_ips=(
            f"  {FORBIDDEN_IP},  {ALLOWED_IP}  "
        ),
    )

    response = post(app, b"{}")

    assert response.status_code == 204
    assert len(records(log_path)) == 1


def test_spoofed_forwarded_for_is_not_read_by_receiver(tmp_path):
    app, log_path, _journal = webhook_app(tmp_path)

    response = post(
        app,
        b"{}",
        remote_addr=FORBIDDEN_IP,
        headers={"X-Forwarded-For": ALLOWED_IP},
    )

    assert response.status_code == 403
    assert records(log_path) == []


@pytest.mark.parametrize(
    "method",
    ["GET", "HEAD", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE"],
)
def test_non_post_methods_return_405_without_persisting_body(
    tmp_path,
    method,
    caplog,
):
    app, log_path, _journal = webhook_app(tmp_path)

    with caplog.at_level(logging.WARNING):
        response = app.test_client().open(
            WEBHOOK_PATH,
            method=method,
            data=b'{"must":"not be stored"}',
            environ_base={"REMOTE_ADDR": ALLOWED_IP},
        )

    assert response.status_code == 405
    assert response.headers["Allow"] == "POST"
    assert records(log_path) == []
    rejection = captured_events(
        caplog,
        "omada.webhook_rejected",
    )[-1]
    assert rejection["rejection_reason"] == "method_not_allowed"
    assert rejection["http_method"] == method


def test_arbitrary_propfind_method_uses_webhook_405_contract(
    tmp_path,
    caplog,
):
    app, log_path, _journal = webhook_app(tmp_path)

    with caplog.at_level(logging.WARNING):
        response = app.test_client().open(
            WEBHOOK_PATH,
            method="PROPFIND",
            data=b'{"must":"not be stored"}',
            environ_base={"REMOTE_ADDR": ALLOWED_IP},
        )

    assert response.status_code == 405
    assert response.headers["Allow"] == "POST"
    assert records(log_path) == []
    rejection = captured_events(
        caplog,
        "omada.webhook_rejected",
    )[-1]
    assert rejection["http_method"] == "PROPFIND"
    assert rejection["rejection_reason"] == "method_not_allowed"


def test_declared_body_over_limit_is_rejected_before_read(tmp_path):
    app, log_path, _journal = webhook_app(
        tmp_path,
        omada_webhook_max_body_bytes=8,
    )

    response = post(app, b"123456789", content_type="text/plain")

    assert response.status_code == 413
    assert records(log_path) == []


def test_terminated_body_over_limit_without_content_length_is_rejected(
    tmp_path,
):
    app, log_path, _journal = webhook_app(
        tmp_path,
        omada_webhook_max_body_bytes=8,
    )
    body = b"123456789"
    environ = create_environ(
        path=WEBHOOK_PATH,
        method="POST",
    )
    environ["REMOTE_ADDR"] = ALLOWED_IP
    environ["wsgi.input"] = io.BytesIO(body)
    environ.pop("CONTENT_LENGTH", None)
    environ["wsgi.input_terminated"] = True

    response = Response.from_app(app.wsgi_app, environ)

    assert response.status_code == 413
    assert records(log_path) == []


def test_request_stream_does_not_read_past_declared_content_length(
    tmp_path,
):
    app, log_path, _journal = webhook_app(
        tmp_path,
        omada_webhook_max_body_bytes=8,
    )
    raw_stream = io.BytesIO(b"123456789")
    environ = create_environ(
        path=WEBHOOK_PATH,
        method="POST",
    )
    environ["REMOTE_ADDR"] = ALLOWED_IP
    environ["CONTENT_LENGTH"] = "2"
    environ["wsgi.input"] = raw_stream

    response = Response.from_app(app.wsgi_app, environ)

    assert response.status_code == 204
    record = records(log_path)[0]
    assert record["content_length"] == 2
    assert record["actual_body_length"] == 2
    assert record["raw_body"] == "12"
    assert raw_stream.tell() == 2


class PartialReadStream:
    def __init__(self, body, chunk_size):
        self._body = body
        self._chunk_size = chunk_size
        self._position = 0

    def read(self, requested):
        size = min(requested, self._chunk_size)
        start = self._position
        end = min(len(self._body), start + size)
        self._position = end
        return self._body[start:end]


def test_bounded_reader_handles_partial_stream_reads(tmp_path):
    app, log_path, _journal = webhook_app(
        tmp_path,
        omada_webhook_max_body_bytes=8,
    )
    environ = create_environ(
        path=WEBHOOK_PATH,
        method="POST",
    )
    environ["REMOTE_ADDR"] = ALLOWED_IP
    environ.pop("CONTENT_LENGTH", None)
    environ["wsgi.input_terminated"] = True
    environ["wsgi.input"] = PartialReadStream(
        b"123456789",
        chunk_size=2,
    )

    response = Response.from_app(app.wsgi_app, environ)

    assert response.status_code == 413
    assert records(log_path) == []


def test_content_length_bounded_stream_handles_partial_reads(
    tmp_path,
):
    app, log_path, _journal = webhook_app(
        tmp_path,
        omada_webhook_max_body_bytes=8,
    )
    body = b'{"a":1}'
    environ = create_environ(
        path=WEBHOOK_PATH,
        method="POST",
    )
    environ["REMOTE_ADDR"] = ALLOWED_IP
    environ["CONTENT_LENGTH"] = str(len(body))
    environ["wsgi.input"] = PartialReadStream(
        body,
        chunk_size=2,
    )

    response = Response.from_app(app.wsgi_app, environ)

    assert response.status_code == 204
    record = records(log_path)[0]
    assert record["actual_body_length"] == len(body)
    assert record["parsed_payload"] == {"a": 1}


class BrokenReadStream:
    def read(self, _requested):
        raise OSError("simulated broken request body")


def test_body_read_error_returns_documented_400_invalid_request(
    tmp_path,
    caplog,
):
    app, log_path, _journal = webhook_app(tmp_path)
    environ = create_environ(
        path=WEBHOOK_PATH,
        method="POST",
    )
    environ["REMOTE_ADDR"] = ALLOWED_IP
    environ["CONTENT_LENGTH"] = "1"
    environ["wsgi.input"] = BrokenReadStream()

    with caplog.at_level(logging.WARNING):
        response = Response.from_app(app.wsgi_app, environ)

    assert response.status_code == 400
    assert records(log_path) == []
    rejection = captured_events(
        caplog,
        "omada.webhook_rejected",
    )[-1]
    assert rejection["rejection_reason"] == "invalid_request"
    assert "simulated broken request body" not in caplog.text


def test_duplicate_deliveries_get_separate_ids_and_lines(tmp_path):
    app, log_path, _journal = webhook_app(tmp_path)
    body = b'{"same":"delivery"}'

    first = post(app, body)
    second = post(app, body)

    assert first.status_code == 204
    assert second.status_code == 204
    saved = records(log_path)
    assert len(saved) == 2
    assert saved[0]["webhook_id"] != saved[1]["webhook_id"]
    assert saved[0]["payload_sha256"] == saved[1]["payload_sha256"]


def test_header_token_mode_accepts_only_constant_time_header_token(
    tmp_path,
    caplog,
):
    app, log_path, _journal = webhook_app(
        tmp_path,
        omada_webhook_auth_mode="header_token",
        omada_webhook_header_token="correct-header-token",
    )

    with caplog.at_level(logging.WARNING):
        missing = post(
            app,
            b'{"attempt":"missing"}',
            path=(
                f"{WEBHOOK_PATH}"
                "?token=correct-header-token"
            ),
        )
        wrong = post(
            app,
            b'{"attempt":"wrong"}',
            headers={"X-Omada-Webhook-Token": "wrong-token"},
        )
    accepted = post(
        app,
        b'{"attempt":"accepted"}',
        headers={
            "X-Omada-Webhook-Token": "correct-header-token",
        },
    )

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert accepted.status_code == 204
    assert {
        event["rejection_reason"]
        for event in captured_events(
            caplog,
            "omada.webhook_rejected",
        )
    } == {"invalid_token"}
    raw_log = log_path.read_text(encoding="utf-8")
    assert "correct-header-token" not in raw_log
    assert records(log_path)[0]["headers"][
        "X-Omada-Webhook-Token"
    ] == "***REDACTED***"


def test_payload_secret_is_redacted_but_hash_uses_original_bytes(
    tmp_path,
):
    secret = "top-secret-value"
    app, log_path, _journal = webhook_app(
        tmp_path,
        omada_webhook_auth_mode="omada_payload_secret",
        omada_webhook_shared_secret=secret,
    )
    body = (
        b'{ "event": "alarm", "shardSecret": '
        b'"top-secret-value", "value": 7 }'
    )

    response = post(app, body)

    assert response.status_code == 204
    raw_log = log_path.read_text(encoding="utf-8")
    assert secret not in raw_log
    record = records(log_path)[0]
    assert record["payload_sha256"] == hashlib.sha256(body).hexdigest()
    assert record["parsed_payload"]["shardSecret"] == "***REDACTED***"
    assert secret not in record["raw_body"]


def test_duplicate_sensitive_json_key_cannot_leak_from_raw_body(
    tmp_path,
):
    app, log_path, _journal = webhook_app(tmp_path)
    secret = "REAL_SECRET"
    body = (
        b'{"shardSecret":"REAL_SECRET",'
        b'"shardSecret":"***REDACTED***",'
        b'"event":"example"}'
    )

    response = post(app, body)

    assert response.status_code == 204
    raw_journal = log_path.read_text(encoding="utf-8")
    assert secret not in raw_journal
    record = records(log_path)[0]
    assert record["payload_sha256"] == hashlib.sha256(body).hexdigest()
    assert record["parsed_payload"]["shardSecret"] == (
        "***REDACTED***"
    )
    assert secret not in record["raw_body"]


def test_invalid_payload_secret_returns_401_and_writes_no_body(
    tmp_path,
    caplog,
):
    app, log_path, _journal = webhook_app(
        tmp_path,
        omada_webhook_auth_mode="omada_payload_secret",
        omada_webhook_shared_secret="expected-secret",
    )
    body = b'{"shardSecret":"wrong-secret","private":"body-value"}'

    with caplog.at_level(logging.WARNING):
        response = post(app, body)

    assert response.status_code == 401
    assert records(log_path) == []
    assert "wrong-secret" not in caplog.text
    assert "body-value" not in caplog.text
    assert "invalid_payload_secret" in caplog.text


def test_payload_secret_mode_rejects_non_object_json(tmp_path):
    app, log_path, _journal = webhook_app(
        tmp_path,
        omada_webhook_auth_mode="omada_payload_secret",
        omada_webhook_shared_secret="expected-secret",
    )

    response = post(app, b'"expected-secret"')

    assert response.status_code == 401
    assert records(log_path) == []


def test_payload_secret_mode_distinguishes_missing_secret_reason(
    tmp_path,
    caplog,
):
    app, log_path, _journal = webhook_app(
        tmp_path,
        omada_webhook_auth_mode="omada_payload_secret",
        omada_webhook_shared_secret="expected-secret",
    )

    with caplog.at_level(logging.WARNING):
        response = post(app, b'{"event":"without-secret"}')

    assert response.status_code == 401
    assert records(log_path) == []
    rejection = captured_events(
        caplog,
        "omada.webhook_rejected",
    )[-1]
    assert rejection["rejection_reason"] == "missing_payload_secret"


def test_header_query_and_nested_json_secrets_are_redacted(tmp_path):
    app, log_path, _journal = webhook_app(tmp_path)
    body = json.dumps(
        {
            "safe": "visible",
            "nested": {
                "SHARDsecret": "json-shard-value",
                "api_key": "json-api-value",
                "items": [
                    {"Access-Token": "json-token-value"},
                ],
            },
        }
    ).encode()
    path = (
        f"{WEBHOOK_PATH}?token=query-token-value"
        "&secret=query-secret-value"
        "&key=query-key-value"
        "&api_key=query-api-underscore-value"
        "&API-Key=query-api-value"
        "&apikey=query-apikey-value"
        "&access_token=query-access-underscore-value"
        "&access-token=query-access-value"
        "&safe=query-visible"
    )

    response = post(
        app,
        body,
        path=path,
        headers={
            "Authorization": "Bearer header-auth-value",
            "Proxy-Authorization": "Basic header-proxy-value",
            "Cookie": "session=header-cookie-value",
            "Set-Cookie": "server=header-set-cookie-value",
            "X-Omada-Webhook-Token": "header-token-value",
            "X-Safe-Header": "header-visible",
        },
    )

    assert response.status_code == 204
    raw_log = log_path.read_text(encoding="utf-8")
    for secret in (
        "json-shard-value",
        "json-api-value",
        "json-token-value",
        "query-token-value",
        "query-secret-value",
        "query-key-value",
        "query-api-underscore-value",
        "query-api-value",
        "query-apikey-value",
        "query-access-underscore-value",
        "query-access-value",
        "header-auth-value",
        "header-proxy-value",
        "header-cookie-value",
        "header-set-cookie-value",
        "header-token-value",
    ):
        assert secret not in raw_log
    record = records(log_path)[0]
    for key in (
        "token",
        "secret",
        "key",
        "api_key",
        "API-Key",
        "apikey",
        "access_token",
        "access-token",
    ):
        assert record["query_parameters"][key] == "***REDACTED***"
    assert record["query_parameters"]["safe"] == "query-visible"
    for key in (
        "Authorization",
        "Proxy-Authorization",
        "Cookie",
        "Set-Cookie",
        "X-Omada-Webhook-Token",
    ):
        assert record["headers"][key] == "***REDACTED***"
    assert record["headers"]["X-Safe-Header"] == "header-visible"
    assert record["parsed_payload"]["safe"] == "visible"
    assert record["parsed_payload"]["nested"]["SHARDsecret"] == (
        "***REDACTED***"
    )


def test_concurrent_deliveries_produce_complete_independent_json_lines(
    tmp_path,
):
    app, log_path, _journal = webhook_app(tmp_path)
    count = 80
    statuses = []
    statuses_lock = threading.Lock()

    def deliver(index):
        response = post(
            app,
            json.dumps({"delivery": index}).encode(),
        )
        with statuses_lock:
            statuses.append(response.status_code)

    threads = [
        threading.Thread(target=deliver, args=(index,))
        for index in range(count)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert statuses == [204] * count
    saved = records(log_path)
    assert len(saved) == count
    assert len({record["webhook_id"] for record in saved}) == count
    assert {
        record["parsed_payload"]["delivery"]
        for record in saved
    } == set(range(count))


def test_journal_rotates_and_every_resulting_line_is_valid_json(
    tmp_path,
):
    log_path = tmp_path / "rotating.log"
    journal = OmadaWebhookJournal(
        str(log_path),
        rotation_max_bytes=300,
        rotation_backup_count=3,
    )
    for index in range(20):
        journal.append(
            {
                "event": "omada.webhook_received",
                "index": index,
                "padding": "x" * 80,
            }
        )
    journal.close()

    paths = [log_path, *sorted(tmp_path.glob("rotating.log.*"))]
    assert len(paths) > 1
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            strict_json_loads(line)


def test_journal_rejects_non_standard_float_before_writing(tmp_path):
    log_path = tmp_path / "strict.log"
    journal = OmadaWebhookJournal(str(log_path))

    with pytest.raises(ValueError):
        journal.append({"value": float("nan")})

    assert not log_path.exists()


@pytest.mark.skipif(os.name != "posix", reason="POSIX file mode only")
def test_journal_file_mode_is_0640_on_posix(tmp_path):
    log_path = tmp_path / "mode.log"
    journal = OmadaWebhookJournal(str(log_path))

    journal.append({"event": "test"})

    assert stat.S_IMODE(log_path.stat().st_mode) == 0o640


class FailingJournal:
    def append(self, _record):
        raise OSError("simulated disk full")


def test_persist_failure_returns_500_and_logs_safe_main_event(
    tmp_path,
    caplog,
):
    logger = logging.getLogger(
        f"test.omada_webhook.failure.{uuid.uuid4()}"
    )
    logger.setLevel(logging.DEBUG)
    app, log_path, _journal = webhook_app(
        tmp_path,
        journal=FailingJournal(),
        logger=logger,
    )
    body = b'{"private":"must-not-enter-main-log"}'

    with caplog.at_level(logging.ERROR):
        response = post(app, body)

    assert response.status_code == 500
    assert records(log_path) == []
    assert "omada.webhook_persist_failed" in caplog.text
    assert "must-not-enter-main-log" not in caplog.text
    assert '"error_type":"log_write_failed"' in caplog.text


def test_processor_failure_does_not_undo_persistence_or_204(tmp_path):
    def broken_processor(_envelope):
        raise RuntimeError("future module failed")

    app, log_path, _journal = webhook_app(
        tmp_path,
        processor=broken_processor,
    )

    response = post(app, b'{"event":"kept"}')

    assert response.status_code == 204
    assert records(log_path)[0]["parsed_payload"]["event"] == "kept"


class ExplodingReceiver:
    def receive(self, *_args, **_kwargs):
        raise RuntimeError("private internal diagnostic")


def test_unexpected_receiver_error_has_separate_safe_event(
    tmp_path,
    caplog,
):
    log_path = tmp_path / "internal.log"
    config = OmadaWebhookConfig.from_settings(settings(log_path))
    logger = logging.getLogger(
        f"test.omada_webhook.internal.{uuid.uuid4()}"
    )
    logger.setLevel(logging.DEBUG)
    app = Flask(__name__)
    app.register_blueprint(
        create_omada_webhook_blueprint(
            config=config,
            receiver=ExplodingReceiver(),
            logger=logger,
        )
    )
    app.config["TESTING"] = True
    body = b'{"private":"must-not-enter-main-log"}'

    with caplog.at_level(logging.ERROR):
        response = post(app, body)

    assert response.status_code == 500
    assert not log_path.exists()
    assert "must-not-enter-main-log" not in caplog.text
    assert "private internal diagnostic" not in caplog.text
    internal = captured_events(
        caplog,
        "omada.webhook_internal_error",
    )[-1]
    assert internal["error_type"] == "RuntimeError"
    assert internal["source_ip"] == ALLOWED_IP
    assert "rejection_reason" not in internal


def full_app_settings(log_path, *, enabled):
    return {
        "portal_counter_enabled": False,
        "portal_counter_db_path": "unused.db",
        "portal_counter_timezone": "Asia/Baku",
        "portal_counter_api_enabled": False,
        "auth_telemetry_enabled": False,
        "capport_enabled": False,
        **settings(
            log_path,
            omada_webhook_enabled=enabled,
        ),
    }


def test_disabled_module_returns_404_and_creates_no_log(
    tmp_path,
    caplog,
):
    import app.web.web as web_module

    log_path = tmp_path / "disabled.log"
    with (
        patch.object(
            web_module,
            "get_settings",
            return_value=full_app_settings(log_path, enabled=False),
        ),
        patch.object(
            web_module,
            "create_controller",
            return_value=object(),
        ),
    ):
        app = web_module.create_app(portal_counter_service=None)
    app.config["TESTING"] = True

    with caplog.at_level(logging.WARNING):
        response = app.test_client().post(
            WEBHOOK_PATH,
            data=b'{"must":"not be read or logged"}',
            environ_base={"REMOTE_ADDR": ALLOWED_IP},
        )

    assert response.status_code == 404
    assert not log_path.exists()
    assert "module_disabled" in caplog.text
    assert "not be read or logged" not in caplog.text


def test_enabled_webhook_is_isolated_from_existing_routes(tmp_path):
    import app.web.web as web_module

    log_path = tmp_path / "integrated.log"
    normalized_path = tmp_path / "integrated_normalized.log"
    with (
        patch.object(
            web_module,
            "get_settings",
            return_value=full_app_settings(log_path, enabled=True),
        ),
        patch.object(
            web_module,
            "create_controller",
            return_value=object(),
        ),
    ):
        app = web_module.create_app(portal_counter_service=None)
    app.config["TESTING"] = True
    client = app.test_client()

    webhook_response = client.post(
        WEBHOOK_PATH,
        data=b'{"event":"integration-test"}',
        content_type="application/json",
        headers={"X-Forwarded-For": ALLOWED_IP},
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    portal_response = client.get("/")
    success_response = client.get("/success")
    missing_session_response = client.get("/auth/session/missing")
    retry_response = client.post(
        f"/auth/session/{uuid.uuid4()}/retry",
        json={"retry_request_id": str(uuid.uuid4())},
    )

    assert webhook_response.status_code == 204
    assert portal_response.status_code == 400
    assert success_response.status_code == 200
    assert missing_session_response.status_code == 404
    assert retry_response.status_code == 404
    assert len(records(log_path)) == 1
    assert len(records(normalized_path)) == 1
    assert records(normalized_path)[0]["event"] == (
        "omada.webhook_unclassified"
    )
    assert records(normalized_path)[0]["parse_reason"] == "TEXT_MISSING"


def test_persist_failure_leaves_portal_and_auth_routes_available(
    tmp_path,
    caplog,
):
    import app.web.web as web_module

    log_path = tmp_path / "must-not-exist.log"
    with (
        patch.object(
            web_module,
            "get_settings",
            return_value=full_app_settings(log_path, enabled=True),
        ),
        patch.object(
            web_module,
            "create_controller",
            return_value=object(),
        ),
        patch.object(
            web_module,
            "OmadaWebhookJournal",
            return_value=FailingJournal(),
        ),
    ):
        app = web_module.create_app(portal_counter_service=None)
    app.config["TESTING"] = True
    client = app.test_client()

    with caplog.at_level(logging.ERROR):
        webhook_response = client.post(
            WEBHOOK_PATH,
            data=b'{"private":"must-not-enter-main-log"}',
            content_type="application/json",
            headers={"X-Forwarded-For": ALLOWED_IP},
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        )
    portal_response = client.get("/")
    session_response = client.get(
        f"/auth/session/{uuid.uuid4()}"
    )
    retry_response = client.post(
        f"/auth/session/{uuid.uuid4()}/retry",
        json={"retry_request_id": str(uuid.uuid4())},
    )

    assert webhook_response.status_code == 500
    assert portal_response.status_code == 400
    assert session_response.status_code == 404
    assert retry_response.status_code == 404
    assert not log_path.exists()
    assert "must-not-enter-main-log" not in caplog.text
    failure = captured_events(
        caplog,
        "omada.webhook_persist_failed",
    )[-1]
    assert failure["error_type"] == "log_write_failed"


def test_default_configuration_has_no_hardcoded_allowed_ip():
    config = OmadaWebhookConfig.from_settings({})

    assert config.enabled is False
    assert config.allowed_ips == frozenset()
    assert config.normalized_log_file.endswith(
        "omada_webhook_normalized.log"
    )


def test_empty_normalized_log_path_is_configuration_error(tmp_path):
    with pytest.raises(
        ValueError,
        match="OMADA_WEBHOOK_NORMALIZED_LOG_FILE",
    ):
        OmadaWebhookConfig.from_settings(
            settings(
                tmp_path / "unused.log",
                omada_webhook_normalized_log_file="",
            )
        )


def test_raw_and_normalized_log_paths_must_be_different(tmp_path):
    log_path = tmp_path / "same.log"

    with pytest.raises(
        ValueError,
        match="must be different",
    ):
        OmadaWebhookConfig.from_settings(
            settings(
                log_path,
                omada_webhook_normalized_log_file=str(log_path),
            )
        )


@pytest.mark.parametrize(
    "auth_mode",
    ["unknown", "", "query_token"],
)
def test_unknown_auth_mode_is_a_controlled_configuration_error(
    tmp_path,
    auth_mode,
):
    with pytest.raises(ValueError, match="OMADA_WEBHOOK_AUTH_MODE"):
        OmadaWebhookConfig.from_settings(
            settings(
                tmp_path / "unused.log",
                omada_webhook_auth_mode=auth_mode,
            )
        )


@pytest.mark.parametrize(
    ("auth_mode", "match"),
    [
        ("header_token", "OMADA_WEBHOOK_HEADER_TOKEN"),
        ("omada_payload_secret", "OMADA_WEBHOOK_SHARED_SECRET"),
    ],
)
def test_selected_secret_mode_requires_its_secret(
    tmp_path,
    auth_mode,
    match,
):
    with pytest.raises(ValueError, match=match):
        OmadaWebhookConfig.from_settings(
            settings(
                tmp_path / "unused.log",
                omada_webhook_auth_mode=auth_mode,
            )
        )
