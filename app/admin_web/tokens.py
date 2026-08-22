"""Canonical opaque-token helpers used by Admin Web security state."""

from __future__ import annotations

import hmac
import re
import secrets


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}")


def new_token() -> str:
    token = secrets.token_urlsafe(32)
    if TOKEN_PATTERN.fullmatch(token) is None:  # pragma: no cover - stdlib invariant
        raise RuntimeError("token generator returned a non-canonical token")
    return token


def is_canonical_token(value: object) -> bool:
    return isinstance(value, str) and TOKEN_PATTERN.fullmatch(value) is not None


def token_matches(submitted: object, stored: object) -> bool:
    if not is_canonical_token(submitted) or not is_canonical_token(stored):
        return False
    return hmac.compare_digest(
        submitted.encode("ascii"),
        stored.encode("ascii"),
    )
