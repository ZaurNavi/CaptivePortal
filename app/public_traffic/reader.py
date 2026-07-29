"""Binary JSONL reader with inode-aware reconciliation."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from app.integrations.omada.webhook_journal import (
    DEFAULT_ROTATION_BACKUP_COUNT,
)

from .repository import PublicTrafficRepository
from .service import PublicTrafficService


CHECKPOINT_WINDOW_BYTES = 2048


@dataclass(frozen=True)
class SourceFile:
    path: Path
    identity: str
    is_active: bool
    size: int


class PublicTrafficReader:
    def __init__(
        self,
        *,
        source_path: str,
        repository: PublicTrafficRepository,
        service: PublicTrafficService,
        logger: logging.Logger,
        backup_count: int = DEFAULT_ROTATION_BACKUP_COUNT,
    ):
        self.source_path = Path(source_path)
        self.repository = repository
        self.service = service
        self.logger = logger
        self.backup_count = max(0, int(backup_count))

    def scan(self) -> bool:
        sources = self._discover_sources()
        discovered = {source.identity for source in sources}
        states = self.repository.get_reader_states()
        complete = True

        for source in sources:
            complete = (
                self._process_source(
                    source,
                    states.get(source.identity),
                )
                and complete
            )

        states = self.repository.get_reader_states()
        for identity, state in states.items():
            if identity in discovered:
                continue
            if state.retired_completed:
                self.repository.delete_reader_state(identity)
                continue
            if state.missing_warning_emitted:
                continue
            self.logger.warning(
                "public_traffic_old_inode_not_found "
                "source_identity=%s source_offset=%s",
                identity,
                state.source_offset,
            )
            self.repository.mark_missing_warning_emitted(
                identity,
                self.service.now_iso(),
            )
        return complete

    def _discover_sources(self) -> list[SourceFile]:
        paths = [
            (Path(f"{self.source_path}.{index}"), False)
            for index in range(self.backup_count, 0, -1)
        ]
        paths.append((self.source_path, True))
        result: list[SourceFile] = []
        seen_identities: set[str] = set()
        for path, is_active in paths:
            try:
                stat_result = path.stat()
            except FileNotFoundError:
                continue
            identity = _source_identity(stat_result)
            if identity in seen_identities:
                continue
            seen_identities.add(identity)
            result.append(
                SourceFile(
                    path=path,
                    identity=identity,
                    is_active=is_active,
                    size=int(stat_result.st_size),
                )
            )
        return result

    def _process_source(self, source, state) -> bool:
        if state is not None and state.missing_warning_emitted:
            self.repository.reset_source_after_reappearance(
                source_identity=source.identity,
                source_path=str(source.path),
                observed_size=source.size,
                now_utc=self.service.now_iso(),
            )
            state = None
        offset = 0 if state is None else state.source_offset
        if source.size < offset:
            self.logger.warning(
                "public_traffic_source_truncated "
                "source_identity=%s old_offset=%s new_size=%s",
                source.identity,
                offset,
                source.size,
            )
            self.repository.reset_source_after_truncate(
                source_identity=source.identity,
                source_path=str(source.path),
                observed_size=source.size,
                now_utc=self.service.now_iso(),
            )
            state = None
            offset = 0

        try:
            stream = source.path.open("rb")
        except FileNotFoundError:
            return False
        with stream:
            opened_stat = os.fstat(stream.fileno())
            if _source_identity(opened_stat) != source.identity:
                self.logger.info(
                    "public_traffic_source_rotated path=%s",
                    source.path,
                )
                return False
            if (
                state is not None
                and state.retired_completed
                and source.is_active
            ):
                self._reset_rewritten_source(
                    source,
                    reason="retired_identity_reused",
                )
                state = None
                offset = 0
            elif state is not None and offset > 0:
                current_checkpoint = _source_checkpoint(
                    stream,
                    offset,
                )
                if (
                    not isinstance(state.source_checkpoint, str)
                    or not hmac.compare_digest(
                        state.source_checkpoint,
                        current_checkpoint,
                    )
                ):
                    self._reset_rewritten_source(
                        source,
                        reason="checkpoint_mismatch",
                    )
                    state = None
                    offset = 0
            stream.seek(offset)
            incomplete = False
            while True:
                offset_start = stream.tell()
                raw_line = stream.readline()
                if not raw_line:
                    break
                offset_end = stream.tell()
                observed_size = int(os.fstat(stream.fileno()).st_size)
                if not raw_line.endswith(b"\n"):
                    incomplete = True
                    source_checkpoint = _source_checkpoint(
                        stream,
                        offset_start,
                    )
                    self.repository.observe_source(
                        source_identity=source.identity,
                        source_path=str(source.path),
                        source_offset=offset_start,
                        source_checkpoint=source_checkpoint,
                        observed_size=observed_size,
                        retired_completed=False,
                        now_utc=self.service.now_iso(),
                    )
                    break
                source_checkpoint = _source_checkpoint(
                    stream,
                    offset_end,
                )
                self._process_line(
                    raw_line=raw_line,
                    source=source,
                    offset_start=offset_start,
                    offset_end=offset_end,
                    observed_size=observed_size,
                    source_checkpoint=source_checkpoint,
                )

            final_size = int(os.fstat(stream.fileno()).st_size)
            final_offset = stream.tell()
            if incomplete:
                return False
            source_checkpoint = _source_checkpoint(
                stream,
                final_offset,
            )
            self.repository.observe_source(
                source_identity=source.identity,
                source_path=str(source.path),
                source_offset=final_offset,
                source_checkpoint=source_checkpoint,
                observed_size=final_size,
                retired_completed=(
                    not source.is_active and final_offset == final_size
                ),
                now_utc=self.service.now_iso(),
            )
            return True

    def _reset_rewritten_source(
        self,
        source: SourceFile,
        *,
        reason: str,
    ) -> None:
        self.logger.warning(
            "public_traffic_source_checkpoint_mismatch "
            "reason=%s source_identity=%s",
            reason,
            source.identity,
        )
        self.repository.reset_source_after_truncate(
            source_identity=source.identity,
            source_path=str(source.path),
            observed_size=source.size,
            now_utc=self.service.now_iso(),
        )

    def _process_line(
        self,
        *,
        raw_line: bytes,
        source: SourceFile,
        offset_start: int,
        offset_end: int,
        observed_size: int,
        source_checkpoint: str,
    ) -> None:
        processed_at = self.service.now_iso()
        try:
            decoded = raw_line[:-1].decode("utf-8")
        except UnicodeDecodeError:
            self.logger.warning(
                "public_traffic_invalid_utf8 "
                "source_identity=%s source_offset=%s",
                source.identity,
                offset_start,
            )
            self.repository.advance_source(
                source_identity=source.identity,
                source_path=str(source.path),
                offset_end=offset_end,
                observed_size=observed_size,
                now_utc=processed_at,
                source_checkpoint=source_checkpoint,
            )
            return

        try:
            record = json.loads(decoded)
        except (json.JSONDecodeError, ValueError):
            record = None
        if not isinstance(record, dict):
            self.logger.warning(
                "public_traffic_reader_error "
                "reason=invalid_json source_identity=%s "
                "source_offset=%s",
                source.identity,
                offset_start,
            )
            self.repository.advance_source(
                source_identity=source.identity,
                source_path=str(source.path),
                offset_end=offset_end,
                observed_size=observed_size,
                now_utc=processed_at,
                source_checkpoint=source_checkpoint,
            )
            return

        classified = self.service.classify_record(record)
        if not classified.target:
            self.repository.advance_source(
                source_identity=source.identity,
                source_path=str(source.path),
                offset_end=offset_end,
                observed_size=observed_size,
                now_utc=processed_at,
                source_checkpoint=source_checkpoint,
            )
            return
        if classified.event is None:
            self.logger.warning(
                "public_traffic_target_event_invalid "
                "reason=%s source_identity=%s source_offset=%s",
                classified.warning_code,
                source.identity,
                offset_start,
            )
            self.repository.advance_source(
                source_identity=source.identity,
                source_path=str(source.path),
                offset_end=offset_end,
                observed_size=observed_size,
                now_utc=processed_at,
                source_checkpoint=source_checkpoint,
            )
            return

        outcome = self.repository.process_offline_event(
            event=classified.event,
            source_identity=source.identity,
            source_path=str(source.path),
            offset_start=offset_start,
            offset_end=offset_end,
            observed_size=observed_size,
            processed_at=processed_at,
            source_checkpoint=source_checkpoint,
        )
        if outcome.duplicate:
            return
        if classified.timestamp_fallback:
            self.logger.warning(
                "public_traffic_timestamp_fallback "
                "normalized_event_id=%s",
                classified.event.normalized_event_id,
            )
        if outcome.skip_reason == "aggregate_overflow":
            self.logger.warning(
                "public_traffic_aggregate_overflow "
                "normalized_event_id=%s",
                classified.event.normalized_event_id,
            )
        elif outcome.skip_reason is not None:
            self.logger.warning(
                "public_traffic_target_event_invalid "
                "reason=%s normalized_event_id=%s",
                outcome.skip_reason,
                classified.event.normalized_event_id,
            )


def _source_identity(stat_result: os.stat_result) -> str:
    return f"{stat_result.st_dev}:{stat_result.st_ino}"


def _source_checkpoint(stream, offset: int) -> str:
    if type(offset) is not int or offset < 0:
        raise ValueError("checkpoint offset must be non-negative")
    original_position = stream.tell()
    try:
        digest = hashlib.sha256()
        digest.update(b"public-traffic-checkpoint-v1\0")
        digest.update(str(offset).encode("ascii"))
        digest.update(b"\0")

        prefix_length = min(CHECKPOINT_WINDOW_BYTES, offset)
        stream.seek(0)
        prefix = stream.read(prefix_length)
        if len(prefix) != prefix_length:
            raise OSError("source became shorter during checkpoint")
        digest.update(len(prefix).to_bytes(4, "big"))
        digest.update(prefix)

        tail_start = max(prefix_length, offset - CHECKPOINT_WINDOW_BYTES)
        tail_length = offset - tail_start
        stream.seek(tail_start)
        tail = stream.read(tail_length)
        if len(tail) != tail_length:
            raise OSError("source became shorter during checkpoint")
        digest.update(len(tail).to_bytes(4, "big"))
        digest.update(tail)
        return digest.hexdigest()
    finally:
        stream.seek(original_position)
