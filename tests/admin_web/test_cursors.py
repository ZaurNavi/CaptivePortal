import pytest

from app.admin_web.cursors import AdminCursorError, decode_cursor, encode_cursor


SITE = "a" * 24
IDENTITY = "10000000-0000-4000-8000-000000000001"
TIMESTAMP = "2026-01-01T00:00:00.000Z"


def test_cursor_is_versioned_site_and_filter_bound():
    filters = {"status": "open"}
    cursor = encode_cursor(
        kind="visits",
        site_id=SITE,
        timestamp=TIMESTAMP,
        identity=IDENTITY,
        filters=filters,
    )
    assert decode_cursor(
        cursor,
        kind="visits",
        site_id=SITE,
        filters=filters,
        identity_kind="uuid",
        maximum_length=4096,
    ) == (TIMESTAMP, IDENTITY)
    with pytest.raises(AdminCursorError):
        decode_cursor(
            cursor,
            kind="visits",
            site_id="b" * 24,
            filters=filters,
            identity_kind="uuid",
            maximum_length=4096,
        )
    with pytest.raises(AdminCursorError):
        decode_cursor(
            cursor,
            kind="visits",
            site_id=SITE,
            filters={"status": "closed"},
            identity_kind="uuid",
            maximum_length=4096,
        )


@pytest.mark.parametrize("value", ["not-base64!", "", "A" * 4097])
def test_malformed_cursor_never_falls_back_to_first_page(value):
    with pytest.raises(AdminCursorError):
        decode_cursor(
            value,
            kind="devices",
            site_id=SITE,
            filters={},
            identity_kind="uuid",
            maximum_length=4096,
        )
