# IMPLEMENTATION-READY FINAL-R2 — TASK-TRAFFIC-PROJECTION-LIFECYCLE-CONSISTENCY-01

**Project:** CaptivPortal  
**Priority:** `P0 / PRODUCTION INCIDENT`  
**Architecture authority:** `ARCHITECTURE FINAL-R1 — PASS`  
**Tech Lead source rebind:** `COMPLETE`  
**Deliverable:** exact implementation-ready Coder TASK for final Tech Lead line-by-line review  
**Status:** `IMPLEMENTATION-READY FINAL-R2 — FOR FINAL TECH LEAD SIGN-OFF`  
**Implementation authorization:** `NOT GRANTED`  
**Coder authorization:** `NOT GRANTED`  
**Coder PLAN:** `FORBIDDEN / NOT REQUIRED`  
**Branch / commit / push / PR / merge:** `NOT AUTHORIZED`  
**Production repair:** `HOLD`  
**Production rebuild:** `HOLD`  
**Production Projection writer:** `STOPPED + DISABLED / CONTAINED`  
**Prepared:** 2026-09-10

---

# 0. Owner workflow rule

Permanent project workflow:

```text
ARCHITECT + TECH LEAD DESIGN
        ↓
OWNER AUTHORIZES
        ↓
CODER WRITES CODE
        ↓
CODER RUNS ONLY NARROW IMPLEMENTATION TESTS
        ↓
CODER HANDOFF
        ↓
OWNER + TECH LEAD OFFICIAL ACCEPTANCE
```

Coder does NOT:

```text
write a PLAN
choose architecture
choose another algorithm
choose another logging format
choose another health model
choose another repair model
run production repair
run official production acceptance
```

If this TASK contradicts the authorized repository baseline, Coder must:

```text
STOP
→ report exact evidence
→ make no workaround
```

---

# 1. Authorized implementation baseline

Implementation TASK is bound to:

```text
REPOSITORY =
ZaurNavi/CaptivePortal

BASELINE SHA =
ff39fe888c53361a7c65a034eaddb0ce92cc4a12

BASELINE TREE =
f6f1068a579c1f1c6f1debeae2e6a1e0da4823b8
```

Immediately before Owner implementation authorization, Tech Lead MUST re-check:

```text
origin/main SHA/tree
```

If unchanged:

```text
this TASK remains implementation-ready
```

If changed:

```text
CODER remains HOLD
Tech Lead performs impact rebind first
```

---

# 2. Production containment — do not change during development

Current production state is intentionally:

```text
traffic-projection.service = inactive
traffic-projection.service = disabled

Projection writer lock = free

traffic_projection.sqlite3 =
quiesced / no active writer

observations.sqlite3 =
continues receiving authoritative Observation data

captive-portal.service =
active / untouched
```

During implementation/testing:

```text
DO NOT enable traffic-projection.service in production
DO NOT run production repair-site
DO NOT run production rebuild-range
DO NOT mutate production Projection DB
DO NOT mutate Observation
```

---

# 3. Frozen production artifact-owned service manifest

Current production manifest is exactly:

```text
1. captive-portal.service
   /usr/bin/python3 /opt/CaptivePortal/run.py
   WorkingDirectory=/opt/CaptivePortal

2. traffic-projection.service
   /usr/bin/python3 -m app.traffic_projection.cli run
   WorkingDirectory=/opt/CaptivePortal
   PYTHONPATH=/opt/CaptivePortal
```

No other long-running CaptivPortal systemd application consumer was found during rebind.

No CaptivPortal cron consumer was found.

This TASK does not add another long-running service.

---

# 4. Root defect to fix

Current worker lifecycle is:

```text
active Projection maintenance
        ↓
_cleanup_if_due()
        ↓
target-version maintenance
```

Current `cleanup()`:

```text
normal_cutoff =
clock_now - retention_days

for Site:
    repository.delete_before(site_id, normal_cutoff)
```

It does not protect an active frozen reconcile lower boundary.

Permanent fix:

```text
for every Projection version + Site cleanup decision:
    read current durable Site state

    validate cleanup-protection state

    if destructive cleanup is not safely authorized:
        no delete

    elif durable diverged:
        no delete

    elif exact repair_active:
        no delete

    elif coherent active frozen reconcile:
        effective_cutoff =
            min(
                normal_cutoff,
                reconcile_sweep_from_utc
            )

    else:
        effective_cutoff =
            normal_cutoff

    repository.delete_before(
        site_id,
        effective_cutoff
    )
```

Existing repository `delete_before()` SQL semantics remain unchanged.

---

# 5. No Projection schema migration

Frozen:

```text
Projection schema version remains 1.

NO new table.
NO new column.
NO new index.
NO schema-version bump.
```

Existing durable fields are sufficient:

```text
reconcile_cursor_started_at
reconcile_cursor_cycle_id

reconcile_sweep_started_at
reconcile_sweep_source_head_utc
reconcile_sweep_source_head_cycle_id
reconcile_sweep_from_utc
```

Coder MUST NOT modify Projection schema.

---

# 6. Files — exact MODIFY scope

Coder may modify exactly:

```text
run.py

app/traffic_projection/service.py
app/traffic_projection/telemetry.py
app/traffic_projection/cli.py

tests/traffic_projection/test_projection.py
```

No other existing file is authorized for modification by default.

---

# 7. Files — exact ADD scope

Coder must add exactly:

```text
app/artifact_identity.py

app/traffic_projection/health_observer.py

tests/test_artifact_identity.py

tests/traffic_projection/test_health_observer.py
tests/traffic_projection/test_telemetry.py
tests/traffic_projection/test_cli.py
```

---

# 8. Files — explicit NO-TOUCH scope

Do NOT modify:

```text
app/traffic_projection/repository.py
app/traffic_projection/models.py
app/traffic_projection/health.py
app/traffic_projection/read_service.py
app/traffic_projection/source.py
app/traffic_projection/config.py
app/traffic_projection/runtime.py
app/traffic_projection/__init__.py

app/analytics/**
app/admin_web/**
app/current_state/**
app/observations/**
app/visit_lifecycle/**
app/visitor_registry/**
app/auth/**
app/web/**

app/config.py
app/settings.py
app/logger.py

requirements*
.env.example

systemd unit files
Nginx
Alloy
Loki
Grafana
```

Additionally:

```text
app/traffic_projection/schema.py
DOES NOT EXIST IN AUTHORIZED BASELINE
MUST NOT BE CREATED
```

Projection schema v1 is owned by:

```text
app/traffic_projection/repository.py
```

and that file remains NO-TOUCH.

The permanent deployment procedure and Grafana acceptance are Owner + Tech Lead operations, not Coder implementation in this TASK.

If implementation appears to require a NO-TOUCH file or creation of `schema.py`:

```text
STOP
→ return exact reason
```

---

# 9. Existing repository semantics that MUST remain unchanged

Preserve exactly:

```text
TrafficProjectionRepository.delete_before()

TrafficProjectionRepository.begin_site_repair()

TrafficProjectionRepository.delete_site_cycles()

TrafficProjectionRepository.site_state()

TrafficProjectionRepository.worker_version_records()

classify_projection_health()

TrafficProjectionReadService healthy-only delivery gate

Observation source semantics

Historical Traffic formulas

Traffic Projection schema v1

retention_days configuration

single-writer lock semantics
```

---

# 10. Exact `repair_active` predicate

In `app/traffic_projection/service.py`, add one shared private helper:

```python
def _repair_active(
    *,
    version_status: str | None,
    state: Mapping[str, Any],
) -> bool:
```

Exact return condition:

```text
version_status == "active"

AND

state["status"] == "rebuilding"

AND

(
    state["last_error_category"] == "repair_delete"

    OR

    state["reconcile_sweep_started_at"] is not None
)
```

No other condition.

Exact authorized consumers are only:

```text
1. normal worker repair continuation classification

2. normal cleanup repair block
```

The Health Observer has NO repair-lineage responsibility.

`app/traffic_projection/health_observer.py` MUST NOT import `_repair_active()` merely for recovery semantics.

Authoritative `traffic_projection_recovered` ownership remains:

```text
TrafficProjectionService.repair_site()
```

Do NOT interpret:

```text
status == "rebuilding"
```

alone as repair.

---

# 11. Existing repair behavior

Do NOT redesign:

```text
TrafficProjectionService.repair_site()
```

Current semantic remains:

```text
one bounded durable repair quantum
```

One Owner-authorized `repair-site` CLI invocation seeds/advances repair state.

Normal worker later continues durable repair.

No repeated manual invocation is required by this TASK.

---

# 12. Cleanup helper — exact function

In `app/traffic_projection/service.py`, add:

```python
def _cleanup_cutoff_for_site(
    self,
    site_id: str,
    *,
    normal_cutoff: str,
    version_status: str,
) -> str | None:
```

Meaning:

```text
string
→ safe effective cutoff

None
→ no normal cleanup mutation for this Site/version
```

This helper emits operational telemetry for cleanup-state failures.

It does not call `delete_before()` itself.

---

# 13. Cleanup state read — exact exception boundary

`_cleanup_cutoff_for_site()` must begin by reading:

```python
state = self.repository.site_state(site_id)
```

For cleanup-safety read handling, catch exactly:

```python
TrafficProjectionStorageUnavailable
TrafficProjectionStorageCorrupt
```

For either known Projection storage failure:

```text
return None

emit:
traffic_projection_worker_storage_unavailable
error_category=cleanup_state_unavailable
```

No deletion.

Do NOT use broad:

```python
except Exception
```

for cleanup authorization.

Unexpected programming/runtime exceptions outside the sanctioned Projection storage failures MUST propagate to the existing worker failure boundary.

Permanent distinction:

```text
known inability to establish cleanup safety
→ safe NO MUTATION

unexpected implementation/runtime bug
→ NOT silently reclassified as cleanup_state_unavailable
```

---

# 14. Missing Site state

If:

```text
state is None
```

then:

```text
return None

emit:
traffic_projection_worker_storage_unavailable
error_category=cleanup_state_unavailable
```

Do NOT call `ensure_site()` from cleanup as recovery.

Do NOT use normal cutoff.

---

# 15. Stored lifecycle status validation

For cleanup authorization, stored Site `status` must be exactly one of the six existing Projection schema v1 statuses:

```text
healthy
catching_up
stale
unavailable
rebuilding
diverged
```

`status=unavailable` is a valid persisted Site lifecycle state.

It MUST NOT be mapped to:

```text
cleanup_state_unavailable
```

merely because the status value is `unavailable`.

Any value outside the six-state allowlist, or a missing status:

```text
return None
emit:
traffic_projection_worker_storage_unavailable
error_category=cleanup_state_unavailable
```

This is cleanup-safety failure.

It does NOT mark Site diverged.

Dynamic/computed-health rules remain unchanged.

---

# 16. Exact frozen-sweep fields to validate

Read:

```text
reconcile_sweep_started_at
reconcile_sweep_from_utc
reconcile_sweep_source_head_utc
reconcile_sweep_source_head_cycle_id

reconcile_cursor_started_at
reconcile_cursor_cycle_id
```

Define:

```text
sweep_active =
reconcile_sweep_started_at is not None
```

---

# 17. Frozen-sweep structural coherence

If `sweep_active` is true, require all of:

```text
reconcile_sweep_started_at = non-empty valid UTC timestamp

reconcile_sweep_from_utc = non-empty valid UTC timestamp

reconcile_sweep_source_head_utc = non-empty valid UTC timestamp

reconcile_sweep_source_head_cycle_id =
non-empty string

reconcile_sweep_from_utc
<=
reconcile_sweep_source_head_utc
```

If any requirement fails:

```text
return None

emit:
traffic_projection_worker_storage_unavailable
error_category=cleanup_fence_invalid
```

No deletion.

---

# 18. Orphan frozen-sweep state

If:

```text
reconcile_sweep_started_at is None
```

then all of these MUST also be null:

```text
reconcile_sweep_from_utc
reconcile_sweep_source_head_utc
reconcile_sweep_source_head_cycle_id
```

If any is non-null:

```text
return None
emit cleanup_fence_invalid
```

No deletion.

---

# 19. Reconcile cursor coherence for cleanup safety

Cursor pair must satisfy:

```text
both null
OR
both non-null
```

If one is null and one is not:

```text
return None
emit cleanup_fence_invalid
```

If cursor is non-null while:

```text
sweep_active == false
```

then:

```text
return None
emit cleanup_fence_invalid
```

If `reconcile_cursor_started_at` is non-null it must be a valid UTC timestamp.

`reconcile_cursor_cycle_id` must be a non-empty string.

Invalid:

```text
return None
emit cleanup_fence_invalid
```

---

# 20. UTC timestamp parser for cleanup safety

In `app/traffic_projection/service.py`, add private helper:

```python
def _parse_utc(value: object) -> datetime | None:
```

Contract:

```text
input must be non-empty str
ISO timestamp must parse
tzinfo must be present
normalize to UTC
```

Invalid:

```text
return None
```

No exception leaks into cleanup authorization.

Do not modify `health.py` private parser.

---

# 21. `repair_delete` incoherence rule

If:

```text
state["last_error_category"] == "repair_delete"
```

but `_repair_active(...)` is false:

```text
cleanup authorization is incoherent
```

Required:

```text
return None
emit:
traffic_projection_worker_storage_unavailable
error_category=cleanup_fence_invalid
```

This prevents an ambiguous repair lineage from authorizing destructive retention.

It does NOT reinterpret target `rebuilding` as repair.

---

# 22. Durable diverged cleanup rule

After state coherence validation:

```text
if state["status"] == "diverged":
    return None
```

Do NOT emit cleanup failure solely because divergence blocks cleanup.

Divergence is expected latched incident state and is exposed through product health.

---

# 23. Exact repair cleanup rule

After state coherence validation:

```text
if _repair_active(
    version_status=version_status,
    state=state,
):
    return None
```

No normal retention mutation.

---

# 24. Active sweep effective cutoff

If coherent `sweep_active`:

```text
parse normal_cutoff
parse reconcile_sweep_from_utc
```

Both must be valid UTC.

Return the earlier timestamp, serialized in existing canonical millisecond-UTC format:

```text
YYYY-MM-DDTHH:MM:SS.mmmZ
```

Equivalent semantic:

```text
min(normal_cutoff, reconcile_sweep_from_utc)
```

Do not alter repository deletion predicate.

---

# 25. Ordinary cleanup cutoff

If:

```text
not diverged
not repair_active
no active frozen sweep
state structurally coherent
```

return:

```text
normal_cutoff
```

This includes a dynamically computed `stale` Site when there is no separate durable cleanup guard.

Canonical computed health is NOT cleanup mutation authority.

---

# 26. `cleanup()` exact refactor

Keep public signature:

```python
def cleanup(
    self,
    *,
    max_chunks: int = MAX_CLEANUP_CHUNKS_PER_INVOCATION,
) -> int:
```

Required algorithm:

```text
1. Read current version_status.

2. Catch exactly:
   TrafficProjectionStorageUnavailable
   TrafficProjectionStorageCorrupt

   from repository.version_status().

   For either:
       emit traffic_projection_worker_storage_unavailable
       error_category=cleanup_state_unavailable
       return 0.

3. Any unexpected exception from version_status()
   propagates.
   Do NOT convert it into cleanup_state_unavailable.

4. If version_status not in:
   active | building | ready
   return 0.

5. Calculate normal_cutoff once for this cleanup invocation:
   clock_now - retention_days.

6. For each configured site_id:
   call _cleanup_cutoff_for_site(
       site_id,
       normal_cutoff=normal_cutoff,
       version_status=version_status,
   )

7. If result is None:
   perform zero delete_before calls for that Site.
   continue to next independently safe Site.

8. If cutoff returned:
   keep existing bounded chunk loop
   and call existing:
   repository.delete_before(site_id, cutoff)

9. Preserve:
   MAX_CLEANUP_CHUNKS_PER_INVOCATION
   MAX_BULK_CYCLES_PER_TRANSACTION
   checkpoint_passive()
```

Do not change row deletion SQL.

`repository.delete_before()` failures are not transformed into cleanup-authorization decisions; they continue through the existing Projection storage/worker failure boundaries.

---

# 27. Cleanup decision must not be cached

Do NOT store per-Site cutoff/fence decisions in:

```text
service object state
global dict
module cache
```

Each `cleanup()` invocation reads current durable state immediately before that Site's cleanup chunk loop.

Under existing single-writer ownership this is the authoritative decision for that Site operation.

---

# 28. `_cleanup_if_due()` scheduling

Keep existing schedule:

```text
86400 seconds
```

No retention frequency change.

Keep:

```text
_last_cleanup = 0.0
```

The fix MUST make immediate post-restart cleanup safe.

Do not add artificial 24-hour startup grace.

---

# 29. Startup cleanup hazard test contract

The implementation must remain safe when:

```text
unfinished durable reconcile exists

new TrafficProjectionService starts
_last_cleanup = 0

host monotonic uptime makes cleanup due immediately
```

`cleanup()` must read the persisted frozen boundary and protect it.

---

# 30. Exact source-identity telemetry insertion

In `TrafficProjectionService.reconcile_site()`, in the existing branch:

```text
source_count != projection_count
```

after persisting:

```text
status=diverged
last_error_category=source_identity
```

and before raising `TrafficProjectionDiverged`, emit:

```text
traffic_projection_source_identity_failed
```

with exact caller fields:

```text
projection_version
site_id
error_category="source_identity"

source_count
projection_count
count_delta = source_count - projection_count

reconcile_sweep_from_utc = frozen from_utc

reconcile_sweep_source_head_utc =
frozen sweep head UTC
```

No cycle payload.

---

# 31. Ready-build source identity telemetry

In `mark_ready()`, preserve current count proof.

Refactor the two count calls into:

```text
source_count
projection_count
```

If mismatch, after durable divergence update and before raising emit:

```text
traffic_projection_source_identity_failed
```

with:

```text
projection_version
site_id
error_category="ready_source_identity"
source_count
projection_count
count_delta
```

Do not invent reconcile-sweep boundary fields for the ready-build proof.

---

# 32. Existing telemetry events remain compatible

Do not remove existing:

```text
traffic_projection_reconcile_completed
traffic_projection_scan_failed
```

This TASK adds the P0 event contract.

Existing compatible `traffic_projection_*` events may remain.

Do not create a `projection_*` namespace.

---

# 33. New shared startup artifact identity module

Add:

```text
app/artifact_identity.py
```

with exactly:

```python
class ArtifactIdentityError(RuntimeError):
    pass
```

and:

```python
@dataclass(frozen=True, slots=True)
class LoadedArtifactIdentity:
    artifact_sha: str
    artifact_tree: str
    service_name: str
    process_started_at: str

    def safe_fields(self) -> dict[str, str]:
        ...

    def json_line(
        self,
        *,
        event: str = "captivportal_loaded_artifact_identity",
    ) -> str:
        ...
```

and:

```python
def capture_loaded_artifact_identity(
    service_name: str,
) -> LoadedArtifactIdentity:
    ...
```

No other public API.

---

# 34. Artifact repository root

`capture_loaded_artifact_identity()` derives current repository root as:

```python
Path(__file__).resolve().parents[1]
```

This resolves to the CaptivPortal checkout containing:

```text
run.py
app/
```

No environment override in v1.

---

# 35. Artifact Git capture commands

At startup execute exactly two bounded Git queries:

```text
git -C <repository_root> rev-parse --verify HEAD

git -C <repository_root> rev-parse --verify HEAD^{tree}
```

Use `subprocess.run()` with:

```text
check=True
stdout captured
stderr suppressed
text=True
timeout=2.0 seconds
```

No later Git query may replace the captured values.

---

# 36. Artifact identity validation

Require:

```text
artifact_sha =
exactly 40 lowercase hexadecimal characters

artifact_tree =
exactly 40 lowercase hexadecimal characters

service_name =
non-empty string
length <=128

process_started_at =
canonical UTC millisecond timestamp
```

Any capture/process/validation error:

```python
raise ArtifactIdentityError(
    "loaded artifact identity is unavailable"
)
```

No raw Git stderr in exception.

---

# 37. Artifact process-start timestamp

Capture:

```text
process_started_at
```

once when `capture_loaded_artifact_identity()` begins.

Format:

```text
YYYY-MM-DDTHH:MM:SS.mmmZ
```

The `LoadedArtifactIdentity` object is immutable for process lifetime.

---

# 38. Artifact identity JSON line

`LoadedArtifactIdentity.json_line()` serializes one-line JSON using:

```python
json.dumps(
    payload,
    ensure_ascii=True,
    allow_nan=False,
    sort_keys=True,
    separators=(",", ":"),
)
```

Exact payload keys:

```text
event
artifact_sha
artifact_tree
service_name
process_started_at
```

No extra fields.

---

# 39. `run.py` artifact identity integration

At the first executable step inside:

```python
main()
```

before logging successful CaptivePortal startup, call:

```python
capture_loaded_artifact_identity(
    "captive-portal.service"
)
```

On success emit exactly one existing-logger line:

```text
captivportal_loaded_artifact_identity
```

using:

```python
logger.info(identity.json_line())
```

Then continue existing application startup.

---

# 40. `run.py` artifact identity failure

If capture raises `ArtifactIdentityError`:

```text
logger.critical(
    "captivportal_artifact_identity_startup_failed"
)
raise SystemExit(1)
```

No raw exception text.

Do not start background workers or Flask server.

No change to existing `shutdown_handler()` semantics is required by this P0.

---

# 41. Projection telemetry logger — exact owned-handler function

In:

```text
app/traffic_projection/telemetry.py
```

add:

```python
def configure_traffic_projection_logger() -> logging.Logger:
```

Exact logger name:

```text
captivportal.traffic_projection
```

Exact logger contract:

```text
logger level = INFO
propagate = False
```

This dedicated P0 logger owns its direct handler set.

Every call to `configure_traffic_projection_logger()` MUST:

```text
1. obtain logging.getLogger("captivportal.traffic_projection")

2. set logger level INFO

3. set propagate=False

4. remove EVERY existing handler
   directly attached to this dedicated logger

5. close every removed handler best-effort

6. install exactly ONE logging.StreamHandler
   using default stderr stream

7. set handler level INFO

8. set formatter:
   "%(message)s"

9. mark the installed handler with a private
   Projection-owned marker
```

Repeated calls MUST leave:

```text
len(logger.handlers) == 1
```

with no duplicate output.

The marker is retained for ownership/debugging, but duplicate prevention is achieved by deterministic replacement of the dedicated logger's direct handlers.

Do not modify:

```text
app/logger.py
generic CaptivPortal logger handlers
```

Because this is the dedicated `captivportal.traffic_projection` logger, replacing its direct handler set is authorized by this TASK.

---

# 42. Projection telemetry wire representation

Change `TrafficProjectionTelemetry.emit()` from `LogRecord.extra` dependency to deterministic one-line JSON message output.

Exact serialization:

```python
json.dumps(
    payload,
    ensure_ascii=True,
    allow_nan=False,
    sort_keys=True,
    separators=(",", ":"),
)
```

Logger call:

```python
self._logger.info("%s", json_line)
```

With the Projection logger formatter `%message`, one event becomes one journal line.

---

# 43. Telemetry safe primitive types

`TrafficProjectionTelemetry.emit()` may include only values that are:

```text
None
bool
int
finite float
str
```

Strings are bounded to:

```text
maximum 256 characters
```

Long strings are truncated to the first 256 characters.

Unsupported field values are omitted.

No object `repr()` conversion.

Telemetry normalization MUST NOT raise into Projection business logic.

---

# 44. Telemetry runtime identity binding

Change constructor to:

```python
class TrafficProjectionTelemetry:
    def __init__(
        self,
        logger: logging.Logger,
        *,
        runtime_fields: Mapping[str, Any] | None = None,
    ):
        ...
```

Allowed runtime fields:

```text
artifact_sha
artifact_tree
service_name
process_started_at
```

Runtime identity fields are filtered through the same safe-field rules.

On `emit()`:

```text
caller event fields
+
runtime identity fields
```

Runtime identity values override caller attempts to provide the same keys.

---

# 45. `SAFE_FIELDS` exact P0 expansion

Preserve existing safe fields and add:

```text
reconcile_sweep_from_utc
reconcile_sweep_source_head_utc

reconcile_cursor_started_at
reconcile_cursor_cycle_id

source_count
projection_count
count_delta

artifact_sha
artifact_tree
service_name
process_started_at
```

Keep existing fields including:

```text
projection_version
site_id
status
build_state
projection_revision
source_head_utc
projection_head_utc
head_lag_seconds
last_incremental_progress_at
reconcile_sweep_started_at
last_full_reconcile_completed_at
backlog_cycle_count
error_category
cycles_*
deep_audit_checked
duration_ms
db_bytes
wal_bytes
```

`event` is inserted by the emitter itself.

---

# 46. Traffic Projection service constructor identity

In:

```text
app/traffic_projection/service.py
```

extend constructor:

```python
def __init__(
    ...,
    artifact_identity: LoadedArtifactIdentity | None = None,
):
```

Store:

```python
self._artifact_identity = artifact_identity
```

Create telemetry with:

```python
runtime_fields=(
    artifact_identity.safe_fields()
    if artifact_identity is not None
    else None
)
```

Identity requirement by command:

```text
run
→ REQUIRED

repair-site
→ REQUIRED

build
mark-ready
activate
mark-failed
rebuild-range
cleanup
→ OPTIONAL / None
```

Long-running `serve_forever()` may not run without identity.

`repair-site` requires identity because it owns authoritative `traffic_projection_recovered` emission when a repair quantum establishes the final healthy proof.

---

# 47. Version service identity propagation

In:

```python
_version_service()
```

pass:

```python
artifact_identity=self._artifact_identity
```

Every version context owned by the one worker therefore emits the same immutable process artifact identity.

---

# 48. Long-running worker identity requirement

At start of:

```python
serve_forever()
```

if:

```text
self._artifact_identity is None
```

raise sanitized:

```python
TrafficProjectionWriterUnavailable(
    "Loaded artifact identity is unavailable"
)
```

before `traffic_projection_worker_started`.

Direct tests that call `serve_forever()` must pass a test `LoadedArtifactIdentity`.

---

# 49. Canonical health observation refactor

In `TrafficProjectionService`, add:

```python
def health_observation(
    self,
    site_id: str,
) -> Mapping[str, Any]:
```

Exact result keys:

```text
health
site_state
source_available
version_status
```

Where:

```text
health =
existing classify_projection_health(...).safe_dict()

site_state =
dict of current repository Site state
or None

source_available =
the exact boolean passed to classify_projection_health()

version_status =
str | None
```

No second source-availability definition is permitted.

---

# 50. `health_observation()` exact classifier/source-availability contract

The method contains the current `health()` input assembly logic:

```text
read site_state
read version record/status
determine version_available
read current source head
overlay current source head into local state copy when present
call existing classify_projection_health()
```

Do NOT implement a second classifier.

Source availability is frozen exactly as:

```python
try:
    current_head = self.source.head(site_id)
except Exception:
    current_head = None
    source_available = False
else:
    source_available = current_head is not None
```

Then call:

```python
classify_projection_health(
    ...,
    source_available=source_available,
    ...
)
```

and return exactly the same value as:

```text
observation["source_available"] = source_available
```

Therefore:

```text
source.head raises
→ source_available=False

source.head returns None
→ source_available=False

source.head returns a valid head tuple
→ source_available=True
```

Do NOT set source availability true merely because the call itself returned successfully with `None`.

The Health Observer's `traffic_projection_worker_source_unavailable` transition uses this exact same boolean.

Storage/repository exceptions outside the source-head read propagate to the observer boundary for storage-failure classification.

---

# 51. Existing `health()` API preservation

Refactor existing:

```python
health(site_id)
```

to return only:

```python
health_observation(site_id)["health"]
```

Its public safe result shape and canonical classifier semantics remain unchanged.

---

# 52. Read-only health service enumeration

Add private:

```python
def _health_worker_services(
    self,
) -> tuple["TrafficProjectionService", ...]:
```

Contract:

```text
read repository.worker_version_records()

include active/building/ready supported versions

reuse self for self.projection_version

use _version_service() for other versions

DO NOT call initialize()
DO NOT mutate Projection
```

This method exists only for read-only health observer enumeration.

---

# 53. New health observer module

Add:

```text
app/traffic_projection/health_observer.py
```

Define:

```python
class TrafficProjectionHealthObserver:
```

Exact constructor:

```python
def __init__(
    self,
    root_service,
    *,
    telemetry: TrafficProjectionTelemetry,
    monotonic=time.monotonic,
):
```

Production constants in this module:

```text
OBSERVE_INTERVAL_SECONDS = 5.0

HEARTBEAT_INTERVAL_SECONDS = 55.0

RECONCILE_STUCK_SECONDS = 60.0
```

Architectural maximum product-health heartbeat age:

```text
60 seconds
```

The 55-second heartbeat target reserves one normal 5-second observer scheduling interval for the architectural `<=60s` requirement.

No settings/config additions.

---

# 54. Health observer threading model

The observer is:

```text
one daemon read-only thread
inside traffic-projection.service process
```

It is NOT:

```text
a writer
a systemd service
a collector
a Historical query client
```

It performs only read-side Projection/source health observation and telemetry.

No Projection business-state mutation.

---

# 55. Health observer in-memory state

Key all observer state by:

```text
(projection_version, site_id)
```

Maintain process-memory maps only for:

```text
previous computed health status

previous source_available condition

previous storage_available condition

last heartbeat monotonic time

last reconcile progress identity

reconcile progress identity last-change monotonic time

reconcile_stuck already-emitted flag
```

No persistence.

The observer MUST NOT track:

```text
repair_lineage_seen
```

or any equivalent recovery-eligibility state.

The observer MUST NOT own or emit:

```text
traffic_projection_recovered
```

Authoritative recovery emission belongs only to:

```text
TrafficProjectionService.repair_site()
```

The observer MUST NOT import `_repair_active()` for recovery semantics.

---

# 56. Observer concurrency guard

Use one internal:

```python
threading.Lock()
```

to serialize:

```text
periodic observation
worker-triggered observe-now calls
startup snapshot
```

Do not hold any Projection write lock beyond the existing process writer ownership.

Observer lock is telemetry state only.

---

# 57. Observer `start()`

Exact method:

```python
def start(
    self,
    initial_services,
) -> None:
```

Behavior:

```text
1. Synchronously observe every initial owned Site/version with:
   startup=True
   force_heartbeat=True

2. Start daemon observer thread.

3. Thread runs every 5 seconds until stop requested.
```

The synchronous startup observation occurs after `traffic_projection_worker_started`.

---

# 58. Observer stop lifecycle — exact APIs

Add exact non-blocking method:

```python
def request_stop(self) -> None:
    ...
```

Contract:

```text
set observer stop Event
NO join
NO blocking wait
```

Keep exact blocking shutdown method:

```python
def stop(
    self,
    timeout_seconds: float,
) -> bool:
```

Contract:

```text
call request_stop()

join daemon thread
up to timeout_seconds

return True
if thread stopped

return False
if still alive
```

Do not raise solely because graceful observer join times out.

Permanent:

```text
request_stop()
=
signal-safe/non-blocking stop request

stop(timeout)
=
request + bounded join
```

---

# 59. Observer periodic service enumeration and root storage fallback

Each periodic iteration calls:

```python
root_service._health_worker_services()
```

This is read-only.

If service/version enumeration fails because Projection storage cannot be read, the observer applies a bounded fallback to each root configured Site key:

```text
key =
(root_service.projection_version, site_id)
```

Exact storage-availability behavior is defined in sections 60 and 68.

For the fallback product-health payload use:

```text
projection_version = root_service.projection_version
site_id = requested Site
status = "unavailable"
error_category = "health_state_unavailable"

all other product-health caller fields = null
```

Runtime artifact fields remain present.

Do NOT reuse stale observer-memory health fields.

Do not mutate Site state.

An observer-side failure during enumeration MUST NOT permanently terminate the observer loop. Later ticks must continue observing independently healthy keys.

---

# 60. Observer Site health read and storage-availability state machine

For each Site/version call:

```python
service.health_observation(site_id)
```

Expected Projection storage failures and unexpected read-only observer-side health-read failures are contained inside the observer boundary.

They MUST NOT mutate Projection business state or replace the worker's original maintenance outcome.

For any health-state observation failure that cannot be safely read:

```text
fallback key =
(service.projection_version, site_id)

fallback product health =
projection_version = service.projection_version
site_id = requested Site
status = "unavailable"
error_category = "health_state_unavailable"

build_state = null
projection_revision = null
source_head_utc = null
projection_head_utc = null
head_lag_seconds = null
last_incremental_progress_at = null
reconcile_sweep_started_at = null
reconcile_sweep_from_utc = null
reconcile_sweep_source_head_utc = null
reconcile_cursor_started_at = null
reconcile_cursor_cycle_id = null
last_full_reconcile_completed_at = null
backlog_cycle_count = null
```

Runtime artifact fields remain present.

Storage availability is tracked per key.

## First/startup failure or available→unavailable transition

If:

```text
previous_storage_available is absent/unknown
OR
previous_storage_available == True
```

then immediately emit:

```text
traffic_projection_worker_storage_unavailable
error_category=health_state_unavailable
```

and immediately emit the fallback:

```text
traffic_projection_product_health
status=unavailable
error_category=health_state_unavailable
```

Then set:

```text
previous_storage_available=False
previous_computed_health_status="unavailable"
last heartbeat timestamp=monotonic now
```

## Repeated failure while already unavailable

If:

```text
previous_storage_available == False
```

do NOT emit the operational storage-unavailable event every observer tick.

Emit fallback `traffic_projection_product_health` only when normal heartbeat timing is due.

Do not copy stale health values into that heartbeat.

## Successful observation after storage failure

On successful `health_observation()`:

```text
previous_storage_available=True
```

Then process the current canonical computed health normally.

No separate storage-recovered event is added.

The current product-health stream establishes recovered operational state.

Permanent:

```text
one Site observation failure
MUST NOT
terminate the observer thread
or prevent other Site/version observations.
```

No raw exception text or traceback in P0 telemetry.

---

# 61. Product-health event exact schema and field provenance

`traffic_projection_product_health` caller fields are exactly:

```text
projection_version
site_id

status
build_state

projection_revision

source_head_utc
projection_head_utc
head_lag_seconds

last_incremental_progress_at

reconcile_sweep_started_at
reconcile_sweep_from_utc
reconcile_sweep_source_head_utc

reconcile_cursor_started_at
reconcile_cursor_cycle_id

last_full_reconcile_completed_at

backlog_cycle_count

error_category
```

Runtime telemetry automatically adds:

```text
artifact_sha
artifact_tree
service_name
process_started_at
```

For a successful `health_observation()` the source of every field is frozen.

## Identity fields

```text
projection_version =
service.projection_version

site_id =
requested Site
```

## Fields sourced from `observation["health"]`

Use exactly:

```text
status
build_state
projection_revision

source_head_utc
projection_head_utc
head_lag_seconds

last_incremental_progress_at
reconcile_sweep_started_at
last_full_reconcile_completed_at

backlog_cycle_count
```

No alternate source precedence.

## Fields sourced from `observation["site_state"]`

Use exactly:

```text
reconcile_sweep_from_utc
reconcile_sweep_source_head_utc

reconcile_cursor_started_at
reconcile_cursor_cycle_id

error_category =
site_state["last_error_category"]
```

If `site_state` is present but one of these optional fields is absent/null:

```text
emit null
```

Do not fall back to observer memory.

## Storage/unreadable fallback

If health/Site state cannot be read safely:

```text
projection_version =
service.projection_version

site_id =
requested Site

status =
"unavailable"

error_category =
"health_state_unavailable"
```

Every other product-health caller field MUST be:

```text
null
```

Runtime artifact fields remain present for the long-running worker.

`status` for successful observations is always the existing canonical computed health classifier status.

Do not add Historical delivery fields.

---

# 62. Product-health heartbeat timing

Emit product health:

```text
immediately at startup
```

and thereafter per Site/version using:

```text
HEARTBEAT_INTERVAL_SECONDS = 55.0
```

Architectural maximum heartbeat age:

```text
<=60 seconds
```

Observer scheduling resolution:

```text
OBSERVE_INTERVAL_SECONDS = 5.0
```

Meaning:

```text
normal heartbeat target = 55 seconds

one normal 5-second scheduling interval
is reserved as implementation budget

no Site/version key is intentionally scheduled
to wait beyond 60 seconds
between product-health heartbeats
```

Tests MUST use fake monotonic time and prove the scheduling contract without real-time sleeps.

`RECONCILE_STUCK_SECONDS = 60.0` remains unchanged.

Reconcile stuck means:

```text
condition age >=60 seconds
→ event at the next bounded observer evaluation
```

It is not a heartbeat-deadline guarantee.

---

# 63. Worker-triggered immediate observation — operational boundary

Add observer method:

```python
def observe_service_site(
    self,
    service,
    site_id: str,
    *,
    startup: bool = False,
    force_heartbeat: bool = False,
) -> None:
```

The worker calls it after each Site maintenance attempt, including after caught divergence/failure.

Purpose:

```text
computed health transitions become visible immediately
instead of waiting for periodic thread
```

This method is a read-only operational boundary.

Expected source/storage observation failures are handled internally according to this TASK.

Unexpected observer-side health-read failures for which no safer classification is available are also contained inside the observer boundary as:

```text
traffic_projection_worker_storage_unavailable
error_category=health_state_unavailable
```

plus the bounded unavailable product-health fallback from section 60.

It MUST NOT:

```text
mutate Projection business state

raise in a way that replaces the caller's
maintenance success/failure outcome

terminate the periodic observer permanently

emit raw exception text/traceback
```

The periodic observer remains responsible for heartbeat/reconcile-stuck even when mutation work is idle or fails.

This fail-safe applies only to the read-only observer boundary; it does NOT authorize swallowing exceptions inside Projection writer business logic.

---

# 64. Startup previous-health semantics

For:

```text
startup=True
```

previous in-memory health is:

```text
UNKNOWN
```

Required:

```text
set current computed health as baseline
emit product-health because force_heartbeat=True
```

Do NOT emit:

```text
site_diverged transition
stale transition
recovered transition
```

merely because the new process first sees that state.

---

# 65. Diverged transition event

Outside startup, when prior computed health:

```text
!= diverged
```

and current canonical computed health:

```text
== diverged
```

emit:

```text
traffic_projection_site_diverged
```

Exact caller fields:

```text
projection_version
site_id
status="diverged"
error_category=site_state.last_error_category
projection_revision
```

Artifact fields auto-added.

---

# 66. Stale transition event

Outside startup, when prior computed status:

```text
!= stale
```

and current canonical computed status:

```text
== stale
```

emit:

```text
traffic_projection_stale
```

Exact caller fields:

```text
projection_version
site_id
status="stale"
build_state
projection_revision
source_head_utc
projection_head_utc
head_lag_seconds
last_incremental_progress_at
last_full_reconcile_completed_at
error_category
```

Artifact fields auto-added.

---

# 67. Source-unavailable operational event

Track `source_available` in process memory.

The value comes ONLY from:

```text
observation["source_available"]
```

and that value is exactly the boolean supplied to the canonical classifier by `health_observation()`.

Therefore source is unavailable when:

```text
source.head(site_id) raises

OR

source.head(site_id) returns None
```

If current observation says:

```text
source_available=False
```

and either:

```text
startup first observation
OR
previous source_available=True
```

emit:

```text
traffic_projection_worker_source_unavailable
```

exact caller fields:

```text
projection_version
site_id
error_category="source_unavailable"
```

Do not emit every 5 seconds while condition is unchanged.

Product heartbeat continues to expose current canonical status.

No second source-availability definition is allowed in the observer.

---

# 68. Storage-unavailable operational event — transition bounded

Observer storage/read failure uses:

```text
traffic_projection_worker_storage_unavailable
```

exact caller fields:

```text
projection_version
site_id when known
error_category="health_state_unavailable"
```

This operational event is transition-bounded:

```text
first/startup storage failure
→ emit immediately

available → unavailable
→ emit immediately

continued unavailable on every 5-second tick
→ DO NOT repeat operational event

continued unavailable at heartbeat deadline
→ emit unavailable product-health heartbeat only
```

Cleanup uses the same event name with:

```text
cleanup_state_unavailable
cleanup_fence_invalid
```

Cleanup telemetry throttling is not changed by the observer state machine.

No separate storage-recovered event.

No raw exception text.

---

# 69. Reconcile progress identity

For active sweep:

```text
reconcile_sweep_started_at != null
```

progress identity is exactly:

```text
(
    reconcile_cursor_started_at,
    reconcile_cursor_cycle_id,
)
```

`last_incremental_progress_at` is NOT the reconcile-stuck progress signal.

---

# 70. Reconcile-stuck observer algorithm

For each active Site/version:

```text
if no prior tracked progress identity:
    store current identity
    changed_at = monotonic now
    stuck_emitted = False

elif current identity != prior identity:
    replace identity
    changed_at = monotonic now
    stuck_emitted = False

elif monotonic now - changed_at >= 60
     and stuck_emitted == False:
    emit traffic_projection_reconcile_stuck
    stuck_emitted = True
```

When sweep becomes inactive:

```text
remove reconcile-progress tracking for that key
```

Worker restart resets this in-memory elapsed timer.

---

# 71. Reconcile-stuck event exact schema

Caller fields:

```text
projection_version
site_id
status = current canonical computed status

reconcile_sweep_started_at
reconcile_sweep_from_utc

reconcile_cursor_started_at
reconcile_cursor_cycle_id

error_category="reconcile_stuck"
```

Artifact fields auto-added.

Do not mutate Site status from this event.

---

# 72. Health observer has NO repair recovery ownership

The Health Observer:

```text
MUST NOT import _repair_active()
MUST NOT keep repair_lineage_seen
MUST NOT infer repair completion
MUST NOT emit traffic_projection_recovered
```

Observer ownership is limited to:

```text
traffic_projection_product_health
traffic_projection_site_diverged
traffic_projection_stale
traffic_projection_worker_source_unavailable
traffic_projection_worker_storage_unavailable
traffic_projection_reconcile_stuck
```

Authoritative recovery event ownership is exclusively:

```text
TrafficProjectionService.repair_site()
```

Therefore no service↔observer coupling is introduced for repair semantics.

---

# 73. Authoritative recovered emission — `repair_site()` ownership

`traffic_projection_recovered` owner is exactly:

```text
TrafficProjectionService.repair_site()
```

At entry to `repair_site()`:

```text
the operation itself establishes explicit repair lineage
```

No observer-memory proof is required.

Preserve existing bounded repair behavior.

After the existing repair/reconcile work returns `result`:

```text
if result.sweep_completed:
    read final Site state

    require:
        final state exists
        final state["status"] == "healthy"

    preserve existing validation:
        if sweep completed
        but final Site state is not healthy
        → TrafficProjectionWriterUnavailable
```

Only after that healthy-proof validation succeeds emit:

```text
traffic_projection_recovered
```

Do not emit before final state verification.

Do not emit if:

```text
result.sweep_completed == False
```

No emission from ordinary `reconcile_site()` or `incremental_site()`.

For the worker-driven multi-quantum repair, only the final `repair_site()` quantum whose sweep completes may emit recovered.

For one-shot `repair-site`, the same rule applies.

---

# 74. `traffic_projection_recovered` exact schema

Caller fields:

```text
projection_version
site_id
status="healthy"
projection_revision
last_full_reconcile_completed_at
error_category=None
```

Values:

```text
projection_revision =
final Site state["projection_revision"]

last_full_reconcile_completed_at =
final Site state["last_full_reconcile_completed_at"]
```

Artifact fields are auto-added when the service was constructed with `LoadedArtifactIdentity`.

Production repair-site is required to carry artifact identity.

Do NOT emit recovered for:

```text
ordinary catching_up → healthy
ordinary reconcile completion
startup first observation healthy
health observer transition
```

Event semantics remain best-effort immediate, not transactional/exactly-once.

---

# 75. Transition event reliability

All transition events are:

```text
BEST-EFFORT IMMEDIATE
```

Not:

```text
exactly-once
transactional
outbox-backed
durable audit
```

Do NOT add telemetry persistence.

Durable truth remains Projection state + canonical health classifier.

---

# 76. New observer integration into `TrafficProjectionService`

Add private instance field:

```python
self._health_observer = None
```

Only long-running `serve_forever()` creates/starts it.

One-shot commands do not start an observer thread.

---

# 77. `serve_forever()` exact startup sequence

Replace current startup with:

```text
1. Require self._artifact_identity.

2. Acquire existing writer_lock.

3. Call _worker_services_by_role()
   to complete required Projection initialization
   and establish owned active/target version contexts.

4. Construct:
   TrafficProjectionHealthObserver(
       self,
       telemetry=self.telemetry,
       monotonic=self._monotonic,
   )

5. Store it in self._health_observer.

6. Emit:
   traffic_projection_worker_started

7. Immediately call:
   observer.start(initial_services=active + targets)

   This synchronously emits startup product-health snapshots
   before observer background loop begins.

8. Enter normal worker lifecycle loop.
```

No `worker_started` before writer lock and initialization.

---

# 78. `traffic_projection_worker_started` exact schema

Caller fields:

```text
no Site-specific field required
```

Telemetry runtime fields provide exactly:

```text
artifact_sha
artifact_tree
service_name
process_started_at
```

Additionally emit:

```text
projection_version=self.projection_version
```

as the CLI-selected root Projection version.

No fake health status field.

---

# 79. `serve_forever()` normal iteration and observer outcome isolation

Preserve current order:

```text
active maintenance
        ↓
cleanup if due
        ↓
target window
        ↓
checkpoint
        ↓
wait
```

After each Site maintenance attempt inside `_maintain_version()`:

```text
if self._health_observer is not None:
    self._health_observer.observe_service_site(
        service,
        site_id,
    )
```

Place it in the common `finally` path so it executes after:

```text
success
divergence catch
source failure catch
storage failure catch
unknown failure catch
```

`observe_service_site()` is required by section 63 to contain its own read-only observer failures.

Therefore the common observer call MUST NOT replace:

```text
successful ProjectionRunResult

TrafficProjectionDiverged handling

source failure handling

storage failure handling

unknown-exception fallback
```

with an observer exception.

The writer/business outcome is authoritative.

Observer operational failure is secondary telemetry only.

Other Site/version observations must remain possible after one observer failure.

---

# 80. Exact known-exception behavior in `_maintain_version()`

In `app/traffic_projection/service.py`, import/use these exact exception classes from `.models`:

```text
TrafficProjectionDiverged
TrafficProjectionSourceUnavailable
TrafficProjectionStorageUnavailable
TrafficProjectionStorageCorrupt
```

Preserve compatible:

```text
traffic_projection_scan_failed
```

with the exact branches below.

## A. `TrafficProjectionDiverged`

```text
DO NOT call:
service._record_worker_failure(site_id)

emit:
traffic_projection_scan_failed
projection_version=<service version>
site_id=<site>
error_category="diverged"
```

Post-attempt observer still runs from the common `finally` path and observes canonical diverged health.

## B. `TrafficProjectionSourceUnavailable`

```text
call:
service._record_worker_failure(site_id)

emit:
traffic_projection_worker_source_unavailable
projection_version=<service version>
site_id=<site>
error_category="source_unavailable"

also preserve:
traffic_projection_scan_failed
projection_version=<service version>
site_id=<site>
error_category="source_or_storage"
```

This deliberately preserves current stale/rebuilding failure-state behavior.

## C. `TrafficProjectionStorageUnavailable`

## D. `TrafficProjectionStorageCorrupt`

For either:

```text
DO NOT call:
service._record_worker_failure(site_id)
```

because the failed repository/storage boundary must not be required to accept another best-effort state write.

Emit:

```text
traffic_projection_worker_storage_unavailable
projection_version=<service version>
site_id=<site>
error_category="storage_unavailable"
```

and preserve:

```text
traffic_projection_scan_failed
projection_version=<service version>
site_id=<site>
error_category="source_or_storage"
```

## E. Unknown `Exception`

Preserve current fallback exactly:

```text
service._record_worker_failure(site_id)

emit:
traffic_projection_scan_failed
projection_version=<service version>
site_id=<site>
error_category="source_or_storage"
```

No raw exception telemetry.

After every branch, including success, the common observer `finally` call remains as specified in section 79.

---

# 81. Observer periodic thread independence

Even if:

```text
Projection mutation makes no progress
worker Site maintenance returns early
worker is waiting between scans
```

the observer thread continues every 5 seconds.

The observer must not depend on a successful mutation to emit product heartbeat or detect stuck reconcile.

---

# 82. `TrafficProjectionService.stop()` exact non-blocking extension

Existing:

```python
def stop(self) -> None:
```

must execute exactly:

```text
1. self._stop.set()

2. if self._health_observer is not None:
       self._health_observer.request_stop()
```

`request_stop()` is Event-only and non-blocking.

Do NOT call:

```text
observer.stop(timeout)
observer thread join
```

inside `TrafficProjectionService.stop()`.

Therefore signal handler path remains:

```text
SIGTERM/SIGINT
→ service.stop()
→ Events only
→ return from signal handler
```

Actual bounded observer join remains `serve_forever()` shutdown responsibility.

---

# 83. `serve_forever()` graceful shutdown

Track whether:

```text
worker_started was successfully emitted
```

and whether stop was requested.

On normal stop:

```text
1. main loop exits.

2. inside writer-lock scope:
   call:
   observer.stop(config.shutdown_timeout_seconds)

   observer.stop():
   → request_stop()
   → bounded join.

3. exit writer_lock context,
   releasing exclusive writer ownership.

4. after writer lock is released:
   if startup completed
   AND stop was requested:
       best-effort emit
       traffic_projection_worker_stopped
```

Unexpected exception/crash must not be falsely labelled as graceful worker stop.

Signal handler never performs the join.

---

# 84. `traffic_projection_worker_stopped` schema

Caller field:

```text
projection_version=self.projection_version
```

Runtime fields auto-add:

```text
artifact_sha
artifact_tree
service_name
process_started_at
```

No guarantee under SIGKILL/crash/OOM/host loss.

---

# 85. Projection CLI logger

In `app/traffic_projection/cli.py` remove direct use of:

```python
logging.getLogger(__name__)
```

for Projection service construction.

Use:

```python
logger = configure_traffic_projection_logger()
```

for all CLI commands.

This ensures existing one-shot Projection telemetry is also emitted in the same deterministic wire form.

---

# 86. Artifact identity failure — exact argparse exit path

Identity is mandatory for:

```text
run
repair-site
```

If `capture_loaded_artifact_identity(...)` raises `ArtifactIdentityError`, use exactly:

```python
parser.exit(
    status=1,
    message="traffic-projection: loaded artifact identity unavailable\n",
)
```

Do NOT use:

```python
parser.error(...)
```

for artifact identity failure because argparse `parser.error()` exits with status 2.

Required:

```text
exit code = 1

stderr exactly contains:
traffic-projection: loaded artifact identity unavailable\n
```

No Git stderr.

No raw exception.

No service construction after capture failure.

---

# 87. Command-specific artifact identity capture

For:

```text
run
```

capture:

```python
capture_loaded_artifact_identity(
    "traffic-projection.service"
)
```

For:

```text
repair-site
```

capture:

```python
capture_loaded_artifact_identity(
    "traffic-projection-repair"
)
```

The value:

```text
traffic-projection-repair
```

is frozen.

For these other one-shot commands:

```text
build
mark-ready
activate
mark-failed
rebuild-range
cleanup
```

do NOT require `LoadedArtifactIdentity`.

If `repair-site` identity capture fails:

```text
do not acquire writer lock for repair
do not construct repair service
do not call repair_site()
exit 1 through exact parser.exit path from section 86
```

---

# 88. Projection CLI service construction

For `run`:

```python
TrafficProjectionService(
    config,
    logger=logger,
    projection_version=args.projection_version,
    artifact_identity=run_identity,
)
```

For `repair-site`:

```python
TrafficProjectionService(
    config,
    logger=logger,
    projection_version=args.projection_version,
    artifact_identity=repair_identity,
)
```

where `repair_identity.service_name` is exactly:

```text
traffic-projection-repair
```

For:

```text
build
mark-ready
activate
mark-failed
rebuild-range
cleanup
```

construct service without artifact identity:

```python
TrafficProjectionService(
    config,
    logger=logger,
    projection_version=args.projection_version,
)
```

No identity object is dynamically attached after service construction.

---

# 89. Projection CLI signal handlers

For `run` mode only, install handlers for:

```text
SIGTERM
SIGINT
```

Exact handler action:

```python
service.stop()
```

Do NOT:

```text
call sys.exit inside handler
raise inside handler
emit worker_stopped inside handler
release writer lock inside handler
```

Normal `serve_forever()` unwinds and performs graceful release/event.

One-shot command signal semantics remain unchanged.

---

# 90. CLI graceful process sequence

Required runtime semantics:

```text
SIGTERM / SIGINT
        ↓
service.stop()
        ↓
_stop Event set
        ↓
worker wait/loop exits
        ↓
observer stop/join
        ↓
writer lock released
        ↓
best-effort traffic_projection_worker_stopped
        ↓
CLI exits 0
```

If `serve_forever()` raises startup/runtime exception, preserve non-zero process failure rather than fabricating graceful success.

---

# 91. CaptivePortal service artifact identity is capture-only

`run.py` changes only startup artifact identity capture/logging.

Do NOT:

```text
change Flask lifecycle
change background worker composition
change Admin behavior
change auth
change shutdown order
```

The P0 deployment manifest verification later uses the startup-captured line to prove `captive-portal.service` loaded the approved artifact.

---

# 92. Telemetry event schemas — canonical list

The following P0 event names and caller fields are frozen.

## `traffic_projection_worker_started`

```text
projection_version
+ runtime artifact fields
```

## `traffic_projection_worker_stopped`

```text
projection_version
+ runtime artifact fields
```

## `traffic_projection_product_health`

```text
projection_version
site_id
status
build_state
projection_revision
source_head_utc
projection_head_utc
head_lag_seconds
last_incremental_progress_at
reconcile_sweep_started_at
reconcile_sweep_from_utc
reconcile_sweep_source_head_utc
reconcile_cursor_started_at
reconcile_cursor_cycle_id
last_full_reconcile_completed_at
backlog_cycle_count
error_category
+ runtime artifact fields
```

## `traffic_projection_site_diverged`

```text
projection_version
site_id
status
projection_revision
error_category
+ runtime artifact fields
```

## `traffic_projection_source_identity_failed`

```text
projection_version
site_id
error_category
source_count
projection_count
count_delta
optional reconcile_sweep_from_utc
optional reconcile_sweep_source_head_utc
+ runtime artifact fields
```

## `traffic_projection_stale`

```text
projection_version
site_id
status
build_state
projection_revision
source_head_utc
projection_head_utc
head_lag_seconds
last_incremental_progress_at
last_full_reconcile_completed_at
error_category
+ runtime artifact fields
```

## `traffic_projection_reconcile_stuck`

```text
projection_version
site_id
status
reconcile_sweep_started_at
reconcile_sweep_from_utc
reconcile_cursor_started_at
reconcile_cursor_cycle_id
error_category
+ runtime artifact fields
```

## `traffic_projection_worker_source_unavailable`

```text
projection_version
optional site_id
error_category
+ runtime artifact fields
```

## `traffic_projection_worker_storage_unavailable`

```text
projection_version
optional site_id
error_category
+ runtime artifact fields
```

## `traffic_projection_recovered`

Owner:

```text
TrafficProjectionService.repair_site()
```

```text
projection_version
site_id
status
projection_revision
last_full_reconcile_completed_at
error_category
+ runtime artifact fields
```

No other P0 event payload field is required.

---

# 93. Exact P0 error-category values

This TASK freezes these new machine values:

```text
cleanup_state_unavailable
cleanup_fence_invalid

health_state_unavailable

source_unavailable
storage_unavailable

reconcile_stuck

source_identity
ready_source_identity
```

Existing compatible categories remain unchanged.

Do not expose raw exception class/message as `error_category`.

---

# 94. Health observer is Layer B only

`traffic_projection_product_health` represents:

```text
Projection Site product health
```

It uses:

```text
canonical classify_projection_health()
```

It does NOT claim:

```text
end-to-end Admin Historical delivery health
```

The standalone worker must not call:

```text
TrafficProjectionReadService historical query
HistoricalTrafficReadService
Admin endpoint
browser route
```

to produce heartbeat.

---

# 95. Historical delivery health remains Layer C

Existing:

```text
TrafficProjectionReadService
Historical/Admin delivery path
Traffic Evidence
```

remain responsible for actual Historical delivery availability.

No new reader-side probe is added by this P0 implementation.

Owner + Tech Lead later test this end-to-end.

---

# 96. No aggregate read gate

The observer may expose multiple Site health records.

Do NOT add a process-wide aggregate health condition that prevents:

```text
healthy Site B Historical read
```

because:

```text
Site A diverged
```

Read gate remains Site-scoped.

---

# 97. Coder tests — existing file modifications

Modify:

```text
tests/traffic_projection/test_projection.py
```

to add focused service/repository-boundary tests only.

Do not turn it into production acceptance.

---

# 98. Cleanup test — frozen active sweep

Create a fixture where:

```text
normal_cutoff > reconcile_sweep_from_utc
```

and durable active sweep is coherent.

Assert:

```text
delete_before called with:
reconcile_sweep_from_utc
```

not moving normal cutoff.

---

# 99. Cleanup test — existing delete semantics preserved

Use actual Projection repository rows around the cutoff with combinations of:

```text
source_started_at
source_finished_at
source_abandoned_at
source_state
```

Assert:

```text
new service fence changes only passed cutoff

existing delete_before terminal/timestamp behavior remains unchanged
```

Do not duplicate/reimplement repository SQL in service.

---

# 100. Cleanup test — durable divergence

Given:

```text
status=diverged
```

assert:

```text
zero delete_before mutation for that Site/version
```

Other safe Site remains cleanable.

---

# 101. Cleanup test — exact repair_active

Case 1:

```text
version_status=active
status=rebuilding
last_error_category=repair_delete
```

→ no cleanup.

Case 2:

```text
version_status=active
status=rebuilding
reconcile_sweep_started_at != null
coherent sweep
```

→ no cleanup.

Case 3:

```text
version_status=building
status=rebuilding
no explicit active repair lineage
```

→ NOT automatically repair blocked.

Normal/fenced cleanup rules apply.

---

# 102. Cleanup test — unreadable/missing state

Test:

```text
site_state read raises storage error
```

and:

```text
site_state returns None
```

Required:

```text
zero delete_before call
cleanup continues to independently safe Site
storage-unavailable event
error_category=cleanup_state_unavailable
```

---

# 103. Cleanup test — incoherent frozen state

Test at least:

```text
started set / from null

from set / started null

sweep head UTC set / head cycle null

cursor timestamp set / cursor cycle null

cursor set with no active sweep

invalid sweep timestamp

from > frozen source head
```

Required:

```text
zero delete_before
error_category=cleanup_fence_invalid
```

No normal-cutoff fallback.

---

# 104. Cleanup tests — valid unavailable, dynamic stale and exception boundary

## Persisted `status=unavailable`

Construct coherent ordinary lifecycle state:

```text
status=unavailable
no divergence latch
no repair_active
no active sweep
```

Assert:

```text
status is accepted as a valid persisted Projection status

it is NOT classified as:
cleanup_state_unavailable

normal retention cutoff is permitted
subject to existing delete_before semantics
```

## Dynamic stale is not durable divergence

Construct ordinary durable lifecycle with:

```text
no diverged latch
no repair_active
no active sweep
```

and canonical health inputs that would classify stale.

Assert normal retention cleanup remains permitted.

Cleanup MUST NOT call canonical classifier to decide deletion.

## Exact cleanup storage exception boundary

For:

```text
repository.version_status()
repository.site_state()
```

test:

```text
TrafficProjectionStorageUnavailable
→ safe no-delete
→ cleanup_state_unavailable

TrafficProjectionStorageCorrupt
→ safe no-delete
→ cleanup_state_unavailable
```

Also test:

```text
unexpected RuntimeError
```

Required:

```text
NOT silently converted to cleanup_state_unavailable
NOT swallowed by cleanup authorization helper
propagates to existing worker failure boundary
```

---

# 105. Actual worker scheduling race test

Reproduce:

```text
iteration N:
active reconcile sweep exists / advances

same serve_forever lifecycle:
cleanup becomes due

iteration N+1:
reconcile resumes/completes
```

Assert:

```text
protected rows survive
source/projection identity matches
Site does not enter diverged
```

Use controlled monotonic/clock test doubles.

---

# 106. Immediate cleanup after restart test

Model:

```text
durable unfinished reconcile exists

new service object:
_last_cleanup=0

monotonic makes cleanup immediately due
```

Run first lifecycle iteration.

Assert persisted fence is used and protected rows survive.

No assumed 24-hour startup grace.

---

# 107. Restart during durable sweep test

Create unfinished persisted reconcile state.

Use service instance A for initial progress.

Create new service instance B against same Projection DB.

Make cleanup due immediately.

Assert:

```text
service B reads persisted sweep boundary
protected rows survive
reconcile resumes
```

---

# 108. Direct production timing topology regression

Fixture timestamps:

```text
frozen lower bound =
2026-08-27T08:26:05.244Z

row A =
2026-08-27T08:26:28.388Z

row B =
2026-08-27T08:27:02.854Z

moving normal cutoff >
row B
```

While sweep active assert both derived rows survive.

After reconcile proof:

```text
source-only=0
projection-only=0
```

Exact production UUIDs are not required.

---

# 109. Source identity telemetry test

Force `source_count != projection_count`.

Assert emitted JSON event:

```text
traffic_projection_source_identity_failed
```

contains exact:

```text
projection_version
site_id
error_category
source_count
projection_count
count_delta
frozen reconcile boundary fields
```

No raw cycle source payload.

---

# 110. Artifact identity tests

Add:

```text
tests/test_artifact_identity.py
```

Cover:

```text
valid HEAD/tree capture

exact two git commands

canonical process timestamp

safe_fields exact keys

json_line exact keys/canonical single-line JSON

invalid Git exit
timeout
non-hex SHA
uppercase SHA
wrong length
invalid tree

all failures:
ArtifactIdentityError
sanitized message

immutability:
capture A
simulate repository now B
existing LoadedArtifactIdentity remains A
```

Do not test production GitHub.

---

# 111. Telemetry tests

Add:

```text
tests/traffic_projection/test_telemetry.py
```

Cover exact dedicated logger ownership.

Pre-seed exactly the authorized logger:

```text
captivportal.traffic_projection
```

with one or more unmarked handlers.

There MUST be no logger introduced by implementation or tests with the misspelled name:

```text
captvportal.traffic_projection
```

Call:

```text
configure_traffic_projection_logger()
```

Assert exactly:

```text
logger.name == "captivportal.traffic_projection"

logger.level == logging.INFO

logger.propagate is False

len(logger.handlers) == 1

logger.handlers[0]
is logging.StreamHandler

handler level == logging.INFO

formatter format == "%(message)s"

pre-existing direct handlers were removed
and closed best-effort

repeated configure call
still leaves exactly one direct handler

one emitted event
→ one output line
```

Also cover telemetry wire behavior:

```text
one JSON line
canonical deterministic encoding

SAFE_FIELDS expansion

runtime artifact fields auto-added
runtime fields cannot be caller-overridden

unsupported object field omitted
long string bounded
NaN/Inf not emitted as invalid JSON
unknown field omitted

no raw exception/object repr leakage
```

Do not modify/test generic CaptivPortal logger ownership.

---

# 112. Health observer tests

Add:

```text
tests/traffic_projection/test_health_observer.py
```

Cover startup and computed-health transitions:

```text
startup already diverged
→ product-health emitted
→ no fabricated site_diverged transition

startup healthy
→ product-health emitted

canonical computed healthy→stale
with unchanged stored status
→ traffic_projection_stale

computed transition to diverged
→ site_diverged
```

Prove observer has no repair-recovery ownership:

```text
health_observer module does not depend on _repair_active
observer does not keep repair_lineage_seen
observer never emits traffic_projection_recovered
```

Exact source availability tests:

```text
source.head raises
→ observation source_available=False

source.head returns None
→ observation source_available=False

source.head returns valid tuple
→ observation source_available=True

canonical classifier receives exactly that same boolean
```

Source transition behavior:

```text
first/startup source unavailable
→ worker_source_unavailable

continued unavailable every 5s
→ no repeated transition event

source recovers
→ normal observation resumes
```

Exact product-health provenance:

```text
health-derived fields come only from:
observation["health"]

sweep/cursor/error_category come only from:
observation["site_state"]

projection_version comes only from:
service.projection_version

no alternate precedence
```

Storage/unreadable fallback:

```text
first storage failure
→ traffic_projection_worker_storage_unavailable
→ immediate unavailable product-health

status="unavailable"
error_category="health_state_unavailable"

ALL other product-health schema fields = null

no stale observer-memory field leakage

additional 5-second failed ticks
→ no repeated operational storage event

heartbeat target/deadline
→ unavailable product-health repeats

successful observation after failure
→ previous_storage_available=True
→ canonical observation resumes

no separate storage-recovered event
```

Heartbeat budget with fake monotonic:

```text
startup heartbeat at T0

normal target at T0+55

observer scheduling resolution=5s

no key is intentionally scheduled
beyond architectural 60-second max
```

Reconcile stuck:

```text
cursor unchanged for >=60s
→ reconcile_stuck on next bounded evaluation

cursor changes
→ timer reset

last_incremental_progress_at changes
while reconcile cursor unchanged
→ still stuck
```

Stop lifecycle:

```text
request_stop()
→ sets Event only
→ no join

stop(timeout)
→ calls request_stop()
→ bounded join
```

Observer survival:

```text
one Site health observation fails
→ observer remains usable

later healthy Site/version is still observed

periodic loop does not terminate permanently

post-maintenance observer failure
→ cannot replace original maintenance outcome
```

Use fake monotonic clock.

No sleep-based 55/60-second tests.

---

# 113. CLI tests

Add:

```text
tests/traffic_projection/test_cli.py
```

Cover:

```text
run uses configure_traffic_projection_logger

run captures:
service_name=traffic-projection.service

run artifact capture failure:
parser.exit status=1
exact sanitized stderr
service not constructed/started

run passes immutable identity to service

repair-site captures:
service_name=traffic-projection-repair

repair-site identity failure:
parser.exit status=1
exact sanitized stderr
writer lock not acquired
repair not started

repair-site passes immutable identity to service

other one-shot commands:
artifact identity not required
```

Signal lifecycle:

```text
SIGTERM handler:
calls service.stop()
does not raise/exit
does not join observer in signal handler

SIGINT handler:
calls service.stop()
does not raise/exit
does not join observer in signal handler

TrafficProjectionService.stop():
observer.request_stop()
but no blocking observer.stop(timeout)
```

Also cover:

```text
worker_started not emitted
when writer lock acquisition fails

graceful run:
stop requested
serve_forever returns cleanly
```

For both `run` and `repair-site` identity failure assert stderr is exactly:

```text
traffic-projection: loaded artifact identity unavailable
```

with one trailing newline, and contains:

```text
no Git stderr
no raw exception
```

No real OS process kill required in Coder narrow tests.

---

# 114. Worker/service lifecycle tests

In:

```text
tests/traffic_projection/test_projection.py
```

cover `serve_forever()` with a test artifact identity:

```text
worker_started only after:
initialize + writer lock

startup product-health emitted immediately

TrafficProjectionService.stop():
sets service Event
requests observer stop
does NOT join observer

serve_forever graceful shutdown:
observer.stop(timeout) performs bounded join
writer lock releases
worker_stopped emitted after release

unexpected exception:
no false worker_stopped
```

Prove observer cannot replace Projection maintenance outcome:

```text
successful maintenance
+
observer post-attempt failure
→ successful maintenance result remains authoritative

TrafficProjectionDiverged
+
observer post-attempt failure
→ diverged branch remains authoritative

source/storage failure
+
observer post-attempt failure
→ original failure branch remains authoritative
```

Cover authoritative recovery ownership:

```text
repair completes in one repair_site invocation
→ traffic_projection_recovered exactly once

multi-quantum worker repair
→ no recovered on incomplete quantum
→ final repair_site quantum emits recovered exactly once

ordinary reconcile/catching_up→healthy
→ no recovered
```

Cover exact `_maintain_version()` exception behavior:

```text
TrafficProjectionDiverged
→ _record_worker_failure NOT called
→ scan_failed/diverged preserved

TrafficProjectionSourceUnavailable
→ _record_worker_failure called
→ worker_source_unavailable/source_unavailable
→ compatible scan_failed/source_or_storage

TrafficProjectionStorageUnavailable
→ _record_worker_failure NOT called
→ worker_storage_unavailable/storage_unavailable
→ compatible scan_failed/source_or_storage

TrafficProjectionStorageCorrupt
→ _record_worker_failure NOT called
→ worker_storage_unavailable/storage_unavailable
→ compatible scan_failed/source_or_storage

unknown Exception
→ _record_worker_failure called
→ compatible scan_failed/source_or_storage
```

No raw exception telemetry.

---

# 115. Health classifier reuse regression

Tests must monkeypatch/spy existing:

```text
classify_projection_health()
```

through `TrafficProjectionService.health_observation()` and prove the observer consumes its resulting status.

Do not duplicate expected classifier decision logic inside the observer test implementation.

---

# 116. Healthy-only Historical read regression

Coder must run existing:

```text
tests/traffic_projection/test_projected_read.py
```

unchanged.

Do not modify read-service semantics.

Any failure caused by this P0 implementation is a STOP/regression.

---

# 117. `run.py` narrow artifact test boundary

No broad application startup test is required from Coder.

`tests/test_artifact_identity.py` covers helper correctness.

`run.py` change must remain limited to:

```text
capture identity
log identity
fail startup if capture impossible
```

Owner + Tech Lead later verify actual `captive-portal.service` startup identity in controlled deployment acceptance.

---

# 118. Coder exact narrow test commands

Run from repository root:

```text
python -m pytest -q tests/test_artifact_identity.py
```

```text
python -m pytest -q \
  tests/traffic_projection/test_telemetry.py \
  tests/traffic_projection/test_health_observer.py \
  tests/traffic_projection/test_cli.py
```

```text
python -m pytest -q tests/traffic_projection/test_projection.py
```

```text
python -m pytest -q tests/traffic_projection/test_projected_read.py
```

Then:

```text
python -m compileall -q \
  app/artifact_identity.py \
  app/traffic_projection \
  run.py
```

Then:

```text
git diff --check
```

Do NOT run the full repository test suite under the Coder TASK.

---

# 119. Coder forbidden test/operation scope

Coder must NOT run or claim:

```text
Central Full Gate

production smoke

production traffic-projection.service

production repair-site

production rebuild-range

production cleanup

production DB write

Grafana production acceptance

Alloy/Loki production acceptance

browser full regression

deployment

rollback

incident closure
```

---

# 120. Coder implementation constraints

Do NOT:

```text
modify retention_days

modify delete_before SQL

change Projection schema

add a telemetry DB/outbox

add request-time Historical probes

add a second writer

add a second process/service

add external notifications

change Historical accepted health states

change Traffic formulas

change Observation data

change repair-site semantics

auto-clear diverged

auto-repair diverged

change systemd unit files

change generic CaptivPortal logger globally
```

---

# 121. No raw exception telemetry

All P0 telemetry must use bounded machine categories.

Forbidden:

```text
error=str(exc)
exception=repr(exc)
traceback
raw DB state
raw Observation row
SQL text
filesystem secrets
```

Existing logger exception behavior outside this P0 telemetry path is not redesigned.

---

# 122. Telemetry JSON must not become business dependency

If telemetry field normalization encounters an unsupported value:

```text
omit that field
continue
```

Do not fail:

```text
reconcile
cleanup
repair
worker maintenance
```

because a telemetry field was malformed.

The only logger startup failure that may prevent worker startup is inability to establish required runtime logging/identity configuration before `worker_started`.

---

# 123. Artifact identity failure is startup-fatal

For both long-running artifact-owned processes after this fix:

```text
reliable startup artifact identity unavailable
→ startup acceptance fails
```

`run.py`:

```text
SystemExit(1)
```

traffic projection `run`:

```text
CLI exit 1
```

Do not continue while reporting unknown/fabricated loaded SHA.

---

# 124. Production deployment changes are NOT Coder code scope

The frozen production deployment procedure is:

```text
STOP:
1. traffic-projection.service
2. captive-portal.service

prove both app PIDs gone

mutate exact approved artifact

START:
1. captive-portal.service
2. readiness proof
3. traffic-projection.service
```

This procedure is executed later by Owner + Tech Lead.

Coder does not write a deploy script in this TASK.

---

# 125. Production repair changes are NOT Coder code scope

After fixed artifact acceptance, Owner + Tech Lead later perform:

```text
forensic incident manifest

consistent Projection backup

coherent fixed deploy

repair-site once with worker stopped

start/enable fixed Projection worker

wait for durable repair/reconcile

full proof

five Historical Admin product validation

journal→Alloy→Loki→Grafana proof
```

Coder performs none of these production operations.

---

# 126. Coder STOP conditions

Coder MUST STOP with evidence if any of these becomes necessary:

```text
modify repository.py/delete_before()

Projection schema change

new durable reconcile field

new table/index/version

Observation mutation

new Projection writer

new systemd service

new canonical health algorithm

change classify_projection_health()

broaden Historical read states

change Traffic formulas

change retention duration

transactional telemetry outbox

request-time Historical heartbeat probe

external notification integration

different repair_active predicate

different repair-site lifecycle

cannot capture immutable startup Git SHA/tree

cannot implement cleanup safely
within current service/repository boundary

must touch a NO-TOUCH file
```

No workaround.

---

# 127. Coder handoff — exact required format

Coder returns one handoff containing exactly these sections.

## A. Identity

```text
TASK =
TASK-TRAFFIC-PROJECTION-LIFECYCLE-CONSISTENCY-01

AUTHORIZED BASELINE SHA =
<sha>

AUTHORIZED BASELINE TREE =
<tree>

CANDIDATE HEAD =
<sha or WORKTREE-UNCOMMITTED>

CANDIDATE TREE =
<tree if commit exists, otherwise N/A>
```

## B. Changed files

```text
MODIFIED:
...

ADDED:
...

UNEXPECTED FILES:
NONE
```

If unexpected file exists:

```text
STOP
```

## C. Implementation summary

Brief factual mapping:

```text
cleanup fence
cleanup fail-safe
repair_active reuse
health observer
telemetry JSON
artifact identity
signal lifecycle
```

No design essay.

## D. Narrow tests

For each exact command from section 118:

```text
COMMAND =
...

RESULT =
PASS / FAIL

TEST COUNT =
...
```

## E. Static checks

```text
compileall = PASS/FAIL
git diff --check = PASS/FAIL
```

## F. Git state

```text
git status --short
git diff --stat
```

## G. Stop conditions

```text
STOP CONDITION ENCOUNTERED =
NO
```

or exact evidence.

## H. Explicit non-claims

Coder must state:

```text
CENTRAL FULL GATE = NOT RUN
PRODUCTION TESTS = NOT RUN
PRODUCTION REPAIR = NOT RUN
GRAFANA/LOKI ACCEPTANCE = NOT RUN
DEPLOY = NOT RUN
OFFICIAL ACCEPTANCE = NOT CLAIMED
```

---

# 128. Git authorization boundary

This TASK document itself does NOT authorize:

```text
branch creation
commit
push
PR
merge
```

When Owner later says:

```text
Начинай разработку по TASK-TRAFFIC-PROJECTION-LIFECYCLE-CONSISTENCY-01-FINAL
```

that authorizes:

```text
local implementation
local narrow tests
Coder handoff
```

only.

GitHub publication remains a separate Owner/Tech Lead instruction unless explicitly included in the Owner authorization.

---

# 129. Owner + Tech Lead post-Coder acceptance — informational only

After handoff, Owner + Tech Lead independently verify:

```text
fresh candidate identity

exact diff/source review

actual worker scheduling race

restart with cleanup immediately due

durable frozen sweep restart

cleanup terminal boundary semantics

direct production timing topology

multi-Site isolation

canonical computed health transitions

reconcile-stuck behavior

structured journal JSON

Alloy → Loki → Grafana

startup artifact identity for both services

graceful and abrupt worker loss

artifact-coherent deployment

forensic capture

canonical production repair

Historical read recovery

five affected Historical Admin products

non-Projection Traffic regression
```

Coder does not claim these PASS.

---

# 129A. Tech Lead final 8-correction closure

```text
FINAL CONSISTENCY SCAN:

FIX 1
_health_observer no longer consumes/imports _repair_active
repair_active consumers limited to:
normal worker repair continuation
cleanup repair block
= CLOSED

FIX 2
observer stop API:
request_stop() = Event only / no join
stop(timeout) = request + bounded join
TrafficProjectionService.stop() = non-blocking
= CLOSED

FIX 3
source_available exact canonical meaning:
head exception or None → False
valid head tuple → True
same bool passed to classifier and observer
= CLOSED

FIX 4
heartbeat:
observer tick = 5 seconds
normal heartbeat target = 55 seconds
architectural maximum = 60 seconds
= CLOSED

FIX 5
storage health failure telemetry:
transition-bounded operational event
+
periodic unavailable product-health heartbeat
no 5-second event flood
= CLOSED

FIX 6
cleanup storage exception boundary:
TrafficProjectionStorageUnavailable
TrafficProjectionStorageCorrupt
ONLY
unexpected exceptions propagate
= CLOSED

FIX 7
read-only observer failure:
must not mutate Projection
must not replace maintenance outcome
must not terminate observer permanently
other Site/version observations continue
= CLOSED

FIX 8
authorized logger name:
captivportal.traffic_projection

misspelled logger:
captvportal.traffic_projection
MUST NOT be introduced
= CLOSED

FUNDAMENTAL ARCHITECTURE CHANGE =
NO

SCHEMA CHANGE =
NO

repository.py CHANGE =
NO

health.py CHANGE =
NO

read_service.py CHANGE =
NO

CODER DISCRETIONARY DESIGN CHOICES =
0

OPEN IMPLEMENTATION QUESTIONS =
0

IMPLEMENTATION AUTHORIZATION =
NOT GRANTED

CODER =
HOLD

PRODUCTION WRITER =
STOPPED + DISABLED

PRODUCTION REPAIR =
HOLD
```

---

# 130. Production recovery gate remains closed

Until Owner + Tech Lead accept candidate:

```text
traffic-projection.service =
STOPPED + DISABLED

production Projection DB =
NO REPAIR

production Observation =
CONTINUES AUTHORITATIVE COLLECTION
```

Do not change containment during development.

---

# 131. FINAL-R2 implementation contract summary

```text
TASK =
TASK-TRAFFIC-PROJECTION-LIFECYCLE-CONSISTENCY-01

TYPE =
P0 PERMANENT FIX

BASELINE =
ff39fe888c53361a7c65a034eaddb0ce92cc4a12

TREE =
f6f1068a579c1f1c6f1debeae2e6a1e0da4823b8

ROOT FIX =
DURABLE PER-SITE/PER-VERSION CLEANUP FENCE

NORMAL CUTOFF =
now - retention_days

ACTIVE SWEEP CUTOFF =
min(normal_cutoff, reconcile_sweep_from_utc)

DELETE SQL/PREDICATE =
UNCHANGED

CLEANUP STATE AUTHORITY =
current durable lifecycle state

CLEANUP STORAGE CATCH =
TrafficProjectionStorageUnavailable
TrafficProjectionStorageCorrupt
ONLY

UNEXPECTED CLEANUP EXCEPTION =
PROPAGATES
NOT RECLASSIFIED

UNKNOWN/INCOHERENT CLEANUP SAFETY =
NO MUTATION

DIVERGED CLEANUP =
BLOCKED

REPAIR CLEANUP =
BLOCKED

repair_active =
active version
+
status rebuilding
+
(
  repair_delete
  OR active durable reconcile sweep
)

repair_active CONSUMERS =
normal worker repair continuation
cleanup repair block
ONLY

HEALTH OBSERVER _repair_active DEPENDENCY =
NO

GENERIC rebuilding =
NOT repair_active

SCHEMA CHANGE =
NO

PERSISTED STATUS ALLOWLIST =
healthy
catching_up
stale
unavailable
rebuilding
diverged

schema.py =
DOES NOT EXIST
MUST NOT BE CREATED

HEALTH AUTHORITY =
existing classify_projection_health()

SOURCE_AVAILABLE =
exact canonical classifier input:
head exception or head None → False
valid head tuple → True

HEALTH OBSERVER =
one read-only daemon thread
inside existing Projection process

OBSERVER FAILURE =
MUST NOT replace Projection business outcome
MUST NOT terminate periodic observer permanently

SECOND WRITER =
NO

OBSERVER TICK =
5 seconds

HEARTBEAT TARGET =
55 seconds

HEARTBEAT ARCHITECTURAL MAX =
60 seconds

RECONCILE STUCK =
unchanged reconcile cursor tuple for 60 seconds

STORAGE FAILURE TELEMETRY =
transition-bounded operational event
+
periodic unavailable product-health heartbeat

TRANSITION EVENTS =
BEST-EFFORT IMMEDIATE

RECOVERED OWNER =
TrafficProjectionService.repair_site()

OBSERVER RECOVERED OWNERSHIP =
NO

REPAIR-SITE ARTIFACT IDENTITY =
REQUIRED
service_name=traffic-projection-repair

IDENTITY FAILURE EXIT =
parser.exit(status=1)
exact sanitized stderr

OBSERVER STOP API =
request_stop()
+
stop(timeout)

TrafficProjectionService.stop() =
Event-only / non-blocking observer stop request

SIGNAL HANDLER JOIN =
NO

STARTUP SNAPSHOT =
IMMEDIATE AFTER worker_started

TELEMETRY WIRE =
single-line deterministic JSON

PROJECTION LOGGER =
captivportal.traffic_projection
owns exactly one direct stderr StreamHandler

MISSPELLED LOGGER captvportal.traffic_projection =
FORBIDDEN / MUST NOT BE INTRODUCED

PRODUCT-HEALTH FIELD SOURCES =
health fields from canonical health
sweep/cursor/error from Site state
projection_version from service

STORAGE HEALTH FALLBACK =
status unavailable
health_state_unavailable
all other product-health fields null
no stale-memory leakage

TELEMETRY PREFIX =
traffic_projection_

ARTIFACT IDENTITY =
shared startup capture helper

ARTIFACT SHA/TREE =
captured once at process startup
immutable for lifetime

PORTAL IDENTITY =
captivportal_loaded_artifact_identity line

PROJECTION STARTED =
after identity + config + writer lock + initialization

PROJECTION STOPPED =
best-effort graceful only
after writer lock release

SIGTERM/SIGINT =
service.stop()
Event-only request
normal unwind

HISTORICAL READ SEMANTICS =
UNCHANGED

OBSERVATION =
UNTOUCHED

REPAIR SEMANTICS =
UNCHANGED

SYSTEMD TOPOLOGY =
UNCHANGED

PRODUCTION WRITER =
REMAINS STOPPED/DISABLED UNTIL ACCEPTED FIX

CODER DISCRETIONARY DESIGN CHOICES =
0

OPEN IMPLEMENTATION QUESTIONS =
0

CODER PLAN =
FORBIDDEN

CODER =
HOLD

IMPLEMENTATION AUTHORIZATION =
NOT GRANTED

PRODUCTION REPAIR =
HOLD
```

---

# 132. Next workflow

```text
IMPLEMENTATION-READY FINAL-R2
        ↓
Tech Lead final consistency scan
        ↓
if PASS:
Owner reviews
        ↓
Owner explicit:
"Начинай разработку по TASK-TRAFFIC-PROJECTION-LIFECYCLE-CONSISTENCY-01-FINAL"
        ↓
Coder implements immediately
        ↓
only narrow tests from this TASK
        ↓
Coder handoff
        ↓
Owner + Tech Lead official acceptance
        ↓
only then controlled production recovery
```

No Coder implementation or production repair is authorized by this document alone.
