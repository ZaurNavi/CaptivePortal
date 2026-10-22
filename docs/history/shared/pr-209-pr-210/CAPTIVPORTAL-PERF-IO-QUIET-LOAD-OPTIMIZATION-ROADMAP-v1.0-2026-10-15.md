# CAPTIVPORTAL — ROADMAP PERF-IO-QUIET v1.0
## План последовательной оптимизации фоновой нагрузки и Small-I/O на production HDD

**Дата baseline и документа:** 2026-10-15 (Asia/Baku)  
**Роль автора:** CaptivPortal Performance & Optimization Researcher  
**Заказчик / решение о допуске изменений:** Owner  
**Статус:** **исследовательская дорожная карта / очередь работ, не implementation TASK и не разрешение менять production**  
**Первая следующая работа:** **QIO-01 — журналирование (`systemd-journald` + источники логов)**. QIO-01 начинается с более точной **read-only** причинной атрибуции.  
**Текущий source baseline при проверке:** checkout Ubuntu `/opt/CaptivePortal`: `84b80376b13002d435be28eec98b91b9cbf71c63` на 2026-10-15 12:55 AZST. Это **не** универсальный loaded-artifact SHA всех живых процессов: у служб могут быть ранее загруженные иные артефакты. Проверять перед любым изменением.

---

## 1. Зачем и что именно оптимизируем

При практически нулевой *гостевой* активности система остаётся занята: `load average ~3–4+`, физический HDD гипервизора ~50–60% busy, хотя полезный сетевой поток мал. Устранить нужно не сам индикатор busy, а **ненужные мелкие завершённые обращения к физическому HDD**, особенно синхронные записи, и **повторную работу CPU с уже известными данными**. При этом нельзя ухудшить авторизацию, истинность материала́лизованных данных, полноту наблюдений, журнал аудита или надёжность хранения.

**Опорная модель расследования:**

```text
источник / цикл / конкретная транзакция
  → SQL, syscall, fdatasync/COMMIT, write amplification
  → cgroup guest: логические + block I/O
  → QEMU cgroup host: block I/O Ubuntu VM
  → физический HDD /dev/sda: completed IOPS, await, busy, sectors
  → влияние на функциональность и стабильность
```

Уровни не взаимозаменяемы. `syscr/rchar` — логические системные чтения, **не** physical IOPS; `io.stat` гостя — учёт guest block I/O, **не** доказательство того, сколько идентичных I/O дошло до host HDD после кеширования/слияния/планирования. Вложенные `252:0` и `253:0` **не суммировать**. Размер файла WAL или SQLite **не** равен числу записей.

---

## 2. Замороженный исходный baseline QUIET-01

**Время:** 2026-10-15 около 12:55–12:57 AZST. **Контекст:** Owner сообщил об одном подключённом, практически неактивном госте. Это режим **очень низкой пользовательской нагрузки**, но не абсолютный ноль: сервисы продолжают получать технические события и могут обрабатывать старые очереди. В интервалах 15 секунд на SPAN обычно было по **7–10 пакетов**, иногда всплески.  
**Метод:** восемь 15-секундных пассивных окон на host HDD `/dev/sda` и отдельно восемь на guest Ubuntu `/dev/vda`; cgroup v2 `io.stat`, `/proc/diskstats`, per-process `/proc/PID/io`, PSI, сетевые счётчики. Обе серии длились ~120 сек и **перекрылись примерно на 105 сек**, но **не являются идеально одной и той же 120-секундной парой**. Для прямой пооперационной причинной привязки требуется более строго синхронизированное окно. 

### 2.1. Физический HDD на гипервизоре (host, 120 сек)

| Показатель | Измерено | Значение |
|---|---:|---|
| Completed writes | **9 742** | **81,2 writes/sec** |
| Completed reads | **891** | **7,4 reads/sec** |
| Записанные физические секторы (512 B) | **197 800** | **101,27 MB/120 sec**, **~0,84 MB/sec** |
| Средний размер завершённой записи | **~10,4 KB** | Small-I/O, а не большой последовательный поток |
| `io_ticks` / elapsed | **~67,4 / 120 секунд** | **~56,1% busy** |
| Средняя сумма времени завершения write/request (`write_ticks / writes`) | **~65 ms** | HDD latency; не равна чистому времени CPU |
| Host cgroup Ubuntu VM | **6 663 writes / 120 sec** | **~68,4%** от всех завершённых host writes по счётчикам; доли могут зависеть от layer accounting |
| Host cgroup Windows Server VM | **1 459 writes** | Самостоятельная конкурирующая VM |
| Host `systemd-journald` / `rrdcached` | **749 / 557 writes** | Host-local нагрузка, не относится к гостевому CaptivPortal |

Проверка `load average` Ubuntu показала примерно **3–4+** при 4 vCPU. Гостевая PSI `io` в контрольном мгновенном наблюдении: `some avg10 ≈ 13,85%`, `full avg10 ≈ 9,48%`; это подтверждает ожидание I/O, но не доказывает, что весь load вызван диском. Дополнительно есть существенное реальное **потребление CPU** фоновыми потоками.

### 2.2. Топ источников записи внутри Ubuntu VM (guest block cgroup, ~120 сек)

| Место | Источник | Учтённые writes | Writes/sec | Guest `wbytes` | Примечание |
|---:|---|---:|---:|---:|---|
| 1 | `systemd-journald.service` | **1 982** | **16,52** | **9,75 MB** | Писатель журнала, настоящие генераторы сообщений требуют атрибуции |
| 2 | `captive-portal.service` | **1 282** | **10,68** | **5,73 MB** | Фоновые SQLite-транзакции в нескольких подсистемах |
| 3 | `snap.microk8s.daemon-containerd.service` | **926** | **7,72** | **3,85 MB** | Инфраструктура VM, независимая от гостей |
| 4 | `network-metadata-projection.service` / NI-02B | **404** | **3,37** | **4,61 MB** | При этом **46 029 pending attribution** |
| 5 | `fingerprint-sensor.service` | **395** | **3,29** | **2,29 MB** | В частности, WAL сетевой атрибуции |
| 6 | `snap.microk8s.daemon-k8s-dqlite.service` | **310** | **2,58** | **4,50 MB** | Вместе с containerd и kicker образует группу MicroK8s |
| 7 | `traffic-projection.service` | **222** | **1,85** | **1,71 MB** | Историческая сверка/активные циклы |
| 8 | `alloy.service`, `cron`, `snap.microk8s.daemon-apiserver-kicker`, `rsyslog` | **48 / 47 / 44 / 41** | — | — | Небольшие писатели; может быть косвенное влияние на journald |
| 9 | `network-service-recognition.service` / NI-04 | **34** | **0,28** | **0,48 MB** | Основная тяжесть вероятнее CPU и read-amplification |
| 10 | `fingerprint-classification.service` | **29** | **0,24** | **0,16 MB** | Запись мала, но CPU заметен |
| 11 | `fingerprint-evidence.service` | **13** | **0,11** | **0,72 MB** | Ранее был критический read-heavy startup, **сейчас восстановился** |
| 12 | `network-metadata.service` / NI-01 | **11** | **0,09** | **1,75 MB** | A включён, сейчас не лидер Small-I/O |

**Как читать рейтинг:** отдельные службы ранжированы по **числу завершённых guest block writes** в измеренном окне, а не по байтам, CPU или номинальному размеру таблиц. Строка MicroK8s в плане — **группа**: containerd 926 + dqlite 310 + kicker 44 ≈ **1 280 writes**; это **не дополнительные** записи сверх таблицы. Не складывать cgroup I/O в утверждение «ровно столько host HDD IOPS», поскольку есть layered accounting, сглаживание, метаданные FS и кеш. Journald генерирует запись при приёме логов *других* служб — **устранение первичного избыточного лога** важнее слепого урезания journald.

### 2.3. Отдельный CPU-лидерборд (25-секундное окно)

| Сервис | Эквивалент одного занятого CPU-ядра |
|---|---:|
| NI-02B | **0,744** |
| Fingerprint Classification / Integration | **0,426** |
| NI-04 | **0,342** |
| Traffic Projection | **0,315** |
| CaptivPortal main | **0,181** |
| NI-01 | **0,004** |

Это **не** рейтинг физического HDD IOPS. По CPU почти два ядра занимают несколько фоновых обработчиков, даже когда пользовательские запросы редки. Работа с историей и polling являются самостоятельной целью оптимизации.

### 2.4. Предметная evidence-проверка (из того же исследования)

1. В 14-секундной **выборке** `/proc/TID/syscall` виден реальный `fdatasync`: у основного CaptivPortal — `visits.sqlite3[-wal]`, `visitor_registry.sqlite3[-wal]`, `current_state.sqlite3[-wal]`, `public_traffic.sqlite3[-wal]`; у Fingerprint Sensor — `network_attribution.sqlite3-wal`; у NI-02B — `network_metadata_projection.sqlite3[-wal]`; у Traffic Projection — `traffic_projection.sqlite3[-wal]`; у NI-04 — `network_service_intelligence.sqlite3-wal`. **Число попаданий в sampling не является количеством COMMIT/fsync за секунду**; sampling искажён длиной ожидания.
2. За 35 секунд менялись SQLite/WAL в том числе `observations`, `public_traffic`, `visits`, `visitor_registry`, `network_metadata_projection`, `network_service_intelligence`, а также `auth_telemetry.log`, `pending_session_cleaner.log` и journald. `Δsize=0` **не означает отсутствия записей**, если страницы перезаписываются.
3. **NI-02B**: `runtime_state=attribution_unavailable`, `safe_reason=pending_attribution`; **46 029** pending, из них **45 529** due к ~13:05 AZST; в bindings 160 `authoritative`, 50 `not_yet_registry_resolved`. **Это не доказательство сбоя**, а подтверждённая большая очередь неопределённости и потенциально тяжёлый цикл.
4. **NI-04**: `usable`, `last_edge_feed_seq=highwater=89805`, `backfill_state=complete` во время проверки. Не отключать корректную materialization на основании CPU без выяснения, какие циклы излишни.
5. Fingerprint Sensor spool **0 rows**, SQLite-файл ~112 MiB сохранил почти весь объём как **freelist**. Пустая очередь уже **не** объясняет постоянные записи Sensor. **НЕ** запускать VACUUM/очистку в production ради уменьшения размера файла.
6. MicroK8s: активны containerd, dqlite, kubelite; видны 3 pod-каталога и 4 containerd task. Команда `kubectl get pods` не успела ответить за 5 секунд. **Нельзя** утверждать, что MicroK8s ненужен или безопасен для остановки.

---

## 3. Принципы и ограничения для **каждой** фазы

- **Measurement → hypothesis → isolated Lab reproduction → prove correctness → gated change → postdeploy matched measurement**. Никакой рефлекторной правки сервиса, отключения логов, перестановки SSD вместо архитектурной работы или массового рестарта.
- **Не трогать** SQLite `synchronous=FULL` и иные утверждённые durability guarantees просто ради IOPS; не отключать `fsync`; не делать `PRAGMA journal_mode`/`wal_checkpoint`/`VACUUM` на живой production без отдельного утверждённого remediation-протокола.
- **Authoritative vs derived:** исходные события, идентичность, авторизация, audit, checkpoint, provenance и safety-state всегда корректны после crash/restart. Derived материализованные данные оптимизируются только при гарантированном replay/recovery. Cursor продвигается **только** за фактически durable данные / гарантированный replay.
- **Нет stale optimism:** отсутствие новых гостей не равно отсутствию старых pending, replay, delivery, expiry, reconciliation. Не удалять pending-атрибуции, не скрывать `attribution_unavailable`, не подменять missing fact положительным выводом.
- **Не снимать функциональность ради performance:** Auth/CAPPORT/Omada, security/audit, readiness, sensor source-health, NI source continuity и retention остаются истинными. Контрольный сценарий — не только quiet, но normal/peak, backlog, restart, crash and recovery.
- **Без прямого Coder GO:** эта карта задаёт порядок исследования, не архитектурный контракт реализации. Owner решает, когда допускать изменения. В production на каждой фазе сначала read-only; code/config/systemd изменение только после отдельного допуска.
- **Исторические решения:** NI-01 оптимизация A (`PR #209`) — **KEEP ACTIVE**, снижение физического I/O ею **не доказано**; NI-01 вариант B (`PR #210`) — **REJECTED/CLOSED UNMERGED**, не возобновлять B/R4 без независимого нового основания. Исторический `coverage_gap_possible` не стирать.
- **Воспроизводимость baseline:** timestamps host/guest, PID+loaded artifact SHA/TREE, configuration, source generation, число клиентов, пакетный rate, lag/backlog, busy/await/PSI, `cgroup io.stat`, log volume, SQLite file/WAL/checkpoint state. Сравнивать **похожую quiet нагрузку** до/после, по нескольким окнам, плюс normal/peak.

---

## 4. Порядок работ: от большего Small-I/O к меньшему

### Этап QIO-00 — фиксировать quiet measurement protocol (организационный prerequisite, не оптимизируемый модуль)

**Уже выполнено:** сравнительный 120-секундный baseline, host+guest, список лидеров, отдельная CPU-оценка, FD-sampling, SQLite-state read-only.  
**Дополнить перед первой правкой:** минимум 3 quiet-окна по 15–30 мин в сопоставимых условиях; одно в другое время суток; проверять, что во время замера нет догоняющего backlog/ротации/maintenance spike, либо отмечать их отдельно. Вести `_begin`, `_end`, `host/guest` time sync. Разделять **background steady-state**, **scheduled spike**, **catch-up**, **startup**.  
**Результат:** воспроизводимый baseline и шаблон сравнения, а не оптимизация ради одной случайной минуты.

### **Этап QIO-01 / P1 — журналирование Ubuntu: крупнейший измеренный писатель**

**Measured:** `systemd-journald` **1 982 guest block writes / 120 s**, 9,75 MB. Файлы journald и application `.log` меняются при низком сетевом трафике. Дополнительно `rsyslog` 41, `alloy` 48 writes; возможны дубли по цепочке producer → stdout/journald → rsyslog/Alloy, **фактически не доказаны**.

**Исследуем причинно (первая задача следующего цикла):**
1. Read-only выяснить **кто создаёт** сообщения, а не просто кто пишет `.journal`: messages/sec и bytes/sec по `_SYSTEMD_UNIT`, event name, severity, repeated payload, rotation/bursts. Системные службы и application разделить, равно как audit/security и routine metrics.
2. Сопоставить spikes journald c `systemd-journald` guest block writes и host QEMU write bursts; учесть journal flush, compression, fsync, `rsyslog`, Alloy; проверить краткие и долгие окна, не выполнять долгий `journalctl` full scan на перегруженном HDD.
3. Выделить **«нулевую полезность»**: бесконечные одинаковые heartbeat, success при отсутствии change, пустые polling events, metrics дубли и ошибки в цикле. Отдельно подтвердить продуктовую необходимость каждого лога.
4. В Lab сравнить *source-side event dedup / transition-only / bounded aggregate summaries / sane log level*, сохранить per-event errors, security/audit, fail-closed и диагностичность. **Не** выключать journald, не сокращать его durability/retention вслепую.

**Gate:** известны **топ-источники журнала**, конкретный event→write путь, proposal измеримо уменьшает физические host IOPS при сохранённой наблюдаемости и audit.  
**Deliverable:** `QIO-01 Journaling Root-Cause & Lab Optimization Admission`, с приоритетом по вкладу *producer*, а не только by storage daemon.

### **Этап QIO-02 / P1 — основной `captive-portal.service`: idle write / fsync fan-out**

**Measured:** **1 282 writes / 120 sec**. Пассивно зафиксированы `fdatasync` у `visits`, `visitor_registry`, `current_state`, `public_traffic` и их WAL, но точные per-file counts **ещё не установлены**.  
**Сначала разобрать по независимым трассам** (порядок *внутри* QIO-02 будет определён измерением, не придуман заранее):
- Visit Lifecycle / Visits: граница source/visit fact, периодическая reconciliation, checkpoint, возможные no-op updates;
- Visitor Registry: snapshots, identity/online/offline state, registry reconciliation, повторная фиксация одного состояния;
- Current State: polling Omada, сравнение с предыдущим snapshot, невидимые изменения, частота транзакций;
- Public Traffic: writer and per-cycle state, фоновый сбор/перерасчёт при нулевом реальном трафике;
- Observations/OMADA collectors: обязательные фоновые poll-cycles и нет ли пустого durable write, функциональные retention/integrity paths.

**Lab гипотезы:** guard `no-effective-change → no state write`, обновление snapshot только при изменившемся canonical content, неизменяемый ownership данных, безопасный debounce/coalescing *derived* данных, reasoned batching существующих commits. **Запрещены** ложный idle при отсутствии Omada / устаревшем snapshot, сброс visit/registry state, слияние independent authoritative facts в один отложенный commit.

**Gate:** per-DB и per-operation доказана вкладная матрица `cycle→transaction→fdatasync→guest writes→host`. После Lab оптимизации все identity, visit start/end, auth, restart, late event, stale-state и current-state тесты PASS, host quiet IOPS ниже без увеличения latency гостя.

### **Этап QIO-03 / P1–P2 — MicroK8s/containerd/dqlite: независимая от портала инфраструктура VM**

**Measured group:** **926 containerd + 310 dqlite + 44 apiserver-kicker = 1 280 guest writes / 120 sec** (~10,7/sec, примерно уровень основного портала). Подтверждены 4 containerd runtime task и каталоги 3 pods; назначение ещё не установлено.

**Проверить:** какие workloads реально работают, кто владелец, какие volumes/alerts/services от них зависят, частоты health/checkpoint/metadata fsync containerd/dqlite, idle vs productive churn. Разложить три службы **отдельно**, чтобы исключить двойной счёт и влияние на host.

**Возможные решения после зависимости/Owner admission:** перенести действительно ненужную лабораторную инфраструктуру с production VM, уменьшить избыточную активность конкретных workload, применить корректную штатную конфигурацию. **Не** отключать/удалять MicroK8s до подтверждения зависимостей. Этап может выполнять SysAdmin отдельно от Coder; это **не** аргумент менять приложение.

**Gate:** dependency inventory, rollback / backup, сохранность pod volumes/availability, host physical write reduction в matched windows.

### **Этап QIO-04 / P1 по CPU и P2 по HDD — NI-02B, очередь атрибуции**

**Measured:** **404 guest writes / 120 sec**, CPU **0,744 ядра**, очень много логических чтений в некоторых 15-секундных интервалах. `46 029 pending`, `45 529 due`, `safe_reason=pending_attribution`; source poll ~1 s, retry до 500/30 s, binding reconcile 60 s.  
**Важно:** `attribution_unavailable` отражает существующую unresolved attribution и **не даёт права** считать все pending мусором или изменять отрицательные/положительные решения.

**Разложить:** время и SQLite VM-steps по `pending()` selection, `prepare()`, `_evaluations()`, source authoritative reads, `commit_dispositions`, registry `reconcile_selection()`, repeated identical UPDATE, WAL checkpoint; установить, что обусловлено действительно изменившимися authority/identity, а что безрезультатным перечитыванием. Проверить backlog freshness и покрытие отдельными категориями.

**Lab гипотезы:** retries при *изменении relevant authority generation / binding* плюс гарантированный fallback/TTL periodic recheck, smarter bounded schedule, reuse immutable derived resolution, immutable facts, diff-based registry no-op gate; batching **только** по совместимым границам durability/replay. Нельзя увеличивать retry interval без математического upper-bound на late resolution и UI freshness или silently discard pending.

**Gate:** backlog и late-binding convergence не хуже baseline, no cross-identity merge, safe_reason accurate, no silent skip; снижение CPU и guest/host physical I/O, а не только улучшение `EXPLAIN`.

### **Этап QIO-05 / P2 — Fingerprint Sensor: network attribution durability и idle writes**

**Measured:** **395 writes / 120 sec**; зафиксирован `fdatasync` `network_attribution.sqlite3-wal`. На 13:02 Sensor spool = **0 rows** и много SQLite freelist; основной писатель сейчас не обязан быть delivery spool. Нельзя делать VACUUM/DELETE ради красивого размера файла.

**Разложить:** CAPTURE/Sensor local state, DHCP/identity attribution, independent WAL commits, здоровье и heartbeat vs source transitions, доставку и подтверждение, данные из SPAN при low traffic. Сравнить `spool` и `network_attribution` отдельно. Предложения — идемпотентные no-op guards, confirmed aggregate summaries, допустимая group commit только не-authoritative статусов.  
**Gate:** без потерь и переупорядочивания evidence, корректный restart/replay, сохранён FULL durability для spool/source, bounded capacity/recovery, честный health.

### **Этап QIO-06 / P2 — Traffic Projection: scheduled full reconcile и логические чтения**

**Measured:** **222 writes / 120 sec**, CPU **0,315 ядра**. В коде `source_head_scan_interval_seconds = 15`; `full_reconcile_target_interval_seconds = 300`. `reconcile_site()` читает historical source metadata, проверяет source/projected counts, выполняет `_deep_audit`, пишет state; в healthy state это **не означает**, что всё бесполезно.

**Разложить:** active incremental vs target window vs full reconciliation; источники повторных `rchar/syscr`, полная проверка `COUNT`/semantic proof и checkpoint/fsync; отдельные cold/warm и old history cases. Предложения — authoritative change signal/generation digest, доказуемая reuse materialized proof, ограниченная scheduled verification и retention verification. **Не** снимать контроль semantic divergence, не пропускать source repair без guarantee.

**Gate:** proven full reconcile detection latency and completeness; equal positive/negative correctness on delayed corrections/restarts; lower CPU **и/или** physical writes, не оба заявлять автоматически.

### **Этап QIO-07 / P3 — NI-04 и Fingerprint Classification: CPU/read-heavy background**

**Measured:** NI-04 **34 guest writes / 120 sec**, CPU **0,342 ядра**; Classification **29 writes**, CPU **0,426 ядра**. NI-04 `usable`, feed cursor догнал highwater, backfill complete. Classification worker делает попытку `claim()`/`identity_due()` каждую секунду; по одному SQL плану видны индексные пути плюс временная сортировка, **но нет доказательства**, что именно SQL план даёт основную нагрузку.

**Исследование:** реальная цена idle selection и coverage reconciliation каждые 30 s в NI-04, materialization heartbeat ~10s, stale/identity job/retry в Classification; сбор CPU stack + SQLite query/profile в **Lab**, готовые telemetry и read-only runtime-state в production. Возможные safe change-driven wakeups и доказуемая reuse downstream materialization.  
**Gate:** не ухудшить materialized service intelligence correctness, identity provenance, durable job processing, replay, index query under mixed workloads. Не оптимизировать idle CPU ценой ростa writes.

### **Этап QIO-08 / P3 — малые источники и объединённый инфраструктурный хвост**

**Measured:** Alloy 48, cron 47, apiserver kicker 44 (в группе MicroK8s уже учтён), rsyslog 41, малые системные writer; NI-01 лишь 11 writes в этом quiet window; FP Evidence 13. Разбирать по *проверенному residual impact* после предыдущих стадий: collector batching/dupes, `rsyslog`/journald duplication, cron jobs, security/audit, optional service chatter; не делать десятки мелких изменений ради несущественных процентов.  
**NI-01** специально не поднимать вверх без нового замера: **A KEEP ACTIVE, B CANCELLED**; доп. исследования ingestion/retention — отдельная ветка в normal/catch-up, а не quiet-small-write оптимизация. Fingerprint Evidence startup full SQLite validation — самостоятельный **readiness/cold-start** риск, наблюдавшийся 14–15 октября; исправлять отдельным архитектурным admission, не приписывать ему высокий **steady-state** write IOPS.

---

## 5. Порядок принятия решения и готовности (stage gate)

**Перед началом модуля:**
1. Перепроверить production checkout, loaded artifact SHA/TREE, конфигурацию, активный источник, latency, clients, backlog; повторить пассивные quiet windows. Обозначить **точное** место в `io.stat` и host physical `diskstats`.
2. Установить operation-level причинность. `ps`, `strace sampling`, `lsof`, `EXPLAIN QUERY PLAN`, file mtime и `journalctl` **по отдельности** не доказывают число физических I/O. Длительную/дорогую instrumentation — Lab. Read-only probes должны быть bounded и не держать production SQLite транзакций.
3. Разделить authoritative write и derived/status/no-op write; доказать crash/replay semantics до предложения batching/cache/materialization.
4. Подготовить **одну falsifiable гипотезу на одно малое изменение**: до/после + контроль false/true identity, retention, failure, restart, late data, health, source continuity.
5. В Lab три gates: correctness (включая negative cases), performance (CPU, WAL, commits, fsync, host disk busy/IOPS/await) и observability/no gaps. Не повторять неуспешный NI-01 B: оптимизация SQL query без улучшения end-to-end — не PASS.
6. Только Owner/admission → implementation review → canary/staged production. После deploy **строго comparable baseline**, 15–30-мин quiet несколько раз плюс normal/peak. Если положительного физического эффекта нет или появился semantic risk — revert и перейти к другой гипотезе.

### Измеримые показатели результата для этапа

| KPI | Основной смысл |
|---|---|
| Host `/dev/sda` completed write IOPS (quiet, median+P95) | Главная бизнес-цель Small-I/O; внутри похожей фоновой нагрузки |
| Host `/dev/sda` write await и busy | Чтобы снижение writes не скрывало ухудшение latency |
| QEMU Ubuntu host cgroup `wios/wbytes` и guest per-service `wios/wbytes` | Где реально уменьшили операции и какие слои остались |
| CPU core-equivalents + guest PSI io | Чтобы лечение HDD не создало новый CPU/I/O узкий участок |
| Per-service durable transactions, fdatasync, WAL bytes/checkpoints (Lab trace) | Какая логика вызвала выигрыш |
| Guest/auth correctness, EVE source coverage, NI checkpoints, pending age, materialization safety state, registry/visit freshness, fingerprint delivery | **Обязательный функциональный gate**, не вспомогательная метрика |
| Journald events per producer / duplicate ratio и audit coverage | Снизили ли *ненужные* записи без потери расследуемости |

**Целевые проценты экономии заранее НЕ устанавливаем:** 120-секундного периода недостаточно для честного обещания (например, «–50% HDD»). Вместо этого фиксируем outcome на каждом этапе и затем **перестраиваем рейтинг**: следующий приоритет выбирается по **новому** baseline, а не механически по старой таблице.

---

## 6. Организация работы без размножения задач

**Один модуль за раз, максимум одна production-гипотеза на ревью.**

```text
QUIET-01 baseline (готов)
  ↓
QIO-01 J journald — расследование producer-ов → Lab → gate → результат
  ↓
повторный физический quiet baseline → пересортировка очереди
  ↓
QIO-02 CaptivPortal main state writers
  ↓
QIO-03 MicroK8s (после dependency-admission)
  ↓
QIO-04 NI-02B pending attribution
  ↓
QIO-05 Fingerprint Sensor
  ↓
QIO-06 Traffic Projection
  ↓
QIO-07 NI-04 / Classification CPU
  ↓
QIO-08 остальной фон + cross-host
```

**Возможное исключение к очереди:** если обнаружен P0/P1 correctness, полнота источника, переполнение очереди, ошибки Omada auth или рост невосстановимого backlog — эксплуатационный incident имеет приоритет над performance roadmap. Так было при восстановлении Fingerprint Evidence/Sensor 14–15 октября. Это **не меняет** рейтинг уже измеренных steady-state записей.

**Моя ответственность как исследователя:** самостоятельно проводить доказуемую read-only атрибуцию, фиксировать гипотезы и контргипотезы, готовить Lab experiment plan и сводку результата; **не** перекладывать само расследование на Chief Architect. Архитектурные решения / изменённые contracts — только если измерения действительно затронули semantic boundaries. Для шага QIO-01 следующий документ должен отвечать: *кто именно заставляет journald писать 1 982 раза за 120 секунд и какая часть безопасно устранима у producer, а не за счёт скрытия логов*.

---

## 7. Рабочий журнал дорожной карты на старт

| ID | Статус | Привязка к baseline | Следующее действие |
|---|---|---|---|
| `QUIET-01` | **CAPTURED** | 2026-10-15, 120-sec host/guest, CPU, sample syscall | Доснять длинные повторения и строгую синхронизацию в QIO-01 |
| **`QIO-01`** | **NEXT — RESEARCH** | journald 1 982 writes/120sec | Найти log-producing units/events и установить физическую причинность |
| `QIO-02` | QUEUED | Portal 1 282 writes/120sec | Per-DB `fdatasync` и фоновая persistence matrix |
| `QIO-03` | QUEUED / DEPENDENCY HOLD | MicroK8s ~1 280 writes/120sec суммарно | Inventory pods/owners; никакого stop без approval |
| `QIO-04` | QUEUED / CORRECTNESS WATCH | NI-02B 404 writes; 46 029 pending; CPU 0,744 | Root cause retry churn без потери late attribution |
| `QIO-05` | QUEUED | Sensor 395 writes; empty spool | Разделить spool, network attribution и status writes |
| `QIO-06` | QUEUED | Traffic projection 222 writes; CPU 0,315 | 300s full reconcile — доказать cost/necessity |
| `QIO-07` | QUEUED | NI-04 34 writes CPU 0,342; Classification 29 writes CPU 0,426 | CPU/read hotspot Lab profile |
| `QIO-08` | QUEUED | Малые службы, NI-01 11 writes | Residual reevaluation после главных оптимизаций |

### Установленные, но не отменённые решения и отдельные требования

- **NI-01-A**: production ACTIVE после PR #209; **сохраняем**.
- **NI-01-B**: PR #210 rejected и не merged; **не возвращаем** без отдельного исследовательского открытия.
- Параметры восстановленного Fingerprint Sensor: отдельный persistent capacity override 160 MiB main / 192 MiB total (15.10.2026); **не откатывать** в рамках quiet-профилирования без осознанного incident/recovery решения.
- Исторические coverage gaps, provenance и fail-closed states сохраняют своё значение независимо от текущего «зелёного» systemd.

**Конец Roadmap v1.0. Следующий исполнительский шаг исследования: `QIO-01`, исключительно read-only.**
