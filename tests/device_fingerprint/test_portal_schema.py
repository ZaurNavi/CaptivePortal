from copy import deepcopy

import pytest

from app.device_fingerprint.models import DeviceFingerprintUnsupportedSchema, DeviceFingerprintValidationError
from app.device_fingerprint.portal_schemas import (
    PORTAL_HEADER_KEYS,
    PORTAL_HEADER_V2_KEYS,
    validate_portal_headers_v1,
    validate_portal_headers_v2,
)
from app.device_fingerprint.schema_registry import build_production_schema_registry


def payload():
    return {
        "platform_family": "android", "mobile_boolean": True,
        "browser_runtime_family": "chromium", "webview_or_captive_context": None,
        "model_family": "Pixel 8", "os_major": 14,
        "platform_source": "sec_ch_ua_platform", "mobile_source": "sec_ch_ua_mobile",
        "runtime_source": "combined", "context_source": None,
        "model_source": "user_agent", "os_major_source": "user_agent",
        "ua_present": True, "sec_ch_ua_present": True,
        "sec_ch_ua_platform_present": True, "sec_ch_ua_mobile_present": True,
    }


def test_exact_portal_schema_is_registered_as_fifth_production_schema():
    value = payload()
    assert set(value) == PORTAL_HEADER_KEYS
    assert build_production_schema_registry().validate("portal_headers", 1, value) == value


@pytest.mark.parametrize("mutation", [
    lambda value: value.update(raw_user_agent="secret"),
    lambda value: value.pop("platform_family"),
    lambda value: value.update(os_major=100),
    lambda value: value.update(mobile_boolean=1),
    lambda value: value.update(model_family="AA:BB:CC:DD:EE:FF"),
    lambda value: value.update(platform_family=None),
    lambda value: value.update(runtime_source="user_agent", ua_present=False),
    lambda value: value.update(
        platform_family=None, mobile_boolean=None, browser_runtime_family=None,
        webview_or_captive_context=None, model_family=None, os_major=None,
        platform_source=None, mobile_source=None, runtime_source=None,
        context_source=None, model_source=None, os_major_source=None,
    ),
])
def test_invalid_or_cross_field_portal_schema_is_rejected(mutation):
    value = deepcopy(payload())
    mutation(value)
    with pytest.raises(DeviceFingerprintValidationError):
        validate_portal_headers_v1(value)


def payload_v2():
    return {
        "model_family": "Nokia G21",
        "os_major": 13,
        "form_factor_mobile": True,
        "form_factor_tablet": False,
        "form_factor_desktop": False,
        "model_source": "sec_ch_ua_model",
        "os_major_source": "sec_ch_ua_platform_version",
        "form_factors_source": "sec_ch_ua_form_factors",
    }


def test_exact_normalized_v2_contract_is_production_registered():
    value = payload_v2()
    assert set(value) == PORTAL_HEADER_V2_KEYS
    assert validate_portal_headers_v2(value) == value
    assert build_production_schema_registry().validate("portal_headers", 2, value) == value
    with pytest.raises(DeviceFingerprintUnsupportedSchema):
        build_production_schema_registry().validate("portal_headers", 3, value)


@pytest.mark.parametrize("mutation", [
    lambda value: value.update(model_family=None, model_source=None),
    lambda value: value.update(os_major=None, os_major_source=None),
    lambda value: value.update(form_factor_mobile=None, form_factor_tablet=None,
                               form_factor_desktop=None, form_factors_source=None),
    lambda value: value.update(model_family=None, model_source=None,
                               form_factor_mobile=None, form_factor_tablet=None,
                               form_factor_desktop=None, form_factors_source=None),
    lambda value: value.update(os_major=None, os_major_source=None,
                               form_factor_mobile=None, form_factor_tablet=None,
                               form_factor_desktop=None, form_factors_source=None),
    lambda value: value.update(model_family=None, model_source=None,
                               os_major=None, os_major_source=None),
    lambda value: value.update(form_factor_mobile=True, form_factor_tablet=True),
    lambda value: value.update(model_family="SM-S918B"),
    lambda value: value.update(model_family="NovelModel X9"),
    lambda value: value.update(model_family="A" * 64),
    lambda value: value.update(os_major=0),
    lambda value: value.update(os_major=999),
])
def test_independent_normalized_v2_groups_and_edges_are_accepted(mutation):
    value = payload_v2()
    mutation(value)
    assert validate_portal_headers_v2(value) == value


@pytest.mark.parametrize("mutation", [
    lambda value: value.update(raw_user_agent="PRIVATE_RAW_UA_CANARY"),
    lambda value: value.update(**{"Sec-CH-UA-Model": '"PRIVATE_RAW_CH_CANARY"'}),
    lambda value: value.pop("model_family"),
    lambda value: value.update(model_family=""),
    lambda value: value.update(model_family="A" * 65),
    lambda value: value.update(model_family="Nokia\nG21"),
    lambda value: value.update(model_family="Nokia\tG21"),
    lambda value: value.update(model_family="Nokía G21"),
    lambda value: value.update(model_family="AA:BB:CC:DD:EE:FF"),
    lambda value: value.update(model_family="123e4567-e89b-12d3-a456-426614174000"),
    lambda value: value.update(model_family="Nokia Build ABC"),
    lambda value: value.update(model_family="Nokia  G21"),
    lambda value: value.update(model_family="Nokia G21 "),
    lambda value: value.update(model_family=None),
    lambda value: value.update(model_source=None),
    lambda value: value.update(model_source="user_agent"),
    lambda value: value.update(os_major=-1),
    lambda value: value.update(os_major=1000),
    lambda value: value.update(os_major=True),
    lambda value: value.update(os_major="13"),
    lambda value: value.update(os_major=None),
    lambda value: value.update(os_major_source=None),
    lambda value: value.update(os_major_source="sec_ch_ua_platform"),
    lambda value: value.update(form_factor_mobile=False),
    lambda value: value.update(form_factor_mobile=None),
    lambda value: value.update(form_factor_mobile=1),
    lambda value: value.update(form_factor_mobile=False, form_factor_tablet=False,
                               form_factor_desktop=False),
    lambda value: value.update(form_factors_source=None),
    lambda value: value.update(form_factors_source="user_agent"),
    lambda value: value.update(form_factor_mobile=None, form_factor_tablet=None,
                               form_factor_desktop=None),
    lambda value: value.update(model_family=None, model_source=None,
                               os_major=None, os_major_source=None,
                               form_factor_mobile=None, form_factor_tablet=None,
                               form_factor_desktop=None, form_factors_source=None),
])
def test_invalid_normalized_v2_shapes_and_provenance_fail_closed(mutation):
    value = deepcopy(payload_v2())
    mutation(value)
    with pytest.raises(DeviceFingerprintValidationError):
        validate_portal_headers_v2(value)


def test_v1_payload_and_registry_semantics_remain_independent_of_v2():
    value = payload()
    assert validate_portal_headers_v1(value) == value
    assert build_production_schema_registry().validate("portal_headers", 1, value) == value
    with pytest.raises(DeviceFingerprintValidationError):
        validate_portal_headers_v1(payload_v2())
    with pytest.raises(DeviceFingerprintValidationError):
        validate_portal_headers_v2(value)
