"""Narrow proof for the default-off, one-shot portal Client Hints probe."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from flask import Response

from app.device_fingerprint_portal.client_hints_probe import (
    ACCEPT_CH,
    CLEAR_CLIENT_HINTS,
    PortalClientHintsProbe,
    ProbeConfig,
    SanitizedProbeRecorder,
    normalize_candidate_headers,
    probe_config_from_env,
)
from app.device_fingerprint_portal.extractor import extract_portal_evidence_candidate


class Clock:
    def __init__(self):
        self.value = 0.0

    def monotonic(self):
        return self.value


class Recorder:
    def __init__(self):
        self.events = []

    def record(self, event):
        self.events.append(event)


def probe(clock, recorder=None, *, capacity=2, ttl=3):
    recorder = recorder or Recorder()
    return (
        PortalClientHintsProbe(
            ProbeConfig(True, ttl, capacity, str(Path.cwd() / "research-output.jsonl")),
            recorder=recorder,
            monotonic=clock.monotonic,
            now=lambda: datetime(2026, 9, 17, tzinfo=timezone.utc),
        ),
        recorder,
    )


def apply(candidate, headers=None, *, site="site-1", mac="AA:BB:CC:DD:EE:FF",
          subtype="omada_external_portal", secure=True):
    response = Response("unchanged", status=200)
    candidate.apply(
        response=response, headers=headers or {}, site_id=site, client_mac=mac,
        source_subtype=subtype, secure=secure,
    )
    assert response.get_data(as_text=True) == "unchanged"
    assert response.status_code == 200
    return response


def test_probe_config_is_default_off_and_requires_explicit_bounds_and_output():
    assert probe_config_from_env({}) == ProbeConfig(False)
    assert probe_config_from_env({"DEVICE_FINGERPRINT_CLIENT_HINTS_PROBE_ENABLED": "false",
                                  "DEVICE_FINGERPRINT_CLIENT_HINTS_PROBE_TTL_SECONDS": "bad"}) == ProbeConfig(False)
    with pytest.raises(ValueError):
        probe_config_from_env({"DEVICE_FINGERPRINT_CLIENT_HINTS_PROBE_ENABLED": "true"})
    with pytest.raises(ValueError):
        probe_config_from_env({"DEVICE_FINGERPRINT_CLIENT_HINTS_PROBE_ENABLED": "true",
                               "DEVICE_FINGERPRINT_CLIENT_HINTS_PROBE_TTL_SECONDS": "3",
                               "DEVICE_FINGERPRINT_CLIENT_HINTS_PROBE_MAX_ENTRIES": "2",
                               "DEVICE_FINGERPRINT_CLIENT_HINTS_PROBE_OUTPUT_PATH": "relative.jsonl"})
    assert probe_config_from_env({"DEVICE_FINGERPRINT_CLIENT_HINTS_PROBE_ENABLED": "true",
                                  "DEVICE_FINGERPRINT_CLIENT_HINTS_PROBE_TTL_SECONDS": "3",
                                  "DEVICE_FINGERPRINT_CLIENT_HINTS_PROBE_MAX_ENTRIES": "2",
                                  "DEVICE_FINGERPRINT_CLIENT_HINTS_PROBE_OUTPUT_PATH": str(Path.cwd() / "probe.jsonl")}).enabled


def test_one_shot_request_observation_and_teardown_are_bounded_and_sanitized():
    clock = Clock()
    candidate, recorder = probe(clock)
    first = apply(candidate)
    assert first.headers["Accept-CH"] == ACCEPT_CH
    assert "Clear-Site-Data" not in first.headers
    assert candidate.pending_count == 1

    raw_canary = "PRIVATE_UNCONTROLLED_MODEL_8291"
    second = apply(candidate, {
        "Sec-CH-UA-Model": f'"{raw_canary}"',
        "Sec-CH-UA-Platform-Version": '"15.2.1"',
        "Sec-CH-UA-Form-Factors": '"Mobile", "Tablet"',
    })
    assert second.headers["Clear-Site-Data"] == CLEAR_CLIENT_HINTS
    assert "Accept-CH" not in second.headers
    assert candidate.pending_count == 0
    assert len(recorder.events) == 1
    event = recorder.events[0]
    assert event["observation"]["model_normalization_state"] == "UNUSABLE"
    assert event["observation"]["normalized_platform_version_major_candidate"] == 15
    assert event["observation"]["normalized_form_factors_candidate"] == ("mobile", "tablet")
    assert raw_canary not in json.dumps(event)
    assert "AA:BB:CC:DD:EE:FF" not in json.dumps(event)
    assert "site-1" not in json.dumps(event)
    assert apply(candidate, {"Sec-CH-UA-Model": '"Pixel 8"'}).headers["Clear-Site-Data"] == CLEAR_CLIENT_HINTS
    assert candidate.pending_count == 0
    assert "Accept-CH" not in apply(candidate).headers
    assert candidate.lifecycle_entry_count <= 2


def test_missing_expired_capacity_and_insecure_paths_do_not_force_requests():
    clock = Clock()
    candidate, recorder = probe(clock, capacity=1)
    assert "Accept-CH" not in apply(candidate, secure=False).headers
    assert apply(candidate).headers["Accept-CH"] == ACCEPT_CH
    assert "Accept-CH" not in apply(candidate, mac="AA:BB:CC:DD:EE:01").headers
    assert apply(candidate).headers["Clear-Site-Data"] == CLEAR_CLIENT_HINTS
    assert recorder.events[-1]["observation"]["lifecycle_result"] == "MISSING"
    assert "Accept-CH" not in apply(candidate).headers
    clock.value = 3.0
    assert apply(candidate).headers["Accept-CH"] == ACCEPT_CH
    clock.value = 6.0
    assert apply(candidate).headers["Clear-Site-Data"] == CLEAR_CLIENT_HINTS
    assert recorder.events[-1]["event_type"] == "probe_expired"
    assert candidate.pending_count == 0
    assert candidate.lifecycle_entry_count == 0


def test_site_mac_and_source_subtype_are_independent_lifecycle_keys():
    clock = Clock()
    candidate, recorder = probe(clock, capacity=4)
    apply(candidate)
    for kwargs in ({"site": "other-site"}, {"mac": "AA:BB:CC:DD:EE:02"},
                   {"subtype": "capport_login"}):
        assert "Clear-Site-Data" not in apply(candidate, **kwargs).headers
    assert candidate.pending_count == 4
    assert apply(candidate, {"Sec-CH-UA-Model": '"Pixel 8"'}).headers["Clear-Site-Data"] == CLEAR_CLIENT_HINTS
    assert recorder.events[-1]["observation"]["normalized_model_family_candidate"] == "pixel"
    assert candidate.pending_count == 3


@pytest.mark.parametrize("raw,state,family", [
    ('"Pixel  8"', "NORMALIZED", "pixel"),
    ('""', "UNUSABLE", None),
    ('"' + "A" * 65 + '"', "UNUSABLE", None),
    ('"Pixel\n8"', "UNUSABLE", None),
    ('"AA:BB:CC:DD:EE:FF"', "UNUSABLE", None),
    ('"123e4567-e89b-12d3-a456-426614174000"', "UNUSABLE", None),
    ('"Pixel Build/AB12"', "UNUSABLE", None),
    ("Pixel 8", "UNUSABLE", None),
])
def test_model_candidate_shapes(raw, state, family):
    result = normalize_candidate_headers({"Sec-CH-UA-Model": raw}, source_subtype="capport_login")
    assert result.model_normalization_state == state
    assert result.normalized_model_family_candidate == family
    assert raw not in repr(result)


@pytest.mark.parametrize("raw,state,major", [
    ('"0.0"', "NORMALIZED", 0),
    ('"999.1.2.3"', "NORMALIZED", 999),
    ('"14.2"', "NORMALIZED", 14),
    ('"14.bad"', "UNUSABLE", None),
    ("14.2", "UNUSABLE", None),
    ('"' + "1" * 65 + '"', "UNUSABLE", None),
    ('"14.\n2"', "UNUSABLE", None),
])
def test_platform_version_candidate_shapes(raw, state, major):
    result = normalize_candidate_headers({"Sec-CH-UA-Platform-Version": raw}, source_subtype="capport_login")
    assert result.platform_version_normalization_state == state
    assert result.normalized_platform_version_major_candidate == major


@pytest.mark.parametrize("raw,state,factors", [
    ('"Mobile"', "NORMALIZED", ("mobile",)),
    ('"Tablet"', "NORMALIZED", ("tablet",)),
    ('"Desktop"', "NORMALIZED", ("desktop",)),
    ('"tablet", "Mobile", "mobile"', "NORMALIZED", ("mobile", "tablet")),
    ('"Car"', "UNUSABLE", None),
    ('"mobile",bad', "UNUSABLE", None),
    ("x" * 129, "UNUSABLE", None),
])
def test_form_factor_candidate_shapes(raw, state, factors):
    result = normalize_candidate_headers({"Sec-CH-UA-Form-Factors": raw}, source_subtype="capport_login")
    assert result.form_factors_normalization_state == state
    assert result.normalized_form_factors_candidate == factors


def test_normalization_is_closed_world_and_never_returns_raw_header_values():
    observed = normalize_candidate_headers({
        "Sec-CH-UA-Model": '"Pixel 8"',
        "Sec-CH-UA-Platform-Version": '"14.0"',
        "Sec-CH-UA-Form-Factors": '"Mobile"',
    }, source_subtype="capport_login")
    assert observed.normalized_model_family_candidate == "pixel"
    assert observed.normalized_platform_version_major_candidate == 14
    assert observed.normalized_form_factors_candidate == ("mobile",)
    invalid = normalize_candidate_headers({
        "Sec-CH-UA-Model": '"Build/private"',
        "Sec-CH-UA-Platform-Version": '"14.bad"',
        "Sec-CH-UA-Form-Factors": '"Car"',
    }, source_subtype="capport_login")
    assert (invalid.model_normalization_state, invalid.platform_version_normalization_state,
            invalid.form_factors_normalization_state) == ("UNUSABLE", "UNUSABLE", "UNUSABLE")
    assert invalid.normalized_model_family_candidate is None
    with pytest.raises(ValueError):
        normalize_candidate_headers({}, source_subtype="not_an_entry")


def test_recorder_writes_only_sanitized_event_with_private_file_mode(tmp_path):
    path = tmp_path / "safe.jsonl"
    clock = Clock()
    candidate = PortalClientHintsProbe(
        ProbeConfig(True, 3, 2, str(path)),
        recorder=SanitizedProbeRecorder(str(path)),
        monotonic=clock.monotonic,
        now=lambda: datetime(2026, 9, 17, tzinfo=timezone.utc),
    )
    apply(candidate)
    apply(candidate, {"Sec-CH-UA-Model": '"unknown-secret-model"'})
    content = path.read_text(encoding="ascii")
    assert len(content.splitlines()) == 1
    assert "unknown-secret-model" not in content
    assert "AA:BB:CC:DD:EE:FF" not in content
    assert "site-1" not in content
    assert json.loads(content)["observation"]["model_normalization_state"] == "UNUSABLE"


def test_privacy_canaries_never_enter_observation_lifecycle_telemetry_or_output():
    class Telemetry:
        def __init__(self):
            self.events = []

        def emit(self, event, **fields):
            self.events.append((event, fields))

    clock = Clock()
    recorder = Recorder()
    telemetry = Telemetry()
    candidate = PortalClientHintsProbe(
        ProbeConfig(True, 3, 2, "C:/explicit/probe.jsonl"),
        recorder=recorder, telemetry=telemetry, monotonic=clock.monotonic,
    )
    request_headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8 Build/PRIVATE_UA_CANARY_8901; wv) Chrome/120 Mobile",
        "Sec-CH-UA-Model": '"PRIVATE_MODEL_CANARY_8902"',
        "Sec-CH-UA-Platform-Version": '"PRIVATE_VERSION_CANARY_8903"',
        "Sec-CH-UA-Form-Factors": '"PRIVATE_FACTOR_CANARY_8904"',
    }
    v1 = extract_portal_evidence_candidate(
        request_headers, source_subtype="omada_external_portal",
        observed_at=datetime(2026, 9, 17, tzinfo=timezone.utc),
    )
    assert v1 is not None
    assert "PRIVATE_" not in repr(v1)
    apply(candidate)
    response = Response("unchanged")
    candidate.apply(
        response=response, headers=request_headers, site_id="site-1",
        client_mac="AA:BB:CC:DD:EE:FF", source_subtype="omada_external_portal",
        secure=True, v1_candidate=v1,
    )
    assert response.headers["Clear-Site-Data"] == CLEAR_CLIENT_HINTS
    assert candidate.pending_count == 0
    retained = repr(recorder.events) + repr(telemetry.events) + repr(candidate._pending) + repr(candidate._terminal)
    assert "PRIVATE_" not in retained
    assert len(recorder.events[0]["v1_semantic_digest"]) == 64
    assert "AA:BB:CC:DD:EE:FF" not in repr(recorder.events)
    assert "site-1" not in repr(recorder.events)
