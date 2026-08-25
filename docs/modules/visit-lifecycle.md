# Visit Lifecycle

Status: current module contract
Updated: 2026-08-25
Baseline: `main@dfc62b43712301b05baf9f6e5dd843e13eaa9fc7`
Schema: v2

## Purpose

Model physical visits independently from process-local AuthSession state.

`AuthSession != Visit`; one Visit may have multiple authorization events.

## Start path

`confirmed AUTHORIZED AuthRun → VisitStartRequest → LocalVisitStartSubmitter → VisitLifecycleService → visits.sqlite3`

Auth success is fail-open with respect to Visit persistence: failure to persist Visit history must not revoke otherwise verified guest authorization.

## Close path

`normalized Omada webhook journal → VisitLifecycleWebhookReader → OfflineEvidence → service → match/close`.

Visit Lifecycle consumes normalized events, not raw webhook interpretation.

## Storage

Current schema includes:
- `visits`;
- `visit_authorizations`;
- `visit_source_events`;
- durable reader state/checkpoint.

Schema v2 adds offline source facts including client IP, SSID, AP MAC, reported connected seconds and reported traffic total bytes.

## Concurrency

`PriorityWriteCoordinator` serializes SQLite write leases:
- Visit Start is foreground/high priority;
- webhook reader and reconciliation are background FIFO;
- writer-slot waits and SQLite busy timeout are separately bounded;
- Visit Start has bounded retry count and total budget.

Do not add an independent SQLite writer path around this coordinator.

## Reader/reconciliation

Reader scans are bounded by line count, bytes and duration and preserve source offsets/identity for durable progress.

Registry reconciliation links visits to persistent device/snapshot identity.

Runtime is active only with healthy reader and running reconciler; otherwise degraded.

## Shutdown

Stop reader/reconciler scheduling first; drain Auth executor before stopping Visit acceptance; then wait for accepted Visit starts to become idle.

## Dependencies

Allowed:
Auth start sink, normalized webhook journal, Registry read service, own SQLite.

Forbidden:
direct Omada polling, raw webhook reinterpretation, dependency from core authorization on Visit success.
