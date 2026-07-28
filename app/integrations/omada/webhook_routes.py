"""HTTP route for the permanent Omada webhook receiver."""

import json
import logging
import uuid
from typing import Any

from flask import Blueprint, Response, g, request

from .webhook_models import OmadaWebhookConfig
from .webhook_receiver import (
    AuthenticationError,
    BodyReadError,
    BodyTooLargeError,
    OmadaWebhookReceiver,
    WebhookPersistError,
    utc_timestamp,
)
from .webhook_security import source_ip_allowed


WEBHOOK_PATH = "/api/integrations/omada/webhook"


def create_omada_webhook_blueprint(
    *,
    config: OmadaWebhookConfig,
    receiver: OmadaWebhookReceiver | None,
    logger: logging.Logger,
) -> Blueprint:
    if config.enabled and receiver is None:
        raise ValueError(
            "Enabled Omada webhook endpoint requires a receiver"
        )

    blueprint = Blueprint(
        "omada_webhook",
        __name__,
    )

    @blueprint.before_app_request
    def guard_omada_webhook():
        if request.path != WEBHOOK_PATH:
            return None

        webhook_id = str(uuid.uuid4())
        received_at = utc_timestamp()
        g.omada_webhook_id = webhook_id
        g.omada_webhook_received_at = received_at

        if not config.enabled:
            _log_event(
                logger,
                event="omada.webhook_rejected",
                level="warning",
                webhook_id=webhook_id,
                source_ip=request.remote_addr,
                http_method=request.method,
                request_path=request.path,
                rejection_reason="module_disabled",
            )
            return Response(status=404)

        if request.method != "POST":
            _log_event(
                logger,
                event="omada.webhook_rejected",
                level="warning",
                webhook_id=webhook_id,
                source_ip=request.remote_addr,
                http_method=request.method,
                request_path=request.path,
                rejection_reason="method_not_allowed",
            )
            response = Response(status=405)
            response.headers["Allow"] = "POST"
            return response

        return None

    @blueprint.route(
        WEBHOOK_PATH,
        methods=["POST"],
        provide_automatic_options=False,
    )
    def omada_webhook():
        webhook_id = g.omada_webhook_id
        received_at = g.omada_webhook_received_at

        if not source_ip_allowed(
            request.remote_addr,
            config.allowed_ips,
        ):
            _log_event(
                logger,
                event="omada.webhook_rejected",
                level="warning",
                webhook_id=webhook_id,
                source_ip=request.remote_addr,
                http_method=request.method,
                request_path=request.path,
                rejection_reason="source_ip_not_allowed",
            )
            return Response(status=403)

        declared_length = request.content_length
        if (
            declared_length is not None
            and declared_length > config.max_body_bytes
        ):
            _log_event(
                logger,
                event="omada.webhook_rejected",
                level="warning",
                webhook_id=webhook_id,
                source_ip=request.remote_addr,
                http_method=request.method,
                request_path=request.path,
                rejection_reason="payload_too_large",
                content_length=declared_length,
            )
            return Response(status=413)

        assert receiver is not None
        try:
            receiver.receive(
                request,
                webhook_id=webhook_id,
                received_at=received_at,
            )
        except BodyTooLargeError:
            _log_event(
                logger,
                event="omada.webhook_rejected",
                level="warning",
                webhook_id=webhook_id,
                source_ip=request.remote_addr,
                http_method=request.method,
                request_path=request.path,
                rejection_reason="payload_too_large",
            )
            return Response(status=413)
        except AuthenticationError as exc:
            _log_event(
                logger,
                event="omada.webhook_rejected",
                level="warning",
                webhook_id=webhook_id,
                source_ip=request.remote_addr,
                http_method=request.method,
                request_path=request.path,
                rejection_reason=exc.rejection_reason,
            )
            return Response(status=401)
        except BodyReadError:
            _log_event(
                logger,
                event="omada.webhook_rejected",
                level="warning",
                webhook_id=webhook_id,
                source_ip=request.remote_addr,
                http_method=request.method,
                request_path=request.path,
                rejection_reason="invalid_request",
            )
            return Response(status=400)
        except WebhookPersistError:
            _log_event(
                logger,
                event="omada.webhook_persist_failed",
                level="error",
                webhook_id=webhook_id,
                source_ip=request.remote_addr,
                http_method=request.method,
                request_path=request.path,
                error_type="log_write_failed",
            )
            return Response(status=500)
        except Exception as exc:
            _log_event(
                logger,
                event="omada.webhook_internal_error",
                level="error",
                webhook_id=webhook_id,
                source_ip=request.remote_addr,
                error_type=type(exc).__name__,
            )
            return Response(status=500)

        return Response(status=204)

    return blueprint


def _log_event(
    logger: logging.Logger,
    *,
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
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.log(
        numeric_level,
        json.dumps(
            record,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
        ),
    )
