"""Bounded process-local minute counters, not durable audit/replay authority."""
import time

SUMMARY_FIELDS = frozenset({
    "batch_count", "record_count", "duplicate_count", "fault_aggregate_update_count",
    "idle_poll_count", "commit_count", "checkpoint_attempt_count",
    "checkpoint_busy_count", "suppressed_event_count",
})
MAX_COUNTER = 9223372036854775807


class SuccessCounters:
    def __init__(self, publish, *, monotonic=time.monotonic):
        self.publish, self.monotonic = publish, monotonic
        self.window_started = monotonic()
        self.counts = {}

    def observe(self, **counts):
        if not set(counts) <= SUMMARY_FIELDS:
            raise ValueError("invalid_success_counter")
        if any(type(value) is not int or not 0 <= value <= MAX_COUNTER for value in counts.values()):
            raise ValueError("invalid_success_counter")
        for field, value in counts.items():
            self.counts[field] = min(MAX_COUNTER, self.counts.get(field, 0) + value)

    def flush_due(self):
        now = self.monotonic()
        if now - self.window_started < 60:
            return
        if self.counts:
            # Closed integer fields only; raw source or identity values cannot enter.
            self.publish(dict(event="success_summary", interval_seconds=60, **self.counts))
            self.counts.clear()
        self.window_started = now
