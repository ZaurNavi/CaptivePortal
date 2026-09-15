from copy import deepcopy

import pytest

from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.portal_schemas import PORTAL_HEADER_KEYS, validate_portal_headers_v1
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
