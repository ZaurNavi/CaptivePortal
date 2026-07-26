"""Value objects returned by the portal counter."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RecordOpenResult:
    recorded: bool
    duplicate: bool


@dataclass(frozen=True)
class CounterSnapshot:
    opened_today: int
    opened_total: int
    day: str
    timezone: str
