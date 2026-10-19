# CAPTIVPORTAL — QIO-02
## Tech Lead → Chief Architect: SQLite Small-I/O / idle-write & fsync fan-out — Architecture Admission Request v1

**Дата:** 2026-10-16 (Asia/Baku)  
**Отправитель:** CaptivPortal Tech Lead — Performance & Optimization  
**Адресат:** Chief Architect  
**Тип работы:** Architecture Admission / Decision Contract, **не Coder TASK и не production GO**  
**Режим QIO-02 сейчас:** READ-ONLY CAUSAL ATTRIBUTION; LAB EXPERIMENT DESIGN после подтверждения причинности

### 1. Основание и актуальный baseline

- Нормативная очередь: `CAPTIVPORTAL-PERF-IO-QUIET-LOAD-OPTIMIZATION-ROADMAP-v1.0-2026-10-15.md` → QIO-02/P1 основной `captive-portal.service`, idle-write/fdatasync fan-out.
- Первичный quiet baseline 2026-10-15: **1,282 guest block writes / 120 s = 10.68/s** на `captive-portal.service`. Пассивно замечены `fdatasync` в `visits`, `visitor_registry`, `current_state`, `public_traffic` SQLite/WAL, **без достоверного per-file числа транзакций**.
- Дополнительная read-only выборка 2026-10-16 02:03:52–02:04:52: **667/60 s = 11.12 guest writes/s**; это не синхронная пара с первичным окном.
- После QIO-01B production deployment `main@e2cbd96916d8a81f07f0d79a1a745f593ccb5114` / TREE `8c95448250d75b01580bfdd4c52a40cf71a288af` гостевой 60-секундный срез `captive-portal.service` показал **4.03 wios/s**, `systemd-journald` **5.82 wios/s** (одно из двух зеркально учтённых cgroup-устройств); на физическом host HDD при другом окне было **~100.77 writes/s, ~90.7% busy**. Это НЕ сопоставимый эксперимент и НЕ доказательство физической экономии от QIO-01B.
- Во время QIO-01B startup основной портал ~11 минут не обслуживал внешний HTTP; системные блокировки чтения страниц наблюдались последовательно на `visits.sqlite3`, затем `current_state.sqlite3`; после этого HTTP 200 и успешные Omada cycles. **Cold-start read pressure — связанный operational risk, но не доказательство ненужных steady-state commits**.
- QIO-01A и QIO-01B находятся в production, Guest Auth E2E подтверждён владельцем; QIO-01D является **отдельной** задачей compact telemetry. PR #215/SSR-01B не включён в scope.

**Правила интерпретации:** guest `io.stat` ≠ host physical IOPS; значения `252:0` и `253:0` не складывать; `syscr/rchar`, число WAL pages, частота SQL или захваченный `fdatasync` в sampling не являются сами по себе completed HDD writes. Измерения — ограниченные, синхронизированные guest/host окна; не обещать процентов до/после заранее.

### 2. Подтверждённые кандидаты и семантические риски

1. **Visitor Registry**: `registry_worker` вызывает `repository.mark_successful_scan(now)` при каждом полном scan; `registry_repository.py` выполняет `BEGIN IMMEDIATE`, обновляет `last_successful_scan_at` и `updated_at`, затем `COMMIT`, даже если membership не менялся. **Но успешный fresh scan — наблюдаемое состояние, не автоматически лишний no-op.**
2. **Current State**: `client_worker`/`ap_worker` регулярно опрашивают Omada (default около 60 s); `repository.publish_cycle()` создаёт durable строку `current_state_cycles`, даже при пустом inventory. **Подтверждённый empty cycle может быть authoritative absence evidence, а не мусор.**
3. **Visit Lifecycle / Visits**: reader scan + retry/reconcile, checkpoints, visit start/end facts. QIO-01D сокращает только *операционные сообщения* `visit.reader_scan_completed`, **не** SQLite-путь. `retry_pending` или reader-state transition возможны при 0 новых строк.
4. **Public Traffic**: отдельные per-cycle и derived-state commits требуют атрибуции; no traffic ≠ no necessary reconciliation.
5. **Observations / Omada collectors**: регулярные successful/partial/error snapshots, source quality, freshness и reporting; stale/failed fetch нельзя превращать в достоверную пустоту.

Конкретные методы/SQL выше являются **source candidates**, а не доказанными лидерами completed guest/host I/O. Tech Lead самостоятельно устанавливает количественный вклад и возвращает evidence; Chief Architect принимает **семантические решения**, не обязан проводить расследование вместо Tech Lead.

### 3. Вопросы для однозначного архитектурного контракта

**Q2-A01 — Категории durability.** Для каждого вида записи и DB: какие факты являются `authoritative`, `derived/rebuildable`, `freshness/proof-of-scan`, `audit/security`, `operational-only`? Какие **must-commit на каждый цикл** даже при неизменном содержимом? Какие можно материализовать как «изменился content/generation» при неизменной корректности?

**Q2-A02 — Visitor Registry freshness.** Разрешено ли отделять durable `last_successful_scan_at` от membership изменения? Если да, определить upper bound staleness, поведение при повторных successful/no-change scans, process crash/restart, длительном отсутствии сканирования, missing source, late events, offline→online, degraded→recovered. Если нельзя доказать эквивалентность health, этот writer сохраняется.

**Q2-A03 — Current State cycle authority.** Является ли каждый успешно/неуспешно завершённый цикл новым immutable evidence факта наличия/отсутствия клиентов и AP? Как защитить `complete`, `unknown`, `partial`, `empty`, `failure` от ложной эквивалентности? Каковы freshness window, consumer watermark, replay/retention и обязательный failure record? Можно ли без потери доказательств пропускать отдельные **derived payload UPDATE** при неизменном canonical content, не пропуская сам cycle fact?

**Q2-A04 — Visits и Reader progress.** Где точная граница irreversible visit/open/close facts, source identity/checkpoints, pending retry, idempotency, reconciliation/health heartbeat? Какие поля при 0 event lines всё же несут durable progress? Может ли no-change fast-path существовать исключительно для подтверждённо избыточных derived metadata, не нарушая replay/crash/restart и не ослабляя `BEGIN/COMMIT` критических фактов?

**Q2-A05 — Public Traffic / Observations.** Матрица allowed/forbidden no-op guards, dedup/materialization/cache для unchanged observations, snapshots и counters; авторитетное отсутствие vs API unavailable; maximum age и revalidation; interop с Device Fingerprint, Visitor Registry, Admin UI, alerts.

**Q2-A06 — Transaction boundaries.** Условия для coalescing/batching только **совместимых derived writes**; где категорически запрещено объединять раздельные durability/replay domains. Не менять `PRAGMA synchronous`, journal mode, WAL autocheckpoint, SQLITE durability или общую filesystem persistence «ради IOPS».

**Q2-A07 — Crash/restart/incomplete scan.** Матрица негативных сценариев: kill между begin/commit, crash после authority commit до materialized read, duplicate/replay, packet loss, stale/unknown Omada, missing source, partial scan, backlog/late events, 20-мин cold startup под нагруженным HDD. Никаких fabricated empty/healthy или пропавших audit events.

**Q2-A08 — Observability и proof.** Какие invariant metrics (service health, last verified complete scan, source gap, pending age, durable generation/cycle status, commits, WAL/fdatasync) обязаны остаться доступны? Точное различие между *no-write because no effective change*, *no scan*, *source unavailable* и *retry pending*. Допускаются лишь bounded in-memory signals для измерений, если не требуют новых durable writes.

**Q2-A09 — Admission/order.** Условия выбора **одной первой маленькой гипотезы** только после независимой per-DB/per-operation матрицы; PASS/HOLD/RETURN criteria. При отсутствующей причинности Chief Architect должен вернуть `EVIDENCE_REQUIRED`, а не назначать Coder выдуманную оптимизацию.

### 4. Что собирает Tech Lead до code admission

- Повторный **10–15-минутный matched quiet baseline** после QIO-01B: одновременно guest per-service `io.stat`, host QEMU-cgroup и host `/dev/sda` completed writes/reads/await/busy, CPU/PSI, guest auth/client count и source freshness. Несколько окон, без искусственных writes/traffic.
- Read-only runtime/source inventory: DB path → owning service/worker → trigger cadence → specific SQL/transaction → fdatasync/checkpoint → observed guest/host contribution; обозначить measurement error и альтернативные объяснения. Тяжёлое SQL tracing/strace, WAL replay и failure injection — **только disposable Lab**.
- Отдельный Lab baseline и корректностные positive/negative tests для одного приоритетного кандидата; `no-op` не принимать по условию `row_count=0`, пустому журналу или неизменной цифре CPU.

### 5. Требуемый ответ Chief Architect

Вернуть **`QIO-02 SQLite Small-I/O Architecture Admission Contract v1`** с:

1. `DECISION=PASS / MODIFY / EVIDENCE_REQUIRED / REJECT` и явными preconditions;
2. matrix по DB/domain: authority class, exact write/commit semantics, owner, freshness/replay upper bound, allowed/forbidden suppressions;
3. приоритетной **условной** первой гипотезой и falsifiable evidence/gates, не с Coder GO;
4. scope boundaries/rollback и явно forbidden durability changes;
5. correctness C01…Cn и performance gate (matched guest/host; total host HDD writes/await/busy, per-DB syscall/commit evidence, auth/visit/current-state data correctness);
6. отдельно документировать cold-start risk vs steady-state writes; QIO-01D logging не сливать с QIO-02 SQLite scope;
7. machine-readable disposition (`ARCHITECTURE`, `LAB`, `CODER`, `PRODUCTION`, `OWNER_GO`).

**Normative state now:**

```ini
TASK=QIO-02
TRACK=SQLITE_SMALL_IO_CAUSAL_ATTRIBUTION
ARCHITECT_REQUEST=GO
READONLY_MEASUREMENT=GO_BOUNDED
LAB_EXPERIMENT=AFTER_EVIDENCE_AND_ARCH_ADMISSION
CODER=HOLD
PR_MERGE=NO
PRODUCTION_CHANGES=NO
DURABILITY_WEAKENING=FORBIDDEN
QIO_01D=SEPARATE_TRACK
SSR_01B_PR_215=UNTOUCHED
```

**Referenced material for Architect:** `CAPTIVPORTAL-PERF-IO-QUIET-LOAD-OPTIMIZATION-ROADMAP-v1.0-2026-10-15.md`; `CAPTIVPORTAL-QIO-01D-QIO-02-TECHLEAD-NEXT-STEPS-2026-10-16.md`; current `main` source read-only at `e2cbd96916d8a81f07f0d79a1a745f593ccb5114` (subject to new HEAD check).
