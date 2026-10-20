# TASK-TRAFFIC-PARTIAL-COVERAGE-01 — TECH LEAD ARCHITECTURE REVIEW R2

**Project:** CaptivPortal  
**From:** Technical Lead  
**To:** CaptivPortal Architect  
**Reviewed:** `TASK-TRAFFIC-PARTIAL-COVERAGE-01-ARCHITECTURE-ADDENDUM-R2-RAW-RANGE-COVERAGE`  
**Parent:** `TASK-TRAFFIC-PARTIAL-COVERAGE-01-ARCHITECTURE-CONTRACT-v1-R1`  
**Baseline:** `main@e8061de9fbd6da8be5cd269779070a4db4d59d64`  
**Date:** 2026-10-11

## 1. Tech Lead disposition

```text
R2 FACTUAL FINDING (SCHEMA v1 CANNOT PROVE NEGATIVE FULL-RANGE COVERAGE) = PASS
R2 SAFE FAILURE-STATE DISTINCTIONS = PASS
R2 MANDATORY PREREQUISITE AS THE ONLY IMPLEMENTATION PATH = NOT ACCEPTED YET
R2 MAIN TASK RESUME = HOLD
CODER = HOLD
CODER SOURCE MODIFICATIONS = NO
PRODUCTION CHANGE = NO

REVIEW QUESTIONS = TL-R2-01..TL-R2-04
REQUEST = BOUNDED ARCHITECTURE DECISION / NO REDESIGN OF R1 CORE
```

I accept that raw `MIN/MAX`, a current retention setting, strict-success boundaries and Traffic Projection boundaries cannot prove the negative claim that the full historical raw range was continuously preserved. The original R1 `has_partial_measurements=false` must not be emitted without actual coverage authority.

However **this does not imply that showing positively observed partial traffic must wait for new Observation schema/writer metadata**. R2 §16 itself explicitly says that Current live coverage and reading existing partial cycles/partial-bucket arithmetic remain feasible without new acquisition, yet unconditionally freezes the *entire parent task* pending a new metadata prerequisite. That is a product sequencing decision, not a logical consequence of inability to prove absence.

## 2. Blocking scope/proportionality questions

### TL-R2-01 — Positive evidence versus negative absence proof (P1)

R2 makes *full raw-range proof* a prerequisite for **both** `has_partial_measurements=false` and showing **positively found** partial buckets (R2 §§6.2, 6.4, 9, 16). These are different kinds of claims:

- **Negative assertion**: “No partial traffic evidence existed anywhere in the requested range.” This requires complete raw-range coverage proof; present schema v1 cannot provide it.
- **Positive assertion**: “These specific, persisted, structurally valid partial AP measurements were observed at these timestamps.” This can be checked on the existing SQLite rows without claiming that the entire requested interval is covered.

Architect must evaluate a **minimal, fail-closed `positive-evidence-only` read mode** that:

1. Allows displaying observed trustworthy partial numeric/evidence-only buckets even when full raw-range coverage is `indeterminate` or positively `incomplete`, provided the actual selected rows pass the existing R1 integrity, source-selection, temporal, Site and hard-cap gates.
2. Never asserts `has_partial_measurements=false` without proof. For indeterminate/incomplete ranges, distinguish **partial evidence observed** from **whole range verified** with separate wire states; no `status=ok/full range` claim.
3. Never silently enables a full-period Average/Peak, comparison or AP share based on a partial subtotal; keep strict projected metrics independent and visibly scoped to complete intervals; suppress comparisons/AP share unless justified.
4. Returns no truncated numeric buckets on query deadline, capacity exhaustion or source integrity failures; preserves the fail-closed unknown/error semantics.
5. Does not use current AP status for retroactive historical Offline claims, modify sources, introduce fake zeros or change legacy routes.
6. Specifies exact DTO, historical chart, status labels and deterministic T19/T21/positive-evidence fixtures if the option is accepted.

**Do not hand wave the potential new contract.** Answer whether this path is safe and feasible, and exactly why if rejected.

### TL-R2-02 — Minimal Current Traffic first (P1)

The triggering incident was **Home → Traffic Now and Traffic → Current** going blank when AP-4 was physically unplugged. R1 live `complete_online_population` and `partial_measured` already have sufficient current authoritative status and rate evidence. Raw historical *negative coverage* proof is not needed for the Current calculation.

Architect must decide whether a separately gated **Current-first implementation milestone** may be extracted from `TASK-TRAFFIC-PARTIAL-COVERAGE-01` with unchanged R1 current semantics:

- Home Traffic Now;
- Traffic Current, and per-AP current details;
- existing `CurrentStateReadService` bounded AP status authority;
- no schema/writer/Omada change;
- legacy strict behavior unchanged if feature disabled;
- history overlay remains held/disabled until its own resolution.

If yes, freeze the exact stage boundary, feature-flag semantics, API/UI behavior, tests, accepted file surface and handoff sequence. If no, explain the actual dependency that prevents Current-only delivery, beyond preserving an original monolithic TASK scope.

### TL-R2-03 — Value of prerequisite 01A for historical incident/restarts (P1)

R2 §§8–9 forbid retrospectively proving coverage. `RawObservationCoverageSegmentV1` would start producing proof only after its implementation/activation. It **cannot certify the October 10 AP-4 outage**, which is the primary regression evidence and the specific historical gap the Owner wants shown. A negative, whole-range proof for old 24h/7d windows cannot be manufactured by migration without false data.

R2 also declares process restarts to break segments unless a separately proven handoff protocol is available (§8.6); and v1 forbids stitching across segments (§9.2). Unless a robust restart/handoff protocol is designed and accepted, a single restart can make entire 24h/7d windows `not covered` for the ensuing window until enough continuous uptime has elapsed.

Architect must state quantitatively and explicitly:

- earliest expected eligibility for a genuinely covered **24h** and **7d** range after installing 01A;
- expected results for the historical **Oct 10 incident** after enabling 01A;
- behavior after **one** normal `captive-portal.service` restart (and subsequent 24h/7d requests);
- whether non-stitchable single-generation proof aligns with the Owner's main problem and is proportionate.

Do not promise the prerequisite will recover pre-instrumentation history.

### TL-R2-04 — Is 01A ready for an implementation task? (P1)

R2 describes the minimum *logical* segment shape but explicitly allows alternative physical schema representations, leaves canonical numeric serialization “project-defined” (§8.5), and permits continuity handoff only under a future proved rule (§8.6). It also requires protected Observation schema + writer changes which the accepted parent R1 explicitly forbade.

Before issuing an executable Coder TASK for 01A, Architect must freeze its **complete, independently reviewable implementation architecture**, including:

- migration/versioning and preserving the existing production `observations.sqlite3` safely, with no fabricated pre-migration coverage;
- exact atomicity and state-transition rules for cycle creation, completion/abandonment, retention cleanup and failed writes;
- persisted segment/sequence constraints and indexed bounded proof lookup;
- exact canonical fingerprint numeric normalization and source configuration generation;
- exact startup/restart/disable/handoff and `next_due_at_utc` handling;
- behavior under concurrent readers, 5-second budget and Site changes;
- deterministic adversarial tests and rollback/feature safety.

This is a separate architecture review and **requires the Owner's explicit agreement** because it expands protected Observation schema/writer scope.

## 3. Requested Architect decision (not open-ended implementation choice)

Compare **both** paths explicitly:

```text
OPTION A — MINIMAL SAFE TRAFFIC FIX (PREFERRED FOR EVALUATION)
Current live correction now; historical positive partial evidence-only overlay if safe;
unknown full-range negative proof stays UNKNOWN; no new schema/writer.

OPTION B — FULL RAW COVERAGE AUTHORITY
Add protected Observation schema/writer metadata prerequisite 01A;
full negative-history proof may become possible only for post-activation compatible segments.
```

Return a bounded `TASK-TRAFFIC-PARTIAL-COVERAGE-01-ARCHITECTURE-DECISION-R3`:

1. **Preferred option** with technical and product rationale, not merely restating R2 HOLD.
2. If Option A is safe: exact minimal contract amendment(s) and revised acceptance fixtures, so the existing Coder TASK can be minimally amended and resumed under Owner authorization. Explicitly distinguish positive observations from unproven absence.
3. If Option A is unsafe: a precise counterexample/proof of why displaying individually verified partial measurements with incomplete-range warning would misrepresent their *own measured meaning*. Then provide the complete prerequisite 01A architecture contract and its expected 24h/7d operational tradeoffs.
4. If only a Current-first split is safe: freeze that split as an independent narrowly scoped milestone, keeping historical implementation HOLD.

**Non-negotiable:** No raw `MIN/MAX` as absence proof; no fake zeros; no Wired/LAN mixing; no hidden partial-to-full metric promotion; no extra Omada calls; no accidental changes to NI-04; production remains untouched.

## 4. Governance

```text
CODER = HOLD
CURRENT WORKTREE = CLEAN / NO SOURCE MODIFICATIONS REPORTED
OWNER IMPLEMENTATION AUTHORIZATION = NOT GRANTED FOR 01A
NEW SCHEMA/WRITER CHANGE = NOT AUTHORIZED
MERGE/DEPLOY/PRODUCTION = NOT AUTHORIZED
```

After Architect R3, Technical Lead independently reviews the selected contract. Only then may Technical Lead issue the bounded Coder task or amendment; Owner authorization remains a separate gate.
