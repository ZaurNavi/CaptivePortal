# CAPTIVPORTAL — QIO-02
## Tech Lead Architecture Review / P0 Admission & P1 Evidence Directive v1

**Дата:** 2026-10-16 (Asia/Baku)  
**Владелец:** Tech Lead — Performance & Optimization  
**Входной контракт:** `CAPTIVPORTAL-QIO-02-SQLITE-SMALL-IO-ARCHITECTURE-ADMISSION-CONTRACT-v1-2026-10-16(1).md`, Chief Architect v1; предыдущий Tech Lead Architecture Request v1.  
**Режим:** READ-ONLY P1; **НЕ Coder TASK**, НЕ production change, НЕ разрешение на Lab implementation.

## 1. Решение

**`P0=PASS` / `SEMANTIC_ARCHITECTURE=ACCEPTED_WITH_MODIFY`** — контракт Chief Architect принят как нормативная граница допустимых оптимизаций. Принимаем отказ от правила «неизменный payload ⇒ можно пропустить COMMIT». Нужна одновременная доказанность обязательств **N1–N7**, включая физический net benefit.

**`P1=EVIDENCE_REQUIRED` / `P2=HOLD` / `CODER=HOLD` / `PRODUCTION=NO_CHANGES`.** Архитектурный PASS сам по себе не разрешает править SQLite. Если измерения или consumer graph опровергают H1, он отклоняется, а не оптимизируется любой ценой.

**Уточнение stage sequence:** N7 (доказанный net physical win после изменения) относится к финальному допуску самого no-op guard в эксплуатацию, а не является логически достижимым prerequisite до разработки экспериментальной версии. Для P2 необходимы реальный базовый per-operation physical cost, consumer audit и одобренный изолированный Lab-эксперимент; после Coder implementation Tech Lead доказывает N7 в matched A/B Lab. Если Chief Architect трактует N7 как обязательный до любого Lab-кода, нужен отдельный ответ архитектора, а не произвольное ослабление gate.

Независимую от Coder техническую приёмку, полные Linux/Windows regression, crash/replay/security/PERF gates выполняет **сам Tech Lead**. **Отдельной организационной роли «независимый QA» нет**; формулировку договора Chief Architect про «independent review and QA» трактуем как эти обязанности Tech Lead.

## 2. Текущая read-only сверка (не physical causality proof)

- GitHub `main` (сверен 2026-10-16): `e2cbd96916d8a81f07f0d79a1a745f593ccb5114`; PR #215 открыт и находится в Draft. Изолирован от QIO-02.
- Production `/opt/CaptivePortal` read-only Git HEAD: `e2cbd96916d8a81f07f0d79a1a745f593ccb5114`; tree: `8c95448250d75b01580bfdd4c52a40cf71a288af`. Loaded-artifact каждого worker и runtime Settings/paths/flags требуют отдельной P1 сверки; Git HEAD не является им автоматически.
- `app/public_traffic/reader.py`, `_process_source()`: partial-line path вызывает `observe_source` отдельно (~line 194), а complete EOF path вызывает **финальный `observe_source`** (~line 225), включая steady idle.
- `app/public_traffic/repository.py`, `observe_source()` (~lines 345–369): `BEGIN IMMEDIATE` → `_upsert_reader_state` → `commit()`.
- `_upsert_reader_state()` (~lines 716–758): `ON CONFLICT DO UPDATE` включает `updated_at = excluded.updated_at` без `WHERE changed`; путь годится для **исследования**, не автоматического пропуска.
- `get_reader_states()` (~lines 183–210) возвращает source identity/path/offset/checkpoint/observed_size/retired/missing, но **не `updated_at`**. Read-only поиск прямого `reader_state.updated_at` в Python `app` не обнаружил непосредственного Public Traffic consumer; это лишь ограниченный source inventory, не исчерпывающий external consumer graph. Отдельный `SELECT MAX(updated_at)` в analytics читает **`visit_reader_state`**, его нельзя ошибочно приписывать Public Traffic.
- Ни один из этих source observations не доказывает, что `observe_source` — лидер physical host writes или что его удаление безопасно.

## 3. Зафиксированные архитектурные границы

**Visitor Registry:** `mark_successful_scan()` и durable `last_successful_scan_at` сохраняются после каждого complete scan. Снижение частоты timestamp — отдельное архитектурное решение с доказанным consumer freshness SLA, **не QIO-02 v1**.

**Current State:** каждый `publish_cycle()` обязателен, в том числе successful empty и partial/error. Отрицательный факт об отсутствии клиента — это новый временно ограниченный authoritative proof, а не «нулевой payload».

**Visits:** никогда не пропускать auth/open/close, offsets/checkpoints, retries, pending match или source-state transitions; 0 входных строк не гарантирует 0 durable progress.

**Public Traffic H1:** единственный условно перспективный первый кандидат — redundant final `observe_source()` на genuine unchanged, same-generation EOF, **только** если `updated_at` не доказывает freshness и tuple действительно эквивалентен с гарантиями конкурентности/crash/replay.

**Observations:** каждый cycle/attempt со статусом `running/success/partial/failure/abandoned` и source scope сохраняет свой смысл и требует соответствующего durable proof.

**Запрещено:** снижать SQLite PRAGMA durability, удалять WAL/fsync/checkpoint, global batching, междоменную коалесценцию authority, `VACUUM`/`REINDEX`/heavy trace на production. Отдельно исследовать cold-start read stalls, не смешивать с steady-state write attribution.

## 4. P1 — Consumer graph для Public Traffic

Подтвердить и задокументировать по коду + runtime конфигурации:

1. Где читается `reader_state` и поле `updated_at`: PublicTraffic reader/repository, background service/API, Admin/Public UI, analytics, health/readiness, alerts, retention/cleanup, replay/forensic tools, внешние dashboard/скрипты/DB readers.
2. Есть ли гарантии «последний успешный полный скан» / source-observed freshness в `updated_at`; значение `NULL`/отсутствие прогресса при исходном no-op; не смешивать с `traffic_daily.updated_at` и `visit_reader_state.updated_at`.
3. Полный persisted tuple: `source_identity`, `source_path`, `source_offset`, `source_checkpoint`, `last_observed_size`, `retired_completed`, `missing_warning_emitted`, relevant source generation/reappearance/truncation/missing; точная transaction/lock/CAS owner boundary.
4. Для positive/negative случаев разобрать: empty same inode EOF; appended line (включая traffic=0); incomplete tail; rotated backup; truncated/replaced inode; missing/reappearing source; updated checkpoint despite same offset; source retired; concurrent writer; kill before/after commit; new process restart/replay.
5. Если существует хотя бы один обязательный freshness consumer, зависящий от повторной записи `updated_at`, **H1=REJECT** в рамках текущего контракта. Не скрывать требование случайным throttling.

## 5. P1 — Per-DB/physical write attribution

Составить матрицу для `public_traffic.sqlite3`, `visitor_registry.sqlite3`, `visits.sqlite3`, `current_state.sqlite3`, `observations.sqlite3`:

`DB → owner/worker → trigger/cadence → exact operation/SQL → committed facts and timestamps → BEGIN/COMMIT and observed WAL/fsync/lock → guest cgroup wios/wbytes → host QEMU/cgroup wios/wbytes → host /dev/sda completed writes/await/busy`.

Только **синхронные** временные границы и корректная карта device IDs. Не складывать `252:0` и `253:0` как независимые физические I/O. Не приписывать host IOPS процессу портала без изоляции и конкурирующих I/O contributors. Отдельно фиксировать load, guest clients, auth health, Omada responses, source age/backlog, snapshot/retention/cron и host background jobs.

Минимум **три сопоставимых quiet окна по 10–15 минут**, до/после однотипной Lab-гипотезы — только после допуска P2; в P1 собрать baseline в разных временных интервалах и условия для повторения. Нужны также normal/peak/catch-up сценарии в disposable Lab. На production только bounded read-only sampling; никакого restart, профилирования, которое существенно увеличивает HDD load, и никаких изменений SQLite.

**Проверяемая метрика:** причинно связанное снижение completed host physical writes/sec и/или latency при неизменной корректности/auth/health. Меньше JSON логов или SQL шагов — недостаточно.

## 6. Дальнейший gateway и владельцы тестов

- **P1 Tech Lead:** собрать `QIO-02 PER-DB PHYSICAL-WRITE & CONSUMER-SEMANTIC EVIDENCE` с количественным ranking, semantic graph, risk/unknowns и recommendation `H1 PASS_TO_LAB / H1 REJECT / ALTERNATE`.
- **P2 Chief Architect:** рассмотреть доказательства и отдельно разрешить один точный Lab-алгоритм/гипотезу. До него **Coder HOLD**.
- **P2 Tech Lead:** создать narrow Coder TASK с exact baseline, file allowlist, invariants C01–C18, rollback, STOP conditions.
- **P3 Coder:** только focused tests, compile/diff, exact tree/replacement patch/evidence, без commit/push/PR.
- **P3 Tech Lead:** самостоятельно воспроизвести изменённое дерево и **полные Windows/Linux regression**, crash/replay/security gates и matched lab performance, включая host HDD и auth E2E.
- **P4/P5:** публикация → Owner merge решение → отдельный Owner production GO → staged deploy/rollback/monitoring; эффект доказать, а не предположить.

## 7. Текущая диспозиция

```ini
TASK=QIO-02
ARCHITECTURE_CONTRACT=v1_ACCEPTED_WITH_MODIFY
P0_SEMANTICS=PASS
P1_ATTRIBUTED_EVIDENCE=OPEN
H1=SOURCE_CODE_CONFIRMED_CONDITIONAL
H1_CONSUMER_GRAPH=INCOMPLETE
H1_HOST_PHYSICAL_COST=UNPROVEN
P2_LAB_ADMISSION=HOLD
CODER=HOLD
FULL_TESTS_OWNER=TECH_LEAD
INDEPENDENT_QA_ROLE=NONE
PRODUCTION_MUTATION=NO
COLD_START_READ=SEPARATE_TRACK
QIO_01D=SEPARATE_TRACK
PR_215=UNTOUCHED
```

**Важное ограничение:** первая статическая проверка только подтверждает путь вызова и SQL; не является основанием для внедрения. Контракт требует реального consumer audit и операционно воспроизводимой I/O причинности.
