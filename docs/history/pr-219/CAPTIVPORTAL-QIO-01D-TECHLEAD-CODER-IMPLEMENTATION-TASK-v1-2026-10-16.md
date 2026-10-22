# CaptivPortal — QIO-01D — Tech Lead → Coder Implementation TASK v1

**Состояние:** `LAB_CODER_GO` только на перечисленную реализацию; `GITHUB_COMMIT/PUSH/PR=NO`, `PRODUCTION_CHANGE=NO`, `COMPACT_PRODUCTION_ACTIVATION=HOLD`.  
**Дата:** 2026-10-16 (Asia/Baku).  
**Основания:** Chief Architect `CAPTIVPORTAL-QIO-01D-CHIEF-ARCHITECT-ADMISSION-CONTRACT-v1-FINAL-2026-10-16(1).md`, Tech Lead Next Steps `CAPTIVPORTAL-QIO-01D-QIO-02-TECHLEAD-NEXT-STEPS-2026-10-16.md`, `CAPTIVPORTAL-QIO-01D-TECHLEAD-ARCHITECTURE-REVIEW-2026-10-16.md`.  
**Текущий проверенный production/main baseline при подготовке:** QIO-01B merge `e2cbd96916d8a81f07f0d79a1a745f593ccb5114`, tree `8c95448250d75b01580bfdd4c52a40cf71a288af`. Перед началом **проверить свежий main на GitHub** и отсутствие новых merge/overlap; если новый main — STOP и запросить rebase/base admission у Tech Lead. **Никакого переписывания работающего production checkout.**

## 1. Цель и архитектурный смысл

Снизить повторные операционные INFO events `visit.reader_scan_completed` во время подтверждённо неизменных healthy empty сканов Visit Lifecycle reader **только при opt-in**, с ограниченным heartbeat. **Не уменьшать количество самих сканов, SQLite writes, retries или source checkpoints.** Не утверждать физическую HDD экономию по количеству сообщений.

Допустимый способ один: узкое in-memory состояние внутри существующего `VisitLifecycleWebhookReader`, monotonic clock, 60s, без новых threads/timers, базы, spool, global logging middleware или API. Согласование архитектуры не разрешает соседние изменения QIO-02.

## 2. File allowlist — заморожен

Production code, только перечисленные пути:

1. `app/visit_lifecycle/webhook_reader.py`: классификация completed scan + in-memory compactor, с прежним scan workflow/return/health.
2. `app/visit_lifecycle/config.py`: strict startup bool validation and forwarding.
3. `app/visit_lifecycle/models.py`: одно поле в `VisitLifecycleConfig`, обратная совместимость конструкторов/default OFF.
4. `app/config.py`: строго типизированный env flag, `default=false`.
5. `app/settings.py`: передача setting через существующий `get_settings()`.

Документация/конфигурация:

6. `.env.example`: единственный example для нового env.
7. `docs/logging.md`: legacy vs compact semantics, schema v2 and observers.
8. `docs/modules/visit-lifecycle.md`: activation, source invariants, rollback, monitor thresholds.

Tests, строго в `tests/visit_lifecycle/`: существующие `test_webhook_reader.py`, `test_config.py`, `test_runtime.py`; разрешено добавить **один** новый файл `test_reader_scan_telemetry_compact.py` для deterministic matrix. Если тесты общего settings startup/wiring не покрываются без дополнительного пути, **не менять неожиданные файлы**, вернуть scope request.

Consumer migration: отдельный review-документ LogQL в handoff (вне checkout), **никаких live Grafana edits**. Если Coder считает обязательным добавить в repo внешний migration artifact — запросить добавление exact path заранее.

**Forbidden:** `run.py`, `app/visit_lifecycle/service.py`/repository/coordinator/storage/migrations, Auth/Omada/client control, NI-04, `app/settings_control` writable/permissions, systemd, Grafana/Loki/Alloy/Promtail config, production dashboard, monitoring infra, generic telemetry handlers, SQLite PRAGMA/checkpoints/durability. Никаких изменений вне allowlist без нового Tech Lead GO.

## 3. Startup flag и режим OFF

`VISIT_LIFECYCLE_READER_SCAN_TELEMETRY_COMPACT_ENABLED`: точно `true|false` (обработать установленным strict boolean parser), default **false**, startup only. Маршрут: `app/config.py` → `app/settings.py:get_settings()` → `visit_config_from_settings()` → `VisitLifecycleConfig` → reader. Никаких чтений `os.environ` в reader и hot updates; без Admin-writable.

На OFF воспроизвести **текущую эмиссию один event на каждый безисключительный completed `scan_once`**, включая `scan_complete=false`, со старым именем/полями/level, без v2 additions. `health_callback` и возвращаемый bool прежние; disabled VisitLifecycle ничего не запускает.

## 4. Условия suppressible и немедленных reports

Допустимо suppress **только** повторный scan, для которого ВСЕ условия истинны: нет exception, complete=true, processed=0, нет committed `retry_pending` progress, reset/reappearance/missing/retired/checkpoint/invalid/error/warning/source-state transitions, scan не stopping/deferred, нет переходов initial→active, failure/incomplete/deferred→recovery или active→idle. **Если точную классификацию провести нельзя, консервативно emit**, а не подавлять.

Немедленно emit тот же `visit.reader_scan_completed` для:

- первого successful completed scan после reader start: `initial`;
- любого processed>0: `activity`;
- любого incomplete: `incomplete`;
- `retry_pending` committed progress при processed=0: `progress`;
- любого source identity/checkpoint/retired/missing/restarted change при processed=0: `source_change`;
- первого successful complete после error, incomplete или expected deferral: `recovery` (если всё ещё partial — `incomplete`);
- первого complete empty после activity: `idle_transition`;
- healthy unchanged quiet empty при наступлении heartbeat boundary: `heartbeat`.

Все `visit.reader_scan_failed`, `visit.reader_scan_deferred`, `visit.reader_source_missing`, `visit.reader_source_restarted`, `visit.offline_invalid`, recovery/error/warnings сохраняют исходную частоту/payload/level; **не оборачивать** ошибки в success и не подавлять их. Обязательные side effects `_discover_sources`, `_process_source`, `_reconcile_missing`, `retry_pending(on_committed_progress)`, offsets/checkpoints, reader states/SQLite calls продолжаются идентично. Для source-transition detection использовать **только уже известные локальные сигналы** и флаги при существующих side effects, не делать дополнительный DB query/transaction и не подменять предупреждения. `retry_pending` callback уже существует; сохранить его вызовы и порядок.

**Priority:** failures/deferrals separate → incomplete → activity/progress/source-change → recovery/transition → heartbeat or quiet suppress. На границе неоднозначности — emit.

## 5. Clock, event schema, counters

`QUIET_SCAN_HEARTBEAT_SECONDS=60.0`, `self._monotonic()` и первый следующий здоровый completed scan при `now-last_completed_report >=60.0`. Clock regression/invalid delta должен дать безопасный немедленный report либо fail-safe bounded state, но никогда вечное suppression. При 5s scan cadence и 20s budget это **не** обещание durable delivery ≤60s; возможна задержка до ~85s+OS jitter.

ON reports сохраняют старые текущие `processed_line_count`, `scan_complete`, `duration_ms` и добавляют:

- `reader_report_schema_version`: integer `2`;
- `report_reason`: строго `initial|activity|incomplete|progress|source_change|recovery|idle_transition|heartbeat`;
- `suppressed_empty_scans`: integer `>=0`, количество предыдущих подавленных healthy scans;
- `scans_represented`: integer, **всегда `suppressed_empty_scans+1`**, без failed/deferred или ещё не завершённого текущего scan.

Counter state — in-memory best effort; crash может потерять непубликованные suppressed counts. Reset после attempted completed-report, **не** выдавать durability/confirmed Loki delivery. При emitter fail-open не влиять на return/callback; прерывание telemetry должно быть не хуже прежнего. Не вводить MAC/IP/token/raw payload в дополнительные поля.

## 6. Узкие tests — зона Coder (не full suite)

Coder запускает только focused tests по change scope: `tests/visit_lifecycle/test_webhook_reader.py`, `test_config.py`, `test_runtime.py`, новый compact test; при необходимости из существующих `tests/visit_lifecycle/test_writer_contention.py`, `test_webhook_finalization.py` только относящиеся кейсы. Сохранить прежние tests/assertions и негативные сценарии.

Минимум deterministic matrix: OFF original event count/fields; default false и недопустимые env; true/false; injected frozen monotonic (0,5,59.999,60,61); first success; activity→idle; incomplete→complete; expected deferral→recovery; error→recovery; missing/restarted/source reused/checkpoint transition; committed retry progress with zero lines; invalid journal even when zero outcomes; non-empty always immediate; repeated 5s quiet scans; 20s scan duration and monotonic boundary; stopped/no fabricated heartbeat; restart resets counters; emit unavailable; no extra DB operations; identical return/health/callback/Visit rows/checkpoints and ordering for OFF/ON.

**Обязательный ownership пункт:** **Coder НЕ запускает full Windows/Linux project regressions и не выдаёт за них результат. Все полные Windows/Linux/SQLite/lifecycle/security/PERF gates проводит сам Tech Lead независимо после handoff. Отдельной роли QA не существует.** Coder не добавляет skip/xfail, не удаляет assertions и не изменяет environment для обхода tests.

## 7. Handoff и STOP

Нужно предоставить: precise BASE HEAD/tree and actual GitHub main at start; changed allowlist files; new candidate tree via safe external index or clean Lab; full replacement patch + SHA256 bytes; focused test IDs and raw JUnit/log, commands (Linux/Windows если available), compileall/diff-check; event examples ON/OFF; migration query plan; negative test proof; no secrets. Status `COMMIT=NO`, `PUSH=NO`, `PR=NO`, `MERGE=NO`, `DEPLOY=NO`, `LIVE_GRAFANA_EDIT=NO`.

**STOP немедленно:** newer main merge conflicts, need for `service.py`/repository/`run.py`/systemd change, lost source signal, uncertain zero-line durable progress, failed negative test, inability to preserve legacy OFF, unknown post-scan telemetry fields or consumer incompatibility. Запросить Tech Lead rather than widen scope.

## 8. Subsequent ownership — Tech Lead / Owner, не Coder

Tech Lead independently reproduces exact candidate patch/tree and conducts full Windows/Linux, Visit/Auth integration, root/security if affected, PERFORMANCE quiet Lab gates and correctness review. **Ни одна «зелёная» строка Coder handoff не заменяет это.** Только после PASS: permission for Coder commit/push/Draft PR; Owner merge GO separate.

**Production compact activation HOLD even after merge.** Current deployed dashboard UID `captive-portal-auth-v3-fixed`, version 65, panel 138 uses `count_over_time(... | event="visit.reader_scan_completed" ...)`, which would undercount scans. First obtain approved Grafana/Loki mixed legacy+v2 query validation, alert thresholds/compatibility, external consumers reconciliation and **separate Owner activation GO**. Keep flag absent/OFF at initial deploy. Rollback: approved flag `false` and controlled restart only, without DB rollback or offset mutation.

### Machine status

```ini
TASK=QIO-01D
IMPLEMENTATION_PATH=ONE_PATH_IN_MEMORY_COMPACTOR
CODER_LAB_GO=YES
CODER_TESTS=FOCUSED_ONLY
FULL_WINDOWS_LINUX_PERF_GATES=TECH_LEAD_ONLY
EXTERNAL_QA_ROLE=NONE
COMPACT_DEFAULT=false
PRODUCTION_COMPACT_ACTIVATION=HOLD
GITHUB_PUBLICATION=HOLD_UNTIL_TECH_LEAD_ACCEPTANCE
SOURCE_SCOPE_EXPANSION=STOP_AND_ASK
```
