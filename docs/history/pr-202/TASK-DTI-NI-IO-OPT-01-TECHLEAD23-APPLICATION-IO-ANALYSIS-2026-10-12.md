# CAPTIVPORTAL — TECHLEAD23
# TASK-DTI-NI-IO-OPT-01 — Application Write-Path Investigation / Preliminary Verdict

**Дата:** 2026-10-12  
**Статус:** READ-ONLY SOURCE INSPECTION + ограниченная LIVE telemetry; **не** окончательное performance admission.  
**Исходные данные:** `TASK-INFRA-IO-01-FINAL-ROOT-CAUSE-REPORT-2026-10-12.md` (SysAdmin, 2026-10-12).  
**Source / production:** `ZaurNavi/CaptivePortal`, `main@88541da8d6952cb91fc945b7f77efcf7e5c46420`, tree `d879f5113319c334faf2bf9ae7b8bea7cfdc977e`.  
**Правила:** NO production application code/config/schema/PRAGMA/service/storage maintenance; NI-05/NI-06 HOLD до отдельного решения Owner. Любые runtime изменения — Owner-approved change plan.

## 1. TL;DR для Owner

Проблема похожа не на «слишком много мегабайт», а на **слишком частые мелкие, синхронно сохраняемые записи** разных систем на одном старом HDD. Система должна и сохранять наблюдение, и запоминать, до какого места обработала источник, и привязывать факт к устройству, и резервировать доказательства Fingerprint. В текущей архитектуре это несколько SQLite-хранилищ и логов, каждый со своей логикой надёжности.

**Обнаружены три главные точки для изучения сокращения write IOPS:**

1. NI-01: `FULL` durable SQLite transactions на пакет до 256 событий и многотабличный/indexed record-per-observation; реальная средняя наполненность пакета в короткой свежей выборке — около 49 событий.
2. NI-02B: каждые 1 сек. выполняется tick; **даже пустой poll пишет обновление `projection_runtime_state` в транзакции**; после каждой транзакции — `PRAGMA wal_checkpoint(PASSIVE)` через `maintain_capacity()`.
3. Fingerprint Sensor: SQLite transport spool использует `journal_mode=DELETE` + `synchronous=FULL`, с отдельными enqueue и acknowledge/delete; частота этих транзакций потенциально зависит от количества нормализованных событий/поставок.

Изменение этих механизмов затрагивает долговечность, воспроизводимость, freshness или delivery. **Архитектурный HOLD; не менять их настройкой «на глаз».**

## 2. Измеренные физические факты SysAdmin (сохранить ограничения)

`omv-hp` / HP ProLiant DL180 G6 / KVM; Ubuntu VM `Ubunt` vda → `/UbuntVM/Ubunt.qcow2` → хост ext4 `/dev/sda1` → один физический SATA HDD `/dev/sda` (MB2000GCWDA, 1.8 TiB). Windows VM и процессы самого хоста тоже используют `/dev/sda`.

* В синхронном окне 85.38 с `/dev/sda`: 143.98 write IOPS, 1835.28 KiB/s, 120.52 ms write await, 92.40% util.
* Ubuntu VM: 1524.79 KiB/s и 122.54 write IOPS на host cgroup устройства 8:0 — **83.08% физически атрибутированных write bytes и 85.11% операций** в данном окне; это **не** доля seek-time.
* В отдельном 121.13-секундном срезе guest vda: 1435.25 KiB/s, 128.82 write IOPS, 223.23 ms write await, 92.52% util.
* На физическом устройстве не выявлено аппаратных ошибок по SMART в проверенном окне. Наработка 72790 часов; SMART PASSED не означает достаточную производительность.
* Прямое совпадение I/O с конкретными NI-01 ingest lag и NI-04 deadline в одном UTC-окне **не доказано** (`ROOT_CAUSE_STATUS=PARTIALLY_PROVEN`).

### Top-10 guest vda / cgroup 252:0, 121.13 с

| Rank | Сервис | Write KiB/s | Write IOPS |
|---:|---|---:|---:|
| 1 | `network-metadata.service` (NI-01) | 428.34 | 28.38 |
| 2 | `fingerprint-sensor.service` | 178.36 | 20.64 |
| 3 | `network-metadata-projection.service` (NI-02B) | 140.15 | 15.15 |
| 4 | `systemd-journald.service` | 77.14 | 16.16 |
| 5 | `fingerprint-evidence.service` | 65.52 | 4.80 |
| 6 | `captive-portal.service` | 50.13 | 10.21 |
| 7 | `snap.microk8s.daemon-k8s-dqlite.service` | 26.75 | 2.05 |
| 8 | `snap.microk8s.daemon-containerd.service` | 23.15 | 5.75 |
| 9 | `fingerprint-classification.service` | 4.89 | 0.99 |
| 10 | `cron.service` | 4.49 | 0.68 |

Три основных сервиса NI-01/Fingerprint Sensor/NI-02B в этом guest окне дают 746.85 KiB/s и 64.17 write IOPS (примерно 52.0% write bytes и 49.8% write IOPS гостевого vda). Остальная нагрузка не является «бесплатной»: journald, Fingerprint Evidence, Portal, microk8s также существенны. Нельзя целиком приписывать journald одному сервису.

## 3. Что именно пишет приложение (подтверждение исходным кодом)

### A. NI-01 — Network Metadata Foundation

Code: [`app/network_metadata/repository.py`](https://github.com/ZaurNavi/CaptivePortal/blob/88541da8d6952cb91fc945b7f77efcf7e5c46420/app/network_metadata/repository.py), [`service.py`](https://github.com/ZaurNavi/CaptivePortal/blob/88541da8d6952cb91fc945b7f77efcf7e5c46420/app/network_metadata/service.py), [`schema.py`](https://github.com/ZaurNavi/CaptivePortal/blob/88541da8d6952cb91fc945b7f77efcf7e5c46420/app/network_metadata/schema.py).

- Writer: SQLite `journal_mode=WAL`, `synchronous=FULL`, `wal_autocheckpoint=1000`, `journal_size_limit=64 MiB`. `transaction()` = `BEGIN IMMEDIATE` → code → `COMMIT` (`repository.py:50–100`).
- На каждое нормализованное событие `_observation()` записывает минимум `network_metadata_observations` и `network_metadata_source_records`, а для retained endpoints — `network_metadata_sensitive_endpoints`, плюс таблицу семейства DNS/TLS/QUIC и потенциальные дочерние DNS answer/query или TLS ALPN. Индексы и constraints требуют дополнительной работы.
- **Это не транзакция на каждый пакет:** `ingest_batch()` проводит эти inserts атомарно на **пакет** (до 256) вместе с обновлением source generation / checkpoint, preserving replay identity. `service.py` сразу обрабатывает следующий пакет, если предыдущий сделал полезную работу; ждёт 1 сек. только когда работы нет.
- Production ENV read-only: `NETWORK_METADATA_BATCH_MAX_RECORDS=256`, `NETWORK_METADATA_BATCH_MAX_BYTES=1048576`, `NETWORK_METADATA_POLL_INTERVAL_SECONDS=1`, `NETWORK_METADATA_MAX_DB_BYTES=51539607552`.
- LIVE read-only journal sample (последние 5 минут в момент запроса): **83 `batch_committed` / 4053 observation records**, средний count **48.83**, max **256**; cadence и распределение не фиксированы, это короткое окно, не нагрузочное испытание.
- `persist_health()` вызывает обёртку транзакции при поллах, но health row добавляется лишь при состоянии/60-секундном heartbeat (`health.py:137–151`). **Не утверждать, что пустые транзакции создают каждую секунду физическую запись.**
- `wal_maintenance()` может выполнять PASSIVE/TRUNCATE checkpoint при retention/размере WAL >64 MiB или пороге footprint; retention раз в ~3600 c. **Причина всплесков WAL/checkpoint не измерена.**

**Гипотеза A1 (приоритет высокий):** изучить неполные пакеты/группировку с допустимой краткой latency budget — без потери checkpoint/replay semantics.  
**A2:** профилировать стоимость индексов/таблиц, retention и PASSIVE/TRUNCATE частоту; нельзя выбросить evidence fields без архитектуры.  
**A3:** проверить, сколько временных event-at → ingested-at лагов вызвано собственным буфером Suricata, очередью, CPU, HDD; не считать, что рост batch size автоматически решает lag.

### B. NI-02B — Device-relative Projection

Code: [`repository.py`](https://github.com/ZaurNavi/CaptivePortal/blob/88541da8d6952cb91fc945b7f77efcf7e5c46420/app/network_metadata_projection/repository.py), [`service.py`](https://github.com/ZaurNavi/CaptivePortal/blob/88541da8d6952cb91fc945b7f77efcf7e5c46420/app/network_metadata_projection/service.py).

- SQLite `WAL`, `synchronous=FULL`, `wal_autocheckpoint=1000`.
- Production ENV: `...PROJECTION_POLL_INTERVAL_SECONDS=1`, `...BATCH_MAX_OBSERVATIONS=256`, `...REGISTRY_RECONCILE_INTERVAL_SECONDS=60`, retention `3600`.
- **Подтверждённый по коду кандидат:** `poll()` при пустом source batch вызывает `with repository.transaction(): repository.success_state(source_verified=True,last_source_poll_at=...)`; `success_state()` → `runtime()` → SQL `UPDATE projection_runtime_state`. То есть idle loop не просто читает, но обновляет durable poll timestamp.
- `transaction()` после COMMIT всегда вызывает `maintain_capacity(post_commit=True)`, в котором выполняется `PRAGMA wal_checkpoint(PASSIVE)`. TRUNCATE — только под capacity pressure. Частота вызовов ≠ доказанная частота физических checkpoint writes; требуются measurements.
- `commit_dispositions()` не просто кэш: сохраняет DeviceNetworkMetadataEdge и source checkpoints, batch at most 256, также binding/reconcile. Оптимизация должна сохранить temporal attribution, registry authority, immutability, fail-closed.

**Гипотеза B1 (высокий приоритет):** отдельно измерить и архитектурно согласовать уменьшение частоты durable *no-new-data poll* записей и PASSIVE-checkpoint checks.  
**B2:** измерить per-batch commits, регистровые reconcile/retention и точное влияние на IOPS/latency.

### C. Fingerprint Sensor — protected critical program

Code: [`spool.py`](https://github.com/ZaurNavi/CaptivePortal/blob/88541da8d6952cb91fc945b7f77efcf7e5c46420/app/device_fingerprint_sensor/spool.py), [`runtime.py`](https://github.com/ZaurNavi/CaptivePortal/blob/88541da8d6952cb91fc945b7f77efcf7e5c46420/app/device_fingerprint_sensor/runtime.py).

- Класс `SensorSpool` — локальная ограниченная SQLite-очередь доставки Evidence/SourceHealth: `journal_mode=DELETE`, `synchronous=FULL`.
- `runtime._raw_loop()` вызывает `spool.enqueue()` для нормализованных событий из кадров; `_eve_loop()` — для нормализованных Suricata событий. `_delivery_loop()` выдаёт пакеты, а `producer.deliver_once()` после успеха вызывает `spool.acknowledge()` (удаление доставленных строк).
- Spool имеет отдельные транзакции INSERT, DELETE, stale purge, capacity checks; каждый durable write на HDD может быть сравнительно дорогим.
- **Не доказано**, что синоним «каждый raw packet» означает «одна durable транзакция на каждый пакет»: нормализатор может вернуть пустой набор событий; реальные counts не измерены.
- **ВНИМАНИЕ:** Sensor/Fingerprint — защищённый путь со своим владельцем контракта. Изменение режима SQLite, накопления, удаления, частоты delivery и аварийного восстановления — отдельная архитектурная admission.

**Гипотеза C1:** выяснить транзакции enqueue/ack/purge и их fsync на операционном уровне, проверить безопасные bounded batches.  
**C2:** сравнить DELETE vs WAL / журналирование только в изолированном тестовом окружении с crash/replay/rejection тестами; никакой production PRAGMA-тюнинг сейчас.

### D. Journald, Fingerprint Evidence, Portal и microk8s

- `journald` — физический guest write contributor 77.14 KiB/s / 16.16 IOPS; он принимает журналы разных сервисов. NI-01 телеметрия `batch_committed` — на каждый успешный batch; NI-02B тоже эмитирует `batch_committed`; Sensor — delivery/status telemetry. **Источники journald write по единицам и exact fsync не атрибутированы.** Отбрасывать health/audit logs без контракта нельзя.
- `fingerprint-evidence` и `captive-portal` остаются самостоятельными I/O участниками; нуждаются в отдельном точечном sample их SQLite/files/transaction patterns, без вмешательства в Auth/CAPPORT.
- `microk8s-dqlite` и `microk8s-containerd` суммарно ≈49.90 KiB/s в указанном срезе; SysAdmin должен установить их business ownership и допустимость будущего выключения, но **теперь ничего не отключать**.
- В live запросе journald last-5-min events доступен для NI-01 (83 batch/4053 records); для NI-02B и Sensor за это окно записи не получены. «Нет журналов» **не означает «нет I/O»**: cgroup write атрибуция сильнее.

## 4. Почему нельзя просто увеличить batch или перевести FULL → NORMAL

`FULL` / WAL / durability, source checkpoint ↔ committed observations, immutable fingerprint evidence, temporal attribution и Site scoping — защитные гарантии. Меньше syncs может означать больше недосохранённых событий при crash, а реже heartbeat — менее правдивый freshness. Safe change — это явные tradeoffs, тесты повреждения/обрыва и Архитектор, а не «улучшение» конфигурацией прямо в production.

## 5. Следующий этап исследования (исключительно bounded read-only / lab)

| ID | Замер / вопрос | Где | Исполнитель | Выходной артефакт |
|---|---|---|---|---|
| P1 | Transaction count, COMMIT/s, fsync/s, WAL frame/checkpoint timing по NI-01 | Изолированная копия/lab; production — только безопасные внешние метрики после Owner gate | Coder+SysAdmin | NI01 transaction/latency table |
| P2 | Сколько idle poll tx и PASSIVE checkpoint checks у NI-02B, сколько writes реально вызывают | Source-level instrumentation в lab | Coder | NI02B idle-vs-busy comparison |
| P3 | Sensor spool SQLite insert/delete/ack rates и write amplification | Тестовый sensor/spool, без реального guest capture | Fingerprint owner + SysAdmin | Spool durable transport study |
| P4 | Разложение journald / Portal / Fingerprint Evidence I/O | SysAdmin с cgroup, journald и разрешёнными метриками | SysAdmin | Source-of-writes addendum |
| P5 | Одновременные UTC-метрики physical w_await, VM write IOPS, NI01 ingest lag, NI02B commit lag и NI04 read duration/timeout | Только согласованные low-overhead passive probes | SysAdmin+TechLead | Correlation matrix, causality limitations |
| P6 | Сравнить HDD-baseline и вариант выделенного SSD/другого устройства без перезапуска production | Отдельный lab/staging / storage plan | SysAdmin | Storage comparison |
| P7 | Оценить задержки сохранения, потерю после crash/restart, replay, retention/privacy, max queue при предлагаемых алгоритмах | Isolated lab / tests | Architect+QA | Safety gate |

Для P1-P7 надо отдельно замерить **bytes/s, write IOPS, fsync/s (где возможно), p95/p99 latency, capture drops, source backlog, replay correctness, disk footprint, NI04 deadline**, а не оптимизировать только по KiB/s.

## 5.1 Операционная оговорка

Текущая TechLead диагностика не меняла исполняемый код, базы, настройки или состояние служб. Для двух безопасных проверок структуры журналов на VM были **скопированы и выполнены диагностические Python-файлы** `/home/admin/techlead23-ni-io-journal-audit.py` и `/home/admin/techlead23-ni-io-journal-five.py`. Они читают ограниченное окно `journalctl`, не меняют конфигурацию; будущая уборка этих вспомогательных файлов допускается только по обычному операторскому процессу. Утверждение «вообще никаких файлов на сервере не создавалось» было бы неверным.

## 6. Решение Tech Lead / governance

```text
TASK = TASK-DTI-NI-IO-OPT-01
INVESTIGATION_MODE = SOURCE_REVIEW_AND_READ_ONLY_DIAGNOSTICS
SOURCE_FINDINGS = CANDIDATE_WRITE_AMPLIFICATION_PATHS_FOUND
ROOT_CAUSE_APPLICATION_DETAIL = NOT_YET_PROVEN
IO_STORAGE_BOTTLENECK = PROVEN_BY_SYSADMIN_IN_SAMPLED_WINDOWS
NI05 = HOLD
NI06 = HOLD
ARCHITECT_REVIEW_REQUIRED = YES
CODER_IMPLEMENTATION = HOLD
GIT_MERGE = NO
PRODUCTION_CONFIGURATION_CHANGE = NO
PRODUCTION_RESTART = NO
```

**Рекомендовано:** Архитектору дать bounded контракт; затем Coder делает сначала performance-test/harness на копии, отдельно предложения, а не готовую production правку. Owner решает последовательность развертывания/миграции. Параллельно SysAdmin готовит независимую ветку «отделение vDisk/SQLite I/O от общего HDD» как потенциальный более высокий ROI.

**Ссылки на исходный код:** точный неизменный commit `88541da8...`, URL приведены выше. Ни telemetry samples, ни cgroup snapshots не доказывают сами по себе сколько fsync следует на конкретную SQL-транзакцию.
