"""Background-only HTTPS/Bearer producer for normalized portal evidence."""

from __future__ import annotations

import re
import ssl
from pathlib import Path
from typing import Any, Iterable

import requests

from .models import DeliveryResult, PortalEvidenceConfig, PortalEvidenceError

_TOKEN = re.compile(r"[A-Za-z0-9_-]{32,256}")
_TRANSIENT = frozenset({500, 503})
_PERMANENT = frozenset({400, 401, 403, 404, 405, 409, 413})


class PortalEvidenceProducer:
    def __init__(self, config: PortalEvidenceConfig, *, session: Any = requests) -> None:
        self.config = config
        self.session = session

    def deliver_evidence(self, events: Iterable[dict[str, Any]]) -> DeliveryResult:
        return self._post("evidence/batch", list(events))

    def deliver_source_health(self, events: Iterable[dict[str, Any]]) -> DeliveryResult:
        return self._post("source-health/batch", list(events))

    def _post(self, endpoint: str, events: list[dict[str, Any]]) -> DeliveryResult:
        try:
            token = self._credential()
            self._validate_ca()
        except PortalEvidenceError:
            return DeliveryResult("config_unavailable", self.config.reject_cooldown_seconds)
        try:
            response = self.session.post(
                f"{self.config.evidence_base_url}/{endpoint}",
                json={"producer_id": self.config.producer_id, "events": events},
                headers={"Authorization": f"Bearer {token}"},
                timeout=(self.config.connect_timeout_seconds, self.config.read_timeout_seconds),
                verify=self.config.ca_cert_path,
            )
        except requests.RequestException:
            return DeliveryResult("transient", self.config.transient_cooldown_seconds)
        status = int(response.status_code)
        if status == 200:
            return DeliveryResult("success", 0, status)
        if status == 429:
            return DeliveryResult("transient", _retry_after(response), status)
        if status in _TRANSIENT:
            return DeliveryResult("transient", self.config.transient_cooldown_seconds, status)
        if status in _PERMANENT:
            return DeliveryResult("permanent", self.config.reject_cooldown_seconds, status)
        return DeliveryResult("permanent", self.config.reject_cooldown_seconds, status)

    def _credential(self) -> str:
        try:
            token = Path(self.config.credential_path).read_text(encoding="ascii").strip()
        except (OSError, UnicodeError) as exc:
            raise PortalEvidenceError("producer credential is unavailable") from exc
        if _TOKEN.fullmatch(token) is None:
            raise PortalEvidenceError("producer credential is invalid")
        return token

    def _validate_ca(self) -> None:
        try:
            ssl.create_default_context(cafile=self.config.ca_cert_path)
        except (OSError, ssl.SSLError) as exc:
            raise PortalEvidenceError("producer CA is unavailable") from exc


def _retry_after(response: Any) -> int:
    try:
        value = int(response.headers.get("Retry-After", ""))
    except (TypeError, ValueError):
        value = 0
    return value if 1 <= value <= 60 else 30
