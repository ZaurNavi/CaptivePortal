# CAPTIVPORTAL — QIO-02 / P2 / H1
## Tech Lead → Coder: Stable Retired Source Final-EOF No-op — Disposable Laptop Lab TASK v1.0

**Issued:** 2026-10-16 (Asia/Baku)  
**Authority:** Chief Architect P2 Lab GO v1.4 (`CAPTIVPORTAL-QIO-02-CHIEF-ARCHITECT-P2-LAPTOP-LAB-GO-CONTRACT-v1.4-2026-10-16.md`); Owner's bounded consumer-risk attestation for Lab.  
**TASK status:** **ISSUED — CODER MAY IMPLEMENT IN ISOLATED LAPTOP LAB ONLY.** This document is the separate Tech Lead TASK required by the architecture contract. It is **not** approval for publication, merge, service restart, deployment, or production profiling.  
**Task ID:** `TASK-QIO-02-P2-H1-LAB-01`.  
**Variant:** `H1_STABLE_RETIRED_FINAL_EOF_ONLY`.

### 1. Frozen baseline and isolation

- Baseline Git commit **`191beda1f23f8f466d2431f42e57571815d85778`**, tree **`3f6d0a05c5d893d3139db44a1692c81e67fd6c6e`**. Coder must verify both and a clean checkout before any edits.
- The Owner's laptop: Windows 10 / WSL2 Ubuntu 22.04. Development must occur **only in the dedicated disposable P2 candidate checkout**, never in production or other shared working trees. Use synthetic journals and new disposable SQLite only; do **not** copy the production database, logs, identifiers, secrets or visitor records.
- The newer GitHub `main@516abc7f56cb9c60a0e450af109334f4949b3da9` (merged unrelated SSR-01B PR #215) is explicitly **not** the test baseline; do not merge/cherry-pick/rebase it into this experiment. Before any future publication Tech Lead, not Coder, will reconcile the newer target tree.
- L0 control evidence established that a repeated unchanged 6-source scan (5 retired + 1 active) performs 6 final-EOF `BEGIN IMMEDIATE / UPSERT / COMMIT`, with all six recovery tuples unchanged and `updated_at` refreshed. L0 is *baseline evidence*, not variant savings.

### 2. Exactly permitted modifications

**Only:**

1. `app/public_traffic/reader.py`
2. `app/public_traffic/repository.py`
3. `tests/test_public_traffic.py`

No changes to any other file inside the candidate Git worktree; no new settings/env flags, database schema or migrations, logging subsystem, new libraries, general batching, startup backfill, source rotation strategy, or SQLite `PRAGMA`/durability settings. No changes to Visit Lifecycle, Registry, Current State, Omada Observations, QIO-01D or SSR-01B.

**NO commit, push, PR, merge, production service action or deploy.** Source patch and report are local handoff artifacts outside the repository; Tech Lead controls acceptance.

### 3. Required function and state behavior

**Problem:** `PublicTrafficReader._process_source()` calls `repository.observe_source()` after every full final EOF. For a retired `.log.N` file already persisted as `retired_completed=1`, its complete, verified EOF can repeat without any new processing. `observe_source()` currently unconditionally performs `_upsert_reader_state()` after `BEGIN IMMEDIATE`, changing only the operational `reader_state.updated_at`. The field is **not** full-scan success proof, and Owner confirmed no deliberately configured required external consumer; unknown external readers remain a documented residual risk for Lab only.

**Target:** Suppress the **state-row UPDATE/UPSERT only** if and only if all below are true:

- This call originates in the **final successful complete EOF branch**, not from incomplete trailing line, reset, migration, an arbitrary other call to `observe_source()` or the active `.log` source.
- The source is a discovered archive (`source.is_active=False`), was **already persisted** as `retired_completed=1`, and still needs to remain `1` (`1→1`). A `0→1` or `1→0` transition is *never* skippable.
- The opened file and current path are validated consistently: same `st_dev:st_ino` source identity/generation relative to discovery/open and final no-op check; final offset still at real EOF; file size consistent with the proposed durable tuple; bounded checkpoint recomputed/verified as in existing reader semantics; check for replace/rename/append/change while validating. Prefer bounded `fstat(open_fd)` + `stat(path)` + checkpoint checks; no full-file hash scan under a database write lock. Include failure/fallback for unverifiable file identity/size/path/checkpoint. Preserve the existing limitation that checkpoint covers only bounded prefix/tail windows, **not** the whole source.
- The **definitive equality comparison is performed inside `PublicTrafficRepository.observe_source()`'s existing `BEGIN IMMEDIATE` writer-serialized transaction**, reading the *current* database row after acquiring the writer lock. It must compare all seven effective persisted fields, preserving exact `NULL` semantics and full digest: `source_identity`, `source_path`, `source_offset`, `source_checkpoint`, `last_observed_size`, `retired_completed=1`, `missing_warning_emitted=0`. The timestamp `updated_at` is not part of equivalence.
- The current row exists, no relevant field differs, no missing-warning flag, and the bounded file verification succeeds **at this decision boundary**. The early `scan()` `get_reader_states()` result may gate *eligibility to attempt a check* but must **never** alone authorize a no-op.

**Recommended narrow design (not permission to relax the requirements):**

- In `reader.py`, only at a complete final EOF of an eligible already-retired archive, pass an explicitly named optional validator/callback/proof to `repository.observe_source()`. It must retain access to the *open stream* until transaction-time validation and be callable at the persistence decision boundary. Any other `observe_source()` invocation, including `reset_source_after_truncate()`, and the incomplete-tail call must retain the legacy default behavior.
- In `repository.py`, retain `BEGIN IMMEDIATE`, busy-timeout, transaction/error/connection lifecycle. If an eligible proof is supplied, fetch the row *under that lock*, compare all seven fields (no preloaded-only check), call the bounded source validator **while lock is still held**, and only then close a true no-op transaction without modifying `reader_state`. For absent/changed/ambiguous state, validator failure, or source race: invoke the **existing** `_upsert_reader_state()` code path. Do not change the shared `_upsert_reader_state()` function globally.
- A filesystem append/replacement **after** the final validation cannot be prevented atomically with a SQLite lock. Preserve next-scan reconciliation and normal event durability; never claim global cross-resource atomicity. When race behavior cannot be proven equivalent to legacy, return HOLD.
- Return value, error categories, side effects and the `traffic_daily` API payload must remain identical to baseline except that an admitted unchanged archive may retain its old `reader_state.updated_at`.

**Explicit non-goals:** Do not bypass `BEGIN IMMEDIATE` as part of this H1 variant; do not skip the active source; do not avoid checkpoint validation; do not change the semantics of `process_offline_event`, `advance_source`, `reset_source_after_truncate`, `reset_source_after_reappearance`, `mark_missing_warning_emitted`, `delete_reader_state`, administrative counter resets, processed-event deduplication, any startup/backfill/retention behavior.

### 4. Coder scoped correctness tests: H1-C01–C20

Write deterministic tests **only** to `tests/test_public_traffic.py`, using `tmp_path`, synthetic input and newly created SQLite files. Instrument SQL via connection callback / targeted spying, and inject races/barriers deterministically rather than hoping a race will occur under timing-based sleeps.

| ID | Mandatory focused assertion |
|---|---|
| C01 | Already-retired archive `1→1`, seven fields identical, real verified EOF: no UPSERT/UPDATE, no modified recovery fields; only permitted timestamp difference vs baseline. |
| C02 | Unchanged active `.log`: legacy UPDATE/UPSERT persists. |
| C03 | Newly discovered source/no row: legacy durable INSERT. |
| C04 | `0→1` and `1→0` retirement transitions: durable, not optimized away. |
| C05 | Appended new line, including zero-traffic event: durable cursor/checkpoint/event handling. |
| C06 | Duplicate and invalid target/non-target lines: existing idempotency and advancement. |
| C07 | Incomplete tail and its later completion: incomplete branch never optimized; no premature progress. |
| C08 | Same-size rewrite affecting bounded checkpoint: mismatch/legacy recovery remains. |
| C09 | Adversarial rewrite only in *middle* beyond checkpoint prefix/tail windows: document bounded-hash blind spot; no claim of full-file validation; H1 must not worsen baseline. |
| C10 | Truncation/rewrite: reset and retry semantics unchanged. |
| C11 | Inode reuse or path replacement: source generation validation, safe fallback. |
| C12 | Late append before, during, and after final validation: eventual processing and checkpoint correctness (do not assume FS+DB atomicity). |
| C13 | Missing archive/active source, reappearance and persisted `missing_warning_emitted` transitions: no incorrect skip. |
| C14 | Concurrent SQLite updater/reset/delete between preloaded scan state and writer transaction; serialize under `BEGIN IMMEDIATE`; no stale-state skip. |
| C15 | One archive reaches EOF while another source in the overall scan is incomplete/fails: do not invent global complete scan. |
| C16 | Rename/rotation during scan and around final validation: safe fallback. |
| C17 | Kill/crash before comparison, during open transaction, immediately after transaction: replay/rollback correct. |
| C18 | Restart/backfill/replay; reset and history invariance. |
| C19 | `traffic_daily`, `processed_events`, completed sessions, API counters and `traffic_daily.updated_at` match baseline for same fixture. |
| C20 | Exceptions, lock/busy handling, warning/error/readiness/freshness outcomes equal baseline; only allowed timestamp change for C01. |

Do not mark untested or failed negative/race/crash cases as PASS or hide them with `xfail/skip`. Return BLOCKER/HOLD with exact reproduction instead.

### 5. Coder performance evidence (focused only)

For the exact six-source synthetic fixture (5 stable retired + 1 unchanged active):

- Record baseline vs candidate on identical input: **expected 5 avoided retired UPSERTs per repeated complete scan**, active source still takes legacy path. Exactly how many `BEGIN IMMEDIATE`, COMMIT/ROLLBACK, WAL writes, syncs and main-file operations remain is **to be measured**, not assumed.
- Collect focused SQL traces and, when supported, local `strace -ff -yy` WAL/main SQLite `pwrite64` bytes/counts, `fdatasync/fsync`, WAL close/checkpoint effects; label storage **WSL2 on laptop SSD**, not physical production HDD.
- Run a compact reproducible A/B with same fixtures (warm/cold, idle and eventful) and at least one counterbalanced `ABBA`/`BAAB` sequence. Separate traced syscall runs from untraced wall-time runs. Do not simulate a busy production host, benchmark Omada, or access `/opt/CaptivePortal` on production.
- If suppressing SQL UPSERT does **not** yield a reproducible **net local I/O benefit** (e.g. connection-level journal setup/checkpoint dominates), state this candidly. Tech Lead, not Coder, decides independent PERF gate and rejection/acceptance. No physical `/dev/sda` benefit claim.

### 6. Coder handoff to Tech Lead (required)

Deliver outside the repo:

1. **Code patch** (`git diff --binary`) touching only the three allowlisted files, plus SHA256 of the exact patch and SHA256 for every modified file; `git status --porcelain` and before/after frozen identity. No committed/pushed objects, no PR.
2. **Focused test report**, command lines, output, explicit per-ID C01–C20 PASS / FAIL / NOT_EXECUTED and reason; highlight concurrency and crash injection reproducibility.
3. **Correctness/state comparison** from identical original/variant fixtures, including exact durable fields, event rowset, counters and controlled timestamp exception.
4. **SQL and local syscall evidence** (trace command, sqlite3/python/WSL versions, hardware/media, observations, sample counts, traced vs untraced distinction, no extrapolation).
5. **Implementation explanation** identifying definitive serialized equality point and file validation/checkpoint strategy, race residuals, fallback conditions and expected rollback.
6. **Candidate source identity and rollback**: frozen base SHA/tree, diff+file hashes, clean recipe (discard candidate checkout and synthetic fixture data only); no global config or migration.

**Coder completion label:** `IMPLEMENTED_IN_ISOLATED_LAB / FOCUSED_TESTS_ONLY / AWAITING_TECHLEAD_INDEPENDENT_GATES`. The Coder must never label project-level `PASS`, publish changes or deploy.

### 7. Independent Tech Lead acceptance (not delegated to Coder)

Upon candidate handoff: Tech Lead independently reviews all line-level changes and tests; reruns full Linux + Windows gates, adversarial file/concurrency/kill-replay/security tests, and matched A/B physical-file syscall/performance gates on laptop; validates no changes outside allowlist and no regressions. No independent organization QA role is required. If N7-post doesn't show net I/O benefit, **REJECT/HOLD** even if SQL statement count drops. Current production HDD physical benefit remains `UNPROVEN` until a separately authorized deployment and safe comparison.

### 8. Status and stops

```ini
TASK=TASK-QIO-02-P2-H1-LAB-01
ARCHITECT_CONTRACT=v1.4
ARCHITECT_P2_LAB_GO=YES
TECHLEAD_TASK=ISSUED
CODER=GO_ISOLATED_LAPTOP_ONLY
BASE_SHA=191beda1f23f8f466d2431f42e57571815d85778
BASE_TREE=3f6d0a05c5d893d3139db44a1692c81e67fd6c6e
VARIANT=H1_STABLE_RETIRED_FINAL_EOF_ONLY
ALLOWED_FILES=app/public_traffic/reader.py,app/public_traffic/repository.py,tests/test_public_traffic.py
SYNTHETIC_DATA_ONLY=YES
GITHUB_COMMIT_PUSH_PR=NO
PRODUCTION_MUTATION=NO
PRODUCTION_PROFILING=NO
FULL_QA_OWNER=TECHLEAD
MERGE_GO=NO
DEPLOY_GO=NO
```

STOP and report immediately if source identity cannot be validated reliably, a stale snapshot can cause a skipped required writer update, any cursor/event data is lost or duplicated, observed behavior differs outside the single operational timestamp exception, concurrency/crash tests regress, no measurable net local I/O benefit survives, or the implementation requires widening the allowlist/schema/SQLite durability.
