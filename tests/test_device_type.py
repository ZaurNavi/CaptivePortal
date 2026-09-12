from __future__ import annotations

import pytest

from app.common.device_type import (
    DEVICE_TYPE_KEY_MAX_UTF8_BYTES,
    normalize_device_type_key,
)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (None, None),
        ("android", "android"),
        ("Android", "android"),
        ("ANDROID", "android"),
        (" android ", "android"),
        ("\tAndroid\n", "android"),
        ("phone", "phone"),
        ("NewVendorThing", "newvendorthing"),
    ],
)
def test_normalize_device_type_key_lexical_matrix(source, expected):
    assert normalize_device_type_key(source) == expected


@pytest.mark.parametrize(
    "source",
    [
        123,
        True,
        b"android",
        {"type": "android"},
        ["android"],
        "",
        "   ",
        "android\x00phone",
        "\ud800",
    ],
)
def test_normalize_device_type_key_rejects_invalid_sources(source):
    assert normalize_device_type_key(source) is None


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Smart  Phone", "smart  phone"),
        ("Smart-Phone", "smart-phone"),
        ("Smart_Phone", "smart_phone"),
        ("Smart.Phone/2", "smart.phone/2"),
    ],
)
def test_normalize_device_type_key_preserves_internal_structure(
    source, expected
):
    assert normalize_device_type_key(source) == expected


def test_normalize_device_type_key_enforces_utf8_byte_bounds():
    assert DEVICE_TYPE_KEY_MAX_UTF8_BYTES == 128
    assert normalize_device_type_key("a" * 128) == "a" * 128
    assert normalize_device_type_key("a" * 129) is None
    assert len(("\u0130" * 64).encode("utf-8")) == 128
    assert normalize_device_type_key("\u0130" * 64) is None


def test_normalize_device_type_key_does_not_apply_unicode_normalization():
    composed = normalize_device_type_key("É")
    decomposed = normalize_device_type_key("E\u0301")
    assert composed == "é"
    assert decomposed == "e\u0301"
    assert composed != decomposed

    full_width = normalize_device_type_key("Ａ")
    ascii_value = normalize_device_type_key("A")
    assert full_width == "ａ"
    assert ascii_value == "a"
    assert full_width != ascii_value
