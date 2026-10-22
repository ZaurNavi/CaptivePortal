# QIO-05 LAB P0 — Fingerprint ingest write-cost research

## Итог и границы

**LAB RESEARCH COMPLETE / TECH LEAD REVIEW. IMPLEMENTATION NOT AUTHORIZED.**

Неизменённый receiver уже использует одну SQLite transaction на batch. На всех 16 измеренных duplicate-only запросах каждого из evidence/health workloads: 100 immutable lookups + 1 watermark SELECT, BEGIN IMMEDIATE, COMMIT, **0 INSERT, 0 UPDATE, 0 DB/WAL pwrite64 bytes, 0 tracked sync syscalls**. Повторная валидация и SELECT/CPU/telemetry при этом остаются. Нулевые syscall bytes не означают отсутствие всех затрат, операций с shared-memory/read marks или физического host I/O.

Положительные вставки действительно создают WAL pages. Отдельный checkpoint при закрытии writer сбрасывает накопленные ранее изменения. Его нельзя приписывать последнему duplicate-only request. Контрольный duplicate workload после seed close/reopen не имеет ни request writes, ни финального checkpoint writes.

Production Evidence/Sensor cgroup writes подтверждены предоставленным SysAdmin FINAL; причинное отнесение этих writes к конкретным SQLite файлам/ingest batches не установлено.

```ini
PRODUCTION_SAVINGS_UPPER_BOUND=NOT_QUANTIFIABLE
PRODUCTION_PHYSICAL_HDD_SAVINGS_BOUND=NOT_QUANTIFIABLE
MISSING_MATCHED_DATA_IS_COMPLETION_BLOCKER=NO
APPLICATION_CODE_CHANGED=NO
DURABILITY_CHANGED=NO
COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACCESS_OR_ACTION=NO
```

## 1. Source / environment identity

- Private detached clean worktree: `/home/zaur_navi/captivportal-lab/worktrees/qio05-lab-p0`.
- Pinned audit HEAD: `516abc7f56cb9c60a0e450af109334f4949b3da9`.
- Pinned TREE: `6e6f00bf6a30978eef5f08ceaf335cc839dcbb52`.
- Current origin/main observed: `cd83c3e04233593126d247b0c96c1135f4233072`; tree `86a2e005b2d250b9580f1e76a80b380d1d69a635`.
- Difference pinned→main for `app/device_fingerprint` and `tests/device_fingerprint`: empty. No inference of the SHA actually loaded in production.
- Linux: WSL2 Ubuntu 22.04, Python 3.10.12, SQLite 3.37.2, ext4 `/dev/sdd`, existing separate Lab venv. Windows: native Python 3.10.11, SQLite 3.40.1, existing Preview venv.
- Host storage: SK hynix BC511 NVMe **SSD**, not production HDD. WSL filesystem/block caching and host VHDX are additional layers.
- Python binary hashes, SQLite compile options, packages, source origins, sys.path, source hashes: `environment.json`, `linux-provenance.json`, `windows-provenance.json`. Both platform source inventories agree byte-for-byte.
- All application/test source remains untouched; empty `application-no-edit.patch`, clean status, diff-check PASS. Other feature worktrees untouched.

## 2. Method and exact fixtures

`probe.py`, `run_matrix.py`, `analyze.py`, `collect_provenance.py` are **external LAB scripts**, not product changes. `execution.json` records all 112 exact commands, order, epoch timestamps, wall times and return codes. Each sample has a new process and new file-backed DB under `/home/zaur_navi/captivportal-lab/qio05-disposable-matrix-v1/`. No background maintenance thread/server is started. Real Flask test client runs authentication/JSON validation/service/repository/telemetry without sockets. A process audit hook denies connect/bind/name resolution.

Two arms are **the same implementation under fixture workloads**, not baseline vs optimized source. For positive vs duplicate evidence and health: ABBA BAAB per arm, 4 fresh processes per workload. Other workloads: 4 consecutive fresh-process repetitions. 14 workloads × 4 repetitions × 2 arms = 112 successful processes; 200 measured operations per arm (400 total). Each process normally performs 4 requests/passes; capacity and boundary-retention perform 1 operation. No parallel test/benchmark workload during measurement. No samples excluded.

Untraced arm has no SQL callback or strace. Timing uses monotonic `perf_counter_ns` around synthetic request serialization/Flask dispatch/real validation+SQLite+telemetry, not TLS/network or full process startup. First request and subsequent warm-connection requests are reported separately. Fresh process does **not** mean cold host page cache; no cache drop or physical-disk benchmark was attempted. Small-sample timing is descriptive, not a proven speedup.

Traced arm: real sqlite connections with SQL trace callback (in-memory external wrapper, no SQL rewriting), and `strace -ff -yy -ttt -s 256 -e trace=pwrite64,write,fdatasync,fsync,ftruncate,unlink,unlinkat`. Raw synthetic traces retained. Phase markers separate SETUP, MEASURE, VERIFY, CLOSE, REOPEN_VERIFY. Verification queries and final reopen are excluded from request SQL/I/O totals. SQL counts are executed statements/attempts, not inferred commits; failed INSERT attempts remain visible. Trace and callback overhead is excluded from reported latency.

DB/WAL/shm syscall counts use returned byte counts and exact file descriptors. `stderr` telemetry is reported separately. WAL page payload writes (4096 bytes) and bytes including frame headers are in the ledger. This is **not** file-attributed kernel writeback or physical HDD measurement. Shared-memory mmap stores/read marks and page-cache writeback are not quantified by pwrite64; absence of traced writes does not establish absence of all memory/lock work. Checkpoint inference is limited to observed main-file writes + sync on close/restart; there is no manual `wal_checkpoint`, VACUUM or autocheckpoint manipulation. Workloads do not establish behaviour after crossing 1000 WAL pages, under concurrent readers, real process power loss, production TLS, or real production maintenance cadence.

Fixtures derive from unchanged `tests/device_fingerprint` factories with disposable namespace:

- N=100; evidence body 44,544 bytes; normal payload `{"vendor_class":"qio05-disposable"}`. Each batch fits configured 65,536-byte request / 8,192-byte payload limits.
- Producer `qio05-synthetic`, capture `qio05-lab`, Site `000000000000000000000001`, locally administered synthetic MAC `02:00:00:00:00:01`, documentation IP `192.0.2.1`, test-only bearer. No production clients/payloads/credentials.
- Deterministic UUIDv4-form source IDs and fixed clock `2026-09-14T12:00:00.000Z`. Replays have identical request-byte SHA256. Generated DB row/generation UUIDs remain real random values, validated within each sample; cross-sample database byte equality is neither expected nor claimed.
- Actual selected repository settings: WAL / synchronous=NORMAL(1) / wal_autocheckpoint=1000 / page_size=4096 / journal_size_limit=67,108,864 / foreign_keys=ON / busy_timeout=500ms. No durability overrides. NORMAL describes this pinned repository, not an independently verified production-loaded configuration.
- Normal cap uses existing factory 64MiB; capacity-only negative fixture uses 128KiB (32 pages), large enough for schema but too small for 100 inserts. It does not represent production capacity or an optimization. An initial **harness preparation** attempt with 64KiB was rejected during schema/cap initialization; preserved `smoke-matrix.log` records it. It is not included in formal measurements. All formal capacity samples use 128KiB.
- Retention uses real `repository.cleanup(now=fixed_clock, evidence_retention_days=30)`; health adds existing 600-second margin. Runtime's wall-clock background maintenance is not substituted/monkeypatched. Idle safety check runs real bounded health validation + capacity + `/health`.

## 3. LAB results

Per measured request/pass; ranges retain all repetitions. SQLite bytes are **syscall bytes**, not physical media bytes. Close bytes are per fresh-process CLOSE phase; see seed caveat below. Detailed per-op ledger and min/max ranges for every SQL/syscall counter: `aggregate.json`, `aggregate.csv`, `operation-ledger.json`, `results/*.syscalls.json`.

| Workload | BEGIN / SELECT / INSERT / UPDATE / COMMIT / ROLLBACK | WAL bytes | Request DB bytes | Close DB bytes |
|---|---|---:|---:|---:|
| evidence new ×100 | 1 / 101 / 100 / 1 / 1 / 0 | 127720–251320 | 0 | 393216–401408 |
| evidence duplicate ×100 | 1 / 101 / 0 / 0 / 1 / 0 | 0 | 0 | 159744 |
| evidence duplicate after seed reopen | 1 / 101 / 0 / 0 / 1 / 0 | 0 | 0 | 0 |
| evidence mixed 50 new + 50 duplicate | 1 / 101 / 50 / 1 / 1 / 0 | 123600–193640 | 0 | 315392–319488 |
| health new ×100 | 1 / 101 / 100 / 1 / 1 / 0 | 98880–185400 | 0 | 307200–311296 |
| health duplicate ×100 | 1 / 101 / 0 / 0 / 1 / 0 | 0 | 0 | 135168 |
| evidence immutable conflict at final event | 1 / 101 / 0 / 0 / 0 / 1 | 0 | 0 | 159744 |
| health immutable conflict at final event | 1 / 101 / 0 / 0 / 0 / 1 | 0 | 0 | 135168 |
| schema validation error | 0 / 0 / 0 / 0 / 0 / 0 | 0 | 0 | 69632 |
| capacity rollback | 1 / 101 / 70 attempted / 0 / 0 / 1 | 0 | 0 | 69632 |
| idle cleanup | 2 / 0 / 0 / 0 / 2 / 0; 2 DELETE statements | 0 | 0 | 225280 |
| bounded idle health/capacity/API check | 0 / 5 / 0 / 0 / 0 / 0 (+PRAGMA) | 0 | 0 | 69632 |
| retention: 50 old evidence + 50 old health deleted | 2 / 0 / 0 / 0 / 2 / 0; 2 DELETE statements | 197760 | 0 | 225280 |
| close + reopen + duplicate retry | 1 / 110 / 0 / 0 / 1 / 0 (+startup PRAGMA) | 0 | 0–159744 | 0 |

No tracked DB/WAL sync calls in the normal request/pass measurements. Restart workload has 0–1 WAL fdatasync and 0–1 DB fdatasync per operation; first restart flushes seed, later restarts are clean. CLOSE phase syncs are separately retained. Bytes in positive CLOSE rows amortize four requests, not one. Duplicate/conflict/idle CLOSE writes flush **schema/seed changes**; final-retention CLOSE also includes a separately labelled verification insert. Do not compare CLOSE totals without accounting for different seed/final-verification fixtures.

All expected authoritative values match **every field** of evidence/health records (canonical payload, hash, normalized MAC, scope, times, sequence), plus full singleton generation/watermark. Generated row IDs remain stable across retry/reopen. Every run executes integrity_check and verifies exact final state after real close/reinitialize; read-only snapshot watermark agrees with durable allocator.

- New evidence/health: 400 rows, allocator 400. Mixed: seed100 + 4×50 new = 300 rows, allocator300.
- Duplicate: seed100 unchanged, allocator100. HTTP200; exact byte-identical request replays.
- Conflict: HTTP409, no new rows, same full authoritative state/watermark100; all 99 prospective new values rolled back/not inserted.
- Invalid payload: HTTP400 before DB transaction; rows/allocator0.
- Capacity: HTTP503 storage_limit after 70 INSERT attempts; zero retained rows/allocator0, runtime unavailable, real reopen verifies durability. No false success or manual state recovery inside measured operation.
- Idle cleanup: zero deletions, two real no-op DELETE transactions; unchanged seeded rows/watermark200. Bounded health: no DML.
- Retention: strict `<` cutoffs remove50+50, keep exact-boundary50+50, allocator stays200. Old replay is rejected as stale. Separate verification insert gets201; final durable counts51 evidence/50 health.
- Restart retry: existing generated IDs/order/generation/allocator100 preserved.

Observed evidence WAL write amplification is approximately 2.87–5.64× the **whole serialized 100-event request** (not payload-only), before checkpoint/main-file writes. Mixed writes are not proportional to inserted row count: B-tree/index page churn, random generated row IDs and DB growth matter. This is fixture-specific local syscall amplification, not an estimate of HDD IOPS or a hypothetical implementation benefit. Positive inserts and immutable/durable identity accounting are mandatory work.

Untraced median / p95 milliseconds: evidence new19.299/28.002; duplicate16.444/31.462; reopened duplicate14.758/24.902; mixed38.641/121.057; health new13.138/15.982; duplicate9.384/10.994. Full ranges and cold-first/warm medians are retained. Outliers are not excluded; this small host-cache-sensitive dataset is not a comparative performance acceptance claim.

## 4. Focused correctness evidence

Both platforms ran unchanged:

```text
python -m pytest -q -rs -p no:cacheprovider
  tests/device_fingerprint/test_repository.py
  tests/device_fingerprint/test_service.py
  tests/device_fingerprint/test_api.py
  --basetemp=<external disposable path> --junitxml=<external artifact>
```

- Linux: **128 PASS / 0 FAIL / 0 SKIP**, 4.04s.
- Native Windows: **128 PASS / 0 FAIL / 0 SKIP**, 9.30s. No Windows strace claimed. Same imported source bytes via UNC; per-platform interpreter/source origins recorded.
- JUnit/logs: `linux-focused.xml/.log`, `windows-focused.xml/.log`; exact IDs in `focused-test-inventory.json`.
- External research scripts py_compile: PASS. Git diff-check: PASS. No full Project/Central Gate executed.
- Existing negative correctness tests may deliberately use special fixture PRAGMAs; those tests are separate from the measured DB arms and do not change the invariant settings above.

## 5. Production evidence reconciliation — existing SysAdmin FINAL, no repeat collection

Source: `QIO-01J-SYSADMIN-FINAL-FULL-ATTRIBUTION-2026-10-16(2).md`, copied unchanged as `SYSADMIN-FINAL-source.md`, SHA256 `b98fa9a59fa980cb82e4926ea23e5d0dd4d4f9d6faa8ed64ae8f35008f94f5ac`. Earlier filename without `(2)` is byte-identical. These are accepted SysAdmin aggregates, **not Coder remeasurements**. `production-evidence.json` contains the windowed transcription.

Historical W1/W2 (§§3.2–3.3), 21:56–22:00 AZST: evidence positive-completed24, all-duplicate-completed6, extra duplicate messages6, source-health positive5, HTTP POST20035. Six all-duplicate outcomes constitute 20% of the **30 evidence-completed messages**, not 20% of ingest bytes, file writes or physical IOPS. Pairing all HTTP requests to exact transactions/batch sizes is not established. The extra six duplicate messages total1866 MESSAGE bytes; their removal is not authorized and consumer semantics remain unreviewed. Existing receiver emits completed plus duplicate event even though duplicate DB mutations are zero.

| Confirmed layer (SysAdmin) | LIVE1 /120s | LIVE2 /120s |
|---|---:|---:|
| Evidence guest cgroup wios | 6750 | 1254 |
| Sensor guest cgroup wios | 2691 | 650 |
| journald guest cgroup wios | 754 | 1209 |
| guest vda completed write IOPS | 111.50 | 72.26 |
| host physical sda write IOPS | 127.39 | 88.74 |
| host physical await ms | 110.54 | 75.50 |

LIVE1 = 19:53:30–19:55:30 UTC, LIVE2 = 19:55:30–19:57:30 UTC (§§4.1–4.3). Use guest device252:0 only, never add layered253:0. Live Evidence journal counts62/26 do not supply a complete batch-size/distribution/file-I/O ledger. Historical outcomes above are from **different windows**; no historical outcome ratio is applied to live writes.

Separate QEMU cross-check (§4.4), 19:58:34.965–19:59:19.966 UTC (~45s): Ubuntu parent3257 writes/30183424 bytes (72.38 IOPS), Windows204 writes, host journald217, physical sda3943 writes (87.62 IOPS). This confirms a large Ubuntu VM contribution in that later window; it is not an additive partition of LIVE1/LIVE2 or a map from individual receiver transactions to disk operations.

Evidence/Sensor direct cgroup writes are not journald MESSAGE bytes. Cgroup block requests, guest completed requests, QEMU/qcow2, host filesystem cache/journal and physical disk operations are distinct accounting layers. Sensor spool I/O is outside this receiver-only lab experiment. File-attributed SQLite write bytes and complete ingest-transaction sizes/frequency in matching production windows are **not measured**. Source loaded in production was not independently checked by Coder. Do not infer that all 6750 Evidence writes are duplicates, journald or SQLite commits.

## 6. Opportunity and decision boundary

1. **Duplicate DB mutation opportunity in this LAB: zero observed DB/WAL syscall bytes to remove.** The source already avoids INSERT/watermark UPDATE. Treat eliminating 100-row duplicate inserts as a falsified premise for this pinned implementation.
2. Duplicate requests still do 101 SELECTs, validation/hash, transaction/lock acquisition and two structured telemetry emits. Avoiding some of that would be a CPU/logging/lock hypothesis, not proven disk savings; exact immutable conflict detection and freshness/security semantics cannot be weakened.
3. Positive and mixed requests create real persistent pages/index updates; source already batches the request in one transaction. Checkpoint timing must be understood separately. Neither cross-request grouping nor changing SQLite synchronization is recommended or authorized here.
4. Transaction-level production opportunity needs matching file attribution and batch distribution. Historical event counts give a bounded count of observed messages/outcomes only. No numerical production write/physical-HDD savings upper bound can be derived from the provided aggregates.
5. **No new measurement request is blocking this completed research.** Tech Lead may combine the SysAdmin matching report when available and select a separate falsifiable implementation task/architecture review.

## 7. Reproducibility, artifacts, retention and cleanup scope

`manifest.json` links frozen source/environment, commands, fixtures, correctness results and explicit nonclaims. `SHA256SUMS.txt` covers all final deliverables except itself/checksum verifier output. `results/` holds all112 JSON results plus56 phase syscall ledgers. Raw56 strace process files and corresponding logs retained. Aggregate tables are immutable snapshots; reruns require new disposable output paths, not overwriting this evidence.

Replay a probe command from `execution.json` with a **fresh external `--out` path**; preserve source HEAD, interpreter and PRAGMAs. Run the full serial ABBA schedule only into a fresh artifact/data namespace. Do not reuse measured DBs as new samples. No package or global environment changes were made. Script source hashes and data-file hashes are retained.

Rollback is unnecessary: no application/configuration/service change exists. All new data are disposable synthetic task SQLite files, external script outputs and external pycache/focused-test temp dirs. They are retained for Tech Lead review; **nothing was deleted**, no logs cleared, no other task files touched. If later cleanup is requested, restrict it to the exact QIO05 roots enumerated in the manifest; preserve accepted evidence first. No action on production is implied.

**STOP: LAB handoff only. Further implementation/durability decisions require separate Tech Lead GO.**
