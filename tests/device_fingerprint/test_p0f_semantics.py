"""Offline K2A request-side semantics; no p0f binary or network required."""

import pytest

from app.device_fingerprint.p0f_semantics import (
    RUNTIME_CONTRACT, adapt_tcp_syn_v2, match_request, parse_request_signature,
)
from tests.device_fingerprint_sensor.test_tcp_syn import parsed


def signature(text, identity="one", **kwargs):
    return parse_request_signature(text, signature_id=identity, **kwargs)


def runtime(options=b"", **kwargs):
    kwargs.setdefault("ip_id", 1)
    kwargs.setdefault("sequence", 1)
    return adapt_tcp_syn_v2(parsed(options=options, **kwargs))


def test_transient_contract_and_fixed_match():
    value = runtime()
    assert value["contract_version"] == RUNTIME_CONTRACT
    assert value["mss"] == value["scale"] == 0
    assert value["option_kinds"] == ()
    sig = signature("4:64:0:0:65535,0:::0")
    assert match_request(value, [sig]).signature_id == "one"
    assert match_request(value, [sig]).match_quality == "exact"
    assert match_request(value, [signature("4:64:4:0:65535,0:::0")]).status == "NO_MATCH"


@pytest.mark.parametrize("value", [
    "6:64:0:0:65535,0:::0", "4:0:0:0:65535,0:::0",
    "4:64:0:0:%1,0:::0", "4:64:0:0:mss*0,0:::0",
    "4:64:0:0:65535,0:eol+2,nop::0",
    "4:64:0:0:65535,0:::flow:0", "4:64:0:0:65535,0:::0:extra",
    "4:64:0:0:65535,0:::?", "4:64:0:0:65535,0:?256::0",
])
def test_unsupported_grammar_fails_closed(value):
    with pytest.raises(ValueError):
        signature(value)


def test_ttl_distance_fuzzy_and_no_match():
    value = runtime()
    value["observed_ttl"] = 63
    exact = match_request(value, [signature("4:64:0:0:65535,0:::0")])
    assert (exact.status, exact.match_quality, exact.distance) == ("MATCH", "exact", 1)
    fuzzy = match_request(value, [signature("4:32:0:0:65535,0:::0")])
    assert (fuzzy.status, fuzzy.match_quality, fuzzy.distance) == ("MATCH", "fuzzy", 1)
    assert match_request(value, [signature("4:32:0:0:65535,0:::0", userland=True)]).status == "NO_MATCH"
    assert match_request(value, [signature("4:64:0:0:1234,0:::0")]).status == "NO_MATCH"


def test_specific_generic_precedence_and_fuzzy_restriction():
    value = runtime()
    generic = signature("4:64:0:0:*,0:::0", "generic", generic=True)
    specific = signature("4:64:0:0:65535,0:::0", "specific")
    assert match_request(value, [generic, specific]).signature_id == "specific"
    assert match_request(value, [generic]).signature_kind == "generic"
    assert match_request(value, [specific]).signature_kind == "specific"
    assert match_request(value, []).status == "NO_MATCH"
    fuzzy = signature("4:64:0:0:65535,0::df:0", "fuzzy")
    assert match_request(value, [fuzzy]).match_quality == "fuzzy"
    assert match_request(value, [fuzzy, generic]).signature_id == "generic"
    assert match_request(value, [signature("4:64:0:0:65535,0::bad:0")]).status == "NO_MATCH"


@pytest.mark.parametrize("window,options,expression", [
    (2920, bytes.fromhex("02 04 05 b4"), "mss*2"),
    (3000, bytes.fromhex("02 04 05 b4"), "mtu*2"),
    (3000, bytes.fromhex("02 04 05 b4"), "%500"),
    (65535, b"", "*"),
])
def test_window_expression_families(window, options, expression):
    value = runtime(options, window=window)
    sig = signature(f"4:64:0:*:{expression},*:{'mss' if options else ''}::0")
    assert match_request(value, [sig]).status == "MATCH"


def test_option_layout_scale_and_exws():
    options = bytes.fromhex("01 02 04 05 b4 04 02 03 03 ff 01 01")
    value = runtime(options)
    assert value["option_kinds"] == (1, 2, 4, 3, 1, 1)
    assert value["mss"] == 1460 and value["scale"] == 255
    assert "exws" in value["quirks"]
    assert match_request(value, [signature("4:64:0:1460:*,255:nop,mss,sok,ws,nop,nop:exws:0")]).status == "MATCH"
    assert match_request(value, [signature("4:64:0:1460:*,*:nop,mss,sok,ws,nop,nop:exws:0")]).status == "MATCH"
    assert match_request(value, [signature("4:64:0:1460:*,255:mss,nop,sok,ws,nop,nop:exws:0")]).status == "NO_MATCH"


def test_eol_fix2_and_malformed_known_value_fix4():
    early = runtime(bytes.fromhex("00 01 00 00"))
    final = runtime(bytes.fromhex("00 00 00 01"))
    assert "opt+" in early["quirks"] and "opt+" not in final["quirks"]
    first = signature("4:64:0:0:*,0:eol+3:opt+:0")
    second = signature("4:64:0:0:*,0:eol+3::0")
    assert match_request(early, [first, second]).signature_id == "one"
    assert match_request(final, [first]).status == "NO_MATCH"
    assert match_request(final, [second]).status == "MATCH"
    for number, raw in ((1200, "04 b0"), (1460, "05 b4")):
        malformed = runtime(bytes.fromhex(f"02 01 {raw}"))
        assert malformed["mss"] == number and "bad" in malformed["quirks"]
        assert match_request(malformed, [signature(f"4:64:0:{number}:*,0:mss:bad:0")]).status == "MATCH"


def test_ns_fix3_ack_fix5_and_payload():
    ns = runtime(ns=True)
    assert "ecn" in ns["quirks"]
    assert "ecn" not in runtime()["quirks"]
    even = runtime(ack_number=0x02000000)
    odd = runtime(ack_number=0x03000000)
    assert "ack+" not in even["quirks"] and "ack+" in odd["quirks"]
    assert match_request(odd, [signature("4:64:0:0:*,0::ack+:0")]).status == "MATCH"
    assert match_request(even, [signature("4:64:0:0:*,0::ack+:0")]).status == "NO_MATCH"
    assert match_request(runtime(payload=b"x"), [signature("4:64:0:0:*,0:::+")]).status == "MATCH"


def test_timestamp_quirks_and_following_options():
    timestamp = runtime(bytes.fromhex("08 0a 00 00 00 00 00 00 00 01 01 01"))
    assert {"ts1-", "ts2+"} <= timestamp["quirks"]
    assert match_request(timestamp, [signature("4:64:0:0:*,0:ts,nop,nop:ts1-,ts2+:0")]).status == "MATCH"
    malformed = runtime(bytes.fromhex("02 01 04 b0 01 01 01 01"))
    assert malformed["option_kinds"] == (2, 1, 1, 1, 1)
    assert "bad" in malformed["quirks"]
