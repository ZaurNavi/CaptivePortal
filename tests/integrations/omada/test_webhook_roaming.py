"""Synthetic, offline CP-QA-OMADA-ROAMING-001 v1.1 contracts."""

import builtins
import copy
import hashlib
import json
import logging
import socket
from unittest.mock import Mock

import pytest
from flask import Flask

from app.integrations.omada import (
    OmadaWebhookConfig,
    OmadaWebhookJournal,
    OmadaWebhookReceiver,
    create_omada_webhook_blueprint,
)
from app.integrations.omada.normalize_log import normalize_log
from app.integrations.omada.webhook_normalized_journal import (
    OmadaWebhookNormalizedJournal,
)
from app.integrations.omada.webhook_normalizer import (
    EVENT_HANDLERS,
    normalize_webhook,
)
from app.integrations.omada.webhook_processor import OmadaWebhookProcessor
from app.integrations.omada.webhook_routes import WEBHOOK_PATH
from app.integrations.omada.webhook_site_mapping import (
    load_webhook_site_id_mapping,
)
from app.public_traffic.service import PublicTrafficService
from app.visit_lifecycle.webhook_reader import _offline_evidence


CLIENT = "02:11:22:33:44:55"
SOURCE = "02:AA:BB:CC:DD:01"
DESTINATION = "02:AA:BB:CC:DD:02"
TIME_MS = 1_785_238_468_934
MAPPING = load_webhook_site_id_mapping('{"Lab":"synthetic-site"}')
COMMON_KEYS = {
    "timestamp", "level", "service", "module", "event", "schema_version",
    "normalized_event_id", "webhook_id", "text_index", "text_count",
    "received_at", "controller_timestamp", "controller_timestamp_ms",
    "delivery_latency_ms", "source_ip", "site", "site_id",
    "site_resolution_status", "controller_name", "payload_sha256",
    "parse_status", "parse_reason", "parse_warnings", "raw_text",
}
ROAMING_KEYS = {"ssid", "source_channel", "destination_channel"} | {
    f"{subject}_{field}"
    for subject in ("client", "source_ap", "destination_ap")
    for field in ("name", "name_raw", "name_available", "name_fallback",
                  "mac", "mac_raw")
}


def roaming(
    *,
    client=f"Lab-phone:{CLIENT}",
    source=f"Lab-AP-2:{SOURCE}",
    destination=f"Lab-AP-1:{DESTINATION}",
    source_channel="[Channel 11]",
    destination_channel="[channel 6]",
    ssid="Zefer_Parki",
):
    return (
        f"[client:{client}] is roaming from "
        f"[ap:{source}]{source_channel} to "
        f"[ap:{destination}]{destination_channel} "
        f'with SSID "{ssid}"'
    )


def envelope(text=None, *, webhook_id="synthetic-delivery", **payload):
    if text is None:
        text = [roaming()]
    return {
        "webhook_id": webhook_id,
        "received_at": "2026-07-28T11:34:28.989Z",
        "payload_sha256": "a" * 64,
        "parsed_payload": {
            "Site": "Lab", "Controller": "Lab-Controller",
            "timestamp": TIME_MS, "text": text, **payload,
        },
        "raw_body": "SYNTHETIC_RAW_BODY_CANARY",
        "headers": {"Authorization": "SYNTHETIC_SECRET_CANARY"},
    }


def normalized(text=None, **payload):
    return normalize_webhook(envelope(text, **payload), site_id_mapping=MAPPING)


def test_roaming_exact_schema_identities_direction_and_common_metadata():
    event = normalized()[0]
    assert set(event) == COMMON_KEYS | ROAMING_KEYS
    assert event["schema_version"] == 1
    assert event["event"] == "omada.client_roaming"
    assert event["parse_status"] == "parsed"
    assert event["parse_reason"] is None
    assert event["parse_warnings"] == []
    assert event["client_mac"] == CLIENT
    assert event["source_ap_mac"] == SOURCE
    assert event["destination_ap_mac"] == DESTINATION
    for subject, name in (("client", "Lab-phone"), ("source_ap", "Lab-AP-2"),
                          ("destination_ap", "Lab-AP-1")):
        assert event[f"{subject}_name"] == name
        assert event[f"{subject}_name_raw"] == name
        assert event[f"{subject}_name_available"] is True
        assert event[f"{subject}_name_fallback"] is None
        assert event[f"{subject}_mac_raw"] == event[f"{subject}_mac"]
    assert event["source_channel"] == 11
    assert event["destination_channel"] == 6
    assert event["ssid"] == "Zefer_Parki"
    assert event["site_id"] == "synthetic-site"
    assert event["site_resolution_status"] == "resolved"
    assert event["controller_timestamp"] == "2026-07-28T11:34:28.934Z"
    assert event["controller_timestamp_ms"] == TIME_MS
    assert event["controller_name"] == "Lab-Controller"
    assert event["received_at"] == "2026-07-28T11:34:28.989Z"
    assert event["delivery_latency_ms"] == 55
    assert event["normalized_event_id"] == "synthetic-delivery:0"
    assert event["text_index"] == 0 and event["text_count"] == 1
    assert event["payload_sha256"] == "a" * 64
    assert event["raw_text"] == roaming()


@pytest.mark.parametrize("ssid", ["Zefer_Parki", "Welcome", "Lab : Wi-Fi", "  Lab Wi-Fi  "])
@pytest.mark.parametrize("channels", [(6, 11), (52, 100)])
@pytest.mark.parametrize("separator", [" ", "\n", "\r\n", "\t  "])
def test_case_whitespace_channels_and_ssid_variants(ssid, channels, separator):
    text = roaming(
        source_channel=f"[cHaNnEl {channels[0]}]",
        destination_channel=f"[CHANNEL {channels[1]}]", ssid=ssid,
    ).replace(" is roaming from ", f"{separator}IS{separator}ROAMING{separator}FROM{separator}")
    text = text.replace(" to ", f"{separator}TO{separator}")
    text = text.replace(" with SSID ", f"{separator}with{separator}SSID{separator}")
    event = normalized([f" {text}\r\n"])[0]
    assert event["event"] == "omada.client_roaming"
    assert event["parse_status"] == "parsed"
    assert (event["source_channel"], event["destination_channel"]) == channels
    assert event["ssid"] == ssid


@pytest.mark.parametrize("subject,mac", [("client", CLIENT), ("source", SOURCE),
                                       ("destination", DESTINATION)])
@pytest.mark.parametrize("kind", ["colon-name", "mac-only", "empty", "mac-fallback"])
def test_named_mac_conventions_without_fabricating_names(subject, mac, kind):
    value = {
        "colon-name": f"Lab:guest:phone:{mac.lower().replace(':', '-')}",
        "mac-only": mac,
        "empty": f":{mac}",
        "mac-fallback": f"{mac}:{mac}",
    }[kind]
    event = normalized([roaming(**{subject: value})])[0]
    prefix = {"client": "client", "source": "source_ap", "destination": "destination_ap"}[subject]
    assert event[f"{prefix}_mac"] == mac
    assert event[f"{prefix}_mac_raw"] == value[-17:]
    if kind == "colon-name":
        assert event[f"{prefix}_name"] == "Lab:guest:phone"
        assert event[f"{prefix}_name_available"] is True
        assert event["parse_status"] == "parsed"
    else:
        assert event[f"{prefix}_name"] is None
        assert event[f"{prefix}_name_available"] is False
        assert event[f"{prefix}_name_fallback"] == {
            "mac-only": "mac_only", "mac-fallback": "mac", "empty": None,
        }[kind]
        assert event["parse_status"] == "partial"
        assert event["parse_warnings"] == [f"{prefix.upper()}_NAME_MISSING"]


@pytest.mark.parametrize("subject", ["client", "source", "destination"])
@pytest.mark.parametrize("value", ["", "Lab", "Lab:bad-mac", "02:11:22:33:44",
                                   "Lab:02:11:22:33:44:GG"])
def test_invalid_required_mac_never_selects_roaming_handler(subject, value):
    text = roaming(**{subject: value})
    assert not EVENT_HANDLERS[0].matches(text)
    event = normalized([text])[0]
    assert event["event"] == "omada.webhook_unclassified"
    assert event["parse_status"] == "unclassified"
    assert event["parse_reason"] == "UNKNOWN_TEXT_FORMAT"
    assert not (set(event) & ROAMING_KEYS)


@pytest.mark.parametrize("ssid", ["", " ", "\t"])
def test_empty_required_ssid_is_unclassified(ssid):
    event = normalized([roaming(ssid=ssid)])[0]
    assert event["event"] == "omada.webhook_unclassified"
    assert event["parse_status"] == "unclassified"
    assert event["parse_reason"] == "UNKNOWN_TEXT_FORMAT"


@pytest.mark.parametrize("subject", ["source", "destination"])
@pytest.mark.parametrize("block,reason", [
    ("", "MISSING"), ("[Channel]", "INVALID"), ("[Channel ]", "INVALID"),
    ("[Channel 0]", "INVALID"), ("[Channel -1]", "INVALID"),
    ("[Channel 1.5]", "INVALID"), ("[Channel nope]", "INVALID"),
    ("[Channel +6]", "INVALID"), ("[Channel ٦]", "INVALID"),
])
def test_optional_channel_is_nullable_only_after_required_identity_gate(subject, block, reason):
    text = roaming(**{f"{subject}_channel": block})
    event = normalized([text])[0]
    assert event["event"] == "omada.client_roaming"
    assert event["parse_status"] == "partial"
    assert event[f"{subject}_channel"] is None
    other = "destination" if subject == "source" else "source"
    assert event[f"{other}_channel"] == (6 if other == "destination" else 11)
    assert event["parse_warnings"] == [f"{subject.upper()}_CHANNEL_{reason}"]
    invalid = normalized([text.replace(CLIENT, "bad-mac")])[0]
    assert invalid["event"] == "omada.webhook_unclassified"
    assert invalid["parse_status"] == "unclassified"


@pytest.mark.parametrize("text", [
    "A client is roaming somewhere", "roaming", "prefix " + roaming(),
    roaming() + " unexpected suffix", roaming() + "\n" + roaming(),
    roaming().replace(f"[ap:Lab-AP-2:{SOURCE}][Channel 11]", ""),
    roaming().replace(f"[ap:Lab-AP-1:{DESTINATION}][channel 6]", ""),
    roaming().replace(f"[client:Lab-phone:{CLIENT}]", ""),
    roaming().replace('with SSID "Zefer_Parki"', ""),
    roaming().replace('"Zefer_Parki"', "Zefer_Parki"),
    roaming().replace("[Channel 11]", "[Channel 11"),
    roaming().replace("[Channel 11]", "[Channel 11][Channel 6]"),
    roaming().replace(" to ", " from "),
    roaming().replace(" with SSID ", " to "),
    roaming().replace('"Zefer_Parki"', '"Zefer_Parki" "Welcome"'),
    roaming().replace(f"[ap:Lab-AP-2:{SOURCE}]", f"[ap:Lab-AP-2:{SOURCE}][ap:extra:{SOURCE}]"),
])
def test_unknown_near_miss_and_malformed_lines_fail_closed(text):
    event = normalized([text])[0]
    assert event["event"] == "omada.webhook_unclassified"
    assert event["parse_status"] == "unclassified"
    assert event["parse_reason"] == "UNKNOWN_TEXT_FORMAT"


def test_source_destination_follow_positions_not_names_and_large_channel_is_safe():
    event = normalized([roaming(source=f"Lab-AP-1:{DESTINATION}",
                                destination=f"Lab-AP-2:{SOURCE}")])[0]
    assert event["source_ap_mac"] == DESTINATION
    assert event["destination_ap_mac"] == SOURCE
    event = normalized([roaming(source_channel="[Channel " + "9" * 10000 + "]")])[0]
    assert event["event"] == "omada.client_roaming"
    assert event["source_channel"] is None
    assert event["parse_warnings"] == ["SOURCE_CHANNEL_INVALID"]


@pytest.mark.parametrize("phrase", [
    "went offline", "went online", "was unauthorized by Main Administrator",
])
def test_roaming_names_cannot_select_a_business_event_even_on_invalid_identity(phrase):
    text = roaming(client=f"{phrase}:{CLIENT}")
    assert normalized([text])[0]["event"] == "omada.client_roaming"
    for invalid in (
        text.replace(CLIENT, "bad-mac"), text.replace(SOURCE, "bad-mac"),
        text.replace(DESTINATION, "bad-mac"), text.replace('"Zefer_Parki"', '""'),
    ):
        event = normalized([invalid])[0]
        assert event["event"] == "omada.webhook_unclassified"
        assert event["parse_status"] == "unclassified"


def test_mixed_batch_one_envelope_time_order_ids_and_no_input_mutation():
    online = (f"[client:Lab-phone:{CLIENT}] (IP: 192.0.2.10) went online on "
              f'[ap:Lab-AP-1:{DESTINATION}] with SSID "Welcome" on channel 6.')
    offline = (f"[client:Lab-phone:{CLIENT}] (IP: 192.0.2.10) "
               f'went offline from SSID "Welcome" on [ap:Lab-AP-1:{DESTINATION}] '
               "(1m connected, 1MB).")
    record = envelope([roaming(), online, offline, "future text", None, "", roaming()])
    before = copy.deepcopy(record)
    first = normalize_webhook(record, site_id_mapping=MAPPING)
    second = normalize_webhook(record, site_id_mapping=MAPPING)
    assert record == before and first == second
    assert [e["event"] for e in first] == [
        "omada.client_roaming", "omada.client_online", "omada.client_offline",
        "omada.webhook_unclassified", "omada.webhook_unclassified",
        "omada.webhook_unclassified", "omada.client_roaming",
    ]
    assert [e["text_index"] for e in first] == list(range(7))
    assert [e["normalized_event_id"] for e in first] == [f"synthetic-delivery:{i}" for i in range(7)]
    assert {e["controller_timestamp_ms"] for e in first} == {TIME_MS}
    assert {e["controller_timestamp"] for e in first} == {"2026-07-28T11:34:28.934Z"}
    assert {e["text_count"] for e in first} == {7}
    assert {e["site_id"] for e in first} == {"synthetic-site"}


@pytest.mark.parametrize("timestamp", [None, "bad", True, -1])
def test_untrusted_controller_time_not_synthesized_for_roaming(timestamp):
    event = normalized(timestamp=timestamp)[0]
    assert event["controller_timestamp"] is None
    assert event["controller_timestamp_ms"] is None
    assert event["parse_status"] == "partial"
    assert event["parse_warnings"]


@pytest.mark.parametrize("site", [None, "Unmapped", ""])
def test_unresolved_site_not_inferred_from_roaming(site):
    event = normalized(Site=site)[0]
    assert event["site_id"] is None
    assert event["site_resolution_status"] != "resolved"


def test_normalizer_is_pure_no_files_network_or_service_logs(monkeypatch, caplog):
    record = envelope()

    def forbidden(*args, **kwargs):
        raise AssertionError("normalizer must not perform I/O")

    with monkeypatch.context() as scoped:
        scoped.setattr(builtins, "open", forbidden)
        scoped.setattr(socket.socket, "connect", forbidden)
        scoped.setattr(logging.Logger, "_log", forbidden)
        events = normalize_webhook(record, site_id_mapping=MAPPING)
    assert events[0]["event"] == "omada.client_roaming"
    output = json.dumps(events)
    assert "SYNTHETIC_RAW_BODY_CANARY" not in output
    assert "SYNTHETIC_SECRET_CANARY" not in output
    assert caplog.records == []


def test_roaming_is_not_visit_or_public_traffic_evidence():
    event = normalized()[0]
    assert _offline_evidence(event) is None
    service = PublicTrafficService(config=Mock(), repository=Mock(), logger=Mock())
    assert service.classify_record(event).target is False
    service.repository.assert_not_called()
    assert service.repository.mock_calls == []
    assert service.logger.mock_calls == []


def test_receiver_processor_journal_batch_and_distinct_delivery_ids(tmp_path, caplog):
    raw_path = tmp_path / "raw.jsonl"
    normalized_path = tmp_path / "normalized.jsonl"
    config = OmadaWebhookConfig.from_settings({
        "omada_webhook_enabled": True,
        "omada_webhook_allowed_ips": "192.0.2.1",
        "omada_webhook_auth_mode": "ip_only",
        "omada_webhook_shared_secret": "",
        "omada_webhook_header_token": "",
        "omada_webhook_max_body_bytes": 1048576,
        "omada_webhook_log_file": str(raw_path),
        "omada_webhook_normalized_log_file": str(normalized_path),
    })
    raw_journal = OmadaWebhookJournal(str(raw_path))
    journal = OmadaWebhookNormalizedJournal(str(normalized_path))
    processor = OmadaWebhookProcessor(journal, site_id_mapping=MAPPING)
    logger = logging.getLogger("test.synthetic.roaming")
    receiver = OmadaWebhookReceiver(config=config, journal=raw_journal,
                                    processor=processor, logger=logger)
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_omada_webhook_blueprint(config=config, receiver=receiver, logger=logger))
    body = {"Site": "Lab", "Controller": "Lab-Controller", "timestamp": TIME_MS,
            "text": [roaming(), roaming(ssid="Welcome"), "future text"]}
    try:
        with app.test_client() as client:
            for _ in range(2):
                response = client.post(WEBHOOK_PATH, json=body,
                                       environ_base={"REMOTE_ADDR": "192.0.2.1"})
                assert response.status_code == 204
        journal.close()
        raw_journal.close()
        raw = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()]
        events = [json.loads(line) for line in normalized_path.read_text(encoding="utf-8").splitlines()]
        assert len(raw) == 2 and len(events) == 6
        assert len({e["normalized_event_id"] for e in events}) == 6
        assert raw[0]["webhook_id"] != raw[1]["webhook_id"]
        for index, item in enumerate(raw):
            assert events[index * 3:(index + 1) * 3] == normalize_webhook(item, site_id_mapping=MAPPING)
        # Only the existing controlled journals may contain source text/identities.
        assert "Lab-phone" not in caplog.text
        assert CLIENT not in caplog.text and SOURCE not in caplog.text
    finally:
        journal.close()
        raw_journal.close()


def test_disposable_backfill_preserves_raw_and_per_delivery_replay_identity(tmp_path):
    source = tmp_path / "raw.jsonl"
    output = tmp_path / "normalized.jsonl"
    records = [envelope([roaming(), roaming(source_channel=""), "future text"])] * 2
    source.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    stats = normalize_log(input_path=source, output_path=output)
    events = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert stats.raw_records_processed == 2
    assert stats.text_items_processed == 6
    assert stats.normalized_events == 6
    assert stats.partial_events == 2 and stats.unclassified_events == 2
    assert stats.normalization_failures == 0
    assert events[:3] == events[3:]
    assert [e["event"] for e in events[:3]] == [
        "omada.client_roaming", "omada.client_roaming", "omada.webhook_unclassified",
    ]
    assert events[1]["parse_warnings"] == ["SOURCE_CHANNEL_MISSING"]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


# QA-RM-01: a malformed roaming announcement must never become business
# evidence because a display name contains a legacy classifier phrase.
NEAR_MISS_MUTATIONS = (
    "unquoted-ssid", "missing-ssid-open", "missing-ssid-close", "empty-ssid",
    "missing-ssid", "suffix", "prefix", "extra-ap", "extra-channel",
    "misplaced-block", "missing-client-open", "missing-client-close",
    "missing-client-colon", "missing-source-open", "missing-source-close",
    "missing-source-colon", "missing-destination-close", "invalid-client",
    "invalid-source", "invalid-destination", "wrong-direction",
)


def near_miss(text, mutation):
    replacements = {
        "unquoted-ssid": ('"Zefer_Parki"', "Zefer_Parki"),
        "missing-ssid-open": ('"Zefer_Parki"', 'Zefer_Parki"'),
        "missing-ssid-close": ('"Zefer_Parki"', '"Zefer_Parki'),
        "empty-ssid": ('"Zefer_Parki"', '""'),
        "missing-ssid": ('with SSID "Zefer_Parki"', ""),
        "extra-ap": ("[Channel 11]", f"[ap:extra:{SOURCE}][Channel 11]"),
        "extra-channel": ("[Channel 11]", "[Channel 11][Channel 6]"),
        "misplaced-block": (" is roaming from ", " [Channel 11] is roaming from "),
        "missing-client-open": ("[client:", "client:"),
        "missing-client-close": ("] is roaming from", " is roaming from"),
        "missing-client-colon": ("[client:", "[client "),
        "missing-source-open": ("[ap:", "ap:"),
        "missing-source-close": ("][Channel 11]", "[Channel 11]"),
        "missing-source-colon": ("[ap:", "[ap "),
        "missing-destination-close": ("][channel 6]", "[channel 6]"),
        "invalid-client": (CLIENT, "bad-mac"),
        "invalid-source": (SOURCE, "bad-mac"),
        "invalid-destination": (DESTINATION, "bad-mac"),
        "wrong-direction": (" to ", " from "),
    }
    if mutation == "suffix":
        return text + " unexpected suffix"
    if mutation == "prefix":
        return "unexpected prefix " + text
    old, new = replacements[mutation]
    assert old in text
    return text.replace(old, new, 1)


@pytest.mark.parametrize("phrase", ["went offline", "went online"])
@pytest.mark.parametrize("subject", ["client", "source", "destination"])
@pytest.mark.parametrize("mutation", NEAR_MISS_MUTATIONS)
def test_QA_RM_01_roaming_near_misses_cannot_escape_through_display_names(
    phrase, subject, mutation,
):
    mac = {"client": CLIENT, "source": SOURCE, "destination": DESTINATION}[subject]
    text = near_miss(roaming(**{subject: f"Guest {phrase}:{mac}"}), mutation)
    event = normalized([text])[0]
    assert event["event"] == "omada.webhook_unclassified"
    assert event["parse_status"] == "unclassified"
    assert event["parse_reason"] == "UNKNOWN_TEXT_FORMAT"
    assert event["parse_warnings"] == []
    assert event["site_id"] == "synthetic-site"
    assert event["site_resolution_status"] == "resolved"
    assert event["text_index"] == 0 and event["text_count"] == 1
    assert event["controller_timestamp_ms"] == TIME_MS
    assert event["normalized_event_id"] == "synthetic-delivery:0"
    assert not (set(event) & ROAMING_KEYS)
    assert _offline_evidence(event) is None
    service = PublicTrafficService(config=Mock(), repository=Mock(), logger=Mock())
    assert service.classify_record(event).target is False
    assert service.repository.mock_calls == [] and service.logger.mock_calls == []


def legacy_connection(verb, *, client_name="Lab-phone", ap_name="Lab-AP", ssid="Welcome"):
    client = f"[client:{client_name}:{CLIENT}] (IP: 192.0.2.10)"
    ap = f"[ap:{ap_name}:{DESTINATION}]"
    if verb == "online":
        return f'{client} went online on {ap} with SSID "{ssid}" on channel 6.'
    return f'{client} went offline from SSID "{ssid}" on {ap} (1m connected, 1MB).'


@pytest.mark.parametrize("verb", ["online", "offline"])
@pytest.mark.parametrize("subject", ["client_name", "ap_name", "ssid"])
@pytest.mark.parametrize("name", ["roaming", "Guest is roaming from", "Guest roaming support"])
def test_QA_RM_01_genuine_connection_is_not_rejected_for_roaming_words(verb, subject, name):
    event = normalized([legacy_connection(verb, **{subject: name})])[0]
    assert event["event"] == f"omada.client_{verb}"
    assert event["parse_status"] == "parsed"
    assert event["parse_reason"] is None
    assert event["client_mac"] == CLIENT and event["ap_mac"] == DESTINATION


@pytest.mark.parametrize("verb", ["online", "offline"])
@pytest.mark.parametrize("subject", ["client_name", "ap_name"])
def test_QA_RM_01_genuine_connection_with_matching_legacy_phrase(verb, subject):
    event = normalized([legacy_connection(verb, **{subject: f"Guest went {verb}"})])[0]
    assert event["event"] == f"omada.client_{verb}"
    assert event["parse_status"] == "parsed"


@pytest.mark.parametrize("subject", ["client_name", "ap_name"])
def test_context_230_repairs_legacy_ambiguity_without_rejecting_genuine_offline(subject):
    # Issue #230 now repairs the separately tracked baseline defect; all R3
    # roaming grammar/fail-closed assertions above remain unchanged.
    event = normalized([legacy_connection("offline", **{subject: "Guest went online"})])[0]
    assert event["event"] == "omada.client_offline"
    assert event["parse_status"] == "parsed"
    assert event["parse_reason"] is None
    assert event["parse_warnings"] == []
    assert event["client_mac"] == CLIENT and event["ap_mac"] == DESTINATION


def test_QA_RM_01_mixed_batch_keeps_one_envelope_time_and_no_false_offline():
    invalid = near_miss(roaming(client=f"Guest went offline:{CLIENT}"), "unquoted-ssid")
    texts = [roaming(), invalid, legacy_connection("offline"), "unknown text"]
    record = envelope(texts)
    before = copy.deepcopy(record)
    events = normalize_webhook(record, site_id_mapping=MAPPING)
    assert record == before
    assert [event["event"] for event in events] == [
        "omada.client_roaming", "omada.webhook_unclassified",
        "omada.client_offline", "omada.webhook_unclassified",
    ]
    assert [event["text_index"] for event in events] == list(range(4))
    assert [event["normalized_event_id"] for event in events] == [f"synthetic-delivery:{i}" for i in range(4)]
    assert {event["controller_timestamp_ms"] for event in events} == {TIME_MS}
    assert {event["controller_timestamp"] for event in events} == {"2026-07-28T11:34:28.934Z"}
    assert {event["site_id"] for event in events} == {"synthetic-site"}
    assert _offline_evidence(events[0]) is None and _offline_evidence(events[1]) is None
    assert _offline_evidence(events[2]) is not None


@pytest.mark.parametrize("verb", ["online", "offline"])
def test_QA_RM_01_quoted_ssid_with_ap_marker_is_not_an_announcement(verb):
    ssid = "is roaming from [ap:Lab]"
    event = normalized([legacy_connection(verb, ssid=ssid)])[0]
    assert event["event"] == f"omada.client_{verb}"
    # #230 R2: the opaque SSID must not masquerade as an AP during DTO
    # extraction either. Roaming announcement/grammar semantics stay intact.
    assert event["parse_status"] == "parsed"
    assert event["parse_warnings"] == []
    assert event["ap_mac"] == DESTINATION
    assert event["ssid"] == ssid


@pytest.mark.parametrize("text,event_name", [
    (f"[client:Guest is roaming from:{CLIENT}] was unauthorized by Main Administrator Lab.",
     "omada.client_unauthorized"),
    (f'[client:Guest roaming:{CLIENT}]\'s authentication on SSID "is roaming from" expired.',
     "omada.client_authentication_expired"),
    (f'[client:Guest is roaming from:{CLIENT}] failed to connect to [ap:Lab:{DESTINATION}] '
     'with SSID "Welcome" on channel 6 because the password was wrong.',
     "omada.client_connection_failed"),
])
def test_QA_RM_01_other_legacy_handlers_keep_roaming_words_in_names(text, event_name):
    event = normalized([text])[0]
    assert event["event"] == event_name
    assert event["parse_reason"] is None


def damaged_roaming_blocks(phrase, subject, damage):
    names = {"client": "Guest", "source": "AP-2", "destination": "AP-1"}
    names[subject] += " " + phrase
    blocks = []
    for role, mac, mode in zip(("client", "source", "destination"),
                              (CLIENT, SOURCE, DESTINATION), damage):
        label = "client" if role == "client" else "ap"
        body = f"{label}:{names[role]}:{mac}"
        blocks.append({"no-open": body + "]", "no-close": "[" + body,
                       "prose": body.replace(label + ":", label + " ", 1)}[mode])
    return (f"{blocks[0]} is roaming from {blocks[1]}[Channel 11] to "
            f'{blocks[2]}[channel 6] with SSID "Zefer_Parki"')


@pytest.mark.parametrize("phrase", ["went offline", "went online"])
@pytest.mark.parametrize("damage", [
    ("no-open", "no-open", "no-open"),
    ("no-close", "no-open", "no-open"),
    ("prose", "prose", "prose"),
])
def test_QA_RM_01_R3_exact_combined_damage_reproducers(phrase, damage):
    text = damaged_roaming_blocks(phrase, "client", damage)
    event = normalized([text])[0]
    assert event["event"] == "omada.webhook_unclassified"
    assert event["parse_status"] == "unclassified"
    assert event["parse_reason"] == "UNKNOWN_TEXT_FORMAT"
    assert not (set(event) & ROAMING_KEYS)


@pytest.mark.parametrize("phrase", ["went offline", "went online"])
@pytest.mark.parametrize("subject", ["client", "source", "destination"])
@pytest.mark.parametrize("client_damage", ["no-open", "no-close", "prose"])
@pytest.mark.parametrize("source_damage", ["no-open", "no-close", "prose"])
@pytest.mark.parametrize("destination_damage", ["no-open", "no-close", "prose"])
def test_QA_RM_01_R3_joint_client_and_ap_damage_is_never_business_evidence(
    phrase, subject, client_damage, source_damage, destination_damage,
):
    event = normalized([damaged_roaming_blocks(
        phrase, subject, (client_damage, source_damage, destination_damage),
    )])[0]
    assert event["event"] == "omada.webhook_unclassified"
    assert event["parse_status"] == "unclassified"
    assert event["parse_reason"] == "UNKNOWN_TEXT_FORMAT"
    assert event["site_id"] == "synthetic-site"
    assert event["site_resolution_status"] == "resolved"
    assert event["text_index"] == 0 and event["text_count"] == 1
    assert event["controller_timestamp_ms"] == TIME_MS
    assert event["normalized_event_id"] == "synthetic-delivery:0"
    assert not (set(event) & ROAMING_KEYS)
    assert _offline_evidence(event) is None
    service = PublicTrafficService(config=Mock(), repository=Mock(), logger=Mock())
    assert service.classify_record(event).target is False
    assert service.repository.mock_calls == [] and service.logger.mock_calls == []


@pytest.mark.parametrize("verb", ["online", "offline"])
@pytest.mark.parametrize("subject", ["client_name", "ap_name", "ssid"])
@pytest.mark.parametrize("name", ["client:Guest is roaming from", "ap:Guest is roaming from",
                                  f"Guest {CLIENT} is roaming from ap:Lab"])
def test_QA_RM_01_R3_role_like_names_are_not_event_announcements(verb, subject, name):
    event = normalized([legacy_connection(verb, **{subject: name})])[0]
    assert event["event"] == f"omada.client_{verb}"
    assert event["parse_status"] == "parsed"
    assert event["client_mac"] == CLIENT and event["ap_mac"] == DESTINATION


def test_QA_RM_01_R3_mixed_combined_damage_keeps_order_and_consumer_isolation():
    texts = [roaming(), damaged_roaming_blocks("went offline", "client", ("no-open",) * 3),
             damaged_roaming_blocks("went online", "client", ("prose",) * 3),
             legacy_connection("offline"), legacy_connection("online"), "unknown"]
    record = envelope(texts)
    before = copy.deepcopy(record)
    events = normalize_webhook(record, site_id_mapping=MAPPING)
    assert record == before
    assert [event["event"] for event in events] == [
        "omada.client_roaming", "omada.webhook_unclassified", "omada.webhook_unclassified",
        "omada.client_offline", "omada.client_online", "omada.webhook_unclassified",
    ]
    assert [event["text_index"] for event in events] == list(range(6))
    assert [event["normalized_event_id"] for event in events] == [f"synthetic-delivery:{i}" for i in range(6)]
    assert {event["text_count"] for event in events} == {6}
    assert {event["site_id"] for event in events} == {"synthetic-site"}
    assert {event["controller_timestamp_ms"] for event in events} == {TIME_MS}
    assert {event["controller_timestamp"] for event in events} == {"2026-07-28T11:34:28.934Z"}
    assert all(_offline_evidence(events[index]) is None for index in (0, 1, 2, 4, 5))
    assert _offline_evidence(events[3]) is not None
