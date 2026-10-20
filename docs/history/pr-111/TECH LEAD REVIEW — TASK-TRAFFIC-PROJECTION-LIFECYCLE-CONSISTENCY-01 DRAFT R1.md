# TECH LEAD REVIEW — REQUIRED CHANGES BEFORE ARCHITECTURE FINAL

## TASK-TRAFFIC-PROJECTION-LIFECYCLE-CONSISTENCY-01

Tech Lead reviewed the Architecture DRAFT against:

- production incident evidence;
- exact current `main`;
- current Traffic Projection writer;
- repository cleanup semantics;
- repair semantics;
- Projection health classifier;
- Historical Projection read gate;
- current logging implementation.

## Review verdict

```text
ARCHITECTURE DIRECTION = ACCEPTED

PER-SITE CLEANUP FENCE = ACCEPTED
DIVERGENCE FAIL-CLOSED = ACCEPTED
DIVERGENCE LATCH = ACCEPTED
SEPARATE SYSTEMD WORKER = ACCEPTED
FIX FIRST / REPAIR SECOND = ACCEPTED
PROCESS HEALTH != PRODUCT HEALTH = ACCEPTED
DEPLOY ARTIFACT COHERENCE = ACCEPTED

ARCHITECTURE FINAL = HOLD

REQUIRED CORRECTIONS = YES
```

Architect should produce:

```text
DRAFT-R2
```

with the following mandatory corrections incorporated.

---

# CHANGE 1 — Correct cleanup boundary semantics

Sections 11 and 52 currently simplify cleanup semantics too far.

Current repository `delete_before()` does NOT mean:

```text
source_started_at < cutoff
→ definitely delete
```

Existing deletion eligibility also requires the existing terminal-state/timestamp predicate.

The architecture must preserve the existing delete semantics and modify **only the maximum cleanup boundary**.

Canonical contract:

```text
normal_cutoff =
now - retention_days

if active frozen reconcile:
    effective_cutoff =
    min(normal_cutoff, reconcile_sweep_from_utc)
else:
    effective_cutoff =
    normal_cutoff
```

Then the existing `delete_before()` eligibility predicate applies unchanged.

Therefore replace wording such as:

```text
cycle < T0
→ eligible for cleanup
```

with:

```text
cycle wholly before T0
→ no longer protected by the reconcile fence;
  existing normal delete_before eligibility rules decide deletion
```

Important invariant:

```text
The P0 fix changes the cleanup fence,
not the historical-row terminal eligibility semantics.
```

Mandatory boundary tests must exercise not only `source_started_at`, but relevant completed/abandoned terminal timestamps around the fence.

---

# CHANGE 2 — Do not use `last_incremental_progress_at` as the sole reconcile-stuck proof

Sections 25 and 59 require correction.

`last_incremental_progress_at` is not a reconcile-exclusive field.

It can represent progress made through Projection maintenance outside the exact reconcile cursor-progress meaning.

Therefore:

```text
fresh last_incremental_progress_at
```

must NOT by itself prove:

```text
active reconcile sweep is progressing
```

A Site could theoretically continue receiving incremental head progress while a reconcile cursor itself is not making useful forward progress.

Architecture must define reconcile-stuck independently.

Preferred contract:

```text
active reconcile =
reconcile_sweep_started_at IS NOT NULL

reconcile progress identity =
(reconcile_cursor_started_at, reconcile_cursor_cycle_id)
```

The implementation must detect whether that reconcile cursor/proof advances across the accepted progress window.

Allowed implementations:

```text
A. structured periodic health telemetry carries the reconcile cursor,
   and stuck state is detected from repeated unchanged cursor evidence;

OR

B. add explicit reconcile-specific progress evidence if repository review
   proves durable detection cannot be implemented safely from existing state.
```

Do NOT silently reuse a general incremental progress field as a reconcile-specific proof.

The existing threshold family may still provide the accepted time budget, but:

```text
progress signal
and
progress threshold
```

are separate concepts.

---

# CHANGE 3 — Relax the absolute “no schema migration required” statement

The retention-race FIX itself does not require a schema change.

That part is accepted.

However Architecture must not prematurely prohibit a narrowly justified schema change if exact durable reconcile-progress observability proves impossible using existing persisted state.

Replace:

```text
Projection schema change = NOT REQUIRED BY ARCHITECTURE
```

with:

```text
RETENTION-FENCE SCHEMA CHANGE = NOT REQUIRED

NEW PERSISTED STATE =
NOT AUTHORIZED BY DEFAULT

If implementation rebind proves that a required P0 invariant
cannot be represented safely and unambiguously using current durable fields,
Tech Lead must STOP and return the specific schema requirement
for narrow Architecture review before implementation.
```

No convenience migration is authorized.

---

# CHANGE 4 — Make `repair-site` lifecycle exact

Sections 18, 42 and 62 need one important clarification.

The existing `repair-site` primitive is accepted as the correct **entry point** for recovery, but it must not be described as though one CLI invocation necessarily performs an entire Site rebuild.

Current contract is bounded/durable.

The explicit repair operation:

```text
1. invalidates previous Site proof;
2. places Site into rebuilding / repair_delete lifecycle;
3. deletes derived Site cycles in bounded chunks;
4. rebuild/reconcile may require subsequent worker iterations;
5. final healthy state is established only after completed proof.
```

Production recovery therefore must explicitly define:

```text
traffic-projection worker stopped
        ↓
exclusive writer lock released
        ↓
invoke Owner-authorized repair-site once
under fixed artifact
        ↓
repair state is durably seeded
        ↓
start fixed normal worker
        ↓
worker detects durable repair state
and continues bounded repair/reconcile
        ↓
new healthy proof
```

Do not require operators to repeatedly invoke manual `repair-site` commands unless exact current implementation review proves that is necessary.

Do not claim:

```text
repair-site command completed
=
Site recovered
```

Recovery remains proof-based.

---

# CHANGE 5 — Artifact identity MUST be captured at process startup

Sections 29, 39 and 61 need a stronger invariant.

It is insufficient for a running process to execute:

```text
git rev-parse HEAD
```

later.

Why:

```text
process starts on artifact A
        ↓
Python imports artifact A modules
        ↓
filesystem checkout replaced by artifact B
        ↓
later git rev-parse reports B
        ↓
process is actually still executing loaded A code
```

That would recreate exactly the false-confidence condition this feature is intended to prevent.

Canonical requirement:

```text
LOADED_ARTIFACT_IDENTITY
must be captured once at process startup
and remain immutable for that process lifetime.
```

At minimum:

```text
artifact SHA
artifact tree/release identity
service name
process start timestamp
```

Deploy acceptance compares:

```text
EXPECTED_DEPLOYED_ARTIFACT
=
STARTUP_CAPTURED_LOADED_ARTIFACT
```

for every artifact-owned long-running process.

Never derive this health field dynamically from a mutable checkout after startup.

Exact mechanism — startup environment, immutable release manifest, bootstrap capture, etc. — belongs to implementation design.

---

# CHANGE 6 — Logging contract must preserve structured fields, not only INFO messages

Sections 27–32 need repository-aware clarification.

Current standalone Traffic Projection CLI uses its own Python logger path, and production evidence already showed that important Projection INFO telemetry did not appear in its journal.

Also, simply attaching the existing generic CaptivPortal stream logger is not sufficient if structured `extra` fields are discarded by its output formatter.

Architecture must require:

```text
event name
+
all approved safe machine fields
```

to survive into the actual journal record.

Accepted wire representation may be:

```text
structured JSON
```

or deterministic:

```text
key=value
```

or another bounded machine-readable format.

But acceptance is NOT:

```text
Python logger received extra fields
```

Acceptance is:

```text
worker emits event
→ journal contains event + required fields
→ Alloy ships the same meaningful fields/message
→ Loki query can identify Site/version/status/error
→ Grafana can alert on it
```

Prefer reuse/extension of the project's canonical logging infrastructure where appropriate.

Do not create an unrelated second logging architecture merely for Projection.

---

# CHANGE 7 — Normalize telemetry event namespace

The DRAFT currently proposes names such as:

```text
projection_site_diverged
projection_source_identity_failed
```

while the existing Projection telemetry vocabulary already uses:

```text
traffic_projection_...
```

Use one canonical namespace.

Required Architecture naming:

```text
traffic_projection_site_diverged
traffic_projection_source_identity_failed
traffic_projection_stale
traffic_projection_reconcile_stuck
traffic_projection_worker_source_unavailable
traffic_projection_worker_storage_unavailable
traffic_projection_recovered
traffic_projection_worker_started
traffic_projection_worker_stopped
traffic_projection_product_health
```

Do not create parallel:

```text
projection_*
```

and:

```text
traffic_projection_*
```

event families.

Existing compatible event names may remain where needed, but the permanent canonical prefix is:

```text
traffic_projection_
```

---

# CHANGE 8 — Clarify heartbeat semantics

The product-health heartbeat requirement is accepted, but rewrite:

```text
no less frequently than 60 seconds
```

as the unambiguous:

```text
maximum heartbeat interval = 60 seconds
```

Normal expectation:

```text
state transition → immediate event

plus

periodic product-health heartbeat
at interval <= 60 seconds
```

This gives both:

```text
fast incident visibility
+
proof that a healthy worker is still reporting
```

Heartbeat must be bounded per Site/version and must not contain raw source data.

---

# CHANGE 9 — Strengthen rollback artifact coherence

Section 67 currently allows a formulation that could be interpreted as:

```text
web rolled back to old artifact
+
Projection worker continues newer fixed artifact
```

while both use the same mutable `/opt/CaptivePortal` checkout.

Under the current mutable-checkout architecture this is forbidden.

Canonical rollback invariant:

```text
All running services using one mutable CaptivPortal checkout
must execute one coherent deployed artifact.
```

If rollback target predates the P0 fix:

```text
captive-portal may be coherently rolled back
only under approved rollback procedure,

BUT

traffic-projection.service must remain STOPPED
rather than restart on known-vulnerable Projection code
until an accepted coherent artifact is available.
```

Do NOT run mixed loaded artifact versions from the same mutable checkout.

An immutable-release-directory architecture may later permit different release bindings, but that is not the current production model.

---

# CHANGE 10 — Add artifact-owned service discovery gate

Section 36 currently says:

```text
at minimum:
captive-portal.service
traffic-projection.service
```

Keep that, but add:

```text
Before implementation/deploy acceptance,
production service inventory must verify whether any other
long-running process executes Python/code directly from
the mutable CaptivPortal artifact.
```

Do not permanently hard-code the deployment lifecycle to only two units without inventory proof.

The resulting deployment manifest is authoritative for artifact-owned long-running services.

Embedded workers running inside `captive-portal.service` remain owned by that process and do not become separate units merely because they have internal worker objects.

---

# CHANGE 11 — Remove/rename “Offline-style absence principle”

Section 8.3:

```text
Offline-style absence principle for projection identity
```

imports terminology from a different Device/Current-State semantic domain and is unnecessarily confusing here.

Replace with:

```text
## Proof-window integrity invariant
```

Canonical wording:

```text
A missing derived row is evidence of Projection/source identity mismatch
only if the comparison was performed over one coherent protected proof window.

Cleanup must not invalidate that proof window while the proof is active.
```

Do not reuse Online/Offline vocabulary in Traffic Projection consistency semantics.

---

# CHANGE 12 — Aggregate health must never gate unrelated Site reads

Section 24 is accepted only with this explicit constraint.

Global operational aggregation may say:

```text
Historical Traffic fleet/product aggregate = unhealthy
if any required configured production Site is unhealthy.
```

However:

```text
aggregate unhealthy
MUST NOT
make healthy Site B's site-scoped Historical read unavailable
because Site A diverged.
```

Read availability remains Site-scoped.

Aggregate health is:

```text
operations / alerting state
```

not a global read gate.

This must agree with the multi-Site isolation invariant.

---

# CHANGE 13 — Add exact P0 regression test for cleanup scheduling order

The race test is good but should reproduce the actual worker ordering, not only call cleanup/reconcile methods independently.

Mandatory test:

```text
worker iteration N:
active reconcile sweep exists / advances

same worker lifecycle:
cleanup becomes due

cleanup runs while reconcile_sweep_from_utc remains durable

worker iteration N+1:
reconcile continues and completes
```

Required result:

```text
cleanup uses protected effective cutoff
no protected projection row removed
identity proof matches
Site remains non-diverged
```

This is important because the production race occurred through the normal `serve_forever()` maintenance lifecycle.

Also include:

```text
worker restart while an unfinished reconcile_sweep_* is durable
```

After restart the fence must still use the persisted frozen boundary.

Protection must therefore survive process restart.

---

# CHANGE 14 — Add direct production incident regression fixture

In addition to synthetic T0/T1 tests, create a regression fixture modeled on the actual incident:

```text
frozen lower bound:
2026-08-27T08:26:05.244Z

source rows immediately after boundary:
08:26:28.388
08:27:02.854

moving cutoff advances past both
```

Expected after FIX:

```text
both rows remain in Projection until active frozen proof completes

SOURCE_ONLY_COUNT=0
PROJECTION_ONLY_COUNT=0
```

Exact production UUIDs are not required in permanent test data; the timing topology is.

---

# CHANGE 15 — Preserve current Historical read health contract explicitly

Repository review confirms current projected Historical reads require:

```text
Projection health == healthy
```

Architecture should state explicitly:

```text
This TASK does not broaden the accepted read states.
```

Therefore:

```text
catching_up
rebuilding
stale
diverged
unavailable
```

remain unavailable for accepted Historical Projection delivery unless a separate future architecture changes that semantic contract.

---

# CHANGE 16 — Add forensic evidence capture before production repair

Before any repair mutation of the current incident, preserve a compact immutable incident manifest in addition to the consistent Projection backup.

At minimum record:

```text
production Git SHA/tree
projection DB checksum/size
projection version
Site state
frozen reconcile bounds
SOURCE_COUNT
PROJECTION_COUNT
SOURCE_ONLY_COUNT
PROJECTION_ONLY_COUNT
source-only cycle IDs
source metadata necessary to reproduce the incident classification
repair start timestamp
```

Do not log raw unnecessary Observation payloads.

Purpose:

```text
repair must not erase the only durable record
of why production entered diverged.
```

This is forensic evidence, not a second source of truth.

---

# FINAL TECH LEAD POSITION

After the above changes, expected architecture verdict remains:

```text
ROOT CAUSE =
RETENTION CLEANUP / FROZEN RECONCILE WINDOW RACE

PERMANENT CONSISTENCY FIX =
PER-SITE / PER-VERSION CLEANUP FENCE

DIVERGENCE =
FAIL-CLOSED + LATCHED

NORMAL CLEANUP WHILE DIVERGED =
BLOCKED

NORMAL CLEANUP WHILE REPAIRING =
BLOCKED

SEPARATE PROJECTION WORKER =
KEEP

ONE SITE DIVERGED =
WORKER REMAINS RUNNING
OTHER SITES CONTINUE

PROCESS HEALTH != PRODUCT HEALTH =
MANDATORY

HISTORICAL READ ACCEPTANCE =
SITE HEALTH MUST REMAIN HEALTHY

OBSERVABILITY =
STATE TRANSITION EVENTS
+
<=60s PRODUCT-HEALTH HEARTBEAT
+
END-TO-END JOURNAL/ALLOY/LOKI PROOF

ARTIFACT IDENTITY =
IMMUTABLY CAPTURED AT PROCESS START

MUTABLE CHECKOUT DEPLOY =
ALL ARTIFACT-OWNED LONG-RUNNING PROCESSES QUIESCED
BEFORE ARTIFACT MUTATION

CURRENT INCIDENT =
FIX FIRST
REPAIR SECOND

RECOVERY =
EXPLICIT repair-site ENTRY
+
DURABLE WORKER-CONTINUED REPAIR
+
FULL RE-PROOF

OBSERVATION MUTATION =
FORBIDDEN

MANUAL TWO-ROW INSERT =
FORBIDDEN

MANUAL HEALTH RESET =
FORBIDDEN

IMPLEMENTATION AUTHORIZATION =
HOLD

PRODUCTION REPAIR =
HOLD
```

Please incorporate these corrections and return:

```text
DRAFT-R2 — TASK-TRAFFIC-PROJECTION-LIFECYCLE-CONSISTENCY-01
```

for final Owner + Tech Lead architecture review.

Do not issue Coder implementation instructions yet.