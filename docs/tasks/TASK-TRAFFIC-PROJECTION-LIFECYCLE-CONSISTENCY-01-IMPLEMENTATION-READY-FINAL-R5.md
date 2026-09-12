# IMPLEMENTATION-READY FINAL-R5 — TASK-TRAFFIC-PROJECTION-LIFECYCLE-CONSISTENCY-01 — PRODUCTION CLOSURE

**Project:** CaptivPortal
**Priority:** `P0 / PRODUCTION INCIDENT`
**Architecture authority:** `ARCHITECTURE FINAL-R1 — PASS`
**Historical implementation milestone:** `IMPLEMENTATION-READY FINAL-R5`
**Accepted implementation:** `FINAL-R5 + FIX-1`
**Current status:** `PRODUCTION ACCEPTED / P0 INCIDENT CLOSED`
**Production repair/rebuild:** `COMPLETED / PASS`
**Production Projection worker:** `ACTIVE + ENABLED`
**Prepared / closure updated:** 2026-09-11

> Historical HOLD / containment statements below are retained as dated lifecycle
> evidence. They are not current production status.

---

# 0. Current authoritative status

```text
TASK-TRAFFIC-PROJECTION-LIFECYCLE-CONSISTENCY-01
= CLOSED / PRODUCTION ACCEPTANCE PASS

PR #111 / FIX-1
= MERGED + DEPLOYED + VERIFIED

PRODUCTION ARTIFACT
= 7472d67274ea5aaea2a20df6b613b78d5bb70f42

PRODUCTION TREE
= 3950df6d400049ed16a823032c6740396cd61137

PROJECTION HEALTH
= HEALTHY

HISTORICAL TRAFFIC READ SURFACE
= RESTORED

traffic-projection.service
= ACTIVE + ENABLED

P0 INCIDENT
= CLOSED
```

The current state supersedes the earlier **current-status** wording:

```text
production repair/rebuild = HOLD
traffic-projection.service = STOPPED + DISABLED / CONTAINED
```

Those statements remain valid only for the historical containment stage before
candidate acceptance and production recovery.

---

# 1. Incident classification — unchanged

Canonical root-cause classification remains:

```text
RETENTION CLEANUP / FROZEN RECONCILE WINDOW RACE
```

Permanent authority:

```text
Observation = authoritative source.
Traffic Projection = derived / rebuildable read model.
```

The P0 failure mechanism was:

```text
frozen reconcile sweep fixes proof window
        ↓
wall clock / normal retention cutoff advances
        ↓
cleanup deletes Projection rows still inside frozen proof window
        ↓
source/projection identity diverges
        ↓
Site status=diverged
last_error_category=source_identity
        ↓
Historical Projection reads fail closed
```

The fix protects the proof window. It does **not** weaken identity proof.

Divergence remains fail-closed. An untrusted Projection must not be served as
healthy.

Production repair remains constrained to the accepted repair model. Arbitrary
SQL mutation, manual health reset or Observation mutation is forbidden.

---

# 2. Historical incident / containment stage

Production Site:

```text
site_id=6a64f17630da7c70d232187a
projection_version=historical_traffic_projection.v1
```

Before repair:

```text
status=diverged
last_error_category=source_identity
projection_revision=88955

traffic-projection.service=inactive
traffic-projection.service=disabled
writer lock=free
```

Observation continued authoritative acquisition and `captive-portal.service`
remained active.

Projection DB:

```text
/opt/CaptivePortal/data/traffic_projection.sqlite3
```

Observation DB:

```text
/opt/CaptivePortal/data/observations.sqlite3
```

Containment purpose:

```text
stop the known-vulnerable Projection writer
preserve incident evidence
prevent unaccepted repair/rebuild
keep Observation untouched
keep Captive Portal operational
```

Historical milestone at this stage:

```text
IMPLEMENTATION-READY FINAL-R5
production repair/rebuild=HOLD
Projection writer=STOPPED + DISABLED / CONTAINED
```

This stage is retained as chronology, not current status.

---

# 3. FINAL-R5 + FIX-1 accepted implementation

Accepted implementation adds / hardens:

```text
durable cleanup fence
durable repair continuation
health observer / structured telemetry
immutable loaded artifact identity
bounded shutdown
restart/interruption-safe persisted repair continuation
```

Critical durable repair rule:

```text
version active
+
status=rebuilding
+
last_error_category=repair_delete
→ active durable repair phase
```

The normal Projection worker recognizes active persisted repair lineage and
continues `repair_site()` instead of falling into the ordinary incremental path.

The same lifecycle also covers an active durable reconcile sweep within
`rebuilding`.

No Projection schema migration was required for the retention fence.

---

# 4. Git / acceptance identity

Implementation baseline before PR:

```text
ff39fe888c53361a7c65a034eaddb0ce92cc4a12
```

Accepted PR head:

```text
a0dc02d5ae0ff16c250cf46a7e7a610c24e6f433
```

Accepted tree:

```text
3950df6d400049ed16a823032c6740396cd61137
```

PR:

```text
#111
```

FIX-1 patch SHA256:

```text
53f76302494edb4ab135cb416b957a392beb55b2469c5bd29cc1823ae9be52a5
```

Owner merged PR #111.

Production merge artifact:

```text
7472d67274ea5aaea2a20df6b613b78d5bb70f42
```

Production merge tree:

```text
3950df6d400049ed16a823032c6740396cd61137
```

Therefore:

```text
accepted tree == production merge tree
```

The exact artifact that passed acceptance is the artifact deployed to
production.

PR acceptance evidence:

```text
Source Review=PASS
Windows Central Full V6=PASS
strict regressions=0
Linux targeted=132 PASS
Linux full=3154 PASS, 1 SKIP
3 baseline/environment failures reproduced identically on clean base
candidate-specific regressions=0
```

---

# 5. Forensic preflight before mutation

Before any production repair mutation, the writer was contained and a forensic
backup was created outside the repository:

```text
/home/admin/captivportal-recovery/projection-incident-20260911-112820
```

The recovery evidence preserved:

```text
SQLite-consistent Projection backup
raw DB/WAL/SHM
writer-lock snapshot
manifest
Site-state snapshot
SHA256 evidence
```

This is an accepted recovery-workflow requirement for this real incident:

```text
contain writer
→ prove lock state
→ preserve forensic evidence / consistent backup
→ only then mutate derived Projection through canonical repair
```

Observation was not mutated.

---

# 6. Production fixed-artifact deployment

Production checkout:

```text
/opt/CaptivePortal
```

Exact deployed artifact:

```text
HEAD=7472d67274ea5aaea2a20df6b613b78d5bb70f42
tree=3950df6d400049ed16a823032c6740396cd61137
```

Post-deploy proof:

```text
repository clean=PASS
exact HEAD/tree=PASS
compileall=PASS
import smoke=PASS
loaded artifact identity=PASS
captive-portal.service=active
```

During this validation:

```text
traffic-projection.service=inactive
traffic-projection.service=disabled
```

The Projection worker intentionally remained contained until repair entry.

---

# 7. Repair CLI environment lesson

The first `repair-site` attempt from an ordinary interactive shell was rejected:

```text
TRAFFIC_PROJECTION_ENABLED must be true
```

Required classification:

```text
fail-closed configuration behavior=CORRECT
repair mutation started=NO
Projection DB changed=NO
```

Production Projection runtime environment is defined by systemd:

```text
unit=/etc/systemd/system/traffic-projection.service
EnvironmentFile=/etc/default/captive-portal
User=admin
Group=admin
WorkingDirectory=/opt/CaptivePortal
ExecStart=/usr/bin/python3 -m app.traffic_projection.cli run
```

Operational invariant learned from the recovery:

```text
Production Projection CLI/repair must not be executed from an arbitrary shell
environment when the canonical worker environment is supplied by systemd
EnvironmentFile.
```

Controlled repair must reproduce the canonical User/Group/WorkingDirectory and
EnvironmentFile context without exposing secrets.

---

# 8. First controlled durable repair quantum

The first real production repair quantum ran through a transient systemd unit
using the canonical Projection environment.

Result:

```text
REPAIR_RC=0

projection_revision:
88955 → 88956

status=rebuilding
last_error_category=repair_delete
```

The repair model cleared obsolete proof/checkpoint state as intended:

```text
old fast_checkpoint cleared
old reconcile sweep/cursor cleared
old projection head cleared
old proof fields cleared
```

After the quantum:

```text
PRAGMA quick_check=ok
writer lock=FREE
```

This was not yet full recovery. It was the accepted durable repair entry.

---

# 9. Durable continuation through the normal worker

After the first quantum, the permanent Projection worker was started but not yet
enabled:

```text
traffic-projection.service=active
traffic-projection.service=disabled
```

Loaded artifact telemetry proved:

```text
artifact_sha=7472d67274ea5aaea2a20df6b613b78d5bb70f42
artifact_tree=3950df6d400049ed16a823032c6740396cd61137
service_name=traffic-projection.service
```

The worker discovered the persisted:

```text
status=rebuilding
last_error_category=repair_delete
```

and automatically continued the durable repair through the normal worker
lifecycle.

Production therefore proved:

```text
repair continuation after restart/persisted rebuilding state=PASS
```

No repeated manual repair-site loop was required.

---

# 10. Delete phase proof

Initial Projection-cycle count:

```text
34342
```

Observed bounded progress included:

```text
34342
→ 32642
→ 30942
→ 27742
→ ...
```

Delete work occurred in bounded chunks of 100 cycles and continued rather than
stalling.

Result:

```text
durable delete phase=PASS
bounded repair continuation=PASS
```

---

# 11. Automatic rebuild / reconcile / deep audit

After delete completion, the same worker automatically progressed to rebuild and
reconcile from authoritative Observation.

Recovery path proved:

```text
Observation authoritative data
→ Projection rebuild
→ full reconcile
→ source/projection identity proof
→ deep audit
→ healthy
```

No arbitrary Projection-row insert and no Observation mutation were used.

---

# 12. Final production acceptance state

Final Site state:

```text
projection_revision=123634
status=healthy
last_error_category=NULL

projection_head_utc=2026-09-11T13:18:00.739Z
source_head_utc=2026-09-11T13:18:00.739Z

last_incremental_progress_at=2026-09-11T13:18:01.515Z
last_full_reconcile_completed_at=2026-09-11T13:17:46.393Z
last_full_reconcile_source_head_utc=2026-09-11T13:16:11.360Z
last_deep_audit_at=2026-09-11T13:17:46.393Z

backlog_cycle_count=0

available_from_utc=2026-08-13T17:37:01.104Z
available_through_utc=2026-09-11T13:17:30.622Z
```

Head coherence:

```text
projection_head_utc == source_head_utc
PASS
```

Projection version:

```text
historical_traffic_projection.v1
status=active
```

DB integrity:

```text
PRAGMA user_version=1
PRAGMA quick_check=ok
```

Final product health:

```text
healthy
```

---

# 13. Service / autostart final state

Final services:

```text
captive-portal.service=active
traffic-projection.service=active
```

After acceptance:

```text
systemctl enable traffic-projection.service
```

Final worker state:

```text
traffic-projection.service=active + enabled
```

The Projection worker is therefore restored to normal production operation and
will start after reboot.

---

# 14. End-to-end Historical Traffic proof

After recovery, Owner manually opened the production Admin Web and verified the
previously unavailable Historical Traffic panels rendered normally again.

This is production proof of the full path:

```text
Observation
→ Traffic Projection
→ HistoricalTrafficReadService
→ Admin Traffic read surface
→ Web UI panels
```

Historical Traffic read surface:

```text
RESTORED / PASS
```

This acceptance does not alter Historical Traffic business formulas.

---

# 15. Final incident verdict

```text
PR #111 / FIX-1=DEPLOYED
Production artifact=VERIFIED

Durable repair=PASS
Persisted repair continuation=PASS
Delete phase=PASS
Rebuild=PASS
Full reconcile=PASS
Deep audit=PASS

Projection health=HEALTHY
Source/projection head coherence=PASS
Backlog=0
DB integrity=PASS

Historical Web panels=PASS
Captive Portal=ACTIVE

Projection worker=ACTIVE
Projection autostart=ENABLED

P0 INCIDENT=CLOSED
PRODUCTION ACCEPTANCE=PASS
```

Current-status wording is therefore:

```text
FIX-1 accepted, merged and deployed to production.
Production recovery completed.
Projection healthy.
Historical Traffic read surface restored.
Worker active + enabled.
P0 incident closed.
```

---

# 16. Non-blocking post-recovery observation

After recovery, normal telemetry showed a short transition:

```text
healthy → stale → healthy
```

during an active reconcile sweep.

Observed context:

```text
error_category=NULL
worker remained running
Projection continued processing
reconcile completed
fresh last_full_reconcile_completed_at was written afterward
final state=healthy
```

Current classification:

```text
OBSERVATION — transient healthy/stale/healthy during active reconcile sweep
```

It is **not** currently classified as:

```text
new incident
TASK regression
production blocker
```

Monitor this behavior. If transient `stale` becomes frequent or user-visible
through the Historical read gate/Web UI, analyze health-observer/read-gate
semantics as a separate future issue.

No new architecture decision is made by recording this observation.

---

# 17. Permanent recovery invariants retained

```text
Observation remains authoritative.
Projection remains derived/rebuildable.
Divergence remains fail-closed.
Do not weaken source/projection proof to restore availability.
Do not mutate Observation to repair Projection.
Do not manually mark diverged Projection healthy.
Do not perform arbitrary SQL repair outside the canonical repair lifecycle.
Forensic capture/consistent backup precedes production repair mutation.
Exact loaded artifact identity is part of production proof.
```

---

# 18. Chronology summary

```text
P0 detected
→ root cause classified:
  RETENTION CLEANUP / FROZEN RECONCILE WINDOW RACE

→ containment:
  writer STOPPED + DISABLED
  repair/rebuild HOLD
  Observation continues

→ Architecture FINAL-R1
→ IMPLEMENTATION-READY FINAL-R5

→ FINAL-R5 + FIX-1 implemented
→ Owner + Tech Lead acceptance PASS
→ PR #111 merged

→ forensic preflight + consistent backup
→ exact fixed artifact deployed

→ arbitrary-shell repair rejected fail-closed
→ repair re-run under canonical systemd runtime context

→ first durable repair quantum:
  rebuilding + repair_delete

→ normal worker resumed persisted repair
→ bounded delete
→ rebuild
→ full reconcile
→ deep audit
→ healthy / backlog 0

→ Historical Web panels restored
→ worker enabled for autostart

→ P0 incident CLOSED
```
