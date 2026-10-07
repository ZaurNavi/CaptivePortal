"""Admitted DNS/TLS/QUIC semantics, after common time and scope gates."""
from dataclasses import asdict

from .canonical import observation_uuid, semantic_digest, sha256, source_event_identity
from .models import (DnsAnswerV1, DnsObservationV1, DnsQueryV1,
    NetworkMetadataSensitiveEndpointV1, NetworkMetadataValidationError, NormalizedEvent,
    QuicObservationV1, RecordOutcome, TlsObservationV1, UINT64_MAX)
from .scope import check_network_scope, check_valid_from
from .validation import integer, ip, ni_format_utc, ni_timestamp, strict_json, text


def _optional(value, validator):
    return None if value is None else validator(value)


def _name(value):
    return text(value, 253, controls=True)


def _rrtype(value):
    return text(value, 32, pattern=r"[A-Za-z0-9_-]+", ascii_only=True)


def _object(value):
    if not isinstance(value, dict):
        raise NetworkMetadataValidationError()
    return value


def _array(value):
    if value is None:
        return []
    if type(value) is not list:
        raise NetworkMetadataValidationError()
    return value


def _dns(value):
    value = _object(value)
    integer(value.get("version"), 3, 3)
    kind = value.get("type")
    if kind not in {"request", "response"}:
        raise NetworkMetadataValidationError()
    tx = integer(value.get("tx_id"), 0, UINT64_MAX)
    wire = _optional(value.get("id"), lambda item: integer(item, 0, 65535))
    rcode = _optional(value.get("rcode"), _rrtype)
    queries, answers = [], []
    source_queries, source_answers = _array(value.get("queries")), _array(value.get("answers"))
    for ordinal, query in enumerate(source_queries):
        query = _object(query)
        name, kind_name = _name(query.get("rrname")), _rrtype(query.get("rrtype"))
        if ordinal < 8:
            queries.append(DnsQueryV1(ordinal, name, kind_name))
    for ordinal, answer in enumerate(source_answers):
        answer = _object(answer)
        answer_type = _rrtype(answer.get("rrtype"))
        if answer_type in {"A", "AAAA", "CNAME"}:
            data = answer.get("rdata")
            data = _name(data) if answer_type == "CNAME" else ip(data, 4 if answer_type == "A" else 6)
            if ordinal < 32:
                answers.append(DnsAnswerV1(ordinal, answer_type, data))
    return DnsObservationV1(3, kind, tx, wire, rcode,
        "observed_retained" if queries else "not_observed",
        "observed_retained" if answers else "not_observed",
        len(source_queries), len(source_answers), len(source_queries) > 8,
        len(source_answers) > 32, tuple(queries), tuple(answers))


def _alpns(value):
    array = _array(value)
    for item in array:
        text(item, 255)
    return tuple(array[:16]), len(array) > 16


def _tls(value):
    value = _object(value)
    version = _optional(value.get("version"), lambda item: text(item, 32, controls=True))
    sni = _optional(value.get("sni"), _name)
    client, client_truncated = _alpns(value.get("client_alpns"))
    server, server_truncated = _alpns(value.get("server_alpns"))
    return TlsObservationV1(version, sni, "observed_retained" if sni is not None else "not_observed",
                            client, server, client_truncated, server_truncated)


def _quic(value):
    value = _object(value)
    version = _optional(value.get("version"), lambda item:
        text(item, 64, pattern=r"[A-Za-z0-9._:-]+", ascii_only=True))
    sni = _optional(value.get("sni"), _name)
    return QuicObservationV1(version, sni, "observed_retained" if sni is not None else "not_observed")


def semantic_payload(event):
    endpoint = asdict(event.endpoint)
    del endpoint["observation_id"]
    payload = asdict(event.payload)
    if event.family == "dns":
        payload["queries"] = [asdict(query) for query in event.payload.queries]
        payload["answers"] = [asdict(answer) for answer in event.payload.answers]
    elif event.family == "tls":
        payload["client_alpns"] = list(event.payload.client_alpns)
        payload["server_alpns"] = list(event.payload.server_alpns)
    binding = event.binding
    return {"correlation": {"flow_id": event.flow_id, "transaction_id": event.transaction_id},
        "endpoint": endpoint, "event_at": event.event_at, "family": event.family,
        "payload": payload, "schema_version": 1,
        "scope": {"capture_scope_binding_digest": binding.binding_digest,
            "capture_scope_binding_schema_version": 1, "capture_source_id": binding.capture_source_id,
            "network_scope_id": binding.network_scope_id, "network_scope_state": "within_intended_scope",
            "site_id": binding.site_id}}


def normalize_record(data, *, source_generation_id, start, end, binding, source_record_sha256=None):
    raw_digest = sha256(data) if source_record_sha256 is None else source_record_sha256
    output_at = None
    try:
        event = strict_json(data)
        family = event.get("event_type")
        if not isinstance(family, str):
            raise NetworkMetadataValidationError()
        if family not in {"dns", "tls", "quic"}:
            return RecordOutcome(start, end, len(data), "unexpected_family", source_record_sha256=raw_digest)
        output_at = ni_format_utc(ni_timestamp(event.get("timestamp")))
        category = check_valid_from(output_at, binding)
        if category:
            return RecordOutcome(start, end, len(data), category, output_event_at=output_at, source_record_sha256=raw_digest)
        category, src, dst = check_network_scope(event, binding)
        if category:
            return RecordOutcome(start, end, len(data), category, output_event_at=output_at, source_record_sha256=raw_digest)
        flow = _optional(event.get("flow_id"), lambda item: integer(item, 0, UINT64_MAX))
        src_port = _optional(event.get("src_port"), lambda item: integer(item, 0, 65535))
        dst_port = _optional(event.get("dest_port"), lambda item: integer(item, 0, 65535))
        proto = _optional(event.get("proto"), lambda item: text(item, 16, ascii_only=True))
        if proto is not None and proto not in {"TCP", "UDP"}:
            raise NetworkMetadataValidationError()
        payload = {"dns": _dns, "tls": _tls, "quic": _quic}[family](event.get(family))
        identity = source_event_identity(source_generation_id, start)
        observation_id = observation_uuid(family, identity)
        endpoint = NetworkMetadataSensitiveEndpointV1(observation_id, src, dst, src_port, dst_port, proto)
        normalized = NormalizedEvent(observation_id, identity, family, output_at, flow,
            payload.dns_tx_id if family == "dns" else None, binding, endpoint, payload, raw_digest, "")
        from dataclasses import replace
        normalized = replace(normalized, semantic_payload_sha256=semantic_digest(semantic_payload(normalized)))
        return RecordOutcome(start, end, len(data), "normalized", normalized, output_at, raw_digest)
    except NetworkMetadataValidationError as error:
        return RecordOutcome(start, end, len(data), error.category, output_event_at=output_at, source_record_sha256=raw_digest)
    except (ValueError, TypeError, OverflowError, RecursionError):
        return RecordOutcome(start, end, len(data), "schema_invalid", output_event_at=output_at, source_record_sha256=raw_digest)
