# TASK-DTI-NI-04 — Background Materialized Service Intelligence
## Architecture Contract v1.1 Addendum
### Closure of Tech Lead findings TL-R1, TL-R2, TL-R3

**Project:** CaptivPortal  
**Authority:** CaptivPortal Architect  
**Date:** 2026-10-13  
**Baseline reviewed:** `main@b1442efc434716d35e21b9e3124c3b9cd2222fbe`  
**Tree:** `1ea6a2d452a5c8147d2a9cdce6c5dcecd9900575`  
**Parent contract:** `TASK-DTI-NI-04-BACKGROUND-MATERIALIZED-SERVICE-INTELLIGENCE-ARCHITECTURE-CONTRACT-v1.md`  
**Scope:** TL-R1 / TL-R2 / TL-R3 only  
**Coder:** HOLD  
**Production change:** NO

---

# 0. Authority and frozen scope

This addendum is normative and amends only the exact parent-contract points named below.

All other Architecture Contract v1 decisions remain frozen, including:

- dedicated NI-04 background worker;
- dedicated NI-04 materialized SQLite store;
- additive NI-02B Service Recognition delivery extension;
- existing NI-01 evidence semantics;
- existing NI-02B attribution/pending semantics;
- existing direct-SNI matcher and frozen knowledge artifacts;
- 24h bounded backfill;
- `off -> shadow -> serve` cutover;
- no Admin request-time recognition in `serve` mode;
- no NI-01, NI-02A, NI-03, Portal/Auth, Omada or recognition-rule redesign.

No open architecture choice is intentionally left to Coder by this addendum.

---

# 1. TL-R1 / P1 — Durable Registry binding-event cursor

## 1.1 Final decision

**The existing `projection_registry_binding_events.binding_event_id` MUST NOT be used as the durable NI-04 worker cursor.**

Reason:

```text
binding_event_id INTEGER PRIMARY KEY
```

is not an AUTOINCREMENT lifetime-monotonic identity, while the event table is retention-managed.
Therefore it is valid audit/history identity for the retained row, but it is not a safe materializer cursor across complete retention and later rowid reuse.

The parent contract §6 is superseded by a small additive NI-02B extension state:

```text
projection_registry_binding_change_index
```

This is **not a second Registry event history**.
It is a bounded current-state change index containing at most one row per currently retained authoritative `Site + MAC` binding.

The existing `projection_registry_binding_events` table remains unchanged and retains its existing semantics and retention.

---

## 1.2 Exact additive table

The NI-02B Service Recognition extension V1 MUST contain:

```text
projection_registry_binding_change_index
----------------------------------------
change_seq INTEGER PRIMARY KEY AUTOINCREMENT
site_id TEXT NOT NULL
client_mac TEXT NOT NULL
binding_state TEXT NOT NULL CHECK(binding_state='authoritative')
device_id TEXT NOT NULL
evaluated_at_utc TEXT NOT NULL

UNIQUE(site_id, client_mac)

FOREIGN KEY(site_id, client_mac)
  REFERENCES projection_site_mac_bindings(site_id, client_mac)
  ON DELETE CASCADE
```

No raw packet/evidence fields are added.

`change_seq` is the only Registry-change cursor authority for NI-04 materialization.

The use of `AUTOINCREMENT` here is deliberate and limited: this cursor requires lifetime non-reuse after deletion. It is not applied to high-volume evidence tables.

---

## 1.3 Initialization during extension migration

When Extension V1 is installed, existing state MUST be seeded deterministically.

Within the same schema-install transaction:

```text
SELECT authoritative rows
FROM projection_site_mac_bindings
ORDER BY site_id ASC, client_mac ASC
```

For every row with:

```text
binding_state='authoritative'
AND device_id IS NOT NULL
```

insert exactly one `projection_registry_binding_change_index` row.

This means an installation does not depend on retained Registry event history.

Cases:

```text
no current authoritative bindings
-> change index empty
-> cursor high-water = 0

current authoritative bindings + empty event history
-> all current authoritative bindings are still discoverable

retained old binding_event_id values reused later
-> irrelevant to NI-04 cursor semantics
```

---

## 1.4 Runtime update algorithm

Only establishment of a new authoritative Site+MAC -> Device binding changes this index.

Inside the SAME NI-02B writer transaction that establishes the authoritative binding:

```text
1. update/insert projection_site_mac_bindings
2. preserve existing projection_registry_binding_events behavior
3. DELETE any existing change-index row for the same site_id + client_mac
4. INSERT a new authoritative change-index row
   -> SQLite allocates a new change_seq
5. COMMIT
```

If the transaction rolls back, neither the authoritative transition nor its change-index sequence becomes committed.

A safe-reason-only Registry event, periodic authoritative revalidation, or another event that does not newly establish authoritative identity MUST NOT allocate a new `change_seq`.

If a retained binding is eventually deleted because no retained projection edge refers to its Site+MAC, the change-index row is removed by FK cascade.

If the same Site+MAC later becomes a new retained authoritative binding, the new insert receives a strictly later `change_seq`.

---

## 1.5 NI-02B read boundary

Replace parent §6 reader with:

```text
read_authoritative_binding_changes(
    after_change_seq,
    limit <= 128,
    deadline
)
```

Return order:

```text
change_seq ASC
```

Each returned row MUST be validated against the current `projection_site_mac_bindings` row in the same read snapshot:

```text
site_id exact
client_mac exact
binding_state = authoritative
device_id exact and non-null
```

Any mismatch is fail-closed `ProjectionUnavailable` / conflict-equivalent behavior; it is never converted into a Device fact.

No other MAC is replayed because one row triggers one exact:

```text
site_id + client_mac + device_id
```

replay job.

---

## 1.6 NI-04 checkpoint and replay transaction

Parent persistent fields are amended:

```text
service_recognition_observations.registry_binding_event_id
-> registry_binding_change_seq

device_materialization_state.registry_binding_event_id
-> registry_binding_change_seq

service_materialization_checkpoints.last_binding_event_id
-> last_binding_change_seq

service_binding_replay_jobs.binding_event_id
-> binding_change_seq
```

`service_binding_replay_jobs.binding_change_seq` is UNIQUE within one materialization generation.

Worker algorithm for one page:

```text
1. read change rows > last_binding_change_seq, ordered ASC, max 128
2. for each row build deterministic replay_job_id from:
       generation_id + change_seq + site_id + client_mac + device_id
3. in ONE NI-04 store transaction:
       INSERT replay job idempotently
       advance last_binding_change_seq through the last row durably enqueued
4. execute replay jobs separately in bounded Site+MAC pages
```

Crash semantics:

```text
crash before NI-04 enqueue/checkpoint COMMIT
-> same change row is read again

crash after enqueue/checkpoint COMMIT
-> deterministic job already exists
-> no duplicate replay
```

Cursor advancement therefore never silently skips a binding change.

---

## 1.7 Worker downtime and retention

The change-index row is current-state persistence, not a 30-day event row.
It survives retention of `projection_registry_binding_events` and survives arbitrary worker downtime while the corresponding retained binding exists.

If the binding itself is later removed only after its retained projection edges are gone, then no current 24h Service Intelligence evidence remains for that binding; losing a future replay trigger at that point does not permit a false positive or false complete-history claim.

No global/cross-MAC recovery replay is introduced.

---

## 1.8 Applicable invariant

```text
A Registry audit row may expire.
A materializer cursor identity may not be reused.
One authoritative Site+MAC change may schedule replay only for that Site+MAC.
No cursor gap may be interpreted as successful processing.
```

---

## 1.9 Deterministic QA — TL-R1

Mandatory tests:

### R1-QA-01 — Empty retained Registry history

```text
event table empty
current authoritative bindings exist
install extension
-> one seeded change-index row per authoritative Site+MAC
-> worker discovers each exactly once
```

### R1-QA-02 — Original event-ID reuse

Create/delete/recreate `projection_registry_binding_events` such that a non-AUTOINCREMENT event ID can be reused.

Expected:

```text
NI-04 behavior unaffected
change_seq remains strictly increasing/non-reused
```

### R1-QA-03 — Binding-event retention

Retain away all old Registry event rows while keeping a retained authoritative binding.

Expected:

```text
change-index row remains
worker restart still discovers exact Site+MAC
```

### R1-QA-04 — Delete and re-create Site+MAC binding

```text
old change_seq = N
binding + index row legitimately retained away
same Site+MAC later becomes authoritative again
-> new change_seq > N
```

### R1-QA-05 — Worker crash before enqueue transaction

Expected same change row after restart.

### R1-QA-06 — Worker crash after enqueue/checkpoint transaction

Expected one deterministic replay job and no duplicate.

### R1-QA-07 — No cross-MAC replay

A change for MAC-A MUST issue zero replay reads for MAC-B.

### R1-QA-08 — Non-authoritative / safe-reason-only change

Must not create a new authoritative `change_seq`.

---

# 2. TL-R2 / P1 — NI-02B additive schema compatibility and rollback

## 2.1 Final decision

The NI-02B Service Recognition persistence is an **optional Extension V1 on top of unchanged Core Projection V1**.

Core V1 tables, columns, triggers, contract version and attribution semantics remain unchanged.

Extension V1 consists exactly of:

```text
projection_service_recognition_extension_meta
projection_service_recognition_feed
projection_registry_binding_change_index
```

plus only indexes/autoindexes required by those exact tables.

The extension installation MUST be transactional and dual-schema-compatible.

---

## 2.2 Extension metadata

Add:

```text
projection_service_recognition_extension_meta
---------------------------------------------
singleton_id INTEGER PRIMARY KEY CHECK(singleton_id=1)
extension_contract_version INTEGER NOT NULL CHECK(extension_contract_version=1)
installed_at_utc TEXT NOT NULL
```

Exactly one row is allowed.

Core remains:

```text
network_metadata_projection_schema.schema_version = 1
projection_contract_version = 1
projection_algorithm_version = existing accepted value
PRAGMA user_version = 1
```

The extension MUST NOT silently bump/redefine those Core V1 identities.

---

## 2.3 Core V1 validation versus Extension V1 validation

The current whole-database exact-signature validator MUST be split conceptually into two closed validators.

### `validate_core_schema_v1()`

It MUST verify the exact accepted Core V1 objects and normalized DDL individually:

```text
all original Core V1 tables
all original Core V1 indexes
all original Core V1 triggers
Core metadata row
PRAGMA requirements
```

No Core object may differ from baseline merely because an extension exists.

### `validate_service_recognition_extension_v1()`

If extension metadata is absent:

```text
NO extension table/index may exist
-> valid CORE_ONLY state
```

If extension metadata is present:

```text
all Extension V1 objects must exist exactly
extension_contract_version must equal 1
no partial extension object set allowed
-> valid CORE_PLUS_EXTENSION_V1 state
```

### Closed object set

Application-owned SQLite objects must equal exactly one of:

```text
CORE_V1
OR
CORE_V1 + SERVICE_RECOGNITION_EXTENSION_V1
```

Unknown application tables/indexes/triggers remain validation failures.

SQLite-owned internal objects such as `sqlite_sequence` are not application schema objects and are excluded from the application-object signature, as they are today via the `sqlite_%` exclusion rule.

---

## 2.4 Compatibility bridge requirement

**The existing production baseline `b1442efc434716d35e21b9e3124c3b9cd2222fbe` is NOT rollback-compatible after Extension V1 installation.**

Its validator expects the previous complete schema signature and must not be declared a valid post-migration rollback target.

Before any extension installation, the implementation MUST produce and accept one exact **compatibility bridge baseline** that:

```text
A. accepts CORE_ONLY
B. accepts CORE_PLUS_EXTENSION_V1
C. does not require the extension to exist
D. maintains feed/change-index rows whenever Extension V1 exists
E. can run with NI-04 materialization publication disabled
```

Release evidence MUST record its exact Git SHA as:

```text
NI04_MAT_COMPAT_BASE_SHA=<exact accepted commit>
```

That exact future accepted SHA, not `b1442efc...`, is the oldest permissible application rollback target after migration.

---

## 2.5 Safe migration algorithm

Migration runs only inside the existing NI-02B single-writer process after it has acquired the normal writer lock.

Preconditions:

```text
Core V1 validation PASS
Extension state = absent OR complete V1
no partial extension objects
```

If absent, execute one SQLite transaction:

```text
BEGIN IMMEDIATE

CREATE projection_service_recognition_extension_meta
CREATE projection_service_recognition_feed
CREATE projection_registry_binding_change_index
CREATE exact required extension indexes if any

seed authoritative projection_registry_binding_change_index rows
in deterministic site_id,client_mac order

INSERT extension metadata version=1

validate Core V1
validate complete Extension V1

COMMIT
```

The existing connection remains:

```text
journal_mode=WAL
synchronous=FULL
foreign_keys=ON
```

No Core table rebuild is allowed by this migration.

---

## 2.6 Crash/interruption semantics

SQLite DDL/DML installation is one transaction.

Required outcomes:

```text
crash/kill before COMMIT
-> transaction rolls back
-> next startup sees valid CORE_ONLY
-> migration may retry

crash after COMMIT
-> next startup sees valid CORE_PLUS_EXTENSION_V1
-> no reinstall

partial application-owned extension object set
-> FAIL CLOSED
-> no writer start
-> no heuristic repair/drop/recreate
```

A partial state produced by external/manual mutation is an integrity incident, not an automatic migration case.

---

## 2.7 Running reader/writer compatibility

Extension installation MUST NOT occur while any long-lived production process still runs code whose projection validator accepts only the old whole-database signature.

Therefore all projection DB consumers must first be on the compatibility bridge code.

At minimum this includes:

```text
captive-portal main process / Admin projection readers
network-metadata-projection writer process
```

Any other production process instantiating the projection schema validator/read boundary is subject to the same rule.

WAL readers already holding an old read transaction may finish that snapshot, but no process using an old binary may remain the supported steady state after migration.

---

## 2.8 Post-migration producer behavior

Once Extension V1 exists, every compatible NI-02B writer MUST continue maintaining:

```text
projection_service_recognition_feed
projection_registry_binding_change_index
```

regardless of whether NI-04 publication mode is:

```text
off
shadow
serve
```

This prevents a silent feed gap during an application-level rollback of NI-04 publication.

Disabling Service Intelligence publication is allowed.
Stopping extension maintenance while the extension exists is not an accepted rollback mechanism.

---

## 2.9 Explicit no-destructive-rollback policy

After Extension V1 installation, rollback means application behavior rollback only.

Allowed:

```text
serve -> shadow
disable NI-04 materialized worker/publication
run NI04_MAT_COMPAT_BASE_SHA
leave extension tables intact
```

Forbidden without a new Owner-approved migration task:

```text
DROP extension tables
rewrite Core schema
restore b1442efc application code against migrated DB
manually edit sqlite_schema/sqlite_sequence
truncate extension state to make an old validator pass
```

No destructive schema downgrade is part of this task.

---

## 2.10 Deployment order under disk-I/O pressure

Mandatory production order:

### Stage R2-0 — Pre-migration evidence

```text
record current HEAD/tree
record DB size/user_version/core integrity
obtain a verified recoverable DB backup/snapshot
confirm no NI-04 backfill is running
```

### Stage R2-1 — Compatibility bridge, extension absent

```text
deploy accepted bridge code
materialization mode = off
extension installation = disabled
```

Restart **projection readers first**, including CaptivePortal/Admin, and verify Core-only reads.

Then restart NI-02B with the same bridge code and verify normal Core-only writer operation.

Record `NI04_MAT_COMPAT_BASE_SHA`.

### Stage R2-2 — Extension install

Enable the one-time extension installation path and restart **NI-02B alone**.

No NI-04 worker, shadow comparison or backfill may start concurrently with this startup.

Because production has known disk-I/O pressure, the deployment gate MUST verify before this restart that the service supervisor allows at least:

```text
TimeoutStartSec >= 180 seconds
```

If that cannot be guaranteed, migration is HOLD until the SysAdmin deployment contract supplies an adequate startup window.

After startup require:

```text
Core V1 validation PASS
Extension V1 validation PASS
quick_check/integrity gate PASS
NI-02B runtime healthy
normal source checkpoint progress resumes
```

### Stage R2-3 — Shadow materializer

Only after R2-2 PASS:

```text
start NI-04 worker in shadow
consume live feed first
then run bounded 24h backfill
```

### Stage R2-4 — Serve

Unchanged parent gates apply.

---

## 2.11 Applicable invariant

```text
Core V1 meaning is immutable.
Extension presence is explicit and versioned.
No old binary may be called rollback-compatible unless it accepts the migrated schema.
Migration interruption yields either complete absence or complete Extension V1.
Rollback never destroys source/projection evidence to regain binary compatibility.
```

---

## 2.12 Deterministic QA — TL-R2

Mandatory tests:

### R2-QA-01 — Core-only bridge

Bridge binary opens exact baseline Core-only DB and preserves existing behavior.

### R2-QA-02 — Core+Extension bridge

Same binary opens fully migrated DB with materialization publication OFF.

### R2-QA-03 — Old baseline rejection documented

`b1442efc...` against migrated fixture MUST be proven incompatible and MUST NOT appear in rollback instructions.

### R2-QA-04 — Transaction crash before each DDL/DML install point

After restart database is either exact Core-only or exact complete Extension V1; never partial.

### R2-QA-05 — Crash immediately after COMMIT

Restart validates Extension V1 and does not reinstall/reseed duplicates.

### R2-QA-06 — Partial/manual extension fixture

Any subset/mismatched DDL fails closed.

### R2-QA-07 — Unknown application object

Unknown non-`sqlite_%` object fails closed.

### R2-QA-08 — Core mutation under extension

Any changed Core V1 DDL fails even if Extension V1 is otherwise valid.

### R2-QA-09 — Extension installed / materialization OFF

New eligible NI-02B edge still receives feed row; new authoritative binding still updates change index.

### R2-QA-10 — Concurrent old reader prohibited gate

Deployment test/runbook proves migration cannot be marked PASS until all declared projection consumers report bridge identity.

### R2-QA-11 — Slow startup

Injected slow I/O/startup longer than normal but below the deployment startup budget completes without forced restart loop or partial schema.

### R2-QA-12 — Restart/retry idempotency

Repeated extension installer invocation against complete V1 makes zero schema/data duplication.

---

# 3. TL-R3 / P2 — Service Categories semantic compatibility

## 3.1 Final decision

**Retain accepted NI-04 V2 public semantics exactly.**

The independent `device_category_rollups` publication path from Contract v1 is withdrawn.

For Materialized V3:

```text
1. select Recent Services first
2. cap publication at 12 Services
3. derive Service Categories only from those selected Services
```

No independent category-history query may add a category whose Service is not present in the selected public Recent Services set.

This is a deliberate compatibility decision, not a new semantic version.

---

## 3.2 Store impact

`device_category_rollups` from parent §11.5 is **NOT REQUIRED and MUST NOT be created in V1 implementation**.

`device_service_rollups` already contains:

```text
service_id
service_category_id
service_category_display_name
last_observed_at
```

and is sufficient for bounded category publication.

This reduces storage and write amplification.

---

## 3.3 Exact Recent Services selection

At evaluation time `T`:

```text
recent_cutoff = T - 1 hour
```

Query materialized `device_service_rollups` for the active generation and exact Site+Device+MAC identity:

```text
WHERE last_observed_at >= recent_cutoff
ORDER BY last_observed_at DESC, service_id ASC
LIMIT 13
```

Why 13:

```text
rows 0..12 -> publish all available rows
row 13 exists -> publish first 12 and mark recognition coverage limited
```

Public `recent_services` contains at most the first 12 rows.

No NI-01 read, matcher call or historical observation aggregation is allowed.

---

## 3.4 Exact category derivation

From the at-most-12 selected public Recent Service rows only:

```text
for each service row in selected order:
    if category not yet present:
        category.last_observed_at = service.last_observed_at
```

Then publish categories ordered:

```text
last_observed_at DESC,
service_category_id ASC
```

Closed taxonomy limits remain unchanged.

A category may never be published solely because an older/non-selected Service row has that category.

---

## 3.5 Last Service Observation remains independent of category derivation

For the existing 24h meaning:

```text
window_cutoff = T - 24 hours
```

read the latest `device_service_rollups` row:

```text
WHERE last_observed_at >= window_cutoff
ORDER BY last_observed_at DESC, service_id ASC
LIMIT 1
```

Use its `last_service_observation_id` to publish the accepted last-observation fields.

This remains a bounded materialized read.

---

## 3.6 Applicable invariant

```text
Public Service Categories are a projection of the public Recent Services set.
They are not an independent claim about additional recent Services.
At most 12 Service rows participate in category derivation.
```

---

## 3.7 Deterministic QA — TL-R3

### R3-QA-01 — More than 12 recent Services

Create 13 materialized Service rollups.

Expected:

```text
recent_services = first 12 by accepted ordering
recognition_state = limited
categories derived only from those 12
```

### R3-QA-02 — 13th Service has unique category

Expected unique category of excluded 13th Service is NOT published.

### R3-QA-03 — Multiple selected Services share category

Exactly one category row; timestamp equals latest selected Service in that category.

### R3-QA-04 — Deterministic tie

Equal `last_observed_at` Service rows use `service_id ASC`; category ties use `service_category_id ASC`.

### R3-QA-05 — Category from old non-recent Service

Service rollup older than 60m must not contribute category even when still inside 24h Last Service window.

### R3-QA-06 — Read isolation

Category publication test substitutes NI-01/NI-02B/matcher with fail-if-called doubles; API still succeeds from materialized rows.

---

# 4. Work-package amendments

Only the following deltas apply.

## WP-B1 — NI-02B additive delivery extension

Add/replace:

```text
+ dual Core-only / Core+Extension validator
+ transactional Extension V1 installer
+ projection_registry_binding_change_index
+ deterministic authoritative-binding seed
+ bounded read_authoritative_binding_changes()
+ compatibility-bridge tests
+ post-migration rollback compatibility gate

- NI-04 durable cursor over projection_registry_binding_events.binding_event_id
```

Existing binding-event history remains otherwise untouched.

## WP-B2 — NI-04 materialized store

Change schema:

```text
registry_binding_event_id -> registry_binding_change_seq
last_binding_event_id     -> last_binding_change_seq
binding_event_id job key  -> binding_change_seq

REMOVE device_category_rollups
```

## WP-C — Background worker

Late binding trigger becomes:

```text
read_authoritative_binding_changes()
-> deterministic exact Site+MAC replay job
```

No global/cross-MAC replay.

## WP-D — Backfill

No semantic change.

Initial shadow/backfill must coexist with seeded binding-change index without double materialization; existing observation idempotency/generation keys are authoritative.

## WP-E — Materialized Admin read / V3

Change category path:

```text
query <=13 Service rollups
publish <=12
derive categories in memory from selected <=12 only
```

No category-rollup table/read.

## WP-F — Release / rollback

Add mandatory gates:

```text
compatibility bridge accepted before extension install
NI04_MAT_COMPAT_BASE_SHA recorded
b1442efc... explicitly forbidden as post-migration rollback target
extension install startup gate >=180s
no destructive schema rollback
```

---

# 5. Consolidated acceptance of Tech Lead findings

```text
TL-R1 / P1 = CLOSED
Decision = binding_event_id rejected as durable cursor;
           bounded AUTOINCREMENT per-Site+MAC change index accepted

TL-R2 / P1 = CLOSED
Decision = dual-compatible Core V1 + Extension V1 validator,
           transactional install,
           compatibility-bridge rollback floor,
           no destructive rollback

TL-R3 / P2 = CLOSED
Decision = preserve V2 category semantics;
           categories derive only from selected <=12 Recent Services;
           device_category_rollups removed
```

---

# 6. Final governance

```text
TASK = TASK-DTI-NI-04 — Background Materialized Service Intelligence
ARCHITECTURE CONTRACT = v1 + v1.1 Addendum

ARCHITECT OPEN_P0 = 0
ARCHITECT OPEN_P1 = 0
ARCHITECT OPEN_P2 = 0

READY_FOR_TECH_LEAD_FINAL IMPLEMENTATION TASK = YES

CODER = HOLD until Tech Lead issues umbrella implementation TASK
PRODUCTION CHANGE = NO
MIGRATION AUTHORIZATION = NO
DEPLOY AUTHORIZATION = NO

NI-05 = HOLD
NI-06 = HOLD
```

All Architecture Contract v1 decisions not explicitly amended above remain frozen.

