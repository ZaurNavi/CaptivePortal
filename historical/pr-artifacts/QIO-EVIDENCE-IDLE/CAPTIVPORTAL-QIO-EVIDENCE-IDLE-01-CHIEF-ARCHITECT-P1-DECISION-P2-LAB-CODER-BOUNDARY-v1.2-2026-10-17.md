# CAPTIVPORTAL — QIO-EVIDENCE-IDLE-01
## Chief Architect P1 Decision / P2 LAB Coder Boundary v1.2

**Дата:** 2026-10-17 (Asia/Baku)  
**Адресат:** Performance & Optimization Tech Lead / Owner  
**Источник:** `QIO-EVIDENCE-IDLE-01-L0-ARCHITECT-MEASUREMENT-HANDOFF-2026-10-17(2).md`, прежний Chief Architect contract v1.1 и read-only source review.  
**Scope:** исключительно старая LAB VM `192.168.0.202` (QEMU `Ubunt`, host `omv-hp:/dev/sda`) и Fingerprint Evidence. **Не трогать** новый `captiv-prod`, Network Metadata и никакие соседние DB/сервисы.

## 1. Вердикт

**DECISION=MODIFY / ARCHITECTURE_DIRECTION=PASS / P2_LAB_PROTOTYPE=GO_CONDITIONAL / P2_FAST_READY=HOLD.**

Архитектор подтверждает реальный источник чрезмерного *cold-start physical read pressure* и утверждает последовательность дальнейшей инженерной работы. Tech Lead может составить **одно ограниченное ТЗ Coder для изолированного LAB-прототипа проверки эквивалентности/стоимости** по §5. Это **не** разрешает изменить production-путь готовности, пропускать проверки или выполнять deployment. Кодер приступает только после явного Tech Lead TASK/GO с точным исходным SHA/tree и allowlist.

**Не утверждено:** metadata-only startup за 3.5 с как безопасная замена; trusted fast path для живой 3.8-GB DB; отмена полной проверки `quick_check` при рестарте; физическая экономия HDD от будущего варианта. Текущий полный `quick_check` имеет `PENDING`, а не `PASS`.

## 2. Принятые измерения и ограничения причинности

Лабораторный Evidence v2: 3,796,074,496 bytes / 926,776 pages × 4096; allocator `last_ingest_sequence=2,834,788`; pinned LAB source `810484e69baa371c4696c3b46654199631538fc4`.

| Полный штатный этап | Результат L0 | Wall time | Process read_bytes |
|---|---|---:|---:|
| metadata/schema/storage-state | PASS | 0.003 s | 0 |
| Evidence: `typeof(ingest_sequence)`/bounds/allocator | PASS | **148.402 s** | **41,791,488** |
| Source Health: same guard | PASS | 0.106 s | 36,864 |
| Evidence↔Source Health collision `JOIN` | PASS | 1.252 s | 4,096 |
| `PRAGMA quick_check` | **NOT YET VERIFIED** | unknown | unknown |

Во время Evidence guard: host HDD completed reads ~85.77/s, busy ~93.05%; во время ongoing `quick_check` ~75.31/s, busy ~93.22%. Числа guest/host интервалов не строго идентичны. A/B/A запуска только Evidence: host reads 2.64→56.20→3.31/s. Эти данные поддерживают *read-pressure* и не доказывают экономию writes или единоличное владение всеми host I/O.

**Задокументировать после завершения:** буквальный полный результат `quick_check` (только `[('ok',)]` = PASS), timestamp окончания, wall/CPU/IO deltas, source snapshot/WAL identity. Продолжающийся процесс, SIGTERM, progress counters, `quick_check(1)` и корректный schema preflight не заменяют `ok`.

## 3. Архитектурная граница доверия: E1–E4 остаются нормативными

### 3.1. Состояния допуска

`UNINITIALIZED → METADATA_VALIDATED → HISTORICAL_VALIDATING → HISTORICALLY_TRUSTED → EVIDENCE_READY`. Ошибка/прерывание в любой обязательной проверке ⇒ `UNAVAILABLE / NOT_READY`, приём ingest запрещён; нет ложного `ready`, HTTP 200, нового watermark или успешного health. Отдельный необслуживающий readiness/status endpoint, если потребуется для диагностики, не означает разрешение писать или делать исторические запросы.

На **существующем однобазовом хранилище** `HISTORICALLY_TRUSTED` возможно только если:

- **T1 (действует сейчас):** на согласованном и подтверждённом состоянии live DB/WAL **полностью успешно** выполнены все требуемые текущие проверки, включая full `PRAGMA quick_check`, точный schema signature и три семантических sequence guards, либо их **доказанные эквиваленты**.
- **T2 (отдельное будущее решение, HOLD):** существует доказанная непрерывная криптографическая/транзакционная цепочка доверия исторической DB. Ни `mtime`, ни UUID generation, ни allocator, ни `data_version`, ни hash только manifest, ни quick bounds probe не гарантируют отсутствие повреждения произвольной нечитанной страницы. Подмена T1 ими запрещена.

**Невозможное требование:** обнаружить произвольную silent corruption в любой из 926,776 страниц **до** приёма данных, при этом вообще не прочитать исторические страницы или не иметь другой независимо доверенной структуры. Это нельзя объявлять эквивалентной O(1) проверкой. Если желаема более слабая политика обнаружения ошибок, требуется **новое явное Owner risk decision**, не автоматическое следствие лабораторного GO.

### 3.2. Неизменные семантические инварианты

- Точный SQLite schema/version/table/index/CHECK signature; корректные storage generation и allocator.
- `ingest_sequence` у каждой сохранённой записи — целое, >=1 и <= durable allocator; отсутствие повторов **внутри каждой** таблицы и **между** Evidence и Source Health.
- Глобальная последовательность не обязана быть непрерывной: retention удаляет старые факты. `MAX(seq)==allocator` для оставшихся строк **не обязателен**.
- Source event idempotency/immutable conflict, atomic event + `last_ingest_sequence` update, crash/replay, safe WAL, отсутствие ложной авторизации/классификации и Source Health.
- `quick_check` проверяет не то же, что `integrity_check`: официальный SQLite прямо указывает, что `quick_check` не проверяет UNIQUE и согласованность содержимого индекса и таблицы. Значит, одни быстрые index min/max **не являются** доказательством исторической целостности или отсутствия коллизий. Существующий набор проверок имеет разные обязанности; тестировать каждую независимо.

**Обработка ошибок:** `SQLITE_BUSY`, `IOERR`, `CORRUPT`, `FULL`, timeouts, несовместимая схема, убитый аудитор ⇒ typed failure / explicit HOLD. Не устраивать неограниченный systemd restart storm и не перезапускать готовый сервис по таймеру ради очистки ошибки. Не выполнять silent recovery/delete/recreate/reindex на исходной БД.

## 4. Выбор инженерной стратегии

### Выбранный немедленный шаг: P2-LAB-01 «exact-validation performance prototype»

**Разрешить одно узкое изолированное исследование алгоритмической стоимости конкретных legacy guards**, прежде всего Evidence scan 148.4 s, **с сохранением штатной границы допуска**. Этот этап может закончиться результатом «невозможно ускорить с эквивалентной детекцией» — это честный исход.

Экспериментировать с:

1. Отдельным исполнением каждой legacy проверки в **одном согласованном SQLite snapshot**, с её точным output и ошибками. Во время реального LAB-базового аудита авторитетен legacy validator.
2. Candidate SQL/index-подходами к Evidence sequence guard (строго отдельная research-функция), анализируя `EXPLAIN QUERY PLAN`, реальный VDBE/SQL и физический HDD read delta. Любой индекс/триггер/материализованный guard требует самостоятельного доказательства покрытия **существующих исторических строк**, правил поддержания на *каждом committed write*, противодействия сторонней записи и цены дополнительного write I/O. Не мигрировать исходную 3.8-GB DB без отдельного Owner LAB mutation GO; работаем на disposable clone/fixture.
3. Точными отрицательными fixtures, опровергающими «быстрое» приближение: неверный тип с арифметически допустимым значением, значение выше allocator, положительный/нулевой/отрицательный диапазон, duplicate/collision, повреждённый индекс или CHECK, missing WAL, valid retention gaps. **Одно несовпадение legacy vs candidate ⇒ candidate REJECT**.
4. Сравнением полного T1 elapsed и всех фаз: если `quick_check` остаётся многоминутным, устранение 148-s guard **не является решением всей проблемы cold-start**, хотя может уменьшить стоимость.

**НЕ выбрано для реализации в этом TASK:** `initialize(): deep_validation=False`, env bypass, `quick_check(1)` как sampling, MIN/MAX вместо typeof/global checks, «аудит когда-нибудь потом» и однобазовое принятие ingest до historical trust. Не вводить production feature flag такого назначения.

### Архитектурный путь к реально быстрому ready: отдельный предмет проектирования

Если T1 невозможно ускорить достаточно, архитектурный устойчивый вариант — **разделить независимую небольшую durable ingress/trusted hot generation и исторический store с отдельным статусом его проверки**. Тогда новый ingest может иметь собственную завершённую trust boundary, не притворяясь, что старые 3.8 GB уже доверены. Это **не разрешено к кодированию** в P2-LAB-01: потребует отдельного контракта на global ingest sequence, durable acknowledgement, дедупликацию с историей, приоритет Source Health, UI/reader availability, crash/replay, retention, migration и rollback. Простое раннее открытие HTTP при сохранённой старой семантике запрещено.

## 5. Контур ТЗ для Coder: ровно один P2-LAB-01

**Имя:** `QIO-EVIDENCE-IDLE-01-P2-LAB-01-EXACT-VALIDATOR-PROTOTYPE`.

**База:** код `810484e69baa371c4696c3b46654199631538fc4` и точный tree SHA — Tech Lead подтверждает при TASK; не подменять GitHub `main` или production HEAD. `research`/tests в отдельном LAB worktree; никакой замены работающего сервиса.

**Allowlist (Tech Lead фиксирует по содержимому исходного tree):** новый однозначно именованный research-only модуль/скрипт в `research/qio_evidence_idle_01/` и focused tests в `tests/device_fingerprint/test_repository.py` **или** отдельный тестовый файл в таком же namespace. Изменение `app/device_fingerprint/repository.py` допускается **только после второго адресного Tech Lead/Architect review**, если требуется production-facing refactor; исходный `initialize()` в этом P2-LAB-01 не трогать. Никаких иных runtime/config/systemd/SQLite path изменений.

**Обязательные результаты Coder:**

- Exact diff+patch SHA256 и candidate tree; source base SHA/tree; allowlist; без commit/push/PR.
- Лабораторный read-only baseline runner исходных предикатов и candidate runner на disposable DB, отдельные `stage result/error`, wall time, VDBE/SQLite profile, guest/host HDD counters с явной атрибуцией и uncertainty.
- Таблица legacy ↔ experimental outcomes на валидных и adversarial fixtures, включая silent corruption vs partial index discrepancy; статические `EXPLAIN` планы.
- Focused Linux+Windows-compatible tests (Coder only), без ослабления существующих asserts, skip/xfail и watchdog-маскировки.
- Explicit report: доказана ли **полная семантическая эквивалентность** guard при всех заданных повреждениях и сколько host physical reads / времени реально убрано в matched A/B/A на LAB VM/HDD. Если нет — `FAIL/UNKNOWN`, не PASS.

**STOP:** существенные изменения schema/retention; изменение PRAGMA WAL/`synchronous`; подключение к действующему `captiv-prod`; попытка использовать оригинальную Evidence DB для corruption injection; тайный config feature flag; ingest после `metadata_only`; потеря старого поведения UNIQUE/cross-collision; недоступность full quick_check result при заявке на operational fast-ready.

**Tech Lead владеет:** независимая репликация exact candidate tree, полные Windows/Linux regressions, root/POSIX, corruption/WAL/recovery, адверсариальные fixtures, реальный HDD matched performance; Coder — исключительно focused/compile/diff и handoff. Отдельной организационной роли QA нет.

## 6. Обязательные acceptance gates L0→L3

| Gate | PASS условие | Текущее состояние |
|---|---|---|
| L0 full check | `quick_check == ['ok']` полностью, измерено время/IO и snapshot идентичность | **PENDING**, не PASS |
| L1 scope & semantics | все исходные predicates, схемы, error categories, storage limits/retention и consumers подтверждены на pinned tree | Частично; P2 research может дополнять |
| P2-LAB-01 Coder focused | конкретный research-only алгоритм + отрицательные fixtures; нет runtime изменений | **GO только после Tech Lead TASK** |
| P2 trust-equivalence | full deep-invariant coverage, crash/restart/WAL, CHECK/type/range, cross-table collision, no false ready | **HOLD** до доказательств |
| Performance | matched physical HDD reads/await/busy, нет ложной causal attribution, ускорение полного trusted startup | **NOT PROVEN** |
| Release/production | full TL acceptance, publication/merge/Owner GO отдельно; `captiv-prod` не использовался | **NO** |

### Minimal negative matrix, additive to prior C01–C20

- N01 valid empty v2 / N02 valid large v2 / N03 valid retention gaps;
- N04 invalid `typeof=real` with in-range numeric value / N05 text/blob/NULL sequence / N06 seq<=0 / N07 seq>allocator;
- N08 intra-table duplicate index/record / N09 cross-table collision;
- N10 schema CHECK text altered / N11 index missing/wrong/index entry mismatch;
- N12 damaged b-tree page / freelist / record; N13 WAL committed not checkpointed; N14 WAL missing/truncated/swapped;
- N15 crash during separate event+watermark COMMIT; N16 recover/replay idempotent; N17 busy/IOERR/interrupted deep audit;
- N18 altered external writer / generation rollback / stale manifest; N19 physical HDD load cold/warm; N20 both source families + API availability invariant.

**Correctness priority:** same legacy PASS/REJECT, no accepted event lost, no false historical clean; a faster result that rejects valid DB or accepts damaged DB fails. Some synthetic physical corruption requires correct handling without undefined SQLite tampering; record fixture injection steps.

## 7. Required handoff from Tech Lead before any fast-ready Coder TASK

1. Completed full `quick_check` and its wall/IO/log/result; no inference from pid still alive.
2. Exact proposed trust algorithm `T1'` or independently justified `T2`; method to ensure same snapshot/WAL provenance and explain corruption coverage not retained if any.
3. Precision evidence from candidate guards on all negative fixtures, plus performance of the **full trusted startup**, not one SQL statement alone.
4. If policy intentionally changes from deep-before-ready, **new Owner risk decision** and separate architectural review. This P2-LAB-01 is not that GO.

## 8. Machine-readable disposition

```ini
TASK=QIO-EVIDENCE-IDLE-01
ARCHITECT_VERSION=v1.2
DECISION=MODIFY
ROOT_CAUSE=CONFIRMED_COLD_START_READ_PRESSURE
LAB_TARGET=192.168.0.202
LAB_HOST_DISK=omv-hp:/dev/sda
BASE_SHA=810484e69baa371c4696c3b46654199631538fc4
L0_SEQUENCE_GUARDS=PASS
L0_FULL_QUICK_CHECK=PENDING_UNVERIFIED
P2_RESEARCH_ONLY_LAB_CODER_TASK=CONDITIONAL_GO_AFTER_TECHLEAD_TASK
P2_PRODUCTION_FACING_FAST_READY=HOLD
T1_DEEP_BEFORE_READY=RETAINED
T2_TRUST_ATTESTATION=UNPROVEN_HOLD
METADATA_ONLY_ACCEPT_INGEST=FORBIDDEN
LAB_FULL_SCAN_AND_HEAVY_IO=OWNER_AUTHORIZED
CODER=HOLD_UNTIL_NARROW_LAB_TASK
MERGE=NO
PRODUCTION_CHANGES=NO
CAPTIV_PROD=DO_NOT_TOUCH
NETWORK_METADATA=OUT_OF_SCOPE
PHYSICAL_HDD_WRITE_SAVINGS=NOT_CLAIMED
```

**Owner-readable conclusion:** подтверждён дорогой индексный полный проход (~148 с) и тяжёлый `quick_check`. ТЗ на изолированную лабораторную проверку конкретных эквивалентных алгоритмов можно выпускать сейчас. ТЗ на замену обязательной проверки целостности короткой метаданной **пока нельзя**: доказательств недостаточно и модель отказа изменится.

## References

- Tech Lead L0 handoff, 2026-10-17, user-attached; previous Chief Architect v1.1.
- `ZaurNavi/CaptivePortal` pinned source `810484e69baa371c4696c3b46654199631538fc4`, `app/device_fingerprint/repository.py`, `app/device_fingerprint/schema.py`.
- SQLite `quick_check` & `integrity_check`: https://www.sqlite.org/pragma.html#pragma_quick_check
- SQLite WAL & recovery: https://www.sqlite.org/wal.html
