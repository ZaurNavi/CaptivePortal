"""Default-OFF pre-durable evidence window; SensorSpool stays the only writer."""

from __future__ import annotations

import json
import threading
import time
from typing import Iterable

from .models import NormalizedEvent, SensorSpoolError

MAX_EVENTS = 32
MAX_OLDEST_EVENT_WAIT_MS = 100
MAX_BUFFERED_SERIALIZED_BYTES = 262144


class _SpoolWriteFailure(SensorSpoolError):
    pass


class IngressCoalescer:
    def __init__(self, spool, *, monotonic=time.monotonic, on_fault=None) -> None:
        self.spool, self.monotonic, self.on_fault = spool, monotonic, on_fault
        self._condition = threading.Condition(threading.Lock())
        self._pending: list[tuple[int, NormalizedEvent]] = []
        self._bytes = 0
        self._oldest: float | None = None
        self._submission_ordinal = 0
        self._disabled = self._closing = False
        self._shutdown_requested = threading.Event()
        self._accepting = True
        self._spool_failed = False
        self._fault_notice: str | None = None
        self._thread: threading.Thread | None = None
        self.spool._capacity_wakeup = self._wake_on_capacity

    def _wake_on_capacity(self) -> None:
        # May be called with the spool lock held: never reverse the
        # condition -> spool lock order or wait for the condition here.
        if self._condition.acquire(blocking=False):
            try:
                self._condition.notify_all()
            finally:
                self._condition.release()

    @property
    def timer_stopped(self) -> bool:
        thread = self._thread
        return thread is None or not thread.is_alive()

    def start(self) -> None:
        try:
            with self._condition:
                self._start_locked()
        finally:
            self._notify_fault()

    def _start_locked(self) -> None:
        if self._thread is not None or self._disabled or self._closing or self._shutdown_requested.is_set():
            return
        try:
            thread = threading.Thread(target=self._run, name="fingerprint-ingress", daemon=False)
            thread.start()
            self._thread = thread
        except Exception:
            self._fallback_locked()

    @staticmethod
    def _serialized_size(event: NormalizedEvent) -> int:
        # Same deterministic JSON grammar as the spool, without keeping a
        # serialized payload copy or rendering it in telemetry.
        encoder = json.JSONEncoder(ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":"))
        size = 0
        for chunk in encoder.iterencode(event.document):
            size += len(chunk)  # ensure_ascii: serialized characters are bytes.
            if size > MAX_BUFFERED_SERIALIZED_BYTES:
                return MAX_BUFFERED_SERIALIZED_BYTES + 1
        return size

    def _enqueue_locked(self, events, *, atomic_coalesced: bool = False) -> int:
        try:
            if atomic_coalesced:
                result = self.spool.enqueue(events, atomic_coalesced=True)
            else:
                result = self.spool.enqueue(events)
            if self.spool.capacity_blocked:
                raise SensorSpoolError("spool capacity blocked")
            return result
        except Exception:
            first_failure = not self._spool_failed
            self._disabled = self._spool_failed = True
            if first_failure:
                self._fault_notice = "spool_write"
            self._condition.notify_all()
            raise _SpoolWriteFailure("ingress spool write unavailable") from None
        finally:
            if self._shutdown_requested.is_set():
                self._condition.notify_all()

    def _flush_locked(self, *, atomic_coalesced: bool = True) -> int:
        if not self._pending:
            return 0
        events = [event for _ordinal, event in self._pending]
        # Exactly one bounded write attempt; failed writes are not represented
        # as durable acceptance or an indefinitely retrying memory sidequeue.
        self._pending = []
        self._bytes, self._oldest = 0, None
        return self._enqueue_locked(events, atomic_coalesced=atomic_coalesced)

    def _fallback_locked(self) -> int:
        self._disabled = True
        self._fault_notice = "ingress_coalescer"
        self._condition.notify_all()
        return self._flush_locked(atomic_coalesced=False)  # Same objects / same IDs; at most 32 rows.

    def _notify_fault(self) -> None:
        with self._condition:
            notice, self._fault_notice = self._fault_notice, None
        if notice is not None and self.on_fault is not None:
            try:
                self.on_fault(notice)
            except Exception:
                pass  # Operational notification cannot break spool/capture.

    def _submit_one_locked(self, ordinal: int, event: NormalizedEvent) -> int:
        count = 0
        submitted_at = self.monotonic()
        if (self._pending and self._oldest is not None
                and self.monotonic() - self._oldest >= MAX_OLDEST_EVENT_WAIT_MS / 1000):
            count += self._flush_locked()
        if self.spool.capacity_blocked:
            count += self._flush_locked()
            return count + self._enqueue_locked((event,))
        if event.endpoint != "evidence":
            count += self._flush_locked()
            return count + self._enqueue_locked((event,))
        size = self._serialized_size(event)
        if size > MAX_BUFFERED_SERIALIZED_BYTES:
            count += self._flush_locked()
            return count + self._enqueue_locked((event,))
        if self._bytes + size > MAX_BUFFERED_SERIALIZED_BYTES:
            count += self._flush_locked()
        if not self._pending:
            self._oldest = submitted_at
        self._pending.append((ordinal, event))
        self._bytes += size
        self._condition.notify_all()
        if (len(self._pending) == MAX_EVENTS
                or self.monotonic() - self._oldest >= MAX_OLDEST_EVENT_WAIT_MS / 1000):
            count += self._flush_locked()
        return count

    def submit(self, events: Iterable[NormalizedEvent]) -> int:
        try:
            with self._condition:
                if not self._accepting or self._shutdown_requested.is_set():
                    raise SensorSpoolError("ingress is stopping")
                self._submission_ordinal += 1
                self._start_locked()
                ordinal, count = self._submission_ordinal, 0
                iterator = iter(events)
                for event in iterator:
                    if self._disabled:
                        count += self._enqueue_locked((event,))
                        continue
                    try:
                        count += self._submit_one_locked(ordinal, event)
                    except _SpoolWriteFailure:
                        raise
                    except Exception:
                        count += self._fallback_locked()
                        # Reusing a current ID if an interrupted operation had
                        # already appended it is safe under INSERT OR IGNORE.
                        count += self._enqueue_locked((event,))
                        for remaining in iterator:
                            count += self._enqueue_locked((remaining,))
                        break
                return count
        finally:
            self._notify_fault()

    def barrier(self, events: Iterable[NormalizedEvent] = ()) -> int:
        """Flush evidence first; source-health uses its own immediate enqueue."""
        try:
            with self._condition:
                if not self._accepting or self._shutdown_requested.is_set():
                    raise SensorSpoolError("ingress is stopping")
                self._submission_ordinal += 1
                self._start_locked()
                try:
                    count = self._flush_locked()
                except _SpoolWriteFailure:
                    raise
                except Exception:
                    count = self._fallback_locked()
                return count + self._enqueue_locked(events)
        finally:
            self._notify_fault()

    def _run(self) -> None:
        try:
            while True:
                with self._condition:
                    if self._disabled:
                        return
                    if self._closing or self._shutdown_requested.is_set():
                        self._flush_locked()
                        return
                    if not self._pending:
                        self._condition.wait()
                        continue
                    remaining = MAX_OLDEST_EVENT_WAIT_MS / 1000 - (self.monotonic() - self._oldest)
                    if remaining > 0 and not self.spool.capacity_blocked:
                        self._condition.wait(remaining)
                        continue
                    self._flush_locked()
        except _SpoolWriteFailure:
            pass  # Already marked fail-closed; never re-confirm a failed write.
        except Exception:
            with self._condition:
                try:
                    self._fallback_locked()
                except _SpoolWriteFailure:
                    pass
        finally:
            self._notify_fault()

    def shutdown(self, *, deadline: float) -> bool:
        # The timer performs the final single flush, so the caller can respect
        # the shared shutdown budget even if a spool write stalls.
        # Signal even if a current spool write owns the ordering guard past the
        # budget. Its completion wakes the timer, which must then exit.
        self._shutdown_requested.set()
        acquired = self._condition.acquire(timeout=max(0.0, deadline - self.monotonic()))
        if not acquired:
            return False
        try:
            self._accepting = False
            self._closing = True
            self._condition.notify_all()
            thread = self._thread
        finally:
            self._condition.release()
        if thread is not None:
            thread.join(max(0.0, deadline - self.monotonic()))
        return (thread is None or not thread.is_alive()) and not self._pending and not self._spool_failed
