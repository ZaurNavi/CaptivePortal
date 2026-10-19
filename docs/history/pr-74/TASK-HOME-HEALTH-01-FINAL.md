# TASK-HOME-HEALTH-01 — FINAL

**Project:** CaptivPortal  
**Area:** Admin Console → Home  
**Status:** FINAL — approved architectural contract for implementation  
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

The v1 visible component set is fixed and ordered:

1. `guest_access` — Guest Access — Site-scoped — critical;
2. `live_network_state` — Live Network State — Site-scoped;
3. `network_history` — Network History Collection — Site-scoped;
4. `visit_tracking` — Visit Tracking — global/application-scoped;
5. `analytics_home_data` — Analytics & Home Data — global/application-scoped.

The following are **not separate visible components** in v1:

- Omada/provider connectivity;
- raw database/storage;
- Visitor Registry;
- Pending Session Cleaner;
- Visitor Snapshot collector;
- Public Traffic;
- Admin Web process/runtime itself.

Their failures are surfaced through the product component they affect.

Guest Access health is request-driven and uses bounded process-local evidence from real authorization outcomes only. It has a configurable evidence lifetime:

```text
WEB_ADMIN_HOME_HEALTH_AUTH_EVIDENCE_MAX_AGE_SECONDS=86400
```

A verified success is `operational` only while its evidence is fresh. Evidence older than the configured maximum age becomes `unknown`, not degraded/unavailable. No synthetic authorization probe is introduced.

A required upstream subsystem in `disabled` state is `unavailable / component_disabled` when that product capability is expected by current Home Health configuration. This must not be confused with disabling Home Health itself: `WEB_ADMIN_HOME_HEALTH_ENABLED=false` keeps the Health endpoint at `404 not_found` and performs no aggregate evaluation.

System Health is explicitly independent from historical coverage/completeness. Partial or not-yet-accumulated historical data does not degrade Health by itself.

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

At FINAL finalization time:

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

## 4.5 Upstream `disabled` semantics

Canonical rule for all five v1 components:

If Home Health itself is enabled and the component's product capability is expected by the current configuration, but a **required upstream subsystem** reports `disabled`, the component is:

```text
status = unavailable
reason_code = component_disabled
```

This is not `unknown`.

For v1, the five visible product capabilities are expected when Home Health is enabled, except that optional sub-capabilities inside `analytics_home_data` are expectation-gated by their own feature flags as defined in §11.

This rule is distinct from disabling Home Health itself:

```text
WEB_ADMIN_HOME_HEALTH_ENABLED=false
→ GET /admin/api/v1/sites/<site_id>/home/health = 404 not_found
→ no HomeHealthReadService evaluation is executed
```

## 4.6 Terminal / non-terminal

All four product states are re-evaluated on every Health read and are therefore non-terminal.

`unavailable` does not mean permanent failure.

A later successful source evaluation MUST allow automatic recovery without restart of Home Health itself.

---

# 4A. HEALTH != DATA COVERAGE / DATA COMPLETENESS

System Health describes whether the **functional runtime/read/collection pipeline is currently working**.

Historical coverage/completeness describes how much trustworthy history exists for a requested range.

These are separate contracts and MUST NOT automatically drive each other.

The following are **not Health degradation by themselves**:

- `traffic_coverage_from_utc = null`;
- Home Activity Traffic = `Partial / Estimated`;
- a selected range begins before a coverage boundary;
- Last 7d / Last 30d have not naturally accumulated yet;
- a valid interval contains `0` Visits;
- there have been no recent Visits;
- a successful complete Observation cycle contains `0` clients;
- a custom range has partial historical coverage.

Therefore:

```text
partial / unknown historical coverage
≠
health degraded / unavailable
```

Health changes only when there is trustworthy evidence that the relevant runtime, read boundary, storage boundary or periodic collection path is itself degraded/unavailable/unknown according to this TASK.

Conversely, `operational` Health does not assert that every historical range is complete. A healthy pipeline may legitimately have partial historical coverage because collection began later or the selected range predates a proven coverage boundary.

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

Therefore HOME-HEALTH-01 includes the minimal authorization health evidence foundation defined in §7, including freshness expiry and canonical-Site bounding.

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

Add a **small, bounded, process-local, thread-safe, read-only health evidence object** for authorization.

This is not a monitoring subsystem.

It MUST have:

- no background thread;
- no DB;
- no log parsing;
- no remote call;
- no client list;
- no unbounded history;
- immutable/read-only snapshots;
- one bounded record only for each **canonical Site ID** accepted by the current application Site identity/configuration model.

Arbitrary ingress `site_id` values MUST NOT create tracker entries.

The tracker is constructed with a canonical Site allowlist supplied by composition from existing application configuration/identity state. Unknown/unconfigured Site IDs are rejected/ignored in a fail-open manner and cannot grow tracker state.

Preferred conceptual interface:

```python
record_verified_success(site_id, occurred_at)
record_system_failure(site_id, occurred_at, retryable, blocking)
snapshot(site_id) -> immutable AuthHealthEvidence
```

Maximum state is bounded by the canonical Site set.

## 7.2 Canonical stored evidence

Per canonical Site, store only bounded product-safe state sufficient to evaluate Health:

- latest system-relevant outcome timestamp;
- latest system-relevant outcome class:
  - `verified_success`;
  - `retryable_system_failure`;
  - `blocking_system_failure`;
- latest verified-success timestamp independently.

The tracker does not need to retain a history of outcomes.

It MUST NOT store per-client/session details.

## 7.3 Update points

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

### System failure

Record only **system-relevant** failures.

Examples:

- provider/network timeout;
- controller network error;
- token/authentication failure;
- malformed controller response;
- authorization worker/system exception.

Do not mark System Health degraded/unavailable for a client-specific condition that is not evidence of a system failure.

## 7.4 Concurrency and ordering contract

The tracker MUST be thread-safe.

All per-Site updates are serialized under tracker synchronization or equivalent atomic semantics.

An older callback MUST NOT overwrite newer evidence.

Canonical comparison:

1. compare normalized UTC `occurred_at` timestamps;
2. a greater timestamp is newer and replaces the current outcome;
3. a lower timestamp is older and MUST NOT replace the current outcome;
4. at exactly the same timestamp, use deterministic severity precedence:

```text
blocking_system_failure
    > retryable_system_failure
    > verified_success
```

This tie-break is intentionally conservative and independent of thread scheduling.

For equal timestamp + equal outcome class, the current outcome is semantically unchanged; no implementation-specific callback order may change Health status/reason.

`last_success_at` is maintained independently as the maximum timestamp of all accepted verified successes. Older success callbacks cannot move it backwards.

A future-dated/invalid evidence timestamp MUST NOT make Guest Access operational; evaluation returns product-safe `unknown` for unusable evidence rather than inventing freshness.

## 7.5 Evidence lifetime

Add:

```text
WEB_ADMIN_HOME_HEALTH_AUTH_EVIDENCE_MAX_AGE_SECONDS=86400
```

Repository default:

```text
86400   # 24 hours
```

Validation range:

```text
300..604800 seconds
# 5 minutes .. 7 days
```

Rationale:

- the default gives a useful real-world proof horizon without synthetic traffic;
- the lower bound keeps the evidence horizon meaningful relative to minute-scale Home refresh;
- the upper bound prevents configuration from turning a very old success into effectively permanent “green” health.

This threshold is **only the validity lifetime of Health evidence**.

It is NOT:

- AuthSession TTL;
- Wi-Fi access lifetime;
- Visit duration;
- authorization period;
- client retry timeout;
- portal session timeout.

At evaluation time:

```text
age_seconds = evaluated_at_utc - latest_outcome_at
```

Boundary rule is exact:

```text
age_seconds <= AUTH_EVIDENCE_MAX_AGE_SECONDS
→ evidence is fresh

age_seconds > AUTH_EVIDENCE_MAX_AGE_SECONDS
→ evidence is old
```

Exactly at the configured boundary, evidence is still fresh.

The age rule applies to the latest system-relevant outcome regardless of class so neither an old success nor an old failure can define current Health forever.

## 7.6 Status rules

For the selected canonical Site:

### `unknown`

Any of:

- current process has not observed trustworthy authorization evidence;
- latest system-relevant outcome is older than `WEB_ADMIN_HOME_HEALTH_AUTH_EVIDENCE_MAX_AGE_SECONDS`;
- evidence time is invalid/future-dated;
- subsystem is initializing and no stronger state is known.

Reason codes:

- `no_authorization_evidence`;
- `authorization_evidence_old`;
- `invalid_authorization_evidence_time`.

Old evidence expires to `unknown`, not `degraded` and not `unavailable`.

### `operational`

All are true:

- authorization subsystem is enabled/available/accepting work;
- latest system-relevant outcome is `verified_success`;
- latest outcome age is within the configured maximum.

Reason:

`latest_authorization_verified`

### `degraded`

All are true:

- authorization subsystem remains enabled/available/accepting later work;
- latest system-relevant outcome is `retryable_system_failure`;
- latest outcome evidence is fresh.

Reason:

`authorization_transient_failure`

### `unavailable`

Any positive current evidence shows:

- required authorization capability/upstream is disabled while Guest Access is expected → `component_disabled`; or
- authorization subsystem itself is not available/accepting; or
- latest fresh system-relevant outcome is a blocking/non-retryable failure that prevents authorization.

Reason examples:

- `authorization_unavailable`;
- `controller_authentication_failed`;
- `component_disabled`.

A later verified success with a newer timestamp automatically recovers Guest Access to `operational`.

No synthetic probe is permitted.

## 7.7 Secret/privacy boundary

Authorization health evidence MUST NOT store:

- MAC;
- IP;
- SSID;
- session ID;
- token;
- URL;
- raw controller response;
- exception text.

Allowed evidence is limited to product-safe fields required above: canonical Site ID, timestamps and normalized outcome class/state.

## 7.8 Fail-open requirement

Any failure inside the authorization health tracker MUST NOT change or block guest authorization behavior.

Health evidence is subordinate to the authorization path.

# 8. Current State health rules

Evaluate client and AP summaries independently using existing canonical Current State metadata.

HOME-HEALTH-01 MUST NOT create a second Current State freshness model.

## `operational`

- Current State runtime state is `active`;
- client freshness = `fresh`;
- AP freshness = `fresh`;
- both required summaries are readable.

## `degraded`

Any of:

- runtime state = `degraded`;
- client freshness = `stale`;
- AP freshness = `stale`;
- latest attempt failed/partial but a valid last complete snapshot remains available under the existing Current State contract.

Reason examples:

- `client_state_stale`;
- `ap_state_stale`;
- `latest_collection_incomplete`.

## `unavailable`

Any of:

- required Current State runtime is `disabled` while Home Health expects Live Network State → `component_disabled`;
- runtime state = `unavailable`;
- client canonical freshness = `unavailable`;
- AP canonical freshness = `unavailable`;
- required persisted source is positively unreadable/unavailable.

## `unknown`

- runtime is starting/initializing; or
- evidence cannot be evaluated safely and no stronger unavailable fact exists.

## Evidence timestamps

Use only timestamps already carried by canonical Current State successful snapshot metadata.

For the required pair `{client, ap}`:

```text
evidence_at
= least-current canonical evidence timestamp
= min(client.snapshot.observed_at,
      ap.snapshot.observed_at)
```

when both exist; otherwise nullable according to available evidence. This timestamp is informational and follows the same canonical evidence basis already used by Current State freshness; HOME-HEALTH-01 does not recompute age from it.

```text
last_success_at
= min(latest successful complete client capture_finished_at,
      latest successful complete AP capture_finished_at)
```

This is the latest point through which **both required sides** have successful complete evidence.

Do not substitute `evaluated_at`/`now` for missing source timestamps.

Existing Current State freshness calculations remain authoritative, including their configured fresh/stale/unavailable thresholds and `CurrentSnapshotMeta` reasons.

# 9. Observation health rules

Observation is periodic, therefore staleness matters.

Use:

- `ObservationFoundationRuntime.state`;
- enabled worker running/degraded state;
- persisted `observation_cycles` facts for the selected Site;
- existing Observation cadence and bounded request/execution configuration.

For v1 staleness, required periodic collector kinds are:

```text
client      if observation_client_enabled == true
ap_dynamic  if observation_ap_enabled == true
```

`ap_config` is not a separate freshness requirement for this Home component because it is the slow AP configuration snapshot stream, not the dynamic Home/history evidence cadence. However, a positive Observation runtime degradation caused by AP config/integrity/cleanup remains valid degradation because the Observation runtime itself reports it.

## Canonical cycle timestamps

For any completed Observation cycle, canonical cycle evidence time is:

```text
observation_cycles.finished_at
```

For successful freshness evidence, the cycle MUST satisfy:

```text
state = completed
result = success
complete = 1
finished_at IS NOT NULL
```

A successful complete cycle with `items_seen = 0` / `items_stored = 0` is valid success. Empty inventory is not degradation.

## Deterministic staleness formula

Let:

```text
N = len(ObservationConfig.site_ids)
```

because current workers process configured Sites sequentially.

### Client collector

Current implementation has no separate client-cycle max-duration setting; it does have bounded pages and per-request timeout. Therefore this TASK derives the allowed recurrence budget only from existing configured bounds and does not invent a fixed grace.

```text
client_cycle_budget_seconds
= N
  * client_max_pages
  * request_timeout_seconds

client_stale_after
= latest_successful_client_finished_at
  + client_interval_seconds
  + client_cycle_budget_seconds
```

At evaluation:

```text
evaluated_at <= client_stale_after
→ client success evidence is not stale

evaluated_at > client_stale_after
→ stale_evidence
```

### AP dynamic collector

AP dynamic and AP config work share one AP worker thread. A slow scheduled config cycle can legitimately delay the next dynamic cycle, so the formula MUST include the existing bounded AP config execution window rather than inventing a magic grace.

```text
ap_dynamic_round_budget_seconds
= N * ap_cycle_max_duration_seconds

ap_config_round_budget_seconds
= N * ap_config_cycle_max_duration_seconds

ap_wait_budget_seconds
= max(ap_interval_seconds,
      ap_config_round_budget_seconds)

ap_dynamic_stale_after
= latest_successful_ap_dynamic_finished_at
  + ap_wait_budget_seconds
  + ap_dynamic_round_budget_seconds
```

At evaluation:

```text
evaluated_at <= ap_dynamic_stale_after
→ AP dynamic success evidence is not stale

evaluated_at > ap_dynamic_stale_after
→ stale_evidence
```

No extra hard-coded 5/10-minute stale threshold or arbitrary grace is allowed.

If future implementation changes Observation scheduler/cycle bounds, Health formula must be updated with that approved architecture; coder must not silently preserve stale assumptions.

## `operational`

All are true:

- Observation runtime = `active`;
- every enabled required collector worker is running;
- latest relevant required cycle does not itself prove a failure/partial condition;
- latest successful complete evidence for every required collector kind is within the formula above.

## `degraded`

Any of:

- runtime = `degraded`;
- latest relevant Site cycle is `partial`/`failed` while runtime continues;
- latest successful complete required evidence is past its derived stale deadline;
- integrity/cleanup state currently degrades Observation runtime.

Stale reason:

`stale_evidence`

## `unavailable`

Positive evidence only:

- required Observation subsystem is `disabled` while Network History is expected → `component_disabled`;
- runtime = `unavailable`;
- required worker is not running outside normal startup/shutdown semantics;
- source storage is positively unavailable/unreadable.

Do not escalate to unavailable solely because there are zero clients/AP rows in a successful complete cycle.

## `unknown`

- startup before first required successful evidence; or
- source cannot be safely classified and there is no positive unavailable fact.

## Evidence timestamps

For each required enabled collector kind, obtain the latest completed cycle `finished_at` and latest successful-complete cycle `finished_at`.

Component timestamps are conservative across required kinds:

```text
evidence_at
= min(latest completed required-kind finished_at values)
```

when all required kinds have such evidence; otherwise nullable/available only to the extent supported.

```text
last_success_at
= min(latest successful-complete required-kind finished_at values)
```

when all required kinds have successful evidence; otherwise nullable.

Do not fabricate `now` for either field.

# 10. Visit Lifecycle health rules

Visit Lifecycle is event-driven and its runtime already integrates webhook-reader/reconciliation health.

## `operational`

`VisitLifecycleRuntime.state == "active"` and `available == True`.

## `degraded`

`VisitLifecycleRuntime.state == "degraded"`.

This includes reader/reconciliation degradation already represented by the runtime.

## `unavailable`

- required Visit Lifecycle runtime is `disabled` while Home Health expects Visit Tracking → `component_disabled`; or
- runtime is `unavailable` / not available.

## `unknown`

Runtime is `starting` or state cannot be safely determined.

## Freshness / no-activity rule

Do not infer failure from “no recent Visit”.

No guest activity is valid. `0` Visits and long periods without a new Visit are not health degradation by themselves.

If the existing canonical `visit_reader_state.updated_at` progress timestamp is available through the approved read boundary, it may be used as `evidence_at`. Otherwise `evidence_at` is `null`.

`last_success_at` is `null` in v1 unless an existing canonical Visit runtime/read success timestamp is available without creating new state.

Do not use the timestamp of the most recent Visit as a health liveness signal and do not fabricate `now`.

# 11. Analytics & Home Data health rules

Use existing Analytics runtime/source-boundary health.

`AnalyticsRuntime.live_health_payload()` is allowed because it:

- opens existing source read boundaries;
- checks schema version;
- checks `PRAGMA query_only`;
- does not scan domain rows;
- does not write;
- does not call Omada.

## Core Analytics

Core source-boundary availability is evaluated independently of historical data coverage.

A source-boundary failure can make the component unavailable even when historical UI values were previously available.

## Optional Home capability enablement

Missing optional Home read services are faults **only when the corresponding product capability is enabled/expected by current configuration**.

Rules:

```text
WEB_ADMIN_HOME_TRAFFIC_ENABLED=true
AND current_traffic_service missing/unavailable
→ degraded
```

```text
WEB_ADMIN_HOME_TRAFFIC_ENABLED=false
→ absence/non-use of current_traffic_service is not a fault
```

```text
WEB_ADMIN_HOME_ACTIVITY_ENABLED=true
AND home_activity_service missing/unavailable
→ degraded
```

```text
WEB_ADMIN_HOME_ACTIVITY_ENABLED=false
→ absence/non-use of home_activity_service is not a fault
```

Intentional feature disablement MUST NOT create false Analytics degradation.

This exception applies to these optional sub-capabilities only. A required core Analytics runtime/source boundary that is disabled while the Analytics & Home Data component is expected uses the canonical `unavailable / component_disabled` rule.

## `operational`

- Analytics runtime = `active`;
- all required core source boundaries are available;
- required core Analytics services exist;
- every **enabled/expected** optional Home service is present/available.

## `degraded`

Core Analytics remains active/readable, but an enabled/expected optional Home service is missing/unavailable.

Reason examples:

- `current_traffic_service_unavailable`;
- `home_activity_service_unavailable`.

Do not degrade because a consciously disabled optional feature has no service.

## `unavailable`

- required Analytics runtime is `disabled` while component is expected → `component_disabled`; or
- Analytics runtime = `unavailable`; or
- one or more required core source boundaries fail open/schema/query-only validation.

## `unknown`

Health evaluation itself fails and no stronger state is available.

## Evidence timestamps

`evidence_at` is the real timestamp at which the lightweight Analytics source-boundary evaluation represented by this response was executed.

This is valid evaluation evidence, not a fabricated domain-data timestamp.

`last_success_at` MUST be `null` unless an existing canonical persisted/runtime source provides a trustworthy last-success timestamp. HOME-HEALTH-01 MUST NOT introduce a new cache/history solely to populate this field.

## Scope

`global`.

A source-boundary failure can affect all Sites; the API must not pretend it is Site-local.

# 12. Aggregate System Health

Aggregate health is not generic `worst(status)`.

Each component has:

```text
criticality = critical | feature
```

In v1:

- `guest_access` = `critical`;
- all other visible components = `feature`.

Aggregation order is deterministic:

### 1. `unavailable`

If any `critical` component is `unavailable`.

For v1 this means Guest Access is positively unavailable.

### 2. `degraded`

If no critical component is unavailable, but any of:

- a critical component is `degraded`;
- a feature component is `degraded`;
- a feature component is `unavailable`.

A Home/analytics/history failure therefore degrades CaptivPortal product health but does not claim the core captive access service is completely down.

### 3. `unknown`

If no known degradation/unavailability exists, but at least one included component is `unknown`.

This prevents UNKNOWN from becoming false HEALTHY.

Important Guest Access age example:

```text
guest_access = unknown
reason_code = authorization_evidence_old
all feature components = operational
→ aggregate = unknown
```

### 4. `operational`

Only if every included component is `operational`.

Canonical examples:

```text
guest_access = degraded
→ aggregate = degraded
```

```text
guest_access = unavailable
→ aggregate = unavailable
```

```text
guest_access = operational
one feature component = unavailable
→ aggregate = degraded
```

```text
guest_access = operational
all feature components = operational
→ aggregate = operational
```

# 13. Source-of-truth matrix

| Component | Scope | Source | Freshness / validity | Standalone remote probe |
|---|---|---|---|---|
| Guest Access | Site | bounded canonical-Site auth outcome evidence over existing verified auth transitions | `AUTH_EVIDENCE_MAX_AGE_SECONDS`; old → unknown | Forbidden |
| Live Network State | Site | Current State runtime + canonical read-service metadata | Reuse existing Current State freshness | Forbidden |
| Network History Collection | Site | Observation runtime + persisted cycle evidence | Exact formula derived from Observation cadence/bounds in §9 | Forbidden |
| Visit Tracking | Global | Visit Lifecycle runtime / reader health | No Visit-activity age threshold | Forbidden |
| Analytics & Home Data | Global | Analytics runtime + source-boundary checks + enabled-feature expectations | Source-boundary evaluation, not historical coverage | Forbidden |

No row in this matrix authorizes a new Omada client, log reader, Health DB or Health worker.

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

One aggregate endpoint is required.

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

Every component object includes:

- `id`;
- `label`;
- `status`;
- `reason_code`;
- `message`;
- `criticality`;
- `scope`;
- `evidence_at` nullable;
- `last_success_at` nullable.

Optional product-safe metadata is allowed only when it has Home user value and is explicitly bounded/allowlisted.

## 15.6 Canonical timestamp semantics

| Component | `evidence_at` | `last_success_at` |
|---|---|---|
| `guest_access` | timestamp of latest accepted system-relevant auth outcome, even if it has aged to `unknown`; null if none | maximum accepted timestamp of a verified `authStatus == 2` authorization success; may remain older than current outcome |
| `live_network_state` | least-current canonical `CurrentSnapshotMeta.observed_at` across required client/AP summaries; this is the same evidence basis used by existing freshness | latest point through which both required client/AP sides have successful complete snapshot evidence; conservative minimum of their `capture_finished_at` values |
| `network_history` | conservative minimum of latest completed required-kind Observation `finished_at` values | conservative minimum of latest successful-complete required-kind Observation `finished_at` values |
| `visit_tracking` | canonical `visit_reader_state.updated_at` only if available through approved read boundary and trustworthy; otherwise null | null unless an existing canonical Visit runtime/read success timestamp exists |
| `analytics_home_data` | timestamp of the actual lightweight source-boundary evaluation performed for this response | null unless an existing canonical source provides a trustworthy last-success timestamp |

Global rules:

- never substitute `evaluated_at`/`now` for a missing source timestamp except `analytics_home_data.evidence_at`, where the timestamp explicitly represents the real evaluation just performed;
- never use “last domain row” as liveness unless this TASK explicitly says so;
- no fake timestamps solely to satisfy schema presence.

## 15.7 Deterministic component ordering

`components` MUST be returned in exactly this API v1 order:

```text
1. guest_access
2. live_network_state
3. network_history
4. visit_tracking
5. analytics_home_data
```

Do not rely on:

- incidental dict insertion order;
- alphabetical sort;
- implementation-specific collection order.

This order is part of the frontend/API contract.

## 15.8 HTTP behavior and the 503 boundary

### Feature disabled

```text
WEB_ADMIN_HOME_HEALTH_ENABLED=false
→ 404 not_found
→ no aggregate evaluation
```

### Component failure

Ordinary component failures MUST return HTTP `200` with product component status.

Examples that MUST remain HTTP 200:

- Current State storage/read failure;
- Observation health adapter failure;
- Visit runtime unavailable;
- Analytics source boundary unavailable;
- Guest Access tracker read failure;
- one or several component evaluator exceptions.

The evaluator exception is isolated to that component and normalized, usually to `unknown / health_read_failed` unless positive evidence supports `unavailable`.

No component reader failure may produce a 500 for Home Health.

### Whole-feature failure

`503 source_unavailable` is allowed **only** when the Home Health layer cannot execute the evaluation contract at all, for example:

- `HomeHealthReadService` cannot be constructed;
- Health configuration is invalid to the point that no evaluation contract exists;
- required Home Health composition object is wholly absent.

Rule:

```text
component failure
→ HTTP 200 + component/aggregate status

whole Home Health service failure
→ HTTP 503 source_unavailable
```

Existing Admin authentication/Site errors remain unchanged:

- unauthenticated → `401`;
- Site forbidden → `403`;
- invalid Site/request → existing Admin behavior.

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
authorization_evidence_old
invalid_authorization_evidence_time
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
WEB_ADMIN_HOME_HEALTH_AUTH_EVIDENCE_MAX_AGE_SECONDS=86400
```

Repository defaults:

```text
WEB_ADMIN_HOME_HEALTH_ENABLED=false
WEB_ADMIN_HOME_HEALTH_REFRESH_SECONDS=60
WEB_ADMIN_HOME_HEALTH_REQUEST_TIMEOUT_SECONDS=20
WEB_ADMIN_HOME_HEALTH_AUTH_EVIDENCE_MAX_AGE_SECONDS=86400
```

Validation:

```text
WEB_ADMIN_HOME_HEALTH_REFRESH_SECONDS
60..300

WEB_ADMIN_HOME_HEALTH_REQUEST_TIMEOUT_SECONDS
5..60
and > WEB_ADMIN_MAX_QUERY_DURATION_SECONDS

WEB_ADMIN_HOME_HEALTH_AUTH_EVIDENCE_MAX_AGE_SECONDS
300..604800
```

The authorization evidence age setting is independent from all auth/session/Visit lifetimes.

Repository default = Health disabled.

Production activation is separate and Owner-controlled.

Health configuration parsing MUST be fail-open relative to the rest of Admin Web.

If Health config is invalid:

- Admin Web remains usable;
- Home Live remains independent;
- Home Traffic remains independent;
- Home Activity remains independent;
- Home Health whole-feature composition may be `unavailable` and its endpoint may return `503 source_unavailable` because no valid Health evaluation contract exists.

Do not require Home Traffic or Home Activity to be enabled merely to enable Home Health.

Their own enablement only determines whether their optional Analytics services are expected for `analytics_home_data` health.

No production values are written by this TASK.

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
- no historical range/coverage aggregation;
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

## Health model / aggregation

1. all components operational → aggregate operational;
2. critical Guest Access unavailable → aggregate unavailable;
3. critical Guest Access degraded → aggregate degraded;
4. feature component unavailable → aggregate degraded;
5. one unknown with no known fault → aggregate unknown;
6. known degradation + another unknown → aggregate degraded;
7. unknown never becomes operational;
8. Guest Access `unknown / authorization_evidence_old` + all features operational → aggregate unknown;
9. Guest Access operational + one feature unavailable → aggregate degraded.

## Guest Access evidence / age / ordering

10. no current-process auth evidence → unknown;
11. verified success younger than max age → operational;
12. verified success exactly at configured max-age boundary → operational;
13. verified success older than max age → unknown / `authorization_evidence_old`;
14. stale success + no later failure → unknown, not degraded;
15. stale old failure also expires to unknown rather than defining Health forever;
16. POST success without verification does not produce operational;
17. fresh retryable system failure → degraded;
18. fresh positive blocking/non-retryable system failure → unavailable;
19. newer retryable failure overrides older success → degraded;
20. newer verified success recovers from prior failure;
21. older callback cannot overwrite newer tracker outcome;
22. equal-timestamp ordering follows blocking > retryable > success;
23. `last_success_at` never moves backwards;
24. unknown/unconfigured Site cannot create/grow tracker state;
25. tracker snapshot is immutable/read-only;
26. concurrent callbacks preserve deterministic timestamp ordering;
27. client-specific non-system outcome does not falsely mark system unavailable;
28. tracker failure does not affect guest authorization;
29. no MAC/IP/SSID/session/token stored in health evidence.

## Disabled semantics

30. expected upstream `disabled` → component `unavailable / component_disabled`;
31. Home Health feature disabled → 404 and HomeHealthReadService evaluation is not called;
32. intentionally disabled Home Traffic does not degrade Analytics because `current_traffic_service` is absent;
33. intentionally disabled Home Activity does not degrade Analytics because `home_activity_service` is absent.

## Current State

34. client fresh + AP fresh → operational;
35. one stale → degraded;
36. latest incomplete attempt with last complete snapshot → degraded under current Current State contract;
37. one required side unavailable → component unavailable;
38. Current State disabled while expected → unavailable/component_disabled;
39. no complete evidence/startup → unknown or unavailable strictly according to existing Current State state/freshness contract;
40. Current State thresholds are reused, not duplicated;
41. evidence/last-success timestamps use canonical source values, never fake now.

## Observation

42. active workers + complete current cycles → operational;
43. runtime degraded → degraded;
44. partial/failed latest cycle → degraded;
45. client stale boundary formula: exactly at deadline not stale;
46. client one instant beyond deadline → degraded/stale;
47. AP dynamic stale boundary formula: exactly at deadline not stale;
48. AP one instant beyond deadline → degraded/stale;
49. Site-count multiplier is applied deterministically;
50. AP config bounded execution window is included in AP dynamic stale allowance;
51. runtime/required worker unavailable → unavailable;
52. Observation disabled while expected → unavailable/component_disabled;
53. successful empty Observation cycle remains valid operational evidence;
54. empty client inventory is not degradation;
55. startup before first required success → unknown;
56. no arbitrary hard-coded stale timeout is used.

## Visit Lifecycle

57. active → operational;
58. degraded reader/reconciler → degraded;
59. unavailable → unavailable;
60. disabled while expected → unavailable/component_disabled;
61. no recent Visits does not affect Visit Tracking health;
62. `0` Visits does not affect Visit Tracking health;
63. evidence timestamp is canonical reader progress only if available, otherwise null.

## Analytics / feature enablement / coverage independence

64. all required core source boundaries valid → operational;
65. schema/query-only/open failure → unavailable;
66. Analytics disabled while expected → unavailable/component_disabled;
67. Home Traffic enabled + missing current traffic service → degraded;
68. Home Traffic disabled + missing current traffic service → not degraded for that reason;
69. Home Activity enabled + missing Home Activity service → degraded;
70. Home Activity disabled + missing Home Activity service → not degraded for that reason;
71. Traffic `Partial / Estimated` with healthy Analytics pipeline does not degrade Health;
72. `traffic_coverage_from_utc = null` does not by itself degrade Health;
73. selected range before coverage boundary does not affect Analytics Health;
74. Last 7d/30d not accumulated does not affect Health;
75. custom partial coverage does not affect Health;
76. no domain-row scan is required;
77. Analytics `evidence_at` is actual lightweight evaluation time; `last_success_at` is null absent canonical source.

## Isolation / HTTP / API / security

78. one component evaluator raises → others still return;
79. component source failure → HTTP 200;
80. Current State storage read failure → HTTP 200 + component state;
81. Observation adapter failure → HTTP 200 + component state;
82. Visit unavailable → HTTP 200 + component state;
83. Analytics source unavailable → HTTP 200 + component state;
84. Guest tracker read failure → HTTP 200 + component state;
85. whole `HomeHealthReadService` unavailable/unconstructable → 503 source_unavailable;
86. no component reader exception produces HTTP 500;
87. route disabled → 404;
88. unauthenticated → 401;
89. Site forbidden → 403;
90. site/global scope is correct;
91. exact five-component order is stable:
    `guest_access`, `live_network_state`, `network_history`, `visit_tracking`, `analytics_home_data`;
92. existing `/admin/api/v1/health` contract remains unchanged;
93. raw errors/secrets/DB paths/internal URLs never appear;
94. no provider method is called by Health route;
95. no full DB integrity call/scan;
96. production Python 3.10 compatibility.

## Frontend

97. renders all four states;
98. request timeout/failure does not show false operational;
99. old payload can remain only with old timestamp/update-unavailable state;
100. recovery refresh works;
101. hidden-tab / generation / abort orchestration remains correct;
102. Home Live/Traffic/Activity behavior is unchanged when Health is disabled.

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
5. Canonical status set is exactly `operational / degraded / unavailable / unknown`.
6. Initializing maps to unknown.
7. Stale periodic evidence maps to degraded.
8. UNKNOWN never maps to operational.
9. Required upstream `disabled` maps to unavailable/component_disabled when capability is expected.
10. Home Health itself disabled returns 404 without evaluation.
11. Exactly five v1 components are returned in the fixed order: Guest Access, Live Network State, Network History, Visit Tracking, Analytics & Home Data.
12. Site/global scope is explicit for every component.
13. Guest Access is the only critical component.
14. Aggregate rules match §12, including old Guest Access evidence → aggregate unknown when no other fault exists.
15. Guest Access tracker is bounded to canonical Sites, thread-safe and snapshot-immutable.
16. Older callbacks cannot overwrite newer Guest Access evidence.
17. Equal-timestamp Guest Access outcomes use deterministic blocking > retryable > success precedence.
18. Guest Access verified success is operational only while evidence age is `<= WEB_ADMIN_HOME_HEALTH_AUTH_EVIDENCE_MAX_AGE_SECONDS`.
19. Old authorization evidence becomes unknown/authorization_evidence_old.
20. No synthetic authorization probe exists.
21. Current State reuses existing freshness semantics and timestamps.
22. Observation uses persisted `finished_at` and exact derived cadence/budget formulas from §9.
23. Successful empty Observation cycle is valid success.
24. Visit Lifecycle uses existing runtime health and does not treat no recent Visits/zero Visits as failure.
25. Analytics reuses existing source-boundary health.
26. Missing Current Traffic/Home Activity services degrade Analytics only when those capabilities are enabled/expected.
27. Historical coverage/completeness does not alter System Health without separate runtime/source failure.
28. `traffic_coverage_from_utc=null`, Partial/Estimated Traffic, pre-coverage ranges and not-yet-accumulated 7d/30d are not Health faults by themselves.
29. API `evidence_at` / `last_success_at` follow the per-component table and never fabricate timestamps.
30. No logs are parsed.
31. No Omada request is made by Health.
32. No new monitoring DB/worker exists.
33. Component failures are isolated and return HTTP 200 with component status.
34. `503 source_unavailable` is reserved for whole Home Health composition/read-service failure.
35. No component reader failure returns 500.
36. No raw internal errors/secrets/topology leak through API/UI.
37. Refresh is bounded and integrated into current Home orchestration.
38. Disabling Health leaves all other Home/runtime features unchanged.
39. Targeted tests pass.
40. Central Lab full regression passes on exact artifact.
41. Any required production-compatible first-restart gate passes during later Owner-controlled rollout.

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

- add bounded canonical-Site process-local authorization health evidence;
- add configurable evidence lifetime with old evidence → unknown;
- make tracker thread-safe with deterministic timestamp/tie ordering;
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

# 31. Architectural questions — closed

No blocking architectural questions remain after Owner / Tech Lead review.

The following previously reviewable behaviors are now FINAL:

- after process restart, Guest Access is `unknown` until real current-process authorization evidence exists;
- no synthetic authorization probe is permitted;
- verified Guest Access success expires as Health evidence after the configured age and then becomes `unknown`;
- default auth Health evidence age is 24 hours;
- canonical Site bounding and deterministic concurrent ordering are mandatory;
- partial historical coverage does not degrade System Health;
- required disabled upstream subsystem is unavailable/component_disabled;
- optional Home Traffic/Home Activity services affect Analytics Health only when their capabilities are enabled/expected;
- component failures are HTTP 200; 503 is whole-feature failure only.

# 32. Final implementation handoff

This document is FINAL and ready for coder implementation against exact baseline:

```text
origin/main@7307cb0f1a5da6d452f5d90e5303d34127ebc916
```

Current runtime code checkpoint remains:

```text
53f617b3ac0155d0d647e58e98309927f9a4d318
```

The repository-head difference remains documentation-only at finalization time.

Coder MUST implement only this approved scope, run targeted tests, and return a handoff for Tech Lead review.

Official full regression belongs to Central Lab.

Merge, production activation, restart and deployment remain Owner-controlled and are not authorized by this TASK.

