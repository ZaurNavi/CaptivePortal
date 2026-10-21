"""Closed source-native Operations health values; no I/O, discovery or probes."""
from app.device_fingerprint_sensor.operations_metadata import require, integer

SENSOR_UNIT = "fingerprint-sensor.service"
NI02_UNIT = "network-metadata-projection.service"
STATES = frozenset({"healthy", "degraded", "unavailable", "unknown", "stale"})
DEPENDENCIES = {
    SENSOR_UNIT: frozenset({"preflight", "raw_capture", "suricata", "delivery", "spool"}),
    NI02_UNIT: frozenset({"source", "writer", "attribution", "registry", "pending"}),
}
REASONS = frozenset({"source_ready", "source_degraded", "source_unavailable", "source_initializing",
    "source_stopping", "dependencies_unconfirmed", "pending_attribution", "registry_degraded",
    "source_poll_stale", "capacity_limited", "blocked_conflict", "report_unavailable", "report_stale"})


def validate(value, unit):
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
