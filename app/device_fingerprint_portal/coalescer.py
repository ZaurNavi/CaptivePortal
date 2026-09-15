"""Bounded atomic non-blocking admission coalescer."""

from __future__ import annotations

import queue
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from itertools import islice
from typing import Any

from .models import CoalescerKey, QueuedPortalEvidence


@dataclass(frozen=True, slots=True)
class AdmissionResult:
    status: str
    item: QueuedPortalEvidence | None = None


class PortalEvidenceCoalescer:
    def __init__(self, *, expiry_seconds: int = 21600, max_entries: int = 8192,
                 monotonic=time.monotonic, lock: Any = None) -> None:
        self.expiry_seconds = expiry_seconds
        self.max_entries = max_entries
        self.monotonic = monotonic
        self._lock = lock or threading.Lock()
        self._entries: OrderedDict[CoalescerKey, float] = OrderedDict()

    def try_admit(
        self,
        key: CoalescerKey,
        destination: queue.Queue[QueuedPortalEvidence],
        item_factory: Callable[[float], QueuedPortalEvidence],
    ) -> AdmissionResult:
        if not self._lock.acquire(blocking=False):
            return AdmissionResult("busy")
        try:
            now = self.monotonic()
            self._cleanup_expired(now)
            expiry = self._entries.get(key)
            if expiry is not None and expiry > now:
                return AdmissionResult("coalesced")
            if expiry is not None:
                self._entries.pop(key, None)
            item = item_factory(now)
            try:
                destination.put_nowait(item)
            except queue.Full:
                return AdmissionResult("full")
            if key not in self._entries and len(self._entries) >= self.max_entries:
                self._entries.popitem(last=False)
            self._entries[key] = now + self.expiry_seconds
            self._entries.move_to_end(key)
            return AdmissionResult("admitted", item)
        finally:
            self._lock.release()

    def shorten(self, keys: Iterable[CoalescerKey], deadline: float) -> None:
        with self._lock:
            for key in keys:
                if key in self._entries:
                    self._entries[key] = min(self._entries[key], deadline)

    def remove(self, keys: Iterable[CoalescerKey]) -> None:
        with self._lock:
            for key in keys:
                self._entries.pop(key, None)

    def expiry(self, key: CoalescerKey) -> float | None:
        with self._lock:
            return self._entries.get(key)

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def _cleanup_expired(self, now: float) -> None:
        for key in list(islice(self._entries, 32)):
            if self._entries[key] <= now:
                self._entries.pop(key, None)
