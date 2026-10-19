# CAPTIVPORTAL — QIO-02 / P1 R3
## Independent Tech Lead live read-only evidence + conditional disposable Lab proposal

**Date:** 2026-10-16, Asia/Baku (UTC+4)  
**Author role:** Tech Lead — Performance & Small-I/O  
**Status:** `P1=EVIDENCE_REQUIRED; H1=CONDITIONAL_CONTINUE_P1; H1_CONSUMER=HOLD; N7-pre=UNPROVEN; P2=HOLD; CODER=HOLD; PRODUCTION_MUTATION=NONE`  
**Normative basis:** Chief Architect `QIO-02 P1 R2 Public Traffic reader_state.updated_at Semantic Disposition v1.2` and earlier QIO-02 contract / P1 R2 audit. This is **not** an Architecture Contract, implementation TASK, or P2 GO.

## 1. Executive verdict

**LIVE SOURCE-LEVEL H1 REPETITION: CONFIRMED.** On the running production Public Traffic SQLite, five completed rotated sources (`omada_webhook_normalized.log.1` through `.5`) retained *identical* source identity, path, offset, source checkpoint, size, retired and missing-warning flags between bounded read-only samples while `reader_state.updated_at` moved forward. The main live source (`.log`) changed its offset and observed size in a separate sample, and must not be classified as no-op. Static review confirms a separate `BEGIN IMMEDIATE → UPSERT → COMMIT` for each `observe_source` call, and a final-EOF call for each discovered source.

**HOST PHYSICAL SAVING: NOT PROVEN.** Live host HDD busy remained about 92.53% in a 30-second physical window; the guest disk was also saturated in a partly overlapping sample. No per-SQL-operation-to-physical-HDD mapping or quiet matched-window evidence exists. No attempt was made to modify code, database, service, configuration, SQLite durability or tracing settings.

**CONSUMER CONTRACT: NOT CLOSED.** Scoped repository/current service, cron and utility searches found no direct freshness consumer requiring `reader_state.updated_at`, but out-of-repository, remote and forensic usage cannot be excluded. Architect v1.2 says this timestamp is not currently authoritative successful-full-scan proof, not that it is universally disposable.

**Disposition:** Continue bounded P1 if economical; no Coder TASK, P2 Lab implementation, merge, deployment or production mutation. Offer this exact Lab proposal only for later separate admission after consumer safety and cost rationale are reviewed.

## 2. Independently verified identity (read-only)

- GitHub `ZaurNavi/CaptivePortal` `main` at inspection: `191beda1f23f8f466d2431f42e57571815d85778`; exact tree: `3f6d0a05c5d893d3139db44a1692c81e67fd6c6e`.
- PR #219 merged; its changed-file list does not contain `app/public_traffic/reader.py` or `repository.py`.
- PR #215 remains OPEN/DRAFT, excluded.
- Production `/opt/CaptivePortal` via authorized desktop → PuTTY `Ubunt` at `2026-10-16T12:18:39Z`: `HEAD=e2cbd96916d8a81f07f0d79a1a745f593ccb5114`, `TREE=8c95448250d75b01580bfdd4c52a40cf71a288af`, tracked checkout clean, `captive-portal.service=active`, MainPID `1887236`, NRestarts `0`.
- Production is **not** silently equated to GitHub `main`. QIO-01D night deploy remains separate and no deployment action was performed.

## 3. Live read-only SQLite source evidence

### Method

Queries used `timeout 3–4s sqlite3 -readonly -separator , /opt/CaptivePortal/data/public_traffic.sqlite3` against six `reader_state` rows. No `PRAGMA wal_checkpoint`, VACUUM, schema inspection with mutation, database copy, trace or writer intervention. Physical source files were checked using `stat`, without reading their contents. Production `lsof` was a bounded point-in-time inspection; it observed the current portal Python PID holding the DB and WAL but cannot exclude other short-lived consumers.

Seven-field effective state tuple (excluding operational timestamp): `source_identity`, `source_path`, `source_offset`, `source_checkpoint`, `last_observed_size`, `retired_completed`, `missing_warning_emitted`.

### Evidence R3-E01 — two-point sample at 12:20:46Z → 12:21:07Z

Six rows present. All five rotated sources `.1`–`.5` had unchanged identity, offset, observed size, retirement flag (`1`) and missing-warning flag (`0`); their `updated_at` increased. This first sample recorded only `length(source_checkpoint)=64` rather than the whole checkpoint, so by itself it does **not** prove full seven-field equality. The live `.log` advanced from offset/size `2,285,144` to `2,286,694` bytes and is a legitimate changed-source case.

### Evidence R3-E02 — exact-checkpoint verification at 12:26:30Z → 12:27:46Z

All seven stored fields for each `.1`–`.5` row, **including the complete SHA-256 checkpoint**, remained byte-for-byte equal across these queries, while all five `updated_at` values advanced. Current final row timestamps:

| Rotated source | Offset = observed size (bytes) | `retired_completed` | Original timestamp UTC | Later timestamp UTC | Effective tuple | 
|---|---:|---:|---|---|---|
| `.log.1` | 52,427,439 | 1 | 12:26:28.573 | 12:27:46.340 | UNCHANGED |
| `.log.2` | 52,427,620 | 1 | 12:26:27.593 | 12:27:45.444 | UNCHANGED |
| `.log.3` | 52,428,073 | 1 | 12:26:26.316 | 12:27:44.463 | UNCHANGED |
| `.log.4` | 52,428,700 | 1 | 12:26:24.737 | 12:27:44.263 | UNCHANGED |
| `.log.5` | 52,428,433 | 1 | 12:26:21.318 | 12:27:43.944 | UNCHANGED |

In addition, `stat` at 12:21:20Z confirmed each rotated file existed on the filesystem with matching `st_dev:st_ino` and size. All five archived source mtimes preceded the read-only observation period. The active source, by contrast, had grown between first-sample endpoints.

**Causal claim allowed:** current code repeatedly commits metadata-only changes to already completed, unmodified rotated sources. **Not allowed:** infer one `fsync` or one physical host disk I/O from each timestamp change, infer exact scan cadence from config default, or claim that the five rows are never needed for future recovery.

### Evidence R3-E03 — static repository correspondence

On exact GitHub merge baseline, `app/public_traffic/reader.py` `scan()` loads a reader-state snapshot before the loop, processes each discovered source and reloads states afterward. `_process_source()` calls `observe_source()` for incomplete tail **and** for final completed EOF. `app/public_traffic/repository.py:observe_source()` executes `BEGIN IMMEDIATE`, `_upsert_reader_state()`, `connection.commit()`. UPSERT unconditionally updates `updated_at` even if the effective state tuple is unchanged. `PublicTrafficRepository.get_reader_states()` returns seven fields, not timestamp. `get_snapshot()` projects `traffic_daily.updated_at`, not `reader_state.updated_at`.

**TOCTOU:** a skip based only on the preloaded `scan()` state is forbidden: the final persistence decision must be conflict-safe and serialized under the single existing writer authority. Source filesystem identity/checkpoint changes are not frozen by DB locks and must still be checked.

## 4. Physical baseline R3-E04 — high-contention non-quiet

Host `OMV-HP /dev/sda`: two read-only `/proc/diskstats` points at `12:23:30Z` and `12:24:00Z`, exactly 30 seconds apart. Difference:

| Completed physical metric | Total 30 s | Normalized |
|---|---:|---:|
| Reads | 2,334 | 77.80/s |
| Writes | 3,099 | 103.30/s |
| Sectors written (512 B) | 63,079 | 1,076,548 B/s |
| io_ticks | 27,760 ms | ~92.53% busy |
| write_ticks | 264,921 ms | ~85.49 ms average write await |

Ubuntu guest `iostat -dx -y 5 6 /dev/vda` produced six five-second windows beginning at about `12:23:04Z` with `%util`: `97.52, 96.08, 96.88, 95.84, 96.96, 96.16`. Guest windows partly overlap but are **not identical** to the host 30-second window; do not mix counters into an exact cost attribution. `iostat` was not installed on host; `/proc/diskstats` was used instead, and no package was installed.

**N7-pre=UNPROVEN; QUIET_WINDOWS=0/3.** At high external disk contention, no honest per-operation physical attribution to H1 is possible from these observations.

## 5. Consumer audit R3-E05 — scope and limitations

- GitHub code search over current default branch: `reader_state` returned scoped references in Public Traffic, distinct Registry/Visit and tests. No confirmed first-party read that consumes Public Traffic `reader_state.updated_at` as freshness proof. Distinct tables called `reader_state` cannot be conflated.
- Public Counter API route (`app/portal_counter/routes.py`) calls `PublicTrafficService.snapshot_payload()`, which calls `PublicTrafficRepository.get_snapshot()`; the presented timestamp is from `traffic_daily`.
- Current module documentation `docs/modules/public-traffic-counter.md` owns the Public Traffic subsystem; older `docs/public_traffic.md` declares itself superseded and must not outrank current source, though it also describes traffic `updated_at` as counted-event time.
- Bounded read-only filename search under `/etc/systemd/system`, `/etc/cron.d`, `/etc/cron.daily`, `/etc/cron.weekly`, `/etc/logrotate.d`, `/usr/local/bin`, `/usr/local/sbin`, `/home/admin/bin` found no matching `public_traffic`, `reader_state` usage in searched `*.service`, `*.timer`, `*.conf`, `*.sh`, `*.py`, `*.cron` files. Absent/unreadable locations, other extensions and other hosts are not covered.
- A point-in-time `lsof` observed only portal PID `1887236` holding the Public Traffic SQLite DB and WAL. This does **not** prove no other short-lived external SQL reader.
- Prior P1 R2 research reported Grafana Loki/Prometheus datasource inspection, not direct SQLite. This R3 did not independently repeat Grafana's live datasource inspection.

**Consumer verdict:** first-party consumer not found; relevant external/forensic/SLA usage **not exhaustively excluded**. `H1_CONSUMER_HOLD` remains until a bounded external owner/inventory attestation or other suitable evidence resolves it. If a required freshness consumer is discovered, reject current H1 semantics and return for compatibility design. Do not silently throttle timestamps.

## 6. Potential scale and prioritization

Five unchanged retired-source rows are updated in a source pass. In the inspected code each final `observe_source()` call opens its own transaction, so at the *source-code level* five such commits are plausible per completed scan. But actual scan duration varies under contention; samples are not adequate to infer a stable 10-second production cadence. SQLite WAL (`synchronous=NORMAL` in current code) may group physical flushes/checkpoints differently from source SQL transactions. **No host write-savings percentage is stated.** Relative to 103.30 total physical host writes/sec in this interval, significance has not been demonstrated.

Important P2 scope ambiguity to close: Architect v1.2 excludes **source retirement**. Clarify that the H1 no-op permission, if ultimately granted, may cover a **stable already-retired** source (`retired_completed=1 → 1`, unchanged tuple) while the **transition into retirement** (`0 → 1`) remains compulsory. The observed five strongest candidate rows are all already retired. Without this clarification, treat stable-retired H1 admission as HOLD rather than guessing.

## 7. Disposable Lab experiment plan — PROPOSAL ONLY, not authorized

**Goal:** isolate the same-tuple final EOF write cost without changing any authoritative cursor, events, recovery or durability semantics. One candidate at a time.

**Immutable Lab baseline:** fresh isolated worktree from exact Tech Lead-approved HEAD/TREE, disposable SQLite and synthetic rotated-file fixtures; record both baseline and candidate tree SHA and checksum. No production database copying required. No production service launch, restart or config mutation.

**Candidate semantic boundary:** only the final `_process_source()` completed-EOF path; unchanged seven-field durable tuple plus same inode/generation and filesystem checkpoint/offset verification. Preserve current `observe_source()` for incomplete tails and all mutation/reset transitions. A separate narrow repository method/conditional persistence path may be proposed, but **no SQL algorithm is admitted at P1**. Final no-op predicate must execute atomically under existing writer serialization, not on preloaded `scan()` state. Ensure first-time source remains inserted; retirement transitions remain durable; stable-retired inclusion is separately reviewed. Do not create a second authority.

**Correctness matrix:** unchanged repeated EOF; zero-byte event; duplicate; new line; partial-to-complete line; same size but changed checkpoint; truncate/rewrite/inode reuse; rotation; disappeared/reappeared; active-to-retired and retired-to-active; missing-warning transitions; conflicting concurrent updater; late file append; two sources with mixed complete/partial results; initial backfill; crash before/during/after transaction; replay after crash; reset/counter history stability; any known external consumer. Compare row sets, checkpoint positions, processed-event IDs, daily aggregates and externally visible availability exactly against baseline; only an explicitly admitted operational timestamp may differ.

**Measured benefit:** matched A/B on the same physical HDD class or suitably equivalent controlled host storage, both under calm and representative load; at least repeated runs, balanced A/B order and untouched instrumentation. Capture committed source calls, SQL transactions, guest cgroup, host disk completed writes/bytes/await/busy, WAL/checkpoint dynamics and total scan latency with correctness gates. No claim that dropping a SQL UPDATE equals dropping a host I/O. If no reproducible physical reduction or latency gain, REJECT candidate.

**Acceptance sequence:** Chief Architect P1 consumer/cost disposition → separate written P2 LAB GO → Tech Lead narrow TASK → Coder isolated implementation + focused tests → Tech Lead independent Windows/Linux/fault/replay/security/PERF → Owner separate GitHub/production decisions. No global SQLite mode/durability changes.

## 8. Remaining precise questions for Chief Architect

1. Does `v1.2` permit conditional no-op when **an already-retired** source remains retired, or does its blanket `source retirement` exclusion also forbid any stable-retired no-op? This is the majority of observed candidate writes.
2. If no direct first-party consumer exists but external incident/forensic use cannot be exhaustively excluded, what **bounded operator attestation or compatibility criterion** suffices to close `H1_CONSUMER_HOLD`, if any? Do not assume absence.
3. If 3 quiet production windows remain unobtainable due to systemic high HDD busy, can a clearly scoped disposable Lab physical A/B **serve as N7-pre causal feasibility evidence** for a *future separate P2 GO*, with no production-savings assertion, or is further production attribution mandatory beforehand?

## 9. Machine-readable handoff

```ini
TASK=QIO-02
REPORT=TECHLEAD_P1_R3_LIVE_READONLY
GITHUB_MAIN=191beda1f23f8f466d2431f42e57571815d85778
GITHUB_TREE=3f6d0a05c5d893d3139db44a1692c81e67fd6c6e
PRODUCTION_HEAD=e2cbd96916d8a81f07f0d79a1a745f593ccb5114
PRODUCTION_TREE=8c95448250d75b01580bfdd4c52a40cf71a288af
PRODUCTION_SERVICE=ACTIVE_PID_1887236_RESTARTS_0
ARCHITECT_V1_2=ACCEPTED_FOR_RESEARCH_ONLY
H1_EXACT_ARCHIVED_SAME_TUPLE_UPDATED_AT_ONLY=PROVEN_5_OF_5
H1_FIRST_PARTY_DIRECT_TIMESTAMP_CONSUMER=NOT_FOUND_IN_SCOPED_REVIEW
H1_EXTERNAL_CONSUMERS=INCOMPLETE
H1_STABLE_RETIRED_SCOPE=ARCHITECT_CLARIFICATION_REQUESTED
H1_TOCTOU=GUARD_REQUIRED
PHYSICAL_HOST_30S_WRITES_PER_SEC=103.30
PHYSICAL_HOST_30S_BUSY_PERCENT=92.53
N7_PRE=UNPROVEN
QUIET_WINDOWS=0_OF_3
P1=EVIDENCE_REQUIRED
H1_CONSUMER=HOLD
P2_LAB=HOLD
CODER=HOLD
PRODUCTION_CHANGES=NO
QIO_01D_DEPLOY=NOT_EXECUTED_IN_THIS_RESEARCH
```
