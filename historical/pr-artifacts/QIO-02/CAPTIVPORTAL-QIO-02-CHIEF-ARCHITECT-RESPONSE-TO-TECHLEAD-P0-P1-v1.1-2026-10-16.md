# CAPTIVPORTAL — QIO-02
## Chief Architect → Tech Lead: P0 Review Disposition & P1/P2 Gate Clarification v1.1

**Дата:** 2026-10-16 (Asia/Baku)  
**Отправитель:** Chief Architect / Performance & Small-I/O  
**Адресат:** Tech Lead — Performance & Optimization  
**Ответ на:** `CAPTIVPORTAL-QIO-02-TECHLEAD-ARCHITECTURE-REVIEW-AND-P1-DIRECTIVE-2026-10-16(2).md`  
**Родительский нормативный контракт:** `CAPTIVPORTAL-QIO-02-SQLITE-SMALL-IO-ARCHITECTURE-ADMISSION-CONTRACT-v1-2026-10-16.md`  
**Суть:** официальное уточнение staging для N7 и владельца полной независимой технической приёмки. Не новый scope, не Coder TASK, не разрешение изменять production.

## 1. Архитектурная диспозиция

**DECISION: ACCEPT TECH LEAD REVIEW / P0 PASS WITH CLARIFICATION.**

Технический лидер верно принял семантические границы v1 и верно разделил доказательство *существующей стоимости операции* от доказательства *реального выигрыша после её изменения*. Смешивать эти два результата в один prerequisite до реализации невозможно. **N7 уточняется по фазам, а не отменяется.** Контракт v1 остаётся нормативным по N1–N6, модели authority/freshness, запретам и тестам C01–C18.

- **P0:** `SEMANTIC_ARCHITECTURE=PASS`, исходный контракт `ACCEPTED_WITH_MODIFY`.
- **P1:** read-only causal attribution и consumer graph — **OPEN / EVIDENCE_REQUIRED**.
- **P2:** отдельный Architect Lab admission — **HOLD** до P1 evidence.
- **Coder:** **HOLD** до P2 и узкого Tech Lead TASK.
- **Production:** **NO CHANGES**, включая SQLite config, код, запуск/остановку служб и DB maintenance.

## 2. N7 — нормативное уточнение фаз

| Фаза | Что необходимо доказать | Gate |
|---|---|---|
| **P1, ДО разрешения Lab** | **N7-pre:** наблюдаемая причинная стоимость конкретного candidate writer: достижимая `cycle → SQL transaction → COMMIT/fdatasync/WAL → guest block I/O → host QEMU → HDD`; корректная device/cgroup map; repeatable matched quiet baseline; наличие заметного *потенциально устранимого* вклада, отличимого от соседних сервисов; отсутствие обязательного consumer/freshness/replay обязательства. | Не доказано → `EVIDENCE_REQUIRED`, `H1 REJECT` или `ALTERNATE`, не Coder TASK. |
| **P2, Architect Lab admission** | Выполнены **N1–N6**, N7-pre; указан точный affected tuple, сериализация сравнения под существующим owner/lock/transaction boundary, negative paths, допустимые файлы, план rollback и falsification criteria. Разрешается **одна** scoped гипотеза **только в disposable Lab**. | Explicit written `P2 LAB GO` Chief Architect, затем narrow Coder TASK от Tech Lead. |
| **P3, ПОСЛЕ создания Lab-кандидата** | **N7-post:** измеренный net improvement **host physical** completed writes/sec и/или latency/await при matched baseline, без ухудшения auth/visits/freshness/source replay/error handling; все тесты и независимая приёмка PASS. Гипотеза должна быть опровержимой; уменьшение SQL/JSON/WAL отдельно не performance PASS. | Нет физического net improvement → `PERFORMANCE_HOLD/REJECT`, даже при semantic PASS. |
| **P4/P5, production** | Exact candidate tree, full gates, отдельные Owner merge/production GO, staged deployment, rollback, повторяемое post-deploy measurement. | Без Owner GO и эксплуатационной приёмки нет production допуска. |

**Фраза v1 «N1–N7 выполнены» относится к окончательному допуску no-op guard в эксплуатацию.** До Lab требуется N1–N6 и N7-pre, после реализации N7-post. Никакой Lab-результат не ретроактивно оправдывает недоказанную семантическую корректность.

**Важно:** на общей физической HDD под несколькими гостями строгую причинность не следует обещать исходя лишь из cgroup корреляции. Если живые bounded sample windows не могут изолировать per-operation physical contribution, Tech Lead вправе представить bounded causal inference и предложить безопасный disposable Lab replication; Architect оценивает ограничения отдельно. Нельзя ложно утверждать, будто production host-I/O по отдельной SQLite-транзакции измерен с точностью 1:1.

## 3. Ответ на H1 / Public Traffic и обязательный semantic gate

**Подтверждение источника:** current-source path `_process_source() → final observe_source() → BEGIN IMMEDIATE → UPSERT reader_state → COMMIT` на EOF и обновление `reader_state.updated_at` без WHERE changed являются **реальным кандидатом на исследование**. Это не доказательство ненужного writer или его стоимости для HDD.

**Неотменяемые условия:**

1. Сверить persisted tuple без исключений: `source_identity`, `source_path`, `source_offset`, `source_checkpoint`, `last_observed_size`, `retired_completed`, `missing_warning_emitted`, и семантику generation/rotation/truncate/missing/reappearance; отдельно разобраться с `updated_at`.
2. Показать consumer graph не только по Python-коду, но и по live adopted settings, public/Admin API, health/SLA, analytics, replay tooling, incident/audit и внешним DB/Grafana потребителям. Нельзя считать отсутствие прямой строки `reader_state.updated_at` в Python полным доказательством отсутствия потребителей.
3. Если `updated_at` является durable доказательством **успешного повторного scan** или управляет fresh/stale/readiness, **текущий H1=REJECT**, а не произвольный throttling. Новая модель freshness — отдельный Chief Architect admission request.
4. Проверить positive case **только** для действительно неизменного same-identity/generation EOF. Любой новый source fact, pending incomplete tail, append (в том числе `traffic_bytes=0`), changed checkpoint, inode change, rotation, truncation, missing/reappear, warning transition или retirement требует старой семантики durable progress.
5. При возможной гонке с другим writer — никакого TOCTOU «прочёл до транзакции, потом не записал». Conditional no-op должен быть атомарен в существующей owner/lock/transaction модели или по доказанному CAS. Добавленная проверка не должна съедать выигрыш чтением/блокировками.
6. `no row mutation` / `commit()` ≠ `fdatasync()` ≠ completed host physical writes. P1 должен измерить реальную стоимость и возможное write amplification. Если текущая операция фактически не вызывает дисковой записи в нужном окне, оптимизация H1 может быть бессмысленной.

**Предложение H1 в Lab допускается только с подтверждёнными (1)–(6).** Tech Lead может отвергнуть H1 и предложить `ALTERNATE` по физическому ranking; Architect не требует оптимизировать Public Traffic любой ценой.

## 4. Разграничение authority и derived (подтверждено без изменения)

| Домен | Обязательное durable поведение | Текущий допуск |
|---|---|---|
| **Visitor Registry** | `mark_successful_scan()` после каждого подтверждённого полного сканирования; freshness нельзя выводить из неизменного membership. Backfill/state/reader checkpoints остаются durable. | Не сокращать timestamp/COMMIT по v1. Если Registry лидер — отдельный `Q2-REGISTRY-FRESHNESS` с consumer SLA. |
| **Current State** | Каждый completed attempt/cycle — самостоятельное наблюдение, включая полный пустой, partial и failure. Cycle ID/time/scope/quality/rows связаны атомарно. | Не вырезать cycle rows. Допустимые derived-only проекции требуют отдельной атрибуции. |
| **Visit Lifecycle** | Auth, visit open/close, source identity/offset/checkpoint, pending retry/reconcile и idempotency сохраняются с прежней crash/replay границей. | Нулевое количество входных событий не даёт права пропустить progress. |
| **Public Traffic** | Per-event dedup/aggregate + checkpoint, reset, rotation, missing/reappear, source state и необходимые freshness proofs. | Только условный H1 в отношении no-change **финального** EOF observe при проверенных границах. |
| **Omada Observations** | Each running/success/partial/failure/abandoned cycle + scope/quality; отсутствие устройств доказано только полным успешным наблюдением. | Никакого пропуска immutable cycle фактов из-за неизменного payload. |

SQLite `synchronous`, `journal_mode`, WAL/checkpoint semantics, transaction durability, retention и independent authoritative commits **не ослаблять**. Не проводить heavy tracing, checkpoint, VACUUM, REINDEX или failure injection на production.

## 5. Владелец независимой проверки

Принимаю замечание организационного характера. Выражение исходного контракта **«independent Tech Lead review and QA» означает независимую от Coder техническую приёмку лично Tech Lead**. Отдельную роль Independent QA не создавать и не ставить формальным gate. Tech Lead выполняет полный source/diff/tree review, Windows/Linux regression, crash/replay/security, физические PERF matched Lab и Auth E2E. Coder выполняет **только focused tests** и evidence из narrow Lab TASK. Права на merge и production принадлежат Owner и требуют отдельных решений.

## 6. P1 deliverable и условия следующего решения

Tech Lead возвращает **`QIO-02 PER-DB PHYSICAL-WRITE & CONSUMER-SEMANTIC EVIDENCE`** с:

1. Сверкой runtime-loaded identity/Settings, точной картой DB → writer/cycle → transaction/commit, ownership/failure semantics для пяти доменов.
2. Перечнем real consumers и freshness obligations (`reader_state.updated_at` не смешивать с `traffic_daily.updated_at` и `visit_reader_state.updated_at`).
3. Не менее **трёх** comparable quiet окон по 10–15 минут (если производственная ситуация позволяет) и синхронными guest/host timestamps, device map, background I/O matrix, CPU/PSI, auth/source readiness, сопутствующим workload. Разрешены только bounded read-only измерения, без перезапусков/фиктивной нагрузки.
4. Ранжированием *подтверждённых* per-DB/operation кандидатов по likely **host physical contribution × safely eliminable fraction × risk/rollback cost**. Не подменять физическую причинность `syscr`, `sqlite steps` или количеством `COMMIT`.
5. Recommendation одним из значений: **`H1 PASS_TO_LAB`** (при снятых semantic blockers), **`H1 REJECT`** (с доказательством причины) или **`ALTERNATE`** (новый точечный candidate с исходной атрибуцией). 
6. Планом disposable Lab, matched A/B performance и correctness C01–C18, crash/kill/replay/late/rotated cases, rollback, STOP triggers. Если данных не хватает — честное `EVIDENCE_REQUIRED`.

**Cold-start read stalls** (`visits.sqlite3`, `current_state.sqlite3`) остаются отдельным `QIO-STARTUP-READ` track. **QIO-01D и PR #215 вне scope.**

## 7. Machine-readable disposition

```ini
TASK=QIO-02
CHIEF_ARCHITECT_REVIEW=ACCEPT_TECHLEAD_P0
ARCHITECTURE_CONTRACT=v1_PLUS_P0_P1_CLARIFICATION_v1.1
P0_SEMANTICS=PASS
N1_TO_N6=REQUIRED_BEFORE_SCOPED_LAB
N7_PRE=REQUIRED_FOR_LAB_ADMISSION
N7_POST=REQUIRED_FOR_PERFORMANCE_PASS_AND_PRODUCTION_ADMISSION
P1_CAUSAL_EVIDENCE=OPEN
H1_SOURCE_PATH=CONFIRMED_FOR_RESEARCH
H1_CONSUMER_GRAPH=INCOMPLETE
H1_HOST_PHYSICAL_COST=UNPROVEN
P2_LAB_ADMISSION=HOLD
CODER=HOLD
INDEPENDENT_FULL_TESTS_OWNER=TECH_LEAD
SEPARATE_INDEPENDENT_QA_ROLE=NONE
PRODUCTION_CHANGES=NO
OWNER_MERGE_GO=REQUIRED_SEPARATELY
OWNER_PRODUCTION_GO=REQUIRED_SEPARATELY
COLD_START_READ=SEPARATE_TRACK
QIO_01D=SEPARATE_TRACK
PR_215=UNTOUCHED
```

**Задание Tech Lead:** продолжить P1 по действующему read-only directive. Приступать к Coder TASK только после отдельного P2 архитектурного решения по одному Lab-эксперименту. Настоящее письмо не разрешает реализацию или изменение production.
