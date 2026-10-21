# CAPTIVPORTAL — QIO-01 Journaling Root Cause & Architecture Handoff v1.0

**Дата:** 2026-10-15 (Asia/Baku)  
**Роль:** Performance & Optimization Researcher → Technical Lead for Performance Optimization  
**Статус:** исследовательское заключение + ограниченные архитектурные решения; **не** Coder TASK и **не** разрешение менять production.  
**Родительский план:** `CAPTIVPORTAL-PERF-IO-QUIET-LOAD-OPTIMIZATION-ROADMAP-v1.0-2026-10-15.md`, стадия **QIO-01**.  
**Production checkout, подтверждённый 15.10.2026:** `84b80376b13002d435be28eec98b91b9cbf71c63`. Фактически загруженный код долгоживущих процессов может отличаться; сверять artifact identity в каждом implementation gate.

## 1. Обнаружение и границы достоверности

### 1.1. Предыдущий контроль QUIET-01, 12:55–12:57 AZST

- Guest `systemd-journald.service`: **1 982 завершённые guest block writes / 120 s** (~16,52 writes/s), **9 752 576 bytes** учтённых записей; самый крупный индивидуальный writer Ubuntu VM.
- Host `/dev/sda`: **9 742 completed writes/120 s** (~81,2/s), **56,1% busy**, ~101,27 MB writes; **Ubuntu VM QEMU cgroup 6 663 writes**. Гостевые/хостовые cgroup I/O **не** равны строго физическим IOPS один к одному.
- Основной портал и другие службы также пишут SQLite независимо от количества посетителей. Это не задача отключения SQLite durability.

### 1.2. Новая независимая QIO-01 выборка, 13:39 AZST

Пассивная **100-секундная** подписка на **новые**, а не исторические сообщения `journalctl --follow -n 0 -o json` и параллельный guest cgroup `io.stat` (`journald`, `rsyslog`, main portal) / `vda diskstats` с шагом около 10 s. Сама диагностическая PuTTY/sudo-сессия создаёт часть auth/audit-событий. **Production не изменялся.**

- **535 новых journal records за ~100 s**, ~5,35 records/s; JSON serialized journal export volume не эквивалентен байтам на диске.
- `journald` cgroup: суммарно около **1 149 guest write operations** на наблюдавшихся 10-секундных интервалах (включая интервалы без completed writes, с пакетными всплесками). Не подменять этим ни все source-логические записи, ни host HDD writes.
- `journalctl --disk-usage`: **3,9 GB** архивных и активных журналов. Это объём хранения, **не** доказательство причины текущей записи.

| Автор journal-записей (`_SYSTEMD_UNIT` / `SYSLOG_IDENTIFIER`) | Records / 100 s | Подтверждённый характер |
|---|---:|---|
| `captive-portal.service` | **178** | В том числе **50 `InsecureRequestWarning` + 50 `warnings.warn`**, то есть ~100 строк предупреждений TLS на регулярных Omada HTTPS-запросах; есть admin query/access, которые **не** автоматически «мусор» |
| `fingerprint-classification.service` | **100** | **100 идентичных `fingerprint.integration_worker_health` с `reason_code=ready`**; один INFO каждые ~1 s |
| Audit records без service unit | **110** | `audit` идентификатор: BPF LOAD/UNLOAD, sudo/cron/PAM/exec, часть создана диагностикой; **не выключать security audit** |
| `snap.microk8s.daemon-containerd.service` | **44** | Ошибки `ExecSync`/неуспешных контейнерных операций, не штатный успешный heartbeat |
| `snap.microk8s.daemon-kubelite.service` | **39** | В частности, **CrashLoopBackOff `calico-node`**, `StartContainer` / `RemoveContainer` |
| `cron.service` | **25** | CRON/sudo, часть связана с PAM/audit и реальными задачами |
| Прочие (NI-01, Evidence, Sensor, Traffic Projection, systemd и др.) | **39** | Отдельные health, reconciliation, source-health/ingest; без оснований для глобального подавления |

**ВНИМАНИЕ:** названные строки `InsecureRequestWarning` и `warnings.warn` относятся к **двум отдельным journal records одного предупреждения**. 100 записей — не 100 независимых запросов. Классификация по шаблонам с обезличиванием; содержимое с MAC/IP/секретами не сохранялось в исследовательский отчёт.

### 1.3. Исходный код / current-state, независимое подтверждение

- `app/device_fingerprint_integration/worker.py`, `IntegrationWorker.run()` — `run_once(); emit("fingerprint.integration_worker_health", reason_code="ready"); stop_event.wait(1)`. После исключения в цикле — `reason_code="integration_unavailable"`; события об outcome/identity записываются отдельно. Ежесекундный `ready` структурно предопределён исходником.
- `app/device_fingerprint_integration/submitter.py` — источник telemetry emitter, current logging pipeline.
- `app/config.py`: `VERIFY_SSL = False` (на исследуемом SHA). `app/controllers/omada.py`: несколько HTTPS-вызовов с `verify=self._verify_ssl`. Историческая документация подтверждает этот security debt. Новая journal-выборка содержит `urllib3 InsecureRequestWarning`. Записи из `/proc/PID/environ` **не** содержат `VERIFY_SSL` — он может приходить из Python settings, а не process env. Не утверждать, что конкретная `env`-переменная выставлена в production.
- MicroK8s запущен с действующими `containerd`, `dqlite`, `kubelite`; ранее обнаружены каталоги 3 pods и 4 containerd runtime tasks. **Нельзя** вслепую останавливать/удалять MicroK8s.
- `/etc/systemd/journald.conf` содержит только `[Journal]` (параметры по умолчанию); `rsyslog` отдельно маршрутизирует syslog/auth/kern, но **дублирование источников и его физический вклад отдельно не доказаны**.
- Помимо journald, app-file `/opt/CaptivePortal/logs/auth_telemetry.log` имеет много `visit.reader_scan_completed`, `home_ap_24h.ap_snapshot`, `observation.ap_cycle_completed`, `current_state.*_cycle_completed`; `/opt/CaptivePortal/logs/pending_session_cleaner.log` содержит `pending_session.scan.completed`. **Это отдельная ветка producer-логирования; записи в app-file не равны автоматически строкам journald.**

## 2. Приоритеты внутри QIO-01

Отделены **безопасность/корректность** и **величина spam**. Оптимизировать источник, не маскируя нарушение.

| Приоритет | Ветка | Решение исследования | Статус передачи Tech Lead |
|---|---|---|---|
| **QIO-01A / первая** | Classification worker `ready` 1/s | Event-on-transition + bounded heartbeat при неизменном здоровье; без SQLite / replay / state manipulation | **ARCHITECTURE CANDIDATE APPROVED FOR TECHLEAD DESIGN**, при условии health-consumer gate |
| **QIO-01B** | Omada HTTPS `InsecureRequestWarning` | Исправить TLS trust/cert validation, не скрывать предупреждение при невалидированной TLS-сессии | **SECURITY/CONTROLLER CONTRACT HOLD** до trust design и совместимости Omada |
| **QIO-01C** | MicroK8s `calico-node` CrashLoopBackOff | Диагностировать и исправить неработающий workload; выяснить владельца/dependency; не выключать ошибки | **SYSADMIN DEPENDENCY HOLD**, не Coder TASK без инвентаризации |
| **QIO-01D** | Routine telemetry portal/visits/admin | Сократить лишь доказанно повторные *неаудиторские* `success/no-change` сообщения при сохранении error/transition и event-driven observability | **RESEARCH HOLD**: разложить source file / journald / consumer |
| **QIO-01E** | Journald/rsyslog/file pipelines | Проверить фактическое дублирование и дисковые batch/write patterns, retention/rotation; source-first | **MEASUREMENT HOLD**, не менять `Storage`/`ForwardToSyslog`/rotation слепо |

## 3. Архитектурное решение QIO-01A: Classification health telemetry

### Проблема

В чистом success idle цикле `IntegrationWorker.run()` каждые ~1 s публикует неизменный `fingerprint.integration_worker_health: ready`. Данные событий и авторизация не меняются; это повтор статуса, а не независимый fact. Для QIO-01 это **100/535 = 18,7%** всех records нового окна. Это **верхняя доля устранимых record-событий**, **не** обещание -18,7% guest writes или HDD busy.

### Требуемый контракт

1. **Один единый authoritative health state в памяти процесса**: `unknown/startup → ready` после реально успешного `run_once`, `ready → integration_unavailable` при исключении/провале цикла, и `integration_unavailable → ready` только после подтверждённого успеха. Логировать каждый **переход немедленно**. Не объявлять `ready` просто потому, что loop живой. Обновлять поле monotonic последней успешной итерации на каждом реальном успехе.
2. **Периодический bounded heartbeat для неизменного `ready`**, предварительный кандидат **60 секунд** вместо каждой секунды. **TechLead обязан проверить** реальных внешних потребителей/алерты и требуемый freshness SLA; если `60 s` несовместим — выбрать обоснованный, документированный upper bound. На немедленной остановке/краше нельзя искусственно генерировать событие успеха; systemd liveness отдельно.
3. **Повторные ошибки не скрывать:** первый failure/изменение категории/серьёзности/новый отказ — немедленно. Одинаковые повторные ошибки могут быть агрегированы только при сохранённых counters, first/last occurrence, error category и bounded failure heartbeat; не терять security/audit и outcome `classification_started`, `classification_succeeded`, `classification_no_result`, `retry`, `identity_*`, `lease_lost`.
4. **Где оптимизировать:** локальный `IntegrationWorker` (перед `emit`), а **не** глобальная блокировка логирования `INFO`, не фильтр `journald`, не переопределение общего `emit`, используемого другими событиями/сервисами. Сохранять существующие event names и обязательные поля; новые optional счетчики/`heartbeat_kind` — additive only, с обратной совместимостью consumer.
5. **Без дополнительных durable writes** ради dedup (не вводить новую health SQLite-таблицу/дополнительный fsync). Использовать monotonic scheduler, clock/wall timestamp в событии, кэп на насыщение counters; после restart новое первое событие должно публиковаться сразу, а не ожидать истечения интервала. Никакого влияния на `run_once` cadence, claim/retry/identity, lock и durability семантику.
6. **Состояние важнее значения idle:** в случае неуспешной попытки, а затем восстановления при любом объёме пользовательского трафика переходы видны немедленно; при многократном idle не выдаётся ложная история новых независимых «готовностей».

### Обязательные тесты TechLead → Coder contract

- Детерминированное время: N успешных idle циклов → событие на первом success + ограниченные heartbeat, а не N одинаковых `ready`. Проверить разные интервалы, clock jumps, restart, shutdown.
- Failure после `ready`, repeated failure, новая причина failure, recovery; никакого ложного `ready`; предупреждения и error outcome не исчезают.
- Появление нового job/identity resolution, retry/lease conflict, аварийный restart — все **существующие доменные и аудиторские события** остаются неизменны.
- Monitoring consumer inventory: дашборды и alert expressions не зависят от ~1/s записей; freshness/staleness safety guard **PASS**, иначе **HOLD** и корректировка interval.
- Lab trace, одинаковые 2–3 quiet и нормальные окна: reporter records/sec, journald guest cgroup `wios`/`wbytes`, VM host QEMU writes, host `/dev/sda` completed writes/await/busy, latency/CPU, classification correctness. **При отсутствии подтверждённого host физического выигрыша — не считать QIO-01A performance PASS, даже если event-count падает.**
- Scoped rollback: возврат старой logger-кратности без отката schema/данных, с сохранением ability to audit.

## 4. Архитектурный запрет QIO-01B: не «глушить» TLS-warning

Текущая причина предупреждений — запросы к Omada HTTPS без подтверждённой проверки certificate chain/identity (`VERIFY_SSL=False` в изученном коде). Это **security debt**, поэтому **запрещено** вырезать `urllib3` предупреждение глобальным filter (`disable_warnings`, catch-warnings around all requests) ради метрики HDD.

**Правильное направление:** выбрать производимый/ротационный trust anchor Omada Controller, валидировать CN/SAN под используемый URL (для IP — корректный IP SAN либо доверенное DNS-имя), установить cert verification в клиентском transport, сохранить auth/token и Omada API compatibility, fail closed при сбое trust с диагностируемым alert. Сначала lab/integration test при истечении/замене cert и недоступности Omada. Security/Owner admission нужен до production. Замерить после исправления, исчезли ли warnings и сохранилась ли успешная API-функциональность.

## 5. QIO-01C: MicroK8s failure, а не «раздражающий лог»

`calico-node` в CrashLoopBackOff генерирует kubelet/containerd error и вторичные audit/kernel/BPF события. Источник **не healthy**; скрытие warning или `journald`-rate limiting без исправления CrashLoop недопустимо. SysAdmin должен сначала установить владельца pod, необходимость MicroK8s на Ubuntu production, workload dependencies, crash reason, affected network policy, backups/state. Затем отдельный bounded remediation с health gate и повторным host measurement; не делать `microk8s stop`, delete pods/volumes/iptables в QIO-01A.

## 6. QIO-01D / E: отдельные очереди, НЕ смешивать с первым фиксом

- Portal loggers: классифицировать **routine success/no-op** vs auth/security/audit vs operational errors, дополнительно app file logging vs stdout/journal. `auth_telemetry.log` и `pending_session_cleaner.log` — отдельные writers; перейти к source-side transition/aggregate лишь после проверки потребителей Grafana/Loki. Admin access и HTTP request logs не подавлять слепо: пользователь/администратор мог реально обращаться к интерфейсу во время «quiet».
- Rsyslog/journald: текущий конфиг не является доказательством двойной записи одинаковых сообщений; сравнить event provenance и block I/O до изменения forwarding/storage/rotation, не менять audit/security/retention.
- Audit/kernel: **не** уменьшать audit policy/disable BPF audit ради уменьшения записей. Сначала уменьшать источники ошибочных действий, которые вызывают audit.

## 7. Экспериментальный gate и ожидаемая выгода

1. **Контроль повторяемости:** 3 quiet окна по 15–30 мин, включая другое время суток; синхронизированные time boundaries на host и guest, проверка активных гостей/admin/Omada polling, backlog и incident state; baseline event templates и service writer IO. Выборка 100 s показывает причины, **не** гарантирует среднесуточный эффект.
2. **Attribution матрица:** source event → stdout/stderr → journald → guest cgroup write burst → Ubuntu QEMU host writes → `/dev/sda` completed write IOPS и write latency. Признать batch/noise и layered accounting; одна строка лога не равна одному physical write.
3. **Измеримая цель QIO-01A на уровне source:** ~100 `ready`/100 sec → first success + bounded heartbeat (~2–3/100sec если 60s и границы окна; без навязанной точной цифры при изменённом SLA). Физические показатели — **не обещать в процентах**, измерить.
4. **Correctness/security invariant:** никаких пропущенных изменений состояний/identity/failure/recovery, Omada auth не ухудшается, журнал аудита сохраняется; duplicate suppression не используется для domain events.
5. **One change / one gate:** TechLead готовит Coder TASK **только QIO-01A** после проверки monitoring/alert consumers. QIO-01B/C/D/E — отдельные решения, независимые допуски. Изменения production Owner approves; по результату новый matched baseline и пересортировка Roadmap.

## 8. Передача техническому лидеру — действие на текущий этап

**Архитектурное решение:** начинать со **scoped, in-memory, transition-only + bounded heartbeat** для `fingerprint.integration_worker_health` в `IntegrationWorker`; остальные события не менять. 

**HOLD перед Coder:** инвентаризация всех consumer-ов `fingerprint.integration_worker_health`, приемлемая максимальная задержка heartbeat и перечень интеграционных тестов. После снятия HOLD TechLead составляет implementation contract и точные acceptance tests на зафиксированном commit/artifact SHA. Результат не считается успешной оптимизацией HDD без matched host-level evidence. 

**Остальные существенные открытия:** TLS `VERIFY_SSL=False` — security trust correction; MicroK8s Calico CrashLoop — SysAdmin incident/dependency; Portal routine logs — отдельная producer attribution. Эти направления **не** объединять в общий «уменьшить INFO» Coder TASK.

---

**Статус QIO-01:** PRIMARY PRODUCERS IDENTIFIED → ARCHITECTURE HANDOFF v1.0. **Production changes: NONE.**
