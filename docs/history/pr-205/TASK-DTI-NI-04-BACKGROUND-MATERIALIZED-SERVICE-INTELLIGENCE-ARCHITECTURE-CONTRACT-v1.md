# TASK-DTI-NI-04 — BACKGROUND MATERIALIZED SERVICE INTELLIGENCE
## ARCHITECTURE CONTRACT v1

**Проект:** CaptivPortal  
**Роль:** Architect  
**Дата:** 2026-10-13  
**Статус:** `COMPLETE / READY FOR TECH LEAD REVIEW`  
**Приоритет:** High / P1 product correctness + read-path architecture  

---

# 0. AUTHORITY / BASELINE / GOVERNANCE

Точный re-pin repository baseline:

```text
repository = ZaurNavi/CaptivePortal
HEAD = b1442efc434716d35e21b9e3124c3b9cd2222fbe
TREE = 1ea6a2d452a5c8147d2a9cdce6c5dcecd9900575
PR #204 / NI-04 Attribution Recovery V2 = merged
```

Этот контракт продолжает и НЕ отменяет принятый:

```text
TASK-DTI-NI-04 — Attribution Recovery Architecture Contract v1
```

Precedence для NI-04 read/materialization semantics:

```text
THIS CONTRACT
  > Attribution Recovery Architecture Contract v1
  > NI-04 Architecture Contract v1-R1
  > NI-04 original v1
```

Он НЕ является Coder TASK и НЕ разрешает production mutation.

```text
IMPLEMENTATION_AUTHORIZATION = NO
CODER = HOLD
MERGE = NO
DEPLOY = NO
PRODUCTION_CHANGE = NO
NI-05 = HOLD
NI-06 = HOLD
```

---

# 1. ARCHITECTURAL DEFECT — ROOT CAUSE

Текущая NI-04 реализация смешала два разных lifecycle:

```text
INGEST / ATTRIBUTION / RECOGNITION LIFECYCLE

и

ADMIN READ / PRESENTATION LIFECYCLE
```

Current path:

```text
Device Card GET
  -> read 24h NI-02B projection facts
  -> collect up to thousands of observation refs
  -> batch-read NI-01 evidence
  -> cross-store validation
  -> direct-SNI recognition
  -> aggregate 60m / 24h summary
  -> serialize
  -> HTTP response
```

Это архитектурно неверно для product read path.

Production уже доказал:

```text
661 device-linked outbound facts were available
NI-02B read ~= 0.53 s
first NI-01 batch of 256 exceeded the internal 5 s budget
full NI-04 request -> ServiceDeadline ~= 5.06 s
```

При этом подтверждённые YouTube events существовали.

Следовательно:

```text
DATA EXISTS
!=
PRODUCT CAN READ IT ON DEMAND WITHIN UI LATENCY
```

Root cause:

```text
SERVICE RECOGNITION WAS MODELED AS A QUERY-TIME COMPUTATION
INSTEAD OF A MATERIALIZED DERIVED PRODUCT.
```

Correct permanent principle:

```text
COMPUTE WHEN EVIDENCE ARRIVES.
PERSIST CONFIRMED DERIVATION.
DEVICE CARD ONLY READS MATERIALIZED STATE.
```

Increasing the request timeout is explicitly rejected as an architectural fix.

---

# 2. NON-NEGOTIABLE INVARIANTS

```text
I01  SNI alone never identifies a Device.
I02  Current IP alone never identifies historical Device identity.
I03  Only authoritative NI-02B Site+MAC -> device binding may attach a Service fact.
I04  No cross-Site or cross-Device merge.
I05  No MAC-randomization merge heuristic.
I06  Direct-SNI Service recognition semantics remain unchanged.
I07  IP-only exact Service inference remains forbidden.
I08  Pending/unavailable evidence is never promoted to a positive Service fact.
I09  Existing NI-02B committed edges remain immutable.
I10  Existing NI-01 evidence remains immutable and NI-04 reads it read-only.
I11  Global pending does not invalidate an already-confirmed Device fact.
I12  Missing/lagging materialization != no Service activity.
I13  Worker outage != erase previously confirmed facts.
I14  Replay cannot duplicate a positive observation.
I15  Rule generations cannot be silently mixed.
I16  Device Card never performs synchronous bulk NI-01 recognition in serve mode.
I17  Portal/Auth/CAPPORT/Omada/Fingerprint remain independent from NI-04 readiness.
I18  Materialized DB never stores raw SNI, raw DNS names, IP history or packet payload.
I19  No full-network-history completeness claim is introduced.
I20  NI-03 semantics are not changed by this task.
```

---

# 3. CLOSED ANSWERS AQ-01 ... AQ-12

## AQ-01 — Worker ownership

Decision:

```text
NEW SEPARATE NI-04 BACKGROUND PROCESS
logical owner = app/network_service_recognition
systemd role = network-service-recognition.service
```

Rejected:

```text
run inside captive-portal.service
run recognition inside NI-02B writer
run recognition inside Admin request
```

Reason:

```text
separate failure domain
single NI-04 writer
Portal/Auth isolation
no NI-02B recognition ownership leak
restart/backlog independent from Web
```

The service may use the same deployment OS account already able to read NI-01/NI-02B and write `/opt/CaptivePortal/data`, avoiding a new permission topology in v1.

## AQ-02 — New event source

Decision:

```text
NI-02B exposes an ADDITIVE durable Service-Recognition candidate edge feed.
```

A cursor over `event_at` is rejected because late pending resolution can create an edge with an old event time.

A cursor over `projected_at` alone is rejected because wall-clock timestamps are not a durable monotonic sequence and the current table has no contractually safe insertion cursor.

SQLite hidden `rowid` is rejected as public architecture because it is not a stable application contract.

Therefore NI-02B receives the smallest safe upstream addition: one monotonic outbox/feed table populated in the SAME transaction as a newly inserted edge.

## AQ-03 — Evidence validation boundary

All existing NI-04 positive-validation rules move unchanged into a reusable background evaluator.

The matcher remains pure and unchanged.

## AQ-04 — Durable storage

Decision:

```text
DEDICATED NI-04 SQLite
/opt/CaptivePortal/data/network_service_intelligence.sqlite3

single writer = network-service-recognition.service
Admin = read-only
```

No Service tables are added to NI-01 or NI-02B databases.

## AQ-05 — Stored entities

Minimum entities:

```text
materialization generation
positive service observation
per-device/service rollup
per-device/category rollup
per-device coverage/materialization state
worker checkpoint/runtime
bounded replay/backfill state
```

No raw hostname/IP payload store.

## AQ-06 — Device identity

Materialization requires current authoritative Site+MAC/device binding from NI-02B.

Facts are stored with exact:

```text
site_id + device_id + client_mac + binding provenance
```

They are never moved to another Device later.

## AQ-07 — 1h / 24h windows

Worker stores rollups.

Device Card only performs cutoff filtering over indexed rollup rows:

```text
last_observed_at >= now-1h
last_observed_at >= now-24h
```

No historical evidence scan and no mass aggregation occurs in the request.

## AQ-08 — Rule changes

Every exact taxonomy/manifest/ruleset tuple creates a distinct materialization generation.

Generations are never mixed in one public result.

A candidate generation backfills in shadow and becomes publication authority only by atomic promotion.

## AQ-09 — Backfill

Required V1 backfill covers the existing user-visible 24-hour NI-04 window only.

It is bounded, resumable and lower priority than live ingestion.

No 14-day historical product is invented by this task.

## AQ-10 — Degradation

Materialization health is a new independent dimension. It is not hidden inside `source_state` or `pipeline_attribution_state`.

## AQ-11 — Transition

```text
off -> shadow -> serve
```

Shadow builds and verifies store without changing current UI.

Serve has NO automatic per-request fallback to legacy on-demand recognition.

## AQ-12 — Minimum implementation scope

Change only:

```text
NI-02B additive edge feed/read support
NI-04 evaluator/worker/store/read service
Admin NI-04 composition/API/frontend contract
config/systemd/docs/tests for this lane
```

Keep all other product lanes untouched.

---

# 4. TARGET DATA FLOW

```text
                   NI-01 Network Metadata
              immutable DNS/TLS/QUIC evidence
                           |
                           | exact ref read
                           v
NI-02B Projection ---> NI-04 Background Worker
 authoritative edge      | validate provenance
 + durable edge feed     | direct-SNI matcher
 + Registry binding      | coverage update
                           v
              NI-04 Materialized SQLite
                   |               |
                   |               +--> checkpoints / health
                   |
                   v
         Materialized NI-04 Read Service
                   |
                   v
      Admin Device Service Intelligence API
                   |
                   v
               Device Card
```

Permanent request-path prohibition in `serve` mode:

```text
NO NI-01 bulk read
NO NI-02B 24h fact scan
NO matcher loop over historical refs
NO query-time recognition backfill
NO heavy aggregation
```

---

# 5. NI-02B ADDITIVE EDGE-COMMIT FEED

This is the only unavoidable NI-02B persistence extension.

It does NOT change attribution semantics, edge semantics, pending semantics, Registry semantics or source checkpoint semantics.

## 5.1 Extension table

Conceptual exact schema:

```text
projection_service_recognition_feed
-----------------------------------
feed_seq INTEGER PRIMARY KEY AUTOINCREMENT
edge_id TEXT NOT NULL UNIQUE
committed_at_utc TEXT NOT NULL

FOREIGN KEY(edge_id)
  REFERENCES device_network_metadata_edges(edge_id)
  ON DELETE CASCADE
```

Required index:

```text
(feed_seq)
```

The INTEGER PRIMARY KEY already provides this ordering; no secondary time index is required in V1.

## 5.2 Atomicity

When NI-02B inserts a NEW `device_network_metadata_edges` row, a feed row is appended only if the edge is an NI-04 candidate:

```text
device_endpoint_role = src
direction = outbound
peer_scope = external
source_event_family IN (dns, tls, quic)
```

For that bounded subset:

```text
INSERT edge
INSERT recognition_feed(edge_id)
COMMIT
```

Inbound/local/unknown-direction edges do NOT receive feed rows in V1. This is deliberate write-amplification minimization.

must occur in the SAME NI-02B SQLite transaction.

If edge insert is an idempotent replay and the edge already exists:

```text
NO second feed row
```

`AUTOINCREMENT` is mandatory so a deleted retained feed row's sequence is never reused.

## 5.3 Retention

Feed rows live no longer than their referenced edge.

When authorized NI-02B retention deletes an edge, FK cascade removes its feed row.

The feed is not a second evidence history.

## 5.4 Version boundary

Do NOT silently redefine NI-02B core schema v1.

Implement this as an explicitly versioned additive extension:

```text
projection_service_recognition_feed_contract_version = 1
```

with its own extension validation metadata.

Core projection contract/version and edge schema remain V1.

No existing edge table rebuild is required.

## 5.5 Internal read API

NI-02B must expose a read-only boundary equivalent to:

```text
read_service_recognition_feed(
    after_feed_seq,
    limit <= 256,
    deadline
)

-> ordered feed rows + exact edge DTOs
```

Order:

```text
feed_seq ASC
```

Also expose:

```text
recognition_feed_bounds()
-> min_retained_feed_seq | null
-> max_feed_seq | null
```

These methods never call NI-02A and never alter projection state.

---

# 6. EXISTING REGISTRY EVENT FEED — REUSED

Late Registry binding must be handled because an edge may be created before `device_id` becomes authoritative.

Do NOT invent a second Registry notification mechanism.

Reuse existing immutable:

```text
projection_registry_binding_events.binding_event_id
```

with a bounded internal reader:

```text
read_registry_binding_events(
    after_binding_event_id,
    limit <= 128,
    deadline
)
```

When a transition establishes an authoritative `site_id + client_mac -> device_id` binding, NI-04 schedules a targeted bounded replay for that exact Site+MAC.

No cross-MAC backfill is allowed.

---

# 7. DEVICE-SCOPED COVERAGE READ — ADDITIVE, READ-ONLY

NI-04 still needs current coverage semantics from Attribution Recovery V2, but this must not cause a 24h fact scan in the Admin request.

Add a small NI-02B internal method equivalent to:

```text
read_recognition_device_coverage(
    site_id,
    device_id,
    client_mac,
    from_utc,
    to_utc,
    deadline
)
```

Returns only:

```text
projection_runtime_state
projection_safe_reason
identity_binding_state
bound_device_id
device_linked_pending_count
```

It does NOT return the 24h fact list.

Worker calls it in background and persists the resulting coverage snapshot in the NI-04 store.

Admin does NOT call it in `serve` mode.

---

# 8. BACKGROUND RECOGNITION WORKER

## 8.1 Process

Logical entry point:

```text
app/network_service_recognition/worker.py / cli.py
```

Deployment unit:

```text
network-service-recognition.service
```

It is independent from:

```text
captive-portal.service
network-metadata-projection.service
```

Recommended systemd ordering:

```text
After=network-metadata-projection.service
```

but NOT hard `Requires=`.

An NI-02B restart/outage degrades recognition; it must not cause Portal shutdown.

## 8.2 Loop priority

Each worker cycle uses this priority:

```text
1. live edge feed
2. authoritative binding replay work
3. device coverage reconciliation
4. historical 24h backfill
5. retention/maintenance
```

Backfill runs only when live feed has no backlog.

## 8.3 Live batch bounds

```text
edge feed rows per batch <= 256
NI-01 exact-ref read batch <= 256
binding events per batch <= 128
unique touched Devices per coverage reconciliation <= 128
memory is batch-bounded
```

No unbounded SELECT and no unbounded list accumulation.

## 8.4 Poll cadence

```text
idle poll interval = 1 second
```

An idle poll performs no NI-04 DB write unless health persistence is due.

Routine health heartbeat persistence:

```text
<= once per 10 seconds when unchanged
```

## 8.5 Batch processing deadline

A single live source/evidence batch has a worker-local upper execution bound:

```text
30 seconds
```

If the upstream read does not complete safely:

```text
no feed checkpoint advance
materialization state -> lagging/source_unavailable
retry later
```

No observation is skipped merely to recover health.

---

# 9. REUSABLE NI-04 EVALUATOR

Current query-time validation logic MUST NOT be copied into a second divergent implementation.

Refactor it into one NI-04-owned pure evaluator equivalent to:

```text
ServiceRecognitionEvaluatorV1.evaluate(
    projection_fact,
    source_evidence,
    authoritative_identity,
    recognition_bundle,
    evaluated_at_utc
)
```

Both legacy shadow comparison and background materializer may call the same evaluator during transition.

After final cutover the materializer is the normal caller.

## 9.1 Mandatory validation before positive recognition

All must remain true:

```text
site exact match
client_mac canonical and exact
current projection binding authoritative
bound_device_id exact
edge device_endpoint_role = src
edge direction = outbound
edge peer_scope = external
edge source family = tls | quic for positive recognition
source observation ref exact
source generation exact
capture source exact
network scope exact
capture-scope digest exact
event_at exact
endpoint tuple exact when retained
exactly one source payload family
SNI presence = observed_retained
canonical hostname valid
active admitted rule eligible
unique Service resolution
ruleset/taxonomy/manifest cross-digests valid
```

The existing `match_direct_sni_v1()` remains semantic authority.

For every safely evaluated authoritative Device candidate, including an `unknown` result with no positive Service, the worker MUST create/update `device_materialization_state`. Positive observation rows are optional only when there is no positive result; coverage progress is not optional. This is what allows a later negative claim to distinguish "safely evaluated with no supported Service" from "never materialized".

## 9.2 DNS

DNS remains non-positive in V1.

It may still mark recognition coverage limited under the already accepted NI-04 rules.

## 9.3 Missing/expired source evidence

If source evidence needed for an edge is unavailable/expired:

```text
NO positive Service observation
coverage is limited/partial
```

If the failure is a store/read failure rather than legitimate retention expiry:

```text
batch checkpoint does not advance
```

---

# 10. MATERIALIZED STORE — OWNERSHIP AND SQLITE CONTRACT

Path:

```text
/opt/CaptivePortal/data/network_service_intelligence.sqlite3
```

Single writer:

```text
network-service-recognition.service
```

Readers:

```text
Admin materialized read service, query_only
```

SQLite policy:

```text
journal_mode = WAL
synchronous = FULL
foreign_keys = ON
busy_timeout = 500 ms
wal_autocheckpoint = 1000
```

No shared write ownership with Admin.

---

# 11. MATERIALIZED STORE — LOGICAL SCHEMA

Exact physical column ordering belongs to the implementation TASK, but the entities, keys and semantics below are frozen.

## 11.1 `service_materialization_schema`

Singleton:

```text
schema_version = 1
materialization_contract_version = 1
algorithm_version = background-service-materialization.v1
created_at_utc
```

## 11.2 `service_materialization_generations`

One row per exact admitted artifact tuple.

Required:

```text
generation_id UUID PRIMARY KEY
state:
    building | active | superseded | expired | failed

taxonomy_id/version/digest
knowledge_manifest_id/version/digest
ruleset_id/version/digest
build_started_at_utc
backfill_from_utc
live_feed_start_seq
activated_at_utc nullable
superseded_at_utc nullable
publishable_until_utc
```

At most one generation may be `active`.

## 11.3 `service_recognition_observations`

Immutable positive facts only.

Required:

```text
service_observation_id TEXT PRIMARY KEY
generation_id
edge_id
source_observation_ref
site_id
device_id
client_mac
registry_binding_event_id
observed_at
source_event_family = tls | quic
service_id
organization_id
service_category_id
evidence_strength_class = strong
support_state = directly_supported
matched_rule_id
materialized_at_utc

UNIQUE(generation_id, edge_id)
```

`service_observation_id` remains deterministic from the accepted NI-04 observation semantics; replay must reproduce it.

Forbidden columns:

```text
raw SNI
raw DNS name
src/dst IP
ports
packet payload
full NI-01 JSON
```

## 11.4 `device_service_rollups`

One display row per Service per Device per generation:

```text
PRIMARY KEY(generation_id, site_id, device_id, service_id)

client_mac
service_id + display_name
organization_id + display_name
service_category_id + display_name
last_observed_at
last_service_observation_id
```

Repeated detections update `last_observed_at` only when the new confirmed observation is later.

They do not create duplicate UI rows.

## 11.5 `device_category_rollups`

```text
PRIMARY KEY(generation_id, site_id, device_id, service_category_id)

client_mac
service_category_id + display_name
last_observed_at
```

## 11.6 `device_materialization_state`

One row per Device/current generation:

```text
PRIMARY KEY(generation_id, site_id, device_id)

client_mac
identity_binding_state
registry_binding_event_id
source_state
pipeline_attribution_state
device_linked_pending
coverage_evaluated_at_utc
coverage_valid_from_utc
last_recognition_limitation_at nullable
last_materialized_at_utc nullable
```

This is coverage state, not positive evidence.

## 11.7 `service_materialization_checkpoints`

One row per generation:

```text
generation_id PRIMARY KEY
last_edge_feed_seq
last_binding_event_id
backfill_state:
    not_started | running | complete | blocked
backfill_from_utc
backfill_site_id nullable
backfill_event_at nullable
backfill_edge_id nullable
updated_at_utc
```

## 11.8 `service_binding_replay_jobs`

Bounded durable queue for late authoritative Registry binding.

```text
job_id deterministic PRIMARY KEY
binding_event_id UNIQUE
site_id
client_mac
device_id
from_utc
to_utc
cursor_event_at nullable
cursor_edge_id nullable
state = pending | running | complete | terminal
```

No raw network evidence is copied into this queue.

## 11.9 `service_materialization_runtime`

Singleton operational state:

```text
runtime_state:
    initializing
    backfilling
    usable
    lagging
    source_unavailable
    recognition_unavailable
    capacity_halted
    blocked_conflict
    stopping

safe_reason nullable
active_generation_id nullable
last_upstream_poll_at_utc nullable
last_successful_commit_at_utc nullable
observed_feed_highwater_seq nullable
committed_feed_cursor_seq nullable
last_coverage_reconcile_at_utc nullable
updated_at_utc
```

---

# 12. IDEMPOTENCY / CHECKPOINT / CRASH CONTRACT

For every live feed batch:

```text
READ NI-02B feed
READ exact NI-01 evidence
VALIDATE / RECOGNIZE in memory
BEGIN IMMEDIATE on NI-04 store
  INSERT OR VERIFY deterministic positive facts
  UPDATE rollups
  UPDATE device materialization state
  ADVANCE NI-04 feed checkpoint
COMMIT
```

Critical invariant:

```text
MATERIALIZATION MUTATION
AND
NI-04 CONSUMER CHECKPOINT
ARE ONE NI-04 STORE TRANSACTION.
```

Crash cases:

### Before commit

```text
facts absent
checkpoint old
replay same feed rows
```

### After commit

```text
facts present
checkpoint advanced
no duplicate replay
```

### Duplicate source delivery

```text
UNIQUE(generation_id, edge_id)
+ deterministic service_observation_id
=> no duplicate positive fact
```

The worker never writes an acknowledgement into NI-02B.

NI-02B feed remains producer-owned immutable delivery evidence until normal NI-02B retention removes the underlying edge.

---

# 13. LATE PENDING RESOLUTION

The accepted NI-02B pending algorithm remains unchanged.

Two cases matter.

## 13.1 Device src edge already existed, peer remained pending

The original authoritative outbound src edge is already sufficient for direct-SNI Service recognition.

It is processed when its edge-feed event arrives.

Later peer resolution does NOT rewrite or re-recognize that immutable src edge.

Coverage reconciliation eventually clears `device_linked_pending` when the pending row disappears.

## 13.2 Device src role itself was pending

No outbound Device edge existed initially.

When retry later resolves src:

```text
NI-02B creates a NEW src edge
same transaction appends NEW feed_seq
NI-04 consumes it
positive recognition may then materialize
```

No scan of old pending history is required.

---

# 14. LATE REGISTRY BINDING

An edge can exist before Device Registry binding becomes authoritative.

Worker behavior:

```text
edge feed arrives
binding not authoritative
-> do not attach Service fact
-> feed may still advance
```

Safety is preserved because existing Registry binding-event history provides a later trigger.

When authoritative binding event appears:

```text
create deterministic binding replay job
scan ONLY that Site+MAC
ONLY within materialization retention / required product window
pages <= 128 edges
run the same evaluator
```

No cross-MAC search.

No guessed Device ID.

---

# 15. IDENTITY CONFLICT / MAC RANDOMIZATION

## Identity conflict

If NI-02B reports/enters conflict:

```text
NO new unsafe Device materialization
runtime/coverage degraded or blocked
existing immutable positive observations are not reassigned
```

Admin may show an existing positive fact only when request identity still exactly matches:

```text
site_id + device_id + canonical_mac
```

Otherwise it is not returned.

## MAC randomization

New MAC means a distinct identity unless Registry itself authoritatively exposes a relationship under a separately accepted identity contract.

NI-04 does not merge Service history across MACs.

---

# 16. ROLLING WINDOW SEMANTICS

Public semantics remain:

```text
Recent Services = last 60 minutes
Last Service Observation = last 24 hours
Service Categories = categories of current Recent Services
```

The request path does NOT recompute historical observations.

At request evaluation time `T`:

```text
recent_cutoff = T - 1 hour
window_cutoff = T - 24 hours
```

Read queries are limited to rollup rows:

```text
Recent Services:
  device_service_rollups
  WHERE last_observed_at >= recent_cutoff
  ORDER BY last_observed_at DESC, service_id
  LIMIT 12

Categories:
  device_category_rollups
  WHERE last_observed_at >= recent_cutoff
  ORDER BY last_observed_at DESC, service_category_id
  LIMIT 10

Last Service Observation:
  device_service_rollups
  WHERE last_observed_at >= window_cutoff
  ORDER BY last_observed_at DESC, service_id
  LIMIT 1
```

This is cheap time filtering over pre-aggregated state, not Service recognition or historical aggregation.

Therefore an item naturally leaves the 60m/24h product window even if:

```text
no new packet arrives
worker is idle
Admin has not opened the page
```

No expiry write is required merely to make UI time semantics correct.

---

# 17. FRESHNESS / NEGATIVE CLAIM SAFETY

A negative statement is stronger than a positive stored fact.

`no_supported_result_observed_with_sufficient_coverage` is allowed only if ALL hold for the requested Device/window:

```text
identity authoritative
active generation publishable
materialization runtime current/usable
live edge feed caught up
required 24h backfill complete
coverage_valid_from_utc <= now-24h
source_state = usable
pipeline_attribution_state = usable
device_linked_pending = false
recognition_state = usable
last_recognition_limitation_at is null OR < now-24h
```

If any condition fails:

```text
NO negative sufficient-coverage claim.
```

Positive confirmed facts may still be displayed with degraded coverage.

---

# 18. MATERIALIZATION LAG CONTRACT

Target normal-operation Service detection latency:

```text
NI-02B edge commit
  -> durable NI-04 materialization

p95 <= 10 seconds
p99 <= 30 seconds
```

Materialization state:

```text
current:
  feed cursor == observed highwater
  AND last successful upstream verification age <= 10s

lagging:
  healthy store but backlog exists
  OR last successful verification age >10s and <=120s

unavailable:
  required source cannot be safely read
  OR verification age >120s
```

A backlog never causes cursor skipping.

---

# 19. RULE / KNOWLEDGE VERSIONING

Every exact tuple:

```text
taxonomy digest
knowledge manifest digest
ruleset digest
```

defines one materialization generation.

## 19.1 New bundle

When worker sees a different admitted tuple:

```text
create BUILDING generation
capture live-feed start highwater
consume new live feed for candidate generation
backfill required 24h
verify candidate
```

The previous generation remains publication authority until explicit atomic promotion.

## 19.2 Promotion

Promotion transaction:

```text
old active -> superseded
candidate building -> active
active_generation_id -> candidate
```

No public response may combine observations/rollups from two generations.

## 19.3 Expired artifact

Each generation stores `publishable_until_utc` from the admitted artifact eligibility boundary.

After that instant:

```text
generation is not valid for new supported-result publication
```

If no replacement generation is active:

```text
recognition coverage = unavailable/limited
negative claims forbidden
```

Persisted old rows are retained for bounded rollback/audit but are not silently re-labelled as current-rule results.

## 19.4 Replay

Rule change replay uses retained NI-02B/NI-01 evidence only.

If source evidence required for a historical event has expired:

```text
no new positive result can be invented
candidate coverage remains partial for that portion
```

---

# 20. RETENTION / PRIVACY / CAPACITY

## 20.1 Product exposure

Public Service Intelligence remains a 24-hour product.

No 14-day Service-history API is introduced.

## 20.2 Internal positive-observation retention

Materialized positive observations may be retained for:

```text
14 days maximum
```

because NI-02B itself has a 14-day evidence horizon and this supports bounded replay/diagnosis without retaining raw SNI/IP.

Rows older than 14 days are deleted by NI-04-owned retention.

## 20.3 Rollup retention

Rollup rows whose `last_observed_at < now-14d` may be removed.

## 20.4 Generation retention

Keep at most:

```text
1 active generation
1 immediate superseded generation
```

Superseded generation grace:

```text
24 hours
```

unless Owner explicitly freezes a rollback candidate longer for a release incident.

## 20.5 DB cap

V1 hard default:

```text
MAX_DB_BYTES = 512 MiB
```

Allowed deployment range if exposed as config:

```text
128 MiB .. 2 GiB
```

Default remains 512 MiB.

At capacity pressure:

```text
run authorized retention
attempt bounded WAL maintenance
if safe headroom still unavailable:
  runtime = capacity_halted
  stop cursor advancement
  preserve already committed facts
```

Forbidden response:

```text
delete current supported facts solely to look healthy
skip feed rows
weaken synchronous=FULL
```

No automatic VACUUM in normal runtime.

---

# 21. INITIAL MIGRATION / BACKFILL

The new store starts empty, but the existing user-visible 24h history must not be intentionally discarded.

## 21.1 Required backfill window

```text
now - 24h .. backfill snapshot cutoff
```

This exactly preserves the existing public NI-04 window.

V1 does NOT introduce a requirement to reconstruct 14 days of Service history.

## 21.2 Live-first handoff

At generation creation:

```text
H = current NI-02B edge-feed highwater
store live_feed_start_seq = H
```

Then:

```text
live consumer starts with feed_seq > H
backfill separately scans the prior 24h projection window
```

This ensures new events do not wait for historical backfill.

Idempotency handles overlap between the two lanes.

## 21.3 Backfill paging

Per Site:

```text
ordered by (event_at, edge_id)
page <= 128 edges
```

Use existing bounded projection index/read boundary.

Backfill performs at most:

```text
1 page per second
```

and yields whenever live feed backlog exists.

## 21.4 Backfill source evidence

Only exact retained NI-01 evidence is accepted.

Expired/unavailable evidence:

```text
no positive fact
window coverage partial/limited
```

## 21.5 Resumability

Backfill cursor is durable in NI-04 store.

Restart resumes from the committed Site/event/edge cursor.

No full restart-from-zero is required.

---

# 22. COVERAGE RECONCILIATION

Feed events alone cannot prove when an existing `device_linked_pending` row disappears without producing another relevant src edge.

Therefore NI-04 runs a bounded background coverage reconciliation.

For touched/recent Devices and Devices currently marked pending:

```text
call NI-02B read_recognition_device_coverage()
update device_materialization_state
```

Bounds:

```text
<= 128 Devices per pass
passes every 30 seconds when work exists
```

No Admin request performs this reconciliation.

This is intentionally background work.

---

# 23. ADMIN MATERIALIZED READ SERVICE

New read boundary:

```text
MaterializedDeviceServiceReadService
```

Input remains:

```text
site_id
device_id
canonical_mac
evaluated_at_utc
deadline
```

The canonical MAC still comes from the existing authorized Device gateway.

The service opens only:

```text
network_service_intelligence.sqlite3
```

in query-only mode.

It MUST NOT open:

```text
network_metadata.sqlite3
network_metadata_projection.sqlite3
```

in `serve` mode.

## 23.1 Read bounds

One request performs at most:

```text
1 generation/runtime read
1 device materialization-state read
1 recent-service indexed read <=12 rows
1 category indexed read <=10 rows
1 last-observation indexed read <=1 row
```

No query returns more than 32 product rows total.

## 23.2 Latency SLO

Materialized SQLite read service:

```text
p95 <= 50 ms
p99 <= 100 ms
```

End-to-end authenticated Admin API on production-class host:

```text
p95 <= 250 ms
p99 <= 500 ms
hard NI-04 materialized read budget <= 1 second
```

Failure is returned honestly; request-time legacy recognition is never invoked automatically.

---

# 24. PUBLIC API VERSIONING

Existing route remains:

```text
GET /admin/api/v1/sites/{site_id}/devices/{device_id}/service-intelligence
```

V2 fields have defined upstream meanings and must not be repurposed to hide materializer lag.

Therefore serve-mode response becomes:

```text
api_version = admin.device.service-intelligence.v3
schema_version = 3
```

All V2 fields retain their semantics.

Add exactly one nested object:

```text
materialization: {
    state:
        current | backfilling | lagging | unavailable | capacity_halted | conflict,

    window_coverage_state:
        complete | partial | unknown,

    last_successful_update_at_utc:
        timestamp | null,

    lag_seconds:
        non-negative integer | null
}
```

No internal feed sequence/checkpoint is public.

## 24.1 New evidence state

Add:

```text
materialization_incomplete
```

Exact evidence-state precedence:

```text
identity != authoritative
    -> identity_pending

last confirmed Service exists
    -> supported_results_present

materialization not current/complete
    -> materialization_incomplete

source_state != usable
    -> insufficient_source_coverage

pipeline_attribution_state != usable
OR device_linked_pending=true
    -> insufficient_attribution

recognition_state != usable
    -> recognition_limited

else
    -> no_supported_result_observed_with_sufficient_coverage
```

A positive fact is never hidden solely because materialization is lagging.

---

# 25. UI CONTRACT

UI remains the existing Service Intelligence section.

No redesign of Device Card.

Add one line in Freshness / Coverage:

```text
Materialization: <state>
```

## 25.1 Positive + lag

```text
Confirmed stored service evidence is shown. Background Service Intelligence is behind; newer activity may be missing.
```

Cards remain visible.

## 25.2 No positive + incomplete materialization

```text
Service Intelligence is not fully materialized for this window; activity is unknown.
```

Never:

```text
No services used
No activity
```

## 25.3 Current/complete

Existing Attribution Recovery V2 wording remains valid.

---

# 26. MODE / SHADOW / CUTOVER CONTRACT

Introduce ONE deployment state:

```text
NETWORK_SERVICE_MATERIALIZATION_MODE = off | shadow | serve
```

Default:

```text
off
```

Existing:

```text
WEB_ADMIN_DEVICE_SERVICE_INTELLIGENCE_ENABLED
```

continues to own whether the product section/API exists.

## `off`

```text
new worker/store not required
legacy on-demand path remains for compatibility before cutover
```

## `shadow`

```text
worker/store active
legacy API remains publication path
materialized result is compared/tested but not user-visible authority
```

## `serve`

```text
Admin uses materialized read only
no NI-01/NI-02B bulk read from Admin
no automatic fallback to legacy per request
```

Explicit Owner rollback may change mode or disable the existing NI-04 product flag.

No request may silently fallback because the materialized store is unhealthy.

---

# 27. SHADOW ACCEPTANCE BEFORE CUTOVER

Before `serve`, candidate must prove:

```text
active materialization generation valid
required 24h backfill complete
live feed caught up
no feed retention gap
coverage reconciliation current
store quick_check = ok
no source mutation
```

For deterministic sampled Devices, compare at the SAME evaluation time:

```text
legacy confirmed positive Service set
vs
materialized confirmed positive Service set
```

Required:

```text
NO extra materialized positives
NO cross-Device mismatch
all expected materialized positives have exact lineage
```

Legacy deadline failures do not count as a false mismatch; they are recorded separately.

Control regression must include:

```text
MAC = C2:32:F5:4E:43:61
Device ID = b7a34589-021a-5b2e-8e22-fdee235543ce
expected admitted YouTube evidence where retained
```

---

# 28. FAILURE MATRIX

| Failure | Worker behavior | Stored positives | Negative claim | Admin |
|---|---|---|---|---|
| NI-01 temporary unavailable | no cursor advance | preserve | forbidden | show stored + degraded materialization |
| NI-02B feed unavailable | no cursor advance | preserve | forbidden | show stored + degraded |
| feed backlog | catch up bounded | preserve | forbidden while incomplete | show stored + lagging |
| feed retention gap | enter recovery backfill | preserve | forbidden | partial/unknown coverage |
| Registry binding pending | no Device fact yet | preserve others | forbidden for affected identity | identity pending |
| identity conflict | fail closed / blocked | never reassign | forbidden | confirmed exact old identity only if still matches |
| source evidence expired | no new positive | preserve prior | limited | degraded |
| bundle invalid | stop new recognition | preserve active admitted generation if still valid | forbidden | recognition unavailable/degraded |
| active artifact expired | no current supported publication from expired generation | retained internally | forbidden | recognition limited/unavailable |
| NI-04 DB busy | retry bounded | preserve | forbidden if lag develops | degraded / 503 if unreadable |
| NI-04 DB corrupt/unreadable | stop writer/read | unavailable to API | forbidden | 503, no legacy fallback |
| capacity exceeded | halt cursor | preserve | forbidden | stored + capacity_halted if readable |
| worker restart | resume checkpoint | preserve | based on lag until caught up | stored + lagging |
| Captive Portal restart | no materializer reset | preserve | unchanged | independent |

---

# 29. RESOURCE BUDGETS

## 29.1 Live lane

```text
batch <= 256 feed rows
max one active worker batch
no intentional delay while backlog exists
batch deadline <= 30s
```

## 29.2 Backfill lane

```text
batch <= 128 edges
<= 1 backfill batch / second
backfill yields whenever live backlog exists
```

## 29.3 Coverage lane

```text
<=128 Devices/pass
normal retry interval >=30s per Device
```

## 29.4 Memory

Acceptance target:

```text
worker steady-state RSS delta <= 64 MiB
```

excluding shared OS page cache.

## 29.5 I/O

The NI-02B feed is candidate-only specifically to bound new write amplification.

Mandatory lab gate before production activation:

```text
NI-02B representative-load p95 batch-commit latency regression <= 10%
NI-02B projected-edge throughput regression <= 5%
no checkpoint/replay semantic regression
no unexpected full-table scan introduced by feed reads
```

If the gate fails, `serve` activation is blocked; the architecture must be reviewed rather than weakening durability.

Forbidden:

```text
periodic full-table NI-01 scan
periodic full-table NI-02B edge scan
Admin-triggered backfill
unbounded SQLite transaction
VACUUM in hot path
one fsync per individual evidence event by design
```

Positive observations and rollup mutations for one batch are committed together.

---

# 30. OBSERVABILITY

Safe counters/gauges:

```text
feed_highwater_seq
feed_cursor_seq
feed_backlog_rows
live_batches_total
feed_rows_examined_total
candidate_edges_total
source_evidence_rows_read_total
service_positive_observations_total
recognition_unknown_total
recognition_limited_total
idempotent_replays_total
binding_replay_jobs_total
binding_replay_edges_total
coverage_reconciliations_total
backfill_pages_total
backfill_edges_total
materialization_lag_seconds
last_successful_commit_age_seconds
source_failures_total
store_failures_total
capacity_halt_total
```

Operational telemetry MUST NOT contain:

```text
MAC
device_id
IP
SNI
DNS name
edge_id
observation_id
binding_id
raw payload
```

Detailed lineage remains in protected NI-04 SQLite only.

---

# 31. UPSTREAM CHANGES — JUSTIFICATION

Exactly one NI-02B write-path addition is accepted:

```text
atomic Service-Recognition candidate feed row
```

Why unavoidable:

```text
event_at cursor misses late-resolved old events
projected_at timestamp is not monotonic authority
rowid is not an application contract
periodic full scan violates resource requirement
cross-DB callback without durable outbox can lose events after crash
```

Therefore a durable producer-owned monotonic sequence is the minimal mechanism that satisfies:

```text
no silent skip
late pending recovery
restart/replay
bounded incremental reads
```

Other NI-02B changes are read-only helper APIs only.

No NI-02A change is needed.

No NI-01 change is needed.

---

# 32. UNTOUCHED MODULES / CONTRACTS

Must remain untouched except regression tests/documentation where needed:

```text
NI-01 acquisition/parser/writer/schema
NI-02A authority algorithm/schema
NI-02B endpoint-attribution algorithm
NI-02B pending retry rules
NI-02B immutable edge semantics
NI-02B source checkpoint semantics
NI-03 Protocol Intelligence public behavior
Fingerprint Sensor / Classification
Current State
Visit Lifecycle
Guest Traffic / Session Traffic
Omada provider behavior
Portal/Auth/CAPPORT
Access Policy
Settings mutation semantics outside new NI-04 setting registration
```

Frozen NI-04 knowledge artifacts and `match_direct_sni_v1()` are reused, not redesigned.

---

# 33. IMPLEMENTATION WORK PACKAGES

These are implementation boundaries for Tech Lead; they are NOT authorization.

## WP-B1 — NI-02B additive delivery extension

```text
edge commit feed extension schema
atomic writer insertion
feed bounds/read API
Registry-event bounded reader
coverage-only bounded reader
migration/compatibility tests
```

No attribution semantic change.

## WP-B2 — NI-04 materialized store foundation

```text
schema/repository
single-writer lock
FULL/WAL policy
generation/checkpoint/runtime
idempotency/crash tests
retention/capacity
```

## WP-C — Background worker/evaluator

```text
shared evaluator extraction
live feed consumer
NI-01 exact evidence batches
rollup writer
coverage reconciliation
late Registry binding replay
graceful shutdown/telemetry
```

## WP-D — 24h bounded backfill

```text
per-Site cursor
live-first priority
128-row pages
resumability
coverage-completeness gates
```

## WP-E — Materialized Admin read / API V3

```text
query-only store reader
Admin composition change
API v3 serializer
frontend minimal V3 support
NO request-time source reads in serve mode
```

## WP-F — Shadow comparison / activation gates

```text
off -> shadow -> serve
YouTube regression
performance/I/O tests
failure/restart tests
rollback drill
```

Tech Lead may deliver these as one umbrella implementation TASK with explicit ordered work packages and independent commits/gates.

---

# 34. DETERMINISTIC ACCEPTANCE TESTS

## AC-M01 — Background positive detection

Without any Admin request:

```text
valid authoritative edge + admitted direct SNI
-> durable service_recognition_observation
-> rollup updated
```

## AC-M02 — Device Card read isolation

In `serve` mode, test substitutes NI-01 and NI-02B readers that raise if called.

Device Service API must still return stored result.

## AC-M03 — YouTube production regression

For the accepted control identity, retained authoritative YouTube evidence materializes and appears even when unrelated/global pending exists.

## AC-M04 — Pending src late resolution

Initial src unavailable -> no positive.

Retry creates src edge/feed row -> exactly one positive materializes.

## AC-M05 — Peer pending only

Authoritative outbound src edge + peer pending -> positive may materialize immediately; coverage remains partial until pending clears.

## AC-M06 — Pending clears without new relevant src edge

Coverage reconciliation clears `device_linked_pending`; positive fact is not duplicated.

## AC-M07 — Late Registry binding

Edge first appears without authoritative device binding -> no fact.

Later authoritative binding event -> targeted replay -> fact materializes once.

## AC-M08 — Identity conflict

No fact is moved to another device_id/MAC.

## AC-M09 — Crash before NI-04 commit

Checkpoint unchanged; replay materializes exactly once.

## AC-M10 — Crash after NI-04 commit

Fact and checkpoint are both committed; restart does not duplicate.

## AC-M11 — Feed duplicate/idempotency

Repeated delivery of same feed row creates no duplicate observation/rollup.

## AC-M12 — Feed retention gap

Worker detects cursor below retained feed floor, enters recovery/backfill and forbids sufficient-coverage negative claim until recovered.

## AC-M13 — 60-minute expiry

At T+60m boundary, Service leaves Recent list via indexed cutoff even with no worker write and no new network event.

## AC-M14 — 24-hour expiry

At T+24h boundary, Last Service Observation disappears from current product window without source re-scan.

## AC-M15 — Worker stopped

Stored positive remains visible with materialization degraded/lagging; no new activity completeness claim.

## AC-M16 — No-result safety

Empty rollups + incomplete materialization MUST NOT produce `no_supported_result_observed_with_sufficient_coverage`.

## AC-M17 — Rule generation isolation

Old and candidate generations never appear in one response.

## AC-M18 — Rule promotion

Candidate must complete required backfill/live catch-up before atomic active-generation switch.

## AC-M19 — Expired rules

Expired generation is not silently published as current admitted recognition.

## AC-M20 — Privacy

Materialized DB schema/content contains no SNI/DNS/IP/packet payload columns.

## AC-M21 — Admin latency

Materialized API meets p95/p99 SLO on production-class lab load.

## AC-M22 — Event-to-store latency

Normal live ingestion meets p95 <=10s / p99 <=30s.

## AC-M23 — Resource isolation

Backfill pauses while live backlog exists and does not materially regress Portal/Auth/CAPPORT differential latency.

## AC-M24 — Upstream immutability

NI-01 source DB and existing NI-02B evidence rows are unchanged by NI-04 worker.

## AC-M25 — No automatic legacy fallback

Materialized store failure in `serve` mode returns degraded/unavailable behavior; it does not trigger historical NI-01 recognition from the HTTP request.

---

# 35. ROLLOUT / ROLLBACK

## Stage 0

```text
mode=off
existing production behavior
```

## Stage 1 — additive NI-02B feed

Deploy feed extension default unused.

Verify projection regression and writer overhead.

## Stage 2 — shadow materializer

```text
mode=shadow
```

Build store and 24h backfill.

No UI authority change.

## Stage 3 — compare

Run deterministic shadow comparisons and performance gates.

## Stage 4 — serve

Owner-authorized:

```text
mode=serve
```

Admin runtime composes only materialized NI-04 reader for normal requests.

## Rollback

Automatic fallback is forbidden.

Owner may explicitly:

```text
disable WEB_ADMIN_DEVICE_SERVICE_INTELLIGENCE_ENABLED
OR
return deployment mode to shadow/off under an approved rollback
OR
revert the exact application commit
```

NI-04 store does not require destructive rollback.

NI-01/NI-02B source evidence is not rewritten.

---

# 36. OWNER APPROVAL GATES

No open architecture choice remains for Coder.

Owner approval is still required for execution of these already-decided changes:

```text
O1 additive NI-02B edge-feed extension
O2 new network-service-recognition.service
O3 new NI-04 SQLite path/store
O4 API V3 cutover after shadow PASS
O5 production activation mode=serve
```

These are authorization gates, not unresolved design questions.

---

# 37. FINAL ARCHITECTURE DECISION

```text
TASK = TASK-DTI-NI-04 — Background Materialized Service Intelligence

ROOT_CAUSE =
QUERY-TIME RECOGNITION / AGGREGATION IN DEVICE CARD READ PATH

TARGET =
BACKGROUND MATERIALIZATION + DURABLE DEVICE-BOUND SERVICE STORE

WORKER_OWNER = NI-04
WORKER_PROCESS = SEPARATE

SOURCE =
NI-02B authoritative edges via durable monotonic edge-commit feed
+ existing Registry binding-event stream
+ exact NI-01 evidence by ref

MATERIALIZED_STORE =
DEDICATED NI-04 SQLITE
SINGLE WRITER
WAL + synchronous FULL

ADMIN SERVE PATH =
MATERIALIZED STORE ONLY
NO BULK NI-01 READ
NO 24H NI-02B FACT SCAN
NO QUERY-TIME RECOGNITION

PUBLIC CONTRACT = V3
ROUTE = UNCHANGED

ROLLING WINDOWS =
1h / 24h preserved
INDEXED CUTOFF OVER PRECOMPUTED ROLLUPS

INITIAL BACKFILL = 24h
LIVE FEED PRIORITY = YES

RULE CHANGE = GENERATION BUILD + ATOMIC PROMOTION
NO GENERATION MIXING

POSITIVE FACT RETENTION = <=14d internal
PUBLIC HISTORY = still 24h

UPSTREAM SEMANTIC CHANGES = NONE
NI-02B ADDITIVE DELIVERY EXTENSION = REQUIRED
NI-01 CHANGE = NO
NI-02A CHANGE = NO
NI-03 CHANGE = NO
CAPPORT/AUTH CHANGE = NO
```

Final governance:

```text
ARCHITECTURE_STATUS = COMPLETE / READY FOR TECH LEAD REVIEW

OPEN_P0 = 0
OPEN_P1 = 0
OPEN_P2 = 0

READY_FOR_ONE_TECH_LEAD_IMPLEMENTATION_TASK = YES

IMPLEMENTATION_AUTHORIZATION = NO
CODER = HOLD UNTIL TECH LEAD ACCEPTANCE + OWNER AUTHORIZATION
MERGE = NO
DEPLOY = NO
PRODUCTION_CHANGE = NO
NI-05 = HOLD
NI-06 = HOLD
```

The architectural principle is now frozen as:

```text
ВЫЧИСЛЯТЬ ПРИ ПОСТУПЛЕНИИ ДАННЫХ.
СОХРАНЯТЬ ПОДТВЕРЖДЁННОЕ.
ПРИ ОТКРЫТИИ КАРТОЧКИ — ТОЛЬКО ЧИТАТЬ.
```
