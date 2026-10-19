# CAPTIVPORTAL — QIO-01D
## Chief Architect Architecture Admission Contract v1 FINAL
### Visit Lifecycle reader: compact successful empty-scan operational telemetry

**Дата:** 2026-10-16 (Asia/Baku)  
**Инициатор:** Tech Lead / QIO-01D  
**Адресат:** тот же CaptivPortal Tech Lead → scoped Coder TASK после собственного pre-code review  
**Вердикт:** **`MODIFY → ARCHITECTURE_PASS`**, реализация разрешается только через отдельный Tech Lead TASK; никаких production действий  
**Взаимосвязь:** QIO-01A journaling root cause; QIO-02 продолжает **read-only** атрибуцию и не включается в scope QIO-01D.

## 0. Evidence и ограничения review

1. В запросе Tech Lead приведена read-only выборка: **346** `visit.reader_scan_completed`, из них **339** с `processed_line_count=0`, все `scan_complete=true`. Это результаты **отчёта Tech Lead**, а не независимый подсчёт Chief Architect на живом production.
2. GitHub, актуальный доступный `app/visit_lifecycle/webhook_reader.py`: `scan_once()` после `_discover_sources()`, обработки файлов, `_reconcile_missing()` и `service.retry_pending()` вызывает `telemetry.emit("visit.reader_scan_completed", processed_line_count=processed, scan_complete=complete, duration_ms=...)`; `_run` спит через `scan_interval_seconds`. Доступный config задаёт **5 s** по умолчанию, scan-time budget **20 s**. Базовое содержимое `app/visit_lifecycle/telemetry.py` направляет технические события в AuthTelemetry/Loki-пайплайн либо fail-open logger.
3. В предоставленном ранее dashboard-артефакте `CaptivePortal_Grafana_AP24_Evidence_Health_v60(1).json` панель **«Активность journal reader» (panel ID 138)** использует `count_over_time(... | json | event="visit.reader_scan_completed" ...)`. Это **доказательство существования такого запроса в указанном JSON**, не доказательство, что именно эта версия сейчас активна в Grafana или что других внешних consumers нет.
4. Документ, названный в обращении `CAPTIVPORTAL-QIO-01D-QIO-02-TECHLEAD-NEXT-STEPS-2026-10-16.md`, **не обнаружен среди доступных вложений и Project files** на момент review. Поэтому принят только явно переданный предмет запроса; предполагаемое содержание этого документа не приписывается ему. Перед Coder GO Tech Lead приобщает оригинал к evidence pack и сверяет отсутствие конфликта.
5. **Важная семантика:** `processed_line_count=0` **не равно** «не было работы». Тот же `scan_once()` может подтвердить durable progress в `retry_pending()`, зарегистрировать пропавший/вернувшийся source, изменить reader source state или сообщить предупреждение, при этом число строк остаётся нулевым. Не трактовать `scan_complete=true` как внешнюю end-to-end availability Omada или гарантированно пустую БД.

## 1. Решение и изменяемая граница

**Разрешено:** менять **только частоту репортинга повторяющегося, подтверждённо неизменного, successful complete empty scan** в `VisitLifecycleWebhookReader` при сохранении самого сканирования, его return value, callback, source progress и иных событий.

**Не разрешено:** изменять расписание scan/reconcile, source discovery/rotation, parsing/validation, bytes/lines/time budgets, checkpoints/offsets, `retry_pending`, retry/backoff, Coordinator, Visit Auth/Close, SQLite transaction/durability/PRAGMA, `logging.INFO` целиком, общую AuthTelemetry схему, Loki pipeline, глобальный logging filter, фоновые процессы или отдельную БД для счетчиков.

**Предпочтительный delivery:** узкая in-memory reporting state внутри существующего reader; без I/O, новых потоков/таймеров и durable counters. Никаких DB-записей ради агрегирования логов. Текущая функция `scan_once()` возвращает **тот же** `bool`; `health_callback(True/False)` вызывается с прежними условиями независимо от того, emitted ли информационный event.

## 2. QD-A01 — Startup-only обратимая активация

**Нормативное решение:** compact reporting является отдельным строго типизированным **startup-only opt-in** (`VISIT_LIFECYCLE_READER_SCAN_TELEMETRY_COMPACT_ENABLED`, допустимые значения `true|false`; default **`false`**). Парсинг через **существующий** `app/config.py` → `app/settings.py` → `visit_config_from_settings` → `VisitLifecycleConfig`, без отдельных direct `os.environ` reads внутри reader, без Admin-writable Settings, hot reload или нового Settings Store. Отсутствие переменной воспроизводит старую эмиссию каждого `scan_once()` byte-/field-semantically, кроме разрешённых test fixture изменений. Disabled Visit Lifecycle остаётся disabled и не начинает I/O.

Для минимизации scope Tech Lead фиксирует точный список затронутых config/model/source файлов до Coder GO. Если требуется иной config route, вернуть на architecture review, а не обходить config ownership.

Режим OFF — исходное поведение; режим ON — правила ниже. Toggle меняет только telemetry, никогда данные или авторизацию. Production activation — отдельный Owner/SysAdmin change после обновления/проверки потребителей, с контролируемым restart по действующему operational контракту; merge сам по себе ничего не активирует.

## 3. QD-A02 — Классы результатов и обязательная немедленная эмиссия

**Pure, healthy, unchanged empty scan** (единственный разрешённый класс подавления) должен одновременно удовлетворять:

- `scan_once()` завершился без exception и **`scan_complete is True`**;
- `processed_line_count == 0`;
- `retry_pending` не подтвердил **никакой** committed/durable progress в этом проходе;
- не произошло распознанного source-identity/checkpoint lifecycle transition, reappearance, truncation, `reader_source_missing`, `reader_source_restarted`, skipped/invalid input или иного warning/error/source-state transition; не вводить дополнительный SQLite read ради определения этого факта;
- не было смены локального состояния reader (`initial`, `recovering`, `partial`/`degraded`, `active` → `idle`) с последнего отчёта;
- scanner не находится в stopping/deferral/error episode. Принять существующие in-memory сигналы, не подменять их догадкой по нулю обработанных строк.

**Немедленные события — без debounce/throttle:**

| Случай | Требование |
|---|---|
| `processed_line_count > 0` | `visit.reader_scan_completed` на **каждом** таком проходе, со старыми результатами/полями |
| `scan_complete=false` | `visit.reader_scan_completed` **каждый раз**, даже при нуле; никакой подмены на успешный heartbeat |
| Durable `retry_pending` progress при `processed=0` | немедленный completed-report, отдельный `report_reason=progress` |
| Source reset/reappearance/missing/checkpoint transition, invalid record warning | исходные `visit.reader_source_restarted`, `visit.reader_source_missing`, `visit.offline_invalid` и прочие предупреждения **немедленно и без изменений**; при распознанной source-state mutation — completed-report без задержки |
| Любой exception/failure | исходный `visit.reader_scan_failed` без изменений; никогда не скрывать под heartbeat |
| Expected writer deferral / starvation | `visit.reader_scan_deferred` и escalated `visit.reader_scan_failed` с прежней частотой, полями и threshold; не снижать их в QIO-01D |
| Первый completed scan после reader start/restart | немедленно, даже если empty |
| Первый completed scan после failure, deferred, incomplete | немедленно с `report_reason=recovery` (или `incomplete` если всё ещё partial); не объявлять recovery до фактического завершения успешного прохода |
| Первая полностью пустая фаза после activity | немедленно обозначить переход `active→idle`, затем разрешить compact heartbeat |
| Stop / exception на shutdown | прежнее поведение; не создавать фиктивный successful report и не блокировать shutdown попыткой flush |

**Порядок приоритетов:** error/deferred не проходят через success-compactor; для success: incomplete → activity/progress/source change → recovery/state transition → heartbeat/quiet suppression. Обязательные событийные классы никогда не теряются ради оптимизации. Все вызовы оригинальных `VisitTelemetry.emit` с security/error-level параметрами сохраняются.

## 4. QD-A03 — Heartbeat bound и freshness

**Константа:** `QUIET_SCAN_HEARTBEAT_SECONDS = 60.0`, через injected `monotonic()`; не wall-clock timestamp и не отдельная background задача.

- При здоровых quiet-сканированиях **первый successful complete scan**, завершённый при `monotonic_now - last_completed_report_monotonic >= 60.0`, обязан попытаться опубликовать heartbeat. В промежутке identical quiet scans только увеличивают in-memory агрегат. При `>=60s` **нельзя** ждать следующего содержательного события.
- Неполный/ошибочный проход не излучает ложный heartbeat. Если процесс вообще не исполняет scan, heartbeat естественно отсутствует; это основание для отдельного `stale telemetry`, а не доказательство healthy reader.
- **60s — бюджет проверки на следующем scan, не строгая гарантия доставки в Loki точно через 60s.** При штатном `scan_interval=5s`, `reader_max_duration=20s` верхняя ориентировочная задержка попытки репорта при непрерывно работающем reader — до `60+5+20=85s` плюс ОС scheduler jitter. При изменённой cadence bound пересчитать; этот TASK её **не меняет**. Если Tech Lead требует абсолютный <=60s SLA при зависшем reader, текущая in-process схема этого не гарантирует; нужно новое отдельное архитектурное решение.
- **Freshness мониторинг:** отсутствие событий успешного `visit.reader_scan_completed` более **120s** при включённом reader и штатных 5s/20s → пометка *telemetry stale / needs investigation*; более **180s** → alert/escalation *telemetry unavailable/unknown*. Эти пороги относятся **только к наблюдаемости**, не изменяют app source-health, Auth или Visit decisions. Для нестандартной cadence Tech Lead обязан установить соответствующий мониторинговый бюджет не меньше `60 + scan_interval + max_duration + jitter margin`.
- При логировании через fail-open `VisitTelemetry.emit` нельзя гарантировать durable delivery или дублировать авторитетные facts через log. Строгий freshness gate никогда не основывается только на наличии heartbeat. Не заявлять, что `emit(...) == True` доказывает доставку в Loki.
- Нет таймера, который пишет, пока scan failure, reader stopping или процесс stopped. Silence сам по себе не «успех».

## 5. QD-A04 — Event contract v2, backward-mode и учёт агрегатов

**На compact=OFF** сохраняется прежняя семантика: ровно один `visit.reader_scan_completed` на каждый безисключительный scan, в том числе при `scan_complete=false`, поля `processed_line_count`, `scan_complete`, `duration_ms` по прежним значениям. Новых полей не требуется.

**На compact=ON** сохраняется имя события **`visit.reader_scan_completed`** и существующие поля, но добавляются безопасные скалярные поля:

| Поле | Тип | Семантика |
|---|---|---|
| `reader_report_schema_version` | integer | **2**, чтобы потребители явно отличали compact stream от legacy |
| `report_reason` | string enum | `initial`, `activity`, `incomplete`, `progress`, `source_change`, `recovery`, `idle_transition`, `heartbeat` |
| `scans_represented` | integer >=1 | **1 текущий завершённый scan + число предшествующих suppressed quiet complete scans** с предыдущего successfully attempted completed-report в этом процессе; не включает failed/deferred вызовы |
| `suppressed_empty_scans` | integer >=0 | Число ранее suppressed quiet complete scans в данном report; **`scans_represented = suppressed_empty_scans + 1`** |

Базовые поля `processed_line_count`, `scan_complete`, `duration_ms` описывают **только текущий** scan, а не сумму, среднее или максимум за окно. При heartbeat они равны `0`, `true`, duration текущего прохода. Не присваивать `duration_ms` агрегированную длительность. `scans_represented`/`suppressed_empty_scans` — **best-effort operational counters** в процессе; после crash/restart могут потеряться ещё не опубликованные quiet counts; не считать их authoritative proof числа durable scans.

Никаких MAC, client IP, cookies, token, raw journal или payload в новых полях. Не менять `event`, `component=visit_lifecycle`, уровень INFO для healthy completed и JSON-обёртку AuthTelemetry. Не менять уровни и payload существующих error/warning/deferred/source events.

**Два различия обязательны для всех consumers:**

1. `count_over_time(visit.reader_scan_completed)` в compact=ON считает **emitted reports**, больше **не** `scan_once` attempts. Количество completed scans измеряется через суммирование `scans_represented` для v2; legacy reports (без v2) считаются по одному. Никаких ложных сравнений частоты scans до/после.
2. Отсутствие нового report между heartbeats не свидетельствует об отсутствии `scan_once`; пропуск heartbeat не доказывает fail без диагностики состояния сервиса, доставки логов и scan freshness.

Пример v2 heartbeat payload полей (логическая форма, без выдуманной envelope):

```json
{
  "event": "visit.reader_scan_completed",
  "processed_line_count": 0,
  "scan_complete": true,
  "duration_ms": 2,
  "reader_report_schema_version": 2,
  "report_reason": "heartbeat",
  "scans_represented": 12,
  "suppressed_empty_scans": 11
}
```

Это только пример чисел; реальные значения выводит scanner. **Вмешательство в формат другого события/авторизации запрещено.**

## 6. QD-A05 — Grafana/Loki и другие consumers

В доступном dashboard JSON существует `panel 138 / «Активность journal reader»`, в котором success series вычисляется через Loki `count_over_time(... | event="visit.reader_scan_completed")`. При compact=ON существующий запрос начинает **недосчитывать** scans. **Нельзя включать compact=ON в production до принятой миграции consumer.**

Требуется Tech Lead / observability owner:

1. Read-only сверить **актуально развернутую** Grafana dashboard/panel/alerts и Loki LogQL queries по точному `event`, `processed_line_count`, `scan_complete`, `duration_ms`. Проверить alerts, recording rules, внешние API и любые разборщики (`file`, journald, Alloy/Promtail). Repo-search единственной эмиссии **не доказывает** отсутствия внешних consumers.
2. Подготовить и на disposable/query Lab **испытать** совместимый query plan для двух периодов: legacy event без `reader_report_schema_version` даёт weight 1; compact v2 даёт weight `scans_represented`. Отдельно показывать *reported events*, *represented successful/partial scans*, *activity* (`processed_line_count>0`), *incomplete/fail/deferred*, *last event age*. **Не** менять смысл одной легенды без rename/annotated transition.
3. Проверить смешанный интервал временного ряда при включении и последующем rollback compact (в том числе логи из двух процессов), non-numeric/absent fields, отсутствие неожиданного Loki `__error__`. Примерные LogQL идеи не считать доказанными без выполнения на реально установленной версии Loki.
4. Подтвердить совместимость существующих error/deferral/health alert expressions. Честно указать **semantic compatibility change** `count_over_time` для old clients; если обнаружен критический consumer, который нельзя обновить, **compact activation HOLD** (код может быть merge с default OFF).
5. Grafana dashboard update — отдельный контролируемый consumer rollout/Owner approval; **не** подменять конфигурацию текущего dashboard без разрешения. В release notes явно указать `reader_report_schema_version=2`, новый способ count и rollout порядок (consumer first, app flag second).

## 7. QD-A06 — Correctness invariants и testing

**Инварианты C01…C12:**

- **C01**: `scan_once()` возвращает идентичный `bool` для каждого входного состояния при compact OFF/ON.
- **C02**: идентичны число и порядок вызовов `_discover_sources`, `_process_source`, `_reconcile_missing`, `retry_pending`, source checkpoint verification/commit, pending callbacks, writer coordinator и shutdown/wakeup.
- **C03**: идентичны durable SQLite rows, offsets, file generations, retries, Visit open/close facts, idempotency, `VisitStorageError` handling и transaction durability. Ни единой дополнительной/снятой SQLite операции ради telemetry.
- **C04**: `health_callback(True/False)` и runtime healthy/degraded одинаковы при OFF/ON; heartbeat не authority.
- **C05**: on OFF старые completion events с прежними условиями и полями, без изменения частоты.
- **C06**: on ON подавляются только повторные full, successful, **truly idle**, unchanged empty scans; активность, pending committed progress, source changes и incomplete reports немедленно.
- **C07**: error, deferred, starvation escalation, source warning, invalid/corruption, recovery не теряются и не снижаются ни в payload, ни в severity, ни по частоте; не подавлять `scan_complete=false`.
- **C08**: heartbeat clock `monotonic`, bounded on next healthy scan, first report after start/recovery/transition immediate; процессные остановки не генерируют фиктивных success.
- **C09**: counter accounting корректно при intermittent activity, long quiet, failure→recovery, source change, clock boundary `59.999/60.000`, длительных сканах; crash-loss counts не объявлены authoritative.
- **C10**: single existing reader thread; no extra thread, timer, SQLite, import cycle, blocking log flush, lock contention или Auth degradation. Telemetry remains fail-open.
- **C11**: no privacy/security regression; output только primitive safe fields и штатная JSON envelope.
- **C12**: эквивалентность существующего Grafana legacy/v2 mixed-history query проверена фактическим Loki Lab; activation cannot precede consumer readiness.

**Минимальная тестовая матрица Tech Lead:** frozen monotonic + fake telemetry; 0/5/59.999/60/61 sec; success→idle, activity→idle, fail→recovery, deferred→recovery, incomplete→complete, pending progress with zero lines, source missing/restarted, invalid journal, restart resets counters; logs unavailable/emit exception; 5s cadence and long duration; original regressions `tests/visit_lifecycle/test_webhook_reader.py`, `test_runtime.py`, `test_writer_contention.py`, `test_webhook_finalization.py`, Auth/Visit integration and full/PERF gates.

**Performance gate:** independent matched quiet Lab/production **read-only** measurement of producer emitted INFO events/sec and bytes/sec, auth_telemetry file writes, journald writes, and **host completed HDD IOPS**; do not infer host disk savings from 339/346 messages. Verify auth latency and lossless source processing unaffected. Production post-deploy measurement only after Owner admission.

## 8. Implementation/release boundary и rollback

**Allowlist proposed** (Tech Lead freezes exact paths in TASK; changes only when necessary for startup config and reader telemetry):

- `app/visit_lifecycle/webhook_reader.py` (only decision/reporting state),
- `app/visit_lifecycle/config.py`, `app/visit_lifecycle/models.py`, `app/config.py`, `app/settings.py` (only new startup-only flag wiring),
- `.env.example`, `docs/logging.md`, `docs/modules/visit-lifecycle.md` (contract, migration, operational diagnostics),
- corresponding narrowly scoped tests and a reviewed dashboard query/migration **artifact** (no live Grafana mutation).

**Excluded:** `app/visit_lifecycle/service.py`, `repository.py`, coordinator/Journal/Omada, core Auth/`run.py`, SQLite migrations, systemd, NI, settings UI, global logging handlers/Alloy/Promtail, existing production Grafana dashboard without separately approved change.

**Rollback A (preferred, no source revert):** set startup `VISIT_LIFECYCLE_READER_SCAN_TELEMETRY_COMPACT_ENABLED=false` through approved environment configuration; Owner-authorized controlled restart → old per-scan event emission. Existing Visit/SQLite/replay unchanged. Confirm actual loaded artifact, no event-v2 fields when OFF, previous Loki query resumes per-scan counts. No database rewind and no reprocessing/replay reset.

**Rollback B:** revert/change to last accepted exact repo TREE only through standard reviewed deployment/Owner process if bug persists with OFF; no emergency unreviewed production editing. Alerts/dashboard must handle periods with both legacy and v2 data.

**Implementation sequence:** Tech Lead obtains missing Next-Steps artifact and current consumer inventory; creates narrow TASK with frozen files, tests and expected initial/heartbeat/counter contracts → Coder implementation in Lab → independent Tech Lead functional + exact TREE QA/full/PERF + current release gate → Owner-controlled PR/merge → consumer dashboard/alerts verified → separate Owner-authorized opt-in activation → matched measurements and rollback readiness.

### Machine disposition

```text
TASK=QIO-01D
ARCHITECT_VERDICT=MODIFY_APPROVE
ARCHITECTURE_ADMISSION=PASS
CHANGE_CLASS=OPTIONAL_OPERATIONAL_TELEMETRY_ONLY
DEFAULT_COMPACT_ENABLED=false
HEARTBEAT_THRESHOLD_SECONDS=60
HEARTBEAT_TRIGGER=NEXT_SUCCESSFUL_COMPLETE_SCAN
INITIAL_ACTIVITY_PARTIAL_ERROR_RECOVERY=IMMEDIATE
SOURCE_CHECKPOINT_SQLITE_RETRY_CHANGE=NO
EXTERNAL_GRAFANA_QUERY_MIGRATION=REQUIRED_BEFORE_ACTIVATION
SUPPORTING_NEXT_STEPS_ATTACHMENT=NOT_AVAILABLE_AT_REVIEW
TECH_LEAD_CODER_TASK_PREPARATION=YES
CODER_GO=HOLD_UNTIL_TECH_LEAD_TASK_AND_G0
FULL_PERF_QA=TECH_LEAD_OWNED
QIO_02=READ_ONLY_ATTRIBUTION_IN_PROGRESS
PRODUCTION_CHANGES=NO
OWNER_MERGE=SEPARATE
OWNER_ACTIVATION=SEPARATE
```

**End of QIO-01D Chief Architect Architecture Admission Contract v1.**
