import pytest

from app.pending_sessions import PendingSessionClassifier


def row(
    mac,
    *,
    wireless=True,
    active=True,
    auth_status=1,
    uptime=180,
    ssid="Guest",
    blocked=False,
    **extra,
):
    value = {
        "mac": mac,
        "wireless": wireless,
        "active": active,
        "authStatus": auth_status,
        "uptime": uptime,
        "ssid": ssid,
        "blocked": blocked,
    }
    value.update(extra)
    return value


def test_classifier_filters_counts_sorts_and_normalizes():
    classifier = PendingSessionClassifier(
        min_uptime_seconds=120,
        ssid_allowlist=("Guest",),
    )
    result = classifier.classify_inventory(
        [
            row("AA-BB-CC-DD-EE-02", uptime=200),
            row("AA:BB:CC:DD:EE:01", uptime=300),
            row("AA:BB:CC:DD:EE:03", auth_status=2),
            row("AA:BB:CC:DD:EE:04", auth_status=9),
            row("AA:BB:CC:DD:EE:05", uptime=119),
            row("AA:BB:CC:DD:EE:06", ssid="Private"),
            row("AA:BB:CC:DD:EE:07", blocked=True),
            row("AA:BB:CC:DD:EE:08", wireless=False),
            row("AA:BB:CC:DD:EE:09", active=False),
            {"mac": "bad"},
        ],
        site_id="site-1",
    )

    assert result.clients_rows_received == 10
    assert result.clients_valid == 9
    assert result.clients_invalid == 1
    assert result.wireless_active_count == 7
    assert result.wired_or_non_wireless_count == 2
    assert result.authorized_active_count == 1
    assert result.unauthorized_active_count == 5
    assert result.unknown_auth_status_count == 1
    assert result.below_threshold_count == 1
    assert result.ssid_not_allowed_count == 1
    assert result.blocked_count == 1
    assert result.initial_candidate_count == 2
    assert [c.observation.mac for c in result.candidates] == [
        "AA:BB:CC:DD:EE:01",
        "AA:BB:CC:DD:EE:02",
    ]
    assert result.auth_status_counts == {"1": 5, "2": 1, "9": 1}


def test_duplicate_mac_is_counted_once_and_excluded():
    classifier = PendingSessionClassifier(
        min_uptime_seconds=1,
        ssid_allowlist=("Guest",),
    )

    result = classifier.classify_inventory(
        [
            row("AA:BB:CC:DD:EE:FF"),
            row("aa-bb-cc-dd-ee-ff"),
        ],
        site_id="site-1",
    )

    assert result.duplicate_mac_count == 1
    assert result.initial_candidate_count == 0
    assert result.candidates == ()


def test_invalid_bool_and_bool_as_integer_are_rejected():
    classifier = PendingSessionClassifier(
        min_uptime_seconds=1,
        ssid_allowlist=("Guest",),
    )

    result = classifier.classify_inventory(
        [
            row("00:00:00:00:00:01", wireless=1),
            row("00:00:00:00:00:02", auth_status=True),
            row("00:00:00:00:00:03", uptime=False),
        ],
        site_id="site-1",
    )

    assert result.clients_valid == 0
    assert result.clients_invalid == 3


def test_optional_fields_are_strictly_parsed():
    classifier = PendingSessionClassifier(
        min_uptime_seconds=1,
        ssid_allowlist=("Guest",),
    )

    result = classifier.classify_inventory(
        [
            row(
                "00:00:00:00:00:01",
                ip="192.168.1.10",
                apMac="11-22-33-44-55-66",
                radioId=1,
                channel=36,
                rssi=-55,
                snr=35,
            )
        ],
        site_id="site-1",
    )

    observation = result.candidates[0].observation
    assert observation.client_ip == "192.168.1.10"
    assert observation.ap_mac == "11:22:33:44:55:66"
    assert observation.radio_id == 1
    assert observation.channel == 36
    assert observation.rssi == -55
    assert observation.snr == 35


def test_auth_status_counts_are_read_only():
    classifier = PendingSessionClassifier(
        min_uptime_seconds=1,
        ssid_allowlist=("Guest",),
    )
    result = classifier.classify_inventory(
        [row("00:00:00:00:00:01")],
        site_id="site-1",
    )

    with pytest.raises(TypeError):
        result.auth_status_counts["1"] = 99
