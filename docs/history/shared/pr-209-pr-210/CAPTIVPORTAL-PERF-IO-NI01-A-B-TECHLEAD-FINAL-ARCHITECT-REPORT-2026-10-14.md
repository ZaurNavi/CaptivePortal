# CAPTIVPORTAL — PERF-IO-NI01: итоговый отчёт Tech Lead Главному архитектору

**Дата:** 2026-10-14, Asia/Baku  
**От:** TechLead23  
**Кому:** Chief Architect, CaptivPortal  
**Решение Owner:** оставить пакет A в эксплуатации; пакет B признать неудачным направлением, прекратить разработку и закрыть PR #210 без merge. Дальнейшее исследование физического HDD I/O — measurement-first.

## 1. Итог и точный статус

**Пакет A / ingestion hotpath: IMPLEMENTED, MERGED, DEPLOYED, ACTIVE.** Его корректность и уменьшение ряда SQL-операций подтверждены. Экономия физических IOPS HDD на сопоставимой долговременной нагрузке **ещё не доказана**. Мы не утверждаем, что общая дисковая проблема решена.

**Пакет B / indexed retention: IMPLEMENTATION CORRECT, PERFORMANCE HYPOTHESIS NOT ACCEPTED, CANCELLED.** Даже после архитектурного исправления R3 лабораторная стоимость B=ON осталась выше исходного legacy-пути в исследованных сценариях. Отказ не является обвинением Coder в ошибке: контракт выполнялся, тесты пройдены; неверно было считать такую замену retention-селектора перспективной оптимизацией без доказанного end-to-end выигрыша.

На момент свежей проверки GitHub:
- PR **#209**: merged; production/source merge commit `018985edaa008847b64051dc49c90914d0a60238`, tree `b73f0ed2450e24b7fe4298630999f402a980cce1`.
- PR **#210**: **CLOSED / MERGED=false**, final candidate HEAD `fd6eb48d6326f40c51e85ca18fc1df9827e44118`, TREE `55c42fff98533dd66416bf49ae0b16bd4e11cae6`; comment: `CLOSED — ARCHITECTURAL APPROACH REJECTED / PERFORMANCE BENEFIT NOT DEMONSTRATED`.
- `main` остаётся на `018985ed…`. **В `main` и production нет кода B**. Никакой revert, чистка SQLite или рестарт для отмены B не требуются.
- Последний зафиксированный read-only production status после A=ON: NI-01 `usable/usable`; семь проверенных сервисов active; checkpoint продвигался. Это датированное наблюдение, не непрерывный health-monitoring.

## 2. Исходная задача и базовая доказательная база

Цель — **уменьшить бесполезные мелкие физические операции HDD**, особенно излишние чтения, записи, транзакции и fsync, не маскируя их SSD и не ослабляя сохранность данных. Перед реализацией было выявлено высокое I/O pressure на Ubuntu VM и физическом накопителе хоста.

Из Architecture Contract R2 / предшествующего исследования R1: на одном 60-секундном гостевом интервале NI-01 имел 2760 cgroup guest write ops (≈45,1 MB write bytes); NI-02B — 1283, fingerprint sensor — 1009, fingerprint evidence — 910; guest `vda` ≈93,3% busy. На **другом** временном интервале host `/dev/sda` был ≈91,4% busy, ≈168,7 write IOPS, а QEMU host-cgroup занимал ≈83,2% host completed writes. Эти окна **нельзя складывать, выдавать за один синхронный замер или целиком приписывать NI-01**.

Source review выявил точные источники логической работы: два per-record `identity_outcome` прохода, `PRAGMA table_info` на каждую вставку, отдельные fault UPSERT, retention SQL с `ORDER BY observation_id`. Но сам факт `SCAN` в `EXPLAIN` или большого числа SQL statements **не доказывает**, что конкретный запрос является главным генератором физических IOPS. R2 правильно содержал этот caveat; дальнейшие результаты требуют усилить именно причинную атрибуцию.

## 3. Пакет A: что сделано и что доказано

Реализация A (`e79e5b7…`, PR #209, затем merge `018985ed…`) внедрила один независимый флаг `NETWORK_METADATA_IO_HOTPATH_V1_ENABLED`, default OFF:

1. **A1 / generation-scoped range probe.** Для all-new batch вместо двух per-record identity-проверок выполняется один bounded index probe в preflight и **новый независимый probe внутри `BEGIN IMMEDIATE`**. Если диапазон пересекается с persisted row, всегда применяется исходный ordered per-record путь; конфликты, replay, первый blocked offset и checkpoint не ослаблены.
2. **A2 / validated immutable column allowlist.** После точной SQLite schema validation кешируются разрешённые table/column names на жизненный цикл connection; при close/recover snapshot сбрасывается. Это убирает hot-path `PRAGMA table_info` без разрешения произвольных SQL identifiers.
3. **A3 / grouped fault UPSERT.** Одинаковые fault categories/epochs аккумулируются только для реально достигнутого Phase-B prefix, записываются до checkpoint hook **в той же транзакции**; сохранены event-count telemetry, atomic commit и crash/replay semantics.

Количественный эффект **в логическом SQL**, подтверждённый Coder и проверками:
- All-new batch N=256: **512** per-record identity SELECT при OFF против **двух range probes и нуля per-record SELECT** при ON.
- Insertion `PRAGMA table_info`: **1451 → 0** в ON hot path для тестовой серии N=256 (при инициализации schema validation сохраняется).
- 256 faults одной группы: **256 UPSERT → 1**.
- Независимый WSL file-backed парный тест: медиана 256-record ingest **171,91 мс OFF → 137,67 мс ON** за пять чередующихся пар. При этом медианные `write_bytes` процесса примерно **651 264 байта** в обоих вариантах, и количество `syscw` также не показало снижения в этом fixture. Это *ускорение участка кода*, **не подтверждённая экономия HDD write IOPS**.

Quality: перед merge Tech Lead независимо получил **1488 PASS** для NI-01/NI-02B/NI-04. Полный Project Central Gate был начат и прерван; две analytics EXPLAIN-plan ошибки воспроизводились на старом baseline, следовательно не являлись A-regression. **Полный Central Gate PASS не заявляется.**

**Production:** A развернули с OFF, проверили loaded commit, затем включили ON. Старт NI-01 при высокой дисковой нагрузке оказался длительным; ошибка первоначальной процедуры Tech Lead — проверка процесса слишком рано после `systemctl restart` (`Type=simple` ≠ application-ready). Преждевременные rollback/restart совпали со сменой EVE generation, диагностирована `source_replaced_while_reader_down`, `coverage_gap_possible=1` и `source_continuity_mismatch/partial` для закрытой generation. Этот исторический provenance/gap **нельзя замалчивать или искусственно «чинить» checkpoint**. После нового успешного запуска флаг `true` подтверждён в окружении, а новый ingest-run имел **изменённый** configuration digest `01d9bd16b95f58b8af79a3ce4b9e145ea4fc8eabd9a94977fbbbb668b2238f62`. В последней проверке текущий NI-01 health был `usable/usable`, checkpoint снова рос.

Системные краткие снимки не показали убедительного улучшения физических HDD IOPS: перед A=ON на разных 30-секундных интервалах guest `vda` ≈97–144 write IOPS при ≈94% busy; после включения ≈132 write IOPS при ≈95,7% busy. **Эти интервалы не workload-matched** (число клиентов/объём EVE и нагрузка других служб менялись); ни доказательство отсутствия выгоды, ни доказательство общей экономии. Owner оставляет A включённым для наблюдения. Никаких слепых переключений для коротких сравнений.

## 4. Пакет B: полная история и причины отказа

**R2 design.** Вместо исходного selector `(event_at < cutoff OR ingested_at < cutoff) [AND state!='expired'] ORDER BY observation_id LIMIT 5000` были предусмотрены две time-index range SELECT по `event_at` и `ingested_at`, каждый `LIMIT 5000`, затем dedup и сортировка глобального oldest-K. Для sensitive TTL = 14 дней, core TTL = 30 дней. В R2 прямо предупреждалось, что `LIMIT 5000` ограничивает возвращённые строки, но **не число просмотренных index entries**. Архитектура была принята **с обязательным performance gate**, а не как безусловно доказанное ускорение.

**Первая реализация R2.** Coder корректно создал Draft PR #210, первая версия HEAD `166a1546…`, целевые B-тесты **61 PASS**; Tech Lead независимо выполнил **1549 PASS** NI-регрессий. На 100 000 ранних `expired` и 5001 пригодных поздних строках sensitive SQL потребовал приблизительно **1,1 млн VM steps** против приблизительно **645 тыс.** у legacy. Индекс ищет по времени, а отбрасывает state, поэтому SQL выполняет много работы до набора 5000 eligible строк. Это подтвердило предусмотренный R2 adversarial risk.

**R3 architecture revision.** Chief Architect утвердил bounded raw-index lookahead, валидированное обнаружение первой expired-строки и **ровно один** fallback на старый sensitive selector, закрытие курсоров и разрешение legacy `observation_id` ordering при fallback. Режим B=ON/core остался прежним R2. Coder реализовал это follow-up commit `fd6eb48…` **в том же PR #210**. Целевые тесты Coder **193 retention/config + 12 crash/replay PASS**. Tech Lead независимо получил **1592 PASS**, diff/scope/AST проверены. **Ошибок корректности и нарушений SQLite invariants не найдено.**

**R3 performance — проблема не решена как бизнес-цель.** Raw lookahead ограничил вредную R2 state-filtered индексную амплификацию; на expired-prefix R3 с полным legacy fallback оказался около **645 тыс. VM steps**, то есть примерно равен legacy плюс малый пролог, против 1,1 млн R2. Но необходимость двух SELECT, чтения строк, Python-проверок canonical UUID/timestamps, дедупликации и сортировки дала дополнительные затраты в обычном случае. Независимая лаборатория Tech Lead, *file-backed базы, без инструментирования VM step callback, по три прогона на одинаковом fixture; миллисекунды, медиана*:

| Сценарий | Legacy OFF | R2 ON | R3 ON | R3 к legacy |
|---|---:|---:|---:|---|
| 20 тыс. eligible | 30,294 | 505,802 | 421,902 | около **13,9× медленнее** |
| 20 тыс. interleaved expired/eligible | 36,992 | 960,332 | 68,675 | около **1,86× медленнее** |
| 100 тыс. expired + 5001 eligible | 410,237 | 720,892 | 503,535 | около **22,7% медленнее** |

Результаты относятся к выбранным synthetic fixtures, небольшой серии, определённому SQLite/cache/CPU окружению: это **не прогноз процентов физического HDD I/O** для production и не универсальное утверждение про все нагрузки. Однако совокупности лабораторных данных достаточно, чтобы **отвергнуть архитектурную ставку B в рамках текущей цели**, не тратя дальнейшие циклы на R4, новые индексы и усложнение schema без новой причинной диагностики.

**Owner decision:** B **CANCELLED**, PR #210 **CLOSED WITHOUT MERGE**; никакой B-код или флаг не попал в production. Ветка, handoff, QA/benchmark evidence сохранены как неудачный эксперимент; не нужны revert коммиты и production рестарты. A остаётся включённым.

## 5. Какие архитектурные предположения надо пересмотреть

**Не утверждаю, что Chief Architect проигнорировал ограничения:** R2 *правильно* требовал adversarial performance test и прямо отделял SQL-cost от физических IOPS. R3 *правильно* документировал, что fallback не гарантирует стоимости ниже legacy. Ошибкой оказалась именно **исходная гипотеза выгодности B**, допущенная к реализации при недостаточном подтверждении, что retention вообще значимый contributor host HDD I/O. Последующая попытка R3 исправила частный worst-case, но **не доказала выигрыш относительно лучшего контрольного варианта — не менять работающий legacy selector**.

Требуемая корректировка инженерного подхода:

1. **Оптимизировать измеренный причинный источник физических I/O**, а не любой запрос с `SCAN` или высоким количеством SQL statements.
2. **Control = текущий корректный путь**, а не только предыдущий экспериментальный R2. R3 < R2 — недостаточно, если R3 > legacy.
3. **Измерять полную операцию**, включая fallback, validation, dedup, sorts, transaction, commit и checkpoint, а не только query plan/probe.
4. **Различать уровни:** SQLite VM steps/SELECTs/latency, Linux process/cgroup I/O, guest vda и host physical device. Значение одного уровня не является механически величиной другого.
5. **Дешёвый обратимый эксперимент отвергать рано**, когда контрольный baseline явно лучше. Не следует создавать R4 только ради спасения уже отвергнутого B.
6. **Корректность ≠ эффективность:** 1592 PASS подтверждают поведение, не полезность для HDD.

## 6. Новое задание Главному архитектору — исследование, не implementation TASK

Прошу подготовить **PERF-IO NEXT INVESTIGATION / MEASUREMENT-FIRST ARCHITECTURE DIRECTIVE**, не немедленный Coder TASK. Цель — установить, какие компоненты и механизмы реально создают физические мелкие HDD I/O, и только потом выбрать следующий узкий пакет.

Минимальные исследовательские вопросы:

**Атрибуция I/O:** одновременно и преимущественно read-only измерить гостевые `vda`, host physical disk и QEMU/cgroup с согласованными окнами; NI-01, NI-02B, NI-04, fingerprint sensor/evidence, SQLite WAL/checkpoint, logging, остальные существенные VM/services. Separate reads/writes, completed ops/bytes, await/queue/busy, PSI, source EVE ingest rate, checksum/backlog/checkpoint progression. Не складывать разновременные данные и не приписывать общий диск NI-01.

**Нормализация:** учитывать число пользователей/AP, объём пакетов/NetFlow/EVE, поступившие bytes/records, committed observations, faults, source generation changes, retention tick/выполненные операции и отдельно TTL background cleanup; строить сопоставимые интервалы разной нагрузки и смотреть **I/O per accepted record**, I/O per event и изменения за часы, не по одной минуте.

**Обоснование следующей цели:** составить ранжированный перечень реальных small-I/O источников с evidence и обратимостью: частота COMMIT/fsync и WAL autocheckpoint; duplicated polling/re-reads; избыточные записи derived/materialized состояний; churn журналирования/телеметрии; фактические heavy read queries (retention только если виновность подтверждена). Для каждого — оценка доли **физического**, не просто логического I/O.

**Контракт безопасности:** source-of-truth vs derived separation; durable checkpoint не обгоняет фактически durable data/replay; неизменные replay/idempotency, SQLite FULL/WAL, canonical schema, TTL, privacy, single-writer и downstream NI-02B/NI-04; допускаются только доказуемые безопасные batching, cache, устранение пустых транзакций/лишних COMMIT, материализация результатов при поступлении данных. Никаких слепых `synchronous` PRAGMA, SSD как маскировки, новых миграций/демонов/индексов без нового contract и достаточного evidence.

**Необходимый выход архитектора:**
- Root-cause matrix: процесс → конкретная операция → логический SQL/файл → guest I/O → host физический I/O, с указанными пробелами доказательств.
- Один или несколько **измеримо приоритетных** вариантов; контрольное сравнение с current A-ON/legacy retention; прогноз только диапазоном с условиями и ясными критериями опровержения.
- Отдельные Lab-only reproducible gates, осмысленный no-op/negative-control, safety/rollback и Owner activation boundary.
- Право вернуть `NO SAFE OPTIMIZATION IDENTIFIED`, если доказательств пока недостаточно.

**Никаких новых Coder GO, merge, production tests или рестартов этим отчётом не разрешается.** Owner выбирает следующий приоритет после нового evidence review.

## 7. Финальный реестр решений

```text
TASK=PERF-IO-NI01
A=IMPLEMENTED_MERGED_PRODUCTION_ACTIVE
A_CORRECTNESS=PASS_NI_INDEPENDENT_1488
A_SQL_REDUCTION=PROVEN_IN_LAB
A_PHYSICAL_HDD_IO_REDUCTION=NOT_ESTABLISHED
A_PRODUCTION_CHANGE_NOW=NO
B=REJECTED_AS_OPTIMIZATION_CANCELLED
B_SOURCE_CORRECTNESS=PASS_NI_INDEPENDENT_1592
B_PR=210_CLOSED_UNMERGED
B_PRODUCTION=NEVER_DEPLOYED
B_REWORK_R4=NO
ARCHITECT_NEXT=MEASUREMENT_FIRST_PHYSICAL_IO_ROOT_CAUSE
CODER_GO=NO
PRODUCTION_TESTS=NO
OWNER_MERGE_DEPLOY_ACTIVATION_AUTHORITY=RESERVED
```

## 8. Evidence / source register

1. `CAPTIVPORTAL-PERF-IO-NI01-ARCHITECTURE-CONTRACT-R2-FINAL-TECHLEAD-2026-10-14.md` — нормативный исходный контракт и ограничения доказательств.
2. `PERF-IO-NI01-A-CODER-TASK-v1-2026-10-14.md`, `HANDOFF(2).md`, PR [#209](https://github.com/ZaurNavi/CaptivePortal/pull/209) — реализация и focused tests A.
3. `CAPTIVPORTAL-PERF-IO-NI01-B-R3-CHIEF-ARCHITECT-RATIFIED-2026-10-14.md`, `HANDOFF-R3.md`, PR [#210](https://github.com/ZaurNavi/CaptivePortal/pull/210) — B/R3 design, benchmark evidence и closure.
4. Tech Lead independent WSL lab logs: PR #209 NI 1488 PASS, paired 256-record A OFF/ON; PR #210 R3 NI 1592 PASS и independent 3-fixture performance measurement.
5. Датированные read-only production observations при rollout A (21:18–21:21 AZST). Долговременной matched physical I/O серии **нет**.

**Подписант: TechLead23. Итог:** A сохранили как безопасное уменьшение SQL-work; B завершили как отрицательный эксперимент. Следующий шаг — не ещё один эвристический алгоритм, а измеренное понимание физического HDD bottleneck.
