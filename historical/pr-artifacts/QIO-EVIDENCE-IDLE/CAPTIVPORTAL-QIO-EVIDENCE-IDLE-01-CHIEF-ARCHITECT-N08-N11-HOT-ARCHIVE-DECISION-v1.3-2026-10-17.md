# CAPTIVPORTAL — QIO-EVIDENCE-IDLE-01
## Chief Architect — P2-LAB-01 Research Closure, N08/N11 Integrity Adjudication and Hot/Archive Architecture Decision v1.3

**Дата:** 2026-10-17 (Asia/Baku)  
**Адресат:** Performance & Optimization Tech Lead (передача через Owner)  
**Источник:** `QIO-EVIDENCE-IDLE-01-P2-LAB-01-INDEPENDENT-TECHLEAD-REVIEW-2026-10-17(1).md`; архитектурные контракты v1.1, v1.2.  
**Строгий scope:** старая лабораторная VM `192.168.0.202`, Fingerprint Evidence only; HDD гипервизора `omv-hp`. Новый действующий `captiv-prod`, Network Metadata, NI-02A, QIO-05, иные модули — **OUT OF SCOPE**.  
**Правовой/исполнительский эффект:** архитектурный вердикт и направление для нового узкого **LAB TASK**; **не** runtime implementation GO, **не** одобрение publication/PR/merge/deploy/production change.

## 1. Решение

**`DECISION=MODIFY; P2_LAB_01=CLOSE_NEGATIVE_FOR_REPLACEMENT; NEXT_ARCHITECTURE=HOT_INGRESS_PLUS_SEALED_HISTORY; NEW_LAB_DESIGN=PASS_WITH_GATES; RUNTIME_READY_CHANGE=HOLD`.**

Прямая попытка «дешевле перечитать все 3.8 GB с прежней полнотой проверки при каждом рестарте» не является решением. Стоимость полного обхода нижне ограничена количеством страниц, которые требуется просмотреть, а под HDD contention физическое чтение может занимать десятки минут. Решение — **уменьшить объект обязательной синхронной проверки перед новым ingest**: небольшое независимое active/hot-хранилище и ранее проверенная, запечатанная, не записываемая история с собственным статусом доверия. В переходе требуется разовое долгое построение/проверка истории. Не разрешается выдавать старую непроверенную историю за healthy.

Это **новая архитектурная граница** и отдельный TASK, а не «рефакторинг» текущего `_validate_connection`. Если Tech Lead хочет просто удалить deep scans или заменить их metadata-only — **REJECT**.

## 2. Измеренные факты и интерпретация

- База L0: `3,796,074,496` байт, `926,776` страниц, `last_ingest_sequence=2,834,788`; исходник audit `810484e69baa371c4696c3b46654199631538fc4`.
- Полный `PRAGMA quick_check`: **PASS**, literal `ok`, `3352.86 s` (55:52.86), `3,961,155,584` байт process reads; проход sequence Evidence: PASS `148.402 s`; Source Health: PASS `0.106 s`; cross-table collisions: PASS `1.252 s`. Это разные последовательные L0-фазы, **не** точный production startup SLA.
- HDD read pressure подтверждён; exclusive physical host IOPS/per-candidate win не измерены. Лаборатория Owner позволяет честные полные замеры непосредственно на VM/HDD, без искусственного PSI/quiet STOP; оригинальную БД не повреждать.
- Точный исследовательский candidate на четырёх **добавленных** файлах воспроизведён независимым Tech Lead; Linux **53 PASS**, Windows **53 PASS**, 0 fail/skip. Полные проектные gates не выполнялись, runtime code не менялся.
- N08: искусственно повреждённый UNIQUE индекс прошёл `quick_check`, но был найден `integrity_check` и таблицей. N11: индекс скрывает строку таблицы; результат `quick_check` зависит от SQLite 3.37.2/3.40.1/3.46.1. Ни N08, ни N11 **не свидетельствуют**, что реальные 3.8 GB повреждены.

## 3. Архитектурные ответы A1–A4 на возврат Tech Lead

### A1 — Объём обещанной целостности: два различных контракта

**Legacy T1 (описание факта):** успешный `PRAGMA quick_check`, точные метаданные/DDL, существующие range/type guards и cross-family collision guard на определённом SQLite snapshot. Этот пакет **не** является гарантией обнаружения произвольной порчи UNIQUE/index-table. Даже `quick_check=ok` из L0 не подтверждает это; N08 это опровергает. Запретить формулировки `ALL_ON_DISK_CORRUPTION_EXCLUDED` и `STRONG_INTEGRITY_PROVEN`.

**Целевой contract T3 (архитектурное требование, не текущий PASS):** при первичном seal исторической версии выполнить полную `PRAGMA integrity_check` **плюс** явные доменные семантические инварианты, включая глобальную непересекаемость `ingest_sequence`, singleton, schema signature, CHECK/тип/диапазон, архивный cutover watermark, producer identity/idempotency; результат `ok` только при полном завершении. SQLite `integrity_check` сильнее `quick_check` в части UNIQUE/index-table, но также не доказывает абсолютное отсутствие любых возможных семантических, аппаратных или будущих повреждений. Не смешивать этот более сильный целевой уровень с историческим T1.

Ни `MIN/MAX`, ни принудительный covering-index scan, ни forced table scan без отдельной проверки всех индексов не заменяют T3. При сомнительном индексе `NOT INDEXED` может выявить проблему, но сама по себе не доказывает всю структуру БД.

### A2 — Исправление проверки и READY

- **На существующем едином файле:** нет быстрого доверенного стартового алгоритма, представленного в evidence. До нового архитектурного admission сохранять прежнюю runtime-политику. Не заменять `_validate_connection` на `_validate_runtime_connection` и не запускать HTTP ingest на основании одних метаданных.
- **На отдельной активной БД:** выполнять полный требуемый integrity/sequence gate **только над её ограниченным размером**, изолированно от исторических страниц. Новый активный ingest `READY` возможен **после** доказанного полного active trust, проверенного единственного writer authority и безопасного cutover state.
- **Для архива:** до полного T3 seal/audit — `HISTORY_UNVERIFIED`; после подтверждения — `HISTORY_TRUSTED_AT_SEAL`, с отдельным freshness/continuous immutability условием; нарушение hash/ACL/manifest/read consistency/SQLite error — `HISTORY_QUARANTINED`. History API обязан сообщать unavailable/unknown, **не** возвращать пустую выборку как подтверждённое отсутствие. При переходном дизайне изменение глобального readiness имеет отдельные consumer/API/Owner gates.
- Фоновый аудит не может «исправить» невалидное прошлое задним числом. Не допускается последовательность `READY(true) → бесконтрольное допроверим позже` при одном неразделённом авторитете.

### A3 — Классификация расхождения

- `N08/N11`: **P1 — correctness/integrity specification gap**, а не доказанный P0 incident на реальной базе. Немедленного emergency production change/restart **нет**. Старый T1 неправильно характеризовать как all-corruption fail-closed.
- Более сильная защита исторических данных и изменение модели startup — отдельный архитектурный scope. Повреждённые disposable fixtures отклоняются/карантинируются; текущая реальная база L0 прошла ровно legacy suite, целевой T3 ещё не проходила.
- Owner получает explicit choice: сохранить legacy T1, пока проектируется T3, или назначить план контролируемого усиления при cutover. Архитектор рекомендует **T3 при sealing**, не слепой `integrity_check` на каждом рестарте 3.8-GB DB.

### A4 — Roadmap

1. `P2-LAB-01` **закрыть как research PASS / replacement NEGATIVE**. Не публиковать research-only patch автоматически, не поручать «улучшить MIN/MAX». Его отрицательные N08/N11 оставить regression evidence.
2. Открыть отдельный **`QIO-EVIDENCE-IDLE-02 / HOT-ARCHIVE-TRUST-BOUNDARY`**: сначала **LAB архитектурный дизайн и минимальный disposable proof**, без runtime hooks и production файлов.
3. После Tech Lead evidence и отдельного адресного Architect **P2 implementation admission** решить, какие runtime компоненты можно менять, и выдать один narrow Coder TASK на lab branch. Без этого `RUNTIME_CODER=HOLD`.

## 4. Выбранная архитектура: один hot writer + запечатанные поколения

```text
                HTTPS Fingerprint Evidence / Source Health
                                |
                 one authenticated/authorized writer
                                |
                  HOT SQLite (bounded pages)
                  - durable ingest + ACK
                  - one sequence allocator
                  - complete startup validation
                                |
                      sealed-generation switch
                        (offline, recoverable)
                                |
              ARCHIVE generation(s), READ-ONLY
              - full T3 validation at seal
              - immutable published manifest
              - old events and Source Health
              - indexed historical reads only
```

### 4.1. Hot-store contract

- `HOT` — единственный изменяемый authoritative store для новых Evidence и Source Health. Нельзя сохранять producer ACK до durable INSERT, idempotency/provenance и watermark в **одной SQLite-транзакции внутри hot**; наследовать текущий exact conflict/duplicate semantics.
- Полный startup gate активного хранилища (для его собственного объёма), включая domain guards. Размер ограничить измеренно подобранным threshold по страницам/времени, а не выдуманной константой `5 seconds` или `16 MiB` без HDD benchmarks. При достижении порога — плановая seal/rollover, но не тайно блокировать forever и не стирать неподтверждённые события.
- После штатной аварии активная БД с WAL должна пройти собственный валидный gate; ни memory flag, ни last `mtime`, ни `database_generation_id` без проверенной связи с диском не являются доказательством сохранности.
- Не менять текущие SQLite `PRAGMA synchronous`, WAL mode, schema constraints ради IOPS. Отдельно измерить per-transaction logging, checkpoint и close recovery.

### 4.2. Archive contract

- Архив формируется **только из консистентного SQLite snapshot при остановленном/fenced старом writer**. Использовать SQLite Backup API или другой документированный SQLite-consistent механизм; **не** `cp` живого DB без `-wal` и `-shm` как доказанный backup.
- До публикации выполнить **полный** integrity + семантический T3 на финальном неизменяемом архивном образе. Контрольное хеширование файла/объекта после аудита, сохранение схемы, версии SQLite/метода проверки, generation UUID, cutoff, sequence range и полного результата с причинами ошибки. **Сам хеш в изменяемом manifest не является доказательством того, что страницы остались неизменны**; нужны защита записи/внешнее хранение attestation, fencing old writer, запрет неавторизованной замены и периодический отдельный scrub.
- Если архив непроверен или оторвался от аттестованной версии — карантин и отказ от утверждений о полноте истории. Исторические SQL чтения должны fail closed на SQLite error, а не порождать false-negative evidence. Перепроверка/реаттестация оффлайн допустима в LAB и позже в отдельном расписании.
- Retention 30 дней для Evidence и отдельный margin Source Health сохраняются как **семантика**, а не только место на диске. Требуется стратегия small archive segments/expiry, не продлевать хранение за политику из-за seal; не удалять часть immutable сегмента без новой явно проверенной поколения/отдельной операции.

### 4.3. Global watermark, дубликаты, читатели

- Сейчас оба event-family используют один `last_ingest_sequence`; `database_generation_id` и watermark имеют значение для snapshot readers. Новый дизайн обязан сохранить **глобальный порядок, отсутствие перекрытия последовательностей и snapshot consistency**, включая migration/cutover и concurrent reads. Выделять disjoint sequence ranges между sealed archive и текущим hot; `max_committed_ingest_sequence` не может уменьшаться или переиспользоваться после crash/restore. Не генерировать новые ACK во время неопределённого cutover.
- Unique producer-event IDs проверяются **между HOT и всем сохраняемым архивным периодом**, а не только внутри новой маленькой БД. Index lookup в аттестованном read-only архиве или эквивалентный долговечный global dedup registry обязателен; при недоступной истории/индексе — консервативный отказ, не silently new event. Не позволять другой family занять уже применённый глобальный sequence.
- Existing read paths: Evidence `site_id/mac/observed_at`, Source Health по `site_id/capture_source_id/kind`, time cursor `(observed_at,id)`, pinned snapshot `database_generation_id/last_ingest_sequence`, retention, expiry, health/unknown, UI materialization. Tech Lead должен составить consumer graph, затем определить cross-generation pinned read API без ложной «пустоты». Отдельная проверка событий, попадающих по observed_at в старый период после cutover.
- SQLite `ATTACH` в WAL **не гарантирует аварийно-атомарный COMMIT сразу двух разных DB**; нельзя использовать его вместо cutover-протокола. Все независимые persisted pointers, manifest, archive и hot приводятся к **идемпотентной state machine**.

### 4.4. Durable cutover / recovery contract

Допускается только отдельный явно спроектированный протокол, проверенный на kill/power loss между **каждым** дисковым шагом. Направление, не готовый алгоритм:

1. `PREPARE`: exclusive owner/lock, остановка ingress и drain подтверждённых записей, immutable cutover position, consistent snapshot and backup; старый writer не может принять новые ACK после fencing.
2. `VERIFY`: проверка будущего архивного образа T3; собранный bound manifest и резервная копия; без успешной проверки — **не публиковать**, вернуться к контролируемому старому состоянию или `HOLD`.
3. `CREATE_HOT`: новый маленький SQLite с новым поколением, стартовой границей `> sealed_max_seq`, строгими schema/invariant checks; ещё нет внешнего ACK.
4. `ACTIVATE`: crash-consistent publication state с взаимно проверяемыми reference/identity; отдельно доказать durability fsync файлов и directory-rename/manifest, отсутствие dual-writer и поведения при WAL recovery.
5. `RECOVER`: на любой неопределённости перед/после переключения — single-writer `NOT_READY`, idempotent rollback/forward recovery без duplicate, missing, reused sequence или фантазийных source-health facts. Сначала fencing+reconcile, лишь затем READY.

**Не считать** эти 5 пунктов уже завершённым реализационным алгоритмом. Tech Lead должен принести точную crash matrix и выбор authority для публикации manifest; второй адресный Architect GO обязателен перед производственным code diff.

## 5. Реалистичная граница целостности

Нельзя одновременно требовать на каждом рестарте строго обнаружить **любую** возможную скрытую порчу **любой** из 926,776 исторических страниц и не читать их (если нет отдельно доказанной аппаратной/криптографической модели целостности). Поэтому выбранный контракт *осознанно* переносит проверку запечатанной истории на seal/periodic scrub + immutable attestation, а immediate ingest readiness защищает **полной проверкой только hot store**. Это **изменение модели доверия**, не доказанная эквивалентность текущему монолиту. Требует Owner acceptance перед runtime activation, независимых QA gates Tech Lead и consumer migration.

На этапе лаборатории Owner уже разрешил полные HDD scans/нагрузку на `192.168.0.202`, если не повреждать исходную 3.8-GB DB: отдельные копии для destructive/corruption/fault injection. Ни SSD notebook, ни запреты по PSI не являются обязательными preconditions для этого LAB.

## 6. Следующий исполнимый узкий LAB TASK для Tech Lead → Coder

**ID:** `QIO-EVIDENCE-IDLE-02-P2-LAB-00-HOT-ARCHIVE-TRUST-PROOF` — **design/research prototype only**. Цель: на одноразовых SQLite fixtures доказать, что hot writer and archived generation можно разделить без нарушения sequence/ACK/idempotency/read semantics; исходный production runtime неизменен.

Tech Lead готовит точный TASK с pinned base commit/tree и allowlist **новых** файлов `research/qio_evidence_idle_02/**`, `tests/device_fingerprint/test_qio_evidence_hot_archive_research.py` либо явно согласованных альтернатив; **ни** `app/device_fingerprint/repository.py`, ни `service.py`, `read_service.py`, `cli.py`, `storage_v2.py`, `schema.py`, настройки, service/systemd, ни реальные DB-файлы не менять этим LAB-00. В прототипе допустимы disposable files, explicit integrity_check, backup/restore, synthetic history, source events и fault injection. Никаких commit/push/PR до отдельного Tech Lead publication GO.

Обязательные выходные артефакты LAB-00:

- Полный source/consumer graph и contract-preserving design для global sequence/dedup, snapshot, retention, Source Health.
- Точные machine-checkable состояния `PREPARE/VERIFY/CREATE_HOT/ACTIVATE/RECOVER`, каждому действию — durable owner, проверка fencing, подтверждение recovery.
- Два искусственных поколения, один hot writer и корректный total-order в процессе рестарта, read duplicates across archive/hot, fail-closed при непроверенном archive.
- Отдельный архив с N08 и N11: `integrity_check`/исторические guards должны помешать seal; cases по SQLite 3.37.2, 3.40.1, версии VM с фиксацией различий; никаких invalid index shortcuts.
- Негативные сценарии: crash до/после INSERT/ACK; до/во время/после WAL commit/checkpoint; во время backup; after archive validation before seal; after new hot creation; before/after publication; duplicate producer ID across generations; cross-family same seq; missing/corrupt manifest, external writer; old archive file mutation, inode replace, rollback snapshot, empty/stale source health; late observed_at, retention boundary.
- Измерения на реальном LAB VM/HDD: cold/warm active-only validation versus original monolithic L0 (честно сравнивая workload); archive seal one-time expense отдельно; host /dev/sda, QEMU cgroup, guest /dev/vda, actual API/health timing и read bytes, P95 latency/error. Тяжёлые corruption/injected tests — только на disposable DB, не на оригинале.
- Coder выполняет **focused tests** и exact source/patch evidence. Tech Lead независимо делает full Windows/Linux, security, crash/WAL/replay/physical HDD gates **только после** отдельного GO на runtime-facing candidate.

**LAB-00 research code is admitted in principle AFTER Tech Lead issues narrow task.** Это не разрешает имплементировать production-facing code и не заменяет следующий Architect P2 implementation review.

## 7. Stop criteria / rollback

`HOLD/REJECT`: нет независимого единственного writer; новая запись ACK без durable commit; нарушен global sequence; дедуп не проверяет архив; неверный partial/full snapshot; непроверенная история считается пустой; исторические ошибки скрыты; lineage manifest обрывается после crash/restore; fail-open на повреждении/нечитаемом архиве; некорректная retention expiry; unsupported SQLite version; SQL/trace under test вызывает изменение оригинальной БД; publication/merge/deploy вне GO.

`ROLLBACK`: для лаборатории удалить только disposable candidates; вернуть worktree на exact pinned tree. Для любого будущего runtime cutover отдельно доказать rollback на прежнюю committed generation без утраты подтверждённых после cutover событий — **простой checkout старого кода не является безопасным data rollback**.

## 8. Машинная диспозиция

```ini
TASK=QIO-EVIDENCE-IDLE-01
ARCHITECT_RESPONSE=v1.3
P2_LAB_01_RESEARCH=PASS_ACCEPTED_WITH_LIMITATIONS
P2_LAB_01_VALIDATOR_REPLACEMENT=REJECT_NO_EQUIVALENCE
N08_N11=CONFIRMED_TEST_FIXTURES_NOT_LIVE_INCIDENT
INTEGRITY_SPEC_GAP=P1
LEGACY_T1=EXACT_EXISTING_CHECKS_NOT_ARBITRARY_CORRUPTION_PROOF
TARGET_T3=FULL_INTEGRITY_CHECK_PLUS_DOMAIN_GUARDS_AT_ARCHIVE_SEAL
ARCHITECTURE=MODIFY_TO_HOT_INGRESS_AND_SEALED_ARCHIVE
NEXT_TASK=QIO-EVIDENCE-IDLE-02-P2-LAB-00-HOT-ARCHIVE-TRUST-PROOF
NEXT_LAB_RESEARCH=GO_AFTER_TECHLEAD_TASK
CODER_LAB_RESEARCH=HOLD_UNTIL_TASK
CODER_RUNTIME_IMPLEMENTATION=HOLD
FAST_READY=HOLD_UNTIL_NEW_ARCHITECT_IMPLEMENTATION_ADMISSION
OLD_LAB_VM_HDD_TESTS=OWNER_AUTHORIZED
ORIGINAL_3_8GB_DB_MUTATION=FORBIDDEN
NETWORK_METADATA=OUT_OF_SCOPE
CAPTIV_PROD=DO_NOT_TOUCH
OWNER_RUNTIME_GO=NOT_GRANTED
PR_MERGE_DEPLOY=NO
HOST_PHYSICAL_SAVING=UNPROVEN
```

## 9. Supporting sources

- Tech Lead independent P2-LAB-01 Review 2026-10-17; measured L0 completion, N08/N11 experimental fixtures, pinned candidate/provenance.
- `app/device_fingerprint/repository.py`, `schema.py`, `read_service.py`, `storage_v2.py` at `810484e69baa371c4696c3b46654199631538fc4` (read-only review); code defaults are not proof of loaded production config.
- SQLite documentation: `https://www.sqlite.org/pragma.html`, `https://www.sqlite.org/backup.html`, `https://www.sqlite.org/lang_attach.html`, `https://www.sqlite.org/wal.html`.
