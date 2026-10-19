# TECH LEAD REVIEW — `TASK-HOME-LIVE-01-DRAFT`

**Project:** CaptivPortal  
**Reviewed document:** `TASK-HOME-LIVE-01 — Admin Console Home Live — DRAFT`  
**Reviewed baseline:** `origin/main@a864dfa78461ccbfe88e110b1aa5bad5f6bfa23e`  
**Review date:** 2026-08-23  
**Decision:** `ARCHITECTURE DIRECTION — PASS`  
**DRAFT status:** `RETURN FOR TARGETED REVISION`  
**Implementation authorization:** `NOT GRANTED`

---

## 1. Итоговая оценка

Архитектурное направление принято. DRAFT правильно строит `HOME-LIVE-01` как read-only product boundary над уже принятым `CurrentStateReadService`, сохраняет Site scope, не создаёт новый Omada polling, не смешивает product UI с Grafana/Loki и отделяет merge от production activation.

Переписывать документ заново не требуется. Однако в текущем виде его нельзя утверждать как FINAL: несколько контрактов расходятся с фактическим кодом `origin/main`, а часть frontend-состояний допускает смешивание разных snapshots или зависание refresh-контроллера.

Архитектору необходимо внести перечисленные ниже обязательные исправления, после чего выдать `TASK-HOME-LIVE-01-FINAL` для короткого повторного контроля.

---

## 2. Что подтверждено и принимается без изменения направления

Подтверждены по `origin/main@a864dfa78461ccbfe88e110b1aa5bad5f6bfa23e`:

- `CurrentStateRuntime.read_service` существует;
- сигнатуры четырёх read-операций в DRAFT указаны корректно;
- exact current values выбираются только из `result='success' AND complete=1`;
- Client scope вычисляется по `Site ID + exact SSID allowlist`;
- Client/AP watermarks и freshness независимы;
- Client cursor уже связан с endpoint, Site, cycle, scope, sort и filters;
- AP cursor связан с endpoint, Site, cycle и scope;
- `fresh/stale/unavailable` и production thresholds в DRAFT совпадают с принятым Current State;
- Current State является отдельным read-only источником и не должен быть реконструирован через Observation, Registry, Visits, Loki или Omada;
- отдельный `WEB_ADMIN_HOME_LIVE_ENABLED=false` необходим;
- четыре Site-scoped GET endpoint являются подходящей формой контракта;
- Client summary, AP summary, Online Devices и Access Points должны получать данные только через `AdminQueryService → CurrentStateReadService`;
- старый Home должен оставаться feature-disabled fallback;
- AP `status=1 → online` подтверждён; остальные значения нельзя продуктово называть Offline;
- client controller counters и uptime нельзя называть Mbps, Download, Upload или session duration без отдельного evidence;
- production activation и rollback должны оставаться отдельным Owner-controlled этапом.

---

## 3. Обязательные исправления перед FINAL

### 3.1. Закрыть deadline-вопрос: принять вариант A как узкое исключение

Открытый вопрос №12 в DRAFT закрыть следующим решением:

```text
ACCEPT OPTION A FOR HOME-LIVE-01.
```

Основание:

- Current State reads выполняют bounded indexed queries;
- page size ограничен;
- исторический scan в задачу не входит;
- production evidence: `p95=4.570 ms`, `max=5.741 ms`;
- добавление нового common deadline abstraction сейчас непропорционально задаче и необоснованно связывает уже принятый Current State с новым refactor.

При этом pre/post deadline checks должны быть обязательными, а не формулироваться как «Admin may classify»:

```python
deadline.require_remaining()
result = current_state_read_service.<method>(...)
deadline.require_remaining()
```

Это не объявляется реальной in-query SQLite cancellation. Ограничение фиксируется в Known Limitations и, при необходимости, отдельном debt item. Coder не должен менять `app/current_state/**` ради deadline в этой задаче.

### 3.2. Исправить mapping `CurrentStateValidationError`

Текущий DRAFT ошибочно задаёт общее правило:

```text
CurrentStateValidationError → HTTP 400
```

В фактическом коде этот класс используется не только для caller input, но и для persisted integrity failures, например:

```text
persisted auth count invariant failed
persisted AP count invariant failed
```

Такая ошибка не является ошибкой браузера и не должна возвращаться как 400.

FINAL должен разделить mapping по происхождению:

```text
Admin-owned validation до source call
(limit, sort, filter, Site, canonical MAC, cycle syntax, cursor length)
→ 400 invalid_request

CurrentStateValidationError из summary/integrity path
→ 503 source_unavailable

CurrentStateValidationError из page path,
однозначно вызванный caller cursor/filter/cycle context
→ 400 invalid_request

sqlite3.Error / safe OSError при Current State read
→ 503 source_unavailable

непредвиденная programming error
→ 500 internal_error
```

Source exception strings, SQLite path и raw SQL не возвращаются и не логируются в user-visible event.

Добавить отдельные тесты, доказывающие:

- malformed cursor → 400;
- invalid caller filter → 400;
- persisted Client invariant failure → 503;
- persisted AP invariant failure → 503;
- SQLite read/open failure → 503;
- unexpected programmer exception → sanitized 500.

### 3.3. Исправить default/max page-size contract

В существующем `AdminQueryService._limit()` верхняя граница вычисляется как:

```text
min(default, 500)
```

Если default равен 100, этот helper не разрешит запрос `limit=250`. Поэтому DRAFT-контракт:

```text
default = 100
hard max = 250
```

невозможно реализовать простым повторным использованием текущего helper.

FINAL должен потребовать отдельную validation path, где default и hard maximum передаются независимо. Обязательные тесты:

```text
limit omitted → 100
limit=1       → accepted
limit=100     → accepted
limit=101     → accepted
limit=250     → accepted
limit=251     → 400
limit=0       → 400
non-canonical integer text → 400
```

### 3.4. Формализовать explicit cycle/cursor-not-found semantics

Фактический `CurrentStateReadService` при переданном, но отсутствующем/уже удалённом `cycle_id` может вернуть:

```text
snapshot.freshness_status = unavailable
items = ()
```

а не выбросить validation exception.

Но DRAFT требует для invalid/expired explicit cycle или cursor:

```text
400 invalid_request
```

FINAL должен явно потребовать Admin-side distinction:

```text
без cycle_id/cursor + нет current complete snapshot
→ HTTP 200, freshness=unavailable

explicit cycle_id/cursor передан,
но source не вернул тот же selected cycle
→ HTTP 400 invalid_request
```

То же правило действует, если pinned cycle исчез из retention или пересёк unavailable threshold во время pagination. UI в таком случае не оставляет уже загруженные строки видимыми как current: он сбрасывает pagination и запускает новый logical refresh.

### 3.5. Добавить безопасный product mapping для будущего `offline_count > 0`

DRAFT исключает product label Offline, но underlying `CurrentApSummary` уже содержит `offline_count`. Если в будущем normalizer начнёт выдавать `offline`, простое удаление этого поля нарушит инвариант:

```text
total != online + other + unknown
```

Для `HOME-LIVE-01` принять безопасный product mapping:

```text
product.online = source.online_count
product.unknown = source.unknown_count
product.other = source.other_count + source.offline_count
```

Для AP item:

```text
source online  → product Online
source unknown → product Unknown
любая другая source classification, включая future offline
               → product Other
```

Обязательный invariant:

```text
AP Total = Online + Other + Unknown
```

Raw future `offline` нельзя показывать пользователю как Offline без нового evidence/review. Добавить тест с искусственным `offline_count > 0`.

### 3.6. Исправить AP pagination и Client/AP enrichment

Один AP page не доказывает отсутствие AP во всём snapshot. Пока `next_cursor != null`, AP, не найденная на загруженной странице, может находиться на следующей странице.

Поэтому текущая формулировка:

```text
Client bucket AP absent from AP snapshot
```

неверна, если UI получил только первую AP page.

FINAL должен ввести два независимых pagination-контекста:

```text
Online Devices cursor
Access Points cursor
```

и два отдельных Load More control. Один общий `#pagination`/cursor для Home использовать нельзя.

AP enrichment states:

```text
matched
not_yet_loaded       # AP page имеет next_cursor
absent_after_exhaustion
ap_source_unavailable
```

Только после `AP next_cursor = null` можно утверждать, что MAC отсутствует в выбранном AP snapshot. До этого UI показывает нейтральное `AP details not loaded`, а не `Unknown AP health`.

`Access Points Now` обязан показывать:

```text
Showing N of Total
```

если список не загружен полностью. AP с нулём scoped clients остаётся видимой среди загруженных AP. Normal auto-refresh по-прежнему ограничен четырьмя начальными GET; дополнительные AP pages загружаются только явно и не входят в normal refresh budget.

### 3.7. Не использовать существующий destructive Home error path

В текущем `admin.js` generic `showFailure()` выполняет:

```javascript
content.replaceChildren()
```

и очищает всю страницу. Это несовместимо с требованием независимого Client/AP failure.

FINAL должен потребовать отдельный Home Live controller и отдельные DOM/state containers минимум для:

```text
Client summary/cards
Client table
Devices by AP
AP summary/card
AP list
global session/authorization state
```

Live Home нельзя проводить через существующую destructive связку `run() → showFailure()` без её архитектурного разделения. Ошибка AP не очищает Client sections; ошибка Client page не очищает AP sections; 401 остаётся глобальным состоянием.

### 3.8. Ввести generation/transaction guard для frontend

Одного boolean `refresh_in_flight` недостаточно. Возможны гонки между:

```text
auto-refresh
manual Refresh
Load More clients
Load More APs
sort change
filter change
visibility change
```

FINAL должен потребовать:

- monotonic `refresh_generation`/request epoch;
- discard response, если generation уже не текущая;
- запрет append строк из старого cycle после нового refresh;
- блокировку или отмену Load More во время смены sort/filter/snapshot;
- проверку `site_id`, `cycle_id` и `source_scope_hash` перед append;
- отдельные Client/AP cursors;
- очистку старой page section, если новый summary принят, но pinned page не получена.

Нельзя показывать новые cards и старую table без явной старой watermark. Предпочтительное поведение: summary обновляется, старая table скрывается, table section показывает собственную ошибку.

### 3.9. Добавить bounded browser request timeout и cancellation

Без `AbortController` зависший network fetch оставит `refresh_in_flight=true` навсегда и остановит manual/automatic refresh.

Добавить repository-safe config:

```text
WEB_ADMIN_HOME_LIVE_REQUEST_TIMEOUT_SECONDS=20
```

Предлагаемые bounds:

```text
5..60
```

и invariant:

```text
HOME_LIVE_REQUEST_TIMEOUT_SECONDS
>
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS
```

Frontend обязан:

- отменять request по timeout;
- очищать timeout/controller в `finally`;
- отменять Home requests при `pagehide`;
- при переходе вкладки в hidden отменять незавершённый Home refresh как neutral cancellation, а не как source failure;
- игнорировать ответ отменённой/старой generation.

### 3.10. Сделать retry/backoff независимым по Client и AP

Текущий DRAFT одновременно требует independent Client/AP failure и описывает один общий consecutive-failure counter. Это противоречие.

Исправить на:

```text
client_failure_count / client_next_eligible_at
ap_failure_count     / ap_next_eligible_at
```

Если AP временно недоступен, Client summary/table продолжают обновляться каждые 60 секунд. AP использует свой `60 → 120 → 300` backoff. Аналогично в обратную сторону.

Manual Refresh запускает только eligible/not-in-flight source groups либо явно пытается обе группы по product decision; результат каждой группы сбрасывает/увеличивает только её собственный counter.

Глобальные non-retry states:

```text
401 session expired → stop all polling, show Sign in
403 Site forbidden  → stop affected Home polling
404 feature disabled during rollout/rollback
                    → stop live polling and request/recommend page reload
```

Retryable:

```text
network timeout
429
503
sanitized 500
```

`400 invalid_request` для UI-generated query/cursor считается client-state defect: cursor сбрасывается, выполняется один clean refresh; бесконечный retry запрещён.

### 3.11. Зафиксировать feature-flag delivery в template/JS

FINAL должен определить точный путь безопасных значений:

```text
AdminWebConfig
→ render_admin_page
→ admin/home.html or safe data-* attributes
→ Home JS controller
```

Минимум передаются:

```text
home_live_enabled
home_live_refresh_seconds
home_live_request_timeout_seconds
current_state_page_size
```

JS не определяет включённость функции пробным запросом к API.

Когда flag=false:

- выполняется только legacy Home flow;
- live timers/listeners/requests не создаются.

Когда flag=true:

- legacy `/health`, Visits 24h и Devices 24h Home requests/cards не выполняются и не смешиваются с Live Home;
- subtitle Home меняется с текущего `Health and a compact 24-hour Site summary` на live-current wording;
- normal refresh request budget остаётся ровно четыре начальных GET.

Добавить config invariant:

```text
WEB_ADMIN_HOME_LIVE_ENABLED=true
requires
WEB_ADMIN_ENABLED=true
```

### 3.12. Уточнить feature-disabled route order

Четыре routes должны быть зарегистрированы всегда, чтобы disabled response оставался canonical JSON, а не Flask HTML 404.

Для disabled feature зафиксировать порядок:

```text
HTTPS/network/request-size boundary
→ Admin session
→ Site syntax/allowlist
→ required capability
→ feature flag
→ 404 not_found
```

После feature gate Current State source не вызывается. Endpoint-specific query schema не должна раскрываться через разные ответы при disabled feature; authorized caller получает стабильный sanitized 404.

### 3.13. Исправить capability/DTO mismatch для AP page

Сейчас AP page назначена capability `admin.read.overview`, но предложенный DTO включает:

```text
IP
model
firmware
raw status code
last_seen
uptime
```

Это больше, чем overview-count boundary.

Для HOME-LIVE-01 принять минимальный вариант:

```text
AP page capability: admin.read.overview
AP item DTO:
  ap_mac
  name
  product_status_classification
```

Если архитектор считает обязательными IP/model/firmware или другие технические поля, AP page должна использовать более узкую существующую capability (`admin.read.observations`) либо отдельное будущее policy decision. Coder не должен самостоятельно расширять overview.

Аналогично сократить Client DTO до реально используемых Home fields. Не включать `device_type`, `radio_id`, `channel`, `auth_status_code` только «на будущее», если UI их не показывает. Каждый exposed field должен иметь зафиксированного UI consumer или отдельное принятое диагностическое назначение.

### 3.14. Добавить строгую frontend response validation

`requestJson()` сейчас проверяет только наличие object/result. Для Live Home этого недостаточно.

Перед rendering frontend обязан проверить:

- `api_version == admin.read.v1`;
- response `site_id` равен page Site;
- snapshot kind соответствует endpoint;
- freshness входит только в `fresh/stale/unavailable`;
- `age_seconds` null либо finite non-negative number;
- non-null counts являются non-negative integers, не boolean;
- Client и AP invariants сходятся;
- page snapshot/cycle/scope совпадает с pinned summary;
- item Site/cycle не противоречит selected snapshot;
- `next_cursor` null или bounded string;
- массивы действительно являются arrays;
- product status входит в allowlist.

Malformed 200 response не рендерится частично и не преобразуется в нули; section переходит в sanitized unexpected/source-integrity state.

Backend serializer также проверяет:

```text
item.site_id == authorized Site
item.cycle_id == selected snapshot cycle
client item SSID belongs to snapshot source scope
```

перед удалением внутренних полей и выдачей DTO.

### 3.15. Добавить измеримую route telemetry

Production acceptance требует server-side p95 и числа 429/503, но текущий Admin route layer не пишет completion duration для каждого data request.

FINAL должен потребовать sanitized event, например:

```text
admin.current_state_query_completed
```

Разрешённые поля:

```text
request_id
route_name (allowlist, не raw URL)
source_kind = client|ap
site_id после authorization
status_code
outcome/reason из allowlist
duration_ms
item_count
```

Запрещены:

```text
MAC/IP/SSID
cursor/cycle_id
scope hash
raw query string
source exception text
```

Тесты должны доказать и наличие измеримого event, и отсутствие sensitive fields. В production gate указать минимальную выборку для p95: не менее 20 измерений каждого endpoint либо явно согласованный эквивалент.

### 3.16. Учесть `shutdown` в latest-attempt semantics

Current State result contract включает не только `partial/failed`, но и `shutdown`.

UI message сделать generic:

```text
Latest collection attempt did not complete successfully;
showing the latest complete snapshot.
```

Добавить frontend/backend тесты для `latest_attempt_result=shutdown`. Raw failure category по-прежнему не показывать.

### 3.17. Уточнить API data minimization

Необходимо согласовать sections 41, 59, 60, 75: сейчас API предлагает больше полей, чем фактически показывает UI.

Принцип FINAL:

```text
No unused fields in v1 DTO merely for future use.
```

Рекомендуемый Client v1 item:

```text
client_mac
name
hostname
ip
ssid
ap_name
ap_mac
band
rssi
snr
controller_uptime
controller_traffic_down
controller_traffic_up
controller_traffic_total
auth_classification
```

Рекомендуемый AP v1 item указан в 3.13.

`source_scope` также сериализуется по allowlist:

```text
scope_type
site_id
ssids (только Client scope)
```

Нельзя просто выполнять `dict(source_scope)` и автоматически публиковать будущие source keys.

### 3.18. Уточнить Home UI при 11 технических полях

Текущий набор колонок слишком широк для существующей responsive shell.

Предпочтительное решение:

- основные колонки: Device/MAC, Auth, IP, AP, Band, RSSI, SNR;
- controller uptime/counters — раскрываемый `Controller facts` блок строки либо desktop-only secondary columns;
- если сохраняется полноценная таблица, она находится в labelled horizontal scroll container, не ломает 560/820px layouts и не обрезает identity/status;
- raw integers показываются без единиц;
- null показывается `—`;
- labels остаются нейтральными.

Обязательная accessibility-разметка:

```text
table caption
thead
th scope=col
visible focus
status conveyed by text, not color only
labelled sort/filter controls
```

Не делать весь обновляемый table container общим `aria-live`, иначе каждые 60 секунд screen reader будет повторно читать большую таблицу. Live announcement должен быть коротким и отдельным.

### 3.19. Зафиксировать sort direction и null placement

API labels должны отражать фактический source order:

```text
MAC                    ascending
Controller uptime      descending, null last
Controller traffic*    descending, null last
Auth status            ascending
AP                     ascending, null last
RSSI                    descending, null last
SNR                     descending, null last
```

Frontend не должен показывать ambiguous sort label без направления. Filter options для AP строятся из union:

```text
Client summary AP buckets
+ loaded AP inventory
```

чтобы AP, присутствующая у клиентов, не исчезала из filter только из-за неполной AP pagination.

### 3.20. Уточнить optional-source construction boundary

Передача optional Current State dependency не должна попасть в существующий `source_ready` gate и не должна сделать:

```text
AdminWebRuntime.state = unavailable
```

Требуемая композиция:

1. существующие обязательные Admin sources строятся как раньше;
2. `AdminQueryService` создаётся как раньше;
3. optional `current_state_read_service` сохраняется без dereference repository/config/path;
4. отсутствие или даже malformed optional object затрагивает только четыре live methods;
5. старые methods/pages продолжают работать.

Добавить `run.py` wiring test, доказывающий передачу именно:

```text
_current_state_runtime.read_service
```

и тест с `None`/poison optional source, при котором legacy Admin остаётся active.

### 3.21. Запретить browser persistence текущих устройств

Добавить privacy requirement:

```text
Home Live не сохраняет MAC/IP/cursors/snapshots
в localStorage, sessionStorage, IndexedDB,
Cache API или service worker cache.
```

Состояние существует только в памяти текущей страницы. Все Admin responses остаются `Cache-Control: no-store`.

### 3.22. Укрепить production activation/rollback contract

Точный activation script подготавливается только после известного merged SHA, но FINAL должен потребовать, чтобы будущий runbook включал:

- exact SHA и clean tree gate;
- backup environment с сохранением metadata;
- config parser dry validation до restart;
- проверку `/etc/default/captive-portal` как `root:root 0600` после записи;
- PID before/after и bounded service startup gate;
- Portal/CAPPORT/Admin smoke;
- четыре Home API smoke с authenticated owner session;
- Client/AP cycle coexistence;
- Observation/Visit/Registry coexistence;
- journal scan только с activation timestamp;
- automatic environment rollback при failed restart/HTTP/config gate;
- отдельный post-activation browser/soak gate;
- rollback только Home flag, без отключения Current State и без удаления DB.

`production acceptance = several cycles` заменить на точное минимальное число refresh cycles и измерений.

---

## 4. Дополнительные обязательные тесты

К уже перечисленным в DRAFT добавить:

```text
source summary invariant failure → 503, not 400
sqlite3 read failure → 503
default 100 / hard max 250
explicit missing cycle → 400
cursor cycle expired during Load More → reset + clean refresh
future AP offline classification → product Other
AP first page incomplete → not_yet_loaded, not absent
separate Client/AP cursors
new Client summary + failed pinned page → old rows not mixed
late response from old generation ignored
request timeout releases in-flight state
hidden-tab abort is neutral
per-source backoff does not slow healthy source
401 stops all polling
404 feature rollback stops live polling
malformed successful JSON rejected
item Site/cycle/scope mismatch rejected
shutdown latest attempt warning
feature=true disables legacy Home requests
conditional Home subtitle
no browser storage writes
responsive table/accessibility structure
run.py passes exact optional read_service
poison Current State optional dependency does not disable legacy Admin
sanitized route completion telemetry
```

---

## 5. Allowed-files correction

Текущий allowed scope в целом принят. Уточнить, что ожидаемыми являются также:

```text
app/admin_web/pages.py
```

для безопасной передачи Home feature context и subtitle/template state, а также допустим новый тест:

```text
tests/admin_web/test_run_wiring.py
```

если это чище существующих tests.

Новые Python/Node production dependencies запрещены.

`app/current_state/**` остаётся read-only dependency. Его изменение для удобства Home не разрешено данным FINAL.

---

## 6. Решения, которые не оставлять Coder-у

Архитектор должен зафиксировать в FINAL уже выбранные решения:

```text
Deadline:
  Option A accepted with mandatory pre/post checks.

AP Offline:
  no Offline product label;
  future source offline collapses into product Other.

AP page capability:
  admin.read.overview only with minimal AP DTO.

Pagination:
  separate Client and AP cursors/controls.

Retry/backoff:
  independent Client and AP state.

Frontend timeout:
  AbortController + bounded configured timeout.

Feature-disabled routes:
  registered canonical JSON routes;
  404 only after security/Site/capability boundary.

Legacy Home:
  used only when feature=false;
  no legacy requests/cards when feature=true.
```

Coder не должен повторно выбирать между этими вариантами в PLAN.

---

## 7. Что оставить вне `HOME-LIVE-01`

Out-of-scope DRAFT принят. Не добавлять:

```text
traffic rate calculation
Mbps or byte-unit interpretation
Current Traffic card
Today metrics
System Health matrix
24h AP analytics
new collector
new Omada call
WebSocket/SSE
write/control actions
tenant/RBAC implementation
Grafana integration
Current State schema/source changes
```

Neutral raw Client controller counters разрешены только как явно названные controller facts и не должны превращаться в analytics.

---

## 8. Требование к следующей версии архитектора

Подготовить:

```text
TASK-HOME-LIVE-01-FINAL
Status: FINAL FOR SHORT TECH LEAD CONTROL REVIEW
Implementation authorization: NOT GRANTED
```

FINAL должен:

1. сохранить сильные части текущего DRAFT;
2. встроить обязательные исправления из этого review в соответствующие разделы, а не приложить их отдельным неоперационным списком;
3. устранить противоречия между API, UI state machine, pagination и acceptance tests;
4. не оставлять Coder-у архитектурные A/B решения;
5. сохранить baseline `a864dfa78461ccbfe88e110b1aa5bad5f6bfa23e`, если `origin/main` не изменился;
6. при изменении `origin/main` выполнить impact review по `app/current_state/**`, `app/admin_web/**`, `run.py`, config/settings и соответствующим tests;
7. не создавать branch, code, commit, push, PR или production change до отдельного Owner authorization.

После этих точечных исправлений направление может быть утверждено без повторного проектирования Home Live с нуля.
