"""Bounded binary JSONL reader with inode-aware reconciliation."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Callable

from .registry_models import (
    ApplyOutcome,
    CHECKPOINT_WINDOW_BYTES,
    ReaderState,
    RegistryConfig,
    ScanResult,
    SourceLineRecord,
)
from .registry_repository import VisitorRegistryRepository
from .registry_service import VisitorRegistryService
from .registry_telemetry import VisitorRegistryTelemetry


_CHECKPOINT_DOMAIN = b"visitor-registry-checkpoint-v1\0"
_READ_CHUNK_BYTES = 65_536


@dataclass
class _OpenedSource:
    path: Path
    identity: str
    is_active: bool
    size: int
    stream: BinaryIO


@dataclass(frozen=True)
class _LineRead:
    data: bytes | None
    offset_end: int
    has_newline: bool
    oversized: bool
    eof_without_data: bool
    interrupted: bool = False


class VisitorRegistryReader:
    def __init__(
        self,
        *,
        config: RegistryConfig,
        repository: VisitorRegistryRepository,
        service: VisitorRegistryService,
        telemetry: VisitorRegistryTelemetry,
    ):
        self.config = config
        self.repository = repository
        self.service = service
        self.telemetry = telemetry

    def scan(
        self,
        *,
        should_stop: Callable[[], bool] | None = None,
    ) -> ScanResult:
        stop = should_stop or (lambda: False)
        try:
            sources = self._discover_sources()
        except OSError as exc:
            self.telemetry.emit_once(
                "visitor_registry_source_permission_denied",
                key=type(exc).__name__,
                exception_type=type(exc).__name__,
            )
            return ScanResult(False, reason="source_discovery_error")

        discovered = {source.identity for source in sources}
        complete = True
        pending_partial = False
        reason: str | None = None
        processed_line_count = 0
        try:
            states = self.repository.get_reader_states()
            for source in sources:
                if stop():
                    return ScanResult(
                        False,
                        pending_partial,
                        "shutdown",
                        processed_line_count,
                    )
                try:
                    result = self._process_source(
                        source,
                        states.get(source.identity),
                        stop,
                    )
                except OSError as exc:
                    if isinstance(exc, PermissionError):
                        self.telemetry.emit_once(
                            "visitor_registry_source_permission_denied",
                            key=source.identity,
                            exception_type=type(exc).__name__,
                        )
                        source_reason = "source_permission_error"
                    else:
                        source_reason = "source_io_error"
                    result = ScanResult(
                        False,
                        reason=source_reason,
                    )
                complete = complete and result.complete
                pending_partial = (
                    pending_partial or result.pending_partial_line
                )
                processed_line_count += result.processed_line_count
                if reason is None and result.reason is not None:
                    reason = result.reason
        finally:
            for source in sources:
                try:
                    source.stream.close()
                except OSError:
                    pass

        states = self.repository.get_reader_states()
        for identity, state in states.items():
            if identity in discovered:
                continue
            if state.retired_completed:
                self.repository.delete_reader_state(identity)
                continue
            complete = False
            reason = reason or "old_inode_missing"
            if not state.missing_warning_emitted:
                self.telemetry.emit(
                    "visitor_registry_old_inode_missing",
                    "warning",
                    source_identity=identity,
                    source_offset=state.source_offset,
                )
                self.repository.mark_missing_warning(
                    identity,
                    self.service.now_iso(),
                )
        if processed_line_count:
            self.telemetry.emit(
                "visitor_registry_scan_completed",
                "debug",
                processed_line_count=processed_line_count,
                scan_complete=complete,
                pending_partial_line=pending_partial,
            )
        return ScanResult(
            complete,
            pending_partial,
            reason,
            processed_line_count,
        )

    def _discover_sources(self) -> list[_OpenedSource]:
        candidates = [
            (Path(f"{self.config.source_log_path}.{index}"), False)
            for index in range(
                self.config.source_backup_count,
                0,
                -1,
            )
        ]
        candidates.append((Path(self.config.source_log_path), True))
        result: list[_OpenedSource] = []
        by_identity: dict[str, int] = {}
        try:
            for path, is_active in candidates:
                try:
                    opened_pair = _open_regular_source(path)
                except FileNotFoundError:
                    continue
                if opened_pair is None:
                    continue
                stream, opened_stat = opened_pair
                try:
                    identity = source_identity(opened_stat)
                    opened = _OpenedSource(
                        path=path,
                        identity=identity,
                        is_active=is_active,
                        size=int(opened_stat.st_size),
                        stream=stream,
                    )
                    previous_index = by_identity.get(identity)
                    if previous_index is None:
                        by_identity[identity] = len(result)
                        result.append(opened)
                    elif (
                        is_active
                        and not result[previous_index].is_active
                    ):
                        result[previous_index].stream.close()
                        result[previous_index] = opened
                    else:
                        stream.close()
                except Exception:
                    stream.close()
                    raise
        except Exception:
            for opened in result:
                try:
                    opened.stream.close()
                except OSError:
                    pass
            raise
        return result

    def _process_source(
        self,
        source: _OpenedSource,
        state: ReaderState | None,
        stop: Callable[[], bool],
    ) -> ScanResult:
        stream = source.stream
        opened_size = int(os.fstat(stream.fileno()).st_size)
        offset = 0 if state is None else state.source_offset

        if (
            state is not None
            and state.retired_completed
            and source.is_active
        ):
            self._reset_source(
                source,
                opened_size,
                reason="retired_identity_reused",
                event="visitor_registry_source_reused",
            )
            state = None
            offset = 0
        elif state is not None and opened_size < offset:
            self._reset_source(
                source,
                opened_size,
                reason="source_truncated",
            )
            state = None
            offset = 0
        elif state is not None:
            try:
                checkpoint = source_checkpoint(stream, offset)
            except OSError:
                return ScanResult(False, reason="checkpoint_io_error")
            if (
                not isinstance(state.source_checkpoint, str)
                or not hmac.compare_digest(
                    state.source_checkpoint,
                    checkpoint,
                )
            ):
                self._reset_source(
                    source,
                    opened_size,
                    reason="checkpoint_mismatch",
                )
                state = None
                offset = 0

        stream.seek(offset)
        pending_partial = False
        processed_line_count = 0
        while True:
            if stop():
                return ScanResult(
                    False,
                    pending_partial,
                    "shutdown",
                    processed_line_count,
                )
            offset_start = stream.tell()
            line = _read_bounded_line(
                stream,
                self.config.max_line_bytes,
                should_stop=stop,
            )
            if line.interrupted:
                return ScanResult(
                    False,
                    pending_partial,
                    "shutdown",
                    processed_line_count,
                )
            if line.eof_without_data:
                break
            observed_size = int(os.fstat(stream.fileno()).st_size)
            if not line.has_newline:
                pending_partial = True
                try:
                    checkpoint = source_checkpoint(
                        stream,
                        offset_start,
                    )
                except OSError:
                    return ScanResult(
                        False,
                        True,
                        "checkpoint_io_error",
                        processed_line_count,
                    )
                self.repository.observe_source(
                    source_identity=source.identity,
                    source_path=str(source.path),
                    source_offset=offset_start,
                    last_observed_size=observed_size,
                    source_checkpoint=checkpoint,
                    retired_completed=False,
                    missing_warning_emitted=False,
                    now_utc=self.service.now_iso(),
                )
                break

            try:
                checkpoint = source_checkpoint(
                    stream,
                    line.offset_end,
                )
            except OSError:
                return ScanResult(
                    False,
                    pending_partial,
                    "checkpoint_io_error",
                    processed_line_count,
                )
            record = SourceLineRecord(
                source_identity=source.identity,
                source_path=str(source.path),
                source_offset_start=offset_start,
                source_offset_end=line.offset_end,
                last_observed_size=observed_size,
                source_checkpoint=checkpoint,
                processing_now=self.service.now_iso(),
            )
            processed_line_count += 1
            if line.oversized:
                self.telemetry.emit_once(
                    "visitor_registry_line_too_large",
                    key=source.identity,
                    source_identity=source.identity,
                    source_offset=offset_start,
                    max_line_bytes=self.config.max_line_bytes,
                )
                self.repository.apply_source_line(
                    record,
                    self.service._untracked_warning("line_too_large"),
                )
                continue
            raw_line = line.data
            if raw_line is None:
                raise RuntimeError("Complete bounded line has no data")
            try:
                decoded = raw_line[:-1].decode("utf-8")
            except UnicodeDecodeError:
                self.telemetry.emit_once(
                    "visitor_registry_invalid_utf8_line",
                    key=source.identity,
                    source_identity=source.identity,
                    source_offset=offset_start,
                )
                self.repository.apply_source_line(
                    record,
                    self.service._untracked_warning("invalid_utf8"),
                )
                continue
            try:
                event = strict_json_object(decoded)
            except ValueError:
                self.telemetry.emit_once(
                    "visitor_registry_invalid_json_line",
                    key=source.identity,
                    source_identity=source.identity,
                    source_offset=offset_start,
                )
                self.repository.apply_source_line(
                    record,
                    self.service._untracked_warning("invalid_json"),
                )
                continue

            try:
                decision = self.service.decide(event)
            except RecursionError:
                self.telemetry.emit_once(
                    "visitor_registry_invalid_json_line",
                    key=source.identity,
                    source_identity=source.identity,
                    source_offset=offset_start,
                )
                self.repository.apply_source_line(
                    record,
                    self.service._untracked_warning("invalid_json"),
                )
                continue
            result = self.repository.apply_source_line(record, decision)
            self._emit_result(result, decision, source, offset_start)

        final_size = int(os.fstat(stream.fileno()).st_size)
        final_offset = stream.tell()
        if pending_partial:
            return ScanResult(
                True,
                True,
                processed_line_count=processed_line_count,
            )
        try:
            checkpoint = source_checkpoint(stream, final_offset)
        except OSError:
            return ScanResult(
                False,
                reason="checkpoint_io_error",
                processed_line_count=processed_line_count,
            )
        self.repository.observe_source(
            source_identity=source.identity,
            source_path=str(source.path),
            source_offset=final_offset,
            last_observed_size=final_size,
            source_checkpoint=checkpoint,
            retired_completed=(
                not source.is_active and final_offset == final_size
            ),
            missing_warning_emitted=False,
            now_utc=self.service.now_iso(),
        )
        return ScanResult(
            True,
            processed_line_count=processed_line_count,
        )

    def _reset_source(
        self,
        source: _OpenedSource,
        observed_size: int,
        *,
        reason: str,
        event: str = "visitor_registry_source_restarted",
    ) -> None:
        checkpoint = source_checkpoint(source.stream, 0)
        self.repository.reset_source(
            source_identity=source.identity,
            source_path=str(source.path),
            observed_size=observed_size,
            checkpoint_at_zero=checkpoint,
            now_utc=self.service.now_iso(),
        )
        self.telemetry.emit(
            event,
            "warning",
            reason=reason,
            source_identity=source.identity,
        )

    def _emit_result(
        self,
        result,
        decision,
        source: _OpenedSource,
        offset_start: int,
    ) -> None:
        if result.outcome is ApplyOutcome.STORED:
            self.telemetry.emit(
                (
                    "visitor_registry_device_created"
                    if result.device_created
                    else "visitor_registry_device_updated"
                ),
                "debug",
                device_id=result.device_id,
            )
            self.telemetry.emit(
                "visitor_registry_snapshot_stored",
                "debug",
                snapshot_id=result.snapshot_id,
                device_id=result.device_id,
            )
        elif result.outcome is ApplyOutcome.SKIPPED:
            self.telemetry.emit(
                "visitor_registry_snapshot_skipped",
                "warning",
                snapshot_id=result.snapshot_id,
                skip_reason=result.skip_reason,
            )
        elif result.outcome is ApplyOutcome.DUPLICATE:
            self.telemetry.emit(
                "visitor_registry_duplicate_ignored",
                "debug",
                snapshot_id=result.snapshot_id,
            )
        elif result.outcome is ApplyOutcome.CONFLICT:
            self.telemetry.emit_once(
                "visitor_registry_snapshot_id_conflict",
                "error",
                key=result.snapshot_id or "",
                snapshot_id=result.snapshot_id,
                source_identity=source.identity,
                source_offset=offset_start,
            )
        elif decision.warning_reason is not None:
            self.telemetry.emit(
                "visitor_registry_snapshot_skipped",
                "warning",
                skip_reason=decision.warning_reason,
                source_identity=source.identity,
                source_offset=offset_start,
            )


def _open_regular_source(
    path: Path,
) -> tuple[BinaryIO, os.stat_result] | None:
    """Open a journal candidate without blocking on a FIFO."""
    candidate_stat = os.lstat(path)
    if (
        not stat.S_ISREG(candidate_stat.st_mode)
        and not stat.S_ISLNK(candidate_stat.st_mode)
    ):
        return None

    flags = os.O_RDONLY
    for flag_name in ("O_NONBLOCK", "O_CLOEXEC", "O_BINARY"):
        flags |= int(getattr(os, flag_name, 0))
    try:
        descriptor = os.open(path, flags)
    except IsADirectoryError:
        return None
    except OSError:
        try:
            target_stat = os.stat(path)
        except OSError:
            raise
        if not stat.S_ISREG(target_stat.st_mode):
            return None
        raise

    try:
        opened_stat = os.fstat(descriptor)
        if not stat.S_ISREG(opened_stat.st_mode):
            os.close(descriptor)
            return None
        stream = os.fdopen(descriptor, "rb", closefd=True)
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise
    return stream, opened_stat


def source_identity(stat_result: os.stat_result) -> str:
    return f"{int(stat_result.st_dev)}:{int(stat_result.st_ino)}"


def source_checkpoint(stream: BinaryIO, offset: int) -> str:
    if offset < 0:
        raise ValueError("Checkpoint offset must not be negative")
    original = stream.tell()
    try:
        size = int(os.fstat(stream.fileno()).st_size)
        if size < offset:
            raise OSError("Source became shorter than checkpoint offset")
        prefix_length = min(CHECKPOINT_WINDOW_BYTES, offset)
        stream.seek(0)
        prefix = stream.read(prefix_length)
        if len(prefix) != prefix_length:
            raise OSError("Checkpoint prefix could not be read")
        tail_start = max(prefix_length, offset - CHECKPOINT_WINDOW_BYTES)
        tail_length = offset - tail_start
        stream.seek(tail_start)
        tail = stream.read(tail_length)
        if len(tail) != tail_length:
            raise OSError("Checkpoint tail could not be read")
        digest = hashlib.sha256()
        digest.update(_CHECKPOINT_DOMAIN)
        digest.update(str(offset).encode("ascii"))
        digest.update(prefix_length.to_bytes(4, "big"))
        digest.update(prefix)
        digest.update(tail_length.to_bytes(4, "big"))
        digest.update(tail)
        return digest.hexdigest()
    finally:
        stream.seek(original)


def strict_json_object(text: str) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise ValueError(f"Invalid JSON constant: {value}")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
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
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    if _contains_unsafe_json_scalar(value):
        raise ValueError("JSON contains an unsafe scalar value")
    return value


def _contains_unsafe_json_scalar(value: Any) -> bool:
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, str):
            if any(
                0xD800 <= ord(character) <= 0xDFFF
                for character in current
            ):
                return True
        elif isinstance(current, float):
            if not math.isfinite(current):
                return True
        elif isinstance(current, list):
            pending.extend(current)
        elif isinstance(current, dict):
            pending.extend(current.keys())
            pending.extend(current.values())
    return False


def _read_bounded_line(
    stream: BinaryIO,
    max_line_bytes: int,
    *,
    should_stop: Callable[[], bool] | None = None,
) -> _LineRead:
    collected = bytearray()
    oversized = False
    saw_data = False
    while True:
        if should_stop is not None and should_stop():
            return _LineRead(
                None,
                stream.tell(),
                False,
                oversized,
                False,
                True,
            )
        chunk = stream.read(_READ_CHUNK_BYTES)
        if not chunk:
            return _LineRead(
                None if oversized else bytes(collected),
                stream.tell(),
                False,
                oversized,
                not saw_data,
            )
        saw_data = True
        newline = chunk.find(b"\n")
        consumed = len(chunk) if newline < 0 else newline + 1
        remainder = len(chunk) - consumed
        if remainder:
            stream.seek(-remainder, os.SEEK_CUR)
        if not oversized:
            if len(collected) + consumed > max_line_bytes:
                oversized = True
                collected.clear()
            else:
                collected.extend(chunk[:consumed])
        if newline >= 0:
            return _LineRead(
                None if oversized else bytes(collected),
                stream.tell(),
                True,
                oversized,
                False,
            )
