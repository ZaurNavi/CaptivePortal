# CAPTIVPORTAL — QIO-EVIDENCE-IDLE-02
## P2-LAB-00 — HOT/ARCHIVE TRUST-BOUNDARY PROOF
### TECH LEAD → CODER / RESEARCH-ONLY TASK v1.0

**Дата:** 2026-10-17 (Asia/Baku)  
**Автор:** Performance & Optimization Tech Lead  
**Основание:** `CAPTIVPORTAL-QIO-EVIDENCE-IDLE-01-CHIEF-ARCHITECT-N08-N11-HOT-ARCHIVE-DECISION-v1.3-2026-10-17` (сохраняет нормативность E1–E4 предыдущих контрактов там, где не заменена v1.3).  
**ID:** `QIO-EVIDENCE-IDLE-02-P2-LAB-00-HOT-ARCHIVE-TRUST-PROOF`  
**Решение TL:** **CODER GO — только research/design/proof на disposable fixtures и в отдельном worktree.**  
**Ограничения:** `RUNTIME_IMPLEMENTATION=HOLD`, `FAST_READY=HOLD`, `PROD=NO`, `COMMIT/PUSH/PR/MERGE/DEPLOY=NO`.

## 0. Архитектурный вердикт и рамки

1. `P2-LAB-01` закрыт как **research PASS / replacement NEGATIVE**. Прямой дешёвой эквивалентной замены монолитной проверки нет. Его research-patch не является базой этой задачи и **не переносится** в новый candidate.
2. `N08/N11` — подтверждённый **P1 integrity-specification gap** на специально повреждённых disposable fixtures, **не** доказанный инцидент на 3.8-GB LAB DB. Legacy T1 гарантирует выполнение конкретных старых проверок, **не** исключает произвольную порчу UNIQUE/index-table.
3. Исторический L0 `PRAGMA quick_check` **PASS**: 2026-10-17 16:52:36+04:00, `3352.86 s`, полный результат `['ok']`, process `read_bytes=3,961,155,584` bytes. Evidence sequence scan отдельно `148.402 s`. Это *не* измерение end-to-end production startup и *не* физический HDD cost одной VM в изоляции.
4. Выбранная архитектура для исследования: **единственный bounded HOT writer**, новая запись Evidence/Source Health с durable ACK только после атомарного commit; **запечатанные immutable ARCHIVE generations** с сильным **T3 at seal** (`full integrity_check + domain guards`). У HOT собственный полный startup trust gate, а у истории независимое состояние trust.
5. Эта задача доказывает/опровергает концепцию на малых файловых SQLite-базах. Это **не** разрешение менять readiness, code composition, HTTP, systemd, схемы реального сервиса, оригинальную БД или production. **Нельзя выдавать успешный fixture за готовый crash-safe runtime cutover.** Любой недоказанный gap → `UNKNOWN/HOLD`.

### 0.1 Frozen source / admission

| Поле | Нормативное значение |
|---|---|
| Repository | `ZaurNavi/CaptivePortal` |
| **BASE commit** | `810484e69baa371c4696c3b46654199631538fc4` |
| **BASE tree** | `6816e73148c91c1e2e778613067a41d8c973c03d` |
| `app/device_fingerprint/repository.py` blob | `12710de576c3f4d887740f73354d51b1096f0a5c` |
| `app/device_fingerprint/schema.py` blob | `a99ed87aa674f064edd50eea51ab408becd48e7d` |
| `app/device_fingerprint/read_service.py` blob | `ea361e12bbbc416d5a70a6bcc98cc0b0ef620c85` |
| `app/device_fingerprint/storage_v2.py` blob | `2cf5b0d33dabea8f5b31b6e59f93229466092ca0` |
| `app/device_fingerprint/service.py` blob | `cc038e5509b86b0c3d0d59b74ca6c63518a615fd` |
| `app/device_fingerprint/cli.py` blob | `e7789e1d50cd5cebfb47cb927eb0d510ec895811` |

Все значения SHA выше сверены Tech Lead с pinned GitHub blob; BASE tree ранее независимо подтверждён на LAB Git object store. Перед работой **Coder заново подтверждает** commit, tree, source blob IDs и чистый новый worktree. Нельзя использовать GitHub `main`, живой checkout `/opt/CaptivePortal`, отдельный прежний незафиксированный P2-LAB-01 candidate или состояние `captiv-prod` вместо указанной базы. При расхождении — **STOP**.

Рабочий каталог: **отдельный worktree от BASE**, расположенный вне путей запущенных приложений и вне старого P2-LAB-01 worktree. Исходный index/HEAD/service не меняется. Любая сборка candidate tree — через **специально созданный временный `GIT_INDEX_FILE`**, с точным списком новых файлов; не индексировать чужой мусор. Запрещены commit/push/PR.

### 0.2 Хосты и файловые границы

- Тестовый контекст: **только старый LAB** `192.168.0.202`, QEMU `Ubunt`, host `omv-hp:/dev/sda` — и локальные disposable фикстуры Coder на Linux/Windows. Рабочая 3.8-GB Evidence DB `/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3` **не меняется** и не получает synthetic corruption, WAL mutation, checkpoint, migration, copy-overwrite или тестовый ingest.
- Новый действующий `captiv-prod`, Network Metadata, NI-02A, QIO-05, Omada/Visit/Settings/другие БД — **абсолютно OUT OF SCOPE**.
- **Owner уже разрешил** Tech Lead read-only/full-scan/физические HDD измерения LAB на старой VM (отдельно от Coder). Это **не** разрешение Coder запускать тяжёлые SQL/backup оригинальной DB, трогать hypervisor, сервисы или проводить performance interference без адресного направления TL. Coder использует ограниченные disposable fixtures; предоставление host physical evidence — обязанность Tech Lead, отдельным этапом.

## 1. Цель исследования / falsifiable hypothesis

**Гипотеза:** можно сохранить единственный durable global ingest sequence, семантику producer ACK/idempotency и изоляцию читателей, если новые записи направляются в маленькую HOT DB, а старое поколение архивируется через T3-verified sealed snapshot и однозначный, crash-recoverable cutover — без необходимости перечитывать полный архив при каждом HOT startup.

**Что опровергает гипотезу:** acknowledged event теряется; повторный ACK на конфликтующие immutable payloads; sequence reuse/cross-family collision; два writer authority; archive недоступен, но duplicate принят как новый; невалидный архив опубликован; manifest и данные расходятся после crash/restore; pinned reader получает неполную выборку под видом пустой; late `observed_at`/retention/source-health нарушают старую семантику; тесты требуют недоказанных гарантий SQLite `ATTACH` или изменяемого manifest/hash.

**Результат** — техническое evidence и явно описанные open gaps. Допустимые итоговые вердикты: `PROTOTYPE_CONSISTENT_ON_TESTED_FIXTURES`, `REJECTED`, `UNKNOWN`. Статусы `TRUST_EQUIVALENT_PROVEN`, `OPERATIONAL_FAST_READY`, `RUNTIME_READY` в этой задаче **недоступны**.

## 2. Точный текущий source/consumer baseline, обязательный для design

В pinned tree:

| Anchor | Действующая семантика, требующая сохранения |
|---|---|
| `repository.py:66–120, 297–321` | `initialize()` проверяет исходный single DB; полный `PRAGMA quick_check`, exact schema, storage state, два per-family sequence guards и cross-family collision guard — до публикации connection |
| `repository.py:157–168` | `database_generation_id` и `max_committed_ingest_sequence` берутся из **одного snapshot** |
| `repository.py:169–243` | Evidence и Source Health используют общий `last_ingest_sequence`; `BEGIN IMMEDIATE` → проверка producer idempotency и immutable conflict → INSERT+watermark → один COMMIT, затем результат `BatchResult` |
| `repository.py:245–280` | Retention по `observed_at`; Source Health имеет дополнительный margin; chunked transaction cleanup; gaps в sequence допустимы |
| `repository.py:283–290` | Текущие WAL/`synchronous`/autocheckpoint — **не менять**. Реальную power-loss durability ACK надо доказать отдельно, а не выводить из одного `COMMIT` |
| `repository.py:402–452` | Writer lock и POSIX/Windows различия; в концепции один owner/fenced writer |
| `read_service.py:18–176` | `DeviceFingerprintSnapshotReadSession`, pinned `(generation, watermark)`, фильтр `ingest_sequence<=watermark`, evidence+Source Health pages с `(observed_at,id)` cursor |
| `read_service.py:177–259` | Стандартные list/latest query paths, time-window/retention validation, Source Health freshness |
| `storage_v2.py:143–187,281–283` | Существующий restore/recovery и `integrity_check` — исследовать семантику, **не заимствовать как готовый hot/archive cutover** |
| `service.py:60–136,188–224,278–302` | Validation, acknowledgments, readiness/writer gate, storage error/health, periodic retention |
| `cli.py:65–109` | Сначала lock и initialize, затем registry/start maintenance/mark_ready и HTTP; новый LAB proof не меняет ни одну из этих стадий |
| `schema.py` | Точные v2 tables, CHECK/UNIQUE/indexes/limits для обеих family и storage singleton |

**Deliverable:** в `CONTRACT.md` сделать **полный source-to-consumer graph**, найти прямых и косвенных читателей/писателей/health/UI API (и file:line anchors) во всём pinned tree. В таблице перечислить для каждого: вызов, authoritative vs derived, ожидаемые fields/errors, текущую single-DB assumption, риск multi-generation, требуемую совместимость; если consumer проверить нельзя — `UNVERIFIED`, не угадывать. Эти anchors выше — **минимум, не полный graph**.

## 3. Modification allowlist / denylist

**Разрешено создать ровно эти НОВЫЕ пути в отдельном research worktree:**

1. `research/qio_evidence_idle_02/__init__.py` (опциональный пустой marker, не импортируемый runtime).
2. `research/qio_evidence_idle_02/hot_archive_trust_proof.py` — маленький research-only executable/library для disposable SQLite; прямого подключения к реальному DB path/API не допускается.
3. `research/qio_evidence_idle_02/CONTRACT.md` — verified consumer graph, proposed state machine, durable authority, rollback forward/recovery, open technical decisions и trust model.
4. `research/qio_evidence_idle_02/README.md` — воспроизводимая процедура, платформы, ограничение размеров fixtures, наблюдения и негативные outcomes.
5. `tests/device_fingerprint/test_qio_evidence_hot_archive_research.py` — focused deterministic Linux/Windows fixtures.

**Всё остальное — denylist**, в том числе: любые существующие файлы, `app/**`, `tests/**` кроме одного нового файла, текущие `research/qio_evidence_idle_01/**`, schema/migrations/requirements/pyproject/config/env/systemd/run.py, логи/сертификаты/секреты сервиса, настоящие SQLite DB/WAL/SHM, изменение работающего checkout. Запрещены hidden env bypass, delayed integrity auditing для той же mutable DB, HTTP readiness, и публикация исходников.

Вне репозитория разрешены только disposable DB и проверочные отчёты/JUnit/log/patch/identity inventory в выделенном workspace; никакого доступа к `captiv-prod`. Если proof потребует иной tracked path или production-facing refactor — **STOP + адресная просьба TL/Architect**, не расширять allowlist самим.

## 4. Исследовательские work packages

### WP-A — точная декларативная модель доверия

Создать `CONTRACT.md` с минимальным machine-checkable словарём:

- Состояния cutover `PREPARE`, `VERIFY`, `CREATE_HOT`, `ACTIVATE`, `RECOVER`; дополнительно `OLD_ACTIVE`, `NEW_ACTIVE`, `HOLD/NOT_READY` при необходимости, **без** ложного транзита из неизвестного в READY.
- Для каждого состояния: writer fence token/epoch (его хранение/срок действия и невозможность stale writer), authoritative file/path + single writer, allowed operations, durable records, guard predicates, expected recovery after crash, whether producer ACK and readers permitted, transition proofs.
- Для истории: `HISTORY_UNVERIFIED`, `HISTORY_TRUSTED_AT_SEAL`, `HISTORY_QUARANTINED`; validity зависит от T3 audit **финального образа**, manifest/attestation binding и непрерывной immutability. Metadata/hash в том же writable каталоге — только диагностический indicator, **не** независимый trust anchor. External writer/rollback без защищённого anchor ⇒ `UNKNOWN/HOLD`.
- Для HOT: полный startup integrity/sequence validation **по HOT**, writer fencing, disjoint committed seq bounds и archive availability requirements до любого ACK; не объявлять доверенной старую историю только из-за HOT readiness.
- `T3`: **полный** `PRAGMA integrity_check` (`[('ok',)]`) на архивном поколении **плюс** exact schema/state/CHECK/type/range, UNIQUE/index-table coverage, global sequence collision, cutoff/max committed, producer idempotency invariant, Source Health. Не выдавать `quick_check` за T3.
- **Authority/persistence**: выбрать исследовательский publication anchor (например отдельный durable state record + immutable generation links, защищённый в тесте), указать предпосылки fsync файлов/каталогов/rename на Linux, Windows differences, rollback старой версии, anti-rollback counter. Если принципиальное звено невозможно доказать в standalone Python/SQLite fixture — **оставить explicit architecture gap**, а не fake PASS.
- **Не** использовать `ATTACH` WAL как основание аварийно-атомарного multi-DB COMMIT. Один `COMMIT` в HOT защищает INSERT+watermark, но не автоматически защищает publication manifest + archive + HOT.

### WP-B — двухпоколенный disposable reference proof

В отдельном временном root (не `/opt/CaptivePortal`, не общий repo) создать **две искусственные SQLite DB** v2-compatible / явно описанный research schema delta: old→sealed archive + fresh bounded HOT. Строить обе исходно из small fixture, не копировать оригинал. Исследование НЕ обязано воспроизводить весь production runtime; оно **обязано** не притворяться, что собственный schema delta прошёл production acceptance.

Проверить:

1. **Single writer** с контролируемым fence/epoch и явной защитой от stale writer даже после restart; если гарантия зависит от внешнего полномочия — описать и протестировать отрицательный сценарий.
2. **Global monotonically allocated sequence** для двух event family: exclusive/disjoint sealed vs HOT ranges; никакой reuse после restore/rollback, включая удалённые по retention строки. Overflow, allocator rollback, gap допустимость.
3. **Producer duplicate and immutable conflict** между HOT и всеми ещё-retained архивами. Сравнение exact payload fields, не просто event ID; повтор той же записи = `duplicate_noop` с сохранением установленной семантики ответа без нового INSERT/sequence, другой immutable payload = conflict, а недоступный индекс истории = `UNAVAILABLE/HOLD`.
4. **Atomic acknowledgment**: никаких successful producer ACK до успешного durable insert и watermark в **одной HOT SQLite transaction**; поведение после `COMMIT` vs реальная power-loss гарантия помечать отдельно. Не делать ACK из RAM/write-behind.
5. **Cross-generation reads**: доказать сортировку и пагинацию по `(observed_at,evidence_id)` / `(observed_at,source_health_id)` с global watermark snapshot, корректный `next_cursor`, latest Source Health и значения **unknown/unavailable** при недоверенной/недоступной истории. Late `observed_at` может попасть в старый временной диапазон, оставаясь в HOT с новым sequence.
6. **Retention:** контрактная текущая политика 30 дней Evidence и отдельный Source Health margin; при этом фактический параметр `evidence_retention_days` и функция cutoff в pinned коде конфигурируемы. Сверить policy/config semantics; не захардкодить неразрешённый срок. Удаление либо целого завершённого segment после expiry, либо через формально описанный reseal; нельзя продлевать хранение или удалять непроверенные записи по удобству.
7. **Archive backup/seal:** fencing старого writer, SQLite Backup API / документированный consistent snapshot, T3 на финальных bytes, hash+metadata+attestation после проверки, old generation *read-only*; дважды открыть/restart+replay synthetic cutover.
8. **Snapshot pinning:** reader открыл view до rollover; writer опубликовал новое поколение; reader либо продолжает прежний pinned row universe, либо получает typed unavailable, но никогда silent partial/empty. Старые generations не удалять, пока есть допустимые pinned readers.

### WP-C — обязательные adversarial / crash tests

Тесты должны иметь **стабильные уникальные имена** (в отчётах `H01`…`H28`), проверять *статус, неизменность committed content/allocator, typed errors и отсутствие ACK/READY*; при необходимости один ID параметризован на семейство Evidence/Source Health. Комбинировать допустимо, но ни один кейс нельзя пометить PASS, если он только упомянут в README.

| ID | Условие | Обязательная проверка |
|---|---|---|
| H01 | Clean empty HOT + sealed archive | Корректный trust-state, reader view и отсутствие false READY до gates |
| H02 | Evidence + Source Health по двум generations | Один global total order / disjoint sequence, no gaps assumption |
| H03 | Same producer-event replay across generations | duplicate noop с существующей семантикой ответа, без нового INSERT/нового sequence |
| H04 | Same key, different immutable payload | immutable conflict, atomic rollback |
| H05 | Archive offline/unverified/quarantined | dedup невозможен ⇒ no new-event ACK; historical read `UNAVAILABLE`, не пустая история |
| H06 | Cross-family seq collision / overlapping ranges | reject/HOLD до READY |
| H07 | Sequencer overflow / deleted seq / rolled-back HOT | no reuse, no artificial reset to `MAX(retained)` |
| H08 | Two attempted writers / stale fencing epoch | exactly one authority, second writer fails closed |
| H09 | Crash before INSERT | no ACK and no partial record |
| H10 | Crash after INSERT but before COMMIT | no ACK; replay safe, rollback uncommitted |
| H11 | Crash after COMMIT before ACK | committed record discovered, idempotent retry noop, no duplicate allocation |
| H12 | Crash after ACK boundary | no previously acknowledged event lost under **declared** fault model |
| H13 | Crash before/during/after WAL commit | atomic event+watermark for each testable step; label simulated vs actual |
| H14 | Crash before/during/after checkpoint | durable recovery, no duplicate/missing/reused sequence |
| H15 | Crash while backup underway | no published partial archive; old owner fenced |
| H16 | N08 artificial broken UNIQUE index in would-be archive | `integrity_check`/T3 refuses seal, no false trust |
| H17 | N11 index/table mismatch | T3 refuses seal; record SQLite versions + differing `quick_check` behavior |
| H18 | Crash after VERIFY before seal/publication | no false published archive, idempotent restart |
| H19 | Crash after CREATE_HOT before ACTIVATE | not dual-writer; forward/rollback deterministic |
| H20 | Crash before/after publication state, incl rename/fsync windows | no orphaned ACK, uncertain state yields HOLD |
| H21 | Missing/altered/corrupt manifest | quarantine / HOLD, not history clean |
| H22 | External writer / replaced inode / mutated archive post-seal | refuse false trust or explicitly UNSOLVED without external anchor |
| H23 | Restored stale manifest + HOT generation / anti-rollback | detect / HOLD; no silent sequence reallocation |
| H24 | Late `observed_at` + equal-timestamp cross-gen pagination | deterministic `(observed_at,id)` order and pinned completeness |
| H25 | Retention boundary plus Source Health margin, expiry | no over-retention/early deletion, known vs unknown semantics |
| H26 | Empty vs stale/missing Source Health | correct result/health freshness, no false healthy or false no-data |
| H27 | Reader pinned before cutover, rollover concurrent | stable read view or typed unavailable; never partial as complete |
| H28 | Busy/IOERR/CORRUPT/FULL/unsupported SQLite error during T3/hot gate | typed HOLD/REJECT, no readiness, no hidden repair |

For H13–H15/H20: process-kill and SQLite fault-injection on disposable fixtures are useful evidence but **not** physical power-loss proof. Explicitly report untested filesystem durability and versions. For N08/N11, use only controlled **disposable** index/schema corruption and keep raw query outputs plus SQLite version; no production DB manipulation. For unsupported/fail-to-inject case ⇒ `UNKNOWN/NOT_TESTED`, not PASS or hidden SKIP. Tests do not weaken existing assertions.

### WP-D — integrity and proof accounting

- `T3` must audit final immutable DB **before** seal announcement and accept only full `[('ok',)]` for `PRAGMA integrity_check`, plus independently evaluated exact domain guards. Keep full error tuples and SQLite diagnostics; distinguish corruption from lock/IO and malformed schema, include WAL identity.
- Manifest records at least generation UUID, source/target schema signature and SQLite runtime version, origin DB path (synthetic), content SHA256, source snapshot/cutover watermark, min/max seq bounds for both family (with legitimate retention gaps), max committed allocator, retention policy, source-health status, completed audit result/time/identity, previous generation link, publication epoch, protection/authority assumption. **Do not record or display secrets**.
- Reopen verified archive read-only; reject changed hash, inode replacement, broken trust binding or bad SQLite read. A single hash in co-mutated manifest cannot authorize `HISTORY_TRUSTED_AT_SEAL` against arbitrary privileged attacker; simulated protected anchor allowed only with explicit lab assumption.
- `integrity_check=ok` alone does not prove payload-level idempotency or source provenance; schema+domain assertions retain separate evidence. Missing producer identity records / checker impossible ⇒ no PASS.
- Differentiate database structural checks vs Source Health freshness/business meaning vs trust on reader/snapshot.

### WP-E — focused gates, delivery, and performance boundary

**Coder выполняет только** focused Linux + native Windows тесты этого одного нового модуля, compileall исследовательского пакета/теста, static AST/diff checks и handoff. Для разных OS записывать Python+SQLite version/build flags, hash source files, test inventory, test outcome (pass/fail/error/skip) с JUnit XML, логи, raw machine state ledger, representative query plans/observations, repro commands. Никаких full-project suites от Coder.

Сравнение performance внутри этого LAB-00 может использовать *только* disposable HOT fixture, с явным `SMALL_FIXTURE_NON_CAUSAL` label, wall/VDBE/process counters. **Запрещено** выдавать эти числа за host HDD экономию. Полный matched A/B/A на LAB `omv-hp:/dev/sda` (host /dev/sda + QEMU cgroup + guest /dev/vda), warm/cold/hot startup latency, API/health P95+error rate, одноразовый T3 seal cost и end-to-end startup — **Tech Lead** только после отдельного измерительного плана и разрешённого окна; исходный full L0 является историческим baseline, не matched control experiment.

**Coder handoff обязателен:**

- `BASE_HEAD/BASE_TREE`, candidate tree (`git write-tree` через isolated index), точный 5-file allowlist и path/status diff; **real operational index unchanged**.
- Полный replacement patch и `PATCH_SHA256/PATCH_BYTES`, sha256 новых файлов, `git diff --check` именно *для staged new-file diff*, `compileall` pass, commands/exits.
- `CONTRACT.md` с source/consumer graph и state/authority matrix; точный псевдопротокол + полный crash-point table и явно **недоказанные** предпосылки безопасности.
- H01–H28 fixture ledger с expected/observed, Linux/Windows environments, N08/N11 version comparison, raw logs, JUnit unique IDs и запрет необоснованных PASS/SKIP.
- Отдельная секция `UNPROVEN/FOLLOW_UP` для power loss/fsync/OS differences/immutable archive/rollback anchor, RPO/RTO и реальных hot-size thresholds.
- Machine-readable disposition: `research_only`, `hot_archive_safety_proven`, `runtime_gate`, `physical_hdd_savings`, `publish`, `prod`. Если equivalence невозможно подтвердить, указать `UNKNOWN/REJECTED`, не менять требования.
- Все внешние артефакты в отдельном подкаталоге handoffs; ни одна база/секрет/лог оригинальной LAB DB не включаются в ZIP.

## 5. Tech Lead independent acceptance gates — ПОСЛЕ handoff

1. Проверить byte-for-byte patch/hash, exact tree и все изменённые paths против allowlist, сравнить с pinned source hashes; **никакой existing runtime/test mutation**.
2. Самостоятельно в собственном worktree воспроизвести H01–H28 и fault/adversarial fixtures, проверить raw SQLite N08/N11 и SQLite-version behavior, запустить focused gates на Linux+Windows; inspect mismatch and gaps.
3. Потребовать от Coder точный source/consumer graph, durable state transitions, idempotency/global allocator proof и явные неустранимые trust gaps; ни один отчёт Coder не замещает TL review.
4. Полные Windows/Linux, root/POSIX/security/WAL/recovery regressions — **только** после следующего адресного Architect runtime-facing admission на точном candidate tree и необходимом scope. Этот RESEARCH-only artifact их не требует и не создаёт production implementation GO.
5. Реальный performance plan и host HDD matched A/B/A — отдельная обязанность TL, не автоматически запускается в этой фазе. Это не оценка по process bytes из крошечных fixtures.
6. Если distributed commit/attestation/crash safety не доказаны, **не** переводить новый design в runtime GO. Передать архитектору `Architecture Decision Request` с графом, точной моделью доверия, результатами fixtures и открытыми вопросами.

## 6. Немедленные STOP / запреты

**STOP и сообщить Tech Lead:** неверный base SHA/tree, любой чужой file modification, второй writer способен ACK; ACK before durable COMMIT; split event/watermark; reused/colliding sequence; потеря Source Health; dedup fail-open при недоступной истории; false empty from historical query; N08/N11 archive seal passes despite invalid T3; mutable co-located manifest объявлен достаточной аттестацией; use of unapproved SQLite version; `ATTACH` WAL используется как доказательство multi-DB atomicity; unsafe raw DB `cp` вместо SQLite-consistent snapshot; оригинальный 3.8-GB DB подвергается мутациям, checkpoint, WAL manipulation или clone corruption; access to `captiv-prod`; любое изменение runtime readiness/systemd/config/SQLite durability; commit/push/PR/deploy вне отдельного GO.

**Rollback только disposable:** остановить synthetic subprocess, удалить ТОЛЬКО созданные test-owned temporary DB/candidates, оставить operational index и service нетронутыми; сохранить логи и вернуться к base in disposable worktree. **Простой rollback Git кода после реального cutover НЕ защищает acknowledged данные**, такую схему не применять.

## 7. Decision return to Architect / Owner

**Этот TASK не решает окончательно:**

- Как реализовать cross-store publication authority, anti-rollback и независимую защищённую attestation от неавторизованной замены истории?
- Каков точный контракт durable ACK при существующем SQLite WAL `synchronous=NORMAL` для process crash vs host power loss, и нужен ли иной **отдельно согласованный** durability policy?
- Как сохранять cross-generation pinned reads при retention/rotation/late arrivals, включая Source Health unknown и reader/session lifetime?
- Как отделить HOT active READY от archive-history status без нарушения существующих consumers и health API, и какое явное Owner acceptance требуется для изменения модели доверия?
- Какие hot-size/page/time thresholds и rollover cadence достижимы на реальном LAB HDD без роста write amplification, и как выглядит independent rollback при уже принятых после cutover ACK?

**Дальнейшая последовательность:** Coder focused LAB-00 proof → TL independent research acceptance → Architect адресный design adjudication/P2 runtime implementation admission → новый строго ограниченный runtime task (если GO) → TL full gates/physical HDD → publication/merge/Owner production GO отдельно.

```ini
TASK=QIO-EVIDENCE-IDLE-02-P2-LAB-00-HOT-ARCHIVE-TRUST-PROOF
ARCHITECT_CONTRACT=v1.3
BASE_HEAD=810484e69baa371c4696c3b46654199631538fc4
BASE_TREE=6816e73148c91c1e2e778613067a41d8c973c03d
CODER_LAB_RESEARCH=GO_THIS_TASK_ONLY
CODER_RUNTIME_IMPLEMENTATION=HOLD
FAST_READY=HOLD
INTEGRITY_MODEL=TARGET_T3_AT_ARCHIVE_SEAL
SINGLE_MUTABLE_AUTHORITY=HOT_ONLY_CANDIDATE_MODEL
ORIGINAL_L0_FULL_QUICK_CHECK=PASS
P2_LAB_01_VALIDATOR_REPLACEMENT=REJECTED
N08_N11=P1_SPEC_GAP_DISPOSABLE_FIXTURES
HOST_PHYSICAL_HDD_SAVINGS=UNPROVEN
ORIGINAL_3_8GB_DB_MUTATION=FORBIDDEN
CAPTIV_PROD=DO_NOT_TOUCH
NETWORK_METADATA=OUT_OF_SCOPE
COMMIT_PUSH_PR_MERGE_DEPLOY=NO
OWNER_RUNTIME_GO=NOT_GRANTED
```
