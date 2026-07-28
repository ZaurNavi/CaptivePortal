"""Capture and persist Omada webhook deliveries without interpreting them."""

import base64
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable

from flask import Request

from .webhook_journal import OmadaWebhookJournal
from .webhook_models import OmadaWebhookConfig, WebhookEnvelope
from .webhook_redaction import (
    is_sensitive_json_key,
    redact_headers,
    redact_json,
    redact_query_parameters,
    safe_json_body,
)
from .webhook_security import authentication_failure_reason


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")


def process_webhook(_envelope: WebhookEnvelope) -> None:
    """Future module hook. Stage 1 intentionally performs no processing."""


class BodyTooLargeError(Exception):
    """Raised after a bounded read proves the actual body is too large."""


class BodyReadError(Exception):
    """Raised when the WSGI input stream cannot be read safely."""


class AuthenticationError(Exception):
    """Raised when the configured webhook authentication check fails."""

    def __init__(self, rejection_reason: str):
        super().__init__(rejection_reason)
        self.rejection_reason = rejection_reason


class WebhookPersistError(Exception):
    """Raised when an accepted delivery cannot be journaled."""


class OmadaWebhookReceiver:
    """Build a secret-safe envelope and synchronously journal it."""

    def __init__(
        self,
        *,
        config: OmadaWebhookConfig,
        journal: OmadaWebhookJournal,
        logger: logging.Logger,
        processor: Callable[[WebhookEnvelope], None] = process_webhook,
    ):
        self.config = config
        self.journal = journal
        self.logger = logger
        self.processor = processor

    def receive(
        self,
        request: Request,
        *,
        webhook_id: str,
        received_at: str,
    ) -> WebhookEnvelope:
        body = self._read_bounded_body(request)
        payload_sha256 = hashlib.sha256(body).hexdigest()
        decoded = self._decode_and_parse(body)

        authentication_error = authentication_failure_reason(
            self.config,
            parsed_payload=decoded["authentication_payload"],
            header_token=request.headers.get(
                "X-Omada-Webhook-Token"
            ),
        )
        if authentication_error is not None:
            raise AuthenticationError(authentication_error)

        envelope = self._build_envelope(
            request=request,
            body=body,
            decoded=decoded,
            payload_sha256=payload_sha256,
            webhook_id=webhook_id,
            received_at=received_at,
        )
        try:
            self.journal.append(self._build_record(envelope))
        except Exception as exc:
            raise WebhookPersistError from exc

        try:
            self.processor(envelope)
        except Exception as exc:
            self._log_system_event(
                "omada.webhook_processing_failed",
                "error",
                webhook_id=webhook_id,
                source_ip=request.remote_addr,
                error_type=type(exc).__name__,
            )
        return envelope

    def _read_bounded_body(self, request: Request) -> bytes:
        stream = request.stream
        chunks: list[bytes] = []
        bytes_read = 0
        try:
            while bytes_read <= self.config.max_body_bytes:
                remaining = self.config.max_body_bytes + 1 - bytes_read
                chunk = stream.read(min(65_536, remaining))
                if not isinstance(chunk, (bytes, bytearray)):
                    raise TypeError("WSGI input did not return bytes")
                if not chunk:
                    break
                normalized_chunk = bytes(chunk)
                chunks.append(normalized_chunk)
                bytes_read += len(normalized_chunk)
        except Exception as exc:
            raise BodyReadError from exc
        body = b"".join(chunks)
        if len(body) > self.config.max_body_bytes:
            raise BodyTooLargeError
        return body

    @staticmethod
    def _decode_and_parse(body: bytes) -> dict[str, Any]:
        try:
            text = body.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            return {
                "payload_format": "binary",
                "body_encoding": "base64",
                "raw_body": None,
                "raw_body_base64": base64.b64encode(body).decode("ascii"),
                "authentication_payload": None,
                "parsed_payload": None,
                "parse_error": None,
                "decode_error": "invalid_utf8",
            }

        sensitive_key_seen = False

        def object_pairs_hook(
            pairs: list[tuple[str, Any]],
        ) -> dict[str, Any]:
            nonlocal sensitive_key_seen
            result: dict[str, Any] = {}
            for key, value in pairs:
                if is_sensitive_json_key(key):
                    sensitive_key_seen = True
                result[key] = value
            return result

        def reject_non_standard_constant(value: str):
            raise ValueError(
                f"Non-standard JSON constant: {value}"
            )

        try:
            parsed_payload = json.loads(
                text,
                object_pairs_hook=object_pairs_hook,
                parse_constant=reject_non_standard_constant,
            )
        except ValueError:
            return {
                "payload_format": "text",
                "body_encoding": "utf-8",
                "raw_body": text,
                "raw_body_base64": None,
                "authentication_payload": None,
                "parsed_payload": None,
                "parse_error": "invalid_json",
                "decode_error": None,
            }

        redacted_payload = redact_json(parsed_payload)
        raw_body = (
            safe_json_body(redacted_payload)
            if sensitive_key_seen
            else text
        )
        return {
            "payload_format": "json",
            "body_encoding": "utf-8",
            "raw_body": raw_body,
            "raw_body_base64": None,
            "authentication_payload": parsed_payload,
            "parsed_payload": redacted_payload,
            "parse_error": None,
            "decode_error": None,
        }

    @staticmethod
    def _build_envelope(
        *,
        request: Request,
        body: bytes,
        decoded: dict[str, Any],
        payload_sha256: str,
        webhook_id: str,
        received_at: str,
    ) -> WebhookEnvelope:
        return WebhookEnvelope(
            webhook_id=webhook_id,
            received_at=received_at,
            source_ip=request.remote_addr,
            http_method=request.method,
            request_path=request.path,
            content_type=request.content_type,
            content_length=request.content_length,
            actual_body_length=len(body),
            user_agent=request.user_agent.string or None,
            query_parameters=redact_query_parameters(
                request.args.lists()
            ),
            headers=redact_headers(request.headers.items()),
            payload_sha256=payload_sha256,
            payload_format=decoded["payload_format"],
            body_encoding=decoded["body_encoding"],
            raw_body=decoded["raw_body"],
            raw_body_base64=decoded["raw_body_base64"],
            parsed_payload=decoded["parsed_payload"],
            parse_error=decoded["parse_error"],
            decode_error=decoded["decode_error"],
        )

    @staticmethod
    def _build_record(
        envelope: WebhookEnvelope,
    ) -> dict[str, Any]:
        return {
            "timestamp": envelope.received_at,
            "level": "info",
            "service": "captive_portal",
            "module": "omada_webhook",
            "event": "omada.webhook_received",
            "schema_version": 1,
            **envelope.to_dict(),
        }

    def _log_system_event(
        self,
        event: str,
        level: str,
        **fields: Any,
    ) -> None:
        record = {
            "timestamp": utc_timestamp(),
            "level": level,
            "service": "captive_portal",
            "module": "omada_webhook",
            "event": event,
            "schema_version": 1,
            **fields,
        }
        numeric_level = getattr(
            logging,
            level.upper(),
            logging.INFO,
        )
        self.logger.log(
            numeric_level,
            json.dumps(
                record,
                ensure_ascii=True,
                allow_nan=False,
                separators=(",", ":"),
            ),
        )
