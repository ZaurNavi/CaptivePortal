# TASK-TRAFFIC-PARTIAL-COVERAGE-01 — CODER IMPLEMENTATION TASK AMENDMENT R3
## Current-first fix and positive-evidence-only historical overlay

**Project:** CaptivPortal / `ZaurNavi/CaptivePortal`  
**Issued by:** Technical Lead  
**Status:** `ARCHITECTURE R3 TECH LEAD ACCEPTED / TASK AMENDMENT ISSUED`  
**Coder implementation authorization:** **NO — explicit Owner authorization required to resume**  
**Production / push / PR / merge / deployment / restart / activation:** **NOT AUTHORIZED**  
**Pinned baseline:** `main@e8061de9fbd6da8be5cd269779070a4db4d59d64`  
**Pinned tree:** `d5503fe1f2b5774bbe55cb2d34dba63246f56f6f`  
**Existing Coder branch:** `feature/traffic-partial-coverage-01`  
**Existing worktree (Coder-reported):** `C:\CaptivPortal-Lab\coder-traffic-partial-coverage-01`  
**Existing Coder state:** clean, no source changes; verify before work, do not assume unchanged.

## 0. Authoritative document set and precedence

This is a **narrow amendment**, not a new independent implementation specification. Coder MUST have and read these complete documents:

1. `TASK-TRAFFIC-PARTIAL-COVERAGE-01-ARCHITECTURE-DECISION-R3(1).md` — accepted decisive change.
2. `TASK-TRAFFIC-PARTIAL-COVERAGE-01-ARCHITECTURE-CONTRACT-v1-R1(1).md` — all unchanged exact models, algorithms, limits, and tests.
3. `TASK-TRAFFIC-PARTIAL-COVERAGE-01-CODER-IMPLEMENTATION-TASK-v1.md` — original implementation instructions as amended here.
4. `TASK-TRAFFIC-PARTIAL-COVERAGE-01-ARCHITECTURE-ADDENDUM-R2-RAW-RANGE-COVERAGE(1).md` — historical diagnosis only where not superseded by R3; **its prerequisite is not required**.

**Precedence in case of conflict:** accepted R3 architecture > R2 addendum > R1 contract > original v1; this implementation amendment explicitly identifies required substitutions for the Coder TASK. **Do not combine incompatible clauses.** If a genuinely unresolved semantic contradiction remains, STOP and return to Tech Lead.

### Decisions now frozen

```text
SELECTED_ARCHITECTURE = OPTION A / MINIMAL SAFE TRAFFIC FIX
PARENT TASK = TASK-TRAFFIC-PARTIAL-COVERAGE-01
STAGE_A = CURRENT-FIRST INCIDENT FIX
STAGE_B = HISTORICAL POSITIVE-EVIDENCE-ONLY OVERLAY
TASK-TRAFFIC-PARTIAL-COVERAGE-01A = NOT A PREREQUISITE
RELIABLE FULL-RAW-RANGE NEGATIVE PROOF = NOT REQUIRED
FEATURE_GATE = WEB_ADMIN_TRAFFIC_PARTIAL_COVERAGE_ENABLED=false BY DEFAULT
NEW_DB/COLLECTOR/OMADA_CALL/SCHEMA/WRITER/BACKFILL = NO
```

Missing traffic remains **missing**, not numeric `0`. A confirmed Offline AP may be **excluded from the current expected-online measurement population**, only with authoritative **time-aligned** Current State evidence. Historical partial data are shown only when **positively observed** in retained Observation rows and individually validated.

## 1. Clear resolution of the previous Coder STOP

Previous blocker:

```text
HOLD_RAW_RANGE_COVERAGE_CLARIFICATION
R1 T19 vs T21: no persisted source-range coverage watermark
```

**Resolution accepted:** schema v1 cannot prove negative full-period coverage. Stage B MUST NOT attempt that proof. It must **not** require a new coverage watermark, new persisted segment object, database migration, new writer, or separate `01A` prerequisite.

What Coder now MUST implement for `coverage_mode=partial_v1` historical response:

- Validated retained partial cycle(s) found by completed bounded scan → return **positive evidence**; `has_partial_measurements=true`.
- No admitted partial cycle found by completed bounded scan → **unknown**, `has_partial_measurements=null`, **never false**.
- Known retained-prefix shortfall → `source_coverage_insufficient=true`, but do not erase positively validated partial bucket(s).
- No affirmative retained-prefix proof → `source_coverage_insufficient=null`, not false.
- Query/source failure or capacity reached → no truncated partial buckets or claims; exact safe envelopes.

**The original Coder TASK v1 STOP rule** “reliable raw source-range coverage cannot be established” is **replaced**: that condition alone is no longer a blocker under R3. It is instead an explicitly supported **unknown evidence state**. All other STOP conditions remain active.

**Important:** strict projected Historical remains independent. An R3 unknown does not erase independently valid strict Average/Peak numeric values; it qualifies their meaning and prevents unsupported full-period comparison/AP share claims **in partial_v1 mode only**.

## 2. Work sequencing / stage release gates

### Stage A — IMPLEMENT FIRST, independently reviewable

Scope ONLY:

```text
Home → Traffic Now
Traffic → Current Network Traffic
Current per-AP Traffic details
```

Stage A preserves the existing historical endpoint and browser historical request behavior unchanged. It may introduce the **single** new default-OFF flag and dispatch current routes only. No historical overlay implementation, serializer, chart modification, or `traffic/history?coverage_mode=partial_v1` support is allowed in Stage A. Do not create a second feature flag.

**Stage A gate:** implementation and tests → local commit/handoff → Tech Lead review → Owner independently decides merge/deploy/restart/activation. The existence of Stage B must **not** delay Stage A technical acceptance or approved deployment.

### Stage B — SEPARATE LATER HANDOFF

Start only **after Stage A Tech Lead acceptance and a further explicit Owner go-ahead for Stage B**. Stage B adds only the Historical Traffic positive-evidence-only overlay as specified by R3. It uses the **same** feature flag; no second flag or source-of-truth.

Stage A and B may use the same branch/worktree only if Tech Lead confirms the baseline and no unrelated commits interfere. Do not silently merge, rebase or modify Stage A after acceptance. Prefer separate clearly identified commits/change sets for independent review.

## 3. Stage A exact implementation instructions

Use original Coder TASK v1 §§3A, 3B, relevant §§3D/3E, R1 §§4–12 and §§20–23 unchanged except staging. Implement:

**A1 — Authoritative status boundary**

```python
CurrentStateReadService.read_ap_status_evidence_at(
    site_id, traffic_finished_at
) -> CurrentApStatusEvidenceV1
```

From the latest **complete successful** AP Current State snapshot for the same Site with `capture_finished_at <= traffic_finished_at`. Source age at traffic time must be within `CurrentStateConfig.ap_fresh_max_age_seconds` (default 90s) to exclude confirmed Offline. No future snapshot, inferred Offline, name/IP-only join, or cross-Site MAC join. Read only; no new Current State collector/DB/schema or browser endpoint.

**A2 — Current evidence and service path**

```python
AnalyticsSourceGateway.read_current_partial_traffic_evidence(...)
CurrentTrafficReadService.get_current_site_traffic_partial_coverage(...)
```

Select newest eligible completed `success|partial` AP-dynamic cycle. Enforce R1 structural integrity and reason/value/timestamp validation, source freshness, time skew, deterministic Wired/LAN selection and Site/MAC population checks. The legacy `get_current_site_traffic(...)` remains strictly unchanged.

Measurement states (closed set):

```text
complete_installed
complete_online_population
partial_measured
unavailable
```

R1 precedence remains binding: a globally partial source cycle with all **observed** APs measured but no independent installed-population proof is **partial_measured**, not `complete_installed`.

**A3 — AP-4 incident canary**

Aligned Current State says 3 Online + 1 Offline. AP1/AP2/AP3 provide valid selected-source pairs; AP4 selected-source rates are `NULL/source_unavailable`. Source cycle is structurally valid, even though result=`partial` and `error_count=2`.

Expected:

```text
measurement_state = complete_online_population
population_scope = confirmed_online
Online = 3; total installed = 4; Offline excluded = 1
Download = sum(AP1..AP3 actual Download)
Upload = sum(AP1..AP3 actual Upload)
Total = Download + Upload
AP4 numeric rate = null, not a fake 0
```

Primary deterministic fixture: AP1=10/1, AP2=5/1, AP3=3/1, AP4=2/1 Mbps when online. All four valid → `20/4/24`; AP4 confirmed Offline and missing → `18/3/21`, with `3 Online / 4 total · 1 Offline excluded`.

AP4 Online or status stale/unknown with absent rates → `partial_measured`, same measured subtotal labeled **partial**; all selected-source directions missing → `unavailable`, numbers `NULL`, not zero. On AP return: `no_baseline`/`counter_reset` → partial; next valid pair → complete installed without manual repair.

**A4 — Current Admin API and flag**

Implement one exact env→config→settings→AdminWebConfig default-OFF flag:

```text
WEB_ADMIN_TRAFFIC_PARTIAL_COVERAGE_ENABLED=false
```

Current opt-in routes only:

```text
GET /admin/api/v1/sites/<site_id>/current-traffic/summary?coverage_mode=partial_v1
GET /admin/api/v1/sites/<site_id>/current-traffic/aps?cycle_id=...&coverage_mode=partial_v1
GET /admin/api/v1/sites/<site_id>/traffic/current?coverage_mode=partial_v1
```

No coverage parameter → **unchanged strict** response. Invalid/duplicate mode → `400 invalid_request`; requested mode when gate OFF → `404 not_found`; ACL/Site controls remain. AP detail paging must share the summary's selected cycle/source/status context; no fabricated AP rows.

**A5 — Current UI only**

When gate ON: Home Traffic Now and Traffic Current request/consume the new safe current DTO, without recalculating completeness in JS. Exact R1 English copy and states. Gate OFF: preserve legacy strict requests. Reuse existing refresh loop. **Stage A Traffic History must continue making its original strict request with unchanged UI.**

## 4. Stage A required tests and handoff

Stage A must test its own production code paths (not parallel test-only arithmetic), including the **current-specific portions** of R1 T01–T10, T12–T16 and R3-T01–T04. Historical halves of R1 T02/T05/T11/T13 and all historical-only fixtures are **deferred to Stage B**, not misreported as PASS.

Mandatory Stage A test matrix:

| Gate | Required PASS proof |
|---|---|
| A-T01 | 4/4 valid current AP measurements → complete_installed / 24 Mbps |
| A-T02 | confirmed Offline AP4 / 3 valid → complete_online_population / 21 Mbps / exclude not zero |
| A-T03 | AP4 Online missing → partial_measured / 21 Mbps warning |
| A-T04 | Offline status unknown/other/stale/unavailable → no false complete-online promotion |
| A-T05 | all rates missing → unavailable / null, not zero; actual valid numeric zero remains zero |
| A-T06 | offline→online no_baseline/counter_reset→valid full recovery; no stale reuse |
| A-T07 | inventory mismatch / wrong Site / same MAC different Site → no false full coverage or cross-Site join |
| A-T08 | timestamp skew/fresh/stale/unavailable, no future status evidence |
| A-T09 | Wired/LAN priority and no mixing; exact selection reason |
| A-T10 | structurally invalid newest candidate fails closed; no fallback to stale apparently-fresh numeric |
| A-T11 | offline status conflicts with counter_reset/numeric ⇒ `status_measurement_conflict` |
| A-T12 | strict legacy API unchanged absent mode; gate OFF; invalid/duplicate mode; 401/403/Site; response bounds |
| A-T13 | UI Home + Traffic Current exact labels/coverage and flag OFF behavior, no History UI/API changes |
| A-T14 | original AP-4 synthetic replay with result=partial/error_count=2, followed by automatic recovery |
| A-T15 | protected collectors/writers/NI/Guest/Session/Portal/Auth/CAPPORT unaffected |

Run targeted existing and new tests, JS checks if touched, all-repo pytest, compileall, `git diff --check`. Report PASS/FAIL/SKIP with counts and explicit evidence. If a full gate cannot run, report `BLOCKED`; never invent PASS. No live disconnection of AP4 is required or authorized—use deterministic synthetic fixtures.

Stage A handoff:

```text
TASK=TASK-TRAFFIC-PARTIAL-COVERAGE-01
STAGE=A_CURRENT
ARCHITECTURE=R3_TECHLEAD_ACCEPTED
IMPLEMENTATION_AUTHORIZATION=<explicit Owner approval, or HOLD>
BASE_HEAD=e8061de9fbd6da8be5cd269779070a4db4d59d64
BASE_TREE=d5503fe1f2b5774bbe55cb2d34dba63246f56f6f
IMPLEMENTATION_COMMIT=<sha>
IMPLEMENTATION_TREE=<sha>
CHANGED_FILES=<list>
TARGETED_TESTS=<exact evidence>
FULL_PYTEST=<PASS/FAIL/BLOCKED, counts>
JS_CHECKS=<...>
COMPILEALL=<...>
DIFF_CHECK=<...>
CURRENT_AP4_REPLAY=<PASS/FAIL>
LEGACY_HISTORY_UNCHANGED=<PASS/FAIL>
FEATURE_DEFAULT=false
OBSERVATION_SCHEMA/WRITER_CHANGE=NO
TRAFFIC_PROJECTION_SCHEMA/WRITER_CHANGE=NO
CURRENT_STATE_SCHEMA/COLLECTOR_CHANGE=NO
NEW_OMADA_CALLS=NO
PRODUCTION_ACTIONS=NO
PUSH/PR/MERGE/DEPLOY=NO
OPEN_P0=<n>
OPEN_P1=<n>
OPEN_P2=<n>
TECH_LEAD_REVIEW=REQUESTED
```

**STOP** if working baseline/tree moved, protected writes become necessary, new source/persistence required, R1 validators cannot be preserved, flags/control cannot be kept backwards compatible, or any unapproved production/merge/push action would be needed.

## 5. Stage B exact amendments (DO NOT IMPLEMENT BEFORE STAGE A ACCEPTANCE)

Keep original v1 TASK §3C on bounded raw Observation read, R1 bucket source selection, independent directional samples, coherent Total arithmetic, capped batches, sparse buckets, strict projection/statistics independence. Replace only **negative range-proof assumptions and historical wire/UI semantics** with R3 §§6–10.

**B1 — Positive evidence, not whole-range absence:** a completed bounded read of retained structurally admissible partial AP-dynamic cycles may positively report observed partial samples. It must never assert the absence of partial cycles across the entire historical period merely because none are visible. No raw coverage watermark and no `01A` prerequisite.

**B2 — R3 overlay status and reason enums** (replace old R1/R2 overlay `status=ok` and related reasons on schema v1):

```text
partial_coverage.status:
  partial_evidence
  source_coverage_insufficient
  unavailable
  capacity_limited

partial_coverage.reason:
  partial_measurements_observed
  raw_observation_range_unproven
  raw_observation_range_incomplete
  overlay_source_unavailable
  overlay_capacity_limited
```

Retain the same `network_traffic_partial_coverage_overlay.v1` metric version; `has_partial_measurements` and `source_coverage_insufficient` remain JSON `boolean|null`.

**B3 — Exact safe decision table:**

| Completed evaluation outcome | status | reason | `has_partial_measurements` | `source_coverage_insufficient` | partial buckets |
|---|---|---|---|---|---|
| ≥1 admitted partial, range unproven | `partial_evidence` | `partial_measurements_observed` | `true` | `null` | validated R1 buckets |
| ≥1 admitted partial, retained-prefix shortage proven | `partial_evidence` | `partial_measurements_observed` | `true` | `true` | validated R1 buckets |
| 0 admitted, range unproven | `source_coverage_insufficient` | `raw_observation_range_unproven` | `null` | `null` | `[]` |
| 0 admitted, retained-prefix shortage proven | `source_coverage_insufficient` | `raw_observation_range_incomplete` | `null` | `true` | `[]` |
| Source/validation unavailable | `unavailable` | `overlay_source_unavailable` | `null` | `null` | `[]` |
| Capacity/deadline exceeded | `capacity_limited` | `overlay_capacity_limited` | `null` | `null` | `[]` |

For positive results, count fields are **actual bounded examined/admitted/rejected row counts** and do not claim period completeness. For completed but zero-admitted results, counts are exact observed scan counts (admitted 0), not fabricated. On source or capacity failure, all examined/admitted/rejected/row counts are `null`, buckets `[]`, bucket_count_returned 0. No partial/truncated results escape. In **all schema-v1 R3 cases**, `comparison_allowed=false`, `ap_share_allowed=false`, comparison numeric fields `NULL`, and public AP-share fractions `NULL` in opt-in partial mode. Strict response without opt-in stays exactly as before.

**B4 — No negative full-range assertion:** `has_partial_measurements=false` is **forbidden** on schema v1 under R3; `source_coverage_insufficient=false` must not be synthesized. No `MIN/MAX`/retention-configuration/projection-bounds proof of full continuity. A source first-row later than `from_utc` may only support a positive retained-prefix-shortage flag; it may not establish that no partial rows existed or suppress actual validated positive rows.

**B5 — Historical UI:** show only **positively validated** partial buckets; preserve complete strict series distinct. `partial_measured` = observed numeric subtotal; `partial_directional` = only measured direction, no fabricated combined Total; `partial_unmeasured` = evidence-only marker, no numeric zero. For a mixed strict/partial bucket, both must remain separate. Exact R3 text:

```text
Average · complete-coverage intervals only
Max observed with complete AP coverage
Observed partial AP measurements are shown separately; they are not included in the strict Average or Peak.
No partial AP measurements were found in retained evidence; full-period partial coverage is not verified.
Partial-coverage evidence is incomplete for part of this period.
```

Use the applicable message for actual R3 state and the exact R1 categorical graph/tooltips where not changed by R3. Historical Stats/Peak numbers remain strict; do not average a 3-AP subtotal into the 4-AP complete rate history.

**B6 — Stage B opt-in route only:**

```text
GET /admin/api/v1/sites/<site_id>/traffic/history?range=24h&coverage_mode=partial_v1
GET /admin/api/v1/sites/<site_id>/traffic/history?range=7d&coverage_mode=partial_v1
```

Preserve existing product `include`/`products`, Site ACL, deadlines, response caps, strict requests absent mode and no new browser-to-source fan-out. When the common feature flag is enabled after B acceptance, Traffic History may request opt-in; prior to B, History must remain strict even when current partial mode is enabled.

**B7 — Read limits:** keep `10,080` candidate partial cycles/request, `150,000` partial AP rows/request, batch ≤ `2,000`, local overlay deadline ≤ `5s`, existing 24h/7d bucket counts/≤720, indexed Site-time queries, no OFFSET, no unbounded in-memory rows. If not fully evaluated within caps, return `capacity_limited` and **no partial numeric buckets**.

**B8 — Stage B test matrix:** all R1 historical fixtures still apply except where superseded by R3. Required extra exact assertions:

```text
R3-T19: zero admitted partial cycles -> unproven, has_partial_measurements=null (not false)
R3-T20: observed Oct10-like 3/4 partial cycle -> partial_evidence, true, visible subtotal
R3-T21: empty query + proven retained-prefix shortage -> incomplete=true, no false absence
R3-T22: retained-prefix shortage + positive partial -> partial_evidence, true; return valid buckets
R3-T23: no valid directions -> partial_unmeasured and NULL numeric fields
R3-T24: partial_directional, no invented Total
R3-T25: deadline/cap overrun after reads -> capacity_limited, counters null, no buckets
R3-T26: unreadable source -> unavailable, counters null, no buckets
R3-T27: single Wired/LAN family, no mixing
R3-T28: strict numeric stats unchanged; opt-in comparison/AP share disallowed
```

Also test strict+partial overlapping bucket, historical 4→3→4 visual quality, Site isolation, AP count ratio `7/9` opportunity formula (R1 T25), structural rejection behavior, source unavailable, old strict API compatibility, and the real Oct10 AP4 synthetic replay. Stage B handoff requires full original repository gate and explicit independent Tech Lead review. **Stage B does not authorize merge/deploy/activation.**

## 6. Approved implementation surfaces / protected modules

**Stage A:** only files enumerated in R3 §11 Stage A (existing Current read/DTO/Current State read boundary, Admin current routes/serialization/config/templates/current JS, settings and relevant tests).  
**Stage B additionally:** `app/analytics/historical_traffic.py`, `app/traffic_projection/read_service.py` (**read-only**), `app/admin_web/historical_traffic_serialization.py` and relevant tests, as listed by R3.

The following remain protected for both stages: Observation AP worker, Observation schema/repository/writer, Traffic Projection schema/repository/projector/writer, Current State collector/repository/schema/status classifier, Omada request behavior, NI modules, Portal/Auth/CAPPORT, Guest/Session/Public Traffic, production service/environment/database files. No new schema, database, background worker, data source, migration, retention change, or backfill. No live AP4 cable tests without Owner permission.

## 7. Mandatory governance / resumption instruction

Coder's previous STOP was legitimate and is resolved **architecturally** by R3. This document does **not** constitute Owner implementation authorization.

**Resumption requires an explicit Owner message approving Stage A Coder work.** If received, confirm exact branch/worktree/HEAD/tree/clean status, read complete sources, and implement **Stage A only**. Never infer permission to push, open PR, merge, deploy or restart production.

After Stage A implementation tests are done, return handoff to Tech Lead. Wait for Tech Lead acceptance and Owner's subsequent Stage B decision. Any baseline movement or incompatibility returns to Tech Lead before coding further.

```text
ARCHITECTURE_R3 = TECH_LEAD_ACCEPTED
PARENT_TASK = OPEN_FOR_STAGED_IMPLEMENTATION_DEFINITION
PREVIOUS_RAW_RANGE_COVERAGE_HOLD = CLEARED_BY_R3
TASK_01A_PREREQUISITE = NO
STAGE_A_CODER = HOLD_UNTIL_EXPLICIT_OWNER_AUTHORIZATION
STAGE_B_CODER = HOLD_UNTIL_STAGE_A_ACCEPTANCE_AND_OWNER_AUTHORIZATION
MERGE = NO
DEPLOY = NO
PRODUCTION_CHANGE = NO
```
