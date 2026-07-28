"""Source-IP and shared-secret checks for Omada webhook requests."""

import hmac
from ipaddress import ip_address
from typing import Any

from .webhook_models import OmadaWebhookConfig


def source_ip_allowed(
    source_ip: str | None,
    allowed_ips: frozenset[str],
) -> bool:
    if source_ip is None:
        return False
    try:
        normalized = str(ip_address(source_ip))
    except ValueError:
        return False
    return normalized in allowed_ips


def authentication_failure_reason(
    config: OmadaWebhookConfig,
    *,
    parsed_payload: Any,
    header_token: str | None,
) -> str | None:
    if config.auth_mode == "ip_only":
        return None
    if config.auth_mode == "header_token":
        valid = (
            isinstance(header_token, str)
            and hmac.compare_digest(
                header_token,
                config.header_token,
            )
        )
        return None if valid else "invalid_token"
    if config.auth_mode == "omada_payload_secret":
        if not isinstance(parsed_payload, dict):
            return "missing_payload_secret"
        if "shardSecret" not in parsed_payload:
            return "missing_payload_secret"
        supplied = parsed_payload.get("shardSecret")
        valid = (
            isinstance(supplied, str)
            and hmac.compare_digest(
                supplied,
                config.shared_secret,
            )
        )
        return None if valid else "invalid_payload_secret"
    return "invalid_request"
