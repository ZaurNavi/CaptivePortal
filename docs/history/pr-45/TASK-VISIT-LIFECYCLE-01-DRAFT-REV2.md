# TASK-VISIT-LIFECYCLE-01 — Visit Lifecycle v1

**Проект:** CaptivPortal  
**Тип:** master implementation TASK / архитектурное ТЗ  
**Статус:** DRAFT REVISION 2 — FOR FINAL REVIEW  
**Implementation authorization:** НЕ ДАНО  
**Основание REV2:** обязательные замечания Tech Lead review; implementation по REV1 не разрешён  
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
VISIT_LIFECYCLE_READER_MAX_LINES_PER_SCAN=5000
VISIT_LIFECYCLE_READER_MAX_BYTES_PER_SCAN=16777216
VISIT_LIFECYCLE_READER_MAX_DURATION_SECONDS=20
VISIT_LIFECYCLE_RECONCILE_BATCH_SIZE=500
VISIT_LIFECYCLE_PENDING_OFFLINE_BATCH_SIZE=500
VISIT_LIFECYCLE_OFFLINE_MATCH_GRACE_SECONDS=30
VISIT_LIFECYCLE_START_BUSY_TIMEOUT_MS=250
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

start_auth_session_id TEXT
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

### `submit_authorized()` execution model

v1 использует **синхронную короткую локальную SQLite transaction** в auth thread.

Запрещено внутри submit:

- Registry lookup;
- Observation query;
- Omada request;
- filesystem scan;
- queue wait;
- sleep/retry loop.

Busy timeout:

```text
VISIT_LIFECYCLE_START_BUSY_TIMEOUT_MS=250
```

При `busy/full/unavailable` submitter:

- не бросает exception наружу в AuthWorker;
- возвращает безопасный `VisitStartOutcome(status="unavailable", ...)`;
- emit operational telemetry;
- AUTHORIZED остаётся AUTHORIZED.

Bounded queue в v1 не добавлять.

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

1. validate request;
2. canonicalize MAC;
3. проверить `visit_authorizations(auth_session_id, auth_run_number)`;
4. если evidence уже существует — вернуть связанный visit без create;
5. если evidence отсутствует — найти open `(site_id + MAC)`;
6. если open visit отсутствует — создать новый;
7. если open visit существует — reuse;
8. attach authorization evidence;
9. commit короткой локальной Visit DB transaction;
10. telemetry.

### Запрет cross-DB I/O в start transaction

`submit_authorized()` **не обращается к Visitor Registry и Observation DB**.

В AUTHORIZED path разрешена только короткая локальная transaction `visits.sqlite3`.

Device/snapshot links всегда добавляет reconciliation после commit.

Следовательно:

```text
Visit DB transaction
!=
Registry lookup
```

и Registry latency/busy никогда не блокирует transaction Visit DB.

---

## 21. Repeat AUTHORIZED

При open visit:

```text
visit_id = same
started_at = unchanged
start_auth_session_id = unchanged
start_auth_run_number = unchanged
initial_snapshot_id = link only to start_auth_session_id
```

`visits.start_auth_session_id` — immutable AuthSession первой авторизации, которая открыла visit.

Повторная авторизация:

- сохраняется только в `visit_authorizations`;
- не заменяет start fields;
- её snapshot не становится `initial_snapshot_id`;
- её SSID/AP/IP context остаётся evidence и может использоваться для безопасного finalization matching/query filters.

---

## 22. `visit_authorizations`

Authorization evidence сохраняет не только факт AuthRun, но и его безопасный контекст:

```text
row_id INTEGER PRIMARY KEY
visit_id TEXT NOT NULL
auth_session_id TEXT NOT NULL
auth_run_number INTEGER NOT NULL
authorization_attempt INTEGER
authorized_at TEXT NOT NULL
final_reason TEXT NOT NULL
client_ip TEXT
portal_ssid TEXT
portal_ap_mac TEXT
portal_radio_id INTEGER
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

`retry_request_id` в v1 не хранить: он не требуется для lifecycle identity. Если позднее окажется нужен для product/debug query, добавлять отдельным schema review.

### Обязательный порядок idempotency

До поиска/создания open visit:

```text
lookup visit_authorizations(auth_session_id, auth_run_number)
```

Если evidence уже существует:

- вернуть связанный `visit_id`;
- новый visit не создавать;
- open/closed status существующего visit не изменять только из-за повторной доставки;
- разрешено запустить безопасный link reconciliation.

Только если evidence отсутствует:

```text
lookup open Site+MAC
→ create/reuse
→ attach evidence
```

Это предотвращает повторную доставку старого AUTHORIZED от создания нового open visit после закрытия исходного.

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

### Site-awareness Registry identity

Текущий Visitor Registry идентифицирует persistent device по MAC и его `get_device_by_mac()` не является Site-scoped.

Для v1 это **осознанное single-tenant ограничение**:

```text
same MAC in Site A and Site B
→ visits разные из-за site_id
→ device_id может быть один и тот же
```

Visit isolation и finalization всегда Site-scoped.  
Изменение device identity model откладывается до Multi-Site/Tenant ADR; Visit Lifecycle не переписывает Registry identity.

---

## 24. Initial snapshot linkage

Preferred exact match:

```text
device_snapshots.auth_session_id == visit.start_auth_session_id
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

PR A реализует **и запускает при enabled Visit Lifecycle минимальный reconciliation worker**. Это часть PR A runtime, а не PR B finalization runtime.

Worker заполняет missing:

```text
device_id
initial_snapshot_id
```

Default:

```text
30 sec fixed delay
VISIT_LIFECYCLE_RECONCILE_BATCH_SIZE=500
```

Только через `VisitorRegistryReadService`.

Правила:

- Registry lookup выполняется вне Visit DB write transaction;
- no Omada call;
- no raw Registry SQL;
- no Registry mutation;
- bounded batch/time;
- idempotent;
- non-null link автоматически не заменять другим;
- Registry unavailable → current pass degraded/skip, visit остаётся valid;
- PR A tests обязаны доказать `snapshot missing → later reconciliation`.

PR B добавляет offline reader/finalization к уже существующему PR A runtime, а не впервые создаёт весь Visit runtime.

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

`VISIT_LIFECYCLE_WEBHOOK_SOURCE` означает **active normalized journal path**, а не raw glob.

Reader сам строит только разрешённые rotation candidates по уже принятому hardened project pattern/current logrotate naming.

Запрещено:

```text
glob("normalized.log*") без проверки имени
```

До implementation Coder обязан сверить фактическую naming scheme существующего normalized journal rotation и соответствующие project tests.

Reader requirements:

- active file + strict allowed rotated names;
- temporary/manual/unrelated files исключаются;
- regular file validation;
- inode/source identity;
- hardened persisted checkpoint;
- rotation/truncate/inode-reuse/fast-regrow protection;
- bounded line bytes;
- `VISIT_LIFECYCLE_READER_MAX_LINES_PER_SCAN=5000`;
- `VISIT_LIFECYCLE_READER_MAX_BYTES_PER_SCAN=16777216`;
- `VISIT_LIFECYCLE_READER_MAX_DURATION_SECONDS=20`;
- strict JSON;
- shutdown checks;
- fixed-delay scan;
- no unbounded read.

Backfill старых normalized journal files до deployment cutover **не включать автоматически**. Production activation TASK отдельно определяет стартовую checkpoint policy, чтобы pre-Visit historical offline events не создавали noise.

---

## 30. `visit_reader_state` — hardened checkpoint contract

Visit reader имеет собственный state и обязан сразу учитывать уже известные project file-race cases.

Минимум:

```text
source_identity TEXT PRIMARY KEY
source_path TEXT NOT NULL
source_offset INTEGER NOT NULL
last_observed_size INTEGER

checkpoint_offset INTEGER
checkpoint_length INTEGER
checkpoint_sha256 TEXT

retired_completed INTEGER NOT NULL
missing_warning_emitted INTEGER NOT NULL
updated_at TEXT NOT NULL
```

Требования:

- checkpoint fingerprint подтверждает, что сохранённый offset относится к тому же content;
- защита от мгновенного inode reuse;
- защита от truncate + fast regrow выше старого offset;
- incomplete rotated file, исчезнувший до EOF, не считается silently completed;
- missing warning bounded/emit once;
- restart validation checkpoint выполняется до доверия старому offset;
- Visitor Registry/Public Traffic offsets не использовать и не менять.

Если текущий repository уже имеет reusable hardened reader primitive, reuse предпочтителен. Копировать reader logic fork-ом без необходимости запрещено.

---

## 31. Event identity

Current normalizer уже формирует:

```text
normalized_event_id = webhook_id + ":" + text_index
```

Для v1 это **обязательный primary event identity**:

```text
visit_source_events.event_id = normalized_event_id
```

Правила:

- valid recognized offline без `normalized_event_id` автоматический visit не закрывает;
- такой record считается invalid normalized input;
- timestamp alone запрещён как ID;
- inode/offset не используется как business event ID;
- source identity/offset всё равно сохраняются как reader provenance.

Это делает replay idempotency независимой от filename/inode.

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

Persisted `processing_result`:

```text
pending_match
closed
unmatched
invalid
```

Semantics:

- unrelated valid normalized events **не сохранять** в `visit_source_events`; checkpoint продвигается;
- recognized valid offline outcome сохраняется;
- duplicate `normalized_event_id` второй row не вставляет; emit `visit.offline_duplicate`, checkpoint продвигается;
- malformed JSON без usable event identity не создаёт source-event row; emit reader telemetry, checkpoint продвигается после safe handling;
- offline-like normalized JSON с event ID, но invalid required fields → `invalid`;
- `pending_match` используется только для bounded race protection `offline-before-start`.

Raw webhook body/text не копировать.

---

## 33. Offline eligibility и обязательный Site prerequisite

Для close:

```text
event_name == omada.client_offline
valid normalized_event_id
valid canonical MAC
usable event time
resolved technical site_id
```

### Подтверждённый current gap

Текущий normalized webhook содержит human-readable Site name:

```text
site = "Home"
```

но не технический:

```text
site_id
```

Следовательно **PR B заблокирован**, пока этот gap не закрыт.

### Обязательный prerequisite PR 0

До PR B отдельным focused prerequisite изменить Webhook Normalizer contract:

```text
normalized event
→ сохраняет existing site/site_name
→ дополнительно содержит resolved site_id
```

Mapping должен быть explicit, deterministic и Future Multi-Site safe.

Рекомендуемый config contract:

```text
OMADA_WEBHOOK_SITE_ID_MAP_JSON={}
```

Production example conceptually:

```json
{"Home":"<SITE_ID>"}
```

Требования:

- strict JSON object `site name → site_id`;
- exact case-sensitive site-name key;
- trim values;
- duplicate JSON keys запрещать/валидировать согласно chosen parser contract;
- пустой/unknown Site → `site_id=null` + normalization warning;
- никакого Omada API call ради mapping;
- никаких hardcoded production Site IDs;
- existing `site` field не ломать для backward compatibility.

Visit Finalization:

```text
site_id is null
→ automatic close forbidden
→ offline outcome invalid/unmatched site_unresolved
```

Нельзя закрывать cross-site visit только по MAC.

PR A не блокируется этим prerequisite, потому что Visit Start уже получает technical `site_id` из AuthSession.

---

## 34. Close time

Preferred:

```text
candidate_close_at = controller_event_at
close_time_source = controller
```

Но DB никогда не сохраняет обратный visit interval.

Если valid controller time:

```text
controller_event_at >= started_at
→ использовать controller_event_at
```

Если controller time меньше `started_at`, но находится внутри разрешённого clock-skew window:

```text
если received_at валиден и received_at >= started_at
→ использовать received_at
→ close_time_source = received_clock_fallback
```

Если ни один timestamp не даёт:

```text
closed_at >= started_at
```

event → `unmatched/stale_or_ambiguous`.

Запрещено:

- сохранять `closed_at < started_at`;
- clamp искусственно к `started_at`;
- скрывать fallback source.

`duration_seconds` поэтому никогда не маскирует обратный диапазон.

---

## 35. Stale offline protection

Offline может закрыть visit только если:

```text
offline_at >= visit.started_at - max_clock_skew
```

Если event содержит valid:

```text
reported_connected_seconds
```

и valid `controller_event_at`, вычислить:

```text
reported_session_started_at =
    controller_event_at - reported_connected_seconds

drift_seconds =
    abs(reported_session_started_at - visit.started_at)
```

Pass condition inclusive:

```text
drift_seconds <=
VISIT_LIFECYCLE_MAX_REPORTED_DURATION_DRIFT_SECONDS
```

Если:

```text
drift_seconds > threshold
```

→ `unmatched/stale_or_ambiguous`.

Rules:

- отсутствие `reported_connected_seconds` **не запрещает** close;
- normalized invalid/missing duration хранится как NULL и не участвует в drift check;
- при `close_time_source` based on `received_at` reported-duration drift **не используется как reject**, потому что delivery lag неизвестен;
- старый offline не должен закрыть новый visit.

---

## 36. SSID/AP safeguards

Visit знает SSID context из:

```text
visits.start_ssid
+
visit_authorizations.portal_ssid
```

Построить set всех non-null authorization SSIDs этого visit.

Если offline SSID non-null:

```text
есть хотя бы один known authorization SSID
AND offline SSID не входит в этот set
→ не закрывать автоматически
→ reason = ssid_changed
```

Если known authorization SSID отсутствуют, SSID не становится обязательным blocker.

Не использовать Observation как обязательный close dependency.

AP mismatch сам по себе не reject:

```text
AP может измениться из-за roaming
```

Сохранить `final_ap_mac`.

Authorization evidence поэтому хранит portal SSID/AP context, а не только first start context.

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

Current normalized offline contract предоставляет aggregate estimate:

```text
reported_traffic_bytes_estimate
```

v1 mapping:

```text
reported_traffic_total_bytes =
    reported_traffic_bytes_estimate

reported_traffic_up_bytes = NULL
reported_traffic_down_bytes = NULL
```

Нельзя делить total на upload/download эвристически.

Если future normalizer когда-либо добавит independently confirmed up/down fields, их использование требует отдельного schema/contract review.

Не вычислять per-visit traffic из AP aggregate radio counters и не делать сложную traffic reconciliation в v1.

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

### Time range semantics

`list_visits(site_id, from_utc, to_utc, ...)` возвращает visits, чей lifecycle interval пересекает half-open query range:

```text
[from_utc, to_utc)
```

SQL semantics conceptually:

```text
visit.started_at < to_utc
AND
(visit.closed_at IS NULL OR visit.closed_at >= from_utc)
```

### Context filters

`ssid` match, если совпадает хотя бы:

```text
start_ssid
final_ssid
visit_authorizations.portal_ssid
```

`ap_mac` match, если совпадает хотя бы:

```text
start_ap_mac
final_ap_mac
visit_authorizations.portal_ap_mac
```

Implementation может использовать `EXISTS` вместо join duplication.

### Ordering/cursor

Stable order:

```text
started_at DESC, visit_id DESC
```

Cursor tuple:

```text
(started_at, visit_id)
```

остается opaque для caller.

Общие rules:

- Site required;
- no cross-site query;
- `from_utc < to_utc`;
- default 500;
- hard max 2000;
- canonical MAC/AP MAC;
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
visit_source_events(source_identity, source_offset_start, source_offset_end)
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

Dependencies injection разделяется:

```text
Visit core/start:
    settings
    VisitRepository
    telemetry

Reconciliation:
    VisitRepository
    VisitorRegistryReadService
    telemetry

Finalization PR B:
    VisitRepository
    normalized webhook reader
    telemetry
```

`ObservationReadService` **не является обязательной runtime dependency** Visit Lifecycle.

`VisitObservationWindow` — pure DTO/query contract. Future Analytics сама соединяет его с ObservationReadService.

VisitStartSubmitter передаётся в AuthWorker через explicit dependency injection.

Approved composition direction:

```text
create VisitRepository + VisitStartSubmitter before create_app()
        ↓
create_app(
    ...,
    visitor_snapshot_collector=existing_snapshot_collector,
    visit_start_submitter=visit_start_submitter,
)
        ↓
create Visitor Registry read service
        ↓
create/start Visit reconciliation worker
        ↓
PR B additionally starts finalization reader
```

Disabled mode использует immutable no-op:

```text
DISABLED_VISIT_START_SUBMITTER
```

Запрещён global mutable proxy/singleton, которому dependency устанавливается позже.

No thread at import.

No thread at import.

---

## 53. Shutdown

Критический relative ordering:

```text
stop durable Visit reader/reconciliation scheduling
→ Auth executor drain while VisitStartSubmitter still accepts
→ after Auth executor drained: VisitStartSubmitter.stop_accepting()
→ finish short Visit DB transaction
→ close Visit runtime
```

Причина:

- поздний успешный AuthRun во время drain должен всё ещё иметь возможность записать visit;
- offline journal durable, поэтому reader может остановиться раньше и replay после restart;
- VisitStartSubmitter нельзя закрывать до Auth executor drain.

Общий bounded timeout:

```text
VISIT_LIFECYCLE_SHUTDOWN_TIMEOUT_SECONDS=20
```

Если current composition root имеет другой safe ordering, Tech Lead может скорректировать его, но invariant `Auth executor drain before start sink close` обязателен.

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

### Prerequisite PR 0 — Webhook Site Identity Enrichment

Нужен **до PR B**, не блокирует PR A.

Scope только:

```text
explicit Site name → site_id config mapping
normalized event site_id
validation/tests/backward compatibility
```

Не содержит Visit DB/runtime.

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
device/snapshot reconciliation worker
minimal start/reconciliation runtime wiring
```

PR A не читает offline journal и не закрывает visits.

Таким образом PR A имеет минимальный runtime для:

```text
AUTHORIZED start
+
Registry reconciliation
```

а PR B добавляет finalization reader/runtime.

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
- duplicate AuthRun idempotency checked before create;
- replayed AuthRun already linked to CLOSED visit does not create new open visit;
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
- required normalized_event_id;
- resolved technical site_id;
- unknown/unresolved Site never closes visit;
- event idempotency;
- checkpoint fingerprint;
- inode reuse;
- truncate + fast regrow;
- incomplete rotated file disappearance;
- strict rotated filename filtering;
- checkpoint/replay after crash;
- exact Site+MAC close;
- duration;
- reported facts;
- stale event rejected;
- drift ambiguity rejected;
- duplicate offline;
- no open → persistent pending_match grace;
- visit appears during grace → pending event may close it after all safeguards;
- grace expires → unmatched/no reconstruction;
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

- prerequisite normalized `site_id` contract merged/accepted;
- automatic close only from normalized `omada.client_offline`;
- reader durable/rotation-safe/hardened checkpoint;
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
- normalized offline lacks reliable technical `site_id`, time or `normalized_event_id`;
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

---

## 77A. REV2 correction checklist — Tech Lead review

Все обязательные вопросы REV1 закрыты следующим образом:

1. **Normalized webhook `site_id`:** подтверждён gap; отдельный prerequisite PR 0 с explicit `site name → site_id` mapping; PR B без него запрещён.
2. **AUTHORIZED idempotency:** lookup `(auth_session_id, auth_run_number)` выполняется **до** open lookup/create.
3. **Cross-DB transaction:** Registry lookup полностью вынесен из synchronous Visit Start transaction; links делает reconciliation.
4. **Reconciliation PR A:** PR A имеет минимальный start/reconciliation runtime; PR B добавляет finalization.
5. **Wiring:** explicit DI, VisitStartSubmitter создаётся до `create_app()`, no mutable singleton/proxy.
6. **submit_authorized:** synchronous local SQLite only, busy timeout 250 ms, no Registry/Omada/queue/sleep.
7. **authorization_attempt/context:** сохраняются в `visit_authorizations`; retry_request_id намеренно не входит v1.
8. **Start AuthSession:** renamed `start_auth_session_id`, immutable; initial snapshot только от first start session.
9. **Registry Site-awareness:** global-by-MAC device identity принят как single-tenant v1 limitation; visits остаются Site-scoped.
10. **SSID safeguard:** сравнение с set всех authorization-evidence SSID, не только start SSID; Observation не обязательна.
11. **Offline earlier than start:** обратный interval не сохраняется; received timestamp fallback либо ambiguous.
12. **Reported duration:** формула drift зафиксирована; threshold inclusive; missing duration не blocks; received fallback не использует drift как reject.
13. **Traffic:** current `reported_traffic_bytes_estimate → total`; up/down остаются NULL.
14. **Event ID:** обязательный `normalized_event_id`; no inode/offset business-ID fallback.
15. **Source-event semantics:** durable rows только offline outcomes; unrelated/duplicate/malformed handling и checkpoint semantics определены.
16. **Offline-before-start race:** persistent `pending_match` grace 30s + bounded recheck; это не reconstruction.
17. **Reader hardening:** checkpoint offset/length/SHA, inode reuse, truncate-regrow, missing rotated file protections.
18. **Source path vs `.log*`:** config = active path; reader использует strict allowed rotated naming, не broad glob.
19. **`visit_state`:** удалена как недоопределённая/ненужная table v1.
20. **Query semantics:** interval overlap `[from,to)`, context filters across start/final/auth evidence, order `(started_at DESC, visit_id DESC)`.

Дополнительные предложения Tech Lead также приняты:

- bounded reader lines/bytes/duration;
- reconciliation/pending batch limits;
- authorization evidence context fields;
- provenance index;
- ObservationReadService удалён из обязательных runtime dependencies;
- shutdown invariant: Auth executor drains before VisitStartSubmitter closes.

---

## 77B. Implementation authorization status

```text
Architecture direction: PASS
REV2: FOR FINAL REVIEW
PR A implementation authorization: NOT YET GIVEN
Prerequisite PR 0 implementation authorization: NOT YET GIVEN
PR B: BLOCKED until prerequisite site_id contract + PR A acceptance
Production activation: SEPARATE FUTURE TASK
```


## 78. Review gate

Документ — DRAFT FOR REVIEW.

До явной команды:

```text
TASK Visit Lifecycle v1 REV2 утверждено, начинать PR A
```

Coder не должен:

- создавать implementation branch;
- менять code/tests;
- commit/push;
- открывать PR;
- deploy.

После общего approval сначала разрешён только PR A.
