# TASK-FP-IO-W2-IMPLEMENT-01 — Device Fingerprint Write-I/O Optimization

**CaptivPortal / TechLead23 / 2026-10-12**  
**Режим:** единое окончательное implementation TASK, source-only, три независимых default-OFF флага; реализация исходников РАЗРЕШЕНА TechLead23 по решению Owner.  
**Архитектурный источник:** `ARCH-DEVICE-FINGERPRINT-IO-WAVE2-WRITE-PATH-CONTRACT-v1` (2026-10-12), с обязательным сохранением `TASK-DEVICE-FINGERPRINT-02-FINAL` и Task-01 evidence semantics.  
**Pinned base:** `main@385fecebd2bd8778c3a2034514d9e72587984753`  
**Pinned tree:** `baefd2c4fbceff51aade93d840d93fc81a88fd58`.

## 0. Статус допуска и полномочия

Это **полная спецификация реализации исходного кода** и **разрешение Coder начать все три пункта одним заданием**. Это НЕ разрешение на изменение production или включение функций.

**Решение Owner в беседе 2026-10-12 (принята рекомендация TechLead23):**

- `F1 / telemetry` — **APPROVED FOR IMPLEMENTATION**; административное исключение не требуется.
- `F1 / stale purge` — `EX-FP-W2-01` **OWNER APPROVED**: допускается доказательно пропускать заведомо пустые stale-DELETE, сохраняя 24-часовую границу и консервативный fallback. **Coder реализует этот пункт сейчас; прежний HOLD снят.** Production-включение — лишь после проверки TechLead23 и отдельного разрешения на rollout.
- `F2 / ingress coalescing` — **APPROVED FOR SOURCE IMPLEMENTATION ONLY, DEFAULT OFF**. `EX-FP-W2-02` **NOT APPROVED FOR PRODUCTION ACTIVATION**. Даже если код будет готов, не активировать на production, пока Owner отдельно не согласится принять возможную потерю максимум 32 ещё не записанных событий/256 KiB за 100-мс окно при аварии (с оговоркой о планировщике). Это НЕ отменяет гарантии для уже зафиксированных записей SQLite.
- `F3 / fingerprint-evidence` — **NO SOURCE MUTATION**. Только отдельная read-only оценка Tech Lead/SysAdmin, НЕ Coder в этом задании.

**Code implementation = GO. Test/QA/Git/deploy = вне полномочий Coder до новой директивы TechLead23.**

**Coder пишет исключительно исходники.** Coder НЕ проводит QA, benchmark, тесты, IOPS-измерения, проверки физического диска, подготовку load-run, настройку системных служб, commit/push/PR/merge/deploy. Всё это отдельно выполняет TechLead23 либо по его распоряжению. Coder передаёт незакоммиченные изменения и краткий handoff с перечнем затронутых файлов, реализацией и ограничениями. Никаких дополнительных архитектурных решений от Coder.

## 1. Область изменений

Разрешённые текущие файлы:

- `app/device_fingerprint_sensor/models.py` — три поля `bool=False` в `SensorConfig`, без перестановки существующих полей, ломания старых конструкторов и новых DB-моделей.
- `app/device_fingerprint_sensor/config.py` — строгий разбор трёх новых независимых флагов, иных knobs нет.
- `app/device_fingerprint_sensor/spool.py` — proof-gated stale purge (`EX-FP-W2-01` согласовано Owner), без смены SQLite semantics.
- `app/device_fingerprint_sensor/runtime.py` — подключение агрегирования телеметрии и bounded ingress coalescing, без изменения source classification или transport ACK.
- `app/device_fingerprint_sensor/telemetry.py` — safe aggregation field allowlist, legacy emission untouched when feature OFF.
- **Один** новый файл `app/device_fingerprint_sensor/ingress_coalescer.py` допустим, если нужен для изолированной реализации F2. **Дополнительные новые модули без необходимости не создавать.** Допускаются небольшие приватные helper-объекты внутри перечисленных модулей; не плодить абстракции.

`producer.py`, `health.py`, `normalizer.py`, Task-01 evidence repository/service, `run.py`, Admin Settings, Omada, Suricata, Network Metadata, CAPPORT/Auth, systemd, схемы и миграции — **не изменять**. Если точное выполнение потребует этого, остановить соответствующий пункт и вернуть TechLead с конкретной причиной, не расширять scope по собственному решению.

## 2. Конфигурация — без выбора альтернатив

В `SensorConfig` добавить в конец (для совместимости positional constructors):

```python
io_stale_purge_gate_enabled: bool = False
io_telemetry_aggregation_enabled: bool = False
io_ingress_coalesce_enabled: bool = False
```

Публичные env-имена **строго**:

```text
DEVICE_FINGERPRINT_SENSOR_IO_STALE_PURGE_GATE_ENABLED=false
DEVICE_FINGERPRINT_SENSOR_IO_TELEMETRY_AGGREGATION_ENABLED=false
DEVICE_FINGERPRINT_SENSOR_IO_INGRESS_COALESCE_ENABLED=false
```

Значения: только `true|false` без учёта регистра, как в существующем `_boolean`; отсутствие = `false`; пустая строка, `0|1|yes|no|on|off`, любое другое значение — `SensorConfigError`. Любая заданная некорректная величина должна завершать старт с ошибкой, не подменяться дефолтом; это относится и к явно переданным флагам при `ENABLED=false`. Флаги независимо включаемые, горячего reload нет, обновляются только при старте `fingerprint-sensor.service`. Не добавлять числовые параметры и не выводить новые настройки в общий конфиг портала.

Всё OFF: существующая семантика, журналирование, циклы spool/producer, порядок событий и shutdown должны оставаться legacy-путём, без нового фонового таймера/очереди.

## 3. F1 — telemetry aggregation (можно реализовать в рамках разрешённого безопасного кода)

Убрать **только при включённом флаге** сообщения «по одному на успех» из `SensorRuntime._delivery_loop()` (`fingerprint_delivery_completed`) и отдельные частые обычные `fingerprint_suricata_stats` из `_emit_stats()`. Не трогать `_suricata_heartbeat()`, `_check_suricata_heartbeat()` и реакцию на unavailable.

- Окно по инжектируемому `monotonic` = 60 секунд, без привязки к UTC-wall-clock.
- За окно: `delivery_success = sum(result.delivered)` и **новое safe поле** `delivery_success_batches = число result.status == "delivered"`.
- Suricata: хранить **последние валидные** `capture_kernel_packets`, `capture_kernel_drops`, `capture_kernel_ifdrops` (последнее — только если присутствует в валидной записи); если валидных stats в окне нет — **не** публиковать эти поля и **не** создавать нули. Поля stats отражают только последнюю действительно полученную валидную запись, не суммируются.
- Публиковать данные в **существующем 60-секундном** `fingerprint_sensor_metrics`, уже создаваемом `_telemetry_loop()` / `_emit_metrics()`; не добавлять ещё одну периодическую journald-строку. После передачи агрегата в однократный emit очищать агрегат; атомарно snapshot/reset под lock, чтобы не удваивать счётчики при гонке с shutdown. Логирование само по себе не является долговечной гарантией: сохранять fail-open поведение SensorTelemetry и fallback при исключениях. Safe allowlist в `SensorTelemetry` расширить только на `delivery_success_batches` и точно необходимые ограниченные числовые counters; ни UUID, ни MAC/IP/SNI, URL, payload, secret.
- При штатном shutdown, если счётчики агрегата ненулевые, перед `fingerprint_sensor_stopped` выдать одну итоговую ограниченную сводку; ошибки агрегатора не блокируют Sensor/spool и ведут к legacy safe telemetry fallback.
- Эти события остаются **немедленными**: start/stop, `fingerprint_delivery_retry`, `fingerprint_delivery_rejected`, любые source/runtime transitions и ошибки capture/preflight/raw/EVE/Suricata/credentials/TLS/config, spool overflow/capacity/stale-drop faults, fatal/exception. Обычные `fingerprint_sensor_metrics` продолжают выходить каждые 60 секунд.

## 4. F1 — proof-gated stale purge (EX-FP-W2-01 OWNER APPROVED; реализовать сейчас)

`SensorSpool` использует только process-local memo **`next_possible_stale_at_utc`** со состояниями `UNKNOWN / EMPTY / datetime`, без записи memo в SQLite. `initialize()` сбрасывает в `UNKNOWN`. В синхронизированном `RLock`:

1. Перед `enqueue()`/`batch()` определить, нужен ли bounded purge. **Важно:** legacy `enqueue()` сейчас вызывает публичный `purge_stale()`, который по требованию пункта 5 должен оставаться принудительным. Разделить внутренний conditional gate и публичную безусловную операцию, не пропуская очистку случайно. Если memo `UNKNOWN`, сначала читать **ровно** `SELECT MIN(observed_at) FROM sensor_spool`; empty→`EMPTY`, иначе canonical UTC + 86400 секунд → deadline. Некорректное время/ошибка memo → `UNKNOWN` и **legacy purge**, а не пропуск.
2. Можно пропустить **только хранимый** stale-`DELETE`, если memo `EMPTY` либо текущее UTC `<` доказанного deadline. Если `now >= deadline`, обязательно выполнить существующий bounded purge (`observed_at < now - 86400`), затем перестроить memo по DB minimum. При последовательном batch-purge по 100 повторять, как в legacy до исчерпания.
3. Каждый входящий event по-прежнему проверять на возраст независимо от skip stored purge; boundary строгий: `<86400s` и `==86400s` retained, `>86400s` stale.
4. После успешного **нового** `INSERT` обновить memo консервативно `min(existing_deadline, observed_at + 86400s)`; если невозможно доказать, выставить UNKNOWN. `INSERT OR IGNORE` дубликаты не позволяют передвигать deadline позже. ACK/eviction/deletion могут оставить более ранний deadline, **не позже** фактического.
5. Публичный явный `purge_stale()` **всегда** выполняет legacy purge, даже если memo считает все записи свежими. Существующие проверки ограничений места/строк/восстановления `capacity_blocked` — authoritative, никакого capacity cache. При ошибке memo fallback к unconditional purge, не startup success по ложному предположению.
6. При флаге OFF — дословная legacy-ветка `purge_stale()` в enqueue и `_purge_stale()` в batch; не изменять Task-02 frozen behavior.

Нельзя переписывать `SensorSpool` на WAL, менять `synchronous=FULL`, индекс/таблицу, 24h TTL, лимит удаления 100, row/byte budgets или `capacity_blocked`.

## 5. F2 — bounded ingress coalescing (default OFF, активация только с EX-FP-W2-02)

**Ровно** три freeze-константы, без production knobs (кодируем, но не включаем на production):

```text
MAX_EVENTS=32
MAX_OLDEST_EVENT_WAIT_MS=100
MAX_BUFFERED_SERIALIZED_BYTES=262144
```

Интерфейс: потокобезопасный process-local evidence-only coalescer. Runtime вызывает единый private `submit(events)` вместо прямого `spool.enqueue(events)` на двух evidence-трассах `_raw_loop`/`_eve_loop`; ВСЕ source-health paths обязаны проходить через immediate barrier при включённом F2, включая `_set_local()`, `_publish_local_health()`, `preflight_or_report()` и health-events из `_delivery_loop()`. В режиме OFF остаются прямые legacy-вызовы. Действующий `SensorSpool.enqueue` остаётся единственным durable write-owner; не создавать второй DB/sidequeue.

- `endpoint=evidence` можно удерживать максимум до первого trigger. `endpoint=source_health` **никогда не буферизовать**: до его записи немедленно предпринять flush предыдущих evidence, затем через legacy `spool.enqueue` сохранять source-health отдельно. Не объединять endpoints в одну spool-транзакцию.
- Один `threading.Lock/Condition` определяет монотонные submission ordinals для нескольких threads; сохраняет исходный порядок events внутри вызова и порядок входа разных потоков в guard. По observed_at **не** сортировать.
- Trigger flush на первом из: 32 pending events; возраст самого старого события 100ms monotonic; следующий event привёл бы к превышению 256 KiB; source_health; orderly shutdown; producer loop fault exit; появление `spool.capacity_blocked`; coalescer fallback. Событие >256KiB обходит буфер и сразу идёт в legacy enqueue при соблюдении старых лимитов.
- Применять безопасно ограниченный *serialized-size* (детерминированный JSON без утечки payload в лог). Никогда не превышать 32 / 256KiB при инкременте, не превышать прежний `MAX_TRANSACTION_ROWS=100` при flush.
- Отдельный bounded flush timer/condition с deadline на монотонных часах, без busy-loop: даже **одно событие и нулевой последующий трафик** должно уходить в spool по истечении 100ms + допустимая задержка планировщика.
- Coalescer не меняет `event_id`, документы, Site, producer/source identity, timestamps и source_kind. `INSERT OR IGNORE` остаётся в spool. Не переразбирать/recreate event в retry. HTTP endpoint batching и ACK после HTTP-200 остаются полностью в `EvidenceProducer.deliver_once()`.
- Coalescer failure при исправном spool: выключить коалесцирование до перезапуска; ровно одна ограниченная попытка legacy flush pending **тех же** IDs; последующие события идут legacy immediately; emit sanitized fault. Spool/capacity fault → прежние degraded/fault semantics, не оптимистическое подтверждение.
- Orderly shutdown использует **существующий общий 20s budget**: остановить приём raw/EVE; закрыть capture/EVE; join **source producer** loops; flush pending один раз; stop/join coalescer timer; затем закончить текущий delivery-loop и закрыть spool, итоговое routine telemetry до final stopped. `clean=True` только если все необходимые workers завершились и flush завершился. Если timeout/spool flush error — `clean=False`, без «clean shutdown» заявления; не удалять/переписывать spool.
- Worker exception path `_raw_loop` и `_eve_loop` выполняет flush barrier перед fault transition, не делает source-health available из недолговечного буфера.
- Контракт аварии (не скрывать): crash до durable spool commit может потерять **не более 32 pending evidence, не более 100ms возраста, не более 256KiB**, уже committed spool rows сохраняются в полном объёме. Это **не** zero-loss; OFF сохраняет legacy guarantees. Production activation **HOLD**, пока Owner прямо не примет эту границу.

## 6. Запреты (обязательные)

**Нельзя**: изменять `SensorSpool` journal `DELETE`/`FULL`; `MAX_TRANSACTION_ROWS=100`; ACK delay/grouping; HTTP success/failed semantics; Task-01 schema/idempotency/watermark; источник capture, RSPAN/SPAN и Suricata; классификацию Fingerprint; CAPPORT/Auth; visitor/attribution/NI-01–NI-06; `fingerprint-evidence.service` repository; retention/capacity limits; Git operations или production deployments; писать секреты, MAC/IP/SNI в телеметрию. Никаких будущих «примените более быструю sqlite настройку».

**Нет новых API, новой таблицы, миграции, фоновых обязательств портала.** Новые flags существуют только внутри процесса Fingerprint Sensor. Когда OFF, не запускать coalescer timer/stream и не создавать необязательных disk operations.


## 6A. Однозначные условия готовности исходников (проверяет только TechLead23)

Код не считается законченным, если отсутствует хотя бы одно из следующих свойств:

1. **OFF/OFF/OFF** — старые вызовы `SensorSpool.enqueue()/batch()/acknowledge()` и `SensorRuntime.shutdown()` остаются прежними по поведению; отсутствуют фоновые coalescer threads, новые SQLite операции и новые journal-строки.
2. **F1 stale** — неизвестный/повреждённый cache и любой недоказанный факт свежести приводят к старому пути `DELETE`; явный `purge_stale()` всегда выполняется; 24h сравнение строгое. Состояния EMPTY/TIMESTAMP обновляются только на основаниях из authoritative SQLite и новых вставок; `ACK` не может продлить deadline.
3. **F1 telemetry** — одно существующее сообщение `fingerprint_sensor_metrics` за 60 секунд содержит агрегированные успехи и последние валидные Suricata stats; аварии, переходы состояний и отказ доставки всегда сообщаются немедленно; штатное выключение не теряет накопленную routine summary без попытки финального emit.
4. **F2 коалесцер** — 33 события дают 32 + 1, одиночное событие сбрасывается таймером, все source-health входят через барьер, входной порядок сохраняется при конкуренции потоков, rollback/retry использует прежние UUID, а `shutdown(clean)` не сообщает успех при незавершённом flush. Буфер никогда не становится долговременным доказательством.
5. **Durability** — не меняются `journal_mode=DELETE`, `synchronous=FULL`, ACK-after-200, HTTP retry/duplicate semantics, размеры spool/TTL, endpoint-homogeneous delivery, Task-01 evidence repository и классификация Fingerprint.

Это **критерии приёмки для моего независимого review**, а не поручение Coder писать тесты или доказывать производительность. По контракту Архитектора я самостоятельно проверю T01–T20, включая аварии, дедупликацию, восстановление, нагрузку и совместимость. Никакой новый QA-исполнитель не назначается.

## 7. Результат Coder / handoff

После реализации **всех трёх** функций передать TechLead23:

1. Точный путь worktree (от pinned base), `BASE_HEAD`, `BASE_TREE`, список изменённых и новых исходных файлов, summary `+/-`.
2. Один чистый patch или `git diff` **включая untracked files**, SHA-256, краткое объяснение реализации F1 и F2, default OFF, условий двух owner exception gates.
3. Любые unresolved ambiguities/архитектурные стоп-факторы отметить как `HOLD`, не угадывать.
4. `TESTS/QA/PERF/GIT/PR/PRODUCTION_ACTION=NOT_DONE`; не делать commit/push/PR/merge/деплой, не просить доступ к production.

**Ответственность TechLead23 (не Coder):** провести полные независимые безопасные тесты на временной spool SQLite, boundary/clock/crash/ACK/health/replay и protected-regression матрицу T01–T20 из Архитектурного контракта, дать Tech Lead PASS/FAIL и только после этого авторизовать Coder на Git-публикацию. Реальные IOPS/PRTG и production activation — отдельное действие TechLead23/Owner, не требующее от Coder доказательств.

## 8. Зафиксированное решение Owner и единый маршрут работы

Owner **согласился с оценкой TechLead23** 2026-10-12 и запросил готовый единый Coder TASK. Эта директива реализует решение без следующих уточнений:

- `EX-FP-W2-01` = **OWNER APPROVED** для реализации доказательно безопасного stale purge; код F1 писать сейчас. Срок хранения 24 часа и консервативный fallback неизменны.
- `EX-FP-W2-02` = **SOURCE IMPLEMENTATION AUTHORIZED, PRODUCTION ACTIVATION NOT AUTHORIZED**. F2 писать сейчас с default OFF. Дополнительное явное решение Owner потребуется **только перед включением F2 на production**, не перед написанием кода.
- `F1 telemetry` = **APPROVED FOR IMPLEMENTATION**.
- `F3 evidence sink` = **NO MUTATION**, аналитика и performance/PRTG остаются у TechLead23/SysAdmin.

Это **один Coder TASK**, один независимый TechLead review по исходникам и его собственные тесты. При обнаружении конкретных дефектов TechLead23 выдаёт лишь точечное исправление. После TechLead PASS может последовать отдельное разрешение Coder на commit/push/PR; deployment и activation остаются действиями Owner/TechLead23.

```
TASK_STATUS                   = READY_FOR_CODER
CODE_IMPLEMENTATION          = AUTHORIZED
ALL_FLAGS_DEFAULT            = OFF
STALE_PURGE_EXCEPTION        = OWNER_APPROVED
INGRESS_COALESCE_SOURCE_CODE = AUTHORIZED
INGRESS_COALESCE_PRODUCTION  = HOLD_OWNER_EXPLICIT_EXCEPTION
CODER_TESTS_QA_PERF          = NOT_ASSIGNED
CODER_COMMIT_PUSH_PR_MERGE   = NOT_AUTHORIZED
PRODUCTION_CHANGES           = NOT_AUTHORIZED
```

