"""NI-specific strict primitives; no source values in exposed failures."""
import ipaddress
import json
import os
import re
import uuid
from datetime import datetime, timezone

from .models import INT64_MAX, NetworkMetadataValidationError

_TIME = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:?[0-9]{2})")


def ni_timestamp(value, *, canonical=False):
    try:
        if not isinstance(value, str) or len(value.encode("utf-8")) > 64 or _TIME.fullmatch(value) is None:
            raise ValueError
        normalized = value.replace("Z", "+00:00")
        if value[-1] != "Z":
            if normalized[-3] != ":":
                normalized = normalized[:-2] + ":" + normalized[-2:]
            hours, minutes = int(normalized[-5:-3]), int(normalized[-2:])
            if hours > 23 or minutes > 59:
                raise ValueError
        # Python 3.10 accepts only 3/6 fractional digits; the NI contract accepts 1..6.
        normalized = re.sub(r"\.([0-9]{1,6})(?=[+-])", lambda match: "." + match[1].ljust(6, "0"), normalized)
        parsed = datetime.fromisoformat(normalized).astimezone(timezone.utc)
        rendered = ni_format_utc(parsed)
        if canonical and value != rendered:
            raise ValueError
        return parsed
    except (ValueError, TypeError, UnicodeError, OverflowError):
        raise NetworkMetadataValidationError() from None


def ni_format_utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise NetworkMetadataValidationError()
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def integer(value, low=0, high=INT64_MAX):
    if type(value) is not int or not low <= value <= high:
        raise NetworkMetadataValidationError()
    return value


def text(value, maximum, *, pattern=None, ascii_only=False, controls=False):
    try:
        if not isinstance(value, str) or not 1 <= len(value.encode("utf-8")) <= maximum or "\0" in value:
            raise ValueError
        if ascii_only and not value.isascii():
            raise ValueError
        if controls and any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError
        if pattern is not None and re.fullmatch(pattern, value, flags=re.ASCII) is None:
            raise ValueError
        return value
    except (ValueError, UnicodeError):
        raise NetworkMetadataValidationError() from None


def digest(value, length=64):
    return text(value, length, pattern="[0-9a-f]{" + str(length) + "}", ascii_only=True)


def canonical_uuid(value, version=None):
    try:
        parsed = uuid.UUID(value)
        if str(parsed) != value or (version is not None and parsed.version != version):
            raise ValueError
        return value
    except (ValueError, TypeError, AttributeError):
        raise NetworkMetadataValidationError() from None


def absolute_path(value):
    if not isinstance(value, str) or not value or "\0" in value or not os.path.isabs(value):
        raise NetworkMetadataValidationError()
    return value


def ip(value, version=None):
    text(value, 45)
    try:
        parsed = ipaddress.ip_address(value)
        if version is not None and parsed.version != version:
            raise ValueError
        return str(parsed)
    except ValueError:
        raise NetworkMetadataValidationError() from None


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise NetworkMetadataValidationError("duplicate_json_member")
            result[key] = value
        return result

    def invalid_constant(_):
        raise NetworkMetadataValidationError("invalid_json")

    try:
        decoded = data.decode("utf-8", errors="strict") if isinstance(data, bytes) else data
    except UnicodeError:
        raise NetworkMetadataValidationError("invalid_utf8") from None
    try:
        result = json.loads(decoded, object_pairs_hook=pairs, parse_constant=invalid_constant)
    except NetworkMetadataValidationError:
        raise
    except (ValueError, TypeError, RecursionError):
        raise NetworkMetadataValidationError("invalid_json") from None
    if not isinstance(result, dict):
        raise NetworkMetadataValidationError("non_object_json")
    return result
