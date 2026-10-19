# CAPTIVPORTAL — QIO-02 SQLite Small-I/O Architecture Admission Contract v1

**Дата:** 2026-10-16 (Asia/Baku)  
**От:** Chief Architect → Tech Lead, Performance & Optimization  
**Тема:** `captive-portal.service` — SQLite idle writes / `fsync` fan-out  
**Нормативный вход:** `CAPTIVPORTAL-QIO-02-TECHLEAD-TO-CHIEF-ARCHITECT-REQUEST-2026-10-16(1).md`; `CAPTIVPORTAL-PERF-IO-QUIET-LOAD-OPTIMIZATION-ROADMAP-v1.0-2026-10-15.md`, QIO-02.  
**Источник для проверки контрактных границ:** GitHub `ZaurNavi/CaptivePortal` read-only по `main@e2cbd96916d8a81f07f0d79a1a745f593ccb5114`, как в запросе Tech Lead. Это не свидетельство идентичности каждого загруженного процесса production: loaded-artifact, настройки, DB/schema и точные пользовательские SLA перепроверяет Tech Lead до Lab/Coder.  
**Тип:** Architecture admission / semantic contract. **Не Coder TASK; не production GO; не доказательство физического I/O выигрыша.**

## 0. Архитектурный вердикт

`DECISION=MODIFY` — направление архитектурно допускается, но **модель "unchanged payload ⇒ no COMMIT" отвергается**. Нужна модель *unchanged effective obligation*: запись можно пропустить только когда **не возникло ни нового authoritative факта, ни freshness/proof-of-scan, ни source progress, ни статуса, ни обязательного аудита**, и корректное чтение/восстановление одинаковы до/после оптимизации.  
`FIRST_CODER_ADMISSION=EVIDENCE_REQUIRED`. Конкретный физически выгодный writer **ещё не атрибутирован**. Текущее состояние: `ARCHITECTURE_SEMANTIC_BOUNDARIES=PASS`; `LAB_SCOPED_CANDIDATE=CONDITIONAL`; `CODER=HOLD`.

**Ровно две независимые границы:**

1. **Data authority / freshness:** что обязано быть durable, независимо от IOPS.
2. **Measured physical efficiency:** есть ли экономия завершённых физических HDD операций при сохранении первого пункта.

Снижение SQL-операций, логических чтений, объёма WAL, количества вызовов `commit()` или отдельных sampled `fdatasync` — само по себе **не** performance PASS.

### Контекст измерений (не переинтерпретировать)

- QUIET-01 2026-10-15: `captive-portal.service` **1 282 guest block writes / 120 s** = 10,68/s; выборочное `fdatasync` нескольких SQLite/WAL без достоверных per-DB counts.
- 2026-10-16 02:03:52–02:04:52: **667/60 s** = 11,12 guest writes/s, отдельное окно.
- После QIO-01B: иной guest 60 s **4,03 wios/s**; host HDD в другом окне **~100,77 writes/s, ~90,7% busy**; **не** matched baseline и **не** физический эффект, доказанный для QIO-01B.
- Гостевой cgroup (`252:0` и `253:0` могут отражать вложенные уровни) и host `/dev/sda` не суммировать и не приравнивать; QEMU/host и guest окна должны иметь общие границы.
- QIO-01A/B развернуты согласно запросу Tech Lead; QIO-01D и PR #215 остаются вне QIO-02.

## 1. Общий формальный допуск к подавлению записи

Для конкретного `operation` и конкретного snapshot/transaction boundary подавление записи **разрешается** только если одновременно доказано:

**N1.** Читается и сравнивается **весь** набор полей, на которые влияют UI/health/alerts/retention/replay/authorization, а не только численность устройств, traffic bytes или rowcount.  
**N2.** Нет нового uniquely identified source fact/event и нет непотреблённого `source_offset`, `generation`, `cycle_id`, `source checkpoint`, watermark, retry/result, lifecycle transition, idempotency key или подтверждённого успешного наблюдения.  
**N3.** Нет изменения `complete/partial/error/unknown`, source scope, источника доверия/identity, `last_*_at`, freshness deadline, source availability или negative/absence proof.  
**N4.** Существующий durable state достаточен, чтобы после crash/restart восстановить точно те же correctness claims и replay boundaries без пропуска фактов и без false freshness.  
**N5.** Read-check и право пропустить запись не создают race с другим writer: выбор должен быть сериализован теми же собственными owner/lock/transaction boundaries либо доказан CAS/atomic gate; никакой новый второй authority.  
**N6.** Нет потери security/audit/evidence retention, observability incident transitions, идентичности Site/SSID/MAC/device/visit, и никаких новых dirty writes для "экономии".  
**N7.** Отдельный matched Lab baseline выявил, что именно этот вызов создаёт существенную физическую нагрузку и изменение снижает host completed writes и/или latency без деградации SLA.

Если хотя бы одно N1–N7 не выполнено: **писать как сейчас / `EVIDENCE_REQUIRED`**. Нельзя заменять durable scan-пруф неустойчивым in-memory `last_success`. `SELECT`/`BEGIN IMMEDIATE`/`COMMIT` без эффективной модификации может уже не создавать физическую запись; это требует проверки, а не предположения.

**Слова имеют точное значение:**

- `authoritative`: уникальный source/domain факт, на котором основаны auth, lifecycle, counters или reconciliation; если он уже корректно закоммичен, повтор допустимо отсеивать **только в рамках доказанного idempotency контракта**.
- `freshness/proof-of-scan`: успешное полное, охваченное правильным source scope наблюдение с временем и качеством; изменение timestamp даже при том же payload — **новый факт свежести**.
- `derived/rebuildable`: материализация из сохранившегося durable source при определённой версии/генерации и bounded replay; если не доказан deterministic rebuild, считать non-rebuildable.
- `audit/security`: подтверждение действия/ошибки/смены охраны или авторизации, отдельное от routine telemetry. Нельзя стирать.
- `operational-only`: диагностическая периодика, которая **не** участвует в service readiness, health SLA, alert freshness, source continuity, consumer watermarks, security или replay; данную квалификацию обязан проверить Tech Lead.

## 2. Матрица DB / owner / фактов / допустимых оптимизаций

| DB / owner | Authoritative или freshness obligation | Derived/operational path | Что обязательно commit / оставить | Где условно возможен no-op | Запрещено |
|---|---|---|---|---|---|
| **`visitor_registry.sqlite3`** — `VisitorRegistryWorker`, `RegistryRepository`, source reader | `visitor_devices`, `device_snapshots`, `processed_snapshot_events`, `reader_state` и source checkpoint; `registry_state.last_successful_scan_at` — **durable proof успешного полного scan**; state transition `ready/degraded` | `registry_state.updated_at` и производные сводки только там, где не несут отдельного freshness смысла | Каждое новое событие/identity/snapshot; каждый реально продвинувшийся checkpoint; `ready/degraded/backfill` transition; **по текущему контракту — durable last_successful_scan_at после каждого успешного полного scan** | Только строго неизменные *побочные* поля/derived metadata или proven no-op state transition без freshness требования; timestamp throttling — **отдельное future design admission**, не текущий Coder GO | Не пропускать `mark_successful_scan()` только потому, что membership равен; не заменять scanner-success на process heartbeat; не объявлять готовность после incomplete scan |
| **`current_state.sqlite3`** — client/AP workers, `CurrentStateRepository` | `current_state_cycles` содержит `cycle_id`, site, scope, capture time, complete/result/errors, counts, quality; **каждый законченный attempt — собственное persisted evidence**; complete+empty в надёжной области охвата = отрицательный факт | Только самостоятельные consumer-проекции и дублирующие derived materialized summaries, если отдельно существуют и rebuildable | **Каждый `publish_cycle()`**, включая successful empty, partial, failed и их факт качества; `current_client_state`/`current_ap_state` атомарны со своим cycle; retention строго по защите pinned cycles | Лишь **вне** immutable authoritative cycle/history: независимо вычисляемый payload/update, если полностью отделён от cycle proof, digest+generation проверены и consumer truth не меняется | Не пропускать empty cycle; не переиспользовать прежний cycle_id/time; не выдавать старый successful за новый; не разделять атомарность cycle+rows; не выкидывать failed/partial |
| **`visits.sqlite3`** — Visit Lifecycle repository/reader/reconcile | `visits` start/end; `visit_authorizations`, `visit_source_events`, `visit_reader_state` source identity/offset/checksum, pending match, retry deadlines/counts, reconciliation attempted_at/next_at; idempotency | Повторно рассчитываемые display stats, telemetry; **не** retry deadline/count, last attempt или checkpoint | Каждое новое authorization/open/close/offline evidence, переход pending/terminal, прогресс reader, retry/reconcile attempt и состояние, меняющее eligibility следующей попытки | Только доказанные no-op ancillary metadata, не участвующие в retry/replay/health/idempotency; отсутствие rows при retry selection не равно разрешению удалять уже записанный progress | Нельзя продвигать offset без durable evidence, объединять auth/visit commit с несвязанным batch, пропускать late events, отсрочивать deadline/attempt или заменять source missing «0 событий» |
| **`public_traffic.sqlite3`** — `PublicTrafficWorker`, source reader, repository | `processed_events` idempotency; `reader_state`: identity/path/offset/checkpoint/observed_size/retired/missing; `traffic_daily` и counter resets в текущей модели не объявлены безопасно rebuildable, пока нет доказанного replay для retention | `reader_state.updated_at` **возможный** operational field, но его consumer/health semantics требуют инвентаризации | Каждый новый offline-event/processed id, atomic event+counters+checkpoint, каждая смена source identity/truncate/rotation/missing/retirement, progress и reset | **Кандидат H1:** не выполнять финальный `observe_source()` в steady idle, если проверенный *весь tuple reader_state* не изменился и `updated_at` не служит proof-of-observation/freshness; отсутствие `new line` само по себе недостаточно | Не гейтить только по `source_offset`, размеру файла или `traffic_bytes==0`; не игнорировать partial line/checkpoint, truncation, backup rotation/old inode, missing/reappearance; не переводить counters в memory-only |
| **`observations.sqlite3`** — Observation Foundation client/AP workers, repository | `observation_cycles`: `running` → `completed`/`abandoned`; `client_observations`, `ap_observations`, radio/config snapshots; per-cycle quality, provenance, site/scope | Secondary projections/reporting cache — только при independently proven rebuild | Каждая начатая cycle/attempt согласно действующему контракту и завершение с фактическими `success/partial/failure`/empty, archive/retention, recovery abandonment; atomically attach factual rows to their cycle | Только несущественные side metadata или explicitly rebuildable projections с теми же guarantees; не ликвидировать cycles ради IOPS без **нового отдельного data-model ADR** | Не объявлять пустым failed fetch, не считать отсутствующего клиента offline без complete source proof, не удалять attempt records, не скрывать partial или `running` после crash |

**Ограничение точности:** таблица классифицирует поля по семантике текущего кода и требованиям продукта, но **не** утверждает, что все упомянутые SQL/таблицы дают измеримый host IOPS вклад. Отдельные физические counts и все реальные consumers — research deliverable Tech Lead, не догадка Architect. `observations` может действовать как authoritative сохранённый snapshot, даже если исходный контроллер является authority сетевой реальности: после ingest этот cycle является authoritative evidence того, что именно было получено.

### 2.1. Freshness / exact temporal bounds

**Current State (кодовые дефолты, НЕ runtime-факты):** клиентский interval **60 s**, `fresh ≤60 s`, `stale ≤180 s`; AP interval **60 s**, `fresh ≤90 s`, `stale ≤300 s`; retention по умолчанию **48 h**. Tech Lead должен установить действующие значения из adopted settings и consumers. Даже если два цикла подряд одинаковы по составу, пропуск второго нарушил бы freshness classification и latest-attempt semantics. Историческая availability/negative proof — функция `site_id + kind + source_scope_hash + capture time + complete + result`, а не хеш списка MAC.

**Visitor Registry:** scan interval по коду по умолчанию **5 s**; это **не** лицензия на durable timestamp раз в 60 s. Временная гарантия действующего writer: при полном подтверждённом scan его `last_successful_scan_at` durable до последующего видимого transition. Архитектурно допускается иная верхняя граница сохранения freshness **только после consumer audit и отдельного нового контракта** с числовым bound `B`, где `0 < B ≤ min(all_consumer_max_staleness, recovery_required_freshness)` и guaranteed honest fail-closed после crash. Пока численные consumer constraints не известны, **B=не определено, per-complete-scan commit KEEP**. Никакого записи «успешно» после missing source, timeout, incomplete или только process alive.

**Visits/Public Traffic/Observations:** authority watermark должен остаться привязан к **последнему реально durable** источнику и соответствующему доказательству обработки; allowed lag для source event commit **0 дополнительных циклов** относительно существующего поведения. Любой batch/rebuild новый upper bound требует отдельного одобрения. Для derived cache freshness максимальное время = существующий consumer SLA, после истечения — `stale/unavailable`, не «last known fresh».

### 2.2. Omada outcome lattice (не сводить к «rowcount=0»)

| Состояние источника | Допустимый факт отсутствия | Durability / read behavior |
|---|---|---|
| `success + complete + correctly scoped + zero rows` | **Подтверждённое отсутствие в данном site/kind/scope на capture_at** | Записать новый cycle как доказательство в момент времени; пустой payload не обнуляет факт |
| `success + complete + nonzero rows` | Только отсутствие **внутри охваченного scope** для невыявленных объектов, если модель разрешает negative inference | Сохранить cycle+rows, canonical source scope/quality |
| `partial` (page/budget/duplicate/malformed) | **Нет глобального отрицательного факта** | Сохранить attempted/partial и failure/category; не маскировать предыдущим success |
| `error/timeout/unavailable` | **Никакого подтверждения отсутствия** | Durable failed attempt, error metrics; старый success может оставаться history, но считается stale по собственному timestamp |
| `shutdown/incomplete` | **Никакого подтверждения отсутствия** | Текущее recovery поведение и маркировка incomplete/abandoned; не генерировать synthetic complete |
| Нет сканирования / сервис остановлен | **Никакого нового факта** | Не продвигать watermark, age растёт; monitor/service state честно показывает отсутствие свежего proof |

**Приоритет для read:** newest attempt и latest verified complete сохранять как **разные** понятия; новый error не должен превращаться в успешный empty и не должен «омолаживать» старый positive. Исторически закреплённые cycle id, cursor/pagination, source scope и pinned cycle retention остаются реальными.

## 3. Transaction ownership, durability и batching

1. **Не менять** действующие `PRAGMA synchronous`, `journal_mode`, `wal_autocheckpoint`, `busy_timeout`, page size, locking semantics, filesystem mount flags, checkpoint schedule и durability promised per module. Замечание: в текущем коде `CurrentStateRepository.initialize()` и `PublicTrafficRepository._connect()` уже используют `journal_mode=WAL` и `synchronous=NORMAL`; задача **не** предлагает ни ослаблять, ни повышать эти режимы, а сохраняет нынешние contracts. Нельзя приписывать каждому DB `FULL`, не проверив код.
2. **Операции событий и watermark должны коммититься атомарно**, где это уже предусмотрено (Public Traffic `processed_events + traffic_daily + reader_state`; Visits `offline evidence + reader progress`; Current State `cycle + rows`). Запрещено обновить durable cursor раньше доказанного durable effect или гарантированного idempotent replay.
3. **Никакого междоменного batching**: Registry/Visits/Current State/Public Traffic/Observations имеют разные независимые authority и recovery graphs. Нельзя синхронизировать их одним worker batch или объединять отложенные commit границы.
4. **Derived-only coalescing** допустимо **только** если один writer/owner, одна DB и один derived lineage/generation, deterministic rebuild проверен на retained authoritative source, нет читателей с per-event freshness/ordering/pinned cursor, и bounded crash/replay воспроизводим. Коалесценция изменений между независимыми authoritative facts — запрещена.
5. No-op guard должен быть защищён от TOCTOU: сравнению подлежит **canonical persisted tuple** с version/CAS или под текущим owner lock; не добавлять SELECT или lock, которые ухудшают CPU/read I/O сильнее записи. Проверить Lab adversarial concurrent writer/failure.
6. Отдельная оптимизация «упразднить BEGIN/COMMIT вокруг SELECT, когда нет rows» **не считается физической** без tracer/host evidence; SQLite пустая транзакция может не дать дискового I/O и тоже нужна сериализация для корректной state machine.
7. Нельзя глобально ставить `synchronous=OFF`, `journal_mode=MEMORY/OFF`, отключать `fsync`, менять только `wal_autocheckpoint` или делать `VACUUM`, `REINDEX`, forced checkpoint на живом HDD для QIO-02.

## 4. Crash, restart, replay — жёсткие сценарии и correctness C01–C18

| ID | Сценарий | Обязательное ожидание |
|---|---|---|
| **C01** | Полный successful unchanged Visitor Registry scan | Реальное durable `last_successful_scan_at` не устаревает против baseline; state/health остаются корректны |
| **C02** | Registry incomplete/missing/unavailable после предыдущего ready | Нет нового successful-scan proof; переход в degraded и reason видны; после recovery новый proof только после complete scan |
| **C03** | Registry offline→online, identity change, source rotate/truncate, duplicate, late snapshot | Ни один processed-event/checkpoint, idempotency marker или принадлежность не теряется; нет cross-MAC/site merge |
| **C04** | Current State complete+empty client inventory | Новый cycle с корректной областью охвата, 0 rows и действительным timestamp durable; consumer подтверждает absent только при свежем complete |
| **C05** | Current State partial/error/timeout и предыдущий success | New attempt persist; freshness previous success не продлевается; negative не фабрикуется |
| **C06** | Current State duplicate/unknown identity и page limit, fail budget | `complete=false` где требуется; source quality/errors durable; нет false absence |
| **C07** | AP/client source scope change и pinned pagination cursor | Смена scope не реиспользует старый цикл; retention не удаляет protected/pinned proof вне существующих гарантий |
| **C08** | Visit start/auth/visit open/end/offline race/duplicate | Один корректный irreversible факт на idempotency key; нет двойного закрытия, утраты Visit/Auth и ошибок auth |
| **C09** | Visit reader offset / checkpoint advance, process crash перед/после commit | Cursor никогда не ahead durable effects; replay safe and idempotent; никаких lost/gap events |
| **C10** | Visit pending row, retry deadline, late identity, reconciliation без новых исходных строк | Дедлайны/attempts/match state остаются durable; late resolving не ухудшен |
| **C11** | Public Traffic repeated EOF with **exact unchanged source tuple** | Условный H1 не изменяет replay/health/retirement/observed freshness; если хотя бы один consumer зависит от `updated_at` — H1 HOLD |
| **C12** | Public Traffic appended line, duplicate, 0-traffic event, partial line, inode rotation/truncate, missing source, reappearance | Atomic `processed_events + counter + checkpoint`; верное disposition и idempotent replay; missing не считается empty |
| **C13** | Observation `running` → successful/partial/failed cycle, startup abandonment | Сохранены оба исходных состояния и корректная retention/restart семантика |
| **C14** | Crash после authority commit до derived materialization | Derived output rebuilt deterministically from committed facts; новая materialization не выдаёт ложную актуальность |
| **C15** | Crash/kill до commit / после commit и повторный запуск | Данные либо не видны и подлежат replay, либо durable и не задвоены; никаких memory-only «успешно обработано» |
| **C16** | Stale/unknown Omada, недоступный источник, interrupted scan, clock jump | Никакой новой guaranteed freshness; age вычисляется по trusted persisted times; monotonic для wait, absolute UTC для persisted event |
| **C17** | Auth/Guest E2E при normal/peak, backlog, disk busy, restart | Auth response/error categories, CAPPORT/Omada, Visit/Registry/Current State source claims и deadlines не ухудшены |
| **C18** | Audit/security, retention, schema mismatch/corruption | Ни одно обязательное событие/сигнал не исчезло, corruption не превращается в successful startup, protected fact не удалён |

**Failure injection только в одноразовой Lab-копии** с чисто тестовыми identities/источниками. **Не** использовать live production события/секреты в тестовых отчетах. Любые fail-closed read paths должны оставаться fail-closed; не лечить `unavailable` чтением старого «удобного» snapshot.

## 5. Отдельный COLD-START риск — НЕ смешивать с steady-state writes

Во время недавнего QIO-01B старта `captive-portal.service` ~11 минут не обслуживал внешний HTTP; были долгие чтения `visits.sqlite3`, затем `current_state.sqlite3`, когда HDD испытывал contention. Это **не** доказательство чрезмерных idle COMMIT. В исходном коде `VisitRepository._startup_check()` выполняет `PRAGMA quick_check` и schema validation; `CurrentStateRepository` выполняет проверку существующей DB при инициализации; подобные чтения потенциально дороги на HDD.

Для **отдельного** `QIO-STARTUP-READ` исследования: read-only установить loaded code, точный startup stack/timing, число cold physical reads и страницы, competing host writers, timeout behavior/readiness; в Lab оценить bounded validation и уже существующий кэш/проверочный протокол без пропуска corruption detection и без выдачи `ready` до авторитетного readiness gate. **Нет допуска** отключать `quick_check`/schema validation, переносить essential integrity check за auth-ready, удалять DB или рестартовать production ради профиля. Результат read-side эксперимента не смешивать с QIO-02 host write IOPS.

## 6. Conditional first hypothesis / priority — по причинности, не по интуиции

**Предпочтительный малый Lab-кандидат H1 (НЕ автоматическое Coder GO):** `PublicTrafficReader._process_source()` выполняет финальный `repository.observe_source()` после EOF, а `PublicTrafficRepository._upsert_reader_state()` делает `ON CONFLICT DO UPDATE` включая `updated_at` даже когда `source_identity/path/offset/checkpoint/observed_size/retired_completed` прежние. Это конкретный bounded no-op кандидат, *если* нет обязательного proof-of-observation на `updated_at` и прямой per-file физический вклад значим.

**Проверяемая гипотеза:** после полного same-generation EOF и unchanged persisted source tuple можно избежать только вспомогательного повторного `observe_source` write, сохранив все source checkpoints/progress/retention/failure, в том числе для missing/truncated/reappearing файлов; delta host writes в matched quiet положителен.

**До допуска H1 Tech Lead должен представить:**

1. **Per-DB hotpath matrix**: `public_traffic.sqlite3` vs `visitor_registry.sqlite3` vs `visits.sqlite3` vs `current_state.sqlite3` vs `observations.sqlite3`: call frequency, SQL rows affected, `BEGIN/COMMIT`, actual `fdatasync`/WAL/checkpoints и коррелирующий guest/host I/O по согласованным границам. Никакого вывода из одного `mtime`/SQL plan.
2. Для `PublicTraffic.reader_state.updated_at`: **полный consumer graph** (read services, Admin UI/API, health, alerts, replay, cleanup, forensic audit). Если хоть одному consumer нужно подтверждение повторного same-offset scan с временным SLA, **H1=REJECT в текущем виде**, нужен отдельный freshness design, а не скрытие.
3. Подтверждение нескольких источников/ротаций: source tuple включает `source_identity`, path, offset, checkpoint hash, observed file size, `retired_completed`, source missing/reappeared; check/skip атомарен относительно writer. Нужно доказать, что `missing_warning_emitted` и изменённая identity/rotation не пропадают.
4. Перевод H1 в Lab: единственный narrow change, откатимый без schema/data migration; explicit source identity and reader state equality, negative cases C11/C12/C15. `updated_at` нельзя просто объявить operational по имени.
5. Минимум **3 matched quiet окна по 10–15 мин** до и после Lab, плюс normal/peak/catch-up; по возможности одно длиннее и в другое время суток. Отдельно считать host `/dev/sda` completed IOPS, await, busy/PSI и полезность source freshness. Если writer не физический лидер или экономия нетто сомнительна, **вернуть EVIDENCE_REQUIRED / выбрать следующий фактический hotspot**, даже если guard SQL корректен.

**Резервный кандидат H2:** только *после* отдельной архитектурной проверки SLA рассмотреть decoupling Registry membership-derived updates from durable scan freshness. **`mark_successful_scan()` не убирать под QIO-02 v1.** Если профилирование выявит Registry как крупнейший физический writer, Tech Lead возвращает более узкий архитектурный запрос `Q2-REGISTRY-FRESHNESS` с точными consumers и max tolerated staleness. Нельзя выбрать произвольное `B=60s`.

**Резервный кандидат H3:** narrow derived-only metadata updates в Visits/Current State, **без** изменения authoritative cycle/reader progress; если их физический объём подтверждён и независимая materialization/consumer модель позволяет это. Действующий `CurrentStateRepository.publish_cycle` **не** отвечает H3: его записи являются canonical cycle evidence.

**Правило выбора:** ранжировать сначала **доказанный per-operation вклад в host physical small writes** × доля устранимых без semantic loss × риск × ожидаемая сложность обратимости. Не ранжировать по размеру DB, частоте GET, CPU или суммарному I/O процесса. H1 — условный технически узкий эксперимент, **не** утверждение, что Public Traffic крупнейший источник.

## 7. Performance / operational gate

### 7.1. Tech Lead READ-ONLY пакет

- Проверить `main`, TREE/loaded artifact per-process, активные feature flags, production paths/schema/`PRAGMA`, компоненты (`Visitor Registry`, `Current State`, `Visits`, `Public Traffic`, `Observations`) и источник входных данных; не включать/выключать сервисы для удобства.
- Три ≥10–15-минутных quiet окна на сопоставимой нагрузке; synchronized begin/end guest and host, device map без double counting; несколько времен суток; поля guest clients, SPAN packets, backlog, Omada health, timestamp accuracy, source age, cron/journal activity.
- Для каждого DB и cycle: `who → trigger → SQL/BEGIN/COMMIT → checkpoint/fdatasync → guest cgroup wios/wbytes → QEMU host wios/wbytes → host /dev/sda write iops/await/busy`. Кратковременный read-only telemetry с bounded CPU/IO; тяжелое trace/profiling только Lab.
- Указание hotpath и конкурирующих cgroup sources; no per-file/transaction physical I/O attribution из `stat`, `syscr`, WAL size или sampled `fdatasync` alone.

### 7.2. Лабораторный PASS (отдельно correctness и performance)

- `Correctness`: C01–C18 PASS, consistent effective data provenance, freshness and negative proofs, no lost audit/auth/evidence, restart/crash/late and no false ready.
- `SQLite`: точная причинность на выбранной операции: число фактических owner commits, busy retries, WAL/checkpoints, writes/fdatasync; lock hold time, CPU/read overhead, worst-case retry; никаких ослаблений configured durability.
- `Guest`: per-service writes/bytes, I/O PSI; throughput и latency Omada scans/auth, no backlog accumulation.
- `Host`: **matched** `QEMU Ubuntu host cgroup` + `/dev/sda` completed writes/sec, write await, busy, total host I/O; median и хвост/P95 по окнам, другие VM/scheduled jobs/accounting noted.
- `Reproducibility`: независимый Tech Lead review и QA; повторное окно того же workload с выключенным оптимизационным флагом в Lab (не в production), где корректно; no performance PASS если только `SQL steps↓`, `WAL bytes↓`, `syscw↓` без host signal.

### 7.3. Дальнейшие stage gates

- **P0 — PASS:** архитектурная граница этой версии принята (но не разрешает менять code).
- **P1 — EVIDENCE_REQUIRED:** Tech Lead возвращает attributed per-DB/operation matrix и consumer graph для конкретного кандидата.
- **P2 — LAB_ADMISSION:** Architect согласует ровно одну bounded hypothesis с explicit exact semantics; Tech Lead выпускает узкий Coder/Lab implementation contract. До P2 `CODER=HOLD`.
- **P3 — LAB_PASS:** correctness + performance на disposable workload, regression тесты, worst-case crash.
- **P4 — OWNER_GO:** отдельно Owner одобряет rollout; staged canary, backing artifacts, reproducible rollback plan без миграции/потери immutable фактов.
- **P5 — POSTDEPLOY:** matched host/guest monitoring по quiet+normal/peak; при нетто-ухудшении или semantic regression revert и закрыть гипотезу как failed, не продолжать в следующую production правку.

## 8. Scope / rollback / boundaries

**QIO-02 IN:** только физический I/O, вызванный SQL/SQLite фоновых workers **основного** `captive-portal.service` в состояниях low-user/catch-up, с доказанной пер-операционной причинностью.  
**OUT:** QIO-01D telemetry/journald, PR #215/SSR-01B, NI-01 A/B, NI-02B queue changes, MicroK8s, host/guest SSD migration, Omada TLS, guest network/Cisco, `fingerprint-evidence` startup, любые изменения auth/security/user experience, не связанные непосредственно с упомянутым writer. Cold-start = отдельная read-risk ветка.

**Откат**: только versioned scoped change, без schema migration, без удаления/wipe/vacuum, без cursor rewind/fast-forward, с полным сохранением durable source. Прежний код должен читать уже записанные факты. Если изменение невозможно откатить без cleanup/migration, оно не допускается как первая гипотеза. В Lab rollback test выполняется до предложения Owner GO.

## 9. Формальная передача Tech Lead

```ini
TASK=QIO-02
CONTRACT=QIO-02-SQLITE-SMALL-IO-ARCHITECTURE-ADMISSION-v1
ARCHITECTURE=MODIFY_SEMANTIC_BOUNDARIES_APPROVED
DECISION=MODIFY
READONLY_MEASUREMENT=GO_BOUNDED
CAUSAL_ATTRIBUTION=EVIDENCE_REQUIRED
CANDIDATE_1=PUBLIC_TRAFFIC_SAME_SOURCE_TUPLE_NOOP_CONDITIONAL
CANDIDATE_1_ADMISSION=HOLD_CONSUMERS_AND_PHYSICAL_COST
VISITOR_REGISTRY_PER_COMPLETE_SCAN_FRESHNESS=KEEP
CURRENT_STATE_EVERY_ATTEMPT_CYCLE=KEEP
VISIT_AUTH_SOURCE_CHECKPOINT_RETRY_PROGRESS=KEEP
OBSERVATIONS_CYCLE_AUTHORITY=KEEP
DERIVED_ONLY_NOOP=ALLOW_IF_N1_TO_N7_PROVEN
LAB=HOLD_PENDING_OPERATION_EVIDENCE_AND_ARCH_ADMISSION
CODER=HOLD
PR_MERGE=NO
PRODUCTION_CHANGES=NO
OWNER_GO=REQUIRED_SEPARATELY
DURABILITY_WEAKENING=FORBIDDEN
COLD_START_READ=SEPARATE_RESEARCH
QIO_01D=SEPARATE_TRACK
SSR_01B_PR_215=UNTOUCHED
```

**Запрос обратного пакета Tech Lead:** после синхронных измерений вернуть `QIO-02 PER-DB PHYSICAL-WRITE & CONSUMER-SEMANTIC EVIDENCE` с ranking, точными loaded artifacts, producer `cycle→SQL→commit` и первичной recommendation (`H1 PASS_TO_LAB / H1 REJECT / ALTERNATE`). Если writer безусловно authoritative/freshness либо физическая причинность не доказана — не начинать Coder, даже если чисто математически хочется «убрать один COMMIT».  

**Конец Architecture Admission Contract v1.**
