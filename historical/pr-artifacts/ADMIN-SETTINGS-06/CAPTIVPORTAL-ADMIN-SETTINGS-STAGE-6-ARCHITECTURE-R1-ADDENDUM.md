# CAPTIVPORTAL ADMIN SETTINGS
## STAGE 6 — ADMIN PRODUCT BEHAVIOR / FEATURE CONTROLS
### ARCHITECTURE R1 ADDENDUM
### Precedence over Architecture Contract v0.1 where explicitly stated

**Project:** CaptivPortal  
**Role:** Architect  
**Baseline:** `main@701ce630b595a87e9350b826a06ee02eaebc7f9e`  
**TREE:** `59425257b1b9ddd557113da158c88d58bfe06bfc`  
**Parent:** `STAGE 6 — ARCHITECTURE CONTRACT v0.1`  
**Status:** `READY FOR TECH LEAD R1 REVIEW`  
**Implementation TASK:** `HOLD`  
**Coder:** `HOLD`  
**Schema change:** `NO`  
**Production change:** `NO`

---

# 0. PRECEDENCE

This Addendum closes exactly:

```text
TL-S6-P1-01
TL-S6-P1-02
TL-S6-P1-03
TL-S6-P1-04
TL-S6-P1-05
TL-S6-P1-06
```

All v0.1 decisions not explicitly changed here remain unchanged. Where this Addendum conflicts with v0.1, this Addendum has precedence.

---

# 1. TL-S6-P1-01 — SINGLE STARTUP FEATURE PLAN / ANALYTICS INJECTION

## 1.1 Exact owner

The one startup `AdminFeaturePlanV1` is owned by:

```text
bootstrap_settings_control(...)
```

`SettingsBootstrapResult` gains exactly one runtime-plan field:

```text
feature_plan
```

No other startup owner may construct a second plan for the same startup snapshot.

## 1.2 One-snapshot / one-plan invariant

```text
one ResolvedSettingsSnapshot(G)
        ↓
exactly one AdminFeaturePlanV1(G)
        ↓
same object identity consumed by every Stage-6 runtime consumer
```

When Settings control is disabled:

```text
G = null
```

and the deployment/base `ResolvedSettingsSnapshot(null)` still produces exactly one runtime plan. Settings UI being disabled does not remove Feature-plan ownership from runtime composition.

## 1.3 Exact startup sequence

```text
1. base_settings = get_settings()
2. explicit_environment_names = frozenset(os.environ)
3. bootstrap_settings_control(...)
   → runtime_settings
   → resolved_snapshot
   → feature_plan
   → existing Settings services/context
   → existing secret resolution / activation service where applicable
4. settings = settings_bootstrap.runtime_settings
   feature_plan = settings_bootstrap.feature_plan
5. existing Controller composition
6. existing create_app / Portal composition
7. existing Observation / Current State / other runtime composition
8. _configure_analytics(..., settings, feature_plan)
9. _configure_admin_web(..., settings, feature_plan, ...)
10. deferred Home AP-24H telemetry remains outside Stage-6 ownership
11. SettingsActivationService.adopt(
        runtime_settings,
        feature_plan,
        analytics_runtime,
        admin_runtime
    )
12. existing post-adoption workers start
```

Current lifecycle ordering is preserved:

```text
Analytics BEFORE Admin Web
```

but Analytics no longer selects Stage-6 behavior from raw Feature booleans.

## 1.4 Construction source

The startup plan is constructed exactly once from:

```text
settings_bootstrap.resolved_snapshot
```

It is not reconstructed from `os.environ`, Flask state, Admin config, Analytics config, a Store reread or a configured-head reread.

```text
feature_plan.generation_id == resolved_snapshot.generation_id
```

Mutation validation may construct a transient candidate graph for a different candidate snapshot; that object is never attached to the running runtime and does not violate the startup invariant.

## 1.5 Analytics injection

`create_analytics_runtime` receives the exact startup object:

```text
feature_plan=AdminFeaturePlanV1
```

If an Analytics runtime object is returned:

```text
analytics_runtime.feature_plan is feature_plan
```

must hold.

## 1.6 traffic.projection_read

Historical source selection is controlled only by:

```text
feature_plan.effective_state("traffic.projection_read")
```

Exact behavior:

```text
enabled
→ historical_source_mode = projection
→ TrafficProjectionReadService boundary

disabled
→ historical_source_mode = base
→ existing non-projection gateway

dormant_parent_disabled
→ historical_source_mode = base
→ existing non-projection gateway

runtime_unavailable
→ no projection-enabled claim
→ projection read config is not used
```

No raw `WEB_ADMIN_TRAFFIC_PROJECTION_READ_ENABLED`, `projection_read_enabled(settings)` or environment lookup may bypass the plan.

If Projection Read is dormant, Analytics MUST NOT validate, open, probe or instantiate projection read configuration/service. It uses the existing base historical gateway.

Analytics exposes safe structural:

```text
historical_source_mode = base | projection
```

This is source selection, not source health. `historical_source_mode=projection` may coexist with runtime source unavailability; raw fallback remains forbidden.

## 1.7 Admin / routes / templates / Health

`create_admin_web_runtime(..., feature_plan=feature_plan)` retains:

```text
admin_runtime.feature_plan is feature_plan
```

Routes and templates consume the plan through `AdminWebRuntime`; Jinja/JS must not rebuild the graph.

Any retained admitted `AdminWebConfig.*_enabled` compatibility field must represent Feature-plan effective eligibility, not an independently parsed raw child value.

Home Health receives the exact same plan object. Expectations are:

```text
home.traffic effective state == enabled
→ Current Traffic service is expected

otherwise
→ not expected solely as optional Home product
```

and:

```text
home.activity effective state == enabled
→ Home Activity service is expected

otherwise
→ not expected solely as optional Home product
```

## 1.8 SettingsActivationService

`SettingsActivationService` is constructed with the same plan reference. Adoption verifies:

```text
runtime_settings is snapshot.values
submitted feature_plan is self.feature_plan
feature_plan.generation_id == snapshot.generation_id
```

If existing Analytics/Admin runtime objects consumed another plan, that is positive structural evidence:

```text
features_configuration_adoption_failed
```

Absence/silence alone does not infer that failure.

Stage-6 composition checks use graph-enabled state, never raw child=true. Exact positive checks:

```text
home.activity == enabled
→ Home Activity config exists/enabled

home.health == enabled
→ Home Health config exists/enabled

devices.list_context == enabled
→ Device List Context config exists/enabled
→ cursor codec exists

traffic.projection_read == enabled
→ if Analytics runtime exists, historical_source_mode=projection

traffic.projection_read disabled/dormant
→ if Analytics runtime exists, historical_source_mode=base
```

Runtime source/service health is not part of activation attestation.

Deferred `WEB_ADMIN_HOME_AP_24H_ENABLED` is not part of `AdminFeaturePlanV1`; its existing handling remains outside Stage 6.

```text
TL-S6-P1-01 = CLOSED
```

---

# 2. TL-S6-P1-02 — EXACT VALIDATION BOUNDARY

Stage 6 has exactly three validation classes:

```text
A. REGISTERED_SCALAR_PRIMITIVE
B. NON_REGISTERED_SUPPORTING_CONFIGURATION
C. SEMANTIC_PREREQUISITE
```

## 2.1 Registered scalars

Registered values are primitive-validated regardless of consumer/product state.

Existing General integer definitions remain unconditional:

```text
selected configured value = integer in bounds
base value = integer in bounds
```

All 17 Feature definitions remain durable `value_type=string` but accept exactly:

```text
"true"
"false"
```

Feature scalar primitive validation is unconditional, including disabled/dormant Features. Persisted Feature overrides are always canonical strings; public API projects booleans.

Stage 6 chooses the strict Feature-base rule:

```text
Feature base/deployment scalar must also be primitive-valid
when a persisted Feature override shadows it.
```

Thus an invalid Feature environment base plus a valid persisted Feature override is still invalid. This is required because Feature `base_value` is a normalized boolean and clear-override fallback must be deterministic. Existing Controller/Portal string-resolution behavior is unchanged.

## 2.2 Exact matrix

### WEB_ADMIN_HOME_ACTIVITY_REFRESH_SECONDS

```text
class = REGISTERED_SCALAR_PRIMITIVE / General
validation = ALWAYS
integer 60..300
```

### Activity supporting tuning

```text
WEB_ADMIN_HOME_ACTIVITY_REQUEST_TIMEOUT_SECONDS
WEB_ADMIN_HOME_ACTIVITY_TRAFFIC_FRESH_MAX_AGE_SECONDS
WEB_ADMIN_HOME_ACTIVITY_TRAFFIC_STALE_MAX_AGE_SECONDS
```

```text
class = NON_REGISTERED_SUPPORTING_CONFIGURATION
validate only when configured home.activity state = enabled
```

Exact rules:

```text
request timeout 5..60
fresh 1..3600
stale 2..7200
stale > fresh
request timeout > WEB_ADMIN_MAX_QUERY_DURATION_SECONDS
```

### WEB_ADMIN_HOME_ACTIVITY_SITE_CONTEXT_JSON

```text
class = NON_REGISTERED_SUPPORTING_CONFIGURATION + SEMANTIC_PREREQUISITE
validate only when configured home.activity state = enabled
```

Existing Activity semantics remain authoritative: strict object/keys, valid Site IDs/timezone/coverage, no duplicate keys, non-empty enabled context, no future coverage, and Site scope inside Admin + Current State scope.

### Current State prerequisite for Activity

```text
CURRENT_STATE_ENABLED
CURRENT_STATE_SITE_IDS
CURRENT_STATE_CLIENT_SSIDS_JSON
```

```text
class = SEMANTIC_PREREQUISITE of home.activity
validate only when configured home.activity state = enabled
```

Required:

```text
CURRENT_STATE_ENABLED=true
valid non-empty Current State Site scope
valid non-empty guest SSID scope
Activity context subset of Admin + Current State Sites
```

No Current State live-health probe.

### WEB_ADMIN_HOME_HEALTH_REFRESH_SECONDS

```text
class = REGISTERED_SCALAR_PRIMITIVE / General
validation = ALWAYS
integer 60..300
```

### Health tuning

```text
WEB_ADMIN_HOME_HEALTH_REQUEST_TIMEOUT_SECONDS
WEB_ADMIN_HOME_HEALTH_AUTH_EVIDENCE_MAX_AGE_SECONDS
```

```text
class = NON_REGISTERED_SUPPORTING_CONFIGURATION
validate only when configured home.health state = enabled
```

Rules:

```text
request timeout 5..60
request timeout > WEB_ADMIN_MAX_QUERY_DURATION_SECONDS
auth evidence age 300..604800
```

### Device List cursor secret

```text
WEB_ADMIN_DEVICE_LIST_CONTEXT_CURSOR_SECRET
```

```text
class = NON_REGISTERED_SUPPORTING_CONFIGURATION + SEMANTIC_PREREQUISITE
validate only when configured devices.list_context state = enabled
```

Exact existing structure:

```text
64 hex chars
→ exactly 32 bytes
```

It remains non-writable and must never be exposed in error/audit/log.

### Projection read config

```text
TRAFFIC_PROJECTION_DB_PATH
OBSERVATION_DB_PATH
OBSERVATION_SITE_IDS
```

```text
class = NON_REGISTERED_SUPPORTING_CONFIGURATION + SEMANTIC_PREREQUISITE
validate only when configured traffic.projection_read state = enabled
```

Rules:

```text
projection DB path = non-empty absolute path
Observation DB path = non-empty absolute path
resolved paths distinct
Observation Site scope = non-empty valid Site set
```

Not required by Stage-6 read consumer:

```text
TRAFFIC_PROJECTION_ENABLED
TRAFFIC_PROJECTION_WRITER_LOCK_PATH
writer process health
projection DB live readiness
```

### Home Live tuning

Unconditional registered:

```text
WEB_ADMIN_HOME_LIVE_REFRESH_SECONDS = integer 60..300
WEB_ADMIN_CURRENT_STATE_PAGE_SIZE = integer 1..250
```

Graph-enabled only:

```text
WEB_ADMIN_HOME_LIVE_REQUEST_TIMEOUT_SECONDS
→ integer 5..60
→ > WEB_ADMIN_MAX_QUERY_DURATION_SECONDS
```

### Home Traffic tuning

Unconditional registered:

```text
WEB_ADMIN_HOME_TRAFFIC_REFRESH_SECONDS = integer 60..300
WEB_ADMIN_HOME_TRAFFIC_PAGE_SIZE = integer 1..250
```

Graph-enabled only:

```text
WEB_ADMIN_HOME_TRAFFIC_REQUEST_TIMEOUT_SECONDS = 5..60 and > max query duration
WEB_ADMIN_HOME_TRAFFIC_FRESH_MAX_AGE_SECONDS = 30..300
WEB_ADMIN_HOME_TRAFFIC_STALE_MAX_AGE_SECONDS = 30..600
WEB_ADMIN_HOME_TRAFFIC_MAX_AP_SKEW_SECONDS = 10..180
stale >= fresh
```

### Traffic tuning

Unconditional registered:

```text
WEB_ADMIN_TRAFFIC_REFRESH_SECONDS = integer 60..300
```

Graph-enabled only for `traffic.root`:

```text
WEB_ADMIN_TRAFFIC_REQUEST_TIMEOUT_SECONDS = 5..60
and > WEB_ADMIN_MAX_QUERY_DURATION_SECONDS
```

All existing General registered scalars remain unconditionally primitive-validated. This includes deferred `WEB_ADMIN_HOME_AP_24H_REFRESH_SECONDS`; AP-24H enable/telemetry configuration remains outside Stage 6.

Admin security/bootstrap/common query-control validation remains unchanged and unconditional under its existing owner.

```text
TL-S6-P1-02 = CLOSED
```

---

# 3. TL-S6-P1-03 — CROSS-DOMAIN GRAPH-AWARE VALIDATION

Permanent invariant:

```text
a dormant-valid Feature combination remains valid through:
Feature mutation
General mutation
Controller mutation
Portal mutation
main startup validation
```

One common Stage-6-aware Admin semantic boundary must replace raw parent/child rejection as an independent validator.

Every candidate snapshot gets exactly one transient candidate Feature graph for that validation transaction.

Exact domain matrix:

```text
GENERAL mutation
→ graph-aware Admin validation
→ existing full Controller secret semantics
→ existing Portal validation

CONTROLLER mutation
→ graph-aware Admin validation
→ existing full Controller secret semantics
→ existing Portal validation

PORTAL mutation
→ graph-aware Admin validation
→ non-secret Controller prerequisite validation
→ Portal validation
→ NO secret resolve/decrypt/master-key access

FEATURES mutation
→ General primitive validation
→ Feature primitive validation
→ candidate Feature graph
→ graph-enabled Feature prerequisites
→ base Admin/security startup validation
→ non-secret Controller prerequisite validation
→ Portal validation
→ NO secret resolve/decrypt/master-key access

MAIN SETTINGS-ENABLED STARTUP
→ one startup Feature plan
→ graph-aware validation
→ existing full Controller secret semantics
→ existing Portal validation
```

The old raw fail-closed checks must not reject these admitted dormant combinations through any path:

```text
Home Traffic=true / Home Live=false
Activity=true / Home Live=false
History=true / Traffic=false
Statistics=true / History=false
Peak=true / Statistics=false
By AP=true / History=false
Independent Ranges=true / History=false
AP Share=true / Independent Ranges=false
Online Guests=true / Traffic=false
Completed Sessions=true / Traffic=false
Evidence=true / Traffic=false
admitted Feature=true / WEB_ADMIN_ENABLED=false
```

Only positively established required composition for:

```text
feature_plan.effective_state(feature) == enabled
```

may cause:

```text
features_configuration_adoption_failed
```

Raw own child=true is not sufficient.

Runtime/source failures, silence, missing source data, query timeout, stale data or projection unavailability do not become that activation failure.

```text
TL-S6-P1-03 = CLOSED
```

---

# 4. TL-S6-P1-04 — EXISTING GENERAL consumer_state

Affected General definitions whose consumer is an admitted Stage-6 Feature:

```text
WEB_ADMIN_CURRENT_STATE_PAGE_SIZE
WEB_ADMIN_HOME_LIVE_REFRESH_SECONDS
→ home.live

WEB_ADMIN_HOME_TRAFFIC_PAGE_SIZE
WEB_ADMIN_HOME_TRAFFIC_REFRESH_SECONDS
→ home.traffic

WEB_ADMIN_TRAFFIC_REFRESH_SECONDS
→ traffic.root

WEB_ADMIN_HOME_ACTIVITY_REFRESH_SECONDS
→ home.activity

WEB_ADMIN_HOME_HEALTH_REFRESH_SECONDS
→ home.health
```

No General API enum expansion is introduced. Existing public `consumer_state` remains:

```text
active
consumer_disabled
null
```

Exact mapping:

```text
effective_feature_state = enabled
→ consumer_state = active
→ effective_value = adopted General value

effective_feature_state = disabled
→ consumer_state = consumer_disabled
→ effective_value = null

effective_feature_state = dormant_parent_disabled
→ consumer_state = consumer_disabled
→ effective_value = null

effective_feature_state = runtime_unavailable
→ consumer_state = null
→ effective_value = null
```

General Settings must never claim a dormant Feature consumer is active.

Stage-1 pending behavior is not redefined:

```text
pending_value = configured General value
when configured_generation != effective_generation
else null
```

This remains independent of consumer_state because it represents generation adoption, not consumer health. Existing General `pending_setting_count` semantics remain unchanged.

A pending Feature disable does not change General effective consumer state before restart; effective plan remains authoritative until adoption.

Deferred:

```text
WEB_ADMIN_HOME_AP_24H_REFRESH_SECONDS
```

continues its existing Stage-1 raw/deferred consumer mapping through `web_admin_home_ap_24h_enabled`. No dormant state is fabricated for AP-24H.

```text
TL-S6-P1-04 = CLOSED
```

---

# 5. TL-S6-P1-05 — COMPLETE SETTINGS SCHEMA v5 CONTRACT

## 5.1 Version / overrides

```text
SETTINGS_SCHEMA_VERSION = 5
```

`settings_overrides` storage remains unchanged:

```text
value_type IN ('integer','string')

integer:
  typeof(integer_value)='integer'
  string_value IS NULL

string:
  integer_value IS NULL
  typeof(string_value)='text'
```

Features use:

```text
value_type='string'
string_value='true'|'false'
integer_value=NULL
```

Exact true/false is also enforced by registry/history validation.

## 5.2 Audit domain and exact type CHECK

`settings_mutation_audit.setting_domain`:

```text
general
controller
portal
features
```

`value_type` remains `integer|string`.

Exact semantic CHECK:

```sql
CHECK(
    (
        setting_domain='general'
        AND value_type='integer'
        AND typeof(previous_configured_value)='integer'
        AND typeof(new_configured_value)='integer'
        AND (
            previous_persisted_override IS NULL
            OR typeof(previous_persisted_override)='integer'
        )
        AND (
            new_persisted_override IS NULL
            OR typeof(new_persisted_override)='integer'
        )
    )
    OR
    (
        setting_domain IN ('controller','portal','features')
        AND value_type='string'
        AND typeof(previous_configured_value)='text'
        AND typeof(new_configured_value)='text'
        AND (
            previous_persisted_override IS NULL
            OR typeof(previous_persisted_override)='text'
        )
        AND (
            new_persisted_override IS NULL
            OR typeof(new_persisted_override)='text'
        )
    )
)
```

Thus:

```text
general → integer
controller → string
portal → string
features → string
```

Configured audit values remain NOT NULL. Persisted override fields may be NULL for absence/clear; when non-null their SQLite typeof must match the domain exactly.

## 5.3 Idempotency domain

`settings_idempotency.mutation_domain` exact set:

```text
general
controller
controller_secret
portal
features
```

Existing fingerprint/receipt semantics remain unchanged.

## 5.4 Exact v4→v5 rebuilt tables

Only:

```text
settings_mutation_audit
settings_idempotency
```

are rebuilt, because their CHECK enums change.

Not rebuilt:

```text
settings_generations
settings_overrides
settings_target_state
settings_activation_events
controller_secret_versions
settings_secret_bindings
settings_secret_mutation_audit
```

## 5.5 Exact v4→v5 migration sequence

Inside the existing SettingsRepository write transaction:

```text
1. require user_version=4
2. validate exact v4 schema
3. validate v4 history, including quick_check + foreign_key_check
4. validate Controller secret history
5. rebuild settings_mutation_audit:
   - drop immutable UPDATE/DELETE triggers
   - rename to *_v4
   - create exact v5 table
   - copy rows/columns 1:1
   - drop *_v4
   - restore immutable UPDATE/DELETE triggers
6. rebuild settings_idempotency with the same bounded sequence
7. PRAGMA user_version=5
8. validate exact complete v5 table+trigger schema
9. PRAGMA quick_check must return ok
10. PRAGMA foreign_key_check must return zero rows
11. validate complete v5 Settings history
12. validate Controller secret history
13. commit only after all checks pass
```

Any failure rolls back the whole migration and yields `settings_store_unavailable`.

## 5.6 Immutable triggers after migration

Existing ordinary immutable tables remain:

```text
settings_generations
settings_overrides
settings_activation_events
settings_mutation_audit
settings_idempotency
```

Each retains immutable UPDATE + DELETE triggers raising:

```text
immutable settings history
```

`settings_target_state` remains intentionally mutable.

Secret trigger semantics remain unchanged:

```text
controller_secret_versions → immutable UPDATE; controlled GC may DELETE
settings_secret_bindings → immutable UPDATE + DELETE
settings_secret_mutation_audit → immutable UPDATE + DELETE
```

Exact post-migration schema validation must prove trigger restoration.

## 5.7 Creation / legacy entry paths

Empty store:

```text
user_version=0 + no tables
→ create exact v5 directly
→ create existing generation 0 + target row
```

Legacy compatibility is retained; no supported entry version is dropped.

```text
v1
→ validate v1 legacy schema/history
→ v1→v2
→ v2→v3
→ v3→v4
→ v4→v5
→ exact v5 validation

v2
→ validate v2 schema/history
→ v2→v3
→ v3→v4
→ v4→v5
→ exact v5 validation

v3
→ validate v3 schema/history + secret history
→ v3→v4
→ v4→v5
→ exact v5 validation

v4
→ validate v4 schema/history + secret history
→ v4→v5
→ exact v5 validation

v5
→ no migration
→ exact v5 schema + quick_check + FK + history + secret validation
```

Future/unknown versions fail closed.

All paths preserve generation IDs/parents/effective target, ordinary overrides, all ordinary audit/idempotency response bytes, activation history, secret versions/bindings/audit/idempotency.

Migration creates no generation, Feature override, mutation audit, activation event or Feature idempotency receipt.

`open_existing_for_recovery()` becomes current-schema-aware for `SETTINGS_SCHEMA_VERSION=5`, does not migrate/create, and must pass the mandatory:

```text
v5 + Stage-4 break-glass recovery = PASS
```

Feature overrides are copied unchanged by a recovery generation.

```text
TL-S6-P1-05 = CLOSED
```

---

# 6. TL-S6-P1-06 — SETTINGS NAVIGATION TARGET

Canonical visible Settings order is:

```text
General
→ Features
→ Controller
→ Portal
```

Let:

```text
general_allowed = Settings enabled AND admin.read.settings.global
features_allowed = Settings enabled AND admin.read.settings.features
controller_allowed = Settings enabled AND admin.read.settings.controller
portal_allowed = Settings enabled AND admin.read.settings.portal
```

Then:

```text
settings_nav_enabled =
general_allowed OR
features_allowed OR
controller_allowed OR
portal_allowed
```

Exact target:

```text
if general_allowed:
    /admin/settings
elif features_allowed:
    /admin/settings/features
elif controller_allowed:
    /admin/settings/controller
elif portal_allowed:
    /admin/settings/portal
else:
    no Settings navigation entry
```

A Features-only read principal therefore has a working top-level Settings link to:

```text
/admin/settings/features
```

and never lands on an inaccessible General page.

Examples:

```text
General + Features → /admin/settings
Features + Controller → /admin/settings/features
Controller + Portal → /admin/settings/controller
Portal only → /admin/settings/portal
```

Store unavailability does not change authorization-derived tab visibility/target; the selected tab renders its bounded unavailable state.

```text
TL-S6-P1-06 = CLOSED
```

---

# 7. R1 COMPLETION GATE

```text
TL-S6-P1-01 = CLOSED
TL-S6-P1-02 = CLOSED
TL-S6-P1-03 = CLOSED
TL-S6-P1-04 = CLOSED
TL-S6-P1-05 = CLOSED
TL-S6-P1-06 = CLOSED

OPEN P0 = 0
OPEN P1 = 0

ARCHITECTURE =
READY FOR TECH LEAD R1 DISPOSITION

IMPLEMENTATION TASK = HOLD
CODER = HOLD
SCHEMA CHANGE = NO
PRODUCTION CHANGE = NO
```

No other Stage-6 Architecture v0.1 decision is reopened by this Addendum.

Until Tech Lead R1 acceptance, implementation remains unauthorized.
