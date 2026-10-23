# Visit Lifecycle

Status: current module contract
Updated: 2026-10-23
Implementation base: `captivprod/main@2594c8753ed09a36fb8ded9b70e5966b23a4810d`
Schema: v6 (explicit read/recovery admission: v2/v3/v4/v5/v6)

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

### Visit-owned NI03/NI04 history (#296, Owner decision v3)

V3 adds the NI03 protocol summary. V4 adds NI04 memberships, service summaries
and one atomic delivery checkpoint in this same Visit DB. These confirmed
children live **as long as their authoritative parent Visit**. No close-age
14/30/365-day cutoff applies to attached memberships or summaries. Physical
parent deletion cascades to both NI03 and NI04 children; this task adds no
Visit auto-purger. NI04 Device 60m/24h presentation and NI02/NI04 raw retention
remain independent and unchanged.

The canonical NI02 Top-1 index and strict schema admission are preserved.
Normal startup never repairs a missing index; the separately approved offline
maintenance procedure remains the only installation/removal boundary.
The configured-Guest-CIDR Sensor/BPF implementation and Operations startup
verification/UI are not replaced by the historical Visit implementation.

Historical V5 removes the obsolete `history_ttl_days` checkpoint policy and adds nullable
`pending_since` and `linkage_attached_at` to membership, plus bounded review and
detached-expiry indexes. A durable detached-row count in the same checkpoint
enforces capacity without a population scan on each incoming fact.
V6 adds optional `first_credit_floor_utc` to that same checkpoint and includes
all detached states in the expiry index. Exact V4/V5 admission, quick/FK checks,
the cutover and output signature verification run in one startup transaction.
Consumer ID, stream ID, sequence/hash, source head and all linked history are
preserved. V4 cannot distinguish an earlier pending interval for an attached
row: migration conservatively seeds its earliest known durable `created_at`
clock and marks already-attached rows as previously linked. It never grants
an old fact a fresh hour and emits no invented historical linkage samples.

On V4/V5 cutover **only existing unlinked memberships** are removed, atomically
with a durable UTC event-time floor F and resetting their detached count to zero.
F is the cutover UTC, checked to cover every removed original event time. An
invalid/future legacy event or inconsistent checkpoint/count fails migration
without partial cleanup. Linked memberships, summaries, NI03 and source outbox
are not removed. Without legacy detached rows (including a fresh V6 DB), F is
NULL. Startup on V6 never advances or recomputes F.

For a **new canonical fact**, including direct association with an existing
Visit, first credit requires `0 <= evaluation_utc - observed_at < 3600s` and,
when F exists, `observed_at > F`. Exact 3600s or pre-cutover facts are discarded
without membership/tombstone; the valid source delivery and checkpoint advance
atomically. Future/invalid event time or stream/hash conflict fails closed.
Owner explicitly accepts that late recognition/backfill reaching Visit for the
first time after one hour cannot earn first Visit credit. This does not delete
NI04 source data or change Device 60m/24h results.

Detached facts (`visit_id IS NULL`) may newly attach only **before 3600s**
from their first durable staging timestamp, with unchanged exact
Site/Device/MAC/auth-snapshot/event-time/lineage checks. At 3600s they are
ineligible even if physical expiration was deferred during source outage.
New direct attachments have no pending clock until a first actual detachment;
replay, restart and later detach/reattach never reset an established clock.
An attached provisional child is not expired merely because it is old.
The independent closed-Visit 15-minute sealing/grace is unchanged.

Indexed GC physically deletes at most 25 detached rows per writer transaction
after their original pending hour has elapsed, and only when original E is
already outside first-credit eligibility (or covered by F). Canonical pending
clocks must satisfy E <= P <= current UTC. GC happens before admission and
decrements the durable detached count in the same transaction. No permanent
expired guards remain; expired states produced by bounded re-review are only
transient until GC. Capacity 100,000 bounds **currently present** detached/
in-flight rows, not cumulative historical identities. True concurrent overflow
fails closed without checkpoint advance; expiry frees space for later events.
Replay of the same original E after GC cannot recreate a new waiting window.
Source-unacknowledged outbox data is never discarded to satisfy staging TTL.
Source ack/hash/floor verification and bounded sole-writer pruning are unchanged.

The supported trust boundary is the canonical NI02 reader (immutable source
edge/semantic digest/identity) plus NI01-to-NI02 evidence equivalence in the
normal NI04 worker evaluator. Live, backfill and binding/generation replay use
that same path; original observed_at comes from the validated fact. The private
positive-outbox helper is not a standalone ingestion authority. No perpetual
identity-time ledger, repeated NI02 cross-DB lookup by Visit, or new producer
protocol is added to authenticate manually fabricated internal helper input.

### Explicit activation and paired recovery

Both sides are inert by default. Visit composition requires the existing NI03
feature gate plus strict startup `VISIT_SERVICE_HISTORY_ENABLED=true` and a
valid NI04 source path. NI04 producer requires explicit `--visit-history-db`
pointing to that Visit DB. There is no new Settings surface.
`VISIT_SERVICE_HISTORY_RETENTION_DAYS` is ignored and
`--visit-history-ttl-days` is no longer accepted: no fake TTL is needed.
NI04 ack accepts the exact V6 consumer without a policy-equality gate; all
consumer/stream/sequence/hash/floor safeguards remain mandatory.

Before any separately approved migration, stop coordinated writers and take
consistent **paired NI04 V1/V2 + Visit V2/V3/V4/V5/V6 backups**, including SQLite WAL
state using the established backup procedure. The canonical deployment starts
from NI04 V1 + Visit V2; retain that exact pre-migration pair and its matching
code, rather than assuming historical #296 schemas are already installed.
Rehearse migration/restore in
Lab and verify exact signatures, checkpoint/hash/floor and child counts.
Old V4/V5 binaries cannot open V6. Rollback of code needs the matching paired
pre-migration backups; never restore Visit alone below an already-pruned
source floor, drop history tables, fake user_version or reset checkpoints.
Disabling activation stops future work, not a schema downgrade. Coder does
not migrate production, change services or authorize rollout.

### Linkage latency operational samples

The existing reconciler exports `visit.service_linkage_sample` at most once
per 60 monotonic seconds, through existing `VisitTelemetry`. It reports only
committed unique staging/linkage/expiry transitions, coarse rejection classes,
committed batches/failures and a bounded unresolved population sample. A
population read failure sets `unresolved_sample_valid=0`, not a healthy zero;
`population_capped` identifies a >100,000 legacy population. No event carries
IP, MAC, Visit/device ID, endpoint, source payload or per-fact log.
`rejected_old_first_delivery` separately counts committed discarded canonical
identities per batch (repeated deliveries in later batches may count again);
it is not a lifetime unique population or a claim of complete source coverage.
`expired_detached_unique` tracks committed pending expiry, distinct from these
old-first-delivery rejections. Saved history remains honestly incomplete when
source coverage or late first delivery cannot be established.

Disjoint linkage buckets are <=30s, (30,60]s, (60,300]s, (300,900]s,
(900,1800]s and (1800,3600)s, measured from persisted `pending_since` to the
first committed linkage. `linkage_attached_at` prevents reattachment/replay
from counting as another unique success. Direct attachment is not a delayed
linkage. Expired and still-unresolved are distinct from linked; no overall
percentage/p95/p99 or production linkage rate is inferred from these counters.

Counters are process-local interval deltas. Each export declares interval,
first-process sample, restart-gap possibility, export/sample failures and
saturation. Failed exports retain deltas until a later attempt. Crashes can
lose unexported deltas, including the commit-to-observer gap; these samples
are not continuous 7–14d evidence without external restart/gap reconciliation.
Sampling adds a bounded read, never a SQLite heartbeat write/commit. No new
worker, timer, logging route or frontend polling is introduced.

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
