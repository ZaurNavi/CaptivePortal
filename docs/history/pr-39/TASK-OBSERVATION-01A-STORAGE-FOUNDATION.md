# TASK-OBSERVATION-01A — Storage Foundation v1

**Проект:** CaptivPortal
**Родительский документ:** `TASK-OBSERVATION-FOUNDATION-01 — REV2`
**Тип:** самостоятельное execution-ТЗ / PR A
**Статус:** READY FOR OWNER APPROVAL
**Implementation authorization:** не дана; старт только по команде owner: `TASK 01A утверждено, начинать PR A`
**Следующий этап:** TASK 01B запрещено начинать до merge и приёмки 01A

## 1. Результат

Создать независимый Site-aware persistence/read/cleanup foundation для будущих Client и AP observations без Omada polling и без production activation.

PR A должен дать:

- `app/observations/` с config/models/repository/read service/cleanup primitives;
- SQLite schema v1;
- lifecycle `running → completed` и crash recovery `running → abandoned`;
- FK, UNIQUE и idempotency;
- fixed-width UTC timestamps;
- bounded retention/cleanup;
- capacity assessment, на основании которого Tech Lead утверждает либо меняет cadence/retention до PR B.

## 2. Baseline gate до изменений

На exact `origin/main` зафиксировать SHA и до первого изменения выполнить:

```bash
python -m pytest -q -rs
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc python -m compileall -q app
git diff --check
git status --short
```

Если runtime отличается от baseline родительского REV2 `a79e0a3`, сравнить изменения. Связанные runtime-изменения — stop condition и review Tech Lead.

Зафиксировать exact SHA, passed/skipped/failed, compileall, diff-check и состояние дерева.

## 3. Жёсткие границы

Не менять Snapshot Collector, Snapshot schema/log/retry, Visitor Registry schema, Auth/CAPPORT, Cleaner, Public Traffic и существующий token lifecycle. Не создавать второй `OmadaProvider`.

В PR A запрещены:

- Omada periodic workers и HTTP calls;
- Client/AP normalizers и polling;
- `run.py` production lifecycle integration;
- Visit Lifecycle, Analytics, HTTP API, Grafana/Alloy;
- systemd/env production changes, deploy/restart;
- новые внешние dependencies.

Observation failure всегда fail-open для CaptivPortal.

## 4. Configuration

Добавить в существующий config pipeline безопасные defaults, необходимые storage/query/cleanup/capacity. Master default:

```text
OBSERVATION_FOUNDATION_ENABLED=false
OBSERVATION_DB_PATH=/opt/CaptivePortal/data/observations.sqlite3
OBSERVATION_DYNAMIC_RETENTION_DAYS=180
OBSERVATION_CONFIG_RETENTION_DAYS=730
OBSERVATION_CLEANUP_INITIAL_DELAY_SECONDS=900
OBSERVATION_CLEANUP_INTERVAL_SECONDS=86400
OBSERVATION_CLEANUP_BATCH_SIZE=5000
OBSERVATION_CLEANUP_MAX_DURATION_SECONDS=30
OBSERVATION_SHUTDOWN_TIMEOUT_SECONDS=20
```

Production values не добавлять. Invalid enabled config делает Observation unavailable, но не мешает portal startup.

## 5. Schema v1

Default DB: `/opt/CaptivePortal/data/observations.sqlite3`; `PRAGMA user_version=1`, `foreign_keys=ON`, bounded `busy_timeout`, WAL preferred, `synchronous=NORMAL` допустим, startup `quick_check`, POSIX mode `0640`.

Таблицы:

```text
observation_cycles
client_observations
ap_observations
ap_radio_observations
ap_config_snapshots
```

Все persisted timestamps: `YYYY-MM-DDTHH:MM:SS.mmmZ`, строго UTC, fixed-width, лексикографически сортируемые.

### observation_cycles

Минимум: `cycle_id PK`, `kind`, `site_id NOT NULL`, `state`, `started_at`, nullable `finished_at/abandoned_at/complete/result`, counters, `created_at/updated_at`.

`kind`: `client|ap_dynamic|ap_config`; `state`: `running|completed|abandoned`; completed result: `success|partial|failed|shutdown`.

До network work будущий worker создаёт `running`; normal finalize выполняется atomic update; startup repository атомарно переводит оставшиеся `running` в `abandoned`, сохраняя `finished_at=NULL`. Cleanup cycle здесь не записывать.

### Idempotency/FK

```text
client_observations: UNIQUE(cycle_id, client_mac)
ap_observations: UNIQUE(cycle_id, ap_mac)
ap_radio_observations: UNIQUE(ap_observation_row_id, band) либо подтверждённая radio_identity
ap_config_snapshots: UNIQUE(cycle_id, ap_mac)
ap_config_snapshots: UNIQUE(site_id, ap_mac, config_sha256)
```

Все child cycle FK — `ON DELETE CASCADE`; radio также ссылается на AP observation с cascade. Partial AP config row не существует.

Создать индексы из master REV2 для Site+MAC/time, Site+time, AP/SSID/radio filters, AP radio, config и cycles. Обычные индексы не заменяют FK/UNIQUE.

Network calls никогда не выполняются внутри SQLite transaction. Writes — короткими сериализованными transactions.

Schema newer than code, corruption, `SQLITE_FULL` и I/O failure → Observation unavailable/degraded без auto-delete/drop/recreate и без emergency deletion.

## 6. Read service

Внутренний read-only `ObservationReadService`, без Flask routes. Реализовать client/AP/radio history и latest methods, включая latest complete AP config.

Контракт:

- обязательный `site_id`, никаких cross-site queries;
- strict time/MAC validation;
- default limit 500, hard max 2000;
- stable order и opaque cursor по `(observed_at, row_id)`;
- malformed cursor → explicit validation error;
- immutable DTO, не `sqlite3.Row`;
- никаких business analytics.

## 7. Cleanup

Global maintenance, без row в `observation_cycles`. Bounded batches/time, UTC cutoffs, shutdown checks, cascade-safe deletion, не удалять `running` текущего process, `abandoned` очищать по retention kind. Automatic full `VACUUM` запрещён.

## 8. Capacity gate

До PR B подготовить таблицу минимум для 50/100/300 clients и 2/10/30 AP:

- rows/day и rows/180 days по каждой table;
- estimated bytes/row, indexes и общий DB size;
- write rate и cleanup cost;
- свободное место/backup implication;
- benchmark representative inserts и read queries.

Отдельно показать worst case: 300 clients × 1/min × 180 days = `77,760,000` client rows до AP/index overhead.

Если объём неприемлем — stop; не начинать 01B/01C до решения retention/cadence/backend.

## 9. Tests и acceptance

Обязательны targeted tests schema/user_version/indexes/FK/UNIQUE/cascade, cycle lifecycle/recovery, fixed UTC ordering, corruption/newer schema, POSIX mode, atomic batches, busy/full classification, cleanup bounds/interruption, query filters/cursors/no cross-site leakage и immutable DTO.

После targeted выполнить Visitor Registry/Snapshot regressions и полный gate из section 2.

Acceptance PR A:

- новых failures относительно pre-change baseline нет либо классификация доказана;
- polling/runtime integration отсутствуют;
- capacity report принят Tech Lead/архитектором;
- retention/cadence direction утверждено;
- diff только allowed scope;
- production не менялась.

## 10. Repository actions и handoff

Рекомендуемая ветка: `feature/observation-storage-v1`. Commit допустим после green tests. Push/PR/merge — только по отдельному разрешению owner.

Handoff: baseline SHA, changed files/reasons, schema/index/FK contracts, query methods, cleanup, capacity table, exact commands/results, security verdict, risks и repository actions.
