# CaptivPortal — Coder Lab Task / Profiling Only
## TASK-DTI-NI-IO-PROFILE-01 — Reproducible Write-I/O Profiling of NI-01/NI-02B

**Issuer:** TechLead23  
**Date:** 2026-10-12  
**Parent task:** `TASK-DTI-NI-IO-OPT-01`  
**Binding architecture:** `ARCH-DTI-NI-IO-OPT-01-WRITE-PATH-CONTRACT-v1`, accepted for laboratory profiling by TechLead23.  
**Exact source baseline:** `main@88541da8d6952cb91fc945b7f77efcf7e5c46420`  
**Expected tree:** `d879f5113319c334faf2bf9ae7b8bea7cfdc977e`

```text
AUTHORIZATION = ISOLATED LAB / SOURCE READ / TEMPORARY MEASUREMENT HARNESS
PRODUCTION_CODE = NO
PRODUCTION_CONFIGURATION = NO
PRODUCTION_DATABASE_READ_OR_WRITE = NO UNLESS SEPARATELY APPROVED
PRODUCTION_SERVICE_RESTART = NO
MERGE/DEPLOY/FEATURE_ACTIVATION = NO
COMMIT/PUSH/PR = NO AUTHORIZATION FROM THIS TASK
FINGERPRINT_WRITER_CHANGE = NO
NI05/NI06 = HOLD
```

## Goal and constraints

**Goal:** Independently quantify whether four Architecture-approved write-path experiments reduce disk IOPS/COMMIT/sync/checkpoint/logging while preserving the entire accepted semantic state, crash/replay, attribution, privacy, source freshness and NI-03/NI-04 bounded reads.

**Do not immediately write a deployable optimization PR.** First build a bounded, isolated laboratory replay/profiling rig that can compare legacy and candidate behavior from the same initial DB snapshot and deterministic source input. Candidate experimentation is restricted to an unmerged local lab copy. Do not change production feature flags. No SQLite PRAGMA mutation of production. No production background profiling or remote load test.

Allowed experimental source surface: `app/network_metadata/*`, `app/network_metadata_projection/*`, focused lab tests/fixtures/harness; no shared CAPPORT/Auth/Omada, no Fingerprint spool writer, no production schema/index/retention changes. A separate SysAdmin lane owns storage benchmarking.

## Stage 0 — hard baseline / environment proof

- Record exact `HEAD`, tree, test/lab machine, filesystem, storage medium and mount, OS, Python/SQLite version, CPU/RAM limits and test invocation. Reject stale/mixed commit inputs.
- Confirm reference behavior `FULL`, WAL, 256 / 1 MiB NI-01 ceiling, 256 NI-02B ceiling, 1-second NI-02B polling, current routine success telemetry. Preserve immutable fixtures/source input hash, deterministic time and start-DB identity.
- Build synthetic/anonymized source DNS/TLS/QUIC streams with explicit source generations, time windows, legal/illegal records, retransmits, conflicts, restart and reader-pin scenarios. No production raw IP/MAC/SNI export; use documented synthetic identities.
- Distinguish process transaction counts, block-level IOPS, SQLite WAL bytes, host physical device I/O and fsync/fdatasync. Do not conflate per-PID `/proc/io` with actual physical disk writes.
- Before CPU-heavy runs, prove the lab I/O path is **not** the production VM's shared HDD `/dev/sda` and cannot congest it indirectly. If isolation cannot be proven: **HOLD** without creating load.

## Stage 1 — P0 legacy profiling, zero candidate change

Profile and archive control measurements of:

- **NI-01:** ingest loop counts, observed batch-size distribution and batch-cap reason (count, byte, end-of-file, stop, generation), `BEGIN/COMMIT` rate, sync-call rate, checkpoint/WAL sizes, retention timing, checkpoint lag, source event-to-commit latency, CPU/RSS. Read-only code inspection also identify idle transactions vs actual durable writes.
- **NI-02B:** successful no-data polls, actual status-only SQLite writes/sec, source batch commits, reconcile/retention transactions, count/timing/trigger of explicit PASSIVE/TRUNCATE, SQLite autocheckpoint, WAL growth, capacity/read-pin states and registry degradation.
- **L1:** count NI-01 and NI-02B success events, bytes/second and journald contribution, with errors/transitions counted separately. Prove useful physical write contribution before treating L1 as a performance candidate.
- **NI-03/NI-04:** run the accepted bounded read paths in parallel to writer load and record p50/p95/p99, success/timeouts; include a retained SNI match and non-match fixture.
- **F0 observation only:** enumerate protected Fingerprint spool enqueue, ACK, purge, DELETE journal, sync and flush semantics in an isolated lab test; no modification of writer code. A separate `TASK-FINGERPRINT-IO-PROFILE-01` needs Fingerprint-owner admission for any broader profiling.

## Stage 2 — controlled candidates (one at a time)

### A1: NI-01 pre-transaction coalescing

- Test strict set `0` (legacy), `100`, `250`, `500` ms. Never wait holding SQLite `BEGIN IMMEDIATE` or another write lock. Never exceed 256 full contiguous records/1 MiB in memory; additional RSS <=16 MiB and CPU/10k <=baseline+10%.
- Commit on the first of count cap, byte cap, coalescing deadline, source-generation close/transition, graceful stop or 4 MiB uncommitted source-file backlog. Backlog high-water => zero intentional wait.
- Verify source identity, normalized facts, exact authoritative checkpoint/generation relationship, no mixed-generation transaction, valid health reference lineage, conflict handling, replay idempotence and exception handling. Show the intentional <=500 ms vulnerability to transient `/run` source loss explicitly.
- Performance pass candidate only if low/normal COMMIT **or** sync calls decrease >=25% **and** attributed NI-01 guest write IOPS decrease >=15%, without regression.

### B1: NI-02B idle durable-poll reduction

- Keep source poll every 1 sec. For unchanged successful **empty** polls, suppress SQLite status-only transaction until 10 sec since last durable success; a real batch commit already satisfies that heartbeat. If another transaction is needed, piggyback only if successful source verification occurred in that tick.
- Persist failure/state/recovery/startup/stopping transitions immediately (subject to already-accepted storage failure behavior). After restart initialize effectively as `initializing` until that run verifies source; do not blindly reuse previous `usable`.
- Independently verify every projection-status, NI-03 and NI-04 reader **derives effective `source_unavailable`, reason `source_poll_stale`**, when evaluated timestamp is more than 30 sec after last durable successful source poll. Use existing DTO shapes/version; if impossible without interface change, HOLD B1 and return to Architect.
- Controlled failure tests: abrupt kill just after/before heartbeat, no tick for >30 sec, transition to/from registry_degraded, pending attribution, start/stop, source read failure, clock boundary at exactly 30 seconds, no false healthy output.
- Lab benefit threshold: status-only SQLite write transaction rate <=0.12 per second during steady no-new-data sample.

### B2: NI-02B explicit checkpoint policy

- Preserve SQLite `FULL`, WAL, autocheckpoint=1000, 16 MiB headroom and all capacity fail-closed behavior.
- Ordinary commit must not itself invoke explicit PASSIVE; triggers: WAL >=16 MiB, retention completed with WAL nonempty, approaching hard headroom, capacity recovery. Rate limit soft explicit PASSIVE to <=1 per 60 sec; capacity safety bypass allowed.
- TRUNCATE remains only within the existing capacity-pressure path and existing reader-pin/busy safeguards. Simulate active pinned readers, WAL growth, pending checkpoint, no fake rollback of already committed dispositions and restart recovery.
- Lab benefit threshold: <=1 explicit PASSIVE per 60 sec below capacity pressure, no capacity or NI-03/NI-04 read regression. Separately report actual **physical write** improvement, not only fewer PASSIVE calls.

### L1: aggregate routine success events

- Experimental 60-second in-memory success counters for NI-01/NI-02B; at most 1 normal summary event per service/60 sec. Preserve all transitions/failures/immediate operational alerts and durable authoritative records.
- Summary includes bounded transaction, batch, record, duplicate, idle poll, checkpoint and suppressed-event counts. No MAC/IP/SNI/device ID or raw source payload. Demonstrate a material reduction in journald attributed I/O, not just fewer lines.
- On crash, summaries may be lost only if they are confirmed non-authoritative: no loss of durable replay/checkpoint, coverage diagnostics or fault notification.

## Stage 3 — matrix, repetitions, hard gates

For each candidate and the legacy baseline, run at least three independent repetitions of these profiles from the **same source input digest, initial DB snapshot, storage class, CPU/RAM caps and flags**; first 60s are warm-up, excluded from percentiles:

| Profile | Duration | What to prove |
|---|---:|---|
| P-IDLE | 10 min | No new source records; source polls/heartbeats/explicit checkpoints; no false healthy state |
| P-LOW | 15 min | Typical DNS/TLS/QUIC rates; batch filling, IOPS and delay |
| P-BURST | 15 min | Source backlog, 4 MiB high-water, bounded drain/replay, max transaction sizes |
| P-READ | 15 min | NI-03/NI-04 5-second deadlines and p99 under concurrent source/projection writes |
| P-CRASH | deterministic matrix | Pre/post COMMIT, NI-01 six crash points, NI-02B seven crash points, WAL reader pins and exact restored semantics |

**Mandatory measurements:** per service transaction/commit/sync/sec, WAL/checkpoint attempts and duration, WAL peak and DB footprint, guest-equivalent write IOPS/KiB/s/p50/p95/p99, CPU/RSS, event-to-ingest, source-to-projection, source backlog, capture loss, per-device attribution, NI-03/NI-04 p50/p95/p99 and deadline counts, semantic identity/digests, row/edge/checkpoint parity, privacy retention, restart/no-loss behavior.

**Hard correctness gate:** same semantic normalized evidence, exact source-record identity/checkpoints, fault/disposition, immutable edge IDs/digests, Registry late-binding semantics; no duplicate or missing accepted record, no false `usable`, no unauthorized raw data retention. If batch/health timing changes a dynamic UUID or timestamp, show provenance validation and seek Architect/RQA comparator admission **before** claiming equality. Any hard failure => candidate FAIL no matter how much IOPS it saves.

**Resource envelope:** CPU <=baseline +10%; RSS <=baseline +16 MiB; zero new NI-03/NI-04 deadlines; NI-03/NI-04 p99 <=baseline +10%; zero new coverage or conflict degradation; A1 high-backlog drain <=baseline +5%. Keep all retention/schema/indices exactly unchanged.

## Stage 4 — evidence handoff, not a production PR

Deliver a self-contained `TASK-DTI-NI-IO-PROFILE-01` report with:

1. exact baseline commit/tree, input fixture hashes, initial DB fingerprints, lab host/storage isolation evidence and tool versions;
2. profile matrix for every tested variant with three runs, warm-up policy and raw bounded metrics (no sensitive identities), per-run reproducible invocation and failures;
3. output of independent crash/replay, privacy, retention, NI-03/NI-04 concurrency and strict DTO tests;
4. benefit-vs-risk table for A1/B1/B2/L1: `LAB_PASS`, `LAB_FAIL`, `INCONCLUSIVE` or `NOT_RUN`, with reasons;
5. recommended values **for review only**, no implied production defaults and no silently selected A1 delay;
6. explicit `PRODUCTION_ACTION=NONE`, `COMMIT/PUSH/PR/MERGE=NONE`, `FEATURE_ACTIVATION=NONE`; local experimental patch/diff hashes if present;
7. questions/ambiguities for Architect/RQA instead of assumptions.

**Stop and escalate immediately** for any required schema/DTO version change, Fingerprint writer mutation, inability to isolate disk/host load, retention reduction, durability weakening, unbounded buffering, source identity change or unreproducible measurements.

## TechLead gate to next phase

Technical Coder completion does not approve optimization implementation. TechLead23 and independent Research & QA review the measured evidence and coordinate any necessary Architect clarification. A new Owner-approved implementation/change task is required after that. NI-05 and NI-06 stay HOLD.
