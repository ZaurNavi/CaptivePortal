"""Closed source-native Operations health values; no I/O, discovery or probes."""
from app.device_fingerprint_sensor.operations_metadata import require, integer

SENSOR_UNIT = "fingerprint-sensor.service"
NI02_UNIT = "network-metadata-projection.service"
EVIDENCE_UNIT = "fingerprint-evidence.service"
NI01_UNIT = "network-metadata.service"
NI04_UNIT = "network-service-recognition.service"
OWNER_SERVICES = {"fingerprint_evidence": EVIDENCE_UNIT, "network_metadata": NI01_UNIT,
    "network_service_recognition": NI04_UNIT}
OWNER_UNITS = frozenset(OWNER_SERVICES.values())
STATES = frozenset({"healthy", "degraded", "unavailable", "unknown", "stale"})
DEPENDENCIES = {
    SENSOR_UNIT: frozenset({"preflight", "raw_capture", "suricata", "delivery", "spool"}),
    NI02_UNIT: frozenset({"source", "writer", "attribution", "registry", "pending"}),
}
REASONS = frozenset({"source_ready", "source_degraded", "source_unavailable", "source_initializing",
    "source_stopping", "dependencies_unconfirmed", "pending_attribution", "registry_degraded",
    "source_poll_stale", "capacity_limited", "blocked_conflict", "report_unavailable", "report_stale",
    "backfilling_incomplete_coverage", "source_lagging", "source_stale"})


def validate(value, unit):
    if unit in OWNER_UNITS:
        return validate_owner(value, unit)
    require(unit in DEPENDENCIES and type(value) is dict)
    keys = {"state", "reason", "dependencies"} | ({"pending_count"} if unit == NI02_UNIT else set())
    require(set(value) == keys and type(value["state"]) is str and value["state"] in STATES - {"stale"})
    require(type(value["reason"]) is str and value["reason"] in REASONS)
    allowed = {
        "healthy": {"source_ready"},
        "unknown": {"dependencies_unconfirmed", "source_initializing", "source_stopping", "source_poll_stale"},
        "degraded": {"source_degraded", "pending_attribution", "registry_degraded", "capacity_limited"},
        "unavailable": {"source_unavailable", "blocked_conflict"},
    }
    require(value["reason"] in allowed[value["state"]])
    if unit == SENSOR_UNIT:
        require(value["reason"] not in {"pending_attribution", "registry_degraded", "capacity_limited", "blocked_conflict"})
    deps = value["dependencies"]
    require(type(deps) is dict and set(deps) == DEPENDENCIES[unit] and all(type(v) is bool for v in deps.values()))
    if value["state"] == "healthy":
        require(all(deps.values()) and value["reason"] == "source_ready")
    if unit == NI02_UNIT:
        pending = value["pending_count"]
        require(pending is None or integer(pending))
        require(deps["pending"] == (pending is not None))
        if value["state"] == "healthy":
            require(pending == 0)
        if value["reason"] == "pending_attribution":
            require(value["state"] == "degraded" and pending is not None and pending > 0)
    return value


def validate_owner(value, unit):
    require(unit in OWNER_UNITS and type(value) is dict and set(value) == {"state", "reason"})
    allowed = {"healthy": {"source_ready"}, "degraded": {"source_degraded"},
        "unavailable": {"source_unavailable"},
        "unknown": {"source_initializing", "source_stopping", "dependencies_unconfirmed"}}
    if unit == NI04_UNIT:
        allowed["healthy"].add("backfilling_incomplete_coverage")
        allowed["degraded"].add("source_lagging")
        allowed["unavailable"].update({"capacity_limited", "blocked_conflict"})
    if unit == NI01_UNIT:
        allowed["degraded"].add("source_stale")
    require(type(value["state"]) is str and value["state"] in allowed
        and type(value["reason"]) is str and value["reason"] in allowed[value["state"]])
    return value


def owner_health(unit, native):
    """Only already-computed owner memory. Never call a health/DB probe here."""
    require(unit in OWNER_UNITS)
    state, reason = "unknown", "dependencies_unconfirmed"
    if unit != NI01_UNIT and type(native) is not str:
        native = None
    if unit == EVIDENCE_UNIT:
        state, reason = {"ready": ("healthy", "source_ready"),
            "degraded": ("degraded", "source_degraded"), "unavailable": ("unavailable", "source_unavailable"),
            "initializing": ("unknown", "source_initializing"), "stopping": ("unknown", "source_stopping")
        }.get(native, (state, reason))
    elif unit == NI04_UNIT:
        state, reason = {"usable": ("healthy", "source_ready"),
            "backfilling": ("healthy", "backfilling_incomplete_coverage"),
            "lagging": ("degraded", "source_lagging"),
            "source_unavailable": ("unavailable", "source_unavailable"),
            "recognition_unavailable": ("unavailable", "source_unavailable"),
            "capacity_halted": ("unavailable", "capacity_limited"),
            "blocked_conflict": ("unavailable", "blocked_conflict"),
            "initializing": ("unknown", "source_initializing"), "stopping": ("unknown", "source_stopping")
        }.get(native, (state, reason))
    else:
        from app.network_metadata.models import CONFLICT_CATEGORIES
        fields = tuple(getattr(native, key, None) for key in ("capture", "output", "ingest"))
        reasons = getattr(native, "local_reasons", None)
        if "unavailable" in fields or "blocked" in fields or isinstance(reasons, (set, frozenset, tuple)) and set(reasons) & CONFLICT_CATEGORIES:
            state, reason = "unavailable", "source_unavailable"
        elif "partial" in fields or "stale" in fields:
            state, reason = "degraded", "source_stale" if "stale" in fields else "source_degraded"
        elif fields == ("usable",) * 3 and isinstance(reasons, (set, frozenset, tuple)) and len(reasons) == 0:
            state, reason = "healthy", "source_ready"
    return validate_owner(dict(state=state, reason=reason), unit)


def sensor_health(native_state, dependencies):
    state, reason = {
        "ready": ("healthy", "source_ready"), "degraded": ("degraded", "source_degraded"),
        "unavailable": ("unavailable", "source_unavailable"), "initializing": ("unknown", "source_initializing"),
        "stopping": ("unknown", "source_stopping"),
    }.get(native_state, ("unknown", "dependencies_unconfirmed"))
    if state == "healthy" and not all(dependencies.values()):
        state, reason = "unknown", "dependencies_unconfirmed"
    return validate(dict(state=state, reason=reason, dependencies=dependencies), SENSOR_UNIT)


def ni02_health(native_state, dependencies, pending_count):
    state, reason = "unknown", "dependencies_unconfirmed"
    if native_state == "usable" and all(dependencies.values()) and pending_count == 0:
        state, reason = "healthy", "source_ready"
    elif native_state == "attribution_unavailable" and pending_count is not None and pending_count > 0:
        state, reason = "degraded", "pending_attribution"
    elif native_state in {"attribution_unavailable", "degraded"}:
        state, reason = "degraded", "source_degraded"
    elif native_state == "registry_degraded":
        state, reason = "degraded", "registry_degraded"
    elif native_state in {"capacity_waiting_reader", "capacity_halted"}:
        state, reason = "degraded", "capacity_limited"
    elif native_state == "blocked_conflict":
        state, reason = "unavailable", "blocked_conflict"
    elif native_state == "source_unavailable":
        state, reason = "unavailable", "source_unavailable"
    elif native_state == "stopping":
        state, reason = "unknown", "source_stopping"
    return validate(dict(state=state, reason=reason, dependencies=dependencies, pending_count=pending_count), NI02_UNIT)


def unknown_evidence(reason="report_unavailable"):
    return dict(state="unknown", source="none", observed_at=None, received_at=None,
                age=None, ttl=180, reason=reason)
