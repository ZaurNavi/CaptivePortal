# Visit Lifecycle

Status: current module contract
Updated: 2026-08-26
Baseline: `main@53f617b3ac0155d0d647e58e98309927f9a4d318`
Schema: v2

## Purpose

Model physical visits independently from process-local AuthSession state.

`AuthSession != Visit`; one Visit may have multiple authorization events.

## Start path

`confirmed AUTHORIZED AuthRun → VisitStartRequest → LocalVisitStartSubmitter → VisitLifecycleService → visits.sqlite3`

Opening evidence includes the ingress `portal_ssid` when proven. CAPPORT and External Portal must preserve their actual ingress SSID context; Visit Lifecycle does not reconstruct missing SSID from Site/configuration.

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

### Optional compact scan telemetry

Startup flag `VISIT_LIFECYCLE_READER_SCAN_TELEMETRY_COMPACT_ENABLED` defaults
to `false`. It follows `app/config.py` -> `app/settings.py:get_settings()` ->
`visit_config_from_settings()` -> immutable `VisitLifecycleConfig` -> the
existing reader. The existing strict boolean parser admits true/false (not
truthy integers or arbitrary strings). It is not Admin-writable, hot-reloaded
or read directly from the environment by the reader. A disabled Visit runtime
still starts no reader and creates no database.

OFF keeps legacy completion reports on every exception-free scan. ON compacts
only proven unchanged healthy empty completed scans in process memory and
attempts a heartbeat on the next healthy completion at or after 60 monotonic
seconds. Initial/activity/incomplete/committed retry progress/source change,
recovery and active-to-idle transitions report immediately; meaningful work
takes priority over initial/recovery. Existing warning/error/deferred and
starvation events are never throttled. See [event v2 contract](../logging.md#visit-reader-compact-completed-reports-qio-01d).

This changes reporting only: discovery, processing, missing-source handling,
pending committed callbacks, offsets/checkpoints, rows, coordinator ordering,
SQLite transactions/durability and reader health remain authoritative and
unchanged. No new database, schema, retry policy, thread or timer. A quiet
scan may still perform SQLite work; zero processed lines are not proof of no
durable progress. Operational aggregation must not be used to skip that work.

Production opt-in is **HOLD**, including after merge. Consumer-first rollout
must validate actual dashboard UID `captive-portal-auth-v3-fixed`/panel 138,
deployed LogQL, alerts and external parsers against mixed OFF/ON/restart
history before separate Owner activation approval. Counters are lossy on
restart or telemetry failure. Completed-report age over 120 seconds is stale;
over 180 seconds requires escalation as unknown/unavailable, not an Auth or
Visit-state decision. Different scan cadence/budgets require reviewed
monitoring thresholds (at least heartbeat + cadence + scan budget + jitter).

Rollback is approved startup flag `false` plus an Owner-controlled restart:
legacy fields/frequency return, without DB rollback, source rewind or replay
reset. No systemd/restart authority or production change is provided here.
Independent correctness/full/performance and Loki consumer acceptance belong
to Tech Lead. Message-count reduction alone does not demonstrate HDD savings.

## Shutdown

Stop reader/reconciler scheduling first; drain Auth executor before stopping Visit acceptance; then wait for accepted Visit starts to become idle.

## Dependencies

Allowed:
Auth start sink, normalized webhook journal, Registry read service, own SQLite.

Forbidden:
direct Omada polling, raw webhook reinterpretation, dependency from core authorization on Visit success.
