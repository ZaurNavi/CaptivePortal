import hashlib
import uuid
from datetime import datetime
import pytest
from app.network_metadata.canonical import ni01_canonical_json, observation_uuid, source_event_identity
from app.network_metadata.models import NetworkMetadataValidationError
from app.network_metadata.validation import ni_timestamp, ni_format_utc, strict_json
from . import GENERATION


def test_canonical_utf8_and_key_order():
    assert ni01_canonical_json({"z": [True, None], "a": "é"}) == b'{"a":"\xc3\xa9","z":[true,null]}'
    assert ni01_canonical_json({"a": "é", "z": [True, None]}) == ni01_canonical_json({"z": [True, None], "a": "é"})
    assert ni01_canonical_json("é") != ni01_canonical_json("e\u0301")


@pytest.mark.parametrize("value", [1.5, float("nan"), {1: "a"}, (1,), {1}, b"raw", datetime.now(), object()])
def test_canonical_rejects_noncontract_types(value):
    with pytest.raises(NetworkMetadataValidationError):
        ni01_canonical_json(value)


def test_fixed_identity_vector():
    identity = source_event_identity(GENERATION, 17)
    assert identity == "suricata-eve-v1:9412aebe-6e13-463b-9a93-d2e5c8475766:17"
    expected = str(uuid.uuid5(uuid.UUID("ce2387da-5bc4-5c4e-9e6a-6de970889764"),
        '{"family":"dns","schema_version":1,"source_event_identity":"' + identity + '"}'))
    assert observation_uuid("dns", identity) == expected


@pytest.mark.parametrize("value", ["2026-01-01T00:00:00Z", "2026-01-01T00:00:00.1Z",
    "2026-01-01T01:00:00+01:00", "2025-12-31T23:00:00-01:00"])
def test_timestamp_normalization(value):
    rendered = ni_format_utc(ni_timestamp(value))
    assert len(rendered) == 27 and rendered.endswith("Z")
    assert ni_format_utc(ni_timestamp(rendered, canonical=True)) == rendered


@pytest.mark.parametrize("value", ["2026-01-01T00:00:00.1234567Z", "2026-01-01T00:00:00", " 2026-01-01T00:00:00Z",
    "2026-02-30T00:00:00Z", "2026-01-01T00:00:60Z", "2026-01-01T00:00:00+24:00", None])
def test_invalid_timestamp(value):
    with pytest.raises(NetworkMetadataValidationError):
        ni_timestamp(value)


@pytest.mark.parametrize("data,category", [(b'\xff', "invalid_utf8"), (b'{', "invalid_json"),
    (b'{"nested":{"x":1,"x":2}}', "duplicate_json_member"), (b'[]', "non_object_json"),
    (b'{"n":NaN}', "invalid_json"), (b'{"n":Infinity}', "invalid_json"), (b'{"n":-Infinity}', "invalid_json")])
def test_strict_json(data, category):
    with pytest.raises(NetworkMetadataValidationError) as error:
        strict_json(data)
    assert error.value.category == category
