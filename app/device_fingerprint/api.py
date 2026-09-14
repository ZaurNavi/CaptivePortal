"""Dedicated protected TLS HTTP application for fingerprint evidence v1."""

from __future__ import annotations

import hmac
import json
import re
import threading
import time
import uuid
from typing import Any

from flask import Flask, Response, g, request
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge
from werkzeug.serving import WSGIRequestHandler

from .config import MAX_HTTP_RESPONSE_BYTES
from .models import (
    DeviceFingerprintConflict,
    DeviceFingerprintStorageCorrupt,
    DeviceFingerprintStorageLimit,
    DeviceFingerprintStorageUnavailable,
    DeviceFingerprintUnsupportedSchema,
    DeviceFingerprintValidationError,
)

API_VERSION = "device-fingerprint.internal.v1"
API_PREFIX = "/api/internal/device-fingerprint/v1"
_TOKEN = re.compile(r"[A-Za-z0-9_-]{32,256}")
_ERRORS = {
    "query_token_forbidden": (400, "Authentication credentials are not accepted in the query string."),
    "invalid_request": (400, "The request is invalid."),
    "unsupported_schema": (400, "The evidence schema is not supported."),
    "invalid_credential": (401, "Authentication is required."),
    "source_network_forbidden": (403, "The source network is not allowed."),
    "producer_forbidden": (403, "The producer is not allowed."),
    "site_forbidden": (403, "The Site is not allowed."),
    "capture_source_forbidden": (403, "The capture source is not allowed."),
    "source_kind_forbidden": (403, "The source kind is not allowed."),
    "not_found": (404, "The requested fingerprint endpoint does not exist."),
    "method_not_allowed": (405, "The method is not allowed for this endpoint."),
    "idempotency_conflict": (409, "The request conflicts with an existing immutable event."),
    "request_too_large": (413, "The request exceeds the allowed size."),
    "concurrency_limit": (429, "Too many fingerprint requests are in progress."),
    "internal_error": (500, "The fingerprint request failed."),
    "runtime_unavailable": (503, "The fingerprint service is temporarily unavailable."),
    "repository_unavailable": (503, "The fingerprint repository is temporarily unavailable."),
    "storage_limit": (503, "The fingerprint repository storage limit was reached."),
    "storage_corrupt": (503, "The fingerprint repository is unavailable."),
}
_METHODS = {
    API_PREFIX + "/evidence/batch": "POST",
    API_PREFIX + "/source-health/batch": "POST",
    API_PREFIX + "/health": "GET",
}


class DeviceFingerprintSafeRequestHandler(WSGIRequestHandler):
    """Werkzeug logger that never writes the fingerprint query string."""

    def log_request(self, code: int | str = "-", size: int | str = "-") -> None:
        original_requestline = self.requestline
        has_path = hasattr(self, "path")
        original_path = self.path if has_path else None
        try:
            parts = original_requestline.split(" ")
            if len(parts) >= 2:
                parts[1] = parts[1].split("?", 1)[0]
                self.requestline = " ".join(parts)
            if has_path and isinstance(original_path, str):
                self.path = original_path.split("?", 1)[0]
            super().log_request(code, size)
        finally:
            self.requestline = original_requestline
            if has_path:
                self.path = original_path


def create_device_fingerprint_app(runtime: Any, *, logger: Any) -> Flask:
    app = Flask("device_fingerprint_internal_v1", static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = runtime.config.max_http_request_bytes
    slots = threading.BoundedSemaphore(runtime.config.max_concurrent_ingest_requests)

    @app.before_request
    def protect() -> Response | None:
        if not request.path.startswith(API_PREFIX):
            return None
        g.device_fingerprint_request_id = str(uuid.uuid4())
        g.device_fingerprint_started = time.monotonic()
        if any(key.lower() in {"token", "access_token", "bearer_token"} for key in request.args.keys()):
            return _error("query_token_forbidden")
        producer = _authenticate(request.headers.get("Authorization"), runtime.config.producers)
        if producer is None:
            response = _error("invalid_credential")
            response.headers["WWW-Authenticate"] = "Bearer"
            return response
        g.device_fingerprint_producer = producer
        try:
            peer = __import__("ipaddress").ip_address(request.remote_addr or "")
        except ValueError:
            return _error("source_network_forbidden")
        if not any(peer in network for network in runtime.config.allowed_networks):
            return _error("source_network_forbidden")
        expected = _METHODS.get(request.path)
        if expected is not None and request.method != expected:
            return _error("method_not_allowed")
        return None

    @app.after_request
    def headers(response: Response) -> Response:
        if request.path.startswith(API_PREFIX):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
            response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.post(API_PREFIX + "/evidence/batch")
    def evidence_batch() -> Response:
        return _ingest(runtime, slots, "evidence", logger)

    @app.post(API_PREFIX + "/source-health/batch")
    def source_health_batch() -> Response:
        return _ingest(runtime, slots, "source_health", logger)

    @app.get(API_PREFIX + "/health")
    def health() -> Response:
        if request.args:
            return _error("invalid_request")
        payload = runtime.health_payload()
        runtime.telemetry.emit(
            "device_fingerprint_product_health",
            request_id=g.device_fingerprint_request_id,
            runtime_state=payload["status"],
            reason=payload["reason"],
            schema_version=payload["schema_version"],
        )
        return _success(payload, 200 if payload["status"] in {"ready", "degraded"} else 503)

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(_error_value: Any) -> Response:
        return _error("request_too_large") if request.path.startswith(API_PREFIX) else Response(status=413)

    @app.errorhandler(404)
    def not_found(_error_value: Any) -> Response:
        return _error("not_found") if request.path.startswith(API_PREFIX) else Response(status=404)

    @app.errorhandler(405)
    def method_not_allowed(_error_value: Any) -> Response:
        return _error("method_not_allowed") if request.path.startswith(API_PREFIX) else Response(status=405)

    @app.errorhandler(Exception)
    def unexpected(_error_value: Exception) -> Response:
        if request.path.startswith(API_PREFIX):
            runtime.telemetry.emit(
                "device_fingerprint_product_health",
                request_id=_request_id(),
                runtime_state="unavailable",
                http_status=500,
                error_category="internal_error",
            )
            return _error("internal_error")
        return Response(status=500)

    return app


def _ingest(runtime: Any, slots: threading.BoundedSemaphore, operation: str, logger: Any) -> Response:
    if not slots.acquire(blocking=False):
        response = _error("concurrency_limit")
        response.headers["Retry-After"] = "1"
        runtime.telemetry.emit("device_fingerprint_ingest_rejected", request_id=g.device_fingerprint_request_id, http_status=429, error_category="concurrency_limit")
        return response
    registered = False
    try:
        if not runtime.begin_ingest():
            _rejected(runtime, operation, "runtime_unavailable", 503)
            return _error("runtime_unavailable")
        registered = True
        if request.args:
            raise DeviceFingerprintValidationError("Query parameters are invalid")
        if request.mimetype != "application/json":
            raise DeviceFingerprintValidationError("JSON content type required")
        try:
            body = request.get_json(silent=False)
        except BadRequest as exc:
            raise DeviceFingerprintValidationError("Invalid JSON") from exc
        producer = g.device_fingerprint_producer
        if runtime.service is None:
            raise RuntimeError("Fingerprint service is not composed")
        result = (runtime.service.evidence_batch(producer, body) if operation == "evidence"
                  else runtime.service.source_health_batch(producer, body))
        event = "device_fingerprint_ingest_completed" if operation == "evidence" else "device_fingerprint_source_health_completed"
        runtime.telemetry.emit(event, request_id=g.device_fingerprint_request_id, producer_id=producer.producer_id, received=result.received, inserted=result.inserted, duplicate_noop=result.duplicate_noop, http_status=200)
        if result.duplicate_noop:
            runtime.telemetry.emit("device_fingerprint_ingest_duplicate", producer_id=producer.producer_id, duplicate_noop=result.duplicate_noop)
        return _success({"status": "ok", "received": result.received, "inserted": result.inserted, "duplicate_noop": result.duplicate_noop}, 200)
    except PermissionError as exc:
        code = str(exc) if str(exc) in _ERRORS else "producer_forbidden"
        _rejected(runtime, operation, code, _ERRORS[code][0])
        return _error(code)
    except OverflowError:
        _rejected(runtime, operation, "request_too_large", 413)
        return _error("request_too_large")
    except RequestEntityTooLarge:
        _rejected(runtime, operation, "request_too_large", 413)
        return _error("request_too_large")
    except DeviceFingerprintUnsupportedSchema:
        _rejected(runtime, operation, "unsupported_schema", 400)
        return _error("unsupported_schema")
    except DeviceFingerprintValidationError:
        _rejected(runtime, operation, "invalid_request", 400)
        return _error("invalid_request")
    except DeviceFingerprintConflict:
        runtime.telemetry.emit("device_fingerprint_ingest_conflict", request_id=g.device_fingerprint_request_id, http_status=409, error_category="idempotency_conflict")
        return _error("idempotency_conflict")
    except DeviceFingerprintStorageLimit as exc:
        runtime.note_storage_error(exc)
        _rejected(runtime, operation, "storage_limit", 503)
        return _error("storage_limit")
    except DeviceFingerprintStorageCorrupt as exc:
        runtime.note_storage_error(exc)
        _rejected(runtime, operation, "storage_corrupt", 503)
        return _error("storage_corrupt")
    except DeviceFingerprintStorageUnavailable:
        _rejected(runtime, operation, "repository_unavailable", 503)
        return _error("repository_unavailable")
    except Exception:
        _rejected(runtime, operation, "internal_error", 500)
        return _error("internal_error")
    finally:
        if registered:
            runtime.finish_ingest()
        slots.release()


def _rejected(runtime: Any, operation: str, category: str, status: int) -> None:
    event = "device_fingerprint_ingest_rejected" if operation == "evidence" else "device_fingerprint_source_health_rejected"
    runtime.telemetry.emit(event, request_id=g.device_fingerprint_request_id, http_status=status, error_category=category)


def _authenticate(header: Any, producers: tuple[Any, ...]) -> Any | None:
    token = None
    if isinstance(header, str) and header.startswith("Bearer ") and header.count(" ") == 1:
        candidate = header[7:]
        if _TOKEN.fullmatch(candidate) is not None:
            token = candidate
    comparisons = []
    for producer in producers:
        comparisons.append((producer, hmac.compare_digest(token or "", producer.bearer_token)))
    matches = [producer for producer, match in comparisons if token is not None and match]
    return matches[0] if len(matches) == 1 else None


def _success(result: Any, status: int) -> Response:
    return _json({"api_version": API_VERSION, "request_id": _request_id(), "result": result}, status)


def _error(code: str) -> Response:
    status, message = _ERRORS[code]
    return _json({"api_version": API_VERSION, "request_id": _request_id(), "error": {"code": code, "message": message}}, status)


def _request_id() -> str:
    return getattr(g, "device_fingerprint_request_id", str(uuid.uuid4()))


def _json(payload: Any, status: int) -> Response:
    body = json.dumps(payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(body) > MAX_HTTP_RESPONSE_BYTES:
        status, message = _ERRORS["internal_error"]
        body = json.dumps({"api_version": API_VERSION, "request_id": _request_id(), "error": {"code": "internal_error", "message": message}}, separators=(",", ":")).encode("utf-8")
    return Response(body, status=status, content_type="application/json")
