from datetime import datetime, timezone

import pytest

from app.device_fingerprint_portal.extractor import extract_portal_evidence_candidate

NOW = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)


def extract(headers):
    return extract_portal_evidence_candidate(headers, source_subtype="capport_login", observed_at=NOW)


def test_android_ch_and_ua_are_normalized_without_build_id():
    result = extract({
        "User-Agent": "Mozilla/5.0 (Linux; Android 14; en-US; Pixel 8 Pro Build/UQ1A.240205.002; wv) Version/4.0 Chrome/120.0 Mobile Safari/537.36",
        "sec-ch-ua": '"Not A Brand";v="99", "Chromium";v="120"',
        "sec-ch-ua-platform": ' "Android" ',
        "sec-ch-ua-mobile": "\t?1 ",
    })
    assert result.quality_state == "valid"
    assert result.payload["platform_family"] == "android"
    assert result.payload["mobile_boolean"] is True
    assert result.payload["browser_runtime_family"] == "android_webview"
    assert result.payload["webview_or_captive_context"] == "android_webview"
    assert result.payload["model_family"] == "Pixel 8 Pro"
    assert result.payload["os_major"] == 14
    assert "UQ1A" not in repr(result.payload)


@pytest.mark.parametrize("value", ["Android", '"Android";x=1', '"Android","Linux"', '"And\\roid"', '\n"Android"'])
def test_malformed_platform_ch_falls_back_only_to_available_ua(value):
    result = extract({"sec-ch-ua-platform": value, "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Firefox/120"})
    assert result.payload["platform_family"] == "linux"
    assert result.payload["platform_source"] == "user_agent"


@pytest.mark.parametrize("value, expected", [(" ?1\t", True), ("\t?0 ", False), ("? 1", None), ('"?1"', None), ("?1,x", None)])
def test_mobile_ch_exact_grammar(value, expected):
    result = extract({"sec-ch-ua-mobile": value, "User-Agent": "Firefox/120"})
    assert result.payload["mobile_boolean"] is expected


def test_brand_list_malformed_item_poisons_ch_and_conflict_is_null():
    malformed = extract({"sec-ch-ua": '"Chromium";v="120", broken', "User-Agent": "Firefox/120"})
    assert malformed.payload["browser_runtime_family"] == "firefox"
    conflict = extract({
        "sec-ch-ua": '"Chromium";v="120"',
        "sec-ch-ua-platform": '"Linux"',
        "User-Agent": "Firefox/120",
    })
    assert conflict.payload["browser_runtime_family"] is None
    assert conflict.payload["runtime_source"] is None


def test_valid_quoted_unknown_platform_falls_back_to_user_agent():
    result = extract({
        "sec-ch-ua-platform": '"FreeBSD"',
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Firefox/120",
    })
    assert result.payload["platform_family"] == "linux"
    assert result.payload["platform_source"] == "user_agent"


def test_android_webview_brand_has_client_hint_precedence():
    result = extract({
        "sec-ch-ua": '"Chromium";v="120", "Android WebView";v="120"',
        "sec-ch-ua-platform": '"Android"',
        "sec-ch-ua-mobile": "?1",
        "User-Agent": "Firefox/120",
    })
    assert result.payload["browser_runtime_family"] == "android_webview"
    assert result.payload["runtime_source"] == "sec_ch_ua"


@pytest.mark.parametrize("value", [
    '"Chromium";v="120";foo="bar"',
    '"Chromium";v="120",',
])
def test_brand_extra_parameter_and_trailing_comma_reject_entire_client_hint(value):
    result = extract({"sec-ch-ua": value, "User-Agent": "Firefox/120"})
    assert result.payload["browser_runtime_family"] == "firefox"
    assert result.payload["runtime_source"] == "user_agent"


def test_android_webview_rule_a_is_independent():
    result = extract({
        "User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8 Build/ABC; wv) Example/1",
    })
    assert result.payload["webview_or_captive_context"] == "android_webview"
    assert result.payload["browser_runtime_family"] == "android_webview"


def test_android_webview_rule_b_is_independent():
    result = extract({
        "User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8 Build/ABC) Version/4.0 Chrome/120 Mobile Safari/537.36",
    })
    assert result.payload["webview_or_captive_context"] == "android_webview"
    assert result.payload["browser_runtime_family"] == "android_webview"


def test_internal_tab_invalidates_android_model_candidate():
    result = extract({
        "User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel\t8 Build/ABC) Chrome/120 Mobile",
    })
    assert result.payload["platform_family"] == "android"
    assert result.payload["os_major"] == 14
    assert result.payload["model_family"] is None
    assert result.payload["model_source"] is None


def test_ios_major_captive_helper_and_missing_or_oversized_headers():
    ios = extract({"User-Agent": "CaptiveNetworkSupport Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) Version/17.0 Safari/605.1"})
    assert ios.payload["platform_family"] == "ios"
    assert ios.payload["os_major"] == 17
    assert ios.payload["webview_or_captive_context"] == "captive_helper"
    assert extract({}) is None
    assert extract({"User-Agent": "Android Mobile Chrome/1 " + "x" * 1025}) is None


def test_multiple_android_models_are_ambiguous():
    result = extract({"User-Agent": "Mozilla/5.0 (Android 13; Pixel 7 Build/A) (Android 13; Pixel 8 Build/B) Chrome/120 Mobile"})
    assert result.payload["model_family"] is None
    assert result.payload["os_major"] == 13
