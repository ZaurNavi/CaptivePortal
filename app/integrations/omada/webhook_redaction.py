"""Secret redaction helpers for persisted webhook envelopes."""

import json
import re
from collections.abc import Mapping
from typing import Any, Iterable


REDACTED = "***REDACTED***"

_SENSITIVE_HEADER_KEYS = {
    "authorization",
    "proxyauthorization",
    "cookie",
    "setcookie",
    "xomadawebhooktoken",
}
_SENSITIVE_QUERY_KEYS = {
    "token",
    "secret",
    "key",
    "apikey",
    "accesstoken",
}
_SENSITIVE_JSON_KEYS = {
    *_SENSITIVE_QUERY_KEYS,
    "shardsecret",
    "sharedsecret",
    "clientsecret",
    "refreshtoken",
    "password",
    *_SENSITIVE_HEADER_KEYS,
}


def _normalize_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def is_sensitive_json_key(value: Any) -> bool:
    return _normalize_key(value) in _SENSITIVE_JSON_KEYS


def redact_headers(
    headers: Iterable[tuple[str, Any]],
) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in headers:
        safe[str(key)] = (
            REDACTED
            if _normalize_key(key) in _SENSITIVE_HEADER_KEYS
            else str(value)
        )
    return safe


def redact_query_parameters(
    parameters: Iterable[tuple[str, list[str]]],
) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, values in parameters:
        redacted_values = (
            [REDACTED for _value in values]
            if _normalize_key(key) in _SENSITIVE_QUERY_KEYS
            else [str(value) for value in values]
        )
        safe[str(key)] = (
            redacted_values[0]
            if len(redacted_values) == 1
            else redacted_values
        )
    return safe


def redact_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): (
                REDACTED
                if is_sensitive_json_key(key)
                else redact_json(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_json(item) for item in value]
    return value


def safe_json_body(redacted_payload: Any) -> str:
    return json.dumps(
        redacted_payload,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )
