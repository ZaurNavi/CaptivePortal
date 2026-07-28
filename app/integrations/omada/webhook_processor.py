"""Live bridge from accepted webhook envelopes to normalized JSONL."""

from __future__ import annotations

from typing import Any

from .webhook_models import WebhookEnvelope
from .webhook_normalized_journal import (
    NormalizedJournalWriteError,
    OmadaWebhookNormalizedJournal,
)
from .webhook_normalizer import normalize_webhook


class WebhookNormalizationError(Exception):
    """Secret-safe context for an internal normalizer exception."""

    def __init__(
        self,
        *,
        webhook_id: str,
        payload_sha256: str,
        exception_type: str,
        error_code: str = "NORMALIZATION_FAILED",
    ):
        super().__init__(error_code)
        self.webhook_id = webhook_id
        self.payload_sha256 = payload_sha256
        self.exception_type = exception_type
        self.error_code = error_code


class WebhookNormalizedWriteError(Exception):
    """Secret-safe context for a normalized journal failure."""

    def __init__(
        self,
        *,
        webhook_id: str,
        normalized_event_id: str | None,
        target_path: str,
        exception_type: str,
        error_code: str = "NORMALIZED_LOG_WRITE_FAILED",
    ):
        super().__init__(error_code)
        self.webhook_id = webhook_id
        self.normalized_event_id = normalized_event_id
        self.target_path = target_path
        self.exception_type = exception_type
        self.error_code = error_code


class OmadaWebhookProcessor:
    """Normalize one persisted delivery and append its event batch."""

    def __init__(
        self,
        journal: OmadaWebhookNormalizedJournal,
    ):
        self.journal = journal

    def __call__(self, envelope: WebhookEnvelope) -> None:
        try:
            normalized = normalize_webhook(envelope.to_dict())
        except Exception as exc:
            raise WebhookNormalizationError(
                webhook_id=envelope.webhook_id,
                payload_sha256=envelope.payload_sha256,
                exception_type=type(exc).__name__,
            ) from exc

        try:
            self.journal.append_many(normalized)
        except NormalizedJournalWriteError as exc:
            raise WebhookNormalizedWriteError(
                webhook_id=envelope.webhook_id,
                normalized_event_id=exc.normalized_event_id,
                target_path=exc.target_path,
                exception_type=exc.exception_type,
            ) from exc
        except Exception as exc:
            raise WebhookNormalizedWriteError(
                webhook_id=envelope.webhook_id,
                normalized_event_id=_first_event_id(normalized),
                target_path=self.journal.log_file,
                exception_type=type(exc).__name__,
            ) from exc


def _first_event_id(events: list[dict[str, Any]]) -> str | None:
    if not events:
        return None
    value = events[0].get("normalized_event_id")
    return value if isinstance(value, str) else None
