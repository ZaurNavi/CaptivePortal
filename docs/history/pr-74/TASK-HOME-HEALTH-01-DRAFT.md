# TASK-HOME-HEALTH-01 — DRAFT

**Project:** CaptivPortal  
**Area:** Admin Console → Home  
**Status:** DRAFT — for Owner / Tech Lead review  
**Prepared against repository:** `main@7307cb0f1a5da6d452f5d90e5303d34127ebc916`  
**Runtime code checkpoint represented by current main:** `53f617b3ac0155d0d647e58e98309927f9a4d318`  
**Date:** 2026-08-27

---

## 0. Executive decision

`HOME-HEALTH-01` adds a product-facing **System Health** block to the existing Home page.

The block answers:

> “CaptivPortal сейчас работает нормально или какой-то его функциональный блок деградировал?”

It must not become a replacement for Grafana/Loki/systemd and must not perform remote probes, repairs or control actions.

Canonical top-level health statuses for v1:

- `operational`
- `degraded`
- `unavailable`
- `unknown`

`initializing` and `stale` are **reason semantics**, not additional top-level statuses:

- initializing / no current evidence → `unknown`;
- stale periodic evidence → `degraded`;
- positive source/runtime unavailability → `unavailable`.

`UNKNOWN != OPERATIONAL`.

A Site Home response contains both Site-scoped and global/application-scoped components. Scope is explicit in the model and is never silently mixed.

The v1 visible component set is deliberately small:

1. **Guest Access** — Site-scoped, critical.
2. **Live Network State** — Site-scoped.
3. **Network History Collection** — Site-scoped.
4. **Visit Tracking** — global/application-scoped.
5. **Analytics & Home Data** — global/application-scoped.

The following are **not separate visible components** in v1:

- Omada/provider connectivity;
- raw database/storage;
- Visitor Registry;
- Pending Session Cleaner;
- Visitor Snapshot collector;
- Public Traffic;
- Admin Web process/runtime itself.

Their failures are surfaced through the product component they affect.

---

# 1. Goal

Add an optional Home `System Health` panel that provides a compact product-safe state of core CaptivPortal functional areas.

The user must be able to determine:

- whether the core guest access path is known to be working;
- whether Home live data is current;
- whether historical network facts continue to be collected;
- whether Visit processing is active;
- whether Analytics/Home read models are available;
- whether a problem is partial degradation, complete unavailability, or insufficient evidence.

This TASK defines functional behavior and architecture only. Final Home visual composition belongs to the later Web Designer phase.

---

# 2. Current-state baseline

Implementation MUST start from exact current `origin/main`.

At DRAFT preparation time:

- repository `main` = `7307cb0f1a5da6d452f5d90e5303d34127ebc916`;
- runtime code checkpoint = `53f617b3ac0155d0d647e58e98309927f9a4d318`;
- the difference is documentation-only;
- current application topology is one application process;
- one shared `OmadaProvider` is created in `run.py` and reused by Portal/Auth, Observation, Current State and other consumers;
- Home Live, Home Traffic and Home Activity already exist;
- Admin API is authenticated and Site-aware;
- Admin currently has `/admin/api/v1/health`, but it reports only `AdminWebRuntime.state` and MUST NOT be redefined as the new System Health contract;
- Current State already provides canonical `fresh / stale / unavailable` snapshot freshness semantics;
- Observation runtime already exposes `active / degraded / unavailable` behavior and persists cycle facts;
- Visit Lifecycle already exposes `active / degraded / unavailable`, including webhook-reader health;
- Analytics already exposes source-boundary health and a lightweight read-only `live_health_payload()` that validates source schema/query-only boundaries.

No new monitoring stack is required.

---

# 3. Architectural boundaries

## 3.1 Product read model

Home Health is a **read-only product read model** owned by Admin Web composition.

Preferred shape:

```text
Home browser
    ↓
GET /admin/api/v1/sites/<site_id>/home/health
    ↓
Admin route / Site authorization
    ↓
AdminQueryService
    ↓
HomeHealthReadService
    ↓
existing runtime/read evidence only
```

`HomeHealthReadService` MUST NOT:

- call Omada directly;
- create another `OmadaProvider`;
- perform request-time network probes;
- query Loki/Grafana;
- scan journal/log files;
- run `PRAGMA quick_check`;
- mutate DBs;
- trigger retries/restarts/cleanup;
- create a background worker;
- create a health database.

## 3.2 Composition

`run.py` may inject existing process-local runtimes/read boundaries into Admin composition.

Allowed injected evidence sources include:

- authorization health evidence described in §7;
- Current State runtime/read service;
- Observation runtime/read boundary;
- Visit Lifecycle runtime/read boundary;
- Analytics runtime;
- Visitor Registry runtime/read boundary only as an internal dependency signal where needed.

The shared Omada provider MUST NOT be injected into the Home Health reader for request-time use.

## 3.3 Failure isolation

Every component evaluator is isolated.

A failure reading one component:

- MUST NOT fail the remaining component evaluations;
- MUST NOT make the route call Omada as fallback;
- MUST NOT fabricate `operational`;
- yields a product-safe component state, normally `unknown` with `reason_code=health_read_failed`, unless positive existing evidence proves `unavailable`.

---

# 4. Canonical health state model

## 4.1 Status enum

Exactly:

```text
operational
degraded
unavailable
unknown
```

No synonym states in API v1.

## 4.2 Meanings

### `operational`

Positive evidence exists that the component's required current runtime/read path is functioning according to its own contract.

### `degraded`

The component remains usable or has usable last-known data, but one or more required signals are stale, partial, failed, or degraded.

### `unavailable`

Positive evidence shows that the component cannot currently provide its product function.

Examples:

- required runtime is `unavailable`;
- required worker is not running;
- Current State canonical freshness is `unavailable`;
- Analytics required source boundary cannot be opened/validated.

### `unknown`

There is insufficient trustworthy evidence to classify the component as operational/degraded/unavailable.

Examples:

- startup/initializing;
- Guest Access has not yet produced any real authorization outcome in the current process lifetime;
- a component health read itself fails and no stronger source state is known.

## 4.3 `initializing`

Not a fifth status.

Represent as:

```json
{
  "status": "unknown",
  "reason_code": "initializing"
}
```

## 4.4 `stale`

Not a fifth status.

For periodic evidence:

```json
{
  "status": "degraded",
  "reason_code": "stale_evidence"
}
```

A component becomes `unavailable` only when the source subsystem's existing semantics or positive runtime state prove unavailability. Do not invent an additional age-only “hard down” threshold unless the source already has one.

## 4.5 Terminal / non-terminal

All four product states are re-evaluated on every Health read and are therefore non-terminal.

`unavailable` does not mean permanent failure.

A later successful source evaluation MUST allow automatic recovery without restart of Home Health itself.

---

# 5. Component inventory

## 5.1 `guest_access`

**Display label:** Guest Access  
**Scope:** `site`  
**Criticality:** `critical`

Represents the Captive Portal authorization path for the selected Site.

This is the only v1 component whose unavailability makes aggregate System Health `unavailable`.

### Why it is included

Guest authorization is the core product function. Excluding it would allow Home to report the system as fully operational while the actual guest-access function is not proven.

### Current repository gap

Current repository has:

- `AuthSessionManager`;
- verified authorization/readback workflow;
- detailed authorization telemetry events;
- local rotating `auth_telemetry.log`.

It does **not** currently expose a canonical product-safe, read-only authorization health snapshot.

Home Health MUST NOT parse `auth_telemetry.log`.

Therefore HOME-HEALTH-01 includes a minimal authorization health evidence foundation described in §7.

---

## 5.2 `live_network_state`

**Display label:** Live Network State  
**Scope:** `site`  
**Criticality:** `feature`

Represents current Site client/AP facts used by Home Live.

Source of truth:

- `CurrentStateRuntime.state`;
- `CurrentStateReadService.get_current_client_summary()`;
- `CurrentStateReadService.get_current_ap_summary()`;
- their existing `CurrentSnapshotMeta.freshness_status`.

No new freshness model is allowed for Current State.

---

## 5.3 `network_history`

**Display label:** Network History Collection  
**Scope:** `site`  
**Criticality:** `feature`

Represents persisted Observation collection that feeds historical network/traffic analytics.

Source of truth:

- `ObservationFoundationRuntime.state`;
- worker running/degraded state;
- latest persisted `observation_cycles` facts for the selected Site;
- Observation configuration cadence/bounds.

No Omada call is made by Health.

---

## 5.4 `visit_tracking`

**Display label:** Visit Tracking  
**Scope:** `global`  
**Criticality:** `feature`

Represents Visit Lifecycle ingestion/start/reconciliation as a product feature.

Source of truth:

- `VisitLifecycleRuntime.state`;
- `VisitLifecycleRuntime.available`;
- existing webhook reader health integrated into runtime state;
- optional lightweight persisted reader progress timestamp if already available.

No “last Visit age” health threshold is allowed because absence of guest visits is a valid state and does not imply failure.

---

## 5.5 `analytics_home_data`

**Display label:** Analytics & Home Data  
**Scope:** `global`  
**Criticality:** `feature`

Represents the read-only Analytics layer and current Home data services.

Source of truth:

- `AnalyticsRuntime.state`;
- existing `AnalyticsRuntime.live_health_payload()`;
- existing source-boundary checks for observations / visits / registry;
- presence of the Home read services required by current product:
  - `current_traffic_service`;
  - `home_activity_service`.

No row scan is required.

---

# 6. Explicitly excluded standalone components

## 6.1 Omada connectivity / provider availability

Do **not** create a separate `omada` health row in v1.

Reason:

- the shared provider currently has no canonical standalone health state;
- read and authorization paths can fail differently;
- a synthetic request-time probe would create a new active dependency and can misrepresent Site-specific behavior;
- Current State, Observation and Guest Access already expose product impact of Omada communication failures.

Omada-related product-safe reason codes may be emitted by affected components, e.g.:

- `controller_unreachable`;
- `controller_authentication_failed`;
- `controller_response_invalid`.

Do not expose Omada URL, token, error body or internal endpoint.

## 6.2 Database / storage

Do not show a generic “Database” row.

Storage is an implementation dependency.

A storage failure must be reflected in the affected product component:

- Live Network State unavailable;
- Visit Tracking unavailable/degraded;
- Analytics unavailable;
- etc.

Do not expose DB names or paths.

## 6.3 Visitor Registry

Do not show it as a separate v1 row.

It is an internal identity/reconciliation source. Its failure is already meaningful through:

- Visit Tracking;
- Analytics source boundary.

A separate row would duplicate the same failure without additional product value.

## 6.4 Pending Session Cleaner / Snapshot / Public Traffic

Excluded from v1 visible System Health because their current degradation does not map cleanly to an independent Home user-facing functional block required by this TASK.

They may be added later only under a separate approved contract.

---

# 7. Authorization health evidence foundation

## 7.1 Requirement

Add a **small, bounded, process-local, read-only health evidence object** for authorization.

This is not a monitoring subsystem.

It MUST have:

- no thread;
- no DB;
- no log parsing;
- no remote call;
- no client list;
- no unbounded history.

Preferred conceptual interface:

```python
record_verified_success(site_id, occurred_at)
record_system_failure(site_id, occurred_at, category, retryable)
snapshot(site_id) -> immutable AuthHealthEvidence
```

Maximum state: one bounded aggregate record per configured/observed Site.

## 7.2 Update points

Evidence MUST be updated only at already authoritative authorization outcome transitions.

### Verified success

Record success only after the existing success contract is satisfied:

```text
authorization request
→ Omada response accepted
→ verification readback
→ authStatus == 2
```

A successful POST without verification is not enough.

### Failure

Record only **system-relevant** failures.

Examples:

- provider/network timeout;
- controller network error;
- token/authentication failure;
- malformed controller response;
- authorization worker/system exception.

Do not mark System Health degraded/unavailable for a client-specific condition that is not evidence of a system failure.

## 7.3 Secret/privacy boundary

Authorization health evidence MUST NOT store:

- MAC;
- IP;
- SSID;
- session ID;
- token;
- URL;
- raw controller response;
- exception text.

Allowed evidence:

- Site ID;
- last verified success timestamp;
- last system failure timestamp;
- normalized failure category;
- retryable boolean;
- whether authorization subsystem is accepting work.

## 7.4 Status rules

For selected Site:

### `unknown`

- current process has not observed any trustworthy authorization outcome; or
- subsystem is initializing and no stronger state is known.

Reason example:

`no_authorization_evidence`

This is expected immediately after process restart until a real authorization attempt produces evidence.

### `operational`

- authorization subsystem is available/accepting; and
- latest system-relevant authorization outcome is a verified success.

No event-age expiry is imposed in v1 because authorization is request-driven; absence of requests is not a stale periodic collector.

The API MUST expose the evidence timestamp so the user can see when the last real proof occurred.

### `degraded`

- latest system-relevant evidence is a retryable/transient system failure;
- subsystem remains available and can accept later attempts.

### `unavailable`

- authorization subsystem itself is not available/accepting; or
- latest positive system evidence proves a non-retryable controller/authentication/configuration failure that prevents authorization.

A later verified success MUST recover the component automatically.

## 7.5 Fail-open requirement

Any failure inside the authorization health tracker MUST NOT change or block guest authorization behavior.

Health evidence is subordinate to the authorization path.

---

# 8. Current State health rules

Evaluate client and AP summaries independently using existing canonical metadata.

## `operational`

- runtime state is `active`;
- client freshness = `fresh`;
- AP freshness = `fresh`;
- both required summaries are readable.

## `degraded`

Any of:

- runtime state = `degraded`;
- client freshness = `stale`;
- AP freshness = `stale`;
- latest attempt failed/partial but a valid last complete snapshot remains available.

Reason examples:

- `client_state_stale`;
- `ap_state_stale`;
- `latest_collection_incomplete`.

## `unavailable`

Any required side is positively unavailable:

- runtime state = `unavailable` or disabled while Home expects Current State;
- client freshness = `unavailable`;
- AP freshness = `unavailable`;
- required persisted source cannot be read.

## `unknown`

- runtime is starting;
- evidence cannot be evaluated safely and no stronger unavailable fact exists.

## Evidence timestamp

Component `evidence_at` is the older of the required client/AP successful evidence timestamps, because component health is only as current as its least-current required side.

Existing Current State defaults remain authoritative, including its current fresh/stale/unavailable thresholds.

HOME-HEALTH-01 MUST NOT add competing Current State thresholds.

---

# 9. Observation health rules

Observation is periodic, therefore staleness matters.

Use:

- runtime state;
- worker running/degraded state;
- latest Site cycle facts by enabled collector kind;
- existing Observation intervals, request bounds and AP cycle bounds.

## `operational`

- Observation runtime = `active`;
- each enabled required collector worker is running;
- latest relevant Site cycle is successful/complete;
- latest cycle is not overdue according to that collector's own configured cadence/bounded execution semantics.

## `degraded`

Any of:

- runtime = `degraded`;
- latest Site cycle is partial/failed but worker remains running;
- latest valid evidence is overdue relative to configured collection cadence;
- integrity/cleanup state currently degrades Observation runtime.

Staleness reason:

`stale_evidence`

Do not introduce a fixed hard-coded “N minutes” threshold.

The evaluator derives expected freshness from the collector's own configuration.

## `unavailable`

Positive evidence only:

- runtime = `unavailable`;
- required worker is not running outside startup/shutdown state;
- source storage cannot be opened/read safely.

Do not escalate to unavailable solely because there were no clients in a cycle.

## `unknown`

- startup before first required cycle;
- source cannot be safely classified.

## Evidence timestamp

Use the oldest latest-cycle timestamp among required enabled collector kinds for the selected Site.

---

# 10. Visit Lifecycle health rules

Visit Lifecycle is event-driven and its runtime already integrates webhook-reader health.

## `operational`

`VisitLifecycleRuntime.state == "active"` and `available == True`.

## `degraded`

`VisitLifecycleRuntime.state == "degraded"`.

This includes reader/reconciliation degradation already represented by the runtime.

## `unavailable`

Runtime is `unavailable` or required Visit Lifecycle is disabled for the running product.

## `unknown`

Runtime is `starting` or state cannot be safely determined.

## Freshness

Do not infer failure from “no recent Visit”.

No guest activity is valid.

If `visit_reader_state.updated_at` is available, it may be returned as optional evidence/progress metadata, but v1 does not invent a wall-clock freshness threshold for Visit activity.

---

# 11. Analytics & Home Data health rules

Use existing Analytics source-boundary health.

`AnalyticsRuntime.live_health_payload()` is allowed because it:

- opens existing source read boundaries;
- checks schema version;
- checks `PRAGMA query_only`;
- does not scan domain rows;
- does not write;
- does not call Omada.

## `operational`

- Analytics runtime = `active`;
- all required source boundaries are available;
- required core Analytics services exist;
- `current_traffic_service` exists;
- `home_activity_service` exists.

## `degraded`

Analytics core remains active/readable, but one optional Home read service required by the current Home product is missing/unavailable while required source boundaries remain usable.

Reason examples:

- `current_traffic_service_unavailable`;
- `home_activity_service_unavailable`.

## `unavailable`

- Analytics runtime = `unavailable`; or
- one or more required source boundaries fail schema/query-only/open validation.

## `unknown`

Health evaluation itself fails and no stronger state is available.

## Scope

`global`.

A source-boundary failure can affect all Sites; the API must not pretend it is Site-local.

---

# 12. Aggregate System Health

Aggregate health is not generic `worst(status)`.

Each component has:

```text
criticality = critical | feature
```

In v1:

- `guest_access` = `critical`;
- all other visible components = `feature`.

Aggregation order:

### 1. `unavailable`

If any `critical` component is `unavailable`.

### 2. `degraded`

If no critical component is unavailable, but any of:

- a critical component is `degraded`;
- a feature component is `degraded`;
- a feature component is `unavailable`.

A Home/analytics failure therefore degrades CaptivPortal product health but does not claim the core captive access service is completely down.

### 3. `unknown`

If no known degradation/unavailability exists, but at least one included component is `unknown`.

This prevents UNKNOWN from becoming false HEALTHY.

### 4. `operational`

Only if every included component is `operational`.

---

# 13. Source-of-truth matrix

| Component | Scope | Source | Periodic freshness | Standalone remote probe |
|---|---|---|---|---|
| Guest Access | Site | new bounded auth outcome evidence over existing verified auth transitions | No; request-driven | Forbidden |
| Live Network State | Site | Current State runtime + canonical read-service metadata | Reuse existing Current State thresholds | Forbidden |
| Network History Collection | Site | Observation runtime + persisted cycle evidence | Derived from existing Observation cadence/bounds | Forbidden |
| Visit Tracking | Global | Visit Lifecycle runtime / reader health | No Visit-age threshold | Forbidden |
| Analytics & Home Data | Global | Analytics runtime + source-boundary checks | Source availability, not data-event age | Forbidden |

---

# 14. Site / global scope model

Every component response MUST include:

```json
{
  "scope": {
    "type": "site",
    "site_id": "..."
  }
}
```

or:

```json
{
  "scope": {
    "type": "global"
  }
}
```

Rules:

- Site components are evaluated for the selected authorized Site.
- Global components represent process-wide/runtime-wide state.
- A global failure may be shown on every Site Home, but MUST remain labeled global in the API model.
- No `tenant_id` is introduced.
- No current single-Site production ID may be hard-coded into Health logic.

---

# 15. API contract

## 15.1 New endpoint

```http
GET /admin/api/v1/sites/<site_id>/home/health
```

One aggregate endpoint is preferred.

Do not create one endpoint per component.

## 15.2 Existing endpoint compatibility

Existing:

```http
GET /admin/api/v1/health
```

MUST retain its current contract unless a separate TASK explicitly changes it.

HOME-HEALTH-01 does not repurpose it.

## 15.3 Request

No query parameters in v1.

Unexpected query parameters → existing Admin `invalid_request` behavior.

Authentication and Site authorization reuse existing Admin middleware/policy.

## 15.4 Successful response

Conceptual payload:

```json
{
  "api_version": "admin.read.v1",
  "data": {
    "health_version": 1,
    "site_id": "6a64f17630da7c70d232187a",
    "evaluated_at": "2026-08-27T12:00:00.000Z",
    "status": "degraded",
    "message": "Some CaptivPortal functions are degraded.",
    "components": [
      {
        "id": "guest_access",
        "label": "Guest Access",
        "status": "operational",
        "reason_code": "latest_authorization_verified",
        "message": "Guest authorization is operating normally.",
        "criticality": "critical",
        "scope": {
          "type": "site",
          "site_id": "6a64f17630da7c70d232187a"
        },
        "evidence_at": "2026-08-27T11:58:34.000Z",
        "last_success_at": "2026-08-27T11:58:34.000Z"
      }
    ]
  }
}
```

Exact outer success envelope must follow current Admin API conventions.

## 15.5 Required component fields

- `id`
- `label`
- `status`
- `reason_code`
- `message`
- `criticality`
- `scope`
- `evidence_at` nullable
- `last_success_at` nullable

Optional product-safe metadata is allowed only when it has Home user value.

## 15.6 HTTP behavior

- Health feature disabled → `404 not_found`, matching current optional Home feature pattern.
- Health feature configuration/source composition unavailable as a whole → `503 source_unavailable`.
- One or more component failures inside a successful Health evaluation → HTTP `200`, with component and aggregate statuses carrying the degradation.
- Unauthorized Admin → existing `401`.
- Site forbidden → existing `403`.
- Invalid Site/request → existing Admin behavior.

---

# 16. Reason-code contract

Reason codes are stable machine-readable product codes.

They MUST NOT contain:

- exception class;
- exception message;
- DB path;
- URL;
- PID;
- hostname;
- raw Omada error body.

Minimum useful v1 set may include:

```text
operational
initializing
no_authorization_evidence
latest_authorization_verified
authorization_transient_failure
authorization_unavailable
controller_unreachable
controller_authentication_failed
current_state_stale
current_state_unavailable
latest_collection_incomplete
stale_evidence
observation_unavailable
visit_runtime_degraded
visit_runtime_unavailable
analytics_source_unavailable
current_traffic_service_unavailable
home_activity_service_unavailable
health_read_failed
component_disabled
```

Coder may reduce/normalize this list, but semantics MUST remain product-safe and deterministic.

---

# 17. Home functional UI contract

This TASK does not define final design.

The Home template needs only enough structure to render the feature.

Functional requirements:

- one System Health section;
- one aggregate state;
- one short aggregate explanation;
- component rows/items;
- each component shows:
  - display label;
  - one of the four canonical states;
  - short user-facing explanation;
  - last evidence/update time when meaningful;
- global vs Site scope must be representable;
- no debug counters;
- no raw exceptions;
- no process details;
- no infrastructure topology.

Example user-facing wording:

- Operational — “Working normally.”
- Degraded — “Data collection is delayed; last known data remains available.”
- Unavailable — “This function is currently unavailable.”
- Unknown — “There is not enough current evidence to confirm status.”

Final colors/icons/grid/spacing are NOT part of this TASK.

---

# 18. Refresh / browser behavior

## 18.1 Default cadence

Add:

```text
WEB_ADMIN_HOME_HEALTH_REFRESH_SECONDS=60
```

Repository default range:

```text
60..300
```

Rationale:

- Home Live default = 60 s;
- Home Traffic default = 60 s;
- Home Activity default = 60 s;
- Current State collectors operate on approximately minute-scale cadence;
- faster Health polling would not produce meaningfully newer source evidence.

## 18.2 Request timeout

Add:

```text
WEB_ADMIN_HOME_HEALTH_REQUEST_TIMEOUT_SECONDS=20
```

Bound:

```text
5..60
```

It MUST exceed the existing Admin query deadline, following the current Home read-feature pattern.

## 18.3 Existing Home orchestration

Health MUST join the existing Home refresh coordination model.

Do not create an unrelated permanent timer/request loop.

Preserve current Home behavior for:

- request cancellation/abort;
- stale-generation protection;
- hidden-tab pause;
- bounded retry/backoff behavior.

## 18.4 Refresh failure

If the Health HTTP refresh itself fails:

- do not convert last known statuses to `operational`;
- panel-level state becomes `unknown` / update unavailable;
- last successfully rendered component values may remain visible only with their old timestamp;
- recovery on the next successful refresh requires no page reload.

---

# 19. Configuration / feature flag

Add:

```text
WEB_ADMIN_HOME_HEALTH_ENABLED=false
WEB_ADMIN_HOME_HEALTH_REFRESH_SECONDS=60
WEB_ADMIN_HOME_HEALTH_REQUEST_TIMEOUT_SECONDS=20
```

Repository default = disabled.

Production activation is separate and Owner-controlled.

Health configuration parsing MUST be fail-open relative to the rest of Admin Web.

If Health config is invalid:

- Admin Web remains usable;
- Home Live remains independent;
- Home Traffic remains independent;
- Home Activity remains independent;
- Health state becomes unavailable.

Do not require Home Traffic or Home Activity flags merely to enable Home Health.

Admin Web itself must be enabled because Health is an Admin Home feature.

---

# 20. Fast rollback

Fast rollback:

```text
WEB_ADMIN_HOME_HEALTH_ENABLED=false
```

Rollback MUST NOT disable or modify:

- Home Live;
- Home Traffic;
- Home Activity;
- Current State;
- Observation;
- Visit Lifecycle;
- Analytics;
- guest authorization.

No data rollback/migration is required because HOME-HEALTH-01 creates no Health DB/schema.

---

# 21. Security

Reuse current Admin security boundary.

Requirements:

- authenticated Admin only;
- existing source-network restriction;
- existing Site authorization;
- same-origin Admin fetch only;
- no secrets;
- no credentials;
- no Omada URL;
- no internal service URLs;
- no DB paths;
- no hostname/PID;
- no raw stack trace;
- no raw SQLite/requests exception;
- no MAC/IP/SSID in authorization health evidence;
- no log contents.

Health reason messages must be explicit allowlisted product text.

---

# 22. Performance / capacity

Home Health evaluation MUST have bounded fixed cost.

Required characteristics:

- component count is fixed/small;
- O(number of components), not O(number of clients/visits/observations);
- at most lightweight metadata/read-boundary queries per component;
- no full-table scans;
- no integrity scan;
- no historical range aggregation;
- no log scan;
- no Omada HTTP request;
- no blocking work outside existing Admin query deadline.

Analytics source checks may reuse existing `PRAGMA user_version` / `PRAGMA query_only` validation.

Observation health may query only latest cycle metadata using indexed/ordered bounded reads.

Current State must reuse its existing summary/meta read path.

No new performance SLA is invented beyond existing Admin query/deadline constraints; targeted tests must prove Health stays within them.

---

# 23. Failure isolation

Each evaluator executes behind an exception boundary.

Example:

```text
Guest Access read fails
→ Guest Access = unknown
→ Current State still evaluated
→ Observation still evaluated
→ Visit still evaluated
→ Analytics still evaluated
→ aggregate computed from resulting component states
→ HTTP 200 if Health service itself completed
```

No single source exception may cause a 500 for the whole Home Health response.

A whole-feature 503 is reserved for Health composition/configuration unavailability, not one component being unhealthy.

---

# 24. Internal observability

Home Health itself requires minimal internal observability.

Allowed events:

```text
admin.home_health_evaluation_failed
admin.home_health_component_read_failed
admin.home_health_stale_evidence
admin.home_health_status_changed
```

Rules:

- `component_read_failed` includes component ID and product-safe category only;
- no raw exception text in structured public fields;
- stale/status-change events must be transition/rate-limited, not emitted every 60-second poll;
- `status_changed` is optional if implementing it would require an unnecessary new stateful subsystem;
- product API never returns engineering telemetry.

Existing missing `current_state.runtime_started` observability gap is NOT part of HOME-HEALTH-01 and MUST NOT be interpreted as Current State runtime failure.

---

# 25. Implementation surface

Expected main code areas, subject to coder confirmation against exact baseline:

```text
app/auth/
    minimal product-safe authorization health evidence

app/admin_web/
    config.py
    runtime.py
    query_service.py
    routes.py
    home_health.py                  # preferred new evaluator/read model
    home_health_serialization.py    # if kept consistent with current Home modules
    templates/admin/home.html
    static/admin.js
    static/admin.css                # minimal functional styling only

run.py
    composition/injection only

tests/
    auth health evidence tests
    admin home health evaluator/API/frontend contract tests
```

Do not add:

- a Health SQLite database;
- a Health worker;
- a Health Omada client;
- Loki/Grafana dependencies.

---

# 26. Testing — targeted

Coder must add targeted tests covering at minimum:

## Health model

1. all components operational → aggregate operational;
2. critical Guest Access unavailable → aggregate unavailable;
3. critical Guest Access degraded → aggregate degraded;
4. feature component unavailable → aggregate degraded;
5. one unknown with no known fault → aggregate unknown;
6. known degradation + another unknown → aggregate degraded;
7. unknown never becomes operational.

## Guest Access

8. no current-process auth evidence → unknown;
9. verified `authStatus == 2` success → operational;
10. POST success without verification does not produce operational;
11. retryable system failure → degraded;
12. positive non-retryable system unavailability → unavailable;
13. later verified success recovers;
14. client-specific non-system outcome does not falsely mark system unavailable;
15. tracker failure does not affect guest authorization;
16. no MAC/IP/SSID/session/token stored in health evidence.

## Current State

17. client fresh + AP fresh → operational;
18. one stale → degraded;
19. latest incomplete attempt with last complete snapshot → degraded;
20. one required side unavailable → component unavailable;
21. no complete evidence/startup → unknown or unavailable strictly according to existing Current State state/freshness contract;
22. Current State thresholds are reused, not duplicated.

## Observation

23. active workers + complete current cycles → operational;
24. runtime degraded → degraded;
25. partial/failed latest cycle → degraded;
26. overdue periodic evidence → degraded/stale;
27. runtime/required worker unavailable → unavailable;
28. empty client inventory in a successful complete cycle is not a failure;
29. startup before first cycle → unknown.

## Visit Lifecycle

30. active → operational;
31. degraded reader/reconciler → degraded;
32. unavailable → unavailable;
33. no recent Visits alone does not degrade health.

## Analytics

34. all source boundaries valid → operational;
35. schema/query-only/open failure → unavailable;
36. missing current traffic service with core analytics active → degraded;
37. missing Home Activity service with core analytics active → degraded;
38. no domain-row scan required.

## Isolation/API/security

39. one component evaluator raises → others still return;
40. route returns 200 with component degradation;
41. whole feature disabled → 404;
42. whole Health composition unavailable → 503;
43. unauthenticated → 401;
44. Site forbidden → 403;
45. site/global scope is correct;
46. existing `/admin/api/v1/health` contract remains unchanged;
47. raw errors/secrets/DB paths/internal URLs never appear;
48. no provider method is called by Health route;
49. no full DB integrity call/scan;
50. production Python 3.10 compatibility.

## Frontend

51. renders all four states;
52. request timeout/failure does not show false operational;
53. old payload can remain only with old timestamp/update-unavailable state;
54. recovery refresh works;
55. hidden-tab / generation / abort orchestration remains correct;
56. Home Live/Traffic/Activity behavior is unchanged when Health is disabled.

---

# 27. Official regression / acceptance gates

## Coder

Targeted/task/module tests only.

## Central Lab

Official full regression on exact candidate artifact.

Current known official runtime baseline before this TASK:

```text
2100 passed
30 skipped
5 deselected
STRICT_REGRESSIONS: 0
```

The new candidate must not weaken current tests.

## Production-compatible acceptance

If HOME-HEALTH-01 changes process-start composition or adds process-local authorization health evidence, rollout acceptance must include one normal first restart.

Expected post-restart semantic:

- Home Health endpoint works;
- Guest Access may initially be `unknown / no_authorization_evidence`;
- first real verified guest authorization changes Guest Access to `operational`;
- Current State/Observation/Visit/Analytics statuses remain independently correct;
- no second “warm-up restart” is required.

Production deploy itself is not part of this implementation TASK.

---

# 28. Acceptance criteria

HOME-HEALTH-01 is implementation-complete when:

1. Home Health is independently feature-flagged and repository-default disabled.
2. New Site-scoped aggregate Health endpoint exists.
3. Existing `/admin/api/v1/health` is not broken/redefined.
4. Endpoint is authenticated and Site-authorized.
5. Canonical status set is exactly operational/degraded/unavailable/unknown.
6. Initializing maps to unknown.
7. Stale periodic evidence maps to degraded.
8. Unknown never maps to operational.
9. Five v1 components are returned with explicit Site/global scope.
10. Guest Access is the only critical v1 component.
11. Aggregate rules match §12.
12. Current State reuses existing freshness semantics.
13. Observation uses existing runtime/cycle/cadence evidence.
14. Visit Lifecycle uses existing runtime health and does not treat no recent visits as failure.
15. Analytics reuses existing source-boundary health.
16. Authorization health uses bounded in-process outcome evidence and verified authorization semantics.
17. No logs are parsed.
18. No Omada request is made by Health.
19. No new monitoring DB/worker exists.
20. Component failures are isolated.
21. No raw internal errors/secrets/topology leak through API/UI.
22. Refresh is bounded and integrated into current Home orchestration.
23. Disabling Health leaves all other Home/runtime features unchanged.
24. Targeted tests pass.
25. Central Lab full regression passes on exact artifact.
26. Any required production-compatible first-restart gate passes during later Owner-controlled rollout.

---

# 29. Explicit non-goals

HOME-HEALTH-01 does NOT implement:

- Grafana replacement;
- Loki UI;
- journal viewer;
- systemd viewer/manager;
- process/PID diagnostics;
- stack traces;
- raw exception display;
- remediation buttons;
- restart;
- reconnect;
- cleanup trigger;
- retry trigger;
- repair actions;
- alerting platform;
- email/Telegram notifications;
- infrastructure monitoring for the whole network;
- switch/router/server health;
- AP/client analytics;
- RF/channel health;
- HOME-AP-24H-01;
- final Home redesign;
- Multi-Tenant/RBAC;
- a second Omada provider;
- a Health database;
- production deployment.

---

# 30. Foundation gaps identified by repository reconciliation

## Gap A — Authorization product health evidence

**Real gap.**

Technical authorization telemetry exists, but there is no canonical product-safe read snapshot.

Resolution in this TASK:

- add bounded process-local authorization health evidence;
- update only from authoritative existing outcome transitions;
- keep authorization behavior fail-open relative to Health.

No log parsing.

## Gap B — Observation product health summary

Observation already has the required runtime and persisted cycle evidence, but there is no dedicated product health DTO.

Resolution in this TASK:

- add a lightweight adapter/read method over existing runtime/cycle facts;
- no schema migration;
- no new collector.

## Gap C — Standalone Omada health

No reliable canonical provider health state exists.

Resolution:

- intentionally do not create a standalone Omada row in v1;
- surface controller impact through affected product components;
- no synthetic probe.

## Gap D — `current_state.runtime_started`

Known observability gap from previous rollout.

Resolution:

- explicitly out of scope;
- persisted successful Current State cycles already prove runtime operation;
- HOME-HEALTH-01 must use actual Current State runtime/read evidence and must not depend on this missing telemetry line.

---

# 31. Open architectural questions

No blocking architectural question remains in this DRAFT.

One semantic behavior is intentionally explicit for Owner / Tech Lead review:

> Immediately after a process restart, `Guest Access` is allowed to be `unknown` until the current process observes a real authoritative authorization outcome. HOME-HEALTH-01 does not perform a synthetic authorization probe merely to make the indicator green.

If Owner / Tech Lead rejects that behavior, a separate approved mechanism for non-destructive authorization liveness proof is required; the coder must not invent one.

---

# 32. Definition of done for DRAFT review

Owner / Tech Lead should specifically approve or reject:

- the five-component visible inventory;
- no standalone Omada/DB/Registry rows;
- four-state model;
- Guest Access as the only critical component;
- aggregate precedence;
- bounded authorization evidence foundation;
- post-restart Guest Access `unknown` semantics;
- new Site endpoint while preserving existing `/admin/api/v1/health`;
- 60-second default refresh;
- feature-flag independence.

After approval, this document may be promoted to `TASK-HOME-HEALTH-01-FINAL.md` and handed to the coder.

