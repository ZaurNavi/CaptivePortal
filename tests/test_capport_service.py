from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier, Event
from unittest.mock import Mock, call, patch

import pytest

from app.auth_telemetry import events
from app.capport.models import CapportConfig
from app.capport.service import CapportService
from app.controllers.omada import OmadaProvider
from app.models import Result


class CapturingTelemetry:
    def __init__(self):
        self.records = []

    def safe_emit_system(self, event, level="info", **fields):
        self.records.append((event, level, fields))
        return True


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def settings(**overrides):
    values = {
        "host": "127.0.0.1",
        "capport_site_id": "site-1",
        "capport_public_base_url": "https://portal.example",
        "capport_api_path": "/capport/api",
        "capport_login_path": "/capport/login",
        "capport_allowed_client_networks": ("192.168.1.0/24",),
        "capport_client_cache_ttl_seconds": 2,
        "capport_failure_cache_ttl_seconds": 2,
    }
    values.update(overrides)
    return values


def config(**overrides):
    return CapportConfig.from_settings(settings(**overrides))


def controller_with(
    *,
    found=True,
    auth_status=0,
    active=True,
):
    controller = Mock()
    controller.get_clients.return_value = Result.ok(
        data={
            "clients": (
                [
                    {
                        "client_ip": "192.168.1.10",
                        "client_mac": "AA:BB:CC:DD:EE:FF",
                        # Deliberately not authoritative.
                        "authStatus": None,
                        "active": None,
                    }
                ]
                if found
                else []
            ),
        }
    )
    controller.get_client.return_value = Result.ok(
        data={
            "authStatus": auth_status,
            "active": active,
            "http_status": 200,
            "error_code": 0,
        }
    )
    return controller


def fallback_controller(
    *,
    auth_status=2,
    active=True,
):
    controller = Mock()
    controller.get_clients.return_value = Result.ok(
        data={
            "clients": [
                {
                    "client_ip": "192.168.1.10",
                    "client_mac": "AA:BB:CC:DD:EE:FF",
                    "authStatus": auth_status,
                    "active": active,
                }
            ],
        }
    )
    controller.get_client.return_value = Result.fail(
        error="API_ERROR",
        data={
            "error_code": -41011,
            "authStatus": None,
            "active": None,
        },
    )
    return controller


def service_for(controller, **kwargs):
    return CapportService(
        controller,
        config(),
        CapturingTelemetry(),
        **kwargs,
    )


def test_unauthorized_client_is_captive():
    controller = controller_with(auth_status=0)

    state = service_for(controller).resolve("192.168.1.10")

    assert state.allowed
    assert state.client_found
    assert state.captive
    controller.get_client.assert_called_once_with(
        "site-1",
        "AA:BB:CC:DD:EE:FF",
    )


def test_authorized_client_is_not_captive():
    controller = controller_with(auth_status=2)

    state = service_for(controller).resolve("192.168.1.10")

    assert state.client_found
    assert state.captive is False
    assert state.client.auth_status == 2


def test_list_with_only_ip_mac_uses_authoritative_get_client_state():
    omada = object.__new__(OmadaProvider)
    omada._omada_url = "https://controller.example"
    omada._omada_id = "controller-id"
    omada._verify_ssl = True
    omada._get_token = Mock(
        return_value=Result.ok(data={"token": "test-token"})
    )
    list_response = FakeResponse(
        {
            "errorCode": 0,
            "result": {
                "data": [
                    {
                        "ip": "192.168.1.10",
                        "mac": "aa-bb-cc-dd-ee-ff",
                    }
                ]
            },
        }
    )
    detail_response = FakeResponse(
        {
            "errorCode": 0,
            "result": {
                "authStatus": 2,
                "active": True,
            },
        }
    )
    service = service_for(omada)

    with patch(
        "app.controllers.omada.requests.get",
        side_effect=[list_response, detail_response],
    ):
        state = service.resolve("192.168.1.10")

    assert state.client_found
    assert state.client.auth_status == 2
    assert state.captive is False
    assert omada._get_token.call_count == 2


def test_unknown_guest_client_is_fail_safe_captive():
    controller = controller_with(found=False)

    state = service_for(controller).resolve("192.168.1.10")

    assert state.allowed
    assert state.client_found is False
    assert state.captive
    assert state.lookup_failed is False
    assert state.reason == "CLIENT_NOT_FOUND"
    controller.get_client.assert_not_called()


def test_controller_failure_is_fail_safe_captive():
    controller = Mock()
    controller.get_clients.return_value = Result.fail(
        error="TOKEN_FAILED",
        message="token unavailable",
    )

    state = service_for(controller).resolve("192.168.1.10")

    assert state.allowed
    assert state.captive
    assert state.lookup_failed
    assert state.reason == "TOKEN_FAILED"


def test_authoritative_state_failure_is_fail_safe():
    controller = controller_with()
    controller.get_client.return_value = Result.fail(
        error="HTTP_ERROR"
    )

    state = service_for(controller).resolve("192.168.1.10")

    assert state.lookup_failed
    assert state.captive
    assert state.reason == "HTTP_ERROR"


def test_detail_minus_41011_uses_exact_authorized_list_fallback():
    controller = fallback_controller(
        auth_status=2,
        active=True,
    )
    telemetry = CapturingTelemetry()
    service = CapportService(
        controller,
        config(),
        telemetry,
    )

    state = service.resolve("192.168.1.10")
    cached_state = service.resolve("192.168.1.10")

    assert state.client_found
    assert state.lookup_failed is False
    assert state.captive is False
    assert state.client.auth_status == 2
    assert state.client.active is True
    assert cached_state.captive is False
    assert cached_state.cache_hit is True
    controller.get_clients.assert_called_once()
    controller.get_client.assert_called_once()

    fallback_events = [
        (level, fields)
        for event, level, fields in telemetry.records
        if event == events.CAPPORT_DETAIL_LOOKUP_FALLBACK
    ]
    assert fallback_events == [
        (
            "warning",
            {
                "site_id": "site-1",
                "detail_error_code": -41011,
                "auth_status": 2,
                "active": True,
                "client_ip": "192.168.1.10",
                "client_mac": "AA:BB:CC:DD:EE:FF",
            },
        )
    ]


@pytest.mark.parametrize(
    ("auth_status", "active"),
    [
        (1, True),
        (0, True),
        (2, False),
        (2, None),
    ],
)
def test_detail_minus_41011_list_fallback_remains_captive(
    auth_status,
    active,
):
    controller = fallback_controller(
        auth_status=auth_status,
        active=active,
    )

    state = service_for(controller).resolve("192.168.1.10")

    assert state.client_found
    assert state.lookup_failed is False
    assert state.captive
    assert state.client.auth_status == auth_status
    assert state.client.active is active


def test_detail_minus_41011_rejects_mismatched_list_identity():
    controller = fallback_controller()
    service = service_for(controller)
    identity = service._build_identity_snapshot(
        [
            {
                "client_ip": "192.168.1.10",
                "client_mac": "AA:BB:CC:DD:EE:FF",
                "authStatus": 2,
                "active": True,
            }
        ],
        generation=0,
    )
    identity.fallback_by_ip["192.168.1.10"] = replace(
        identity.fallback_by_ip["192.168.1.10"],
        client_mac="AA:BB:CC:DD:EE:00",
    )
    service._identity_cache["site-1"] = identity

    state = service.resolve("192.168.1.10")

    assert state.client_found is False
    assert state.lookup_failed
    assert state.captive
    assert state.reason == "DETAIL_LOOKUP_FALLBACK_REJECTED"


def test_detail_minus_41011_rejects_duplicate_ip_fallback():
    controller = fallback_controller()
    controller.get_clients.return_value = Result.ok(
        data={
            "clients": [
                {
                    "client_ip": "192.168.1.10",
                    "client_mac": "AA:BB:CC:DD:EE:01",
                    "authStatus": 2,
                    "active": True,
                },
                {
                    "client_ip": "192.168.1.10",
                    "client_mac": "AA:BB:CC:DD:EE:02",
                    "authStatus": 2,
                    "active": False,
                },
            ],
        }
    )

    state = service_for(controller).resolve("192.168.1.10")

    assert state.client_found is False
    assert state.lookup_failed
    assert state.captive
    assert state.reason == "DETAIL_LOOKUP_FALLBACK_REJECTED"
    controller.get_client.assert_called_once_with(
        "site-1",
        "AA:BB:CC:DD:EE:01",
    )


@pytest.mark.parametrize("detail_error", ["HTTP_ERROR", "TOKEN_FAILED"])
def test_non_api_detail_error_never_uses_list_fallback(
    detail_error,
):
    controller = fallback_controller()
    controller.get_client.return_value = Result.fail(
        error=detail_error,
        data={"error_code": -41011},
    )
    telemetry = CapturingTelemetry()
    service = CapportService(
        controller,
        config(),
        telemetry,
    )

    state = service.resolve("192.168.1.10")

    assert state.client_found is False
    assert state.lookup_failed
    assert state.captive
    assert state.reason == detail_error
    assert all(
        event != events.CAPPORT_DETAIL_LOOKUP_FALLBACK
        for event, _level, _fields in telemetry.records
    )


def test_missing_authoritative_auth_status_is_fail_safe():
    controller = controller_with()
    controller.get_client.return_value = Result.ok(
        data={"authStatus": None, "active": True}
    )

    state = service_for(controller).resolve("192.168.1.10")

    assert state.lookup_failed
    assert state.captive
    assert state.reason == "MALFORMED_CLIENT_STATE"


def test_outside_network_never_calls_controller():
    controller = Mock()

    state = service_for(controller).resolve("10.0.0.10")

    assert state.allowed is False
    assert state.reason == "CLIENT_NOT_ALLOWED"
    controller.get_clients.assert_not_called()
    controller.get_client.assert_not_called()


def test_invalid_ip_never_calls_controller():
    controller = Mock()

    state = service_for(controller).resolve("not-an-ip")

    assert state.allowed is False
    assert state.reason == "INVALID_CLIENT_IP"
    controller.get_clients.assert_not_called()


def test_successful_resolution_cache_avoids_repeated_controller_calls():
    controller = controller_with(auth_status=2)
    service = service_for(controller)

    first = service.resolve("192.168.1.10")
    second = service.resolve("192.168.1.10")

    assert first.cache_hit is False
    assert second.cache_hit is True
    controller.get_clients.assert_called_once()
    controller.get_client.assert_called_once()


def test_force_refresh_rebinds_cached_ip_to_current_mac():
    controller = Mock()
    controller.get_clients.side_effect = [
        Result.ok(
            data={
                "clients": [
                    {
                        "client_ip": "192.168.1.10",
                        "client_mac": "AA:BB:CC:DD:EE:01",
                    }
                ]
            }
        ),
        Result.ok(
            data={
                "clients": [
                    {
                        "client_ip": "192.168.1.10",
                        "client_mac": "AA:BB:CC:DD:EE:02",
                    }
                ]
            }
        ),
    ]
    controller.get_client.side_effect = [
        Result.ok(data={"authStatus": 2, "active": True}),
        Result.ok(data={"authStatus": 0, "active": True}),
    ]
    service = service_for(controller)

    old_state = service.resolve("192.168.1.10")
    new_state = service.resolve(
        "192.168.1.10",
        force_refresh=True,
    )

    assert old_state.client.client_mac == "AA:BB:CC:DD:EE:01"
    assert old_state.captive is False
    assert new_state.client.client_mac == "AA:BB:CC:DD:EE:02"
    assert new_state.captive
    assert controller.get_clients.call_count == 2
    assert controller.get_client.call_args_list == [
        call("site-1", "AA:BB:CC:DD:EE:01"),
        call("site-1", "AA:BB:CC:DD:EE:02"),
    ]


def test_slow_old_mac_detail_is_discarded_after_identity_refresh():
    old_detail_started = Event()
    identity_refreshed = Event()
    release_old_detail = Event()
    identity_calls = 0
    controller = Mock()

    def load_identity(_site_id):
        nonlocal identity_calls
        identity_calls += 1
        client_mac = (
            "AA:BB:CC:DD:EE:01"
            if identity_calls == 1
            else "AA:BB:CC:DD:EE:02"
        )
        if identity_calls == 2:
            identity_refreshed.set()
        return Result.ok(
            data={
                "clients": [
                    {
                        "client_ip": "192.168.1.10",
                        "client_mac": client_mac,
                    }
                ]
            }
        )

    def load_detail(_site_id, client_mac):
        if client_mac == "AA:BB:CC:DD:EE:01":
            old_detail_started.set()
            assert release_old_detail.wait(timeout=2)
            return Result.ok(
                data={"authStatus": 2, "active": True}
            )
        return Result.ok(
            data={"authStatus": 0, "active": True}
        )

    controller.get_clients.side_effect = load_identity
    controller.get_client.side_effect = load_detail
    service = service_for(controller)

    with ThreadPoolExecutor(max_workers=2) as executor:
        old_lookup = executor.submit(
            service.resolve,
            "192.168.1.10",
        )
        assert old_detail_started.wait(timeout=2)
        refreshed_lookup = executor.submit(
            service.resolve,
            "192.168.1.10",
            force_refresh=True,
        )
        assert identity_refreshed.wait(timeout=2)
        release_old_detail.set()
        old_result = old_lookup.result(timeout=2)
        refreshed_result = refreshed_lookup.result(timeout=2)

    next_result = service.resolve("192.168.1.10")

    assert old_result.client.client_mac == "AA:BB:CC:DD:EE:02"
    assert refreshed_result.client.client_mac == "AA:BB:CC:DD:EE:02"
    assert next_result.client.client_mac == "AA:BB:CC:DD:EE:02"
    assert old_result.captive
    assert refreshed_result.captive
    assert next_result.captive
    assert controller.get_client.call_args_list.count(
        call("site-1", "AA:BB:CC:DD:EE:01")
    ) == 1
    assert controller.get_client.call_args_list.count(
        call("site-1", "AA:BB:CC:DD:EE:02")
    ) == 1


def test_slow_old_mac_fallback_is_not_saved_after_identity_change():
    old_detail_started = Event()
    identity_refreshed = Event()
    release_old_detail = Event()
    identity_calls = 0
    controller = Mock()
    telemetry = CapturingTelemetry()

    def load_identity(_site_id):
        nonlocal identity_calls
        identity_calls += 1
        old_identity = identity_calls == 1
        if not old_identity:
            identity_refreshed.set()
        return Result.ok(
            data={
                "clients": [
                    {
                        "client_ip": "192.168.1.10",
                        "client_mac": (
                            "AA:BB:CC:DD:EE:01"
                            if old_identity
                            else "AA:BB:CC:DD:EE:02"
                        ),
                        "authStatus": 2 if old_identity else 0,
                        "active": True,
                    }
                ]
            }
        )

    def load_detail(_site_id, client_mac):
        if client_mac == "AA:BB:CC:DD:EE:01":
            old_detail_started.set()
            assert release_old_detail.wait(timeout=2)
        return Result.fail(
            error="API_ERROR",
            data={"error_code": -41011},
        )

    controller.get_clients.side_effect = load_identity
    controller.get_client.side_effect = load_detail
    service = CapportService(
        controller,
        config(),
        telemetry,
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        old_lookup = executor.submit(
            service.resolve,
            "192.168.1.10",
        )
        assert old_detail_started.wait(timeout=2)
        refreshed_lookup = executor.submit(
            service.resolve,
            "192.168.1.10",
            force_refresh=True,
        )
        assert identity_refreshed.wait(timeout=2)
        release_old_detail.set()
        old_result = old_lookup.result(timeout=2)
        refreshed_result = refreshed_lookup.result(timeout=2)

    cached_result = service.resolve("192.168.1.10")

    assert old_result.client.client_mac == "AA:BB:CC:DD:EE:02"
    assert refreshed_result.client.client_mac == "AA:BB:CC:DD:EE:02"
    assert cached_result.client.client_mac == "AA:BB:CC:DD:EE:02"
    assert old_result.captive
    assert refreshed_result.captive
    assert cached_result.captive
    assert controller.get_client.call_args_list.count(
        call("site-1", "AA:BB:CC:DD:EE:01")
    ) == 1
    assert controller.get_client.call_args_list.count(
        call("site-1", "AA:BB:CC:DD:EE:02")
    ) == 1

    fallback_events = [
        fields
        for event, _level, fields in telemetry.records
        if event == events.CAPPORT_DETAIL_LOOKUP_FALLBACK
    ]
    assert len(fallback_events) == 1
    assert fallback_events[0]["client_mac"] == (
        "AA:BB:CC:DD:EE:02"
    )
    assert fallback_events[0]["auth_status"] == 0


def test_login_refreshes_cached_not_found_and_finds_new_client():
    controller = controller_with(auth_status=0)
    controller.get_clients.side_effect = [
        Result.ok(data={"clients": []}),
        Result.ok(
            data={
                "clients": [
                    {
                        "client_ip": "192.168.1.10",
                        "client_mac": "AA:BB:CC:DD:EE:FF",
                    }
                ],
            }
        ),
    ]
    clock = FakeClock()
    service = service_for(
        controller,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )

    api_state = service.resolve("192.168.1.10")
    login_state = service.resolve_for_login("192.168.1.10")

    assert api_state.client_found is False
    assert login_state.client_found
    assert controller.get_clients.call_count == 2
    controller.get_client.assert_called_once()
    assert clock.sleeps == [1.0]


def test_login_retry_count_and_wait_are_bounded():
    controller = controller_with(found=False)
    clock = FakeClock()
    service = service_for(
        controller,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )

    state = service.resolve_for_login("192.168.1.10")

    assert state.client_found is False
    assert controller.get_clients.call_count == 5
    assert sum(clock.sleeps) <= 5.0
    assert clock.now <= 5.0


def test_failure_cooldown_avoids_sequential_retries():
    controller = Mock()
    controller.get_clients.return_value = Result.fail(
        error="HTTP_ERROR"
    )
    service = service_for(controller)

    first = service.resolve("192.168.1.10")
    second = service.resolve("192.168.1.11")

    assert first.lookup_failed
    assert second.lookup_failed
    assert second.cache_hit
    controller.get_clients.assert_called_once()


def test_parallel_controller_failure_uses_one_call_and_fail_safe():
    started = Event()
    release = Event()
    controller = Mock()

    def fail(_site_id):
        started.set()
        assert release.wait(timeout=2)
        return Result.fail(error="HTTP_ERROR")

    controller.get_clients.side_effect = fail
    service = service_for(controller)

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(
                service.resolve,
                f"192.168.1.{index}",
            )
            for index in (10, 11, 12)
        ]
        assert started.wait(timeout=2)
        release.set()
        states = [future.result(timeout=2) for future in futures]

    assert controller.get_clients.call_count == 1
    assert all(state.lookup_failed for state in states)
    assert all(state.captive for state in states)


def test_parallel_outage_calls_underlying_get_clients_once():
    omada = object.__new__(OmadaProvider)
    omada.get_clients = Mock(
        return_value=Result.fail(error="HTTP_ERROR")
    )
    service = service_for(omada)

    with ThreadPoolExecutor(max_workers=3) as executor:
        states = list(
            executor.map(
                service.resolve,
                (
                    "192.168.1.10",
                    "192.168.1.11",
                    "192.168.1.12",
                ),
            )
        )

    omada.get_clients.assert_called_once()
    assert all(state.lookup_failed for state in states)
    assert all(state.captive for state in states)


def test_sequential_different_ips_share_identity_snapshot():
    controller = Mock()
    controller.get_clients.return_value = Result.ok(
        data={
            "clients": [
                {
                    "client_ip": "192.168.1.10",
                    "client_mac": "AA:BB:CC:DD:EE:10",
                },
                {
                    "client_ip": "192.168.1.11",
                    "client_mac": "AA:BB:CC:DD:EE:11",
                },
            ]
        }
    )
    controller.get_client.return_value = Result.ok(
        data={"authStatus": 2, "active": True}
    )
    service = service_for(controller)

    first = service.resolve("192.168.1.10")
    second = service.resolve("192.168.1.11")

    assert first.client_found
    assert second.client_found
    controller.get_clients.assert_called_once_with("site-1")
    assert controller.get_client.call_count == 2


def test_parallel_different_ips_share_list_and_detail_in_parallel():
    controller = Mock()
    clients = [
        {
            "client_ip": f"192.168.1.{last_octet}",
            "client_mac": f"AA:BB:CC:DD:EE:{last_octet:02d}",
        }
        for last_octet in (10, 11, 12)
    ]
    controller.get_clients.return_value = Result.ok(
        data={"clients": clients}
    )
    detail_barrier = Barrier(3)

    def load_detail(_site_id, _client_mac):
        # This only succeeds when per-IP detail calls overlap.
        detail_barrier.wait(timeout=2)
        return Result.ok(
            data={"authStatus": 2, "active": True}
        )

    controller.get_client.side_effect = load_detail
    service = service_for(controller)

    with ThreadPoolExecutor(max_workers=3) as executor:
        states = list(
            executor.map(
                service.resolve,
                (
                    "192.168.1.10",
                    "192.168.1.11",
                    "192.168.1.12",
                ),
            )
        )

    controller.get_clients.assert_called_once_with("site-1")
    assert controller.get_client.call_count == 3
    assert all(state.client_found for state in states)
    assert all(state.captive is False for state in states)


def test_parallel_successful_requests_use_single_refresh():
    started = Event()
    release = Event()
    controller = controller_with(auth_status=2)

    def load(_site_id):
        started.set()
        assert release.wait(timeout=2)
        return Result.ok(
            data={
                "clients": [
                    {
                        "client_ip": "192.168.1.10",
                        "client_mac": "AA:BB:CC:DD:EE:FF",
                    }
                ],
            }
        )

    controller.get_clients.side_effect = load
    service = service_for(controller)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(service.resolve, "192.168.1.10")
        assert started.wait(timeout=2)
        second = executor.submit(service.resolve, "192.168.1.10")
        release.set()
        assert first.result(timeout=2).client_found
        assert second.result(timeout=2).client_found

    controller.get_clients.assert_called_once()
    controller.get_client.assert_called_once()


@pytest.mark.parametrize(
    "override",
    [
        {"capport_site_id": ""},
        {"capport_public_base_url": "http://portal.example"},
        {"capport_api_path": "capport/api"},
        {"capport_login_path": "capport/login"},
        {"capport_allowed_client_networks": ("bad-network",)},
        {"capport_client_cache_ttl_seconds": 0},
        {"capport_failure_cache_ttl_seconds": 0},
        {"host": "0.0.0.0"},
    ],
)
def test_invalid_configuration_fails_at_startup(override):
    with pytest.raises(ValueError):
        CapportConfig.from_settings(settings(**override))
