# CAPTIVPORTAL — QIO-EVIDENCE-IDLE-01
## P2-LAB-01 — Exact Validator Performance Prototype
### TECH LEAD → CODER RESEARCH-ONLY TASK v1.0

**Date:** 2026-10-17 (Asia/Baku)  
**Issuer:** Independent Performance & Optimization Tech Lead  
**Architect authority:** `CAPTIVPORTAL-QIO-EVIDENCE-IDLE-01-CHIEF-ARCHITECT-P1-DECISION-P2-LAB-CODER-BOUNDARY-v1.2-2026-10-17`  
**TASK:** `QIO-EVIDENCE-IDLE-01-P2-LAB-01-EXACT-VALIDATOR-PROTOTYPE`  
**Verdict:** `GO — RESEARCH-ONLY / ISOLATED DISPOSABLE LAB; NO RUNTIME CHANGE`  
**Fast-ready:** `HOLD` • **Production:** `NO` • **Merge/push/PR/commit:** `NO`  
**L0 full `PRAGMA quick_check`:** `PENDING / NOT VERIFIED` as of 2026-10-17 16:23 AZST. Do not represent it as PASS.  

### 0. Frozen source identity and pre-code gate

| Identity | Exact pinned value |
|---|---|
| Repository | `ZaurNavi/CaptivePortal` |
| BASE commit | `810484e69baa371c4696c3b46654199631538fc4` |
| BASE tree | `6816e73148c91c1e2e778613067a41d8c973c03d` |
| `app/device_fingerprint/repository.py` blob | `12710de576c3f4d887740f73354d51b1096f0a5c` |
| `app/device_fingerprint/schema.py` blob | `a99ed87aa674f064edd50eea51ab408becd48e7d` |
| `tests/device_fingerprint/test_repository.py` blob | `217ed982237b5a5761e004c72a73f4f5200dee6b` |

The base commit exists in the authorized LAB VM's Git object store; BASE tree was read-only confirmed via `git rev-parse BASE^{tree}`. The **current checkout** on `/opt/CaptivePortal` had a DIFFERENT SHA (`cd83c3e04233593126d247b0c96c1135f4233072`); it is NOT the allowed source base. The historical pinned code is also available in an existing isolated source/deploy directory. Never assume `main == pinned LAB == current checkout`.

Coder MUST independently check BASE commit, BASE tree and above source blobs before work. If any mismatch/absence: **STOP, no coding**. Create a separate disposable development worktree outside `/opt/CaptivePortal` or any running service directory; use the exact pinned BASE. Do not change `HEAD`, index, tracked files, environment or service in the operational checkout. Do not change the original Evidence DB.

### 1. Objective — one question only

**Can the exact historical `ingest_sequence` guards be evaluated with measurably less computational/physical-read cost, while producing exactly the same PASS/REJECT/error outcomes on every admitted state, including adversarial/corrupt states, without weakening deep-before-ready (T1)?**

A rigorous **negative** result (no proven cheaper equivalent) is an acceptable, useful final finding. This task does NOT create a trusted fast-ready path, does NOT modify `DeviceFingerprintRepository.initialize()`, and does NOT authorize dropping `PRAGMA quick_check`.

Current L0 metrics for comparison, *not claimed as per-statement exclusive physical I/O*:

- Original DB 3,796,074,496 bytes, 926,776 × 4096-byte pages, WAL, allocator 2,834,788.
- Full Evidence sequence guard: PASS, 148.402 seconds, process `read_bytes` +41,791,488 bytes.
- Source-health guard: PASS, 0.106 seconds; collision JOIN: PASS, 1.252 seconds.
- Full `quick_check` began 15:56:44 AZST and remained running at 16:23 AZST; result unknown. Original audit PID 500349 was in `D`/`wait_on_page_bit_common`; Evidence service inactive.
- Physical `/dev/sda` read IOPS during measured windows approximately 75–86/s and host busy ~93%; guest and host windows not perfectly synchronized; other host I/O contributors exist.

### 2. Normative code anchors / exact legacy validation

Pinned `app/device_fingerprint/repository.py`:

- `DeviceFingerprintRepository.initialize()` at lines ~66–120: calls `_validate_connection()`, then storage cap/POSIX enforcement, before publishing a connection. Do not change it.
- `_validate_connection()` at lines ~297–321: verifies exact schema version; **full `PRAGMA quick_check`** requiring the complete `['ok']` result; exact schema signature; storage state/allocator; two full `typeof(ingest_sequence)!='integer' OR ingest_sequence<1 OR ingest_sequence>? LIMIT 1` guards; cross-table equality JOIN `LIMIT 1`.
- `_validate_runtime_connection()` at lines ~324–330: metadata-only validation for normal in-process health; **NOT** an equivalent startup integrity validator.
- `_validate_storage_state()` lines ~333–342 and `_validate_schema_signature()` ~345–368 define the metadata checks.
- `app/device_fingerprint/schema.py`: schema version 2, two unique `ingest_sequence` indexes, exact constraints/signatures. SQLite CHECK and unique index presence do NOT by themselves prove historic bytes/index consistency against unauthorized external writes or corruption.

**Required semantics:** for every stored row, exact integer type and range `[1, durable_allocator]` in BOTH evidence and source-health; no duplicates within either table or across the two tables; gaps after retention valid; `MAX(retained_sequence)` need NOT equal allocator. Exact schema/index/CHECK/storage-generation validations remain required. `quick_check` is distinct from, and weaker in some respects than, `integrity_check`; do not conflate their duties. Commit + allocator atomicity, Source Health, idempotency, immutable-event conflict, and WAL/crash/replay must not regress.

**Baseline order caveat:** current `initialize()` performs `quick_check` **before** schema/sequence guards. The earlier L0 measurement ran guarded SQL first and `quick_check` last. Preserve this difference transparently when claiming actual end-to-end startup cost; warm-cache stage times from a different order are NOT a full cold startup benchmark.

### 3. Exact modification allowlist

All files below must be NEW research/test artifacts; do not alter existing files:

1. `research/qio_evidence_idle_01/__init__.py` — optional import marker, no runtime hook.
2. `research/qio_evidence_idle_01/exact_validator_prototype.py` — stand-alone research-only runner and candidate implementations; no production import or side effect.
3. `research/qio_evidence_idle_01/README.md` — replicable read-only/disposable commands, limitations and safety protocol.
4. `tests/device_fingerprint/test_qio_evidence_exact_validator.py` — focused deterministic test fixtures and assertions.

**Explicit denylist:** all `app/**` files, existing tests including `tests/device_fingerprint/test_repository.py`, other `research/**`, any systemd/env/config/migrations/requirements/SQLite paths, `run.py`, runtime feature flags, `captiv-prod`, Network Metadata, other DB/services. Any change outside allowlist ⇒ **STOP** and return to Tech Lead. No `git commit`, push, PR, merge or deploy. `git write-tree` is permitted only with a dedicated isolated index (not a shared operational index).

### 4. Implementation work packages

**WP1 — Reference baseline runner.** Pure test/research adapter with bounded, explicit CLI over a supplied **disposable fixture path** (or offline explicitly authorized clone). Use SQLite read-only connection (`mode=ro`, `query_only=ON`); read consistency via ONE pinned SQLite read transaction for all original stages; validate snapshot/WAL provenance and record failure if unable to prove a common snapshot. Preserve exact legacy SQL predicates and binder/allocator semantics; collect complete stage outcomes, including all `quick_check` rows, exceptions and SQLite primary/extended codes where available. Do not infer `PASS` from a running process, metadata checks, process counters or `quick_check(1)`.

**WP2 — Experimental candidates.** Implement separate research functions, not monkeypatches of production `initialize`. Record each candidate SQL and `EXPLAIN QUERY PLAN` plan, with VDBE steps / SQLite progress sampling where supported, wall time and process read/write-byte deltas. Comparing scan order, covering-index access, and other index-backed strategies is allowed. A MIN/MAX or bounded-probe-only candidate may exist **solely as a deliberately rejectable negative control**, never as an accepted equivalent. A proposed new index/trigger/materialized invariant must additionally prove historical backfill, every committed-write update, corruption/external-writer defenses, and extra write-I/O; otherwise classify `UNPROVEN` / `REJECT`. No original DB migration.

**WP3 — Equivalence harness.** Build deterministic valid and adversarial disposable v2 fixtures. For each, run BOTH the unmodified baseline semantics and each candidate on the **same verified fixture snapshot**, recording per-stage and whole-pipeline PASS/REJECT/typed error. A candidate has only three admissible verdicts: `EQUIVALENT_PROVEN`, `REJECTED`, `UNKNOWN`. An individual matching test suite is not a mathematical proof of all future corruption; mark untested categories explicitly. One legacy/candidate mismatch (false ACCEPT or false REJECT) ⇒ `REJECTED`, no silent normalization.

**WP4 — Performance instrumentation, not unapproved physical stress.** A research runner may collect available `/proc/self/io`, guest `/proc/diskstats`, PSI and measurement timestamps, with process/guest versus **physical host HDD** layers strictly separated. Matched host physical `/dev/sda` A/B/A, cold/warm runs on the real 3.8-GB database and any host/VM interference control are **Tech Lead's independent acceptance activities after the current L0 auditor completes and a suitable authorized window exists**. Coder must NOT run a second heavyweight full scan, clone 3.8GB onto the shared HDD, start/stop the Evidence service, change SQLite durability, or touch `omv-hp` without a separate explicit action authorization. Unmeasured actual host saving is `UNKNOWN`, never estimated from guest process bytes.

**WP5 — Focused tests on Linux and Windows.** Coder owns only unit/focused tests on small disposable fixtures, syntax/compile and diff hygiene. No fake passing fixtures, skipped/xfail cases, weakened legacy assertions or long watchdog overrides to hide a hang. Failure reporting must retain precise error type and before/after source identity.

### 5. Mandatory tests (N01–N20) and verdict semantics

| ID | Fixture / check | Mandatory proof |
|---|---|---|
| N01 | Valid empty v2 | Both pass; allocator zero and schema correct |
| N02 | Valid populated v2 incl. both families | Both pass; bounded fixture then scalable stress model |
| N03 | Valid retention gaps | Both pass without contiguity or max==allocator requirement |
| N04 | `typeof=real` despite numerically in-range | Both reject; numeric coercion not accepted |
| N05 | text/blob/NULL sequence | Reject or exact schema/SQLite failure; record injection method |
| N06 | zero/negative sequence | Both reject; no false PASS |
| N07 | sequence greater than durable allocator | Both reject |
| N08 | intra-table duplicate / broken uniqueness | Fail-closed on constructible deterministic corruption |
| N09 | cross-table sequence collision | Both reject with intact per-table uniqueness |
| N10 | altered/missing schema CHECK | Both reject exact signature mismatch |
| N11 | missing/wrong index / index-to-table discrepancy | Both reject or explicit corruption error; record mechanics |
| N12 | b-tree/freelist/record damage | Exact legacy rejection/error classification; no false clean |
| N13 | committed, not-yet-checkpointed WAL | Snapshot includes committed writes, consistent high-water |
| N14 | missing/truncated/swapped WAL | Preserve evidence; reject/unavailable or prove exact replay semantics |
| N15 | crash around event + allocator commit | Atomicity; no accepted half-transaction |
| N16 | replay/idempotent duplicate/conflict | No omitted accepted event; immutable conflict preserved |
| N17 | `BUSY`, `IOERR`, interrupted validation | Explicit typed/unavailable or ERROR, never READY |
| N18 | external writer / rollback / stale manifest | Cannot infer trust from metadata/mtime/manifest alone |
| N19 | cold/warm costs and physical HDD | Instrument design; real host matched A/B/A reserved for Tech Lead |
| N20 | both source families and consumer/readiness invariant | No ingest/serving of false historical trust |

Fixture generator may use temporary CHECK-bypass techniques **only on disposable files**, if deterministic and documented; never on original DB. For structurally impossible corruption cases, use reproducible corrupt **disposable copies** plus SQLite-defined failure evidence, not unsupported arbitrary tampering of an operational file. If a fixture cannot be produced or observed safely, explicitly report `NOT_TESTED/BLOCKED` and do not claim full equivalence. Existing source tests are unchanged.

### 6. Required safety and negative controls

**Do not implement or ship** any of: `initialize(deep_validation=False)`, env bypass, `quick_check(1)` substituted for full check, `SELECT MIN/MAX` as replacement of full type/range/collision guards, accept ingest after metadata-only, asynchronous integrity check after declaring trusted one-DB history, external trust UUID/mtime/data_version/allocator/hash-only manifest. No modification to WAL/synchronous/fsync/checkpoint/retention/reader schema. No silent delete/recreate/reindex/repair.

The candidate must fail closed on an incomplete/aborted `quick_check`, unexpected SQLite error, unknown source version, wrong storage generation or inconsistent WAL view. Preserve error categories `StorageCorrupt`, `StorageUnavailable`, `StorageLimit` where legacy semantics distinguish them. A research script must not advertise a live HTTP endpoint or change live readiness.

### 7. Coder handoff — exact deliverables

Return **one reproducible handoff** with:

1. Exact base commit + tree, changed paths (allowlist only), candidate tree from isolated index, full unified patch and its `SHA256`; zero commit/push/PR/merge/deploy.
2. Linux/Windows Python & SQLite versions; exact focused test commands and IDs; exit codes; JUnit/test report; skip/fail counts; `compileall` and `git diff --check`.
3. Baseline and every candidate: exact SQL, per-stage result/typed error, `EXPLAIN` plan, wall time, VDBE/progress steps, process/guest I/O and snapshot/WAL identity (when present). Do NOT present `read_bytes` as physical host completed reads.
4. Full N01–N20 table: fixture identity/hash, method, expected legacy behavior, observed legacy, observed candidate, match/mismatch, source of confidence, blocked/untested fields.
5. Clear conclusion: `guard_equivalence = PROVEN/REJECTED/UNKNOWN`, `deep_T1_equivalence = PROVEN/REJECTED/UNKNOWN` (NOT automatically PROVEN by sequence-only tests); `full_quick_check = PENDING/PASS/FAIL` from complete exact result only; `host_physical_HDD_savings = NOT_MEASURED` unless independently measured by Tech Lead.
6. Residual P0/P1 and exact STOP/blockers requiring Tech Lead/Architect action; no claims of faster operational ready.

### 8. Independent Tech Lead acceptance (NOT Coder scope)

Tech Lead subsequently verifies exact patch hash and reconstructs candidate tree independently; checks all frozen production paths unchanged and no unauthorized side effects; independently replays adversarial corruption/type/allocator/WAL scenarios, full Windows/Linux/root-POSIX and failure/security regressions as applicable, real `quick_check` completion, and matched host HDD A/B/A with guest/host clocks and other workloads recorded. Failed or interrupted runs are NOT PASS. Tech Lead, not Coder, decides whether any additional architecture review is needed.

**No further Coder task to alter startup readiness is authorized here.** A future fast-ready TASK requires complete L0 `quick_check` final evidence, rigorously justified T1' or separately accepted T2, negative suite and full-startup physical performance proof; policy weakening needs a new Owner risk decision and Architect contract.

### 9. STOP / GO machine-readable

```ini
ARCHITECT=v1.2
BASE_COMMIT=810484e69baa371c4696c3b46654199631538fc4
BASE_TREE=6816e73148c91c1e2e778613067a41d8c973c03d
CODER_RESEARCH_ONLY=GO
CODER_RUNTIME_IMPLEMENTATION=HOLD
LAB_DISPOSABLE_FIXTURES=GO
ORIGINAL_LAB_DB_MUTATION=NO
PARALLEL_FULL_LAB_DB_AUDIT=NO
QUICK_CHECK_FULL_L0=PENDING_UNVERIFIED
APP_DEVICE_FINGERPRINT_MODIFICATIONS=NO
COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
PRODUCTION=NO
CAPTIV_PROD=DO_NOT_TOUCH
NETWORK_METADATA=OUT_OF_SCOPE
PHYSICAL_HDD_PERFORMANCE=NOT_PROVEN
```

**Owner-facing note:** This is a bounded experiment to determine whether *exact* existing guards admit a faster equivalent—not an authorization to trade data integrity for startup speed. If evidence fails, keeping the current deep T1 gate is the correct result.
