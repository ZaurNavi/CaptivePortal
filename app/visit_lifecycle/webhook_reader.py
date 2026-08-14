"""Durable bounded reader for normalized Omada offline events."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import stat
import threading
import time
from dataclasses import dataclass
from ipaddress import ip_address
from pathlib import Path
from typing import Any, BinaryIO, Callable

from app.common.mac import format_mac_colon
from app.integrations.omada.webhook_journal import (
    DEFAULT_ROTATION_BACKUP_COUNT,
)

from .models import (
    MAX_SQLITE_INTEGER,
    OfflineEvidence,
    ReaderCheckpoint,
    ReaderProgress,
    VisitLifecycleConfig,
    VisitReaderState,
    VisitStorageError,
    VisitValidationError,
    normalize_utc,
    utc_now,
)
from .repository import VisitRepository
from .service import VisitLifecycleService
from .telemetry import VisitTelemetry


CHECKPOINT_WINDOW_BYTES = 2_048
READ_CHUNK_BYTES = 64 * 1_024
CHECKPOINT_DOMAIN = b"visit-webhook-reader-v1\0"


@dataclass(frozen=True)
class _OpenedSource:
    path: Path
    identity: str
    is_active: bool
    stream: BinaryIO


@dataclass
class _Budget:
    lines: int
    bytes: int
    deadline: float


@dataclass(frozen=True)
class _Line:
    data: bytes | None
    offset_end: int
    has_newline: bool
    oversized: bool
    eof: bool
    stopped: bool = False
    budget_exhausted: bool = False


class VisitLifecycleWebhookReader:
    """Read normalized JSONL safely and persist evidence/checkpoints."""

    def __init__(
        self,
        *,
        config: VisitLifecycleConfig,
        repository: VisitRepository,
        service: VisitLifecycleService,
        telemetry: VisitTelemetry,
        now_factory: Callable[[], str] = utc_now,
        monotonic: Callable[[], float] = time.monotonic,
        health_callback: Callable[[bool], None] | None = None,
        backup_count: int = DEFAULT_ROTATION_BACKUP_COUNT,
    ):
        self.config = config
        self.repository = repository
        self.service = service
        self.telemetry = telemetry
        self._now = now_factory
        self._monotonic = monotonic
        self._health_callback = health_callback
        self._backup_count = max(0, int(backup_count))
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lifecycle_lock = threading.Lock()

    @property
    def running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def start(self) -> bool:
        with self._lifecycle_lock:
            if self.running:
                return False
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="visit_webhook_reader",
                daemon=True,
            )
            self._thread.start()
            return True

    def stop(self, timeout_seconds: float) -> bool:
        self._stop_event.set()
        thread = self._thread
        if thread is None:
            return True
        thread.join(max(0.0, float(timeout_seconds)))
        return not thread.is_alive()

    def scan_once(self) -> bool:
        started = self._monotonic()
        budget = _Budget(
            lines=self.config.reader_max_lines_per_scan,
            bytes=self.config.reader_max_bytes_per_scan,
            deadline=started + self.config.reader_max_duration_seconds,
        )
        processed = 0
        complete = True
        sources: list[_OpenedSource] = []
        try:
            sources = self._discover_sources()
            discovered = {source.identity for source in sources}
            states = self.repository.get_reader_states()
            for source in sources:
                if self._bounded_stop(budget):
                    complete = False
                    break
                line_count, source_complete = self._process_source(
                    source,
                    states.get(source.identity),
                    budget,
                )
                processed += line_count
                complete = complete and source_complete
            self._reconcile_missing(discovered)
            self.service.retry_pending(now_utc=self._now())
            self.telemetry.emit(
                "visit.reader_scan_completed",
                processed_line_count=processed,
                scan_complete=complete,
                duration_ms=int((self._monotonic() - started) * 1000),
            )
            if self._health_callback is not None:
                self._health_callback(True)
            return complete
        except Exception as exc:
            fields: dict[str, Any] = {
                "error_type": type(exc).__name__,
                "operation": "reader",
                "attempt": 1,
                "retry_exhausted": False,
                "wait_ms": int((self._monotonic() - started) * 1000),
            }
            if isinstance(exc, VisitStorageError):
                fields["storage_category"] = exc.category.value
                fields["lock_wait_ms"] = exc.lock_wait_ms
            self.telemetry.emit(
                "visit.reader_scan_failed",
                "error",
                **fields,
            )
            if self._health_callback is not None:
                self._health_callback(False)
            return False
        finally:
            for source in sources:
                try:
                    source.stream.close()
                except OSError:
                    pass

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self.scan_once()
            if self._stop_event.wait(self.config.scan_interval_seconds):
                return

    def _discover_sources(self) -> list[_OpenedSource]:
        candidates = [
            (Path(f"{self.config.webhook_source}.{index}"), False)
            for index in range(self._backup_count, 0, -1)
        ]
        candidates.append((Path(self.config.webhook_source), True))
        result: list[_OpenedSource] = []
        by_identity: dict[str, int] = {}
        try:
            for path, is_active in candidates:
                try:
                    opened = _open_regular_source(path)
                except FileNotFoundError:
                    continue
                if opened is None:
                    continue
                stream, opened_stat = opened
                source = _OpenedSource(
                    path=path,
                    identity=_source_identity(opened_stat),
                    is_active=is_active,
                    stream=stream,
                )
                previous = by_identity.get(source.identity)
                if previous is None:
                    by_identity[source.identity] = len(result)
                    result.append(source)
                elif is_active and not result[previous].is_active:
                    result[previous].stream.close()
                    result[previous] = source
                else:
                    stream.close()
        except Exception:
            for source in result:
                source.stream.close()
            raise
        return result

    def _process_source(
        self,
        source: _OpenedSource,
        state: VisitReaderState | None,
        budget: _Budget,
    ) -> tuple[int, bool]:
        stream = source.stream
        observed_size = int(os.fstat(stream.fileno()).st_size)
        offset = 0 if state is None else state.source_offset
        reset_reason: str | None = None
        if state is not None and state.missing_warning_emitted:
            reset_reason = "source_reappeared"
        elif state is not None and state.retired_completed and source.is_active:
            reset_reason = "retired_identity_reused"
        elif state is not None and observed_size < offset:
            reset_reason = "source_truncated"
        elif state is not None:
            try:
                current = _checkpoint(stream, offset)
            except OSError:
                return 0, False
            if not _checkpoint_matches(state, current):
                reset_reason = "checkpoint_mismatch"
        if reset_reason is not None:
            offset = 0
            checkpoint = _checkpoint(stream, 0)
            self.repository.reset_reader_source(
                _progress(source, 0, observed_size, checkpoint),
                now_utc=self._now(),
            )
            self.telemetry.emit(
                "visit.reader_source_restarted",
                "warning",
                reason=reset_reason,
                source_identity=source.identity,
            )

        stream.seek(offset)
        processed = 0
        while not self._bounded_stop(budget):
            offset_start = stream.tell()
            line = _read_bounded_line(
                stream,
                max_line_bytes=self.config.max_line_bytes,
                max_scan_bytes=budget.bytes,
                should_stop=lambda: self._bounded_stop(budget),
            )
            consumed = line.offset_end - offset_start
            budget.bytes = max(0, budget.bytes - consumed)
            if line.stopped or line.budget_exhausted:
                return processed, False
            if line.eof:
                break
            observed_size = int(os.fstat(stream.fileno()).st_size)
            if not line.has_newline:
                checkpoint = _checkpoint(stream, offset_start)
                self.repository.observe_reader_progress(
                    _progress(
                        source,
                        offset_start,
                        observed_size,
                        checkpoint,
                    ),
                    now_utc=self._now(),
                )
                return processed, False
            checkpoint = _checkpoint(stream, line.offset_end)
            progress = _progress(
                source,
                line.offset_end,
                observed_size,
                checkpoint,
                source_offset_start=offset_start,
            )
            evidence: OfflineEvidence | None = None
            if line.oversized:
                self.telemetry.emit(
                    "visit.offline_invalid",
                    "warning",
                    reason="line_too_large",
                    source_identity=source.identity,
                    source_offset=offset_start,
                )
            else:
                try:
                    assert line.data is not None
                    record = _strict_json_object(
                        line.data[:-1].decode("utf-8")
                    )
                    evidence = _offline_evidence(record)
                except (UnicodeError, ValueError, RecursionError):
                    self.telemetry.emit(
                        "visit.offline_invalid",
                        "warning",
                        reason="invalid_normalized_json",
                        source_identity=source.identity,
                        source_offset=offset_start,
                    )
            self.service.process_journal_line(
                progress=progress,
                evidence=evidence,
                now_utc=self._now(),
            )
            processed += 1
            budget.lines -= 1

        final_size = int(os.fstat(stream.fileno()).st_size)
        final_offset = stream.tell()
        if final_offset == final_size:
            checkpoint = _checkpoint(stream, final_offset)
            self.repository.observe_reader_progress(
                _progress(
                    source,
                    final_offset,
                    final_size,
                    checkpoint,
                    retired_completed=not source.is_active,
                ),
                now_utc=self._now(),
            )
            return processed, True
        return processed, False

    def _reconcile_missing(self, discovered: set[str]) -> None:
        for identity, state in self.repository.get_reader_states().items():
            if identity in discovered:
                continue
            if state.retired_completed:
                self.repository.delete_reader_state(identity)
            elif not state.missing_warning_emitted:
                self.telemetry.emit(
                    "visit.reader_source_missing",
                    "warning",
                    source_identity=identity,
                    source_offset=state.source_offset,
                )
                self.repository.mark_reader_source_missing(
                    identity,
                    now_utc=self._now(),
                )

    def _bounded_stop(self, budget: _Budget) -> bool:
        return (
            self._stop_event.is_set()
            or budget.lines <= 0
            or budget.bytes <= 0
            or self._monotonic() >= budget.deadline
        )


def _offline_evidence(record: dict[str, Any]) -> OfflineEvidence | None:
    if record.get("event") != "omada.client_offline":
        return None
    event_id = _optional_text(record.get("normalized_event_id"))
    invalid_reason = None if event_id is not None else "invalid_event_id"

    site_id = _optional_text(record.get("site_id"))
    if (
        record.get("site_resolution_status") != "resolved"
        or site_id is None
    ):
        invalid_reason = invalid_reason or "site_unresolved"

    client_mac = _optional_mac(record.get("client_mac"))
    if client_mac is None:
        invalid_reason = invalid_reason or "invalid_client_mac"

    controller_at = _optional_utc(record.get("controller_timestamp"))
    received_at = _optional_utc(record.get("received_at"))
    if controller_at is None and received_at is None:
        invalid_reason = invalid_reason or "invalid_time"

    return OfflineEvidence(
        event_id=event_id,
        site_id=site_id,
        client_mac=client_mac,
        controller_event_at=controller_at,
        received_at=received_at,
        client_ip=_optional_ip(record.get("client_ip")),
        ssid=_optional_text(record.get("ssid")),
        ap_mac=_optional_mac(record.get("ap_mac")),
        reported_connected_seconds=_optional_nonnegative_int(
            record.get("reported_connected_seconds")
        ),
        reported_traffic_total_bytes=_optional_nonnegative_int(
            record.get("reported_traffic_bytes_estimate")
        ),
        invalid_reason=invalid_reason,
    )


def _optional_text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _optional_mac(value: Any) -> str | None:
    try:
        return format_mac_colon(value) if isinstance(value, str) else None
    except (TypeError, ValueError):
        return None


def _optional_ip(value: Any) -> str | None:
    try:
        return str(ip_address(value)) if isinstance(value, str) else None
    except ValueError:
        return None


def _optional_utc(value: Any) -> str | None:
    try:
        return normalize_utc(value, "event_time") if isinstance(value, str) else None
    except VisitValidationError:
        return None


def _optional_nonnegative_int(value: Any) -> int | None:
    if type(value) is int and 0 <= value <= MAX_SQLITE_INTEGER:
        return value
    return None


def _open_regular_source(
    path: Path,
) -> tuple[BinaryIO, os.stat_result] | None:
    candidate = os.lstat(path)
    if not stat.S_ISREG(candidate.st_mode) and not stat.S_ISLNK(
        candidate.st_mode
    ):
        return None
    flags = os.O_RDONLY
    for name in ("O_NONBLOCK", "O_CLOEXEC", "O_BINARY"):
        flags |= int(getattr(os, name, 0))
    descriptor = os.open(path, flags)
    try:
        opened_stat = os.fstat(descriptor)
        if not stat.S_ISREG(opened_stat.st_mode):
            os.close(descriptor)
            return None
        return os.fdopen(descriptor, "rb", closefd=True), opened_stat
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise


def _source_identity(value: os.stat_result) -> str:
    return f"{int(value.st_dev)}:{int(value.st_ino)}"


def _checkpoint(stream: BinaryIO, offset: int) -> ReaderCheckpoint:
    original = stream.tell()
    try:
        if int(os.fstat(stream.fileno()).st_size) < offset:
            raise OSError("Source is shorter than checkpoint")
        prefix_length = min(CHECKPOINT_WINDOW_BYTES, offset)
        stream.seek(0)
        prefix = stream.read(prefix_length)
        tail_start = max(prefix_length, offset - CHECKPOINT_WINDOW_BYTES)
        tail_length = offset - tail_start
        stream.seek(tail_start)
        tail = stream.read(tail_length)
        if len(prefix) != prefix_length or len(tail) != tail_length:
            raise OSError("Checkpoint bytes could not be read")
        digest = hashlib.sha256()
        digest.update(CHECKPOINT_DOMAIN)
        digest.update(str(offset).encode("ascii"))
        digest.update(prefix)
        digest.update(tail)
        return ReaderCheckpoint(
            checkpoint_offset=offset,
            checkpoint_length=prefix_length + tail_length,
            checkpoint_sha256=digest.hexdigest(),
        )
    finally:
        stream.seek(original)


def _checkpoint_matches(
    state: VisitReaderState,
    actual: ReaderCheckpoint,
) -> bool:
    return (
        state.checkpoint_offset == actual.checkpoint_offset
        and state.checkpoint_length == actual.checkpoint_length
        and isinstance(state.checkpoint_sha256, str)
        and hmac.compare_digest(
            state.checkpoint_sha256,
            actual.checkpoint_sha256,
        )
    )


def _progress(
    source: _OpenedSource,
    offset: int,
    observed_size: int,
    checkpoint: ReaderCheckpoint,
    *,
    retired_completed: bool = False,
    source_offset_start: int | None = None,
) -> ReaderProgress:
    return ReaderProgress(
        source_identity=source.identity,
        source_path=str(source.path),
        source_offset=offset,
        last_observed_size=observed_size,
        checkpoint=checkpoint,
        retired_completed=retired_completed,
        source_offset_start=source_offset_start,
    )


def _read_bounded_line(
    stream: BinaryIO,
    *,
    max_line_bytes: int,
    max_scan_bytes: int,
    should_stop: Callable[[], bool],
) -> _Line:
    collected = bytearray()
    oversized = False
    saw_data = False
    remaining = max_scan_bytes
    while remaining > 0:
        if should_stop():
            return _Line(None, stream.tell(), False, oversized, False, True)
        chunk = stream.read(min(READ_CHUNK_BYTES, remaining))
        if not chunk:
            return _Line(
                None if oversized else bytes(collected),
                stream.tell(),
                False,
                oversized,
                not saw_data,
            )
        saw_data = True
        remaining -= len(chunk)
        newline = chunk.find(b"\n")
        selected = chunk if newline < 0 else chunk[: newline + 1]
        if newline >= 0:
            stream.seek(-(len(chunk) - len(selected)), os.SEEK_CUR)
        if not oversized:
            available = max_line_bytes + 1 - len(collected)
            collected.extend(selected[:available])
            oversized = len(collected) > max_line_bytes
            if oversized:
                collected.clear()
        if newline >= 0:
            return _Line(
                None if oversized else bytes(collected),
                stream.tell(),
                True,
                oversized,
                False,
            )
    return _Line(
        None,
        stream.tell(),
        False,
        oversized,
        False,
        budget_exhausted=True,
    )


def _strict_json_object(text: str) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise ValueError(value)

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    try:
        value = json.loads(
            text,
            parse_constant=reject_constant,
            object_pairs_hook=unique_object,
        )
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise ValueError("Malformed strict JSON") from exc
    if not isinstance(value, dict) or _unsafe_json_value(value):
        raise ValueError("JSON root/value is unsafe")
    return value


def _unsafe_json_value(value: Any) -> bool:
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, str) and any(
            0xD800 <= ord(character) <= 0xDFFF
            for character in current
        ):
            return True
        if isinstance(current, float) and not math.isfinite(current):
            return True
        if isinstance(current, list):
            pending.extend(current)
        elif isinstance(current, dict):
            pending.extend(current.keys())
            pending.extend(current.values())
    return False
