# Deferred Architecture Request — Historical Traffic Projection Maintenance / Reindex

Status: DEFERRED ARCHITECTURE REQUEST / REMINDER
Updated: 2026-09-06

Working future name:

```text
TASK-TRAFFIC-PROJECTION-MAINTENANCE-UI-01
```

The name is **not canonical** and may be changed by Architect.

## 1. Do not implement now

This request must not expand the current:

```text
TASK-TRAFFIC-PROJECTION-01 — Historical Traffic Materialized Projection Foundation
```

First complete and accept the current Projection Foundation, including its real
implemented contracts for correctness, parity, rebuild, catch-up, performance,
storage/WAL, concurrency, source immutability and production-compatible
acceptance.

After that, Owner + Tech Lead must re-check this deferred request against the
actual accepted implementation. Only then is it handed to Lab/System Architect
for a separate canonical architecture TASK.

## 2. Current architectural basis

At current repository baseline, Historical Traffic Projection is a
derived/disposable read-model over authoritative Observation evidence.

Current code identifies:

```text
projection version = historical_traffic_projection.v1
source schema version = 1
default derived DB = /opt/CaptivePortal/data/traffic_projection.sqlite3
```

A projection DB is not an authoritative source.

The normal worker model is incremental processing/reconciliation of new
Observation cycles.

A full rebuild over the retention horizon is a rare explicit maintenance
operation, not an invisible normal browser/background side effect.

## 3. Future goal

Design an operator-visible Projection Maintenance / Reindex workflow that allows
an administrator to:

1. understand projection health/state;
2. see when intervention is required;
3. explicitly request an allowed maintenance action;
4. observe rebuild/repair progress;
5. understand validation/result;
6. activate a ready projection under the approved lifecycle.

The HTTP/Admin browser request must not perform the long rebuild itself.

Conceptual flow:

```text
Admin Console
→ Projection status/diagnostics
→ explicit Rebuild/Repair request
→ maintenance execution layer / worker
→ observable progress
→ building/rebuilding
→ validation
→ ready
→ explicit approved activation
→ active
```

## 4. Architecture work to define later

Architect must define, at minimum:

- scope/non-scope;
- lifecycle/state machine;
- full rebuild semantics;
- Site repair;
- projection-version rebuild;
- failure/interruption/restart/resume;
- whether cancellation is safe;
- command/action model;
- progress model;
- Admin API;
- authorization/confirmation;
- single-writer/concurrency ownership;
- audit trail;
- sanitized errors;
- operator-visible status/health;
- side-by-side rebuild;
- activation semantics;
- telemetry;
- Admin UI information architecture;
- acceptance criteria;
- migration/production activation plan.

## 5. Health / lifecycle concepts to reconcile

Future design must reconcile operational health concepts such as:

```text
healthy
catching_up
stale
unavailable
rebuilding
diverged
```

with projection-version lifecycle concepts such as:

```text
building
ready
active
retired
failed
```

Do not assume these are the same state machine.

## 6. Progress contract

The future progress model must be deterministic, durable across worker restart,
bounded-transaction compatible and inexpensive for UI polling.

A possible candidate concept is:

```text
processed captured source cycles / captured total source cycles
```

but this is not approved until Architect validates it.

The design must avoid an expensive full source COUNT on every UI poll and avoid
new load on authoritative Observation storage.

## 7. Operator-safe actions

Potential actions to evaluate, not pre-approve:

- Rebuild Projection;
- Repair Site;
- Activate ready version;
- Cleanup;
- Mark Failed;
- Cancel/Abort only if safe.

Internal CLI capabilities are not automatically Admin UI buttons.

## 8. Safety / authorization

Maintenance actions are privileged administrative operations.

Future design must address:
- required authorization;
- explicit confirmation for expensive/destructive actions;
- duplicate-launch protection;
- single-writer ownership;
- audit history;
- browser-session loss;
- application/worker restart;
- accidental production activation prevention.

## 9. Side-by-side rebuild invariant

If a healthy active projection exists, build a replacement beside it.

Preferred lifecycle:

```text
active old version keeps serving reads
→ build new version
→ validate
→ ready
→ activate
→ old version can later retire
```

Do not destroy healthy active projection simply to build a replacement.

## 10. No hidden raw fallback

If the accepted Projection Foundation continues to prohibit raw fallback,
maintenance must preserve that rule.

If no usable active projection exists during rebuild/repair, Historical Traffic
may report controlled unavailable/maintenance state instead of silently
performing expensive raw reconstruction.

## 11. Automatic vs explicit work

Automatic/background work may include:
- source-head polling;
- incremental catch-up;
- periodic reconciliation;
- bounded cleanup;
- health maintenance.

Explicit maintenance may include:
- full rebuild;
- repair;
- incompatible-version rebuild;
- operator-controlled activation;
- other recovery operations.

Opening the Admin page must never start a full rebuild.

## 12. Hard boundaries

The future maintenance workflow must not:
- mutate authoritative Observation evidence;
- write to Observation DB;
- perform Omada acquisition;
- change Historical Traffic semantic meaning;
- tie rebuild lifetime to one browser HTTP request;
- auto-activate a new version unless the accepted lifecycle explicitly allows it;
- violate single-writer ownership;
- turn derived projection into an authoritative store.

## 13. Re-validation trigger

Re-open this document only after the current Projection Foundation has reached
full accepted closure.

At that point:

```text
Owner + Tech Lead
→ compare this reminder with actual implementation
→ amend/remove stale assumptions
→ hand to Architect
→ Architect produces separate canonical TASK/ADR/PLAN
```

Until then, this document is a reminder only, not implementation authority.
