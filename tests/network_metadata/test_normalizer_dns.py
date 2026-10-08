import pytest
from . import configuration, outcome, source_event, record


def test_dns_uint64_and_crlf_hash(tmp_path):
    binding = configuration(tmp_path).capture_scope_binding
    a, b = outcome(binding), outcome(binding, record() + b"\r")
    assert a.category == b.category == "normalized"
    assert a.normalized.transaction_id == 18446744073709551615
    assert a.normalized.source_record_sha256 != b.normalized.source_record_sha256
    assert a.normalized.semantic_payload_sha256 == b.normalized.semantic_payload_sha256


def test_dns_v3_compact_offset_through_normalizer(tmp_path):
    event = source_event(timestamp="2026-10-08T09:31:20.123456+0400")
    data = record(event)
    binding = configuration(tmp_path).capture_scope_binding
    result = outcome(binding, data)
    assert result.category == "normalized"
    assert result.normalized.event_at == "2026-10-08T05:31:20.123456Z"
    assert result.normalized.payload.dns_version == 3
    event["timestamp"] = "2026-10-08T09:31:20.123456+04:00"
    extended = outcome(binding, record(event))
    assert extended.category == "normalized"
    assert result.normalized.semantic_payload_sha256 == extended.normalized.semantic_payload_sha256
    assert result.normalized.source_record_sha256 != extended.normalized.source_record_sha256


def test_dns_source_caps_and_ordinals(tmp_path):
    event = source_event()
    event["dns"]["queries"] *= 9
    event["dns"]["answers"] = [{"rrtype": "MX"}] * 31 + [{"rrtype": "AAAA", "rdata": "2001:db8::9"}, {"rrtype": "CNAME", "rdata": "late.example"}]
    result = outcome(configuration(tmp_path).capture_scope_binding, record(event)).normalized.payload
    assert len(result.queries) == 8 and result.queries_truncated and result.query_count_observed == 9
    assert [item.ordinal for item in result.queries] == list(range(8))
    assert result.answer_count_observed == 33 and result.answers_truncated
    assert [(item.ordinal, item.answer_type) for item in result.answers] == [(31, "AAAA")]


@pytest.mark.parametrize("field", ["queries", "answers"])
def test_invalid_beyond_cap_is_still_invalid(tmp_path, field):
    event = source_event()
    event["dns"][field] *= 40
    event["dns"][field][-1] = {"rrtype": "A", "rrname": "bad\nname", "rdata": "not-ip"}
    assert outcome(configuration(tmp_path).capture_scope_binding, record(event)).category == "schema_invalid"


@pytest.mark.parametrize("field,value", [("version", True), ("version", 2), ("tx_id", -1), ("tx_id", True),
    ("id", 65536), ("rcode", "bad space"), ("type", "bad"), ("queries", {})])
def test_dns_invalid(tmp_path, field, value):
    event = source_event()
    event["dns"][field] = value
    assert outcome(configuration(tmp_path).capture_scope_binding, record(event)).category == "schema_invalid"


@pytest.mark.parametrize("value", [None, []])
def test_absent_dns_values(tmp_path, value):
    event = source_event()
    event["dns"].update(type="response", queries=value, answers=value)
    payload = outcome(configuration(tmp_path).capture_scope_binding, record(event)).normalized.payload
    assert payload.query_names_presence_state == payload.answer_values_presence_state == "not_observed"


def test_unknown_fields_not_semantic(tmp_path):
    binding = configuration(tmp_path).capture_scope_binding
    a = outcome(binding)
    b = outcome(binding, record(source_event(extra={"raw_secret": "ignore-me"})))
    assert a.normalized.semantic_payload_sha256 == b.normalized.semantic_payload_sha256
    assert a.normalized.source_record_sha256 != b.normalized.source_record_sha256
