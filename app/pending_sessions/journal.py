from __future__ import annotations

import json
import logging
import os
import sys
import threading
import uuid
from logging.handlers import RotatingFileHandler
from typing import Any


class JournalWriteError(RuntimeError):
    pass


class _StrictRotatingFileHandler(RotatingFileHandler):
    def _open(self):
        stream = super()._open()
        if os.name == "posix":
            try:
                os.chmod(self.baseFilename, 0o640)
            except OSError as exc:
                stream.close()
                raise JournalWriteError(f"chmod failed: {exc}") from exc
        return stream

    def handleError(self, record: logging.LogRecord) -> None:
        error = sys.exc_info()[1]
        if error is not None:
            raise JournalWriteError(f"handler error: {error}") from error
        raise JournalWriteError("handler error")


class JournalWriter:
    def __init__(
        self,
        filename: str,
        *,
        max_bytes: int = 52_428_800,
        backup_count: int = 20,
    ) -> None:
        self._lock = threading.RLock()
        self._closed = False
        self._logger = logging.getLogger(
            f"captive_portal.pending_sessions.journal.{uuid.uuid4().hex}"
        )
        self._logger.propagate = False
        self._logger.setLevel(logging.INFO)
        self._handler = _StrictRotatingFileHandler(
            filename=filename,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        self._handler.setFormatter(logging.Formatter("%(message)s"))
        self._logger.addHandler(self._handler)

    def write_and_flush(
        self,
        event: dict[str, Any],
        *,
        fsync: bool = False,
    ) -> None:
        try:
            payload = json.dumps(
                event,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise JournalWriteError(f"serialize failed: {exc}") from exc

        with self._lock:
            if self._closed:
                raise JournalWriteError("writer closed")
            try:
                self._logger.info(payload)
                self._handler.flush()
                if fsync:
                    stream = self._handler.stream
                    if stream is None:
                        raise JournalWriteError("journal stream is unavailable")
                    os.fsync(stream.fileno())
            except JournalWriteError:
                raise
            except Exception as exc:
                raise JournalWriteError(f"write failed: {exc}") from exc

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._logger.removeHandler(self._handler)
            self._handler.close()
            self._closed = True
