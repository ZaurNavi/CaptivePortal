"""Canonical Site/filter-bound opaque keyset cursors for Admin Web."""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import datetime
from typing import Any, Mapping


_VERSION = 1


class AdminCursorError(ValueError):
    pass


def filter_fingerprint(filters: Mapping[str, Any]) -> str:
    payload = json.dumps(
        dict(filters),
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def encode_cursor(
    *,
    kind: str,
    site_id: str,
    timestamp: str,
    identity: str | int,
    filters: Mapping[str, Any],
) -> str:
    payload = {
        "f": filter_fingerprint(filters),
        "i": identity,
        "k": kind,
        "s": site_id,
        "t": timestamp,
        "v": _VERSION,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return base64.urlsafe_b64encode(encoded).decode("ascii").rstrip("=")


def decode_cursor(
    value: object,
    *,
    kind: str,
    site_id: str,
    filters: Mapping[str, Any],
    identity_kind: str,
    maximum_length: int,
) -> tuple[str, str | int] | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum_length
    ):
        raise AdminCursorError("cursor is malformed")
    try:
        padding = "=" * (-len(value) % 4)
        raw = base64.b64decode(
            value + padding,
            altchars=b"-_",
            validate=True,
        )
        payload = json.loads(raw.decode("ascii"))
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise AdminCursorError("cursor is malformed") from exc
    if (
        not isinstance(payload, dict)
        or set(payload) != {"f", "i", "k", "s", "t", "v"}
        or payload["v"] != _VERSION
        or payload["k"] != kind
        or payload["s"] != site_id
        or payload["f"] != filter_fingerprint(filters)
    ):
        raise AdminCursorError("cursor is malformed")
    timestamp = _timestamp(payload["t"])
    identity = _identity(payload["i"], identity_kind)
    if encode_cursor(
        kind=kind,
        site_id=site_id,
        timestamp=timestamp,
        identity=identity,
        filters=filters,
    ) != value:
        raise AdminCursorError("cursor is not canonical")
    return timestamp, identity


def _timestamp(value: object) -> str:
    if not isinstance(value, str):
        raise AdminCursorError("cursor is malformed")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError as exc:
        raise AdminCursorError("cursor is malformed") from exc
    canonical = parsed.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    if value != canonical:
        raise AdminCursorError("cursor is malformed")
    return value


def _identity(value: object, kind: str) -> str | int:
    if kind == "row_id":
        if type(value) is not int or value <= 0:
            raise AdminCursorError("cursor is malformed")
        return value
    if kind == "uuid":
        if not isinstance(value, str):
            raise AdminCursorError("cursor is malformed")
        try:
            canonical = str(uuid.UUID(value))
        except (ValueError, AttributeError) as exc:
            raise AdminCursorError("cursor is malformed") from exc
        if canonical != value:
            raise AdminCursorError("cursor is malformed")
        return value
    raise ValueError("unsupported cursor identity kind")
