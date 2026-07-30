"""Thread-safe rotating JSONL writer for Visitor Snapshot data events."""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler
from typing import Any


LOGGER_NAME = "captive_portal.visitor_snapshots"
_HANDLER_MARKER = "_captive_portal_visitor_snapshot"
_CONFIG_LOCK = threading.RLock()


class VisitorSnapshotWriteError(OSError):
    """The dedicated data journal could not persist an event."""


class _VisitorSnapshotRotatingFileHandler(RotatingFileHandler):
    def _open(self):
        stream = super()._open()
        if os.name == "posix":
            os.chmod(self.baseFilename, 0o640)
        return stream

    def handleError(self, record: logging.LogRecord) -> None:
        error = sys.exc_info()[1]
        if error is not None:
            raise error
        raise OSError("Unknown Visitor Snapshot journal failure")


class VisitorSnapshotWriter:
    def __init__(
        self,
        log_file: str,
        *,
        rotation_max_bytes: int,
        rotation_backup_count: int,
    ):
        self.log_file = str(log_file)
        self.rotation_max_bytes = int(rotation_max_bytes)
        self.rotation_backup_count = int(rotation_backup_count)
        self.available = False
        self._logger = logging.getLogger(LOGGER_NAME)
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        self._lock = threading.RLock()
        self._handler: _VisitorSnapshotRotatingFileHandler | None = None

    def initialize(self) -> bool:
        with self._lock:
            if self.available and self._handler is not None:
                return True
            try:
                handler = _VisitorSnapshotRotatingFileHandler(
                    filename=self.log_file,
                    maxBytes=self.rotation_max_bytes,
                    backupCount=self.rotation_backup_count,
                    encoding="utf-8",
                    delay=False,
                )
                setattr(handler, _HANDLER_MARKER, True)
                handler.setFormatter(logging.Formatter("%(message)s"))
                with _CONFIG_LOCK:
                    for existing in list(self._logger.handlers):
                        if getattr(existing, _HANDLER_MARKER, False):
                            self._logger.removeHandler(existing)
                            try:
                                existing.close()
                            except Exception:
                                pass
                    self._logger.addHandler(handler)
                self._handler = handler
                self.available = True
                return True
            except Exception:
                self.available = False
                self._handler = None
                return False

    def write(self, record: dict[str, Any]) -> None:
        try:
            line = json.dumps(
                record,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
            line.encode("utf-8", errors="strict")
        except Exception as exc:
            raise VisitorSnapshotWriteError(
                "Visitor Snapshot event is not strict JSON"
            ) from exc

        with self._lock:
            if not self.available or self._handler is None:
                raise VisitorSnapshotWriteError(
                    "Visitor Snapshot writer is unavailable"
                )
            log_record = logging.LogRecord(
                name=LOGGER_NAME,
                level=logging.INFO,
                pathname=__file__,
                lineno=0,
                msg=line,
                args=(),
                exc_info=None,
            )
            try:
                self._handler.emit(log_record)
            except Exception as exc:
                self.available = False
                raise VisitorSnapshotWriteError(
                    "Visitor Snapshot journal write failed"
                ) from exc

    def close(self) -> None:
        with self._lock:
            handler = self._handler
            self._handler = None
            self.available = False
            if handler is None:
                return
            with _CONFIG_LOCK:
                try:
                    self._logger.removeHandler(handler)
                except Exception:
                    pass
            try:
                handler.close()
            except Exception:
                pass
