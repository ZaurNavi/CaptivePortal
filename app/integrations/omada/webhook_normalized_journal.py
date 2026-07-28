"""Thread-safe rotating JSONL journal for normalized Omada events."""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler
from typing import Any, Iterable

from .webhook_journal import (
    DEFAULT_ROTATION_BACKUP_COUNT,
    DEFAULT_ROTATION_MAX_BYTES,
)


class NormalizedJournalWriteError(Exception):
    """Identify the normalized event whose append failed."""

    def __init__(
        self,
        *,
        normalized_event_id: str | None,
        target_path: str,
        exception_type: str,
    ):
        super().__init__("Normalized Omada journal write failed")
        self.normalized_event_id = normalized_event_id
        self.target_path = target_path
        self.exception_type = exception_type


class _NormalizedRotatingFileHandler(RotatingFileHandler):
    def _open(self):
        stream = super()._open()
        if os.name == "posix":
            os.chmod(self.baseFilename, 0o640)
        return stream

    def handleError(self, record: logging.LogRecord) -> None:
        error = sys.exc_info()[1]
        if error is not None:
            raise error
        raise OSError("Unknown normalized Omada journal failure")


class OmadaWebhookNormalizedJournal:
    """Append strict JSON records without interleaving webhook batches."""

    def __init__(
        self,
        log_file: str,
        *,
        rotation_max_bytes: int = DEFAULT_ROTATION_MAX_BYTES,
        rotation_backup_count: int = DEFAULT_ROTATION_BACKUP_COUNT,
    ):
        self.log_file = str(log_file)
        self._rotation_max_bytes = max(0, int(rotation_max_bytes))
        self._rotation_backup_count = max(
            0,
            int(rotation_backup_count),
        )
        self._lock = threading.RLock()
        self._handler: _NormalizedRotatingFileHandler | None = None

    def append(self, record: dict[str, Any]) -> None:
        self.append_many([record])

    def append_many(
        self,
        records: Iterable[dict[str, Any]],
    ) -> None:
        serialized: list[tuple[str | None, str]] = []
        for record in records:
            event_id = _event_id(record)
            try:
                line = json.dumps(
                    record,
                    ensure_ascii=True,
                    allow_nan=False,
                    separators=(",", ":"),
                )
            except Exception as exc:
                raise NormalizedJournalWriteError(
                    normalized_event_id=event_id,
                    target_path=self.log_file,
                    exception_type=type(exc).__name__,
                ) from exc
            serialized.append((event_id, line))

        if not serialized:
            return

        with self._lock:
            handler = self._get_handler()
            for event_id, line in serialized:
                log_record = logging.LogRecord(
                    name="captive_portal.omada_webhook_normalized",
                    level=logging.INFO,
                    pathname=__file__,
                    lineno=0,
                    msg=line,
                    args=(),
                    exc_info=None,
                )
                try:
                    handler.emit(log_record)
                except Exception as exc:
                    raise NormalizedJournalWriteError(
                        normalized_event_id=event_id,
                        target_path=self.log_file,
                        exception_type=type(exc).__name__,
                    ) from exc

    def close(self) -> None:
        with self._lock:
            if self._handler is not None:
                self._handler.close()
                self._handler = None

    def _get_handler(self) -> _NormalizedRotatingFileHandler:
        if self._handler is None:
            handler = _NormalizedRotatingFileHandler(
                filename=self.log_file,
                maxBytes=self._rotation_max_bytes,
                backupCount=self._rotation_backup_count,
                encoding="utf-8",
                delay=True,
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._handler = handler
        return self._handler


def _event_id(record: Any) -> str | None:
    if not isinstance(record, dict):
        return None
    value = record.get("normalized_event_id")
    return value if isinstance(value, str) else None
