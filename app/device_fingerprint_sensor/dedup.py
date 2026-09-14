"""Bounded exact-frame duplicate suppression."""

from __future__ import annotations

import hashlib
from collections import OrderedDict


class ExactFrameDeduplicator:
    def __init__(self, capture_source_id: str, *, max_entries: int = 65536, horizon_ms: float = 0.25) -> None:
        self._prefix = capture_source_id.encode("ascii") + b"\0"
        self._max_entries = max_entries
        self._horizon_ns = int(horizon_ms * 1_000_000)
        self._seen: OrderedDict[bytes, int] = OrderedDict()
        self.raw_packet_count = 0
        self.duplicate_packet_count = 0
        self.deduplicated_packet_count = 0

    def is_duplicate(self, frame: bytes, received_ns: int) -> bool:
        self.raw_packet_count += 1
        key = hashlib.blake2s(
            self._prefix + len(frame).to_bytes(8, "big") + frame,
            digest_size=16,
        ).digest()
        previous = self._seen.get(key)
        duplicate = previous is not None and 0 <= received_ns - previous <= self._horizon_ns
        self._seen[key] = received_ns
        self._seen.move_to_end(key)
        while len(self._seen) > self._max_entries:
            self._seen.popitem(last=False)
        if duplicate:
            self.duplicate_packet_count += 1
        else:
            self.deduplicated_packet_count += 1
        return duplicate

    @property
    def ratio(self) -> float:
        return self.duplicate_packet_count / self.raw_packet_count if self.raw_packet_count else 0.0
