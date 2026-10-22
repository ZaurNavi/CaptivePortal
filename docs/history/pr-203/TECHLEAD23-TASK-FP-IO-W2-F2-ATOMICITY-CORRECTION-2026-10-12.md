# TECHLEAD23 — Fingerprint Wave 2: точечное исправление F2 / SQLite group atomicity

**Дата:** 2026-10-12  
**Исходное задание:** `TASK-FP-IO-W2-IMPLEMENT-01`  
**Статус:** `FIX_REQUIRED / F2_SOURCE_HOLD`  
**Исполнитель:** Coder — только исходный код  
**Контроль:** TechLead23 — самостоятельно все тесты, QA, публикационный допуск, production

## 1. Подтверждённая исходная поставка

- Repo: `ZaurNavi/CaptivePortal`
- Parent HEAD: `385fecebd2bd8778c3a2034514d9e72587984753`
- Parent TREE: `baefd2c4fbceff51aade93d840d93fc81a88fd58`
- Рабочее дерево Coder: `/home/zaur_navi/captivportal-lab/worktrees/fp-io-w2-implement-01`
- Получено 6 файлов, `+561/-22`, patch 38 630 bytes, SHA256 `6f2d49b624692679038e82b0b6a9d5995904cbe6d4659f537423001fd4b80485`.
- Независимая Lab TechLead: `780/780` исходных тестов PASS, 18 Python-модулей AST PASS, `8/8` новых исследовательских тестов PASS (один из них *воспроизвёл дефект*, а не подтвердил корректность).
- Изоляция: тесты выполнялись на независимой копии; Coder worktree/production не изменены.

## 2. Подтверждённый дефект F2

Текущий `SensorSpool` подключён к SQLite с `isolation_level=None`. Вызов `with connection: connection.executemany(...)` **не создаёт транзакцию**. В результате каждая `INSERT OR IGNORE` самостоятельно фиксируется. При отказе третьей вставки две первые уже становятся долговременными записями. Это **нарушает обязательный T06 архитектурного контракта** `ARCH-DEVICE-FINGERPRINT-IO-WAVE2-WRITE-PATH-CONTRACT-v1`: успешный групповой flush должен быть атомарным («целиком COMMIT или целиком ROLLBACK»).

**Независимое воспроизведение:** в изолированной временной SQLite-базе установлен тестовый `BEFORE INSERT` trigger с `RAISE(ABORT)` для третьего события; при coalescer flush 32 событий первые **2** записи остались в таблице, `connection.in_transaction=False`. Это является отрицательным T06.

**TechLead23 disposition:** T06 трактуется буквально как **group-level atomicity для F2 coalesced evidence flush**, а не как атомарность отдельных SQL statements. Отдельное обращение к Архитектору не требуется: требование уже явно утверждено архитектурным контрактом. Разрешается узкая реализация транзакционной границы **только для F2**, без изменения legacy/OFF режима и без включения F2 в production.

## 3. Единственная исправительная задача Coder

Исправить вызов сохранения coalesced evidence prefix с использованием существующего `SensorSpool` как единственного durable writer:

1. В `app/device_fingerprint_sensor/spool.py` предоставить внутренний opt-in вызов **для одного F2-буфера evidence**. Рекомендуемый фиксированный интерфейс: `SensorSpool.enqueue(events, *, atomic_coalesced=False)`; default `False` обязан оставить прежние транзакционные границы без изменений. Разрешено одно эквивалентное внутреннее приватное API, если оно лучше сохраняет backward compatibility. Никаких новых production/env flags.
2. В ветке `atomic_coalesced=True` **только вставки одного однородного evidence prefix** (до 32 записей, не более 262144 serialized bytes согласно coalescer) выполнять как **ровно одну SQLite transaction**: `BEGIN IMMEDIATE` → вставки с прежним `INSERT OR IGNORE` → `COMMIT` на полном успехе; при ошибке до COMMIT — `ROLLBACK`. Никакая неуспешная часть группы не должна остаться зафиксированной. Проверить все path-выходы и то, что соединение не остаётся в состоянии `in_transaction` после сбоя. Не расширять существующий `MAX_TRANSACTION_ROWS=100`.
3. Применять новый режим **только из `_flush_locked()` нового `IngressCoalescer`**, когда на диске должен появиться накопленный homogeneous evidence prefix. Вызовы `source_health` barrier, одиночного oversized-event bypass, legacy spool enqueue, ACK, retry, обычного прямого ingress и F1-only режима по-прежнему используют старую транзакционную семантику.
4. Существующие `purge_stale`, входную проверку 24h TTL, `_make_room`, row/byte/headroom capacity authority и отсутствие schema migration сохранять. Не смешивать удаление ACK с F2 group transaction и не изменять HTTP-delivery semantics.
5. Если `io_stale_purge_gate_enabled=true` одновременно с `io_ingress_coalesce_enabled=true`, cache `next_possible_stale_at_utc` нельзя обновлять как доказанный successful durable insert **до COMMIT**. Решение: собирать действительно вставленные timestamps и отражать их в memo только после успешного COMMIT; при любой ошибке/rollback переводить memo в `UNKNOWN` и запускать обычную DB-derived refresh перед следующей попыткой skip. `INSERT OR IGNORE` duplicate не должен ошибочно расширять срок хранения.
6. Не ослаблять `journal_mode=DELETE`, `synchronous=FULL`, `ACK-after-200`, source-health immediacy, FIFO, лимиты F2 (`32 / 100 ms / 256 KiB`), fallback, crash envelope. **Crash до durable flush по-прежнему допускает потерю ещё не зафиксированных событий** и остаётся запрещённым к production activation без отдельного решения Owner.

## 4. Контрольные сценарии для TechLead23 — не поручаются Coder

- **F2 SQL-failure test:** trigger `RAISE(ABORT)` на третьей вставке из 32 → ни одна новая запись этой группы не зафиксирована, нет незакрытой транзакции. Уже ранее durable spool rows продолжают существовать.
- **F2 successful group:** 32 уникальных ID фиксируются одним атомарным batch, следующий 1 ID фиксируется по 100ms timeout; exact stable IDs, order, source-health barrier сохраняются.
- **F2 + F1 cache:** при transaction rollback кэш UNKNOWN/валидно восстановлен и stale data не переживает строгий 24h boundary; при полном COMMIT memo не выходит за фактический minimum.
- **Default OFF and F1-only:** прежняя работа без нового SQL BEGIN, действующие регрессионные тесты неизменны.
- **ACK/HTTP:** no ACK on non-200/ambiguous; ACK deletes exact successful request row IDs; no schema/PRAGMA changes.
- **Crash power/process simulated in Lab:** before and during transaction no malformed spool / partial group; source-health immediate.

**Все тесты, профилирование, верификацию, публикационный допуск и deployment проводит TechLead23. Coder их не выполняет.**

## 5. Строгие границы и handoff

- Исправить только нужные исходники, преимущественно `spool.py` и `ingress_coalescer.py`; если нужен другой файл, кратко указать причину.
- Использовать **тот же** незакоммиченный Coder worktree. Существующие пять модифицированных и один новый файл не сбрасывать. Не затрагивать другие worktree.
- Не выполнять git commit/push/PR/merge, production restart, deployment, измерения или тесты.
- Вернуть **полный обновлённый patch от точного Parent**, `SHA256`, `wc -c`, список файлов, короткую заметку о F2 transaction boundary и подтверждение `COMMIT/PUSH/PR/MERGE/DEPLOY=NO`.
- После исправления **STOP**, передача TechLead23 для независимой проверки.

```
TECHLEAD23 = SOURCE REVIEW: F1 REGRESSION PASS / F2 HOLD
F2_T06_GROUP_ATOMICITY = FAIL (REPRODUCED)
NARROW_F2_TRANSACTION_REPAIR = AUTHORIZED FOR SOURCE ONLY
CODER_ACTION = TARGETED_CODE_FIX
COMMIT/PUSH/PR/MERGE = HOLD
PRODUCTION = UNTOUCHED / HOLD
```
