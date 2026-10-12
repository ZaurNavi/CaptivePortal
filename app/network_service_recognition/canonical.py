"""CaptivPortalRecognitionCanonicalJsonV1. Errors never contain source values."""
import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping


class RecognitionValidationError(ValueError):
    def __init__(self, reason="invalid_recognition_artifact"):
        self.reason = reason
        super().__init__(reason)


def canonical_json(value):
    def plain(item):
        if isinstance(item, Mapping):
            if any(type(key) is not str for key in item):
                raise RecognitionValidationError()
            return {key: plain(val) for key, val in item.items()}
        if type(item) in (list, tuple):
            return [plain(val) for val in item]
        if type(item) is str:
            if unicodedata.normalize("NFC", item) != item:
                raise RecognitionValidationError()
            return item
        if item is None or type(item) in (int, bool):
            return item
        raise RecognitionValidationError()
    try:
        return json.dumps(plain(value), ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (UnicodeError, RecursionError, TypeError, ValueError):
        raise RecognitionValidationError() from None


def strict_artifact_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise RecognitionValidationError("duplicate_json_member")
            result[key] = value
        return result
    def forbidden(_):
        raise RecognitionValidationError()
    try:
        if type(raw) is not bytes or len(raw) > 16 * 1024 * 1024:
            raise RecognitionValidationError()
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                           parse_float=forbidden, parse_constant=forbidden)
        if type(value) is not dict or canonical_json(value) != raw:
            raise RecognitionValidationError("noncanonical_artifact_bytes")
        return value
    except (UnicodeError, ValueError, TypeError, RecursionError):
        raise RecognitionValidationError() from None


def content_digest(value, own_field):
    return hashlib.sha256(canonical_json({key: val for key, val in value.items()
                                         if key != own_field})).hexdigest()


def canonical_hostname(value):
    try:
        if type(value) is not str or not value.isascii() or not 1 <= len(value) <= 253:
            return None
        host = value[:-1] if value.endswith(".") else value
        host = host.lower()
        if not host or any(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) is None
                           for label in host.split(".")):
            return None
        return host
    except (ValueError, TypeError):
        return None
