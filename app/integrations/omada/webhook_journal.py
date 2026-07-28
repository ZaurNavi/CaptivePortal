"""Synchronous, rotating JSONL journal for accepted Omada webhooks."""

import json
import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler
from typing import Any


DEFAULT_ROTATION_MAX_BYTES = 52_428_800
DEFAULT_ROTATION_BACKUP_COUNT = 10


class _WebhookRotatingFileHandler(RotatingFileHandler):
    def _open(self):
        stream = super()._open()
        if os.name == "posix":
            os.chmod(self.baseFilename, 0o640)
        return stream

    def handleError(self, record: logging.LogRecord) -> None:
        error = sys.exc_info()[1]
        if error is not None:
            raise error
        raise OSError("Unknown Omada webhook journal failure")


class OmadaWebhookJournal:
    """Append one UTF-8 JSON object per successfully persisted delivery."""

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
        self._handler: _WebhookRotatingFileHandler | None = None

    def append(self, record: dict[str, Any]) -> None:
        line = json.dumps(
            record,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
        )
        with self._lock:
            handler = self._get_handler()
            log_record = logging.LogRecord(
                name="captive_portal.omada_webhook",
                level=logging.INFO,
                pathname=__file__,
                lineno=0,
                msg=line,
                args=(),
                exc_info=None,
            )
            handler.emit(log_record)

    def close(self) -> None:
        with self._lock:
            if self._handler is not None:
                self._handler.close()
                self._handler = None

    def _get_handler(self) -> _WebhookRotatingFileHandler:
        if self._handler is None:
            handler = _WebhookRotatingFileHandler(
                filename=self.log_file,
                maxBytes=self._rotation_max_bytes,
                backupCount=self._rotation_backup_count,
                encoding="utf-8",
                delay=True,
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._handler = handler
        return self._handler
