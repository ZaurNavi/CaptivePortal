# CAPTIVPORTAL — QIO-01A / ARCHITECTURE DISPOSITION A1–A4 v1.0

**Дата:** 2026-10-15 (Asia/Baku)  
**От:** Performance & Optimization Architect  
**Кому:** Technical Lead — Performance Optimization  
**Основание:** `CAPTIVPORTAL-QIO-01A-TECHLEAD-TO-ARCHITECT-SINGLE-RETURN-v2.0-2026-10-15.md` и QIO-01 Architecture Handoff v1.0.  
**Статус:** **ARCHITECTURE DISPOSITION APPROVED — TECH LEAD MAY PREPARE EXACT QIO-01A CODER TASK**. Это **не** разрешение деплоить в production.  
**Owner clarification:** PRTG — отдельный SNMP/системный мониторинг; по заявлению Owner, зависимостей от CaptivPortal и `fingerprint.integration_worker_health` в PRTG нет.

## 0. Принятые факты и границы

Согласен с наблюдением Tech Lead: `IntegrationWorker.run_once()` возвращает `False` и при `consumer_lock` miss, и при нормальном lock-owned idle. Нынешний `run()` публикует `ready` после обоих исходов, если исключения нет. Это дефект **семантики health**, который следует устранить локально одновременно с сокращением повторов `ready`.

За 100 секунд исследования обнаружены 100 одинаковых `fingerprint.integration_worker_health` / `ready` среди 535 записей нового journald-потока. Это потенциально устранимая доля log records, **не** обещание соответствующего снижения физического HDD IOPS.

Tech Lead подтвердил идентичность blob `worker.py`, `runtime.py`, `submitter.py` между проверенными GitHub `7e84bc563f1b6dd3d72da66ae25849d9a7d96540` и production checkout `84b80376b13002d435be28eec98b91b9cbf71c63`. **Loaded-artifact identity долгоживущего процесса остаётся непроверенной**; не заменять этим фактом deploy gate.

## A1 — точная семантика lock-owned readiness: **APPROVED**

1. **`ready` подтверждается только тогда, когда конкретная итерация `run_once()` действительно приобрела `consumer_lock` и завершила bounded цикл без необработанного исключения.** Lock-owned idle с отсутствием due jobs — полноценный successful ready-cycle. Значение activity-boolean не является доказательством ready.
2. **Lock miss никогда не подтверждает `ready`.** После первого miss состояние данного worker считается **`consumer_lock_unavailable`**, а не успешным ready и не обязательно глобальной недоступностью всего pipeline. Публиковать немедленно `fingerprint.integration_worker_health` с `reason_code="consumer_lock_unavailable"`. При повторных miss — публиковать этот non-ready сигнал каждый раз без ограничения частоты в v1 (см. A4). Нельзя интерпретировать его как доказательство, что другой законный владелец lock не обрабатывает очередь.
3. Если ранее был `ready`, уже **первый** miss прекращает ready-серию; оставлять прошлый `ready` активным на основании предшествующего success запрещено. После возвращения владения lock и успешного bounded цикла **немедленно** публиковать `ready` как восстановление.
4. Необработанный infrastructure failure при выполнении worker/cycle → немедленный `reason_code="integration_unavailable"` на каждой неуспешной итерации, как в существующем коде. Не сводить lock miss и infrastructure failure к одному состоянию.
5. **Доменные outcomes — отдельная плоскость:** `classification_retry`, `classification_no_result`, `lease_lost` и identity-resolution outcomes по-прежнему публикуются согласно существующим правилам и не подменяются глобальным статусом worker. Обработанный и durably завершённый доменный retry/no-result **сам по себе** не переводит worker в `integration_unavailable`; если цикл lock-owned и bounded завершён без необработанного failure, worker health может быть `ready`. `lease_lost` остаётся немедленным предупреждающим событием; его существующую domain semantics не менять этим TASK.
6. **Сохранить внешний контракт `run_once() -> bool`:** `False` означает «не было обработанной работы» **либо** «lock не приобретён», как сейчас. Для health использовать приватный per-iteration outcome (например, `OWNED_COMPLETED`, `LOCK_MISSED`, `UNHANDLED_FAILURE`) или приватный эквивалент; Tech Lead выбирает техническую форму, Coder не меняет публичный return/API. Маркер устанавливается только для текущей итерации, сбрасывается перед каждой новой, в том числе перед исключениями, чтобы прошлый success не мог породить ложный ready. Исключить гонки и загрязнение результата при прямых тестовых вызовах `run_once()`.
7. **Не вводить** второй worker, внешнюю очередь, новый durable health-state, новую таблицу, fsync, lock upgrade/replacement, дополнительную постоянную БД или изменение claim/lease/retry/identity алгоритмов.

### Health-state transition table

| Текущий/предыдущий статус | Результат текущего цикла | `fingerprint.integration_worker_health` |
|---|---|---|
| startup / unknown | lock-owned success, включая idle | `ready` **сразу** |
| steady ready | очередной lock-owned success до heartbeat deadline | ничего |
| steady ready | lock-owned success при `monotonic_elapsed >= 60 s` | `ready` heartbeat |
| любой | lock miss | `consumer_lock_unavailable` **сразу, на каждом miss** |
| любой | необработанный infrastructure failure | `integration_unavailable` **сразу, на каждом failure** |
| non-ready | новый lock-owned success | `ready` **сразу**, заново запустить 60s цикл |
| stop / crash | нет нового успешного bounded цикла | **никогда не создавать искусственный `ready`** |

Новый код `consumer_lock_unavailable` — **диагностическая не-готовность данного worker**, а не самостоятельное доказательство P0 всей подсистемы.

## A2 — heartbeat, staleness, PRTG: **APPROVED WITH RECORDED OWNER SCOPE**

1. **Фиксировать `READY_HEARTBEAT_MAX_INTERVAL_SECONDS = 60` для QIO-01A v1.** Интервал относится **только к успешному, неизменному lock-owned ready**. Внутри worker использовать `time.monotonic()` или injected monotonic test clock, условие `elapsed >= 60`, и публиковать heartbeat при ближайшем завершённом успешном цикле. Не прерывать работу job ради принудительного heartbeat. Реальный интервал может превысить 60s при долгом цикле, остановке, ошибке или перегрузке — никакой ложной гарантии wall-clock доставки.
2. **Liveness и functional readiness — разные сигналы:** `systemd active/restarts` говорит о процессе; корректный lock-owned `ready`/heartbeat — о функционировании worker-цикла; отсутствие classification domain events не является ни успехом, ни отказом.
3. **Текущий external stale alert: `NOT CONFIGURED / NOT VERIFIED`.** Не заявлять, что Grafana/PRTG уже контролирует свежесть этого события. Для **будущего отдельно допускаемого мониторинга** рекомендуемая конструкция: считать last observed `ready` по *timestamp получения записи journal/Loki*; предварительный порог `age > 180 seconds` при одновременно ожидаемой активности службы, с явно указанной задержкой доставки логов. Это **рекомендация для отдельного Monitoring TASK**, не изменение QIO-01A и не активный SLA.
4. **Owner PRTG disposition:** Owner сообщил, что PRTG работает отдельно, собирая SNMP/системные датчики, **не является потребителем health-событий CaptivPortal**. Принять как **Owner-asserted non-consumer / limited-risk acceptance для QIO-01A**. При этом Tech Lead прав: authenticated sensor/notification inventory не выполнен из-за HTTP 401, поэтому нельзя писать `PRTG TECHNICALLY VERIFIED`. В отчёте хранить оба факта. **PRTG auth/read-only inventory не является обязательным блокером для узкого QIO-01A** при данном Owner-допуске; при последующем обнаружении кастомного SSH/EXE event consumer или явной зависимости от 1/s ready — мониторинговый gate возвращается в HOLD, cadence пересматривается.
5. GitHub, локальные конфигурации, live Grafana dashboards/alerts и Loki/Alloy исследованы Tech Lead; отсутствие exact event-specific consumer там подтверждено в проверенном объёме, **не глобально** для интернета/внешних систем. В рамках текущего ограниченного изменения monitoring compatibility admission **достаточен при документировании этой границы**.
6. Не обещать, что shutdown публикует failure или что отсутствие heartbeat обязательно даст алерт: systemd liveness и будущий stale-monitoring — независимые контракты.

## A3 — telemetry envelope: **MINIMAL V1 APPROVED**

- **Не менять JSON** `fingerprint.integration_worker_health` в QIO-01A: `{ "event": "fingerprint.integration_worker_health", "reason_code": "..." }`. Разрешены существующие context fields только там, где они уже присутствуют (например, отдельный `lease_lost` c `integration_id`).
- Допускаются значения `reason_code`: существующие `ready`, `integration_unavailable` и новый `consumer_lock_unavailable`. Это **изменение значения статуса**, но **не изменение ключей/schema**.
- **Не добавлять** `event_at_utc`, `heartbeat_kind`, counters, `last_seen`, `version` или source-wall-timestamp в v1. Из ранее предложенного handoff **снять требование source timestamp** для этого фиксированного scope; время записи берётся из journald/Loki envelope, а для scheduling — только monotonic clock внутри worker.
- **Не менять** глобальный `submitter.emit` и его allowlist. Прямой существующий тест `emit('...ready') -> {event, reason_code}` продолжает PASS. Не раскрывать payload, secrets, MAC/IP, tracebacks.

## A4 — failure emissions: **APPROVED, NO FAILURE DEDUP IN V1**

- Подавлять/редуцировать **только** повторные позитивные `ready` после успешного lock-owned цикла. **Никакие не-ready события не throttle** в v1, даже идентичные последовательные `integration_unavailable` или `consumer_lock_unavailable`.
- Каждый failure, lock miss, transition, recovery публикуется сразу. Event `lease_lost`, `classification_started`, `classification_succeeded`, `classification_no_result`, `classification_retry`, `integration_identity_*`, Auth-facing submitter `integration_unavailable` — без изменения имени, количества по доменным причинам, содержимого и скорости публикации.
- Не менять systemd Restart/Watchdog, общий LOG_LEVEL, journald/rsyslog, TLS warnings, MicroK8s, audit, OpenAPI, SQLite writes/transaction границы.

## 5. Exact implementation admission and tests for Tech Lead

**Architectural HOLD A1–A4: CLOSED. TECH LEAD MAY ISSUE ONE SCOPED CODER IMPLEMENTATION TASK** для `QIO-01A` после pinning версии; никакого автоматического production GO.

**Implementation scope:** `app/device_fingerprint_integration/worker.py` и строго необходимые targeted tests. Любое изменение emitter/schema, DB, systemd или соседнего модуля требует возвращения на architectural review.

**Минимальные детерминированные tests:**

1. `run_once()` возвращает прежнее activity-boolean: `False` при lock miss, `False` при lock-owned idle, `True` при работе. Подтверждение `ready` только по приватному owned-success outcome, не по bool; публичные сигнатуры/прямые тесты неизменны.
2. Start: первый successful owned idle `ready` немедленно; последующие 1s success молчат до `elapsed >= 60`, затем один ready; `59.999 / 60 / 60.001`, большой forward monotonic jump, clock injection, отсутствие негативных elapsed artefacts; crash/restart получает немедленный fresh ready после первого successful owned cycle.
3. Lock miss before first success, lock miss after ready, повторные misses, затем recovery; ни одного ready на miss. Проверить случаи, когда другой consumer законно держит lock; не приписывать global unavailable.
4. Exception first/after ready, повторные исключения, повторные разные failures и recovery; **каждый** failure немедленно, ready только после следующего owned-success.
5. Controlled `classification_retry` / `no_result`, `lease_lost`, identity resolution/conflict, identity_due + no job, защита от stale private outcome, stop/shutdown, strict output JSON. Domain calls/transactions/cadence не изменены.
6. Если test double подменяет `run_once` без приватного подтверждения ownership, **fail closed** (не публиковать `ready` на одном только `False`/`True`), либо строго использовать проверяемый явно выданный observation interface; не вводить ложное подтверждение через mocks.
7. Monitoring smoke: current Grafana/alerts без зависимости от кратности 1/s (scope verified); PRTG disposition записана как Owner-asserted / technically unverified. Никакого выдуманного deployed stale alert.
8. Следом Windows Central Lab strict gates, Linux/WSL Lab focused correctness and host/guest comparative performance; production только по отдельному Owner GO и staged deployment/rollback.

**Performance verdict:** ожидается значительное снижение **повторных сообщений `ready`**. Не объявлять `18,7%` снижением HDD и не принимать performance PASS по одним логам. Обязательное matched `journald cgroup wios/wbytes` → QEMU Ubuntu → физический HDD `/dev/sda` write IOPS/await/busy с наблюдением фоновой нагрузки. Отдельно подтвердить сохранность auth/classification/identity/provenance/audit.

## 6. Передача / verdict

```text
QIO-01A ARCHITECTURE A1 = APPROVED: lock-owned bounded successful cycle only
QIO-01A ARCHITECTURE A2 = APPROVED: 60 s successful-ready cadence, no existing stale alert claim
QIO-01A PRTG = OWNER-ASSERTED NON-CONSUMER; TECHNICAL INVENTORY UNVERIFIED; LIMITED-RISK ACCEPTED
QIO-01A ARCHITECTURE A3 = APPROVED: MINIMAL JSON V1; no added timestamps/fields
QIO-01A ARCHITECTURE A4 = APPROVED: failures and domain events always immediate
QIO-01A TECH LEAD CODER TASK = MAY ISSUE after source/version pinning
QIO-01A PRODUCTION DEPLOY = HOLD pending separate Owner approval + QA/perf gates
QIO-01B/C/D/E = OUT OF SCOPE
```

**Ответ на PRTG:** не смешивать этот отдельный SNMP/системный мониторинг с CaptivPortal analytics/health. Допущение об отсутствии потребителя `fingerprint.integration_worker_health` взято из решения Owner, а не из независимого просмотра защищённых PRTG sensors.
