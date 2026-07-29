import hashlib
import json
import os
import stat
from unittest.mock import patch

import pytest

from app.integrations.omada.normalize_log import (
    invalid_raw_line_event,
    main,
    normalize_log,
)
from app.integrations.omada.webhook_normalizer import normalize_webhook


RECEIVED_AT = "2026-07-28T11:34:28.989Z"
CONTROLLER_TIMESTAMP_MS = 1_785_238_468_934
ONLINE = (
    "[client:Galaxy-A24:32-84-C9-40-38-88] "
    "(IP: 192.168.1.96) went online on "
    "[ap:EC-75-0C-18-6F-F8:EC-75-0C-18-6F-F8] "
    'with SSID "Zefer_Parki" on channel 64.'
)
OFFLINE = (
    "[client:Galaxy-A13:1E-93-8A-14-32-6B] "
    "(IP: 192.168.1.92) "
    'went offline from SSID "Zefer_Parki" on '
    "[ap:EC-75-0C-18-6F-F8:EC-75-0C-18-6F-F8] "
    "(31m connected, 92.28MB)."
)
UNAUTHORIZED = (
    "[client:12-4E-9B-DE-22-A7] "
    "was unauthorized by Main Administrator "
    "z******vi@gmail.com."
)
AUTHENTICATION_EXPIRED = (
    "[client:Galaxy-A12:3E-69-8B-CE-B8-43]'s "
    'authentication on SSID "YuksekSuret" expired.'
)
WRONG_PASSWORD = (
    "[client:76-4B-5C-A6-30-6F:76-4B-5C-A6-30-6F] "
    "failed to connect to "
    "[ap:EC-75-0C-18-6F-F8:EC-75-0C-18-6F-F8] "
    'with SSID "Welcome" on channel 64 '
    "because the password was wrong."
    "(1 time in the last minute)"
)
UNCLASSIFIED_KEYS = {
    "timestamp",
    "level",
    "service",
    "module",
    "event",
    "schema_version",
    "normalized_event_id",
    "webhook_id",
    "text_index",
    "text_count",
    "received_at",
    "controller_timestamp",
    "controller_timestamp_ms",
    "delivery_latency_ms",
    "source_ip",
    "site",
    "controller_name",
    "payload_sha256",
    "parse_status",
    "parse_reason",
    "parse_warnings",
    "raw_text",
    "source_line_number",
    "source_line_sha256",
    "exception_type",
}


def raw_record(webhook_id, text):
    return {
        "timestamp": RECEIVED_AT,
        "level": "info",
        "service": "captive_portal",
        "module": "omada_webhook",
        "event": "omada.webhook_received",
        "schema_version": 1,
        "webhook_id": webhook_id,
        "received_at": RECEIVED_AT,
        "source_ip": "192.168.0.222",
        "payload_sha256": "b" * 64,
        "parsed_payload": {
            "Site": "Home",
            "Controller": "Omada Controller_051C41",
            "timestamp": CONTROLLER_TIMESTAMP_MS,
            "shardSecret": "***REDACTED***",
            "text": text,
        },
        "raw_body": '{"shardSecret":"***REDACTED***"}',
        "headers": {"Authorization": "***REDACTED***"},
    }


def write_raw_lines(path, lines):
    with path.open("wb") as stream:
        for line in lines:
            if isinstance(line, dict):
                line = json.dumps(
                    line,
                    ensure_ascii=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            stream.write(line)
            stream.write(b"\n")


def read_events(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


def test_backfill_normalizes_wrong_password_raw_record(tmp_path):
    input_path = tmp_path / "raw.log"
    output_path = tmp_path / "normalized.log"
    write_raw_lines(
        input_path,
        [raw_record("wrong-password-webhook", [WRONG_PASSWORD])],
    )

    stats = normalize_log(
        input_path=input_path,
        output_path=output_path,
    )
    events = read_events(output_path)

    assert stats.raw_records_processed == 1
    assert stats.text_items_processed == 1
    assert stats.normalized_events == 1
    assert stats.partial_events == 0
    assert stats.unclassified_events == 0
    assert stats.invalid_raw_lines == 0
    assert stats.normalization_failures == 0
    assert len(events) == 1
    assert events[0]["event"] == "omada.client_connection_failed"
    assert events[0]["parse_status"] == "parsed"
    assert events[0]["failure_reason"] == "WRONG_PASSWORD"
    assert events[0]["controller_reason_raw"] == (
        "password was wrong"
    )
    assert events[0]["occurrence_count"] == 1
    assert events[0]["occurrence_window_seconds"] == 60


def test_backfill_normalizes_authentication_expired_raw_record(
    tmp_path,
):
    input_path = tmp_path / "raw.log"
    output_path = tmp_path / "normalized.log"
    write_raw_lines(
        input_path,
        [
            raw_record(
                "authentication-expired-webhook",
                [AUTHENTICATION_EXPIRED],
            )
        ],
    )

    stats = normalize_log(
        input_path=input_path,
        output_path=output_path,
    )
    events = read_events(output_path)

    assert stats.raw_records_processed == 1
    assert stats.text_items_processed == 1
    assert stats.normalized_events == 1
    assert stats.partial_events == 0
    assert stats.unclassified_events == 0
    assert stats.invalid_raw_lines == 0
    assert stats.normalization_failures == 0
    assert len(events) == 1
    assert events[0]["event"] == (
        "omada.client_authentication_expired"
    )
    assert events[0]["parse_status"] == "parsed"
    assert events[0]["client_name"] == "Galaxy-A12"
    assert events[0]["client_mac"] == "3E:69:8B:CE:B8:43"
    assert events[0]["ssid"] == "YuksekSuret"
    assert events[0]["authentication_state"] == "expired"
    assert events[0]["expiration_source"] == "omada_controller"


def test_backfill_continues_after_invalid_line_and_is_secret_safe(
    tmp_path,
):
    input_path = tmp_path / "raw.log"
    output_path = tmp_path / "normalized.log"
    invalid_line = b'{"shardSecret":"must-never-leak",broken'
    write_raw_lines(
        input_path,
        [
            raw_record("webhook-1", [ONLINE]),
            b"   ",
            invalid_line,
            raw_record(
                "webhook-2",
                [OFFLINE, UNAUTHORIZED],
            ),
        ],
    )

    stats = normalize_log(
        input_path=input_path,
        output_path=output_path,
    )
    events = read_events(output_path)

    assert stats.raw_records_processed == 3
    assert stats.text_items_processed == 3
    assert stats.normalized_events == 4
    assert stats.partial_events == 0
    assert stats.unclassified_events == 1
    assert stats.invalid_raw_lines == 1
    assert stats.normalization_failures == 0
    assert [event["event"] for event in events] == [
        "omada.client_online",
        "omada.webhook_unclassified",
        "omada.client_offline",
        "omada.client_unauthorized",
    ]

    invalid = events[1]
    expected_sha = hashlib.sha256(invalid_line).hexdigest()
    assert invalid["parse_reason"] == "INVALID_RAW_JSON"
    assert invalid["source_line_number"] == 3
    assert invalid["source_line_sha256"] == expected_sha
    assert invalid["normalized_event_id"] == (
        f"invalid-raw:3:{expected_sha}"
    )
    assert invalid["raw_text"] is None
    output_bytes = output_path.read_bytes()
    assert b"must-never-leak" not in output_bytes
    assert b"shardSecret" not in output_bytes
    assert b"Authorization" not in output_bytes
    assert b"raw_body" not in output_bytes


def test_invalid_raw_event_is_deterministic_and_contains_full_schema():
    line = b"{not json}"

    first = invalid_raw_line_event(
        line_number=42,
        line_bytes=line,
    )
    second = invalid_raw_line_event(
        line_number=42,
        line_bytes=line,
    )

    assert first == second
    assert set(first) == UNCLASSIFIED_KEYS
    assert first["normalized_event_id"].startswith(
        "invalid-raw:42:"
    )
    assert first["webhook_id"] is None
    assert first["text_index"] is None
    assert first["text_count"] is None
    assert first["received_at"] is None
    assert first["controller_timestamp"] is None
    assert first["controller_timestamp_ms"] is None
    assert first["delivery_latency_ms"] is None
    assert first["raw_text"] is None
    assert first["parse_warnings"] == []
    assert first["exception_type"] is None


def test_internal_normalization_failure_is_separate_and_continues(
    tmp_path,
):
    input_path = tmp_path / "raw.log"
    output_path = tmp_path / "normalized.log"
    write_raw_lines(
        input_path,
        [
            raw_record("broken-normalizer", [ONLINE]),
            raw_record("still-processed", [UNAUTHORIZED]),
        ],
    )
    real_normalize = normalize_webhook

    def fail_first(record):
        if record["webhook_id"] == "broken-normalizer":
            raise ValueError("secret exception message")
        return real_normalize(record)

    with patch(
        "app.integrations.omada.normalize_log.normalize_webhook",
        side_effect=fail_first,
    ):
        stats = normalize_log(
            input_path=input_path,
            output_path=output_path,
        )

    events = read_events(output_path)
    assert stats.raw_records_processed == 2
    assert stats.text_items_processed == 2
    assert stats.normalized_events == 2
    assert stats.invalid_raw_lines == 0
    assert stats.normalization_failures == 1
    assert events[0]["parse_reason"] == "NORMALIZATION_FAILED"
    assert events[0]["normalized_event_id"].startswith(
        "normalization-failed:1:"
    )
    assert events[0]["exception_type"] == "ValueError"
    assert events[0]["source_line_number"] == 1
    assert events[0]["raw_text"] is None
    assert set(events[0]) == UNCLASSIFIED_KEYS
    assert events[1]["event"] == "omada.client_unauthorized"
    output_bytes = output_path.read_bytes()
    assert b"secret exception message" not in output_bytes
    assert b"broken-normalizer" not in output_bytes
    assert b"shardSecret" not in output_bytes


def test_existing_output_requires_explicit_mode(tmp_path):
    input_path = tmp_path / "raw.log"
    output_path = tmp_path / "normalized.log"
    write_raw_lines(input_path, [raw_record("one", [ONLINE])])
    output_path.write_text("keep-me\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        normalize_log(
            input_path=input_path,
            output_path=output_path,
        )

    assert output_path.read_text(encoding="utf-8") == "keep-me\n"


def test_append_and_overwrite_modes(tmp_path):
    input_path = tmp_path / "raw.log"
    output_path = tmp_path / "normalized.log"
    write_raw_lines(input_path, [raw_record("one", [ONLINE])])

    normalize_log(
        input_path=input_path,
        output_path=output_path,
    )
    normalize_log(
        input_path=input_path,
        output_path=output_path,
        append=True,
    )
    assert len(read_events(output_path)) == 2

    normalize_log(
        input_path=input_path,
        output_path=output_path,
        overwrite=True,
    )
    assert len(read_events(output_path)) == 1


def test_append_and_overwrite_cannot_be_combined(tmp_path):
    input_path = tmp_path / "raw.log"
    output_path = tmp_path / "normalized.log"
    write_raw_lines(input_path, [raw_record("one", [ONLINE])])

    with pytest.raises(ValueError):
        normalize_log(
            input_path=input_path,
            output_path=output_path,
            append=True,
            overwrite=True,
        )


def test_input_and_output_must_be_different(tmp_path):
    input_path = tmp_path / "raw.log"
    write_raw_lines(input_path, [raw_record("one", [ONLINE])])

    with pytest.raises(ValueError):
        normalize_log(
            input_path=input_path,
            output_path=input_path,
        )


def test_non_dict_json_and_invalid_utf8_are_invalid_raw_lines(
    tmp_path,
):
    input_path = tmp_path / "raw.log"
    output_path = tmp_path / "normalized.log"
    write_raw_lines(input_path, [b"[]", b"\xff"])

    stats = normalize_log(
        input_path=input_path,
        output_path=output_path,
    )

    assert stats.raw_records_processed == 2
    assert stats.invalid_raw_lines == 2
    assert stats.unclassified_events == 2
    assert [
        event["parse_reason"] for event in read_events(output_path)
    ] == ["INVALID_RAW_JSON", "INVALID_RAW_JSON"]


def test_cli_prints_exact_statistics(tmp_path, capsys):
    input_path = tmp_path / "raw.log"
    output_path = tmp_path / "normalized.log"
    write_raw_lines(input_path, [raw_record("one", [ONLINE])])

    result = main([
        "--input",
        str(input_path),
        "--output",
        str(output_path),
    ])

    assert result == 0
    assert capsys.readouterr().out.strip() == "\n".join([
        "Raw records processed: 1",
        "Text items processed: 1",
        "Normalized events: 1",
        "Partial events: 0",
        "Unclassified events: 0",
        "Invalid raw lines: 0",
        "Normalization failures: 0",
    ])


def test_cli_returns_nonzero_for_internal_normalization_failure(
    tmp_path,
    capsys,
):
    input_path = tmp_path / "raw.log"
    output_path = tmp_path / "normalized.log"
    write_raw_lines(
        input_path,
        [raw_record("broken-normalizer", [ONLINE])],
    )

    with patch(
        "app.integrations.omada.normalize_log.normalize_webhook",
        side_effect=RuntimeError("private diagnostic"),
    ):
        result = main([
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ])

    assert result == 1
    assert "Normalization failures: 1" in capsys.readouterr().out
    event = read_events(output_path)[0]
    assert event["parse_reason"] == "NORMALIZATION_FAILED"
    assert event["exception_type"] == "RuntimeError"
    output_bytes = output_path.read_bytes()
    assert b"private diagnostic" not in output_bytes
    assert b"shardSecret" not in output_bytes


@pytest.mark.skipif(os.name != "posix", reason="POSIX file mode only")
def test_backfill_output_mode_is_0640(tmp_path):
    input_path = tmp_path / "raw.log"
    output_path = tmp_path / "normalized.log"
    write_raw_lines(input_path, [raw_record("one", [ONLINE])])

    normalize_log(
        input_path=input_path,
        output_path=output_path,
    )

    assert stat.S_IMODE(output_path.stat().st_mode) == 0o640
