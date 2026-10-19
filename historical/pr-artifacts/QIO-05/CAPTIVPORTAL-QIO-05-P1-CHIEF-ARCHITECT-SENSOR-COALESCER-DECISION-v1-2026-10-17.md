# CAPTIVPORTAL — QIO-05 P1
## Chief Architect — Sensor IngressCoalescer Durability Decision v1

**Дата:** 2026-10-17 · **Адресат:** Performance & Optimization Tech Lead  
**Вход:** `CAPTIVPORTAL-QIO-05-P1-CHIEF-ARCHITECT-REQUEST-SENSOR-COALESCER-DURABILITY-2026-10-17(1).md`; `CAPTIVPORTAL-QIO-05-P1-TECHLEAD-SENSOR-SPOOL-AND-NI02A-LAB-RESEARCH-2026-10-17(1).md`.  
**Изученный source ref:** `ZaurNavi/CaptivePortal@cd83c3e04233593126d247b0c96c1135f4233072` (GitHub read-only). Контроль текущей загруженной production-версии и значения runtime flag **не выполнялся**.  
**Статус:** **`ARCHITECTURE_REJECT_PRE_DURABLE_BUFFER`** для включения существующего default-OFF coalescer. Эта диспозиция не отменяет его ценности как исследовательского прототипа и не запрещает независимую **безопасную** оптимизацию после устойчивой записи.

## 0. Вердикт и что именно отклонено

**ОТКЛОНИТЬ production-активацию нынешнего `DEVICE_FINGERPRINT_SENSOR_IO_INGRESS_COALESCE_ENABLED` в текущем контракте `submit()`**: получение события Sensor и возврат из `submit()` могут предшествовать durable SQLite insert, а доказуемого replay raw/EVE источника либо crash-surviving provenance для утраченного pre-durable интервала не предъявлено. Не считать bounded window (`32 events / 100 ms / 262144 bytes`) автоматически безопасной. Только снижение syscall не может расширить принятую гарантию полноты Evidence.

**Формальный различитель:**

- `observed/captured`: нормализатор получил входное наблюдение; оно ещё не является подтверждённо сохранённым Evidence;
- `volatile_pending`: событие находится в памяти; **не принято как durable**, может исчезнуть при аварии;
- `durable_spooled`: успешная SQLite-транзакция включила событие в `SensorSpool` (`DELETE` journal, `synchronous=FULL`); это локальная граница durable acceptance;
- `central_acknowledged`: центральный Evidence API подтвердил durable-aware обработку, после чего spool может удалить строки; доставка уже закреплена существующим at-least-once/idempotency контрактом.

Нельзя объявлять `volatile_pending` устойчиво принятым; нельзя выдавать `SensorSpool.enqueue` за факт центрального ACK. Для вновь принятого Evidence без отдельного **явного, заранее разрешённого** lossy contract должен действовать путь возврата только после durable acceptance.

**Не следует путать:** не гарантируется абсолютная запись каждого пакета на L2 — потери capture, overflow, retention и capacity уже являются отдельными ограниченными возможностями системы. Решение запрещает новый *неучтённый* разрыв после захвата и до durable acceptance, который невозможно квалифицировать по event-time.

## 1. A1 — durable authority boundary

**`A1=REJECT_VOLATILE_ACCEPTANCE_FOR_EXISTING_CONTRACT`.**

1. `IngressCoalescer.submit()` может вернуть `0` после помещения Evidence в `_pending`; вызывающие части runtime не ждут подтверждения SQLite. Число `0` не является доказательством безопасного отсутствия Evidence: оно может означать buffered submission. `SensorRuntime._raw_loop()` продолжает обработку и независимо вызывает `_attribution_call("record_frame", ...)`.
2. `IngressCoalescer._flush_locked()` **сначала** делает `self._pending = []`, **затем** вызывает `spool.enqueue(..., atomic_coalesced=True)`. Если процесс умирает или запись завершается неудачей, buffered events могут исчезнуть. Автоматическое включение direct-write fallback после ошибки не восстанавливает события после hard crash и не отменяет уже возвращённые submit.
3. `SensorSpool` остаётся единственным durable ingress-writer. Существующий успешный commit — точка, после которой разрешено считать событие готовым для at-least-once delivery. SQLite `synchronous=FULL` и другие durability-параметры остаются неизменны.
4. Для **NI-02A DHCP authority**, подтверждения `verified_through`, source coverage и других authority-фактов **никакая** pre-durable буферизация в рамках QIO-05 не разрешена.
5. Если Owner в будущем захочет **осознанно** разрешить bounded best-effort evidence loss, это будет отдельный frozen-semantic change/admission: явный договор `captured vs volatile vs durable`, видимые source-health / coverage-gap / reboot epochs, последствия для downstream классификации и Owner risk acceptance. Текущий флаг не может служить таким договором сам по себе.

## 2. A2 — ordering, barriers, stop и размеры окна

**`A2=CURRENT_BARRIERS_INSUFFICIENT_FOR_ABRUPT_CRASH`.**

- Нормативный принцип: source-health/fault/recovery/stop/delivery-success не должны сообщать о более высокой степени готовности/полноты, чем реально durable evidence и достоверное состояние source. Сначала durable-база, затем подтверждение зависящего от неё progress/health; ошибки не маскировать обычным `available`.
- В коде `barrier()` сначала вызывает `_flush_locked()`, затем `spool.enqueue(health)`; это поддерживает порядок в **успешном нормальном выполнении**, но не обеспечивает crash-safe доказательства, что предыдущий `submit()` успел стать durable. `_submit_health([])` вообще не выполняет flush, потому что при дедупликации здоровье может не породить событие.
- `shutdown(deadline=...)` содержит bounded final-flush и может вернуть `False`, но гарантии graceful shutdown неприменимы к `SIGKILL`, OOM, отказу питания, падению VM и остановке гипервизора без исполнения обработчиков.
- При spool exception механизм отключает coalescer / публикует fault лишь best-effort. Даже удачно отправленная fault-телеметрия не восстанавливает уже пропавший список событий.
- **Разрешённый максимум событий, для которых `submit()` уже вернулся, но они остаются только volatile: `0`**. Поэтому `32`, `100 ms`, `262144 B` как operational activation settings = **NOT ADMITTED**, а не «уменьшить до 16/50ms». Это не запрещает короткое локальное накопление нескольких элементов *внутри одной ещё незавершённой синхронной submission-транзакции*, в которой caller ждёт durable completion и имеет чёткую fault/retry семантику.

## 3. A3 — replay, idempotency, gaps, downstream truth

**`A3=REPLAY_UNPROVEN / UNOBSERVED_LOSS_POSSIBLE`.**

- `RawCapture.receive()` принимает живой `AF_PACKET` socket; `EveReceiver.receive()` читает Unix `SOCK_DGRAM`. Ни один из изученных input paths не предоставляет durable replay/offset ACK для уже прочитанного события. Присутствие Suricata в системе **не является доказательством** наличия долговечного повторного источника конкретных datagrams.
- Durable spool event IDs сохраняются при retry и позволяют dedup `INSERT OR IGNORE`. Это защищает **уже сохранённые строки**, но не восстановит исчезнувшее из `_pending` наблюдение.
- SourceHealthTracker публикует transition/heartbeat (`available/unavailable/unsupported`, около 300s). Ни ingress, ни health-объект не содержит durable pre-commit event counts, terminal ordinal, guaranteed replay cursor или crash-surviving interval watermark. При hard crash поток может исчезнуть **без записанного `delivery_loss_confirmed`**, затем новое `available` может выглядеть как непрерывная работоспособность.
- Source-health policy знает `unknown` и `delivery_unavailable_loss_possible`, однако наличие этих классов **не означает**, что текущий Sensor установит их правильно именно на событии sudden pre-durable crash. В частности, отсутствие health heartbeat может в конечном итоге вызвать `unknown` по freshness, но **не доказывает корректную event-time границу потери**.
- Запрещено трактовать незаписанное Evidence как `no device`, `negative fingerprint`, пустое успешное покрытие или делать положительный NI/identity вывод о completeness. `covered_available` / статус `ready` без соответствующей гарантии нельзя использовать как доказательство полноты утраченного интервала.
- Никакие source offsets / authority generations / processing checkpoints не могут проходить дальше доказуемой durable или гарантированно воспроизводимой границы.
- Существующий future classification contract допускает честное `delivery_unavailable_loss_possible` / `delivery_loss_confirmed` и `unknown`; **подмена loss локальным good-health не допустима**. Прежде чем рассматривать иной lossy дизайн, потребуется отдельный протокол durable epoch/pending boundary и исключение ложного `covered_available` даже при crash/restart; его долговечность и полезность для I/O нужно доказать, а не предположить.

## 4. A4 — Lab verification: обязательные детерминированные проверки

**`A4=EXISTING_FLAG_NOT_ADMITTED; LAB_DIAGNOSTICS_ALLOWED_NO_PRODUCTION`.** Tech Lead вправе исследовать текущий источник **в disposable Lab**, но тесты не превращают REJECT в activation PASS автоматически. На каждой фазе сравнивать видимые accepted IDs, durable spool IDs, отправленные/acknowledged IDs, loss/gap state, ordering и source-health truth. Инъекции делаются в отдельной SQLite и синтетических захваченных событиях без production data.

| ID | Failure / workload | Обязательная проверка |
|---|---|---|
| S01 | Normalization до submission | Нельзя объявить durable acceptance или новый watermark |
| S02 | Успешный volatile `submit` до timer flush; внешний `SIGKILL` | Выявить исчезнувшие IDs и отсутствие replay, оценить может ли это быть доказуемо маркировано после restart |
| S03 | Power-cut/model crash после помещения 1, 31, 32 events в память | Нижняя и верхняя границы потенциальной потери |
| S04 | Исключение до `BEGIN`, после `BEGIN` до `COMMIT` | Не выдавать success; транзакция атомарна, нет ложного durable counter |
| S05 | Падение сразу после успешного `COMMIT`, до consumer signal | Durable rows переживают restart, повтор безопасен по `event_id` |
| S06 | `source_health` barrier при pending evidence | FIFO evidence-before-health при нормальном завершении, отказ не превращается в `available` |
| S07 | `source_health` dedup (`events=[]`) | Отсутствующий barrier не должен быть ошибочно объявлен гарантией flushed evidence |
| S08 | Параллельный raw + EVE submit + health + delivery | Порядок авторитетных health/evidence без silent skip и race |
| S09 | Graceful stop 20 s; блокировка SQLite дольше deadline | `shutdown=False`, подтверждённое non-clean; повторный запуск не выдаёт мнимой полноты |
| S10 | `SIGKILL`, OOM, VM crash/reboot | Никакой graceful flush/diagnostic callback недоступен; честная неопределённость |
| S11 | 32 events / 262144 bytes / oldest 100ms boundary | No overflow, path fallthrough and actual delay; не утверждать burst safety только по лимитам |
| S12 | Spool `capacity_blocked`, DB FULL/BUSY/IOERR, exhaustion | Fail-closed, сохранение уже committed rows и source-health semantics; ни hidden success, ни потерянный control факт |
| S13 | Duplicate IDs, retry, network timeout, API 200 before ack delete | At-least-once и `INSERT OR IGNORE` без ложной новой полноты |
| S14 | 24h stale retention, purge/eviction on capacity | Count/mark known drops, не превращать их в успешное полное покрытие |
| S15 | No events, health heartbeat, recovery following crash | Отсутствие фактов не интерпретировать как полноту неописанного интервала |
| S16 | NI-02A `record_frame` / `confirm_capture` concurrently with pending evidence | Независимая authority не получает ложных гарантий из buffered advisory evidence |
| S17 | Long-running burst/calm/normal intervals and flush-on-fault | Stability, producer memory bounds, ordering, fair latency; no silent trapped queue |
| S18 | Windows + Linux focused suite, then independent TL full suite | Platform outcome, reproducible traces, source/artifact SHA, zero hidden test suppression |

`S02/S03/S10` для текущего pre-durable архитектурного варианта **ожидаемо показывают возможную потерю**, поэтому не являются gate, который можно «сдать» без изменения контракта. Любое будущее предложение должно обеспечить durable acceptance или формальное разрешение + truthful recovery semantics.

**Performance gate:** отдельные показатели local `pwrite64`, `fdatasync`, `unlink`, SQLite commits, throughput, FIFO/lag, stop latency и end-to-end `guest io.stat → QEMU → physical HDD`. Лабораторные числа **2614→126 pwrite64, 404→20 fdatasync, 102→6 unlink** относятся к прямому группированию вызовов `SensorSpool.enqueue`, **не** к полноценному coalescer runtime/failure path и **не** к измеренному production HDD выигрышу. Значимый IO gain необходим для будущей оптимизации, но не заменяет safety gates.

## 5. A5 — activation, compatibility, rollback

**`A5=NO_OFF_TO_ON_GO`.**

1. `OFF→ON` сейчас **запрещено**. Текущее фактическое значение production флага неизвестно; read-only инспекция остановлена Tech Lead при IO full PSI >5%. Не утверждать, что флаг точно OFF в живом процессе только потому, что default=false.
2. При следующем разрешённом безопасном preflight Tech Lead/SysAdmin сверяет nonsecret `runtime flag`, loaded artifact SHA, activation path, настоящие spool IDs/metrics, Sensor/Evidence health, pending delivery/ACK, authority coverage, возможность отката и backpressure. Без преодоления pressure gate и Owner GO runtime конфигурацию не трогать.
3. Если неожиданно обнаружится `ON`, **STOP / INCIDENT REVIEW**: уведомить Owner о расхождении и предложить безопасный переход OFF с сохранением уже durable spool и пониманием startup/restart риска; **никаких односторонних `systemctl restart` или env edits**.
4. Само выключение флага не восстанавливает потенциально утраченные до durable события. Rollback должен сохранить DB/schema, `producer_event_id`/`event_id`, уже отправленные ACK и pending durable rows. После переключения и рестарта проверять source-health/loss-gap uncertainty, actual Auth/NI correctness и отсутствие чужого вмешательства.
5. Для *будущего нового контракта* потребуются заранее подготовленные feature flag default-OFF, rollback к подтверждённому base SHA/tree, целевые мониторинги `captured`, `enqueued_durable`, `volatile_pending`, `commit_failures`, `capacity_blocked`, `flush_error`, `delivery_retry`, `ack`, `source_health_transition`, `known_gap/unprovable_gap`, `restart_epoch`, `shutdown_clean`. **Счётчик только в RAM не может доказать, что не было потерь при power loss.** Метрики должны различать отсутствие данных и отсутствие передачи.
6. **Не менять** существующую durable SQLite spool (DELETE/FULL), источник DHCP authority, event ID identity/dedup, SourceHealthPolicy, центральный Evidence API и Viewer/Classification semantics без самостоятельного семантического допуска. Архитектура не требует писать новые production health rows ради красивых dashboard metrics.
7. Да, для включения текущего кода **недостаточно только флага**: либо нужен другой no-loss алгоритм, либо отдельно запрошенный и принятый Owner+Architect контракт управляемой потери с доказуемой деградацией покрытия. Локальные bugfix возможны лишь как отдельный bounded TASK и не дают автоматического activation GO.

## 6. A6 — окончательное решение и допустимые альтернативы

**`A6=ARCHITECTURE_REJECT_PRE_DURABLE_BUFFER`** — текущая семантика `submit()` с pre-durable memory queue не допускается в production. Это **не общий запрет batching** и не запрет исследовать всё в disposable Lab.

**Допустимая следующая ветка:** `POST_DURABLE_OR_SYNCHRONOUS_BATCHING_RESEARCH`:

- Собирать уже имеющиеся **на момент вызова** `Iterable[NormalizedEvent]` и выполнять одну синхронную bounded SQLite-транзакцию; возвращаться вызывающему коду только после durable commit. Если вызов принёс одно событие, нельзя незаметно ожидать следующих из иных вызовов после successful return.
- Для трафика, который уже надёжно записан в отдельно принадлежащий durable журнал источника с replay/ack, можно исследовать группирование его последующих операций. В текущей raw/EVE модели такой журнал **не подтверждён**, поэтому не приписывать ему ожидаемый выигрыш.
- Можно оценить уже существующую **post-spool** batch HTTP delivery и совместимые derived-only cache/aggregate операции, не расширяя окно отсутствия durable evidence. Не обещать, что post-spool batching сократит **ingress** `fsync`: это другое место нагрузки.
- Если значимое сокращение I/O возможно только с подтверждением Evidence через некоторое время после capture, сначала формально спроектировать *новую* acceptance/loss/gap/replay/health семантику и получить отдельное Owner risk decision; существующее default-OFF переключение не считается достаточной архитектурой.

### Machine-readable disposition

```ini
TASK=QIO-05
PHASE=P1_CHIEF_ARCHITECT
DECISION=ARCHITECTURE_REJECT_PRE_DURABLE_BUFFER
A1=REJECT_VOLATILE_ACCEPTANCE
A2=INSUFFICIENT_HARD_CRASH_ORDER_AND_BARRIER_PROOF
A3=INPUT_REPLAY_UNPROVEN_LOSS_GAP_UNOBSERVABLE
A4=DISPOSABLE_LAB_FAILURE_RESEARCH_ONLY
A5=OFF_TO_ON_NOT_AUTHORIZED
A6=REJECT_CURRENT_ACTIVATION
NI02A_COVERAGE_CADENCE=FROZEN
SENSOR_SPOOL_DELETE_FULL=FROZEN
ALTERNATE=POST_DURABLE_OR_SYNCHRONOUS_BATCHING_RESEARCH
CODE_EDITS=NO
CODER=HOLD
PR_MERGE=NO
PRODUCTION_CHANGES=NO
OWNER_GO=NO
HOST_PHYSICAL_HDD_SAVINGS=UNPROVEN
```

## 7. Tech Lead next action

Tech Lead принимает/возвращает архитектурную диспозицию и самостоятельно выбирает следующий ограниченный read-only/source/Lab вопрос. Если нужна оптимизация ingress без потерь, сначала исследовать **синхронную bounded group submission** на уже доступных входных списках и отделить его эффект от 100 синтетических одиночных вызовов. Если инициируется разрешение на lossy advisory capture — оформить **отдельный frozen contract change request** с точной областью потерь, источник-epoch/watermarks, replay assumptions, статусами неизвестного coverage, аппаратной аварией и отдельным решением Owner. До этого `IngressCoalescer` не активировать.

**Живой production не изучался и не менялся в этой архитектурной передаче.**
