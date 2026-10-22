# QIO-05 P2 — synchronous atomic existing-list enqueue

**LAB ONLY — HOLD for independent Tech Lead review. Not publication/deployment acceptance.**

## Implementation and frozen boundaries

Base: `cd83c3e04233593126d247b0c96c1135f4233072`, tree `86a2e005b2d250b9580f1e76a80b380d1d69a635`. Fetch verified origin/main at that identity; no relevant source drift. Repository origin is `ZaurNavi/CaptivePortal`.

Private branch/worktree: `task/qio-05-p2-sync-existing-list`, `/home/zaur_navi/captivportal-lab/worktrees/qio05-p2-sync-existing-list`. Separate clean baseline: `/home/zaur_navi/captivportal-lab/worktrees/qio05-p2-sync-baseline`. Neither is an Owner feature worktree. No commits created; implementation worktree intentionally DIRTY/uncommitted; real index unstaged. Exact candidate TREE/patch size/SHA256 and changed blob identities are in `candidate-identity.json` and `FINAL-IDENTITY-AND-RESULTS.md`.

Exactly three changed files:

- `app/device_fingerprint_sensor/spool.py`: 3 additions / 1 deletion; no other production file changed.
- `tests/device_fingerprint_sensor/test_spool.py`: focused new tests/helpers; existing assertions preserved.
- `tests/device_fingerprint_sensor/test_runtime.py`: ordered health/empty dedup/failure-boundary tests only; existing assertions preserved.

Normal `enqueue` materializes/validates its already supplied list as before. A local boolean records whether that list has >=2 elements; after unchanged purge/filter/capacity work, nonempty proposed rows use the existing `_insert_coalesced_rows()` explicit BEGIN IMMEDIATE → INSERT OR IGNORE loop → COMMIT → memo update implementation. This helper is synchronous despite its historical name. It does not create/enable an IngressCoalescer. Capturing list cardinality before stale filtering also makes a >=2 input with one remaining fresh event explicit; an all-stale/empty proposal still returns0 without an insert transaction.

Single-element calls remain on the previous immediate durable path. No wait for another call, no timer, new worker, pending acceptance, schema or persistent state. Ordinary health and up-to100 input are not restricted to coalescer evidence-only/32-row/262144-byte admission. Existing `atomic_coalesced=True` constraints and transaction/fault path remain unchanged. Capacity, TTL, drop policy, source IDs, queue ordering, busy_timeout=500 and DELETE/FULL remain unchanged.

Source links:

- [Candidate spool boundary](//wsl.localhost/Ubuntu-22.04/home/zaur_navi/captivportal-lab/worktrees/qio05-p2-sync-existing-list/app/device_fingerprint_sensor/spool.py:113)
- [Existing synchronous atomic helper](//wsl.localhost/Ubuntu-22.04/home/zaur_navi/captivportal-lab/worktrees/qio05-p2-sync-existing-list/app/device_fingerprint_sensor/spool.py:160)
- [Focused spool tests](//wsl.localhost/Ubuntu-22.04/home/zaur_navi/captivportal-lab/worktrees/qio05-p2-sync-existing-list/tests/device_fingerprint_sensor/test_spool.py:111)
- [Runtime health/barrier tests](//wsl.localhost/Ubuntu-22.04/home/zaur_navi/captivportal-lab/worktrees/qio05-p2-sync-existing-list/tests/device_fingerprint_sensor/test_runtime.py:273)

`candidate-identity.json` proves identical Git blobs/trees for ingress_coalescer, runtime, models, config, the entire receiver Evidence subtree and NI-02A subtree. No NI-02A recorder/cadence or runtime ordering change. Coalescer stays default OFF; this task never enables its flag or constructs it. Actual production flags/loaded SHA are not inspected or asserted.

## Focused verification / T01–T10 mapping

Linux: **97 PASS / 0 FAIL / 0 SKIP**, 4.29s. Native Windows: **97 PASS / 0 FAIL / 0 SKIP**, 9.96s. All97 exact test IDs match across platforms. `focused-test-ids.json` holds the per-platform inventory; JUnit and full logs are supplied. No skip/xfail/deselection added; no existing assertion weakened. Exact per-scenario IDs start with `test_QIO05_`.

| Requirement | Evidence |
|---|---|
| T01 empty/single/2/4/8/32/100, health2/4, max101 | `existing_list_transaction_and_durable_order`; PRAGMAs, SQL BEGIN/COMMIT, durable row sequence after reopen; stale-filter and ordinary size-cap tests |
| T02 four mixed/duplicate lists, both gates | `mixed_duplicate_lists_and_autoincrement_semantics`; exact rows/order/counts after reopen; unchanged ignored-ID AUTOINCREMENT candidate consumption |
| T03 second/last insert fault, both endpoints/gates | `real_sqlite_abort_has_zero_proposed_survivors`; real BEFORE INSERT trigger RAISE(ABORT), real IntegrityError, zero proposed survivors, no memo notifications, allocator unchanged and later retry succeeds |
| T04 BEGIN BUSY / failure | Real second SQLite connection takes write lock immediately before actual BEGIN; timeout/failure is propagated, no active transaction; separately injected RuntimeError |
| T04 mid-transaction error / FULL / interruption | Real trigger abort, real SQLite max_page_count FULL, injected KeyboardInterrupt after prefix; rollback state checked after real reopen |
| T04 COMMIT error | Actual SQLite authorizer denies COMMIT after two INSERTs; genuine DatabaseError and rollback verified. IOERR and rollback-IOERR are explicitly simulated, not real hardware failures |
| T04 rollback failure discard | Test-only proxy raises rollback error while actual transaction is live; underlying real SQLite connection is closed, spool.connection=None, reopen has no proposed rows |
| T05 durable completion / lost response | Independent reader sees all4 rows before memo callback/return; reopen+retry inserts0; subprocess os._exit(73) after commit without close/consumer response leaves all3 IDs exactly once |
| T06 evidence-before-health | Real SensorRuntime `_submit`/`_submit_health`, real spool and SourceHealthTracker, no worker/capture/service started; durable evidence precedes four health rows, empty dedup causes no SQL, failed submission has no durable success/health |
| T07 earlier housekeeping survives | Separate stale purge and capacity eviction fixtures verify independent earlier commits survive proposed insertion rollback; stale/eviction counts preserved; health rows are protected and capacity returns0 without false insertion |
| T08 immediate single | Repeated singles visible to independent reader on each return; atomic helper is forbidden by test seam for single calls. Runtime threads empty, ingress=None; frozen source proves no NI-02A change |
| T09 A/B/B/A measurement | `execution-ledger.json`, raw traces, `aggregate.csv/.json`, per-op rows/bytes/allocator, phase SQL/syscall counts, first/warm untraced latency; performance summary in `FINAL-IDENTITY-AND-RESULTS.md` |
| T10 platform/static | Both focused JUnit logs, compileall/py_compile log, diff-check, exact allowlist, isolated-index tree, baseline apply-check + candidate reverse-apply-check |

Focused command on each platform (full resolved interpreter/temp/output paths in manifest):

```text
python -m pytest -q -rs -p no:cacheprovider
  tests/device_fingerprint_sensor/test_spool.py
  tests/device_fingerprint_sensor/test_runtime.py
  tests/device_fingerprint_sensor/test_producer.py
  --basetemp=<new external disposable path> --junitxml=<external path>
```

`test_producer.py` was executed unchanged for immediate ACK/retry compatibility; it was not edited. Original producer/TLS/transport behavior is not reimplemented. All credentials/session objects used by these focused tests are synthetic.

One development run before final test preparation had86 PASS/2 FAIL: disabling SQLite authorizer with `set_authorizer(None)` in Python3.10 left later verification unauthorized. The new test was corrected to an explicit allow-all authorizer for verification and strengthened to assert actual COMMIT denial after both INSERT attempts. That was a test harness issue, not a production change. Original development log/JUnit are retained; final97-case inventories above are not merged with the earlier run or represented as first-attempt green.

## Counterexample / consumer review

Production call sites in the Sensor subtree are exactly runtime.py `_submit` and `_submit_health` and the two direct/guarded calls inside ingress_coalescer.py. Runtime input loops propagate failed submissions into their existing fault path; they do not inspect a successfully committed prefix from a failed call. No current caller dependency on partial proposed-row survival was found. The coalescer is rejected for activation and is not used by this implementation/measurement. Its ordinary fallback naturally uses the new ordinary list boundary, without editing that module or relaxing guarded admission.

Real SQLite trigger fault probes explicitly show the known baseline defect: second/last failure can leave1/2 proposed survivors; candidate leaves0. This is an intentional all-or-nothing correction admitted by Architecture A6, **not byte-equivalence on failed calls**. `fault-evidence.json` and raw traces retain the distinction. Existing rows remain; successful enqueue identities, FIFO row order, returned counts and SQLite sequence semantics are compared exactly baseline/candidate after every call and after reopen.

Housekeeping precedes the insertion transaction and is **not** claimed atomic with proposed rows. Error invalidates the stale memo to UNKNOWN; proposed insertion timestamps are noted only after COMMIT. A successful COMMIT followed by a lost response can have durable rows despite caller uncertainty; replay remains idempotent. No false rollback of an already completed COMMIT is promised.

## Measurement protocol / I/O layers

Both arms use real unchanged initialization/configuration and ordinary `enqueue`; the only source delta is the accepted list transaction branch. Neither arm passes `atomic_coalesced=True`. Synthetic event factory and Clock are the unchanged existing test helpers; documents are `{"id": i}` with fixed event IDs/UTC time. Thus the benchmark is intentionally a controlled minimal normalized document, not the real production payload-size distribution.

Per workload/gate: ABBA ABBA, four independent baseline and four candidate processes. Workloads: evidence1/2/8/32/100, health4, mixed8, duplicate8; each process makes four calls. Gates false/true both covered. Separate untraced latency arm and SQL+strace arm; no concurrent test/benchmark workloads. Fresh process/DB does **not** imply cold OS cache; no cache drop, venv/dependency installation or service mutation. First/warm latency, all repetitions and ranges retained; no bad sample is excluded.

Linux disposable DB is on WSL2 ext4 over the laptop NVMe SSD. Real repository settings: journal_mode=DELETE, synchronous=FULL(2), busy_timeout500, page_size4096, original schema1; normal fixture budgets10MB total/5MB main/1000 rows. These are synthetic nonbinding budgets; production budgets are not modified or inferred. Full, bounded and fault fixtures are separate from normal measurement arms.

Trace filter: `strace -ff -yy -ttt -s 128 -e trace=pwrite64,write,fdatasync,fsync,unlink,unlinkat,ftruncate`. Counts use returned bytes and exact main/rollback-journal paths, with parent-directory sync separately attributed and included in total sync counts. SETUP (initialize/seed), ENQUEUE, VERIFY, CLOSE and REOPEN_VERIFY are separate. SETUP includes the seed for mixed/duplicate workloads; it is not labelled pure bootstrap cost there. There is no WAL checkpoint phase in DELETE mode; CLOSE is reported separately, no manual checkpoint is introduced. Journal unlink counts are not HDD operations. SQL callback enumerates **explicit statements**, not internal SQLite autocommit transactions; zero explicit BEGIN/COMMIT in baseline does not mean zero commits. Fault-trigger callbacks can repeat the parent statement; do not infer INSERT attempts or durable counts from those repeated callback entries. Durability/file-syscall evidence makes the distinction. SQL instrumentation/strace is absent from reported call-latency samples.

The first aggregation counted file-only syncs; final root aggregates also include directory fdatasync from the same immutable raw traces. The superseded intermediate aggregation is retained under `analysis-v1-file-only/`, explicitly not the final total. No workload, source, raw run or latency sample was changed/repeated to make this accounting correction.

All normal-case proposed fields/IDs/order/returned counts/SQLite AUTOINCREMENT state and durable DB length are paired exactly before/after each call and after reopen, not just a row count. Fault probes have independent outcome expectations. Raw synthetic-only SQLite DBs remain in the task data root; hashes/paths are indexed. Traces, results and SQL are supplied in the handoff bundle.

## Limitations and independent gates

- Real disk/power loss, kernel EIO/fsync failure, host crash and storage-controller failure were not induced. IOERR/rollback error are labelled safe test-only simulations; COMMIT authorization denial, trigger errors, max_page_count FULL, actual lock contention and abrupt process exit are genuine scoped SQLite/process tests, not proof of arbitrary hardware faults.
- Exact production multirow submission frequency/payload distribution and matching per-file SQLite write bytes are unknown. Real singleton traffic is not expected to gain grouped I/O savings; no cross-call accumulation is permitted.
- Grouped-list improvement must not be represented as a gain from enabling the rejected pre-durable coalescer. Synthetic2/8/100 and health cases avoid a claim resting only on32-row input, but production benefit still requires independent evidence.
- Linux/Windows focused results are Coder development evidence. **Tech Lead independent full Windows/Linux/security/performance acceptance: NOT YET RUN.** No Project/Central full gate was executed or claimed.
- `PRODUCTION_PHYSICAL_HDD_SAVINGS_BOUND=NOT_QUANTIFIABLE`. No SysAdmin remeasurement or production access requested/performed. Guest cgroup I/O, SQLite syscall bytes and physical HDD IOPS are not interchangeable.

## Transport, provenance and rollback

`QIO05-P2-replacement.patch` is the full three-file unified binary-capable diff. SHA256/size/candidate tree are frozen in identity/manifest; baseline apply-check and candidate reverse-apply-check do not modify either checkout. Candidate tree uses a private external Git index; real index and HEAD remain unchanged. `SHA256SUMS.txt` covers final artifact content. Detailed Linux/Windows environment/source hashes and exact test/trace commands are provided. The Owner's prior QIO05 P0 archive and worktrees were not changed.

No rollout performed or needed for LAB-only work. To reject this candidate, retain the patch/evidence and leave production untouched; do not reset shared/Owner worktrees. Disposable synthetic DB/temp/pycache directories are enumerated in manifest and retained for review, not deleted. Any future publication, deployment, service restart or cleanup needs its own authorization.

```ini
ARCHITECTURE_PRE_DURABLE_BUFFER=REJECTED
ARCHITECTURE_SYNC_EXISTING_LIST=A6_RESEARCH_ADMITTED
CODER_LAB_IMPLEMENTATION=COMPLETE
TECH_LEAD_INDEPENDENT_FULL_TESTS=NOT_YET_RUN
PRODUCTION_HDD_SAVINGS=NOT_QUANTIFIABLE
COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO
FINAL=HOLD_FOR_TECH_LEAD_INDEPENDENT_REVIEW
```
