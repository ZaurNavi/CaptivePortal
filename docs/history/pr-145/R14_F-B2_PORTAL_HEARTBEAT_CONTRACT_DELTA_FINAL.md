# DEVICE-FINGERPRINT-03A-R2 / F-B2
## PORTAL HEARTBEAT CONTRACT DELTA / FINAL

**Role:** ARCHITECT2  
**Disposition:** FROZEN-CONTRACT CHANGE CLOSURE  
**Scope:** R14 / F-B2 portal idle heartbeat only  
**Architecture revision:** R14 remains the owning architecture revision  
**Task-04:** HOLD  
**Coder task:** NOT ISSUED BY THIS DOCUMENT  

---

# 1. Change-request disposition

TechLead12 frozen-contract request is **ACCEPTED** as a bounded formal architecture delta.

This delta changes only the portal source-health emitter semantics required to satisfy the already-frozen R14 requirement:

```text
portal idle heartbeat independent of visitors
```

It does NOT authorize or change:

```text
Task boundaries
Task-01 evidence storage
Task-04 classification storage
network-sensor emitter semantics
network-sensor binding epochs
evidence payload schemas
portal evidence payload semantics
Authorization behavior
classification semantics
SourceEvaluability coverage classes
covered_delayed removal
Task-01 delayed-event semantics
retention semantics except normal downstream F-B3 recomputation
```

All unrelated R14 contracts remain frozen.

---

# 2. Accepted F-B1 baseline

The following F-B1 results are accepted inputs and are not rewritten:

```text
EvidenceSourceBindingTimeline:v1:sha256:
820c5d43aca36b2284fe43cf4bbc4ce380300901c7adf9a0808353d28004a357

BindingClockPolicy:v1:sha256:
4d825299e26819129ab5c357f12e7c5a54fa06999df02cf1cc87ccb1ae45ca66

F-B1 authority start =
2026-09-18T10:43:29.014Z

clock offset =
0 ms

cutover guard =
0 sec
```

These artifacts describe the accepted pre-change timeline/clock state.

The portal emitter semantic change defined here MUST create a later portal binding epoch and therefore a new immutable `EvidenceSourceBindingTimeline` ArtifactContent. The accepted old timeline remains immutable/auditable.

---

# 3. Existing portal emitter disposition

The currently admitted historical portal emitter contract is:

```text
heartbeat mode =
EVENT_DRIVEN

nominal_interval_ms =
null

same_state_heartbeat_required =
false
```

That contract remains valid for the historical portal binding epoch(s) that reference it.

It MUST NOT be mutated, reinterpreted, rehashed, or silently replaced.

Because its heartbeat semantics change, the replacement portal implementation requires:

```text
new immutable SourceHealthEmitterContract
+
new portal binding epoch
```

The old epoch remains authoritative for its original interval.

---

# 4. Replacement portal heartbeat mode

The replacement V1 portal heartbeat mode is frozen as:

```text
mode =
PERIODIC

nominal_interval_ms =
60000

same_state_heartbeat_required =
true
```

Therefore the portal producer MUST attempt a visitor-independent source-health heartbeat once per:

```text
60,000 ms
=
60 seconds
```

while the portal source-health emitter is enabled and the portal producer process is running.

The periodic heartbeat MUST NOT depend on:

```text
visitor request arrival
portal page load
successful captive authorization
portal_headers evidence production
portal_headers evidence delivery
MAC presence
IP presence
UA presence
Client Hints presence
```

No synthetic visitor request or browser traffic may be generated to create the heartbeat.

---

# 5. Exact heartbeat event semantics

The periodic heartbeat is a normal Task-01 source-health event for:

```text
source_kind =
portal_headers
```

using the producer/site/capture-source authority of the active portal binding epoch.

A healthy periodic heartbeat has:

```text
status =
available

reason_code =
null
```

It carries no:

```text
MAC
IP
UA
Client Hints
device identity
classification result
authorization state
```

A successful visitor evidence delivery MUST NOT substitute for the required periodic same-state heartbeat.

Additional `available` events caused by implementation-local recovery handling are permitted only if already valid under the admitted emitter/status contract, but they do not reset or remove the obligation to produce periodic same-state heartbeats.

---

# 6. Delivery failure semantics remain conservative

The existing portal delivery failure reason remains:

```text
reason_code =
ingest_delivery_unavailable

status =
unavailable

failure domain =
DELIVERY
```

No new reason code is introduced by this architecture delta.

If the portal producer cannot deliver to Task-01 over the same failed transport, central Task-01 cannot receive a live failure event merely because the producer detected the failure.

Therefore the frozen R14 rule remains:

```text
last compatible heartbeat ages out
→ coverage becomes unknown
```

A later recovery does NOT prove the missing interval complete.

Historical health backfill remains subject to the existing Task-01 delayed-event contract.

---

# 7. SourceHealthEmitterContract delta

The replacement portal `SourceHealthEmitterContract` MUST preserve all already-admitted non-heartbeat portal semantics unless implementation proof requires a separately reviewed change.

Its heartbeat subobject is exactly:

```text
heartbeat_behavior_cadence_semantics = {
    "mode": "PERIODIC",
    "nominal_interval_ms": 60000,
    "same_state_heartbeat_required": true
}
```

The contract MUST have a new:

```text
producer_service_implementation_identity
```

that identifies the exact heartbeat-capable implementation candidate.

The existing historical emitter ArtifactContent remains immutable.

The replacement emitter ArtifactContent ID/digest is produced only after exact F-B0 delta admission; this architecture document does not pre-invent that digest.

---

# 8. Exact SourceHealthPolicy freshness contract

For the replacement portal PERIODIC emitter, the `SourceHealthPolicy` family rule is frozen as:

```text
expected_heartbeat.mode =
PERIODIC

expected_heartbeat.nominal_interval_ms =
60000

freshness.freshness_timeout_ms =
180000

freshness.when_timeout_exceeded =
unknown
```

Relationship:

```text
freshness_timeout_ms
=
3 × nominal_interval_ms
```

Thus:

```text
nominal heartbeat cadence =
60 s

freshness timeout =
180 s
```

This permits bounded scheduling/delivery jitter and missed heartbeat opportunities without changing the conservative failure model.

Exact age rule:

```text
age_ms =
evaluation_time_utc
-
latest compatible portal source-health event observed_at
```

For the active binding epoch:

```text
0 <= age_ms <= 180000
→ event remains fresh for policy interpretation

age_ms > 180000
→ coverage = unknown
```

Negative age remains invalid under the existing timestamp/clock contracts.

A fresh `available / reason_code=null` heartbeat maps to the already-frozen `covered_available` semantics.

An explicit fresh `unavailable / ingest_delivery_unavailable` event maps through the existing DELIVERY mapping; this delta does not change the conservative coverage-class taxonomy.

---

# 9. Historical policy interpretation

The next admitted `SourceHealthPolicy` MUST retain enough emitter-specific rules to interpret both:

```text
OLD portal binding epoch
→ historical EVENT_DRIVEN portal SourceHealthEmitterContract

NEW portal binding epoch
→ replacement PERIODIC portal SourceHealthEmitterContract
```

The old epoch is NOT retroactively treated as PERIODIC.

Silence in the old EVENT_DRIVEN epoch is interpreted under the old contract and may remain `unknown`.

The new 60 s / 180 s heartbeat/freshness rule applies only to binding epochs that explicitly reference the new PERIODIC emitter contract.

Existing network-sensor rules remain byte/semantically unchanged.

---

# 10. Portal binding cutover contract

A new portal emitter semantic version requires a new portal binding epoch under frozen F-B1 rules.

The controlled transition is exactly:

```text
1. build heartbeat-capable portal implementation candidate

2. execute bounded F-B0 delta proof

3. admit new immutable portal SourceHealthEmitterContract

4. select controlled cutover timestamp T

5. end old portal binding epoch at T

6. start new portal binding epoch at T
   referencing the NEW SourceHealthEmitterContract

7. activate the heartbeat-capable portal implementation for that epoch

8. obtain new-period portal heartbeat evidence

9. construct/validate new immutable EvidenceSourceBindingTimeline
   containing:
       old portal epoch unchanged except its finite end T
       new portal epoch beginning at T
       unchanged network-sensor epochs

10. execute F-B2 controlled portal idle/failure/recovery proofs
```

No historical portal source-health row is reassigned from the old epoch to the new epoch.

No network binding epoch is changed by this portal-only cutover.

---

# 11. First-heartbeat / cutover behavior

Health state does not cross binding epochs.

Therefore the new portal epoch MUST NOT inherit the final `available` state of the historical EVENT_DRIVEN epoch.

For:

```text
[T, first compatible heartbeat of new epoch)
```

central coverage is conservatively:

```text
unknown
```

unless an explicit compatible source-health event for the new epoch exists.

The heartbeat-capable implementation MUST attempt its first periodic heartbeat no later than:

```text
T + 60000 ms
```

F-B2 controlled proof MUST demonstrate a successful new-epoch `available` heartbeat without any visitor traffic.

No artificial backdating of that heartbeat to `T` is permitted.

---

# 12. Required F-B0 delta execution

A bounded F-B0 delta execution **IS REQUIRED**.

This is NOT a new architecture gate number and does not reopen unrelated F-B0 contracts.

The F-B0 delta consumes:

```text
exact heartbeat-capable portal implementation candidate

existing historical portal SourceHealthEmitterContract

replacement portal SourceHealthEmitterContract candidate

periodic heartbeat fixtures

delivery failure/recovery fixtures

Task-01 delayed-event behavior
```

PASS requires:

```text
new implementation identity exact

mode = PERIODIC

nominal_interval_ms = 60000

same_state_heartbeat_required = true

available heartbeat independent of visitors

existing ingest_delivery_unavailable meaning unchanged

no new lossless-completeness claim

no Authorization coupling
```

Canonical output:

```text
new immutable portal SourceHealthEmitterContract
```

The old contract remains retained.

---

# 13. Required F-B1 delta execution

A bounded F-B1 delta/cutover execution **IS REQUIRED** because frozen R14 says:

```text
new emitter semantics create new epoch
```

This is NOT a new architecture gate number and does not reopen the already accepted clock methodology or network bindings.

The F-B1 delta reuses the accepted `BindingClockPolicy` unless new measurement proves its assumptions invalid.

Given the accepted current proof:

```text
clock offset = 0 ms
cutover guard = 0 sec
```

no architecture-driven change to those values is required merely because portal heartbeat semantics change.

PASS requires:

```text
one exact controlled cutover timestamp T

old portal epoch ends at T

new portal epoch starts at T

new epoch references new portal SourceHealthEmitterContract

no overlapping portal authority outside frozen cutover rules

no rewrite of historical old epoch

network-sensor epochs unchanged

new EvidenceSourceBindingTimeline ArtifactContent deterministic
```

Canonical output:

```text
updated immutable EvidenceSourceBindingTimeline
```

`BindingClockPolicy` may be referenced unchanged when the bounded cutover proof confirms its existing assumptions remain valid.

---

# 14. F-B2 controlled proof requirements

After F-B0-delta and F-B1-delta PASS, F-B2 MUST prove the new portal behavior.

Minimum controlled cases:

## 14.1 Idle healthy portal

Conditions:

```text
no visitor traffic
no portal_headers evidence production
portal process healthy
Task-01 transport healthy
```

Proof window:

```text
>= 240000 ms
```

PASS:

```text
at least four successive compatible periodic heartbeat events
with no visitor dependency

no intended heartbeat interval > 60000 ms
```

The retained trace MUST make heartbeat timestamps and absence of visitor evidence explicit.

## 14.2 Freshness boundary

Using the admitted policy:

```text
latest available heartbeat age <= 180000 ms
→ fresh

latest compatible heartbeat age > 180000 ms
→ unknown
```

Boundary fixtures MUST include exactly:

```text
180000 ms
180001 ms
```

## 14.3 Portal transport failure

When heartbeat delivery cannot reach Task-01:

```text
no claim that central saw live unavailable

existing fresh state ages out

after >180000 ms without compatible event
→ unknown
```

## 14.4 Recovery

After transport recovery:

```text
new current heartbeat may restore current fresh available state

historical backfill only under Task-01 delayed-event rules

recovery MUST NOT mark the missing interval complete

NO covered_delayed
```

## 14.5 Historical epoch isolation

Replay before T MUST use:

```text
old EVENT_DRIVEN emitter contract
```

Replay at/after T MUST use:

```text
new PERIODIC emitter contract
```

No health state crosses T merely because producer_id/capture_source_id remained the same.

---

# 15. SourceHealthPolicy artifact requirements

F-B2 must materialize a new immutable `SourceHealthPolicy` because the accepted emitter set/family rules change.

The policy MUST include:

```text
existing network-sensor emitter rules unchanged

historical portal EVENT_DRIVEN emitter rule retained for old epoch interpretation

new portal PERIODIC emitter rule:
    nominal_interval_ms = 60000
    freshness_timeout_ms = 180000
    timeout -> unknown
```

No `covered_delayed` class is introduced.

No source gets a lossless completion guarantee.

---

# 16. F-B3 consequence

Because F-B2 produces a new `SourceHealthPolicy`, normal frozen gate flow requires:

```text
F-B3 health-retention-margin proof
```

to run against the new policy before Foundation admission/update activation.

This delta does NOT pre-invent a new `health_anchor_margin_seconds`.

F-B3 derives/proves the required margin from the admitted policy and existing Task-01 health retention capability.

If the required margin is not supported by already-preserved Task-01 history:

```text
policy activation BLOCKED
```

until sufficient history exists, exactly as frozen R14 already requires.

---

# 17. Required transition sequence — FINAL

The exact allowed transition sequence is:

```text
heartbeat-capable portal implementation candidate

→ bounded F-B0 delta:
     new portal SourceHealthEmitterContract admission

→ bounded F-B1 delta:
     controlled portal binding cutover
     updated EvidenceSourceBindingTimeline

→ F-B2:
     idle heartbeat / timeout / failure / recovery / historical-isolation proofs
     new SourceHealthPolicy

→ F-B3:
     health-retention-margin compatibility proof

→ later Foundation runtime-profile re-admission/activation
  only through the already-frozen R14 update lifecycle
```

No Coder task for F-B2 implementation should assume the new contract is admitted until TechLead12 accepts this architecture delta.

---

# 18. Additional gate disposition

Answer to the explicit change-request question:

```text
NEW F-B0/F-B1 GATE NUMBER =
NO

BOUNDED F-B0 DELTA EXECUTION =
YES / REQUIRED

BOUNDED F-B1 DELTA CUTOVER EXECUTION =
YES / REQUIRED

F-B2 =
REQUIRED after both delta executions

F-B3 =
REQUIRED after the new SourceHealthPolicy is produced
```

No other Foundation gate is reopened by this architecture delta unless the bounded proofs discover a separate frozen-contract incompatibility.

---

# 19. Frozen-contract statement

Everything in R14 not explicitly changed by this document remains frozen.

Specifically unchanged:

```text
network sensor PERIODIC 300000 ms emitter semantics

existing network-sensor SourceHealthEmitterContract(s)

existing network binding epochs

coverage-class enum

transport-failure truth

NO covered_delayed

Task-01 delayed-event handling

SourceEvaluability semantic boundary

classification semantics

Task-04 scope

Authorization isolation
```

This document does not authorize implementation beyond the bounded heartbeat work required to satisfy F-B0/F-B1 delta proofs and F-B2.

---

# 20. FINAL ARCHITECT DECISION

```text
PORTAL HEARTBEAT MODE =
PERIODIC

PORTAL HEARTBEAT NOMINAL INTERVAL =
60000 ms

PORTAL SAME-STATE HEARTBEAT REQUIRED =
true

PORTAL FRESHNESS TIMEOUT =
180000 ms

TIMEOUT COVERAGE =
unknown

OLD PORTAL EVENT_DRIVEN CONTRACT =
RETAINED / HISTORICAL ONLY

NEW PORTAL EMITTER CONTRACT =
REQUIRED

NEW PORTAL BINDING EPOCH =
REQUIRED

HISTORICAL EPOCH REWRITE =
FORBIDDEN

NETWORK EMITTER/BINDING CHANGE =
NONE

BOUNDED F-B0 DELTA =
REQUIRED

BOUNDED F-B1 DELTA =
REQUIRED

F-B2 =
PROCEED ONLY AFTER BOTH DELTAS PASS

F-B3 =
REQUIRED AFTER NEW SourceHealthPolicy
```

---

# 21. Repository verification note

At Architect2 review time the connected repository `main` was independently observed at:

```text
main =
00a86d32cd8979334d864dd162acaebdfe6ed73c

tree =
1301b0ae7f4f52f23bc79760cb3be4c8c4e62318
```

That state contains the admitted historical portal emitter contract with:

```text
EVENT_DRIVEN
nominal_interval_ms = null
same_state_heartbeat_required = false
```

This repository observation is evidence for the blocker and does not alter the accepted F-B1 artifact identities listed in §2.
