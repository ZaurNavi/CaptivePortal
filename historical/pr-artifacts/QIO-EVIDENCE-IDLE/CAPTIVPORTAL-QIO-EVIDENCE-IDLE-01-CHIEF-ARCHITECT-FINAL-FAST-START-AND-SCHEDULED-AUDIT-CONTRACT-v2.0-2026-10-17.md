# CAPTIVPORTAL — QIO-EVIDENCE-IDLE-01
## Chief Architect → Tech Lead: FINAL Architecture Contract v2.0 — Fast Startup + Scheduled Integrity Audit + Future DB & Services UI

**Дата:** 2026-10-17 (Asia/Baku, UTC+04:00)  
**Owner decision:** оставить **одну существующую SQLite Evidence DB**; на обычном запуске не читать всю историческую базу. Отдельный глубокий аудит исполняется **по расписанию в 03:00 Asia/Baku** на лабораторном узле до появления UI. В будущем — ручной запуск, настройки расписания и результаты в Admin UI **DB & Services**.  
**Адресат:** Performance & Optimization Tech Lead для подготовки **одного однозначного implementation TASK** кодеру.  
**Scope:** `fingerprint-evidence.service`, `app/device_fingerprint` и только лабораторная VM `192.168.0.202`, её реальное HDD/QEMU окружение. **Новый действующий `captiv-prod` — NO TOUCH.** Network Metadata, Sensor Spool, NI-02A, другие SQLite — не изменять этим заданием.  
**Статус:** `ARCHITECTURE=PASS_WITH_EXPLICIT_INTEGRITY_TRADEOFF; TECHLEAD_TASK_PREPARATION=GO; CODER=HOLD_UNTIL_TECHLEAD_TASK; LAB_RUNTIME_CHANGE=CONDITIONAL; PROD_CHANGE=NO`.

> **Normative override.** Этот документ **заменяет** выбранный в QIO-EVIDENCE-IDLE-01 v1.3 обязательный Hot/Archive переход для решения проблемы старта. Архивирование и разделение SQLite **не являются prerequisite**. Прежние v1.1/v1.2 измерения и N08/N11 сохраняются как evidence, но направление реализации определяется настоящим документом. Контракт `DB-SERVICES-01 v1` остаётся действующим в своём **read-only** объёме; управление аудитом — отдельное, будущим изменением архитектуры прав/операций.

---

## 0. Единственное решение, которое реализуем

**Одна SQLite DB, три независимых контура:**

1. **Fast startup gate:** открыть обычную Evidence SQLite с действующим WAL/recovery, проверить ограниченный набор метаданных, схемы и storage state; **не сканировать таблицы и индексы целиком**. В случае PASS Evidence API принимает новые durable события **без ожидания исторического полного аудита**.
2. **Online runtime safety:** сохранить SQLite ограничения, последовательное выделение глобального `ingest_sequence` в одной текущей транзакции, точную дедупликацию и поведение fail-closed при реально наблюдаемых ошибках БД; никаких пропусков commit, no-op/retention/PRAGMA изменений.
3. **Deep audit:** отдельный, независимо запускаемый процесс/команда, не блокирующие старт, со штатным согласованным снимком SQLite и полным `PRAGMA integrity_check` **плюс** доменными проверками; результаты с provenance, временем и идентичностью именно проверенного снимка. **Автоматический триггер — ежедневно в 03:00 Asia/Baku после отдельного допуска установки лабораторного расписания**; ручной CLI запуск — с самого первого лабораторного этапа. В дальнейшем UI становится клиентом этого самостоятельного механизма.

**Обязательный осознанный компромисс:** при таком запуске **не обеспечивается предварительное выявление всякого латентного повреждения исторических страниц**. `fast-gate PASS` означает **готовность операций по имеющимся проверенным локальным признакам**, а не `entire_database_integrity_verified`. Это не эквивалентность прежней полной проверке. Допуск такой модели утверждён как *направление* Owner; перед изменением настоящего production Owner отдельно утверждает точную остаточную степень риска. Никому не разрешено называть быстрый запуск «полной проверкой». Если полнота исторической проверки **обязательна до каждого API ACK**, fast-start невозможен без новой границы хранения — это другой проект.

## 1. Закреплённые доказательства и масштаб

| Зафиксированный факт L0/P2 | Результат | Значение для реализации |
|---|---:|---|
| БД `device_fingerprint_evidence.sqlite3` | 3,796,074,496 bytes; 926,776 pages | Читать всю DB при каждом restart нельзя считать bounded startup |
| `last_ingest_sequence` | 2,834,788 | Сохранить глобальный durable allocator |
| Быстрая `_validate_runtime_connection` | 0.002–0.003 s в диагностике | **Не** сертификат всей БД; пригодный референс только metadata path |
| Исторический Evidence sequence guard | 148.402 s | Убрать **из startup**, сохранить в deep audit |
| Исторический Source Health guard | 0.106 s | Убрать **из startup**, сохранить в deep audit |
| Cross-family collision guard | 1.252 s | Убрать **из startup**, сохранить в deep audit |
| Полный `PRAGMA quick_check` | **PASS**, 3352.86 s = 55:52.86 | Даже успешная проверка заняла почти час; **не** повторять на каждом старте |
| N08 | `quick_check=ok`, `integrity_check` увидел некорректный UNIQUE индекс | Нельзя называть `quick_check` защитой от всех index/table нарушений |
| N11 | Видимость повреждения `quick_check` зависит от SQLite version; индекс мог скрыть невалидную строку | Не заменять глубокие проверки на `MIN/MAX`/простой индексный scan |
| Physical host HDD during full checks | 75–86 read IOPS, ~93% busy (конкурирующая нагрузка) | Измерять реальное время старта на лабораторном HDD; не присваивать все host reads одному PID |

Полный L0 `quick_check` **завершён успешно** 2026-10-17 16:52:36 +04:00 — старый статус PENDING из промежуточных отчётов **устарел**. Это подтверждает только соответствующий проверенный snapshot и не доказывает «абсолютно целостна» при всех категориях дефектов.

## 2. Fast startup — точное поведение

### 2.1. Mandatory gate (bounded by design, not by false numeric SLA)

- Сохранить существующие `_prepare_local_file_target`, exclusive writer lock, разрешённый путь, проверку файлового типа/прав, SQLite version, `PRAGMA user_version`, exact schema signature таблиц/индексов/обязательных CHECK declarations, проверку единственного storage singleton, каноничности `database_generation_id` и integer/range `last_ingest_sequence`, действующие `enforce_storage_cap` и SQLite `WAL` recovery.
- Проверка `_validate_runtime_connection` — **отправная точка**. Tech Lead должен явно сопоставить перечень проверок с legacy `_validate_connection` и подтвердить, что быстрый gate **не читает пользовательские ряды**, не делает global index scan, `PRAGMA quick_check/integrity_check`, `COUNT(*)`, table JOIN, global `MIN/MAX` over history или full `EXPLAIN` с реальным выполнением.
- Реальная проверка плана/стоимости: на базе порядка 3.8 GB (LAB), с чистым/тёплым page cache, startup не должен масштабироваться линейно с числами evidence rows; ожидания блокировок SQLite, hard I/O errors и огромный WAL являются отдельными реальными причинами задержки и **не маскируются**.
- Зависимость `DeviceFingerprintRuntime.initialize()`/`app/device_fingerprint/cli.py:run` изменить **минимально**: metadata-only gate становится штатной проверкой готовности; отдельная `deep_validate` команда/процесс не импортируется/не запускается при startup. Нельзя временно monkeypatch `_validate_connection` или глобально удалять реализацию deep validation.
- Если быстрый gate не прошёл: `READY=false`, нет ingest ACK, никакого автоматического пересоздания/миграции/исправления DB, нет restart storm. Существующая error taxonomy `StorageCorrupt/Unavailable/Limit` сохраняется, новая причина маркируется точно.
- При успехе: `READY=true` для приёма **новых событий при стандартных runtime гарантиях**; независимый audit статус может оставаться `never_run`, `running`, `passed`, `failed`, `incomplete`, `stale` и не должен сам по себе притворяться критерием startup-ready.

### 2.2. Неприкосновенные инварианты data plane

- Одно прежнее SQLite-хранилище и прежняя схема v2. Никаких shard, sealed generation, дополнительных writer authority или переноса архива.
- В `DeviceFingerprintRepository._ingest()` сохранить `BEGIN IMMEDIATE`, durable allocation `ingest_sequence`, двустороннюю таблицезависимую дедупликацию, immutable conflict, commit/rollback и исходный контракт HTTP acceptance. `last_ingest_sequence` продвигается **только** после записанных в транзакции новых событий; crash/replay не создаёт ложный checkpoint. Сохранить Source Health и consumer read watermark semantics (`database_generation_id`, `max_committed_ingest_sequence`).
- Существующие `journal_mode=WAL`, `synchronous=NORMAL`, автоконтроль checkpoint, retention, writer lock, schema, cap, TLS, access policy **не менять**. Не ослаблять durability ради быстрого запуска.
- SQLite `SQLITE_CORRUPT/NOTADB` и доказанные store/allocator/schema нарушения во время normal operations должны приводить к `storage_corrupt` и блокировке последующих Evidence writes до explicit recovery. I/O/busy/full — по действующей временной/limit taxonomy, без ложного сообщения «всё целостно».
- При обнаружении подозрительного глобального повреждения аудитором не удалять и не чинить БД автоматически; см. раздел 5.

## 3. Deep audit — независимый от запуска проверочный механизм

### 3.1. Исполняемый профиль

- Новый **узкий Evidence-only CLI/audit runner**; запросить явное имя в implementation TASK, например `python3 -m app.device_fingerprint.audit_cli run --store-id fingerprint_evidence`. Это **предлагаемый интерфейс**, не команда существующего продукта и не разрешение запускать её сейчас.
- Стандартный scope по умолчанию — **одна** зарегистрированная Evidence DB, реальный путь предоставляется через существующую доверенную конфигурацию (никакого HTTP/query parameter → произвольный file path). Права ОС — минимальные; на первом LAB этапе отдельный безопасный запуск от оператора.
- Защита от второго параллельного запуска: один singleton/lock в audit worker, ошибки `already_running`/`busy`, журнал запуска, timeout/termination cleanup. Никаких конкурентных полных аудиторов, бесконтрольных повторов и restart storm.
- **Предпочтительный профиль:** согласованный SQLite snapshot с Online Backup API во временное специально выделенное и достаточное по ёмкости пространство; проверить **копию**, затем публиковать результат. Копирование не означает простого `cp main.sqlite3` при активном WAL. Снимок обязан быть завершён штатным `backup`/завершённым копированием, иметь provenance `source_path_identity`, `database_generation_id`, source `last_ingest_sequence` **в одном логически согласованном состоянии**, `snapshot_created_at_utc`, SQLite version, audit code SHA/method version; доказать внутреннюю самосогласованность snapshot метаданных. Snapshot не служит текущим DB trust forever.
- Для большого файла предварительно проверить свободное место с запасом и write permission; не затрагивать основной DB, не очищать WAL, не удалять посторонние файлы. Online backup может долго читать/писать HDD; при бесконечных busy/lock, невозможности создать snapshot, превышении заданного LAB max duration или space budget → `incomplete`, не `pass`.
- **Прямой аудит live SQLite** допустим только как отдельно проверенный режим при недостатке пространства/специальной LAB диагностике: SQLite read transaction может удерживать WAL reader snapshot и препятствовать checkpoint/reset во время часового обхода. Не считать `mode=ro` = «нулевая побочная нагрузка». Для production acceptance предпочтителен snapshot режим.
- После успешного завершения копии, проверить её в `mode=ro`, `query_only=ON`, с полным `PRAGMA integrity_check` (не `quick_check(1)`, не частичным table-only check), `PRAGMA foreign_key_check`, если FK применимы, плюс **точные доменные full checks**: schema/signature, storage singleton, canonical generation/allocator, per-table ingest sequence type/range/allocator, межтабличные collisions, identity uniqueness and immutable conflict where contracts require, допустимый глобальный watermark и retention semantics. Для недоказуемых деклараций не выводить `pass`.
- `integrity_check` имеет предел возвращаемых ошибок; **PASS только если корректно завершён и результат ровно `ok`**; любое нарушение, SQL exception, timeout, отмена, неполный результат — не `pass`. Доменные проверки обязаны уметь обнаружить N08/N11 классы; иное = test failure.
- Дозировать запись diagnostic telemetry и audit report: одно summary/run + bounded milestones; **не писать событие/строку лога на каждую страницу** и не порождать отдельный мелкий I/O. Не хранить персональные/packet payloads в отчёте.
- Cleanup: удалять только известный временный snapshot этого конкретного запуска после закрытия SQLite handles и сохранения результата, с symlink/path ownership checks и manifest run identity. При аварийном завершении — operator-review cleanup; нельзя сканировать/удалять произвольные `.sqlite3`.

### 3.2. Источник фактов, статусы и TTL

Каждый audit report — **отдельный операторский артефакт**, никак не подделывающий статус live store:

| Статус аудита | Значение |
|---|---|
| `never_run` | Периодический аудит ещё не завершался или достоверный отчёт отсутствует |
| `queued` | Запрос принят управляющим механизмом, исполнение ещё не начато |
| `running` | Аудитор активен, snapshot/scan ещё не завершены |
| `passed` | Полный audit **определённого snapshot** завершился без обнаруженных ошибок |
| `failed` | Доказано нарушение целостности/доменного инварианта на проверенном snapshot |
| `incomplete` | Timeout, отмена, power loss, disk full, snapshot failure, worker crash или неизвестный результат |
| `stale` | Последний полный PASS слишком стар для выбранной политики, новый доказанный PASS отсутствует |

Публикуемый bounded contract `db_audit_status.v1`:
`store_id, run_id, trigger(manual|schedule), status, stage(snapshot|integrity|domain|complete), created_at_utc, started_at_utc, finished_at_utc, snapshot_at_utc, database_generation_id, snapshot_last_ingest_sequence, sqlite_version, audit_contract_version, source_commit, duration_seconds, category_code, check_summary, schedule_policy_id, report_written_at_utc`.

- Отчёт создаётся **атомарной заменой** защищённого ограниченного JSON-файла под заранее заданным trusted path (например, `.../audit-status/fingerprint_evidence.json`) — это **операционные метаданные аудитора**, не новые данные посетителей; точный путь/owner/mode/retention остаются Tech Lead+SysAdmin deployment binding. Допустима альтернативная схема из уже существующего безопасного audit store, но **не новая SQLite только ради статуса**, если необходимость не доказана.
- Начало запуска, completion, timeout, interruption, crash-recovery метки устойчивы и различимы: «последний PASS» хранится отдельно от «последней попытки». Незавершённый `running` после рестарта аудитора превращается в `incomplete`, а не сохраняет «вечный running»/«success».
- `passed` означает `snapshot passed` и, если live DB уже изменилась, в UI отображается **«проверен снимок на дату»**, а не «БД гарантированно здорова сейчас». В UI `DB operational_state` из `DB-SERVICES-01 v1` **не становится `available` автоматически** только по старому `passed`.
- Полезные счётчики для monitoring: `last_attempt`, `last_success`, `last_failure`, `duration`, `time_since_pass`, `next_scheduled_run`, `run_pending`, `overlap_skipped`, `snapshot_bytes`, `failure_category`, space needed/available summary; никакой абсолютный path или SQL исключение в браузер.

## 4. Расписание: сейчас 03:00, затем настраиваемое через UI

### 4.1. Временный LAB profile, до появления UI

**Owner selected:** `daily at 03:00 Asia/Baku` (UTC+04:00; локальный день по часовому поясу Баку). Это не «03:00 UTC» и не «ночью после каждого рестарта».

- Первый LAB implementation сначала реализует надёжный CLI + отчёт + tests. **После Tech Lead LAB PASS и отдельного разрешения оператора на расписание** установить для старой лабораторной VM `systemd` **oneshot service + timer**, вызывающие аудит по фиксированному allowlisted пути/аргументам и отдельному техническому identity; не трогать systemd unit Evidence/API, запуск/остановка которого остаются независимыми.
- Желаемая семантика таймера: `OnCalendar=*-*-* 03:00:00` с **`Timezone=Asia/Baku`** через системный TZ или поддерживаемую версией systemd calendar timezone форму (Tech Lead/SysAdmin должен подтвердить на целевой системе `systemd-analyze calendar` и фактический local schedule); `Persistent=false`, чтобы отключённая ночью VM **не запускала многочасовой аудит немедленно после включения утром**; единичный `flock`/lock, no overlap, no queue accumulation.
- `systemd` auto-restart на неуспешном аудите **не включать**. Audit failure логируется/сохраняется и ждёт следующего планового окна или ручного запуска; никаких повторов в tight loop. При выключении VM/suspend недовыполненный запуск записать как `incomplete` после следующей проверки состояния.
- Никаких искусственных «PSI должен быть ниже N» запретов **в лаборатории**: Owner разрешил нагружать её HDD. Вместе с тем реальный disk full/зависший writer/нехватка места/WAL рост, повреждение файлов, некорректный путь — настоящие stop conditions.
- Временный timer может читаться будущей панелью как `source=schedule_attested`, но **не должен автоматически становиться writable через Web Admin**: пока права/управляющий API не реализованы, UI только показывает параметры, подтверждённые operator-managed schedule manifest.
- **В этом чате и этим архитектурным документом timer НЕ УСТАНОВЛЕН и НЕ ЗАПУЩЕН.** Это разрешение Tech Lead подготовить соответствующий отдельный шаг после LAB acceptance, не инструктаж на немедленный невалидированный prod deploy.

### 4.2. Будущая UI-панель DB & Services (совместимость, но НЕ часть первого TASK)

В `DB-SERVICES-01 v1` **прямо запрещены** SQL probes, новые daemons, операции записи/настроек и управление сервисами. Поэтому не изменять и не обходить текущий read-only контракт исподтишка. Предусмотреть отдельное аддитивное `DB-AUDIT-CONTROL-01` со следующими требованиями:

- **Статус/просмотр:** авторизованному Admin с глобальным `admin.read.operations` может быть виден **только ранее записанный и источник-подтверждённый** `db_audit_status.v1` (после явной доработки contracts/sampler). Страница **никогда не выполняет аудит при GET** и не открывает SQLite. Текущий `DB-SERVICES-01 v1` не расширяется автоматически одним этим документом.
- **Кнопка «Запустить аудит»:** будущий явный POST с отдельным non-default global permission уровня `admin.execute.db_audit` и CSRF/session/rate limit; POST ставит **один** разрешённый `store_id` в очередь единственного аудиторского исполнителя. Ответ `accepted/queued`, **не** «audit passed»; не передавать произвольные SQL/path/shell arguments.
- **Настраиваемое расписание:** отдельное право `admin.configure.db_audit` (не `admin.read.operations`/обычный site read). Политика `manual|daily|weekly|monthly`, timezone, local HH:MM, weekday/day-of-month, DST/missed-run policy, enabled, generation/version, operator identity and audit trail. При дне, отсутствующем в конкретном месяце, выбрать явную семантику `skip` (не запускать без согласованного fallback). Default policy — `daily 03:00 Asia/Baku` после временного периода; нельзя считать поведение systemd timer и UI scheduler идентичным без независимой совместимости и cutover.
- **Единственный scheduler owner после перехода:** исключить двойной запуск (и старый systemd timer, и новый управляемый scheduler). Ввести idempotent owner handoff с подтверждением отключения временного timer и одинаковым lock/run_id протоколом до включения UI scheduling. Web frontend не получает прямых shell/systemctl/sudo полномочий; privileged executor отдельно проектируется и ограничивается allowlist.
- В UI показывать: `last audited snapshot`/`started`/`duration`/`next run`/`current stage`/`failure category`/`report freshness`, кнопку и расписание после согласованного расширения. `health=unknown/present_unverified` не делается зелёным из-за размера файла или старого PASS.
- UI control-plane, persistent schedule policy, API paths, grant parser, operator identity, csrf и deployment mechanism требуют **отдельного архитектурного + security review и собственного implementation TASK**, когда дизайнерская панель действительно будет готова. Сейчас замораживаем **контракт результата и смысл**, не строим преждевременно вторую систему управления.

## 5. Результаты аудита и реакция на проблемы

- **Audit `passed`:** записать timestamp/snapshot identity, не рестартовать service, не перезапускать deep audit, не считать будущие WAL writes уже проверенными.
- **Audit `incomplete` / `never_run` / `stale`:** показать оператору нейтральный статус и причину. **Не** останавливать Evidence только потому, что вчера ночью не хватило места/времени для отдельного теста. Не объявлять полный integrity PASS. Следующая попытка в расписании или вручную.
- **Audit `failed` (подтверждённое повреждение snapshot):** немедленно сформировать operator alert / `integrity_suspect`, запретить ложный green; сопоставить `database_generation_id`, snapshot watermark и фактический live store. Если подтверждена применимость обнаруженной критичной порчи к действующему Evidence store — перевести **именно Evidence** в `storage_corrupt/unavailable`, прекратить новые ingest ACK/записи и вызвать контролируемый recovery flow. Нельзя без доказательства принадлежности снимка и состояния live DB «чинить»/останавливать другие сервисы. Реакция на failure требует выделенного, проверенного signalling между audit worker и Evidence runtime, **не** неявного импорта audit status в маршрут API. Для первого lab TASK допускается безопасный `alert + manual isolation` как проверяемая предступень, а автоматический fail-closed hook требует **отдельного approval**.
- Скрытые повреждения (например N08/N11) могут быть обнаружены только при позднем аудите; это неизбежный и принятый проектный риск fast-start. Никто не выдаёт старый `quick_check PASS` за полный `integrity_check PASS`.

## 6. Tech Lead → Coder: точная граница первого implementation TASK

**ID:** `QIO-EVIDENCE-IDLE-01-P2-LAB-02-FAST-START-AND-INDEPENDENT-AUDITOR`.

**Tech Lead GO для подготовки TASK; Coder HOLD до TASK.** ТЗ должно содержать pinned HEAD/TREE для целевого laboratory checkout (прошлый измеренный `810484e...`, а текущий `main` и lab checkout могли сдвинуться), path allowlist, единственного writer authority и отсутствие production deploy.

### 6.1. Deliverables в LAB

**D1 — fast-start:** выделить предсказуемый, bounded validator из `app/device_fingerprint/repository.py`; `initialize()` использует только этот путь при обычном запуске, **deep validation доступна отдельно** и не удалена из кода. `app/device_fingerprint/cli.py` и `app/device_fingerprint/service.py` меняются только если это строго необходимо для композиции и READY truthfulness. Никакого второго Evidence writer.

**D2 — independent audit:** отдельный Evidence-only CLI module и testable audit service, делающий согласованный online SQLite backup и full `integrity_check + domain validation`; результаты только в ограниченный operator status/report. Сначала manual CLI, без UI, без automatic timer в Coder TASK #1, если Tech Lead отдельно не расширит scope после сосредоточенного review.

**D3 — minimal status:** машинно читаемый `db_audit_status.v1` с `last_attempt + last_verified_success` и несмешением snapshot vs live. Исполнитель создаёт отчёт; Admin read-only sampler **не изменяется** в этой задаче.

**D4 — measurements:** сравнение старого и нового startup на одной и той же лабораторной VM/HDD, cold/warm, `elapsed`, `READY time`, source DB bytes, guest `/dev/vda` и host `/dev/sda` diskstats/cgroup (при честной доступности), число SQL statements/full scans, API acceptance, WAL files, pre/post sequence state. Корректно отделять host background writes; не выдавать busy % за exclusive attribution. Отдельно измерить online backup + offline full audit; тяжёлая audit часть **не должна** запускаться при обычном restart.

**D5 — audit schedule integration blueprint:** одна текстовая конфигурация/документация operator timer 03:00 (LAB-only), `Persistent=false`, single lock, failure status; **не** устанавливать и не активировать timers/units в первом Coder TASK без отдельного Owner/SysAdmin разрешения на LAB.

### 6.2. Allowlist/forbidden changes

Tech Lead замораживает exact allowlist перед Coder GO; предлагаемый минимум: `app/device_fingerprint/repository.py`, новый `app/device_fingerprint/audit_cli.py`, новый `app/device_fingerprint/audit_runner.py`, при необходимости минимально `app/device_fingerprint/cli.py`/`service.py`, узкие `tests/device_fingerprint/` и `docs/` для контракта. Не изменять read service, ingest schema и migration/recovery без отдельного архитектурного запроса; не использовать monkeypatch в shipped runtime.

**Запрещено:** `captiv-prod` mutation, live original DB corruption injection, `VACUUM/REINDEX/DELETE` как ремонт, сокращение SQLite durability, WAL checkpoint promotion, live schema migration, global source health/capture/Network Metadata, Admin Web write endpoints, ввод дополнительного daemon как скрытой предпосылки старта, сохранение `integrity_pass=true` после любых новых записей, Git push/PR/merge/deploy без отдельного разрешения Owner.

## 7. Acceptance gates Tech Lead (независимые)

| Gate | Критерий |
|---|---|
| **FS-00** Source parity | Exact repo HEAD/TREE + lab deployment + Python/SQLite version known; golden original DB safeguarded; no production touch |
| **FS-01** Startup isolation | API ordinary startup path performs **0** full `quick_check/integrity_check`, **0** historical sequence table scan/JOIN; deep audit never auto invoked by startup |
| **FS-02** Fast metadata | Schema signature, state/generation/range, missing/malformed/wrong-version files all fail closed before ingest; no new DB created on broken existing path |
| **FS-03** Data correctness | New evidence, duplicate, immutable conflict, Source Health, global ingest_sequence, commit/crash/replay, single writer, retention, read watermark snapshot exact parity |
| **FS-04** Corruption boundary | N08/N11 historical corruption **not advertised** as caught by fast gate; online operation detects errors it actually encounters; deep audit catches fixtures. Honest status separation |
| **FS-05** Audit accuracy | Snapshot backup valid under concurrent WAL writes; `integrity_check` full exact `ok`, required domain checks, snapshot provenance; incomplete/snapshot partial never PASS |
| **FS-06** Fault handling | Kill before/during/after backup, audit SQL fault, DB corrupt, disk full, write denied, missing temp space, stale running marker, busy, concurrent trigger all have bounded/safe outcomes |
| **FS-07** Scheduling | No audit before READY due to startup; no overlap; 03:00 Asia/Baku calendar verified in LAB; `Persistent=false`; missed audit not immediate morning restart; timer not activated before authorization |
| **FS-08** Observability | `last_attempt`, `last_success`, status, snapshot reference and age consistent; no secrets, payload, raw DB paths in Admin-facing projection |
| **FS-09** Physical disk | Matched original vs candidate on **LAB VM/HDD**; guest/host correctly labelled; cold/warm effects and background VM load noted; no physical savings fabricated |
| **FS-10** Isolation | `captiv-prod`, Network Metadata, QIO-05, Sensor Spool, Admin Web v1, other DBs untouched; no change to SQLite PRAGMA durability |
| **FS-11** Independent regression | Coder runs focused tests; **Tech Lead** owns full clean Linux + Windows (where applicable), security, crash/replay and HDD/latency regression; no rubberstamp from Coder tests |
| **FS-12** Owner deployment | LAB activation only after Tech Lead PASS and operator GO; Git PR/merge/new production rollout require later separate Owner GO; emergency rollback = feature path flag/rollback of code with maintained durable DB, no data loss |

**Mandatory negative demonstration:** fast gate intentionally does **not** catch arbitrary latent corruption; deep audit catches injected N08/N11 and independent index inconsistency. Tests must not be written to imply equivalent corruption detection.

## 8. Risk register / OWNER explicit trade-off for future deployment

- **R1 — Historical corruption not pre-detected.** Real, unavoidable under fast startup; audited later. Mitigate strict live SQLite errors, periodic full audit, reliable backup and operator alerts. Explicit Owner GO at production deployment; not hidden as “optimization with no semantic changes”.
- **R2 — Nightly expensive audit (~4 GB).** It may use much more than one hour on HDD, plus creating snapshot; **does not block normal Evidence startup**; can contend with active writes. LAB Owner authorized heavy work; prod schedule separately reviewed for backup space/HDD impact.
- **R3 — Long WAL readers / checkpoint starvation.** Prefer backup→verify rather than hour-long live transaction. Monitor WAL and source writer, prevent capacity exhaustion.
- **R4 — Incorrect status carry-forward.** Last good snapshot != live DB healthy; status provenance/time mandatory.
- **R5 — Damage to base from failure injection.** Only disposable SQLite copies get corruption injection; golden LAB original protected.
- **R6 — Duplicate schedulers on UI handoff.** One active owner/lock at cutover; privileges and grants separate.
- **R7 — Compatibility with `DB-SERVICES-01 v1`.** Existing read-only page has no DB opens, scheduler, new daemon or mutating endpoints. UI-control changes need new formal contract and security review; don't silently expand v1.

## 9. Immediate handoff / decision statement

**Tech Lead:** prepare a single Coder TASK for `FS-00..FS-12` with smallest exact file allowlist and clear split `FAST_START` vs `AUDIT_CLI`; LAB testing permitted on `192.168.0.202`. If Coder task cannot meet snapshot safety, start D1 alone with audit runner D2 as separate lab iteration, **never** fall back to full historical scan on normal startup silently. Next architectural review only for material safety deviations, not routine recirculation of the same L0 reports.

**Owner / future SysAdmin:** after Tech Lead LAB PASS separately approve the LAB 03:00 daily timer; current document does not invoke or install any systemd configuration. Later approve UI control-plane integration and any true production rollout individually.

```ini
TASK=QIO-EVIDENCE-IDLE-01
CONTRACT=CHIEF_ARCHITECT_V2_0_FINAL
DIRECTION=SINGLE_SQLITE_FAST_START_PLUS_INDEPENDENT_DEEP_AUDIT
ARCHITECTURE=PASS_WITH_EXPLICIT_INTEGRITY_TRADEOFF
HOT_ARCHIVE_PREREQUISITE=REMOVED
NORMAL_STARTUP_FULL_QUICK_CHECK=NO
NORMAL_STARTUP_FULL_SEQUENCE_SCANS=NO
NORMAL_STARTUP_DEEP_AUDIT=NO
EVIDENCE_SOURCE_DB=UNCHANGED
AUDIT=FULL_INTEGRITY_AND_DOMAIN_CHECK_ON_CONSISTENT_SNAPSHOT
AUDIT_LAB_SCHEDULE_PROPOSED=DAILY_03_00_ASIA_BAKU
AUDIT_SCHEDULE_ACTIVATION=AFTER_LAB_TECHLEAD_PASS_AND_OWNER_GO
FUTURE_UI=DB_AND_SERVICES_ADDENDUM_REQUIRED
CODER_TASK_PREPARATION=GO
CODER=HOLD_UNTIL_EXACT_TECHLEAD_TASK
LAB_VM=192.168.0.202
PRODUCTION=NO_CHANGES
GIT_PUBLICATION=NO
```

### Normative source documents

1. `QIO-EVIDENCE-IDLE-01-TECHLEAD-FORENSIC-2026-10-17(1).md`
2. `QIO-EVIDENCE-IDLE-01-L0-ARCHITECT-MEASUREMENT-HANDOFF-2026-10-17(2).md`
3. `QIO-EVIDENCE-IDLE-01-P2-LAB-01-INDEPENDENT-TECHLEAD-REVIEW-2026-10-17(1).md`
4. `CAPTIVPORTAL-DB-SERVICES-01-CHIEF-ARCHITECT-ARCHITECTURE-CONTRACT-v1-2026-10-17(2).md` — v1 remains read-only.
5. Official SQLite reference: https://www.sqlite.org/pragma.html (`integrity_check` / `quick_check`), https://www.sqlite.org/backup.html (online consistent backup), https://www.sqlite.org/wal.html (long reader/checkpoint interaction).
