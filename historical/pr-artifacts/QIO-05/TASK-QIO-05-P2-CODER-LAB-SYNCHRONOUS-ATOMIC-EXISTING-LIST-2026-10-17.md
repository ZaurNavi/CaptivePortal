# TASK-QIO-05-P2 — Coder LAB: synchronous atomic commit for already-available SensorSpool lists

**Task ID:** `TASK-QIO-05-P2-CODER-LAB-SYNCHRONOUS-ATOMIC-EXISTING-LIST`  
**Version/date:** v1 / 2026-10-17  
**Issued by:** Performance & Optimization Tech Lead  
**Scope:** LAB-only small-I/O correctness/performance candidate, **not** permission to publish or deploy.  
**Source baseline:** verify repository `ZaurNavi/CaptivePortal` and current `origin/main`; last verified at issuance `cd83c3e04233593126d247b0c96c1135f4233072`. Do not assume `origin/main` still matches. Pin recorded SHA + tree, compare source before implementing; STOP if relevant source changed.

## 0. Architecture approval scope

Chief Architect decision `QIO-05 P1 Sensor IngressCoalescer Durability Decision v1` **REJECTS** pre-durable volatile queue activation. **Never enable** `DEVICE_FINGERPRINT_SENSOR_IO_INGRESS_COALESCE_ENABLED`. A6 **permits** separate synchronous bounded transaction of a list already available when caller invokes `SensorSpool.enqueue`; successful return must remain after durable SQLite commit. No cross-call buffering or timer. `SensorSpool` stays on `DELETE` journal + `synchronous=FULL`; authoritative NI-02A cadence and contracts are frozen.

Tech Lead independently observed in current `app/device_fingerprint_sensor/spool.py`:

- `sqlite3.connect(..., isolation_level=None)`.
- Ordinary path uses `with connection:` / `executemany` or per-row `execute` **without `BEGIN`**, so each successful INSERT may auto-commit.
- Existing `atomic_coalesced=True` path explicitly `BEGIN IMMEDIATE` → inserts → `COMMIT`, and rolls back on failure.
- On four lists of eight synthetic events, ordinary vs atomic: `pwrite64 842→114`, `fdatasync 132→20`, `unlink 34→6`, with 32/32 unique rows verified after reopen. Syscall totals include startup/close and are a single WSL2 SSD comparison, **not HDD proof**.
- Injected failure on second of three rows: ordinary path leaves one committed survivor, explicit atomic path leaves zero proposed rows.

## 1. Narrow implementation contract

**Goal:** a list of events **already passed together** into ordinary `SensorSpool.enqueue()` with `len(values)>=2` must be inserted within a single **explicit, synchronous SQLite transaction**: `BEGIN IMMEDIATE`, bounded work, `COMMIT` before return; rollback on error, fail closed. A single-event call may retain the existing immediate durable path. Preserve an empty-call no-op. Max 100 rows remains unchanged.

Do not introduce a new collection window or wait across calls, even 1ms. Avoid a new thread, in-memory pending acceptance, changed `SensorRuntime` ordering, or deferred success. Do **not** use this TASK to turn on the old coalescer. Keep `atomic_coalesced=True` existing guarded compatibility path intact; its extra constraints (evidence-only, <=32, size cap) must not leak into the ordinary path (which supports health and up to100).

**Durability/fault invariants:**

1. `DELETE`/`FULL`/`busy_timeout`/capacity budget/retention limits unchanged. No `PRAGMA` relaxation, WAL switch, schema migration, new persistent file, altered event identity or source-health generation.
2. `INSERT OR IGNORE` semantics preserved; duplicate IDs are no-ops; accurate existing returned count and on-disk event sequence/order on success. Deterministic FIFO for already-listed events, no upstream `_submit`/NI-02A reordering.
3. For candidate multirow inserts, all proposed rows commit or none commit on failure before COMMIT. No `success` return before COMMIT. For successful commit followed by lost consumer response, retry with same IDs remains idempotent.
4. On `BEGIN`, INSERT, or COMMIT error, close/rollback safely as appropriate. No dangling live transaction, falsely successful telemetry, false durable acknowledgement, or incorrectly advanced in-memory stale memo. Inject genuine SQLite failures in disposable DBs.
5. Preserve **pre-existing housekeeping semantics**: stale purge, capacity eviction and capacity/fault accounting can happen before the proposed insertion transaction. Do not falsely assert those earlier independent commits roll back together with candidate rows. Avoid broadening scope to this housekeeping.
6. Preserve `io_stale_purge_gate_enabled=true/false` paths and correct memo updates only after successful insert transaction. Preserve `source_health` immediate durable barrier semantics, including already formed lists and empty deduplicated health events.
7. Existing `atomic_coalesced=True` path must not regress; existing feature flags/config unchanged, default OFF unchanged.

## 2. File allowlist / forbidden scope

**Allowlist:**
- `app/device_fingerprint_sensor/spool.py`
- `tests/device_fingerprint_sensor/test_spool.py`
- `tests/device_fingerprint_sensor/test_runtime.py` **only if needed for ordered health/barrier coverage**
- `tests/device_fingerprint_sensor/test_producer.py` **only if needed to verify restart/ACK idempotence**

No other source/test file may be edited without Tech Lead review. Forbidden: `app/device_fingerprint_sensor/ingress_coalescer.py`, `config.py`, `models.py`, `runtime.py`, NI-02A repository/recorder/cadence, receiver Evidence repository/API, auth, TLS, release/deploy/systemd/env, Grafana, prod DB and any production host. This task does not permit modifications to tests outside allowlist, `skip/xfail`, assertion weakening or deleting coverage.

Use a **new isolated LAB worktree**, not the owner's current worktrees. No access to production, no mutation of host/VM services, no external network traffic or secret material.

## 3. Required focused tests and evidence

Coder owns only **focused tests**, static/diff checks and reproducible LAB traces. Tech Lead owns the independent full Windows/Linux/security/performance gates.

- T01: existing empty list; one event; 2/4/8/32/100 already-available Evidence rows; source-health 2/4; ordinary path behaves as one explicit transaction for >=2. Max 101 stays rejected.
- T02: four event lists with mixed duplicate and fresh IDs; exact rows, IDs, durable sequence/order, returned counts, `INSERT OR IGNORE` and pure duplicate-only; both memo-gate settings.
- T03: test-only injected failure at 2nd/last INSERT inside multirow group; 0 proposed survivors after close/reopen; no stale memo drift, correct fault and no open transaction.
- T04: `BEGIN IMMEDIATE` BUSY/failure, mid-transaction DB error, SQLite commit error/IOERR simulation, rollback-failure connection discard, and no misleading result. Use safe injection in a disposable DB; where realistic fault simulation is impossible, label unproven rather than faking.
- T05: successful COMMIT followed by simulated lost acknowledgement / process termination before response; same event IDs retry, preserve only one durable copy.
- T06: source-health ordering: Evidence event(s) durable before dependent health status; empty dedup health unchanged, no path through rejected volatile coalescer.
- T07: stale purge/eviction/capacity precede insert, preserve original budgets/drop policy; test pre-existing housekeeping may survive a later batch insertion failure while proposed new rows do not.
- T08: repeated `single` input remains immediate; no group waiting, no background thread, no change in NI-02A coverage cadence or settings.
- T09: compare exact baseline vs candidate on disposable same input; A/B/B/A repeated with phase-separated syscall counts for `pwrite64`, `fdatasync`, `unlink`, SQL BEGIN/INSERT/COMMIT and durable DB bytes. Separate startup, candidate insert, shutdown and checkpoint phases. Include request latency (first/warm, medians and ranges). No inference of physical HDD IOPS from WSL2 SSD.
- T10: Linux and Windows scoped tests for allowed modules; compileall, `git diff --check`, clean reproducible diff, no skips added. Do **not** run/claim main full gate on behalf of Tech Lead.

**Critical falsifiability:** If ordinary `enqueue()` has a hidden contractual consumer relying on partial commit of rows from one failed call, or the revised code cannot preserve fault/retry/health semantics, STOP and return the failing counterexample; do not broaden the task or unilaterally rewrite the architecture. If source changed materially on new `main`, STOP and seek re-baselining. An apparent performance win that exists only with artificial 32-row input must be labelled; real multirow rate on production is still unknown.

## 4. Coder handoff

Return a frozen **LAB ONLY** bundle with base commit/tree, exact file allowlist, changed blob hashes, candidate tree or reproducible patch, SHA256SUMS, all focused JUnit/logs, unique test IDs, synthetic failure traces, A/B performance ledger, counterexample analysis and explicit I/O-layer limitations. Include source-code links and exact rerun commands. Do not touch the Owner's QIO-05 P0 archive or other worktrees. Keep code changes isolated.

Final decision flags:

```ini
ARCHITECTURE_PRE_DURABLE_BUFFER=REJECTED
ARCHITECTURE_SYNC_EXISTING_LIST=A6_RESEARCH_ADMITTED
CODER_LAB_IMPLEMENTATION=GO
CODER_FOCUSED_TESTS=REQUIRED
TECH_LEAD_INDEPENDENT_FULL_TESTS=NOT_YET_RUN
PRODUCTION_HDD_SAVINGS=NOT_QUANTIFIABLE
PR_MERGE_DEPLOY=NO
COMMIT=NO
PUSH=NO
PRODUCTION_ACTION=NO
```

**Return to Tech Lead for independent review.** Even accepted LAB implementation does not imply PR authorization or Owner production GO.
