from __future__ import annotations

import json
import os
import threading
from logging.handlers import RotatingFileHandler
import logging
from typing import Any
import uuid


class JournalWriteError(RuntimeError):
    pass


class _StrictRotatingFileHandler(RotatingFileHandler):
    def _open(self):
        stream = super()._open()
        # enforce mode; if fails, raise
        if os.name == "posix":
            try:
                os.chmod(self.baseFilename, 0o640)
            except OSError as exc:
                raise JournalWriteError(f"chmod failed: {exc}") from exc
        return stream

    def handleError(self, record: logging.LogRecord) -> None:
        # Always raise; do not swallow
        err = None
        try:
            exc_info = logging.sys.exc_info()
            err = exc_info[1]
        except Exception:
            pass
        if err:
            raise JournalWriteError(f"handler error: {err}") from err
        raise JournalWriteError("handler error")


class JournalWriter:
    def __init__(self, filename: str, *, max_bytes: int = 52428800, backup_count: int = 20):
        self._lock = threading.RLock()
        # unique logger per instance (UUID) to avoid shared handlers
        logger_name = f"captive_portal.pending_sessions.journal.{uuid.uuid4().hex}"
        self._logger = logging.getLogger(logger_name)
        self._logger.propagate = False
        self._logger.setLevel(logging.INFO)

        # do not remove handlers from other loggers; this instance owns its handler
        handler = _StrictRotatingFileHandler(filename=filename, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(message)s"))
        self._logger.addHandler(handler)
        self._handler = handler
        self._closed = False
        self._filename = os.path.abspath(filename)

    def write_and_flush(self, event: dict[str, Any], *, fsync: bool = False) -> None:
        try:
            payload = json.dumps(event, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        except Exception as exc:
            raise JournalWriteError(f"serialize failed: {exc}") from exc

        with self._lock:
            if self._closed:
                raise JournalWriteError("writer closed")
            try:
                self._logger.info(payload)
                self._handler.flush()
                if fsync:
                    stream = getattr(self._handler, "stream", None)
                    if stream is None:
                        raise JournalWriteError("no underlying file stream for fsync")
                    try:
                        fd = stream.fileno()
                        os.fsync(fd)
                    except Exception as exc:
                        raise JournalWriteError(f"fsync failed: {exc}") from exc
            except JournalWriteError:
                raise
            except Exception as exc:
                raise JournalWriteError(f"write failed: {exc}") from exc

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            try:
                handler = getattr(self, "_handler", None)
                if handler is not None:
                    try:
                        self._logger.removeHandler(handler)
                    except Exception:
                        pass
                    try:
                        handler.close()
                    except Exception:
                        pass
            finally:
                self._closed = True