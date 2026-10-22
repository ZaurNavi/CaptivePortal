# TASK-VISIT-LIFECYCLE-01 — Visit Lifecycle v1

**Проект:** CaptivPortal  
**Тип:** master implementation TASK / архитектурное ТЗ  
**Статус:** DRAFT FOR REVIEW  
**Implementation authorization:** НЕ ДАНО  
**Исполнитель:** Coder / coding agent  
**Review:** Tech Lead + архитектор + owner  
**Test responsibility:** agent; production acceptance — owner/Tech Lead  
**Дата:** 13 августа 2026 года  
**Baseline на момент подготовки:** `origin/main@8efa9d89fd11184228be0b385309c1724c52c9e1`

---

## 1. Цель

Реализовать следующий функциональный этап CURRENT Roadmap:

```text
Visit Lifecycle v1
```

Visit Lifecycle создаёт самостоятельную Site-aware сущность `visit` и связывает уже существующие authoritative layers:

```text
Visitor Device
    ↓
successful AUTHORIZED
    ↓
Initial Authorized Client Snapshot
    ↓
OPEN VISIT
    ↓
Client/AP Observation history
    ↓
omada.client_offline
    ↓
CLOSED VISIT
```

Модуль создаёт основу для будущих:

- Visitor / Visit Analytics;
- Wireless Analytics в контексте визита;
- Web Foundation;
- CaptivPortal Admin Console;
- reports.

Visit Lifecycle не является Analytics.

---

## 2. Baseline / prerequisites

На момент подготовки:

```text
origin/main = 8efa9d89fd11184228be0b385309c1724c52c9e1
```

Observation Foundation уже реализован и находится в `main`.

Owner сообщил:

```text
Observation Foundation production activation = PASS
observations accumulate normally
```

Перед implementation:

```bash
git fetch origin
git rev-parse origin/main
git status --short
```

Если current `origin/main` новее:

1. зафиксировать exact SHA;
2. сравнить изменения;
3. если затронуты AuthWorker, Snapshot, Visitor Registry, Observation, Webhook или `run.py` — сначала Tech Lead impact review.

---

## 3. Обязательный pre-change Linux gate

До первой правки:

```bash
python -m pytest -q -rs
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc \
  python -m compileall -q app
git diff --check
git status --short
```

Сохранить:

```text
baseline_sha
passed
skipped
failed
compileall
diff_check
working_tree_state
```

---

## 4. Существующие authoritative sources

### Authorization

Start fact:

```text
AuthRun final_state = AUTHORIZED
```

Поддержать существующие success reasons:

```text
ALREADY_AUTHORIZED
AUTHORIZED_AFTER_ATTEMPT
AUTHORIZED_FINAL_VERIFY
```

### Visitor Registry

Использовать только через:

```text
VisitorRegistryReadService
```

Для:

- `device_id`;
- exact snapshot lookup по `auth_session_id`;
- позднего reconciliation.

### Observation Foundation

Использовать:

```text
ObservationReadService
```

Visit не копирует observation rows.

Логическая связь:

```text
site_id
client_mac
visit.started_at
visit.closed_at
```

### Omada Webhook Normalizer

Finalization source v1:

```text
omada.client_offline
```

Visit Lifecycle не парсит raw Omada webhook text повторно.

---

## 5. Жёсткие границы

Не менять бизнес-контракт:

- Auth/CAPPORT;
- Authorized Client Snapshot Collector;
- Visitor Registry schema;
- Observation schema/cadence;
- Pending Session Cleaner;
- Omada provider/token lifecycle.

Cleaner может вызвать reconnect → обычный offline event.  
Visit Lifecycle обрабатывает этот offline обычным механизмом.

---

## 6. Главный инвариант

Нельзя считать:

```text
1 AuthSession == 1 physical visit
```

v1 invariant:

```text
не более одного OPEN visit
для (site_id + canonical client_mac)
```

Повторный successful AuthRun при уже открытом visit:

- второй visit не создаёт;
- `started_at` не меняет;
- добавляет authorization evidence;
- может заполнить отсутствующие links.

---

## 7. Persistence

Создать отдельную DB:

```text
/opt/CaptivePortal/data/visits.sqlite3
```

Не расширять:

```text
visitor_registry.sqlite3
observations.sqlite3
```

Schema:

```text
PRAGMA user_version = 1
```

---

## 8. Новый package

```text
app/visit_lifecycle/
├── __init__.py
├── config.py
├── models.py
├── repository.py
├── service.py
├── read_service.py
├── start_sink.py
├── webhook_reader.py
├── reconciliation.py
├── runtime.py
└── telemetry.py
```

Допускается минимальное объединение файлов без смешивания responsibilities.

---

## 9. Configuration

Через existing config pipeline:

```text
VISIT_LIFECYCLE_ENABLED=false
VISIT_LIFECYCLE_DB_PATH=/opt/CaptivePortal/data/visits.sqlite3
VISIT_LIFECYCLE_WEBHOOK_SOURCE=/opt/CaptivePortal/logs/omada_webhook_normalized.log
VISIT_LIFECYCLE_SCAN_INTERVAL_SECONDS=5
VISIT_LIFECYCLE_RECONCILE_INTERVAL_SECONDS=30
VISIT_LIFECYCLE_MAX_LINE_BYTES=1048576
VISIT_LIFECYCLE_SHUTDOWN_TIMEOUT_SECONDS=20
VISIT_LIFECYCLE_MAX_OFFLINE_CLOCK_SKEW_SECONDS=120
VISIT_LIFECYCLE_MAX_REPORTED_DURATION_DRIFT_SECONDS=300
```

Repository default:

```text
VISIT_LIFECYCLE_ENABLED=false
```

Production activation — отдельный TASK.

---

## 10. Runtime states

```text
disabled
starting
active
degraded
unavailable
stopping
```

Visit failure всегда fail-open относительно portal/auth.

---

## 11. Tables

Минимум:

```text
visits
visit_authorizations
visit_source_events
visit_reader_state
visit_state
```

Analytics tables не создавать.

---

## 12. `visits`

Минимальные fields:

```text
visit_id TEXT PRIMARY KEY
site_id TEXT NOT NULL
client_mac TEXT NOT NULL

device_id TEXT
initial_snapshot_id TEXT

auth_session_id TEXT
start_auth_run_number INTEGER
start_final_reason TEXT

started_at TEXT NOT NULL
closed_at TEXT
status TEXT NOT NULL
close_reason TEXT
close_time_source TEXT

start_ip TEXT
start_ssid TEXT
start_ap_mac TEXT

final_ip TEXT
final_ssid TEXT
final_ap_mac TEXT

reported_connected_seconds INTEGER
reported_traffic_total_bytes INTEGER
reported_traffic_up_bytes INTEGER
reported_traffic_down_bytes INTEGER

duration_seconds INTEGER

offline_event_id TEXT

created_at TEXT NOT NULL
updated_at TEXT NOT NULL
```

---

## 13. Status

v1:

```text
open
closed
```

Close reason минимум:

```text
omada_client_offline
```

Не вводить business-classification statuses.

---

## 14. Open-visit DB invariant

Database-level constraint обязателен:

```text
UNIQUE(site_id, client_mac) WHERE status='open'
```

или эквивалентный partial unique index.

Service-side check не заменяет DB constraint.

---

## 15. Visit ID

```text
UUIDv4 lowercase canonical text
```

Создаётся только при новом physical-logical visit row.

---

## 16. Timestamp contract

Единый формат:

```text
YYYY-MM-DDTHH:MM:SS.mmmZ
```

Всегда UTC, fixed-width, lexicographically sortable.

Monotonic time не persist.

---

## 17. Visit Start contract

Добавить narrow sink:

```python
class VisitStartSubmitter(Protocol):
    def submit_authorized(
        self,
        request: VisitStartRequest,
    ) -> VisitStartOutcome:
        ...
```

Request минимум:

```text
auth_session_id
site_id
client_mac
authorized_at
auth_run_number
authorization_attempt
final_reason
client_ip
portal_ssid
portal_ap_mac
portal_radio_id
```

Immutable.

---

## 18. AuthWorker integration

Допускается минимальная правка `app/auth/worker.py`:

```text
final AUTHORIZED path
→ safe VisitStartSubmitter call
```

Не менять:

- authorization algorithm;
- retry;
- readiness;
- progress;
- final states;
- CAPPORT;
- Snapshot behavior.

Invariant:

```text
Visit start failure
must not become authorization failure.
```

---

## 19. Snapshot ordering

Snapshot и Visit Start — независимые consumers одного `AUTHORIZED`.

Правильно:

```text
AUTHORIZED
 ├─ Snapshot async submit
 └─ Visit Start submit
```

Запрещено:

```text
wait snapshot → only then create visit
```

Visit может временно иметь:

```text
device_id = NULL
initial_snapshot_id = NULL
```

---

## 20. Create-or-reuse start algorithm

Для authorized request:

1. validate;
2. canonicalize MAC;
3. lookup open `(site_id + MAC)`;
4. если нет — create visit;
5. если есть — reuse;
6. attach authorization evidence;
7. try device/snapshot links;
8. commit;
9. telemetry.

---

## 21. Repeat AUTHORIZED

При open visit:

```text
visit_id = same
started_at = unchanged
```

Повторная авторизация сохраняется отдельно.

---

## 22. `visit_authorizations`

```text
row_id INTEGER PRIMARY KEY
visit_id TEXT NOT NULL
auth_session_id TEXT NOT NULL
auth_run_number INTEGER NOT NULL
authorized_at TEXT NOT NULL
final_reason TEXT NOT NULL
created_at TEXT NOT NULL
```

Idempotency:

```text
UNIQUE(auth_session_id, auth_run_number)
```

FK:

```text
visit_id → visits(visit_id) ON DELETE CASCADE
```

---

## 23. Device linkage

Источник authority:

```text
VisitorRegistryReadService.get_device_by_mac()
```

Если device найден:

```text
device_id = Registry device_id
```

Если Registry временно unavailable / snapshot ещё не ingest:

```text
device_id = NULL
```

Visit всё равно создаётся.

Visit Lifecycle не генерирует собственный device ID.

---

## 24. Initial snapshot linkage

Preferred exact match:

```text
device_snapshots.auth_session_id == visit.auth_session_id
```

Если snapshot доступен:

```text
initial_snapshot_id = snapshot_id
```

Если нет:

```text
NULL
```

Временной nearest-snapshot heuristic v1 запрещён.

Если current read service не умеет lookup snapshot by auth_session_id, допустима только narrow read-only method без Registry schema changes.

---

## 25. Reconciliation

Bounded worker/service заполняет missing:

```text
device_id
initial_snapshot_id
```

Default:

```text
30 sec fixed delay
```

Только через VisitorRegistryReadService.

Правила:

- no Omada call;
- no raw Registry SQL;
- no Registry mutation;
- bounded batch;
- idempotent;
- non-null link автоматически не заменять другим.

---

## 26. Observation linkage

Не добавлять `visit_id` в observations schema.

Не копировать observation rows в visits DB.

Window:

```text
site_id = visit.site_id
client_mac = visit.client_mac
from = started_at
to = closed_at or now
```

Будущая Analytics использует `VisitLifecycleReadService + ObservationReadService`.

---

## 27. Finalization source

Automatic close v1 только:

```text
normalized omada.client_offline
```

No Omada polling in normal close path.

---

## 28. Webhook ingestion architecture

Не помещать Visit DB business logic в HTTP webhook route.

Использовать durable normalized journal:

```text
omada_webhook_normalized.log*
        ↓
VisitLifecycleWebhookReader
        ↓
normalized event
        ↓
VisitLifecycleService.finalize_from_offline()
```

Причины:

- webhook HTTP остаётся fail-open;
- replay после restart;
- rotation-safe;
- durable;
- idempotent.

---

## 29. Reader

По project pattern:

- regular file validation;
- inode/source identity;
- persisted offset;
- rotation/truncate;
- bounded line bytes;
- strict JSON;
- shutdown checks;
- no unbounded read.

Visit reader имеет собственные offsets.

---

## 30. `visit_reader_state`

```text
source_identity TEXT PRIMARY KEY
source_path TEXT NOT NULL
source_offset INTEGER NOT NULL
last_observed_size INTEGER
retired_completed INTEGER NOT NULL
updated_at TEXT NOT NULL
```

Visitor Registry reader state не использовать.

---

## 31. Event identity

До implementation проверить normalized journal schema.

Использовать existing stable event ID, если он есть.

Если нет — определить deterministic event ID из:

```text
safe immutable normalized event fields
+
source identity
+
source offset range
```

Timestamp alone не является unique ID.

---

## 32. `visit_source_events`

```text
event_id TEXT PRIMARY KEY
event_type TEXT NOT NULL
site_id TEXT
client_mac TEXT
controller_event_at TEXT
received_at TEXT
source_identity TEXT NOT NULL
source_offset_start INTEGER NOT NULL
source_offset_end INTEGER NOT NULL
processing_result TEXT NOT NULL
visit_id TEXT
reason TEXT
processed_at TEXT NOT NULL
```

Results:

```text
closed
ignored
unmatched
invalid
duplicate
```

Raw webhook body/text не копировать.

---

## 33. Offline eligibility

Для close:

```text
event_name == omada.client_offline
valid canonical MAC
usable event time
usable Site context
```

Если normalized event не содержит надёжный `site_id` — это prerequisite issue.

Нельзя закрывать cross-site visit только по MAC.

---

## 34. Close time

Preferred:

```text
closed_at = controller_event_at
close_time_source = controller
```

Fallback при invalid/missing controller time:

```text
closed_at = received_at
close_time_source = received
```

Fallback должен быть явно сохранён.

---

## 35. Stale offline protection

Offline может закрыть visit только если:

```text
offline_at >= visit.started_at - max_clock_skew
```

Если event содержит:

```text
reported_connected_seconds
```

вычислить:

```text
reported_session_started_at =
offline_at - reported_connected_seconds
```

Если mismatch с visit start превышает configured drift:

```text
не закрывать автоматически
```

Event → `unmatched/stale_or_ambiguous`.

Старый offline не должен закрыть новый visit.

---

## 36. SSID/AP safeguards

Если оба SSID non-null и отличаются:

```text
не закрывать автоматически
reason = ssid_changed
```

AP mismatch сам по себе не reject:

```text
AP может измениться из-за roaming
```

Сохранить final AP.

---

## 37. Atomic finalization

Один offline event:

1. check event idempotency;
2. find open visit Site+MAC;
3. stale/context checks;
4. save event evidence;
5. close visit;
6. save final context/reported facts;
7. commit;
8. durable reader checkpoint advances only according to safe reader contract.

Crash/replay не должен закрывать visit повторно.

---

## 38. Duration

Authoritative lifecycle duration:

```text
duration_seconds =
floor(closed_at - started_at)
```

не меньше 0.

Omada:

```text
reported_connected_seconds
```

хранится отдельно как source fact.

Не подменять одно другим.

---

## 39. Traffic

Offline reported traffic сохранять как source facts, если normalized numeric fields доступны.

Не вычислять per-visit traffic из AP aggregate radio counters.

Не делать сложную traffic reconciliation в v1.

---

## 40. Unmatched offline events

Если подходящего open visit нет:

```text
НЕ создавать reconstructed visit
```

Сохранить event:

```text
processing_result = unmatched
```

Reasons минимум:

```text
no_open_visit
stale_or_ambiguous
site_missing
ssid_changed
invalid_time
```

---

## 41. Offline-only reconstructed visits

Исторически рассматривались.

Решение v1:

```text
НЕ РЕАЛИЗОВЫВАТЬ
```

Причины:

- нет confirmed CaptivPortal start;
- риск смешать старую Omada session и текущий visit;
- device/snapshot link может быть неоднозначен.

Unmatched evidence сохраняется для future task.

---

## 42. Restart behavior

Open visits остаются open после restart.

Не создавать synthetic close на startup.

После restart:

- reader продолжает offsets;
- replay event idempotent;
- reconciliation продолжает links.

---

## 43. Missing offline

v1 не закрывает visit по guessed timeout.

Давно открытые visits должны быть видимы через read service.

Stale-open reconciliation — отдельный future TASK после production evidence.

---

## 44. Read service

Создать:

```text
VisitLifecycleReadService
```

Без HTTP routes.

Минимум:

```text
get_visit(site_id, visit_id)

get_open_visit(site_id, client_mac)

list_visits(
  site_id,
  from_utc,
  to_utc,
  status=None,
  client_mac=None,
  device_id=None,
  ssid=None,
  ap_mac=None,
  limit=500,
  cursor=None,
)

list_device_visits(...)

list_open_visits(...)

list_unmatched_events(...)
```

---

## 45. Query rules

- Site required;
- no cross-site query;
- stable ordering;
- opaque cursor;
- default 500;
- hard max 2000;
- canonical MAC;
- strict UTC;
- immutable DTO;
- no analytics.

---

## 46. Observation window helper

Допустим DTO:

```text
VisitObservationWindow(
 site_id,
 client_mac,
 from_utc,
 to_utc,
)
```

Он только описывает query boundary.

---

## 47. Indexes

Минимум:

```text
visits(site_id, started_at, visit_id)
visits(site_id, closed_at, visit_id)
visits(site_id, client_mac, started_at, visit_id)
visits(site_id, device_id, started_at, visit_id)
visits(site_id, status, started_at, visit_id)
visits(site_id, ssid, started_at, visit_id)
visits(site_id, start_ap_mac, started_at, visit_id)

visit_authorizations(visit_id, authorized_at, row_id)

visit_source_events(site_id, controller_event_at, event_id)
visit_source_events(processing_result, processed_at)
```

Plus open partial UNIQUE.

---

## 48. SQLite contract

- POSIX mode `0640`;
- `foreign_keys=ON`;
- bounded busy timeout;
- WAL preferred;
- `synchronous=NORMAL` допустим;
- startup `quick_check`;
- schema validation;
- newer schema → unavailable;
- corruption preserved for diagnosis;
- no auto-delete/drop/recreate;
- no network/file waits inside transaction.

---

## 49. Fail-open

Invariant:

```text
Visit Lifecycle failure
must not become CaptivPortal failure.
```

Visit failure не должна:

- изменить AUTHORIZED;
- забрать Internet;
- запустить auth retry;
- изменить AuthSession;
- изменить CAPPORT;
- изменить Snapshot;
- изменить Registry;
- изменить Observation;
- изменить Cleaner;
- попасть visitor browser.

---

## 50. Telemetry

Summary events:

```text
visit.runtime_started
visit.runtime_stopped
visit.runtime_unavailable

visit.opened
visit.start_reused
visit.authorization_attached
visit.link_reconciled

visit.closed
visit.offline_unmatched
visit.offline_duplicate
visit.offline_invalid

visit.reader_scan_completed
visit.reader_scan_failed
visit.storage_error
```

Не писать raw snapshot/webhook/observations.

---

## 51. Security

Никогда не хранить/логировать:

- Access Token;
- Client Secret;
- Authorization header;
- cookie;
- Wi-Fi password;
- raw webhook;
- raw snapshot.

MAC в technical storage — полный.

---

## 52. Runtime / composition

Visit runtime создаётся через `run.py`.

Dependencies injection:

```text
settings
VisitorRegistryReadService
ObservationReadService
telemetry
```

VisitStartSubmitter передаётся в AuthWorker.

No thread at import.

---

## 53. Shutdown

Visit Lifecycle:

1. stopping;
2. no new background scans;
3. start submitter safe-unavailable;
4. interrupt reader/reconciliation;
5. finish short transaction;
6. bounded 20 sec stop.

---

## 54. Single-process

v1 поддерживает текущий:

```text
one application process
```

Multi-worker/HA — только после отдельного ADR.

---

## 55. Future Multi-Site Compatibility

Модель:

```text
Site-aware, single-tenant
```

Обязательно:

- every visit has Site;
- open uniqueness includes Site;
- every query requires Site;
- offline close requires Site;
- no hardcode Site/SSID;
- no tenant_id yet;
- Tenant != Site;
- MAC is not future global tenant identity;
- no new Omada provider/token lifecycle.

---

## 56. Product / Observability Boundary

Authoritative visit data:

```text
VisitLifecycleReadService
→ visits.sqlite3
```

Related authorities:

```text
VisitorRegistryReadService
ObservationReadService
```

Запрещён future product flow:

```text
Admin Console → Grafana/Loki → rebuild visits
```

Grafana остаётся internal observability.

---

## 57. Acquisition / Analytics Boundary

Lifecycle хранит deterministic facts:

```text
started_at
closed_at
duration
source context
reported traffic
IDs
```

Не вычисляет:

```text
returning visitor
frequent visitor
valuable visitor
long visit
bad wifi visit
needs second AP
```

---

## 58. Не входит в TASK

Не реализовывать:

- Analytics Foundation;
- Admin API;
- Web Foundation;
- Admin Console;
- Grafana/Alloy/Loki changes;
- Tenant/RBAC/entitlements;
- branding;
- guessed timeout close;
- offline-only reconstruction;
- observation copy;
- `visit_id` in Observation DB;
- production activation.

---

## 59. Allowed new files

```text
app/visit_lifecycle/**
tests/visit_lifecycle/**
```

---

## 60. Existing files allowed minimally

```text
app/config.py
app/settings.py
app/auth/worker.py
app/web/web.py   # wiring only if truly required
run.py
.env.example
```

Допустимо narrowly изменить:

```text
app/visitor_registry/registry_read_service.py
```

только для missing exact snapshot-by-auth-session read method.

Observation files — только narrow read/export helper при доказанной необходимости; schema/writers/cadence запрещено менять.

Webhook normalizer менять только отдельным prerequisite PR, если current normalized contract реально не даёт обязательный Site/event identity.

---

## 61. Forbidden areas

Не менять business behavior:

```text
app/capport/**
app/pending_sessions/**
app/visitor_registry/snapshot_*
app/visitor_registry/registry_repository.py schema
app/visitor_registry/registry_worker.py
app/observations/client_worker.py
app/observations/ap_worker.py
app/observations/repository.py schema
app/controllers/omada*.py
```

Также:

```text
requirements*.txt
.github/workflows/**
Grafana JSON
Alloy/Loki
systemd
Nginx
production env
```

---

## 62. Knowledge Base boundary

Coder не обновляет KB.

После runtime acceptance отдельный TASK получает Knowledge Base Lead.

---

## 63. No new dependency

Использовать stdlib + existing dependencies.

Persistence:

```text
sqlite3
```

---

## 64. Обязательное разбиение реализации

### PR A — Visit Storage + Start / Active Visits

Scope:

```text
config
models
visits.sqlite3
repository
read service
VisitStartSubmitter
minimal AUTHORIZED wiring
single-open invariant
visit_authorizations
device/snapshot reconciliation
```

PR A не читает offline journal и не закрывает visits.

### PR B — Finalization + Runtime Integration

Scope:

```text
normalized webhook reader
reader state
offline validation
stale protection
atomic close
unmatched evidence
runtime lifecycle
telemetry
```

Production activation — отдельный TASK.

PR B нельзя начинать до merge/acceptance PR A и отдельной owner-команды.

---

## 65. Tests — storage/start

Минимум:

- schema/user_version/indexes;
- FK/cascade;
- open partial UNIQUE;
- UUID;
- UTC format/order;
- new open visit;
- repeat start reuse;
- duplicate AuthRun idempotency;
- concurrent open conflict safe;
- different Site same MAC;
- Registry device link;
- Registry unavailable still opens;
- exact snapshot link;
- snapshot missing then reconciliation;
- existing link not replaced;
- Visit sink error leaves AUTHORIZED;
- Snapshot semantics unchanged;
- busy/full/corruption/newer-schema;
- quick_check/no auto-recreate.

---

## 66. Tests — reader/finalization

Минимум:

- missing/regular/rotated/truncated journal;
- bounded line;
- malformed JSON;
- unrelated normalized event;
- valid offline;
- event idempotency;
- checkpoint/replay after crash;
- exact Site+MAC close;
- duration;
- reported facts;
- stale event rejected;
- drift ambiguity rejected;
- duplicate offline;
- no open → unmatched/no reconstruction;
- same MAC other Site untouched;
- SSID mismatch reject;
- AP mismatch allowed;
- old event not close later new visit;
- controller time preferred;
- received time fallback;
- storage failure replay-safe;
- shutdown.

---

## 67. Query tests

- get visit;
- open lookup;
- range;
- status;
- MAC/device/SSID/AP;
- device visits;
- open visits;
- unmatched events;
- stable cursor;
- malformed cursor;
- hard limit;
- no cross-site leakage;
- immutable DTO;
- observation window.

---

## 68. Regressions

После PR A:

```text
Visitor Snapshot
Visitor Registry
Observation Foundation
Auth successful paths
CAPPORT
```

После PR B дополнительно:

```text
Omada webhook normalizer/receiver/journal
Pending Cleaner
```

Coder обязан использовать реальные current test paths и привести exact commands.

---

## 69. Full gate

Выполнить:

1. до изменений;
2. после PR A;
3. после PR B.

```bash
python -m pytest -q -rs
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc \
  python -m compileall -q app
git diff --check
```

Зафиксировать exact SHA и passed/skipped/failed.

---

## 70. Acceptance PR A

PASS если:

- independent Visit DB;
- single-open DB invariant;
- successful AUTHORIZED creates/reuses visit fail-open;
- Snapshot unchanged;
- nullable device/snapshot links + reconciliation;
- Visitor Registry schema unchanged;
- Observation schema unchanged;
- Site-aware read service;
- no finalization yet;
- tests/regressions/full gate reviewable;
- production unchanged.

---

## 71. Acceptance PR B

PASS если:

- automatic close only from normalized `omada.client_offline`;
- reader durable/rotation-safe;
- replay/idempotency safe;
- old offline cannot close new visit;
- unmatched event never invents visit;
- duration and Omada reported duration separated;
- Observation linkage remains query-window based;
- fail-open;
- Site isolation;
- no Analytics/Grafana dependency;
- tests/full gate reviewable;
- production unchanged.

---

## 72. Stop conditions

Остановить затронутую часть если:

- current main contracts materially differ;
- normalized offline lacks reliable Site/time/event identity;
- exact snapshot lookup requires Registry schema rewrite;
- Snapshot semantics must change;
- Observation schema/cadence must change;
- Omada polling becomes required for normal finalization;
- guessed timeout close becomes necessary;
- external dependency required;
- Visit module would need raw webhook parser;
- cross-DB SQLite FK required;
- pre-change full baseline missing;
- production/live credentials required;
- Grafana/Alloy/systemd change required.

---

## 73. Repository actions

После approval:

```text
feature/visit-lifecycle-start-v1
feature/visit-lifecycle-finalization-v1
```

Разрешено:

- fetch;
- branch;
- allowed changes;
- tests;
- local commit after green targeted tests.

Без отдельного owner permission:

- no push;
- no PR;
- no merge;
- no force/rewrite;
- no deploy;
- no production env changes.

---

## 74. Handoff

Каждый PR возвращает:

```text
BASELINE
IMPLEMENTED
NOT IMPLEMENTED
FILES CHANGED
CONTRACTS
VISIT STORAGE
START CONTRACT
FINALIZATION CONTRACT
QUERY CONTRACTS
TEST COMMANDS
TEST RESULTS
SECURITY VERDICT
RISKS / UNVERIFIED
REPOSITORY ACTIONS
NEXT OWNER ACTION
```

Подтвердить явно:

```text
Auth semantics changed: NO
Snapshot semantics changed: NO
Visitor Registry schema changed: NO
Observation schema changed: NO
Omada provider/token lifecycle changed: NO
```

---

## 75. Production activation

НЕ входит.

Отдельный activation TASK после merge PR A+B должен проверить:

```text
AUTHORIZED → open visit
device/snapshot reconciliation
Observation window
real omada.client_offline → closed visit
duration/reported fields
restart/replay
no duplicate close
portal unaffected
```

---

## 76. Future work intentionally excluded

После real production visit history отдельно решать:

- stale-open reconciliation;
- offline-only historical reconstruction;
- roaming-aware segmentation;
- richer traffic reconciliation;
- Analytics Foundation;
- Web/Admin API.

---

## 77. Итоговый invariant

```text
Visitor Registry
= WHO

Snapshot
= START PHOTO

Observation Foundation
= WHAT HAPPENED OVER TIME

Visit Lifecycle
= WHEN THIS VISIT STARTED AND ENDED

Analytics
= WHAT IT MEANS
```

Visit Lifecycle связывает существующие authoritative layers, а не дублирует их.

---

## 78. Review gate

Документ — DRAFT FOR REVIEW.

До явной команды:

```text
TASK Visit Lifecycle v1 утверждено, начинать PR A
```

Coder не должен:

- создавать implementation branch;
- менять code/tests;
- commit/push;
- открывать PR;
- deploy.

После общего approval сначала разрешён только PR A.
