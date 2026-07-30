from __future__ import annotations

import uuid

import pytest

from app.common.mac import (
    format_mac_colon,
    format_mac_hyphen,
    parse_mac,
)
from app.visitor_registry.snapshot_ids import (
    VISITOR_SNAPSHOT_NAMESPACE,
    build_snapshot_id,
)


def test_namespace_is_the_permanent_schema_v1_value():
    assert VISITOR_SNAPSHOT_NAMESPACE == uuid.UUID(
        "f69e1190-9a09-55fc-81c5-63fab0ce2703"
    )


def test_snapshot_id_is_stable_across_mac_formats():
    expected = build_snapshot_id(
        "session-one",
        "02:11:22:33:44:55",
    )
    assert build_snapshot_id(
        "session-one",
        "02-11-22-33-44-55",
    ) == expected
    assert build_snapshot_id(
        "session-one",
        "0211.2233.4455",
    ) == expected


def test_new_session_changes_snapshot_id():
    assert build_snapshot_id(
        "session-one",
        "02:11:22:33:44:55",
    ) != build_snapshot_id(
        "session-two",
        "02:11:22:33:44:55",
    )


@pytest.mark.parametrize(
    "value",
    [
        "02:11:22:33:44:55",
        "02-11-22-33-44-55",
        "0211.2233.4455",
        "02 11 22 33 44 55",
        "021122334455",
    ],
)
def test_shared_mac_parser_and_formatters(value):
    assert parse_mac(value) == "021122334455"
    assert format_mac_colon(value) == "02:11:22:33:44:55"
    assert format_mac_hyphen(value) == "02-11-22-33-44-55"


@pytest.mark.parametrize("value", [None, "", "zz", "02:11:22"])
def test_shared_mac_parser_rejects_invalid_input(value):
    with pytest.raises(ValueError):
        parse_mac(value)
