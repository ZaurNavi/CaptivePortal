"""The single Ni01CanonicalJsonV1, source identity and fixed UUID namespace."""
import hashlib
import json
import uuid

from .models import NI01_OBSERVATION_NAMESPACE_UUID, SOURCE_CONTRACT_VERSION, NetworkMetadataValidationError
from .validation import canonical_uuid, integer


def ni01_canonical_json(value):
    def check(item):
        if type(item) in (str, int, bool) or item is None:
            return
        if type(item) is list:
            for child in item:
                check(child)
            return
        if type(item) is dict and all(type(key) is str for key in item):
            for child in item.values():
                check(child)
            return
        raise NetworkMetadataValidationError()
    try:
        check(value)
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise NetworkMetadataValidationError() from None


Ni01CanonicalJsonV1 = ni01_canonical_json


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def semantic_digest(value):
    return sha256(ni01_canonical_json(value))


def source_event_identity(source_generation_id, record_start_byte_offset):
    canonical_uuid(source_generation_id, 4)
    integer(record_start_byte_offset)
    return f"{SOURCE_CONTRACT_VERSION}:{source_generation_id}:{record_start_byte_offset}"


def observation_uuid(family, identity):
    if family not in {"dns", "tls", "quic"}:
        raise NetworkMetadataValidationError()
    value = ni01_canonical_json({"family": family, "schema_version": 1,
                                "source_event_identity": identity}).decode("utf-8")
    return str(uuid.uuid5(uuid.UUID(NI01_OBSERVATION_NAMESPACE_UUID), value))
