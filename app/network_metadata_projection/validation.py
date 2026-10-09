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
