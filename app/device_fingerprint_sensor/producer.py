"""At-least-once HTTPS producer for the normalized spool."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from .models import SensorConfig, SensorError
from .spool import SensorSpool

_TOKEN = re.compile(r"[A-Za-z0-9_-]{32,256}")
_TRANSIENT = frozenset({429, 500, 503})
_PERMANENT = frozenset({400, 401, 403, 404, 405, 409, 413})


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    status: str
    delivered: int
    delay_seconds: float
    http_status: int | None


class EvidenceProducer:
    def __init__(self, config: SensorConfig, spool: SensorSpool, *, session: Any = requests,
                 random_value=None) -> None:
        self.config = config
        self.spool = spool
        self.session = session
        self.random_value = random_value or random.random
        self.attempt = 0
        self.permanent_fault = False

    def read_credential(self) -> str:
        if not self.config.credential_path:
            raise SensorError("producer credential is unavailable")
        try:
            token = Path(self.config.credential_path).read_text(encoding="ascii").strip()
        except OSError as exc:
            raise SensorError("producer credential is unavailable") from exc
        if _TOKEN.fullmatch(token) is None:
            raise SensorError("producer credential is invalid")
        return token

    def deliver_once(self) -> DeliveryResult:
        if self.permanent_fault:
            return DeliveryResult("permanent", 0, 0, None)
        batch = self.spool.batch(self.config.delivery_batch_size)
        if batch is None:
            self.attempt = 0
            return DeliveryResult("empty", 0, 0, None)
        endpoint, rows = batch
        url_path = "evidence/batch" if endpoint == "evidence" else "source-health/batch"
        token = self.read_credential()
        try:
            response = self.session.post(
                f"{self.config.evidence_base_url}/{url_path}",
                json={"producer_id": self.config.producer_id, "events": [row[1] for row in rows]},
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.config.http_timeout_seconds,
                verify=self.config.ca_cert_path,
            )
        except requests.RequestException:
            return self._retry(None, None)
        status = int(response.status_code)
        if status == 200:
            self.spool.acknowledge(row[0] for row in rows)
            self.attempt = 0
            return DeliveryResult("delivered", len(rows), 0, 200)
        if status in _PERMANENT:
            self.permanent_fault = True
            return DeliveryResult("permanent", 0, 0, status)
        if status in _TRANSIENT:
            return self._retry(status, response.headers.get("Retry-After"))
        self.permanent_fault = True
        return DeliveryResult("permanent", 0, 0, status)

    def _retry(self, status: int | None, retry_after: str | None) -> DeliveryResult:
        if status == 429 and retry_after is not None:
            try:
                value = int(retry_after)
            except ValueError:
                value = 0
            if 1 <= value <= 60:
                return DeliveryResult("retry", 0, float(value), status)
        base = min(30, 2 ** min(self.attempt, 5))
        self.attempt += 1
        jitter = (self.random_value() * 0.2) - 0.1
        return DeliveryResult("retry", 0, base * (1 + jitter), status)
