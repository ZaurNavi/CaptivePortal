import json
import os
import stat
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

import pytest

from app.integrations.omada.webhook_normalized_journal import (
    OmadaWebhookNormalizedJournal,
)
from app.integrations.omada.webhook_normalizer import (
    EVENT_HANDLERS,
    normalize_mac,
    normalize_webhook,
)


WEBHOOK_ID = "62dc9f43-40c7-4ef9-a886-6639ee29350e"
RECEIVED_AT = "2026-07-28T11:34:28.989Z"
CONTROLLER_TIMESTAMP_MS = 1_785_238_468_934

ONLINE = (
    "[client:Galaxy-A24:32-84-C9-40-38-88]\n"
    "(IP: 192.168.1.96)\n"
    "went online on\n"
    "[ap:EC-75-0C-18-6F-F8:EC-75-0C-18-6F-F8]\n"
    'with SSID "Zefer_Parki"\n'
    "on channel 64."
)
OFFLINE = (
    "[client:Galaxy-A13:1E-93-8A-14-32-6B]\n"
    "(IP: 192.168.1.92)\n"
    'went offline from SSID "Zefer_Parki"\n'
    "on [ap:EC-75-0C-18-6F-F8:EC-75-0C-18-6F-F8]\n"
    "(31m connected, 92.28MB)."
)
UNAUTHORIZED = (
    "[client:12-4E-9B-DE-22-A7]\n"
    "was unauthorized by Main Administrator "
    "z******vi@gmail.com."
)
AUTHENTICATION_EXPIRED = (
    "[client:Galaxy-A12:3E-69-8B-CE-B8-43]'s "
    'authentication on SSID "YuksekSuret" expired.'
)
BLOCKED_CONNECTION = (
    "[client:38-77-07-91-13-FF:38-77-07-91-13-FF] "
    "failed to connect to "
    "[ap:EC-75-0C-18-6F-F8:EC-75-0C-18-6F-F8] "
    'with SSID "Zefer_Parki" on channel 11 '
    "because the user was blocked by "
    "MAC block/MAC Filter/Lock To AP."
    "(6 times in the last minute)"
)
WRONG_PASSWORD = (
    "[client:76-4B-5C-A6-30-6F:76-4B-5C-A6-30-6F] "
    "failed to connect to "
    "[ap:EC-75-0C-18-6F-F8:EC-75-0C-18-6F-F8] "
    'with SSID "Welcome" on channel 64 '
    "because the password was wrong."
    "(1 time in the last minute)"
)

COMMON_KEYS = {
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
}
UNCLASSIFIED_KEYS = COMMON_KEYS | {
    "source_line_number",
    "source_line_sha256",
    "exception_type",
}
CONNECTION_KEYS = {
    "client_name",
    "client_name_raw",
    "client_name_available",
    "client_name_fallback",
    "client_mac",
    "client_mac_raw",
    "client_ip",
    "ssid",
    "ap_name",
    "ap_name_raw",
    "ap_name_available",
    "ap_name_fallback",
    "ap_mac",
    "ap_mac_raw",
    "channel",
}
REPORTED_KEYS = {
    "reported_connected_raw",
    "reported_connected_seconds",
    "reported_traffic_raw",
    "reported_traffic_value",
    "reported_traffic_unit",
    "reported_traffic_bytes_estimate",
}
FAILED_CONNECTION_KEYS = {
    "client_name",
    "client_name_raw",
    "client_name_available",
    "client_name_fallback",
    "client_mac",
    "client_mac_raw",
    "ssid",
    "ap_name",
    "ap_name_raw",
    "ap_name_available",
    "ap_name_fallback",
    "ap_mac",
    "ap_mac_raw",
    "channel",
    "failure_reason",
    "failure_source",
    "controller_reason_raw",
    "occurrence_count",
    "occurrence_window_seconds",
}
AUTHENTICATION_EXPIRED_KEYS = {
    "client_name",
    "client_name_raw",
    "client_name_available",
    "client_name_fallback",
    "client_mac",
    "client_mac_raw",
    "ssid",
    "authentication_state",
    "expiration_source",
}


def raw_record(text=ONLINE, **payload_overrides):
    payload = {
        "Site": "Home",
        "Controller": "Omada Controller_051C41",
        "timestamp": CONTROLLER_TIMESTAMP_MS,
        "text": [text] if isinstance(text, str) else text,
    }
    payload.update(payload_overrides)
    return {
        "webhook_id": WEBHOOK_ID,
        "received_at": RECEIVED_AT,
        "source_ip": "192.168.0.222",
        "payload_sha256": "a" * 64,
        "parsed_payload": payload,
        "raw_body": "must-not-be-copied",
        "headers": {"Authorization": "***REDACTED***"},
    }


def single(record):
    events = normalize_webhook(record)
    assert len(events) == 1
    return events[0]


def test_online_event_has_fixed_schema_and_canonical_values():
    event = single(raw_record())

    assert set(event) == COMMON_KEYS | CONNECTION_KEYS
    assert event["event"] == "omada.client_online"
    assert event["parse_status"] == "parsed"
    assert event["parse_reason"] is None
    assert event["parse_warnings"] == []
    assert event["level"] == "info"
    assert event["client_name"] == "Galaxy-A24"
    assert event["client_name_available"] is True
    assert event["client_mac"] == "32:84:C9:40:38:88"
    assert event["client_ip"] == "192.168.1.96"
    assert event["ssid"] == "Zefer_Parki"
    assert event["ap_name"] is None
    assert event["ap_name_fallback"] == "mac"
    assert event["ap_mac"] == "EC:75:0C:18:6F:F8"
    assert event["channel"] == 64
    assert event["timestamp"] == RECEIVED_AT
    assert event["controller_timestamp_ms"] == (
        CONTROLLER_TIMESTAMP_MS
    )
    assert event["controller_timestamp"] == (
        "2026-07-28T11:34:28.934Z"
    )
    assert event["delivery_latency_ms"] == 55
    assert event["normalized_event_id"] == f"{WEBHOOK_ID}:0"
    assert "raw_body" not in event
    assert "headers" not in event
    assert "shardSecret" not in json.dumps(event)


@pytest.mark.parametrize(
    ("client_block", "name_raw", "fallback"),
    [
        (
            "12-4E-9B-DE-22-A7:12-4E-9B-DE-22-A7",
            "12-4E-9B-DE-22-A7",
            "mac",
        ),
        ("E2-5F-DC-4A-6D-CC", None, "mac_only"),
    ],
)
def test_mac_hostname_fallback_is_valid_not_partial(
    client_block,
    name_raw,
    fallback,
):
    text = ONLINE.replace(
        "Galaxy-A24:32-84-C9-40-38-88",
        client_block,
    )

    event = single(raw_record(text))

    assert event["parse_status"] == "parsed"
    assert event["client_name"] is None
    assert event["client_name_raw"] == name_raw
    assert event["client_name_available"] is False
    assert event["client_name_fallback"] == fallback
    assert "CLIENT_NAME_MISSING" not in event["parse_warnings"]


def test_online_without_ip_is_partial_but_stays_classified():
    event = single(raw_record(ONLINE.replace(
        "(IP: 192.168.1.96)\n",
        "",
    )))

    assert event["event"] == "omada.client_online"
    assert event["client_ip"] is None
    assert event["parse_status"] == "partial"
    assert event["parse_reason"] is None
    assert event["parse_warnings"] == ["CLIENT_IP_MISSING"]
    assert event["level"] == "warning"


def test_recognized_event_keeps_type_when_mac_and_ip_are_invalid():
    text = ONLINE.replace(
        "Galaxy-A24:32-84-C9-40-38-88",
        "Galaxy-A24:not-a-mac",
    ).replace("192.168.1.96", "999.1.1.1")

    event = single(raw_record(text))

    assert event["event"] == "omada.client_online"
    assert event["client_mac"] is None
    assert event["client_mac_raw"] == "not-a-mac"
    assert event["client_name"] == "Galaxy-A24"
    assert event["client_ip"] is None
    assert event["parse_status"] == "partial"
    assert "INVALID_CLIENT_MAC" in event["parse_warnings"]
    assert "INVALID_CLIENT_IP" in event["parse_warnings"]


def test_online_supports_real_ap_name_and_unicode_ssid():
    text = ONLINE.replace(
        "EC-75-0C-18-6F-F8:EC-75-0C-18-6F-F8",
        "Park-Gate:EC-75-0C-18-6F-F8",
    ).replace("Zefer_Parki", "Zəfər Parkı – Qonaq")

    event = single(raw_record(text))

    assert event["parse_status"] == "parsed"
    assert event["ap_name"] == "Park-Gate"
    assert event["ap_name_available"] is True
    assert event["ap_name_fallback"] is None
    assert event["ssid"] == "Zəfər Parkı – Qonaq"


def test_online_without_channel_is_partial():
    event = single(raw_record(ONLINE.replace(
        "\non channel 64.",
        "",
    )))

    assert event["channel"] is None
    assert event["parse_warnings"] == ["CHANNEL_MISSING"]


def test_offline_duration_and_traffic_are_normalized():
    event = single(raw_record(OFFLINE))

    assert set(event) == COMMON_KEYS | CONNECTION_KEYS | REPORTED_KEYS
    assert event["event"] == "omada.client_offline"
    assert event["parse_status"] == "parsed"
    assert event["channel"] is None
    assert event["reported_connected_raw"] == "31m"
    assert event["reported_connected_seconds"] == 1860
    assert event["reported_traffic_raw"] == "92.28MB"
    assert event["reported_traffic_value"] == 92.28
    assert event["reported_traffic_unit"] == "MB"
    assert event["reported_traffic_bytes_estimate"] == 96_762_593


@pytest.mark.parametrize(
    ("source", "seconds"),
    [
        ("1h connected", 3600),
        ("1h4m connected", 3840),
        ("1h4m5s connected", 3845),
        ("8m connected", 480),
        ("8m7s connected", 487),
        ("11s connected", 11),
    ],
)
def test_offline_duration_variants(source, seconds):
    text = OFFLINE.replace("31m connected", source)

    event = single(raw_record(text))

    assert event["reported_connected_seconds"] == seconds
    assert "DURATION_INVALID" not in event["parse_warnings"]


def test_offline_missing_duration_and_traffic_is_valid():
    text = OFFLINE.replace("\n(31m connected, 92.28MB).", "")

    event = single(raw_record(text))

    assert event["parse_status"] == "parsed"
    assert event["parse_warnings"] == []
    for key in REPORTED_KEYS:
        assert event[key] is None
    assert "CHANNEL_MISSING" not in event["parse_warnings"]


def test_invalid_present_duration_and_traffic_are_partial():
    text = OFFLINE.replace(
        "31m connected, 92.28MB",
        "1x connected, many-MB",
    )

    event = single(raw_record(text))

    assert event["parse_status"] == "partial"
    assert event["reported_connected_raw"] == "1x"
    assert event["reported_traffic_raw"] == "many-MB"
    assert "DURATION_INVALID" in event["parse_warnings"]
    assert "TRAFFIC_INVALID" in event["parse_warnings"]


def test_huge_duration_is_partial_instead_of_raising():
    huge_duration = "9" * 5000
    text = OFFLINE.replace(
        "31m connected",
        f"{huge_duration}h connected",
    )

    event = single(raw_record(text))

    assert event["event"] == "omada.client_offline"
    assert event["parse_status"] == "partial"
    assert event["reported_connected_raw"] == f"{huge_duration}h"
    assert event["reported_connected_seconds"] is None
    assert "DURATION_INVALID" in event["parse_warnings"]


def test_huge_traffic_is_partial_and_never_becomes_infinity():
    huge_traffic = f"{'9' * 5000}MB"
    text = OFFLINE.replace("92.28MB", huge_traffic)

    event = single(raw_record(text))

    assert event["event"] == "omada.client_offline"
    assert event["parse_status"] == "partial"
    assert event["reported_traffic_raw"] == huge_traffic
    assert event["reported_traffic_value"] is None
    assert event["reported_traffic_unit"] is None
    assert event["reported_traffic_bytes_estimate"] is None
    assert "TRAFFIC_INVALID" in event["parse_warnings"]


def test_traffic_uses_decimal_half_up_and_normalizes_unit():
    text = OFFLINE.replace("92.28MB", "15.43mb")

    event = single(raw_record(text))

    expected = int(
        (Decimal("15.43") * (1024**2)).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )
    assert event["reported_traffic_value"] == 15.43
    assert event["reported_traffic_unit"] == "MB"
    assert event["reported_traffic_bytes_estimate"] == expected
    assert expected == 16_179_528


def test_administrative_unauthorized_fixed_schema():
    event = single(raw_record(UNAUTHORIZED))

    assert set(event) == COMMON_KEYS | {
        "client_mac",
        "client_mac_raw",
        "administrator",
        "action",
        "action_source",
    }
    assert event["event"] == "omada.client_unauthorized"
    assert event["parse_status"] == "parsed"
    assert event["client_mac"] == "12:4E:9B:DE:22:A7"
    assert event["administrator"] == "z******vi@gmail.com"
    assert event["action"] == "unauthorize"
    assert event["action_source"] == "omada_controller"


def test_authentication_expired_named_client_has_fixed_schema():
    record = raw_record(AUTHENTICATION_EXPIRED)
    record["parsed_payload"]["shardSecret"] = "must-not-be-copied"
    record["raw_body_base64"] = "must-not-be-copied"

    event = single(record)

    assert set(event) == COMMON_KEYS | AUTHENTICATION_EXPIRED_KEYS
    assert event["event"] == "omada.client_authentication_expired"
    assert event["parse_status"] == "parsed"
    assert event["parse_reason"] is None
    assert event["parse_warnings"] == []
    assert event["level"] == "info"
    assert event["client_name"] == "Galaxy-A12"
    assert event["client_name_raw"] == "Galaxy-A12"
    assert event["client_name_available"] is True
    assert event["client_name_fallback"] is None
    assert event["client_mac"] == "3E:69:8B:CE:B8:43"
    assert event["client_mac_raw"] == "3E-69-8B-CE-B8-43"
    assert event["ssid"] == "YuksekSuret"
    assert event["authentication_state"] == "expired"
    assert event["expiration_source"] == "omada_controller"
    assert event["normalized_event_id"] == f"{WEBHOOK_ID}:0"
    assert event["webhook_id"] == WEBHOOK_ID
    assert event["text_index"] == 0
    assert event["text_count"] == 1
    assert event["received_at"] == RECEIVED_AT
    assert event["controller_timestamp_ms"] == (
        CONTROLLER_TIMESTAMP_MS
    )
    assert event["source_ip"] == "192.168.0.222"
    assert event["site"] == "Home"
    assert event["controller_name"] == "Omada Controller_051C41"
    assert event["payload_sha256"] == "a" * 64
    assert event["raw_text"] == AUTHENTICATION_EXPIRED
    serialized = json.dumps(event)
    for secret_key in (
        "raw_body",
        "raw_body_base64",
        "headers",
        "Authorization",
        "shardSecret",
    ):
        assert secret_key not in serialized


def test_authentication_expired_mac_as_name_uses_fallback():
    text = AUTHENTICATION_EXPIRED.replace(
        "Galaxy-A12:3E-69-8B-CE-B8-43",
        "E2-B3-44-FC-9A-DD:E2-B3-44-FC-9A-DD",
    )

    event = single(raw_record(text))

    assert event["parse_status"] == "parsed"
    assert event["parse_warnings"] == []
    assert event["client_name"] is None
    assert event["client_name_raw"] == "E2-B3-44-FC-9A-DD"
    assert event["client_name_available"] is False
    assert event["client_name_fallback"] == "mac"
    assert event["client_mac"] == "E2:B3:44:FC:9A:DD"
    assert event["client_mac_raw"] == "E2-B3-44-FC-9A-DD"


def test_authentication_expired_mac_only_uses_fallback():
    text = AUTHENTICATION_EXPIRED.replace(
        "Galaxy-A12:3E-69-8B-CE-B8-43",
        "E2-B3-44-FC-9A-DD",
    )

    event = single(raw_record(text))

    assert event["parse_status"] == "parsed"
    assert event["parse_warnings"] == []
    assert event["client_name"] is None
    assert event["client_name_raw"] is None
    assert event["client_name_available"] is False
    assert event["client_name_fallback"] == "mac_only"
    assert event["client_mac"] == "E2:B3:44:FC:9A:DD"
    assert event["client_mac_raw"] == "E2-B3-44-FC-9A-DD"


def test_authentication_expired_preserves_unicode():
    text = (
        "[client:Qonaq-Əli:3E-69-8B-CE-B8-43]'s "
        'authentication on SSID "Zəfər Parkı – Qonaq" expired.'
    )

    event = single(raw_record(text))

    assert event["parse_status"] == "parsed"
    assert event["client_name"] == "Qonaq-Əli"
    assert event["client_name_raw"] == "Qonaq-Əli"
    assert event["ssid"] == "Zəfər Parkı – Qonaq"
    assert event["raw_text"] == text


@pytest.mark.parametrize(
    "raw_text",
    [
        AUTHENTICATION_EXPIRED.removesuffix("."),
        (
            "[client:Galaxy-A12:3E-69-8B-CE-B8-43]\n"
            "’s\nAUTHENTICATION   ON\nSSID "
            '"YuksekSuret"\nEXPIRED.\n'
        ),
    ],
)
def test_authentication_expired_accepts_confirmed_format_variants(
    raw_text,
):
    event = single(raw_record(raw_text))

    assert event["event"] == "omada.client_authentication_expired"
    assert event["parse_status"] == "parsed"
    assert event["ssid"] == "YuksekSuret"
    assert event["raw_text"] == raw_text


@pytest.mark.parametrize(
    (
        "client_body",
        "client_name",
        "client_name_raw",
        "client_mac_raw",
    ),
    [
        (
            "Galaxy-A12:not-a-mac",
            "Galaxy-A12",
            "Galaxy-A12",
            "not-a-mac",
        ),
        ("", None, None, None),
    ],
)
def test_authentication_expired_invalid_client_is_partial(
    client_body,
    client_name,
    client_name_raw,
    client_mac_raw,
):
    text = AUTHENTICATION_EXPIRED.replace(
        "Galaxy-A12:3E-69-8B-CE-B8-43",
        client_body,
    )

    event = single(raw_record(text))

    assert event["event"] == "omada.client_authentication_expired"
    assert event["parse_status"] == "partial"
    assert event["parse_reason"] is None
    assert event["level"] == "warning"
    assert event["parse_warnings"] == ["INVALID_CLIENT_MAC"]
    assert event["client_name"] == client_name
    assert event["client_name_raw"] == client_name_raw
    assert event["client_mac"] is None
    assert event["client_mac_raw"] == client_mac_raw


@pytest.mark.parametrize("ssid_raw", ["", "   ", "\n\t"])
def test_authentication_expired_empty_ssid_is_partial(ssid_raw):
    text = AUTHENTICATION_EXPIRED.replace(
        "YuksekSuret",
        ssid_raw,
    )

    event = single(raw_record(text))

    assert event["event"] == "omada.client_authentication_expired"
    assert event["parse_status"] == "partial"
    assert event["level"] == "warning"
    assert event["ssid"] is None
    assert event["parse_warnings"] == ["SSID_MISSING"]


def test_authentication_expired_strips_only_outer_ssid_whitespace():
    text = AUTHENTICATION_EXPIRED.replace(
        "YuksekSuret",
        "  Zəfər   Parkı  ",
    )

    event = single(raw_record(text))

    assert event["parse_status"] == "parsed"
    assert event["ssid"] == "Zəfər   Parkı"
    assert event["raw_text"] == text


@pytest.mark.parametrize(
    "raw_text",
    [
        'authentication on SSID "YuksekSuret" expired.',
        (
            "[client:Galaxy-A12:3E-69-8B-CE-B8-43"
            "'s authentication on SSID "
            '"YuksekSuret" expired.'
        ),
        (
            "[client:Galaxy-A12:3E-69-8B-CE-B8-43]'s "
            "authentication expired."
        ),
        (
            "[client:Galaxy-A12:3E-69-8B-CE-B8-43]'s "
            "authentication on SSID YuksekSuret expired."
        ),
        (
            "[client:Galaxy-A12:3E-69-8B-CE-B8-43]'s "
            'authentication on SSID "YuksekSuret expired.'
        ),
        (
            "[client:Galaxy-A12:3E-69-8B-CE-B8-43]'s "
            'authentication on network "YuksekSuret" expired.'
        ),
        (
            "[client:Galaxy-A12:3E-69-8B-CE-B8-43]'s "
            "authentication failed."
        ),
        (
            "[client:Galaxy-A12:3E-69-8B-CE-B8-43]'s "
            'authorization on SSID "YuksekSuret" expired.'
        ),
        (
            "[client:Galaxy-A12:3E-69-8B-CE-B8-43]'s "
            'authentication on SSID "YuksekSuret" changed.'
        ),
        (
            "[client:Galaxy-A12:3E-69-8B-CE-B8-43]'s "
            'authentication on SSID "YuksekSuret" '
            "expired because of unknown reason."
        ),
        (
            "[client:Galaxy-A12:3E-69-8B-CE-B8-43]'s "
            'authentication on SSID "YuksekSuret" '
            "expired unexpectedly."
        ),
    ],
)
def test_authentication_expired_near_matches_are_unclassified(
    raw_text,
):
    event = single(raw_record(raw_text))

    assert set(event) == UNCLASSIFIED_KEYS
    assert event["event"] == "omada.webhook_unclassified"
    assert event["parse_status"] == "unclassified"
    assert event["parse_reason"] == "UNKNOWN_TEXT_FORMAT"
    assert event["raw_text"] == raw_text


@pytest.mark.parametrize(
    "occurrence_count",
    [1, 3, 6, 999_999],
)
def test_blocked_connection_has_fixed_schema(occurrence_count):
    text = BLOCKED_CONNECTION.replace(
        "6 times",
        f"{occurrence_count} times",
    )

    event = single(raw_record(text))

    assert set(event) == COMMON_KEYS | FAILED_CONNECTION_KEYS
    assert event["event"] == "omada.client_connection_failed"
    assert event["parse_status"] == "parsed"
    assert event["parse_reason"] is None
    assert event["parse_warnings"] == []
    assert event["client_name"] is None
    assert event["client_name_raw"] == "38-77-07-91-13-FF"
    assert event["client_name_available"] is False
    assert event["client_name_fallback"] == "mac"
    assert event["client_mac"] == "38:77:07:91:13:FF"
    assert event["ssid"] == "Zefer_Parki"
    assert event["ap_name"] is None
    assert event["ap_name_raw"] == "EC-75-0C-18-6F-F8"
    assert event["ap_name_available"] is False
    assert event["ap_name_fallback"] == "mac"
    assert event["ap_mac"] == "EC:75:0C:18:6F:F8"
    assert event["channel"] == 11
    assert event["failure_reason"] == "ACCESS_POLICY_BLOCKED"
    assert event["failure_source"] == "omada_controller"
    assert event["controller_reason_raw"] == (
        "MAC block/MAC Filter/Lock To AP"
    )
    assert event["occurrence_count"] == occurrence_count
    assert event["occurrence_window_seconds"] == 60


def test_blocked_connection_preserves_real_client_name():
    text = BLOCKED_CONNECTION.replace(
        "38-77-07-91-13-FF:38-77-07-91-13-FF",
        "Park-Guest:38-77-07-91-13-FF",
    )

    event = single(raw_record(text))

    assert event["event"] == "omada.client_connection_failed"
    assert event["parse_status"] == "parsed"
    assert event["client_name"] == "Park-Guest"
    assert event["client_name_raw"] == "Park-Guest"
    assert event["client_name_available"] is True
    assert event["client_name_fallback"] is None
    assert event["client_mac"] == "38:77:07:91:13:FF"


@pytest.mark.parametrize("channel", [11, 64])
def test_wrong_password_live_event_has_fixed_schema(channel):
    text = WRONG_PASSWORD.replace("channel 64", f"channel {channel}")

    event = single(raw_record(text))

    assert set(event) == COMMON_KEYS | FAILED_CONNECTION_KEYS
    assert event["event"] == "omada.client_connection_failed"
    assert event["level"] == "info"
    assert event["parse_status"] == "parsed"
    assert event["parse_reason"] is None
    assert event["parse_warnings"] == []
    assert event["client_name"] is None
    assert event["client_name_raw"] == "76-4B-5C-A6-30-6F"
    assert event["client_name_available"] is False
    assert event["client_name_fallback"] == "mac"
    assert event["client_mac"] == "76:4B:5C:A6:30:6F"
    assert event["client_mac_raw"] == "76-4B-5C-A6-30-6F"
    assert event["ssid"] == "Welcome"
    assert event["ap_name"] is None
    assert event["ap_name_raw"] == "EC-75-0C-18-6F-F8"
    assert event["ap_name_available"] is False
    assert event["ap_name_fallback"] == "mac"
    assert event["ap_mac"] == "EC:75:0C:18:6F:F8"
    assert event["ap_mac_raw"] == "EC-75-0C-18-6F-F8"
    assert event["channel"] == channel
    assert event["failure_reason"] == "WRONG_PASSWORD"
    assert event["failure_source"] == "omada_controller"
    assert event["controller_reason_raw"] == "password was wrong"
    assert event["occurrence_count"] == 1
    assert event["occurrence_window_seconds"] == 60


@pytest.mark.parametrize(
    ("count", "noun"),
    [
        (1, "time"),
        (1, "times"),
        (2, "time"),
        (2, "times"),
    ],
)
def test_connection_failure_accepts_time_or_times_for_any_count(
    count,
    noun,
):
    text = WRONG_PASSWORD.replace(
        "1 time",
        f"{count} {noun}",
    )

    event = single(raw_record(text))

    assert event["event"] == "omada.client_connection_failed"
    assert event["parse_status"] == "parsed"
    assert event["occurrence_count"] == count
    assert event["occurrence_window_seconds"] == 60


@pytest.mark.parametrize(
    ("source_reason", "expected_failure_reason"),
    [
        ("Password   was Wrong", "WRONG_PASSWORD"),
        (
            "MAC   block / MAC Filter / Lock To AP",
            "ACCESS_POLICY_BLOCKED",
        ),
    ],
)
def test_connection_failure_preserves_controller_reason_text(
    source_reason,
    expected_failure_reason,
):
    if expected_failure_reason == "WRONG_PASSWORD":
        text = WRONG_PASSWORD.replace(
            "password was wrong",
            source_reason,
        )
    else:
        text = BLOCKED_CONNECTION.replace(
            "MAC block/MAC Filter/Lock To AP",
            source_reason,
        )

    event = single(raw_record(text))

    assert event["event"] == "omada.client_connection_failed"
    assert event["parse_status"] == "parsed"
    assert event["failure_reason"] == expected_failure_reason
    assert event["controller_reason_raw"] == source_reason


@pytest.mark.parametrize(
    ("occurrence", "count", "window", "warnings"),
    [
        (
            "",
            None,
            None,
            [
                "OCCURRENCE_COUNT_MISSING",
                "OCCURRENCE_WINDOW_MISSING",
            ],
        ),
        (
            "(abc times in the last minute)",
            None,
            60,
            ["OCCURRENCE_COUNT_INVALID"],
        ),
        (
            "(6 times)",
            6,
            None,
            ["OCCURRENCE_WINDOW_MISSING"],
        ),
    ],
)
def test_wrong_password_occurrence_errors_remain_partial(
    occurrence,
    count,
    window,
    warnings,
):
    text = WRONG_PASSWORD.replace(
        "(1 time in the last minute)",
        occurrence,
    )

    event = single(raw_record(text))

    assert event["event"] == "omada.client_connection_failed"
    assert event["parse_status"] == "partial"
    assert event["failure_reason"] == "WRONG_PASSWORD"
    assert event["occurrence_count"] == count
    assert event["occurrence_window_seconds"] == window
    assert event["parse_warnings"] == warnings


def test_wrong_password_legacy_attempts_recently_remains_partial():
    text = WRONG_PASSWORD.replace(
        "(1 time in the last minute)",
        "(6 attempts recently)",
    )

    event = single(raw_record(text))

    assert event["event"] == "omada.client_connection_failed"
    assert event["parse_status"] == "partial"
    assert event["failure_reason"] == "WRONG_PASSWORD"
    assert event["occurrence_count"] == 6
    assert event["occurrence_window_seconds"] is None
    assert event["parse_warnings"] == [
        "OCCURRENCE_WINDOW_INVALID",
    ]


@pytest.mark.parametrize(
    ("text", "warning"),
    [
        (
            BLOCKED_CONNECTION.replace(" on channel 11", ""),
            "CHANNEL_MISSING",
        ),
        (
            BLOCKED_CONNECTION.replace(
                "on channel 11",
                "on channel eleven",
            ),
            "CHANNEL_INVALID",
        ),
    ],
)
def test_blocked_connection_invalid_channel_is_partial(
    text,
    warning,
):
    event = single(raw_record(text))

    assert event["event"] == "omada.client_connection_failed"
    assert event["parse_status"] == "partial"
    assert event["channel"] is None
    assert event["parse_warnings"] == [warning]


@pytest.mark.parametrize(
    "raw_count",
    [
        "0",
        "-1",
        "abc",
        "1000000",
        "9" * 5000,
    ],
)
def test_blocked_connection_invalid_occurrence_count_is_partial(
    raw_count,
):
    text = BLOCKED_CONNECTION.replace("6 times", f"{raw_count} times")

    event = single(raw_record(text))

    assert event["event"] == "omada.client_connection_failed"
    assert event["parse_status"] == "partial"
    assert event["occurrence_count"] is None
    assert event["occurrence_window_seconds"] == 60
    assert event["parse_warnings"] == [
        "OCCURRENCE_COUNT_INVALID",
    ]


@pytest.mark.parametrize(
    ("text", "count", "window", "warnings"),
    [
        (
            BLOCKED_CONNECTION.replace(
                ".(6 times in the last minute)",
                ".",
            ),
            None,
            None,
            [
                "OCCURRENCE_COUNT_MISSING",
                "OCCURRENCE_WINDOW_MISSING",
            ],
        ),
        (
            BLOCKED_CONNECTION.replace(
                "6 times",
                "times",
            ),
            None,
            60,
            ["OCCURRENCE_COUNT_MISSING"],
        ),
        (
            BLOCKED_CONNECTION.replace(
                "last minute",
                "",
            ),
            6,
            None,
            ["OCCURRENCE_WINDOW_MISSING"],
        ),
        (
            BLOCKED_CONNECTION.replace(
                "last minute",
                "last 5 minutes",
            ),
            6,
            None,
            ["OCCURRENCE_WINDOW_INVALID"],
        ),
        (
            BLOCKED_CONNECTION.replace(
                "times in the last minute",
                "attempts recently",
            ),
            6,
            None,
            ["OCCURRENCE_WINDOW_INVALID"],
        ),
    ],
)
def test_blocked_connection_occurrence_partial_contract(
    text,
    count,
    window,
    warnings,
):
    event = single(raw_record(text))

    assert event["event"] == "omada.client_connection_failed"
    assert event["parse_status"] == "partial"
    assert event["occurrence_count"] == count
    assert event["occurrence_window_seconds"] == window
    assert event["parse_warnings"] == warnings


def test_blocked_occurrence_tolerates_case_spacing_and_punctuation():
    text = BLOCKED_CONNECTION.replace(
        ".(6 times in the last minute)",
        " ( 6   TIMES   IN THE   LAST MINUTE ) .",
    )

    event = single(raw_record(text))

    assert event["parse_status"] == "parsed"
    assert event["occurrence_count"] == 6
    assert event["occurrence_window_seconds"] == 60


def test_unknown_failed_to_connect_reason_is_unclassified():
    raw_text = BLOCKED_CONNECTION.replace(
        "the user was blocked by "
        "MAC block/MAC Filter/Lock To AP",
        "the supplied password was rejected",
    )

    event = single(raw_record(raw_text))

    assert set(event) == UNCLASSIFIED_KEYS
    assert event["event"] == "omada.webhook_unclassified"
    assert event["parse_status"] == "unclassified"
    assert event["parse_reason"] == "UNKNOWN_TEXT_FORMAT"
    assert event["raw_text"] == raw_text


@pytest.mark.parametrize(
    "raw_text",
    [
        WRONG_PASSWORD.replace(
            "the password was wrong",
            "the supplied password was rejected",
        ),
        WRONG_PASSWORD.replace(
            "password was wrong.",
            "password was wrong due to client configuration.",
        ),
        WRONG_PASSWORD.replace(
            "(1 time in the last minute)",
            "(1 time in the last minute "
            "due to client configuration)",
        ),
        (
            WRONG_PASSWORD
            + " due to client configuration"
        ),
        WRONG_PASSWORD.replace(
            "(1 time in the last minute)",
            "(123 bananas due to client configuration)",
        ),
    ],
)
def test_unconfirmed_or_extended_password_reason_is_unclassified(
    raw_text,
):
    event = single(raw_record(raw_text))

    assert set(event) == UNCLASSIFIED_KEYS
    assert event["event"] == "omada.webhook_unclassified"
    assert event["parse_status"] == "unclassified"
    assert event["parse_reason"] == "UNKNOWN_TEXT_FORMAT"
    assert event["raw_text"] == raw_text


@pytest.mark.parametrize(
    ("raw_text", "event_name"),
    [
        (ONLINE, "omada.client_online"),
        (OFFLINE, "omada.client_offline"),
        (UNAUTHORIZED, "omada.client_unauthorized"),
        (
            AUTHENTICATION_EXPIRED,
            "omada.client_authentication_expired",
        ),
        (
            BLOCKED_CONNECTION,
            "omada.client_connection_failed",
        ),
        (
            WRONG_PASSWORD,
            "omada.client_connection_failed",
        ),
    ],
)
def test_registry_fixtures_have_one_unambiguous_handler(
    raw_text,
    event_name,
):
    matches = [
        handler.event_name
        for handler in EVENT_HANDLERS
        if handler.matches(raw_text)
    ]

    assert matches == [event_name]


def test_registry_order_defines_overlapping_pattern_priority():
    raw_text = (
        "[client:12-4E-9B-DE-22-A7]\n"
        "went online\n"
        "was unauthorized by Main Administrator admin."
    )

    matches = [
        handler.event_name
        for handler in EVENT_HANDLERS
        if handler.matches(raw_text)
    ]
    event = single(raw_record(raw_text))

    assert matches == [
        "omada.client_unauthorized",
        "omada.client_online",
    ]
    assert event["event"] == "omada.client_unauthorized"
    assert event["parse_status"] == "parsed"


def test_event_handler_registry_is_ordered_and_unique():
    event_names = tuple(
        handler.event_name for handler in EVENT_HANDLERS
    )

    assert isinstance(EVENT_HANDLERS, tuple)
    assert event_names == (
        "omada.client_unauthorized",
        "omada.client_authentication_expired",
        "omada.client_online",
        "omada.client_offline",
        "omada.client_connection_failed",
    )
    assert len(event_names) == len(set(event_names))


def test_unknown_text_is_preserved_as_unclassified():
    raw_text = "future Omada event with unknown syntax"

    event = single(raw_record(raw_text))

    assert set(event) == UNCLASSIFIED_KEYS
    assert event["event"] == "omada.webhook_unclassified"
    assert event["parse_status"] == "unclassified"
    assert event["parse_reason"] == "UNKNOWN_TEXT_FORMAT"
    assert event["parse_warnings"] == []
    assert event["raw_text"] == raw_text
    assert event["source_line_number"] is None
    assert event["source_line_sha256"] is None
    assert event["exception_type"] is None


def test_unclassified_event_preserves_time_warnings():
    record = raw_record(
        "future Omada event with unknown syntax",
        timestamp="not-a-timestamp",
    )
    record["received_at"] = "not-a-datetime"

    event = single(record)

    assert event["event"] == "omada.webhook_unclassified"
    assert event["parse_status"] == "unclassified"
    assert event["parse_reason"] == "UNKNOWN_TEXT_FORMAT"
    assert event["timestamp"] is None
    assert event["received_at"] is None
    assert event["controller_timestamp"] is None
    assert event["controller_timestamp_ms"] is None
    assert event["delivery_latency_ms"] is None
    assert event["parse_warnings"] == [
        "RECEIVED_AT_INVALID",
        "CONTROLLER_TIMESTAMP_INVALID",
    ]


def test_unclassified_event_preserves_delivery_latency_warning():
    record = raw_record(
        "future Omada event with unknown syntax",
    )
    record["received_at"] = "2026-07-28T11:34:39.000Z"

    event = single(record)

    assert event["event"] == "omada.webhook_unclassified"
    assert event["parse_status"] == "unclassified"
    assert event["parse_reason"] == "UNKNOWN_TEXT_FORMAT"
    assert event["delivery_latency_ms"] == 10_066
    assert event["parse_warnings"] == [
        "HIGH_DELIVERY_LATENCY",
    ]


@pytest.mark.parametrize(
    ("payload_change", "reason"),
    [
        ({"remove_text": True}, "TEXT_MISSING"),
        ({"text": "not-an-array"}, "TEXT_INVALID_TYPE"),
        ({"text": []}, "TEXT_EMPTY"),
    ],
)
def test_missing_invalid_or_empty_text_has_one_webhook_diagnostic(
    payload_change,
    reason,
):
    record = raw_record()
    if payload_change.get("remove_text"):
        del record["parsed_payload"]["text"]
    else:
        record["parsed_payload"]["text"] = payload_change["text"]

    event = single(record)

    assert event["normalized_event_id"] == f"{WEBHOOK_ID}:none"
    assert event["text_index"] is None
    assert event["text_count"] == 0
    assert event["raw_text"] is None
    assert event["parse_status"] == "unclassified"
    assert event["parse_reason"] == reason
    assert event["parse_warnings"] == []


def test_invalid_and_blank_text_items_each_get_diagnostic():
    record = raw_record([
        ONLINE,
        None,
        42,
        {},
        [],
        True,
        "",
        "   ",
    ])

    events = normalize_webhook(record)

    assert len(events) == 8
    assert events[0]["event"] == "omada.client_online"
    assert [
        event["parse_reason"] for event in events[1:6]
    ] == ["TEXT_ITEM_INVALID_TYPE"] * 5
    assert [
        event["parse_reason"] for event in events[6:]
    ] == ["TEXT_ITEM_EMPTY", "TEXT_ITEM_EMPTY"]
    assert [event["text_index"] for event in events] == list(range(8))
    assert all(event["text_count"] == 8 for event in events)
    assert len({
        event["normalized_event_id"] for event in events
    }) == 8


def test_multiple_event_types_share_webhook_and_have_stable_ids():
    record = raw_record([
        ONLINE,
        AUTHENTICATION_EXPIRED,
        BLOCKED_CONNECTION,
        OFFLINE,
        UNAUTHORIZED,
    ])

    first = normalize_webhook(record)
    second = normalize_webhook(record)

    assert [event["event"] for event in first] == [
        "omada.client_online",
        "omada.client_authentication_expired",
        "omada.client_connection_failed",
        "omada.client_offline",
        "omada.client_unauthorized",
    ]
    assert [event["webhook_id"] for event in first] == [
        WEBHOOK_ID,
    ] * 5
    assert [event["text_index"] for event in first] == [
        0,
        1,
        2,
        3,
        4,
    ]
    assert all(event["text_count"] == 5 for event in first)
    assert [event["normalized_event_id"] for event in first] == [
        f"{WEBHOOK_ID}:0",
        f"{WEBHOOK_ID}:1",
        f"{WEBHOOK_ID}:2",
        f"{WEBHOOK_ID}:3",
        f"{WEBHOOK_ID}:4",
    ]
    assert [
        event["normalized_event_id"] for event in first
    ] == [
        event["normalized_event_id"] for event in second
    ]


def test_wrong_password_items_in_one_webhook_are_independent():
    channel_11 = WRONG_PASSWORD.replace("channel 64", "channel 11")
    record = raw_record([WRONG_PASSWORD, channel_11])

    first = normalize_webhook(record)
    second = normalize_webhook(record)

    assert len(first) == 2
    assert [event["event"] for event in first] == [
        "omada.client_connection_failed",
        "omada.client_connection_failed",
    ]
    assert [event["failure_reason"] for event in first] == [
        "WRONG_PASSWORD",
        "WRONG_PASSWORD",
    ]
    assert [event["text_index"] for event in first] == [0, 1]
    assert [event["text_count"] for event in first] == [2, 2]
    assert [event["channel"] for event in first] == [64, 11]
    assert [event["raw_text"] for event in first] == [
        WRONG_PASSWORD,
        channel_11,
    ]
    assert [event["normalized_event_id"] for event in first] == [
        f"{WEBHOOK_ID}:0",
        f"{WEBHOOK_ID}:1",
    ]
    assert [
        event["normalized_event_id"] for event in first
    ] == [
        event["normalized_event_id"] for event in second
    ]


@pytest.mark.parametrize(
    ("timestamp", "warning"),
    [
        (None, "CONTROLLER_TIMESTAMP_INVALID"),
        (True, "CONTROLLER_TIMESTAMP_INVALID"),
        (1.5, "CONTROLLER_TIMESTAMP_INVALID"),
        ("1.5", "CONTROLLER_TIMESTAMP_INVALID"),
        (-1, "CONTROLLER_TIMESTAMP_OUT_OF_RANGE"),
        (946_684_799_999, "CONTROLLER_TIMESTAMP_OUT_OF_RANGE"),
        (4_102_444_800_001, "CONTROLLER_TIMESTAMP_OUT_OF_RANGE"),
    ],
)
def test_invalid_controller_timestamp_is_partial(timestamp, warning):
    event = single(raw_record(ONLINE, timestamp=timestamp))

    assert event["event"] == "omada.client_online"
    assert event["parse_status"] == "partial"
    assert event["controller_timestamp"] is None
    assert event["controller_timestamp_ms"] is None
    assert event["delivery_latency_ms"] is None
    assert event["parse_warnings"] == [warning]


def test_huge_controller_timestamp_is_partial_instead_of_raising():
    event = single(raw_record(
        ONLINE,
        timestamp="9" * 5000,
    ))

    assert event["event"] == "omada.client_online"
    assert event["parse_status"] == "partial"
    assert event["controller_timestamp"] is None
    assert event["controller_timestamp_ms"] is None
    assert event["delivery_latency_ms"] is None
    assert event["parse_warnings"] == [
        "CONTROLLER_TIMESTAMP_OUT_OF_RANGE"
    ]


def test_integer_string_controller_timestamp_is_accepted():
    event = single(raw_record(
        ONLINE,
        timestamp=str(CONTROLLER_TIMESTAMP_MS),
    ))

    assert event["parse_status"] == "parsed"
    assert event["controller_timestamp_ms"] == (
        CONTROLLER_TIMESTAMP_MS
    )


def test_missing_received_at_is_partial_and_canonical_time_is_null():
    record = raw_record()
    del record["received_at"]

    event = single(record)

    assert event["timestamp"] is None
    assert event["received_at"] is None
    assert event["delivery_latency_ms"] is None
    assert event["parse_status"] == "partial"
    assert event["parse_warnings"] == ["RECEIVED_AT_MISSING"]


@pytest.mark.parametrize(
    "received_at",
    [
        "bad",
        "2026-07-28T11:34:28.989",
        "0001-01-01T00:00:00+14:00",
        1_785_238_468_989,
        None,
    ],
)
def test_invalid_received_at_is_partial(received_at):
    record = raw_record()
    record["received_at"] = received_at

    event = single(record)

    assert event["timestamp"] is None
    assert event["received_at"] is None
    assert event["delivery_latency_ms"] is None
    assert event["parse_status"] == "partial"
    assert event["parse_warnings"] == ["RECEIVED_AT_INVALID"]


def test_received_at_with_offset_is_canonicalized_to_utc():
    record = raw_record()
    record["received_at"] = "2026-07-28T15:34:28.989+04:00"

    event = single(record)

    assert event["timestamp"] == RECEIVED_AT
    assert event["received_at"] == RECEIVED_AT
    assert event["delivery_latency_ms"] == 55
    assert event["parse_status"] == "parsed"
    assert event["parse_warnings"] == []


@pytest.mark.parametrize(
    ("latency", "warning"),
    [
        (-101, "NEGATIVE_DELIVERY_LATENCY"),
        (10_001, "HIGH_DELIVERY_LATENCY"),
    ],
)
def test_material_delivery_latency_is_preserved_and_warned(
    latency,
    warning,
):
    received_ms = CONTROLLER_TIMESTAMP_MS + latency
    received_at = (
        datetime.fromtimestamp(
            received_ms / 1000,
            tz=timezone.utc,
        )
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
    record = raw_record()
    record["received_at"] = received_at

    event = single(record)

    assert event["delivery_latency_ms"] == latency
    assert event["parse_warnings"] == [warning]
    assert event["parse_status"] == "partial"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("12-4e-9b-de-22-a7", "12:4E:9B:DE:22:A7"),
        ("12:4e:9b:de:22:a7", "12:4E:9B:DE:22:A7"),
        ("bad", None),
        (None, None),
    ],
)
def test_normalize_mac(value, expected):
    assert normalize_mac(value) == expected


def test_normalized_journal_writes_strict_ascii_safe_jsonl(tmp_path):
    path = tmp_path / "normalized.log"
    journal = OmadaWebhookNormalizedJournal(str(path))
    record = single(raw_record(
        ONLINE.replace("Zefer_Parki", "Zəfər\ud800"),
    ))

    journal.append(record)
    journal.close()

    raw_line = path.read_bytes().strip()
    assert b"\\ud800" in raw_line
    parsed = json.loads(raw_line)
    assert parsed["event"] == "omada.client_online"


def test_normalized_journal_rejects_nan_before_file_creation(tmp_path):
    path = tmp_path / "normalized.log"
    journal = OmadaWebhookNormalizedJournal(str(path))

    with pytest.raises(Exception):
        journal.append({
            "normalized_event_id": "id:0",
            "value": float("nan"),
        })

    assert not path.exists()


@pytest.mark.skipif(os.name != "posix", reason="POSIX file mode only")
def test_normalized_journal_mode_is_0640(tmp_path):
    path = tmp_path / "normalized.log"
    journal = OmadaWebhookNormalizedJournal(str(path))

    journal.append({"normalized_event_id": "id:0"})
    journal.close()

    assert stat.S_IMODE(path.stat().st_mode) == 0o640
