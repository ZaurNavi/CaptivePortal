# CAPTIVPORTAL — PERF-IO / NI-01 Architecture Contract R2
## Chief Architect FINAL · передача TechLead23

**Дата:** 2026-10-14 (Asia/Baku)  
**Источник ревью:** `CAPTIVPORTAL-PERF-IO-ARCHITECTURE-CONTRACT-R1-2026-10-14(1).md` (Performance & Optimization Researcher)  
**Решение:** **`MODIFY → APPROVE`**. Этот документ R2 **заменяет** R1 как нормативный архитектурный контракт для подготовки implementation TASK. R1 остаётся исследовательским/evidence приложением.  
**Рабочие пакеты:** `PERF-IO-NI01-A` (ingestion) и `PERF-IO-NI01-B` (retention), **раздельные изменения и независимая активация**.  
**Статус:** `ARCHITECT_ACCEPTED / READY_FOR_TECH_LEAD_TASK`. **Не означает** `CODER_GO`, merge, изменение configuration/production, stop/start сервиса или запуск производительных тестов на рабочей VM.  
**Research baseline:** `HEAD=3b5f70cec467939995fecc7667169239000b7308`, `TREE=5d52a536adffe55475ec9dd9d4b3e2d7ea8eeb2b`, по R1. Tech Lead обязан заново подтвердить HEAD/TREE перед фиксацией implementation base.  
**Проверка Главным архитектором:** содержимое `app/network_metadata/service.py`, `repository.py`, `retention.py`, `schema.py`, `config.py` и модели проверено в GitHub **именно на указанном commit**. Live host sampling, cgroup, host diskstats, current loaded process identity и EXPLAIN на production не повторялись архитектором; для этих фактов авторитет — отчёт R1, а не независимый повторный замер.

---

## 1. Архитектурный вердикт и границы утверждений

1. **A: APPROVED** — один bounded indexed range probe в preflight плюс **независимый повторный probe под `BEGIN IMMEDIATE`**, immutable validated insert-column allowlist, grouped fault UPSERT. Все три оптимизации входят в **один default-OFF** deployment flag A; rollback A атомарный на уровне поведения процесса.
2. **B: APPROVED AS IMPLEMENTATION DESIGN; ACTIVATION GATED** — две ограниченные индексные выборки вместо scan по `observation_id` в `sensitive/core` retention. **Отдельный default-OFF flag B**, отдельные QA/performance gates. При неуспехе на `already-expired` данных B остаётся OFF, и R2 не даёт полномочий добавлять индекс или менять schema.
3. R1 установил наличие дорогостоящих *операций*, но не измеренный причинный вклад каждого SQL в физический HDD IOPS. Запрещено обещать фиксированную экономию IOPS/latency и утверждать, что этот PR снимает нагрузку всего хоста. Подтверждение физического эффекта — обязательная проверка до production activation.
4. Сохраняются `NI-01` source-of-truth, exact single-writer, SQLite V1, FULL durability, replay/continuity, retention TTL, внешние read contracts. `NI-02B`, `NI-04`, Fingerprint, Portal, Omada, CAPPORT, Visitor Registry, sensor/Suricata — **не в scope**.
5. Новых миграций, таблиц, индексов, SQLite PRAGMA для ослабления durability, служб, фоновых воркеров, новых API и источников данных **нет**.

## 2. Evidence status (строгое различение)

**R1: production measurements, read-only (reported, не повторялись в этом ревью):**

- Guest Ubuntu cgroup sample 2026-10-14 17:17:39–17:18:39 AZST: NI-01 2 760 guest write ops / 45 064 192 write bytes за ~60 s; NI-02B 1 283 ops; fingerprint sensor 1 009 ops; fingerprint evidence 910 ops. Guest `vda` ~93,3% busy в этом окне.
- Отдельный host `/dev/sda` интервал 17:28:57–17:29:57 AZST: ~91,4% busy, ~168,7 write IOPS; QEMU Ubuntu VM host-cgroup accounted ~83,2% host completed writes этого позднего окна. **Нельзя смешивать bytes и rates этих разных временных окон**, удваивать process+cgroup accounting или приписывать все host writes NI-01.
- 2026-10-14 13:26:56Z отдельный NI-01 DB source checkpoint совпал с размером открытого EVE descriptor; этот факт **не доказывает** отсутствие периодических задержек.
- Production EXPLAIN (передано R1): существующий `ORDER BY observation_id LIMIT 5000` в `sensitive/core` использовал `SCAN ... sqlite_autoindex_network_metadata_observations_1`; это *query plan evidence*, а не duration профилирование выполненного retention.

**Git source independently verified on research HEAD:**

- `service.py:poll_once` вызывает `identity_outcome()` для каждого нормализованного record до `ingest_batch()`; `repository.py:ingest_batch()` повторяет её для каждого outcome в Phase A внутри transaction.
- `repository.py:_insert()` выполняет `PRAGMA table_info(table)` на каждую вставку.
- `repository.py:_fault()` выполняет отдельный `INSERT ... ON CONFLICT DO UPDATE` на каждый новый fault.
- `retention.py:_select()` для sensitive/core содержит `WHERE(event_at<? OR ingested_at<?) ... ORDER BY observation_id LIMIT 5000`; schema содержит `idx_nm_observations_event` и `idx_nm_observations_ingested`.
- Основной batch существующего `repository.py:ingest_batch` оборачивает `candidate.ensure`, Phase B, `checkpoint`, generation update **одной transaction**. Новая оптимизация обязана это сохранить.

**Architecture interpretation:** постоянная конкуренция за HDD подтверждена на конкретных интервалах, но доли cgroup и SQL-частоты не являются доказательством одинаковой доли физических IOPS; порядок исправления NI-01 выбран по воспроизводимым source-level операциям и bounded риску.

## 3. PERF-IO-NI01-A — нормативный алгоритм

### A1. Generation-scoped bounded identity range probe

**До normalizer preflight:** после существующих source lifecycle/continuity guards и получения уже ограниченного batch `records` (не более 256 records и лимита retained bytes) один **read-only** indexed probe с ключом:

```sql
SELECT 1 FROM network_metadata_source_records
 WHERE source_generation_id = :generation_id
   AND record_start_byte_offset BETWEEN :first_start AND :last_start
 LIMIT 1;
```

Только **при гарантированно пустом результате** preflight допускается эквивалент `identity_outcome = new` для каждого последующего outcome данного batch. Все проверки normalizer и текущие source guards остаются. Если найден **любой** row в диапазоне (даже на offset, не совпадающем с offsets текущих records) — весь preflight переходит в **исходный ordered per-record `identity_outcome` path**, включая остановку на **первом** конфликте и неизменные категории. Query exception/invalid result → storage-unavailable fail-closed; никогда не трактовать как отсутствие ряда.

**Внутри `ingest_batch`** после `BEGIN IMMEDIATE` (после существующей validation/bounds проверки) выполнить **новый независимый** range probe по `outcomes` в том же exact `source_generation_id`. Нельзя использовать результат вне транзакции как доказательство transactional state. Пустой диапазон ⇒ новые identities; непустой ⇒ исходный ordered per-record проверочный алгоритм. Проверку correctness/replay нельзя заменять cache, checkpoint offset, source file identity, site IP или догадкой.

**Invariant:** при all-new batch размером N — ровно **1 preflight + 1 transaction range probe**, **0 per-record identity SELECT**, если test fixture не имеет persisted identity в проверяемых диапазонах. Это экономия *SQL statements*, не гарантированная экономия физических reads. При overlap допустима цена дополнительного probe и полностью исходная логика. Сохраняются exact `source_record_sha256`, `semantic_payload_sha256`, `digest_state=expired`, `duplicate_noop`, `source_record_identity_conflict`, `normalizer_determinism_conflict`, `replay_identity_evidence_expired`, первый конфликтующий offset, blocked checkpoint, `source_generation_id` isolation.

**R2 уточнение:** схема тестов, имитирующих row insertion между preflight и transaction, — **fault-injection only**, не разрешение запускать второй writer против реального single-writer lock. Конкурентное внештатное изменение SQLite не становится нормальной эксплуатационной моделью.

### A2. Insert-column validation cache с lifecycle ownership

В `NetworkMetadataRepository.initialize()` **после успешной точной** `validate_schema()` подготовить immutable/closed `table -> allowed columns` для всех `TABLE_DDL` из **validated actual connection**. До этого cache не authoritative. `_insert()` продолжает запрещать таблицы вне `TABLE_DDL` и колонки вне validated allowlist; parameterized INSERT остаётся неизменным. `PRAGMA table_info(table)` на каждую вставку больше не нужен **только в режиме A=ON**.

- При `close()` состояние cache инвалидируется; `recover()/initialize()` переинициализирует заново **только после** успешной schema validation. Не переносить snapshot между connections/DB files.
- Любая ошибка introspection, validation, невозможность initialize cache — **fail closed**, не fallback к «довериться SQL».
- Физический/административный DDL drift после validated startup **не поддерживается**, поскольку writer владеет schema и сторонняя мутация запрещена. Не делать unbounded schema check на каждом `_insert`; SQLite errors по-прежнему прерывают transaction. Tests обязаны покрыть изменение schema до нового initialize, повторное открытие, ошибочный table/column.
- Не создавать второй mutable глобальный list/cross-run allowlist.

### A3. Fault accumulation within existing committed batch

**Scope только Phase B** существующего `ingest_batch()` и **только реально достигнутый** префикс исходного `plan`, включая остановку на первом конфликте. Вместо непосредственного per-record `_fault()` при A=ON накопить группы ключа:

```text
(logical_source_id, source_generation_key, fault_category, aggregation_epoch_start_utc)
```

Для группы собирать `count`, **первый и последний offset в фактическом order**, `first_seen_at=last_seen_at=transaction_now` текущего единого transaction timestamp; текущие правила определения bucket (5 минут, UTC) не меняются. **После Phase B и до existing `before_checkpoint_update` crash hook**, выполнить один equivalent UPSERT на группу, параметризованно и детерминированно. Для уже существующей группы `count = count + added_count`; старые `first_seen_utc`/`first_relevant_offset` оставлять, `last_seen_utc`/`last_relevant_offset` обновлять как делал последний legacy fault.

- Поведение invalid category проверяется **при добавлении fault**. При ошибке — rollback всего batch, без успешного checkpoint.
- Применение `expire_touched_identity`, вставки normalized facts, mutable `candidate`, health, generation, signal counts и telemetry — как прежде; fault counter `faults` соответствует **количеству событий**, не количеству групп.
- Любой crash/SQLite error **до COMMIT** — rollback наблюдений, fault агрегатов, health и checkpoint. Crash после COMMIT — replay старого префикса не удваивает committed fault rows.
- Остальные `_fault` вызовы вне `ingest_batch` (если таковые имеются в будущей базе) не меняют семантику. При A=OFF текущий путь полностью сохраняется.

**R2 уточнение:** группировать ровно тот же prefix, не собирать все input outcomes заранее и не перемещать UPSERT после `COMMIT`; иначе конфликт в середине batch изменит durable fault count.

### A4. One opt-in activation switch

`NETWORK_METADATA_IO_HOTPATH_V1_ENABLED=false` — строго environment `true`/`false`, unset=false. Парсить по действующему NI-01 config path **только когда NI-01 включён**; неверное значение при NI-01 enabled → controlled startup failure, ни в коем случае не silent-enable. App runtime/Portal независимо живёт без NI-01.

Для `false` canonical `configuration_digest` **бит-в-бит прежний**, включая отсутствие нового ключа, и storage behaviour в legacy path сохраняется. Для `true` flag включается в канонический digest, configuration/run lineage различимо. Runtime mutation без controlled restart не поддерживается. Никакого управления через Admin UI.

## 4. PERF-IO-NI01-B — normative retention selection

### B1. Algorithm for `sensitive` and `core` only

`NETWORK_METADATA_RETENTION_INDEXED_V1_ENABLED=false`, strict true/false, independent A; `false` = legacy query/selection. `true` = **две SQL ветки**, каждая с `LIMIT 5000`, со строгим existing eligibility filter для данной категории:

```sql
-- branch 1; for sensitive append AND sensitive_endpoint_presence_state!='expired'
SELECT observation_id, event_at, ingested_at
  FROM network_metadata_observations
 WHERE event_at < :cutoff [AND sensitive_endpoint_presence_state!='expired']
 ORDER BY event_at, observation_id LIMIT 5000;

-- branch 2; same filter when sensitive
SELECT observation_id, event_at, ingested_at
  FROM network_metadata_observations
 WHERE ingested_at < :cutoff [AND sensitive_endpoint_presence_state!='expired']
 ORDER BY ingested_at, observation_id LIMIT 5000;
```

- `cutoff = now-14d` для sensitive, `now-30d` для core; `<`, не `<=`; **OR** eligibility сохранена. Не заменять на `AND` или client-side fuzzy threshold.
- Два результата: не более 10 000 retrieved rows, дедупликация **по полному** observation_id, сортировка по `(min(event_at, ingested_at), observation_id)` с canonical timestamp comparison; выбрать первые `<=5000`, далее существующая `_delete(kind, ids)` в **текущей transaction**.
- Изменение внутреннего deletion order с `observation_id` на oldest eligible **разрешено**. Уровень данных/read DTO/security semantics неизменен; подбор не должен зависеть от порядка SQL без `ORDER BY`.
- Никаких SQL `UNION DISTINCT`, unrestricted sort, extra query per candidate, новых индексов, temporary durable tables и cross-run cursors.
- **Доказательство completeness:** любой eligible row, не вошедший в топ-5000 по его минимальному timestamp в обеих ветках, имеет не менее 5000 предшественников в ветке, соответствующей его min timestamp. У каждого предшественника `min(event_at,ingested_at)` не позже его; tie-break по observation_id сохраняет порядок. Следовательно, он не может войти в глобальный earliest-5000. Тест должен проверить это для всех eligibility/filter и tie permutations, а не полагаться только на интуицию.
- `health/faults/generations/bindings/runs`, `expire_touched_identity`, retention categories и их priority order **без изменений**; глобальный `RETENTION_MAX_BATCHES_PER_PASS=20`, 5000 delete IDs per transaction, source cursor/checkpoint не меняются.

### B2. Failure/performance boundaries

- Обязательные plans на representative file-backed lab: `idx_nm_observations_event (event_at<?)` / `idx_nm_observations_ingested (ingested_at<?)` с индексным range SEARCH; никакого full table / observation_id PK SCAN для двух веток. SQLite план может зависеть от данных/статистики — не закладывать обещание, что любой план на любой БД будет идентичен.
- **Известный риск:** уже `expired` sensitive rows могут лежать в раннем префиксе индексов. Предикат state не включён в time indexes; даже `LIMIT 5000` не ограничивает число прочитанных index entries/row checks. **Это обязательный adversarial performance gate.** Нельзя обозначать ветки «bounded read I/O» только из-за LIMIT; bound относится к возвращённым rows и process memory, не к physical page traversal.
- Не вводить при неудаче новый индекс и не переписывать category state machine без нового Architecture Review. B остаётся OFF.
- При SQLite error, invalid stored timestamp/schema inconsistency, interrupted transaction, capacity pressure — fail-closed; не записывать retention-success, не сдвигать NI-01 checkpoint, не маскировать ошибку как «нет eligible rows».
- Retention по исходному контракту *bounded best-effort per pass*, а не гарантия, что вся просроченная DB будет очищена немедленно при уже существующем backlog. Приёмка требует сохранения TTL thresholds и способности eventual catch-up при реальной нагрузке, без неограниченного scan/latency.

### B3. Second independent activation switch

`NETWORK_METADATA_RETENTION_INDEXED_V1_ENABLED=false`: проверка только строгого `true`/`false`; false absent from canonical configuration digest для legacy identity, true included. NI-01 disabled не требует парсинга новых полей. Допускаются четыре combinations A/B OFF/ON; **не** объединять два флага: A и B должны иметь самостоятельные baseline и rollback. Только controlled restart, не Admin mutation.

## 5. Immutable system invariants

| Owner/domain | Frozen requirement |
|---|---|
| Source identity | `(source_generation_id,record_start_byte_offset)`, immutable record + semantic SHA; no IP-only identity |
| Replay | `duplicate_noop`, conflicts, expired digest fail-closed; **first conflict stops prefix** |
| Transaction | `BEGIN IMMEDIATE`, persisted observations+child rows, source records, fault count, health, generation and source checkpoint **one COMMIT** |
| SQLite | V1 schema/signature/indexes, FK, WAL, `synchronous=FULL`, limits/headroom/maintenance unchanged |
| Source | Original EVE, Suricata normalization/scope admission, generation lifecycle, continuity anchor, file truncation handling |
| Retention | 14d sensitive, 30d core, 45d health/faults, 90d generation/binding/run; same eligibility and delete cascade |
| Device consumers | NI-02B and NI-04 read DTO/provenance identity and availability unaffected; no gap hidden as healthy |
| Portal | Auth/CAPPORT/Omada and guest-facing latency/availability protected; optional NI failure may not veto core authentication |
| Security | No raw DNS, SNI, MAC, IP, payload, secrets or request lines added to telemetry; no new personal data |
| Runtime | Exactly one NI-01 writer and existing independent service; no new sidecar/daemon/queue |

## 6. Exact allowed production-code file scope per package

**A — approved:**

```text
app/network_metadata/service.py
app/network_metadata/repository.py
app/network_metadata/config.py
app/network_metadata/models.py
```

**B — approved:**

```text
app/network_metadata/retention.py
app/network_metadata/config.py
app/network_metadata/models.py
```

**Test/documentation scope allowed** (add focused files as needed; Tech Lead shall enumerate in TASK):

```text
tests/network_metadata/test_service.py
tests/network_metadata/test_repository.py
tests/network_metadata/test_checkpoint_crash.py
tests/network_metadata/test_retention.py
tests/network_metadata/test_config.py
tests/network_metadata/test_capacity.py
tests/network_metadata/test_health.py
docs/configuration.md
.env.example  # optional explicit default-OFF documentation, not auto-loaded
```

**Not allowed:** `app/network_metadata/schema.py`, `normalizer.py`, `scope.py`, `read_service.py`, `projection_source.py`, any `app/network_metadata_projection/*`, `app/network_attribution/*`, `app/device_fingerprint*`, `app/network_service_recognition/*`, `app/web/*`, `run.py`, `app/settings.py`, Omada/Visitor Registry/CAPPORT/Admin, DB schema migration or manual production DB data modification. Additional file necessary → **scope return to Tech Lead/Architect**, not coder workaround. Changes to `tests` may be made only insofar as they test this contract.

## 7. Acceptance matrix — mandatory for implementation TASK

### A1: range probe

- **A1-01** N=1,2,256 unique/all-new: exactly one preflight + one in-transaction range SQL, no per-record identity SELECT; equal canonical observations/child facts/health/checkpoint/telemetry to legacy.
- **A1-02** duplicate first/middle/last; overlap row in empty slot, duplicate+new batch: fallback exact old per-record behavior and first-conflict prefix.
- **A1-03** `source_record_identity_conflict`, `normalizer_determinism_conflict`, `replay_identity_evidence_expired` first/middle/last: identical reason, blocked offset and replay behavior.
- **A1-04** preflight empty then simulated insertion/change before Phase A: in-transaction re-probe wins; no trust in prior probe; single-writer simulated test only.
- **A1-05** generation rotation/old generation, EVE truncation, continuity-anchor failure, partial record/oversized record, disk failure, invalid schema: no digest bypass, fail closed, no checkpoint gap.
- **A1-06** crash before transaction COMMIT / after commit; duplicate replay; exactly once committed state, bounded batch size.

### A2: schema allowlist cache

- **A2-01** all DNS/TLS/QUIC family inserts and optional children identical to legacy; unknown table/column rejected.
- **A2-02** trace `PRAGMA table_info` absent from A=ON hot `_insert`, present at verified initialize. A=OFF legacy path unchanged.
- **A2-03** close/recover/DB reopen and invalid schema before reopen never adopt stale cache; failed cache init leaves no writable unvalidated state.

### A3: grouped faults

- **A3-01** F=0,1,10,256, G=0/1/many; count F→G SQL statements and exact database aggregate equivalence.
- **A3-02** mixed categories, different epochs, pre-existing aggregate, equal timestamps and first/last offsets; every field matches old behavior.
- **A3-03** valid+fault+duplicate+first conflict in one batch, crash before/after UPSERT, before/after checkpoint and COMMIT. No outcome after first conflict, no partial durable commit.
- **A3-04** SQL failure/overflow/invalid fault category; rollback and retry correct; telemetry count is *events*, not buckets.

### B: retention

- **B-01** EXPLAIN both branches, with representative indexed range SEARCH and no original observation-id PK scan for chosen fixture; `<=5000` per stream, `<=10000` fetched, `<=5000` deletion IDs.
- **B-02** fixture 0/1/5000/5001/20000 eligible; compare **eligibility and eventual completeness** vs legacy (deletion order intentionally differs). No early expiration.
- **B-03** `event_at` old / `ingested_at` new, reverse, ties/mixed eligibility, already-expired sensitive, future timestamps, 14/30 day boundaries, all canonical timestamp rules.
- **B-04** adversarial fixture with **large early already-expired prefix**: bounded latency/I/O or return B activation HOLD; not permitted to declare success solely on query plans/10k returned rows.
- **B-05** 20×5000 global batches, slow reader WAL, capacity pressure, unavailable source/storage, SQLite error; no retained-source cursor drift, no deadlock, no unsafe maintenance.
- **B-06** FK cascade, source digest_state expiry, exact schema signature, NI-02B/NI-04 downstream compatibility.

### Integration + release

- **E2E-01** Compare A OFF/B OFF vs A ON/B OFF vs A OFF/B ON vs A ON/B ON on identical **separate file-backed** fixtures and clocks. Equal canonical persistent facts/health/fault counts/checkpoints; B selection order is the only permitted data-operation-order difference.
- **E2E-02** deterministic crash/restart, staging acceptance, current mandatory Central Lab full regression, Linux compatibility, schema and security checks. Official testing policy remains authoritative.
- **E2E-03** no storage upgrade, no IO_PRAGMA relax, no expensive trial against live production DB.

**Release stop:** open mandatory P0/P1 test failure or performance regression in representative workload → HOLD, not force-promote.

## 8. Performance acceptance and staged activation

**Before any development:** Tech Lead validates exact research HEAD/TREE vs actual approved implementation baseline and confirms loaded NI-01 artifact. If commits differ, provide diff impact; reuse this contract only if implementation surfaces remain semantically same; else Architect return. **Do not** equate current checkout to running binary by assumption.

**Lab comparison:** pair legacy vs candidates on equivalent file-backed input/data distributions; repeat multiple identical workload runs and report SQL counts, `read/write ops`, bytes, latency and checkpoint throughput. Run normal all-new batch, high-fault batch, replay/conflict batch and retention with large expired prefix. Do not infer disk IOPS reduction from CPU/SQL counts alone.

**Controlled production sequence** (requires separate Owner approval for each action):

1. Publish Git-accepted A, both feature flags OFF → deploy dormant code → verify exact loaded SHA/TREE and legacy behavior. Deployment itself does not authorize activation.
2. Collect bounded baseline of source EVE generation/byte checkpoint and 60s intervals for guest cgroup/vda and, **synchronized if measured**, host `/dev/sda` + corresponding QEMU cgroup. Host and guest device measurements from different windows must not be mixed in arithmetic.
3. Owner activates **A only**, controlled restart. Check auth/CAPPORT health, ingestion/replay/checkpoint, EVE backlog, WAL/IO and resulting normalized cost. If improvement not physically measurable in representative workload or anything degrades, A stays HOLD/revert OFF and investigate; do not advertise resolved disk incident.
4. After independent Lab gates, publish B dormant; Owner activates **B only** after approved baseline/rollback. Confirm retention runs do not dominate ingestion and expired-heavy window is safe. B failure → B OFF; A acceptance stays independent.
5. Combined A+B acceptance only after separate tests. No NI-02B, NI-04, fingerprint, sensor or Portal production settings changed by this initiative.

**Measurements:** same-time comparable device/cgroup accounting; writes/sec, reads/sec, bytes/input record, bytes/committed observation, fault SQL/upsert count, batch/throughput, pending source backlog bytes, watermark progress, write/read await, disk busy, WAL growth/blocked readers. Distinguish source event-time age from input byte backlog. Each R1 snapshot is a baseline example, **not** a perpetual threshold and **not** a proof of current state.

**Stopping criteria:** incorrect identity/replay, change to durable aggregate/checkpoint, new `blocked_conflict`, schema drift, retention not catching up, reader failures, source backlog/latency regression, positive service facts lost, Guest Auth/CAPPORT degradation, physical disk deterioration. Rollback = turn *appropriate* flag OFF and controlled restart on accepted compatible Git release; no SQLite hand surgery, no fake checkpoint advancement.

**No mandatory hard % IOPS improvement is invented.** Tech Lead should report observed direction/magnitude, run-to-run variance and workload equivalence; if ambiguous, activation HOLD and return with evidence.

## 9. Findings from R1 review — accepted / changed / rejected

| R1 point | R2 disposition |
|---|---|
| Two independent packages A/B | **ACCEPTED**; must have separate default-OFF flags and separate rollout |
| Generation-scoped range probe | **ACCEPTED WITH SAFETY CLARIFICATION:** independent transactional probe; overlap falls back; no caching across windows |
| One-time column allowlist | **ACCEPTED WITH LIFECYCLE CLARIFICATION:** verified init; invalidate on close/recover; external DDL forbidden |
| Fault aggregation | **ACCEPTED WITH ORDERING CLARIFICATION:** only Phase-B reached prefix; UPSERT before existing checkpoint hook; same transaction |
| Two index-ordered retention branches | **ACCEPTED WITH PERFORMANCE GATE:** 10k return is *not* 10k scan bound, expired prefix adversarial test mandatory |
| Retention deletion order | **ACCEPTED:** oldest eligible internally; strict eligibility/retention bounds retained |
| All SQL reductions are physical savings | **REJECTED** as an inference; requires file-backed and physical device evidence |
| Change SQLite cache size, synchronous, indexes | **REJECTED FOR THIS TASK**; new architecture review required |
| Change NI-02B/NI-04/fingerprint/Portal | **REJECTED FOR THIS TASK**; separately owned programs |
| Treat checkout HEAD as loaded artifact | **REJECTED:** Tech Lead verifies process loaded artifact independently |

## 10. TechLead23 handoff — exact final directive

```text
TASK_FAMILY = CAPTIVPORTAL-PERF-IO-NI01
ARCHITECTURE_DOCUMENT = CAPTIVPORTAL-PERF-IO-NI01-ARCHITECTURE-CONTRACT-R2-FINAL-TECHLEAD-2026-10-14.md
SUPERSEDES = CAPTIVPORTAL-PERF-IO-ARCHITECTURE-CONTRACT-R1-2026-10-14(1).md
ARCHITECT_VERDICT = MODIFY_THEN_APPROVE
ARCHITECTURE_STATE = ACCEPTED_FOR_TECH_LEAD_IMPLEMENTATION_TASK
RESEARCH_HEAD = 3b5f70cec467939995fecc7667169239000b7308
RESEARCH_TREE = 5d52a536adffe55475ec9dd9d4b3e2d7ea8eeb2b
TECH_LEAD_BASELINE_REPIN = REQUIRED
PACKAGE_A = PERF-IO-NI01-A (RANGE_PROBE + COLUMN_CACHE + GROUPED_FAULTS)
PACKAGE_B = PERF-IO-NI01-B (TWO_INDEX_RETENTION_SELECTION)
PACKAGE_A_FLAG = NETWORK_METADATA_IO_HOTPATH_V1_ENABLED=false
PACKAGE_B_FLAG = NETWORK_METADATA_RETENTION_INDEXED_V1_ENABLED=false
SCHEMA_CHANGE = NO
MIGRATION = NO
SQLITE_DURABILITY_CHANGE = NO
SOURCE_OR_CHECKPOINT_SEMANTICS_CHANGE = NO
NI02B_NI04_FINGERPRINT_AUTH_CAPPORT_CHANGE = NO
CODER_GO = NO (until Tech Lead issued exact TASK)
PRODUCTION_CHANGE = NO
OWNER_ACTIVATION_GO = SEPARATE_REQUIRED
NEXT = TECH_LEAD PIN -> TWO SCOPED TASKS -> CODER LAB QA -> OWNER RELEASE/ACTIVATION
```

**Tech Lead acceptance request:** issue **two separately reviewable implementation TASKs** with the exact per-package file allowlist, explicit tests above and independent release gates. If candidate cannot satisfy R2 without modifying forbidden modules/schema, **return to Architect**, do not silently widen scope.

---

### Source pointers (code baseline, not links to mutable `main`)

- `app/network_metadata/service.py`: `poll_once`, preflight normalizer+identity loop.
- `app/network_metadata/repository.py`: `initialize`, `_insert`, `_fault`, `identity_outcome`, `ingest_batch`, `_observation`, `ensure_headroom`.
- `app/network_metadata/retention.py`: `expire_touched_identity`, `run`, `_select`, `_delete`.
- `app/network_metadata/schema.py`: `TABLE_DDL`, `INDEX_DDL`, `validate_schema`.
- `app/network_metadata/config.py` and `app/network_metadata/models.py`: strict env parsing, `configuration_digest`, immutable config.
- R1 §1 read-only measurements, §3 A candidates, §4 B proposal, §7 QA and §12 independent FP/NI-02B research backlog. R1 measurement numbers are retained as dated evidence; they are not recertified production facts.
