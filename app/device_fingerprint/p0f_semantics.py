"""Pinned p0f 3.09b IPv4 request-side semantics over validated tcp_syn/2.

This module does not read packets or a signature corpus, persist derived facts,
or participate in the sensor / authorization runtime. Callers supply signatures.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .network_schemas import validate_tcp_syn_v2


RUNTIME_CONTRACT = "p0f_runtime_ipv4_request_v1"
MATCHER_CONTRACT = "p0f_3_09b_ipv4_request_matcher_v1"
MAX_DIST = 35
MAX_TCP_OPT = 24

_KINDS = {0: "eol", 1: "nop", 2: "mss", 3: "ws", 4: "sok", 5: "sack", 8: "ts"}
_QUIRKS = frozenset({
    "df", "id+", "id-", "ecn", "0+", "seq-", "ack+", "uptr+",
    "urgf+", "pushf+", "ts1-", "ts2+", "opt+", "exws", "bad",
})
_FUZZY_REMOVED = frozenset({"df", "id+"})
_FUZZY_ADDED = frozenset({"id-", "ecn"})


def _number(value: str, minimum: int, maximum: int) -> int:
    if re.fullmatch(r"[0-9]+", value) is None:
        raise ValueError("Malformed p0f signature number")
    result = int(value)
    if not minimum <= result <= maximum:
        raise ValueError("Out-of-range p0f signature number")
    return result


@dataclass(frozen=True)
class RequestSignature:
    signature_id: str
    version: str
    ttl: int
    bad_ttl: bool
    ip_option_length: int
    mss: int | None
    window_type: str
    window_value: int
    scale: int | None
    option_kinds: tuple[int, ...]
    eol_padding_length: int
    quirks: frozenset[str]
    payload_class: int | None
    generic: bool
    userland: bool


def parse_request_signature(
    text: str, *, signature_id: str, generic: bool = False, userland: bool = False,
) -> RequestSignature:
    """Parse one pinned request-side ``sig`` value; reject unsupported syntax."""
    if not isinstance(signature_id, str) or not signature_id or not isinstance(text, str):
        raise ValueError("Missing signature identity or text")
    fields = text.split(":")
    if len(fields) != 8:
        raise ValueError("Malformed p0f signature")
    version, ttl_text, olen_text, mss_text, window_scale, layout, quirk_text, payload = fields
    if version not in {"4", "*"}:
        raise ValueError("Only IPv4 request signatures are supported")
    bad_ttl = ttl_text.endswith("-")
    if bad_ttl:
        ttl = _number(ttl_text[:-1], 1, 255)
    elif "+" in ttl_text:
        initial, distance = ttl_text.split("+", 1)
        ttl = _number(initial, 1, 255) + _number(distance, 0, 255)
        if ttl > 255:
            raise ValueError("Invalid initial TTL plus distance")
    else:
        ttl = _number(ttl_text, 1, 255)
    olen = _number(olen_text, 0, 255)
    # In 3.09b, the `ttl-:` branch skips the first IP-option digit. Only
    # the pinned corpus's `ttl-:0:` form has unambiguous request semantics.
    if bad_ttl and olen != 0:
        raise ValueError("Unsupported bad-TTL / IP-options combination")
    mss = None if mss_text == "*" else _number(mss_text, 0, 65535)
    if "," not in window_scale:
        raise ValueError("Missing window scale")
    window_text, scale_text = window_scale.split(",", 1)
    scale = None if scale_text == "*" else _number(scale_text, 0, 255)
    if window_text == "*":
        window_type, window_value = "any", 0
    elif window_text.startswith("%"):
        window_type, window_value = "mod", _number(window_text[1:], 2, 65535)
    elif window_text.startswith("mss*"):
        window_type, window_value = "mss", _number(window_text[4:], 1, 1000)
    elif window_text.startswith("mtu*"):
        window_type, window_value = "mtu", _number(window_text[4:], 1, 1000)
    else:
        window_type, window_value = "fixed", _number(window_text, 0, 65535)
    kinds: list[int] = []
    eol_padding = 0
    if layout:
        for index, token in enumerate(layout.split(",")):
            if token.startswith("eol+"):
                if index != len(layout.split(",")) - 1:
                    raise ValueError("EOL must be final")
                eol_padding = _number(token[4:], 0, 255)
                kind = 0
            elif token in {"nop", "mss", "ws", "sok", "sack", "ts"}:
                kind = {"nop": 1, "mss": 2, "ws": 3, "sok": 4, "sack": 5, "ts": 8}[token]
            elif token.startswith("?"):
                kind = _number(token[1:], 0, 255)
            else:
                raise ValueError("Unsupported option token")
            kinds.append(kind)
    if len(kinds) > MAX_TCP_OPT:
        raise ValueError("Too many options")
    quirks = frozenset(quirk_text.split(",")) if quirk_text else frozenset()
    if "" in quirks or quirks - _QUIRKS:
        raise ValueError("Unsupported request-side quirk")
    if payload not in {"*", "0", "+"}:
        raise ValueError("Unsupported payload class")
    return RequestSignature(
        signature_id, version, ttl, bad_ttl, olen, mss, window_type,
        window_value, scale, tuple(kinds), eol_padding, quirks,
        {"*": None, "0": 0, "+": 1}[payload], bool(generic), bool(userland),
    )


def adapt_tcp_syn_v2(value: Mapping[str, Any]) -> dict[str, Any]:
    """Create transient p0f request facts from the frozen strict evidence DTO."""
    source = validate_tcp_syn_v2(value)
    quirks: set[str] = set()
    def mark(when: bool, name: str) -> None:
        if when:
            quirks.add(name)
    mark(source["ip_ecn_bits"] != 0 or source["tcp_ns"] or source["tcp_ece"] or source["tcp_cwr"], "ecn")
    mark(source["ip_df"], "df")
    mark(source["ip_df"] and not source["ip_id_zero"], "id+")
    mark(not source["ip_df"] and source["ip_id_zero"], "id-")
    mark(source["ip_reserved_flag"], "0+")
    mark(source["tcp_sequence_zero"], "seq-")
    mark(source["tcp_ack_first_octet_lsb_set"], "ack+")
    mark(source["tcp_urg_pointer_nonzero"] and not source["tcp_urg"], "uptr+")
    mark(source["tcp_urg"], "urgf+")
    mark(source["tcp_push"], "pushf+")
    mss = 0
    scale = 0
    last_timestamp_nonzero = False
    kinds: list[int] = []
    eol_padding = 0
    records = source["tcp_option_records"]
    for record in records[:MAX_TCP_OPT]:
        kind = record["kind"]
        kinds.append(kind)
        if record["structure_state"] == "malformed_but_observable":
            mark(True, "bad")
        if kind == 0:
            eol_padding = record["eol_padding_length"]
            mark(record["eol_padding_nonzero_before_final_byte"], "opt+")
        elif kind == 2 and record["mss"] is not None:
            mss = record["mss"]
        elif kind == 3 and record["window_scale_raw"] is not None:
            scale = record["window_scale_raw"]
            mark(scale > 14, "exws")
        elif kind == 8:
            # p0f aborts a physically short Timestamp before reading TSval.
            if record["timestamp_echo_nonzero"] is not None:
                last_timestamp_nonzero = not record["timestamp_value_zero"]
                mark(record["timestamp_value_zero"], "ts1-")
                mark(record["timestamp_echo_nonzero"] is True, "ts2+")
        elif kind == 5:
            declared = record["declared_length"]
            if declared is None or not 10 <= declared <= 34 or record["structure_state"] != "well_formed":
                mark(True, "bad")
                break
        elif kind not in _KINDS:
            declared = record["declared_length"]
            if declared is None or not 2 <= declared <= 40 or record["structure_state"] != "well_formed":
                mark(True, "bad")
                break
    mark(len(records) > MAX_TCP_OPT, "bad")
    # The p0f packet parser initializes absent MSS and WS to numeric zero.
    return {
        "contract_version": RUNTIME_CONTRACT,
        "ip_version": 4,
        "observed_ttl": source["observed_ttl"],
        "ip_option_length": source["ip_option_length_bytes"],
        "mss": mss,
        "window": source["tcp_window"],
        "scale": scale,
        "option_kinds": tuple(kinds),
        "eol_padding_length": eol_padding,
        "quirks": frozenset(quirks),
        "payload_class": int(source["tcp_payload_present"]),
        "total_header_length": 20 + source["ip_option_length_bytes"] + source["tcp_header_length_bytes"],
        "last_timestamp_nonzero": last_timestamp_nonzero,
    }


@dataclass(frozen=True)
class MatchResult:
    status: str
    signature_id: str | None
    match_quality: str | None
    signature_kind: str | None
    distance: int | None


def _window_multiple(runtime: Mapping[str, Any]) -> tuple[int, bool]:
    win, mss = runtime["window"], runtime["mss"]
    if not win or mss < 100:
        return -1, False
    divisors = [
        (mss, False),
        (mss - 12 if runtime["last_timestamp_nonzero"] else 0, False),
        (1460, False), (1448, False), (mss + 40, True),
        (mss + runtime["total_header_length"], True), (1500, True),
    ]
    for divisor, use_mtu in divisors:
        if divisor and win % divisor == 0:
            return win // divisor, use_mtu
    return -1, False


def _distance_guess(ttl: int) -> int:
    for initial in (32, 64, 128, 255):
        if ttl <= initial:
            return initial - ttl
    raise AssertionError("validated TTL out of range")


def match_request(runtime: Mapping[str, Any], signatures: Sequence[RequestSignature]) -> MatchResult:
    """Match in declared signature order, using pinned specific/generic/fuzzy precedence."""
    if runtime.get("contract_version") != RUNTIME_CONTRACT:
        raise ValueError("Unsupported runtime contract")
    multiple, use_mtu = _window_multiple(runtime)
    generic_match: RequestSignature | None = None
    fuzzy_match: RequestSignature | None = None
    for signature in signatures:
        if not isinstance(signature, RequestSignature):
            raise ValueError("Invalid signature set")
        if signature.option_kinds != runtime["option_kinds"]:
            continue
        deleted = signature.quirks - runtime["quirks"]
        added = runtime["quirks"] - signature.quirks
        fuzzy = bool(deleted or added)
        if fuzzy and (fuzzy_match or deleted - _FUZZY_REMOVED or added - _FUZZY_ADDED):
            continue
        if signature.eol_padding_length != runtime["eol_padding_length"] or signature.ip_option_length != runtime["ip_option_length"]:
            continue
        ttl = runtime["observed_ttl"]
        if signature.bad_ttl:
            if signature.ttl < ttl:
                continue
        elif signature.ttl < ttl or signature.ttl - ttl > MAX_DIST:
            fuzzy = True
        if signature.mss is not None and signature.mss != runtime["mss"]:
            continue
        if signature.scale is not None and signature.scale != runtime["scale"]:
            continue
        if signature.payload_class is not None and signature.payload_class != runtime["payload_class"]:
            continue
        if signature.window_type == "fixed" and signature.window_value != runtime["window"]:
            continue
        if signature.window_type == "mod" and runtime["window"] % signature.window_value:
            continue
        if signature.window_type == "mss" and (use_mtu or signature.window_value != multiple):
            continue
        if signature.window_type == "mtu" and (not use_mtu or signature.window_value != multiple):
            continue
        if not fuzzy and not signature.generic:
            return MatchResult("MATCH", signature.signature_id, "exact", "specific", signature.ttl - ttl)
        if not fuzzy and generic_match is None:
            generic_match = signature
        elif fuzzy and fuzzy_match is None:
            fuzzy_match = signature
    if generic_match is not None:
        return MatchResult("MATCH", generic_match.signature_id, "exact", "generic", generic_match.ttl - runtime["observed_ttl"])
    if fuzzy_match is None or fuzzy_match.userland:
        return MatchResult("NO_MATCH", None, None, None, None)
    ttl = runtime["observed_ttl"]
    distance = (
        _distance_guess(ttl)
        if fuzzy_match.ttl < ttl or (not fuzzy_match.bad_ttl and fuzzy_match.ttl - ttl > MAX_DIST)
        else fuzzy_match.ttl - ttl
    )
    return MatchResult("MATCH", fuzzy_match.signature_id, "fuzzy", "generic" if fuzzy_match.generic else "specific", distance)
