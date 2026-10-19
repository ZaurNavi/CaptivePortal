# CAPTIVPORTAL — QIO-02 P1
## Tech Lead Read-only Consumer & I/O Attribution Evidence — R1

**Дата:** 2026-10-16 (Asia/Baku)  
**Роль:** Tech Lead по оптимизации. Главные регрессионные и performance gates выполняет сам Tech Lead; отдельной независимой QA-роли нет.  
**Scope:** только read-only P1 investigation, не реализация, не Coder TASK и не production GO.

## 1. Действующий architecture admission и решения

Нормативный контракт: `CAPTIVPORTAL-QIO-02-SQLITE-SMALL-IO-ARCHITECTURE-ADMISSION-CONTRACT-v1-2026-10-16(1).md` (Chief Architect), `CAPTIVPORTAL-QIO-02-TECHLEAD-ARCHITECTURE-REVIEW-AND-P1-DIRECTIVE-2026-10-16.md`.

- `P0=PASS`; `P1=EVIDENCE_REQUIRED`; `P2_LAB=HOLD`; `CODER=HOLD`.
- H1: optional removal of redundant final Public Traffic `observe_source()` on completely unchanged same-generation EOF, conditional on complete consumer graph and physical cost proof.
- Other canonical durable fields / visits / registry successful-scan freshness / Current State and Observations cycles are outside permitted suppression scope.
- No production changes were made in this P1 investigation; neither QIO-01D nor PR #215 was touched.

## 2. Artefact identity, host topology, honest accounting

- GitHub `main` and production checkout initially checked at `e2cbd96916d8a81f07f0d79a1a745f593ccb5114`, tree `8c95448250d75b01580bfdd4c52a40cf71a288af`. `captive-portal.service` remained active, existing MainPID `1887236`, `NRestarts=0` at read-only baseline.
- Guest `192.168.0.202`, KVM/QEMU machine, `vda` 400 GB, `vdb` 900 GB. Physical QEMU host is **OMV-HP**, not a separate unrelated host: host `pgrep` identified QEMU `guest=Ubunt` PID 2664346 (historical live PID at measurement), backing file `/UbuntVM/Ubunt.qcow2` on ext4 `/dev/sda1`. This was independently rechecked before host physical I/O attribution. The VM has a second backing disk on a different mounted volume, so QEMU cgroup may contain several physical device identifiers; compare the `8:0` device with `/dev/sda` only.
- Guest Linux cgroup `io.stat` reports both `252:0` and `253:0` layers; **do not sum** them. They are not independent physical writes.
- Host cgroup `machine-qemu...Ubunt.scope` contains all guest processes, while guest `captive-portal.service` captures only one source of its workload. Physical host `sda` includes all VMs and host services; no 1:1 attribution per SQL transaction from those counters alone.
- No heavy trace, SQLite checkpoint, VACUUM, PRAGMA durability change, systemd restart, production code modification, or active workload injection.

## 3. Current runtime inventory (read-only)

Process environment and `data/` file metadata were read without printing credentials, source identities or guest MAC/IPs. The following DBs existed:

| DB | Main-file bytes observed | Notable WAL bytes observed | Contractual authority |
|---|---:|---:|---|
| `public_traffic.sqlite3` | 18,223,104 | none visible at sample | processed events, reader state, counters |
| `visitor_registry.sqlite3` | 67,719,168 | none visible at sample | source events / durable `last_successful_scan_at` |
| `visits.sqlite3` | 66,031,616 | 4,152 | auth, visits, checkpoints, retry |
| `current_state.sqlite3` | 87,113,728 | none visible at sample | each cycle and its quality/scope, even empty |
| `observations.sqlite3` | 926,433,280 | 19,640,072 | each observation attempt/cycle incl. incomplete/error |

These are one-time file sizes, **not per-DB fsync counts, measured write contributions or criteria for candidate ranking**. Current State, Visit Lifecycle, Registry, Observation Foundation were enabled in the process env. Visit Lifecycle scan interval explicitly `5 s`. Public Traffic scan interval was not explicitly present in process env; code default is `10 s`, which is not independent proof of a runtime adopted value if there is an override.

## 4. H1 production behavior and consumer inventory

Source verification at `main@e2cbd969`:

1. `app/public_traffic/reader.py::_process_source`: final complete EOF calls `repository.observe_source()` even after unchanged input; partial-line path is separate, must not be affected.
2. `app/public_traffic/repository.py::observe_source`: `BEGIN IMMEDIATE` → UPSERT → `commit()`; `_upsert_reader_state` changes `updated_at` on conflict even when source tuple unchanged. No SQL `WHERE changed` guard.
3. **Controlled read-only two-point live DB check, 32 seconds:** 6 reader-state rows in both snapshots; for 5/6 rows, source identity/path/offset/checkpoint/observed size/retired/missing fields unchanged and only `updated_at` changed; sixth row had a source tuple change. No row identities/paths disclosed. This confirms repeated timestamp updates in production, not the number of commits or physical writes they caused.
4. `get_reader_states()` reads identity/path/offset/checkpoint/observed size/retired/missing and does **not** project `reader_state.updated_at`. Github code search found no exact `reader_state.updated_at` references in the repository and no other `FROM reader_state` user of the Public Traffic table besides Public Traffic repository. `SELECT MAX(updated_at)` in Analytics SourceGateway refers to **`visit_reader_state`**, not Public Traffic.
5. Live Grafana DB data sources were read in `mode=ro`: `loki`, `prometheus`; no SQLite Grafana data source. This excludes direct SQLite querying through these configured Grafana data sources, **not** external scripts/API/direct SQLite consumers.

Consumer graph residuals: external scripts and forensic direct SQL readers not fully inventoried; source `updated_at` may be an implicit operational freshness proof even without a code consumer. A no-op skip remains prohibited until consumer / replay / SLA proof and concurrency guard semantics accepted.

## 5. First standalone guest 10-minute baseline (read-only)

UTC `2026-10-16 10:48:07`–`10:58:08`; sampled `sysfs`/cgroup/PSI every 60 seconds with no database reads; reported in independent block layers (do not sum `252:0` and `253:0`).

| Metric | 10-minute average |
|---|---:|
| Guest `vda` completed writes | **49.709/s** |
| Guest `vda` completed reads | 131.461/s |
| Guest `vda` busy | 96.60% |
| Guest `vda` write await | 99.4 ms |
| Guest I/O full pressure delta | 41.59% |
| `captive-portal.service` guest write `wios`, ONE layer `252:0` | **6.728/s** |
| `systemd-journald.service` guest write `wios`, ONE layer `252:0` | **7.551/s** |

Interpretation: significant contention and non-portal writers exist inside guest. This is an observational window, not a controlled quiet baseline. No physical IOPS or H1 cost is inferred from these numbers alone.

## 6. Aligned guest / QEMU / physical host 10-minute sample

**T0 UTC:** `2026-10-16T10:54:00Z`; both processes synchronized to one start bound. Sampling only `sysfs`/cgroup/PSI counters every 60 seconds. Host `qemu_vm` cgroup `/sys/fs/cgroup/machine.slice/machine-qemu\\x2d3\\x2dUbunt.scope`, physical `/dev/sda`; guest `/sys/block/vda`, two service cgroups. Other VM and host system processes are confounders; do not equate host writes with QEMU writes.

**Окно:** 10:54:00–11:04:00 UTC (14:54–15:04 Asia/Baku), десять минут синхронных чтений счётчиков. Оба измерительных процесса штатно завершили все 10 интервалов; SSH exit = 0. После измерения CaptivPortal оставался `active`, PID `1887236`, `NRestarts=0`, checkout `e2cbd969…` чистый.

| Уровень, выбранный один device layer | 10-minute mean |
|---|---:|
| `captive-portal.service`, guest `252:0`, `wios` | **6.92/s** |
| `systemd-journald.service`, guest `252:0`, `wios` | **6.82/s** |
| Весь guest `vda`, completed write ops | **48.53/s** |
| Весь guest `vda`, completed read ops | 124.13/s |
| Guest `vda` busy / write await | 97.49% / 96.88 ms |
| Guest I/O full stall time | **51.77%** |
| QEMU `Ubunt` VM host cgroup, physical device `8:0`, `wios` | **43.72/s** |
| Host physical `/dev/sda`, completed write ops | **66.80/s** |
| Host physical `/dev/sda`, completed read ops | 132.08/s |
| Host `/dev/sda` busy / write await | **91.27% / 89.21 ms** |
| Host I/O full stall time | 5.75% |

Selected aligned minute-by-minute measurements (write operations/sec):

| Interval UTC | Guest `vda` | Ubuntu QEMU on host `8:0` | Host `/dev/sda` |
|---|---:|---:|---:|
| 10:54–10:55 | 49.08 | 44.44 | 68.71 |
| 10:55–10:56 | 45.33 | 41.50 | 74.15 |
| 10:56–10:57 | 53.71 | 50.13 | 75.62 |
| 10:57–10:58 | 52.36 | 46.98 | 70.17 |
| 10:58–10:59 | 50.08 | 45.37 | 62.60 |
| 10:59–11:00 | 39.12 | 33.67 | 47.60 |
| 11:00–11:01 | 44.12 | 40.45 | 68.77 |
| 11:01–11:02 | 50.84 | 45.82 | 71.13 |
| 11:02–11:03 | 44.94 | 39.77 | 59.77 |
| 11:03–11:04 | 55.70 | 49.07 | 69.55 |

**Пределы причинного вывода:**

- Host `/dev/sda` включает другие QEMU workloads, system processes и физический I/O scheduler; cgroup requests могут coalesce и переучитываться. `43.72 host-QEMU wios/s` не равны `66.80 completed physical writes/s`.
- QEMU VM `8:0` включает все Ubuntu guest services, а не только портал; `6.92 portal guest writes/s` **не** измеренный физический вклад конкретной SQLite БД.
- Гостевые cgroup слои `252:0` и `253:0` **не суммировать**.
- Guest full-pressure >50% и physical HDD busy >90%: **quiet conditions не доказаны**. Это high-contention observational baseline, не matched quiet A/B.
- Физическая стоимость одиночного `PublicTraffic observe_source` остаётся не измерена. Частота изменения `updated_at` и размер БД не доказывают экономию HDD.
- Дополнительный запрос к другой QEMU VM был заблокирован удалённым инструментом и не повторялся альтернативным способом. Конкурирующая нагрузка учтена не полностью.


## 7. P1 verdict and next admission gate

**AFTER SYNCHRONIZED BASELINE:** H1 source-path and repeated live timestamp updating are proven; per-operation physical write cost, exact consumer/freshness safety and net A/B host improvement are not. Therefore **`P1=PARTIAL / P2_LAB=HOLD / CODER=HOLD / PRODUCTION_MUTATION=NO`** until Architect reviews the evidence.

Before P2, Tech Lead should:
1. Finish external consumers and `updated_at` freshness/replay semantic audit; any required `updated_at`-as-scan-proof consumer rejects H1.
2. Obtain reproducible per-DB/transaction baseline on isolated Lab using bounded tracing, rather than heavy production instrumentation. Establish relative SQL call frequency, actual WAL/fdatasync, and estimate an upper bound for host physical gain. Reproduce complete source tuple cases: same EOF, append and 0-byte evidence, rotation, truncate, missing/reappear, partial tail, checkpoint mismatch, concurrency and crash.
3. Capture additional quiet windows with client/source workload classification; at least three matched quiet 10–15-minute windows before and after any **approved Lab change**, with QEMU/host and auth/health checks. The current high-contention window must not be labeled quiet.
4. Return `QIO-02 PER-DB PHYSICAL-WRITE & CONSUMER-SEMANTIC EVIDENCE` and recommendation `H1 PASS_TO_LAB / H1 REJECT / ALTERNATE` to Chief Architect. No Coder TASK before P2.
