# CAPTIVPORTAL — PERF-IO / Architecture Contract R1
## NI-01: устранение повторных SQLite-lookup, write amplification и дорогих retention-сканов

**Status:** `FINAL CANDIDATE — FOR CHIEF ARCHITECT REVIEW`  
**Project:** CaptivPortal · Performance & Disk-I/O Optimization  
**Date:** 2026-10-14, Asia/Baku  
**Prepared by:** Performance & Optimization Researcher  
**Authorization:** Research complete for this candidate; **no Coder GO, no merge, no production change**. Architect → Tech Lead → Coder TASK → QA → Owner-gated production.  
**Scope:** NI-01 first. NI-02B / Fingerprint have independent follow-on disposition in §12; they are not silently changed by this document.

> **Решение в одном абзаце.** Главная причина текущей дисковой проблемы — не единичный ошибочный `pread64`, а постоянная конкуренция множества маленьких операций записи и индексных чтений на общем HDD. В NI-01 проверка identity для каждого входного события выполняется дважды, в его горячей вставке повторно запрашивается структура таблиц, а каждый fault обновляет SQLite агрегат отдельным SQL statement; вдобавок retention периодически читает большой индекс наблюдений с неподходящим планом. Предлагается **два самостоятельных ограниченных изменения**: PERF-IO-NI01-A (горячий ingestion) и PERF-IO-NI01-B (retention selection). Ни одно не меняет источники истины, SQLite схему, durability, пользовательский API или семантику checkpoint/replay. Доказанный эффект: уменьшение числа логических запросов, устранимое полное сканирование индекса при retention. Точная экономия физических IOPS является **release-gate, а не придуманным обещанием**.

---

## 1. Подтверждённый baseline и разделение доказательств

### 1.1 Точная идентичность

**Production:** Ubuntu VM `192.168.0.202`; Git checkout `HEAD=3b5f70cec467939995fecc7667169239000b7308`, `TREE=5d52a536adffe55475ec9dd9d4b3e2d7ea8eeb2b`, clean worktree. Гипервизор `omv-hp`, Debian/QEMU, исходный HDD `/dev/sda` с разделом `/dev/sda1` под VM disk.

Активные сервисы во время инспекции:

- `network-metadata.service` — PID 3690031; запущен 2026-10-12 22:43:19 AZST.
- `network-metadata-projection.service` — PID 2699780; запущен 2026-10-14 15:52:27 AZST.
- `network-service-recognition.service` (NI-04) — PID 2724752; запущен 2026-10-14 16:11:15 AZST.
- `fingerprint-evidence.service` — PID 165010; запущен 2026-10-08 15:14:06 AZST.
- `fingerprint-sensor.service` — PID 429953; запущен 2026-10-13 11:08:00 AZST.
- `captive-portal.service` — active.

**Loaded-artifact distinction:** Git checkout HEAD нельзя автоматически считать commit, загруженным всеми процессами. `app/network_metadata/{service,repository,retention,schema}.py` не менялись в Git с `d8250271...` (2026-10-12 21:52 AZST), то есть последнего изменения этих файлов **до** запуска NI-01. Тем не менее перед implementation/deploy Tech Lead должен сверить exact loaded artifact. Fingerprint Evidence запущен до изменения его repository в `edb99fc9...` от 2026-10-13 — текущий Git код не служит доказательством текущей загруженной реализации этого сервиса.

### 1.2 Переданное Tech Lead evidence

- На предыдущем тестовом интервале: EVE→NI-01 lag 8–9 мин; 18 из 20 stack samples — ожидание физического чтения SQLite (`pread64` / `wait_on_page_bit_common`).
- `vda` busy 95,8%; read/write await 57,7/136,2 мс; NI-01 DB ~3,55 GB; default SQLite connection cache ~2 MiB.
- За 60 с NI-01 ~41,4 MiB write I/O при продвижении EVE checkpoint на ~295 KiB.

Эти сведения поступили от Tech Lead через Owner; наши последующие измерения — **другие окна**, их числители и знаменатели нельзя смешивать.

### 1.3 Новый 60-секундный read-only замер Ubuntu VM

Sampling: `2026-10-14 17:17:39–17:18:39 AZST`, четыре последовательных 15-секундных интервала, итого 60,14 с. `io.stat`, cgroup v2, для guest `252:0` (vda). `253:0` — вложенная/альтернативная строка, **не суммировать** с `252:0`.

| Service / cgroup | Read ops / 60s | Write ops / 60s | Read bytes | Write bytes |
|---|---:|---:|---:|---:|
| NI-01 `network-metadata` | 357 | **2 760** | 1 679 360 | **45 064 192** |
| NI-02B `network-metadata-projection` | 0 | **1 283** | 0 | 19 505 152 |
| `fingerprint-sensor` | 16 | **1 009** | 65 536 | 7 049 216 |
| `fingerprint-evidence` | 325 | **910** | 1 339 392 | 8 585 216 |
| `systemd-journald` | 1 | 734 | 114 688 | 3 493 888 |
| Captive Portal | 121 | 356 | 495 616 | 1 556 480 |
| NI-04 `network-service-recognition` | 47 | 40 | 221 184 | 421 888 |

Guest `vda` из `/proc/diskstats` за то же окно: `Δreads=861`, `Δwrites=8151`; `Δio_ticks=56 120 ms` (~93,3% busy); `Δread_ticks=51 649 ms` (~60,0 ms/completed read), `Δwrite_ticks=2 367 616 ms` (~290,5 ms/completed write). Здесь время ожидания операций — **не** время CPU и **не** средняя latency каждого SQL.

NI-01 имеет приблизительно 33,9% *всех* guest vda completed write operations за окно; NI-02B — 15,7%, FP Sensor — 12,4%, FP Evidence — 11,2%; вместе эти четыре дали ~73,1% guest completed writes. Не переносить эту долю на другие часы без измерения.

За тот же 60,14-секундный guest-интервал `/proc/<pid>/io` NI-01 показывал `write_bytes=42 184 704`, `read_bytes=1 679 360`; guest cgroup может учитывать записи, перенесённые writeback, несколько иначе, чем PID. Это не две независимые нагрузки — складывать их нельзя.

### 1.4 Прямой 60-секундный замер физического HDD хоста

Separate **later** sampling window: `2026-10-14 17:28:57–17:29:57 AZST`, `omv-hp /dev/sda`, 60,01 s. `Δwrites=10 123` (~168,7 write IOPS), `Δreads=1261` (~21,0 read IOPS), `Δio_ticks=54 832 ms` (~91,4% busy), write await ~115,5 ms, read await ~46,2 ms. Ubuntu VM QEMU cgroup on host: `Δwrites=8423` (~140,4 wIOPS, **83,2%** `/dev/sda` completed writes), `Δwbytes=102 096 896` (≈97,4 MiB); Windows VM `Δwrites=615`. Host/guest данные собраны **в разные минуты**, между ними запрещено рассчитывать byte-for-byte коэффициент усиления.

**Вывод:** продуктивная Ubuntu VM — подтверждённый главный потребитель физического HDD, а не гипотетический посторонний торрент/Windows. Внутри Ubuntu явные основные направления — NI-01, NI-02B и Fingerprint.

### 1.5 Динамическая задержка: проблема не непрерывна

Однократное безопасное read-only открытие NI-01 DB через SQLite `mode=ro`, `query_only=ON`, timeout 0,2 s, **без сканирования таблиц**, в `2026-10-14T13:26:56Z` показало:

- Active generation `8628116a-75ad-4bbc-aa9f-10b15a800064`, `processing_state=runnable`.
- Durable NI-01 `committed_byte_offset=8 263 292`, `updated_at_utc=13:26:54.396573Z`.
- Открытый EVE-file descriptor процесса NI-01 имел **ровно 8 263 292 bytes**.
- Последний health: `metadata_ingest_health=usable`, `last_ingested_event_at=13:26:18.877637Z`.
- `page_count=873755`, `page_size=4096`, `freelist_count=0`, DB тогда ~3 578 900 480 B по page_count; `PRAGMA cache_size=-2000` у новой read-only SQLite connection. Writer code сам `cache_size` не меняет.

**Следствие:** в этот момент байтового backlog в открытом EVE-файле не было. Прошлые 8–9 минут — **эпизодическая задержка** при перегрузке/изменении нагрузки; не утверждать текущий непрерывный lag. `last_ingested_event_at` — event timestamp, не latency-секундомер (он зависит от наличия и часов источника).

### 1.6 Фактически активные flags

NI-01: `INGEST_COALESCE_ENABLED=true`, `MAX_MS=250`, `BATCH_MAX_RECORDS=256`, `BATCH_MAX_BYTES=1048576`, `TELEMETRY_AGGREGATION_ENABLED=true`.

NI-02B: `IDLE_WRITE_REDUCTION_ENABLED=true`, `CHECKPOINT_OPT_ENABLED=true`, `TELEMETRY_AGGREGATION_ENABLED=true`.

По journal за последние 15 мин `network-metadata` опубликовал 14 `success_summary` с суммарными `batch_count=213`, `record_count=5237`: примерно 14,2 batches/мин, 24,6 committed observations/batch в том отрезке. `record_count` **не** число всех сырых/отфильтрованных EVE records и не число COMMIT всей системы. У FP Evidence в том же окне 117 успешных evidence-batch и 25 source-health batch events; 3 069 `inserted` из агрегированных журналов, без утверждения о физической причинности каждой операции.

---

## 2. Классификация причин: не путать с корреляцией

| Signal | Status | Доказательство / ограничение |
|---|---|---|
| Физический HDD перегружен мелкими write IOPS | **OBSERVED** | host `/dev/sda` ~91% busy, 168,7 write IOPS; Ubuntu VM ~83% host writes |
| NI-01 много читает физические страницы SQLite при задержке | **OBSERVED, other interval** | трассировка Tech Lead 18/20 samples; отдельный наш 60s: 357 guest reads |
| NI-01 выполняет два identity-point SELECT на каждый record в обычном path | **SOURCE-PROVEN** | `service.py:poll_once`; `repository.py:ingest_batch → Phase A`, `identity_outcome` |
| Двойной SQL значит ровно двойное количество физического read I/O | **NOT PROVEN** | caching/readahead/page reuse; запрещено такой вывод делать |
| NI-01 регулярно читает структуру таблиц при каждом INSERT | **SOURCE-PROVEN** | `_insert()` → `PRAGMA table_info(table)` каждый вызов |
| NI-01 выполняет отдельный fault-UPSERT на каждый отвергнутый record | **SOURCE-PROVEN** | `_fault()` внутри Phase B |
| NI-01 retention может сканировать большой observation index | **QUERY-PLAN-PROVEN** | live `EXPLAIN QUERY PLAN`, §5; это **план**, не доказанная длительность конкретного retention run |
| Каждый гостевой idle-period создаёт ненужные NI-01 writes | **NOT PROVEN** | «0 посетителей» ≠ 0 Suricata-EVE; нет синхронного ночного guest-count/EVE/IO sample |
| NI-02B / FP должны просто перестать писать на диск | **REJECTED AS UNSAFE** | полезные derived/provenance/spool состояния, до проверки не считать лишними |

**Architecture priority:** лечить **путь NI-01 ingestion + периодический retention**, не отключать защитную инфраструктуру и не ослаблять commit/fsync.

---

# 3. PERF-IO-NI01-A — Hot Ingestion Cost Reduction

**Decision:** `RECOMMEND APPROVAL`; **scope:** `app/network_metadata/service.py`, `repository.py` и узкие tests; возможны внутренние helpers. Без изменения `schema.py`, normalizer semantic, external read contracts, scheduler, input filtering, CAPPORT или источника EVE.

## A1. Бounded identity-window probe вместо двух N-lookup loops

**Current:** service делает `identity_outcome(generation, outcome)` на каждом нормализованном record, останавливает preflight на первом conflict; `ingest_batch` заново выполняет те же indexed queries в transactional Phase A. Запрос на runtime DB:

```sql
SELECT digest_state, source_record_sha256, semantic_payload_sha256
FROM network_metadata_source_records
WHERE source_generation_id = ?
  AND record_start_byte_offset = ?;
```

В реально работающей DB query planner использует `sqlite_autoindex_network_metadata_source_records_2` (indexed SEARCH). Именно **многократный B-tree seek**, а не отсутствие индекса, является оптимизационной целью.

**Required algorithm — closed semantic decision:**

1. Уже считанный bounded список `records` (≤256 и ≤1 MiB) имеет исходные `start` offsets. В **preflight** в `service.py`, перед индивидуальной нормализацией, один раз спросить NI-01 repository, **есть ли хоть одна ранее persisted identity в интервале** `[first_record.start, last_record.start]` текущей exact generation.
2. Выполнить readonly `EXISTS`/`SELECT 1 ... LIMIT 1`, используя текущий composite primary key, без полного сканирования:

   ```sql
   SELECT 1 FROM network_metadata_source_records
   WHERE source_generation_id = ?
     AND record_start_byte_offset BETWEEN ? AND ?
   LIMIT 1;
   ```

3. Если строк нет, только для **этого preflight snapshot** считать каждую проверку `identity_outcome` равной `new`; нормализовать и строить outcomes как прежде.
4. Если хотя бы одна строка в интервале есть, preflight **целиком переходит на существующий per-record `identity_outcome` path**, включая stop на первом конфликте. Никакой попытки установить «дубликат» по одному лишь overlap/probe.
5. `ingest_batch` **обязательно вновь**, уже **после `BEGIN IMMEDIATE`**, выполняет самостоятельный bounded range probe для точных `outcomes`, независимо от результата service preflight. При пустом диапазоне disposition = `new` для всех outcomes. При непустом — точно прежняя per-record проверка в том же порядке с теми же conflict/duplicate/expired semantics.
6. Смена поколения, closed generation, input truncation, interrupted file, reader reset, blocked state и schema validation продолжают управляться текущими guards; range probe не может замещать `load_active`, continuity anchor, validation, crash recovery или cursor/checkpoint integrity.
7. Если probe получает ошибку SQLite, **fail closed** по принятой storage-unavailable policy. Никакого fallback «не прочитали, значит new».
8. При пустом диапазоне БД гарантия строится на `source_generation_id + start` exact identity и сохранении **единственного писателя**. Не добавлять process-global эвристический identity cache, который может пережить generation/migration/retention или ошибочно склеить Site/MAC.

**Expected logical query count (new-only batch of N records):** **2 bounded covering range probes total**, вместо ~`2N` exact identity SELECT. При reuse/retention/collision — дополнительный probe и исходный exact per-record path, безопасно дороже, чем сломанный replay. Подтверждённый `EXPLAIN` для range:

```
SEARCH ... USING COVERING INDEX sqlite_autoindex_network_metadata_source_records_2
(source_generation_id=? AND record_start_byte_offset>? AND record_start_byte_offset<?)
```

Это конкретный безопасный механизм сокращения read amplification. **Не обещать, что каждая устранённая SQL-команда соответствовала physical disk read:** измерить на одинаковой file-backed workload.

**Critical semantics preserved:** immutable `source_record_sha256`, `semantic_payload_sha256`, `digest_state='expired'`; `source_record_identity_conflict`, `normalizer_determinism_conflict`, `replay_identity_evidence_expired`, `duplicate_noop`; exact first conflicting offset and blocked checkpoint position; preflight stops normalizing at first conflict, transactional Phase A rechecks authoritative state; normalized identity is never made from IP-only inference; source generation scoped identity.

## A2. Startup-validated immutable column allowlist вместо PRAGMA на каждый INSERT

`NetworkMetadataRepository._insert` вызывает `PRAGMA table_info(table)` при каждой вставке (в `observations`, `source_records`, `sensitive_endpoints`, family-specific rows и дочерних DNS/ALPN). **Change:** после `validate_schema()` один раз прочитать таблицы/колонки из реально проверенной exact V1 schema в `self._insert_columns_by_table`, при recover/reinitialize пересоздать snapshot. Все последующие `_insert` проверяют `table in TABLE_DDL` и `values.keys() ⊆ cached_actual_columns`, после чего используют прежний параметризованный INSERT. Любая неожиданная таблица/колонка fail-closed как ранее.

- Никакой динамической DDL, таблиц, индексов или нового migration mechanism.
- Не переносить schema checks в каждый query; schema contract strict, writer единственный.
- Нельзя создавать cache до `validate_schema()` и использовать его после закрытия/повторного открытия connection.
- Результат: `PRAGMA table_info` со **всех hot inserts** переносится в bounded initialize, без удаления проверки allowlist.

## A3. Grouped fault UPSERT within existing ingest transaction

`_fault(generation, category, now, offset)` сейчас выполняет по одному:

```sql
INSERT INTO network_metadata_ingest_fault_aggregates (..., count, first_seen, last_seen,
 first_relevant_offset, last_relevant_offset)
VALUES (...,1, ...)
ON CONFLICT (...) DO UPDATE
SET count=count+1,
    last_seen_utc=excluded.last_seen_utc,
    last_relevant_offset=excluded.last_relevant_offset;
```

**Change:** в Phase B в том же транзакционном `plan` собрать fault items в bounded accumulator по **точному существующему primary key** `(logical_source_id, source_generation_key, fault_category, aggregation_epoch_start_utc)`. Для каждой группы держать `{count, first_offset, last_offset, now}`, не более числа processed outcomes (≤256). После обработки плана, но **до** checkpoint UPDATE/COMMIT, исполнить один equivalent UPSERT на каждую группу: `count=count+excluded.count`, старые `first_seen_utc` и `first_relevant_offset` при конфликте **не изменять**, `last_seen_utc` и `last_relevant_offset` установить по последнему fault той группы.

**Exact effects remain:** сумма fault counts, пятьминутная bucket semantics, logical/generation identity, first/last relevant offsets и timestamps, original batch-size bounds, blocking/conflict, diagnostics, immutable normalized facts. При любой ошибке — rollback **всего** batch, включая новые observations и checkpoint. Fault-aggregation не становится async/fire-and-forget и не создаёт отдельного неконтролируемого durable буфера.

**Expected logical SQL reduction:** при F faults в G distinct key buckets — `F` → `G` UPSERT внутри одного существующего COMMIT. Экономия physical writes может быть меньше, чем разница SQL calls, если один page уже dirty в transaction; измерять, а не декларировать.

## A4. Explicit non-goals A

- **НЕ** удалять transaction, `BEGIN IMMEDIATE`, `COMMIT` или checkpoint atomicity.
- **НЕ** уменьшать SQLite `synchronous=FULL`, не менять WAL journal mode / `wal_autocheckpoint=1000`, не переносить checkpoint за durable results.
- **НЕ** пропускать replay conflict checking, не полагаться на source offset без generation.
- **НЕ** удалять отдельные observability/source-health/fault записи, не менять retention TTL.
- **НЕ** менять нормализатор, source-scope filtering, Suricata, Fingerprint source path или EVE content.
- **НЕ** увеличивать `batch_max_records/bytes`, менять scheduling/coalescing timers — они уже включены и требуют отдельного доказательства.
- **НЕ** добавлять новые DB/index/table, external queue, Redis/Postgres, SSD.

### A5. Operational gate

Под одним отдельным default-off rollout gate `NETWORK_METADATA_IO_HOTPATH_V1_ENABLED=false` объединить A1+A2+A3 с точным typed config parsing (`true/false` only); disabled mode побайтно эквивалентен прежнему. Для enabled mode состав обработки изменён **только** производительностью, не persist semantics. В `configuration_digest` указанное значение по умолчанию false должно сохранять legacy identity, enabled должен однозначно отражаться в создаваемой run configuration identity. Нет «самовключения» после code deployment, отдельная Owner activation. Нельзя позволить переключение посреди одного процесса без restart/composition.

Не добавлять много независимых флагов: локальные isolated microbenchmark и fault-injection тесты могут сравнивать helpers отдельно, production activation — одна обратимая оптимизация. Все paths still strict: unknown env value aborts NI-01 startup safely; Guest Portal stays independent.

---

# 4. PERF-IO-NI01-B — Retention Indexed Selection

**Decision:** `RECOMMEND APPROVAL`, **independent** from A.  
**Scope:** `app/network_metadata/retention.py`, focused tests; **no schema/index change**.

## B1. Source of read amplification

Сегодня `_select("sensitive"|"core")`:

```sql
SELECT observation_id
FROM network_metadata_observations
WHERE (event_at < ? OR ingested_at < ?)
  [AND sensitive_endpoint_presence_state != 'expired']
ORDER BY observation_id LIMIT 5000;
```

**Measured via live `EXPLAIN QUERY PLAN`, no query execution:**

```
SCAN network_metadata_observations
USING INDEX sqlite_autoindex_network_metadata_observations_1
```

В таблице 3.5+ GB это потенциально дорогой проход через большой observation-id индекс. При малом числе истекших строк `LIMIT` не гарантирует короткое выполнение. Это точный, независимо от двух identity lookups, дефект **query shape**. Для сравнения, удаление `ORDER BY observation_id` в том же read-only EXPLAIN переключило SQLite на `MULTI-INDEX OR` с `idx_nm_observations_event` и `idx_nm_observations_ingested` — существующие индексы, новая DDL не требуется.

## B2. Accepted indexed algorithm

Чтобы одновременно обеспечить индексный проход, строго ограниченный объём результата и детерминизм **без** разрастания temporary DISTINCT/UNION, реализовать **две index-ordered, bounded ветки** в `_select` для sensitive/core:

1. `SELECT observation_id,event_at,ingested_at FROM network_metadata_observations WHERE event_at < cutoff [AND state != 'expired'] ORDER BY event_at,observation_id LIMIT 5000` — реально существующий `idx_nm_observations_event`.
2. `SELECT observation_id,event_at,ingested_at FROM network_metadata_observations WHERE ingested_at < cutoff [AND state != 'expired'] ORDER BY ingested_at,observation_id LIMIT 5000` — существующий `idx_nm_observations_ingested`.
3. В bounded process-local памяти объединить candidate observation IDs (максимум 10 000 прочитанных строк), без SELECT per candidate, выбрать **самые старые** по `(min(event_at,ingested_at), observation_id)` не более 5 000; исполнить **существующий** `_delete` без изменения semantics, количества transaction chunks и `RETENTION_MAX_BATCHES_PER_PASS=20`.
4. При timeout/SQLite error не объявлять retention successful и не перепрыгивать список. Следующий проход возобновляется обычным existing retention invocation, persisted checkpoint NI-01 не изменяется по причинам ошибки retention.

**Correctness proof (why 5k per branch suffice):** если earliest timestamp записи определяется `min(event_at, ingested_at)`, любая запись, не вошедшая в первые 5 000 ни одной ветки, имеет не менее 5 000 других eligibility records не моложе себя в ветке, соответствующей её min timestamp. Поэтому такая запись не может войти в глобальные 5 000 самых ранних по `(min_timestamp,id)` (включая deterministic tie-break). Никакие eligible records не удаляются преждевременно; все eligible получают возможность удаления в последующих passes. Список при этом остаётся bounded независимо от общего числа строк.

**Сохранить**: `event_at < cutoff OR ingested_at < cutoff` (не превращать в `AND`), 14d sensitive + 30d core, `sensitive_endpoint_presence_state!='expired'` для sensitive, прочие категории/приоритеты, 5k limit, max 20 transaction batches, capacity headroom, cascading FK, digest-state expiration semantics, source generation. Изменение порядка выбора с `observation_id` на `oldest eligible` — **явное внутреннее архитектурное решение**; результат retention не имеет пользовательской гарантии прежнего observation-ID порядка.

**IMPORTANT LIMITATION:** индексные ветки могут читать много уже-`expired` sensitive rows (state predicate не входит в existing time index). Новый индекс сейчас **не добавлять**, потому что он увеличит стоимость каждого NI-01 write. Если bounded lab и production evidence покажет неприемлемый scan на этом префиксе, второй index design возвращается Architect как отдельная, измеренная migration trade-off, а не stealth schema change.

### B3. Exact query-plan / capacity gates

- Две ветки должны иметь `SEARCH ... USING INDEX idx_nm_observations_event (event_at<?)` и `...idx_nm_observations_ingested (ingested_at<?)`, **не** table/full ID-index SCAN.
- Каждая ветка `LIMIT <=5000`, memory ≤10 000 candidate records до дедупликации.
- Формальный equivalence test должен доказать eligibility predicates и eventual completeness, включая противоположный порядок `event_at/ingested_at`, равные timestamps, rows already expired, zero candidates, 5k boundary, ~20k candidate fixture.
- При production activation ни одна retention run не должна непредсказуемо задерживать NI-01 ingestion, и совокупный NI-01 read bytes/op during hourly retention должны быть ниже исходного сопоставимого baseline. Если нагрузка растёт — rollback B, без изменения retention deadlines или source checkpoint.

### B4. Rollout gate

Независимый default-off `NETWORK_METADATA_RETENTION_INDEXED_V1_ENABLED=false`; enabled case делает исключительно B2 selection, disabled — unchanged SQL. Новый флаг не изменяет существующую schema и не является «разрешением» на удаление данных вне стандартной политики. Активация под Owner-controlled deploy, rollback через return to disabled + approved restart. Не менять эти flags через Admin UI.

---

# 5. Что намеренно НЕ предлагается как решение сейчас

1. **Заменить HDD на SSD:** скроет ошибки чтения/коммитов и IOPS-конкуренцию, не решает архитектурную причину.
2. **Поменять `synchronous=FULL` на NORMAL/OFF**: неприемлемая смена crash/durability guarantees.
3. **Двигать EVE/NI-02B/NI-04 cursor вперёд заранее:** запрещено. Никакой потерянной или ложно считанной `complete` информации.
4. **Удалить из схемы множественные secondary indexes вслепую:** может сломать read services, correctness и дать дорогую migration. Требуется отдельное сравнение read/write/retention trade-off.
5. **Увеличить SQLite page cache и объявить проблему решённой:** в 8 GB VM на момент probe ~5.78 GB MemAvailable, writer явно `PRAGMA cache_size` не переопределяет, а read-only SQLite connection имеет default `-2000` KiB. Это оправдывает **будущий** bounded opt-in cache experiment (например 32 MiB только writer), но после устранения бессмысленных SQL/retention scans. Этот контракт **не разрешает** менять cache-size в production.
6. **Переизобрести durable source checkpoint или fault store:** source-of-truth/retention/lineage contracts остаются под Chief Architect.
7. **Перенастроить Suricata/capture VLAN, фильтровать upstream, остановить Fingerprint:** изменение иных frozen domains без доказанной необходимости запрещено.
8. **Убрать NI-02B, Fingerprint и portal writers:** их записи могут быть necessary authoritative/derived facts. Отдельные оптимизации после изоляции вклада NI-01.

---

# 6. Correctness, recovery, security invariants — hard freeze

| Domain | Must remain |
|---|---|
| NI-01 durability | SQLite WAL, `synchronous=FULL`, single writer + writer lock; no raw uncommitted checkpoint advancement |
| Batch atomicity | normalized facts + immutable record identity + fault aggregate + health + generation + source checkpoint **one existing transaction** |
| Source replay | generation-scoped `(source_generation_id,record_start_byte_offset)` identity, digest comparison, expired identity fail closed |
| Conflict | first conflict stops prefix; `blocked_reason_code`, `blocked_record_start_byte_offset`, cursor exact |
| Crash/restart | crash before COMMIT retries same source prefix; crash after COMMIT reuses durable checkpoint; reader reset/continuity anchor unchanged |
| Source provenance | raw SHA/digest, observation UUID, `run_id`, `health_ref`, Site/scope contract unchanged |
| Privacy | no raw SNI/DNS/MAC/IP new telemetry; no persistent packet archive; state of `observed_retained/expired` unchanged |
| Multi-Site | no global identity cache; generation+exact source offset key remains authoritative |
| Retention | 14d/30d/45d/90d classes, sensitive/core eligibility, bounded deletes, foreign key cascades unchanged |
| NI-02B/NI-04 | existing readers and source cursor remain compatible; unchanged read DTO, schema, source-health semantics and downstream materialization |
| Portal | CAPPORT/auth endpoints and startup must not be blocked by NI-01 optimization fault; existing independent failure boundaries |
| SQLite/schema | V1 signature, `PRAGMA user_version`, all indexes and FK preserved; no migration |

---

# 7. Required QA / evidence matrix for Tech Lead implementation TASK

The Tech Lead shall convert the following gates into deterministic tests without reopening architecture choices.

**A1 identity probe:**

- A1-T1 all-new batches `N=1,2,256`: preflight and in-transaction each execute **one indexed `EXISTS` probe**, with zero exact lookup SQL; identical DB/checkpoint/health to legacy.
- A1-T2 boundary duplicate at first/middle/last record: fallback exactly preserves old `duplicate_noop`, source digest, cursor and emitted bounded telemetry.
- A1-T3 tampered raw digest, tampered semantic digest, expired digest at first/middle/last position: exactly legacy fault enum, blocked prefix, no succeeding record commit.
- A1-T4 preflight `EXISTS` empty, transactional probe sees row inserted/changed (simulated permitted single-writer test fixture/hook): Phase A **never** trusts preflight; existing conflict semantics win.
- A1-T5 existing row only between two incoming record starts: fallback exact identity checks (no false collision, no source-offset shortcut).
- A1-T6 generation rotation, truncation, source absence, crash at every existing crash point, recovery/replay, `NetworkMetadataStorageUnavailable`, corrupted DB signature: fail closed, no cursor jump.
- A1-T7 `source_record` expired identities with replay: remains `replay_identity_evidence_expired`, not new.

**A2 column cache:**

- A2-T1 all observation families and optional DNS query/answer, TLS ALPN inputs: same complete SQLite rows and read DTOs.
- A2-T2 invalid/unknown table and invalid column: same validation error.
- A2-T3 mocked schema drift/recover/connection reopen resets cache; never accepts stale schema.
- A2-T4 trace proves `PRAGMA table_info` absent from runtime `_insert` hot path, still present during exact schema validation/init.

**A3 faults:**

- A3-T1 1/10/256 same-category faults: exact count, first/last offsets, epoch bucket and timestamps.
- A3-T2 mixed categories, multiple existing aggregates, edge at five-minute epoch boundary: exact legacy rows.
- A3-T3 valid + faults + duplicate + conflict in same batch; crash before/after checkpoint and fault UPSERT; one atomic result or rollback.
- A3-T4 counted faults not secretly skipped by filtered outcome, source checkpoint never advanced beyond durable fault result.

**B indexed retention:**

- B-T1 live-equivalent `EXPLAIN QUERY PLAN` of BOTH indexed branches, no table/PK full index scan.
- B-T2 compare eligibility against legacy for 0/1/5000/5001/20000 rows: complete selection over repeated passes, no too-young rows.
- B-T3 late ingest `event_at` old / `ingested_at` recent and reverse; OR semantics preserved.
- B-T4 sensitive-to-expired-to-core TTL transition remains exactly the legacy state machine/digest expiry.
- B-T5 20×5000 bounded chunks, capacity pressure, read-only consumer concurrently holding WAL snapshot, source unavailable; no unbounded read, deadlock, unsafe truncate or stale checkpoint.
- B-T6 schema/layout unchanged; child cascade and NI-02B/NI-04 readers recover after retention.

**End-to-end:**

- Reuse exact frozen normalized EVE fixture, including DNS/TLS/QUIC, filtered events, backfill, duplicates, corruption and non-faulted cases. Run legacy vs A+B candidate in separate *file-backed* lab SQLite stores, compare canonical DB read DTOs/health/checkpoints/aggregates (ignore internal performance/retention-selection-order only).
- Test repeated crash recovery and deliberate injection at existing crash hooks. No unexpected source generation split, cross-Site/identity merge, lost replay or newly created false-positive service recognition.
- No heavy/profiling test on production database; performance stress on synthetic/copied **offline** store only under authorized capacity envelope.
- Existing targeted suites first, then integration/regression; no high-risk mass production `COUNT(*)`, `VACUUM`, `ANALYZE` or live `PRAGMA integrity_check`.

---

# 8. Production acceptance: compare normalized cost, not raw totals

**No implementation task or production activation until Chief Architect review and separate Owner-controlled gates.** Suggested safe rollout: accept A in tests → deploy code default OFF → baseline current settings → Owner enable A → verify → accept B separately → Owner enable B → compare. Require Git `HEAD/TREE`, actual loaded process artifact, current flags, clean checkout and rollback plan before any change. Revisions of `main` require Tech Lead re-pin / diff review.

**Baseline capture** (short, bounded windows with same methodology and no per-event tracing on HDD): synchronized host `/dev/sda` diskstats and host `Ubunt` QEMU cgroup, guest `vda` + service cgroup `io.stat`, `/proc/PID/io`, EVE file size and durable checkpoint offset, 60s `success_summary` counters and availability/latency health. Include one low-traffic and one daytime workload if actually available; do **not** label daytime as no-visitors or assume future night metrics.

**Compute both absolute and normalized:** writes/sec, reads/sec, read/write await, host busy, bytes per committed normalized observation, bytes and SQL statements per filtered/fault input outcome, batches per minute, checkpoint progress/sec, backlog bytes, tail-to-commit age when input event timestamps allow it, WAL main-write checkpoint throughput. Accounting basis must be the **same interval** and same cgroup/host level; never divide host bytes by guest source bytes from different minutes. Negative values/dirty writeback attribution must be interpreted cautiously.

**Positive gate A:** exact identity SQL execution count reduces from ~`2N` to 2 probes in all-new batches; `PRAGMA table_info`/INSERT becomes init-only; fault SQL count reduces from F to grouped G in repeated categories. Must also show **measured reduction** in physical read/write IOPS, physical bytes per comparable admitted workload, write-await, or backlog-recovery throughput on at least one representative workload without statistically meaningful regression elsewhere. No unearned fixed percentage promise. If no physical improvement, do not declare Disk-I/O problem solved: capture reasons, keep gate HOLD for further architectural review.

**Positive gate B:** proof of indexed query plans and bounded 10k candidate selection; observed retention run I/O + duration improve relative to equivalently aged/data-filled file-backed baseline. Ensure normal ingestion latency is not worsened, and no stale sensitive data remains past retention acceptance bounds. If source DB ages into large already-expired prefix, fail admission / return to Architect for a separately proved indexing/cursor strategy.

**Hard stop / rollback triggers:** elevated EVE checkpoint lag or queue age compared to matched baseline; any missed/double admission; mismatch of immutable observation/identity hashes; unexpected `blocked_conflict`; failed replay/crash QA; increased incomplete NI-02B/NI-04 coverage; capacity/retention failure; sustained HDD IOPS/await regression; Portal/CAPPORT service degradation. Disable only approved feature gate under controlled restart/rollout, not direct DB surgery.

**Expected target outcome:** lower small-I/O/read amplification in NI-01 and less periodic retention scan cost. This is **not** a claim that every write from a 3.5-GB normalized database is redundant; useful multitable/index persistence inherently amplifies source input bytes.

---

# 9. Ownership, authority and change ordering

- **Chief Architect**: accept/return A1/A2/A3, B2, exact failure/replay semantics and protected invariants.
- **Tech Lead**: on Architect acceptance write independent, reviewable Coder tasks `PERF-IO-NI01-A` and `PERF-IO-NI01-B`; verify actual loaded artifact vs current checkout; test + QA; obtain Owner approval per deployment phase.
- **Coder**: feature branch and tests only, no prod; no autonomous scope expansion or schema/SQLite durability change.
- **SysAdmin**: bounded read-only synchronized host/guest performance acceptance; production changes only on explicit Owner authorization.
- **Owner**: rollout and actual acceptance, no silent feature enable or migrations.

**Sequencing:** A first for the continuously running hot ingestion path, B independent for periodic scan; deploy separately to attribute gains. Do **not** mix new Fingerprint work, NI-02B schema, or NI-04 materialization features into these PRs.

---

# 10. Decision questions closed for Architect review

1. Should we trust outside-preflight result inside transaction? **No**; always re-probe under `BEGIN IMMEDIATE`.
2. Should we skip identity checks for replay/expired? **No**; fallback to exact legacy path when range has any existing row.
3. May we decouple checkpoint from new committed facts/fault aggregate? **No**.
4. May we change source/normalized semantics, retention TTL, secondary indexes or schema? **No**.
5. Are we allowed to loosen SQLite durable writes? **No**.
6. Can we drop per-event fault updates? **Only regroup to one UPSERT with identical durable count/first/last semantics in the same transaction**.
7. Does retention need lexicographic observation-ID deletion order? **No externally guaranteed order exists**; recommend explicit oldest-eligible internal order while preserving eligibility, 5k limit and class priority.
8. Do we need SSD/additional daemon/external DB? **No**.
9. Is the 8–9-minute lag still continuous right now? **Not proved**; at 13:26:56Z snapshot the durable checkpoint had caught up to the open EVE fd size.
10. Can NI-02B/FP optimizations be rolled into NI-01 PR? **No**; they own independent persisted semantics.

---

# 11. Exact Tech Lead handoff / review verdict

```text
CONTRACT = CAPTIVPORTAL-PERF-IO-ARCHITECTURE-CONTRACT-R1
BASE_HEAD = 3b5f70cec467939995fecc7667169239000b7308
BASE_TREE = 5d52a536adffe55475ec9dd9d4b3e2d7ea8eeb2b
EVIDENCE = READ_ONLY_SOURCE + LIVE_SQLITE_EXPLAIN + GUEST_CGROUP_60S + HOST_QEMU_60S
RECOMMENDED_CHANGE_A = NI01_BOUNDED_IDENTITY_RANGE_PROBE + INSERT_COLUMN_CACHE + GROUPED_FAULT_UPSERT
RECOMMENDED_CHANGE_B = NI01_TWO_INDEXED_RETENTION_CANDIDATE_STREAMS
DATABASE_SCHEMA_CHANGE = NO
DATABASE_DURABILITY_CHANGE = NO
CHECKPOINT_OR_IDENTITY_SEMANTICS_CHANGE = NO
NI02B_NI04_PORTAL_FINGERPRINT_SOURCE_CHANGE = NO
PRODUCTION_MUTATION = NONE
ARCHITECTURE_STATUS = FINAL_CANDIDATE_FOR_CHIEF_ARCHITECT_REVIEW
CODER_GO = NO
OWNER_PRODUCTION_GO = NO
NEXT = CHIEF_ARCHITECT_DECISION -> TECH_LEAD_EXACT_TASKS -> CODER/QA -> OWNER_GATED_RELEASE
```

## 12. Отдельные компоненты: самостоятельное направление, пока без разрешения на изменения

| Component | Confirmed live contribution | Source-grounded hypothesis / result | Disposition |
|---|---|---|---|
| **NI-02B** | 1283 guest write ops/60s; 19.5 MB guest wbytes, idle flags already ON | `commit_dispositions` пишет derived edges, pending, Registry bindings и checkpoint атомарно. `reconcile` выполняет transaction по расписанию, а idle durable state ограничен ~10 s. Это реальные writes; доля бессмысленных не установлена. | **RESEARCH NEXT / separate Architect contract only after attribution.** Не трогать source checkpoint, Registry authority, feed delivery и NI-04 binding-change sequence. |
| **Fingerprint Evidence** | 910 guest writes + 325 reads/60s; 117 evidence-batches + 25 health-batches/15min | In checked Git repository `_ingest` делает one transaction per received HTTP batch with identity dedup/atomic watermark. **Но** running service старше relevant Git source update; loaded implementation must be pinned first. | **RESEARCH NEXT**: producer batches, duplicate/no-op commits, watermark and durability. Никакого авторизационного изменения до loaded artifact match. |
| **Fingerprint Sensor** | 1009 guest writes/60s | Local transport spool SQLite `DELETE`+FULL, bounded atomic coalescing/stale purge gating; требуется подтверждение loaded wave2 flags/real enqueue rate, иначе нельзя заключить, что commits «бесполезны». | **RESEARCH NEXT**, no sensor ack/queue durability changes. |
| **Captive Portal** | 356 guest writes/60s | Source of protected guest authorization and various derived/UI services; no proven pointless write. | **PROTECTED / P2**, не оптимизировать по одному числу. |
| **journald** | 734 guest writes/60s | Shared operational logging. 15m NI-01 success telemetry is already aggregated, thus no simple per-event logging root cause from NI-01. | **P2**; avoid disabling audit/health logging. |

**Owner night observation:** при 0–1 посетителе HDD около 50% busy и host load 3–4 — правдоподобная, но ещё не независимая синхронная выборка. Source path/architecture позволяет фоновый EVE, health, retention, retry, reconciliation и Fingerprint независимо от числа посетителей. Запрет на «пустой Wi-Fi ⇒ не писать никогда»: это могло бы потерять source provenance. Допустимое дальнейшее архитектурное исследование — *confirmed no-change / duplicate / filtered / heartbeats* по каждому потребителю, включая реальные quiet windows.

**Финальный исследовательский вердикт:** для NI-01 выявлены **два самостоятельных, конкретных и testable источника лишней работы** (hot identity/SQL+fault path и retention query plan). Представлены замкнутые варианты изменения и приёмки. Всё остальное оставлено вне scope до причинного доказательства, чтобы избежать ложного обещания «один патч исправит все IOPS».
