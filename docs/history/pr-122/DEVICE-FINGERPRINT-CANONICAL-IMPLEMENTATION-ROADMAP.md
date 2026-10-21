# DEVICE-FINGERPRINT — CANONICAL IMPLEMENTATION ROADMAP

**Project:** CaptivPortal / Device Fingerprint  
**Document role:** canonical implementation-order and stage-boundary contract  
**Owner:** Project Owner  
**Execution roles:** Architect → Tech Lead → Coder  
**Status:** CANONICAL WORKING ROADMAP  
**Date:** 2026-09-16

---

## 1. PURPOSE

This document exists to prevent the Device Fingerprint work from again collapsing multiple foundation stages and Task-04 into one monolithic implementation/review task.

The project MUST proceed sequentially:

```text
TASK-DEVICE-FINGERPRINT-01
        ↓
TASK-DEVICE-FINGERPRINT-02
        ↓
TASK-DEVICE-FINGERPRINT-03
        ↓
TASK-DEVICE-FINGERPRINT-03A
        ↓
FOUNDATION ADMISSION
        ↓
TASK-DEVICE-FINGERPRINT-04
```

The governing rule is:

> For each already-existing stage, compare CURRENT MAIN against the exact requirements Task-04 places on that stage, implement only the missing delta, pass the stage gate, freeze the stage, and only then move forward.

No later stage may be used as justification to reopen an already accepted earlier stage unless a concrete blocking incompatibility is proven.

---

# 2. CURRENT REPOSITORY BASELINE

Repository:

```text
ZaurNavi/CaptivePortal
```

Verified current `main` baseline at the time this roadmap was created:

```text
HEAD =
d37d3ec126ccd512fe835af0db21221e2f83d565
```

Relevant merged history already present on `main`:

```text
TASK-DEVICE-FINGERPRINT-01
Device Fingerprint Evidence Foundation

TASK-DEVICE-FINGERPRINT-02
Core Packet Sensor + Network Evidence

TASK-DEVICE-FINGERPRINT-03
Portal UA / Client Hints Evidence

TASK-DEVICE-FINGERPRINT-03A
Multi-Platform Labeled Evidence Matrix

TASK-DEVICE-FINGERPRINT-02 follow-up fixes
- compact EVE timestamp offsets
- raw AF_PACKET capture protocol
- AF_PACKET interface bind protocol
```

Therefore this roadmap does NOT restart the project.

Every stage below is:

```text
CURRENT MAIN
    ↓
MISSING DELTA REQUIRED FOR TASK-04
    ↓
IMPLEMENT
    ↓
VERIFY
    ↓
FREEZE
```

---

# 3. NON-NEGOTIABLE EXECUTION RULES

## 3.1 One stage at a time

Do NOT ask Architect or Coder to solve:

```text
01 + 02 + 03 + 03A + 04
```

in one task.

The active stage is the ONLY implementation scope unless the Owner explicitly authorizes otherwise.

## 3.2 Stage freeze

After a stage passes its acceptance gate:

```text
STAGE = FROZEN FOR TASK-04
```

A frozen stage is not reopened because:
- another document was rewritten;
- wording was improved;
- a later stage has a nicer design idea;
- Architect wants to normalize naming;
- Coder prefers another implementation;
- a future stage could be simplified by changing old semantics.

Reopening requires a proven blocking incompatibility and explicit Tech Lead review.

## 3.3 Architect scope

For each stage Architect receives the narrow question:

```text
CURRENT MAIN
+
TASK-04 REQUIREMENTS RELEVANT TO THIS STAGE
→
WHAT EXACT DELTA IS REQUIRED?
```

Architect must NOT redesign unrelated frozen stages.

## 3.4 Tech Lead scope

Tech Lead must:
- verify the actual repository `main`;
- compare current implementation against the current stage target;
- distinguish existing functionality from missing delta;
- identify exact acceptance criteria;
- identify Owner decisions before implementation;
- prevent Coder from making architecture/product-policy decisions;
- stop scope expansion;
- freeze the stage after PASS.

## 3.5 Coder scope

Coder receives:
1. the canonical roadmap / architecture reference;
2. one current-stage implementation task;
3. exact baseline;
4. exact allowed scope;
5. required tests;
6. acceptance/handoff requirements.

Coder must NOT choose between unresolved architecture or Owner-policy alternatives.

If a required decision is missing:

```text
STOP
→ return exact blocker
→ do not invent a policy
```

---

# 4. OWNER DECISION RULE

Architect and Tech Lead may make internal deterministic technical decisions when they are fully constrained by already accepted contracts.

The following MUST be explicitly surfaced to Owner before becoming project policy:
- production database migration authorization;
- disruptive or production-affecting tests;
- maintenance windows;
- retention values affecting storage/policy;
- privacy expansion;
- collection of new durable data classes;
- external cloud/runtime dependency;
- commercial/licensing acceptance;
- new external data provider;
- production activation/deployment;
- materially increased resource/storage envelope;
- optional experimental browser behavior;
- any new mandatory physical-device/sample quota;
- any requirement that materially changes project scope.

No hidden Owner decisions.

No invented mandatory numbers such as:

```text
12 devices
48 samples
multiple Apple devices
```

unless Owner explicitly accepts such a requirement for a specific future purpose.

---

# 5. STAGE 01 — TASK-DEVICE-FINGERPRINT-01 → TASK-04 READINESS

## 5.1 Existing foundation

Task-01 already provides the normalized evidence foundation, including the current evidence and source-health persistence/read boundary.

Task-01 is NOT to be rewritten from scratch.

## 5.2 Required delta category

Task-01 must be brought only to the state required for deterministic Task-04 evidence snapshots and source evaluability.

Expected readiness areas include:

```text
controlled schema migration where required
global deterministic ingest ordering / watermark capability
database generation identity / rollback-generation detection
stable snapshot read boundary
single-read-transaction snapshot capability
pagination-to-exhaustion semantics
evidence + source-health snapshot consistency
health-retention compatibility required by later SourceEvaluability
```

Exact delta must be derived from CURRENT MAIN before Coder receives the Task-01 readiness task.

## 5.3 Stage-01 gate

Task-01 readiness is accepted only after proof that:
- existing evidence semantics are preserved;
- existing IDs/payload integrity are preserved;
- migration is controlled and reversible where required;
- duplicate/conflict semantics remain correct;
- snapshot universe is deterministic;
- concurrent writes do not produce torn snapshot membership;
- rollback/generation behavior is deterministic;
- current ingestion/read behavior is not regressed.

## 5.4 Owner decisions potentially required

Before implementation or production application, explicitly ask Owner if required for:
- production DB migration;
- migration/maintenance window;
- rollback risk;
- retention increase;
- materially increased storage footprint.

## 5.5 Exit condition

After acceptance:

```text
TASK-01 =
FROZEN FOR TASK-04
```

Then and only then move to Task-02 readiness.

---

# 6. STAGE 02 — TASK-DEVICE-FINGERPRINT-02 → TASK-04 READINESS

## 6.1 Existing foundation

Task-02 already provides the network sensor path.

Current production path includes the already-merged AF_PACKET/EVE fixes.

Do NOT reopen raw capture architecture without a proven blocking reason.

## 6.2 Required delta category

Task-02 must provide the exact network evidence Task-04 needs.

Expected readiness work includes:

```text
tcp_syn/2 alongside existing tcp_syn/1
exact durable TCP/IP semantic facts required by admitted TCP fingerprint interpretation
ordered TCP option representation
malformed-but-observable behavior
privacy minimization
v1/v2 coexistence
sensor → normalizer → Task-01 end-to-end proof
exact source-health emitter semantics
TTL / RSPAN capture-placement proof
```

TLS/QUIC/JA4 evidence remains evidence.

Task-02 must NOT silently turn JA4 evidence into classification knowledge.

## 6.3 Stage-02 gate

Required proof includes:
- packet fixtures;
- malformed packet behavior;
- privacy constraints;
- v1 regression;
- v2 persistence;
- live/end-to-end capture path;
- source-health semantics;
- TTL placement validity;
- no regression of current AF_PACKET production path.

## 6.4 Owner decisions potentially required

Explicitly ask Owner before:
- disruptive live topology proof;
- production capture changes;
- adding a new durable sensitive field;
- changing passive sensor topology.

## 6.5 Exit condition

After acceptance:

```text
TASK-02 =
FROZEN FOR TASK-04
```

Then move to Task-03 readiness.

---

# 7. STAGE 03 — TASK-DEVICE-FINGERPRINT-03 → TASK-04 READINESS

## 7.1 Existing foundation

Task-03 already provides normalized portal evidence.

Raw UA / raw Client-Hints data must not become durable evidence merely for classification convenience.

Portal fingerprint collection must remain isolated from Authorization success/failure.

## 7.2 Mandatory readiness delta

Task-03 readiness must include a visitor-independent source-health mechanism so that:

```text
no visitors
```

is not confused with:

```text
portal evidence source failed
```

The health contract must support later SourceEvaluability.

## 7.3 portal_headers/2 is an Owner decision

Task-04 MUST NOT be blocked merely because high-entropy Client Hints are not admitted.

Owner must explicitly choose one of:

```text
OPTION A
DEFER portal_headers/2

Result:
portal_headers/2 = NOT_ADMITTED
Task-04 uses portal_headers/1
```

or:

```text
OPTION B
AUTHORIZE bounded Accept-CH experiment

Result:
portal_headers/2 is admitted only after
privacy + lifecycle + value proof passes
```

`Critical-CH` is not introduced merely to force evidence collection.

## 7.4 Stage-03 gate

Proof includes:
- idle health heartbeat;
- transport failure/recovery;
- portal evidence normalization regression;
- no Authorization regression;
- no raw-header durability regression;
- if Option B is chosen: bounded Accept-CH experiment gate.

## 7.5 Exit condition

After acceptance:

```text
TASK-03 =
FROZEN FOR TASK-04
```

Then move to 03A.

---

# 8. STAGE 03A — KNOWLEDGE / VALIDATION FOUNDATION

## 8.1 03A role

03A is NOT a mandatory fixed physical-device collection quota.

Existing 03A labeled-matrix tooling remains valid and retained for:
- research;
- local validation;
- regression;
- controlled campaigns.

But Task-04 readiness does NOT require arbitrary fixed counts unless Owner later authorizes a specific experiment.

## 8.2 Required 03A outcome

03A prepares the reference-knowledge and validation foundation Task-04 needs.

Expected areas:

```text
classification taxonomy
alias mapping
K1 DHCP knowledge
K2A p0f conformance/oracle
K2B TCP production knowledge
K3 normalized portal rule set
K4 IEEE assignment knowledge
source provenance
license/governance review
freshness rules where applicable
offline immutable knowledge bundle
evidence-adapter contracts
classification policy
product-validation policy
```

JA4 may remain:

```text
evidence available
+
no admitted semantic knowledge
→ NO CLAIM
```

No invented JA4 knowledge.

## 8.3 Owner decisions potentially required

Explicitly ask Owner before accepting:
- external K1/K2B/K4 source choice where alternatives exist;
- licensing/commercial restrictions;
- use of an external/cloud runtime;
- production retention policy;
- materially different storage/resource policy;
- validation ground truth requiring Owner-owned devices/data;
- any new mandatory test-device quota.

---

# 9. FOUNDATION ADMISSION

Task-04 implementation does NOT begin merely because Task-01/02/03/03A exist.

Foundation Admission occurs only after:

```text
TASK-01 readiness = PASS
TASK-02 readiness = PASS
TASK-03 readiness = PASS
TASK-03A knowledge/validation readiness = PASS
```

Foundation Admission verifies that the frozen outputs are mutually compatible.

If one Foundation component fails:

```text
return only to the failed component
```

Do NOT reopen every earlier stage.

---

# 10. STAGE 04 — TASK-DEVICE-FINGERPRINT-04

Task-04 starts only after explicit Owner authorization following Foundation Admission.

Recommended implementation decomposition:

```text
TASK-04A
Evidence snapshot materialization
+
SourceEvaluability

TASK-04B
Evidence adapters
+
OriginAssessment

TASK-04C
Pure classification/fusion
+
DimensionResult
+
global result

TASK-04D
Classification persistence
+
audit/replay
+
runtime/control-plane

TASK-04E
internal current/history read boundary

TASK-04F
controlled product validation
+
Task-04 acceptance
```

Task-04 does NOT own:

```text
identity/session integration
Device Card/Admin presentation
Authorization decisions
```

Those remain later task ownership.

---

# 11. TASK-04 STORAGE / BOUNDARY RULES

Task-04 classification persistence remains separate from Task-01 evidence persistence.

Conceptually:

```text
Task-01 Evidence DB
        ↓ READ
Task-04 classifier
        ↓
Classification DB
```

No cross-MAC identity merge.

No Authorization change.

No public UI requirement inside Task-04.

No Device Card implementation inside Task-04.

---

# 12. POST TASK-04 OWNERSHIP

After Task-04:

```text
TASK-05
identity/session integration

TASK-06
Device Card / Admin presentation
```

Task-04 must not absorb these scopes.

---

# 13. EXECUTION COMMAND FORMAT

After this roadmap is canonical, each implementation task must be narrow.

Template:

```text
DOCUMENT:
TASK-DEVICE-FINGERPRINT-XX
CURRENT MAIN → TASK-04 READINESS

BASELINE:
<exact main SHA>

INPUT:
current repository state
+
accepted prior-stage outputs
+
only Task-04 requirements relevant to this stage

GOAL:
implement the missing delta only

FORBIDDEN:
redesign frozen earlier stages
implement later stages
invent Owner policy

TESTS:
<narrow stage tests>

HANDOFF:
changed files
commit SHA
test results
known blockers

NO MERGE / NO DEPLOY
unless separately authorized
```

---

# 14. STAGE TRANSITION RULE

The only normal transition is:

```text
Architect narrow analysis
        ↓
Tech Lead review
        ↓
Owner decisions if any
        ↓
Tech Lead Coder task
        ↓
Coder implementation + narrow tests
        ↓
Tech Lead / Owner acceptance
        ↓
STAGE FREEZE
        ↓
NEXT STAGE
```

Do NOT skip directly from Architect design to multi-stage Coder implementation.

---

# 15. TIMEOUT / OVERSIZED-TASK RULE

If Architect or any reasoning agent repeatedly times out while trying to handle multiple stages:

```text
STOP THE MONOLITHIC REQUEST
```

Do NOT simply retry the same oversized task indefinitely.

Return to the current stage only:

```text
CURRENT MAIN
→
CURRENT STAGE READINESS
```

No loss of frozen earlier work.

---

# 16. PROJECT ANTI-REGRESSION RULE

This roadmap is specifically intended to prevent a repeat of the monolithic-review failure mode.

Forbidden pattern:

```text
design 01
+
redesign 02
+
redesign 03
+
redesign 03A
+
design 04
+
activation
+
rollback
+
all acceptance gates
in one continuously rewritten task
```

Required pattern:

```text
01 READY → FREEZE
02 READY → FREEZE
03 READY → FREEZE
03A READY → FREEZE
FOUNDATION ADMIT
04 IMPLEMENT
```

---

# 17. OWNER ESCALATION RULE

Architect and Tech Lead must proactively tell Owner when the work is drifting from this roadmap.

Do NOT wait until the project is already trapped in a large rewrite.

Escalate when:
- one stage starts pulling unrelated earlier stages back into scope;
- one task grows beyond a bounded reviewable implementation unit;
- the same architecture document is repeatedly rewritten without closing a gate;
- an unresolved Owner decision is being silently converted into a technical default;
- repeated timeouts indicate the active task is too large;
- implementation order no longer matches this roadmap.

Required escalation wording in substance:

```text
OWNER DECISION / PROCESS CORRECTION REQUIRED

Current work has left the canonical stage boundary.

Proposed correction:
<exact bounded correction>

No implementation continues across that boundary
until Owner/Tech Lead resolve it.
```

---

# 18. CANONICAL PATH

This is the path to remember:

```text
CURRENT MAIN

↓
TASK-01 → TASK-04 READINESS
↓ GATE
FREEZE 01

↓
TASK-02 → TASK-04 READINESS
↓ GATE
FREEZE 02

↓
TASK-03 → TASK-04 READINESS
↓ GATE
FREEZE 03

↓
TASK-03A → TASK-04 KNOWLEDGE / VALIDATION READINESS
↓ GATE
FREEZE 03A

↓
FOUNDATION ADMISSION

↓ OWNER AUTHORIZATION

TASK-04 IMPLEMENTATION

↓
TASK-04 ACCEPTANCE

↓ OWNER PRODUCTION-ACTIVATION DECISION

TASK-05

↓
TASK-06
```

No model, Architect, Tech Lead, or Coder may silently replace this order with a monolithic implementation plan.

---

# 19. CURRENT NEXT ACTION

Until explicitly superseded by Owner:

```text
NEXT ARCHITECT REQUEST =
TASK-DEVICE-FINGERPRINT-01
CURRENT MAIN → TASK-04 READINESS

NOT:
full 01→04 architecture rewrite
```

The Architect must inspect current `main`, identify only the Task-01 delta required for Task-04, surface Owner decisions separately, and stop at the Task-01 readiness boundary.

---

# 20. AUTHORITY

This roadmap controls implementation ORDER and stage boundaries.

Detailed accepted task/foundation contracts control technical semantics inside their respective frozen stage.

If a detailed document appears to imply a different implementation order:

```text
STOP
→ escalate to Owner + Tech Lead
→ do not silently reorder stages
```
