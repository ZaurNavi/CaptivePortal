"""B1 read-only freshness policy; no DTO expansion or writer side effects."""
from datetime import datetime, timezone

from app.network_metadata.validation import ni_timestamp
from app.network_metadata.models import NetworkMetadataValidationError

SOURCE_USABLE_STATES = frozenset({"usable", "registry_degraded", "attribution_unavailable"})
SOURCE_POLL_STALE_AFTER_SECONDS = 30


def effective_runtime_state(row, *, enabled, evaluated_at_utc=None):
    state, reason = row["runtime_state"], row["safe_reason"]
    if not enabled or state not in SOURCE_USABLE_STATES:
        return state, reason
    try:
        now = evaluated_at_utc if evaluated_at_utc is not None else datetime.now(timezone.utc)
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError
        last = ni_timestamp(row["last_source_poll_at"], canonical=True)
        age = (now - last).total_seconds()
        if 0 <= age <= SOURCE_POLL_STALE_AFTER_SECONDS:
            return state, reason
    except (ValueError, TypeError, AttributeError, KeyError, IndexError, OverflowError, NetworkMetadataValidationError):
        pass
    # Future, missing and malformed timestamps are not evidence of freshness.
    return "source_unavailable", "source_poll_stale"
