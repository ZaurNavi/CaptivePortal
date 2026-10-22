# TASK-TRAFFIC-PARTIAL-COVERAGE-01 — ARCHITECTURE CLARIFICATION R2
## Raw Observation Range Coverage Authority — Coder STOP / T19 versus T21

**From:** CaptivPortal Technical Lead  
**To:** CaptivPortal Architect  
**Date:** 2026-10-11  
**Status:** ARCHITECTURE HOLD — BOUNDED CLARIFICATION REQUIRED  
**Affected parent:** `TASK-TRAFFIC-PARTIAL-COVERAGE-01-ARCHITECTURE-CONTRACT-v1-R1`  
**Relevant sections:** §17.2-B/E, §18, §19, T19, T21, §40  
**Coder state:** Worktree clean, source unchanged; no tests/commit/push/PR/merge/deploy/production action.  
**Baseline:** `main@e8061de9fbd6da8be5cd269779070a4db4d59d64` / tree `d5503fe1f2b5774bbe55cb2d34dba63246f56f6f`.

## 1. Why a correction is required

Coder correctly stopped at the task's explicit blocker:

`HOLD_RAW_RANGE_COVERAGE_CLARIFICATION`

R1 §17.2-B permits `status=ok`, `has_partial_measurements=false` only if a **fully covered raw Observation range** has been checked and no partial cycles exist. R1 §19/T21 requires `status=source_coverage_insufficient` if that range is not covered. However **the exact proof predicate is not frozen**, and the authorized raw store has no independently recorded retention/coverage watermark.

Verified code facts from the pinned baseline:

- `app/observations/repository.py::delete_expired_cycles()` removes non-running cycles with `started_at < cutoff_utc` using bounded deletion, without persisting a deletion/coverage watermark.
- Existing `app/analytics/source_gateway.py::_historical_source_bounds()` derives usable strict-history boundaries from validated successful/complete traffic samples. Those boundaries **cannot** prove preservation of all raw partial cycles.
- `TrafficProjectionReadService` returns projection-derived bounds. These likewise **cannot** serve as an independent raw Observation range-coverage authority.
- Merely taking `MIN`/`MAX` timestamps of existing Site-scoped raw cycles, without an explicitly justified rule, does not establish continuity or absence of discarded/missing intermediate evidence.

**No Coder-defined approximation, assumption about retention, or silent `false` is allowed.** The issue is not a reason to redesign Option 3, its read-only overlay, or the safe-failure JSON already accepted in R1.

## 2. Decision required — freeze one implementable proof rule

Please issue a **narrow R2 amendment** specifying the complete deterministic predicate for `raw_observation_range_covered(site_id, from_utc, to_utc, evaluated_at_utc)` that the implementation can evaluate from already authorized sources, or explicitly conclude that it cannot be proven without a protected architecture change.

The amendment MUST resolve these questions:

1. **Authority:** Which *existing* persisted facts may prove the raw range: `observations.sqlite3` `observation_cycles`, existing Observation configuration/retention, authoritative collection metadata, or something else already available? Declare forbidden substitutes explicitly: strict-success history bounds and Traffic Projection bounds are not independent raw-retention proof.
2. **Exact Site/scope:** Which `site_id`, `kind='ap_dynamic'`, scope/version criteria and identity consistency checks govern the proof? Must different scope histories or a Site added mid-window fail the proof?
3. **Boundary definition:** Specify exact inclusive/exclusive timestamp predicates for `[from_utc,to_utc)`, taking into account that `to_utc` is commonly "now" and the most recent normal collection may have finished *before* `to_utc`. If using tolerance, freeze its source, units and allowable range; no arbitrary Coder-chosen seconds.
4. **Eligible lifecycle/result:** Which `state` and `result` cycles count toward boundary coverage proof (`completed/success`, `completed/partial`, `completed/failed`, `completed/shutdown`, `abandoned`, `running`)? Distinguish cycles usable for retention/coverage proof from cycles eligible for numeric overlay.
5. **Gaps and truncation:** Is a simple earliest/latest bracketing rule sufficient, or must the implementation prove collection continuity/max permitted inter-cycle gap? If gaps are checked, specify ordered key, exact comparison, permitted interval and behavior when no cycles exist. State why the selected criterion really supports "no retained partial cycles" given time-based cleanup without watermark.
6. **Retention/deletion:** Define how to handle `dynamic_retention_days`, cleanup lag, raw database creation/initialization after requested range start, loss of source access, manual/intermediate deletions (if detectable), and ranges straddling the oldest available raw data. No assumption that a default 180-day retention alone proves real historical coverage.
7. **Failure classification:** Freeze which condition returns each accepted R1 envelope:
   - `ok` + `has_partial_measurements=false`;
   - `ok` + `has_partial_measurements=true`;
   - `source_coverage_insufficient` + `has_partial_measurements=null`;
   - `unavailable` + `has_partial_measurements=null`;
   - `capacity_limited` + `has_partial_measurements=null`.
   Clarify unknown/indeterminate proof versus positively established insufficient coverage, and forbid classifying an empty query result as proven absence by itself.
8. **Bounds/performance:** Prove that the required determination can run within the existing 5-second local overlay budget, 10,080-cycle/150,000-row hard caps and Site/time indexed scans, with no new DB/index/schema/writer/background job. If it cannot, give an explicit architectural HOLD rather than a fictitious PASS.

## 3. Mandatory deterministic tests in the amendment

Supply exact input cycles/coverage facts and expected wire status for at least:

- **T19 (strict-only, proven fully covered):** A normal, recent 24h range with complete strict traffic data and zero raw partial cycles. Must have a reachable PASS fixture for `has_partial_measurements=false` / `status=ok`.
- **T21 (provably incomplete raw range):** A 7d or 24h request extending before Site collection/raw retention began. Expect `status=source_coverage_insufficient`, `has_partial_measurements=null`, empty overlay buckets and blocked comparison/AP share.
- **Now-boundary:** Request `[now-24h, now)` with last valid collector cycle ending less than a full polling period before `now`.
- **Internal gap:** Raw cycles on both sides but no cycles in a middle period; determine whether coverage can be asserted or is unknown/insufficient.
- **Only failed cycles:** Failed/shutdown/abandoned/running cycles present, no admitted partials: distinguish range proof from numeric evidence.
- **Retention trim:** Time-based cleanup has removed older cycles; requested range begins before, at, and after the recorded earliest raw timestamp.
- **Site/scope transition:** Observation history exists for another Site or previous collection scope, but not the entire target Site/range.
- **Overlay capacity/source failure:** The status must preserve the previously frozen `capacity_limited`/`unavailable` envelopes without false absence assertions.

## 4. Fixed, non-negotiable constraints

Preserve in full the accepted R1 architecture:

- Option 3, confirmed Offline exclusion only for time-aligned current status; otherwise measured subtotal explicitly partial.
- Historical partial overlay remains read-only, bounded and independent of strict Projection statistics.
- No fake zero; no Wired/LAN mixing; no retroactive Offline status in historical data.
- No Observation/Traffic Projection/Current State schema, writer or collector changes; no new database, materializer, API source, Omada calls, retention change or production action **without further explicit Owner/Architect review**.
- Existing strict endpoints/API remain unchanged without `coverage_mode=partial_v1`.
- Feature flag default OFF and independent merge/deploy/activation approvals.

If the requested **proof** is impossible using the approved facts, say `ARCHITECTURE HOLD / ADDITIONAL PREREQUISITE REQUIRED`, identify the exact minimal prerequisite and return to Owner/Tech Lead. Do **not** force Coder to invent a proof or to return fake `ok`.

## 5. Expected deliverable

`TASK-TRAFFIC-PARTIAL-COVERAGE-01-ARCHITECTURE-ADDENDUM-R2-RAW-RANGE-COVERAGE.md`

This should be a narrow normative supplement; do not rewrite the whole R1 document. Include:

- exact frozen predicate and SQL-implementable retrieval semantics;
- state/failure matrix;
- T19/T21 plus boundary/gap/retention tests with exact expected outputs;
- performance/capacity treatment;
- explicit statement of whether the original no-schema-change implementation remains possible;
- final verdict: `ARCHITECTURE CLARIFICATION PASS / RESUME CODER TASK` or `ARCHITECTURE HOLD / PREREQUISITE REQUIRED`.

**Until Tech Lead accepts the R2 addendum: Coder remains HOLD. No code changes, tests, commits, push, PR, merge, deploy, restarts, or production edits are authorized under this clarification.**
