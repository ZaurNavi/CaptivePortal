# CAPTIVPORTAL — TASK-DTI-NI-IO-IMPLEMENT-01-WAVE1
## Первая волна оптимизации дисковых записей NI-01 / NI-02B / NI Telemetry
### ОДНОЗНАЧНОЕ IMPLEMENTATION TASK ДЛЯ CODER — CODE ONLY

**Инициатор:** Owner, поручение от 2026-10-12. **Автор ТЗ:** TechLead23.  
**Тип:** реализация исходного кода. **Не:** лабораторные измерения, performance proof, QA или deployment.  
**Repository:** `ZaurNavi/CaptivePortal`  
**Pinned parent:** `88541da8d6952cb91fc945b7f77efcf7e5c46420`  
**Pinned tree:** `d879f5113319c334faf2bf9ae7b8bea7cfdc977e`  
**Architecture:** `ARCH-DTI-NI-IO-OPT-01-WRITE-PATH-CONTRACT-v1` (2026-10-12)  
**Former profiling task:** `TASK-DTI-NI-IO-PROFILE-01` — `HOLD_MEASUREMENT_QUALIFICATION`; он НЕ является зависимостью для написания кода по настоящему Owner-решению.  

### Решение Owner о последовательности

Owner явно назначил иной порядок, чем прежний `profiling-first`: **исходный код → независимая проверка и тесты Tech Lead / Research & QA → решение о Git/PR/merge → отдельный Owner-authorized deployment → реальные production-метрики**. Это исключение касается только **очередности работ** и **разрешения написать код**; оно **не отменяет** архитектурных ограничений на надёжность, семантику и границы изменения. Архитектурный контракт не переиздан и сам по себе не авторизовал production. Coder не объявляет performance PASS и не подменяет измерения предположениями.

```text
TASK=TASK-DTI-NI-IO-IMPLEMENT-01-WAVE1
CODER_AUTHORIZATION=SOURCE_IMPLEMENTATION_ONLY
ARCHITECTURE=ARCH-DTI-NI-IO-OPT-01-WRITE-PATH-CONTRACT-v1
IMPLEMENT=A1+B1+B2+L1
FINGERPRINT=HOLD
NI-05/NI-06=HOLD
TEST_DESIGN/TEST_EXECUTION/QA/PROFILING=NOT_ASSIGNED_TO_CODER
COMMIT/PUSH/PR/MERGE=HOLD_FOR_TECHLEAD_AND_OWNER
PRODUCTION_ACCESS/DEPLOY/RESTART/FLAGS/DB_WRITE=FORBIDDEN
DEFAULT_ALL_OPT_FLAGS=OFF
```

## 1. Рабочее пространство — обязательно

1. Работать в **новом чистом изолированном рабочем дереве** на WSL/laptop SSD, не на production HDD. Путь нового дерева: `/home/zaur_navi/captivportal-lab/worktrees/dti-ni-io-implement-01-wave1`. Создавать его только если пути ещё нет; при существующем пути без однозначного происхождения остановиться, ничего не удалять.
2. Взять **точно** указанный pinned parent commit/tree. Не переиспользовать dirty worktree `/home/zaur_navi/captivportal-lab/repo` (там другая работа) либо другие R7-копии. Не выполнять `reset --hard`, `clean`, checkout поверх чужой работы, `safe.directory` для root или изменения global Git config.
3. Создать **незакоммиченные** рабочие изменения только в целевых модулях. Не изменять production host/VM и работающие SQLite-файлы. Не брать реальные MAC/IP/SNI из production.
4. Если точный parent недоступен или дерево не совпадает, **HOLD / BASELINE_MISMATCH**, без попытки подобрать другой commit.

## 2. Жёсткие системные ограничения

**Запрещено менять:** `journal_mode=WAL`, `synchronous=FULL`, `wal_autocheckpoint=1000`; NI-01 единый atomic `BEGIN IMMEDIATE`/`COMMIT` для source identity, нормализованных фактов, health/fault и checkpoint; любые схемы, версии, индексы, триггеры, сроки retention/privacy, иммутабельные edge-digest/identity, source-generation/replay semantics; NI-02A temporal authority; Registry identity; NI-03/NI-04 product DTO/версии/лимиты; CAPPORT/Auth, Omada, SPAN/Suricata; Fingerprint spool/writers. Не добавлять cache/source store, background writer, миграцию, внешнюю зависимость или поток для оптимизации.

Каждая оптимизация **строго opt-in**; при всех флагах `false` observable behavior исходного кода, включая семантику транзакций, журнальных сообщений, DB signature и значения контрактных DTO, должен остаться legacy. Не допускать ложного `usable` при потере источника. Весь NI-01 поток идёт по старой схеме `generation→source_record→normalized row→checkpoint`.

## 3. Конфигурация и включение — точные ключи

Добавить поддержку этих **шести** environment keys (не Admin Settings):

```dotenv
NETWORK_METADATA_INGEST_COALESCE_ENABLED=false
NETWORK_METADATA_INGEST_COALESCE_MAX_MS=0
NETWORK_METADATA_PROJECTION_IDLE_WRITE_REDUCTION_ENABLED=false
NETWORK_METADATA_PROJECTION_CHECKPOINT_OPT_ENABLED=false
NETWORK_METADATA_TELEMETRY_AGGREGATION_ENABLED=false
NETWORK_METADATA_PROJECTION_TELEMETRY_AGGREGATION_ENABLED=false
```

- Boolean значения **только** `true` / `false` в нижнем регистре. Иные значения для активного соответствующего сервиса → config failure, без «тихого» fallback.
- Для A1: если `ENABLED=false`, `MAX_MS=0`; если `ENABLED=true`, `MAX_MS ∈ {100,250,500}`; все остальные комбинации отклонить.
- Оптимизационные ключи относятся к **соответствующему process environment**. B1 reader guard в `captive-portal.service` должен получать **тот же** `NETWORK_METADATA_PROJECTION_IDLE_WRITE_REDUCTION_ENABLED=true`, что и `network-metadata-projection.service`; ни один Coder-деплой/изменение systemd не разрешено. Реальное одновременное включение — отдельный Owner deployment/activation gate.
- Сервису, у которого базовый feature `ENABLED=false`, сохранить существующий disabled-fast-path без нового I/O и обязательного разбора посторонних ключей.
- `config digest`: при выключенных оптимизациях сохранить **байт-в-байт legacy canonical configuration digest** для NI-01 и NI-02B, даже если добавлены поля dataclass; при включении соответствующей оптимизации digest должен различать режим/значение. Старые DB/run records, source generations и provenance не переписывать.
- Защититься от ошибочного частичного включения B1: reader stale guard не должен полагаться только на состояние writer in-memory; его режим должен контролироваться своим process env и задокументирован как требующий синхронного включения в обоих процессах. Никаких новых полей в NI-03/NI-04 DTO.

## 4. A1 — NI-01 bounded pre-COMMIT coalescing

**Целевые существующие файлы:** `app/network_metadata/config.py`, `models.py`, `service.py`, при необходимости строго локальный helper внутри `app/network_metadata/`. Не менять `source.py`/`repository.py`, если работа может быть реализована без нарушения текущих API; при реальной необходимости поправки только в `app/network_metadata/` и без изменений схемы/транзакционной атомарности.

**Было:** `NetworkMetadataService.poll_once()` сразу после `BinarySourceReader.read_batch()` нормализует и пишет считанные полные source records одним atomic `ingest_batch`; `run_forever` непрерывно обрабатывает backlog, а при пустом poll ждёт `poll_interval_seconds=1`.

**Сделать:**

1. Только при `COALESCE_ENABLED=true` собрать **уже завершённые, последовательные записи одного source generation** в существующем bounded-batch пути перед открытием SQLite write transaction; не открывать `BEGIN IMMEDIATE`, пока идёт ожидание.
2. Верхние пределы одного commit неизменны: **256 записей и 1,048,576 retained source bytes**, а `record_too_large` следует прежним отдельным semantic правилам. Не разрывать source record, не переставлять его, не смешивать generations, не изменять правила `identity_outcome`/conflict/fault.
3. Deadline считается **монотонно от первой полной ещё некоммиченной записи**. Одно из условий немедленного закрытия батча: 256 записей, лимит bytes, истёк выбранный `MAX_MS`, необходимость закрыть/сменить generation, graceful stop, **>=4 MiB uncommitted source-file backlog**. Реагировать на первое наступившее условие. При backlog >=4 MiB дополнительное ожидание **0 ms**; непрерывную выгрузку backlog не замедлять.
4. Не удерживать более legacy 1 MiB source payload bytes в памяти, дополнительная RSS цель <=16 MiB; использовать `Event.wait()`/timed-block вместо busy-spin. **Не добавлять** второй durable spool, второй checkpoint, отдельные transactional commits для data и checkpoint, передачу в другой процесс или адаптивное ожидание по HDD/CPU.
5. При graceful stop с nonempty buffer: прекратить ожидание, попытаться обычный atomic commit полного валидного prefix и только затем завершить. При crash до COMMIT: durable checkpoint не сдвинут и старые bytes должны пройти обычный replay. При конфликте в buffered prefix: оставить exact inherited fail-closed behavior; не переставлять или скрывать конфликт.
6. При rotation/truncation/close source generation: **до** старого transition обработать eligible полный buffered prefix старого descriptor; потом выполнять существующий `_replace()`/`_lifecycle()`; никогда не прикреплять запись старого fd к новой generation. Если source bytes безвозвратно исчезли, не фабриковать commit/success — оставить прежний gap/health semantics.
7. При `0 ms`/флаге OFF **вообще не менять** старый цикл ingest: никакого дополнительного event wait, буфера, лишнего SQLite read, задержки или иного разбиения пакетов.
8. Сохранить нынешние per-batch provenance/health reference validation. Новые ingestion run IDs, timestamps или количества батчей не должны трактоваться как основание изменить семантику source identity/normalized observation. Точный QA-компаратор будет утверждён Tech Lead/RQA, не Coder.

**Не выбирать production MAX_MS.** Значения 100/250/500 реализуются как закрытые разрешённые варианты; дефолт OFF/0.

## 5. B1 — NI-02B empty poll: 10s durable heartbeat, 30s fail-closed

**Целевые файлы:** `app/network_metadata_projection/config.py`, `models.py`, `service.py`, `repository.py`, `read_service.py`, `recognition_read_service.py`, при необходимости новый узкий helper `effective_runtime_state.py` в этом же пакете.

1. Источник NI-01 продолжать проверять каждые **1 секунду**. Меняется **не опрос**, а запись в SQLite при успешном пустом опросе без обязательных изменений состояния.
2. Если source verification PASS, новых source observations нет, effective state без изменений, иных обязательных записей нет и с последнего **durable successful source-poll heartbeat** прошло `<10 секунд`, **не вызывать write transaction**, не выполнять `UPDATE projection_runtime_state` и post-commit maintenance. Хранить промежуточный успех в памяти процесса (не новый store).
3. При достижении `>=10 секунд` записать один атомарный update `last_source_poll_at`; реальный `commit_dispositions()` уже обновляет это поле и засчитывается в heartbeat, не создавать вторую heartbeat transaction. Если в том же tick нужна другая обязательная transaction, допускается включение timestamp лишь когда в **этом tick** source verification действительно успешна.
4. В следующих состояниях не откладывать необходимую запись: `initializing`, transition `usable↔degraded` / `registry_degraded` / `attribution_unavailable`, source failure/recovery, capacity state, blocked conflict, stopping/graceful stop. Не превращать изменение состояния в «пустой heartbeat». Не переводить `source_unavailable` в `usable` по старым данным до успешной верификации текущего процесса.
5. На старте процесса, если B1 активен, effective state должен стать `initializing` до первого успешного source poll текущего запуска; старая persisted `usable` сама по себе не делает процесс ready. Никаких DB schema/enum изменений. При аварийном завершении heartbeat закономерно устаревает.
6. **30-секундный cross-process guard:** из одного авторитетного read-only helper использовать `last_source_poll_at` из **того же SQLite snapshot**, где прочитан `runtime_state`. Для `usable`, `registry_degraded`, `attribution_unavailable` (все source-usable в `_COVERAGE`) при `evaluated_at_utc - last_source_poll_at >30s` либо invalid/missing timestamp выдавать effective `runtime_state='source_unavailable'`, reason `source_poll_stale` в уже существующем `safe_reason` там, где такой field предусмотрен. На ровно 30s ещё не stale. Не допускать обхода при clock skew и future timestamps: недостоверный timestamp → fail closed. Для уже source-unavailable/blocked/degraded состояний исходную худшую оценку не улучшать.
7. Guard встроить **последовательно в оба read path**: `DeviceNetworkMetadataReadService.read_protocol_evidence_snapshot()` (NI-03) и `DeviceNetworkMetadataRecognitionReadService.read_service_recognition_snapshot()` (NI-04), а также `DeviceNetworkMetadataReadService.get_status()`. Для NI-03 оставить exact `{'runtime_state','binding_state','bound_device_id','facts'}`; для NI-04 оставить exact `RecognitionProjectionSnapshotV1` (version/fields). Нельзя добавить `safe_reason` в эти два frozen response DTO; операционный reason допускается в `get_status()`.
8. Read guard должен использовать свой feature flag, **по умолчанию false**, и legacy read behavior без флага сохранять точно. Вызов от Portal должен работать через уже существующие constructors/composition без изменений CAPPORT/Auth кода; читателю доступны его process-environment и переносящийся parent init. Не создавать новый runtime reader DB writer.
9. Реальные статусы `registry_degraded` и `attribution_unavailable` не «исправлять» до `usable` автоматически. Fail-closed может только понизить их effective source dimension; исходную identity-binding state не выдумывать.

## 6. B2 — NI-02B conditional PASSIVE checkpoint

**Целевой файл:** `app/network_metadata_projection/repository.py`, вызов retention из `service.py` при необходимости.

1. В режиме B2 убрать **безусловный explicit `PRAGMA wal_checkpoint(PASSIVE)`** после каждого обычного `COMMIT`. Оставить SQLite `wal_autocheckpoint=1000`, `WAL`, `FULL`, existing transaction headroom **16 MiB**, `combined DB+WAL+SHM` cap.
2. Explicit PASSIVE только по причине: **A:** WAL `>=16 MiB`; **B:** retention уже выполнен и WAL nonempty; **C:** комбинированный размер + 16 MiB headroom приближается к/пересекает configurated cap; **D:** восстановление из `capacity_*` состояния.
3. Мягкие A/B проверки ограничить частотой **не более одной попытки PASSIVE за 60 секунд** (monotonic; timer только в памяти). Для C/D разрешён немедленный обход rate limit, если иначе нет безопасного headroom; **не ослаблять hard cap**.
4. `TRUNCATE` разрешён **только в прежней ветке capacity pressure** и в пределах старых busy/reader-pin handling; никаких периодических TRUNCATE, TRUNCATE «на старте» или ручных production checkpoint.
5. При pinned reader + достаточном headroom — не переименовывать успешно committed disposition в rollback; допускается отложить soft checkpoint. При реальной нехватке пространства оставить `capacity_waiting_reader` / `capacity_halted` fail-closed. Ошибка после COMMIT не должна прикидываться откатом уже записанного.
6. Все операции legacy при `CHECKPOINT_OPT_ENABLED=false` оставить по исходному пути, включая вызываемый `maintain_capacity(post_commit=True)`.

## 7. L1 — агрегировать routine success telemetry, НЕ ошибки

**Целевые файлы:** `app/network_metadata/telemetry.py`, `app/network_metadata_projection/telemetry.py` и узкие вызовы из двух существующих `service.py`/`repository.py` при необходимости.

1. При собственном флаге false оставить `emit()` legacy byte/semantic behavior. При true поддержать **один in-memory агрегатор на процесс/сервис**, без отдельного потока, SQLite, файла или дополнительной очереди.
2. За каждое окно **60 monotonic секунд** формировать **не более одного нормального success-summary event на сервис** (NI-01 отдельно, NI-02B отдельно). Накапливать `batch_count`, `record_count`, `duplicate_count`, `fault_aggregate_update_count`, `idle_poll_count`, `commit_count`, `checkpoint_attempt_count`, `checkpoint_busy_count`, `suppressed_event_count` — только если соответствующий показатель реально наблюдается; неизвестные числа не выдумывать. Числовые counters строго bounded/nonnegative, безопасные к сбросу после публикации. Не расширять сырой log schema произвольными upstream строками.
3. Убирать из per-success journal только события `batch_committed`, повторяющиеся успешные duplicate-уведомления/агрегированные update, успешные idle polls/checkpoint maintenance. `service_started/stopped`, source generation open/close, durable health/runtime **transitions**, `storage_unavailable`, capacity stop, identity/conflict faults, `projection_conflict`, source/registry/attribution unavailable/recovery — **публиковать немедленно**. Первое появление fault/transition нельзя скрывать до минутной сводки.
4. Для fault aggregates: durable source fault outcome остаётся в SQLite и все первые/переходные fault signals immediate; допускается собирать **только повторные одинаковые routine update notifications**, не semantic alarm.
5. Сводка должна выводиться через нынешний безопасный logger, с фиксированным closed allowlist полей; без IP/MAC/device_id/DNS/SNI/raw endpoint/сырого Registry; без динамического исходного payload. Закрытые event grammar и validation сохранить либо расширить **только** собственным строго определённым `success_summary` и закрытыми integer-field именами. Не менять NI-03/NI-04 логи/DTO.
6. Отсутствие записи minute summary при аварийной смерти процесса разрешено: сводка не является audit authority; durable source record/checkpoint/edges сохраняются. При штатном закрытии не создавать второй внеочередной нормальный summary, который нарушает max frequency; предпочесть deterministic flush в существующем loop в разрешённом окне.

## 8. Фиксированная последовательность реализации внутри ОДНОГО TASK

1. **B1** — убрать лишний idle write и защитить всех читателей stale. Не менять NI-01/Fingerprint.
2. **B2** — conditional checkpoint NI-02B. Проверять feature combination: B1 only, B2 only, B1+B2; OFF/OFF legacy.
3. **A1** — bounded coalescing NI-01 со strict stop/rotation/backlog semantics. OFF/0 legacy.
4. **L1** — NI-01/NI-02B success event aggregation. OFF legacy.
5. Все четыре режима должны допускать **независимое включение**; реализовать combination support без неявного включения другого режима. Место для future production decision оставить только на feature flags; НЕ добавлять принудительное включение в production config.

## 9. Список допустимых файлов и запретов

**В пределах TASK можно менять только:**

```text
app/network_metadata/config.py
app/network_metadata/models.py
app/network_metadata/service.py
app/network_metadata/repository.py   (только если A1 действительно требует)
app/network_metadata/telemetry.py
app/network_metadata/*.py            (только узкие helper без изменения внешних контрактов)
app/network_metadata_projection/config.py
app/network_metadata_projection/models.py
app/network_metadata_projection/service.py
app/network_metadata_projection/repository.py
app/network_metadata_projection/read_service.py
app/network_metadata_projection/recognition_read_service.py
app/network_metadata_projection/telemetry.py
app/network_metadata_projection/*.py (только узкие helper без изменения внешних контрактов)
```

`run.py`, `app/admin_web/*`, `app/network_protocol_intelligence/*`, `app/network_service_recognition/*`, `app/network_attribution/*`, `app/device_fingerprint*/*`, `app/device_fingerprint_sensor/*`, `app/network_metadata*/schema.py`, `tests/*`, CI, deploy/systemd/scripts/production ENV **не менять**. Если иное неизбежно для корректности — вернуть `HOLD_IMPLEMENTATION_BOUNDARY` с точной причиной; **не расширять самостоятельно**.

## 10. Завершение Coder и handoff — только исходный код

Coder должен предоставить:

- Новый WSL source worktree path, parent HEAD/tree; список реально изменённых файлов; **uncommitted diff** (он лежит в новом worktree), без коммита.
- Одну короткую сводку реализованных веток B1/B2/A1/L1, настройки/значения их default OFF, как включаются по флагам позднее.
- Строго зафиксированные технические blockers, если обнаружены, вместо догадок/самовольного упрощения. Если один кандидат упёрся в архитектурную несовместимость, не ломать его; изолировать и отметить, какие независимые кандидаты написаны.

Coder **НЕ ДОЛЖЕН**: собирать physical IOPS / latency, повторять Stage-0 profiling, создавать performance-harness, писать/запускать тесты или full test suites, предоставлять доказательства %, QA-вердикт, писать большой исследовательский отчёт, изменять Git history/commit/push/PR/merge, затрагивать production host/VM или запускать сервисы. Эти задачи последовательно выполнят **TechLead23 / Research & QA / SysAdmin / Owner** после code handoff.

После получения кода **TechLead23** организует независимые regression/crash/replay/cross-process stale/read-deadline tests, проверит архитектуру и выполнит сравнение I/O в реальных условиях; любые выявленные дефекты вернутся Coder как точечный defect-fix TASK. Затем **отдельное** разрешение Owner на Git/PR, merge, deployment и включение каждой оптимизации. Не обещать 20–30% экономии заранее.

## 11. Короткая формулировка для Coder

> **Реализуй B1, B2, A1, L1 в исходном коде на pinned parent. Держи все шесть флагов выключенными по умолчанию, сохраняй FULL/WAL и все durable checkpoint/replay/identity contracts, не меняй Fingerprint, CAPPORT/Auth, schema или production. Работа только в новом чистом worktree. Никаких тестов, измерений, профилирования, публикации в Git и отчётов-доказательств. Дай перечень изменённых файлов и готовый uncommitted diff на приёмку TechLead23.**

---

**OWNER ORDER (IMPLEMENTATION BEFORE MEASUREMENT) = RECORDED**  
**TECHLEAD23 IMPLEMENTATION TASK = ISSUED / SOURCE-ONLY**  
**ARCHITECTURE SEMANTIC CONSTRAINTS = PRESERVED**  
**CODER TEST/PROOF DUTY = NONE**  
**PRODUCTION CHANGE = NONE**  
**NI-05 / NI-06 = HOLD**
