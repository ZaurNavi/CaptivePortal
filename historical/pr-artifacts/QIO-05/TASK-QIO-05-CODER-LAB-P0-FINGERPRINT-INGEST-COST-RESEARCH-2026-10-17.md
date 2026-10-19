# TASK-QIO-05-CODER-LAB-P0 — Fingerprint ingest SQLite write-cost research

**Owner:** Optimization Tech Lead  
**Executor:** Coder  
**Authorization:** Isolated disposable LAB research ONLY. **No product implementation, no service change, no commit/push/PR/merge/deploy, no production network/data or credentials.** This task is separate from the QIO-02 publication branch.

## Research hypothesis

Can we reproduce and attribute the physical write/syscall cost of (A) `N=100` entirely **new valid fingerprint evidence events**, (B) identical 100-event **duplicate-only retry** (zero inserts), (C) source-health positive and duplicate-only, and (D) idle/cleanup checks, on unchanged approved source? Does the current existing one-transaction-per-batch path already avoid SQLite page changes for duplicate-only input, and what extra commits / checkpoints occur? Never assume cgroup Evidence write spike is due to duplicates.

## Frozen source and inventory

Use a new, private worktree copied from an exact pinned repository state; record HEAD/TREE/current main separately. Initial code-audit reference: `main@516abc7f56cb9c60a0e450af109334f4949b3da9` (not proof of loaded production SHA). Relevant paths:

- `app/device_fingerprint/api.py::_ingest`; `service.py::evidence_batch/source_health_batch`;
- `app/device_fingerprint/repository.py::_ingest` (BEGIN IMMEDIATE, per-event immutable lookup, positive INSERT, sequence-watermark UPDATE only on insert, COMMIT);
- `app/device_fingerprint/telemetry.py`, `tests/device_fingerprint/test_repository.py`, `tests/device_fingerprint/test_service.py`, `tests/device_fingerprint/test_api.py`;
- downstream read semantics of ingest watermark and immutable identity.

Do not change `app/` code or tests' original assertions. Standalone **untracked** lab scripts and synthetic temp SQLite outside the repository are allowed, in an isolated task directory; don't modify another Coder's feature worktree or shared test runner. If reproducing requires application changes, stop and request Tech Lead architectural/scope review instead.

## Test matrix and measurements

1. Derive valid synthetic test records using existing test factories and fixed synthetic clocks; no real MAC/IP/client/production payload. Distinct IDs vs exact byte-identical replay. Run **positive, repeated duplicate, mixed, source-health, error/conflict, capacity/rollback, restart/reopen and retention** scenarios. Preserve selected production SQLite configuration; never change `synchronous`, journal mode or WAL autockpt to manufacture a win. Track versions, OS, file system, source tree and table rows/ingest sequence.
2. Two arms are **existing implementation under different fixture workloads** (not a modified code candidate). For each workload use at least 4 repetitions and ABBA order where sensible; distinguish cold interpreter vs warm DB/OS cache. Report SQL `BEGIN/COMMIT/INSERT/UPDATE` counts, source DB/WAL/shm `pwrite64`, `fdatasync/fsync`, bytes, checkpoints if observable, and latency distribution. Linux `strace -ff -yy` is permitted ONLY on disposable lab processes with new temporary DBs. Windows native focused correctness gate using available venv; don't claim Windows strace.
3. Verify exact equality of authoritative tables and durable watermark against their expected fixture outcome. Replay same identities with same payload is no-op success; conflicting immutable same-ID values must remain conflict; failed transaction must not advance `last_ingest_sequence`; restart/replay order exact; retention, cap and health safety remain. Verify any absence of database writes does not imply no CPU or logical SELECT cost.
4. Report estimated *source transaction-level* opportunity and its theoretical upper bound from real SysAdmin telemetry, **not** claimed production host-HDD savings. Distinguish positive-insert work that is mandatory from repeated duplicate-only work and actual changed page count. Do not unilaterally recommend reduced FULL/NORMAL sync guarantees or grouping across request boundaries.

## Deliverables and stop gate

`HANDOFF-QIO05-LAB-P0.md`, machine-readable `manifest` (source SHA/tree, environment, exact commands, fixture parameters, result status), focused Linux/Windows tests, SQL/syscall measurements, immutable aggregate tables, raw synthetic-only strace logs, patch/diff status showing zero application edits, rollback/cleanup scope. SHA256 checksums and read-only provenance. If forced to introduce an API/schema/storage/durability change, **HOLD / Tech Lead + Chief Architect** first.

**No implementation GO** is granted by a successful lab profile. Tech Lead compares this against SysAdmin's matching producer/file attribution, chooses one falsifiable optimization if safe, and then issues a separate implementation TASK or Architect request.
