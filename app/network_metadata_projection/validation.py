"""Projection-local exact keys and immutable semantic digest."""
import hashlib
from app.network_metadata.canonical import ni01_canonical_json
from app.network_metadata.validation import ni_timestamp, ni_format_utc, canonical_uuid, digest
from app.network_attribution.validation import canonical_mac
from app.device_fingerprint.validation import validate_site_id
from .models import ProjectionValidationError


def edge_id(observation_id, role):
    canonical_uuid(observation_id, 5)
    if role not in {"src", "dst"}:
        raise ProjectionValidationError()
    return hashlib.sha256(("device-network-metadata-edge-v1\0" + observation_id + "\0" + role).encode("utf-8")).hexdigest()


def semantic_digest(edge):
    excluded = {"device_id", "identity_binding_state", "identity_binding_evaluated_at", "device_id_bound_at",
                "projected_at", "projection_run_id", "edge_semantic_digest"}
    return hashlib.sha256(ni01_canonical_json({key: value for key, value in edge.items() if key not in excluded})).hexdigest()


def read_window(site_id, from_utc, to_utc, limit, cursor):
    try:
        validate_site_id(site_id)
        first, last = ni_timestamp(from_utc, canonical=True), ni_timestamp(to_utc, canonical=True)
        if not 0 < (last - first).total_seconds() <= 14 * 86400 or type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError
        if cursor is not None:
            if type(cursor) is not tuple or len(cursor) != 2:
                raise ValueError
            instant = ni_timestamp(cursor[0], canonical=True)
            digest(cursor[1])
            if not first <= instant < last:
                raise ValueError
    except Exception:
        raise ProjectionValidationError() from None


def timestamp(value):
    return ni_format_utc(value)


def validate_reset_floors(connection, admission):
    """Closed durable discard proof. No assertions of historical processing."""
    from types import SimpleNamespace
    from app.network_metadata.canonical import observation_uuid, source_event_identity
    epoch_row = connection.execute("SELECT * FROM projection_source_reset_epoch").fetchone()
    names = [column[0] for column in connection.execute("SELECT * FROM projection_source_reset_epoch LIMIT 0").description]
    epoch = dict(zip(names, epoch_row))
    canonical_uuid(epoch["reset_epoch_id"], 4)
    ni_timestamp(epoch["reset_at_utc"], canonical=True)
    digest(epoch["source_snapshot_digest"])
    if type(epoch["floor_count"]) is not int or epoch["floor_count"] < 0:
        raise ValueError
    if epoch["admission_digest"] != admission.digest:
        raise ValueError
    columns = [column[0] for column in connection.execute("SELECT * FROM projection_source_reset_floors LIMIT 0").description]
    floors = []
    for row in connection.execute("SELECT * FROM projection_source_reset_floors ORDER BY source_generation_id"):
        floor = dict(zip(columns, row))
        if floor.pop("reset_epoch_id") != epoch["reset_epoch_id"] or floor.pop("reset_at_utc") != epoch["reset_at_utc"]:
            raise ValueError
        canonical_uuid(floor["source_generation_id"], 4)
        matches = [b for b in admission.bindings if b.binding_digest == floor["capture_scope_binding_digest"]]
        if len(matches) != 1:
            raise ValueError
        admission.binding_for(SimpleNamespace(**floor, capture_scope_ipv4_cidrs=matches[0].ipv4_cidrs,
            network_scope_state="within_intended_scope", event_at=floor["binding_valid_from_utc"]))
        low, high = floor["generation_start_offset"], floor["committed_byte_offset"]
        if type(low) is not int or type(high) is not int or not 0 <= low <= high:
            raise ValueError
        offset, observation = floor["last_retained_record_start_byte_offset"], floor["last_retained_observation_id"]
        if offset is None:
            if observation is not None:
                raise ValueError
        else:
            if type(offset) is not int or not low <= offset < high:
                raise ValueError
            identity = source_event_identity(floor["source_generation_id"], offset)
            if observation not in {observation_uuid(family, identity) for family in ("dns", "tls", "quic")}:
                raise ValueError
        floors.append(floor)
    if len(floors) != epoch["floor_count"] or hashlib.sha256(ni01_canonical_json(floors)).hexdigest() != epoch["source_snapshot_digest"]:
        raise ValueError
    return tuple(floors)
