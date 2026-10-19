# CAPTIVPORTAL — QIO-EVIDENCE-IDLE-01
## Chief Architect: Fingerprint Evidence Startup Integrity / Read-Pressure Architecture Contract v1.1 — Owner LAB override

**Дата:** 2026-10-17 (Asia/Baku)  
**Адресат:** Performance & Optimization Tech Lead  
**Объект:** только Fingerprint Evidence на **лабораторной VM** из forensic `192.168.0.202`. Owner в новом сообщении написал `192.168.202`; этот неполный IPv4 не подменяет подтверждённый forensic-адрес: перед подключением Tech Lead сверяет identity VM. **НЕ** действующий новый `captiv-prod`, **НЕ** Network Metadata.  
**Решение:** **`APPROVE_CONTRACT` + `LAB_VM_FULL_SCALE_MEASUREMENT=GO` по явному Owner LAB override.** Прямые полные чтения, аудиты и стартовые A/B/A на лабораторной VM разрешены, даже если HDD загружен. `FAST_READY_IMPLEMENTATION=HOLD` до эквивалентных гарантий; Coder/new-production GO не выданы.  
**Базис:** Tech Lead `QIO-EVIDENCE-IDLE-01-TECHLEAD-FORENSIC-2026-10-17` и Architecture Request; статическая сверка `ZaurNavi/CaptivePortal@810484e69baa371c4696c3b46654199631538fc4` (`app/device_fingerprint/repository.py`, `schema.py`, `service.py`, `cli.py`, `storage_v2.py`). Исправление v1.1 внесено **только в исследовательский контур** по явному указанию Owner: «работаем сейчас на виртуалке ... это наша лаборатория», без ограничений ради загруженности лабораторного HDD. Изменений службы, БД или кода этим документом не выполнено.

## 0. Owner LAB override — нормативная поправка к v1 (2026-10-17)

**Owner отменил запрет на тяжёлую диагностику лабораторной VM.** Для QIO-EVIDENCE-IDLE-01 **сама VM и физический HDD под ней являются целевым экспериментальным стендом**, а не средой, которую нужно беречь от полного чтения. Наличие SSD на ноутбуке делает его нерепрезентативным для этой физической проблемы. Поэтому:

- **Разрешены на подтверждённой лабораторной VM:** полные `PRAGMA quick_check` и другие глубокие read-only SQLite проверки, полные guard-сканы и JOIN, `EXPLAIN`/SQL tracing/profiling, запуск/остановка **только** лабораторной `fingerprint-evidence.service`, контролируемые повторные A/B/A, cold/warm-start, длинные прогоны и одновременные guest/host HDD измерения. Техлидер выбирает методику и фиксирует реальный эффект, даже если I/O busy/PSI высокие.
- **Отменены как условия допуска LAB:** пороги HDD busy/PSI, `throttle` из заботы о старой VM, обязательный уход на ноутбук/WSL/SSD и запрет на полный скан из-за его длительности. Время/объём чтения **измеряем**, а не ограничиваем заранее до начала опыта.
- **Для corruption injection, разрушительных WAL/DB сценариев, `SIGKILL` с риском повреждения/потери содержимого:** использовать отдельную одноразовую копию/fixture **на этой же лабораторной VM** (с HDD-фиделити), а не безвозвратно повреждать исходную большую базу. Для восстановимых старт/стоп, полного аудита и read-only measurement допустима сама лабораторная Evidence DB.
- **Не разрешено:** действия на действующем `captiv-prod`, Network Metadata, эксплуатационное включение непроверенного fast-start, обнуление allocator/generation, снижение SQLite durability. Контроль целостности и fail-closed семантика остаются обязательными **для любого будущего исправления**, а не как ограничение лабораторного исследования.
- **Scope разрешения:** это прямой Owner GO на **LAB measurements/controlled LAB service cycle**, но не Coder implementation, публикацию, merge или перенос экспериментального кода в production. Тестовые инъекции ошибок и меняющий БД прототип — только после точной изоляции/отдельного допуска соответствующего этапа.

### 0.1. Подтверждённый диагноз и пределы доказательств

- Evidence DB: **3 796 074 496 bytes**, **926 776 SQLite pages** по 4 KiB, `last_ingest_sequence=2 834 788`. Файл велик, но индексные границы `observed_at` соответствуют приблизительно 30 суткам: просроченный retention backlog **не доказан**; `VACUUM` не назначается.
- A/B/A по старой VM, 45-секундные окна: host `/dev/sda` **2,64 → 56,20 → 3,31 read IOPS**; busy **35,88 → 65,68 → 24,95%**; guest `/dev/vda` **0,04 → 56,17 → 0,07 read IOPS**; guest I/O PSI full **7,32 → 35,15 → 8,59%**. Окна host/guest не идеально совмещены; фоновые host writers отличались. Доказана сильная причинная связь **старта Evidence с ростом read pressure**, а не точное распределение каждой операции по SQL и не снижение write IOPS.
- `DeviceFingerprintRepository.initialize()` до выдачи API readiness вызывает `_validate_connection()`: **полный** `PRAGMA quick_check`; signature/schema/storage state; два потенциально линейных `ingest_sequence` invalid-row поиска; межтабличный collision JOIN. Отдельный `quick_check` не завершился за >2 мин, отдельный sequence guard был прерван на 4 с; `_validate_runtime_connection()` ~0,002 с, но **не эквивалентен** глубокому аудиту.
- Диагностическая временная замена deep validation на bounded в однократном LAB процессе дала **3,500 с**, но дала около **356 352 proc.write_bytes**, и **не была безопасным read-only proof** или кандидатом в production. Статус целостности старой DB **не подтверждён**: `quick_check` не завершён.
- Логическая стоимость проверок не обязана равняться host physical reads; производительность целевого нового `captiv-prod` не исследована и не предполагается.

## 1. Архитектурный принцип / границы доверия

1. **Нельзя заменить** `PRAGMA quick_check` + глобальные guards на `_validate_runtime_connection()` и объявить сохранённую защиту: проверка схемы и singleton не обнаружит произвольную порчу страниц, исторические CHECK нарушения и cross-table ingest-sequence collision.
2. **Deep audit — не то же самое, что fast admission.** Их можно разделять только если перед допуском чтения/ingest есть *доказанное доверие к точной DB generation/snapshot и ко всем последующим committed изменениям*. При отсутствии этого доказательства использовать legacy deep-before-ready или оставаться `not-ready`.
3. **Не существует бесплатного O(1) доказательства целостности произвольно изменяемых 3,8 ГБ** после отключения полного сканирования. В частности, `mtime`, inode, `page_count`, `freelist_count`, singleton `database_generation_id`, `last_ingest_sequence`, `PRAGMA quick_check(1)` или `PRAGMA data_version` **не являются** доказательством неизменности всех страниц и WAL.
4. **Никаких ложных гарантий:** `quick_check` сам НЕ проверяет UNIQUE или согласованность содержимого индексов с таблицами; сравнивать следует с фактическим набором гарантий существующего startup (`quick_check` **плюс** собственные guards), а не с воображаемым «идеальным integrity_check». Полный `integrity_check` для отдельных recovery/migration процедур — иной, ещё более тяжёлый gate.
5. Архитектура допускает две разные цели: **(а)** устранить избыточный read pressure при *доказуемо эквивалентной* integrity-gate, **(б)** отдельно предложить Owner явно ослабленную политику обнаружения исторической corruption. Цель (б) не разрешена настоящим контрактом и требует нового Owner risk/admission. Никогда не выдавать (б) за (а).

## E1. Startup invariant — APPROVE_CONTRACT, gated design

**Сохранить действующее правило:** до подтверждённой пригодности DB Evidence не принимает новое ingest и не выставляет `ready`, включая source-health; не выдаёт заведомо неподтверждённую историю как достоверную.

**Допустимая для исследования двухступенчатая схема:**

- **Stage F — bounded metadata preflight (fast, не trust):** writer-lock ownership, exact artifact/schema/version/expected indexes/SQL CHECK fragments, singleton/generation/allocator, DB path/permissions/storage bounds, SQLite/WAL-open error classification, bounded indexed lookups и отсутствие активной migration/recovery. Результат F означает только `METADATA_VALID`, **не `INTEGRITY_VERIFIED`**.
- **Stage T — trustworthy admission:** либо (T1) существующий deep check завершён успешно на *той же live generation/snapshot* до допуска ingest, либо (T2) успешно проверенная **immutable/offline snapshot generation** с криптографически/транзакционно доказанным непрерывным lineage всех последующих коммитов, отсутствием сторонних writers, доказанным покрытием committed WAL/restore/checkpoint и подтверждением невозможности незамеченной порчи. Полная формализация T2 и практическая реализация **не предъявлены**, поэтому сейчас `T2=UNPROVEN/HOLD`.
- **Stage R — ready + ingest:** только после `F && T`; writer-lock/uniqueness/idempotency сохраняются. При любом несовпадении attestation или неизвестном состоянии — **не принимать события**, не переходить к bounded-only fallback. Предусмотреть безопасный explicit offline recovery с отдельным Owner GO.

**Ключевое следствие:** вынесение полного сканирования в фон *при продолжении записи в ту же недоверенную DB* сейчас **не допускается**. Фоновая deep-проверка на immutable/consistent backup разрешена как исследование, но сама по себе **не аттестует изменившуюся live DB**. Режим отдельной новой trusted ingest-generation или durable quarantine возможен только как **новый архитектурный запрос** с миграцией/ownership/consumer contract, не скрытый shortcut E1.

## E2. Fail-closed / retries / startup readiness — PASS как invariant

- Состояния: `starting` → `metadata_checked` → `integrity_pending` → `integrity_verified` → `ready`. Отдельные терминальные/деградированные: `integrity_unverified`, `integrity_failed`, `integrity_timeout`, `storage_unavailable`, `writer_lock_unavailable`, `recovery_required`. Это концептуальные состояния; **не** предписание немедленно менять существующий публичный API/schema.
- Во всех `pending/unverified/failed/timeout`: **нет success HTTP evidence ingest, source-health ingest, background retention writes, reads, заявленных verified, и ложных successful health**. Статус `systemd active` или «порт слушает» не равен `ready`. Если локальная диагностическая health endpoint возможна — только read-only/неэкспонирующая недоверенные данные и явно `not-ready`.
- `timeout` или SQLite I/O error — не успех, не бесконечный блокирующий startup и не бесконечный `Restart=on-failure` storm. Сервис должен завершить проверку контролируемым отказом либо оставаться в безопасном `not-ready` в рамках заранее установленного stop/retry policy. Этим контрактом **не разрешается** менять systemd; в отдельном P2 gate Tech Lead проверяет существующие `Restart`, `StartLimit*`, stop timeout и задаёт точный retry admission с SysAdmin/Owner.
- При `SQLITE_CORRUPT`, schema mismatch или invalid sequence/collision — `integrity_failed`/`recovery_required`; автоматический rebuild/обнуление/rebaseline запрещены. После нового старта доверие не наследуется из памяти процесса.
- Все ошибки и блокировки должны быть наблюдаемы с bounded-rate telemetry, без флудящих per-page logs/секретов/личных Evidence payload.

## E3. Integrity preservation / offline attestation — HOLD до proof

Требуемый proof для T2 (не обещание, что он достижим без новой архитектуры):

1. **Точный источник:** SQLite-consistent immutable snapshot через штатный backup API/эквивалент, под подтверждённым single-writer/lock и без раздельного небезопасного копирования `.sqlite3` и `-wal`. Привязка к artifact SHA, schema signature, generation UUID, размерам, полному логическому/физическому evidence fingerprint и зафиксированному WAL snapshot horizon.
2. **Успешная полная проверка snapshot:** набор `quick_check + schema/storage + ingest-sequence invalid/collision guards` с полным результатом и отрицательными corruption fixtures; отдельный `integrity_check` только если выбран явно более строгий стандарт. Не выдавать частичную проверку/отменённый запрос за PASS.
3. **Неизменность либо ledger:** если snapshot **sealed immutable** и не меняется, она может иметь долгоживущую attestation; для mutable active DB требуется транзакционно доказуемый и проверяемый на recovery lineage всех последующих committed изменений/страниц. Само **хранение хэша/manifest** без его надёжной проверки после crash/bit rot не доказывает фактические байты, а полный re-hash снова O(N). Отдельный tool/endpoint `data_version` не заменяет это.
4. **Crash и подмена:** неверный/устаревший generation, rollback из backup, WAL survives without checkpoint, clean shutdown и `SIGKILL`, power failure, db+wal replacement, partial/corrupt attestation, чужой writer, исчезновение seal/readonly flags — все **инвалидируют trust или проходят отдельно доказанное восстановление**. Не доверять timestamp marker/`last_ingest_sequence` из потенциально повреждённой самой DB как единственному свидетельству.
5. **Контроль при чтении:** успешная historical attestation не даёт обещания, что диск не испортился позже; при SQLite corruption/IO-error любой runtime read/write fails closed, важны текущее snapshot-consistency и monitoring. Не провозглашать абсолютную защиту от silent storage corruption без проверки данных.

**Предпочтение:** сначала на **той самой лабораторной VM** измерить полный текущий startup и все четыре его дорогостоящих элемента на реальном HDD; затем на изолированных HDD-расположенных копиях/fixtures исследовать аттестацию, identity-preserving fast admission и её coverage. Если эквивалентность на mutable live базе не получается — **вернуть `HOLD` и не заменять deep-before-ready**. Возможная будущая hot/immutable-archive архитектура — отдельный Evidence migration project, не часть узкого стартового фикса.

## E4. SQL invariants / global ingest sequence — обязательны

| Категория | Текущая защита | Что нельзя терять | LAB-кандидат (не одобренный fast fix) |
|---|---|---|---|
| Schema/column/constraint | exact signature + `user_version` | существующая версия, типы, CHECK/NOT NULL, индексы, protected schema | bounded signature at F, deep audit retained at T |
| Row-level CHECK / malformed pages | полный `quick_check` | обнаружение CHECK/структурных ошибок до доверия | не заменять `quick_check(1)` или `SELECT LIMIT 1` |
| Ingest sequence type/range | две таблицы с `CHECK(ingest_sequence BETWEEN 1 AND MAX)` и собственный `typeof`/range scan | не допустить отрицательные/нецелочисленные/sequence > allocator исторические значения | для *новых* вставок existing CHECK + allocator under `BEGIN IMMEDIATE`; min/max via indexes может доказывать только часть свойств при заранее доверенной DB; в противном случае нужны deep guards |
| Duplicate sequence внутри каждой таблицы | `UNIQUE(ingest_sequence)` | нет внутритабличных повторов | сохранять индекс; не считать его проверку заменой `quick_check` |
| Cross-table collision | `JOIN evidence.health ON ingest_sequence` | единое sequence-пространство двух таблиц | текущие два независимых UNIQUE **не запрещают** cross-table collision; исследовать pointwise cross-table guard/trigger или единый allocator-ledger, но это отдельное изменение schema/commit cost и требует миграции + статического доказательства исторической чистоты |
| Allocator state | singleton + max range | durable monotonic `last_ingest_sequence`, generation and replay | никаких generation resets/counter gaps normalization; retention законно оставляет gaps |

**Нельзя:** скрыто считать `MAX(ingest_sequence)` полным integrity proof; делать `SELECT ... LIMIT 1` вместо CHECK; менять SQL так, чтобы adversarial row в середине history стал невидимым; удалять table/schema/INDEX проверки; включать PRAGMA `ignore_check_constraints`/`writable_schema` ради тестов вне disposable LAB.

## E5. LAB HDD startup I/O — прямая диагностика на VM (Owner override)

**Нормативный выбор среды:** все измерения, которым нужна реальная механика дисковых задержек, выполняются **на лабораторной VM из forensic (`192.168.0.202`) и её физическом host HDD**, а **не на ноутбуке/SSD**. Tech Lead вправе проводить полный стартовый аудит без искусственного 5-секундного timeout, лимита 16 MiB, quiet-обязательства или PSI/HDD-busy gate.

1. **Сначала замерить неизменённый baseline:** отдельно `PRAGMA quick_check` (полное выполнение, без `LIMIT`/premature PASS), signature/schema/state, оба полных `ingest_sequence` guards, cross-table collision JOIN. Для каждого записать elapsed, start/end, SQL plan, `pread64`, байты, SQLite VM steps, lock time и любые incidental writer IO при `initialize()`. Установить реальные индивидуальные и суммарные доли; предыдущий quick_check >2 мин и 4-секундный interrupt не дают полного результата.
2. **Полные проходы разрешены:** на лабораторном HDD специально проверять worst-case cold/hot page cache, большой реальный historical corpus, повторный restart, системный HDD await/busy, VM PSI, QEMU I/O и физический `/dev/sda`. Высокая загрузка диска является **предметом измерения**, а не поводом автоматически запретить испытание. Не считать VM `read IOPS` прямой копией физического HDD IOPS; окна выравнивать и учитывать host background I/O.
3. **Кандидат быстрого допуска:** цель убрать O(N) глубинные сканы из критического пути **только при доказанной эквивалентности trust gate T** (E1–E4), либо сохранить полный deep-before-ready. Не навязывать `≤5 sec`/`≤16 MiB` как архитектурно обязательный SLA без результата стендовых измерений; сравнить точные read-amplification и readiness от исходного алгоритма и нескольких проверенных вариантов.
4. **Полный/оффлайн аудит:** можно выполнить на лабораторной DB в остановленном сервисе, на корректном SQLite-consistent snapshot либо специально подготовленной HDD fixture. Аудит продолжается до реального результата или явно маркированной ошибки/прерывания; `timeout` никогда не засчитывается как целостность PASS. Для будущей **эксплуатационной** двухступенчатой схемы отдельная доказанная политика lineage/snapshot по E3 обязательна; в LAB разрешение на тяжёлую проверку её не заменяет.
5. **Прогоны с записью/ошибками:** `repository.initialize()` способен менять служебные файлы/производить disk writes даже без HTTP: это уже показано forensic. Перед любыми опытами, допускающими запись, зафиксировать baseline, режим журнала/WAL, checkpoint/allocator/generation и точку восстановления. Создавать отдельную копию для corruption injection; не заявлять «read-only» только потому, что запрос был SELECT.
6. **Наблюдаемость:** реальное время до `ready`/API HTTP, `validation_stage`, проверенная generation и provenance, полная/частичная валидность аудита, error category, `rows/pages examined`, physical read bytes/IOPS/await/busy, guest/QEMU I/O, PSI, background host contributors, WAL state, lock-owner, extent of startup writes. Публиковать ограниченные агрегированные метрики без Evidence payload/секретов.
7. **Раздельные результаты:** `cold-start HDD read pressure` ≠ `steady-state WAL writes` ≠ `retention writes` ≠ `HTTP readiness`. Ни уменьшение времени старта, ни исчезновение 56 HDD read IOPS не доказывают уменьшения physical write IOPS.

**Запрет из исходного E5 v1 «не проводить полные сканы на загруженной старой VM; исследовать на ноутбуке» отменён Owner.** Тайм-ауты/ограничения используются только как часть выбранного тестового сценария, а не для искусственного прекращения целевого чтения. Это изменение режима лаборатории **не смягчает** эксплуатационный fail-closed контракт E1–E4.

## E6. Admission and acceptance gates

### E6.1 LAB corruption/recovery matrix C01–C20

**Синтетические disposable базы **на лабораторной VM/HDD** для всех разрушительных сценариев; для реального read-only baseline допустима собственная лабораторная Evidence DB. Действующий production dataset не используется; исходник и версия SQLite pinned.** Проверять legacy outcome и candidate на том же повреждении. Пропуск возможен только для documented divergence с новым Owner risk authorization — которого сейчас нет.

| ID | Сценарий | Ожидаемый результат |
|---|---|---|
| C01 | свежая корректная DB / schema v2 | readiness после полноценного T; ingest / replay PASS |
| C02 | большая корректная DB, cold cache / hot cache | bounded F; T trustworthy, без ложного PASS |
| C03 | schema/user_version/table/index/CHECK signature mismatch | fail closed |
| C04 | валидный sqlite с исторически нарушенным `CHECK` | fail closed до ingest |
| C05 | повреждённая database page / freelist / record | fail closed, без auto rebuild |
| C06 | нецелочисленный/NULL/отрицательный/слишком большой `ingest_sequence` | fail closed |
| C07 | `ingest_sequence > last_ingest_sequence` в любой таблице | fail closed |
| C08 | две записи с одинаковым sequence в одной таблице | fail closed |
| C09 | cross-table sequence collision | fail closed |
| C10 | валидные gaps после retention | PASS, без ложной corruption/renumber |
| C11 | source duplicate batch/replay, unique producer-event | 1 durable fact, no false conflict |
| C12 | crash before/within/after SQLite COMMIT | no accepted-but-lost event, correct rollback/replay |
| C13 | WAL contains committed changes; checkpoint occurs; unclean close | trusted snapshot/recovery or HOLD, no stale seal |
| C14 | WAL missing, truncated, corrupt or swapped | fail closed / recovery required |
| C15 | backup/restore старой generation / смена DB inode | attestation invalidated, no rollback-to-ready |
| C16 | silent mutation after snapshot audit / external writer | attestation invalidated, no unchanged assumption |
| C17 | killed/stalled deep auditor / no completed result | status unverified; no ready |
| C18 | SQLITE_BUSY, IOERR, FULL, temporary HDD stall | correct error + bounded safe control; no restart storm |
| C19 | expired/stale manifest, corrupt manifest, wrong artifact SHA | no T2 admission |
| C20 | valid source-health / Evidence end-to-end + retention / restart | real auth/identity data semantics unchanged |

### E6.2 Performance and implementation stages

**P0/L0 — LAB VM/HDD measurement GO (Owner-authorized):** Tech Lead на **лабораторной VM `192.168.0.202`** проводит повторные полноценные startup/profiling прогоны и A/B/A. Можно запускать/останавливать именно лабораторную `fingerprint-evidence.service`, выполнять **полный** `PRAGMA quick_check`, оба sequence scan, JOIN, SQL tracing/`EXPLAIN`, холодные/горячие кеши, чтение всех 3,8 ГБ и выравнивать counters guest/QEMU/host HDD. Никакого требования переносить опыт на SSD ноутбука и никаких «STOP при высокой HDD busy/PSI». Фиксировать исходный полный результат проверки, source SHA, unit/runtime flags, reader/writer lock и SQLite side effects. Тяжёлые тесты намеренно допускаются по решению Owner.

**P0/L0 negative/crash/corruption fixtures:** на этой же VM, но в **отдельных копиях** БД/журналов. Не повреждать единственный исходник 3,8-GB Evidence при тестах `writable_schema`, WAL damage, `SIGKILL` во время открытой записи. Учесть, что диагностический `initialize()` может делать служебные записи, и иметь согласованную baseline/restore copy.

**P1/L1 — formal trust design:** Tech Lead на основании измерений представляет точный T1/T2 алгоритм, собственность snapshot/manifest, fail-closed, crash/WAL, индексы и глобальные guards, все C01–C20 и причинно разобранную стоимость каждого startup этапа. Если нет доказанной эквивалентности — `HOLD` на fast-ready, даже если быстрое `initialize()` технически достижимо.

**P2 — отдельный Chief Architect implementation admission:** только после P1 доказательств возможен узкий Coder TASK на **изолированном LAB worktree/DB**. Coder выполняет focused tests; Tech Lead независимо выполняет полные Windows/Linux, corruption, WAL, crash, security и **физические лабораторные HDD** performance gates. LAB Coder, commit, push, PR, merge и любое изменение действующего production не следуют из разрешения на измерения.

**Performance evidence:** (а) cold-start HTTP/Evidence readiness при **той же доказанной integrity-семантике**, (б) операции SQL/VM steps/pread/write/fsync, (в) VM, QEMU и host `/dev/sda` completed reads/writes, bytes, await/busy, (г) CPU/PSI, (д) влияние других host contributors; (е) startup incidental writes и WAL/checkpoint. A/B/A повторять на **целевой лабораторной HDD-инфраструктуре**; ноутбук с SSD не является обязательным benchmark. Не использовать `active` или первый HTTP 200 как доказательство готовности Evidence к trusted ingest.

**Rollback:** never blindly downgrade schema/restore stale DB; before any production admission later — Owner approves maintenance window, verified safe snapshot + WAL semantics, exact source/tree, one writer lock, reversal of configuration/feature, and a plan for commits made since backup. No reverting DB generation or dropping durable Evidence/Source Health. Fail or corrupt DB => explicit recovery protocol, not automatic delete/recreate.

## 7. Scope ownership, next handoff, decision

**Tech Lead next:** использовать лабораторную VM и её HDD для полноценных повторных запусков, полного аудита и измерений всех дорогих SQL-проверок; явный Owner GO на лабораторные прогоны уже получен. Не нужен ноутбук/SSD и дополнительное разрешение только из-за высокой нагрузки LAB. После L0 предъявить точный алгоритм с полноценной защитой исторических данных либо честный HOLD. **Never** turn `deep=false` into an env switch simply to make `initialize()` fast. Кодирование быстрого варианта пока отдельно не разрешено.

**SysAdmin / Tech Lead LAB:** вправе проверять и управлять **только** лабораторной `fingerprint-evidence.service` для замеров (startup, shutdown, restart), независимо от HDD busy/PSI. Сверить source/runtime identity, lock, WAL и backup до меняющих операции; отделить лабораторные изменения от prod. Новый `captiv-prod` OUT OF SCOPE.

**Owner:** уже дал явное разрешение на полноценные исследования **именно на LAB VM с HDD**, в том числе тяжёлые полные проверки и старт/стоп лабораторной Evidence. Это не Owner GO на ослабление corruption-detection или deployment нового production. Если будущая конструкция ослабит deep-before-ready, потребуется отдельное согласование риска.

**Chief Architect verdict:**

```ini
TASK=QIO-EVIDENCE-IDLE-01
DECISION=APPROVE_CONTRACT
SCOPE=FINGERPRINT_EVIDENCE_ONLY_OWNER_LAB_VM
ROOT_CAUSE=STARTUP_DEEP_SQLITE_READ_PRESSURE_CONFIRMED
FULL_DB_INTEGRITY_ON_EACH_RESTART=RETAINED_UNTIL_EQUIVALENCE_PROVEN
FAST_METADATA_GATE=LAB_RESEARCH_APPROVED_NOT_READY
OFFLINE_ATTESTATION_FAST_ADMISSION=UNPROVEN_HOLD
EVIDENCE_INGEST_BEFORE_TRUST=FORBIDDEN
CROSS_TABLE_INGEST_SEQUENCE_GUARD=RETAIN_OR_PROVE_EQUIVALENT
LAB_VM_HDD_FULL_AUDIT_AND_RESTART_MEASUREMENTS=GO
LAB_HEAVY_IO_AND_FULL_SCAN=OWNER_AUTHORIZED
LAB_QUIET_PSI_BUSY_GATE=NOT_REQUIRED
LAB_NOTEBOOK_SSD_BENCHMARK=NOT_REQUIRED
LAB_CORRUPTION_INJECTION=DISPOSABLE_DB_ONLY
LAB_IMPLEMENTATION=HOLD_PENDING_TRUST_PROOF
CODER=HOLD
PRODUCTION_CHANGES=NO
NEW_CAPTIV_PROD=DO_NOT_TOUCH
NETWORK_METADATA=OUT_OF_SCOPE
OWNER_LAB_GO=GIVEN
OWNER_PRODUCTION_GO=NO
PHYSICAL_READ_CAUSE=EVIDENCE_STARTUP_A_B_A_SUPPORTED
PHYSICAL_WRITE_SAVINGS=NOT_CLAIMED
```

**Non-negotiable:** этот контракт **разрешает** полноформатные эксперименты, полный SQLite deep scan и контролируемые старты/остановки **лабораторной** Evidence-службы на VM/HDD. Он **не разрешает** объявлять необоснованный быстрый startup безопасным, ослаблять trust/guards при приёме ingest, выдавать неполный audit за PASS или затрагивать новый production.

## References

- Локальный forensic Tech Lead: `QIO-EVIDENCE-IDLE-01-TECHLEAD-FORENSIC-2026-10-17`.
- Источник репозитория: `ZaurNavi/CaptivePortal@810484e69baa371c4696c3b46654199631538fc4`.
- SQLite PRAGMA `quick_check`/`integrity_check`: https://www.sqlite.org/pragma.html#pragma_quick_check и https://www.sqlite.org/pragma.html#pragma_integrity_check .
- SQLite WAL: https://www.sqlite.org/wal.html .
- SQLite Online Backup API: https://www.sqlite.org/backup.html .
