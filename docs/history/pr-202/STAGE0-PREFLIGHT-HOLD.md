# TASK-DTI-NI-IO-PROFILE-01 — Stage-0 preflight / HOLD

Date: 2026-10-12. Scope: local read-only baseline/environment inspection only.
This is not a profiling result, optimization acceptance or official gate PASS.

## Frozen source identity

- Requested baseline: `88541da8d6952cb91fc945b7f77efcf7e5c46420`.
- Requested tree: `d879f5113319c334faf2bf9ae7b8bea7cfdc977e`.
- Fetched `origin/main`: `88541da8d6952cb91fc945b7f77efcf7e5c46420`.
- Fetched main tree: `d879f5113319c334faf2bf9ae7b8bea7cfdc977e`.
- Source inspection used `git show <exact baseline>:<path>`; no mixed/stale runtime was executed.
- Existing Windows R7 publication worktree was preserved at `f3e23af844c91be1ba5b56e92b2dcadb6ad3822c`, tree `d879f5113319c334faf2bf9ae7b8bea7cfdc977e`, clean. It was NOT relabeled as the requested baseline commit.
- No new profiling worktree, experimental branch, implementation patch or commit created.

## Input document SHA256

| Input | SHA256 |
|---|---|
| TASK-DTI-NI-IO-PROFILE-01-CODER-LAB-ONLY-2026-10-12.md | `0ae94b7a1e965ae7dc9dd602d178f49e06bfe99386f9a94ad996e5983c8da4a9` |
| TECHLEAD23-DTI-NI-IO-OPT-01-ARCHITECTURE-REVIEW-VERDICT-2026-10-12.md | `9188a73f5d25759453bc53c063810cbeef4e8ed7f63758e1599a5fd9733982ac` |
| ARCH-DTI-NI-IO-OPT-01-WRITE-PATH-CONTRACT-v1.md | `30c4b0723d50f424fac09cea915d18650a2b3ce5fe7b899edacb999f3200b5a4` |

## Local Lab storage isolation

Read-only Windows CIM/storage inspection observed:

- Physical computer: HP ProBook 450 G7, host `DESKTOP-7C8M3BS`.
- OS: Windows 10 Pro, version 10.0.19045.
- Logical processors: 8. Physical RAM: 17,018,630,144 bytes.
- Local Disk 0: SK hynix BC511 HFM512GDJTNI-82A0A, NVMe SSD, 512,110,190,592 bytes.
- C: maps to that Disk 0; it is the Windows boot/system disk.
- Ubuntu-22.04 registry BasePath: `C:\Users\Zaur Navi\AppData\Local\wsl\{35d28455-8dd0-4641-b901-de155d565adf}`.
- Its local `ext4.vhdx` exists at that BasePath; observed length 14,079,229,952 bytes.
- Proposed native Linux Lab parent `/home/zaur_navi/captivportal-lab` resolves to ext4 `/dev/sdd`, mounted at `/`, not a network mount or production guest disk.

This storage path is on the independent laptop NVMe, not the production OMV `/dev/sda` HDD described in the supplied TechLead analysis. No production access was used to establish this local path.

WSL `/dev/sda` is a separate 356.9 MiB virtual disk, NOT evidence of access to the production physical HDD with the same device name.

## Linux runtime / metric capabilities

- Distro: Ubuntu-22.04 / Ubuntu 22.04.5 LTS.
- Kernel: `6.18.33.2-microsoft-standard-WSL2`, x86_64.
- User: `zaur_navi`, UID 1000.
- PID 1: systemd. Journald process present.
- Python: `/home/zaur_navi/captivportal-lab/test-gate-platform-01-r1-venv/bin/python`, 3.10.12.
- SQLite: 3.37.2.
- `/usr/bin/python3.10` SHA256: `a2f33a6e006989270f4340528eb61f8f97366e00a5d1b602ac8672ea44fc56ae`.
- WSL reports 8 processors and MemTotal 8,052,344 KiB. No workload-specific CPU/RAM limits configured or asserted.
- `strace` 5.16 present. `systemd-run` and `journalctl` present.
- `iostat`, `pidstat`, `bpftrace`, `blktrace` not found on inspected PATH. No installation attempted.
- Cgroup v2 present; root-level `io.stat` and `/proc/diskstats` readable. These are aggregate virtual-device counters, NOT per-service physical NVMe metrics.
- As the ordinary Lab user, tracefs is root-only and cgroup subtree control is not writable.
- A read-only WSL-root capability check found `block_rq_issue`, `block_rq_complete`, and `ext4_sync_file_enter` tracepoint formats available. No tracepoint enabled, tracing session started, cgroup created, limit changed or service reconfigured.
- Windows `wpr.exe`, `logman.exe`, `Get-Counter` available. Current Windows token is NOT an Administrator token. No elevated host tracing attempted.

## Existing worktrees preserved

The canonical native `/home/zaur_navi/captivportal-lab/repo` is an unrelated dirty Traffic candidate at `e1a278c3e2c131b0762d7134485dcf3208eac11e`. It was inspected, not reused, reset, cleaned or edited.

The older native R7 copy is also staged/dirty and was not reused or altered.
Future execution must use a NEW clean native worktree at the exact requested baseline, not either existing dirty tree.

A root Git inspection of the canonical native repo refused dubious ownership. It was retried read-only as its ordinary owner. No `safe.directory` or global Git configuration changed.

## Read-only legacy source confirmation

Exact baseline inspection confirms:

- NI-01 repository initialization preserves WAL, FULL, autocheckpoint 1000, journal-size limit 64 MiB.
- NI-01 atomic transaction opens BEGIN IMMEDIATE and commits observation/source/checkpoint changes together.
- NI-01 `wal_maintenance()` is conditional; no claim of per-commit explicit checkpoint was made.
- NI-02B repository preserves WAL, FULL, autocheckpoint 1000.
- Successful NI-02B empty poll executes a transaction and updates `last_source_poll_at` after source verification.
- Successful NI-02B transactions call `maintain_capacity(post_commit=True)`; maintenance attempts PASSIVE.

These are source facts, NOT observed rates, sync counts or physical write savings.

## Admission / instrumentation question for TechLead23 + SysAdmin

Full Stage-3 evidence requires separately attributed service/block IOPS, physical-host I/O, write-latency p50/p95/p99 and material journald I/O reduction. No qualified collector/methodology currently binds the WSL virtual-device requests to the physical Windows NVMe requests with the required attribution and latency semantics.

Linux-root tracing can observe the virtual block layer. It cannot by itself establish physical NVMe completion latency or physical per-service/journald write attribution. `/proc/io`, SQL counters and virtual-device totals cannot substitute for those mandatory metrics.

Please provide/admit either:

1. A bounded host collector and correlation methodology for this laptop WSL/NVMe environment, including elevation/collector ownership, output limits and per-service/journald attribution; or
2. A separately authorized isolated native Linux Lab with a known non-production physical storage path and qualified per-service/block/physical latency collectors.

If TechLead intends a virtual-only preliminary measurement lane, explicitly define its scope and permitted INCONCLUSIVE results. It must not be presented as the full physical-I/O benefit gate, and no acceptance thresholds should be silently weakened.

No refusal of Linux instrumentation support is claimed: tracepoints and strace exist. The HOLD concerns the unqualified full measurement chain, not source incompatibility or storage-isolation failure.

## Actual run disposition

| Variant | Result | Reason |
|---|---|---|
| Legacy P-IDLE/P-LOW/P-BURST/P-READ/P-CRASH | NOT_RUN | Measurement qualification pending |
| A1 0/100/250/500 ms | NOT_RUN | No experimental changes or comparator claims |
| B1 | NOT_RUN | No experimental changes |
| B2 | NOT_RUN | No experimental changes |
| L1 | NOT_RUN | Journald physical attribution unqualified |
| F0 | NOT_RUN | No spool execution or mutation |

No synthetic replay fixture or initial DB snapshot created; therefore no fixture/DB hashes or performance invocation exist yet. No semantic equality, capture-loss, crash/replay, throughput, CPU/RSS or latency result is claimed.

## Actions and final status

Only fetched origin refs/objects, read documents and exact source, inspected local Windows/WSL environment, and created this external preflight report. Starting the local WSL distro occurred as part of environment inspection; no production service was contacted or restarted.

```text
TASK=TASK-DTI-NI-IO-PROFILE-01
STATUS=HOLD_MEASUREMENT_QUALIFICATION
BASELINE_IDENTITY=PASS
LOCAL_STORAGE_ISOLATION=PASS
LOAD_RUNS=NOT_RUN
EXPERIMENTAL_SOURCE_CHANGES=NONE
PRODUCTION_ACTION=NONE
COMMIT=NONE
PUSH=NONE
PR=NONE
MERGE=NONE
FEATURE_ACTIVATION=NONE
NI05=HOLD
NI06=HOLD
NEXT_ACTION=TECHLEAD23 / SYSADMIN MEASUREMENT DISPOSITION
```
