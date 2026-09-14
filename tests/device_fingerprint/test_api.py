import json
import http.client
import ipaddress
import logging
import threading

import pytest

from app.device_fingerprint.api import (
    API_PREFIX, API_VERSION, DeviceFingerprintSafeRequestHandler,
    create_device_fingerprint_app,
)
from app.device_fingerprint.models import (
    DeviceFingerprintProducer, DeviceFingerprintStorageUnavailable,
    DeviceFingerprintValidationError,
)
from app.device_fingerprint.repository import DeviceFingerprintRepository
from app.device_fingerprint.schema_registry import EvidenceSchemaRegistry
from app.device_fingerprint.service import DeviceFingerprintRuntime
from app.device_fingerprint.telemetry import DeviceFingerprintTelemetry
from tests.device_fingerprint import Identity, NOW, SITE, TOKEN, config, evidence_event, health_event, logger, producer


ERROR_MESSAGES = {
    "query_token_forbidden": "Authentication credentials are not accepted in the query string.",
    "invalid_request": "The request is invalid.",
    "unsupported_schema": "The evidence schema is not supported.",
    "invalid_credential": "Authentication is required.",
    "source_network_forbidden": "The source network is not allowed.",
    "producer_forbidden": "The producer is not allowed.",
    "site_forbidden": "The Site is not allowed.",
    "capture_source_forbidden": "The capture source is not allowed.",
    "source_kind_forbidden": "The source kind is not allowed.",
    "not_found": "The requested fingerprint endpoint does not exist.",
    "method_not_allowed": "The method is not allowed for this endpoint.",
    "idempotency_conflict": "The request conflicts with an existing immutable event.",
    "request_too_large": "The request exceeds the allowed size.",
    "concurrency_limit": "Too many fingerprint requests are in progress.",
    "internal_error": "The fingerprint request failed.",
    "runtime_unavailable": "The fingerprint service is temporarily unavailable.",
    "repository_unavailable": "The fingerprint repository is temporarily unavailable.",
    "storage_limit": "The fingerprint repository storage limit was reached.",
    "storage_corrupt": "The fingerprint repository is unavailable.",
}


def application(tmp_path, *, validator=None, **config_overrides):
    cfg = config(tmp_path, **config_overrides)
    repo = DeviceFingerprintRepository(cfg.db_path, max_db_bytes=cfg.max_db_bytes)
    registry = EvidenceSchemaRegistry()
    if validator is None:
        def validator(value):
            if set(value) != {"vendor_class"}:
                raise DeviceFingerprintValidationError("Invalid DHCP evidence")
            return dict(value)
    registry.register("dhcp", 1, validator)
    registry.freeze()
    telemetry = DeviceFingerprintTelemetry(logger(), runtime_fields=Identity().safe_fields())
    runtime = DeviceFingerprintRuntime(cfg, repo, registry, artifact_identity=Identity(), telemetry=telemetry, now=lambda: NOW)
    runtime.initialize(); runtime.mark_ready()
    return create_device_fingerprint_app(runtime, logger=logger()), runtime


def headers(token=TOKEN):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def assert_error(response, status, code):
    assert response.status_code == status
    assert response.json == {"api_version": API_VERSION, "request_id": response.json["request_id"], "error": {"code": code, "message": ERROR_MESSAGES[code]}}
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_query_secret_precedes_auth_and_proxy_headers_are_ignored(tmp_path):
    app, _runtime = application(tmp_path)
    client = app.test_client()
    assert_error(client.get(API_PREFIX + "/health?ToKeN=x"), 400, "query_token_forbidden")
    assert_error(client.get(API_PREFIX + "/health", environ_base={"REMOTE_ADDR": "10.0.0.1"}, headers={**headers(), "X-Forwarded-For": "127.0.0.1", "Forwarded": "for=127.0.0.1", "X-Real-IP": "127.0.0.1"}), 403, "source_network_forbidden")


@pytest.mark.parametrize("key", ["token", "TOKEN", "access_token", "Access_Token", "bearer_token", "BEARER_TOKEN"])
def test_every_query_credential_key_is_rejected_case_insensitively_before_auth(tmp_path, key):
    app, _runtime = application(tmp_path)
    assert_error(app.test_client().get(API_PREFIX + f"/health?{key}=secret"), 400, "query_token_forbidden")


@pytest.mark.parametrize("authorization", [None, "bearer " + TOKEN, "Bearer  short", "Bearer " + TOKEN + " "])
def test_bearer_is_exact(tmp_path, authorization):
    app, _runtime = application(tmp_path)
    headers_value = {} if authorization is None else {"Authorization": authorization}
    response = app.test_client().get(API_PREFIX + "/health", headers=headers_value)
    assert_error(response, 401, "invalid_credential")
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("method,path", [("post", "/health"), ("get", "/evidence/batch"), ("get", "/source-health/batch"), ("options", "/evidence/batch")])
def test_exact_namespace_methods_are_json_405(tmp_path, method, path):
    app, _runtime = application(tmp_path)
    response = getattr(app.test_client(), method)(API_PREFIX + path, headers=headers())
    assert_error(response, 405, "method_not_allowed")
    assert b"<!doctype" not in response.data.lower()


def test_head_is_explicitly_unsupported(tmp_path):
    app, _runtime = application(tmp_path)
    response = app.test_client().head(API_PREFIX + "/health", headers=headers())
    assert response.status_code == 405
    assert response.headers["Cache-Control"] == "no-store"


def test_unknown_namespace_path_is_protected_json_404(tmp_path):
    app, _runtime = application(tmp_path)
    client = app.test_client()
    assert_error(client.get(API_PREFIX + "/unknown"), 401, "invalid_credential")
    assert_error(client.get(API_PREFIX + "/unknown", headers=headers()), 404, "not_found")


def test_dedicated_app_has_exact_namespace_and_no_static_surface(tmp_path):
    app, _runtime = application(tmp_path)
    assert app.name == "device_fingerprint_internal_v1"
    assert app.static_folder is None
    rules = {rule.rule: sorted(rule.methods - {"HEAD", "OPTIONS"}) for rule in app.url_map.iter_rules()}
    assert rules == {
        API_PREFIX + "/evidence/batch": ["POST"],
        API_PREFIX + "/source-health/batch": ["POST"],
        API_PREFIX + "/health": ["GET"],
    }


def test_evidence_and_source_health_success_shapes(tmp_path):
    app, _runtime = application(tmp_path)
    client = app.test_client()
    response = client.post(API_PREFIX + "/evidence/batch", headers=headers(), json={"producer_id": producer().producer_id, "events": [evidence_event()]})
    assert response.status_code == 200
    assert response.json["result"] == {"status": "ok", "received": 1, "inserted": 1, "duplicate_noop": 0}
    response = client.post(API_PREFIX + "/source-health/batch", headers=headers(), json={"producer_id": producer().producer_id, "events": [health_event()]})
    assert response.status_code == 200 and response.json["result"]["inserted"] == 1


def test_authorization_and_schema_fail_closed(tmp_path):
    app, _runtime = application(tmp_path)
    client = app.test_client()
    body = {"producer_id": "another", "events": [evidence_event()]}
    assert_error(client.post(API_PREFIX + "/evidence/batch", headers=headers(), json=body), 403, "producer_forbidden")
    for field, value, code in (("site_id", "0" * 24, "site_forbidden"), ("capture_source_id", "other", "capture_source_forbidden"), ("source_kind", "tcp_syn", "source_kind_forbidden")):
        body = {"producer_id": producer().producer_id, "events": [evidence_event(**{field: value})]}
        if field == "source_kind":
            # tcp_syn is producer-authorized but deliberately unregistered.
            code = "unsupported_schema"
            status = 400
        else:
            status = 403
        assert_error(client.post(API_PREFIX + "/evidence/batch", headers=headers(), json=body), status, code)
    body = {"producer_id": producer().producer_id, "events": [evidence_event(source_kind="quic_client")]}
    assert_error(client.post(API_PREFIX + "/evidence/batch", headers=headers(), json=body), 403, "source_kind_forbidden")


@pytest.mark.parametrize("path,event_factory", [
    ("/evidence/batch", evidence_event),
    ("/source-health/batch", health_event),
])
@pytest.mark.parametrize("location,value,status,code", [
    ("producer_id", "BAD VALUE", 400, "invalid_request"),
    ("producer_id", "other-producer", 403, "producer_forbidden"),
    ("site_id", "not-a-site", 400, "invalid_request"),
    ("site_id", "0" * 24, 403, "site_forbidden"),
    ("capture_source_id", "BAD VALUE", 400, "invalid_request"),
    ("capture_source_id", "other-source", 403, "capture_source_forbidden"),
    ("source_kind", "BAD VALUE", 400, "invalid_request"),
    ("source_kind", "quic_client", 403, "source_kind_forbidden"),
])
def test_canonical_validation_precedes_authorization(
    tmp_path, path, event_factory, location, value, status, code
):
    app, _runtime = application(tmp_path)
    body = {"producer_id": producer().producer_id, "events": [event_factory()]}
    if location == "producer_id":
        body[location] = value
    else:
        body["events"][0][location] = value
    assert_error(app.test_client().post(API_PREFIX + path, headers=headers(), json=body), status, code)


def test_ipaddress_canonicalization_is_used_for_durable_retry_identity(tmp_path):
    configured = producer()
    configured = DeviceFingerprintProducer(
        configured.producer_id, configured.bearer_token,
        configured.capture_source_id, configured.site_id,
        configured.allowed_guest_cidrs + (ipaddress.ip_network("2001:db8::/32"),),
        configured.allowed_source_kinds,
    )
    app, runtime = application(tmp_path, producers=(configured,))
    body = {"producer_id": configured.producer_id, "events": [evidence_event(
        observed_ip="2001:0db8:0000:0000:0000:0000:0000:0001"
    )]}
    first = app.test_client().post(API_PREFIX + "/evidence/batch", headers=headers(), json=body)
    assert first.json["result"]["inserted"] == 1
    body["events"][0]["observed_ip"] = "2001:db8::1"
    retry = app.test_client().post(API_PREFIX + "/evidence/batch", headers=headers(), json=body)
    assert retry.json["result"]["duplicate_noop"] == 1
    stored = runtime.repository.connection.execute(
        "SELECT observed_ip FROM device_fingerprint_evidence"
    ).fetchone()[0]
    assert stored == "2001:db8::1"


def test_health_exact_shape_and_runtime_status(tmp_path):
    app, runtime = application(tmp_path)
    response = app.test_client().get(API_PREFIX + "/health", headers=headers())
    assert response.status_code == 200
    assert {name: response.headers[name] for name in (
        "Cache-Control", "Pragma", "X-Content-Type-Options"
    )} == {
        "Cache-Control": "no-store", "Pragma": "no-cache",
        "X-Content-Type-Options": "nosniff",
    }
    assert set(response.json["result"]) == {"status", "reason", "artifact_identity", "schema_version", "evidence_retention_days", "source_health_retention_days", "last_successful_retention_at"}
    runtime.transition_stopping()
    assert app.test_client().get(API_PREFIX + "/health", headers=headers()).status_code == 503


@pytest.mark.parametrize("state,reason,status", [
    ("initializing", None, 503),
    ("ready", None, 200),
    ("degraded", "retention_failed", 200),
    ("unavailable", "storage_limit", 503),
    ("stopping", "stopping", 503),
])
def test_health_http_status_matches_runtime_state(tmp_path, state, reason, status):
    app, runtime = application(tmp_path)
    with runtime.condition:
        runtime.state, runtime.reason = state, reason
    response = app.test_client().get(API_PREFIX + "/health", headers=headers())
    assert response.status_code == status
    assert response.json["result"]["status"] == state


def test_batch_query_content_type_count_and_payload_bounds(tmp_path):
    app, _runtime = application(tmp_path, max_events_per_batch=1, max_payload_bytes=256)
    client = app.test_client()
    path = API_PREFIX + "/evidence/batch"
    assert_error(client.post(path + "?unexpected=1", headers=headers(), json={"producer_id": producer().producer_id, "events": [evidence_event()]}), 400, "invalid_request")
    assert_error(client.post(path, headers={"Authorization": f"Bearer {TOKEN}"}, data="{}"), 400, "invalid_request")
    assert_error(client.post(path, headers=headers(), json={"producer_id": producer().producer_id, "events": []}), 400, "invalid_request")
    events = [evidence_event(), evidence_event(source_event_id="77777777-7777-4777-8777-777777777777")]
    assert_error(client.post(path, headers=headers(), json={"producer_id": producer().producer_id, "events": events}), 413, "request_too_large")
    large = evidence_event(payload={"vendor_class": "x" * 300})
    assert_error(client.post(path, headers=headers(), json={"producer_id": producer().producer_id, "events": [large]}), 413, "request_too_large")


@pytest.mark.parametrize("content_type,accepted", [
    ("application/json", True),
    ("application/json; charset=utf-8", True),
    ("application/vnd.example+json", False),
    ("text/json", False),
    ("text/plain", False),
    (None, False),
])
def test_post_requires_exact_application_json_mime(tmp_path, content_type, accepted):
    app, _runtime = application(tmp_path)
    request_headers = {"Authorization": f"Bearer {TOKEN}"}
    if content_type is not None:
        request_headers["Content-Type"] = content_type
    response = app.test_client().post(
        API_PREFIX + "/evidence/batch", headers=request_headers,
        data=json.dumps({"producer_id": producer().producer_id, "events": [evidence_event()]}),
    )
    if accepted:
        assert response.status_code == 200
    else:
        assert_error(response, 400, "invalid_request")


def test_idempotency_conflict_is_exact_and_does_not_echo_data(tmp_path):
    app, _runtime = application(tmp_path)
    client = app.test_client(); path = API_PREFIX + "/evidence/batch"
    body = {"producer_id": producer().producer_id, "events": [evidence_event()]}
    assert client.post(path, headers=headers(), json=body).status_code == 200
    body["events"][0]["payload"] = {"vendor_class": "conflict-secret"}
    response = client.post(path, headers=headers(), json=body)
    assert_error(response, 409, "idempotency_conflict")
    assert b"conflict-secret" not in response.data and TOKEN.encode() not in response.data


def test_duplicate_ids_and_wrong_guest_ip_fail_without_write(tmp_path):
    app, runtime = application(tmp_path)
    path = API_PREFIX + "/evidence/batch"; client = app.test_client(); item = evidence_event()
    assert_error(client.post(path, headers=headers(), json={"producer_id": producer().producer_id, "events": [item, item]}), 400, "invalid_request")
    outside = evidence_event(observed_ip="10.0.0.1")
    assert_error(client.post(path, headers=headers(), json={"producer_id": producer().producer_id, "events": [outside]}), 400, "invalid_request")
    assert runtime.repository.connection.execute("SELECT COUNT(*) FROM device_fingerprint_evidence").fetchone()[0] == 0


@pytest.mark.parametrize("reason,code", [("storage_limit", "storage_limit"), ("storage_corrupt", "storage_corrupt"), ("repository", "repository_unavailable")])
def test_repository_failures_have_typed_503(tmp_path, monkeypatch, reason, code):
    from app.device_fingerprint.models import DeviceFingerprintStorageCorrupt, DeviceFingerprintStorageLimit, DeviceFingerprintStorageUnavailable
    app, runtime = application(tmp_path)
    errors = {"storage_limit": DeviceFingerprintStorageLimit(), "storage_corrupt": DeviceFingerprintStorageCorrupt(), "repository": DeviceFingerprintStorageUnavailable()}
    monkeypatch.setattr(runtime.service, "evidence_batch", lambda *_a, **_k: (_ for _ in ()).throw(errors[reason]))
    response = app.test_client().post(API_PREFIX + "/evidence/batch", headers=headers(), json={"producer_id": producer().producer_id, "events": [evidence_event()]})
    assert_error(response, 503, code)


def test_concurrency_guard_is_immediate_and_health_uses_no_slot(tmp_path, monkeypatch):
    import app.device_fingerprint.api as module
    class Slot:
        def acquire(self, blocking=False): return False
        def release(self): raise AssertionError("unacquired slot released")
    monkeypatch.setattr(module.threading, "BoundedSemaphore", lambda _count: Slot())
    app, _runtime = application(tmp_path)
    client = app.test_client()
    response = client.post(API_PREFIX + "/evidence/batch", headers=headers(), json={"producer_id": producer().producer_id, "events": [evidence_event()]})
    assert_error(response, 429, "concurrency_limit")
    assert response.headers["Retry-After"] == "1"
    assert client.get(API_PREFIX + "/health", headers=headers()).status_code == 200


def test_unexpected_service_failure_is_sanitized_500(tmp_path, monkeypatch):
    app, runtime = application(tmp_path)
    monkeypatch.setattr(runtime.service, "evidence_batch", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("sensitive detail")))
    response = app.test_client().post(API_PREFIX + "/evidence/batch", headers=headers(), json={"producer_id": producer().producer_id, "events": [evidence_event()]})
    assert_error(response, 500, "internal_error")
    assert b"sensitive" not in response.data
    assert runtime.active_ingest_count == 0


def test_schema_validator_programming_failure_stays_sanitized_internal_error(tmp_path, caplog):
    sensitive = "SENSITIVE_VALIDATOR_FAILURE"

    def broken_validator(_payload):
        raise RuntimeError(sensitive)

    app, _runtime = application(tmp_path, validator=broken_validator)
    with caplog.at_level(logging.INFO, logger="device-fingerprint-test"):
        response = app.test_client().post(
            API_PREFIX + "/evidence/batch", headers=headers(),
            json={"producer_id": producer().producer_id, "events": [evidence_event()]},
        )
    assert_error(response, 500, "internal_error")
    assert response.json["error"]["message"] == "The fingerprint request failed."
    assert sensitive.encode() not in response.data
    assert sensitive not in caplog.text


def test_schema_validator_owned_validation_failure_remains_invalid_request(tmp_path):
    def rejecting_validator(_payload):
        raise DeviceFingerprintValidationError("expected validator rejection")

    app, _runtime = application(tmp_path, validator=rejecting_validator)
    response = app.test_client().post(
        API_PREFIX + "/evidence/batch", headers=headers(),
        json={"producer_id": producer().producer_id, "events": [evidence_event()]},
    )
    assert_error(response, 400, "invalid_request")


def test_sqlite_constraint_programming_failure_is_sanitized_internal_error(tmp_path, monkeypatch):
    import sqlite3
    error = sqlite3.IntegrityError("sensitive constraint detail")
    error.sqlite_errorcode = 19
    mapped = DeviceFingerprintRepository._sqlite_error(error)
    assert not isinstance(mapped, DeviceFingerprintStorageUnavailable)
    app, runtime = application(tmp_path)
    monkeypatch.setattr(runtime.service, "evidence_batch", lambda *_args: (_ for _ in ()).throw(mapped))
    response = app.test_client().post(
        API_PREFIX + "/evidence/batch", headers=headers(),
        json={"producer_id": producer().producer_id, "events": [evidence_event()]},
    )
    assert_error(response, 500, "internal_error")
    assert b"constraint" not in response.data


def test_unexpected_app_failure_emits_only_sanitized_telemetry(tmp_path, monkeypatch):
    app, runtime = application(tmp_path)
    emitted = []
    monkeypatch.setattr(runtime.telemetry, "emit", lambda event, **fields: emitted.append((event, fields)))
    monkeypatch.setattr(
        runtime, "health_payload",
        lambda: (_ for _ in ()).throw(RuntimeError("Bearer secret MAC AA:BB IP 192.0.2.1")),
    )
    response = app.test_client().get(API_PREFIX + "/health", headers=headers())
    assert_error(response, 500, "internal_error")
    assert emitted == [("device_fingerprint_product_health", {
        "request_id": response.json["request_id"], "runtime_state": "unavailable",
        "http_status": 500, "error_category": "internal_error",
    })]
    serialized = json.dumps(emitted)
    assert "Bearer" not in serialized and "AA:BB" not in serialized and "192.0.2.1" not in serialized


def test_authentication_compares_candidate_against_every_configured_secret(tmp_path, monkeypatch):
    import app.device_fingerprint.api as module
    first = producer()
    producers = (
        first,
        DeviceFingerprintProducer("sensor-two", "B" * 32, "span-two", SITE,
                                  first.allowed_guest_cidrs, first.allowed_source_kinds),
        DeviceFingerprintProducer("sensor-three", "C" * 32, "span-three", SITE,
                                  first.allowed_guest_cidrs, first.allowed_source_kinds),
    )
    calls = []
    real_compare = module.hmac.compare_digest
    monkeypatch.setattr(module.hmac, "compare_digest", lambda left, right: (calls.append((left, right)), real_compare(left, right))[1])
    app, _runtime = application(tmp_path, producers=producers)
    assert app.test_client().get(API_PREFIX + "/health", headers=headers()).status_code == 200
    assert [right for _left, right in calls] == [item.bearer_token for item in producers]


def test_actual_request_handler_strips_every_query_including_encoded_prefix(tmp_path):
    from werkzeug.serving import make_server
    app, _runtime = application(tmp_path)
    logged = []

    class AccessLogHandler(logging.Handler):
        def emit(self, record):
            logged.append(record.getMessage())

    access_logger = logging.getLogger("werkzeug")
    access_handler = AccessLogHandler()
    previous_level = access_logger.level
    access_logger.setLevel(logging.INFO)
    access_logger.addHandler(access_handler)
    server = make_server("127.0.0.1", 0, app, request_handler=DeviceFingerprintSafeRequestHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        requests = (
            ("/anything?token=plain-secret", {}),
            ("/%61pi/internal/device-fingerprint/v1/health?access_token=encoded-secret", {}),
            (API_PREFIX + "/health?ordinary=value", headers()),
        )
        statuses = []
        for target, request_headers in requests:
            connection = http.client.HTTPConnection(
                "127.0.0.1", server.server_port, timeout=2
            )
            connection.request("GET", target, headers=request_headers)
            response = connection.getresponse()
            statuses.append(response.status)
            response.read()
            connection.close()
    finally:
        server.shutdown()
        thread.join(2)
        server.server_close()
        access_logger.removeHandler(access_handler)
        access_logger.setLevel(previous_level)
    assert statuses == [404, 400, 400]
    assert len(logged) == 3
    assert all("?" not in line for line in logged)
    combined = "\n".join(logged)
    assert "plain-secret" not in combined
    assert "encoded-secret" not in combined
    assert "ordinary=value" not in combined
    assert any("GET /anything HTTP/1.1" in line and " 404 " in line for line in logged)
    assert any(
        f"GET {API_PREFIX}/health HTTP/1.1" in line and " 400 " in line
        for line in logged
    )


def test_source_health_has_exact_seven_keys_and_no_identity_fields(tmp_path):
    app, runtime = application(tmp_path); item = health_event(); item["observed_mac"] = "AA:BB:CC:DD:EE:FF"
    response = app.test_client().post(API_PREFIX + "/source-health/batch", headers=headers(), json={"producer_id": producer().producer_id, "events": [item]})
    assert_error(response, 400, "invalid_request")
    assert runtime.repository.connection.execute("SELECT COUNT(*) FROM device_fingerprint_source_health_events").fetchone()[0] == 0


def test_invalid_body_and_bearer_are_absent_from_response_and_operational_logs(tmp_path, caplog):
    app, _runtime = application(tmp_path)
    marker = "raw-body-sensitive-marker"
    body = {"producer_id": producer().producer_id, "events": [
        {**evidence_event(), "forbidden_extra": marker}
    ]}
    with caplog.at_level(logging.INFO, logger="device-fingerprint-test"):
        response = app.test_client().post(
            API_PREFIX + "/evidence/batch", headers=headers(), json=body
        )
    assert_error(response, 400, "invalid_request")
    assert marker.encode() not in response.data
    assert marker not in caplog.text
    assert TOKEN not in caplog.text


def test_http_body_limit_and_health_query_contract(tmp_path):
    app, _runtime = application(tmp_path, max_http_request_bytes=65_536)
    client = app.test_client()
    response = client.post(API_PREFIX + "/evidence/batch", headers=headers(), data=json.dumps({"padding": "x" * 70_000}))
    assert_error(response, 413, "request_too_large")
    assert_error(client.get(API_PREFIX + "/health?detail=1", headers=headers()), 400, "invalid_request")


def test_runtime_unavailable_prevents_repository_mutation(tmp_path):
    app, runtime = application(tmp_path); runtime.transition_stopping()
    response = app.test_client().post(API_PREFIX + "/evidence/batch", headers=headers(), json={"producer_id": producer().producer_id, "events": [evidence_event()]})
    assert_error(response, 503, "runtime_unavailable")
    assert runtime.repository.connection.execute("SELECT COUNT(*) FROM device_fingerprint_evidence").fetchone()[0] == 0


def test_rejected_after_semaphore_releases_slot_for_later_registered_request(tmp_path, monkeypatch):
    app, runtime = application(tmp_path)
    real_begin = runtime.begin_ingest
    decisions = iter((False, True))
    monkeypatch.setattr(runtime, "begin_ingest", lambda: next(decisions) and real_begin())
    body = {"producer_id": producer().producer_id, "events": [evidence_event()]}
    first = app.test_client().post(API_PREFIX + "/evidence/batch", headers=headers(), json=body)
    assert_error(first, 503, "runtime_unavailable")
    second = app.test_client().post(API_PREFIX + "/evidence/batch", headers=headers(), json=body)
    assert second.status_code == 200
    assert runtime.active_ingest_count == 0
