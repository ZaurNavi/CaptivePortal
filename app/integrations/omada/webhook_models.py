"""Configuration and transport models for Omada webhook deliveries."""

from dataclasses import asdict, dataclass
from ipaddress import ip_address
from typing import Any


SUPPORTED_AUTH_MODES = {
    "ip_only",
    "omada_payload_secret",
    "header_token",
}


def _parse_bool(value: Any, setting_name: str) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    raise ValueError(
        f"{setting_name} must be true or false, got {value!r}"
    )


def _parse_allowed_ips(value: Any) -> frozenset[str]:
    if value is None:
        raw_values: list[str] = []
    elif isinstance(value, str):
        raw_values = value.split(",")
    else:
        raw_values = [str(item) for item in value]

    allowed: set[str] = set()
    for raw_value in raw_values:
        candidate = raw_value.strip()
        if not candidate:
            continue
        try:
            allowed.add(str(ip_address(candidate)))
        except ValueError as exc:
            raise ValueError(
                "OMADA_WEBHOOK_ALLOWED_IPS contains an invalid IP "
                f"address: {candidate!r}"
            ) from exc
    return frozenset(allowed)


@dataclass(frozen=True)
class OmadaWebhookConfig:
    """Validated webhook receiver configuration."""

    enabled: bool
    allowed_ips: frozenset[str]
    auth_mode: str
    shared_secret: str
    header_token: str
    max_body_bytes: int
    log_file: str

    @classmethod
    def from_settings(
        cls,
        settings: dict[str, Any],
    ) -> "OmadaWebhookConfig":
        enabled = _parse_bool(
            settings.get("omada_webhook_enabled", False),
            "OMADA_WEBHOOK_ENABLED",
        )
        auth_mode = str(
            settings.get("omada_webhook_auth_mode", "ip_only")
        ).strip().lower()
        if auth_mode not in SUPPORTED_AUTH_MODES:
            raise ValueError(
                "OMADA_WEBHOOK_AUTH_MODE must be one of "
                f"{sorted(SUPPORTED_AUTH_MODES)}, got {auth_mode!r}"
            )

        raw_shared_secret = settings.get(
            "omada_webhook_shared_secret",
            "",
        )
        raw_header_token = settings.get(
            "omada_webhook_header_token",
            "",
        )
        shared_secret = (
            ""
            if raw_shared_secret is None
            else str(raw_shared_secret)
        )
        header_token = (
            ""
            if raw_header_token is None
            else str(raw_header_token)
        )
        if (
            auth_mode == "omada_payload_secret"
            and not shared_secret.strip()
        ):
            raise ValueError(
                "OMADA_WEBHOOK_SHARED_SECRET is required when "
                "OMADA_WEBHOOK_AUTH_MODE=omada_payload_secret"
            )
        if auth_mode == "header_token" and not header_token.strip():
            raise ValueError(
                "OMADA_WEBHOOK_HEADER_TOKEN is required when "
                "OMADA_WEBHOOK_AUTH_MODE=header_token"
            )

        raw_max_body_bytes = settings.get(
            "omada_webhook_max_body_bytes",
            1_048_576,
        )
        try:
            max_body_bytes = int(raw_max_body_bytes)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "OMADA_WEBHOOK_MAX_BODY_BYTES must be a positive integer"
            ) from exc
        if max_body_bytes <= 0:
            raise ValueError(
                "OMADA_WEBHOOK_MAX_BODY_BYTES must be a positive integer"
            )

        raw_log_file = settings.get(
            "omada_webhook_log_file",
            "/opt/CaptivePortal/logs/omada_webhook.log",
        )
        log_file = (
            ""
            if raw_log_file is None
            else str(raw_log_file).strip()
        )
        if not log_file:
            raise ValueError("OMADA_WEBHOOK_LOG_FILE must not be empty")

        return cls(
            enabled=enabled,
            allowed_ips=_parse_allowed_ips(
                settings.get(
                    "omada_webhook_allowed_ips",
                    "",
                )
            ),
            auth_mode=auth_mode,
            shared_secret=shared_secret,
            header_token=header_token,
            max_body_bytes=max_body_bytes,
            log_file=log_file,
        )


@dataclass(frozen=True)
class WebhookEnvelope:
    """Secret-safe representation of one webhook HTTP delivery."""

    webhook_id: str
    received_at: str
    source_ip: str | None
    http_method: str
    request_path: str
    content_type: str | None
    content_length: int | None
    actual_body_length: int
    user_agent: str | None
    query_parameters: dict[str, Any]
    headers: dict[str, Any]
    payload_sha256: str
    payload_format: str
    body_encoding: str | None
    raw_body: str | None
    raw_body_base64: str | None
    parsed_payload: Any
    parse_error: str | None
    decode_error: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
