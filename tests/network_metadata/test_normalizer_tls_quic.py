import pytest
from . import configuration, outcome, record, source_event


def test_tls_compact_offset_through_normalizer(tmp_path):
    event = source_event("tls", timestamp="2026-10-08T09:31:20.123456+0400")
    result = outcome(configuration(tmp_path).capture_scope_binding, record(event))
    assert result.category == "normalized"
    assert result.normalized.event_at == "2026-10-08T05:31:20.123456Z"


def test_tls_order_duplicates_caps(tmp_path):
    event = source_event("tls")
    event["tls"]["client_alpns"] = ["h2", "h2"] + [str(index) for index in range(15)]
    result = outcome(configuration(tmp_path).capture_scope_binding, record(event)).normalized.payload
    assert len(result.client_alpns) == 16 and result.client_alpns[:2] == ("h2", "h2")
    assert result.client_alpns_truncated and not result.server_alpns_truncated


def test_tls_invalid_alpn_after_cap(tmp_path):
    event = source_event("tls")
    event["tls"]["client_alpns"] = ["h2"] * 16 + ["bad\0value"]
    assert outcome(configuration(tmp_path).capture_scope_binding, record(event)).category == "schema_invalid"


@pytest.mark.parametrize("family", ["tls", "quic"])
def test_optional_sni(tmp_path, family):
    event = source_event(family)
    del event[family]["sni"]
    payload = outcome(configuration(tmp_path).capture_scope_binding, record(event)).normalized.payload
    assert payload.sni is None and payload.sni_presence_state == "not_observed"


@pytest.mark.parametrize("value", ["a b", "v1/2", "é", "x" * 65, 1])
def test_quic_version(tmp_path, value):
    event = source_event("quic")
    event["quic"]["version"] = value
    assert outcome(configuration(tmp_path).capture_scope_binding, record(event)).category == "schema_invalid"
