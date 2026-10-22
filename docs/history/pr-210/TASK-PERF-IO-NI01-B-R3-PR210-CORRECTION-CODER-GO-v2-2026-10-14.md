# CaptivPortal — PERF-IO-NI01-B / R3 expired-prefix guard
## TECH LEAD IMPLEMENTATION TASK v2 — CODER GO — PR #210 follow-up correction

**Issuer:** Tech Lead / TechLead23  
**Date:** 2026-10-14 (Asia/Baku)  
**Status:** `CODER_GO_R3_CORRECTION_ONLY / MERGE_HOLD / PRODUCTION_HOLD`  
**Authority:** Chief Architect ratified `CAPTIVPORTAL-PERF-IO-NI01-B-R3-CHIEF-ARCHITECT-RATIFIED-2026-10-14.md`, status `ARCHITECT_R3_ACCEPTED_WITH_CLARIFICATIONS`. This TASK incorporates the clarifications and **supersedes** prepared `TASK-PERF-IO-NI01-B-R3-PR210-CORRECTION-CODER-HOLD-2026-10-14.md`, particularly its obsolete instruction *not* to rerun previously passing B-focused tests. R3 controls the modified sensitive path; unmodified R2 contract still controls the rest.

## 0. Exactly pinned source and permission

```text
REPOSITORY=ZaurNavi/CaptivePortal
PR=210
BRANCH=task/perf-io-ni01-b
BASE_MAIN_HEAD=018985edaa008847b64051dc49c90914d0a60238
BASE_MAIN_TREE=b73f0ed2450e24b7fe4298630999f402a980cce1
EXPECTED_PR_HEAD_BEFORE_R3=166a1546c96cdfc09b624b614b6b0080c425a3d3
EXPECTED_PR_TREE_BEFORE_R3=793ffd7025b7161c4cfab193077d114c5e042422
PR_STATE_AT_TECHLEAD_DISPATCH=DRAFT_OPEN_UNMERGED
PR_MERGEABILITY_AT_TECHLEAD_DISPATCH=MERGEABLE
```

The above identities were independently verified on GitHub by Tech Lead at task issuance. **Coder must independently check them again** locally and for remote branch before the first edit and immediately before push. Reuse **the existing PR #210 / its current worktree and branch**. Worktree clean at entry. Do **not** start a second PR, rebase, reset, amend previous commit, merge main, force-push or rewrite history. If any expected identity, remote branch, `main`, or file state diverges: **STOP** and return exact differences to Tech Lead before editing/publishing.

**Permission:** modify only three files enumerated in §1, run laboratory focused tests/evidence, make **one focused follow-up commit**, normal push **to the existing branch**, and update PR #210 handoff/body. Coder cannot merge, deploy, change production config, test on production or touch production SQLite/service. Production A (`NETWORK_METADATA_IO_HOTPATH_V1_ENABLED=true`) continues untouched. B stays **default OFF**.

## 1. Scope: ONLY THREE MODIFIED FILES

1. `app/network_metadata/retention.py` — replace **only** the B=ON / `sensitive` branch of `RetentionPolicy._select()` with approved R3 guarded raw-index lookahead + one legacy fallback.
2. `tests/network_metadata/test_retention.py` — add R3 test cases and adjust **only** those old B R2 tests whose expected query counts/ordering are legitimately changed by R3; preserve all other assertions.
3. `docs/configuration.md` — explain R3 switch, fast/fallback ordering, single fallback trigger, independent default-OFF B flag, limitations of physical I/O claims, and independent activation gate.

**Strictly untouched:** `app/network_metadata/config.py`, `models.py`, `schema.py`, `repository.py`, `service.py`, `normalizer.py`, read/projection paths, systemd, migrations, SQL schema/index definitions, `tests/network_metadata/test_config.py` (READ-ONLY test execution), A hotpath and any other module. No additional feature flag, persistent cursor/store, timer, background job, or configuration digest modification. If three-file limit is insufficient, **STOP** and request a scope decision.

Hard frozen: SQLite V1 exact DDL/signature, FK/cascades, WAL, `synchronous=FULL`, transactions, checkpoint/replay and source lineage; retention thresholds sensitive **14d**, core **30d**, diagnostics **45d**, lineage **90d**; strict `<` cutoff; logical `OR` eligibility; `run`, `_delete`, `expire_touched_identity`; global 20-batch/5,000 IDs-per-batch budget, category priority and capacity stop. No changes to NI-02B, NI-04, Fingerprint, Portal/Auth, Suricata or Omada.

## 2. Normative algorithm (R3 — B=ON / sensitive ONLY)

Let `K=5000`, `age=cutoff[14]`. Only for `kind=='sensitive' and repo.config.retention_indexed_v1_enabled`:

**First raw time-index branch**, SQL shape exactly:

```sql
SELECT observation_id,event_at,ingested_at,sensitive_endpoint_presence_state
FROM network_metadata_observations
WHERE event_at < ?
ORDER BY event_at,observation_id
LIMIT 5000;
```

Create a cursor, **iterate lazily**, inspecting at most K returned raw rows, without an upfront `fetchall()` and without a `state!='expired'` SQL predicate. For **every visited row, including a prospective expired row**, first verify:

- Full canonical `observation_id`, using the same UUID-version validation as current PR #210.
- Canonical `event_at`, `ingested_at` via current date validation; validated timestamp for this branch is **strictly less** than the cutoff.
- Presence state is one of existing valid states (`observed_retained`, `not_observed`, `expired`); malformed/NULL/contradictory data never counts as verified expired.
- For identity repeated across branches, exact canonical timestamps **and state** agree; otherwise fail closed as corruption.

**First verified `expired` row** is the *only* condition authorizing fallback. Immediately stop iterating and **close cursor**, discard all candidate state, **do not start or continue second lookahead**, then execute the unchanged original legacy sensitive selector **exactly once**:

```sql
SELECT observation_id
FROM network_metadata_observations
WHERE (event_at<? OR ingested_at<?)
  AND sensitive_endpoint_presence_state!='expired'
ORDER BY observation_id
LIMIT 5000;
```

Pass identical cutoff twice. Validate the full canonical IDs returned by this legacy SELECT; do not change its SQL predicate, parameters, limit, ordering or query semantics. **Return in legacy `observation_id` order** (Chief Architect expressly approved this one R2 departure). Do not re-sort its output oldest-first, do not claim first 5,000 IDs match R2 global oldest, and do not run fallback twice in one `_select()` call.

If the first branch ends without encountering expired, **close first cursor before opening the second**:

```sql
SELECT observation_id,event_at,ingested_at,sensitive_endpoint_presence_state
FROM network_metadata_observations
WHERE ingested_at < ?
ORDER BY ingested_at,observation_id
LIMIT 5000;
```

Stream and validate as above. On first verified `expired` in branch two: close this cursor, discard indexed candidates, execute that same legacy sensitive SELECT once. There must never be two simultaneously open indexed cursors.

If **neither** branch sees verified expired: combine at most `2K` raw results, deduplicate by full canonical ID, reject mismatched duplicate `(event_at,ingested_at,state)` tuples, return at most K candidates sorted by `(min(event_at,ingested_at), observation_id)` (same R2 global-oldest fast path). `not_observed` is *eligible* like `observed_retained` under existing `state!='expired'` predicate; neither triggers fallback.

**Cursor safety:** use an unconditional and reviewable close/finally lifecycle on each stream (normal EOF, first expired, validation fault, SQLite exception, interrupt/early exit); close the active cursor *before* running legacy SQL. Do not put fallback in `except`, and do not leave dangling cursors during return. The fallback cursor also closes on success/error. SQLite iteration interruption or query error must never get silently transformed into an empty result or a fallback.

**Error semantics:** invalid visited ID/time/state or inconsistent duplicate → existing `NetworkMetadataStorageCorrupt` behavior; SQLite execute/step/fallback query error → existing `NetworkMetadataStorageUnavailable`; no checkpoint modifications, fake `retention_completed`, or skipped capacity checks. Use controlled exceptions consistent with current PR #210. This R3 selector does **not** assert complete inspection of unvisited fallback rows' timestamps or an unbounded integrity scan.

**Other paths frozen:** for `B=ON / core`, preserve current PR #210 R2 SQL, validation, candidate handling and global-oldest behavior. For `B=OFF`, both kinds continue the **literal** legacy path. Other five retention classes, `run`, `_delete`, `expire_touched_identity` remain unchanged in AST/behavior. Four A/B combinations remain independent. B=ON configuration digest stays precisely PR #210's meaning; OFF digest unchanged.

## 3. Mandatory Coder focused QA — ALL cases after the final source edit

Do all work **only in disposable WSL/native-Linux Lab** against file-backed fixtures (exact existing V1 schema and FKs for integration/perf fixtures). No production probes, production database clones with sensitive information, load generators on live hosts, or full central project gate by Coder.

**F1 Fast-path correctness:** empty, 1, 5,000, 5,001, 20,000 eligible observations and `OR` source timestamps; strict 14-day boundary, ties, crossover/disjoint/overlap, different `event_at` vs `ingested_at` orders. If no visited expired, results **exactly** global oldest K. B=OFF and B=ON core semantics unchanged.

**F2 Fallback and cursor discipline:** expired in first/middle/last positions **0 / 2499 / 4999** for **both** `event_at` and `ingested_at` streams; assert genuine lazy stop on first verified expired, cursor closed on every exit; when first stream hits expired, second never executes; exactly one literal legacy sensitive SQL invocation; same selected IDs **and same order** as B=OFF for identical fixture. `not_observed`/`observed_retained` do not trigger fallback. For expired located after the first K raw rows, do **not** trigger fallback based on unseen data.

**F3 Negative/fail-closed:** malformed ID/version, noncanonical or contradictory timestamps, invalid/NULL presence state, duplicate identity with inconsistent timestamps/state, SQLite failures in opening/iterating both indexed cursors and in legacy fallback, iterator interruption. Errors must propagate as controlled corruption/unavailable; no fake `[]`/success, unintended data mutation, moved checkpoint, incorrect retention success telemetry, or leaked cursor. No fallback on errors or capacity stop.

**F4 Exact V1 integration and safety:** 100,000 expired-prefix + 5,001 eligible tail with real V1 DDL/FKs and file-backed WAL; selection parity to original B=OFF legacy **when fallback is triggered**, repeated stable passes prove eventual eligible-set cleanup, bounded 20 global transactions × at most 5000 rows per batch, 14/30/45/90-day rules, rollback/fault/replay, `PRAGMA foreign_key_check`, materialized read snapshots/capacity guards, A/B independence. Preserve existing R2 assertions that remain valid.

**F5 Mandatory reconciliation of earlier passing tests:** **revisit and update** at minimum `test_b_strict_boundaries_mixed_presence_and_future` and `test_b_explain_actual_queries_and_expired_heavy_prefix`: R3 legitimately changes query counts and fallback sort order. Do not mask failures with unconditional skipping/xfail or relax assertions unrelated to approved R3. After final code/tests correction run **all B-focused tests**, not only newly added or failing cases. Also execute `tests/network_metadata/test_config.py` in read-only mode (including A/B flags/digests) and relevant focused crash/retention/compatibility tests. The earlier **61 B PASS** and **1549 NI PASS** certify only the old SHA and **cannot** substitute for retesting new SHA. Keep Coder test scope focused, not full project suite.

## 4. Adversarial performance gate: account for WHOLE cost

Record **actual executed SQL shapes** (trace) and `EXPLAIN QUERY PLAN` on exact V1 schema/indexes. Both raw indexed branches must use existing `idx_nm_observations_event` / `idx_nm_observations_ingested` range lookups in accepted baseline conditions, without temp sorting or scanning observation PK as main path.

Compare on **identical file-backed fixtures**:

1. Baseline **B=OFF legacy**.
2. Old **R2 PR #210** unguarded sensitive algorithm (from exact starting commit; do not alter current history).
3. New **R3 guarded** sensitive algorithm.

At least: all-eligible/no-expired, interleaved states, 100k expired-prefix with 5001 eligible tail; retain exact other bounds and compare fresh/warm cache with method disclosed. Capture time distribution, candidate eligibility/parity, inspected raw rows for branch 1 and 2, use and position of early exit, count of legacy fallback SQL executions, and **VM step counts separately** for each raw lookahead **and the entire fallback legacy SELECT**, plus combined per-selection/per-pass cost. **Do not report “B fixed” from bounded lookahead alone.** If physical read bytes/ops measured in lab, identify instrument and limitations. SQL VM steps and short warm-cache timings are **not** HDD IOPS.

If material regression persists relative to B=OFF in expired-heavy representative cases, explicitly report `B_ACTIVATION_HOLD` and `MERGE_HOLD_PERF_REVIEW` for Tech Lead/Chief Architect; do **not** add an index, modify schema, or claim full solution. Independently performed expanded regression, comparative performance/security, release qualification and any production decision belong to Tech Lead, **on the NEW SHA/TREE**.

## 5. Change discipline and PR handoff

- Before edit: verify `main`/candidate baseline, current branch/worktree, tree, clean status. Before push: fetch/verify identities and scope. Any baseline drift → STOP and provide exact diff; do not self-reconcile.
- Ensure `app/network_metadata/config.py`, `models.py`, `schema.py`, `repository.py`, `service.py` untouched; compare AST/hashes of protected `run`, `_delete`, `expire_touched_identity`, B=ON core and B=OFF selector against exact pre-R3 PR #210.
- Tests: record commands, counts, failures, re-runs and exact environment/SQLite/Python versions; preserve first failure evidence, fix without changing unrelated test behavior. `git diff --check` and syntax checks PASS.
- Make **one follow-up commit** in `task/perf-io-ni01-b`; normal push only to update **existing PR #210**. If any unanticipated merge conflict, STOP.
- Update PR body/handoff with old and new candidate HEAD/TREE and parent, three-file change scope, R3 rationale, full focused results, SQL trace/EXPLAIN, **full fallback cost**, outstanding risks and explicit `B_IMPLEMENTATION`, `B_ACTIVATION` dispositions. **No CI PASS** claim without actual CI evidence.
- STOP on any requirement for schema, index, migration, new flag, modified durability, broader code scope, new data store, or altered deletion/checkpoint/replay semantics.

## 6. Authorization and gates

```text
ARCHITECT_R3=RATIFIED_WITH_CLARIFICATIONS
CODER=GO_FOR_R3_FOLLOWUP_IN_PR210_ONLY
PR210=DRAFT_UNMERGED
MERGE=HOLD_PENDING_TECHLEAD_NEW_SHA_ACCEPTANCE_AND_OWNER
DEPLOY=NO
PRODUCTION_B_ACTIVATION=HOLD
PRODUCTION_A=ON_UNCHANGED
CODER_TEST_LOCATION=LAB_ONLY
CODER_TEST_SCOPE=ALL_B_FOCUSED_PLUS_TARGETED_COMPATIBILITY
TECHLEAD_INDEPENDENT_REGRESSION_PERFORMANCE_SECURITY=REQUIRED_ON_NEW_SHA
OWNER_MERGE_AND_PRODUCTION_AUTHORITY=RETAINED
```

**Acceptance does not authorize merge or production.** Return the updated PR #210 URL, follow-up commit SHA/TREE, exact test/performance evidence, and HOLD/GO observations for independent Tech Lead review. Until then **do not** merge and **do not** activate B.
