"""Bounded physical-file reader and exact, non-heuristic lifecycle decisions."""
import os
import stat
import hashlib
from dataclasses import dataclass

from .canonical import sha256
from .models import (CONTINUITY_ANCHOR_MAX_BYTES, SOURCE_READ_CHUNK_BYTES,
                     NetworkMetadataStorageUnavailable, NetworkMetadataValidationError)
from .validation import canonical_uuid, integer


@dataclass(frozen=True, slots=True, repr=False)
class SourceRecord:
    start: int
    end: int
    byte_length: int
    data: bytes | None
    source_record_sha256: str


@dataclass(frozen=True, slots=True)
class GenerationDecision:
    action: str
    close_reason: str | None = None
    coverage_gap_possible: bool = False
    start_offset: int = 0


def host_boot_id():
    try:
        with open("/proc/sys/kernel/random/boot_id", "r", encoding="ascii") as stream:
            value = stream.read(128).strip()
        return canonical_uuid(value)
    except (OSError, UnicodeError, NetworkMetadataValidationError):
        raise NetworkMetadataStorageUnavailable() from None


def physical_identity(info):
    if not stat.S_ISREG(info.st_mode):
        raise NetworkMetadataValidationError()
    return integer(info.st_dev), integer(info.st_ino)


def continuity_anchor(fd, offset):
    integer(offset)
    length = min(CONTINUITY_ANCHOR_MAX_BYTES, offset)
    if not length:
        return (0, 0, None)
    try:
        data = os.pread(fd, length, offset - length)
        if len(data) != length:
            raise OSError
        return (offset - length, length, sha256(data))
    except OSError:
        raise NetworkMetadataStorageUnavailable() from None


def anchor_matches(fd, checkpoint):
    return continuity_anchor(fd, checkpoint.committed_byte_offset) == (
        checkpoint.continuity_anchor_start_offset, checkpoint.continuity_anchor_length,
        checkpoint.continuity_anchor_sha256)


def decide_startup_generation(generation, checkpoint, boot_id, current, binding, *, continuity=True):
    if generation is not None and generation.processing_state == "blocked":
        return GenerationDecision("blocked")
    if generation is None:
        return GenerationDecision("open" if current is not None else "wait")
    if generation.host_boot_id != boot_id:
        return GenerationDecision("replace", "host_reboot_source_lost", True)
    if current is None:
        return GenerationDecision("wait")
    if physical_identity(current) != (generation.st_dev, generation.st_ino):
        return GenerationDecision("replace", "source_replaced_while_reader_down", True)
    if current.st_size < checkpoint.committed_byte_offset:
        return GenerationDecision("replace", "observed_truncation", True)
    if not continuity:
        return GenerationDecision("replace", "continuity_anchor_mismatch", True)
    if binding.binding_digest != generation.capture_scope_binding_digest:
        return GenerationDecision("cutover", "capture_scope_binding_changed", False,
                                  checkpoint.committed_byte_offset)
    return GenerationDecision("resume", start_offset=checkpoint.committed_byte_offset)


class BinarySourceReader:
    """Scan position is disposable. Only a repository checkpoint is durable."""
    def __init__(self, fd, *, max_record_bytes, offset=0):
        self.fd = fd
        self.max_record_bytes = max_record_bytes
        self.reset(offset)

    def reset(self, offset):
        self.scan_offset = self.record_start = integer(offset)
        self._buffer = bytearray()
        self._count = 0
        self._discard = False
        self._record_hash = hashlib.sha256()
        self.at_eof = False

    @property
    def retained_unfinished_bytes(self):
        return len(self._buffer)

    @property
    def tail_length(self):
        return self._count

    def read_batch(self, max_records, max_bytes):
        records, retained = [], 0
        budget = max_bytes + SOURCE_READ_CHUNK_BYTES
        self.at_eof = False
        try:
            while budget > 0 and len(records) < max_records:
                chunk = os.pread(self.fd, min(SOURCE_READ_CHUNK_BYTES, budget), self.scan_offset)
                if not chunk:
                    self.at_eof = True
                    break
                budget -= len(chunk)
                position = 0
                while position < len(chunk):
                    delimiter = chunk.find(b"\n", position)
                    stop = len(chunk) if delimiter < 0 else delimiter
                    segment = chunk[position:stop]
                    self._record_hash.update(segment)
                    self._count += len(segment)
                    if not self._discard:
                        if self._count > self.max_record_bytes:
                            self._discard = True
                            self._buffer.clear()
                        else:
                            self._buffer.extend(segment)
                    self.scan_offset += len(segment)
                    if delimiter < 0:
                        break
                    self.scan_offset += 1
                    item = SourceRecord(self.record_start, self.scan_offset, self._count,
                                        None if self._discard else bytes(self._buffer), self._record_hash.hexdigest())
                    if (item.data is None and records) or (item.data is not None and retained + item.byte_length > max_bytes):
                        self.reset(item.start)
                        return records
                    records.append(item)
                    retained += item.byte_length if item.data is not None else 0
                    self.record_start = self.scan_offset
                    self._buffer.clear()
                    self._count, self._discard = 0, False
                    self._record_hash = hashlib.sha256()
                    position = delimiter + 1
                    if item.data is None or len(records) >= max_records:
                        return records
            return records
        except OSError:
            raise NetworkMetadataStorageUnavailable() from None
