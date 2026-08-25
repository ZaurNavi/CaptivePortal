# Pending Client Session Cleaner

Status: current implementation; repository default disabled
Updated: 2026-08-25
Baseline: `main@dfc62b43712301b05baf9f6e5dd843e13eaa9fc7`

## Purpose

Safely terminate stale unauthorised Omada Wi-Fi client sessions using guarded `reconnect`.

## Eligibility

A candidate must satisfy:
- `active == true`;
- wireless;
- `authStatus == 1`;
- SSID in configured allowlist;
- uptime threshold;
- not blocked;
- no duplicate/ambiguous inventory condition.

## Safety chain

```text
complete paginated inventory
  ↓
classification
  ↓
local AuthSession protection
  ↓
fresh client preflight
  ↓
second local protection
  ↓
cooldown / hourly / per-scan action guard
  ↓
durable action.planned audit
  ↓
reconnect
  ↓
bounded verification
  ↓
action.completed
```

Core principle: **uncertainty => no reconnect**.

Incomplete inventory, ambiguous identity, protection failure, preflight mismatch, audit failure, exhausted guard, shutdown or internal error blocks mutation.

## Shared OmadaProvider

Cleaner reuses the process-wide provider/token cache.

Pending-session methods are attached to the same provider class; no second OAuth client/provider/token manager is permitted without explicit change intent.

Token recovery uses compare-and-invalidate so a late stale response cannot erase a newer token published by another thread.

## Action policy

Current automatic mutation is guarded `reconnect`.

Do not silently substitute disconnect, delete, unauth, block/unblock, forget or other client-control operations merely because research proves they exist.

A successful reconnect POST is not the final result; verification is bounded and explicit.

## Audit/persistence

Default:
`/opt/CaptivePortal/logs/pending_session_cleaner.log`.

The JSONL audit contains schema-versioned scan/planned/completed events.

`action.planned` must be durably written before POST.

ActionGuard cooldown/hour counters are bounded **process-local memory**. Process restart resets those counters; this is a known limitation.

Cleaner uses no SQLite.

## Lifecycle

One worker per application process. Scheduling is fixed-delay with overlap suppression.

Shutdown moves Cleaner to stopping before other long-lived data components and must prevent new mutation after stop begins.

Multi-process Cleaner execution is unsupported without leader-election/inter-process coordination ADR.

## Testing responsibility

Targeted Cleaner tests belong to a Cleaner implementation task. Full repository suite remains Reviewer / Tech Lead / owner pre-production responsibility according to `AGENTS.md`.

Do not preserve old test-count numbers as permanent current facts.

## Fail-open

Cleaner may become disabled/unavailable without breaking Portal/Auth. Fail-open relative to portal does not weaken the fail-closed safety decision for whether a reconnect is allowed.
