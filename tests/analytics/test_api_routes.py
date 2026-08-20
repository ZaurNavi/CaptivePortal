from __future__ import annotations

import ipaddress
import logging
import threading
import time
from types import SimpleNamespace

import pytest
from flask import Flask

from app.analytics.api import API_PREFIX, create_analytics_blueprint
from app.analytics.api_config import AnalyticsApiConfig
from app.analytics.models import (
    AnalyticsProvenance,
    AnalyticsQuality,
    AnalyticsResult,
    CoverageMetric,
)
from app.analytics.config import AnalyticsConfig
from app.analytics.visits import VisitAnalyticsService
from app.analytics.wireless import WirelessAnalyticsService


SITE = "0123456789abcdef01234567"
OTHER_SITE = "fedcba9876543210fedcba98"
TOKEN = "test-analytics-bearer-token-value-0001"
FROM = "2026-01-01T00:00:00.000Z"
TO = "2026-01-02T00:00:00.000Z"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def _result(status="ok", value=None, reason=None):
    return AnalyticsResult(
        status=status,
        value=CoverageMetric(1, 2, 0.5) if value is None else value,
        quality=AnalyticsQuality(
            "strict_complete", reason=reason, accepted_rows=1
        ),
        provenance=AnalyticsProvenance(
            site_id=SITE,
            from_utc=FROM,
            to_utc=TO,
            evaluation_at_utc=TO,
            computed_at_utc=TO,
            quality_mode="strict_complete",
            source_names=("observations",),
            source_schema_versions={"observations": 1},
            source_watermarks={"observations": None},
            source_rows_examined=2,
            source_rows_accepted=1,
            source_rows_rejected=1,
            sample_size=1,
            missing_count=0,
            partial_cycle_count=0,
            failed_cycle_count=0,
            abandoned_cycle_count=0,
            filters={},
            metric_version="test.v1",
            query_duration_ms=1.25,
        ),
    )


class ServiceSpy:
    def __init__(self, result=None, callback=None):
        self.result = result or _result()
        self.callback = callback
        self.calls = []

    def __getattr__(self, name):
        def invoke(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            if self.callback is not None:
                self.callback()
            return self.result
        return invoke


class Runtime:
    def __init__(self, *, state="active", result=None, maximum=1_048_576,
                 callback=None):
        self.state = state
        self.api_config = AnalyticsApiConfig(
            enabled=True,
            bearer_token=TOKEN,
            allowed_networks=(
                ipaddress.ip_network("127.0.0.1/32"),
                ipaddress.ip_network("::1/128"),
            ),
            allowed_site_ids=frozenset({SITE}),
            max_concurrent_requests=1,
            max_response_bytes=maximum,
        )
        self.quality_service = ServiceSpy(result, callback)
        self.wireless_service = ServiceSpy(result, callback)
        self.visit_service = ServiceSpy(result, callback)

    def health_payload(self):
        return {
            "state": self.state,
            "modules": {"quality": True, "wireless": True, "visits": True},
            "sources": {
                "observations": {
                    "available": self.state == "active",
                    "expected_schema_version": 1,
                    "actual_schema_version": 1,
                    "query_only": True,
                }
            },
        }


def _app(runtime=None, *, logger=None):
    selected = runtime or Runtime()
    app = Flask(__name__)
    app.register_blueprint(
        create_analytics_blueprint(
            selected, logger=logger or logging.getLogger("api-test")
        )
    )
    app.testing = True
    return app, selected


def _query(extra=""):
    suffix = f"&{extra}" if extra else ""
    return f"?site_id={SITE}&from_utc={FROM}&to_utc={TO}{suffix}"


@pytest.mark.parametrize(
    ("path", "service_name", "method", "extra"),
    [
        ("/quality/source", "quality_service", "get_source_quality", ""),
        ("/wireless/signal", "wireless_service", "get_signal_distribution", "metric=rssi"),
        ("/wireless/client-context", "wireless_service",
         "get_client_distribution", "dimension=ap_mac"),
        ("/wireless/concurrency", "wireless_service", "get_concurrent_client_distribution", ""),
        ("/wireless/ap-resource", "wireless_service",
         "get_ap_resource_distribution", "metric=cpu_util"),
        ("/wireless/radio-utilization", "wireless_service",
         "get_radio_utilization", "metric=busy_util"),
        ("/wireless/throughput", "wireless_service",
         "get_throughput_distribution", "metric=client_download_mbps"),
        ("/wireless/counter-quality", "wireless_service", "get_counter_quality", ""),
        ("/wireless/correlation", "wireless_service",
         "get_signal_ap_correlation", "signal_metric=rssi&ap_metric=busy_util"),
        ("/visits/counts", "visit_service", "get_visit_counts", ""),
        ("/visits/time-series", "visit_service", "get_visit_time_series", "granularity=day"),
        ("/visits/devices", "visit_service", "get_device_counts", ""),
        ("/visits/repeat-devices", "visit_service", "get_repeat_devices", ""),
        ("/visits/new-to-site", "visit_service", "get_new_to_site_devices", ""),
        ("/visits/duration", "visit_service", "get_duration_distribution", ""),
        ("/visits/authorizations", "visit_service", "get_authorization_distribution", ""),
        ("/visits/closure", "visit_service", "get_closure_distribution", ""),
        ("/visits/source-events", "visit_service", "get_source_event_quality", ""),
        ("/visits/contexts", "visit_service", "get_context_distributions", ""),
        ("/visits/transitions", "visit_service", "get_context_transition", ""),
        ("/visits/observation-coverage", "visit_service", "get_observation_coverage_summary", ""),
        ("/visits/traffic", "visit_service", "get_visit_traffic_summary", ""),
        ("/visits/return-intervals", "visit_service", "get_return_intervals", ""),
    ],
)
def test_endpoint_invokes_exactly_one_public_method(
    path, service_name, method, extra
):
    app, runtime = _app()
    response = app.test_client().get(
        API_PREFIX + path + _query(extra), headers=AUTH
    )
    assert response.status_code == 200
    selected = getattr(runtime, service_name)
    assert [call[0] for call in selected.calls] == [method]
    other_calls = sum(
        len(getattr(runtime, name).calls)
        for name in {"quality_service", "wireless_service", "visit_service"}
        if name != service_name
    )
    assert other_calls == 0
    body = response.get_json()
    assert body["api_version"] == "analytics.internal.v1"
    assert body["result"]["value"] == {
        "denominator": 2, "numerator": 1, "ratio": 0.5,
    }
    assert body["result"]["provenance"]["source_rows_rejected"] == 1


def test_common_values_are_passed_unchanged_and_evaluation_is_server_generated():
    app, runtime = _app()
    response = app.test_client().get(
        API_PREFIX + "/quality/source" + _query(), headers=AUTH
    )
    assert response.status_code == 200
    _, args, kwargs = runtime.quality_service.calls[0]
    assert args[:3] == (SITE, FROM, TO)
    assert kwargs == {}
    assert args[3].endswith("Z")


@pytest.mark.parametrize(
    "header",
    [None, "Basic value", "bearer " + TOKEN, "Bearer", "Bearer  " + TOKEN,
     "Bearer invalid"],
)
def test_missing_malformed_or_invalid_bearer_is_401(header):
    app, runtime = _app()
    headers = {} if header is None else {"Authorization": header}
    response = app.test_client().get(API_PREFIX + "/health", headers=headers)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert not runtime.quality_service.calls
    assert TOKEN.encode() not in response.data


def test_authentication_uses_constant_time_compare(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.analytics.api.hmac.compare_digest",
        lambda supplied, expected: calls.append((supplied, expected)) or True,
    )
    app, _ = _app()
    assert app.test_client().get(
        API_PREFIX + "/health", headers={"Authorization": "Bearer supplied"}
    ).status_code == 200
    assert calls == [("supplied", TOKEN)]


def test_query_string_token_is_rejected_even_with_valid_header():
    app, _ = _app()
    response = app.test_client().get(
        API_PREFIX + "/health?token=secret", headers=AUTH
    )
    assert response.status_code == 400
    assert b"secret" not in response.data


def test_credentials_are_absent_from_operational_logs(caplog):
    app, _ = _app()
    supplied = "credential-that-must-not-appear-anywhere"
    with caplog.at_level(logging.WARNING):
        response = app.test_client().get(
            API_PREFIX + "/health",
            headers={"Authorization": f"Bearer {supplied}"},
        )
    assert response.status_code == 401
    assert supplied not in caplog.text
    assert TOKEN not in caplog.text


def test_disallowed_source_ip_is_403_before_service_call():
    app, runtime = _app()
    response = app.test_client().get(
        API_PREFIX + "/quality/source" + _query(),
        headers=AUTH,
        environ_base={"REMOTE_ADDR": "192.0.2.10"},
    )
    assert response.status_code == 403
    assert not runtime.quality_service.calls


def test_disallowed_site_is_403_before_service_call():
    app, runtime = _app()
    query = f"?site_id={OTHER_SITE}&from_utc={FROM}&to_utc={TO}"
    response = app.test_client().get(
        API_PREFIX + "/quality/source" + query, headers=AUTH
    )
    assert response.status_code == 403
    assert not runtime.quality_service.calls


@pytest.mark.parametrize(
    "suffix",
    ["&unknown=1", "&site_id=" + SITE, "&client_mac=02:11:22:33:44:55"],
)
def test_unknown_duplicate_and_private_identifier_parameters_are_400(suffix):
    app, runtime = _app()
    response = app.test_client().get(
        API_PREFIX + "/quality/source" + _query() + suffix, headers=AUTH
    )
    assert response.status_code == 400
    assert not runtime.quality_service.calls


def test_non_get_is_405():
    app, _ = _app()
    response = app.test_client().post(
        API_PREFIX + "/quality/source" + _query(), headers=AUTH
    )
    assert response.status_code == 405


@pytest.mark.parametrize("method", ["post", "put"])
def test_routing_405_has_analytics_security_headers(method):
    app, _ = _app()
    response = getattr(app.test_client(), method)(
        API_PREFIX + "/quality/source" + _query(), headers=AUTH
    )
    assert response.status_code == 405
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.parametrize(
    ("status", "reason", "http"),
    [
        ("partial", None, 200),
        ("insufficient_data", None, 200),
        ("unavailable", "source_unavailable", 503),
        ("partial", "query_deadline", 503),
    ],
)
def test_analytics_status_mapping(status, reason, http):
    app, _ = _app(Runtime(result=_result(status=status, reason=reason)))
    response = app.test_client().get(
        API_PREFIX + "/quality/source" + _query(), headers=AUTH
    )
    assert response.status_code == http
    assert response.get_json()["result"]["status"] == status


def test_health_is_protected_cheap_and_safe():
    app, runtime = _app()
    response = app.test_client().get(API_PREFIX + "/health", headers=AUTH)
    assert response.status_code == 200
    assert not runtime.quality_service.calls
    text = response.get_data(as_text=True)
    assert "db_path" not in text
    assert "allowed_network" not in text
    assert TOKEN not in text


def test_health_uses_live_source_check_on_every_request_and_recovers():
    runtime = Runtime()
    states = iter((True, False, True))
    calls = []

    def live():
        healthy = next(states)
        calls.append(healthy)
        state = "active" if healthy else "unavailable"
        return healthy, {
            "state": state,
            "modules": {"quality": True, "wireless": True, "visits": True},
            "sources": {
                "observations": {
                    "available": healthy,
                    "expected_schema_version": 1,
                    "actual_schema_version": 1 if healthy else None,
                    "query_only": healthy,
                }
            },
        }

    runtime.live_health_payload = live
    app, _ = _app(runtime)
    client = app.test_client()
    assert client.get(API_PREFIX + "/health", headers=AUTH).status_code == 200
    assert client.get(API_PREFIX + "/health", headers=AUTH).status_code == 503
    assert client.get(API_PREFIX + "/health", headers=AUTH).status_code == 200
    assert calls == [True, False, True]


def test_health_rejects_query_parameters():
    app, _ = _app()
    response = app.test_client().get(
        API_PREFIX + "/health?unexpected=value", headers=AUTH
    )
    assert response.status_code == 400


def test_unavailable_runtime_health_and_metric_are_controlled_503():
    app, runtime = _app(Runtime(state="unavailable"))
    client = app.test_client()
    assert client.get(API_PREFIX + "/health", headers=AUTH).status_code == 503
    response = client.get(
        API_PREFIX + "/quality/source" + _query(), headers=AUTH
    )
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "analytics_unavailable"
    assert not runtime.quality_service.calls


@pytest.mark.parametrize(
    ("state", "category"),
    [("disabled", "runtime_disabled"), ("unavailable", "runtime_unavailable")],
)
def test_inactive_runtime_emits_exactly_one_safe_failure(
    state, category, caplog,
):
    logger = logging.getLogger(f"api-inactive-{state}")
    app, _ = _app(Runtime(state=state), logger=logger)
    with caplog.at_level(logging.INFO, logger=logger.name):
        response = app.test_client().get(
            API_PREFIX + "/quality/source" + _query(), headers=AUTH
        )
    assert response.status_code == 503
    records = [
        record.getMessage() for record in caplog.records
        if "analytics.api_request_" in record.getMessage()
    ]
    assert len(records) == 1
    assert "analytics.api_request_failed" in records[0]
    assert category in records[0]
    for forbidden in (TOKEN, "Authorization", "Cookie", "from_utc"):
        assert forbidden not in records[0]


def test_security_and_cache_headers_present_without_cors():
    app, _ = _app()
    response = app.test_client().get(API_PREFIX + "/health", headers=AUTH)
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "Access-Control-Allow-Origin" not in response.headers


@pytest.mark.parametrize("status", [400, 401, 403, 404, 405, 413, 429, 500, 503])
def test_security_headers_cover_framework_and_error_statuses(status):
    app, _ = _app()
    app.add_url_rule(
        API_PREFIX + f"/_test/status/{status}",
        endpoint=f"analytics_test_status_{status}",
        view_func=lambda selected=status: ("", selected),
        methods=["GET"],
    )
    response = app.test_client().get(
        API_PREFIX + f"/_test/status/{status}", headers=AUTH
    )
    assert response.status_code == status
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_response_overflow_returns_only_controlled_error():
    huge = "x" * 70_000
    app, _ = _app(Runtime(result=_result(value={"large": huge}), maximum=65_536))
    response = app.test_client().get(
        API_PREFIX + "/quality/source" + _query(), headers=AUTH
    )
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "response_too_large"
    assert huge.encode() not in response.data


def test_unknown_value_type_is_controlled_serialization_error():
    app, _ = _app(Runtime(result=_result(value=object())))
    response = app.test_client().get(
        API_PREFIX + "/quality/source" + _query(), headers=AUTH
    )
    assert response.status_code == 500
    assert response.get_json()["error"]["code"] == "serialization_error"
    assert b"object at" not in response.data


def test_concurrency_limit_is_non_blocking_and_slot_releases():
    entered = threading.Event()
    release = threading.Event()

    def blocked():
        entered.set()
        assert release.wait(3)

    runtime = Runtime(callback=blocked)
    app, runtime = _app(runtime)
    first_status = []

    def first_request():
        with app.test_client() as client:
            first_status.append(client.get(
                API_PREFIX + "/quality/source" + _query(), headers=AUTH
            ).status_code)

    thread = threading.Thread(target=first_request)
    thread.start()
    assert entered.wait(2)
    started = time.perf_counter()
    second = app.test_client().get(
        API_PREFIX + "/quality/source" + _query(), headers=AUTH
    )
    elapsed = time.perf_counter() - started
    assert second.status_code == 429
    assert second.headers["Retry-After"] == "1"
    assert elapsed < 0.5
    release.set()
    thread.join(3)
    assert first_status == [200]
    runtime.quality_service.callback = None
    assert app.test_client().get(
        API_PREFIX + "/quality/source" + _query(), headers=AUTH
    ).status_code == 200


def test_small_fixture_api_overhead_p95_is_below_100_ms():
    app, _ = _app()
    client = app.test_client()
    durations = []
    for _ in range(60):
        started = time.perf_counter()
        response = client.get(
            API_PREFIX + "/quality/source" + _query(), headers=AUTH
        )
        durations.append((time.perf_counter() - started) * 1000)
        assert response.status_code == 200
    durations.sort()
    p95 = durations[int(len(durations) * 0.95) - 1]
    assert p95 < 100


def test_real_services_are_aggregate_only_and_leave_sources_unchanged(
    analytics_stack,
):
    config = AnalyticsConfig(
        enabled=True,
        wireless_enabled=True,
        wireless_min_samples=1,
        visit_enabled=True,
        visit_min_cohort_size=1,
    )
    api_config = AnalyticsApiConfig(
        enabled=True,
        bearer_token=TOKEN,
        allowed_networks=(ipaddress.ip_network("127.0.0.1/32"),),
        allowed_site_ids=frozenset({"site-a"}),
        max_concurrent_requests=2,
        max_response_bytes=1_048_576,
    )
    runtime = SimpleNamespace(
        state="active",
        api_config=api_config,
        quality_service=analytics_stack.service,
        wireless_service=WirelessAnalyticsService(config, analytics_stack.gateway),
        visit_service=VisitAnalyticsService(config, analytics_stack.gateway),
    )
    runtime.health_payload = lambda: {"state": "active"}
    app = Flask(__name__)
    app.register_blueprint(
        create_analytics_blueprint(runtime, logger=logging.getLogger("real-api"))
    )
    client = app.test_client()
    common = (
        "?site_id=site-a&from_utc=2026-01-01T09:59:00.000Z"
        "&to_utc=2026-01-01T11:00:00.000Z"
    )

    def source_state(repository):
        with repository.read_connection() as connection:
            schema = tuple(connection.execute(
                "SELECT type,name,sql FROM sqlite_schema ORDER BY type,name"
            ))
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            changes = connection.total_changes
        return version, schema, changes

    before = tuple(source_state(repository) for repository in (
        analytics_stack.observations,
        analytics_stack.visits,
        analytics_stack.registry,
    ))
    paths = (
        "/quality/source" + common,
        "/wireless/signal" + common + "&metric=rssi",
        "/visits/counts" + common,
    )
    responses = [client.get(API_PREFIX + path, headers=AUTH) for path in paths]
    assert [response.status_code for response in responses] == [200, 200, 200]
    after = tuple(source_state(repository) for repository in (
        analytics_stack.observations,
        analytics_stack.visits,
        analytics_stack.registry,
    ))
    assert after == before
    output = "".join(response.get_data(as_text=True) for response in responses)
    assert "02:11:22:33:44:55" not in output
    assert "192.0.2.10" not in output
