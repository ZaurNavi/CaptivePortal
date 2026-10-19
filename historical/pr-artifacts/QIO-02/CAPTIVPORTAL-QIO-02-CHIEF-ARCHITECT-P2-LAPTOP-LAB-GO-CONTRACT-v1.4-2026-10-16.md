# CAPTIVPORTAL — QIO-02 / H1
## Chief Architect → Optimization Tech Lead: P2 Disposable Laptop Lab Admission Contract v1.4

**Date:** 2026-10-16 (Asia/Baku)  
**Decision:** **P2 DISPOSABLE LAPTOP LAB = GO (strictly scoped)**  
**Status:** Normative Architecture P2 Lab admission. **Not** a Coder TASK, source publication approval, merge GO, or production GO.  
**Incoming request:** `CAPTIVPORTAL-QIO-02-P2-LAB-ADMISSION-REQUEST-OWNER-ATTESTED-v1-2026-10-16(1).md`.  
**Predecessors:** QIO-02 Architecture Contract v1; P0/P1 v1.1; H1 Freshness v1.2; Laptop Lab v1.3.  
**Repository base for Lab comparison:** `191beda1f23f8f466d2431f42e57571815d85778`, tree `3f6d0a05c5d893d3139db44a1692c81e67fd6c6e`.  
**Newer main reported by Tech Lead (not silently included):** `516abc7f56cb9c60a0e450af109334f4949b3da9`; merged PR #215 is **outside H1**.

---

## 1. Chief Architect disposition and justification

**GO:** Permit Tech Lead to issue *one* narrow implementation TASK to Coder for **disposable, isolated laptop/WSL2 Lab only**, focused on redundant final-EOF persistence of a **stable, already-retired** Public Traffic source. The Coder may act **only upon that subsequent explicit Tech Lead TASK**; this architecture GO is not self-executing.

**Why sufficient for Lab:**

1. Owner attests no deliberate required `public_traffic.sqlite3.reader_state.updated_at` freshness consumer was configured, and accepts bounded unknown-consumer risk for Lab. First-party `get_reader_states()` does not read this timestamp; Public Traffic user-facing freshness uses a *different* `traffic_daily.updated_at`. This is **not** an assertion that every external script was inventoried, nor production compatibility acceptance.
2. P1-L0 used synthetic sources and original code on Owner laptop. Five stable retired files plus one unchanged active source produced **six final-EOF `BEGIN IMMEDIATE / UPSERT / COMMIT` paths per complete scan**, 30 redundant logical UPSERTs across five repeated scans. Their recovery tuples were unchanged; timestamps moved. The original-path traced WAL/main-file writes and syncs establish a plausible, reproducible local cost, **not** measured variant saving or production HDD benefit.
3. Further production load measurements were explicitly stopped by Owner. The SSD lab has sufficient fidelity to test **logical correctness, transaction effects and local syscall causality**, but not to quantify `/dev/sda` production impact.

**Clarification of N7 gate:** N7-pre is **satisfied for isolated Lab admission only** by the reproducible unchanged-fixture logical/syscall baseline and bounded risk. N7-post (a demonstrable **net** WAL/sync/local-I/O or latency improvement after implementation, with all correctness gates) remains **OPEN**. Production physical write-IOPS savings remain **UNPROVEN**, and no historic 3× quiet-production measurement requirement is reintroduced for the *Lab experiment*.

**No independent SysAdmin attestation required for this disposable Lab-only GO.** Such evidence and consumer compatibility must be re-assessed for any future deployment admission, with Owner as final decision maker.

---

## 2. Exact permitted H1 domain

The candidate is **not** generic no-op SQL suppression. It applies solely to the **final successful EOF** branch of `PublicTrafficReader._process_source()` for a discovered **rotated/archival** source that was already durably `retired_completed=1` and remains `retired_completed=1`.

| Scenario | H1 optional unchanged skip | Authority / action |
|---|---|---|
| Already-retired archive, complete final EOF, exact same persisted recovery tuple, reliable file validation | **MAY skip UPDATE** | No new durable progression; operational `updated_at` may remain old |
| Initial discovery / no persisted row | **FORBIDDEN** | Insert source row through legacy path |
| Active `.log` final EOF, even unchanged | **FORBIDDEN in H1 v1** | Legacy `observe_source()` remains |
| `retired_completed` transition `0→1` or `1→0` | **FORBIDDEN** | Transition must be durable |
| New appended bytes / event, including zero-traffic or duplicate | **FORBIDDEN for changed progress** | Persist event/checkpoint/offset according to legacy transaction rules |
| Incomplete trailing line, malformed record, source reset | **FORBIDDEN** | Preserve current effects and retry behavior |
| Missing/reappearing source, inode reuse, path switch, truncation, rotation, checkpoint change | **FORBIDDEN** | Legacy source-recovery actions |
| `missing_warning_emitted=1` or altered/missing/ambiguous row | **FORBIDDEN** | Legacy path or existing error handling; do not erase/overwrite warning evidence |
| Any unverified file identity, conflicting DB mutation, time-bound uncertainty | **FORBIDDEN** | Fail-closed to legacy behavior; do not fabricate success |

**`reader_state.updated_at` classification:** Operational last-row-write time, **not** a durable proof that *all* sources were successfully scanned at that instant. H1 may leave that timestamp unchanged **only** in the strict unchanged retired scenario. It must never be repurposed as a new successful-scan timestamp, nor be replaced with a fabricated heartbeat.

**Source identity caution:** `_source_identity()` uses `st_dev:st_ino`; `_source_checkpoint()` hashes the offset and **bounded prefix/tail windows**, **not the entire source file**. The implementation must not claim this digest proves whole-file immutability or establishes cross-resource atomicity. Its existing validation semantics must be preserved; the Lab comparison must establish no worse handling of same-size rewriting, missed middle-file rewrite, inode reuse, late append and rotation than baseline. An unsafe or unprovable corner case falls back to legacy persistence or HOLD.

---

## 3. Atomicity, source-generation and race contract

**A. Reader validation:** Keep the existing source discovery, file open, `fstat`, identity match, offset/checkpoint verification, per-line handling, incomplete-tail branch and EOF processing. Evaluate H1 only *after* a real complete final EOF of an already-retired source. The `scan()`-initial `get_reader_states()` object is a **hint**, never sufficient for skipping persistence.

**B. Serialized DB decision:** The definitive equality check must execute against the **current persisted row in the same existing writer-serialized `BEGIN IMMEDIATE` transaction** used by `observe_source()`. Compare **all seven effective fields**, with exact `NULL`/type treatment:

`source_identity`, `source_path`, `source_offset`, full `source_checkpoint`, `last_observed_size`, `retired_completed=1`, `missing_warning_emitted=0`.

The incoming source must independently assert valid retired complete EOF. An absent row, value change, unverified/invalid checkpoint, or unexpected concurrent state requires the **existing UPSERT**. No independent locking authority, second database, new durable heartbeat or `updated_at` comparison in the equivalence predicate.

**C. Filesystem verification:** The open file descriptor, final offset/size and discovery identity must remain consistent with the same path/generation through the bounded no-op decision. The implementation must provide a reasoned verification of `fstat(open_fd)` and current path identity (for example `stat(path)`), with the established bounded checkpoint at the relevant offset; if an append/rename/replacement or inconsistent observation is detected, H1 skips **nothing**. At the writer boundary use a bounded validation strategy that does not create a new unbounded HDD scan or excessively hold `BEGIN IMMEDIATE`. The implementation strategy (callback, explicit proof object with revalidation, or another narrow design) is Tech Lead's choice subject to the same invariant and deterministic Lab tests; do **not** authorize a mere `skip_if_preloaded_state_equal` flag.

**D. Cross-resource impossibility:** SQLite locking cannot atomically freeze an OS file being written or renamed by another process. Therefore no implementation may claim absolute FS+SQLite atomicity. For an append/replacement **after** the last successful validation, the next scan must deterministically reconcile source identity, offset/checkpoint and any new lines; failures must not advance the checkpoint past durable event processing, lose a unique event, double-count on replay, mark a new source retired without proof or assert false freshness. Require race-injection tests at the final validation/commit boundary. If this equivalence to baseline cannot be demonstrated, STOP/HOLD.

**E. Transaction end:** For a true unchanged no-op, end the transaction safely without row `UPDATE`; preserve exception/rollback, busy-timeout and connection-close semantics. **No assumption** that eliminating SQL UPSERT eliminates `BEGIN IMMEDIATE`, WAL setup, checkpoint or `fsync`: measured syscall outcome is a separate gate. The untouched fallback must remain behaviorally identical to baseline.

**F. No other owners:** Do not change `process_offline_event`, `advance_source`, `reset_source_after_truncate`, `reset_source_after_reappearance`, `mark_missing_warning_emitted`, `delete_reader_state`, processed-event idempotency, daily counters, rollover/rotation logic, startup backfill or retention; source/consumer domains outside Public Traffic remain frozen.

---

## 4. Scope and responsibilities

**Allowed source/test files, ONLY after Tech Lead TASK:**

- `app/public_traffic/reader.py`
- `app/public_traffic/repository.py`
- `tests/test_public_traffic.py`

Do not introduce environment flags, settings, schemas/migrations, new libraries, service files, deployment scripts, PR #215/SSR-01B or QIO-01D changes. Any documentation-file change needs separately explicit allowlisting by Tech Lead. No copying production DBs; use disposable, synthetic SQLite/source logs only.

**Tech Lead owns:** focused Coder TASK and file allowlist; verification of frozen base/tree; independent source/diff and full Windows/Linux, security, concurrency, crash/replay and PERF gates; rejection/return for regression; any subsequent publication readiness decision. **There is no separate mandatory organizational QA role.**

**Coder owns:** candidate implementation **only inside permitted laptop Lab workspace**, scoped tests, exact replacement patch and SHA256, test IDs and logs, candidate tree identity, rollback recipe. `commit/push/PR/merge/deploy = NO` until later explicit approvals; candidate artifacts may be delivered to Tech Lead for review.

**Revision handling:** The A/B lab may use pinned `191beda...` for reproducibility. Before source publication, Tech Lead must re-evaluate current `main` HEAD/TREE (the report notes merged PR #215), verify no hidden interaction, reconstruct the *exact* candidate against accepted target base and repeat relevant gates. A validated old-base Lab does not silently approve a future `main` deploy.

---

## 5. Mandatory correctness checks (Lab)

- **H1-C01** Stable retired `1→1`, same seven fields, identical bounded checkpoint and final complete EOF → no state-row UPDATE (transaction still opens/closes unless independently justified); no change in any recovery field; permitted older `updated_at` only.
- **H1-C02** Active source unchanged → legacy write; **H1-C03** New source/no row → insert; **H1-C04** retirement `0→1` and `1→0` → durable transition.
- **H1-C05** New line incl zero traffic; **H1-C06** duplicate and invalid lines; **H1-C07** partial line followed by completion → baseline event/idempotency/cursor equivalence.
- **H1-C08** Same-size changed checkpoint; **H1-C09** changed-middle/unchanged bounded-window adversarial fixture → disclose current checkpoint limitation, no new false invariant; **H1-C10** truncate/rewrite; **H1-C11** inode reuse and path replacement; **H1-C12** late append during/after final validation → no lost eventual processing.
- **H1-C13** missing/reappearance and warning flag; **H1-C14** concurrent repository updater/reset/delete around `BEGIN IMMEDIATE`; **H1-C15** multi-source scan where another source is incomplete/failed; **H1-C16** source rename/rotation midscan.
- **H1-C17** Crash/kill before comparison, during open transaction and immediately after transaction; **H1-C18** process restart/backfill/replay, reset and counter history invariance.
- **H1-C19** External/public API counters, traffic totals and `traffic_daily.updated_at` unchanged from baseline for identical event fixtures; idempotent event IDs and monotonic source progress preserved.
- **H1-C20** Fallback paths and error categories equivalent; no false ready/success/freshness or silent exception handling; intentional loss of repeated `reader_state.updated_at` refresh only for admitted H1-C01.

At minimum Tech Lead independently reproduces negative/race/crash cases at the exact candidate tree. Any new failing or unsupported scenario is **HOLD**, not `xfail/skip` to reach nominal PASS.

---

## 6. P2/L1 performance and non-regression gates

**Matched controlled A/B on Owner laptop**: original pinned code vs candidate, same generated fixtures, identical DB/file topology and instrumentation, interleaved ABBA/BAAB ordering, warm and cold trials, idle/burst/eventful workloads. Do not attribute WSL2 SSD results directly to production spinning HDD.

Capture, separately:

1. Recovered tuple, processed-event rowset, counter totals, source completeness and restart/replay outcome (must match baseline except authorized operational timestamp).
2. Exact method invocations, `BEGIN IMMEDIATE`, `UPSERT/UPDATE`, COMMIT/ROLLBACK counts; verify expected **five retired UPDATEs avoided per repeated six-source complete pass**, while active-source legacy remains.
3. WAL and main DB `pwrite64` calls/bytes and `fdatasync/fsync`, checkpoint/close behavior, SQLite locks/busy and error distribution; trace both arms identically.
4. Instrumented syscalls vs **separate** uninstrumented latency trials; CPU/IO where defensible; no increase in source lag, tail processing latency or contention.
5. If available, laptop physical-device metrics tagged **local SSD** only; no invented host `/dev/sda` metrics.

**Performance PASS** requires repeatable, causally attributable local WAL/main-file write or sync reduction (with local device evidence where defensible), **without** material latency/lock/contention regression, together with all correctness PASS. Latency-only improvement without evidence of fewer I/O effects is not enough to claim QIO-02 Small-I/O PASS; it can be documented as a separate finding. Merely fewer SQL statements or unchanged timestamps is **insufficient**. If the transaction opens/closes and journal mode behavior dominate such that no meaningful benefit survives, **REJECT H1 as a Small-I/O optimization**. Report magnitude and conditions, not a promised percentage.

**Production savings status remains NOT PROVEN** until a separate Owner-authorized, safe deployment and comparable measurements become possible. This GO does not grant them.

---

## 7. STOP / rollback / escalation

STOP and return to Chief Architect/Tech Lead HOLD on: mandatory previously unknown consumer; lack of reliable per-file/source generation confirmation; stale preloaded state used for skip; advancement of source cursor without durable event; changed retirement/missing/error behavior; race-induced lost/double event; widened scope or new schema/PRAGMA; failed crash replay; loss of deterministic fallback; measurable latency regression; no local net performance benefit; files outside allowlist.

Lab rollback: discard candidate worktree/patch and return to immutable base; wipe only synthetic Lab SQLite and log fixtures, never production files. The code change introduces **no schema/data migration**, so rollback must not require durable data rewrite. Full service/data/consumer production rollback requires separate design if deployment is ever proposed.

**No further production profiling** under this admission. The prior host HDD `~92.53% busy` is a contention observation, not a signal to retest live. Cold-start read stalls remain a separate research track; QIO-01D is separate.

---

## 8. Exact machine-readable disposition

```ini
TASK=QIO-02
VARIANT=H1_STABLE_RETIRED_FINAL_EOF_ONLY
DECISION=GO
P2_DISPOSABLE_LAPTOP_LAB=GO
OWNER_ATTESTATION=ACCEPTED_FOR_LAB_SCOPE
EXTERNAL_CONSUMER_GRAPH=BOUNDED_RESIDUAL_RISK_FOR_LAB
SYSADMIN_ATTESTATION=NOT_REQUIRED_FOR_ISOLATED_LAB
P1_L0_EVIDENCE=SUFFICIENT_FOR_LAB_ADMISSION
N7_PRE=SATISFIED_FOR_LAB_FEASIBILITY_ONLY
N7_POST=OPEN
HOST_PRODUCTION_HDD_BENEFIT=UNPROVEN
BASE_SHA=191beda1f23f8f466d2431f42e57571815d85778
BASE_TREE=3f6d0a05c5d893d3139db44a1692c81e67fd6c6e
CURRENT_MAIN_OBSERVED_IN_REQUEST=516abc7f56cb9c60a0e450af109334f4949b3da9
TECHLEAD_CODER_TASK=REQUIRED_SEPARATELY
CODER=HOLD_UNTIL_TECHLEAD_TASK
CODER_SCOPE=ISOLATED_LAPTOP_LAB_ONLY
GITHUB_COMMIT_PUSH_PR=NO
OWNER_MERGE_GO=NO
OWNER_PRODUCTION_GO=NO
PRODUCTION_MUTATION=NO
PRODUCTION_PROFILING=NO
QIO_01D=SEPARATE
PR_215_SSR_01B=OUT_OF_SCOPE
COLD_START_READ=SEPARATE_TRACK
```

**Chief Architect conclusion:** P2 Lab may proceed. The burden now shifts to controlled implementation and falsifiable Lab evidence, not more stressful production observation. Architecture GO ends at the laptop boundary; all downstream gates remain separate.
