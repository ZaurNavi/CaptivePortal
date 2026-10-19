# CAPTIVPORTAL — QIO-02 / P1 R3
## Chief Architect → Tech Lead: Owner Laptop-Lab Direction & H1 Admission Clarifications v1.3

**Дата:** 2026-10-16 (Asia/Baku)  
**Тип:** нормативное архитектурное уточнение к QIO-02 v1 / P1 v1.1 / H1 v1.2; **не Coder TASK и не production GO**.  
**Основание:** `CAPTIVPORTAL-QIO-02-P1-R3-LIVE-READONLY-EVIDENCE-AND-LAB-PROPOSAL-2026-10-16(1).md` (Tech Lead R3).  
**Прямое решение Owner:** прекратить нагружать production дополнительным QIO-02 профилированием; продолжать исследование в изолированной лаборатории на ноутбуке.  
**Приоритет безопасности:** ни тестов на live DB, ни рестартов production, ни изменения SQLite PRAGMA, ни нагрузочного эксперимента на гипервизоре.

## 1. Executive decision

**DECISION = MODIFY / LAPTOP-LAB RESEARCH GO.**

1. **Production heavy profiling и требование трёх quiet production windows для перехода к лабораторной проверке QIO-02 приостанавливаются решением Owner.** Уже полученные read-only production сведения остаются историческим baseline, но новых исследований, создающих существенную нагрузку на рабочий HDD, не проводить. Никаких нагрузочных synthetic-run на 192.168.0.202/гипервизоре.
2. **P1-L0: разрешена подготовка и выполнение локального, полностью disposable исследования на ноутбуке** с неизменённым upstream кодом, фиктивными input-файлами и новой тестовой SQLite. Допускается пассивная инструментальная съёмка *лабораторных* SQL/COMMIT/WAL/fsync и физического I/O ноутбука. Не копировать живую production SQLite или сырой пользовательский source-журнал ради этого опыта.
3. **P2 implementation admission остаётся отдельным решением Chief Architect.** Owner разрешил перенести место работы, а не дал автоматическое разрешение менять код/сливать PR. До P2 Tech Lead может подготовить baseline, fixture и измерительный протокол без patch к production-коду. Coder HOLD.
4. **H1 сохраняется условно перспективной**, но физическая экономия на рабочем HDD *не доказана*. Отсутствие трёх production quiet windows не блокирует возможность последующего **отдельного P2 Lab GO** при достаточном независимом локальном causal evidence и закрытой consumer-семантике. Не объявлять N7-post PASS на основании SSD/ноутбука.

## 2. Ответы на три точных вопроса Tech Lead R3

### Q1. Уже завершённый архивный источник (`retired_completed=1 → 1`)

**ДА — в принципе H1 может охватывать *стабильно завершённый* архивный источник**, если одновременно: та же подтверждённая identity/generation; полный 7-полевой durable tuple не изменился; source на файловой системе не изменён и действительно достигнут тот же EOF; нет дополнительного authoritative/health/consumer обязательства; окончательное решение принято атомарно в существующей writer serialization границе.

**НЕТ — переходы `0 → 1` и `1 → 0` не входят в no-op**: это обязательные durable state transitions. Новая source identity, ротация, disappearance/reappearance, truncate/rewrite, изменившийся checkpoint, appended event даже с traffic=0/duplicate, incomplete tail, missing-warning и любая иная смена tuple продолжают проходить обычный durable путь. Ранее встречавшееся в v1.2 выражение «source retirement excluded» относится к **переходу**, а не к повторному проверочному EOF при уже сохранённом `retired_completed=1`.

### Q2. Как ограниченно закрыть риск внешних consumers `reader_state.updated_at`

Бесконечного математического доказательства отсутствия любого внешнего читателя не требуем. Нужно **bounded operational attestation**, а не молчаливое предположение:

- Tech Lead фиксирует текущую карту first-party consumers (reader/repository/API/Admin, cron/systemd/scripts, Grafana/Loki/Alloy, diagnostics/forensics, external SQL reads) и точную *область*, которую смог проверить; timestamp **не** подменять с `traffic_daily.updated_at`, `visit_reader_state.updated_at` или Registry freshness.
- Owner и, при наличии отдельного ответственного, SysAdmin/Observability owner подтверждают **в письменном handoff**: не существует известного обязательного monitoring/freshness/forensic/SLA consumer, для которого каждое обновление именно `public_traffic.sqlite3:reader_state.updated_at` является authoritative/required; либо перечисляют существующие зависимости.
- Неясные/недоступные внешние потребители перечисляются как *residual risk*; Owner отдельно и осознанно принимает ограниченный риск **только при отсутствии известных обязательных зависимостей**. Для уже обнаруженного required consumer — H1 REJECT_CURRENT_DESIGN, не игнорировать и не подменять обещанную свежесть.
- Такое bounded attestation достаточно **для допуска локального P2-эксперимента**, но ещё не для production GO. Перед deployment Tech Lead повторно сверяет потребителей и принимает отдельный compatibility/rollback gate; запрещено представлять `updated_at` как «последнее полное успешное сканирование».

**На данный момент R3 consumer graph ещё неполон: H1_CONSUMER=HOLD_FOR_IMPLEMENTATION.** Для P1-L0 baseline на ноутбуке этот HOLD препятствием не является.

### Q3. Может ли Lab заменить три quiet production windows как N7-pre?

**ДА, для узкого допуска к последующему disposable P2 experiment: локальная воспроизводимая причинная демонстрация принимается как N7-pre *feasibility*; production attribution можно оставить OPEN** по явному решению Owner не нагружать его дополнительно.

Но уровни доказательств не смешивать:

- **L0 без изменения production-кода:** показать в лаборатории на точной ревизии, что пять неизменных retired-source final-EOF действительно вызывают дополнительные SQL UPDATE/COMMIT и какие WAL bytes, sync/lock/wall-time возникают. Воспроизвести отсутствие эффекта при активном источнике с новыми событиями и при partial/error. Записать Linux/Windows платформы, SQLite версии, параметры, host disk и режим хранения.
- **L1 после отдельного P2 GO и Coder TASK:** matched A/B неизменённого baseline и точной узкой variant на одинаковой лабораторной машине/накопителе, с повторными циклами в сбалансированном порядке, cold/warm и burst/idle. Считать реальное уменьшение completed writes/fsync/WAL/checkpoint, latency и ошибки — там, где платформа позволяет это наблюдать.
- **Различие носителей:** SSD-ноутбук доказывает локальный causal effect, но не экстраполирует `write await`, HDD busy и общую экономию `/dev/sda`. Если доступен ненагруженный лабораторный вращающийся HDD, выполнять дополнительный A/B на нём. Если нет — честно указать `LAB_HDD_FIDELITY=LIMITED`, не пытаться создавать нагрузку на production вместо него.
- **N7-post для deployment:** лабораторный воспроизводимый выигрыш + correctness обязателен; production outcome на физическом HDD остаётся `NOT_YET_VERIFIED`. После отдельно одобренного внедрения допускаются только заранее согласованные bounded monitoring/сопоставимые пассивные окна; ни одного заявления «production IOPS снижены», пока это реально не измерено. Если итоговая экономия не доказана — не объявлять performance PASS.

## 3. Архитектурные границы гипотезы H1

**Единственная рассматриваемая запись:** final `PublicTrafficReader._process_source()` → `repository.observe_source()` на *подтверждённом* complete EOF при действительно **неизменном** состоянии. Не менять `advance_source()`, `process_offline_event()`, `reset_*`, missing/return transitions, initial backfill, count resets, aggregates или visit/current-state/registry/observations.

**Сравниваемый effective durable tuple**: `source_identity`, `source_path`, `source_offset`, `source_checkpoint` (полный digest), `last_observed_size`, `retired_completed`, `missing_warning_emitted`; также проверить source-device/inode/generation и логические условия footer/EOF. Единственная потенциально допускаемая разница с legacy — operational `reader_state.updated_at` при *реальном* unchanged no-op и при закрытом consumer contract.

**TOCTOU запрет:** early read `scan() → get_reader_states()` не может быть единственным основанием пропуска. Проверка current stored row и решение об UPDATE должны выполняться в существующей SQLite write-serialization/atomic conditional boundary; stale client snapshot не является authority. SQLite lock не удерживает файловую систему источника от append/rotation — сохранять inode/fstat/checkpoint guards и корректность следующего scan. При неизвестности/гонке выполнять legacy durable path, а не optimistic skip.

**Никакой изменения durability:** не менять `synchronous`, `journal_mode`, WAL checkpoint, fsync, transaction boundaries authoritative effects, не делать VACUUM/REINDEX/PRAGMA mutation на production; не добавлять cron/webhook/SQLite heartbeat для имитации прежнего `updated_at`.

## 4. План лаборатории на ноутбуке: исполняется Tech Lead, не Coder

**P1-L0 разрешено сейчас (изолированная инфраструктура):**

1. Зафиксировать точный выбранный исходный git HEAD+tree. R3 имел `main@191beda1f23f8f466d2431f42e57571815d85778`, production отставал `e2cbd96916d8a81f07f0d79a1a745f593ccb5114`; PR #215 остается вне scope. При следующем запуске заново проверить HEAD и выбрать reproducible base; не смешивать правки других TASK.
2. Создать только новые disposable тестовые SQLite и синтетические `omada_webhook_normalized.log`, `.1`–`.5`; каждая identity и checkpoint должны генерироваться из fixture, без копирования персональных логов production.
3. До/после каждого fixture-run собирать records/offset/checkpoint, `updated_at`, SQL transaction count, WAL size/writes, fsync/lock wait, SQLite replay и local physical-device writes/await/busy при измеримости. Контроль за собственным laptop background I/O; никто не заявляет прямого соответствия VM guest/host HDD.
4. Сделать контрольные случаи: **A** — повторный неизменный EOF пяти retired; **B** — active source с append; **C** — retired transition; **D** — partial line; **E** — same size + changed checkpoint; **F** — rotation/reappearance; **G** — crash/replay. В P1-L0 используется исходный код без оптимизации; цель — базовая воспроизводимость и стоимость.
5. Сформировать отчёт `QIO-02 P1-L0 LAPTOP CAUSAL BASELINE & P2 LAB ADMISSION REQUEST` с характеристиками диска, числами и ограничениями. Никаких загрузок на production, массовых SSH команд или долгих remote probes.

**P2/L1 — отдельный future gate:** Tech Lead возвращает (a) L0 baseline; (b) consumer attestation/risk owner; (c) конкретный узкий алгоритм сравнения под writer lock; (d) ожидаемую измеримую величину выигрыша, доступный тип HDD/SSD, mandatory fail cases; (e) exact file allowlist/rollback. Chief Architect выдаёт новый `P2 LAB GO / HOLD / REJECT`. Затем Tech Lead готовит Coder TASK; Coder делает focused tests; Tech Lead независимо проводит full Linux/Windows, crash/replay/security/PERF. Никакого смешивания этих обязанностей.

## 5. Stop conditions и интерпретация результата

**Остановить H1 до code:** доказанный обязательный consumer `reader_state.updated_at`; невозможность сделать atomic guard; неоднозначная owner/generation/replay семантика; воспроизводимый data loss в лабораторном протоколе; отсутствие обоснованного causal cost даже на локальной disposable DB. При этих условиях вернуть `H1=REJECT/ALTERNATE` и выбрать иной writer из QIO-02.

**Не считать успехом:** снижение `updated_at` меняющихся строк как единственную метрику; ускорение CPU без physical evidence; снижение journald QIO-01D; пересчитанные guest `io.stat` как host /dev/sda; позитивные тесты без negative crash/replay; performance под SSD как доказательство эффекта на production HDD.

**Операционное преимущество:** перенос исследования на ноутбук снимает дополнительный риск для HDD, который в R3 достигал `~92.53% busy`, `103.30 host writes/s` и `~85.49 ms/write await`. Причина этой нагрузки общесистемная и не доказана за H1.

## 6. Machine-readable disposition

```ini
TASK=QIO-02
DOCUMENT=CHIEF_ARCHITECT_P1_R3_LAPTOP_LAB_DISPOSITION_V1_3
OWNER_DIRECTION=STOP_ADDITIONAL_PRODUCTION_QIO02_PROFILING
P1_L0_DISPOSABLE_LAPTOP_BASELINE=GO
P1_L0_PRODUCTION_FILES_OR_DATABASES=DO_NOT_COPY
H1_STABLE_RETIRED_SAME_TUPLE=CONDITIONALLY_ELIGIBLE
H1_RETIREMENT_TRANSITION=MANDATORY_DURABLE
H1_UPDATED_AT_CLASSIFICATION=OPERATIONAL_NOT_FULL_SCAN_PROOF
H1_CONSUMER_ATTESTATION=REQUIRED_FOR_P2_IMPLEMENTATION
H1_CONSUMER_GRAPH=INCOMPLETE
H1_TOCTOU_GUARD=MANDATORY
N7_PRE_LAB_FEASIBILITY=ACCEPTABLE_FOR_FUTURE_P2_REVIEW
N7_POST_PRODUCTION_PHYSICAL_EFFECT=UNPROVEN
P2_VARIANT_IMPLEMENTATION=HOLD_PENDING_L0_AND_CONSUMER_ATTESTATION
CODER=HOLD
PR_MERGE=NO
PRODUCTION_CHANGES=NO
OWNER_PRODUCTION_GO=NO
QIO_01D=SEPARATE_TRACK
PR_215=UNTOUCHED
COLD_START_READ=SEPARATE_TRACK
```

**Следующий ответственный:** Tech Lead готовит P1-L0 disposable laptop measurements и bounded external consumer attestation. После их получения Chief Architect принимает отдельное решение по P2. До этого production не трогать.
