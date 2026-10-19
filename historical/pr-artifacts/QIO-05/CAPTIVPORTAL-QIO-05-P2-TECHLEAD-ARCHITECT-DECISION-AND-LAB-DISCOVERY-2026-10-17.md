# CaptivPortal — QIO-05 P2: Tech Lead architecture acceptance and newly verified I/O root cause

**Date:** 2026-10-17 (Asia/Baku)  
**Owner:** Performance & Optimization Tech Lead  
**Architecture input:** `CAPTIVPORTAL-QIO-05-P1-CHIEF-ARCHITECT-SENSOR-COALESCER-DECISION-v1-2026-10-17(1).md`  
**Repository verified:** `ZaurNavi/CaptivePortal` `main@cd83c3e04233593126d247b0c96c1135f4233072` (GitHub read-only). The `SensorSpool`, `IngressCoalescer`, config, NI-02A source blobs match the older QIO-05 P0 reference `516abc7f...`. **Not a production-loaded SHA confirmation.**

## 1. Formal acceptance of architecture

**ACCEPT `ARCHITECTURE_REJECT_PRE_DURABLE_BUFFER`.** The existing `DEVICE_FINGERPRINT_SENSOR_IO_INGRESS_COALESCE_ENABLED` flag MUST NOT be turned ON. Return from `submit()` while an event is only RAM-buffered is not durable acceptance; current AF_PACKET/EVE datagram inputs have no demonstrated durable replay. Source-health, NI-02A and coverage authority must not misrepresent missing Evidence as completeness. Current SQLite `DELETE`/`FULL` durability must remain unchanged.

**Architecture A6 authorizes investigation of a distinct alternative:** synchronous, bounded transaction for the *complete list already supplied by the caller*, with the call returning only after durable completion. No inter-call deferral, timer, background queue, or new volatility. This is NOT an activation approval nor a merge/deploy approval.

## 2. Critical correction to earlier Tech Lead interpretation

The earlier statement "`SensorSpool.enqueue(list)` already persists all rows as one transaction" was **incorrect**. In `app/device_fingerprint_sensor/spool.py`, SQLite is opened with `isolation_level=None`, meaning SQLite autocommit. In `_enqueue()` the ordinary path uses `with connection:` plus per-row `execute` or `executemany`, but **does not issue `BEGIN`**. Under autocommit, the connection context manager does not implicitly make a multirow transaction: each inserted row commits separately. By contrast `_insert_coalesced_rows()` uses an explicit `BEGIN IMMEDIATE` / `COMMIT`, with rollback on error. This latter method is currently reached only via `atomic_coalesced=True` (used by the rejected pre-durable coalescer), but its direct synchronous method demonstrates the legal transaction pattern.

Hence the expensive part is not necessarily the interval in RAM; it is that the normal path can perform **multiple durable commits within one already-available multi-event list**.

## 3. Independent disposable WSL2 lab evidence

Lab source: pre-existing isolated `/home/zaur_navi/captivportal-lab/worktrees/qio05-lab-p0`; no application or production source edits. SQLite and SensorSpool settings as coded: `journal_mode=DELETE`, `synchronous=FULL`. Each comparison starts with a fresh test-only DB. Source scripts (on owner's authorized workstation):

- `C:\CaptivPortal-Lab\tmp\qio05-p2-existing-list-baseline-20261017.py`
- `C:\CaptivPortal-Lab\tmp\qio05-p2-rollback-lab-20261017.py`

Four successive calls with an **already available list of eight** immutable, synthetic Evidence events per call (`32` unique IDs total). Two alternative paths use identical events and the existing source; no cross-call buffering. `strace -f -c` syscall totals include identical fresh-DB setup/close, so are NOT isolated physical-media I/O measures or pure request-phase counts.

| Metric | Ordinary `enqueue(list)` | Explicit transaction via `atomic_coalesced=True` |
|---|---:|---:|
| Lists / records | 4 / 32 | 4 / 32 |
| `pwrite64` calls (whole subprocess) | **842** | **114** |
| `fdatasync` calls (whole subprocess) | **132** | **20** |
| `unlink` calls (whole subprocess) | **34** | **6** |
| Rows after SQLite close/reopen | 32 | 32 |
| Distinct event IDs after reopen | 32 | 32 |
| Observed SQLite settings | DELETE/FULL | DELETE/FULL |

**Failure injection:** test-only `BEFORE INSERT` trigger `RAISE(ABORT)` on the second of three synthetic rows. Ordinary `enqueue()` returns `SensorSpoolError`, yet **one row remains durably committed** after reopening. Existing explicit-transaction branch returns `SensorSpoolError`, rolls back all three proposed rows and has **zero** survivors. In both cases `connection.in_transaction=False` after the failure. This is a narrow test of proposed-row atomicity; it does not assert that housekeeping (`_purge_stale`, capacity eviction), executed before candidate insertion, will roll back with that batch.

**Do not equate these numbers to production benefit:** this is a 1× disposable test per mode and not a matched real-input histogram; most live raw TCP SYN and TLS/QUIC normalizations create zero/one event per submission. DHCP correlation can release a pre-existing bounded list (up to eight); grouped health transitions can also submit lists. The frequency of such multirow submissions in production and file-specific HDD benefit remain unmeasured. The lab compares transaction mechanisms, not a proof of production IOPS savings.

## 4. One admissible narrow candidate

**`QIO-05-P2 / SYNCHRONOUS-ATOMIC-EXISTING-LIST` — LAB IMPLEMENTATION GO ONLY.**

For an existing list containing `>=2` events supplied to the ordinary `SensorSpool.enqueue()`, execute all accepted inserts as **one explicit SQLite transaction**, with immediate durable commit before returning. Preserve max 100 rows, event ID semantics, order, `INSERT OR IGNORE`, exact reported insert count, source-health ordering, existing stale/capacity behavior, and `DELETE/FULL`. One-event handling can remain on the current immediate path; no artificial wait for another event. Handle `BEGIN/INSERT/COMMIT` errors with safe rollback and accurately signalled failure. Do not mark uncommitted events successful or update the stale memo before successful commit. Do not touch coalescer, flags, NI-02A cadence, receiver, API, security or production.

The potential changed behavior for a failed `>=2` list is **all-or-nothing proposed inserts instead of partially surviving committed inserts**. Architecture A6 permits a synchronous batch with precise fault/retry semantics, but any hidden consumer dependency on partial survivors is a STOP, not a unilateral assumption.

## 5. Gates and status

- `ARCHITECTURE_PRE_DURABLE_COALESCER = REJECTED`; `COALESCER_FLAG_ON = FORBIDDEN`.
- `ARCHITECTURE_SYNC_EXISTING_LIST = RESEARCH ADMITTED BY A6`.
- `CODER_LAB_IMPLEMENTATION = GO` **only** under separate narrow P2 TASK.
- `TECH_LEAD_FULL_WINDOWS_LINUX_PERF_REVIEW = NOT YET RUN`.
- `PRODUCTION_PHYSICAL_HDD_SAVINGS = NOT QUANTIFIABLE`; frequency of live multirow batches unknown.
- `COMMIT/PUSH/PR/MERGE/DEPLOY/PRODUCTION_ACTION = NO`.

**Follow-on:** task `TASK-QIO-05-P2-CODER-LAB-SYNCHRONOUS-ATOMIC-EXISTING-LIST-2026-10-17.md`. Independently review any implementation against the precise baseline and failure contract. Do not skip Tech Lead full gates or Owner separate publication/production decisions.
