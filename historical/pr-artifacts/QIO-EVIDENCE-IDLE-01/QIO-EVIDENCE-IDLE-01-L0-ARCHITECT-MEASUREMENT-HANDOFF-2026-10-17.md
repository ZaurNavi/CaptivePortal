# CAPTIVPORTAL — QIO-EVIDENCE-IDLE-01
## Independent Tech Lead — L0 measured findings and Chief Architect decision handoff

**Date:** 2026-10-17 (Asia/Baku). **Scope:** only old lab VM `192.168.0.202`, QEMU domain `Ubunt` on `omv-hp` (`192.168.0.220`), physical host `/dev/sda`. **Explicitly OUT OF SCOPE:** running `captiv-prod`, Network Metadata, code implementation or deployment.

**Status: measured interim, NOT final full-integrity certificate.** Current LAB deep `PRAGMA quick_check` has been initiated under Owner's full-scan override and was still executing at the latest observation. It must not be marked PASS without complete `[("ok",)]` result. All other stages listed below have completed. This handoff separates the durable findings from the outstanding integrity result.

### 1. Owner / role clarification

There is **no independent direct chat** between Chief Architect and Tech Lead. The Owner relays artifacts between two chat contexts. This handoff is intended to be forwarded by Owner; merely authoring it does **not** notify Chief Architect. Implementation gate remains held under Architect v1.1 §E6.2. Coder runs **only scoped focused tests** if a later P2 contract authorizes implementation; all full Linux/Windows and failure/security/physical HDD regression tests are **Tech Lead's independent responsibility**.

### 2. Identity and unmodified read-only audit

- VM identity confirmed on machine: IP `192.168.0.202`, hostname `local.domain.az`. Deployed pinned source tree: `810484e69baa371c4696c3b46654199631538fc4`.
- Original Evidence DB: `/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3`; `3,796,074,496` bytes, `926,776` SQLite pages of `4096` bytes, `journal_mode=wal`, `last_ingest_sequence=2,834,788`.
- `fingerprint-evidence.service=inactive` before auditor start. Auditor uses SQLite URI `mode=ro`, `PRAGMA query_only=ON`, no exposed HTTP server, no ingestion; original Evidence DB remains the target of an authorized full read-only audit. No test corruption injection or deletion of database.
- L0 process PID `500349`, started `2026-10-17T15:54:14+04:00`. Command script available on remote operator laptop: `C:\CaptivPortal-Lab\tmp\qio-evidence-l0-deep-stages-20261017.sh`.
- Audit SQL stages execute **sequentially**, preserving full legacy guard predicates; short bounded checks are **not** counted as replacements for these stages.

### 3. Completed L0 stages — actual measured outcomes

| Stage (legacy predicate) | Result | Elapsed | SQLite VDBE steps lower bound | Process `read_bytes` delta | Process `write_bytes` delta |
|---|---|---:|---:|---:|---:|
| Exact runtime metadata/schema/state preflight | PASS (`METADATA_VALID`) | **0.003 s** | 0 | 0 | 0 |
| Evidence `typeof(ingest_sequence)` / range / allocator scan | **PASS: no invalid row** | **148.402 s** | **19,900,000** | **41,791,488 bytes** | 0 |
| Source-health `typeof(ingest_sequence)` / range / allocator scan | **PASS: no invalid row** | **0.106 s** | 950,000 | 36,864 bytes | 0 |
| Cross-table Evidence ↔ source-health sequence collision JOIN | **PASS: no collision** | **1.252 s** | 9,950,000 | 4,096 bytes | 0 |
| Full `PRAGMA quick_check` | **IN PROGRESS at interim handoff — no conclusion** | Not finalized | Not finalized | Not finalized | Not finalized |

**Key interpretation:** the large Evidence guard performs a complete **covering-index scan** (`uq_df_evidence_ingest_sequence`), independent of current client activity. The source-health guard and cross-table JOIN also perform global index work, though their most recent warm-cache executions were faster. `read_bytes` here are Linux **process** accounting values, not necessarily one-to-one physical HDD completed reads.

### 4. Correlated physical host/guest observation during full Evidence sequence scan

Matched **45-second windows**, displaced in start by ~5.7 s (not perfectly identical). Each source uses `/proc/diskstats` deltas and `/proc/pressure/io` deltas, not inferred results from `strace`.

| Metric | Physical host `omv-hp:/dev/sda` | Guest `192.168.0.202:/dev/vda` |
|---|---:|---:|
| Read IOPS | **85.77** | **60.72** |
| Write IOPS | 57.95 | 31.66 |
| Read throughput | 0.410 MiB/s | 0.291 MiB/s |
| Write throughput | 0.499 MiB/s | 0.284 MiB/s |
| Read await | 14.11 ms | 21.16 ms |
| Write await | 46.91 ms | 119.86 ms |
| Busy (`diskstats` time) | **93.05%** | 96.38% |
| I/O PSI full | 4.72% | **46.47%** |

Host QEMU Ubunt cgroup delta in same 45 s: `rios=3822`, `rbytes=19,025,920`, `wios=1438`, `wbytes=14,063,104`. **Do not equate QEMU/cgroup I/O counts directly with physical host HDD IOPS.** Significant other writers are present on host; measured host writes cannot be exclusively attributed to Evidence.

### 5. Separate correlated host/guest observation during deep `quick_check`

| Metric | Physical host `/dev/sda` | Guest `/dev/vda` |
|---|---:|---:|
| Read IOPS | **75.31** | **71.44** |
| Write IOPS | 49.18 | 24.15 |
| Read throughput | 0.409 MiB/s | 0.356 MiB/s |
| Busy | **93.22%** | 97.70% |
| Read await | 16.26 ms | 16.63 ms |
| I/O PSI full | 4.86% | **41.16%** |

The intervals were separately started ~11 seconds apart. A `quick_check` process observed during this stage was in Linux `D` / `wait_on_page_bit_common`. This corroborates real HDD read pressure but does **not** establish that all host reads are attributable to the single SQL statement.

### 5.1. Long-running check status at last direct observation

At `2026-10-17T16:01:36+04:00`, the original auditor PID `500349` was **still alive** (`D`, `wait_on_page_bit_common`), elapsed ~7m23s from its overall process start. Aggregate `/proc/500349/io` since process start: `read_bytes=177,274,880`, `write_bytes=32,768`, `syscr=101,255`. This covers **all completed phases and the still-active quick_check**, therefore must **not** be mislabelled as quick_check-only counts. Evidence systemd remained `inactive`. The `PRAGMA quick_check` itself began `2026-10-17T15:56:44+04:00` and had not returned `ok` or any other final result. The ongoing command must not be inferred to have passed.

### 6. Prior causal A/B/A evidence (from accepted forensic)

When only Evidence service was enabled on the lab VM and other CaptivPortal components remained stopped, physical host `/dev/sda` read IOPS were `2.64 -> 56.20 -> 3.31` on off/on/off windows; guest `/dev/vda` `0.04 -> 56.17 -> 0.07`; guest I/O PSI full `7.32% -> 35.15% -> 8.59%`. This established service-triggered HDD read pressure, but did not distinguish individual SQL statements. The current L0 provides the per-query decomposition.

### 7. Integrity/admission and candidate risk

- Source `DeviceFingerprintRepository.initialize()` invokes `PRAGMA quick_check` and its own historic sequence guards **before** admission of Evidence ingest.
- The existing `_validate_runtime_connection()` is a fast **metadata-only** test. Previously ~0.002–0.003 s. In a diagnostic standalone process substituting it for the deep check, `initialize()` finished in 3.5 s but caused ~356 KiB of incidental write I/O. This is **NOT equivalent integrity verification and is NOT a safe candidate**.
- Missing information for P1 equivalence: **completed** full `quick_check` on this DB (result and cost), full cold/warm repetitions, negative corruption fixtures and crash/WAL/rollback matrix, cryptographically/transactionally justified immutable generation and commit lineage if T2 is contemplated.
- No `mtime`, `data_version`, generation UUID, allocator, `quick_check(1)` or index minima/maxima may be treated as proof that arbitrary DB pages and WAL have not been corrupted.
- Do not admit ingest or claim readiness if deep trust is missing. No production speedup, no physical *write* IOPS saving is claimed.

### 8. Chief Architect decision requested

**A. Measured facts:** recognize per-stage historic sequence scan ~148.4 s and measured ~75–86 physical host HDD read IOPS with ~93% host disk busy under the independent tests. These findings support excessive *cold-start read pressure* without current clients.

**B. Integrity gate:** full `quick_check` remains **UNVERIFIED** until actual finish; do not accept preliminary samples or a manual abort as PASS.

**C. Preserve HOLD:** Do not authorize Coder fast-start implementation based on metadata-only check. Architect v1.1 P0/L0 measurement permitted; P1 proof and a new P2 implementation admission are required. If equivalent T2 cannot be proved, retain legacy deep-before-ready or request a separately explicit Owner risk/change decision; an implementation task must not silently weaken historical corruption detection.

**D. Sequencing:** complete Evidence L0 and L1 before investigating Network Metadata. New live `captiv-prod` is **never an experiment target**.

### 9. Source/evidence provenance and limitations

- Architect source: `CAPTIVPORTAL-QIO-EVIDENCE-IDLE-01-CHIEF-ARCHITECT-STARTUP-INTEGRITY-CONTRACT-v1.1-OWNER-LAB-2026-10-17` §0, E1–E6.
- Laboratory SQL experiment (remote): `C:\CaptivPortal-Lab\tmp\qio-evidence-l0-deep-stages-20261017.sh`, remote terminal PID `22904`, guest audit PID `500349` at start.
- Prior raw forensic source: `C:\CaptivPortal-Lab\handoffs\QIO-EVIDENCE-IDLE-IO-FORENSICS-20261017.zip`.
- Earlier Tech Lead source: `QIO-EVIDENCE-IDLE-01-TECHLEAD-FORENSIC-2026-10-17.md`.
- Physical measurements are short windows affected by background host VM workloads; they are **not** a complete exclusive-cost accounting.

**Status line:** `L0=PARTIAL_MEASURED; LEGACY_SEQUENCE_GUARDS=PASS; QUICK_CHECK=NOT_YET_VERIFIED; T2=UNPROVEN; CODER=HOLD; PROD=UNCHANGED`.
