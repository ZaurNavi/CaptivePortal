# PERF-IO-NI01-A — NI-01 ingestion hot-path optimization
## TECH LEAD IMPLEMENTATION TASK v1 — CODER

**Project:** CaptivPortal / `ZaurNavi/CaptivePortal`  
**Issued:** 2026-10-14 / Tech Lead  
**Decision:** **CODER GO — LAB IMPLEMENTATION, FOCUSED TESTS, COMMIT, PUSH, PR ONLY**  
**Priority:** P1 — reversible SQLite statement amplification reduction  
**Normative authority:** `CAPTIVPORTAL-PERF-IO-NI01-ARCHITECTURE-CONTRACT-R2-FINAL-TECHLEAD-2026-10-14.md`, §§1–3, 5–8, 10. The R2 architecture supersedes R1; R1 is dated research evidence, not runtime truth.

## 0. Verified baseline and drift admission

**Approved A implementation baseline:**

```text
REPO=ZaurNavi/CaptivePortal
BASE_HEAD=27087766d3f2e104a44da3f36aa6e72a082b12de
BASE_TREE=3fe941f1962e6df72d102ba36da60bf25f3bd70a
RESEARCH_HEAD=3b5f70cec467939995fecc7667169239000b7308
RESEARCH_TREE=5d52a536adffe55475ec9dd9d4b3e2d7ea8eeb2b
```

Tech Lead checked the research-to-implementation diff: it contains **only PR #207 / NI-05** files, none in `app/network_metadata/`. Thus the architecture's NI-01 source assumptions remain identical on approved implementation HEAD.

**Running NI-01 is an older loaded artifact, not `BASE_HEAD`:** 2026-10-14 read-only production verification found `network-metadata.service` active, PID 3690031, start 2026-10-12 22:43:19 +04; latest persisted ingest-run provenance identifies `385fecebd2bd8778c3a2034514d9e72587984753` / tree `baefd2c4fbceff51aade93d840d93fc81a88fd58`. Comparing this older commit to new `main` shows no changes in A's four implementation files, although other NI-related modules did evolve. **Do not equate checkout HEAD, process provenance and production activation.** The later controlled release requires new loaded-artifact confirmation.

Coder: create an isolated native Git worktree/feature branch from **exact** `BASE_HEAD`; verify `git rev-parse HEAD`, tree, and clean status before editing. No auto-drift/rebase. If `main` or target files drift, return exact diff to Tech Lead and HOLD.

## 1. Outcome and boundaries

Optimize the ingestion hot path **without modifying observable NI-01 behavior**. Three subchanges form **one indivisible behavior switch**:

1. A1: batch-level generation-scoped indexed identity probe in preflight **and a new independent probe within `BEGIN IMMEDIATE`**;
2. A2: validated, immutable, repository-instance insert-column allowlist, eliminating per-insert `PRAGMA table_info` only when A is ON;
3. A3: deterministic fault grouping / one UPSERT per reached group within the existing commit transaction.

**One switch only:** `NETWORK_METADATA_IO_HOTPATH_V1_ENABLED` (`true` or `false`, default/unset `false`). There must be no A1/A2/A3 partial-activation knobs. OFF preserves the exact existing legacy execution path, configuration digest and durable results.

Must preserve source-of-truth, single-writer, SQLite V1 schema/signatures/indexes, `WAL`, `synchronous=FULL`, foreign keys, exact source identity, replay, first-conflict cutoff, checkpoint, source lifecycle, retention, health, telemetry, read DTOs, privacy, NI-02B/NI-04 downstream compatibility, Portal/Auth/CAPPORT isolation.

**No production access, database mutations, service restart, deploy, feature activation, forced migrations or performance experiments against production.** Physical IOPS improvement has not been established and is not an accepted claim of this task.

## 2. Exact production source allowlist

Only:

```text
app/network_metadata/service.py
app/network_metadata/repository.py
app/network_metadata/config.py
app/network_metadata/models.py
```

Do **not** edit `app/network_metadata/schema.py`, `normalizer.py`, `scope.py`, `read_service.py`, `projection_source.py`, `retention.py`, `app/network_metadata_projection/**`, `app/network_attribution/**`, Fingerprint, NI-04, `run.py`, `app/settings.py`, Admin, Omada, CAPPORT, Visitor Registry, SQL schema/index/PRAGMAs, deployment or systemd units.

**Allowed targeted tests** (edit/add tests only for this A contract):

```text
tests/network_metadata/test_service.py
tests/network_metadata/test_repository.py
tests/network_metadata/test_checkpoint_crash.py
tests/network_metadata/test_config.py
tests/network_metadata/test_capacity.py
tests/network_metadata/test_health.py
```

**Allowed documentation:** `docs/configuration.md`, and optionally `.env.example` solely to document the default-OFF flag. No unrelated docs or tests. Scope increase → Tech Lead decision first; do not work around closed scope.

## 3. A1 — two separate exact range probes

After all existing source lifecycle/continuity/headroom guards and acquisition of the existing bounded batch (`<=256` records, same retained bytes), and **before the normalizer's per-record preflight loop**, issue **one** read-only indexed query for the exact current generation and the first/last batch **record start offsets**:

```sql
SELECT 1 FROM network_metadata_source_records
 WHERE source_generation_id = :generation_id
   AND record_start_byte_offset BETWEEN :first_start AND :last_start
 LIMIT 1;
```

- Only a **definitely empty** result permits treating subsequent preflight identity dispositions as `new`; still invoke normalizer for each admitted record, preserve source guards, record ordering, possible first conflict, and existing early-stop logic.
- If **any** row exists inside the interval, even at an offset not represented by current records, execute the **original ordered per-record `identity_outcome()` path for the entire batch**. No mixed shortcuts.
- SQL failure, malformed result, or ambiguity → storage-unavailable / fail-closed. Never reinterpret as “empty”.
- Do not infer newness from checkpoint, source file ID, IP, input hashes, or cached earlier range answers.

Inside `NetworkMetadataRepository.ingest_batch`, after the existing input validation, capacity guard, and `BEGIN IMMEDIATE`, run a **fresh independent** probe on the exact `outcomes` range and generation. The preflight result is **not** trusted transactionally. Only if this in-transaction probe is empty may Phase A use `new` without per-record identity SELECT. If nonempty, run original ordered per-record Phase A and stop at **the first** conflict. `candidate.ensure`, Phase B, health, fault aggregates, checkpoint and generation update remain in the **same transaction/COMMIT**.

All-new batch expected SQL shape: **one preflight probe + one transactional probe; zero per-record identity SELECT** for N=1,2,256. This is an SQL statement-count claim, **not** a physical IOPS claim. Preserve `duplicate_noop`, `source_record_identity_conflict`, `normalizer_determinism_conflict`, `replay_identity_evidence_expired`, `digest_state=expired`, first blocked offset and replay identity validation. Simulated between-probe row changes are **fault-injection only**, not a second real writer.

## 4. A2 — validated column snapshot lifecycle

After successful `validate_schema()` on the actual SQLite connection during `NetworkMetadataRepository.initialize()`, build an **immutable per-instance/per-connection `table -> frozenset(allowed columns)`** for every table in existing `TABLE_DDL`. Do not mark it authoritative before validation succeeds. Guard incomplete/failed build, invalid table/columns and stale DB associations with fail-closed behavior.

- For A=ON, `_insert()` checks table membership in `TABLE_DDL` and columns against this validated allowlist; keep bound SQL parameters and all insert semantics. No per-insert `PRAGMA table_info`.
- For A=OFF, legacy `PRAGMA table_info` path stays intact.
- `close()` invalidates cache. `recover()` / new `initialize()` rebuilds a fresh snapshot **only following successful validation of that connection**; no global cache or reuse across DB files.
- Unsupported external DDL drift after startup is **not** an excuse to add repeated schema checks. SQLite errors still abort/rollback.

Test correct cache preparation, unsupported table/column, invalid/replaced schema on reopen, connection recovery and pre-validation/failure path.

## 5. A3 — batch-local grouped fault UPSERT

Within existing `ingest_batch` **Phase B only**, and only the **actually reached ordered plan prefix**, replace immediate per-event `_fault()` calls for A=ON with local accumulation by exact key:

```text
(logical_source_id, source_generation_key, fault_category, aggregation_epoch_start_utc)
```

The 5-minute UTC epoch is the *existing* algorithm. For each group retain `count`, actual first and last relevant offsets, and the single transaction's `transaction_now` for first/last seen (while old persisted first seen/offset remains untouched on conflict). Validate `FAULT_CATEGORIES` **at accumulation time**, not only at flush. After Phase B and **before** the existing `before_checkpoint_update` crash hook, issue **one equivalent parameterized UPSERT per nonempty group**, deterministic stable order. Preserve `count=count+added_count`, same `last_seen_utc`/`last_relevant_offset` behavior; no emitted event after first conflict. No new commit boundary or modified crash-hook order.

- A=OFF calls legacy `_fault()` unchanged.
- Maintain `faults` telemetry as **event count**, not group count.
- Preserve `expire_touched_identity`, normalized facts, candidate health, generation and checkpoint.
- Any fault validation error, SQL error or crash before `COMMIT`: entire transaction rollback, no checkpoint advance. Replay after committed transaction must not increment fault rows twice.
- `_fault` calls **outside** `ingest_batch` stay intact, including generation lifecycle.

## 6. Configuration contract

Add an immutable config field `io_hotpath_v1_enabled: bool = False` in `NetworkMetadataConfig` (name is implementation-local; env key is normative). Parse only after the existing enabled=true gate:

```text
NETWORK_METADATA_IO_HOTPATH_V1_ENABLED=false   # unset=false
```

Only literal lowercase `true` or `false`; invalid when enabled → `NetworkMetadataConfigError` and controlled startup failure. When NI-01 disabled, ignore even malformed new flag. `false` must be **absent from canonical digest inputs**, giving exactly previous `configuration_digest`. `true` is present in canonical digest for explicit lineage/identity. No runtime change without controlled restart; no Admin toggle. B's independent flag is **not** introduced in this A PR.

## 7. Coder-focused acceptance tests (execute only scoped tests)

Implement **deterministic, focused** tests covering R2 acceptance IDs A1-01..A1-06, A2-01..A2-03, A3-01..A3-04 and A flag config. Tests may use disposable file-backed SQLite/fixtures, controlled clock, SQL tracing and crash injection; never attach to live production DB.

- N=1/2/256 all-new with expected **exact** identity SQL counts; compare serialized observations, child rows, health, checkpoint, telemetry versus OFF.
- First/middle/last duplicates and conflicts, row in range but not at input offset, generation isolation, expired digest, changed normalizer semantic digest, first-conflict prefix and offset.
- Empty preflight but simulated nonempty transactional re-probe, source truncation/rotation/continuity failure, partial/oversized records, invalid schema, SQLite errors and capacity.
- A2 no `PRAGMA table_info` on ON insertion hot path, validation on initialize, fail-closed across `close()/recover()`.
- A3 F=0/1/10/256, G=0/1/many groups, existing aggregate, multiple epochs/categories, SQL count/first-last offsets, crash boundaries around observation/fault/checkpoint/COMMIT, stable post-commit replay.
- Verify OFF == frozen legacy data/behavior/config digest, strict env parsing, disabled short-circuit and ON lineage.

**Coder execution boundary:** run the narrowly affected `tests/network_metadata/*` tests for this change **once** after implementation/corrections and report exact command/counters. Do not run the entire repository, Central/Full regression, extended physical I/O benchmark or production tests. Tech Lead owns broader independent tests and physical measurements. Implementing a targeted test is not authorization to run a costly host-wide load experiment.

Mandatory HOLD for an open correctness failure. Do not weaken assertions, source integrity, `synchronous=FULL`, foreign keys, or migrate schema to force PASS.

## 8. Handoff / publication

Deliver one **A-only** branch and PR against approved `main`, with exact base/head/tree, changed-file list, summary of SQL statement deltas, focused test output, OFF/ON equivalence evidence and any open questions. Commit/push/PR permitted, **no merge**. Do not push a second unrelated optimization into A.

At the end report:

```text
TASK=PERF-IO-NI01-A
RESULT=PASS | BLOCKED (with exact cause)
BASE_HEAD=...
BASE_TREE=...
CANDIDATE_HEAD=...
CANDIDATE_TREE=...
CHANGED_FILES=...
FLAG=NETWORK_METADATA_IO_HOTPATH_V1_ENABLED (DEFAULT_OFF)
FOCUSED_TESTS=... (command + counts)
SQL_DELTA=... (measured statements only)
OFF_PATH_EQUIVALENCE=...
PR_URL=...
MERGE=NO
PRODUCTION_CHANGE=NO
```

## 9. Independent release / activation (NOT CODER TASK)

Tech Lead: code review; broader targeted compatibility and Lab comparison against equivalent file-backed data; production process provenance/release integrity; independent physical I/O evidence. Owner: PR merge, dormant code publication, every environment change/activation and restart. Activation order: deploy A with flag OFF → prove legacy behavior and exact loaded identity → baseline → activate **A only** after separate Owner approval → monitor and revert OFF for any correctness/health/performance regression. Do not claim physical disk incident resolved on fewer SQL statements alone.

**Tech Lead directive:** `CODER GO — PACKAGE A ONLY`; `PACKAGE B` is a distinct follow-up work item and may not be bundled into A.
