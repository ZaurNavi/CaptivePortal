# TASK-VISIT-LIFECYCLE-02 — устранить потерю Visit Start из-за конкуренции SQLite writers

## 1. Статус и приоритет

- Тип: production defect fix.
- Приоритет: высокий.
- Область: Visit Lifecycle.
- Production deployment/activation в рамках задания запрещены.
- Schema migration не требуется и запрещена без отдельного согласования.

## 2. Исходное состояние

Visit Lifecycle объединён в `main` и активирован в production.

Контрольная production-версия на момент диагностики:

```text
main SHA: fe797593fb12b9cb9f81bdb22e1c14f2d08b037e
Visit schema: v2
SQLite quick_check: ok
```

На production подтверждено:

- база исправна;
- schema v2 соответствует контракту;
- Reader полностью догнал rotated и active normalized webhook journals;
- Visits открываются и закрываются;
- Reconciliation связывает Visits с Visitor Registry;
- runtime продолжает работать после временных конфликтов;
- `visit.runtime_unavailable` после активации не наблюдался.

После завершения initial backfill зарегистрировано:

```text
visit.opened=53
visit.start_reused=2
visit.authorization_attached=55
visit.closed=35
visit.reader_scan_completed=2022
visit.reader_scan_failed=5
visit.reconciliation_degraded=3
visit.storage_error stage=start category=busy=4
```

Четыре ошибки Start являются потенциально потерянными регистрациями авторизации: Start работает fail-open и после `VisitStorageError(BUSY)` не повторяет запись.

## 3. Подтверждённая причина

В production runtime создаётся один `VisitRepository`. Этот же объект передаётся:

- `VisitLifecycleService` и Start path;
- `VisitLifecycleWebhookReader`;
- `VisitLinkReconciler`;
- `VisitLifecycleReadService`.

В `VisitRepository` имеется один `threading.RLock`, поэтому проблема не вызвана отдельными repository instances.

Текущий writer path использует `_bounded_write()`:

1. пытается получить общий `_write_lock`;
2. ждёт не более `busy_timeout_ms`;
3. текущий default равен `250 ms`;
4. при истечении времени выбрасывает `VisitStorageError(BUSY)` ещё до выполнения полезной транзакции;
5. этот же параметр применяется также к `sqlite3.connect(... timeout=...)` и `PRAGMA busy_timeout`.

Таким образом, один параметр одновременно управляет:

- ожиданием внутреннего application writer-slot;
- ожиданием блокировки SQLite;
- Start;
- Reader;
- Reconciliation.

`LocalVisitStartSubmitter` вызывает Start синхронно один раз. При `VisitStorageError` он пишет `visit.storage_error`, возвращает `status="unavailable"` и не выполняет retry.

Reader и Reconciliation вызываются повторно фоновыми циклами, поэтому после временной конкуренции восстанавливаются. Start аналогичного механизма восстановления не имеет.

Production timestamps показывают взаимную конкуренцию:

- `reader_scan_failed` возникает рядом с `visit.opened`, `visit.authorization_attached` или `visit.link_reconciled`;
- `visit.storage_error stage=start category=busy` возникает рядом с `visit.reader_scan_completed`;
- база после конфликтов остаётся исправной;
- Reader продолжает движение checkpoint.

## 4. Цель

Устранить потерю Visit Start при нормальной внутрипроцессной конкуренции Start, Reader и Reconciliation за общий SQLite writer-slot, сохранив:

- fail-open пользовательской авторизации;
- bounded latency auth path;
- идемпотентность Visit Start;
- атомарность Reader event + checkpoint;
- восстановление Reader/Reconciliation;
- текущую schema v2;
- существующие публичные контракты вне Visit Lifecycle.

## 5. Обязательные функциональные требования

### 5.1. Разделить политики ожидания

Нельзя использовать один и тот же числовой лимит как единственную политику для всех следующих случаев:

- foreground Start writer-slot;
- background Reader writer-slot;
- background Reconciliation writer-slot;
- SQLite `busy_timeout`.

Допустима выбранная кодером реализация, но назначения и пределы ожидания должны быть явно разделены в коде и тестах.

Если добавляются настройки:

- они должны иметь безопасные defaults;
- должны проходить существующую централизованную config validation;
- должны быть отражены в `.env.example`;
- запрещено требовать новых production env values для сохранения обратной совместимости;
- имена и смысл настроек должны однозначно отличать writer-slot wait, SQLite wait и retry budget.

### 5.2. Исключить starvation Start

Foreground Start не должен проигрывать бесконечному повторному захвату writer-slot фоновым Reader/Reconciliation.

После появления ожидающего Start фоновые операции не должны бесконтрольно пере-захватывать слот перед ним.

Конкретный механизм выбирает кодер. Допустимы, например:

- справедливый/приоритетный write coordinator;
- сериализованный writer executor;
- иной локальный механизм, детерминированно исключающий starvation.

Простая замена `250 ms` на большее значение без устранения starvation не считается выполнением задания.

### 5.3. Добавить bounded retry для Start

При transient `BUSY` Start должен выполнять ограниченные повторные попытки в пределах общего latency budget.

Требования:

- retry разрешён только для категории `BUSY`;
- validation, unavailable, corrupt/schema и прочие постоянные ошибки не должны маскироваться retry;
- число попыток и общий budget должны быть конечными;
- между попытками должен применяться bounded backoff; допускается небольшой jitter;
- после исчерпания budget auth path остаётся fail-open;
- финальная ошибка должна возвращаться вызывающему коду как существующий безопасный `unavailable` outcome;
- одна успешная повторная попытка не должна порождать финальный `visit.storage_error` уровня error.

### 5.4. Гарантировать идемпотентность повторного Start

Retry одного логического запроса не должен создавать:

- второй открытый Visit для того же `site_id + client_mac`;
- дублирующую authorization row;
- повторную initial snapshot link;
- несовместимые telemetry outcomes `opened` и `start_reused` для одной фактически выполненной операции.

Повтор после неоднозначного результата транзакции также должен завершаться через существующие database invariants/idempotency, а не через предположение, что первая попытка точно не записала данные.

### 5.5. Сохранить корректность фоновых writer-путей

Reader и Reconciliation при временно занятом slot должны:

- выполнить bounded wait/retry либо безопасно отложить цикл;
- не продвигать Reader checkpoint без атомарно сохранённого результата события;
- не терять normalized webhook line;
- не создавать duplicate `visit_source_events`;
- не ломать `pending_match` retry;
- автоматически продолжить работу без restart runtime.

### 5.6. Не держать writer-slot дольше необходимого

Проверить все участки под `_bounded_write()` и `BEGIN IMMEDIATE`.

Под writer-slot запрещено выполнять:

- сетевые вызовы;
- sleep/backoff;
- чтение файлов журнала;
- обращения к Visitor Registry read service;
- telemetry I/O, если его можно выполнить после commit/release;
- другую работу, не требующую одной атомарной SQLite write transaction.

Если такая работа уже отсутствует, зафиксировать это тестами или кратким пояснением в handoff.

## 6. Telemetry

Нужно сохранить существующие event names для совместимости Grafana:

- `visit.storage_error`;
- `visit.reader_scan_failed`;
- `visit.reconciliation_degraded`;
- `visit.opened`;
- `visit.start_reused`;
- `visit.authorization_attached`.

Добавить безопасные поля, достаточные для диагностики конкуренции. Минимально:

```text
operation
attempt
retry_exhausted
wait_ms или lock_wait_ms
```

Допускаются дополнительные bounded поля, например `max_attempts` или `budget_ms`.

Запрещено помещать в telemetry:

- полный MAC;
- IP;
- authorization payload;
- токены/секреты;
- raw webhook record;
- exception text, способный раскрыть путь или данные клиента.

Требования к событиям:

- промежуточный успешно восстановленный `BUSY` не должен учитываться Grafana как финальный production error;
- исчерпание retry должно давать ровно одно финальное диагностическое событие для логической операции;
- Reader/Reconciliation должны отличаться через поле `operation` или существующий event name;
- существующие Grafana queries по event name не должны перестать работать.

## 7. Обязательные тесты

Тесты должны быть детерминированными. Запрещено полагаться только на случайную нагрузку и длинные `sleep`.

### 7.1. Start ждёт занятого background writer и успешно завершается

Организовать контролируемое удержание writer-slot Reader/Reconciliation дольше старого порога 250 ms.

Проверить:

- Start становится ожидающим;
- после освобождения slot Start завершается успешно в пределах budget;
- создаётся ровно один Visit;
- создаётся ровно одна authorization row;
- финального `visit.storage_error` нет.

### 7.2. Start имеет приоритет над повторным background acquire

Проверить порядок:

1. background writer удерживает slot;
2. Start начинает ждать;
3. второй background writer становится ожидающим;
4. после освобождения первым проходит Start;
5. background работа выполняется после него.

### 7.3. Retry Start идемпотентен

Смоделировать transient `BUSY`, затем успешную попытку и повтор/неоднозначный исход.

Проверить database invariants и отсутствие duplicate rows.

### 7.4. Retry exhaustion остаётся fail-open

Удерживать writer-slot дольше полного Start budget.

Проверить:

- вызов завершается за bounded time;
- возвращается безопасный `status="unavailable"` с category `busy`;
- создаётся ровно одно финальное `visit.storage_error`;
- присутствуют `operation=start`, итоговый attempt и `retry_exhausted=true`;
- исключение не выходит в auth flow.

### 7.5. Постоянные ошибки не повторяются

Проверить минимум:

- validation error;
- unavailable/corrupt/schema error, применимый к текущим контрактам.

Они не должны проходить BUSY retry policy.

### 7.6. Reader checkpoint остаётся атомарным

Смоделировать конкуренцию/`BUSY` во время обработки journal line.

Проверить:

- при неуспехе offset не продвинут;
- при следующем цикле строка обработана;
- `visit_source_events` не дублируется;
- offset после успеха соответствует обработанной строке.

### 7.7. Reconciliation восстанавливается

Смоделировать временно занятый writer-slot.

Проверить:

- runtime не становится permanently unavailable;
- последующий цикл связывает Visit;
- duplicate link/update отсутствует.

### 7.8. Конкурентная серия

Одновременно прогнать серию Start, Reader и Reconciliation operations.

Acceptance:

- нет потерянных успешных Start requests;
- нет duplicate open Visits;
- нет duplicate authorization rows;
- Reader достигает конечного checkpoint;
- `PRAGMA quick_check` возвращает `ok`;
- `PRAGMA foreign_key_check` не возвращает нарушений;
- exact schema v2 signature не изменена.

### 7.9. Shutdown

Проверить shutdown во время ожидающего/retrying Start:

- новые submissions перестают приниматься;
- уже принятые вызовы либо завершаются в пределах budget, либо безопасно возвращают unavailable;
- `wait_for_idle()` остаётся bounded;
- deadlock отсутствует.

## 8. Регрессионные требования

Обязательно сохранить:

- Python 3.10 compatibility;
- Windows/POSIX compatibility существующей suite;
- fail-open авторизацию;
- webhook finalization;
- rotated journal handling;
- pending event processing;
- reconciliation с Visitor Registry;
- read service;
- schema v1 → v2 migration;
- exact fresh/migrated v2 signature;
- отклонение повреждённой v2 без изменений;
- текущие event names и безопасную telemetry schema;
- отсутствие новых runtime dependencies.

## 9. Запрещённые изменения

В рамках задачи запрещено без отдельного согласования:

- менять Visit schema v2 или `PRAGMA user_version`;
- создавать schema v3;
- менять semantic определения Visit open/close;
- менять правила webhook matching/finalization;
- менять Visitor Registry schema;
- менять Observation/Analytics modules;
- менять Omada OpenAPI client;
- добавлять Redis/PostgreSQL/внешнюю очередь;
- делать auth path block-until-success без конечного budget;
- скрывать исчерпание retry понижением финальной ошибки до debug;
- выполнять production deployment/activation;
- исправлять несвязанные долги и форматировать несвязанные файлы.

## 10. Ожидаемый минимальный scope файлов

Точный набор определяет реализация, но ожидается работа преимущественно в:

```text
app/visit_lifecycle/config.py
app/visit_lifecycle/models.py
app/visit_lifecycle/repository.py
app/visit_lifecycle/start_sink.py
app/visit_lifecycle/webhook_reader.py
app/visit_lifecycle/reconciliation.py
.env.example
tests/visit_lifecycle/
```

Изменение файлов вне этого списка должно быть отдельно объяснено в handoff.

## 11. Проверки перед handoff

Кодер должен выполнить и привести фактические результаты:

1. targeted concurrency/retry tests;
2. всю `tests/visit_lifecycle` suite;
3. Omada/webhook integration tests, затронутые Reader;
4. Auth integration/worker tests, затронутые Start;
5. полную test suite;
6. `python -m compileall` для изменённых Python modules либо всего проекта;
7. проверку clean diff и отсутствия посторонних файлов;
8. проверку отсутствия секретов и PII в patch/telemetry fixtures.

Если полная suite содержит platform-specific skips, перечислить их отдельно. Ноль новых failures обязателен.

## 12. Обязательный handoff кодера

Handoff должен содержать:

- подтверждённую root cause по коду;
- описание выбранного механизма fairness/priority;
- отдельное описание Start retry policy и полного latency budget;
- объяснение, почему retry идемпотентен;
- перечень изменённых файлов;
- новые настройки и defaults, если добавлены;
- telemetry contract до/после;
- результаты targeted и full tests;
- commit/branch/patch metadata;
- инструкцию безопасного production deployment;
- отдельный production verification plan;
- rollback plan.

Commit, push, PR, merge и production deployment выполнять только по отдельному разрешению.

## 13. Definition of Done

Задача считается выполненной только если одновременно доказано:

1. Один общий writer coordination mechanism обслуживает Start, Reader и Reconciliation.
2. Ожидающий Start не starvation-ится фоновыми writer-путями.
3. Transient BUSY восстанавливается в bounded budget.
4. Retry exhaustion остаётся fail-open и наблюдаемым.
5. Повтор Start не создаёт дубликатов.
6. Reader event и checkpoint остаются атомарными.
7. Reconciliation автоматически восстанавливается.
8. Schema v2 и её exact signature не изменены.
9. Все targeted и regression tests проходят без новых failures.
10. Исправление представляет собой точечный patch без несвязанных изменений.

## 14. Production acceptance после отдельного deployment

Deployment не входит в эту задачу, но кодер должен подготовить критерии последующей проверки.

Минимальное окно наблюдения после deployment:

- не менее одного реального периода посещений;
- желательно не менее 50 успешных Start submissions либо 24 часа, что наступит позже.

Acceptance:

- `visit.storage_error{stage="start", storage_category="busy"}=0`;
- `visit.reader_scan_failed` из-за BUSY = 0 либо каждый случай явно recovered без checkpoint gap;
- `visit.reconciliation_degraded` из-за BUSY = 0 либо каждый случай явно recovered;
- нет `visit.runtime_unavailable`;
- Reader не отстаёт от active journal сверх штатного scan interval/batch delay;
- количество `visit.opened + visit.start_reused` согласуется с успешно принятыми Start submissions;
- authorization rows не теряются и не дублируются;
- `PRAGMA quick_check=ok`;
- exact schema v2 signature сохранена.

