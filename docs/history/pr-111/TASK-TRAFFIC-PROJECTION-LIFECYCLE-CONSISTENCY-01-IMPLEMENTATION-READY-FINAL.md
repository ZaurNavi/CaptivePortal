# IMPLEMENTATION-READY FINAL — TASK-TRAFFIC-PROJECTION-LIFECYCLE-CONSISTENCY-01

**Project:** CaptivPortal  
**Priority:** `P0 / PRODUCTION INCIDENT`  
**Architecture authority:** `ARCHITECTURE FINAL-R1 — PASS`  
**Tech Lead source rebind:** `COMPLETE`  
**Deliverable:** exact implementation-ready Coder TASK for final Tech Lead line-by-line review  
**Status:** `FINAL TASK CANDIDATE — CODER HOLD`  
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
app/traffic_projection/schema.py
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

The permanent deployment procedure and Grafana acceptance are Owner + Tech Lead operations, not Coder implementation in this TASK.

If implementation appears to require a NO-TOUCH file:

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

This helper is used by:

```text
normal worker repair continuation classification
cleanup repair block
health observer repair-lineage recognition
```

where applicable.

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

# 13. Cleanup state read

`_cleanup_cutoff_for_site()` must begin by reading:

```python
state = self.repository.site_state(site_id)
```

Catch Projection storage/read exceptions.

If state read fails:

```text
return None

emit:
traffic_projection_worker_storage_unavailable
error_category=cleanup_state_unavailable
```

No deletion.

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

For cleanup authorization, stored Site `status` must be one of:

```text
healthy
catching_up
stale
rebuilding
diverged
```

Any other or missing status:

```text
return None
emit:
traffic_projection_worker_storage_unavailable
error_category=cleanup_state_unavailable
```

This is cleanup-safety failure.

It does NOT mark Site diverged.

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

2. If version_status not in:
   active | building | ready
   return 0.

3. If version_status read fails:
   emit traffic_projection_worker_storage_unavailable
   error_category=cleanup_state_unavailable
   return 0.

4. Calculate normal_cutoff once for this cleanup invocation:
   clock_now - retention_days.

5. For each configured site_id:
   call _cleanup_cutoff_for_site(
       site_id,
       normal_cutoff,
       version_status,
   )

6. If result is None:
   perform zero delete_before calls for that Site.
   continue to next independently safe Site.

7. If cutoff returned:
   keep existing bounded chunk loop
   and call existing:
   repository.delete_before(site_id, cutoff)

8. Preserve:
   MAX_CLEANUP_CHUNKS_PER_INVOCATION
   MAX_BULK_CYCLES_PER_TRANSACTION
   checkpoint_passive()
```

Do not change row deletion SQL.

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

# 41. Projection telemetry logger — exact new function

In:

```text
app/traffic_projection/telemetry.py
```

add:

```python
def configure_traffic_projection_logger() -> logging.Logger:
```

Logger name:

```text
captivportal.traffic_projection
```

Production contract:

```text
level = INFO
propagate = False
one StreamHandler to stderr
handler level = INFO
formatter = "%(message)s"
```

Use a private handler marker to prevent duplicate handler installation on repeated configuration calls.

Do not modify `app/logger.py`.

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

One-shot commands may continue with `artifact_identity=None`.

Long-running `serve_forever()` may not.

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
bool

version_status =
str | None
```

---

# 50. `health_observation()` classifier contract

The method must contain the current `health()` input assembly logic:

```text
read site_state
read version record/status
determine version_available
read current source head
overlay current source head into local state copy
call existing classify_projection_health()
```

Do NOT implement a second classifier.

Source read exception:

```text
source_available = False
current_head = None
```

Storage/repository exceptions propagate to caller for observer classification.

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
HEARTBEAT_INTERVAL_SECONDS = 60.0
RECONCILE_STUCK_SECONDS = 60.0
```

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

Maintain process-memory maps for:

```text
previous computed health status

previous source_available condition

last heartbeat monotonic time

last reconcile progress identity

reconcile progress identity last-change monotonic time

reconcile_stuck already-emitted flag

repair lineage seen flag
```

No persistence.

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

# 58. Observer `stop()`

Exact method:

```python
def stop(
    self,
    timeout_seconds: float,
) -> bool:
```

Behavior:

```text
set observer stop Event
join daemon thread up to timeout
return True if thread stopped
return False if still alive
```

Do not raise solely because graceful observer join times out.

---

# 59. Observer periodic service enumeration

Each periodic iteration calls:

```python
root_service._health_worker_services()
```

This is read-only.

If service/version enumeration fails due Projection storage:

```text
emit:
traffic_projection_worker_storage_unavailable
error_category=health_state_unavailable
```

Then for the root service's configured Site IDs emit best-effort:

```text
traffic_projection_product_health
status=unavailable
```

using root projection version.

Do not mutate Site state.

---

# 60. Observer Site health read

For each Site/version call:

```python
service.health_observation(site_id)
```

If repository/storage read fails:

```text
emit:
traffic_projection_worker_storage_unavailable
error_category=health_state_unavailable

emit product-health:
status=unavailable
```

No Site mutation.

---

# 61. Product-health event exact schema

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

`status` is the existing canonical computed health classifier status.

Do not add Historical delivery fields.

---

# 62. Product-health heartbeat timing

Emit product health:

```text
immediately at startup
```

and thereafter per Site/version whenever:

```text
60 seconds have elapsed
since that key's last product-health heartbeat
```

Maximum interval:

```text
<=60 seconds
```

The 5-second observer loop is the scheduling resolution.

---

# 63. Worker-triggered immediate observation

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

The periodic observer remains responsible for heartbeat/reconcile-stuck even when mutation work is idle or fails.

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

Product heartbeat continues to show current canonical status.

---

# 68. Storage-unavailable operational event

For observer storage/read failure emit:

```text
traffic_projection_worker_storage_unavailable
```

exact caller fields:

```text
projection_version
site_id when known
error_category="health_state_unavailable"
```

Cleanup may use the same event with:

```text
cleanup_state_unavailable
cleanup_fence_invalid
```

Do not include raw exception text.

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

# 72. Repair lineage tracking

Observer marks:

```text
repair_lineage_seen=True
```

only after observing exact:

```python
_repair_active(
    version_status=observation["version_status"],
    state=site_state,
)
```

Do not set it merely because:

```text
computed health is rebuilding
stored status is rebuilding
computed health was diverged
```

Explicit durable repair lineage is required.

---

# 73. Recovered event conditions

Emit:

```text
traffic_projection_recovered
```

exactly once per observed repair lineage when all are true:

```text
repair_lineage_seen=True

current canonical computed status == "healthy"

site_state.last_full_reconcile_completed_at is non-null

site_state.last_deep_audit_at is non-null

site_state.last_error_category is null

site_state.reconcile_sweep_started_at is null
```

After emission:

```text
repair_lineage_seen=False
```

---

# 74. Recovered event exact schema

Caller fields:

```text
projection_version
site_id
status="healthy"
projection_revision
last_full_reconcile_completed_at
error_category=None
```

Artifact fields auto-added.

Do NOT emit for:

```text
ordinary catching_up → healthy
ordinary startup rebuilding → healthy
startup first observation already healthy
```

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

# 79. `serve_forever()` normal iteration

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

Place this in a `finally` path so it executes after:

```text
success
divergence catch
source/storage failure catch
```

The observer call itself must not replace the current worker failure handling.

---

# 80. Worker source/storage failure events in `_maintain_version()`

Preserve existing bounded failure handling and existing:

```text
traffic_projection_scan_failed
```

Add explicit event classification where the exception type is known.

Catch:

```python
TrafficProjectionSourceUnavailable
```

separately and emit:

```text
traffic_projection_worker_source_unavailable
error_category="source_unavailable"
```

Catch Projection repository/storage exceptions:

```text
TrafficProjectionStorageUnavailable
TrafficProjectionStorageCorrupt
```

and emit:

```text
traffic_projection_worker_storage_unavailable
error_category="storage_unavailable"
```

For existing generic unknown exception handling, preserve sanitized:

```text
traffic_projection_scan_failed
error_category=source_or_storage
```

Do not expose raw exception strings.

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

# 82. `stop()` exact extension

Existing:

```python
def stop(self) -> None:
    self._stop.set()
```

must additionally:

```text
request observer stop if observer exists
```

Do NOT join from signal handler itself.

Join occurs in `serve_forever()` shutdown `finally`.

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
   stop/join health observer
   using config.shutdown_timeout_seconds.

3. exit writer_lock context,
   releasing exclusive writer ownership.

4. after writer lock is released:
   if startup completed
   AND stop was requested:
       best-effort emit
       traffic_projection_worker_stopped
```

Unexpected exception/crash must not be falsely labelled as graceful worker stop.

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

# 86. Projection `run` artifact identity capture

For:

```text
args.command == "run"
```

after configuration validation and before service construction call:

```python
capture_loaded_artifact_identity(
    "traffic-projection.service"
)
```

If it fails:

```text
print only sanitized CLI error through argparse exit path
exit code = 1
```

Exact public text:

```text
traffic-projection: loaded artifact identity unavailable
```

Do not include Git stderr/raw exception.

---

# 87. One-shot CLI artifact identity behavior

For:

```text
build
mark-ready
activate
mark-failed
repair-site
rebuild-range
cleanup
```

do NOT require `LoadedArtifactIdentity`.

They continue using existing explicit writer-lock behavior.

Production repair acceptance separately proves the fixed filesystem artifact before one-shot `repair-site`.

---

# 88. Projection CLI service construction

For `run`:

```python
TrafficProjectionService(
    config,
    logger=logger,
    projection_version=args.projection_version,
    artifact_identity=identity,
)
```

For one-shot commands:

```python
TrafficProjectionService(
    config,
    logger=logger,
    projection_version=args.projection_version,
)
```

No identity object is dynamically attached later.

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

# 104. Cleanup test — dynamic stale is not durable divergence

Construct ordinary durable lifecycle with:

```text
no diverged latch
no repair_active
no active sweep
```

and canonical health inputs that would classify stale.

Assert normal retention cleanup remains permitted.

Cleanup MUST NOT call canonical classifier to decide deletion.

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

Cover:

```text
configure_traffic_projection_logger():
INFO
propagate false
message-only handler
no duplicate marked handler

emit:
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

---

# 112. Health observer tests

Add:

```text
tests/traffic_projection/test_health_observer.py
```

Cover:

```text
startup:
already diverged
→ product-health emitted
→ no fabricated site_diverged transition

startup healthy
→ product-health emitted

canonical computed healthy→stale
with unchanged stored status
→ traffic_projection_stale

computed transition to diverged
→ site_diverged

source unavailable first observation
→ worker_source_unavailable
not repeated every 5s unchanged

heartbeat:
next product health by <=60s

reconcile cursor unchanged 60s
→ reconcile_stuck

reconcile cursor changes
→ timer reset

last_incremental_progress_at changes
while reconcile cursor unchanged
→ still stuck

repair_active observed
then new healthy proof
→ recovered once

catching_up→healthy without repair lineage
→ no recovered

observer storage failure
→ storage-unavailable
→ product-health unavailable

observer thread:
read-only
stop/join
```

Use fake monotonic clock.

No sleep-based 60-second tests.

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

artifact capture failure:
exit 1
sanitized text
service not started

run passes immutable identity to service

SIGTERM handler:
calls service.stop()
does not raise/exit in handler

SIGINT handler:
calls service.stop()

one-shot repair-site:
does not require artifact identity
preserves writer_lock path

worker_started not emitted
when writer lock acquisition fails

graceful run:
stop requested
serve_forever returns cleanly
```

No real OS process kill required in Coder narrow tests.

---

# 114. Worker lifecycle tests

In:

```text
tests/traffic_projection/test_projection.py
```

also cover `serve_forever()` with a test artifact identity:

```text
worker_started only after:
initialize + writer lock

startup product-health emitted immediately

graceful stop:
observer stops
writer lock releases
worker_stopped emitted after release

unexpected exception:
no false worker_stopped

health observer receives observe-now
after Site maintenance attempt
```

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

# 131. Final implementation contract summary

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

GENERIC rebuilding =
NOT repair_active

SCHEMA CHANGE =
NO

HEALTH AUTHORITY =
existing classify_projection_health()

HEALTH OBSERVER =
one read-only daemon thread
inside existing Projection process

SECOND WRITER =
NO

HEARTBEAT =
traffic_projection_product_health
<=60 seconds

OBSERVER TICK =
5 seconds

RECONCILE STUCK =
unchanged reconcile cursor tuple for 60 seconds

TRANSITION EVENTS =
BEST-EFFORT IMMEDIATE

STARTUP SNAPSHOT =
IMMEDIATE AFTER worker_started

TELEMETRY WIRE =
single-line deterministic JSON

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
IMPLEMENTATION-READY FINAL
        ↓
Tech Lead line-by-line review
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
