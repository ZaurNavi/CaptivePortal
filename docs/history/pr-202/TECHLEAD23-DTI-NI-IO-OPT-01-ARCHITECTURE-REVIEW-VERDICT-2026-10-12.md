# CaptivPortal — TechLead23 / Independent Architecture Review
## TASK-DTI-NI-IO-OPT-01 — Write-Path Architecture Contract v1

**Date:** 2026-10-12  
**Input:** `ARCH-DTI-NI-IO-OPT-01-WRITE-PATH-CONTRACT-v1(1).md` (Architect); `TASK-INFRA-IO-01-FINAL-ROOT-CAUSE-REPORT-2026-10-12.md` (SysAdmin); `TASK-DTI-NI-IO-OPT-01-TECHLEAD23-APPLICATION-IO-ANALYSIS-2026-10-12.md` (TechLead).  
**Source independently checked:** `ZaurNavi/CaptivePortal`, `main@88541da8d6952cb91fc945b7f77efcf7e5c46420`; tree `d879f5113319c334faf2bf9ae7b8bea7cfdc977e`. GitHub main and commit tree checked via read-only connector.  
**Review mode:** architecture/source verification only. No edits to repository, service configuration, SQLite, or production runtime.

## 1. Decision

```text
TASK = TASK-DTI-NI-IO-OPT-01
ARCH_CONTRACT = ARCH-DTI-NI-IO-OPT-01-WRITE-PATH-CONTRACT-v1
TECHLEAD_ARCHITECTURE_REVIEW = PASS FOR PROFILING-ONLY
SOURCE_COMPATIBILITY = PASS WITH IMPLEMENTATION NOTES
OPEN_BLOCKING_P0 = 0
OPEN_BLOCKING_P1 = 0
IMPLEMENTATION_PRODUCTION = HOLD
CODER_NEXT_SCOPE = TASK-DTI-NI-IO-PROFILE-01 / ISOLATED LAB ONLY
COMMIT_PUSH_PR_MERGE = NOT AUTHORIZED BY THIS REVIEW
DEPLOY / RESTART / PRODUCTION_FLAG / PRAGMA / DB_MIGRATION = NO
NI05 = HOLD
NI06 = HOLD
```

This is **not an assertion that any optimization saves a measured number of IOPS**. It is approval to measure accepted candidates in an isolated laboratory, compare them to the exact legacy behavior and test for safety. No performance/semantic candidate is admitted for production by this verdict.

## 2. Key independent source checks

1. `app/network_metadata/repository.py`: NI-01 uses `journal_mode=WAL`, `synchronous=FULL`; one `BEGIN IMMEDIATE`/`COMMIT` encompasses normalized observations, source identity and checkpoint. Existing max per batch is 256 source records / 1 MiB. Conditional NI-01 `wal_maintenance()` must not be misrepresented as a checkpoint on every transaction.
2. `app/network_metadata/service.py`: polling sleeps one second only if no useful ingest work. `HealthController.ensure()` writes a new health snapshot at state changes or a due heartbeat; even if `persist_health()` opens a transaction more often, a transaction's existence alone does not prove a physical write. A1 must measure actual I/O and preserve record/generation atomicity.
3. `app/network_metadata_projection/service.py`: a successful empty `poll()` enters a write transaction to persist `last_source_poll_at` even if no new observations exist. Candidate B1 has a directly confirmed current write path.
4. `app/network_metadata_projection/repository.py`: every transaction's successful `COMMIT` calls `maintain_capacity(post_commit=True)`, which attempts `PRAGMA wal_checkpoint(PASSIVE)`. Candidate B2 has a directly confirmed explicit-checkpoint invocation; physical write reduction remains to be measured.
5. `app/network_metadata_projection/models.py`: current `RUNTIME_STATES` already include `initializing`, `stopping`, `source_unavailable`, etc. B1 can preserve the existing SQLite schema/enum and map the derived stale condition to `source_unavailable`.
6. `app/network_metadata_projection/read_service.py` and `recognition_read_service.py`: NI-03/NI-04 read services are independent and consume persisted runtime state. Both must use the same effective 30-second stale check. NI-03 returns an **exact dict shape** (`runtime_state`, `binding_state`, `bound_device_id`, `facts`); changing it breaks the existing consumer contract. NI-04 uses a frozen `RecognitionProjectionSnapshotV1`. Preserve both shapes while deriving the effective enum and surfacing `source_poll_stale` through an already admitted status/reason field where available. `get_status()` also needs the stale policy.
7. `app/device_fingerprint_sensor/spool.py`: separate Fingerprint-owned SQLite DELETE-journal/FULL spool, enqueue/ack/delete persistence. Only read-only/lab profiling is admitted in this phase; no NI-owned writer mutation.

## 3. Candidate dispositions

| ID | Candidate | TechLead disposition | Enforced limits |
|---|---|---|---|
| A1 | NI-01 pre-commit coalescing | **LAB ONLY** | 0/100/250/500 ms; 256 records and 1 MiB max; zero wait at 4 MiB backlog; intact atomic checkpoint/replay; no waiting under `BEGIN IMMEDIATE` |
| B1 | NI-02B idle-state write reduction | **LAB ONLY; first priority** | poll still every 1 s; 10 s durable unchanged-success heartbeat; immediate transition persistence; 30 s fail-closed cross-process source-stale evaluation |
| B2 | NI-02B explicit PASSIVE checkpoint policy | **LAB ONLY** | keep FULL/WAL/autocheckpoint; at most one routine PASSIVE per 60 s; WAL >=16 MiB, retention or capacity triggers; headroom and TRUNCATE safety unchanged |
| L1 | Routine success-log aggregation | **LAB ONLY, condition on journald attribution** | one normal aggregate per service/60 s; start/stop, state transitions and failures stay immediate; no raw identifiers |
| F0 | Fingerprint spool | **PROFILING ONLY; NO MUTATION** | distinct Fingerprint-owned architecture admission required for any changes |
| S0 | Dedicated SSD/vDisk comparison | **INDEPENDENT SYSADMIN LAB LANE** | no production move unless Owner approves a separate backup/migration/rollback plan |

`FULL → NORMAL/OFF`, schema/index/retention changes, CAPPORT/Auth, production DB migration and NI05/NI06 implementation remain forbidden in this phase.

## 4. Mandatory implementation-review notes (no architecture blocker for lab P0)

**N1 — effective stale-source state must not accidentally widen DTOs.** For B1, derive a fail-closed `source_unavailable` when `evaluated_at_utc - last_source_poll_at > 30 seconds`, with operational reason `source_poll_stale`. Apply consistently to NI-03's narrow projection reader, NI-04's recognition reader and the projection status read. Never treat a persisted `usable` row as proof the current process is alive. Preserve exact existing DTO field sets and version. If the frozen interface cannot express the required reason while preserving semantics, **hold B1 implementation and refer the interface question to Architect**; do not independently expand NI-03/NI-04 product contracts.

**N2 — deterministic equality needs a frozen comparator.** A1 changes batch boundaries and commit timing, so health heartbeat UUIDs/timestamps, ingest-run IDs and ephemeral instrumentation may legitimately differ even when replay and observations are semantically equal. The lab comparison must compare the *same required semantic fields* and verify every retained health reference, identity, source-record digest and checkpoint; it must not silently omit a material provenance discrepancy. If exact parity of batch-associated health rows is ambiguous, raise it to Architect/RQA **before** claiming A1 acceptance. Do not relax the architect's hard semantic gate unilaterally.

**N3 — prove I/O, not just SQL invocations.** Count and time actual commits, `fsync/fdatasync`, WAL checkpoints and cgroup/device IOPS. A reduction in calls to `PRAGMA wal_checkpoint(PASSIVE)` is not yet a demonstrated reduction in physical disk latency.

**N4 — lab isolation.** The Architect allows local test-only candidate variants under `app/network_metadata/*`, `app/network_metadata_projection/*` and focused tests/harness only. There is no authority to edit production, ingest real sensitive client identities into a lab, change Sensor writer, perform ad hoc production checkpointing, or create/push a PR by virtue of this architecture review.

**N5 — source/guest/host comparison.** SysAdmin measured Ubuntu VM as 83.08% of physical `/dev/sda` write bytes and 85.11% of write IOPS during one synchronous host sample. Within the guest, NI-01, Fingerprint Sensor and NI-02B are top contributors. These percentages are sample-specific; NI-04 deadlines and NI-01 lag have not yet been causally linked to an identical I/O window. Do not promise aggregate percent savings.

## 5. Required next gates

1. Issue `TASK-DTI-NI-IO-PROFILE-01` as a **profiling-only** lab handoff, with frozen base commit/tree.
2. For every candidate, collect repeatable P-IDLE/P-LOW/P-BURST/P-READ/P-CRASH matrices, minimum three runs, controlled data/DB start state/hardware and warm-up exclusion; evidence includes crash/replay/privacy/latency and measured write IOPS.
3. TechLead + independent RQA review evidence, and Architect revisits any boundary/comparator ambiguity.
4. Candidate-by-candidate benefit gate (A1 >=25% COMMIT-or-sync reduction **and** >=15% attributed NI-01 write IOPS; B1 idle state-only writes <=0.12/s; B2 routine explicit PASSIVE <=1/60 s; others must demonstrate material benefit). Any semantic regression => FAIL regardless of speed.
5. Only then prepare an implementation/release contract, with Owner's separate merge/deploy/activation decisions and single-variable production comparison.

## 6. Owner explanation

The system currently behaves like several clerks saving each small receipt separately on one mechanical drive. The safe experiment is to reduce unnecessary receipts and group legitimate receipts while preserving the official ledger. P0 measures whether that actually makes the mechanical drive queue shorter. The experiment itself does not change what customers see or alter production.
