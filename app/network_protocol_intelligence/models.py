"""Closed public NI-03 DTOs. No endpoint or source identity payloads."""
from dataclasses import asdict, dataclass
from datetime import timedelta

from app.device_fingerprint.validation import validate_site_id
from app.network_metadata.validation import canonical_uuid, ni_timestamp

PROTOCOLS = {"dns": "DNS", "tls": "TLS", "quic": "QUIC"}


class ProtocolValidationError(ValueError):
    pass


class ProtocolUnavailable(RuntimeError):
    pass


class ProtocolBusy(RuntimeError):
    pass


class ProtocolDeadline(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ProtocolWindowV1:
    from_utc: str
    to_utc: str
    duration_seconds: int
    recent_from_utc: str
    recent_duration_seconds: int


@dataclass(frozen=True, slots=True)
class ProtocolCoverageV1:
    scope: str
    source_state: str
    attribution_state: str
    projection_state: str
    historical_window_completeness_claimed: bool


@dataclass(frozen=True, slots=True)
class RecentProtocolV1:
    protocol_id: str
    display_label: str
    last_observed_at: str


@dataclass(frozen=True, slots=True)
class LastProtocolObservationV1:
    protocol_id: str
    display_label: str
    observed_at: str


@dataclass(frozen=True, slots=True)
class DeviceProtocolSummaryV1:
    schema_version: int
    site_id: str
    device_id: str
    evaluated_at_utc: str
    window: ProtocolWindowV1
    availability_state: str
    evidence_state: str
    identity_binding_state: str
    recent_protocols: tuple[RecentProtocolV1, ...]
    last_protocol_observation: LastProtocolObservationV1 | None
    freshness_state: str
    coverage: ProtocolCoverageV1


def public_summary(value):
    """Validate exact typed fields and cross-field invariants before publication."""
    try:
        if type(value) is not DeviceProtocolSummaryV1:
            raise ValueError
        if type(value.window) is not ProtocolWindowV1 or type(value.coverage) is not ProtocolCoverageV1:
            raise ValueError
        validate_site_id(value.site_id)
        canonical_uuid(value.device_id)
        at = ni_timestamp(value.evaluated_at_utc, canonical=True)
        window, coverage = value.window, value.coverage
        start = ni_timestamp(window.from_utc, canonical=True)
        recent = ni_timestamp(window.recent_from_utc, canonical=True)
        if (type(value.schema_version) is not int or value.schema_version != 1
                or window.to_utc != value.evaluated_at_utc
                or type(window.duration_seconds) is not int or window.duration_seconds != 86400
                or type(window.recent_duration_seconds) is not int or window.recent_duration_seconds != 3600
                or at - start != timedelta(days=1) or at - recent != timedelta(hours=1)
                or coverage.scope != "current_pipeline"
                or coverage.historical_window_completeness_claimed is not False
                or coverage.projection_state not in {"usable", "degraded"}
                or coverage.source_state not in {"usable", "degraded", "unavailable", "unknown"}
                or coverage.attribution_state not in {"usable", "degraded", "unavailable", "unknown"}
                or (coverage.projection_state, coverage.source_state, coverage.attribution_state) not in {
                    ("usable", "usable", "usable"), ("degraded", "usable", "usable"),
                    ("degraded", "usable", "degraded"), ("degraded", "unavailable", "unknown"),
                    ("degraded", "degraded", "degraded"), ("degraded", "unknown", "unknown")}
                or value.availability_state != (
                    "usable" if coverage.projection_state == "usable"
                    and value.identity_binding_state == "authoritative" else "degraded")
                or value.evidence_state not in {"present", "empty", "identity_pending"}
                or value.identity_binding_state not in {"authoritative", "pending", "unavailable", "absent"}
                or type(value.recent_protocols) is not tuple):
            raise ValueError
        ordered = []
        seen = set()
        for item in value.recent_protocols:
            if type(item) is not RecentProtocolV1 or item.protocol_id not in PROTOCOLS:
                raise ValueError
            event = ni_timestamp(item.last_observed_at, canonical=True)
            if item.display_label != PROTOCOLS[item.protocol_id] or item.protocol_id in seen or not recent <= event < at:
                raise ValueError
            seen.add(item.protocol_id)
            ordered.append((at - event, tuple(PROTOCOLS).index(item.protocol_id)))
        if ordered != sorted(ordered):
            raise ValueError
        last = value.last_protocol_observation
        if last is not None:
            if type(last) is not LastProtocolObservationV1 or last.protocol_id not in PROTOCOLS:
                raise ValueError
            event = ni_timestamp(last.observed_at, canonical=True)
            if last.display_label != PROTOCOLS[last.protocol_id] or not start <= event < at:
                raise ValueError
            expected = freshness((at - event).total_seconds(), coverage)
            if value.evidence_state != "present" or value.freshness_state != expected:
                raise ValueError
            if event >= recent:
                if not value.recent_protocols or value.recent_protocols[0] != RecentProtocolV1(last.protocol_id, last.display_label, last.observed_at):
                    raise ValueError
            elif value.recent_protocols:
                raise ValueError
        elif value.recent_protocols or value.evidence_state == "present" or value.freshness_state != "unavailable":
            raise ValueError
        if (value.identity_binding_state == "authoritative") != (value.evidence_state != "identity_pending"):
            raise ValueError
        result = asdict(value)
        result["recent_protocols"] = list(result["recent_protocols"])
        return result
    except Exception:
        raise ProtocolUnavailable() from None


def freshness(age, coverage):
    if age < 0 or age > 86400:
        raise ProtocolUnavailable()
    base = "fresh" if age <= 300 else "recent" if age <= 3600 else "stale"
    if coverage.source_state in {"unavailable", "unknown"}:
        return "stale"
    if base == "fresh" and (coverage.source_state == "degraded" or coverage.attribution_state != "usable"):
        return "recent"
    return base
