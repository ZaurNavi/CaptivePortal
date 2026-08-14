"""Strict fail-open mapping from Omada Site names to technical IDs."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, NamedTuple


MAPPING_INVALID_EVENT = "omada.webhook_site_mapping_invalid"


class SiteResolution(NamedTuple):
    """Resolved technical context for one normalized webhook event."""

    site_id: str | None
    status: str


@dataclass(frozen=True)
class WebhookSiteIdMapping:
    """Validated immutable Site-name mapping with fail-open resolution."""

    entries: MappingProxyType
    valid: bool
    error_code: str | None = None

    def resolve(self, site: Any) -> SiteResolution:
        if not self.valid:
            return SiteResolution(None, "mapping_invalid")
        if not isinstance(site, str) or not site.strip():
            return SiteResolution(None, "site_missing")
        site_id = self.entries.get(site)
        if site_id is None:
            return SiteResolution(None, "site_unresolved")
        return SiteResolution(site_id, "resolved")


class _DuplicateKeyError(ValueError):
    pass


def load_webhook_site_id_mapping(raw_json: Any) -> WebhookSiteIdMapping:
    """Parse the complete mapping strictly, returning an invalid sentinel."""
    if not isinstance(raw_json, str):
        return _invalid("CONFIG_NOT_STRING")
    try:
        payload = json.loads(
            raw_json,
            object_pairs_hook=_object_without_duplicate_keys,
        )
    except _DuplicateKeyError:
        return _invalid("DUPLICATE_SITE_NAME")
    except (json.JSONDecodeError, UnicodeError, RecursionError):
        return _invalid("MALFORMED_JSON")

    if not isinstance(payload, dict):
        return _invalid("ROOT_NOT_OBJECT")

    validated: dict[str, str] = {}
    for site_name, site_id in payload.items():
        if not site_name.strip():
            return _invalid("SITE_NAME_EMPTY")
        if not isinstance(site_id, str):
            return _invalid("SITE_ID_NOT_STRING")
        if not site_id.strip():
            return _invalid("SITE_ID_EMPTY")
        validated[site_name] = site_id

    return WebhookSiteIdMapping(
        entries=MappingProxyType(validated),
        valid=True,
    )


def log_invalid_webhook_site_id_mapping(
    logger: logging.Logger,
    mapping: WebhookSiteIdMapping,
) -> None:
    """Emit one structured warning without exposing the raw environment."""
    if mapping.valid:
        return
    record = {
        "timestamp": _utc_timestamp(),
        "level": "warning",
        "service": "captive_portal",
        "module": "omada_webhook_normalizer",
        "event": MAPPING_INVALID_EVENT,
        "schema_version": 1,
        "component": "omada_webhook_site_mapping",
        "error_code": mapping.error_code or "MAPPING_INVALID",
    }
    logger.warning(
        json.dumps(
            record,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
        )
    )


def _object_without_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(key)
        result[key] = value
    return result


def _invalid(error_code: str) -> WebhookSiteIdMapping:
    return WebhookSiteIdMapping(
        entries=MappingProxyType({}),
        valid=False,
        error_code=error_code,
    )


def _utc_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


EMPTY_WEBHOOK_SITE_ID_MAPPING = load_webhook_site_id_mapping("{}")
